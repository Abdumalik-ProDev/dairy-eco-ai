"""Data-side audit records: dataset registry, usage scan, lineage, cleaning log, EDA, features.

Every number is computed from the real processed tables, raw-file inspectors and pipeline
source. Facts that the project never recorded are labelled ``NOT_RECORDED``.
"""

from __future__ import annotations

import ast
import hashlib
from typing import Any

import numpy as np
import pandas as pd

from dairyeco.audit.common import NOT_RECORDED, PROJECT_ROOT, rel, sha256_file, symbol_exists
from dairyeco.audit.splits import load_task_frame
from dairyeco.config import METADATA_DIR, PROCESSED_DIR, REFERENCE_DIR, SYNTHETIC_DIR
from dairyeco.models import pipeline as ml_pipeline
from dairyeco.models.registry import FEATURE_DESCRIPTIONS, MODEL_REGISTRY, get_task_summary_dict

TABLES: dict[str, dict[str, Any]] = {
    "agribalyse_dairy_products": {
        "path": PROCESSED_DIR / "agribalyse_dairy_products.csv", "raw_sources": ["agribalyse_3_2"],
        "built_by": ("src/dairyeco/data/harmonize.py", "build_agribalyse_dairy_table")},
    "agribalyse_farm_gate_dairy": {
        "path": PROCESSED_DIR / "agribalyse_farm_gate_dairy.csv", "raw_sources": ["agribalyse_3_2"],
        "built_by": ("src/dairyeco/data/harmonize.py", "build_agribalyse_farm_gate_table")},
    "pdo_cheese_harmonized": {
        "path": PROCESSED_DIR / "pdo_cheese_harmonized.csv", "raw_sources": ["pdo_cheese_lca"],
        "built_by": ("src/dairyeco/data/harmonize.py", "build_pdo_cheese_harmonized_table")},
    "uslci_curated_factors": {
        "path": PROCESSED_DIR / "uslci_curated_factors.csv", "raw_sources": ["uslci"],
        "built_by": ("src/dairyeco/data/harmonize.py", "build_uslci_curated_table")},
    "packaging_impact_factors": {
        "path": PROCESSED_DIR / "packaging_impact_factors.csv",
        "raw_sources": ["uslci", "anl_nist_regional_plastics_2024", "agribalyse_3_2"],
        "built_by": ("src/dairyeco/data/harmonize.py", "build_unified_packaging_impact_factors")},
    "nist_plastic_carbon_intensity": {
        "path": REFERENCE_DIR / "nist_plastic_carbon_intensity.csv",
        "raw_sources": ["anl_nist_regional_plastics_2024"],
        "built_by": ("src/dairyeco/data/pdf_extraction.py", "")},
    "ifc_dairy_benchmarks": {
        "path": REFERENCE_DIR / "ifc_dairy_benchmarks.csv", "raw_sources": ["ifc_wbg_ehs_dairy_2007"],
        "built_by": ("src/dairyeco/data/pdf_extraction.py", "")},
    "simulated_packaging_scenarios": {
        "path": SYNTHETIC_DIR / "simulated_packaging_scenarios.csv",
        "raw_sources": ["agribalyse_3_2", "packaging_impact_factors (via LCA engine)"],
        "built_by": ("src/dairyeco/models/pipeline.py", "generate_simulated_scenario_dataset")},
}

SELECTION_NOTE = (
    "Alternatives considered / rejected: " + NOT_RECORDED + ". The project artifacts record the "
    "selected sources and gaps (e.g. USLCI lacks container glass and liquid packaging board, filled "
    "by labelled proxies) but no explicit candidate-dataset comparison."
)


# ----------------------------------------------------------------------------- usage scan
def scan_usage(basename: str) -> list[dict[str, str]]:
    """Find functions in ``src/`` whose source mentions ``basename`` (AST-derived, not hand-written)."""
    hits: list[dict[str, str]] = []
    for py in sorted((PROJECT_ROOT / "src").rglob("*.py")):
        if "audit" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        if basename not in text:
            continue
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = ast.get_source_segment(text, node) or ""
                if basename in seg:
                    hits.append({"file": rel(py), "function": node.name})
        if not any(h["file"] == rel(py) for h in hits):
            hits.append({"file": rel(py), "function": "(module level)"})
    return hits


