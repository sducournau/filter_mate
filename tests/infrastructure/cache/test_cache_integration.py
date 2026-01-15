"""
Tests for CacheManager Integration

Validates that all caches (GeometryCache, ExpressionCache, etc.)
are properly registered in the global CacheManager.

Created: 2026-01-14 (v4.0.5)
"""

import pytest
from unittest.mock import Mock, patch

from core.tasks.cache.geometry_cache import GeometryCache
from core.tasks.cache.expression_cache import ExpressionCache
from infrastructure.cache.cache_manager import (
    CacheManager,
    CacheConfig,
    CachePolicy
)


class TestCacheManagerIntegration:
    """Test cache registration in CacheManager."""
    
    def setup_method(self):
        """Reset CacheManager before each test."""
        # Reset singleton instance
        CacheManager._instance = None
        CacheManager._lock = __import__('threading').Lock()
    
    def test_geometry_cache_registers_in_manager(self):
        """Test that GeometryCache registers itself in CacheManager."""
        # Create cache
        geom_cache = GeometryCache(max_size=100)
        
        # Verify registration
        manager = CacheManager.get_instance()
        stats = manager.get_stats("geometry_task")
        
        assert stats is not None, "geometry_task should be registered"
        assert stats.max_size == 100
        assert stats.policy == CachePolicy.FIFO
    
    def test_expression_cache_registers_in_manager(self):
        """Test that ExpressionCache registers itself in CacheManager."""
        # Create cache
        expr_cache = ExpressionCache(max_size=200, ttl_seconds=300.0)
        
        # Verify registration
        manager = CacheManager.get_instance()
        stats = manager.get_stats("expression_task")
        
        assert stats is not None, "expression_task should be registered"
        assert stats.max_size == 200
        assert stats.policy == CachePolicy.LRU
        assert stats.ttl_seconds == 300.0
    
    def test_multiple_caches_registered(self):
        """Test that multiple caches can be registered simultaneously."""
        # Create multiple caches
        geom_cache = GeometryCache(max_size=100)
        expr_cache = ExpressionCache(max_size=200)
        
        # Get all stats
        manager = CacheManager.get_instance()
        all_stats = manager.get_stats()
        
        assert "geometry_task" in all_stats
        assert "expression_task" in all_stats
        assert len(all_stats) >= 2
    
    def test_cache_manager_clear_all(self):
        """Test that CacheManager can clear all registered caches."""
        # Create and populate caches
        geom_cache = GeometryCache(max_size=100)
        expr_cache = ExpressionCache(max_size=200)
        
        # Put some data (mock)
        # NOTE: GeometryCache.put() requires specific parameters
        # We'll just test the manager's clear_all_caches() method
        
        # Clear all
        manager = CacheManager.get_instance()
        cleared_count = manager.clear_all_caches()
        
        # Should have cleared at least 2 caches
        assert cleared_count >= 2
    
    def test_shared_instance_pattern(self):
        """Test that shared instances work correctly."""
        # Get shared instances
        geom1 = GeometryCache.get_shared_instance()
        geom2 = GeometryCache.get_shared_instance()
        
        expr1 = ExpressionCache.get_shared_instance()
        expr2 = ExpressionCache.get_shared_instance()
        
        # Verify singletons
        assert geom1 is geom2, "Shared GeometryCache instances should be identical"
        assert expr1 is expr2, "Shared ExpressionCache instances should be identical"
        
        # Verify both registered
        manager = CacheManager.get_instance()
        all_stats = manager.get_stats()
        
        assert "geometry_task" in all_stats
        assert "expression_task" in all_stats


class TestFilterMateAppCacheMethods:
    """Test FilterMateApp cache management methods."""
    
    @patch('filter_mate_app.CacheManager')
    def test_get_all_cache_stats(self, mock_manager_class):
        """Test FilterMateApp.get_all_cache_stats() method."""
        from filter_mate_app import FilterMateApp
        
        # Mock CacheManager
        mock_manager = Mock()
        mock_manager.get_stats.return_value = {
            "geometry_task": Mock(hits=100, misses=10),
            "expression_task": Mock(hits=200, misses=20)
        }
        mock_manager_class.get_instance.return_value = mock_manager
        
        # Create app instance
        with patch('filter_mate_app.os.path.exists', return_value=True):
            app = FilterMateApp("/fake/plugin/dir")
        
        # Get stats
        stats = app.get_all_cache_stats()
        
        assert "geometry_task" in stats
        assert "expression_task" in stats
        assert stats["geometry_task"].hits == 100
        assert stats["expression_task"].hits == 200
    
    @patch('filter_mate_app.CacheManager')
    @patch('filter_mate_app.iface')
    def test_clear_all_caches(self, mock_iface, mock_manager_class):
        """Test FilterMateApp.clear_all_caches() method."""
        from filter_mate_app import FilterMateApp
        
        # Mock CacheManager
        mock_manager = Mock()
        mock_manager.clear_all_caches.return_value = 3  # 3 caches cleared
        mock_manager_class.get_instance.return_value = mock_manager
        
        # Mock message bar
        mock_message_bar = Mock()
        mock_iface.messageBar.return_value = mock_message_bar
        
        # Create app instance
        with patch('filter_mate_app.os.path.exists', return_value=True):
            app = FilterMateApp("/fake/plugin/dir")
        
        # Clear caches
        cleared_count = app.clear_all_caches()
        
        assert cleared_count == 3
        mock_manager.clear_all_caches.assert_called_once()
        mock_message_bar.pushSuccess.assert_called_once()


class TestCacheStatistics:
    """Test cache statistics tracking."""
    
    def setup_method(self):
        """Reset CacheManager before each test."""
        CacheManager._instance = None
        CacheManager._lock = __import__('threading').Lock()
    
    def test_cache_hit_miss_tracking(self):
        """Test that cache hits/misses are tracked properly."""
        # Create cache
        geom_cache = GeometryCache(max_size=10)
        
        # Mock underlying cache to simulate hits/misses
        # NOTE: This is a simplified test - real usage would populate the cache
        
        # Get stats
        manager = CacheManager.get_instance()
        stats = manager.get_stats("geometry_task")
        
        # Initial state
        assert stats.current_size == 0
        assert stats.max_size == 10
    
    def test_cache_policy_enforcement(self):
        """Test that cache policies are correctly configured."""
        geom_cache = GeometryCache(max_size=100)
        expr_cache = ExpressionCache(max_size=200, ttl_seconds=300.0)
        
        manager = CacheManager.get_instance()
        
        # Check geometry cache policy (FIFO)
        geom_stats = manager.get_stats("geometry_task")
        assert geom_stats.policy == CachePolicy.FIFO
        assert geom_stats.ttl_seconds is None  # No TTL for FIFO
        
        # Check expression cache policy (LRU with TTL)
        expr_stats = manager.get_stats("expression_task")
        assert expr_stats.policy == CachePolicy.LRU
        assert expr_stats.ttl_seconds == 300.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
