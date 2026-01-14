# FilterMate v3.0.0 - Architecture Before Migration

> **Document Purpose**: Complete architecture reference of the legacy codebase (`before_migration/`)  
> **Date**: January 14, 2026  
> **For Comparison With**: FilterMate v4.0 Hexagonal Architecture  
> **Total Lines of Code**: ~90,000 LOC

---

## 📋 Executive Summary

This document describes the **monolithic architecture** of FilterMate v3.0.0 before the hexagonal migration (EPIC-1). The codebase was structured around a `modules/` folder containing all business logic, utilities, and backends in a flat or semi-organized hierarchy.

### Key Characteristics

| Aspect | Description |
|--------|-------------|
| **Architecture** | Monolithic with partial separation |
| **Entry Point** | `filter_mate.py` (1,259 lines) |
| **God Classes** | 3 major files > 5,000 lines each |
| **Backend Pattern** | Strategy pattern for providers |
| **Task System** | QgsTask-based async operations |
| **Total Files** | ~85 Python files |
| **Total LOC** | ~90,000 lines |

---

## 📁 Directory Structure

```
before_migration/
├── filter_mate.py                 # Plugin entry point (1,259 LOC)
├── filter_mate_app.py             # Application orchestrator (5,699 LOC) ⚠️ GOD CLASS
├── filter_mate_dockwidget.py      # UI management (12,467 LOC) ⚠️ GOD CLASS
├── filter_mate_dockwidget_base.py # Generated UI code (1,648 LOC)
├── filter_mate_dockwidget_base.ui # Qt Designer file
├── resources.py                   # Qt resources (1,923 LOC)
├── resources.qrc                  # Qt resource definitions
├── metadata.txt                   # QGIS plugin metadata
├── __init__.py
│
├── config/                        # Configuration system
│   ├── config.py                  # Config loading (401 LOC)
│   ├── config.json                # User configuration
│   ├── config.default.json        # Default values
│   ├── config_schema.json         # JSON schema
│   ├── config.v2.example.json     # Example v2 config
│   ├── feedback_config.py
│   └── README_CONFIG.md
│
├── modules/                       # All business logic (75+ files)
│   ├── appUtils.py               # Utility functions (1,838 LOC)
│   ├── appTasks.py               # Legacy (migrated to tasks/)
│   ├── constants.py              # Centralized constants (459 LOC)
│   ├── logging_config.py         # Logging setup (235 LOC)
│   ├── object_safety.py          # Memory safety (1,355 LOC)
│   ├── geometry_safety.py        # Geometry validation (1,030 LOC)
│   │
│   ├── backends/                 # Multi-backend system (17 files)
│   │   ├── base_backend.py       # Abstract interface (281 LOC)
│   │   ├── factory.py            # Backend factory (734 LOC)
│   │   ├── postgresql_backend.py # PostgreSQL/PostGIS (3,329 LOC)
│   │   ├── spatialite_backend.py # Spatialite (4,564 LOC)
│   │   ├── ogr_backend.py        # OGR/GDAL (3,229 LOC)
│   │   ├── memory_backend.py     # QGIS memory layers (639 LOC)
│   │   ├── auto_optimizer.py     # Auto-optimization (1,784 LOC)
│   │   ├── multi_step_optimizer.py # Multi-step filtering (1,010 LOC)
│   │   ├── optimizer_metrics.py  # Performance metrics (930 LOC)
│   │   ├── parallel_processor.py # Parallel processing (636 LOC)
│   │   ├── mv_registry.py        # Materialized view registry
│   │   ├── wkt_cache.py          # WKT geometry cache
│   │   ├── spatial_index_manager.py
│   │   ├── spatialite_cache.py   # Spatialite caching (806 LOC)
│   │   ├── postgresql_buffer_optimizer.py (739 LOC)
│   │   ├── __init__.py           # Module exports (223 LOC)
│   │   └── README.md
│   │
│   ├── tasks/                    # Async task system (14 files)
│   │   ├── filter_task.py        # Main filter task (11,970 LOC) ⚠️ GOD CLASS
│   │   ├── layer_management_task.py # Layer management (1,805 LOC)
│   │   ├── task_utils.py         # Task utilities (564 LOC)
│   │   ├── geometry_cache.py     # Geometry caching
│   │   ├── query_cache.py        # Query result cache (626 LOC)
│   │   ├── progressive_filter.py # Progressive loading (880 LOC)
│   │   ├── multi_step_filter.py  # Multi-step filtering (1,051 LOC)
│   │   ├── parallel_executor.py  # Parallel execution (631 LOC)
│   │   ├── result_streaming.py   # Result streaming
│   │   ├── expression_evaluation_task.py
│   │   ├── combined_query_optimizer.py (1,598 LOC)
│   │   ├── query_complexity_estimator.py
│   │   ├── __init__.py           # Module exports
│   │   └── README.md
│   │
│   ├── qt_json_view/             # JSON tree view widget
│   │   ├── datatypes.py          # Data types (823 LOC)
│   │   ├── model.py
│   │   ├── view.py
│   │   └── __init__.py
│   │
│   ├── widgets.py                # Custom widgets (2,180 LOC)
│   ├── ui_config.py              # UI configuration (1,086 LOC)
│   ├── ui_styles.py              # Theme/styles (628 LOC)
│   ├── ui_elements.py
│   ├── ui_elements_helpers.py
│   ├── ui_widget_utils.py
│   │
│   ├── config_helpers.py         # Config utilities (979 LOC)
│   ├── config_migration.py       # Config migration (962 LOC)
│   ├── config_editor_widget.py
│   ├── config_metadata.py
│   ├── config_metadata_handler.py
│   │
│   ├── filter_history.py         # Undo/redo (598 LOC)
│   ├── filter_favorites.py       # Favorites system (853 LOC)
│   ├── flag_manager.py           # State flags
│   ├── state_manager.py          # State management
│   │
│   ├── circuit_breaker.py        # Connection protection
│   ├── connection_pool.py        # Connection pooling (1,010 LOC)
│   ├── prepared_statements.py    # SQL prepared statements (673 LOC)
│   ├── postgresql_optimizer.py   # PG optimization (773 LOC)
│   ├── psycopg2_availability.py  # PostgreSQL detection
│   │
│   ├── crs_utils.py              # CRS utilities (964 LOC)
│   ├── type_utils.py             # Type conversion
│   ├── icon_utils.py             # Icon management
│   ├── signal_utils.py           # Signal helpers
│   ├── feedback_utils.py         # User feedback
│   ├── exploring_cache.py        # Feature exploring cache
│   ├── customExceptions.py       # Custom exceptions
│   │
│   ├── backend_optimization_widget.py (2,068 LOC)
│   ├── optimization_dialogs.py
│   │
│   ├── __init__.py
│   └── README.md
│
├── i18n/                         # Translations (21 languages)
├── icons/                        # Icon resources
└── resources/                    # Additional resources
```

