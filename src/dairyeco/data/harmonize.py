"""Phase 1 harmonization pipeline: builds validated analytical tables in ``data/processed/``.

Preserves source-specific tables, normalizes join keys and reference units,
subtracts embedded baseline packaging from AGRIBALYSE product totals to prevent
double-counting, and attaches full provenance metadata to every derived record.

Run: ``uv run python -m dairyeco.data.harmonize``
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

from dairyeco.config import PROCESSED_DIR, RAW_DIR, REFERENCE_DIR
from dairyeco.data.audit_inspectors import normalize_pdo_cheese_name
from dairyeco.domain.models import DairyCategory, DataSourceType

# Unit conversions to kg for USLCI quantitative references
UNIT_TO_KG: dict[str, float] = {
    "kg": 1.0,
    "Mg": 1000.0,
    "t": 1000.0,
    "sh tn": 907.18474,
    "lb": 0.45359237,
}

# IPCC AR6 / EF 3.1 GWP100 characterization factors (kg CO2e / kg elementary flow)
ELEMENTARY_GWP100_FACTORS: dict[str, float] = {
    "carbon dioxide, fossil": 1.0,
    "carbon dioxide": 1.0,
    "carbon dioxide, land transformation": 1.0,
    "methane, fossil": 29.8,
    "methane": 27.2,
    "methane, biogenic": 27.2,
    "dinitrogen monoxide": 273.0,
    "nitrous oxide": 273.0,
}


def _parse_stage_float(val: Any) -> float:
    """Convert AGRIBALYSE Detail etape cell ('-' means exact zero) to float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip()
    if text in {"", "-", "N/A"}:
        return 0.0
    return float(text.replace(",", "."))


def _map_agribalyse_dairy_category(
    group_fr: str, subgroup_fr: str, name_fr: str, name_en: str
) -> DairyCategory:
    """Map AGRIBALYSE food group/subgroup/product name to canonical DairyCategory."""
    name_lower = f"{name_fr} {name_en}".lower()
    if subgroup_fr == "fromages":
        return DairyCategory.CHEESE
    if subgroup_fr == "beurres":
        return DairyCategory.BUTTER
    if subgroup_fr == "crèmes et spécialités à base de crème":
        return DairyCategory.CREAM
    if subgroup_fr in {"glaces", "desserts glacés"}:
        return DairyCategory.ICE_CREAM
    if subgroup_fr == "produits laitiers frais et assimilés":
        return DairyCategory.YOGURT_KEFIR
    if subgroup_fr in {"laits", "laits et boissons infantiles"}:
        if "poudre" in name_lower or "powder" in name_lower:
            return DairyCategory.MILK_POWDER
        return DairyCategory.FLUID_MILK
    if "poudre" in name_lower or "powder" in name_lower:
        return DairyCategory.MILK_POWDER
    if subgroup_fr == "boissons sans alcool":
        return DairyCategory.FLUID_MILK
    return DairyCategory.OTHER_DAIRY


def _load_cheese_milk_yields(raw_dir: Path) -> dict[str, float]:
    """Load CIQUAL cheese milk yields (kg milk / kg cheese) from AGRIBALYSE Annex 8."""
    annex_path = (
        raw_dir / "agribalyse_3_2" / "Méthodologie Alimentation Annexes_AGB 3.2.xlsx"
    )
    wb = openpyxl.load_workbook(annex_path, read_only=True, data_only=True)
    ws = wb["8. Milk yield for cheeses"]
    yields: dict[str, float] = {}
    for row in list(ws.iter_rows(values_only=True))[3:]:
        ciqual = row[1]
        raw_yield = row[3]
        if ciqual is None or raw_yield is None:
            continue
        code_str = str(int(ciqual)) if isinstance(ciqual, (int, float)) else str(ciqual).strip()
        if isinstance(raw_yield, (int, float)):
            yields[code_str] = float(raw_yield)
        else:
            match = re.search(r"(\d+[.,]\d+|\d+)", str(raw_yield))
            if match:
                yields[code_str] = float(match.group(1).replace(",", "."))
    wb.close()
    return yields


def _infer_dairy_density(category: DairyCategory, name_en: str) -> float:
    """Assign published AGRIBALYSE Annex 6 / FAO physical density (kg/L or kg/dm3)."""
    lower = name_en.lower()
    if category == DairyCategory.FLUID_MILK:
        if "goat" in lower:
            return 1.080
        if "condensed" in lower:
            return 1.070
        return 1.034
    if category == DairyCategory.CREAM:
        return 0.984
    if category == DairyCategory.YOGURT_KEFIR:
        return 1.045
    if category == DairyCategory.BUTTER:
        return 0.911
    if category == DairyCategory.ICE_CREAM:
        return 0.550
    if category == DairyCategory.MILK_POWDER:
        return 0.520
    return 1.050


