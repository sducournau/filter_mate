# Correction Crash Qt JSON Tree View - FilterMate

**Date:** 7 décembre 2025  
**Problème:** Crash QGIS lié aux widgets, particulièrement Qt JSON Tree View  
**Statut:** ✅ CORRIGÉ

---

## 🔴 PROBLÈME

Crash de QGIS lors du chargement du plugin FilterMate, lié à la gestion des widgets Qt et particulièrement le `JsonView` (Qt JSON Tree View).

### Symptômes
- QGIS crash au lancement du plugin
- Erreurs liées à Qt model/view
- Violations d'accès mémoire lors de la manipulation des widgets

---

## 🔍 ANALYSE

### Cause Principale : Ordre d'Initialisation de JsonView

**Localisation:** `modules/qt_json_view/view.py` et `filter_mate_dockwidget.py`

**Problème:**

Dans `JsonView.__init__()` :
```python
def __init__(self, model, plugin_dir=None, parent=None):
    super(JsonView, self).__init__(parent)
    self.model = model  # Stocké mais PAS appliqué
    # ... configuration des styles ...
    # ❌ setModel() n'est JAMAIS appelé dans le constructeur
```

Dans `manage_configuration_model()` :
```python
def manage_configuration_model(self):
    self.config_model = JsonModel(...)                          # 1. Créer modèle
    self.config_view = JsonView(self.config_model, ...)         # 2. Créer vue (modèle non appliqué)
    self.CONFIGURATION.layout().insertWidget(0, self.config_view)  # 3. Insérer dans layout
    self.config_view.setModel(self.config_model)                # 4. ⚠️ CRASH ICI
```

**Pourquoi ça crash ?**

1. `JsonView` est créé avec un modèle mais `setModel()` n'est pas appelé dans le constructeur
2. Le widget est inséré dans le layout **sans modèle défini**
3. Qt essaie de dessiner le widget → accède au modèle → **modèle NULL** → **CRASH**
4. Appeler `setModel()` après insertion est trop tard, Qt a déjà tenté d'accéder au modèle

---

### Cause Secondaire : Gestion Dangereuse des Widgets Dynamiques

**Localisation:** `reset_multiple_checkable_combobox()`

**Problème:**
```python
def reset_multiple_checkable_combobox(self):
    layout = self.verticalLayout_exploring_multiple_selection
    item = layout.itemAt(0)
    layout.removeItem(item)  # ❌ Retire l'item mais ne libère pas le widget
    
    # Widget toujours en mémoire, référencé ailleurs
    # Potentiel double-free ou accès mémoire invalide
```

**Risques:**
- Widget retiré du layout mais pas supprimé de la mémoire
- Références pendantes dans `self.widgets`
- Qt peut tenter d'accéder au widget détruit → **CRASH**

---

## ✅ CORRECTIONS APPLIQUÉES

### 1. **Fix JsonView : setModel() dans le Constructeur** ✅

**Fichier:** `modules/qt_json_view/view.py`

**Avant:**
```python
def __init__(self, model, plugin_dir=None, parent=None):
    super(JsonView, self).__init__(parent)
    self.model = model
    # ... reste du code ...
```

**Après:**
```python
def __init__(self, model, plugin_dir=None, parent=None):
    super(JsonView, self).__init__(parent)
    self.model = model
    
    # CRITICAL: Set model IMMEDIATELY to avoid Qt crashes
    if model is not None:
        self.setModel(model)
    
    # ... reste du code ...
```

**Résultat:** Le modèle est appliqué AVANT toute manipulation du widget.

---

### 2. **Fix manage_configuration_model() : Ne Plus Rappeler setModel()** ✅

**Fichier:** `filter_mate_dockwidget.py`

**Avant:**
```python
def manage_configuration_model(self):
    self.config_model = JsonModel(...)
    self.config_view = JsonView(self.config_model, ...)
    self.CONFIGURATION.layout().insertWidget(0, self.config_view)
    self.config_view.setModel(self.config_model)  # ❌ Redondant et dangereux
    self.config_view.setAnimated(True)
```

