"""Deterministic Economic & Financial Calculation Engine for DairyEco AI.

Implements vision.md Section 6:
- Packaging material cost = component mass (kg) * unit price (currency/kg), accounting for
  reuse amortization on reusable bodies and filling-line reject / product spoilage multipliers.
- Packaging washing/reverse-logistics, freight, waste disposal, and product loss costs.
- Plant utilities, labour, maintenance, total operating cost, and contribution margin.
- Incremental capex + installation, annual cash flow delta, horizon-validated payback
  (years and months), cumulative cash flow schedule, NPV, break-even annual volume, and
  marginal carbon abatement cost (USD / tCO2e).
- Never trains a black-box ML model for ROI, NPV, or profit; labels outputs clearly as scenario
  estimates when derived from assumed/proxy inputs.
"""

from __future__ import annotations

from typing import Any

from dairyeco.domain.models import (
    DataSourceType,
    EconomicResult,
    EnvironmentalResult,
    PackageConfiguration,
    ScenarioAssumptions,
)
from dairyeco.lca.engine import compute_packaging_transport_tkm


def calculate_npv(
    initial_investment: float,
    annual_cash_flow_delta: float,
    discount_rate: float,
    years: int,
) -> float:
    """Compute Net Present Value (NPV) of an incremental investment over `years`."""
    if years <= 0:
        return -initial_investment
    if discount_rate == 0.0:
        return -initial_investment + annual_cash_flow_delta * years
    pv_annuity = sum(
        annual_cash_flow_delta / ((1.0 + discount_rate) ** t) for t in range(1, years + 1)
    )
    return -initial_investment + pv_annuity


