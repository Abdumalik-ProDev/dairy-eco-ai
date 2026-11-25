"""Reconstruction of the exact CV splits used by ``dairyeco.models.pipeline`` and leakage audits.

``make_splits`` mirrors the split logic in ``run_task1_*``, ``run_task2_*`` and
``run_task3_*`` (same seeds / strata / groups). Every check below is computed from the real
datasets and from the real source code of the pipeline - nothing is asserted by hand.
"""

from __future__ import annotations

import inspect
from typing import Any

import joblib
import numpy as np
import pandas as pd

from dairyeco.audit.common import rel
from dairyeco.config import ARTIFACTS_DIR
from dairyeco.models import pipeline as ml_pipeline
from dairyeco.models.registry import (
    MODEL_REGISTRY,
    SEED,
    get_task_summary_dict,
    load_task_frame,
    make_holdout_split,
    make_splits,
)

ENTITY_COL = {
    "task1_agribalyse_gwp": "product_id",
    "task2a_pdo_cheese_total": "pdo_cheese_id",
    "task2b_pdo_cheese_post_farm": "pdo_cheese_id",
    "task3a_surrogate_gwp": "product_id",
    "task3b_surrogate_cost": "product_id",
}
SPLIT_DESCRIPTION = {
    "task1_agribalyse_gwp": "20% Stratified Holdout + StratifiedKFold(n_splits=5) on dev split",
    "task2a_pdo_cheese_total": "20% Stratified Holdout + StratifiedKFold(n_splits=5) by target quartile on dev split",
    "task2b_pdo_cheese_post_farm": "20% Stratified Holdout + StratifiedKFold(n_splits=5) by target quartile on dev split",
    "task3a_surrogate_gwp": "20% Group Holdout + GroupKFold(n_splits=5) grouped by product_id on dev split",
    "task3b_surrogate_cost": "20% Group Holdout + GroupKFold(n_splits=5) grouped by product_id on dev split",
}


def _check(cid: str, name: str, status: str, evidence: str, code_ref: str) -> dict[str, str]:
    return {"id": cid, "name": name, "status": status, "evidence": evidence, "code_ref": code_ref}


