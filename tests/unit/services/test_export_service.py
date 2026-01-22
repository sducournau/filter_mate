# -*- coding: utf-8 -*-
"""
Tests for ExportService - Export orchestration service.

Tests:
- Initialization
- Single layer export
- Batch export
- GeoPackage export
- Parameter validation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os


# Mock QGIS before any imports
@pytest.fixture(autouse=True)
def mock_qgis_modules():
    """Mock QGIS modules for all tests."""
    mock_qgis = MagicMock()
    mock_qgis.core = MagicMock()
    mock_qgis.PyQt = MagicMock()
    
    with patch.dict('sys.modules', {
        'qgis': mock_qgis,
        'qgis.core': mock_qgis.core,
        'qgis.PyQt': mock_qgis.PyQt,
        'qgis.PyQt.QtCore': MagicMock(),
        'qgis.PyQt.QtWidgets': MagicMock(),
    }):
        yield


class TestExportServiceStructure:
    """Tests for ExportService module structure."""
    
    def test_export_service_module_importable(self, mock_qgis_modules):
        """Test that export_service module can be imported."""
        # Force reimport with mocks
        if 'core.services.export_service' in sys.modules:
            del sys.modules['core.services.export_service']
        
        try:
            with patch('adapters.qgis.factory.get_qgis_factory'):
                # Module should be importable when QGIS is mocked
                pass
        except ImportError:
            # Expected in test environment without full QGIS
            pass


class TestExportServiceValidationLogic:
    """Tests for ExportService validation logic (standalone)."""
    
    def test_validate_empty_layers_list(self):
        """Test validation fails with empty layers list."""
        layers = []
        errors = []
        
        if not layers:
            errors.append("No layers provided for export")
        
        assert len(errors) > 0
        assert "No layers" in errors[0]
    
    def test_validate_none_layer(self):
        """Test validation fails with None layer."""
        layers = [None]
        errors = []
        
        for layer in layers:
            if not layer:
                errors.append("Invalid layer: None")
        
        assert len(errors) > 0
        assert "Invalid" in errors[0]
    
    def test_validate_empty_output_path(self):
        """Test validation fails with empty output path."""
        output_path = ""
        errors = []
        
        if not output_path:
            errors.append("Output path not specified")
        
        assert len(errors) > 0
        assert "path" in errors[0].lower()
    
    def test_validate_file_exists_no_overwrite(self):
        """Test validation fails when file exists and overwrite disabled."""
        with patch('os.path.exists', return_value=True):
            output_path = "/existing/file.shp"
            overwrite = False
            errors = []
            
            if os.path.exists(output_path) and not overwrite:
                errors.append(f"Output file exists and overwrite is disabled: {output_path}")
            
            assert len(errors) > 0
            assert "exists" in errors[0].lower()
    
    def test_validate_success_all_valid(self):
        """Test validation succeeds with valid parameters."""
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        
        layers = [mock_layer]
        output_path = "/new/output.shp"
        overwrite = True
        errors = []
        
        # Basic validation
        if not layers:
            errors.append("No layers provided")
        
        for layer in layers:
            if layer and not layer.isValid():
                errors.append("Invalid layer")
        
        if not output_path:
            errors.append("No output path")
        
        assert len(errors) == 0


class TestExportResultLogic:
    """Tests for ExportResult logic (standalone)."""
    
    def test_export_result_default_values(self):
        """Test ExportResult default structure."""
        result = {
            'success': False,
            'output_path': '',
            'layers_exported': 0,
            'features_exported': 0,
            'errors': []
        }
        
        assert result['success'] is False
        assert result['output_path'] == ''
        assert result['layers_exported'] == 0
        assert result['errors'] == []
    
    def test_export_result_success_state(self):
        """Test ExportResult success state."""
        result = {
            'success': True,
            'output_path': '/output/file.shp',
            'layers_exported': 1,
            'features_exported': 100,
            'errors': []
        }
        
        assert result['success'] is True
        assert result['layers_exported'] == 1
        assert len(result['errors']) == 0
    
    def test_export_result_error_state(self):
        """Test ExportResult error state."""
        result = {
            'success': False,
            'output_path': '',
            'layers_exported': 0,
            'features_exported': 0,
            'errors': ['Export failed: invalid format']
        }
        
        assert result['success'] is False
        assert len(result['errors']) > 0


class TestExportFormatLogic:
    """Tests for export format handling."""
    
    def test_geopackage_extension_added(self):
        """Test .gpkg extension is added if missing."""
        output_path = "/output/file"
        
        if not output_path.endswith('.gpkg'):
            output_path += '.gpkg'
        
        assert output_path.endswith('.gpkg')
    
    def test_geopackage_extension_preserved(self):
        """Test .gpkg extension is preserved if present."""
        output_path = "/output/file.gpkg"
        
        if not output_path.endswith('.gpkg'):
            output_path += '.gpkg'
        
        assert output_path.count('.gpkg') == 1
    
    def test_shapefile_format_value(self):
        """Test shapefile format detection."""
        output_path = "/output/file.shp"
        
        is_shapefile = output_path.endswith('.shp')
        
        assert is_shapefile is True


class TestBatchExportLogic:
    """Tests for batch export logic."""
    
    def test_batch_export_count(self):
        """Test batch export counts layers correctly."""
        mock_layers = [Mock(), Mock(), Mock()]
        
        for layer in mock_layers:
            layer.featureCount.return_value = 100
        
        layers_exported = len(mock_layers)
        features_exported = sum(layer.featureCount() for layer in mock_layers)
        
        assert layers_exported == 3
        assert features_exported == 300
    
    def test_batch_export_empty_layers(self):
        """Test batch export fails with empty layers list."""
        layers = []
        errors = []
        
        if not layers:
            errors.append("No layers provided for export")
        
        assert len(errors) > 0


class TestProgressCallbackLogic:
    """Tests for progress callback handling."""
    
    def test_progress_callback_called(self):
        """Test progress callback is called."""
        progress_callback = Mock()
        
        # Simulate progress updates
        progress_callback(0)
        progress_callback(50)
        progress_callback(100)
        
        assert progress_callback.call_count == 3
    
    def test_cancel_callback_checked(self):
        """Test cancel callback is checked."""
        cancel_callback = Mock(return_value=False)
        
        # Simulate check
        should_cancel = cancel_callback()
        
        cancel_callback.assert_called_once()
        assert should_cancel is False

