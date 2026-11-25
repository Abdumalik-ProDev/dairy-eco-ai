"""Lightweight experiment tracker (JSONL) with reproducibility checks.

MLflow was considered and not added: it would introduce a dependency and server/state for what
is a single-developer research project. Records here are plain JSON lines that MLflow can
ingest later. Experiments train in memory only - production artifacts are never overwritten.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline

from dairyeco.audit.common import (
    NOT_RECORDED,
    code_fingerprint,
    environment_versions,
    rel,
    sha256_file,
)
from dairyeco.audit.splits import SPLIT_DESCRIPTION
from dairyeco.config import ARTIFACTS_DIR, EXPERIMENTS_DIR
from dairyeco.models import pipeline as ml_pipeline
from dairyeco.models.registry import (
    MODEL_REGISTRY,
    SEED,
    build_preprocessor,
    extract_estimator_params,
    get_task_summary_dict,
    load_task_frame,
    make_splits,
    run_cv_experiment,
)

EXPERIMENT_LOG = EXPERIMENTS_DIR / "experiments.jsonl"
REPRO_TOLERANCE = 1e-6


def feature_pipeline_version() -> str:
    """Hash of the preprocessing source (what actually transforms features)."""
    src = inspect.getsource(build_preprocessor)
    return hashlib.sha256(src.encode()).hexdigest()[:16]


def _read_all() -> list[dict[str, Any]]:
    if not EXPERIMENT_LOG.exists():
        return []
    return [json.loads(line) for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def list_experiments() -> list[dict[str, Any]]:
    return _read_all()


def _append(record: dict[str, Any]) -> None:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _config_hash(task_key: str, arch: str, params: dict[str, Any], seed: int) -> str:
    return hashlib.sha256(json.dumps([task_key, arch, params, seed], sort_keys=True).encode()).hexdigest()[:8]


def log_experiment(
    task_key: str, arch: str, params: dict[str, Any], summary: dict[str, Any], seed: int = SEED,
    note: str = "",
) -> dict[str, Any]:
    """Run and persist one controlled experiment (in memory training only)."""
    metrics = run_cv_experiment(task_key, arch, params, summary, seed)
    meta = MODEL_REGISTRY[task_key]
    info = get_task_summary_dict(summary, task_key)
    cf = code_fingerprint()
    now = datetime.now(UTC)
    record = {
        "experiment_id": f"EXP-{now:%Y%m%d-%H%M%S}-{_config_hash(task_key, arch, params, seed)}",
        "created_at": now.isoformat(timespec="seconds"), "kind": "new_run", "task_key": task_key,
        "architecture": arch, "hyperparameters": params, "seed": seed,
        "split_method": SPLIT_DESCRIPTION[task_key], "features": info["feature_columns"],
        "target": meta["target_col"], "feature_pipeline_version": feature_pipeline_version(),
        "dataset_checksums": {rel(meta["dataset_file"]): sha256_file(meta["dataset_file"])},
        "code_version": cf["vcs_commit"], "code_fingerprint": cf["aggregate_sha256"],
        "environment": environment_versions(), "metrics": metrics,
        "artifacts": "none (in-memory; production .joblib files untouched)", "note": note,
        "reproducible_via_tracker": True,
    }
    _append(record)
    return record


def register_historical_baselines(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconstruct one record per production champion from existing artifacts (idempotent).

    Fields that were never recorded at training time are labelled, not invented.
    """
    existing = {r["experiment_id"] for r in _read_all()}
    cf = code_fingerprint()
    added = []
    import joblib

    for tk, meta in MODEL_REGISTRY.items():
        eid = f"HIST-{tk}"
        if eid in existing:
            continue
        info = get_task_summary_dict(summary, tk)
        art = ARTIFACTS_DIR / meta["artifact_file"]
        pipe = joblib.load(art)
        diag = info["champion_diagnostics"]
        record = {
            "experiment_id": eid, "created_at": datetime.fromtimestamp(art.stat().st_mtime, UTC).isoformat(timespec="seconds"),
            "created_at_basis": "artifact file mtime (training timestamp was not recorded)",
            "kind": "reconstructed_historical", "task_key": tk, "architecture": info["best_model_name"],
            "hyperparameters": extract_estimator_params(pipe), "seed": SEED,
            "seed_basis": "random_state=42 in models/pipeline.py (code evidence)",
            "split_method": SPLIT_DESCRIPTION[tk], "features": info["feature_columns"],
            "target": meta["target_col"], "feature_pipeline_version": feature_pipeline_version(),
            "dataset_checksums": {rel(meta["dataset_file"]): sha256_file(meta["dataset_file"])},
            "dataset_checksums_basis": "hash at audit time, NOT at training time",
            "code_version": cf["vcs_commit"], "code_fingerprint": cf["aggregate_sha256"],
            "code_fingerprint_basis": "hash at audit time; training-time code not recorded",
            "environment": environment_versions(), "environment_basis": "audit time; training-time versions "
                                                                       + NOT_RECORDED,
            "metrics": {k: diag[k] for k in ("oof_mae", "oof_r2", "train_mae_mean", "train_r2_mean",
                                            "r2_generalization_gap", "normalized_mae_gap", "fit_diagnosis")},
            "duration_s": NOT_RECORDED, "artifacts": rel(art), "artifact_sha256": sha256_file(art),
            "note": "Reconstructed from ml_evaluation_summary.json and the .joblib artifact",
            "reproducible_via_tracker": False,
        }
        _append(record)
        added.append(record)
    return added


