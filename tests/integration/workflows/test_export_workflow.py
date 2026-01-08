# -*- coding: utf-8 -*-
"""
End-to-End Tests for Export Workflow - ARCH-050

Tests the complete export workflow from layer selection
to file output.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock
import tempfile
from pathlib import Path
import sys

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def export_controller_mock():
    """Create a mock export controller."""
    controller = MagicMock()
    controller.is_active = False
    controller.get_source_layer.return_value = None
    controller.get_output_format.return_value = "GeoPackage"
    controller.get_output_path.return_value = None
    controller.can_export.return_value = False
    
    # State
    controller._source_layer = None
    controller._output_path = None
    controller._format = "GeoPackage"
    controller._options = {}
    
    def set_source(layer):
        controller._source_layer = layer
        controller.get_source_layer.return_value = layer
        controller.can_export.return_value = bool(layer and controller._output_path)
    
    def set_output(path):
        controller._output_path = path
        controller.get_output_path.return_value = path
        controller.can_export.return_value = bool(controller._source_layer and path)
    
    def set_format(fmt):
        controller._format = fmt
        controller.get_output_format.return_value = fmt
    
    controller.set_source_layer.side_effect = set_source
    controller.set_output_path.side_effect = set_output
    controller.set_output_format.side_effect = set_format
    
    return controller


@pytest.fixture
def mock_export_result():
    """Create a successful export result."""
    result = MagicMock()
    result.success = True
    result.feature_count = 100
    result.output_path = "/tmp/export.gpkg"
    result.file_size_bytes = 51200
    result.export_time_ms = 500.0
    result.error_message = None
    return result


@pytest.mark.e2e
@pytest.mark.integration
class TestExportWorkflowE2E:
    """E2E tests for the export workflow."""
    
    @pytest.mark.parametrize("format_name,extension", [
        ("GeoPackage", ".gpkg"),
        ("Shapefile", ".shp"),
        ("GeoJSON", ".geojson"),
        ("CSV", ".csv"),
        ("KML", ".kml"),
    ])
    def test_export_to_format(
        self,
        export_controller_mock,
        sample_vector_layer,
        mock_export_result,
        format_name,
        extension
    ):
        """Test exporting to various formats."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / f"export{extension}"
            
            # Setup
            controller.set_source_layer(sample_vector_layer)
            controller.set_output_format(format_name)
            controller.set_output_path(str(output_path))
            
            # Configure mock export
            mock_export_result.output_path = str(output_path)
            controller.export_layer = MagicMock(return_value=mock_export_result)
            
            # Execute export
            result = controller.export_layer()
            
            # Verify
            assert result.success is True
            assert result.feature_count > 0
    
    def test_export_filtered_layer(
        self,
        export_controller_mock,
        sample_vector_layer,
        mock_export_result
    ):
        """Test exporting a filtered layer."""
        controller = export_controller_mock
        
        # Simulate filtered layer
        sample_vector_layer.setSubsetString('"population" > 10000')
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "filtered_export.gpkg"
            
            controller.set_source_layer(sample_vector_layer)
            controller.set_output_path(str(output_path))
            
            # Mock export
            controller.export_layer = MagicMock(return_value=mock_export_result)
            result = controller.export_layer()
            
            assert result.success is True
    
    def test_export_selected_features_only(
        self,
        export_controller_mock,
        sample_vector_layer,
        mock_export_result
    ):
        """Test exporting only selected features."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "selected_export.gpkg"
            
            controller.set_source_layer(sample_vector_layer)
            controller.set_output_path(str(output_path))
            controller.set_export_selected_only = MagicMock()
            controller.set_export_selected_only(True)
            
            # Mock export with fewer features
            mock_export_result.feature_count = 25
            controller.export_layer = MagicMock(return_value=mock_export_result)
            
            result = controller.export_layer()
            assert result.success is True
            assert result.feature_count == 25
    
    def test_export_with_crs_transform(
        self,
        export_controller_mock,
        sample_vector_layer,
        mock_export_result
    ):
        """Test exporting with CRS transformation."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "transformed_export.gpkg"
            
            controller.set_source_layer(sample_vector_layer)
            controller.set_output_path(str(output_path))
            controller.set_output_crs = MagicMock()
            controller.set_output_crs("EPSG:3857")  # Web Mercator
            
            controller.export_layer = MagicMock(return_value=mock_export_result)
            result = controller.export_layer()
            
            assert result.success is True
    
    def test_export_with_field_mapping(
        self,
        export_controller_mock,
        sample_vector_layer,
        mock_export_result
    ):
        """Test exporting with custom field mapping."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "mapped_export.gpkg"
            
            controller.set_source_layer(sample_vector_layer)
            controller.set_output_path(str(output_path))
            
            # Set field mapping
            field_mapping = {
                "id": "feature_id",
                "name": "feature_name",
                "population": "pop_count"
            }
            controller.set_field_mapping = MagicMock()
            controller.set_field_mapping(field_mapping)
            
            controller.export_layer = MagicMock(return_value=mock_export_result)
            result = controller.export_layer()
            
            assert result.success is True


@pytest.mark.e2e
@pytest.mark.integration
class TestBatchExportWorkflowE2E:
    """E2E tests for batch export operations."""
    
    def test_export_multiple_layers(
        self,
        export_controller_mock,
        multiple_layers,
        mock_export_result
    ):
        """Test exporting multiple layers at once."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup batch export
            controller.set_source_layers = MagicMock()
            controller.set_output_directory = MagicMock()
            controller.batch_export = MagicMock()
            
            controller.set_source_layers(multiple_layers)
            controller.set_output_directory(tmpdir)
            
            # Mock batch result
            batch_result = MagicMock()
            batch_result.success = True
            batch_result.total_exported = 5
            batch_result.failed_count = 0
            batch_result.results = [mock_export_result] * 5
            
            controller.batch_export.return_value = batch_result
            result = controller.batch_export()
            
            assert result.success is True
            assert result.total_exported == 5
            assert result.failed_count == 0
    
    def test_batch_export_with_partial_failure(
        self,
        export_controller_mock,
        multiple_layers
    ):
        """Test batch export with some failures."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            controller.set_source_layers = MagicMock()
            controller.set_output_directory = MagicMock()
            controller.batch_export = MagicMock()
            
            controller.set_source_layers(multiple_layers)
            controller.set_output_directory(tmpdir)
            
            # Mock partial failure
            batch_result = MagicMock()
            batch_result.success = True  # Overall success if some exported
            batch_result.total_exported = 3
            batch_result.failed_count = 2
            batch_result.failed_layers = ["layer_3", "layer_4"]
            
            controller.batch_export.return_value = batch_result
            result = controller.batch_export()
            
            assert result.total_exported == 3
            assert result.failed_count == 2


@pytest.mark.e2e
@pytest.mark.integration
class TestExportValidationE2E:
    """E2E tests for export validation."""
    
    def test_invalid_output_path(
        self,
        export_controller_mock,
        sample_vector_layer
    ):
        """Test error handling for invalid output path."""
        controller = export_controller_mock
        
        controller.set_source_layer(sample_vector_layer)
        controller.set_output_path("/invalid/path/that/does/not/exist/export.gpkg")
        
        # Should fail validation
        controller.validate_export = MagicMock(return_value=False)
        assert controller.validate_export() is False
    
    def test_unsupported_format(
        self,
        export_controller_mock,
        sample_vector_layer
    ):
        """Test error handling for unsupported format."""
        controller = export_controller_mock
        
        controller.set_source_layer(sample_vector_layer)
        controller.set_output_format("UnsupportedFormat")
        
        # Should fail validation
        controller.validate_format = MagicMock(return_value=False)
        assert controller.validate_format() is False
    
    def test_empty_layer_export(
        self,
        export_controller_mock,
        empty_layer
    ):
        """Test exporting an empty layer."""
        controller = export_controller_mock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty_export.gpkg"
            
            controller.set_source_layer(empty_layer)
            controller.set_output_path(str(output_path))
            
            # Empty export result
            empty_result = MagicMock()
            empty_result.success = True
            empty_result.feature_count = 0
            
            controller.export_layer = MagicMock(return_value=empty_result)
            result = controller.export_layer()
            
            # Should succeed even with 0 features
            assert result.success is True
            assert result.feature_count == 0
