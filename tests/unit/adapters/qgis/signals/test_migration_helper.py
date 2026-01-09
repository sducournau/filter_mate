"""
Tests for SignalMigrationHelper.

Story: MIG-086
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path
import warnings

# Add plugin path for imports
plugin_path = Path(__file__).parents[5]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


# ─────────────────────────────────────────────────────────────────
# Mock Classes
# ─────────────────────────────────────────────────────────────────

class MockSignal:
    """Mock Qt signal for testing."""
    
    def __init__(self, name: str = "signal"):
        self.name = name
        self._connections = []
    
    def connect(self, handler):
        if handler not in self._connections:
            self._connections.append(handler)
    
    def disconnect(self, handler=None):
        if handler is None:
            self._connections.clear()
        elif handler in self._connections:
            self._connections.remove(handler)


class MockWidget:
    """Mock widget with signals."""
    
    def __init__(self, name: str = "widget"):
        self.name = name
        self.clicked = MockSignal("clicked")
        self.currentIndexChanged = MockSignal("currentIndexChanged")
        self.toggled = MockSignal("toggled")
        self.valueChanged = MockSignal("valueChanged")


class MockDockWidget:
    """Mock dockwidget with widgets and handlers."""
    
    def __init__(self):
        # Create mock widgets
        self.comboBox_filtering_current_layer = MockWidget("layer_combo")
        self.comboBox_exploring_current_layer = MockWidget("exploring_combo")
        self.pushButton_apply_filter = MockWidget("apply_btn")
        self.pushButton_clear_filter = MockWidget("clear_btn")
        self.pushButton_reset_all = MockWidget("reset_btn")
        self.groupBox_exploring_1 = MockWidget("groupbox_1")
        self.groupBox_exploring_2 = MockWidget("groupbox_2")
        self.groupBox_exploring_3 = MockWidget("groupbox_3")
        self.comboBox_exploring_1_property = MockWidget("prop_1")
        self.comboBox_exploring_2_property = MockWidget("prop_2")
        self.comboBox_exploring_3_property = MockWidget("prop_3")
        self.comboBox_exploring_1_value = MockWidget("val_1")
        self.comboBox_exploring_2_value = MockWidget("val_2")
        self.comboBox_exploring_3_value = MockWidget("val_3")
        self.doubleSpinBox_buffer_value = MockWidget("buffer_spin")
        self.comboBox_buffer_unit = MockWidget("buffer_unit")
        self.pushButton_export_gpkg = MockWidget("export_gpkg")
        self.pushButton_export_shp = MockWidget("export_shp")
    
    # Mock handlers
    def _on_filtering_layer_changed(self, *args): pass
    def _on_exploring_layer_changed(self, *args): pass
    def _on_apply_filter(self, *args): pass
    def _on_clear_filter(self, *args): pass
    def _on_reset_all(self, *args): pass
    def _on_groupbox_1_toggled(self, *args): pass
    def _on_groupbox_2_toggled(self, *args): pass
    def _on_groupbox_3_toggled(self, *args): pass
    def _on_property_1_changed(self, *args): pass
    def _on_property_2_changed(self, *args): pass
    def _on_property_3_changed(self, *args): pass
    def _on_value_1_changed(self, *args): pass
    def _on_value_2_changed(self, *args): pass
    def _on_value_3_changed(self, *args): pass
    def _on_buffer_value_changed(self, *args): pass
    def _on_buffer_unit_changed(self, *args): pass
    def _on_export_gpkg(self, *args): pass
    def _on_export_shp(self, *args): pass


class MockSignalManager:
    """Mock SignalManager for testing."""
    
    def __init__(self):
        self._connections = {}
        self._counter = 0
    
    def connect(self, sender, signal_name, receiver, context=None):
        self._counter += 1
        conn_id = f"sig_{self._counter:05d}"
        self._connections[conn_id] = {
            'sender': sender,
            'signal_name': signal_name,
            'receiver': receiver,
            'context': context
        }
        # Actually connect
        signal = getattr(sender, signal_name, None)
        if signal:
            signal.connect(receiver)
        return conn_id
    
    def disconnect(self, connection_id):
        if connection_id in self._connections:
            del self._connections[connection_id]
            return True
        return False
    
    def get_connection_count(self):
        return len(self._connections)


# ─────────────────────────────────────────────────────────────────
# Import Migration Helper
# ─────────────────────────────────────────────────────────────────

from adapters.qgis.signals.migration_helper import (
    SignalMigrationHelper,
    SignalDefinition,
    SignalCategory,
    MigrationResult,
    deprecated_signal_connection,
    DOCKWIDGET_WIDGET_SIGNALS,
    get_all_signal_definitions,
    get_signals_by_category,
    get_signals_by_context,
)


# ─────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def dockwidget():
    """Create a mock dockwidget."""
    return MockDockWidget()


@pytest.fixture
def signal_manager():
    """Create a mock signal manager."""
    return MockSignalManager()


@pytest.fixture
def helper(dockwidget, signal_manager):
    """Create a SignalMigrationHelper."""
    return SignalMigrationHelper(dockwidget, signal_manager, debug=True)


# ─────────────────────────────────────────────────────────────────
# Test SignalDefinition
# ─────────────────────────────────────────────────────────────────

class TestSignalDefinition:
    """Tests for SignalDefinition dataclass."""
    
    def test_init(self):
        """Test SignalDefinition initialization."""
        sig_def = SignalDefinition(
            name='test_signal',
            widget_attr='button',
            signal_name='clicked',
            handler_name='on_click'
        )
        
        assert sig_def.name == 'test_signal'
        assert sig_def.widget_attr == 'button'
        assert sig_def.signal_name == 'clicked'
        assert sig_def.handler_name == 'on_click'
        assert sig_def.category == SignalCategory.WIDGET
    
    def test_to_dict(self):
        """Test to_dict method."""
        sig_def = SignalDefinition(
            name='test',
            widget_attr='btn',
            signal_name='clicked',
            handler_name='handler',
            context='actions'
        )
        
        result = sig_def.to_dict()
        
        assert result['name'] == 'test'
        assert result['context'] == 'actions'
        assert result['category'] == 'WIDGET'


# ─────────────────────────────────────────────────────────────────
# Test MigrationResult
# ─────────────────────────────────────────────────────────────────

class TestMigrationResult:
    """Tests for MigrationResult dataclass."""
    
    def test_success_rate_100(self):
        """Test 100% success rate."""
        result = MigrationResult(
            total_signals=10,
            migrated=10,
            failed=0
        )
        
        assert result.success_rate == 100.0
    
    def test_success_rate_50(self):
        """Test 50% success rate."""
        result = MigrationResult(
            total_signals=10,
            migrated=5,
            failed=5
        )
        
        assert result.success_rate == 50.0
    
    def test_success_rate_zero_total(self):
        """Test success rate with zero total."""
        result = MigrationResult(total_signals=0)
        
        assert result.success_rate == 100.0
    
    def test_to_dict(self):
        """Test to_dict method."""
        result = MigrationResult(
            total_signals=10,
            migrated=8,
            failed=2
        )
        
        data = result.to_dict()
        
        assert data['total_signals'] == 10
        assert data['migrated'] == 8
        assert '80.0%' in data['success_rate']


# ─────────────────────────────────────────────────────────────────
# Test Deprecated Decorator
# ─────────────────────────────────────────────────────────────────

class TestDeprecatedDecorator:
    """Tests for deprecated_signal_connection decorator."""
    
    def test_warning_raised(self):
        """Test that deprecation warning is raised."""
        @deprecated_signal_connection('SignalManager.connect()')
        def legacy_connect():
            return "result"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = legacy_connect()
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'deprecated' in str(w[0].message).lower()
            assert result == "result"
    
    def test_function_still_works(self):
        """Test that decorated function still works."""
        @deprecated_signal_connection('new_method')
        def old_method(x, y):
            return x + y
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = old_method(1, 2)
        
        assert result == 3


# ─────────────────────────────────────────────────────────────────
# Test SignalMigrationHelper Init
# ─────────────────────────────────────────────────────────────────

class TestSignalMigrationHelperInit:
    """Tests for SignalMigrationHelper initialization."""
    
    def test_init(self, dockwidget, signal_manager):
        """Test initialization."""
        helper = SignalMigrationHelper(dockwidget, signal_manager)
        
        assert helper._target is dockwidget
        assert helper._signal_manager is signal_manager
        assert len(helper._migrated_signals) == 0
    
    def test_init_debug(self, dockwidget, signal_manager):
        """Test initialization with debug."""
        helper = SignalMigrationHelper(dockwidget, signal_manager, debug=True)
        
        assert helper._debug is True
    
    def test_repr(self, helper):
        """Test string representation."""
        assert "SignalMigrationHelper" in repr(helper)
        assert "0 migrated" in repr(helper)


# ─────────────────────────────────────────────────────────────────
# Test Migration
# ─────────────────────────────────────────────────────────────────

class TestSignalMigrationHelperMigrate:
    """Tests for migration methods."""
    
    def test_migrate_single_signal(self, helper):
        """Test migrating a single signal definition."""
        sig_def = SignalDefinition(
            name='apply_filter_clicked',
            widget_attr='pushButton_apply_filter',
            signal_name='clicked',
            handler_name='_on_apply_filter',
            context='actions'
        )
        
        result = helper.migrate_signals([sig_def])
        
        assert result.total_signals == 1
        assert result.migrated == 1
        assert result.failed == 0
    
    def test_migrate_widget_signals(self, helper):
        """Test migrating all widget signals."""
        result = helper.migrate_widget_signals()
        
        assert result.total_signals == len(DOCKWIDGET_WIDGET_SIGNALS)
        assert result.migrated > 0
        assert result.success_rate > 80
    
    def test_migrate_missing_widget(self, dockwidget, signal_manager):
        """Test migration with missing widget."""
        helper = SignalMigrationHelper(dockwidget, signal_manager, debug=True)
        
        sig_def = SignalDefinition(
            name='missing',
            widget_attr='nonexistent_widget',
            signal_name='clicked',
            handler_name='_on_click'
        )
        
        result = helper.migrate_signals([sig_def])
        
        assert result.migrated == 0
        assert result.skipped == 1
    
    def test_migrate_missing_handler(self, dockwidget, signal_manager):
        """Test migration with missing handler."""
        helper = SignalMigrationHelper(dockwidget, signal_manager, debug=True)
        
        sig_def = SignalDefinition(
            name='missing_handler',
            widget_attr='pushButton_apply_filter',
            signal_name='clicked',
            handler_name='nonexistent_handler'
        )
        
        result = helper.migrate_signals([sig_def])
        
        assert result.migrated == 0
        assert result.skipped == 1


# ─────────────────────────────────────────────────────────────────
# Test Validation
# ─────────────────────────────────────────────────────────────────

class TestSignalMigrationHelperValidate:
    """Tests for validation methods."""
    
    def test_validate_migration(self, helper):
        """Test migration validation."""
        helper.migrate_widget_signals()
        
        success, stats = helper.validate_migration()
        
        assert 'expected_signals' in stats
        assert 'migrated_signals' in stats
        assert 'coverage' in stats
    
    def test_get_migration_stats(self, helper):
        """Test getting migration stats."""
        helper.migrate_widget_signals()
        
        stats = helper.get_migration_stats()
        
        assert 'migrated' in stats
        assert 'failed' in stats
        assert 'by_category' in stats


# ─────────────────────────────────────────────────────────────────
# Test Disconnect
# ─────────────────────────────────────────────────────────────────

class TestSignalMigrationHelperDisconnect:
    """Tests for disconnect methods."""
    
    def test_disconnect_all_migrated(self, helper, signal_manager):
        """Test disconnecting all migrated signals."""
        helper.migrate_widget_signals()
        initial_count = signal_manager.get_connection_count()
        
        assert initial_count > 0
        
        disconnected = helper.disconnect_all_migrated()
        
        assert disconnected == initial_count
        assert len(helper._migrated_signals) == 0


# ─────────────────────────────────────────────────────────────────
# Test Utility Functions
# ─────────────────────────────────────────────────────────────────

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_get_all_signal_definitions(self):
        """Test getting all signal definitions."""
        sigs = get_all_signal_definitions()
        
        assert len(sigs) == len(DOCKWIDGET_WIDGET_SIGNALS)
        assert all(isinstance(s, SignalDefinition) for s in sigs)
    
    def test_get_signals_by_category(self):
        """Test getting signals by category."""
        widget_sigs = get_signals_by_category(SignalCategory.WIDGET)
        
        assert len(widget_sigs) > 0
        assert all(s.category == SignalCategory.WIDGET for s in widget_sigs)
    
    def test_get_signals_by_context(self):
        """Test getting signals by context."""
        action_sigs = get_signals_by_context('actions')
        
        assert len(action_sigs) > 0
        assert all(s.context == 'actions' for s in action_sigs)
    
    def test_get_signals_by_context_filtering(self):
        """Test getting filtering context signals."""
        filtering_sigs = get_signals_by_context('filtering')
        
        assert len(filtering_sigs) > 0


# ─────────────────────────────────────────────────────────────────
# Test DOCKWIDGET_WIDGET_SIGNALS
# ─────────────────────────────────────────────────────────────────

class TestPredefinedSignals:
    """Tests for predefined signal definitions."""
    
    def test_signals_have_required_fields(self):
        """Test that all signals have required fields."""
        for sig in DOCKWIDGET_WIDGET_SIGNALS:
            assert sig.name is not None
            assert sig.widget_attr is not None
            assert sig.signal_name is not None
            assert sig.handler_name is not None
    
    def test_signals_have_unique_names(self):
        """Test that all signal names are unique."""
        names = [sig.name for sig in DOCKWIDGET_WIDGET_SIGNALS]
        
        assert len(names) == len(set(names))
    
    def test_signals_have_valid_categories(self):
        """Test that all signals have valid categories."""
        for sig in DOCKWIDGET_WIDGET_SIGNALS:
            assert isinstance(sig.category, SignalCategory)
    
    def test_signals_cover_all_contexts(self):
        """Test that signals cover expected contexts."""
        contexts = {sig.context for sig in DOCKWIDGET_WIDGET_SIGNALS}
        
        assert 'filtering' in contexts
        assert 'exploring' in contexts
        assert 'actions' in contexts
        assert 'exporting' in contexts


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestSignalMigrationIntegration:
    """Integration tests for signal migration."""
    
    def test_full_migration_workflow(self, dockwidget, signal_manager):
        """Test complete migration workflow."""
        helper = SignalMigrationHelper(
            dockwidget, signal_manager, debug=True
        )
        
        # Step 1: Migrate
        result = helper.migrate_widget_signals()
        assert result.migrated > 0
        
        # Step 2: Validate
        success, stats = helper.validate_migration()
        assert 'coverage' in stats
        
        # Step 3: Get stats
        migration_stats = helper.get_migration_stats()
        assert len(migration_stats['migrated']) > 0
        
        # Step 4: Disconnect
        disconnected = helper.disconnect_all_migrated()
        assert disconnected == result.migrated
    
    def test_partial_migration_recovery(self, dockwidget, signal_manager):
        """Test that partial migration can be recovered."""
        helper = SignalMigrationHelper(dockwidget, signal_manager)
        
        # First migration
        result1 = helper.migrate_widget_signals()
        count1 = result1.migrated
        
        # Disconnect all
        helper.disconnect_all_migrated()
        
        # Second migration should work
        result2 = helper.migrate_widget_signals()
        
        assert result2.migrated == count1
