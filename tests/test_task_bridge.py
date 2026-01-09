# -*- coding: utf-8 -*-
"""
Unit tests for TaskBridge.

Tests the Strangler Fig pattern bridge between legacy FilterEngineTask
and v3 hexagonal backends.

MIG-023: FilterTask Split Migration
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass


# ============================================================================
# Mock Fixtures
# ============================================================================

def create_mock_layer(
    layer_id: str = "test_layer_123",
    name: str = "Test Layer",
    provider_type: str = "ogr",
    feature_count: int = 100
):
    """Create a mock QGIS vector layer."""
    layer = Mock()
    layer.id.return_value = layer_id
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.providerType.return_value = provider_type
    layer.geometryType.return_value = 2  # Polygon
    layer.subsetString.return_value = ""
    layer.featureCount.return_value = feature_count
    
    # CRS
    crs = Mock()
    crs.authid.return_value = "EPSG:4326"
    layer.crs.return_value = crs
    
    # Data provider
    provider = Mock()
    provider.geometryColumn.return_value = "geom"
    layer.dataProvider.return_value = provider
    
    return layer


def create_mock_backend_factory():
    """Create a mock BackendFactory."""
    factory = Mock()
    
    # Create a mock backend
    backend = Mock()
    backend_info = Mock()
    backend_info.name = "mock_backend"
    backend.get_info.return_value = backend_info
    
    # Mock execution result
    result = Mock()
    result.is_success = True
    result.feature_ids = {1, 2, 3, 4, 5}
    result.count = 5
    result.error_message = ""
    backend.execute.return_value = result
    
    factory.get_backend.return_value = backend
    
    return factory


# ============================================================================
# BridgeResult Tests
# ============================================================================

class TestBridgeResult:
    """Tests for BridgeResult dataclass."""
    
    def test_default_creation(self):
        """Test creating BridgeResult with defaults."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult(
            status=BridgeStatus.SUCCESS,
            success=True
        )
        
        assert result.status == BridgeStatus.SUCCESS
        assert result.success is True
        assert result.feature_ids == []
        assert result.feature_count == 0
        assert result.execution_time_ms == 0.0
    
    def test_fallback_factory(self):
        """Test BridgeResult.fallback() factory method."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult.fallback("Test reason")
        
        assert result.status == BridgeStatus.FALLBACK
        assert result.success is False
        assert result.error_message == "Test reason"
    
    def test_not_available_factory(self):
        """Test BridgeResult.not_available() factory method."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult.not_available()
        
        assert result.status == BridgeStatus.NOT_AVAILABLE
        assert result.success is False
    
    def test_to_legacy_format(self):
        """Test BridgeResult serialization to legacy format."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult(
            status=BridgeStatus.SUCCESS,
            success=True,
            feature_ids=[1, 2, 3],
            feature_count=3,
            execution_time_ms=123.45,
            backend_used="postgresql"
        )
        
        d = result.to_legacy_format()
        
        assert d['success'] is True
        assert d['feature_ids'] == [1, 2, 3]
        assert d['execution_time_ms'] == 123.45
        assert d['backend'] == 'postgresql'


# ============================================================================
# BridgeStatus Tests
# ============================================================================

class TestBridgeStatus:
    """Tests for BridgeStatus enum."""
    
    def test_all_statuses_exist(self):
        """Test all required statuses are defined."""
        from adapters.task_bridge import BridgeStatus
        
        assert hasattr(BridgeStatus, 'SUCCESS')
        assert hasattr(BridgeStatus, 'FALLBACK')
        assert hasattr(BridgeStatus, 'ERROR')
        assert hasattr(BridgeStatus, 'NOT_AVAILABLE')


# ============================================================================
# TaskBridge Initialization Tests
# ============================================================================

class TestTaskBridgeInit:
    """Tests for TaskBridge initialization."""
    
    def test_init_without_auto_initialize(self):
        """Test creating TaskBridge without auto-initialization."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        assert bridge._initialized is False
        assert bridge._backend_factory is None
    
    def test_metrics_initialized(self):
        """Test metrics are initialized correctly."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        metrics = bridge.metrics
        assert metrics['operations'] == 0
        assert metrics['successes'] == 0
        assert metrics['fallbacks'] == 0
        assert metrics['errors'] == 0
        assert metrics['total_time_ms'] == 0.0
        assert 'by_type' in metrics
    
    def test_metrics_by_type_structure(self):
        """Test per-operation-type metrics structure."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        by_type = bridge.metrics['by_type']
        assert 'attribute' in by_type
        assert 'spatial' in by_type
        assert 'multi_step' in by_type
        
        for op_type in ['attribute', 'spatial', 'multi_step']:
            assert by_type[op_type]['count'] == 0
            assert by_type[op_type]['success'] == 0
            assert by_type[op_type]['time_ms'] == 0.0


# ============================================================================
# TaskBridge Metrics Tests
# ============================================================================

