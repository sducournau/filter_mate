# Release Notes - FilterMate v2.8.15

**Date de sortie**: 6 janvier 2026  
**Type**: Patch (Correctif de bugs)  
**Priorité**: Haute

## 🐛 Corrections de bugs

### CRITICAL - QgsMessageLog.logMessage TypeError

**Problème**: Erreur récurrente lors de l'utilisation du backend OGR empêchant l'affichage correct des messages de log:

```
TypeError: QgsMessageLog.logMessage(): argument 2 has unexpected type 'MessageLevel'
```

**Cause technique**:
- Utilisation incorrecte de `Qgis.MessageLevel(0)` au lieu de la constante `Qgis.Info`
- Arguments passés dans le mauvais ordre : `(message, level)` au lieu de `(message, tag, level)`
- La signature correcte de QgsMessageLog.logMessage est : `logMessage(message: str, tag: str, level: Qgis.MessageLevel)`

**Solution implémentée**:
- Remplacement de tous les `Qgis.MessageLevel(0)` par `Qgis.Info` (constante appropriée)
- Correction de l'ordre des arguments pour respecter la signature API QGIS

**Fichiers modifiés**:
- [modules/backends/ogr_backend.py](modules/backends/ogr_backend.py) - 18 usages corrigés
- [modules/backends/spatialite_cache.py](modules/backends/spatialite_cache.py) - 2 usages corrigés
- [config/config.py](config/config.py) - 1 usage corrigé

**Impact**:
- ✅ Suppression de toutes les exceptions TypeError lors du logging
- ✅ Messages de debug et de diagnostic correctement affichés dans le panneau Messages QGIS
- ✅ Stabilité accrue du backend OGR pour tous les types de couches

---

### Backend OGR - Interface désynchronisée après filtrage

**Problème**: Lors de l'utilisation du backend OGR (Shapefile, GeoPackage, CSV, etc.), deux problèmes d'affichage apparaissaient après application d'un filtre:

1. **Combobox de couche source vide**
   - La liste déroulante montrant la couche active (`comboBox_filtering_current_layer`) se réinitialisait à vide
   - L'utilisateur ne voyait plus quelle couche était sélectionnée
   - Nécessitait de cliquer manuellement sur la couche dans les Layers pour restaurer l'affichage

2. **Panel Exploring non rafraîchi**
   - Le widget "Multiple Selection" affichait encore les features **avant le filtrage**
   - Les nouvelles features filtrées n'apparaissaient pas dans la liste
   - La sélection de features pouvait cibler des entités qui n'existaient plus

**Cause technique**:
- Le backend OGR utilise un mécanisme de rechargement du data provider après application du `subsetString`
- Ce rechargement invalide les références des widgets Qt qui pointent vers l'ancienne instance du provider
- Les widgets (combobox, liste de features) ne détectent pas automatiquement ce changement

**Solution implémentée**:
- Ajout d'une synchronisation explicite dans `filter_engine_task_completed()` pour le backend OGR
- Restauration automatique de la combobox avec la couche actuelle
- Rechargement forcé des widgets Exploring (`_reload_exploration_widgets()`) pour afficher les features filtrées

**Fichiers modifiés**:
- [filter_mate_app.py](filter_mate_app.py) - Ligne ~3988 - Ajout synchronisation post-filtrage OGR
- [FIX_OGR_COMBOBOX_EXPLORING_2026-01.md](docs/FIX_OGR_COMBOBOX_EXPLORING_2026-01.md) - Documentation complète du fix

**Impact**:
- ✅ Combobox toujours synchronisée avec la couche active après filtrage OGR
- ✅ Panel Exploring affiche correctement les features filtrées
- ✅ Expérience utilisateur cohérente entre les 3 backends (PostgreSQL/Spatialite/OGR)
- ✅ Pas de régression sur les autres backends (code activé uniquement pour OGR)

---

## 🧪 Tests recommandés

### Test 1: Filtrage simple OGR
1. Charger un Shapefile ou GeoPackage dans QGIS
2. Appliquer un filtre attributaire simple (ex: `population > 10000`)
3. Vérifier que la combobox affiche toujours la couche source
4. Vérifier que le panel "Multiple Selection" affiche uniquement les features filtrées

### Test 2: Filtrage multi-étapes
1. Charger une couche OGR
2. Appliquer un premier filtre
3. Activer le mode "Add to existing filter" (combine operator AND)
4. Appliquer un second filtre
5. Vérifier que l'interface reste stable à chaque étape

### Test 3: Switch de couches
1. Filtrer une couche OGR (couche A)
2. Changer pour une autre couche (couche B)
3. Revenir sur la couche A
4. Vérifier que la combobox et le panel Exploring affichent correctement la couche A filtrée

---

## 📊 Compatibilité

- **QGIS**: 3.16+
- **Python**: 3.7+
- **Backends concernés**: OGR (Shapefile, GeoPackage, CSV, etc.)
- **OS**: Windows, Linux, macOS

---

## 🔗 Références

- **Issue**: Signalé par utilisateur le 6 janvier 2026
- **Documentation technique**: [FIX_OGR_COMBOBOX_EXPLORING_2026-01.md](docs/FIX_OGR_COMBOBOX_EXPLORING_2026-01.md)
- **Commits**: v2.8.15
- **Pattern similaire**: FIX_OGR_TEMP_LAYER_GC_2026-01.md (problème de référence OGR)

---

## 📝 Notes de migration

Aucune action requise de la part des utilisateurs. Le correctif s'applique automatiquement lors de la mise à jour du plugin.

---

## 🙏 Remerciements

Merci aux utilisateurs qui ont signalé ce problème et fourni les détails nécessaires pour le reproduire et le corriger.
