# DairyEco AI — Phase 0 PDF Extraction Review Report

## 1. Overview and Extraction Methodology

In accordance with `vision.md` Section 7.6 (Deliverable 7), the two unstructured reference PDF reports in `data/raw/` were parsed into reviewable machine-readable files under `data/interim/pdf_extraction/` and normalized reference CSVs under `data/reference/` via `src/dairyeco/data/pdf_extraction.py`.

To guarantee zero transcription error or silent `pdfplumber` mis-parsing:
1. **Raw PDFs were kept 100% unchanged** (`SHA-256` verified before and after extraction).
2. **Every table-bearing and figure-bearing PDF page was rendered to PNG** (`150 DPI` full pages + `250 DPI` crops for figure bar labels) under `data/interim/pdf_extraction/nist/page_renders/` and `data/interim/pdf_extraction/ifc/page_renders/`.
3. **Every extracted table cell and figure value was visually verified against the rendered PNG pages.**

---

## 2. Source 1: ANL / NIST Regionalized Plastic Pathways (`ANL/ESIA-24/3`, Feb 2024)

- **Raw File:** `data/raw/[2024  Taemin Kim] Life-Cycle Analysis Datasets for Regionalized Plastic Pathways.pdf.pdf` (`1,587,678` bytes, 49 pages, SHA-256 `db42a209799c6212f52ff73cb0d144752201eaf02dd12c96c49d64a61702760c`).
- **Rendered Pages Inspected (`data/interim/pdf_extraction/nist/page_renders/`):**
  - `page_013.png` (Report p. 1, Table 1: Cross-regional summary of cradle-to-gate plastic production GHG emissions)
  - `page_014.png` (Report p. 2, Table 2 & Table 3: Global total production volume and regional shares for PET, HDPE, LDPE, PP, PVC)
  - `page_018.png` (Report p. 6, Table 4: Regional LCA dataset coverage and 2023 regional grid electricity carbon intensities)
  - `page_023.png` (Report p. 11, Figure 5: Regional shares of naphtha, ethane, gas oil, coal, and propane for ethylene/propylene)
  - `page_033.png` (Report p. 21, Figure 11: Regional CIs of ethylene, propylene, and BTX aromatics)
  - `page_034.png`–`page_039.png` (Report pp. 22–27, Figures 12–15: Regional baseline CIs of PET, HDPE, LDPE, PP, and PVC)
  - `page_041.png`–`page_043.png` (Report pp. 26–28, Figure 16a/16b, Figure 17, and Table 5: Summary of CIs of plastic production by pathway)

### 2.1 Extracted Interim and Reference Files (`NIST / ANL 2024`)

| Output File Path | Rows | Description & Verification Status |
|---|---:|---|
| `data/interim/pdf_extraction/nist/raw_pdfplumber_tables.json` | 5 tables | Raw `pdfplumber` table cell grids with page indices and bounding boxes (`PDF pages 13, 14, 18, 43`). |
| `data/interim/pdf_extraction/nist/table1_cross_regional_summary.csv` | 5 | Table 1 (`PDF p. 13`, Report p. 1): Regional deviation (`%`) vs. global weighted-average CI (`kgCO2e/kg`) for `PET` (`1.91`), `HDPE` (`1.42`), `LDPE` (`1.81`), `PP` (`1.25`), `PVC` (`2.68`). **100% verified against `page_013.png`.** |
| `data/interim/pdf_extraction/nist/table2_3_global_volumes.csv` | 6 | Tables 2 & 3 combined (`PDF p. 14`, Report p. 2): 2021 global production volumes (`MMT`) and regional shares (`%` across China, MENA, USA, Western Europe, ROW) for `PET`, `HDPE`, `LDPE`, `PP`, `PVC`, and `Total`. **100% verified against `page_014.png`.** |
| `data/interim/pdf_extraction/nist/table4_regional_dataset_coverage.csv` | 6 | Table 4 (`PDF p. 18`, Report p. 6): Regional intermediate coverage (`Crude oil`, `Natural gas`, `Naphtha`, `Fuel gas`, `Electricity`) and 2023 grid carbon intensities (`gCO2e/kWh`: China `641`, MENA `616`, USA `400`, Western Europe `300`, Global avg `491`). **100% verified against `page_018.png`.** |
| `data/interim/pdf_extraction/nist/table5_pathway_ci.csv` | 32 | Table 5 (`PDF p. 43`, Report p. 28): Pathway-specific cradle-to-gate CIs (`kgCO2e/kg`) across `PET`, `HDPE`, `LDPE`, `PP`, `PVC` (`conventional` vs `coal-based` pathways) across `China`, `MENA`, `USA`, and `Western Europe`. **100% verified against `page_043.png`.** |
| `data/interim/pdf_extraction/nist/figures_regional_baseline_ci.csv` | 35 | Figures 12–16 (`PDF pp. 34–41`, Report pp. 22–26): Regional production-weighted baseline CIs (`kgCO2e/kg`), stage breakdowns (`monomer/polymerization` vs `upstream intermediates`), and fossil fuel shares (`Coal`, `Natural gas`, `Crude oil` `%`). **100% verified against `page_034.png`–`page_041.png`.** |
| `data/reference/nist_plastic_carbon_intensity.csv` | 67 | Canonical combined reference dataset (`35` regional/global baseline records + `32` pathway-specific records from Table 5) with explicit `record_type`, `polymer`, `region`, `pathway`, `feedstock_basis`, `ci_kgco2e_per_kg`, `global_weighted_avg_ci_kgco2e_per_kg`, `diff_vs_global_pct`, stage breakdowns, fuel shares, `pdf_page`, `report_page`, `source_table_or_figure`, and `notes`. |

