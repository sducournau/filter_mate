# -*- coding: utf-8 -*-
"""
Raster Performance Optimization Module.

EPIC-2: Raster Integration
US-12: Performance Optimization

Provides performance optimization utilities for raster operations:
- Smart sampling for large rasters
- Memory-efficient iteration
- Progress tracking
- Computation throttling
- Background task support

Author: FilterMate Team
Date: January 2026
"""
import logging
import math
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    Callable,
    Generator,
    List,
    Optional,
    Tuple,
    TypeVar,
)

logger = logging.getLogger('FilterMate.Core.RasterPerformance')

T = TypeVar('T')


# =============================================================================
# Performance Thresholds
# =============================================================================

@dataclass(frozen=True)
class PerformanceThresholds:
    """
    Configurable performance thresholds.
    
    These values determine when optimizations are applied.
    """
    # Pixel counts
    SMALL_RASTER_PIXELS: int = 1_000_000       # 1 megapixel
    MEDIUM_RASTER_PIXELS: int = 10_000_000     # 10 megapixels
    LARGE_RASTER_PIXELS: int = 100_000_000     # 100 megapixels
    
    # Sample sizes
    DEFAULT_SAMPLE_SIZE: int = 250_000         # Default sample
    MIN_SAMPLE_SIZE: int = 10_000              # Minimum for accuracy
    MAX_SAMPLE_SIZE: int = 1_000_000           # Maximum for performance
    
    # Time limits (seconds)
    DEFAULT_TIMEOUT: float = 30.0              # Default operation timeout
    HISTOGRAM_TIMEOUT: float = 10.0            # Histogram computation
    STATS_TIMEOUT: float = 20.0                # Statistics computation
    
    # Memory limits (MB)
    MAX_MEMORY_MB: float = 500.0               # Max memory for operations
    WARNING_MEMORY_MB: float = 200.0           # Memory warning threshold
    
    # Histogram bins
    DEFAULT_HISTOGRAM_BINS: int = 256
    MIN_HISTOGRAM_BINS: int = 16
    MAX_HISTOGRAM_BINS: int = 1024


# Default thresholds instance
DEFAULT_THRESHOLDS = PerformanceThresholds()


# =============================================================================
# Sampling Strategies
# =============================================================================

class SamplingStrategy(Enum):
    """Strategies for sampling large rasters."""
    NONE = auto()           # No sampling (full computation)
    RANDOM = auto()         # Random pixel sampling
    SYSTEMATIC = auto()     # Systematic grid sampling
    ADAPTIVE = auto()       # Adaptive based on data distribution
    BLOCK = auto()          # Block-based sampling


@dataclass
class SamplingConfig:
    """
    Configuration for raster sampling.
    
    Attributes:
        strategy: Sampling strategy to use
        sample_size: Target number of pixels to sample
        coverage_percent: Target coverage percentage
        seed: Random seed for reproducibility
        preserve_extremes: Whether to preserve min/max values
    """
    strategy: SamplingStrategy = SamplingStrategy.SYSTEMATIC
    sample_size: int = DEFAULT_THRESHOLDS.DEFAULT_SAMPLE_SIZE
    coverage_percent: float = 10.0
    seed: Optional[int] = None
    preserve_extremes: bool = True


