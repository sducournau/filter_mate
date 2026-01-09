---
storyId: MIG-075
title: Create BackendService
epic: 6.4 - Additional Services
phase: 6
sprint: 7
priority: P1
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-012]
blocks: [MIG-071, MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-075: Create BackendService

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un service pour la logique de sélection de backend,  
**Afin que** les décisions de backend soient testables et découplées de l'UI.

---

## 🎯 Objectif

Extraire les méthodes de sélection de backend de `filter_mate_dockwidget.py` (lignes 2897-3248) vers un service pur Python sans dépendances QGIS directes (utilise les ports/adapters).

---

## ✅ Critères d'Acceptation

### Code

- [ ] `core/services/backend_service.py` créé (< 300 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style
- [ ] **Aucune dépendance QGIS directe**

### Méthodes à Implémenter

- [ ] `get_available_backends_for_layer(layer_info: LayerInfo) -> List[str]`
- [ ] `detect_current_backend(layer_info: LayerInfo) -> str`
- [ ] `verify_backend_supports_layer(backend: str, layer_info: LayerInfo) -> bool`
- [ ] `get_optimal_backend_for_layer(layer_info: LayerInfo) -> str`
- [ ] `get_backend_capabilities(backend: str) -> BackendCapabilities`
- [ ] `is_backend_available(backend: str) -> bool`

### Architecture Hexagonale

- [ ] Utilise `LayerInfo` VO au lieu de `QgsVectorLayer` direct
- [ ] Utilise `BackendPort` pour les opérations backend
- [ ] Tests unitaires sans mocks QGIS

### Tests

- [ ] `tests/unit/core/services/test_backend_service.py` créé
- [ ] Tests pour détection de backend
- [ ] Tests pour sélection optimale
- [ ] Couverture > 90%

---

## 📝 Spécifications Techniques

### Structure du Service

```python
"""
Backend Service for FilterMate.

Pure Python service for backend selection logic.
No direct QGIS dependencies - uses ports/adapters.
"""

from typing import List, Optional
from dataclasses import dataclass
import logging

from core.domain.value_objects import LayerInfo
from core.ports.backend_port import BackendPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendCapabilities:
    """Capabilities of a backend."""
    supports_materialized_views: bool = False
    supports_spatial_index: bool = True
    supports_complex_expressions: bool = True
    max_features_recommended: int = 100000
    supports_concurrent_queries: bool = False


class BackendService:
    """
    Service for backend selection and capabilities.

    This service contains pure business logic for determining
    which backend to use for a given layer. It has no UI dependencies
    and can be tested without QGIS.

    Backends:
    - postgresql: Best for large datasets, materialized views
    - spatialite: Good for medium datasets, temp tables
    - ogr: Universal fallback, memory-based
    """

    BACKEND_PRIORITY = ['postgresql', 'spatialite', 'ogr']

    BACKEND_CAPABILITIES = {
        'postgresql': BackendCapabilities(
            supports_materialized_views=True,
            supports_spatial_index=True,
            supports_complex_expressions=True,
            max_features_recommended=1000000,
            supports_concurrent_queries=True,
        ),
        'spatialite': BackendCapabilities(
            supports_materialized_views=False,
            supports_spatial_index=True,
            supports_complex_expressions=True,
            max_features_recommended=100000,
            supports_concurrent_queries=False,
        ),
        'ogr': BackendCapabilities(
            supports_materialized_views=False,
            supports_spatial_index=False,
            supports_complex_expressions=False,
            max_features_recommended=10000,
            supports_concurrent_queries=False,
        ),
    }

    def __init__(self, backend_port: BackendPort) -> None:
        """
        Initialize the backend service.

        Args:
            backend_port: Port for backend operations
        """
        self._backend_port = backend_port
        self._available_backends: Optional[List[str]] = None

    def get_available_backends_for_layer(
        self,
        layer_info: LayerInfo
    ) -> List[str]:
        """
        Get backends available for a specific layer.

        Args:
            layer_info: Information about the layer

        Returns:
            List of available backend names, ordered by preference
        """
        available = []

        for backend in self.BACKEND_PRIORITY:
            if self.verify_backend_supports_layer(backend, layer_info):
                available.append(backend)

        return available

    def detect_current_backend(self, layer_info: LayerInfo) -> str:
        """
        Detect the natural backend for a layer based on its provider.

        Args:
            layer_info: Information about the layer

        Returns:
            Backend name ('postgresql', 'spatialite', or 'ogr')
        """
        provider = layer_info.provider_type

        if provider == 'postgres':
            return 'postgresql'
        elif provider == 'spatialite':
            return 'spatialite'
        else:
            return 'ogr'

    def verify_backend_supports_layer(
        self,
        backend: str,
        layer_info: LayerInfo
    ) -> bool:
        """
        Check if a backend can handle a specific layer.

        Args:
            backend: Backend name
            layer_info: Information about the layer

        Returns:
            True if the backend supports this layer
        """
        if not self.is_backend_available(backend):
            return False

        # PostgreSQL requires a postgres layer
        if backend == 'postgresql':
            return layer_info.provider_type == 'postgres'

        # Spatialite requires a spatialite layer OR a file-based layer
        if backend == 'spatialite':
            return layer_info.provider_type in ('spatialite', 'ogr')

        # OGR is always available as fallback
        return True

    def get_optimal_backend_for_layer(
        self,
        layer_info: LayerInfo
    ) -> str:
        """
        Get the optimal backend for a layer based on its characteristics.

        Args:
            layer_info: Information about the layer

        Returns:
            Recommended backend name
        """
        available = self.get_available_backends_for_layer(layer_info)

        if not available:
            logger.warning("No backends available, falling back to OGR")
            return 'ogr'

        # Consider feature count for optimization
        feature_count = layer_info.feature_count

        for backend in available:
            caps = self.get_backend_capabilities(backend)
            if feature_count <= caps.max_features_recommended:
                return backend

        # Return first available (highest priority)
        return available[0]

    def get_backend_capabilities(self, backend: str) -> BackendCapabilities:
        """
        Get capabilities for a backend.

        Args:
            backend: Backend name

        Returns:
            BackendCapabilities dataclass
        """
        return self.BACKEND_CAPABILITIES.get(
            backend,
            self.BACKEND_CAPABILITIES['ogr']
        )

    def is_backend_available(self, backend: str) -> bool:
        """
        Check if a backend is available in the current environment.

        Args:
            backend: Backend name

        Returns:
            True if the backend is available
        """
        if self._available_backends is None:
            self._available_backends = self._backend_port.get_available_backends()

        return backend in self._available_backends
```

---

## 🔗 Dépendances

### Entrée

- MIG-012: FilterService (pattern à suivre)
- `core/ports/backend_port.py` existant

### Sortie

- MIG-071: BackendController (utilise ce service)
- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                | Avant       | Après        |
| ----------------------- | ----------- | ------------ |
| Logique dans dockwidget | ~350 lignes | 0            |
| Nouveau fichier         | -           | < 300 lignes |
| Testabilité             | Faible      | 100%         |

---

## 🧪 Scénarios de Test

### Test 1: Detect PostgreSQL Backend

```python
def test_detect_postgresql_backend():
    """Une couche postgres doit retourner le backend postgresql."""
    service = BackendService(mock_port)
    layer_info = LayerInfo(provider_type='postgres', feature_count=1000)

    result = service.detect_current_backend(layer_info)

    assert result == 'postgresql'
```

### Test 2: Get Optimal Backend for Large Dataset

```python
def test_optimal_backend_large_dataset():
    """Un gros dataset doit recommander PostgreSQL si disponible."""
    mock_port = Mock()
    mock_port.get_available_backends.return_value = ['postgresql', 'spatialite', 'ogr']
    service = BackendService(mock_port)
    layer_info = LayerInfo(provider_type='postgres', feature_count=500000)

    result = service.get_optimal_backend_for_layer(layer_info)

    assert result == 'postgresql'
```

### Test 3: Fallback to OGR When No Backend Available

```python
def test_fallback_to_ogr():
    """OGR doit être utilisé si aucun autre backend n'est disponible."""
    mock_port = Mock()
    mock_port.get_available_backends.return_value = ['ogr']
    service = BackendService(mock_port)
    layer_info = LayerInfo(provider_type='ogr', feature_count=1000)

    result = service.get_optimal_backend_for_layer(layer_info)

    assert result == 'ogr'
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `core/services/backend_service.py`
- [ ] Implémenter `BackendService`
- [ ] Créer `BackendCapabilities` dataclass
- [ ] Ajouter export dans `core/services/__init__.py`
- [ ] Créer fichier de test
- [ ] Vérifier pas de dépendances QGIS directes

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
