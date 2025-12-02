# Audit de l'Application FilterMate

**Date**: 2 décembre 2025  
**Version analysée**: 1.8  
**Objectif**: Analyser la codebase et évaluer la possibilité de fonctionner sans base de données PostgreSQL

---

## 1. Vue d'ensemble

FilterMate est un plugin QGIS permettant d'explorer, filtrer et exporter des données vectorielles. Il supporte actuellement trois types de sources de données:
- **PostgreSQL/PostGIS** (base de données externe)
- **Spatialite** (SQLite avec extensions spatiales)
- **OGR** (fichiers géographiques: Shapefile, GeoJSON, etc.)

### Architecture actuelle

```
FilterMate
├── Core (filter_mate.py, filter_mate_app.py)
├── Configuration (config/, config.json)
├── Modules
│   ├── appTasks.py      # Gestion des tâches de filtrage
│   ├── appUtils.py      # Utilitaires (connexion PostgreSQL)
│   ├── widgets.py       # Interface utilisateur
│   └── customExceptions.py
└── Interface (filter_mate_dockwidget.py, *.ui)
```

---

## 2. Analyse de la dépendance PostgreSQL

### 2.1 Utilisation actuelle de PostgreSQL

#### Fichiers concernés:
1. **`modules/appUtils.py`**
   - Import: `psycopg2` (ligne 2)
   - Fonction: `get_datasource_connexion_from_layer()` - établit les connexions PostgreSQL

2. **`modules/appTasks.py`**
   - Import: `psycopg2` (ligne 9)
   - Nombreuses fonctions spécifiques PostgreSQL:
     - `qgis_expression_to_postgis()` - conversion expressions QGIS → PostGIS
     - `prepare_postgresql_source_geom()` - préparation géométries PostgreSQL
     - Création de **vues matérialisées** PostgreSQL (`CREATE MATERIALIZED VIEW`)
     - Gestion des index spatiaux PostgreSQL
     - Utilisation du schéma temporaire `filterMate_temp`

3. **`filter_mate_app.py`**
   - Gestion du schéma temporaire PostgreSQL (`app_postgresql_temp_schema`)
   - Détection et connexion aux sources PostgreSQL du projet
   - Variable: `project_datasources['postgresql']`

### 2.2 Fonctionnalités spécifiques PostgreSQL

#### Vues matérialisées (MATERIALIZED VIEWS)
```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS "{schema}"."mv_{name}" 
TABLESPACE pg_default AS {sql_subset_string} WITH DATA;
```
- **Avantage**: Performance optimale pour grands datasets
- **Limitation**: Spécifique à PostgreSQL (non supporté par SQLite/Spatialite)

#### Requêtes spatiales optimisées
- Utilisation de **PostGIS**: `ST_Buffer`, `ST_Transform`, `ST_Union`, `ST_Intersects`, etc.
- Prédicats géométriques performants sur grandes tables
- Index spatiaux GIST

#### Schéma temporaire
- Création d'un schéma `filterMate_temp` pour stocker les vues matérialisées temporaires
- Requête SQL: `CREATE SCHEMA IF NOT EXISTS filterMate_temp AUTHORIZATION postgres;`

### 2.3 Fonctionnalités déjà indépendantes de PostgreSQL

#### Spatialite (SQLite + extension spatiale)
Le plugin utilise **déjà** Spatialite pour:
- Historique des subsets/filtres (`filterMate_db.sqlite`)
- Métadonnées du projet
- Stockage local des configurations

**Localisation**: `C:\Users\simon\AppData\Roaming\QGIS\QGIS3\profiles\default\FilterMate\filterMate_db.sqlite`

#### Support OGR
- Fichiers Shapefile, GeoJSON, GeoPackage
- Fonction `prepare_ogr_source_geom()` existe déjà

---

## 3. État actuel du support multi-sources

### 3.1 Détection automatique du type de source

Le code détecte automatiquement le type de provider:
```python
# modules/appTasks.py
if layer.providerType() == 'postgres':
    layer_provider_type = 'postgresql'
elif layer.providerType() == 'spatialite':
    layer_provider_type = 'spatialite'
elif layer.providerType() == 'ogr':
    layer_provider_type = 'ogr'
```

