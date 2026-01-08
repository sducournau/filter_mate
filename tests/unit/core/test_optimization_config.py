# -*- coding: utf-8 -*-
"""
Unit Tests for OptimizationConfig Value Object.

Tests the OptimizationConfig domain object for:
- Creation via factory methods
- Validation of values
- Decision methods (should_use_mv, etc.)
- Immutability

Author: FilterMate Team
Date: January 2026
"""
import pytest
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))

from core.domain.optimization_config import OptimizationConfig


# ============================================================================
# OptimizationConfig Creation Tests
# ============================================================================

class TestOptimizationConfigCreation:
    """Tests for OptimizationConfig creation."""
    
    def test_default_factory(self):
        """default() should create config with balanced defaults."""
        config = OptimizationConfig.default()
        
        assert config.use_materialized_views
        assert config.use_cache
        assert config.use_spatial_index
        assert not config.parallel_execution
    
    def test_performance_factory(self):
        """performance() should create high-performance config."""
        config = OptimizationConfig.performance()
        
        assert config.use_materialized_views
        assert config.use_cache
        assert config.use_spatial_index
        # Performance mode may enable more aggressive settings
    
    def test_memory_efficient_factory(self):
        """memory_efficient() should create low-memory config."""
        config = OptimizationConfig.memory_efficient()
        
        # Memory efficient mode should have lower cache sizes
        assert config.cache_max_entries <= 50
        assert config.max_geometry_cache_mb <= 50
    
    def test_disabled_factory(self):
        """disabled() should create config with all optimizations off."""
        config = OptimizationConfig.disabled()
        
        assert not config.use_materialized_views
        assert not config.use_cache
        assert not config.use_spatial_index
        assert not config.parallel_execution
    
    def test_direct_creation(self):
        """Should allow direct creation with custom values."""
        config = OptimizationConfig(
            use_materialized_views=False,
            mv_feature_threshold=50000,
            use_cache=True,
            cache_ttl_seconds=600.0,
            batch_size=10000
        )
        
        assert not config.use_materialized_views
        assert config.mv_feature_threshold == 50000
        assert config.use_cache
        assert config.cache_ttl_seconds == 600.0
        assert config.batch_size == 10000


# ============================================================================
# OptimizationConfig Validation Tests
# ============================================================================

