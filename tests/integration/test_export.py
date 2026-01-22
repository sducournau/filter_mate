# -*- coding: utf-8 -*-
"""
Integration Tests for Export Workflow.

Tests the complete export workflow including:
- Single layer export to various formats
- Multi-layer batch export
- ZIP archive creation (v5.0)
- Style export
- CRS transformation

Author: FilterMate Team
Date: January 2026
Sprint: 1.2 - Critical Tests
"""
import pytest
import sys
import os
import tempfile
import zipfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(plugin_dir))

# Mock QGIS before importing
sys.modules['qgis'] = Mock()
sys.modules['qgis.core'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = Mock()
sys.modules['qgis.processing'] = Mock()

from core.export.layer_exporter import LayerExporter, ExportConfig, ExportResult, ExportFormat


class TestExportConfig:
    """Tests for ExportConfig dataclass."""
    
    def test_default_values(self):
        """Test ExportConfig default values."""
        config = ExportConfig(
            layers=["layer1"],
            output_path="/tmp/export",
            datatype="GPKG"
        )
        
        assert config.layers == ["layer1"]
        assert config.output_path == "/tmp/export"
        assert config.datatype == "GPKG"
        assert config.projection is None
        assert config.style_format is None
        assert config.save_styles is False
        assert config.batch_mode is False
        assert config.batch_zip is False
    
    def test_batch_zip_config(self):
        """Test batch ZIP configuration."""
        config = ExportConfig(
            layers=["layer1", "layer2"],
            output_path="/tmp/export.zip",
            datatype="GPKG",
            batch_mode=True,
            batch_zip=True
        )
        
        assert config.batch_zip is True
        assert config.batch_mode is True


class TestExportResult:
    """Tests for ExportResult dataclass."""
    
    def test_success_result(self):
        """Test successful export result."""
        result = ExportResult(
            success=True,
            exported_count=3,
            failed_count=0,
            output_path="/tmp/export"
        )
        
        assert result.success is True
        assert result.exported_count == 3
        assert result.warnings == []
    
    def test_failure_result(self):
        """Test failed export result."""
        result = ExportResult(
            success=False,
            exported_count=0,
            failed_count=1,
            error_message="Export failed"
        )
        
        assert result.success is False
        assert result.error_message == "Export failed"
    
    def test_partial_success(self):
        """Test partial success (some layers failed)."""
        result = ExportResult(
            success=True,
            exported_count=2,
            failed_count=1,
            error_message="1 layer(s) failed to export"
        )
        
        assert result.success is True
        assert result.exported_count == 2
        assert result.failed_count == 1


class TestExportFormat:
    """Tests for ExportFormat enum."""
    
    def test_all_formats_exist(self):
        """Test all expected formats are defined."""
        expected_formats = [
            "GPKG", "SHAPEFILE", "GEOJSON", "GML", 
            "KML", "CSV", "XLSX", "TAB", "DXF", "SPATIALITE"
        ]
        
        for fmt in expected_formats:
            assert hasattr(ExportFormat, fmt), f"Missing format: {fmt}"
    
    def test_format_values(self):
        """Test format values for QGIS driver names."""
        assert ExportFormat.GPKG.value == "GPKG"
        assert ExportFormat.SHAPEFILE.value == "ESRI Shapefile"
        assert ExportFormat.GEOJSON.value == "GeoJSON"


class TestLayerExporterInit:
    """Tests for LayerExporter initialization."""
    
    def test_init_with_project(self):
        """Test initialization with mock project."""
        mock_project = Mock()
        
        exporter = LayerExporter(project=mock_project)
        
        assert exporter.project == mock_project
    
    def test_init_without_project(self):
        """Test initialization without project."""
        exporter = LayerExporter()
        
        assert exporter.project is None


class TestLayerExporterGetLayer:
    """Tests for get_layer_by_name method."""
    
    def test_get_existing_layer(self):
        """Test getting an existing layer by name."""
        mock_layer = Mock()
        mock_layer.name.return_value = "test_layer"
        
        mock_project = Mock()
        mock_project.mapLayersByName.return_value = [mock_layer]
        
        exporter = LayerExporter(project=mock_project)
        result = exporter.get_layer_by_name("test_layer")
        
        assert result == mock_layer
        mock_project.mapLayersByName.assert_called_with("test_layer")
    
    def test_get_nonexistent_layer(self):
        """Test getting a non-existent layer returns None."""
        mock_project = Mock()
        mock_project.mapLayersByName.return_value = []
        
        exporter = LayerExporter(project=mock_project)
        result = exporter.get_layer_by_name("nonexistent")
        
        assert result is None
    
    def test_get_layer_without_project(self):
        """Test getting layer without project returns None."""
        exporter = LayerExporter()
        result = exporter.get_layer_by_name("any_layer")
        
        assert result is None


class TestBatchExportZip:
    """Tests for batch ZIP export functionality (v5.0)."""
    
    def test_batch_export_creates_zip(self):
        """Test that batch_zip creates a ZIP archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "export.zip")
            
            # Mock layer
            mock_layer = Mock()
            mock_layer.name.return_value = "test_layer"
            mock_layer.crs.return_value = Mock()
            mock_layer.featureCount.return_value = 10
            
            mock_project = Mock()
            mock_project.mapLayersByName.return_value = [mock_layer]
            
            exporter = LayerExporter(project=mock_project)
            
            # Mock the export_multiple_to_directory method
            with patch.object(exporter, 'export_multiple_to_directory') as mock_export:
                mock_export.return_value = ExportResult(
                    success=True,
                    exported_count=1,
                    output_path=temp_dir
                )
                
                # Create a dummy file in temp directory for zip
                def create_dummy_files(*args, **kwargs):
                    # Simulate files created during export
                    config = args[0]
                    dummy_file = os.path.join(config.output_path, "test_layer.gpkg")
                    with open(dummy_file, 'w') as f:
                        f.write("test content")
                    return ExportResult(
                        success=True,
                        exported_count=1,
                        output_path=config.output_path
                    )
                
                mock_export.side_effect = create_dummy_files
                
                config = ExportConfig(
                    layers=["test_layer"],
                    output_path=zip_path,
                    datatype="GPKG",
                    batch_mode=True,
                    batch_zip=True
                )
                
                result = exporter.export_batch(config)
                
                # Verify ZIP was created
                assert result.success is True
                assert result.output_path.endswith('.zip')
                assert os.path.exists(result.output_path)
                
                # Verify ZIP contents
                with zipfile.ZipFile(result.output_path, 'r') as zipf:
                    assert len(zipf.namelist()) > 0
    
    def test_batch_export_without_zip(self):
        """Test batch export without ZIP falls back to directory."""
        mock_project = Mock()
        exporter = LayerExporter(project=mock_project)
        
        with patch.object(exporter, 'export_multiple_to_directory') as mock_export:
            mock_export.return_value = ExportResult(
                success=True,
                exported_count=1,
                output_path="/tmp/export"
            )
            
            config = ExportConfig(
                layers=["layer1"],
                output_path="/tmp/export",
                datatype="GPKG",
                batch_mode=True,
                batch_zip=False  # No ZIP
            )
            
            result = exporter.export_batch(config)
            
            mock_export.assert_called_once()
            assert result.success is True
    
    def test_zip_extension_added(self):
        """Test .zip extension is added if missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Path without .zip extension
            base_path = os.path.join(temp_dir, "export_archive")
            
            mock_project = Mock()
            exporter = LayerExporter(project=mock_project)
            
            with patch.object(exporter, 'export_multiple_to_directory') as mock_export:
                def create_dummy(*args, **kwargs):
                    config = args[0]
                    with open(os.path.join(config.output_path, "test.gpkg"), 'w') as f:
                        f.write("test")
                    return ExportResult(success=True, exported_count=1, output_path=config.output_path)
                
                mock_export.side_effect = create_dummy
                
                config = ExportConfig(
                    layers=["layer1"],
                    output_path=base_path,  # No .zip
                    datatype="GPKG",
                    batch_zip=True
                )
                
                result = exporter.export_batch(config)
                
                # Should add .zip extension
                assert result.output_path == base_path + ".zip"


class TestExportWorkflowIntegration:
    """Integration tests for complete export workflow."""
    
    def test_export_workflow_with_mock_qgis(self):
        """Test complete export workflow with mocked QGIS."""
        # This test simulates a full export workflow
        mock_layer = Mock()
        mock_layer.name.return_value = "buildings"
        mock_layer.crs.return_value = Mock()
        mock_layer.crs().authid.return_value = "EPSG:4326"
        mock_layer.featureCount.return_value = 500
        mock_layer.subsetString.return_value = "category = 'residential'"
        
        mock_project = Mock()
        mock_project.mapLayersByName.return_value = [mock_layer]
        
        exporter = LayerExporter(project=mock_project)
        
        # Test config creation
        config = ExportConfig(
            layers=["buildings"],
            output_path="/tmp/buildings_export.gpkg",
            datatype="GPKG",
            save_styles=True,
            style_format="qml"
        )
        
        assert config.layers == ["buildings"]
        assert config.save_styles is True
    
    def test_export_multiple_formats(self):
        """Test export supports all documented formats."""
        formats_to_test = [
            ("GPKG", "test.gpkg"),
            ("GeoJSON", "test.geojson"),
            ("ESRI Shapefile", "test.shp"),
        ]
        
        for format_name, expected_ext in formats_to_test:
            config = ExportConfig(
                layers=["layer1"],
                output_path=f"/tmp/{expected_ext}",
                datatype=format_name
            )
            
            assert config.datatype == format_name


class TestExportErrorHandling:
    """Tests for export error handling."""
    
    def test_export_with_invalid_layer(self):
        """Test export handles invalid layer gracefully."""
        mock_project = Mock()
        mock_project.mapLayersByName.return_value = []  # Layer not found
        
        exporter = LayerExporter(project=mock_project)
        
        config = ExportConfig(
            layers=["nonexistent_layer"],
            output_path="/tmp/export.gpkg",
            datatype="GPKG"
        )
        
        # Should handle gracefully without crashing
        layer = exporter.get_layer_by_name("nonexistent_layer")
        assert layer is None
    
    def test_export_result_with_warnings(self):
        """Test export result can contain warnings."""
        result = ExportResult(
            success=True,
            exported_count=2,
            warnings=["CRS transformation applied", "Style file not found"]
        )
        
        assert len(result.warnings) == 2
        assert "CRS transformation applied" in result.warnings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