### 3.2 Logique conditionnelle existante

Le plugin adapte déjà son comportement selon la source:
```python
# modules/appTasks.py (ligne 340-344)
provider_list = self.provider_list + [self.param_source_provider_type]

if 'postgresql' in provider_list:
    self.prepare_postgresql_source_geom()

if 'ogr' in provider_list or 'spatialite' in provider_list or self.param_buffer_expression != '':
    self.prepare_ogr_source_geom()
```

### 3.3 Filtrages géométriques

```python
# modules/appTasks.py (ligne 562)
if self.param_source_provider_type == 'postgresql' and layer_provider_type == 'postgresql':
    # Utilise PostGIS pour requêtes optimisées
else:
    # Utilise QGIS pour filtrage en mémoire
```

---

## 4. Analyse des dépendances Python

### 4.1 Dépendance critique
```python
import psycopg2  # Bibliothèque PostgreSQL
```

**Problème**: Import non conditionnel dans `appUtils.py` et `appTasks.py`

**Impact**: Si `psycopg2` n'est pas installé, le plugin ne peut pas démarrer, même pour des sources non-PostgreSQL.

### 4.2 Autres dépendances (OK)
- `qgis.core`, `qgis.gui`, `qgis.utils` ✅
- `PyQt5` (QtCore, QtGui, QtWidgets) ✅
- `json`, `os`, `sys`, `re`, `math` (stdlib) ✅

---

## 5. Scénarios d'utilisation

### 5.1 Avec PostgreSQL (actuel)
- ✅ Filtrage ultra-rapide sur grandes tables PostGIS
- ✅ Vues matérialisées pour performances optimales
- ✅ Prédicats géométriques côté serveur
- ❌ Nécessite serveur PostgreSQL + PostGIS
- ❌ Configuration réseau/authentification

### 5.2 Sans PostgreSQL (objectif)
- ✅ Fonctionnement autonome (pas de serveur externe)
- ✅ Fichiers locaux: Shapefile, GeoPackage, GeoJSON
- ✅ Spatialite pour données SQLite locales
- ⚠️ Performances réduites sur très grands datasets
- ⚠️ Filtrage en mémoire par QGIS

---

## 6. Recommandations pour fonctionner sans PostgreSQL

### 6.1 Modifications prioritaires

#### A. Rendre l'import psycopg2 conditionnel
**Urgence**: 🔴 CRITIQUE

```python
# modules/appUtils.py
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    
def get_datasource_connexion_from_layer(layer):
    if not PSYCOPG2_AVAILABLE:
        return None, None
    # ... reste du code
```

**Fichiers à modifier**:
- `modules/appUtils.py` (ligne 2)
- `modules/appTasks.py` (ligne 9)

#### B. Remplacer les vues matérialisées PostgreSQL
**Urgence**: 🟠 HAUTE

**Solutions alternatives**:

1. **Spatialite avec tables temporaires**
   ```sql
   -- Au lieu de MATERIALIZED VIEW
   CREATE TEMP TABLE mv_{name} AS {sql_subset_string};
   CREATE INDEX idx_{name}_geom ON mv_{name}(geometry);
   ```

2. **Couches temporaires QGIS en mémoire**
   ```python
   temp_layer = QgsVectorLayer("Point?crs=epsg:4326", "temp", "memory")
   # Copier features filtrées
   ```

3. **GeoPackage temporaire** (recommandé)
   ```python
   # Utiliser GeoPackage comme alternative performante
   temp_gpkg = "temp_filter.gpkg"
   QgsVectorFileWriter.writeAsVectorFormat(
       layer, temp_gpkg, "UTF-8", crs, "GPKG"
   )
   ```

#### C. Adapter les fonctions spatiales
**Urgence**: 🟡 MOYENNE

Mapper les fonctions PostGIS vers équivalents:

| PostGIS | Spatialite | QGIS (Python) |
|---------|------------|---------------|
| `ST_Buffer()` | `ST_Buffer()` ✅ | `geometry().buffer()` |
| `ST_Intersects()` | `ST_Intersects()` ✅ | `geometry().intersects()` |
| `ST_Union()` | `ST_Union()` ✅ | `QgsGeometry.unaryUnion()` |
| `ST_Transform()` | `ST_Transform()` ✅ | `QgsCoordinateTransform` |