def calculate_payback_schedule(
    initial_investment: float,
    annual_incremental_cash_flow: float,
    horizon_years: int,
) -> dict[str, Any]:
    """Calculate horizon-validated payback period, cumulative cash flow schedule, and status explanation.

    Rules:
    - Year-by-year cumulative cash flow is ``CF(t) = -initial_investment + t * annual_incremental_cash_flow``
      for ``t = 0 .. horizon_years``.
    - If ``initial_investment == 0`` and ``annual_incremental_cash_flow >= 0``:
      payback is immediate (``0.0 years`` / ``0.0 months``).
    - If ``annual_incremental_cash_flow <= 0`` (and ``initial_investment > 0`` or ``annual_incremental_cash_flow < 0``):
      payback is ``None`` (``No payback``) because incremental cash flows are non-positive.
    - If ``initial_investment > 0`` and ``annual_incremental_cash_flow > 0``:
      ``unconstrained_years = initial_investment / annual_incremental_cash_flow``.
      Payback is returned as ``round(unconstrained_years, 2)`` ONLY if ``unconstrained_years <= horizon_years``
      (i.e. cumulative net cash flow at ``horizon_years`` >= 0). Otherwise returns ``None`` (``No payback``)
      with ``payback_status = 'exceeds_horizon'``.
    """
    horizon = max(1, int(horizon_years))
    inv = max(0.0, float(initial_investment))
    cf = float(annual_incremental_cash_flow)

    schedule = [round(-inv + t * cf, 2) for t in range(horizon + 1)]
    cum_net_cf = schedule[-1]

    if inv == 0.0:
        if cf >= 0.0:
            return {
                "simple_payback_years": 0.0,
                "simple_payback_months": 0.0,
                "unconstrained_payback_years": 0.0,
                "cumulative_net_cash_flow_usd": cum_net_cf,
                "cumulative_cash_flow_schedule": schedule,
                "payback_status": "immediate",
                "payback_explanation": (
                    f"Immediate payback (0.0 yrs / 0.0 mos): $0 upfront CAPEX with "
                    f"+${cf:,.0f}/yr positive incremental cash flow."
                ),
            }
        return {
            "simple_payback_years": None,
            "simple_payback_months": None,
            "unconstrained_payback_years": None,
            "cumulative_net_cash_flow_usd": cum_net_cf,
            "cumulative_cash_flow_schedule": schedule,
            "payback_status": "negative_cash_flow",
            "payback_explanation": (
                f"No payback: although upfront CAPEX is $0, the proposed transition "
                f"reduces annual operating cash flow by -${abs(cf):,.0f}/yr "
                f"(cumulative {horizon}-year cash flow: -${abs(cum_net_cf):,.0f})."
            ),
        }

    if cf <= 0.0:
        reason = (
            f"No payback: annual incremental cash flow is -${abs(cf):,.0f}/yr "
            f"(proposed packaging increases operating expenses relative to baseline), "
            f"so the ${inv:,.0f} upfront CAPEX is never recovered "
            f"({horizon}-year cumulative cash flow: -${abs(cum_net_cf):,.0f})."
            if cf < 0.0
            else (
                f"No payback: annual incremental cash flow is $0/yr, "
                f"so the ${inv:,.0f} upfront CAPEX cannot be recovered."
            )
        )
        return {
            "simple_payback_years": None,
            "simple_payback_months": None,
            "unconstrained_payback_years": None,
            "cumulative_net_cash_flow_usd": cum_net_cf,
            "cumulative_cash_flow_schedule": schedule,
            "payback_status": "negative_cash_flow",
            "payback_explanation": reason,
        }

    raw_years = inv / cf
    unconstrained_yrs = round(raw_years, 2)
    raw_months = raw_years * 12.0

    if raw_years <= horizon + 1e-9:
        payback_yrs = round(raw_years, 2)
        payback_mos = round(raw_months, 1)
        return {
            "simple_payback_years": payback_yrs,
            "simple_payback_months": payback_mos,
            "unconstrained_payback_years": unconstrained_yrs,
            "cumulative_net_cash_flow_usd": cum_net_cf,
            "cumulative_cash_flow_schedule": schedule,
            "payback_status": "within_horizon",
            "payback_explanation": (
                f"Payback achieved in {payback_yrs:.2f} years ({payback_mos:.1f} months): "
                f"+${cf:,.0f}/yr incremental cash flow recovers the ${inv:,.0f} CAPEX within "
                f"the {horizon}-year evaluation horizon (cumulative net cash flow: +${cum_net_cf:,.0f})."
            ),
        }

    return {
        "simple_payback_years": None,
        "simple_payback_months": None,
        "unconstrained_payback_years": unconstrained_yrs,
        "cumulative_net_cash_flow_usd": cum_net_cf,
        "cumulative_cash_flow_schedule": schedule,
        "payback_status": "exceeds_horizon",
        "payback_explanation": (
            f"No payback within the {horizon}-year horizon: positive annual savings of +${cf:,.0f}/yr "
            f"recover ${cf * horizon:,.0f} over {horizon} years (leaving a net shortfall of "
            f"-${abs(cum_net_cf):,.0f}). Full recovery of the ${inv:,.0f} CAPEX requires "
            f"{unconstrained_yrs:.2f} years ({raw_months:.1f} months)."
        ),
    }


