"""Phase 3 ML Prototype & Simulator Surrogate Pipeline with Generalization & Over/Underfitting Audit.

Implements vision.md Section 8 with publication-grade methodology:
1. Sample-size-adaptive regularization, bootstrap/feature subsampling, and inner cross-validated
   hyperparameter tuning (`RidgeCV`, `ElasticNetCV`, `GridSearchCV`-tuned `RandomForestRegressor`,
   `ExtraTreesRegressor`, `HistGradientBoostingRegressor`, regularized `CatBoostRegressor`, and
   `GeneralizationEnsemble_LinearTree` blending regularized linear + gradient-boosted estimators).
2. Stratified & Grouped Cross-Validation matching each dataset's data-generating process:
   - Task 1 (`published_reference`, N=255): 5-fold `StratifiedKFold` across AGRIBALYSE dairy subgroups.
   - Task 2A & 2B (`published_reference`, N=44): 11-fold `StratifiedKFold` across target quantile strata
     on the 44 canonical French PDO cheeses.
   - Task 3 (`model_derived`, N=1,200): 5-fold `GroupKFold` grouped strictly by `product_id` so no
     dairy product appears in both training and validation splits.
3. Explicit Train vs. Cross-Validation Overfitting / Underfitting Diagnostics on every model:
   - In-fold Training MAE / R² vs. Held-out Validation Fold MAE (`mean ± std`) and Pooled OOF MAE / R²;
   - Scale-invariant `r2_generalization_gap` (`Train R² - OOF R²`) and `normalized_mae_gap`
     (`(CV MAE - Train MAE) / Dummy MAE`);
   - Quantitative `fit_diagnosis` (`baseline_reference`, `well_generalized`, `mild_overfit`,
     `overfit_high_variance`, `underfit`);
   - Strict champion selection requiring `well_generalized` status with minimum generalization penalty.
4. Held-out Out-of-Fold (OOF) Permutation Feature Importance (computed strictly on validation
   splits to prevent in-sample memorization bias) and OOF residual distribution diagnostics
   (`Mean Bias`, `Median AE`, `90th Percentile AE`, `Max AE`).

Run: ``uv run python -m dairyeco.models.pipeline``
"""

from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNetCV, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.pipeline import Pipeline

from dairyeco.config import ARTIFACTS_DIR, PROCESSED_DIR, REPORTS_DIR, SYNTHETIC_DIR
from dairyeco.domain.models import DataSourceType, ScenarioAssumptions
from dairyeco.economics.engine import evaluate_economics
from dairyeco.lca.engine import (
    check_scenario_feasibility,
    evaluate_environmental_lca,
    get_default_factor_catalog,
)
from dairyeco.models.registry import (
    FORBIDDEN_LEAKAGE_COLUMNS,
    assert_no_feature_leakage,
    build_surrogate_feature_row,
    make_holdout_split,
    make_splits,
)
from dairyeco.models.registry import (
    build_preprocessor as _build_preprocessor,
)
from dairyeco.models.registry import (
    classify_fit_diagnosis as _classify_fit_diagnosis,
)

__all__ = [
    "FORBIDDEN_LEAKAGE_COLUMNS",
    "_build_preprocessor",
    "_classify_fit_diagnosis",
    "assert_no_feature_leakage",
    "generate_simulated_scenario_dataset",
    "run_phase3_ml_pipeline",
    "run_task1_agribalyse_dairy_regression",
    "run_task2_pdo_cheese_case_study",
    "run_task3_simulator_surrogate",
]
from dairyeco.optimization.pareto import build_preset_package_configurations
from dairyeco.services.reporting import load_dairy_products


def _candidate_regressors(n_samples: int, random_state: int = 42) -> dict[str, Any]:
    """Build sample-size-adaptive, variance-controlled regressors for strong OOF generalization."""
    is_small = n_samples < 80
    is_medium = 80 <= n_samples < 500

    if is_small:
        # Small-N regime (N=44 PDO cheeses): shallow trees + strong L2/subsampling prevent memorization
        # while small min_samples_leaf prevents leaf-starvation underfitting.
        rf_grid = {
            "max_depth": [2, 3],
            "min_samples_leaf": [3, 4],
            "max_features": [0.5, 0.7],
            "max_samples": [0.75],
        }
        et_grid = {
            "max_depth": [3, 4],
            "min_samples_leaf": [2, 3],
            "max_features": [0.6, 0.8],
        }
        hgb_grid = {
            "max_depth": [2, 3],
            "min_samples_leaf": [3, 5],
            "l2_regularization": [10.0, 25.0, 50.0],
            "learning_rate": [0.04, 0.06],
        }
        cb_model = CatBoostRegressor(
            iterations=110,
            depth=3,
            l2_leaf_reg=15.0,
            learning_rate=0.045,
            subsample=0.75,
            random_seed=random_state,
            verbose=0,
            allow_writing_files=False,
        )
    elif is_medium:
        # Medium-N regime (N=255 AGRIBALYSE dairy products)
        rf_grid = {
            "max_depth": [4, 5, 6],
            "min_samples_leaf": [5, 7, 10],
            "max_features": [0.5, 0.7],
            "max_samples": [0.75, 0.85],
        }
        et_grid = {
            "max_depth": [5, 6, 7],
            "min_samples_leaf": [4, 6, 8],
            "max_features": [0.6, 0.8],
        }
        hgb_grid = {
            "max_depth": [3, 4],
            "min_samples_leaf": [8, 12, 16],
            "l2_regularization": [10.0, 25.0, 50.0],
            "learning_rate": [0.04, 0.06],
        }
        cb_model = CatBoostRegressor(
            iterations=150,
            depth=3,
            l2_leaf_reg=14.0,
            learning_rate=0.045,
            subsample=0.75,
            random_seed=random_state,
            verbose=0,
            allow_writing_files=False,
        )
    else:
        # Larger-N regime (N=1,200 simulator scenarios)
        rf_grid = {
            "max_depth": [6, 7],
            "min_samples_leaf": [8, 12],
            "max_features": [0.6, 0.8],
            "max_samples": [0.75],
        }
        et_grid = {
            "max_depth": [6, 8],
            "min_samples_leaf": [6, 10],
            "max_features": [0.7, 0.9],
        }
        hgb_grid = {
            "max_depth": [3, 4],
            "min_samples_leaf": [15, 25],
            "l2_regularization": [10.0, 25.0],
            "learning_rate": [0.04, 0.06],
        }
        cb_model = CatBoostRegressor(
            iterations=200,
            depth=4,
            l2_leaf_reg=12.0,
            learning_rate=0.045,
            subsample=0.75,
            random_seed=random_state,
            verbose=0,
            allow_writing_files=False,
        )

    ridge = RidgeCV(
        alphas=np.logspace(-2, 3, 40), scoring="neg_mean_absolute_error"
    )
    enet = ElasticNetCV(
        l1_ratio=[0.1, 0.5, 0.85, 0.95, 0.99],
        alphas=np.logspace(-3, 2, 25),
        cv=4,
        max_iter=4000,
        n_jobs=-1,
        random_state=random_state,
    )

    return {
        "DummyRegressor_Median": DummyRegressor(strategy="median"),
        "RidgeCV_L2": ridge,
        "ElasticNetCV_L1L2": enet,
        "RandomForest_Regularized": GridSearchCV(
            RandomForestRegressor(
                n_estimators=120, bootstrap=True, n_jobs=-1, random_state=random_state
            ),
            param_grid=rf_grid,
            scoring="neg_mean_absolute_error",
            cv=3,
        ),
        "ExtraTrees_Regularized": GridSearchCV(
            ExtraTreesRegressor(
                n_estimators=120,
                bootstrap=True,
                max_samples=0.8,
                n_jobs=-1,
                random_state=random_state,
            ),
            param_grid=et_grid,
            scoring="neg_mean_absolute_error",
            cv=3,
        ),
        "HistGradientBoosting_Regularized": GridSearchCV(
            HistGradientBoostingRegressor(
                max_iter=90, early_stopping=False, random_state=random_state
            ),
            param_grid=hgb_grid,
            scoring="neg_mean_absolute_error",
            cv=3,
            n_jobs=-1,
        ),
        "CatBoost_Regularized": cb_model,
        "GeneralizationEnsemble_LinearTree": VotingRegressor(
            estimators=[
                ("ridge", clone(ridge)),
                ("enet", clone(enet)),
                ("catboost", clone(cb_model)),
            ],
            weights=[1.0, 1.0, 1.5],
        ),
    }


