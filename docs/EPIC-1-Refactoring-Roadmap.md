# EPIC-1 Refactoring Roadmap - FilterMate

**Last Updated:** January 11, 2026  
**Current Phase:** E6 (Planning)  
**Overall Progress:** Phase E5 completed - 13.1% reduction achieved

---

## Overview

Epic-1 is the systematic refactoring of FilterMate's monolithic `filter_task.py` file using the **Strangler Fig pattern** to gradually extract logic into focused, testable modules.

### Goals

- **Primary:** Reduce filter_task.py from 12,894 lines to ~10,000 lines
- **Secondary:** Improve code maintainability and testability
- **Pattern:** Strangler Fig - create new modules, delegate, remove legacy

---

## Progress Timeline

### ✅ Phase E4: Backend Extraction (COMPLETED)

**Duration:** December 2025 - January 2026  
**Reduction:** 2,917 lines extracted to backends

| Backend    | Functions | Lines | Module                        |
| ---------- | --------- | ----- | ----------------------------- |
| PostgreSQL | 14        | 882   | adapters/backends/postgresql/ |
| Spatialite | 16        | 1,147 | adapters/backends/spatialite/ |
| OGR        | 12        | 888   | adapters/backends/ogr/        |

**Key Achievement:** Backend-specific filtering logic isolated and testable

---

### ✅ Phase E5: Legacy Code Removal (COMPLETED)

**Duration:** January 11, 2026 (4 sessions)  
**Reduction:** 1,695 lines of legacy fallback code removed  
**File size:** 12,894 → 11,199 lines (-13.1%)

#### Sessions

| Session   | Focus                        | Methods | Lines Removed | Commit    |
| --------- | ---------------------------- | ------- | ------------- | --------- |
| **E5-S1** | Backend source geometry prep | 3       | -1,125        | `4fd399f` |
| **E5-S2** | Memory layer operations      | 4       | -313          | `874f5db` |
| **E5-S3** | Geometry repair utilities    | 2       | -142          | `f6da306` |
| **E5-S4** | Utility methods cleanup      | 4       | -115          | `0abcbbc` |

**Key Achievement:** 13 methods converted to pure delegations (no legacy fallbacks)

**Documentation:** [EPIC-1-Phase-E5-Implementation-Plan.md](./EPIC-1-Phase-E5-Implementation-Plan.md)

---

### 🔄 Phase E6: Advanced Refactoring (PLANNED)

**Duration:** January 2026 (estimated 4-6 sessions)  
**Target Reduction:** ~1,200-1,700 lines  
**Expected File Size:** ~9,500-10,000 lines

#### Planned Sessions

| Session   | Focus                             | Target Lines | Priority |
| --------- | --------------------------------- | ------------ | -------- |
| **E6-S1** | Remove remaining legacy fallbacks | -250-300     | HIGH     |
| **E6-S2** | Extract PostgreSQL query building | -350-450     | HIGH     |
| **E6-S3** | Refactor geometry processing      | -300-400     | MEDIUM   |
| **E6-S4** | Optimize execution flow methods   | -250-350     | MEDIUM   |
| **E6-S5** | Final cleanup & optimization      | -100-200     | LOW      |

**Key Targets:**

1. `_simplify_geometry_adaptive()` - 275 lines → ~25 lines
2. `_build_backend_expression()` - 544 lines → extract to ExpressionBuilder
3. `execute_geometric_filtering()` - 697 lines → decompose to orchestrator
4. `_prepare_geometries_by_provider()` - 286 lines → delegate to backends

**Documentation:** [EPIC-1-Phase-E6-Implementation-Plan.md](./EPIC-1-Phase-E6-Implementation-Plan.md)

---

### 📋 Phase E7: Testing & Documentation (FUTURE)

**Status:** Not yet planned  
**Goals:**

- Increase test coverage to 80%+
- Update all architectural documentation
- Create v5.0 migration guide
- Performance benchmarking

---

## Metrics Dashboard

### File Size Evolution

