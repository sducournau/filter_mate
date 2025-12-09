# Guide d'intégration des widgets d'historique FilterMate

**Date**: 8 décembre 2025  
**Version**: 1.0  
**Statut**: Guide d'implémentation

## Vue d'ensemble

Ce document guide l'intégration des widgets d'historique dans l'interface FilterMate. Les widgets ont été créés dans `modules/ui_history_widgets.py` et testés dans `tests/test_ui_history_widgets.py`.

## Widgets disponibles

### 1. `CompactHistoryWidget` (Recommandé pour l'UI principale)

**Description**: Widget compact combinant dropdown et boutons undo/redo en une seule ligne.

**Composants**:
- Label "History:"
- Bouton Undo (◀)
- Dropdown avec liste des états
- Bouton Redo (▶)

**Signaux émis**:
```python
undoRequested()  # Émis lors du clic sur undo
redoRequested()  # Émis lors du clic sur redo
stateSelected(int)  # Émis lors de la sélection d'un état (index)
```

**Utilisation**:
```python
# Dans filter_mate_dockwidget.py
from modules.ui_history_widgets import CompactHistoryWidget

# Dans __init__()
self.history_widget = CompactHistoryWidget(self)

# Connecter le HistoryManager
self.history_widget.set_history_manager(self.history_manager)

# Définir la couche active
self.history_widget.set_current_layer(layer.id())

# Connecter les signaux
self.history_widget.undoRequested.connect(self._on_undo_requested)
self.history_widget.redoRequested.connect(self._on_redo_requested)
self.history_widget.stateSelected.connect(self._on_history_state_selected)

# Mettre à jour après chaque opération de filtre
self.history_widget.update_history()
```

### 2. `HistoryDropdown`

**Description**: Dropdown autonome montrant les états récents.

**Configuration**:
```python
from modules.ui_history_widgets import HistoryDropdown

dropdown = HistoryDropdown(parent=self, max_items=10)
dropdown.set_history_manager(history_manager)
dropdown.set_current_layer(layer_id)

# Signal
dropdown.stateSelected.connect(self._jump_to_state)
```

### 3. `HistoryNavigationWidget`

**Description**: Boutons undo/redo avec indicateur de position.

**Composants**:
- Bouton Undo
- Label de position (ex: "3/5")
- Bouton Redo

**Utilisation**:
```python
from modules.ui_history_widgets import HistoryNavigationWidget

nav_widget = HistoryNavigationWidget(self)
nav_widget.set_history_manager(history_manager)
nav_widget.set_current_layer(layer_id)

nav_widget.undoRequested.connect(self._on_undo)
nav_widget.redoRequested.connect(self._on_redo)
```

### 4. `HistoryListWidget`

**Description**: Liste complète avec détails (timestamps, feature counts, metadata).

**Usage recommandé**: Panel dédié ou dialog d'historique.

```python
from modules.ui_history_widgets import HistoryListWidget

list_widget = HistoryListWidget(self)
list_widget.set_history_manager(history_manager)
list_widget.set_current_layer(layer_id)

list_widget.stateSelected.connect(self._jump_to_state)
```

## Intégration dans FilterMate

### Étape 1: Ajouter le widget au layout principal

**Fichier**: `filter_mate_dockwidget.py`

```python
# Dans la méthode _setup_widgets() ou équivalent

from modules.ui_history_widgets import CompactHistoryWidget

# Créer le widget
self.history_widget = CompactHistoryWidget(self)

# L'ajouter au layout (par exemple, après les contrôles de filtre)
# Supposons que vous avez un layout vertical principal
self.main_layout.addWidget(self.history_widget)

# Ou dans un layout horizontal avec d'autres contrôles
history_row_layout = QHBoxLayout()
history_row_layout.addWidget(QLabel("Filter History:"))
history_row_layout.addWidget(self.history_widget, stretch=1)
self.main_layout.addLayout(history_row_layout)
```

### Étape 2: Initialiser avec le HistoryManager

**Fichier**: `filter_mate_dockwidget.py`

```python
# Dans la méthode qui initialise les connections avec filter_mate_app

def connect_to_app(self, app):
    """Connect to the main application."""
    self.app = app
    
    # Connecter le history manager
    if hasattr(self, 'history_widget') and hasattr(app, 'history_manager'):
        self.history_widget.set_history_manager(app.history_manager)
        logger.info("History widget connected to HistoryManager")
```