def reproduce(experiment_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    rec = next((r for r in _read_all() if r["experiment_id"] == experiment_id), None)
    if rec is None:
        return {"status": "unknown_experiment"}
    if not rec.get("reproducible_via_tracker"):
        return {"status": "not_reproducible_via_tracker",
                "reason": "Historical champion came from nested GridSearchCV over 8 candidates; re-running "
                          "`dairyeco train` regenerates (and overwrites) artifacts, so it is not done here."}
    meta = MODEL_REGISTRY[rec["task_key"]]
    cur = sha256_file(meta["dataset_file"])
    orig_hash = next(iter(rec["dataset_checksums"].values()))
    rerun = run_cv_experiment(rec["task_key"], rec["architecture"], rec["hyperparameters"], summary, rec["seed"])
    keys = ["oof_mae", "oof_rmse", "oof_r2", "train_mae_mean", "train_r2_mean"]
    diff = max(abs(rerun[k] - rec["metrics"][k]) for k in keys)
    return {"status": "reproduced" if diff <= REPRO_TOLERANCE and cur == orig_hash else "mismatch",
            "max_abs_metric_diff": diff, "dataset_unchanged": cur == orig_hash,
            "code_unchanged": code_fingerprint()["aggregate_sha256"] == rec["code_fingerprint"],
            "rerun_metrics": rerun}


# ----------------------------------------------------------------------------- diagnostics
def _champion_estimator(task_key: str) -> Any:
    import joblib

    pipe = joblib.load(ARTIFACTS_DIR / MODEL_REGISTRY[task_key]["artifact_file"])
    reg = pipe.named_steps["reg"]
    return clone(getattr(reg, "best_estimator_", reg))


def _cv_setup(task_key: str, summary: dict[str, Any]):
    meta = MODEL_REGISTRY[task_key]
    feats = get_task_summary_dict(summary, task_key)["feature_columns"]
    df = load_task_frame(task_key)
    X, y = df[feats], df[meta["target_col"]]
    num = [c for c in feats if pd.api.types.is_numeric_dtype(X[c])]
    cat = [c for c in feats if c not in num]
    prep = ml_pipeline._build_preprocessor(num, cat, min_frequency=2 if len(df) < 80 else None)
    return X, y, num, prep, make_splits(task_key, df, meta["target_col"])


def learning_curve_data(task_key: str, summary: dict[str, Any]) -> pd.DataFrame:
    """Train/validation MAE vs training-set size using the champion's fitted hyperparameters.

    Caveat (shown in the UI): those hyperparameters were tuned on all rows, so the curve is
    diagnostic of data hunger, not an unbiased performance estimate.
    """
    from sklearn.model_selection import learning_curve

    X, y, _, prep, splits = _cv_setup(task_key, summary)
    pipe = Pipeline([("prep", prep), ("reg", _champion_estimator(task_key))])
    sizes, tr, va = learning_curve(
        pipe, X, y, cv=splits, train_sizes=[0.3, 0.5, 0.7, 0.85, 1.0],
        scoring="neg_mean_absolute_error", n_jobs=1,
    )
    return pd.DataFrame({"train_size": sizes, "train_mae": -tr.mean(axis=1), "validation_mae": -va.mean(axis=1)})


def noise_sensitivity(task_key: str, summary: dict[str, Any], levels=(0.0, 0.05, 0.1, 0.2)) -> pd.DataFrame:
    """OOF MAE when numeric validation inputs get Gaussian noise (sigma = level x training std)."""
    X, y, num, prep, splits = _cv_setup(task_key, summary)
    rng = np.random.default_rng(SEED)
    rows = []
    for lvl in levels:
        oof = np.zeros(len(y))
        for tr, va in splits:
            fold = clone(Pipeline([("prep", clone(prep)), ("reg", _champion_estimator(task_key))]))
            fold.fit(X.iloc[tr], y.iloc[tr])
            xv = X.iloc[va].copy()
            for c in num:
                xv[c] = xv[c] + rng.normal(0.0, lvl * float(X.iloc[tr][c].std() or 0.0), len(xv))
            oof[va] = fold.predict(xv)
        rows.append({"noise_sigma_x_std": lvl, "oof_mae": float(mean_absolute_error(y, oof))})
    return pd.DataFrame(rows)
