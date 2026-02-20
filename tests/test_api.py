"""Integration tests for the FastAPI REST API.

Uses an in-memory SQLite database to avoid requiring PostgreSQL.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import router
from app.storage.database import Base, Commune, RegionBudget, RegionStats, get_db

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed test data before each test."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    db = TestSessionLocal()
    # Clear existing data
    db.query(RegionStats).delete()
    db.query(RegionBudget).delete()
    db.query(Commune).delete()
    db.commit()

    # Seed data
    db.add(RegionBudget(
        year=2023, region_code="011", region_name="Ile-de-France",
        total_revenue=6_000_000, total_expenditure=5_300_000,
        operating_revenue=5_000_000, operating_expenditure=4_500_000,
        investment_revenue=1_000_000, investment_expenditure=800_000,
        debt=2_000_000,
    ))
    db.add(RegionBudget(
        year=2023, region_code="024", region_name="Centre-Val de Loire",
        total_revenue=2_500_000, total_expenditure=2_200_000,
        operating_revenue=2_000_000, operating_expenditure=1_800_000,
        investment_revenue=500_000, investment_expenditure=400_000,
        debt=800_000,
    ))
    db.add(Commune(
        code_insee="75056", name="Paris",
        region_code="11", region_name="Ile-de-France",
        department_code="75", department_name="Paris",
        population=2_165_423, area_km2=105.4, density=20_545,
    ))
    db.add(Commune(
        code_insee="45234", name="Orleans",
        region_code="24", region_name="Centre-Val de Loire",
        department_code="45", department_name="Loiret",
        population=116_685, area_km2=27.5, density=4_243,
    ))
    db.add(RegionStats(
        year=2023, region_code="11", region_name="Ile-de-France",
        total_population=2_165_423, total_revenue=6_000_000,
        total_expenditure=5_300_000, revenue_per_capita=2.77,
        expenditure_per_capita=2.45, num_communes=1,
    ))
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=TEST_ENGINE)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"


class TestKPIs:
    def test_kpis_returns_correct_counts(self):
        resp = client.get("/api/v1/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_communes"] == 2
        assert data["total_regions"] == 2
        assert data["budget_year_range"]["min"] == 2023
        assert data["budget_year_range"]["max"] == 2023


class TestBudgets:
    def test_list_all_budgets(self):
        resp = client.get("/api/v1/budgets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

    def test_filter_by_year(self):
        resp = client.get("/api/v1/budgets?year=2023")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_by_region(self):
        resp = client.get("/api/v1/budgets?region_code=011")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["region_name"] == "Ile-de-France"

    def test_pagination(self):
        resp = client.get("/api/v1/budgets?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["data"]) == 1


class TestCommunes:
    def test_list_communes(self):
        resp = client.get("/api/v1/communes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_search_commune(self):
        resp = client.get("/api/v1/communes?search=Paris")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["name"] == "Paris"

    def test_filter_by_department(self):
        resp = client.get("/api/v1/communes?department_code=45")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestRegionStats:
    def test_list_stats(self):
        resp = client.get("/api/v1/stats/regions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["region_name"] == "Ile-de-France"

    def test_filter_by_year(self):
        resp = client.get("/api/v1/stats/regions?year=2023")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_region(self):
        resp = client.get("/api/v1/stats/regions?region_code=11")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestExport:
    def test_export_budgets_csv(self):
        resp = client.get("/api/v1/export/budgets")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "budgets.csv" in resp.headers["content-disposition"]
        lines = resp.text.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_export_stats_csv(self):
        resp = client.get("/api/v1/export/stats")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


class TestMetrics:
    def test_metrics(self):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "datasets_ingested" in data


class TestCacheEndpoint:
    def test_clear_cache(self):
        resp = client.post("/api/v1/cache/clear")
        assert resp.status_code == 200
        assert "evicted" in resp.json()
