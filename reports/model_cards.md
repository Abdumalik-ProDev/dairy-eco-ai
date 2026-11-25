# DairyEco AI — Phase 3 Model Cards, Generalization Audit & Over/Underfitting Diagnostics

## 1. Epistemic Governance & Anti-Overfitting / Anti-Underfitting Protocol

In strict compliance with `vision.md` Section 8:
1. **No Black-Box Financial/ROI Model on Synthetic Labels:** ROI, NPV, payback, and contribution margin are computed deterministically by `dairyeco.economics.engine`.
2. **Sample-Size-Adaptive Regularization, Subsampling & Inner Hyperparameter Search:**
   - Every linear model uses inner cross-validated regularization (`RidgeCV_L2` over 40 log-spaced $\alpha \in [10^{-2}, 10^3]$, `ElasticNetCV_L1L2` over $L_1/L_2$ ratios and $\alpha$ grids).
   - Every tree ensemble (`RandomForest_Regularized`, `ExtraTrees_Regularized`, `HistGradientBoosting_Regularized`) uses bootstrap subsampling (`max_samples = 0.75..0.85`), feature subsampling (`max_features = 0.5..0.8`), and an inner 3-fold `GridSearchCV` inside each outer training split that adapts `max_depth`, `min_samples_leaf`, and `l2_regularization` to the sample size $N$ — preventing both **leaf-starvation underfitting** on small $N$ ($N=44$) and **deep-tree memorization overfitting**.
   - `CatBoost_Regularized` constrains tree depth (`depth = 3..4`), applies strong $L_2$ leaf regularization (`l2_leaf_reg = 12..15`), and uses stochastic subsampling (`subsample = 0.75`).
   - `GeneralizationEnsemble_LinearTree` blends regularized linear models (`RidgeCV_L2`, `ElasticNetCV_L1L2`) with regularized gradient boosting (`CatBoost_Regularized`) to combine low-variance global linear structure with bounded non-linear interactions.
3. **Scale-Invariant Quantitative Overfitting / Underfitting Diagnosis (`fit_diagnosis`):**
   - Every model is audited by comparing in-fold **Train MAE / R²** against out-of-fold **Validation MAE (`Mean ± Std`) and Pooled OOF R²** using two scale-invariant generalization metrics:
     - **R² Generalization Gap:** $\Delta R^2 = \max(0, R^2_{\text{train}} - R^2_{\text{OOF}})\quad$ (fraction of variance memorized in-sample)
     - **Normalized MAE Gap:** $\Delta \text{NMAE} = \max(0, \text{MAE}_{\text{CV}} - \text{MAE}_{\text{train}}) / \text{MAE}_{\text{dummy}}\quad$ (train-to-CV error gap scaled by baseline target dispersion)
   - Classification rules:
     - `underfit`: OOF MAE fails to improve over `DummyRegressor_Median` by at least 15% or OOF $R^2 < 0.25$.
     - `overfit_high_variance`: $\Delta R^2 > 0.10$ or $\Delta \text{NMAE} > 0.12$.
     - `mild_overfit`: $0.045 < \Delta R^2 \le 0.10$ or $0.065 < \Delta \text{NMAE} \le 0.12$.
     - `well_generalized`: Strong out-of-fold accuracy with tightly bounded generalization gaps ($\Delta R^2 \le 0.045$ and $\Delta \text{NMAE} \le 0.065$).
   - **Strict Generalization-First Champion Selection:** Champion selection strictly prioritizes `well_generalized` candidates with the lowest generalization-penalized OOF MAE.
4. **Held-Out Out-of-Fold (OOF) Permutation Importance:** Feature importances are computed strictly on held-out validation splits $(X_{\text{val}}, y_{\text{val}})$ across folds rather than on training data, eliminating in-sample memorization bias.

---

## 2. Task 1: AGRIBALYSE 3.2 Core Dairy Non-Packaging GWP Regression (N=255, Pre-LCA Attributes)

- **Data Source Type:** `published_reference` (`data/processed/agribalyse_dairy_products.csv`)
- **Target:** `non_packaging_gwp_kgco2e_per_kg` (`kg CO2e / kg product`)
- **Validation:** 20% untouched Stratified Holdout + 5-fold StratifiedKFold on dev split (80%) with inner hyperparameter regularization and held-out OOF permutation importance
- **Features (`7`):** `milk_yield_kg_milk_per_kg_product, density_kg_per_l, dqr_overall, category, agribalyse_subgroup_fr, delivery_mode, baseline_packaging_approach`

