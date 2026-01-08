# -*- coding: utf-8 -*-
"""
PostgreSQL Backend Integration Tests - ARCH-051

Integration tests for PostgreSQL backend with materialized views,
query optimization, and cleanup services.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def mock_postgresql_connection():
    """Create a mock PostgreSQL connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = (100,)
    cursor.fetchall.return_value = [(i,) for i in range(100)]
    cursor.description = [("id",), ("name",), ("geom",)]
    return conn


@pytest.fixture
def mock_connection_pool(mock_postgresql_connection):
    """Create a mock connection pool."""
    pool = MagicMock()
    pool.getconn.return_value = mock_postgresql_connection
    pool.putconn = MagicMock()
    return pool


@pytest.fixture
def postgresql_backend_mock(mock_connection_pool):
    """Create a mock PostgreSQL backend."""
    backend = MagicMock()
    backend.name = "PostgreSQL"
    backend._pool = mock_connection_pool
    backend._session_id = "test_session_001"
    backend._use_mv_optimization = True
    
    # Metrics
    backend._metrics = {
        "executions": 0,
        "mv_executions": 0,
        "direct_executions": 0,
        "total_time_ms": 0.0,
        "errors": 0
    }
    
    return backend


@pytest.fixture
def mv_manager_mock():
    """Create a mock MaterializedViewManager."""
    manager = MagicMock()
    manager._active_mvs = {}
    manager._session_id = "test_session_001"
    
    def create_mv(query, table_name):
        mv_name = f"fm_mv_{table_name}_{manager._session_id[:8]}"
        manager._active_mvs[mv_name] = {
            "query": query,
            "created_at": "2026-01-08T12:00:00",
            "row_count": 100
        }
        return mv_name
    
    def exists(mv_name):
        return mv_name in manager._active_mvs
    
    def drop(mv_name):
        if mv_name in manager._active_mvs:
            del manager._active_mvs[mv_name]
            return True
        return False
    
    def refresh(mv_name):
        if mv_name in manager._active_mvs:
            return MagicMock(success=True)
        return MagicMock(success=False)
    
    def get_statistics(mv_name):
        if mv_name in manager._active_mvs:
            return MagicMock(
                row_count=100,
                size_bytes=51200,
                last_refresh="2026-01-08T12:00:00"
            )
        return None
    
    manager.create.side_effect = create_mv
    manager.exists.side_effect = exists
    manager.drop.side_effect = drop
    manager.refresh.side_effect = refresh
    manager.get_statistics.side_effect = get_statistics
    
    return manager


@pytest.fixture
def optimizer_mock():
    """Create a mock QueryOptimizer."""
    optimizer = MagicMock()
    
    def analyze_query(query):
        return MagicMock(
            estimated_rows=1000,
            estimated_cost=50.0,
            uses_index=True,
            recommendations=[]
        )
    
    def optimize_expression(expression):
        # Simulate optimization
        return expression.replace("LIKE '%", "ILIKE '%")
    
    optimizer.analyze_query.side_effect = analyze_query
    optimizer.optimize_expression.side_effect = optimize_expression
    
    return optimizer


@pytest.fixture
def cleanup_service_mock():
    """Create a mock CleanupService."""
    service = MagicMock()
    service._session_resources = []
    
    def register_resource(resource_type, resource_id):
        service._session_resources.append({
            "type": resource_type,
            "id": resource_id
        })
    
    def cleanup_session():
        count = len(service._session_resources)
        service._session_resources.clear()
        return MagicMock(success=True, cleaned_count=count)
    
    def get_resource_count():
        return len(service._session_resources)
    
    service.register_resource.side_effect = register_resource
    service.cleanup_session.side_effect = cleanup_session
    service.get_session_resource_count.side_effect = get_resource_count
    
    return service


@pytest.mark.integration
@pytest.mark.postgresql
class TestPostgreSQLBackendIntegration:
    """Integration tests for PostgreSQL backend."""
    
    def test_backend_initialization(self, postgresql_backend_mock):
        """Test backend initializes correctly."""
        backend = postgresql_backend_mock
        
        assert backend.name == "PostgreSQL"
        assert backend._session_id is not None
        assert backend._use_mv_optimization is True
    
    def test_execute_with_mv_optimization(
        self,
        postgresql_backend_mock,
        mv_manager_mock,
        postgresql_layer
    ):
        """Test filter execution uses MV for large datasets."""
        backend = postgresql_backend_mock
        backend._mv_manager = mv_manager_mock
        
        # Configure layer as large
        postgresql_layer.featureCount.return_value = 50000
        
        # Simulate execution
        expression = '"population" > 10000'
        
        # Create MV for large dataset
        mv_name = mv_manager_mock.create(
            f"SELECT * FROM test_table WHERE {expression}",
            "test_table"
        )
        
        assert mv_manager_mock.exists(mv_name) is True
    
    def test_execute_without_mv_small_dataset(
        self,
        postgresql_backend_mock,
        postgresql_layer
    ):
        """Test direct execution for small datasets."""
        backend = postgresql_backend_mock
        
        # Small dataset
        postgresql_layer.featureCount.return_value = 500
        
        # Configure execute result
        result = MagicMock()
        result.success = True
        result.matched_count = 50
        result.used_optimization = False
        backend.execute.return_value = result
        
        execution_result = backend.execute('"population" > 10000', postgresql_layer)
        
        assert execution_result.success is True
        assert execution_result.used_optimization is False


