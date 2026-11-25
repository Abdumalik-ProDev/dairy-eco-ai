# DairyEco AI — Phase 0 Data Dictionary

> **Phase:** Phase 0 (Inventory, Source Identification, Extraction & Data Audit)  
> **Updated:** 2026-11-11  
> **Scope:** Schema definitions, primary/join keys, units, and provenance semantics for all Phase 0 metadata/reference tables and raw source datasets under `data/raw/`.

---

## 1. Provenance & Data-Origin Classification

Every dataset and derived record in DairyEco AI must carry an explicit data-origin classification (`data_type` / `provenance_type`):

| Classification | Definition | Allowed Use in DairyEco AI |
|---|---|---|
| `measured` | Direct operational, BOM, utility, or financial measurements from a verified dairy plant or supplier invoice/quotation. | Primary plant calibration, baseline vs. alternative evaluation, and (when sample size permits) company operational ML. |
| `published-reference` | Peer-reviewed or official public LCA/benchmark values (AGRIBALYSE 3.2, PDO Cheese LCA, USLCI, ANL/NIST 2024, IFC/WBG 2007). | Deterministic LCA factors, process benchmarks, sanity-check bounds, and exploratory case studies. **Not independent company ML samples.** |
| `proxy` | A `published-reference` factor from a non-local geography or adjacent material/process applied where local data do not exist (e.g., MENA or Western Europe resin CI for Uzbekistan; AGRIBALYSE `PACK PROXY`). | Scenario estimation with explicit proxy warning and sensitivity analysis. |
| `assumed` | Transparent engineering or economic parameter set by the user/analyst (e.g., transport distance, reuse trip count, breakage rate, discount rate, assumed unit price). | Scenario calculation engine and sensitivity/tornado analysis; never labelled as observed company savings. |
| `synthetic` / `LCA-model-derived` | Outputs generated deterministically by running the DairyEco AI LCA/economic calculation engine over a grid of scenario inputs. | Surrogate model approximation tests only (`test score = simulator fidelity`, not real-world predictive accuracy). |

---

## 2. Phase 0 Generated Metadata & Reference Schemas

### 2.1 `data/metadata/raw_file_inventory.csv` (8,096 rows)

Generated deterministically by `uv run python -m dairyeco.data.inventory`.

| Column | Type | Unit / Format | Description |
|---|---|---|---|
| `relative_path` | `string` | POSIX path | Path relative to repository root (`data/raw/...`). Primary key. |
| `file_name` | `string` | Filename | Basename of the file on disk (preserves spaces, accents, missing/double extensions). |
| `extension` | `string` | Lowercase ext | File suffix without leading dot (`xlsx`, `pdf`, `json`, `txt`, `png`, `jpg`, or `""` for extensionless files such as `data_PDOcheeses_LCI`). |
| `media_type` | `string` | IANA MIME | Detected MIME type (`mimetypes` + magic-byte ZIP/OOXML/PDF inspection). |
| `size_bytes` | `int64` | `bytes` | Exact file size on disk. |
| `sha256` | `string` | 64-char hex | SHA-256 digest of raw file bytes. |
| `likely_source` | `string` | Enum ID | Canonical source dataset ID (`agribalyse_3_2`, `pdo_cheese_lca`, `uslci`, `anl_nist_regional_plastics_2024`, `ifc_wbg_ehs_dairy_2007`). |
| `source_component` | `string` | Category | Subdirectory or role (`root`, `download_manifest`, `report_pdf`, `processes`, `flows`, `sources`, `locations`, `actors`, `unit_groups`, `flow_properties`, `currencies`, `dq_systems`, `parameters`, `bin`). |
| `identification_confidence` | `string` | `high`/`medium`/`low` | Confidence in source identity based on internal file metadata. |
| `identification_basis` | `string` | Text | Summary of internal evidence confirming the source assignment. |

### 2.2 `data/metadata/dataset_manifest.csv` (5 rows)

Generated deterministically by `uv run python -m dairyeco.data.inventory`.

