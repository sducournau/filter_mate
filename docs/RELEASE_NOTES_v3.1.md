# FilterMate v3.1.0 Release Notes

> **Release Date:** January 9, 2026  
> **Type:** Minor Release (Architecture Migration Complete)

## 🎉 Overview

FilterMate v3.1.0 marks the **completion of the v3.0 architecture migration**. This release focuses on validation, testing, and preparation for the stable v3.x series.

## 🏗️ Architecture Migration Complete

The hexagonal architecture migration (started in v3.0.0) is now complete:

| Phase   | Status      | Description              |
| ------- | ----------- | ------------------------ |
| Phase 1 | ✅ Complete | Stabilization & Tests    |
| Phase 2 | ✅ Complete | Core Domain Layer        |
| Phase 3 | ✅ Complete | God Class Refactoring    |
| Phase 4 | ✅ Complete | Backend Modernization    |
| Phase 5 | ✅ Complete | Validation & Deprecation |

## ✨ What's New

### Comprehensive Test Suite

- **150+ new tests** covering all major workflows
- **E2E workflow tests** for filtering, export, favorites, history
- **Performance benchmarks** comparing v3.0 vs v2.x baselines
- **Regression detection** with 5% threshold alerts

### Performance Validation

v3.0 performance compared to v2.x baselines:

| Backend    | Operation  | v2.x  | v3.0  | Change  |
| ---------- | ---------- | ----- | ----- | ------- |
| PostgreSQL | 10k filter | 120ms | 102ms | -15% 🚀 |
| Spatialite | 10k filter | 250ms | 225ms | -10% 🚀 |
| OGR        | 10k filter | 800ms | 760ms | -5% 🚀  |

### Deprecation System

Legacy modules now emit warnings when imported:

```python
# This will show a DeprecationWarning:
from modules.appUtils import get_datasource_connexion_from_layer

# Use the new path instead:
from adapters.database_manager import DatabaseManager
```

**Timeline:**

- v3.1.0: Deprecation warnings added
- v3.x: Legacy modules continue to work
- v4.0.0: Legacy modules removed

## 📋 Migration Guide

See [docs/migration-v3.md](docs/migration-v3.md) for complete migration instructions.

### Quick Reference

| Old Import         | New Import             |
| ------------------ | ---------------------- |
| `modules.appUtils` | `infrastructure.utils` |
| `modules.appTasks` | `adapters.qgis.tasks`  |
| `modules.backends` | `adapters.backends`    |
| `modules.config_*` | `config.config`        |

## 🧪 Testing

Run the full test suite:

```bash
# All tests
pytest tests/ -v

# E2E tests only
pytest tests/ -m e2e -v

# Performance benchmarks
pytest tests/ -m benchmark -v

# Deprecation tests
pytest tests/test_deprecation_warnings.py -v
```

## 📊 Code Quality Metrics

| Metric          | Before  | After     | Target   |
| --------------- | ------- | --------- | -------- |
| Test Coverage   | ~60%    | ~75%      | 85%      |
| Code Complexity | Medium  | Low       | Low      |
| Type Hints      | Partial | Extensive | Full     |
| Documentation   | Partial | Complete  | Complete |

## 🔮 What's Next

### Phase 6: DockWidget Refactoring (In Progress)

- Extract layout managers ✅
- Extract style managers 🔄
- Extract controllers 📝
- Reduce DockWidget from 13k to <2k lines

### v3.2.0 (Planned)

- Theme manager extraction
- Icon manager extraction
- Button styler component

### v4.0.0 (Planned)

- Remove deprecated `modules.*` package
- Complete controller extraction
- Plugin API stabilization

## 🙏 Acknowledgments

Thanks to all contributors and users who provided feedback during the v3.0 migration process.

## 📚 Resources

- [Migration Guide](docs/migration-v3.md)
- [Architecture Documentation](docs/architecture-v3.md)
- [API Reference](docs/api-reference.md)
- [Issue Tracker](https://github.com/sducournau/filter_mate/issues)

---

_FilterMate v3.1.0 - Making spatial filtering simple and powerful._
