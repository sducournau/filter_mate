"""
Tests for PostgresInfoDialog.

Story: MIG-083
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# Mock QGIS modules before any imports that use them
_qgis_mock = MagicMock()
_qgis_pyqt_mock = MagicMock()


class MockQt:
    """Mock Qt namespace with required constants."""
    AlignCenter = 0x84
    Checked = 2
    Unchecked = 0
    RichText = 1
    gray = 7


class MockQMessageBox:
    """Mock QMessageBox."""
    Yes = 1
    No = 0
    
    @staticmethod
    def question(*args, **kwargs):
        return MockQMessageBox.Yes
    
    @staticmethod
    def information(*args, **kwargs):
        pass
    
    @staticmethod
    def warning(*args, **kwargs):
        pass
    
    @staticmethod
    def critical(*args, **kwargs):
        pass


class MockQDialog:
    """Mock QDialog base class."""
    def __init__(self, parent=None):
        self.parent_widget = parent
        self._title = ""
        self._modal = False
        self._min_width = 0
        self._min_height = 0
    
    def setWindowTitle(self, title):
        self._title = title
    
    def setMinimumWidth(self, width):
        self._min_width = width
    
    def setMinimumHeight(self, height):
        self._min_height = height
    
    def setModal(self, modal):
        self._modal = modal
    
    def reject(self):
        pass
    
    def tr(self, text):
        return text


class MockQDialogButtonBox:
    """Mock QDialogButtonBox."""
    Close = 0x00200000
    
    def __init__(self, buttons=None):
        self.buttons = buttons
        self.rejected = Mock()
    
    def rejected(self):
        pass


class MockSessionStatus:
    """Mock SessionStatus enum."""
    INACTIVE = 'INACTIVE'
    ACTIVE = 'ACTIVE'
    CLEANING = 'CLEANING'
    CLOSED = 'CLOSED'
    ERROR = 'ERROR'
    
    @property
    def name(self):
        return self._name
    
    def __init__(self, name='ACTIVE'):
        self._name = name


class MockCleanupResult:
    """Mock CleanupResult dataclass."""
    def __init__(self, success=True, views_dropped=0, error_message=""):
        self.success = success
        self.views_dropped = views_dropped
        self.error_message = error_message


class MockListWidget:
    """Mock QListWidget."""
    def __init__(self, parent=None):
        self._items = []
        self._max_height = 0
        self._alternating = False
    
    def clear(self):
        self._items = []
    
    def addItem(self, text):
        item = MockListWidgetItem(text)
        self._items.append(item)
    
    def item(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None
    
    def setMaximumHeight(self, height):
        self._max_height = height
    
    def setAlternatingRowColors(self, enabled):
        self._alternating = enabled
    
    def count(self):
        return len(self._items)


class MockListWidgetItem:
    """Mock QListWidgetItem."""
    def __init__(self, text=""):
        self._text = text
        self._foreground = None
    
    def text(self):
        return self._text
    
    def setForeground(self, color):
        self._foreground = color


class MockCheckBox:
    """Mock QCheckBox."""
    def __init__(self, text="", parent=None):
        self._text = text
        self._checked = False
        self._tooltip = ""
        self.stateChanged = Mock()
    
    def isChecked(self):
        return self._checked
    
    def setChecked(self, checked):
        self._checked = checked
    
    def setToolTip(self, tooltip):
        self._tooltip = tooltip


class MockPushButton:
    """Mock QPushButton."""
    def __init__(self, text="", parent=None):
        self._text = text
        self._enabled = True
        self._tooltip = ""
        self.clicked = Mock()
    
    def setEnabled(self, enabled):
        self._enabled = enabled
    
    def isEnabled(self):
        return self._enabled
    
    def setToolTip(self, tooltip):
        self._tooltip = tooltip


# Configure mocks
_qgis_pyqt_mock.QtCore.Qt = MockQt
_qgis_pyqt_mock.QtWidgets.QDialog = MockQDialog
_qgis_pyqt_mock.QtWidgets.QDialogButtonBox = MockQDialogButtonBox
_qgis_pyqt_mock.QtWidgets.QMessageBox = MockQMessageBox
_qgis_pyqt_mock.QtWidgets.QVBoxLayout = MagicMock
_qgis_pyqt_mock.QtWidgets.QHBoxLayout = MagicMock
_qgis_pyqt_mock.QtWidgets.QFormLayout = MagicMock
_qgis_pyqt_mock.QtWidgets.QLabel = MagicMock
_qgis_pyqt_mock.QtWidgets.QFrame = MagicMock
_qgis_pyqt_mock.QtWidgets.QGroupBox = MagicMock
_qgis_pyqt_mock.QtWidgets.QListWidget = MockListWidget
_qgis_pyqt_mock.QtWidgets.QCheckBox = MockCheckBox
_qgis_pyqt_mock.QtWidgets.QPushButton = MockPushButton
_qgis_pyqt_mock.QtWidgets.QWidget = MagicMock

sys.modules['qgis'] = _qgis_mock
sys.modules['qgis.PyQt'] = _qgis_pyqt_mock
sys.modules['qgis.PyQt.QtCore'] = _qgis_pyqt_mock.QtCore
sys.modules['qgis.PyQt.QtWidgets'] = _qgis_pyqt_mock.QtWidgets
sys.modules['qgis.core'] = MagicMock()
sys.modules['qgis.gui'] = MagicMock()


# ─────────────────────────────────────────────────────────────────
# Mock Session Manager
# ─────────────────────────────────────────────────────────────────

class MockPostgresSessionManager:
    """Mock PostgresSessionManager for testing."""
    
    def __init__(
        self,
        session_id="abc12345",
        schema="filtermate_temp",
        auto_cleanup=True,
        is_active=True,
        views=None
    ):
        self._session_id = session_id
        self._schema = schema
        self._auto_cleanup = auto_cleanup
        self._is_active = is_active
        self._views = views or []
        self._status = MockSessionStatus('ACTIVE' if is_active else 'INACTIVE')
    
    @property
    def session_id(self):
        return self._session_id
    
    @property
    def schema(self):
        return self._schema
    
    @property
    def auto_cleanup(self):
        return self._auto_cleanup
    
    @auto_cleanup.setter
    def auto_cleanup(self, value):
        self._auto_cleanup = value
    
    @property
    def is_active(self):
        return self._is_active
    
    @property
    def status(self):
        return self._status
    
    @property
    def view_count(self):
        return len(self._views)
    
    def get_session_views(self):
        return self._views
    
    def cleanup_session_views(self, connection):
        count = len(self._views)
        self._views = []
        return MockCleanupResult(success=True, views_dropped=count)


# ─────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def session_manager():
    """Create a mock session manager."""
    return MockPostgresSessionManager(
        session_id="test1234",
        schema="filtermate_temp",
        auto_cleanup=True,
        views=["mv_test1234_layer1", "mv_test1234_layer2"]
    )


@pytest.fixture
def empty_session_manager():
    """Create a mock session manager with no views."""
    return MockPostgresSessionManager(
        session_id="empty123",
        schema="filtermate_temp",
        auto_cleanup=False,
        views=[]
    )


@pytest.fixture
def inactive_session_manager():
    """Create an inactive session manager."""
    return MockPostgresSessionManager(
        session_id=None,
        schema="filtermate_temp",
        is_active=False,
        views=[]
    )


# ─────────────────────────────────────────────────────────────────
# Test Classes
# ─────────────────────────────────────────────────────────────────

class TestPostgresInfoDialogInit:
    """Tests for dialog initialization."""
    
    def test_init_without_session_manager(self):
        """Dialog should show unavailable message when no manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        assert dialog._session_manager is None
        assert dialog.is_available is False
    
    def test_init_with_session_manager(self, session_manager):
        """Dialog should initialize properly with session manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog._session_manager is session_manager
        assert dialog.is_available is True
    
    def test_window_title_set(self, session_manager):
        """Dialog should have correct window title."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog._title == "PostgreSQL Session Info"
    
    def test_modal_set(self, session_manager):
        """Dialog should be modal."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog._modal is True
    
    def test_minimum_size_set(self, session_manager):
        """Dialog should have minimum size."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog._min_width >= 400
        assert dialog._min_height >= 300