| Column | Type | Description |
|---|---|---|
| `dataset_id` | `string` | Primary key (`agribalyse_3_2`, `pdo_cheese_lca`, `uslci`, `anl_nist_regional_plastics_2024`, `ifc_wbg_ehs_dairy_2007`). |
| `title` | `string` | Full title of the dataset or report as verified from internal contents. |
| `provider` | `string` | Publishing institution(s) and authoring organization(s). |
| `version` | `string` | Dataset version and publication/modification date found in internal metadata. |
| `url` | `string` | Official source URL or repository note if not embedded inside raw files. |
| `download_date` | `string` | ISO date (`YYYY-MM-DD`) of local file acquisition. |
| `licence` | `string` | Licence terms stated in internal metadata (or explicit note if missing). |
| `geography` | `string` | Geographic coverage (`FR`, `US`/`RNA`/`GLO`, `USA`/`Western Europe`/`MENA`/`China`, Nordic/European). |
| `reference_year` | `string` | Reference year(s) of inventory/impact data and publication. |
| `functional_unit` | `string` | Exact functional unit(s) or reference flow(s) in the source. |
| `system_boundary` | `string` | System boundary (cradle-to-grave, cradle-to-farm-gate, cradle-to-cheese-gate, cradle-to-resin-gate, gate-to-gate). |
| `lcia_method` | `string` | LCIA characterization method or operational metric definition. |
| `file_path` | `string` | Relative path under `data/raw/`. |
| `file_count` | `int64` | Number of raw files belonging to this dataset. |
| `total_size_bytes` | `int64` | Sum of `size_bytes` across all files in the dataset. |
| `sha256_checksum` | `string` | File SHA-256 (for single-file PDFs) or deterministic aggregate SHA-256 over sorted `<sha256>  <relative_path>` lines. |
| `identification_confidence` | `string` | `high` or `medium`. |
| `data_type` | `string` | Provenance classification (`published-reference`). |
| `intended_use` | `string` | Role of the dataset in DairyEco AI. |
| `limitations` | `string` | Key methodological, geographic, schema, and completeness limitations. |

### 2.3 `data/reference/nist_plastic_carbon_intensity.csv` (67 rows)

Generated by `uv run python -m dairyeco.data.pdf_extraction` from `ANL/ESIA-24/3` (February 2024).

| Column | Type | Unit / Format | Description |
|---|---|---|---|
| `record_id` | `string` | `NIST-CI-001`..`067` | Primary key. |
| `source_dataset_id` | `string` | `anl_nist_regional_plastics_2024` | Foreign key to `dataset_manifest.csv`. |
| `source_file` | `string` | POSIX path | Exact path to raw PDF in `data/raw/`. |
| `report_number` | `string` | `ANL/ESIA-24/3` | Official Argonne/NIST report identifier. |
| `report_year` | `int` | `2024` | Publication year. |
| `pdf_page` | `int` | `14`, `33`, `35`, `37`..`43` | 1-based page index in the PDF file. |
| `report_page` | `string` | `xi`, `18`, `20`, `22`..`28` | Printed page number in the report. |
| `table_or_figure_ref` | `string` | Text | Exact table/figure reference (`Table 1`, `Table 5`, `Figure 16(a)`, `Figure 18(a)`, `Figure 20(a)`, etc.). |
| `record_type` | `string` | Enum | `resin_cross_regional_average` (5 rows), `resin_regional_baseline` (20 rows), `background_energy_fig18` (10 rows), `pathway_specific_table5` (32 rows). |
| `material_or_product` | `string` | Text | `PET`, `HDPE`, `LDPE`, `PP`, `PVC`, `Ethylene and propylene`, `Propylene`, `Electricity grid mix`, `Natural gas supply`. |
| `technology_or_feedstock_category` | `string` | Text | Technology/feedstock variation dimension (e.g., `Terephthalic monomer mix`, `Steam cracking feedstock mix`, `Propylene sourcing mix`, `VCM production technology mix`). |
| `pathway` | `string` | Text | Specific pathway (`Regional baseline mix`, `PTA-based`, `DMT-based`, `NGL-based`, `Petroleum-based`, `Steam cracking-based`, `Non-steam cracking based (e.g., FCC and PDH)`, `EDC-based`, `Acetylene-based`). |
| `region` | `string` | Enum | `USA`, `Western Europe`, `MENA`, `China`, or `Cross-regional average`. |
| `value` | `float` | `original_unit` | Numeric value exactly as reported in the PDF table or figure label. |
| `original_unit` | `string` | Text | Unit string from PDF (`kgCO2e/kg`, `kgCO2e/kg-PET`, `kgCO2e/kg-ethylene or propylene`, `kgCO2e/kg-propylene`, `kgCO2e/kg-PVC`, `gCO2e/kWh`, `gCO2e/MJ`). |
| `normalized_value` | `float` | `normalized_unit` | Value converted to kg CO2e per reference unit (`value` unchanged for resins/monomers; `value / 1000` for `gCO2e/kWh` and `gCO2e/MJ`). |
| `normalized_unit` | `string` | Text | `kg CO2e / kg`, `kg CO2e / kWh`, or `kg CO2e / MJ`. |
| `functional_unit` | `string` | Text | Functional unit definition (`1 kg of virgin <resin> resin at plant gate`, `1 kWh of regional grid electricity`, etc.). |
| `system_boundary` | `string` | Text | Cradle-to-gate boundary definition. |
| `deviation_from_cross_regional_avg_pct` | `float` or `""` | `%` | Percentage deviation from 4-region average reported in Table 1 / Figures 16b–24b. |
| `rank_in_table1` | `string` | Text | Rank order in Table 1 (`1st (Min. CI)`, `2nd`, `3rd`, `4th (Max. CI)`, `Cross-regional average`, or `""`). |
| `extraction_method` | `string` | Text | `pdfplumber_table1`, `pdfplumber_table5`, `rendered_page_visual_verification`, or `rendered_page_visual_verification_plus_table1_pct`. |
| `verification_status` | `string` | Text | `verified_against_rendered_page`. |
| `rendered_page_path` | `string` | POSIX path | Path to the rendered PNG page used for verification. |
| `notes` | `string` | Text | Provenance notes and cross-check documentation. |

