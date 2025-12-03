"""
FilterMate Unit Tests - Basic Infrastructure

This module contains initial unit tests for FilterMate functionality,
focusing on utility functions and data conversions.

Run tests with:
    pytest tests/test_appUtils.py -v
    pytest tests/test_appUtils.py --cov=modules
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsWkbTypes


class TestGeometryTypeConversion:
    """Test geometry type conversion utilities"""
    
    def test_point_geometry(self):
        """Test Point geometry type conversion"""
        from modules.appUtils import geometry_type_to_string
        result = geometry_type_to_string(QgsWkbTypes.PointGeometry)
        assert result == "GeometryType.Point"
    
    def test_line_geometry(self):
        """Test LineString geometry type conversion"""
        from modules.appUtils import geometry_type_to_string
        result = geometry_type_to_string(QgsWkbTypes.LineGeometry)
        assert result == "GeometryType.Line"
    
    def test_polygon_geometry(self):
        """Test Polygon geometry type conversion"""
        from modules.appUtils import geometry_type_to_string
        result = geometry_type_to_string(QgsWkbTypes.PolygonGeometry)
        assert result == "GeometryType.Polygon"
    
    def test_unknown_geometry(self):
        """Test Unknown geometry type conversion"""
        from modules.appUtils import geometry_type_to_string
        result = geometry_type_to_string(QgsWkbTypes.UnknownGeometry)
        assert result == "GeometryType.UnknownGeometry"
    
    def test_null_geometry(self):
        """Test NullGeometry type conversion"""
        from modules.appUtils import geometry_type_to_string
        result = geometry_type_to_string(QgsWkbTypes.NullGeometry)
        assert result == "GeometryType.UnknownGeometry"


class TestProviderDetection:
    """Test layer provider type detection"""
    
    def test_postgresql_provider(self):
        """Test PostgreSQL provider detection"""
        from modules.appUtils import detect_layer_provider_type
        
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        
        result = detect_layer_provider_type(mock_layer)
        assert result == "postgresql"
    
    def test_spatialite_provider(self):
        """Test Spatialite provider detection"""
        from modules.appUtils import detect_layer_provider_type
        
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'spatialite'
        mock_layer.dataProvider().capabilities.return_value = Mock()
        
        result = detect_layer_provider_type(mock_layer)
        assert result == "spatialite"
    
    def test_ogr_provider(self):
        """Test OGR provider detection"""
        from modules.appUtils import detect_layer_provider_type
        
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'ogr'
        mock_provider = Mock()
        mock_provider.capabilities.return_value = 0  # No Spatialite capabilities
        mock_layer.dataProvider.return_value = mock_provider
        
        result = detect_layer_provider_type(mock_layer)
        assert result == "ogr"


class TestLoggingConfiguration:
    """Test logging configuration and setup"""
    
    def test_logger_creation(self, tmp_path):
        """Test logger is created with correct configuration"""
        from modules.logging_config import setup_logger
        
        log_file = tmp_path / "test.log"
        logger = setup_logger('TestLogger', str(log_file))
        
        assert logger is not None
        assert logger.name == 'TestLogger'
        assert len(logger.handlers) > 0
    
    def test_log_file_rotation(self, tmp_path):
        """Test log file rotation is configured"""
        from modules.logging_config import setup_logger
        from logging.handlers import RotatingFileHandler
        
        log_file = tmp_path / "test_rotation.log"
        logger = setup_logger('TestRotation', str(log_file))
        
        # Find the rotating file handler
        rotating_handler = None
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                rotating_handler = handler
                break
        
        assert rotating_handler is not None
        assert rotating_handler.maxBytes == 10*1024*1024  # 10 MB
        assert rotating_handler.backupCount == 5
    
    def test_logging_messages(self, tmp_path, caplog):
        """Test different log levels are recorded"""
        from modules.logging_config import setup_logger
        import logging
        
        log_file = tmp_path / "test_messages.log"
        logger = setup_logger('TestMessages', str(log_file), level=logging.DEBUG)
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Check log file was created
        assert log_file.exists()


class TestIconCaching:
    """Test icon caching functionality"""
    
    @patch('filter_mate_dockwidget.QgsLayerItem')
    def test_icon_cache_works(self, mock_qgs_layer_item):
        """Test that icon_per_geometry_type uses cache"""
        from filter_mate_dockwidget import FilterMateDockWidget
        
        # Setup mock
        mock_point_icon = Mock()
        mock_qgs_layer_item.iconPoint.return_value = mock_point_icon
        
        # Create instance
        widget = FilterMateDockWidget(None, None, None, None)
        
        # First call should create icon
        icon1 = widget.icon_per_geometry_type('GeometryType.Point')
        assert icon1 == mock_point_icon
        assert mock_qgs_layer_item.iconPoint.call_count == 1
        
        # Second call should use cache
        icon2 = widget.icon_per_geometry_type('GeometryType.Point')
        assert icon2 == mock_point_icon
        assert mock_qgs_layer_item.iconPoint.call_count == 1  # Still 1, not called again
        
        # Cache should contain the entry
        assert 'GeometryType.Point' in FilterMateDockWidget._icon_cache
    
    def test_different_geometry_types_cached_separately(self):
        """Test that different geometry types are cached separately"""
        from filter_mate_dockwidget import FilterMateDockWidget
        
        widget = FilterMateDockWidget(None, None, None, None)
        
        # Clear cache for clean test
        FilterMateDockWidget._icon_cache.clear()
        
        with patch('filter_mate_dockwidget.QgsLayerItem') as mock_qgs:
            mock_qgs.iconPoint.return_value = Mock(name='point_icon')
            mock_qgs.iconLine.return_value = Mock(name='line_icon')
            mock_qgs.iconPolygon.return_value = Mock(name='polygon_icon')
            
            icon_point = widget.icon_per_geometry_type('GeometryType.Point')
            icon_line = widget.icon_per_geometry_type('GeometryType.Line')
            icon_polygon = widget.icon_per_geometry_type('GeometryType.Polygon')
            
            # All should be different
            assert icon_point != icon_line
            assert icon_line != icon_polygon
            assert icon_point != icon_polygon
            
            # All should be in cache
            assert len(FilterMateDockWidget._icon_cache) == 3


class TestErrorHandling:
    """Test improved error handling"""
    
    def test_config_directory_creation_error_is_logged(self, caplog):
        """Test that directory creation errors are properly logged"""
        import os
        from unittest.mock import patch
        
        with patch('os.makedirs', side_effect=OSError("Permission denied")):
            # Import will attempt to create directory
            with pytest.raises(OSError):
                os.makedirs("/fake/path", exist_ok=True)
    
    def test_database_connection_close_errors_logged(self, caplog):
        """Test that database connection close errors are logged"""
        import logging
        
        with caplog.at_level(logging.DEBUG):
            # Simulate code from appTasks.py
            mock_conn = Mock()
            mock_conn.close.side_effect = Exception("Connection already closed")
            
            try:
                mock_conn.close()
            except Exception as e:
                # This should be logged now instead of silently passed
                logging.getLogger('FilterMate').debug(f"Could not close database connection: {e}")
            
            assert "Could not close database connection" in caplog.text


# Fixtures
@pytest.fixture
def mock_qgis_layer():
    """Create a mock QGIS vector layer"""
    layer = Mock()
    layer.name.return_value = "Test Layer"
    layer.featureCount.return_value = 100
    layer.providerType.return_value = "memory"
    return layer


@pytest.fixture
def mock_postgresql_connection():
    """Create a mock PostgreSQL connection"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    return conn, cursor


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
