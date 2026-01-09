"""
Unit tests for PostgresSessionManager.

Tests session lifecycle, view management, and cleanup operations.
Story: MIG-078
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


# ─────────────────────────────────────────────────────────────────
# Mock PyQt5/QGIS before importing
# ─────────────────────────────────────────────────────────────────

class MockSignal:
    """Mock pyqtSignal for testing."""
    def __init__(self, *args):
        self.args = args
        self.callbacks = []
        self.emissions = []
    
    def emit(self, *args):
        self.emissions.append(args)
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


# Apply mocks
import sys
mock_pyqt = Mock()
mock_pyqt.pyqtSignal = MockSignal
mock_pyqt.QObject = MockQObject
sys.modules['qgis'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = mock_pyqt
sys.modules['qgis.core'] = Mock()
sys.modules['PyQt5'] = Mock()
sys.modules['PyQt5.QtCore'] = mock_pyqt


# Now import PostgresSessionManager
from core.services.postgres_session_manager import (
    PostgresSessionManager,
    SessionStatus,
    SessionInfo,
    ViewInfo,
    CleanupResult
)


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def manager():
    """Create a PostgresSessionManager instance."""
    return PostgresSessionManager()


@pytest.fixture
def active_manager():
    """Create an active session manager."""
    mgr = PostgresSessionManager()
    mgr.start_session("test1234")
    return mgr


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    
    # Default: no views found
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = (0,)
    
    return conn


@pytest.fixture
def mock_cursor_with_views(mock_connection):
    """Mock cursor that returns some views."""
    cursor = mock_connection.cursor.return_value
    
    # Setup sequential fetchall responses
    cursor.fetchall.side_effect = [
        [("mv_test1234_12345678",), ("mv_test1234_87654321",)],  # Session views
    ]
    cursor.fetchone.side_effect = [
        (2,),  # Session view count
        (5,),  # Total views
        (1,),  # Schema exists
    ]
    
    return mock_connection


# ─────────────────────────────────────────────────────────────────
# Test SessionStatus Enum
# ─────────────────────────────────────────────────────────────────

class TestSessionStatus:
    """Tests for SessionStatus enum."""
    
    def test_all_statuses_exist(self):
        """Verify all expected statuses exist."""
        assert SessionStatus.INACTIVE is not None
        assert SessionStatus.ACTIVE is not None
        assert SessionStatus.CLEANING is not None
        assert SessionStatus.CLOSED is not None
        assert SessionStatus.ERROR is not None


# ─────────────────────────────────────────────────────────────────
# Test Dataclasses
# ─────────────────────────────────────────────────────────────────

class TestDataclasses:
    """Tests for dataclass behavior."""
    
    def test_session_info_defaults(self):
        """Test SessionInfo default values."""
        info = SessionInfo(
            session_id="abc123",
            schema="test_schema",
            created_at=datetime.now()
        )
        
        assert info.status == SessionStatus.INACTIVE
        assert info.view_count == 0
        assert info.total_schema_views == 0
        assert info.other_session_views == 0
        assert info.schema_exists is False
        assert info.auto_cleanup_enabled is True
        assert info.last_activity is None
    
    def test_view_info_defaults(self):
        """Test ViewInfo default values."""
        info = ViewInfo(
            name="mv_test_123",
            session_id="test",
            schema="schema",
            layer_id="layer_123",
            created_at=datetime.now()
        )
        
        assert info.size_bytes == 0
        assert info.row_count == 0
    
    def test_cleanup_result_defaults(self):
        """Test CleanupResult default values."""
        result = CleanupResult(success=True)
        
        assert result.views_dropped == 0
        assert result.views_failed == 0
        assert result.schema_dropped is False
        assert result.error_message == ""


# ─────────────────────────────────────────────────────────────────
# Test Initialization
# ─────────────────────────────────────────────────────────────────

class TestInitialization:
    """Tests for manager initialization."""
    
    def test_default_initialization(self, manager):
        """Test default initialization values."""
        assert manager.session_id is None
        assert manager.schema == PostgresSessionManager.DEFAULT_SCHEMA
        assert manager.is_active is False
        assert manager.auto_cleanup is True
        assert manager.status == SessionStatus.INACTIVE
    
    def test_custom_schema(self):
        """Test custom schema initialization."""
        mgr = PostgresSessionManager(schema="custom_schema")
        assert mgr.schema == "custom_schema"
    
    def test_auto_cleanup_disabled(self):
        """Test disabled auto-cleanup."""
        mgr = PostgresSessionManager(auto_cleanup=False)
        assert mgr.auto_cleanup is False
    
    def test_view_count_starts_zero(self, manager):
        """Test view count starts at zero."""
        assert manager.view_count == 0
    
    def test_metrics_initialized(self, manager):
        """Test metrics are initialized."""
        metrics = manager.metrics
        
        assert metrics['views_created'] == 0
        assert metrics['views_dropped'] == 0
        assert metrics['cleanup_count'] == 0
        assert metrics['errors'] == 0


# ─────────────────────────────────────────────────────────────────
# Test Session Lifecycle
# ─────────────────────────────────────────────────────────────────

class TestSessionLifecycle:
    """Tests for session lifecycle management."""
    
    def test_generate_session_id(self, manager):
        """Test session ID generation."""
        session_id = manager.generate_session_id()
        
        assert session_id is not None
        assert len(session_id) == 8
        assert all(c in '0123456789abcdef' for c in session_id)
    
    def test_generate_unique_ids(self, manager):
        """Test that generated IDs are unique."""
        ids = [manager.generate_session_id() for _ in range(10)]
        assert len(set(ids)) == 10
    
    def test_start_session_auto_id(self, manager):
        """Test starting session with auto-generated ID."""
        session_id = manager.start_session()
        
        assert manager.session_id is not None
        assert len(manager.session_id) == 8
        assert manager.is_active is True
        assert manager.status == SessionStatus.ACTIVE
    
    def test_start_session_custom_id(self, manager):
        """Test starting session with custom ID."""
        session_id = manager.start_session("custom_id")
        
        assert session_id == "custom_id"
        assert manager.session_id == "custom_id"
    
    def test_start_session_signal_emitted(self, manager):
        """Test session_started signal is emitted."""
        manager.start_session("test123")
        
        assert len(manager.session_started.emissions) == 1
        assert manager.session_started.emissions[0] == ("test123",)
    
    def test_start_session_already_active(self, active_manager):
        """Test starting session when already active."""
        session_id = active_manager.start_session("new_session")
        
        # Should return existing session
        assert session_id == "test1234"
        assert active_manager.session_id == "test1234"
    
    def test_close_session(self, active_manager):
        """Test closing a session."""
        result = active_manager.close_session()
        
        assert result.success is True
        assert active_manager.session_id is None
        assert active_manager.status == SessionStatus.CLOSED
    
    def test_close_session_signal_emitted(self, active_manager):
        """Test session_closed signal is emitted."""
        active_manager.close_session()
        
        assert len(active_manager.session_closed.emissions) == 1
        assert active_manager.session_closed.emissions[0] == ("test1234",)
    
    def test_close_inactive_session(self, manager):
        """Test closing when no session is active."""
        result = manager.close_session()
        
        assert result.success is True
        assert "No active session" in result.error_message


# ─────────────────────────────────────────────────────────────────
# Test View Management
# ─────────────────────────────────────────────────────────────────

class TestViewManagement:
    """Tests for view management."""
    
    def test_get_view_name(self, active_manager):
        """Test view name generation."""
        view_name = active_manager.get_view_name("layer_123")
        
        assert view_name.startswith("mv_test1234_")
        assert "_" in view_name
    
    def test_get_view_name_with_suffix(self, active_manager):
        """Test view name with suffix."""
        view_name = active_manager.get_view_name("layer_123", "filtered")
        
        assert view_name.endswith("_filtered")
    
    def test_get_view_name_no_session(self, manager):
        """Test view name fails without session."""
        with pytest.raises(ValueError, match="No active session"):
            manager.get_view_name("layer_123")
    
    def test_register_view(self, active_manager):
        """Test registering a view."""
        active_manager.register_view("mv_test_view", "layer_123")
        
        assert active_manager.view_count == 1
        assert "mv_test_view" in active_manager.get_session_views()
    
    def test_register_view_signal(self, active_manager):
        """Test view_created signal is emitted."""
        active_manager.register_view("mv_test_view", "layer_123")
        
        assert len(active_manager.view_created.emissions) == 1
        assert active_manager.view_created.emissions[0] == ("test1234", "mv_test_view")
    
    def test_register_view_metrics(self, active_manager):
        """Test view registration updates metrics."""
        active_manager.register_view("mv_view_1", "layer_1")
        active_manager.register_view("mv_view_2", "layer_2")
        
        assert active_manager.metrics['views_created'] == 2
    
    def test_unregister_view(self, active_manager):
        """Test unregistering a view."""
        active_manager.register_view("mv_test_view", "layer_123")
        active_manager.unregister_view("mv_test_view")
        
        assert active_manager.view_count == 0
        assert "mv_test_view" not in active_manager.get_session_views()
    
    def test_unregister_view_signal(self, active_manager):
        """Test view_dropped signal is emitted."""
        active_manager.register_view("mv_test_view", "layer_123")
        active_manager.unregister_view("mv_test_view")
        
        assert len(active_manager.view_dropped.emissions) == 1
    
    def test_get_session_views(self, active_manager):
        """Test getting list of session views."""
        active_manager.register_view("mv_view_1", "layer_1")
        active_manager.register_view("mv_view_2", "layer_2")
        
        views = active_manager.get_session_views()
        
        assert len(views) == 2
        assert "mv_view_1" in views
        assert "mv_view_2" in views
    
    def test_is_session_view_registered(self, active_manager):
        """Test is_session_view for registered view."""
        active_manager.register_view("mv_test_view", "layer_123")
        
        assert active_manager.is_session_view("mv_test_view") is True
    
    def test_is_session_view_by_pattern(self, active_manager):
        """Test is_session_view by naming pattern."""
        # Not registered, but matches pattern
        assert active_manager.is_session_view("mv_test1234_something") is True
    
    def test_is_not_session_view(self, active_manager):
        """Test is_session_view returns False for other views."""
        assert active_manager.is_session_view("mv_other_session") is False


# ─────────────────────────────────────────────────────────────────
# Test Cleanup Operations
# ─────────────────────────────────────────────────────────────────

class TestCleanupOperations:
    """Tests for cleanup operations."""
    
    def test_cleanup_no_session(self, manager, mock_connection):
        """Test cleanup fails without session."""
        result = manager.cleanup_session_views(mock_connection)
        
        assert result.success is False
        assert "No session ID" in result.error_message
    
    def test_cleanup_no_views(self, active_manager, mock_connection):
        """Test cleanup with no views to drop."""
        result = active_manager.cleanup_session_views(mock_connection)
        
        assert result.success is True
        assert result.views_dropped == 0
    
    def test_cleanup_with_views(self, active_manager, mock_cursor_with_views):
        """Test cleanup drops views."""
        result = active_manager.cleanup_session_views(mock_cursor_with_views)
        
        assert result.success is True
        assert result.views_dropped == 2
    
    def test_cleanup_updates_metrics(self, active_manager, mock_cursor_with_views):
        """Test cleanup updates metrics."""
        active_manager.cleanup_session_views(mock_cursor_with_views)
        
        assert active_manager.metrics['cleanup_count'] == 1
        assert active_manager.metrics['last_cleanup'] is not None
    
    def test_cleanup_signal_emitted(self, active_manager, mock_cursor_with_views):
        """Test cleanup_completed signal is emitted."""
        active_manager.cleanup_session_views(mock_cursor_with_views)
        
        assert len(active_manager.cleanup_completed.emissions) == 1
        session_id, count = active_manager.cleanup_completed.emissions[0]
        assert session_id == "test1234"
        assert count == 2
    
    def test_cleanup_handles_error(self, active_manager, mock_connection):
        """Test cleanup handles database errors."""
        mock_connection.cursor.return_value.execute.side_effect = Exception("DB Error")
        
        result = active_manager.cleanup_session_views(mock_connection)
        
        assert result.success is False
        assert "DB Error" in result.error_message
        assert active_manager.metrics['errors'] == 1
    
    def test_cleanup_schema_no_exist(self, active_manager, mock_connection):
        """Test cleanup schema that doesn't exist."""
        result = active_manager.cleanup_schema_if_empty(mock_connection)
        
        assert result.success is True
        assert "does not exist" in result.error_message
    
    def test_cleanup_schema_other_sessions(self, active_manager, mock_connection):
        """Test cleanup schema with other sessions."""
        cursor = mock_connection.cursor.return_value
        cursor.fetchone.side_effect = [
            (1,),  # Schema exists
        ]
        cursor.fetchall.return_value = [
            ("mv_other_session_123",),  # Other session view
        ]
        
        result = active_manager.cleanup_schema_if_empty(mock_connection)
        
        assert result.success is False
        assert "other sessions" in result.error_message
    
    def test_cleanup_schema_force(self, active_manager, mock_connection):
        """Test force cleanup schema with other sessions."""
        cursor = mock_connection.cursor.return_value
        cursor.fetchone.side_effect = [
            (1,),  # Schema exists
        ]
        cursor.fetchall.return_value = [
            ("mv_other_session_123",),
        ]
        
        result = active_manager.cleanup_schema_if_empty(mock_connection, force=True)
        
        assert result.success is True
        assert result.schema_dropped is True


