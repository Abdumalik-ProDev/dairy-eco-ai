# DairyEco AI — Scenario Decision-Support Report

> [!WARNING]
> **Prototype Epistemic Disclaimer:** This report combines published international LCA reference
> data (`AGRIBALYSE 3.2`, `NIST/ANL 2024`, `USLCI`, `IFC 2007`) with scenario-level economic
> and operational assumptions (`assumed` / `proxy`). Financial metrics are scenario estimates,
> **not validated measurements of any Uzbek dairy company's actual savings or profitability**.

## 1. Product, Functional Unit, and System Boundaries

- **Selected Dairy Product:** `Milk, semi-skimmed, pasteurised` (`AGB-19042`, CIQUAL/AGB `19042`)
- **Category / Delivery Mode:** `fluid_milk` / `Ambiant (long)`
- **Primary Functional Unit (FU):** **`1,000.0 kg` of saleable dairy product delivered**
- **Annual Production Volume:** `5,000,000 kg / year`
- **De-packaged Dairy Product Baseline Footprint (`AGRIBALYSE 3.2` with `Emballage` subtracted):** `1.174 kg CO2e / kg` (`1,174.1 kg CO2e / FU`)
- **Original AGRIBALYSE `Emballage` Stage (`PACK AGB`):** `0.096 kg CO2e / kg` (subtracted before adding custom BOM packaging to prevent double counting)
- **Electricity Grid Assumption:** `0.573 kg CO2e / kWh` (`Cross-regional average (NIST/ANL 2024)`)
- **Economic Basis:** `USD` (Price year `2025`, discount rate `10.0%`, horizon `7 years`)

---

## 2. Scenario Comparison Summary (per `1,000 kg` Saleable Product)

| Scenario | Feasible | Pareto Optimal | Packaging Cost (`USD/FU`) | Total Op. Cost (`USD/FU`) | Packaging GWP (`kg CO2e/FU`) | Combined GWP (`kg CO2e/FU`) | Virgin Plastic (`kg/FU`) | Pkg Mass (`kg/FU`) | Payback (`yrs`) | NPV (`USD`) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Baseline: 1.0 kg Virgin HDPE Bottle (Blow-Molded)** | Yes | No | `74.93` | `128.99` | `130.48` | `1,304.58` | `32.08` | `48.28` | — | — |
| **Alt 1: 1.0 kg Virgin PET Bottle** | Yes | No | `83.37` | `137.43` | `158.15` | `1,332.25` | `36.13` | `52.33` | No payback | -255,447 |
| **Alt 2: 1.0 kg Lightweight 50% rPET Bottle** | Yes | ★ Yes | `64.98` | `119.04` | `100.17` | `1,274.27` | `15.04` | `41.27` | 1.01 | 192,204 |
| **Alt 3: 1.0 kg Composite Aseptic Carton (LPB + LDPE + Al Foil)** | Yes | No | `67.50` | `121.56` | `109.28` | `1,283.38` | `7.17` | `43.43` | 1.35 | 130,862 |
| **Alt 4: 1.0 kg Single-Use Glass Bottle (35% Cullet)** | Yes | No | `243.43` | `297.49` | `537.17` | `1,711.27` | `0.00` | `394.42` | No payback | -4,151,643 |
| **Alt 5: 1.0 kg Returnable Glass Bottle (20 Max Trips, 90% Return)** | Yes | No | `80.02` | `134.08` | `138.74` | `1,312.84` | `0.00` | `58.78` | No payback | -173,901 |
| **Alt 6: 1.0 kg Flexible LDPE/LLDPE Pillow Pouch** | NO | No | `46.29` | `100.35` | `65.55` | `1,239.65` | `7.38` | `20.71` | 0.35 | 647,158 |

### Trade-Off & Feasibility Interpretation

