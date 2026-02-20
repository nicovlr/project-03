"""Data transformation: aggregation and cross-joining of datasets."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Region budget helpers
# ---------------------------------------------------------------------------

# Mapping of common column names found in the region budget CSV.
# The raw CSV uses French abbreviations — we map them to English.
BUDGET_COLUMN_MAP = {
    "exer": "year",
    "reg": "region_code",
    "lbudg": "region_name",
    "rec_totales_f": "operating_revenue",
    "dep_totales_f": "operating_expenditure",
    "rec_totales_i": "investment_revenue",
    "dep_totales_i": "investment_expenditure",
    "encours_de_dette": "debt",
}


def transform_region_budgets(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and reshape the raw region budget DataFrame.

    Returns a DataFrame with one row per (year, region_code).
    """
    df = df.copy()

    # Rename known columns
    rename = {k: v for k, v in BUDGET_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    required = ["year", "region_code"]
    for col in required:
        if col not in df.columns:
            raise KeyError(f"Missing required column after rename: {col}")

    # Coerce types
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["region_code"] = df["region_code"].astype(str).str.strip().str.zfill(3)

    numeric_cols = [
        "operating_revenue",
        "operating_expenditure",
        "investment_revenue",
        "investment_expenditure",
        "debt",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Compute totals
    if "operating_revenue" in df.columns and "investment_revenue" in df.columns:
        df["total_revenue"] = df["operating_revenue"] + df["investment_revenue"]
    if "operating_expenditure" in df.columns and "investment_expenditure" in df.columns:
        df["total_expenditure"] = df["operating_expenditure"] + df["investment_expenditure"]

    # Clean region name
    if "region_name" in df.columns:
        df["region_name"] = (
            df["region_name"].str.replace(r"^REG\s+", "", regex=True).str.strip().str.title()
        )

    keep = [
        c
        for c in [
            "year",
            "region_code",
            "region_name",
            "total_revenue",
            "total_expenditure",
            "operating_revenue",
            "operating_expenditure",
            "investment_revenue",
            "investment_expenditure",
            "debt",
        ]
        if c in df.columns
    ]

    df = df[keep].dropna(subset=["year", "region_code"])
    df["year"] = df["year"].astype(int)
    logger.info("Transformed region budgets: %d rows", len(df))
    return df


# ---------------------------------------------------------------------------
# Communes helpers
# ---------------------------------------------------------------------------


def aggregate_communes_by_region(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate commune data to the region level.

    Returns a DataFrame with columns:
        region_code, region_name, total_population, num_communes
    """
    df = df.copy()

    # Try to detect the right column names (post-cleaning, they are snake_cased)
    code_col = _find_col(df, ["reg_code", "code_region", "region_code"])
    name_col = _find_col(df, ["reg_nom", "nom_region", "region_name"])
    pop_col = _find_col(df, ["population", "pop"])

    if code_col is None or pop_col is None:
        raise KeyError(
            f"Cannot find region code or population columns. Available: {list(df.columns)}"
        )

    df[pop_col] = pd.to_numeric(df[pop_col], errors="coerce").fillna(0).astype(int)
    df[code_col] = df[code_col].astype(str).str.strip()

    agg = (
        df.groupby(code_col)
        .agg(
            total_population=(pop_col, "sum"),
            num_communes=(pop_col, "count"),
            region_name=(name_col, "first") if name_col else (code_col, "first"),
        )
        .reset_index()
    )

    agg = agg.rename(columns={code_col: "region_code"})
    logger.info("Aggregated communes into %d regions", len(agg))
    return agg


# ---------------------------------------------------------------------------
# Cross-join: budget + demographics → per-capita stats
# ---------------------------------------------------------------------------


def compute_region_stats(
    budgets: pd.DataFrame,
    communes_agg: pd.DataFrame,
) -> pd.DataFrame:
    """Join budget data with demographics to produce per-capita KPIs.

    Both DataFrames must have a ``region_code`` column.
    ``budgets`` must have ``year``, ``total_revenue``, ``total_expenditure``.
    ``communes_agg`` must have ``total_population``, ``num_communes``.
    """
    # Normalize region codes — budget uses 3-digit, communes may use 2-digit
    budgets = budgets.copy()
    communes_agg = communes_agg.copy()

    budgets["region_code"] = budgets["region_code"].astype(str).str.strip().str.lstrip("0")
    communes_agg["region_code"] = (
        communes_agg["region_code"].astype(str).str.strip().str.lstrip("0")
    )

    merged = budgets.merge(
        communes_agg[["region_code", "total_population", "num_communes"]],
        on="region_code",
        how="inner",
    )

    if merged.empty:
        logger.warning("Cross-join produced 0 rows — check region_code alignment")
        return merged

    merged["revenue_per_capita"] = (
        merged["total_revenue"] / merged["total_population"].replace(0, 1)
    ).round(2)
    merged["expenditure_per_capita"] = (
        merged["total_expenditure"] / merged["total_population"].replace(0, 1)
    ).round(2)

    keep = [
        "year",
        "region_code",
        "region_name",
        "total_population",
        "total_revenue",
        "total_expenditure",
        "revenue_per_capita",
        "expenditure_per_capita",
        "num_communes",
    ]
    merged = merged[[c for c in keep if c in merged.columns]]
    logger.info("Region stats computed: %d rows", len(merged))
    return merged


# ---------------------------------------------------------------------------
# Employment / salary mass helpers
# ---------------------------------------------------------------------------

EMPLOYMENT_COLUMN_MAP = {
    "region": "region_name",
    "code_region": "region_code",
    "dernier_jour_du_mois": "month_date",
    "masse_salariale_brute": "salary_mass",
    "glissement_annuel_masse_salariale": "salary_yoy_change",
    "assiette_chomage_partiel": "partial_unemployment_base",
    "part_de_l_assiette_chomage_partiel": "partial_unemployment_share",
}


def transform_employment(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the regional employment/salary mass DataFrame.

    Returns a DataFrame with columns:
        region_code, region_name, month, salary_mass,
        salary_yoy_change, partial_unemployment_base, partial_unemployment_share
    """
    df = df.copy()

    rename = {k: v for k, v in EMPLOYMENT_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Detect region code and name columns
    code_col = _find_col(df, ["region_code", "code_region"])
    name_col = _find_col(df, ["region_name", "region", "nom_region"])

    if code_col and code_col != "region_code":
        df = df.rename(columns={code_col: "region_code"})
    if name_col and name_col != "region_name":
        df = df.rename(columns={name_col: "region_name"})

    # Extract YYYY-MM from date column
    date_col = _find_col(df, ["month_date", "dernier_jour_du_mois"])
    if date_col:
        df["month"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m")
    elif "month" not in df.columns:
        logger.warning("No date column found in employment data")
        return pd.DataFrame()

    # Coerce numeric columns
    for col in [
        "salary_mass",
        "salary_yoy_change",
        "partial_unemployment_base",
        "partial_unemployment_share",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "region_code" in df.columns:
        df["region_code"] = df["region_code"].astype(str).str.strip()

    keep = [
        c
        for c in [
            "region_code",
            "region_name",
            "month",
            "salary_mass",
            "salary_yoy_change",
            "partial_unemployment_base",
            "partial_unemployment_share",
        ]
        if c in df.columns
    ]

    df = df[keep].dropna(subset=["month"])
    logger.info("Transformed employment data: %d rows", len(df))
    return df


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None
