# Repository Structure - FilterMate v4.0.3

**Last Updated:** January 17, 2026

## Overview

FilterMate v4.0 uses a **complete hexagonal architecture** with clear separation:
- **Core**: Business logic (tasks, services, domain, ports)
- **Adapters**: External integrations (backends, QGIS, repositories)
- **Infrastructure**: Cross-cutting concerns (cache, database, utils)
- **UI**: User interface (controllers, widgets, styles)
- **Tests**: Comprehensive test suite (157 files, ~47K lines)

## Root Directory Files

### Core Plugin Files (Runtime)
```
filter_mate.py              # Plugin entry point (QGIS integration)
filter_mate_app.py          # Main application orchestrator (2,271 lines)
filter_mate_dockwidget.py   # UI dockwidget management (5,987 lines)
filter_mate_dockwidget_base.py  # Base UI class (auto-generated)
filter_mate_dockwidget_base.ui  # Qt Designer UI file
resources.py                # Qt resources (auto-generated)
resources.qrc               # Qt resource definitions
__init__.py                 # Package initialization
```

### Build & Configuration
```
metadata.txt                # QGIS plugin metadata (v4.0.3)
compile_ui.bat/sh           # Compile .ui to .py
setup_tests.bat/sh          # Test environment setup
requirements-test.txt       # Test dependencies
pytest.ini                  # Pytest configuration
```

### Documentation
```
README.md                   # User-facing introduction
CHANGELOG.md                # Complete version history (5,987 lines)
LICENSE                     # License file
```

### Development Tools (Root)
```
check_imports.py            # Import validation
fix_imports.py              # Import fixes
DIAGNOSTIC_FILTER.py        # Filter diagnostics
ENABLE_DEBUG_LOGGING.py     # Debug logging
ENABLE_LOGGING.py           # Logging setup
clean_python_cache.sh       # Cache cleanup
```

## Hexagonal Architecture Directories

### core/
Core business logic:
```
core/
├── domain/                 # Domain models
│   ├── exceptions.py
│   ├── favorites_manager.py
│   ├── filter_expression.py
│   ├── filter_result.py
│   ├── layer_info.py
│   └── optimization_config.py
├── export/                 # Export functionality
│   ├── batch_exporter.py
│   ├── export_validator.py
│   ├── layer_exporter.py
│   └── style_exporter.py
├── filter/                 # Filter domain logic
│   ├── expression_builder.py
│   ├── expression_combiner.py
│   ├── expression_sanitizer.py
│   ├── filter_orchestrator.py
│   ├── pk_formatter.py
│   ├── result_processor.py
│   └── source_filter_builder.py
├── geometry/               # Geometry utilities
│   ├── buffer_processor.py
│   ├── crs_utils.py
│   ├── geometry_converter.py
│   ├── geometry_repair.py
│   ├── geometry_safety.py
│   └── spatial_index.py
├── optimization/           # Query optimization
│   ├── combined_query_optimizer.py (1,599 lines)
│   ├── config_provider.py
│   ├── logging_utils.py
│   ├── performance_advisor.py
│   └── query_analyzer.py
├── ports/                  # Port interfaces (hexagonal)
│   ├── backend_port.py
│   ├── backend_services.py
│   ├── cache_port.py
│   ├── filter_executor_port.py
│   ├── filter_optimizer.py
│   ├── layer_lifecycle_port.py
│   ├── qgis_port.py
│   ├── repository_port.py
│   └── task_management_port.py
├── services/               # Hexagonal services (26 services, 14,520 lines)
│   ├── app_initializer.py (696)
│   ├── auto_optimizer.py (678)
│   ├── backend_expression_builder.py (593)
│   ├── backend_service.py (735)
│   ├── buffer_service.py (470)
│   ├── canvas_refresh_service.py (382)
│   ├── datasource_manager.py (508)
│   ├── export_service.py (422)
│   ├── expression_service.py (741)
│   ├── favorites_service.py (853)
│   ├── filter_application_service.py (201)
│   ├── filter_parameter_builder.py (419)
│   ├── filter_service.py (785)
│   ├── geometry_preparer.py (703)
│   ├── history_service.py (625)
│   ├── layer_filter_builder.py (348)
│   ├── layer_lifecycle_service.py (860)
│   ├── layer_organizer.py (454)
│   ├── layer_service.py (728)
│   ├── optimization_manager.py (545)
│   ├── postgres_session_manager.py (698)
│   ├── source_layer_filter_executor.py (410)
│   ├── source_subset_buffer_builder.py (440)
│   ├── task_management_service.py (216)
│   ├── task_orchestrator.py (545)
│   └── task_run_orchestrator.py (465)
├── strategies/             # Filter strategies
│   ├── multi_step_filter.py (1,050)
│   └── progressive_filter.py (880)
└── tasks/                  # Async task modules
    ├── filter_task.py (5,217 lines - main!)
    ├── layer_management_task.py (1,869)
    ├── expression_evaluation_task.py
    ├── task_completion_handler.py
    ├── builders/           # Subset string builders
    ├── cache/              # Expression/geometry cache
    ├── collectors/         # Feature collectors
    ├── connectors/         # Backend connectors
    ├── dispatchers/        # Action dispatchers
    └── executors/          # Filter executors
```