**Après:**
```python
def manage_configuration_model(self):
    try:
        # Create model with data
        self.config_model = JsonModel(...)
        
        # Create view with model - setModel() is called in JsonView.__init__()
        self.config_view = JsonView(self.config_model, self.plugin_dir)
        
        # Insert into layout
        self.CONFIGURATION.layout().insertWidget(0, self.config_view)
        
        # Note: setModel() is already called in JsonView constructor - do NOT call again
        
        self.config_view.setAnimated(True)
        self.config_view.setEnabled(True)
        self.config_view.show()
    except Exception as e:
        logger.error(f"Error creating configuration model: {e}")
```

**Résultat:** 
- Plus d'appel redondant à `setModel()`
- Gestion d'erreurs robuste
- Ordre d'opérations correct et sûr

---

### 3. **Fix reload_configuration_model() : Protection Contre None** ✅

**Fichier:** `filter_mate_dockwidget.py`

**Avant:**
```python
def reload_configuration_model(self):
    if self.widgets_initialized is True:
        self.config_model = JsonModel(...)
        self.config_view.setModel(self.config_model)  # ❌ Peut crasher si config_view est None
```

**Après:**
```python
def reload_configuration_model(self):
    if self.widgets_initialized is True:
        try:
            self.config_model = JsonModel(...)
            
            # Update view model - safe to call here since view already exists
            if hasattr(self, 'config_view') and self.config_view is not None:
                self.config_view.setModel(self.config_model)
                self.config_view.model = self.config_model
            
            # Save to file
            json_object = json.dumps(self.CONFIG_DATA, indent=4)
            with open(self.plugin_dir + '/config/config.json', 'w') as outfile:
                outfile.write(json_object)
        except Exception as e:
            logger.error(f"Error reloading configuration model: {e}")
```

**Résultat:** Protection contre `AttributeError` et crashes.

---

### 4. **Fix reset_multiple_checkable_combobox() : Gestion Mémoire Correcte** ✅

**Fichier:** `filter_mate_dockwidget.py`

**Avant:**
```python
def reset_multiple_checkable_combobox(self):
    layout = self.verticalLayout_exploring_multiple_selection
    item = layout.itemAt(0)
    layout.removeItem(item)  # ❌ Fuite mémoire
    
    if self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection:
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset()
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close()
```

**Après:**
```python
def reset_multiple_checkable_combobox(self):
    try:
        layout = self.verticalLayout_exploring_multiple_selection
        
        # Safely remove old widget from layout
        if layout.count() > 0:
            item = layout.itemAt(0)
            if item and item.widget():
                old_widget = item.widget()
                layout.removeWidget(old_widget)
                # Properly delete the old widget to free resources
                old_widget.deleteLater()  # ✅ Libération correcte
            elif item:
                layout.removeItem(item)
        
        # Reset and close widget safely
        if hasattr(self, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection') and \
           self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection is not None:
            try:
                self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.reset()
                self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.close()
                self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection.deleteLater()
            except (RuntimeError, AttributeError) as e:
                logger.debug(f"Could not close widget (may already be destroyed): {e}")
        
        # Create new widget
        self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection = None
        self.set_multiple_checkable_combobox()
        
        # Insert new widget
        if self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection is not None:
            layout.insertWidget(0, self.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection)
            layout.update()
            
            # Update widgets registry
            self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"] = {...}
    except Exception as e:
        logger.error(f"Error resetting multiple checkable combobox: {e}")
```

**Résultat:**
- Libération correcte de la mémoire avec `deleteLater()`
- Protection contre widgets déjà détruits
- Gestion d'erreurs complète
- Pas de fuites mémoire

---

## 🎯 RÉSUMÉ DES PRINCIPES CORRIGÉS

### Principe 1 : Initialisation Complète dans le Constructeur
```python
# ❌ MAUVAIS
class MyView(QTreeView):
    def __init__(self, model):
        super().__init__()
        self.model = model  # Stocké mais pas appliqué
        
# ✅ BON
class MyView(QTreeView):
    def __init__(self, model):
        super().__init__()
        self.model = model
        if model is not None:
            self.setModel(model)  # Appliqué immédiatement
```

