# -*- coding: utf-8 -*-
"""
Conftest for core/tasks handler tests.

Pre-mocks the deep import chains so individual handler modules can be
imported without pulling in the entire QGIS/plugin dependency tree.

The handlers use relative imports like:
    from ...infrastructure.logging import setup_logger

From core/tasks/handler.py, '...' resolves 3 levels up:
    core.tasks.handler -> core.tasks -> core -> (root = filter_mate)

So '...infrastructure' resolves to 'filter_mate.infrastructure'.
Since pytest runs from the filter_mate directory as CWD, we need
a parent 'filter_mate' package that contains 'core', 'infrastructure',
'config', 'adapters', etc.

Strategy:
    1. Create a 'filter_mate' package in sys.modules as parent of 'core'
    2. Mock all submodules under filter_mate (infrastructure, config, etc.)
    3. Load handler modules with proper package hierarchy
"""
import sys
import types
import os
from unittest.mock import MagicMock


def _create_package(name, parent=None):
    """Create a real module/package object and register in sys.modules."""
    mod = types.ModuleType(name)
    mod.__path__ = []
    mod.__package__ = name
    sys.modules[name] = mod
    if parent and hasattr(sys.modules.get(parent), '__dict__'):
        short_name = name.rsplit('.', 1)[-1]
        setattr(sys.modules[parent], short_name, mod)
    return mod


