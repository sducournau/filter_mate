# FilterMate v4.0 - Unified Architecture Documentation

**Version**: 4.0  
**Date**: 2026-01-10  
**Status**: Consolidation Phase  
**Architecture Pattern**: Layered Hybrid (v3.x MVC + v4.x Hexagonal)

---

## 🏗️ Architecture Overview

FilterMate uses a **Layered Hybrid Architecture** combining:

1. **v3.x MVC Controllers** (UI Layer) - ~8,154 lines
2. **v4.x Hexagonal Services** (Business Logic) - ~1,121 lines

This design maximizes value from both migrations while maintaining clear boundaries.

```
┌──────────────────────────────────────────────────────────┐
│                    UI LAYER (v3.x)                       │
│                 MVC Controllers Pattern                   │
├──────────────────────────────────────────────────────────┤
│  FilteringController │ ExploringController │ Exporting   │
│  BackendController   │ LayerSyncController │ Config      │
│                                                           │
│  BaseController (abstract) + Mixins                      │
│  ControllerIntegration (orchestration)                   │
│  ControllerRegistry (lifecycle)                          │
└──────────────────────────────────────────────────────────┘
                            ▼ uses (DI)
┌──────────────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER                          │
│         FilterMateApp + FilterMateDockWidget             │
├──────────────────────────────────────────────────────────┤
│  • Application lifecycle                                 │
│  • Service instantiation (lazy)                          │
│  • Controller coordination                               │
│  • Legacy fallbacks (Strangler Fig)                      │
│  • Plugin integration                                    │
└──────────────────────────────────────────────────────────┘
                            ▼ coordinates
┌──────────────────────────────────────────────────────────┐
│            BUSINESS LOGIC LAYER (v4.x)                   │
│           Hexagonal (Ports & Adapters)                   │
├──────────────────────────────────────────────────────────┤
│  LayerLifecycleService  │ TaskManagementService          │
│  FilteringService*       │ ExportService*                 │
│                                                           │
│  (*future services)                                      │
└──────────────────────────────────────────────────────────┘
                            ▼ implements
┌──────────────────────────────────────────────────────────┐
│               DOMAIN LAYER                                │
│          Pure Domain Logic + Interfaces                  │
├──────────────────────────────────────────────────────────┤
│  core/domain/     │ Business entities                    │
│  core/ports/      │ Service interfaces (Protocols)       │
└──────────────────────────────────────────────────────────┘
                            ▼ uses
┌──────────────────────────────────────────────────────────┐
│            INFRASTRUCTURE LAYER                           │
│        Adapters + Repositories + External Systems        │
├──────────────────────────────────────────────────────────┤
│  adapters/backends/  │ PostgreSQL, Spatialite, OGR       │
│  adapters/qgis/      │ QGIS API integration              │
│  adapters/repositories/ │ Data access                    │
│  infrastructure/     │ External services                 │
└──────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
filter_mate/
│
├── ui/controllers/                 # v3.x MVC Controllers (UI Layer)
│   ├── base_controller.py         # Abstract base for all controllers
│   ├── filtering_controller.py    # Filtering tab logic (1,066 lines)
│   ├── exploring_controller.py    # Exploring tab logic
│   ├── exporting_controller.py    # Export tab logic
│   ├── backend_controller.py      # Backend management
│   ├── layer_sync_controller.py   # Layer synchronization
│   ├── config_controller.py       # Configuration UI
│   ├── integration.py              # ControllerIntegration (1,782 lines)
│   ├── registry.py                 # ControllerRegistry (lifecycle)
│   └── mixins/                     # Reusable controller behaviors
│       ├── layer_selection_mixin.py
│       └── task_mixin.py
│
├── core/                           # v4.x Hexagonal Architecture
│   ├── services/                   # Business Logic Layer
│   │   ├── layer_lifecycle_service.py   # Layer management (755 lines)
│   │   ├── task_management_service.py   # Task coordination (216 lines)
│   │   └── filter_service.py            # Filtering logic
│   │
│   ├── ports/                      # Domain Interfaces
│   │   ├── layer_lifecycle_port.py      # Interface (181 lines)
│   │   ├── task_management_port.py      # Interface (70 lines)
│   │   └── filter_service_port.py
│   │
│   └── domain/                     # Pure Domain
│       ├── entities/               # Business entities
│       └── value_objects/          # Immutable values
│
├── adapters/                       # Infrastructure Layer
│   ├── backends/                   # Database adapters
│   │   ├── factory.py              # Backend selection
│   │   ├── postgresql_backend.py
│   │   ├── spatialite_backend.py
│   │   └── ogr_backend.py
│   │
│   ├── qgis/                       # QGIS API adapters
│   │   ├── signals/                # Signal management
│   │   ├── layers/                 # Layer operations
│   │   └── tasks/                  # QgsTask wrappers
│   │
│   ├── repositories/               # Data access
│   │   ├── filter_repository.py
│   │   └── config_repository.py
│   │
│   └── task_builder.py             # Task parameter builder (166 lines)
│
├── infrastructure/                 # External Systems
│   ├── persistence/                # Database connections
│   ├── logging/                    # Logging configuration
│   └── resilience/                 # Error handling, retries
│
├── utils/                          # Utilities
│   ├── constants.py
│   └── helpers.py
│
├── filter_mate_app.py              # Orchestration Layer (6,357 lines)
├── filter_mate_dockwidget.py       # UI Root + v3.x integration (13,456 lines)
├── filter_mate.py                  # Plugin entry point
└── metadata.txt                    # QGIS plugin metadata
```

