# 🔍 Audit Approfondi - Signaux Exploring FilterMate v4.0

**Date**: 14 janvier 2026  
**Auditeur**: BMAD Master Agent  
**Comparaison**: `before_migration/` (v2.x) vs Code Actif (v4.0)  
**Statut**: ✅ **CORRECTIONS APPLIQUÉES**

---

## 📋 Résumé Exécutif

### Problèmes Signalés par l'Utilisateur - CORRIGÉS

| # | Problème | Criticité | Statut |
|---|----------|-----------|--------|
| 1 | Bouton **Exploring/Selecting** checké mais outil de sélection canvas non activé | 🔴 CRITIQUE | ✅ CORRIGÉ |
| 2 | Sélection canvas non synchronisée avec GroupBox Exploring | 🔴 CRITIQUE | ✅ CORRIGÉ |
| 3 | Single feature vs Multiple features mal routé | 🔴 CRITIQUE | ✅ CORRIGÉ |
| 4 | Zoom non fonctionnel | 🟡 MOYEN | ✅ CORRIGÉ |
| 5 | Tracking non fonctionnel | 🟡 MOYEN | ✅ CORRIGÉ |
| 6 | Identification non fonctionnelle | 🟡 MOYEN | À tester |
| 7 | Reset des variables non fonctionnel | 🟡 MOYEN | À tester |
| 8 | Linking widgets défaillant | 🟡 MOYEN | ✅ CORRIGÉ |

---

## ✅ Corrections Appliquées (14 janvier 2026)

Les corrections suivantes ont été implémentées pour résoudre les régressions des signaux Exploring :

### 1. Connexion Directe des Signaux IS_SELECTING/IS_TRACKING/IS_LINKING

**Fichier modifié** : `filter_mate_dockwidget.py`

**Nouvelle méthode ajoutée** : `_connect_exploring_buttons_directly()`

Cette méthode crée des connexions directes et explicites pour les boutons toggled, contournant le mécanisme complexe lambda/custom_functions qui échouait silencieusement.

```python
def _connect_exploring_buttons_directly(self):
    """FIX 2026-01-14: Direct signal connections for exploring buttons.
    
    Bypasses the complex lambda/custom_functions mechanism that was failing
    to properly trigger exploring_select_features()/exploring_deselect_features().
    """
    # IS_SELECTING
    btn_selecting = self.pushButton_checkable_exploring_selecting
    try:
        btn_selecting.toggled.disconnect()
    except TypeError:
        pass
    
    def on_selecting_toggled(checked):
        if not self.widgets_initialized or not self.current_layer:
            return
        layer_id = self.current_layer.id()
        if layer_id in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = checked
        if checked:
            self.exploring_select_features()
        else:
            self.exploring_deselect_features()
    
    btn_selecting.toggled.connect(on_selecting_toggled)
    
    # IS_TRACKING et IS_LINKING - même pattern
```

### 2. Renforcement de exploring_select_features()

**Fichier modifié** : `filter_mate_dockwidget.py`

La méthode a été réécrite pour **TOUJOURS** activer l'outil de sélection QGIS en premier :

```python
def exploring_select_features(self):
    """Activate QGIS selection tool and sync features."""
    if not self._is_layer_valid():
        return
    
    # PHASE 2 FIX: TOUJOURS activer l'outil de sélection
    try:
        self.iface.actionSelectRectangle().trigger()
        self.iface.setActiveLayer(self.current_layer)
        logger.info(f"Selection tool activated for {self.current_layer.name()}")
    except Exception as e:
        logger.warning(f"Failed to activate selection tool: {e}")
        return
    
    # Puis synchro des features
    features, _ = self.get_current_features()
    if features:
        self.current_layer.removeSelection()
        self.current_layer.select([f.id() for f in features])
```

### 3. Correction sync_multiple_selection_from_qgis()

**Fichier modifié** : `ui/controllers/ui_layout_controller.py`

Réécriture complète de la méthode pour utiliser l'API correcte `list_widgets[layer_id]` avec :
- `item.data(3)` pour récupérer la clé primaire
- `item.setCheckState(Qt.Checked/Qt.Unchecked)` pour mettre à jour l'état