**Spatialite supporte la majorité des fonctions PostGIS!**

### 6.2 Stratégie de migration recommandée

#### Phase 1: Import conditionnel (immédiat)
- Rendre `psycopg2` optionnel
- Ajouter gestion d'erreur si PostgreSQL non disponible

#### Phase 2: Alternative Spatialite (court terme)
- Créer fonction `create_temp_table_spatialite()` comme alternative à `create_materialized_view_postgresql()`
- Utiliser base Spatialite temporaire pour filtres complexes
- Réutiliser base `filterMate_db.sqlite` existante

#### Phase 3: Mode hybride (moyen terme)
- Détecter automatiquement si PostgreSQL disponible
- Choisir backend optimal selon source:
  - PostgreSQL → vues matérialisées PostGIS
  - Autres → tables temporaires Spatialite
  
#### Phase 4: Optimisations (long terme)
- GeoPackage comme format intermédiaire performant
- Cache spatial local
- Index R-tree Spatialite

---

## 7. Analyse d'impact

### 7.1 Modifications nécessaires

| Fichier | Lignes concernées | Complexité | Temps estimé |
|---------|-------------------|------------|--------------|
| `modules/appUtils.py` | 2-45 | 🟢 Faible | 1h |
| `modules/appTasks.py` | 9, 216-720, 1139-1365 | 🔴 Élevée | 8-12h |
| `filter_mate_app.py` | 81, 444-894 | 🟡 Moyenne | 4-6h |
| **TOTAL** | ~150 lignes | | **13-19h** |

### 7.2 Fonctionnalités impactées

#### Fonctionnent déjà sans PostgreSQL ✅
- Filtrage par expression (sources locales)
- Export de couches
- Configuration/préférences
- Historique des subsets (Spatialite)
- Interface utilisateur

#### Nécessitent adaptation ⚠️
- Filtrage géométrique optimisé (vues matérialisées)
- Prédicats spatiaux sur très grandes tables
- Buffers dynamiques avec expressions

#### Performances réduites sur 🐢
- Datasets > 100k features
- Requêtes spatiales complexes multiples
- Combinaisons de filtres géométriques

---

## 8. Plan d'action proposé

### 8.1 Actions immédiates (Sprint 1 - 1 semaine)

1. **Rendre psycopg2 optionnel**
   - Import conditionnel avec try/except
   - Flag global `POSTGRESQL_AVAILABLE`
   - Désactiver fonctions PostgreSQL si non disponible

2. **Tester fonctionnalités de base sans PostgreSQL**
   - Filtrage expression sur Shapefile
   - Filtrage expression sur GeoPackage
   - Export vers différents formats

3. **Documenter limitations**
   - README.md: section "Sans PostgreSQL"
   - Message utilisateur si performance dégradée

### 8.2 Actions court terme (Sprint 2-3 - 2-3 semaines)

1. **Implémenter alternative Spatialite**
   - Fonction `create_temp_spatialite_table()`
   - Remplacer vues matérialisées PostgreSQL
   - Tester performances sur datasets moyens (1k-50k features)

2. **Adapter filtrage géométrique**
   - Utiliser Spatialite pour prédicats spatiaux
   - Fallback QGIS si nécessaire
   - Optimiser avec index R-tree

3. **Mettre à jour configuration**
   - Option "Mode de fonctionnement" dans config.json
   - Auto-détection backend optimal

### 8.3 Actions moyen terme (Sprint 4-6 - 1-2 mois)

1. **Mode hybride intelligent**
   - Détection automatique sources disponibles
   - Sélection backend optimal par couche
   - Cache résultats intermédiaires

2. **Optimisations performances**
   - GeoPackage comme format temporaire
   - Stratégies d'indexation adaptatives
   - Parallélisation calculs (QThreads)

3. **Tests complets**
   - Suite tests unitaires
   - Benchmarks performances
   - Validation utilisateurs beta

---

## 9. Analyse des risques

