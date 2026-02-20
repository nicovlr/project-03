"""Registry of available datasets and their configurations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DatasetConfig:
    name: str
    slug: str
    description: str
    csv_separator: str = ";"
    source: str = "data.gouv.fr"


DATASET_REGISTRY: dict[str, DatasetConfig] = {
    "region_budgets": DatasetConfig(
        name="Comptes individuels des regions",
        slug="comptes-individuels-des-regions-fichier-global-a-compter-de-2008",
        description="Budget regional : recettes, depenses, dette par region et par annee.",
        csv_separator=";",
        source="Ministere de l'Economie",
    ),
    "communes": DatasetConfig(
        name="Communes et villes de France",
        slug="communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather",
        description="Demographie communale : population, superficie, densite.",
        csv_separator=",",
        source="data.gouv.fr",
    ),
    "chomage_regional": DatasetConfig(
        name="Masse salariale et chomage partiel par region",
        slug="masse-salariale-et-assiette-chomage-partiel-mensuelles-du-secteur-prive-par-region",
        description="Masse salariale brute et assiette chomage partiel mensuelles par region.",
        csv_separator=";",
        source="Urssaf",
    ),
}
