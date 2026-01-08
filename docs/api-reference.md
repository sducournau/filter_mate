# FilterMate v3.0 - API Reference

> **Version**: 3.0.0 | **Date**: January 2026

Complete API reference for FilterMate plugin developers and integrators.

---

## 📦 Core Domain

### Domain Objects

#### FilterExpression

Immutable value object representing a filter expression.

```python
from core.domain.filter_expression import FilterExpression

# Constructor
expr = FilterExpression(
    expression: str,            # Filter expression string
    layer_id: str,              # QGIS layer ID
    backend_type: str = None,   # Backend hint (optional)
    is_geometric: bool = False, # Is geometric filter
    predicate: str = None,      # Spatial predicate
    buffer_distance: float = 0.0  # Buffer in meters
)

# Properties (read-only)
expr.expression      # str: The filter expression
expr.layer_id        # str: Target layer ID
expr.backend_type    # Optional[str]: Backend type
expr.is_geometric    # bool: Is geometric filter
expr.predicate       # Optional[str]: Spatial predicate
expr.buffer_distance # float: Buffer distance
```

#### FilterResult

Result of a filtering operation.

```python
from core.domain.filter_result import FilterResult

result = FilterResult(
    success: bool,              # Operation succeeded
    expression: str,            # Expression used
    feature_count: int,         # Features after filter
    execution_time_ms: float,   # Execution time
    backend_used: str,          # Backend name
    feature_ids: List[int] = None,   # Matched feature IDs
    error_message: str = None,  # Error if failed
    optimization_applied: str = None  # Optimization used
)

# Properties
result.success            # bool
result.expression         # str
result.feature_count      # int
result.execution_time_ms  # float
result.backend_used       # str
result.feature_ids        # Optional[List[int]]
result.error_message      # Optional[str]
result.optimization_applied # Optional[str]

# Methods
result.is_empty()         # bool: No features matched
result.to_dict()          # dict: Serialize to dictionary
```

#### LayerInfo

Information about a QGIS vector layer.

```python
from core.domain.layer_info import LayerInfo

info = LayerInfo(
    layer_id: str,              # QGIS layer ID
    name: str,                  # Layer name
    provider_type: str,         # Provider type (postgresql, etc.)
    feature_count: int,         # Total features
    geometry_type: int,         # QgsWkbTypes value
    crs: str = None,            # CRS string (e.g., "EPSG:4326")
    source: str = None          # Layer source
)

# Properties
info.layer_id       # str
info.name           # str
info.provider_type  # str
info.feature_count  # int
info.geometry_type  # int
info.crs            # Optional[str]
info.source         # Optional[str]

# Methods
info.is_postgresql()    # bool: Is PostgreSQL layer
info.is_spatialite()    # bool: Is Spatialite layer
info.is_ogr()           # bool: Is OGR layer
info.is_large()         # bool: > 100k features
```

---

### Ports (Interfaces)

#### BackendPort

Abstract base class for filter backends.

```python
from core.ports.backend_port import BackendPort
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional

class BackendPort(ABC):

    @abstractmethod
    def apply_geometric_filter(
        self,
        predicate: str,
        geometry_wkt: str,
        buffer_distance: float,
        **kwargs
    ) -> Tuple[bool, str, int]:
        """
        Apply geometric filter.

        Args:
            predicate: Spatial predicate (intersects, within, etc.)
            geometry_wkt: Source geometry as WKT
            buffer_distance: Buffer distance in meters
            **kwargs: Backend-specific options

        Returns:
            Tuple of (success, expression, feature_count)
        """
        pass

    @abstractmethod
    def apply_attribute_filter(
        self,
        expression: str,
        **kwargs
    ) -> Tuple[bool, str, int]:
        """
        Apply attribute filter.

        Args:
            expression: Filter expression
            **kwargs: Backend-specific options

        Returns:
            Tuple of (success, expression, feature_count)
        """
        pass

    @abstractmethod
    def get_filtered_feature_ids(self) -> List[int]:
        """Return list of filtered feature IDs."""
        pass

    @abstractmethod
    def supports_optimization(self, optimization_type: str) -> bool:
        """
        Check optimization support.

        Args:
            optimization_type: One of 'materialized_view', 'rtree',
                             'caching', 'connection_pool'
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return backend identifier."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Release backend resources."""
        pass
```

