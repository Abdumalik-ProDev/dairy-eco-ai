"""Developer Mode for DairyEco AI — Technical ML, Data, Provenance & Execution Inspector.

Preserves all 5 technical workbench tabs (A–E) plus the 17-section ML Engineering Lab & Audit Center,
optimized with dynamic tabs (``on_change="rerun"``), ``st.form`` batching, and shared logic from
``dairyeco.models.registry`` so hidden tabs and slider drags never trigger redundant CV runs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import altair as alt
import joblib
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.pipeline import Pipeline

from dairyeco.audit import experiments as xp
from dairyeco.config import ARTIFACTS_DIR, PROCESSED_DIR
from dairyeco.domain.models import (
    DairyProductRecord,
    EnvironmentalResult,
    PackageConfiguration,
    ScenarioAssumptions,
    ScenarioComparisonResult,
)
from dairyeco.models.registry import (
    FEATURE_DESCRIPTIONS,
    FORBIDDEN_LEAKAGE_COLUMNS,
    INT_PARAMS,
    MODEL_REGISTRY,
    PARAM_SPECS,
    assert_no_feature_leakage,
    build_experimental_estimator,
    build_preprocessor,
    build_surrogate_feature_df,
    extract_estimator_params,
    get_task_summary_dict,
    load_task_frame,
    run_cv_experiment,
)


@st.cache_resource(max_entries=4)
def load_ml_artifacts() -> tuple[dict[str, Any], dict[str, Pipeline]]:
    """Load ML evaluation summary JSON and all 5 trained production pipelines from disk."""
    summary_path = ARTIFACTS_DIR / "ml_evaluation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pipelines: dict[str, Pipeline] = {}
    for key, meta in MODEL_REGISTRY.items():
        p_path = ARTIFACTS_DIR / meta["artifact_file"]
        if p_path.exists():
            pipelines[key] = joblib.load(p_path)
    return summary, pipelines


@st.cache_data(max_entries=16)
def load_task_dataset(task_key: str) -> pd.DataFrame:
    """Load the underlying dataset for the selected ML task (cached)."""
    return load_task_frame(task_key)


def build_surrogate_feature_row(
    product: DairyProductRecord,
    package_config: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    env_result: EnvironmentalResult | None = None,
) -> pd.DataFrame:
    """Compatibility wrapper returning the 1-row DataFrame for Task 3 surrogate models."""
    eff_trips = env_result.effective_reuse_trips if env_result is not None else None
    return build_surrogate_feature_df(product, package_config, assumptions, eff_trips)


def run_in_memory_cv_experiment(
    task_key: str,
    arch_name: str,
    params: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Run controlled in-memory CV via the shared registry runner."""
    return run_cv_experiment(
        task_key=task_key,
        arch=arch_name,
        params=params,
        summary=summary,
        return_fitted_pipeline=True,
    )


def _extract_estimator_params(pipe: Pipeline) -> dict[str, Any]:
    """Compatibility alias for ``dairyeco.models.registry.extract_estimator_params``."""
    return extract_estimator_params(pipe)


def render_param_widgets(arch: str, prefix: str) -> dict[str, Any]:
    """Render shared hyperparameter widgets for any supported experimental architecture."""
    out: dict[str, Any] = {}
    cols = st.columns(2)
    for idx, (param_name, (lo, hi, default, step)) in enumerate(PARAM_SPECS[arch].items()):
        with cols[idx % 2]:
            if param_name in INT_PARAMS:
                out[param_name] = int(
                    st.number_input(
                        param_name,
                        min_value=int(lo),
                        max_value=int(hi),
                        value=int(default),
                        step=int(step),
                        key=f"{prefix}_{arch}_{param_name}",
                    )
                )
            else:
                out[param_name] = float(
                    st.number_input(
                        param_name,
                        min_value=float(lo),
                        max_value=float(hi),
                        value=float(default),
                        step=float(step),
                        key=f"{prefix}_{arch}_{param_name}",
                    )
                )
    return out


def compute_local_feature_attributions(
    pipeline: Pipeline,
    X_background: pd.DataFrame,
    x_instance: pd.DataFrame,
    max_bg_samples: int = 80,
) -> tuple[float, float, pd.DataFrame]:
    """Compute additive local feature attributions (one-feature-at-a-time marginal shifts)."""
    bg = (
        X_background.sample(n=min(len(X_background), max_bg_samples), random_state=42)
        if len(X_background) > max_bg_samples
        else X_background.copy()
    )
    base_preds = pipeline.predict(bg)
    expected_value = float(np.mean(base_preds))
    instance_pred = float(pipeline.predict(x_instance)[0])
    total_diff = instance_pred - expected_value

    raw_effects: list[float] = []
    cols = list(x_instance.columns)
    for col in cols:
        perturbed = bg.copy()
        perturbed[col] = x_instance[col].iloc[0]
        effect = float(np.mean(pipeline.predict(perturbed)) - expected_value)
        raw_effects.append(effect)

    raw_arr = np.array(raw_effects, dtype=float)
    raw_sum = float(np.sum(raw_arr))
    scaled_arr = raw_arr * (total_diff / raw_sum) if abs(raw_sum) > 1e-6 else raw_arr

    rows = [
        {
            "feature": col,
            "input_value": str(x_instance[col].iloc[0]),
            "attribution": round(float(scaled_arr[i]), 4),
            "abs_attribution": round(abs(float(scaled_arr[i])), 4),
        }
        for i, col in enumerate(cols)
    ]
    df_attr = pd.DataFrame(rows).sort_values("abs_attribution", ascending=False)
    return expected_value, instance_pred, df_attr