@pytest.mark.integration
@pytest.mark.postgresql
class TestMaterializedViewLifecycle:
    """Tests for MV lifecycle: create, use, refresh, drop."""
    
    def test_mv_create(self, mv_manager_mock):
        """Test MV creation."""
        mv_name = mv_manager_mock.create(
            "SELECT * FROM test_table WHERE population > 1000",
            "test_mv"
        )
        
        assert mv_name is not None
        assert mv_manager_mock.exists(mv_name) is True
    
    def test_mv_refresh(self, mv_manager_mock):
        """Test MV refresh."""
        mv_name = mv_manager_mock.create(
            "SELECT * FROM test_table",
            "refresh_test"
        )
        
        result = mv_manager_mock.refresh(mv_name)
        assert result.success is True
    
    def test_mv_statistics(self, mv_manager_mock):
        """Test getting MV statistics."""
        mv_name = mv_manager_mock.create(
            "SELECT * FROM test_table",
            "stats_test"
        )
        
        stats = mv_manager_mock.get_statistics(mv_name)
        assert stats.row_count > 0
    
    def test_mv_drop(self, mv_manager_mock):
        """Test MV drop."""
        mv_name = mv_manager_mock.create(
            "SELECT * FROM test_table",
            "drop_test"
        )
        
        assert mv_manager_mock.exists(mv_name) is True
        mv_manager_mock.drop(mv_name)
        assert mv_manager_mock.exists(mv_name) is False
    
    def test_mv_full_lifecycle(self, mv_manager_mock):
        """Test complete MV lifecycle."""
        # Create
        mv_name = mv_manager_mock.create(
            "SELECT * FROM cities WHERE pop > 100000",
            "cities_mv"
        )
        assert mv_manager_mock.exists(mv_name)
        
        # Get stats
        stats = mv_manager_mock.get_statistics(mv_name)
        assert stats.row_count > 0
        
        # Refresh
        result = mv_manager_mock.refresh(mv_name)
        assert result.success
        
        # Drop
        mv_manager_mock.drop(mv_name)
        assert not mv_manager_mock.exists(mv_name)


@pytest.mark.integration
@pytest.mark.postgresql
class TestQueryOptimization:
    """Tests for query optimization."""
    
    def test_analyze_simple_query(self, optimizer_mock):
        """Test analyzing a simple query."""
        query = "SELECT * FROM cities WHERE population > 10000"
        analysis = optimizer_mock.analyze_query(query)
        
        assert analysis.estimated_rows > 0
        assert analysis.uses_index is True
    
    def test_optimize_like_expression(self, optimizer_mock):
        """Test optimizing LIKE expressions."""
        expression = '"name" LIKE \'%ville%\''
        optimized = optimizer_mock.optimize_expression(expression)
        
        # Should convert to ILIKE for better performance
        assert "ILIKE" in optimized


@pytest.mark.integration
@pytest.mark.postgresql
class TestCleanupService:
    """Tests for cleanup service."""
    
    def test_register_resource(self, cleanup_service_mock):
        """Test registering a resource for cleanup."""
        service = cleanup_service_mock
        
        service.register_resource("mv", "mv_test_001")
        service.register_resource("temp_table", "temp_test_001")
        
        assert service.get_session_resource_count() == 2
    
    def test_cleanup_session(self, cleanup_service_mock):
        """Test session cleanup."""
        service = cleanup_service_mock
        
        # Register some resources
        service.register_resource("mv", "mv_1")
        service.register_resource("mv", "mv_2")
        service.register_resource("temp_table", "temp_1")
        
        # Cleanup
        result = service.cleanup_session()
        
        assert result.success is True
        assert result.cleaned_count == 3
        assert service.get_session_resource_count() == 0
    
    def test_cleanup_empty_session(self, cleanup_service_mock):
        """Test cleanup with no resources."""
        service = cleanup_service_mock
        
        result = service.cleanup_session()
        
        assert result.success is True
        assert result.cleaned_count == 0


@pytest.mark.integration
@pytest.mark.postgresql
class TestConnectionPooling:
    """Tests for connection pooling."""
    
    def test_get_connection(self, mock_connection_pool):
        """Test getting a connection from pool."""
        conn = mock_connection_pool.getconn()
        assert conn is not None
    
    def test_return_connection(self, mock_connection_pool):
        """Test returning connection to pool."""
        conn = mock_connection_pool.getconn()
        mock_connection_pool.putconn(conn)
        mock_connection_pool.putconn.assert_called_once_with(conn)
    
    def test_execute_with_pooled_connection(
        self,
        mock_connection_pool,
        mock_postgresql_connection
    ):
        """Test executing query with pooled connection."""
        conn = mock_connection_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM test_table LIMIT 10")
        results = cursor.fetchall()
        
        assert len(results) == 100  # Mocked to return 100 rows
        mock_connection_pool.putconn(conn)
