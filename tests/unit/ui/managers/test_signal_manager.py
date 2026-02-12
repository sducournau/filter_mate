# -*- coding: utf-8 -*-
"""
Tests for DockwidgetSignalManager.

These tests mock all QGIS/PyQt dependencies to verify signal management
logic without a running QGIS application.

Module tested: ui.managers.dockwidget_signal_manager

Key behaviors tested:
    - manage_signal: connection/disconnection with cache
    - change_signal_state: low-level signal connect/disconnect
    - connect_widgets_signals / disconnect_widgets_signals: bulk operations
    - Cache operations: clear_cache, get_cache_state
    - SignalStateChangeError raised on bad input
"""
import sys
import types
import pathlib
import importlib.util
from unittest.mock import MagicMock

import pytest

# SignalStateChangeError will be imported from the same module instance
# that dockwidget_signal_manager uses (see below after module loading)

# ---------------------------------------------------------------------------
# Import isolation for DockwidgetSignalManager
#
# ui/managers/__init__.py imports ConfigurationManager which pulls in
# infrastructure.logging and other deep imports.  We bypass __init__.py
# entirely and load dockwidget_signal_manager.py directly from disk.
#
# The target module uses `from ...core.domain.exceptions import ...`
# which is a 3-level relative import:  ui.managers -> ui -> filter_mate -> core
# So we must register the full filter_mate.ui.managers package hierarchy.
# ---------------------------------------------------------------------------

_project_root = pathlib.Path(__file__).resolve().parents[4]

# Build the full package hierarchy that the relative imports expect.
# The relative import `from ...core.domain.exceptions` from
# filter_mate.ui.managers.dockwidget_signal_manager resolves to
# filter_mate.core.domain.exceptions
_package_hierarchy = [
    ("filter_mate", _project_root),
    ("filter_mate.ui", _project_root / "ui"),
    ("filter_mate.ui.managers", _project_root / "ui" / "managers"),
    ("filter_mate.core", _project_root / "core"),
    ("filter_mate.core.domain", _project_root / "core" / "domain"),
]

for _pkg_name, _pkg_dir in _package_hierarchy:
    if _pkg_name not in sys.modules:
        pkg = types.ModuleType(_pkg_name)
        pkg.__path__ = [str(_pkg_dir)]
        pkg.__package__ = _pkg_name
        sys.modules[_pkg_name] = pkg

# The exceptions module is pure Python, import it properly
_exc_spec = importlib.util.spec_from_file_location(
    "filter_mate.core.domain.exceptions",
    str(_project_root / "core" / "domain" / "exceptions.py"),
)
_exc_module = importlib.util.module_from_spec(_exc_spec)
_exc_module.__package__ = "filter_mate.core.domain"
sys.modules["filter_mate.core.domain.exceptions"] = _exc_module
_exc_spec.loader.exec_module(_exc_module)

# Mock modules that ConfigurationManager would import
sys.modules.setdefault("filter_mate.ui.managers.configuration_manager", MagicMock())
_infra_mock = MagicMock()
sys.modules.setdefault("filter_mate.infrastructure", _infra_mock)
sys.modules.setdefault("filter_mate.infrastructure.logging", MagicMock())
sys.modules.setdefault("filter_mate.infrastructure.signal_utils", MagicMock())

# Also register short-name aliases since conftest uses them
# (core.domain.exceptions is already importable from conftest setup)

# Load the target module from file, skipping __init__.py
_module_path = _project_root / "ui" / "managers" / "dockwidget_signal_manager.py"
_spec = importlib.util.spec_from_file_location(
    "filter_mate.ui.managers.dockwidget_signal_manager",
    str(_module_path),
    submodule_search_locations=[],
)
_module = importlib.util.module_from_spec(_spec)
_module.__package__ = "filter_mate.ui.managers"
sys.modules["filter_mate.ui.managers.dockwidget_signal_manager"] = _module
_spec.loader.exec_module(_module)

DockwidgetSignalManager = _module.DockwidgetSignalManager

# Import SignalStateChangeError from the SAME module instance that
# dockwidget_signal_manager uses, ensuring isinstance() checks match.
SignalStateChangeError = _module.SignalStateChangeError


# =========================================================================
# Fixtures
# =========================================================================

