"""Data cleaning and normalization utilities."""

from __future__ import annotations

import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip, and snake_case column names."""
    df = df.copy()
    df.columns = [re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_") for col in df.columns]
    return df


def drop_duplicates(df: pd.DataFrame, subset: list[str] | None = None) -> pd.DataFrame:
    """Remove duplicate rows."""
    before = len(df)
    df = df.drop_duplicates(subset=subset)
    removed = before - len(df)
    if removed:
        logger.info("Removed %d duplicate rows", removed)
    return df


def fill_missing_numeric(df: pd.DataFrame, value: float = 0.0) -> pd.DataFrame:
    """Fill NaN in numeric columns with a default value."""
    numeric_cols = df.select_dtypes(include="number").columns
    df = df.copy()
    df[numeric_cols] = df[numeric_cols].fillna(value)
    return df


def strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from string columns."""
    df = df.copy()
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in str_cols:
        df[col] = df[col].str.strip()
    return df


def coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Force columns to numeric, coercing errors to NaN."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def clean_dataframe(
    df: pd.DataFrame,
    dedup_subset: list[str] | None = None,
    numeric_fill: float = 0.0,
) -> pd.DataFrame:
    """Run the full cleaning pipeline on a DataFrame."""
    df = normalize_columns(df)
    df = strip_strings(df)
    df = drop_duplicates(df, subset=dedup_subset)
    df = fill_missing_numeric(df, value=numeric_fill)
    logger.info("Cleaning complete: %d rows x %d cols", len(df), len(df.columns))
    return df
