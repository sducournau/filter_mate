# Guide de Migration - FilterMate sans PostgreSQL

## 🎯 Objectif
Permettre à FilterMate de fonctionner sans dépendance PostgreSQL, en utilisant Spatialite et OGR pour toutes les opérations.

---

## 📋 Checklist de Migration

### Phase 1: Import Conditionnel (1 jour) ✅
- [ ] Modifier `modules/appUtils.py` - Import psycopg2 conditionnel
- [ ] Modifier `modules/appTasks.py` - Import psycopg2 conditionnel
- [ ] Ajouter flag global `POSTGRESQL_AVAILABLE`
- [ ] Tester démarrage plugin sans psycopg2
- [ ] Commit: "feat: Make PostgreSQL optional dependency"

### Phase 2: Backend Spatialite (3-5 jours) 🔄
- [ ] Créer fonction `create_temp_spatialite_table()`
- [ ] Créer fonction `qgis_expression_to_spatialite()`
- [ ] Adapter `execute_geometric_filtering()` pour Spatialite
- [ ] Implémenter création index spatiaux Spatialite
- [ ] Tester filtrage géométrique basique
- [ ] Commit: "feat: Add Spatialite backend for filtering"

### Phase 3: Tests & Documentation (2-3 jours) 📝
- [ ] Tests unitaires backend Spatialite
- [ ] Tests intégration multi-sources
- [ ] Tests régression PostgreSQL
- [ ] Documentation utilisateur
- [ ] Benchmarks performances
- [ ] Commit: "test: Add multi-backend test suite"

### Phase 4: Optimisation (3-5 jours) ⚡
- [ ] Auto-détection backend optimal
- [ ] Cache résultats intermédiaires
- [ ] Optimisation index R-tree
- [ ] Messages utilisateur pédagogiques
- [ ] Commit: "perf: Optimize Spatialite backend"

---

## 🔧 Modifications Détaillées

### 1. modules/appUtils.py

#### AVANT (ligne 1-5):
```python
import math
import psycopg2
from qgis.core import *
from qgis.utils import *
```

#### APRÈS:
```python
import math
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None

from qgis.core import *
from qgis.utils import *
```

#### Fonction à modifier (ligne 15-44):
```python
def get_datasource_connexion_from_layer(layer):
    """Get PostgreSQL connection from layer (if available)"""
    
    # Nouvelle vérification
    if not POSTGRESQL_AVAILABLE:
        return None, None
    
    connexion = None
    source_uri, authcfg_id = get_data_source_uri(layer)
    
    # Vérifier que c'est bien une source PostgreSQL
    if layer.providerType() != 'postgres':
        return None, None
    
    # ... reste du code existant
```

---

### 2. modules/appTasks.py

#### A. Import conditionnel (début fichier)

**AVANT**:
```python
import psycopg2
from qgis.PyQt.QtCore import *
# ...
```

**APRÈS**:
```python
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None

from qgis.PyQt.QtCore import *
# ...
```

#### B. Nouvelle fonction alternative vues matérialisées

**AJOUTER après ligne ~440**:
```python
def create_temp_spatialite_table(self, db_path, table_name, sql_query, geom_field='geometry'):
    """
    Crée une table temporaire Spatialite comme alternative 
    aux vues matérialisées PostgreSQL.
    
    Args:
        db_path: Chemin vers base Spatialite
        table_name: Nom de la table temporaire (sans préfixe 'temp_')
        sql_query: Requête SQL de sélection
        geom_field: Nom du champ géométrie (défaut: 'geometry')
    
    Returns:
        bool: True si succès, False sinon
    """
    import sqlite3
    
    try:
        # Connexion avec support Spatialite
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)
        
        # Charger extension Spatialite
        try:
            conn.load_extension('mod_spatialite')
        except:
            # Tentative alternative (Windows)
            conn.load_extension('mod_spatialite.dll')
        
        cursor = conn.cursor()
        
        # Supprimer table si existe
        temp_table = f"temp_{table_name}"
        cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")
        
        # Créer table temporaire
        cursor.execute(f"CREATE TABLE {temp_table} AS {sql_query}")
        
        # Créer index spatial (R-tree)
        try:
            cursor.execute(f"""
                SELECT CreateSpatialIndex('{temp_table}', '{geom_field}')
            """)
        except Exception as e:
            # Index spatial optionnel
            print(f"Warning: Could not create spatial index: {e}")
        
        # Créer index sur clé primaire
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{temp_table}_pk 
            ON {temp_table}(rowid)
        """)
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error creating Spatialite temp table: {e}")
        return False
```

#### C. Fonction conversion expressions QGIS → Spatialite