---

## 🏗️ Core Architecture

### 1. Entry Point (`filter_mate.py`) - 1,259 LOC

The QGIS plugin entry point handling:
- Plugin initialization and GUI setup
- Translation loading (21 languages)
- Configuration migration
- Auto-activation signals
- Menu and toolbar creation

```python
class FilterMate:
    """QGIS Plugin Implementation."""
    
    def __init__(self, iface):
        # Save QGIS interface reference
        # Initialize locale and translation
        # Setup plugin directory
        
    def initGui(self):
        # Create menu entries and toolbar icons
        # Connect auto-activation signals
        # Auto-migrate configuration
        
    def run(self):
        # Open FilterMate dockwidget
        # Initialize FilterMateApp if needed
```

### 2. Application Orchestrator (`filter_mate_app.py`) - 5,699 LOC ⚠️

**GOD CLASS** containing:
- Layer management and validation
- Task orchestration (filter, export)
- Signal handling and state management
- Project lifecycle management
- Stability constants and timeouts

Key responsibilities:
- `_filter_usable_layers()`: Layer validation
- `_on_layers_added()`: Signal handler with debouncing
- `manage_task()`: Task lifecycle management
- Signal connections for project changes

```python
class FilterMateApp:
    PROJECT_LAYERS = {}  # Layer registry
    
    STABILITY_CONSTANTS = {
        'MAX_ADD_LAYERS_QUEUE': 50,
        'FLAG_TIMEOUT_MS': 30000,
        'LAYER_RETRY_DELAY_MS': 500,
        'UI_REFRESH_DELAY_MS': 300,
        # ... 10+ more constants
    }
```

### 3. Dockwidget (`filter_mate_dockwidget.py`) - 12,467 LOC ⚠️

**GOD CLASS** containing:
- Complete UI implementation
- Event handlers for all UI elements
- Layer/field selection logic
- Expression building
- Export configuration
- Theme management
- Value relation handling

---

## 🔌 Backend Architecture

### Backend Interface (`base_backend.py`)

```python
class GeometricFilterBackend(ABC):
    """Abstract base class for geometric filtering backends."""
    
    @abstractmethod
    def build_expression(self, layer_props, predicates, source_geom, 
                         buffer_value, source_filter, **kwargs) -> str:
        """Build a filter expression for this backend."""
        
    @abstractmethod
    def apply_filter(self, layer, expression, old_subset, 
                     combine_operator) -> bool:
        """Apply the filter expression to the layer."""
        
    @abstractmethod
    def supports_layer(self, layer) -> bool:
        """Check if this backend supports the given layer."""
```

