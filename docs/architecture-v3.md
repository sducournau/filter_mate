# FilterMate v3.0 - Architecture Documentation

> **⚠️ DOCUMENT OBSOLÈTE**  
> **Remplacé par**: [`architecture-unified-v4.0.md`](consolidation/architecture-unified-v4.0.md)  
> **Date de dépréciation**: 11 janvier 2026  
> **Raison**: Documentation consolidée v4.0 disponible avec réconciliation v3.x/v4.x

---

## 📚 Documentation Actuelle

**Ce document a été remplacé par la documentation consolidée v4.0:**

- **Architecture complète**: [architecture-unified-v4.0.md](consolidation/architecture-unified-v4.0.md)
- **Décisions architecturales**: [ADR-001](consolidation/ADR-001-v3-v4-architecture-reconciliation.md)
- **Progrès migration**: [migration-progress-report-v4.0.md](consolidation/migration-progress-report-v4.0.md)
- **Index complet**: [BMAD_DOCUMENTATION_INDEX.md](consolidation/BMAD_DOCUMENTATION_INDEX.md)

**Backup original**: `_backups/docs/architecture-v3.md.backup-2026-01-11`

---

> **Version**: 3.0.0 | **Status**: ⚠️ DEPRECATED | **Date**: January 2026

## 📋 Executive Summary

FilterMate v3.0 introduces a complete architectural refactoring based on **Hexagonal Architecture** (Ports & Adapters pattern) to achieve:

- **Single Responsibility**: Maximum 800 lines per file
- **High Testability**: 90%+ code coverage enabled through dependency injection
- **Multi-Backend Support**: PostgreSQL, Spatialite, OGR, and Memory backends
- **Clean Separation**: Core domain logic isolated from QGIS dependencies

## 🏗️ Architecture Overview

### High-Level View

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          QGIS Plugin Entry Point                         │
│                            filter_mate.py                                │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────────┐
│                          Composition Root                                │
│                          FilterMateApp                                   │
│  • Dependency injection setup                                            │
│  • Service registration                                                  │
│  • Controller initialization                                             │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   UI Layer    │       │   Core Domain   │       │    Adapters     │
│               │       │                 │       │                 │
│ • DockWidget  │       │ • Services      │       │ • Backends      │
│ • Controllers │       │ • Ports         │       │ • Repositories  │
│ • Widgets     │       │ • Domain Types  │       │ • QGIS Tasks    │
│ • Dialogs     │       │                 │       │                 │
└───────────────┘       └─────────────────┘       └─────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐
          │  Infrastructure │         │   Config Layer  │
          │                 │         │                 │
          │ • Cache Manager │         │ • config.json   │
          │ • Logger        │         │ • Schema        │
          │ • Utils         │         │ • Migration     │
          └─────────────────┘         └─────────────────┘
```

### Directory Structure

```
filter_mate/
├── filter_mate.py              # QGIS entry point
├── filter_mate_app.py          # Composition Root
│
├── core/                       # Pure Python - No QGIS dependencies
│   ├── domain/                 # Value Objects & Entities
│   │   ├── filter_expression.py
│   │   ├── filter_result.py
│   │   ├── layer_info.py
│   │   └── optimization_config.py
│   │
│   ├── services/               # Business Logic
│   │   ├── filter_service.py
│   │   ├── export_service.py
│   │   ├── expression_service.py
│   │   ├── optimization_service.py
│   │   └── history_service.py
│   │
│   └── ports/                  # Interfaces (Abstract Base Classes)
│       ├── backend_port.py
│       ├── repository_port.py
│       └── config_port.py
│
├── adapters/                   # External World Integration
│   ├── backends/               # Filter Backends
│   │   ├── factory.py
│   │   ├── postgresql_backend.py
│   │   ├── spatialite_backend.py
│   │   ├── ogr_backend.py
│   │   └── memory_backend.py
│   │
│   ├── repositories/           # Data Access
│   │   ├── layer_repository.py
│   │   ├── config_repository.py
│   │   └── favorites_repository.py
│   │
│   └── qgis/                   # QGIS-specific adapters
│       └── tasks/              # QgsTask implementations
│
├── ui/                         # User Interface Layer
│   ├── controllers/            # UI Controllers
│   └── widgets/                # Reusable widgets
│
├── infrastructure/             # Cross-cutting concerns
│   ├── cache/
│   ├── config/
│   ├── logging/
│   └── utils/
│
├── config/                     # Configuration files
│   ├── config.json
│   └── config_schema.json
│
└── tests/                      # Test suites
    ├── unit/
    ├── integration/
    ├── performance/
    └── regression/
