# Bug Analysis: comboBox_filtering_current_layer Signal Issues

**Date**: 2026-01-15  
**Status**: 🔴 CRITICAL - Signaux incohérents sur certains systèmes  
**Reporter**: Simon Ducourneau  
**Severity**: HIGH - Impacte l'expérience utilisateur

---

## 🐛 Symptômes

Quand l'utilisateur change le `current_layer` dans `comboBox_filtering_current_layer`:

1. ✅ **Devrait** mettre à jour les widgets d'**exploring** (`setLayer`)
2. ✅ **Devrait** mettre à jour la liste **layers_to_filter** (exclure le current layer)
3. ❌ **Sur certains systèmes** : les signaux ne se déclenchent pas ou partiellement

---

## 🔍 Analyse Approfondie

### Architecture des Signaux

```
comboBox_filtering_current_layer (QgsMapLayerComboBox)
    ↓ layerChanged signal
    → current_layer_changed(layer, manual_change=True)
        ↓
        → LayerSyncController.on_current_layer_changed()
            ↓
            → LayerSyncController.synchronize_layer_widgets()
                ↓
                ├─→ _sync_current_layer_combobox()
                ├─→ _sync_layers_to_filter_combobox()  ← Exclude current layer
                ├─→ ExploringController._reload_exploration_widgets()  ← setLayer
                └─→ _sync_layer_property_widgets()
```

### Configuration Actuelle

**Fichier**: `ui/managers/configuration_manager.py` ligne 418-421

```python
"CURRENT_LAYER": {
    "TYPE": "ComboBox",
    "WIDGET": d.comboBox_filtering_current_layer,
    # FIX 2026-01-14: Pass manual_change=True for manual combobox changes
    "SIGNALS": [("layerChanged", lambda layer: d.current_layer_changed(layer, manual_change=True))]
}
```

✅ **Signal correctement configuré** avec `manual_change=True`

### Connexion du Signal

**Fichier**: `filter_mate_dockwidget.py` ligne 1424-1432

```python
cache_key = "FILTERING.CURRENT_LAYER.layerChanged"
if cache_key in self._signal_connection_states:
    logger.debug(f"Signal {cache_key} already connected: {self._signal_connection_states[cache_key]}")
else:
    # Connect comboBox_filtering_current_layer.layerChanged signal
    self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
    logger.info("✓ Connected FILTERING.CURRENT_LAYER.layerChanged signal via manageSignal")
```

✅ **Signal connecté au startup**

---

## 🔎 Problèmes Identifiés

### 1. 🔴 CRITIQUE: Reconnexion Manquante Après Déconnexion

**Fichier**: `filter_mate_dockwidget.py` ligne 2750

```python
def _disconnect_layer_signals(self):
    """v3.1 Sprint 17: Disconnect all layer-related widget signals before updating."""
    exploring = ["SINGLE_SELECTION_FEATURES", "SINGLE_SELECTION_EXPRESSION", ...]
    filtering = ["CURRENT_LAYER", "HAS_LAYERS_TO_FILTER", "LAYERS_TO_FILTER", ...]  # ← CURRENT_LAYER inclus!
    widgets_to_stop = [["EXPLORING", w] for w in exploring] + [["FILTERING", w] for w in filtering]
    
    for wp in widgets_to_stop: 
        self.manageSignal(wp, 'disconnect')  # ← CURRENT_LAYER est déconnecté!
```

**Problème**: Le signal `CURRENT_LAYER.layerChanged` est **déconnecté** pendant `_disconnect_layer_signals()`

**Reconnexion**: Cherchons où il devrait être reconnecté...

**Fichier**: `ui/controllers/layer_sync_controller.py` ligne 661-696

