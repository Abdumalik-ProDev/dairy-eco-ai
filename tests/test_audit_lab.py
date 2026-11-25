"""Tests for the ML audit layer: lineage, preprocessing, splits, leakage, reproducibility, lab UI."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dairyeco.audit import experiments as xp
from dairyeco.audit import model_audit as ma
from dairyeco.audit.build import build_audit
from dairyeco.audit.common import sha256_file, symbol_exists
from dairyeco.audit.splits import audit_task_splits
from dairyeco.config import PROJECT_ROOT
from dairyeco.dashboard.dev_mode import load_ml_artifacts
from dairyeco.models.registry import (
    MODEL_REGISTRY,
    assert_no_feature_leakage,
    build_preprocessor,
    load_task_frame,
    make_splits,
)

_build_preprocessor = build_preprocessor


@pytest.fixture(scope="module")
def audit() -> dict:
    return build_audit()


def test_dataset_lineage_counts_and_checksums(audit: dict) -> None:
    flows = audit["lineage"]["flows"]
    agb = pd.read_csv(PROJECT_ROOT / "data/processed/agribalyse_dairy_products.csv")
    assert flows["agribalyse_dairy_products"][1]["rows_after"] == len(agb)
    assert flows["agribalyse_dairy_products"][0]["rows_after"] == 2458
    assert flows["pdo_cheese_harmonized"][-1]["rows_after"] == 44
    assert flows["pdo_cheese_harmonized"][-1]["rows_before"] == 1232
    # de-packaging must not double count: total - packaging == non-packaging to float precision
    assert "e-15" in flows["agribalyse_dairy_products"][3]["note"] or "e-1" in flows["agribalyse_dairy_products"][3]["note"]
    for t in audit["dataset_registry"]["tables"]:
        assert sha256_file(PROJECT_ROOT / t["file"]) == t["sha256"]
        if t["built_by"]["symbol"]:
            assert t["built_by_verified"]
    core_tables = {t["table"]: t for t in audit["dataset_registry"]["tables"]}
    assert core_tables["agribalyse_dairy_products"]["consumers"]
    assert core_tables["pdo_cheese_harmonized"]["consumers"]


def test_decision_register_points_to_real_code(audit: dict) -> None:
    assert audit["decision_register"]
    for d in audit["decision_register"]:
        assert d["symbol_verified"], f"{d['id']} references missing {d['file']}::{d['symbol']}"
        assert symbol_exists(d["file"], d["symbol"])
    assert not symbol_exists("src/dairyeco/models/pipeline.py", "does_not_exist")


def test_preprocessing_is_fitted_on_training_data_only() -> None:
    train = pd.DataFrame({"x": [1.0, 2.0, 3.0, np.nan, 5.0], "c": ["a", "a", "b", "a", "b"]})
    val = pd.DataFrame({"x": [np.nan, 1000.0], "c": ["a", "zzz"]})
    prep = _build_preprocessor(["x"], ["c"]).fit(train)
    out = prep.transform(val)
    median_train = np.nanmedian(train["x"])  # 2.5
    scaler = prep.named_transformers_["num"].named_steps["scaler"]
    expected = (median_train - scaler.center_[0]) / scaler.scale_[0]
    assert out[0, 0] == pytest.approx(expected)  # imputed with the TRAIN median, not val statistics
    assert out[1, 1:].sum() == 0  # unseen category -> all-zero one-hot (handle_unknown=ignore)


def test_splits_are_deterministic_and_leak_free(audit: dict) -> None:
    for tk in MODEL_REGISTRY:
        df = load_task_frame(tk)
        tgt = MODEL_REGISTRY[tk]["target_col"]
        a, b = make_splits(tk, df, tgt), make_splits(tk, df, tgt)
        assert all(np.array_equal(x[1], y[1]) for x, y in zip(a, b, strict=True))
        seen = np.zeros(len(df), dtype=int)
        for tr, va in a:
            assert not set(tr) & set(va)
            seen[va] += 1
        assert (seen == 1).all()
        if tk.startswith("task3"):
            for tr, va in a:
                assert not set(df["product_id"].iloc[tr]) & set(df["product_id"].iloc[va])
        rec = audit["split_audit"][tk]
        hard = {c["id"]: c["status"] for c in rec["checks"]}
        for cid in ("split_integrity", "full_coverage", "target_leakage", "preprocessing_in_fold", "independent_holdout"):
            assert hard[cid] == "pass"


def test_leakage_guard_catches_target_and_forbidden_columns() -> None:
    with pytest.raises(ValueError):
        assert_no_feature_leakage(["a", "total_gwp_kgco2e_per_kg"], "y")
    with pytest.raises(ValueError):
        assert_no_feature_leakage(["a", "y"], "y")
    assert_no_feature_leakage(["a", "b"], "y")


def test_readiness_gates_are_evidence_based(audit: dict) -> None:
    summary, _ = load_ml_artifacts()
    for tk, rd in audit["readiness"].items():
        assert rd["level"] == "experimental"  # holdout passes, but G6 (real plant data) & G7 (monitoring) fail
        assert rd["blockers"]
    tk = "task2a_pdo_cheese_total"
    model, sp = audit["model_registry"][tk], audit["split_audit"][tk]
    # leakage failure forces not_suitable regardless of accuracy
    bad = {**sp, "checks": [{**c, "status": "fail"} if c["id"] == "target_leakage" else c for c in sp["checks"]]}
    assert ma.assess_readiness(model, bad, True, 0)["level"] == "not_suitable"
    # even with a holdout, model-derived labels and missing external validation cap the level
    ok = {**sp, "checks": [{**c, "status": "pass"} if c["id"] == "independent_holdout" else c for c in sp["checks"]]}
    assert ma.assess_readiness({**model, "source_type": "model_derived"}, ok, True, 1)["level"] == "experimental"
    assert summary


def test_experiment_tracking_and_reproducibility(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xp, "EXPERIMENTS_DIR", tmp_path)
    monkeypatch.setattr(xp, "EXPERIMENT_LOG", tmp_path / "experiments.jsonl")
    summary, _ = load_ml_artifacts()
    rec = xp.log_experiment("task2a_pdo_cheese_total", "Ridge", {"alpha": 5.0}, summary, seed=7, note="test")
    assert rec["experiment_id"].startswith("EXP-")
    for field in ("dataset_checksums", "code_fingerprint", "environment", "seed", "hyperparameters",
                  "feature_pipeline_version", "metrics", "created_at"):
        assert rec[field]
    assert xp.list_experiments()[0]["experiment_id"] == rec["experiment_id"]
    res = xp.reproduce(rec["experiment_id"], summary)
    assert res["status"] == "reproduced" and res["max_abs_metric_diff"] <= xp.REPRO_TOLERANCE
    other = xp.log_experiment("task2a_pdo_cheese_total", "Ridge", {"alpha": 50.0}, summary, seed=7)
    assert other["metrics"]["oof_mae"] != rec["metrics"]["oof_mae"]
    hist = xp.register_historical_baselines(summary)
    assert len(hist) == len(MODEL_REGISTRY) and xp.register_historical_baselines(summary) == []
    assert xp.reproduce("HIST-task1_agribalyse_gwp", summary)["status"] == "not_reproducible_via_tracker"
    assert "Not recorded" in hist[0]["duration_s"]


def test_split_audit_checks_runs_standalone() -> None:
    summary, _ = load_ml_artifacts()
    a = audit_task_splits("task3a_surrogate_gwp", summary)
    grp = next(c for c in a["checks"] if c["id"] == "group_leakage")
    assert grp["status"] == "pass"


def test_ml_lab_renders_all_sections(audit: dict) -> None:
    from streamlit.testing.v1 import AppTest

    from dairyeco.dashboard.audit_lab import PAGES

    app = PROJECT_ROOT / "src" / "dairyeco" / "dashboard" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=90)
    at.run()
    at.toggle(key="developer_mode_toggle").set_value(True).run()
    assert not at.exception
    at.session_state["dev_view"] = "lab"
    at.run()
    assert not at.exception, at.exception
    for page in PAGES:
        at.session_state["lab_page"] = page
        at.run()
        assert not at.exception, f"{page}: {at.exception}"
    # executive interface remains intact with Developer Mode off
    at.toggle(key="developer_mode_toggle").set_value(False).run()
    assert not at.exception
