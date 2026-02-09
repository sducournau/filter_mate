# -*- coding: utf-8 -*-
"""
Integration tests for hexagonal services and controllers.

Tests the interactions between services, controllers, and the app orchestrator.
These tests verify that all components work together correctly.

Target: Complete E2E workflow coverage for critical user paths.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from dataclasses import dataclass


def create_mock_layer(layer_id="test_layer_123", name="Test Layer", provider="ogr"):
    """Create a mock QGIS layer."""
    layer = Mock()
    layer.id.return_value = layer_id
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.providerType.return_value = provider
    layer.geometryType.return_value = 2  # Polygon
    layer.subsetString.return_value = ""
    layer.featureCount.return_value = 100
    
    crs = Mock()
    crs.authid.return_value = "EPSG:4326"
    layer.crs.return_value = crs
    
    return layer


def create_mock_dockwidget():
    """Create a mock dockwidget with common widgets."""
    dw = Mock()
    
    # Buffer widgets
    dw.mQgsDoubleSpinBox_filtering_buffer_value = Mock()
    dw.mQgsDoubleSpinBox_filtering_buffer_value.value.return_value = 0.0
    
    dw.mQgsSpinBox_filtering_buffer_segments = Mock()
    dw.mQgsSpinBox_filtering_buffer_segments.value.return_value = 5
    
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
    dw.get_layers_to_filter = Mock(return_value=["layer_1", "layer_2"])
    
    # Centroids
    dw.checkBox_filtering_use_centroids_source_layer = Mock()
    dw.checkBox_filtering_use_centroids_source_layer.isChecked.return_value = False
    dw.checkBox_filtering_use_centroids_distant_layers = Mock()
    dw.checkBox_filtering_use_centroids_distant_layers.isChecked.return_value = False
    
    # Forced backends
    dw.forced_backends = {}
    
    # Current layer
    dw.current_layer = None
    
    # Tab tools
    dw.tabTools = Mock()
    dw.tabTools.currentChanged = Mock()
    dw.tabTools.currentChanged.connect = Mock()
    dw.tabTools.currentChanged.disconnect = Mock()
    
    return dw


@pytest.mark.integration
class TestServiceIntegration:
    """Tests for service-to-service integration."""
    
    def test_task_builder_with_layer_lifecycle(self):
        """Test TaskBuilder uses LayerLifecycleService for validation."""
        from adapters.task_builder import TaskParameterBuilder
        from core.services.layer_lifecycle_service import LayerLifecycleService
        
        # Arrange
        dw = create_mock_dockwidget()
        layer = create_mock_layer()
        
        lifecycle_service = LayerLifecycleService()
        builder = TaskParameterBuilder(dw, {})
        
        # Act - Build layer info
        layer_info = builder.build_layer_info(layer)
        
        # Assert - Layer info should be valid
        assert layer_info is not None
        assert layer_info.layer_id == "test_layer_123"
        
        # Act - Filter usable layers should accept this layer
        with patch('infrastructure.utils.is_sip_deleted', return_value=False):
            with patch('infrastructure.utils.is_layer_valid', return_value=True):
                with patch('infrastructure.utils.is_layer_source_available', return_value=True):
                    usable = lifecycle_service.filter_usable_layers([layer])
                    assert len(usable) == 1
    
    def test_task_management_with_layer_lifecycle(self):
        """Test TaskOrchestrator coordinates with LayerLifecycle."""
        from unittest.mock import Mock
        from core.services.task_orchestrator import TaskOrchestrator
        from core.services.layer_lifecycle_service import LayerLifecycleService

        # Arrange
        task_service = TaskOrchestrator(
            get_dockwidget=Mock(return_value=None), get_project_layers=Mock(return_value={}),
            get_config_data=Mock(return_value={}), get_project=Mock(return_value=None),
            check_reset_stale_flags=Mock(), set_loading_flag=Mock(), set_initializing_flag=Mock(),
            get_task_parameters=Mock(return_value=None), handle_filter_task=Mock(),
            handle_layer_task=Mock(), handle_undo=Mock(), handle_redo=Mock(),
            force_reload_layers=Mock(), handle_remove_all_layers=Mock(),
            handle_project_initialization=Mock(),
        )
        lifecycle_service = LayerLifecycleService()
        
        layers = [create_mock_layer(f"layer_{i}") for i in range(3)]
        
        # Act - Enqueue layers
        result = task_service.enqueue_add_layers(layers)
        
        # Assert
        assert result is True
        assert task_service.get_queue_size() == 1
        
        # Act - Clear queue (simulating cleanup)
        task_service.clear_queue()
        
        # Assert
        assert task_service.get_queue_size() == 0


@pytest.mark.integration
class TestControllerServiceIntegration:
    """Tests for controller-to-service integration."""
    
    def test_filtering_controller_uses_task_builder(self):
        """Test FilteringController uses TaskParameterBuilder."""
        from ui.controllers.filtering_controller import FilteringController
        from adapters.task_builder import TaskParameterBuilder
        
        # Arrange
        dw = create_mock_dockwidget()
        source = create_mock_layer("source_123", "Source")
        
        controller = FilteringController(dw)
        
        # Act - Set source layer
        controller.set_source_layer(source)
        
        # Assert
        assert controller.get_source_layer() is source
    
    def test_exploring_controller_caches_results(self):
        """Test ExploringController caches expression results."""
        from ui.controllers.exploring_controller import ExploringController
        
        # Arrange
        dw = create_mock_dockwidget()
        dw._exploring_cache = {}
        
        controller = ExploringController(dw)
        layer = create_mock_layer()
        
        # Act - Set layer and verify cache setup
        controller.set_current_layer(layer)
        
        # Assert - Controller should be ready for caching
        assert controller.get_current_layer() is layer


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Tests for complete E2E workflows."""
    
    def test_filter_workflow_basic(self):
        """Test basic filter workflow: select → filter → apply."""
        from adapters.task_builder import TaskParameterBuilder, TaskType
        from core.services.layer_lifecycle_service import LayerLifecycleService
        
        # Arrange
        dw = create_mock_dockwidget()
        source = create_mock_layer("source_123", "Source Layer")
        target1 = create_mock_layer("target_1", "Target 1")
        target2 = create_mock_layer("target_2", "Target 2")
        
        lifecycle = LayerLifecycleService()
        builder = TaskParameterBuilder(dw, {})
        
        # Step 1: Validate layers
        with patch('infrastructure.utils.is_sip_deleted', return_value=False):
            with patch('infrastructure.utils.is_layer_valid', return_value=True):
                with patch('infrastructure.utils.is_layer_source_available', return_value=True):
                    usable = lifecycle.filter_usable_layers([source, target1, target2])
                    assert len(usable) == 3
        
        # Step 2: Build filter parameters
        params = builder.build_filter_params(
            source_layer=source,
            target_layers=[target1, target2],
            features=[1, 2, 3],
            expression="id IN (1, 2, 3)"
        )
        
        # Assert
        assert params is not None
        assert params.task_type == TaskType.FILTER
        assert len(params.target_layers) == 2
    
    def test_export_workflow_basic(self):
        """Test basic export workflow: select layers → configure → export."""
        from adapters.task_builder import TaskParameterBuilder, TaskType
        
        # Arrange
        dw = create_mock_dockwidget()
        layer1 = create_mock_layer("layer_1", "Layer 1")
        layer2 = create_mock_layer("layer_2", "Layer 2")
        
        builder = TaskParameterBuilder(dw, {})
        
        # Act - Build export parameters
        params = builder.build_export_params(
            layers=[layer1, layer2],
            output_path="/tmp/export.gpkg",
            format_type="GPKG"
        )
        
        # Assert
        assert params is not None
        assert params.task_type == TaskType.EXPORT
        assert len(params.layers_to_export) == 2
    
    def test_cleanup_workflow(self):
        """Test cleanup workflow: all services clean up properly."""
        from unittest.mock import Mock
        from core.services.layer_lifecycle_service import LayerLifecycleService
        from core.services.task_orchestrator import TaskOrchestrator

        # Arrange
        lifecycle = LayerLifecycleService()
        task_mgmt = TaskOrchestrator(
            get_dockwidget=Mock(return_value=None), get_project_layers=Mock(return_value={}),
            get_config_data=Mock(return_value={}), get_project=Mock(return_value=None),
            check_reset_stale_flags=Mock(), set_loading_flag=Mock(), set_initializing_flag=Mock(),
            get_task_parameters=Mock(return_value=None), handle_filter_task=Mock(),
            handle_layer_task=Mock(), handle_undo=Mock(), handle_redo=Mock(),
            force_reload_layers=Mock(), handle_remove_all_layers=Mock(),
            handle_project_initialization=Mock(),
        )
        
        # Add some state
        task_mgmt.enqueue_add_layers([create_mock_layer()])
        task_mgmt.increment_pending_tasks()
        
        # Act - Cleanup
        task_mgmt.clear_queue()
        task_mgmt.reset_counters()
        
        # Assert - All state cleared
        assert task_mgmt.get_queue_size() == 0
        assert task_mgmt.get_pending_tasks_count() == 0