### Champion Generalization & Residual Summary
- **Selected Champion Model:** `RidgeCV_L2` (`fit_diagnosis = well_generalized`)
- **Out-of-Fold MAE (Dev):** `0.7497 kg CO2e / kg product` (Fold Mean ± Std: `0.7487 ± 0.1521 kg CO2e / kg product`, Train MAE: `0.7047 kg CO2e / kg product`, Normalized MAE Gap: `0.0218`)
- **Out-of-Fold R² vs. Train R² (Dev):** `OOF R² = 0.6908` vs. `Train R² = 0.7255` (`R² Generalization Gap = 0.0347`)
- **Untouched Holdout Test Set (`n = 51`):** `Holdout MAE = 0.6175 kg CO2e / kg product`, `Holdout R² = 0.9038`
- **Residual Distribution (`kg CO2e / kg product`):** Median Absolute Error = `0.4979`, 90th Percentile AE = `1.6578`, Mean Bias = `+0.0306`

### Cross-Validation & Generalization Gap Table
| Model | Champion | OOF MAE (Primary) | Fold MAE (`Mean ± Std`) | Train MAE | Norm MAE Gap | OOF RMSE | OOF R² | Train R² | R² Gap (`Train - CV`) | Fit Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `DummyRegressor_Median` | — | **2.0170** | `2.0170 ± 0.1016` | 2.0161 | `0.0004` | 2.4172 | -0.1371 | -0.1380 | `0.0000` | `baseline_reference` |
| `RidgeCV_L2` | ★ **Selected** | **0.7497** | `0.7487 ± 0.1521` | 0.7047 | `0.0218` | 1.2605 | 0.6908 | 0.7255 | `0.0347` | `well_generalized` |
| `ElasticNetCV_L1L2` | — | **0.7644** | `0.7634 ± 0.1664` | 0.7110 | `0.0260` | 1.2967 | 0.6728 | 0.7244 | `0.0516` | `mild_overfit` |
| `RandomForest_Regularized` | — | **0.7772** | `0.7770 ± 0.1502` | 0.7159 | `0.0303` | 1.3359 | 0.6527 | 0.7141 | `0.0614` | `mild_overfit` |
| `ExtraTrees_Regularized` | — | **0.8304** | `0.8301 ± 0.1497` | 0.7923 | `0.0187` | 1.4121 | 0.6119 | 0.6542 | `0.0423` | `well_generalized` |
| `HistGradientBoosting_Regularized` | — | **0.7359** | `0.7352 ± 0.1666` | 0.6167 | `0.0588` | 1.2867 | 0.6778 | 0.7763 | `0.0985` | `mild_overfit` |
| `CatBoost_Regularized` | — | **0.8136** | `0.8132 ± 0.1543` | 0.7684 | `0.0222` | 1.3464 | 0.6472 | 0.7107 | `0.0635` | `mild_overfit` |
| `GeneralizationEnsemble_LinearTree` | — | **0.7577** | `0.7569 ± 0.1555` | 0.7093 | `0.0236` | 1.2692 | 0.6865 | 0.7358 | `0.0493` | `mild_overfit` |

### Held-Out OOF Permutation Feature Importances (Non-Causal Explanatory Behaviour)
| Rank | Feature | Held-Out OOF Permutation MAE Importance | Fold Std |
|---:|---|---:|---:|
| 1 | `density_kg_per_l` | **0.9719** | ±0.2005 |
| 2 | `category` | **0.5483** | ±0.1258 |
| 3 | `baseline_packaging_approach` | **0.5412** | ±0.0677 |
| 4 | `agribalyse_subgroup_fr` | **0.4486** | ±0.0982 |
| 5 | `dqr_overall` | **0.3038** | ±0.0738 |
| 6 | `delivery_mode` | **0.2310** | ±0.1120 |

---

## 3. Task 2: French PDO Cheese Exploratory Case Study (N=44 Canonical Cheeses)