class TestTaskBridgeMetrics:
    """Tests for TaskBridge metrics tracking."""
    
    def test_reset_metrics(self):
        """Test resetting metrics."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        # Manually modify metrics
        bridge._metrics['operations'] = 10
        bridge._metrics['successes'] = 5
        
        # Reset
        bridge.reset_metrics()
        
        assert bridge.metrics['operations'] == 0
        assert bridge.metrics['successes'] == 0
    
    def test_update_type_metrics(self):
        """Test _update_type_metrics helper."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        # Update attribute metrics
        bridge._update_type_metrics('attribute', True, 50.0)
        bridge._update_type_metrics('attribute', True, 30.0)
        bridge._update_type_metrics('attribute', False, 20.0)
        
        by_type = bridge.metrics['by_type']['attribute']
        assert by_type['count'] == 3
        assert by_type['success'] == 2
        assert by_type['time_ms'] == 100.0
    
    def test_get_metrics_report(self):
        """Test formatted metrics report generation."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        # Add some operations
        bridge._metrics['operations'] = 10
        bridge._metrics['successes'] = 8
        bridge._metrics['fallbacks'] = 1
        bridge._metrics['errors'] = 1
        bridge._metrics['total_time_ms'] = 500.0
        bridge._metrics['by_type']['attribute'] = {'count': 5, 'success': 5, 'time_ms': 200.0}
        bridge._metrics['by_type']['spatial'] = {'count': 5, 'success': 3, 'time_ms': 300.0}
        
        report = bridge.get_metrics_report()
        
        assert "TASKBRIDGE V3 MIGRATION METRICS" in report
        assert "Total Operations: 10" in report
        assert "Successes: 8" in report
        assert "80.0%" in report
        assert "attribute:" in report
        assert "spatial:" in report
    
    def test_pct_helper(self):
        """Test percentage calculation helper."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        assert bridge._pct(5, 10) == "50.0%"
        assert bridge._pct(0, 0) == "0%"
        assert bridge._pct(3, 4) == "75.0%"


# ============================================================================
# TaskBridge Availability Tests
# ============================================================================

class TestTaskBridgeAvailability:
    """Tests for TaskBridge availability checks."""
    
    def test_not_available_when_not_initialized(self):
        """Test is_available returns False when not initialized."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        assert bridge.is_available() is False
    
    @patch('adapters.task_bridge.TaskBridge._try_initialize')
    def test_available_when_initialized(self, mock_init):
        """Test is_available returns True when properly initialized."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        bridge._initialized = True
        bridge._backend_factory = Mock()
        
        assert bridge.is_available() is True


# ============================================================================
# TaskBridge supports_multi_step Tests
# ============================================================================

