"""Deterministic BOM-based Packaging & Dairy Life-Cycle Assessment (LCA) Engine.

Implements vision.md Section 3 & Section 7:
- Primary functional unit: 1,000 kg of saleable dairy product delivered.
- Distinct boundaries for (a) Packaging-system assessment and (b) Dairy-manufacturing assessment.
- Subtracts AGRIBALYSE's embedded baseline packaging (`Emballage` stage) before adding custom
  BOM packaging so packaging is never double-counted.
- Models reusable containers (effective trips from return rate, breakage, and max trip cap;
  washing water, thermal & electric energy; reverse logistics).
- Avoids double-counting recycled content and end-of-life credits (cut-off allocation).
- Validates hard technical feasibility constraints and checks against IFC packaging mass benchmarks.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from dairyeco.config import PROCESSED_DIR, REFERENCE_DIR
from dairyeco.domain.models import (
    FOSSIL_PLASTIC_MATERIALS,
    POLYMER_MATERIALS,
    ConversionProcess,
    DairyCategory,
    DairyProductRecord,
    DataSourceType,
    EnvironmentalResult,
    FeasibilityCheckResult,
    MaterialFamily,
    PackageComponentBOM,
    PackageConfiguration,
    PackageFormat,
    ProvenanceRecord,
    ScenarioAssumptions,
)

# Engineering packaging mass plausibility bounds (g packaging / kg dairy product)
PACKAGING_MASS_SANITY_BOUNDS_G_PER_KG: dict[DairyCategory, tuple[float, float]] = {
    DairyCategory.FLUID_MILK: (3.5, 35.0),
    DairyCategory.YOGURT_KEFIR: (3.5, 45.0),
    DairyCategory.CHEESE: (8.0, 30.0),
    DairyCategory.MILK_POWDER: (8.0, 29.0),
    DairyCategory.BUTTER: (4.0, 35.0),
    DairyCategory.CREAM: (5.0, 40.0),
    DairyCategory.ICE_CREAM: (10.0, 60.0),
    DairyCategory.OTHER_DAIRY: (3.5, 50.0),
}
IFC_PACKAGING_BOUNDS_G_PER_KG = PACKAGING_MASS_SANITY_BOUNDS_G_PER_KG

US_BASELINE_GRID_CI_KGCO2E_PER_KWH = 0.466
EU_BASELINE_GRID_CI_KGCO2E_PER_KWH = 0.285


@lru_cache(maxsize=4)
def load_ifc_plant_benchmarks(reference_dir: Path = REFERENCE_DIR) -> pd.DataFrame:
    """Load IFC/World Bank (2007) Dairy Processing EHS benchmark table."""
    return pd.read_csv(reference_dir / "ifc_dairy_benchmarks.csv")


def compute_packaging_transport_tkm(
    package_config: PackageConfiguration,
    total_pkg_mass_kg: float,
    gross_packages_filled: float,
) -> tuple[float, float, float]:
    """Compute (inbound_tkm, outbound_tare_tkm, reverse_tkm) with reusable-only reverse mass."""
    filled_tare_mass_kg = (package_config.total_bom_mass_g / 1000.0) * gross_packages_filled
    inbound_tkm = (total_pkg_mass_kg / 1000.0) * package_config.supplier_to_plant_distance_km
    outbound_pkg_tkm = (filled_tare_mass_kg / 1000.0) * package_config.distribution_distance_km
    reverse_tkm = 0.0
    if package_config.reuse.is_reusable and package_config.reuse.reverse_transport_distance_km > 0:
        reusable_unit_mass_g = sum(
            c.mass_g_per_package
            for c in package_config.components
            if package_config.is_reusable_component(c)
        )
        returned_mass_kg = (
            (reusable_unit_mass_g / 1000.0)
            * gross_packages_filled
            * package_config.reuse.return_rate
        )
        reverse_tkm = (returned_mass_kg / 1000.0) * package_config.reuse.reverse_transport_distance_km
    return inbound_tkm, outbound_pkg_tkm, reverse_tkm

PAPER_BOARD_MATERIALS: frozenset[MaterialFamily] = frozenset(
    {
        MaterialFamily.PAPERBOARD,
        MaterialFamily.CORRUGATED_BOARD,
        MaterialFamily.LIQUID_PACKAGING_BOARD,
    }
)


class FactorCatalog:
    """O(1)-indexed in-memory lookup over data/processed/packaging_impact_factors.csv."""

    def __init__(self, factors_df: pd.DataFrame | None = None) -> None:
        if factors_df is None:
            factors_df = pd.read_csv(PROCESSED_DIR / "packaging_impact_factors.csv")
        self.df = factors_df

        self._virgin_by_mat_reg: dict[tuple[str, str], dict[str, Any]] = {}
        self._virgin_by_mat: dict[str, dict[str, Any]] = {}
        self._recycled_by_mat: dict[str, dict[str, Any]] = {}
        self._conversion_by_proc: dict[str, dict[str, Any]] = {}
        self._transport_by_mode: dict[str, dict[str, Any]] = {}
        self._eol_by_proc: dict[str, dict[str, Any]] = {}

        for record in factors_df.to_dict(orient="records"):
            dom = str(record["domain"])
            mat = str(record["material_or_process"])
            sub = str(record["pathway_or_subtype"])
            geo = str(record["geography"]).lower()
            if dom == "material_production":
                if sub == "virgin_resin_baseline":
                    self._virgin_by_mat_reg[(mat, geo)] = record
                    if mat not in self._virgin_by_mat or geo == "cross-regional average":
                        self._virgin_by_mat[mat] = record
                elif sub == "mechanically_recycled_resin":
                    self._recycled_by_mat[mat] = record
            elif dom == "package_conversion":
                self._conversion_by_proc[mat] = record
            elif dom == "transport":
                self._transport_by_mode[mat] = record
            elif dom == "end_of_life":
                self._eol_by_proc[mat] = record

    def get_virgin_material_factor(
        self, material: MaterialFamily, region: str = "Cross-regional average"
    ) -> dict[str, Any]:
        mat_key = str(material)
        exact = self._virgin_by_mat_reg.get((mat_key, region.lower()))
        if exact is not None:
            return exact
        fallback = self._virgin_by_mat.get(mat_key)
        if fallback is not None:
            return fallback
        raise KeyError(f"No virgin material factor found for {material}")

    def get_recycled_material_factor(
        self, material: MaterialFamily, region: str = "Cross-regional average"
    ) -> dict[str, Any]:
        mat_key = str(material)
        rec = self._recycled_by_mat.get(mat_key)
        if rec is not None:
            return rec
        virgin = dict(self.get_virgin_material_factor(material, region))
        virgin["gwp_kgco2e_per_unit"] = round(float(virgin["gwp_kgco2e_per_unit"]) * 0.65, 4)
        virgin["fossil_energy_mj_per_unit"] = round(
            float(virgin["fossil_energy_mj_per_unit"]) * 0.50, 4
        )
        virgin["source_type"] = str(DataSourceType.PROXY)
        virgin["notes"] = f"Fallback recycled factor proxy for {material}"
        return virgin

    def get_conversion_factor(self, process: ConversionProcess) -> dict[str, Any]:
        conv = self._conversion_by_proc.get(str(process))
        if conv is None:
            raise KeyError(f"No conversion factor found for {process}")
        return conv

    def get_transport_factor(self, mode: str) -> dict[str, Any]:
        return self._transport_by_mode.get(
            mode, self._transport_by_mode["combination_truck"]
        )

    def get_eol_factors_for_material(
        self, material: MaterialFamily
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        rec_row = self._eol_by_proc["mrf_sorting"]
        if material in POLYMER_MATERIALS:
            return (
                rec_row,
                self._eol_by_proc["incineration_plastics"],
                self._eol_by_proc["landfill_plastics"],
            )
        if material in PAPER_BOARD_MATERIALS:
            return (
                rec_row,
                self._eol_by_proc["incineration_paperboard"],
                self._eol_by_proc["landfill_paperboard"],
            )
        return (
            rec_row,
            self._eol_by_proc["incineration_inert"],
            self._eol_by_proc["landfill_glass_metal"],
        )


@lru_cache(maxsize=4)
def get_default_factor_catalog(processed_dir: Path = PROCESSED_DIR) -> FactorCatalog:
    """Return cached FactorCatalog loaded from `processed_dir`."""
    return FactorCatalog(pd.read_csv(processed_dir / "packaging_impact_factors.csv"))


def check_scenario_feasibility(
    product: DairyProductRecord,
    package_config: PackageConfiguration,
) -> FeasibilityCheckResult:
    """Evaluate hard technical, food-safety, and barrier feasibility constraints."""
    violations: list[str] = []
    warnings: list[str] = []

    if (
        package_config.compatible_categories
        and product.category not in package_config.compatible_categories
    ):
        violations.append(
            f"Package '{package_config.name}' ({package_config.package_format}) is not compatible "
            f"with dairy category '{product.category}' (compatible: "
            f"{[str(c) for c in package_config.compatible_categories]})."
        )

    if "ambiant" in product.delivery_mode.lower() and not package_config.high_barrier:
        violations.append(
            f"Ambient long-shelf-life product '{product.name_en}' requires a high-barrier "
            f"package, but '{package_config.name}' has high_barrier=False."
        )

    if product.category == DairyCategory.FLUID_MILK and package_config.package_format in {
        PackageFormat.FILM_WRAP,
        PackageFormat.SACK,
    }:
        violations.append(
            f"Fluid milk cannot be packaged in '{package_config.package_format}' due to liquid containment."
        )

    for comp in package_config.components:
        if (
            not comp.is_secondary_or_tertiary
            and comp.recycled_content_fraction > 0.50
            and comp.material_family in {MaterialFamily.HDPE, MaterialFamily.LDPE, MaterialFamily.PP}
        ):
            warnings.append(
                f"Component '{comp.component_name}' uses {comp.recycled_content_fraction*100:.0f}% "
                f"mechanically recycled {comp.material_family} in primary food contact; verify "
                "food-grade decontamination certification or functional barrier layer."
            )

    if package_config.reuse.is_reusable and package_config.reuse.return_rate < 0.75:
        warnings.append(
            f"Reusable package return rate ({package_config.reuse.return_rate*100:.1f}%) is below "
            f"75%, resulting in only {package_config.reuse.effective_trips:.2f} effective trips per container."
        )

    return FeasibilityCheckResult(
        is_feasible=len(violations) == 0,
        violations=violations,
        warnings=warnings,
    )


def evaluate_component_lca(
    comp: PackageComponentBOM,
    new_containers_for_fu: float,
    filled_packages_for_fu: float,
    is_reusable_body: bool,
    catalog: FactorCatalog,
    grid_ci_kgco2e_per_kwh: float,
) -> tuple[dict[str, Any], list[ProvenanceRecord]]:
    """Calculate material, conversion, and EoL impacts for a single BOM component."""
    effective_units = new_containers_for_fu if is_reusable_body else filled_packages_for_fu
    total_mass_kg = (comp.mass_g_per_package / 1000.0) * effective_units

    rec_frac = comp.recycled_content_fraction
    virgin_mass_kg = total_mass_kg * (1.0 - rec_frac)
    recycled_mass_kg = total_mass_kg * rec_frac
    virgin_fossil_plastic_kg = (
        virgin_mass_kg if comp.material_family in FOSSIL_PLASTIC_MATERIALS else 0.0
    )

    v_factor = catalog.get_virgin_material_factor(comp.material_family, comp.resin_region)
    r_factor = catalog.get_recycled_material_factor(comp.material_family, comp.resin_region)
    conv_factor = catalog.get_conversion_factor(comp.conversion_process)
    eol_rec, eol_inc, eol_lf = catalog.get_eol_factors_for_material(comp.material_family)

    # Adjust conversion GWP for scenario electricity grid intensity vs source region baseline
    base_grid_ci = (
        EU_BASELINE_GRID_CI_KGCO2E_PER_KWH
        if str(conv_factor.get("geography", "")).startswith("FR")
        else US_BASELINE_GRID_CI_KGCO2E_PER_KWH
    )
    conv_elec_kwh_per_kg = float(conv_factor["electricity_kwh_per_unit"])
    conv_gwp_per_kg = max(
        0.0,
        float(conv_factor["gwp_kgco2e_per_unit"])
        + conv_elec_kwh_per_kg * (grid_ci_kgco2e_per_kwh - base_grid_ci),
    )

    mat_gwp = (
        virgin_mass_kg * float(v_factor["gwp_kgco2e_per_unit"])
        + recycled_mass_kg * float(r_factor["gwp_kgco2e_per_unit"])
    )
    conv_gwp = total_mass_kg * conv_gwp_per_kg

    waste_rec_kg = total_mass_kg * comp.eol_recycling_fraction
    waste_inc_kg = total_mass_kg * comp.eol_incineration_fraction
    waste_lf_kg = total_mass_kg * comp.eol_landfill_fraction

    eol_gwp = (
        waste_rec_kg * float(eol_rec["gwp_kgco2e_per_unit"])
        + waste_inc_kg * float(eol_inc["gwp_kgco2e_per_unit"])
        + waste_lf_kg * float(eol_lf["gwp_kgco2e_per_unit"])
    )
    energy_mj = (
        virgin_mass_kg * float(v_factor["fossil_energy_mj_per_unit"])
        + recycled_mass_kg * float(r_factor["fossil_energy_mj_per_unit"])
        + total_mass_kg * float(conv_factor["fossil_energy_mj_per_unit"])
        + waste_rec_kg * float(eol_rec["fossil_energy_mj_per_unit"])
        + waste_inc_kg * float(eol_inc["fossil_energy_mj_per_unit"])
        + waste_lf_kg * float(eol_lf["fossil_energy_mj_per_unit"])
    )
    water_l = (
        virgin_mass_kg * float(v_factor["water_l_per_unit"])
        + recycled_mass_kg * float(r_factor["water_l_per_unit"])
        + total_mass_kg * float(conv_factor["water_l_per_unit"])
    )

    prov_list = [
        ProvenanceRecord(
            source_dataset_id=str(v_factor["source_dataset_id"]),
            source_record_id=str(v_factor["source_record_id"]),
            source_type=DataSourceType(str(v_factor["source_type"])),
            geography=str(v_factor["geography"]),
            reference_year=str(v_factor["reference_year"]),
            lcia_method=str(v_factor["lcia_method"]),
            system_boundary=str(v_factor["system_boundary"]),
            original_unit=str(v_factor["original_unit"]),
            notes=f"Component '{comp.component_name}' ({comp.material_family}): {v_factor['notes']}",
        )
    ]

    summary = {
        "component_name": comp.component_name,
        "material_family": str(comp.material_family),
        "mass_g_per_package": comp.mass_g_per_package,
        "is_reusable_amortized": is_reusable_body,
        "total_mass_kg_per_fu": round(total_mass_kg, 4),
        "virgin_fossil_plastic_kg_per_fu": round(virgin_fossil_plastic_kg, 4),
        "recycled_content_kg_per_fu": round(recycled_mass_kg, 4),
        "material_gwp_kgco2e": round(mat_gwp, 4),
        "conversion_gwp_kgco2e": round(conv_gwp, 4),
        "eol_gwp_kgco2e": round(eol_gwp, 4),
        "total_component_gwp_kgco2e": round(mat_gwp + conv_gwp + eol_gwp, 4),
        "energy_mj": round(energy_mj, 4),
        "water_l": round(water_l, 4),
        "waste_recycled_kg": round(waste_rec_kg, 4),
        "waste_incinerated_kg": round(waste_inc_kg, 4),
        "waste_landfilled_kg": round(waste_lf_kg, 4),
    }
    return summary, prov_list


def evaluate_environmental_lca(
    product: DairyProductRecord,
    package_config: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    catalog: FactorCatalog | None = None,
) -> EnvironmentalResult:
    """Execute complete deterministic environmental LCA per functional unit (1,000 kg saleable)."""
    if catalog is None:
        catalog = get_default_factor_catalog()

    fu_kg = assumptions.functional_unit_saleable_kg
    saleable_packages = fu_kg / package_config.net_fill_mass_kg
    loss_multiplier = package_config.gross_fill_multiplier
    gross_packages_filled = saleable_packages * loss_multiplier
    product_loss_kg = fu_kg * (loss_multiplier - 1.0)

    eff_trips = package_config.reuse.effective_trips
    new_containers_for_fu = gross_packages_filled / eff_trips

    comp_breakdowns: list[dict[str, Any]] = []
    provenances: list[ProvenanceRecord] = [
        ProvenanceRecord(
            source_dataset_id=product.source_dataset_id,
            source_record_id=product.product_id,
            source_type=product.source_type,
            geography="FR",
            reference_year="2024/2025",
            lcia_method="EF 3.1 (adapted) V1.00",
            system_boundary="Cradle-to-grave with Emballage stage subtracted",
            original_unit="kg CO2 eq / kg product",
            notes=f"De-packaged baseline dairy product '{product.name_en}'",
        )
    ]

    raw_mat_gwp = conv_gwp = eol_gwp = pkg_energy_mj = pkg_water_l = 0.0
    total_pkg_mass_kg = virgin_plastic_kg = recycled_mass_kg = 0.0
    w_rec_kg = w_inc_kg = w_lf_kg = 0.0

    for comp in package_config.components:
        comp_res, comp_prov = evaluate_component_lca(
            comp=comp,
            new_containers_for_fu=new_containers_for_fu,
            filled_packages_for_fu=gross_packages_filled,
            is_reusable_body=package_config.is_reusable_component(comp),
            catalog=catalog,
            grid_ci_kgco2e_per_kwh=assumptions.grid_carbon_intensity_kgco2e_per_kwh,
        )
        comp_breakdowns.append(comp_res)
        provenances.extend(comp_prov)

        raw_mat_gwp += comp_res["material_gwp_kgco2e"]
        conv_gwp += comp_res["conversion_gwp_kgco2e"]
        eol_gwp += comp_res["eol_gwp_kgco2e"]
        pkg_energy_mj += comp_res["energy_mj"]
        pkg_water_l += comp_res["water_l"]
        total_pkg_mass_kg += comp_res["total_mass_kg_per_fu"]
        virgin_plastic_kg += comp_res["virgin_fossil_plastic_kg_per_fu"]
        recycled_mass_kg += comp_res["recycled_content_kg_per_fu"]
        w_rec_kg += comp_res["waste_recycled_kg"]
        w_inc_kg += comp_res["waste_incinerated_kg"]
        w_lf_kg += comp_res["waste_landfilled_kg"]

    t_factor = catalog.get_transport_factor(package_config.transport_mode)
    t_gwp_per_tkm = float(t_factor["gwp_kgco2e_per_unit"])
    t_mj_per_tkm = float(t_factor["fossil_energy_mj_per_unit"])

    inbound_tkm, outbound_pkg_tkm, reverse_tkm = compute_packaging_transport_tkm(
        package_config=package_config,
        total_pkg_mass_kg=total_pkg_mass_kg,
        gross_packages_filled=gross_packages_filled,
    )

    total_pkg_tkm = inbound_tkm + outbound_pkg_tkm + reverse_tkm
    pkg_transport_gwp = total_pkg_tkm * t_gwp_per_tkm
    pkg_energy_mj += total_pkg_tkm * t_mj_per_tkm

    washing_gwp = 0.0
    if package_config.reuse.is_reusable and eff_trips > 1.0:
        washed_units = gross_packages_filled * package_config.reuse.return_rate
        wash_elec_kwh = washed_units * package_config.reuse.washing_electricity_kwh_per_package
        wash_therm_mj = washed_units * package_config.reuse.washing_thermal_energy_mj_per_package
        wash_water_l = washed_units * package_config.reuse.washing_water_l_per_package

        washing_gwp = (
            wash_elec_kwh * assumptions.grid_carbon_intensity_kgco2e_per_kwh
            + wash_therm_mj * 0.068
        )
        pkg_energy_mj += wash_elec_kwh * 3.6 + wash_therm_mj
        pkg_water_l += wash_water_l

    spoilage_gwp = product_loss_kg * product.non_packaging_gwp_kgco2e_per_kg
    pkg_system_total_gwp = (
        raw_mat_gwp + conv_gwp + pkg_transport_gwp + washing_gwp + eol_gwp + spoilage_gwp
    )

    dairy_base_gwp = (
        fu_kg * product.non_packaging_gwp_kgco2e_per_kg
        if assumptions.include_dairy_processing_boundary
        else 0.0
    )
    combined_gwp = dairy_base_gwp + pkg_system_total_gwp

    plant_energy_mj = (
        fu_kg
        * (
            assumptions.plant_electricity_kwh_per_kg_product * 3.6
            + assumptions.plant_thermal_mj_per_kg_product
        )
        if assumptions.include_dairy_processing_boundary
        else 0.0
    )
    plant_water_l = (
        fu_kg * assumptions.plant_water_l_per_kg_product
        if assumptions.include_dairy_processing_boundary
        else 0.0
    )

    effective_pkg_g_per_kg_product = (total_pkg_mass_kg * 1000.0) / fu_kg
    low_b, high_b = PACKAGING_MASS_SANITY_BOUNDS_G_PER_KG.get(product.category, (3.5, 50.0))
    if effective_pkg_g_per_kg_product < low_b:
        ifc_status = (
            f"below_engineering_range ({effective_pkg_g_per_kg_product:.1f} g/kg < "
            f"typical {low_b:.1f}-{high_b:.1f} g/kg)"
        )
    elif effective_pkg_g_per_kg_product > high_b:
        ifc_status = (
            f"above_engineering_range ({effective_pkg_g_per_kg_product:.1f} g/kg > "
            f"typical {low_b:.1f}-{high_b:.1f} g/kg; typical for heavy glass or small single-serve)"
        )
    else:
        ifc_status = (
            f"within_engineering_range ({effective_pkg_g_per_kg_product:.1f} g/kg in "
            f"typical {low_b:.1f}-{high_b:.1f} g/kg)"
        )

    return EnvironmentalResult(
        functional_unit_kg=fu_kg,
        packages_required_for_fu=round(saleable_packages, 2),
        new_containers_manufactured_for_fu=round(new_containers_for_fu, 2),
        effective_reuse_trips=round(eff_trips, 3),
        packaging_raw_material_gwp_kgco2e=round(raw_mat_gwp, 3),
        packaging_conversion_gwp_kgco2e=round(conv_gwp, 3),
        packaging_transport_gwp_kgco2e=round(pkg_transport_gwp, 3),
        packaging_reuse_washing_gwp_kgco2e=round(washing_gwp, 3),
        packaging_eol_gwp_kgco2e=round(eol_gwp, 3),
        spoilage_attributable_gwp_kgco2e=round(spoilage_gwp, 3),
        packaging_system_total_gwp_kgco2e=round(pkg_system_total_gwp, 3),
        dairy_non_packaging_base_gwp_kgco2e=round(dairy_base_gwp, 3),
        combined_total_gwp_kgco2e=round(combined_gwp, 3),
        gwp_per_kg_saleable_product=round(combined_gwp / fu_kg, 5),
        gwp_per_package_kgco2e=round(pkg_system_total_gwp / saleable_packages, 5),
        packaging_system_energy_mj=round(pkg_energy_mj, 2),
        plant_processing_energy_mj=round(plant_energy_mj, 2),
        total_energy_mj=round(pkg_energy_mj + plant_energy_mj, 2),
        packaging_and_washing_water_l=round(pkg_water_l, 2),
        plant_processing_water_l=round(plant_water_l, 2),
        total_water_l=round(pkg_water_l + plant_water_l, 2),
        total_packaging_mass_kg=round(total_pkg_mass_kg, 3),
        virgin_fossil_plastic_mass_kg=round(virgin_plastic_kg, 3),
        recycled_content_mass_kg=round(recycled_mass_kg, 3),
        waste_recycled_kg=round(w_rec_kg, 3),
        waste_incinerated_kg=round(w_inc_kg, 3),
        waste_landfilled_kg=round(w_lf_kg, 3),
        product_loss_total_kg=round(product_loss_kg, 3),
        ifc_packaging_mass_benchmark_status=ifc_status,
        component_breakdown=comp_breakdowns,
        provenance_records=provenances,
    )
