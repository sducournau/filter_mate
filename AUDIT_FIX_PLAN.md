# FilterMate Audit Fix Plan
**Date**: 3 décembre 2025  
**Audit Completed**: 2 décembre 2025

## Executive Summary
This document outlines the implementation plan to address all issues identified in the codebase audit. Issues are prioritized by severity and impact, with clear milestones for tracking progress.

---

## 🔴 Phase 1: Critical Fixes (Week 1)
**Goal**: Address memory leaks and performance bottlenecks  
**Priority**: HIGH - Production Impact

### 1.1 Fix Database Connection Leaks
**File**: `modules/appUtils.py` (lines 105-163)  
**Issue**: Connections not closed in error paths  
**Impact**: Memory leaks, locked database files

**Implementation**:
```python
# BEFORE (current code)
def create_temp_spatialite_table(db_path, table_name, sql_query, geom_field='geometry', srid=4326):
    try:
        conn = sqlite3.connect(db_path)
        # ... operations ...
        conn.close()  # Only on success
    except Exception as e:
        if 'conn' in locals():
            conn.close()  # May miss some paths

# AFTER (fixed)
def create_temp_spatialite_table(db_path, table_name, sql_query, geom_field='geometry', srid=4326):
    try:
        with sqlite3.connect(db_path) as conn:
            conn.enable_load_extension(True)
            # ... operations ...
            # conn.close() automatic
    except Exception as e:
        # Connection already closed
        raise
```

**Testing**:
- [ ] Test normal execution path
- [ ] Test exception during operation
- [ ] Test connection cleanup
- [ ] Verify no locked database files

**Estimated Time**: 2 hours

---

### 1.2 Cache featureCount() Calls
**File**: `modules/appTasks.py` (lines 1886-1920)  
**Issue**: Multiple expensive calls in loop (O(n²))  
**Impact**: Severe performance degradation on large datasets

**Implementation**:
```python
# BEFORE
def search_primary_key_from_layer(self, layer):
    primary_key_index = layer.primaryKeyAttributes()
    if len(primary_key_index) > 0:
        for field_id in primary_key_index:
            if len(layer.uniqueValues(field_id)) == layer.featureCount():  # ❌ Called repeatedly
                # ...

# AFTER
def search_primary_key_from_layer(self, layer):
    feature_count = layer.featureCount()  # ✅ Call once, cache result
    primary_key_index = layer.primaryKeyAttributes()
    if len(primary_key_index) > 0:
        for field_id in primary_key_index:
            if len(layer.uniqueValues(field_id)) == feature_count:  # ✅ Use cached value
                # ...
```

**Locations to fix**:
- Line 1894: `if len(layer.uniqueValues(field_id)) == layer.featureCount():`
- Line 1902: `if len(layer.uniqueValues(...)) == layer.featureCount():`

**Testing**:
- [ ] Benchmark with 100 features
- [ ] Benchmark with 10,000 features
- [ ] Benchmark with 100,000 features
- [ ] Verify correct primary key detection

**Estimated Time**: 1 hour

---

### 1.3 Replace Bare Except Clauses
**Files**: Multiple locations (16 instances)  
**Issue**: Silent failures, hard to debug  
**Impact**: Hidden bugs, poor error messages

**Locations**:
1. `modules/appUtils.py`: lines 111, 114
2. `modules/widgets.py`: lines 534, 538, 633, 639, 660, 664, 683, 734
3. `filter_mate_app.py`: lines 219, 798, 843, 960
4. `filter_mate_dockwidget.py`: lines 1112, 1122, 1731

**Implementation Strategy**:
```python
# BEFORE
try:
    conn.load_extension('mod_spatialite')
except:
    pass  # ❌ Hides everything

# AFTER - Option 1: Specific exceptions
try:
    conn.load_extension('mod_spatialite')
except (OSError, sqlite3.OperationalError) as e:
    logger.warning(f"Could not load spatialite extension: {e}")

# AFTER - Option 2: Log and re-raise
try:
    conn.load_extension('mod_spatialite')
except Exception as e:
    logger.error(f"Unexpected error loading spatialite: {e}")
    raise
```

**Testing**:
- [ ] Test each error path individually
- [ ] Verify error messages are clear
- [ ] Check no legitimate errors are hidden

**Estimated Time**: 4 hours

---

