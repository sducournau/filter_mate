"""
Tests for ConfigController.

Story: MIG-070
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


class TestConfigController:
    """Tests for ConfigController class."""

    def test_creation(self, mock_dockwidget):
        """Should create controller with dockwidget reference."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)

        assert controller.dockwidget is mock_dockwidget
        assert controller.pending_changes == []
        assert not controller.has_pending_changes

    def test_setup_initializes_controller(self, mock_dockwidget):
        """Setup should initialize the controller."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        assert controller._initialized is True

    def test_teardown_clears_state(self, mock_dockwidget):
        """Teardown should clear pending changes."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()
        controller._pending_changes = [{'path': ['test']}]
        controller._changes_pending = True

        controller.teardown()

        assert controller.pending_changes == []
        assert not controller._changes_pending


class TestPendingChanges:
    """Tests for pending changes management."""

    def test_has_pending_changes_false_when_empty(self, mock_dockwidget):
        """has_pending_changes should be False when no changes."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)

        assert controller.has_pending_changes is False

    def test_has_pending_changes_true_when_pending(self, mock_dockwidget):
        """has_pending_changes should be True when changes pending."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller._pending_changes = [{'path': ['test']}]
        controller._changes_pending = True

        assert controller.has_pending_changes is True


class TestApplyPendingChanges:
    """Tests for apply_pending_config_changes."""

    def test_apply_no_changes_returns_true(self, mock_dockwidget):
        """Should return True when no changes to apply."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        result = controller.apply_pending_config_changes()

        assert result is True

    def test_apply_clears_pending_changes(self, mock_dockwidget):
        """Should clear pending changes after applying."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()
        controller._pending_changes = [{'path': ['TEST_KEY'], 'index': Mock(), 'item': Mock()}]
        controller._changes_pending = True

        result = controller.apply_pending_config_changes()

        assert result is True
        assert controller.pending_changes == []
        assert not controller._changes_pending

    def test_apply_disables_buttonbox(self, mock_dockwidget):
        """Should disable buttonBox after applying changes."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()
        controller._pending_changes = [{'path': ['TEST'], 'index': Mock(), 'item': Mock()}]
        controller._changes_pending = True

        controller.apply_pending_config_changes()

        mock_dockwidget.buttonBox.setEnabled.assert_called_with(False)

    def test_apply_saves_configuration(self, mock_dockwidget):
        """Should save configuration after applying changes."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()
        controller._pending_changes = [{'path': ['TEST'], 'index': Mock(), 'item': Mock()}]
        controller._changes_pending = True

        controller.apply_pending_config_changes()

        mock_dockwidget.save_configuration_model.assert_called()


class TestCancelPendingChanges:
    """Tests for cancel_pending_config_changes."""

    def test_cancel_no_changes_does_nothing(self, mock_dockwidget):
        """Should do nothing when no changes to cancel."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        # Should not raise
        controller.cancel_pending_config_changes()

        assert controller.pending_changes == []

    def test_cancel_clears_pending_changes(self, mock_dockwidget):
        """Should clear pending changes after cancelling."""
        from ui.controllers.config_controller import ConfigController

        # Mock the JSON file loading
        with patch('builtins.open', MagicMock()):
            with patch('json.load', return_value={}):
                with patch('ui.controllers.config_controller.JsonModel', Mock()):
                    controller = ConfigController(mock_dockwidget)
                    controller.setup()
                    controller._pending_changes = [{'path': ['TEST']}]
                    controller._changes_pending = True

                    controller.cancel_pending_config_changes()

                    assert controller.pending_changes == []
                    assert not controller._changes_pending

    def test_cancel_disables_buttonbox(self, mock_dockwidget):
        """Should disable buttonBox after cancelling changes."""
        from ui.controllers.config_controller import ConfigController

        with patch('builtins.open', MagicMock()):
            with patch('json.load', return_value={}):
                with patch('ui.controllers.config_controller.JsonModel', Mock()):
                    controller = ConfigController(mock_dockwidget)
                    controller.setup()
                    controller._pending_changes = [{'path': ['TEST']}]
                    controller._changes_pending = True

                    controller.cancel_pending_config_changes()

                    mock_dockwidget.buttonBox.setEnabled.assert_called_with(False)


class TestThemeChange:
    """Tests for theme change handling."""

    def test_apply_theme_change_ignores_non_theme(self, mock_dockwidget):
        """Should ignore changes that don't affect theme."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        changes_summary = []
        change = {'path': ['OTHER_KEY'], 'index': Mock(), 'item': Mock()}

        controller._apply_theme_change(change, changes_summary)

        assert changes_summary == []

    def test_apply_theme_change_dark(self, mock_dockwidget):
        """Should apply dark theme."""
        from ui.controllers.config_controller import ConfigController

        # Mock the model item
        mock_value_item = Mock()
        mock_value_item.data = Mock(return_value={'value': 'dark', 'choices': ['auto', 'dark', 'light']})
        mock_dockwidget.config_view.model.itemFromIndex.return_value = mock_value_item

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        with patch('ui.controllers.config_controller.StyleLoader') as mock_loader:
            changes_summary = []
            mock_index = Mock()
            mock_index.siblingAtColumn.return_value = mock_index
            change = {'path': ['UI', 'ACTIVE_THEME'], 'index': mock_index, 'item': Mock()}

            controller._apply_theme_change(change, changes_summary)

            assert 'Theme: dark' in changes_summary