def _make_mock_widget(signal_name="clicked", handler=None):
    """Create a mock widget with a signal for testing.

    Returns a dict in the format expected by dockwidget.widgets:
        {"WIDGET": mock_widget, "SIGNALS": [(signal_name, handler)]}
    """
    widget = MagicMock()
    widget.isSignalConnected.return_value = False

    # Create a mock signal
    signal = MagicMock()
    setattr(widget, signal_name, signal)

    # hasattr check must work
    # MagicMock already returns True for hasattr by default

    handler = handler or MagicMock()

    return {
        "WIDGET": widget,
        "SIGNALS": [(signal_name, handler)],
    }


def _make_mock_dockwidget(widgets_dict=None):
    """Create a mock dockwidget with widgets dictionary."""
    dockwidget = MagicMock()
    dockwidget.widgets = widgets_dict or {}
    dockwidget.widgets_initialized = True
    dockwidget.PROJECT_LAYERS = {}
    dockwidget.current_layer = None
    dockwidget.project_props = {}
    return dockwidget


# =========================================================================
# Constructor
# =========================================================================

class TestDockwidgetSignalManagerInit:
    """Tests for DockwidgetSignalManager initialization."""

    def test_init_sets_dockwidget(self):
        dockwidget = MagicMock()
        manager = DockwidgetSignalManager(dockwidget)
        assert manager.dockwidget is dockwidget

    def test_init_empty_cache(self):
        dockwidget = MagicMock()
        manager = DockwidgetSignalManager(dockwidget)
        assert manager._signal_connection_states == {}

    def test_init_layer_tree_view_disconnected(self):
        dockwidget = MagicMock()
        manager = DockwidgetSignalManager(dockwidget)
        assert manager._layer_tree_view_signal_connected is False


# =========================================================================
# manage_signal
# =========================================================================