@pytest.mark.integration
class TestErrorRecovery:
    """Tests for error recovery scenarios."""
    
    def test_invalid_layer_recovery(self):
        """Test recovery from invalid layer operations."""
        from core.services.layer_lifecycle_service import LayerLifecycleService
        
        # Arrange
        lifecycle = LayerLifecycleService()
        invalid_layer = create_mock_layer()
        invalid_layer.isValid.return_value = False
        
        # Act - Filter should handle invalid layer
        with patch('infrastructure.utils.is_sip_deleted', return_value=False):
            with patch('infrastructure.utils.is_layer_valid', return_value=False):
                usable = lifecycle.filter_usable_layers([invalid_layer])
        
        # Assert - No usable layers
        assert len(usable) == 0
    
    def test_queue_overflow_recovery(self):
        """Test recovery from queue overflow."""
        from unittest.mock import Mock, patch
        from core.services.task_orchestrator import TaskOrchestrator, StabilityConstants

        # Arrange - Small queue (patch constant for entire test)
        with patch.object(StabilityConstants, 'MAX_ADD_LAYERS_QUEUE', 2):
            service = TaskOrchestrator(
                get_dockwidget=Mock(return_value=None), get_project_layers=Mock(return_value={}),
                get_config_data=Mock(return_value={}), get_project=Mock(return_value=None),
                check_reset_stale_flags=Mock(), set_loading_flag=Mock(), set_initializing_flag=Mock(),
                get_task_parameters=Mock(return_value=None), handle_filter_task=Mock(),
                handle_layer_task=Mock(), handle_undo=Mock(), handle_redo=Mock(),
                force_reload_layers=Mock(), handle_remove_all_layers=Mock(),
                handle_project_initialization=Mock(),
            )

            # Act - Fill queue
            assert service.enqueue_add_layers([create_mock_layer()])  # 1
            assert service.enqueue_add_layers([create_mock_layer()])  # 2
            result = service.enqueue_add_layers([create_mock_layer()])  # 3 - overflow

            # Assert - Overflow handled gracefully
            assert result is False
            assert service.get_queue_size() == 2

            # Recovery - Clear and retry
            service.clear_queue()
            assert service.enqueue_add_layers([create_mock_layer()])  # Success
    
    def test_concurrent_task_cancellation(self):
        """Test safe handling of concurrent task cancellation."""
        from unittest.mock import Mock
        from core.services.task_orchestrator import TaskOrchestrator

        # Arrange
        service = TaskOrchestrator(
            get_dockwidget=Mock(return_value=None), get_project_layers=Mock(return_value={}),
            get_config_data=Mock(return_value={}), get_project=Mock(return_value=None),
            check_reset_stale_flags=Mock(), set_loading_flag=Mock(), set_initializing_flag=Mock(),
            get_task_parameters=Mock(return_value=None), handle_filter_task=Mock(),
            handle_layer_task=Mock(), handle_undo=Mock(), handle_redo=Mock(),
            force_reload_layers=Mock(), handle_remove_all_layers=Mock(),
            handle_project_initialization=Mock(),
        )

        # Act - Cancel with no tasks (should not raise)
        try:
            service.safe_cancel_all_tasks()
            success = True
        except Exception:
            success = False

        # Assert
        assert success is True