### adapters/
External integrations:
```
adapters/
├── backends/               # Multi-backend architecture
│   ├── factory.py
│   ├── hexagonal_config.py
│   ├── legacy_adapter.py
│   ├── postgresql_availability.py
│   ├── memory/             # Memory backend
│   │   └── backend.py
│   ├── ogr/                # OGR backend
│   │   ├── backend.py
│   │   ├── executor_wrapper.py
│   │   ├── filter_executor.py (1,033)
│   │   └── geometry_optimizer.py
│   ├── postgresql/         # PostgreSQL backend
│   │   ├── backend.py
│   │   ├── cleanup.py
│   │   ├── executor_wrapper.py
│   │   ├── filter_actions.py (787)
│   │   ├── filter_executor.py (948)
│   │   ├── mv_manager.py
│   │   ├── optimizer.py
│   │   └── schema_manager.py
│   └── spatialite/         # Spatialite backend
│       ├── backend.py
│       ├── cache.py
│       ├── executor_wrapper.py
│       ├── filter_executor.py (1,144)
│       └── index_manager.py
├── qgis/                   # QGIS adapters
│   ├── expression_adapter.py
│   ├── factory.py
│   ├── feature_adapter.py
│   ├── filter_optimizer.py (820)
│   ├── geometry_adapter.py
│   ├── geometry_preparation.py (1,204)
│   ├── layer_adapter.py
│   ├── source_feature_resolver.py
│   ├── signals/            # Signal management
│   │   ├── debouncer.py
│   │   ├── layer_signal_handler.py
│   │   ├── migration_helper.py
│   │   └── signal_manager.py
│   └── tasks/              # QGIS tasks
│       ├── base_task.py
│       ├── export_task.py
│       ├── filter_task.py
│       ├── layer_task.py
│       ├── multi_step_task.py
│       ├── progress_handler.py
│       └── spatial_task.py
├── repositories/           # Data access
│   └── layer_repository.py
├── app_bridge.py
├── backend_registry.py
├── compat.py
├── database_manager.py
├── filter_result_handler.py (809)
├── layer_refresh_manager.py
├── layer_task_completion_handler.py
├── layer_validator.py
├── legacy_adapter.py
├── task_bridge.py
├── task_builder.py (957)
├── undo_redo_handler.py
└── variables_manager.py
```

### infrastructure/
Cross-cutting concerns:
```
infrastructure/
├── cache/                  # Caching
│   ├── cache_manager.py
│   ├── exploring_cache.py
│   ├── geometry_cache.py
│   └── query_cache.py
├── config/                 # Configuration
│   └── config_migration.py
├── database/               # Database utilities
│   ├── connection_pool.py (995)
│   ├── postgresql_support.py
│   ├── prepared_statements.py
│   ├── spatialite_support.py
│   └── sql_utils.py
├── di/                     # Dependency injection
│   ├── container.py
│   └── providers.py
├── feedback/               # User feedback
├── logging/                # Logging setup
├── parallel/               # Parallel execution
│   └── parallel_executor.py
├── state/                  # State management
│   └── flag_manager.py
├── streaming/              # Result streaming
│   └── result_streaming.py
├── utils/                  # Utilities
│   ├── complexity_estimator.py
│   ├── layer_utils.py (1,185)
│   ├── provider_utils.py
│   ├── signal_utils.py
│   ├── task_utils.py
│   └── validation_utils.py
├── constants.py
├── field_utils.py
├── resilience.py
├── signal_utils.py
└── state_manager.py
```