```python
def reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
    """Reconnect all layer-related widget signals after updates."""
    
    exploring_signal_prefixes = [
        ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
        ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
        # ...
    ]
    
    # Reconnect only non-exploring signals
    for widget_path in widgets_to_reconnect:
        if widget_path not in exploring_signal_prefixes:  # ← CURRENT_LAYER devrait passer ici
            if hasattr(dw, 'manageSignal'):
                dw.manageSignal(widget_path, 'connect')  # ← Reconnexion!
```

✅ **Reconnexion prévue** mais dépend de `widgets_to_reconnect`

**Fichier**: `filter_mate_dockwidget.py` ligne 3146-3150

```python
def current_layer_changed(self, layer, manual_change=False):
    # ...
    widgets = self._disconnect_layer_signals()  # ← Retourne la liste
    # ...
    self._reconnect_layer_signals(widgets, layer_props)  # ← Devrait reconnecter
```

✅ **Reconnexion appelée**

### 2. 🔴 CRITIQUE: `_synchronize_layer_widgets` - Reconnexion Conditionnelle

**Fichier**: `filter_mate_dockwidget.py` ligne 2789-2802

```python
def _synchronize_layer_widgets(self, layer, layer_props, manual_change=False):
    # Try delegation first
    if self._layer_sync_ctrl:
        if self._controller_integration.delegate_synchronize_layer_widgets(layer, layer_props, manual_change=manual_change):
            return  # ← Sort immédiatement si délégué!
    
    # Fallback: Minimal inline logic when controller unavailable
    if not self._is_ui_ready() or not layer:
        return
    
    last_layer = self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].currentLayer()
    if last_layer is None or last_layer.id() != layer.id():
        self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
        self.widgets["FILTERING"]["CURRENT_LAYER"]["WIDGET"].setLayer(layer)
        self.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')  # ← Reconnexion!
```

**Problème**: 
- ✅ Fallback reconnecte CURRENT_LAYER
- ❌ **Délégation au controller** ne reconnecte **PAS** CURRENT_LAYER!

**Fichier**: `ui/controllers/layer_sync_controller.py` ligne 598-657

```python
def synchronize_layer_widgets(self, layer, layer_props, manual_change=False, skip_combobox_sync=False):
    """Synchronize all layer-related widgets."""
    
    # Detect multi-step filter
    # Sync current layer combobox (unless protected)
    if not skip_combobox_sync:
        self._sync_current_layer_combobox(layer)  # ← Met à jour mais ne reconnecte PAS!
    
    # Synchronize all layer property widgets
    self._sync_layer_property_widgets(layer, layer_props)
    
    # CRITICAL: Populate layers_to_filter combobox (excluding current layer)
    self._sync_layers_to_filter_combobox(layer)  # ← Reconnecte layers_to_filter
    
    # NO RECONNECTION OF CURRENT_LAYER signal!
```

### 3. 🟡 MOYEN: `_sync_current_layer_combobox` - Pas de Reconnexion

**Fichier**: `ui/controllers/layer_sync_controller.py` ligne 794-823

```python
def _sync_current_layer_combobox(self, layer: QgsVectorLayer) -> None:
    """Update current layer combobox widget without triggering signals."""
    dw = self.dockwidget
    
    # Get current layer widget
    current_layer_widget = dw.widgets.get("FILTERING", {}).get("CURRENT_LAYER", {}).get("WIDGET")
    if not current_layer_widget:
        return
    
    # Get currently displayed layer
    displayed_layer = current_layer_widget.currentLayer()
    
    # Only update if different
    if displayed_layer and displayed_layer.id() == layer.id():
        logger.debug("_sync_current_layer_combobox: Layer already displayed, skipping")
        return
    
    logger.debug(f"_sync_current_layer_combobox: Updating combo | {displayed_layer.name() if displayed_layer else 'None'} → {layer.name()}")
    
    # Disconnect, update, reconnect
    if hasattr(dw, 'manageSignal'):
        dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
        
    current_layer_widget.setLayer(current_layer)
    
    if hasattr(dw, 'manageSignal'):
        dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')  # ← RECONNEXION ICI!
```