def evaluate_economics(
    package_config: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    env_result: EnvironmentalResult,
) -> EconomicResult:
    """Calculate transparent unit economics per functional unit (1,000 kg saleable product)."""
    fu_kg = assumptions.functional_unit_saleable_kg
    saleable_packages = fu_kg / package_config.net_fill_mass_kg
    gross_packages_filled = saleable_packages * package_config.gross_fill_multiplier
    eff_trips = package_config.reuse.effective_trips
    new_containers_for_fu = gross_packages_filled / eff_trips

    comp_costs: list[dict[str, Any]] = []
    pkg_material_cost_fu = 0.0

    for comp in package_config.components:
        effective_units = (
            new_containers_for_fu
            if package_config.is_reusable_component(comp)
            else gross_packages_filled
        )
        comp_mass_kg_fu = (comp.mass_g_per_package / 1000.0) * effective_units
        comp_cost_fu = comp_mass_kg_fu * comp.unit_price_usd_per_kg
        pkg_material_cost_fu += comp_cost_fu

        comp_costs.append(
            {
                "component_name": comp.component_name,
                "material_family": str(comp.material_family),
                "mass_kg_per_fu": round(comp_mass_kg_fu, 4),
                "unit_price_per_kg": comp.unit_price_usd_per_kg,
                "price_source_type": str(comp.price_source_type),
                "cost_per_fu": round(comp_cost_fu, 3),
                "cost_per_saleable_package": round(comp_cost_fu / saleable_packages, 5),
            }
        )

    # Reuse washing cost
    washing_cost_fu = 0.0
    if package_config.reuse.is_reusable and eff_trips > 1.0:
        washed_units = gross_packages_filled * package_config.reuse.return_rate
        washing_cost_fu = washed_units * (
            package_config.reuse.washing_cost_usd_per_package
            + package_config.reuse.washing_electricity_kwh_per_package
            * assumptions.electricity_price_usd_per_kwh
            + package_config.reuse.washing_thermal_energy_mj_per_package
            * assumptions.natural_gas_price_usd_per_mj
            + (package_config.reuse.washing_water_l_per_package / 1000.0)
            * assumptions.water_price_usd_per_m3
        )

    # Packaging freight cost (inbound + outbound tare + reverse return of reusable containers)
    inbound_tkm, outbound_tare_tkm, reverse_tkm = compute_packaging_transport_tkm(
        package_config=package_config,
        total_pkg_mass_kg=env_result.total_packaging_mass_kg,
        gross_packages_filled=gross_packages_filled,
    )

    freight_cost_fu = (
        inbound_tkm + outbound_tare_tkm + reverse_tkm
    ) * assumptions.freight_cost_usd_per_tkm

    # Packaging end-of-life waste disposal cost minus recyclable scrap credit
    disposed_waste_kg = env_result.waste_incinerated_kg + env_result.waste_landfilled_kg
    waste_net_cost_fu = (
        disposed_waste_kg * assumptions.waste_disposal_cost_usd_per_kg
        - env_result.waste_recycled_kg * assumptions.recycled_scrap_credit_usd_per_kg
    )

    # Product loss cost (rejects + package-attributable spoilage)
    product_loss_cost_fu = (
        env_result.product_loss_total_kg * assumptions.raw_dairy_loss_cost_usd_per_kg
    )

    total_pkg_attributable_cost_fu = (
        pkg_material_cost_fu
        + washing_cost_fu
        + freight_cost_fu
        + waste_net_cost_fu
        + product_loss_cost_fu
    )

    # Dairy plant utilities, labour, and maintenance per FU
    if assumptions.include_dairy_processing_boundary:
        plant_utilities_cost_fu = fu_kg * (
            assumptions.plant_electricity_kwh_per_kg_product
            * assumptions.electricity_price_usd_per_kwh
            + assumptions.plant_thermal_mj_per_kg_product
            * assumptions.natural_gas_price_usd_per_mj
            + (assumptions.plant_water_l_per_kg_product / 1000.0)
            * assumptions.water_price_usd_per_m3
        )
        plant_labour_maint_fu = (fu_kg / 1000.0) * (
            assumptions.labour_cost_usd_per_1000kg + assumptions.maintenance_cost_usd_per_1000kg
        )
    else:
        plant_utilities_cost_fu = 0.0
        plant_labour_maint_fu = 0.0

    total_op_cost_fu = (
        total_pkg_attributable_cost_fu + plant_utilities_cost_fu + plant_labour_maint_fu
    )
    effective_selling_price = (
        assumptions.net_selling_price_usd_per_kg + assumptions.proposed_price_premium_usd_per_kg
    )
    revenue_fu = fu_kg * effective_selling_price
    contribution_margin_fu = revenue_fu - total_op_cost_fu

    annual_fus = assumptions.annual_production_volume_kg / fu_kg
    annual_op_cost = total_op_cost_fu * annual_fus
    total_investment = (
        assumptions.incremental_capex_usd + assumptions.installation_commissioning_usd
    )

    all_measured = assumptions.assumptions_source_type == DataSourceType.MEASURED and all(
        c.price_source_type == DataSourceType.MEASURED for c in package_config.components
    )
    epistemic_label = (
        "verified_company_economics (measured)"
        if all_measured
        else "scenario_estimate (derived from assumed/proxy financial inputs; not observed company savings)"
    )

    return EconomicResult(
        functional_unit_kg=fu_kg,
        currency=assumptions.currency,
        price_year=assumptions.price_year,
        packaging_material_cost_per_fu=round(pkg_material_cost_fu, 2),
        packaging_washing_reuse_cost_per_fu=round(washing_cost_fu, 2),
        packaging_freight_cost_per_fu=round(freight_cost_fu, 2),
        packaging_waste_net_cost_per_fu=round(waste_net_cost_fu, 2),
        product_loss_cost_per_fu=round(product_loss_cost_fu, 2),
        total_packaging_attributable_cost_per_fu=round(total_pkg_attributable_cost_fu, 2),
        plant_utilities_cost_per_fu=round(plant_utilities_cost_fu, 2),
        plant_labour_and_maintenance_cost_per_fu=round(plant_labour_maint_fu, 2),
        total_operating_cost_per_fu=round(total_op_cost_fu, 2),
        cost_per_saleable_package=round(total_pkg_attributable_cost_fu / saleable_packages, 5),
        cost_per_kg_saleable_product=round(total_op_cost_fu / fu_kg, 4),
        revenue_per_fu=round(revenue_fu, 2),
        contribution_margin_per_fu=round(contribution_margin_fu, 2),
        annual_operating_cost=round(annual_op_cost, 2),
        total_initial_investment=round(total_investment, 2),
        epistemic_status=epistemic_label,
        component_cost_breakdown=comp_costs,
    )