- **Baseline: 1.0 kg Virgin HDPE Bottle (Blow-Molded) (`PKG-HDPE-BOTTLE-1L`):** Reference baseline configuration. (IFC benchmark check: `above_engineering_range (48.3 g/kg > typical 3.5-35.0 g/kg; typical for heavy glass or small single-serve)`)
- **Alt 1: 1.0 kg Virgin PET Bottle (`PKG-PET-BOTTLE-1L`):** Dominated by baseline: higher operating cost and higher packaging GHG emissions. (IFC benchmark check: `above_engineering_range (52.3 g/kg > typical 3.5-35.0 g/kg; typical for heavy glass or small single-serve)`)
- **Alt 2: 1.0 kg Lightweight 50% rPET Bottle (`PKG-RPET50-BOTTLE-1L`):** Win-win: reduces both operating cost and packaging GHG emissions vs baseline. (IFC benchmark check: `above_engineering_range (41.3 g/kg > typical 3.5-35.0 g/kg; typical for heavy glass or small single-serve)`)
- **Alt 3: 1.0 kg Composite Aseptic Carton (LPB + LDPE + Al Foil) (`PKG-CARTON-LPB-1L`):** Win-win: reduces both operating cost and packaging GHG emissions vs baseline. (IFC benchmark check: `above_engineering_range (43.4 g/kg > typical 3.5-35.0 g/kg; typical for heavy glass or small single-serve)`)
- **Alt 4: 1.0 kg Single-Use Glass Bottle (35% Cullet) (`PKG-GLASS-SINGLE-1L`):** Dominated by baseline: higher operating cost and higher packaging GHG emissions. (IFC benchmark check: `above_engineering_range (394.4 g/kg > typical 3.5-35.0 g/kg; typical for heavy glass or small single-serve)`)
- **Alt 5: 1.0 kg Returnable Glass Bottle (20 Max Trips, 90% Return) (`PKG-GLASS-REUSE-1L`):** Dominated by baseline: higher operating cost and higher packaging GHG emissions. (IFC benchmark check: `above_engineering_range (58.8 g/kg > typical 3.5-35.0 g/kg; typical for heavy glass or small single-serve)`)
- **Alt 6: 1.0 kg Flexible LDPE/LLDPE Pillow Pouch (`PKG-POUCH-LDPE-1L`):** Win-win: reduces both operating cost and packaging GHG emissions vs baseline. (IFC benchmark check: `within_engineering_range (20.7 g/kg in typical 3.5-35.0 g/kg)`)
  - **[INFEASIBLE VIOLATION]:** Ambient long-shelf-life product 'Milk, semi-skimmed, pasteurised' requires a high-barrier package, but '1.0 kg Flexible LDPE/LLDPE Pillow Pouch' has high_barrier=False.

---

## 3. One-at-a-Time Tornado Sensitivity Analysis (Baseline Configuration)

| Parameter | Low Cost (`USD/FU`) | High Cost (`USD/FU`) | Cost Swing (`USD/FU`) | Low Pkg GWP (`kg CO2e/FU`) | High Pkg GWP (`kg CO2e/FU`) | GWP Swing (`kg CO2e/FU`) |
|---|---:|---:|---:|---:|---:|---:|
| Package Component Mass (+/-25%) | `112.83` | `145.15` | **`32.32`** | `101.42` | `159.54` | **`58.13`** |
| Electricity Grid Carbon Intensity (+/-25%) | `128.99` | `128.99` | **`0.00`** | `123.99` | `136.97` | **`12.99`** |
| Package-Attributable Spoilage Rate (+/-25%) | `127.13` | `130.86` | **`3.73`** | `127.86` | `133.12` | **`5.26`** |
| Supply & Distribution Distance (+/-25%) | `128.46` | `129.52` | **`1.06`** | `130.13` | `130.83` | **`0.69`** |
| Package Material Unit Price (+/-25%) | `113.47` | `144.51` | **`31.04`** | `130.48` | `130.48` | **`0.00`** |
| Electricity Tariff (+/-25%) | `123.99` | `133.99` | **`10.00`** | `130.48` | `130.48` | **`0.00`** |

---

## 4. Data Provenance & Epistemic Classification