✅ **Cette méthode reconnecte correctement!**

**MAIS**: Elle peut **sortir prématurément** (ligne 813) si le layer est déjà affiché!

---

## 🚨 Root Cause Analysis

### Scénario Problématique

1. **User change layer** dans `comboBox_filtering_current_layer`
2. Signal `layerChanged` → `current_layer_changed(layer, manual_change=True)`
3. `_disconnect_layer_signals()` **déconnecte CURRENT_LAYER**
4. **Délégation** à `LayerSyncController.synchronize_layer_widgets()`
5. `_sync_current_layer_combobox()` appelée
6. **PROBLÈME**: Si `displayed_layer.id() == layer.id()` (ligne 813):
   - Sort prématurément → **PAS de reconnexion!**
7. `reconnect_layer_signals()` appelée mais **CURRENT_LAYER** n'est **PAS dans la liste**!

### Pourquoi Sur Certains Systèmes?

**Hypothèse**: Race condition ou différences de timing Qt entre systèmes

- Sur systèmes **rapides**: `setLayer()` se met à jour immédiatement → `displayed_layer.id() == layer.id()` → Skip reconnexion
- Sur systèmes **lents**: `setLayer()` prend du temps → `displayed_layer != layer` → Reconnexion OK

---

## ✅ Solutions

### Solution 1: **Forcer la Reconnexion dans `synchronize_layer_widgets`**

**Fichier**: `ui/controllers/layer_sync_controller.py`

Après `_sync_layers_to_filter_combobox(layer)`, ajouter:

```python
# CRITICAL: Always reconnect CURRENT_LAYER signal after sync
if hasattr(dw, 'manageSignal'):
    dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
    logger.debug("✓ CURRENT_LAYER signal reconnected after widget sync")
```

### Solution 2: **Retirer CURRENT_LAYER de `_disconnect_layer_signals`**

**Fichier**: `filter_mate_dockwidget.py`

```python
def _disconnect_layer_signals(self):
    exploring = [...]
    # CRITICAL: Ne PAS déconnecter CURRENT_LAYER (utilisateur peut changer pendant sync)
    filtering = ["HAS_LAYERS_TO_FILTER", "LAYERS_TO_FILTER", ...]  # ← Retirer CURRENT_LAYER
```

**Avantages**:
- ✅ Évite la déconnexion/reconnexion inutile
- ✅ Signal toujours actif pour les changements utilisateur

**Inconvénients**:
- ❌ Peut causer réentrance si signal se déclenche pendant update

### Solution 3 (RECOMMANDÉE): **Combinaison + Lock de Réentrance**

1. **Retirer CURRENT_LAYER** de `_disconnect_layer_signals()`
2. **Utiliser le lock existant** `_updating_current_layer` pour bloquer réentrance
3. **Garantir reconnexion** dans `_sync_current_layer_combobox()` (déjà fait!)

---

## 🔧 Implémentation Recommandée

### Changement 1: Ne Plus Déconnecter CURRENT_LAYER

**Fichier**: `filter_mate_dockwidget.py` ligne 2750

```python
def _disconnect_layer_signals(self):
    """v3.1 Sprint 17: Disconnect all layer-related widget signals before updating."""
    exploring = ["SINGLE_SELECTION_FEATURES", "SINGLE_SELECTION_EXPRESSION", ...]
    
    # FIX 2026-01-15: Ne PAS déconnecter CURRENT_LAYER
    # Le signal layerChanged doit rester actif car l'utilisateur peut changer
    # de layer pendant une mise à jour. Le lock _updating_current_layer
    # prévient la réentrance.
    filtering = [
        "HAS_LAYERS_TO_FILTER", "LAYERS_TO_FILTER",
        "HAS_COMBINE_OPERATOR", "SOURCE_LAYER_COMBINE_OPERATOR",
        "OTHER_LAYERS_COMBINE_OPERATOR", "HAS_GEOMETRIC_PREDICATES",
        "GEOMETRIC_PREDICATES", "HAS_BUFFER_VALUE", "BUFFER_VALUE",
        "BUFFER_VALUE_PROPERTY", "HAS_BUFFER_TYPE", "BUFFER_TYPE"
    ]  # ← CURRENT_LAYER retiré
    
    widgets_to_stop = [["EXPLORING", w] for w in exploring] + [["FILTERING", w] for w in filtering]
    
    for wp in widgets_to_stop: 
        self.manageSignal(wp, 'disconnect')
    
    # Optionnel: Log pour debugging
    logger.debug(f"Disconnected {len(widgets_to_stop)} widget signals (CURRENT_LAYER kept active)")
    
    return widgets_to_stop
```

