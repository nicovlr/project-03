"""GeoJSON and region code mapping for France choropleth maps."""

from __future__ import annotations

# URL of the official GeoJSON for French regions (IGN simplified)
REGIONS_GEOJSON_URL = (
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions.geojson"
)

# Mapping from region budget 3-digit codes (stripped of leading zeros)
# to region names as they appear in the GeoJSON (for matching).
# Also includes the 2-digit codes from the communes dataset.
REGION_CODE_TO_NAME = {
    # 3-digit budget codes (leading-zero-stripped)
    "1": "Guadeloupe",
    "2": "Martinique",
    "3": "Guyane",
    "4": "La Reunion",
    "6": "Mayotte",
    "11": "Ile-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comte",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhone-Alpes",
    "93": "Provence-Alpes-Cote d'Azur",
    "94": "Corse",
}
