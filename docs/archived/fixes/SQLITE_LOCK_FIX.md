# Fix: SQLite "Database is Locked" Error

## Problem Description

FilterMate was experiencing `sqlite3.OperationalError: database is locked` errors when multiple concurrent operations tried to write to the Spatialite database. This occurred especially in the `insert_properties_to_spatialite` function during project layer management.

**Error Stack Trace:**
```
sqlite3.OperationalError: database is locked 
Traceback (most recent call last):
  File "modules\appTasks.py", line 5061, in finished
    raise self.exception
  File "modules\appTasks.py", line 4207, in run
    result = self.manage_project_layers()
  File "modules\appTasks.py", line 4252, in manage_project_layers
    result = self.add_project_layer(layer)
  File "modules\appTasks.py", line 4559, in add_project_layer
    self.insert_properties_to_spatialite(layer.id(), layer_props)
  File "modules\appTasks.py", line 4932, in insert_properties_to_spatialite
    cur.execute("""INSERT INTO fm_project_layers_properties
sqlite3.OperationalError: database is locked
```

## Root Causes

1. **Concurrent write operations**: Multiple `QgsTask` instances trying to write to the same SQLite database simultaneously
2. **Insufficient timeout**: 30-second timeout was not enough for busy systems
3. **No retry mechanism**: Failed immediately on lock errors instead of waiting and retrying
4. **No exponential backoff**: Would retry at same rate, potentially causing contention

## Solution Implemented

### 1. Increased Connection Timeout (30s → 60s)

```python
# Before
SQLITE_TIMEOUT = 30.0

# After  
SQLITE_TIMEOUT = 60.0
```

### 2. Added Retry Constants

```python
# Maximum number of retries for database operations when locked
SQLITE_MAX_RETRIES = 5

# Initial delay between retries (will increase exponentially)
SQLITE_RETRY_DELAY = 0.1  # 100ms
```

### 3. Created Generic Retry Function

New utility function `sqlite_execute_with_retry()` that:
- Wraps any database operation
- Automatically retries on "database is locked" errors
- Implements exponential backoff (0.1s → 0.2s → 0.4s → 0.8s → 1.6s)
- Logs retry attempts for debugging
- Fails fast on non-lock errors

```python
def sqlite_execute_with_retry(operation_func, operation_name="database operation", 
                               max_retries=SQLITE_MAX_RETRIES, initial_delay=SQLITE_RETRY_DELAY):
    """
    Execute a SQLite operation with retry logic for handling database locks.
    
    Implements exponential backoff for "database is locked" errors.
    """
    retry_delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return operation_func()
            
        except sqlite3.OperationalError as e:
            last_exception = e
            
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                logger.warning(
                    f"Database locked during {operation_name}. "
                    f"Retry {attempt + 1}/{max_retries} after {retry_delay:.2f}s"
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error(
                    f"Database operation '{operation_name}' failed after {attempt + 1} attempts: {e}"
                )
                raise
                
        except Exception as e:
            logger.error(f"Error during {operation_name}: {e}")
            raise
```

### 4. Refactored `insert_properties_to_spatialite()`

Before: Manual connection management with no retry
After: Wrapped in retry logic

```python
def insert_properties_to_spatialite(self, layer_id, layer_props):
    # Use retry logic wrapper for database operations
    def do_insert():
        conn = self._safe_spatialite_connect()
        try:
            cur = conn.cursor()
            # ... insert operations ...
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                conn.close()
    
    # Execute with automatic retry on database lock
    sqlite_execute_with_retry(
        do_insert, 
        operation_name=f"insert properties for layer {layer_id}"
    )
```

## Benefits

### Reliability
- **5 retry attempts** with exponential backoff increases success rate dramatically
- **Proper error handling** with rollback on failures
- **Clean connection management** ensures connections are always closed

### Performance
- **WAL mode** (already enabled) allows concurrent reads during writes
- **Exponential backoff** reduces database contention
- **Batch inserts** in single transaction (already present, maintained)

### Maintainability  
- **Reusable function** can be applied to other database operations
- **Clear logging** for debugging lock issues
- **Configurable parameters** (max_retries, initial_delay)

## Testing

Created comprehensive test suite in `tests/test_sqlite_lock_handling.py`:

1. **Basic operation success** - Verifies normal operation without locks
2. **Retry on locked database** - Simulates lock and verifies retry works
3. **Permanent lock failure** - Verifies eventual failure after max retries
4. **Non-lock error handling** - Verifies immediate failure on other errors
5. **Exponential backoff** - Verifies delay increases correctly
6. **Concurrent writes** - Simulates multiple threads writing simultaneously

## Usage Example

For any other database write operation that might encounter locks:

```python
def my_database_operation(self, some_param):
    def do_work():
        conn = self._safe_spatialite_connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE table SET ...")
            conn.commit()
            return True
        finally:
            conn.close()
    
    sqlite_execute_with_retry(
        do_work,
        operation_name="update table"
    )
```

## Configuration

Adjust retry behavior if needed:

```python
# In modules/appTasks.py
SQLITE_MAX_RETRIES = 5      # Increase for busy systems
SQLITE_RETRY_DELAY = 0.1    # Adjust initial delay
SQLITE_TIMEOUT = 60.0       # Connection timeout
```

## Monitoring

Watch for these log messages:

**Warning (retry in progress):**
```
Database locked during insert properties for layer <id>. Retry 2/5 after 0.20s
```

**Error (all retries failed):**
```
Database operation 'insert properties for layer <id>' failed after 5 attempts: database is locked
```

## Future Improvements

1. **Apply to other operations**: Use `sqlite_execute_with_retry` for other write operations:
   - `save_filter_to_spatialite()`
   - Table creation operations
   - Index creation operations

2. **Metrics**: Add metrics to track:
   - How often retries occur
   - Average retry count before success
   - Which operations fail most often

3. **Adaptive delays**: Adjust retry parameters based on system load

4. **Connection pooling**: Consider connection pooling for frequently accessed databases (though SQLite doesn't benefit as much as client-server databases)

## Related Files

- **modules/appTasks.py**: Main implementation (lines 65-172, 4988-5026)
- **tests/test_sqlite_lock_handling.py**: Comprehensive test suite
- **docs/SQLITE_LOCK_FIX.md**: This documentation

## References

- SQLite WAL Mode: https://www.sqlite.org/wal.html
- SQLite Locking: https://www.sqlite.org/lockingv3.html
- QGIS Task API: https://qgis.org/pyqgis/master/core/QgsTask.html

## Commit Message

```
fix: Add retry mechanism for SQLite "database is locked" errors

- Increase connection timeout from 30s to 60s
- Implement sqlite_execute_with_retry() with exponential backoff
- Refactor insert_properties_to_spatialite() to use retry logic
- Add comprehensive test suite for lock handling
- Add constants for configurable retry behavior

Fixes concurrent write errors when multiple QgsTasks access
the Spatialite database simultaneously.

Resolves: #[issue-number]
```