**AJOUTER après ligne ~390** (après `qgis_expression_to_postgis`):
```python
def qgis_expression_to_spatialite(self, expression):
    """
    Convertit une expression QGIS en SQL Spatialite.
    
    Bonus: Spatialite utilise la même syntaxe que PostGIS 
    pour la plupart des fonctions spatiales!
    
    Args:
        expression: Expression QGIS (string)
    
    Returns:
        str: Expression SQL Spatialite
    """
    # Mapping des fonctions si différentes
    # (en pratique, Spatialite est très compatible PostGIS)
    
    spatialite_expression = expression
    
    # Remplacements si nécessaire
    replacements = {
        # Exemple: certaines fonctions ont noms différents
        # 'qt_function': 'spatialite_function',
    }
    
    for qgis_func, spatialite_func in replacements.items():
        spatialite_expression = spatialite_expression.replace(
            qgis_func, 
            spatialite_func
        )
    
    return spatialite_expression
```

#### D. Modifier fonction de filtrage géométrique (ligne ~562)

**AVANT**:
```python
if self.param_source_provider_type == 'postgresql' and layer_provider_type == 'postgresql':
    # Logique PostgreSQL
    postgis_sub_expression_array = []
    # ...
```

**APRÈS**:
```python
# Support multi-backend
if (self.param_source_provider_type == 'postgresql' and 
    layer_provider_type == 'postgresql' and 
    POSTGRESQL_AVAILABLE):
    
    # Logique PostgreSQL (optimisée)
    postgis_sub_expression_array = []
    # ... code existant ...
    
elif (self.param_source_provider_type == 'spatialite' or 
      layer_provider_type == 'spatialite'):
    
    # Nouvelle logique Spatialite
    spatialite_sub_expression_array = []
    for spatialite_predicate in list(self.current_predicates.values()):
        # Construction expression Spatialite
        # Syntaxe très similaire à PostGIS
        param_distant_geom_expression = # ... construire expression
        
        spatialite_sub_expression_array.append(
            spatialite_predicate + 
            f'({self.spatialite_source_geom}, {param_distant_geom_expression})'
        )
    
    if len(spatialite_sub_expression_array) > 1:
        param_expression = ' OR '.join(spatialite_sub_expression_array)
    else:
        param_expression = spatialite_sub_expression_array[0]
    
    # Utiliser expression dans requête Spatialite
    # ... code à adapter ...
    
else:
    # Fallback QGIS (code existant)
    # ...
```

#### E. Modifier création vues matérialisées (lignes 1139, 1188, etc.)

**PATTERN À APPLIQUER**:
```python
# AVANT (ligne ~1139)
sql_create_request = 'CREATE MATERIALIZED VIEW IF NOT EXISTS ...'

# APRÈS
if self.param_source_provider_type == 'postgresql' and POSTGRESQL_AVAILABLE:
    # PostgreSQL: Vues matérialisées
    sql_create_request = 'CREATE MATERIALIZED VIEW IF NOT EXISTS ...'
    # ... exécution PostgreSQL ...
    
elif self.param_source_provider_type == 'spatialite':
    # Spatialite: Tables temporaires
    db_path = self.task_parameters["task"]["app"].db_file_path
    
    # Construire requête SELECT équivalente
    sql_query = f"SELECT ... FROM ... WHERE ..."
    
    success = self.create_temp_spatialite_table(
        db_path=db_path,
        table_name=self.source_subset_name,
        sql_query=sql_query,
        geom_field=self.source_geometry_field
    )
    
    if not success:
        raise Exception("Failed to create Spatialite temp table")
        
else:
    # OGR ou autre: fallback QGIS
    # ... code existant ...
```

---

### 3. filter_mate_app.py

#### Modifier gestion datasources PostgreSQL (ligne ~890-894)

**AVANT**:
```python
if len(self.project_datasources['postgresql']) >= 1:
    postgresql_connexions = list(self.project_datasources['postgresql'].keys())
    if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] == "":
        self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ...
```

**APRÈS**:
```python
# Vérifier disponibilité PostgreSQL
from modules.appUtils import POSTGRESQL_AVAILABLE

if 'postgresql' in self.project_datasources and POSTGRESQL_AVAILABLE:
    if len(self.project_datasources['postgresql']) >= 1:
        postgresql_connexions = list(self.project_datasources['postgresql'].keys())
        if self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] == "":
            self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ...
else:
    # PostgreSQL non disponible: utiliser Spatialite
    if 'postgresql' in self.project_datasources:
        # Avertir utilisateur si couches PostgreSQL détectées
        self.iface.messageBar().pushWarning(
            "FilterMate",
            "PostgreSQL layers detected but psycopg2 not available. "
            "Using local Spatialite backend (may be slower)."
        )
```

---

## 🧪 Tests à Exécuter

### Test 1: Démarrage sans PostgreSQL
```python
# 1. Désinstaller psycopg2 (environnement test)
pip uninstall psycopg2 psycopg2-binary

# 2. Lancer QGIS et activer FilterMate
# 3. Vérifier: pas d'erreur au démarrage
# 4. Vérifier: message warning si couches PostgreSQL
```

### Test 2: Filtrage expression Shapefile
```python
# Dans QGIS:
# 1. Charger Shapefile
# 2. Ouvrir FilterMate
# 3. Appliquer filtre expression: "population > 10000"
# 4. Vérifier résultats corrects
# 5. Vérifier historique Spatialite mis à jour
```