class RasterSampler:
    """
    Smart sampler for large rasters.
    
    Provides efficient sampling strategies that balance
    accuracy with performance.
    
    Example:
        >>> sampler = RasterSampler(width=10000, height=10000)
        >>> config = sampler.recommend_sampling()
        >>> for x, y in sampler.sample_positions(config):
        ...     process_pixel(x, y)
    """
    
    def __init__(
        self,
        width: int,
        height: int,
        band_count: int = 1,
        thresholds: PerformanceThresholds = DEFAULT_THRESHOLDS
    ):
        """
        Initialize sampler.
        
        Args:
            width: Raster width in pixels
            height: Raster height in pixels
            band_count: Number of bands
            thresholds: Performance thresholds
        """
        self.width = width
        self.height = height
        self.band_count = band_count
        self.thresholds = thresholds
        self.total_pixels = width * height
    
    @property
    def raster_size_category(self) -> str:
        """Get raster size category."""
        if self.total_pixels <= self.thresholds.SMALL_RASTER_PIXELS:
            return "small"
        elif self.total_pixels <= self.thresholds.MEDIUM_RASTER_PIXELS:
            return "medium"
        elif self.total_pixels <= self.thresholds.LARGE_RASTER_PIXELS:
            return "large"
        return "very_large"
    
    @property
    def needs_sampling(self) -> bool:
        """Check if sampling is recommended."""
        return self.total_pixels > self.thresholds.SMALL_RASTER_PIXELS
    
    def recommend_sampling(self) -> SamplingConfig:
        """
        Recommend sampling configuration based on raster size.
        
        Returns:
            Optimal SamplingConfig for this raster
        """
        if not self.needs_sampling:
            return SamplingConfig(
                strategy=SamplingStrategy.NONE,
                sample_size=self.total_pixels
            )
        
        # Calculate optimal sample size
        if self.total_pixels <= self.thresholds.MEDIUM_RASTER_PIXELS:
            # Medium: 10% sample
            sample_size = min(
                self.total_pixels // 10,
                self.thresholds.MAX_SAMPLE_SIZE
            )
            strategy = SamplingStrategy.SYSTEMATIC
        elif self.total_pixels <= self.thresholds.LARGE_RASTER_PIXELS:
            # Large: 1% sample
            sample_size = min(
                self.total_pixels // 100,
                self.thresholds.MAX_SAMPLE_SIZE
            )
            strategy = SamplingStrategy.SYSTEMATIC
        else:
            # Very large: fixed sample
            sample_size = self.thresholds.DEFAULT_SAMPLE_SIZE
            strategy = SamplingStrategy.BLOCK
        
        # Ensure minimum
        sample_size = max(sample_size, self.thresholds.MIN_SAMPLE_SIZE)
        
        coverage = (sample_size / self.total_pixels) * 100
        
        logger.debug(
            f"[RasterSampler] Recommended: {strategy.name}, "
            f"size={sample_size}, coverage={coverage:.2f}%"
        )
        
        return SamplingConfig(
            strategy=strategy,
            sample_size=sample_size,
            coverage_percent=coverage,
            preserve_extremes=True
        )
    
    def sample_positions(
        self,
        config: SamplingConfig
    ) -> Generator[Tuple[int, int], None, None]:
        """
        Generate sample positions.
        
        Args:
            config: Sampling configuration
            
        Yields:
            (x, y) pixel coordinates
        """
        if config.strategy == SamplingStrategy.NONE:
            yield from self._full_iteration()
        elif config.strategy == SamplingStrategy.SYSTEMATIC:
            yield from self._systematic_sample(config.sample_size)
        elif config.strategy == SamplingStrategy.RANDOM:
            yield from self._random_sample(config.sample_size, config.seed)
        elif config.strategy == SamplingStrategy.BLOCK:
            yield from self._block_sample(config.sample_size)
        else:
            yield from self._systematic_sample(config.sample_size)
    
    def _full_iteration(self) -> Generator[Tuple[int, int], None, None]:
        """Iterate all pixels."""
        for y in range(self.height):
            for x in range(self.width):
                yield (x, y)
    
    def _systematic_sample(
        self,
        sample_size: int
    ) -> Generator[Tuple[int, int], None, None]:
        """
        Systematic grid sampling.
        
        Creates an evenly-spaced grid of sample points.
        """
        # Calculate grid spacing
        ratio = self.total_pixels / sample_size
        step = max(1, int(math.sqrt(ratio)))
        
        for y in range(0, self.height, step):
            for x in range(0, self.width, step):
                yield (x, y)
    
    def _random_sample(
        self,
        sample_size: int,
        seed: Optional[int] = None
    ) -> Generator[Tuple[int, int], None, None]:
        """Random sampling with optional seed."""
        import random
        if seed is not None:
            random.seed(seed)
        
        positions = set()
        while len(positions) < sample_size:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if (x, y) not in positions:
                positions.add((x, y))
                yield (x, y)
    
    def _block_sample(
        self,
        sample_size: int
    ) -> Generator[Tuple[int, int], None, None]:
        """
        Block-based sampling.
        
        Samples all pixels within evenly-distributed blocks.
        """
        # Calculate block parameters
        block_size = 16
        blocks_needed = sample_size // (block_size * block_size)
        blocks_x = int(math.sqrt(blocks_needed))
        blocks_y = max(1, blocks_needed // blocks_x)
        
        step_x = self.width // (blocks_x + 1)
        step_y = self.height // (blocks_y + 1)
        
        for by in range(blocks_y):
            for bx in range(blocks_x):
                start_x = step_x * (bx + 1) - block_size // 2
                start_y = step_y * (by + 1) - block_size // 2
                
                for dy in range(block_size):
                    for dx in range(block_size):
                        x = start_x + dx
                        y = start_y + dy
                        if 0 <= x < self.width and 0 <= y < self.height:
                            yield (x, y)


# =============================================================================
# Progress Tracking
# =============================================================================

@dataclass
class ProgressInfo:
    """
    Progress information for long-running operations.
    
    Attributes:
        current: Current progress count
        total: Total items to process
        elapsed_seconds: Time elapsed
        estimated_total_seconds: Estimated total time
        message: Current status message
        is_cancelled: Whether operation was cancelled
    """
    current: int = 0
    total: int = 0
    elapsed_seconds: float = 0.0
    estimated_total_seconds: float = 0.0
    message: str = ""
    is_cancelled: bool = False
    
    @property
    def percent(self) -> float:
        """Get progress percentage."""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100)
    
    @property
    def remaining_seconds(self) -> float:
        """Get estimated remaining time."""
        return max(0, self.estimated_total_seconds - self.elapsed_seconds)
    
    def __str__(self) -> str:
        return (
            f"Progress: {self.percent:.1f}% "
            f"({self.current}/{self.total}), "
            f"ETA: {self.remaining_seconds:.1f}s"
        )


