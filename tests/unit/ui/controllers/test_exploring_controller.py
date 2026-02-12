# -*- coding: utf-8 -*-
"""
Unit tests for Exploring Controller.

Tests the ExploringController class for:
- Initialization and default state
- Teardown cleans up resources
- Tab activation/deactivation lifecycle
- Features cache management
- GroupBox mode state
- Selected features state tracking
- BaseController signal management helpers

All QGIS/Qt dependencies are mocked.
"""
import sys
import types
import pathlib
import importlib.util
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

_project_root = pathlib.Path(__file__).resolve().parents[4]


def _ensure_exploring_mocks():
    ROOT = "filter_mate"
    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = [str(_project_root)]
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    # Build package hierarchy
    _packages = {
        f"{ROOT}.ui": _project_root / "ui",
        f"{ROOT}.ui.controllers": _project_root / "ui" / "controllers",
        f"{ROOT}.ui.controllers.mixins": _project_root / "ui" / "controllers" / "mixins",
        f"{ROOT}.infrastructure": _project_root / "infrastructure",
        f"{ROOT}.infrastructure.signal_utils": MagicMock(),
        f"{ROOT}.infrastructure.utils": MagicMock(),
        f"{ROOT}.infrastructure.feedback": MagicMock(),
        f"{ROOT}.config": MagicMock(),
        f"{ROOT}.config.config": MagicMock(),
    }

    for pkg_name, pkg_dir in _packages.items():
        if isinstance(pkg_dir, MagicMock):
            sys.modules[pkg_name] = pkg_dir
        elif pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = [str(pkg_dir)]
            pkg.__package__ = pkg_name
            sys.modules[pkg_name] = pkg

    # Mock qgis
    qgis_mocks = {
        "qgis": MagicMock(),
        "qgis.core": MagicMock(),
        "qgis.PyQt": MagicMock(),
        "qgis.PyQt.QtCore": MagicMock(),
        "qgis.PyQt.QtGui": MagicMock(),
        "qgis.utils": MagicMock(),
    }
    for name, mock_obj in qgis_mocks.items():
        sys.modules[name] = mock_obj

    sys.modules["qgis.PyQt.QtCore"].QObject = object
    sys.modules["qgis.PyQt.QtCore"].pyqtSignal = MagicMock(side_effect=lambda *a: MagicMock())
    sys.modules["qgis.PyQt.QtCore"].QColor = None

    # Remove sip to avoid metaclass MRO conflict
    if "sip" in sys.modules:
        del sys.modules["sip"]

    # Create a fake BaseController that avoids the QObject metaclass problem
    class FakeBaseController:
        def __init__(self, dockwidget, filter_service=None, signal_manager=None):
            self._dockwidget = dockwidget
            self._filter_service = filter_service
            self._signal_manager = signal_manager
            self._is_active = False
            self._connection_ids = []

        @property
        def dockwidget(self):
            return self._dockwidget

        @property
        def filter_service(self):
            return self._filter_service

        @property
        def signal_manager(self):
            return self._signal_manager

        @property
        def is_active(self):
            return self._is_active

        def setup(self): pass
        def teardown(self): pass

        def on_tab_activated(self):
            self._is_active = True

        def on_tab_deactivated(self):
            self._is_active = False

        def _connect_signal(self, sender, signal_name, receiver, context=None):
            if self._signal_manager is None:
                try:
                    signal = getattr(sender, signal_name)
                    signal.connect(receiver)
                except (AttributeError, RuntimeError):
                    pass
                return None
            try:
                conn_id = self._signal_manager.connect(
                    sender=sender, signal_name=signal_name,
                    receiver=receiver, context=context or self.__class__.__name__
                )
                self._connection_ids.append(conn_id)
                return conn_id
            except Exception:
                return None

        def _disconnect_signal(self, connection_id):
            if self._signal_manager is None:
                return False
            if connection_id in self._connection_ids:
                success = self._signal_manager.disconnect(connection_id)
                if success:
                    self._connection_ids.remove(connection_id)
                return success
            return False

        def _disconnect_all_signals(self):
            if self._signal_manager is None:
                self._connection_ids.clear()
                return 0
            count = 0
            for conn_id in list(self._connection_ids):
                if self._signal_manager.disconnect(conn_id):
                    count += 1
            self._connection_ids.clear()
            return count

        def __repr__(self):
            return (
                f"<{self.__class__.__name__} "
                f"active={self._is_active} "
                f"connections={len(self._connection_ids)}>"
            )

    base_mod = types.ModuleType("filter_mate.ui.controllers.base_controller")
    base_mod.__package__ = "filter_mate.ui.controllers"
    base_mod.BaseController = FakeBaseController
    base_mod.QObjectABCMeta = type
    sys.modules["filter_mate.ui.controllers.base_controller"] = base_mod

    # Create a fake LayerSelectionMixin
    class FakeLayerSelectionMixin:
        PROVIDER_TYPE_MAP = {}

        def get_current_layer(self):
            return getattr(self, '_current_layer', None)

        def is_layer_valid(self, layer):
            return layer is not None and hasattr(layer, 'isValid') and layer.isValid()

    mixin_mod = types.ModuleType("filter_mate.ui.controllers.mixins.layer_selection_mixin")
    mixin_mod.__package__ = "filter_mate.ui.controllers.mixins"
    mixin_mod.LayerSelectionMixin = FakeLayerSelectionMixin
    sys.modules["filter_mate.ui.controllers.mixins.layer_selection_mixin"] = mixin_mod

    # Mock signal_utils with SignalBlocker
    sb_mod = sys.modules.get("filter_mate.infrastructure.signal_utils")
    if isinstance(sb_mod, MagicMock):
        sb_mod.SignalBlocker = MagicMock


