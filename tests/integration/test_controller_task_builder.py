# -*- coding: utf-8 -*-
"""
Integration tests for Controller → TaskParameterBuilder → Legacy flow.

Tests the complete integration chain for the Strangler Fig migration pattern.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


def create_mock_layer(layer_id="layer_123", name="Test Layer", provider="ogr"):
    """Create a mock QGIS layer."""
    layer = Mock()
    layer.id.return_value = layer_id
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.providerType.return_value = provider
    layer.geometryType.return_value = 2  # Polygon
    layer.subsetString.return_value = ""
    
    crs = Mock()
    crs.authid.return_value = "EPSG:4326"
    layer.crs.return_value = crs
    
    return layer


def create_mock_dockwidget():
    """Create a mock dockwidget with required attributes."""
    dw = Mock()
    
    # Buffer widgets
    dw.mQgsDoubleSpinBox_filtering_buffer_value = Mock()
    dw.mQgsDoubleSpinBox_filtering_buffer_value.value.return_value = 10.0
    
    dw.mQgsSpinBox_filtering_buffer_segments = Mock()
    dw.mQgsSpinBox_filtering_buffer_segments.value.return_value = 8
    
    dw.comboBox_filtering_buffer_type = Mock()
    dw.comboBox_filtering_buffer_type.currentText.return_value = "Round"
    
    # Geometric predicates
    dw.pushButton_checkable_filtering_geometric_predicates = Mock()
    dw.pushButton_checkable_filtering_geometric_predicates.isChecked.return_value = True
    
    # FIX: Use comboBox_filtering_geometric_predicates with checkedItems() (QgsCheckableComboBox)
    dw.comboBox_filtering_geometric_predicates = Mock()
    dw.comboBox_filtering_geometric_predicates.checkedItems.return_value = ["intersects"]
    
    # Layers to filter
    dw.pushButton_checkable_filtering_layers_to_filter = Mock()
    dw.pushButton_checkable_filtering_layers_to_filter.isChecked.return_value = True
    dw.get_layers_to_filter = Mock(return_value=["target_1", "target_2"])
    
    # Centroids
    dw.checkBox_filtering_use_centroids_source_layer = Mock()
    dw.checkBox_filtering_use_centroids_source_layer.isChecked.return_value = False
    dw.checkBox_filtering_use_centroids_distant_layers = Mock()
    dw.checkBox_filtering_use_centroids_distant_layers.isChecked.return_value = False
    
    # Required for controller
    dw.current_layer = None
    dw.PROJECT_LAYERS = {}
    dw.forced_backends = {}
    
    # Mock get_current_features
    mock_feature = Mock()
    mock_feature.id.return_value = 1
    dw.get_current_features = Mock(return_value=([mock_feature], "id = 1"))
    
    # Tabs
    dw.tabTools = Mock()
    dw.tabTools.currentChanged = Mock()
    dw.tabTools.currentChanged.connect = Mock()
    
    # Signals
    dw.currentLayerChanged = Mock()
    dw.currentLayerChanged.connect = Mock()
    
    return dw


class TestControllerTaskBuilderIntegration:
    """Tests for FilteringController + TaskParameterBuilder integration."""
    
    def test_controller_builds_task_parameters(self):
        """Test controller can build TaskParameters via builder."""
        from ui.controllers.filtering_controller import (
            FilteringController, TASK_BUILDER_AVAILABLE
        )
        
        if not TASK_BUILDER_AVAILABLE:
            pytest.skip("TaskParameterBuilder not available")
        
        dw = create_mock_dockwidget()
        source_layer = create_mock_layer("source_123", "Source")
        target_layer = create_mock_layer("target_1", "Target")
        
        # Setup dockwidget state
        dw.current_layer = source_layer
        dw.PROJECT_LAYERS = {
            "source_123": {"infos": {}, "filtering": {}},
            "target_1": {"infos": {}, "filtering": {}}
        }
        
        # Create controller
        controller = FilteringController(dockwidget=dw)
        controller._source_layer = source_layer
        controller._target_layer_ids = ["target_1"]
        
        # Mock QgsProject
        with patch('qgis.core.QgsProject') as mock_project_class:
            mock_project = Mock()
            mock_project.mapLayer.return_value = target_layer
            mock_project_class.instance.return_value = mock_project
            
            # Build task parameters
            params = controller.build_task_parameters()
        
        assert params is not None
        assert params.source_layer_info.layer_id == "source_123"
        assert len(params.target_layers) == 1
        assert params.filtering_config is not None
        assert params.filtering_config.buffer_value == 10.0
    
    def test_controller_handles_missing_dockwidget(self):
        """Test controller returns None when dockwidget missing."""
        from ui.controllers.filtering_controller import (
            FilteringController, TASK_BUILDER_AVAILABLE
        )
        
        if not TASK_BUILDER_AVAILABLE:
            pytest.skip("TaskParameterBuilder not available")
        
        controller = FilteringController(dockwidget=None)
        params = controller.build_task_parameters()
        
        assert params is None
    
    def test_controller_handles_missing_source_layer(self):
        """Test controller returns None when source layer missing."""
        from ui.controllers.filtering_controller import (
            FilteringController, TASK_BUILDER_AVAILABLE
        )
        
        if not TASK_BUILDER_AVAILABLE:
            pytest.skip("TaskParameterBuilder not available")
        
        dw = create_mock_dockwidget()
        controller = FilteringController(dockwidget=dw)
        controller._source_layer = None
        
        params = controller.build_task_parameters()
        
        assert params is None


class TestControllerExecuteFilterIntegration:
    """Tests for execute_filter with TaskParameterBuilder."""
    
    def test_execute_filter_logs_task_params(self):
        """Test execute_filter logs TaskParameters when available."""
        from ui.controllers.filtering_controller import FilteringController
        
        dw = create_mock_dockwidget()
        source_layer = create_mock_layer("source_123", "Source")
        target_layer = create_mock_layer("target_1", "Target")
        
        dw.current_layer = source_layer
        dw.PROJECT_LAYERS = {
            "source_123": {"infos": {}, "filtering": {}},
            "target_1": {"infos": {}, "filtering": {}}
        }
        
        # Create controller with mock filter_service
        mock_service = Mock()
        controller = FilteringController(
            dockwidget=dw,
            filter_service=mock_service
        )
        controller._source_layer = source_layer
        controller._target_layer_ids = ["target_1"]
        
        # Mock QgsProject
        with patch('qgis.core.QgsProject') as mock_project_class:
            mock_project = Mock()
            mock_project.mapLayer.return_value = target_layer
            mock_project_class.instance.return_value = mock_project
            
            # Execute filter - should return False (delegating to legacy)
            result = controller.execute_filter()
        
        # Should delegate to legacy (return False)
        assert result is False
    
    def test_execute_filter_without_service(self):
        """Test execute_filter returns False without filter_service."""
        from ui.controllers.filtering_controller import FilteringController
        
        dw = create_mock_dockwidget()
        source_layer = create_mock_layer()
        
        controller = FilteringController(dockwidget=dw)
        controller._source_layer = source_layer
        controller._target_layer_ids = ["target_1"]
        
        result = controller.execute_filter()
        
        # Should return False - no filter service
        assert result is False


class TestTaskParametersToLegacy:
    """Tests for converting TaskParameters to legacy format."""
    
    def test_to_legacy_format_structure(self):
        """Test TaskParameters converts to expected legacy structure."""
        from adapters.task_builder import (
            TaskParameters, TaskType, LayerInfo, FilteringConfig
        )
        
        source_info = LayerInfo(
            layer_id="source_123",
            layer_name="Source Layer",
            provider_type="postgresql",
            crs_authid="EPSG:4326",
            geometry_type="GeometryType.Polygon"
        )
        
        target_info = LayerInfo(
            layer_id="target_1",
            layer_name="Target Layer",
            provider_type="postgresql",
            crs_authid="EPSG:4326",
            geometry_type="GeometryType.Point"
        )
        
        filtering_config = FilteringConfig(
            buffer_value=100.0,
            buffer_segments=8,
            buffer_type="Flat",
            has_geometric_predicates=True,
            geometric_predicates=["intersects", "contains"]
        )
        
        params = TaskParameters(
            task_type=TaskType.FILTER,
            source_layer_info=source_info,
            target_layers=[target_info],
            filtering_config=filtering_config,
            features=[1, 2, 3],
            expression="id IN (1,2,3)",
            forced_backends={"target_1": "ogr"}
        )
        
        project_layers = {
            "source_123": {
                "infos": {"layer_id": "source_123"},
                "filtering": {}
            }
        }
        
        legacy = params.to_legacy_format(
            project_layers=project_layers,
            config_data={"APP": {}},
            project=Mock(),
            plugin_dir="/path/to/plugin"
        )
        
        # Verify structure
        assert "task" in legacy
        assert "filtering" in legacy
        assert "plugin_dir" in legacy
        assert "forced_backends" in legacy
        
        # Verify task section
        assert legacy["task"]["expression"] == "id IN (1,2,3)"
        assert len(legacy["task"]["layers"]) == 1
        
        # Verify filtering section
        assert legacy["filtering"]["buffer_value"] == 100.0
        assert legacy["filtering"]["buffer_type"] == "Flat"
        assert legacy["filtering"]["geometric_predicates"] == ["intersects", "contains"]
        
        # Verify forced backends
        assert legacy["forced_backends"]["target_1"] == "ogr"
