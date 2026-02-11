# -*- coding: utf-8 -*-
"""
Unit tests for Layer Sync Controller.

Tests the LayerSyncController class for:
- Initialization and default state
- Post-filter protection window timing
- Filtering-in-progress blocking
- Manual vs automatic layer change behavior
- Layer validation
- is_layer_truly_deleted with protection window
- State management (save/mark/clear/restore)
- Reentrant call protection

All QGIS/Qt dependencies are mocked.
"""
import sys
import time
import types
import pathlib
import importlib.util
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

_project_root = pathlib.Path(__file__).resolve().parents[4]


def _ensure_sync_mocks():
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

    # Mock qgis modules
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

    # Remove sip to avoid metaclass MRO conflict
    if "sip" in sys.modules:
        del sys.modules["sip"]

    # Create a fake BaseController
    class FakeBaseController:
        def __init__(self, dockwidget, filter_service=None, signal_manager=None):
            self._dockwidget = dockwidget
            self._filter_service = filter_service
            self._signal_manager = signal_manager
            self._is_active = False
            self._initialized = False
            self._connection_ids = []

        @property
        def dockwidget(self):
            return self._dockwidget

        @property
        def filter_service(self):
            return self._filter_service

        @property
        def is_active(self):
            return self._is_active

        def setup(self): pass

        def teardown(self):
            self._connection_ids.clear()

        def on_tab_activated(self):
            self._is_active = True

        def on_tab_deactivated(self):
            self._is_active = False

        def _disconnect_all_signals(self):
            self._connection_ids.clear()
            return 0

    base_mod = types.ModuleType("filter_mate.ui.controllers.base_controller")
    base_mod.__package__ = "filter_mate.ui.controllers"
    base_mod.BaseController = FakeBaseController
    base_mod.QObjectABCMeta = type
    sys.modules["filter_mate.ui.controllers.base_controller"] = base_mod

    # Mock signal_utils with a working SignalBlocker context manager
    class _FakeSignalBlocker:
        """No-op context manager replacing the real SignalBlocker."""
        def __init__(self, *widgets):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    sb_mod = sys.modules.get("filter_mate.infrastructure.signal_utils")
    if isinstance(sb_mod, MagicMock):
        sb_mod.SignalBlocker = _FakeSignalBlocker


_ensure_sync_mocks()

# Load layer_sync_controller
_lsc_path = _project_root / "ui" / "controllers" / "layer_sync_controller.py"
_lsc_mod_name = "filter_mate.ui.controllers.layer_sync_controller"
if _lsc_mod_name in sys.modules:
    del sys.modules[_lsc_mod_name]

_lsc_spec = importlib.util.spec_from_file_location(_lsc_mod_name, str(_lsc_path))
_lsc_mod = importlib.util.module_from_spec(_lsc_spec)
_lsc_mod.__package__ = "filter_mate.ui.controllers"
sys.modules[_lsc_mod_name] = _lsc_mod
_lsc_spec.loader.exec_module(_lsc_mod)

LayerSyncController = _lsc_mod.LayerSyncController
POST_FILTER_PROTECTION_WINDOW = _lsc_mod.POST_FILTER_PROTECTION_WINDOW


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_dockwidget():
    dw = MagicMock()
    dw.PROJECT_LAYERS = {}
    dw._filter_completed_time = 0
    dw._saved_layer_id_before_filter = None
    dw._filtering_in_progress = False
    dw._updating_current_layer = False
    return dw


@pytest.fixture
def controller(mock_dockwidget):
    return LayerSyncController(dockwidget=mock_dockwidget)


@pytest.fixture
def mock_valid_layer():
    layer = MagicMock()
    layer.name.return_value = "test_layer"
    layer.id.return_value = "layer_abc"
    layer.isValid.return_value = True
    return layer


# ===========================================================================
# Tests -- Initialization
# ===========================================================================

class TestInit:
    def test_default_state(self, controller):
        assert controller._filter_completed_time == 0
        assert controller._saved_layer_id_before_filter is None
        assert controller._current_layer_id is None
        assert controller._updating_current_layer is False
        assert controller._filtering_in_progress is False

    def test_current_layer_id_property(self, controller):
        assert controller.current_layer_id is None
        controller._current_layer_id = "abc123"
        assert controller.current_layer_id == "abc123"


