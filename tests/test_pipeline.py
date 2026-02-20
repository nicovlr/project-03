"""Tests for the GovSense data pipeline.

These tests validate the cleaning, transformation, and cross-join logic
without requiring a live database or network access.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.processing.cleaner import (
    clean_dataframe,
    coerce_numeric,
    drop_duplicates,
    fill_missing_numeric,
    normalize_columns,
    strip_strings,
)
from app.processing.transformer import (
    aggregate_communes_by_region,
    compute_region_stats,
    transform_region_budgets,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def raw_budget_df() -> pd.DataFrame:
    """Simulates raw data from the region budgets CSV."""
    return pd.DataFrame({
        "exer": [2023, 2023, 2022, 2022],
        "reg": ["011", "024", "011", "024"],
        "lbudg": ["REG ILE-DE-FRANCE", "REG CENTRE-VAL DE LOIRE", "REG ILE-DE-FRANCE", "REG CENTRE-VAL DE LOIRE"],
        "rec_totales_f": [5_000_000, 2_000_000, 4_800_000, 1_900_000],
        "dep_totales_f": [4_500_000, 1_800_000, 4_300_000, 1_700_000],
        "rec_totales_i": [1_000_000, 500_000, 900_000, 450_000],
        "dep_totales_i": [800_000, 400_000, 750_000, 380_000],
        "encours_de_dette": [2_000_000, 800_000, 2_100_000, 850_000],
    })


@pytest.fixture
def raw_communes_df() -> pd.DataFrame:
    """Simulates raw data from the communes CSV."""
    return pd.DataFrame({
        "code_insee": ["75056", "45234", "75001", "45001"],
        "nom_standard": ["Paris", "Orleans", "Paris 1er", "Amilly"],
        "reg_code": ["11", "24", "11", "24"],
        "reg_nom": ["Ile-de-France", "Centre-Val de Loire", "Ile-de-France", "Centre-Val de Loire"],
        "dep_code": ["75", "45", "75", "45"],
        "dep_nom": ["Paris", "Loiret", "Paris", "Loiret"],
        "population": [2_165_423, 116_685, 16_000, 14_500],
        "superficie_km2": [105.4, 27.5, 1.8, 35.0],
        "densite": [20_545, 4_243, 8_889, 414],
    })


# ── Cleaner tests ─────────────────────────────────────────────────────────

class TestCleaner:
    def test_normalize_columns(self):
        df = pd.DataFrame({"  Col Name  ": [1], "Another-Col!": [2]})
        result = normalize_columns(df)
        assert list(result.columns) == ["col_name", "another_col"]

    def test_strip_strings(self):
        df = pd.DataFrame({"city": ["  Paris  ", " Lyon"], "code": ["75", "69"]})
        result = strip_strings(df)
        assert result["city"].tolist() == ["Paris", "Lyon"]

    def test_drop_duplicates(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
        result = drop_duplicates(df)
        assert len(result) == 2

    def test_drop_duplicates_subset(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 20, 20]})
        result = drop_duplicates(df, subset=["a"])
        assert len(result) == 2

    def test_fill_missing_numeric(self):
        df = pd.DataFrame({"val": [1.0, None, 3.0], "name": ["a", "b", "c"]})
        result = fill_missing_numeric(df)
        assert result["val"].tolist() == [1.0, 0.0, 3.0]
        # String column should be untouched
        assert result["name"].tolist() == ["a", "b", "c"]

    def test_coerce_numeric(self):
        df = pd.DataFrame({"amount": ["100", "N/A", "300"]})
        result = coerce_numeric(df, ["amount"])
        assert result["amount"].tolist()[0] == 100.0
        assert pd.isna(result["amount"].tolist()[1])

    def test_clean_dataframe_integration(self):
        df = pd.DataFrame({
            "  Name ": ["  Alice ", "  Bob ", "  Alice "],
            "Value!": [10, None, 10],
        })
        result = clean_dataframe(df)
        assert "name" in result.columns
        assert "value" in result.columns
        assert result["value"].isna().sum() == 0
        assert len(result) == 2  # dedup


# ── Transformer tests ─────────────────────────────────────────────────────

class TestTransformRegionBudgets:
    def test_basic_transform(self, raw_budget_df):
        result = transform_region_budgets(raw_budget_df)
        assert "year" in result.columns
        assert "region_code" in result.columns
        assert "total_revenue" in result.columns
        assert "total_expenditure" in result.columns
        assert len(result) == 4

    def test_region_name_cleaned(self, raw_budget_df):
        result = transform_region_budgets(raw_budget_df)
        names = result["region_name"].unique()
        for name in names:
            assert not name.startswith("REG ")

    def test_total_computed(self, raw_budget_df):
        result = transform_region_budgets(raw_budget_df)
        row = result[(result["year"] == 2023) & (result["region_code"] == "011")].iloc[0]
        assert row["total_revenue"] == 6_000_000  # 5M operating + 1M investment
        assert row["total_expenditure"] == 5_300_000  # 4.5M + 0.8M

    def test_missing_column_raises(self):
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        with pytest.raises(KeyError):
            transform_region_budgets(df)


class TestAggregateCommunesByRegion:
    def test_aggregation(self, raw_communes_df):
        result = aggregate_communes_by_region(raw_communes_df)
        assert len(result) == 2  # Two regions
        assert "total_population" in result.columns
        assert "num_communes" in result.columns

    def test_population_sums(self, raw_communes_df):
        result = aggregate_communes_by_region(raw_communes_df)
        idf = result[result["region_code"] == "11"]
        assert idf.iloc[0]["total_population"] == 2_165_423 + 16_000


class TestComputeRegionStats:
    def test_cross_join(self, raw_budget_df, raw_communes_df):
        budgets = transform_region_budgets(raw_budget_df)
        communes_agg = aggregate_communes_by_region(raw_communes_df)
        result = compute_region_stats(budgets, communes_agg)

        assert len(result) > 0
        assert "revenue_per_capita" in result.columns
        assert "expenditure_per_capita" in result.columns

    def test_per_capita_values(self, raw_budget_df, raw_communes_df):
        budgets = transform_region_budgets(raw_budget_df)
        communes_agg = aggregate_communes_by_region(raw_communes_df)
        result = compute_region_stats(budgets, communes_agg)

        # Check that per_capita = total / population
        for _, row in result.iterrows():
            if row["total_population"] > 0:
                expected_rev = round(row["total_revenue"] / row["total_population"], 2)
                assert abs(row["revenue_per_capita"] - expected_rev) < 0.01

    def test_empty_on_no_match(self):
        budgets = pd.DataFrame({
            "year": [2023],
            "region_code": ["999"],
            "region_name": ["Nowhere"],
            "total_revenue": [100],
            "total_expenditure": [90],
        })
        communes = pd.DataFrame({
            "region_code": ["1"],
            "total_population": [1000],
            "num_communes": [5],
        })
        result = compute_region_stats(budgets, communes)
        assert len(result) == 0


# ── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_dataframe_cleaning(self):
        df = pd.DataFrame({"A": [], "B": []})
        result = clean_dataframe(df)
        assert len(result) == 0

    def test_zero_population_per_capita(self):
        """revenue_per_capita should not crash on zero population."""
        budgets = pd.DataFrame({
            "year": [2023],
            "region_code": ["1"],
            "region_name": ["Test"],
            "total_revenue": [100_000],
            "total_expenditure": [90_000],
        })
        communes = pd.DataFrame({
            "region_code": ["1"],
            "total_population": [0],
            "num_communes": [0],
        })
        result = compute_region_stats(budgets, communes)
        assert len(result) == 1
        # Should not be infinity
        assert result.iloc[0]["revenue_per_capita"] == 100_000.0
