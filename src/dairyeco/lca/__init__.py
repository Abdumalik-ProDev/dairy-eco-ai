"""LCA engine exports."""

from __future__ import annotations

from dairyeco.lca.engine import (
    IFC_PACKAGING_BOUNDS_G_PER_KG,
    FactorCatalog,
    check_scenario_feasibility,
    evaluate_component_lca,
    evaluate_environmental_lca,
    get_default_factor_catalog,
)

__all__ = [
    "IFC_PACKAGING_BOUNDS_G_PER_KG",
    "FactorCatalog",
    "check_scenario_feasibility",
    "evaluate_component_lca",
    "evaluate_environmental_lca",
    "get_default_factor_catalog",
]
