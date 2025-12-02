# Configuration du Projet FilterMate pour Serena

## Informations Générales

**Nom du projet**: FilterMate  
**Type**: Plugin QGIS Python  
**Langage principal**: Python 3.x  
**Framework**: PyQt5, QGIS API  
**Base de données**: Spatialite (SQLite), PostgreSQL/PostGIS (optionnel)

---

## Architecture du Projet

### Structure des fichiers

```
filter_mate/
├── Core
│   ├── filter_mate.py              # Point d'entrée plugin QGIS
│   ├── filter_mate_app.py          # Application principale (1038 lignes)
│   ├── filter_mate_dockwidget.py   # Widget dock interface
│   └── filter_mate_dockwidget_base.py
│
├── Configuration
│   ├── config/
│   │   ├── config.json            # Configuration JSON principale
│   │   └── config.py              # Gestion configuration Python
│   └── metadata.txt               # Métadonnées plugin QGIS
│
├── Modules
│   ├── appTasks.py                # Tâches filtrage (1700+ lignes) 🔥
│   ├── appUtils.py                # Utilitaires connexion DB
│   ├── widgets.py                 # Widgets personnalisés UI
│   ├── customExceptions.py        # Exceptions métier
│   └── qt_json_view/              # Visualisation JSON (externe)
│
├── Ressources
│   ├── icons/                     # Icônes interface
│   ├── i18n/                      # Fichiers traduction
│   └── resources.qrc              # Ressources Qt
│
└── Documentation
    ├── README.md
    ├── LICENSE
    └── AUDIT_FILTERMATE.md        # Ce document d'audit
```

---

## Composants Clés

### 1. filter_mate_app.py
**Rôle**: Orchestrateur principal de l'application

**Classes principales**:
- `FilterMateApp`: Classe principale application
  - Gestion des tâches (filtrage, export, reset)
  - Initialisation base Spatialite
  - Gestion des événements QGIS
  - Configuration projet et couches

**Dépendances critiques**:
- QGIS API (`QgsProject`, `QgsVectorLayer`, `QgsApplication`)
- Spatialite (via `pyspatialite`)
- Configuration (`config.py`, `config.json`)

**Points d'attention**:
- Variable `project_datasources`: dictionnaire des sources de données par type
- Variable `app_postgresql_temp_schema_setted`: flag schéma PostgreSQL
- Fonction `init_filterMate_db()`: initialisation base Spatialite

### 2. modules/appTasks.py
**Rôle**: Gestion des tâches de filtrage asynchrones

**Classes principales**:
- `FilterTask(QgsTask)`: Tâche de filtrage asynchrone
  - Préparation requêtes spatiales
  - Gestion multi-sources (PostgreSQL/Spatialite/OGR)
  - Création vues matérialisées PostgreSQL
  - Filtrage géométrique

**Fonctions critiques pour migration sans PostgreSQL**:
- `prepare_postgresql_source_geom()`: ligne ~389 - À adapter
- `prepare_ogr_source_geom()`: ligne ~466 - Déjà fonctionnelle ✅
- `qgis_expression_to_postgis()`: ligne ~362 - À dupliquer pour Spatialite
- `execute_geometric_filtering()`: ligne ~519 - Logique conditionnelle
- Création vues matérialisées: lignes 1139, 1188, 1202, 1341 - À remplacer

**Variables d'état importantes**:
- `param_source_provider_type`: 'postgresql' | 'spatialite' | 'ogr'
- `postgresql_source_geom`: géométrie source PostgreSQL
- `spatialite_source_geom`: géométrie source Spatialite
- `ogr_source_geom`: géométrie source OGR

### 3. modules/appUtils.py
**Rôle**: Utilitaires de connexion et helpers

**Fonctions**:
- `get_datasource_connexion_from_layer(layer)`: Connexion PostgreSQL via psycopg2
- `get_data_source_uri(layer)`: Extraction URI source données
- `truncate(number, digits)`: Utilitaire mathématique

