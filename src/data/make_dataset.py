"""
Entrypoint pour le retraitement des données brutes en données prêtes à l'emploi pour les modèles de machine learning.
Exécute séquentiellement les scripts de nettoyage et de transformation des données, puis stocke les résultats dans le dossier data/processed.
"""

import os

from src.data.clean_population_data import clean_population_data
from src.data.clean_complete_grid import clean_complete_grid
from src.data.retrieve_sirene_data import retrieve_sirene_data
from src.data.merge_population_grid import merge_population_grid


if __name__ == "__main__":
    os.makedirs("./data/processed", exist_ok=True)

    # Récupère les données de population carroyée et les données Sirene
    clean_population_data()
    clean_complete_grid()
    merge_population_grid()