### 2.4 `data/reference/ifc_dairy_benchmarks.csv` (69 rows)

Generated by `uv run python -m dairyeco.data.pdf_extraction` from the IFC/World Bank Group EHS Guidelines for Dairy Processing (April 30, 2007).

| Column | Type | Unit / Format | Description |
|---|---|---|---|
| `benchmark_id` | `string` | `IFC-BM-001`..`069` | Primary key. |
| `source_dataset_id` | `string` | `ifc_wbg_ehs_dairy_2007` | Foreign key to `dataset_manifest.csv`. |
| `source_file` | `string` | POSIX path | `data/raw/111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf`. |
| `report_year` | `int` | `2007` | Guideline publication year. |
| `underlying_source_year` | `string` | `2001`, `2002`, `2007` | Year of the underlying survey data cited in footnotes (`2001` Nordic Council of Ministers; `2002` European Dairy Association cited in EC 2006). |
| `underlying_citation` | `string` | Text | Exact source citation from table footnotes. |
| `pdf_page` | `int` | `8` or `9` | 1-based page number in the PDF. |
| `report_page` | `int` | `8` or `9` | Printed page number in the guideline. |
| `table_ref` | `string` | `Table 1`, `Table 2`, `Table 3` | Source table identifier. |
| `benchmark_category` | `string` | Enum | `Effluent guideline level` (10 rows), `Total solid waste generation` (3 rows), `Water` (17 rows), `Energy` (17 rows), `Wastewater discharge` (22 rows). |
| `product_or_pollutant` | `string` | Text | Dairy product group (`Market milk and cultured products`, `Cheese and whey`, `Milk powder, cheese, and (or) liquid products`, `Cheese, whey, and powder`, `Ice cream`) or effluent parameter (`pH`, `BOD5`, `COD`, `Total nitrogen`, `Total phosphorus`, `Oil and grease`, `Total suspended solids`, `Temperature increase`, `Total coliform bacteria`, `Active Ingredients / Antibiotics`). |
| `region_or_column` | `string` | Text | `WBG EHS Guideline Value`, `Nordic dairies survey`, `European dairies`, `Swedish dairies`, `Danish dairies`, `Finnish dairies`, `Norwegian dairies`, `Nordic dairies (merged cell spanning Swedish, Danish, Finnish, Norwegian columns)`, or `Industry benchmark`. |
| `raw_value_string` | `string` | Text | Exact string extracted from the PDF table cell (e.g., `0.96–2.8`, `1.7–14a`, `<3b`, `-`). |
| `min_value` | `float` or `""` | `original_unit` | Lower bound of range (or point value when single number; empty for upper-bound `<3b`, `-`, or qualitative). |
| `max_value` | `float` or `""` | `original_unit` | Upper bound of range (or `3.0` for `<3b`, or point value). |
| `single_value` | `float` or `""` | `original_unit` | Populated only when the cell is a single point value or upper bound, empty for intervals. |
| `value_qualifier` | `string` | Enum | `range`, `point_value`, `upper_bound_less_than`, `not_reported`, `case_specific_qualitative`. |
| `original_unit` | `string` | Text | Exact unit string in the PDF (`L/L processed milk`, `L/kg icecream`, `kWh/L processed milk`, `KWh/kg ice cream`, `Liters/L processed milk`, `liters/L processed milk`, `L/kg ice cream`, `kg/1000 l`, `mg/l`, `pH`, `°C`, `MPNa / 100 ml`, `case-specific`). |
| `normalized_unit` | `string` | Text | Standardized unit notation (`L / L processed milk`, `L / kg ice cream`, `kWh / L processed milk`, `kWh / kg ice cream`, `kg / 1000 L processed milk (or product)`, `mg/L`, `pH`, `°C`, `MPN/100 mL`). |
| `functional_unit_basis` | `string` | Text | Reference basis (`1 L of processed milk`, `1,000 L of processed milk / dairy output`, `1 kg of ice cream`, or `Treated sanitary/process wastewater discharge concentration`). |
| `system_boundary` | `string` | Text | Gate-to-gate dairy processing plant boundary. |
| `sample_size_dairies` | `int` or `""` | Count | Number of surveyed dairies where reported in footnotes (`13`, `17`, `4` in Table 2). |
| `footnote_key` | `string` | `a`, `b`, `c`, or `""` | Footnote marker attached to the cell or column. |
| `footnote_text` | `string` | Text | Full footnote text from the table footer. |
| `extraction_method` | `string` | Text | Extraction and verification method. |
| `verification_status` | `string` | Text | `verified_against_rendered_page`. |
| `rendered_page_path` | `string` | POSIX path | Path to rendered PNG page (`ifc_pdfpage_08-08.png` or `ifc_pdfpage_09-09.png`). |
| `notes` | `string` | Text | Layout and interpretation notes. |