#### ConfigPort

Interface for configuration access.

```python
from core.ports.config_port import ConfigPort
from typing import Any, Optional

class ConfigPort(ABC):

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        pass

    @abstractmethod
    def save(self) -> None:
        """Persist configuration."""
        pass

    @abstractmethod
    def reload(self) -> None:
        """Reload from storage."""
        pass
```

#### CachePort

Interface for caching.

```python
from core.ports.cache_port import CachePort
from typing import Any, Optional

class CachePort(ABC):

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get cached value or None."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = None) -> None:
        """Set cached value with optional TTL."""
        pass

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """Invalidate specific cache entry."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass
```

---

### Services

#### FilterService

Main filtering orchestration service.

```python
from core.services.filter_service import FilterService
from core.domain.filter_result import FilterResult

# Constructor
service = FilterService(
    backend: BackendPort,
    cache: Optional[CachePort] = None,
    logger: Optional[LoggerPort] = None
)

# Methods
result = service.apply_filter(
    expression: str,        # Filter expression
    layer_id: str,          # Target layer ID
    use_optimization: bool = True,  # Use backend optimization
    use_cache: bool = True  # Use expression caching
) -> FilterResult

result = service.apply_geometric_filter(
    predicate: str,         # Spatial predicate
    geometry_wkt: str,      # Source geometry
    layer_id: str,          # Target layer ID
    buffer_distance: float = 0.0,
    buffer_unit: int = 0    # QgsUnitTypes value
) -> FilterResult

service.clear_filter(layer_id: str) -> bool

service.validate_expression(expression: str) -> Tuple[bool, str]
```

#### HistoryService

Filter history management with undo/redo.

```python
from core.services.history_service import HistoryService

# Constructor
history = HistoryService(
    max_size: int = 50,
    repository: Optional[HistoryRepositoryPort] = None
)

# Methods
history.push(state: dict) -> None
    # Add state to history

history.undo() -> Optional[dict]
    # Undo last action, returns previous state

history.redo() -> Optional[dict]
    # Redo undone action, returns next state

history.can_undo() -> bool
history.can_redo() -> bool

history.get_entries(limit: int = 10) -> List[dict]
    # Get recent history entries

history.clear() -> None
    # Clear all history
```

#### ExpressionService

Expression parsing and validation.

```python
from core.services.expression_service import ExpressionService

# Constructor
expr_service = ExpressionService()

# Methods
is_valid, error = expr_service.validate(expression: str) -> Tuple[bool, str]

parsed = expr_service.parse(expression: str) -> ParsedExpression

sql = expr_service.to_sql(
    expression: str,
    backend_type: str  # 'postgresql', 'spatialite', 'ogr'
) -> str

qgis_expr = expr_service.to_qgis(expression: str) -> str
```

---

## 🔌 Adapters

### Backends

#### BackendFactory

Factory for creating appropriate filter backends.

```python
from adapters.backends.factory import BackendFactory

# Constructor
factory = BackendFactory(
    config: Optional[ConfigPort] = None
)

# Methods
backend = factory.get_backend(
    layer: QgsVectorLayer,
    **kwargs
) -> BackendPort

backend_name = factory.detect_backend_type(
    layer: QgsVectorLayer
) -> str

factory.register_backend(
    provider_type: str,
    backend_class: Type[BackendPort]
) -> None
```

#### PostgreSQLBackend

PostgreSQL/PostGIS filter backend.