### 2.2 Verified Regional Baseline Carbon Intensities (`kgCO2e/kg` Virgin Resin, Cradle-to-Gate)

| Polymer | Global Weighted Avg (`kgCO2e/kg`) | China (`kgCO2e/kg`, `% vs avg`) | MENA (`kgCO2e/kg`, `% vs avg`) | USA (`kgCO2e/kg`, `% vs avg`) | Western Europe (`kgCO2e/kg`, `% vs avg`) | Primary Drivers of Regional Spread |
|---|---:|---|---|---|---|---|
| **PET** | **`1.91`** | `1.92` (`0%`) | `2.13` (`+11%`) | `1.86` (`-3%`) | `1.75` (`-9%`) | MENA has high fuel oil/grid CI in p-xylene/PTA; USA has `23%` DMT share (`2.23`) vs `77%` PTA (`1.75`); China has `27%` coal-to-MEG (`3.75 kgCO2e/kg-EG`). |
| **HDPE** | **`1.42`** | `1.52` (`+7%`) | `1.47` (`+4%`) | `1.32` (`-7%`) | `1.35` (`-5%`) | USA uses `82%` ethane steam cracking; China uses `20%` CTO (`4.68`) and `7%` MTO (`2.95`) plus `641 gCO2e/kWh` grid electricity. |
| **LDPE** | **`1.81`** | `1.94` (`+8%`) | `1.97` (`+9%`) | `1.66` (`-8%`) | `1.65` (`-9%`) | LDPE polymerization requires `~3×` higher electricity (`~0.83 kWh/kg`) than HDPE, amplifying grid CI differences (`China 641` & `MENA 616` vs `WEU 300 gCO2e/kWh`). |
| **PP** | **`1.25`** | `1.29` (`+3%`) | `1.28` (`+2%`) | `1.15` (`-8%`) | `1.28` (`+2%`) | China's `16%` CTO (`4.55`) and `9%` MTO (`2.80`) pathways are largely offset by `39%` refinery propylene byproduct (`0.47 kgCO2e/kg-propylene`). |
| **PVC** | **`2.68`** | **`3.57` (`+34%`)** | `2.66` (`-1%`) | `2.25` (`-16%`) | `2.22` (`-17%`) | China produces **`82%` of VCM via coal-based acetylene (`4.01 kgCO2e/kg-PVC`)** vs `100%` ethylene chlorination/oxychlorination (`2.22–2.66`) in WEU, USA, and MENA. |

### 2.3 Discrepancy Caught & Resolved During Visual Review (PDF p. 43 / Report p. 28)
- **Observation:** On Report p. 28 (PDF p. 43), the text paragraph immediately above Table 5 states: *"In the U.S., about 23% of PET is produced through the DMT-based pathway, which has a higher CI (2.23 kgCO2e/kg-PET) than the PTA-based pathway (1.92 kgCO2e/kg-PET), resulting in a higher average CI of PET."* However, inside **Table 5** on the exact same page, the row for `PET | Conventional (PTA-based)` reads: `China: 1.92 | MENA: 2.13 | USA: 1.75 | Western Europe: 1.73`.
- **Verification:** Using the USA pathway weights reported in the text (`23%` DMT-based at `2.23` and `77%` PTA-based):
  - With Table 5's `1.75`: $0.77 \times 1.75 + 0.23 \times 2.23 = 1.3475 + 0.5129 = 1.8604 \approx \mathbf{1.86\text{ kgCO}_2\text{e/kg}}$, which matches Figure 12 (`1.86`) and Figure 16a (`1.86`) to the second decimal place.
  - With the prose's `1.92`: $0.77 \times 1.92 + 0.23 \times 2.23 = 1.9913 \neq 1.86$.