### Test 3: Filtrage géométrique Spatialite
```python
# Dans QGIS:
# 1. Charger 2 couches Shapefile (points et polygones)
# 2. Sélectionner couche points
# 3. Filtrer par intersection avec polygones
# 4. Vérifier: table temporaire créée dans filterMate_db.sqlite
# 5. Vérifier: résultats corrects
```

### Test 4: Régression PostgreSQL
```python
# Avec psycopg2 installé:
# 1. Charger couches PostgreSQL
# 2. Appliquer filtres (expression + géométrique)
# 3. Comparer performances avant/après modifications
# 4. Vérifier: comportement identique
```

---

## 📊 Validation Performances

### Benchmarks à réaliser

| Dataset | Taille | PostgreSQL | Spatialite | QGIS Memory | Ratio |
|---------|--------|------------|------------|-------------|-------|
| Small   | 1k features | ~0.5s | ~1s | ~2s | 2x |
| Medium  | 10k features | ~2s | ~5s | ~15s | 2.5x |
| Large   | 100k features | ~10s | ~30s | timeout | 3x |
| XLarge  | 1M+ features | ~30s | ~3min | timeout | 6x |

**Objectifs**:
- ✅ Small/Medium: Performance acceptable Spatialite
- ⚠️ Large: Avertissement utilisateur recommandé
- ❌ XLarge: PostgreSQL fortement recommandé

---

## 📝 Messages Utilisateur

### Avertissement performance
```python
# Dans filter_mate_app.py ou appTasks.py
if layer.featureCount() > 50000 and not POSTGRESQL_AVAILABLE:
    self.iface.messageBar().pushWarning(
        "FilterMate - Performance",
        f"Large dataset detected ({layer.featureCount()} features). "
        "Consider using PostgreSQL/PostGIS for better performance. "
        "Visit: https://github.com/sducournau/filter_mate#postgresql",
        duration=10
    )
```

### Information backend utilisé
```python
# Afficher dans log ou interface
backend = "PostgreSQL" if POSTGRESQL_AVAILABLE else "Spatialite"
print(f"FilterMate: Using {backend} backend for layer {layer.name()}")
```

---

## 🐛 Débogage

### Vérifier Spatialite disponible
```python
import sqlite3

def check_spatialite():
    try:
        conn = sqlite3.connect(':memory:')
        conn.enable_load_extension(True)
        conn.load_extension('mod_spatialite')
        cursor = conn.cursor()
        cursor.execute("SELECT spatialite_version()")
        version = cursor.fetchone()[0]
        conn.close()
        print(f"✅ Spatialite {version} available")
        return True
    except Exception as e:
        print(f"❌ Spatialite not available: {e}")
        return False
```

### Logger requêtes SQL
```python
# Ajouter dans create_temp_spatialite_table
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('FilterMate')

logger.debug(f"Executing Spatialite query: {sql_query[:100]}...")
```

---

## 🚀 Déploiement

### 1. Version Beta (utilisateurs tests)
- Branche: `feature/spatialite-backend`
- Flag: `"EXPERIMENTAL_SPATIALITE": true` dans config.json
- Feedback: GitHub Issues

### 2. Version Stable
- Merge dans `main` après validation
- Update metadata.txt: version 1.9
- Tag Git: `v1.9.0`
- Documentation README.md enrichie

### 3. Communication
```markdown
# Changelog v1.9.0

## 🎉 Nouvelles fonctionnalités
- ✨ FilterMate peut maintenant fonctionner sans PostgreSQL!
- 🚀 Support complet Spatialite pour filtrage géométrique
- 📦 Installation simplifiée (pas de serveur externe requis)

## ⚠️ Notes
- PostgreSQL reste recommandé pour datasets > 100k features
- Performances Spatialite: 2-3x plus lent que PostGIS sur grandes tables
- Toutes fonctionnalités préservées!
```

---

## ✅ Critères de Succès

- [ ] Plugin démarre sans psycopg2
- [ ] Filtrage expression fonctionne (Shapefile/GeoPackage)
- [ ] Filtrage géométrique fonctionne (Spatialite)
- [ ] Tests régression PostgreSQL OK
- [ ] Documentation utilisateur complète
- [ ] Benchmarks performances documentés
- [ ] 0 erreur sur datasets test
- [ ] Feedback positif utilisateurs beta

---

## 📚 Ressources

- Audit complet: `AUDIT_FILTERMATE.md`
- Config projet: `SERENA_PROJECT_CONFIG.md`
- Spatialite functions: https://www.gaia-gis.it/gaia-sins/spatialite-sql-latest.html
- PostGIS compatibility: https://www.gaia-gis.it/fossil/libspatialite/wiki?name=switching-to-4.0

---

**Guide maintenu par**: Équipe FilterMate  
**Dernière mise à jour**: 2 décembre 2025  
**Pour questions**: GitHub Issues