# ─────────────────────────────────────────────────────────────────
# Test Schema Management
# ─────────────────────────────────────────────────────────────────

class TestSchemaManagement:
    """Tests for schema management."""
    
    def test_ensure_schema_exists(self, manager, mock_connection):
        """Test ensuring schema exists."""
        result = manager.ensure_schema_exists(mock_connection)
        
        assert result is True
        cursor = mock_connection.cursor.return_value
        cursor.execute.assert_called()
    
    def test_ensure_schema_error(self, manager, mock_connection):
        """Test schema creation error handling."""
        mock_connection.cursor.return_value.execute.side_effect = Exception("Error")
        
        result = manager.ensure_schema_exists(mock_connection)
        
        assert result is False


# ─────────────────────────────────────────────────────────────────
# Test Session Info
# ─────────────────────────────────────────────────────────────────

class TestSessionInfo:
    """Tests for session info retrieval."""
    
    def test_get_session_info_basic(self, active_manager):
        """Test basic session info without DB."""
        info = active_manager.get_session_info()
        
        assert info.session_id == "test1234"
        assert info.schema == PostgresSessionManager.DEFAULT_SCHEMA
        assert info.status == SessionStatus.ACTIVE
        assert info.auto_cleanup_enabled is True
    
    def test_get_session_info_with_db(self, active_manager, mock_connection):
        """Test session info with DB connection."""
        cursor = mock_connection.cursor.return_value
        cursor.fetchone.side_effect = [
            (3,),   # Our session views
            (10,),  # Total views
            (1,),   # Schema exists
        ]
        
        info = active_manager.get_session_info(mock_connection)
        
        assert info.view_count == 3
        assert info.total_schema_views == 10
        assert info.other_session_views == 7
        assert info.schema_exists is True
    
    def test_get_session_info_html(self, active_manager):
        """Test HTML formatted session info."""
        html = active_manager.get_session_info_html()
        
        assert "<b>Session ID:</b>" in html
        assert "test1234" in html
        assert "ACTIVE" in html
    
    def test_get_session_info_html_with_db(self, active_manager, mock_connection):
        """Test HTML info with database data."""
        cursor = mock_connection.cursor.return_value
        cursor.fetchone.side_effect = [
            (2,),  # Our views
            (5,),  # Total
            (1,),  # Schema exists
        ]
        
        html = active_manager.get_session_info_html(mock_connection)
        
        assert "Your session views" in html
        assert "2" in html