---

## 3. Raw Source Dataset Schemas

### 3.1 AGRIBALYSE 3.2 (`data/raw/agribalyse_3_2/`)

#### A. `AGRIBALYSE3.2_Tableur produits alimentaires_PublieAOUT25.xlsx`

- **Functional unit:** `1 kg of food product consumed at the consumer` (including intermediate supply-chain and consumer preparation losses).
- **System boundary:** Cradle-to-grave across 6 stages (`Agriculture`, `Transformation`, `Emballage`, `Transport`, `Supermarché et distribution`, `Consommation`).
- **LCIA method:** EF 3.1 adapted for SimaPro v1.00 (single score in `mPt/kg` + 19 midpoint/sub-indicator columns).
- **Entity & Primary/Join Key:** `Code AGB` (2,458 rows; 2,451 unique codes + 7 duplicate codes `9901`, `25998`, `26013`, `26034`, `26037`, `26232`, `27029` where both the unfixed software version and packaging-fixed version are present; none of the 7 duplicates are dairy products). For unique identification across all 2,458 rows, use composite key `(Code AGB, LCI Name)`.

**Sheet `Synthese` (2,458 data rows, rows 4–2461; 32 columns):**

| Col Index (0-based) | Excel Col | Header (Row 3) | Indicator Label (Row 2) | Unit / Values |
|---|---|---|---|---|
| 0 | `A` | `Code AGB` | — | Integer or string code (e.g., `19023`, `3000_1`). Join key across sheets. |
| 1 | `B` | `Code CIQUAL` | — | ANSES CIQUAL nutritional database code. |
| 2 | `C` | `Groupe d'aliment` | — | Food group (e.g., `'lait et produits laitiers'`: 223 rows; `'matières grasses'`: 58 rows; `'glaces et sorbets'`: 25 rows). |
| 3 | `D` | `Sous-groupe d'aliment` | — | Food subgroup (`'fromages'`: 121, `'produits laitiers frais et assimilés'`: 79, `'laits'`: 17, `'crèmes et spécialités à base de crème'`: 6, `'beurres'`: 10, `'glaces'`: 10, `'desserts glacés'`: 12). |
| 4 | `E` | `Nom du Produit en Français` | — | French product name. |
| 5 | `F` | `LCI Name` | — | English LCI dataset name. |
| 6 | `G` | `code saison (0 : hors saison ; 1 : de saison ; 2 : mix de consommation FR)` | — | Seasonality code (`0`, `1`, `2`). |
| 7 | `H` | `code avion (1 : par avion)` | — | Air-freight flag (`0` or `1`). |
| 8 | `I` | `Livraison` | — | Delivery temperature mode (`'Glacé'`, `'Ambiant (long)'`, `'Congelé'`, `'Ambiant (court)'`, `'Ambiant (moyen)'`). |
| 9 | `J` | `Approche emballage ` | — | Packaging modelling flag: `'PACK AGB'` (product-specific packaging inventory) or `'PACK PROXY'` (approximated from a similar product). |
| 10 | `K` | `Préparation` | — | Consumer preparation mode (e.g., `'Pas de préparation'`, `'Four'`, `'Poêle'`, `'Micro-ondes'`, `'ébullition'`). |
| 11 | `L` | `DQR - Note de qualité de la donnée (1 excellente ; 5 très faible)` | — | Overall Data Quality Rating (`1.0` best to `5.0` worst). |
| 12 | `M` | `mPt/kg de produit` | `Score unique EF 3.1` | `mPt/kg de produit` |
| 13 | `N` | `kg CO2 eq/kg de produit` | `Changement climatique` | `kg CO2 eq/kg de produit` |
| 14 | `O` | `kg CVC11 eq/kg de produit` | `Appauvrissement de la couche d'ozone` | `kg CFC11 eq/kg` (note typo `CVC11` in sheet header) |
| 15 | `P` | `kBq U-235 eq/kg de produit` | `Rayonnements ionisants` | `kBq U-235 eq/kg de produit` |
| 16 | `Q` | `kg NMVOC eq/kg de produit` | `Formation photochimique d'ozone` | `kg NMVOC eq/kg de produit` |
| 17 | `R` | `disease inc./kg de produit` | `Particules fines` | `disease inc./kg de produit` |
| 18 | `S` | `CTUh/kg de produit` | `Effets toxicologiques sur la santé humaine : substances non-cancérogènes` | `CTUh/kg de produit` |
| 19 | `T` | `CTUh/kg de produit` | `Effets toxicologiques sur la santé humaine : substances cancérogènes` | `CTUh/kg de produit` |
| 20 | `U` | `mol H+ eq/kg de produit` | `Acidification terrestre et eaux douces` | `mol H+ eq/kg de produit` |
| 21 | `V` | `kg P eq/kg de produit` | `Eutrophisation eaux douces` | `kg P eq/kg de produit` |
| 22 | `W` | `kg N eq/kg de produit` | `Eutrophisation marine` | `kg N eq/kg de produit` |
| 23 | `X` | `mol N eq/kg de produit` | `Eutrophisation terrestre` | `mol N eq/kg de produit` |
| 24 | `Y` | `CTUe/kg de produit` | `Écotoxicité pour écosystèmes aquatiques d'eau douce` | `CTUe/kg de produit` |
| 25 | `Z` | `Pt/kg de produit` | `Utilisation du sol` | `Pt/kg de produit` |
| 26 | `AA` | `m3 depriv./kg de produit` | `Épuisement des ressources eau` | `m3 depriv./kg de produit` (AWARE water deprivation) |
| 27 | `AB` | `MJ/kg de produit` | `Épuisement des ressources énergétiques` | `MJ/kg de produit` (fossil energy resource use) |
| 28 | `AC` | `kg Sb eq/kg de produit` | `Épuisement des ressources minéraux` | `kg Sb eq/kg de produit` |
| 29 | `AD` | `kg CO2 eq/kg de produit` | `Changement climatique - émissions biogéniques` | `kg CO2 eq/kg de produit` |
| 30 | `AE` | `kg CO2 eq/kg de produit` | `Changement climatique - émissions fossiles` | `kg CO2 eq/kg de produit` |
| 31 | `AF` | `kg CO2 eq/kg de produit` | `Changement climatique - émissions liées au changement d'affectation des sols` | `kg CO2 eq/kg de produit` |