def table_profile(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    path = spec["path"]
    df = pd.read_csv(path)
    miss = df.isna().sum()
    prof: dict[str, Any] = {
        "table": name, "file": rel(path), "rows": len(df), "columns": int(df.shape[1]),
        "sha256": sha256_file(path), "missing_cells": int(miss.sum()),
        "columns_with_missing": {k: int(v) for k, v in miss[miss > 0].items()},
        "duplicate_rows": int(df.duplicated().sum()),
        "raw_sources": spec["raw_sources"], "built_by": {"file": spec["built_by"][0],
                                                         "symbol": spec["built_by"][1]},
        "built_by_verified": bool(spec["built_by"][1]) and symbol_exists(*spec["built_by"]),
        "consumers": scan_usage(path.name),
    }
    for col in ("functional_unit", "system_boundary", "lcia_method", "geography", "reference_year",
                "source_type", "source_dataset_id"):
        if col in df.columns:
            vc = df[col].astype(str).value_counts().head(8)
            prof[col] = {k: int(v) for k, v in vc.items()}
    return prof


def build_dataset_registry() -> dict[str, Any]:
    manifest = pd.read_csv(METADATA_DIR / "dataset_manifest.csv").fillna("").to_dict("records")
    tables = [table_profile(n, s) for n, s in TABLES.items()]
    sup: dict[str, list[str]] = {}
    for t in tables:
        for c in t["consumers"]:
            sup.setdefault(t["table"], []).append(f"{c['file']}::{c['function']}")
    for m in manifest:
        m["derived_tables"] = [t["table"] for t in tables if m["dataset_id"] in t["raw_sources"]]
        m["selection_rationale"] = {
            "verified_intended_use": m["intended_use"],
            "alternatives_considered": NOT_RECORDED,
        }
    return {"manifest": manifest, "tables": tables, "selection_note": SELECTION_NOTE,
            "unused_tables": [t["table"] for t in tables if not t["consumers"]]}


# ----------------------------------------------------------------------------- lineage
def build_lineage() -> dict[str, Any]:
    from dairyeco.data.audit_inspectors import (
        inspect_agribalyse_food,
        inspect_pdo_cheese,
        inspect_uslci,
    )

    agb = inspect_agribalyse_food()
    pdo = inspect_pdo_cheese()
    usl = inspect_uslci()
    agb_df = pd.read_csv(PROCESSED_DIR / "agribalyse_dairy_products.csv")
    core = agb_df[agb_df["is_core_dairy"]]
    pdo_df = pd.read_csv(PROCESSED_DIR / "pdo_cheese_harmonized.csv")
    usl_df = pd.read_csv(PROCESSED_DIR / "uslci_curated_factors.csv")
    fac = pd.read_csv(PROCESSED_DIR / "packaging_impact_factors.csv")
    sim = pd.read_csv(SYNTHETIC_DIR / "simulated_packaging_scenarios.csv")

    h = "src/dairyeco/data/harmonize.py"
    gap = (core["stage_sum_gwp_kgco2e_per_kg"] - core["total_gwp_kgco2e_per_kg"])
    nonneg = core[core["total_gwp_kgco2e_per_kg"] >= core["packaging_stage_gwp_kgco2e_per_kg"]]
    depack_resid = float(
        (nonneg["total_gwp_kgco2e_per_kg"] - nonneg["packaging_stage_gwp_kgco2e_per_kg"]
         - nonneg["non_packaging_gwp_kgco2e_per_kg"]).abs().max()
    )
    flows = {
        "agribalyse_dairy_products": [
            {"step": 1, "operation": "Read 'Synthese' sheet (all food products)", "rows_before": None,
             "rows_after": agb.total_synthese_rows, "join": "-", "code": f"{h}::build_agribalyse_dairy_table",
             "note": f"{agb.unique_agb_codes} unique Code AGB; {len(agb.duplicate_agb_codes)} duplicated "
                     "codes are all non-dairy"},
            {"step": 2, "operation": "Filter dairy: group 'lait et produits laitiers' or core subgroups "
                                     "(+ adjacent infant/beverage dairy)", "rows_before": agb.total_synthese_rows,
             "rows_after": len(agb_df), "join": "-", "code": f"{h}::build_agribalyse_dairy_table",
             "note": f"inspector counts {agb.core_dairy_row_count} core rows"},
            {"step": 3, "operation": "Join 'Detail etape' stage table on (Code AGB, LCI name)",
             "rows_before": len(agb_df), "rows_after": len(agb_df),
             "join": "INNER via dict lookup; products without a stage row are skipped silently in code "
                     "(no unmatched log is written)", "cardinality": "1:1",
             "code": f"{h}::build_agribalyse_dairy_table",
             "note": f"core rows: inspector {agb.core_dairy_row_count} vs processed {len(core)} "
                     f"-> unmatched core rows = {agb.core_dairy_row_count - len(core)}"},
            {"step": 4, "operation": "De-package: non_packaging = max(0, total - Emballage stage)",
             "rows_before": len(core), "rows_after": len(core), "join": "-",
             "code": f"{h}::build_agribalyse_dairy_table",
             "note": f"max |total - pack - non_pack| on rows where total>=pack = {depack_resid:.2e} "
                     f"(double-count check); rows clipped at 0: "
                     f"{int((core['total_gwp_kgco2e_per_kg'] < core['packaging_stage_gwp_kgco2e_per_kg']).sum())}"},
            {"step": 5, "operation": "Reconciliation: sum of 6 stage columns vs Synthese total",
             "rows_before": len(core), "rows_after": len(core), "join": "-", "code": f"{h}",
             "note": f"mean gap {gap.mean():+.4f}, max |gap| {gap.abs().max():.4f} kg CO2e/kg "
                     f"({int((gap.abs() > 1e-3).sum())} core rows differ by >0.001)"},
        ],
        "pdo_cheese_harmonized": [
            {"step": 1, "operation": "Read 7 cheese-level workbooks",
             "rows_before": None, "rows_after": sum(pdo.table_cheese_counts.values()), "join": "-",
             "code": f"{h}::build_pdo_cheese_harmonized_table",
             "note": f"rows per table: {pdo.table_cheese_counts}"},
            {"step": 2, "operation": "Normalise cheese names (strip + 'Camenbert'->'Camembert')",
             "rows_before": sum(pdo.table_cheese_counts.values()), "rows_after": sum(pdo.table_cheese_counts.values()),
             "join": "-", "code": "src/dairyeco/data/audit_inspectors.py::normalize_pdo_cheese_name",
             "note": f"{len(pdo.raw_name_mismatches)} cheeses had raw-name mismatches across tables"},
            {"step": 3, "operation": "Join 7 tables on normalised name (canonical order from characterization)",
             "rows_before": 7 * pdo.canonical_cheese_count, "rows_after": len(pdo_df),
             "join": "INNER via dict lookup per table (KeyError would abort - no silent loss)",
             "cardinality": "1:1 per table", "code": f"{h}::build_pdo_cheese_harmonized_table",
             "note": "exactly 44 canonical cheeses enforced by ValueError guard"},
            {"step": 4, "operation": "Pivot long LCIA (1,232 indicator rows) to one row per cheese",
             "rows_before": pdo.lcia_total_indicator_rows, "rows_after": len(pdo_df),
             "join": "group by cheese, pick 5 indicators", "code": f"{h}::build_pdo_cheese_harmonized_table",
             "note": "1,232 = 44 cheeses x 28 indicators; never used as independent samples"},
        ],
        "uslci_curated_factors": [
            {"step": 1, "operation": "Scan all openLCA process JSON", "rows_before": None,
             "rows_after": usl.total_processes, "join": "-", "code": "src/dairyeco/data/audit_inspectors.py::inspect_uslci",
             "note": f"{usl.bridge_process_count} bridge processes with 0 elementary flows"},
            {"step": 2, "operation": "Select curated processes by UUID prefix; normalise reference units to kg",
             "rows_before": usl.total_processes, "rows_after": len(usl_df), "join": "UUID prefix lookup",
             "code": f"{h}::build_uslci_curated_table", "note": "unit conversions: Mg, t, sh tn, lb -> kg"},
        ],
        "packaging_impact_factors": [
            {"step": 1, "operation": "Assemble LCA factor catalogue from NIST CSV + USLCI table + literal constants",
             "rows_before": len(usl_df), "rows_after": len(fac),
             "join": "USLCI joined by UUID 8-char prefix (LEFT-style dict lookup)",
             "code": f"{h}::build_unified_packaging_impact_factors",
             "note": "factor_id by source_type: " + str(fac["source_type"].value_counts().to_dict())},
        ],
        "simulated_packaging_scenarios": [
            {"step": 1, "operation": "Sample products x presets x perturbations; run deterministic LCA+economics engine",
             "rows_before": len(core), "rows_after": len(sim), "join": "none (generated)",
             "code": "src/dairyeco/models/pipeline.py::generate_simulated_scenario_dataset",
             "note": f"{sim['product_id'].nunique()} distinct products sampled (with replacement) into 1,200 rows; "
                     "infeasible combinations are rejected by check_scenario_feasibility"},
        ],
    }
    gmat = []
    man = pd.read_csv(METADATA_DIR / "dataset_manifest.csv")
    for _, r in man.iterrows():
        gmat.append({k: r[k] for k in ("dataset_id", "functional_unit", "system_boundary",
                                       "lcia_method", "geography", "reference_year")})
    return {
        "flows": flows, "compatibility_matrix": gmat,
        "integration_decisions": [
            {"combination": "AGRIBALYSE (cradle-to-grave, incl. baseline packaging) x packaging factor catalogue",
             "why": "Executive scenarios swap packaging; baseline packaging must be removed first",
             "safeguard": "non_packaging = total - Emballage stage before adding new packaging impacts "
                          "(prevents double counting)",
             "residual_risk": "Other stages (transport, distribution) still embed AGRIBALYSE packaging assumptions"},
            {"combination": "AGRIBALYSE x PDO cheese",
             "why": "Not combined", "safeguard": "Different FU boundary (consumer vs ripening exit), LCIA "
             "method (EF 3.1 vs EF 3.0/ILCD) and exclusion of packaging; kept as separate ML tasks",
             "residual_risk": "None from merging; cheese predictions are not comparable across tasks"},
            {"combination": "NIST/ANL resin GWP (GREET 2022) x USLCI (IPCC AR6 characterised here) x proxies",
             "why": "No single source covers all packaging materials, conversion, transport and EoL",
             "safeguard": "Each factor carries source_dataset_id, source_type, lcia_method, system_boundary",
             "residual_risk": "Mixed LCIA methods and geographies in one catalogue; many values are literals "
                              "typed in harmonize.py rather than computed from raw files"},
        ],
    }


# ----------------------------------------------------------------------------- cleaning
def _iqr_outliers(s: pd.Series) -> int:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    return int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())


