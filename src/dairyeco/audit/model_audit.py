"""Model-side audit records: registry, risk register, readiness gates, decisions, overview, graph."""

from __future__ import annotations

import math
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV, RidgeCV
from sklearn.model_selection import GridSearchCV

from dairyeco.audit.common import (
    NOT_RECORDED,
    rel,
    sha256_file,
    symbol_exists,
)
from dairyeco.audit.data_records import scan_usage
from dairyeco.audit.splits import SEED, SPLIT_DESCRIPTION, load_task_frame
from dairyeco.config import ARTIFACTS_DIR, METADATA_DIR, PROCESSED_DIR, SYNTHETIC_DIR
from dairyeco.models import pipeline as ml_pipeline
from dairyeco.models.registry import (
    MODEL_REGISTRY,
    extract_estimator_params,
    get_task_summary_dict,
)
from dairyeco.optimization.pareto import build_preset_package_configurations

PROBLEM = {
    "task1_agribalyse_gwp": (
        ("Predict de-packaged GWP (kg CO2e/kg) of a dairy product from pre-LCA product attributes "
         "(category, subgroup, delivery mode, milk yield, density, DQR)."),
        ("Inferred: AGRIBALYSE already publishes GWP for every product, so a model adds no new information "
         "for these 255 products; it is a leak-free pre-LCA research baseline.")),
    "task2a_pdo_cheese_total": (
        ("Predict total cradle-to-ripening-exit GWP of a PDO cheese from specifications, allocation, "
        "co-products and raw-milk origin."),
        ("Inferred: exploratory case study (N=44). The deterministic LCA already exists in the source; ML "
        "explores which pre-LCI specs explain GWP.")),
    "task2b_pdo_cheese_post_farm": (
        "Predict post-farm GWP (processing + ripening + transport) from physical LCI utility flows.",
        ("Inferred: a physical relation (electricity, transport, cleaning) -> GWP; a linear model recovering it "
        "is a sanity check of the data, not a prediction tool.")),
    "task3a_surrogate_gwp": (
        "Approximate the deterministic packaging-system GWP of a scenario.",
        ("ML is NOT needed for correctness: the deterministic LCA engine is exact and is what the executive UI "
        "displays. A surrogate is only justified for speed in large optimisation sweeps.")),
    "task3b_surrogate_cost": (
        "Approximate the deterministic packaging-attributable cost of a scenario.",
        "Same as 3A: the economics engine is exact; the surrogate is a fast approximation."),
}


def _grid_size(grid: dict[str, list[Any]]) -> int:
    return int(math.prod(len(v) for v in grid.values()))