class TestUIProfileChange:
    """Tests for UI profile change handling."""

    def test_apply_profile_change_compact(self, mock_dockwidget):
        """Should apply compact profile."""
        from ui.controllers.config_controller import ConfigController

        mock_value_item = Mock()
        mock_value_item.data = Mock(return_value={'value': 'compact', 'choices': ['auto', 'compact', 'normal']})
        mock_dockwidget.config_view.model.itemFromIndex.return_value = mock_value_item

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        with patch('ui.controllers.config_controller.UIConfig') as mock_config:
            with patch('ui.controllers.config_controller.DisplayProfile') as mock_profile:
                mock_config.get_profile_name.return_value = 'compact'

                changes_summary = []
                mock_index = Mock()
                mock_index.siblingAtColumn.return_value = mock_index
                change = {'path': ['UI', 'UI_PROFILE'], 'index': mock_index, 'item': Mock()}

                controller._apply_ui_profile_change(change, changes_summary)

                assert 'Profile: compact' in changes_summary


class TestConfigPersistence:
    """Tests for configuration persistence."""

    def test_get_current_config(self, mock_dockwidget):
        """Should return current configuration."""
        from ui.controllers.config_controller import ConfigController

        mock_dockwidget.CONFIG_DATA = {'theme': 'dark', 'profile': 'compact'}

        controller = ConfigController(mock_dockwidget)

        result = controller.get_current_config()

        assert result == {'theme': 'dark', 'profile': 'compact'}

    def test_set_config_value(self, mock_dockwidget):
        """Should set configuration value."""
        from ui.controllers.config_controller import ConfigController

        mock_dockwidget.CONFIG_DATA = {}

        controller = ConfigController(mock_dockwidget)

        result = controller.set_config_value('theme', 'dark')

        assert result is True
        assert mock_dockwidget.CONFIG_DATA['theme'] == 'dark'


class TestSignals:
    """Tests for Qt signals."""

    def test_config_changed_signal_emitted(self, mock_dockwidget):
        """config_changed signal should be emitted on change."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.setup()

        # Track signal emission
        signal_received = []
        controller.config_changed.connect(lambda k, v: signal_received.append((k, v)))

        controller.set_config_value('theme', 'dark')

        assert len(signal_received) == 1
        assert signal_received[0][0] == 'theme'


class TestTabLifecycle:
    """Tests for tab lifecycle hooks."""

    def test_on_tab_activated(self, mock_dockwidget):
        """on_tab_activated should set is_active."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)

        controller.on_tab_activated()

        assert controller.is_active is True

    def test_on_tab_deactivated(self, mock_dockwidget):
        """on_tab_deactivated should clear is_active."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller.on_tab_activated()

        controller.on_tab_deactivated()

        assert controller.is_active is False


class TestRepr:
    """Tests for string representation."""

    def test_repr(self, mock_dockwidget):
        """__repr__ should show useful info."""
        from ui.controllers.config_controller import ConfigController

        controller = ConfigController(mock_dockwidget)
        controller._pending_changes = [{'path': ['test']}]

        result = repr(controller)

        assert 'ConfigController' in result
        assert 'pending=1' in result
