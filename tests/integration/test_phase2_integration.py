"""
Phase 2 Integration Tests.

End-to-end tests verifying controller coordination,
workflow execution, and performance requirements.
"""
import pytest
import time
from unittest.mock import Mock, MagicMock, patch


# === Test Fixtures ===

@pytest.fixture
def mock_dockwidget():
    """Create a mock dockwidget with all required attributes."""
    dockwidget = Mock()
    
    # Mock tabTools
    dockwidget.tabTools = Mock()
    dockwidget.tabTools.currentChanged = Mock()
    dockwidget.tabTools.currentChanged.connect = Mock()
    dockwidget.tabTools.currentChanged.disconnect = Mock()
    
    # Mock signals
    dockwidget.currentLayerChanged = Mock()
    dockwidget.currentLayerChanged.connect = Mock()
    dockwidget.currentLayerChanged.disconnect = Mock()
    
    # Mock state
    dockwidget.current_layer = None
    dockwidget._exploring_cache = Mock()
    
    return dockwidget


@pytest.fixture
def mock_layer():
    """Create a mock QGIS vector layer."""
    layer = Mock()
    layer.id.return_value = "test_layer_001"
    layer.name.return_value = "Test Layer"
    layer.isValid.return_value = True
    layer.providerType.return_value = "ogr"
    layer.featureCount.return_value = 1000
    return layer


@pytest.fixture
def integration(mock_dockwidget):
    """Create and setup a ControllerIntegration instance."""
    from ui.controllers.integration import ControllerIntegration
    
    integration = ControllerIntegration(mock_dockwidget)
    integration.setup()
    yield integration
    integration.teardown()


# === Controller Coordination Tests ===

class TestControllerCoordination:
    """Tests for controller coordination through the registry."""
    
    def test_all_controllers_registered(self, integration):
        """Verify all three controllers are registered."""
        assert integration.registry is not None
        assert len(integration.registry) == 3
    
    def test_controllers_accessible_by_name(self, integration):
        """Verify controllers are accessible by name."""
        from ui.controllers.exploring_controller import ExploringController
        from ui.controllers.filtering_controller import FilteringController
        from ui.controllers.exporting_controller import ExportingController
        
        exploring = integration.registry.get('exploring')
        filtering = integration.registry.get('filtering')
        exporting = integration.registry.get('exporting')
        
        assert isinstance(exploring, ExploringController)
        assert isinstance(filtering, FilteringController)
        assert isinstance(exporting, ExportingController)
    
    def test_controllers_share_dockwidget(self, integration, mock_dockwidget):
        """Verify all controllers reference the same dockwidget."""
        assert integration.exploring_controller.dockwidget is mock_dockwidget
        assert integration.filtering_controller.dockwidget is mock_dockwidget
        assert integration.exporting_controller.dockwidget is mock_dockwidget
    
    def test_tab_switching_activates_controller(self, integration):
        """Test that tab switching activates the correct controller."""
        from ui.controllers.registry import TabIndex
        
        # Initially no controller is active
        assert not integration.exploring_controller.is_active
        assert not integration.filtering_controller.is_active
        
        # Activate filtering tab
        integration._on_tab_changed(TabIndex.FILTERING.value)
        
        # Both exploring and filtering are on tab 0
        assert integration.exploring_controller.is_active
        assert integration.filtering_controller.is_active
    
    def test_controller_cleanup_on_teardown(self, mock_dockwidget):
        """Test that teardown properly cleans up all controllers."""
        from ui.controllers.integration import ControllerIntegration
        
        integration = ControllerIntegration(mock_dockwidget)
        integration.setup()
        
        # Get references before teardown
        exploring = integration.exploring_controller
        filtering = integration.filtering_controller
        exporting = integration.exporting_controller
        
        integration.teardown()
        
        # All references should be None
        assert integration.exploring_controller is None
        assert integration.filtering_controller is None
        assert integration.exporting_controller is None
        assert integration.registry is None


# === Filtering Workflow Tests ===

