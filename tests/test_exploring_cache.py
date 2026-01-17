"""
Tests for Exploring Features Cache
Phase 2 (v4.1.0-beta.2): Unit tests for exploring features caching.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from infrastructure.cache.exploring_cache import ExploringFeaturesCache


@pytest.fixture
def cache():
    """Create fresh cache for each test with 60s TTL."""
    return ExploringFeaturesCache(max_layers=50, max_age_seconds=60.0)


@pytest.fixture
def mock_features():
    """Create mock feature list."""
    features = []
    for i in range(10):
        feature = Mock()
        feature.id.return_value = i
        feature.attribute.return_value = f"value_{i}"
        features.append(feature)
    return features


class TestCacheBasicOperations:
    """Test basic cache get/put/invalidate operations."""
    
    def test_put_and_get(self, cache, mock_features):
        """Test storing and retrieving features."""
        layer_id = "layer_123"
        groupbox_type = "by_attribute"
        expression = '"status" = 1'
        
        # Put features in cache
        cache.put(layer_id, groupbox_type, mock_features, expression)
        
        # Get features from cache
        result = cache.get(layer_id, groupbox_type)
        
        assert result is not None
        assert result['features'] == mock_features
        assert result['expression'] == expression
        assert 'timestamp' in result
    
    def test_get_nonexistent(self, cache):
        """Test getting non-existent entry returns None."""
        result = cache.get("layer_nonexistent", "by_attribute")
        assert result is None
    
    def test_put_overwrites_existing(self, cache, mock_features):
        """Test that put overwrites existing entry."""
        layer_id = "layer_123"
        groupbox_type = "by_attribute"
        
        # First put
        cache.put(layer_id, groupbox_type, mock_features[:5], "expr1")
        
        # Second put (overwrite)
        cache.put(layer_id, groupbox_type, mock_features, "expr2")
        
        result = cache.get(layer_id, groupbox_type)
        assert len(result['features']) == 10
        assert result['expression'] == "expr2"


class TestCacheInvalidation:
    """Test cache invalidation mechanisms."""
    
    def test_invalidate_specific_entry(self, cache, mock_features):
        """Test invalidating specific layer/groupbox entry."""
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        cache.put("layer_1", "by_spatial", mock_features, "expr2")
        cache.put("layer_2", "by_attribute", mock_features, "expr3")
        
        # Invalidate specific entry
        cache.invalidate("layer_1", "by_attribute")
        
        # Should be gone
        assert cache.get("layer_1", "by_attribute") is None
        
        # Others should remain
        assert cache.get("layer_1", "by_spatial") is not None
        assert cache.get("layer_2", "by_attribute") is not None
    
    def test_invalidate_layer(self, cache, mock_features):
        """Test invalidating all entries for a layer."""
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        cache.put("layer_1", "by_spatial", mock_features, "expr2")
        cache.put("layer_2", "by_attribute", mock_features, "expr3")
        
        # Invalidate entire layer
        cache.invalidate_layer("layer_1")
        
        # Layer 1 should be gone
        assert cache.get("layer_1", "by_attribute") is None
        assert cache.get("layer_1", "by_spatial") is None
        
        # Layer 2 should remain
        assert cache.get("layer_2", "by_attribute") is not None
    
    def test_invalidate_all(self, cache, mock_features):
        """Test clearing entire cache."""
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        cache.put("layer_2", "by_spatial", mock_features, "expr2")
        cache.put("layer_3", "by_custom", mock_features, "expr3")
        
        # Clear all
        cache.invalidate_all()
        
        # Everything should be gone
        assert cache.get("layer_1", "by_attribute") is None
        assert cache.get("layer_2", "by_spatial") is None
        assert cache.get("layer_3", "by_custom") is None


class TestCacheTTL:
    """Test Time-To-Live expiration."""
    
    def test_entry_not_expired_within_ttl(self, mock_features):
        """Test entry remains valid within TTL."""
        cache = ExploringFeaturesCache(max_layers=10, max_age_seconds=60.0)
        
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        
        # Get immediately (should work)
        result = cache.get("layer_1", "by_attribute")
        assert result is not None
    
    def test_entry_expires_after_ttl(self, mock_features):
        """Test entry expires after TTL."""
        # Very short TTL for testing
        cache = ExploringFeaturesCache(max_layers=10, max_age_seconds=0.1)
        
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        
        # Wait for expiration
        import time
        time.sleep(0.2)
        
        # Should be expired
        result = cache.get("layer_1", "by_attribute")
        assert result is None
    
    def test_ttl_zero_disables_expiration(self, mock_features):
        """Test TTL=0 disables automatic expiration."""
        cache = ExploringFeaturesCache(max_layers=10, max_age_seconds=0.0)
        
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        
        # Wait a bit
        import time
        time.sleep(0.1)
        
        # Should still be valid (TTL disabled)
        result = cache.get("layer_1", "by_attribute")
        assert result is not None


class TestCacheStatistics:
    """Test cache statistics tracking."""
    
    def test_stats_after_operations(self, cache, mock_features):
        """Test statistics after various operations."""
        # Initial stats
        stats = cache.get_stats()
        assert stats['entries'] == 0
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        
        # Add entries
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        cache.put("layer_2", "by_spatial", mock_features, "expr2")
        
        stats = cache.get_stats()
        assert stats['entries'] == 2
        
        # Cache hit
        cache.get("layer_1", "by_attribute")
        stats = cache.get_stats()
        assert stats['hits'] == 1
        
        # Cache miss
        cache.get("layer_nonexistent", "by_attribute")
        stats = cache.get_stats()
        assert stats['misses'] == 1
    
    def test_hit_rate_calculation(self, cache, mock_features):
        """Test hit rate calculation."""
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        
        # 2 hits
        cache.get("layer_1", "by_attribute")
        cache.get("layer_1", "by_attribute")
        
        # 1 miss
        cache.get("layer_2", "by_attribute")
        
        stats = cache.get_stats()
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert abs(stats['hit_rate'] - 0.666) < 0.01  # ~66.6%


class TestCacheCapacity:
    """Test cache capacity limits."""
    
    def test_max_layers_limit(self, mock_features):
        """Test cache respects max_layers limit."""
        cache = ExploringFeaturesCache(max_layers=3, max_age_seconds=300.0)
        
        # Add 5 layers (exceeds max of 3)
        for i in range(5):
            cache.put(f"layer_{i}", "by_attribute", mock_features, f"expr_{i}")
        
        stats = cache.get_stats()
        # Should have evicted oldest entries to stay at max_layers
        assert stats['entries'] <= 3
    
    def test_lru_eviction(self, mock_features):
        """Test LRU eviction when capacity exceeded."""
        cache = ExploringFeaturesCache(max_layers=3, max_age_seconds=300.0)
        
        # Add 3 entries
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        cache.put("layer_2", "by_attribute", mock_features, "expr2")
        cache.put("layer_3", "by_attribute", mock_features, "expr3")
        
        # Access layer_1 (make it most recent)
        cache.get("layer_1", "by_attribute")
        
        # Add layer_4 (should evict layer_2, the least recently used)
        cache.put("layer_4", "by_attribute", mock_features, "expr4")
        
        # Layer_2 should be evicted
        assert cache.get("layer_2", "by_attribute") is None
        
        # Others should remain
        assert cache.get("layer_1", "by_attribute") is not None
        assert cache.get("layer_3", "by_attribute") is not None
        assert cache.get("layer_4", "by_attribute") is not None


class TestCacheMemoryEstimation:
    """Test cache memory usage estimation."""
    
    def test_size_estimation(self, cache, mock_features):
        """Test cache size estimation."""
        # Empty cache
        size_empty = cache.estimate_size_bytes()
        assert size_empty >= 0
        
        # Add entries
        cache.put("layer_1", "by_attribute", mock_features, "expr1")
        cache.put("layer_2", "by_spatial", mock_features, "expr2")
        
        size_with_data = cache.estimate_size_bytes()
        
        # Should be larger with data
        assert size_with_data > size_empty


class TestMultipleGroupboxTypes:
    """Test caching multiple groupbox types for same layer."""
    
    def test_different_groupbox_types_independent(self, cache, mock_features):
        """Test different groupbox types are cached independently."""
        layer_id = "layer_1"
        
        # Cache different groupbox types
        cache.put(layer_id, "by_attribute", mock_features[:5], "expr_attr")
        cache.put(layer_id, "by_spatial", mock_features[5:], "expr_spatial")
        cache.put(layer_id, "by_custom", mock_features, "expr_custom")
        
        # Each should be retrievable independently
        result_attr = cache.get(layer_id, "by_attribute")
        result_spatial = cache.get(layer_id, "by_spatial")
        result_custom = cache.get(layer_id, "by_custom")
        
        assert len(result_attr['features']) == 5
        assert len(result_spatial['features']) == 5
        assert len(result_custom['features']) == 10
        
        assert result_attr['expression'] == "expr_attr"
        assert result_spatial['expression'] == "expr_spatial"
        assert result_custom['expression'] == "expr_custom"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_features_list(self, cache):
        """Test caching empty features list."""
        cache.put("layer_1", "by_attribute", [], "expr1")
        
        result = cache.get("layer_1", "by_attribute")
        assert result is not None
        assert result['features'] == []
    
    def test_empty_expression(self, cache, mock_features):
        """Test caching with empty expression."""
        cache.put("layer_1", "by_attribute", mock_features, "")
        
        result = cache.get("layer_1", "by_attribute")
        assert result is not None
        assert result['expression'] == ""
    
    def test_none_values_handled(self, cache):
        """Test None values don't break cache."""
        # Should not crash
        result = cache.get(None, "by_attribute")
        assert result is None
        
        result = cache.get("layer_1", None)
        assert result is None
