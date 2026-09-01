from typing import Any

from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]


class MissionRequest(BaseModel):
    mission: str = Field(
        min_length=10,
        max_length=2000,
    )


class MissionPlan(BaseModel):
    location: str
    date: str
    objective: str
    threshold_c: float = 35.0
    tools: list[str]


class InvestigationResponse(BaseModel):
    mission: str
    status: str
    plan: dict[str, Any]
    risk_summary: dict[str, Any]
    recommendations: list[dict[str, Any]]
    peak_periods: list[dict[str, Any]]
    map_data: dict[str, Any]
    investigation_trace: list[dict[str, Any]]
