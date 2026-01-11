# EPIC-1 Phase E6: Advanced Refactoring & Optimization

**Status:** PLANNED  
**Date:** January 11, 2026  
**Estimated Effort:** 4-6 sessions  
**Target:** Reduce filter_task.py from 11,199 to ~10,000 lines

## Overview

Phase E6 focuses on:

1. **Removing remaining legacy fallbacks** from methods with v4.0 delegations
2. **Extracting large monolithic methods** into focused, testable components
3. **Optimizing critical paths** for better performance
4. **Final cleanup** to reach target file size

## Current State (Post-E5)

- **File size**: 11,199 lines
- **Target**: ~10,000 lines
- **Remaining**: ~1,200 lines to optimize
- **Legacy fallbacks**: ~15-20 methods still have try/except ImportError blocks

## Planned Sessions

### E6-S1: Remove Remaining Legacy Fallbacks (~200-250 lines)

**Candidates:**

| Method                          | Lines | Legacy Block | Delegation Target              |
| ------------------------------- | ----- | ------------ | ------------------------------ |
| `_simplify_geometry_adaptive()` | 275   | ~250 lines   | GeometryPreparationAdapter     |
| `_apply_qgis_buffer()`          | ~80   | ~50 lines    | core.geometry.buffer_processor |
| `_simplify_buffer_result()`     | 146   | ~120 lines   | core.geometry.buffer_processor |

**Expected reduction**: ~250-300 lines

---

### E6-S2: Extract PostgreSQL Query Building (~300-400 lines)

**Large methods to decompose:**

| Method                               | Lines | Action                                         |
| ------------------------------------ | ----- | ---------------------------------------------- |
| `_build_backend_expression()`        | 544   | Extract to core/services/expression_builder.py |
| `_filter_action_postgresql_direct()` | 151   | Extract to adapters/backends/postgresql/       |
| `_sanitize_subset_string()`          | 160   | Extract to core/services/expression_service.py |

**Benefits:**

- Better testability for SQL generation
- Clearer separation of concerns
- Reusable across backends

**Expected reduction**: ~350-450 lines

---

### E6-S3: Refactor Geometry Processing Pipeline (~250-350 lines)

**Target methods:**

| Method                                           | Lines | Action                                                 |
| ------------------------------------------------ | ----- | ------------------------------------------------------ |
| `_prepare_geometries_by_provider()`              | 286   | Simplify by delegating to backend executors            |
| `_convert_geometry_collection_to_multipolygon()` | 135   | Extract to core/geometry/geometry_converter.py         |
| `_simplify_source_for_ogr_fallback()`            | 130   | Extract to adapters/backends/ogr/geometry_optimizer.py |

**Expected reduction**: ~300-400 lines

---

### E6-S4: Optimize Execution Flow Methods (~200-300 lines)

**Main execution methods:**

| Method                          | Lines | Action                                  |
| ------------------------------- | ----- | --------------------------------------- |
| `execute_geometric_filtering()` | 697   | Break into smaller orchestrator methods |
| `execute_filtering()`           | 230   | Delegate more to TaskBridge             |
| `execute_exporting()`           | 204   | Delegate more to core.export            |

**Strategy:**

- Keep high-level orchestration in filter_task.py
- Extract detailed logic to specialized modules
- Reduce method complexity (cyclomatic complexity)

**Expected reduction**: ~250-350 lines

---

### E6-S5: Cleanup & Optimization (~100-150 lines)

**Targets:**

1. **Remove duplicate code patterns**
   - Consolidate similar validation logic
   - Extract common error handling
2. **Optimize imports**
   - Move imports to module level where possible
   - Remove unused imports
3. **Simplify control flow**

   - Reduce nested if/else blocks
   - Use early returns
   - Extract complex conditions to named methods

4. **Documentation cleanup**
   - Remove obsolete comments
   - Update docstrings to reflect delegations
   - Remove "FIXME" and "TODO" for completed work

**Expected reduction**: ~100-200 lines

---

## Detailed Action Plan

### Phase E6-S1: Legacy Fallback Removal (PRIORITY 1)

#### Method: \_simplify_geometry_adaptive()

**Current state**: 275 lines (delegation + 250 lines legacy)
**Target**: ~25 lines (pure delegation)
**Module**: adapters/qgis/geometry_preparation.py (already exists)

**Steps:**

1. ✅ Verify GeometryPreparationAdapter.simplify_geometry_adaptive() works
2. Remove ~250 lines of legacy simplification logic
3. Test with large geometries (>1M WKT)
4. Validate buffer-aware tolerance calculation

#### Method: \_apply_qgis_buffer()

**Current state**: ~80 lines
**Target**: ~30 lines
**Module**: core/geometry/buffer_processor.py

**Steps:**

1. Check if buffer logic is already in core.geometry
2. Remove legacy QGIS processing calls
3. Delegate to BufferService

#### Method: \_simplify_buffer_result()

**Current state**: 146 lines
**Target**: ~25 lines
**Module**: core/geometry/buffer_processor.py

**Steps:**

1. Extract to BufferService.simplify_result()
2. Remove legacy progressive simplification code
3. Keep only delegation wrapper

---

### Phase E6-S2: Expression Builder Extraction

#### Create: core/services/expression_builder.py

**Purpose**: Centralize SQL expression building logic

**Classes:**

```python
class ExpressionBuilder:
    """Build backend-specific SQL expressions."""

    def build_postgresql_expression(context) -> str
    def build_spatialite_expression(context) -> str
    def build_ogr_expression(context) -> str
    def sanitize_subset_string(expression, provider) -> str
    def combine_expressions(expr1, expr2, operator) -> str
```