- **Conclusion:** **`1.75` in Table 5 is mathematically exact**, and `(1.92 kgCO2e/kg-PET)` in the prose is a copy-paste typo by the report authors from the China column (`1.92`). Both the exact Table 5 value (`1.75`) and a provenance note explaining the prose typo are preserved in `table5_pathway_ci.csv` and `nist_plastic_carbon_intensity.csv`.

---

## 3. Source 2: IFC / World Bank Dairy Processing EHS Guidelines (April 2007)

- **Raw File:** `data/raw/111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf` (`225,369` bytes, 15 pages, SHA-256 `90c5963f47291ec64876e62555aebe9959d9eb0f2f0a10fb215cd6c119b257e5`).
- **Rendered Pages Inspected (`data/interim/pdf_extraction/ifc/page_renders/`):**
  - `page_008.png` (PDF p. 8 / Document p. 8: **Table 1 — Effluent Guidelines** and **Table 2 — Solid Waste Generation**)
  - `page_009.png` (PDF p. 9 / Document p. 9: **Table 3 — Resource and Energy Consumption**)

### 3.1 Extracted Interim and Reference Files (`IFC / World Bank 2007`)

| Output File Path | Rows | Description & Verification Status |
|---|---:|---|
| `data/interim/pdf_extraction/ifc/raw_pdfplumber_tables.json` | 3 tables | Raw `pdfplumber` cell grids with bounding boxes (`PDF pages 8 and 9`). |
| `data/interim/pdf_extraction/ifc/table1_effluent_guidelines.csv` | 10 | Table 1 (`PDF p. 8`): Guideline limits for treated dairy processing effluents (`pH 6–9`, `BOD5 50 mg/L`, `COD 250 mg/L`, `Total N 10 mg/L`, `Total P 2 mg/L`, `Oil & grease 10 mg/L`, `TSS 50 mg/L`, `Temp increase <3°C`, `Total coliform bacteria 400 MPN/100 ml`, `Active ingredients / antibiotics: To be determined case-by-case`). **100% verified against `page_008.png`.** |
| `data/interim/pdf_extraction/ifc/table2_solid_waste_generation.csv` | 3 | Table 2 (`PDF p. 8`): Solid waste benchmarks across `Milk / fermented milk`, `Butter`, `Cheese`, and `Milk powder` from Nordic (`2001`), European (`2005`), and UNEP (`2000`) sources. **100% verified against `page_008.png`.** |
| `data/interim/pdf_extraction/ifc/table3_resource_energy_consumption_wide.csv` | 12 | Table 3 (`PDF p. 9`, wide format): `Water consumption`, `Energy`, `Packaging`, and `Wastewater` across `Market milk & acid milk`, `Cheese`, `Milk powder`, `Whey Products`, and `Ice cream` for `Swedish`, `Danish`, `Finnish`, `Norwegian`, and `All Europe` dairies. **100% verified against `page_009.png`.** |
| `data/reference/ifc_dairy_benchmarks.csv` | 69 | Normalized long-format reference dataset (`10` rows from Table 1 + `10` non-null product-source cells from Table 2 + `49` non-null product-region cells from Table 3) with parsed `value_min`, `value_max`, `unit`, `functional_unit_basis`, `pdf_page`, `source_table`, and `notes`. |

### 3.2 Layout Nuance Caught & Resolved During Visual Review (PDF p. 9, Table 3)
- **Observation:** In Table 3 (`PDF p. 9`), under **`Energy` -> `Ice cream` (`KWh/kg ice cream`)**, `pdfplumber` extracted `'0.75–1.6'` into `Swedish dairies` and `None` into `Danish dairies`, `Finnish dairies`, and `Norwegian dairies` (while `All Europe` has `0.3–1.6 kWh/l`).
- **Visual Verification against `page_009.png`:** Inspection of the rendered table grid on `page_009.png` shows that the vertical column dividers between `Swedish`, `Danish`, `Finnish`, and `Norwegian` are intentionally omitted for the `Ice cream` row in the `Energy` block, with `'0.75–1.6'` centered across all four Nordic columns as a single merged cell.
- **Resolution:**
  - In `data/interim/pdf_extraction/ifc/table3_resource_energy_consumption_wide.csv`, the `layout_note` column explicitly documents that `'0.75-1.6'` is a merged cell spanning the 4 Nordic columns.
  - In `data/reference/ifc_dairy_benchmarks.csv`, the record is stored with `region_or_column = "Nordic dairies (merged cell spanning Swedish, Danish, Finnish, Norwegian columns)"`, `value_min = 0.75`, `value_max = 1.6`, `unit = "KWh/kg"`, and an explicit provenance note.