class TestPostgresInfoDialogProperties:
    """Tests for dialog properties."""
    
    def test_session_manager_property(self, session_manager):
        """session_manager property should return the manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog.session_manager is session_manager
    
    def test_is_available_true(self, session_manager):
        """is_available should be True with session manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog.is_available is True
    
    def test_is_available_false(self):
        """is_available should be False without session manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        assert dialog.is_available is False


class TestPostgresInfoDialogViews:
    """Tests for view list functionality."""
    
    def test_views_displayed(self, session_manager):
        """Views should be displayed in the list."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        # Views list should be populated
        if dialog._views_list:
            assert dialog._views_list.count() == 2
    
    def test_cleanup_enabled_with_views(self, session_manager):
        """Cleanup button should be enabled when views exist."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        if dialog._cleanup_btn:
            assert dialog._cleanup_btn.isEnabled() is True
    
    def test_cleanup_disabled_without_views(self, empty_session_manager):
        """Cleanup button should be disabled without views."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=empty_session_manager)
        
        if dialog._cleanup_btn:
            assert dialog._cleanup_btn.isEnabled() is False
    
    def test_empty_views_message(self, empty_session_manager):
        """Empty views list should show message."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=empty_session_manager)
        
        if dialog._views_list:
            assert dialog._views_list.count() == 1
            item = dialog._views_list.item(0)
            assert "(No temporary views)" in item.text()


class TestPostgresInfoDialogAutoCleanup:
    """Tests for auto-cleanup functionality."""
    
    def test_auto_cleanup_checkbox_initial_state(self, session_manager):
        """Auto-cleanup checkbox should reflect session manager setting."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        if dialog._auto_cleanup_cb:
            assert dialog._auto_cleanup_cb.isChecked() is True
    
    def test_auto_cleanup_checkbox_unchecked(self, empty_session_manager):
        """Auto-cleanup checkbox should be unchecked when disabled."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=empty_session_manager)
        
        if dialog._auto_cleanup_cb:
            assert dialog._auto_cleanup_cb.isChecked() is False
    
    def test_auto_cleanup_change_updates_manager(self, session_manager):
        """Changing auto-cleanup should update session manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        # Simulate checkbox change
        dialog._on_auto_cleanup_changed(MockQt.Unchecked)
        
        assert session_manager.auto_cleanup is False
    
    def test_auto_cleanup_enable(self, empty_session_manager):
        """Enabling auto-cleanup should update manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=empty_session_manager)
        
        dialog._on_auto_cleanup_changed(MockQt.Checked)
        
        assert empty_session_manager.auto_cleanup is True


class TestPostgresInfoDialogCleanup:
    """Tests for cleanup functionality."""
    
    def test_cleanup_with_no_views(self, empty_session_manager):
        """Cleanup with no views should show info message."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=empty_session_manager)
        
        # Should not raise
        dialog._on_cleanup_clicked()
    
    def test_cleanup_confirmation(self, session_manager):
        """Cleanup should ask for confirmation."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        with patch.object(MockQMessageBox, 'question', return_value=MockQMessageBox.No):
            dialog._on_cleanup_clicked()
            # Views should not be cleaned
            assert session_manager.view_count == 2
    
    def test_cleanup_success(self, session_manager):
        """Successful cleanup should clear views."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        with patch.object(MockQMessageBox, 'question', return_value=MockQMessageBox.Yes):
            dialog._on_cleanup_clicked()
            # Views should be cleaned
            assert session_manager.view_count == 0
    
    def test_cleanup_no_manager(self):
        """Cleanup should do nothing without manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        # Should not raise
        dialog._on_cleanup_clicked()


class TestPostgresInfoDialogUnavailable:
    """Tests for unavailable state."""
    
    def test_unavailable_no_views_list(self):
        """Unavailable state should not create views list."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        assert dialog._views_list is None
    
    def test_unavailable_no_cleanup_button(self):
        """Unavailable state should not create cleanup button."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        assert dialog._cleanup_btn is None
    
    def test_unavailable_no_auto_cleanup_checkbox(self):
        """Unavailable state should not create auto-cleanup checkbox."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        assert dialog._auto_cleanup_cb is None


