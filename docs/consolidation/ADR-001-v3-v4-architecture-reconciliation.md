# ADR-001: v3.x MVC Controllers and v4.x Hexagonal Architecture Reconciliation

**Status**: Accepted  
**Date**: 2026-01-10  
**Deciders**: FilterMate Development Team  
**Technical Story**: Consolidation Phase after Phase 2.1 & 2.2 completion

---

## Context and Problem Statement

FilterMate has undergone two parallel architectural migrations:

1. **v3.x MVC Controllers** (STORY-2.4, 2.5, Phase 6)

   - 6 UI controllers (~8,154 lines)
   - ControllerIntegration orchestration layer
   - Strangler Fig pattern for gradual DockWidget migration
   - Focus: UI separation and tab-based orchestration

2. **v4.x Hexagonal Architecture** (MIG-100, 101, 102)
   - 3 hexagonal services (~1,121 lines)
   - Ports & Adapters pattern
   - Focus: Business logic extraction from FilterMateApp

**Problem**: These architectures were implemented independently and now coexist. We need to:

- Define their relationship and boundaries
- Ensure they complement rather than conflict
- Document unified architecture
- Provide clear migration path forward

## Decision Drivers

- **Backward Compatibility**: 100% maintained (critical for existing users)
- **Code Duplication**: Minimize redundancy between v3.x and v4.x
- **Developer Clarity**: Clear guidelines on where new code belongs
- **Migration Continuity**: Don't discard substantial working code
- **Testing Strategy**: Both architectures must be testable

## Considered Options

### Option 1: v4.x Replaces v3.x (Full Hexagonal)

**Description**: Deprecate v3.x controllers, migrate all to v4.x hexagonal services

**Pros**:

- Single unified architecture
- Pure hexagonal pattern
- Cleaner long-term design

**Cons**:

- Discard ~8,154 lines of working code
- Requires ~20h of re-implementation
- Risk of introducing bugs
- No immediate business value

**Decision**: ❌ Rejected

### Option 2: v3.x Replaces v4.x (Pure MVC)

**Description**: Remove v4.x services, use only v3.x MVC controllers

**Pros**:

- Single unified architecture
- UI-focused design
- Controllers already comprehensive

**Cons**:

- Lose hexagonal architecture benefits
- Business logic coupled to UI layer
- Harder to test business logic independently
- Discard recent quality work (MIG-100/101/102)

**Decision**: ❌ Rejected

### Option 3: Layered Hybrid Architecture (SELECTED)

**Description**: Maintain both architectures with clear layer boundaries

```
┌─────────────────────────────────────────┐
│     UI Layer (v3.x Controllers)         │
│  - FilteringController                  │
│  - ExploringController                  │
│  - ExportingController                  │
│  - etc.                                 │
├─────────────────────────────────────────┤
│   Orchestration Layer (FilterMateApp)   │
│  - Coordinates services & controllers   │
│  - Legacy delegation & fallbacks        │
├─────────────────────────────────────────┤
│  Business Logic (v4.x Services)         │
│  - LayerLifecycleService                │
│  - TaskManagementService                │
│  - Future services                      │
├─────────────────────────────────────────┤
│    Domain Layer (Entities & Ports)      │
│  - Core business entities               │
│  - Port interfaces                      │
├─────────────────────────────────────────┤
│  Infrastructure (Adapters & Repos)      │
│  - Database adapters                    │
│  - QGIS adapters                        │
│  - External systems                     │
└─────────────────────────────────────────┘
```

**Pros**:

- Preserve all working code (~9,275 lines)
- Clear separation of concerns
- Each layer has defined responsibility
- Both architectures testable
- Gradual evolution possible
- Controllers can use services (dependency injection)

**Cons**:

- More complex architecture
- Requires clear documentation
- Two patterns to understand

**Decision**: ✅ **ACCEPTED**

---

## Decision Outcome

### Chosen Option: Layered Hybrid Architecture

**Rationale**:

- Maximizes value of both migrations
- Clear separation: UI (controllers) vs Business Logic (services)
- Controllers can consume services via dependency injection
- Each layer independently testable
- Natural evolution path as codebase grows

---

## Architecture Principles

### Layer Responsibilities

#### 1. UI Layer (v3.x Controllers)

**Location**: `ui/controllers/`

**Responsibilities**:

- Tab-specific UI orchestration
- Widget state management
- User input validation
- UI event handling
- Direct widget manipulation

**Pattern**: MVC Controllers with BaseController

**Examples**:

- `FilteringController`: Manages filtering tab widgets
- `ExploringController`: Manages exploring tab
- `ExportingController`: Manages export options

**Can depend on**:

- v4.x services (via dependency injection)
- FilterService
- SignalManager
- Domain entities

**Cannot**:

- Contain business logic (delegate to services)
- Directly access infrastructure (use services)

#### 2. Orchestration Layer (FilterMateApp)

**Location**: `filter_mate_app.py`, `filter_mate_dockwidget.py`

**Responsibilities**:

- Application lifecycle
- Service instantiation (lazy loading)
- Controller coordination
- Legacy fallback mechanisms
- Plugin integration

**Pattern**: Application Controller + Strangler Fig

**Can depend on**:

- v4.x services
- v3.x controllers (via ControllerIntegration)
- Adapters and repositories

**Cannot**:

- Contain complex business logic
- Duplicate service functionality

#### 3. Business Logic Layer (v4.x Services)

**Location**: `core/services/`

**Responsibilities**:

- Core business rules
- Domain logic
- Workflow orchestration
- Cross-cutting concerns

**Pattern**: Hexagonal (Ports & Adapters)

**Examples**:

- `LayerLifecycleService`: Layer management logic
- `TaskManagementService`: Async task coordination
- Future: `FilteringService`, `ExportService`

**Can depend on**:

- Domain entities
- Ports (interfaces)
- Other services (via ports)

**Cannot**:

- Depend on UI components
- Depend on QGIS directly (use adapters)
- Contain UI logic

#### 4. Domain Layer

**Location**: `core/domain/`, `core/ports/`

**Responsibilities**:

- Pure domain entities
- Business abstractions
- Port interfaces

**Pattern**: Domain-Driven Design

**Can depend on**:

- Nothing (pure domain)

**Cannot**:

- Depend on infrastructure
- Depend on UI
- Depend on frameworks

#### 5. Infrastructure Layer

**Location**: `adapters/`, `infrastructure/`

**Responsibilities**:

- External system integration
- Database access
- QGIS API interaction
- File system operations

**Pattern**: Adapters implementing ports

**Can depend on**:

- Ports (implements interfaces)
- External libraries

**Cannot**:

- Contain business logic
- Depend on UI

---

## Integration Guidelines

### Controllers Using Services

Controllers MAY use services for business logic:

```python
# FilteringController using LayerLifecycleService
class FilteringController(BaseController):
    def __init__(
        self,
        dockwidget,
        filter_service,
        layer_lifecycle_service  # ← Injected v4.x service
    ):
        super().__init__(dockwidget, filter_service)
        self._layer_service = layer_lifecycle_service

    def _populate_layers(self):
        # Delegate to service instead of direct implementation
        layers = self._layer_service.filter_usable_layers()
        self._update_layer_combobox(layers)
```

**Benefits**:

- Controllers stay thin
- Business logic centralized
- Services reusable
- Better testability

### Services Independent of Controllers

Services MUST NOT depend on controllers:

```python
# ❌ BAD - Service depends on controller
class LayerLifecycleService:
    def __init__(self, filtering_controller):
        self._controller = filtering_controller  # Wrong!

# ✅ GOOD - Service uses callbacks or events
class LayerLifecycleService:
    def __init__(self):
        self._on_layers_changed: Optional[Callable] = None

    def set_layers_changed_callback(self, callback: Callable):
        self._on_layers_changed = callback
```

### FilterMateApp as Mediator

FilterMateApp coordinates both:

```python
class FilterMateApp:
    def __init__(self):
        # v4.x services
        self._layer_lifecycle_service = None
        self._task_management_service = None

        # v3.x controllers (via integration)
        self._controller_integration = None

    def _get_layer_lifecycle_service(self):
        if not self._layer_lifecycle_service:
            self._layer_lifecycle_service = LayerLifecycleService(...)
        return self._layer_lifecycle_service

    def setup_controllers(self):
        # Inject services into controllers
        layer_service = self._get_layer_lifecycle_service()
        self._controller_integration.inject_service(layer_service)
```

---

## Migration Path

### Current State (v4.0)

- ✅ 3 hexagonal services implemented
- ✅ 6 MVC controllers implemented
- ✅ ControllerIntegration bridge functional
- ⏳ Services/controllers not yet integrated

### Phase 3: Consolidation (Current - 6h)

1. **Document unified architecture** ✅ (this ADR)
2. **Create integration patterns**
   - Service injection into controllers
   - Event-based communication
3. **Remove redundant fallbacks**
   - Clean up temporary delegation code
   - Simplify FilterMateApp orchestration
4. **Update all documentation**
   - Architecture diagrams
   - Developer guides

### Phase 4: Testing (10h)

1. **Service tests**: Unit tests for v4.x services
2. **Controller tests**: Integration tests for v3.x controllers
3. **E2E tests**: Full workflow validation
4. **Performance**: Benchmarks for both layers

### Phase 5: Continued Extraction

New extractions follow layer boundaries:

- **UI logic** → v3.x controllers (extend existing)
- **Business logic** → v4.x services (new services)
- **Infrastructure** → Adapters

---

## Architectural Patterns

### Dependency Injection

Services injected into controllers:

```python
# In ControllerIntegration.setup()
filtering_controller = FilteringController(
    dockwidget=self._dockwidget,
    filter_service=self._filter_service,
    layer_lifecycle_service=app._get_layer_lifecycle_service(),  # ← Inject
    task_management_service=app._get_task_management_service()   # ← Inject
)
```

### Event-Driven Communication

Services notify via callbacks:

```python
# Service publishes events
class LayerLifecycleService:
    def __init__(self):
        self._on_layers_added: List[Callable] = []

    def add_layers_added_listener(self, callback: Callable):
        self._on_layers_added.append(callback)

    def handle_layers_added(self, layers):
        # Business logic
        ...
        # Notify listeners
        for callback in self._on_layers_added:
            callback(layers)

# Controller subscribes
class FilteringController(BaseController):
    def setup(self):
        self._layer_service.add_layers_added_listener(
            self._on_layers_added
        )

    def _on_layers_added(self, layers):
        # Update UI
        self._refresh_layer_list()
```

### Strangler Fig Continuation

Both architectures use Strangler Fig:

- **v3.x controllers**: Gradually replace DockWidget methods
- **v4.x services**: Gradually replace FilterMateApp methods
- **Eventual goal**: Thin orchestration layer, logic in services/controllers

---

## Testing Strategy

### Service Tests (Unit)

Test services in isolation:

```python
def test_layer_lifecycle_service_filter_usable_layers():
    # Arrange
    service = LayerLifecycleService()
    mock_layers = [create_mock_layer(), ...]

    # Act
    usable = service.filter_usable_layers(mock_layers)

    # Assert
    assert len(usable) == expected_count
    assert all(layer.is_valid() for layer in usable)
```

### Controller Tests (Integration)

Test controllers with mocked services:

```python
def test_filtering_controller_populate_layers():
    # Arrange
    mock_service = Mock(LayerLifecycleService)
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

### E2E Tests

Test complete workflows:

```python
def test_filter_workflow_end_to_end():
    # Setup real QGIS project
    project = QgsProject.instance()
    layer = add_test_layer(project)

    # Execute filter via UI
    plugin.dockwidget.filter_tab.set_layer(layer)
    plugin.dockwidget.filter_tab.apply_filter("area > 1000")

    # Verify result
    assert layer.featureCount() == expected_filtered_count
```

---

## Consequences

### Positive

- ✅ Preserves ~9,275 lines of working code
- ✅ Clear separation of concerns
- ✅ Both architectures independently testable
- ✅ Flexible evolution path
- ✅ Controllers can leverage services
- ✅ No code duplication (when properly integrated)
- ✅ Backward compatibility maintained

### Negative

- ⚠️ More complex architecture (2 patterns)
- ⚠️ Requires thorough documentation
- ⚠️ Developers must understand both layers
- ⚠️ Integration points need careful management

### Neutral

- ℹ️ Architecture will evolve over time
- ℹ️ Some controllers may become thin wrappers (acceptable)
- ℹ️ Some services may have no UI (acceptable for CLI/API)

---

## Compliance Validation

### Code Review Checklist

When reviewing new code, verify:

- [ ] UI logic in controllers only
- [ ] Business logic in services only
- [ ] No business logic in orchestration layer
- [ ] Services don't depend on UI
- [ ] Controllers use services via DI
- [ ] Proper layer boundaries respected
- [ ] Tests cover appropriate layer

### Refactoring Guidelines

When refactoring existing code:

1. **Identify layer**: Where does this logic belong?
2. **Extract to appropriate layer**:
   - UI manipulation → Controller
   - Business rule → Service
   - External system → Adapter
3. **Use dependency injection**: Controllers get services via constructor
4. **Add tests**: Unit for services, integration for controllers
5. **Update documentation**: Keep architecture docs current

---

## References

- **Hexagonal Architecture**: Alistair Cockburn
- **Ports & Adapters**: Same as Hexagonal
- **MVC Pattern**: Trygve Reenskaug
- **Strangler Fig Pattern**: Martin Fowler
- **Domain-Driven Design**: Eric Evans

---

## Related Documents

- [migration-progress-report-v4.0.md](./migration-progress-report-v4.0.md)
- [architecture-v3.md](../docs/architecture-v3.md)
- [MIG-100](../_bmad/bmm/data/stories/MIG-100-task-parameter-builder.md)
- [MIG-101](../_bmad/bmm/data/stories/MIG-101-layer-lifecycle-service.md)
- [MIG-102](../_bmad/bmm/data/stories/MIG-102-task-management-service.md)

---

**Revision History**:

- 2026-01-10: Initial version (ADR-001)