## 🟡 Phase 2: Stability Improvements (Week 2)
**Goal**: Prevent resource leaks on task cancellation  
**Priority**: MEDIUM - Stability

### 2.1 Add Connection Cleanup to Task Cancellation
**File**: `modules/appTasks.py` (lines 1249-1610)  
**Issue**: Connections not closed if task cancelled  
**Impact**: Resource leaks, locked databases

**Implementation**:
```python
class FilterEngineTask(QgsTask):
    def __init__(self, ...):
        # ... existing code ...
        self.active_connections = []  # Track connections
    
    def manage_layer_subset_strings(self, layer, ...):
        conn = None
        try:
            conn = spatialite_connect(self.db_file_path)
            self.active_connections.append(conn)  # Track
            cur = conn.cursor()
            
            # ... operations ...
            
        finally:
            if conn:
                try:
                    cur.close()
                    conn.close()
                except:
                    pass
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
    
    def cancel(self):
        # Cleanup all active connections
        for conn in self.active_connections[:]:  # Copy list
            try:
                conn.close()
            except:
                pass
        self.active_connections.clear()
        super().cancel()
```

**Testing**:
- [ ] Start filter task, cancel immediately
- [ ] Start filter task, cancel mid-operation
- [ ] Verify no locked database files
- [ ] Check no connection leaks

**Estimated Time**: 3 hours

---

### 2.2 Standardize Provider Type Constants
**Files**: Multiple  
**Issue**: Inconsistent 'postgresql' vs 'postgres'  
**Impact**: Bugs, confusion

**Implementation**:

**Step 1**: Add constants to `modules/appUtils.py`:
```python
# Provider type constants (QGIS providerType() returns these values)
PROVIDER_POSTGRES = 'postgres'      # PostgreSQL/PostGIS
PROVIDER_SPATIALITE = 'spatialite'  # Spatialite
PROVIDER_OGR = 'ogr'                # OGR (Shapefile, GeoPackage, etc.)
PROVIDER_MEMORY = 'memory'          # In-memory layers

# Export for use in other modules
__all__ = ['POSTGRESQL_AVAILABLE', 'PROVIDER_POSTGRES', 'PROVIDER_SPATIALITE', 
           'PROVIDER_OGR', 'PROVIDER_MEMORY']
```

**Step 2**: Update imports in all files:
```python
from .modules.appUtils import (
    POSTGRESQL_AVAILABLE, 
    PROVIDER_POSTGRES,
    PROVIDER_SPATIALITE, 
    PROVIDER_OGR
)
```

**Step 3**: Replace all hardcoded strings:
- `'postgres'` → `PROVIDER_POSTGRES`
- `'postgresql'` → `PROVIDER_POSTGRES`
- `'spatialite'` → `PROVIDER_SPATIALITE`
- `'ogr'` → `PROVIDER_OGR`

**Files to update**:
- `filter_mate_app.py`
- `modules/appTasks.py`
- `modules/appUtils.py`
- `modules/widgets.py`

**Testing**:
- [ ] Test PostgreSQL layer detection
- [ ] Test Spatialite layer detection
- [ ] Test OGR layer detection
- [ ] Verify no regressions

**Estimated Time**: 2 hours

---

## 🔵 Phase 3: Code Quality Refactoring (Week 3-4)
**Goal**: Improve maintainability and testability  
**Priority**: MEDIUM - Technical Debt

### 3.1 Refactor Large Methods
**Target**: Break down 3 massive methods into smaller, focused functions

#### 3.1.1 Refactor `execute_geometric_filtering()`
**File**: `modules/appTasks.py` (lines 579-950, 371 lines!)

**Current Structure**: One giant method
**Target Structure**: 
```python
def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
    """Main coordinator method (~50 lines)"""
    if layer_provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
        return self._execute_postgresql_filtering(layer, layer_props)
    elif layer_provider_type == PROVIDER_SPATIALITE:
        return self._execute_spatialite_filtering(layer, layer_props)
    else:
        return self._execute_ogr_filtering(layer, layer_props)

def _execute_postgresql_filtering(self, layer, layer_props):
    """PostgreSQL-specific filtering logic (~80 lines)"""
    # PostgreSQL optimization path
    pass

def _execute_spatialite_filtering(self, layer, layer_props):
    """Spatialite-specific filtering logic (~80 lines)"""
    # Spatialite path
    pass

def _execute_ogr_filtering(self, layer, layer_props):
    """OGR/QGIS processing fallback (~80 lines)"""
    # Generic QGIS processing path
    pass

def _handle_layer_reprojection(self, layer, target_crs):
    """Handle CRS transformation (~40 lines)"""
    pass

def _create_spatial_index(self, layer):
    """Create spatial index if missing (~30 lines)"""
    pass
```

