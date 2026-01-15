# Debug: Synchronisation Sélection Canvas ↔ Pickers (2026-01-15)

## 🎯 Objectif

Diagnostiquer pourquoi la synchronisation bidirectionnelle entre la sélection canvas QGIS et les feature pickers ne fonctionne pas quand le bouton `pushButton_checkable_exploring_selecting` est coché.

## 📋 Fonctionnalité Attendue

Quand `pushButton_checkable_exploring_selecting` est **coché** :

1. ✅ L'outil de sélection QGIS doit être activé sur le canvas
2. ✅ Quand l'utilisateur sélectionne **1 entité** sur le canvas → `mFeaturePickerWidget_exploring_single_selection` doit afficher cette entité
3. ✅ Quand l'utilisateur sélectionne **plusieurs entités** sur le canvas → `checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection` doit cocher ces entités

## 🔍 Diagnostic Ajouté (v10)

### Logs de Traçage

Des logs détaillés ont été ajoutés pour tracer le flux complet :

#### 1. Activation du bouton IS_SELECTING

**Fichier** : `filter_mate_dockwidget.py` L3324-3347

```
🔌 _ensure_selection_changed_connected CALLED: current_layer=<nom>, connection_flag=<True/False>
✅ _ensure_selection_changed_connected: Connected selectionChanged signal for layer '<nom>'
```

ou

```
ℹ️ _ensure_selection_changed_connected: Signal already connected for layer '<nom>'
```

#### 2. Sélection sur le Canvas

**Fichier** : `filter_mate_dockwidget.py` L3349-3382

```
🔔 on_layer_selection_changed TRIGGERED: selected=<N>, deselected=<M>, clearAndSelect=<True/False>
🔀 Delegating to ExploringController.handle_layer_selection_changed
```

**Fichier** : `ui/controllers/exploring_controller.py` L2496-2510

```
🎯 ExploringController.handle_layer_selection_changed ENTERED: selected=<N>, deselected=<M>
```

#### 3. Synchronisation des Widgets

**Fichier** : `ui/controllers/exploring_controller.py` L2620-2750

```
📊 Selected features count: <N>
📦 Current groupbox: <single_selection|multiple_selection>
🔀 Auto-switching to <groupbox> (<N> features)
🔧 Syncing single selection widget...
🔧 Syncing multiple selection widget...
✅ _sync_widgets_from_qgis_selection COMPLETED
```

## 🧪 Procédure de Test

### Préparation

1. **Redémarrer QGIS** pour recharger le plugin avec les nouveaux logs
2. **Ouvrir la console Python** dans QGIS (`Ctrl+Alt+P`)
3. **Charger une couche vectorielle** avec quelques entités

### Test 1 : Vérifier la Connexion du Signal

1. Activer le panneau FilterMate
2. Sélectionner une couche dans le combobox
3. **Cocher le bouton IS_SELECTING** (icône de sélection)

**Logs attendus dans la console Python** :

```
🔌 _ensure_selection_changed_connected CALLED: current_layer=ma_couche, connection_flag=False
✅ _ensure_selection_changed_connected: Connected selectionChanged signal for layer 'ma_couche'
```

**Si aucun log n'apparaît** : Le signal `toggled` du bouton n'est pas connecté correctement.

### Test 2 : Vérifier le Déclenchement du Signal selectionChanged

1. Avec le bouton IS_SELECTING **coché**
2. **Sélectionner 1 entité sur le canvas** avec l'outil de sélection (rectangle ou clic)

**Logs attendus** :

```
🔔 on_layer_selection_changed TRIGGERED: selected=1, deselected=0, clearAndSelect=False
🔀 Delegating to ExploringController.handle_layer_selection_changed
🎯 ExploringController.handle_layer_selection_changed ENTERED: selected=1, deselected=0
```

**Si "🔔 on_layer_selection_changed TRIGGERED" n'apparaît PAS** : Le signal `selectionChanged` du layer n'est pas connecté.

**Si "🎯 ExploringController.handle_layer_selection_changed ENTERED" n'apparaît PAS** : Le problème est dans la délégation au controller.

### Test 3 : Vérifier la Synchronisation des Widgets

1. Continuer après Test 2
2. Observer si les logs de synchronisation apparaissent

**Logs attendus** :

```
📊 Selected features count: 1
📦 Current groupbox: single_selection
🔧 Syncing single selection widget...
🔧 Syncing multiple selection widget...
✅ _sync_widgets_from_qgis_selection COMPLETED
```