### Backend Implementations

| Backend | File | LOC | Use Case |
|---------|------|-----|----------|
| **PostgreSQL** | `postgresql_backend.py` | 3,329 | PostGIS databases |
| **Spatialite** | `spatialite_backend.py` | 4,564 | SQLite/GeoPackage |
| **OGR** | `ogr_backend.py` | 3,229 | Shapefiles, universal fallback |
| **Memory** | `memory_backend.py` | 639 | QGIS memory layers |

### Backend Factory (`factory.py`) - 734 LOC

Selects appropriate backend based on:
1. Layer provider type
2. Feature count (small dataset optimization)
3. PostgreSQL availability
4. Configuration settings

```python
def should_use_memory_optimization(layer, layer_provider_type) -> bool:
    """
    For small PostgreSQL datasets, use memory backend
    to avoid network overhead.
    """
```

---

## ⚡ Task System

### Main Filter Task (`filter_task.py`) - 11,970 LOC ⚠️

**GOD CLASS** implementing `QgsTask`:

```python
class FilterEngineTask(QgsTask):
    """
    Core filtering task for FilterMate.
    
    Supports:
    - Source layer filtering (attribute and geometry)
    - Multi-layer geometric filtering with spatial predicates
    - Export operations
    - Filter history management (undo/redo/reset)
    
    Backends:
    - PostgreSQL/PostGIS (optimal for large datasets)
    - Spatialite (good for medium datasets)
    - OGR (fallback)
    """
    
    # PyQt signals for task communication
    taskCompleted = pyqtSignal(dict)
    taskFailed = pyqtSignal(str, str)
    progressChanged = pyqtSignal(float, str)
```

### Layer Management Task (`layer_management_task.py`) - 1,805 LOC

Handles:
- Adding/removing layers from filter list
- Project load/reload operations
- Layer validation and cleanup

---

## 📊 Module Inventory by Size

### Top 15 Largest Files

| Rank | File | Lines | Category |
|------|------|-------|----------|
| 1 | `filter_mate_dockwidget.py` | 12,467 | UI |
| 2 | `modules/tasks/filter_task.py` | 11,970 | Tasks |
| 3 | `filter_mate_app.py` | 5,699 | Core |
| 4 | `modules/backends/spatialite_backend.py` | 4,564 | Backend |
| 5 | `modules/backends/postgresql_backend.py` | 3,329 | Backend |
| 6 | `modules/backends/ogr_backend.py` | 3,229 | Backend |
| 7 | `modules/widgets.py` | 2,180 | UI |
| 8 | `modules/backend_optimization_widget.py` | 2,068 | UI |
| 9 | `resources.py` | 1,923 | Resources |
| 10 | `modules/appUtils.py` | 1,838 | Utilities |
| 11 | `modules/tasks/layer_management_task.py` | 1,805 | Tasks |
| 12 | `modules/backends/auto_optimizer.py` | 1,784 | Backend |
| 13 | `filter_mate_dockwidget_base.py` | 1,648 | UI (generated) |
| 14 | `modules/tasks/combined_query_optimizer.py` | 1,598 | Tasks |
| 15 | `modules/object_safety.py` | 1,355 | Utilities |

### Category Breakdown

| Category | Files | Total LOC | % of Total |
|----------|-------|-----------|------------|
| **Core/Entry** | 4 | ~21,000 | 23% |
| **Backends** | 17 | ~18,000 | 20% |
| **Tasks** | 14 | ~20,000 | 22% |
| **UI Components** | 8 | ~10,000 | 11% |
| **Utilities** | 15 | ~12,000 | 13% |
| **Configuration** | 8 | ~4,000 | 5% |
| **Other** | ~20 | ~5,000 | 6% |
| **TOTAL** | ~85 | ~90,000 | 100% |

---

## 🔄 Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  filter_mate.py │────▶│  FilterMateApp   │────▶│  FilterEngineTask │
│  (Entry Point)  │     │  (Orchestrator)  │     │  (Async Task)     │
└─────────────────┘     └──────────────────┘     └───────────────────┘
                               │                          │
                               ▼                          ▼
                    ┌──────────────────┐       ┌───────────────────┐
                    │   DockWidget     │       │  BackendFactory   │
                    │   (UI - 12k LOC) │       └───────────────────┘
                    └──────────────────┘                │
                                              ┌─────────┼─────────┐
                                              ▼         ▼         ▼
                                        PostgreSQL  Spatialite   OGR
                                        Backend     Backend      Backend