def _setup_handler_mocks():
    """Install all mocks needed for handler imports."""
    if getattr(_setup_handler_mocks, '_done', False):
        return
    _setup_handler_mocks._done = True

    # Logger and ENV mocks
    mock_logger = MagicMock()
    mock_setup_logger = MagicMock(return_value=mock_logger)
    mock_env_vars = {"PATH_ABSOLUTE_PROJECT": "/tmp/filtermate_test"}  # nosec B108

    # Constants mock with real values
    mock_constants = MagicMock()
    mock_constants.PROVIDER_POSTGRES = 'postgresql'
    mock_constants.PROVIDER_SPATIALITE = 'spatialite'
    mock_constants.PROVIDER_OGR = 'ogr'
    mock_constants.PROVIDER_MEMORY = 'memory'
    mock_constants.PROVIDER_VIRTUAL = 'virtual'

    # Backend services mock
    mock_bs_instance = MagicMock()
    mock_get_bs = MagicMock(return_value=mock_bs_instance)

    # HistoryRepository as a real class (not instance)
    MockHistoryRepo = type('HistoryRepository', (), {
        '__init__': lambda self, conn, cur: None,
        'insert': MagicMock(return_value=True),
        'delete_for_layer': MagicMock(return_value=True),
        'delete_entry': MagicMock(return_value=True),
        'get_last_entry': MagicMock(return_value=None),
        'close': lambda self: None,
    })

    # ---------------------------------------------------------------
    # Create the filter_mate package hierarchy
    # ---------------------------------------------------------------
    # We need: filter_mate -> core -> tasks -> handler.py
    # And:     filter_mate -> infrastructure, config, adapters, etc.

    ROOT = 'filter_mate'

    # Create filter_mate root package
    _create_package(ROOT)

    # Create core hierarchy under filter_mate
    _create_package(f'{ROOT}.core')
    _create_package(f'{ROOT}.core.tasks', f'{ROOT}.core')

    # Also ensure 'core' at top level points to filter_mate.core
    if 'core' not in sys.modules or isinstance(sys.modules['core'], MagicMock):
        sys.modules['core'] = sys.modules[f'{ROOT}.core']
    if 'core.tasks' not in sys.modules or isinstance(sys.modules['core.tasks'], MagicMock):
        sys.modules['core.tasks'] = sys.modules[f'{ROOT}.core.tasks']
        sys.modules['core'].tasks = sys.modules['core.tasks']

    # ---------------------------------------------------------------
    # Mock all modules under filter_mate.* that handlers import
    # via relative imports (from ...X import Y)
    # ---------------------------------------------------------------
    fm_modules = {
        # infrastructure
        f'{ROOT}.infrastructure': MagicMock(),
        f'{ROOT}.infrastructure.logging': MagicMock(setup_logger=mock_setup_logger),
        f'{ROOT}.infrastructure.constants': mock_constants,
        f'{ROOT}.infrastructure.utils': MagicMock(
            detect_layer_provider_type=MagicMock(return_value='ogr'),
            get_spatialite_datasource_from_layer=MagicMock(return_value=(None, None)),
        ),
        f'{ROOT}.infrastructure.streaming': MagicMock(),
        f'{ROOT}.infrastructure.database': MagicMock(),
        f'{ROOT}.infrastructure.database.prepared_statements': MagicMock(
            create_prepared_statements=MagicMock(return_value=None),
        ),

        # config
        f'{ROOT}.config': MagicMock(),
        f'{ROOT}.config.config': MagicMock(ENV_VARS=mock_env_vars),

        # core sub-packages
        f'{ROOT}.core.ports': MagicMock(),
        f'{ROOT}.core.ports.backend_services': MagicMock(
            get_backend_services=mock_get_bs,
            BackendServices=MagicMock(),
        ),
        f'{ROOT}.core.export': MagicMock(),
        f'{ROOT}.core.export.style_exporter': MagicMock(),
        f'{ROOT}.core.services': MagicMock(),
        f'{ROOT}.core.services.buffer_service': MagicMock(),
        f'{ROOT}.core.services.filter_parameter_builder': MagicMock(),
        f'{ROOT}.core.services.source_subset_buffer_builder': MagicMock(),
        f'{ROOT}.core.services.geometry_preparer': MagicMock(),
        f'{ROOT}.core.geometry': MagicMock(),
        f'{ROOT}.core.geometry.crs_utils': MagicMock(
            is_geographic_crs=MagicMock(return_value=False),
            is_metric_crs=MagicMock(return_value=True),
            get_optimal_metric_crs=MagicMock(return_value='EPSG:2154'),
            get_layer_crs_info=MagicMock(return_value={}),
        ),
        f'{ROOT}.core.geometry.spatial_index': MagicMock(),
        f'{ROOT}.core.geometry.buffer_processor': MagicMock(),
        f'{ROOT}.core.optimization': MagicMock(),
        f'{ROOT}.core.optimization.config_provider': MagicMock(),
        f'{ROOT}.core.backends': MagicMock(),
        f'{ROOT}.core.backends.auto_optimizer': MagicMock(),

        # adapters
        f'{ROOT}.adapters': MagicMock(),
        f'{ROOT}.adapters.repositories': MagicMock(),
        f'{ROOT}.adapters.repositories.history_repository': MagicMock(
            HistoryRepository=MockHistoryRepo,
        ),
        f'{ROOT}.adapters.backends': MagicMock(),
        f'{ROOT}.adapters.backends.postgresql': MagicMock(),
        f'{ROOT}.adapters.backends.postgresql.mv_reference_tracker': MagicMock(),
        f'{ROOT}.adapters.backends.spatialite': MagicMock(),
        f'{ROOT}.adapters.backends.ogr': MagicMock(),

        # tasks sub-modules
        f'{ROOT}.core.tasks.builders': MagicMock(),
        f'{ROOT}.core.tasks.builders.subset_string_builder': MagicMock(),
    }

    for mod_name, mock_obj in fm_modules.items():
        if mod_name not in sys.modules:
            sys.modules[mod_name] = mock_obj

    # ---------------------------------------------------------------
    # Load handler modules using importlib with proper __package__
    # ---------------------------------------------------------------
    import importlib.util

    handler_dir = os.path.join(
        os.path.dirname(__file__),
        '..', '..', '..', '..', 'core', 'tasks'
    )
    handler_dir = os.path.normpath(handler_dir)

    handler_files = [
        'cleanup_handler',
        'export_handler',
        'geometry_handler',
        'initialization_handler',
        'source_geometry_preparer',
        'subset_management_handler',
    ]

    for handler_name in handler_files:
        fm_module_name = f'{ROOT}.core.tasks.{handler_name}'
        short_module_name = f'core.tasks.{handler_name}'

        if fm_module_name in sys.modules and not isinstance(sys.modules[fm_module_name], MagicMock):
            # Already loaded as a real module
            sys.modules[short_module_name] = sys.modules[fm_module_name]
            continue

        file_path = os.path.join(handler_dir, f'{handler_name}.py')
        if not os.path.exists(file_path):
            continue

        spec = importlib.util.spec_from_file_location(
            fm_module_name,
            file_path,
            submodule_search_locations=[],
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            module.__package__ = f'{ROOT}.core.tasks'
            sys.modules[fm_module_name] = module
            sys.modules[short_module_name] = module  # alias
            try:
                spec.loader.exec_module(module)
                # Also set as attribute on the tasks package
                setattr(sys.modules[f'{ROOT}.core.tasks'], handler_name, module)
                setattr(sys.modules['core.tasks'], handler_name, module)
            except Exception as e:
                sys.modules[fm_module_name] = MagicMock()
                sys.modules[short_module_name] = MagicMock()
                import warnings
                warnings.warn(
                    f"Could not load handler {handler_name}: {e}",
                    stacklevel=2,
                )


# Run at import time
_setup_handler_mocks()
