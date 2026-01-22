# FilterMate Project Overview

**Last Updated:** January 22, 2026  
**Version:** 4.3.10 (Production)  
**Status:** Production - Hexagonal Architecture Complete

## Recent Changes (v4.3.x Series - January 2026)

### v4.3.10 - Export & Buffer Complete Fix (January 22, 2026)
- 📦 Consolidated all v4.3.1-v4.3.9 fixes
- ✅ Export workflow: 100% functional
- ✅ Filter chaining with dynamic buffers: Working
- ✅ Buffer tables: Properly created, committed, reused
- ✅ Debug prints: All removed
- ✅ Code quality: 8.5/10 (+1.0)

### v4.3.9 - Buffer Transaction Fix
- 🔧 FIX: Buffer table transaction commit (psycopg2 autocommit=False)

### v4.3.8 - Cleanup
- 🧹 Removed all debug prints
- 📊 Export success message added

### v4.3.7 - Export Flags Sync
- 🔧 FIX: JUST-IN-TIME sync for ALL export flags

## Architecture v4.3 (Hexagonal)

```
filter_mate.py              → Plugin entry point
filter_mate_app.py          → Application orchestrator (2,383 lines)
filter_mate_dockwidget.py   → UI management (6,925 lines)
ui/controllers/             → MVC Controllers (13 controllers)
core/
├── tasks/                  → Async operations (filter_task.py: 5,851 lines)
├── services/               → Hexagonal services (28 services)
├── domain/                 → Domain models
├── filter/                 → Filter domain logic
├── geometry/               → Geometry utilities
├── optimization/           → Query optimization
├── ports/                  → Port interfaces
├── strategies/             → Filter strategies
├── export/                 → Export functionality
adapters/
├── backends/               → Multi-backend (postgresql/spatialite/ogr/memory)
├── qgis/                   → QGIS adapters (signals, tasks)
├── repositories/           → Data access
infrastructure/
├── logging/, cache/, utils/, database/
├── di/, feedback/, parallel/, streaming/
```

## Code Statistics (January 22, 2026)

| Layer | Lines | Files |
|-------|-------|-------|
| Core | 48,667 | ~100 |
| Adapters | 33,253 | ~70 |
| Infrastructure | 13,424 | ~40 |
| UI | 31,195 | ~55 |
| Tests | 51,962 | ~176 |
| **Total (prod)** | **126,539** | **~314** |

## Key Metrics

- **Test Coverage**: ~75% (target: 80%)
- **Quality Score**: 8.5/10 (+1.0 from v4.1.0)
- **Backend Support**: PostgreSQL, Spatialite, OGR, Memory
- **Translations**: 21 languages
- **Bare Excepts**: 0 ✅
- **Debug Prints**: 0 ✅

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `filter_mate_app.py` | Application orchestrator | 2,383 |
| `filter_mate_dockwidget.py` | UI management | 6,925 |
| `core/tasks/filter_task.py` | Main filtering task | 5,851 |
| `ui/controllers/integration.py` | UI orchestration | 3,028 |
| `ui/controllers/exploring_controller.py` | Feature explorer | 3,208 |

## See Also

- Memory: `CONSOLIDATED_PROJECT_CONTEXT` - Full project context
- Memory: `code_style_conventions` - Coding guidelines
- CHANGELOG.md - Full version history