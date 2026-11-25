"""ML Engineering Lab & Model Audit Center (Developer Mode).

Reads persisted audit records from ``artifacts/audit/`` (built by ``dairyeco audit``) and the
experiment log. Nothing on these pages is hand-typed history: every table is derived from
code, data, artifacts or logs, and gaps are shown as "Not recorded / Unknown".
"""

from __future__ import annotations

import json
from typing import Any

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from dairyeco.audit import experiments as xp
from dairyeco.audit.build import build_audit, load_audit
from dairyeco.audit.common import NOT_RECORDED, sha256_file, symbol_source
from dairyeco.config import AUDIT_DIR, PROJECT_ROOT
from dairyeco.dashboard.dev_mode import (
    compute_local_feature_attributions,
    load_ml_artifacts,
    render_param_widgets,
)
from dairyeco.models.registry import (
    INT_PARAMS,
    MODEL_REGISTRY,
    PARAM_SPECS,
    build_surrogate_feature_df,
    get_task_summary_dict,
    load_task_frame,
)

PAGES = [
    "1. Project & pipeline overview", "2. Dataset registry", "3. Dataset selection & provenance",
    "4. Data integration & lineage", "5. Data cleaning & quality", "6. Exploratory data analysis",
    "7. Feature engineering", "8. Model registry", "9. Training & experiments", "10. Hyperparameter tuning",
    "11. Validation & testing", "12. Bias & reliability audit", "13. Explainability",
    "14. Prediction inspector", "15. Reproducibility & artifacts", "16. Code & decision traceability",
    "17. Open issues & recommendations",
]
STATUS_ICON = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "na": "N/A", "implemented": "implemented",
               "partial": "partial", "missing": "MISSING"}
LEVEL_LABEL = {"research_prototype": "Research prototype", "experimental": "Experimental",
               "validated": "Validated", "production_candidate": "Production candidate",
               "not_suitable": "Not suitable for use"}
LEVEL_COLOR = {"research_prototype": "orange", "experimental": "yellow", "validated": "blue",
               "production_candidate": "green", "not_suitable": "red"}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


@st.cache_data(show_spinner=False)
def _records(mtime: float) -> dict[str, Any] | None:
    return load_audit()


def _short(text: Any, n: int = 140) -> str:
    s = str(text)
    return s if len(s) <= n else s[: n - 1] + "…"


def _df(rows: list[dict[str, Any]], cols: list[str] | None = None, height: int | None = None) -> None:
    df = pd.DataFrame(rows)
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(
                lambda v: json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)
            )
    if height:
        st.dataframe(df, hide_index=True, height=height)
    else:
        st.dataframe(df, hide_index=True)


def _task_select(key: str, label: str = "Model / ML task") -> str:
    return st.selectbox(label, list(MODEL_REGISTRY), format_func=lambda k: MODEL_REGISTRY[k]["label"], key=key)


def _kind_note(source_type: str) -> None:
    if source_type == "model_derived":
        st.warning("Labels are produced by the deterministic LCA/economics engine (model-derived). "
                   "Metrics measure how well ML copies the engine.", icon=":material/science:")
    else:
        st.info(f"Labels come from a {source_type.replace('_', ' ')} source.", icon=":material/menu_book:")


