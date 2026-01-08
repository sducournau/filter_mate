"""
Unit tests for ExportingController.

Tests the exporting tab controller functionality including
layer selection, format configuration, output path,
CRS selection, and export execution.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


def create_exporting_controller(with_service=True):
    """Create an ExportingController for testing."""
    from ui.controllers.exporting_controller import ExportingController
    
    dockwidget = Mock()
    signal_manager = Mock()
    signal_manager.connect.return_value = "sig_001"
    
    filter_service = Mock() if with_service else None
    
    controller = ExportingController(
        dockwidget=dockwidget,
        filter_service=filter_service,
        signal_manager=signal_manager
    )
    
    return controller


class TestExportingControllerInitialization:
    """Tests for controller initialization."""
    
    def test_initialization(self):
        """Test controller initializes correctly."""
        controller = create_exporting_controller()
        
        assert controller.dockwidget is not None
        assert controller.get_layers_to_export() == []
        assert controller.get_output_path() == ""
    
    def test_default_format(self):
        """Test default format is GeoPackage."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        assert controller.get_output_format() == ExportFormat.GEOPACKAGE
    
    def test_initialization_without_service(self):
        """Test controller works without filter service."""
        controller = create_exporting_controller(with_service=False)
        
        assert controller.filter_service is None
        assert controller is not None


class TestLayerSelection:
    """Tests for layer selection."""
    
    def test_set_layers_to_export(self):
        """Test setting layers to export."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["layer_1", "layer_2"])
        
        assert controller.get_layers_to_export() == ["layer_1", "layer_2"]
    
    def test_add_layer(self):
        """Test adding a layer."""
        controller = create_exporting_controller()
        
        controller.add_layer("layer_1")
        controller.add_layer("layer_2")
        
        assert "layer_1" in controller.get_layers_to_export()
        assert "layer_2" in controller.get_layers_to_export()
    
    def test_add_duplicate_layer(self):
        """Test adding duplicate layer is ignored."""
        controller = create_exporting_controller()
        
        controller.add_layer("layer_1")
        controller.add_layer("layer_1")
        
        assert controller.get_layers_to_export().count("layer_1") == 1
    
    def test_remove_layer(self):
        """Test removing a layer."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["layer_1", "layer_2", "layer_3"])
        controller.remove_layer("layer_2")
        
        assert controller.get_layers_to_export() == ["layer_1", "layer_3"]
    
    def test_clear_layers(self):
        """Test clearing all layers."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["layer_1", "layer_2"])
        controller.clear_layers()
        
        assert controller.get_layers_to_export() == []
    
    def test_on_layer_selection_changed_handler(self):
        """Test on_layer_selection_changed handler."""
        controller = create_exporting_controller()
        
        controller.on_layer_selection_changed(["l1", "l2"])
        
        assert controller.get_layers_to_export() == ["l1", "l2"]


class TestFormatSelection:
    """Tests for format selection."""
    
    def test_set_output_format(self):
        """Test setting output format."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        controller.set_output_format(ExportFormat.SHAPEFILE)
        
        assert controller.get_output_format() == ExportFormat.SHAPEFILE
    
    def test_get_available_formats(self):
        """Test getting available formats."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        formats = controller.get_available_formats()
        
        assert len(formats) == len(ExportFormat)
        assert ExportFormat.GEOPACKAGE in formats
        assert ExportFormat.SHAPEFILE in formats
    
    def test_on_format_changed_handler(self):
        """Test on_format_changed handler."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        controller.on_format_changed("GeoJSON")
        
        assert controller.get_output_format() == ExportFormat.GEOJSON
    
    def test_on_format_changed_invalid(self):
        """Test on_format_changed with invalid value."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        controller.on_format_changed("InvalidFormat")
        
        # Should keep default
        assert controller.get_output_format() == ExportFormat.GEOPACKAGE


class TestExportFormat:
    """Tests for ExportFormat enum."""
    
    def test_extension_property(self):
        """Test extension property."""
        from ui.controllers.exporting_controller import ExportFormat
        
        assert ExportFormat.GEOPACKAGE.extension == '.gpkg'
        assert ExportFormat.SHAPEFILE.extension == '.shp'
        assert ExportFormat.GEOJSON.extension == '.geojson'
    
    def test_from_extension(self):
        """Test format detection from extension."""
        from ui.controllers.exporting_controller import ExportFormat
        
        assert ExportFormat.from_extension('.gpkg') == ExportFormat.GEOPACKAGE
        assert ExportFormat.from_extension('.shp') == ExportFormat.SHAPEFILE
        assert ExportFormat.from_extension('.GEOJSON') == ExportFormat.GEOJSON
    
    def test_supports_multiple_layers(self):
        """Test supports_multiple_layers property."""
        from ui.controllers.exporting_controller import ExportFormat
        
        assert ExportFormat.GEOPACKAGE.supports_multiple_layers is True
        assert ExportFormat.SHAPEFILE.supports_multiple_layers is False


class TestOutputPath:
    """Tests for output path configuration."""
    
    def test_set_output_path(self):
        """Test setting output path."""
        controller = create_exporting_controller()
        
        controller.set_output_path("/tmp/export.gpkg")
        
        assert controller.get_output_path() == "/tmp/export.gpkg"
    
    def test_output_path_detects_format(self):
        """Test output path detects format from extension."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        controller.set_output_path("/tmp/export.shp")
        
        assert controller.get_output_format() == ExportFormat.SHAPEFILE
    
    def test_on_output_path_changed_handler(self):
        """Test on_output_path_changed handler."""
        controller = create_exporting_controller()
        
        controller.on_output_path_changed("/home/user/data.geojson")
        
        assert controller.get_output_path() == "/home/user/data.geojson"