**Sheet `Detail etape` (2,458 valid product rows + 12,445 trailing formula rows; 153 columns):**

- **Columns `0..7` (`A..H`):** `Code AGB`, `Code CIQUAL`, `Groupe d'aliment`, `Sous-groupe d'aliment`, `Nom du Produit en Français`, `LCI Name`, `DQR`, `Nom et code` (formula `=E5&" ("&A5&")"` which produces `' ()'` on trailing rows `2463..14907` where `Code AGB` is `None`).
- **Columns `8..147` (`I..ER`):** 20 blocks of 7 columns each (`20 × 7 = 140` columns) corresponding to the exact 20 impact indicators in `Synthese` (columns `12..31`). Within each 7-column block, the sub-columns are:
  1. `Agriculture`
  2. `Transformation`
  3. `Emballage` (packaging raw material production, conversion, transport to factory, and packaging end-of-life)
  4. `Transport`
  5. `Supermarché et distribution`
  6. `Consommation`
  7. `Total`
  *(Note: exact zero values in `Detail etape` are stored as the string `"-"` rather than `0.0`.)*
- **Columns `148..152` (`ES..EW`):** `DQR Overall`, `P` (Precision), `TiR` (Time Representativeness), `GR` (Geographical Representativeness), `TeR` (Technological Representativeness).

**Sheet `Detail ingredient` (7,269 valid rows across 1,099 multi-ingredient products; 30 non-empty columns):**

