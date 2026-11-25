"""Canonical domain entities, enums, and provenance contracts for DairyEco AI."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DataSourceType(StrEnum):
    """Explicit epistemic classification required by vision.md Section 3 & 5."""

    MEASURED = "measured"
    PUBLISHED_REFERENCE = "published_reference"
    PROXY = "proxy"
    ASSUMED = "assumed"
    SYNTHETIC = "synthetic"
    MODEL_DERIVED = "model_derived"


class DairyCategory(StrEnum):
    """Supported dairy product categories in reliable source data."""

    FLUID_MILK = "fluid_milk"
    YOGURT_KEFIR = "yogurt_kefir"
    CHEESE = "cheese"
    BUTTER = "butter"
    CREAM = "cream"
    ICE_CREAM = "ice_cream"
    MILK_POWDER = "milk_powder"
    OTHER_DAIRY = "other_dairy"


class PackageFormat(StrEnum):
    """Supported dairy packaging formats."""

    BOTTLE = "bottle"
    CARTON = "carton"
    CUP = "cup"
    POUCH = "pouch"
    FILM_WRAP = "film_wrap"
    TUB = "tub"
    JAR = "jar"
    SACK = "sack"


class MaterialFamily(StrEnum):
    """Supported packaging material families."""

    HDPE = "HDPE"
    LDPE = "LDPE"
    LLDPE = "LLDPE"
    PET = "PET"
    PP = "PP"
    PVC = "PVC"
    GPPS = "GPPS"
    HIPS = "HIPS"
    EPS = "EPS"
    PLA = "PLA"
    PAPERBOARD = "paperboard"
    CORRUGATED_BOARD = "corrugated_board"
    LIQUID_PACKAGING_BOARD = "liquid_packaging_board"
    GLASS = "glass"
    ALUMINIUM = "aluminium"


POLYMER_MATERIALS: frozenset[MaterialFamily] = frozenset(
    {
        MaterialFamily.HDPE,
        MaterialFamily.LDPE,
        MaterialFamily.LLDPE,
        MaterialFamily.PET,
        MaterialFamily.PP,
        MaterialFamily.PVC,
        MaterialFamily.GPPS,
        MaterialFamily.HIPS,
        MaterialFamily.EPS,
        MaterialFamily.PLA,
    }
)

FOSSIL_PLASTIC_MATERIALS: frozenset[MaterialFamily] = frozenset(
    POLYMER_MATERIALS - {MaterialFamily.PLA}
)


class ConversionProcess(StrEnum):
    """Package converting process applied to raw resin, board, glass, or metal."""

    BLOW_MOLDING = "blow_molding"
    INJECTION_MOLDING = "injection_molding"
    THERMOFORMING = "thermoforming"
    FILM_EXTRUSION = "film_extrusion"
    CARTON_CONVERTING = "carton_converting"
    CORRUGATED_CONVERTING = "corrugated_converting"
    GLASS_FORMING = "glass_forming"
    ALUMINIUM_FOIL_ROLLING = "aluminium_foil_rolling"
    NONE = "none"


class ProvenanceRecord(BaseModel):
    """Traceability record attached to every factor and calculated output."""

    source_dataset_id: str
    source_record_id: str
    source_type: DataSourceType
    geography: str
    reference_year: str
    lcia_method: str
    system_boundary: str
    original_unit: str
    notes: str = ""


class DairyProductRecord(BaseModel):
    """Normalized finished dairy product LCA record from AGRIBALYSE 3.2."""

    product_id: str
    code_agb: str
    name_fr: str
    name_en: str
    category: DairyCategory
    agribalyse_group: str
    agribalyse_subgroup: str
    delivery_mode: str
    baseline_packaging_approach: str
    functional_unit: str = "1 kg of food product consumed at consumer"
    total_gwp_kgco2e_per_kg: float
    non_packaging_gwp_kgco2e_per_kg: float
    agriculture_gwp_kgco2e_per_kg: float
    transformation_gwp_kgco2e_per_kg: float
    packaging_stage_gwp_kgco2e_per_kg: float
    transport_gwp_kgco2e_per_kg: float
    distribution_gwp_kgco2e_per_kg: float
    consumption_gwp_kgco2e_per_kg: float
    single_score_mpt_per_kg: float
    water_depletion_m3_per_kg: float
    fossil_energy_mj_per_kg: float
    milk_yield_kg_milk_per_kg_product: float | None = None
    density_kg_per_l: float | None = None
    source_type: DataSourceType = DataSourceType.PUBLISHED_REFERENCE
    source_dataset_id: str = "agribalyse_3_2"


class ImpactFactorRecord(BaseModel):
    """Normalized material, conversion, energy, transport, or EoL impact factor."""

    factor_id: str
    domain: str
    material_or_process: str
    pathway_or_subtype: str
    geography: str
    reference_year: str
    gwp_kgco2e_per_unit: float
    fossil_energy_mj_per_unit: float
    water_l_per_unit: float
    electricity_kwh_per_unit: float = 0.0
    unit: str
    original_value: float
    original_unit: str
    functional_unit: str
    system_boundary: str
    lcia_method: str
    source_dataset_id: str
    source_record_id: str
    source_type: DataSourceType
    notes: str = ""


class PackageComponentBOM(BaseModel):
    """Single physical component of a package Bill of Materials (BOM)."""

    component_name: str = Field(..., description="e.g., body, cap, label, liner, foil_layer, case")
    material_family: MaterialFamily
    mass_g_per_package: float = Field(..., gt=0.0)
    recycled_content_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    conversion_process: ConversionProcess = ConversionProcess.NONE
    resin_region: str = Field(
        default="Cross-regional average",
        description="Region for NIST polymer factors: Western Europe, USA, China, MENA, or Cross-regional average",
    )
    unit_price_usd_per_kg: float = Field(default=1.50, ge=0.0)
    price_source_type: DataSourceType = DataSourceType.ASSUMED
    eol_recycling_fraction: float = Field(default=0.20, ge=0.0, le=1.0)
    eol_incineration_fraction: float = Field(default=0.20, ge=0.0, le=1.0)
    eol_landfill_fraction: float = Field(default=0.60, ge=0.0, le=1.0)
    is_secondary_or_tertiary: bool = False

    @model_validator(mode="after")
    def validate_eol_sum(self) -> PackageComponentBOM:
        total_eol = (
            self.eol_recycling_fraction
            + self.eol_incineration_fraction
            + self.eol_landfill_fraction
        )
        if abs(total_eol - 1.0) > 1e-4:
            raise ValueError(
                f"End-of-life fractions for component '{self.component_name}' must sum to 1.0 "
                f"(got {total_eol:.4f})."
            )
        return self


class ReuseParameters(BaseModel):
    """Parameters governing returnable/reusable packaging loops."""

    is_reusable: bool = False
    nominal_max_trips: int = Field(default=1, ge=1)
    return_rate: float = Field(default=0.90, ge=0.0, le=1.0)
    breakage_loss_rate_per_trip: float = Field(default=0.02, ge=0.0, le=1.0)
    washing_water_l_per_package: float = Field(default=0.0, ge=0.0)
    washing_thermal_energy_mj_per_package: float = Field(default=0.0, ge=0.0)
    washing_electricity_kwh_per_package: float = Field(default=0.0, ge=0.0)
    washing_cost_usd_per_package: float = Field(default=0.0, ge=0.0)
    reverse_transport_distance_km: float = Field(default=0.0, ge=0.0)

    @property
    def effective_trips(self) -> float:
        """Expected effective uses of a container accounting for return rate, breakage, and cap."""
        if not self.is_reusable or self.nominal_max_trips <= 1:
            return 1.0
        survival_prob = self.return_rate * (1.0 - self.breakage_loss_rate_per_trip)
        if survival_prob >= 0.999999:
            return float(self.nominal_max_trips)
        if survival_prob <= 0.0:
            return 1.0
        return (1.0 - (survival_prob ** self.nominal_max_trips)) / (1.0 - survival_prob)


class PackageConfiguration(BaseModel):
    """Complete packaging configuration represented as a multi-component BOM."""

    config_id: str
    name: str
    package_format: PackageFormat
    net_fill_mass_kg: float = Field(..., gt=0.0, description="Saleable dairy product mass per package (kg)")
    components: list[PackageComponentBOM] = Field(..., min_length=1)
    reuse: ReuseParameters = Field(default_factory=ReuseParameters)
    supplier_to_plant_distance_km: float = Field(default=250.0, ge=0.0)
    distribution_distance_km: float = Field(default=150.0, ge=0.0)
    transport_mode: str = Field(default="combination_truck")
    line_reject_rate: float = Field(default=0.005, ge=0.0, lt=0.5)
    package_attributable_spoilage_rate: float = Field(default=0.01, ge=0.0, lt=0.5)
    compatible_categories: list[DairyCategory] = Field(default_factory=list)
    shelf_life_days: int = Field(default=21, ge=1)
    high_barrier: bool = True
    requires_cold_chain: bool = True
    notes: str = ""

    @property
    def gross_fill_multiplier(self) -> float:
        """Gross packages required per saleable package after line rejects and spoilage."""
        return 1.0 / (
            (1.0 - self.line_reject_rate) * (1.0 - self.package_attributable_spoilage_rate)
        )

    @property
    def total_bom_mass_g(self) -> float:
        """Total one-way tare mass (g) across all BOM components on a filled package."""
        return sum(c.mass_g_per_package for c in self.components)

    def is_reusable_component(self, comp: PackageComponentBOM) -> bool:
        """Return True if a component is a primary container body amortized across reuse trips."""
        return (
            self.reuse.is_reusable
            and not comp.is_secondary_or_tertiary
            and comp.component_name.lower() in {"body", "bottle", "jar", "tub", "container"}
        )

    @model_validator(mode="after")
    def validate_composite_carton_not_100pct_paper(self) -> PackageConfiguration:
        """Enforce vision.md Section 2 rule: Never represent a composite carton as 100% paper."""
        if self.package_format == PackageFormat.CARTON:
            materials = {c.material_family for c in self.components}
            paper_only = materials.issubset(
                {
                    MaterialFamily.PAPERBOARD,
                    MaterialFamily.CORRUGATED_BOARD,
                    MaterialFamily.LIQUID_PACKAGING_BOARD,
                }
            )
            if paper_only:
                raise ValueError(
                    f"PackageConfiguration '{self.config_id}' has format='carton' with only paper/board "
                    "components. Per vision.md Section 2, composite dairy cartons must include polymer "
                    "(e.g., LDPE) and/or aluminium barrier/closure components, never 100% paper."
                )
        return self


class ScenarioAssumptions(BaseModel):
    """Operational, regional, and financial assumptions for scenario evaluation."""

    functional_unit_saleable_kg: float = Field(default=1000.0, gt=0.0)
    annual_production_volume_kg: float = Field(default=5_000_000.0, gt=0.0)
    currency: str = "USD"
    price_year: int = 2025
    grid_carbon_intensity_kgco2e_per_kwh: float = Field(
        default=0.573,
        ge=0.0,
        description="Default 0.573 kg CO2e/kWh (NIST/ANL 2024 Fig. 18a cross-regional avg); Uzbekistan gas-heavy proxy ~0.550",
    )
    grid_region_label: str = "Cross-regional average (NIST/ANL 2024)"
    plant_electricity_kwh_per_kg_product: float = Field(default=0.25, ge=0.0)
    plant_thermal_mj_per_kg_product: float = Field(default=0.80, ge=0.0)
    plant_water_l_per_kg_product: float = Field(default=1.80, ge=0.0)
    electricity_price_usd_per_kwh: float = Field(default=0.08, ge=0.0)
    natural_gas_price_usd_per_mj: float = Field(default=0.008, ge=0.0)
    water_price_usd_per_m3: float = Field(default=1.20, ge=0.0)
    labour_cost_usd_per_1000kg: float = Field(default=18.0, ge=0.0)
    maintenance_cost_usd_per_1000kg: float = Field(default=7.50, ge=0.0)
    freight_cost_usd_per_tkm: float = Field(default=0.11, ge=0.0)
    waste_disposal_cost_usd_per_kg: float = Field(default=0.06, ge=0.0)
    recycled_scrap_credit_usd_per_kg: float = Field(default=0.08, ge=0.0)
    raw_dairy_loss_cost_usd_per_kg: float = Field(default=0.85, ge=0.0)
    net_selling_price_usd_per_kg: float = Field(default=1.80, ge=0.0)
    proposed_price_premium_usd_per_kg: float = Field(
        default=0.0,
        description="Optional market price change ($/kg saleable product) for proposed sustainable packaging",
    )
    incremental_capex_usd: float = Field(default=0.0, ge=0.0)
    installation_commissioning_usd: float = Field(default=0.0, ge=0.0)
    discount_rate: float = Field(default=0.10, ge=0.0, le=0.50)
    project_lifetime_years: int = Field(default=7, ge=1, le=30)
    include_dairy_processing_boundary: bool = True
    assumptions_source_type: DataSourceType = DataSourceType.ASSUMED


class FeasibilityCheckResult(BaseModel):
    """Hard technical and regulatory constraint check result."""

    is_feasible: bool
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EnvironmentalResult(BaseModel):
    """Environmental results per functional unit (default 1,000 kg saleable product)."""

    functional_unit_kg: float
    packages_required_for_fu: float
    new_containers_manufactured_for_fu: float
    effective_reuse_trips: float
    # Packaging-system boundary (kg CO2e / FU)
    packaging_raw_material_gwp_kgco2e: float
    packaging_conversion_gwp_kgco2e: float
    packaging_transport_gwp_kgco2e: float
    packaging_reuse_washing_gwp_kgco2e: float
    packaging_eol_gwp_kgco2e: float
    spoilage_attributable_gwp_kgco2e: float
    packaging_system_total_gwp_kgco2e: float
    # Dairy-manufacturing & baseline product boundary (kg CO2e / FU)
    dairy_non_packaging_base_gwp_kgco2e: float
    combined_total_gwp_kgco2e: float
    gwp_per_kg_saleable_product: float
    gwp_per_package_kgco2e: float
    # Energy, water, mass, plastic, waste
    packaging_system_energy_mj: float
    plant_processing_energy_mj: float
    total_energy_mj: float
    packaging_and_washing_water_l: float
    plant_processing_water_l: float
    total_water_l: float
    total_packaging_mass_kg: float
    virgin_fossil_plastic_mass_kg: float
    recycled_content_mass_kg: float
    waste_recycled_kg: float
    waste_incinerated_kg: float
    waste_landfilled_kg: float
    product_loss_total_kg: float
    ifc_packaging_mass_benchmark_status: str
    component_breakdown: list[dict[str, Any]]
    provenance_records: list[ProvenanceRecord]


class EconomicResult(BaseModel):
    """Economic results per functional unit (default 1,000 kg saleable product)."""

    functional_unit_kg: float
    currency: str
    price_year: int
    packaging_material_cost_per_fu: float
    packaging_washing_reuse_cost_per_fu: float
    packaging_freight_cost_per_fu: float
    packaging_waste_net_cost_per_fu: float
    product_loss_cost_per_fu: float
    total_packaging_attributable_cost_per_fu: float
    plant_utilities_cost_per_fu: float
    plant_labour_and_maintenance_cost_per_fu: float
    total_operating_cost_per_fu: float
    cost_per_saleable_package: float
    cost_per_kg_saleable_product: float
    revenue_per_fu: float
    contribution_margin_per_fu: float
    annual_operating_cost: float
    total_initial_investment: float
    epistemic_status: str
    component_cost_breakdown: list[dict[str, Any]]


class ScenarioComparisonResult(BaseModel):
    """Full comparison of an alternative scenario against a baseline scenario."""

    scenario_id: str
    scenario_name: str
    product_id: str
    product_name: str
    package_config_id: str
    package_config_name: str
    is_baseline: bool
    feasibility: FeasibilityCheckResult
    environmental: EnvironmentalResult
    economic: EconomicResult
    # Deltas relative to baseline (alternative - baseline)
    delta_cost_per_fu: float = 0.0
    delta_cost_pct: float = 0.0
    delta_packaging_cost_pct: float = 0.0
    delta_packaging_gwp_kgco2e_per_fu: float = 0.0
    delta_packaging_gwp_pct: float = 0.0
    delta_total_gwp_kgco2e_per_fu: float = 0.0
    delta_total_gwp_pct: float = 0.0
    delta_virgin_plastic_kg_per_fu: float = 0.0
    delta_packaging_mass_kg_per_fu: float = 0.0
    initial_investment_usd: float = 0.0
    annual_cash_flow_savings: float = 0.0
    simple_payback_years: float | None = None
    simple_payback_months: float | None = None
    unconstrained_payback_years: float | None = None
    cumulative_net_cash_flow_usd: float = 0.0
    cumulative_cash_flow_schedule: list[float] = Field(default_factory=list)
    payback_status: str = "baseline"
    payback_explanation: str = ""
    npv_usd: float | None = None
    break_even_annual_volume_kg: float | None = None
    abatement_cost_usd_per_tco2e: float | None = None
    is_pareto_optimal: bool = False
    tradeoff_summary: str = ""