**Si ces logs n'apparaissent PAS** : Le flag `is_selecting` n'est pas activé dans `PROJECT_LAYERS`.

### Test 4 : Test avec Multiple Sélection

1. **Sélectionner plusieurs entités** sur le canvas (rectangle)

**Logs attendus** :

```
🔔 on_layer_selection_changed TRIGGERED: selected=5, deselected=0, clearAndSelect=False
🎯 ExploringController.handle_layer_selection_changed ENTERED: selected=5, deselected=0
📊 Selected features count: 5
📦 Current groupbox: single_selection
🔀 Auto-switching to multiple_selection (5 features)
✅ Switched to multiple_selection
🔧 Syncing single selection widget...
🔧 Syncing multiple selection widget...
✅ _sync_widgets_from_qgis_selection COMPLETED
```

## 🐛 Problèmes Possibles

### Problème 1 : Aucun log du tout

**Cause** : Le signal `toggled` du bouton n'est pas connecté.

**Solution** :
- Vérifier dans `filter_mate_dockwidget.py` L2257-2273 que `_on_selecting_toggled` est bien connecté
- Vérifier que `_connect_exploring_buttons_directly()` est appelé pendant l'initialisation

### Problème 2 : Log "🔌" mais pas de log "🔔"

**Cause** : Le signal `selectionChanged` du layer ne se déclenche pas.

**Vérifications** :
1. Le layer est-il modifiable ou en lecture seule ?
2. Le flag `current_layer_selection_connection` est-il à `True` ?
3. Y a-t-il une erreur silencieuse lors de la connexion ?

**Solution** :
- Forcer la reconnexion manuellement dans la console Python :

```python
dw = iface.mainWindow().findChild(QDockWidget, 'FilterMateDockWidget')
if dw and dw.current_layer:
    dw.current_layer.selectionChanged.disconnect()
    dw.current_layer.selectionChanged.connect(dw.on_layer_selection_changed)
    print("Signal reconnected manually")
```

### Problème 3 : Log "🔔" et "🎯" mais pas de synchronisation

**Cause** : Le flag `is_selecting` n'est pas activé dans `PROJECT_LAYERS`.

**Vérification** :

```python
dw = iface.mainWindow().findChild(QDockWidget, 'FilterMateDockWidget')
if dw and dw.current_layer:
    layer_id = dw.current_layer.id()
    is_selecting = dw.PROJECT_LAYERS.get(layer_id, {}).get("exploring", {}).get("is_selecting", False)
    button_checked = dw.pushButton_checkable_exploring_selecting.isChecked()
    print(f"is_selecting in PROJECT_LAYERS: {is_selecting}")
    print(f"Button checked: {button_checked}")
```

**Solution** : Synchroniser manuellement :

```python
if button_checked and not is_selecting:
    dw.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = True
    print("Fixed is_selecting flag")
```

### Problème 4 : Logs complets mais widgets ne se mettent pas à jour

**Cause** : Problème dans `_sync_single_selection_from_qgis()` ou `_sync_multiple_selection_from_qgis()`.

**Vérification** : Chercher des erreurs/warnings dans les logs après "🔧 Syncing...".

## 📝 Rapport à Fournir

Si le problème persiste après ces tests, merci de fournir :

1. **Copie complète des logs** depuis le moment où vous cochez IS_SELECTING jusqu'après la sélection
2. **Version de QGIS** utilisée
3. **Type de couche** (PostgreSQL, Shapefile, GeoPackage, etc.)
4. **Nombre d'entités** dans la couche
5. **État du bouton** avant/après (`pushButton_checkable_exploring_selecting.isChecked()`)

## 🔧 Fichiers Modifiés

### v10 - Logs de Diagnostic (2026-01-15)

1. **`filter_mate_dockwidget.py`**
   - L3324-3347 : `_ensure_selection_changed_connected()` - Logs détaillés connexion signal
   - L3349-3382 : `on_layer_selection_changed()` - Logs déclenchement + délégation

2. **`ui/controllers/exploring_controller.py`**
   - L2496-2510 : `handle_layer_selection_changed()` - Log point d'entrée

## ✅ Prochaines Étapes

Une fois les logs récupérés, nous pourrons :
1. Identifier précisément où le flux se bloque
2. Corriger le problème ciblé
3. Supprimer les logs de debug (ou les passer en `logger.debug()`)
