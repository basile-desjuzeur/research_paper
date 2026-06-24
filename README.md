# Projet de Recherche FoodBiome

Le but de ce projet est de proposer une méthodologie pour diagnostiquer la répartition d'entreprises agro-alimentaires au sens large sur le territoire de France métropolitaine.

## Reproducibilité

Pour reproduire les résultats, il est nécessaire de suivre les étapes suivantes :
1. Cloner le dépôt GitHub 
2. Installer les dépendances avec ```uv install```


## Données

| Données | Source | Emplacement |
|---|---|---|
| Population carroyée (1 km) | [lien](https://www.insee.fr/fr/statistiques/7655464?sommaire=7655515) | [carreaux_1km_met.csv](./data/raw/carreaux_1km_met.csv) |
| Grille 1 km complète | [lien](https://www.insee.fr/fr/statistiques/6214726#consulter) | [grille200m_metropole.gpkg](data/raw/grille200m_gpkg/grille200m_metropole_gpkg/grille200m_metropole.gpkg) |
| Répertoire Sirene | [API](https://portail-api.insee.fr/catalog/api/2ba0e549-5587-3ef1-9082-99cd865de66f/doc?page=1383565d-39b7-4379-8356-5d39b723798e#variables-non-historis%C3%A9es) | ?|
| Géométrie des régions | [lien](https://www.data.gouv.fr/api/1/datasets/r/aa76860a-51af-4744-a593-4c19af2570b8) | [regions-100m.geojson](./data/raw/regions-100m.geojson) |

Le retraitement des données a été fait dans [src/data](./src/data/) est reproductible avec le point d'entrée [src/data/make_dataset.py](./src/data/make_dataset.py).

Il faut lancer :
```python
python src/data/make_dataset.py
```

## Identification des zones prioritaires 

Le rendu visuel est fait par lissage gaussien sur les données pour créer une carte bivariée.

## Caractérisation des zones prioritaires


Winsorisation ?
Le doc INSEE donne :

- niveau de vie
- dynamique de construction de logements
- surtout les vieux ?


Entrainement d'un algo sur ces données : classif est_prio puis analyse post-hoc de l'algo.