### Changement 2: Garantir Reconnexion dans Controller

**Fichier**: `ui/controllers/layer_sync_controller.py` ligne 640

```python
def synchronize_layer_widgets(self, layer, layer_props, manual_change=False, skip_combobox_sync=False):
    """Synchronize all layer-related widgets."""
    dw = self.dockwidget
    
    # ... (code existant)
    
    # CRITICAL: Populate layers_to_filter combobox (excluding current layer)
    self._sync_layers_to_filter_combobox(layer)
    
    # FIX 2026-01-15: Garantir que CURRENT_LAYER signal est reconnecté
    # Même si _sync_current_layer_combobox() sort prématurément
    if not skip_combobox_sync and hasattr(dw, 'manageSignal'):
        try:
            # Vérifier si signal est déjà connecté
            current_widget = dw.widgets.get("FILTERING", {}).get("CURRENT_LAYER", {}).get("WIDGET")
            if current_widget:
                signal = getattr(current_widget, 'layerChanged', None)
                if signal:
                    # Reconnexion sécurisée (idempotente)
                    dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
                    logger.debug("✓ CURRENT_LAYER.layerChanged signal reconnected (safety check)")
        except Exception as e:
            logger.warning(f"Could not reconnect CURRENT_LAYER signal: {e}")
    
    # Synchronize state-dependent widgets
    self._sync_state_dependent_widgets()
```

### Changement 3: Retirer Early Return dans `_sync_current_layer_combobox`

**Fichier**: `ui/controllers/layer_sync_controller.py` ligne 807-813

```python
def _sync_current_layer_combobox(self, layer: QgsVectorLayer) -> None:
    """Update current layer combobox widget without triggering signals."""
    dw = self.dockwidget
    
    # Get current layer widget
    current_layer_widget = dw.widgets.get("FILTERING", {}).get("CURRENT_LAYER", {}).get("WIDGET")
    if not current_layer_widget:
        return
    
    # Get currently displayed layer
    displayed_layer = current_layer_widget.currentLayer()
    
    # FIX 2026-01-15: Toujours reconnecter le signal même si layer identique
    # Raison: Le signal peut avoir été déconnecté ailleurs
    # SUPPRIMÉ:
    # if displayed_layer and displayed_layer.id() == layer.id():
    #     logger.debug("_sync_current_layer_combobox: Layer already displayed, skipping")
    #     return
    
    logger.debug(f"_sync_current_layer_combobox: Updating combo | {displayed_layer.name() if displayed_layer else 'None'} → {layer.name()}")
    
    # Disconnect, update, reconnect (TOUJOURS)
    if hasattr(dw, 'manageSignal'):
        dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'disconnect')
        
    # Mettre à jour même si identique (force refresh)
    current_layer_widget.blockSignals(True)
    current_layer_widget.setLayer(layer)
    current_layer_widget.blockSignals(False)
    
    # TOUJOURS reconnecter
    if hasattr(dw, 'manageSignal'):
        dw.manageSignal(["FILTERING", "CURRENT_LAYER"], 'connect', 'layerChanged')
        logger.debug("✓ CURRENT_LAYER.layerChanged signal reconnected")
```

---

