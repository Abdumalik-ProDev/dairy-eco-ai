# DairyEco AI — Data Sources Documentation (Phase 0)

## 1. Overview and Provenance Philosophy

This document records the authoritative metadata, licensing, scope, functional units, system boundaries, life-cycle impact assessment (LCIA) methods, and intended analytical roles for all five raw data sources present in `data/raw/`.

In accordance with `vision.md` (Revision 2.2):
- **`data/raw/` is strictly immutable.** No files or directories under `data/raw/` have been renamed, edited, moved, or deleted.
- **Directory names were verified from internal file contents.** User-renamed directories (`agribalyse_3_2`, `pdo_cheese_lca`, `uslci`) and PDF files were verified directly from internal headers, XML metadata, JSON-LD manifests, and document title pages.
- **Every value carries a source type:** `measured`, `published_reference`, `proxy`, `assumed`, `synthetic`, or `model_derived`. All five sources in `data/raw/` represent `published_reference` data.

---

## 2. Summary of Confirmed Sources

| `dataset_id` | Local Path | Verified Source Identity | Provider / Publisher | Version / Date | Geography | Confidence |
|---|---|---|---|---|---|---|
| `agribalyse_3_2` | `data/raw/agribalyse_3_2/` | **AGRIBALYSE 3.2** (Food Products, Conventional & Organic Agriculture, Methodology & Annexes) | ADEME, INRAE (`Means-InOut`), GIS REVALIM, EVEA S.A. Coopérative | v3.2 (Sep 2024; food workbook Aug 2025; conv. ag. Nov 2025; bio ag. Nov 2024) | France (`FR`, French market mix) | `high` |
| `pdo_cheese_lca` | `data/raw/pdo_cheese_lca/` | **French PDO Cheese LCA Dataset** (*Life Cycle Assessment of 44 French PDO Cheeses*) | INRAE / Institut Agro / French PDO cheese LCA research consortium (Recherche Data Gouv Dataverse) | 2020–2022 (`docProps/core.xml` modified Apr–Aug 2022; INAO specs accessed Sep/Nov 2020) | France (PDO regions + national transport) | `medium` |
| `uslci` | `data/raw/uslci/` | **U.S. Life Cycle Inventory (USLCI) Database** (openLCA JSON-LD schema v3) | National Renewable Energy Laboratory (NREL) / Federal LCA Commons | FY24.Q1–Q4 (process timestamps up to `2024-09-25`; openLCA v2.0.3 export) | United States (`US`, `RNA`, census regions) | `high` |
| `anl_nist_regional_plastics_2024` | `data/raw/[2024  Taemin Kim] Life-Cycle Analysis Datasets for Regionalized Plastic Pathways.pdf.pdf` | **ANL/ESIA-24/3: Life-Cycle Analysis Datasets for Regionalized Plastic Pathways** | Argonne National Laboratory (Taemin Kim, Longwen Ou, Hoyoung Kwon); sponsored by NIST OISM Circular Economy Program | February 2024 (`ANL/ESIA-24/3`) | China, MENA, USA, Western Europe, Global | `high` |
| `ifc_wbg_ehs_dairy_2007` | `data/raw/111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf` | **Environmental, Health, and Safety (EHS) Guidelines for Dairy Processing** | International Finance Corporation (IFC) / World Bank Group | April 30, 2007 (Report `111927`) | Global / European & Nordic reference benchmarks | `high` |

---

## 3. Detailed Source Specifications

### 3.1 AGRIBALYSE 3.2 (`data/raw/agribalyse_3_2/`)

- **Local Files:** 15 files (`109,928,924` bytes; aggregate SHA-256: `fe12c0a18e614fb4c04da84fb519e49e0131bc6d7f5547a27ce11991ebbc4730`).
  - `MANIFEST.TXT`
  - `AGRIBALYSE3.2_Tableur produits alimentaires_PublieAOUT25.xlsx` (`9.35 MB`)
  - `AGRIBALYSE3.2_partie agriculture_conv_PublieNOV25.xlsx` (`2.15 MB`)
  - `AGRIBALYSE3.2_Tableur agriculture_bio_PublieNov24.xlsx` (`1.53 MB`)
  - `Méthodologie Alimentation Annexes_AGB 3.2.xlsx` (`0.78 MB`)
  - `Alignement methodologique ICV agricole avec AGB 32.xlsx` (`0.23 MB`)
  - `Alignement methodologique ICV transfo avec AGB 32.xlsx` (`0.23 MB`)
  - 8 methodology, change-report, and soya note PDFs (in French and English).
