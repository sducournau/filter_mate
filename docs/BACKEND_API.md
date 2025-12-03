# Backend API Documentation

## Overview

FilterMate uses a plugin architecture for handling different data sources (PostgreSQL/PostGIS, Spatialite, and OGR). This document describes the backend system architecture, interfaces, and usage patterns.

## Architecture

### Backend System Design

```
┌─────────────────────────────────────────────────┐
│          FilterMate Application                  │
│                                                   │
│  ┌───────────────────────────────────────────┐  │
│  │      Backend Factory                       │  │
│  │  (Selects appropriate backend)             │  │
│  └────────────────┬──────────────────────────┘  │
│                   │                              │
│         ┌─────────┴─────────┐                   │
│         │                   │                   │
│    ┌────▼────┐         ┌────▼────┐             │
│    │PostgreSQL│         │Spatialite│            │
│    │ Backend  │         │ Backend  │            │
│    └────┬────┘         └────┬────┘             │
│         │                   │                   │
│         └─────────┬─────────┘                   │
│                   │                              │
│         ┌─────────▼─────────┐                   │
│         │   OGR Backend     │                   │
│         │   (Fallback)      │                   │
│         └───────────────────┘                   │
└─────────────────────────────────────────────────┘
```

### Backend Interface

All backends implement the abstract `GeometricFilterBackend` class defined in `modules/backends/base_backend.py`.

## Base Backend Class

### `GeometricFilterBackend`

Abstract base class that defines the interface all backends must implement.

**Location**: `modules/backends/base_backend.py`

#### Constructor

```python
def __init__(self, task_params: Dict):
    """
    Initialize the backend with task parameters.
    
    Args:
        task_params: Dictionary containing task configuration and layer information
    """
```

#### Abstract Methods

All backends **must** implement these methods:

##### `build_expression()`

```python
@abstractmethod
def build_expression(
    self,
    layer_props: Dict,
    predicates: Dict,
    source_geom: Optional[str] = None,
    buffer_value: Optional[float] = None,
    buffer_expression: Optional[str] = None
) -> str:
    """
    Build a filter expression for this backend.
    
    Args:
        layer_props: Layer properties dictionary containing:
            - layer_name: Table/layer name
            - layer_schema: Schema name (PostgreSQL only)
            - geometry_field: Name of geometry column
            - primary_key_name: Primary key field name
            - layer_provider_type: 'postgresql', 'spatialite', or 'ogr'
        
        predicates: Dictionary of spatial predicates to apply:
            - Key: Predicate name (e.g., 'intersects', 'contains')
            - Value: SQL function name for this backend
        
        source_geom: Source geometry for spatial filtering (optional)
            - For PostgreSQL: PostGIS geometry expression
            - For Spatialite: Spatialite geometry expression
            - For OGR: QGIS geometry object
        
        buffer_value: Buffer distance value (optional)
            - Static numeric value in layer units
        
        buffer_expression: Expression for dynamic buffer (optional)
            - Can reference layer fields
            - Takes precedence over buffer_value
    
    Returns:
        Filter expression as a string suitable for this backend
        - PostgreSQL: PostGIS SQL WHERE clause
        - Spatialite: Spatialite SQL WHERE clause
        - OGR: QGIS expression string
    
    Raises:
        NotImplementedError: Must be implemented by subclasses
    
    Example:
        >>> backend.build_expression(
        ...     layer_props={'layer_name': 'roads', 'geometry_field': 'geom'},
        ...     predicates={'intersects': 'ST_Intersects'},
        ...     source_geom='ST_GeomFromText(...)',
        ...     buffer_value=100.0
        ... )
        'ST_Intersects(ST_Buffer("roads"."geom", 100.0), ST_GeomFromText(...))'
    """
```

##### `apply_filter()`

```python
@abstractmethod
def apply_filter(
    self,
    layer: QgsVectorLayer,
    expression: str,
    old_subset: Optional[str] = None,
    combine_operator: Optional[str] = None
) -> bool:
    """
    Apply the filter expression to the layer.
    
    Args:
        layer: QGIS vector layer to filter
            - Must be a valid QgsVectorLayer instance
            - Must have a data provider
        
        expression: Filter expression to apply
            - Built by build_expression()
            - Backend-specific format
        
        old_subset: Existing subset string (optional)
            - Previous filter expression on the layer
            - Used when combining filters
        
        combine_operator: Operator to combine with existing filter (AND/OR)
            - 'AND': Both old and new filters must match
            - 'OR': Either old or new filter must match
            - None: Replace existing filter
    
    Returns:
        True if filter was applied successfully, False otherwise
    
    Raises:
        NotImplementedError: Must be implemented by subclasses
    
    Notes:
        - Should handle provider-specific quirks
        - Should log errors appropriately
        - May modify layer's subset string or use provider filters
    
    Example:
        >>> success = backend.apply_filter(
        ...     layer=roads_layer,
        ...     expression='ST_Intersects(...)',
        ...     old_subset='road_type = "highway"',
        ...     combine_operator='AND'
        ... )
    """
```