```

---

## 🔑 Key Patterns Used

### 1. Strategy Pattern (Backends)
```python
# Backend selection based on provider type
backend = BackendFactory.get_backend(layer, task_params)
expression = backend.build_expression(...)
backend.apply_filter(layer, expression)
```

### 2. Factory Pattern
```python
class BackendFactory:
    @staticmethod
    def get_backend(layer, task_params) -> GeometricFilterBackend:
        provider_type = detect_layer_provider_type(layer)
        
        if provider_type == 'postgresql' and POSTGRESQL_AVAILABLE:
            return PostgreSQLGeometricFilter(task_params)
        elif provider_type == 'spatialite':
            return SpatialiteGeometricFilter(task_params)
        else:
            return OGRGeometricFilter(task_params)
```

### 3. Observer Pattern (Signals)
```python
# Task completion signals
taskCompleted = pyqtSignal(dict)
taskFailed = pyqtSignal(str, str)
progressChanged = pyqtSignal(float, str)
```

### 4. Template Method (Tasks)
```python
class FilterEngineTask(QgsTask):
    def run(self):
        # Template: Setup → Execute → Cleanup
        self._setup_task()
        result = self._execute_filter()
        self._cleanup()
        return result
```

---

## ⚠️ Architecture Issues (Pre-Migration)

### 1. God Classes
Three files contain **30,000+ LOC combined**:
- `filter_mate_dockwidget.py`: 12,467 LOC
- `filter_task.py`: 11,970 LOC
- `filter_mate_app.py`: 5,699 LOC

### 2. Tight Coupling
- UI directly imports backend logic
- Task classes have UI dependencies
- Configuration scattered across modules

### 3. Monolithic Structure
- All code in `modules/` without clear boundaries
- No explicit ports/adapters separation
- Difficult to test in isolation

### 4. Mixed Responsibilities
- `filter_mate_app.py` handles:
  - Layer management
  - Task orchestration
  - Signal management
  - State management
  - Project lifecycle

---

## 📦 Dependencies Map

### Internal Dependencies
```
filter_mate.py
├── filter_mate_app.py
│   ├── filter_mate_dockwidget.py
│   ├── modules/tasks/
│   │   ├── filter_task.py
│   │   │   ├── modules/backends/*
│   │   │   ├── modules/appUtils.py
│   │   │   └── modules/geometry_safety.py
│   │   └── layer_management_task.py
│   └── modules/appUtils.py
└── config/config.py
```

### External Dependencies
- **QGIS Core**: QgsTask, QgsVectorLayer, QgsGeometry, QgsExpression
- **PyQt5**: Signals, Widgets, Core
- **GDAL/OGR**: ogr module for file-based layers
- **psycopg2** (optional): PostgreSQL/PostGIS support
- **sqlite3**: Spatialite support

---

## 📝 Configuration System

### Config Files
| File | Purpose |
|------|---------|
| `config.json` | User configuration (editable) |
| `config.default.json` | Default values |
| `config_schema.json` | JSON schema for validation |

### Config Structure (v2.0)
```json
{
  "_CONFIG_VERSION": "2.0",
  "APP": {
    "AUTO_ACTIVATE": { "value": false },
    "DOCKWIDGET": {
      "FEEDBACK_LEVEL": { "value": "normal" },
      "LANGUAGE": { "value": "auto" },
      "THEME": { "value": "auto" }
    },
    "OPTIONS": {
      "SMALL_DATASET_OPTIMIZATION": {
        "enabled": { "value": true },
        "threshold": { "value": 5000 }
      }
    }
  },
  "POSTGRESQL": {
    "FILTER": {
      "MATERIALIZED_VIEW": { "value": true }
    }
  }
}
```

---

## 🔄 Comparison Quick Reference

| Aspect | v3.0 (Before) | v4.0 (After) |
|--------|---------------|--------------|
| **Architecture** | Monolithic | Hexagonal |
| **God Classes** | 3 (30k LOC) | 0 |
| **Max File Size** | 12,467 LOC | ~2,500 LOC |
| **Coupling** | Tight | Loose (ports/adapters) |
| **Testability** | Low | High |
| **modules/ folder** | Main code location | Shims only |
| **Total LOC** | ~90,000 | ~75,000 (-17%) |

---

## 📚 Related Documents

- [CODEBASE-AUDIT-20260114.md](CODEBASE-AUDIT-20260114.md) - Post-migration audit
- [REGRESSION-AUDIT-20260114.md](REGRESSION-AUDIT-20260114.md) - Regression analysis
- [PHASE-E13-STEP6-SUMMARY.md](PHASE-E13-STEP6-SUMMARY.md) - Migration completion

---

*Document generated by BMad Master for FilterMate migration documentation.*
