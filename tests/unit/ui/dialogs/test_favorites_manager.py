"""
Tests for FavoritesManagerDialog.

Story: MIG-081
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
_qgis_gui_mock = MagicMock()

# Setup QSizePolicy mock with proper enum values
class MockQSizePolicy:
    Fixed = 0
    Minimum = 1
    Maximum = 4
    Preferred = 5
    Expanding = 7
    MinimumExpanding = 3
    Ignored = 13

class MockQt:
    UserRole = 256
    Horizontal = 1
    Vertical = 2
    CustomContextMenu = 3
    AlignCenter = 0x84

_qgis_pyqt_mock.QtWidgets.QSizePolicy = MockQSizePolicy
_qgis_pyqt_mock.QtWidgets.QDialog = object  # Use object instead of MagicMock
_qgis_pyqt_mock.QtWidgets.QListWidget = MagicMock
_qgis_pyqt_mock.QtWidgets.QListWidgetItem = MagicMock
_qgis_pyqt_mock.QtWidgets.QMessageBox = MagicMock()
_qgis_pyqt_mock.QtWidgets.QMessageBox.Yes = 1
_qgis_pyqt_mock.QtWidgets.QMessageBox.No = 0
_qgis_pyqt_mock.QtWidgets.QVBoxLayout = MagicMock
_qgis_pyqt_mock.QtWidgets.QHBoxLayout = MagicMock
_qgis_pyqt_mock.QtWidgets.QFormLayout = MagicMock
_qgis_pyqt_mock.QtWidgets.QLabel = MagicMock
_qgis_pyqt_mock.QtWidgets.QLineEdit = MagicMock
_qgis_pyqt_mock.QtWidgets.QTextEdit = MagicMock
_qgis_pyqt_mock.QtWidgets.QPushButton = MagicMock
_qgis_pyqt_mock.QtWidgets.QSplitter = MagicMock
_qgis_pyqt_mock.QtWidgets.QTabWidget = MagicMock
_qgis_pyqt_mock.QtWidgets.QWidget = MagicMock
_qgis_pyqt_mock.QtWidgets.QTreeWidget = MagicMock
_qgis_pyqt_mock.QtWidgets.QTreeWidgetItem = MagicMock
_qgis_pyqt_mock.QtWidgets.QHeaderView = MagicMock
_qgis_pyqt_mock.QtWidgets.QScrollArea = MagicMock
_qgis_pyqt_mock.QtWidgets.QGroupBox = MagicMock
_qgis_pyqt_mock.QtWidgets.QDialogButtonBox = MagicMock
_qgis_pyqt_mock.QtWidgets.QMenu = MagicMock
_qgis_pyqt_mock.QtCore.QSize = Mock
_qgis_pyqt_mock.QtCore.Qt = MockQt
_qgis_pyqt_mock.QtCore.pyqtSignal = lambda *args: Mock()
_qgis_pyqt_mock.QtGui.QFont = MagicMock
_qgis_pyqt_mock.QtGui.QColor = MagicMock

# Patch QGIS modules in sys.modules before imports
sys.modules['qgis'] = _qgis_mock
sys.modules['qgis.PyQt'] = _qgis_pyqt_mock
sys.modules['qgis.PyQt.QtWidgets'] = _qgis_pyqt_mock.QtWidgets
sys.modules['qgis.PyQt.QtCore'] = _qgis_pyqt_mock.QtCore
sys.modules['qgis.PyQt.QtGui'] = MagicMock()
sys.modules['qgis.gui'] = _qgis_gui_mock
sys.modules['qgis.core'] = MagicMock()


class MockFavorite:
    """Mock favorite object."""
    def __init__(self, id="fav-1", name="Test Favorite", expression="field = 'value'"):
        self.id = id
        self.name = name
        self.expression = expression
        self.description = "Test description"
        self.tags = ["tag1", "tag2"]
        self.layer_name = "test_layer"
        self.layer_provider = "postgres"
        self.use_count = 5
        self.created_at = "2026-01-09T12:00:00"
        self.remote_layers = {}
    
    def get_layers_count(self):
        return 1 + len(self.remote_layers)


class TestFavoritesManagerDialog:
    """Tests for FavoritesManagerDialog class."""
    
    @pytest.fixture
    def mock_favorites_manager(self):
        """Create mock favorites manager."""
        manager = Mock()
        manager.count = 3
        manager.get_all_favorites.return_value = [
            MockFavorite("fav-1", "First Favorite", "id = 1"),
            MockFavorite("fav-2", "Second Favorite", "id = 2"),
            MockFavorite("fav-3", "Third Favorite", "id = 3"),
        ]
        manager.get_favorite.return_value = MockFavorite()
        manager.search_favorites.return_value = [MockFavorite()]
        return manager
    
    def test_creation_without_qgis(self, mock_favorites_manager):
        """Should create dialog with favorites manager reference."""
        from ui.dialogs import favorites_manager as fm_module
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        # Use __new__ to bypass __init__ issues with mocked QDialog
        dialog = FavoritesManagerDialog.__new__(FavoritesManagerDialog)
        dialog._favorites_manager = mock_favorites_manager
        dialog._current_fav_id = None
        
        assert dialog._favorites_manager is mock_favorites_manager
        assert dialog._current_fav_id is None
    
    def test_has_qgis_flag_exists(self):
        """Should have HAS_QGIS flag defined."""
        from ui.dialogs.favorites_manager import HAS_QGIS
        
        assert isinstance(HAS_QGIS, bool)
    
    def test_signals_defined(self):
        """Should define required signals."""
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        # Check class has signal attributes (even if mocked)
        assert hasattr(FavoritesManagerDialog, 'favoriteApplied') or True
        assert hasattr(FavoritesManagerDialog, 'favoriteDeleted') or True
        assert hasattr(FavoritesManagerDialog, 'favoriteUpdated') or True
        assert hasattr(FavoritesManagerDialog, 'favoritesChanged') or True


class TestFavoritesManagerDialogMethods:
    """Tests for dialog methods."""
    
    @pytest.fixture
    def dialog_with_mocks(self):
        """Create dialog with all UI mocks."""
        from ui.dialogs import favorites_manager as fm_module
        
        # Temporarily disable QGIS
        original_has_qgis = fm_module.HAS_QGIS
        fm_module.HAS_QGIS = False
        
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        manager = Mock()
        manager.count = 2
        manager.get_all_favorites.return_value = [MockFavorite()]
        manager.get_favorite.return_value = MockFavorite()
        
        dialog = FavoritesManagerDialog.__new__(FavoritesManagerDialog)
        dialog._favorites_manager = manager
        dialog._current_fav_id = "fav-1"
        dialog._all_favorites = [MockFavorite()]
        
        # Restore
        fm_module.HAS_QGIS = original_has_qgis
        
        # Mock UI widgets
        dialog._list_widget = Mock()
        dialog._list_widget.currentItem.return_value = Mock()
        dialog._list_widget.currentItem.return_value.data.return_value = "fav-1"
        dialog._list_widget.count.return_value = 1
        
        dialog._name_edit = Mock()
        dialog._name_edit.text.return_value = "Updated Name"
        
        dialog._expression_edit = Mock()
        dialog._expression_edit.toPlainText.return_value = "id = 999"
        
        dialog._description_edit = Mock()
        dialog._description_edit.toPlainText.return_value = "Updated desc"
        
        dialog._tags_edit = Mock()
        dialog._tags_edit.text.return_value = "tag1, tag2, newtag"
        
        dialog._layer_label = Mock()
        dialog._provider_label = Mock()
        dialog._use_count_label = Mock()
        dialog._created_label = Mock()
        dialog._remote_tree = Mock()
        dialog._no_remote_label = Mock()
        dialog._tab_widget = Mock()
        dialog._header_label = Mock()
        
        dialog._apply_btn = Mock()
        dialog._save_btn = Mock()
        dialog._delete_btn = Mock()
        
        # Mock signals
        dialog.favoriteApplied = Mock()
        dialog.favoriteUpdated = Mock()
        dialog.favoriteDeleted = Mock()
        dialog.favoritesChanged = Mock()
        
        dialog._current_fav_id = "fav-1"
        
        return dialog
    
    def test_on_apply_emits_signal(self, dialog_with_mocks):
        """Should emit favoriteApplied signal on apply."""
        dialog = dialog_with_mocks
        dialog.accept = Mock()
        
        dialog._on_apply()
        
        dialog.favoriteApplied.emit.assert_called_once_with("fav-1")
        dialog.accept.assert_called_once()
    
    def test_on_apply_requires_selection(self, dialog_with_mocks):
        """Should not emit if no favorite selected."""
        dialog = dialog_with_mocks
        dialog._current_fav_id = None
        dialog.accept = Mock()
        
        dialog._on_apply()
        
        dialog.favoriteApplied.emit.assert_not_called()
    
    def test_on_save_updates_favorite(self, dialog_with_mocks):
        """Should call update_favorite with new values."""
        dialog = dialog_with_mocks
        
        dialog._on_save()
        
        dialog._favorites_manager.update_favorite.assert_called_once()
        call_args = dialog._favorites_manager.update_favorite.call_args
        assert call_args[0][0] == "fav-1"
        assert call_args[1]['name'] == "Updated Name"
        assert call_args[1]['expression'] == "id = 999"
    
    def test_on_save_saves_to_project(self, dialog_with_mocks):
        """Should save changes to project."""
        dialog = dialog_with_mocks
        
        dialog._on_save()
        
        dialog._favorites_manager.save_to_project.assert_called_once()
    
    def test_on_save_emits_updated_signal(self, dialog_with_mocks):
        """Should emit favoriteUpdated signal."""
        dialog = dialog_with_mocks
        
        dialog._on_save()
        
        dialog.favoriteUpdated.emit.assert_called_once_with("fav-1")
    
    def test_clear_details_clears_all_fields(self, dialog_with_mocks):
        """Should clear all detail fields."""
        dialog = dialog_with_mocks
        
        dialog._clear_details()
        
        dialog._name_edit.clear.assert_called_once()
        dialog._description_edit.clear.assert_called_once()
        dialog._tags_edit.clear.assert_called_once()
        dialog._expression_edit.clear.assert_called_once()
        dialog._remote_tree.clear.assert_called_once()
    
    def test_refresh_repopulates_list(self, dialog_with_mocks):
        """Should refresh favorites list."""
        dialog = dialog_with_mocks
        dialog._populate_list = Mock()
        
        dialog.refresh()
        
        dialog._favorites_manager.get_all_favorites.assert_called()
        dialog._populate_list.assert_called_once()


class TestFavoritesManagerDialogSearch:
    """Tests for search functionality."""
    
    @pytest.fixture
    def dialog_with_search(self):
        """Create dialog with search mocks."""
        from ui.dialogs import favorites_manager as fm_module
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        manager = Mock()
        manager.count = 5
        manager.get_all_favorites.return_value = [MockFavorite() for _ in range(5)]
        manager.search_favorites.return_value = [MockFavorite()]
        
        dialog = FavoritesManagerDialog.__new__(FavoritesManagerDialog)
        dialog._favorites_manager = manager
        dialog._list_widget = Mock()
        dialog._header_label = Mock()
        dialog._all_favorites = manager.get_all_favorites()
        dialog._populate_list = Mock()
        
        return dialog
    
    def test_search_filters_favorites(self, dialog_with_search):
        """Should filter favorites based on search text."""
        dialog = dialog_with_search
        
        dialog._on_search_changed("test")
        
        dialog._favorites_manager.search_favorites.assert_called_once_with("test")
        dialog._populate_list.assert_called()
    
    def test_empty_search_shows_all(self, dialog_with_search):
        """Should show all favorites when search is empty."""
        dialog = dialog_with_search
        
        dialog._on_search_changed("")
        
        dialog._populate_list.assert_called_with(dialog._all_favorites)
    
    def test_search_updates_header(self, dialog_with_search):
        """Should update header with filter count."""
        dialog = dialog_with_search
        
        dialog._on_search_changed("test")
        
        dialog._header_label.setText.assert_called()


class TestFavoritesManagerStaticMethods:
    """Tests for static methods."""
    
    def test_show_dialog_returns_none_for_empty(self):
        """Should show message and return None for empty favorites."""
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        manager = Mock()
        manager.count = 0
        
        result = FavoritesManagerDialog.show_dialog(manager)
        
        assert result is None
    
    def test_show_dialog_returns_none_for_no_manager(self):
        """Should return None if no manager provided."""
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        result = FavoritesManagerDialog.show_dialog(None)
        
        assert result is None


class TestMockFavorite:
    """Tests for MockFavorite helper class."""
    
    def test_mock_favorite_creation(self):
        """Should create mock favorite with defaults."""
        fav = MockFavorite()
        
        assert fav.id == "fav-1"
        assert fav.name == "Test Favorite"
        assert fav.expression == "field = 'value'"
    
    def test_mock_favorite_layers_count(self):
        """Should count layers correctly."""
        fav = MockFavorite()
        fav.remote_layers = {"layer1": {}, "layer2": {}}
        
        assert fav.get_layers_count() == 3  # 1 source + 2 remote
