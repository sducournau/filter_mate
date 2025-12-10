"""
Test plugin loading and initialization.

These smoke tests verify that the plugin can be loaded
and its basic structure is correct.
"""
import pytest
from unittest.mock import Mock, patch


def test_plugin_module_imports():
    """Test that core plugin modules can be imported."""
    # Should not raise ImportError
    import filter_mate
    from filter_mate import FilterMate
    
    assert FilterMate is not None
    assert hasattr(FilterMate, '__init__')


def test_plugin_has_required_methods():
    """Test that plugin has required QGIS methods."""
    from filter_mate import FilterMate
    
    # Required methods for QGIS plugins
    assert hasattr(FilterMate, 'initGui'), "Missing initGui method"
    assert hasattr(FilterMate, 'unload'), "Missing unload method"
    assert callable(FilterMate.initGui)
    assert callable(FilterMate.unload)


def test_plugin_instantiation(mock_iface):
    """Test that plugin can be instantiated."""
    from filter_mate import FilterMate
    
    # Should not raise exception
    plugin = FilterMate(mock_iface)
    
    assert plugin is not None
    assert plugin.iface == mock_iface
    assert hasattr(plugin, 'actions')
    assert isinstance(plugin.actions, list)


def test_plugin_has_metadata():
    """Test that plugin directory has metadata.txt."""
    from pathlib import Path
    
    plugin_dir = Path(__file__).parent.parent
    metadata_file = plugin_dir / 'metadata.txt'
    
    assert metadata_file.exists(), "metadata.txt not found"
    
    # Check metadata content
    content = metadata_file.read_text()
    assert 'name=' in content
    assert 'version=' in content
    assert 'qgisMinimumVersion=' in content


def test_config_module_imports():
    """Test that config module can be imported."""
    from config import config
    
    assert hasattr(config, 'init_env_vars')
    assert hasattr(config, 'load_default_config')
    assert hasattr(config, 'save_config')


def test_postgresql_availability_flag():
    """Test that POSTGRESQL_AVAILABLE flag is properly set."""
    from modules.appUtils import POSTGRESQL_AVAILABLE
    
    # Should be boolean
    assert isinstance(POSTGRESQL_AVAILABLE, bool)


@pytest.mark.parametrize("module_name", [
    "modules.appTasks",
    "modules.appUtils",
    "modules.constants",
    "modules.customExceptions",
    "modules.filter_history",
    "modules.signal_utils",
])
def test_core_modules_import(module_name):
    """Test that core modules can be imported."""
    import importlib
    
    # Should not raise ImportError
    module = importlib.import_module(module_name)
    assert module is not None


def test_backend_modules_import():
    """Test that backend modules can be imported."""
    from modules.backends import base_backend
    from modules.backends import spatialite_backend
    from modules.backends import ogr_backend
    
    assert hasattr(base_backend, 'BaseBackend')
    assert hasattr(spatialite_backend, 'SpatialiteBackend')
    assert hasattr(ogr_backend, 'OGRBackend')


def test_constants_defined():
    """Test that required constants are defined."""
    from modules.constants import (
        PROVIDER_POSTGRES,
        PROVIDER_SPATIALITE,
        PROVIDER_OGR
    )
    
    assert PROVIDER_POSTGRES is not None
    assert PROVIDER_SPATIALITE is not None
    assert PROVIDER_OGR is not None