- **Columns `0..9` (`A..J`):** `Ciqual AGB`, `Ciqual code`, `Nom Français`, `Groupe d'aliment`, `Sous-groupe d'aliment`, `LCI Name`, `Ingredients` (e.g., `'Lait'`, `'Crème'`, `'Sucre'`, `'Autres étapes'`), `Code et Nom`, `Groupe`, `Sous-groupe`.
- **Columns `10..29` (`K..AD`):** The 20 EF 3.1 impact indicators per kg of finished product contributed by that ingredient row.

#### B. `AGRIBALYSE3.2_partie agriculture_conv_PublieNOV25.xlsx` & `AGRIBALYSE3.2_Tableur agriculture_bio_PublieNov24.xlsx`

- **Functional unit:** `1 kg of agricultural product at farm gate` (`sortie ferme`).
- **System boundary:** Cradle-to-farm-gate (excludes dairy processing, packaging, retail, and consumer stages).
- **Data sheets:** `AGB 3.2 agricole conventionnel` (227 rows; 8 in `Agricultural\Animal production\Dairy\Transformation`) and `AGB 3.2 agricole biologique` (226 rows; 6 in `Agricultural\Animal production\Dairy\Transformation`).
- **Columns (`0..23`, 24 columns):**
  - `0`: `Nom du Produit en Français`
  - `1`: `LCI Name` (primary identifier, e.g., `Cow milk, conventional, national average, at farm gate {FR} U`)
  - `2`: `Type de production` (`'Elevage'` or `'Culture'`)
  - `3`: `Catégorie` (e.g., `'Agricultural\Animal production\Dairy\Transformation'`)
  - `4..23`: Same 20 EF 3.1 indicators (`mPt/kg`, `kg CO2 eq/kg`, `kg CFC11 eq/kg`, etc.).

#### C. `Méthodologie Alimentation Annexes_AGB 3.2.xlsx` (13 sheets)

Key dairy-relevant reference sheets:
- **`6. Density` (13 data rows):** Bulk density (`kg/L`) for liquid products, including 3 dairy rows: `Milk, semi-skimmed, pasteurised` (`1.034 kg/L`), `Goat milk, whole, raw` (`1.08 kg/L`), `Liquid cream 30% fat, UHT` (`0.984 kg/L`).
- **`8. Milk yield for cheeses` (118 data rows):** Maps `Cheese name` and `CIQUAL` code (`12112` Abondance, `12105` Beaufort, `12110` Comté, etc.) to `Milk type` (`Cow`, `Goat`, `Sheep`, `Buffalo`), `Yield (ACTALIA 2022)` (kg of milk per kg of cheese, e.g., `8.9` for Abondance, `9.4` for Beaufort, `10` for Comté, or `'Générique (8,52)'`), and `ACYVIA process used as proxy`.

---

### 3.2 French PDO Cheese LCA (`data/raw/pdo_cheese_lca/`)

- **True Observation Entity:** French PDO (Protected Designation of Origin / AOP) cheese variety (`44` distinct cheeses: 29 cow, 12 goat, 2 sheep, 1 sheep/whey `Brocciu`).
- **Primary / Join Key:** Normalized cheese name (`normalize_pdo_cheese_name(raw_name)`), required because raw strings contain trailing whitespace across all 7 tables and a spelling discrepancy at index 9 (`'Camenbert de Normandie '` in `characterization` and `LCIA` vs. `'Camembert de Normandie '` in `allocations`, `coproducts`, `distances`, `specifications`, and `LCI`).
- **Functional Unit:** `1 kg of ripened cheese` (`FU = 1kg of cheese`).
- **System Boundary:** Cradle-to-ripened-cheese gate (farm milk production, milk transport, milk pumping, milk storage, milk processing, cheese ripening, equipment cleaning; plus inter-site cheese transport to a shared ripening room in the `Additional` / `Alternative` scenario). **Packaging is excluded.**

