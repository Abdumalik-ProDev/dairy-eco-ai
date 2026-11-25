"""Preset BOM packaging library, multi-scenario comparator, Pareto frontier, and sensitivity analysis."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from dairyeco.domain.models import (
    ConversionProcess,
    DairyCategory,
    DairyProductRecord,
    DataSourceType,
    MaterialFamily,
    PackageComponentBOM,
    PackageConfiguration,
    PackageFormat,
    ReuseParameters,
    ScenarioAssumptions,
    ScenarioComparisonResult,
)
from dairyeco.economics.engine import (
    compute_capital_and_tradeoff_metrics,
    evaluate_economics,
)
from dairyeco.lca.engine import (
    FactorCatalog,
    check_scenario_feasibility,
    evaluate_environmental_lca,
    get_default_factor_catalog,
)


def _bom(
    name: str,
    mat: MaterialFamily,
    mass_g: float,
    price: float,
    conv: ConversionProcess = ConversionProcess.NONE,
    rec: float = 0.0,
    eol: tuple[float, float, float] = (0.20, 0.20, 0.60),
    sec: bool = False,
) -> PackageComponentBOM:
    """Concise builder for a validated PackageComponentBOM."""
    return PackageComponentBOM(
        component_name=name,
        material_family=mat,
        mass_g_per_package=mass_g,
        recycled_content_fraction=rec,
        conversion_process=conv,
        unit_price_usd_per_kg=price,
        eol_recycling_fraction=eol[0],
        eol_incineration_fraction=eol[1],
        eol_landfill_fraction=eol[2],
        is_secondary_or_tertiary=sec,
    )


def build_preset_package_configurations() -> dict[str, PackageConfiguration]:
    """Return 12 multi-component BOM packaging presets across dairy categories."""
    fluid_cats = [DairyCategory.FLUID_MILK, DairyCategory.YOGURT_KEFIR, DairyCategory.CREAM]
    cup_cats = [
        DairyCategory.YOGURT_KEFIR,
        DairyCategory.CREAM,
        DairyCategory.ICE_CREAM,
        DairyCategory.BUTTER,
        DairyCategory.CHEESE,
    ]
    C = ConversionProcess
    M = MaterialFamily
    EOL_CASE = (0.70, 0.10, 0.20)
    EOL_CASE_HI = (0.75, 0.10, 0.15)

    presets = [
        PackageConfiguration(
            config_id="PKG-HDPE-BOTTLE-1L",
            name="1.0 kg Virgin HDPE Bottle (Blow-Molded)",
            package_format=PackageFormat.BOTTLE,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body", M.HDPE, 28.0, 1.45, C.BLOW_MOLDING),
                _bom("cap", M.HDPE, 2.5, 1.55, C.INJECTION_MOLDING),
                _bom("label", M.PP, 1.2, 1.80, C.FILM_EXTRUSION),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 16.0, 0.92, C.CORRUGATED_CONVERTING, 0.50, EOL_CASE, True),
            ],
            line_reject_rate=0.004,
            package_attributable_spoilage_rate=0.008,
            compatible_categories=fluid_cats,
            shelf_life_days=21,
            high_barrier=True,
            notes="Standard 1 kg HDPE dairy bottle with secondary corrugated tray/case.",
        ),
        PackageConfiguration(
            config_id="PKG-PET-BOTTLE-1L",
            name="1.0 kg Virgin PET Bottle",
            package_format=PackageFormat.BOTTLE,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body", M.PET, 32.0, 1.52, C.BLOW_MOLDING),
                _bom("cap", M.HDPE, 2.5, 1.55, C.INJECTION_MOLDING),
                _bom("label", M.PP, 1.2, 1.80, C.FILM_EXTRUSION),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 16.0, 0.92, C.CORRUGATED_CONVERTING, 0.50, EOL_CASE, True),
            ],
            line_reject_rate=0.004,
            package_attributable_spoilage_rate=0.008,
            compatible_categories=fluid_cats,
            shelf_life_days=21,
            high_barrier=True,
            notes="Standard 1 kg virgin PET dairy bottle.",
        ),
        PackageConfiguration(
            config_id="PKG-RPET50-BOTTLE-1L",
            name="1.0 kg Lightweight 50% rPET Bottle",
            package_format=PackageFormat.BOTTLE,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body", M.PET, 24.0, 1.58, C.BLOW_MOLDING, 0.50, (0.35, 0.15, 0.50)),
                _bom("cap", M.HDPE, 2.0, 1.55, C.INJECTION_MOLDING),
                _bom("label", M.PP, 0.9, 1.80, C.FILM_EXTRUSION),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 14.0, 0.90, C.CORRUGATED_CONVERTING, 0.85, EOL_CASE_HI, True),
            ],
            line_reject_rate=0.003,
            package_attributable_spoilage_rate=0.006,
            compatible_categories=fluid_cats,
            shelf_life_days=21,
            high_barrier=True,
            notes="Lightweight PET bottle with 50% food-grade rPET and 85%-recycled corrugated case.",
        ),
        PackageConfiguration(
            config_id="PKG-CARTON-LPB-1L",
            name="1.0 kg Composite Aseptic Carton (LPB + LDPE + Al Foil)",
            package_format=PackageFormat.CARTON,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body_paperboard", M.LIQUID_PACKAGING_BOARD, 20.5, 1.35, C.CARTON_CONVERTING, 0.0, (0.25, 0.25, 0.50)),
                _bom("pe_moisture_layers", M.LDPE, 4.8, 1.50, C.FILM_EXTRUSION, 0.0, (0.05, 0.35, 0.60)),
                _bom("aluminium_oxygen_barrier", M.ALUMINIUM, 1.4, 3.60, C.ALUMINIUM_FOIL_ROLLING, 0.20, (0.10, 0.20, 0.70)),
                _bom("cap_fitment", M.HDPE, 2.3, 1.55, C.INJECTION_MOLDING),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 14.0, 0.90, C.CORRUGATED_CONVERTING, 0.70, EOL_CASE, True),
            ],
            line_reject_rate=0.005,
            package_attributable_spoilage_rate=0.005,
            compatible_categories=fluid_cats,
            shelf_life_days=90,
            high_barrier=True,
            requires_cold_chain=False,
            notes="Multilayer composite aseptic carton (71% board, 16.5% LDPE, 4.8% Al foil, 7.9% HDPE cap).",
        ),
        PackageConfiguration(
            config_id="PKG-GLASS-SINGLE-1L",
            name="1.0 kg Single-Use Glass Bottle (35% Cullet)",
            package_format=PackageFormat.BOTTLE,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body", M.GLASS, 360.0, 0.48, C.GLASS_FORMING, 0.35, (0.30, 0.05, 0.65)),
                _bom("cap", M.ALUMINIUM, 3.2, 3.10, C.ALUMINIUM_FOIL_ROLLING, 0.30),
                _bom("label", M.PAPERBOARD, 1.5, 1.20, C.NONE, 0.50),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 25.0, 0.92, C.CORRUGATED_CONVERTING, 0.60, EOL_CASE, True),
            ],
            line_reject_rate=0.006,
            package_attributable_spoilage_rate=0.006,
            compatible_categories=fluid_cats,
            shelf_life_days=28,
            high_barrier=True,
            notes="Single-use glass bottle; illustrates high mass and energy penalty without reuse.",
        ),
        PackageConfiguration(
            config_id="PKG-GLASS-REUSE-1L",
            name="1.0 kg Returnable Glass Bottle (20 Max Trips, 90% Return)",
            package_format=PackageFormat.BOTTLE,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body", M.GLASS, 420.0, 0.52, C.GLASS_FORMING, 0.45, (0.65, 0.05, 0.30)),
                _bom("cap", M.ALUMINIUM, 3.0, 3.10, C.ALUMINIUM_FOIL_ROLLING, 0.35),
                _bom("label", M.PAPERBOARD, 1.2, 1.20, C.NONE, 0.60),
            ],
            reuse=ReuseParameters(
                is_reusable=True,
                nominal_max_trips=20,
                return_rate=0.90,
                breakage_loss_rate_per_trip=0.02,
                washing_water_l_per_package=0.65,
                washing_thermal_energy_mj_per_package=0.24,
                washing_electricity_kwh_per_package=0.025,
                washing_cost_usd_per_package=0.015,
                reverse_transport_distance_km=150.0,
            ),
            line_reject_rate=0.005,
            package_attributable_spoilage_rate=0.006,
            compatible_categories=fluid_cats,
            shelf_life_days=21,
            high_barrier=True,
            notes="Returnable glass bottle with caustic washing and reverse transport loop.",
        ),
        PackageConfiguration(
            config_id="PKG-POUCH-LDPE-1L",
            name="1.0 kg Flexible LDPE/LLDPE Pillow Pouch",
            package_format=PackageFormat.POUCH,
            net_fill_mass_kg=1.0,
            components=[
                _bom("body_film", M.LLDPE, 7.2, 1.60, C.FILM_EXTRUSION, 0.0, (0.05, 0.20, 0.75)),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 13.0, 0.90, C.CORRUGATED_CONVERTING, 0.70, EOL_CASE, True),
            ],
            line_reject_rate=0.007,
            package_attributable_spoilage_rate=0.018,
            compatible_categories=[DairyCategory.FLUID_MILK, DairyCategory.YOGURT_KEFIR],
            shelf_life_days=10,
            high_barrier=False,
            notes="Ultra-lightweight flexible PE pouch; very low resin cost/mass but higher product spoilage/puncture loss (1.8%).",
        ),
        PackageConfiguration(
            config_id="PKG-PP-CUP-400G",
            name="400 g Thermoformed Virgin PP Cup + Al Foil Lid",
            package_format=PackageFormat.CUP,
            net_fill_mass_kg=0.40,
            components=[
                _bom("body", M.PP, 11.5, 1.48, C.THERMOFORMING),
                _bom("foil_lid", M.ALUMINIUM, 1.2, 3.50, C.ALUMINIUM_FOIL_ROLLING, 0.15),
                _bom("paperboard_sleeve", M.PAPERBOARD, 2.8, 1.15, C.CARTON_CONVERTING, 0.50),
                _bom("corrugated_tray", M.CORRUGATED_BOARD, 8.0, 0.90, C.CORRUGATED_CONVERTING, 0.70, EOL_CASE, True),
            ],
            line_reject_rate=0.005,
            package_attributable_spoilage_rate=0.009,
            compatible_categories=cup_cats,
            shelf_life_days=28,
            high_barrier=True,
            notes="Standard 400 g thermoformed PP dairy cup with aluminium heat-seal lid.",
        ),
        PackageConfiguration(
            config_id="PKG-RPP30-CUP-400G",
            name="400 g Lightweight K3-Style 30% rPP Cup + Recycled Board Wrap",
            package_format=PackageFormat.CUP,
            net_fill_mass_kg=0.40,
            components=[
                _bom("body", M.PP, 8.2, 1.62, C.THERMOFORMING, 0.30, (0.30, 0.20, 0.50)),
                _bom("foil_lid", M.ALUMINIUM, 1.0, 3.50, C.ALUMINIUM_FOIL_ROLLING, 0.35),
                _bom("paperboard_sleeve", M.PAPERBOARD, 4.2, 1.10, C.CARTON_CONVERTING, 0.85, (0.65, 0.10, 0.25)),
                _bom("corrugated_tray", M.CORRUGATED_BOARD, 7.2, 0.90, C.CORRUGATED_CONVERTING, 0.85, EOL_CASE_HI, True),
            ],
            line_reject_rate=0.005,
            package_attributable_spoilage_rate=0.009,
            compatible_categories=cup_cats,
            shelf_life_days=28,
            high_barrier=True,
            notes="Lightweight PP inner cup reinforced by tear-off recycled paperboard wrap.",
        ),
        PackageConfiguration(
            config_id="PKG-CHEESE-FLOWPACK-250G",
            name="250 g Cheese Rigid PET Tray + Barrier Film Flowpack",
            package_format=PackageFormat.TUB,
            net_fill_mass_kg=0.25,
            components=[
                _bom("tray_body", M.PET, 9.0, 1.60, C.THERMOFORMING, 0.40),
                _bom("barrier_film_lid", M.LLDPE, 2.8, 1.75, C.FILM_EXTRUSION),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 5.5, 0.90, C.CORRUGATED_CONVERTING, 0.75, EOL_CASE, True),
            ],
            line_reject_rate=0.004,
            package_attributable_spoilage_rate=0.007,
            compatible_categories=[DairyCategory.CHEESE, DairyCategory.BUTTER],
            shelf_life_days=45,
            high_barrier=True,
            notes="250 g ripened cheese MAP thermoformed tray + barrier film.",
        ),
        PackageConfiguration(
            config_id="PKG-BUTTER-FOILWRAP-200G",
            name="200 g Butter Aluminium-Parchment Laminate Wrap",
            package_format=PackageFormat.FILM_WRAP,
            net_fill_mass_kg=0.20,
            components=[
                _bom("foil_layer", M.ALUMINIUM, 1.5, 3.60, C.ALUMINIUM_FOIL_ROLLING, 0.25),
                _bom("parchment_paper", M.PAPERBOARD, 1.8, 1.40, C.CARTON_CONVERTING),
                _bom("pe_tie_layer", M.LDPE, 0.6, 1.55, C.FILM_EXTRUSION),
                _bom("corrugated_case", M.CORRUGATED_BOARD, 4.2, 0.90, C.CORRUGATED_CONVERTING, 0.75, EOL_CASE, True),
            ],
            line_reject_rate=0.003,
            package_attributable_spoilage_rate=0.006,
            compatible_categories=[DairyCategory.BUTTER, DairyCategory.CHEESE],
            shelf_life_days=60,
            high_barrier=True,
            notes="Traditional 200 g butter foil-parchment wrap.",
        ),
        PackageConfiguration(
            config_id="PKG-POWDER-SACK-25KG",
            name="25 kg Milk Powder Multi-wall Kraft Sack with LDPE Liner",
            package_format=PackageFormat.SACK,
            net_fill_mass_kg=25.0,
            components=[
                _bom("kraft_sack_body", M.PAPERBOARD, 380.0, 1.12, C.CARTON_CONVERTING, 0.20, (0.55, 0.15, 0.30)),
                _bom("ldpe_moisture_liner", M.LDPE, 95.0, 1.50, C.FILM_EXTRUSION),
            ],
            line_reject_rate=0.002,
            package_attributable_spoilage_rate=0.003,
            compatible_categories=[DairyCategory.MILK_POWDER, DairyCategory.OTHER_DAIRY],
            shelf_life_days=365,
            high_barrier=True,
            requires_cold_chain=False,
            notes="25 kg industrial bulk milk powder multi-wall paper sack with inner PE liner.",
        ),
    ]
    return {p.config_id: p for p in presets}


def identify_pareto_frontier(
    results: list[ScenarioComparisonResult],
) -> list[ScenarioComparisonResult]:
    """Flag Pareto-efficient scenarios minimizing (operating cost per FU, packaging GWP per FU)."""
    feasible = [r for r in results if r.feasibility.is_feasible]
    for r in results:
        r.is_pareto_optimal = False

    for candidate in feasible:
        c_cost = candidate.economic.total_operating_cost_per_fu
        c_gwp = candidate.environmental.packaging_system_total_gwp_kgco2e
        candidate.is_pareto_optimal = not any(
            other.scenario_id != candidate.scenario_id
            and other.economic.total_operating_cost_per_fu <= c_cost
            and other.environmental.packaging_system_total_gwp_kgco2e <= c_gwp
            and (
                other.economic.total_operating_cost_per_fu < c_cost
                or other.environmental.packaging_system_total_gwp_kgco2e < c_gwp
            )
            for other in feasible
        )
    return results


def compare_scenarios(
    product: DairyProductRecord,
    baseline_config: PackageConfiguration,
    alternative_configs: list[PackageConfiguration],
    assumptions: ScenarioAssumptions,
    catalog: FactorCatalog | None = None,
) -> list[ScenarioComparisonResult]:
    """Evaluate baseline + alternatives and compute deltas, capital metrics, and Pareto frontier."""
    if catalog is None:
        catalog = get_default_factor_catalog()

    base_feas = check_scenario_feasibility(product, baseline_config)
    base_env = evaluate_environmental_lca(product, baseline_config, assumptions, catalog)
    base_assumptions = deepcopy(assumptions)
    base_assumptions.incremental_capex_usd = 0.0
    base_assumptions.installation_commissioning_usd = 0.0
    base_assumptions.proposed_price_premium_usd_per_kg = 0.0
    base_econ = evaluate_economics(baseline_config, base_assumptions, base_env)

    comparisons: list[ScenarioComparisonResult] = [
        ScenarioComparisonResult(
            scenario_id=f"SCEN-BASE-{baseline_config.config_id}",
            scenario_name=f"Baseline: {baseline_config.name}",
            product_id=product.product_id,
            product_name=product.name_en,
            package_config_id=baseline_config.config_id,
            package_config_name=baseline_config.name,
            is_baseline=True,
            feasibility=base_feas,
            environmental=base_env,
            economic=base_econ,
            tradeoff_summary="Reference baseline configuration.",
        )
    ]

    for idx, alt_cfg in enumerate(alternative_configs, start=1):
        feas = check_scenario_feasibility(product, alt_cfg)
        env = evaluate_environmental_lca(product, alt_cfg, assumptions, catalog)
        econ = evaluate_economics(alt_cfg, assumptions, env)
        deltas = compute_capital_and_tradeoff_metrics(
            baseline_env=base_env,
            baseline_econ=base_econ,
            alt_env=env,
            alt_econ=econ,
            assumptions=assumptions,
        )
        comparisons.append(
            ScenarioComparisonResult(
                scenario_id=f"SCEN-ALT-{idx:02d}-{alt_cfg.config_id}",
                scenario_name=f"Alt {idx}: {alt_cfg.name}",
                product_id=product.product_id,
                product_name=product.name_en,
                package_config_id=alt_cfg.config_id,
                package_config_name=alt_cfg.name,
                is_baseline=False,
                feasibility=feas,
                environmental=env,
                economic=econ,
                **deltas,
            )
        )

    return identify_pareto_frontier(comparisons)


def run_one_at_a_time_sensitivity(
    product: DairyProductRecord,
    package_config: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    swing_fraction: float = 0.25,
    catalog: FactorCatalog | None = None,
) -> pd.DataFrame:
    """Run tornado sensitivity analysis (+/- swing_fraction) on key operational and LCA drivers."""
    if catalog is None:
        catalog = get_default_factor_catalog()

    base_env = evaluate_environmental_lca(product, package_config, assumptions, catalog)
    base_econ = evaluate_economics(package_config, assumptions, base_env)
    base_cost = base_econ.total_operating_cost_per_fu
    base_gwp = base_env.packaging_system_total_gwp_kgco2e

    parameters = [
        ("package_component_unit_price", "Package Material Unit Price (+/-25%)"),
        ("package_component_mass", "Package Component Mass (+/-25%)"),
        ("grid_carbon_intensity", "Electricity Grid Carbon Intensity (+/-25%)"),
        ("spoilage_loss_rate", "Package-Attributable Spoilage Rate (+/-25%)"),
        ("transport_distance", "Supply & Distribution Distance (+/-25%)"),
        ("electricity_price", "Electricity Tariff (+/-25%)"),
    ]
    if package_config.reuse.is_reusable:
        parameters.append(("reuse_return_rate", "Container Return Rate (80% to 98%)"))

    rows: list[dict[str, Any]] = []
    for param_key, label in parameters:
        low_cfg, high_cfg = deepcopy(package_config), deepcopy(package_config)
        low_assump, high_assump = deepcopy(assumptions), deepcopy(assumptions)

        if param_key == "package_component_unit_price":
            for c in low_cfg.components:
                c.unit_price_usd_per_kg *= 1.0 - swing_fraction
            for c in high_cfg.components:
                c.unit_price_usd_per_kg *= 1.0 + swing_fraction
        elif param_key == "package_component_mass":
            for c in low_cfg.components:
                c.mass_g_per_package *= 1.0 - swing_fraction
            for c in high_cfg.components:
                c.mass_g_per_package *= 1.0 + swing_fraction
        elif param_key == "grid_carbon_intensity":
            low_assump.grid_carbon_intensity_kgco2e_per_kwh *= 1.0 - swing_fraction
            high_assump.grid_carbon_intensity_kgco2e_per_kwh *= 1.0 + swing_fraction
        elif param_key == "spoilage_loss_rate":
            low_cfg.package_attributable_spoilage_rate = max(
                0.0, low_cfg.package_attributable_spoilage_rate * (1.0 - swing_fraction)
            )
            high_cfg.package_attributable_spoilage_rate = min(
                0.25, high_cfg.package_attributable_spoilage_rate * (1.0 + swing_fraction)
            )
        elif param_key == "transport_distance":
            low_cfg.supplier_to_plant_distance_km *= 1.0 - swing_fraction
            low_cfg.distribution_distance_km *= 1.0 - swing_fraction
            high_cfg.supplier_to_plant_distance_km *= 1.0 + swing_fraction
            high_cfg.distribution_distance_km *= 1.0 + swing_fraction
        elif param_key == "electricity_price":
            low_assump.electricity_price_usd_per_kwh *= 1.0 - swing_fraction
            high_assump.electricity_price_usd_per_kwh *= 1.0 + swing_fraction
        elif param_key == "reuse_return_rate":
            low_cfg.reuse.return_rate = 0.80
            high_cfg.reuse.return_rate = 0.98

        env_low = evaluate_environmental_lca(product, low_cfg, low_assump, catalog)
        econ_low = evaluate_economics(low_cfg, low_assump, env_low)
        env_high = evaluate_environmental_lca(product, high_cfg, high_assump, catalog)
        econ_high = evaluate_economics(high_cfg, high_assump, env_high)

        cost_swing = abs(
            econ_high.total_operating_cost_per_fu - econ_low.total_operating_cost_per_fu
        )
        gwp_swing = abs(
            env_high.packaging_system_total_gwp_kgco2e
            - env_low.packaging_system_total_gwp_kgco2e
        )

        rows.append(
            {
                "parameter_key": param_key,
                "parameter_label": label,
                "baseline_cost_per_fu": round(base_cost, 2),
                "low_param_cost_per_fu": round(econ_low.total_operating_cost_per_fu, 2),
                "high_param_cost_per_fu": round(econ_high.total_operating_cost_per_fu, 2),
                "cost_swing_usd_per_fu": round(cost_swing, 2),
                "baseline_packaging_gwp_kgco2e_per_fu": round(base_gwp, 2),
                "low_param_packaging_gwp_kgco2e_per_fu": round(
                    env_low.packaging_system_total_gwp_kgco2e, 2
                ),
                "high_param_packaging_gwp_kgco2e_per_fu": round(
                    env_high.packaging_system_total_gwp_kgco2e, 2
                ),
                "gwp_swing_kgco2e_per_fu": round(gwp_swing, 2),
                "source_type": str(DataSourceType.MODEL_DERIVED),
            }
        )

    return pd.DataFrame(rows).sort_values(
        by=["gwp_swing_kgco2e_per_fu", "cost_swing_usd_per_fu"], ascending=False
    )
