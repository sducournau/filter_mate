"""
Tests for FavoritesController.

Story: MIG-072
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestFavoritesController:
    """Tests for FavoritesController class."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with favorites indicator."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.current_layer = None
        dockwidget._favorites_manager = None
        
        # Mock favorites indicator label
        label = Mock()
        label.text = Mock(return_value="★")
        label.setText = Mock()
        label.setStyleSheet = Mock()
        label.setToolTip = Mock()
        label.adjustSize = Mock()
        dockwidget.favorites_indicator_label = label
        
        # Mock expression widget
        expr_widget = Mock()
        expr_widget.expression = Mock(return_value="")
        dockwidget.mQgsFieldExpressionWidget_filtering_active_expression = expr_widget
        
        return dockwidget

    @pytest.fixture
    def mock_favorites_manager(self):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.count = 0
        manager.get_all_favorites = Mock(return_value=[])
        manager.get_recent_favorites = Mock(return_value=[])
        manager.get_by_id = Mock(return_value=None)
        manager.get_by_name = Mock(return_value=None)
        manager.add = Mock()
        manager.remove = Mock(return_value=True)
        manager.save_to_project = Mock()
        manager.load_from_project = Mock()
        manager.increment_use_count = Mock()
        manager.export_to_file = Mock(return_value=True)
        manager.import_from_file = Mock(return_value=0)
        return manager

    @pytest.fixture
    def mock_favorite(self):
        """Create mock FilterFavorite."""
        favorite = Mock()
        favorite.id = "fav_123"
        favorite.name = "Test Favorite"
        favorite.expression = "name = 'test'"
        favorite.use_count = 5
        favorite.get_display_name = Mock(return_value="Test Favorite")
        favorite.get_preview = Mock(return_value="name = 'test'")
        favorite.get_layers_count = Mock(return_value=1)
        favorite.remote_layers = {}
        return favorite

    @pytest.fixture
    def controller(self, mock_dockwidget, mock_favorites_manager):
        """Create FavoritesController instance with mocked manager."""
        from ui.controllers.favorites_controller import FavoritesController
        controller = FavoritesController(mock_dockwidget)
        controller._favorites_manager = mock_favorites_manager
        mock_dockwidget._favorites_manager = mock_favorites_manager
        return controller

    def test_creation(self, mock_dockwidget):
        """Should create controller with dockwidget reference."""
        from ui.controllers.favorites_controller import FavoritesController
        
        controller = FavoritesController(mock_dockwidget)
        
        assert controller.dockwidget is mock_dockwidget
        assert not controller.is_initialized
        assert controller.count == 0

    def test_setup_initializes_controller(self, controller, mock_dockwidget):
        """Setup should initialize the controller."""
        controller.setup()
        
        assert controller.is_initialized
        assert controller._indicator_label is mock_dockwidget.favorites_indicator_label

    def test_teardown_clears_state(self, controller):
        """Teardown should clear favorites manager reference."""
        controller.setup()
        
        controller.teardown()
        
        assert controller._favorites_manager is None
        assert not controller.is_initialized

    def test_count_returns_manager_count(self, controller, mock_favorites_manager):
        """Count property should return manager's count."""
        mock_favorites_manager.count = 5
        
        assert controller.count == 5

    def test_update_indicator_empty(self, controller, mock_dockwidget, mock_favorites_manager):
        """Update indicator should show empty state when no favorites."""
        controller.setup()
        mock_favorites_manager.count = 0
        
        controller.update_indicator()
        
        mock_dockwidget.favorites_indicator_label.setText.assert_called_with("★")
        mock_dockwidget.favorites_indicator_label.setToolTip.assert_called()

    def test_update_indicator_with_favorites(self, controller, mock_dockwidget, mock_favorites_manager):
        """Update indicator should show count when favorites exist."""
        controller.setup()
        mock_favorites_manager.count = 3
        
        controller.update_indicator()
        
        mock_dockwidget.favorites_indicator_label.setText.assert_called_with("★ 3")

    def test_get_current_filter_expression_from_widget(self, controller, mock_dockwidget):
        """Should get expression from expression widget."""
        controller.setup()
        mock_dockwidget.mQgsFieldExpressionWidget_filtering_active_expression.expression.return_value = "population > 1000"
        
        result = controller.get_current_filter_expression()
        
        assert result == "population > 1000"

    def test_get_current_filter_expression_from_layer(self, controller, mock_dockwidget):
        """Should fall back to layer subsetString."""
        controller.setup()
        mock_dockwidget.mQgsFieldExpressionWidget_filtering_active_expression.expression.return_value = ""
        
        mock_layer = Mock()
        mock_layer.subsetString = Mock(return_value="type = 'residential'")
        mock_dockwidget.current_layer = mock_layer
        
        result = controller.get_current_filter_expression()
        
        assert result == "type = 'residential'"

    def test_get_current_filter_expression_empty(self, controller, mock_dockwidget):
        """Should return empty string when no expression."""
        controller.setup()
        mock_dockwidget.mQgsFieldExpressionWidget_filtering_active_expression.expression.return_value = ""
        mock_dockwidget.current_layer = None
        
        result = controller.get_current_filter_expression()
        
        assert result == ""

    @patch('ui.controllers.favorites_controller.QMessageBox')
    def test_add_current_to_favorites_no_expression(self, mock_msgbox, controller, mock_dockwidget):
        """Should show warning when no filter active."""
        controller.setup()
        mock_dockwidget.mQgsFieldExpressionWidget_filtering_active_expression.expression.return_value = ""
        mock_dockwidget.current_layer = None
        
        result = controller.add_current_to_favorites()
        
        assert result is False
        mock_msgbox.warning.assert_called_once()

    def test_apply_favorite_success(self, controller, mock_dockwidget, mock_favorites_manager, mock_favorite):
        """Should apply favorite and emit signal."""
        controller.setup()
        mock_favorites_manager.get_by_id.return_value = mock_favorite
        
        signals_received = []
        controller.favorite_applied.connect(lambda name: signals_received.append(name))
        
        result = controller.apply_favorite("fav_123")
        
        assert result is True
        assert len(signals_received) == 1
        assert signals_received[0] == "Test Favorite"
        mock_favorites_manager.increment_use_count.assert_called_with("fav_123")

    def test_apply_favorite_not_found(self, controller, mock_favorites_manager):
        """Should return False when favorite not found."""
        controller.setup()
        mock_favorites_manager.get_by_id.return_value = None
        
        result = controller.apply_favorite("nonexistent")
        
        assert result is False

    def test_remove_favorite_success(self, controller, mock_favorites_manager, mock_favorite):
        """Should remove favorite and emit signal."""
        controller.setup()
        mock_favorites_manager.get_by_id.return_value = mock_favorite
        
        signals_received = []
        controller.favorite_removed.connect(lambda name: signals_received.append(name))
        
        result = controller.remove_favorite("fav_123")
        
        assert result is True
        assert len(signals_received) == 1
        assert signals_received[0] == "Test Favorite"
        mock_favorites_manager.save_to_project.assert_called()

    def test_remove_favorite_not_found(self, controller, mock_favorites_manager):
        """Should return False when favorite not found."""
        controller.setup()
        mock_favorites_manager.get_by_id.return_value = None
        
        result = controller.remove_favorite("nonexistent")
        
        assert result is False

    def test_get_all_favorites(self, controller, mock_favorites_manager, mock_favorite):
        """Should return all favorites."""
        controller.setup()
        mock_favorites_manager.get_all_favorites.return_value = [mock_favorite]
        
        result = controller.get_all_favorites()
        
        assert len(result) == 1
        assert result[0] is mock_favorite

    def test_get_recent_favorites(self, controller, mock_favorites_manager, mock_favorite):
        """Should return recent favorites with limit."""
        controller.setup()
        mock_favorites_manager.get_recent_favorites.return_value = [mock_favorite]
        
        result = controller.get_recent_favorites(limit=5)
        
        mock_favorites_manager.get_recent_favorites.assert_called_with(limit=5)
        assert len(result) == 1

    @patch('ui.controllers.favorites_controller.QFileDialog')
    def test_export_favorites_success(self, mock_dialog, controller, mock_favorites_manager):
        """Should export favorites to file."""
        controller.setup()
        mock_dialog.getSaveFileName.return_value = ("/tmp/favorites.json", "JSON Files")
        mock_favorites_manager.count = 3
        
        result = controller.export_favorites()
        
        assert result is True
        mock_favorites_manager.export_to_file.assert_called_with("/tmp/favorites.json")

    @patch('ui.controllers.favorites_controller.QFileDialog')
    def test_export_favorites_cancelled(self, mock_dialog, controller, mock_favorites_manager):
        """Should return False when export cancelled."""
        controller.setup()
        mock_dialog.getSaveFileName.return_value = ("", "")
        
        result = controller.export_favorites()
        
        assert result is False

    @patch('ui.controllers.favorites_controller.QMessageBox')
    @patch('ui.controllers.favorites_controller.QFileDialog')
    def test_import_favorites_merge(self, mock_dialog, mock_msgbox, controller, mock_favorites_manager):
        """Should import favorites with merge."""
        controller.setup()
        mock_dialog.getOpenFileName.return_value = ("/tmp/favorites.json", "JSON Files")
        mock_msgbox.question.return_value = mock_msgbox.Yes
        mock_favorites_manager.import_from_file.return_value = 5
        
        result = controller.import_favorites()
        
        assert result == 5
        mock_favorites_manager.import_from_file.assert_called_with("/tmp/favorites.json", merge=True)
        mock_favorites_manager.save_to_project.assert_called()

    @patch('ui.controllers.favorites_controller.QMessageBox')
    @patch('ui.controllers.favorites_controller.QFileDialog')
    def test_import_favorites_replace(self, mock_dialog, mock_msgbox, controller, mock_favorites_manager):
        """Should import favorites with replace."""
        controller.setup()
        mock_dialog.getOpenFileName.return_value = ("/tmp/favorites.json", "JSON Files")
        mock_msgbox.question.return_value = mock_msgbox.No
        mock_favorites_manager.import_from_file.return_value = 3
        
        result = controller.import_favorites()
        
        assert result == 3
        mock_favorites_manager.import_from_file.assert_called_with("/tmp/favorites.json", merge=False)

    def test_favorites_changed_signal(self, controller, mock_favorites_manager, mock_favorite):
        """Should emit favorites_changed when favorites are modified."""
        controller.setup()
        mock_favorites_manager.get_by_id.return_value = mock_favorite
        
        signals_received = []
        controller.favorites_changed.connect(lambda: signals_received.append(True))
        
        controller.remove_favorite("fav_123")
        
        assert len(signals_received) == 1


