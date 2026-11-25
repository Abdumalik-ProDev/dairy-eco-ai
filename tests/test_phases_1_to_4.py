"""Automated tests for Phases 1, 2, 3, and 4 (harmonization, LCA/economic engines, ML, Pareto, API)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from dairyeco.api.app import app
from dairyeco.domain.models import (
    ConversionProcess,
    DairyCategory,
    DairyProductRecord,
    DataSourceType,
    MaterialFamily,
    PackageComponentBOM,
    PackageConfiguration,
    PackageFormat,
    ReuseParameters,
    ScenarioAssumptions,
)
from dairyeco.economics.engine import (
    calculate_npv,
    evaluate_economics,
)
from dairyeco.lca.engine import (
    evaluate_environmental_lca,
)
from dairyeco.models.pipeline import (
    assert_no_feature_leakage,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "models"
REPORTS_DIR = REPO_ROOT / "reports"


def test_phase1_harmonized_tables_and_provenance() -> None:
    """Verify all Phase 1 processed tables exist, have expected counts, and preserve provenance."""
    agb_df = pd.read_csv(PROCESSED_DIR / "agribalyse_dairy_products.csv")
    farm_df = pd.read_csv(PROCESSED_DIR / "agribalyse_farm_gate_dairy.csv")
    pdo_df = pd.read_csv(PROCESSED_DIR / "pdo_cheese_harmonized.csv")
    uslci_df = pd.read_csv(PROCESSED_DIR / "uslci_curated_factors.csv")
    factors_df = pd.read_csv(PROCESSED_DIR / "packaging_impact_factors.csv")

    assert len(agb_df) == 277
    assert int(agb_df["is_core_dairy"].sum()) == 255
    assert len(farm_df) == 14
    assert len(pdo_df) == 44
    assert len(uslci_df) == 56
    assert len(factors_df) == 65

    # Verify Parquet counterparts exist
    for name in [
        "agribalyse_dairy_products",
        "agribalyse_farm_gate_dairy",
        "pdo_cheese_harmonized",
        "uslci_curated_factors",
        "packaging_impact_factors",
    ]:
        assert (PROCESSED_DIR / f"{name}.parquet").exists()

    # Check de-packaged GWP identity: non_packaging = total - packaging_stage
    diff = (
        agb_df["total_gwp_kgco2e_per_kg"]
        - agb_df["packaging_stage_gwp_kgco2e_per_kg"]
        - agb_df["non_packaging_gwp_kgco2e_per_kg"]
    )
    assert np.allclose(diff, 0.0, atol=1e-5)

    # Check PDO cheese shared ripening room reduces ripening electricity on Abondance
    abondance = pdo_df[pdo_df["cheese_name"] == "Abondance"].iloc[0]
    assert float(abondance["lci_ripening_electricity_kwh_initial"]) == pytest.approx(62.5)
    assert float(abondance["lci_ripening_electricity_kwh_additional"]) == pytest.approx(0.853)
    assert float(abondance["gwp_alt_total_kgco2e_per_kg"]) < float(
        abondance["gwp_base_total_kgco2e_per_kg"]
    )


def test_domain_validation_rules() -> None:
    """Verify composite carton rule (never 100% paper) and EoL fraction sum rule."""
    # 1. EoL fractions must sum to 1.0
    with pytest.raises(ValueError, match="must sum to 1.0"):
        PackageComponentBOM(
            component_name="body",
            material_family=MaterialFamily.HDPE,
            mass_g_per_package=25.0,
            eol_recycling_fraction=0.50,
            eol_incineration_fraction=0.50,
            eol_landfill_fraction=0.50,
        )

    # 2. Composite carton cannot be represented as 100% paperboard
    with pytest.raises(ValueError, match="never 100% paper"):
        PackageConfiguration(
            config_id="INVALID-100PCT-PAPER-CARTON",
            name="Invalid 100% Paper Carton",
            package_format=PackageFormat.CARTON,
            net_fill_mass_kg=1.0,
            components=[
                PackageComponentBOM(
                    component_name="body",
                    material_family=MaterialFamily.LIQUID_PACKAGING_BOARD,
                    mass_g_per_package=28.0,
                )
            ],
        )


def test_phase2_hand_calculated_lca_and_economic_formulas() -> None:
    """Verify deterministic LCA and financial formulas against exact hand calculations."""
    # 1. Check effective reuse trips formula:
    # p = return_rate * (1 - breakage) = 0.90 * 0.98 = 0.882
    # effective_trips = (1 - 0.882^20) / (1 - 0.882) = 7.7865571
    reuse = ReuseParameters(
        is_reusable=True,
        nominal_max_trips=20,
        return_rate=0.90,
        breakage_loss_rate_per_trip=0.02,
    )
    expected_trips = (1.0 - (0.882**20)) / (1.0 - 0.882)
    assert reuse.effective_trips == pytest.approx(expected_trips, rel=1e-6)

    # 2. Hand-calculated single-component scenario (zero reject/loss, zero transport, 1000 kg FU)
    product = DairyProductRecord(
        product_id="TEST-MILK",
        code_agb="00000",
        name_fr="Lait test",
        name_en="Test Milk",
        category=DairyCategory.FLUID_MILK,
        agribalyse_group="lait et produits laitiers",
        agribalyse_subgroup="laits",
        delivery_mode="Glacé",
        baseline_packaging_approach="PACK AGB",
        total_gwp_kgco2e_per_kg=1.30,
        non_packaging_gwp_kgco2e_per_kg=1.20,
        agriculture_gwp_kgco2e_per_kg=1.00,
        transformation_gwp_kgco2e_per_kg=0.12,
        packaging_stage_gwp_kgco2e_per_kg=0.10,
        transport_gwp_kgco2e_per_kg=0.05,
        distribution_gwp_kgco2e_per_kg=0.02,
        consumption_gwp_kgco2e_per_kg=0.01,
        single_score_mpt_per_kg=0.11,
        water_depletion_m3_per_kg=0.03,
        fossil_energy_mj_per_kg=4.5,
    )
    # 1000 packages of 1 kg each, 20 g virgin HDPE in USA (1.32 kg CO2e/kg),
    # no conversion (none = 0.0), 100% landfill (0.042 kg CO2e/kg), price $2.00/kg
    cfg = PackageConfiguration(
        config_id="HAND-CALC-HDPE",
        name="Hand Calc HDPE",
        package_format=PackageFormat.BOTTLE,
        net_fill_mass_kg=1.0,
        components=[
            PackageComponentBOM(
                component_name="body",
                material_family=MaterialFamily.HDPE,
                mass_g_per_package=20.0,
                recycled_content_fraction=0.0,
                conversion_process=ConversionProcess.NONE,
                resin_region="USA",
                unit_price_usd_per_kg=2.00,
                eol_recycling_fraction=0.0,
                eol_incineration_fraction=0.0,
                eol_landfill_fraction=1.0,
            )
        ],
        supplier_to_plant_distance_km=0.0,
        distribution_distance_km=0.0,
        line_reject_rate=0.0,
        package_attributable_spoilage_rate=0.0,
        compatible_categories=[DairyCategory.FLUID_MILK],
    )
    assumptions = ScenarioAssumptions(
        functional_unit_saleable_kg=1000.0,
        include_dairy_processing_boundary=True,
    )
    env = evaluate_environmental_lca(product, cfg, assumptions)
    econ = evaluate_economics(cfg, assumptions, env)

    # 1000 packages * 20 g = 20.0 kg HDPE
    assert env.total_packaging_mass_kg == pytest.approx(20.0)
    assert env.virgin_fossil_plastic_mass_kg == pytest.approx(20.0)
    # Raw material GWP = 20 kg * 1.32 kg CO2e/kg (NIST USA HDPE) = 26.40 kg CO2e
    assert env.packaging_raw_material_gwp_kgco2e == pytest.approx(26.40, abs=1e-2)
    # EoL landfill GWP = 20 kg * 0.042 kg CO2e/kg = 0.84 kg CO2e
    assert env.packaging_eol_gwp_kgco2e == pytest.approx(0.84, abs=1e-2)
    # Dairy base GWP = 1000 kg * 1.20 = 1200.0 kg CO2e
    assert env.dairy_non_packaging_base_gwp_kgco2e == pytest.approx(1200.0)
    assert env.combined_total_gwp_kgco2e == pytest.approx(1227.24, abs=1e-2)

    # Material cost = 20 kg * $2.00/kg = $40.00
    assert econ.packaging_material_cost_per_fu == pytest.approx(40.00)
    assert "scenario_estimate" in econ.epistemic_status

    # Check NPV hand calculation: -$10,000 investment + $3,000/yr for 5 yrs at 0% = +$5,000
    assert calculate_npv(10_000.0, 3_000.0, 0.0, 5) == pytest.approx(5_000.0)


def test_phase3_ml_leakage_guard_and_artifacts() -> None:
    """Verify leakage guard, overfitting/underfitting diagnostics, and champion selection."""
    # Leakage guard must block target, IDs, co-computed LCIA indicators, and circular surrogate features
    with pytest.raises(ValueError, match="Target leakage detected"):
        assert_no_feature_leakage(
            ["category", "single_score_mpt_per_kg"], "non_packaging_gwp_kgco2e_per_kg"
        )
    with pytest.raises(ValueError, match="Target leakage detected"):
        assert_no_feature_leakage(["cheese_name", "ripening_days"], "target")
    with pytest.raises(ValueError, match="Target leakage detected"):
        assert_no_feature_leakage(
            ["category", "eutrophication_marine_kg_n_eq_per_kg"], "non_packaging_gwp_kgco2e_per_kg"
        )
    with pytest.raises(ValueError, match="Target leakage detected"):
        assert_no_feature_leakage(
            ["net_fill_mass_kg", "expected_bom_material_spend_usd_per_fu"], "target_cost"
        )

    summary_path = ARTIFACTS_DIR / "ml_evaluation_summary.json"
    assert summary_path.exists()
    assert (REPORTS_DIR / "model_cards.md").exists()
    assert (SYNTHETIC_DIR / "simulated_packaging_scenarios.csv").exists()

    sim_df = pd.read_csv(SYNTHETIC_DIR / "simulated_packaging_scenarios.csv")
    assert len(sim_df) == 1200
    assert (sim_df["source_type"] == str(DataSourceType.MODEL_DERIVED)).all()

    import json

    ml_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for diag in [
        ml_summary["task1_agribalyse"]["champion_diagnostics"],
        ml_summary["task2_pdo_cheese"]["champion_diagnostics"],
        ml_summary["task2_pdo_cheese"]["regime_2b_full_lci_post_farm"]["champion_diagnostics"],
        ml_summary["task3_simulator_surrogate"]["gwp_surrogate"]["champion_diagnostics"],
        ml_summary["task3_simulator_surrogate"]["cost_surrogate"]["champion_diagnostics"],
    ]:
        assert diag["fit_diagnosis"] == "well_generalized"
        assert float(diag["r2_generalization_gap"]) <= 0.045
        assert float(diag["normalized_mae_gap"]) <= 0.065
        assert int(diag["holdout_n"]) > 0
        assert float(diag["holdout_r2"]) > 0.50


def test_phase4_pareto_sensitivity_and_fastapi_endpoints() -> None:
    """Verify multi-scenario Pareto optimization, sensitivity analysis, and FastAPI endpoints."""
    client = TestClient(app)

    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_prods = client.get("/products?category=fluid_milk")
    assert r_prods.status_code == 200
    prods = r_prods.json()
    assert len(prods) == 14

    r_presets = client.get("/package-presets")
    assert r_presets.status_code == 200
    presets = r_presets.json()
    assert len(presets) == 12

    r_metrics = client.get("/models/metrics")
    assert r_metrics.status_code == 200
    metrics_data = r_metrics.json()
    assert "task1_agribalyse" in metrics_data
    assert "task2_pdo_cheese" in metrics_data
    assert "task3_simulator_surrogate" in metrics_data

    # Test POST /scenarios/compare
    payload = {
        "product_id": prods[0]["product_id"],
        "baseline_config": presets[0],
        "alternative_configs": [presets[2], presets[3], presets[4]],
        "include_sensitivity": True,
    }
    r_comp = client.post("/scenarios/compare", json=payload)
    assert r_comp.status_code == 200
    body = r_comp.json()
    assert len(body["comparisons"]) == 4
    assert any(c["is_pareto_optimal"] for c in body["comparisons"])
    assert len(body["sensitivity_records"]) >= 6
    assert "DairyEco AI — Scenario Decision-Support Report" in body["markdown_report"]


def test_streamlit_executive_dashboard() -> None:
    """Verify the redesigned Streamlit executive dashboard renders in English, Uzbek, and Russian."""
    from streamlit.testing.v1 import AppTest

    from dairyeco.config import PROJECT_ROOT

    app_path = PROJECT_ROOT / "src" / "dairyeco" / "dashboard" / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=30)
    at.run()
    assert not at.exception, f"Streamlit app raised exception (EN): {at.exception}"
    assert any("What happens if we switch" in t.value for t in at.title)

    metric_labels_en = {m.label for m in at.metric}
    assert "Proposed annual packaging cost" in metric_labels_en
    assert "Packaging carbon footprint" in metric_labels_en

    # Switch to Uzbek (uz)
    at.session_state["platform_lang"] = "uz"
    at.run()
    assert not at.exception, f"Streamlit app raised exception (UZ): {at.exception}"
    assert any("Sut mahsulotlari qadoqlarini" in t.value for t in at.title)
    metric_labels_uz = {m.label for m in at.metric}
    assert "Taklif etilayotgan yillik qadoqlash xarajati" in metric_labels_uz
    assert "Qadoqlashning uglerod izi (CO₂e)" in metric_labels_uz

    # Switch to Russian (ru)
    at.session_state["platform_lang"] = "ru"
    at.run()
    assert not at.exception, f"Streamlit app raised exception (RU): {at.exception}"
    assert any("Что изменится при переходе" in t.value for t in at.title)
    metric_labels_ru = {m.label for m in at.metric}
    assert "Годовые затраты на новую упаковку" in metric_labels_ru
    assert "Углеродный след упаковки (CO₂e)" in metric_labels_ru


def test_payback_schedule_and_scenario_dynamics() -> None:
    """Verify profitable, unprofitable, horizon-exceeding, zero-CAPEX, and dynamic payback cases."""
    from dairyeco.economics.engine import calculate_payback_schedule
    from dairyeco.optimization.pareto import (
        build_preset_package_configurations,
        compare_scenarios,
    )
    from dairyeco.services.reporting import load_dairy_products

    # 1. Profitable within horizon ($50k CAPEX, +$25k/yr savings, 5-year horizon -> 2.00 yrs / 24.0 mos)
    res_prof = calculate_payback_schedule(
        initial_investment=50_000.0,
        annual_incremental_cash_flow=25_000.0,
        horizon_years=5,
    )
    assert res_prof["simple_payback_years"] == pytest.approx(2.00)
    assert res_prof["simple_payback_months"] == pytest.approx(24.0)
    assert res_prof["payback_status"] == "within_horizon"
    assert res_prof["cumulative_net_cash_flow_usd"] == pytest.approx(75_000.0)
    assert res_prof["cumulative_cash_flow_schedule"] == [
        -50_000.0,
        -25_000.0,
        0.0,
        25_000.0,
        50_000.0,
        75_000.0,
    ]

    # 2. Positive cash flow that exceeds evaluation horizon -> returns None (No payback) on 5-yr horizon
    res_exceed = calculate_payback_schedule(
        initial_investment=50_000.0,
        annual_incremental_cash_flow=9_400.0,
        horizon_years=5,
    )
    assert res_exceed["simple_payback_years"] is None
    assert res_exceed["simple_payback_months"] is None
    assert res_exceed["unconstrained_payback_years"] == pytest.approx(5.32, abs=0.01)
    assert res_exceed["payback_status"] == "exceeds_horizon"
    assert res_exceed["cumulative_net_cash_flow_usd"] == pytest.approx(-3_000.0)

    # Same cash flow on 7-yr horizon recovers CAPEX -> returns 5.32 yrs / 63.8 mos
    res_recov = calculate_payback_schedule(
        initial_investment=50_000.0,
        annual_incremental_cash_flow=9_400.0,
        horizon_years=7,
    )
    assert res_recov["simple_payback_years"] == pytest.approx(5.32, abs=0.01)
    assert res_recov["simple_payback_months"] == pytest.approx(63.8, abs=0.1)
    assert res_recov["payback_status"] == "within_horizon"
    assert res_recov["cumulative_net_cash_flow_usd"] == pytest.approx(15_800.0)

    # 3. Unprofitable (negative incremental cash flow) -> None (No payback)
    res_unprof = calculate_payback_schedule(
        initial_investment=50_000.0,
        annual_incremental_cash_flow=-12_000.0,
        horizon_years=5,
    )
    assert res_unprof["simple_payback_years"] is None
    assert res_unprof["simple_payback_months"] is None
    assert res_unprof["payback_status"] == "negative_cash_flow"
    assert res_unprof["cumulative_net_cash_flow_usd"] == pytest.approx(-110_000.0)

    # 4. Zero-investment ($0 CAPEX) cases
    res_zero_pos = calculate_payback_schedule(
        initial_investment=0.0,
        annual_incremental_cash_flow=15_000.0,
        horizon_years=5,
    )
    assert res_zero_pos["simple_payback_years"] == 0.0
    assert res_zero_pos["simple_payback_months"] == 0.0
    assert res_zero_pos["payback_status"] == "immediate"

    res_zero_neg = calculate_payback_schedule(
        initial_investment=0.0,
        annual_incremental_cash_flow=-5_000.0,
        horizon_years=5,
    )
    assert res_zero_neg["simple_payback_years"] is None
    assert res_zero_neg["payback_status"] == "negative_cash_flow"

    # 5. Dynamic scenario responsiveness (volume, CAPEX, and alternative selection)
    milk = load_dairy_products()[0]
    presets = build_preset_package_configurations()
    base_cfg = presets["PKG-HDPE-BOTTLE-1L"]
    rpet_cfg = presets["PKG-RPET50-BOTTLE-1L"]
    pet_cfg = presets["PKG-PET-BOTTLE-1L"]

    a_5k = ScenarioAssumptions(
        annual_production_volume_kg=5_000_000.0,
        incremental_capex_usd=45_000.0,
        installation_commissioning_usd=5_000.0,
        project_lifetime_years=5,
    )
    a_10k = ScenarioAssumptions(
        annual_production_volume_kg=10_000_000.0,
        incremental_capex_usd=45_000.0,
        installation_commissioning_usd=5_000.0,
        project_lifetime_years=5,
    )
    a_high_capex = ScenarioAssumptions(
        annual_production_volume_kg=5_000_000.0,
        incremental_capex_usd=95_000.0,
        installation_commissioning_usd=5_000.0,
        project_lifetime_years=5,
    )

    c_5k = compare_scenarios(milk, base_cfg, [rpet_cfg, pet_cfg], a_5k)
    c_10k = compare_scenarios(milk, base_cfg, [rpet_cfg], a_10k)
    c_hc = compare_scenarios(milk, base_cfg, [rpet_cfg], a_high_capex)

    pb_5k = c_5k[1].simple_payback_years
    pb_10k = c_10k[1].simple_payback_years
    pb_hc = c_hc[1].simple_payback_years
    pb_pet = c_5k[2].simple_payback_years

    assert pb_5k is not None and pb_5k > 0
    assert pb_10k == pytest.approx(pb_5k / 2.0, abs=0.02)
    assert pb_hc == pytest.approx(pb_5k * 2.0, abs=0.02)
    assert pb_pet is None  # Virgin PET is costlier than HDPE -> No payback


def test_developer_mode_and_ml_experimentation() -> None:
    """Verify Developer Mode toggle, execution trace, and in-memory ML experimentation."""
    from streamlit.testing.v1 import AppTest

    from dairyeco.config import PROJECT_ROOT
    from dairyeco.dashboard.dev_mode import (
        load_ml_artifacts,
        run_in_memory_cv_experiment,
    )

    summary, _ = load_ml_artifacts()
    exp_ridge_low = run_in_memory_cv_experiment(
        "task1_agribalyse_gwp", "Ridge", {"alpha": 0.01}, summary
    )
    exp_ridge_high = run_in_memory_cv_experiment(
        "task1_agribalyse_gwp", "Ridge", {"alpha": 100.0}, summary
    )
    assert exp_ridge_low["oof_mae"] != exp_ridge_high["oof_mae"]

    app_path = PROJECT_ROOT / "src" / "dairyeco" / "dashboard" / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=40)
    at.run()
    assert not at.exception

    # Enable Developer Mode toggle and verify all 5 technical tabs render cleanly without auto-running Tab E CV
    at.toggle(key="developer_mode_toggle").set_value(True).run()
    assert not at.exception, f"Developer Mode raised exception: {at.exception}"
    tab_labels = [tab.label for tab in at.tabs]
    assert any("A. ML Model Configuration" in lbl for lbl in tab_labels)
    assert any("B. Data Transparency" in lbl for lbl in tab_labels)
    assert any("C. Model Transparency" in lbl for lbl in tab_labels)
    assert any("D. Execution Trace" in lbl for lbl in tab_labels)
    assert any("E. Experimentation" in lbl for lbl in tab_labels)
    assert "exp_result_task3a_surrogate_gwp" not in at.session_state


def test_reusable_reverse_transport_and_tiny_abatement_safety() -> None:
    """Verify reusable reverse transport excludes disposable caps/labels and tiny GWP delta never crashes."""
    from dairyeco.economics.engine import compute_capital_and_tradeoff_metrics
    from dairyeco.lca.engine import compute_packaging_transport_tkm

    cfg = PackageConfiguration(
        config_id="REUSE-TEST",
        name="Reuse Test",
        package_format=PackageFormat.BOTTLE,
        net_fill_mass_kg=1.0,
        components=[
            PackageComponentBOM(
                component_name="body",
                material_family=MaterialFamily.GLASS,
                mass_g_per_package=400.0,
            ),
            PackageComponentBOM(
                component_name="cap",
                material_family=MaterialFamily.ALUMINIUM,
                mass_g_per_package=50.0,
            ),
        ],
        reuse=ReuseParameters(
            is_reusable=True,
            nominal_max_trips=10,
            return_rate=0.90,
            breakage_loss_rate_per_trip=0.0,
            reverse_transport_distance_km=100.0,
        ),
        supplier_to_plant_distance_km=0.0,
        distribution_distance_km=0.0,
        line_reject_rate=0.0,
        package_attributable_spoilage_rate=0.0,
    )
    # 1,000 packages * 400 g body = 400 kg * 0.90 return = 360 kg = 0.36 t * 100 km = 36.0 t*km
    _, _, rev_tkm = compute_packaging_transport_tkm(cfg, total_pkg_mass_kg=100.0, gross_packages_filled=1000.0)
    assert rev_tkm == pytest.approx(36.0)

    # Tiny GWP reduction (0.0005 kg CO2e/FU -> avoided_tco2e <= 1e-6 -> abatement_cost is None) must not raise TypeError
    product = DairyProductRecord(
        product_id="TEST-MILK-TINY",
        code_agb="00001",
        name_fr="Lait",
        name_en="Milk",
        category=DairyCategory.FLUID_MILK,
        agribalyse_group="lait et produits laitiers",
        agribalyse_subgroup="laits",
        delivery_mode="Glacé",
        baseline_packaging_approach="PACK AGB",
        total_gwp_kgco2e_per_kg=1.30,
        non_packaging_gwp_kgco2e_per_kg=1.20,
        agriculture_gwp_kgco2e_per_kg=1.00,
        transformation_gwp_kgco2e_per_kg=0.12,
        packaging_stage_gwp_kgco2e_per_kg=0.10,
        transport_gwp_kgco2e_per_kg=0.05,
        distribution_gwp_kgco2e_per_kg=0.02,
        consumption_gwp_kgco2e_per_kg=0.01,
        single_score_mpt_per_kg=0.11,
        water_depletion_m3_per_kg=0.03,
        fossil_energy_mj_per_kg=4.5,
    )
    assump = ScenarioAssumptions()
    base_env = evaluate_environmental_lca(product, cfg, assump)
    alt_env = base_env.model_copy(
        update={"packaging_system_total_gwp_kgco2e": base_env.packaging_system_total_gwp_kgco2e - 0.0005}
    )
    base_econ = evaluate_economics(cfg, assump, base_env)
    alt_econ = base_econ.model_copy(
        update={"total_operating_cost_per_fu": base_econ.total_operating_cost_per_fu + 5.0}
    )
    metrics = compute_capital_and_tradeoff_metrics(base_env, base_econ, alt_env, alt_econ, assump)
    assert metrics["abatement_cost_usd_per_tco2e"] is None
    assert "Environmental trade-off" in metrics["tradeoff_summary"]


def test_registry_and_audit_decoupled_from_streamlit() -> None:
    """Verify dairyeco.models.registry and dairyeco.audit do not import streamlit."""
    import subprocess
    import sys

    code = (
        "import sys; import dairyeco.models.registry; import dairyeco.audit.build; "
        "assert 'streamlit' not in sys.modules"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr



