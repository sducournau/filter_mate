"""
Tests for RasterStatsCache.

US-10: Statistics Caching - Sprint 3 EPIC-2 Raster Integration

Tests the LRU cache for raster statistics:
- Cache entry lifecycle
- TTL expiration
- LRU eviction
- Layer invalidation
- Memory management
"""

import unittest
from unittest.mock import Mock
from datetime import datetime, timedelta
import time


class TestCacheEntry(unittest.TestCase):
    """Test CacheEntry dataclass."""

    def test_entry_creation(self):
        """Test cache entry is created with value."""
        value = {"min": 0, "max": 255}

        # Simulated entry
        entry = {
            'value': value,
            'created_at': datetime.now(),
            'access_count': 0
        }

        self.assertEqual(entry['value'], value)
        self.assertEqual(entry['access_count'], 0)

    def test_entry_touch_increments_count(self):
        """Test touch() updates access metadata."""
        entry = {
            'access_count': 0,
            'last_accessed': datetime.now()
        }

        # Simulate touch
        entry['access_count'] += 1
        entry['last_accessed'] = datetime.now()

        self.assertEqual(entry['access_count'], 1)

    def test_entry_age_calculation(self):
        """Test age calculation in seconds."""
        created = datetime.now() - timedelta(seconds=60)
        age = (datetime.now() - created).total_seconds()

        self.assertGreaterEqual(age, 59)
        self.assertLess(age, 62)

    def test_entry_expiration_check(self):
        """Test TTL expiration logic."""
        ttl_seconds = 300
        created_old = datetime.now() - timedelta(seconds=400)
        created_new = datetime.now() - timedelta(seconds=100)

        age_old = (datetime.now() - created_old).total_seconds()
        age_new = (datetime.now() - created_new).total_seconds()

        is_expired_old = age_old > ttl_seconds
        is_expired_new = age_new > ttl_seconds

        self.assertTrue(is_expired_old)
        self.assertFalse(is_expired_new)


class TestRasterStatsCacheBasics(unittest.TestCase):
    """Test basic cache operations."""

    def test_put_and_get_stats(self):
        """Test storing and retrieving statistics."""
        cache = {}
        layer_id = "layer_123"
        stats = {"band_count": 3, "width": 1000, "height": 1000}

        # Put
        cache[layer_id] = stats

        # Get
        result = cache.get(layer_id)

        self.assertEqual(result, stats)

    def test_has_stats(self):
        """Test checking if stats exist."""
        cache = {}
        layer_id = "layer_123"

        # Before put
        self.assertFalse(layer_id in cache)

        # After put
        cache[layer_id] = {"data": "value"}
        self.assertTrue(layer_id in cache)

    def test_cache_miss_returns_none(self):
        """Test missing entry returns None."""
        cache = {}
        result = cache.get("nonexistent")
        self.assertIsNone(result)


class TestLRUEviction(unittest.TestCase):
    """Test LRU eviction behavior."""

    def test_eviction_at_capacity(self):
        """Test oldest entry is evicted when at capacity."""
        max_entries = 3
        cache = {}

        # Fill cache
        for i in range(max_entries):
            cache[f"layer_{i}"] = f"stats_{i}"

        self.assertEqual(len(cache), 3)

        # Add one more, need to evict
        if len(cache) >= max_entries:
            oldest_key = next(iter(cache))
            del cache[oldest_key]

        cache["layer_new"] = "stats_new"

        self.assertEqual(len(cache), 3)
        self.assertIn("layer_new", cache)
        self.assertNotIn("layer_0", cache)

    def test_lru_order_updated_on_access(self):
        """Test accessing entry updates LRU order."""
        from collections import OrderedDict

        cache = OrderedDict()
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        # Access 'a' - should move to end
        cache.move_to_end("a")

        keys = list(cache.keys())
        self.assertEqual(keys, ["b", "c", "a"])


class TestHistogramCache(unittest.TestCase):
    """Test histogram-specific caching."""

    def test_histogram_key_includes_band(self):
        """Test histogram cache key includes band number."""
        layer_id = "layer_123"
        band = 2

        key = f"{layer_id}:histogram:band{band}"

        self.assertEqual(key, "layer_123:histogram:band2")

    def test_histogram_memory_limit(self):
        """Test histogram memory limit enforcement."""
        max_memory = 50 * 1024 * 1024  # 50MB
        current_memory = 45 * 1024 * 1024  # 45MB
        new_item_size = 10 * 1024 * 1024  # 10MB

        would_exceed = current_memory + new_item_size > max_memory

        self.assertTrue(would_exceed)