### Étape 3: Gérer les changements de couche

**Fichier**: `filter_mate_dockwidget.py`

```python
def on_layer_selection_changed(self, layer):
    """Handle layer selection changes."""
    # Code existant...
    
    # Mettre à jour le widget d'historique
    if hasattr(self, 'history_widget') and layer:
        self.history_widget.set_current_layer(layer.id())
        logger.debug(f"History widget updated for layer: {layer.name()}")
```

### Étape 4: Mettre à jour après les opérations de filtre

**Fichier**: `filter_mate_dockwidget.py`

```python
def on_filter_applied(self, layer_id, success):
    """Handle filter application completion."""
    # Code existant...
    
    # Mettre à jour l'historique
    if hasattr(self, 'history_widget') and success:
        self.history_widget.update_history()
        logger.debug("History widget updated after filter application")
```

### Étape 5: Implémenter les handlers de signaux

**Fichier**: `filter_mate_dockwidget.py`

```python
def _on_undo_requested(self):
    """Handle undo request from history widget."""
    logger.info("Undo requested from history widget")
    
    # Obtenir la couche active
    layer = self.get_active_layer()
    if not layer:
        return
    
    # Appeler la méthode undo de l'app
    if hasattr(self.app, 'undo_filter'):
        self.app.undo_filter(layer.id())
    
    # Mettre à jour le widget
    self.history_widget.update_history()

def _on_redo_requested(self):
    """Handle redo request from history widget."""
    logger.info("Redo requested from history widget")
    
    # Obtenir la couche active
    layer = self.get_active_layer()
    if not layer:
        return
    
    # Appeler la méthode redo de l'app
    if hasattr(self.app, 'redo_filter'):
        self.app.redo_filter(layer.id())
    
    # Mettre à jour le widget
    self.history_widget.update_history()

def _on_history_state_selected(self, state_index):
    """Handle direct jump to history state."""
    logger.info(f"Jump to history state requested: index {state_index}")
    
    # Obtenir la couche active
    layer = self.get_active_layer()
    if not layer:
        return
    
    # Appeler la méthode jump_to_state de l'app
    if hasattr(self.app, 'jump_to_history_state'):
        self.app.jump_to_history_state(layer.id(), state_index)
    
    # Mettre à jour le widget
    self.history_widget.update_history()
```

### Étape 6: Implémenter les méthodes dans FilterMateApp

**Fichier**: `filter_mate_app.py`

```python
def redo_filter(self, layer_id: str):
    """
    Redo the last undone filter operation.
    
    Args:
        layer_id: ID of the layer to redo filter on
    """
    logger.info(f"Redo filter requested for layer: {layer_id}")
    
    # Obtenir l'historique
    history = self.history_manager.get_history(layer_id)
    if not history or not history.can_redo():
        logger.warning("Cannot redo: no redo state available")
        iface.messageBar().pushWarning(
            "FilterMate",
            "No filter state to redo",
            3
        )
        return
    
    # Obtenir la couche
    layer = QgsProject.instance().mapLayer(layer_id)
    if not layer:
        logger.error(f"Layer not found: {layer_id}")
        return
    
    # Effectuer le redo
    next_state = history.redo()
    if not next_state:
        logger.error("Redo returned no state")
        return
    
    # Appliquer le filtre
    try:
        layer.setSubsetString(next_state.expression)
        logger.info(f"Redo successful: {next_state.description}")
        
        iface.messageBar().pushSuccess(
            "FilterMate",
            f"Redone: {next_state.description}",
            3
        )
        
        # Rafraîchir la couche
        layer.triggerRepaint()
        
    except Exception as e:
        logger.error(f"Error applying redo filter: {str(e)}", exc_info=True)
        iface.messageBar().pushCritical(
            "FilterMate",
            f"Error redoing filter: {str(e)}",
            5
        )

def jump_to_history_state(self, layer_id: str, state_index: int):
    """
    Jump directly to a specific history state.
    
    Args:
        layer_id: ID of the layer
        state_index: Index of the state to jump to
    """
    logger.info(f"Jump to history state: layer={layer_id}, index={state_index}")
    
    # Obtenir l'historique
    history = self.history_manager.get_history(layer_id)
    if not history:
        logger.error("No history available")
        return
    
    # Obtenir la couche
    layer = QgsProject.instance().mapLayer(layer_id)
    if not layer:
        logger.error(f"Layer not found: {layer_id}")
        return
    
    # Vérifier l'index
    if not (0 <= state_index < len(history._states)):
        logger.error(f"Invalid state index: {state_index}")
        return
    
    # Obtenir l'état
    target_state = history._states[state_index]
    
    # Mettre à jour l'index courant
    history._current_index = state_index
    
    # Appliquer le filtre
    try:
        layer.setSubsetString(target_state.expression)
        logger.info(f"Jumped to state: {target_state.description}")
        
        iface.messageBar().pushSuccess(
            "FilterMate",
            f"Restored: {target_state.description}",
            3
        )
        
        # Rafraîchir la couche
        layer.triggerRepaint()
        
    except Exception as e:
        logger.error(f"Error jumping to state: {str(e)}", exc_info=True)
        iface.messageBar().pushCritical(
            "FilterMate",
            f"Error restoring filter state: {str(e)}",
            5
        )
```

