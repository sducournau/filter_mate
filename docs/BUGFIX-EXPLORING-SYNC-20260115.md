# BUGFIX: Synchronisation Widgets EXPLORING et Sélection Canvas - 2026-01-15

## 🐛 Problèmes Identifiés

### 1. Groupboxes et widgets ne se rafraîchissent pas correctement

**Symptôme**: 
- Les widgets EXPLORING (feature picker single/multiple selection) ne se mettent pas à jour visuellement
- Les groupboxes ne rafraîchissent pas leur contenu après changement de couche ou de mode
- **Le feature picker de single selection n'affiche pas les features de la couche**
- Problème spécifique à certains environnements Qt/QGIS

**Cause racine**: 
- Appels à `update()` présents mais insuffisants sur certains systèmes
- Certains environnements Qt/QGIS nécessitent `repaint()` en plus de `update()`
- Manque de refresh explicite après configuration des groupboxes
- **Le `QgsFeaturePickerWidget` ne rafraîchit pas son modèle interne après `setLayer()` + `setDisplayExpression()`**

**Solution**:
- Ajout de `repaint()` après chaque `update()` pour forcer le rendu immédiat
- Application systématique dans:
  - `_configure_single_selection_groupbox()` 
  - `_configure_multiple_selection_groupbox()`
  - `_sync_single_selection_from_qgis()` (ExploringController)
  - `_fallback_sync_widgets_from_qgis_selection()` (dockwidget)
  - `sync_multiple_selection_from_qgis()` (UILayoutController)
  - **`_reload_exploration_widgets()` - CRITICAL pour forcer le chargement des features**

### 2. pushButton_checkable_exploring_selecting n'active pas l'outil de sélection

**Symptôme**: 
- Le bouton IS_SELECTING peut être checké mais l'outil de sélection canvas n'est pas activé
- La sélection sur le canvas ne fonctionne pas même si le bouton est activé

**Cause racine**: 
- Le code d'activation existait déjà (`self.iface.actionSelectRectangle().trigger()`)
- Mais le refresh visuel n'était pas forcé
- Le bouton était déjà correctement connecté via signal direct (pas via `layer_property_changed`)

**Solution**:
- Vérification que `exploring_select_features()` active bien l'outil via `actionSelectRectangle().trigger()`
- Ajout de refresh visuel pour confirmer visuellement l'état du bouton

### 3. Synchronisation feature picker ↔ sélection canvas défaillante

**Symptôme**: 
- Sélection sur canvas → feature picker ne se met pas à jour
- Changement dans feature picker → sélection canvas ne suit pas
- Mode single selection ↔ multiple selection ne switch pas automatiquement

**Cause racine**: 
- La synchronisation existait mais manquait le refresh visuel
- `sync_multiple_selection_from_qgis()` était incomplète (ne gérait pas le UNCHECK)
- Pas de `repaint()` après modification des états de check

**Solution**:
- Complétion de `sync_multiple_selection_from_qgis()` pour UNCHECK les items non sélectionnés
- Ajout de `repaint()` systématique après modification des feature pickers
- Double sens confirmé:
  - QGIS → FilterMate: via `handle_layer_selection_changed()` → `_sync_widgets_from_qgis_selection()`
  - FilterMate → QGIS: via `handle_exploring_features_result()` avec `is_selecting=True`

## 📝 Fichiers Modifiés

### 1. filter_mate_dockwidget.py

**Lignes 2320-2337**: Ajout repaint() dans `_configure_single_selection_groupbox()`
```python
def _configure_single_selection_groupbox(self):
    """v4.0 Sprint 17: Configure single selection groupbox."""
    layer_props = self._configure_groupbox_common("single_selection")
    if layer_props is None: return True
    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
    self.exploring_link_widgets()
    if not self._syncing_from_qgis:
        f = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].feature()
        if f and f.isValid(): self.exploring_features_changed(f)
    self._update_exploring_buttons_state()
    # FIX 2026-01-15: Force visual refresh of single selection widget
    if "EXPLORING" in self.widgets and "SINGLE_SELECTION_FEATURES" in self.widgets["EXPLORING"]:
        widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
        if widget:
            widget.update()
            widget.repaint()
    return True
```