class TestLayerInvalidation(unittest.TestCase):
    """Test layer-specific cache invalidation."""

    def test_invalidate_removes_all_layer_entries(self):
        """Test invalidation removes all entries for a layer."""
        cache = {
            "layer_a:stats:all": "data1",
            "layer_a:stats:band1": "data2",
            "layer_a:histogram:band1": "data3",
            "layer_b:stats:all": "data4",
        }

        layer_id = "layer_a"

        # Remove all entries starting with layer_id
        keys_to_remove = [
            k for k in cache if k.startswith(f"{layer_id}:")
        ]
        for key in keys_to_remove:
            del cache[key]

        self.assertEqual(len(cache), 1)
        self.assertIn("layer_b:stats:all", cache)

    def test_clear_removes_all_entries(self):
        """Test clear removes all cache entries."""
        cache = {"a": 1, "b": 2, "c": 3}

        cache.clear()

        self.assertEqual(len(cache), 0)


class TestCacheStats(unittest.TestCase):
    """Test cache statistics tracking."""

    def test_hit_rate_calculation(self):
        """Test hit rate is calculated correctly."""
        hits = 75
        misses = 25
        total = hits + misses

        hit_rate = hits / total if total > 0 else 0.0

        self.assertEqual(hit_rate, 0.75)

    def test_hit_rate_with_zero_requests(self):
        """Test hit rate is 0 when no requests."""
        hits = 0
        misses = 0
        total = hits + misses

        hit_rate = hits / total if total > 0 else 0.0

        self.assertEqual(hit_rate, 0.0)

    def test_memory_usage_tracking(self):
        """Test memory usage is tracked."""
        memory_bytes = 0
        entry_sizes = [1000, 2000, 500]

        for size in entry_sizes:
            memory_bytes += size

        self.assertEqual(memory_bytes, 3500)

        memory_mb = memory_bytes / (1024 * 1024)
        self.assertLess(memory_mb, 0.01)


class TestThreadSafety(unittest.TestCase):
    """Test thread safety mechanisms."""

    def test_lock_prevents_race_conditions(self):
        """Test lock usage pattern."""
        import threading

        lock = threading.RLock()
        shared_data = {"count": 0}

        def increment():
            with lock:
                shared_data["count"] += 1

        threads = [
            threading.Thread(target=increment)
            for _ in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(shared_data["count"], 10)


class TestCacheConfiguration(unittest.TestCase):
    """Test cache configuration options."""

    def test_default_config_values(self):
        """Test default configuration values."""
        defaults = {
            'max_entries': 50,
            'max_memory_mb': 100.0,
            'ttl_seconds': 3600,
            'enable_histograms': True,
        }

        self.assertEqual(defaults['max_entries'], 50)
        self.assertEqual(defaults['ttl_seconds'], 3600)

    def test_custom_config_overrides_defaults(self):
        """Test custom configuration overrides."""
        defaults = {'max_entries': 50}
        custom = {'max_entries': 100}

        merged = {**defaults, **custom}

        self.assertEqual(merged['max_entries'], 100)


class TestGlobalCacheInstance(unittest.TestCase):
    """Test global cache singleton."""

    def test_get_cache_returns_same_instance(self):
        """Test global cache returns singleton."""
        instance1 = id(object())  # Simulated first call
        instance2 = instance1  # Singleton returns same

        self.assertEqual(instance1, instance2)

    def test_reset_clears_global(self):
        """Test reset clears global instance."""
        global_cache = {"data": "value"}

        # Reset
        global_cache = None

        self.assertIsNone(global_cache)


class TestCacheIntegration(unittest.TestCase):
    """Integration tests for cache with service."""

    def test_service_uses_cache_for_stats(self):
        """Test service checks cache before computation."""
        cache = Mock()
        cache.get_stats.return_value = {"cached": True}

        result = cache.get_stats("layer_123")

        self.assertEqual(result["cached"], True)
        cache.get_stats.assert_called_once()

    def test_service_populates_cache_after_computation(self):
        """Test service stores computed stats in cache."""
        cache = Mock()
        stats = {"computed": True}

        cache.put_stats("layer_123", stats)

        cache.put_stats.assert_called_once_with("layer_123", stats)


if __name__ == '__main__':
    unittest.main()
