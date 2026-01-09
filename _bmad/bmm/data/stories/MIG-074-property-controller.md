---
storyId: MIG-074
title: Create PropertyController
epic: 6.3 - New Controllers
phase: 6
sprint: 7
priority: P2
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-020, MIG-073]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-074: Create PropertyController

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un controller pour les propriétés,  
**Afin que** les changements de propriétés soient centralisés et testables.

---

## 🎯 Objectif

Extraire les méthodes de gestion des propriétés de `filter_mate_dockwidget.py` (lignes 10796-11374) vers un controller dédié.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `ui/controllers/property_controller.py` créé (< 400 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes Extraites

- [ ] `project_property_changed()`
- [ ] `layer_property_changed()`
- [ ] `_update_buffer_validation()`
- [ ] `_on_geometry_type_changed()`
- [ ] `_on_crs_changed()`
- [ ] `_on_extent_changed()`
- [ ] `_validate_property_value()`
- [ ] `_apply_property_to_widgets()`

### Intégration

- [ ] Coordonne avec LayerSyncController (MIG-073)
- [ ] Délégation depuis dockwidget fonctionne
- [ ] Signaux Qt correctement gérés

### Tests

- [ ] `tests/unit/ui/controllers/test_property_controller.py` créé
- [ ] Tests pour changement de propriété projet
- [ ] Tests pour changement de propriété layer
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Controller

```python
"""
Property Controller for FilterMate.

Manages project and layer property change events.
Extracted from filter_mate_dockwidget.py (lines 10796-11374).
"""

from typing import TYPE_CHECKING, Any, Optional
import logging

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsVectorLayer, QgsProject

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class PropertyController(QObject):
    """
    Controller for property management.

    Handles:
    - Project property changes
    - Layer property changes
    - Buffer validation updates
    - Geometry type changes

    Signals:
        property_changed: Emitted when a property changes
        buffer_validation_updated: Emitted when buffer validation changes
    """

    property_changed = pyqtSignal(str, str, object)  # source, key, value
    buffer_validation_updated = pyqtSignal(bool)  # is_valid

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the property controller.

        Args:
            dockwidget: Main dockwidget reference
        """
        super().__init__()
        self.dockwidget = dockwidget

    def setup(self) -> None:
        """Connect to property change signals."""
        QgsProject.instance().writeProject.connect(self._on_project_saved)

    def project_property_changed(self, key: str, value: Any) -> None:
        """
        Handle project property change.

        Args:
            key: Property key that changed
            value: New property value
        """
        logger.debug(f"Project property changed: {key} = {value}")

        if key == 'crs':
            self._on_project_crs_changed(value)
        elif key == 'extent':
            self._on_project_extent_changed(value)

        self.property_changed.emit('project', key, value)

    def layer_property_changed(
        self,
        layer: QgsVectorLayer,
        key: str,
        value: Any
    ) -> None:
        """
        Handle layer property change.

        Args:
            layer: Layer that changed
            key: Property key that changed
            value: New property value
        """
        logger.debug(f"Layer {layer.name()} property changed: {key} = {value}")

        if key == 'geometry_type':
            self._on_geometry_type_changed(layer, value)
        elif key == 'crs':
            self._on_layer_crs_changed(layer, value)

        self.property_changed.emit('layer', key, value)
        self._update_buffer_validation(layer)

    def _update_buffer_validation(self, layer: QgsVectorLayer) -> None:
        """
        Update buffer validation state for layer.

        Args:
            layer: Current layer
        """
        # Check if buffer operations are valid for this layer
        geom_type = layer.geometryType()
        crs = layer.crs()

        # Buffer requires a valid CRS
        is_valid = crs.isValid() and not crs.isGeographic()

        self.buffer_validation_updated.emit(is_valid)

        if not is_valid:
            logger.warning(
                f"Buffer operations disabled for {layer.name()}: "
                f"CRS is geographic or invalid"
            )

    def _on_geometry_type_changed(
        self,
        layer: QgsVectorLayer,
        new_type: int
    ) -> None:
        """Handle geometry type change."""
        # Update icons and available operations
        pass

    def _on_project_crs_changed(self, new_crs) -> None:
        """Handle project CRS change."""
        pass

    def _on_layer_crs_changed(
        self,
        layer: QgsVectorLayer,
        new_crs
    ) -> None:
        """Handle layer CRS change."""
        self._update_buffer_validation(layer)
```

---

## 🔗 Dépendances

### Entrée

- MIG-020: FilteringController (coordination)
- MIG-073: LayerSyncController (événements layer)

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique               | Avant | Après        |
| ---------------------- | ----- | ------------ |
| Lignes dans dockwidget | ~580  | 0            |
| Nouveau fichier        | -     | < 400 lignes |

---

## 🧪 Scénarios de Test

### Test 1: Layer Property Change

```python
def test_layer_property_changed():
    """Le changement de propriété doit émettre un signal."""
    controller = PropertyController(mock_dockwidget)
    mock_layer = Mock()

    with patch.object(controller, 'property_changed') as signal:
        controller.layer_property_changed(mock_layer, 'crs', 'EPSG:4326')

    signal.emit.assert_called_once()
```

### Test 2: Buffer Validation for Geographic CRS

```python
def test_buffer_invalid_for_geographic_crs():
    """Le buffer doit être invalide pour un CRS géographique."""
    controller = PropertyController(mock_dockwidget)
    mock_layer = Mock()
    mock_layer.crs.return_value.isGeographic.return_value = True

    with patch.object(controller, 'buffer_validation_updated') as signal:
        controller._update_buffer_validation(mock_layer)

    signal.emit.assert_called_with(False)
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `ui/controllers/property_controller.py`
- [ ] Implémenter `PropertyController`
- [ ] Ajouter export dans `ui/controllers/__init__.py`
- [ ] Créer délégation dans dockwidget
- [ ] Créer fichier de test
- [ ] Vérifier intégration avec LayerSyncController

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
