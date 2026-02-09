"""
Pytest configuration and fixtures for FilterMate tests.

This module provides common test fixtures and configuration
for the FilterMate plugin test suite.
"""
import pytest
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def plugin_dir_path():
    """Return the plugin directory path."""
    return str(plugin_dir)


@pytest.fixture
def mock_iface():
    """
    Mock QGIS iface object.
    
    Returns a mock object that simulates the QGIS interface
    for testing without a full QGIS environment.
    """
    from unittest.mock import Mock, MagicMock
    
    iface = Mock()
    iface.mainWindow.return_value = Mock()
    iface.addDockWidget = Mock()
    iface.removeDockWidget = Mock()
    iface.messageBar.return_value = Mock()
    iface.mapCanvas.return_value = Mock()
    iface.activeLayer.return_value = None
    iface.addToolBar = Mock()
    iface.pluginMenu.return_value = Mock()
    
    return iface


@pytest.fixture
def mock_qgs_project():
    """
    Mock QgsProject instance.
    
    Returns a mock QGIS project for testing.
    """
    from unittest.mock import Mock
    
    project = Mock()
    project.instance.return_value = project
    project.mapLayers.return_value = {}
    project.readPath.return_value = './'
    project.fileName.return_value = ''
    
    return project


@pytest.fixture
def sample_layer_metadata():
    """Return sample layer metadata for testing."""
    return {
        'id': 'test_layer_123',
        'name': 'Test Layer',
        'provider_type': 'spatialite',
        'feature_count': 100,
        'geometry_type': 'Point',
        'crs': 'EPSG:4326'
    }


@pytest.fixture
def sample_filter_params():
    """Return sample filter parameters for testing."""
    return {
        'layer_id': 'test_layer_123',
        'attribute_expression': 'population > 10000',
        'spatial_predicates': ['intersects'],
        'buffer_distance': 100.0,
        'buffer_unit': 'meters',
        'combine_operator': 'AND'
    }


# === Hexagonal Services Fixtures ===

@pytest.fixture
def mock_qgs_vector_layer():
    """
    Create a mock QgsVectorLayer for testing.
    
    Provides a fully configured mock layer with all common methods.
    """
    from unittest.mock import Mock
    
    layer = Mock()
    layer.id.return_value = "test_layer_123"
    layer.name.return_value = "Test Layer"
    layer.isValid.return_value = True
    layer.providerType.return_value = "ogr"
    layer.geometryType.return_value = 2  # Polygon
    layer.subsetString.return_value = ""
    layer.featureCount.return_value = 100
    layer.setSubsetString = Mock(return_value=True)
    layer.dataProvider.return_value = Mock()
    layer.reload = Mock()
    layer.triggerRepaint = Mock()
    
    # CRS
    crs = Mock()
    crs.authid.return_value = "EPSG:4326"
    crs.isGeographic.return_value = True
    layer.crs.return_value = crs
    
    # Fields
    layer.fields.return_value = Mock()
    layer.primaryKeyAttributes.return_value = [0]
    
    return layer


@pytest.fixture
def mock_postgresql_layer(mock_qgs_vector_layer):
    """Create a mock PostgreSQL layer."""
    layer = mock_qgs_vector_layer
    layer.providerType.return_value = "postgres"
    return layer


@pytest.fixture
def mock_spatialite_layer(mock_qgs_vector_layer):
    """Create a mock Spatialite layer."""
    layer = mock_qgs_vector_layer
    layer.providerType.return_value = "spatialite"
    return layer


@pytest.fixture
def mock_postgresql_connection():
    """
    Create a mock PostgreSQL connection.
    
    Simulates psycopg2 connection for testing without database.
    """
    from unittest.mock import Mock, MagicMock
    
    conn = Mock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    cursor.execute = Mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()
    
    return conn


@pytest.fixture
def layer_lifecycle_service():
    """Create a LayerLifecycleService instance for testing."""
    from core.services.layer_lifecycle_service import LayerLifecycleService, LayerLifecycleConfig
    
    config = LayerLifecycleConfig(
        postgresql_temp_schema="test_schema",
        auto_cleanup_enabled=True,
        signal_debounce_ms=10,  # Fast for tests
        max_postgresql_retries=1
    )
    return LayerLifecycleService(config=config)