```

## 🎯 Core Domain Layer

The core domain contains pure Python code with **no QGIS dependencies**, making it fully testable.

### Domain Objects

#### FilterExpression

```python
# core/domain/filter_expression.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class FilterExpression:
    """Immutable value object representing a filter expression."""

    expression: str
    layer_id: str
    backend_type: Optional[str] = None
    is_geometric: bool = False
    predicate: Optional[str] = None
    buffer_distance: float = 0.0
```

#### FilterResult

```python
# core/domain/filter_result.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class FilterResult:
    """Result of a filtering operation."""

    success: bool
    expression: str
    feature_count: int
    execution_time_ms: float
    backend_used: str
    feature_ids: Optional[List[int]] = None
    error_message: Optional[str] = None
    optimization_applied: Optional[str] = None
```

### Ports (Interfaces)

#### BackendPort

```python
# core/ports/backend_port.py
from abc import ABC, abstractmethod
from typing import Tuple

class BackendPort(ABC):
    """Interface for filter backends."""

    @abstractmethod
    def apply_geometric_filter(
        self,
        predicate: str,
        geometry_wkt: str,
        buffer_distance: float,
        **kwargs
    ) -> Tuple[bool, str, int]:
        """Apply a geometric filter and return (success, expression, count)."""
        pass

    @abstractmethod
    def supports_optimization(self, optimization_type: str) -> bool:
        """Check if backend supports a specific optimization."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return backend name for identification."""
        pass
```

### Services

#### FilterService

```python
# core/services/filter_service.py
from typing import Optional
from core.ports.backend_port import BackendPort
from core.domain.filter_result import FilterResult

class FilterService:
    """Main filtering orchestration service."""

    def __init__(self, backend: BackendPort, cache=None, logger=None):
        self._backend = backend
        self._cache = cache
        self._logger = logger

    def apply_filter(
        self,
        expression: str,
        layer_id: str,
        use_optimization: bool = True
    ) -> FilterResult:
        """Apply filter with optional optimization."""
        # Implementation...
```

## 🔌 Adapters Layer

### Multi-Backend System

The adapter layer implements the `BackendPort` interface for each supported data source:

```
                    ┌─────────────────┐
                    │   BackendPort   │
                    │   (Interface)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌────────────────┐   ┌────────────────┐
│  PostgreSQL   │   │   Spatialite   │   │      OGR       │
│   Backend     │   │    Backend     │   │    Backend     │
├───────────────┤   ├────────────────┤   ├────────────────┤
│ • MV Support  │   │ • R-tree Index │   │ • Universal    │
│ • Connection  │   │ • Temp Tables  │   │ • File-based   │
│   Pooling     │   │ • Caching      │   │ • Fallback     │
│ • Query Opt   │   │ • GeoPackage   │   │ • Shapefile    │
└───────────────┘   └────────────────┘   └────────────────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Backend Factory │
                    │                 │
                    │ Selects optimal │
                    │ backend based   │
                    │ on layer type   │
                    └─────────────────┘
```

#### Backend Factory

```python
# adapters/backends/factory.py
from typing import Dict, Type
from core.ports.backend_port import BackendPort

class BackendFactory:
    """Factory for creating appropriate filter backends."""

    _backends: Dict[str, Type[BackendPort]] = {
        'postgresql': PostgreSQLBackend,
        'spatialite': SpatialiteBackend,
        'ogr': OGRBackend,
        'memory': MemoryBackend,
    }

    def get_backend(self, layer_provider: str, **kwargs) -> BackendPort:
        """Get optimal backend for layer provider type."""
        # Small dataset optimization
        if self._should_use_memory_optimization(kwargs):
            return MemoryBackend(**kwargs)

        backend_class = self._backends.get(layer_provider, OGRBackend)
        return backend_class(**kwargs)