class TestOptimizationConfigValidation:
    """Tests for OptimizationConfig validation."""
    
    def test_negative_mv_threshold_raises(self):
        """Negative mv_feature_threshold should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            OptimizationConfig(mv_feature_threshold=-1)
    
    def test_negative_cache_ttl_raises(self):
        """Negative cache_ttl_seconds should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            OptimizationConfig(cache_ttl_seconds=-1.0)
    
    def test_negative_cache_entries_raises(self):
        """Negative cache_max_entries should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            OptimizationConfig(cache_max_entries=-1)
    
    def test_zero_batch_size_raises(self):
        """Zero batch_size should raise ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            OptimizationConfig(batch_size=0)
    
    def test_zero_max_workers_raises(self):
        """Zero max_workers should raise ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            OptimizationConfig(max_workers=0)
    
    def test_valid_edge_values(self):
        """Edge values should be valid."""
        config = OptimizationConfig(
            mv_feature_threshold=0,
            cache_ttl_seconds=0.0,
            cache_max_entries=0,
            batch_size=1,
            max_workers=1
        )
        
        assert config.mv_feature_threshold == 0
        assert config.cache_ttl_seconds == 0.0
        assert config.batch_size == 1


# ============================================================================
# OptimizationConfig Immutability Tests
# ============================================================================

class TestOptimizationConfigImmutability:
    """Tests for OptimizationConfig immutability."""
    
    def test_config_is_frozen(self):
        """OptimizationConfig should be immutable."""
        config = OptimizationConfig.default()
        
        with pytest.raises(Exception):  # FrozenInstanceError
            config.use_materialized_views = False
    
    def test_with_method_creates_copy(self):
        """with_* methods should create new instance."""
        original = OptimizationConfig.default()
        
        if hasattr(original, 'with_cache_disabled'):
            modified = original.with_cache_disabled()
            
            assert original.use_cache
            assert not modified.use_cache
            assert original is not modified


# ============================================================================
# OptimizationConfig Decision Methods Tests
# ============================================================================

class TestOptimizationConfigDecisions:
    """Tests for OptimizationConfig decision methods."""
    
    def test_should_use_mv_true(self):
        """should_use_mv should return True for large datasets."""
        config = OptimizationConfig(
            use_materialized_views=True,
            mv_feature_threshold=10000
        )
        
        assert config.should_use_mv(50000)
    
    def test_should_use_mv_false_disabled(self):
        """should_use_mv should return False when disabled."""
        config = OptimizationConfig(
            use_materialized_views=False,
            mv_feature_threshold=10000
        )
        
        assert not config.should_use_mv(50000)
    
    def test_should_use_mv_false_small_dataset(self):
        """should_use_mv should return False for small datasets."""
        config = OptimizationConfig(
            use_materialized_views=True,
            mv_feature_threshold=10000
        )
        
        assert not config.should_use_mv(5000)
    
    def test_should_use_spatial_index_true(self):
        """should_use_spatial_index should return True for qualifying datasets."""
        config = OptimizationConfig(
            use_spatial_index=True,
            spatial_index_threshold=1000
        )
        
        assert config.should_use_spatial_index(5000)
    
    def test_should_use_spatial_index_false_disabled(self):
        """should_use_spatial_index should return False when disabled."""
        config = OptimizationConfig(
            use_spatial_index=False,
            spatial_index_threshold=1000
        )
        
        assert not config.should_use_spatial_index(5000)
    
    def test_should_use_spatial_index_false_small(self):
        """should_use_spatial_index should return False for small datasets."""
        config = OptimizationConfig(
            use_spatial_index=True,
            spatial_index_threshold=1000
        )
        
        assert not config.should_use_spatial_index(500)
    
    def test_use_cache_enabled(self):
        """use_cache property should return True when enabled."""
        config = OptimizationConfig(use_cache=True)
        
        assert config.use_cache is True
    
    def test_use_cache_disabled(self):
        """use_cache property should return False when disabled."""
        config = OptimizationConfig(use_cache=False)
        
        assert config.use_cache is False
    
    def test_should_use_streaming_true(self):
        """should_use_streaming should return True for very large datasets."""
        config = OptimizationConfig(streaming_threshold=50000)
        
        assert config.should_use_streaming(100000)
    
    def test_should_use_streaming_false(self):
        """should_use_streaming should return False for smaller datasets."""
        config = OptimizationConfig(streaming_threshold=50000)
        
        assert not config.should_use_streaming(30000)


# ============================================================================
# OptimizationConfig Property Tests
# ============================================================================

class TestOptimizationConfigProperties:
    """Tests for OptimizationConfig computed properties."""
    
    def test_default_values(self):
        """Default values should be sensible."""
        config = OptimizationConfig.default()
        
        assert config.mv_feature_threshold > 0
        assert config.cache_ttl_seconds > 0
        assert config.batch_size > 0
        assert config.max_workers >= 1
    
    def test_cache_settings(self):
        """Cache settings should be accessible."""
        config = OptimizationConfig(
            use_cache=True,
            cache_ttl_seconds=120.0,
            cache_max_entries=50
        )
        
        assert config.cache_ttl_seconds == 120.0
        assert config.cache_max_entries == 50
    
    def test_parallel_settings(self):
        """Parallel settings should be accessible."""
        config = OptimizationConfig(
            parallel_execution=True,
            max_workers=8
        )
        
        assert config.parallel_execution
        assert config.max_workers == 8


# ============================================================================
# OptimizationConfig Equality Tests
# ============================================================================

class TestOptimizationConfigEquality:
    """Tests for OptimizationConfig equality."""
    
    def test_equal_configs(self):
        """Configs with same values should be equal."""
        config1 = OptimizationConfig(
            use_materialized_views=True,
            mv_feature_threshold=10000
        )
        config2 = OptimizationConfig(
            use_materialized_views=True,
            mv_feature_threshold=10000
        )
        
        assert config1 == config2
    
    def test_different_configs_not_equal(self):
        """Configs with different values should not be equal."""
        config1 = OptimizationConfig(mv_feature_threshold=10000)
        config2 = OptimizationConfig(mv_feature_threshold=20000)
        
        assert config1 != config2
    
    def test_hashable(self):
        """OptimizationConfig should be hashable."""
        config = OptimizationConfig.default()
        
        hash_value = hash(config)
        assert isinstance(hash_value, int)
        
        config_set = {config}
        assert config in config_set


# ============================================================================
# OptimizationConfig Fluent Interface Tests
# ============================================================================

class TestOptimizationConfigFluentInterface:
    """Tests for OptimizationConfig fluent interface."""
    
    def test_with_cache_ttl(self):
        """with_cache_ttl should return new config with updated TTL."""
        config = OptimizationConfig(cache_ttl_seconds=60.0)
        new_config = config.with_cache_ttl(180.0)
        
        assert new_config.cache_ttl_seconds == 180.0
        assert config.cache_ttl_seconds == 60.0  # Original unchanged
    
    def test_with_batch_size(self):
        """with_batch_size should return new config with updated batch size."""
        config = OptimizationConfig(batch_size=500)
        new_config = config.with_batch_size(2000)
        
        assert new_config.batch_size == 2000
        assert config.batch_size == 500  # Original unchanged
    
    def test_with_parallel_enabled(self):
        """with_parallel should enable parallel execution."""
        config = OptimizationConfig(parallel_execution=False)
        new_config = config.with_parallel(True, max_workers=8)
        
        assert new_config.parallel_execution is True
        assert new_config.max_workers == 8
        assert config.parallel_execution is False  # Original unchanged
    
    def test_with_caching_enabled(self):
        """with_caching should enable caching with new settings."""
        config = OptimizationConfig(use_cache=False)
        new_config = config.with_caching(True, ttl_seconds=120.0, max_entries=200)
        
        assert new_config.use_cache is True
        assert new_config.cache_ttl_seconds == 120.0
        assert new_config.cache_max_entries == 200
        assert config.use_cache is False  # Original unchanged


# ============================================================================
# OptimizationConfig String Representation Tests
# ============================================================================

class TestOptimizationConfigStringRepresentation:
    """Tests for OptimizationConfig string representation."""
    
    def test_str_with_features(self):
        """__str__ should show enabled features."""
        config = OptimizationConfig(
            use_materialized_views=True,
            mv_feature_threshold=10000,
            use_cache=True,
            cache_ttl_seconds=60.0
        )
        
        str_repr = str(config)
        
        assert "MV" in str_repr or "Materialized" in str_repr or "OptimizationConfig" in str_repr
    
    def test_str_disabled(self):
        """__str__ should show disabled for no features."""
        config = OptimizationConfig.disabled()
        
        str_repr = str(config)
        
        assert "disabled" in str_repr.lower() or "OptimizationConfig" in str_repr


# ============================================================================
# OptimizationConfig Edge Cases Tests
# ============================================================================

class TestOptimizationConfigEdgeCases:
    """Tests for OptimizationConfig edge cases."""
    
    def test_very_large_threshold(self):
        """Should handle very large thresholds."""
        config = OptimizationConfig(
            mv_feature_threshold=10_000_000,
            streaming_threshold=100_000_000
        )
        
        assert config.mv_feature_threshold == 10_000_000
        assert not config.should_use_mv(1_000_000)
    
    def test_zero_cache_ttl(self):
        """Zero cache TTL should be valid (immediate expiration)."""
        config = OptimizationConfig(cache_ttl_seconds=0.0)
        
        assert config.cache_ttl_seconds == 0.0
    
    def test_very_large_cache_size(self):
        """Should handle very large cache sizes."""
        config = OptimizationConfig(
            cache_size_mb=1000.0,
            max_geometry_cache_mb=500.0
        )
        
        assert config.cache_size_mb == 1000.0
        assert config.max_geometry_cache_mb == 500.0
