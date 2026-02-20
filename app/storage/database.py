"""PostgreSQL database models and connection management."""

import os

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://govsense:govsense@localhost:5432/govsense",
)

# Lazy engine / session — created on first use so imports don't fail
# when the database is unreachable (e.g. during testing or CI).
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Dataset(Base):
    """Metadata about an ingested data.gouv.fr dataset."""

    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True)
    title = Column(String(512), nullable=False)
    slug = Column(String(512))
    description = Column(Text)
    organization = Column(String(256))
    license = Column(String(64))
    last_modified = Column(DateTime)
    ingested_at = Column(DateTime, server_default=func.now())


class RegionBudget(Base):
    """Regional budget data (comptes individuels des regions)."""

    __tablename__ = "region_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    region_code = Column(String(8), nullable=False, index=True)
    region_name = Column(String(256))
    total_revenue = Column(Float)
    total_expenditure = Column(Float)
    operating_revenue = Column(Float)
    operating_expenditure = Column(Float)
    investment_revenue = Column(Float)
    investment_expenditure = Column(Float)
    debt = Column(Float)
    population = Column(Integer)


class Commune(Base):
    """Commune demographics data."""

    __tablename__ = "communes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_insee = Column(String(8), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    region_code = Column(String(8), index=True)
    region_name = Column(String(256))
    department_code = Column(String(8))
    department_name = Column(String(256))
    population = Column(Integer)
    area_km2 = Column(Float)
    density = Column(Float)


class RegionStats(Base):
    """Aggregated region-level statistics (cross-joined view)."""

    __tablename__ = "region_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, index=True)
    region_code = Column(String(8), index=True)
    region_name = Column(String(256))
    total_population = Column(Integer)
    total_revenue = Column(Float)
    total_expenditure = Column(Float)
    revenue_per_capita = Column(Float)
    expenditure_per_capita = Column(Float)
    num_communes = Column(Integer)


class RegionEmployment(Base):
    """Regional employment / salary mass data (Urssaf)."""

    __tablename__ = "region_employment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_code = Column(String(8), index=True)
    region_name = Column(String(256))
    month = Column(String(10), index=True)  # YYYY-MM
    salary_mass = Column(Float)
    salary_yoy_change = Column(Float)  # Year-on-year % change
    partial_unemployment_base = Column(Float)
    partial_unemployment_share = Column(Float)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=get_engine())


def get_db():
    """FastAPI dependency that yields a DB session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