- **Data Source Type:** `published_reference` (`data/processed/pdo_cheese_harmonized.csv`, strictly `N = 44` canonical cheese entities; the `1,232` indicator rows in `data_PDOcheeses_LCIA.xlsx` are never treated as independent samples)
- **Validation:** 20% untouched Stratified Holdout (9 cheeses) + 5-fold StratifiedKFold on dev split (35 cheeses)

### 3.1 Regime 2A — Pre-LCI Cheese Specifications & Milk Origin Yield Only (`gwp_base_total_kgco2e_per_kg`)
Predicts total cradle-to-ripening-exit cheese GWP (`kg CO2e / kg ripened cheese`) using only PDO cheese specification, dry-matter allocation across skimming/draining, co-product mass, authorized collection distance, and raw milk origin breakdown (lowland cow, highland/mountain cow, sheep, goat) known **before** measuring factory electricity or cleaning utilities.

#### Champion Generalization & Residual Summary (Regime 2A)
- **Selected Champion Model:** `ElasticNetCV_L1L2` (`fit_diagnosis = well_generalized`)
- **Out-of-Fold MAE (Dev):** `0.1736 kg CO2e / kg ripened cheese` (Fold Mean ± Std: `0.1736 ± 0.1043 kg CO2e / kg ripened cheese`, Train MAE: `0.0492 kg CO2e / kg ripened cheese`, Normalized MAE Gap: `0.0598`)
- **Out-of-Fold R² vs. Train R² (Dev):** `OOF R² = 0.9875` vs. `Train R² = 0.9995` (`R² Generalization Gap = 0.0120`)
- **Untouched Holdout Test Set (`n = 9`):** `Holdout MAE = 0.1829 kg CO2e / kg ripened cheese`, `Holdout R² = 0.9870`
- **Residual Distribution (`kg CO2e / kg ripened cheese`):** Median Absolute Error = `0.0913`, 90th Percentile AE = `0.3448`, Mean Bias = `+0.0429`

#### Cross-Validation & Generalization Gap Table (Regime 2A)
| Model | Champion | OOF MAE (Primary) | Fold MAE (`Mean ± Std`) | Train MAE | Norm MAE Gap | OOF RMSE | OOF R² | Train R² | R² Gap (`Train - CV`) | Fit Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `DummyRegressor_Median` | — | **2.0807** | `2.0807 ± 0.4011` | 2.0616 | `0.0092` | 2.9296 | -0.0523 | -0.0519 | `0.0003` | `baseline_reference` |
| `RidgeCV_L2` | — | **0.1777** | `0.1777 ± 0.0997` | 0.0500 | `0.0614` | 0.3085 | 0.9883 | 0.9995 | `0.0112` | `well_generalized` |
| `ElasticNetCV_L1L2` | ★ **Selected** | **0.1736** | `0.1736 ± 0.1043` | 0.0492 | `0.0598` | 0.3191 | 0.9875 | 0.9995 | `0.0120` | `well_generalized` |
| `RandomForest_Regularized` | — | **0.9163** | `0.9163 ± 0.2395` | 0.7516 | `0.0792` | 1.4086 | 0.7567 | 0.8260 | `0.0693` | `mild_overfit` |
| `ExtraTrees_Regularized` | — | **0.7422** | `0.7422 ± 0.2681` | 0.5359 | `0.0991` | 1.2445 | 0.8101 | 0.9041 | `0.0940` | `mild_overfit` |
| `HistGradientBoosting_Regularized` | — | **0.6062** | `0.6062 ± 0.3112` | 0.4188 | `0.0901` | 1.0295 | 0.8701 | 0.9222 | `0.0521` | `mild_overfit` |
| `CatBoost_Regularized` | — | **0.9155** | `0.9155 ± 0.3263` | 0.7670 | `0.0714` | 1.5287 | 0.7135 | 0.8100 | `0.0965` | `mild_overfit` |
| `GeneralizationEnsemble_LinearTree` | — | **0.4472** | `0.4472 ± 0.1794` | 0.3309 | `0.0559` | 0.7040 | 0.9392 | 0.9643 | `0.0251` | `well_generalized` |

#### Held-Out OOF Permutation Feature Importances (Regime 2A)
| Rank | Feature | Held-Out OOF Permutation MAE Importance | Fold Std |
|---:|---|---:|---:|
| 1 | `ripening_days` | **1.6534** | ±0.7222 |
| 2 | `whey_coproduct_kg_per_kg_cheese` | **0.7422** | ±0.2315 |
| 3 | `allocation_before_skimming` | **0.2561** | ±0.2439 |
| 4 | `milk_type` | **0.1891** | ±0.1075 |
| 5 | `lci_total_raw_milk_kg` | **0.1812** | ±0.2381 |
| 6 | `lci_cow_milk_lowland_kg` | **0.1266** | ±0.1531 |