```

### Backend Optimizations

| Backend        | Optimization         | Use Case                           |
| -------------- | -------------------- | ---------------------------------- |
| **PostgreSQL** | Materialized Views   | Repeated filters on large datasets |
| **PostgreSQL** | Connection Pooling   | High-frequency operations          |
| **Spatialite** | R-tree Spatial Index | Geometric filtering                |
| **Spatialite** | Temporary Tables     | Complex multi-step filters         |
| **OGR**        | Expression Caching   | Repeated filter expressions        |
| **Memory**     | Direct Processing    | Small datasets (<10k features)     |

### Repositories

```python
# adapters/repositories/config_repository.py
from core.ports.repository_port import ConfigRepositoryPort
from pathlib import Path
import json

class ConfigRepository(ConfigRepositoryPort):
    """File-based configuration repository."""

    def __init__(self, config_path: Path):
        self._config_path = config_path

    def load(self) -> dict:
        if self._config_path.exists():
            return json.loads(self._config_path.read_text())
        return self._get_defaults()

    def save(self, config: dict) -> None:
        self._config_path.write_text(json.dumps(config, indent=2))
```

## 🖥️ UI Layer

### Controller Pattern

The UI uses a lightweight MVC pattern where controllers handle user interactions:

```python
# ui/controllers/filtering_controller.py
from core.services.filter_service import FilterService
from core.domain.filter_result import FilterResult

class FilteringController:
    """Controller for filtering tab."""

    def __init__(self, filter_service: FilterService, view):
        self._filter_service = filter_service
        self._view = view

    def on_apply_filter(self, expression: str) -> None:
        """Handle filter application request."""
        result = self._filter_service.apply_filter(expression)
        self._update_view(result)

    def _update_view(self, result: FilterResult) -> None:
        if result.success:
            self._view.show_success(f"Filtered {result.feature_count} features")
        else:
            self._view.show_error(result.error_message)
```

## 🔧 Infrastructure Layer

### Cache Manager

```python
# infrastructure/cache/cache_manager.py
from typing import Optional, Any
from datetime import datetime, timedelta