---

## 🎯 Layer Responsibilities

### 1. UI Layer (v3.x Controllers)

**Location**: `ui/controllers/`  
**Pattern**: MVC Controllers + Strangler Fig  
**Size**: ~8,154 lines across 14 files

**Responsibilities**:

- ✅ Tab-specific UI orchestration
- ✅ Widget state management
- ✅ User input validation
- ✅ UI event handling
- ✅ Direct widget manipulation

**Key Components**:

#### BaseController (Abstract)

- Common infrastructure for all controllers
- Signal management via SignalManager
- Service access (FilterService, etc.)
- Lifecycle hooks (setup/teardown, activation/deactivation)

#### Concrete Controllers

| Controller          | Lines  | Purpose             | Status      |
| ------------------- | ------ | ------------------- | ----------- |
| FilteringController | 1,066  | Filtering tab logic | ✅ Complete |
| ExploringController | ~1,200 | Exploring tab logic | ✅ Complete |
| ExportingController | ~800   | Export options      | ✅ Complete |
| BackendController   | ~400   | Backend selection   | ✅ Complete |
| LayerSyncController | ~600   | Layer sync UI       | ✅ Complete |
| ConfigController    | ~500   | Configuration       | ✅ Complete |

#### Integration Infrastructure

- **ControllerIntegration** (1,782 lines): Orchestration, signal wiring, lifecycle
- **ControllerRegistry**: Controller lifecycle management
- **Mixins**: Reusable behaviors (LayerSelectionMixin, TaskMixin)

**Dependencies**:

- ✅ Can use v4.x services (via DI)
- ✅ Can use FilterService
- ✅ Can use SignalManager
- ✅ Can use domain entities
- ❌ Cannot contain business logic
- ❌ Cannot directly access infrastructure

**Example**:

```python
class FilteringController(BaseController):
    """Manages filtering tab UI."""

    def __init__(
        self,
        dockwidget: FilterMateDockWidget,
        filter_service: FilterService,
        layer_lifecycle_service: LayerLifecycleService  # ← DI
    ):
        super().__init__(dockwidget, filter_service)
        self._layer_service = layer_lifecycle_service

    def setup(self) -> None:
        """Initialize controller."""
        super().setup()
        self._connect_signals()
        self._populate_layers()

    def _populate_layers(self):
        """Delegate to service for business logic."""
        layers = self._layer_service.filter_usable_layers()
        self._update_layer_combobox(layers)  # UI update only
```

---

### 2. Orchestration Layer

**Location**: `filter_mate_app.py`, `filter_mate_dockwidget.py`  
**Pattern**: Application Controller + Strangler Fig  
**Size**: ~19,813 lines (being reduced)

**Responsibilities**:

- ✅ Application lifecycle
- ✅ Service instantiation (lazy)
- ✅ Controller coordination
- ✅ Legacy fallback mechanisms
- ✅ Plugin integration with QGIS

**Key Components**:

#### FilterMateApp

- Main application orchestrator
- Service factory (lazy initialization)
- Legacy method delegation
- Backward compatibility fallbacks

#### FilterMateDockWidget

- UI root component
- ControllerIntegration initialization
- Legacy UI methods (being migrated)

**Dependencies**:

- ✅ Can use v4.x services
- ✅ Can use v3.x controllers (via ControllerIntegration)
- ✅ Can use adapters and repositories
- ❌ Cannot contain complex business logic
- ❌ Cannot duplicate service functionality

**Example**:

```python
class FilterMateApp:
    """Application orchestrator."""

    def __init__(self):
        # v4.x services (lazy)
        self._layer_lifecycle_service: Optional[LayerLifecycleService] = None
        self._task_management_service: Optional[TaskManagementService] = None

        # v3.x controllers
        self._controller_integration: Optional[ControllerIntegration] = None

    def _get_layer_lifecycle_service(self) -> LayerLifecycleService:
        """Lazy service initialization."""
        if not self._layer_lifecycle_service:
            self._layer_lifecycle_service = LayerLifecycleService(
                iface=self.iface,
                # ... dependencies
            )
        return self._layer_lifecycle_service

    def manage_task(self, task_params):
        """Delegate to service with fallback."""
        try:
            service = self._get_task_management_service()
            return service.manage_task(task_params)
        except Exception:
            return self._legacy_manage_task(task_params)  # Fallback
```

---

### 3. Business Logic Layer (v4.x Services)

**Location**: `core/services/`  
**Pattern**: Hexagonal (Ports & Adapters)  
**Size**: ~1,121 lines across 3 services

**Responsibilities**:

- ✅ Core business rules
- ✅ Domain logic
- ✅ Workflow orchestration
- ✅ Cross-cutting concerns

**Key Components**:

| Service               | Lines | Port Lines | Purpose           | Status      |
| --------------------- | ----- | ---------- | ----------------- | ----------- |
| LayerLifecycleService | 755   | 181        | Layer management  | ✅ Complete |
| TaskManagementService | 216   | 70         | Task coordination | ✅ Complete |
| FilteringService\*    | -     | -          | Filtering logic   | 🔮 Future   |
| ExportService\*       | -     | -          | Export operations | 🔮 Future   |

(\*future services)

**Dependencies**:

- ✅ Can use domain entities
- ✅ Can use ports (interfaces)
- ✅ Can use other services (via ports)
- ❌ Cannot depend on UI components
- ❌ Cannot depend on QGIS directly (use adapters)
- ❌ Cannot contain UI logic

**Example**:

```python
class LayerLifecycleService:
    """
    Manages layer lifecycle in QGIS project.

    Hexagonal architecture: Core business logic,
    independent of UI and infrastructure.
    """

    def __init__(
        self,
        iface: QgisInterface,
        layer_repository: LayerRepositoryPort,  # ← Port
        on_layers_changed: Optional[Callable] = None
    ):
        self._iface = iface
        self._repository = layer_repository
        self._on_layers_changed = on_layers_changed

    def filter_usable_layers(
        self,
        layers: Optional[List[QgsVectorLayer]] = None
    ) -> List[QgsVectorLayer]:
        """
        Filter layers to only usable ones.

        Business rule: Layer must be valid, vector, and supported provider.
        """
        if layers is None:
            layers = QgsProject.instance().mapLayers().values()

        usable = []
        for layer in layers:
            if not isinstance(layer, QgsVectorLayer):
                continue
            if not layer.isValid():
                continue
            if layer.providerType() not in SUPPORTED_PROVIDERS:
                continue
            usable.append(layer)

        return usable
```

---

### 4. Domain Layer

**Location**: `core/domain/`, `core/ports/`  
**Pattern**: Domain-Driven Design  
**Size**: ~251 lines (ports only currently)

**Responsibilities**:

- ✅ Pure domain entities
- ✅ Business abstractions
- ✅ Port interfaces (protocols)

**Key Components**:

#### Ports (Interfaces)

- `LayerLifecyclePort` (181 lines)
- `TaskManagementPort` (70 lines)
- `FilterServicePort` (future)