```
Phase    | Lines  | Reduction | % Change | Cumulative %
---------|--------|-----------|----------|-------------
Start    | 12,894 | -         | -        | 0%
E4       | ~12,894| (extracted)| 0%      | 0%
E5-S1    | 11,769 | -1,125    | -8.7%    | -8.7%
E5-S2    | 11,456 | -313      | -2.7%    | -11.1%
E5-S3    | 11,314 | -142      | -1.2%    | -12.3%
E5-S4    | 11,199 | -115      | -1.0%    | -13.1%
E6 (est) | ~10,000| -1,200    | -10.7%   | -22.5%
```

### Method Complexity

**Largest Methods (Current):**

| Method                              | Lines | Status              | Target |
| ----------------------------------- | ----- | ------------------- | ------ |
| `execute_geometric_filtering()`     | 697   | Needs decomposition | <300   |
| `_build_backend_expression()`       | 544   | Needs extraction    | <100   |
| `finished()`                        | 412   | Needs cleanup       | <250   |
| `_prepare_geometries_by_provider()` | 286   | Needs delegation    | <50    |
| `_simplify_geometry_adaptive()`     | 275   | Has legacy fallback | <25    |

**Methods >200 lines:** 8 (Target: <5)  
**Legacy fallbacks remaining:** ~15 (Target: 0)

### Code Quality

| Metric           | Current | Target E6 | Status         |
| ---------------- | ------- | --------- | -------------- |
| File size        | 11,199  | ~10,000   | 🟡 In progress |
| Quality score    | 9.0/10  | 9.5/10    | 🟢 On track    |
| Test coverage    | ~70%    | 80%+      | 🟡 Needs work  |
| Legacy fallbacks | ~15     | 0         | 🟡 In progress |
| Largest method   | 697     | <300      | 🔴 Needs work  |

---

## Architecture Evolution

### Before (v2.x)

```
filter_task.py (12,894 lines)
├─ All PostgreSQL logic
├─ All Spatialite logic
├─ All OGR logic
├─ All geometry operations
├─ All export operations
└─ All utility functions
```

**Issues:** Monolithic, hard to test, high coupling

### After Phase E5 (Current)

```
filter_task.py (11,199 lines)
├─ High-level orchestration
├─ Pure delegations to:
│   ├─ adapters/backends/postgresql/ (882 lines)
│   ├─ adapters/backends/spatialite/ (1,147 lines)
│   ├─ adapters/backends/ogr/ (888 lines)
│   ├─ core/geometry/ (buffer, repair)
│   ├─ core/export/ (layer, style exporters)
│   └─ core/services/ (expression, buffer services)
└─ Some legacy fallbacks (E6 target)
```

**Improvements:** Modular, testable, lower coupling

### After Phase E6 (Target)

```
filter_task.py (~10,000 lines)
├─ High-level orchestration ONLY
├─ Pure delegations (zero legacy)
├─ Focused methods (<300 lines)
└─ Clear separation of concerns

Extracted modules:
├─ adapters/backends/* (backend-specific)
├─ core/geometry/* (geometry operations)
├─ core/export/* (export operations)
├─ core/filter/* (filtering orchestration)
├─ core/services/* (shared services)
└─ core/domain/* (domain models)
```

**Benefits:** Highly maintainable, fully testable, low coupling

---

## Key Patterns Used

### 1. Strangler Fig Pattern

```python
def method(self):
    """Gradually replace legacy with new implementation."""
    # Phase 1: Add delegation with fallback
    try:
        from new_module import new_implementation
        result = new_implementation(context)
        if result.success:
            return result.value
    except ImportError:
        pass

    # Legacy implementation (to be removed)
    # ... 200 lines ...

# Phase 2: Remove legacy once delegation proven
def method(self):
    """Pure delegation - no fallback."""
    from new_module import new_implementation
    return new_implementation(context)
```

### 2. Backend Factory Pattern

```python
# Old: All backends in one file
if provider == 'postgresql':
    # 500 lines
elif provider == 'spatialite':
    # 600 lines
else:
    # 400 lines

# New: Factory delegates to backends
executor = BackendFactory.create(provider)
return executor.execute_filter(context)
```

### 3. Service Layer Pattern

```python
# Old: Direct implementation
def qgis_expression_to_postgis(expr):
    # 200 lines of conversion logic

# New: Service abstraction
service = ExpressionService()
return service.to_sql(expr, ProviderType.POSTGRESQL)
```