# ─────────────────────────────────────────────────────────────────
# Test Utility Methods
# ─────────────────────────────────────────────────────────────────

class TestUtilityMethods:
    """Tests for utility methods."""
    
    def test_get_view_pattern_with_session(self, active_manager):
        """Test view pattern with active session."""
        pattern = active_manager.get_view_pattern()
        
        assert pattern == "mv_test1234_%"
    
    def test_get_view_pattern_custom_session(self, active_manager):
        """Test view pattern with custom session ID."""
        pattern = active_manager.get_view_pattern("custom123")
        
        assert pattern == "mv_custom123_%"
    
    def test_get_view_pattern_no_session(self, manager):
        """Test view pattern without session."""
        pattern = manager.get_view_pattern()
        
        assert pattern == "mv_%"
    
    def test_parse_view_name_valid(self, manager):
        """Test parsing valid view name."""
        result = manager.parse_view_name("mv_abc123_12345678_filtered")
        
        assert result is not None
        session_id, layer_hash, suffix = result
        assert session_id == "abc123"
        assert layer_hash == "12345678"
        assert suffix == "filtered"
    
    def test_parse_view_name_no_suffix(self, manager):
        """Test parsing view name without suffix."""
        result = manager.parse_view_name("mv_abc123_12345678")
        
        assert result is not None
        session_id, layer_hash, suffix = result
        assert suffix == ""
    
    def test_parse_view_name_invalid(self, manager):
        """Test parsing invalid view name."""
        result = manager.parse_view_name("not_a_view")
        
        assert result is None
    
    def test_reset(self, active_manager):
        """Test resetting manager state."""
        active_manager.register_view("mv_test", "layer")
        
        active_manager.reset()
        
        assert active_manager.session_id is None
        assert active_manager.status == SessionStatus.INACTIVE
        assert active_manager.view_count == 0
        assert active_manager.metrics['views_created'] == 0