def compute_capital_and_tradeoff_metrics(
    baseline_env: EnvironmentalResult,
    baseline_econ: EconomicResult,
    alt_env: EnvironmentalResult,
    alt_econ: EconomicResult,
    assumptions: ScenarioAssumptions,
) -> dict[str, Any]:
    """Compare an alternative scenario against the baseline scenario."""
    fu_kg = assumptions.functional_unit_saleable_kg
    annual_fus = assumptions.annual_production_volume_kg / fu_kg

    delta_cost_fu = alt_econ.total_operating_cost_per_fu - baseline_econ.total_operating_cost_per_fu
    delta_cost_pct = (
        (delta_cost_fu / baseline_econ.total_operating_cost_per_fu * 100.0)
        if baseline_econ.total_operating_cost_per_fu > 0
        else 0.0
    )
    delta_pkg_cost_fu = (
        alt_econ.total_packaging_attributable_cost_per_fu
        - baseline_econ.total_packaging_attributable_cost_per_fu
    )
    delta_pkg_cost_pct = (
        (delta_pkg_cost_fu / baseline_econ.total_packaging_attributable_cost_per_fu * 100.0)
        if baseline_econ.total_packaging_attributable_cost_per_fu > 0
        else 0.0
    )

    delta_pkg_gwp_fu = (
        alt_env.packaging_system_total_gwp_kgco2e
        - baseline_env.packaging_system_total_gwp_kgco2e
    )
    delta_pkg_gwp_pct = (
        (delta_pkg_gwp_fu / baseline_env.packaging_system_total_gwp_kgco2e * 100.0)
        if baseline_env.packaging_system_total_gwp_kgco2e > 0
        else 0.0
    )

    delta_tot_gwp_fu = (
        alt_env.combined_total_gwp_kgco2e - baseline_env.combined_total_gwp_kgco2e
    )
    delta_tot_gwp_pct = (
        (delta_tot_gwp_fu / baseline_env.combined_total_gwp_kgco2e * 100.0)
        if baseline_env.combined_total_gwp_kgco2e > 0
        else 0.0
    )

    delta_virgin_plastic_fu = (
        alt_env.virgin_fossil_plastic_mass_kg - baseline_env.virgin_fossil_plastic_mass_kg
    )
    delta_pkg_mass_fu = alt_env.total_packaging_mass_kg - baseline_env.total_packaging_mass_kg

    # Incremental cash flow = operating cost savings + incremental revenue (if any price premium)
    delta_revenue_fu = alt_econ.revenue_per_fu - baseline_econ.revenue_per_fu
    net_cash_flow_per_fu = -delta_cost_fu + delta_revenue_fu
    annual_savings = round(net_cash_flow_per_fu * annual_fus, 2)
    investment = alt_econ.total_initial_investment

    payback_info = calculate_payback_schedule(
        initial_investment=investment,
        annual_incremental_cash_flow=annual_savings,
        horizon_years=assumptions.project_lifetime_years,
    )

    break_even_vol_kg: float | None = None
    if investment > 0 and net_cash_flow_per_fu > 0:
        annual_savings_per_kg = net_cash_flow_per_fu / fu_kg
        break_even_vol_kg = round(
            investment / (annual_savings_per_kg * assumptions.project_lifetime_years), 1
        )
    elif investment == 0.0 and net_cash_flow_per_fu >= 0:
        break_even_vol_kg = 0.0

    npv_val = round(
        calculate_npv(
            initial_investment=investment,
            annual_cash_flow_delta=annual_savings,
            discount_rate=assumptions.discount_rate,
            years=assumptions.project_lifetime_years,
        ),
        2,
    )

    # Marginal carbon abatement cost (USD / metric ton CO2e avoided)
    abatement_cost: float | None = None
    avoided_tco2e_per_fu = -delta_pkg_gwp_fu / 1000.0
    if avoided_tco2e_per_fu > 1e-6:
        abatement_cost = round(delta_cost_fu / avoided_tco2e_per_fu, 2)

    if net_cash_flow_per_fu >= 0 and delta_pkg_gwp_fu <= 0:
        summary = "Win-win: reduces both operating cost and packaging GHG emissions vs baseline."
    elif net_cash_flow_per_fu < 0 and delta_pkg_gwp_fu < 0:
        abatement_note = (
            f" (${abatement_cost:.1f}/tCO2e avoided)" if abatement_cost is not None else ""
        )
        summary = (
            f"Environmental trade-off: reduces packaging GWP by {-delta_pkg_gwp_pct:.1f}% "
            f"at +${delta_cost_fu:.2f}/FU{abatement_note}."
        )
    elif net_cash_flow_per_fu > 0 and delta_pkg_gwp_fu > 0:
        summary = (
            f"Cost-saving trade-off: saves ${net_cash_flow_per_fu:.2f}/FU but increases packaging GWP "
            f"by +{delta_pkg_gwp_pct:.1f}%."
        )
    else:
        summary = "Dominated by baseline: higher operating cost and higher packaging GHG emissions."

    return {
        "delta_cost_per_fu": round(delta_cost_fu, 2),
        "delta_cost_pct": round(delta_cost_pct, 2),
        "delta_packaging_cost_pct": round(delta_pkg_cost_pct, 2),
        "delta_packaging_gwp_kgco2e_per_fu": round(delta_pkg_gwp_fu, 3),
        "delta_packaging_gwp_pct": round(delta_pkg_gwp_pct, 2),
        "delta_total_gwp_kgco2e_per_fu": round(delta_tot_gwp_fu, 3),
        "delta_total_gwp_pct": round(delta_tot_gwp_pct, 2),
        "delta_virgin_plastic_kg_per_fu": round(delta_virgin_plastic_fu, 3),
        "delta_packaging_mass_kg_per_fu": round(delta_pkg_mass_fu, 3),
        "initial_investment_usd": round(investment, 2),
        "annual_cash_flow_savings": annual_savings,
        "simple_payback_years": payback_info["simple_payback_years"],
        "simple_payback_months": payback_info["simple_payback_months"],
        "unconstrained_payback_years": payback_info["unconstrained_payback_years"],
        "cumulative_net_cash_flow_usd": payback_info["cumulative_net_cash_flow_usd"],
        "cumulative_cash_flow_schedule": payback_info["cumulative_cash_flow_schedule"],
        "payback_status": payback_info["payback_status"],
        "payback_explanation": payback_info["payback_explanation"],
        "npv_usd": npv_val,
        "break_even_annual_volume_kg": break_even_vol_kg,
        "abatement_cost_usd_per_tco2e": abatement_cost,
        "tradeoff_summary": summary,
    }
