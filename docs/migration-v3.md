# FilterMate v3.0 - Migration Guide

> **Version**: 3.0.0 | **Date**: January 2026

This guide covers the migration from FilterMate v2.x to v3.0 for both **users** and **developers**.

## 📋 Quick Summary

| Aspect                 | Impact       | Notes                         |
| ---------------------- | ------------ | ----------------------------- |
| **User Configuration** | ✅ Automatic | Config migrates automatically |
| **Plugin API**         | ⚠️ Changed   | New module structure          |
| **Performance**        | 📈 Improved  | Better backend selection      |
| **Compatibility**      | ✅ Same      | QGIS 3.22+ supported          |

---

## 👤 For Users

### What Changes?

**Nothing visible** - The user interface remains the same, and all your configurations (favorites, history, settings) will migrate automatically.

### What Improves?

- **Better Performance**: Smarter backend selection for your data
- **More Stability**: Improved error handling
- **Same Features**: All v2.x features are preserved

### Migration Steps

1. **Backup** (optional but recommended):

   ```
   config/config.json → config/config.backup.json
   ```

2. **Update the plugin** via QGIS Plugin Manager

3. **Done!** - Configuration migrates automatically on first launch

### Troubleshooting

If you encounter issues after upgrade:

1. **Check logs**: `logs/filtermate.log`
2. **Reset configuration**: Delete `config/config.json` (recreated with defaults)
3. **Report issues**: https://github.com/sducournau/filter_mate/issues

---

## 👨‍💻 For Developers

### Import Path Changes

#### Core Domain

```python
# v2.x (old)
from modules.appUtils import FilterResult
from modules.backends.factory import BackendFactory

# v3.0 (new)
from core.domain.filter_result import FilterResult
from adapters.backends.factory import BackendFactory
```

#### Services

```python
# v2.x (old)
from filter_mate_app import FilterMateApp
app = FilterMateApp(iface, dockwidget)
result = app.apply_filter(expression)

# v3.0 (new)
from core.services.filter_service import FilterService
service = FilterService(backend, cache, logger)
result = service.apply_filter(expression, layer_id)
```

#### Backends

```python
# v2.x (old)
from modules.backends.postgresql_backend import PostgreSQLGeometricFilter
backend = PostgreSQLGeometricFilter(layer, task_params)

# v3.0 (new)
from adapters.backends.postgresql_backend import PostgreSQLBackend
backend = PostgreSQLBackend(layer, **config)
```

### New Module Structure

```
v2.x                           v3.0
────────────────────────────   ────────────────────────────
modules/                       core/
  appUtils.py                    domain/
  appTasks.py                      filter_expression.py
  backends/                        filter_result.py
    factory.py                   services/
    postgresql_backend.py          filter_service.py
    spatialite_backend.py        ports/
    ogr_backend.py                 backend_port.py

                               adapters/
                                 backends/
                                   factory.py
                                   postgresql_backend.py
                                 repositories/
                                   config_repository.py

                               infrastructure/
                                 cache/
                                 utils/
```

### Interface Changes

#### BackendPort Interface

All backends now implement the `BackendPort` abstract base class:

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
        """Apply a geometric filter."""
        pass

    @abstractmethod
    def supports_optimization(self, optimization_type: str) -> bool:
        """Check if backend supports optimization."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return backend name."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup backend resources."""
        pass
```

#### Service Pattern

Services now use dependency injection:

```python
# v2.x (old) - Direct instantiation
class FilterMateApp:
    def __init__(self, iface, dockwidget):
        self.backend_factory = BackendFactory()  # Hard dependency
        self.cache = ExpressionCache()           # Hard dependency

# v3.0 (new) - Dependency injection
class FilterService:
    def __init__(
        self,
        backend: BackendPort,
        cache: Optional[CachePort] = None,
        logger: Optional[LoggerPort] = None
    ):
        self._backend = backend
        self._cache = cache
        self._logger = logger
```

### Testing Migration

#### Mock Backends

```python
# v2.x (old) - Complex mocking
with patch('modules.backends.factory.BackendFactory.get_backend') as mock:
    mock.return_value = MagicMock()
    # test...

