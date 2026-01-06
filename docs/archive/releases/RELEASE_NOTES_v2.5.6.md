# FilterMate v2.5.6 - Synchronisation Bidirectionnelle Améliorée

**Date de sortie** : 30 décembre 2025  
**Type** : Feature Enhancement + Amélioration UX  
**Priorité** : Moyenne

---

## 🎯 Nouveauté Principale : Synchronisation Bidirectionnelle Complète

### ✨ Synchronisation QGIS ↔ Widgets quand `is_selecting` est activé

La sélection entre le canvas QGIS et les widgets FilterMate (Feature Picker / Custom Feature Picker) est désormais **complètement bidirectionnelle** quand le bouton `is_selecting` est coché.

#### Comportement Précédent (v2.5.5 et antérieur)
- ✅ **Widgets → QGIS** : fonctionnel (sélection dans QGIS quand widget change)
- ❌ **QGIS → Widgets** : additive seulement pour Multiple Selection
  - Cochait les features sélectionnées dans QGIS
  - Ne décochait JAMAIS les features non sélectionnées
  - Résultat : incohérence entre sélection QGIS et widget

#### Nouveau Comportement (v2.5.6)
- ✅ **Widgets → QGIS** : inchangé (fonctionnel)
- ✅ **QGIS → Widgets** : synchronisation COMPLÈTE
  - **Single Selection** : affiche la feature si exactement 1 sélectionnée
  - **Multiple Selection** : reflète EXACTEMENT la sélection QGIS
    - ✅ Coche les features sélectionnées
    - ✅ Décoche les features NON sélectionnées
- 🎯 Résultat : widgets et canvas parfaitement synchronisés

---

## 🔧 Modifications Techniques

### Architecture de Synchronisation

```
┌─────────────────────────────────────────────┐
│     QGIS Layer Selection (Canvas)           │
└──────────────┬──────────────────────────────┘
               │ selectionChanged signal
               │
               ▼ SI is_selecting = TRUE
┌─────────────────────────────────────────────┐
│  on_layer_selection_changed()               │
│  - Vérifie is_selecting actif               │
│  - Vérifie _syncing_from_qgis flag          │
│  - Appelle _sync_widgets_from_qgis()        │
└──────────────┬──────────────────────────────┘
               │
               ├──► Single Selection?
               │    └─► setFeature(feature)
               │         blockSignals pendant update
               │
               └──► Multiple Selection?
                    └─► Sync COMPLÈTE:
                         - Check sélectionnées
                         - Uncheck non-sélectionnées
                         - _syncing_from_qgis = True
                         - emit signal
                         - _syncing_from_qgis = False
```

### Protection Anti-Boucles Infinies

Nouveau flag `_syncing_from_qgis` empêche les récursions :

```python
# Dans on_layer_selection_changed
if self._syncing_from_qgis:
    return  # Skip si sync en cours

# Dans _sync_multiple_selection_from_qgis
self._syncing_from_qgis = True
try:
    # Update widgets + emit signal
    multiple_widget.updatingCheckedItemList.emit(...)
finally:
    self._syncing_from_qgis = False

# Dans exploring_features_changed
if not self._syncing_from_qgis:
    # Update QGIS selection
```

---

## 📋 Changements de Comportement

### Mode Single Selection

**Avant et Après (inchangé)** :
- Sync si exactement 1 feature sélectionnée dans QGIS
- Vérification pour éviter updates inutiles

### Mode Multiple Selection

**Avant v2.5.6 (additive)** :
```python
if feature_id in selected_ids:
    if item.checkState() != Qt.Checked:
        item.setCheckState(Qt.Checked)
# Ne décoche JAMAIS → incohérence
```

**v2.5.6 (complète)** :
```python
if feature_id in selected_ids:
    item.setCheckState(Qt.Checked)  # Coche sélectionnées
else:
    item.setCheckState(Qt.Unchecked)  # Décoche non-sélectionnées
# Reflète EXACTEMENT QGIS
```

### Bouton `is_selecting`

**Rôle (inchangé mais clarifié)** :
- ✅ Active synchronisation **bidirectionnelle**
- ✅ Widgets → QGIS : toujours actif si is_selecting = True
- ✅ QGIS → Widgets : désormais synchronisation complète si is_selecting = True
- ❌ Si is_selecting = False : aucune synchronisation

---

