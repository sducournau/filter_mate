# Test Fixes Summary - January 13, 2026

## Overview

This document summarizes the test infrastructure fixes made during the v4.0.1-alpha migration.

## Problem Statement

After the hexagonal architecture migration, tests were failing due to:
1. `TypeError: isinstance() arg 2 must be a type or tuple of types`
2. Import errors with relative imports beyond top-level package
3. Mock objects not properly simulating QGIS classes

## Root Cause Analysis

### Issue 1: isinstance() Check Failure

**Cause**: Using `sys.modules['qgis.core'] = Mock()` makes `QgsVectorLayer` a generic Mock object instead of a class. When code calls `isinstance(layer, QgsVectorLayer)`, Python raises TypeError because Mock is not a type.

**Solution**: Create proper mock classes that can be used in isinstance() checks:

```python
class MockQgsVectorLayer:
    """Mock QgsVectorLayer that properly works with isinstance() checks."""
    def __init__(self, layer_id="test_layer", name="test_layer", ...):
        self._id = layer_id
        self._name = name
        ...
    
    def id(self): return self._id
    def name(self): return self._name
    # ... other methods
```

Then register the class:
```python
mock_qgis_core = Mock()
mock_qgis_core.QgsVectorLayer = MockQgsVectorLayer  # Class, not instance!
sys.modules['qgis.core'] = mock_qgis_core
```

### Issue 2: Relative Import Beyond Package

**Cause**: Files in `adapters/` using `from ..core.import X` work fine in QGIS but fail in pytest because pytest treats the workspace differently.

**Solution**: 
- For tests: Use `importlib.util` to load specific modules directly
- For production: Keep relative imports (they work in QGIS)

### Issue 3: Mock Method Behavior

**Cause**: Tests expected `mock_layer.isValid.return_value = False` but our MockQgsVectorLayer uses real methods.

**Solution**: Add setter methods to allow dynamic behavior modification:
```python
class MockQgsVectorLayer:
    def set_valid(self, value): self._is_valid = value
    def set_name(self, value): self._name = value
    # ...
```

## Files Modified

### tests/unit/test_layer_service.py

1. Added `MockQgsVectorLayer` class with:
   - All standard QGIS layer methods
   - `set_*` methods for dynamic behavior
   - Proper deleted layer simulation

2. Added `MockQgsFields` and `MockQgsField` for field testing

3. Added `MockQgsWkbTypes` for geometry type display

4. Updated fixtures to use proper mock classes

5. Updated tests to use `set_*` methods instead of `.return_value`

**Result**: 47 tests pass

### tests/unit/test_filter_executor_port.py

1. Created comprehensive tests for new hexagonal components:
   - `FilterStatus` enum tests
   - `FilterExecutionResult` dataclass tests
   - `FilterExecutorPort` abstract interface tests
   - `BackendRegistry` DI container tests
   - Integration tests
   - Edge case tests
   - Performance tests

2. Used `importlib.util` to load BackendRegistry directly, bypassing problematic imports

**Result**: 31 tests pass

## Test Execution

### Individual Execution (Recommended)

```bash
# LayerService tests
python -m pytest tests/unit/test_layer_service.py -v --override-ini="addopts="

# FilterExecutorPort tests
python -m pytest tests/unit/test_filter_executor_port.py -v --override-ini="addopts="
```

### Known Issues

**Batch Execution Conflict**: Running both test files together causes import cache pollution. The first file's mock setup affects the second file's module resolution.

**Workaround**: Run test files separately or use pytest-forked plugin.

## Mock Classes Reference

### MockQgsVectorLayer

```python
MockQgsVectorLayer(
    layer_id="test_layer_123",
    name="test_layer",
    provider_type="postgres",
    is_valid=True,
    deleted=False
)

# Change behavior dynamically:
mock_layer.set_valid(False)
mock_layer.set_name("new_name")
mock_layer.set_subset("id > 10")
mock_layer.set_primary_key_attributes([1])
```

### MockQgsFields / MockQgsField

```python
fields = MockQgsFields([
    MockQgsField("id", "Integer"),
    MockQgsField("name", "String"),
    MockQgsField("geom", "Geometry")
])

assert fields.count() == 3
assert fields.names() == ["id", "name", "geom"]
```

### MockQgsWkbTypes

```python
assert MockQgsWkbTypes.displayString(1) == "Point"
assert MockQgsWkbTypes.displayString(3) == "Polygon"
```

## Future Improvements

1. **Create conftest.py**: Centralize mock setup to avoid duplication and ensure consistent mocking across test files.

2. **Use pytest-forked**: Add plugin for process isolation between test files.

3. **Convert to absolute imports**: Consider converting adapter imports to absolute for better pytest compatibility.

4. **Add more mock classes**: MockQgsProject, MockQgsGeometry, MockQgsCoordinateReferenceSystem as needed.

## Statistics

| Test File | Tests | Status |
|-----------|-------|--------|
| test_layer_service.py | 47 | ✅ Pass (isolated) |
| test_filter_executor_port.py | 31 | ✅ Pass (isolated) |
| **Total New/Fixed** | **78** | **✅** |

## Related Documentation

- [ARCHITECTURE-COMPARISON-20260113.md](ARCHITECTURE-COMPARISON-20260113.md)
- [REGRESSION-FIX-PLAN-20260113.md](REGRESSION-FIX-PLAN-20260113.md)
- [HEXAGONAL-MIGRATION-20260113.md](HEXAGONAL-MIGRATION-20260113.md)