## Raccourcis clavier

### Implémentation avec QShortcut

**Fichier**: `filter_mate_dockwidget.py`

```python
from qgis.PyQt.QtWidgets import QShortcut
from qgis.PyQt.QtGui import QKeySequence

def _setup_keyboard_shortcuts(self):
    """Setup keyboard shortcuts for history navigation."""
    # Ctrl+Z: Undo
    self.undo_shortcut = QShortcut(QKeySequence.Undo, self)
    self.undo_shortcut.activated.connect(self._on_undo_requested)
    logger.debug("Undo shortcut registered (Ctrl+Z)")
    
    # Ctrl+Y: Redo
    self.redo_shortcut = QShortcut(QKeySequence.Redo, self)
    self.redo_shortcut.activated.connect(self._on_redo_requested)
    logger.debug("Redo shortcut registered (Ctrl+Y)")
    
    # Ctrl+Shift+Z: Alternative redo (common on Mac)
    self.redo_alt_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
    self.redo_alt_shortcut.activated.connect(self._on_redo_requested)
    logger.debug("Alternative redo shortcut registered (Ctrl+Shift+Z)")

# Appeler dans __init__()
def __init__(self, parent=None):
    super().__init__(parent)
    # ... code existant ...
    self._setup_keyboard_shortcuts()
```

## Tests d'intégration

### Checklist de validation

- [ ] Le widget s'affiche correctement dans l'interface
- [ ] Les boutons sont désactivés quand aucun historique n'existe
- [ ] Le bouton undo est activé après l'application d'un filtre
- [ ] Le bouton redo est activé après un undo
- [ ] Le dropdown affiche les états récents
- [ ] La sélection dans le dropdown fonctionne
- [ ] Le label de position affiche "X/Y" correctement
- [ ] Ctrl+Z déclenche undo
- [ ] Ctrl+Y déclenche redo
- [ ] Le changement de couche met à jour l'historique
- [ ] Les messages de feedback apparaissent dans la barre de messages

### Script de test manuel

```python
# À exécuter dans la console Python de QGIS

from qgis.utils import iface
from qgis.core import QgsProject

# Obtenir le dockwidget FilterMate
dock = iface.mainWindow().findChild(QDockWidget, "FilterMate")
if not dock:
    print("FilterMate dockwidget not found")
else:
    widget = dock.widget()
    
    # Vérifier que le history_widget existe
    if hasattr(widget, 'history_widget'):
        hw = widget.history_widget
        print(f"✓ History widget found")
        print(f"  - Undo enabled: {hw.undo_button.isEnabled()}")
        print(f"  - Redo enabled: {hw.redo_button.isEnabled()}")
        print(f"  - Dropdown items: {hw.dropdown.count()}")
        print(f"  - State label: {hw.dropdown.currentText()}")
    else:
        print("✗ History widget not found in dockwidget")
```

## Position recommandée dans l'interface

### Option 1: Barre horizontale sous les contrôles de filtre

```
┌─────────────────────────────────────────┐
│ Layer: [Dropdown]                       │
│ Filter Type: [Dropdown]                 │
│ [Apply Filter Button]                   │
├─────────────────────────────────────────┤
│ History: [◀] [Recent states ▼] [▶]     │  ← CompactHistoryWidget
├─────────────────────────────────────────┤
│ Results: 1,234 features                 │
└─────────────────────────────────────────┘
```

### Option 2: Section dédiée avec frame