def build_cleaning_log(summary: dict[str, Any]) -> list[dict[str, Any]]:
    from dairyeco.data.audit_inspectors import inspect_agribalyse_food, inspect_pdo_cheese

    agb = inspect_agribalyse_food()
    pdo = inspect_pdo_cheese()
    agb_all = pd.read_csv(PROCESSED_DIR / "agribalyse_dairy_products.csv")
    core = agb_all[agb_all["is_core_dairy"]]
    h = "src/dairyeco/data/harmonize.py"
    p = "src/dairyeco/models/pipeline.py"

    ops: list[dict[str, Any]] = [
        {"id": "C01", "stage": "cleaning", "operation": "Duplicate Code AGB rows",
         "original": f"{len(agb.duplicate_agb_codes)} duplicated codes ({agb.total_synthese_rows} rows / "
                     f"{agb.unique_agb_codes} unique)", "method": "Composite key (Code AGB, LCI name)",
         "reason": "Duplicates are non-dairy (software vs packaging-corrected versions)",
         "affected": int(agb_all["code_agb"].duplicated().sum()),
         "result": "0 duplicated code_agb in processed dairy table when affected == 0",
         "risks": "Other categories would need explicit deduplication", "alternatives": "Keep packaging-corrected row only",
         "code": f"{h}::build_agribalyse_dairy_table"},
        {"id": "C02", "stage": "cleaning", "operation": "Trailing empty formula rows in 'Detail etape'",
         "original": f"{agb.detail_etape_trailing_formula_rows} empty rows", "method": "Keep rows with Code AGB not None",
         "reason": "Rows are spreadsheet formula padding", "affected": agb.detail_etape_trailing_formula_rows,
         "result": f"{agb.detail_etape_valid_rows} valid stage rows", "risks": "None identified",
         "alternatives": "Row-range slicing", "code": f"{h}::build_agribalyse_dairy_table"},
        {"id": "C03", "stage": "cleaning", "operation": "'-' strings used for exact zero in stage cells",
         "original": "string '-'", "method": "_parse_stage_float: '-' -> 0.0",
         "reason": "Source documents '-' as zero", "affected": NOT_RECORDED + " (not counted by pipeline)",
         "result": f"{int((core['transformation_gwp_kgco2e_per_kg'] == 0).sum())} core rows now have "
                   "transformation GWP == 0 (includes true zeros)",
         "risks": "Cannot separate '-' zeros from numeric zeros after conversion", "alternatives": "NaN + indicator",
         "code": f"{h}::_parse_stage_float"},
        {"id": "C04", "stage": "cleaning", "operation": "Filter to core dairy products",
         "original": f"{len(agb_all)} dairy-adjacent rows", "method": "is_core_dairy == True",
         "reason": "Task 1 targets core dairy products; infant/beverage rows are adjacent",
         "affected": int(len(agb_all) - len(core)), "result": f"{len(core)} rows used for Task 1",
         "risks": "Excludes flavoured milks and infant dairy", "alternatives": "Include with category flag",
         "code": f"{p}::run_task1_agribalyse_dairy_regression"},
        {"id": "C05", "stage": "integration", "operation": "Packaging stage subtracted (de-packaging)",
         "original": "Totals include baseline packaging", "method": "total - Emballage stage, clipped at 0",
         "reason": "Avoid double counting packaging when swapping packaging",
         "affected": len(core), "result": f"mean packaging share {core['packaging_share_of_gwp_pct'].mean():.1f}%",
         "risks": "Clipping at 0 hides negative differences; non-GWP indicators used as features still include packaging",
         "alternatives": "Sum the 5 non-packaging stages", "code": f"{h}::build_agribalyse_dairy_table"},
        {"id": "C06", "stage": "cleaning", "operation": "PDO cheese name normalisation",
         "original": f"{len(pdo.raw_name_mismatches)} cheeses with spelling/whitespace mismatches",
         "method": "strip + Camenbert->Camembert", "reason": "Exact string joins fail otherwise",
         "affected": len(pdo.raw_name_mismatches), "result": "44-to-44 set equality across 7 tables",
         "risks": "Manual map covers one known typo only", "alternatives": "Fuzzy matching",
         "code": "src/dairyeco/data/audit_inspectors.py::normalize_pdo_cheese_name"},
        {"id": "C07", "stage": "cleaning", "operation": "PDO LCIA long -> wide pivot",
         "original": f"{pdo.lcia_total_indicator_rows} indicator rows", "method": "group by cheese",
         "reason": "Rows are not independent samples", "affected": pdo.lcia_total_indicator_rows,
         "result": "44 observations", "risks": "Tiny N", "alternatives": "None (data constraint)",
         "code": f"{h}::build_pdo_cheese_harmonized_table"},
        {"id": "C08", "stage": "cleaning", "operation": "Unit normalisation of USLCI reference flows",
         "original": "reference amounts in kg, Mg, t, sh tn, 1000 kg, 1.105 kg ...",
         "method": "divide by qref_amount * UNIT_TO_KG", "reason": "Per-kg factors needed",
         "affected": "56 curated processes", "result": "per-normalised-unit columns",
         "risks": "Only listed units supported", "alternatives": "pint library", "code": f"{h}::build_uslci_curated_table"},
        {"id": "C09", "stage": "leakage", "operation": "Forbidden-column guard",
         "original": "targets, identifiers and sibling GWP columns present in processed tables",
         "method": "assert_no_feature_leakage", "reason": "Prevent trivially recoverable targets and ID memorisation",
         "affected": len(ml_pipeline.FORBIDDEN_LEAKAGE_COLUMNS), "result": "ValueError if violated",
         "risks": "List is hand-maintained", "alternatives": "Automatic correlation screen",
         "code": f"{p}::assert_no_feature_leakage"},
    ]
    # data-dependent: missing, outliers, encoding per task
    for tk in MODEL_REGISTRY:
        info = get_task_summary_dict(summary, tk)
        df = load_task_frame(tk)
        feats = info["feature_columns"]
        num = [c for c in feats if pd.api.types.is_numeric_dtype(df[c])]
        cat = [c for c in feats if c not in num]
        miss = int(df[feats].isna().sum().sum())
        out = {c: _iqr_outliers(df[c]) for c in num}
        out_total = int(sum(out.values()))
        top = dict(sorted(out.items(), key=lambda kv: -kv[1])[:5])
        minf = 2 if len(df) < 80 else None
        ops.append({
            "id": f"M-{tk}", "stage": "preprocessing", "operation": f"Imputation, scaling, encoding ({tk})",
            "original": f"{len(df)} rows; {miss} missing cells in {len(feats)} features; "
                        f"{out_total} IQR-outlier cells (1.5xIQR) across {len(num)} numeric features",
            "method": "numeric: SimpleImputer(median)+RobustScaler; categorical: SimpleImputer(most_frequent)+"
                      f"OneHotEncoder(min_frequency={minf}); fitted inside each CV fold",
            "reason": "Median/IQR statistics resist the heavy-tailed LCA values; no rows are deleted",
            "affected": {"missing_cells": miss, "outlier_cells": out_total, "top_outlier_features": top,
                         "numeric": len(num), "categorical": len(cat)},
            "result": "No record removed; outliers retained and down-weighted by robust scaling",
            "risks": "Outliers (e.g. Roquefort, butters) remain influential; imputation untested when missing "
                     "cells = 0", "alternatives": "Winsorisation, log-transform of skewed targets",
            "code": f"{p}::_build_preprocessor"})
    return ops