### 9.1 Risques techniques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Performance dégradée grands datasets | 🔴 Haute | 🟡 Moyen | Documentation + warning utilisateur |
| Bugs rétrocompatibilité PostgreSQL | 🟡 Moyenne | 🔴 Élevé | Tests exhaustifs mode PostgreSQL |
| Limitations Spatialite vs PostGIS | 🟡 Moyenne | 🟢 Faible | Spatialite supporte ~90% fonctions PostGIS |
| Complexité maintenance double backend | 🟠 Moyenne | 🟡 Moyen | Architecture modulaire + abstraction |

### 9.2 Risques fonctionnels

- **Perte de fonctionnalité**: NON - toutes fonctionnalités gardées, performance réduite
- **Régression utilisateurs PostgreSQL**: Risque faible si tests approfondis
- **Adoption utilisateurs**: Gain attendu (simplicité installation)

---

## 10. Métriques de succès

### 10.1 Critères techniques
- ✅ Plugin démarre sans psycopg2 installé
- ✅ Filtrage fonctionnel sur Shapefile/GeoPackage/GeoJSON
- ✅ Filtrage géométrique sans PostgreSQL (Spatialite)
- ✅ Temps filtrage < 5s sur 10k features (Spatialite)
- ✅ Pas de régression performances PostgreSQL

### 10.2 Critères utilisateur
- ✅ Installation simplifiée (pas de dépendance serveur)
- ✅ Fonctionnement "out of the box"
- ✅ Documentation claire limitations/avantages
- ✅ Message pédagogique si performance limitée

---

## 11. Conclusion

### 11.1 Faisabilité
🟢 **FAISABLE** - Le plugin **peut fonctionner sans PostgreSQL**

**Points positifs**:
- Infrastructure Spatialite déjà présente
- Support OGR déjà implémenté
- Architecture modulaire adaptable
- ~80% fonctionnalités indépendantes de PostgreSQL

**Points d'attention**:
- Effort développement: 2-3 semaines temps plein
- Tests approfondis nécessaires
- Documentation utilisateur à enrichir
- Performance réduite sur très grands datasets

### 11.2 Recommandation finale

**Stratégie recommandée: MODE HYBRIDE**

1. **Phase 1 (immédiat)**: Rendre PostgreSQL optionnel
   - Impact: faible
   - Gain: plugin fonctionne sans PostgreSQL (fonctionnalités limitées)

2. **Phase 2 (court terme)**: Implémenter backend Spatialite
   - Impact: moyen
   - Gain: filtrage géométrique performant sans PostgreSQL

3. **Phase 3 (moyen terme)**: Auto-détection et optimisation
   - Impact: moyen
   - Gain: meilleur des deux mondes selon contexte

**Bénéfices attendus**:
- 📈 Adoption facilitée (pas de serveur PostgreSQL requis)
- 🚀 Utilisation simplifiée (fichiers locaux)
- 💪 Garde puissance PostgreSQL si disponible
- 🔧 Maintenance raisonnable (architecture claire)

---

## 12. Ressources

### 12.1 Documentation pertinente
- [Spatialite SQL functions](https://www.gaia-gis.it/gaia-sins/spatialite-sql-latest.html)
- [QGIS PyQGIS API](https://qgis.org/pyqgis/master/)
- [GeoPackage specification](https://www.geopackage.org/)

### 12.2 Exemples de code

#### Import conditionnel PostgreSQL
```python
# Début de modules/appUtils.py
import math
try:
    import psycopg2
    POSTGRESQL_SUPPORT = True
except ImportError:
    POSTGRESQL_SUPPORT = False
    import warnings
    warnings.warn("PostgreSQL support disabled: psycopg2 not found")

from qgis.core import *
from qgis.utils import *
```

#### Création table temporaire Spatialite
```python
def create_temp_spatialite_table(self, db_path, table_name, sql_query):
    """Alternative aux vues matérialisées PostgreSQL"""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension("mod_spatialite")
    
    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS temp_{table_name}")
    cursor.execute(f"CREATE TABLE temp_{table_name} AS {sql_query}")
    
    # Index spatial
    cursor.execute(f"""
        SELECT CreateSpatialIndex('temp_{table_name}', 'geometry')
    """)
    
    conn.commit()
    conn.close()
```

---

**Audit réalisé par**: GitHub Copilot (Claude Sonnet 4.5)  
**Date**: 2 décembre 2025  
**Prochaine révision**: Après implémentation Phase 1
