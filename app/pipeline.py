"""Full data pipeline: ingest → clean → transform → store.

Run with:  python -m app.pipeline
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ingestion.data_gouv import (
    get_dataset_metadata,
    ingest_communes,
    ingest_region_budgets,
    DATASETS,
)
from app.processing.cleaner import clean_dataframe
from app.processing.transformer import (
    aggregate_communes_by_region,
    compute_region_stats,
    transform_region_budgets,
)
from app.storage.database import (
    Commune,
    Dataset,
    RegionBudget,
    RegionStats,
    get_session_factory,
    init_db,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _save_dataset_meta(db: Session, slug: str) -> None:
    """Fetch and persist dataset metadata."""
    meta = get_dataset_metadata(slug)
    ds = Dataset(
        id=meta["id"],
        title=meta["title"],
        slug=meta.get("slug"),
        description=(meta.get("description") or "")[:2000],
        organization=(meta.get("organization") or {}).get("name"),
        license=meta.get("license"),
        last_modified=meta.get("last_modified"),
    )
    db.merge(ds)
    db.commit()


def _store_budgets(db: Session, df) -> int:
    """Bulk insert region budget rows."""
    db.query(RegionBudget).delete()
    records = []
    for _, row in df.iterrows():
        records.append(RegionBudget(
            year=int(row["year"]),
            region_code=str(row["region_code"]),
            region_name=row.get("region_name"),
            total_revenue=row.get("total_revenue"),
            total_expenditure=row.get("total_expenditure"),
            operating_revenue=row.get("operating_revenue"),
            operating_expenditure=row.get("operating_expenditure"),
            investment_revenue=row.get("investment_revenue"),
            investment_expenditure=row.get("investment_expenditure"),
            debt=row.get("debt"),
        ))
    db.bulk_save_objects(records)
    db.commit()
    return len(records)


def _store_communes(db: Session, df) -> int:
    """Bulk insert commune rows."""
    db.query(Commune).delete()

    # Detect column names (post-cleaning: snake_case)
    col_map = {
        "code_insee": ["code_insee", "code_commune_insee"],
        "name": ["nom_standard", "nom_commune", "name", "nom"],
        "region_code": ["reg_code", "code_region", "region_code"],
        "region_name": ["reg_nom", "nom_region", "region_name"],
        "department_code": ["dep_code", "code_departement", "department_code"],
        "department_name": ["dep_nom", "nom_departement", "department_name"],
        "population": ["population", "pop"],
        "area_km2": ["superficie_km2", "area_km2", "superficie"],
        "density": ["densite", "density"],
    }

    def _get(row, key):
        for candidate in col_map.get(key, [key]):
            if candidate in row.index:
                return row[candidate]
        return None

    records = []
    for _, row in df.iterrows():
        pop = _get(row, "population")
        records.append(Commune(
            code_insee=str(_get(row, "code_insee") or ""),
            name=str(_get(row, "name") or ""),
            region_code=str(_get(row, "region_code") or ""),
            region_name=str(_get(row, "region_name") or ""),
            department_code=str(_get(row, "department_code") or ""),
            department_name=str(_get(row, "department_name") or ""),
            population=int(pop) if pop and pop == pop else 0,
            area_km2=float(_get(row, "area_km2") or 0),
            density=float(_get(row, "density") or 0),
        ))
    db.bulk_save_objects(records)
    db.commit()
    return len(records)


def _store_region_stats(db: Session, df) -> int:
    """Bulk insert region stats rows."""
    db.query(RegionStats).delete()
    records = []
    for _, row in df.iterrows():
        records.append(RegionStats(
            year=int(row["year"]),
            region_code=str(row["region_code"]),
            region_name=row.get("region_name"),
            total_population=int(row.get("total_population", 0)),
            total_revenue=row.get("total_revenue"),
            total_expenditure=row.get("total_expenditure"),
            revenue_per_capita=row.get("revenue_per_capita"),
            expenditure_per_capita=row.get("expenditure_per_capita"),
            num_communes=int(row.get("num_communes", 0)),
        ))
    db.bulk_save_objects(records)
    db.commit()
    return len(records)


def run_pipeline() -> dict[str, int]:
    """Execute the full ETL pipeline."""
    init_db()
    db = get_session_factory()()
    counts: dict[str, int] = {}

    try:
        # 1. Ingest
        logger.info("=== STEP 1: Ingesting data from data.gouv.fr ===")
        raw_budgets = ingest_region_budgets()
        raw_communes = ingest_communes()

        # 2. Clean
        logger.info("=== STEP 2: Cleaning data ===")
        clean_budgets = clean_dataframe(raw_budgets)
        clean_communes = clean_dataframe(raw_communes)

        # 3. Transform
        logger.info("=== STEP 3: Transforming data ===")
        budgets = transform_region_budgets(clean_budgets)
        communes_agg = aggregate_communes_by_region(clean_communes)
        region_stats = compute_region_stats(budgets, communes_agg)

        # 4. Store
        logger.info("=== STEP 4: Storing to database ===")
        _save_dataset_meta(db, DATASETS["region_budgets"])
        _save_dataset_meta(db, DATASETS["communes"])

        counts["budgets"] = _store_budgets(db, budgets)
        counts["communes"] = _store_communes(db, clean_communes)
        counts["region_stats"] = _store_region_stats(db, region_stats)

        logger.info("=== Pipeline complete ===")
        logger.info("Stored: %s", counts)
        return counts

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_pipeline()