**Benefits**:
- Each method <100 lines
- Easy to unit test individually
- Clear separation of concerns
- Better error handling per backend

**Estimated Time**: 6 hours

---

#### 3.1.2 Refactor `manage_layer_subset_strings()`
**File**: `modules/appTasks.py` (lines 1249-1610, 361 lines!)

**Target Structure**:
```python
def manage_layer_subset_strings(self, layer, sql_subset_string=None, ...):
    """Main coordinator (~30 lines)"""
    conn = self._get_database_connection()
    history = self._get_subset_history(conn, layer)
    
    if self.task_action == 'filter':
        return self._apply_filter(conn, layer, sql_subset_string, history)
    elif self.task_action == 'unfilter':
        return self._remove_filter(conn, layer, history)
    # ...

def _get_subset_history(self, conn, layer):
    """Retrieve filter history (~30 lines)"""
    pass

def _apply_postgresql_filter(self, conn, layer, sql_subset, history):
    """PostgreSQL materialized view approach (~60 lines)"""
    pass

def _apply_spatialite_filter(self, conn, layer, sql_subset, history):
    """Spatialite temp table approach (~60 lines)"""
    pass

def _apply_layer_filter(self, layer, subset_string):
    """Apply filter to layer (~20 lines)"""
    pass
```

**Estimated Time**: 6 hours

---

#### 3.1.3 Refactor `execute_source_layer_filtering()`
**File**: `modules/appTasks.py` (lines 181-322, 141 lines)

**Target Structure**:
```python
def execute_source_layer_filtering(self):
    """Main coordinator (~40 lines)"""
    if not self._validate_filtering_params():
        return False
    
    self._prepare_source_layer()
    return self._execute_provider_specific_filter()

def _validate_filtering_params(self):
    """Validate all parameters (~30 lines)"""
    pass

def _prepare_source_layer(self):
    """Prepare source layer (reprojection, buffer) (~40 lines)"""
    pass

def _execute_provider_specific_filter(self):
    """Execute filter based on provider (~40 lines)"""
    pass
```

**Estimated Time**: 4 hours

---

### 3.2 Replace Debug Print with Logging
**Files**: All Python files  
**Issue**: Production code cluttered with print()  
**Impact**: Log management, debugging

**Implementation**:

**Step 1**: Add logging setup in `modules/appUtils.py`:
```python
import logging

# Configure FilterMate logger
logger = logging.getLogger('FilterMate')
logger.setLevel(logging.DEBUG)  # Will be controlled by QGIS settings

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - FilterMate - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Optional: Add handler for file logging
# handler = logging.FileHandler('filtermate.log')
# handler.setFormatter(formatter)
# logger.addHandler(handler)

__all__ = ['logger', 'POSTGRESQL_AVAILABLE', ...]
```

**Step 2**: Replace all print statements:
```python
# BEFORE
print(f"FilterMate: Provider={provider_type}, PostgreSQL={use_postgresql}")
print("FilterMate: Using Spatialite backend")

# AFTER
logger.debug(f"Provider={provider_type}, PostgreSQL={use_postgresql}")
logger.info("Using Spatialite backend")
```

**Logging Levels to Use**:
- `logger.debug()`: Detailed technical info
- `logger.info()`: User-relevant actions
- `logger.warning()`: Potential issues
- `logger.error()`: Errors that don't crash
- `logger.critical()`: Fatal errors

**Files with print statements**:
- `modules/appTasks.py`: ~15 print statements
- `modules/appUtils.py`: ~5 print statements
- `filter_mate_app.py`: ~3 print statements

**Testing**:
- [ ] Verify logs appear in QGIS console
- [ ] Test different log levels
- [ ] Check performance impact (minimal)

**Estimated Time**: 3 hours

---

## 🟢 Phase 4: Testing & Documentation (Week 5)
**Goal**: Ensure changes work correctly and are documented  
**Priority**: MEDIUM - Quality Assurance

