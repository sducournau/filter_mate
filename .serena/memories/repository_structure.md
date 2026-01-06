# Repository Structure - FilterMate v2.9.6

**Last Updated:** January 6, 2026

## Overview

FilterMate follows a clean, organized repository structure with clear separation between:
- **Runtime code**: Plugin files needed for QGIS execution
- **Development tools**: Scripts for building, translating, and debugging
- **Documentation**: User and developer documentation
- **Tests**: Unit tests and integration tests

## Root Directory Files

### Core Plugin Files (Runtime)
```
filter_mate.py              # Plugin entry point (QGIS integration)
filter_mate_app.py          # Main application orchestrator
filter_mate_dockwidget.py   # UI dockwidget management
filter_mate_dockwidget_base.py  # Base UI class (auto-generated from .ui)
filter_mate_dockwidget_base.ui  # Qt Designer UI file
resources.py                # Qt resources (auto-generated)
resources.qrc               # Qt resource definitions
__init__.py                 # Package initialization
```

### Build & Configuration
```
metadata.txt                # QGIS plugin metadata
compile_ui.bat              # Windows: Compile .ui to .py
setup_tests.bat             # Windows: Test environment setup
setup_tests.sh              # Linux: Test environment setup
requirements-test.txt       # Test dependencies
```

**Note (December 16, 2025):** Build and development scripts have been moved to `tools/` directory:
- `create_release_zip.py` → `tools/build/`
- `fix_pyuic5_imports.py`, `remove_ui_suffixes.py` → `tools/ui/`
- `test_import.py`, `test_plugin_load.py`, `reload_plugin.py` → `tools/diagnostic/`

### Documentation (Root)
```
README.md                   # User-facing introduction
CHANGELOG.md                # Complete version history
LICENSE                     # License file
```

### Git & Editor Configuration
```
.gitignore                  # Git ignore patterns
.gitattributes              # Git attributes
.editorconfig               # Editor settings
```

## Directory Structure

### config/
Plugin configuration files:
```
config/
├── config.json             # Active configuration (user-editable)
├── config.default.json     # Default configuration (reference)
├── config.py               # Configuration loader
└── config.v2.example.json  # Example for v2 format
```

### modules/
Core application modules:
```
modules/
├── appTasks.py             # Re-exports (backwards compat)
├── appUtils.py             # Database & utility functions
├── config_helpers.py       # Configuration utilities
├── constants.py            # Application constants
├── customExceptions.py     # Custom exceptions
├── feedback_utils.py       # User feedback utilities
├── filter_history.py       # Filter history & undo/redo
├── logging_config.py       # Logging setup
├── prepared_statements.py  # SQL prepared statements
├── psycopg2_availability.py  # Centralized psycopg2 imports (v2.8.7)
├── signal_utils.py         # Qt signal utilities
├── state_manager.py        # Application state
├── crs_utils.py            # CRS utilities (v2.5.7)
├── type_utils.py           # Type conversion utilities
├── ui_config.py            # Dynamic UI dimensions
├── ui_elements.py          # UI element creation
├── ui_elements_helpers.py  # UI helpers
├── ui_styles.py            # Theme management
├── ui_widget_utils.py      # Widget utilities
├── widgets.py              # Custom widgets
├── backends/               # Multi-backend architecture
│   ├── __init__.py
│   ├── base_backend.py     # Abstract base class
│   ├── factory.py          # Backend factory
│   ├── postgresql_backend.py
│   ├── spatialite_backend.py
│   └── ogr_backend.py
├── tasks/                  # Async task modules
│   ├── __init__.py
│   ├── README.md
│   ├── task_utils.py           # Common utilities
│   ├── geometry_cache.py       # Geometry caching
│   ├── layer_management_task.py
│   ├── filter_task.py
│   ├── expression_evaluation_task.py  # Expression evaluation
│   ├── multi_step_filter.py    # Multi-step filtering
│   ├── parallel_executor.py    # Parallel execution
│   ├── progressive_filter.py   # Progressive/two-phase filtering (v2.5.9)
│   ├── query_cache.py          # Query caching with TTL
│   ├── query_complexity_estimator.py  # SQL complexity analysis (v2.5.9)
│   └── result_streaming.py     # Streaming exports
└── qt_json_view/           # JSON tree view widgets
    ├── __init__.py
    ├── CHANGELOG.md
    ├── README.md
    ├── datatypes.py
    ├── delegate.py
    ├── model.py
    └── view.py
```

### tools/
Development utilities (NOT part of plugin runtime):
```
tools/
├── README.md                       # Tool documentation
├── add_missing_strings.py          # Add missing translation strings
├── compile_translations_simple.py  # Simple translation compiler
├── create_new_translations.py      # Create new language translations
├── enable_debug_logs.py            # Enable debug logging
├── test_spatialite_large_gpkg.py   # Spatialite performance testing
├── update_translations.py          # Update translation files
├── verify_all_translations.py      # Verify translation completeness
├── zip_plugin.py                   # Create plugin ZIP (Python)
├── zip_plugin.sh                   # Create plugin ZIP (Shell)
├── i18n/                           # Translation tools (additional)
│   └── ...
└── ui/                             # UI modification tools
    └── ...
```

