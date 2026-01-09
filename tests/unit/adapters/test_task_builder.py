"""
Unit tests for TaskParameterBuilder.

Tests the task parameter building logic in the adapters layer.
Target: >80% code coverage.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from adapters.task_builder import TaskParameterBuilder


@pytest.mark.unit
class TestTaskParameterBuilder:
    """Tests for TaskParameterBuilder adapter."""
    
    @pytest.fixture
    def mock_iface(self):
        """Mock QGIS interface."""
        iface = Mock()
        iface.messageBar.return_value = Mock()
        return iface
    
    @pytest.fixture
    def builder(self, mock_iface):
        """Create TaskParameterBuilder instance."""
        return TaskParameterBuilder(iface=mock_iface)
    
    # === build_common_task_params() tests ===
    
    def test_build_common_task_params_basic(self, builder):
        """Should build common parameters with basic inputs."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.providerType.return_value = "postgres"
        
        task_type = "filter"
        layer_name = "Test Layer"
        
        # Act
        result = builder.build_common_task_params(
            task_type=task_type,
            layer=mock_layer,
            layer_name=layer_name
        )
        
        # Assert
        assert result is not None
        assert result["task_type"] == "filter"
        assert result["layer_id"] == "layer_123"
        assert result["layer_name"] == "Test Layer"
        assert result["provider_type"] == "postgres"
    
    def test_build_common_task_params_with_expression(self, builder):
        """Should include expression when provided."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.providerType.return_value = "postgres"
        
        expression = "area > 1000"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name="Test Layer",
            expression=expression
        )
        
        # Assert
        assert result["expression"] == "area > 1000"
    
    def test_build_common_task_params_with_backend(self, builder):
        """Should include backend type when specified."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.providerType.return_value = "postgres"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name="Test Layer",
            backend="postgresql"
        )
        
        # Assert
        assert result["backend"] == "postgresql"
    
    def test_build_common_task_params_none_layer_raises(self, builder):
        """Should raise ValueError when layer is None."""
        # Act & Assert
        with pytest.raises((ValueError, TypeError, AttributeError)):
            builder.build_common_task_params(
                task_type="filter",
                layer=None,
                layer_name="Test"
            )
    
    def test_build_common_task_params_invalid_task_type(self, builder):
        """Should handle invalid task type gracefully."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        mock_layer.providerType.return_value = "postgres"
        
        # Act
        result = builder.build_common_task_params(
            task_type="invalid_type",
            layer=mock_layer,
            layer_name="Test Layer"
        )
        
        # Assert - should still build params
        assert result is not None
        assert result["task_type"] == "invalid_type"
    
    # === build_layer_management_params() tests ===
    
    def test_build_layer_management_params_basic(self, builder):
        """Should build layer management parameters."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        
        # Act
        result = builder.build_layer_management_params(
            layer=mock_layer,
            operation="add"
        )
        
        # Assert
        assert result is not None
        assert result["layer_id"] == "layer_123"
        assert result["layer_name"] == "Test Layer"
        assert result["operation"] == "add"
    
    def test_build_layer_management_params_with_options(self, builder):
        """Should include additional options when provided."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Test Layer"
        
        options = {
            "auto_refresh": True,
            "cleanup_on_remove": True
        }
        
        # Act
        result = builder.build_layer_management_params(
            layer=mock_layer,
            operation="remove",
            options=options
        )
        
        # Assert
        assert result["operation"] == "remove"
        assert result.get("auto_refresh") is True
        assert result.get("cleanup_on_remove") is True
    
    def test_build_layer_management_params_multiple_layers(self, builder):
        """Should handle multiple layers."""
        # Arrange
        mock_layer1 = Mock()
        mock_layer1.id.return_value = "layer_1"
        mock_layer1.name.return_value = "Layer 1"
        
        mock_layer2 = Mock()
        mock_layer2.id.return_value = "layer_2"
        mock_layer2.name.return_value = "Layer 2"
        
        layers = [mock_layer1, mock_layer2]
        
        # Act - build for each layer
        results = [
            builder.build_layer_management_params(layer, "add")
            for layer in layers
        ]
        
        # Assert
        assert len(results) == 2
        assert results[0]["layer_id"] == "layer_1"
        assert results[1]["layer_id"] == "layer_2"
    
    # === Integration with layer providers ===
    
    def test_build_params_postgres_provider(self, builder):
        """Should handle PostgreSQL provider correctly."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "pg_layer"
        mock_layer.name.return_value = "PG Layer"
        mock_layer.providerType.return_value = "postgres"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name="PG Layer"
        )
        
        # Assert
        assert result["provider_type"] == "postgres"
    
    def test_build_params_spatialite_provider(self, builder):
        """Should handle Spatialite provider correctly."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "sl_layer"
        mock_layer.name.return_value = "SL Layer"
        mock_layer.providerType.return_value = "spatialite"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name="SL Layer"
        )
        
        # Assert
        assert result["provider_type"] == "spatialite"
    
    def test_build_params_ogr_provider(self, builder):
        """Should handle OGR provider correctly."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "ogr_layer"
        mock_layer.name.return_value = "OGR Layer"
        mock_layer.providerType.return_value = "ogr"
        
        # Act
        result = builder.build_common_task_params(
            task_type="export",
            layer=mock_layer,
            layer_name="OGR Layer"
        )
        
        # Assert
        assert result["provider_type"] == "ogr"
    
    # === Edge cases ===
    
    def test_build_params_empty_layer_name(self, builder):
        """Should handle empty layer name."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = ""
        mock_layer.providerType.return_value = "postgres"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name=""
        )
        
        # Assert
        assert result is not None
        assert result["layer_name"] == ""
    
    def test_build_params_special_characters_in_name(self, builder):
        """Should handle special characters in layer name."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Layer with 'quotes' and \"double\""
        mock_layer.providerType.return_value = "postgres"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name="Layer with 'quotes' and \"double\""
        )
        
        # Assert
        assert result is not None
        assert "quotes" in result["layer_name"]
    
    def test_build_params_unicode_layer_name(self, builder):
        """Should handle Unicode in layer name."""
        # Arrange
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        mock_layer.name.return_value = "Couche avec accents éàù"
        mock_layer.providerType.return_value = "postgres"
        
        # Act
        result = builder.build_common_task_params(
            task_type="filter",
            layer=mock_layer,
            layer_name="Couche avec accents éàù"
        )
        
        # Assert
        assert result is not None
        assert "Couche" in result["layer_name"]


# Run with: pytest tests/unit/adapters/test_task_builder.py -v --cov=adapters/task_builder