#### Domain Entities (future)

- `Filter` entity
- `LayerConfig` value object
- `TaskResult` entity

**Dependencies**:

- ❌ No dependencies (pure domain)

**Example**:

```python
from typing import Protocol, List, Optional
from qgis.core import QgsVectorLayer

class LayerLifecyclePort(Protocol):
    """
    Port for layer lifecycle management.

    Pure interface - no implementation.
    """

    def filter_usable_layers(
        self,
        layers: Optional[List[QgsVectorLayer]] = None
    ) -> List[QgsVectorLayer]:
        """Filter to usable layers only."""
        ...

    def cleanup_postgresql_session_views(
        self,
        layer: QgsVectorLayer
    ) -> bool:
        """Clean PostgreSQL views."""
        ...
```

---

### 5. Infrastructure Layer

**Location**: `adapters/`, `infrastructure/`  
**Pattern**: Adapters implementing ports  
**Size**: Varies (backends, repositories, etc.)

**Responsibilities**:

- ✅ External system integration
- ✅ Database access (PostgreSQL, Spatialite, OGR)
- ✅ QGIS API interaction
- ✅ File system operations
- ✅ Logging, resilience

**Key Components**:

#### Backend Adapters

- `PostgreSQLBackend`: PostgreSQL operations
- `SpatialiteBackend`: Spatialite operations
- `OGRBackend`: OGR/GDAL operations
- `BackendFactory`: Backend selection logic

#### QGIS Adapters

- `SignalManager`: QGIS signal management
- `TaskAdapter`: QgsTask wrappers
- `LayerAdapter`: Layer operations

#### Repositories

- `FilterRepository`: Filter persistence
- `ConfigRepository`: Configuration storage

**Dependencies**:

- ✅ Implements ports
- ✅ Can use external libraries (psycopg2, sqlite3, etc.)
- ❌ Cannot contain business logic
- ❌ Cannot depend on UI

**Example**:

```python
class LayerRepository:
    """
    Repository for layer data access.

    Adapter: Implements port, hides QGIS API details.
    """

    def get_all_vector_layers(self) -> List[QgsVectorLayer]:
        """Get all vector layers from QGIS project."""
        project = QgsProject.instance()
        all_layers = project.mapLayers().values()

        return [
            layer for layer in all_layers
            if isinstance(layer, QgsVectorLayer)
        ]

    def get_layer_by_id(self, layer_id: str) -> Optional[QgsVectorLayer]:
        """Get layer by ID."""
        project = QgsProject.instance()
        return project.mapLayer(layer_id)
```

---

## 🔄 Integration Patterns

### Pattern 1: Service Injection into Controllers

Controllers receive services via constructor (Dependency Injection):

```python
# In ControllerIntegration.setup()
def setup(self) -> None:
    """Setup all controllers with service injection."""

    # Get services from FilterMateApp
    app = self._dockwidget.parent_app
    layer_service = app._get_layer_lifecycle_service()
    task_service = app._get_task_management_service()

    # Inject into controller
    self._filtering_controller = FilteringController(
        dockwidget=self._dockwidget,
        filter_service=self._filter_service,
        layer_lifecycle_service=layer_service,  # ← Injected
        task_management_service=task_service    # ← Injected
    )

    self._filtering_controller.setup()
```

**Benefits**:

- Controllers stay thin
- Business logic centralized in services
- Easy to test (mock services)
- Clear dependencies

### Pattern 2: Event-Driven Communication

Services notify controllers via callbacks/events:

```python
# Service publishes events
class LayerLifecycleService:
    def __init__(self):
        self._on_layers_added: List[Callable] = []

    def add_layers_added_listener(self, callback: Callable):
        """Register listener for layers added."""
        self._on_layers_added.append(callback)

    def handle_layers_added(self, layers: List[QgsVectorLayer]):
        """Handle layers added to project."""
        # Business logic
        usable_layers = self.filter_usable_layers(layers)

        # Notify all listeners
        for callback in self._on_layers_added:
            callback(usable_layers)

# Controller subscribes
class FilteringController(BaseController):
    def setup(self):
        """Setup controller."""
        self._layer_service.add_layers_added_listener(
            self._on_layers_added
        )

    def _on_layers_added(self, layers: List[QgsVectorLayer]):
        """React to layers added event."""
        self._refresh_layer_combobox(layers)
```