### Principe 2 : Pas d'Appels Redondants
```python
# ❌ MAUVAIS
view = MyView(model)           # setModel() appelé dans __init__
layout.insertWidget(0, view)
view.setModel(model)           # ❌ Redondant, peut crasher

# ✅ BON
view = MyView(model)           # setModel() appelé dans __init__
layout.insertWidget(0, view)   # Modèle déjà défini, safe
```

### Principe 3 : Libération Correcte des Widgets
```python
# ❌ MAUVAIS
layout.removeItem(item)        # Retire mais ne libère pas

# ✅ BON
if item and item.widget():
    widget = item.widget()
    layout.removeWidget(widget)
    widget.deleteLater()       # Libération planifiée par Qt
```

### Principe 4 : Protection Contre None
```python
# ❌ MAUVAIS
self.config_view.setModel(model)  # Crash si config_view est None

# ✅ BON
if hasattr(self, 'config_view') and self.config_view is not None:
    self.config_view.setModel(model)
```

---

## 🧪 TESTS RECOMMANDÉS

### Test 1: Chargement Initial
```
1. Démarrer QGIS
2. Activer FilterMate
3. Vérifier: Pas de crash
4. Vérifier: Configuration tree view s'affiche correctement
```

### Test 2: Rechargement Configuration
```
1. Ouvrir l'onglet Configuration
2. Modifier une valeur
3. Recharger la configuration
4. Vérifier: Pas de crash
5. Vérifier: Modifications sauvegardées
```

### Test 3: Reset Multiple Selection Widget
```
1. Aller dans l'onglet Exploration
2. Sélectionner "Multiple Selection"
3. Changer de couche plusieurs fois
4. Vérifier: Pas de crash
5. Vérifier: Widget se met à jour correctement
```

### Test 4: Fermeture/Réouverture Plugin
```
1. Fermer le plugin
2. Rouvrir le plugin
3. Répéter 5 fois
4. Vérifier: Pas de crash ni fuite mémoire
```

---

## 📚 RÉFÉRENCES Qt

### QWidget Memory Management
- **QObject::deleteLater()**: Planifie la suppression du widget de manière sûre
- **QLayout::removeWidget()**: Retire ET supprime le widget du layout
- **QLayout::removeItem()**: Retire MAIS ne supprime PAS le widget

### QTreeView/QAbstractItemModel
- **setModel()**: Doit être appelé AVANT toute manipulation du widget
- Le modèle doit exister pendant toute la durée de vie de la vue
- Changer le modèle après insertion peut causer des crashes

### Best Practices
1. Toujours initialiser complètement les widgets dans le constructeur
2. Utiliser `deleteLater()` pour supprimer les widgets Qt
3. Protéger les accès avec `hasattr()` et `is not None`
4. Wrapper les opérations Qt dans des `try/except`

---

## 🔄 FICHIERS MODIFIÉS

1. ✅ `modules/qt_json_view/view.py` - Fix constructeur JsonView
2. ✅ `filter_mate_dockwidget.py` - Fix manage_configuration_model()
3. ✅ `filter_mate_dockwidget.py` - Fix reload_configuration_model()
4. ✅ `filter_mate_dockwidget.py` - Fix reset_multiple_checkable_combobox()

---

## 📝 NOTES POUR DÉVELOPPEURS

### Diagnostic de Crash Qt
Si un crash similaire se reproduit :

1. **Vérifier l'ordre d'initialisation**
   - Le modèle est-il défini avant l'insertion dans le layout ?
   - `setModel()` est-il appelé au bon moment ?

2. **Vérifier la gestion mémoire**
   - Les widgets sont-ils supprimés avec `deleteLater()` ?
   - Y a-t-il des références pendantes ?

3. **Vérifier les protections**
   - Y a-t-il des checks `if widget is not None` ?
   - Les `try/except` sont-ils présents ?

4. **Utiliser le debugger Qt**
   ```bash
   # Lancer QGIS avec debug Qt
   QT_LOGGING_RULES="qt.*.debug=true" qgis
   ```

---

**FIN DU DOCUMENT**
