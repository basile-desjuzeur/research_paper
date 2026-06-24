"""
Récupère les données de l'API Sirene et les stocke dans un fichier parquet.
Pagination par curseur (recommandée par l'INSEE pour >1000 résultats).
"""
import json
import time
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape

CODES_NAF = ["47.11Z", "47.19B"]
GEOMETRY_FILTER: gpd.GeoDataFrame | None = None
OUT = "./data/processed/sirene_data.parquet"

URL  = "https://api.insee.fr/entreprises/sirene/V3/siret"
# Champs retournés : siret, siren, naf, coordonnées lon/lat
CHAMPS = ",".join([
    "siret",
    "siren",
    "activitePrincipaleEtablissement",   # code NAF établissement
    "activitePrincipaleUniteLegale",      # code NAF unité légale (fallback)
    "longitudeEtablissement",
    "latitudeEtablissement",
])
NOMBRE   = 1000   # max par page
RATE_LIMIT_DELAY = 2.0  # secondes entre requêtes (limite : 30 req/min)


def get_api_key() -> str:
    with open("./credentials/credentials.json") as f:
        return json.load(f)["cle_sirene"]


def _build_query(codes_naf: list[str]) -> str:
    """Construit la query Solr : établissements actifs avec les codes NAF demandés."""
    naf_filter = " OR ".join([
        f"activitePrincipaleEtablissement:{code.replace('.', '')}"
        for code in codes_naf
    ])
    # periode() → filtre sur la période courante (état actif)
    return f"periode(etatAdministratifEtablissement:A) AND periode({naf_filter})"


def _fetch_page(query: str, cursor: str, headers: dict) -> dict:
    """Fetch une page de résultats, retourne le JSON brut."""
    params = {
        "q":       query,
        "champs":  CHAMPS,
        "nombre":  NOMBRE,
        "curseur": cursor,
    }
    response = requests.get(URL, headers=headers, params=params, timeout=30)

    if response.status_code == 404:
        print(response.text)
        return {"header": {"total": 0}, "etablissements": []}

    response.raise_for_status()
    return response.json()


def _parse_etablissements(etablissements: list[dict]) -> list[dict]:
    """Extrait les champs utiles d'une liste d'établissements."""
    records = []
    for etab in etablissements:
        lon = etab.get("longitudeEtablissement")
        lat = etab.get("latitudeEtablissement")
        if lon is None or lat is None:
            continue  # pas de géolocalisation → on ignore

        # periodes → prendre la plus récente pour le NAF
        periodes = etab.get("periodesEtablissement", [{}])
        naf = periodes[0].get("activitePrincipaleEtablissement") if periodes else None

        records.append({
            "siret":   etab.get("siret"),
            "siren":   etab.get("siren"),
            "naf":     naf or etab.get("activitePrincipaleUniteLegale"),
            "lon":     float(lon),
            "lat":     float(lat),
        })
    return records


def retrieve_sirene_data(
    codes_naf: list[str] = CODES_NAF,
    geometry_filter: gpd.GeoDataFrame | None = GEOMETRY_FILTER,
) -> gpd.GeoDataFrame:
    """
    Récupère tous les établissements actifs pour les codes NAF donnés.
    Si geometry_filter est fourni (GeoDataFrame), filtre les points dans la géométrie.
    Pagination automatique par curseur INSEE.
    """
    headers = {
        "Accept":        "application/json",
        "Authorization": f"Bearer {get_api_key()}",
    }
    query   = _build_query(codes_naf)
    cursor  = "*"
    records = []

    # Préparer le filtre géométrique (union de toutes les géométries)
    geom_filter = geometry_filter.geometry.unary_union if geometry_filter is not None else None

    print(f"Requête : {query}")

    while True:
        data = _fetch_page(query, cursor, headers)
        header = data.get("header", {})

        if not records:  # première page
            print(f"Total estimé : {header.get('total', '?')} établissements")

        page_records = _parse_etablissements(data.get("etablissements", []))
        records.extend(page_records)
        print(f"  {len(records)} récupérés...", end="\r")

        cursor_suivant = header.get("curseurSuivant")
        # Condition d'arrêt : plus de résultats ou curseur identique
        if not cursor_suivant or cursor_suivant == cursor:
            break

        cursor = cursor_suivant
        time.sleep(RATE_LIMIT_DELAY)  # respect rate limit 30 req/min

    print(f"\n✓ {len(records)} établissements récupérés")

    if not records:
        return gpd.GeoDataFrame(columns=["siret", "siren", "naf", "geometry"], crs="EPSG:4326")

    df  = pd.DataFrame(records)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(row.lon, row.lat) for row in df.itertuples()],
        crs="EPSG:4326",
    )

    # Filtre géométrique post-API (l'API Sirene ne supporte pas le filtre polygone)
    if geom_filter is not None:
        gdf = gdf[gdf.geometry.within(geom_filter)].reset_index(drop=True)
        print(f"  → {len(gdf)} après filtre géométrique")

    return gdf


def save_file(gdf: gpd.GeoDataFrame, path: str = OUT) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    gdf.to_parquet(path, index=False)
    print(f"✓ Sauvegardé dans {path}")


def retrieve_and_save(
    codes_naf: list[str] = CODES_NAF,
    geometry_filter: gpd.GeoDataFrame | None = GEOMETRY_FILTER,
    out: str = OUT,
) -> None:
    gdf = retrieve_sirene_data(codes_naf, geometry_filter)
    save_file(gdf, out)


if __name__ == "__main__":
    retrieve_and_save()