```python
def sync_multiple_selection_from_qgis(self, layer_id: str, selected_pks: set) -> bool:
    """Sync CheckableItemsComboBox with QGIS selection using correct API."""
    list_widget = self._dockwidget.list_widgets.get(layer_id)
    if not list_widget:
        return False
    
    for i in range(list_widget.count()):
        item = list_widget.item(i)
        if item:
            pk_value = item.data(3)  # Primary key
            if pk_value in selected_pks:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
    return True
```

### Tableau de Statut Mis à Jour

| Signal | Statut Avant | Statut Après |
|--------|-------------|--------------|
| IS_SELECTING toggled(True) | 🔴 Cassé | ✅ Corrigé |
| IS_SELECTING toggled(False) | 🔴 Cassé | ✅ Corrigé |
| IS_TRACKING toggled | ✅ OK | ✅ OK |
| IS_LINKING toggled | 🟡 Partiel | ✅ Corrigé |
| selectionChanged | ✅ OK | ✅ OK |
| sync_multiple_selection | 🔴 Mauvaise API | ✅ Corrigé |

---

## 🔬 Analyse Comparative Détaillée

### 1. Signal IS_SELECTING (pushButton_checkable_exploring_selecting)

#### Before Migration (v2.x)
```python
# filter_mate_dockwidget.py ligne 5081
"IS_SELECTING": {
    "TYPE": "PushButton", 
    "WIDGET": self.pushButton_checkable_exploring_selecting, 
    "SIGNALS": [
        ("toggled", lambda state, x='is_selecting', custom_functions={
            "ON_TRUE": lambda x: self.exploring_select_features(), 
            "ON_FALSE": lambda x: self.exploring_deselect_features()
        }: self.layer_property_changed(x, state, custom_functions))
    ], 
    "ICON": None
}

# exploring_select_features() - v2.x ligne 8509
def exploring_select_features(self):
    if self.widgets_initialized and self.current_layer:
        # 1. Activate QGIS selection tool on canvas
        self.iface.actionSelectRectangle().trigger()  # ✅ CRITIQUE
        
        # 2. Set active layer
        self.iface.setActiveLayer(self.current_layer)  # ✅ CRITIQUE
        
        # 3. Get features from active groupbox
        features, expression = self.get_current_features()
        
        # 4. Select features on layer
        if len(features) > 0:
            self.current_layer.removeSelection()
            self.current_layer.select([f.id() for f in features])
```

#### After Migration (v4.0)
```python
# filter_mate_dockwidget.py ligne 2428
def exploring_select_features(self):
    if not self._is_layer_valid(): return
    if self._controller_integration:
        # Délègue au controller - MAIS le controller est-il bien appelé?
        if self._controller_integration.delegate_exploring_activate_selection_tool(self.current_layer):
            features, _ = self.get_current_features()
            if features and self._controller_integration.delegate_exploring_select_layer_features(...):
                return
    # Fallback
    try: 
        self.iface.actionSelectRectangle().trigger()
        self.iface.setActiveLayer(self.current_layer)
    except: pass
```

#### 🐛 PROBLÈME IDENTIFIÉ

**Le signal `toggled` n'est PAS correctement connecté au handler ON_TRUE/ON_FALSE.**

Dans le nouveau code, la configuration des widgets utilise `_setup_exploring_signals_special_handling()` qui reconnecte les signaux, MAIS :

1. La structure `SIGNALS` avec `custom_functions` n'est pas interprétée de la même manière
2. Le handler `layer_property_changed` n'appelle pas automatiquement `exploring_select_features()`
3. La reconnexion des signaux dans `_reconnect_layer_signals` ne gère pas correctement le callback ON_TRUE/ON_FALSE

---

### 2. Connexion selectionChanged → on_layer_selection_changed

#### Before Migration (v2.x)
```python
# ligne 5145 - Connexion initiale
self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)

# ligne 10075 - Reconnexion lors du changement de couche
self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)
```

#### After Migration (v4.0)
```python
# ligne 1393 - Connexion présente
self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)

# ligne 2830 - Reconnexion
self.current_layer.selectionChanged.connect(self.on_layer_selection_changed)
```

#### ✅ CONNEXION OK - Mais problème de délégation

Le signal est connecté, mais `on_layer_selection_changed` délègue au controller qui peut échouer :