class TestManageSignal:
    """Tests for manage_signal() method."""

    def test_invalid_widget_path_not_list_raises(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)

        with pytest.raises(SignalStateChangeError):
            manager.manage_signal("NOT_A_LIST")

    def test_invalid_widget_path_wrong_length_raises(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)

        with pytest.raises(SignalStateChangeError):
            manager.manage_signal(["ONLY_ONE"])

    def test_invalid_widget_path_three_elements_raises(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)

        with pytest.raises(SignalStateChangeError):
            manager.manage_signal(["A", "B", "C"])

    def test_connect_signal(self):
        handler = MagicMock()
        widget_data = _make_mock_widget("clicked", handler)
        widgets = {"EXPLORING": {"MY_BUTTON": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        result = manager.manage_signal(["EXPLORING", "MY_BUTTON"], "connect")

        # change_signal_state should have been called internally
        # The widget's signal.connect should have been called
        assert result is not None

    def test_disconnect_signal(self):
        handler = MagicMock()
        widget_data = _make_mock_widget("clicked", handler)
        # Simulate that signal is currently connected
        widget_data["WIDGET"].isSignalConnected.return_value = True
        widgets = {"EXPLORING": {"MY_BUTTON": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        result = manager.manage_signal(["EXPLORING", "MY_BUTTON"], "disconnect")
        assert result is not None

    def test_skip_if_already_connected(self):
        handler = MagicMock()
        widget_data = _make_mock_widget("clicked", handler)
        widgets = {"EXPLORING": {"MY_BUTTON": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        # Pre-fill cache to indicate already connected
        manager._signal_connection_states["EXPLORING.MY_BUTTON.clicked"] = True

        result = manager.manage_signal(["EXPLORING", "MY_BUTTON"], "connect")
        # Should skip (already connected), return cached state
        assert result is True

    def test_skip_if_already_disconnected(self):
        handler = MagicMock()
        widget_data = _make_mock_widget("clicked", handler)
        widgets = {"EXPLORING": {"MY_BUTTON": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager._signal_connection_states["EXPLORING.MY_BUTTON.clicked"] = False

        result = manager.manage_signal(["EXPLORING", "MY_BUTTON"], "disconnect")
        assert result is False

    def test_filter_by_custom_signal_name(self):
        handler1 = MagicMock()
        handler2 = MagicMock()
        widget_data = {
            "WIDGET": MagicMock(),
            "SIGNALS": [
                ("clicked", handler1),
                ("toggled", handler2),
            ],
        }
        widget_data["WIDGET"].isSignalConnected.return_value = False
        widgets = {"EXPLORING": {"BTN": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager.manage_signal(
            ["EXPLORING", "BTN"], "connect", custom_signal_name="toggled"
        )

        # Only "toggled" cache key should be set, not "clicked"
        assert "EXPLORING.BTN.toggled" in manager._signal_connection_states
        assert "EXPLORING.BTN.clicked" not in manager._signal_connection_states

    def test_none_handler_signals_skipped(self):
        """Signals with None handler should be skipped."""
        widget_data = {
            "WIDGET": MagicMock(),
            "SIGNALS": [
                ("clicked", None),  # None handler
                ("toggled", MagicMock()),
            ],
        }
        widget_data["WIDGET"].isSignalConnected.return_value = False
        widgets = {"EXPLORING": {"BTN": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager.manage_signal(["EXPLORING", "BTN"], "connect")

        # Only toggled should be in cache, clicked had None handler
        assert "EXPLORING.BTN.clicked" not in manager._signal_connection_states
        assert "EXPLORING.BTN.toggled" in manager._signal_connection_states

    def test_empty_signals_list_returns_none(self):
        """Widget with empty SIGNALS list: state stays None, SIGNALS is falsy.

        The return expression is: True if (state is None and SIGNALS) else state
        With SIGNALS=[], the condition is False, so it returns state=None.
        """
        widget_data = {
            "WIDGET": MagicMock(),
            "SIGNALS": [],
        }
        widgets = {"EXPLORING": {"BTN": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        result = manager.manage_signal(["EXPLORING", "BTN"], "connect")
        assert result is None


# =========================================================================
# change_signal_state
# =========================================================================

class TestChangeSignalState:
    """Tests for change_signal_state() method."""

    def test_invalid_widget_path_raises(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)

        with pytest.raises(SignalStateChangeError):
            manager.change_signal_state("invalid", "clicked", MagicMock())

    def test_missing_signal_raises(self):
        widget = MagicMock(spec=[])  # spec=[] means no attributes
        widget_data = {"WIDGET": widget, "SIGNALS": []}
        widgets = {"GRP": {"W": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        with pytest.raises(SignalStateChangeError):
            manager.change_signal_state(
                ["GRP", "W"], "nonexistent_signal", MagicMock()
            )

    def test_connect_calls_signal_connect(self):
        handler = MagicMock()
        widget = MagicMock()
        widget.isSignalConnected.return_value = False
        signal = MagicMock()
        widget.clicked = signal

        widget_data = {"WIDGET": widget, "SIGNALS": [("clicked", handler)]}
        widgets = {"GRP": {"W": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager.change_signal_state(["GRP", "W"], "clicked", handler, "connect")
        signal.connect.assert_called_once_with(handler)

    def test_disconnect_calls_signal_disconnect(self):
        handler = MagicMock()
        widget = MagicMock()
        widget.isSignalConnected.return_value = True
        signal = MagicMock()
        widget.clicked = signal

        widget_data = {"WIDGET": widget, "SIGNALS": [("clicked", handler)]}
        widgets = {"GRP": {"W": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager.change_signal_state(["GRP", "W"], "clicked", handler, "disconnect")
        signal.disconnect.assert_called_once_with(handler)

    def test_layer_tree_view_uses_flag(self):
        """LAYER_TREE_VIEW uses internal flag instead of isSignalConnected."""
        handler = MagicMock()
        widget = MagicMock()
        signal = MagicMock()
        widget.currentLayerChanged = signal

        widget_data = {"WIDGET": widget, "SIGNALS": [("currentLayerChanged", handler)]}
        widgets = {"QGIS": {"LAYER_TREE_VIEW": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        # Initially disconnected
        assert manager._layer_tree_view_signal_connected is False

        manager.change_signal_state(
            ["QGIS", "LAYER_TREE_VIEW"], "currentLayerChanged", handler, "connect"
        )
        assert manager._layer_tree_view_signal_connected is True

        manager.change_signal_state(
            ["QGIS", "LAYER_TREE_VIEW"], "currentLayerChanged", handler, "disconnect"
        )
        assert manager._layer_tree_view_signal_connected is False

    def test_type_error_silenced_on_disconnect(self):
        """TypeError during disconnect should not propagate."""
        handler = MagicMock()
        widget = MagicMock()
        widget.isSignalConnected.return_value = True
        signal = MagicMock()
        signal.disconnect.side_effect = TypeError("not connected")
        widget.clicked = signal

        widget_data = {"WIDGET": widget, "SIGNALS": [("clicked", handler)]}
        widgets = {"GRP": {"W": widget_data}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        # Should not raise
        manager.change_signal_state(["GRP", "W"], "clicked", handler, "disconnect")


# =========================================================================
# connect_widgets_signals / disconnect_widgets_signals
# =========================================================================

class TestBulkSignalOperations:
    """Tests for connect_widgets_signals and disconnect_widgets_signals."""

    def test_connect_all_skips_qgis(self):
        handler = MagicMock()
        exploring_widget = _make_mock_widget("clicked", handler)
        qgis_widget = _make_mock_widget("currentLayerChanged", handler)

        widgets = {
            "EXPLORING": {"BTN": exploring_widget},
            "QGIS": {"LAYER_TREE_VIEW": qgis_widget},
        }
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager.connect_widgets_signals()

        # EXPLORING should be processed, QGIS should be skipped
        assert "EXPLORING.BTN.clicked" in manager._signal_connection_states
        assert "QGIS.LAYER_TREE_VIEW.currentLayerChanged" not in manager._signal_connection_states

    def test_disconnect_all_with_empty_widgets(self):
        dockwidget = _make_mock_dockwidget({})
        dockwidget.widgets = {}
        manager = DockwidgetSignalManager(dockwidget)

        # Should not raise
        manager.disconnect_widgets_signals()

    def test_disconnect_all_processes_non_qgis(self):
        handler = MagicMock()
        widget_data = _make_mock_widget("clicked", handler)
        widget_data["WIDGET"].isSignalConnected.return_value = True

        widgets = {
            "ACTION": {"FILTER": widget_data},
        }
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        manager.disconnect_widgets_signals()
        # Should have attempted disconnect
        assert "ACTION.FILTER.clicked" in manager._signal_connection_states


# =========================================================================
# Cache operations
# =========================================================================

class TestCacheOperations:
    """Tests for cache management methods."""

    def test_clear_cache_specific_key(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)
        manager._signal_connection_states = {
            "A.B.clicked": True,
            "C.D.toggled": False,
        }

        manager.clear_cache("A.B.clicked")
        assert "A.B.clicked" not in manager._signal_connection_states
        assert "C.D.toggled" in manager._signal_connection_states

    def test_clear_cache_all(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)
        manager._signal_connection_states = {
            "A.B.clicked": True,
            "C.D.toggled": False,
        }

        manager.clear_cache()
        assert manager._signal_connection_states == {}

    def test_clear_cache_nonexistent_key_no_error(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)

        # Should not raise
        manager.clear_cache("nonexistent.key")

    def test_get_cache_state_existing(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)
        manager._signal_connection_states["A.B.clicked"] = True

        assert manager.get_cache_state("A.B.clicked") is True

    def test_get_cache_state_nonexistent(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)

        assert manager.get_cache_state("nonexistent") is None

    def test_get_cache_state_false(self):
        dockwidget = _make_mock_dockwidget()
        manager = DockwidgetSignalManager(dockwidget)
        manager._signal_connection_states["A.B.clicked"] = False

        assert manager.get_cache_state("A.B.clicked") is False


# =========================================================================
# Properties
# =========================================================================

class TestProperties:
    """Tests for property accessors."""

    def test_widgets_property(self):
        widgets = {"EXPLORING": {}}
        dockwidget = _make_mock_dockwidget(widgets)
        manager = DockwidgetSignalManager(dockwidget)

        assert manager.widgets is widgets

    def test_widgets_initialized_true(self):
        dockwidget = _make_mock_dockwidget()
        dockwidget.widgets_initialized = True
        manager = DockwidgetSignalManager(dockwidget)

        assert manager.widgets_initialized is True

    def test_widgets_initialized_false(self):
        dockwidget = _make_mock_dockwidget()
        dockwidget.widgets_initialized = False
        manager = DockwidgetSignalManager(dockwidget)

        assert manager.widgets_initialized is False

    def test_widgets_initialized_missing_attribute(self):
        dockwidget = MagicMock(spec=[])  # no attributes
        dockwidget.widgets = {}
        manager = DockwidgetSignalManager(dockwidget)

        # getattr with default False
        assert manager.widgets_initialized is False