| File Name | Sheet Name | Rows × Cols | Entity Grain | Columns & Units |
|---|---|---|---|---|
| `dataset_PDOcheeses_characterization.xlsx` | `Feuil1` | `46 × 5` (44 data rows) | 1 row per cheese (44 rows) | `Cheeses names` (str), `Technology` (`Pressed cooked cheese`, `Pressed uncooked cheese`, `Bloomy rind cheese`, `Washed rind cheese`, `Blue veined cheese`, `Whey cheese`), `Milk type` (`cow`, `goat`, `sheep`), `Ripening time (days)` (int/float, `9` to `150` days). |
| `dataset_PDOcheeses_allocations.xlsx` | `Feuil1` | `48 × 5` (44 data rows) | 1 row per cheese (44 rows) | `Cheese name` (col B), `Steps before skimming` (dimensionless dry-matter allocation factor `0.466`–`0.73`), `Steps from skimming to draining` (`0.466`–`0.73`), `Steps after draining` (`1` for all 44 cheeses). |
| `dataset_PDOcheeses_coproducts.xlsx` | `Feuil1` | `48 × 4` (44 data rows) | 1 row per cheese (44 rows) | `Cheese name` (col B), `Cream produced (kg)` (`0` to `0.506` kg/kg cheese), `Whey produced (kg)` (`3.89` to `10.17` kg/kg cheese). |
| `data_PDOcheeses_distances.xlsx` | `Estimated distances` | `47 × 3` (44 data rows) | 1 row per cheese (44 rows) | `Cheese name` (col B), `Maximal distance (km)` (`15` to `302` km, estimated from PDO geographical area specifications). |
| `data_PDOcheeses_specifications.xlsx` | `Cheeses specifications` | `105 × 5` (44 non-empty rows) | 1 row per cheese (44 rows) | `Cheese name` (col C), `Link to cheeses specifications` (col D, URLs to INAO / Ministry of Agriculture PDFs accessed Sep/Nov 2020). |
| `data_PDOcheeses_datasheets.xlsx` | `Equipment data sheets` | `9 × 3` (3 data rows) | 1 row per process step (3 rows) | `Step` (`Pumping`, `Milk storage + milk processing`, `Milk processing`), `link to the datasheet...` (equipment manufacturer URLs). |
| `data_PDOcheeses_LCI` *(no `.xlsx` extension)* | `' '` *(single space)* | `102 × 24` | Two stacked 44-row tables (88 cheese×scenario rows) + 13-row background mapping table | **Block 1 (rows 4–47):** `Initial scenario: Ripening at cheese factory` (`LCI without allocation`, `FU = 1kg of cheese`): `Cow milk (lowland)` (`kg`), `Cow milk (highland)` (`kg`), `Sheep milk` (`kg`), `Goat milk` (`kg`), `Milk transport: Transport` (`tkm`), `Milk pumping: Electricity` (`kWh`), `Milk storage: Steel` (`kg`), `Milk storage: Electricity` (`kWh`), `Milk processing: Steel` (`kg`), `Milk processing: Cooper` (`kg`), `Milk processing: Wood` (`m3`), `Milk processing: Electricity` (`kWh`), `Ripening: Steel` (`kg`), `Ripening: Wood` (`m3` in header row 3), `Ripening: Electricity` (`kWh`), `Cleaning: Water` (`kg`), `Cleaning: Sodium hydroxide` (`kg`), `Cleaning: Nitric acid` (`kg`).<br>**Block 2 (rows 55–98):** `Additional scenario: Ripening in a shared ripening room`: same columns plus `Cheese transport: Transport` (`tkm`) at col `O` (index 14), and `Ripening: Wood` header at row 54 col `Q` (index 16) is labelled `kg` despite having identical numbers to Block 1.<br>**Right-hand table (rows 1–14, cols V–X):** Maps `Item` to `Database` (`AGRIBALYSE 3.0`, `Ecoinvent 3`) and `Name in database`. |
| `data_PDOcheeses_LCIA.xlsx` | `LCIA Cheeses` | `1364 × 24` (1,232 data rows) | 1 row per `(cheese, impact_category)` (`44 × 28 = 1,232` rows) | **Col A (`0`):** `Cheese name` (populated only on the first of each cheese's 28 rows; blank separator row between cheeses).<br>**Cols B–K (`1..10`):** `Base scenario` (`Impact category`, `Unit`, `Total`, `Milk production`, `Milk transport`, `Milk pumping`, `Milk storage`, `Milk processing`, `Cheese ripening`, `Equipment cleaning`).<br>**Cols N–X (`13..23`):** `Alternative scenario` (`Impact category`, `Unit`, `Total`, `Milk production`, `Milk transport`, `Milk pumping`, `Milk storage`, `Milk processing`, `Cheese ripening`, `Equipment cleaning`, `Cheese transport`). |

---

### 3.3 USLCI Database (`data/raw/uslci/`)

- **Format:** openLCA JSON-LD export (`openlca.json`: `{"schemaVersion": 3, "repositoryClientVersion": 6, "repositoryServerVersion": 5}`).
- **Entity Directories & Counts:**
  - `processes/`: `1,434` JSON files (`1,408` `UNIT_PROCESS`, `26` `LCI_RESULT`).
  - `flows/`: `5,708` JSON files (`ELEMENTARY_FLOW`, `PRODUCT_FLOW`, `WASTE_FLOW`).
  - `sources/`: `477` JSON files (bibliographic references).
  - `locations/`: `314` JSON files (countries, US states, NERC/FERC regions).
  - `actors/`: `76` JSON files (data developers/organizations).
  - `flow_properties/`: `21` JSON files (Mass, Energy, Volume, Length, Area, Cargo transport, Number of items, etc.).
  - `unit_groups/`: `14` JSON files (Units of mass, energy, volume, transport `t*km`, etc., with conversion factors).
  - `currencies/`: `12` JSON files (`USD`, `EUR`, etc. — used only by USEEIO bridge flows).
  - `dq_systems/`: `2` JSON files (US EPA Process and Flow pedigree matrices).
  - `parameters/`: `1` JSON file.
  - `bin/`: `9` binary attachment files (`1` calculation preferences JSON + `8` PDF/JPG/PNG attachments for water/lithium/cement sources).
  - `lcia_methods/`: **0 files (not present in export).**

**Process JSON Schema (`data/raw/uslci/processes/<uuid>.json`):**

| JSON Path | Type | Description |
|---|---|---|
| `@id` | `string` (UUID) | Unique process identifier (primary key; matches filename stem). |
| `name` | `string` | Process name (e.g., `High density polyethylene, HDPE; virgin resin; at plant`). |
| `category` | `string` | NAICS-based category path (e.g., `31-33: Manufacturing/3252: Resin...`, `Bridge Processes/USLCI to US Electricity Baseline`). |
| `processType` | `string` | `UNIT_PROCESS` (gate-to-gate exchanges) or `LCI_RESULT` (cradle-to-gate aggregated elementary flows). |
| `location.name` | `string` or `null` | Process geography (`United States of America (the)`, `Northern America`, `Global`, etc.). |
| `processDocumentation.validFrom` / `validUntil` | `string` (ISO date) | Temporal validity window of the inventory data. |
| `processDocumentation.technologyDescription` | `string` | Process boundary and technology description. |
| `exchanges[]` | `array<object>` | Input and output flows (`isInput`: `bool`, `isQuantitativeReference`: `bool`, `amount`: `float`, `unit.name`: `string`, `flow.@id`: `UUID`, `flow.name`: `string`, `flow.flowType`: `ELEMENTARY_FLOW` / `PRODUCT_FLOW` / `WASTE_FLOW`, `defaultProvider.@id`: optional upstream process `UUID`). |

---

## 4. Canonical Entity Mapping (Phase 1 Target Model)

Per `vision.md` Section 5, Phase 1 will map these source schemas into six normalized canonical entities without concatenating incompatible sources:

1. **`Product`:** Maps from AGRIBALYSE `Synthese` (`Code AGB`, `Code CIQUAL`, `Groupe d'aliment`, `Sous-groupe d'aliment`, `Livraison`, bulk density from Annex 6) and PDO Cheese `characterization` (`canonical_cheese_name`, `Technology`, `Milk type`, `Ripening time (days)`).
2. **`PackageConfiguration` & `PackageBOMComponent`:** User/scenario-defined BOM components (`body`, `cap`, `label`, `seal`, `liner`, `secondary_box`, `pallet_wrap`) linking to material/conversion/EoL `ImpactFactor` records from NIST (`nist_plastic_carbon_intensity.csv`), USLCI (`processes/`), or AGRIBALYSE stage baselines.
3. **`ProductionObservation`:** Plant-level utility/yield/waste records benchmarked against `ifc_dairy_benchmarks.csv` (`Water`, `Energy`, `Wastewater discharge`, `Total solid waste generation`) and PDO Cheese `LCI` / `coproducts`.
4. **`FinancialObservation`:** Placeholder schema for future Uzbekistan company/supplier records (unit packaging price, processing cost, labour, utilities, capex, discount rate, useful life, currency, price year). **Never populated with fabricated company financial labels.**
5. **`ImpactFactor`:** Normalized factor table retaining `source_dataset_id`, `source_record_id`, `indicator`, `value`, `original_unit`, `normalized_value`, `normalized_unit`, `geography`, `reference_year`, `lcia_method`, `system_boundary`, `functional_unit`, and `provenance_type` (`published-reference`, `proxy`, `measured`).
6. **`Scenario`:** Links a baseline vs. alternative `Product` + `PackageConfiguration` + activity assumptions to deterministic economic and environmental outputs for `1,000 kg of saleable dairy product delivered to a defined distribution point`.