# ===========================================================================
# Tests -- Protection window properties
# ===========================================================================

class TestProtectionWindowProperties:
    def test_not_within_protection_by_default(self, controller):
        assert controller.is_within_protection_window is False

    def test_protection_remaining_zero_by_default(self, controller):
        assert controller.protection_remaining == 0.0

    def test_within_protection_after_mark(self, controller):
        controller.mark_filter_completed()
        assert controller.is_within_protection_window is True
        assert controller.protection_remaining > 0.0

    def test_protection_remaining_decreases(self, controller):
        controller._filter_completed_time = time.time() - 1.0
        remaining = controller.protection_remaining
        # With 1.5s window and 1.0s elapsed, ~0.5s remaining
        assert remaining < POST_FILTER_PROTECTION_WINDOW
        assert remaining > 0.0

    def test_protection_expired(self, controller):
        controller._filter_completed_time = time.time() - POST_FILTER_PROTECTION_WINDOW - 1.0
        assert controller.is_within_protection_window is False
        assert controller.protection_remaining == 0.0


# ===========================================================================
# Tests -- set_filtering_in_progress
# ===========================================================================

class TestSetFilteringInProgress:
    def test_sets_flag(self, controller):
        controller.set_filtering_in_progress(True)
        assert controller._filtering_in_progress is True

    def test_clears_flag(self, controller):
        controller._filtering_in_progress = True
        controller.set_filtering_in_progress(False)
        assert controller._filtering_in_progress is False

    def test_syncs_with_dockwidget(self, controller, mock_dockwidget):
        controller.set_filtering_in_progress(True)
        assert mock_dockwidget._filtering_in_progress is True


# ===========================================================================
# Tests -- save_layer_before_filter
# ===========================================================================

class TestSaveLayerBeforeFilter:
    def test_saves_layer_id(self, controller, mock_valid_layer):
        controller.save_layer_before_filter(mock_valid_layer)
        assert controller._saved_layer_id_before_filter == "layer_abc"

    def test_saves_none_when_no_layer(self, controller, mock_dockwidget):
        mock_dockwidget.current_layer = None
        controller.save_layer_before_filter(None)
        assert controller._saved_layer_id_before_filter is None


# ===========================================================================
# Tests -- mark_filter_completed
# ===========================================================================

class TestMarkFilterCompleted:
    def test_sets_timestamp(self, controller):
        before = time.time()
        controller.mark_filter_completed()
        after = time.time()
        assert before <= controller._filter_completed_time <= after

    def test_clears_filtering_flag(self, controller):
        controller._filtering_in_progress = True
        controller.mark_filter_completed()
        assert controller._filtering_in_progress is False

    def test_syncs_with_dockwidget(self, controller, mock_dockwidget):
        controller.mark_filter_completed()
        assert mock_dockwidget._filter_completed_time > 0
        assert mock_dockwidget._filtering_in_progress is False


# ===========================================================================
# Tests -- clear_protection
# ===========================================================================

class TestClearProtection:
    def test_clears_all_state(self, controller):
        controller._filter_completed_time = time.time()
        controller._saved_layer_id_before_filter = "some_id"
        controller._filtering_in_progress = True

        controller.clear_protection()

        assert controller._filter_completed_time == 0
        assert controller._saved_layer_id_before_filter is None
        assert controller._filtering_in_progress is False

    def test_syncs_with_dockwidget(self, controller, mock_dockwidget):
        controller._filter_completed_time = time.time()
        controller.clear_protection()
        assert mock_dockwidget._filter_completed_time == 0
        assert mock_dockwidget._saved_layer_id_before_filter is None
        assert mock_dockwidget._filtering_in_progress is False


# ===========================================================================
# Tests -- validate_layer
# ===========================================================================

