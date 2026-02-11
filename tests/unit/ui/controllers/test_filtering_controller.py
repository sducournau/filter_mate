# -*- coding: utf-8 -*-
"""
Unit tests for Filtering Controller.

Tests the FilteringController and its associated domain objects:
- PredicateType enum: spatial predicate values
- BufferType enum: buffer application modes
- CombineOperator enum: SQL operator mapping (with i18n)
- FilterConfiguration dataclass: validation, serialization
- FilterResult dataclass: execution result data
- FilteringController: state management, predicate/buffer/target management,
  expression building, configuration build/apply, execution guards

All QGIS/Qt dependencies are mocked.
"""
import sys
import types
import pathlib
import importlib.util
from abc import ABCMeta, abstractmethod
from unittest.mock import MagicMock, PropertyMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

_project_root = pathlib.Path(__file__).resolve().parents[4]


def _ensure_filtering_mocks():
    ROOT = "filter_mate"
    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = [str(_project_root)]
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    # Build the package hierarchy the relative imports need
    _packages = {
        f"{ROOT}.ui": _project_root / "ui",
        f"{ROOT}.ui.controllers": _project_root / "ui" / "controllers",
        f"{ROOT}.ui.controllers.mixins": _project_root / "ui" / "controllers" / "mixins",
        f"{ROOT}.infrastructure": _project_root / "infrastructure",
        f"{ROOT}.infrastructure.signal_utils": MagicMock(),
        f"{ROOT}.infrastructure.utils": MagicMock(),
        f"{ROOT}.infrastructure.feedback": MagicMock(),
        f"{ROOT}.adapters": MagicMock(),
        f"{ROOT}.adapters.task_builder": MagicMock(),
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

    # Provide a real pyqtSignal mock that returns a descriptor-like object
    sys.modules["qgis.PyQt.QtCore"].pyqtSignal = MagicMock(side_effect=lambda *a: MagicMock())
    sys.modules["qgis.PyQt.QtCore"].QObject = object
    sys.modules["qgis.PyQt.QtCore"].QTimer = MagicMock()

    # Remove sip so base_controller falls through to the type(QObject) fallback,
    # then mock sip.wrappertype as ABCMeta which is compatible
    if "sip" in sys.modules:
        del sys.modules["sip"]

    # Create a fake BaseController that avoids the metaclass problem
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

    # Install the fake BaseController into the base_controller module
    base_mod = types.ModuleType("filter_mate.ui.controllers.base_controller")
    base_mod.__package__ = "filter_mate.ui.controllers"
    base_mod.BaseController = FakeBaseController
    base_mod.QObjectABCMeta = type  # Plain type
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

    # Mock signal_utils with a SignalBlocker
    sb_mod = sys.modules.get("filter_mate.infrastructure.signal_utils")
    if isinstance(sb_mod, MagicMock):
        sb_mod.SignalBlocker = MagicMock


_ensure_filtering_mocks()

# Load filtering_controller
_fc_path = _project_root / "ui" / "controllers" / "filtering_controller.py"
_fc_mod_name = "filter_mate.ui.controllers.filtering_controller"
if _fc_mod_name in sys.modules:
    del sys.modules[_fc_mod_name]

_fc_spec = importlib.util.spec_from_file_location(_fc_mod_name, str(_fc_path))
_fc_mod = importlib.util.module_from_spec(_fc_spec)
_fc_mod.__package__ = "filter_mate.ui.controllers"
sys.modules[_fc_mod_name] = _fc_mod
_fc_spec.loader.exec_module(_fc_mod)

PredicateType = _fc_mod.PredicateType
BufferType = _fc_mod.BufferType
CombineOperator = _fc_mod.CombineOperator
FilterConfiguration = _fc_mod.FilterConfiguration
FilterResult = _fc_mod.FilterResult
FilteringController = _fc_mod.FilteringController


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_dockwidget():
    dw = MagicMock()
    dw.PROJECT_LAYERS = {}
    dw.widgets_initialized = True
    dw.current_layer = None
    dw.has_loaded_layers = False
    return dw


@pytest.fixture
def controller(mock_dockwidget):
    return FilteringController(
        dockwidget=mock_dockwidget,
        filter_service=None,
        signal_manager=None,
    )


# ===========================================================================
# Tests -- PredicateType enum
# ===========================================================================

class TestPredicateType:
    def test_all_predicates_defined(self):
        expected = [
            "intersects", "contains", "within", "touches",
            "crosses", "overlaps", "disjoint", "equals", "bbox",
        ]
        for val in expected:
            assert PredicateType(val) is not None

    def test_default_is_intersects(self, controller):
        assert controller.get_predicate() == PredicateType.INTERSECTS


# ===========================================================================
# Tests -- BufferType enum
# ===========================================================================

class TestBufferType:
    def test_all_types_defined(self):
        expected = ["none", "source", "target", "both"]
        for val in expected:
            assert BufferType(val) is not None


# ===========================================================================
# Tests -- CombineOperator enum
# ===========================================================================

class TestCombineOperator:
    def test_from_index_and(self):
        assert CombineOperator.from_index(0) == CombineOperator.AND

    def test_from_index_and_not(self):
        assert CombineOperator.from_index(1) == CombineOperator.AND_NOT

    def test_from_index_or(self):
        assert CombineOperator.from_index(2) == CombineOperator.OR

    def test_from_index_invalid_defaults_and(self):
        assert CombineOperator.from_index(999) == CombineOperator.AND

    def test_to_index_round_trip(self):
        for op in CombineOperator:
            assert CombineOperator.from_index(op.to_index()) == op

    def test_from_string_english(self):
        assert CombineOperator.from_string("AND") == CombineOperator.AND
        assert CombineOperator.from_string("AND NOT") == CombineOperator.AND_NOT
        assert CombineOperator.from_string("OR") == CombineOperator.OR

    def test_from_string_french(self):
        assert CombineOperator.from_string("ET") == CombineOperator.AND
        assert CombineOperator.from_string("ET NON") == CombineOperator.AND_NOT
        assert CombineOperator.from_string("OU") == CombineOperator.OR

    def test_from_string_german(self):
        assert CombineOperator.from_string("UND") == CombineOperator.AND
        assert CombineOperator.from_string("UND NICHT") == CombineOperator.AND_NOT
        assert CombineOperator.from_string("ODER") == CombineOperator.OR

    def test_from_string_empty_defaults_and(self):
        assert CombineOperator.from_string("") == CombineOperator.AND
        assert CombineOperator.from_string(None) == CombineOperator.AND

    def test_from_string_case_insensitive(self):
        assert CombineOperator.from_string("and") == CombineOperator.AND
        assert CombineOperator.from_string("or") == CombineOperator.OR


# ===========================================================================
# Tests -- FilterConfiguration
# ===========================================================================

class TestFilterConfiguration:
    def test_defaults(self):
        config = FilterConfiguration()
        assert config.source_layer_id is None
        assert config.target_layer_ids == []
        assert config.predicate == PredicateType.INTERSECTS
        assert config.buffer_value == 0.0
        assert config.buffer_type == BufferType.NONE
        assert config.expression == ""

    def test_is_valid_with_source_and_targets(self):
        config = FilterConfiguration(
            source_layer_id="layer_1",
            target_layer_ids=["layer_2", "layer_3"],
        )
        assert config.is_valid() is True

    def test_is_invalid_without_source(self):
        config = FilterConfiguration(target_layer_ids=["layer_2"])
        assert config.is_valid() is False

    def test_is_invalid_without_targets(self):
        config = FilterConfiguration(source_layer_id="layer_1")
        assert config.is_valid() is False

    def test_to_dict(self):
        config = FilterConfiguration(
            source_layer_id="src",
            target_layer_ids=["tgt"],
            predicate=PredicateType.WITHIN,
            buffer_value=100.0,
        )
        d = config.to_dict()
        assert d["source_layer_id"] == "src"
        assert d["target_layer_ids"] == ["tgt"]
        assert d["predicate"] == "within"
        assert d["buffer_value"] == 100.0

    def test_from_dict_round_trip(self):
        original = FilterConfiguration(
            source_layer_id="src",
            target_layer_ids=["t1", "t2"],
            predicate=PredicateType.CONTAINS,
            buffer_value=50.0,
            buffer_type=BufferType.SOURCE,
            expression="test_expr",
        )
        restored = FilterConfiguration.from_dict(original.to_dict())
        assert restored.source_layer_id == original.source_layer_id
        assert restored.target_layer_ids == original.target_layer_ids
        assert restored.predicate == original.predicate
        assert restored.buffer_value == original.buffer_value
        assert restored.buffer_type == original.buffer_type

    def test_from_dict_defaults_for_missing_keys(self):
        config = FilterConfiguration.from_dict({})
        assert config.source_layer_id is None
        assert config.predicate == PredicateType.INTERSECTS


# ===========================================================================
# Tests -- FilterResult
# ===========================================================================

class TestFilterResult:
    def test_defaults(self):
        r = FilterResult(success=True)
        assert r.success is True
        assert r.affected_features == 0
        assert r.error_message == ""
        assert r.execution_time_ms == 0.0

    def test_error_result(self):
        r = FilterResult(success=False, error_message="Layer not found")
        assert r.success is False
        assert r.error_message == "Layer not found"


# ===========================================================================
# Tests -- FilteringController initialization
# ===========================================================================

class TestFilteringControllerInit:
    def test_default_state(self, controller):
        assert controller.get_source_layer() is None
        assert controller.get_target_layers() == []
        assert controller.get_predicate() == PredicateType.INTERSECTS
        assert controller.get_buffer_value() == 0.0
        assert controller.get_buffer_type() == BufferType.NONE
        assert controller.get_expression() == ""

    def test_is_executing_false_by_default(self, controller):
        assert controller._is_executing is False

    def test_undo_stacks_empty(self, controller):
        assert len(controller._undo_stack) == 0
        assert len(controller._redo_stack) == 0


# ===========================================================================
# Tests -- FilteringController source/target management
# ===========================================================================

class TestSourceTargetManagement:
    def test_set_source_layer(self, controller):
        layer = MagicMock()
        layer.id.return_value = "layer_1"
        controller.set_source_layer(layer)
        assert controller.get_source_layer() is layer

    def test_set_source_layer_clears_targets(self, controller):
        layer1 = MagicMock()
        layer1.id.return_value = "l1"
        layer1.__eq__ = lambda self, other: False
        controller._target_layer_ids = ["t1", "t2"]
        controller.set_source_layer(layer1)
        assert controller.get_target_layers() == []

    def test_set_same_source_is_noop(self, controller):
        layer = MagicMock()
        controller._source_layer = layer
        controller._target_layer_ids = ["t1"]
        controller.set_source_layer(layer)
        # Targets should NOT be cleared since source didn't change
        assert controller.get_target_layers() == ["t1"]

    def test_add_target_layer(self, controller):
        controller.add_target_layer("t1")
        controller.add_target_layer("t2")
        assert controller.get_target_layers() == ["t1", "t2"]

    def test_add_duplicate_target_ignored(self, controller):
        controller.add_target_layer("t1")
        controller.add_target_layer("t1")
        assert controller.get_target_layers() == ["t1"]

    def test_remove_target_layer(self, controller):
        controller._target_layer_ids = ["t1", "t2", "t3"]
        controller.remove_target_layer("t2")
        assert "t2" not in controller.get_target_layers()

    def test_get_target_layers_returns_copy(self, controller):
        controller._target_layer_ids = ["t1"]
        targets = controller.get_target_layers()
        targets.append("t2")
        # Original should not be modified
        assert controller.get_target_layers() == ["t1"]


# ===========================================================================
# Tests -- FilteringController predicate/buffer
# ===========================================================================

class TestPredicateBufferManagement:
    def test_set_predicate(self, controller):
        controller.set_predicate(PredicateType.WITHIN)
        assert controller.get_predicate() == PredicateType.WITHIN

    def test_set_same_predicate_is_noop(self, controller):
        controller._on_config_changed_callbacks = [MagicMock()]
        controller.set_predicate(PredicateType.INTERSECTS)  # Same as default
        # Callback should NOT have been called
        controller._on_config_changed_callbacks[0].assert_not_called()

    def test_on_predicate_changed_valid(self, controller):
        controller.on_predicate_changed("within")
        assert controller.get_predicate() == PredicateType.WITHIN

    def test_on_predicate_changed_invalid_ignored(self, controller):
        controller.on_predicate_changed("not_a_predicate")
        # Should remain at default
        assert controller.get_predicate() == PredicateType.INTERSECTS

    def test_set_buffer_value(self, controller):
        controller.set_buffer_value(100.0)
        assert controller.get_buffer_value() == 100.0

    def test_negative_buffer_clamped_to_zero(self, controller):
        controller.set_buffer_value(-50.0)
        assert controller.get_buffer_value() == 0.0

    def test_set_buffer_type(self, controller):
        controller.set_buffer_type(BufferType.SOURCE)
        assert controller.get_buffer_type() == BufferType.SOURCE

    def test_on_buffer_changed(self, controller):
        controller.on_buffer_changed(200.0, "target")
        assert controller._buffer_value == 200.0
        assert controller._buffer_type == BufferType.TARGET

    def test_on_buffer_changed_invalid_type_defaults_none(self, controller):
        controller.on_buffer_changed(100.0, "invalid_type")
        assert controller._buffer_type == BufferType.NONE

    def test_get_available_predicates(self, controller):
        predicates = controller.get_available_predicates()
        assert isinstance(predicates, list)
        assert len(predicates) > 0
        # The controller returns display names (strings) for UI combobox
        assert "Intersect" in predicates or PredicateType.INTERSECTS in predicates


# ===========================================================================
# Tests -- FilteringController expression building
# ===========================================================================

class TestExpressionBuilding:
    def test_empty_expression_without_source(self, controller):
        controller._target_layer_ids = ["t1"]
        controller._rebuild_expression()
        assert controller.get_expression() == ""

    def test_empty_expression_without_targets(self, controller):
        controller._source_layer = MagicMock()
        controller._rebuild_expression()
        assert controller.get_expression() == ""

    def test_builds_expression_with_source_and_target(self, controller):
        controller._source_layer = MagicMock()
        controller._target_layer_ids = ["target_1"]
        controller._current_predicate = PredicateType.INTERSECTS
        controller._rebuild_expression()
        expr = controller.get_expression()
        assert "intersects" in expr
        assert "target_1" in expr

    def test_builds_expression_with_buffer(self, controller):
        controller._source_layer = MagicMock()
        controller._target_layer_ids = ["target_1"]
        controller._buffer_value = 100.0
        controller._rebuild_expression()
        expr = controller.get_expression()
        assert "buffer" in expr
        assert "100" in expr

    def test_multiple_targets_joined_with_or(self, controller):
        controller._source_layer = MagicMock()
        controller._target_layer_ids = ["t1", "t2"]
        controller._rebuild_expression()
        assert " OR " in controller.get_expression()


# ===========================================================================
# Tests -- FilteringController can_execute / execute_filter
# ===========================================================================

class TestExecution:
    def test_cannot_execute_without_source(self, controller):
        controller._target_layer_ids = ["t1"]
        assert controller.can_execute() is False

    def test_cannot_execute_without_targets(self, controller):
        layer = MagicMock()
        layer.id.return_value = "src"
        controller._source_layer = layer
        assert controller.can_execute() is False

    def test_can_execute_with_valid_config(self, controller):
        layer = MagicMock()
        layer.id.return_value = "src"
        controller._source_layer = layer
        controller._target_layer_ids = ["t1"]
        assert controller.can_execute() is True

    def test_cannot_execute_while_executing(self, controller):
        layer = MagicMock()
        layer.id.return_value = "src"
        controller._source_layer = layer
        controller._target_layer_ids = ["t1"]
        controller._is_executing = True
        assert controller.can_execute() is False

    def test_execute_filter_returns_false_no_service(self, controller):
        layer = MagicMock()
        layer.id.return_value = "src"
        controller._source_layer = layer
        controller._target_layer_ids = ["t1"]
        # No filter_service -> delegates to legacy
        result = controller.execute_filter()
        assert result is False

    def test_execute_unfilter_returns_false_no_source(self, controller):
        assert controller.execute_unfilter() is False

    def test_execute_reset_returns_false_no_source(self, controller):
        assert controller.execute_reset_filters() is False


# ===========================================================================
# Tests -- FilteringController configuration build/apply
# ===========================================================================

class TestConfigurationBuildApply:
    def test_build_configuration(self, controller):
        layer = MagicMock()
        layer.id.return_value = "src_layer"
        controller._source_layer = layer
        controller._target_layer_ids = ["t1", "t2"]
        controller._current_predicate = PredicateType.WITHIN
        controller._buffer_value = 50.0

        config = controller.build_configuration()
        assert config.source_layer_id == "src_layer"
        assert config.target_layer_ids == ["t1", "t2"]
        assert config.predicate == PredicateType.WITHIN
        assert config.buffer_value == 50.0

    def test_apply_configuration(self, controller):
        config = FilterConfiguration(
            source_layer_id="src",
            target_layer_ids=["t1"],
            predicate=PredicateType.CONTAINS,
            buffer_value=200.0,
            buffer_type=BufferType.BOTH,
            expression="custom_expr",
        )
        controller.apply_configuration(config)
        assert controller._target_layer_ids == ["t1"]
        assert controller._current_predicate == PredicateType.CONTAINS
        assert controller._buffer_value == 200.0
        assert controller._buffer_type == BufferType.BOTH
        assert controller._current_expression == "custom_expr"