- **Identity Verification:** Confirmed via the `Notice` sheets of the Excel workbooks (`AGRIBALYSE® 3.2 Septembre 2024 - Version corrigée Août 2025` / `18/11/2025`) and the cover pages of the ADEME/INRAE methodology reports.
- **Licence:** **Licence Ouverte / Open Licence ("Etalab")** — explicitly stated in `Notice` row 24 (`Soumis à la Licence Ouverte "Etalab"`). Permits reuse, modification, and commercial/non-commercial redistribution subject to attribution of source and update date. Upstream unit-process background databases (Ecoinvent 3.9.1, WFLDB 3.5) remain subject to their respective licences if accessed outside the aggregated ADEME spreadsheet.
- **Functional Units:**
  - *Food Products Workbook:* **`1 kg of food product consumed at the consumer`** (edible portion as consumed, accounting for preparation and intermediate/consumer food losses).
  - *Agricultural Workbooks (Conventional & Organic):* **`1 kg of agricultural product leaving the farm gate`** (raw milk, cull animal liveweight, or crop product at farm exit).
- **System Boundaries:**
  - *Food Products:* **Cradle-to-grave (`Field to Plate`)** across 6 disaggregated life-cycle stages in `Detail etape`:
    1. `Agriculture` (raw agricultural production, farm inputs, enteric & manure emissions)
    2. `Transformation` (industrial processing, recipe assembly, factory utilities)
    3. `Emballage` (primary/secondary/tertiary packaging material production, forming, transport to plant, and packaging end-of-life)
    4. `Transport` (freight transport across supply chain stages)
    5. `Supermarché et distribution` (retail storage, refrigeration, retail losses)
    6. `Consommation` (household refrigeration, cooking/preparation if any)
  - *Agricultural Workbooks:* **Cradle-to-farm-gate** (`du champ à la sortie de la ferme`).
- **LCIA Method:** **Environmental Footprint `EF 3.1 (adapted) V1.00`** calculated in SimaPro Developer 9.6.0.1. Reports 16 midpoint impact categories plus a weighted single score (`Score unique EF` in `mPt / kg`) and 3 climate change sub-indicators (`Changement climatique - biogénique`, `- fossile`, `- changement d'affectation des sols` in `kg CO2 eq / kg`).
- **Intended Role in DairyEco AI:**
  - Baseline product-level cradle-to-grave and stage-level life-cycle environmental impacts for **`255` core dairy products** (`223` in `lait et produits laitiers`, `10` in `beurres`, `22` in `glaces` / `desserts glacés`) plus `19` infant/beverage dairy products and **`14` farm-gate milk/dairy animal systems** (8 conventional, 6 organic).
  - Reference stage breakdown (`Agriculture`, `Transformation`, `Emballage`, `Transport`, `Supermarché et distribution`, `Consommation`) to isolate baseline packaging (`Emballage`) when evaluating packaging alternatives.
  - Physical milk-to-cheese yield factors (`Méthodologie Alimentation Annexes_AGB 3.2.xlsx`, sheet `8. Milk yield for cheeses`) and dairy densities (`sheet 6. Density`).

---

### 3.2 French PDO Cheese LCA (`data/raw/pdo_cheese_lca/`)

