"""Multi-objective Pareto analysis, preset BOMs, and sensitivity sweeps."""

from dairyeco.optimization.pareto import (
    build_preset_package_configurations,
    compare_scenarios,
    identify_pareto_frontier,
    run_one_at_a_time_sensitivity,
)

__all__ = [
    "build_preset_package_configurations",
    "compare_scenarios",
    "identify_pareto_frontier",
    "run_one_at_a_time_sensitivity",
]