### 3.2 Regime 2B — Full LCI Physical Inventory Audit (`gwp_base_post_farm_total_kgco2e_per_kg`)
Includes measured processing and ripening electricity (`lci_ripening_electricity_kwh_initial`, `lci_processing_electricity_kwh`) alongside cheese specifications. Demonstrates that once physical LCI utility flows are measured, regularized linear models recover the physical LCA relationship (`OOF R² = 1.0000`, `Holdout R² = 0.9959`, `well_generalized`).

#### Champion Generalization & Residual Summary (Regime 2B)
- **Selected Champion Model:** `ElasticNetCV_L1L2` (`fit_diagnosis = well_generalized`)
- **Out-of-Fold MAE (Dev):** `0.0061 kg CO2e / kg ripened cheese` (Fold Mean ± Std: `0.0061 ± 0.0023 kg CO2e / kg ripened cheese`, Train MAE: `0.0032 kg CO2e / kg ripened cheese`, Normalized MAE Gap: `0.0022`)
- **Out-of-Fold R² vs. Train R² (Dev):** `OOF R² = 1.0000` vs. `Train R² = 1.0000` (`R² Generalization Gap = 0.0000`)
- **Untouched Holdout Test Set (`n = 9`):** `Holdout MAE = 0.0203 kg CO2e / kg ripened cheese`, `Holdout R² = 0.9959`
- **Residual Distribution (`kg CO2e / kg ripened cheese`):** Median Absolute Error = `0.0039`, 90th Percentile AE = `0.0122`, Mean Bias = `-0.0007`

#### Cross-Validation & Generalization Gap Table (Regime 2B)
| Model | Champion | OOF MAE (Primary) | Fold MAE (`Mean ± Std`) | Train MAE | Norm MAE Gap | OOF RMSE | OOF R² | Train R² | R² Gap (`Train - CV`) | Fit Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `DummyRegressor_Median` | — | **1.2978** | `1.2978 ± 0.1300` | 1.2937 | `0.0032` | 2.3564 | -0.1315 | -0.1319 | `0.0000` | `baseline_reference` |
| `RidgeCV_L2` | — | **0.0069** | `0.0069 ± 0.0028` | 0.0023 | `0.0035` | 0.0111 | 1.0000 | 1.0000 | `0.0000` | `well_generalized` |
| `ElasticNetCV_L1L2` | ★ **Selected** | **0.0061** | `0.0061 ± 0.0023` | 0.0032 | `0.0022` | 0.0087 | 1.0000 | 1.0000 | `0.0000` | `well_generalized` |
| `RandomForest_Regularized` | — | **0.4736** | `0.4736 ± 0.2058` | 0.4453 | `0.0218` | 0.9497 | 0.8162 | 0.8570 | `0.0408` | `well_generalized` |
| `ExtraTrees_Regularized` | — | **0.4431** | `0.4431 ± 0.1423` | 0.3246 | `0.0913` | 0.8635 | 0.8481 | 0.9133 | `0.0652` | `mild_overfit` |
| `HistGradientBoosting_Regularized` | — | **0.2747** | `0.2747 ± 0.1634` | 0.2190 | `0.0429` | 0.6171 | 0.9224 | 0.9401 | `0.0177` | `well_generalized` |
| `CatBoost_Regularized` | — | **0.6568** | `0.6568 ± 0.2454` | 0.5387 | `0.0910` | 1.2409 | 0.6862 | 0.8246 | `0.1384` | `overfit_high_variance` |
| `GeneralizationEnsemble_LinearTree` | — | **0.2823** | `0.2823 ± 0.1050` | 0.2312 | `0.0394` | 0.5329 | 0.9421 | 0.9677 | `0.0256` | `well_generalized` |

---

## 4. Task 3: LCA & Cost Engine Surrogate Models (N=1,200 Simulated Scenarios, GroupKFold by Product)