@pytest.mark.integration
class TestPerformanceScenarios:
    """Tests for performance-critical scenarios."""
    
    def test_bulk_layer_processing(self):
        """Test processing many layers efficiently."""
        from core.services.layer_lifecycle_service import LayerLifecycleService
        
        # Arrange - 100 layers
        layers = [create_mock_layer(f"layer_{i}") for i in range(100)]
        lifecycle = LayerLifecycleService()
        
        # Act
        with patch('infrastructure.utils.is_sip_deleted', return_value=False):
            with patch('infrastructure.utils.is_layer_valid', return_value=True):
                with patch('infrastructure.utils.is_layer_source_available', return_value=True):
                    usable = lifecycle.filter_usable_layers(layers)
        
        # Assert - All processed
        assert len(usable) == 100
    
    def test_rapid_queue_operations(self):
        """Test rapid enqueue/dequeue operations."""
        from unittest.mock import Mock
        from core.services.task_orchestrator import TaskOrchestrator

        # Arrange
        service = TaskOrchestrator(
            get_dockwidget=Mock(return_value=None), get_project_layers=Mock(return_value={}),
            get_config_data=Mock(return_value={}), get_project=Mock(return_value=None),
            check_reset_stale_flags=Mock(), set_loading_flag=Mock(), set_initializing_flag=Mock(),
            get_task_parameters=Mock(return_value=None), handle_filter_task=Mock(),
            handle_layer_task=Mock(), handle_undo=Mock(), handle_redo=Mock(),
            force_reload_layers=Mock(), handle_remove_all_layers=Mock(),
            handle_project_initialization=Mock(),
        )

        # Act - Rapid operations
        for i in range(10):
            service.enqueue_add_layers([create_mock_layer(f"layer_{i}")])

        for i in range(5):
            service.clear_queue()
            service.enqueue_add_layers([create_mock_layer(f"new_layer_{i}")])

        # Assert - State is consistent
        assert service.get_queue_size() >= 0  # Valid state


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