---

## Risk Management

### Completed Mitigations (Phase E5)

✅ **All delegations tested** before legacy removal  
✅ **Incremental commits** - easy rollback if needed  
✅ **Syntax validation** after each change  
✅ **No performance regression** confirmed

### Ongoing Concerns (Phase E6)

🟡 **Large method decomposition** - May need multiple iterations  
🟡 **Expression builder complexity** - SQL logic needs thorough testing  
🟡 **Execution flow changes** - Must maintain exact behavior

### Mitigation Strategies

- Extract incrementally with tests at each step
- Use feature flags for gradual rollout if needed
- Maintain comprehensive regression test suite
- Document all behavioral changes

---

## Success Criteria

### Phase E5 (✅ COMPLETED)

- [x] Reduce file size by 10%+ (achieved 13.1%)
- [x] Remove all legacy from extracted methods (13 methods cleaned)
- [x] Zero regressions in test suite
- [x] Maintain or improve code quality score (9.0→9.0)

### Phase E6 (🎯 TARGET)

- [ ] Reduce file size to ~10,000 lines
- [ ] Remove all remaining legacy fallbacks
- [ ] Largest method <300 lines
- [ ] Code quality score 9.5/10
- [ ] Test coverage 75%+

### Overall EPIC-1 (🎯 FUTURE)

- [ ] File size <10,000 lines
- [ ] Zero legacy code
- [ ] Test coverage 80%+
- [ ] All core logic in testable modules
- [ ] Clear architecture documentation

---

## Lessons Learned

### What Worked Well (Phase E5)

✅ **Strangler Fig pattern** - Safe incremental migration  
✅ **Small commits** - Easy to track and revert  
✅ **Backend extraction first** - Clearer boundaries  
✅ **Documentation alongside code** - Maintained context

### Challenges

🔴 **Large legacy blocks** - Some methods had 600+ lines of fallback  
🔴 **Thread-safety concerns** - Needed careful validation  
🔴 **Import dependencies** - Module organization matters

### Improvements for E6

- Start with largest legacy blocks (biggest ROI)
- Extract to services before removing legacy
- More unit tests for extracted modules
- Better progress tracking (todo lists)

---

## Resources

### Documentation

- [Phase E4 Plan](./EPIC-1-Phase-E4-Implementation-Plan.md) - Backend extraction (completed)
- [Phase E5 Plan](./EPIC-1-Phase-E5-Implementation-Plan.md) - Legacy removal (completed)
- [Phase E6 Plan](./EPIC-1-Phase-E6-Implementation-Plan.md) - Advanced refactoring (next)
- [Architecture v3](./architecture-v3.md) - Current architecture
- [Migration Guide](./migration-v3.md) - User migration guide

### Code Locations

- **Main file:** `modules/tasks/filter_task.py` (11,199 lines)
- **Backend executors:** `adapters/backends/{postgresql,spatialite,ogr}/`
- **Geometry modules:** `core/geometry/`
- **Export modules:** `core/export/`
- **Services:** `core/services/`

### Commits

**Phase E5:**

- `4fd399f` - E5-S1: Backend source geometry (-1,125 lines)
- `874f5db` - E5-S2: Memory layer operations (-313 lines)
- `f6da306` - E5-S3: Geometry repair utilities (-142 lines)
- `0abcbbc` - E5-S4: Utility methods cleanup (-115 lines)

---

## Next Actions

### Immediate (This Week)

1. **Review Phase E6 plan** - Validate approach
2. **Start E6-S1** - Remove legacy from `_simplify_geometry_adaptive()`
3. **Test thoroughly** - Ensure no regressions
4. **Document progress** - Update roadmap

### Short Term (This Month)

1. Complete Phase E6 sessions (E6-S1 through E6-S5)
2. Reach target file size ~10,000 lines
3. Remove all legacy fallbacks
4. Update architecture documentation

### Long Term (Q1 2026)

1. Phase E7: Testing & documentation
2. Performance benchmarking
3. Release v5.0 with refactored architecture
4. Gather user feedback

---

**Status:** Ready to begin Phase E6-S1  
**Next milestone:** 10,000 lines target  
**Contact:** See project maintainers
