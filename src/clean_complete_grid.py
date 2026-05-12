"""
Les données carroyées fournies par l'insee ne couvrent pas tout le territoire.
Pour résoudre ça, on enrichit avec le carroyage INSEE fournit sans données.
Ce carroyage est à l'échelle 200 mètres donc on le met à la bonne échelle.
"""
import os
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely import box as shapely_box
import fiona
import pyarrow as pa
import pyarrow.parquet as pq

PATH       = "./data/raw/grille200m_gpkg/grille200m_metropole_gpkg/grille200m_metropole.gpkg"
OUT        = "./data/processed/full_1km_grid.parquet"
CHUNK_SIZE = 500_000


def _ids_to_grid(ids: pd.Series) -> gpd.GeoDataFrame:
    """Reconstruit les carreaux 1km depuis les identifiants INSPIRE (vectorisé)."""
    coords = (
        ids.drop_duplicates()
        .str.extract(r"N(\d+)E(\d+)")
        .astype(np.int32)
        .rename(columns={0: "y_min", 1: "x_min"})
    )
    x_min = coords["x_min"].to_numpy()
    y_min = coords["y_min"].to_numpy()
    geoms = shapely_box(x_min, y_min, x_min + 1000, y_min + 1000)
    return gpd.GeoDataFrame(
        {"id_carr_1km": ids.drop_duplicates().values},
        geometry=geoms,
        crs="EPSG:3035",
    )


def _iter_chunks(path: str, chunk_size: int):
    """Lit le gpkg par chunks, yield des Series d'id_carr_1km uniques."""
    seen = set()
    buffer = []

    with fiona.open(path) as src: # lazy pointeur vers le fichier gpkp (non chargé en ram) 
        # chaque ligne est chargée au fur et à mesure, une à la fois en RAM
        for feature in src:
            id_1km = feature["properties"]["id_carr_1km"] # strucrure des fichiers geojson en dict
            if id_1km in seen:
                continue
            seen.add(id_1km)
            buffer.append(id_1km)

            if len(buffer) >= chunk_size:
                # écriture par blocs de chunks_size
                yield pd.Series(buffer, dtype="string")
                buffer = []

    if buffer:
        yield pd.Series(buffer, dtype="string")


def clean_complete_grid(path: str = PATH, out: str = OUT, chunk_size: int = CHUNK_SIZE) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(
            "Télécharger le fichier gpkg sur https://www.insee.fr/fr/statistiques/6214726#consulter\n"
            "Puis le décompresser."
        )

    writer = None
    total = 0

    for chunk_ids in _iter_chunks(path, chunk_size):
        gdf = _ids_to_grid(chunk_ids)

        # Convertir geometry en WKB pour parquet
        table = pa.table({
            "id_carr_1km": gdf["id_carr_1km"].values,
            "geometry":    gdf["geometry"].to_wkb(),
        })

        if writer is None:
            writer = pq.ParquetWriter(out, table.schema)
        writer.write_table(table)
        total += len(gdf)
        print(f"  {total:,} carreaux écrits...", end="\r")

    if writer:
        writer.close()

    print(f"\n✓ {total:,} carreaux 1km écrits dans {out}")


if __name__ == "__main__":
    clean_complete_grid()