- **Local Files:** 9 files (`382,857` bytes; aggregate SHA-256: `4b201a8b56e11e1d494fa1ab64d862a51eb9a24eb778cb3b55eb348188424d58`).
  - `MANIFEST.TXT`
  - `data_PDOcheeses_LCI` (extensionless file on disk; verified via magic bytes `PK\x03\x04` and `xl/workbook.xml` as an OOXML `.xlsx` workbook)
  - `data_PDOcheeses_LCIA.xlsx`
  - `dataset_PDOcheeses_allocations.xlsx`
  - `dataset_PDOcheeses_characterization.xlsx`
  - `dataset_PDOcheeses_coproducts.xlsx`
  - `data_PDOcheeses_distances.xlsx`
  - `data_PDOcheeses_datasheets.xlsx`
  - `data_PDOcheeses_specifications.xlsx`
- **Identity Verification (`medium` confidence):** Confirmed from internal workbook titles (`LCI without allocation`, `FU = 1kg of cheese`), the exact list of 44 French Protected Designation of Origin (PDO / AOP) cheeses, INAO specification URLs (`https://extranet.inao.gouv.fr/...`, accessed September & November 2020), and background links to `AGRIBALYSE 3.0` and `Ecoinvent 3` (`Cut-off, S`). Confidence is rated `medium` solely because no bibliographic citation, DOI, author list, or explicit licence text is embedded inside the raw files (`docProps/core.xml` has `creator=None` and modified dates `2022-04-04` to `2022-08-25`).
- **Licence:** Hosted on French institutional Dataverse (typically `Etalab Open Licence 2.0` or `CC-BY`), **but not explicitly embedded in the raw files**. Must be verified against the original Dataverse landing page before external redistribution.
- **Functional Unit:** **`1 kg of ripened PDO cheese`** (`FU = 1kg of cheese` at exit of the ripening facility).
- **System Boundaries:** **Cradle-to-ripening-exit (excluding packaging, retail distribution, and consumer phases):**
  - *Base / Initial Scenario (Ripening at cheese factory):* 7 stages — `Milk production`, `Milk transport`, `Milk pumping`, `Milk storage`, `Milk processing`, `Cheese ripening`, `Equipment cleaning`.
  - *Alternative / Additional Scenario (Ripening in a shared ripening room):* 8 stages — adds `Cheese transport` (`t.km`) from the cheese factory to a shared ripening facility and uses deeper underground cellars (`7.21 m3` wood per ton vs. `1.80 m3` wood per ton, slightly higher ripening electricity).
- **Allocation Rule:** **Dry-matter content allocation** between ripened cheese and co-products (cream and liquid whey) at the dairy plant (`data_PDOcheeses_allocations.xlsx`). Mean cheese dry-matter allocation factor is `46.54%` (range `30.89%` for *Chabichou du Poitou* to `58.92%` for *Comté* / *Beaufort*), except *Brocciu* (`100%`, whey cheese).
- **LCIA Method:** **EF 3.0 / ILCD Midpoint** (`28` indicators per cheese across `1,232` rows = `44 cheeses × 28 indicators`).
- **Intended Role in DairyEco AI:**
  - Process-level validation and sensitivity dataset for 44 French cheeses (`29` cow, `12` goat, `3` sheep), linking physical LCI inputs (raw milk `kg`, NaCl, CaCl2, rennet, electricity, natural gas, ripening wood, cleaning chemicals, transport `t.km`), co-product allocations, and stage-disaggregated LCIA impacts.
  - Benchmark for validating processing-stage vs. milk-production-stage emission shares.

---

### 3.3 USLCI Database (`data/raw/uslci/`)

- **Local Files:** 8,070 JSON/bin files (`133,045,311` bytes; aggregate SHA-256: `29fdd16b136263ee6a8f28bf23cf5da459aa58be762da0f114e875561bd05b5d`).
  - `openlca.json` (`schemaVersion: 3`)
  - `categories.json`
  - `processes/` (`1,434` JSON files)
  - `flows/` (`5,708` JSON files)
  - `sources/` (`477`), `locations/` (`314`), `actors/` (`76`), `flow_properties/` (`21`), `unit_groups/` (`14`), `currencies/` (`12`), `dq_systems/` (`2`), `parameters/` (`1`), `bin/` (`9`).