### ui/
User interface:
```
ui/
├── config/                 # UI configuration
│   ├── ui_elements.py
│   └── __init__.py (924) - UI profiles (COMPACT/NORMAL)
├── controllers/            # MVC controllers (12 controllers)
│   ├── integration.py (2,971) - Main orchestrator
│   ├── exploring_controller.py (2,922)
│   ├── filtering_controller.py (1,467)
│   ├── property_controller.py (1,267)
│   ├── layer_sync_controller.py (1,244)
│   ├── exporting_controller.py (975)
│   ├── backend_controller.py (974)
│   ├── config_controller.py
│   ├── favorites_controller.py
│   ├── ui_layout_controller.py
│   ├── base_controller.py
│   ├── registry.py
│   └── mixins/             # Controller mixins
│       └── layer_selection_mixin.py
├── dialogs/                # Dialogs
│   ├── config_editor_widget.py
│   ├── favorites_manager.py
│   ├── optimization_dialog.py
│   └── postgres_info_dialog.py
├── elements/               # UI elements
├── layout/                 # Layout management
│   ├── action_bar_manager.py
│   ├── base_manager.py
│   ├── dimensions_manager.py (902)
│   ├── spacing_manager.py
│   └── splitter_manager.py
├── managers/               # UI managers
│   ├── configuration_manager.py (915)
│   └── exploring_signal_manager.py
├── styles/                 # Styling
│   ├── base_styler.py
│   ├── button_styler.py
│   ├── icon_manager.py
│   ├── style_loader.py
│   ├── theme_manager.py
│   └── theme_watcher.py
├── widgets/                # Custom widgets
│   ├── backend_indicator.py
│   ├── custom_widgets.py (1,166)
│   ├── favorites_widget.py
│   ├── history_widget.py
│   ├── tree_view.py
│   └── json_view/          # JSON tree view
│       ├── datatypes.py (823)
│       ├── delegate.py
│       ├── model.py
│       ├── themes.py
│       └── view.py
└── orchestrator.py
```

### tests/
Comprehensive test suite (157 files, ~47,600 lines):
```
tests/
├── unit/                   # Unit tests
│   ├── adapters/           # Adapter tests
│   ├── core/               # Core tests
│   ├── infrastructure/     # Infrastructure tests
│   ├── ports/              # Port tests
│   ├── services/           # Service tests
│   ├── tasks/              # Task tests
│   ├── ui/                 # UI tests
│   └── utils/              # Utils tests
├── integration/            # Integration tests
│   ├── backends/           # Backend integration
│   ├── workflows/          # E2E workflows
│   └── fixtures/           # Test fixtures
├── regression/             # Regression tests
├── performance/            # Performance benchmarks
├── manual/                 # Manual test docs
├── test_backends/          # Legacy backend tests
├── conftest.py             # Pytest fixtures
└── README.md               # Testing documentation
```

### Other Directories

```
config/                     # Plugin configuration
├── config.json             # Active configuration
├── config.default.json     # Defaults
├── config.py               # Configuration loader
└── config.v2.example.json  # V2 format example

docs/                       # Documentation
├── fixes/                  # Bug fix documentation
└── archive/                # Historical docs

tools/                      # Development utilities (NOT packaged)
├── i18n/                   # Translation tools
└── ui/                     # UI tools

i18n/                       # Translations (21 languages)
resources/                  # Static resources (QSS themes)
icons/                      # Plugin icons
website/                    # Docusaurus website
utils/                      # Python utilities
├── deprecation.py
├── type_utils.py

before_migration/           # ARCHIVED: Legacy modules/ code
├── modules/                # Old structure (preserved)
└── ARCHIVE_NOTICE.md

_bmad/                      # BMAD methodology
└── bmm/, core/, _config/

_bmad-output/               # BMAD outputs
.serena/                    # Serena MCP config
.github/                    # GitHub config
```

## File Statistics Summary

| Category | Files | Lines | Description |
|----------|-------|-------|-------------|
| Core | ~50 | ~28,000 | Tasks, services, domain |
| Adapters | ~40 | ~15,000 | Backends, QGIS, repos |
| Infrastructure | ~25 | ~8,000 | Cache, DB, utils |
| UI | ~45 | ~15,000 | Controllers, widgets |
| Root | ~10 | ~8,300 | Entry points |
| **Subtotal** | **~170** | **~74,300** | Runtime code |
| Tests | 157 | ~47,600 | Test suite |
| **Total** | **~327** | **~122,000** | All Python |

## Notes

1. **Hexagonal complete**: Core isolated from external concerns
2. **modules/ archived**: Migrated to `before_migration/`
3. **tools/ not packaged**: Development utilities only
4. **21 languages**: Full i18n support
5. **157 test files**: Comprehensive coverage