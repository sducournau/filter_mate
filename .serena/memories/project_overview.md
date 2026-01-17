# FilterMate Project Overview

**Last Updated:** January 17, 2026  
**Version:** 4.0.3 (v4.0.5 in development)  
**Status:** Production - Hexagonal Architecture Complete

## Recent Changes (v4.0.x Series - January 2026)

### v4.0.5 - Splitter Layout (In Development)
- 🔧 FIX: Panel truncation when dragging splitter handle
- 📐 Increased minimum heights: exploring 120→140px, toolset 200→250px
- 📊 Initial splitter ratio changed: 50/50 → 35/65

### v4.0.4 - UX Enhancement (January 13, 2026)
- ✨ NEW: Conditional widget states with automatic enable/disable
- 🎯 12 pushbutton→widget mappings (6 FILTERING + 6 EXPORTING)
- 📄 Documentation: `docs/UX-ENHANCEMENT-CONDITIONAL-WIDGET-STATES.md`

### v4.0.3 - Icons & Compact Mode (January 13, 2026)
- 🐛 FIX: Missing button icons via IconManager migration
- 🎨 Improved COMPACT mode dimensions (button 48→42px)
- 📐 Better layout spacing (margins 8→10px, GroupBox padding 6→8px)

### v4.0.2 - Signal Cleanup (January 13, 2026)
- 🧹 Eliminated duplicate fieldChanged signal connections
- ♻️ All signals now handled ONLY by ExploringController via SignalManager

### v4.0.1 - UI Profile Fix (January 13, 2026)
- 🐛 FIX: COMPACT restored as default UI profile
- 📐 Resolution breakpoint: 1920x1080 → 2560x1440

### v4.0.0-alpha - God Classes Complete! (January 12, 2026)
- 🎉 MILESTONE: All god classes objectives achieved (-66.9% reduction)
- 🏗️ Hexagonal architecture fully established
- 📊 20 services (10,528 lines), 12 controllers (13,143 lines)
- 🗂️ modules/ folder migrated to `before_migration/`

## Architecture v4.0 (Hexagonal)

```
filter_mate.py              → Plugin entry point
filter_mate_app.py          → Application orchestrator (2,271 lines)
filter_mate_dockwidget.py   → UI management (5,987 lines)
ui/controllers/             → MVC Controllers (13,143 lines)
core/
├── tasks/                  → Async operations (filter_task.py: 5,217 lines)
├── services/               → Hexagonal services (26 services, 14,520 lines)
├── domain/                 → Domain models
├── filter/                 → Filter domain logic
├── geometry/               → Geometry utilities
├── optimization/           → Query optimization
├── ports/                  → Port interfaces
├── strategies/             → Filter strategies
adapters/
├── backends/               → Multi-backend (postgresql/spatialite/ogr/memory)
├── qgis/                   → QGIS adapters (signals, tasks)
├── repositories/           → Data access
infrastructure/
├── logging/, cache/, utils/, database/
├── di/, feedback/, parallel/, streaming/

REMOVED: modules/ → migrated to before_migration/modules/ (v4.0)
```

## Code Statistics (January 17, 2026)

| Layer | Lines | Files |
|-------|-------|-------|
| Core (tasks+services+domain+...) | ~22,000 | 50+ |
| Adapters (backends+qgis+repos) | ~15,000 | 40+ |
| Infrastructure | ~8,000 | 25+ |
| UI (controllers+widgets+...) | ~20,000 | 45+ |
| Tests | ~47,600 | 157 |
| **Total (excl. tests)** | **~109,000** | **220+** |

## Key Metrics

- **Test Coverage**: ~75% (target: 80%)
- **God Classes Reduction**: -66.9% complete
- **Backend Support**: PostgreSQL, Spatialite, OGR, Memory
- **Translations**: 21 languages

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `filter_mate_app.py` | Application orchestrator | 2,271 |
| `filter_mate_dockwidget.py` | UI management | 5,987 |
| `core/tasks/filter_task.py` | Main filtering task | 5,217 |
| `ui/controllers/integration.py` | UI orchestration | 2,971 |
| `ui/controllers/exploring_controller.py` | Feature explorer | 2,922 |

## See Also

- Memory: `architecture_overview` - Detailed architecture
- Memory: `backend_architecture` - Multi-backend system
- Memory: `code_style_conventions` - Coding guidelines
- CHANGELOG.md - Full version history