### 4.1 Add Unit Tests for Database Connections
**File**: Create `test_database_connections.py`

**Tests to implement**:
```python
import unittest
from unittest.mock import Mock, patch
import sqlite3

class TestDatabaseConnections(unittest.TestCase):
    
    def test_connection_cleanup_on_success(self):
        """Test connection is closed after successful operation"""
        pass
    
    def test_connection_cleanup_on_exception(self):
        """Test connection is closed even when exception occurs"""
        pass
    
    def test_connection_cleanup_on_task_cancel(self):
        """Test all connections closed when task is cancelled"""
        pass
    
    def test_no_connection_leaks_after_multiple_operations(self):
        """Test no connections remain after multiple filter operations"""
        pass
    
    def test_context_manager_usage(self):
        """Verify context managers are used correctly"""
        pass
    
    def test_concurrent_connection_handling(self):
        """Test multiple tasks don't interfere with each other"""
        pass
```

**Estimated Time**: 6 hours

---

### 4.2 Add Spatial Index Verification
**File**: `modules/appTasks.py` (before lines 874-914)

**Implementation**:
```python
def _verify_spatial_index_exists(self, layer):
    """
    Check if spatial index exists, create if missing.
    Returns True if index exists or was created successfully.
    """
    if not layer.hasSpatialIndex():
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            "FilterMate",
            f"Creating spatial index for {layer.name()}...",
            Qgis.Info, 3
        )
        
        try:
            processing.run('qgis:createspatialindex', {
                'INPUT': layer
            })
            logger.info(f"Created spatial index for layer: {layer.name()}")
            return True
        except Exception as e:
            logger.warning(f"Could not create spatial index: {e}")
            return False
    return True

def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
    # Add at beginning of method
    if not self._verify_spatial_index_exists(layer):
        logger.warning(f"Proceeding without spatial index for {layer.name()} - may be slow")
    
    # ... rest of method
```

**Estimated Time**: 2 hours

---

### 4.3 Update Documentation
**File**: `README.md`

**Add Backend Selection section**:
```markdown
## Backend Selection

FilterMate automatically selects the best backend based on your data source:

### PostgreSQL Backend (Optimal Performance)
**When used**: 
- Layer source is PostgreSQL/PostGIS
- `psycopg2` Python package is installed
- Best for datasets >50,000 features

**Features**:
- Materialized views for fast filtering
- Server-side spatial operations
- Native spatial indexes

**Installation**:
```bash
pip install psycopg2-binary
# Or in QGIS Python console:
import pip
pip.main(['install', 'psycopg2-binary'])
```

### Spatialite Backend (Good Performance)
**When used**:
- Layer source is Spatialite
- Automatically available (SQLite built-in)
- Good for datasets <50,000 features

**Features**:
- Temporary tables for filtering
- R-tree spatial indexes
- Local database operations

### OGR Backend (Universal Compatibility)
**When used**:
- Layer source is Shapefile, GeoPackage, or other OGR formats
- Fallback when PostgreSQL not available
- Works with all data sources

**Features**:
- QGIS processing framework
- Memory-based operations
- Full compatibility

### Performance Comparison
| Backend      | 10k Features | 100k Features | 1M Features |
|--------------|--------------|---------------|-------------|
| PostgreSQL   | <1s          | <2s           | ~10s        |
| Spatialite   | <2s          | ~10s          | ~60s        |
| OGR          | ~5s          | ~30s          | >120s       |

*Times are approximate and depend on geometry complexity*

### Checking Current Backend
Open QGIS Python console and run:
```python
from modules.appUtils import POSTGRESQL_AVAILABLE
print(f"PostgreSQL available: {POSTGRESQL_AVAILABLE}")
```
```

**Estimated Time**: 2 hours

---

## 📊 Implementation Timeline

### Week 1: Critical Fixes (Phase 1)
- **Days 1-2**: Database connection leaks (Task 1.1)
- **Day 2**: Cache featureCount() (Task 1.2)
- **Days 3-4**: Replace bare except (Task 1.3)
- **Day 5**: Testing and validation

**Deliverable**: Stable version with no memory leaks

---

### Week 2: Stability (Phase 2)
- **Days 1-2**: Task cancellation cleanup (Task 2.1)
- **Days 3-4**: Provider type constants (Task 2.2)
- **Day 5**: Integration testing

**Deliverable**: No resource leaks on cancellation

