"""FastAPI REST endpoints for GovSense."""

from __future__ import annotations

import io
import time
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.auth import verify_api_key
from app.api.cache import clear_cache
from app.api.schemas import (
    BudgetListOut,
    CommuneListOut,
    CommuneOut,
    DatasetOut,
    EmploymentListOut,
    HealthOut,
    KPIsOut,
    MetricsOut,
    RegionBudgetOut,
    RegionEmploymentOut,
    RegionStatsOut,
    YearRange,
)
from app.storage.database import (
    Commune,
    Dataset,
    RegionBudget,
    RegionEmployment,
    RegionStats,
    get_db,
)

router = APIRouter(prefix="/api/v1", tags=["GovSense API"])

# Track startup time for metrics
_start_time = time.time()
_request_count = 0


def _inc_requests():
    global _request_count
    _request_count += 1


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


@router.get("/datasets", summary="List ingested datasets", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[DatasetOut]:
    _inc_requests()
    rows = db.query(Dataset).order_by(Dataset.ingested_at.desc()).all()
    return [DatasetOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Region budgets
# ---------------------------------------------------------------------------


@router.get("/budgets", summary="Query region budgets", response_model=BudgetListOut)
def list_budgets(
    year: int | None = Query(None, description="Filter by year"),
    region_code: str | None = Query(None, description="Filter by region code"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> BudgetListOut:
    _inc_requests()
    q = db.query(RegionBudget)
    if year:
        q = q.filter(RegionBudget.year == year)
    if region_code:
        q = q.filter(RegionBudget.region_code == region_code)
    total = q.count()
    rows = q.order_by(RegionBudget.year, RegionBudget.region_code).offset(offset).limit(limit).all()
    return BudgetListOut(
        total=total,
        data=[RegionBudgetOut.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Communes
# ---------------------------------------------------------------------------


@router.get("/communes", summary="Query communes", response_model=CommuneListOut)
def list_communes(
    region_code: str | None = Query(None),
    department_code: str | None = Query(None),
    search: str | None = Query(None, description="Search by commune name"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> CommuneListOut:
    _inc_requests()
    q = db.query(Commune)
    if region_code:
        q = q.filter(Commune.region_code == region_code)
    if department_code:
        q = q.filter(Commune.department_code == department_code)
    if search:
        q = q.filter(Commune.name.ilike(f"%{search}%"))
    total = q.count()
    rows = q.order_by(Commune.name).offset(offset).limit(limit).all()
    return CommuneListOut(
        total=total,
        data=[CommuneOut.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Region stats (cross-joined view)
# ---------------------------------------------------------------------------


@router.get(
    "/stats/regions",
    summary="Region-level KPIs (budget x demographics)",
    response_model=list[RegionStatsOut],
)
def list_region_stats(
    year: int | None = Query(None),
    region_code: str | None = Query(None),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> list[RegionStatsOut]:
    _inc_requests()
    q = db.query(RegionStats)
    if year:
        q = q.filter(RegionStats.year == year)
    if region_code:
        q = q.filter(RegionStats.region_code == region_code)
    rows = q.order_by(RegionStats.year, RegionStats.region_code).all()
    return [RegionStatsOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Employment
# ---------------------------------------------------------------------------


@router.get("/employment", summary="Regional employment data", response_model=EmploymentListOut)
def list_employment(
    region_code: str | None = Query(None),
    month: str | None = Query(None, description="Filter by month (YYYY-MM)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> EmploymentListOut:
    _inc_requests()
    q = db.query(RegionEmployment)
    if region_code:
        q = q.filter(RegionEmployment.region_code == region_code)
    if month:
        q = q.filter(RegionEmployment.month == month)
    total = q.count()
    rows = (
        q.order_by(RegionEmployment.month.desc(), RegionEmployment.region_name)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return EmploymentListOut(
        total=total,
        data=[RegionEmploymentOut.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Summary KPIs
# ---------------------------------------------------------------------------


@router.get("/kpis", summary="High-level KPIs", response_model=KPIsOut)
def get_kpis(
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> KPIsOut:
    _inc_requests()
    total_communes = db.query(func.count(Commune.id)).scalar() or 0
    total_regions = db.query(func.count(func.distinct(RegionBudget.region_code))).scalar() or 0
    total_population = db.query(func.sum(Commune.population)).scalar() or 0
    budget_years = db.query(func.min(RegionBudget.year), func.max(RegionBudget.year)).first()
    return KPIsOut(
        total_communes=total_communes,
        total_regions=total_regions,
        total_population=total_population,
        budget_year_range=YearRange(
            min=budget_years[0] if budget_years else None,
            max=budget_years[1] if budget_years else None,
        ),
    )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@router.get("/export/budgets", summary="Export budgets as CSV")
def export_budgets_csv(
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
):
    _inc_requests()
    q = db.query(RegionBudget)
    if year:
        q = q.filter(RegionBudget.year == year)
    rows = q.all()
    data = [RegionBudgetOut.model_validate(r).model_dump() for r in rows]
    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=budgets.csv"},
    )


@router.get("/export/stats", summary="Export region stats as CSV")
def export_stats_csv(
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
):
    _inc_requests()
    q = db.query(RegionStats)
    if year:
        q = q.filter(RegionStats.year == year)
    rows = q.all()
    data = [RegionStatsOut.model_validate(r).model_dump() for r in rows]
    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=region_stats.csv"},
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", summary="Application metrics", response_model=MetricsOut)
def get_metrics(
    db: Session = Depends(get_db),
    _key: str = Depends(verify_api_key),
) -> MetricsOut:
    datasets_count = db.query(func.count(Dataset.id)).scalar() or 0
    return MetricsOut(
        uptime_seconds=round(time.time() - _start_time, 2),
        total_requests=_request_count,
        datasets_ingested=datasets_count,
        last_pipeline_run=None,
    )


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


@router.post("/cache/clear", summary="Clear API cache")
def flush_cache(_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    evicted = clear_cache()
    return {"evicted": evicted}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", summary="Health check", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        return HealthOut(status="ok", database="connected")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB error: {exc}") from exc
