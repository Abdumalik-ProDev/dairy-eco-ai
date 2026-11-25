"""Scenario orchestration and Markdown/JSON report generator for DairyEco AI.

Implements vision.md Section 10:
- Loads normalized dairy products from `data/processed/agribalyse_dairy_products.csv`.
- Generates reproducible scenario reports containing scenario definitions, functional unit,
  boundaries, sources/versions/geographies/years, assumptions, calculation results,
  Pareto status, sensitivity drivers, uncertainty, and limitations.
- Never displays a metric without its unit and provenance context.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from dairyeco.config import PROCESSED_DIR
from dairyeco.domain.models import (
    DairyCategory,
    DairyProductRecord,
    ScenarioAssumptions,
    ScenarioComparisonResult,
)
from dairyeco.lca.engine import get_default_factor_catalog
from dairyeco.optimization.pareto import (
    build_preset_package_configurations,
    compare_scenarios,
    run_one_at_a_time_sensitivity,
)


@lru_cache(maxsize=4)
def _load_dairy_products_cached(
    processed_dir_str: str,
    core_only: bool,
) -> tuple[DairyProductRecord, ...]:
    df = pd.read_csv(Path(processed_dir_str) / "agribalyse_dairy_products.csv")
    if core_only:
        df = df[df["is_core_dairy"] == True]
    records: list[DairyProductRecord] = []
    for row in df.to_dict(orient="records"):
        records.append(
            DairyProductRecord(
                product_id=str(row["product_id"]),
                code_agb=str(row["code_agb"]),
                name_fr=str(row["name_fr"]),
                name_en=str(row["name_en"]),
                category=DairyCategory(str(row["category"])),
                agribalyse_group=str(row["agribalyse_group_fr"]),
                agribalyse_subgroup=str(row["agribalyse_subgroup_fr"]),
                delivery_mode=str(row["delivery_mode"]),
                baseline_packaging_approach=str(row["baseline_packaging_approach"]),
                total_gwp_kgco2e_per_kg=float(row["total_gwp_kgco2e_per_kg"]),
                non_packaging_gwp_kgco2e_per_kg=float(row["non_packaging_gwp_kgco2e_per_kg"]),
                agriculture_gwp_kgco2e_per_kg=float(row["agriculture_gwp_kgco2e_per_kg"]),
                transformation_gwp_kgco2e_per_kg=float(row["transformation_gwp_kgco2e_per_kg"]),
                packaging_stage_gwp_kgco2e_per_kg=float(row["packaging_stage_gwp_kgco2e_per_kg"]),
                transport_gwp_kgco2e_per_kg=float(row["transport_gwp_kgco2e_per_kg"]),
                distribution_gwp_kgco2e_per_kg=float(row["distribution_gwp_kgco2e_per_kg"]),
                consumption_gwp_kgco2e_per_kg=float(row["consumption_gwp_kgco2e_per_kg"]),
                single_score_mpt_per_kg=float(row["single_score_mpt_per_kg"]),
                water_depletion_m3_per_kg=float(row["water_depletion_m3_per_kg"]),
                fossil_energy_mj_per_kg=float(row["fossil_energy_mj_per_kg"]),
                milk_yield_kg_milk_per_kg_product=(
                    float(row["milk_yield_kg_milk_per_kg_product"])
                    if pd.notna(row["milk_yield_kg_milk_per_kg_product"])
                    else None
                ),
                density_kg_per_l=float(row["density_kg_per_l"]),
            )
        )
    return tuple(records)


def load_dairy_products(
    processed_dir: Path = PROCESSED_DIR,
    core_only: bool = True,
) -> list[DairyProductRecord]:
    """Load harmonized AGRIBALYSE 3.2 dairy product records (cached in memory)."""
    return list(_load_dairy_products_cached(str(processed_dir.resolve()), core_only))


def generate_scenario_markdown_report(
    product: DairyProductRecord,
    assumptions: ScenarioAssumptions,
    comparisons: list[ScenarioComparisonResult],
    sensitivity_df: pd.DataFrame | None = None,
) -> str:
    """Format a complete, provenance-tagged Markdown scenario decision report."""
    fu = assumptions.functional_unit_saleable_kg
    curr = assumptions.currency

    lines: list[str] = [
        "# DairyEco AI — Scenario Decision-Support Report",
        "",
        "> [!WARNING]",
        "> **Prototype Epistemic Disclaimer:** This report combines published international LCA reference",
        "> data (`AGRIBALYSE 3.2`, `NIST/ANL 2024`, `USLCI`, `IFC 2007`) with scenario-level economic",
        "> and operational assumptions (`assumed` / `proxy`). Financial metrics are scenario estimates,",
        "> **not validated measurements of any Uzbek dairy company's actual savings or profitability**.",
        "",
        "## 1. Product, Functional Unit, and System Boundaries",
        "",
        f"- **Selected Dairy Product:** `{product.name_en}` (`{product.product_id}`, CIQUAL/AGB `{product.code_agb}`)",
        f"- **Category / Delivery Mode:** `{product.category}` / `{product.delivery_mode}`",
        f"- **Primary Functional Unit (FU):** **`{fu:,.1f} kg` of saleable dairy product delivered**",
        f"- **Annual Production Volume:** `{assumptions.annual_production_volume_kg:,.0f} kg / year`",
        (f"- **De-packaged Dairy Product Baseline Footprint (`AGRIBALYSE 3.2` with `Emballage` subtracted):** "
        f"`{product.non_packaging_gwp_kgco2e_per_kg:.3f} kg CO2e / kg` (`{product.non_packaging_gwp_kgco2e_per_kg * fu:,.1f} kg CO2e / FU`)"),
        (f"- **Original AGRIBALYSE `Emballage` Stage (`{product.baseline_packaging_approach}`):** "
        f"`{product.packaging_stage_gwp_kgco2e_per_kg:.3f} kg CO2e / kg` (subtracted before adding custom BOM packaging to prevent double counting)"),
        f"- **Electricity Grid Assumption:** `{assumptions.grid_carbon_intensity_kgco2e_per_kwh:.3f} kg CO2e / kWh` (`{assumptions.grid_region_label}`)",
        f"- **Economic Basis:** `{curr}` (Price year `{assumptions.price_year}`, discount rate `{assumptions.discount_rate*100:.1f}%`, horizon `{assumptions.project_lifetime_years} years`)",
        "",
        "---",
        "",
        f"## 2. Scenario Comparison Summary (per `{fu:,.0f} kg` Saleable Product)",
        "",
        f"| Scenario | Feasible | Pareto Optimal | Packaging Cost (`{curr}/FU`) | Total Op. Cost (`{curr}/FU`) | Packaging GWP (`kg CO2e/FU`) | Combined GWP (`kg CO2e/FU`) | Virgin Plastic (`kg/FU`) | Pkg Mass (`kg/FU`) | Payback (`yrs`) | NPV (`{curr}`) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for comp in comparisons:
        env = comp.environmental
        econ = comp.economic
        payback_str = (
            f"{comp.simple_payback_years:.2f}"
            if comp.simple_payback_years is not None
            else ("—" if comp.is_baseline else "No payback")
        )
        npv_str = (
            f"{comp.npv_usd:,.0f}" if comp.npv_usd is not None and not comp.is_baseline else "—"
        )
        lines.append(
            f"| **{comp.scenario_name}** | {'Yes' if comp.feasibility.is_feasible else 'NO'} | "
            f"{'★ Yes' if comp.is_pareto_optimal else 'No'} | "
            f"`{econ.total_packaging_attributable_cost_per_fu:,.2f}` | "
            f"`{econ.total_operating_cost_per_fu:,.2f}` | "
            f"`{env.packaging_system_total_gwp_kgco2e:,.2f}` | "
            f"`{env.combined_total_gwp_kgco2e:,.2f}` | "
            f"`{env.virgin_fossil_plastic_mass_kg:,.2f}` | "
            f"`{env.total_packaging_mass_kg:,.2f}` | "
            f"{payback_str} | {npv_str} |"
        )

    lines.extend(
        [
            "",
            "### Trade-Off & Feasibility Interpretation",
            "",
        ]
    )
    for comp in comparisons:
        lines.append(
            f"- **{comp.scenario_name} (`{comp.package_config_id}`):** {comp.tradeoff_summary} "
            f"(IFC benchmark check: `{comp.environmental.ifc_packaging_mass_benchmark_status}`)"
        )
        for v in comp.feasibility.violations:
            lines.append(f"  - **[INFEASIBLE VIOLATION]:** {v}")
        for w in comp.feasibility.warnings:
            lines.append(f"  - *[Warning]:* {w}")

    if sensitivity_df is not None and not sensitivity_df.empty:
        lines.extend(
            [
                "",
                "---",
                "",
                "## 3. One-at-a-Time Tornado Sensitivity Analysis (Baseline Configuration)",
                "",
                f"| Parameter | Low Cost (`{curr}/FU`) | High Cost (`{curr}/FU`) | Cost Swing (`{curr}/FU`) | Low Pkg GWP (`kg CO2e/FU`) | High Pkg GWP (`kg CO2e/FU`) | GWP Swing (`kg CO2e/FU`) |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for _, srow in sensitivity_df.iterrows():
            lines.append(
                f"| {srow['parameter_label']} | `{srow['low_param_cost_per_fu']:,.2f}` | "
                f"`{srow['high_param_cost_per_fu']:,.2f}` | **`{srow['cost_swing_usd_per_fu']:,.2f}`** | "
                f"`{srow['low_param_packaging_gwp_kgco2e_per_fu']:,.2f}` | "
                f"`{srow['high_param_packaging_gwp_kgco2e_per_fu']:,.2f}` | "
                f"**`{srow['gwp_swing_kgco2e_per_fu']:,.2f}`** |"
            )

    # Provenance section from baseline scenario
    if comparisons:
        lines.extend(
            [
                "",
                "---",
                "",
                "## 4. Data Provenance & Epistemic Classification",
                "",
                "| Source Dataset ID | Record ID | Source Type | Geography | Year | LCIA Method | Notes |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        seen_keys: set[tuple[str, str]] = set()
        for comp in comparisons:
            for p in comp.environmental.provenance_records:
                key = (p.source_dataset_id, p.source_record_id)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                lines.append(
                    f"| `{p.source_dataset_id}` | `{p.source_record_id}` | `{p.source_type}` | "
                    f"`{p.geography}` | `{p.reference_year}` | `{p.lcia_method}` | {p.notes} |"
                )

    return "\n".join(lines) + "\n"


def run_default_fluid_milk_comparison(
    processed_dir: Path = PROCESSED_DIR,
) -> dict[str, Any]:
    """Run a complete reference comparison on semi-skimmed pasteurized milk across 6 package formats."""
    products = load_dairy_products(processed_dir)
    # Pick pasteurized semi-skimmed milk (or first fluid_milk product)
    milk_products = [p for p in products if p.category == DairyCategory.FLUID_MILK]
    selected = next(
        (p for p in milk_products if "pasteur" in p.name_en.lower() and "semi" in p.name_en.lower()),
        milk_products[0],
    )
    presets = build_preset_package_configurations()
    baseline = presets["PKG-HDPE-BOTTLE-1L"]
    alternatives = [
        presets["PKG-PET-BOTTLE-1L"],
        presets["PKG-RPET50-BOTTLE-1L"],
        presets["PKG-CARTON-LPB-1L"],
        presets["PKG-GLASS-SINGLE-1L"],
        presets["PKG-GLASS-REUSE-1L"],
        presets["PKG-POUCH-LDPE-1L"],
    ]
    assumptions = ScenarioAssumptions(
        incremental_capex_usd=45_000.0,
        installation_commissioning_usd=5_000.0,
    )
    catalog = get_default_factor_catalog(processed_dir)
    comparisons = compare_scenarios(
        product=selected,
        baseline_config=baseline,
        alternative_configs=alternatives,
        assumptions=assumptions,
        catalog=catalog,
    )
    sens_df = run_one_at_a_time_sensitivity(selected, baseline, assumptions, catalog=catalog)
    md_report = generate_scenario_markdown_report(selected, assumptions, comparisons, sens_df)
    return {
        "product": selected,
        "assumptions": assumptions,
        "comparisons": comparisons,
        "sensitivity_df": sens_df,
        "markdown_report": md_report,
    }