## 🧪 Tests de Validation

### Test 1: Changement Manuel de Layer

1. Ouvrir FilterMate avec 3+ layers
2. Changer `comboBox_filtering_current_layer` manuellement
3. **Vérifier**:
   - ✅ Widgets exploring mis à jour (`setLayer` appelé)
   - ✅ `layers_to_filter` exclut le nouveau current layer
   - ✅ Logs montrent reconnexion du signal

### Test 2: Changements Rapides Successifs

1. Changer de layer 5 fois rapidement
2. **Vérifier**:
   - ✅ Tous les changements sont traités
   - ✅ Pas de déconnexion permanente du signal
   - ✅ `_updating_current_layer` lock fonctionne

### Test 3: Pendant Filtering

1. Lancer un filtre (tâche longue)
2. Changer de layer pendant le filtre
3. **Vérifier**:
   - ✅ Changement bloqué si automatique
   - ✅ Changement autorisé si manuel (`manual_change=True`)
   - ✅ Signal reconnecté après fin du filtre

---

## 📊 Impact Analysis

### Changements Requis

| Fichier | Ligne | Type | Difficulté |
|---------|-------|------|------------|
| `filter_mate_dockwidget.py` | 2750 | Remove CURRENT_LAYER from disconnect | ⭐ Facile |
| `ui/controllers/layer_sync_controller.py` | 640 | Add safety reconnection | ⭐⭐ Moyen |
| `ui/controllers/layer_sync_controller.py` | 807-813 | Remove early return | ⭐ Facile |

### Risques

- 🟢 **LOW**: Lock `_updating_current_layer` déjà en place
- 🟢 **LOW**: manageSignal() est idempotent (ne double pas les connexions)
- 🟡 **MEDIUM**: Peut changer le comportement de reconnexion existant

### Bénéfices

- ✅ **Signal toujours actif** → Changements utilisateur toujours détectés
- ✅ **Pas de race condition** → Fonctionne sur tous les systèmes
- ✅ **Simplifie le code** → Moins de déconnexions/reconnexions

---

## 🎯 Prochaines Étapes

1. [ ] Implémenter Changement 1 (retirer CURRENT_LAYER de disconnect)
2. [ ] Implémenter Changement 2 (safety reconnection dans controller)
3. [ ] Implémenter Changement 3 (retirer early return)
4. [ ] Tester sur système où signaux échouent
5. [ ] Tester scénarios edge cases (changements rapides, pendant filtre, etc.)
6. [ ] Commit avec message: `fix: ensure comboBox_filtering_current_layer signal stays connected (BUGFIX-COMBOBOX-20260115)`

---

## 📝 Notes Additionnelles

### Pourquoi `manual_change=True` est Important

Le flag `manual_change=True` permet de:
- ✅ **Bypasser la protection post-filter** (5s window)
- ✅ **Forcer la mise à jour** même pendant filtering
- ✅ **Distinguer changements utilisateur vs. automatiques**

### Architecture de Protection

```
Protection Layers:
1. _updating_current_layer lock → Prévient réentrance
2. _filtering_in_progress flag → Bloque auto-changes pendant filtre
3. POST_FILTER_PROTECTION_WINDOW → Bloque auto-changes après filtre (5s)

manual_change=True → BYPASS layers 2 & 3 (pas layer 1)
```

### Logs de Debugging

Pour tracer le problème, activer ces logs:

```python
logger.debug(f"manageSignal: {widget_path} | action={custom_action} | signal={custom_signal_name}")
logger.debug(f"Signal '{signal_name}' | state_key={state_key} | cached={cached}")
logger.debug(f"_sync_current_layer_combobox: Layer={layer.name()}, displayed={displayed_layer.name()}")
```

---

**Auteur**: GitHub Copilot (Agent Analyst)  
**Révision**: Requise par équipe technique  
**Priorité**: 🔴 HIGH - Impacte l'UX sur certains systèmes
