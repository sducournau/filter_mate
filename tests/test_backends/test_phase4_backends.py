# -*- coding: utf-8 -*-
"""
Tests for Phase 4 Backend Components

Tests for refactored backend packages:
- PostgreSQL (MVManager, Optimizer)
- Spatialite (Cache, IndexManager)
- OGR Backend
- Memory Backend

ARCH-048: Phase 4 Tests
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


# =============================================================================
# PostgreSQL MVManager Tests
# =============================================================================

class TestMaterializedViewManager:
    """Tests for MVManager."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        pool = Mock()
        conn = Mock()
        cursor = Mock()
        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        return pool

    @pytest.fixture
    def mv_manager(self, mock_pool):
        """Create MVManager with mock connection pool."""
        from adapters.backends.postgresql.mv_manager import MaterializedViewManager
        return MaterializedViewManager(
            connection_pool=mock_pool,
            session_id="test-session-123"
        )

    def test_init(self, mv_manager):
        """Test MVManager initialization."""
        assert mv_manager._session_id == "test-session-123"
        assert len(mv_manager._created_mvs) == 0
        assert 'mvs_created' in mv_manager._metrics

    def test_session_id_property(self, mv_manager):
        """Test session ID property."""
        assert mv_manager.session_id == "test-session-123"

    def test_config_defaults(self, mv_manager):
        """Test default config values."""
        assert mv_manager.config.feature_threshold == 10000
        assert mv_manager.config.auto_refresh is True

    def test_metrics_initial(self, mv_manager):
        """Test initial metrics."""
        assert mv_manager._metrics['mvs_created'] == 0
        assert mv_manager._metrics['mvs_refreshed'] == 0
        assert mv_manager._metrics['mvs_dropped'] == 0

    def test_naming_conventions(self, mv_manager):
        """Test naming conventions (unified fm_temp_* prefix v4.4.3+)."""
        from adapters.backends.postgresql.mv_manager import MaterializedViewManager
        assert MaterializedViewManager.MV_PREFIX == "fm_temp_mv_"
        assert MaterializedViewManager.MV_SCHEMA == "filtermate_temp"


# =============================================================================
# PostgreSQL Optimizer Tests
# =============================================================================

