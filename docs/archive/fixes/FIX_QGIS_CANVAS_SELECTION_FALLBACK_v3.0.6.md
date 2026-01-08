# Fix: QGIS Canvas Selection Fallback v3.0.6

**Date**: 2026-01-07  
**Criticité**: 🔴 **CRITIQUE**  
**Issue**: 2ème filtre multi-step ne filtre pas les couches distantes quand widgets non synchronisés

---

## 🐛 Problème

**Symptôme** :
- Step 1: Filtre zone → Toutes les couches filtrées ✅
- Changement de couche source vers "ducts"
- Sélection multiple depuis le canvas QGIS
- Step 2: Filtre avec buffer → **Seulement la couche source filtrée** ❌
- Logs: "⚠️ SINGLE_SELECTION: Widget has no valid feature selected!"

**Attendu** : Couches distantes filtrées avec l'intersection des ducts sélectionnés  
**Réel** : Filtre annulé car `get_current_features()` retourne une liste vide

---

## 🔍 Root Cause Analysis

### Flux du Problème

1. **Step 1**: Filtre zone_mro → Toutes les couches filtrées ✅
2. **Changement de couche** → `current_layer_changed()` vers "ducts"
3. **Sélection canvas QGIS**: Utilisateur sélectionne plusieurs ducts
4. **Widgets NON synchronisés** car `is_selecting` n'est PAS activé pour "ducts"
5. **Step 2 déclenché** → `get_current_features()` appelé
6. **`current_exploring_groupbox` = "single_selection"** (pas basculé car pas de sync)
7. **Widget single_selection VIDE** → Pas de feature valide
8. **ABORT**: `get_task_parameters()` retourne `None` → Filtre non exécuté

### Code problématique (avant fix)

```python
# get_current_features() - branche single_selection
if input is None or (hasattr(input, 'isValid') and not input.isValid()):
    # Recovery from saved FID...
    else:
        # ❌ Retourne liste vide, filtre avorté!
        return [], ''
```

**Impact** : Quand `is_selecting` n'est pas activé, la sélection QGIS n'est pas synchronisée avec les widgets. Le filtre échoue silencieusement.

---

## ✅ Solution v3.0.6

### Fix get_current_features() - QGIS Canvas Selection Fallback

**Nouveau comportement** :
1. Si widget single_selection n'a pas de feature valide
2. Vérifier si QGIS a des features sélectionnées sur le canvas
3. Si 1 feature sélectionnée → Utiliser pour single_selection
4. Si > 1 features sélectionnées → Basculer vers multiple_selection et utiliser

**Code ajouté** (single_selection branch):
```python
# v3.0.6: Check if QGIS has selected features on canvas for current layer
qgis_selected = self.current_layer.selectedFeatures() if self.current_layer else []
if len(qgis_selected) > 0:
    logger.info(f"   🔄 SINGLE_SELECTION: Found {len(qgis_selected)} features selected in QGIS canvas!")
    
    if len(qgis_selected) == 1:
        # Use the single QGIS-selected feature
        input = qgis_selected[0]
        # Continue with normal processing
    else:
        # Multiple features selected - switch to multiple_selection mode
        features, expression = self.get_exploring_features(qgis_selected, True)
        return features, expression
else:
    # No QGIS selection either - return empty (abort filter)
    return [], ''
```

**Code ajouté** (multiple_selection branch):
```python
# v3.0.6: If still no input, try QGIS canvas selection as final fallback
if not input or len(input) == 0:
    qgis_selected = self.current_layer.selectedFeatures() if self.current_layer else []
    if len(qgis_selected) > 0:
        features, expression = self.get_exploring_features(qgis_selected, True)
        return features, expression
```

---

## 📋 Fichiers Modifiés

1. **filter_mate_dockwidget.py**
   - `get_current_features()` - branche single_selection (~ligne 7496-7545)
   - `get_current_features()` - branche multiple_selection (~ligne 7575-7595)
   - **Fix** : Ajout fallback vers sélection QGIS canvas quand widgets non synchronisés

---

## 🧪 Tests de Validation

### Scénario 1: Multi-Step sans is_selecting activé

**Setup** :
1. Step 1: Filtre zone (Polygon)
2. **Désactiver is_selecting** pour la couche "ducts"
3. Changer de couche vers "ducts" dans le combobox
4. **Sélectionner plusieurs ducts depuis le canvas QGIS** (pas depuis widget)
5. Lancer Step 2 avec buffer 1m

**Résultat Attendu** :
- Log: "🔄 SINGLE_SELECTION: Found X features selected in QGIS canvas!"
- Log: "🔄 AUTO-SWITCH: X features selected, using MULTIPLE_SELECTION mode"
- Toutes les couches distantes sont filtrées avec intersection ✅

### Scénario 2: Multi-Step avec groupbox multiple_selection

**Setup** :
1. Activer manuellement la groupbox multiple_selection
2. Widget non synchronisé (pas d'éléments cochés)
3. Sélectionner plusieurs features depuis le canvas QGIS
4. Lancer le filtre

**Résultat Attendu** :
- Log: "🔄 MULTIPLE_SELECTION: Using X features from QGIS canvas selection!"
- Filtre appliqué avec les features QGIS

---

## 💡 Notes Techniques

### Pourquoi ce problème survient ?

Le bouton `is_selecting` contrôle la synchronisation bidirectionnelle :
- **Activé** : Sélection canvas → Widget synchronisé → Filtre OK
- **Désactivé** : Sélection canvas → Widget NON synchronisé → Filtre ÉCHOUE

Cette situation est fréquente en multi-step filtering car chaque couche a son propre état `is_selecting`.

### Pourquoi le fix est sûr ?

1. Le fallback n'est activé QUE si widget est vide
2. La sélection QGIS est une source fiable de features
3. Les FIDs sont sauvegardés pour récupération future
4. Le cache exploring est mis à jour pour cohérence

### Compatibilité

- ✅ Compatible avec tous les backends (PostgreSQL, Spatialite, OGR)
- ✅ Pas de changement d'API externe
- ✅ Rétrocompatible avec versions précédentes
- ✅ Fonctionne avec/sans is_selecting activé

---

## 📊 Logs Attendus (succès)

```
get_current_features: groupbox='single_selection', layer='ducts'
   ⚠️ SINGLE_SELECTION: No valid feature in widget and no saved FID!
   🔄 SINGLE_SELECTION: Found 15 features selected in QGIS canvas!
   🔄 AUTO-SWITCH: 15 features selected, using MULTIPLE_SELECTION mode
   RESULT: 15 features, expression='fid IN (1234, 1235, ...)'
```

---

**Fix validé pour v3.0.6** - Améliore la robustesse du filtrage multi-step
