"""
Lissage gaussien de densité établissements / population sur grille carroyée.

Inspiration : https://www.icem7.fr/cartographie/les-lignes-de-force-du-vote-rn-en-2024/

Formule (pour chaque cellule x de la grille de sortie) :
    densité(x) = 1000 × Σ_i w(d_i) × store_weight_i
                         ───────────────────────────────
                         Σ_j w(d_j) × pop_j

avec w(d) = exp(−d² / (2σ²)),  σ = rayon / SIGMA_FACTOR (défaut : rayon / 3).

Résultat : établissements lissés pour 1 000 habitants.

Optimisations :
  · KDTree (cKDTree scipy) — O(log N) par requête, groupées par chunk
  · distances au carré — évite sqrt inutile avant d'élever au carré
  · globals COW fork — les gros tableaux numpy ne sont jamais picklés
  · multiprocessing.Pool — parallélise sur les cellules de sortie
  · float32 — réduit l'empreinte mémoire des coordonnées
"""
from __future__ import annotations

import os
from multiprocessing import Pool, cpu_count
from pathlib import Path

import numpy as np
import geopandas as gpd
from scipy.spatial import KDTree


# ── constantes ─────────────────────────────────────────────────────────────────

SIGMA_FACTOR = 3.0    # σ = rayon / SIGMA_FACTOR
CHUNK_SIZE   = 6_000  # cellules par tâche worker
TARGET_CRS   = 2154   # Lambert-93 (mètres)


# ── globals partagés via fork COW ──────────────────────────────────────────────
# Peuplés dans gaussian_blur() AVANT la création du Pool pour bénéficier du
# copy-on-write Linux : aucune sérialisation des gros tableaux numpy.

_store_tree:   KDTree     | None = None
_pop_tree:     KDTree     | None = None
_store_coords: np.ndarray | None = None  # (M, 2) float32
_store_w:      np.ndarray | None = None  # (M,)   float32  poids par établissement
_pop_coords:   np.ndarray | None = None  # (N, 2) float32
_pop_values:   np.ndarray | None = None  # (N,)   float64  population
_out_coords:   np.ndarray | None = None  # (P, 2) float32  cellules de sortie
_radius:       float = 0.0
_sigma2:       float = 0.0              # σ² précalculé


# ── worker ─────────────────────────────────────────────────────────────────────

def _worker(indices: np.ndarray) -> np.ndarray:
    """Calcule la densité lissée pour un sous-ensemble de cellules de sortie."""
    xy_chunk = _out_coords[indices]  # type: ignore[index]

    # requêtes groupées sur tout le chunk (plus rapide qu'une à une)
    store_nbrs = _store_tree.query_ball_point(xy_chunk, _radius)  # type: ignore[union-attr]
    pop_nbrs   = _pop_tree.query_ball_point(xy_chunk, _radius)    # type: ignore[union-attr]

    results = np.empty(len(indices), dtype=np.float64)

    for k in range(len(indices)):
        xy = xy_chunk[k]

        # ── numérateur : établissements lissés ───────────────────────────────
        idx_s = store_nbrs[k]
        if idx_s:
            diff = _store_coords[idx_s] - xy  # type: ignore[index]
            d2   = (diff * diff).sum(axis=1)
            w    = np.exp(-0.5 * d2 / _sigma2)
            num  = (w * _store_w[idx_s]).sum()  # type: ignore[index]
        else:
            num = 0.0

        # ── dénominateur : population lissée ─────────────────────────────────
        idx_p = pop_nbrs[k]
        if idx_p:
            diff  = _pop_coords[idx_p] - xy  # type: ignore[index]
            d2    = (diff * diff).sum(axis=1)
            w     = np.exp(-0.5 * d2 / _sigma2)
            denom = (w * _pop_values[idx_p]).sum()  # type: ignore[index]
        else:
            denom = 0.0

        results[k] = num / denom if denom > 0 else np.nan

    return results


# ── helpers ────────────────────────────────────────────────────────────────────

def _load(src: gpd.GeoDataFrame | str | Path) -> gpd.GeoDataFrame:
    if isinstance(src, (str, Path)):
        src = gpd.read_parquet(src)
    if src.crs is None or src.crs.to_epsg() != TARGET_CRS:
        src = src.to_crs(epsg=TARGET_CRS)
    return src


