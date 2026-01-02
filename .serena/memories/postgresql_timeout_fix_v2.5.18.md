# PostgreSQL Statement Timeout Fix (v2.5.18)

**Date**: January 2, 2026

## Problem Identified

### Symptoms
- QGIS displays "(Ne répond pas)" / "(Not Responding)" during geometric filtering
- FilterMate log shows repeated "Loading features was canceled" and "Building features list was canceled"
- PostgreSQL backend selected for layer filtering but never completes
- Large source dataset (3859 features from `troncon_de_route`) filtering `batiment` layer

### Root Cause
PostgreSQL complex spatial queries (EXISTS with ST_Intersects on large datasets) can take very long and block indefinitely:
- No `statement_timeout` configured on PostgreSQL connections
- Materialized view creation with complex WHERE clause blocks
- No automatic fallback to OGR when PostgreSQL query times out

## Solutions Implemented

### 1. Connection Pool Statement Timeout (`modules/connection_pool.py`)

**New constant:**
```python
DEFAULT_STATEMENT_TIMEOUT = 120  # 2 minutes
```

**Modified `_create_connection()`:**
```python
# After psycopg2.connect():
try:
    with conn.cursor() as cursor:
        timeout_ms = self.DEFAULT_STATEMENT_TIMEOUT * 1000
        cursor.execute(f"SET statement_timeout = {timeout_ms}")
        conn.commit()
except Exception as timeout_err:
    logger.warning(f"Could not set statement_timeout: {timeout_err}")
```

### 2. Non-Pooled Connection Timeout (`modules/appUtils.py`)

**Modified `get_datasource_connexion_from_layer()`:**
```python
# After psycopg2.connect():
try:
    with connexion.cursor() as cursor:
        cursor.execute("SET statement_timeout = 120000")  # 120s in ms
        connexion.commit()
except Exception as timeout_err:
    logger.warning(f"Could not set statement_timeout: {timeout_err}")
```

### 3. Intelligent Timeout Detection (`modules/backends/postgresql_backend.py`)

**Modified exception handling in `_apply_with_materialized_view()`:**
```python
except Exception as e:
    error_str = str(e).lower()
    
    is_timeout = (
        'timeout' in error_str or 
        'canceling statement' in error_str or
        'querycanceled' in error_str.replace(' ', '')
    )
    
    if is_timeout:
        self.log_warning(f"⏱️ PostgreSQL query TIMEOUT for {layer.name()}")
        # Mark layer for OGR fallback
        self.task_params['forced_backends'][layer.id()] = 'ogr'
        return False  # Triggers OGR fallback
```

### 4. Automatic OGR Fallback for PostgreSQL (`modules/tasks/filter_task.py`)

**Modified fallback condition in `execute_geometric_filtering()`:**
```python
# Before: should_fallback = was_forced or (backend_name == 'spatialite')
# After:
should_fallback = was_forced or (backend_name in ('spatialite', 'postgresql'))
```

**Added PostgreSQL-specific warning:**
```python
elif backend_name == 'postgresql':
    logger.warning(f"⚠️ PostgreSQL backend FAILED for {layer.name()}")
    logger.warning(f"  → Query may have timed out or connection failed")
    logger.warning(f"  → Consider reducing source feature count or using simpler predicates")
```

## Files Modified

| File | Changes |
|------|---------|
| `modules/connection_pool.py` | Added `DEFAULT_STATEMENT_TIMEOUT`, modified `_create_connection()` |
| `modules/appUtils.py` | Added statement_timeout to `get_datasource_connexion_from_layer()` |
| `modules/backends/postgresql_backend.py` | Added timeout detection in exception handler |
| `modules/tasks/filter_task.py` | Extended OGR fallback to PostgreSQL failures |

## Expected Behavior After Fix

1. **Timeout Protection**: PostgreSQL queries automatically cancel after 2 minutes
2. **Graceful Degradation**: When timeout occurs, OGR backend takes over
3. **User Notification**: QGIS message panel shows timeout warning
4. **No UI Freeze**: QGIS remains responsive even during long-running queries

## Configuration

The timeout can be adjusted via:
- Connection pool: `ConnectionPool.DEFAULT_STATEMENT_TIMEOUT`
- Direct connections: Hardcoded 120 seconds in `appUtils.py`

For very complex spatial queries, users can increase PostgreSQL server-side settings:
```sql
SET statement_timeout = '300s';  -- 5 minutes
```

## Testing

To test the fix:
1. Load a project with PostgreSQL layers
2. Select a source layer with many features (1000+)
3. Filter against a large target layer (batiment, etc.)
4. If PostgreSQL times out:
   - Warning appears in QGIS message panel
   - OGR fallback automatically engages
   - Filtering completes (slower but successful)

## Related Issues

- QGIS Bug: "Ne répond pas" during filtering
- Log pattern: "Loading features was canceled" repeated
- Context: IGN topo data with troncon_de_route → batiment intersection