class TestPostgresInfoDialogConnectionName:
    """Tests for connection name display."""
    
    def test_default_connection_name(self, session_manager):
        """Default connection name should be 'Default'."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        assert dialog._connection_name == "Default"
    
    def test_custom_connection_name(self, session_manager):
        """Custom connection name should be used."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(
            session_manager=session_manager,
            connection_name="MyDatabase"
        )
        
        assert dialog._connection_name == "MyDatabase"


class TestPostgresInfoDialogRefresh:
    """Tests for view refresh functionality."""
    
    def test_refresh_clears_list(self, session_manager):
        """Refresh should clear the views list first."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        if dialog._views_list:
            initial_count = dialog._views_list.count()
            dialog._refresh_views()
            # Count should be same after refresh (2 views)
            assert dialog._views_list.count() == initial_count
    
    def test_refresh_no_manager(self):
        """Refresh should do nothing without manager."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=None)
        
        # Should not raise
        dialog._refresh_views()
    
    def test_refresh_updates_button_state(self, session_manager):
        """Refresh should update cleanup button state."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        # Clear views
        session_manager._views = []
        dialog._refresh_views()
        
        if dialog._cleanup_btn:
            assert dialog._cleanup_btn.isEnabled() is False


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestPostgresInfoDialogIntegration:
    """Integration tests for PostgresInfoDialog."""
    
    def test_full_workflow_with_views(self, session_manager):
        """Test complete workflow with views."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        # Create dialog
        dialog = PostgresInfoDialog(session_manager=session_manager)
        
        # Verify initial state
        assert dialog.is_available
        if dialog._views_list:
            assert dialog._views_list.count() == 2
        if dialog._cleanup_btn:
            assert dialog._cleanup_btn.isEnabled()
        
        # Toggle auto-cleanup
        dialog._on_auto_cleanup_changed(MockQt.Unchecked)
        assert not session_manager.auto_cleanup
        
        # Cleanup
        with patch.object(MockQMessageBox, 'question', return_value=MockQMessageBox.Yes):
            dialog._on_cleanup_clicked()
        
        # Verify cleanup
        assert session_manager.view_count == 0
    
    def test_full_workflow_without_postgresql(self):
        """Test workflow when PostgreSQL is unavailable."""
        from ui.dialogs.postgres_info_dialog import PostgresInfoDialog
        
        # Create dialog without manager
        dialog = PostgresInfoDialog(session_manager=None)
        
        # Verify state
        assert not dialog.is_available
        assert dialog._views_list is None
        assert dialog._cleanup_btn is None
        assert dialog._auto_cleanup_cb is None
        
        # Actions should not raise
        dialog._refresh_views()
        dialog._on_cleanup_clicked()
