# Release Notes - FilterMate v2.8.16

**Date de sortie**: 6 janvier 2026  
**Type**: Patch (Correctif de bug critique)  
**Priorité**: Haute

## 🐛 Correction de bug

### CRITICAL - Backend OGR: Canvas non rafraîchi après filtrage

**Problème**: Après application d'un filtre sur une couche OGR (Shapefile, GeoPackage, CSV, etc.), la carte (canvas QGIS) ne s'actualisait pas visuellement pour afficher les features filtrées.

**Symptômes**:
- La carte restait figée sur l'affichage avant le filtrage
- Les nouvelles features filtrées n'apparaissaient pas visuellement
- Un zoom manuel ou un clic sur la couche était nécessaire pour forcer l'actualisation
- Les widgets UI (combobox, panel Exploring) étaient corrects mais pas l'affichage cartographique

**Impact utilisateur**: L'utilisateur pensait que le filtre n'avait pas fonctionné car la carte ne changeait pas visuellement, alors qu'en réalité le filtre était appliqué mais pas affiché.

**Cause technique**:
- Le backend OGR recharge le data provider après application du `subsetString`
- La fonction `filter_engine_task_completed()` rafraîchissait l'UI mais **n'appelait pas `triggerRepaint()`** sur la couche
- Le simple appel à `iface.mapCanvas().refresh()` était **insuffisant pour OGR** (contrairement à PostgreSQL/Spatialite)

**Solution implémentée**:
- Ajout de `triggerRepaint()` sur **source_layer** et **current_layer** avant le rafraîchissement du canvas
- Ordre critique respecté: `layer.triggerRepaint()` → `canvas.refresh()`
- Protection avec vérifications `isValid()` pour éviter les erreurs

**Code ajouté** (ligne ~3992 de filter_mate_app.py):
```python
# 3. v2.8.16: Force explicit layer repaint for OGR to ensure canvas displays filtered features
# OGR data provider reload requires explicit triggerRepaint() on BOTH source and current layer
logger.debug(f"v2.8.16: OGR filter completed - triggering layer repaint")
if source_layer and source_layer.isValid():
    source_layer.triggerRepaint()
if self.dockwidget.current_layer.isValid():
    self.dockwidget.current_layer.triggerRepaint()
# Force canvas refresh to ensure display is updated
self.iface.mapCanvas().refresh()
```

**Fichiers modifiés**:
- [filter_mate_app.py](filter_mate_app.py) - Ligne ~3992 - Ajout `triggerRepaint()` pour OGR
- [FIX_OGR_CANVAS_REFRESH_2026-01.md](docs/FIX_OGR_CANVAS_REFRESH_2026-01.md) - Documentation complète du fix

**Impact**:
- ✅ Canvas (carte) correctement rafraîchi après filtrage OGR
- ✅ Affichage visuel immédiat des features filtrées
- ✅ Complète le fix v2.8.15 pour une expérience OGR complète
- ✅ Aucune régression sur PostgreSQL/Spatialite (code activé uniquement pour OGR)

---

## 🔗 Relation avec v2.8.15

Cette version **complète** le fix v2.8.15 qui avait résolu:
- ✅ v2.8.15: Combobox vide après filtrage OGR
- ✅ v2.8.15: Panel Exploring non rafraîchi

La v2.8.16 ajoute:
- ✅ v2.8.16: Canvas (carte) rafraîchi après filtrage OGR

Les deux versions forment une **solution complète** pour le backend OGR.

---

## 🧪 Tests recommandés

### Test 1: Filtrage simple avec Shapefile
1. Charger un Shapefile avec > 100 features
2. Appliquer un filtre attributaire (ex: `population > 10000`)
3. ✅ Vérifier que la carte affiche **immédiatement** les features filtrées
4. ✅ Pas besoin de zoom manuel pour rafraîchir

### Test 2: Filtrage multi-étapes avec GeoPackage
1. Charger un GeoPackage
2. Appliquer un premier filtre spatial
3. ✅ Vérifier le rafraîchissement visuel
4. Activer "Add to existing filter" (combine AND)
5. Appliquer un second filtre attributaire
6. ✅ Vérifier que la carte se rafraîchit à chaque étape

### Test 3: Zoom auto après filtrage
1. Activer "Auto extent" (is_tracking) dans le panel Exploring
2. Appliquer un filtre OGR
3. ✅ Vérifier que le zoom s'ajuste ET que la carte affiche les features filtrées

### Test 4: Switch entre couches
1. Charger 2 couches OGR (A et B)
2. Filtrer couche A → vérifier rafraîchissement
3. Passer à couche B, la filtrer → vérifier rafraîchissement
4. Revenir à couche A → vérifier que l'affichage reste correct

---

## 📊 Compatibilité

- **QGIS**: 3.16+
- **Python**: 3.7+
- **Backends concernés**: OGR uniquement (Shapefile, GeoPackage, CSV, etc.)
- **Backends non affectés**: PostgreSQL, Spatialite (aucune régression)
- **OS**: Windows, Linux, macOS

---

## 📈 Performance

- **Impact**: Négligeable
- **Optimisation**: `triggerRepaint()` utilise le cache interne de QGIS
- **Scope**: Uniquement pour backend OGR (pas d'impact sur PostgreSQL/Spatialite)

---

## 🔗 Références

- **Issue**: Signalé par utilisateur le 6 janvier 2026
- **Documentation technique**: [FIX_OGR_CANVAS_REFRESH_2026-01.md](docs/FIX_OGR_CANVAS_REFRESH_2026-01.md)
- **Commits**: v2.8.16
- **Fixes liés**: 
  - v2.8.15: [FIX_OGR_COMBOBOX_EXPLORING_2026-01.md](docs/FIX_OGR_COMBOBOX_EXPLORING_2026-01.md)
  - [FIX_OGR_TEMP_LAYER_GC_2026-01.md](docs/FIX_OGR_TEMP_LAYER_GC_2026-01.md)

---

## 📝 Notes de migration

Aucune action requise de la part des utilisateurs. Le correctif s'applique automatiquement lors de la mise à jour du plugin vers v2.8.16.

---

## 🙏 Remerciements

Merci aux utilisateurs qui ont signalé ce problème et fourni les détails nécessaires pour le reproduire et le corriger rapidement.

---

**Prochaines étapes**: Validation utilisateur + préparation release v2.9.0 (features + optimisations)