@pytest.fixture
def task_management_service():
    """Create a TaskOrchestrator instance for testing (formerly TaskManagementService).

    Phase 5 consolidation: TaskManagementService merged into TaskOrchestrator.
    Fixture name kept for backward compatibility with existing tests.
    """
    from unittest.mock import Mock
    from core.services.task_orchestrator import TaskOrchestrator

    return TaskOrchestrator(
        get_dockwidget=Mock(return_value=None),
        get_project_layers=Mock(return_value={}),
        get_config_data=Mock(return_value={}),
        get_project=Mock(return_value=None),
        check_reset_stale_flags=Mock(),
        set_loading_flag=Mock(),
        set_initializing_flag=Mock(),
        get_task_parameters=Mock(return_value=None),
        handle_filter_task=Mock(),
        handle_layer_task=Mock(),
        handle_undo=Mock(),
        handle_redo=Mock(),
        force_reload_layers=Mock(),
        handle_remove_all_layers=Mock(),
        handle_project_initialization=Mock(),
    )


@pytest.fixture
def task_parameter_builder():
    """Create a TaskParameterBuilder instance for testing."""
    from adapters.task_builder import TaskParameterBuilder
    from unittest.mock import Mock
    
    # Create mock dockwidget with required widgets
    dw = Mock()
    dw.mQgsDoubleSpinBox_filtering_buffer_value = Mock()
    dw.mQgsDoubleSpinBox_filtering_buffer_value.value.return_value = 0.0
    dw.mQgsSpinBox_filtering_buffer_segments = Mock()
    dw.mQgsSpinBox_filtering_buffer_segments.value.return_value = 5
    dw.comboBox_filtering_buffer_type = Mock()
    dw.comboBox_filtering_buffer_type.currentText.return_value = "Round"
    dw.pushButton_checkable_filtering_geometric_predicates = Mock()
    dw.pushButton_checkable_filtering_geometric_predicates.isChecked.return_value = False
    # FIX: Use comboBox_filtering_geometric_predicates with checkedItems() (QgsCheckableComboBox)
    dw.comboBox_filtering_geometric_predicates = Mock()
    dw.comboBox_filtering_geometric_predicates.checkedItems.return_value = []
    dw.pushButton_checkable_filtering_layers_to_filter = Mock()
    dw.pushButton_checkable_filtering_layers_to_filter.isChecked.return_value = False
    dw.get_layers_to_filter = Mock(return_value=[])
    dw.checkBox_filtering_use_centroids_source_layer = Mock()
    dw.checkBox_filtering_use_centroids_source_layer.isChecked.return_value = False
    dw.checkBox_filtering_use_centroids_distant_layers = Mock()
    dw.checkBox_filtering_use_centroids_distant_layers.isChecked.return_value = False
    dw.forced_backends = {}
    
    return TaskParameterBuilder(dw, {})


@pytest.fixture
def sample_project_layers():
    """Return sample PROJECT_LAYERS dictionary for testing."""
    return {
        'layer_123': {
            'layer': None,  # Would be actual layer in real code
            'infos': {
                'layer_provider_type': 'postgresql',
                'layer_table_name': 'test_table',
                'layer_schema': 'public',
                'layer_geometry_field': 'geom',
                'layer_primary_key_name': 'gid'
            },
            'filtering': {
                'is_already_subset': False,
                'old_subset_string': ''
            }
        },
        'layer_456': {
            'layer': None,
            'infos': {
                'layer_provider_type': 'spatialite',
                'layer_table_name': 'other_table',
                'layer_geometry_field': 'geometry'
            },
            'filtering': {}
        }
    }


# === Test Markers ===

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower, multiple components)")
    config.addinivalue_line("markers", "postgres: Tests requiring PostgreSQL")
    config.addinivalue_line("markers", "slow: Slow tests")