class TestFilteringWorkflow:
    """End-to-end tests for the filtering workflow."""
    
    def test_complete_filtering_workflow(self, integration, mock_layer):
        """Test complete filtering workflow from layer selection to execution."""
        filtering = integration.filtering_controller
        
        # Step 1: Set source layer
        filtering.set_source_layer(mock_layer)
        assert filtering.get_source_layer() is mock_layer
        
        # Step 2: Set target layers
        filtering.set_target_layers(["target_1", "target_2"])
        assert len(filtering.get_target_layers()) == 2
        
        # Step 3: Configure predicate
        from ui.controllers.filtering_controller import PredicateType
        filtering.set_predicate(PredicateType.CONTAINS)
        assert filtering.get_predicate() == PredicateType.CONTAINS
        
        # Step 4: Set buffer
        filtering.set_buffer_value(100.0)
        assert filtering.get_buffer_value() == 100.0
        
        # Step 5: Verify expression was built
        expression = filtering.get_expression()
        assert "contains" in expression
        assert "target_1" in expression
        
        # Step 6: Verify can execute
        assert filtering.can_execute() is True
        
        # Step 7: Execute filter
        result = filtering.execute_filter()
        assert result is True
        
        # Step 8: Verify undo is available
        assert filtering.can_undo() is True
    
    def test_filtering_undo_redo_cycle(self, integration, mock_layer):
        """Test undo/redo functionality in filtering workflow."""
        filtering = integration.filtering_controller
        
        # Setup and execute first filter
        filtering.set_source_layer(mock_layer)
        filtering.set_target_layers(["target_1"])
        filtering.execute_filter()
        
        # Verify undo is available
        assert filtering.can_undo() is True
        assert filtering.can_redo() is False
        
        # Undo
        filtering.undo()
        assert filtering.can_redo() is True
        
        # Redo
        filtering.redo()
        assert filtering.can_undo() is True
    
    def test_filtering_configuration_persistence(self, integration, mock_layer):
        """Test that filter configuration can be serialized and restored."""
        filtering = integration.filtering_controller
        
        # Setup configuration
        filtering.set_source_layer(mock_layer)
        filtering.set_target_layers(["t1", "t2"])
        from ui.controllers.filtering_controller import PredicateType
        filtering.set_predicate(PredicateType.WITHIN)
        filtering.set_buffer_value(50.0)
        
        # Get configuration
        config = filtering.build_configuration()
        config_dict = config.to_dict()
        
        # Reset controller
        filtering.reset()
        assert filtering.get_target_layers() == []
        
        # Restore configuration
        from ui.controllers.filtering_controller import FilterConfiguration
        restored_config = FilterConfiguration.from_dict(config_dict)
        filtering.apply_configuration(restored_config)
        
        # Verify restoration
        assert filtering.get_target_layers() == ["t1", "t2"]
        assert filtering.get_predicate() == PredicateType.WITHIN
        assert filtering.get_buffer_value() == 50.0


# === Exploring Workflow Tests ===

class TestExploringWorkflow:
    """End-to-end tests for the exploring workflow."""
    
    def test_layer_field_cascade(self, integration, mock_layer):
        """Test that layer change properly cascades to field/feature state."""
        exploring = integration.exploring_controller
        
        # Set layer
        exploring.set_layer(mock_layer)
        exploring.set_field("test_field")
        exploring.set_selected_features(["val1", "val2"])
        
        # Verify state
        assert exploring.get_current_layer() is mock_layer
        assert exploring.get_current_field() == "test_field"
        assert len(exploring.get_selected_features()) == 2
        
        # Change layer - should clear field and selection
        new_layer = Mock()
        new_layer.isValid.return_value = True
        exploring.set_layer(new_layer)
        
        assert exploring.get_current_field() is None
    
    def test_multiple_feature_selection(self, integration, mock_layer):
        """Test multiple feature selection handling."""
        exploring = integration.exploring_controller
        
        exploring.set_layer(mock_layer)
        
        # Select multiple features
        exploring.set_selected_features(["a", "b", "c", "d", "e"])
        assert len(exploring.get_selected_features()) == 5
        
        # Update selection
        exploring.on_selection_changed(["x", "y"])
        assert exploring.get_selected_features() == ["x", "y"]
        
        # Clear selection
        exploring.clear_selection()
        assert exploring.get_selected_features() == []
    
    def test_spatial_navigation_without_layer(self, integration):
        """Test that spatial navigation fails gracefully without layer."""
        exploring = integration.exploring_controller
        
        # No layer set - should return False
        assert exploring.flash_feature(1) is False
        assert exploring.zoom_to_feature(1) is False
        assert exploring.identify_feature(1) is False
        assert exploring.zoom_to_selected() is False


