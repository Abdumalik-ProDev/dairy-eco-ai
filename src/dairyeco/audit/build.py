"""Build and persist every audit record under ``artifacts/audit/`` (``dairyeco audit``)."""

from __future__ import annotations

import json
from typing import Any

from dairyeco.audit import data_records as dr
from dairyeco.audit import model_audit as ma
from dairyeco.audit.common import (
    code_fingerprint,
    environment_versions,
    now_iso,
    read_audit_json,
    write_audit_json,
)
from dairyeco.audit.experiments import register_historical_baselines
from dairyeco.audit.splits import audit_task_splits
from dairyeco.config import ARTIFACTS_DIR, AUDIT_DIR
from dairyeco.models.registry import MODEL_REGISTRY

RECORD_NAMES = (
    "dataset_registry", "lineage", "cleaning_log", "eda", "feature_registry", "model_registry",
    "split_audit", "risk_register", "decision_register", "readiness", "pipeline_overview",
    "dependency_graph", "audit_manifest",
)


def build_audit() -> dict[str, Any]:
    summary = json.loads((ARTIFACTS_DIR / "ml_evaluation_summary.json").read_text(encoding="utf-8"))
    registry = dr.build_dataset_registry()
    models = ma.build_model_registry(summary)
    splits = {tk: audit_task_splits(tk, summary) for tk in MODEL_REGISTRY}
    risks = ma.build_risk_register(summary, splits)
    hist = register_historical_baselines(summary)
    monitoring_hits = len(ma.scan_usage("drift") or ma.scan_usage("monitor"))
    readiness = {
        tk: ma.assess_readiness(models[tk], splits[tk], True, monitoring_hits) for tk in MODEL_REGISTRY
    }
    payload = {
        "dataset_registry": registry,
        "lineage": dr.build_lineage(),
        "cleaning_log": dr.build_cleaning_log(summary),
        "eda": dr.build_eda(summary),
        "feature_registry": dr.build_feature_registry(summary),
        "model_registry": models,
        "split_audit": splits,
        "risk_register": risks,
        "decision_register": ma.build_decision_register(),
        "readiness": readiness,
        "pipeline_overview": ma.build_pipeline_overview(),
        "dependency_graph": {"dot": ma.build_dependency_dot(registry)},
    }
    payload["audit_manifest"] = {
        "generated_at": now_iso(), "code_fingerprint": code_fingerprint(), "environment": environment_versions(),
        "historical_records_added": [h["experiment_id"] for h in hist],
        "records": [n for n in RECORD_NAMES if n != "audit_manifest"],
    }
    for name in RECORD_NAMES:
        write_audit_json(name, payload[name])
    return payload


def load_audit() -> dict[str, Any] | None:
    """Load persisted records; ``None`` if ``dairyeco audit`` has not been run."""
    if not (AUDIT_DIR / "audit_manifest.json").exists():
        return None
    return {n: read_audit_json(n) for n in RECORD_NAMES}