class TestQueryOptimizer:
    """Tests for PostgreSQL QueryOptimizer."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        pool = Mock()
        conn = Mock()
        cursor = Mock()
        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
        return pool

    @pytest.fixture
    def optimizer(self, mock_pool):
        """Create QueryOptimizer with mock pool."""
        from adapters.backends.postgresql.optimizer import QueryOptimizer
        return QueryOptimizer(connection_pool=mock_pool)

    def test_init(self, optimizer):
        """Test QueryOptimizer initialization."""
        assert optimizer._pool is not None
        assert 'queries_analyzed' in optimizer._metrics

    def test_metrics_initial(self, optimizer):
        """Test initial metrics."""
        assert optimizer._metrics['queries_analyzed'] == 0


# =============================================================================
# Spatialite Cache Tests
# =============================================================================

class TestSpatialiteCache:
    """Tests for SpatialiteCache."""

    @pytest.fixture
    def cache(self):
        """Create SpatialiteCache."""
        from adapters.backends.spatialite.cache import SpatialiteCache
        return SpatialiteCache(max_entries=100, ttl_seconds=60)

    def test_init(self, cache):
        """Test cache initialization."""
        assert cache._max_entries == 100
        assert cache._default_ttl == timedelta(seconds=60)
        assert len(cache._result_cache) == 0

    def test_result_cache_empty(self, cache):
        """Test result cache starts empty."""
        assert len(cache._result_cache) == 0

    def test_geometry_cache_empty(self, cache):
        """Test geometry cache starts empty."""
        assert len(cache._geometry_cache) == 0

    def test_initial_metrics(self, cache):
        """Test initial metrics."""
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._evictions == 0


# =============================================================================
# Spatialite IndexManager Tests
# =============================================================================

class TestRTreeIndexManager:
    """Tests for RTreeIndexManager."""

    @pytest.fixture
    def mock_connection(self):
        """Create mock connection."""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        return conn

    @pytest.fixture
    def index_manager(self, mock_connection):
        """Create IndexManager with mock connection."""
        from adapters.backends.spatialite.index_manager import RTreeIndexManager
        return RTreeIndexManager(connection=mock_connection)

    def test_init(self, index_manager):
        """Test IndexManager initialization."""
        assert index_manager._conn is not None
        assert 'indexes_created' in index_manager._metrics

    def test_metrics_initial(self, index_manager):
        """Test initial metrics."""
        assert index_manager._metrics['indexes_created'] == 0
        assert index_manager._metrics['indexes_dropped'] == 0
        assert index_manager._metrics['indexes_rebuilt'] == 0


# =============================================================================
# OGR Backend Tests
# =============================================================================

class TestOGRBackend:
    """Tests for OGRBackend."""

    @pytest.fixture
    def backend(self):
        """Create OGRBackend."""
        from adapters.backends.ogr.backend import OGRBackend
        return OGRBackend()

    def test_init(self, backend):
        """Test backend initialization."""
        assert backend._batch_size == 1000
        assert 'executions' in backend._metrics

    def test_priority(self, backend):
        """Test backend priority."""
        assert backend.priority == 50  # Fallback

    def test_metrics_initial(self, backend):
        """Test initial metrics."""
        assert backend._metrics['executions'] == 0
        assert backend._metrics['features_processed'] == 0
        assert backend._metrics['total_time_ms'] == 0.0


# =============================================================================
# Memory Backend Tests
# =============================================================================

class TestMemoryBackend:
    """Tests for MemoryBackend."""

    @pytest.fixture
    def backend(self):
        """Create MemoryBackend."""
        from adapters.backends.memory.backend import MemoryBackend
        return MemoryBackend()

    def test_init(self, backend):
        """Test backend initialization."""
        assert backend is not None
        assert backend.name == 'Memory'

    def test_priority(self, backend):
        """Test backend priority."""
        assert backend.priority == 60  # Between OGR and Spatialite

    def test_max_features(self, backend):
        """Test max recommended features constant."""
        from adapters.backends.memory.backend import MemoryBackend
        assert MemoryBackend.MAX_RECOMMENDED_FEATURES == 50000


# =============================================================================
# PostgreSQL Backend Tests
# =============================================================================

class TestPostgreSQLBackend:
    """Tests for PostgreSQLBackend."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        pool = Mock()
        conn = Mock()
        cursor = Mock()
        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        return pool

    @pytest.fixture
    def backend(self, mock_pool):
        """Create PostgreSQLBackend with mock pool."""
        from adapters.backends.postgresql.backend import PostgreSQLBackend
        return PostgreSQLBackend(connection_pool=mock_pool)

    def test_init(self, backend):
        """Test backend initialization."""
        assert backend._pool is not None
        assert backend._mv_manager is not None
        assert backend._optimizer is not None

    def test_priority(self, backend):
        """Test backend priority."""
        assert backend.priority == 100  # Highest

    def test_metrics_initial(self, backend):
        """Test initial metrics."""
        assert 'executions' in backend._metrics


# =============================================================================
# Spatialite Backend Tests
# =============================================================================

class TestSpatialiteBackend:
    """Tests for SpatialiteBackend."""

    @pytest.fixture
    def mock_connection(self):
        """Create mock connection."""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        return conn

    @pytest.fixture
    def backend(self, mock_connection):
        """Create SpatialiteBackend with mock connection."""
        from adapters.backends.spatialite.backend import SpatialiteBackend
        return SpatialiteBackend(connection=mock_connection)

    def test_init(self, backend):
        """Test backend initialization."""
        assert backend._conn is not None
        assert backend._cache is not None
        assert backend._index_manager is not None

    def test_priority(self, backend):
        """Test backend priority."""
        assert backend.priority == 80

    def test_cache_available(self, backend):
        """Test cache is available."""
        assert backend._cache is not None

    def test_index_manager_available(self, backend):
        """Test index manager is available."""
        assert backend._index_manager is not None