```python
from adapters.backends.postgresql_backend import PostgreSQLBackend

# Constructor
backend = PostgreSQLBackend(
    layer: QgsVectorLayer,
    connection_pool: Optional[ConnectionPool] = None,
    config: Optional[dict] = None
)

# Methods (inherits BackendPort)
success, expr, count = backend.apply_geometric_filter(
    predicate: str,
    geometry_wkt: str,
    buffer_distance: float,
    use_mv: bool = True  # Use materialized view
)

# PostgreSQL-specific methods
backend.create_materialized_view(
    view_name: str,
    query: str,
    with_index: bool = True
) -> bool

backend.refresh_materialized_view(
    view_name: str,
    concurrently: bool = True
) -> bool

backend.drop_materialized_view(view_name: str) -> bool

backend.get_mv_feature_count(view_name: str) -> int
```

#### SpatialiteBackend

Spatialite/GeoPackage filter backend.

```python
from adapters.backends.spatialite_backend import SpatialiteBackend

# Constructor
backend = SpatialiteBackend(
    layer: QgsVectorLayer,
    config: Optional[dict] = None
)

# Methods (inherits BackendPort)
success, expr, count = backend.apply_geometric_filter(
    predicate: str,
    geometry_wkt: str,
    buffer_distance: float,
    use_rtree: bool = True  # Use R-tree index
)

# Spatialite-specific methods
backend.create_spatial_index(
    table_name: str,
    geometry_column: str = "geometry"
) -> bool

backend.has_spatial_index(
    table_name: str,
    geometry_column: str = "geometry"
) -> bool

backend.create_temp_table(
    table_name: str,
    query: str
) -> bool
```

#### OGRBackend

Universal OGR fallback backend.

```python
from adapters.backends.ogr_backend import OGRBackend

# Constructor
backend = OGRBackend(
    layer: QgsVectorLayer,
    config: Optional[dict] = None
)

# Methods (inherits BackendPort)
# Standard BackendPort interface only
# No OGR-specific optimizations
```

---

### Repositories

#### ConfigRepository

File-based configuration storage.

```python
from adapters.repositories.config_repository import ConfigRepository

# Constructor
repo = ConfigRepository(
    config_path: Path,
    schema_path: Optional[Path] = None
)

# Methods
config = repo.load() -> dict
repo.save(config: dict) -> None
repo.validate(config: dict) -> Tuple[bool, List[str]]
repo.migrate(from_version: str) -> dict
```

#### FavoritesRepository

Favorites persistence.

```python
from adapters.repositories.favorites_repository import FavoritesRepository

# Constructor
repo = FavoritesRepository(storage_path: Path)

# Methods
favorites = repo.get_all() -> List[dict]
favorite = repo.get(name: str) -> Optional[dict]
repo.add(name: str, data: dict) -> bool
repo.update(name: str, data: dict) -> bool
repo.delete(name: str) -> bool
repo.rename(old_name: str, new_name: str) -> bool
```

---

## 🔧 Infrastructure

### CacheManager

Centralized cache management.

```python
from infrastructure.cache.cache_manager import CacheManager

# Constructor
cache = CacheManager(
    ttl_seconds: int = 300,  # Default TTL
    max_size: int = 1000     # Max entries
)

# Methods (implements CachePort)
value = cache.get(key: str) -> Optional[Any]
cache.set(key: str, value: Any, ttl_seconds: int = None) -> None
cache.invalidate(key: str) -> None
cache.clear() -> None

# Additional methods
cache.get_stats() -> dict  # Cache statistics
cache.cleanup_expired() -> int  # Remove expired entries
```

### Provider Utilities

```python
from infrastructure.utils.provider_utils import (
    detect_provider,
    is_postgresql_layer,
    is_spatialite_layer,
    is_ogr_layer,
    POSTGRESQL_AVAILABLE
)

# Functions
provider = detect_provider(layer: QgsVectorLayer) -> str
    # Returns 'postgresql', 'spatialite', 'ogr', or 'memory'

is_pg = is_postgresql_layer(layer: QgsVectorLayer) -> bool
is_sl = is_spatialite_layer(layer: QgsVectorLayer) -> bool
is_ogr = is_ogr_layer(layer: QgsVectorLayer) -> bool

# Constants
POSTGRESQL_AVAILABLE  # bool: True if psycopg2 installed
```

