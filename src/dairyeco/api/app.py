"""FastAPI REST application for DairyEco AI decision support."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from dairyeco.config import ARTIFACTS_DIR, PROCESSED_DIR
from dairyeco.domain.models import (
    PackageConfiguration,
    ScenarioAssumptions,
    ScenarioComparisonResult,
)
from dairyeco.lca.engine import get_default_factor_catalog
from dairyeco.optimization.pareto import (
    build_preset_package_configurations,
    compare_scenarios,
    run_one_at_a_time_sensitivity,
)
from dairyeco.services.reporting import (
    generate_scenario_markdown_report,
    load_dairy_products,
)

app = FastAPI(
    title="DairyEco AI API",
    version="0.1.0",
    description=(
        "Hybrid deterministic LCA, engineering economics, multi-objective Pareto, "
        "and ML surrogate decision-support API for sustainable dairy manufacturing and packaging."
    ),
)


class ScenarioCompareRequest(BaseModel):
    """Request payload for multi-scenario comparison."""

    product_id: str = Field(default="AGB-19041", description="AGRIBALYSE product_id")
    baseline_config: PackageConfiguration
    alternative_configs: list[PackageConfiguration] = Field(default_factory=list)
    assumptions: ScenarioAssumptions = Field(default_factory=ScenarioAssumptions)
    include_sensitivity: bool = True


class ScenarioCompareResponse(BaseModel):
    """Response payload for multi-scenario comparison."""

    product_id: str
    product_name: str
    functional_unit_kg: float
    comparisons: list[ScenarioComparisonResult]
    sensitivity_records: list[dict[str, Any]]
    markdown_report: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "dairyeco-ai", "version": "0.1.0"}


@app.get("/products")
def list_products(category: str | None = None) -> list[dict[str, Any]]:
    products = load_dairy_products(PROCESSED_DIR, core_only=True)
    if category:
        products = [p for p in products if str(p.category) == category]
    return [p.model_dump() for p in products]


@app.get("/package-presets")
def list_package_presets() -> list[dict[str, Any]]:
    presets = build_preset_package_configurations()
    return [cfg.model_dump() for cfg in presets.values()]


@app.get("/impact-factors")
def list_impact_factors(domain: str | None = None) -> list[dict[str, Any]]:
    df = get_default_factor_catalog(PROCESSED_DIR).df
    if domain:
        df = df[df["domain"] == domain]
    return df.to_dict(orient="records")


@app.get("/models/metrics")
def get_model_metrics() -> dict[str, Any]:
    summary_path = ARTIFACTS_DIR / "ml_evaluation_summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="ML evaluation summary not found.")
    return json.loads(summary_path.read_text(encoding="utf-8"))


@app.post("/scenarios/compare", response_model=ScenarioCompareResponse)
def evaluate_and_compare_scenarios(
    payload: ScenarioCompareRequest,
) -> ScenarioCompareResponse:
    products = load_dairy_products(PROCESSED_DIR, core_only=False)
    product = next((p for p in products if p.product_id == payload.product_id), None)
    if product is None:
        raise HTTPException(
            status_code=404, detail=f"Dairy product '{payload.product_id}' not found."
        )

    catalog = get_default_factor_catalog(PROCESSED_DIR)
    comparisons = compare_scenarios(
        product=product,
        baseline_config=payload.baseline_config,
        alternative_configs=payload.alternative_configs,
        assumptions=payload.assumptions,
        catalog=catalog,
    )
    sens_df = (
        run_one_at_a_time_sensitivity(
            product=product,
            package_config=payload.baseline_config,
            assumptions=payload.assumptions,
            catalog=catalog,
        )
        if payload.include_sensitivity
        else pd.DataFrame()
    )
    md_report = generate_scenario_markdown_report(
        product=product,
        assumptions=payload.assumptions,
        comparisons=comparisons,
        sensitivity_df=sens_df,
    )

    return ScenarioCompareResponse(
        product_id=product.product_id,
        product_name=product.name_en,
        functional_unit_kg=payload.assumptions.functional_unit_saleable_kg,
        comparisons=comparisons,
        sensitivity_records=sens_df.to_dict(orient="records") if not sens_df.empty else [],
        markdown_report=md_report,
    )