- **Identity Verification:** Confirmed from `openlca.json`, NREL/Franklin Associates/CORRIM/thinkstep/ERG `sources` and `actors` entries, and NAICS category taxonomy in `categories.json`.
- **Licence:** U.S. Federal LCA Commons / NREL USLCI open data terms (publicly available for research and LCA modeling with attribution to NREL / Federal LCA Commons and individual data submitters).
- **Functional Units / Quantitative References:** Process-specific reference flows (`isQuantitativeReference: true` in `exchanges`). Most polymer, corrugated, and fuel datasets use `1.0 kg`, `1.0 m3`, `1.0 l`, or `1.0 t*km`, **but several critical processes use non-unit reference quantities** (e.g., `1000.0 kg` for EPS, secondary aluminum ingot, and aluminum rolling; `1.10516007 kg` for containerboard; `13.5 kg` for aluminum cans; `1.0 sh tn = 907.18474 kg` for MSW combustion and landfilling; `1.0 Mg = 1000.0 kg` for MRF sorting).
- **System Boundaries:** Primarily **gate-to-gate or cradle-to-gate unit processes** (`1,408` `UNIT_PROCESS` records and `26` rolled-up `LCI_RESULT` records).
- **LCIA Method:** **None bundled (`0` LCIA method files exist in `data/raw/uslci/`).** Furthermore, `97` processes are `Bridge Processes` (`USLCI to US Electricity Baseline` and `USLCI to USEEIO`) that contain zero elementary flows and require external Federal LCA Commons repositories to resolve upstream grid electricity and EEIO inputs.
- **Intended Role in DairyEco AI:**
  - Inventory source for North American virgin polymers (`HDPE`, `LDPE`, `LLDPE`, `PET`, `PP`, `GPPS`, `HIPS`, `PVC`, `PLA`, `EPS`), mechanically recycled polymers (`rHDPE`, `rPET`, `rPP` flake and pellet), plastic conversion (`injection molding`, `thermoforming`, `stretch film`, `extrusion`), paperboard (`containerboard`, `corrugated product`), aluminum (`primary ingot` `LCI_RESULT`, `secondary ingot`, `rolling`, `sheet coated`), industrial fuel boilers, freight transport (`truck`, `train`, `ship`), and municipal solid waste end-of-life (`MRF sorting`, `MSW combustion`, `MSW landfilling`).

---

### 3.4 ANL / NIST Regionalized Plastic Pathways PDF (`data/raw/[2024  Taemin Kim] Life-Cycle Analysis Datasets for Regionalized Plastic Pathways.pdf.pdf`)

- **Local File:** 1 PDF file (`1,587,678` bytes; SHA-256: `db42a209799c6212f52ff73cb0d144752201eaf02dd12c96c49d64a61702760c`; 49 pages).
- **Identity Verification:** Title page confirms Technical Report **`ANL/ESIA-24/3`**, *Life-Cycle Analysis Datasets for Regionalized Plastic Pathways*, Energy Systems and Infrastructure Analysis Division, Argonne National Laboratory, by Taemin Kim, Longwen Ou, and Hoyoung Kwon, February 2024, sponsored by the **National Institute of Standards and Technology (NIST)** Office of Information Systems Management (OISM) Circular Economy Program.
- **Licence:** U.S. Federal Government / Argonne National Laboratory public technical report (`ANL/ESIA-24/3`); unrestricted citation and research use with attribution.
- **Functional Unit:** **`1 kg of virgin polymer resin`** (`kgCO2e/kg-polymer` for `PET`, `HDPE`, `LDPE`, `PP`, `PVC`).
- **System Boundary:** **Cradle-to-gate** (from crude oil, natural gas, or coal extraction through refining, cracking/methanol-to-olefins/acetylene, monomer synthesis, and polymerization to virgin resin at plant gate). Excludes downstream converting (injection/blow molding/thermoforming), transport to filler, use phase, and end-of-life.
- **LCIA Method:** **GWP100 (`kgCO2e/kg`)** modeled in R&D GREET (`GREET 2023`) combined with IHS Markit Process Economics Program (PEP) 2021 technology share data and 2023 regional electricity grid carbon intensities (`China: 641 gCO2e/kWh`, `MENA: 616 gCO2e/kWh`, `USA: 400 gCO2e/kWh`, `Western Europe: 300 gCO2e/kWh`, `Global avg: 491 gCO2e/kWh`).
- **Intended Role in DairyEco AI:**
  - Primary regionalized cradle-to-gate carbon intensity reference for virgin packaging polymers (`PET`, `HDPE`, `LDPE`, `PP`, `PVC`) across **China, MENA, USA, Western Europe, and Global average**, enabling sensitivity analysis of resin sourcing region and feedstock pathway (naphtha vs. ethane vs. coal/CTO/MTO/acetylene).