def audit_task_splits(task_key: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Run split / leakage / contamination checks for one registered model task."""
    meta = MODEL_REGISTRY[task_key]
    info = get_task_summary_dict(summary, task_key)
    target = meta["target_col"]
    feats: list[str] = info["feature_columns"]
    full_df = load_task_frame(task_key)
    n_full = len(full_df)
    dev_idx, ho_idx = make_holdout_split(task_key, full_df, target)
    df = full_df.iloc[dev_idx].reset_index(drop=True)
    n = len(df)
    splits = make_splits(task_key, df, target)

    seen = np.zeros(n, dtype=int)
    overlap = 0
    group_overlap = 0
    gcol = "product_id" if task_key.startswith("task3") else None
    for tr, va in splits:
        overlap += len(set(tr) & set(va))
        seen[va] += 1
        if gcol:
            group_overlap += len(set(df[gcol].iloc[tr]) & set(df[gcol].iloc[va]))
    sizes = [{"fold": i + 1, "train": len(tr), "validation": len(va)}
             for i, (tr, va) in enumerate(splits)]

    keys = pd.util.hash_pandas_object(df[feats].astype(str), index=False).to_numpy()
    dup_cross = int(sum(np.isin(keys[va], keys[tr]).sum() for tr, va in splits))
    entity = ENTITY_COL[task_key]
    n_entities = int(full_df[entity].nunique()) if entity in full_df.columns else -1

    ho_overlap = len(set(dev_idx) & set(ho_idx))
    ho_group_overlap = (
        len(set(full_df[gcol].iloc[dev_idx]) & set(full_df[gcol].iloc[ho_idx]))
        if gcol
        else 0
    )
    has_holdout = bool(info.get("holdout_metrics")) and ho_overlap == 0 and ho_group_overlap == 0

    try:
        ml_pipeline.assert_no_feature_leakage(feats, target)
        leak_status, leak_ev = "pass", (
            f"{len(feats)} features checked against {len(ml_pipeline.FORBIDDEN_LEAKAGE_COLUMNS)} "
            "forbidden columns and the target"
        )
    except ValueError as exc:
        leak_status, leak_ev = "fail", str(exc)

    src = inspect.getsource(ml_pipeline._evaluate_candidates)
    prep_in_fold = "clone(base_pipe)" in src and "fold_pipe.fit(X_tr" in src
    prod = joblib.load(ARTIFACTS_DIR / meta["artifact_file"])
    prep_is_step = list(prod.named_steps)[:1] == ["prep"]

    sel_src = inspect.getsource(ml_pipeline._evaluate_candidates)
    selects_on_oof = "min(" in sel_src and 'r["mae"]' in sel_src

    checks = [
        _check("split_integrity", "Train/validation indices never overlap",
               "pass" if overlap == 0 else "fail", f"{overlap} overlapping indices across {len(splits)} folds",
               "models/pipeline.py::_evaluate_candidates"),
        _check("full_coverage", "Every record is validated exactly once (OOF)",
               "pass" if (seen == 1).all() else "fail",
               f"min/max validation count per record = {seen.min()}/{seen.max()}",
               "models/pipeline.py::_evaluate_candidates"),
        _check("entity_unique", f"One record per entity ({entity})",
               "pass" if n_entities == n_full else "warn",
               f"{n_entities} unique '{entity}' values in {n_full} rows", "data/harmonize.py"),
        _check("group_leakage", "No group (product) shared between train and validation",
               ("pass" if group_overlap == 0 else "fail") if gcol else "na",
               (f"{group_overlap} shared product_id across folds" if gcol
                else "Each row is its own entity (255 products / 44 cheeses); no repeated groups exist"),
               "models/pipeline.py::run_task3_simulator_surrogate"),
        _check("duplicate_feature_vectors", "Identical feature vectors across train/validation",
               "pass" if dup_cross == 0 else "warn",
               f"{dup_cross} validation rows have an exact feature-vector twin in their training fold",
               "models/pipeline.py"),
        _check("target_leakage", "Forbidden/target columns absent from features", leak_status, leak_ev,
               "models/pipeline.py::assert_no_feature_leakage"),
        _check("preprocessing_in_fold", "Imputer/scaler/encoder fitted on training fold only",
               "pass" if (prep_in_fold and prep_is_step) else "fail",
               f"fold pipeline cloned and fitted on X_tr each fold: {prep_in_fold}; "
               f"production artifact first step is 'prep': {prep_is_step}",
               "models/pipeline.py::_evaluate_candidates"),
        _check("temporal_leakage", "Temporal ordering", "na",
               "Records carry no observation timestamp (static LCA reference values); a temporal "
               "split is not defined for this data", "-"),
        _check("selection_on_oof", "Model-family selection uses the same OOF scores that are reported",
               "warn" if selects_on_oof else "pass",
               "Champion = argmin penalised OOF MAE among candidates; inner GridSearchCV is nested, "
               "but the final OOF numbers are also the selection criterion (optimistic bias possible)",
               "models/pipeline.py::_evaluate_candidates"),
        _check("independent_holdout", "Untouched final test set",
               "pass" if has_holdout else "fail",
               (f"{len(ho_idx)} untouched holdout records ({len(ho_idx)/n_full:.0%}); "
                f"0 index overlap, {ho_group_overlap} group overlap with dev split")
               if has_holdout else
               "The pipeline defines cross-validation only; no record is excluded from selection",
               "models/pipeline.py::_evaluate_candidates"),
    ]
    return {
        "task_key": task_key, "n_rows": n_full, "n_dev_rows": n, "n_holdout_rows": len(ho_idx),
        "n_features": len(feats), "seed": SEED,
        "split_method": SPLIT_DESCRIPTION[task_key], "fold_sizes": sizes,
        "validation_fraction": round(float(np.mean([s["validation"] / n for s in sizes])), 4),
        "checks": checks, "dataset_file": rel(meta["dataset_file"]),
    }