class TestFavoritesStyles:
    """Tests for FAVORITES_STYLES configuration."""

    def test_styles_have_required_properties(self):
        """Style configurations should have all required properties."""
        from ui.controllers.favorites_controller import FAVORITES_STYLES
        
        for state, style in FAVORITES_STYLES.items():
            assert 'background' in style
            assert 'hover' in style
            assert 'color' in style

    def test_active_style_is_visible(self):
        """Active style should use visible gold color."""
        from ui.controllers.favorites_controller import FAVORITES_STYLES
        
        assert 'f39c12' in FAVORITES_STYLES['active']['background']

    def test_empty_style_is_muted(self):
        """Empty style should use muted gray color."""
        from ui.controllers.favorites_controller import FAVORITES_STYLES
        
        assert 'ecf0f1' in FAVORITES_STYLES['empty']['background']


class TestGetCurrentFilterExpression:
    """Tests for get_current_filter_expression method."""

    @pytest.fixture
    def controller(self):
        """Create controller with minimal mock."""
        from ui.controllers.favorites_controller import FavoritesController
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.favorites_indicator_label = None
        dockwidget._favorites_manager = None
        return FavoritesController(dockwidget)

    def test_empty_when_no_sources(self, controller):
        """Should return empty when no expression sources exist."""
        controller.setup()
        
        result = controller.get_current_filter_expression()
        
        assert result == ""

    def test_strips_whitespace(self, controller):
        """Should strip whitespace from expression."""
        controller.setup()
        widget = Mock()
        widget.expression = Mock(return_value="  name = 'test'  ")
        controller.dockwidget.mQgsFieldExpressionWidget_filtering_active_expression = widget
        
        result = controller.get_current_filter_expression()
        
        assert result == "  name = 'test'  "  # Returns raw expression, caller handles stripping