_ensure_exploring_mocks()

# Load exploring_controller
_ec_path = _project_root / "ui" / "controllers" / "exploring_controller.py"
_ec_mod_name = "filter_mate.ui.controllers.exploring_controller"
if _ec_mod_name in sys.modules:
    del sys.modules[_ec_mod_name]

_ec_spec = importlib.util.spec_from_file_location(_ec_mod_name, str(_ec_path))
_ec_mod = importlib.util.module_from_spec(_ec_spec)
_ec_mod.__package__ = "filter_mate.ui.controllers"
sys.modules[_ec_mod_name] = _ec_mod
_ec_spec.loader.exec_module(_ec_mod)

ExploringController = _ec_mod.ExploringController


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_dockwidget():
    dw = MagicMock()
    dw.PROJECT_LAYERS = {}
    dw.widgets_initialized = True
    dw.current_layer = None
    dw._exploring_cache = {}
    return dw


@pytest.fixture
def controller(mock_dockwidget):
    return ExploringController(
        dockwidget=mock_dockwidget,
        filter_service=None,
        signal_manager=None,
        features_cache=None,
    )


@pytest.fixture
def controller_with_cache(mock_dockwidget):
    cache = {}
    return ExploringController(
        dockwidget=mock_dockwidget,
        filter_service=None,
        signal_manager=None,
        features_cache=cache,
    )


# ===========================================================================
# Tests -- Initialization
# ===========================================================================

class TestInit:
    def test_default_state(self, controller):
        assert controller._current_layer is None
        assert controller._current_field is None
        assert controller._selected_features == []
        assert controller._current_groupbox_mode == "single_selection"

    def test_features_cache_none_by_default(self, controller):
        assert controller._features_cache is None

    def test_features_cache_can_be_injected(self, controller_with_cache):
        assert controller_with_cache._features_cache is not None
        assert isinstance(controller_with_cache._features_cache, dict)

    def test_dockwidget_stored(self, controller, mock_dockwidget):
        assert controller.dockwidget is mock_dockwidget


# ===========================================================================
# Tests -- Teardown
# ===========================================================================

class TestTeardown:
    def test_clears_current_layer(self, controller):
        controller._current_layer = MagicMock()
        controller.teardown()
        assert controller._current_layer is None

    def test_clears_current_field(self, controller):
        controller._current_field = "some_field"
        controller.teardown()
        assert controller._current_field is None

    def test_clears_selected_features(self, controller):
        controller._selected_features = ["f1", "f2"]
        controller.teardown()
        assert controller._selected_features == []

    def test_clears_features_cache_if_present(self, controller_with_cache):
        controller_with_cache._features_cache["key"] = "value"
        controller_with_cache.teardown()
        assert controller_with_cache._features_cache == {}


# ===========================================================================
# Tests -- Tab lifecycle
# ===========================================================================

class TestTabLifecycle:
    def test_on_tab_activated_sets_active(self, controller):
        controller.on_tab_activated()
        assert controller.is_active is True

    def test_on_tab_deactivated_sets_inactive(self, controller):
        controller._is_active = True
        controller.on_tab_deactivated()
        assert controller.is_active is False


# ===========================================================================
# Tests -- BaseController properties
# ===========================================================================

class TestBaseControllerProperties:
    def test_filter_service_none(self, controller):
        assert controller.filter_service is None

    def test_signal_manager_none(self, controller):
        assert controller.signal_manager is None

    def test_is_active_default_false(self, controller):
        assert controller.is_active is False

    def test_repr(self, controller):
        r = repr(controller)
        assert "ExploringController" in r
        # The controller has its own __repr__ with layer/field/selected info
        assert "layer=" in r or "active=" in r


# ===========================================================================
# Tests -- Signal management helpers (from BaseController)
# ===========================================================================

class TestSignalManagement:
    def test_connect_signal_without_manager_fallback(self, controller):
        sender = MagicMock()
        result = controller._connect_signal(sender, "clicked", lambda: None)
        assert result is None  # No signal manager

    def test_disconnect_all_signals_without_manager(self, controller):
        controller._connection_ids = ["c1", "c2"]
        count = controller._disconnect_all_signals()
        assert count == 0
        assert controller._connection_ids == []

    def test_connect_signal_with_manager(self, mock_dockwidget):
        signal_mgr = MagicMock()
        signal_mgr.connect.return_value = "conn_001"
        ctrl = ExploringController(
            dockwidget=mock_dockwidget,
            signal_manager=signal_mgr,
        )
        sender = MagicMock()
        conn_id = ctrl._connect_signal(sender, "clicked", lambda: None)
        assert conn_id == "conn_001"
        assert "conn_001" in ctrl._connection_ids

    def test_disconnect_signal_with_manager(self, mock_dockwidget):
        signal_mgr = MagicMock()
        signal_mgr.connect.return_value = "conn_001"
        signal_mgr.disconnect.return_value = True
        ctrl = ExploringController(
            dockwidget=mock_dockwidget,
            signal_manager=signal_mgr,
        )
        ctrl._connection_ids = ["conn_001"]
        result = ctrl._disconnect_signal("conn_001")
        assert result is True
        assert "conn_001" not in ctrl._connection_ids
