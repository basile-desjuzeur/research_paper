"""
Les données carroyées fournies par l'insee ne couvrent pas tout le territoire.
Pour résoudre ça, on enrichit avec le carroyage INSEE fournit sans données.
Ce carroyage est à l'échelle 200 mètres donc on le met à la bonne échelle. 
"""
import os
import geopandas as gpd
import re
from shapely.geometry import box
import numpy as np
from shapely import box as shapely_box


def read_data(path="/mnt/421C392D1C391D7B/main/Projets/agri/data/raw/grille200m_gpkg/grille200m_metropole_gpkg/grille200m_metropole.gpkg") -> gpd.GeoDataFrame: # type: ignore

    if not os.path.exists(path):
        raise FileNotFoundError("Télécharger le fichier gpkg sur https://www.insee.fr/fr/statistiques/6214726#consulter \n Puis le décompresser")
    
    return gpd.read_file(path)

def make_grid_1km(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Extraire les coords directement depuis la string avec str.extract (vectorisé)
    coords = (
        df["id_carr_1km"]
        .drop_duplicates()
        .str.extract(r"N(\d+)E(\d+)")
        .astype(np.int32)
        .rename(columns={0: "y_min", 1: "x_min"})
    )
    
    # Construire les 4 coords des bbox en numpy
    x_min = coords["x_min"].to_numpy()
    y_min = coords["y_min"].to_numpy()
    
    # shapely.box accepte des arrays numpy directement (vectorisé, pas de boucle)
    geoms = shapely_box(x_min, y_min, x_min + 1000, y_min + 1000)
    
    return gpd.GeoDataFrame(
        {"id_carr_1km": coords.index},  # ou reset_index si besoin
        geometry=geoms,
        crs="EPSG:3035"
    )


def clean_complete_grid() -> gpd.GeoDataFrame : #type: ignore

    gdf = read_data()
    return make_grid_1km(gdf)


if __name__ == "__main__":

    gdf = clean_complete_grid()
    gdf.to_parquet("../data/processed/full_1km_grid.parquet", index=False)