class CacheManager:
    """Centralized cache management."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and datetime.now() - entry['timestamp'] < self._ttl:
            return entry['value']
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = {
            'value': value,
            'timestamp': datetime.now()
        }
```

### Provider Utilities

```python
# infrastructure/utils/provider_utils.py
PROVIDER_MAPPING = {
    'postgres': 'postgresql',
    'spatialite': 'spatialite',
    'ogr': 'ogr',
    'memory': 'memory',
    'delimitedtext': 'ogr',
    'WFS': 'ogr',
}

def detect_provider(layer) -> str:
    """Detect and normalize layer provider type."""
    raw_provider = layer.providerType()
    return PROVIDER_MAPPING.get(raw_provider, 'ogr')
```

## 🧪 Testing Strategy

### Test Structure

```
tests/
├── conftest.py                 # Shared fixtures
│
├── unit/                       # Unit tests (fast, isolated)
│   ├── core/
│   │   ├── test_filter_service.py
│   │   └── test_domain_objects.py
│   └── adapters/
│       └── test_backend_factory.py
│
├── integration/                # Integration tests
│   ├── workflows/              # E2E workflow tests
│   │   ├── test_filtering_workflow.py
│   │   └── test_export_workflow.py
│   └── backends/               # Backend integration
│       ├── test_postgresql_integration.py
│       ├── test_spatialite_integration.py
│       └── test_ogr_integration.py
│
├── performance/                # Performance benchmarks
│   ├── test_filtering_benchmarks.py
│   └── benchmark_utils.py
│
└── regression/                 # Regression tests
    ├── test_known_issues.py
    ├── test_edge_cases.py
    └── test_compatibility.py
```

### Test Coverage Goals

| Layer          | Target Coverage | Tests Count |
| -------------- | --------------- | ----------- |
| Core Domain    | 95%+            | 150+        |
| Adapters       | 90%+            | 100+        |
| UI Controllers | 85%+            | 50+         |
| Infrastructure | 90%+            | 75+         |
| **Total**      | **90%+**        | **375+**    |

### Running Tests

```bash
# All tests
pytest tests/ -v

# By category
pytest tests/unit/ -v --cov=core
pytest tests/integration/ -v -m integration
pytest tests/performance/ -v -m benchmark
pytest tests/regression/ -v -m regression

# Quick validation
pytest tests/unit/ tests/integration/ -v --tb=short
```

## 📊 Metrics & Quality

### Architecture Metrics (v3.0 vs v2.x)

| Metric                | v2.9.x       | v3.0       | Improvement |
| --------------------- | ------------ | ---------- | ----------- |
| Largest file          | 12,944 lines | ~800 lines | 94% ↓       |
| Code duplication      | ~15%         | <2%        | 87% ↓       |
| Cyclomatic complexity | 45 avg       | 12 avg     | 73% ↓       |
| Test coverage         | ~35%         | 90%+       | 157% ↑      |
| Coupling score        | 8/10         | 3/10       | 62% ↓       |

### Performance Baselines

| Operation                        | Target | Backend    |
| -------------------------------- | ------ | ---------- |
| Simple filter (1k features)      | <50ms  | Any        |
| Complex filter (10k features)    | <200ms | Any        |
| Geometric filter (100k features) | <500ms | PostgreSQL |
| Backend initialization           | <100ms | All        |
| Expression parsing               | <10ms  | N/A        |

## 🔄 Migration from v2.x

### User Impact

- **Zero breaking changes**: All user configurations migrate automatically
- **Same UI**: Visual interface unchanged
- **Better performance**: Optimized backend selection
- **Improved stability**: Better error handling

### Developer Impact

- **New module structure**: Import paths changed
- **Dependency injection**: Services receive dependencies
- **Port-based testing**: Mock via interfaces
- **Clear boundaries**: Core domain has no QGIS deps

## �️ Legacy Removal Roadmap

### Current State (v3.0.21)

The codebase currently maintains **dual architecture** for backward compatibility:

| Architecture        | Location                                       | Status        | Removal Target |
| ------------------- | ---------------------------------------------- | ------------- | -------------- |
| **New (Hexagonal)** | `core/`, `adapters/`, `ui/`, `infrastructure/` | ✅ Production | Keep           |
| **Legacy**          | `modules/`                                     | ⚠️ Deprecated | v4.0.0         |

### Planned Phases

| Phase       | Version   | Focus                 | Status     |
| ----------- | --------- | --------------------- | ---------- |
| **Phase 1** | v3.1→v3.2 | Backend Consolidation | 📋 Planned |
| **Phase 2** | v3.2→v3.3 | Tasks Consolidation   | 📋 Planned |
| **Phase 3** | v3.3→v3.4 | Utilities Migration   | 📋 Planned |
| **Phase 4** | v3.4→v4.0 | Final Cleanup         | 📋 Planned |

### Key Migrations

```
modules/backends/          → adapters/backends/     (Phase 1)
modules/tasks/             → adapters/qgis/tasks/   (Phase 2)
modules/appUtils.py        → Split to multiple      (Phase 3)
modules/*.py               → core/, infrastructure/ (Phase 3)
```

For detailed migration plan, see [Legacy Removal Roadmap](../_bmad/bmm/data/legacy-removal-roadmap.md).

## 📚 Related Documentation

- [Developer Guide](development-guide.md)
- [Migration Guide](migration-v3.md)
- [API Reference](api-reference.md)
- [Backend Audit Report](BACKEND_AUDIT_REPORT.md)
- [Component Inventory](component-inventory.md)
- [Legacy Removal Roadmap](../_bmad/bmm/data/legacy-removal-roadmap.md)

---

_Last updated: January 2026 | FilterMate v3.0.21_