### tests/
Unit and integration tests:
```
tests/
├── conftest.py                      # Pytest fixtures
├── README.md                        # Testing documentation
├── __init__.py                      # Package init
├── test_auto_activate_config.py     # Config auto-activation tests
├── test_auto_config_reset.py        # Config reset tests
├── test_config_fallback.py          # Config fallback tests
├── test_config_helpers.py           # Config helper tests
├── test_config_improved_structure.py # Config structure tests
├── test_config_migration.py         # Config migration tests
├── test_filter_preservation.py      # Filter preservation tests
├── test_forced_backend_respect.py   # Backend forcing tests
├── test_geographic_crs.py           # CRS handling tests
├── test_negative_buffer.py          # Negative buffer tests (v2.5.x)
├── test_phase4_optimizations.py     # Phase 4 optimization tests
├── test_plugin_loading.py           # Plugin loading tests
├── test_postgresql_buffer.py        # PostgreSQL buffer tests
├── test_postgresql_layer_handling.py # PostgreSQL layer tests
├── test_postgresql_mv_cleanup.py    # MV cleanup tests
├── test_primary_key_detection.py    # PK detection tests
├── test_project_change.py           # Project change tests
├── test_undo_redo.py                # Undo/redo tests
└── test_backends/                   # Backend-specific tests
```

### docs/
Documentation:
```
docs/
├── EXPRESSION_LOADING_OPTIMIZATION.md        # Expression loading optimizations
├── FIX_MEMORY_LAYER_COUNT_2025-12.md         # Memory layer feature count fix
├── FIX_NEGATIVE_BUFFER_2025-12.md            # Negative buffer handling fix
├── NEGATIVE_BUFFER_FIX_README.md             # Negative buffer documentation
├── PERFORMANCE_OPTIMIZATION_v2.5.10.md       # v2.5.10 performance optimizations
├── RELEASE_NOTES_v2.5.3.md                   # v2.5.3 release notes
├── RELEASE_NOTES_v2.5.4.md                   # v2.5.4 release notes
├── RELEASE_NOTES_v2.5.5.md                   # v2.5.5 release notes (CRITICAL)
├── RELEASE_NOTES_v2.5.6.md                   # v2.5.6 release notes
├── RELEASE_NOTES_v2.5.7.md                   # v2.5.7 release notes
├── SYNC_ARCHITECTURE_v2.5.6.md               # Bidirectional sync architecture
├── TRANSLATION_PLAN_2025-12.md               # Translation planning
├── archive/                                   # Historical documentation
│   └── ... (archived docs)
└── fixes/                                     # Bug fix documentation (legacy)
    └── ... (older fix documentation)
```

### i18n/
Translations (21 languages):
```
i18n/
├── FilterMate_am.ts/.qm    # Amharic (NEW v2.4.1)
├── FilterMate_da.ts/.qm    # Danish
├── FilterMate_de.ts/.qm    # German
├── FilterMate_en.ts/.qm    # English
├── FilterMate_es.ts/.qm    # Spanish
├── FilterMate_fi.ts/.qm    # Finnish
├── FilterMate_fr.ts/.qm    # French
├── FilterMate_hi.ts/.qm    # Hindi
├── FilterMate_id.ts/.qm    # Indonesian
├── FilterMate_it.ts/.qm    # Italian
├── FilterMate_nb.ts/.qm    # Norwegian Bokmål
├── FilterMate_nl.ts/.qm    # Dutch
├── FilterMate_pl.ts/.qm    # Polish
├── FilterMate_pt.ts/.qm    # Portuguese
├── FilterMate_ru.ts/.qm    # Russian
├── FilterMate_sl.ts/.qm    # Slovenian (NEW v2.4.1)
├── FilterMate_sv.ts/.qm    # Swedish
├── FilterMate_tl.ts/.qm    # Filipino/Tagalog (NEW v2.4.1)
├── FilterMate_tr.ts/.qm    # Turkish
├── FilterMate_uz.ts/.qm    # Uzbek
├── FilterMate_vi.ts/.qm    # Vietnamese
└── FilterMate_zh.ts/.qm    # Chinese
```

### resources/
Static resources:
```
resources/
└── styles/                 # QSS theme files
    ├── default.qss
    ├── dark.qss
    ├── light.qss
    └── dynamic_template.qss
```

### icons/
Plugin icons and images.

### website/
Docusaurus documentation website:
```
website/
├── docusaurus.config.ts
├── package.json
├── docs/                   # MDX documentation
├── src/                    # Website components
└── i18n/                   # Website translations
```

### .github/
GitHub configuration:
```
.github/
├── copilot-instructions.md # Coding guidelines
└── workflows/
    └── test.yml            # CI/CD pipeline
```

### .serena/
Serena MCP configuration:
```
.serena/
├── config.json             # Serena project config
└── memories/               # Project memories
```

## File Counts Summary

| Category | File Count | Description |
|----------|------------|-------------|
| Core Plugin | ~10 | Runtime Python files |
| Modules | ~35 | Application modules (including object_safety.py) |
| Tests | ~20 | Test files |
| Tools | ~15 | Development utilities |
| Documentation | ~20 | Markdown files |
| Translations | 42 | .ts and .qm files (21 languages × 2) |
| Resources | ~10 | QSS and icons |

## Gitignore Patterns

Key patterns in `.gitignore`:
- `__pycache__/`, `*.py[cod]` - Python cache
- `.pytest_cache/`, `htmlcov/` - Test outputs
- `website/node_modules/` - Node dependencies
- `*.backup`, `*.bak` - Backup files
- `*.sqlite-wal`, `*.sqlite-shm` - SQLite temp files

## Notes

1. **Root directory is clean**: Only essential files, no utility scripts
2. **tools/ is not packaged**: Excluded from release ZIP
3. **docs/archive/**: Historical documentation preserved but not active
4. **Backwards compatibility**: Module re-exports maintain API stability