class TestTaskBridgeMultiStepSupport:
    """Tests for multi-step filtering support detection."""
    
    def test_supports_multi_step_when_not_available(self):
        """Test supports_multi_step returns False when bridge not available."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        assert bridge.supports_multi_step() is False
    
    @patch('adapters.task_bridge.TaskBridge.is_available')
    def test_supports_multi_step_with_import(self, mock_available):
        """Test supports_multi_step checks for MultiStepRequest import."""
        from adapters.task_bridge import TaskBridge
        
        mock_available.return_value = True
        bridge = TaskBridge(auto_initialize=False)
        bridge._initialized = True
        bridge._backend_factory = Mock()
        
        # This will try to import MultiStepRequest
        # Result depends on whether core module exists
        result = bridge.supports_multi_step()
        
        # Should return boolean
        assert isinstance(result, bool)


# ============================================================================
# TaskBridge execute_attribute_filter Tests
# ============================================================================

class TestTaskBridgeAttributeFilter:
    """Tests for attribute filter execution."""
    
    def test_returns_not_available_when_not_initialized(self):
        """Test returns NOT_AVAILABLE status when bridge not available."""
        from adapters.task_bridge import TaskBridge, BridgeStatus
        
        bridge = TaskBridge(auto_initialize=False)
        layer = create_mock_layer()
        
        result = bridge.execute_attribute_filter(
            layer=layer,
            expression="field = 'value'"
        )
        
        assert result.status == BridgeStatus.NOT_AVAILABLE
        assert result.success is False


# ============================================================================
# TaskBridge execute_spatial_filter Tests
# ============================================================================

class TestTaskBridgeSpatialFilter:
    """Tests for spatial filter execution."""
    
    def test_returns_not_available_when_not_initialized(self):
        """Test returns NOT_AVAILABLE status when bridge not available."""
        from adapters.task_bridge import TaskBridge, BridgeStatus
        
        bridge = TaskBridge(auto_initialize=False)
        source = create_mock_layer(layer_id="source")
        target = create_mock_layer(layer_id="target")
        
        result = bridge.execute_spatial_filter(
            source_layer=source,
            target_layers=[target],
            predicates=['intersects']
        )
        
        assert result.status == BridgeStatus.NOT_AVAILABLE
        assert result.success is False


# ============================================================================
# TaskBridge execute_multi_step_filter Tests
# ============================================================================

class TestTaskBridgeMultiStepFilter:
    """Tests for multi-step filter execution."""
    
    def test_returns_not_available_when_not_initialized(self):
        """Test returns NOT_AVAILABLE when bridge not available."""
        from adapters.task_bridge import TaskBridge, BridgeStatus
        
        bridge = TaskBridge(auto_initialize=False)
        source = create_mock_layer()
        
        result = bridge.execute_multi_step_filter(
            source_layer=source,
            steps=[]
        )
        
        assert result.status == BridgeStatus.NOT_AVAILABLE
        assert result.success is False
    
    def test_fallback_when_services_not_initialized(self):
        """Test fallback when services not fully initialized."""
        from adapters.task_bridge import TaskBridge, BridgeStatus
        
        bridge = TaskBridge(auto_initialize=False)
        bridge._initialized = True
        bridge._backend_factory = Mock()
        
        source = create_mock_layer()
        
        # Even with _initialized=True, services may not be available
        # This should return FALLBACK with an error message
        result = bridge.execute_multi_step_filter(
            source_layer=source,
            steps=[{'target_layer_ids': ['test'], 'predicates': ['intersects']}]
        )
        
        # Should either succeed or fallback gracefully
        assert result.status in [BridgeStatus.SUCCESS, BridgeStatus.FALLBACK, BridgeStatus.ERROR]


# ============================================================================
# Integration Pattern Tests
# ============================================================================

class TestStranglerFigPattern:
    """Tests verifying the Strangler Fig pattern implementation."""
    
    def test_fallback_result_signals_legacy_use(self):
        """Test FALLBACK status signals caller should use legacy code."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult.fallback("Feature not supported")
        
        # Caller should check status and fall back
        should_use_legacy = (result.status == BridgeStatus.FALLBACK)
        assert should_use_legacy is True
    
    def test_success_result_signals_v3_handled(self):
        """Test SUCCESS status signals v3 handled the operation."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult(
            status=BridgeStatus.SUCCESS,
            success=True,
            feature_count=10
        )
        
        # Caller should skip legacy code
        v3_handled = (result.status == BridgeStatus.SUCCESS and result.success)
        assert v3_handled is True
    
    def test_not_available_result_allows_fallback(self):
        """Test NOT_AVAILABLE status allows caller to try legacy."""
        from adapters.task_bridge import BridgeResult, BridgeStatus
        
        result = BridgeResult.not_available()
        
        # Caller can choose to fallback when bridge not available
        can_fallback = (result.status in [BridgeStatus.FALLBACK, BridgeStatus.ERROR, BridgeStatus.NOT_AVAILABLE])
        assert can_fallback is True


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_metrics_immutable_copy(self):
        """Test metrics property returns a copy, not the original."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        metrics1 = bridge.metrics
        metrics1['operations'] = 999
        
        metrics2 = bridge.metrics
        assert metrics2['operations'] == 0  # Original unchanged
    
    def test_invalid_operation_type_ignored(self):
        """Test _update_type_metrics ignores invalid operation types."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        # Should not raise, just be ignored
        bridge._update_type_metrics('invalid_type', True, 100.0)
        
        # Verify no crash and original types unaffected
        assert bridge.metrics['by_type']['attribute']['count'] == 0


# ============================================================================
# TaskBridge Export Tests
# ============================================================================

class TestTaskBridgeExport:
    """Tests for export functionality."""
    
    def test_returns_not_available_when_not_initialized(self):
        """Test returns NOT_AVAILABLE when bridge not available."""
        from adapters.task_bridge import TaskBridge, BridgeStatus
        
        bridge = TaskBridge(auto_initialize=False)
        source = create_mock_layer()
        
        result = bridge.execute_export(
            source_layer=source,
            output_path="/tmp/test.gpkg",
            format="gpkg"
        )
        
        assert result.status == BridgeStatus.NOT_AVAILABLE
        assert result.success is False
    
    def test_supports_export_when_not_available(self):
        """Test supports_export returns False when bridge not available."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        assert bridge.supports_export() is False
    
    def test_export_metrics_type_exists(self):
        """Test export metrics type is tracked."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        # Verify export type exists in metrics
        assert 'export' in bridge.metrics['by_type']
        assert bridge.metrics['by_type']['export']['count'] == 0
    
    def test_export_updates_metrics(self):
        """Test export operations update metrics correctly."""
        from adapters.task_bridge import TaskBridge
        
        bridge = TaskBridge(auto_initialize=False)
        
        # Manually update export metrics
        bridge._update_type_metrics('export', True, 1000.0)
        bridge._update_type_metrics('export', True, 500.0)
        bridge._update_type_metrics('export', False, 200.0)
        
        export_metrics = bridge.metrics['by_type']['export']
        assert export_metrics['count'] == 3
        assert export_metrics['success'] == 2
        assert export_metrics['time_ms'] == 1700.0
