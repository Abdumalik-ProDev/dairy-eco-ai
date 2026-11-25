"""Phase 0 automated tests for raw file inventory, source inspectors, and PDF extractions."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dairyeco.data.audit_inspectors import (
    inspect_agribalyse_agriculture,
    inspect_agribalyse_food,
    inspect_pdo_cheese,
    inspect_uslci,
    normalize_pdo_cheese_name,
)
from dairyeco.data.inventory import (
    identify,
    sha256_file,
    sniff_media_type,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
METADATA_DIR = REPO_ROOT / "data" / "metadata"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
INTERIM_PDF_DIR = REPO_ROOT / "data" / "interim" / "pdf_extraction"


@pytest.fixture(scope="module")
def raw_inventory_df() -> pd.DataFrame:
    path = METADATA_DIR / "raw_file_inventory.csv"
    assert path.exists(), f"Missing inventory CSV: {path}"
    return pd.read_csv(path, keep_default_na=False)


@pytest.fixture(scope="module")
def dataset_manifest_df() -> pd.DataFrame:
    path = METADATA_DIR / "dataset_manifest.csv"
    assert path.exists(), f"Missing dataset manifest CSV: {path}"
    return pd.read_csv(path, keep_default_na=False)


@pytest.fixture(scope="module")
def agribalyse_food_summary():
    return inspect_agribalyse_food(RAW_DIR)


@pytest.fixture(scope="module")
def pdo_summary():
    return inspect_pdo_cheese(RAW_DIR)


@pytest.fixture(scope="module")
def uslci_summary():
    return inspect_uslci(RAW_DIR)


def test_raw_inventory_completeness_and_checksums(
    raw_inventory_df: pd.DataFrame,
    dataset_manifest_df: pd.DataFrame,
) -> None:
    """Verify recursive inventory covers all 8,096 raw files and matches SHA-256 hashes."""
    required_cols = {
        "relative_path",
        "file_name",
        "extension",
        "media_type",
        "size_bytes",
        "sha256",
        "likely_source",
        "source_component",
        "identification_confidence",
        "identification_basis",
    }
    assert required_cols.issubset(raw_inventory_df.columns)
    assert len(raw_inventory_df) == 8096
    assert int(raw_inventory_df["size_bytes"].astype(int).sum()) == 245170139
    assert set(raw_inventory_df["likely_source"].unique()) == {
        "agribalyse_3_2",
        "pdo_cheese_lca",
        "uslci",
        "anl_nist_regional_plastics_2024",
        "ifc_wbg_ehs_dairy_2007",
    }
    assert (raw_inventory_df["sha256"].str.len() == 64).all()

    # Spot-check PDF hashes and extensionless PDO LCI file media type
    nist_rel = (
        "data/raw/[2024  Taemin Kim] Life-Cycle Analysis Datasets "
        "for Regionalized Plastic Pathways.pdf.pdf"
    )
    ifc_rel = "data/raw/111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf"
    pdo_lci_path = REPO_ROOT / "data/raw/pdo_cheese_lca/data_PDOcheeses_LCI"

    assert sha256_file(REPO_ROOT / nist_rel) == (
        "db42a209799c6212f52ff73cb0d144752201eaf02dd12c96c49d64a61702760c"
    )
    assert sha256_file(REPO_ROOT / ifc_rel) == (
        "90c5963f47291ec64876e62555aebe9959d9eb0f2f0a10fb215cd6c119b257e5"
    )
    assert sniff_media_type(pdo_lci_path) == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    src, comp, conf, _ = identify(pdo_lci_path, RAW_DIR)
    assert (src, comp, conf) == ("pdo_cheese_lca", "root", "medium")

    # Verify manifest schema and row count
    assert len(dataset_manifest_df) == 5
    assert set(dataset_manifest_df["dataset_id"]) == {
        "agribalyse_3_2",
        "pdo_cheese_lca",
        "uslci",
        "anl_nist_regional_plastics_2024",
        "ifc_wbg_ehs_dairy_2007",
    }
    assert int(dataset_manifest_df["file_count"].astype(int).sum()) == 8096


def test_agribalyse_audit_inspector(agribalyse_food_summary) -> None:
    """Verify AGRIBALYSE 3.2 food & agricultural dairy audit findings."""
    assert agribalyse_food_summary.total_synthese_rows == 2458
    assert agribalyse_food_summary.unique_agb_codes == 2451
    assert {str(c) for c in agribalyse_food_summary.duplicate_agb_codes} == {
        "9901",
        "25998",
        "26013",
        "26034",
        "26037",
        "26232",
        "27029",
    }
    assert agribalyse_food_summary.core_dairy_row_count == 255
    subgroup_totals = {
        subgrp: cnt
        for (_, subgrp), cnt in agribalyse_food_summary.dairy_group_subgroups.items()
    }
    assert subgroup_totals == {
        "fromages": 121,
        "produits laitiers frais et assimilés": 79,
        "laits": 17,
        "desserts glacés": 12,
        "beurres": 10,
        "glaces": 10,
        "crèmes et spécialités à base de crème": 6,
    }
    assert agribalyse_food_summary.core_dairy_packaging_approaches == {
        "PACK AGB": 230,
        "PACK PROXY": 25,
    }
    assert agribalyse_food_summary.detail_etape_valid_rows == 2458
    assert agribalyse_food_summary.detail_etape_trailing_formula_rows == 12445
    assert agribalyse_food_summary.detail_ingredient_valid_rows == 7269
    assert agribalyse_food_summary.detail_ingredient_unique_codes == 1099
    assert len(agribalyse_food_summary.indicators) == 20
    assert agribalyse_food_summary.stages == [
        "Agriculture",
        "Transformation",
        "Emballage",
        "Transport",
        "Supermarché et distribution",
        "Consommation",
        "Total",
    ]

    ag_summary = inspect_agribalyse_agriculture(RAW_DIR)
    assert ag_summary["conventional"]["total_rows"] == 227
    assert ag_summary["conventional"]["dairy_category_count"] == 8
    assert ag_summary["organic"]["total_rows"] == 226
    assert ag_summary["organic"]["dairy_category_count"] == 6


def test_pdo_cheese_audit_inspector(pdo_summary) -> None:
    """Verify PDO Cheese LCA observation entity (44 cheeses) and table join consistency."""
    assert normalize_pdo_cheese_name("Camenbert de Normandie ") == "Camembert de Normandie"
    assert normalize_pdo_cheese_name("Bleu d'Auvergne  ") == "Bleu d'Auvergne"

    assert pdo_summary.canonical_cheese_count == 44
    assert len(pdo_summary.canonical_cheese_names) == 44
    for key in [
        "characterization",
        "allocations",
        "coproducts",
        "distances",
        "specifications",
        "lci_initial",
        "lci_additional",
    ]:
        assert pdo_summary.table_cheese_counts[key] == 44

    assert pdo_summary.lcia_total_indicator_rows == 1232
    assert pdo_summary.lcia_indicators_per_cheese == 28
    assert pdo_summary.lcia_total_indicator_rows == (
        pdo_summary.canonical_cheese_count * pdo_summary.lcia_indicators_per_cheese
    )
    assert pdo_summary.functional_unit == "FU = 1kg of cheese"
    assert pdo_summary.ripening_wood_unit_initial == "m3"
    assert pdo_summary.ripening_wood_unit_additional == "kg"


def test_uslci_audit_inspector(uslci_summary) -> None:
    """Verify USLCI process counts, absence of bundled LCIA methods, and curated processes."""
    assert uslci_summary.schema_version == 3
    assert uslci_summary.total_processes == 1434
    assert uslci_summary.unit_process_count == 1408
    assert uslci_summary.lci_result_count == 26
    assert uslci_summary.bridge_process_count == 97
    assert uslci_summary.lcia_method_count == 0
    assert uslci_summary.total_product_flow_inputs == 6833
    assert uslci_summary.unprovided_product_flow_inputs == 2171
    assert len(uslci_summary.curated_packaging_energy_processes) == 56

    by_prefix = {
        row["uuid"][:8]: row for row in uslci_summary.curated_packaging_energy_processes
    }
    assert by_prefix["99963138"]["process_type"] == "LCI_RESULT"
    assert by_prefix["99963138"]["elementary_exchanges"] == 583
    assert by_prefix["cf1241fd"]["qref_amount"] == 1000.0
    assert by_prefix["30a3f9c8"]["qref_unit"] == "sh tn"
    assert by_prefix["4c476cdb"]["qref_unit"] == "Mg"
    assert (
        by_prefix["06d602eb"]["suitability_status"]
        == "unsuitable_bridge_stub_to_useeio_0_elementary_flows"
    )
    assert (
        by_prefix["44a867b1"]["suitability_status"]
        == "unsuitable_bridge_stub_to_us_electricity_baseline"
    )


def test_extracted_pdf_tables_and_reference_outputs() -> None:
    """Verify NIST and IFC extracted interim and reference CSV schemas and key values."""
    nist_ref = pd.read_csv(REFERENCE_DIR / "nist_plastic_carbon_intensity.csv")
    ifc_ref = pd.read_csv(REFERENCE_DIR / "ifc_dairy_benchmarks.csv")

    # NIST reference checks
    assert len(nist_ref) == 67
    assert {"PET", "HDPE", "LDPE", "PP", "PVC"}.issubset(
        set(nist_ref["material_or_product"].unique())
    )
    assert set(nist_ref["record_type"].unique()) == {
        "resin_cross_regional_average",
        "resin_regional_baseline",
        "background_energy_fig18",
        "pathway_specific_table5",
    }

    # Check USA PTA-based PET pathway uses verified Table 5 value 1.75 (not prose typo 1.92)
    usa_pet_pta = nist_ref[
        (nist_ref["record_type"] == "pathway_specific_table5")
        & (nist_ref["material_or_product"] == "PET")
        & (nist_ref["region"] == "USA")
        & (nist_ref["pathway"] == "PTA-based")
    ]
    assert len(usa_pet_pta) == 1
    assert float(usa_pet_pta.iloc[0]["normalized_value"]) == pytest.approx(1.75)

    # Check China PVC baseline CI (3.57 kgCO2e/kg, +34% vs global 2.68)
    china_pvc = nist_ref[
        (nist_ref["record_type"] == "resin_regional_baseline")
        & (nist_ref["material_or_product"] == "PVC")
        & (nist_ref["region"] == "China")
    ]
    assert len(china_pvc) == 1
    assert float(china_pvc.iloc[0]["normalized_value"]) == pytest.approx(3.57)
    assert float(
        china_pvc.iloc[0]["deviation_from_cross_regional_avg_pct"]
    ) == pytest.approx(34.0)

    # IFC reference checks
    assert len(ifc_ref) == 69
    assert set(ifc_ref["table_ref"].unique()) == {
        "Table 1",
        "Table 2",
        "Table 3",
    }

    # Check merged Nordic ice cream energy cell was explicitly preserved
    nordic_ice_cream = ifc_ref[
        (ifc_ref["table_ref"] == "Table 3")
        & (ifc_ref["benchmark_category"] == "Energy")
        & (ifc_ref["product_or_pollutant"] == "Ice cream")
        & (ifc_ref["region_or_column"].str.startswith("Nordic dairies"))
    ]
    assert len(nordic_ice_cream) == 1
    assert float(nordic_ice_cream.iloc[0]["min_value"]) == pytest.approx(0.75)
    assert float(nordic_ice_cream.iloc[0]["max_value"]) == pytest.approx(1.6)

    # Check interim CSVs and rendered PNGs exist
    for rel_path in [
        "nist/raw_pdfplumber_tables.json",
        "nist/table1_cross_regional_summary.csv",
        "nist/table2_3_global_volumes.csv",
        "nist/table4_regional_dataset_coverage.csv",
        "nist/table5_pathway_ci.csv",
        "nist/figures_regional_baseline_ci.csv",
        "ifc/raw_pdfplumber_tables.json",
        "ifc/table1_effluent_guidelines.csv",
        "ifc/table2_solid_waste_generation.csv",
        "ifc/table3_resource_energy_consumption_wide.csv",
    ]:
        assert (INTERIM_PDF_DIR / rel_path).exists(), f"Missing interim file: {rel_path}"
