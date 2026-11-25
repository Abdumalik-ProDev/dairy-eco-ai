# DairyEco AI — ML Engineering Lab & Model Audit Center

## Overview

The **ML Engineering Lab & Model Audit Center** is embedded in DairyEco AI's **Developer Mode** (toggled from the main application header). Every audit table and metric is derived directly from source code, processed datasets, model artifacts, and `artifacts/experiments/experiments.jsonl`—never hand-typed.

---

## 1. System Architecture (`src/dairyeco/audit/` + `src/dairyeco/models/registry.py`)

1. **`dairyeco/models/registry.py`** (pure Python, no Streamlit dependency):
   - Single source of truth for `MODEL_REGISTRY` (5 tasks), `FEATURE_DESCRIPTIONS`, `FORBIDDEN_LEAKAGE_COLUMNS`, `PARAM_SPECS`, `make_holdout_split`, `make_splits`, `build_surrogate_feature_row`, `build_experimental_estimator`, and `run_cv_experiment`.
2. **`dairyeco/audit/common.py`**:
   - SHA-256 file and pipeline-source fingerprinting (`sha256_file`, `code_fingerprint`) and AST symbol verification (`symbol_exists`, `symbol_source`).
3. **`dairyeco/audit/splits.py`**:
   - Audits index overlap, group leakage (`product_id` for Task 3), untouched 20% holdout isolation, duplicate feature vectors, target/forbidden-column leakage, and in-fold preprocessing isolation.
4. **`dairyeco/audit/data_records.py`**:
   - Profiles all 8 derived/reference/synthetic tables, scans `src/` via AST for dataset consumers, documents lineage, cleaning operations, EDA statistics, and the feature registry.
5. **`dairyeco/audit/experiments.py`**:
   - Append-only JSONL experiment tracker (`artifacts/experiments/experiments.jsonl`), historical champion baseline registration, learning curves, and noise-robustness checks.
6. **`dairyeco/audit/model_audit.py` & `build.py`**:
   - Evaluates the 8-candidate model pool (`DummyRegressor_Median`, `RidgeCV_L2`, `ElasticNetCV_L1L2`, `RandomForest_Regularized`, `ExtraTrees_Regularized`, `HistGradientBoosting_Regularized`, `CatBoost_Regularized`, `GeneralizationEnsemble_LinearTree` VotingRegressor), builds the 20-item Risk Register, 14-item Decision Register, 8-gate Readiness Evaluator (`G1`–`G8`), and persists 13 JSON audit artifacts to `artifacts/audit/`.

---

## 2. Interactive Developer Mode (`dev_mode.py` & `audit_lab.py`)

Toggling **Developer Mode** in the top bar opens two views:
- **Technical Workbench (5 dynamic tabs):**
  - **A. ML Model Configuration:** Switch between production champions and in-memory experimental fits (`st.form`-batched) with live inference.
  - **B. Data Transparency:** Dataset identity, `ColumnTransformer` preprocessing inspection, feature dictionary, and missing-value audit.
  - **C. Model Transparency:** Cross-model summary across all 5 tasks, 8-candidate CV + untouched holdout benchmark table, OOF permutation importance, and one-feature-at-a-time marginal local attributions.
  - **D. Execution Trace:** Step-by-step deterministic LCA/economics vs. ML surrogate comparison and attached provenance records.
  - **E. Experimentation:** Explicit form-submitted 5-fold CV benchmarking against the production champion with optional logging to `experiments.jsonl`.
- **ML Engineering Lab & Audit (17 sections):**
  - Full governance explorer covering pipeline overview, dataset registry, provenance, lineage, cleaning log, EDA, feature registry, model registry, experiment tracker, hyperparameter tuning sweeps, validation & split audit, bias & readiness gates, explainability, prediction inspector, reproducibility, decision traceability, and open issues.

---

## 3. Separation of Deterministic Core & ML

The Executive Dashboard and FastAPI `/scenarios/compare` endpoint always compute environmental and financial outputs deterministically via `dairyeco.lca.engine` and `dairyeco.economics.engine`. Machine-learning models are strictly separated for research benchmarking (Tasks 1, 2A, 2B) and surrogate approximation studies (Tasks 3A, 3B).
