"""Prépare la données de population carroyée"""
import os
import pandas as pd
from shapely.geometry import Polygon
import geopandas as gpd

def read_data(path="./data/raw/carreaux_1km_met.csv")-> pd.DataFrame:
    
    if not os.path.exists(path):
        raise FileNotFoundError("Télécharger les données INSEE sur https://www.insee.fr/fr/statistiques/7655464?sommaire=7655515")
    
    return pd.read_csv(path)

def idinspire_to_geom(id_inspire : str) -> Polygon:
    """ 
    idcar_1km : Indentifiant Inspire du carreau
    Qui se décompose de la manière suivante : « CRS » pour « coordinate reference system » 
    + code_crs (code projection EPSG) 
    + « RES » pour « résolution » + « 200m / 1000m » 
    + « N » pour Nord + coordonnée_y_coin_inférieur_gauche
    + « E » pour Est + coordonnée_x_coin_inférieur_gauche.

    ex : CRS3035RES1000mN2029000E4252000

    Après vérif ils sont tous en crs 3035 LAEA qui est métrique
    """

    # on split la string pour extraire les coordonnées
    parts = id_inspire.split("RES")
    coords_part = parts[1].split("m")[1]  # on prend la partie après "RES1000m"
    
    # on split à nouveau pour séparer les coordonnées nord et est
    north_part, east_part = coords_part.split("E")
    
    # on extrait les valeurs numériques
    north = int(north_part.replace("N", ""))
    east = int(east_part)
    
    # on crée un polygone carré de 1km x 1km à partir des coordonnées du coin inférieur gauche
    return Polygon([(east, north), (east + 1000, north), (east + 1000, north + 1000), (east, north + 1000)])

def keep_first_commune(lcog_geo:int) -> str:
    """ 
    Il y a plusieurs codes géo par carreaux, triés par surface d'intersection décroissante/
    On garde la première
    """
    return str(lcog_geo)[:5]

def clean_population_data() -> gpd.GeoDataFrame:
    """ 
    Nettoie les données de population carroyée en créant une géométrie à partir de l'identifiant Inspire.
    """
    df = read_data()

    # trouve la géométrie des carreaux 
    df["geometry"] = df["idcar_1km"].apply(idinspire_to_geom) # type: ignore
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:3035")

    # reprojette en Lambert 93 pour être compatible avec les autres données
    gdf = gdf.to_crs(epsg=2154)


    gdf["lcog_geo"] = gdf["lcog_geo"].apply(keep_first_commune)

    return gdf

if __name__ == "__main__":
    gdf = clean_population_data()
    path = "./data/processed/population_carroyée.geoparquet"
    gdf.to_parquet(path, index=False)