"""Shared ML task registry, splitting, feature engineering, and CV runner (no Streamlit imports)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import (
    GroupKFold,
    GroupShuffleSplit,
    StratifiedKFold,
    StratifiedShuffleSplit,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from dairyeco.config import PROCESSED_DIR, SYNTHETIC_DIR
from dairyeco.domain.models import (
    DairyProductRecord,
    PackageConfiguration,
    ScenarioAssumptions,
)

SEED = 42

FORBIDDEN_LEAKAGE_COLUMNS: frozenset[str] = frozenset(
    {
        "product_id",
        "code_agb",
        "code_ciqual",
        "name_fr",
        "name_en",
        "pdo_cheese_id",
        "cheese_name",
        "total_gwp_kgco2e_per_kg",
        "non_packaging_gwp_kgco2e_per_kg",
        "agriculture_gwp_kgco2e_per_kg",
        "transformation_gwp_kgco2e_per_kg",
        "packaging_stage_gwp_kgco2e_per_kg",
        "transport_gwp_kgco2e_per_kg",
        "distribution_gwp_kgco2e_per_kg",
        "consumption_gwp_kgco2e_per_kg",
        "stage_sum_gwp_kgco2e_per_kg",
        "packaging_share_of_gwp_pct",
        "gwp_biogenic_kgco2e_per_kg",
        "gwp_fossil_kgco2e_per_kg",
        "gwp_luluc_kgco2e_per_kg",
        "single_score_mpt_per_kg",
        "ozone_depletion_kg_cfc11e_per_kg",
        "particulate_matter_disease_inc_per_kg",
        "acidification_mol_h_eq_per_kg",
        "eutrophication_freshwater_kg_p_eq_per_kg",
        "eutrophication_marine_kg_n_eq_per_kg",
        "land_use_pt_per_kg",
        "water_depletion_m3_per_kg",
        "non_packaging_water_m3_per_kg",
        "packaging_stage_water_m3_per_kg",
        "fossil_energy_mj_per_kg",
        "non_packaging_fossil_energy_mj_per_kg",
        "packaging_stage_fossil_energy_mj_per_kg",
        "mineral_resources_kg_sb_eq_per_kg",
        "gwp_base_total_kgco2e_per_kg",
        "gwp_base_milk_production_kgco2e_per_kg",
        "gwp_base_post_farm_total_kgco2e_per_kg",
        "gwp_base_cheese_ripening_kgco2e_per_kg",
        "gwp_alt_total_kgco2e_per_kg",
        "gwp_alt_post_farm_total_kgco2e_per_kg",
        "expected_bom_material_spend_usd_per_fu",
        "expected_spoilage_gwp_kgco2e_per_fu",
    }
)


def assert_no_feature_leakage(feature_cols: list[str], target_col: str) -> None:
    """Raise ValueError if any feature column is in FORBIDDEN_LEAKAGE_COLUMNS or equals target."""
    leaked = [
        c for c in feature_cols if c in FORBIDDEN_LEAKAGE_COLUMNS or c == target_col
    ]
    if leaked:
        raise ValueError(
            f"Target leakage detected! Forbidden columns in feature set: {leaked}"
        )


def build_preprocessor(
    numeric_cols: list[str], categorical_cols: list[str], min_frequency: int | None = None
) -> ColumnTransformer:
    """Build leakage-safe ColumnTransformer (median/RobustScaler + OHE)."""
    num_pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]
    )
    ohe_kwargs: dict[str, Any] = {
        "handle_unknown": "infrequent_if_exist" if min_frequency else "ignore",
        "sparse_output": False,
    }
    if min_frequency is not None:
        ohe_kwargs["min_frequency"] = min_frequency
    cat_pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("ohe", OneHotEncoder(**ohe_kwargs)),
        ]
    )
    transformers = []
    if numeric_cols:
        transformers.append(("num", num_pipe, numeric_cols))
    if categorical_cols:
        transformers.append(("cat", cat_pipe, categorical_cols))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def classify_fit_diagnosis(
    model_name: str,
    pooled_cv_mae: float,
    dummy_cv_mae: float,
    pooled_cv_r2: float,
    r2_gap: float,
    norm_mae_gap: float,
) -> str:
    """Assign a scale-invariant overfitting/underfitting diagnosis from train-vs-CV metrics."""
    if model_name.startswith("DummyRegressor"):
        return "baseline_reference"
    if pooled_cv_mae >= 0.85 * dummy_cv_mae or pooled_cv_r2 < 0.25:
        return "underfit"
    if r2_gap > 0.10 or norm_mae_gap > 0.12:
        return "overfit_high_variance"
    if r2_gap > 0.045 or norm_mae_gap > 0.065:
        return "mild_overfit"
    return "well_generalized"


FEATURE_DESCRIPTIONS: dict[str, str] = {
    # Task 1 AGRIBALYSE pre-LCA features
    "milk_yield_kg_milk_per_kg_product": "Raw milk required per kg dairy product (AGRIBALYSE Annex 8, kg milk/kg)",
    "density_kg_per_l": "Product bulk density (kg / L, category physical rule)",
    "dqr_overall": "AGRIBALYSE Data Quality Ratio (1 = highest quality, 5 = lowest)",
    "category": "Canonical dairy product category (fluid_milk, cheese, butter, yogurt_kefir, etc.)",
    "agribalyse_subgroup_fr": "AGRIBALYSE 3.2 taxonomic subgroup",
    "delivery_mode": "Supply chain temperature regime (chilled, ambient, frozen)",
    "baseline_packaging_approach": "Original AGRIBALYSE baseline packaging material subtracted during de-packaging",
    # Task 2 PDO Cheese features
    "ripening_days": "Minimum authorized PDO cellar ripening duration (days)",
    "allocation_before_skimming": "Dry-matter allocation factor prior to skimming",
    "allocation_skimming_to_draining": "Dry-matter allocation factor from skimming to curd draining",
    "allocation_after_draining": "Dry-matter allocation factor after draining",
    "cream_coproduct_kg_per_kg_cheese": "Co-product cream mass generated per kg ripened cheese (kg/kg)",
    "whey_coproduct_kg_per_kg_cheese": "Co-product liquid whey generated per kg ripened cheese (kg/kg)",
    "max_authorized_distance_km": "Maximum PDO decree milk collection radius (km)",
    "lci_cow_milk_lowland_kg": "Lowland cow raw milk input per kg cheese (kg/kg)",
    "lci_cow_milk_highland_kg": "Mountain/highland cow raw milk input per kg cheese (kg/kg)",
    "lci_sheep_milk_kg": "Raw sheep milk input per kg cheese (kg/kg)",
    "lci_goat_milk_kg": "Raw goat milk input per kg cheese (kg/kg)",
    "lci_total_raw_milk_kg": "Total raw milk required per 1 kg ripened cheese (kg/kg)",
    "lci_milk_transport_tkm": "Raw milk collection transport demand (t·km / kg cheese)",
    "lci_milk_storage_kwh": "Chilled raw milk storage electricity (kWh / kg cheese)",
    "lci_processing_electricity_kwh": "Cheese-making vat & pressing electricity (kWh / kg cheese)",
    "lci_ripening_electricity_kwh_initial": "Ripening cellar HVAC electricity demand (kWh / kg cheese)",
    "lci_cleaning_water_kg": "CIP sanitation water consumption (kg / kg cheese)",
    "technology": "PDO cheese family (Pressed cooked, Pressed uncooked, Soft, Blue-veined, Fresh)",
    "milk_type": "Ruminant milk species (Cow, Ewe/Sheep, Goat)",
    # Task 3 Simulator Surrogate features (physical/operational inputs only)
    "is_reusable": "Binary indicator (1 = multi-trip returnable container, 0 = single-use)",
    "effective_reuse_trips": "Expected container lifetime trips accounting for return rate and breakage",
    "net_fill_mass_kg": "Saleable dairy product mass per individual package (kg)",
    "total_bom_mass_g_per_pkg": "Total one-way Bill of Materials tare mass per package (g)",
    "effective_bom_mass_kg_per_fu": "Amortized packaging mass manufactured per 1,000 kg saleable product (kg/FU)",
    "primary_recycled_content_frac": "Recycled content fraction in primary container body (0.0–1.0)",
    "weighted_eol_recycling_frac": "Mass-weighted end-of-life recycling rate across BOM components (0.0–1.0)",
    "weighted_avg_material_price_usd_per_kg": "Mass-weighted average raw packaging material price ($/kg)",
    "supplier_distance_km": "Inbound packaging supplier-to-dairy-plant distance (km)",
    "distribution_distance_km": "Outbound finished dairy distribution distance (km)",
    "line_reject_rate": "Filling-line package defect/reject fraction (0.0–0.5)",
    "spoilage_loss_rate": "Package-attributable dairy spoilage/leakage fraction (0.0–0.5)",
    "grid_ci_kgco2e_per_kwh": "Regional electricity grid carbon intensity (kg CO₂e/kWh)",
    "electricity_price_usd_per_kwh": "Industrial electricity tariff ($/kWh)",
    "dairy_non_packaging_gwp_per_kg": "De-packaged dairy product baseline GWP (kg CO₂e/kg)",
    "preset_id": "Canonical packaging BOM preset identifier",
    "dairy_category": "Target dairy product category",
    "package_format": "Physical container format (bottle, carton, cup, pouch, film_wrap, tub, sack)",
    "primary_material": "Primary structural material family (HDPE, PET, PP, LPB, glass, etc.)",
    "primary_conversion": "Primary converting process (blow_molding, thermoforming, carton_converting, etc.)",
    "resin_region": "Polymer production geography (NIST 2024: Western Europe, USA, China, MENA, Cross-regional average)",
}

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "task3a_surrogate_gwp": {
        "label": "Task 3A — Packaging System GWP Surrogate (N=1,200, GroupKFold)",
        "artifact_file": "task3_surrogate_gwp_model.joblib",
        "summary_path": ("task3_simulator_surrogate", "gwp_surrogate"),
        "dataset_file": SYNTHETIC_DIR / "simulated_packaging_scenarios.csv",
        "dataset_name": "LCA Simulator Surrogate Dataset (1,200 Scenarios across Dairy Products)",
        "source_authority": "DairyEco AI Deterministic LCA & Economic Simulator (AGRIBALYSE 3.2 + NIST 2024 + USLCI)",
        "source_type": "model_derived",
        "target_col": "target_packaging_system_gwp_kgco2e_per_fu",
        "target_unit": "kg CO₂e / 1,000 kg FU",
        "cv_type": "GroupKFold (5 folds grouped by product_id) + 20% Group Holdout",
        "supports_live_scenario": True,
    },
    "task3b_surrogate_cost": {
        "label": "Task 3B — Packaging Attributable Cost Surrogate (N=1,200, GroupKFold)",
        "artifact_file": "task3_surrogate_cost_model.joblib",
        "summary_path": ("task3_simulator_surrogate", "cost_surrogate"),
        "dataset_file": SYNTHETIC_DIR / "simulated_packaging_scenarios.csv",
        "dataset_name": "LCA Simulator Surrogate Dataset (1,200 Scenarios across Dairy Products)",
        "source_authority": "DairyEco AI Deterministic LCA & Economic Simulator",
        "source_type": "model_derived",
        "target_col": "target_packaging_cost_usd_per_fu",
        "target_unit": "USD / 1,000 kg FU",
        "cv_type": "GroupKFold (5 folds grouped by product_id) + 20% Group Holdout",
        "supports_live_scenario": True,
    },
    "task1_agribalyse_gwp": {
        "label": "Task 1 — AGRIBALYSE 3.2 De-Packaged Dairy GWP Regression (N=255, StratifiedKFold)",
        "artifact_file": "task1_agribalyse_gwp_model.joblib",
        "summary_path": ("task1_agribalyse",),
        "dataset_file": PROCESSED_DIR / "agribalyse_dairy_products.csv",
        "dataset_name": "AGRIBALYSE 3.2 Core Dairy Products (N=255 de-packaged records)",
        "source_authority": "ADEME / INRAE AGRIBALYSE v3.2 (France / Europe, EF 3.1)",
        "source_type": "published_reference",
        "target_col": "non_packaging_gwp_kgco2e_per_kg",
        "target_unit": "kg CO₂e / kg product",
        "cv_type": "StratifiedKFold (5 folds by subgroup) + 20% Stratified Holdout",
        "supports_live_scenario": False,
    },
    "task2a_pdo_cheese_total": {
        "label": "Task 2A — French PDO Cheese Pre-LCI Total GWP Regression (N=44, 5-Fold StratifiedKFold)",
        "artifact_file": "task2_pdo_cheese_gwp_model.joblib",
        "summary_path": ("task2_pdo_cheese",),
        "dataset_file": PROCESSED_DIR / "pdo_cheese_harmonized.csv",
        "dataset_name": "French PDO Cheese LCA Dataset (44 canonical cheeses, 1 kg ripened cheese FU)",
        "source_authority": "INRAE / Institut Agro / Actalia (EF 3.0 / ILCD Midpoint, 28 indicators)",
        "source_type": "published_reference",
        "target_col": "gwp_base_total_kgco2e_per_kg",
        "target_unit": "kg CO₂e / kg ripened cheese",
        "cv_type": "StratifiedKFold (5 folds by target quartile) + 20% Stratified Holdout",
        "supports_live_scenario": False,
    },
    "task2b_pdo_cheese_post_farm": {
        "label": "Task 2B — French PDO Cheese Full-LCI Post-Farm GWP Regression (N=44, 5-Fold StratifiedKFold)",
        "artifact_file": "task2b_pdo_cheese_post_farm_gwp_model.joblib",
        "summary_path": ("task2_pdo_cheese", "regime_2b_full_lci_post_farm"),
        "dataset_file": PROCESSED_DIR / "pdo_cheese_harmonized.csv",
        "dataset_name": "French PDO Cheese LCA Dataset — Post-Farm Processing & Ripening Boundary (N=44)",
        "source_authority": "INRAE / Institut Agro / Actalia (EF 3.0 / ILCD Midpoint, 28 indicators)",
        "source_type": "published_reference",
        "target_col": "gwp_base_post_farm_total_kgco2e_per_kg",
        "target_unit": "kg CO₂e / kg ripened cheese",
        "cv_type": "StratifiedKFold (5 folds by target quartile) + 20% Stratified Holdout",
        "supports_live_scenario": False,
    },
}

PARAM_SPECS: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "CatBoostRegressor": {
        "iterations": (40, 400, 150, 10),
        "depth": (2, 8, 4, 1),
        "learning_rate": (0.01, 0.2, 0.045, 0.005),
        "l2_leaf_reg": (1, 50, 12, 1),
    },
    "HistGradientBoostingRegressor": {
        "max_iter": (30, 300, 90, 10),
        "max_depth": (2, 10, 4, 1),
        "learning_rate": (0.02, 0.2, 0.05, 0.01),
        "l2_regularization": (0, 60, 15, 2.5),
        "min_samples_leaf": (3, 40, 10, 1),
    },
    "RandomForestRegressor": {
        "n_estimators": (40, 300, 120, 20),
        "max_depth": (2, 14, 6, 1),
        "min_samples_leaf": (1, 25, 5, 1),
        "max_features": (0.3, 1.0, 0.7, 0.1),
    },
    "ExtraTreesRegressor": {
        "n_estimators": (40, 300, 120, 20),
        "max_depth": (2, 14, 6, 1),
        "min_samples_leaf": (1, 25, 4, 1),
        "max_features": (0.3, 1.0, 0.7, 0.1),
    },
    "Ridge": {"alpha": (0.01, 100, 10, 0.5)},
    "ElasticNet": {"alpha": (0.001, 5, 0.1, 0.01), "l1_ratio": (0.1, 0.99, 0.5, 0.05)},
}

INT_PARAMS: frozenset[str] = frozenset(
    {"iterations", "depth", "max_iter", "max_depth", "min_samples_leaf", "n_estimators"}
)


def get_task_summary_dict(summary: dict[str, Any], task_key: str) -> dict[str, Any]:
    """Extract the task evaluation dictionary from ml_evaluation_summary.json."""
    path = MODEL_REGISTRY[task_key]["summary_path"]
    curr = summary
    for step in path:
        curr = curr[step]
    if task_key in {"task3a_surrogate_gwp", "task3b_surrogate_cost"}:
        parent = summary["task3_simulator_surrogate"]
        return {
            **curr,
            "feature_columns": parent["feature_columns"],
            "n_observations": parent["n_observations"],
            "validation_scheme": parent["validation_scheme"],
            "data_source_type": parent["data_source_type"],
        }
    if task_key == "task2b_pdo_cheese_post_farm":
        parent = summary["task2_pdo_cheese"]
        return {
            **curr,
            "n_observations": parent["n_observations"],
            "validation_scheme": parent["validation_scheme"],
            "data_source_type": parent["data_source_type"],
        }
    return curr


def load_task_frame(task_key: str) -> pd.DataFrame:
    """Load the processed dataset frame for a registered ML task."""
    meta = MODEL_REGISTRY[task_key]
    df = pd.read_csv(meta["dataset_file"])
    if task_key == "task1_agribalyse_gwp" and "is_core_dairy" in df.columns:
        df = df[df["is_core_dairy"] == True].copy().reset_index(drop=True)
    return df


def make_holdout_split(
    task_key: str,
    df: pd.DataFrame,
    target_col: str,
    test_size: float = 0.20,
    seed: int = SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a deterministic dev/holdout index split matching the task's data-generating process."""
    if task_key in {"task3a_surrogate_gwp", "task3b_surrogate_cost"}:
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        return next(gss.split(df, df[target_col], df["product_id"]))
    if task_key == "task1_agribalyse_gwp":
        strata = df["agribalyse_subgroup_fr"].astype(str)
    else:
        strata = pd.qcut(df[target_col], q=4, labels=False, duplicates="drop").astype(str)
    sss = StratifiedShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    return next(sss.split(df, strata))


