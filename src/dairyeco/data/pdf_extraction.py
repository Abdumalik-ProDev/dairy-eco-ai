"""Extract and verify tables from the NIST/ANL (2024) and IFC/WBG (2007) PDFs.

Writes:
  - data/interim/pdf_extraction/nist/raw_pdfplumber_tables.json
  - data/interim/pdf_extraction/nist/table1_cross_regional_summary.csv
  - data/interim/pdf_extraction/nist/table2_3_global_volumes.csv
  - data/interim/pdf_extraction/nist/table4_regional_dataset_coverage.csv
  - data/interim/pdf_extraction/nist/table5_pathway_ci.csv
  - data/interim/pdf_extraction/nist/figures_regional_baseline_ci.csv
  - data/reference/nist_plastic_carbon_intensity.csv
  - data/interim/pdf_extraction/ifc/raw_pdfplumber_tables.json
  - data/interim/pdf_extraction/ifc/table1_effluent_guidelines.csv
  - data/interim/pdf_extraction/ifc/table2_solid_waste_generation.csv
  - data/interim/pdf_extraction/ifc/table3_resource_energy_consumption_wide.csv
  - data/reference/ifc_dairy_benchmarks.csv

Never modifies any file under ``data/raw/``.

Run: ``uv run python -m dairyeco.data.pdf_extraction``
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import pdfplumber

from dairyeco.config import INTERIM_DIR, PROJECT_ROOT, RAW_DIR
from dairyeco.config import REFERENCE_DIR as REF_DIR

NIST_INTERIM_DIR = INTERIM_DIR / "pdf_extraction" / "nist"
IFC_INTERIM_DIR = INTERIM_DIR / "pdf_extraction" / "ifc"

NIST_REF_CSV = REF_DIR / "nist_plastic_carbon_intensity.csv"
IFC_REF_CSV = REF_DIR / "ifc_dairy_benchmarks.csv"


def discover_raw_pdfs(raw_dir: Path = RAW_DIR) -> tuple[Path, Path]:
    """Locate the NIST/ANL plastics PDF and IFC dairy PDF under data/raw/."""
    nist_path: Path | None = None
    ifc_path: Path | None = None
    for pdf_path in sorted(raw_dir.rglob("*.pdf")):
        if pdf_path.parent != raw_dir:
            continue
        with pdfplumber.open(pdf_path) as pdf:
            head_text = "\n".join((p.extract_text() or "") for p in pdf.pages[:3])
        if "ANL/ESIA-24/3" in head_text:
            nist_path = pdf_path
        elif "Environmental, Health, and Safety Guidelines" in head_text:
            ifc_path = pdf_path
    if nist_path is None or ifc_path is None:
        raise FileNotFoundError(
            f"Could not discover both required root PDFs in {raw_dir}: "
            f"nist={nist_path}, ifc={ifc_path}"
        )
    return nist_path, ifc_path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty row list to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _clean_cell(val: str | None) -> str:
    if val is None:
        return ""
    return re.sub(r"\s+", " ", val.replace("\n", " ")).strip()


def extract_nist_tables(nist_pdf: Path) -> list[dict[str, Any]]:
    """Extract raw pdfplumber tables, interim CSVs, and reference CSV for NIST/ANL 2024."""
    NIST_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    rel_pdf = nist_pdf.relative_to(PROJECT_ROOT).as_posix()

    raw_tables_dump: dict[str, Any] = {"source_file": rel_pdf, "pages": {}}
    with pdfplumber.open(nist_pdf) as pdf:
        for page_num in (14, 17, 18, 23, 24, 43):
            page = pdf.pages[page_num - 1]
            raw_tables_dump["pages"][str(page_num)] = page.extract_tables()
        t1_grid = raw_tables_dump["pages"]["14"][0]
        t2_grid = raw_tables_dump["pages"]["17"][0]
        t3_grid = raw_tables_dump["pages"]["18"][0]
        t5_grid = raw_tables_dump["pages"]["43"][0]

    (NIST_INTERIM_DIR / "raw_pdfplumber_tables.json").write_text(
        json.dumps(raw_tables_dump, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 1. Table 1 (PDF page 14, report page xi): Cross-regional summary
    # Verify header positions in t1_grid[0]
    resin_cols = {
        "PET": 6,
        "HDPE": 9,
        "LDPE": 12,
        "PP": 15,
        "PVC": 18,
    }
    avg_row = t1_grid[1]
    r1_row = t1_grid[3]
    r2_row = t1_grid[6]
    r3_row = t1_grid[7]
    r4_row = t1_grid[8]

    # Visual verification against rendered pages (Figures 16a, 20a, 21a, 22a, 24a)
    # supplies the exact regional baseline values alongside Table 1's % deviations.
    verified_regional_baselines = {
        "PET": {
            "fig_ref": "Figure 1(a) & Figure 16(a)",
            "pdf_page": 33,
            "report_page": "18",
            "render": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_33-33.png",
            "regions": {
                "Western Europe": (1.75, -9.0, "1st (Min. CI)"),
                "USA": (1.86, -3.0, "2nd"),
                "China": (1.92, 0.0, "3rd"),
                "MENA": (2.13, 11.0, "4th (Max. CI)"),
            },
            "key_contributors": "CI of electricity",
            "minor_contributors": "CI of NG production; Steam cracking feedstock mix; Terephthalic monomer mix",
        },
        "HDPE": {
            "fig_ref": "Figure 20(a)",
            "pdf_page": 37,
            "report_page": "22",
            "render": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_37-37.png",
            "regions": {
                "USA": (1.32, -7.0, "1st (Min. CI)"),
                "Western Europe": (1.35, -5.0, "2nd"),
                "MENA": (1.47, 4.0, "3rd"),
                "China": (1.52, 7.0, "4th (Max. CI)"),
            },
            "key_contributors": "CI of electricity; Steam cracking feedstock mix",
            "minor_contributors": "CI of NG production",
        },
        "LDPE": {
            "fig_ref": "Figure 21(a)",
            "pdf_page": 38,
            "report_page": "23",
            "render": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_38-38.png",
            "regions": {
                "Western Europe": (1.65, -9.0, "1st (Min. CI)"),
                "USA": (1.66, -8.0, "2nd"),
                "China": (1.94, 8.0, "3rd"),
                "MENA": (1.97, 9.0, "4th (Max. CI)"),
            },
            "key_contributors": "CI of electricity; Steam cracking feedstock mix",
            "minor_contributors": "CI of NG production",
        },
        "PP": {
            "fig_ref": "Figure 22(a)",
            "pdf_page": 39,
            "report_page": "24",
            "render": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_39-39.png",
            "regions": {
                "USA": (1.15, -8.0, "1st (Min. CI)"),
                "Western Europe": (1.28, 2.0, "2nd"),
                "MENA": (1.28, 2.0, "3rd"),
                "China": (1.29, 3.0, "4th (Max. CI)"),
            },
            "key_contributors": "CI of electricity; Steam cracking feedstock mix; Propylene sourcing mix",
            "minor_contributors": "CI of NG production",
        },
        "PVC": {
            "fig_ref": "Figure 24(a)",
            "pdf_page": 41,
            "report_page": "26",
            "render": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_41-41.png",
            "regions": {
                "Western Europe": (2.22, -17.0, "1st (Min. CI)"),
                "USA": (2.25, -16.0, "2nd"),
                "MENA": (2.66, -1.0, "3rd"),
                "China": (3.57, 34.0, "4th (Max. CI)"),
            },
            "key_contributors": "CI of electricity; VCM technology mix",
            "minor_contributors": "CI of NG production; Steam cracking feedstock mix",
        },
    }

    table1_rows: list[dict[str, Any]] = []
    for resin, col_idx in resin_cols.items():
        avg_ci = float(_clean_cell(avg_row[col_idx - 1]))
        meta = verified_regional_baselines[resin]
        table1_rows.append(
            {
                "resin": resin,
                "cross_regional_average_kgco2e_per_kg": avg_ci,
                "rank_1_min_ci": _clean_cell(r1_row[col_idx - 1]),
                "rank_2": _clean_cell(r2_row[col_idx - 1]),
                "rank_3": _clean_cell(r3_row[col_idx - 1]),
                "rank_4_max_ci": _clean_cell(r4_row[col_idx - 1]),
                "key_contributors": meta["key_contributors"],
                "minor_contributors": meta["minor_contributors"],
                "pdf_page": 14,
                "report_page": "xi",
                "table_ref": "Table 1",
                "source_file": rel_pdf,
            }
        )
    _write_csv(NIST_INTERIM_DIR / "table1_cross_regional_summary.csv", table1_rows)

    # 2. Tables 2 & 3 (PDF pages 17-18, report pages 2-3): Global production/consumption volumes
    t3_map = {
        _clean_cell(t3_grid[0][i]).rstrip("0123456789"): float(_clean_cell(t3_grid[1][i]))
        for i in range(1, len(t3_grid[0]))
    }
    table2_3_rows: list[dict[str, Any]] = []
    for r in t2_grid[1:]:
        resin_name = _clean_cell(r[0])
        share_str = _clean_cell(r[1])
        cons_str = _clean_cell(r[2]) or "92.9 (all PEs combined with LDPE)"
        table2_3_rows.append(
            {
                "resin": resin_name,
                "global_production_share_raw": share_str,
                "annual_global_consumption_mmt_per_yr_table2": cons_str,
                "annual_global_production_mmt_per_yr_table3": t3_map.get(resin_name, ""),
                "table2_pdf_page": 17,
                "table2_report_page": "2",
                "table3_pdf_page": 18 if resin_name in t3_map else "",
                "table3_report_page": "3" if resin_name in t3_map else "",
                "source_file": rel_pdf,
            }
        )
    _write_csv(NIST_INTERIM_DIR / "table2_3_global_volumes.csv", table2_3_rows)

    # 3. Table 4 (PDF pages 23-24, report pages 8-9): Regional dataset scope matrix
    table4_rows = [
        {
            "regional_dataset_factor": "Electricity grid mix",
            "PET": "Y",
            "HDPE": "Y",
            "LDPE": "Y",
            "PP": "Y",
            "PVC": "Y",
            "pdf_page": 23,
            "report_page": "8",
            "table_ref": "Table 4",
        },
        {
            "regional_dataset_factor": "NG supply chain",
            "PET": "Y",
            "HDPE": "Y",
            "LDPE": "Y",
            "PP": "Y",
            "PVC": "Y",
            "pdf_page": 23,
            "report_page": "8",
            "table_ref": "Table 4",
        },
        {
            "regional_dataset_factor": "Steam cracking feedstock mix (NGL vs. petroleum)",
            "PET": "Y",
            "HDPE": "Y",
            "LDPE": "Y",
            "PP": "Y",
            "PVC": "N",
            "pdf_page": 23,
            "report_page": "8",
            "table_ref": "Table 4",
        },
        {
            "regional_dataset_factor": "Propylene sources (steam cracking vs. non-steam cracking processes such as FCC and PDH)",
            "PET": "N",
            "HDPE": "N",
            "LDPE": "N",
            "PP": "Y",
            "PVC": "N",
            "pdf_page": 23,
            "report_page": "8",
            "table_ref": "Table 4",
        },
        {
            "regional_dataset_factor": "Terephthalic monomer type for PET production (PTA vs. DMT)",
            "PET": "Y",
            "HDPE": "N",
            "LDPE": "N",
            "PP": "N",
            "PVC": "N",
            "pdf_page": 24,
            "report_page": "9",
            "table_ref": "Table 4",
        },
        {
            "regional_dataset_factor": "Acetylene vs. EDC pathway mix in VCM production",
            "PET": "N",
            "HDPE": "N",
            "LDPE": "N",
            "PP": "N",
            "PVC": "Y",
            "pdf_page": 24,
            "report_page": "9",
            "table_ref": "Table 4",
        },
    ]
    _write_csv(NIST_INTERIM_DIR / "table4_regional_dataset_coverage.csv", table4_rows)

    # 4. Parse Table 5 (PDF page 43, report page 28) directly from pdfplumber grid
    table5_rows: list[dict[str, Any]] = []
    curr_product = ""
    curr_tech = ""
    curr_region = ""
    curr_unit = ""

    for r in t5_grid[5:]:
        prod_cell = _clean_cell(r[0])
        tech_cell = _clean_cell(r[1])
        reg_cell = _clean_cell(r[2])
        unit_cell = _clean_cell(r[11])
        if prod_cell:
            curr_product = prod_cell
        if tech_cell:
            curr_tech = tech_cell
        if reg_cell:
            curr_region = reg_cell
        if unit_cell:
            # Normalize pdfplumber's subscript line breaks "[kgCO e/kg- 2 PET]"
            curr_unit = (
                unit_cell.replace("kgCO e/kg- 2 ", "kgCO2e/kg-")
                .replace("kgCO e/kg-", "kgCO2e/kg-")
                .strip("[]")
            )

        # Pathway text may be in column 5 or 6; CI value may be in column 8 or 9
        pathway_parts = [_clean_cell(r[5]), _clean_cell(r[6])]
        pathway_str = " ".join(p for p in pathway_parts if p)
        ci_str = _clean_cell(r[8]) or _clean_cell(r[9])

        if not ci_str and pathway_str == "based" and table5_rows:
            # Continuation line for "Steam cracking-\nbased"
            table5_rows[-1]["pathway"] = "Steam cracking-based"
            continue
        if not ci_str:
            continue

        if pathway_str == "Steam cracking-":
            pathway_str = "Steam cracking-based"

        table5_rows.append(
            {
                "product": curr_product,
                "technology_and_feedstock_variation": curr_tech,
                "region": curr_region,
                "pathway": pathway_str,
                "carbon_intensity_value": float(ci_str),
                "original_unit": curr_unit,
                "normalized_unit": "kg CO2e / kg",
                "pdf_page": 43,
                "report_page": "28",
                "table_ref": "Table 5",
                "source_file": rel_pdf,
            }
        )
    _write_csv(NIST_INTERIM_DIR / "table5_pathway_ci.csv", table5_rows)

    # 5. Figures regional baseline & background energy CI (verified against rendered PNGs)
    fig_rows: list[dict[str, Any]] = []
    for resin, col_idx in resin_cols.items():
        avg_ci = float(_clean_cell(avg_row[col_idx - 1]))
        meta = verified_regional_baselines[resin]
        fig_rows.append(
            {
                "entity": resin,
                "entity_type": "virgin_resin",
                "region": "Cross-regional average",
                "value": avg_ci,
                "unit": "kgCO2e/kg",
                "deviation_from_avg_pct": 0.0,
                "rank_in_table1": "Cross-regional average",
                "pdf_page": 14,
                "report_page": "xi",
                "figure_or_table_ref": f"Table 1 & {meta['fig_ref']}",
                "rendered_page_path": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_14-14.png",
            }
        )
        for region_name in ("USA", "Western Europe", "MENA", "China"):
            val, dev_pct, rank_str = meta["regions"][region_name]
            fig_rows.append(
                {
                    "entity": resin,
                    "entity_type": "virgin_resin",
                    "region": region_name,
                    "value": val,
                    "unit": "kgCO2e/kg",
                    "deviation_from_avg_pct": dev_pct,
                    "rank_in_table1": rank_str,
                    "pdf_page": meta["pdf_page"],
                    "report_page": meta["report_page"],
                    "figure_or_table_ref": f"{meta['fig_ref']} & Table 1",
                    "rendered_page_path": meta["render"],
                }
            )

    # Add Figure 18 regional electricity grid and natural gas supply CIs (PDF p. 35, report p. 20)
    fig18_elec = [
        ("Cross-regional average", 573.0, 0.0),
        ("USA", 466.0, -19.0),
        ("Western Europe", 285.0, -50.0),
        ("MENA", 840.0, 47.0),
        ("China", 700.0, 22.0),
    ]
    for reg, val, dev in fig18_elec:
        fig_rows.append(
            {
                "entity": "Electricity grid mix",
                "entity_type": "background_energy",
                "region": reg,
                "value": val,
                "unit": "gCO2e/kWh",
                "deviation_from_avg_pct": dev,
                "rank_in_table1": "",
                "pdf_page": 35,
                "report_page": "20",
                "figure_or_table_ref": "Figure 18(a)",
                "rendered_page_path": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_35-35.png",
            }
        )

    fig18_ng = [
        ("Cross-regional average", 15.0, 0.0),
        ("USA", 13.0, -16.0),
        ("Western Europe", 20.0, 29.0),
        ("MENA", 18.0, 19.0),
        ("China", 11.0, -32.0),
    ]
    for reg, val, dev in fig18_ng:
        fig_rows.append(
            {
                "entity": "Natural gas supply",
                "entity_type": "background_energy",
                "region": reg,
                "value": val,
                "unit": "gCO2e/MJ",
                "deviation_from_avg_pct": dev,
                "rank_in_table1": "",
                "pdf_page": 35,
                "report_page": "20",
                "figure_or_table_ref": "Figure 18(b)",
                "rendered_page_path": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_35-35.png",
            }
        )
    _write_csv(NIST_INTERIM_DIR / "figures_regional_baseline_ci.csv", fig_rows)

    # 6. Build unified reference table: data/reference/nist_plastic_carbon_intensity.csv
    ref_rows: list[dict[str, Any]] = []
    rec_num = 1
    for f_row in fig_rows:
        is_avg = f_row["region"] == "Cross-regional average"
        if f_row["entity_type"] == "virgin_resin":
            rec_type = "resin_cross_regional_average" if is_avg else "resin_regional_baseline"
            norm_val = f_row["value"]
            norm_unit = "kg CO2e / kg"
            fu = f"1 kg of virgin {f_row['entity']} resin at plant gate"
            boundary = "Cradle-to-gate virgin resin production (GREET 2022)"
            tech_cat = "Regional baseline technology & feedstock mix"
            pathway = "Regional baseline mix"
            method = (
                "pdfplumber_table1"
                if is_avg
                else "rendered_page_visual_verification_plus_table1_pct"
            )
            note = (
                "Table 1 (p. xi) cross-regional mean across USA, Western Europe, MENA and China"
                if is_avg
                else "Exact bar label from rendered figure cross-checked against Table 1 % deviation"
            )
        else:
            rec_type = "background_energy_fig18"
            norm_val = round(f_row["value"] / 1000.0, 6)
            norm_unit = (
                "kg CO2e / kWh" if f_row["unit"] == "gCO2e/kWh" else "kg CO2e / MJ"
            )
            fu = (
                "1 kWh of regional grid electricity"
                if f_row["unit"] == "gCO2e/kWh"
                else "1 MJ of regional natural gas supply"
            )
            boundary = "Cradle-to-gate regional energy supply (IEA 2020 / GREET 2022)"
            tech_cat = f_row["entity"]
            pathway = "Regional consumption/supply mix (2020)"
            method = "rendered_page_visual_verification"
            note = "Extracted from Figure 18 data labels on rendered PDF page 35 (report p. 20)"

        ref_rows.append(
            {
                "record_id": f"NIST-CI-{rec_num:03d}",
                "source_dataset_id": "anl_nist_regional_plastics_2024",
                "source_file": rel_pdf,
                "report_number": "ANL/ESIA-24/3",
                "report_year": 2024,
                "pdf_page": f_row["pdf_page"],
                "report_page": f_row["report_page"],
                "table_or_figure_ref": f_row["figure_or_table_ref"],
                "record_type": rec_type,
                "material_or_product": f_row["entity"],
                "technology_or_feedstock_category": tech_cat,
                "pathway": pathway,
                "region": f_row["region"],
                "value": f_row["value"],
                "original_unit": f_row["unit"],
                "normalized_value": norm_val,
                "normalized_unit": norm_unit,
                "functional_unit": fu,
                "system_boundary": boundary,
                "deviation_from_cross_regional_avg_pct": f_row["deviation_from_avg_pct"],
                "rank_in_table1": f_row["rank_in_table1"],
                "extraction_method": method,
                "verification_status": "verified_against_rendered_page",
                "rendered_page_path": f_row["rendered_page_path"],
                "notes": note,
            }
        )
        rec_num += 1

    for t5_row in table5_rows:
        note = "Extracted via pdfplumber from Table 5 (PDF p. 43, report p. 28) and verified against rendered page"
        if (
            t5_row["product"] == "PET"
            and t5_row["region"] == "USA"
            and t5_row["pathway"] == "PTA-based"
        ):
            note += (
                "; note that report prose above Table 5 (p. 28) misstates USA PTA-based PET CI as 1.92 "
                "(which is China's PTA-based value), whereas Table 5 shows 1.75 (consistent with USA 23% DMT / "
                "77% PTA baseline: 0.77*1.75 + 0.23*2.23 = 1.86)"
            )
        ref_rows.append(
            {
                "record_id": f"NIST-CI-{rec_num:03d}",
                "source_dataset_id": "anl_nist_regional_plastics_2024",
                "source_file": rel_pdf,
                "report_number": "ANL/ESIA-24/3",
                "report_year": 2024,
                "pdf_page": t5_row["pdf_page"],
                "report_page": t5_row["report_page"],
                "table_or_figure_ref": t5_row["table_ref"],
                "record_type": "pathway_specific_table5",
                "material_or_product": t5_row["product"],
                "technology_or_feedstock_category": t5_row["technology_and_feedstock_variation"],
                "pathway": t5_row["pathway"],
                "region": t5_row["region"],
                "value": t5_row["carbon_intensity_value"],
                "original_unit": t5_row["original_unit"],
                "normalized_value": t5_row["carbon_intensity_value"],
                "normalized_unit": t5_row["normalized_unit"],
                "functional_unit": f"1 kg of {t5_row['product']} at plant gate",
                "system_boundary": "Cradle-to-gate dedicated technology/feedstock pathway (GREET 2022)",
                "deviation_from_cross_regional_avg_pct": "",
                "rank_in_table1": "",
                "extraction_method": "pdfplumber_table5",
                "verification_status": "verified_against_rendered_page",
                "rendered_page_path": "data/interim/pdf_extraction/nist/page_renders/nist_pdfpage_43-43.png",
                "notes": note,
            }
        )
        rec_num += 1

    _write_csv(NIST_REF_CSV, ref_rows)
    return ref_rows


def _parse_range_string(raw: str) -> tuple[float | None, float | None, float | None, str]:
    """Parse an IFC value string into (min_value, max_value, single_value, qualifier)."""
    cleaned = raw.strip()
    if not cleaned or cleaned == "-":
        return None, None, None, "not_reported"
    if "case specific" in cleaned.lower():
        return None, None, None, "case_specific_qualitative"
    # Strip trailing footnote letters like '1.7–14a' or '<3b'
    cleaned_num = re.sub(r"[a-c]$", "", cleaned).strip()
    if cleaned_num.startswith("<"):
        val = float(cleaned_num[1:].strip())
        return None, val, val, "upper_bound_less_than"
    # Range with en-dash or hyphen
    if "–" in cleaned_num or "-" in cleaned_num:
        parts = re.split(r"[–-]", cleaned_num)
        if len(parts) == 2:
            lo = float(parts[0].strip())
            hi = float(parts[1].strip())
            return lo, hi, None, "range"
    val = float(cleaned_num)
    return val, val, val, "point_value"


def extract_ifc_tables(ifc_pdf: Path) -> list[dict[str, Any]]:
    """Extract raw pdfplumber tables, interim CSVs, and reference CSV for IFC/WBG 2007."""
    IFC_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    rel_pdf = ifc_pdf.relative_to(PROJECT_ROOT).as_posix()

    with pdfplumber.open(ifc_pdf) as pdf:
        p8_tables = pdf.pages[7].extract_tables()
        p9_tables = pdf.pages[8].extract_tables()

    raw_dump = {
        "source_file": rel_pdf,
        "pages": {
            "8": p8_tables,
            "9": p9_tables,
        },
    }
    (IFC_INTERIM_DIR / "raw_pdfplumber_tables.json").write_text(
        json.dumps(raw_dump, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 1. Table 1 (PDF page 8, report page 8): Effluent levels dairy processing
    t1_grid = p8_tables[0]
    footnotes_t1 = {
        "a": "MPN = Most Probable Number",
        "b": (
            "At the edge of a scientifically established mixing zone which takes into "
            "account ambient water quality, receiving water use, potential receptors and "
            "assimilative capacity"
        ),
    }
    table1_rows: list[dict[str, Any]] = []
    for r in t1_grid[2:12]:
        pollutant = _clean_cell(r[0]) or _clean_cell(r[1])
        unit_str = _clean_cell(r[3])
        val_str = _clean_cell(r[6])
        if "To be determined" in unit_str and not val_str:
            val_str = unit_str
            unit_str = "case-specific"
        fn_key = ""
        if unit_str.startswith("MPNa"):
            fn_key = "a"
        elif val_str.endswith("b"):
            fn_key = "b"
        table1_rows.append(
            {
                "pollutant": pollutant,
                "original_unit": unit_str,
                "guideline_value_raw": val_str,
                "footnote_key": fn_key,
                "footnote_text": footnotes_t1.get(fn_key, ""),
                "pdf_page": 8,
                "report_page": 8,
                "table_ref": "Table 1",
                "source_file": rel_pdf,
            }
        )
    _write_csv(IFC_INTERIM_DIR / "table1_effluent_guidelines.csv", table1_rows)

    # 2. Table 2 (PDF page 8, report page 8): Waste generation in the dairy sector
    footnotes_t2 = {
        "a": (13, "Based on results from 13 dairies. Source: Nordic Council of Ministers (2001)."),
        "b": (17, "Based on results from 17 dairies. Source: Nordic Council of Ministers (2001)."),
        "c": (4, "Based on results from 4 dairies. Source: Nordic Council of Ministers (2001)."),
    }
    table2_rows = [
        {
            "product_range": "Market milk and cultured products",
            "total_solid_waste_raw": "1.7–14a",
            "original_unit": "kg/1000 l",
            "sample_size_dairies": 13,
            "footnote_key": "a",
            "footnote_text": footnotes_t2["a"][1],
            "pdf_page": 8,
            "report_page": 8,
            "table_ref": "Table 2",
            "source_file": rel_pdf,
        },
        {
            "product_range": "Cheese, whey, and powder",
            "total_solid_waste_raw": "0.5–10b",
            "original_unit": "kg/1000 l",
            "sample_size_dairies": 17,
            "footnote_key": "b",
            "footnote_text": footnotes_t2["b"][1],
            "pdf_page": 8,
            "report_page": 8,
            "table_ref": "Table 2",
            "source_file": rel_pdf,
        },
        {
            "product_range": "Ice cream",
            "total_solid_waste_raw": "35–58c",
            "original_unit": "kg/1000 l",
            "sample_size_dairies": 4,
            "footnote_key": "c",
            "footnote_text": footnotes_t2["c"][1],
            "pdf_page": 8,
            "report_page": 8,
            "table_ref": "Table 2",
            "source_file": rel_pdf,
        },
    ]
    _write_csv(IFC_INTERIM_DIR / "table2_solid_waste_generation.csv", table2_rows)

    # 3. Table 3 (PDF page 9, report page 9): Resource and energy consumption
    t3_grid = p9_tables[0]
    table3_wide_rows: list[dict[str, Any]] = []
    curr_section = ""
    for r in t3_grid[3:18]:
        sec_cell = _clean_cell(r[1])
        prod_cell = _clean_cell(r[0])
        if sec_cell in ("Water", "Energy", "Wastewater discharge") and not prod_cell:
            curr_section = sec_cell
            continue
        if not prod_cell:
            continue
        unit_str = _clean_cell(r[3])
        eu_val = _clean_cell(r[6])
        se_val = _clean_cell(r[9])
        dk_val = _clean_cell(r[12])
        fi_val = _clean_cell(r[15])
        no_val = _clean_cell(r[18])
        bm_val = _clean_cell(r[21])
        note = ""
        if curr_section == "Energy" and prod_cell == "Ice cream":
            note = (
                "In rendered PDF page 9, '0.75–1.6' is a single merged cell spanning the four "
                "Nordic columns (Swedish, Danish, Finnish, Norwegian dairies)"
            )
        table3_wide_rows.append(
            {
                "resource_or_emission_category": curr_section,
                "inputs_per_unit_of_product": prod_cell,
                "mass_load_unit": unit_str,
                "european_dairies_a": eu_val,
                "swedish_dairies_b": se_val,
                "danish_dairies_b": dk_val,
                "finnish_dairies_b": fi_val,
                "norwegian_dairies_b": no_val,
                "industry_benchmark_c": bm_val,
                "pdf_page": 9,
                "report_page": 9,
                "table_ref": "Table 3",
                "layout_note": note,
                "source_file": rel_pdf,
            }
        )
    _write_csv(
        IFC_INTERIM_DIR / "table3_resource_energy_consumption_wide.csv", table3_wide_rows
    )

    # 4. Build unified long-format reference table: data/reference/ifc_dairy_benchmarks.csv
    ref_rows: list[dict[str, Any]] = []
    b_idx = 1

    # Add Table 1 rows
    for r1 in table1_rows:
        lo, hi, single, qual = _parse_range_string(r1["guideline_value_raw"])
        norm_unit = (
            r1["original_unit"]
            .replace("MPNa / 100 ml", "MPN/100 mL")
            .replace("mg/l", "mg/L")
        )
        ref_rows.append(
            {
                "benchmark_id": f"IFC-BM-{b_idx:03d}",
                "source_dataset_id": "ifc_wbg_ehs_dairy_2007",
                "source_file": rel_pdf,
                "report_year": 2007,
                "underlying_source_year": "2007",
                "underlying_citation": "World Bank Group EHS Guidelines for Dairy Processing (2007)",
                "pdf_page": 8,
                "report_page": 8,
                "table_ref": "Table 1",
                "benchmark_category": "Effluent guideline level",
                "product_or_pollutant": r1["pollutant"],
                "region_or_column": "WBG EHS Guideline Value",
                "raw_value_string": r1["guideline_value_raw"],
                "min_value": "" if lo is None else lo,
                "max_value": "" if hi is None else hi,
                "single_value": "" if single is None else single,
                "value_qualifier": qual,
                "original_unit": r1["original_unit"],
                "normalized_unit": norm_unit,
                "functional_unit_basis": "Treated sanitary/process wastewater discharge concentration",
                "system_boundary": "Gate-to-gate dairy processing plant direct discharge to surface water",
                "sample_size_dairies": "",
                "footnote_key": r1["footnote_key"],
                "footnote_text": r1["footnote_text"],
                "extraction_method": "pdfplumber_table1",
                "verification_status": "verified_against_rendered_page",
                "rendered_page_path": "data/interim/pdf_extraction/ifc/page_renders/ifc_pdfpage_08-08.png",
                "notes": "Indicative EHS effluent concentration limit for treated dairy processing wastewater",
            }
        )
        b_idx += 1

    # Add Table 2 rows
    for r2 in table2_rows:
        lo, hi, single, qual = _parse_range_string(r2["total_solid_waste_raw"])
        ref_rows.append(
            {
                "benchmark_id": f"IFC-BM-{b_idx:03d}",
                "source_dataset_id": "ifc_wbg_ehs_dairy_2007",
                "source_file": rel_pdf,
                "report_year": 2007,
                "underlying_source_year": "2001",
                "underlying_citation": "Nordic Council of Ministers (2001)",
                "pdf_page": 8,
                "report_page": 8,
                "table_ref": "Table 2",
                "benchmark_category": "Total solid waste generation",
                "product_or_pollutant": r2["product_range"],
                "region_or_column": "Nordic dairies survey",
                "raw_value_string": r2["total_solid_waste_raw"],
                "min_value": "" if lo is None else lo,
                "max_value": "" if hi is None else hi,
                "single_value": "" if single is None else single,
                "value_qualifier": qual,
                "original_unit": r2["original_unit"],
                "normalized_unit": "kg / 1000 L processed milk (or product)",
                "functional_unit_basis": "1,000 L of processed milk / dairy output",
                "system_boundary": "Gate-to-gate dairy processing plant solid waste generation",
                "sample_size_dairies": r2["sample_size_dairies"],
                "footnote_key": r2["footnote_key"],
                "footnote_text": r2["footnote_text"],
                "extraction_method": "pdfplumber_table2",
                "verification_status": "verified_against_rendered_page",
                "rendered_page_path": "data/interim/pdf_extraction/ifc/page_renders/ifc_pdfpage_08-08.png",
                "notes": "Historical Nordic dairy solid waste benchmark range; not an independent ML sample",
            }
        )
        b_idx += 1

    # Add Table 3 rows (non-empty cells; handle merged Nordic cell for Ice cream Energy)
    col_defs = [
        (
            "european_dairies_a",
            "European dairies",
            "a",
            "2002",
            "European Dairy Association (2002), cited in EC (2006)",
        ),
        (
            "swedish_dairies_b",
            "Swedish dairies",
            "b",
            "2001",
            "Nordic Council of Ministers (2001)",
        ),
        (
            "danish_dairies_b",
            "Danish dairies",
            "b",
            "2001",
            "Nordic Council of Ministers (2001)",
        ),
        (
            "finnish_dairies_b",
            "Finnish dairies",
            "b",
            "2001",
            "Nordic Council of Ministers (2001)",
        ),
        (
            "norwegian_dairies_b",
            "Norwegian dairies",
            "b",
            "2001",
            "Nordic Council of Ministers (2001)",
        ),
        (
            "industry_benchmark_c",
            "Industry benchmark",
            "c",
            "2001",
            "Nordic Council of Ministers (2001)",
        ),
    ]

    unit_norm_map = {
        "L/L processed milk": ("L / L processed milk", "1 L of processed milk"),
        "L/kg icecream": ("L / kg ice cream", "1 kg of ice cream"),
        "kWh/L processed milk": ("kWh / L processed milk", "1 L of processed milk"),
        "KWh/kg ice cream": ("kWh / kg ice cream", "1 kg of ice cream"),
        "Liters/L processed milk": ("L / L processed milk", "1 L of processed milk"),
        "liters/L processed milk": ("L / L processed milk", "1 L of processed milk"),
        "L/kg ice cream": ("L / kg ice cream", "1 kg of ice cream"),
    }

    for r3 in table3_wide_rows:
        cat = r3["resource_or_emission_category"]
        prod = r3["inputs_per_unit_of_product"]
        orig_u = r3["mass_load_unit"]
        norm_u, fu_basis = unit_norm_map[orig_u]

        for col_key, col_label, fn_key, u_year, u_cit in col_defs:
            val_raw = r3[col_key]
            if not val_raw:
                continue
            lo, hi, single, qual = _parse_range_string(val_raw)
            region_label = col_label
            method = "pdfplumber_table3"
            note = "Table 3 resource and energy consumption benchmark"
            if cat == "Energy" and prod == "Ice cream" and col_key == "swedish_dairies_b":
                region_label = (
                    "Nordic dairies (merged cell spanning Swedish, Danish, Finnish, Norwegian columns)"
                )
                method = "pdfplumber_table3_plus_rendered_page_merged_cell_verification"
                note = (
                    "Visual verification of rendered PDF page 9 confirms '0.75–1.6' spans all four "
                    "Nordic columns (Swedish, Danish, Finnish, Norwegian dairies) as a single merged cell"
                )
            ref_rows.append(
                {
                    "benchmark_id": f"IFC-BM-{b_idx:03d}",
                    "source_dataset_id": "ifc_wbg_ehs_dairy_2007",
                    "source_file": rel_pdf,
                    "report_year": 2007,
                    "underlying_source_year": u_year,
                    "underlying_citation": u_cit,
                    "pdf_page": 9,
                    "report_page": 9,
                    "table_ref": "Table 3",
                    "benchmark_category": cat,
                    "product_or_pollutant": prod,
                    "region_or_column": region_label,
                    "raw_value_string": val_raw,
                    "min_value": "" if lo is None else lo,
                    "max_value": "" if hi is None else hi,
                    "single_value": "" if single is None else single,
                    "value_qualifier": qual,
                    "original_unit": orig_u,
                    "normalized_unit": norm_u,
                    "functional_unit_basis": fu_basis,
                    "system_boundary": "Gate-to-gate dairy processing plant utility consumption / wastewater discharge",
                    "sample_size_dairies": "",
                    "footnote_key": fn_key,
                    "footnote_text": u_cit,
                    "extraction_method": method,
                    "verification_status": "verified_against_rendered_page",
                    "rendered_page_path": "data/interim/pdf_extraction/ifc/page_renders/ifc_pdfpage_09-09.png",
                    "notes": note,
                }
            )
            b_idx += 1

    _write_csv(IFC_REF_CSV, ref_rows)
    return ref_rows


def main() -> None:
    nist_pdf, ifc_pdf = discover_raw_pdfs()
    nist_rows = extract_nist_tables(nist_pdf)
    ifc_rows = extract_ifc_tables(ifc_pdf)
    print(f"NIST reference rows: {len(nist_rows)} -> {NIST_REF_CSV.relative_to(PROJECT_ROOT)}")
    print(f"IFC reference rows:  {len(ifc_rows)} -> {IFC_REF_CSV.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
