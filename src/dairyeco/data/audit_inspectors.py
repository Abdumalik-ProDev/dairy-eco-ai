"""Read-only source inspectors for AGRIBALYSE 3.2, French PDO Cheese LCA, and USLCI.

Used by Phase 0 audit reports and automated tests to verify schemas, row counts,
entity join keys, functional units, packaging inclusion, and suitability flags
without mutating ``data/raw/``.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl

from dairyeco.config import RAW_DIR

PDO_SPELLING_MAP = {
    "Camenbert de Normandie": "Camembert de Normandie",
}


def normalize_pdo_cheese_name(raw_name: str) -> str:
    """Strip whitespace and normalize known spelling variants across PDO cheese tables."""
    cleaned = " ".join(raw_name.strip().split())
    return PDO_SPELLING_MAP.get(cleaned, cleaned)


@dataclass(frozen=True)
class AgribalyseFoodAudit:
    total_synthese_rows: int
    unique_agb_codes: int
    duplicate_agb_codes: list[int | str]
    detail_etape_valid_rows: int
    detail_etape_trailing_formula_rows: int
    detail_ingredient_valid_rows: int
    detail_ingredient_unique_codes: int
    indicators: list[tuple[str, str]]
    stages: list[str]
    dairy_group_subgroups: dict[tuple[str, str], int]
    core_dairy_row_count: int
    core_dairy_packaging_approaches: dict[str, int]
    core_dairy_delivery_modes: dict[str, int]


def inspect_agribalyse_food(raw_dir: Path = RAW_DIR) -> AgribalyseFoodAudit:
    """Inspect the main AGRIBALYSE 3.2 food product workbook."""
    wb_path = (
        raw_dir
        / "agribalyse_3_2"
        / "AGRIBALYSE3.2_Tableur produits alimentaires_PublieAOUT25.xlsx"
    )
    wb = openpyxl.load_workbook(wb_path, read_only=True, data_only=True)

    ws_syn = wb["Synthese"]
    syn_rows = list(ws_syn.iter_rows(values_only=True))
    ind_names = syn_rows[1][12:32]
    ind_units = syn_rows[2][12:32]
    indicators = [
        (str(n).strip(), str(u).strip())
        for n, u in zip(ind_names, ind_units, strict=True)
        if n is not None and u is not None
    ]

    data_syn = [r for r in syn_rows[3:] if r[0] is not None]
    code_counts = Counter(r[0] for r in data_syn)
    dups = sorted(k for k, v in code_counts.items() if v > 1)

    core_dairy_subgroups = {
        "crèmes et spécialités à base de crème",
        "fromages",
        "laits",
        "produits laitiers frais et assimilés",
        "beurres",
        "glaces",
        "desserts glacés",
    }
    subgroup_counter: Counter[tuple[str, str]] = Counter()
    core_dairy_rows = []
    for r in data_syn:
        grp = str(r[2] or "")
        subgrp = str(r[3] or "")
        if grp == "lait et produits laitiers" or subgrp in core_dairy_subgroups:
            subgroup_counter[(grp, subgrp)] += 1
            core_dairy_rows.append(r)

    pkg_counts = Counter(str(r[9] or "") for r in core_dairy_rows)
    deliv_counts = Counter(str(r[8] or "") for r in core_dairy_rows)

    ws_et = wb["Detail etape"]
    et_rows = list(ws_et.iter_rows(values_only=True))
    stages = [str(c).strip() for c in et_rows[3][8:15] if c is not None]
    valid_et = sum(1 for r in et_rows[4:] if r[0] is not None)
    trailing_et = sum(1 for r in et_rows[4:] if r[0] is None and any(r))

    ws_ing = wb["Detail ingredient"]
    ing_rows = list(ws_ing.iter_rows(values_only=True))
    valid_ing = [r for r in ing_rows[3:] if r[0] is not None]
    unique_ing_codes = len({r[0] for r in valid_ing})

    wb.close()
    return AgribalyseFoodAudit(
        total_synthese_rows=len(data_syn),
        unique_agb_codes=len(code_counts),
        duplicate_agb_codes=dups,
        detail_etape_valid_rows=valid_et,
        detail_etape_trailing_formula_rows=trailing_et,
        detail_ingredient_valid_rows=len(valid_ing),
        detail_ingredient_unique_codes=unique_ing_codes,
        indicators=indicators,
        stages=stages,
        dairy_group_subgroups=dict(sorted(subgroup_counter.items())),
        core_dairy_row_count=len(core_dairy_rows),
        core_dairy_packaging_approaches=dict(pkg_counts),
        core_dairy_delivery_modes=dict(deliv_counts),
    )


def inspect_agribalyse_agriculture(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    """Inspect the conventional and organic agricultural workbooks in AGRIBALYSE 3.2."""
    agb_dir = raw_dir / "agribalyse_3_2"
    result: dict[str, Any] = {}
    for key, fname, sname in [
        (
            "conventional",
            "AGRIBALYSE3.2_partie agriculture_conv_PublieNOV25.xlsx",
            "AGB 3.2 agricole conventionnel",
        ),
        (
            "organic",
            "AGRIBALYSE3.2_Tableur agriculture_bio_PublieNov24.xlsx",
            "AGB 3.2 agricole biologique",
        ),
    ]:
        wb = openpyxl.load_workbook(agb_dir / fname, read_only=True, data_only=True)
        ws = wb[sname]
        rows = [r for r in list(ws.iter_rows(values_only=True))[3:] if r[0] is not None]
        dairy_rows = [
            {
                "name_fr": r[0],
                "lci_name": r[1],
                "production_type": r[2],
                "category": r[3],
                "single_score_mpt_per_kg": r[4],
                "climate_change_kg_co2eq_per_kg": r[5],
            }
            for r in rows
            if "Dairy" in str(r[3] or "")
        ]
        wb.close()
        result[key] = {
            "total_rows": len(rows),
            "dairy_category_count": len(dairy_rows),
            "dairy_records": dairy_rows,
        }
    return result


@dataclass(frozen=True)
class PdoCheeseAudit:
    canonical_cheese_count: int
    canonical_cheese_names: list[str]
    table_cheese_counts: dict[str, int]
    raw_name_mismatches: list[dict[str, Any]]
    lci_initial_rows: int
    lci_additional_rows: int
    lcia_total_indicator_rows: int
    lcia_indicators_per_cheese: int
    lcia_indicator_names: list[tuple[str, str]]
    functional_unit: str
    ripening_wood_unit_initial: str
    ripening_wood_unit_additional: str


def inspect_pdo_cheese(raw_dir: Path = RAW_DIR) -> PdoCheeseAudit:
    """Inspect all 8 workbooks in data/raw/pdo_cheese_lca/."""
    pdo_dir = raw_dir / "pdo_cheese_lca"

    def _rows(fname: str) -> list[tuple[Any, ...]]:
        with (pdo_dir / fname).open("rb") as handle:
            wb = openpyxl.load_workbook(handle, read_only=True, data_only=True)
            ws = wb[wb.sheetnames[0]]
            data = list(ws.iter_rows(values_only=True))
            wb.close()
            return data

    char_rows = _rows("dataset_PDOcheeses_characterization.xlsx")
    alloc_rows = _rows("dataset_PDOcheeses_allocations.xlsx")
    coprod_rows = _rows("dataset_PDOcheeses_coproducts.xlsx")
    dist_rows = _rows("data_PDOcheeses_distances.xlsx")
    spec_rows = _rows("data_PDOcheeses_specifications.xlsx")
    lci_rows = _rows("data_PDOcheeses_LCI")
    lcia_rows = _rows("data_PDOcheeses_LCIA.xlsx")

    raw_lists = {
        "characterization": [str(r[1]) for r in char_rows[2:] if r[1]],
        "allocations": [str(r[1]) for r in alloc_rows[4:] if r[1]],
        "coproducts": [str(r[1]) for r in coprod_rows[4:] if r[1]],
        "distances": [str(r[1]) for r in dist_rows[3:] if r[1]],
        "specifications": [str(r[2]) for r in spec_rows[2:] if len(r) > 2 and r[2]],
        "lci_initial": [str(r[1]) for r in lci_rows[4:48] if r[1]],
        "lci_additional": [str(r[1]) for r in lci_rows[55:99] if r[1]],
        "lcia": [str(r[0]) for r in lcia_rows[3:] if r[0]],
    }

    table_counts = {k: len(v) for k, v in raw_lists.items()}
    canonical_sets = {
        k: [normalize_pdo_cheese_name(n) for n in v] for k, v in raw_lists.items()
    }
    first_canonical = canonical_sets["allocations"]
    for k, norm_list in canonical_sets.items():
        if norm_list != first_canonical:
            raise ValueError(f"Canonical cheese order mismatch in {k}")

    mismatches: list[dict[str, Any]] = []
    for idx, canon_name in enumerate(first_canonical):
        raw_by_table = {k: raw_lists[k][idx] for k in raw_lists}
        distinct_raw = sorted(set(raw_by_table.values()))
        distinct_stripped = sorted({n.strip() for n in distinct_raw})
        if len(distinct_raw) > 1 or any(n != canon_name for n in distinct_raw):
            mismatches.append(
                {
                    "index": idx,
                    "canonical_name": canon_name,
                    "distinct_stripped": distinct_stripped,
                    "distinct_raw": distinct_raw,
                }
            )

    lcia_non_empty = [r for r in lcia_rows[3:] if r[1] is not None]
    first_cheese_indicators = [
        (str(r[1]).strip(), str(r[2]).strip()) for r in lcia_rows[3:31] if r[1] is not None
    ]

    return PdoCheeseAudit(
        canonical_cheese_count=len(first_canonical),
        canonical_cheese_names=first_canonical,
        table_cheese_counts=table_counts,
        raw_name_mismatches=mismatches,
        lci_initial_rows=len(raw_lists["lci_initial"]),
        lci_additional_rows=len(raw_lists["lci_additional"]),
        lcia_total_indicator_rows=len(lcia_non_empty),
        lcia_indicators_per_cheese=len(first_cheese_indicators),
        lcia_indicator_names=first_cheese_indicators,
        functional_unit=str(lci_rows[0][1]).strip(),
        ripening_wood_unit_initial=str(lci_rows[3][15]).strip(),
        ripening_wood_unit_additional=str(lci_rows[54][16]).strip(),
    )


@dataclass(frozen=True)
class UslciAudit:
    schema_version: int
    total_processes: int
    unit_process_count: int
    lci_result_count: int
    bridge_process_count: int
    lcia_method_count: int
    total_product_flow_inputs: int
    unprovided_product_flow_inputs: int
    curated_packaging_energy_processes: list[dict[str, Any]]


def inspect_uslci(raw_dir: Path = RAW_DIR) -> UslciAudit:
    """Inspect the USLCI openLCA JSON-LD export and catalogue key processes."""
    uslci_dir = raw_dir / "uslci"
    meta = json.loads((uslci_dir / "openlca.json").read_text(encoding="utf-8"))
    lcia_dir = uslci_dir / "lcia_methods"
    lcia_count = len(list(lcia_dir.glob("*.json"))) if lcia_dir.exists() else 0

    proc_files = sorted((uslci_dir / "processes").glob("*.json"))
    output_flows: set[str] = set()
    parsed_procs: list[dict[str, Any]] = []

    for p in proc_files:
        d = json.loads(p.read_text(encoding="utf-8"))
        parsed_procs.append(d)
        for ex in d.get("exchanges", []):
            if not ex.get("isInput") and ((ex.get("flow") or {}).get("flowType")) == "PRODUCT_FLOW":
                fid = (ex.get("flow") or {}).get("@id")
                if fid:
                    output_flows.add(fid)

    unit_cnt = 0
    lci_res_cnt = 0
    bridge_cnt = 0
    total_prod_in = 0
    unprovided_prod_in = 0

    for d in parsed_procs:
        ptype = d.get("processType")
        if ptype == "UNIT_PROCESS":
            unit_cnt += 1
        elif ptype == "LCI_RESULT":
            lci_res_cnt += 1
        cat = d.get("category") or ""
        if "Bridge" in cat:
            bridge_cnt += 1
        for ex in d.get("exchanges", []):
            if ex.get("isInput") and ((ex.get("flow") or {}).get("flowType")) == "PRODUCT_FLOW":
                total_prod_in += 1
                fid = (ex.get("flow") or {}).get("@id")
                if fid not in output_flows:
                    unprovided_prod_in += 1

    # Curate key packaging/energy/transport/EoL processes by UUID prefix
    target_prefixes = {
        # Virgin polymers
        "2712f03a": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "6a12cba1": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "1dbafde2": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "2b2f738d": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "2e8facf6": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "13821cca": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "d1c572b0": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "cf1241fd": ("virgin_polymer", "unit_conversion_required_1000kg_qref"),
        "3dbccdda": ("virgin_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "e281027f": ("bio_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        # Recycled polymers
        "17664c37": ("recycled_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "b15aa6b2": ("recycled_polymer", "chain_process_0_direct_elementary_flows"),
        "f7b7280d": ("recycled_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        "22ebc7fb": ("recycled_polymer", "chain_process_0_direct_elementary_flows"),
        "185648c2": ("recycled_polymer", "suitable_unit_process_needs_electricity_and_lcia"),
        # Plastic conversion
        "89a2b59a": ("plastic_conversion", "suitable_unit_process_needs_electricity_and_lcia"),
        "9fe670f2": ("plastic_conversion", "suitable_unit_process_needs_electricity_and_lcia"),
        "18c37a18": ("plastic_conversion", "suitable_unit_process_needs_electricity_and_lcia"),
        "26f39b7c": ("plastic_conversion", "chain_process_0_direct_elementary_flows"),
        "e2f66950": ("plastic_conversion", "chain_process_0_direct_elementary_flows"),
        # Paperboard & paper
        "c245a252": ("paperboard", "unit_conversion_required_1_10516kg_qref"),
        "12ba204b": ("paperboard_recycled", "unit_conversion_required_1_10516kg_qref"),
        "226ed3c2": ("corrugated_board", "suitable_unit_process_needs_electricity_and_lcia"),
        "9c10be0f": ("corrugated_board_recycled", "suitable_unit_process_needs_electricity_and_lcia"),
        "f9cf891e": ("kraft_paper_bag", "unit_conversion_required_834_61kg_qref"),
        # Glass (showing gap / unsuitable processes)
        "06d602eb": ("glass", "unsuitable_bridge_stub_to_useeio_0_elementary_flows"),
        "1bea9d6a": ("eol_landfill", "unit_conversion_required_1_short_ton_qref"),
        # Aluminium
        "99963138": ("aluminium_primary", "suitable_lci_result_cradle_to_gate_1kg"),
        "21aeedbf": ("aluminium_primary", "legacy_1997_unit_process"),
        "bcc68f88": ("aluminium_secondary", "unit_conversion_required_1000kg_qref"),
        "9cc8fafa": ("aluminium_secondary_can", "legacy_1997_unit_process"),
        "2b196386": ("aluminium_rolling", "unit_conversion_required_1000kg_qref"),
        "6edc2da1": ("aluminium_rolling", "unit_conversion_required_1000kg_qref"),
        "96543dd3": ("aluminium_can_conversion", "unit_conversion_required_13_5kg_qref"),
        # Electricity (showing bridge stub limitation)
        "44a867b1": ("electricity", "unsuitable_bridge_stub_to_us_electricity_baseline"),
        "bd38f6f8": ("electricity", "unsuitable_bridge_stub_to_us_electricity_baseline"),
        "ab7f18b8": ("electricity", "unsuitable_routes_to_bridge_stubs_0_elementary_flows"),
        # Fuel & thermal energy
        "f347daea": ("fuel_boiler", "market_mix_links_to_3_boiler_size_processes"),
        "4d7e8233": ("fuel_boiler", "suitable_unit_process_with_direct_emissions"),
        "53804132": ("fuel_boiler", "market_mix_links_to_3_boiler_size_processes"),
        "0924e625": ("fuel_boiler", "suitable_unit_process_with_direct_emissions"),
        "9d9b6815": ("fuel_boiler", "suitable_unit_process_with_direct_emissions"),
        "4eec7a31": ("fuel_boiler", "suitable_unit_process_with_direct_emissions"),
        # Transport
        "34156f3c": ("transport_truck", "suitable_unit_process_with_direct_emissions"),
        "45b70b50": ("transport_truck", "suitable_unit_process_with_direct_emissions"),
        "bf6e7378": ("transport_truck", "suitable_unit_process_with_direct_emissions"),
        "7de9c230": ("transport_rail", "suitable_unit_process_with_direct_emissions"),
        # End-of-life
        "a3c523bb": ("eol_mrf_sorting", "multi_output_1Mg_qref_0_direct_elementary_flows"),
        "4c476cdb": ("eol_mrf_sorting", "multi_output_1Mg_qref_0_direct_elementary_flows"),
        "00a9571c": ("eol_combustion", "unit_conversion_required_1_short_ton_qref"),
        "30a3f9c8": ("eol_combustion", "unit_conversion_required_1_short_ton_qref"),
        "e847ff05": ("eol_combustion", "chain_process_1_short_ton_qref_0_direct_elementary_flows"),
        "9da15ed3": ("eol_combustion", "unit_conversion_required_1_short_ton_qref"),
        "abe35439": ("eol_landfill", "unit_conversion_required_1_short_ton_qref"),
        "67119c4c": ("eol_landfill", "unit_conversion_required_1_short_ton_qref"),
        "8a63f602": ("eol_landfill", "unit_conversion_required_1_short_ton_qref"),
    }

    curated: list[dict[str, Any]] = []
    for d in parsed_procs:
        pid = d.get("@id") or ""
        prefix = pid[:8]
        if prefix not in target_prefixes:
            continue
        domain_role, suitability = target_prefixes[prefix]
        exchanges = d.get("exchanges", [])
        qref = next(
            (
                e
                for e in exchanges
                if e.get("isQuantitativeReference") or e.get("quantitativeReference")
            ),
            {},
        )
        elem_cnt = sum(
            1 for e in exchanges if ((e.get("flow") or {}).get("flowType")) == "ELEMENTARY_FLOW"
        )
        tech_cnt = len(exchanges) - elem_cnt
        doc = d.get("processDocumentation") or {}
        curated.append(
            {
                "uuid": pid,
                "domain_role": domain_role,
                "name": d.get("name"),
                "category": d.get("category"),
                "process_type": d.get("processType"),
                "location": (d.get("location") or {}).get("name") or "unspecified",
                "valid_from": (doc.get("validFrom") or "")[:10],
                "valid_until": (doc.get("validUntil") or "")[:10],
                "qref_flow": ((qref.get("flow") or {}).get("name")),
                "qref_amount": qref.get("amount"),
                "qref_unit": ((qref.get("unit") or {}).get("name")),
                "tech_exchanges": tech_cnt,
                "elementary_exchanges": elem_cnt,
                "suitability_status": suitability,
            }
        )

    return UslciAudit(
        schema_version=int(meta["schemaVersion"]),
        total_processes=len(parsed_procs),
        unit_process_count=unit_cnt,
        lci_result_count=lci_res_cnt,
        bridge_process_count=bridge_cnt,
        lcia_method_count=lcia_count,
        total_product_flow_inputs=total_prod_in,
        unprovided_product_flow_inputs=unprovided_prod_in,
        curated_packaging_energy_processes=curated,
    )
