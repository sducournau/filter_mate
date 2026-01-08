"""
Tests for OptimizationConfig Value Object.

Part of Phase 3 Core Domain Layer implementation.
"""
import pytest
from core.domain.optimization_config import OptimizationConfig


class TestOptimizationConfigCreation:
    """Tests for OptimizationConfig creation."""

    def test_create_default(self):
        """Test creating default configuration."""
        config = OptimizationConfig.default()
        assert config.use_materialized_views
        assert config.use_cache
        assert config.use_spatial_index
        assert not config.parallel_execution

    def test_create_performance(self):
        """Test creating performance configuration."""
        config = OptimizationConfig.performance()
        assert config.use_materialized_views
        assert config.mv_feature_threshold == 5000
        assert config.parallel_execution
        assert config.max_workers == 4

    def test_create_memory_efficient(self):
        """Test creating memory-efficient configuration."""
        config = OptimizationConfig.memory_efficient()
        assert not config.use_materialized_views
        assert config.use_cache
        assert config.cache_ttl_seconds == 60.0
        assert not config.parallel_execution

    def test_create_disabled(self):
        """Test creating disabled configuration."""
        config = OptimizationConfig.disabled()
        assert not config.use_materialized_views
        assert not config.use_cache
        assert not config.use_spatial_index
        assert not config.parallel_execution

    def test_for_layer_count_small(self):
        """Test configuration for small layer."""
        config = OptimizationConfig.for_layer_count(500)
        assert not config.use_materialized_views

    def test_for_layer_count_medium(self):
        """Test configuration for medium layer."""
        config = OptimizationConfig.for_layer_count(50000)
        assert config.use_materialized_views

    def test_for_layer_count_large(self):
        """Test configuration for large layer."""
        config = OptimizationConfig.for_layer_count(200000)
        assert config.parallel_execution


class TestOptimizationConfigImmutability:
    """Tests for OptimizationConfig immutability."""

    def test_config_is_frozen(self):
        """Test that configuration cannot be modified."""
        config = OptimizationConfig.default()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.use_cache = False

    def test_with_cache_ttl_returns_new(self):
        """Test that with_cache_ttl returns new instance."""
        config1 = OptimizationConfig.default()
        config2 = config1.with_cache_ttl(60.0)
        
        assert config1 is not config2
        assert config1.cache_ttl_seconds != config2.cache_ttl_seconds
        assert config2.cache_ttl_seconds == 60.0

    def test_with_batch_size_returns_new(self):
        """Test that with_batch_size returns new instance."""
        config1 = OptimizationConfig.default()
        config2 = config1.with_batch_size(1000)
        
        assert config1 is not config2
        assert config2.batch_size == 1000

    def test_with_parallel_returns_new(self):
        """Test that with_parallel returns new instance."""
        config1 = OptimizationConfig.default()
        config2 = config1.with_parallel(True, max_workers=8)
        
        assert config1 is not config2
        assert config2.parallel_execution
        assert config2.max_workers == 8

    def test_with_caching_returns_new(self):
        """Test that with_caching returns new instance."""
        config1 = OptimizationConfig.default()
        config2 = config1.with_caching(False)
        
        assert config1 is not config2
        assert not config2.use_cache


class TestOptimizationConfigValidation:
    """Tests for OptimizationConfig validation."""

    def test_negative_mv_threshold_raises_error(self):
        """Test that negative mv_feature_threshold raises ValueError."""
        with pytest.raises(ValueError, match="mv_feature_threshold cannot be negative"):
            OptimizationConfig(mv_feature_threshold=-1)

    def test_negative_cache_ttl_raises_error(self):
        """Test that negative cache_ttl_seconds raises ValueError."""
        with pytest.raises(ValueError, match="cache_ttl_seconds cannot be negative"):
            OptimizationConfig(cache_ttl_seconds=-1)

    def test_negative_cache_entries_raises_error(self):
        """Test that negative cache_max_entries raises ValueError."""
        with pytest.raises(ValueError, match="cache_max_entries cannot be negative"):
            OptimizationConfig(cache_max_entries=-1)

    def test_zero_batch_size_raises_error(self):
        """Test that zero batch_size raises ValueError."""
        with pytest.raises(ValueError, match="batch_size must be at least 1"):
            OptimizationConfig(batch_size=0)

    def test_zero_workers_raises_error(self):
        """Test that zero max_workers raises ValueError."""
        with pytest.raises(ValueError, match="max_workers must be at least 1"):
            OptimizationConfig(max_workers=0)


class TestOptimizationConfigDecisions:
    """Tests for OptimizationConfig decision methods."""

    def test_should_use_mv_true_by_count(self):
        """Test should_use_mv returns true for large feature count."""
        config = OptimizationConfig.default()
        assert config.should_use_mv(15000)  # Above default threshold

    def test_should_use_mv_true_by_complexity(self):
        """Test should_use_mv returns true for complex expression."""
        config = OptimizationConfig.default()
        assert config.should_use_mv(100, expression_complexity=5)

    def test_should_use_mv_false_when_disabled(self):
        """Test should_use_mv returns false when disabled."""
        config = OptimizationConfig.disabled()
        assert not config.should_use_mv(100000)

    def test_should_use_mv_false_small_layer(self):
        """Test should_use_mv returns false for small layer."""
        config = OptimizationConfig.default()
        assert not config.should_use_mv(500)

    def test_should_use_spatial_index_true(self):
        """Test should_use_spatial_index returns true."""
        config = OptimizationConfig.default()
        assert config.should_use_spatial_index(5000)

    def test_should_use_spatial_index_false_small(self):
        """Test should_use_spatial_index returns false for small layer."""
        config = OptimizationConfig.default()
        assert not config.should_use_spatial_index(100)

    def test_should_use_spatial_index_false_disabled(self):
        """Test should_use_spatial_index returns false when disabled."""
        config = OptimizationConfig.disabled()
        assert not config.should_use_spatial_index(10000)

    def test_should_use_streaming(self):
        """Test should_use_streaming for large datasets."""
        config = OptimizationConfig.default()
        assert config.should_use_streaming(100000)
        assert not config.should_use_streaming(1000)

    def test_should_use_parallel(self):
        """Test should_use_parallel decision."""
        config = OptimizationConfig.performance()
        assert config.should_use_parallel(50000)

    def test_should_not_use_parallel_when_disabled(self):
        """Test should_use_parallel returns false when disabled."""
        config = OptimizationConfig.default()  # parallel_execution = False
        assert not config.should_use_parallel(50000)

    def test_get_batch_count(self):
        """Test batch count calculation."""
        config = OptimizationConfig(batch_size=1000)
        assert config.get_batch_count(500) == 1
        assert config.get_batch_count(1000) == 1
        assert config.get_batch_count(1001) == 2
        assert config.get_batch_count(2500) == 3


class TestOptimizationConfigString:
    """Tests for OptimizationConfig string representation."""

    def test_str_with_features(self):
        """Test string representation shows enabled features."""
        config = OptimizationConfig.performance()
        string_repr = str(config)
        assert "MV" in string_repr
        assert "Cache" in string_repr
        assert "Parallel" in string_repr

    def test_str_disabled(self):
        """Test string representation for disabled config."""
        config = OptimizationConfig.disabled()
        string_repr = str(config)
        assert "disabled" in string_repr