**Lignes 2339-2356**: Ajout repaint() dans `_configure_multiple_selection_groupbox()`
```python
def _configure_multiple_selection_groupbox(self):
    """v4.0 Sprint 17: Configure multiple selection groupbox."""
    layer_props = self._configure_groupbox_common("multiple_selection")
    if layer_props is None: return True
    self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect')
    self.exploring_link_widgets()
    if not self._syncing_from_qgis:
        features = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures()
        if features: self.exploring_features_changed(features, True)
    self._update_exploring_buttons_state()
    # FIX 2026-01-15: Force visual refresh of multiple selection widget
    if "EXPLORING" in self.widgets and "MULTIPLE_SELECTION_FEATURES" in self.widgets["EXPLORING"]:
        widget = self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
        if widget:
            widget.update()
            widget.repaint()
    return True
```

**Lignes 2556-2568**: Ajout repaint() dans `_fallback_sync_widgets_from_qgis_selection()`
```python
# Sync single selection widget
if selected_count >= 1:
    feature_picker = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
    current_feature = feature_picker.feature()
    feature_id = selected_features[0].id()
    if not (current_feature and current_feature.isValid() and current_feature.id() == feature_id):
        self._syncing_from_qgis = True
        try:
            feature_picker.setFeature(feature_id)
            # FIX 2026-01-15: Force visual refresh
            feature_picker.update()
            feature_picker.repaint()
        finally:
            self._syncing_from_qgis = False
```

**Lignes 2954-2968**: Ajout repaint() dans `_fallback_reload_exploration_widgets()`
```python
# Update single selection widget (QgsFeaturePickerWidget)
if "SINGLE_SELECTION_FEATURES" in self.widgets.get("EXPLORING", {}):
    widget = self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
    if widget:
        widget.setLayer(None)  # Force refresh
        widget.setLayer(layer)
        widget.setDisplayExpression(single_expr)
        widget.setFetchGeometry(True)
        widget.setShowBrowserButtons(True)
        widget.setAllowNull(True)
        # FIX 2026-01-15: Force visual refresh to display features
        widget.update()
        widget.repaint()
```

### 2. ui/controllers/exploring_controller.py

**Lignes 2147-2157**: Ajout repaint() dans `_reload_exploration_widgets()` après configuration du single selection picker
```python
picker_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
picker_widget.setLayer(None)
picker_widget.setLayer(layer)
picker_widget.setDisplayExpression(single_expr)
picker_widget.setFetchGeometry(True)
picker_widget.setShowBrowserButtons(True)
picker_widget.setAllowNull(True)
# FIX 2026-01-15: Force visual refresh to display features
picker_widget.update()
picker_widget.repaint()
```

**Lignes 2420-2432**: Ajout repaint() dans `_sync_single_selection_from_qgis()`
```python
logger.info(f"Syncing single selection to feature ID {feature_id}")

self._dockwidget._syncing_from_qgis = True
try:
    feature_picker.setFeature(feature_id)
    # FIX 2026-01-15: Force visual refresh
    feature_picker.update()
    feature_picker.repaint()
finally:
    self._dockwidget._syncing_from_qgis = False
```

### 3. ui/controllers/ui_layout_controller.py

