"""
Carte simple de la population francaise à petite résolution
"""
import geopandas as gpd
import matplotlib.pyplot as plt


def read_file(path:str = "./data/processed/pop_carr_full_grid.geoparquet") -> gpd.GeoDataFrame :# type: ignore

    return gpd.read_parquet(path)

def plot_population_map(gdf: gpd.GeoDataFrame) -> None:

    fig, ax = plt.subplots(figsize=(10, 10))
    gdf.plot(column="population", ax=ax, legend=True, cmap="viridis", edgecolor="none")
    ax.set_title("Population par carreau de 1km² en France")
    ax.set_axis_off()
    plt.show()