def _centroids_f32(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Centroïdes en float32 contigu (réduit l'empreinte mémoire)."""
    c = gdf.geometry.centroid
    return np.ascontiguousarray(
        np.column_stack([c.x.to_numpy(np.float64), c.y.to_numpy(np.float64)]),
        dtype=np.float32,
    )


# ── API publique ───────────────────────────────────────────────────────────────

def gaussian_blur(
    grid_pop: gpd.GeoDataFrame | str | Path,
    grid_stores: gpd.GeoDataFrame | str | Path,
    radius: float,
    *,
    sigma: float | None = None,
    population_col: str = "ind",
    store_weight_col: str | None = None,
    n_workers: int | None = None,
    out: str | Path | None = None,
) -> gpd.GeoDataFrame:
    """
    Lissage gaussien de la densité d'établissements pondérée par la population.

    Parameters
    ----------
    grid_pop : GeoDataFrame ou chemin geoparquet
        Grille carroyée avec colonne population (carreaux 1 km INSEE).
    grid_stores : GeoDataFrame ou chemin parquet/geoparquet
        Positions des établissements. Chaque ligne = 1 établissement
        (géométrie point) ou cellule avec un compte (+ store_weight_col).
    radius : float
        Rayon de lissage en mètres (ex. 10_000 pour 10 km).
    sigma : float, optional
        Écart-type du noyau. Défaut : radius / 3.
    population_col : str
        Colonne population dans grid_pop. Défaut : "ind".
    store_weight_col : str, optional
        Colonne poids dans grid_stores. Si None, chaque ligne pèse 1.
    n_workers : int, optional
        Nombre de processus. Défaut : tous les cœurs CPU.
    out : str ou Path, optional
        Chemin de sauvegarde du résultat en geoparquet.

    Returns
    -------
    GeoDataFrame
        Même géométrie que grid_pop avec colonne ``density``
        (établissements lissés pour 1 000 habitants).
    """
    global _store_tree, _pop_tree
    global _store_coords, _store_w, _pop_coords, _pop_values, _out_coords
    global _radius, _sigma2

    sigma     = radius / SIGMA_FACTOR if sigma is None else sigma
    n_workers = n_workers or cpu_count()

    # ── chargement ─────────────────────────────────────────────────────────────
    print(f"[blur] Chargement des données…")
    gdf_pop    = _load(grid_pop)
    gdf_stores = _load(grid_stores)

    # ── préparation des tableaux ───────────────────────────────────────────────
    _out_coords   = _centroids_f32(gdf_pop)
    _store_coords = _centroids_f32(gdf_stores)
    _pop_coords   = _out_coords  # pop et sortie sur la même grille

    _pop_values = gdf_pop[population_col].to_numpy(np.float64)
    _store_w    = (
        gdf_stores[store_weight_col].to_numpy(np.float32)
        if store_weight_col is not None
        else np.ones(len(gdf_stores), dtype=np.float32)
    )

    _radius = float(radius)
    _sigma2 = float(sigma) ** 2

    # ── KDTrees (construits une seule fois, partagés via fork COW) ─────────────
    print(f"[blur] KDTree stores  ({len(_store_coords):>10,} pts)…")
    _store_tree = KDTree(_store_coords)
    print(f"[blur] KDTree pop     ({len(_pop_coords):>10,} pts)…")
    _pop_tree   = KDTree(_pop_coords)

    # ── découpage en chunks ────────────────────────────────────────────────────
    n_out   = len(_out_coords)
    indices = np.arange(n_out)
    chunks  = [indices[i : i + CHUNK_SIZE] for i in range(0, n_out, CHUNK_SIZE)]
    print(
        f"[blur] Lissage : {n_out:,} cellules — "
        f"{len(chunks)} chunks — {n_workers} workers — "
        f"rayon {radius/1000:.1f} km — σ {sigma/1000:.2f} km"
    )

    # ── traitement parallèle ───────────────────────────────────────────────────
    raw = np.empty(n_out, dtype=np.float64)

    with Pool(processes=n_workers) as pool:
        done = 0
        for chunk, result in zip(chunks, pool.imap(_worker, chunks)):
            raw[chunk] = result
            done += len(chunk)
            print(f"\r[blur] {done:>10,} / {n_out:,} cellules traitées", end="", flush=True)

    print()

    # ── assemblage ─────────────────────────────────────────────────────────────
    gdf_out = gdf_pop[["geometry"]].copy()
    gdf_out["density"] = raw * 1_000  # établissements pour 1 000 habitants

    if out is not None:
        os.makedirs(Path(out).parent, exist_ok=True)
        gdf_out.to_parquet(out)
        print(f"[blur] ✓ Sauvegardé → {out}")

    return gdf_out


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Lissage gaussien densité établissements / population"
    )
    p.add_argument("--pop",     default="./data/processed/pop_carr_full_grid.geoparquet",
                   help="Grille population (geoparquet)")
    p.add_argument("--stores",  default="./data/processed/sirene_data.parquet",
                   help="Positions établissements (parquet/geoparquet)")
    p.add_argument("--radius",  type=float, default=10_000,
                   help="Rayon de lissage en mètres (défaut : 10 000 m)")
    p.add_argument("--sigma",   type=float, default=None,
                   help="σ du noyau gaussien (défaut : rayon/3)")
    p.add_argument("--pop-col", default="ind",
                   help="Colonne population dans la grille (défaut : ind)")
    p.add_argument("--store-weight-col", default=None,
                   help="Colonne poids par établissement (optionnel)")
    p.add_argument("--out",     default="./data/processed/gaussian_blur.geoparquet",
                   help="Fichier de sortie (geoparquet)")
    p.add_argument("--workers", type=int, default=None,
                   help="Nombre de processus (défaut : tous les cœurs)")
    args = p.parse_args()

    gaussian_blur(
        args.pop,
        args.stores,
        args.radius,
        sigma=args.sigma,
        population_col=args.pop_col,
        store_weight_col=args.store_weight_col,
        n_workers=args.workers,
        out=args.out,
    )