# ----------------------------------------------------------------------------- pages
def _p_overview(A: dict[str, Any]) -> None:
    st.markdown("#### From raw dataset to displayed result")
    st.caption("Status of each engineering stage, checked against files, code and logs - not self-reported.")
    ov = A["pipeline_overview"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Implemented", sum(o["status"] == "implemented" for o in ov), border=True)
    c2.metric("Partial", sum(o["status"] == "partial" for o in ov), border=True)
    c3.metric("Missing", sum(o["status"] == "missing" for o in ov), border=True)
    _df(ov, ["stage", "status", "evidence", "code"])
    st.markdown("##### Model readiness (evidence-based gates)")
    rows = [{"model": MODEL_REGISTRY[k]["label"], "readiness": LEVEL_LABEL[v["level"]],
             "first blocker": _short(v["blockers"][0], 110) if v["blockers"] else "none"}
            for k, v in A["readiness"].items()]
    _df(rows)
    m = A["audit_manifest"]
    st.caption(f"Audit records generated {m['generated_at']} · code fingerprint "
               f"`{m['code_fingerprint']['aggregate_sha256'][:16]}` · {m['code_fingerprint']['vcs_commit']}")
    st.info("Legend: **verified** = computed from data/code/artifacts here; **inferred** = reasoned from code, "
            "labelled as such; **Not recorded / Unknown** = the project never stored it, and nothing was invented.",
            icon=":material/fact_check:")
    if st.button("Rebuild audit records (re-reads raw files, ~1 min)", icon=":material/refresh:", key="lab_rebuild"):
        with st.spinner("Rebuilding audit records..."):
            build_audit()
        st.cache_data.clear()
        st.rerun()


def _p_registry(A: dict[str, Any]) -> None:
    reg = A["dataset_registry"]
    st.markdown("#### Dataset registry")
    _df(reg["manifest"], ["dataset_id", "provider", "version", "geography", "reference_year", "file_count",
                          "identification_confidence", "licence"])
    st.markdown("##### Derived tables (profiled from the real files)")
    _df(reg["tables"], ["table", "file", "rows", "columns", "missing_cells", "duplicate_rows", "sha256"])
    if reg["unused_tables"]:
        st.warning(f"Tables with no consumer found in src/: {', '.join(reg['unused_tables'])}", icon=":material/link_off:")
    st.markdown("##### Where each table is used (AST scan of `src/`)")
    rows = [{"table": t["table"], "file": c["file"], "function": c["function"]}
            for t in reg["tables"] for c in t["consumers"]]
    _df(rows)
    st.markdown("##### Dataset dependency & usage graph")
    st.graphviz_chart(A["dependency_graph"]["dot"])


def _p_provenance(A: dict[str, Any]) -> None:
    reg = A["dataset_registry"]
    ids = [m["dataset_id"] for m in reg["manifest"]]
    ds = st.selectbox("Dataset", ids, key="lab_prov_ds")
    m = next(x for x in reg["manifest"] if x["dataset_id"] == ds)
    st.markdown(f"##### {m['title']}")
    left, right = st.columns(2)
    with left, st.container(border=True):
        for k in ("provider", "version", "url", "download_date", "licence", "geography", "reference_year",
                  "file_path", "file_count", "total_size_bytes", "sha256_checksum", "identification_confidence"):
            st.markdown(f"**{k}:** {m[k]}")
    with right, st.container(border=True):
        for k in ("functional_unit", "system_boundary", "lcia_method", "data_type", "intended_use", "limitations"):
            st.markdown(f"**{k}:** {m[k]}")
    st.markdown("**Why selected:** " + m["selection_rationale"]["verified_intended_use"])
    st.markdown(f"**Alternatives considered:** {m['selection_rationale']['alternatives_considered']}")
    st.markdown("**Derived tables:** " + (", ".join(m["derived_tables"]) or "none (PDF reference extracted by pdf_extraction.py)"))
    used_by = sorted({k for k, v in MODEL_REGISTRY.items() for t in reg["tables"]
                      if t["table"] in m["derived_tables"] and v["dataset_file"].name == f"{t['table']}.csv"})
    st.markdown("**ML tasks supported directly:** " + (", ".join(used_by) or
                                                       "none directly (feeds deterministic LCA engine)"))
    st.markdown("##### Cross-dataset comparability (never merged blindly)")
    _df(A["lineage"]["compatibility_matrix"])


def _p_lineage(A: dict[str, Any]) -> None:
    flows = A["lineage"]["flows"]
    tbl = st.selectbox("Output table", list(flows), key="lab_lin_tbl")
    steps = flows[tbl]
    _df(steps, ["step", "operation", "rows_before", "rows_after", "join", "cardinality", "note", "code"])
    chart = alt.Chart(pd.DataFrame(steps).dropna(subset=["rows_after"])).mark_bar(color="#0f766e").encode(
        x=alt.X("step:O", title="Step"), y=alt.Y("rows_after:Q", title="Rows after step"),
        tooltip=["operation", "rows_before", "rows_after"])
    st.altair_chart(chart.properties(height=200), alt="Rows remaining after each integration step.")
    st.markdown("##### Integration decisions")
    _df(A["lineage"]["integration_decisions"])
    st.caption("Join type is read from the code (dictionary lookups = inner joins). The pipeline does not "
               "write unmatched-record logs; the unmatched counts above are recomputed by this audit.")


def _p_cleaning(A: dict[str, Any]) -> None:
    ops = A["cleaning_log"]
    stage = st.pills("Stage", sorted({o["stage"] for o in ops}), selection_mode="multi", key="lab_clean_stage")
    show = [o for o in ops if not stage or o["stage"] in stage]
    _df(show, ["id", "stage", "operation", "affected", "result"])
    for o in show:
        with st.expander(f"{o['id']} · {o['operation']}"):
            for k, lab in (("original", "Original condition"), ("method", "Applied method"), ("reason", "Why"),
                           ("affected", "Records/features affected"), ("result", "Result after"),
                           ("risks", "Risks"), ("alternatives", "Alternatives"), ("code", "Code")):
                st.markdown(f"**{lab}:** {o[k]}")
    rep = PROJECT_ROOT / "reports" / "data_quality_report.md"
    if rep.exists():
        with st.expander("Source-level data-quality findings (reports/data_quality_report.md)"):
            st.markdown(rep.read_text(encoding="utf-8"))


def _p_eda(A: dict[str, Any]) -> None:
    tk = _task_select("lab_eda_task")
    e = A["eda"][tk]
    st.caption(f"N = {e['n']} · target `{e['target']}` ({e['target_unit']})")
    h = e["target_hist"]
    hist = pd.DataFrame({"bin": [f"{a:.2f}" for a in h["edges"][:-1]], "count": h["counts"]})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Target distribution**")
        st.altair_chart(alt.Chart(hist).mark_bar(color="#0f766e").encode(x=alt.X("bin:N", sort=None, title=e["target_unit"]),
                                                                          y="count:Q"),
                        alt="Histogram of the target variable.")
        sk = e["target_skew"]
        st.caption(f"Skew = {sk:+.2f}. " + ("Right-skewed: absolute-error metrics and robust scaling are appropriate; "
                                            "a few high-emission products dominate errors." if sk > 1 else
                                            "Roughly symmetric."))
    with c2:
        st.markdown("**Feature-target association (Spearman, numeric)**")
        corr = pd.DataFrame(list(e["target_correlations"].items()), columns=["feature", "rho"]).head(12)
        st.altair_chart(alt.Chart(corr).mark_bar().encode(
            y=alt.Y("feature:N", sort="-x", title=None), x=alt.X("rho:Q", scale=alt.Scale(domain=[-1, 1])),
            color=alt.condition("datum.rho > 0", alt.value("#dc2626"), alt.value("#0f766e")),
            tooltip=["feature", alt.Tooltip("rho:Q", format="+.3f")]),
            alt="Bar chart of Spearman correlation between each numeric feature and the target.")
        st.caption("Association only; correlated features share credit and nothing here implies causality.")
    st.markdown("**Numeric features** (missing values, outliers by 1.5×IQR, skew)")
    _df(e["numeric_features"])
    if e["missing_features"]:
        st.warning(f"Features with missing values: {e['missing_features']}")
    else:
        st.success("No missing values in any feature of this task - imputers are inactive on this dataset.")
    st.markdown("**Collinear numeric pairs (|rho| > 0.9)** - confounding / unstable importance risk")
    if e["collinear_pairs"]:
        _df(e["collinear_pairs"])
    else:
        st.caption("none")
    st.markdown("**Class balance and target by category**")
    for c, levels in list(e["categorical"].items())[:4]:
        with st.expander(f"{c}"):
            _df(levels)
    st.markdown(f"**Geography:** {e['geography']} · **Reference years:** {e['reference_year']}")
    st.caption(e["class_balance_note"])
    st.info("Train vs inference distribution comparison for a concrete scenario is on the Prediction inspector page.")


def _p_features(A: dict[str, Any]) -> None:
    tk = _task_select("lab_feat_task")
    f = A["feature_registry"][tk]
    st.markdown(f"**Target:** `{f['target']}` ({f['target_unit']}) · **label type:** {f['label_type']}")
    st.markdown(f"**Construction:** {f['label_construction']}")
    st.markdown(f"**Limitations:** {f['target_limitations']}")
    _kind_note(f["source_type"])
    risk = st.pills("Leakage / bias risk", ["low", "medium"], selection_mode="multi", key="lab_feat_risk")
    rows = [r for r in f["features"] if not risk or any(r["leakage_or_bias_risk"].startswith(x) for x in risk)]
    _df(rows, ["feature", "dtype", "description", "origin", "transformation", "note", "available_at_inference",
               "leakage_or_bias_risk", "expected_relationship"])
    st.caption("Original inclusion rationale and prior expected relationships were never recorded; the table "
               "shows observed relationships instead.")


def _p_models(A: dict[str, Any]) -> None:
    models = A["model_registry"]
    rows = [{"model": m["label"], "champion": m["champion"], "N": m["n_observations"], "source": m["source_type"],
             "baseline MAE": m["baseline"]["oof_mae"], "champion MAE": m["champion_diagnostics"]["oof_mae"],
             "vs baseline": f"{m['improvement_vs_baseline_mae']:.0%}", "readiness": LEVEL_LABEL[A["readiness"][k]["level"]]}
            for k, m in models.items()]
    _df(rows)
    tk = _task_select("lab_model_task")
    m = models[tk]
    st.markdown(f"**Problem:** {m['problem']}")
    st.markdown(f"**ML vs deterministic:** {m['why_ml_vs_deterministic']}")
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown(f"**Champion:** `{m['champion']}` → `{m['estimator_class']}`")
        st.markdown(f"**Selection rule:** {m['selection_rule']}")
        st.markdown(f"**Seed:** {m['seed']} · **Training duration:** {m['training_duration']} · "
                    f"**Experiment version:** {m['experiment_version']}")
        st.json(m["fitted_hyperparameters"], expanded=False)
    with c2, st.container(border=True):
        b = m["best_by_metric"]
        st.markdown("**Is the most accurate model the champion?**")
        st.markdown("\n".join(f"- {k.replace('_', ' ')}: `{v}`" for k, v in b.items()))
        if not m["champion_is_lowest_mae"] or len(set(b.values())) > 1:
            st.caption("Different candidates win different criteria; the champion is a documented trade-off, "
                       "not simply the most accurate model.")
    cand = pd.DataFrame(m["candidates"])
    _df(cand.to_dict("records"), ["model_name", "is_selected_champion", "fit_diagnosis", "mae", "rmse", "r2",
                                  "train_r2_mean", "r2_generalization_gap", "normalized_mae_gap"])
    with st.expander("Audit answers for this model (acceptance questions 1-14)"):
        sp = A["split_audit"][tk]
        fr = A["feature_registry"][tk]
        risks = [r for r in A["risk_register"] if tk in r["models"] and r["status"] == "open"]
        ans = [
            ("1 Data origin", f"{m['dataset']} ({m['source_type']}) → page 2/3"),
            ("2 Why these datasets", "Intended use from manifest; alternatives " + NOT_RECORDED + " → page 3"),
            ("3 Exact records/features", f"{sp['n_rows']} rows × {sp['n_features']} features → pages 7, 14"),
            ("4 How combined", "page 4 lineage"), ("5 Cleaning/transforms", "page 5"),
            ("6 Why features/target", f"label: {fr['label_type']}; inclusion rationale {NOT_RECORDED} → page 7"),
            ("7 Why this algorithm", m["selection_rule"] + " (candidate pool rationale " + NOT_RECORDED + ")"),
            ("8 Training/optimisation", f"seed {m['seed']}; nested search → page 10"),
            ("9 Validation/testing", sp["split_method"] + " → page 11"),
            ("10 Biases/limits", f"{len(risks)} open risks → page 12"),
            ("11 How it predicts", "Preprocessor → estimator; inspect on page 14"),
            ("12 Reproducible?", "Tracker record + checksums → page 15 (historical run only partially)"),
            ("13 Code and data behind a result", "page 16 result tracer"),
            ("14 Fix before trusting", "; ".join(A["readiness"][tk]["blockers"][:2])),
        ]
        _df([{"question": q, "answer": a} for q, a in ans])


def _exp_table() -> pd.DataFrame:
    rows = []
    for r in xp.list_experiments():
        m = r["metrics"]
        rows.append({"experiment_id": r["experiment_id"], "kind": r["kind"], "task": r["task_key"],
                     "architecture": r["architecture"], "seed": r["seed"], "oof_mae": m["oof_mae"],
                     "oof_r2": m["oof_r2"], "gap": m["r2_generalization_gap"], "fit": m["fit_diagnosis"],
                     "duration_s": r.get("duration_s", NOT_RECORDED), "created": r["created_at"]})
    return pd.DataFrame(rows)


def _p_training(A: dict[str, Any], summary: dict[str, Any]) -> None:
    st.markdown("#### Experiments (in-memory training; production artifacts are never touched)")
    tk = _task_select("lab_exp_task")
    with st.form("lab_exp_form"):
        arch = st.selectbox("Architecture", list(PARAM_SPECS), key="lab_exp_arch")
        params = render_param_widgets(arch, "lab_exp")
        seed = st.number_input("Random seed", 0, 10_000, 42, key="lab_exp_seed")
        note = st.text_input("Note", key="lab_exp_note")
        go = st.form_submit_button("Run and log experiment", icon=":material/play_arrow:", type="primary")
    if go:
        with st.spinner("Cross-validating..."):
            rec = xp.log_experiment(tk, arch, params, summary, int(seed), note)
        st.success(f"Logged {rec['experiment_id']} - OOF MAE {rec['metrics']['oof_mae']}, "
                   f"R² {rec['metrics']['oof_r2']}, {rec['metrics']['fit_diagnosis']}")
    df = _exp_table()
    if df.empty:
        st.info("No experiments logged yet. Run `dairyeco audit` to register historical champions.")
        return
    sub = df[df["task"] == tk]
    _df(sub.to_dict("records"))
    if len(sub) > 1:
        st.altair_chart(alt.Chart(sub).mark_bar().encode(
            x=alt.X("experiment_id:N", sort=None, title=None), y=alt.Y("oof_mae:Q", title="OOF MAE"),
            color="kind:N", tooltip=["experiment_id", "architecture", "oof_mae", "oof_r2", "fit"]).properties(height=240),
            alt="OOF MAE of every logged experiment for this task versus the reconstructed production champion.")
    st.caption("HIST-* rows are reconstructed from artifacts (training time, duration, code and dependency versions "
               "were not recorded). EXP-* rows are fully recorded.")


def _p_tuning(A: dict[str, Any], summary: dict[str, Any]) -> None:
    tk = _task_select("lab_tune_task")
    m = A["model_registry"][tk]
    st.markdown("**Search method and space used for production selection** (read from `_candidate_regressors`)")
    rows = [{"candidate": k, "method": v["method"], "space": v["space"],
             "combinations": v.get("n_combinations", "-"), "inner fits / outer fold": v.get("inner_fits_per_outer_fold", "-")}
            for k, v in m["search_spaces"].items()]
    _df(rows)
    st.caption("Search is exhaustive over small hand-chosen grids, nested inside each outer training fold. "
               "Why these grids were chosen: " + NOT_RECORDED + ".")
    st.markdown("##### Validation curve - sweep one hyperparameter")
    with st.form("lab_sweep"):
        arch = st.selectbox("Architecture", list(PARAM_SPECS), key="lab_sweep_arch")
        base = render_param_widgets(arch, "lab_sweep_base")
        param = st.selectbox("Parameter to sweep", list(PARAM_SPECS[arch]), key="lab_sweep_param")
        lo, hi, _, _ = PARAM_SPECS[arch][param]
        pts = st.slider("Points", 3, 6, 4, key="lab_sweep_pts")
        go = st.form_submit_button("Run sweep (each run is logged)", icon=":material/stacked_line_chart:")
    if go:
        vals = np.linspace(lo, hi, pts)
        if param in INT_PARAMS:
            vals = sorted({round(v) for v in vals})
        res = []
        with st.spinner("Running sweep..."):
            for v in vals:
                p = {**base, param: v}
                rec = xp.log_experiment(tk, arch, p, summary, note=f"sweep {param}")
                res.append({param: float(v), "OOF MAE": rec["metrics"]["oof_mae"],
                            "Train MAE": rec["metrics"]["train_mae_mean"]})
        long = pd.DataFrame(res).melt(param, var_name="series", value_name="MAE")
        st.altair_chart(alt.Chart(long).mark_line(point=True).encode(x=f"{param}:Q", y="MAE:Q", color="series:N"),
                        alt="Train versus out-of-fold MAE as one hyperparameter varies.")
        st.caption("A widening train/OOF gap signals overfitting; both high signals underfitting.")


def _p_validation(A: dict[str, Any], summary: dict[str, Any]) -> None:
    tk = _task_select("lab_val_task")
    sp = A["split_audit"][tk]
    m = A["model_registry"][tk]
    st.markdown(f"**Split:** {sp['split_method']} · seed {sp['seed']} · ≈{sp['validation_fraction']:.1%} validation per fold "
                "· no separate test set")
    st.altair_chart(alt.Chart(pd.DataFrame(sp["fold_sizes"]).melt("fold", var_name="part", value_name="records")).mark_bar().encode(
        x="fold:O", y="records:Q", color="part:N"), alt="Train and validation record counts for each cross-validation fold.")
    st.markdown("##### Leakage & contamination checks (computed)")
    _df(sp["checks"], ["id", "name", "status", "evidence", "code_ref"])
    cand = pd.DataFrame(m["candidates"])
    st.markdown("##### Baseline vs candidates - train vs out-of-fold")
    long = cand.melt(["model_name"], ["train_r2_mean", "r2"], var_name="split", value_name="R²")
    st.altair_chart(alt.Chart(long).mark_bar().encode(x=alt.X("model_name:N", title=None, sort=None),
                                                      y="R²:Q", color="split:N", xOffset="split:N"),
                    alt="Train versus out-of-fold R-squared for each candidate model.")
    d = m["champion_diagnostics"]
    st.markdown(f"Champion residuals: median |err| {d['median_abs_error']}, p90 |err| {d['p90_abs_error']}, "
                f"mean bias {d['mean_bias_error']}; fold MAE {d['cv_mae_mean_pm_std']}; "
                f"diagnosis **{d['fit_diagnosis']}**.")
    c1, c2 = st.columns(2)
    if c1.button("Compute learning curve", key=f"lab_lc_{tk}", icon=":material/show_chart:"):
        with st.spinner("Learning curve..."):
            lc = xp.learning_curve_data(tk, summary)
        st.altair_chart(alt.Chart(lc.melt("train_size", var_name="series", value_name="MAE")).mark_line(point=True).encode(
            x="train_size:Q", y="MAE:Q", color="series:N"), alt="Learning curve of train and validation MAE.")
        st.caption("Uses the champion's final hyperparameters (tuned on all rows): diagnostic only.")
    if c2.button("Run noise-robustness test", key=f"lab_nz_{tk}", icon=":material/graphic_eq:"):
        with st.spinner("Perturbing inputs..."):
            nz = xp.noise_sensitivity(tk, summary)
        st.altair_chart(alt.Chart(nz).mark_line(point=True).encode(x="noise_sigma_x_std:Q", y="oof_mae:Q"),
                        alt="OOF MAE as Gaussian noise is added to numeric validation inputs.")


def _p_bias(A: dict[str, Any]) -> None:
    risks = A["risk_register"]
    f1, f2 = st.columns(2)
    sev = f1.pills("Severity", ["high", "medium", "low"], selection_mode="multi", key="lab_risk_sev")
    sta = f2.pills("Status", ["open", "accepted", "mitigated", "resolved"], selection_mode="multi", key="lab_risk_sta")
    show = [r for r in risks if (not sev or r["severity"] in sev) and (not sta or r["status"] in sta)]
    show.sort(key=lambda r: SEV_ORDER[r["severity"]])
    _df(show, ["id", "category", "title", "severity", "status", "models"])
    for r in show:
        with st.expander(f"{r['id']} · {r['severity'].upper()} · {r['status']} · {r['title']}"):
            for k in ("evidence", "impact", "mitigation"):
                st.markdown(f"**{k.title()}:** {r[k]}")
    st.markdown("##### Model readiness")
    tk = _task_select("lab_ready_task")
    rd = A["readiness"][tk]
    st.badge(LEVEL_LABEL[rd["level"]], color=LEVEL_COLOR[rd["level"]], icon=":material/shield:")
    _df(rd["gates"])
    st.caption("Rule: " + rd["rule"] + ". High accuracy alone never raises the level.")


def _p_explain(A: dict[str, Any], ctx: dict[str, Any], pipes: dict[str, Any]) -> None:
    tk = _task_select("lab_exp_x_task")
    m = A["model_registry"][tk]
    st.markdown("##### Global importance - held-out OOF permutation (MAE increase when a feature is shuffled)")
    imp = pd.DataFrame(m["feature_importances"]).head(12)
    st.altair_chart(alt.Chart(imp).mark_bar(color="#0f766e").encode(
        y=alt.Y("feature:N", sort="-x", title=None), x="oof_mean_mae_importance:Q",
        tooltip=["feature", "oof_mean_mae_importance", "oof_std_mae_importance"]),
        alt="Bar chart of out-of-fold permutation importance.")
    st.caption("Limits: with correlated features importance is shared arbitrarily; it describes the model, "
               "not the real world, and is not causal.")
    st.markdown("##### Local explanation")
    pipe = pipes[tk]
    df = load_task_frame(tk)
    feats = get_task_summary_dict(ctx["summary"], tk)["feature_columns"]
    if MODEL_REGISTRY[tk]["supports_live_scenario"]:
        x = build_surrogate_feature_df(ctx["product"], ctx["proposed"], ctx["assumptions"], ctx["prop_comp"].environmental.effective_reuse_trips)
        st.caption("Input: the active executive scenario (proposed packaging).")
    else:
        idx = st.number_input("Record index", 0, len(df) - 1, 0, key="lab_exp_x_idx")
        x = df[feats].iloc[[int(idx)]]
    exp_v, pred, attr = compute_local_feature_attributions(pipe, df[feats], x)
    st.markdown(f"Base value E[f(X)] = **{exp_v:.3f}** → prediction **{pred:.3f}** {MODEL_REGISTRY[tk]['target_unit']}")
    top = attr.head(10)
    st.altair_chart(alt.Chart(top).mark_bar().encode(
        y=alt.Y("feature:N", sort=None, title=None), x="attribution:Q",
        color=alt.condition("datum.attribution > 0", alt.value("#dc2626"), alt.value("#0f766e")),
        tooltip=["feature", "input_value", "attribution"]), alt="Local additive attribution per feature.")
    st.caption("Method: one-feature-at-a-time replacement against a background sample, rescaled to sum to "
               "f(x) − E[f]. SHAP-like but not true Shapley values (`shap` is not installed); interactions are ignored.")
    p90 = m["champion_diagnostics"]["p90_abs_error"]
    st.markdown(f"**Uncertainty (empirical):** 90% of out-of-fold absolute errors were ≤ {p90} "
                f"{MODEL_REGISTRY[tk]['target_unit']}. This is not a calibrated prediction interval.")


def _trace_to_source(tk: str, row: pd.Series) -> dict[str, Any]:
    if tk == "task1_agribalyse_gwp":
        return {"entity": row.get("name_en"), "id": row.get("product_id"), "AGB code": row.get("code_agb"),
                "source workbook": "data/raw/agribalyse_3_2/AGRIBALYSE3.2_Tableur produits alimentaires_PublieAOUT25.xlsx",
                "sheets": "Synthese + Detail etape"}
    if tk.startswith("task2"):
        return {"entity": row.get("cheese_name"), "id": row.get("pdo_cheese_id"),
                "INAO spec": row.get("inao_specification_url"), "source folder": "data/raw/pdo_cheese_lca/"}
    return {"entity": row.get("product_id"), "id": row.get("scenario_row_id"),
            "source": "data/synthetic/simulated_packaging_scenarios.csv (generated)"}


def _p_inspector(A: dict[str, Any], ctx: dict[str, Any], pipes: dict[str, Any]) -> None:
    tk = _task_select("lab_pi_task")
    meta = MODEL_REGISTRY[tk]
    pipe = pipes[tk]
    df = load_task_frame(tk)
    feats = get_task_summary_dict(ctx["summary"], tk)["feature_columns"]
    expected, exp_label, source_row = None, "", None
    if meta["supports_live_scenario"]:
        comp = ctx["prop_comp"]
        x = build_surrogate_feature_df(ctx["product"], ctx["proposed"], ctx["assumptions"], comp.environmental.effective_reuse_trips)
        expected = (comp.environmental.packaging_system_total_gwp_kgco2e if tk == "task3a_surrogate_gwp"
                    else comp.economic.total_packaging_attributable_cost_per_fu)
        exp_label = "Deterministic engine (exact)"
        st.caption(f"Live scenario: {ctx['product'].name_en} → {ctx['proposed'].name}")
    else:
        idx = st.number_input("Dataset record", 0, len(df) - 1, 0, key="lab_pi_idx")
        source_row = df.iloc[int(idx)]
        x = df[feats].iloc[[int(idx)]]
        expected, exp_label = float(source_row[meta["target_col"]]), "Published/calculated reference label"
    pred = float(pipe.predict(x)[0])
    c1, c2, c3 = st.columns(3)
    c1.metric("ML prediction", f"{pred:,.3f}", border=True)
    c2.metric(exp_label, f"{expected:,.3f}", border=True)
    c3.metric("Residual", f"{pred - expected:+,.3f}", border=True)
    st.badge("ML-generated", color="violet", icon=":material/psychology:")
    st.caption(f"Unit: {meta['target_unit']} · 90% of OOF errors ≤ "
               f"{A['model_registry'][tk]['champion_diagnostics']['p90_abs_error']} (empirical).")
    st.markdown("##### Input vector vs training distribution")
    rows = []
    for f in feats:
        v = x[f].iloc[0]
        if pd.api.types.is_numeric_dtype(df[f]):
            lo, hi = float(df[f].min()), float(df[f].max())
            ok = lo <= float(v) <= hi
            rows.append({"feature": f, "value": v, "training range": f"{lo:.4g} – {hi:.4g}",
                         "in range": "yes" if ok else "OUT OF RANGE"})
        else:
            rows.append({"feature": f, "value": v, "training range": f"{df[f].nunique()} levels",
                         "in range": "yes" if v in set(df[f]) else "UNSEEN LEVEL"})
    _df(rows)
    if any(r["in range"] not in ("yes",) for r in rows):
        st.warning("Some inputs lie outside the training data: the prediction extrapolates.", icon=":material/warning:")
    prep = pipe.named_steps["prep"].transform(x)
    st.markdown(f"**Preprocessing:** {len(feats)} raw features → {prep.shape[1]} encoded columns "
                f"(median/RobustScaler + one-hot, fitted on the full training set for the deployed artifact).")
    if source_row is not None:
        st.markdown("##### Trace to source")
        st.json(_trace_to_source(tk, source_row))
    else:
        st.info("Executive results never use this surrogate: they come from the deterministic engines. "
                "This page shows only how closely the ML copy tracks them.", icon=":material/calculate:")


def _p_repro(A: dict[str, Any], summary: dict[str, Any]) -> None:
    m = A["audit_manifest"]
    st.markdown("**Code fingerprint** (no git commit exists): `" + m["code_fingerprint"]["aggregate_sha256"] + "`")
    st.json(m["environment"], expanded=False)
    st.markdown("##### Artifact integrity (recorded vs current SHA-256)")
    rows = []
    for k, mm in A["model_registry"].items():
        cur = sha256_file(PROJECT_ROOT / mm["artifact"]["path"])
        rows.append({"model": k, "artifact": mm["artifact"]["path"], "bytes": mm["artifact"]["bytes"],
                     "trained (mtime)": mm["artifact"]["mtime_utc"], "unchanged since audit": cur == mm["artifact"]["sha256"]})
    _df(rows)
    st.markdown("##### Dataset checksums")
    _df([{"table": t["table"], "file": t["file"], "sha256": t["sha256"],
          "unchanged": sha256_file(PROJECT_ROOT / t["file"]) == t["sha256"]} for t in A["dataset_registry"]["tables"]])
    st.markdown("##### Reproduce an experiment")
    df = _exp_table()
    if df.empty:
        return
    eid = st.selectbox("Experiment", df["experiment_id"].tolist(), key="lab_repro_id")
    rec = next(r for r in xp.list_experiments() if r["experiment_id"] == eid)
    with st.expander("Full record"):
        st.json(rec, expanded=False)
    if st.button("Re-run and compare", key="lab_repro_go", icon=":material/replay:"):
        with st.spinner("Re-running..."):
            res = xp.reproduce(eid, summary)
        if res["status"] == "reproduced":
            st.success(f"Reproduced: max metric difference {res['max_abs_metric_diff']:.2e}; dataset unchanged="
                       f"{res['dataset_unchanged']}; code unchanged={res['code_unchanged']}")
        else:
            st.warning(json.dumps(res, default=str)[:600])
    st.code("uv run dairyeco audit   # rebuild audit records\nuv run dairyeco train   # WARNING: retrains and overwrites model artifacts",
            language="bash")


def _trace_dot(A: dict[str, Any]) -> str:
    lines = ["digraph T {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];']
    for t in A["dataset_registry"]["tables"]:
        for s in t["raw_sources"]:
            lines.append(f'"{s}" [label="Raw\\n{s}", fillcolor="#e0f2fe"];')
            lines.append(f'"{s}" -> "{t["built_by"]["symbol"] or t["table"]}";')
        b = t["built_by"]["symbol"] or "pdf_extraction"
        lines.append(f'"{b}" [label="Clean/Integrate\\n{b}", fillcolor="#fef9c3"];')
        lines.append(f'"{b}" -> "tbl_{t["table"]}"; "tbl_{t["table"]}" [label="Table\\n{t["table"]}", fillcolor="#fef3c7"];')
    for tk, meta in MODEL_REGISTRY.items():
        lines.append(f'"tbl_{meta["dataset_file"].stem}" -> "feat_{tk}" -> "train_{tk}" -> "art_{tk}" -> "pred_{tk}" -> "ui";')
        lines.append(f'"feat_{tk}" [label="Features\\n{tk}", fillcolor="#fae8ff"]; "train_{tk}" [label="Training\\n_evaluate_candidates", fillcolor="#dcfce7"];')
        lines.append(f'"art_{tk}" [label="Artifact\\n{meta["artifact_file"]}", fillcolor="#bbf7d0"]; "pred_{tk}" [label="Prediction\\n{tk}", fillcolor="#ddd6fe"];')
    lines.append('"tbl_packaging_impact_factors" -> "lca.engine::evaluate_environmental_lca" -> "economics.engine::evaluate_economics" -> "ui";')
    lines.append('"tbl_agribalyse_dairy_products" -> "lca.engine::evaluate_environmental_lca";')
    lines.append('"ui" [label="Streamlit\\n(executive = deterministic, dev = ML)", fillcolor="#ede9fe"];')
    lines.append("}")
    return "\n".join(lines)


def _p_trace(A: dict[str, Any], ctx: dict[str, Any]) -> None:
    st.markdown("##### End-to-end dependency graph")
    st.graphviz_chart(_trace_dot(A))
    st.markdown("##### Trace a displayed result")
    comp = ctx["prop_comp"]
    which = st.selectbox("Displayed metric (active scenario)",
                         ["Packaging system CO₂e (executive)", "Packaging cost per FU (executive)", "Payback period (executive)"],
                         key="lab_trace_metric")
    man = {m["dataset_id"]: m for m in A["dataset_registry"]["manifest"]}
    if which.startswith("Packaging system CO"):
        st.markdown(f"**Value:** {comp.environmental.packaging_system_total_gwp_kgco2e:,.2f} kg CO₂e/FU — computed by "
                    "`lca/engine.py::evaluate_environmental_lca` (deterministic, not ML).")
        recs = comp.environmental.provenance_records
        rows = []
        for p in recs:
            m = man.get(p.source_dataset_id)
            rows.append({"source dataset": p.source_dataset_id, "record": p.source_record_id, "type": str(p.source_type),
                         "geography": p.geography, "year": p.reference_year,
                         "raw file(s)": m["file_path"] if m else "reference CSV / proxy (see packaging_impact_factors)",
                         "dataset sha256": (m["sha256_checksum"][:16] + "…") if m else "-"})
        _df(rows)
        st.caption("Each factor row used in the calculation, with its source file and checksum. "
                   "'proxy' rows are assumptions, not published values.")
        st.code(symbol_source("src/dairyeco/lca/engine.py", "evaluate_environmental_lca", 40), language="python")
    elif which.startswith("Packaging cost"):
        st.markdown(f"**Value:** ${comp.economic.total_packaging_attributable_cost_per_fu:,.2f}/FU — "
                    "`economics/engine.py::evaluate_economics` using material prices from the preset BOM "
                    "(`optimization/pareto.py::build_preset_package_configurations`) = assumed scenario inputs.")
        st.code(symbol_source("src/dairyeco/economics/engine.py", "evaluate_economics", 40), language="python")
    else:
        st.markdown(f"**Status:** {comp.payback_status} — `economics/engine.py::calculate_payback_schedule`; "
                    "inputs (CAPEX, price premium, horizon) are user assumptions.")
        st.code(symbol_source("src/dairyeco/economics/engine.py", "calculate_payback_schedule", 50), language="python")
    st.markdown("##### Decision register")
    dec = A["decision_register"]
    _df(dec, ["id", "what", "why", "file", "symbol", "symbol_verified", "tests", "alternatives", "limitation"])
    pick = st.selectbox("Show implementing code", [f"{d['id']} · {d['symbol']}" for d in dec], key="lab_dec_pick")
    d = next(x for x in dec if x["id"] == pick.split(" · ")[0])
    st.code(symbol_source(d["file"], d["symbol"], 70) or "(source not found)", language="python")
    st.caption("Source text is read from the repository file now; `symbol_verified` is an AST check.")


def _p_issues(A: dict[str, Any]) -> None:
    st.markdown("#### What must be fixed before trusting each model")
    tk = _task_select("lab_issue_task")
    rd = A["readiness"][tk]
    st.badge(LEVEL_LABEL[rd["level"]], color=LEVEL_COLOR[rd["level"]], icon=":material/shield:")
    for b in rd["blockers"]:
        st.markdown(f"- {b}")
    fail = [c for c in A["split_audit"][tk]["checks"] if c["status"] in ("fail", "warn")]
    st.markdown("**Validation findings:** " + "; ".join(f"{c['id']} ({c['status']})" for c in fail))
    open_r = sorted([r for r in A["risk_register"] if tk in r["models"] and r["status"] == "open"],
                    key=lambda r: SEV_ORDER[r["severity"]])
    st.markdown("##### Open risks and recommended actions (highest severity first)")
    _df([{"id": r["id"], "severity": r["severity"], "issue": r["title"], "recommendation": r["mitigation"]}
         for r in open_r])
    st.markdown("##### Gaps where history was not recorded")
    st.markdown("- Training timestamps, duration, dependency versions, code version: not recorded at training time "
                "(project not under git).\n- Reasons for feature inclusion and candidate-pool/grid choices: not recorded.\n"
                "- Alternative datasets considered: not recorded.\n- External validation on real plant data: none exists.")
    st.markdown("##### Cross-model priorities")
    st.markdown("1. Hold out an untouched test set (R01/R02).\n2. Trace every packaging factor literal to a page/table or "
                "recompute from raw data (R11).\n3. Collect Central-Asian data before any local claim (R06).\n"
                "4. Add drift/checksum monitoring (R16).\n5. `git init` and use the experiment tracker for every run (R17).")


# ----------------------------------------------------------------------------- entry
def render_ml_lab(product, baseline_cfg, proposed_cfg, assumptions, base_comp, prop_comp) -> None:
    """Render the 17-section ML Engineering Lab & Audit Center."""
    manifest = AUDIT_DIR / "audit_manifest.json"
    A = _records(manifest.stat().st_mtime if manifest.exists() else 0.0)
    st.markdown("### :material/biotech: ML Engineering Lab & Model Audit Center")
    if A is None:
        st.warning("Audit records have not been built yet.", icon=":material/info:")
        if st.button("Build audit records now (~1 min)", type="primary", key="lab_build_first"):
            with st.spinner("Reading raw files, profiling data, auditing splits and models..."):
                build_audit()
            st.cache_data.clear()
            st.rerun()
        st.caption("Or run `uv run dairyeco audit` in a terminal.")
        return
    summary, pipes = load_ml_artifacts()
    ctx = {"summary": summary, "product": product, "baseline": baseline_cfg, "proposed": proposed_cfg,
           "assumptions": assumptions, "prop_comp": prop_comp, "base_comp": base_comp}
    nav, body = st.columns([1, 4], gap="medium")
    with nav:
        page = st.radio("Section", PAGES, key="lab_page", label_visibility="collapsed")
    with body:
        st.markdown(f"#### {page}")
        if page == PAGES[0]:
            _p_overview(A)
        elif page == PAGES[1]:
            _p_registry(A)
        elif page == PAGES[2]:
            _p_provenance(A)
        elif page == PAGES[3]:
            _p_lineage(A)
        elif page == PAGES[4]:
            _p_cleaning(A)
        elif page == PAGES[5]:
            _p_eda(A)
        elif page == PAGES[6]:
            _p_features(A)
        elif page == PAGES[7]:
            _p_models(A)
        elif page == PAGES[8]:
            _p_training(A, summary)
        elif page == PAGES[9]:
            _p_tuning(A, summary)
        elif page == PAGES[10]:
            _p_validation(A, summary)
        elif page == PAGES[11]:
            _p_bias(A)
        elif page == PAGES[12]:
            _p_explain(A, ctx, pipes)
        elif page == PAGES[13]:
            _p_inspector(A, ctx, pipes)
        elif page == PAGES[14]:
            _p_repro(A, summary)
        elif page == PAGES[15]:
            _p_trace(A, ctx)
        else:
            _p_issues(A)