# v3.0 (new) - Interface-based mocking
class MockBackend(BackendPort):
    def apply_geometric_filter(self, *args, **kwargs):
        return (True, "id > 0", 100)

    def supports_optimization(self, opt_type):
        return False

    def get_name(self):
        return "MockBackend"

    def cleanup(self):
        pass

# Use in tests
service = FilterService(backend=MockBackend())
result = service.apply_filter("field = 1", "layer_id")
```

#### Test Fixtures

New fixtures are available in `tests/integration/conftest.py`:

```python
# Available fixtures
@pytest.fixture
def mock_postgresql_backend():
    """Mock PostgreSQL backend."""
    ...

@pytest.fixture
def mock_spatialite_backend():
    """Mock Spatialite backend."""
    ...

@pytest.fixture
def sample_vector_layer():
    """Create a sample vector layer for testing."""
    ...

@pytest.fixture
def test_expressions():
    """Common test expressions."""
    ...
```

### Configuration Changes

#### Config Format

The configuration format has been enhanced with versioning:

```json
// v2.x config.json
{
  "filter_expression": "field = 1",
  "selected_layer": "my_layer"
}

// v3.0 config.json (migrated automatically)
{
  "version": "3.0",
  "metadata": {
    "created": "2026-01-15T10:30:00",
    "migrated_from": "2.x"
  },
  "filters": {
    "expression": "field = 1",
    "layer": "my_layer"
  },
  "history": {
    "max_size": 50,
    "entries": []
  },
  "favorites": [],
  "backends": {
    "postgresql": {
      "use_materialized_views": true,
      "mv_refresh_threshold": 10000
    },
    "spatialite": {
      "use_rtree_index": true
    }
  }
}
```

### Common Migration Issues

#### 1. Import Errors

```python
# Error: ModuleNotFoundError: No module named 'modules.backends'
# Solution: Update import path

# Old
from modules.backends.factory import BackendFactory

# New
from adapters.backends.factory import BackendFactory
```

#### 2. Initialization Changes

```python
# Error: TypeError: __init__() got unexpected keyword argument
# Solution: Use dependency injection

# Old
backend = PostgreSQLGeometricFilter(layer, task_params)

# New
from adapters.backends.postgresql_backend import PostgreSQLBackend
backend = PostgreSQLBackend(
    layer=layer,
    connection_pool=pool,
    config=config
)
```

#### 3. Testing Migration

```python
# Old test pattern
def test_filter():
    app = FilterMateApp(mock_iface, mock_dockwidget)
    result = app.apply_filter("field = 1")
    assert result

# New test pattern
def test_filter():
    backend = MockBackend()
    service = FilterService(backend=backend)
    result = service.apply_filter("field = 1", "layer_id")
    assert result.success
```

### Deprecation Notices

The following are deprecated and will be removed in v4.0:

| Deprecated                     | Replacement                    | Removal |
| ------------------------------ | ------------------------------ | ------- |
| `modules/appUtils.py`          | `infrastructure/utils/`        | v4.0    |
| `FilterMateApp.apply_filter()` | `FilterService.apply_filter()` | v4.0    |
| Direct backend instantiation   | `BackendFactory.get_backend()` | v4.0    |

### Performance Improvements

v3.0 includes several performance improvements:

| Feature                | v2.x  | v3.0  | Improvement |
| ---------------------- | ----- | ----- | ----------- |
| Backend initialization | 200ms | 80ms  | 60% faster  |
| Simple filter (10k)    | 150ms | 100ms | 33% faster  |
| Memory usage           | ~50MB | ~35MB | 30% less    |

### Getting Help

- **Documentation**: [docs/architecture-v3.md](architecture-v3.md)
- **API Reference**: [docs/api-reference.md](api-reference.md)
- **Issues**: https://github.com/sducournau/filter_mate/issues
- **Discussions**: https://github.com/sducournau/filter_mate/discussions

---

_Last updated: January 2026 | FilterMate v3.0.0_