# ─────────────────────────────────────────────────────────────────
# Test Properties
# ─────────────────────────────────────────────────────────────────

class TestProperties:
    """Tests for manager properties."""
    
    def test_auto_cleanup_setter(self, manager):
        """Test auto_cleanup setter."""
        manager.auto_cleanup = False
        assert manager.auto_cleanup is False
        
        manager.auto_cleanup = True
        assert manager.auto_cleanup is True
    
    def test_metrics_is_copy(self, manager):
        """Test metrics returns a copy."""
        metrics1 = manager.metrics
        metrics1['views_created'] = 999
        
        metrics2 = manager.metrics
        assert metrics2['views_created'] == 0


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for PostgresSessionManager."""
    
    def test_full_session_lifecycle(self, manager, mock_cursor_with_views):
        """Test complete session lifecycle."""
        # Start session
        session_id = manager.start_session()
        assert manager.is_active
        
        # Register views
        manager.register_view("mv_view_1", "layer_1")
        manager.register_view("mv_view_2", "layer_2")
        assert manager.view_count == 2
        
        # Close with cleanup
        result = manager.close_session(mock_cursor_with_views)
        assert result.success
        assert manager.status == SessionStatus.CLOSED
        assert manager.view_count == 0
    
    def test_multiple_session_cycles(self, manager):
        """Test multiple session start/close cycles."""
        for i in range(3):
            session_id = manager.start_session()
            assert manager.is_active
            
            manager.register_view(f"mv_view_{i}", f"layer_{i}")
            
            result = manager.close_session()
            assert result.success
            assert manager.view_count == 0
        
        # Signals should have been emitted for each cycle
        assert len(manager.session_started.emissions) == 3
        assert len(manager.session_closed.emissions) == 3
    
    def test_error_recovery(self, active_manager, mock_connection):
        """Test recovery from errors."""
        # Simulate error
        mock_connection.cursor.return_value.execute.side_effect = Exception("Error")
        
        result = active_manager.cleanup_session_views(mock_connection)
        assert not result.success
        assert active_manager.metrics['errors'] == 1
        
        # Reset error
        mock_connection.cursor.return_value.execute.side_effect = None
        mock_connection.cursor.return_value.fetchall.return_value = []
        
        # Should work again
        result = active_manager.cleanup_session_views(mock_connection)
        assert result.success