class ProgressTracker:
    """
    Track progress of long-running operations.
    
    Example:
        >>> tracker = ProgressTracker(total=1000)
        >>> for item in items:
        ...     process(item)
        ...     tracker.update(1, "Processing...")
        ...     if tracker.should_report():
        ...         callback(tracker.get_progress())
    """
    
    def __init__(
        self,
        total: int,
        report_interval: float = 0.5,
        callback: Optional[Callable[[ProgressInfo], None]] = None
    ):
        """
        Initialize progress tracker.
        
        Args:
            total: Total items to process
            report_interval: Minimum seconds between reports
            callback: Optional progress callback
        """
        self.total = total
        self.report_interval = report_interval
        self.callback = callback
        
        self._current = 0
        self._start_time = time.time()
        self._last_report_time = 0.0
        self._cancelled = False
        self._message = ""
    
    def update(
        self,
        count: int = 1,
        message: Optional[str] = None
    ) -> None:
        """
        Update progress.
        
        Args:
            count: Number of items processed
            message: Optional status message
        """
        self._current += count
        if message:
            self._message = message
        
        if self.should_report() and self.callback:
            self.callback(self.get_progress())
            self._last_report_time = time.time()
    
    def should_report(self) -> bool:
        """Check if progress should be reported."""
        now = time.time()
        return (now - self._last_report_time) >= self.report_interval
    
    def get_progress(self) -> ProgressInfo:
        """Get current progress info."""
        elapsed = time.time() - self._start_time
        
        # Estimate total time
        if self._current > 0:
            rate = self._current / elapsed
            estimated_total = self.total / rate if rate > 0 else 0
        else:
            estimated_total = 0
        
        return ProgressInfo(
            current=self._current,
            total=self.total,
            elapsed_seconds=elapsed,
            estimated_total_seconds=estimated_total,
            message=self._message,
            is_cancelled=self._cancelled
        )
    
    def cancel(self) -> None:
        """Cancel the operation."""
        self._cancelled = True
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self._cancelled
    
    @property
    def is_complete(self) -> bool:
        """Check if complete."""
        return self._current >= self.total


