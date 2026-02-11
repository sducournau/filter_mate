# -*- coding: utf-8 -*-
"""
Unit tests for Memory Backend.

Tests the MemoryBackend class for:
- Initialization and default state
- Metrics tracking and reset
- supports_layer() for MEMORY provider
- get_info() metadata
- estimate_execution_time() calculations
- cleanup() (no-op)
- get_statistics() / reset_statistics()

Note: The execute() method requires real QGIS expression evaluation
and is tested at integration level. We focus on pure logic here.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

def _ensure_memory_mocks():
    ROOT = "filter_mate"
    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = []
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    from enum import Enum, Flag, auto
    from dataclasses import dataclass

    class FakeProviderType(Enum):
        MEMORY = "memory"
        OGR = "ogr"
        POSTGRES = "postgres"
        SPATIALITE = "spatialite"

    class FakeBackendCapability(Flag):
        SPATIAL_FILTER = auto()

    @dataclass
    class FakeBackendInfo:
        name: str = ""
        version: str = ""
        capabilities: object = None
        priority: int = 0
        max_features: int = 0
        description: str = ""

    @dataclass
    class FakeFilterExpression:
        raw: str = ""
        is_spatial: bool = False

    @dataclass
    class FakeFilterResult:
        success: bool = True
        feature_ids: list = None
        error_message: str = None

        @classmethod
        def error(cls, **kwargs):
            return cls(success=False, error_message=kwargs.get("error_message", ""))

        @classmethod
        def success_result(cls, **kwargs):
            return cls(success=True, feature_ids=kwargs.get("feature_ids", []))

    @dataclass
    class FakeLayerInfo:
        layer_id: str = ""
        feature_count: int = 0
        provider_type: object = None

    # Create a minimal BackendPort ABC
    from abc import ABC, abstractmethod

    class FakeBackendPort(ABC):
        @property
        def name(self):
            return self.__class__.__name__

        @abstractmethod
        def execute(self, expression, layer_info, target_layer_infos=None): pass

        @abstractmethod
        def supports_layer(self, layer_info): pass

        @abstractmethod
        def get_info(self): pass

        @abstractmethod
        def cleanup(self): pass

        @abstractmethod
        def estimate_execution_time(self, expression, layer_info): pass

    mocks = {
        f"{ROOT}.core": MagicMock(),
        f"{ROOT}.core.ports": MagicMock(),
        f"{ROOT}.core.ports.backend_port": MagicMock(),
        f"{ROOT}.core.domain": MagicMock(),
        f"{ROOT}.core.domain.filter_expression": MagicMock(),
        f"{ROOT}.core.domain.filter_result": MagicMock(),
        f"{ROOT}.core.domain.layer_info": MagicMock(),
        f"{ROOT}.adapters": MagicMock(),
        f"{ROOT}.adapters.backends": MagicMock(),
        f"{ROOT}.adapters.backends.memory": MagicMock(),
    }

    mocks[f"{ROOT}.core.ports.backend_port"].BackendPort = FakeBackendPort
    mocks[f"{ROOT}.core.ports.backend_port"].BackendInfo = FakeBackendInfo
    mocks[f"{ROOT}.core.ports.backend_port"].BackendCapability = FakeBackendCapability
    mocks[f"{ROOT}.core.domain.filter_expression"].FilterExpression = FakeFilterExpression
    mocks[f"{ROOT}.core.domain.filter_expression"].ProviderType = FakeProviderType
    mocks[f"{ROOT}.core.domain.filter_result"].FilterResult = FakeFilterResult
    mocks[f"{ROOT}.core.domain.layer_info"].LayerInfo = FakeLayerInfo

    for name, mock_obj in mocks.items():
        if name not in sys.modules:
            sys.modules[name] = mock_obj


_ensure_memory_mocks()

import importlib.util
import os

_backend_path = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "adapters", "backends", "memory", "backend.py"
))

_spec = importlib.util.spec_from_file_location(
    "filter_mate.adapters.backends.memory.backend",
    _backend_path,
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "filter_mate.adapters.backends.memory"
sys.modules[_mod.__name__] = _mod
_spec.loader.exec_module(_mod)

MemoryBackend = _mod.MemoryBackend
create_memory_backend = _mod.create_memory_backend

# Get the fake types for building test fixtures
FakeProviderType = sys.modules["filter_mate.core.domain.filter_expression"].ProviderType
FakeFilterExpression = sys.modules["filter_mate.core.domain.filter_expression"].FilterExpression
FakeLayerInfo = sys.modules["filter_mate.core.domain.layer_info"].LayerInfo


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def backend():
    return MemoryBackend()


# ===========================================================================
# Tests -- Initialization
# ===========================================================================

class TestInit:
    def test_default_metrics(self, backend):
        m = backend.metrics
        assert m["executions"] == 0
        assert m["features_processed"] == 0
        assert m["total_time_ms"] == 0.0
        assert m["errors"] == 0

    def test_metrics_returns_copy(self, backend):
        m1 = backend.metrics
        m2 = backend.metrics
        assert m1 is not m2
        assert m1 == m2

    def test_max_recommended_features(self, backend):
        assert backend.MAX_RECOMMENDED_FEATURES == 50000


# ===========================================================================
# Tests -- supports_layer
# ===========================================================================

class TestSupportsLayer:
    def test_supports_memory_provider(self, backend):
        layer_info = FakeLayerInfo(
            layer_id="mem_1",
            feature_count=100,
            provider_type=FakeProviderType.MEMORY,
        )
        assert backend.supports_layer(layer_info) is True

    def test_rejects_ogr_provider(self, backend):
        layer_info = FakeLayerInfo(
            layer_id="ogr_1",
            feature_count=100,
            provider_type=FakeProviderType.OGR,
        )
        assert backend.supports_layer(layer_info) is False

    def test_rejects_postgres_provider(self, backend):
        layer_info = FakeLayerInfo(
            layer_id="pg_1",
            feature_count=100,
            provider_type=FakeProviderType.POSTGRES,
        )
        assert backend.supports_layer(layer_info) is False


# ===========================================================================
# Tests -- get_info
# ===========================================================================

class TestGetInfo:
    def test_returns_backend_info(self, backend):
        info = backend.get_info()
        assert info.name == "Memory"
        assert info.version == "1.0.0"
        assert info.max_features == 50000
        assert "memory" in info.description.lower() or "In-memory" in info.description


# ===========================================================================
# Tests -- estimate_execution_time
# ===========================================================================

class TestEstimateExecutionTime:
    def test_non_spatial_estimation(self, backend):
        expr = FakeFilterExpression(raw='"id" > 10', is_spatial=False)
        layer_info = FakeLayerInfo(feature_count=1000)
        time_ms = backend.estimate_execution_time(expr, layer_info)
        # 1000 * 0.02 = 20ms
        assert time_ms == pytest.approx(20.0)

    def test_spatial_estimation_higher(self, backend):
        expr = FakeFilterExpression(raw="intersects(...)", is_spatial=True)
        layer_info = FakeLayerInfo(feature_count=1000)
        time_ms = backend.estimate_execution_time(expr, layer_info)
        # 1000 * 0.02 * 1.5 = 30ms
        assert time_ms == pytest.approx(30.0)

    def test_zero_features(self, backend):
        expr = FakeFilterExpression(raw='"id" > 10', is_spatial=False)
        layer_info = FakeLayerInfo(feature_count=0)
        time_ms = backend.estimate_execution_time(expr, layer_info)
        assert time_ms == 0.0

    def test_large_dataset_estimation(self, backend):
        expr = FakeFilterExpression(raw='"id" > 10', is_spatial=False)
        layer_info = FakeLayerInfo(feature_count=100000)
        time_ms = backend.estimate_execution_time(expr, layer_info)
        # 100000 * 0.02 = 2000ms
        assert time_ms == pytest.approx(2000.0)


# ===========================================================================
# Tests -- cleanup
# ===========================================================================

class TestCleanup:
    def test_cleanup_does_not_raise(self, backend):
        # cleanup() is a no-op but should not error
        backend.cleanup()


# ===========================================================================
# Tests -- get_statistics / reset_statistics
# ===========================================================================

class TestStatistics:
    def test_get_statistics(self, backend):
        stats = backend.get_statistics()
        assert "executions" in stats
        assert "features_processed" in stats

    def test_reset_statistics(self, backend):
        # Manually bump a metric
        backend._metrics["executions"] = 42
        backend._metrics["errors"] = 3
        backend.reset_statistics()
        assert backend._metrics["executions"] == 0
        assert backend._metrics["errors"] == 0


# ===========================================================================
# Tests -- create_memory_backend factory
# ===========================================================================

class TestFactory:
    def test_creates_instance(self):
        b = create_memory_backend()
        assert isinstance(b, MemoryBackend)