**⚠️ Import psycopg2 ligne 2**: À rendre conditionnel en priorité

### 4. config/config.py
**Rôle**: Initialisation variables d'environnement

**Fonctions**:
- `init_env_vars()`: Initialisation variables globales
- `merge(a, b)`: Fusion dictionnaires configuration

**Variables globales**:
```python
ENV_VARS = {
    "PROJECT": QgsProject.instance(),
    "PLATFORM": sys.platform,
    "DIR_CONFIG": chemin config,
    "PATH_ABSOLUTE_PROJECT": chemin projet,
    "CONFIG_DATA": données config.json,
    "QGIS_SETTINGS_PATH": chemin profil QGIS,
    "PLUGIN_CONFIG_DIRECTORY": chemin plugin FilterMate
}
```

---

## Base de Données Spatialite

### Localisation
```
C:\Users\simon\AppData\Roaming\QGIS\QGIS3\profiles\default\FilterMate\filterMate_db.sqlite
```

### Usage actuel
- Historique des subsets par couche
- Métadonnées du projet FilterMate
- Configuration des widgets par couche
- Peut être étendu pour remplacer PostgreSQL ✅

### Tables (à documenter via analyse DB)
- `project_metadata`: Métadonnées projet
- `layer_history`: Historique filtres par couche
- Autres tables à identifier

---

## Dépendances Python

### Requises
```python
# QGIS (fourni par QGIS)
from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

# Standard library
import os, sys, json, re, math
from functools import partial
```

### Optionnelles (à rendre optionnelles)
```python
# PostgreSQL - À RENDRE CONDITIONNEL
import psycopg2

# Spatialite - Déjà intégré QGIS
from pyspatialite import dbapi2 as spatialite  # ou sqlite3
```

---

## Patterns de Code

### Détection type de provider
```python
# Pattern utilisé dans le code
if layer.providerType() == 'postgres':
    layer_provider_type = 'postgresql'
elif layer.providerType() == 'spatialite':
    layer_provider_type = 'spatialite'
elif layer.providerType() == 'ogr':
    layer_provider_type = 'ogr'
```

### Logique conditionnelle par source
```python
# Pattern dans appTasks.py
if self.param_source_provider_type == 'postgresql' and layer_provider_type == 'postgresql':
    # Utilisation PostGIS optimisée
    # Création vues matérialisées
    # Requêtes SQL côté serveur
else:
    # Fallback QGIS
    # Filtrage en mémoire
    # Utilisation API Python QGIS
```

### Connexion bases de données
```python
# PostgreSQL (appUtils.py)
connexion = psycopg2.connect(
    user=username, 
    password=password, 
    host=host, 
    port=port, 
    database=dbname
)

# Spatialite (filter_mate_app.py)
conn = spatialite_connect(self.db_file_path)
cursor = conn.cursor()
cursor.execute(sql_statement)
conn.commit()
conn.close()
```

---

## Points d'Entrée pour Migration

### 1. Rendre psycopg2 optionnel (PRIORITÉ 1)

**Fichiers à modifier**:
- `modules/appUtils.py`: ligne 2
- `modules/appTasks.py`: ligne 9

**Code proposé**:
```python
# modules/appUtils.py
import math
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None  # Pour éviter NameError

from qgis.core import *

def get_datasource_connexion_from_layer(layer):
    if not POSTGRESQL_AVAILABLE:
        return None, None
    # ... reste du code
```

### 2. Alternative vues matérialisées (PRIORITÉ 2)

**Fonction à créer** dans `modules/appTasks.py`:
```python
def create_temp_spatialite_table(self, table_name, sql_query):
    """
    Alternative à CREATE MATERIALIZED VIEW PostgreSQL
    Utilise Spatialite avec table temporaire indexée
    """
    pass  # Voir exemple dans AUDIT_FILTERMATE.md
```