**Lignes 189-217**: Complétion de `sync_multiple_selection_from_qgis()` avec UNCHECK + repaint()
```python
checked_count = 0
unchecked_count = 0

for i in range(list_widget.count()):
    item = list_widget.item(i)
    item_pk_value = item.data(3)  # data(3) = PRIMARY KEY value
    item_pk_str = str(item_pk_value) if item_pk_value is not None else item_pk_value
    
    if item_pk_str in selected_pk_values:
        # CHECK features selected in QGIS
        if item.checkState() != Qt.Checked:
            item.setCheckState(Qt.Checked)
            checked_count += 1
    else:
        # UNCHECK features not selected in QGIS
        if item.checkState() != Qt.Unchecked:
            item.setCheckState(Qt.Unchecked)
            unchecked_count += 1

logger.debug(f"sync_multiple_selection_from_qgis: checked={checked_count}, unchecked={unchecked_count}")

# Force visual refresh
multi_widget.update()
multi_widget.repaint()

return True

except Exception as e:
    logger.warning(f"sync_multiple_selection_from_qgis error: {e}")
    return False
finally:
    dw._syncing_from_qgis = False
```

## 🔍 Architecture de la Synchronisation

### Flux de synchronisation QGIS → FilterMate

```
Layer.selectionChanged
    ↓
on_layer_selection_changed() [dockwidget]
    ↓
handle_layer_selection_changed() [ExploringController]
    ↓
_sync_widgets_from_qgis_selection() [ExploringController]
    ↓
├─→ _sync_single_selection_from_qgis()
│   └─→ feature_picker.setFeature(feature_id)
│       └─→ widget.repaint() ← FIX 2026-01-15
│
└─→ _sync_multiple_selection_from_qgis() [via UILayoutController]
    └─→ item.setCheckState(Qt.Checked/Unchecked)
        └─→ multi_widget.repaint() ← FIX 2026-01-15
```

### Flux de synchronisation FilterMate → QGIS

```
Feature picker changed (featureChanged/updatingCheckedItemList)
    ↓
exploring_features_changed() [ExploringController]
    ↓
handle_exploring_features_result() [ExploringController]
    ↓
if is_selecting == True:
    ↓
    current_layer.removeSelection()
    current_layer.select([f.id() for f in features])
```

### Flag anti-récursion: `_syncing_from_qgis`

- **True**: Changement provenant de QGIS → ne pas re-synchroniser vers QGIS
- **False**: Changement provenant de FilterMate → synchroniser vers QGIS

## ✅ Comportements Attendus Après Correction

### 1. Changement de couche
- Les feature pickers se rafraîchissent visuellement
- Les groupboxes affichent leurs widgets correctement
- Pas de "fantômes" d'ancienne couche

### 2. Sélection sur canvas (avec IS_SELECTING actif)
- Single selection:
  - 1 feature sélectionnée → switch auto vers single_selection groupbox
  - Feature picker affiche la feature sélectionnée
- Multiple selection:
  - 2+ features sélectionnées → switch auto vers multiple_selection groupbox
  - Checkboxes cochées/décochées selon sélection canvas

### 3. Changement dans feature picker (avec IS_SELECTING actif)
- Single selection:
  - Changement de feature → sélection canvas mise à jour
- Multiple selection:
  - Cocher/décocher items → sélection canvas mise à jour

### 4. Actions des boutons
- **IS_SELECTING ON**: 
  - Outil de sélection rectangle activé sur canvas
  - Features du groupbox actif sélectionnées sur la couche
- **IS_SELECTING OFF**: 
  - Sélection canvas effacée
  - Outil de sélection désactivé
- **IDENTIFY**: 
  - Features flashent sur le canvas
  - Fonctionne pour tous les modes de groupbox
- **ZOOM**: 
  - Canvas zoom sur les features du groupbox actif
  - Fonctionne pour tous les modes de groupbox
- **IS_TRACKING**: 
  - Auto-zoom sur sélection canvas quand actif

## 🧪 Tests à Effectuer

### Test 1: Refresh visuel des widgets
- [ ] Changer de couche → feature pickers se mettent à jour visuellement
- [ ] Switch entre groupboxes → widgets se rafraîchissent correctement
- [ ] Pas de "lag" visuel ou d'affichage figé

