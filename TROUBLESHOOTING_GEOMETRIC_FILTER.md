# 🔧 Guide de Diagnostic Rapide - Filtre Géométrique

## Problème: Les couches distantes ne sont pas filtrées

### ✅ Solution Rapide (3 étapes)

1. **Ouvrir Console Python QGIS** (`Ctrl + Alt + P`)

2. **Exécuter le diagnostic:**
   ```python
   exec(open(r'C:\Users\SimonDucorneau\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\filter_mate\DIAGNOSTIC_FILTER.py').read())
   ```

3. **Vérifier le résultat:**
   - ✓ Prédicats géométriques actifs: `True`
   - ✓ Prédicats cochés: `['intersects']`
   - ✓ Couches sélectionnées: `> 0`
   - ✓ `has_geometric_predicates: True`
   - ✓ `has_layers_to_filter: True`

### 🔍 Si le diagnostic révèle un problème:

#### Cas 1: `has_geometric_predicates: False`
**Solution:** Cliquez sur le bouton "Prédicats géométriques" dans l'interface FilterMate

#### Cas 2: `geometric_predicates: []` (liste vide)
**Solution:** Cochez au moins un prédicat (Intersects, Contains, etc.)

#### Cas 3: `has_layers_to_filter: False`
**Solution:** Cochez les couches à filtrer dans la liste "Layers to filter"

#### Cas 4: `task['layers'] count: 0`
**Solution:** 
1. Les couches PostgreSQL ne sont pas dans PROJECT_LAYERS
2. Exécutez: Bouton "Actualiser les couches" dans FilterMate
3. Ou exécutez en console:
   ```python
   from qgis.utils import plugins
   plugins['filter_mate'].filter_mate_app.manage_task('add_layers')
   ```

### 📋 Activer les Logs Détaillés

Si le diagnostic ne suffit pas, activez le logging complet:

```python
exec(open(r'C:\Users\SimonDucorneau\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\filter_mate\ENABLE_LOGGING.py').read())
```

Puis lancez votre filtre et cherchez dans la console:
- `🔍 Checking if distant layers should be filtered...`
- `⚠️ DISTANT LAYERS FILTERING SKIPPED` (si problème)
- `✓ COMPLETE SUCCESS` (si succès)

### 🐛 Codes Erreur Courants

| Message | Cause | Solution |
|---------|-------|----------|
| `has_geometric_predicates = FALSE` | Bouton prédicats non activé | Activer les prédicats géométriques |
| `No layers to filter` | Aucune couche cochée | Cocher des couches dans "Layers to filter" |
| `layers_count = 0` | Couches non organisées | Actualiser PROJECT_LAYERS |
| `geometric_predicates list: []` | Aucun prédicat coché | Cocher Intersects/Contains/etc. |

### 📝 Informations à Fournir pour Support

Si le problème persiste, fournir:
1. **Sortie du DIAGNOSTIC_FILTER.py**
2. **Logs après ENABLE_LOGGING.py** (chercher les 🔍 et ⚠️)
3. **Type de couches** (PostgreSQL, Shapefile, GeoPackage)
4. **Backend utilisé** (PostgreSQL, Spatialite, OGR)

---

## 🚀 Workflow Idéal

1. Ouvrir couche source PostgreSQL
2. Sélectionner une ou plusieurs features
3. **Activer "Prédicats géométriques"** ✅
4. **Cocher "Intersects"** (ou autre prédicat) ✅
5. **Cocher les couches à filtrer** dans la liste ✅
6. Cliquer "Apply Filter"
7. → Couche source ET couches distantes filtrées ✓

## 🎯 Vérification Rapide Avant Filtrage

Avant de cliquer "Apply Filter", vérifier:
- [ ] Bouton "Prédicats géométriques" activé (bleu/surligné)
- [ ] Au moins UN prédicat coché (Intersects, Contains, etc.)
- [ ] Au moins UNE couche cochée dans "Layers to filter"
- [ ] Couches PostgreSQL visibles dans "Layers to filter"

Si l'une de ces cases n'est pas cochée → Les couches distantes ne seront PAS filtrées!