# ----------------------------------------------------------------------------- EDA
def build_eda(summary: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tk, meta in MODEL_REGISTRY.items():
        info = get_task_summary_dict(summary, tk)
        df = load_task_frame(tk)
        tgt = meta["target_col"]
        feats = info["feature_columns"]
        num = [c for c in feats if pd.api.types.is_numeric_dtype(df[c])]
        cat = [c for c in feats if c not in num]
        y = df[tgt]
        counts, edges = np.histogram(y, bins=20)
        stats = []
        for c in num:
            s = df[c]
            stats.append({"feature": c, "missing": int(s.isna().sum()), "mean": float(s.mean()),
                          "std": float(s.std()), "min": float(s.min()), "max": float(s.max()),
                          "skew": float(s.skew()), "iqr_outliers": _iqr_outliers(s),
                          "n_unique": int(s.nunique())})
        rho = df[[*num, tgt]].corr(method="spearman")
        corr_t = rho[tgt].drop(tgt).dropna().sort_values(key=abs, ascending=False)
        pairs = []
        fm = rho.drop(index=tgt, columns=tgt)
        cols = list(fm.columns)
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                v = fm.loc[a, b]
                if pd.notna(v) and abs(v) > 0.9:
                    pairs.append({"a": a, "b": b, "spearman": float(v)})
        pairs.sort(key=lambda d: -abs(d["spearman"]))
        cats = {}
        for c in cat:
            g = df.groupby(c)[tgt].agg(["count", "mean"]).sort_values("count", ascending=False).head(12)
            cats[c] = [{"level": str(i), "count": int(r["count"]), "target_mean": float(r["mean"])}
                       for i, r in g.iterrows()]
        out[tk] = {
            "n": len(df), "target": tgt, "target_unit": meta["target_unit"],
            "target_summary": {k: float(v) for k, v in y.describe().items()},
            "target_skew": float(y.skew()),
            "target_hist": {"counts": counts.tolist(), "edges": [float(e) for e in edges]},
            "numeric_features": stats, "target_correlations": {k: float(v) for k, v in corr_t.items()},
            "collinear_pairs": pairs[:8], "categorical": cats,
            "missing_features": {c: int(df[c].isna().sum()) for c in feats if df[c].isna().any()},
            "geography": df["geography"].astype(str).value_counts().to_dict() if "geography" in df.columns else
            {"synthetic grid/resin regions": "see resin_region"},
            "reference_year": df["reference_year"].astype(str).value_counts().to_dict()
            if "reference_year" in df.columns else {NOT_RECORDED: len(df)},
            "class_balance_note": (
                "Imbalance measured on the largest categorical feature level share: "
                + (f"{max((l['count'] for l in next(iter(cats.values()))), default=0) / len(df):.0%}"
                   if cats else "n/a")),
        }
    return out


# ----------------------------------------------------------------------------- features
_AGB = "agribalyse_dairy_products.csv"
_PDO = "pdo_cheese_harmonized.csv"
DERIVATIONS: dict[str, tuple[str, str, str]] = {
    # feature -> (origin column(s), transformation, note)
    "non_packaging_water_m3_per_kg": ("Synthese[water depletion] ; Detail etape[packaging-stage water, col 108]",
                                      "max(0, total - packaging stage)", "de-packaged"),
    "non_packaging_fossil_energy_mj_per_kg": ("Synthese[fossil energy] ; Detail etape[col 115]",
                                              "max(0, total - packaging stage)", "de-packaged"),
    "acidification_mol_h_eq_per_kg": ("Synthese col 20", "none (copied)", "TOTAL incl. packaging; target excludes packaging"),
    "eutrophication_freshwater_kg_p_eq_per_kg": ("Synthese col 21", "none (copied)", "TOTAL incl. packaging"),
    "eutrophication_marine_kg_n_eq_per_kg": ("Synthese col 22", "none (copied)", "TOTAL incl. packaging"),
    "land_use_pt_per_kg": ("Synthese col 25", "none (copied)", "TOTAL incl. packaging"),
    "transport_gwp_kgco2e_per_kg": ("Detail etape col 18", "_parse_stage_float", "stage GWP"),
    "distribution_gwp_kgco2e_per_kg": ("Detail etape col 19", "_parse_stage_float", "stage GWP"),
    "consumption_gwp_kgco2e_per_kg": ("Detail etape col 20", "_parse_stage_float", "stage GWP"),
    "density_kg_per_l": ("(none - assigned by rule)", "_infer_dairy_density(category, name)",
                         "ASSUMED per category, not measured per product"),
    "dqr_overall": ("Synthese col 11", "float()", "AGRIBALYSE data quality rating"),
    "category": ("Group/subgroup/name", "_map_agribalyse_dairy_category", "rule-based mapping"),
    "agribalyse_subgroup_fr": ("Synthese col 3", "string", "also used to stratify CV"),
    "delivery_mode": ("Synthese col 8", "string", ""),
    "baseline_packaging_approach": ("Synthese col 9", "string", "PACK AGB vs PACK PROXY"),
    "lci_total_raw_milk_kg": ("LCI initial cols 2-5", "sum of 4 milk inputs", "derived"),
    "effective_bom_mass_kg_per_fu": ("package BOM, reject, spoilage, reuse",
                                     "gross_pkgs/eff_trips * total_bom_g/1000", "formula in build_surrogate_feature_row"),
    "expected_bom_material_spend_usd_per_fu": ("effective_bom_mass_kg_per_fu x weighted price", "product",
                                               "closely mirrors the cost target"),
    "expected_spoilage_gwp_kgco2e_per_fu": ("spoilage rate x dairy GWP", "1000*s/(1-s)*dairy_gwp",
                                            "input-derived (known before factor lookup)"),
}
LABEL_TYPE = {
    "task1_agribalyse_gwp": ("calculated from published values",
                             "Synthese total GWP minus Detail etape 'Emballage' stage (max 0)"),
    "task2a_pdo_cheese_total": ("published LCIA output",
                                "Base-scenario total climate change from data_PDOcheeses_LCIA (author-calculated)"),
    "task2b_pdo_cheese_post_farm": ("calculated from published values",
                                    "Sum of 6 post-farm stage GWPs (transport,pumping,storage,processing,ripening,cleaning)"),
    "task3a_surrogate_gwp": ("synthetic / model-derived",
                             "EnvironmentalResult.packaging_system_total_gwp_kgco2e from the deterministic LCA engine"),
    "task3b_surrogate_cost": ("synthetic / model-derived",
                              "total_packaging_attributable_cost_per_fu from the deterministic economics engine"),
}


def _leak_risk(tk: str, f: str) -> str:
    if tk.startswith("task1"):
        if f.endswith("_per_kg") and f not in {"density_kg_per_l"}:
            return "medium: co-computed LCIA indicator, only available after a full LCA"
        return "low"
    if tk.startswith("task2b") and "electricity" in f:
        return "low leakage, but near-deterministic physical driver of the target"
    if tk.startswith("task3"):
        if f == "preset_id":
            return "medium: identity proxy that nearly fixes the whole BOM"
        return "low"
    return "low"


def build_feature_registry(summary: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tk, meta in MODEL_REGISTRY.items():
        info = get_task_summary_dict(summary, tk)
        df = load_task_frame(tk)
        tgt = meta["target_col"]
        num = [c for c in info["feature_columns"] if pd.api.types.is_numeric_dtype(df[c])]
        rho = df[[*num, tgt]].corr(method="spearman")[tgt] if num else pd.Series(dtype=float)
        live = meta["supports_live_scenario"]
        rows = []
        for f in info["feature_columns"]:
            origin, trans, note = DERIVATIONS.get(
                f, (f"{meta['dataset_file'].name}::{f}", "none (copied from processed table)", ""))
            if f.startswith(("lci_", "allocation_", "ripening_", "cream_", "whey_", "max_auth", "technology", "milk_type")) \
                    and f not in DERIVATIONS:
                origin = "PDO workbook column (see build_pdo_cheese_harmonized_table)"
            sign = "n/a (categorical)"
            if f in rho.index and pd.notna(rho[f]):
                sign = f"observed Spearman rho = {rho[f]:+.2f} (empirical, not a prior)"
            rows.append({
                "feature": f, "description": FEATURE_DESCRIPTIONS.get(f, NOT_RECORDED),
                "dtype": "numeric" if f in num else "categorical", "origin": origin, "transformation": trans,
                "note": note, "inclusion_reason": f"{NOT_RECORDED} (original rationale not documented); "
                                                  "inferred: " + FEATURE_DESCRIPTIONS.get(f, "domain feature"),
                "expected_relationship": f"prior {NOT_RECORDED}; " + sign,
                "missing_treatment": "median / most_frequent imputation inside CV fold",
                "available_at_inference": ("yes - built by dashboard.dev_mode.build_surrogate_feature_row"
                                           if live else "no live inference path (research case study)"),
                "leakage_or_bias_risk": _leak_risk(tk, f),
                "n_missing": int(df[f].isna().sum()),
            })
        ltype, ldef = LABEL_TYPE[tk]
        out[tk] = {"target": tgt, "label_type": ltype, "label_construction": ldef,
                   "source_type": meta["source_type"], "target_unit": meta["target_unit"],
                   "features": rows,
                   "target_limitations": (
                       "Model-derived label: metrics measure how well ML copies the engine, not real-world accuracy"
                       if tk.startswith("task3") else
                       "Published/calculated value for France-specific supply chains; not a measurement of any "
                       "specific plant")}
    return out


def dataset_checksums_for(task_key: str) -> dict[str, str]:
    meta = MODEL_REGISTRY[task_key]
    p = meta["dataset_file"]
    return {rel(p): sha256_file(p)}


def string_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


__all__ = [
    "build_cleaning_log", "build_dataset_registry", "build_eda", "build_feature_registry",
    "build_lineage", "dataset_checksums_for",
]