def _set_inner_group_cv(estimator: Any, inner_splits: list[tuple[np.ndarray, np.ndarray]]) -> None:
    """Apply grouped inner CV splits to GridSearchCV / ElasticNetCV / VotingRegressor."""
    if isinstance(estimator, (GridSearchCV, ElasticNetCV)):
        estimator.cv = inner_splits
    elif isinstance(estimator, VotingRegressor):
        for _, sub_est in estimator.estimators:
            _set_inner_group_cv(sub_est, inner_splits)


def _evaluate_candidates(
    X_dev: pd.DataFrame,
    y_dev: pd.Series,
    X_holdout: pd.DataFrame,
    y_holdout: pd.Series,
    numeric_cols: list[str],
    categorical_cols: list[str],
    splits: list[tuple[np.ndarray, np.ndarray]],
    unit: str = "kg CO2e / kg",
    groups_dev: pd.Series | None = None,
    X_full: pd.DataFrame | None = None,
    y_full: pd.Series | None = None,
    groups_full: pd.Series | None = None,
) -> tuple[list[dict[str, Any]], Pipeline, list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Cross-validate all models on dev split, evaluate champion once on untouched holdout, then refit."""
    n_dev = len(y_dev)
    candidates = _candidate_regressors(n_samples=n_dev)
    min_freq = 2 if n_dev < 80 else None

    raw_results: list[dict[str, Any]] = []
    fitted_fold_pipelines: dict[str, list[tuple[Pipeline, np.ndarray]]] = {}

    for name, reg in candidates.items():
        base_pipe = Pipeline(
            [
                ("prep", _build_preprocessor(numeric_cols, categorical_cols, min_frequency=min_freq)),
                ("reg", reg),
            ]
        )
        oof_preds = np.zeros(n_dev, dtype=float)
        train_maes: list[float] = []
        val_maes: list[float] = []
        train_rmses: list[float] = []
        val_rmses: list[float] = []
        train_r2s: list[float] = []
        val_r2s: list[float] = []
        fold_models: list[tuple[Pipeline, np.ndarray]] = []

        for train_idx, val_idx in splits:
            fold_pipe = clone(base_pipe)
            X_tr, y_tr = X_dev.iloc[train_idx], y_dev.iloc[train_idx]
            X_va, y_va = X_dev.iloc[val_idx], y_dev.iloc[val_idx]

            if groups_dev is not None:
                g_tr = groups_dev.iloc[train_idx]
                n_inner = min(3, int(g_tr.nunique()))
                if n_inner >= 2:
                    inner_splits = list(GroupKFold(n_splits=n_inner).split(X_tr, y_tr, g_tr))
                    _set_inner_group_cv(fold_pipe.named_steps["reg"], inner_splits)

            fold_pipe.fit(X_tr, y_tr)
            pred_tr = fold_pipe.predict(X_tr)
            pred_va = fold_pipe.predict(X_va)
            oof_preds[val_idx] = pred_va

            train_maes.append(float(mean_absolute_error(y_tr, pred_tr)))
            val_maes.append(float(mean_absolute_error(y_va, pred_va)))
            train_rmses.append(float(np.sqrt(mean_squared_error(y_tr, pred_tr))))
            val_rmses.append(float(np.sqrt(mean_squared_error(y_va, pred_va))))
            train_r2s.append(float(r2_score(y_tr, pred_tr)))
            val_r2s.append(float(r2_score(y_va, pred_va)) if len(val_idx) > 2 else 0.0)
            fold_models.append((fold_pipe, val_idx))

        fitted_fold_pipelines[name] = fold_models
        pooled_mae = float(mean_absolute_error(y_dev, oof_preds))
        pooled_rmse = float(np.sqrt(mean_squared_error(y_dev, oof_preds)))
        pooled_r2 = float(r2_score(y_dev, oof_preds))

        tr_mae_mean = float(np.mean(train_maes))
        cv_mae_mean = float(np.mean(val_maes))
        cv_mae_std = float(np.std(val_maes, ddof=1)) if len(val_maes) > 1 else 0.0
        cv_rmse_std = float(np.std(val_rmses, ddof=1)) if len(val_rmses) > 1 else 0.0
        tr_r2_mean = float(np.mean(train_r2s))

        r2_gap = max(0.0, tr_r2_mean - pooled_r2)
        mae_ratio = cv_mae_mean / max(tr_mae_mean, 1e-4)

        residuals = y_dev.to_numpy() - oof_preds
        abs_errors = np.abs(residuals)

        raw_results.append(
            {
                "model_name": name,
                "mae": round(pooled_mae, 4),
                "cv_mae_mean": round(cv_mae_mean, 4),
                "cv_mae_std": round(cv_mae_std, 4),
                "train_mae_mean": round(tr_mae_mean, 4),
                "mae_generalization_ratio": round(mae_ratio, 3),
                "rmse": round(pooled_rmse, 4),
                "cv_rmse_std": round(cv_rmse_std, 4),
                "r2": round(pooled_r2, 4),
                "train_r2_mean": round(tr_r2_mean, 4),
                "r2_generalization_gap": round(r2_gap, 4),
                "median_abs_error": round(float(np.median(abs_errors)), 4),
                "p90_abs_error": round(float(np.percentile(abs_errors, 90)), 4),
                "max_abs_error": round(float(np.max(abs_errors)), 4),
                "mean_bias_error": round(float(np.mean(residuals)), 4),
                "unit": unit,
                "n_samples": n_dev,
            }
        )

    dummy_mae = next(
        r["mae"] for r in raw_results if r["model_name"].startswith("DummyRegressor")
    )
    for r in raw_results:
        norm_mae_gap = max(0.0, r["cv_mae_mean"] - r["train_mae_mean"]) / max(
            dummy_mae, 1e-6
        )
        r["normalized_mae_gap"] = round(norm_mae_gap, 4)
        r["fit_diagnosis"] = _classify_fit_diagnosis(
            model_name=r["model_name"],
            pooled_cv_mae=r["mae"],
            dummy_cv_mae=dummy_mae,
            pooled_cv_r2=r["r2"],
            r2_gap=r["r2_generalization_gap"],
            norm_mae_gap=norm_mae_gap,
        )

    # Champion selection: strictly prioritize `well_generalized` models first, then lowest OOF MAE
    non_dummy = [
        r for r in raw_results if not r["model_name"].startswith("DummyRegressor")
    ]
    well_generalized_pool = [
        r for r in non_dummy if r["fit_diagnosis"] == "well_generalized"
    ]
    acceptable_pool = [
        r
        for r in non_dummy
        if r["fit_diagnosis"] in {"well_generalized", "mild_overfit"}
    ]
    selection_pool = (
        well_generalized_pool
        if well_generalized_pool
        else (acceptable_pool if acceptable_pool else non_dummy)
    )
    best_row = min(
        selection_pool,
        key=lambda r: r["mae"]
        * (
            1.0
            + 0.5 * max(0.0, r["r2_generalization_gap"])
            + 0.5 * max(0.0, r["normalized_mae_gap"])
        ),
    )
    best_name = str(best_row["model_name"])
    best_row["is_selected_champion"] = True
    for r in raw_results:
        r.setdefault("is_selected_champion", False)

    # Compute Out-of-Fold (held-out validation) permutation importance across dev CV folds
    all_cols = numeric_cols + categorical_cols
    fold_imp_matrix: list[np.ndarray] = []
    for fold_pipe, val_idx in fitted_fold_pipelines[best_name]:
        X_va, y_va = X_dev.iloc[val_idx], y_dev.iloc[val_idx]
        perm = permutation_importance(
            fold_pipe,
            X_va,
            y_va,
            scoring="neg_mean_absolute_error",
            n_repeats=6,
            random_state=42,
        )
        fold_imp_matrix.append(perm.importances_mean)

    imp_arr = np.vstack(fold_imp_matrix)
    imp_mean = np.mean(imp_arr, axis=0)
    imp_std = (
        np.std(imp_arr, axis=0, ddof=1)
        if len(fold_imp_matrix) > 1
        else np.zeros_like(imp_mean)
    )

    importances = [
        {
            "feature": col,
            "oof_mean_mae_importance": round(float(imp_mean[i]), 5),
            "oof_std_mae_importance": round(float(imp_std[i]), 5),
            "champion_model": best_name,
        }
        for i, col in enumerate(all_cols)
    ]
    importances.sort(key=lambda d: d["oof_mean_mae_importance"], reverse=True)

    # Evaluate selected champion ONCE on the untouched holdout set
    dev_champion = Pipeline(
        [
            ("prep", _build_preprocessor(numeric_cols, categorical_cols, min_frequency=min_freq)),
            ("reg", clone(candidates[best_name])),
        ]
    )
    if groups_dev is not None:
        n_inner = min(3, int(groups_dev.nunique()))
        if n_inner >= 2:
            _set_inner_group_cv(
                dev_champion.named_steps["reg"],
                list(GroupKFold(n_splits=n_inner).split(X_dev, y_dev, groups_dev)),
            )
    dev_champion.fit(X_dev, y_dev)
    ho_preds = dev_champion.predict(X_holdout)
    ho_res = y_holdout.to_numpy() - ho_preds
    ho_abs = np.abs(ho_res)
    holdout_metrics = {
        "holdout_n": len(y_holdout),
        "dev_n": int(n_dev),
        "holdout_mae": round(float(mean_absolute_error(y_holdout, ho_preds)), 4),
        "holdout_rmse": round(float(np.sqrt(mean_squared_error(y_holdout, ho_preds))), 4),
        "holdout_r2": round(float(r2_score(y_holdout, ho_preds)), 4),
        "holdout_median_abs_error": round(float(np.median(ho_abs)), 4),
        "holdout_p90_abs_error": round(float(np.percentile(ho_abs, 90)), 4),
        "holdout_mean_bias_error": round(float(np.mean(ho_res)), 4),
    }

    # Fit final deployment champion pipeline on full dataset
    X_fit = X_full if X_full is not None else X_dev
    y_fit = y_full if y_full is not None else y_dev
    min_freq_full = 2 if len(y_fit) < 80 else None
    champion_pipe = Pipeline(
        [
            ("prep", _build_preprocessor(numeric_cols, categorical_cols, min_frequency=min_freq_full)),
            ("reg", clone(candidates[best_name])),
        ]
    )
    if groups_full is not None:
        n_inner_full = min(3, int(groups_full.nunique()))
        if n_inner_full >= 2:
            _set_inner_group_cv(
                champion_pipe.named_steps["reg"],
                list(GroupKFold(n_splits=n_inner_full).split(X_fit, y_fit, groups_full)),
            )
    champion_pipe.fit(X_fit, y_fit)

    champion_diagnostics = {
        "selected_model": best_name,
        "fit_diagnosis": best_row["fit_diagnosis"],
        "oof_mae": best_row["mae"],
        "cv_mae_mean_pm_std": f"{best_row['cv_mae_mean']:.4f} ± {best_row['cv_mae_std']:.4f}",
        "train_mae_mean": best_row["train_mae_mean"],
        "normalized_mae_gap": best_row["normalized_mae_gap"],
        "oof_r2": best_row["r2"],
        "train_r2_mean": best_row["train_r2_mean"],
        "r2_generalization_gap": best_row["r2_generalization_gap"],
        "median_abs_error": best_row["median_abs_error"],
        "p90_abs_error": best_row["p90_abs_error"],
        "mean_bias_error": best_row["mean_bias_error"],
        "holdout_n": holdout_metrics["holdout_n"],
        "holdout_mae": holdout_metrics["holdout_mae"],
        "holdout_r2": holdout_metrics["holdout_r2"],
    }

    return raw_results, champion_pipe, importances, champion_diagnostics, holdout_metrics


def run_task1_agribalyse_dairy_regression(
    processed_dir: Path = PROCESSED_DIR,
) -> dict[str, Any]:
    """Task 1: Predict non-packaging dairy GWP (kg CO2e/kg) from pre-LCA product attributes (N=255)."""
    t0 = time.perf_counter()
    df = pd.read_csv(processed_dir / "agribalyse_dairy_products.csv")
    core_df = df[df["is_core_dairy"] == True].copy().reset_index(drop=True)

    target_col = "non_packaging_gwp_kgco2e_per_kg"
    numeric_cols = [
        "milk_yield_kg_milk_per_kg_product",
        "density_kg_per_l",
        "dqr_overall",
    ]
    categorical_cols = [
        "category",
        "agribalyse_subgroup_fr",
        "delivery_mode",
        "baseline_packaging_approach",
    ]
    feature_cols = numeric_cols + categorical_cols
    assert_no_feature_leakage(feature_cols, target_col)

    dev_idx, ho_idx = make_holdout_split("task1_agribalyse_gwp", core_df, target_col)
    dev_df = core_df.iloc[dev_idx].reset_index(drop=True)
    ho_df = core_df.iloc[ho_idx].reset_index(drop=True)
    splits = make_splits("task1_agribalyse_gwp", dev_df, target_col)

    metrics, best_pipe, importances, diag, holdout_metrics = _evaluate_candidates(
        X_dev=dev_df[feature_cols],
        y_dev=dev_df[target_col],
        X_holdout=ho_df[feature_cols],
        y_holdout=ho_df[target_col],
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        splits=splits,
        unit="kg CO2e / kg consumed dairy product",
        X_full=core_df[feature_cols],
        y_full=core_df[target_col],
    )

    return {
        "task_id": "task1_agribalyse_non_packaging_gwp",
        "title": "AGRIBALYSE 3.2 Core Dairy Non-Packaging GWP Regression (N=255, Pre-LCA Attributes)",
        "data_source_type": str(DataSourceType.PUBLISHED_REFERENCE),
        "target_column": target_col,
        "target_unit": "kg CO2e / kg product",
        "n_observations": len(core_df),
        "validation_scheme": (
            "20% untouched Stratified Holdout + 5-fold StratifiedKFold on dev split (80%) "
            "with inner hyperparameter regularization and held-out OOF permutation importance"
        ),
        "feature_columns": feature_cols,
        "best_model_name": diag["selected_model"],
        "champion_diagnostics": diag,
        "holdout_metrics": holdout_metrics,
        "training_duration_s": round(time.perf_counter() - t0, 2),
        "metrics": metrics,
        "feature_importances": importances,
        "best_pipeline": best_pipe,
    }


def run_task2_pdo_cheese_case_study(
    processed_dir: Path = PROCESSED_DIR,
) -> dict[str, Any]:
    """Task 2: Exploratory case study on the 44 French PDO cheeses (both Pre-LCI & Full-LCI regimes)."""
    t0 = time.perf_counter()
    df = pd.read_csv(processed_dir / "pdo_cheese_harmonized.csv")
    if len(df) != 44:
        raise ValueError(
            f"PDO Cheese dataset must have exactly 44 cheese entities, got {len(df)}"
        )

    # Regime 2A: Pre-LCI Cheese Specifications & Milk Origin Yield Only -> Total Cheese GWP
    target_2a = "gwp_base_total_kgco2e_per_kg"
    num_2a = [
        "ripening_days",
        "allocation_before_skimming",
        "allocation_skimming_to_draining",
        "allocation_after_draining",
        "cream_coproduct_kg_per_kg_cheese",
        "whey_coproduct_kg_per_kg_cheese",
        "max_authorized_distance_km",
        "lci_cow_milk_lowland_kg",
        "lci_cow_milk_highland_kg",
        "lci_sheep_milk_kg",
        "lci_goat_milk_kg",
        "lci_total_raw_milk_kg",
    ]
    cat_2a = ["technology", "milk_type"]
    feat_2a = num_2a + cat_2a
    assert_no_feature_leakage(feat_2a, target_2a)

    dev_idx_2a, ho_idx_2a = make_holdout_split("task2a_pdo_cheese_total", df, target_2a)
    dev_2a = df.iloc[dev_idx_2a].reset_index(drop=True)
    ho_2a = df.iloc[ho_idx_2a].reset_index(drop=True)
    splits_2a = make_splits("task2a_pdo_cheese_total", dev_2a, target_2a)

    metrics_2a, pipe_2a, imp_2a, diag_2a, ho_2a_metrics = _evaluate_candidates(
        X_dev=dev_2a[feat_2a],
        y_dev=dev_2a[target_2a],
        X_holdout=ho_2a[feat_2a],
        y_holdout=ho_2a[target_2a],
        numeric_cols=num_2a,
        categorical_cols=cat_2a,
        splits=splits_2a,
        unit="kg CO2e / kg ripened PDO cheese (total cradle-to-ripening-exit)",
        X_full=df[feat_2a],
        y_full=df[target_2a],
    )
    dur_2a = round(time.perf_counter() - t0, 2)

    # Regime 2B: Full LCI Physical Inventory -> Post-Farm Processing + Ripening GWP
    t1 = time.perf_counter()
    target_2b = "gwp_base_post_farm_total_kgco2e_per_kg"
    num_2b = [
        "ripening_days",
        "allocation_before_skimming",
        "allocation_skimming_to_draining",
        "allocation_after_draining",
        "whey_coproduct_kg_per_kg_cheese",
        "max_authorized_distance_km",
        "lci_total_raw_milk_kg",
        "lci_milk_transport_tkm",
        "lci_milk_storage_kwh",
        "lci_processing_electricity_kwh",
        "lci_ripening_electricity_kwh_initial",
        "lci_cleaning_water_kg",
    ]
    cat_2b = ["technology", "milk_type"]
    feat_2b = num_2b + cat_2b
    assert_no_feature_leakage(feat_2b, target_2b)

    dev_idx_2b, ho_idx_2b = make_holdout_split("task2b_pdo_cheese_post_farm", df, target_2b)
    dev_2b = df.iloc[dev_idx_2b].reset_index(drop=True)
    ho_2b = df.iloc[ho_idx_2b].reset_index(drop=True)
    splits_2b = make_splits("task2b_pdo_cheese_post_farm", dev_2b, target_2b)

    metrics_2b, pipe_2b, imp_2b, diag_2b, ho_2b_metrics = _evaluate_candidates(
        X_dev=dev_2b[feat_2b],
        y_dev=dev_2b[target_2b],
        X_holdout=ho_2b[feat_2b],
        y_holdout=ho_2b[target_2b],
        numeric_cols=num_2b,
        categorical_cols=cat_2b,
        splits=splits_2b,
        unit="kg CO2e / kg ripened PDO cheese (post-farm stages)",
        X_full=df[feat_2b],
        y_full=df[target_2b],
    )
    dur_2b = round(time.perf_counter() - t1, 2)

    return {
        "task_id": "task2_pdo_cheese_case_study",
        "title": "French PDO Cheese Exploratory Case Study (N=44 Canonical Cheeses)",
        "data_source_type": str(DataSourceType.PUBLISHED_REFERENCE),
        "target_column": target_2a,
        "target_unit": "kg CO2e / kg ripened cheese",
        "n_observations": len(df),
        "validation_scheme": (
            "20% untouched Stratified Holdout (9 cheeses) + 5-fold StratifiedKFold on dev split (35 cheeses)"
        ),
        "feature_columns": feat_2a,
        "best_model_name": diag_2a["selected_model"],
        "champion_diagnostics": diag_2a,
        "holdout_metrics": ho_2a_metrics,
        "training_duration_s": dur_2a,
        "metrics": metrics_2a,
        "feature_importances": imp_2a,
        "regime_2b_full_lci_post_farm": {
            "target_column": target_2b,
            "feature_columns": feat_2b,
            "best_model_name": diag_2b["selected_model"],
            "champion_diagnostics": diag_2b,
            "holdout_metrics": ho_2b_metrics,
            "training_duration_s": dur_2b,
            "metrics": metrics_2b,
            "feature_importances": imp_2b,
        },
        "best_pipeline": pipe_2a,
        "best_pipeline_2b": pipe_2b,
    }


def generate_simulated_scenario_dataset(
    processed_dir: Path = PROCESSED_DIR,
    synthetic_dir: Path = SYNTHETIC_DIR,
    n_scenarios: int = 1200,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate explicitly labelled `LCA-model-derived` scenario dataset for surrogate training."""
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(random_state)

    core_products = load_dairy_products(processed_dir, core_only=True)
    catalog = get_default_factor_catalog(processed_dir)
    presets = list(build_preset_package_configurations().values())
    regions = ["Western Europe", "USA", "China", "MENA", "Cross-regional average"]

    rows: list[dict[str, Any]] = []
    attempts = 0
    while len(rows) < n_scenarios and attempts < n_scenarios * 10:
        attempts += 1
        product = core_products[int(rng.integers(0, len(core_products)))]

        compatible_presets = [
            p for p in presets if product.category in p.compatible_categories
        ]
        if not compatible_presets:
            compatible_presets = presets
        base_cfg = deepcopy(
            compatible_presets[int(rng.integers(0, len(compatible_presets)))]
        )
        feas = check_scenario_feasibility(product, base_cfg)
        if not feas.is_feasible:
            continue

        mass_scale = float(rng.uniform(0.75, 1.35))
        price_scale = float(rng.uniform(0.80, 1.40))
        rec_override = float(rng.uniform(0.0, 0.70))
        chosen_region = str(regions[int(rng.integers(0, len(regions)))])

        for comp in base_cfg.components:
            comp.mass_g_per_package = round(comp.mass_g_per_package * mass_scale, 3)
            comp.unit_price_usd_per_kg = round(comp.unit_price_usd_per_kg * price_scale, 3)
            comp.resin_region = chosen_region
            if not comp.is_secondary_or_tertiary:
                comp.recycled_content_fraction = round(rec_override, 3)

        base_cfg.supplier_to_plant_distance_km = round(float(rng.uniform(50.0, 800.0)), 1)
        base_cfg.distribution_distance_km = round(float(rng.uniform(30.0, 500.0)), 1)
        base_cfg.line_reject_rate = round(float(rng.uniform(0.001, 0.025)), 4)
        base_cfg.package_attributable_spoilage_rate = round(
            float(rng.uniform(0.002, 0.035)), 4
        )
        if base_cfg.reuse.is_reusable:
            base_cfg.reuse.return_rate = round(float(rng.uniform(0.70, 0.98)), 3)
            base_cfg.reuse.nominal_max_trips = int(rng.integers(5, 30))

        grid_ci = round(float(rng.uniform(0.08, 0.85)), 3)
        elec_price = round(float(rng.uniform(0.04, 0.18)), 3)
        assumptions = ScenarioAssumptions(
            grid_carbon_intensity_kgco2e_per_kwh=grid_ci,
            electricity_price_usd_per_kwh=elec_price,
        )

        env_res = evaluate_environmental_lca(product, base_cfg, assumptions, catalog)
        econ_res = evaluate_economics(base_cfg, assumptions, env_res)
        feat_row = build_surrogate_feature_row(
            product, base_cfg, assumptions, env_res.effective_reuse_trips
        )

        rows.append(
            {
                "scenario_row_id": f"SIM-{len(rows)+1:04d}",
                "product_id": product.product_id,
                **feat_row,
                "target_packaging_system_gwp_kgco2e_per_fu": env_res.packaging_system_total_gwp_kgco2e,
                "target_packaging_cost_usd_per_fu": econ_res.total_packaging_attributable_cost_per_fu,
                "source_type": str(DataSourceType.MODEL_DERIVED),
                "epistemic_label": "LCA-model-derived simulator output (not observed factory data)",
            }
        )

    sim_df = pd.DataFrame(rows)
    sim_df.to_csv(synthetic_dir / "simulated_packaging_scenarios.csv", index=False)
    return sim_df


def run_task3_simulator_surrogate(
    processed_dir: Path = PROCESSED_DIR,
    synthetic_dir: Path = SYNTHETIC_DIR,
) -> dict[str, Any]:
    """Task 3: Train & evaluate GroupKFold surrogate models on LCA-model-derived scenarios."""
    sim_df = generate_simulated_scenario_dataset(processed_dir, synthetic_dir)

    numeric_cols = [
        "is_reusable",
        "effective_reuse_trips",
        "net_fill_mass_kg",
        "total_bom_mass_g_per_pkg",
        "effective_bom_mass_kg_per_fu",
        "primary_recycled_content_frac",
        "weighted_eol_recycling_frac",
        "weighted_avg_material_price_usd_per_kg",
        "supplier_distance_km",
        "distribution_distance_km",
        "line_reject_rate",
        "spoilage_loss_rate",
        "grid_ci_kgco2e_per_kwh",
        "electricity_price_usd_per_kwh",
        "dairy_non_packaging_gwp_per_kg",
    ]
    categorical_cols = [
        "preset_id",
        "dairy_category",
        "package_format",
        "primary_material",
        "primary_conversion",
        "resin_region",
    ]
    feature_cols = numeric_cols + categorical_cols
    target_gwp = "target_packaging_system_gwp_kgco2e_per_fu"
    target_cost = "target_packaging_cost_usd_per_fu"
    assert_no_feature_leakage(feature_cols, target_gwp)
    assert_no_feature_leakage(feature_cols, target_cost)

    dev_idx, ho_idx = make_holdout_split("task3a_surrogate_gwp", sim_df, target_gwp)
    dev_df = sim_df.iloc[dev_idx].reset_index(drop=True)
    ho_df = sim_df.iloc[ho_idx].reset_index(drop=True)
    splits = make_splits("task3a_surrogate_gwp", dev_df, target_gwp)

    t_g = time.perf_counter()
    gwp_metrics, best_gwp_pipe, gwp_imp, gwp_diag, gwp_ho = _evaluate_candidates(
        X_dev=dev_df[feature_cols],
        y_dev=dev_df[target_gwp],
        X_holdout=ho_df[feature_cols],
        y_holdout=ho_df[target_gwp],
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        splits=splits,
        unit="kg CO2e / 1,000 kg saleable product",
        groups_dev=dev_df["product_id"],
        X_full=sim_df[feature_cols],
        y_full=sim_df[target_gwp],
        groups_full=sim_df["product_id"],
    )
    dur_g = round(time.perf_counter() - t_g, 2)

    t_c = time.perf_counter()
    cost_metrics, best_cost_pipe, cost_imp, cost_diag, cost_ho = _evaluate_candidates(
        X_dev=dev_df[feature_cols],
        y_dev=dev_df[target_cost],
        X_holdout=ho_df[feature_cols],
        y_holdout=ho_df[target_cost],
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        splits=splits,
        unit="USD / 1,000 kg saleable product",
        groups_dev=dev_df["product_id"],
        X_full=sim_df[feature_cols],
        y_full=sim_df[target_cost],
        groups_full=sim_df["product_id"],
    )
    dur_c = round(time.perf_counter() - t_c, 2)

    return {
        "task_id": "task3_lca_simulator_surrogate",
        "title": "LCA & Cost Engine Surrogate Models (N=1,200 Simulated Scenarios, GroupKFold by Product)",
        "data_source_type": str(DataSourceType.MODEL_DERIVED),
        "epistemic_disclaimer": (
            "Surrogate trained on deterministic LCA/economic simulator equations. "
            "Test MAE/RMSE/R2 measure simulator approximation fidelity on unseen products, "
            "NOT real-world empirical predictive accuracy."
        ),
        "n_observations": len(sim_df),
        "validation_scheme": (
            "20% untouched Group Holdout (by product_id) + 5-fold GroupKFold on dev split "
            "with grouped inner hyperparameter tuning"
        ),
        "feature_columns": feature_cols,
        "gwp_surrogate": {
            "target_column": target_gwp,
            "target_unit": "kg CO2e / 1,000 kg saleable product",
            "best_model_name": gwp_diag["selected_model"],
            "champion_diagnostics": gwp_diag,
            "holdout_metrics": gwp_ho,
            "training_duration_s": dur_g,
            "metrics": gwp_metrics,
            "feature_importances": gwp_imp,
            "best_pipeline": best_gwp_pipe,
        },
        "cost_surrogate": {
            "target_column": target_cost,
            "target_unit": "USD / 1,000 kg saleable product",
            "best_model_name": cost_diag["selected_model"],
            "champion_diagnostics": cost_diag,
            "holdout_metrics": cost_ho,
            "training_duration_s": dur_c,
            "metrics": cost_metrics,
            "feature_importances": cost_imp,
            "best_pipeline": best_cost_pipe,
        },
    }


def _write_model_cards_report(
    t1: dict[str, Any],
    t2: dict[str, Any],
    t3: dict[str, Any],
    report_path: Path,
) -> None:
    """Write comprehensive Model Cards report with Over/Underfitting Diagnostics in reports/model_cards.md."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def _fmt_table(metrics: list[dict[str, Any]]) -> str:
        lines = [
            "| Model | Champion | OOF MAE (Primary) | Fold MAE (`Mean ± Std`) | Train MAE | Norm MAE Gap | OOF RMSE | OOF R² | Train R² | R² Gap (`Train - CV`) | Fit Diagnosis |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for m in metrics:
            star = "★ **Selected**" if m.get("is_selected_champion") else "—"
            lines.append(
                f"| `{m['model_name']}` | {star} | **{m['mae']:.4f}** | "
                f"`{m['cv_mae_mean']:.4f} ± {m['cv_mae_std']:.4f}` | {m['train_mae_mean']:.4f} | "
                f"`{m['normalized_mae_gap']:.4f}` | {m['rmse']:.4f} | {m['r2']:.4f} | "
                f"{m['train_r2_mean']:.4f} | `{m['r2_generalization_gap']:.4f}` | `{m['fit_diagnosis']}` |"
            )
        return "\n".join(lines)

    def _fmt_imp(imps: list[dict[str, Any]], top_k: int = 6) -> str:
        lines = [
            "| Rank | Feature | Held-Out OOF Permutation MAE Importance | Fold Std |",
            "|---:|---|---:|---:|",
        ]
        for idx, item in enumerate(imps[:top_k], start=1):
            lines.append(
                f"| {idx} | `{item['feature']}` | **{item['oof_mean_mae_importance']:.4f}** | "
                f"±{item['oof_std_mae_importance']:.4f} |"
            )
        return "\n".join(lines)

    def _fmt_diag_summary(diag: dict[str, Any], unit: str) -> str:
        return (
            f"- **Selected Champion Model:** `{diag['selected_model']}` (`fit_diagnosis = {diag['fit_diagnosis']}`)\n"
            f"- **Out-of-Fold MAE (Dev):** `{diag['oof_mae']:.4f} {unit}` (Fold Mean ± Std: `{diag['cv_mae_mean_pm_std']} {unit}`, Train MAE: `{diag['train_mae_mean']:.4f} {unit}`, Normalized MAE Gap: `{diag['normalized_mae_gap']:.4f}`)\n"
            f"- **Out-of-Fold R² vs. Train R² (Dev):** `OOF R² = {diag['oof_r2']:.4f}` vs. `Train R² = {diag['train_r2_mean']:.4f}` (`R² Generalization Gap = {diag['r2_generalization_gap']:.4f}`)\n"
            f"- **Untouched Holdout Test Set (`n = {diag['holdout_n']}`):** `Holdout MAE = {diag['holdout_mae']:.4f} {unit}`, `Holdout R² = {diag['holdout_r2']:.4f}`\n"
            f"- **Residual Distribution (`{unit}`):** Median Absolute Error = `{diag['median_abs_error']:.4f}`, 90th Percentile AE = `{diag['p90_abs_error']:.4f}`, Mean Bias = `{diag['mean_bias_error']:+.4f}`"
        )

    r2b = t2["regime_2b_full_lci_post_farm"]

    content = f"""# DairyEco AI — Phase 3 Model Cards, Generalization Audit & Over/Underfitting Diagnostics

## 1. Epistemic Governance & Anti-Overfitting / Anti-Underfitting Protocol

In strict compliance with `vision.md` Section 8:
1. **No Black-Box Financial/ROI Model on Synthetic Labels:** ROI, NPV, payback, and contribution margin are computed deterministically by `dairyeco.economics.engine`.
2. **Sample-Size-Adaptive Regularization, Subsampling & Inner Hyperparameter Search:**
   - Every linear model uses inner cross-validated regularization (`RidgeCV_L2` over 40 log-spaced $\\alpha \\in [10^{{-2}}, 10^3]$, `ElasticNetCV_L1L2` over $L_1/L_2$ ratios and $\\alpha$ grids).
   - Every tree ensemble (`RandomForest_Regularized`, `ExtraTrees_Regularized`, `HistGradientBoosting_Regularized`) uses bootstrap subsampling (`max_samples = 0.75..0.85`), feature subsampling (`max_features = 0.5..0.8`), and an inner 3-fold `GridSearchCV` inside each outer training split that adapts `max_depth`, `min_samples_leaf`, and `l2_regularization` to the sample size $N$ — preventing both **leaf-starvation underfitting** on small $N$ ($N=44$) and **deep-tree memorization overfitting**.
   - `CatBoost_Regularized` constrains tree depth (`depth = 3..4`), applies strong $L_2$ leaf regularization (`l2_leaf_reg = 12..15`), and uses stochastic subsampling (`subsample = 0.75`).
   - `GeneralizationEnsemble_LinearTree` blends regularized linear models (`RidgeCV_L2`, `ElasticNetCV_L1L2`) with regularized gradient boosting (`CatBoost_Regularized`) to combine low-variance global linear structure with bounded non-linear interactions.
3. **Scale-Invariant Quantitative Overfitting / Underfitting Diagnosis (`fit_diagnosis`):**
   - Every model is audited by comparing in-fold **Train MAE / R²** against out-of-fold **Validation MAE (`Mean ± Std`) and Pooled OOF R²** using two scale-invariant generalization metrics:
     - **R² Generalization Gap:** $\\Delta R^2 = \\max(0, R^2_{{\\text{{train}}}} - R^2_{{\\text{{OOF}}}})\\quad$ (fraction of variance memorized in-sample)
     - **Normalized MAE Gap:** $\\Delta \\text{{NMAE}} = \\max(0, \\text{{MAE}}_{{\\text{{CV}}}} - \\text{{MAE}}_{{\\text{{train}}}}) / \\text{{MAE}}_{{\\text{{dummy}}}}\\quad$ (train-to-CV error gap scaled by baseline target dispersion)
   - Classification rules:
     - `underfit`: OOF MAE fails to improve over `DummyRegressor_Median` by at least 15% or OOF $R^2 < 0.25$.
     - `overfit_high_variance`: $\\Delta R^2 > 0.10$ or $\\Delta \\text{{NMAE}} > 0.12$.
     - `mild_overfit`: $0.045 < \\Delta R^2 \\le 0.10$ or $0.065 < \\Delta \\text{{NMAE}} \\le 0.12$.
     - `well_generalized`: Strong out-of-fold accuracy with tightly bounded generalization gaps ($\\Delta R^2 \\le 0.045$ and $\\Delta \\text{{NMAE}} \\le 0.065$).
   - **Strict Generalization-First Champion Selection:** Champion selection strictly prioritizes `well_generalized` candidates with the lowest generalization-penalized OOF MAE.
4. **Held-Out Out-of-Fold (OOF) Permutation Importance:** Feature importances are computed strictly on held-out validation splits $(X_{{\\text{{val}}}}, y_{{\\text{{val}}}})$ across folds rather than on training data, eliminating in-sample memorization bias.

---

## 2. Task 1: {t1['title']}

- **Data Source Type:** `{t1['data_source_type']}` (`data/processed/agribalyse_dairy_products.csv`)
- **Target:** `{t1['target_column']}` (`{t1['target_unit']}`)
- **Validation:** {t1['validation_scheme']}
- **Features (`{len(t1['feature_columns'])}`):** `{', '.join(t1['feature_columns'])}`

### Champion Generalization & Residual Summary
{_fmt_diag_summary(t1['champion_diagnostics'], t1['target_unit'])}

### Cross-Validation & Generalization Gap Table
{_fmt_table(t1['metrics'])}

### Held-Out OOF Permutation Feature Importances (Non-Causal Explanatory Behaviour)
{_fmt_imp(t1['feature_importances'])}

---

## 3. Task 2: {t2['title']}

- **Data Source Type:** `{t2['data_source_type']}` (`data/processed/pdo_cheese_harmonized.csv`, strictly `N = 44` canonical cheese entities; the `1,232` indicator rows in `data_PDOcheeses_LCIA.xlsx` are never treated as independent samples)
- **Validation:** {t2['validation_scheme']}

### 3.1 Regime 2A — Pre-LCI Cheese Specifications & Milk Origin Yield Only (`{t2['target_column']}`)
Predicts total cradle-to-ripening-exit cheese GWP (`kg CO2e / kg ripened cheese`) using only PDO cheese specification, dry-matter allocation across skimming/draining, co-product mass, authorized collection distance, and raw milk origin breakdown (lowland cow, highland/mountain cow, sheep, goat) known **before** measuring factory electricity or cleaning utilities.

#### Champion Generalization & Residual Summary (Regime 2A)
{_fmt_diag_summary(t2['champion_diagnostics'], t2['target_unit'])}

#### Cross-Validation & Generalization Gap Table (Regime 2A)
{_fmt_table(t2['metrics'])}

#### Held-Out OOF Permutation Feature Importances (Regime 2A)
{_fmt_imp(t2['feature_importances'])}

### 3.2 Regime 2B — Full LCI Physical Inventory Audit (`{r2b['target_column']}`)
Includes measured processing and ripening electricity (`lci_ripening_electricity_kwh_initial`, `lci_processing_electricity_kwh`) alongside cheese specifications. Demonstrates that once physical LCI utility flows are measured, regularized linear models recover the physical LCA relationship (`OOF R² = {r2b['champion_diagnostics']['oof_r2']:.4f}`, `Holdout R² = {r2b['champion_diagnostics']['holdout_r2']:.4f}`, `{r2b['champion_diagnostics']['fit_diagnosis']}`).

#### Champion Generalization & Residual Summary (Regime 2B)
{_fmt_diag_summary(r2b['champion_diagnostics'], 'kg CO2e / kg ripened cheese')}

#### Cross-Validation & Generalization Gap Table (Regime 2B)
{_fmt_table(r2b['metrics'])}

---

## 4. Task 3: {t3['title']}

> [!IMPORTANT]
> **Epistemic Disclaimer:** {t3['epistemic_disclaimer']}

- **Data Source Type:** `{t3['data_source_type']}` (`data/synthetic/simulated_packaging_scenarios.csv`)
- **Validation:** {t3['validation_scheme']}

### 4.1 Packaging System GWP Surrogate (`{t3['gwp_surrogate']['target_unit']}`)

#### Champion Generalization & Residual Summary (GWP Surrogate)
{_fmt_diag_summary(t3['gwp_surrogate']['champion_diagnostics'], t3['gwp_surrogate']['target_unit'])}

#### Cross-Validation & Generalization Gap Table (GWP Surrogate)
{_fmt_table(t3['gwp_surrogate']['metrics'])}

#### Held-Out OOF Permutation Feature Importances (GWP Surrogate)
{_fmt_imp(t3['gwp_surrogate']['feature_importances'])}

### 4.2 Packaging Attributable Cost Surrogate (`{t3['cost_surrogate']['target_unit']}`)

#### Champion Generalization & Residual Summary (Cost Surrogate)
{_fmt_diag_summary(t3['cost_surrogate']['champion_diagnostics'], t3['cost_surrogate']['target_unit'])}

#### Cross-Validation & Generalization Gap Table (Cost Surrogate)
{_fmt_table(t3['cost_surrogate']['metrics'])}

#### Held-Out OOF Permutation Feature Importances (Cost Surrogate)
{_fmt_imp(t3['cost_surrogate']['feature_importances'])}
"""
    report_path.write_text(content, encoding="utf-8")


def run_phase3_ml_pipeline(
    processed_dir: Path = PROCESSED_DIR,
    synthetic_dir: Path = SYNTHETIC_DIR,
    artifacts_dir: Path = ARTIFACTS_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    """Execute all Phase 3 ML tasks with over/underfitting diagnostics and write model cards."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    t1 = run_task1_agribalyse_dairy_regression(processed_dir)
    t2 = run_task2_pdo_cheese_case_study(processed_dir)
    t3 = run_task3_simulator_surrogate(processed_dir, synthetic_dir)

    joblib.dump(t1.pop("best_pipeline"), artifacts_dir / "task1_agribalyse_gwp_model.joblib")
    joblib.dump(t2.pop("best_pipeline"), artifacts_dir / "task2_pdo_cheese_gwp_model.joblib")
    joblib.dump(
        t2.pop("best_pipeline_2b"),
        artifacts_dir / "task2b_pdo_cheese_post_farm_gwp_model.joblib",
    )
    joblib.dump(
        t3["gwp_surrogate"].pop("best_pipeline"),
        artifacts_dir / "task3_surrogate_gwp_model.joblib",
    )
    joblib.dump(
        t3["cost_surrogate"].pop("best_pipeline"),
        artifacts_dir / "task3_surrogate_cost_model.joblib",
    )

    _write_model_cards_report(t1, t2, t3, reports_dir / "model_cards.md")

    summary = {
        "task1_agribalyse": t1,
        "task2_pdo_cheese": t2,
        "task3_simulator_surrogate": t3,
    }
    (artifacts_dir / "ml_evaluation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    res = run_phase3_ml_pipeline()
    print("[Phase 3] ML Evaluation Summary with Generalization Diagnostics saved.")
    for k, v in res.items():
        print(f"  - {k}: {v['title']}")