def search_spaces(n: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, est in ml_pipeline._candidate_regressors(n).items():
        if isinstance(est, GridSearchCV):
            out[name] = {"method": f"GridSearchCV(cv={est.cv}, scoring={est.scoring}) nested in each outer train fold",
                         "space": {k: list(v) for k, v in est.param_grid.items()},
                         "n_combinations": _grid_size(est.param_grid),
                         "inner_fits_per_outer_fold": _grid_size(est.param_grid) * int(est.cv)}
        elif isinstance(est, RidgeCV):
            a = np.asarray(est.alphas)
            out[name] = {"method": "RidgeCV (efficient leave-one-out over alphas)",
                         "space": {"alpha": f"{len(a)} log-spaced values in [{a.min():.3g}, {a.max():.3g}]"}}
        elif isinstance(est, ElasticNetCV):
            a = np.asarray(est.alphas)
            out[name] = {"method": f"ElasticNetCV(cv={est.cv})",
                         "space": {"l1_ratio": list(est.l1_ratio), "alpha": f"{len(a)} log-spaced values in "
                                                                          f"[{a.min():.3g}, {a.max():.3g}]"}}
        else:
            params = {k: v for k, v in est.get_params(deep=False).items()
                      if isinstance(v, (int, float, str, bool)) or v is None}
            out[name] = {"method": "fixed configuration (no search)" if not hasattr(est, "estimators")
                         else "VotingRegressor of Ridge+ElasticNet+CatBoost (weights 1,1,1.5)",
                         "space": {k: v for k, v in list(params.items())[:10]}}
    return out


def build_model_registry(summary: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tk, meta in MODEL_REGISTRY.items():
        info = get_task_summary_dict(summary, tk)
        art = ARTIFACTS_DIR / meta["artifact_file"]
        pipe = joblib.load(art)
        reg = pipe.named_steps["reg"]
        inner = getattr(reg, "best_estimator_", reg)
        metrics = [m for m in info["metrics"]]
        non_dummy = [m for m in metrics if not m["model_name"].startswith("Dummy")]
        dummy = next(m for m in metrics if m["model_name"].startswith("Dummy"))
        champ = next(m for m in metrics if m.get("is_selected_champion"))
        best = {
            "lowest_oof_mae": min(non_dummy, key=lambda m: m["mae"])["model_name"],
            "lowest_oof_rmse": min(non_dummy, key=lambda m: m["rmse"])["model_name"],
            "highest_oof_r2": max(non_dummy, key=lambda m: m["r2"])["model_name"],
            "smallest_r2_gap": min(non_dummy, key=lambda m: m["r2_generalization_gap"])["model_name"],
        }
        n = info["n_observations"]
        what, why_ml = PROBLEM[tk]
        out[tk] = {
            "label": meta["label"], "dataset": meta["dataset_name"], "source_type": meta["source_type"],
            "problem": what, "why_ml_vs_deterministic": why_ml, "n_observations": n,
            "champion": champ["model_name"], "estimator_class": type(inner).__name__,
            "fitted_hyperparameters": extract_estimator_params(pipe),
            "candidates": metrics, "baseline": {"model": dummy["model_name"], "oof_mae": dummy["mae"],
                                               "oof_r2": dummy["r2"]},
            "improvement_vs_baseline_mae": round(1 - champ["mae"] / dummy["mae"], 4),
            "best_by_metric": best, "champion_is_lowest_mae": best["lowest_oof_mae"] == champ["model_name"],
            "selection_rule": "argmin of OOF MAE x (1 + 0.5*r2_gap + 0.5*norm_mae_gap) within the "
                              "'well_generalized' pool (models/pipeline.py::_evaluate_candidates)",
            "search_spaces": search_spaces(n), "cv": meta["cv_type"], "split_method": SPLIT_DESCRIPTION[tk],
            "seed": SEED, "training_duration": f"{info.get('training_duration_s', NOT_RECORDED)} s",
            "experiment_version": NOT_RECORDED,
            "holdout_metrics": info.get("holdout_metrics", {}),
            "artifact": {"path": rel(art), "sha256": sha256_file(art), "bytes": art.stat().st_size,
                         "mtime_utc": pd.Timestamp(art.stat().st_mtime, unit="s", tz="UTC").isoformat()},
            "champion_diagnostics": info["champion_diagnostics"],
            "feature_importances": info.get("feature_importances", []),
        }
    return out


def _presets_vs_training() -> dict[str, Any]:
    sim = pd.read_csv(SYNTHETIC_DIR / "simulated_packaging_scenarios.csv")
    mapping = {"line_reject_rate": "line_reject_rate", "spoilage_loss_rate": "package_attributable_spoilage_rate",
               "supplier_distance_km": "supplier_to_plant_distance_km",
               "distribution_distance_km": "distribution_distance_km", "net_fill_mass_kg": "net_fill_mass_kg"}
    rows = []
    for pid, cfg in build_preset_package_configurations().items():
        for col, attr in mapping.items():
            v = float(getattr(cfg, attr))
            lo, hi = float(sim[col].min()), float(sim[col].max())
            if not lo <= v <= hi:
                rows.append({"preset": pid, "feature": col, "value": v, "train_min": lo, "train_max": hi})
    return {"out_of_range": rows, "n_presets": len(build_preset_package_configurations())}


def build_risk_register(summary: dict[str, Any], split_audits: dict[str, Any]) -> list[dict[str, Any]]:
    agb = load_task_frame("task1_agribalyse_gwp")
    cheese_share = float((agb["category"] == "cheese").mean())
    sim = pd.read_csv(SYNTHETIC_DIR / "simulated_packaging_scenarios.csv")
    cats_all = set(pd.read_csv(PROCESSED_DIR / "agribalyse_dairy_products.csv")
                   .query("is_core_dairy")["category"].unique())
    missing_cats = sorted(cats_all - set(sim["dairy_category"].unique()))
    fac = pd.read_csv(PROCESSED_DIR / "packaging_impact_factors.csv")
    proxy_share = float((fac["source_type"] == "proxy").mean())
    t2 = summary["task2_pdo_cheese"]["champion_diagnostics"]
    t2_mae, t2_std = t2["oof_mae"], float(str(t2["cv_mae_mean_pm_std"]).split("±")[1])
    pv = _presets_vs_training()
    dup = {tk: next(c for c in a["checks"] if c["id"] == "duplicate_feature_vectors")["evidence"]
           for tk, a in split_audits.items()}
    cf = pd.read_csv(SYNTHETIC_DIR / "simulated_packaging_scenarios.csv")
    has_circular_feat = "expected_bom_material_spend_usd_per_fu" in cf.columns
    t1_feats = set(summary["task1_agribalyse"]["feature_columns"])
    has_lcia_leak = bool(t1_feats & {"eutrophication_marine_kg_n_eq_per_kg", "transport_gwp_kgco2e_per_kg"})
    has_holdout = all(
        next(c for c in split_audits[tk]["checks"] if c["id"] == "independent_holdout")["status"] == "pass"
        for tk in MODEL_REGISTRY
    )
    monitoring = scan_usage("drift") or scan_usage("monitor")

    def r(rid, cat, title, sev, evidence, impact, mitigation, status, models):
        return {"id": rid, "category": cat, "title": title, "severity": sev, "evidence": evidence,
                "impact": impact, "mitigation": mitigation, "status": status, "models": models}

    all_models = list(MODEL_REGISTRY)
    t3 = ["task3a_surrogate_gwp", "task3b_surrogate_cost"]
    risks = [
        r("R01", "validation", "Untouched holdout test set", "low" if has_holdout else "high",
          "20% stratified/grouped holdout evaluated once per task" if has_holdout else
          "Pipeline defines CV only; all rows participate in selection (see split audit)",
          "Holdout metrics are unbiased for fixed dev selection",
          "Maintain strict holdout isolation", "resolved" if has_holdout else "open", all_models),
        r("R02", "validation", "Model-family selection reuses the reported OOF metric", "medium",
          "8 candidates, champion = argmin penalised OOF MAE; mitigated by 20% untouched holdout",
          "Mild optimistic bias on OOF, largest for N=44", "Report holdout alongside OOF", "mitigated" if has_holdout else "open", all_models),
        r("R03", "label", "Task 3 labels are produced by the deterministic engine", "high",
          "target = EnvironmentalResult/EconomicResult output (generate_simulated_scenario_dataset)",
          "Metrics measure engine-copy fidelity, not real-world accuracy",
          "Disclosed in model card; executive UI uses the exact engine, never the surrogate", "accepted", t3),
        r("R04", "leakage", "Task 3 circular target-mirror features", "low" if not has_circular_feat else "medium",
          "expected_bom_material_spend and expected_spoilage_gwp removed from Task 3 features" if not has_circular_feat
          else "Target-mirror features present",
          "Surrogate learns from physical/operational inputs only", "Keep target-mirror features blocked",
          "resolved" if not has_circular_feat else "open", t3),
        r("R05", "sample size", "Task 2 has only 44 observations", "high",
          f"champion OOF MAE {t2_mae:.3f} with fold std {t2_std:.3f} (std > mean)",
          "Performance estimate has very wide uncertainty", "Do not use for decisions; collect more cheeses", "open",
          ["task2a_pdo_cheese_total", "task2b_pdo_cheese_post_farm"]),
        r("R06", "geographic bias", "Training data are France/US/EU; deployment goal is Central Asia", "high",
          "AGRIBALYSE/PDO geography = FR only; resin factors US/EU/CN/MENA; UI grid presets include Uzbekistan",
          "Factors may not transfer to Uzbek supply chains", "Collect local plant data; label outputs as FR-based",
          "open", all_models),
        r("R07", "temporal bias", "Reference years span 2007-2025 and no observation date exists", "medium",
          "packaging factor reference_year values: "
          + ", ".join(sorted(fac["reference_year"].astype(str).unique())) + "; PDO tables 2020-2022",
          "Cannot test temporal drift; mixed vintages", "Record vintages explicitly; refresh factors", "accepted", all_models),
        r("R08", "sampling bias", "Task 1 sample dominated by cheese", "medium",
          f"cheese = {cheese_share:.0%} of 255 core AGRIBALYSE products",
          "Performance on other categories is less certain", "Report per-category error", "open", ["task1_agribalyse_gwp"]),
        r("R09", "selection bias", "PDO cheeses are specialty products", "medium",
          "44 PDO cheeses only; INAO-regulated technologies", "Not representative of industrial cheese",
          "State scope in every PDO output", "accepted", ["task2a_pdo_cheese_total", "task2b_pdo_cheese_post_farm"]),
        r("R10", "representation", "Dairy categories absent from simulator training set", "medium" if missing_cats else "low",
          f"core categories without simulated rows: {missing_cats or 'none'}",
          "Surrogate cannot be trusted for missing categories", "Extend the generator", "open" if missing_cats else "resolved", t3),
        r("R11", "measurement bias", "Many LCA factors are typed literals; part are proxies", "high",
          f"{proxy_share:.0%} of {len(fac)} packaging factors are source_type=proxy; GWP/energy/water values "
          "for USLCI polymers are literals in harmonize.py, not computed from raw JSON",
          "Exact-looking numbers may not trace to raw files", "Compute factors from raw data or cite the page/table "
          "per literal", "open", all_models),
        r("R12", "measurement bias", "Density assigned by category rule", "low",
          "_infer_dairy_density returns one value per category", "Density is a redundant proxy of category",
          "Use measured density where available", "accepted", ["task1_agribalyse_gwp"]),
        r("R13", "feature validity", "Task 1 co-computed LCIA indicator leakage",
          "medium" if has_lcia_leak else "low",
          "Co-computed LCIA midpoint indicators and stage GWPs are blocked by FORBIDDEN_LEAKAGE_COLUMNS"
          if not has_lcia_leak else "LCIA indicators present in Task 1",
          "Task 1 uses pre-LCA attributes only" if not has_lcia_leak else "Mild definition mismatch",
          "Keep co-computed LCIA indicators blocked", "resolved" if not has_lcia_leak else "open",
          ["task1_agribalyse_gwp"]),
        r("R14", "proxy variable", "preset_id / category act as identity proxies", "medium",
          "preset_id nearly determines package BOM in Task 3", "Model may memorise presets rather than physics",
          "Ablate identity features", "open", t3),
        r("R15", "distribution shift", "Executive presets vs simulator training ranges",
          "medium" if pv["out_of_range"] else "low",
          f"{len(pv['out_of_range'])} preset/feature values outside the simulated range: {pv['out_of_range'][:4]}",
          "Out-of-range scenarios extrapolate", "Widen generator ranges or block predictions",
          "open" if pv["out_of_range"] else "resolved", t3),
        r("R16", "monitoring", "No drift or performance monitoring", "medium",
          f"code scan for 'drift'/'monitor' outside audit layer: {len(monitoring)} hits",
          "Silent degradation after data refresh", "Add scheduled checksum + metric checks", "open", all_models),
        r("R17", "reproducibility", "Historical training metadata not recorded", "medium",
          "No VCS commit, training duration, dependency versions or experiment IDs existed before this audit layer",
          "Past results cannot be exactly reproduced", "Use the experiment tracker from now on; initialise git", "mitigated",
          all_models),
        r("R18", "uncertainty", "No calibrated prediction intervals", "medium",
          "Only empirical OOF absolute-error quantiles are available",
          "Users may over-read point predictions", "Conformal prediction on a holdout", "open", all_models),
        r("R19", "leakage", "Near-duplicate feature vectors across folds", "low",
          "; ".join(f"{k}: {v}" for k, v in dup.items()), "Slightly optimistic CV", "Group near-duplicates", "accepted",
          all_models),
        r("R20", "interpretation", "Importance/attribution methods are not causal", "low",
          "Permutation importance with correlated features; local attribution is marginal replacement, not exact SHAP",
          "Misreading as causal drivers", "State limitation next to every chart", "accepted", all_models),
    ]
    return risks


def _gate(gid: str, name: str, status: str, evidence: str) -> dict[str, str]:
    return {"id": gid, "name": name, "status": status, "evidence": evidence}


def assess_readiness(model: dict[str, Any], split_audit: dict[str, Any], tracker_has_record: bool,
                     monitoring_hits: int) -> dict[str, Any]:
    chk = {c["id"]: c for c in split_audit["checks"]}
    hard = ["split_integrity", "full_coverage", "group_leakage", "target_leakage", "preprocessing_in_fold"]
    bad = [h for h in hard if chk[h]["status"] == "fail"]
    diag = model["champion_diagnostics"]
    gates = [
        _gate("G1", "No leakage / split violations", "pass" if not bad else "fail",
              "all structural checks pass" if not bad else f"failed: {bad}"),
        _gate("G2", "Generalisation (train vs OOF)", "pass" if diag["fit_diagnosis"] == "well_generalized" else "fail",
              f"fit_diagnosis={diag['fit_diagnosis']}, R2 gap={diag['r2_generalization_gap']}"),
        _gate("G3", "Beats baseline by >= 50% MAE", "pass" if model["improvement_vs_baseline_mae"] >= 0.5 else "fail",
              f"improvement {model['improvement_vs_baseline_mae']:.1%} vs {model['baseline']['model']}"),
        _gate("G4", "Independent untouched test set", chk["independent_holdout"]["status"] if
              chk["independent_holdout"]["status"] in ("pass", "fail") else "fail", chk["independent_holdout"]["evidence"]),
        _gate("G5", "Labels measured or published (not model-derived)",
              "fail" if model["source_type"] == "model_derived" else "pass", f"source_type={model['source_type']}"),
        _gate("G6", "Validated on real observed plant/market data", "fail",
              "No external validation record exists in the project (" + NOT_RECORDED + ")"),
        _gate("G7", "Monitoring / drift detection in place", "pass" if monitoring_hits else "fail",
              f"{monitoring_hits} code references to drift/monitoring"),
        _gate("G8", "Reproducible experiment record", "partial" if tracker_has_record else "fail",
              "Reconstructed historical record exists; training-time code/env/duration not recorded"
              if tracker_has_record else "no record"),
    ]
    st = {g["id"]: g["status"] for g in gates}
    if st["G1"] == "fail" or st["G2"] == "fail" or st["G3"] == "fail":
        level = "not_suitable"
    elif st["G4"] != "pass":
        level = "research_prototype"
    elif st["G5"] != "pass" or st["G6"] != "pass":
        level = "experimental"
    elif st["G7"] != "pass" or st["G8"] != "pass":
        level = "validated"
    else:
        level = "production_candidate"
    blockers = [f"{g['id']} {g['name']}: {g['evidence']}" for g in gates if g["status"] != "pass"]
    return {"level": level, "gates": gates, "blockers": blockers,
            "rule": "not_suitable if G1-G3 fail; research_prototype if G4 fails; experimental if G5 or G6 fail; "
                    "validated if G7/G8 not both pass; else production_candidate"}


def _d(did, what, why, file, symbol, inputs, outputs, tests, alternatives, limitation):
    return {"id": did, "what": what, "why": why, "file": file, "symbol": symbol,
            "symbol_verified": symbol_exists(file, symbol), "inputs": inputs, "outputs": outputs,
            "tests": tests, "alternatives": alternatives, "limitation": limitation}


def build_decision_register() -> list[dict[str, Any]]:
    h, p, r, a = (
        "src/dairyeco/data/harmonize.py",
        "src/dairyeco/models/pipeline.py",
        "src/dairyeco/models/registry.py",
        "src/dairyeco/data/audit_inspectors.py",
    )
    t1, t0 = "tests/test_phases_1_to_4.py::test_phase1_harmonized_tables_and_provenance", "tests/test_phase0_audit.py"
    return [
        _d("D01", "Subtract AGRIBALYSE packaging stage from product GWP", "Baseline totals embed packaging; swapping "
           "packaging would double count", h, "build_agribalyse_dairy_table", "AGRIBALYSE Synthese + Detail etape",
           "agribalyse_dairy_products.csv", [t1], NOT_RECORDED, "Other stages keep packaging-related assumptions"),
        _d("D02", "Normalise PDO cheese names before joining", "Whitespace and Camenbert/Camembert typo break joins",
           a, "normalize_pdo_cheese_name", "7 PDO workbooks", "44-cheese table", [t0 + "::test_pdo_cheese_audit_inspector"],
           "Fuzzy matching (not recorded as considered)", "One hard-coded typo"),
        _d("D03", "Treat 44 cheeses (not 1,232 LCIA rows) as observations", "Rows are 44 x 28 indicators, not independent",
           h, "build_pdo_cheese_harmonized_table", "data_PDOcheeses_LCIA.xlsx", "pdo_cheese_harmonized.csv",
           [t1], NOT_RECORDED, "N=44"),
        _d("D04", "Mark proxy factors with source_type", "USLCI lacks container glass/LPB; blow-molding", h,
           "build_unified_packaging_impact_factors", "NIST CSV, USLCI table, literals", "packaging_impact_factors.csv",
           [t1], NOT_RECORDED, "Proxy rows marked explicitly as DataSourceType.PROXY"),
        _d("D05", "Block forbidden columns from features", "Prevent target/ID/LCIA leakage", r, "assert_no_feature_leakage",
           "feature list", "ValueError or pass", ["tests/test_phases_1_to_4.py::test_phase3_ml_leakage_guard_and_artifacts"],
           "Automatic correlation screen (not recorded)", "Hand-maintained list"),
        _d("D06", "Median/RobustScaler + one-hot inside a Pipeline", "Heavy tails; avoids fitting on validation data", r,
           "build_preprocessor", "feature table", "design matrix", ["tests/test_phases_1_to_4.py::test_phase3_ml_leakage_guard_and_artifacts"],
           NOT_RECORDED, "No log-transform of skewed targets"),
        _d("D07", "Candidate set of 8 regularised models incl. dummy baseline", "Compare linear, bagging, boosting, "
           "ensemble under shared splits", p, "_candidate_regressors", "N (sample size)", "estimators + search grids",
           [], "Candidate pool itself: " + NOT_RECORDED, "Grids are small, hand-chosen"),
        _d("D08", "Champion = penalised OOF MAE among well-generalised models", "Prefer generalisation over raw accuracy",
           p, "_evaluate_candidates", "OOF predictions", "champion + diagnostics", [], NOT_RECORDED,
           "Mitigated by 20% untouched holdout evaluation"),
        _d("D09", "Thresholds for over/underfit diagnosis", "Scale-invariant gap rules", r, "classify_fit_diagnosis",
           "train/OOF metrics", "fit_diagnosis label", [], NOT_RECORDED, "Thresholds (0.045, 0.10, ...) are heuristic"),
        _d("D10", "GroupKFold by product for Task 3", "Same product must not appear in train and validation", p,
           "run_task3_simulator_surrogate", "simulated scenarios", "group-safe splits", ["tests/test_audit_lab.py::test_split_audit_checks"],
           "Random KFold (rejected: would leak products)", "Only product-level grouping"),
        _d("D11", "StratifiedKFold(11) for 44 cheeses", "Balanced target quartiles in 4-cheese folds", p,
           "run_task2_pdo_cheese_case_study", "44 cheeses", "OOF predictions", [], NOT_RECORDED, "High variance"),
        _d("D12", "Generate 1,200 simulator scenarios", "Create labelled data for a fast surrogate", p,
           "generate_simulated_scenario_dataset", "products x presets x random perturbations", "simulated_packaging_scenarios.csv",
           [], NOT_RECORDED, "Perturbation ranges are assumptions"),
        _d("D13", "Executive results come from deterministic engines", "Exact, auditable, no ML error", "src/dairyeco/lca/engine.py",
           "evaluate_environmental_lca", "product, packaging, assumptions", "EnvironmentalResult",
           ["tests/test_phases_1_to_4.py::test_phase2_hand_calculated_lca_and_economic_formulas"], NOT_RECORDED,
           "Factor quality bounds accuracy"),
        _d("D14", "Payback from incremental cash flows", "Correct financial logic", "src/dairyeco/economics/engine.py",
           "calculate_payback_schedule", "CAPEX, annual cash flow, horizon", "payback status/years",
           ["tests/test_phases_1_to_4.py::test_payback_schedule_and_scenario_dynamics"], NOT_RECORDED, "Assumed inputs"),
    ]


def build_pipeline_overview() -> list[dict[str, Any]]:
    inv = METADATA_DIR / "raw_file_inventory.csv"
    n_inv = len(pd.read_csv(inv)) if inv.exists() else 0
    mon = scan_usage("drift") or scan_usage("monitor")
    art_use = scan_usage("task3_surrogate_gwp_model.joblib")
    api_loads = [x for x in art_use if "api" in x["file"]]
    s = lambda stage, status, ev, ref: {"stage": stage, "status": status, "evidence": ev, "code": ref}
    return [
        s("Data discovery", "partial", "reports/dataset_audit.md documents the sources found; discovery process and "
          "rejected candidates not recorded", "reports/dataset_audit.md"),
        s("Dataset selection", "partial", f"dataset_manifest.csv lists 5 sources with intended use; alternatives {NOT_RECORDED}",
          "data/metadata/dataset_manifest.csv"),
        s("Data acquisition", "implemented", f"{n_inv} raw files inventoried with SHA-256; download_date field in manifest",
          "src/dairyeco/data/inventory.py"),
        s("Data profiling", "implemented", "audit_inspectors.py + reports/data_quality_report.md (18 findings)",
          "src/dairyeco/data/audit_inspectors.py"),
        s("Data cleaning", "implemented", "documented in the Cleaning log", "src/dairyeco/data/harmonize.py"),
        s("Data integration", "implemented", "documented in the Lineage page", "src/dairyeco/data/harmonize.py"),
        s("Feature engineering", "implemented", "documented in the Feature registry", "src/dairyeco/models/pipeline.py"),
        s("EDA", "partial", "No EDA was persisted by the original pipeline; this audit layer computes and stores it",
          "src/dairyeco/audit/data_records.py::build_eda"),
        s("Model selection", "implemented", "8 candidates compared per task", "src/dairyeco/models/pipeline.py::_candidate_regressors"),
        s("Training", "implemented", "Nested CV training; duration not recorded", "src/dairyeco/models/pipeline.py"),
        s("Hyperparameter optimisation", "implemented", "Nested GridSearchCV/RidgeCV/ElasticNetCV", "src/dairyeco/models/pipeline.py"),
        s("Validation", "implemented", "Stratified / Group K-fold OOF", "src/dairyeco/models/pipeline.py"),
        s("Testing", "partial", "No independent holdout (CV only)", "src/dairyeco/audit/splits.py"),
        s("Explainability", "partial", "OOF permutation importance persisted; local attribution is SHAP-style marginal "
          "replacement, not true SHAP", "src/dairyeco/dashboard/dev_mode.py::compute_local_feature_attributions"),
        s("Model evaluation", "implemented", "ml_evaluation_summary.json + reports/model_cards.md", "reports/model_cards.md"),
        s("Deployment", "partial", f"joblib artifacts loaded by Developer Mode; API loads surrogate: {bool(api_loads)}; "
          "executive UI uses deterministic engines only", "src/dairyeco/dashboard/dev_mode.py::load_ml_artifacts"),
        s("Inference", "partial", "Live inference only for Task 3 surrogates in Developer Mode",
          "src/dairyeco/dashboard/dev_mode.py"),
        s("Monitoring", "missing" if not mon else "partial", f"{len(mon)} drift/monitoring references found", "-"),
    ]


def build_dependency_dot(registry: dict[str, Any]) -> str:
    lines = ["digraph G {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];']
    for m in registry["manifest"]:
        lines.append(f'"raw:{m["dataset_id"]}" [label="RAW\\n{m["dataset_id"]}", fillcolor="#e0f2fe"];')
    task_by_file: dict[str, list[str]] = {}
    for tk, meta in MODEL_REGISTRY.items():
        task_by_file.setdefault(meta["dataset_file"].name, []).append(tk)
    for t in registry["tables"]:
        lines.append(f'"tbl:{t["table"]}" [label="TABLE\\n{t["table"]}\\n{t["rows"]} rows", fillcolor="#fef9c3"];')
        for src in t["raw_sources"]:
            if any(src == m["dataset_id"] for m in registry["manifest"]):
                lines.append(f'"raw:{src}" -> "tbl:{t["table"]}";')
        for c in t["consumers"]:
            label = f'{c["file"].split("/")[-1]}::{c["function"]}'
            lines.append(f'"fn:{label}" [label="{label}", fillcolor="#f1f5f9"];')
            lines.append(f'"tbl:{t["table"]}" -> "fn:{label}";')
        for tk in task_by_file.get(f'{t["table"]}.csv', []):
            lines.append(f'"mdl:{tk}" [label="MODEL\\n{tk}", fillcolor="#dcfce7"];')
            lines.append(f'"tbl:{t["table"]}" -> "mdl:{tk}";')
            lines.append(f'"mdl:{tk}" -> "ui:dev" [style=dashed];')
    lines.append('"ui:dev" [label="Streamlit\\nDeveloper Mode", fillcolor="#ede9fe"];')
    lines.append("}")
    return "\n".join(lines)


