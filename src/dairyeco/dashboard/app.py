"""DairyEco AI — Executive Packaging Transition Decision Platform (EN / UZ / RU) + Developer Mode.

Answers the core business question:
"What happens to our business and the environment if we switch from our current
packaging to a more sustainable alternative?"

Supports instantaneous language switching across English, Uzbek (Oʻzbekcha),
and Russian (Русский), plus a dedicated Developer Mode toggle for inspecting
ML models, hyperparameters, dataset schemas, SHAP/additive feature attributions,
end-to-end execution traces, and controlled in-memory experiments.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from dairyeco.config import PROCESSED_DIR
from dairyeco.dashboard.dev_mode import render_developer_mode
from dairyeco.dashboard.i18n import (
    CATEGORY_LABELS_I18N,
    LANGUAGES,
    PACKAGE_FORMAT_I18N,
    UI_TEXT,
    build_plain_language_narrative,
    localize_payback_explanation,
    localize_preset_name,
    localize_preset_notes,
    localize_product_name,
    localize_sensitivity_label,
)
from dairyeco.domain.models import (
    POLYMER_MATERIALS,
    DairyCategory,
    DairyProductRecord,
    PackageConfiguration,
    ScenarioAssumptions,
    ScenarioComparisonResult,
)
from dairyeco.lca.engine import get_default_factor_catalog
from dairyeco.optimization.pareto import (
    build_preset_package_configurations,
    compare_scenarios,
    run_one_at_a_time_sensitivity,
)
from dairyeco.services.reporting import (
    generate_scenario_markdown_report,
    load_dairy_products,
)

st.set_page_config(
    page_title="DairyEco AI — Packaging Transition Impact Calculator",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DEFAULT_PAIR_BY_CATEGORY: dict[DairyCategory, tuple[str, str]] = {
    DairyCategory.FLUID_MILK: ("PKG-HDPE-BOTTLE-1L", "PKG-RPET50-BOTTLE-1L"),
    DairyCategory.YOGURT_KEFIR: ("PKG-PP-CUP-400G", "PKG-RPP30-CUP-400G"),
    DairyCategory.CREAM: ("PKG-PP-CUP-400G", "PKG-RPP30-CUP-400G"),
    DairyCategory.ICE_CREAM: ("PKG-PP-CUP-400G", "PKG-RPP30-CUP-400G"),
    DairyCategory.CHEESE: ("PKG-CHEESE-FLOWPACK-250G", "PKG-BUTTER-FOILWRAP-200G"),
    DairyCategory.BUTTER: ("PKG-BUTTER-FOILWRAP-200G", "PKG-CHEESE-FLOWPACK-250G"),
    DairyCategory.MILK_POWDER: ("PKG-POWDER-SACK-25KG", "PKG-CARTON-LPB-1L"),
    DairyCategory.OTHER_DAIRY: ("PKG-HDPE-BOTTLE-1L", "PKG-RPET50-BOTTLE-1L"),
}

GRID_PRESETS: dict[str, dict[str, str]] = {
    "uz_grid": {
        "en": "Uzbekistan / Central Asia (assumed natural-gas grid proxy — 0.550 kg CO₂e/kWh)",
        "uz": "Oʻzbekiston / Markaziy Osiyo (tabiiy gazga asoslangan tarmoq — 0,550 kg CO₂e/kVt·soat)",
        "ru": "Узбекистан / Центральная Азия (газовая генерация — 0,550 кг CO₂e/кВт·ч)",
    },
    "global_grid": {
        "en": "Cross-regional average (NIST/ANL 2024 Fig. 18a — 0.573 kg CO₂e/kWh)",
        "uz": "Mintaqalararo oʻrtacha koʻrsatkich (NIST/ANL 2024 — 0,573 kg CO₂e/kVt·soat)",
        "ru": "Межрегиональное среднее (NIST/ANL 2024 — 0,573 кг CO₂e/кВт·ч)",
    },
    "eu_grid": {
        "en": "Western Europe average (NIST/ANL 2024 Fig. 18a — 0.285 kg CO₂e/kWh)",
        "uz": "Gʻarbiy Yevropa oʻrtacha elektr tarmogʻi (NIST 2024 — 0,285 kg CO₂e/kVt·soat)",
        "ru": "Средняя электросеть Западной Европы (NIST 2024 — 0,285 кг CO₂e/кВт·ч)",
    },
    "us_grid": {
        "en": "United States average (NIST/ANL 2024 Fig. 18a — 0.466 kg CO₂e/kWh)",
        "uz": "AQSH oʻrtacha elektr tarmogʻi (NIST 2024 — 0,466 kg CO₂e/kVt·soat)",
        "ru": "Средняя электросеть США (NIST 2024 — 0,466 кг CO₂e/кВт·ч)",
    },
}

GRID_VALUES: dict[str, float] = {
    "uz_grid": 0.550,
    "global_grid": 0.573,
    "eu_grid": 0.285,
    "us_grid": 0.466,
}

RESIN_REGION_LABELS: dict[str, dict[str, str]] = {
    "Cross-regional average": {
        "en": "Cross-regional average",
        "uz": "Mintaqalararo oʻrtacha koʻrsatkich",
        "ru": "Межрегиональное среднее",
    },
    "Western Europe": {
        "en": "Western Europe",
        "uz": "Gʻarbiy Yevropa",
        "ru": "Западная Европа",
    },
    "USA": {
        "en": "USA",
        "uz": "AQSH",
        "ru": "США",
    },
    "China": {
        "en": "China",
        "uz": "Xitoy",
        "ru": "Китай",
    },
    "MENA": {
        "en": "Middle East & North Africa (MENA)",
        "uz": "Yaqin Sharq va Shimoliy Afrika (MENA)",
        "ru": "Ближний Восток и Северная Африка (MENA)",
    },
}


@st.cache_resource(max_entries=16)
def _get_cached_catalog():
    return get_default_factor_catalog(PROCESSED_DIR)


@st.cache_data(max_entries=16)
def _get_cached_products() -> list[DairyProductRecord]:
    return load_dairy_products(PROCESSED_DIR, core_only=True)


def _apply_package_overrides(
    cfg: PackageConfiguration,
    resin_region: str,
    reuse_return_rate: float | None = None,
    material_price_multiplier: float = 1.0,
) -> PackageConfiguration:
    updated = deepcopy(cfg)
    for comp in updated.components:
        if comp.material_family in POLYMER_MATERIALS:
            comp.resin_region = resin_region
        if abs(material_price_multiplier - 1.0) > 1e-6:
            comp.unit_price_usd_per_kg = round(
                comp.unit_price_usd_per_kg * material_price_multiplier, 4
            )
    if updated.reuse.is_reusable and reuse_return_rate is not None:
        updated.reuse.return_rate = reuse_return_rate
    return updated


def _format_signed_currency(val: float, currency: str = "USD") -> str:
    prefix = "$" if currency == "USD" else f"{currency} "
    if abs(val) < 0.5:
        return f"{prefix}0"
    sign = "+" if val > 0 else "-"
    return f"{sign}{prefix}{abs(val):,.0f}"


def _format_currency(val: float, currency: str = "USD", decimals: int = 0) -> str:
    prefix = "$" if currency == "USD" else f"{currency} "
    if val < 0:
        return f"-{prefix}{abs(val):,.{decimals}f}"
    return f"{prefix}{val:,.{decimals}f}"


def _format_signed_pct(val: float) -> str:
    if abs(val) < 0.05:
        return "0.0%"
    return f"{val:+.1f}%"


def _package_summary_stats(
    cfg: PackageConfiguration, lang: str, t: dict[str, Any]
) -> dict[str, str]:
    total_mass_g = cfg.total_bom_mass_g
    recycled_mass_g = sum(
        c.mass_g_per_package * c.recycled_content_fraction for c in cfg.components
    )
    eol_recycled_g = sum(
        c.mass_g_per_package * c.eol_recycling_fraction for c in cfg.components
    )
    recycled_pct = (recycled_mass_g / total_mass_g * 100.0) if total_mass_g > 0 else 0.0
    eol_recycled_pct = (eol_recycled_g / total_mass_g * 100.0) if total_mass_g > 0 else 0.0
    primary_materials = ", ".join(
        dict.fromkeys(
            c.material_family.value.replace("_", " ").upper()
            for c in cfg.components
            if not c.is_secondary_or_tertiary
        )
    )
    fmt_label = PACKAGE_FORMAT_I18N.get(lang, PACKAGE_FORMAT_I18N["en"]).get(
        cfg.package_format, cfg.package_format.value.title()
    )
    return {
        "format": fmt_label,
        "materials": primary_materials or "Mixed",
        "fill_size": f"{cfg.net_fill_mass_kg * 1000:,.0f} g"
        if cfg.net_fill_mass_kg < 1.0
        else f"{cfg.net_fill_mass_kg:,.1f} kg",
        "total_mass_g": f"{total_mass_g:,.1f} g",
        "recycled_content": f"{recycled_pct:.0f}%",
        "eol_recycling": f"{eol_recycled_pct:.0f}%",
        "spoilage_rate": f"{cfg.package_attributable_spoilage_rate * 100:.1f}%",
        "reusable": (
            t["reusable_yes"](cfg.reuse.effective_trips)
            if cfg.reuse.is_reusable
            else t["reusable_no"]
        ),
    }


def _classify_decision(comp: ScenarioComparisonResult, t: dict[str, Any]) -> dict[str, str]:
    """Classify the proposed transition into one of four clear executive verdicts."""
    if not comp.feasibility.is_feasible:
        return {
            "verdict": t["verdict_infeasible"],
            "badge_text": t["badge_infeasible"],
            "badge_color": "red",
            "icon": ":material/error:",
        }

    saves_money = comp.annual_cash_flow_savings >= 0.0
    cuts_emissions = comp.delta_packaging_gwp_kgco2e_per_fu < 0.0

    if saves_money and cuts_emissions:
        return {
            "verdict": t["verdict_win_win"],
            "badge_text": t["badge_win_win"],
            "badge_color": "green",
            "icon": ":material/verified:",
        }
    if cuts_emissions and not saves_money:
        return {
            "verdict": t["verdict_env_only"],
            "badge_text": t["badge_env_only"],
            "badge_color": "blue",
            "icon": ":material/eco:",
        }
    if saves_money and not cuts_emissions:
        return {
            "verdict": t["verdict_econ_only"],
            "badge_text": t["badge_econ_only"],
            "badge_color": "orange",
            "icon": ":material/payments:",
        }
    return {
        "verdict": t["verdict_neither"],
        "badge_text": t["badge_neither"],
        "badge_color": "red",
        "icon": ":material/warning:",
    }


def main() -> None:
    products = _get_cached_products()
    presets = build_preset_package_configurations()
    catalog = _get_cached_catalog()

    # -------------------------------------------------------------------------
    # Header, Language Switcher & Developer Mode Toggle
    # -------------------------------------------------------------------------
    hdr_left, hdr_mid, hdr_right = st.columns([2.1, 0.9, 1.0], gap="medium")
    with hdr_right:
        selected_lang = st.segmented_control(
            "Language / Til / Язык",
            options=list(LANGUAGES.keys()),
            default="en",
            format_func=lambda code: LANGUAGES[code],
            selection_mode="single",
            key="platform_lang",
        )
        lang = selected_lang if selected_lang in LANGUAGES else "en"

    t = UI_TEXT[lang]
    cat_labels = CATEGORY_LABELS_I18N[lang]

    with hdr_mid:
        st.write("")
        dev_mode_enabled = st.toggle(
            f":material/terminal: {t['lbl_dev_mode']}",
            value=False,
            key="developer_mode_toggle",
            help="Open the technical ML, Data Provenance, SHAP Explainability & Execution Trace workbench.",
        )

    with hdr_left:
        st.markdown(f"### :material/eco: {t['brand_subtitle']}")

    st.title(t["main_title"])
    st.caption(t["main_caption"])

    # -------------------------------------------------------------------------
    # 1. Simple Scenario Builder
    # -------------------------------------------------------------------------
    with st.container(border=True):
        st.markdown(f"#### :material/tune: {t['sec1_title']}")

        row1_col1, row1_col2, row1_col3 = st.columns([1.1, 1.4, 1.0], gap="medium")

        available_categories = sorted(
            {p.category for p in products},
            key=lambda c: list(cat_labels.keys()).index(c) if c in cat_labels else 99,
        )
        default_cat_idx = (
            available_categories.index(DairyCategory.FLUID_MILK)
            if DairyCategory.FLUID_MILK in available_categories
            else 0
        )

        with row1_col1:
            selected_category = st.selectbox(
                t["lbl_category"],
                options=available_categories,
                index=default_cat_idx,
                format_func=lambda c: cat_labels.get(c, c.value),
            )

        category_products = [p for p in products if p.category == selected_category]
        default_prod_idx = 0
        for idx, prod in enumerate(category_products):
            if "pasteur" in prod.name_en.lower() and "semi" in prod.name_en.lower():
                default_prod_idx = idx
                break

        with row1_col2:
            selected_product = st.selectbox(
                t["lbl_product"],
                options=category_products,
                index=default_prod_idx,
                format_func=lambda p: localize_product_name(p.name_en, lang),
            )

        with row1_col3:
            annual_tonnes = st.number_input(
                t["lbl_volume"],
                min_value=50,
                max_value=500_000,
                value=5_000,
                step=500,
                help=t["hlp_volume"],
            )
            annual_volume_kg = float(annual_tonnes) * 1_000.0

        compatible_ids = [
            cid
            for cid, cfg in presets.items()
            if selected_category in cfg.compatible_categories
        ]
        incompatible_ids = [cid for cid in presets if cid not in compatible_ids]
        ordered_preset_ids = compatible_ids + incompatible_ids

        default_base_id, default_alt_id = DEFAULT_PAIR_BY_CATEGORY.get(
            selected_category, ("PKG-HDPE-BOTTLE-1L", "PKG-RPET50-BOTTLE-1L")
        )
        if default_base_id not in ordered_preset_ids:
            default_base_id = ordered_preset_ids[0]
        if default_alt_id not in ordered_preset_ids or default_alt_id == default_base_id:
            default_alt_id = (
                ordered_preset_ids[1] if len(ordered_preset_ids) > 1 else ordered_preset_ids[0]
            )

        def _format_pkg_label(cid: str) -> str:
            cfg = presets[cid]
            loc_name = localize_preset_name(cid, cfg.name, lang)
            compat_tag = "" if cid in compatible_ids else t["lbl_check_compat"]
            return f"{loc_name}{compat_tag}"

        row2_col1, row2_col2, row2_col3 = st.columns([1.25, 1.25, 1.0], gap="medium")

        with row2_col1:
            baseline_id = st.selectbox(
                t["lbl_current_pkg"],
                options=ordered_preset_ids,
                index=ordered_preset_ids.index(default_base_id),
                format_func=_format_pkg_label,
                key=f"base_pkg_{selected_category.value}",
            )

        alt_candidates = [cid for cid in ordered_preset_ids if cid != baseline_id]
        default_alt_idx = (
            alt_candidates.index(default_alt_id) if default_alt_id in alt_candidates else 0
        )

        with row2_col2:
            proposed_id = st.selectbox(
                t["lbl_proposed_pkg"],
                options=alt_candidates,
                index=default_alt_idx,
                format_func=_format_pkg_label,
                key=f"prop_pkg_{selected_category.value}_{baseline_id}",
            )

        with row2_col3:
            comparison_years = int(
                st.selectbox(
                    t["lbl_period"],
                    options=[1, 3, 5, 7, 10],
                    index=2,
                    format_func=t["fmt_years"],
                )
            )

        # Optional financial & regional assumptions tucked cleanly inside an expander
        with st.expander(f":material/settings: {t['exp_assumptions']}"):
            a_col1, a_col2, a_col3, a_col4 = st.columns(4, gap="medium")
            with a_col1:
                capex_usd = st.number_input(
                    t["lbl_capex"],
                    min_value=0.0,
                    max_value=10_000_000.0,
                    value=45_000.0,
                    step=5_000.0,
                    help=t["hlp_capex"],
                )
                install_usd = st.number_input(
                    t["lbl_install"],
                    min_value=0.0,
                    max_value=2_000_000.0,
                    value=5_000.0,
                    step=1_000.0,
                )
            with a_col2:
                selling_price_per_kg = st.number_input(
                    t["lbl_selling_price"],
                    min_value=0.20,
                    max_value=30.0,
                    value=1.80,
                    step=0.10,
                    help=t["hlp_selling_price"],
                )
                raw_dairy_loss_cost = st.number_input(
                    t["lbl_spoilage_cost"],
                    min_value=0.10,
                    max_value=15.0,
                    value=0.85,
                    step=0.05,
                    help=t["hlp_spoilage_cost"],
                )
            with a_col3:
                resin_region = st.selectbox(
                    t["lbl_resin_region"],
                    options=list(RESIN_REGION_LABELS.keys()),
                    index=0,
                    format_func=lambda r: RESIN_REGION_LABELS[r].get(lang, r),
                )
                grid_key = st.selectbox(
                    t["lbl_grid"],
                    options=list(GRID_PRESETS.keys()),
                    index=0,
                    format_func=lambda gk: GRID_PRESETS[gk].get(lang, gk),
                )
                grid_intensity = GRID_VALUES[grid_key]
                grid_label = GRID_PRESETS[grid_key]["en"]
            with a_col4:
                discount_rate_pct = st.slider(
                    t["lbl_discount"],
                    min_value=0.0,
                    max_value=25.0,
                    value=10.0,
                    step=0.5,
                )
                reuse_return_rate_pct = st.slider(
                    t["lbl_return_rate"],
                    min_value=50.0,
                    max_value=99.0,
                    value=90.0,
                    step=1.0,
                    help=t["hlp_return_rate"],
                )
            proposed_mat_price_adj_pct = st.slider(
                t["lbl_mat_price_adj"],
                min_value=-30.0,
                max_value=30.0,
                value=0.0,
                step=1.0,
                help="Simulate supplier resin/board price discounts or premiums on the proposed packaging.",
            )

    # -------------------------------------------------------------------------
    # Run the real calculation pipeline
    # -------------------------------------------------------------------------
    assumptions = ScenarioAssumptions(
        functional_unit_saleable_kg=1000.0,
        annual_production_volume_kg=annual_volume_kg,
        grid_carbon_intensity_kgco2e_per_kwh=grid_intensity,
        grid_region_label=grid_label,
        net_selling_price_usd_per_kg=selling_price_per_kg,
        raw_dairy_loss_cost_usd_per_kg=raw_dairy_loss_cost,
        incremental_capex_usd=capex_usd,
        installation_commissioning_usd=install_usd,
        discount_rate=discount_rate_pct / 100.0,
        project_lifetime_years=comparison_years,
    )

    mat_mult = 1.0 + (proposed_mat_price_adj_pct / 100.0)
    baseline_cfg = _apply_package_overrides(
        presets[baseline_id], resin_region, reuse_return_rate_pct / 100.0, 1.0
    )
    proposed_cfg = _apply_package_overrides(
        presets[proposed_id], resin_region, reuse_return_rate_pct / 100.0, mat_mult
    )

    other_compatible_cfgs = [
        _apply_package_overrides(presets[cid], resin_region, reuse_return_rate_pct / 100.0, 1.0)
        for cid in compatible_ids
        if cid not in {baseline_id, proposed_id}
    ]
    all_comparisons = compare_scenarios(
        product=selected_product,
        baseline_config=baseline_cfg,
        alternative_configs=[proposed_cfg, *other_compatible_cfgs],
        assumptions=assumptions,
        catalog=catalog,
    )

    base_comp = all_comparisons[0]
    prop_comp = next(c for c in all_comparisons if c.package_config_id == proposed_id)

    base_env = base_comp.environmental
    prop_env = prop_comp.environmental
    base_econ = base_comp.economic
    prop_econ = prop_comp.economic

    # Scale per-FU (1,000 kg = 1 tonne) metrics to annual and comparison-period totals
    annual_fus = annual_volume_kg / assumptions.functional_unit_saleable_kg
    total_investment_usd = prop_comp.initial_investment_usd

    # Business annual & period figures
    base_annual_pkg_cost = base_econ.total_packaging_attributable_cost_per_fu * annual_fus
    prop_annual_pkg_cost = prop_econ.total_packaging_attributable_cost_per_fu * annual_fus
    annual_cost_diff = prop_annual_pkg_cost - base_annual_pkg_cost
    annual_incremental_cf = prop_comp.annual_cash_flow_savings
    period_net_benefit = prop_comp.cumulative_net_cash_flow_usd

    base_annual_margin = base_econ.contribution_margin_per_fu * annual_fus
    prop_annual_margin = prop_econ.contribution_margin_per_fu * annual_fus
    annual_margin_diff = prop_annual_margin - base_annual_margin

    # Environmental annual figures
    base_annual_pkg_co2_t = (base_env.packaging_system_total_gwp_kgco2e * annual_fus) / 1000.0
    prop_annual_pkg_co2_t = (prop_env.packaging_system_total_gwp_kgco2e * annual_fus) / 1000.0
    diff_annual_pkg_co2_t = prop_annual_pkg_co2_t - base_annual_pkg_co2_t

    base_annual_plastic_t = (base_env.virgin_fossil_plastic_mass_kg * annual_fus) / 1000.0
    prop_annual_plastic_t = (prop_env.virgin_fossil_plastic_mass_kg * annual_fus) / 1000.0
    diff_annual_plastic_t = prop_annual_plastic_t - base_annual_plastic_t
    diff_plastic_pct = (
        ((prop_annual_plastic_t - base_annual_plastic_t) / base_annual_plastic_t) * 100.0
        if base_annual_plastic_t > 0
        else (100.0 if prop_annual_plastic_t > 0 else 0.0)
    )

    base_annual_disposed_waste_t = (
        (base_env.waste_landfilled_kg + base_env.waste_incinerated_kg) * annual_fus
    ) / 1000.0
    prop_annual_disposed_waste_t = (
        (prop_env.waste_landfilled_kg + prop_env.waste_incinerated_kg) * annual_fus
    ) / 1000.0
    diff_annual_disposed_waste_t = prop_annual_disposed_waste_t - base_annual_disposed_waste_t
    diff_waste_pct = (
        (
            (prop_annual_disposed_waste_t - base_annual_disposed_waste_t)
            / base_annual_disposed_waste_t
        )
        * 100.0
        if base_annual_disposed_waste_t > 0
        else 0.0
    )

    base_annual_water_m3 = (base_env.packaging_and_washing_water_l * annual_fus) / 1000.0
    prop_annual_water_m3 = (prop_env.packaging_and_washing_water_l * annual_fus) / 1000.0
    diff_annual_water_m3 = prop_annual_water_m3 - base_annual_water_m3
    diff_water_pct = (
        ((prop_annual_water_m3 - base_annual_water_m3) / base_annual_water_m3) * 100.0
        if base_annual_water_m3 > 0
        else 0.0
    )

    base_annual_energy_gj = (base_env.packaging_system_energy_mj * annual_fus) / 1000.0
    prop_annual_energy_gj = (prop_env.packaging_system_energy_mj * annual_fus) / 1000.0
    diff_annual_energy_gj = prop_annual_energy_gj - base_annual_energy_gj
    diff_energy_pct = (
        ((prop_annual_energy_gj - base_annual_energy_gj) / base_annual_energy_gj) * 100.0
        if base_annual_energy_gj > 0
        else 0.0
    )

    # Localized names
    loc_product_name = localize_product_name(selected_product.name_en, lang)
    loc_base_pkg_name = localize_preset_name(baseline_id, baseline_cfg.name, lang)
    loc_prop_pkg_name = localize_preset_name(proposed_id, proposed_cfg.name, lang)
    loc_base_pkg_notes = localize_preset_notes(baseline_id, baseline_cfg.notes, lang)
    loc_prop_pkg_notes = localize_preset_notes(proposed_id, proposed_cfg.notes, lang)

    # -------------------------------------------------------------------------
    # 2. Decision Summary & Plain-Language Meaning (30-Second Executive Takeaway)
    # -------------------------------------------------------------------------
    decision = _classify_decision(prop_comp, t)

    plain_english_summary = build_plain_language_narrative(
        lang=lang,
        annual_tonnes=annual_tonnes,
        product_name=loc_product_name,
        base_pkg_name=loc_base_pkg_name,
        prop_pkg_name=loc_prop_pkg_name,
        diff_annual_pkg_co2_t=diff_annual_pkg_co2_t,
        delta_pkg_gwp_pct_str=_format_signed_pct(prop_comp.delta_packaging_gwp_pct),
        diff_annual_plastic_t=diff_annual_plastic_t,
        annual_cost_diff=annual_cost_diff,
        delta_cost_pct=prop_comp.delta_packaging_cost_pct,
        cost_diff_formatted=_format_currency(abs(annual_cost_diff)),
    )

    with st.container(border=True):
        top_left, top_right = st.columns([2.2, 1.0], gap="medium")
        with top_left:
            st.badge(
                decision["badge_text"],
                icon=decision["icon"],
                color=decision["badge_color"],
            )
            st.markdown(f"### {decision['verdict']}")
            st.markdown(plain_english_summary)
        with top_right, st.container(border=True):
            st.caption(t["cum_box_caption"](comparison_years))
            cum_co2_t = diff_annual_pkg_co2_t * comparison_years
            st.markdown(
                "\n".join(
                    [
                        t["cum_net_cash"](
                            comparison_years, _format_signed_currency(period_net_benefit)
                        ),
                        t["cum_co2"](comparison_years, cum_co2_t),
                        t["cum_plastic"](
                            comparison_years, diff_annual_plastic_t * comparison_years
                        ),
                    ]
                )
            )

        if not prop_comp.feasibility.is_feasible:
            st.error(
                " ; ".join(prop_comp.feasibility.violations),
                title=t["err_infeasible_title"],
                icon=":material/error:",
            )
        elif prop_comp.feasibility.warnings:
            st.warning(
                " ; ".join(prop_comp.feasibility.warnings),
                title=t["warn_operational_title"],
                icon=":material/info:",
            )

    # -------------------------------------------------------------------------
    # 3. Business Impact Section (Validated Incremental Cash Flow & Payback)
    # -------------------------------------------------------------------------
    st.markdown(f"### :material/payments: {t['sec2_title']}")
    st.caption(
        t["sec2_caption"](
            annual_tonnes,
            comparison_years,
            _format_currency(total_investment_usd),
            discount_rate_pct,
        )
    )

    b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5, gap="small")

    with b_col1:
        st.metric(
            label=t["m_prop_cost"],
            value=_format_currency(prop_annual_pkg_cost),
            delta=t["m_prop_cost_delta"](
                _format_signed_pct(prop_comp.delta_packaging_cost_pct),
                _format_currency(base_annual_pkg_cost),
            ),
            delta_color="inverse",
            border=True,
            help=t["m_prop_cost_help"],
        )

    with b_col2:
        st.metric(
            label=t["m_capex"],
            value=_format_currency(total_investment_usd),
            delta=t["m_capex_delta"](
                _format_currency(capex_usd), _format_currency(install_usd)
            ),
            delta_color="off",
            border=True,
            help=t["hlp_capex"],
        )

    with b_col3:
        st.metric(
            label=t["m_inc_cf"],
            value=t["m_savings_val"](_format_signed_currency(annual_incremental_cf)),
            delta=t["m_savings_delta"](
                _format_signed_currency(annual_incremental_cf * comparison_years),
                comparison_years,
            ),
            delta_color="normal" if annual_incremental_cf >= 0 else "inverse",
            border=True,
            help=t["m_savings_help"],
        )

    with b_col4:
        if (
            prop_comp.simple_payback_years is not None
            and prop_comp.simple_payback_months is not None
        ):
            payback_display = t["m_payback_yrs_mos"](
                prop_comp.simple_payback_years, prop_comp.simple_payback_months
            )
            payback_delta = (
                t["m_payback_no_capex"]
                if prop_comp.payback_status == "immediate"
                else t["m_payback_within"]
            )
            payback_color = "normal"
        else:
            payback_display = t["m_payback_none"]
            if (
                prop_comp.payback_status == "exceeds_horizon"
                and prop_comp.unconstrained_payback_years is not None
            ):
                payback_delta = (
                    f"{t['m_payback_exceeds'](comparison_years)} "
                    f"({prop_comp.unconstrained_payback_years:.1f} yrs)"
                )
            else:
                payback_delta = t["m_payback_cost_up"]
            payback_color = "off"

        st.metric(
            label=t["m_payback"],
            value=payback_display,
            delta=payback_delta,
            delta_color=payback_color,
            border=True,
            help=t["m_payback_help"](_format_currency(total_investment_usd)),
        )

    with b_col5:
        npv_val = prop_comp.npv_usd if prop_comp.npv_usd is not None else 0.0
        st.metric(
            label=t["m_cum_cf"](comparison_years),
            value=_format_signed_currency(period_net_benefit),
            delta=f"NPV: {_format_signed_currency(npv_val)} | Margin: {_format_signed_currency(annual_margin_diff)}/yr",
            delta_color="normal" if period_net_benefit >= 0 else "inverse",
            border=True,
            help=t["m_npv_help"],
        )

    # Clear Payback Explanation & Year-by-Year Cumulative Cash Flow Schedule
    localized_pb_explanation = localize_payback_explanation(
        lang=lang,
        payback_status=prop_comp.payback_status,
        initial_investment=total_investment_usd,
        annual_cf=annual_incremental_cf,
        horizon_years=comparison_years,
        payback_years=prop_comp.simple_payback_years,
        payback_months=prop_comp.simple_payback_months,
        unconstrained_years=prop_comp.unconstrained_payback_years,
        cum_net_cf=period_net_benefit,
        fallback_en=prop_comp.payback_explanation,
    )
    if prop_comp.simple_payback_years is not None:
        st.success(
            localized_pb_explanation,
            title=t["m_payback"],
            icon=":material/check_circle:",
        )
    else:
        st.warning(
            localized_pb_explanation,
            title=t["m_payback"],
            icon=":material/schedule:",
        )

    cf_exp = st.expander(f":material/timeline: {t['exp_cf_schedule']}", on_change="rerun")
    if cf_exp.open:
        with cf_exp:
            cf_years = list(range(comparison_years + 1))
            cf_schedule_df = pd.DataFrame(
                {
                    "Year": [f"Year {y}" for y in cf_years],
                    "Year_Num": cf_years,
                    "Annual Incremental Cash Flow ($)": [
                        -total_investment_usd if y == 0 else annual_incremental_cf for y in cf_years
                    ],
                    "Cumulative Net Cash Flow ($)": prop_comp.cumulative_cash_flow_schedule,
                }
            )
            cf_c1, cf_c2 = st.columns([1.4, 1.0], gap="medium")
            with cf_c1:
                cf_chart = (
                    alt.Chart(cf_schedule_df)
                    .mark_bar(cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("Year:N", sort=None, title=None),
                        y=alt.Y(
                            "Cumulative Net Cash Flow ($):Q",
                            title="Cumulative net cash flow ($)",
                        ),
                        color=alt.condition(
                            alt.datum["Cumulative Net Cash Flow ($)"] >= 0,
                            alt.value("#0f766e"),
                            alt.value("#dc2626"),
                        ),
                        tooltip=[
                            alt.Tooltip("Year:N"),
                            alt.Tooltip("Annual Incremental Cash Flow ($):Q", format="$,.0f"),
                            alt.Tooltip("Cumulative Net Cash Flow ($):Q", format="$,.0f"),
                        ],
                    )
                    .properties(height=220)
                )
                st.altair_chart(
                    cf_chart,
                    alt="Bar chart showing cumulative net cash flow from Year 0 CAPEX through the evaluation horizon.",
                )
            with cf_c2:
                st.dataframe(
                    cf_schedule_df[
                        [
                            "Year",
                            "Annual Incremental Cash Flow ($)",
                            "Cumulative Net Cash Flow ($)",
                        ]
                    ],
                    hide_index=True,
                    alt="Year-by-year incremental and cumulative net cash flow table.",
                    column_config={
                        "Annual Incremental Cash Flow ($)": st.column_config.NumberColumn(
                            format="$%+,.0f"
                        ),
                        "Cumulative Net Cash Flow ($)": st.column_config.NumberColumn(
                            format="$%+,.0f"
                        ),
                    },
                )

    # -------------------------------------------------------------------------
    # 4. Environmental Impact Section
    # -------------------------------------------------------------------------
    st.markdown(f"### :material/forest: {t['sec3_title']}")
    st.caption(t["sec3_caption"])

    e_col1, e_col2, e_col3, e_col4, e_col5 = st.columns(5, gap="small")

    with e_col1:
        st.metric(
            label=t["m_co2"],
            value=t["m_co2_val"](prop_annual_pkg_co2_t),
            delta=t["m_co2_delta"](
                diff_annual_pkg_co2_t,
                _format_signed_pct(prop_comp.delta_packaging_gwp_pct),
            ),
            delta_color="inverse",
            border=True,
            help=t["m_co2_help"](_format_signed_pct(prop_comp.delta_total_gwp_pct)),
        )

    with e_col2:
        st.metric(
            label=t["m_plastic"],
            value=t["m_plastic_val"](prop_annual_plastic_t),
            delta=t["m_plastic_delta"](
                diff_annual_plastic_t, _format_signed_pct(diff_plastic_pct)
            ),
            delta_color="inverse",
            border=True,
            help=t["m_plastic_help"],
        )

    with e_col3:
        st.metric(
            label=t["m_waste"],
            value=t["m_waste_val"](prop_annual_disposed_waste_t),
            delta=t["m_waste_delta"](
                diff_annual_disposed_waste_t, _format_signed_pct(diff_waste_pct)
            ),
            delta_color="inverse",
            border=True,
            help=t["m_waste_help"](prop_env.waste_recycled_kg * annual_fus / 1000.0),
        )

    with e_col4:
        st.metric(
            label=t["m_water"],
            value=t["m_water_val"](prop_annual_water_m3),
            delta=t["m_water_delta"](diff_annual_water_m3, _format_signed_pct(diff_water_pct)),
            delta_color="inverse",
            border=True,
            help=t["m_water_help"],
        )

    with e_col5:
        st.metric(
            label=t["m_energy"],
            value=t["m_energy_val"](prop_annual_energy_gj),
            delta=t["m_energy_delta"](
                diff_annual_energy_gj, _format_signed_pct(diff_energy_pct)
            ),
            delta_color="inverse",
            border=True,
            help=t["m_energy_help"],
        )

    # -------------------------------------------------------------------------
    # 5. Visual Comparison: Before vs. After Cards & Interactive Charts
    # -------------------------------------------------------------------------
    st.markdown(f"### :material/compare_arrows: {t['sec4_title']}")

    base_stats = _package_summary_stats(baseline_cfg, lang, t)
    prop_stats = _package_summary_stats(proposed_cfg, lang, t)

    card_left, card_right = st.columns(2, gap="medium")

    with card_left, st.container(border=True):
        st.badge(t["badge_current_card"], icon=":material/inventory_2:", color="gray")
        st.markdown(f"#### {loc_base_pkg_name}")
        st.caption(loc_base_pkg_notes)
        m1, m2, m3 = st.columns(3)
        m1.metric(
            t["lbl_cost_per_pkg"],
            f"${base_econ.cost_per_saleable_package:.3f}",
        )
        m2.metric(
            t["lbl_co2_per_pkg"],
            f"{base_env.gwp_per_package_kgco2e * 1000:,.0f} g CO₂e",
        )
        m3.metric(
            t["lbl_pkg_weight"],
            base_stats["total_mass_g"],
        )
        st.markdown(
            t["card_bullets"](
                base_stats["materials"],
                base_stats["format"],
                base_stats["recycled_content"],
                base_stats["eol_recycling"],
                base_stats["spoilage_rate"],
                base_env.product_loss_total_kg * annual_fus / 1000.0,
            )
        )

    with card_right, st.container(border=True):
        st.badge(
            t["badge_proposed_card"],
            icon=":material/check_circle:",
            color=decision["badge_color"],
        )
        st.markdown(f"#### {loc_prop_pkg_name}")
        st.caption(loc_prop_pkg_notes)
        p1, p2, p3 = st.columns(3)
        pkg_cost_diff = prop_econ.cost_per_saleable_package - base_econ.cost_per_saleable_package
        pkg_co2_diff_g = (
            prop_env.gwp_per_package_kgco2e - base_env.gwp_per_package_kgco2e
        ) * 1000.0
        mass_diff_g = proposed_cfg.total_bom_mass_g - baseline_cfg.total_bom_mass_g

        p1.metric(
            t["lbl_cost_per_pkg"],
            f"${prop_econ.cost_per_saleable_package:.3f}",
            delta=f"{pkg_cost_diff:+.3f} $",
            delta_color="inverse",
        )
        p2.metric(
            t["lbl_co2_per_pkg"],
            f"{prop_env.gwp_per_package_kgco2e * 1000:,.0f} g CO₂e",
            delta=f"{pkg_co2_diff_g:+,.0f} g CO₂e",
            delta_color="inverse",
        )
        p3.metric(
            t["lbl_pkg_weight"],
            prop_stats["total_mass_g"],
            delta=f"{mass_diff_g:+.1f} g",
            delta_color="off",
        )
        st.markdown(
            t["card_bullets"](
                prop_stats["materials"],
                prop_stats["format"],
                prop_stats["recycled_content"],
                prop_stats["eol_recycling"],
                prop_stats["spoilage_rate"],
                prop_env.product_loss_total_kg * annual_fus / 1000.0,
            )
        )

    # Visual Breakdown Charts (Cost & Carbon by driver)
    chart_col1, chart_col2 = st.columns(2, gap="medium")
    s_cur = t["scen_current"]
    s_prop = t["scen_proposed"]
    cd = t["cost_drivers"]
    cs = t["co2_stages"]

    with chart_col1, st.container(border=True):
        st.markdown(f"##### {t['chart_cost_title']}")
        cost_rows = [
            {
                "Driver": cd["raw"],
                "Scenario": s_cur,
                "Annual Cost ($)": base_econ.packaging_material_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["raw"],
                "Scenario": s_prop,
                "Annual Cost ($)": prop_econ.packaging_material_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["spoilage"],
                "Scenario": s_cur,
                "Annual Cost ($)": base_econ.product_loss_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["spoilage"],
                "Scenario": s_prop,
                "Annual Cost ($)": prop_econ.product_loss_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["freight"],
                "Scenario": s_cur,
                "Annual Cost ($)": base_econ.packaging_freight_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["freight"],
                "Scenario": s_prop,
                "Annual Cost ($)": prop_econ.packaging_freight_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["washing"],
                "Scenario": s_cur,
                "Annual Cost ($)": base_econ.packaging_washing_reuse_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["washing"],
                "Scenario": s_prop,
                "Annual Cost ($)": prop_econ.packaging_washing_reuse_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["waste"],
                "Scenario": s_cur,
                "Annual Cost ($)": base_econ.packaging_waste_net_cost_per_fu * annual_fus,
            },
            {
                "Driver": cd["waste"],
                "Scenario": s_prop,
                "Annual Cost ($)": prop_econ.packaging_waste_net_cost_per_fu * annual_fus,
            },
        ]
        cost_df = pd.DataFrame(cost_rows)
        cost_chart = (
            alt.Chart(cost_df)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                y=alt.Y("Driver:N", sort=None, title=None),
                x=alt.X("Annual Cost ($):Q", title=t["chart_cost_x"]),
                yOffset="Scenario:N",
                color=alt.Color(
                    "Scenario:N",
                    scale=alt.Scale(
                        domain=[s_cur, s_prop],
                        range=["#64748b", "#0f766e"],
                    ),
                    legend=alt.Legend(orient="top", title=None),
                ),
                tooltip=[
                    alt.Tooltip("Scenario:N"),
                    alt.Tooltip("Driver:N"),
                    alt.Tooltip("Annual Cost ($):Q", format="$,.0f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(
            cost_chart,
            alt="Grouped bar chart comparing annual packaging cost drivers between current and proposed packaging.",
        )

    with chart_col2, st.container(border=True):
        st.markdown(f"##### {t['chart_co2_title']}")
        co2_rows = [
            {
                "Stage": cs["raw"],
                "Scenario": s_cur,
                "Emissions (t CO2e/yr)": base_env.packaging_raw_material_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["raw"],
                "Scenario": s_prop,
                "Emissions (t CO2e/yr)": prop_env.packaging_raw_material_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["converting"],
                "Scenario": s_cur,
                "Emissions (t CO2e/yr)": base_env.packaging_conversion_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["converting"],
                "Scenario": s_prop,
                "Emissions (t CO2e/yr)": prop_env.packaging_conversion_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["spoilage"],
                "Scenario": s_cur,
                "Emissions (t CO2e/yr)": base_env.spoilage_attributable_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["spoilage"],
                "Scenario": s_prop,
                "Emissions (t CO2e/yr)": prop_env.spoilage_attributable_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["transport"],
                "Scenario": s_cur,
                "Emissions (t CO2e/yr)": base_env.packaging_transport_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["transport"],
                "Scenario": s_prop,
                "Emissions (t CO2e/yr)": prop_env.packaging_transport_gwp_kgco2e
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["washing_eol"],
                "Scenario": s_cur,
                "Emissions (t CO2e/yr)": (
                    base_env.packaging_reuse_washing_gwp_kgco2e + base_env.packaging_eol_gwp_kgco2e
                )
                * annual_fus
                / 1000.0,
            },
            {
                "Stage": cs["washing_eol"],
                "Scenario": s_prop,
                "Emissions (t CO2e/yr)": (
                    prop_env.packaging_reuse_washing_gwp_kgco2e + prop_env.packaging_eol_gwp_kgco2e
                )
                * annual_fus
                / 1000.0,
            },
        ]
        co2_df = pd.DataFrame(co2_rows)
        co2_chart = (
            alt.Chart(co2_df)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                y=alt.Y("Stage:N", sort=None, title=None),
                x=alt.X("Emissions (t CO2e/yr):Q", title=t["chart_co2_x"]),
                yOffset="Scenario:N",
                color=alt.Color(
                    "Scenario:N",
                    scale=alt.Scale(
                        domain=[s_cur, s_prop],
                        range=["#64748b", "#0f766e"],
                    ),
                    legend=alt.Legend(orient="top", title=None),
                ),
                tooltip=[
                    alt.Tooltip("Scenario:N"),
                    alt.Tooltip("Stage:N"),
                    alt.Tooltip("Emissions (t CO2e/yr):Q", format=",.1f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(
            co2_chart,
            alt="Grouped bar chart comparing annual packaging carbon emissions by stage between current and proposed packaging.",
        )

    # -------------------------------------------------------------------------
    # 6. Compare All Compatible Alternatives & Data Transparency
    # -------------------------------------------------------------------------
    all_exp = st.expander(f":material/leaderboard: {t['exp_all_options']}", on_change="rerun")
    if all_exp.open:
        with all_exp:
            st.caption(t["exp_all_caption"])
            alt_table_rows = []
            for comp in all_comparisons:
                if not comp.feasibility.is_feasible and comp.package_config_id != proposed_id:
                    continue
                verdict_info = (
                    {"verdict": t["verdict_baseline"]}
                    if comp.is_baseline
                    else _classify_decision(comp, t)
                )
                loc_opt_name = localize_preset_name(
                    comp.package_config_id, comp.package_config_name, lang
                )
                alt_table_rows.append(
                    {
                        t["col_option"]: loc_opt_name,
                        t["col_selection"]: (
                            t["scen_current"]
                            if comp.is_baseline
                            else (
                                t["scen_proposed"]
                                if comp.package_config_id == proposed_id
                                else t["scen_alt"]
                            )
                        ),
                        t["col_ann_cost"]: comp.economic.total_packaging_attributable_cost_per_fu
                        * annual_fus,
                        t["col_cost_diff"]: comp.delta_cost_per_fu * annual_fus,
                        t["col_co2"]: comp.environmental.packaging_system_total_gwp_kgco2e
                        * annual_fus
                        / 1000.0,
                        t["col_co2_pct"]: comp.delta_packaging_gwp_pct,
                        t["col_plastic"]: comp.environmental.virgin_fossil_plastic_mass_kg
                        * annual_fus
                        / 1000.0,
                        t["col_payback"]: (
                            f"{comp.simple_payback_years:.2f} yrs ({comp.simple_payback_months:.1f} mos)"
                            if comp.simple_payback_years is not None
                            and comp.simple_payback_months is not None
                            else ("—" if comp.is_baseline else t["m_payback_none"])
                        ),
                        t["col_decision"]: verdict_info["verdict"],
                    }
                )
            st.dataframe(
                pd.DataFrame(alt_table_rows),
                hide_index=True,
                alt="Comparison table of all compatible packaging alternatives.",
                column_config={
                    t["col_ann_cost"]: st.column_config.NumberColumn(format="$%.0f"),
                    t["col_cost_diff"]: st.column_config.NumberColumn(format="$%+.0f"),
                    t["col_co2"]: st.column_config.NumberColumn(format="%.1f t"),
                    t["col_co2_pct"]: st.column_config.NumberColumn(format="%+.1f%%"),
                    t["col_plastic"]: st.column_config.NumberColumn(format="%.1f t"),
                },
            )

    prov_exp = st.expander(f":material/verified_user: {t['exp_provenance']}", on_change="rerun")
    if prov_exp.open:
        with prov_exp:
            sens_df = run_one_at_a_time_sensitivity(
                selected_product, proposed_cfg, assumptions, catalog=catalog
            )
            u_col1, u_col2 = st.columns([1.2, 1.0], gap="medium")
            with u_col1:
                st.markdown(f"##### {t['sens_title']}")
                st.caption(t["sens_caption"](loc_prop_pkg_name, annual_tonnes))
                sens_display = pd.DataFrame(
                    {
                        t["col_sens_param"]: [
                            localize_sensitivity_label(
                                str(row["parameter_key"]), str(row["parameter_label"]), lang
                            )
                            for _, row in sens_df.iterrows()
                        ],
                        t["col_sens_cost"]: sens_df["cost_swing_usd_per_fu"] * annual_fus,
                        t["col_sens_co2"]: sens_df["gwp_swing_kgco2e_per_fu"]
                        * annual_fus
                        / 1000.0,
                    }
                )
                st.dataframe(
                    sens_display,
                    hide_index=True,
                    alt="One-at-a-time sensitivity analysis table for cost and carbon drivers.",
                    column_config={
                        t["col_sens_cost"]: st.column_config.NumberColumn(format="±$%.0f"),
                        t["col_sens_co2"]: st.column_config.NumberColumn(format="±%.1f t"),
                    },
                )
            with u_col2:
                st.markdown(f"##### {t['prov_title']}")
                st.info(
                    t["prov_body"],
                    title=t["prov_alert_title"],
                    icon=":material/menu_book:",
                )
                md_report = generate_scenario_markdown_report(
                    selected_product, assumptions, [base_comp, prop_comp], sens_df
                )
                st.download_button(
                    label=t["btn_download"],
                    data=md_report,
                    file_name=f"dairyeco_transition_{selected_product.product_id}_{proposed_id}.md",
                    mime="text/markdown",
                    icon=":material/download:",
                )

    # -------------------------------------------------------------------------
    # 7. Dedicated Developer Mode (only rendered when toggled ON)
    # -------------------------------------------------------------------------
    if dev_mode_enabled:
        render_developer_mode(
            selected_product=selected_product,
            baseline_cfg=baseline_cfg,
            proposed_cfg=proposed_cfg,
            assumptions=assumptions,
            base_comp=base_comp,
            prop_comp=prop_comp,
        )


if __name__ == "__main__":
    main()
