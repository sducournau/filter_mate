# Backend Selection

FilterMate automatically detects and uses the appropriate backend based on your layer's data source. This document explains how backend selection works and how you can influence it.

## Automatic Detection

When you select a layer in FilterMate, the plugin automatically identifies the backend:

- **PostgreSQL/PostGIS**: Layers connected to a PostgreSQL database
- **Spatialite**: Layers using Spatialite databases (.sqlite, .db)
- **OGR**: File-based formats (Shapefile, GeoPackage, CSV, etc.)

## Backend Priority

If multiple backends could handle your data, FilterMate uses this priority:

1. **PostgreSQL** (best performance for large datasets)
2. **Spatialite** (good performance, local databases)
3. **OGR** (compatibility fallback)

## Layer Provider Types

FilterMate uses QGIS's layer provider information to determine the appropriate backend:

```python
if layer.providerType() == 'postgres':
    # Use PostgreSQL backend
elif layer.providerType() == 'spatialite':
    # Use Spatialite backend
elif layer.providerType() == 'ogr':
    # Use OGR backend
```

## PostgreSQL Availability

FilterMate requires the `psycopg2` Python package for PostgreSQL support. If it's not installed:

- PostgreSQL layers will fall back to QGIS's native filtering
- You'll see a warning message
- Install with: `pip install psycopg2-binary`

Check availability:
```python
from modules.appUtils import POSTGRESQL_AVAILABLE
if POSTGRESQL_AVAILABLE:
    print("PostgreSQL backend available")
```

## Backend Capabilities

Different backends have different capabilities:

| Feature | PostgreSQL | Spatialite | OGR |
|---------|-----------|-----------|-----|
| **Filtering** | ✓ | ✓ | ✓ |
| **Spatial Operations** | ✓ | ✓ | Limited |
| **Buffer Operations** | ✓ | ✓ | ✓ |
| **Export** | ✓ | ✓ | ✓ |
| **Materialized Views** | ✓ | Temp Tables | Memory |
| **Spatial Indexes** | ✓ | ✓ | ✗ |
| **Large Datasets (&>;100k)** | Excellent | Good | Limited |

## Performance Considerations

### When to Use Each Backend

**PostgreSQL**:
- Datasets > 100,000 features
- Complex spatial operations
- Shared/remote data access
- Production environments

**Spatialite**:
- Local projects
- Datasets < 100,000 features
- Offline work
- Desktop analysis

**OGR**:
- File-based formats
- Simple filtering
- Smaller datasets (< 10,000 features)
- Compatibility with various formats

## Configuration

### Automatic Behavior

No configuration needed! FilterMate automatically:
1. Detects your layer's provider type
2. Checks backend availability
3. Selects the optimal backend
4. Falls back gracefully if needed

### Advanced Options

For developers, you can access backend information:

```python
from modules.appUtils import get_datasource_connexion_from_layer

connexion, source_uri = get_datasource_connexion_from_layer(layer)
if connexion:
    # Direct database connection available
    print(f"Using backend: {layer.providerType()}")
```

## Troubleshooting

### PostgreSQL Not Available

If you see warnings about PostgreSQL:

1. **Check Installation**:
   ```bash
   python -c "import psycopg2; print('OK')"
   ```

2. **Install if Missing**:
   ```bash
   pip install psycopg2-binary
   ```

3. **Restart QGIS** after installation

### Spatialite Issues

If Spatialite operations fail:

1. Verify the database file is accessible
2. Check file permissions
3. Ensure `mod_spatialite` is available

### OGR Limitations

OGR backend has limitations:
- Slower for large datasets
- Limited spatial functions
- No server-side processing

**Solution**: Consider converting to Spatialite or PostgreSQL for better performance.

## See Also

- [Backend Overview](./overview.md) - General information about backends
- [PostgreSQL Backend](./postgresql.md) - PostgreSQL-specific features
- [Spatialite Backend](./spatialite.md) - Spatialite-specific features
- [OGR Backend](./ogr.md) - OGR capabilities and limitations
- [Performance Comparison](./performance-comparison.md) - Benchmark results