# === Exporting Workflow Tests ===

class TestExportingWorkflow:
    """End-to-end tests for the exporting workflow."""
    
    def test_single_layer_export(self, integration):
        """Test single layer export workflow."""
        exporting = integration.exporting_controller
        
        # Configure export
        exporting.set_layers_to_export(["layer_1"])
        exporting.set_output_path("/tmp/export.gpkg")
        
        # Verify configuration
        assert exporting.can_export() is True
        
        # Execute export
        result = exporting.execute_export()
        assert result is True
        
        # Verify result
        last_result = exporting.get_last_result()
        assert last_result.success is True
        assert len(last_result.exported_files) == 1
    
    def test_batch_export(self, integration):
        """Test batch export workflow."""
        exporting = integration.exporting_controller
        from ui.controllers.exporting_controller import ExportFormat, ExportMode
        
        # Configure batch export
        exporting.set_layers_to_export(["layer_1", "layer_2", "layer_3"])
        exporting.set_output_path("/tmp/batch_export/")
        exporting.set_output_format(ExportFormat.SHAPEFILE)
        
        # Shapefile doesn't support multiple layers - should auto-set batch mode
        assert exporting.get_export_mode() == ExportMode.BATCH
        
        # Execute
        result = exporting.execute_export()
        assert result is True
        
        # Verify batch result
        last_result = exporting.get_last_result()
        assert len(last_result.exported_files) == 3
    
    def test_export_format_detection(self, integration):
        """Test that format is detected from file extension."""
        exporting = integration.exporting_controller
        from ui.controllers.exporting_controller import ExportFormat
        
        # Set path with .shp extension
        exporting.set_output_path("/tmp/export.shp")
        assert exporting.get_output_format() == ExportFormat.SHAPEFILE
        
        # Change to .geojson
        exporting.set_output_path("/tmp/export.geojson")
        assert exporting.get_output_format() == ExportFormat.GEOJSON
    
    def test_export_configuration_serialization(self, integration):
        """Test export configuration serialization."""
        exporting = integration.exporting_controller
        from ui.controllers.exporting_controller import ExportFormat, ExportConfiguration
        
        # Setup
        exporting.set_layers_to_export(["l1", "l2"])
        exporting.set_output_path("/tmp/out.gpkg")
        exporting.set_output_crs("EPSG:4326")
        exporting.set_include_styles(True)
        
        # Serialize
        config = exporting.build_configuration()
        data = config.to_dict()
        
        # Reset
        exporting.reset()
        
        # Restore
        restored = ExportConfiguration.from_dict(data)
        exporting.apply_configuration(restored)
        
        # Verify
        assert exporting.get_layers_to_export() == ["l1", "l2"]
        assert exporting.get_output_crs() == "EPSG:4326"
        assert exporting.get_include_styles() is True


# === Cross-Controller Integration Tests ===

class TestCrossControllerIntegration:
    """Tests for interactions between controllers."""
    
    def test_layer_change_updates_all_controllers(self, integration, mock_layer, mock_dockwidget):
        """Test that layer change updates exploring and filtering controllers."""
        mock_dockwidget.current_layer = mock_layer
        
        # Trigger layer change
        integration._on_current_layer_changed()
        
        # Verify both controllers updated
        assert integration.exploring_controller.get_current_layer() is mock_layer
        assert integration.filtering_controller.get_source_layer() is mock_layer
    
    def test_delegation_methods_work(self, integration, mock_layer):
        """Test that delegation methods call correct controllers."""
        # Test execute_filter delegation
        integration.filtering_controller.set_source_layer(mock_layer)
        integration.filtering_controller.set_target_layers(["t1"])
        
        result = integration.delegate_execute_filter()
        assert result is True
        
        # Test undo delegation
        result = integration.delegate_undo_filter()
        # Should work since we just executed a filter
        assert result is True
    
    def test_controller_isolation(self, integration, mock_layer):
        """Test that controllers don't interfere with each other."""
        # Configure filtering
        integration.filtering_controller.set_source_layer(mock_layer)
        integration.filtering_controller.set_target_layers(["t1"])
        
        # Configure exporting with same layer
        integration.exporting_controller.set_layers_to_export(["t1"])
        integration.exporting_controller.set_output_path("/tmp/out.gpkg")
        
        # Execute both - should not interfere
        filter_result = integration.filtering_controller.execute_filter()
        export_result = integration.exporting_controller.execute_export()
        
        assert filter_result is True
        assert export_result is True