def make_splits(
    task_key: str,
    df: pd.DataFrame,
    target_col: str,
    seed: int = SEED,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Create deterministic 5-fold CV splits matching the task's data-generating process."""
    if task_key in {"task3a_surrogate_gwp", "task3b_surrogate_cost"}:
        return list(GroupKFold(n_splits=5).split(df, df[target_col], df["product_id"]))
    if task_key == "task1_agribalyse_gwp":
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        return list(skf.split(df, df["agribalyse_subgroup_fr"].astype(str)))
    strata = pd.qcut(df[target_col], q=4, labels=False, duplicates="drop").astype(str)
    n_splits = min(5, int(strata.value_counts().min()))
    skf = StratifiedKFold(n_splits=max(2, n_splits), shuffle=True, random_state=seed)
    return list(skf.split(df, strata))


def build_surrogate_feature_row(
    product: DairyProductRecord,
    package_config: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    effective_reuse_trips: float | None = None,
) -> dict[str, Any]:
    """Build the clean 21-feature physical/operational dict for Task 3 surrogate models."""
    primary_comp = package_config.components[0]
    comp_masses = [c.mass_g_per_package for c in package_config.components]
    total_bom_mass_g = sum(comp_masses)
    avg_unit_price = float(
        np.average(
            [c.unit_price_usd_per_kg for c in package_config.components],
            weights=comp_masses,
        )
    )
    weighted_rec_eol = float(
        np.average(
            [c.eol_recycling_fraction for c in package_config.components],
            weights=comp_masses,
        )
    )

    eff_trips = (
        effective_reuse_trips
        if effective_reuse_trips is not None
        else package_config.reuse.effective_trips
    )
    saleable_pkgs = 1000.0 / package_config.net_fill_mass_kg
    gross_pkgs = saleable_pkgs * package_config.gross_fill_multiplier
    new_containers = gross_pkgs / eff_trips
    eff_bom_mass_kg_per_fu = sum(
        (c.mass_g_per_package / 1000.0)
        * (new_containers if package_config.is_reusable_component(c) else gross_pkgs)
        for c in package_config.components
    )

    return {
        "is_reusable": int(package_config.reuse.is_reusable),
        "effective_reuse_trips": round(eff_trips, 4),
        "net_fill_mass_kg": package_config.net_fill_mass_kg,
        "total_bom_mass_g_per_pkg": round(total_bom_mass_g, 3),
        "effective_bom_mass_kg_per_fu": round(eff_bom_mass_kg_per_fu, 4),
        "primary_recycled_content_frac": primary_comp.recycled_content_fraction,
        "weighted_eol_recycling_frac": round(weighted_rec_eol, 4),
        "weighted_avg_material_price_usd_per_kg": round(avg_unit_price, 4),
        "supplier_distance_km": package_config.supplier_to_plant_distance_km,
        "distribution_distance_km": package_config.distribution_distance_km,
        "line_reject_rate": package_config.line_reject_rate,
        "spoilage_loss_rate": package_config.package_attributable_spoilage_rate,
        "grid_ci_kgco2e_per_kwh": assumptions.grid_carbon_intensity_kgco2e_per_kwh,
        "electricity_price_usd_per_kwh": assumptions.electricity_price_usd_per_kwh,
        "dairy_non_packaging_gwp_per_kg": product.non_packaging_gwp_kgco2e_per_kg,
        "preset_id": str(package_config.config_id),
        "dairy_category": str(product.category),
        "package_format": str(package_config.package_format),
        "primary_material": str(primary_comp.material_family),
        "primary_conversion": str(primary_comp.conversion_process),
        "resin_region": str(primary_comp.resin_region),
    }


def build_surrogate_feature_df(
    product: DairyProductRecord,
    package_config: PackageConfiguration,
    assumptions: ScenarioAssumptions,
    effective_reuse_trips: float | None = None,
) -> pd.DataFrame:
    """Return a single-row DataFrame for live surrogate inference."""
    return pd.DataFrame(
        [build_surrogate_feature_row(product, package_config, assumptions, effective_reuse_trips)]
    )


def build_experimental_estimator(
    arch_name: str,
    params: dict[str, Any],
    random_state: int = SEED,
) -> Any:
    """Instantiate an experimental scikit-learn / CatBoost estimator from hyperparameters."""
    if arch_name == "CatBoostRegressor":
        return CatBoostRegressor(
            iterations=int(params.get("iterations", 150)),
            depth=int(params.get("depth", 4)),
            learning_rate=float(params.get("learning_rate", 0.045)),
            l2_leaf_reg=float(params.get("l2_leaf_reg", 12.0)),
            subsample=float(params.get("subsample", 0.75)),
            random_seed=random_state,
            verbose=0,
            allow_writing_files=False,
        )
    if arch_name == "HistGradientBoostingRegressor":
        return HistGradientBoostingRegressor(
            max_iter=int(params.get("max_iter", 90)),
            max_depth=int(params.get("max_depth", 4)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            l2_regularization=float(params.get("l2_regularization", 15.0)),
            min_samples_leaf=int(params.get("min_samples_leaf", 10)),
            random_state=random_state,
        )
    if arch_name == "RandomForestRegressor":
        return RandomForestRegressor(
            n_estimators=int(params.get("n_estimators", 120)),
            max_depth=int(params.get("max_depth", 6)),
            min_samples_leaf=int(params.get("min_samples_leaf", 5)),
            max_features=float(params.get("max_features", 0.7)),
            bootstrap=True,
            n_jobs=-1,
            random_state=random_state,
        )
    if arch_name == "ExtraTreesRegressor":
        return ExtraTreesRegressor(
            n_estimators=int(params.get("n_estimators", 120)),
            max_depth=int(params.get("max_depth", 6)),
            min_samples_leaf=int(params.get("min_samples_leaf", 4)),
            max_features=float(params.get("max_features", 0.7)),
            bootstrap=True,
            max_samples=0.8,
            n_jobs=-1,
            random_state=random_state,
        )
    if arch_name == "Ridge":
        return Ridge(alpha=float(params.get("alpha", 10.0)), random_state=random_state)
    if arch_name == "ElasticNet":
        return ElasticNet(
            alpha=float(params.get("alpha", 0.1)),
            l1_ratio=float(params.get("l1_ratio", 0.5)),
            max_iter=4000,
            random_state=random_state,
        )
    raise ValueError(f"Unsupported experimental architecture: {arch_name}")


def extract_estimator_params(pipe: Pipeline) -> dict[str, Any]:
    """Extract readable hyperparameters from a fitted sklearn Pipeline."""
    reg = pipe.named_steps.get("reg")
    if reg is None:
        return {}
    if hasattr(reg, "best_estimator_"):
        reg = reg.best_estimator_
    if isinstance(reg, CatBoostRegressor):
        return reg.get_all_params()
    if hasattr(reg, "get_params"):
        raw = reg.get_params(deep=False)
        clean: dict[str, Any] = {}
        for k, v in raw.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                clean[k] = v
            elif isinstance(v, (list, tuple)) and len(v) <= 6:
                clean[k] = str(v)
        return clean
    return {}


def run_cv_experiment(
    task_key: str,
    arch: str,
    params: dict[str, Any],
    summary: dict[str, Any],
    seed: int = SEED,
    return_fitted_pipeline: bool = False,
) -> dict[str, Any]:
    """Run controlled in-memory CV on the development split with the exact production split recipe."""
    import time

    t0 = time.perf_counter()
    meta = MODEL_REGISTRY[task_key]
    info = get_task_summary_dict(summary, task_key)
    feats: list[str] = info["feature_columns"]
    target = meta["target_col"]
    assert_no_feature_leakage(feats, target)

    full_df = load_task_frame(task_key)
    dev_idx, _ = make_holdout_split(task_key, full_df, target, seed=SEED)
    df = full_df.iloc[dev_idx].reset_index(drop=True)
    X, y = df[feats], df[target]

    num = [c for c in feats if pd.api.types.is_numeric_dtype(X[c])]
    cat = [c for c in feats if c not in num]
    min_freq = 2 if len(df) < 80 else None
    splits = make_splits(task_key, df, target, seed=seed)

    base = Pipeline(
        [
            ("prep", build_preprocessor(num, cat, min_frequency=min_freq)),
            ("reg", build_experimental_estimator(arch, params, random_state=seed)),
        ]
    )
    oof = np.zeros(len(y), dtype=float)
    tr_mae, va_mae, tr_r2 = [], [], []
    for tr, va in splits:
        fold = clone(base).fit(X.iloc[tr], y.iloc[tr])
        pred_tr = fold.predict(X.iloc[tr])
        pred_va = fold.predict(X.iloc[va])
        oof[va] = pred_va
        tr_mae.append(float(mean_absolute_error(y.iloc[tr], pred_tr)))
        va_mae.append(float(mean_absolute_error(y.iloc[va], pred_va)))
        tr_r2.append(float(r2_score(y.iloc[tr], pred_tr)))

    mae = float(mean_absolute_error(y, oof))
    rmse = float(np.sqrt(mean_squared_error(y, oof)))
    r2 = float(r2_score(y, oof))
    tr_mae_mean = float(np.mean(tr_mae))
    cv_mae_mean = float(np.mean(va_mae))
    cv_mae_std = float(np.std(va_mae, ddof=1)) if len(va_mae) > 1 else 0.0
    tr_r2_mean = float(np.mean(tr_r2))
    gap = max(0.0, tr_r2_mean - r2)
    dummy = next(
        (m["mae"] for m in info["metrics"] if m["model_name"].startswith("Dummy")),
        float(np.mean(np.abs(y - np.median(y)))),
    )
    nmae_gap = max(0.0, cv_mae_mean - tr_mae_mean) / max(dummy, 1e-6)
    diag = classify_fit_diagnosis(arch, mae, dummy, r2, gap, nmae_gap)

    out: dict[str, Any] = {
        "architecture": arch,
        "hyperparameters": params,
        "oof_mae": round(mae, 6),
        "cv_mae_mean": round(cv_mae_mean, 6),
        "cv_mae_std": round(cv_mae_std, 6),
        "oof_rmse": round(rmse, 6),
        "oof_r2": round(r2, 6),
        "train_mae_mean": round(tr_mae_mean, 6),
        "train_r2_mean": round(tr_r2_mean, 6),
        "r2_generalization_gap": round(gap, 6),
        "normalized_mae_gap": round(nmae_gap, 6),
        "fit_diagnosis": diag,
        "fold_val_mae": [round(float(v), 6) for v in va_mae],
        "duration_s": round(time.perf_counter() - t0, 2),
    }
    if return_fitted_pipeline:
        out["pipeline"] = clone(base).fit(X, y)
    return out


__all__ = [
    "FEATURE_DESCRIPTIONS",
    "FORBIDDEN_LEAKAGE_COLUMNS",
    "INT_PARAMS",
    "MODEL_REGISTRY",
    "PARAM_SPECS",
    "SEED",
    "assert_no_feature_leakage",
    "build_experimental_estimator",
    "build_preprocessor",
    "build_surrogate_feature_df",
    "build_surrogate_feature_row",
    "classify_fit_diagnosis",
    "extract_estimator_params",
    "get_task_summary_dict",
    "load_task_frame",
    "make_holdout_split",
    "make_splits",
    "run_cv_experiment",
]
