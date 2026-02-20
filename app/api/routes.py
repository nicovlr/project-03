"""FastAPI REST endpoints for GovSense."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.storage.database import (
    Commune,
    Dataset,
    RegionBudget,
    RegionStats,
    get_db,
)

router = APIRouter(prefix="/api/v1", tags=["GovSense API"])


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

@router.get("/datasets", summary="List ingested datasets")
def list_datasets(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.query(Dataset).order_by(Dataset.ingested_at.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "organization": r.organization,
            "license": r.license,
            "last_modified": str(r.last_modified) if r.last_modified else None,
            "ingested_at": str(r.ingested_at) if r.ingested_at else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Region budgets
# ---------------------------------------------------------------------------

@router.get("/budgets", summary="Query region budgets")
def list_budgets(
    year: int | None = Query(None, description="Filter by year"),
    region_code: str | None = Query(None, description="Filter by region code"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(RegionBudget)
    if year:
        q = q.filter(RegionBudget.year == year)
    if region_code:
        q = q.filter(RegionBudget.region_code == region_code)
    total = q.count()
    rows = q.order_by(RegionBudget.year, RegionBudget.region_code).offset(offset).limit(limit).all()
    return {
        "total": total,
        "data": [
            {
                "year": r.year,
                "region_code": r.region_code,
                "region_name": r.region_name,
                "total_revenue": r.total_revenue,
                "total_expenditure": r.total_expenditure,
                "operating_revenue": r.operating_revenue,
                "operating_expenditure": r.operating_expenditure,
                "investment_revenue": r.investment_revenue,
                "investment_expenditure": r.investment_expenditure,
                "debt": r.debt,
                "population": r.population,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Communes
# ---------------------------------------------------------------------------

@router.get("/communes", summary="Query communes")
def list_communes(
    region_code: str | None = Query(None),
    department_code: str | None = Query(None),
    search: str | None = Query(None, description="Search by commune name"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(Commune)
    if region_code:
        q = q.filter(Commune.region_code == region_code)
    if department_code:
        q = q.filter(Commune.department_code == department_code)
    if search:
        q = q.filter(Commune.name.ilike(f"%{search}%"))
    total = q.count()
    rows = q.order_by(Commune.name).offset(offset).limit(limit).all()
    return {
        "total": total,
        "data": [
            {
                "code_insee": r.code_insee,
                "name": r.name,
                "region_code": r.region_code,
                "region_name": r.region_name,
                "department_code": r.department_code,
                "department_name": r.department_name,
                "population": r.population,
                "area_km2": r.area_km2,
                "density": r.density,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Region stats (cross-joined view)
# ---------------------------------------------------------------------------

@router.get("/stats/regions", summary="Region-level KPIs (budget x demographics)")
def list_region_stats(
    year: int | None = Query(None),
    region_code: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    q = db.query(RegionStats)
    if year:
        q = q.filter(RegionStats.year == year)
    if region_code:
        q = q.filter(RegionStats.region_code == region_code)
    rows = q.order_by(RegionStats.year, RegionStats.region_code).all()
    return [
        {
            "year": r.year,
            "region_code": r.region_code,
            "region_name": r.region_name,
            "total_population": r.total_population,
            "total_revenue": r.total_revenue,
            "total_expenditure": r.total_expenditure,
            "revenue_per_capita": r.revenue_per_capita,
            "expenditure_per_capita": r.expenditure_per_capita,
            "num_communes": r.num_communes,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Summary KPIs
# ---------------------------------------------------------------------------

@router.get("/kpis", summary="High-level KPIs")
def get_kpis(db: Session = Depends(get_db)) -> dict[str, Any]:
    total_communes = db.query(func.count(Commune.id)).scalar() or 0
    total_regions = db.query(func.count(func.distinct(RegionBudget.region_code))).scalar() or 0
    total_population = db.query(func.sum(Commune.population)).scalar() or 0
    budget_years = db.query(
        func.min(RegionBudget.year), func.max(RegionBudget.year)
    ).first()
    return {
        "total_communes": total_communes,
        "total_regions": total_regions,
        "total_population": total_population,
        "budget_year_range": {
            "min": budget_years[0] if budget_years else None,
            "max": budget_years[1] if budget_years else None,
        },
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", summary="Health check")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB error: {exc}")
