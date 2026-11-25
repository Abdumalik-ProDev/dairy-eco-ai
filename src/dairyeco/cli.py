"""Unified Command-Line Interface (`dairyeco`) for DairyEco AI.

Usage:
  uv run dairyeco status       # Inspect processed datasets, model generalization & reports
  uv run dairyeco inventory    # Run Phase 0 raw file inventory & dataset manifest
  uv run dairyeco extract-pdfs # Run Phase 0 NIST & IFC PDF table extraction
  uv run dairyeco harmonize    # Run Phase 1 data harmonization
  uv run dairyeco train        # Run Phase 3 ML training & generalization audit
  uv run dairyeco audit        # Build ML Engineering Lab audit records (artifacts/audit/)
  uv run dairyeco report       # Generate Phase 4 reference scenario comparison report
"""

from __future__ import annotations

import argparse
import json
import sys

from dairyeco.config import ARTIFACTS_DIR, METADATA_DIR, PROCESSED_DIR, REPORTS_DIR


def _cmd_status() -> int:
    print("=== DairyEco AI System Status ===")
    manifest = METADATA_DIR / "dataset_manifest.csv"
    print(f"Phase 0 Manifest:    {'OK' if manifest.exists() else 'MISSING'} ({manifest})")

    for table in [
        "agribalyse_dairy_products.csv",
        "agribalyse_farm_gate_dairy.csv",
        "pdo_cheese_harmonized.csv",
        "uslci_curated_factors.csv",
        "packaging_impact_factors.csv",
    ]:
        p = PROCESSED_DIR / table
        print(f"Phase 1 Table:       {'OK' if p.exists() else 'MISSING'} ({table})")

    summary_path = ARTIFACTS_DIR / "ml_evaluation_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        t1 = summary["task1_agribalyse"]["champion_diagnostics"]
        t2a = summary["task2_pdo_cheese"]["champion_diagnostics"]
        t2b = summary["task2_pdo_cheese"]["regime_2b_full_lci_post_farm"]["champion_diagnostics"]
        t3g = summary["task3_simulator_surrogate"]["gwp_surrogate"]["champion_diagnostics"]
        t3c = summary["task3_simulator_surrogate"]["cost_surrogate"]["champion_diagnostics"]
        print("Phase 3 Champions:")
        for label, d in [
            ("Task 1 (AGRIBALYSE N=255)", t1),
            ("Task 2A (PDO Pre-LCI N=44)", t2a),
            ("Task 2B (PDO Full-LCI N=44)", t2b),
            ("Task 3A (GWP Surrogate N=1200)", t3g),
            ("Task 3B (Cost Surrogate N=1200)", t3c),
        ]:
            print(
                f"  - {label:32s}: {d['selected_model']} | "
                f"OOF R2={d['oof_r2']:.4f} | R2 Gap={d['r2_generalization_gap']:.4f} | "
                f"{d['fit_diagnosis']}"
            )
    else:
        print("Phase 3 Champions:   MISSING")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dairyeco",
        description="DairyEco AI CLI for data harmonization, ML evaluation, and scenario reporting.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Display dataset, model generalization, and artifact status")
    sub.add_parser("inventory", help="Run Phase 0 raw file inventory & dataset manifest")
    sub.add_parser("extract-pdfs", help="Run Phase 0 NIST & IFC PDF table extraction")
    sub.add_parser("harmonize", help="Run Phase 1 data harmonization")
    sub.add_parser("train", help="Run Phase 3 ML pipeline and generate model_cards.md")
    sub.add_parser("report", help="Generate Phase 4 scenario comparison report")
    sub.add_parser("audit", help="Build ML Engineering Lab audit records (artifacts/audit/)")

    args = parser.parse_args(argv)
    if args.command == "status":
        return _cmd_status()
    if args.command == "inventory":
        from dairyeco.data.inventory import main as inv_main

        inv_main()
        return 0
    if args.command == "extract-pdfs":
        from dairyeco.data.pdf_extraction import main as pdf_main

        pdf_main()
        return 0
    if args.command == "harmonize":
        from dairyeco.data.harmonize import run_phase1_harmonization

        paths = run_phase1_harmonization()
        for name, p in paths.items():
            print(f"[Phase 1] {name} -> {p}")
        return 0
    if args.command == "train":
        from dairyeco.models.pipeline import run_phase3_ml_pipeline

        run_phase3_ml_pipeline()
        print(f"[Phase 3] Model cards updated -> {REPORTS_DIR / 'model_cards.md'}")
        return 0
    if args.command == "audit":
        from dairyeco.audit.build import build_audit
        from dairyeco.config import AUDIT_DIR

        payload = build_audit()
        print(f"[Audit] {len(payload)} record sets written -> {AUDIT_DIR}")
        for tk, r in payload["readiness"].items():
            print(f"  - {tk}: readiness = {r['level']}")
        return 0
    if args.command == "report":
        from dairyeco.services.reporting import run_default_fluid_milk_comparison

        res = run_default_fluid_milk_comparison()
        out = REPORTS_DIR / "scenario_comparison_report.md"
        out.write_text(res["markdown_report"], encoding="utf-8")
        print(f"[Phase 4] Scenario report written -> {out}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