> [!IMPORTANT]
> **Epistemic Disclaimer:** Surrogate trained on deterministic LCA/economic simulator equations. Test MAE/RMSE/R2 measure simulator approximation fidelity on unseen products, NOT real-world empirical predictive accuracy.

- **Data Source Type:** `model_derived` (`data/synthetic/simulated_packaging_scenarios.csv`)
- **Validation:** 20% untouched Group Holdout (by product_id) + 5-fold GroupKFold on dev split with grouped inner hyperparameter tuning

### 4.1 Packaging System GWP Surrogate (`kg CO2e / 1,000 kg saleable product`)

#### Champion Generalization & Residual Summary (GWP Surrogate)
- **Selected Champion Model:** `GeneralizationEnsemble_LinearTree` (`fit_diagnosis = well_generalized`)
- **Out-of-Fold MAE (Dev):** `21.5747 kg CO2e / 1,000 kg saleable product` (Fold Mean ± Std: `21.5724 ± 3.5965 kg CO2e / 1,000 kg saleable product`, Train MAE: `19.3792 kg CO2e / 1,000 kg saleable product`, Normalized MAE Gap: `0.0213`)
- **Out-of-Fold R² vs. Train R² (Dev):** `OOF R² = 0.9443` vs. `Train R² = 0.9592` (`R² Generalization Gap = 0.0149`)
- **Untouched Holdout Test Set (`n = 239`):** `Holdout MAE = 19.0667 kg CO2e / 1,000 kg saleable product`, `Holdout R² = 0.9599`
- **Residual Distribution (`kg CO2e / 1,000 kg saleable product`):** Median Absolute Error = `16.1173`, 90th Percentile AE = `45.6807`, Mean Bias = `+0.4358`

#### Cross-Validation & Generalization Gap Table (GWP Surrogate)
| Model | Champion | OOF MAE (Primary) | Fold MAE (`Mean ± Std`) | Train MAE | Norm MAE Gap | OOF RMSE | OOF R² | Train R² | R² Gap (`Train - CV`) | Fit Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `DummyRegressor_Median` | — | **102.9391** | `102.9447 ± 10.5491` | 102.6922 | `0.0025` | 132.1350 | -0.0289 | -0.0272 | `0.0017` | `baseline_reference` |
| `RidgeCV_L2` | — | **25.4549** | `25.4515 ± 3.6245` | 24.0212 | `0.0139` | 34.9432 | 0.9280 | 0.9367 | `0.0086` | `well_generalized` |
| `ElasticNetCV_L1L2` | — | **25.4881** | `25.4848 ± 3.5277` | 24.1715 | `0.0128` | 34.8285 | 0.9285 | 0.9364 | `0.0079` | `well_generalized` |
| `RandomForest_Regularized` | — | **27.0161** | `27.0192 ± 4.2454` | 21.4090 | `0.0545` | 39.5049 | 0.9080 | 0.9374 | `0.0294` | `well_generalized` |
| `ExtraTrees_Regularized` | — | **31.9200** | `31.9247 ± 6.6892` | 27.4038 | `0.0439` | 46.2062 | 0.8742 | 0.9076 | `0.0335` | `well_generalized` |
| `HistGradientBoosting_Regularized` | — | **22.0590** | `22.0604 ± 2.2902` | 14.0697 | `0.0776` | 33.3957 | 0.9343 | 0.9699 | `0.0357` | `mild_overfit` |
| `CatBoost_Regularized` | — | **22.4308** | `22.4304 ± 4.4873` | 18.3515 | `0.0396` | 36.5209 | 0.9214 | 0.9603 | `0.0389` | `well_generalized` |
| `GeneralizationEnsemble_LinearTree` | ★ **Selected** | **21.5747** | `21.5724 ± 3.5965` | 19.3792 | `0.0213` | 30.7510 | 0.9443 | 0.9592 | `0.0149` | `well_generalized` |

#### Held-Out OOF Permutation Feature Importances (GWP Surrogate)
| Rank | Feature | Held-Out OOF Permutation MAE Importance | Fold Std |
|---:|---|---:|---:|
| 1 | `dairy_non_packaging_gwp_per_kg` | **61.9362** | ±4.6173 |
| 2 | `effective_bom_mass_kg_per_fu` | **50.0823** | ±17.7302 |
| 3 | `spoilage_loss_rate` | **30.6103** | ±2.8716 |
| 4 | `line_reject_rate` | **20.0980** | ±3.0948 |
| 5 | `grid_ci_kgco2e_per_kwh` | **5.5283** | ±0.6652 |
| 6 | `total_bom_mass_g_per_pkg` | **4.0897** | ±2.3019 |

