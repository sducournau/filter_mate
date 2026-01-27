"""
Raster Statistics Service.

Hexagonal service for raster layer statistics and analysis.
Orchestrates between UI layer and RasterPort backend.

EPIC-2: Raster Integration
US-04: Raster Stats Service

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.

Architecture:
    UI Layer (RasterExploringGroupBox)
        ↓
    RasterStatsService (this module)
        ↓
    RasterPort (interface)
        ↓
    QGISRasterBackend (implementation)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..ports.raster_port import (
    BandStatistics,
    HistogramBinMethod,
    HistogramData,
    PixelIdentifyResult,
    RasterDataType,
    RasterPort,
    RasterRendererType,
    RasterStats,
    TransparencySettings,
)

if TYPE_CHECKING:
    from ...infrastructure.cache import RasterStatsCache

logger = logging.getLogger(__name__)


# =============================================================================
# Service Enumerations
# =============================================================================

class StatsRequestStatus(Enum):
    """Status of a statistics request."""
    PENDING = auto()
    COMPUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class StatsCacheStrategy(Enum):
    """Caching strategy for statistics."""
    NONE = auto()           # No caching
    LAYER = auto()          # Cache per layer
    SESSION = auto()        # Cache for session duration
    PERSISTENT = auto()     # Persist to disk


# =============================================================================
# Service Data Classes
# =============================================================================

@dataclass
class StatsRequest:
    """
    Request for raster statistics computation.
    
    Attributes:
        layer_id: Target raster layer ID
        bands: Specific bands to compute (None = all)
        include_histogram: Whether to compute histogram
        histogram_bins: Number of histogram bins
        sample_size: Pixels to sample (0 = all)
        priority: Request priority (higher = more urgent)
        callback: Optional completion callback
    """
    layer_id: str
    bands: Optional[List[int]] = None
    include_histogram: bool = True
    histogram_bins: int = 256
    sample_size: int = 0
    priority: int = 0
    callback: Optional[Callable[['StatsResponse'], None]] = None


@dataclass
class StatsResponse:
    """
    Response from raster statistics computation.
    
    Attributes:
        request: Original request
        status: Computation status
        stats: Computed statistics (if successful)
        histograms: Computed histograms per band
        error_message: Error message (if failed)
        computation_time_ms: Time taken for computation
        timestamp: When computation completed
    """
    request: StatsRequest
    status: StatsRequestStatus
    stats: Optional[RasterStats] = None
    histograms: Dict[int, HistogramData] = field(default_factory=dict)
    error_message: str = ""
    computation_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        """Check if computation was successful."""
        return self.status == StatsRequestStatus.COMPLETED

    @property
    def has_histograms(self) -> bool:
        """Check if histograms are available."""
        return len(self.histograms) > 0


@dataclass
class LayerStatsSnapshot:
    """
    Snapshot of layer statistics for UI display.
    
    Simplified representation for UI components.
    
    Attributes:
        layer_id: Layer identifier
        layer_name: Human-readable name
        band_count: Number of bands
        width: Raster width in pixels
        height: Raster height in pixels
        crs: CRS authority ID
        extent: Bounding box (xmin, ymin, xmax, ymax)
        file_size_mb: Approximate file size in MB
        band_summaries: Quick stats per band
        renderer_type: Current renderer type name
    """
    layer_id: str
    layer_name: str
    band_count: int
    width: int
    height: int
    crs: str
    extent: Tuple[float, float, float, float]
    file_size_mb: float = 0.0
    band_summaries: List['BandSummary'] = field(default_factory=list)
    renderer_type: str = "unknown"


@dataclass
class BandSummary:
    """
    Summary statistics for a single band (UI-friendly).
    
    Attributes:
        band_number: 1-based band index
        min_value: Minimum value (formatted)
        max_value: Maximum value (formatted)
        mean: Mean value (formatted)
        std_dev: Standard deviation (formatted)
        no_data: No-data value (formatted, or "None")
        data_type: Data type name
        null_percent: Percentage of null pixels
    """
    band_number: int
    min_value: str
    max_value: str
    mean: str
    std_dev: str
    no_data: str
    data_type: str
    null_percent: str


# =============================================================================
# Raster Stats Service
# =============================================================================

class RasterStatsService:
    """
    Service for raster layer statistics and analysis.
    
    Provides a clean interface between UI components and
    the RasterPort backend. Handles:
    - Statistics computation orchestration
    - Histogram generation
    - Result caching
    - Format conversion for UI display
    
    Thread Safety:
        This service is NOT thread-safe. For background
        computation, use RasterStatsTask (QgsTask wrapper).
    
    Example:
        >>> from core.services.raster_stats_service import RasterStatsService
        >>> from adapters.backends import get_qgis_raster_backend
        >>> 
        >>> service = RasterStatsService(get_qgis_raster_backend())
        >>> snapshot = service.get_layer_snapshot(layer_id)
        >>> print(f"Layer: {snapshot.layer_name}, Bands: {snapshot.band_count}")
    """
    
    def __init__(
        self,
        backend: RasterPort,
        cache_strategy: StatsCacheStrategy = StatsCacheStrategy.SESSION,
        cache: Optional['RasterStatsCache'] = None
    ):
        """
        Initialize Raster Stats Service.
        
        Args:
            backend: RasterPort implementation to use
            cache_strategy: Caching strategy for results
            cache: Optional RasterStatsCache instance (uses global if None)
        """
        self._backend = backend
        self._cache_strategy = cache_strategy
        self._response_cache: Dict[str, StatsResponse] = {}
        self._pending_requests: Dict[str, StatsRequest] = {}
        
        # Use dedicated cache for better management (US-10)
        self._stats_cache: Optional['RasterStatsCache'] = cache
        if cache is None and cache_strategy != StatsCacheStrategy.NONE:
            try:
                from ...infrastructure.cache import get_raster_stats_cache
                self._stats_cache = get_raster_stats_cache()
            except ImportError:
                logger.warning(
                    "[RasterStatsService] RasterStatsCache not available"
                )
        
        logger.debug(
            f"[RasterStatsService] Initialized with cache={cache_strategy.name}"
        )
    
    # =========================================================================
    # Public API - Statistics
    # =========================================================================
    
    def compute_statistics(
        self,
        request: StatsRequest
    ) -> StatsResponse:
        """
        Compute statistics for a raster layer.
        
        Synchronous computation - for background processing,
        use RasterStatsTask instead.
        
        Args:
            request: Statistics request parameters
            
        Returns:
            StatsResponse with computed statistics or error
        """
        import time
        start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(request)
        if cache_key in self._response_cache:
            cached = self._response_cache[cache_key]
            logger.debug(
                f"[RasterStatsService] Cache hit for {request.layer_id}"
            )
            return cached
        
        try:
            # Mark as computing
            self._pending_requests[request.layer_id] = request
            
            # Compute statistics via backend
            stats = self._backend.get_statistics(
                layer_id=request.layer_id,
                bands=request.bands,
                sample_size=request.sample_size,
                force_recalculate=False
            )
            
            # Compute histograms if requested
            histograms = {}
            if request.include_histogram:
                bands = request.bands or list(
                    range(1, stats.band_count + 1)
                )
                for band_num in bands:
                    try:
                        hist = self._backend.get_histogram(
                            layer_id=request.layer_id,
                            band_number=band_num,
                            bin_count=request.histogram_bins
                        )
                        histograms[band_num] = hist
                    except Exception as e:
                        logger.warning(
                            f"[RasterStatsService] Histogram failed for "
                            f"band {band_num}: {e}"
                        )
            
            # Build response
            elapsed_ms = (time.time() - start_time) * 1000
            response = StatsResponse(
                request=request,
                status=StatsRequestStatus.COMPLETED,
                stats=stats,
                histograms=histograms,
                computation_time_ms=elapsed_ms
            )
            
            # Cache response
            if self._cache_strategy != StatsCacheStrategy.NONE:
                self._response_cache[cache_key] = response
            
            # Invoke callback
            if request.callback:
                request.callback(response)
            
            logger.debug(
                f"[RasterStatsService] Computed stats for {request.layer_id} "
                f"in {elapsed_ms:.1f}ms"
            )
            return response
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            response = StatsResponse(
                request=request,
                status=StatsRequestStatus.FAILED,
                error_message=str(e),
                computation_time_ms=elapsed_ms
            )
            
            logger.error(
                f"[RasterStatsService] Stats computation failed: {e}"
            )
            
            if request.callback:
                request.callback(response)
            
            return response
            
        finally:
            # Remove from pending
            self._pending_requests.pop(request.layer_id, None)
    
    def get_layer_snapshot(
        self,
        layer_id: str
    ) -> Optional[LayerStatsSnapshot]:
        """
        Get a quick snapshot of layer statistics for UI.
        
        Uses cached data if available, otherwise computes.
        
        Args:
            layer_id: Raster layer ID
            
        Returns:
            LayerStatsSnapshot or None if layer invalid
        """
        # Check if layer is valid
        if not self._backend.is_valid(layer_id):
            return None
        
        # Try to get from cache or compute
        request = StatsRequest(
            layer_id=layer_id,
            include_histogram=False,  # Skip histogram for snapshot
            sample_size=1000000  # Sample for speed
        )
        
        response = self.compute_statistics(request)
        
        if not response.is_success or not response.stats:
            return None
        
        stats = response.stats
        
        # Build band summaries
        band_summaries = []
        for band_stats in stats.band_statistics:
            summary = self._format_band_summary(band_stats)
            band_summaries.append(summary)
        
        # Estimate file size (rough approximation)
        bytes_per_pixel = self._estimate_bytes_per_pixel(
            stats.band_statistics[0].data_type if stats.band_statistics else RasterDataType.BYTE
        )
        estimated_size_mb = (
            stats.width * stats.height * stats.band_count * bytes_per_pixel
        ) / (1024 * 1024)
        
        return LayerStatsSnapshot(
            layer_id=layer_id,
            layer_name=stats.layer_name,
            band_count=stats.band_count,
            width=stats.width,
            height=stats.height,
            crs=stats.crs_auth_id,
            extent=stats.extent,
            file_size_mb=round(estimated_size_mb, 2),
            band_summaries=band_summaries,
            renderer_type=stats.renderer_type.name.lower()
        )
    
    def get_band_histogram(
        self,
        layer_id: str,
        band_number: int = 1,
        bin_count: int = 256
    ) -> Optional[HistogramData]:
        """
        Get histogram for a specific band.
        
        Args:
            layer_id: Raster layer ID
            band_number: 1-based band index
            bin_count: Number of histogram bins
            
        Returns:
            HistogramData or None if computation fails
        """
        try:
            return self._backend.get_histogram(
                layer_id=layer_id,
                band_number=band_number,
                bin_count=bin_count
            )
        except Exception as e:
            logger.error(
                f"[RasterStatsService] Histogram failed: {e}"
            )
            return None
    
    # =========================================================================
    # Public API - Pixel Identification
    # =========================================================================
    
    def identify_at_point(
        self,
        layer_id: str,
        x: float,
        y: float,
        crs: Optional[str] = None
    ) -> Optional[PixelIdentifyResult]:
        """
        Identify pixel values at a map location.
        
        Args:
            layer_id: Raster layer ID
            x: X coordinate
            y: Y coordinate
            crs: CRS of coordinates (None = layer CRS)
            
        Returns:
            PixelIdentifyResult or None if invalid
        """
        try:
            return self._backend.identify_pixel(
                layer_id=layer_id,
                x=x,
                y=y,
                crs_auth_id=crs
            )
        except Exception as e:
            logger.error(
                f"[RasterStatsService] Identify failed: {e}"
            )
            return None
    
    # =========================================================================
    # Public API - Transparency
    # =========================================================================
    
    def set_layer_opacity(
        self,
        layer_id: str,
        opacity: float
    ) -> bool:
        """
        Set layer opacity.
        
        Args:
            layer_id: Raster layer ID
            opacity: Opacity value (0.0-1.0)
            
        Returns:
            True if successfully applied
        """
        return self._backend.set_opacity(layer_id, opacity)
    
    def get_layer_opacity(
        self,
        layer_id: str
    ) -> float:
        """
        Get current layer opacity.
        
        Args:
            layer_id: Raster layer ID
            
        Returns:
            Current opacity (0.0-1.0)
        """
        settings = self._backend.get_transparency_settings(layer_id)
        return settings.global_opacity
    
    # =========================================================================
    # Public API - Validation
    # =========================================================================
    
    def is_layer_valid(self, layer_id: str) -> bool:
        """Check if layer is valid for statistics."""
        return self._backend.is_valid(layer_id)
    
    def supports_statistics(self, layer_id: str) -> bool:
        """Check if layer supports statistics computation."""
        return self._backend.supports_statistics(layer_id)
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def clear_cache(self, layer_id: Optional[str] = None) -> None:
        """
        Clear statistics cache.
        
        Args:
            layer_id: Specific layer to clear (None = all)
        """
        if layer_id:
            keys_to_remove = [
                k for k in self._response_cache
                if k.startswith(layer_id)
            ]
            for key in keys_to_remove:
                del self._response_cache[key]
            
            # Also clear dedicated cache
            if self._stats_cache:
                self._stats_cache.invalidate_layer(layer_id)
            
            logger.debug(
                f"[RasterStatsService] Cleared cache for {layer_id}"
            )
        else:
            self._response_cache.clear()
            if self._stats_cache:
                self._stats_cache.clear()
            logger.debug("[RasterStatsService] Cleared all cache")
    
    def invalidate_cache(self, layer_id: str) -> None:
        """
        Invalidate cache for a specific layer.
        
        Alias for clear_cache(layer_id) for API compatibility.
        
        Args:
            layer_id: Layer to invalidate
        """
        self.clear_cache(layer_id)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        return {
            'cached_layers': len(self._response_cache),
            'pending_requests': len(self._pending_requests)
        }
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _get_cache_key(self, request: StatsRequest) -> str:
        """Generate cache key for request."""
        bands_str = ','.join(map(str, request.bands)) if request.bands else 'all'
        return f"{request.layer_id}_{bands_str}_{request.sample_size}"
    
    def _format_band_summary(
        self,
        stats: BandStatistics
    ) -> BandSummary:
        """
        Format band statistics for UI display.
        
        Args:
            stats: Raw band statistics
            
        Returns:
            BandSummary with formatted strings
        """
        # Format based on data type
        is_float = stats.data_type in (
            RasterDataType.FLOAT32,
            RasterDataType.FLOAT64,
            RasterDataType.CFLOAT32,
            RasterDataType.CFLOAT64
        )
        
        if is_float:
            fmt = lambda v: f"{v:.4f}" if v is not None else "N/A"
        else:
            fmt = lambda v: f"{v:.2f}" if v is not None else "N/A"
        
        return BandSummary(
            band_number=stats.band_number,
            min_value=fmt(stats.min_value),
            max_value=fmt(stats.max_value),
            mean=fmt(stats.mean),
            std_dev=fmt(stats.std_dev),
            no_data=fmt(stats.no_data_value) if stats.has_no_data else "None",
            data_type=stats.data_type.name,
            null_percent=f"{stats.null_percentage:.1f}%"
        )
    
    def _estimate_bytes_per_pixel(
        self,
        data_type: RasterDataType
    ) -> int:
        """Estimate bytes per pixel for data type."""
        byte_sizes = {
            RasterDataType.BYTE: 1,
            RasterDataType.INT16: 2,
            RasterDataType.UINT16: 2,
            RasterDataType.INT32: 4,
            RasterDataType.UINT32: 4,
            RasterDataType.FLOAT32: 4,
            RasterDataType.FLOAT64: 8,
            RasterDataType.CINT16: 4,
            RasterDataType.CINT32: 8,
            RasterDataType.CFLOAT32: 8,
            RasterDataType.CFLOAT64: 16,
        }
        return byte_sizes.get(data_type, 1)


# =============================================================================
# Factory Function
# =============================================================================

_default_service: Optional[RasterStatsService] = None


def get_raster_stats_service(
    backend: Optional[RasterPort] = None
) -> RasterStatsService:
    """
    Get the default RasterStatsService instance.
    
    Args:
        backend: Optional backend to use (creates default if None)
        
    Returns:
        RasterStatsService singleton instance
    """
    global _default_service
    
    if _default_service is None:
        if backend is None:
            # Import here to avoid circular imports
            from adapters.backends import get_qgis_raster_backend
            backend = get_qgis_raster_backend()
        _default_service = RasterStatsService(backend)
    
    return _default_service


def reset_raster_stats_service() -> None:
    """Reset the default service instance (for testing)."""
    global _default_service
    _default_service = None
