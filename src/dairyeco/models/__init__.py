"""Machine learning pipelines and surrogate evaluation for DairyEco AI."""

from dairyeco.models.pipeline import (
    FORBIDDEN_LEAKAGE_COLUMNS,
    assert_no_feature_leakage,
    generate_simulated_scenario_dataset,
    run_phase3_ml_pipeline,
    run_task1_agribalyse_dairy_regression,
    run_task2_pdo_cheese_case_study,
    run_task3_simulator_surrogate,
)

__all__ = [
    "FORBIDDEN_LEAKAGE_COLUMNS",
    "assert_no_feature_leakage",
    "generate_simulated_scenario_dataset",
    "run_phase3_ml_pipeline",
    "run_task1_agribalyse_dairy_regression",
    "run_task2_pdo_cheese_case_study",
    "run_task3_simulator_surrogate",
]