##### `supports_layer()`

```python
@abstractmethod
def supports_layer(self, layer: QgsVectorLayer) -> bool:
    """
    Check if this backend supports the given layer.
    
    Args:
        layer: QGIS vector layer to check
    
    Returns:
        True if this backend can handle the layer, False otherwise
    
    Notes:
        - PostgreSQL backend: Returns True for 'postgres' provider
        - Spatialite backend: Returns True for 'spatialite' provider
        - OGR backend: Returns True for all other providers (fallback)
    
    Example:
        >>> if backend.supports_layer(my_layer):
        ...     backend.apply_filter(my_layer, expression)
    """
```

##### `get_backend_name()`

```python
@abstractmethod
def get_backend_name(self) -> str:
    """
    Get the human-readable name of this backend.
    
    Returns:
        Backend name string
    
    Example:
        >>> print(backend.get_backend_name())
        'PostgreSQL/PostGIS'
    """
```

#### Helper Methods

The base class provides these utility methods:

##### `prepare_geometry_expression()`

```python
def prepare_geometry_expression(
    self,
    geom_field: str,
    buffer_value: Optional[float] = None,
    buffer_expression: Optional[str] = None,
    simplify_tolerance: Optional[float] = None
) -> str:
    """
    Prepare geometry expression with optional buffer and simplification.
    
    Args:
        geom_field: Name of geometry field
        buffer_value: Buffer distance (optional)
        buffer_expression: Expression for dynamic buffer (optional)
        simplify_tolerance: Simplification tolerance (optional)
    
    Returns:
        Geometry expression string
    
    Notes:
        - Default implementation returns field name as-is
        - Backends should override with provider-specific functions
    """
```

##### `validate_layer_properties()`

```python
def validate_layer_properties(self, layer_props: Dict) -> tuple:
    """
    Validate that layer properties contain required keys.
    
    Args:
        layer_props: Layer properties dictionary
    
    Returns:
        tuple: (is_valid, missing_keys, error_message)
    
    Example:
        >>> is_valid, missing, msg = backend.validate_layer_properties(props)
        >>> if not is_valid:
        ...     print(f"Invalid: {msg}")
    """
```

##### `build_buffer_expression()`

```python
def build_buffer_expression(
    self,
    geom_expr: str,
    buffer_value: Optional[float] = None,
    buffer_expression: Optional[str] = None
) -> str:
    """
    Build buffer expression for geometry.
    
    Args:
        geom_expr: Geometry expression
        buffer_value: Static buffer distance
        buffer_expression: Dynamic buffer expression
    
    Returns:
        Buffered geometry expression
    
    Notes:
        - Base implementation uses generic Buffer() function
        - Backends override with ST_Buffer (PostGIS), Buffer (Spatialite)
    """
```

##### `combine_expressions()`

```python
def combine_expressions(
    self,
    expressions: list,
    operator: str = "OR"
) -> str:
    """
    Combine multiple expressions with logical operator.
    
    Args:
        expressions: List of expression strings
        operator: Logical operator (AND, OR)
    
    Returns:
        Combined expression string
    
    Example:
        >>> combined = backend.combine_expressions(
        ...     ['expr1', 'expr2', 'expr3'],
        ...     operator='OR'
        ... )
        '(expr1) OR (expr2) OR (expr3)'
    """
```

##### Logging Methods

```python
def log_info(self, message: str)
def log_warning(self, message: str)
def log_error(self, message: str)
def log_debug(self, message: str)
```

## Backend Implementations

### PostgreSQL Backend

**Class**: `PostgreSQLGeometricFilter`  
**Location**: `modules/backends/postgresql_backend.py`  
**Provider**: `postgres`

#### Features

- Server-side spatial operations using PostGIS
- Materialized views for performance
- R-tree spatial indexes
- Optimized for large datasets (> 100k features)

#### Dependencies

- Requires `psycopg2` module
- Checks `POSTGRESQL_AVAILABLE` flag before use

#### Spatial Functions

Uses PostGIS spatial functions:
- `ST_Intersects`, `ST_Contains`, `ST_Within`, `ST_Crosses`, `ST_Overlaps`, `ST_Touches`
- `ST_Buffer` for buffering
- `ST_MakeValid` for geometry validation
- `ST_GeomFromText` for geometry creation

