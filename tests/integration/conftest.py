# -*- coding: utf-8 -*-
"""
Integration Test Configuration - ARCH-049

Provides shared fixtures and utilities for integration testing
of the FilterMate v3.0 architecture.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "postgresql: PostgreSQL backend tests")
    config.addinivalue_line("markers", "spatialite: Spatialite backend tests")
    config.addinivalue_line("markers", "ogr: OGR backend tests")
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
    config.addinivalue_line("markers", "regression: Regression tests for known issues")
    config.addinivalue_line("markers", "slow: Slow running tests")
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, Optional, List
import uuid
import time


# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(plugin_dir))


# ============================================================================
# Mock QGIS Environment
# ============================================================================

@pytest.fixture
def mock_qgis_interface():
    """Create a mock QGIS interface for testing."""
    iface = MagicMock()
    iface.mapCanvas.return_value = MagicMock()
    iface.mainWindow.return_value = MagicMock()
    iface.messageBar.return_value = MagicMock()
    iface.activeLayer.return_value = None
    iface.addDockWidget = MagicMock()
    iface.removeDockWidget = MagicMock()
    return iface


@pytest.fixture
def mock_qgis_project():
    """Create a mock QGIS project for testing."""
    project = MagicMock()
    project.mapLayers.return_value = {}
    project.readPath.return_value = './'
    project.fileName.return_value = 'test_project.qgz'
    project.crs.return_value = MagicMock(authid=lambda: 'EPSG:4326')
    return project


# ============================================================================
# Mock Backend Fixtures
# ============================================================================

@pytest.fixture
def mock_postgresql_backend():
    """Create a mock PostgreSQL backend."""
    backend = MagicMock()
    backend.name = "PostgreSQL"
    backend.get_priority.return_value = 100
    backend.supports_mv.return_value = True
    backend.supports_spatial.return_value = True
    
    # Mock info
    backend.get_info.return_value = MagicMock(
        name="PostgreSQL",
        priority=100,
        provider_types=["postgres", "postgresql"],
        capabilities=["mv_optimization", "spatial", "connection_pool"]
    )
    
    # Mock execution
    backend.execute.return_value = MagicMock(
        success=True,
        matched_count=100,
        feature_ids=[i for i in range(100)],
        execution_time_ms=25.0,
        used_optimization=True
    )
    
    return backend


@pytest.fixture
def mock_spatialite_backend():
    """Create a mock Spatialite backend."""
    backend = MagicMock()
    backend.name = "Spatialite"
    backend.get_priority.return_value = 50
    backend.supports_rtree.return_value = True
    backend.supports_spatial.return_value = True
    
    # Mock info
    backend.get_info.return_value = MagicMock(
        name="Spatialite",
        priority=50,
        provider_types=["spatialite", "ogr"],  # OGR for GeoPackage
        capabilities=["rtree", "spatial", "cache"]
    )
    
    # Mock execution
    backend.execute.return_value = MagicMock(
        success=True,
        matched_count=100,
        feature_ids=[i for i in range(100)],
        execution_time_ms=50.0,
        used_optimization=True
    )
    
    return backend


@pytest.fixture
def mock_ogr_backend():
    """Create a mock OGR backend."""
    backend = MagicMock()
    backend.name = "OGR"
    backend.get_priority.return_value = 10
    backend.supports_spatial.return_value = True
    
    # Mock info
    backend.get_info.return_value = MagicMock(
        name="OGR",
        priority=10,
        provider_types=["ogr", "memory"],
        capabilities=["universal"]
    )
    
    # Mock execution
    backend.execute.return_value = MagicMock(
        success=True,
        matched_count=100,
        feature_ids=[i for i in range(100)],
        execution_time_ms=150.0,
        used_optimization=False
    )
    
    return backend


@pytest.fixture
def mock_memory_backend():
    """Create a mock memory backend."""
    backend = MagicMock()
    backend.name = "Memory"
    backend.get_priority.return_value = 5
    backend.supports_spatial.return_value = True
    
    # Mock info
    backend.get_info.return_value = MagicMock(
        name="Memory",
        priority=5,
        provider_types=["memory"],
        capabilities=["fast"]
    )
    
    # Mock execution
    backend.execute.return_value = MagicMock(
        success=True,
        matched_count=50,
        feature_ids=[i for i in range(50)],
        execution_time_ms=5.0,
        used_optimization=False
    )
    
    return backend


@pytest.fixture
def all_mock_backends(
    mock_postgresql_backend,
    mock_spatialite_backend,
    mock_ogr_backend,
    mock_memory_backend
):
    """Return all mock backends for cross-backend testing."""
    return {
        "postgresql": mock_postgresql_backend,
        "spatialite": mock_spatialite_backend,
        "ogr": mock_ogr_backend,
        "memory": mock_memory_backend
    }


# ============================================================================
# Mock Layer Fixtures
# ============================================================================

def create_mock_layer(
    layer_id: Optional[str] = None,
    name: str = "Test Layer",
    provider_type: str = "ogr",
    feature_count: int = 1000,
    geometry_type: str = "Polygon",
    crs: str = "EPSG:4326",
    subset_string: str = ""
) -> MagicMock:
    """
    Factory function to create mock QGIS vector layers.
    
    Args:
        layer_id: Unique layer ID (auto-generated if None)
        name: Layer name
        provider_type: Provider type (ogr, postgres, spatialite, memory)
        feature_count: Number of features
        geometry_type: Geometry type
        crs: CRS authority ID
        subset_string: Initial subset string
        
    Returns:
        Mock QgsVectorLayer
    """
    layer = MagicMock()
    layer.id.return_value = layer_id or f"layer_{uuid.uuid4().hex[:8]}"
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.providerType.return_value = provider_type
    layer.featureCount.return_value = feature_count
    layer.wkbType.return_value = 3  # Polygon
    
    # CRS mock
    crs_mock = MagicMock()
    crs_mock.authid.return_value = crs
    crs_mock.isValid.return_value = True
    layer.crs.return_value = crs_mock
    
    # Subset string
    layer._subset_string = subset_string
    layer.subsetString.return_value = subset_string
    
    def set_subset(expr):
        layer._subset_string = expr
        layer.subsetString.return_value = expr
        return True
    layer.setSubsetString.side_effect = set_subset
    
    # Fields mock
    fields_mock = MagicMock()
    fields_mock.names.return_value = ["id", "name", "population", "area"]
    layer.fields.return_value = fields_mock
    
    # Provider mock
    provider_mock = MagicMock()
    provider_mock.name.return_value = provider_type
    layer.dataProvider.return_value = provider_mock
    
    return layer


@pytest.fixture
def sample_vector_layer(mock_qgis_interface):
    """Create a sample vector layer for testing."""
    return create_mock_layer(
        layer_id="test_layer_001",
        name="Test Layer",
        provider_type="ogr",
        feature_count=1000
    )


@pytest.fixture
def postgresql_layer():
    """Create a mock PostgreSQL layer."""
    layer = create_mock_layer(
        layer_id="postgresql_layer_001",
        name="PostgreSQL Layer",
        provider_type="postgres",
        feature_count=50000
    )
    
    # Add PostgreSQL-specific properties
    uri_mock = MagicMock()
    uri_mock.database.return_value = "test_db"
    uri_mock.host.return_value = "localhost"
    uri_mock.port.return_value = "5432"
    uri_mock.schema.return_value = "public"
    uri_mock.table.return_value = "test_table"
    uri_mock.geometryColumn.return_value = "geom"
    uri_mock.keyColumn.return_value = "gid"
    layer.dataProvider.return_value.uri.return_value = uri_mock
    
    return layer


@pytest.fixture
def spatialite_layer():
    """Create a mock Spatialite layer."""
    return create_mock_layer(
        layer_id="spatialite_layer_001",
        name="Spatialite Layer",
        provider_type="spatialite",
        feature_count=10000
    )


@pytest.fixture
def ogr_layer():
    """Create a mock OGR layer (Shapefile)."""
    return create_mock_layer(
        layer_id="ogr_layer_001",
        name="Shapefile Layer",
        provider_type="ogr",
        feature_count=5000
    )


@pytest.fixture
def memory_layer():
    """Create a mock memory layer."""
    return create_mock_layer(
        layer_id="memory_layer_001",
        name="Memory Layer",
        provider_type="memory",
        feature_count=500
    )


@pytest.fixture
def large_postgresql_layer():
    """Create a large PostgreSQL layer for performance testing."""
    return create_mock_layer(
        layer_id="large_postgresql_layer",
        name="Large PostgreSQL Layer",
        provider_type="postgres",
        feature_count=100000
    )


@pytest.fixture
def empty_layer():
    """Create an empty layer for edge case testing."""
    return create_mock_layer(
        layer_id="empty_layer_001",
        name="Empty Layer",
        provider_type="ogr",
        feature_count=0
    )


@pytest.fixture
def layer_with_null_geometry():
    """Create a layer with features that have NULL geometry."""
    layer = create_mock_layer(
        layer_id="null_geom_layer",
        name="Layer with NULL Geometry",
        feature_count=100
    )
    layer.hasNullGeometry = MagicMock(return_value=True)
    return layer


@pytest.fixture
def multiple_layers():
    """Create multiple layers for concurrent testing."""
    return [
        create_mock_layer(f"layer_{i}", f"Layer {i}")
        for i in range(5)
    ]


@pytest.fixture
def test_layers_per_backend(
    postgresql_layer,
    spatialite_layer,
    ogr_layer,
    memory_layer
):
    """Return test layers organized by backend type."""
    return {
        "postgresql": postgresql_layer,
        "spatialite": spatialite_layer,
        "ogr": ogr_layer,
        "memory": memory_layer
    }


# ============================================================================
# Expression Fixtures
# ============================================================================

@pytest.fixture
def basic_attribute_expression():
    """Return a basic attribute filter expression."""
    return '"population" > 10000'


@pytest.fixture
def spatial_expression():
    """Return a spatial filter expression."""
    return 'intersects($geometry, @filter_geometry)'


@pytest.fixture
def complex_expression():
    """Return a complex combined expression."""
    return '("population" > 10000 AND "area" > 100) OR "name" LIKE \'%ville%\''


@pytest.fixture
def test_expressions():
    """Return a variety of test expressions."""
    return {
        "simple_comparison": '"population" > 10000',
        "string_match": '"name" LIKE \'%ville%\'',
        "range_filter": '"area" BETWEEN 100 AND 500',
        "null_check": '"name" IS NOT NULL',
        "in_list": '"category" IN (\'A\', \'B\', \'C\')',
        "spatial_intersects": 'intersects($geometry, @filter_geometry)',
        "spatial_within": 'within($geometry, @filter_geometry)',
        "spatial_contains": 'contains($geometry, @filter_geometry)',
        "combined": '"population" > 5000 AND intersects($geometry, @filter_geometry)'
    }


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest.fixture
def mock_filter_service():
    """Create a mock FilterService."""
    service = MagicMock()
    service.apply_filter.return_value = MagicMock(
        success=True,
        matched_count=100,
        execution_time_ms=50.0
    )
    service.can_apply_filter.return_value = True
    return service


@pytest.fixture
def mock_export_service():
    """Create a mock ExportService."""
    service = MagicMock()
    service.export_layer.return_value = MagicMock(
        success=True,
        feature_count=100,
        output_path="/tmp/export.gpkg"
    )
    return service


@pytest.fixture
def mock_history_service():
    """Create a mock HistoryService."""
    service = MagicMock()
    service.can_undo.return_value = False
    service.can_redo.return_value = False
    service.undo.return_value = MagicMock(success=True)
    service.redo.return_value = MagicMock(success=True)
    return service


# ============================================================================
# Controller Fixtures
# ============================================================================

@pytest.fixture
def mock_dockwidget():
    """Create a mock dockwidget with all required attributes."""
    dockwidget = MagicMock()
    
    # Mock tabTools
    dockwidget.tabTools = MagicMock()
    dockwidget.tabTools.currentChanged = MagicMock()
    dockwidget.tabTools.currentChanged.connect = MagicMock()
    dockwidget.tabTools.currentChanged.disconnect = MagicMock()
    
    # Mock signals
    dockwidget.currentLayerChanged = MagicMock()
    dockwidget.currentLayerChanged.connect = MagicMock()
    dockwidget.currentLayerChanged.disconnect = MagicMock()
    
    # Mock state
    dockwidget.current_layer = None
    dockwidget._exploring_cache = MagicMock()
    
    # Mock UI elements
    dockwidget.comboBox_filtering_current_layer = MagicMock()
    dockwidget.comboBox_exporting_current_layer = MagicMock()
    dockwidget.pushButton_apply_filter = MagicMock()
    dockwidget.pushButton_clear_filter = MagicMock()
    
    return dockwidget


# ============================================================================
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def create_feature_ids(count: int, start: int = 0) -> List[int]:
        """Generate a list of feature IDs."""
        return list(range(start, start + count))
    
    @staticmethod
    def create_layer_metadata(
        layer_id: str = "test_layer",
        provider: str = "ogr",
        feature_count: int = 1000
    ) -> Dict[str, Any]:
        """Create layer metadata dictionary."""
        return {
            "id": layer_id,
            "name": f"Layer_{layer_id}",
            "provider_type": provider,
            "feature_count": feature_count,
            "geometry_type": "Polygon",
            "crs": "EPSG:4326"
        }
    
    @staticmethod
    def create_filter_config(
        expression: str = '"population" > 10000',
        buffer: float = 0.0,
        predicate: str = "intersects"
    ) -> Dict[str, Any]:
        """Create filter configuration dictionary."""
        return {
            "expression": expression,
            "buffer_distance": buffer,
            "spatial_predicate": predicate,
            "combine_operator": "AND",
            "target_layers": []
        }


@pytest.fixture
def test_data_generator():
    """Provide test data generator."""
    return TestDataGenerator()


# ============================================================================
# Timing Utilities
# ============================================================================

class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        return False


@pytest.fixture
def timing_context():
    """Provide timing context for performance measurements."""
    return TimingContext


# ============================================================================
# Pytest Markers
# ============================================================================

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "postgresql: mark test as PostgreSQL-specific"
    )
    config.addinivalue_line(
        "markers", "spatialite: mark test as Spatialite-specific"
    )
    config.addinivalue_line(
        "markers", "ogr: mark test as OGR-specific"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "benchmark: mark test as performance benchmark"
    )
    config.addinivalue_line(
        "markers", "regression: mark test as regression test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
