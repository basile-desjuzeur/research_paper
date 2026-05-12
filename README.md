# Projet de Recherche FoodBiome


## Données

| Données | Source | Emplacement |
| Population carroyée (1 km) | https://www.insee.fr/fr/statistiques/7655464?sommaire=7655515 | data/raw/carreaux_1km_met.csv |


1. 

idcar_1km : Indentifiant Inspire du carreau

qui se décompose de la manière suivante : « CRS » pour « coordinate reference system » + code_crs (code projection EPSG) + « RES » pour « résolution » + « 200m / 1000m » + « N » pour Nord + coordonnée_y_coin_inférieur_gauche + « E » pour Est + coordonnée_x_coin_inférieur_gauche.

Population française sur des carreaux de 1km (autres = 200m : pas pertinent, niveau naturel = hétérogène).
Une partie des valeurs ont été imputées.
Potentiellement plusieurs communes (lcog_geo)
Nombre d'individus


Winsorisation


## Caractérisation des zones sous dotées

Le doc INSEE donne :

- niveau de vie
- dynamique de construction de logements
- surtout les vieux ?