**Lignes à modifier**:
- 1139, 1188, 1202, 1341: Appels CREATE MATERIALIZED VIEW
- Ajouter branche conditionnelle:
  ```python
  if self.param_source_provider_type == 'postgresql':
      self.create_postgresql_materialized_view(...)
  else:
      self.create_temp_spatialite_table(...)
  ```

### 3. Adapter expressions spatiales (PRIORITÉ 3)

**Fonction existante**: `qgis_expression_to_postgis()` ligne 362

**Nouvelle fonction à créer**: 
```python
def qgis_expression_to_spatialite(self, expression):
    """
    Convertit expression QGIS en SQL Spatialite
    Similaire à qgis_expression_to_postgis()
    Bonus: Spatialite = syntaxe compatible PostGIS!
    """
    pass
```

---

## Tests Recommandés

### Tests unitaires à créer
```python
# tests/test_multi_provider.py

def test_filter_without_postgresql():
    """Vérifie filtrage sans PostgreSQL disponible"""
    pass

def test_spatialite_alternative():
    """Vérifie création table temp Spatialite"""
    pass

def test_ogr_filtering():
    """Vérifie filtrage Shapefile/GeoPackage"""
    pass

def test_geometric_predicates_spatialite():
    """Vérifie prédicats géométriques Spatialite"""
    pass
```

### Tests d'intégration
- Charger projet avec couches Shapefile uniquement
- Appliquer filtre expression
- Appliquer filtre géométrique (buffer + intersects)
- Export résultats
- Vérifier historique Spatialite

### Tests de régression
- Vérifier fonctionnement identique avec PostgreSQL actif
- Benchmarks performances avant/après
- Validation utilisateurs beta

---

## Configuration Recommandée

### Ajout à config.json
```json
{
    "APP": {
        "OPTIONS": {
            "POSTGRESQL_ENABLED": true,
            "FALLBACK_TO_SPATIALITE": true,
            "WARN_PERFORMANCE_DEGRADATION": true,
            "MAX_FEATURES_MEMORY_FILTER": 50000
        }
    }
}
```

---

## Commandes Utiles

### Analyse base Spatialite
```bash
sqlite3 filterMate_db.sqlite
.tables
.schema
SELECT * FROM sqlite_master WHERE type='table';
```

### Vérification dépendances
```python
# Dans console Python QGIS
import sys
print(sys.path)

try:
    import psycopg2
    print(f"psycopg2 version: {psycopg2.__version__}")
except ImportError:
    print("psycopg2 non disponible")

import sqlite3
print(f"sqlite3 version: {sqlite3.sqlite_version}")
```

### Tests Spatialite
```python
import sqlite3
conn = sqlite3.connect(':memory:')
conn.enable_load_extension(True)
try:
    conn.load_extension('mod_spatialite')
    print("Spatialite OK")
except:
    print("Spatialite non disponible")
```

---

## Métriques Code

- **Lignes totales**: ~3000-4000 lignes Python
- **Fichiers critiques**: 3 (filter_mate_app.py, appTasks.py, appUtils.py)
- **Lignes à modifier pour migration**: ~150-200 lignes
- **Complexité**: Moyenne-Haute (architecture modulaire aide)
- **Tests existants**: À créer
- **Documentation**: README basique, à enrichir

---

## Liens Utiles

### Documentation QGIS
- PyQGIS Cookbook: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/
- QGIS API: https://qgis.org/pyqgis/master/
- Plugin Development: https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/plugins/

### Spatialite
- Documentation: https://www.gaia-gis.it/fossil/libspatialite/
- SQL Reference: https://www.gaia-gis.it/gaia-sins/spatialite-sql-latest.html
- Fonctions spatiales: Compatible PostGIS à ~90%

### PostgreSQL/PostGIS
- PostGIS Reference: https://postgis.net/docs/
- psycopg2: https://www.psycopg.org/docs/

---

**Document maintenu par**: Équipe FilterMate  
**Dernière mise à jour**: 2 décembre 2025  
**Version**: 1.0