def _get_active_explain_row(
    task_key: str,
    task_meta: dict[str, Any],
    task_df: pd.DataFrame,
    feature_cols: list[str],
    selected_product: DairyProductRecord,
    proposed_cfg: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    prop_comp: ScenarioComparisonResult,
) -> pd.DataFrame:
    """Build or select the active 1-row feature DataFrame for the chosen task."""
    if task_meta["supports_live_scenario"]:
        return build_surrogate_feature_row(
            selected_product, proposed_cfg, assumptions, prop_comp.environmental
        )
    idx = int(st.session_state.get(f"dev_sample_idx_{task_key}", 0))
    idx = max(0, min(idx, len(task_df) - 1))
    return task_df[feature_cols].iloc[[idx]]


def render_developer_mode(
    selected_product: DairyProductRecord,
    baseline_cfg: PackageConfiguration,
    proposed_cfg: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    base_comp: ScenarioComparisonResult,
    prop_comp: ScenarioComparisonResult,
) -> None:
    """Render the complete 5-tab Developer Mode workbench + 17-section Audit Lab."""
    summary, prod_pipelines = load_ml_artifacts()

    st.divider()
    dev_view = st.segmented_control(
        "Developer view",
        options=["workbench", "lab"],
        default="workbench",
        format_func=lambda v: (
            "Technical workbench" if v == "workbench" else "ML Engineering Lab & Audit (17 sections)"
        ),
        key="dev_view",
    )
    if dev_view == "lab":
        from dairyeco.dashboard.audit_lab import render_ml_lab

        render_ml_lab(
            selected_product, baseline_cfg, proposed_cfg, assumptions, base_comp, prop_comp
        )
        return

    with st.container(border=True):
        st.badge(
            "Developer Mode Active — Read-Only Production Artifacts",
            icon=":material/terminal:",
            color="violet",
        )
        st.markdown("### :material/developer_board: Developer Mode & Technical Inspection Workbench")
        st.caption(
            "Inspect all 5 registered ML pipelines, compare all 8 candidate algorithms per task, "
            "audit dataset preprocessing and holdout generalization, trace deterministic vs. surrogate "
            "execution, and run controlled in-memory hyperparameter experiments."
        )

        selected_task_key = st.selectbox(
            "Active ML task / registered model pipeline",
            options=list(MODEL_REGISTRY.keys()),
            index=0,
            format_func=lambda k: MODEL_REGISTRY[k]["label"],
            key="dev_active_task_key",
        )

        task_meta = MODEL_REGISTRY[selected_task_key]
        task_summary = get_task_summary_dict(summary, selected_task_key)
        prod_pipe = prod_pipelines[selected_task_key]
        task_df = load_task_dataset(selected_task_key)
        feature_cols: list[str] = task_summary["feature_columns"]
        target_col: str = task_meta["target_col"]

        tab_a, tab_b, tab_c, tab_d, tab_e = st.tabs(
            [
                ":material/tune: A. ML Model Configuration",
                ":material/database: B. Data Transparency",
                ":material/insights: C. Model Transparency",
                ":material/account_tree: D. Execution Trace",
                ":material/science: E. Experimentation",
            ],
            on_change="rerun",
        )

        # =====================================================================
        # TAB A: ML Model Configuration & Live Inference
        # =====================================================================
        if tab_a.open:
            with tab_a:
                st.markdown("#### A. ML Model Configuration & Live Inference")
                col_cfg1, col_cfg2 = st.columns([1.15, 1.25], gap="medium")
                exp_pipe_key = f"dev_tab_a_exp_pipe_{selected_task_key}"

                with col_cfg1, st.container(border=True):
                    mode_choice = st.segmented_control(
                        "Inference configuration source",
                        options=["production", "experimental"],
                        default="production",
                        format_func=lambda m: (
                            "Production champion" if m == "production" else "Experimental (in-memory)"
                        ),
                        key="dev_cfg_source_mode",
                    )

                    if mode_choice != "experimental":
                        st.badge(
                            f"TRAINED PRODUCTION MODEL: {task_summary['best_model_name']}",
                            icon=":material/verified:",
                            color="green",
                        )
                        st.caption(
                            f"Artifact: `artifacts/models/{task_meta['artifact_file']}` | "
                            f"Validation: `{task_meta['cv_type']}`"
                        )
                        st.markdown("**Production estimator configuration & defaults:**")
                        st.json(extract_estimator_params(prod_pipe), expanded=False)
                        active_infer_pipe = prod_pipe
                    else:
                        st.badge(
                            "EXPERIMENTAL CONFIGURATION (In-Memory Sandbox)",
                            icon=":material/science:",
                            color="orange",
                        )
                        exp_arch = st.selectbox(
                            "Estimator architecture",
                            options=list(PARAM_SPECS.keys()),
                            key="dev_tab_a_arch",
                        )
                        with st.form("dev_tab_a_exp_form"):
                            exp_params = render_param_widgets(exp_arch, "tab_a")
                            fit_btn = st.form_submit_button(
                                "Fit experimental model (in-memory)",
                                type="primary",
                                icon=":material/play_arrow:",
                            )
                        if fit_btn or exp_pipe_key not in st.session_state:
                            num_c = [
                                c for c in feature_cols if pd.api.types.is_numeric_dtype(task_df[c])
                            ]
                            cat_c = [c for c in feature_cols if c not in num_c]
                            min_f = 2 if len(task_df) < 80 else None
                            exp_pipe = Pipeline(
                                [
                                    ("prep", build_preprocessor(num_c, cat_c, min_frequency=min_f)),
                                    ("reg", build_experimental_estimator(exp_arch, exp_params)),
                                ]
                            )
                            exp_pipe.fit(task_df[feature_cols], task_df[target_col])
                            st.session_state[exp_pipe_key] = exp_pipe
                        active_infer_pipe = st.session_state[exp_pipe_key]

                with col_cfg2, st.container(border=True):
                    st.markdown("##### Live Model Inference Execution")
                    if task_meta["supports_live_scenario"]:
                        st.caption(
                            f"Executing live surrogate inference on your selected scenario: "
                            f"**{selected_product.name_en}** (`{proposed_cfg.name}` vs `{baseline_cfg.name}`)."
                        )
                        X_base_row = build_surrogate_feature_row(
                            selected_product, baseline_cfg, assumptions, base_comp.environmental
                        )
                        X_prop_row = build_surrogate_feature_row(
                            selected_product, proposed_cfg, assumptions, prop_comp.environmental
                        )
                        pred_base_active = float(active_infer_pipe.predict(X_base_row)[0])
                        pred_prop_active = float(active_infer_pipe.predict(X_prop_row)[0])
                        pred_prop_prod = float(prod_pipe.predict(X_prop_row)[0])

                        if selected_task_key == "task3a_surrogate_gwp":
                            det_prop = prop_comp.environmental.packaging_system_total_gwp_kgco2e
                            unit_lbl = "kg CO₂e / FU"
                        else:
                            det_prop = prop_comp.economic.total_packaging_attributable_cost_per_fu
                            unit_lbl = "USD / FU"

                        inf_m1, inf_m2, inf_m3 = st.columns(3)
                        inf_m1.metric(
                            f"Active ML Prediction ({unit_lbl})",
                            f"{pred_prop_active:,.2f}",
                            delta=f"{pred_prop_active - pred_base_active:+,.2f} vs baseline",
                            delta_color="inverse",
                            border=True,
                        )
                        inf_m2.metric(
                            f"Production Champion ({unit_lbl})",
                            f"{pred_prop_prod:,.2f}",
                            delta=f"{pred_prop_active - pred_prop_prod:+,.2f} active vs prod",
                            delta_color="off",
                            border=True,
                        )
                        inf_m3.metric(
                            f"Deterministic Engine ({unit_lbl})",
                            f"{det_prop:,.2f}",
                            delta=f"Surrogate err: {pred_prop_active - det_prop:+,.2f}",
                            delta_color="off",
                            border=True,
                        )
                    else:
                        name_col = (
                            "name_en"
                            if "name_en" in task_df.columns
                            else ("cheese_name" if "cheese_name" in task_df.columns else task_df.columns[0])
                        )
                        sample_idx = st.selectbox(
                            "Select dataset record for live inference",
                            options=list(range(len(task_df))),
                            index=0,
                            format_func=lambda idx: f"Row {idx}: {task_df[name_col].iloc[idx]}",
                            key=f"dev_sample_idx_{selected_task_key}",
                        )
                        x_row = task_df[feature_cols].iloc[[sample_idx]]
                        actual_y = float(task_df[target_col].iloc[sample_idx])
                        pred_active = float(active_infer_pipe.predict(x_row)[0])
                        pred_prod = float(prod_pipe.predict(x_row)[0])

                        im1, im2, im3 = st.columns(3)
                        im1.metric(
                            f"Active ML Prediction ({task_meta['target_unit']})",
                            f"{pred_active:.3f}",
                            delta=f"Err vs actual: {pred_active - actual_y:+.3f}",
                            delta_color="off",
                            border=True,
                        )
                        im2.metric(
                            f"Production Champion ({task_meta['target_unit']})",
                            f"{pred_prod:.3f}",
                            delta=f"{pred_active - pred_prod:+.3f} active vs prod",
                            delta_color="off",
                            border=True,
                        )
                        im3.metric(
                            f"Published Reference Value ({task_meta['target_unit']})",
                            f"{actual_y:.3f}",
                            border=True,
                        )

        # =====================================================================
        # TAB B: Data Transparency
        # =====================================================================
        if tab_b.open:
            with tab_b:
                st.markdown("#### B. Data Transparency, Preprocessing & Provenance")
                d_col1, d_col2 = st.columns([1.1, 1.3], gap="medium")
                x_explain_row = _get_active_explain_row(
                    selected_task_key,
                    task_meta,
                    task_df,
                    feature_cols,
                    selected_product,
                    proposed_cfg,
                    assumptions,
                    prop_comp,
                )

                with d_col1, st.container(border=True):
                    st.markdown("##### Dataset Identity & Provenance")
                    assert_no_feature_leakage(feature_cols, target_col)
                    st.markdown(
                        f"- **Dataset Name:** {task_meta['dataset_name']}\n"
                        f"- **Authoritative Source:** {task_meta['source_authority']}\n"
                        f"- **Epistemic Classification (`DataSourceType`):** `{task_meta['source_type']}`\n"
                        f"- **Underlying File:** `{task_meta['dataset_file'].relative_to(PROCESSED_DIR.parent.parent)}`\n"
                        f"- **Sample Count (`N`):** `{len(task_df):,}` observations × `{len(feature_cols)}` features\n"
                        f"- **Target Column:** `{target_col}` (`{task_meta['target_unit']}`)\n"
                        f"- **Leakage Guard (`assert_no_feature_leakage`):** Passed (`{len(FORBIDDEN_LEAKAGE_COLUMNS)}` forbidden columns excluded)"
                    )

                    num_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(task_df[c])]
                    cat_cols = [c for c in feature_cols if c not in num_cols]
                    prep_step = prod_pipe.named_steps["prep"]
                    transformed_sample = prep_step.transform(task_df[feature_cols].iloc[:5])
                    ohe_step = prep_step.named_transformers_["cat"].named_steps["ohe"]

                    st.markdown("##### Preprocessing & Transformation Pipeline (`ColumnTransformer`)")
                    st.markdown(
                        f"1. **Numeric Pipeline (`{len(num_cols)}` columns):**\n"
                        f"   - **Missing-Value Handling:** `SimpleImputer(strategy='median')`\n"
                        f"   - **Scaling:** `RobustScaler()` (median-centered, IQR-scaled)\n"
                        f"2. **Categorical Pipeline (`{len(cat_cols)}` columns):**\n"
                        f"   - **Missing-Value Handling:** `SimpleImputer(strategy='most_frequent')`\n"
                        f"   - **Encoding:** `OneHotEncoder(handle_unknown='{ohe_step.handle_unknown}', min_frequency={ohe_step.min_frequency})`\n"
                        f"3. **Post-Transform Design Matrix Shape:** `{len(task_df)} rows × {transformed_sample.shape[1]} encoded columns`"
                    )

                with d_col2, st.container(border=True):
                    st.markdown("##### Feature Dictionary & Missing-Value Audit")
                    schema_rows = [
                        {
                            "Feature": col,
                            "Type": "numeric" if pd.api.types.is_numeric_dtype(task_df[col]) else "categorical",
                            "Missing": int(task_df[col].isna().sum()),
                            "Example / Summary": (
                                f"mean={task_df[col].mean():.3g}, std={task_df[col].std():.3g}"
                                if pd.api.types.is_numeric_dtype(task_df[col])
                                else f"{task_df[col].nunique()} unique ({task_df[col].iloc[0]})"
                            ),
                            "Description": FEATURE_DESCRIPTIONS.get(col, "Domain feature"),
                        }
                        for col in feature_cols
                    ]
                    st.dataframe(
                        pd.DataFrame(schema_rows),
                        hide_index=True,
                        height=340,
                        alt="Feature dictionary and missing-value audit table.",
                    )

                data_exp = st.expander(
                    ":material/table_view: Inspect active inference feature vector & sample training records",
                    on_change="rerun",
                )
                if data_exp.open:
                    with data_exp:
                        st.markdown("**Active Inference Input Vector (`1 × p`):**")
                        st.dataframe(x_explain_row, hide_index=True, alt="Active inference feature vector.")
                        st.markdown("**Training Dataset Sample (`Top 10 rows`):**")
                        st.dataframe(
                            task_df[[*feature_cols[:8], target_col]].head(10),
                            hide_index=True,
                            alt="Top 10 training records.",
                        )

        # =====================================================================
        # TAB C: Model Transparency & All-Models Comparison
        # =====================================================================
        if tab_c.open:
            with tab_c:
                st.markdown("#### C. Model Transparency, Cross-Validation & All-Models Comparison")
                artifact_path: Path = ARTIFACTS_DIR / task_meta["artifact_file"]
                mtime_str = (
                    datetime.fromtimestamp(artifact_path.stat().st_mtime, tz=UTC).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                    if artifact_path.exists()
                    else "N/A"
                )
                diag = task_summary["champion_diagnostics"]
                ho = task_summary.get("holdout_metrics", {})

                m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5, gap="small")
                m_c1.metric(
                    "Champion Architecture",
                    task_summary["best_model_name"],
                    delta=f"Fit: {diag['fit_diagnosis']}",
                    border=True,
                )
                m_c2.metric(
                    f"Dev OOF MAE ({task_meta['target_unit']})",
                    f"{diag['oof_mae']:.4f}",
                    delta=f"Holdout MAE: {ho.get('holdout_mae', diag.get('holdout_mae', 'N/A'))}",
                    delta_color="off",
                    border=True,
                )
                m_c3.metric(
                    "Dev OOF R² / Holdout R²",
                    f"{diag['oof_r2']:.4f}",
                    delta=f"Holdout R²: {ho.get('holdout_r2', diag.get('holdout_r2', 'N/A'))} (n={ho.get('holdout_n', diag.get('holdout_n', '?'))})",
                    delta_color="normal",
                    border=True,
                )
                m_c4.metric(
                    "R² Generalization Gap",
                    f"{diag['r2_generalization_gap']:.4f}",
                    delta="Threshold ≤ 0.045",
                    delta_color="normal" if diag["r2_generalization_gap"] <= 0.045 else "inverse",
                    border=True,
                )
                m_c5.metric(
                    "Normalized MAE Gap",
                    f"{diag['normalized_mae_gap']:.4f}",
                    delta=f"Trained: {mtime_str[:10]}",
                    delta_color="off",
                    border=True,
                )

                st.markdown("##### All 5 Registered ML Tasks (Cross-Model Summary)")
                all_task_rows = []
                for tk_key, tk_meta in MODEL_REGISTRY.items():
                    tk_sum = get_task_summary_dict(summary, tk_key)
                    tk_d = tk_sum["champion_diagnostics"]
                    tk_ho = tk_sum.get("holdout_metrics", {})
                    all_task_rows.append(
                        {
                            "Task": tk_meta["label"].split(" (")[0],
                            "Source Type": tk_meta["source_type"],
                            "N": tk_sum["n_observations"],
                            "Champion": tk_sum["best_model_name"],
                            "Dev OOF MAE": tk_d["oof_mae"],
                            "Dev OOF R²": tk_d["oof_r2"],
                            "Holdout MAE": tk_ho.get("holdout_mae", tk_d.get("holdout_mae")),
                            "Holdout R²": tk_ho.get("holdout_r2", tk_d.get("holdout_r2")),
                            "Fit Diagnosis": tk_d["fit_diagnosis"],
                        }
                    )
                st.dataframe(
                    pd.DataFrame(all_task_rows),
                    hide_index=True,
                    alt="Summary of champion models across all 5 registered ML tasks.",
                )

                st.markdown("##### Candidate Benchmark & Generalization Audit Table (8 Algorithms)")
                metrics_df = pd.DataFrame(task_summary["metrics"])
                display_cols = [
                    "model_name",
                    "is_selected_champion",
                    "fit_diagnosis",
                    "mae",
                    "cv_mae_mean",
                    "cv_mae_std",
                    "train_mae_mean",
                    "normalized_mae_gap",
                    "r2",
                    "train_r2_mean",
                    "r2_generalization_gap",
                    "rmse",
                ]
                st.dataframe(
                    metrics_df[[c for c in display_cols if c in metrics_df.columns]],
                    hide_index=True,
                    alt="Benchmark comparison across all 8 candidate algorithms for the active task.",
                )

                x_explain_row = _get_active_explain_row(
                    selected_task_key,
                    task_meta,
                    task_df,
                    feature_cols,
                    selected_product,
                    proposed_cfg,
                    assumptions,
                    prop_comp,
                )
                exp_col1, exp_col2 = st.columns(2, gap="medium")
                with exp_col1, st.container(border=True):
                    st.markdown("##### Global Feature Importance (Held-out OOF Permutation MAE)")
                    imp_df = pd.DataFrame(task_summary["feature_importances"]).head(12)
                    imp_chart = (
                        alt.Chart(imp_df)
                        .mark_bar(cornerRadiusEnd=4, color="#0f766e")
                        .encode(
                            y=alt.Y("feature:N", sort="-x", title=None),
                            x=alt.X(
                                "oof_mean_mae_importance:Q",
                                title=f"OOF Permutation MAE Importance ({task_meta['target_unit']})",
                            ),
                            tooltip=[
                                alt.Tooltip("feature:N"),
                                alt.Tooltip("oof_mean_mae_importance:Q", format=".4f"),
                                alt.Tooltip("oof_std_mae_importance:Q", format=".4f"),
                            ],
                        )
                        .properties(height=300)
                    )
                    st.altair_chart(
                        imp_chart,
                        alt="Horizontal bar chart of held-out Out-of-Fold permutation feature importance.",
                    )

                with exp_col2, st.container(border=True):
                    st.markdown("##### Local Additive Feature Attribution (Active Input)")
                    exp_val, inst_pred, attr_df = compute_local_feature_attributions(
                        prod_pipe, task_df[feature_cols], x_explain_row
                    )
                    st.caption(
                        f"Baseline Expectation E[f(X)] = **{exp_val:.3f}** → "
                        f"Prediction f(x) = **{inst_pred:.3f}** "
                        f"(Net shift = **{inst_pred - exp_val:+.3f} {task_meta['target_unit']}**)"
                    )
                    top_attr = attr_df.head(10).copy()
                    top_attr["direction"] = np.where(
                        top_attr["attribution"] >= 0, "Increases prediction", "Reduces prediction"
                    )
                    attr_chart = (
                        alt.Chart(top_attr)
                        .mark_bar(cornerRadiusEnd=4)
                        .encode(
                            y=alt.Y("feature:N", sort=None, title=None),
                            x=alt.X(
                                "attribution:Q",
                                title=f"Marginal contribution φ_j ({task_meta['target_unit']})",
                            ),
                            color=alt.Color(
                                "direction:N",
                                scale=alt.Scale(
                                    domain=["Reduces prediction", "Increases prediction"],
                                    range=["#0f766e", "#dc2626"],
                                ),
                                legend=alt.Legend(orient="top", title=None),
                            ),
                            tooltip=[
                                alt.Tooltip("feature:N"),
                                alt.Tooltip("input_value:N"),
                                alt.Tooltip("attribution:Q", format="+.4f"),
                            ],
                        )
                        .properties(height=270)
                    )
                    st.altair_chart(
                        attr_chart,
                        alt="Local marginal feature attribution chart for the active prediction.",
                    )

        # =====================================================================
        # TAB D: End-to-End Execution Trace
        # =====================================================================
        if tab_d.open:
            with tab_d:
                st.markdown("#### D. End-to-End Pipeline Execution Trace")
                st.markdown(
                    "`Source Data (AGRIBALYSE / NIST / USLCI / IFC)` → "
                    "`De-Packaging & Physical BOM Scaling` → "
                    "`Feature Vector / Factor Lookup` → "
                    "`Deterministic LCA & Financial Engine vs. ML Surrogate` → "
                    "`Executive Streamlit Dashboard`"
                )

                tr_col1, tr_col2 = st.columns(2, gap="medium")
                with tr_col1, st.container(border=True):
                    st.markdown("##### 1. Source Data & De-Packaging Boundary (`published_reference`)")
                    st.markdown(
                        f"- **Selected Product:** `{selected_product.name_en}` (`{selected_product.product_id}`, AGB `{selected_product.code_agb}`)\n"
                        f"- **Raw AGRIBALYSE Total GWP:** `{selected_product.total_gwp_kgco2e_per_kg:.3f} kg CO₂e/kg`\n"
                        f"- **Subtracted AGRIBALYSE `Emballage` Stage (`{selected_product.baseline_packaging_approach}`):** "
                        f"`-{selected_product.packaging_stage_gwp_kgco2e_per_kg:.3f} kg CO₂e/kg`\n"
                        f"- **De-Packaged Dairy Base GWP:** **`{selected_product.non_packaging_gwp_kgco2e_per_kg:.3f} kg CO₂e/kg`** "
                        f"(`{selected_product.non_packaging_gwp_kgco2e_per_kg * 1000.0:,.1f} kg CO₂e / FU`)\n"
                        f"- **Proposed Package BOM (`{proposed_cfg.config_id}`):** `{len(proposed_cfg.components)}` components, "
                        f"`{proposed_cfg.total_bom_mass_g:.1f} g` tare mass, "
                        f"`{prop_comp.environmental.packages_required_for_fu:,.1f}` saleable packages / FU"
                    )

                    st.markdown("##### 2. Deterministic Financial Cash Flow & Payback Trace (`assumed` / `scenario_estimate`)")
                    st.markdown(
                        f"- **Initial Investment (CAPEX + Installation):** `${prop_comp.initial_investment_usd:,.2f}`\n"
                        f"- **Baseline Operating Cost:** `${base_comp.economic.total_operating_cost_per_fu:,.2f} / FU` "
                        f"(Packaging: `${base_comp.economic.total_packaging_attributable_cost_per_fu:,.2f} / FU`)\n"
                        f"- **Proposed Operating Cost:** `${prop_comp.economic.total_operating_cost_per_fu:,.2f} / FU` "
                        f"(Packaging: `${prop_comp.economic.total_packaging_attributable_cost_per_fu:,.2f} / FU`)\n"
                        f"- **Unit Cost Delta (`Proposed - Baseline`):** `{prop_comp.delta_cost_per_fu:+,.2f} USD / FU` "
                        f"(`{prop_comp.delta_packaging_cost_pct:+.2f}%` packaging cost change)\n"
                        f"- **Annual Production Volume:** `{assumptions.annual_production_volume_kg / 1000.0:,.0f} FUs/yr` "
                        f"(`{assumptions.annual_production_volume_kg:,.0f} kg/yr`)\n"
                        f"- **Annual Incremental Net Cash Flow:** **`{prop_comp.annual_cash_flow_savings:+,.2f} USD / yr`**\n"
                        f"- **Payback Status (`{assumptions.project_lifetime_years}-yr horizon`):** `{prop_comp.payback_status}` — "
                        f"{prop_comp.payback_explanation}"
                    )

                with tr_col2, st.container(border=True):
                    st.markdown(
                        "##### 3. Deterministic Engine vs. ML Surrogate Comparison (per `1,000 kg` FU)"
                    )
                    X_prop_sur = build_surrogate_feature_row(
                        selected_product, proposed_cfg, assumptions, prop_comp.environmental
                    )
                    gwp_sur_pred = float(prod_pipelines["task3a_surrogate_gwp"].predict(X_prop_sur)[0])
                    cost_sur_pred = float(prod_pipelines["task3b_surrogate_cost"].predict(X_prop_sur)[0])

                    det_gwp = prop_comp.environmental.packaging_system_total_gwp_kgco2e
                    det_cost = prop_comp.economic.total_packaging_attributable_cost_per_fu

                    comp_trace_df = pd.DataFrame(
                        [
                            {
                                "Output Metric": "Packaging System GWP (kg CO₂e / FU)",
                                "Deterministic Engine (Exact LCA)": round(det_gwp, 2),
                                "ML Surrogate Prediction (Task 3A/3B)": round(gwp_sur_pred, 2),
                                "Difference (ML - Exact)": round(gwp_sur_pred - det_gwp, 2),
                                "Used in Executive UI?": "Yes — Exact LCA Engine",
                            },
                            {
                                "Output Metric": "Packaging Attributable Cost (USD / FU)",
                                "Deterministic Engine (Exact LCA)": round(det_cost, 2),
                                "ML Surrogate Prediction (Task 3A/3B)": round(cost_sur_pred, 2),
                                "Difference (ML - Exact)": round(cost_sur_pred - det_cost, 2),
                                "Used in Executive UI?": "Yes — Exact Economic Engine",
                            },
                            {
                                "Output Metric": "Simple Payback Period (years)",
                                "Deterministic Engine (Exact LCA)": (
                                    prop_comp.simple_payback_years
                                    if prop_comp.simple_payback_years is not None
                                    else "No payback"
                                ),
                                "ML Surrogate Prediction (Task 3A/3B)": "N/A (Deterministic accounting only)",
                                "Difference (ML - Exact)": "0.00",
                                "Used in Executive UI?": "Yes — Exact Cash Flow Schedule",
                            },
                        ]
                    )
                    st.dataframe(
                        comp_trace_df,
                        hide_index=True,
                        alt="Comparison between deterministic engines and ML surrogate predictions.",
                    )

                    st.markdown("##### 4. Provenance Records Attached to Active Scenario")
                    prov_rows = [
                        {
                            "Dataset ID": p.source_dataset_id,
                            "Record ID": p.source_record_id,
                            "Source Type": str(p.source_type),
                            "Geography": p.geography,
                            "Year": p.reference_year,
                            "Boundary / Notes": p.notes,
                        }
                        for p in prop_comp.environmental.provenance_records
                    ]
                    st.dataframe(
                        pd.DataFrame(prov_rows),
                        hide_index=True,
                        height=210,
                        alt="Provenance records attached to the active scenario.",
                    )

        # =====================================================================
        # TAB E: Controlled Experimentation Sandbox
        # =====================================================================
        if tab_e.open:
            with tab_e:
                st.markdown("#### E. Controlled Cross-Validation Experimentation Sandbox")
                st.caption(
                    "Modify estimator architecture and hyperparameters, run full out-of-fold cross-validation "
                    "on the development split in memory, and compare against the production champion without "
                    "overwriting disk models."
                )

                e_left, e_right = st.columns([1.0, 1.4], gap="medium")
                with e_left, st.container(border=True):
                    exp_arch_e = st.selectbox(
                        "Experimental estimator architecture",
                        options=list(PARAM_SPECS.keys()),
                        key="dev_tab_e_arch",
                    )
                    with st.form("dev_tab_e_form"):
                        exp_params_e = render_param_widgets(exp_arch_e, "tab_e")
                        log_to_tracker = st.checkbox(
                            "Log run to experiment tracker (experiments.jsonl)",
                            value=False,
                            key="dev_tab_e_log",
                        )
                        run_exp_btn = st.form_submit_button(
                            "Run cross-validation experiment (in-memory)",
                            type="primary",
                            icon=":material/play_arrow:",
                        )

                with e_right, st.container(border=True):
                    state_key = f"exp_result_{selected_task_key}"
                    if run_exp_btn:
                        with st.spinner("Running 5-fold cross-validation..."):
                            if log_to_tracker:
                                rec = xp.log_experiment(
                                    selected_task_key, exp_arch_e, exp_params_e, summary
                                )
                                exp_res = {
                                    "architecture": exp_arch_e,
                                    "hyperparameters": exp_params_e,
                                    **rec["metrics"],
                                }
                            else:
                                exp_res = run_cv_experiment(
                                    selected_task_key, exp_arch_e, exp_params_e, summary
                                )
                            st.session_state[state_key] = exp_res

                    if state_key not in st.session_state:
                        st.info(
                            "Configure hyperparameters on the left and click **Run cross-validation "
                            "experiment** to benchmark against the production champion.",
                            icon=":material/science:",
                        )
                    else:
                        exp_res = st.session_state[state_key]
                        prod_diag = task_summary["champion_diagnostics"]

                        st.markdown("##### Experimental Run vs. Production Champion Baseline")
                        comp_exp_df = pd.DataFrame(
                            [
                                {
                                    "Metric": f"Pooled OOF MAE ({task_meta['target_unit']})",
                                    "Production Champion": prod_diag["oof_mae"],
                                    "Experimental Model": exp_res["oof_mae"],
                                    "Delta (Exp - Prod)": round(
                                        exp_res["oof_mae"] - prod_diag["oof_mae"], 4
                                    ),
                                },
                                {
                                    "Metric": "In-Fold Train MAE",
                                    "Production Champion": prod_diag["train_mae_mean"],
                                    "Experimental Model": exp_res["train_mae_mean"],
                                    "Delta (Exp - Prod)": round(
                                        exp_res["train_mae_mean"] - prod_diag["train_mae_mean"], 4
                                    ),
                                },
                                {
                                    "Metric": "Pooled OOF R²",
                                    "Production Champion": prod_diag["oof_r2"],
                                    "Experimental Model": exp_res["oof_r2"],
                                    "Delta (Exp - Prod)": round(
                                        exp_res["oof_r2"] - prod_diag["oof_r2"], 4
                                    ),
                                },
                                {
                                    "Metric": "R² Generalization Gap (Train R² - OOF R²)",
                                    "Production Champion": prod_diag["r2_generalization_gap"],
                                    "Experimental Model": exp_res["r2_generalization_gap"],
                                    "Delta (Exp - Prod)": round(
                                        exp_res["r2_generalization_gap"]
                                        - prod_diag["r2_generalization_gap"],
                                        4,
                                    ),
                                },
                                {
                                    "Metric": "Normalized MAE Gap",
                                    "Production Champion": prod_diag["normalized_mae_gap"],
                                    "Experimental Model": exp_res["normalized_mae_gap"],
                                    "Delta (Exp - Prod)": round(
                                        exp_res["normalized_mae_gap"] - prod_diag["normalized_mae_gap"],
                                        4,
                                    ),
                                },
                                {
                                    "Metric": "Fit Diagnosis",
                                    "Production Champion": prod_diag["fit_diagnosis"],
                                    "Experimental Model": exp_res["fit_diagnosis"],
                                    "Delta (Exp - Prod)": (
                                        "Matches"
                                        if exp_res["fit_diagnosis"] == prod_diag["fit_diagnosis"]
                                        else f"{prod_diag['fit_diagnosis']} → {exp_res['fit_diagnosis']}"
                                    ),
                                },
                            ]
                        )
                        st.dataframe(
                            comp_exp_df,
                            hide_index=True,
                            alt="Experimental CV run versus production champion baseline.",
                        )
                        st.caption(
                            f"Experimental configuration: `{exp_res['architecture']}` with `{exp_res['hyperparameters']}`. "
                            f"Production `.joblib` files in `artifacts/models/` remain untouched."
                        )