### 4.2 Packaging Attributable Cost Surrogate (`USD / 1,000 kg saleable product`)

#### Champion Generalization & Residual Summary (Cost Surrogate)
- **Selected Champion Model:** `GeneralizationEnsemble_LinearTree` (`fit_diagnosis = well_generalized`)
- **Out-of-Fold MAE (Dev):** `5.8348 USD / 1,000 kg saleable product` (Fold Mean ± Std: `5.8355 ± 1.0856 USD / 1,000 kg saleable product`, Train MAE: `5.2309 USD / 1,000 kg saleable product`, Normalized MAE Gap: `0.0188`)
- **Out-of-Fold R² vs. Train R² (Dev):** `OOF R² = 0.9674` vs. `Train R² = 0.9767` (`R² Generalization Gap = 0.0093`)
- **Untouched Holdout Test Set (`n = 239`):** `Holdout MAE = 5.2644 USD / 1,000 kg saleable product`, `Holdout R² = 0.9707`
- **Residual Distribution (`USD / 1,000 kg saleable product`):** Median Absolute Error = `4.0841`, 90th Percentile AE = `11.3629`, Mean Bias = `-0.0354`

#### Cross-Validation & Generalization Gap Table (Cost Surrogate)
| Model | Champion | OOF MAE (Primary) | Fold MAE (`Mean ± Std`) | Train MAE | Norm MAE Gap | OOF RMSE | OOF R² | Train R² | R² Gap (`Train - CV`) | Fit Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `DummyRegressor_Median` | — | **32.1670** | `32.1693 ± 4.8651` | 32.0526 | `0.0036` | 50.9668 | -0.0300 | -0.0302 | `0.0000` | `baseline_reference` |
| `RidgeCV_L2` | — | **7.0169** | `7.0175 ± 0.9682` | 6.6511 | `0.0114` | 10.9314 | 0.9526 | 0.9588 | `0.0062` | `well_generalized` |
| `ElasticNetCV_L1L2` | — | **7.4901** | `7.4903 ± 0.7638` | 7.1743 | `0.0098` | 11.0368 | 0.9517 | 0.9572 | `0.0055` | `well_generalized` |
| `RandomForest_Regularized` | — | **8.9672** | `8.9682 ± 2.0505` | 6.8988 | `0.0643` | 14.8191 | 0.9129 | 0.9506 | `0.0376` | `well_generalized` |
| `ExtraTrees_Regularized` | — | **10.6183** | `10.6189 ± 1.8074` | 9.1374 | `0.0461` | 15.8474 | 0.9004 | 0.9308 | `0.0304` | `well_generalized` |
| `HistGradientBoosting_Regularized` | — | **6.1396** | `6.1402 ± 1.2686` | 3.9951 | `0.0667` | 10.9906 | 0.9521 | 0.9791 | `0.0270` | `mild_overfit` |
| `CatBoost_Regularized` | — | **6.0392** | `6.0398 ± 1.3591` | 4.8010 | `0.0385` | 9.9044 | 0.9611 | 0.9810 | `0.0199` | `well_generalized` |
| `GeneralizationEnsemble_LinearTree` | ★ **Selected** | **5.8348** | `5.8355 ± 1.0856` | 5.2309 | `0.0188` | 9.0631 | 0.9674 | 0.9767 | `0.0093` | `well_generalized` |

#### Held-Out OOF Permutation Feature Importances (Cost Surrogate)
| Rank | Feature | Held-Out OOF Permutation MAE Importance | Fold Std |
|---:|---|---:|---:|
| 1 | `effective_bom_mass_kg_per_fu` | **36.0184** | ±11.6783 |
| 2 | `weighted_avg_material_price_usd_per_kg` | **14.1985** | ±0.8369 |
| 3 | `spoilage_loss_rate` | **5.7558** | ±0.3162 |
| 4 | `line_reject_rate` | **3.7686** | ±0.4175 |
| 5 | `total_bom_mass_g_per_pkg` | **3.5788** | ±2.4138 |
| 6 | `preset_id` | **3.4904** | ±0.6095 |
