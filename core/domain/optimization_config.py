"""
Optimization Configuration Value Object.

Immutable configuration for backend optimization strategies.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class OptimizationConfig:
    """
    Immutable configuration for backend optimizations.

    Provides settings that control how the filter backends optimize
    their operations. Different presets are available for different
    use cases (performance, memory-efficient, disabled).

    Attributes:
        use_materialized_views: Enable MV for PostgreSQL
        mv_feature_threshold: Minimum features to trigger MV
        mv_complexity_threshold: Minimum expression complexity for MV
        use_cache: Enable result caching
        cache_ttl_seconds: Cache time-to-live in seconds
        cache_max_entries: Maximum cache entries
        use_spatial_index: Prefer spatial index when available
        spatial_index_threshold: Minimum features for spatial index benefit
        batch_size: Batch size for feature processing
        parallel_execution: Enable parallel processing
        max_workers: Maximum parallel workers

    Example:
        >>> config = OptimizationConfig.performance()
        >>> config.should_use_mv(50000)
        True
        >>> config.should_use_spatial_index(5000)
        True
    """
    # Materialized View settings
    use_materialized_views: bool = True
    mv_feature_threshold: int = 10000
    mv_complexity_threshold: int = 3
    mv_refresh_on_update: bool = True

    # Cache settings
    use_cache: bool = True
    cache_ttl_seconds: float = 300.0
    cache_max_entries: int = 100
    cache_size_mb: float = 50.0

    # Spatial index settings
    use_spatial_index: bool = True
    spatial_index_threshold: int = 1000
    prefer_rtree: bool = True

    # Performance settings
    batch_size: int = 5000
    parallel_execution: bool = False
    max_workers: int = 4

    # Memory settings
    max_geometry_cache_mb: float = 100.0
    streaming_threshold: int = 50000

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.mv_feature_threshold < 0:
            raise ValueError("mv_feature_threshold cannot be negative")
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        if self.cache_max_entries < 0:
            raise ValueError("cache_max_entries cannot be negative")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.max_workers < 1:
            raise ValueError("max_workers must be at least 1")

    @classmethod
    def default(cls) -> 'OptimizationConfig':
        """
        Create configuration with default values.

        Returns:
            OptimizationConfig with balanced defaults
        """
        return cls()

    @classmethod
    def performance(cls) -> 'OptimizationConfig':
        """
        Create configuration optimized for maximum performance.

        Uses more memory and enables all optimizations.

        Returns:
            OptimizationConfig for high performance
        """
        return cls(
            use_materialized_views=True,
            mv_feature_threshold=5000,
            mv_complexity_threshold=2,
            use_cache=True,
            cache_ttl_seconds=600.0,
            cache_max_entries=200,
            cache_size_mb=100.0,
            use_spatial_index=True,
            spatial_index_threshold=500,
            batch_size=10000,
            parallel_execution=True,
            max_workers=4,
            max_geometry_cache_mb=200.0,
            streaming_threshold=100000
        )

    @classmethod
    def memory_efficient(cls) -> 'OptimizationConfig':
        """
        Create configuration optimized for low memory usage.

        Reduces cache sizes and disables memory-intensive features.

        Returns:
            OptimizationConfig for memory efficiency
        """
        return cls(
            use_materialized_views=False,
            use_cache=True,
            cache_ttl_seconds=60.0,
            cache_max_entries=20,
            cache_size_mb=10.0,
            use_spatial_index=True,
            spatial_index_threshold=2000,
            batch_size=1000,
            parallel_execution=False,
            max_workers=1,
            max_geometry_cache_mb=20.0,
            streaming_threshold=10000
        )

    @classmethod
    def disabled(cls) -> 'OptimizationConfig':
        """
        Create configuration with all optimizations disabled.

        Useful for debugging or testing baseline performance.

        Returns:
            OptimizationConfig with no optimizations
        """
        return cls(
            use_materialized_views=False,
            use_cache=False,
            use_spatial_index=False,
            parallel_execution=False,
            batch_size=1000,
            max_workers=1
        )

    @classmethod
    def for_layer_count(cls, feature_count: int) -> 'OptimizationConfig':
        """
        Create configuration optimized for a specific layer size.

        Args:
            feature_count: Number of features in the layer

        Returns:
            OptimizationConfig appropriate for the layer size
        """
        if feature_count > 100000:
            return cls.performance()
        elif feature_count > 10000:
            return cls.default()
        else:
            return cls.memory_efficient()

    def should_use_mv(
        self,
        feature_count: int,
        expression_complexity: int = 1
    ) -> bool:
        """
        Determine if materialized view should be used.

        Args:
            feature_count: Number of features in source layer
            expression_complexity: Estimated expression complexity (1-10)

        Returns:
            True if MV should be used
        """
        if not self.use_materialized_views:
            return False
        return (
            feature_count >= self.mv_feature_threshold or
            expression_complexity >= self.mv_complexity_threshold
        )

    def should_use_spatial_index(self, feature_count: int) -> bool:
        """
        Determine if spatial index should be preferred.

        Args:
            feature_count: Number of features in layer

        Returns:
            True if spatial index should be used
        """
        if not self.use_spatial_index:
            return False
        return feature_count >= self.spatial_index_threshold

    def should_use_streaming(self, feature_count: int) -> bool:
        """
        Determine if streaming mode should be used.

        Streaming mode processes features in batches to reduce memory.

        Args:
            feature_count: Number of features to process

        Returns:
            True if streaming should be used
        """
        return feature_count >= self.streaming_threshold

    def should_use_parallel(self, feature_count: int) -> bool:
        """
        Determine if parallel execution should be used.

        Args:
            feature_count: Number of features to process

        Returns:
            True if parallel execution should be used
        """
        if not self.parallel_execution:
            return False
        # Only worth parallelizing for larger datasets
        return feature_count >= self.batch_size * 2

    def get_batch_count(self, feature_count: int) -> int:
        """
        Calculate number of batches for a given feature count.

        Args:
            feature_count: Total features to process

        Returns:
            Number of batches
        """
        return (feature_count + self.batch_size - 1) // self.batch_size

    def with_cache_ttl(self, ttl_seconds: float) -> 'OptimizationConfig':
        """
        Return new config with modified cache TTL.

        Args:
            ttl_seconds: New cache TTL in seconds

        Returns:
            New OptimizationConfig with updated TTL
        """
        return replace(self, cache_ttl_seconds=ttl_seconds)

    def with_batch_size(self, size: int) -> 'OptimizationConfig':
        """
        Return new config with modified batch size.

        Args:
            size: New batch size

        Returns:
            New OptimizationConfig with updated batch size
        """
        return replace(self, batch_size=size)

    def with_parallel(
        self,
        enabled: bool,
        max_workers: Optional[int] = None
    ) -> 'OptimizationConfig':
        """
        Return new config with modified parallel settings.

        Args:
            enabled: Whether to enable parallel execution
            max_workers: Optional new max workers value

        Returns:
            New OptimizationConfig with updated parallel settings
        """
        workers = max_workers if max_workers is not None else self.max_workers
        return replace(self, parallel_execution=enabled, max_workers=workers)

    def with_caching(
        self,
        enabled: bool,
        ttl_seconds: Optional[float] = None,
        max_entries: Optional[int] = None
    ) -> 'OptimizationConfig':
        """
        Return new config with modified caching settings.

        Args:
            enabled: Whether to enable caching
            ttl_seconds: Optional new TTL
            max_entries: Optional new max entries

        Returns:
            New OptimizationConfig with updated cache settings
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.cache_ttl_seconds
        entries = max_entries if max_entries is not None else self.cache_max_entries
        return replace(self, use_cache=enabled, cache_ttl_seconds=ttl, cache_max_entries=entries)

    def __str__(self) -> str:
        """Human-readable representation."""
        features = []
        if self.use_materialized_views:
            features.append(f"MV(>{self.mv_feature_threshold})")
        if self.use_cache:
            features.append(f"Cache({self.cache_ttl_seconds}s)")
        if self.use_spatial_index:
            features.append("SpatialIdx")
        if self.parallel_execution:
            features.append(f"Parallel({self.max_workers})")

        return f"OptimizationConfig({', '.join(features) or 'disabled'})"