**Benefits**:

- Loose coupling
- Services don't depend on UI
- Multiple listeners possible
- Testable independently

### Pattern 3: Lazy Service Initialization

Services created on-demand to avoid circular dependencies:

```python
class FilterMateApp:
    def __init__(self):
        self._layer_lifecycle_service: Optional[LayerLifecycleService] = None

    def _get_layer_lifecycle_service(self) -> LayerLifecycleService:
        """Get or create layer lifecycle service (lazy)."""
        if not self._layer_lifecycle_service:
            self._layer_lifecycle_service = LayerLifecycleService(
                iface=self.iface,
                project=QgsProject.instance(),
                logger=logger,
                # Callbacks from dockwidget
                on_usable_layers_updated=lambda layers: (
                    self.dockwidget.populate_cmbComboBoxLayer(layers)
                    if self.dockwidget else None
                )
            )
            logger.debug("LayerLifecycleService created (lazy init)")

        return self._layer_lifecycle_service
```

**Benefits**:

- Avoid circular dependencies
- Only create when needed
- Centralized service factory
- Easy to mock in tests

### Pattern 4: Strangler Fig Migration

Gradual replacement with fallbacks:

```python
class FilterMateApp:
    def manage_task(self, task_params):
        """
        Manage task with v4.x service or v3.x fallback.

        Strangler Fig: New code tries service first,
        falls back to legacy if unavailable.
        """
        try:
            # v4.x path
            service = self._get_task_management_service()
            return service.manage_task(task_params)
        except Exception as e:
            logger.warning(f"Service unavailable, using fallback: {e}")
            # v3.x fallback
            return self._legacy_manage_task(task_params)
```

**Benefits**:

- Zero breaking changes
- Safe gradual migration
- Easy rollback
- 100% backward compatibility

---

## 📊 Code Metrics

### Layer Distribution

| Layer                    | Files  | Lines       | Percentage |
| ------------------------ | ------ | ----------- | ---------- |
| UI Controllers (v3.x)    | 14     | ~8,154      | 28%        |
| Business Services (v4.x) | 3      | 1,121       | 4%         |
| Domain Ports             | 3      | 251         | 1%         |
| Orchestration            | 2      | 19,813      | 68%        |
| **Total**                | **22** | **~29,339** | **100%**   |

**Note**: Orchestration layer is large (god classes) but being reduced via Strangler Fig.

### Complexity Reduction

| Component                   | Before | After  | Reduction |
| --------------------------- | ------ | ------ | --------- |
| FilterMateApp.manage_task() | High   | Medium | 40%       |
| Layer lifecycle methods     | High   | Low    | 70%       |
| Task management             | Medium | Low    | 60%       |
| UI logic coupling           | High   | Medium | 50%       |

---

## 🧪 Testing Strategy

### Service Tests (Unit - v4.x)

Test services in isolation with mocks:

```python
# tests/unit/test_layer_lifecycle_service.py
import pytest
from core.services.layer_lifecycle_service import LayerLifecycleService

def test_filter_usable_layers_excludes_invalid():
    # Arrange
    service = LayerLifecycleService(...)
    valid_layer = create_mock_layer(is_valid=True)
    invalid_layer = create_mock_layer(is_valid=False)

    # Act
    result = service.filter_usable_layers([valid_layer, invalid_layer])

    # Assert
    assert len(result) == 1
    assert result[0] == valid_layer
```

**Target Coverage**: 80% for all services

### Controller Tests (Integration - v3.x)

Test controllers with mocked services:

```python
# tests/integration/test_filtering_controller.py
import pytest
from unittest.mock import Mock
from ui.controllers.filtering_controller import FilteringController

def test_populate_layers_uses_service():
    # Arrange
    mock_service = Mock(spec=LayerLifecycleService)
    mock_service.filter_usable_layers.return_value = [layer1, layer2]

    controller = FilteringController(
        dockwidget=mock_dockwidget,
        layer_lifecycle_service=mock_service
    )

    # Act
    controller._populate_layers()

    # Assert
    mock_service.filter_usable_layers.assert_called_once()
    assert controller._layer_combobox.count() == 2
```