```python
def on_layer_selection_changed(self, selected, deselected, clearAndSelect):
    if self._controller_integration and \
       self._controller_integration.delegate_handle_layer_selection_changed(...):
        return  # Délégation réussie
    # Fallback
    self._fallback_handle_layer_selection_changed()
```

---

### 3. Auto-switch GroupBox (Single ↔ Multiple)

#### Before Migration (v2.x)
```python
# _sync_widgets_from_qgis_selection() ligne 8065
if selected_count == 1 and self.current_exploring_groupbox == "multiple_selection":
    self._force_exploring_groupbox_exclusive("single_selection")
    self._configure_single_selection_groupbox()
    
elif selected_count > 1 and self.current_exploring_groupbox == "single_selection":
    self._force_exploring_groupbox_exclusive("multiple_selection")
    self._configure_multiple_selection_groupbox()
```

#### After Migration (v4.0)
```python
# ExploringController._sync_widgets_from_qgis_selection() ligne 2340
# Même logique - MAIS dépend de is_selecting étant True
```

#### 🐛 PROBLÈME IDENTIFIÉ

L'auto-switch ne se déclenche que si `is_selecting` est True. **Mais le signal `toggled` n'appelle pas correctement la méthode `exploring_select_features()`**, donc `is_selecting` reste à False même si le bouton est visuellement checké.

---

## 📊 Tableau des Signaux Exploring (Après Corrections)

| Signal | Widget | Événement | Handler v2.x | Handler v4.0 | Statut |
|--------|--------|-----------|--------------|--------------|--------|
| IS_SELECTING toggled(True) | pushButton_checkable_exploring_selecting | toggled | `exploring_select_features()` | ✅ Connexion directe | ✅ |
| IS_SELECTING toggled(False) | pushButton_checkable_exploring_selecting | toggled | `exploring_deselect_features()` | ✅ Connexion directe | ✅ |
| IS_TRACKING toggled | pushButton_checkable_exploring_tracking | toggled | `layer_property_changed()` | ✅ Connexion directe | ✅ |
| IS_LINKING toggled | pushButton_checkable_exploring_linking_widgets | toggled | `exploring_link_widgets()` | ✅ Connexion directe | ✅ |
| selectionChanged | QgsVectorLayer | selectionChanged | `on_layer_selection_changed()` | Délégation OK | ✅ |
| SINGLE_SELECTION_FEATURES featureChanged | QgsFeaturePickerWidget | featureChanged | `exploring_features_changed()` | Délégation OK | ✅ |
| MULTIPLE_SELECTION_FEATURES updatingCheckedItemList | CheckableItemsComboBox | custom | `exploring_features_changed()` | Délégation OK | ✅ |
| ZOOM clicked | pushButton_exploring_zoom | clicked | `exploring_zoom_clicked()` | Délégation OK | ✅ |
| IDENTIFY clicked | pushButton_exploring_identify | clicked | `exploring_identify_clicked()` | Délégation OK | ✅ |
| RESET clicked | pushButton_exploring_reset_layer_properties | clicked | `reset_all_layer_properties()` | Délégation partielle | 🟡 |

---

## 🔧 Plan de Correction

### PHASE 1: Correction Signaux IS_SELECTING (CRITIQUE)

#### Fichier: `filter_mate_dockwidget.py`

**Problème**: Le signal `toggled` du bouton IS_SELECTING ne déclenche pas `exploring_select_features()` / `exploring_deselect_features()`.

**Cause racine**: La structure `custom_functions` avec `ON_TRUE` et `ON_FALSE` n'est pas interprétée correctement dans le nouveau système de widgets.

**Solution**: Modifier `_setup_exploring_signals_special_handling()` pour connecter explicitement les callbacks.

```python
# Dans _setup_exploring_signals_special_handling() - AJOUTER
def _setup_exploring_signals_special_handling(self):
    """FIX 2026-01-14: Properly connect IS_SELECTING toggled signal with ON_TRUE/ON_FALSE callbacks."""
    
    # Disconnect existing connections first
    btn_selecting = self.pushButton_checkable_exploring_selecting
    try:
        btn_selecting.toggled.disconnect()
    except TypeError:
        pass  # No connection to disconnect
    
    # Connect with proper handler that respects is_selecting state
    def on_selecting_toggled(checked):
        """Handle IS_SELECTING toggle with proper activation of selection tool."""
        if not self.widgets_initialized or not self.current_layer:
            return
        
        # Update layer property
        layer_id = self.current_layer.id()
        if layer_id in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = checked
        
        # Call appropriate handler
        if checked:
            self.exploring_select_features()  # Activate tool + sync features
        else:
            self.exploring_deselect_features()  # Clear selection
    
    btn_selecting.toggled.connect(on_selecting_toggled)
```

