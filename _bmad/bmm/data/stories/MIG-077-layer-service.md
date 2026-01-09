---
storyId: MIG-077
title: Create LayerService
epic: 6.4 - Additional Services
phase: 6
sprint: 7
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-012]
blocks: [MIG-073, MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-077: Create LayerService

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un service pour la validation et manipulation des layers,  
**Afin que** les opérations sur layers soient testables et centralisées.

---

## 🎯 Objectif

Extraire les méthodes de validation et manipulation des layers de `filter_mate_dockwidget.py` (lignes 9543-9702, 10437-10561) vers un service.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `core/services/layer_service.py` créé (< 300 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes à Implémenter

- [ ] `validate_layer(layer) -> ValidationResult`
- [ ] `prepare_layer_for_filtering(layer) -> bool`
- [ ] `reset_layer_expressions(layer) -> bool`
- [ ] `ensure_valid_current_layer(layer) -> Optional[LayerInfo]`
- [ ] `is_layer_truly_deleted(layer_id: str) -> bool`
- [ ] `get_layer_info(layer) -> LayerInfo`
- [ ] `get_layer_feature_count(layer) -> int`
- [ ] `get_layer_geometry_type(layer) -> GeometryType`

### Intégration

- [ ] Utilise `LayerInfo` VO pour retourner les informations
- [ ] Utilise `QGISLayerAdapter` pour les opérations QGIS
- [ ] Délègue les opérations QGIS à l'adapter

### Tests

- [ ] `tests/unit/core/services/test_layer_service.py` créé
- [ ] Tests pour validation
- [ ] Tests pour reset expressions
- [ ] Couverture > 85%

---

## 📝 Spécifications Techniques

### Structure du Service

```python
"""
Layer Service for FilterMate.

Service for layer validation and manipulation.
Uses adapters for QGIS operations.
"""

from typing import Optional
from dataclasses import dataclass
from enum import Enum, auto
import logging

from core.domain.value_objects import LayerInfo
from adapters.qgis.layer_adapter import QGISLayerAdapter

logger = logging.getLogger(__name__)


class GeometryType(Enum):
    """Layer geometry types."""
    POINT = auto()
    LINE = auto()
    POLYGON = auto()
    UNKNOWN = auto()
    NO_GEOMETRY = auto()


@dataclass
class ValidationResult:
    """Result of layer validation."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class LayerService:
    """
    Service for layer validation and manipulation.

    This service provides:
    - Layer validation (geometry, CRS, features)
    - Layer preparation for filtering
    - Expression reset
    - Layer info extraction

    QGIS operations are delegated to QGISLayerAdapter.
    """

    def __init__(self, layer_adapter: QGISLayerAdapter) -> None:
        """
        Initialize the layer service.

        Args:
            layer_adapter: Adapter for QGIS layer operations
        """
        self._adapter = layer_adapter

    def validate_layer(self, layer) -> ValidationResult:
        """
        Validate a layer for FilterMate operations.

        Args:
            layer: QGIS vector layer

        Returns:
            ValidationResult with status and any errors/warnings
        """
        errors = []
        warnings = []

        # Check layer validity
        if not self._adapter.is_valid(layer):
            errors.append("Layer is not valid")
            return ValidationResult(False, errors, warnings)

        # Check if it's a vector layer
        if not self._adapter.is_vector_layer(layer):
            errors.append("Layer is not a vector layer")
            return ValidationResult(False, errors, warnings)

        # Check for features
        feature_count = self._adapter.get_feature_count(layer)
        if feature_count == 0:
            warnings.append("Layer has no features")

        # Check for geometry
        if not self._adapter.has_geometry(layer):
            warnings.append("Layer has no geometry (attribute-only)")

        # Check CRS
        if not self._adapter.has_valid_crs(layer):
            warnings.append("Layer CRS is not defined")

        # Large layer warning
        if feature_count > 100000:
            warnings.append(
                f"Large layer ({feature_count} features). "
                "Consider using PostgreSQL backend for better performance."
            )

        return ValidationResult(True, errors, warnings)

    def prepare_layer_for_filtering(self, layer) -> bool:
        """
        Prepare a layer for filtering operations.

        Args:
            layer: QGIS vector layer

        Returns:
            True if layer is ready for filtering
        """
        validation = self.validate_layer(layer)
        if not validation.is_valid:
            logger.error(f"Layer validation failed: {validation.errors}")
            return False

        if validation.has_warnings:
            for warning in validation.warnings:
                logger.warning(warning)

        return True

    def reset_layer_expressions(self, layer) -> bool:
        """
        Reset all filter expressions on a layer.

        Args:
            layer: QGIS vector layer

        Returns:
            True if reset successful
        """
        try:
            self._adapter.set_subset_string(layer, "")
            logger.debug(f"Reset expressions for layer: {layer.name()}")
            return True
        except Exception as e:
            logger.error(f"Failed to reset expressions: {e}")
            return False

    def ensure_valid_current_layer(
        self,
        layer
    ) -> Optional[LayerInfo]:
        """
        Ensure a layer is valid and return its info.

        Args:
            layer: QGIS vector layer or None

        Returns:
            LayerInfo if valid, None otherwise
        """
        if layer is None:
            return None

        validation = self.validate_layer(layer)
        if not validation.is_valid:
            return None

        return self.get_layer_info(layer)

    def is_layer_truly_deleted(self, layer_id: str) -> bool:
        """
        Check if a layer ID refers to a deleted layer.

        Args:
            layer_id: Layer ID to check

        Returns:
            True if the layer no longer exists
        """
        return self._adapter.get_layer_by_id(layer_id) is None

    def get_layer_info(self, layer) -> LayerInfo:
        """
        Extract layer information into a value object.

        Args:
            layer: QGIS vector layer

        Returns:
            LayerInfo value object
        """
        return LayerInfo(
            id=self._adapter.get_id(layer),
            name=self._adapter.get_name(layer),
            provider_type=self._adapter.get_provider_type(layer),
            feature_count=self._adapter.get_feature_count(layer),
            geometry_type=self.get_layer_geometry_type(layer),
            crs=self._adapter.get_crs(layer),
            source=self._adapter.get_source(layer),
        )

    def get_layer_geometry_type(self, layer) -> GeometryType:
        """
        Get the geometry type of a layer.

        Args:
            layer: QGIS vector layer

        Returns:
            GeometryType enum value
        """
        geom_type = self._adapter.get_geometry_type(layer)

        mapping = {
            0: GeometryType.POINT,
            1: GeometryType.LINE,
            2: GeometryType.POLYGON,
            4: GeometryType.NO_GEOMETRY,
        }

        return mapping.get(geom_type, GeometryType.UNKNOWN)

    def get_layer_feature_count(self, layer) -> int:
        """
        Get the feature count of a layer.

        Args:
            layer: QGIS vector layer

        Returns:
            Number of features
        """
        return self._adapter.get_feature_count(layer)
```

---

## 🔗 Dépendances

### Entrée

- MIG-012: FilterService (pattern à suivre)
- `adapters/qgis/layer_adapter.py` (à créer si inexistant)

### Sortie

- MIG-073: LayerSyncController (utilise ce service)
- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                | Avant       | Après        |
| ----------------------- | ----------- | ------------ |
| Logique dans dockwidget | ~280 lignes | 0            |
| Nouveau fichier         | -           | < 300 lignes |
| Testabilité             | Faible      | Élevée       |

---

## 🧪 Scénarios de Test

### Test 1: Validate Valid Layer

```python
def test_validate_valid_layer():
    """Un layer valide doit passer la validation."""
    mock_adapter = Mock()
    mock_adapter.is_valid.return_value = True
    mock_adapter.is_vector_layer.return_value = True
    mock_adapter.get_feature_count.return_value = 1000
    mock_adapter.has_geometry.return_value = True
    mock_adapter.has_valid_crs.return_value = True

    service = LayerService(mock_adapter)
    result = service.validate_layer(mock_layer)

    assert result.is_valid is True
    assert result.errors == []
```

### Test 2: Validate Large Layer Warning

```python
def test_validate_large_layer_warning():
    """Un gros layer doit générer un warning."""
    mock_adapter = Mock()
    mock_adapter.is_valid.return_value = True
    mock_adapter.is_vector_layer.return_value = True
    mock_adapter.get_feature_count.return_value = 500000
    mock_adapter.has_geometry.return_value = True
    mock_adapter.has_valid_crs.return_value = True

    service = LayerService(mock_adapter)
    result = service.validate_layer(mock_layer)

    assert result.is_valid is True
    assert any("Large layer" in w for w in result.warnings)
```

### Test 3: Reset Expressions

```python
def test_reset_layer_expressions():
    """Le reset doit appeler setSubsetString avec chaine vide."""
    mock_adapter = Mock()
    service = LayerService(mock_adapter)

    result = service.reset_layer_expressions(mock_layer)

    assert result is True
    mock_adapter.set_subset_string.assert_called_with(mock_layer, "")
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `core/services/layer_service.py`
- [ ] Créer/vérifier `adapters/qgis/layer_adapter.py` existe
- [ ] Implémenter `LayerService`
- [ ] Créer `ValidationResult` et `GeometryType`
- [ ] Ajouter export dans `core/services/__init__.py`
- [ ] Créer fichier de test
- [ ] Vérifier intégration avec LayerSyncController

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