# =============================================================================
# Computation Throttling
# =============================================================================

class ComputationThrottle:
    """
    Throttle computation to avoid UI freezes.
    
    Periodically yields control to allow UI updates.
    
    Example:
        >>> throttle = ComputationThrottle()
        >>> for item in large_list:
        ...     process(item)
        ...     if throttle.should_yield():
        ...         throttle.yield_control()
    """
    
    def __init__(
        self,
        yield_interval_ms: int = 100,
        items_per_check: int = 1000
    ):
        """
        Initialize throttle.
        
        Args:
            yield_interval_ms: Target milliseconds between yields
            items_per_check: Items to process before time check
        """
        self.yield_interval_ms = yield_interval_ms
        self.items_per_check = items_per_check
        
        self._last_yield_time = time.time()
        self._items_since_check = 0
    
    def should_yield(self) -> bool:
        """Check if should yield control."""
        self._items_since_check += 1
        
        if self._items_since_check >= self.items_per_check:
            self._items_since_check = 0
            elapsed_ms = (time.time() - self._last_yield_time) * 1000
            return elapsed_ms >= self.yield_interval_ms
        
        return False
    
    def yield_control(self) -> None:
        """
        Yield control to UI.
        
        Processes pending Qt events.
        """
        try:
            from qgis.PyQt.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        except ImportError:
            pass
        
        self._last_yield_time = time.time()


# =============================================================================
# Memory Estimation
# =============================================================================

@dataclass
class MemoryEstimate:
    """
    Memory usage estimation.
    
    Attributes:
        base_mb: Base memory for operation
        per_pixel_bytes: Bytes per pixel
        total_pixels: Total pixels to process
        band_count: Number of bands
    """
    base_mb: float = 10.0
    per_pixel_bytes: int = 8
    total_pixels: int = 0
    band_count: int = 1
    
    @property
    def total_mb(self) -> float:
        """Calculate total estimated memory."""
        pixel_mb = (
            self.total_pixels * self.band_count * self.per_pixel_bytes
        ) / (1024 * 1024)
        return self.base_mb + pixel_mb
    
    @property
    def is_safe(self) -> bool:
        """Check if within safe limits."""
        return self.total_mb <= DEFAULT_THRESHOLDS.MAX_MEMORY_MB
    
    @property
    def needs_sampling(self) -> bool:
        """Check if sampling is needed for memory."""
        return self.total_mb > DEFAULT_THRESHOLDS.WARNING_MEMORY_MB


def estimate_memory(
    width: int,
    height: int,
    band_count: int = 1,
    bytes_per_pixel: int = 8
) -> MemoryEstimate:
    """
    Estimate memory requirements for raster operation.
    
    Args:
        width: Raster width
        height: Raster height
        band_count: Number of bands
        bytes_per_pixel: Bytes per pixel value
        
    Returns:
        MemoryEstimate with calculated values
    """
    return MemoryEstimate(
        per_pixel_bytes=bytes_per_pixel,
        total_pixels=width * height,
        band_count=band_count
    )


# =============================================================================
# Batch Processing
# =============================================================================

def batch_iterator(
    items: List[T],
    batch_size: int = 1000
) -> Generator[List[T], None, None]:
    """
    Iterate items in batches.
    
    Args:
        items: Items to iterate
        batch_size: Size of each batch
        
    Yields:
        Lists of items
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def chunked_range(
    start: int,
    stop: int,
    chunk_size: int = 1000
) -> Generator[range, None, None]:
    """
    Generate ranges in chunks.
    
    Args:
        start: Range start
        stop: Range stop
        chunk_size: Size of each chunk
        
    Yields:
        range objects
    """
    for i in range(start, stop, chunk_size):
        yield range(i, min(i + chunk_size, stop))
