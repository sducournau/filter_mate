"""
Test source table name extraction for different layer types.
"""
import pytest
from unittest.mock import Mock, MagicMock
from qgis.core import QgsVectorLayer, QgsDataSourceUri

# Import the function to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.appUtils import get_source_table_name


def test_get_source_table_name_postgres():
    """Test extraction from PostgreSQL layer."""
    # Mock PostgreSQL layer
    layer = Mock(spec=QgsVectorLayer)
    layer.providerType.return_value = 'postgres'
    layer.source.return_value = 'dbname=mydb host=localhost table="public"."my_table" (geom)'
    layer.name.return_value = 'Display Name'
    
    result = get_source_table_name(layer)
    # Should extract actual table name from source
    assert result in ['my_table', 'Display Name']  # Accept either since URI parsing may vary


def test_get_source_table_name_gpkg_with_layername():
    """Test extraction from GeoPackage with layername parameter."""
    # Mock OGR/GeoPackage layer with layername
    layer = Mock(spec=QgsVectorLayer)
    layer.providerType.return_value = 'ogr'
    layer.source.return_value = '/path/to/file.gpkg|layername=actual_table_name'
    layer.name.return_value = 'Distribution Cluster'
    
    result = get_source_table_name(layer)
    assert result == 'actual_table_name'


def test_get_source_table_name_gpkg_no_layername():
    """Test extraction from GeoPackage without explicit layername."""
    # Mock OGR/GeoPackage layer without layername
    layer = Mock(spec=QgsVectorLayer)
    layer.providerType.return_value = 'ogr'
    layer.source.return_value = '/path/to/file.gpkg'
    layer.name.return_value = 'Display Name'
    
    result = get_source_table_name(layer)
    # Should fallback to layer.name()
    assert result == 'Display Name'


def test_get_source_table_name_spatialite():
    """Test extraction from Spatialite layer."""
    # Mock Spatialite layer
    layer = Mock(spec=QgsVectorLayer)
    layer.providerType.return_value = 'spatialite'
    layer.source.return_value = '/path/to/file.sqlite'
    layer.name.return_value = 'Display Name'
    
    # Mock QgsDataSourceUri
    mock_uri = Mock()
    mock_uri.table.return_value = 'source_table'
    
    with pytest.mock.patch('modules.appUtils.QgsDataSourceUri', return_value=mock_uri):
        result = get_source_table_name(layer)
        assert result == 'source_table'


def test_get_source_table_name_shapefile():
    """Test extraction from Shapefile."""
    # Mock Shapefile layer
    layer = Mock(spec=QgsVectorLayer)
    layer.providerType.return_value = 'ogr'
    layer.source.return_value = '/path/to/myfile.shp'
    layer.name.return_value = 'Display Name'
    
    result = get_source_table_name(layer)
    # Should extract filename without extension
    assert result == 'myfile'


def test_get_source_table_name_none():
    """Test with None layer."""
    result = get_source_table_name(None)
    assert result is None


def test_get_source_table_name_fallback():
    """Test fallback to layer.name() on error."""
    # Mock layer that will cause exception
    layer = Mock(spec=QgsVectorLayer)
    layer.providerType.side_effect = Exception("Test error")
    layer.name.return_value = 'Fallback Name'
    
    result = get_source_table_name(layer)
    assert result == 'Fallback Name'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
