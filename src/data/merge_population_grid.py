"""
Porte les données de population sur une grille complète.
"""
import pandas as pd
import geopandas as gpd

OUT = "./data/processed/pop_carr_full_grid.geoparquet"

def read_files() -> (gpd.GeoDataFrame, gpd.GeoDataFrame) :#type: ignore

    gdf_grid = gpd.read_parquet("./data/processed/full_1km_grid.geoparquet")
    gdf_pop = gpd.read_parquet("./data/processed/population_carroyée.geoparquet")

    return gdf_grid, gdf_pop


def merge_gdfs(gdf_grid, gdf_pop) -> gpd.GeoDataFrame : #type: ignore

    return pd.merge(gdf_grid, gdf_pop, left_on=["id_carr_1km"], right_on=["idcar_1km"], how="left", suffixes=("_ref", "_pop")) #type: ignore

def fillna_by_dtype(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Numériques → 0
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)
    
    # Strings/object → "inconnu"
    str_cols = df.select_dtypes(include="str").columns
    df[str_cols] = df[str_cols].fillna("inconnu")
    
    # Catégorielles → mode
    cat_cols = df.select_dtypes(include="category").columns
    for col in cat_cols:
        df[col] = df[col].fillna(df[col].mode()[0])

    return df


def drop_rename_cols(gdf) -> gpd.GeoDataFrame: #type: ignore
    
    gdf.drop(columns=["geometry_pop", "idcar_1km"], inplace=True)
    gdf.rename(columns={"geometry_ref":"geometry"}, inplace=True)

    return gdf.set_geometry("geometry")

def save_file(gdf : gpd.GeoDataFrame, path:str =OUT)->None:

    gdf.to_parquet(OUT, index=False)

def merge_population_grid() -> None:
    gdf_grid, gdf_pop = read_files()
    gdf = (
        merge_gdfs(gdf_grid, gdf_pop)
        .pipe(drop_rename_cols)
        .pipe(fillna_by_dtype)
    )
    save_file(gdf) # pyright: ignore[reportArgumentType]

if __name__ == "__main__":
    merge_population_grid()