```
┌─────────────────────────────────────────┐
│ [Apply Filter Button]                   │
├─────────────────────────────────────────┤
│ ┌─ Filter History ──────────────────┐   │
│ │ [◀] [Recent states ▼] [▶]        │   │  ← CompactHistoryWidget
│ │ Position: 3/5                     │   │
│ └───────────────────────────────────┘   │
├─────────────────────────────────────────┤
│ Results: 1,234 features                 │
└─────────────────────────────────────────┘
```

### Option 3: Toolbar séparée

```
┌─────────────────────────────────────────┐
│ [File] [Edit] [Tools]                   │
│ [◀] [Recent ▼] [▶] | [⭐ Favorites]    │  ← Toolbar avec histoire + favoris
├─────────────────────────────────────────┤
│ Layer: [Dropdown]                       │
│ [Apply Filter Button]                   │
└─────────────────────────────────────────┘
```

## Styling et thèmes

Les widgets respectent automatiquement le thème QGIS actif. Pour personnaliser :

```python
# Dans filter_mate_dockwidget.py ou ui_styles.py

def apply_history_widget_styles(widget, theme='light'):
    """Apply custom styles to history widget."""
    
    if theme == 'dark':
        widget.setStyleSheet("""
            QToolButton {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #ffffff;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
            }
            QToolButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
            QComboBox {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                color: #ffffff;
            }
        """)
    else:
        widget.setStyleSheet("""
            QToolButton {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)
```

## Performance et optimisation

### Mises à jour incrémentales

Au lieu de reconstruire tout le dropdown à chaque fois :

```python
def update_history_incremental(self, new_state):
    """Update history with just the new state."""
    # Ajouter le nouvel état au début
    self.dropdown.insertItem(0, format_state(new_state))
    
    # Limiter le nombre d'items
    while self.dropdown.count() > self.max_items:
        self.dropdown.removeItem(self.dropdown.count() - 1)
    
    # Mettre à jour les boutons
    self.update_buttons()
```

### Lazy loading pour grandes histoires

```python
def load_history_lazy(self, layer_id, limit=20):
    """Load only recent history items."""
    history = self.history_manager.get_history(layer_id)
    if history:
        recent_states = history._states[-limit:]
        self._populate_dropdown(recent_states)
```

## Dépannage

### Le widget ne s'affiche pas

1. Vérifier que le widget est ajouté au layout
2. Vérifier que `show()` est appelé si nécessaire
3. Vérifier la hiérarchie de layouts

### Les boutons restent désactivés

1. Vérifier que `set_history_manager()` a été appelé
2. Vérifier que `set_current_layer()` a été appelé
3. Vérifier que l'historique contient des états

### Les signaux ne se déclenchent pas

1. Vérifier que les connections sont établies
2. Vérifier que les handlers sont définis
3. Logger dans les handlers pour debug

### Le dropdown est vide

1. Vérifier que `update_history()` est appelé après chaque opération
2. Vérifier que le layer_id est correct
3. Logger le contenu de l'historique

## Prochaines étapes

### Améliorations possibles

1. **Icônes personnalisées**: Créer des icônes SVG pour undo/redo
2. **Prévisualisation**: Afficher un aperçu lors du survol d'un état
3. **Groupement**: Grouper les états par date/session
4. **Export**: Permettre l'export de l'historique en JSON
5. **Statistiques**: Afficher des stats (nombre d'undos, états les plus utilisés)

### Intégration avec les favoris

Le système de favoris (`filter_favorites.py`) peut être intégré avec l'historique :

```python
# Ajouter un bouton "Save as favorite" à côté de l'historique
def save_current_state_as_favorite(self):
    """Save current filter state as a favorite."""
    # Obtenir l'état courant de l'historique
    history = self.history_manager.get_history(self.current_layer_id)
    if history and history._current_index >= 0:
        current_state = history._states[history._current_index]
        
        # Créer un favori à partir de l'état
        # (nécessite conversion FilterState → FilterFavorite)
        self.favorites_manager.create_from_history_state(current_state)
```

## Références

- **Module des widgets**: `modules/ui_history_widgets.py`
- **Tests**: `tests/test_ui_history_widgets.py`
- **Audit d'historique**: `docs/FILTER_HISTORY_AUDIT.md`
- **Module d'historique**: `modules/filter_history.py`
- **Documentation PyQt5**: https://doc.qt.io/qt-5/

## Support

Pour toute question ou problème :
1. Consulter les logs: `FilterMate.HistoryWidgets`
2. Vérifier les tests unitaires
3. Consulter l'audit d'historique pour le contexte
