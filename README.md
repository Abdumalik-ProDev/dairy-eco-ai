# DairyEco AI (`dairyeco-ai`)

> **Research Prototype:** *An ML-Based Economic and Environmental Decision Support System for Sustainable Dairy Manufacturing and Packaging Optimization*

`DairyEco AI` is a hybrid decision-support prototype combining deterministic Bill-of-Materials (BOM) Life-Cycle Assessment (LCA), engineering unit economics, multi-objective Pareto optimization, one-at-a-time sensitivity analysis, and leakage-free machine-learning surrogates and case studies.

---

## Core Design & Research Governance

1. **Immutable Source Data (`data/raw/`):** All `8,096` raw files across 5 public sources (`AGRIBALYSE 3.2`, `French PDO Cheese LCA`, `USLCI`, `NIST/ANL 2024 Regionalized Plastic Pathways`, `IFC/World Bank 2007 Dairy Processing EHS Guidelines`) are inventoried and SHA-256 checksummed without modification.
2. **Primary Functional Unit:** **`1,000 kg` of saleable dairy product delivered** to a defined distribution point, keeping **Packaging-system assessment** and **Dairy-manufacturing assessment** boundaries distinct.
3. **No Double-Counting of Packaging:** AGRIBALYSE 3.2 finished-product totals include baseline packaging (`PACK AGB` / `PACK PROXY`). `DairyEco AI` subtracts the `Emballage` stage before adding custom BOM packaging systems.
4. **Honest Trade-Off Reporting:** Composite cartons are represented as multi-layer BOMs (`LPB + LDPE + Aluminium foil + HDPE cap`, never 100% paper). Reusable glass models container manufacture amortized over effective trips (`return_rate`, `breakage_loss_rate_per_trip`, `nominal_max_trips`), caustic washing water/energy, and reverse logistics.
5. **Epistemic Provenance:** Every factor and output is tagged as `published_reference`, `proxy`, `assumed`, `measured`, or `model_derived`. Financial results under public/assumed prices are explicitly labelled as scenario estimates, not observed Uzbek company savings.

---

## Quickstart Commands (`uv` & `dairyeco` CLI)

```bash
# 1. Phase 0: Inventory data/raw/ and extract & verify NIST/IFC PDF reference tables
uv run dairyeco inventory
uv run dairyeco extract-pdfs

# 2. Phase 1: Build harmonized & validated analytical tables (CSV + Parquet in data/processed/)
uv run dairyeco harmonize

# 3. Phase 3: Train & cross-validate ML tasks (with 20% untouched holdout) and generate Model Cards
uv run dairyeco train

# 4. Build ML Engineering Lab audit records (artifacts/audit/) & scenario report
uv run dairyeco audit
uv run dairyeco report
uv run dairyeco status

# 5. Run full automated test suite and linter
uv run pytest -v
uv run ruff check src tests

# 6. Launch the interactive Streamlit Decision-Support Dashboard
uv run streamlit run src/dairyeco/dashboard/app.py

# 7. Launch the FastAPI REST Backend
uv run uvicorn dairyeco.api.app:app --reload --port 8000
```

---

## Repository Structure

```text
dairyeco-ai/
├── vision.md                           # Project specification (Revision 2.2)
├── pyproject.toml                      # Package metadata & uv dependencies
├── data/
│   ├── raw/                            # Immutable raw sources (8,096 files)
│   ├── interim/pdf_extraction/         # Extracted PDF tables & rendered PNG verification pages
│   ├── reference/                      # Normalized NIST & IFC reference CSVs
│   ├── processed/                      # Harmonized analytical tables (.csv & .parquet)
│   ├── synthetic/                      # Explicitly labelled LCA-model-derived surrogate scenarios
│   └── metadata/                       # dataset_manifest.csv, raw_file_inventory.csv, data_dictionary.md
├── src/dairyeco/
│   ├── domain/models.py                # Pydantic domain contracts & validation rules
│   ├── data/                           # inventory.py, pdf_extraction.py, audit_inspectors.py, harmonize.py
│   ├── lca/engine.py                   # Deterministic BOM packaging & dairy LCA engine
│   ├── economics/engine.py             # Deterministic unit economics, NPV, payback & abatement cost engine
│   ├── models/pipeline.py              # Leakage-free ML tasks & GroupKFold simulator surrogates
│   ├── optimization/pareto.py          # 12 BOM presets, Pareto frontier & tornado sensitivity engine
│   ├── services/reporting.py           # Scenario orchestration & Markdown report generator
│   ├── api/app.py                      # FastAPI REST endpoints
│   └── dashboard/app.py                # Streamlit interactive dashboard
├── reports/                            # Audit, data quality, PDF review, model cards & scenario reports
├── docs/data_sources.md                # Authoritative source documentation
└── tests/                              # Automated pytest suites (Phases 0-4)
```