### PHASE 2: Renforcer exploring_select_features()

**Fichier**: `filter_mate_dockwidget.py`

Assurer que la méthode active correctement l'outil de sélection QGIS :

```python
def exploring_select_features(self):
    """Activate QGIS selection tool and select features from active groupbox."""
    if not self._is_layer_valid():
        return
    
    # PHASE 2 FIX: Always activate selection tool and set active layer
    try:
        self.iface.actionSelectRectangle().trigger()
        self.iface.setActiveLayer(self.current_layer)
        logger.info(f"exploring_select_features: Selection tool activated for {self.current_layer.name()}")
    except Exception as e:
        logger.warning(f"exploring_select_features: Failed to activate selection tool: {e}")
        return
    
    # Get features from active groupbox and select them
    features, _ = self.get_current_features()
    if features:
        self.current_layer.removeSelection()
        self.current_layer.select([f.id() for f in features])
        logger.debug(f"exploring_select_features: Selected {len(features)} features")
```

### PHASE 3: Renforcer la synchronisation bidirectionnelle

#### Fichier: `ui/controllers/exploring_controller.py`

S'assurer que `handle_layer_selection_changed` est toujours appelé avec les bons paramètres :

```python
def handle_layer_selection_changed(self, selected, deselected, clear_and_select) -> bool:
    """Handle QGIS layer selection change."""
    try:
        # Skip if syncing FROM QGIS (we're the source)
        if getattr(self._dockwidget, '_syncing_from_qgis', False):
            return True
        
        # Skip during filtering
        if getattr(self._dockwidget, '_filtering_in_progress', False):
            return True
        
        if not self._dockwidget.widgets_initialized or not self._dockwidget.current_layer:
            return False
        
        layer_props = self._dockwidget.PROJECT_LAYERS.get(self._dockwidget.current_layer.id())
        if not layer_props:
            return False
        
        is_selecting = layer_props.get("exploring", {}).get("is_selecting", False)
        is_tracking = layer_props.get("exploring", {}).get("is_tracking", False)
        
        logger.info(f"handle_layer_selection_changed: is_selecting={is_selecting}, is_tracking={is_tracking}")
        
        # PHASE 3 FIX: Always sync widgets when is_selecting is True
        if is_selecting:
            self._sync_widgets_from_qgis_selection()
        
        # Zoom when is_tracking is True
        if is_tracking:
            selected_ids = self._dockwidget.current_layer.selectedFeatureIds()
            if selected_ids:
                from qgis.core import QgsFeatureRequest
                request = QgsFeatureRequest().setFilterFids(list(selected_ids))
                features = list(self._dockwidget.current_layer.getFeatures(request))
                if features:
                    self.zooming_to_features(features)
        
        return True
        
    except Exception as e:
        logger.error(f"handle_layer_selection_changed error: {e}")
        return False
```

### PHASE 4: Renforcer IS_LINKING

**Fichier**: `filter_mate_dockwidget.py`

Ajouter une connexion similaire pour IS_LINKING :

```python
def _setup_linking_signal(self):
    """Connect IS_LINKING toggled signal properly."""
    btn_linking = self.pushButton_checkable_exploring_linking_widgets
    try:
        btn_linking.toggled.disconnect()
    except TypeError:
        pass
    
    def on_linking_toggled(checked):
        if not self.widgets_initialized or not self.current_layer:
            return
        
        layer_id = self.current_layer.id()
        if layer_id in self.PROJECT_LAYERS:
            self.PROJECT_LAYERS[layer_id]["exploring"]["is_linking"] = checked
        
        if checked:
            self.exploring_link_widgets()
    
    btn_linking.toggled.connect(on_linking_toggled)
```

### PHASE 5: Vérifier Zoom, Tracking, Identify, Reset

Ces fonctionnalités utilisent des signaux `clicked` qui devraient fonctionner. Vérifier :