| Source Dataset ID | Record ID | Source Type | Geography | Year | LCIA Method | Notes |
|---|---|---|---|---|---|---|
| `agribalyse_3_2` | `AGB-19042` | `published_reference` | `FR` | `2024/2025` | `EF 3.1 (adapted) V1.00` | De-packaged baseline dairy product 'Milk, semi-skimmed, pasteurised' |
| `anl_nist_regional_plastics_2024` | `NIST-CI-006` | `published_reference` | `Cross-regional average` | `2024` | `GREET 2022/2023 GWP100` | Component 'body' (HDPE): Table 1 (p. xi) cross-regional mean across USA, Western Europe, MENA and China (GWP is published_reference NIST/ANL 2024; fossil_energy_mj and water_l are secondary literature proxies) |
| `anl_nist_regional_plastics_2024` | `NIST-CI-016` | `published_reference` | `Cross-regional average` | `2024` | `GREET 2022/2023 GWP100` | Component 'label' (PP): Table 1 (p. xi) cross-regional mean across USA, Western Europe, MENA and China (GWP is published_reference NIST/ANL 2024; fossil_energy_mj and water_l are secondary literature proxies) |
| `uslci` | `226ed3c2-e020-4c95-b1fc-4559fc2d18ac` | `proxy` | `US/RNA` | `2022/2024` | `IPCC GWP100 / EF 3.1` | Component 'corrugated_case' (corrugated_board): Corrugated product average cradle-to-gate proxy (anchored to USLCI unit process) |
| `anl_nist_regional_plastics_2024` | `NIST-CI-001` | `published_reference` | `Cross-regional average` | `2024` | `GREET 2022/2023 GWP100` | Component 'body' (PET): Table 1 (p. xi) cross-regional mean across USA, Western Europe, MENA and China (GWP is published_reference NIST/ANL 2024; fossil_energy_mj and water_l are secondary literature proxies) |
| `agribalyse_3_2` | `AGB-LPB-PROXY` | `proxy` | `FR/EU` | `2022/2024` | `IPCC GWP100 / EF 3.1` | Component 'body_paperboard' (liquid_packaging_board): Liquid packaging board substrate proxy (PE and Al layers modelled as separate BOM components) |
| `anl_nist_regional_plastics_2024` | `NIST-CI-011` | `published_reference` | `Cross-regional average` | `2024` | `GREET 2022/2023 GWP100` | Component 'pe_moisture_layers' (LDPE): Table 1 (p. xi) cross-regional mean across USA, Western Europe, MENA and China (GWP is published_reference NIST/ANL 2024; fossil_energy_mj and water_l are secondary literature proxies) |
| `uslci` | `99963138-ddf9-3b32-9e93-69593d76cb08` | `published_reference` | `US/RNA` | `2022/2024` | `IPCC GWP100 / EF 3.1` | Component 'aluminium_oxygen_barrier' (aluminium): USLCI LCI_RESULT: Aluminum primary ingot at plant (583 elementary flows; GWP computed directly from USLCI JSON) |
| `agribalyse_3_2` | `AGB-GLASS-VIRGIN-REF` | `proxy` | `FR/EU` | `2022/2024` | `IPCC GWP100 / EF 3.1` | Component 'body' (glass): Container glass (virgin batch) proxy derived from AGRIBALYSE 3.2 packaging documentation (fills USLCI container-glass gap) |
| `uslci` | `c245a252-0860-41d2-9789-802bab7984ab` | `proxy` | `US/RNA` | `2022/2024` | `IPCC GWP100 / EF 3.1` | Component 'label' (paperboard): Containerboard average production proxy (biogenic-adjusted from USLCI unit process, 1.10516 kg qref) |
| `uslci` | `1dbafde2-2bc3-405c-9726-4d92fe7d29f9` | `proxy` | `Northern America` | `2014` | `IPCC AR6 GWP100 + literature roll-up proxy` | Component 'body_film' (LLDPE): Cradle-to-gate proxy anchored to USLCI LLDPE unit process (unlinked upstream inputs) |
