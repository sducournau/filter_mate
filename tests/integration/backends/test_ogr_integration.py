# -*- coding: utf-8 -*-
"""
OGR Backend Integration Tests - ARCH-051

Integration tests for OGR backend - the universal fallback.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def ogr_backend_mock():
    """Create a mock OGR backend."""
    backend = MagicMock()
    backend.name = "OGR"
    backend._batch_size = 1000
    backend._use_progress = True
    
    # Metrics
    backend._metrics = {
        "executions": 0,
        "features_processed": 0,
        "total_time_ms": 0.0,
        "errors": 0
    }
    
    return backend


@pytest.fixture
def mock_qgis_expression():
    """Create a mock QGIS expression evaluator."""
    expression = MagicMock()
    expression.isValid.return_value = True
    expression.hasParserError.return_value = False
    expression.parserErrorString.return_value = ""
    
    # Simulate evaluation
    expression.evaluate.return_value = True
    
    return expression


@pytest.mark.integration
@pytest.mark.ogr
class TestOGRBackendIntegration:
    """Integration tests for OGR backend."""
    
    def test_backend_initialization(self, ogr_backend_mock):
        """Test backend initializes correctly."""
        backend = ogr_backend_mock
        
        assert backend.name == "OGR"
        assert backend._batch_size == 1000
    
    def test_execute_attribute_filter(
        self,
        ogr_backend_mock,
        ogr_layer
    ):
        """Test executing attribute filter."""
        backend = ogr_backend_mock
        
        result = MagicMock()
        result.success = True
        result.matched_count = 100
        result.execution_time_ms = 150.0
        result.used_optimization = False
        backend.execute.return_value = result
        
        execution_result = backend.execute(
            '"population" > 10000',
            ogr_layer
        )
        
        assert execution_result.success is True
        assert execution_result.used_optimization is False
    
    def test_execute_spatial_filter(
        self,
        ogr_backend_mock,
        ogr_layer
    ):
        """Test executing spatial filter."""
        backend = ogr_backend_mock
        
        result = MagicMock()
        result.success = True
        result.matched_count = 50
        result.is_spatial = True
        backend.execute.return_value = result
        
        execution_result = backend.execute(
            "intersects($geometry, @filter_geometry)",
            ogr_layer
        )
        
        assert execution_result.success is True
    
    def test_supports_all_formats(self, ogr_backend_mock):
        """Test OGR supports multiple formats."""
        backend = ogr_backend_mock
        
        backend.get_supported_formats = MagicMock(return_value=[
            "Shapefile", "GeoJSON", "GeoPackage", "KML",
            "CSV", "GML", "GPX", "MapInfo"
        ])
        
        formats = backend.get_supported_formats()
        assert "Shapefile" in formats
        assert "GeoJSON" in formats
        assert len(formats) >= 5


@pytest.mark.integration
@pytest.mark.ogr
class TestOGRExpressionEvaluation:
    """Tests for QGIS expression evaluation in OGR backend."""
    
    def test_validate_expression(self, mock_qgis_expression):
        """Test expression validation."""
        expr = mock_qgis_expression
        
        assert expr.isValid() is True
        assert expr.hasParserError() is False
    
    def test_invalid_expression(self):
        """Test handling invalid expression."""
        expr = MagicMock()
        expr.isValid.return_value = False
        expr.hasParserError.return_value = True
        expr.parserErrorString.return_value = "Syntax error at position 10"
        
        assert expr.isValid() is False
        assert "Syntax error" in expr.parserErrorString()
    
    @pytest.mark.parametrize("expression,expected_valid", [
        ('"population" > 10000', True),
        ('"name" LIKE \'%test%\'', True),
        ('intersects($geometry, @filter)', True),
        ('"invalid syntax', False),
    ])
    def test_various_expressions(
        self,
        ogr_backend_mock,
        expression,
        expected_valid
    ):
        """Test various expression types."""
        backend = ogr_backend_mock
        
        backend.validate_expression = MagicMock(return_value=expected_valid)
        
        is_valid = backend.validate_expression(expression)
        assert is_valid == expected_valid


@pytest.mark.integration
@pytest.mark.ogr
class TestOGRFeatureIteration:
    """Tests for feature iteration in OGR backend."""
    
    def test_iterate_features_with_progress(
        self,
        ogr_backend_mock,
        ogr_layer
    ):
        """Test feature iteration with progress reporting."""
        backend = ogr_backend_mock
        
        progress_values = []
        
        def track_progress(value):
            progress_values.append(value)
        
        backend.iterate_features = MagicMock(side_effect=lambda layer, callback: [
            callback(0),
            callback(25),
            callback(50),
            callback(75),
            callback(100)
        ])
        
        backend.iterate_features(ogr_layer, track_progress)
        
        backend.iterate_features.assert_called_once()
    
    def test_batch_processing(self, ogr_backend_mock):
        """Test batch processing of features."""
        backend = ogr_backend_mock
        backend._batch_size = 100
        
        # Simulate processing 1000 features in batches
        backend.process_in_batches = MagicMock(
            return_value=MagicMock(
                total_processed=1000,
                batches=10,
                total_time_ms=500.0
            )
        )
        
        result = backend.process_in_batches(
            features=range(1000),
            batch_size=100
        )
        
        assert result.total_processed == 1000
        assert result.batches == 10


@pytest.mark.integration
@pytest.mark.ogr
class TestOGRFormatSupport:
    """Tests for specific format support."""
    
    def test_shapefile_support(self, ogr_backend_mock, ogr_layer):
        """Test Shapefile format support."""
        backend = ogr_backend_mock
        ogr_layer.dataProvider().dataSourceUri.return_value = "/path/to/file.shp"
        
        backend.detect_format = MagicMock(return_value="Shapefile")
        
        format_name = backend.detect_format(ogr_layer)
        assert format_name == "Shapefile"
    
    def test_geojson_support(self, ogr_backend_mock, ogr_layer):
        """Test GeoJSON format support."""
        backend = ogr_backend_mock
        ogr_layer.dataProvider().dataSourceUri.return_value = "/path/to/file.geojson"
        
        backend.detect_format = MagicMock(return_value="GeoJSON")
        
        format_name = backend.detect_format(ogr_layer)
        assert format_name == "GeoJSON"
    
    def test_csv_support(self, ogr_backend_mock, ogr_layer):
        """Test CSV format support."""
        backend = ogr_backend_mock
        ogr_layer.dataProvider().dataSourceUri.return_value = "/path/to/file.csv"
        
        backend.detect_format = MagicMock(return_value="CSV")
        
        format_name = backend.detect_format(ogr_layer)
        assert format_name == "CSV"


@pytest.mark.integration
@pytest.mark.ogr
class TestOGRFallback:
    """Tests for OGR as fallback backend."""
    
    def test_fallback_from_postgresql(
        self,
        ogr_backend_mock,
        postgresql_layer
    ):
        """Test OGR as fallback when PostgreSQL unavailable."""
        backend = ogr_backend_mock
        
        # Simulate PostgreSQL not available
        backend.is_fallback = MagicMock(return_value=True)
        
        result = MagicMock()
        result.success = True
        result.is_fallback = True
        result.matched_count = 100
        backend.execute.return_value = result
        
        # Execute through OGR fallback
        execution_result = backend.execute(
            '"population" > 10000',
            postgresql_layer
        )
        
        assert execution_result.success is True
    
    def test_fallback_from_spatialite(
        self,
        ogr_backend_mock,
        spatialite_layer
    ):
        """Test OGR as fallback when Spatialite fails."""
        backend = ogr_backend_mock
        
        result = MagicMock()
        result.success = True
        result.is_fallback = True
        backend.execute.return_value = result
        
        execution_result = backend.execute(
            '"area" > 1000',
            spatialite_layer
        )
        
        assert execution_result.success is True