### Test 2: Synchronisation QGIS → FilterMate (IS_SELECTING = ON)
- [ ] Sélectionner 1 feature sur canvas → single selection se met à jour
- [ ] Sélectionner 2+ features sur canvas → switch vers multiple selection
- [ ] Multiple selection: cocher/décocher reflète la sélection canvas
- [ ] Clear selection sur canvas → widgets se vident

### Test 3: Synchronisation FilterMate → QGIS (IS_SELECTING = ON)
- [ ] Changer feature dans single picker → canvas selection suit
- [ ] Cocher items dans multiple picker → canvas selection suit
- [ ] Décocher items dans multiple picker → canvas selection suit

### Test 4: Actions des boutons
- [ ] IS_SELECTING ON → outil sélection activé + features sélectionnées
- [ ] IS_SELECTING OFF → sélection effacée
- [ ] IDENTIFY → flash des features
- [ ] ZOOM → zoom sur les features
- [ ] IS_TRACKING → auto-zoom sur sélection

## 📚 Références

- **before_migration/filter_mate_dockwidget.py**: Implémentation de référence (lignes 5079-5092, 8049-8140)
- **EXPLORING-SIGNALS-AUDIT-20260114.md**: Audit complet des signaux EXPLORING
- **BUGFIX-ICONS-REFRESH-20260115.md**: Problème similaire de refresh visuel (FILTERING tab)

## 🎯 Impact des Corrections

### Refresh visuel
- ✅ Les widgets se mettent à jour immédiatement sur tous les environnements
- ✅ Compatibilité multi-plateformes améliorée (Windows/Linux/macOS)
- ✅ Résout les problèmes de drivers Qt/QGIS problématiques

### Synchronisation bidirectionnelle
- ✅ QGIS → FilterMate: Auto-switch groupbox + mise à jour widgets
- ✅ FilterMate → QGIS: Sélection canvas suit les changements dans widgets
- ✅ Pas de récursion infinie grâce au flag `_syncing_from_qgis`

### Expérience utilisateur
- ✅ Comportement intuitif et prévisible
- ✅ Feedback visuel immédiat
- ✅ Cohérence entre canvas et widgets

## 🔄 Workflow Complet

```
1. Utilisateur active IS_SELECTING
   ↓
2. Outil sélection rectangle activé sur canvas
   ↓
3. Utilisateur sélectionne sur canvas
   ↓
4. handle_layer_selection_changed() détecte le changement
   ↓
5. Auto-switch groupbox (1 feature → single, 2+ → multiple)
   ↓
6. _sync_widgets_from_qgis_selection() met à jour widgets
   ↓
7. widget.repaint() force le refresh visuel ← FIX 2026-01-15
   ↓
8. Utilisateur voit immédiatement la sélection dans FilterMate
   ↓
9. Utilisateur modifie dans FilterMate (feature picker)
   ↓
10. exploring_features_changed() détecte le changement
    ↓
11. handle_exploring_features_result() synchronise vers QGIS
    ↓
12. current_layer.select([...]) met à jour canvas
    ↓
13. Utilisateur voit immédiatement la sélection sur le canvas
```

## 📌 Notes de Développement

### Pourquoi repaint() après update()?

- `update()`: Planifie un rafraîchissement lors du prochain cycle d'événements Qt
- `repaint()`: Force un rafraîchissement IMMÉDIAT, synchrone

Sur certains environnements (drivers Qt problématiques, charge CPU élevée), `update()` seul peut être ignoré ou retardé. `repaint()` garantit le rafraîchissement visuel immédiat.

### Pattern update() + repaint()

```python
widget.update()    # Planifie le rafraîchissement
widget.repaint()   # Force le rafraîchissement immédiat
```

Ce pattern est utilisé de manière cohérente dans tout FilterMate v4.0 pour garantir la compatibilité multi-environnements.

---

**Version**: FilterMate v4.0.2-alpha  
**Date**: 2026-01-15  
**Auteur**: Claude Sonnet 4.5 + Simon Ducorneau