---

## 🖥️ UI Layer

### Controllers

#### FilteringController

Controls filtering tab interactions.

```python
from ui.controllers.filtering_controller import FilteringController

# Constructor
controller = FilteringController(
    filter_service: FilterService,
    view: FilteringView
)

# Methods
controller.on_apply_filter(expression: str) -> None
controller.on_clear_filter() -> None
controller.on_expression_changed(expression: str) -> None
controller.on_layer_changed(layer_id: str) -> None
```

---

## 📊 Type Definitions

### Enumerations

```python
from core.domain.enums import (
    SpatialPredicate,
    OptimizationType,
    BackendType
)

# SpatialPredicate
SpatialPredicate.INTERSECTS
SpatialPredicate.WITHIN
SpatialPredicate.CONTAINS
SpatialPredicate.OVERLAPS
SpatialPredicate.TOUCHES
SpatialPredicate.CROSSES
SpatialPredicate.DISJOINT

# OptimizationType
OptimizationType.MATERIALIZED_VIEW
OptimizationType.RTREE_INDEX
OptimizationType.EXPRESSION_CACHE
OptimizationType.CONNECTION_POOL

# BackendType
BackendType.POSTGRESQL
BackendType.SPATIALITE
BackendType.OGR
BackendType.MEMORY
```

### Type Aliases

```python
from core.domain.types import (
    LayerId,        # str
    Expression,     # str
    FeatureId,      # int
    FeatureIds,     # List[int]
    GeometryWKT,    # str
    FilterCallback  # Callable[[FilterResult], None]
)
```

---

## 🔗 Event System

### Signals

```python
from adapters.qgis.signals.signal_manager import SignalManager

signals = SignalManager()

# Available signals
signals.filter_started.connect(callback)      # FilterExpression
signals.filter_completed.connect(callback)    # FilterResult
signals.filter_failed.connect(callback)       # str (error message)
signals.backend_changed.connect(callback)     # str (backend name)
signals.layer_changed.connect(callback)       # str (layer_id)
signals.history_changed.connect(callback)     # None
signals.favorites_changed.connect(callback)   # None
```

---

## 📚 Examples

### Basic Filtering

```python
from adapters.backends.factory import BackendFactory
from core.services.filter_service import FilterService

# Get layer
layer = QgsProject.instance().mapLayersByName("my_layer")[0]

# Create backend
factory = BackendFactory()
backend = factory.get_backend(layer)

# Create service
service = FilterService(backend)

# Apply filter
result = service.apply_filter("population > 10000", layer.id())

if result.success:
    print(f"Filtered {result.feature_count} features")
else:
    print(f"Error: {result.error_message}")
```

### Geometric Filtering

```python
from core.services.filter_service import FilterService

# Create polygon WKT
polygon_wkt = "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"

# Apply geometric filter
result = service.apply_geometric_filter(
    predicate="intersects",
    geometry_wkt=polygon_wkt,
    layer_id=layer.id(),
    buffer_distance=100.0
)
```

### Custom Backend

```python
from core.ports.backend_port import BackendPort

class CustomBackend(BackendPort):
    def apply_geometric_filter(self, predicate, geometry_wkt, buffer_distance, **kwargs):
        # Custom implementation
        return (True, "custom expression", 42)

    def apply_attribute_filter(self, expression, **kwargs):
        return (True, expression, 100)

    def get_filtered_feature_ids(self):
        return [1, 2, 3]

    def supports_optimization(self, opt_type):
        return False

    def get_name(self):
        return "CustomBackend"

    def cleanup(self):
        pass

# Register with factory
factory.register_backend("custom", CustomBackend)
```

---

_Last updated: January 2026 | FilterMate v3.0.0_