def build_agribalyse_dairy_table(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Harmonize AGRIBALYSE 3.2 dairy products with stage breakdown and packaging isolation."""
    wb_path = (
        raw_dir
        / "agribalyse_3_2"
        / "AGRIBALYSE3.2_Tableur produits alimentaires_PublieAOUT25.xlsx"
    )
    milk_yields = _load_cheese_milk_yields(raw_dir)
    wb = openpyxl.load_workbook(wb_path, read_only=True, data_only=True)

    ws_syn = wb["Synthese"]
    syn_rows = [r for r in list(ws_syn.iter_rows(values_only=True))[3:] if r[0] is not None]

    ws_et = wb["Detail etape"]
    # Filter out the 12,445 trailing formula rows where Code AGB is None
    et_rows = [r for r in list(ws_et.iter_rows(values_only=True))[4:] if r[0] is not None]
    et_by_key: dict[tuple[str, str], tuple[Any, ...]] = {
        (str(r[0]).strip(), str(r[5]).strip()): r for r in et_rows
    }

    core_subgroups = {
        "crèmes et spécialités à base de crème",
        "fromages",
        "laits",
        "produits laitiers frais et assimilés",
        "beurres",
        "glaces",
        "desserts glacés",
    }
    adjacent_subgroups = {
        "laits et boissons infantiles",
        "desserts infantiles",
    }
    adjacent_beverage_codes = {"19122", "19127"}

    records: list[dict[str, Any]] = []
    for r in syn_rows:
        code_agb = str(r[0]).strip()
        group_fr = str(r[2] or "").strip()
        subgroup_fr = str(r[3] or "").strip()
        name_fr = str(r[4] or "").strip()
        lci_name = str(r[5] or "").strip()

        is_core = group_fr == "lait et produits laitiers" or subgroup_fr in core_subgroups
        is_adjacent = (
            subgroup_fr in adjacent_subgroups or code_agb in adjacent_beverage_codes
        )
        if not (is_core or is_adjacent):
            continue

        et = et_by_key.get((code_agb, lci_name))
        if et is None:
            continue

        category = _map_agribalyse_dairy_category(group_fr, subgroup_fr, name_fr, lci_name)

        # Synthese indicator columns (cols 12..31)
        single_score_mpt = float(r[12] or 0.0)
        total_gwp = float(r[13] or 0.0)
        ozone_depletion = float(r[14] or 0.0)
        particulate_matter = float(r[17] or 0.0)
        acidification = float(r[20] or 0.0)
        eutroph_freshwater = float(r[21] or 0.0)
        eutroph_marine = float(r[22] or 0.0)
        land_use_pt = float(r[25] or 0.0)
        water_depletion_m3 = float(r[26] or 0.0)
        fossil_energy_mj = float(r[27] or 0.0)
        mineral_resources_kg_sb = float(r[28] or 0.0)
        gwp_biogenic = float(r[29] or 0.0)
        gwp_fossil = float(r[30] or 0.0)
        gwp_luluc = float(r[31] or 0.0)

        # Detail etape climate change stages: cols 15..21 (index 8..14 is Score unique, 15..21 is Climate Change)
        ag_gwp = _parse_stage_float(et[15])
        transfo_gwp = _parse_stage_float(et[16])
        pack_gwp = _parse_stage_float(et[17])
        transport_gwp = _parse_stage_float(et[18])
        distrib_gwp = _parse_stage_float(et[19])
        cons_gwp = _parse_stage_float(et[20])
        stage_sum_gwp = ag_gwp + transfo_gwp + pack_gwp + transport_gwp + distrib_gwp + cons_gwp
        non_pack_gwp = max(0.0, total_gwp - pack_gwp)
        pack_share_pct = (pack_gwp / total_gwp * 100.0) if total_gwp > 0 else 0.0

        # Detail etape water depletion stages (indicator index 14 -> offset 8 + 14*7 = 106..112)
        pack_water_m3 = _parse_stage_float(et[108])
        non_pack_water_m3 = max(0.0, water_depletion_m3 - pack_water_m3)

        # Detail etape fossil energy stages (indicator index 15 -> offset 8 + 15*7 = 113..119)
        pack_energy_mj = _parse_stage_float(et[115])
        non_pack_energy_mj = max(0.0, fossil_energy_mj - pack_energy_mj)

        records.append(
            {
                "product_id": f"AGB-{code_agb}",
                "code_agb": code_agb,
                "code_ciqual": str(r[1] or "").strip(),
                "name_fr": name_fr,
                "name_en": lci_name,
                "category": str(category),
                "is_core_dairy": is_core,
                "agribalyse_group_fr": group_fr,
                "agribalyse_subgroup_fr": subgroup_fr,
                "seasonality": str(r[6] or "").strip(),
                "airplane_transport_flag": str(r[7] or "").strip(),
                "delivery_mode": str(r[8] or "").strip(),
                "baseline_packaging_approach": str(r[9] or "").strip(),
                "preparation_mode": str(r[10] or "").strip(),
                "dqr_overall": float(r[11]) if r[11] is not None else None,
                "total_gwp_kgco2e_per_kg": round(total_gwp, 6),
                "non_packaging_gwp_kgco2e_per_kg": round(non_pack_gwp, 6),
                "agriculture_gwp_kgco2e_per_kg": round(ag_gwp, 6),
                "transformation_gwp_kgco2e_per_kg": round(transfo_gwp, 6),
                "packaging_stage_gwp_kgco2e_per_kg": round(pack_gwp, 6),
                "transport_gwp_kgco2e_per_kg": round(transport_gwp, 6),
                "distribution_gwp_kgco2e_per_kg": round(distrib_gwp, 6),
                "consumption_gwp_kgco2e_per_kg": round(cons_gwp, 6),
                "stage_sum_gwp_kgco2e_per_kg": round(stage_sum_gwp, 6),
                "packaging_share_of_gwp_pct": round(pack_share_pct, 3),
                "gwp_biogenic_kgco2e_per_kg": round(gwp_biogenic, 6),
                "gwp_fossil_kgco2e_per_kg": round(gwp_fossil, 6),
                "gwp_luluc_kgco2e_per_kg": round(gwp_luluc, 6),
                "single_score_mpt_per_kg": round(single_score_mpt, 6),
                "ozone_depletion_kg_cfc11e_per_kg": ozone_depletion,
                "particulate_matter_disease_inc_per_kg": particulate_matter,
                "acidification_mol_h_eq_per_kg": round(acidification, 6),
                "eutrophication_freshwater_kg_p_eq_per_kg": eutroph_freshwater,
                "eutrophication_marine_kg_n_eq_per_kg": round(eutroph_marine, 6),
                "land_use_pt_per_kg": round(land_use_pt, 4),
                "water_depletion_m3_per_kg": round(water_depletion_m3, 6),
                "non_packaging_water_m3_per_kg": round(non_pack_water_m3, 6),
                "packaging_stage_water_m3_per_kg": round(pack_water_m3, 6),
                "fossil_energy_mj_per_kg": round(fossil_energy_mj, 6),
                "non_packaging_fossil_energy_mj_per_kg": round(non_pack_energy_mj, 6),
                "packaging_stage_fossil_energy_mj_per_kg": round(pack_energy_mj, 6),
                "mineral_resources_kg_sb_eq_per_kg": mineral_resources_kg_sb,
                "milk_yield_kg_milk_per_kg_product": milk_yields.get(code_agb),
                "density_kg_per_l": _infer_dairy_density(category, lci_name),
                "functional_unit": "1 kg of food product consumed at consumer",
                "system_boundary": "Cradle-to-grave (Field to Plate; non_packaging columns subtract Emballage stage)",
                "lcia_method": "EF 3.1 (adapted) V1.00",
                "geography": "FR",
                "reference_year": "2024/2025",
                "source_dataset_id": "agribalyse_3_2",
                "source_type": str(DataSourceType.PUBLISHED_REFERENCE),
            }
        )

    wb.close()
    return pd.DataFrame(records)


def build_agribalyse_farm_gate_table(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Harmonize conventional and organic farm-gate dairy records from AGRIBALYSE 3.2."""
    agb_dir = raw_dir / "agribalyse_3_2"
    rows_out: list[dict[str, Any]] = []

    for mode, fname, sname, ref_year in [
        (
            "conventional",
            "AGRIBALYSE3.2_partie agriculture_conv_PublieNOV25.xlsx",
            "AGB 3.2 agricole conventionnel",
            "2024/2025",
        ),
        (
            "organic",
            "AGRIBALYSE3.2_Tableur agriculture_bio_PublieNov24.xlsx",
            "AGB 3.2 agricole biologique",
            "2024",
        ),
    ]:
        wb = openpyxl.load_workbook(agb_dir / fname, read_only=True, data_only=True)
        ws = wb[sname]
        for idx, r in enumerate(list(ws.iter_rows(values_only=True))[3:], start=1):
            if r[0] is None or "Dairy" not in str(r[3] or ""):
                continue
            rows_out.append(
                {
                    "farm_record_id": f"AGB-FARM-{mode[:4].upper()}-{idx:03d}",
                    "production_mode": mode,
                    "name_fr": str(r[0]).strip(),
                    "lci_name": str(r[1]).strip(),
                    "production_type": str(r[2] or "").strip(),
                    "category_path": str(r[3] or "").strip(),
                    "single_score_mpt_per_kg": float(r[4] or 0.0),
                    "gwp_total_kgco2e_per_kg": float(r[5] or 0.0),
                    "acidification_mol_h_eq_per_kg": float(r[12] or 0.0),
                    "eutrophication_freshwater_kg_p_eq_per_kg": float(r[13] or 0.0),
                    "eutrophication_marine_kg_n_eq_per_kg": float(r[14] or 0.0),
                    "land_use_pt_per_kg": float(r[17] or 0.0),
                    "water_depletion_m3_per_kg": float(r[18] or 0.0),
                    "fossil_energy_mj_per_kg": float(r[19] or 0.0),
                    "gwp_biogenic_kgco2e_per_kg": float(r[21] or 0.0),
                    "gwp_fossil_kgco2e_per_kg": float(r[22] or 0.0),
                    "gwp_luluc_kgco2e_per_kg": float(r[23] or 0.0),
                    "functional_unit": "1 kg of agricultural product leaving farm gate",
                    "system_boundary": "Cradle-to-farm-gate",
                    "lcia_method": "EF 3.1 (adapted) V1.00",
                    "geography": "FR",
                    "reference_year": ref_year,
                    "source_dataset_id": "agribalyse_3_2",
                    "source_type": str(DataSourceType.PUBLISHED_REFERENCE),
                }
            )
        wb.close()

    return pd.DataFrame(rows_out)


def build_pdo_cheese_harmonized_table(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Harmonize all 7 cheese-level PDO tables onto the 44 canonical French PDO cheeses."""
    pdo_dir = raw_dir / "pdo_cheese_lca"

    def _read_sheet(fname: str) -> list[tuple[Any, ...]]:
        with (pdo_dir / fname).open("rb") as handle:
            wb = openpyxl.load_workbook(handle, read_only=True, data_only=True)
            ws = wb[wb.sheetnames[0]]
            data = list(ws.iter_rows(values_only=True))
            wb.close()
            return data

    char_rows = _read_sheet("dataset_PDOcheeses_characterization.xlsx")
    alloc_rows = _read_sheet("dataset_PDOcheeses_allocations.xlsx")
    coprod_rows = _read_sheet("dataset_PDOcheeses_coproducts.xlsx")
    dist_rows = _read_sheet("data_PDOcheeses_distances.xlsx")
    spec_rows = _read_sheet("data_PDOcheeses_specifications.xlsx")
    lci_rows = _read_sheet("data_PDOcheeses_LCI")
    lcia_rows = _read_sheet("data_PDOcheeses_LCIA.xlsx")

    char_by_name = {
        normalize_pdo_cheese_name(str(r[1])): r for r in char_rows[2:] if r[1]
    }
    alloc_by_name = {
        normalize_pdo_cheese_name(str(r[1])): r for r in alloc_rows[4:] if r[1]
    }
    coprod_by_name = {
        normalize_pdo_cheese_name(str(r[1])): r for r in coprod_rows[4:] if r[1]
    }
    dist_by_name = {
        normalize_pdo_cheese_name(str(r[1])): r for r in dist_rows[3:] if r[1]
    }
    spec_by_name = {
        normalize_pdo_cheese_name(str(r[2])): r
        for r in spec_rows[2:]
        if len(r) > 2 and r[2]
    }
    lci_init_by_name = {
        normalize_pdo_cheese_name(str(r[1])): r for r in lci_rows[4:48] if r[1]
    }
    lci_add_by_name = {
        normalize_pdo_cheese_name(str(r[1])): r for r in lci_rows[55:99] if r[1]
    }

    # Parse 1,232 LCIA rows grouped by canonical cheese name (44 cheeses x 28 indicators)
    lcia_by_cheese: dict[str, dict[str, tuple[Any, ...]]] = {}
    current_cheese: str | None = None
    for r in lcia_rows[3:]:
        if r[0] is not None and str(r[0]).strip():
            current_cheese = normalize_pdo_cheese_name(str(r[0]))
            lcia_by_cheese.setdefault(current_cheese, {})
        if current_cheese and r[1] is not None:
            ind_name = str(r[1]).strip()
            lcia_by_cheese[current_cheese][ind_name] = r

    canonical_names = sorted(char_by_name.keys())
    if len(canonical_names) != 44:
        raise ValueError(f"Expected 44 PDO cheeses, got {len(canonical_names)}")

    records: list[dict[str, Any]] = []
    for idx, name in enumerate(canonical_names, start=1):
        c_row = char_by_name[name]
        a_row = alloc_by_name[name]
        cp_row = coprod_by_name[name]
        d_row = dist_by_name[name]
        s_row = spec_by_name[name]
        li_row = lci_init_by_name[name]
        la_row = lci_add_by_name[name]
        ind_map = lcia_by_cheese[name]

        cc_row = ind_map["Climate change"]
        wd_row = ind_map["Water use"]
        fe_row = ind_map["Resource use, fossils"]
        ac_row = ind_map["Acidification"]
        eu_fw_row = ind_map["Eutrophication, freshwater"]

        # Unallocated raw milk inputs (cols 2..5 in LCI)
        milk_cow_low = float(li_row[2] or 0.0)
        milk_cow_high = float(li_row[3] or 0.0)
        milk_sheep = float(li_row[4] or 0.0)
        milk_goat = float(li_row[5] or 0.0)
        total_raw_milk_kg = milk_cow_low + milk_cow_high + milk_sheep + milk_goat

        # Base scenario GWP stages (cols 3..10)
        gwp_base_total = float(cc_row[3] or 0.0)
        gwp_base_milk_prod = float(cc_row[4] or 0.0)
        gwp_base_milk_trans = float(cc_row[5] or 0.0)
        gwp_base_milk_pump = float(cc_row[6] or 0.0)
        gwp_base_milk_stor = float(cc_row[7] or 0.0)
        gwp_base_milk_proc = float(cc_row[8] or 0.0)
        gwp_base_ripening = float(cc_row[9] or 0.0)
        gwp_base_cleaning = float(cc_row[10] or 0.0)
        gwp_base_post_farm = (
            gwp_base_milk_trans
            + gwp_base_milk_pump
            + gwp_base_milk_stor
            + gwp_base_milk_proc
            + gwp_base_ripening
            + gwp_base_cleaning
        )

        # Alternative scenario GWP stages (cols 15..23)
        gwp_alt_total = float(cc_row[15] or 0.0)
        gwp_alt_milk_prod = float(cc_row[16] or 0.0)
        gwp_alt_ripening = float(cc_row[21] or 0.0)
        gwp_alt_cheese_trans = float(cc_row[23] or 0.0)
        gwp_alt_post_farm = gwp_alt_total - gwp_alt_milk_prod

        raw_tech = " ".join(str(c_row[2] or "").split())
        if raw_tech.lower() == "pâte pressée non cuite":
            raw_tech = "Pressed uncooked cheese"

        records.append(
            {
                "pdo_cheese_id": f"PDO-{idx:02d}",
                "cheese_name": name,
                "technology": raw_tech,
                "milk_type": str(c_row[3] or "").strip(),
                "ripening_days": float(c_row[4] or 0.0),
                "allocation_before_skimming": float(a_row[2] or 0.0),
                "allocation_skimming_to_draining": float(a_row[3] or 0.0),
                "allocation_after_draining": float(a_row[4] or 0.0),
                "cream_coproduct_kg_per_kg_cheese": float(cp_row[2] or 0.0),
                "whey_coproduct_kg_per_kg_cheese": float(cp_row[3] or 0.0),
                "max_authorized_distance_km": float(d_row[2] or 0.0),
                "inao_specification_url": str(s_row[3] or "").strip(),
                # LCI unallocated physical inputs per 1 kg ripened cheese
                "lci_cow_milk_lowland_kg": milk_cow_low,
                "lci_cow_milk_highland_kg": milk_cow_high,
                "lci_sheep_milk_kg": milk_sheep,
                "lci_goat_milk_kg": milk_goat,
                "lci_total_raw_milk_kg": round(total_raw_milk_kg, 6),
                "lci_milk_transport_tkm": float(li_row[6] or 0.0),
                "lci_milk_pumping_kwh": float(li_row[7] or 0.0),
                "lci_milk_storage_steel_kg": float(li_row[8] or 0.0),
                "lci_milk_storage_kwh": float(li_row[9] or 0.0),
                "lci_processing_steel_kg": float(li_row[10] or 0.0),
                "lci_processing_copper_kg": float(li_row[11] or 0.0),
                "lci_processing_wood_m3": float(li_row[12] or 0.0),
                "lci_processing_electricity_kwh": float(li_row[13] or 0.0),
                "lci_ripening_steel_kg_initial": float(li_row[14] or 0.0),
                "lci_ripening_wood_m3_initial": float(li_row[15] or 0.0),
                "lci_ripening_electricity_kwh_initial": float(li_row[16] or 0.0),
                "lci_cleaning_water_kg": float(li_row[17] or 0.0),
                "lci_cleaning_naoh_kg": float(li_row[18] or 0.0),
                "lci_cleaning_hno3_kg": float(li_row[19] or 0.0),
                "lci_cheese_transport_tkm_additional": float(la_row[14] or 0.0),
                "lci_ripening_wood_m3_additional": float(la_row[16] or 0.0),
                "lci_ripening_electricity_kwh_additional": float(la_row[17] or 0.0),
                # LCIA Base Scenario (ripening at cheese factory)
                "gwp_base_total_kgco2e_per_kg": round(gwp_base_total, 6),
                "gwp_base_milk_production_kgco2e_per_kg": round(gwp_base_milk_prod, 6),
                "gwp_base_milk_transport_kgco2e_per_kg": round(gwp_base_milk_trans, 6),
                "gwp_base_milk_pumping_kgco2e_per_kg": round(gwp_base_milk_pump, 6),
                "gwp_base_milk_storage_kgco2e_per_kg": round(gwp_base_milk_stor, 6),
                "gwp_base_milk_processing_kgco2e_per_kg": round(gwp_base_milk_proc, 6),
                "gwp_base_cheese_ripening_kgco2e_per_kg": round(gwp_base_ripening, 6),
                "gwp_base_equipment_cleaning_kgco2e_per_kg": round(gwp_base_cleaning, 6),
                "gwp_base_post_farm_total_kgco2e_per_kg": round(gwp_base_post_farm, 6),
                # LCIA Alternative Scenario (ripening in shared ripening room)
                "gwp_alt_total_kgco2e_per_kg": round(gwp_alt_total, 6),
                "gwp_alt_milk_production_kgco2e_per_kg": round(gwp_alt_milk_prod, 6),
                "gwp_alt_cheese_ripening_kgco2e_per_kg": round(gwp_alt_ripening, 6),
                "gwp_alt_cheese_transport_kgco2e_per_kg": round(gwp_alt_cheese_trans, 6),
                "gwp_alt_post_farm_total_kgco2e_per_kg": round(gwp_alt_post_farm, 6),
                # Supporting EF 3.0 / ILCD indicators
                "water_use_base_m3_depriv_per_kg": float(wd_row[3] or 0.0),
                "water_use_alt_m3_depriv_per_kg": float(wd_row[15] or 0.0),
                "fossil_resource_use_base_mj_per_kg": float(fe_row[3] or 0.0),
                "fossil_resource_use_alt_mj_per_kg": float(fe_row[15] or 0.0),
                "acidification_base_mol_h_eq_per_kg": float(ac_row[3] or 0.0),
                "freshwater_eutrophication_base_kg_p_eq_per_kg": float(eu_fw_row[3] or 0.0),
                # Provenance
                "functional_unit": "1 kg of ripened PDO cheese (packaging excluded)",
                "system_boundary": "Cradle-to-ripening-exit (excludes packaging, retail, consumer)",
                "lcia_method": "EF 3.0 / ILCD Midpoint (28 indicators)",
                "geography": "FR",
                "reference_year": "2020/2022",
                "source_dataset_id": "pdo_cheese_lca",
                "source_type": str(DataSourceType.PUBLISHED_REFERENCE),
                "unit_notes": (
                    "lci_ripening_wood_m3_additional normalized to m3 (raw row-54 header says 'kg' "
                    "by typo, but numerical values match Initial m3 and Ecoinvent Sawnwood m3)"
                ),
            }
        )

    return pd.DataFrame(records)


def build_uslci_curated_table(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Extract and normalize the 56 curated USLCI processes with direct elementary GHG & electricity."""
    from dairyeco.data.audit_inspectors import inspect_uslci

    audit = inspect_uslci(raw_dir)
    proc_dir = raw_dir / "uslci" / "processes"

    rows_out: list[dict[str, Any]] = []
    for item in audit.curated_packaging_energy_processes:
        uuid = item["uuid"]
        proc_path = proc_dir / f"{uuid}.json"
        data = json.loads(proc_path.read_text(encoding="utf-8"))
        exchanges = data.get("exchanges", [])

        qref_amt = float(item["qref_amount"] or 1.0)
        qref_unit = str(item["qref_unit"] or "kg").strip()
        if qref_unit in UNIT_TO_KG:
            norm_divisor = qref_amt * UNIT_TO_KG[qref_unit]
            normalized_unit = "kg"
        else:
            norm_divisor = qref_amt
            normalized_unit = qref_unit

        direct_ghg_kgco2e = 0.0
        direct_elec_kwh = 0.0
        direct_water_l = 0.0

        for ex in exchanges:
            flow = ex.get("flow") or {}
            fname = str(flow.get("name") or "").strip().lower()
            ftype = str(flow.get("flowType") or "")
            amt = float(ex.get("amount") or 0.0)
            unit_name = str((ex.get("unit") or {}).get("name") or "").strip()

            if ftype == "ELEMENTARY_FLOW" and not ex.get("isInput"):
                for ghg_key, factor in ELEMENTARY_GWP100_FACTORS.items():
                    if fname == ghg_key or fname.startswith(f"{ghg_key},"):
                        flow_kg = amt * UNIT_TO_KG.get(unit_name, 1.0)
                        direct_ghg_kgco2e += flow_kg * factor
                        break
            elif ftype == "ELEMENTARY_FLOW" and ex.get("isInput") and "water" in fname:
                if unit_name in {"l", "L", "kg"}:
                    direct_water_l += amt
                elif unit_name == "m3":
                    direct_water_l += amt * 1000.0
            elif ftype == "PRODUCT_FLOW" and ex.get("isInput") and "electricity" in fname:
                if unit_name == "kWh":
                    direct_elec_kwh += amt
                elif unit_name == "MJ":
                    direct_elec_kwh += amt / 3.6

        rows_out.append(
            {
                "uslci_process_uuid": uuid,
                "domain_role": item["domain_role"],
                "process_name": item["name"],
                "category": item["category"],
                "process_type": item["process_type"],
                "geography": item["location"],
                "valid_from": item["valid_from"],
                "qref_flow": item["qref_flow"],
                "original_qref_amount": qref_amt,
                "original_qref_unit": qref_unit,
                "normalized_unit": normalized_unit,
                "normalization_divisor": round(norm_divisor, 8),
                "direct_elementary_gwp_kgco2e_per_norm_unit": round(
                    direct_ghg_kgco2e / norm_divisor, 6
                ),
                "direct_electricity_input_kwh_per_norm_unit": round(
                    direct_elec_kwh / norm_divisor, 6
                ),
                "direct_water_input_l_per_norm_unit": round(
                    direct_water_l / norm_divisor, 6
                ),
                "tech_exchanges": item["tech_exchanges"],
                "elementary_exchanges": item["elementary_exchanges"],
                "suitability_status": item["suitability_status"],
                "source_dataset_id": "uslci",
                "source_type": str(DataSourceType.PUBLISHED_REFERENCE),
            }
        )

    return pd.DataFrame(rows_out)


def build_unified_packaging_impact_factors(
    raw_dir: Path = RAW_DIR,
    reference_dir: Path = REFERENCE_DIR,
    uslci_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build unified, provenance-tracked impact factor catalog for the LCA engine."""
    nist_df = pd.read_csv(reference_dir / "nist_plastic_carbon_intensity.csv")
    if uslci_df is None:
        uslci_df = build_uslci_curated_table(raw_dir)
    uslci_by_prefix = {
        str(row["uslci_process_uuid"])[:8]: row for _, row in uslci_df.iterrows()
    }

    usa_grid_rows = nist_df[
        (nist_df["record_type"] == "background_energy_fig18")
        & (nist_df["material_or_product"] == "Electricity grid mix")
        & (nist_df["region"] == "USA")
    ]
    usa_grid_ci = float(usa_grid_rows.iloc[0]["normalized_value"]) if not usa_grid_rows.empty else 0.466

    factors: list[dict[str, Any]] = []

    # 1. Virgin polymers from NIST/ANL 2024 across regions (PET, HDPE, LDPE, PP, PVC)
    # Note: NIST 2024 reports GWP CI only; fossil_energy_mj and water_l are secondary literature proxies.
    resin_energy_mj = {"PET": 68.0, "HDPE": 76.0, "LDPE": 78.0, "PP": 73.0, "PVC": 56.0}
    resin_water_l = {"PET": 16.5, "HDPE": 11.0, "LDPE": 14.0, "PP": 10.5, "PVC": 18.0}

    nist_baselines = nist_df[
        nist_df["record_type"].isin(
            ["resin_cross_regional_average", "resin_regional_baseline"]
        )
    ]
    for _, row in nist_baselines.iterrows():
        mat = str(row["material_or_product"]).strip()
        reg = str(row["region"]).strip()
        val = float(row["normalized_value"])
        factors.append(
            {
                "factor_id": f"MAT-{mat}-{reg.upper().replace(' ', '_').replace('-', '_')}",
                "domain": "material_production",
                "material_or_process": mat,
                "pathway_or_subtype": "virgin_resin_baseline",
                "geography": reg,
                "reference_year": "2024",
                "gwp_kgco2e_per_unit": round(val, 4),
                "fossil_energy_mj_per_unit": resin_energy_mj.get(mat, 70.0),
                "water_l_per_unit": resin_water_l.get(mat, 12.0),
                "electricity_kwh_per_unit": 0.0,
                "unit": "kg",
                "original_value": float(row["value"]),
                "original_unit": str(row["original_unit"]),
                "functional_unit": str(row["functional_unit"]),
                "system_boundary": str(row["system_boundary"]),
                "lcia_method": "GREET 2022/2023 GWP100",
                "source_dataset_id": "anl_nist_regional_plastics_2024",
                "source_record_id": str(row["record_id"]),
                "source_type": str(DataSourceType.PUBLISHED_REFERENCE),
                "notes": (
                    f"{row['notes']} (GWP is published_reference NIST/ANL 2024; "
                    "fossil_energy_mj and water_l are secondary literature proxies)"
                ),
            }
        )

    # 2. Additional USLCI virgin & bio polymers (LLDPE, GPPS, HIPS, EPS, PLA)
    # Standalone USLCI unit processes lack upstream provider roll-up, so cradle-to-gate totals are tagged PROXY.
    additional_polymers = [
        ("LLDPE", "1dbafde2", 1.48, 75.0, 11.5, "Cradle-to-gate proxy anchored to USLCI LLDPE unit process (unlinked upstream inputs)"),
        ("GPPS", "13821cca", 2.52, 84.0, 15.0, "Cradle-to-gate proxy anchored to USLCI GPPS unit process (unlinked upstream inputs)"),
        ("HIPS", "d1c572b0", 2.64, 86.0, 15.5, "Cradle-to-gate proxy anchored to USLCI HIPS unit process (unlinked upstream inputs)"),
        ("EPS", "cf1241fd", 2.58, 85.0, 16.0, "Cradle-to-gate proxy anchored to USLCI EPS unit process (normalized from 1000 kg qref)"),
        ("PLA", "e281027f", 1.82, 42.0, 28.0, "Cradle-to-gate proxy anchored to USLCI PLA unit process (unlinked upstream inputs)"),
    ]
    for mat, pref, gwp_val, mj_val, w_val, note in additional_polymers:
        u_row = uslci_by_prefix[pref]
        factors.append(
            {
                "factor_id": f"MAT-{mat}-USLCI",
                "domain": "material_production",
                "material_or_process": mat,
                "pathway_or_subtype": "virgin_resin_baseline",
                "geography": str(u_row["geography"]),
                "reference_year": str(u_row["valid_from"])[:4] or "2018",
                "gwp_kgco2e_per_unit": gwp_val,
                "fossil_energy_mj_per_unit": mj_val,
                "water_l_per_unit": w_val,
                "electricity_kwh_per_unit": float(
                    u_row["direct_electricity_input_kwh_per_norm_unit"]
                ),
                "unit": "kg",
                "original_value": float(u_row["original_qref_amount"]),
                "original_unit": str(u_row["original_qref_unit"]),
                "functional_unit": f"1 kg of {mat} resin at plant",
                "system_boundary": "Cradle-to-gate proxy (standalone USLCI unit process lacks upstream links)",
                "lcia_method": "IPCC AR6 GWP100 + literature roll-up proxy",
                "source_dataset_id": "uslci",
                "source_record_id": str(u_row["uslci_process_uuid"]),
                "source_type": str(DataSourceType.PROXY),
                "notes": note,
            }
        )

    # 3. Mechanically recycled polymers (USLCI unit processes lack upstream collection/reprocessing roll-up -> PROXY)
    recycled_polymers = [
        ("HDPE", "17664c37", 0.48, 12.5, 4.2, "Literature roll-up proxy anchored to USLCI rHDPE flake unit process (RNA)"),
        ("PET", "f7b7280d", 0.56, 14.8, 5.5, "Literature roll-up proxy anchored to USLCI rPET flake unit process (RNA)"),
        ("PP", "185648c2", 0.46, 11.8, 3.9, "Literature roll-up proxy anchored to USLCI rPP pellet unit process (RNA)"),
        ("LDPE", "17664c37", 0.52, 13.2, 4.5, "Proxy from rHDPE mechanical recycling (RNA)"),
        ("LLDPE", "17664c37", 0.52, 13.2, 4.5, "Proxy from rHDPE mechanical recycling (RNA)"),
    ]
    for mat, pref, gwp_val, mj_val, w_val, note in recycled_polymers:
        u_row = uslci_by_prefix[pref]
        elec_kwh = float(u_row["direct_electricity_input_kwh_per_norm_unit"])
        factors.append(
            {
                "factor_id": f"MAT-REC-{mat}",
                "domain": "material_production",
                "material_or_process": mat,
                "pathway_or_subtype": "mechanically_recycled_resin",
                "geography": str(u_row["geography"]),
                "reference_year": "2016",
                "gwp_kgco2e_per_unit": gwp_val,
                "fossil_energy_mj_per_unit": mj_val,
                "water_l_per_unit": w_val,
                "electricity_kwh_per_unit": elec_kwh,
                "unit": "kg",
                "original_value": 1.0,
                "original_unit": "kg",
                "functional_unit": f"1 kg of mechanically recycled {mat}",
                "system_boundary": "Collection, sorting, washing, and pelletization (cut-off allocation proxy)",
                "lcia_method": "IPCC AR6 GWP100 + regional electricity proxy",
                "source_dataset_id": "uslci",
                "source_record_id": str(u_row["uslci_process_uuid"]),
                "source_type": str(DataSourceType.PROXY),
                "notes": note,
            }
        )

    # 4. Paperboard, Corrugated, Aluminium, Glass, and LPB
    # Primary aluminium (99963138) is an LCI_RESULT with 583 elementary flows -> genuine published_reference!
    al_prim = uslci_by_prefix["99963138"]
    al_prim_gwp = round(float(al_prim["direct_elementary_gwp_kgco2e_per_norm_unit"]), 4)

    non_polymer_materials = [
        (
            "paperboard",
            "virgin_resin_baseline",
            str(uslci_by_prefix["c245a252"]["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            0.94,
            24.5,
            float(uslci_by_prefix["c245a252"]["direct_water_input_l_per_norm_unit"]),
            float(uslci_by_prefix["c245a252"]["direct_electricity_input_kwh_per_norm_unit"]),
            "Containerboard average production proxy (biogenic-adjusted from USLCI unit process, 1.10516 kg qref)",
        ),
        (
            "paperboard",
            "mechanically_recycled_resin",
            str(uslci_by_prefix["12ba204b"]["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            0.71,
            16.2,
            float(uslci_by_prefix["12ba204b"]["direct_water_input_l_per_norm_unit"]),
            float(uslci_by_prefix["12ba204b"]["direct_electricity_input_kwh_per_norm_unit"]),
            "Containerboard 100% recycled proxy (anchored to USLCI unit process, 1.10516 kg qref)",
        ),
        (
            "corrugated_board",
            "virgin_resin_baseline",
            str(uslci_by_prefix["226ed3c2"]["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            0.98,
            25.8,
            19.2,
            0.46,
            "Corrugated product average cradle-to-gate proxy (anchored to USLCI unit process)",
        ),
        (
            "corrugated_board",
            "mechanically_recycled_resin",
            str(uslci_by_prefix["9c10be0f"]["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            0.75,
            17.4,
            12.4,
            0.41,
            "Corrugated product 100% recycled cradle-to-gate proxy (anchored to USLCI unit process)",
        ),
        (
            "liquid_packaging_board",
            "virgin_resin_baseline",
            "AGB-LPB-PROXY",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            0.88,
            22.0,
            21.0,
            0.39,
            "Liquid packaging board substrate proxy (PE and Al layers modelled as separate BOM components)",
        ),
        (
            "liquid_packaging_board",
            "mechanically_recycled_resin",
            "AGB-LPB-REC-PROXY",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            0.72,
            17.5,
            14.5,
            0.35,
            "Partially recycled paperboard substrate proxy",
        ),
        (
            "aluminium",
            "virgin_resin_baseline",
            str(al_prim["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PUBLISHED_REFERENCE,
            al_prim_gwp,
            138.0,
            42.0,
            float(al_prim["direct_electricity_input_kwh_per_norm_unit"]),
            "USLCI LCI_RESULT: Aluminum primary ingot at plant (583 elementary flows; GWP computed directly from USLCI JSON)",
        ),
        (
            "aluminium",
            "mechanically_recycled_resin",
            str(uslci_by_prefix["9cc8fafa"]["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            1.42,
            21.5,
            7.8,
            float(uslci_by_prefix["9cc8fafa"]["direct_electricity_input_kwh_per_norm_unit"]),
            "Secondary aluminium ingot proxy (anchored to legacy USLCI unit process 9cc8fafa)",
        ),
        (
            "glass",
            "virgin_resin_baseline",
            "AGB-GLASS-VIRGIN-REF",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            1.05,
            15.8,
            6.4,
            0.32,
            "Container glass (virgin batch) proxy derived from AGRIBALYSE 3.2 packaging documentation (fills USLCI container-glass gap)",
        ),
        (
            "glass",
            "mechanically_recycled_resin",
            "AGB-GLASS-CULLET-REF",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            0.68,
            10.2,
            4.1,
            0.26,
            "Container glass (100% recycled cullet melting) proxy derived from AGRIBALYSE 3.2 packaging documentation",
        ),
    ]
    for mat, subtype, rec_id, ds_id, stype, gwp_v, mj_v, w_v, el_v, note in non_polymer_materials:
        factors.append(
            {
                "factor_id": f"MAT-{mat.upper()}-{subtype[:6].upper()}",
                "domain": "material_production",
                "material_or_process": mat,
                "pathway_or_subtype": subtype,
                "geography": "US/RNA" if ds_id == "uslci" else "FR/EU",
                "reference_year": "2022/2024",
                "gwp_kgco2e_per_unit": round(gwp_v, 4),
                "fossil_energy_mj_per_unit": round(mj_v, 4),
                "water_l_per_unit": round(w_v, 4),
                "electricity_kwh_per_unit": round(el_v, 4),
                "unit": "kg",
                "original_value": round(gwp_v, 4),
                "original_unit": "kg CO2e/kg",
                "functional_unit": f"1 kg of {mat} ({subtype})",
                "system_boundary": "Cradle-to-gate material production",
                "lcia_method": "IPCC GWP100 / EF 3.1",
                "source_dataset_id": ds_id,
                "source_record_id": rec_id,
                "source_type": str(stype),
                "notes": note,
            }
        )

    # 5. Package conversion processes (per 1 kg of converted component)
    # Processes with direct USLCI electricity inputs are computed from USLCI electricity * NIST USA grid CI (0.466).
    inj = uslci_by_prefix["89a2b59a"]
    thm = uslci_by_prefix["18c37a18"]
    ext = uslci_by_prefix["e2f66950"]
    foil_roll = uslci_by_prefix["2b196386"]

    def _conv_from_uslci(u: pd.Series, note: str) -> tuple[str, str, DataSourceType, float, float, float, float, str]:
        elec = float(u["direct_electricity_input_kwh_per_norm_unit"])
        direct_gwp = float(u["direct_elementary_gwp_kgco2e_per_norm_unit"])
        water = float(u["direct_water_input_l_per_norm_unit"])
        gwp = round(direct_gwp + elec * usa_grid_ci, 4)
        mj = round(elec * 3.6, 2)
        return (str(u["uslci_process_uuid"]), "uslci", DataSourceType.PUBLISHED_REFERENCE, gwp, mj, water, elec, note)

    conversions = [
        ("injection_molding", *_conv_from_uslci(inj, "Computed from USLCI injection molding electricity (1.79 kWh/kg) x NIST USA grid CI")),
        ("thermoforming", *_conv_from_uslci(thm, "Computed from USLCI thermoforming electricity (2.9014 kWh/kg) x NIST USA grid CI")),
        ("film_extrusion", *_conv_from_uslci(ext, "Computed from USLCI extrusion electricity (0.468 kWh/kg) x NIST USA grid CI")),
        (
            "blow_molding",
            "AGB-BLOW-MOLD-PROXY",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            0.62,
            10.4,
            3.1,
            1.26,
            "Bottle blow molding proxy (fills USLCI blow-molding gap; scaled from extrusion + compressed air)",
        ),
        (
            "carton_converting",
            "AGB-CARTON-CONV-PROXY",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            0.22,
            4.1,
            1.2,
            0.45,
            "Multilayer carton lamination, printing, and die-cutting proxy",
        ),
        (
            "corrugated_converting",
            str(uslci_by_prefix["226ed3c2"]["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            0.14,
            2.8,
            0.9,
            0.28,
            "Corrugated box converting & slotting proxy",
        ),
        (
            "glass_forming",
            "AGB-GLASS-FORM-PROXY",
            "agribalyse_3_2",
            DataSourceType.PROXY,
            0.18,
            3.2,
            0.8,
            0.36,
            "Bottle annealing & finishing beyond batch melting proxy",
        ),
        (
            "aluminium_foil_rolling",
            str(foil_roll["uslci_process_uuid"]),
            "uslci",
            DataSourceType.PROXY,
            0.58,
            9.6,
            2.4,
            1.18,
            "Foil gauge finishing proxy (USLCI 2b196386 covers bulk cold rolling incl. thermal fuel)",
        ),
        (
            "none",
            "NONE",
            "uslci",
            DataSourceType.PUBLISHED_REFERENCE,
            0.0,
            0.0,
            0.0,
            0.0,
            "No additional conversion step",
        ),
    ]
    for conv_name, rec_id, ds_id, stype, gwp_v, mj_v, w_v, el_v, note in conversions:
        factors.append(
            {
                "factor_id": f"CONV-{conv_name.upper()}",
                "domain": "package_conversion",
                "material_or_process": conv_name,
                "pathway_or_subtype": "gate_to_gate_conversion",
                "geography": "US/RNA" if ds_id == "uslci" else "FR/EU",
                "reference_year": "2020/2024",
                "gwp_kgco2e_per_unit": round(gwp_v, 4),
                "fossil_energy_mj_per_unit": round(mj_v, 4),
                "water_l_per_unit": round(w_v, 4),
                "electricity_kwh_per_unit": round(el_v, 4),
                "unit": "kg",
                "original_value": round(gwp_v, 4),
                "original_unit": "kg CO2e/kg",
                "functional_unit": "1 kg of converted package component",
                "system_boundary": "Gate-to-gate converting process",
                "lcia_method": "IPCC GWP100 + grid electricity",
                "source_dataset_id": ds_id,
                "source_record_id": rec_id,
                "source_type": str(stype),
                "notes": note,
            }
        )

    # 6. Freight transport modes computed directly from USLCI elementary GHG flows (per 1 t*km)
    transports = [
        ("combination_truck", "34156f3c", 1.24, 0.05, "USLCI Combination truck, diesel powered (1 t*km; direct tailpipe GHG from JSON)"),
        ("single_unit_truck", "45b70b50", 2.98, 0.11, "USLCI Single unit truck, diesel powered (1 t*km; direct tailpipe GHG from JSON)"),
        ("light_commercial_truck", "bf6e7378", 5.70, 0.18, "USLCI Light commercial truck, diesel powered (1 t*km; direct tailpipe GHG from JSON)"),
        ("rail", "7de9c230", 0.32, 0.02, "USLCI Freight train, diesel powered (1 t*km; direct tailpipe GHG from JSON)"),
    ]
    for mode_name, pref, mj_v, w_v, note in transports:
        u_row = uslci_by_prefix[pref]
        gwp_v = round(float(u_row["direct_elementary_gwp_kgco2e_per_norm_unit"]), 4)
        factors.append(
            {
                "factor_id": f"TRANS-{mode_name.upper()}",
                "domain": "transport",
                "material_or_process": mode_name,
                "pathway_or_subtype": "freight_transport",
                "geography": "US",
                "reference_year": "2018",
                "gwp_kgco2e_per_unit": gwp_v,
                "fossil_energy_mj_per_unit": mj_v,
                "water_l_per_unit": w_v,
                "electricity_kwh_per_unit": 0.0,
                "unit": "t*km",
                "original_value": 1.0,
                "original_unit": "t*km",
                "functional_unit": "1 metric ton-km of freight transport",
                "system_boundary": "Gate-to-gate vehicle operation + fuel combustion",
                "lcia_method": "IPCC AR6 GWP100",
                "source_dataset_id": "uslci",
                "source_record_id": str(u_row["uslci_process_uuid"]),
                "source_type": str(DataSourceType.PUBLISHED_REFERENCE),
                "notes": note,
            }
        )

    # 7. End-of-life disposal/sorting factors (USLCI direct flows where available; others tagged PROXY)
    mrf_row = uslci_by_prefix["4c476cdb"]
    mrf_elec = float(mrf_row["direct_electricity_input_kwh_per_norm_unit"])
    inc_pl_row = uslci_by_prefix["30a3f9c8"]
    inc_pb_row = uslci_by_prefix["9da15ed3"]
    lf_pb_row = uslci_by_prefix["67119c4c"]

    eol_factors = [
        (
            "mrf_sorting",
            "all_recyclables",
            str(mrf_row["uslci_process_uuid"]),
            DataSourceType.PUBLISHED_REFERENCE,
            round(mrf_elec * usa_grid_ci, 4),
            round(mrf_elec * 3.6, 2),
            0.15,
            round(mrf_elec, 4),
            "Computed from USLCI MRF single-stream sorting electricity (0.0894 kWh/kg) x NIST USA grid CI",
        ),
        (
            "incineration_plastics",
            "plastics",
            str(inc_pl_row["uslci_process_uuid"]),
            DataSourceType.PUBLISHED_REFERENCE,
            round(float(inc_pl_row["direct_elementary_gwp_kgco2e_per_norm_unit"]), 4),
            0.40,
            0.80,
            0.0,
            "Computed from USLCI MSW combustion of plastics (direct GHG from JSON, normalized from 1 sh tn)",
        ),
        (
            "incineration_paperboard",
            "paper_board",
            str(inc_pb_row["uslci_process_uuid"]),
            DataSourceType.PUBLISHED_REFERENCE,
            round(float(inc_pb_row["direct_elementary_gwp_kgco2e_per_norm_unit"]), 4),
            0.25,
            0.45,
            0.0,
            "Computed from USLCI MSW combustion of paper/board (direct GHG from JSON, normalized from 1 sh tn)",
        ),
        (
            "incineration_inert",
            "glass_aluminium",
            "AGB-INERT-INCIN-PROXY",
            DataSourceType.PROXY,
            0.025,
            0.30,
            0.20,
            0.0,
            "Inert material handling in MSW WTE facility proxy",
        ),
        (
            "landfill_plastics",
            "plastics",
            str(uslci_by_prefix["abe35439"]["uslci_process_uuid"]),
            DataSourceType.PROXY,
            0.042,
            0.52,
            0.12,
            0.0,
            "MSW landfilling of mixed plastics equipment/handling proxy (USLCI abe35439 has 0 direct elementary GHG)",
        ),
        (
            "landfill_paperboard",
            "paper_board",
            str(lf_pb_row["uslci_process_uuid"]),
            DataSourceType.PUBLISHED_REFERENCE,
            round(float(lf_pb_row["direct_elementary_gwp_kgco2e_per_norm_unit"]), 4),
            0.48,
            0.15,
            0.0,
            "Computed from USLCI MSW landfilling of mixed paper/board (anaerobic methane direct GHG from JSON)",
        ),
        (
            "landfill_glass_metal",
            "glass_aluminium",
            str(uslci_by_prefix["1bea9d6a"]["uslci_process_uuid"]),
            DataSourceType.PROXY,
            0.028,
            0.38,
            0.08,
            0.0,
            "MSW landfilling of glass/metals handling proxy (USLCI 1bea9d6a has 0 direct elementary GHG)",
        ),
    ]
    for proc_key, subtype, rec_uuid, stype, gwp_v, mj_v, w_v, el_v, note in eol_factors:
        factors.append(
            {
                "factor_id": f"EOL-{proc_key.upper()}",
                "domain": "end_of_life",
                "material_or_process": proc_key,
                "pathway_or_subtype": subtype,
                "geography": "RNA",
                "reference_year": "2018",
                "gwp_kgco2e_per_unit": round(gwp_v, 4),
                "fossil_energy_mj_per_unit": mj_v,
                "water_l_per_unit": w_v,
                "electricity_kwh_per_unit": el_v,
                "unit": "kg",
                "original_value": 1.0,
                "original_unit": "sh tn or Mg",
                "functional_unit": "1 kg of packaging waste entering EoL route",
                "system_boundary": "Waste collection, sorting/combustion/landfilling (cut-off approach)",
                "lcia_method": "IPCC AR6 GWP100",
                "source_dataset_id": "uslci" if stype == DataSourceType.PUBLISHED_REFERENCE else "uslci_proxy",
                "source_record_id": rec_uuid,
                "source_type": str(stype),
                "notes": note,
            }
        )

    return pd.DataFrame(factors)


def run_phase1_harmonization(
    raw_dir: Path = RAW_DIR,
    reference_dir: Path = REFERENCE_DIR,
    processed_dir: Path = PROCESSED_DIR,
) -> dict[str, Path]:
    """Execute full Phase 1 harmonization and persist CSV + Parquet tables."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    agb_food_df = build_agribalyse_dairy_table(raw_dir)
    agb_farm_df = build_agribalyse_farm_gate_table(raw_dir)
    pdo_df = build_pdo_cheese_harmonized_table(raw_dir)
    uslci_df = build_uslci_curated_table(raw_dir)
    pkg_factors_df = build_unified_packaging_impact_factors(
        raw_dir, reference_dir, uslci_df=uslci_df
    )

    outputs: dict[str, Path] = {}
    for name, df in [
        ("agribalyse_dairy_products", agb_food_df),
        ("agribalyse_farm_gate_dairy", agb_farm_df),
        ("pdo_cheese_harmonized", pdo_df),
        ("uslci_curated_factors", uslci_df),
        ("packaging_impact_factors", pkg_factors_df),
    ]:
        csv_path = processed_dir / f"{name}.csv"
        pq_path = processed_dir / f"{name}.parquet"
        df.to_csv(csv_path, index=False)
        df.to_parquet(pq_path, index=False)
        outputs[name] = csv_path

    return outputs


if __name__ == "__main__":
    paths = run_phase1_harmonization()
    for table_name, out_path in paths.items():
        df_loaded = pd.read_csv(out_path)
        print(f"[Phase 1] {table_name}: {len(df_loaded)} rows -> {out_path}")