class TestCRSSelection:
    """Tests for CRS selection."""
    
    def test_get_output_crs_initially_none(self):
        """Test CRS is None initially (use layer CRS)."""
        controller = create_exporting_controller()
        
        assert controller.get_output_crs() is None
    
    def test_set_output_crs(self):
        """Test setting output CRS."""
        controller = create_exporting_controller()
        
        controller.set_output_crs("EPSG:4326")
        
        assert controller.get_output_crs() == "EPSG:4326"
    
    def test_on_crs_changed_handler(self):
        """Test on_crs_changed handler."""
        controller = create_exporting_controller()
        
        controller.on_crs_changed("EPSG:3857")
        
        assert controller.get_output_crs() == "EPSG:3857"
    
    def test_on_crs_changed_empty_string(self):
        """Test on_crs_changed with empty string resets to None."""
        controller = create_exporting_controller()
        
        controller.set_output_crs("EPSG:4326")
        controller.on_crs_changed("")
        
        assert controller.get_output_crs() is None


class TestExportMode:
    """Tests for export mode."""
    
    def test_default_mode_is_single(self):
        """Test default mode is single."""
        from ui.controllers.exporting_controller import ExportMode
        
        controller = create_exporting_controller()
        
        assert controller.get_export_mode() == ExportMode.SINGLE
    
    def test_set_export_mode(self):
        """Test setting export mode."""
        from ui.controllers.exporting_controller import ExportMode
        
        controller = create_exporting_controller()
        
        controller.set_export_mode(ExportMode.BATCH)
        
        assert controller.get_export_mode() == ExportMode.BATCH
    
    def test_multi_layer_sets_batch_mode_for_shapefile(self):
        """Test multi-layer auto-sets batch mode for non-multi-layer formats."""
        from ui.controllers.exporting_controller import ExportFormat, ExportMode
        
        controller = create_exporting_controller()
        controller.set_output_format(ExportFormat.SHAPEFILE)
        
        controller.set_layers_to_export(["l1", "l2"])
        
        assert controller.get_export_mode() == ExportMode.BATCH


class TestExportOptions:
    """Tests for export options."""
    
    def test_include_styles_default_false(self):
        """Test include styles is false by default."""
        controller = create_exporting_controller()
        
        assert controller.get_include_styles() is False
    
    def test_set_include_styles(self):
        """Test setting include styles."""
        controller = create_exporting_controller()
        
        controller.set_include_styles(True)
        
        assert controller.get_include_styles() is True
    
    def test_zip_output_default_false(self):
        """Test zip output is false by default."""
        controller = create_exporting_controller()
        
        assert controller.get_zip_output() is False
    
    def test_set_zip_output(self):
        """Test setting zip output."""
        controller = create_exporting_controller()
        
        controller.set_zip_output(True)
        
        assert controller.get_zip_output() is True


