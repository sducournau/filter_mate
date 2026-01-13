"""
Unit tests for LayerService.

Tests layer validation, info extraction, and protection window logic.
Story: MIG-077
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────
# Mock PyQt5/QGIS before importing
# ─────────────────────────────────────────────────────────────────

class MockSignal:
    """Mock pyqtSignal for testing."""
    def __init__(self, *args):
        self.args = args
        self.callbacks = []
    
    def emit(self, *args):
        for cb in self.callbacks:
            cb(*args)
    
    def connect(self, callback):
        self.callbacks.append(callback)
    
    def disconnect(self, callback=None):
        if callback:
            self.callbacks.remove(callback)
        else:
            self.callbacks.clear()


class MockQObject:
    """Mock QObject."""
    def __init__(self, parent=None):
        self.parent = parent


class MockQgsField:
    """Mock QGIS Field for testing."""
    def __init__(self, name, type_name="String"):
        self._name = name
        self._type_name = type_name
    
    def name(self): return self._name
    def typeName(self): return self._type_name


class MockQgsFields:
    """Mock QGIS Fields collection for testing."""
    def __init__(self, fields=None):
        self._fields = fields or []
    
    def __len__(self): return len(self._fields)
    def __iter__(self): return iter(self._fields)
    def __getitem__(self, index): return self._fields[index]
    def at(self, index): return self._fields[index] if 0 <= index < len(self._fields) else None
    def names(self): return [f.name() for f in self._fields]
    def count(self): return len(self._fields)


class MockQgsVectorLayer:
    """
    Mock QgsVectorLayer that properly works with isinstance() checks.
    This fixes the TypeError: isinstance() arg 2 must be a type error.
    
    Use set_* methods to change behavior dynamically in tests:
        mock_layer.set_valid(False)  # Instead of mock_layer.isValid.return_value = False
    """
    def __init__(
        self,
        layer_id="test_layer_123",
        name="test_layer",
        provider_type="postgres",
        is_valid=True,
        deleted=False
    ):
        self._id = layer_id
        self._name = name
        self._provider_type = provider_type
        self._is_valid = is_valid
        self._deleted = deleted
        self._subset = ""
        self._editable = False
        self._feature_count = 1000
        self._primary_key_attributes = []
        # Default fields include common PK names for testing
        self._fields = MockQgsFields([
            MockQgsField("id", "Integer"),
            MockQgsField("name", "String"),
            MockQgsField("geom", "Geometry")
        ])
    
    # Setters for dynamic test behavior modification
    def set_id(self, value): self._id = value
    def set_name(self, value): self._name = value
    def set_valid(self, value): self._is_valid = value
    def set_deleted(self, value): self._deleted = value
    def set_editable(self, value): self._editable = value
    def set_feature_count(self, value): self._feature_count = value
    def set_subset(self, value): self._subset = value
    def set_primary_key_attributes(self, value): self._primary_key_attributes = value
    def set_fields(self, value): self._fields = value
    
    def id(self):
        if self._deleted:
            raise RuntimeError("C++ object deleted")
        return self._id
    
    def name(self):
        if self._deleted:
            raise RuntimeError("C++ object deleted")
        return self._name
    
    def providerType(self): return self._provider_type
    def isValid(self): return self._is_valid
    def isEditable(self): return self._editable
    def subsetString(self): return self._subset
    def setSubsetString(self, s): self._subset = s; return True
    def featureCount(self): return self._feature_count
    def crs(self):
        crs = Mock()
        crs.authid.return_value = "EPSG:4326"
        return crs
    def wkbType(self): return 1
    def fields(self): return self._fields
    def primaryKeyAttributes(self): return self._primary_key_attributes


# Apply mocks with proper QgsVectorLayer class
import sys
mock_pyqt = Mock()
mock_pyqt.pyqtSignal = MockSignal
mock_pyqt.QObject = MockQObject

# Create QgsWkbTypes mock
class MockQgsWkbTypes:
    """Mock QgsWkbTypes for geometry type display."""
    @staticmethod
    def displayString(wkb_type):
        type_map = {
            0: "Unknown",
            1: "Point",
            2: "LineString",
            3: "Polygon",
            4: "MultiPoint",
            5: "MultiLineString",
            6: "MultiPolygon"
        }
        return type_map.get(wkb_type, "Unknown")


# Create qgis.core mock with proper QgsVectorLayer class
mock_qgis_core = Mock()
mock_qgis_core.QgsVectorLayer = MockQgsVectorLayer
mock_qgis_core.QgsWkbTypes = MockQgsWkbTypes

sys.modules['qgis'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = mock_pyqt
sys.modules['qgis.core'] = mock_qgis_core
sys.modules['PyQt5'] = Mock()
sys.modules['PyQt5.QtCore'] = mock_pyqt


# Now import LayerService
from core.services.layer_service import (
    LayerService,
    LayerValidationStatus,
    LayerValidationResult,
    LayerInfo,
    LayerSyncState
)


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def service():
    """Create a LayerService instance."""
    return LayerService()


@pytest.fixture
def mock_layer():
    """Create a mock QGIS vector layer using MockQgsVectorLayer."""
    # Use MockQgsVectorLayer class which properly supports isinstance() checks
    return MockQgsVectorLayer(
        layer_id="test_layer_123",
        name="test_layer",
        provider_type="postgres",
        is_valid=True,
        deleted=False
    )


@pytest.fixture
def deleted_layer():
    """Create a mock layer that simulates a deleted C++ object."""
    return MockQgsVectorLayer(
        layer_id="deleted_layer",
        name="deleted",
        deleted=True
    )


@pytest.fixture
def mock_project_layers():
    """Create mock PROJECT_LAYERS dict."""
    return {
        "test_layer_123": {"infos": {"layer_name": "test_layer"}},
        "other_layer_456": {"infos": {"layer_name": "other_layer"}}
    }


# ─────────────────────────────────────────────────────────────────
# Test LayerValidationResult
# ─────────────────────────────────────────────────────────────────

class TestLayerValidationResult:
    """Tests for LayerValidationResult dataclass."""
    
    def test_is_valid_true(self):
        """Test is_valid property returns True for VALID status."""
        result = LayerValidationResult(status=LayerValidationStatus.VALID)
        assert result.is_valid is True
    
    def test_is_valid_false(self):
        """Test is_valid property returns False for non-VALID status."""
        for status in LayerValidationStatus:
            if status != LayerValidationStatus.VALID:
                result = LayerValidationResult(status=status)
                assert result.is_valid is False
    
    def test_full_result(self):
        """Test result with all fields populated."""
        layer = Mock()
        result = LayerValidationResult(
            status=LayerValidationStatus.VALID,
            layer=layer,
            layer_id="layer_123",
            layer_name="My Layer",
            error_message=""
        )
        
        assert result.is_valid
        assert result.layer is layer
        assert result.layer_id == "layer_123"
        assert result.layer_name == "My Layer"


# ─────────────────────────────────────────────────────────────────
# Test Layer Validation
# ─────────────────────────────────────────────────────────────────

class TestLayerValidation:
    """Tests for layer validation."""
    
    def test_validate_none_layer(self, service):
        """Test validation fails for None layer."""
        result = service.validate_layer(None)
        
        assert result.status == LayerValidationStatus.INVALID
        assert "None" in result.error_message
    
    def test_validate_plugin_busy(self, service, mock_layer):
        """Test validation fails when plugin is busy."""
        result = service.validate_layer(mock_layer, plugin_busy=True)
        
        assert result.status == LayerValidationStatus.PLUGIN_BUSY
        assert "busy" in result.error_message.lower()
    
    def test_validate_deleted_layer(self, service, deleted_layer):
        """Test validation handles deleted C++ object."""
        result = service.validate_layer(deleted_layer)
        
        assert result.status == LayerValidationStatus.DELETED
        assert "deleted" in result.error_message.lower()
    
    def test_validate_source_unavailable(self, service, mock_layer):
        """Test validation detects unavailable source."""
        mock_layer.set_valid(False)
        
        with patch.object(service, '_is_layer_source_available', return_value=False):
            result = service.validate_layer(mock_layer)
        
        assert result.status == LayerValidationStatus.SOURCE_UNAVAILABLE
        assert result.layer_id == "test_layer_123"
    
    def test_validate_not_in_project_layers(self, service, mock_layer, mock_project_layers):
        """Test validation fails if layer not in PROJECT_LAYERS."""
        mock_layer.set_id("unknown_layer_999")
        
        result = service.validate_layer(mock_layer, project_layers=mock_project_layers)
        
        assert result.status == LayerValidationStatus.NOT_IN_PROJECT
    
    def test_validate_valid_layer(self, service, mock_layer, mock_project_layers):
        """Test validation passes for valid layer."""
        with patch.object(service, '_is_layer_source_available', return_value=True):
            result = service.validate_layer(mock_layer, project_layers=mock_project_layers)
        
        assert result.status == LayerValidationStatus.VALID
        assert result.is_valid
        assert result.layer is mock_layer
        assert result.layer_id == "test_layer_123"
        assert result.layer_name == "test_layer"


# ─────────────────────────────────────────────────────────────────
# Test Layer Information
# ─────────────────────────────────────────────────────────────────

class TestLayerInfo:
    """Tests for layer information extraction."""
    
    def test_get_layer_info_none(self, service):
        """Test get_layer_info returns None for None layer."""
        result = service.get_layer_info(None)
        assert result is None
    
    def test_get_layer_info_deleted(self, service, deleted_layer):
        """Test get_layer_info handles deleted layer."""
        result = service.get_layer_info(deleted_layer)
        assert result is None
    
    def test_get_layer_info_caching(self, service, mock_layer):
        """Test that layer info is cached."""
        # QgsWkbTypes is already mocked globally via mock_qgis_core
        
        # First call
        info1 = service.get_layer_info(mock_layer)
        
        # Second call should use cache
        info2 = service.get_layer_info(mock_layer, use_cache=True)
        
        assert info1 is info2
    
    def test_clear_cache_specific(self, service, mock_layer):
        """Test clearing specific layer from cache."""
        # Add to cache
        service._layer_info_cache["test_layer_123"] = Mock()
        service._layer_info_cache["other_layer"] = Mock()
        
        # Clear specific layer
        service.clear_cache("test_layer_123")
        
        assert "test_layer_123" not in service._layer_info_cache
        assert "other_layer" in service._layer_info_cache
    
    def test_clear_cache_all(self, service):
        """Test clearing all cached layer info."""
        service._layer_info_cache["layer_1"] = Mock()
        service._layer_info_cache["layer_2"] = Mock()
        
        service.clear_cache()
        
        assert len(service._layer_info_cache) == 0


# ─────────────────────────────────────────────────────────────────
# Test Primary Key Detection
# ─────────────────────────────────────────────────────────────────

class TestPrimaryKeyDetection:
    """Tests for primary key detection."""
    
    def test_detect_pk_none_layer(self, service):
        """Test PK detection with None layer."""
        result = service._detect_primary_key(None)
        assert result is None
    
    def test_detect_pk_from_provider(self, service, mock_layer):
        """Test PK from provider attributes."""
        mock_layer.set_primary_key_attributes([1])
        
        result = service._detect_primary_key(mock_layer)
        
        assert result == "name"  # Index 1 in our mock fields
    
    def test_detect_pk_common_names(self, service, mock_layer):
        """Test PK detection using common names."""
        mock_layer.set_primary_key_attributes([])
        
        result = service._detect_primary_key(mock_layer)
        
        assert result == "id"  # 'id' is in common PK names
    
    def test_get_primary_key_from_props(self, service, mock_layer):
        """Test get_primary_key uses layer_props first."""
        layer_props = {
            'infos': {'primary_key_name': 'custom_pk'}
        }
        
        result = service.get_primary_key(mock_layer, layer_props)
        
        assert result == "custom_pk"
    
    def test_get_primary_key_auto_detect(self, service, mock_layer):
        """Test get_primary_key falls back to auto-detection."""
        result = service.get_primary_key(mock_layer, None)
        
        assert result is not None


# ─────────────────────────────────────────────────────────────────
# Test Layer Sync State
# ─────────────────────────────────────────────────────────────────

class TestLayerSyncState:
    """Tests for layer sync state extraction."""
    
    def test_get_sync_state_none_layer(self, service):
        """Test sync state returns None for None layer."""
        result = service.get_sync_state(None)
        assert result is None
    
    def test_get_sync_state_basic(self, service, mock_layer):
        """Test basic sync state extraction."""
        state = service.get_sync_state(mock_layer)
        
        assert state is not None
        assert state.layer_id == "test_layer_123"
        assert state.layer_name == "test_layer"
        assert state.provider_type == "postgres"
        assert state.has_subset is False
    
    def test_get_sync_state_with_subset(self, service, mock_layer):
        """Test sync state with active subset."""
        mock_layer.set_subset("id > 100")
        
        state = service.get_sync_state(mock_layer)
        
        assert state.has_subset is True
        assert state.subset_string == "id > 100"
    
    def test_get_sync_state_forced_backend(self, service, mock_layer):
        """Test sync state with forced backend."""
        forced_backends = {"test_layer_123": "postgresql"}
        
        state = service.get_sync_state(mock_layer, forced_backends=forced_backends)
        
        assert state.forced_backend == "postgresql"
    
    def test_detect_multi_step_filter(self, service, mock_layer):
        """Test multi-step filter detection."""
        mock_layer.set_subset("id > 10 AND name = 'test'")
        
        result = service._detect_multi_step_filter(mock_layer)
        
        assert result is True
    
    def test_detect_multi_step_from_props(self, service, mock_layer):
        """Test multi-step detection from layer_props."""
        mock_layer.set_subset("id > 10")
        layer_props = {'has_combine_operator': {'has_combine_operator': True}}
        
        result = service._detect_multi_step_filter(mock_layer, layer_props)
        
        assert result is True


# ─────────────────────────────────────────────────────────────────
# Test Field Validation
# ─────────────────────────────────────────────────────────────────

class TestFieldValidation:
    """Tests for field expression validation."""
    
    def test_validate_empty_expression(self, service, mock_layer):
        """Test empty expression is valid."""
        is_valid, error = service.validate_field_expression(mock_layer, "")
        
        assert is_valid is True
        assert error is None
    
    def test_validate_none_layer(self, service):
        """Test validation with None layer."""
        is_valid, error = service.validate_field_expression(None, "id")
        
        assert is_valid is False
        assert "layer" in error.lower()
    
    def test_get_valid_expression_fallback(self, service, mock_layer):
        """Test get_valid_expression falls back correctly."""
        with patch.object(service, 'validate_field_expression', return_value=(False, "invalid")):
            with patch.object(service, '_detect_primary_key', return_value="pk_field"):
                result = service.get_valid_expression(mock_layer, "invalid_expr")
        
        assert result == "pk_field"


# ─────────────────────────────────────────────────────────────────
# Test Protection Window
# ─────────────────────────────────────────────────────────────────

class TestProtectionWindow:
    """Tests for post-filter protection window."""
    
    def test_initial_state(self, service):
        """Test initial protection state."""
        assert service.is_within_protection_window() is False
        assert service._saved_layer_id_before_filter is None
    
    def test_save_layer_before_filter(self, service, mock_layer):
        """Test saving layer before filter."""
        service.save_layer_before_filter(mock_layer)
        
        assert service._saved_layer_id_before_filter == "test_layer_123"
    
    def test_mark_filter_completed(self, service):
        """Test marking filter as completed."""
        service.mark_filter_completed()
        
        assert service._filter_completed_time > 0
        assert service.is_within_protection_window() is True
    
    def test_protection_window_expires(self, service):
        """Test protection window expiration."""
        service._filter_completed_time = time.time() - 10  # 10 seconds ago
        
        assert service.is_within_protection_window() is False
    
    def test_clear_filter_protection(self, service, mock_layer):
        """Test clearing filter protection."""
        service.save_layer_before_filter(mock_layer)
        service.mark_filter_completed()
        
        service.clear_filter_protection()
        
        assert service._filter_completed_time == 0
        assert service._saved_layer_id_before_filter is None
    
    def test_should_block_layer_change_none(self, service, mock_layer):
        """Test blocking None layer during protection."""
        service.save_layer_before_filter(mock_layer)
        service.mark_filter_completed()
        
        should_block, reason = service.should_block_layer_change(None)
        
        assert should_block is True
        assert "None" in reason
    
    def test_should_block_different_layer(self, service, mock_layer):
        """Test blocking different layer during protection."""
        service.save_layer_before_filter(mock_layer)
        service.mark_filter_completed()
        
        other_layer = Mock()
        other_layer.id.return_value = "other_layer_456"
        
        should_block, reason = service.should_block_layer_change(other_layer)
        
        assert should_block is True
        assert "change" in reason.lower()
    
    def test_should_allow_same_layer(self, service, mock_layer):
        """Test allowing same layer during protection."""
        service.save_layer_before_filter(mock_layer)
        service.mark_filter_completed()
        
        should_block, reason = service.should_block_layer_change(mock_layer)
        
        assert should_block is False
    
    def test_should_allow_after_window(self, service, mock_layer):
        """Test allowing layer change after window expires."""
        service.save_layer_before_filter(mock_layer)
        service._filter_completed_time = time.time() - 10
        
        other_layer = Mock()
        other_layer.id.return_value = "other_layer"
        
        should_block, _ = service.should_block_layer_change(other_layer)
        
        assert should_block is False


# ─────────────────────────────────────────────────────────────────
# Test Utility Methods
# ─────────────────────────────────────────────────────────────────

class TestUtilityMethods:
    """Tests for utility methods."""
    
    def test_get_layer_display_name_none(self, service):
        """Test display name for None layer."""
        result = service.get_layer_display_name(None)
        assert result == "(No layer)"
    
    def test_get_layer_display_name_deleted(self, service, deleted_layer):
        """Test display name for deleted layer."""
        result = service.get_layer_display_name(deleted_layer)
        
        assert result == "(Deleted)"
    
    def test_get_layer_display_name_truncated(self, service, mock_layer):
        """Test display name truncation."""
        mock_layer.set_name("A" * 50)
        
        result = service.get_layer_display_name(mock_layer, max_length=20)
        
        assert len(result) == 20
        assert result.endswith("...")
    
    def test_get_provider_display_name(self, service):
        """Test provider display name mapping."""
        name, icon = service.get_provider_display_name('postgres')
        
        assert name == 'PostgreSQL'
        assert icon == '🐘'
    
    def test_get_provider_display_name_unknown(self, service):
        """Test unknown provider display name."""
        name, icon = service.get_provider_display_name('custom_provider')
        
        assert name == 'custom_provider'
    
    def test_cleanup_for_removed_layers(self, service):
        """Test cleanup of cached data for removed layers."""
        service._layer_info_cache = {
            "layer_1": Mock(),
            "layer_2": Mock(),
            "layer_3": Mock()
        }
        service._saved_layer_id_before_filter = "layer_2"
        
        removed = service.cleanup_for_removed_layers(["layer_1"])
        
        assert removed == 2
        assert "layer_1" in service._layer_info_cache
        assert "layer_2" not in service._layer_info_cache
        assert service._saved_layer_id_before_filter is None


# ─────────────────────────────────────────────────────────────────
# Test Dataclasses
# ─────────────────────────────────────────────────────────────────

class TestDataclasses:
    """Tests for dataclass behavior."""
    
    def test_layer_info_defaults(self):
        """Test LayerInfo default values."""
        info = LayerInfo(
            layer_id="id",
            name="test",
            provider_type="ogr",
            feature_count=100,
            geometry_type="Point",
            crs="EPSG:4326"
        )
        
        assert info.primary_key is None
        assert info.has_valid_source is True
        assert info.is_editable is False
        assert info.fields == []
    
    def test_layer_sync_state_defaults(self):
        """Test LayerSyncState default values."""
        state = LayerSyncState(
            layer_id="id",
            layer_name="test",
            provider_type="postgres"
        )
        
        assert state.has_subset is False
        assert state.subset_string == ""
        assert state.is_multi_step_filter is False
        assert state.primary_key is None
        assert state.forced_backend is None


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for LayerService."""
    
    def test_full_validation_workflow(self, service, mock_layer, mock_project_layers):
        """Test complete validation workflow."""
        with patch.object(service, '_is_layer_source_available', return_value=True):
            # Validate
            result = service.validate_layer(mock_layer, mock_project_layers)
            assert result.is_valid
            
            # Get info - QgsWkbTypes is already mocked globally
            info = service.get_layer_info(mock_layer)
            
            # Get sync state
            state = service.get_sync_state(mock_layer)
            
            assert info is not None or state is not None
    
    def test_protection_workflow(self, service, mock_layer):
        """Test complete filter protection workflow."""
        # Before filter
        service.save_layer_before_filter(mock_layer)
        
        # Simulate filter
        service.mark_filter_completed()
        
        # Try to change layer
        other_layer = Mock()
        other_layer.id.return_value = "other"
        
        should_block, _ = service.should_block_layer_change(other_layer)
        assert should_block is True
        
        # Same layer should be allowed
        should_block, _ = service.should_block_layer_change(mock_layer)
        assert should_block is False
        
        # Cleanup
        service.clear_filter_protection()
        should_block, _ = service.should_block_layer_change(other_layer)
        assert should_block is False