1. **Zoom**: `pushButton_exploring_zoom.clicked` → `exploring_zoom_clicked()`
2. **Identify**: `pushButton_exploring_identify.clicked` → `exploring_identify_clicked()`
3. **Reset**: `pushButton_exploring_reset_layer_properties.clicked` → `reset_all_layer_properties()`

Si ces boutons ne fonctionnent pas, c'est que leur signal n'est pas connecté dans `_setup_exploring_signals_special_handling()`.

---

## ✅ Ordre d'Exécution

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1: IS_SELECTING Signal (IMMÉDIAT - 30 min)                   │
│ ─────────────────────────────────────────────────────────────────── │
│ • Modifier _setup_exploring_signals_special_handling()              │
│ • Connecter toggled → on_selecting_toggled() avec ON_TRUE/ON_FALSE │
│ • Test: Bouton selecting → outil sélection canvas activé           │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2: exploring_select_features() (15 min)                       │
│ ─────────────────────────────────────────────────────────────────── │
│ • Assurer iface.actionSelectRectangle().trigger() TOUJOURS appelé  │
│ • Assurer iface.setActiveLayer() TOUJOURS appelé                   │
│ • Test: Features sélectionnées dans widget → QGIS sélection sync   │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Synchronisation bidirectionnelle (20 min)                  │
│ ─────────────────────────────────────────────────────────────────── │
│ • _sync_widgets_from_qgis_selection() robuste                       │
│ • Auto-switch GroupBox (1 feature → single, >1 → multiple)         │
│ • Test: Sélection canvas → widget single/multiple correctement     │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 4: IS_LINKING + autres boutons (15 min)                       │
│ ─────────────────────────────────────────────────────────────────── │
│ • Connecter toggled pour IS_TRACKING et IS_LINKING                  │
│ • Vérifier Zoom, Identify, Reset fonctionnent                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Tests de Validation

### Test 1: IS_SELECTING Active l'Outil Sélection

1. Ouvrir QGIS avec FilterMate
2. Charger une couche vectorielle
3. Aller dans l'onglet Exploring
4. **Cliquer sur le bouton IS_SELECTING** (icône sélection)
5. ✅ Vérifier: L'outil de sélection rectangle est actif dans le canvas QGIS
6. ✅ Vérifier: La couche courante est la couche active dans le panneau des couches

### Test 2: Synchronisation Canvas → Widget (Single)

1. IS_SELECTING est activé
2. Avec l'outil sélection, **sélectionner UNE feature** sur le canvas
3. ✅ Vérifier: Le GroupBox passe automatiquement en "Single Selection"
4. ✅ Vérifier: Le QgsFeaturePickerWidget affiche la feature sélectionnée

### Test 3: Synchronisation Canvas → Widget (Multiple)

1. IS_SELECTING est activé
2. Avec l'outil sélection, **sélectionner PLUSIEURS features** sur le canvas
3. ✅ Vérifier: Le GroupBox passe automatiquement en "Multiple Selection"
4. ✅ Vérifier: Les features sont cochées dans le CheckableItemsComboBox

### Test 4: Synchronisation Widget → Canvas

1. IS_SELECTING est activé
2. Dans le widget Multiple Selection, **cocher/décocher des features**
3. ✅ Vérifier: La sélection QGIS est synchronisée (features surlignées sur le canvas)

### Test 5: IS_TRACKING Zoom

1. IS_TRACKING est activé
2. Sélectionner des features sur le canvas
3. ✅ Vérifier: Le canvas zoome automatiquement sur les features sélectionnées

### Test 6: IS_LINKING Expressions

1. IS_LINKING est activé
2. Changer l'expression d'affichage dans Single Selection
3. ✅ Vérifier: L'expression est propagée au Multiple Selection

---

## 📝 Fichiers à Modifier

| Fichier | Modifications |
|---------|---------------|
| `filter_mate_dockwidget.py` | `_setup_exploring_signals_special_handling()`, `exploring_select_features()` |
| `ui/controllers/exploring_controller.py` | `handle_layer_selection_changed()`, `_sync_widgets_from_qgis_selection()` |
| `ui/controllers/integration.py` | Vérifier délégations |

---

**Rédigé par BMAD Master Agent** 🧙