class TestExportConfiguration:
    """Tests for ExportConfiguration dataclass."""
    
    def test_build_configuration(self):
        """Test building configuration object."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1", "l2"])
        controller.set_output_path("/tmp/out.gpkg")
        controller.set_output_format(ExportFormat.GEOPACKAGE)
        
        config = controller.build_configuration()
        
        assert config.layer_ids == ["l1", "l2"]
        assert config.output_path == "/tmp/out.gpkg"
        assert config.output_format == ExportFormat.GEOPACKAGE
    
    def test_configuration_is_valid(self):
        """Test configuration validity check."""
        from ui.controllers.exporting_controller import ExportConfiguration
        
        # Valid config
        valid_config = ExportConfiguration(
            layer_ids=["l1"],
            output_path="/tmp/out.gpkg"
        )
        assert valid_config.is_valid() is True
        
        # Invalid - no layers
        invalid_config = ExportConfiguration(
            layer_ids=[],
            output_path="/tmp/out.gpkg"
        )
        assert invalid_config.is_valid() is False
        
        # Invalid - no path
        invalid_config2 = ExportConfiguration(
            layer_ids=["l1"],
            output_path=""
        )
        assert invalid_config2.is_valid() is False
    
    def test_configuration_to_dict(self):
        """Test configuration serialization."""
        from ui.controllers.exporting_controller import ExportConfiguration, ExportFormat
        
        config = ExportConfiguration(
            layer_ids=["l1"],
            output_path="/tmp/out.shp",
            output_format=ExportFormat.SHAPEFILE
        )
        
        data = config.to_dict()
        
        assert data["layer_ids"] == ["l1"]
        assert data["output_format"] == "ESRI Shapefile"
    
    def test_configuration_from_dict(self):
        """Test configuration deserialization."""
        from ui.controllers.exporting_controller import ExportConfiguration, ExportFormat
        
        data = {
            "layer_ids": ["l1", "l2"],
            "output_path": "/tmp/out.geojson",
            "output_format": "GeoJSON"
        }
        
        config = ExportConfiguration.from_dict(data)
        
        assert config.layer_ids == ["l1", "l2"]
        assert config.output_format == ExportFormat.GEOJSON


class TestExportExecution:
    """Tests for export execution."""
    
    def test_can_export_valid_config(self):
        """Test can_export with valid configuration."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1"])
        controller.set_output_path("/tmp/out.gpkg")
        
        assert controller.can_export() is True
    
    def test_can_export_invalid_config(self):
        """Test can_export with invalid configuration."""
        controller = create_exporting_controller()
        
        # No layers or path
        assert controller.can_export() is False
    
    def test_execute_export(self):
        """Test executing export."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1"])
        controller.set_output_path("/tmp/out.gpkg")
        
        result = controller.execute_export()
        
        assert result is True
    
    def test_is_exporting_initially_false(self):
        """Test is_exporting is false initially."""
        controller = create_exporting_controller()
        
        assert controller.is_exporting() is False
    
    def test_get_progress_initially_zero(self):
        """Test progress is 0 initially."""
        controller = create_exporting_controller()
        
        assert controller.get_progress() == 0.0
    
    def test_get_last_result(self):
        """Test getting last export result."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1"])
        controller.set_output_path("/tmp/out.gpkg")
        controller.execute_export()
        
        result = controller.get_last_result()
        
        assert result is not None
        assert result.success is True


class TestExportResult:
    """Tests for ExportResult dataclass."""
    
    def test_partial_success(self):
        """Test partial_success property."""
        from ui.controllers.exporting_controller import ExportResult
        
        # Full success
        full_success = ExportResult(
            success=True,
            exported_files=["a.gpkg", "b.gpkg"]
        )
        assert full_success.partial_success is False
        
        # Partial success
        partial = ExportResult(
            success=False,
            exported_files=["a.gpkg"],
            failed_layers=["layer_b"]
        )
        assert partial.partial_success is True
        
        # Full failure
        failure = ExportResult(
            success=False,
            failed_layers=["layer_a", "layer_b"]
        )
        assert failure.partial_success is False


class TestCallbacks:
    """Tests for callback registration."""
    
    def test_register_export_started_callback(self):
        """Test registering export started callback."""
        controller = create_exporting_controller()
        started_called = []
        
        def on_started():
            started_called.append(True)
        
        controller.register_export_started_callback(on_started)
        controller.set_layers_to_export(["l1"])
        controller.set_output_path("/tmp/out.gpkg")
        controller.execute_export()
        
        assert len(started_called) == 1
    
    def test_register_export_completed_callback(self):
        """Test registering export completed callback."""
        controller = create_exporting_controller()
        results_received = []
        
        def on_completed(result):
            results_received.append(result)
        
        controller.register_export_completed_callback(on_completed)
        controller.set_layers_to_export(["l1"])
        controller.set_output_path("/tmp/out.gpkg")
        controller.execute_export()
        
        assert len(results_received) == 1
        assert results_received[0].success is True
    
    def test_config_callback(self):
        """Test configuration change callback."""
        controller = create_exporting_controller()
        configs_received = []
        
        def on_config_changed(config):
            configs_received.append(config)
        
        controller.register_config_callback(on_config_changed)
        controller.set_layers_to_export(["l1"])
        
        assert len(configs_received) > 0


class TestLifecycle:
    """Tests for controller lifecycle."""
    
    def test_setup(self):
        """Test setup is called without error."""
        controller = create_exporting_controller()
        
        controller.setup()
        
        # No exception = success
    
    def test_teardown(self):
        """Test teardown cleans up state."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1", "l2"])
        controller.set_output_path("/tmp/out.gpkg")
        
        controller.teardown()
        
        assert controller.get_layers_to_export() == []
        assert controller.get_output_path() == ""
    
    def test_reset(self):
        """Test reset clears all configuration."""
        from ui.controllers.exporting_controller import ExportFormat
        
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1"])
        controller.set_output_format(ExportFormat.SHAPEFILE)
        controller.set_output_path("/tmp/out.shp")
        controller.set_output_crs("EPSG:4326")
        
        controller.reset()
        
        assert controller.get_layers_to_export() == []
        assert controller.get_output_format() == ExportFormat.GEOPACKAGE
        assert controller.get_output_path() == ""
        assert controller.get_output_crs() is None


class TestRepr:
    """Tests for string representation."""
    
    def test_repr(self):
        """Test repr output."""
        controller = create_exporting_controller()
        
        controller.set_layers_to_export(["l1", "l2"])
        controller.set_output_path("/tmp/export.gpkg")
        
        repr_str = repr(controller)
        
        assert "ExportingController" in repr_str
        assert "layers=2" in repr_str
        assert "GPKG" in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
