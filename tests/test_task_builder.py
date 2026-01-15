# -*- coding: utf-8 -*-
"""
Unit tests for TaskParameterBuilder.

Tests the task parameter building functionality.
"""
import pytest
from unittest.mock import Mock, MagicMock


def create_mock_dockwidget():
    """Create a mock dockwidget with widget attributes."""
    dw = Mock()
    
    # Buffer widgets
    dw.mQgsDoubleSpinBox_filtering_buffer_value = Mock()
    dw.mQgsDoubleSpinBox_filtering_buffer_value.value.return_value = 10.0
    
    dw.mQgsSpinBox_filtering_buffer_segments = Mock()
    dw.mQgsSpinBox_filtering_buffer_segments.value.return_value = 8
    
    dw.comboBox_filtering_buffer_type = Mock()
    dw.comboBox_filtering_buffer_type.currentText.return_value = "Round"
    
    # Geometric predicates widgets
    dw.pushButton_checkable_filtering_geometric_predicates = Mock()
    dw.pushButton_checkable_filtering_geometric_predicates.isChecked.return_value = True
    
    # FIX: Use comboBox_filtering_geometric_predicates with checkedItems() (QgsCheckableComboBox)
    dw.comboBox_filtering_geometric_predicates = Mock()
    dw.comboBox_filtering_geometric_predicates.checkedItems.return_value = ["intersects"]
    
    # Layers to filter widgets
    dw.pushButton_checkable_filtering_layers_to_filter = Mock()
    dw.pushButton_checkable_filtering_layers_to_filter.isChecked.return_value = True
    
    dw.get_layers_to_filter = Mock(return_value=["layer_1", "layer_2"])
    
    # Centroids checkboxes
    dw.checkBox_filtering_use_centroids_source_layer = Mock()
    dw.checkBox_filtering_use_centroids_source_layer.isChecked.return_value = False
    
    dw.checkBox_filtering_use_centroids_distant_layers = Mock()
    dw.checkBox_filtering_use_centroids_distant_layers.isChecked.return_value = True
    
    # Forced backends
    dw.forced_backends = {"layer_1": "ogr"}
    
    return dw


def create_mock_layer(layer_id="test_layer_123", name="Test Layer"):
    """Create a mock QGIS layer."""
    layer = Mock()
    layer.id.return_value = layer_id
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.providerType.return_value = "ogr"
    layer.geometryType.return_value = 2  # Polygon
    layer.subsetString.return_value = ""
    
    crs = Mock()
    crs.authid.return_value = "EPSG:4326"
    layer.crs.return_value = crs
    
    return layer


class TestFilteringConfig:
    """Tests for FilteringConfig dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        from adapters.task_builder import FilteringConfig
        
        config = FilteringConfig()
        
        assert config.buffer_value == 0.0
        assert config.buffer_segments == 5
        assert config.buffer_type == "Round"
        assert config.has_geometric_predicates is False
        assert config.geometric_predicates == []
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        from adapters.task_builder import FilteringConfig
        
        config = FilteringConfig(
            buffer_value=10.0,
            buffer_type="Flat",
            has_geometric_predicates=True,
            geometric_predicates=["intersects", "contains"]
        )
        
        result = config.to_dict()
        
        assert result["buffer_value"] == 10.0
        assert result["buffer_type"] == "Flat"
        assert result["has_geometric_predicates"] is True
        assert result["geometric_predicates"] == ["intersects", "contains"]


class TestLayerInfo:
    """Tests for LayerInfo dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        from adapters.task_builder import LayerInfo
        
        info = LayerInfo(
            layer_id="layer_123",
            layer_name="Test Layer",
            provider_type="postgresql",
            crs_authid="EPSG:4326",
            geometry_type="GeometryType.Polygon",
            is_subset=True
        )
        
        result = info.to_dict()
        
        assert result["layer_id"] == "layer_123"
        assert result["layer_name"] == "Test Layer"
        assert result["layer_provider_type"] == "postgresql"
        assert result["is_already_subset"] is True