class TestValidateLayer:
    def test_none_layer_invalid(self, controller):
        assert controller.validate_layer(None) is False

    def test_valid_layer(self, controller, mock_valid_layer):
        assert controller.validate_layer(mock_valid_layer) is True

    def test_invalid_layer(self, controller):
        layer = MagicMock()
        layer.isValid.return_value = False
        assert controller.validate_layer(layer) is False

    def test_deleted_cpp_object(self, controller):
        layer = MagicMock()
        layer.name.side_effect = RuntimeError("C++ object deleted")
        assert controller.validate_layer(layer) is False


# ===========================================================================
# Tests -- is_layer_truly_deleted
# ===========================================================================

class TestIsLayerTrulyDeleted:
    def test_none_layer_is_deleted(self, controller):
        assert controller.is_layer_truly_deleted(None) is True

    def test_blocked_during_filtering(self, controller, mock_valid_layer):
        controller._filtering_in_progress = True
        assert controller.is_layer_truly_deleted(mock_valid_layer) is False

    def test_blocked_during_protection_window(self, controller, mock_valid_layer):
        controller._filter_completed_time = time.time()
        assert controller.is_layer_truly_deleted(mock_valid_layer) is False

    def test_sip_deleted_returns_true(self, controller, mock_valid_layer):
        # Outside protection window
        controller._filter_completed_time = 0
        controller._filtering_in_progress = False
        # Ensure sip is available for the test
        sip_mock = MagicMock()
        sip_mock.isdeleted.return_value = True
        sys.modules["sip"] = sip_mock
        assert controller.is_layer_truly_deleted(mock_valid_layer) is True

    def test_sip_not_deleted_returns_false(self, controller, mock_valid_layer):
        controller._filter_completed_time = 0
        controller._filtering_in_progress = False
        sip_mock = MagicMock()
        sip_mock.isdeleted.return_value = False
        sys.modules["sip"] = sip_mock
        assert controller.is_layer_truly_deleted(mock_valid_layer) is False


# ===========================================================================
# Tests -- on_current_layer_changed (CRIT-005 protection)
# ===========================================================================

class TestOnCurrentLayerChanged:
    def test_blocks_reentrant_call(self, controller, mock_valid_layer):
        controller._updating_current_layer = True
        assert controller.on_current_layer_changed(mock_valid_layer) is False

    def test_blocks_auto_change_during_filtering(self, controller, mock_valid_layer):
        controller._filtering_in_progress = True
        result = controller.on_current_layer_changed(mock_valid_layer, manual_change=False)
        assert result is False

    def test_allows_manual_change_during_filtering(self, controller, mock_valid_layer):
        controller._filtering_in_progress = True
        # Need to make _ensure_valid_current_layer return the layer
        controller._find_fallback_layer = MagicMock(return_value=None)
        result = controller.on_current_layer_changed(mock_valid_layer, manual_change=True)
        assert result is True

    def test_blocks_none_during_protection(self, controller):
        controller._filter_completed_time = time.time()
        controller._saved_layer_id_before_filter = "saved_id"
        result = controller.on_current_layer_changed(None, manual_change=False)
        assert result is False

    def test_blocks_different_layer_during_protection(self, controller, mock_valid_layer):
        controller._filter_completed_time = time.time()
        controller._saved_layer_id_before_filter = "other_layer_id"
        result = controller.on_current_layer_changed(mock_valid_layer, manual_change=False)
        assert result is False

    def test_allows_same_layer_during_protection(self, controller, mock_valid_layer):
        controller._filter_completed_time = time.time()
        controller._saved_layer_id_before_filter = "layer_abc"  # matches mock layer id
        result = controller.on_current_layer_changed(mock_valid_layer, manual_change=False)
        assert result is True
        assert controller._current_layer_id == "layer_abc"

    def test_allows_manual_change_during_protection(self, controller, mock_valid_layer):
        controller._filter_completed_time = time.time()
        controller._saved_layer_id_before_filter = "other_id"
        result = controller.on_current_layer_changed(mock_valid_layer, manual_change=True)
        assert result is True


# ===========================================================================
# Tests -- POST_FILTER_PROTECTION_WINDOW constant
# ===========================================================================

class TestProtectionConstant:
    def test_protection_window_value(self):
        assert POST_FILTER_PROTECTION_WINDOW == 1.5
