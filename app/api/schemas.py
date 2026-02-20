"""Pydantic schemas for API request validation and response serialization."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


class DatasetOut(BaseModel):
    id: str
    title: str
    organization: str | None = None
    license: str | None = None
    last_modified: datetime | None = None
    ingested_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Region budgets
# ---------------------------------------------------------------------------


class RegionBudgetOut(BaseModel):
    year: int
    region_code: str
    region_name: str | None = None
    total_revenue: float | None = None
    total_expenditure: float | None = None
    operating_revenue: float | None = None
    operating_expenditure: float | None = None
    investment_revenue: float | None = None
    investment_expenditure: float | None = None
    debt: float | None = None
    population: int | None = None

    model_config = {"from_attributes": True}


class BudgetListOut(BaseModel):
    total: int
    data: list[RegionBudgetOut]


# ---------------------------------------------------------------------------
# Communes
# ---------------------------------------------------------------------------


class CommuneOut(BaseModel):
    code_insee: str
    name: str
    region_code: str | None = None
    region_name: str | None = None
    department_code: str | None = None
    department_name: str | None = None
    population: int | None = None
    area_km2: float | None = None
    density: float | None = None

    model_config = {"from_attributes": True}


class CommuneListOut(BaseModel):
    total: int
    data: list[CommuneOut]


# ---------------------------------------------------------------------------
# Region stats
# ---------------------------------------------------------------------------


class RegionStatsOut(BaseModel):
    year: int
    region_code: str
    region_name: str | None = None
    total_population: int | None = None
    total_revenue: float | None = None
    total_expenditure: float | None = None
    revenue_per_capita: float | None = None
    expenditure_per_capita: float | None = None
    num_communes: int | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------


class YearRange(BaseModel):
    min: int | None = None
    max: int | None = None


class KPIsOut(BaseModel):
    total_communes: int
    total_regions: int
    total_population: int
    budget_year_range: YearRange


# ---------------------------------------------------------------------------
# Employment
# ---------------------------------------------------------------------------


class RegionEmploymentOut(BaseModel):
    region_code: str
    region_name: str | None = None
    month: str
    salary_mass: float | None = None
    salary_yoy_change: float | None = None
    partial_unemployment_base: float | None = None
    partial_unemployment_share: float | None = None

    model_config = {"from_attributes": True}


class EmploymentListOut(BaseModel):
    total: int
    data: list[RegionEmploymentOut]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthOut(BaseModel):
    status: str
    database: str


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class MetricsOut(BaseModel):
    uptime_seconds: float
    total_requests: int
    datasets_ingested: int
    last_pipeline_run: datetime | None = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineRunOut(BaseModel):
    status: str
    message: str
    counts: dict[str, int] | None = None