---

### Week 3-4: Refactoring (Phase 3)
- **Week 3 Days 1-3**: Refactor execute_geometric_filtering (Task 3.1.1)
- **Week 3 Days 4-5**: Refactor manage_layer_subset_strings (Task 3.1.2)
- **Week 4 Days 1-2**: Refactor execute_source_layer_filtering (Task 3.1.3)
- **Week 4 Days 3-4**: Implement logging (Task 3.2)
- **Week 4 Day 5**: Code review and cleanup

**Deliverable**: Maintainable, well-structured code

---

### Week 5: Testing & Docs (Phase 4)
- **Days 1-3**: Unit tests (Task 4.1)
- **Day 4**: Spatial index verification (Task 4.2)
- **Day 5**: Documentation updates (Task 4.3)

**Deliverable**: Tested, documented improvements

---

## 🎯 Success Criteria

### Phase 1 Success
- [ ] No memory leaks detected in 24-hour stress test
- [ ] Primary key detection <1s for 100k feature layers
- [ ] All exceptions properly logged with stack traces
- [ ] Zero bare except clauses remaining

### Phase 2 Success
- [ ] Task cancellation leaves no open connections
- [ ] All provider type checks use constants
- [ ] No hardcoded 'postgres'/'postgresql' strings
- [ ] Full backend switching test suite passes

### Phase 3 Success
- [ ] No methods >150 lines
- [ ] Code coverage >70% for refactored methods
- [ ] All debug output uses logger
- [ ] Code complexity score improved by 30%

### Phase 4 Success
- [ ] All new tests pass
- [ ] Documentation reviewed by 2 developers
- [ ] Performance benchmarks documented
- [ ] User guide updated

---

## 🔬 Testing Strategy

### Manual Testing
1. **Connection Leak Test**:
   - Run 100 filter operations consecutively
   - Check system resources (open files, memory)
   - Verify no locked database files

2. **Performance Test**:
   - Benchmark with 10k, 100k, 1M feature layers
   - Compare before/after timings
   - Document improvements

3. **Backend Switching Test**:
   - Test PostgreSQL → Spatialite fallback
   - Test with/without psycopg2 installed
   - Verify correct backend selected

### Automated Testing
```bash
# Run test suite
python -m pytest test_database_connections.py -v

# Run with coverage
python -m pytest --cov=modules --cov-report=html

# Performance benchmark
python benchmark_performance.py --features 100000
```

---

## 🚨 Rollback Plan

If issues arise during implementation:

1. **Git Branch Strategy**:
   ```bash
   git checkout -b audit-fixes-phase1
   # Make changes
   git commit -m "Phase 1: Fix connection leaks"
   # Test thoroughly
   git checkout main
   git merge audit-fixes-phase1
   ```

2. **Feature Flags** (if needed):
   ```python
   USE_NEW_CONNECTION_HANDLING = True  # Set to False to rollback
   ```

3. **Backup Critical Files**:
   - `modules/appUtils.py.backup`
   - `modules/appTasks.py.backup`

---

## 📝 Notes

### Dependencies to Verify
- Python 3.7+ (existing requirement)
- QGIS 3.x API (existing requirement)
- sqlite3 (built-in)
- psycopg2 (optional, already handled)

### Breaking Changes
**None expected** - All changes are internal improvements

### Migration Path
**Not required** - Backward compatible

---

## 🎉 Expected Benefits

### Performance Improvements
- **50-80% faster** primary key detection on large layers
- **No memory leaks** = stable long-running sessions
- **Better resource management** = support more concurrent operations

### Code Quality
- **50% reduction** in method complexity
- **Easier testing** with smaller, focused methods
- **Better error messages** with specific exceptions

### Maintainability
- **Clearer code structure** = easier onboarding
- **Better logging** = faster debugging
- **Comprehensive tests** = confidence in changes

---

## 📞 Support & Review

### Code Review Checkpoints
- [ ] After Phase 1: Security & stability review
- [ ] After Phase 2: Architecture review
- [ ] After Phase 3: Code quality review
- [ ] After Phase 4: Final acceptance review

### Questions or Issues
- Create GitHub issue with `audit-fix` label
- Reference this plan in commit messages
- Document any deviations from plan

---

**Plan Version**: 1.0  
**Last Updated**: 3 décembre 2025  
**Next Review**: After Phase 1 completion