## 🎨 Améliorations UX

### Scénario d'Utilisation Typique

**Workflow Amélioré** :
1. Activer `is_selecting` ✅
2. Sélectionner features dans canvas QGIS
3. **Nouveau** : Widget reflète EXACTEMENT la sélection
4. Modifier sélection dans canvas (ajouter/supprimer features)
5. **Nouveau** : Widget se met à jour automatiquement
6. Filtrer/exporter les features sélectionnées

**Avantages** :
- 🎯 Cohérence parfaite canvas ↔ widgets
- ⚡ Workflow fluide : sélection → filtrage immédiat
- 🔄 Synchronisation temps réel bidirectionnelle

---

## 🐛 Corrections de Bugs

### Protection Contre Boucles Infinies

**Problème identifié** :
```
QGIS selection change → update widget → emit signal 
→ exploring_features_changed → update QGIS → BOUCLE INFINIE
```

**Solution implémentée** :
```python
# Flag _syncing_from_qgis bloque récursions
if self._syncing_from_qgis:
    return  # Ne re-déclenche pas la synchronisation
```

### Optimisations Performance

- Vérification avant update (compare feature.id())
- Blocage signaux temporaire (blockSignals)
- Compteurs de changements (update seulement si nécessaire)

---

## 📊 Fichiers Modifiés

| Fichier | Modifications | Lignes |
|---------|---------------|--------|
| `filter_mate_dockwidget.py` | 5 méthodes modifiées | ~200 |

### Détail des Modifications

1. **`__init__`** : Ajout flag `_syncing_from_qgis`
2. **`on_layer_selection_changed()`** : Protection anti-boucles
3. **`_sync_widgets_from_qgis_selection()`** : Documentation mise à jour
4. **`_sync_single_selection_from_qgis()`** : Optimisations
5. **`_sync_multiple_selection_from_qgis()`** : Sync complète (check + uncheck)
6. **`exploring_features_changed()`** : Vérification flag anti-boucles

---

## 🧪 Tests Recommandés

### Test 1 : Synchronisation Bidirectionnelle
```
1. Activer is_selecting
2. Sélectionner 3 features dans canvas
3. ✅ Vérifier 3 features cochées dans widget
4. Désélectionner 1 feature dans canvas
5. ✅ Vérifier 1 feature décochée dans widget
6. Sélectionner dans widget
7. ✅ Vérifier update dans canvas
```

### Test 2 : Protection Anti-Boucles
```
1. Activer is_selecting
2. Sélectionner rapidement 10 features
3. ✅ Pas de freeze/lag
4. ✅ Logs : "Skipping (sync in progress)"
5. ✅ Synchronisation correcte
```

### Test 3 : Mode Single Selection
```
1. Activer is_selecting
2. Sélectionner 1 feature dans canvas
3. ✅ Feature affichée dans widget
4. Sélectionner 2 features
5. ✅ Widget non modifié (nécessite exactement 1)
```

---

## 🔄 Compatibilité

- ✅ **QGIS** : 3.0+
- ✅ **Python** : 3.7+
- ✅ **Backends** : PostgreSQL, Spatialite, OGR
- ✅ **Rétrocompatibilité** : Aucun changement breaking

---

## 🚀 Migration depuis v2.5.5

**Aucune action requise** - La mise à jour est transparente.

### Changements de comportement

1. **Multiple Selection** : synchronisation complète au lieu d'additive
   - Décoche maintenant les features non sélectionnées
   - Reflète exactement la sélection QGIS

2. **Protection anti-boucles** : nouveau flag interne
   - Empêche récursions lors de sync bidirectionnelle
   - Transparent pour l'utilisateur

### Bénéfices immédiats

- ✅ Widgets toujours cohérents avec canvas
- ✅ Synchronisation complète et fiable
- ✅ Pas de comportement inattendu

---

## 📚 Documentation Technique

Voir [SYNC_ARCHITECTURE_v2.5.6.md](./SYNC_ARCHITECTURE_v2.5.6.md) pour:
- Architecture détaillée
- Diagrammes de flux
- Benchmarks performance
- Guide debugging

---

## 👥 Contributeurs

- **Simon Ducournau** - Implémentation synchronisation bidirectionnelle complète

---

**Version suivante prévue** : v2.5.7 (corrections bugs éventuels)  
**Statut** : ✅ Prêt pour production