#### Example Usage

```python
from modules.backends.postgresql_backend import PostgreSQLGeometricFilter

# Check if PostgreSQL is available
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE:
    backend = PostgreSQLGeometricFilter(task_params)
    
    expression = backend.build_expression(
        layer_props={
            'layer_name': 'buildings',
            'layer_schema': 'public',
            'geometry_field': 'geom',
            'primary_key_name': 'gid'
        },
        predicates={'intersects': 'ST_Intersects'},
        source_geom="ST_Buffer(ST_GeomFromText('POINT(0 0)', 4326), 0.01)",
        buffer_value=10.0
    )
    
    success = backend.apply_filter(buildings_layer, expression)
```

### Spatialite Backend

**Class**: `SpatialiteGeometricFilter`  
**Location**: `modules/backends/spatialite_backend.py`  
**Provider**: `spatialite`

#### Features

- Local SQLite database with Spatialite extension
- Temporary tables instead of materialized views
- R-tree spatial indexes
- Good for moderate datasets (< 100k features)

#### Dependencies

- Python `sqlite3` module (built-in)
- Spatialite extension (mod_spatialite)

#### Spatial Functions

Uses Spatialite spatial functions (90% compatible with PostGIS):
- `ST_Intersects`, `ST_Contains`, `ST_Within`, etc.
- `Buffer` for buffering (note: not ST_Buffer)
- `ST_IsValid` for geometry validation

#### Example Usage

```python
from modules.backends.spatialite_backend import SpatialiteGeometricFilter

backend = SpatialiteGeometricFilter(task_params)

expression = backend.build_expression(
    layer_props={
        'layer_name': 'roads',
        'geometry_field': 'geometry'
    },
    predicates={'intersects': 'ST_Intersects'},
    source_geom=source_wkt,
    buffer_expression='"speed_limit" / 10'  # Dynamic buffer based on field
)

success = backend.apply_filter(roads_layer, expression)
```

### OGR Backend

**Class**: `OGRGeometricFilter`  
**Location**: `modules/backends/ogr_backend.py`  
**Provider**: Various (ShapeFile, GeoPackage, GeoJSON, etc.)

#### Features

- Fallback backend for unsupported providers
- Uses QGIS processing algorithms
- Memory-based operations
- Universal compatibility

#### Performance Notes

- Slower than database backends for large datasets
- Loads features into memory
- No server-side indexing
- Best for small to medium datasets (< 10k features)

#### Example Usage

```python
from modules.backends.ogr_backend import OGRGeometricFilter

backend = OGRGeometricFilter(task_params)

expression = backend.build_expression(
    layer_props={'layer_name': 'points'},
    predicates={'intersects': '$geometry'},  # QGIS expression format
    source_geom=qgs_geometry,  # QgsGeometry object
    buffer_value=50.0
)

success = backend.apply_filter(points_layer, expression)
```

## Backend Factory

### `BackendFactory`

**Location**: `modules/backends/factory.py`

Factory class for creating appropriate backend instances.

#### Methods

##### `get_backend()`

```python
@staticmethod
def get_backend(layer: QgsVectorLayer, task_params: Dict) -> GeometricFilterBackend:
    """
    Get the appropriate backend for a layer.
    
    Selection logic:
        1. PostgreSQL backend if layer provider is 'postgres' and psycopg2 available
        2. Spatialite backend if layer provider is 'spatialite'
        3. OGR backend for all other providers (fallback)
    
    Args:
        layer: QGIS vector layer
        task_params: Task parameters dictionary
    
    Returns:
        Appropriate backend instance
    
    Example:
        >>> backend = BackendFactory.get_backend(my_layer, params)
        >>> expression = backend.build_expression(...)
    """
```

## Usage Patterns

### Basic Filtering

```python
from modules.backends.factory import BackendFactory

# Get appropriate backend for layer
backend = BackendFactory.get_backend(layer, task_params)

# Build filter expression
expression = backend.build_expression(
    layer_props=layer_properties,
    predicates=spatial_predicates,
    source_geom=source_geometry
)

# Apply filter
if backend.apply_filter(layer, expression):
    print(f"Filter applied using {backend.get_backend_name()}")
else:
    print("Filter application failed")
```

### Filtering with Buffer

```python
backend = BackendFactory.get_backend(layer, task_params)

# Static buffer
expression = backend.build_expression(
    layer_props=props,
    predicates={'intersects': 'ST_Intersects'},
    source_geom=source,
    buffer_value=100.0  # 100 units
)

# Dynamic buffer using field
expression = backend.build_expression(
    layer_props=props,
    predicates={'intersects': 'ST_Intersects'},
    source_geom=source,
    buffer_expression='"buffer_distance"'  # Use field value
)
```

