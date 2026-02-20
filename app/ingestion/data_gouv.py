"""Ingestion module for data.gouv.fr public API.

Handles dataset discovery, metadata retrieval, and CSV download.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://www.data.gouv.fr/api/1"

# Well-known dataset slugs used in the demo pipeline
DATASETS = {
    "region_budgets": "comptes-individuels-des-regions-fichier-global-a-compter-de-2008",
    "communes": "communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather",
    "chomage_regional": "masse-salariale-et-assiette-chomage-partiel-mensuelles-du-secteur-prive-par-region",
}

# Timeouts (connect, read) in seconds
TIMEOUT = httpx.Timeout(15.0, read=120.0)


def search_datasets(query: str, page_size: int = 20) -> list[dict[str, Any]]:
    """Search datasets on data.gouv.fr.

    Returns a list of lightweight dataset dicts (id, title, slug, description).
    """
    url = f"{BASE_URL}/datasets/"
    params = {"q": query, "page_size": page_size}
    resp = httpx.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    return [
        {
            "id": ds["id"],
            "title": ds["title"],
            "slug": ds["slug"],
            "description": (ds.get("description") or "")[:300],
            "organization": (ds.get("organization") or {}).get("name"),
            "last_modified": ds.get("last_modified"),
            "license": ds.get("license"),
        }
        for ds in payload.get("data", [])
    ]


def get_dataset_metadata(slug_or_id: str) -> dict[str, Any]:
    """Fetch full metadata for a single dataset."""
    url = f"{BASE_URL}/datasets/{slug_or_id}/"
    resp = httpx.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def list_csv_resources(dataset_meta: dict) -> list[dict[str, str]]:
    """Extract CSV resource entries from dataset metadata."""
    resources = dataset_meta.get("resources", [])
    return [
        {
            "id": r["id"],
            "title": r.get("title", ""),
            "url": r["url"],
            "format": r.get("format", ""),
            "filesize": r.get("filesize"),
        }
        for r in resources
        if (r.get("format") or "").lower() == "csv"
    ]


def download_csv(url: str, sep: str | None = None) -> pd.DataFrame:
    """Download a CSV file and return it as a DataFrame.

    Automatically detects the separator if not provided.
    """
    logger.info("Downloading CSV from %s", url)
    resp = httpx.get(url, follow_redirects=True, timeout=TIMEOUT)
    resp.raise_for_status()

    raw = resp.text
    if sep is None:
        first_line = raw.split("\n", maxsplit=1)[0]
        sep = ";" if first_line.count(";") > first_line.count(",") else ","

    df = pd.read_csv(io.StringIO(raw), sep=sep, low_memory=False)
    logger.info("Downloaded %d rows x %d columns", len(df), len(df.columns))
    return df


def download_resource(resource_id: str, sep: str | None = None) -> pd.DataFrame:
    """Download a resource by its ID using the stable redirect URL."""
    url = f"{BASE_URL}/datasets/r/{resource_id}"
    return download_csv(url, sep=sep)


# ---------------------------------------------------------------------------
# High-level helpers for the demo pipeline
# ---------------------------------------------------------------------------


def ingest_region_budgets() -> pd.DataFrame:
    """Download the regional budget dataset CSV."""
    meta = get_dataset_metadata(DATASETS["region_budgets"])
    csv_resources = list_csv_resources(meta)
    if not csv_resources:
        raise RuntimeError("No CSV resource found for region budgets dataset")
    return download_csv(csv_resources[0]["url"], sep=";")


def ingest_communes() -> pd.DataFrame:
    """Download the communes demographics dataset CSV."""
    meta = get_dataset_metadata(DATASETS["communes"])
    csv_resources = list_csv_resources(meta)
    if not csv_resources:
        raise RuntimeError("No CSV resource found for communes dataset")
    return download_csv(csv_resources[0]["url"], sep=",")


def ingest_chomage_regional() -> pd.DataFrame:
    """Download the regional unemployment / salary mass dataset CSV."""
    meta = get_dataset_metadata(DATASETS["chomage_regional"])
    csv_resources = list_csv_resources(meta)
    if not csv_resources:
        raise RuntimeError("No CSV resource found for chomage regional dataset")
    return download_csv(csv_resources[0]["url"], sep=";")