---

### 3.5 IFC / World Bank Group Dairy Processing EHS Guidelines (`data/raw/111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf`)

- **Local File:** 1 PDF file (`225,369` bytes; SHA-256: `90c5963f47291ec64876e62555aebe9959d9eb0f2f0a10fb215cd6c119b257e5`; 15 pages).
- **Identity Verification:** Header and cover confirm **International Finance Corporation (IFC) / World Bank Group**, *Environmental, Health, and Safety Guidelines for Dairy Processing*, April 30, 2007 (`111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf`).
- **Licence:** IFC / World Bank Group public guidelines (open for reference and benchmarking with attribution).
- **Functional Units:**
  - *Table 1 (Effluent Guidelines):* Concentration limits (`mg/L`, `pH`, `°C`, `MPN/100 ml`, `%`).
  - *Table 2 (Solid Waste Generation):* **`kg or tonnes of solid waste per tonne of manufactured dairy product`** (`kg/t` or `t/t` across `Milk/fermented milk`, `Butter`, `Cheese`, `Milk powder`).
  - *Table 3 (Resource and Energy Consumption):* **`liters of water per kg product (`l/kg`)`**, **`kWh per kg product (`KWh/kg`)` or `MJ/t`**, **`grams of packaging per kg product (`g/kg`)`**, and **`liters or kg of wastewater per kg product (`l/kg` or `kg/kg`)`** across `Market milk & acid milk`, `Cheese`, `Milk powder`, `Whey Products`, and `Ice cream` for `Swedish`, `Danish`, `Finnish`, `Norwegian`, and `All Europe` dairies.
- **System Boundary:** **Gate-to-gate dairy processing plant operations** (raw milk reception, pasteurization, separation, fermentation/cheesemaking/drying, CIP cleaning, refrigeration, packaging consumption mass, and effluent treatment).
- **Intended Role in DairyEco AI:**
  - Engineering plausibility bounds and default reference ranges for factory-level water consumption (`0.8–60 l/kg`), energy consumption (`0.09–3.6 kWh/kg`), packaging material intensity (`3.5–35 g/kg product` for market milk, `8–30 g/kg` for cheese, `8–29 g/kg` for milk powder), solid waste generation (`0.2–20 kg/t`), and untreated/treated wastewater effluent limits.

---

## 4. What Public Sources Do NOT Provide (Explicit Scope Boundary)

Per `vision.md` Section 5.6 and Section 6.2, none of the five public datasets in `data/raw/` contain:
1. **Uzbekistan or company-specific financial/supplier prices** (e.g., local UZS/USD per-kg resin, paperboard, foil, or container prices).
2. **Dairy plant capital expenditure (CAPEX), equipment tooling switchover costs, or depreciation schedules.**
3. **Plant-specific labor rates, utility tariffs, or product gross margins.**
4. **Line-specific packaging reject/scrap rates, shelf-life spoilage rates, or consumer willingness-to-pay.**
5. **Exact primary/secondary/tertiary packaging Bill of Materials (BOM) component weights inside AGRIBALYSE** (AGRIBALYSE 3.2 provides the aggregated `Emballage` stage impact for each food product, not the raw gram weights of body/lid/label/case components).

In Phase 1+, any economic or Uzbekistan-specific operational parameter must be explicitly parameterized as user-configurable scenario inputs labeled `assumed` or `proxy`, never fabricated or presented as measured company economics.
