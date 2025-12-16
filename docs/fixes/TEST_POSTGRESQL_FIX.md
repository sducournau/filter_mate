# Test du Fix PostgreSQL dans QGIS

## Problème résolu
Le plugin restait désactivé quand des couches PostgreSQL étaient ajoutées sans psycopg2 installé.

## Modifications apportées

### 1. `modules/appUtils.py`
- Ajout de vérification `POSTGRESQL_AVAILABLE` dans `is_layer_source_available()`
- Les couches PostgreSQL sont maintenant rejetées si psycopg2 n'est pas disponible

### 2. `filter_mate_app.py`
- Ajout de messages d'avertissement dans `_on_layers_added()`
- Log du statut PostgreSQL au démarrage dans `__init__()`

### 3. `tests/test_postgresql_layer_handling.py`
- Tests unitaires pour valider le comportement

## Comment tester dans QGIS

### Étape 1 : Recharger le plugin

Dans QGIS, ouvrir la **Console Python** (Ctrl+Alt+P) et exécuter :

```python
# Recharger le plugin
from qgis.utils import plugins, reloadPlugin
reloadPlugin('filter_mate')
```

Ou utiliser le plugin **Plugin Reloader** si installé.

### Étape 2 : Vérifier le statut PostgreSQL

Dans la Console Python QGIS :

```python
from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
print(f"PostgreSQL support: {POSTGRESQL_AVAILABLE}")
```

**Résultat attendu :**
- `True` si psycopg2 est installé
- `False` si psycopg2 n'est pas installé

### Étape 3 : Exécuter le test de chargement

Dans la Console Python QGIS :

```python
exec(open(r'C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate/test_plugin_load.py').read())
```

Ce script affiche :
- ✓ État des imports du plugin
- ✓ Disponibilité de PostgreSQL
- ✓ Couches PostgreSQL dans le projet
- ✓ État du plugin

### Étape 4 : Tester avec couches PostgreSQL

#### Cas 1 : psycopg2 NON installé (reproduire le bug)

1. **Désinstaller psycopg2** (si nécessaire) :
   ```bash
   # Dans OSGeo4W Shell ou Python de QGIS
   pip uninstall psycopg2 psycopg2-binary
   ```

2. **Redémarrer QGIS**

3. **Ajouter une couche PostgreSQL** :
   - Couche → Ajouter une couche → Ajouter une couche PostGIS
   - Connexion : `post — QGIS [imagodata]`
   - Sélectionner une table

4. **Résultat attendu** :
   - ⚠️ **Message d'avertissement jaune** dans la barre de message :
     ```
     Couches PostgreSQL détectées (nom_couche) mais psycopg2 n'est pas installé.
     Le plugin ne peut pas utiliser ces couches.
     Installez psycopg2 pour activer le support PostgreSQL.
     ```
   - Le plugin n'affiche PAS la couche PostgreSQL dans sa liste
   - Les autres couches (Spatialite, GeoPackage, etc.) fonctionnent normalement

5. **Vérifier les logs** :
   - Ouvrir **Préférences → Journal des messages**
   - Filtrer sur "FilterMate"
   - Devrait contenir :
     ```
     WARNING: FilterMate: PostgreSQL support DISABLED - psycopg2 not installed
     WARNING: FilterMate: Cannot use X PostgreSQL layer(s) - psycopg2 not available
     WARNING: PostgreSQL layer detected but psycopg2 not available: nom_couche
     ```

#### Cas 2 : psycopg2 installé (solution)

1. **Installer psycopg2** :
   ```bash
   # Dans OSGeo4W Shell
   pip install psycopg2-binary
   ```

2. **Redémarrer QGIS**

3. **Recharger le plugin** (Console Python) :
   ```python
   from qgis.utils import reloadPlugin
   reloadPlugin('filter_mate')
   ```

4. **Ajouter une couche PostgreSQL**

5. **Résultat attendu** :
   - ✅ **Aucun avertissement**
   - ✅ La couche PostgreSQL apparaît dans FilterMate
   - ✅ Le plugin s'active normalement
   - ✅ Les opérations de filtrage fonctionnent

6. **Vérifier les logs** :
   - Devrait contenir :
     ```
     INFO: FilterMate: PostgreSQL support enabled (psycopg2 available)
     ```

## Tests automatisés

Les tests unitaires sont dans `tests/test_postgresql_layer_handling.py` mais nécessitent un environnement de test QGIS complet.

Pour exécuter les tests (si pytest-qgis est configuré) :

```bash
pytest tests/test_postgresql_layer_handling.py -v
```

## Diagnostic rapide

Si le plugin ne se charge toujours pas, vérifier :

### 1. Import Python
Dans Console Python QGIS :
```python
import sys
print("Python version:", sys.version)
print("Python path:", sys.path)

# Test import
try:
    from filter_mate.modules import appUtils
    print("✓ Import OK")
    print("POSTGRESQL_AVAILABLE:", appUtils.POSTGRESQL_AVAILABLE)
except ImportError as e:
    print("✗ Import Error:", e)
```

### 2. Structure des fichiers
Vérifier que ces fichiers existent :
```
filter_mate/
  ├── __init__.py
  ├── filter_mate.py
  ├── filter_mate_app.py
  └── modules/
      ├── __init__.py
      └── appUtils.py
```

### 3. Logs QGIS
- **Menu** : Préférences → Journal des messages
- **Filtrer** : "FilterMate"
- **Chercher** : Erreurs (rouge), Avertissements (orange)

### 4. Console Python QGIS
Erreurs de chargement du plugin visibles dans la console au démarrage.

## Résolution de problèmes courants

### "No module named 'modules'"
**Cause** : Import incorrect (devrait être `from .modules` ou `from filter_mate.modules`)
**Solution** : Vérifier que tous les imports dans le plugin utilisent des imports relatifs

### "No module named 'qgis'"
**Cause** : Tentative d'exécution hors de QGIS
**Solution** : Exécuter uniquement dans la Console Python de QGIS

### "Plugin désactivé malgré corrections"
**Cause** : Plugin pas rechargé après modifications
**Solution** : 
```python
from qgis.utils import reloadPlugin
reloadPlugin('filter_mate')
```

## Fichiers modifiés

- ✅ `modules/appUtils.py` : Vérification POSTGRESQL_AVAILABLE
- ✅ `filter_mate_app.py` : Messages d'avertissement
- ✅ `tests/test_postgresql_layer_handling.py` : Tests unitaires
- ✅ `docs/fixes/POSTGRESQL_LAYER_ACTIVATION_FIX.md` : Documentation complète

## Prochaine étape

Si tout fonctionne, le fix peut être commité :

```bash
git add modules/appUtils.py filter_mate_app.py tests/test_postgresql_layer_handling.py
git commit -m "fix: Plugin désactivé avec couches PostgreSQL sans psycopg2

- Ajout vérification POSTGRESQL_AVAILABLE dans is_layer_source_available()
- Messages d'avertissement clairs quand PostgreSQL détecté sans psycopg2
- Log du statut PostgreSQL au démarrage
- Tests unitaires pour valider le comportement

Fixes #XX"
```