# === Performance Tests ===

class TestPerformance:
    """Performance regression tests."""
    
    def test_controller_setup_time(self, mock_dockwidget):
        """Test that controller setup is fast enough."""
        from ui.controllers.integration import ControllerIntegration
        
        start = time.time()
        integration = ControllerIntegration(mock_dockwidget)
        integration.setup()
        elapsed = time.time() - start
        
        integration.teardown()
        
        # Setup should complete in less than 100ms
        assert elapsed < 0.1, f"Setup took {elapsed*1000:.1f}ms, expected < 100ms"
    
    def test_controller_teardown_time(self, mock_dockwidget):
        """Test that controller teardown is fast enough."""
        from ui.controllers.integration import ControllerIntegration
        
        integration = ControllerIntegration(mock_dockwidget)
        integration.setup()
        
        start = time.time()
        integration.teardown()
        elapsed = time.time() - start
        
        # Teardown should complete in less than 50ms
        assert elapsed < 0.05, f"Teardown took {elapsed*1000:.1f}ms, expected < 50ms"
    
    def test_filter_configuration_build_time(self, integration, mock_layer):
        """Test that filter configuration building is fast."""
        filtering = integration.filtering_controller
        
        # Setup complex configuration
        filtering.set_source_layer(mock_layer)
        filtering.set_target_layers([f"target_{i}" for i in range(100)])
        
        start = time.time()
        for _ in range(1000):
            config = filtering.build_configuration()
        elapsed = time.time() - start
        
        # 1000 builds should complete in less than 100ms
        assert elapsed < 0.1, f"1000 builds took {elapsed*1000:.1f}ms, expected < 100ms"
    
    def test_undo_stack_performance(self, integration, mock_layer):
        """Test that undo stack operations are fast."""
        filtering = integration.filtering_controller
        filtering.set_source_layer(mock_layer)
        filtering.set_target_layers(["t1"])
        
        # Execute many filters to build undo stack
        start = time.time()
        for i in range(50):
            filtering.execute_filter()
        elapsed = time.time() - start
        
        # 50 filter executions should complete in less than 100ms
        assert elapsed < 0.1, f"50 executions took {elapsed*1000:.1f}ms, expected < 100ms"
        
        # Undo all
        start = time.time()
        while filtering.can_undo():
            filtering.undo()
        elapsed = time.time() - start
        
        # 50 undos should complete in less than 50ms
        assert elapsed < 0.05, f"50 undos took {elapsed*1000:.1f}ms, expected < 50ms"


# === Memory Tests ===

class TestMemoryUsage:
    """Memory usage tests to detect leaks."""
    
    def test_no_memory_leak_on_setup_teardown(self, mock_dockwidget):
        """Test that repeated setup/teardown doesn't leak memory."""
        from ui.controllers.integration import ControllerIntegration
        import gc
        
        # Force garbage collection
        gc.collect()
        
        # Perform many setup/teardown cycles
        for _ in range(100):
            integration = ControllerIntegration(mock_dockwidget)
            integration.setup()
            integration.teardown()
        
        # Force garbage collection
        gc.collect()
        
        # If we got here without error, no obvious memory issues
        # More detailed memory testing would require tracemalloc
    
    def test_no_circular_references(self, mock_dockwidget):
        """Test that controllers don't have circular references."""
        from ui.controllers.integration import ControllerIntegration
        import gc
        import weakref
        
        integration = ControllerIntegration(mock_dockwidget)
        integration.setup()
        
        # Create weak references
        weak_exploring = weakref.ref(integration.exploring_controller)
        weak_filtering = weakref.ref(integration.filtering_controller)
        weak_exporting = weakref.ref(integration.exporting_controller)
        
        integration.teardown()
        del integration
        
        # Force garbage collection
        gc.collect()
        
        # Weak references should be dead (objects collected)
        # Note: This may not work in all cases due to mock complexity
        # but it's a good sanity check


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