### Combining Filters

```python
# Apply initial filter
backend.apply_filter(layer, expression1)

# Combine with new filter using AND
backend.apply_filter(
    layer,
    expression2,
    old_subset=expression1,
    combine_operator='AND'
)
```

### Error Handling

```python
from modules.backends.factory import BackendFactory

try:
    backend = BackendFactory.get_backend(layer, task_params)
    
    # Validate layer properties first
    is_valid, missing, error = backend.validate_layer_properties(props)
    if not is_valid:
        backend.log_error(f"Invalid layer properties: {error}")
        return False
    
    # Build and apply expression
    expression = backend.build_expression(props, predicates)
    if not expression:
        backend.log_warning("Empty expression generated")
        return False
    
    success = backend.apply_filter(layer, expression)
    if success:
        backend.log_info("Filter applied successfully")
    else:
        backend.log_error("Failed to apply filter")
    
    return success
    
except Exception as e:
    logger.error(f"Backend error: {e}")
    return False
```

## Performance Guidelines

### PostgreSQL Backend

- **Best for**: > 100k features
- **Optimization**: Uses materialized views, server-side indexing
- **Tip**: Ensure spatial indexes exist on geometry columns

### Spatialite Backend

- **Best for**: 10k - 100k features
- **Optimization**: Creates temporary tables with R-tree indexes
- **Tip**: Keep database file on fast local storage

### OGR Backend

- **Best for**: < 10k features
- **Optimization**: Minimal - memory-based operations
- **Tip**: Warn users about performance with large datasets

## Testing

### Unit Tests

Test files located in `tests/test_backends.py`:

```python
def test_postgresql_backend():
    """Test PostgreSQL backend functionality."""
    # Test build_expression
    # Test apply_filter
    # Test buffer operations
    
def test_spatialite_backend():
    """Test Spatialite backend functionality."""
    
def test_ogr_backend():
    """Test OGR fallback backend."""
    
def test_backend_factory():
    """Test backend selection logic."""
```

### Manual Testing

1. Test with PostgreSQL layer (if psycopg2 available)
2. Test with Spatialite/GeoPackage layer
3. Test with ShapeFile (OGR fallback)
4. Test buffer operations
5. Test filter combination
6. Test with large datasets (performance)

## Extending the Backend System

### Adding a New Backend

1. Create new file in `modules/backends/`
2. Inherit from `GeometricFilterBackend`
3. Implement all abstract methods
4. Add backend to factory selection logic
5. Write unit tests
6. Update documentation

Example skeleton:

```python
from .base_backend import GeometricFilterBackend

class MyCustomBackend(GeometricFilterBackend):
    """Backend for MyCustom data source."""
    
    def supports_layer(self, layer):
        return layer.providerType() == 'mycustom'
    
    def build_expression(self, layer_props, predicates, **kwargs):
        # Implement expression building logic
        pass
    
    def apply_filter(self, layer, expression, **kwargs):
        # Implement filter application logic
        pass
    
    def get_backend_name(self):
        return "MyCustom Backend"
```

## Troubleshooting

### Common Issues

**PostgreSQL backend not being used**
- Check if `psycopg2` is installed
- Verify `POSTGRESQL_AVAILABLE` flag in `modules/appUtils.py`
- Check layer provider type is 'postgres'

**Slow performance with OGR backend**
- Dataset may be too large for memory operations
- Consider converting to PostgreSQL or Spatialite
- Check for spatial indexes

**Filter not applying**
- Check logs for error messages
- Validate layer properties structure
- Verify spatial predicate syntax for backend

### Debug Logging

Enable debug logging to see backend operations:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Backends will log:
- Backend selection
- Expression building
- Filter application steps
- Errors and warnings

## API Reference Summary

| Class | Method | Purpose |
|-------|--------|---------|
| `GeometricFilterBackend` | `build_expression()` | Build filter expression |
| | `apply_filter()` | Apply filter to layer |
| | `supports_layer()` | Check compatibility |
| | `validate_layer_properties()` | Validate input |
| `PostgreSQLGeometricFilter` | (inherits above) | PostGIS implementation |
| `SpatialiteGeometricFilter` | (inherits above) | Spatialite implementation |
| `OGRGeometricFilter` | (inherits above) | OGR fallback |
| `BackendFactory` | `get_backend()` | Create backend instance |

## See Also

- [Architecture Overview](architecture.md)
- [Developer Onboarding Guide](DEVELOPER_ONBOARDING.md)
- [FilterMate Coding Guidelines](../.github/copilot-instructions.md)