class TestTaskParameterBuilder:
    """Tests for TaskParameterBuilder."""
    
    def test_build_filtering_config(self):
        """Test building FilteringConfig from UI."""
        from adapters.task_builder import TaskParameterBuilder
        
        dw = create_mock_dockwidget()
        builder = TaskParameterBuilder(dw, {})
        
        config = builder.build_filtering_config()
        
        assert config.buffer_value == 10.0
        assert config.buffer_segments == 8
        assert config.buffer_type == "Round"
        assert config.has_geometric_predicates is True
        assert "intersects" in config.geometric_predicates
        assert config.use_centroids_distant_layers is True
    
    def test_build_layer_info(self):
        """Test building LayerInfo from layer."""
        from adapters.task_builder import TaskParameterBuilder
        
        dw = create_mock_dockwidget()
        layer = create_mock_layer()
        
        builder = TaskParameterBuilder(dw, {})
        info = builder.build_layer_info(layer)
        
        assert info is not None
        assert info.layer_id == "test_layer_123"
        assert info.layer_name == "Test Layer"
        assert info.provider_type == "ogr"
        assert info.crs_authid == "EPSG:4326"
    
    def test_build_layer_info_with_stored_data(self):
        """Test building LayerInfo uses PROJECT_LAYERS data."""
        from adapters.task_builder import TaskParameterBuilder
        
        dw = create_mock_dockwidget()
        layer = create_mock_layer()
        
        project_layers = {
            "test_layer_123": {
                "infos": {
                    "layer_provider_type": "postgresql",
                    "layer_table_name": "my_table",
                    "layer_schema": "public",
                    "layer_geometry_field": "geom"
                }
            }
        }
        
        builder = TaskParameterBuilder(dw, project_layers)
        info = builder.build_layer_info(layer)
        
        assert info.provider_type == "postgresql"
        assert info.table_name == "my_table"
        assert info.schema == "public"
        assert info.geometry_field == "geom"
    
    def test_build_layer_info_returns_none_for_invalid(self):
        """Test returns None for invalid layer."""
        from adapters.task_builder import TaskParameterBuilder
        
        dw = create_mock_dockwidget()
        layer = create_mock_layer()
        layer.isValid.return_value = False
        
        builder = TaskParameterBuilder(dw, {})
        info = builder.build_layer_info(layer)
        
        assert info is None
    
    def test_build_filter_params(self):
        """Test building complete filter parameters."""
        from adapters.task_builder import TaskParameterBuilder, TaskType
        
        dw = create_mock_dockwidget()
        source = create_mock_layer("source_123", "Source Layer")
        target1 = create_mock_layer("target_1", "Target 1")
        target2 = create_mock_layer("target_2", "Target 2")
        
        builder = TaskParameterBuilder(dw, {})
        params = builder.build_filter_params(
            source_layer=source,
            target_layers=[target1, target2],
            features=[1, 2, 3],
            expression="id IN (1, 2, 3)"
        )
        
        assert params is not None
        assert params.task_type == TaskType.FILTER
        assert params.source_layer_info.layer_id == "source_123"
        assert len(params.target_layers) == 2
        assert params.features == [1, 2, 3]
        assert params.expression == "id IN (1, 2, 3)"
        assert params.filtering_config is not None
        assert params.forced_backends == {"layer_1": "ogr"}
    
    def test_build_filter_params_returns_none_no_targets(self):
        """Test returns None when no valid targets."""
        from adapters.task_builder import TaskParameterBuilder
        
        dw = create_mock_dockwidget()
        source = create_mock_layer()
        
        builder = TaskParameterBuilder(dw, {})
        params = builder.build_filter_params(
            source_layer=source,
            target_layers=[]  # No targets
        )
        
        assert params is None
    
    def test_clean_buffer_value_precision(self):
        """Test buffer value cleaning removes precision errors."""
        from adapters.task_builder import TaskParameterBuilder
        
        dw = create_mock_dockwidget()
        builder = TaskParameterBuilder(dw, {})
        
        # Test precision error cleaning
        assert builder._clean_buffer_value(0.9999999999999999) == 1.0
        assert builder._clean_buffer_value(1.0000000000000002) == 1.0
        assert builder._clean_buffer_value(10.5) == 10.5
        assert builder._clean_buffer_value(0.0) == 0.0


class TestTaskParameters:
    """Tests for TaskParameters dataclass."""
    
    def test_to_legacy_format(self):
        """Test conversion to legacy format."""
        from adapters.task_builder import (
            TaskParameters, TaskType, LayerInfo, FilteringConfig
        )
        
        source_info = LayerInfo(
            layer_id="layer_123",
            layer_name="Test",
            provider_type="ogr",
            crs_authid="EPSG:4326",
            geometry_type="GeometryType.Polygon"
        )
        
        target_info = LayerInfo(
            layer_id="target_1",
            layer_name="Target",
            provider_type="ogr",
            crs_authid="EPSG:4326",
            geometry_type="GeometryType.Point"
        )
        
        params = TaskParameters(
            task_type=TaskType.FILTER,
            source_layer_info=source_info,
            target_layers=[target_info],
            filtering_config=FilteringConfig(buffer_value=10.0),
            expression="test expression"
        )
        
        project_layers = {
            "layer_123": {
                "infos": {},
                "filtering": {}
            }
        }
        
        legacy = params.to_legacy_format(
            project_layers=project_layers,
            config_data={"test": True},
            project=Mock(),
            plugin_dir="/path/to/plugin"
        )
        
        assert "task" in legacy
        assert legacy["task"]["expression"] == "test expression"
        assert len(legacy["task"]["layers"]) == 1
        assert legacy["filtering"]["buffer_value"] == 10.0
        assert legacy["plugin_dir"] == "/path/to/plugin"
