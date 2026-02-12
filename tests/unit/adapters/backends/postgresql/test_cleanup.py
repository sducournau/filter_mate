# -*- coding: utf-8 -*-
"""
Unit tests for PostgreSQL Cleanup Service.

Tests the PostgreSQLCleanupService class for:
- Initialization and properties
- Session view cleanup
- Orphaned view cleanup
- Schema management (ensure_schema_exists, cleanup_schema_if_empty)
- Circuit breaker integration
- Metrics tracking
- Error handling

All database operations are mocked.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock setup
# ---------------------------------------------------------------------------

def _ensure_cleanup_mocks():
    ROOT = "filter_mate"
    if ROOT not in sys.modules:
        fm = types.ModuleType(ROOT)
        fm.__path__ = []
        fm.__package__ = ROOT
        sys.modules[ROOT] = fm

    mocks = {
        f"{ROOT}.infrastructure": MagicMock(),
        f"{ROOT}.infrastructure.database": MagicMock(),
        f"{ROOT}.infrastructure.database.sql_utils": MagicMock(),
        f"{ROOT}.infrastructure.resilience": MagicMock(),
    }
    mocks[f"{ROOT}.infrastructure.database.sql_utils"].sanitize_sql_identifier = lambda x: x

    for name, mock_obj in mocks.items():
        if name not in sys.modules:
            sys.modules[name] = mock_obj


_ensure_cleanup_mocks()

import importlib.util
import os

_cleanup_path = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "adapters", "backends", "postgresql", "cleanup.py"
))

_spec = importlib.util.spec_from_file_location(
    "filter_mate.adapters.backends.postgresql.cleanup",
    _cleanup_path,
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "filter_mate.adapters.backends.postgresql"
sys.modules[_mod.__name__] = _mod
_spec.loader.exec_module(_mod)

PostgreSQLCleanupService = _mod.PostgreSQLCleanupService


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def service():
    """Create a cleanup service with default settings."""
    return PostgreSQLCleanupService(
        session_id="abc12345",
        schema="filtermate_temp",
    )


@pytest.fixture
def mock_connexion():
    conn = MagicMock()
    conn.closed = False
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def mock_cursor(mock_connexion):
    return mock_connexion.cursor.return_value


# ===========================================================================
# Tests -- Initialization
# ===========================================================================

class TestInit:
    def test_default_values(self, service):
        assert service.session_id == "abc12345"
        assert service.schema == "filtermate_temp"
        assert service.metrics["views_cleaned"] == 0
        assert service.metrics["errors"] == 0

    def test_session_id_setter(self, service):
        service.session_id = "new_session"
        assert service.session_id == "new_session"

    def test_default_schema(self):
        s = PostgreSQLCleanupService()
        assert s.schema == "filtermate_temp"

    def test_metrics_returns_copy(self, service):
        m1 = service.metrics
        m2 = service.metrics
        assert m1 is not m2  # Different objects
        assert m1 == m2      # Same values


# ===========================================================================
# Tests -- Circuit Breaker
# ===========================================================================

class TestCircuitBreaker:
    def test_proceeds_when_no_breaker(self, service):
        assert service._check_circuit_breaker() is True

    def test_blocks_when_breaker_open(self):
        breaker = MagicMock()
        breaker.is_open = True
        s = PostgreSQLCleanupService(
            session_id="test",
            circuit_breaker=breaker,
        )
        assert s._check_circuit_breaker() is False

    def test_proceeds_when_breaker_closed(self):
        breaker = MagicMock()
        breaker.is_open = False
        s = PostgreSQLCleanupService(
            session_id="test",
            circuit_breaker=breaker,
        )
        assert s._check_circuit_breaker() is True

    def test_record_success_calls_breaker(self):
        breaker = MagicMock()
        s = PostgreSQLCleanupService(session_id="t", circuit_breaker=breaker)
        s._record_success()
        breaker.record_success.assert_called_once()

    def test_record_failure_increments_errors(self):
        breaker = MagicMock()
        s = PostgreSQLCleanupService(session_id="t", circuit_breaker=breaker)
        s._record_failure()
        breaker.record_failure.assert_called_once()
        assert s._metrics["errors"] == 1


# ===========================================================================
# Tests -- cleanup_session_views
# ===========================================================================

class TestCleanupSessionViews:
    def test_raises_without_session_id(self):
        s = PostgreSQLCleanupService()
        conn = MagicMock()
        with pytest.raises(ValueError, match="session_id"):
            s.cleanup_session_views(conn)

    def test_uses_instance_session_id(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchall.return_value = []
        count, views = service.cleanup_session_views(mock_connexion)
        assert count == 0
        assert views == []

    def test_drops_matching_views(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchall.return_value = [
            ("fm_temp_mv_abc12345_layer1",),
            ("fm_temp_mv_abc12345_layer2",),
        ]
        count, views = service.cleanup_session_views(mock_connexion)
        assert count == 2
        assert len(views) == 2
        assert service.metrics["views_cleaned"] >= 2

    def test_custom_session_id_override(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchall.return_value = [("fm_temp_mv_xyz_layer1",)]
        count, views = service.cleanup_session_views(mock_connexion, session_id="xyz")
        assert count == 1

    def test_skipped_when_circuit_open(self):
        breaker = MagicMock()
        breaker.is_open = True
        s = PostgreSQLCleanupService(session_id="test", circuit_breaker=breaker)
        conn = MagicMock()
        count, views = s.cleanup_session_views(conn)
        assert count == 0
        # Connection should not have been used
        conn.cursor.assert_not_called()


# ===========================================================================
# Tests -- ensure_schema_exists
# ===========================================================================

class TestEnsureSchemaExists:
    def test_creates_schema(self, service, mock_connexion, mock_cursor):
        result = service.ensure_schema_exists(mock_connexion)
        assert result is True
        mock_connexion.commit.assert_called()

    def test_returns_false_on_error(self, service, mock_connexion, mock_cursor):
        mock_cursor.execute.side_effect = Exception("permission denied")
        result = service.ensure_schema_exists(mock_connexion)
        assert result is False

    def test_skipped_when_circuit_open(self):
        breaker = MagicMock()
        breaker.is_open = True
        s = PostgreSQLCleanupService(session_id="test", circuit_breaker=breaker)
        result = s.ensure_schema_exists(MagicMock())
        assert result is False


# ===========================================================================
# Tests -- cleanup_schema_if_empty
# ===========================================================================

class TestCleanupSchemaIfEmpty:
    def test_returns_false_if_schema_does_not_exist(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchone.return_value = (0,)
        result = service.cleanup_schema_if_empty(mock_connexion)
        assert result is False

    def test_drops_empty_schema(self, service, mock_connexion, mock_cursor):
        # Schema exists
        mock_cursor.fetchone.return_value = (1,)
        # No views
        mock_cursor.fetchall.return_value = []
        result = service.cleanup_schema_if_empty(mock_connexion)
        assert result is True

    def test_preserves_schema_with_other_sessions_views(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchone.return_value = (1,)
        # Views from another session
        mock_cursor.fetchall.return_value = [("fm_temp_mv_othersess_layer1",)]
        result = service.cleanup_schema_if_empty(mock_connexion)
        assert result is False

    def test_force_drops_even_with_views(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [("fm_temp_mv_othersess_layer1",)]
        result = service.cleanup_schema_if_empty(mock_connexion, force=True)
        assert result is True


# ===========================================================================
# Tests -- get_session_view_count
# ===========================================================================

class TestGetSessionViewCount:
    def test_returns_count(self, service, mock_connexion, mock_cursor):
        mock_cursor.fetchone.return_value = (5,)
        count = service.get_session_view_count(mock_connexion)
        assert count == 5

    def test_returns_zero_without_session_id(self, mock_connexion):
        s = PostgreSQLCleanupService()
        count = s.get_session_view_count(mock_connexion)
        assert count == 0

    def test_returns_zero_on_error(self, service):
        conn = MagicMock()
        conn.cursor.side_effect = Exception("error")
        count = service.get_session_view_count(conn)
        assert count == 0