**Target Coverage**: 70% for all controllers

### E2E Tests (Full Workflow)

Test complete user workflows:

```python
# tests/e2e/test_filter_workflow.py
def test_apply_filter_workflow():
    # Setup real QGIS project
    project = QgsProject.instance()
    layer = add_test_layer(project, feature_count=1000)

    # Execute via plugin
    plugin.dockwidget.filter_tab.select_layer(layer)
    plugin.dockwidget.filter_tab.set_filter_expression("area > 500")
    plugin.dockwidget.filter_tab.apply_filter()

    # Verify
    assert layer.featureCount() < 1000
    assert layer.subsetString() == "area > 500"
```

**Target Coverage**: Critical workflows (filter, explore, export)

---

## 📚 Code Review Guidelines

### New Code Checklist

When adding new functionality:

- [ ] **Layer identification**: Which layer does this belong to?

  - UI logic → Controller
  - Business logic → Service
  - Infrastructure → Adapter

- [ ] **Dependencies**: Are dependencies correct?

  - Controllers can use services (DI)
  - Services cannot use UI
  - Services use ports, not concrete adapters

- [ ] **Tests**: Are appropriate tests added?

  - Services: Unit tests
  - Controllers: Integration tests
  - Workflows: E2E tests

- [ ] **Documentation**: Is it documented?
  - Docstrings complete
  - Architecture docs updated
  - ADRs for significant decisions

### Refactoring Checklist

When refactoring existing code:

- [ ] **Extract to proper layer**:

  - Identify current location
  - Determine correct layer
  - Move with tests

- [ ] **Update dependencies**:

  - Use DI for services
  - Update imports
  - Remove circular dependencies

- [ ] **Maintain backward compatibility**:

  - Add fallbacks if needed
  - Don't break existing APIs
  - Update changelog

- [ ] **Test coverage**:
  - Add tests for extracted code
  - Verify existing tests pass
  - Add integration tests if needed

---

## 🚀 Migration Roadmap

### ✅ Completed

- **Phase 1**: Radical migration (deleted modules/, new structure)
- **Phase 2.1**: v4.x services extraction (3 services, 1,121 lines)
- **Phase 2.2**: v3.x controllers (6 controllers, ~8,154 lines) - discovered existing
- **Phase 3.1**: ADR-001 (architecture reconciliation) - this document

### 🔄 Current Phase: 3 - Consolidation

**Estimated Duration**: 6h  
**Progress**: 50% (ADR + this doc complete)

Remaining tasks:

- [ ] Identify and remove fallbacks
- [ ] Update roadmap
- [ ] Create test strategy guide

### 🔮 Future Phases

**Phase 4: Testing** (10h)

- Unit tests for services (target: 80%)
- Integration tests for controllers (target: 70%)
- E2E tests for workflows

**Phase 5: Continued Extraction** (ongoing)

- More services as needed
- Complete DockWidget delegation
- Remove legacy code

**Phase 6: Optimization** (8h)

- Performance profiling
- Caching strategies
- Database query optimization

---

## 📖 References

### Internal Documents

- [ADR-001: Architecture Reconciliation](./_bmad-output/ADR-001-v3-v4-architecture-reconciliation.md)
- [Migration Progress Report](./_bmad-output/migration-progress-report-v4.0.md)
- [MIG-100: TaskParameterBuilder](../_bmad/bmm/data/stories/MIG-100-task-parameter-builder.md)
- [MIG-101: LayerLifecycleService](../_bmad/bmm/data/stories/MIG-101-layer-lifecycle-service.md)
- [MIG-102: TaskManagementService](../_bmad/bmm/data/stories/MIG-102-task-management-service.md)

### External Resources

- **Hexagonal Architecture**: [Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture/)
- **MVC Pattern**: [Martin Fowler](https://martinfowler.com/eaaDev/uiArchs.html)
- **Strangler Fig**: [Martin Fowler](https://martinfowler.com/bliki/StranglerFigApplication.html)
- **DDD**: [Eric Evans - Domain-Driven Design](https://www.domainlanguage.com/ddd/)

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-10  
**Maintainer**: FilterMate Development Team