**Methods to extract:**

- `_build_backend_expression()` → ExpressionBuilder.build\_\*()
- `_sanitize_subset_string()` → ExpressionBuilder.sanitize_subset_string()
- Parts of `_combine_with_old_subset()` → ExpressionBuilder.combine_expressions()

**Benefits:**

- Single responsibility (expression building)
- Easier to test SQL generation
- Can be reused by other components

---

### Phase E6-S3: Geometry Pipeline Simplification

#### Refactor: \_prepare_geometries_by_provider()

**Current**: 286 lines of provider-specific branching
**Target**: ~50 lines of delegation

**Strategy:**

```python
def _prepare_geometries_by_provider(self):
    """Orchestrator - delegates to backend executors."""

    if self.provider == 'postgresql':
        return self.pg_executor.prepare_geometries(context)
    elif self.provider == 'spatialite':
        return self.spatialite_executor.prepare_geometries(context)
    else:
        return self.ogr_executor.prepare_geometries(context)
```

**Extract provider-specific logic to:**

- `adapters/backends/postgresql/geometry_preparer.py`
- `adapters/backends/spatialite/geometry_preparer.py`
- `adapters/backends/ogr/geometry_preparer.py`

---

### Phase E6-S4: Execution Flow Optimization

#### Refactor: execute_geometric_filtering()

**Current**: 697 lines - too complex!
**Target**: ~200-300 lines

**Decomposition strategy:**

```python
def execute_geometric_filtering(self):
    """Main orchestrator - high level only."""
    self._validate_geometric_parameters()
    self._prepare_source_geometry()
    self._execute_spatial_filter()
    self._post_process_results()

# Extract to separate methods:
def _validate_geometric_parameters(self) -> ValidationResult
def _prepare_source_geometry(self) -> GeometryContext
def _execute_spatial_filter(self, context) -> FilterResult
def _post_process_results(self, result) -> ProcessedResult
```

**Move complex logic to:**

- `core/filter/geometric_filter_orchestrator.py`
- Keep only coordination in filter_task.py

---

## Success Metrics

### Quantitative Goals

| Metric                      | Current      | Target E6     |
| --------------------------- | ------------ | ------------- |
| File size                   | 11,199 lines | ~10,000 lines |
| Largest method              | 697 lines    | <300 lines    |
| Methods >200 lines          | 8 methods    | <5 methods    |
| Legacy fallbacks            | ~15          | 0             |
| Cyclomatic complexity (avg) | ~12          | <8            |

### Qualitative Goals

- ✅ Zero legacy fallback code
- ✅ Clear separation of concerns
- ✅ All core logic testable in isolation
- ✅ Improved maintainability score (9.5/10)
- ✅ Better IDE navigation (smaller methods)

---

## Risk Assessment

### Low Risk

- **Legacy fallback removal**: Delegations are tested and working
- **Small method extraction**: Clear boundaries

### Medium Risk

- **Large method decomposition**: May need several iterations
- **Expression builder**: Complex SQL logic, needs thorough testing

### Mitigation

- Extract incrementally, commit after each step
- Maintain comprehensive test coverage
- Use feature flags if needed for gradual rollout

---

## Timeline Estimate

| Session   | Duration       | Lines Reduced          |
| --------- | -------------- | ---------------------- |
| E6-S1     | 1-2 hours      | ~250-300               |
| E6-S2     | 2-3 hours      | ~350-450               |
| E6-S3     | 2-3 hours      | ~300-400               |
| E6-S4     | 2-3 hours      | ~250-350               |
| E6-S5     | 1-2 hours      | ~100-200               |
| **Total** | **8-13 hours** | **~1,250-1,700 lines** |

**Expected final size**: ~9,500-9,950 lines (under 10,000 target!)

---

## Next Steps (Immediate)

1. **Start E6-S1**: Remove legacy from `_simplify_geometry_adaptive()` (biggest quick win)
2. **Verify**: Run test suite after each removal
3. **Document**: Update this plan with actual results
4. **Commit**: Small, focused commits for each method

---

## Post-E6 Roadmap

### Phase E7: Performance Optimization (Optional)

- Caching strategies for repeated operations
- Async/threading for independent operations
- Memory optimization for large datasets

### Phase E8: Testing & Documentation (Required)

- Increase test coverage to 80%+
- Update all documentation
- Create migration guide for v5.0

### Phase E9: Final Polish (Optional)

- Code style consistency (Black, isort)
- Type hints completion
- Final code review

---

## Appendix: Method Inventory

### Methods with Legacy Fallbacks (Need E6-S1)

```python
# High Priority (>100 lines legacy)
_simplify_geometry_adaptive()          # 250 lines legacy
_simplify_buffer_result()              # 120 lines legacy

# Medium Priority (50-100 lines legacy)
_apply_qgis_buffer()                   # 50 lines legacy
_fix_invalid_geometries()              # 60 lines legacy

# Low Priority (<50 lines legacy)
_apply_buffer_with_fallback()          # 30 lines legacy
_create_memory_layer_for_buffer()      # 20 lines legacy
```

### Large Methods Needing Decomposition (E6-S2 to E6-S4)

```python
execute_geometric_filtering()          # 697 lines - Priority 1
_build_backend_expression()            # 544 lines - Priority 1
finished()                             # 412 lines - Priority 2
_prepare_geometries_by_provider()      # 286 lines - Priority 1
execute_filtering()                    # 230 lines - Priority 2
execute_exporting()                    # 204 lines - Priority 3
```

---

**Status**: Ready to begin E6-S1  
**Estimated completion**: End of January 2026
