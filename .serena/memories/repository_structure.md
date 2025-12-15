# Repository Structure - FilterMate v2.3.0

**Last Updated:** December 15, 2025

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
├── signal_utils.py         # Qt signal utilities
├── state_manager.py        # Application state
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
│   ├── task_utils.py       # Common utilities
│   ├── geometry_cache.py   # Geometry caching
│   ├── layer_management_task.py
│   └── filter_task.py
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
├── README.md               # Tool documentation
├── build/                  # Build & release
│   └── create_release_zip.py
├── diagnostic/             # Debugging tools
│   ├── diagnose_before_load.py
│   ├── diagnose_freeze.py
│   ├── test_color_picker.py
│   ├── test_load_simple.py
│   └── validate_config_helpers.py
├── i18n/                   # Translation tools
│   ├── add_ui_tooltips_translations.py
│   ├── compile_translations.bat
│   ├── compile_ts_to_qm.py
│   ├── open_qt_linguist.bat
│   ├── simple_qm_compiler.py
│   ├── update_translations.py
│   └── verify_translations.py
└── ui/                     # UI modification tools
    ├── fix_ui_suffixes.py
    ├── remove_ui_suffixes.py
    ├── update_ui_tooltips.py
    └── verify_ui_fix.py
```

### tests/
Unit and integration tests:
```
tests/
├── conftest.py             # Pytest fixtures
├── README.md               # Testing documentation
├── test_*.py               # Test modules (30+ files)
└── test_backends/          # Backend-specific tests
```

### docs/
Documentation:
```
docs/
├── CONFIG_HARMONIZATION_*.md  # Configuration docs
├── POSTGRESQL_MV_OPTIMIZATION.md
└── archive/                # Historical documentation
    ├── CODEBASE_QUALITY_AUDIT_*.md
    ├── IMPLEMENTATION_STATUS_*.md
    ├── UNDO_REDO_*.md
    └── ... (archived docs)
```

### i18n/
Translations (7 languages):
```
i18n/
├── FilterMate_de.ts/.qm    # German
├── FilterMate_en.ts/.qm    # English
├── FilterMate_es.ts/.qm    # Spanish
├── FilterMate_fr.ts/.qm    # French
├── FilterMate_it.ts/.qm    # Italian
├── FilterMate_nl.ts/.qm    # Dutch
└── FilterMate_pt.ts/.qm    # Portuguese
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
| Modules | ~30 | Application modules |
| Tests | ~35 | Test files |
| Tools | ~15 | Development utilities |
| Documentation | ~20 | Markdown files |
| Translations | 14 | .ts and .qm files |
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
