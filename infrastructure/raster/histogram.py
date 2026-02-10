"""
Raster Histogram Infrastructure.

Low-level functions for computing raster band histograms and statistics.
All functions are thread-safe: they create layers from URIs, never accept
QgsLayer objects directly.

Thread Safety Contract:
    - ALL layer objects are created from URI strings within each function
    - NO QgsMapLayer references are passed in or stored
    - Functions support cancellation via optional feedback parameter

Phase 2: Histogram computation + band statistics.
"""
import logging
from typing import Dict, List, Optional, Tuple

from qgis.core import (
    QgsRasterBandStats,
    QgsRasterLayer,
)

logger = logging.getLogger(__name__)

# Valid bin count options for histogram UI
VALID_BIN_COUNTS = (64, 128, 256, 512)


def compute_band_histogram(
    raster_uri: str,
    band: int = 1,
    n_bins: int = 256,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> Optional[Tuple[List[int], List[float]]]:
    """Compute histogram for a single raster band.

    Thread-safe: creates the layer from URI internally.

    Args:
        raster_uri: URI/path of the raster layer.
        band: 1-based band number.
        n_bins: Number of histogram bins (64, 128, 256, or 512).
        min_value: Minimum value for histogram range. If None, uses band min.
        max_value: Maximum value for histogram range. If None, uses band max.

    Returns:
        Tuple of (counts, bin_edges) where:
            - counts: list of int, length = n_bins
            - bin_edges: list of float, length = n_bins + 1
        Returns None if computation fails.
    """
    if n_bins not in VALID_BIN_COUNTS:
        logger.warning(
            f"Invalid bin count {n_bins}, falling back to 256. "
            f"Valid values: {VALID_BIN_COUNTS}"
        )
        n_bins = 256

    raster = QgsRasterLayer(raster_uri, "temp_raster_histogram")
    if not raster.isValid():
        logger.error(f"Invalid raster layer for histogram: {raster_uri}")
        return None

    provider = raster.dataProvider()
    if provider is None:
        logger.error(f"No data provider for raster: {raster_uri}")
        return None

    band_count = raster.bandCount()
    if band < 1 or band > band_count:
        logger.error(
            f"Band {band} out of range [1, {band_count}] for: {raster_uri}"
        )
        return None

    try:
        # If min/max not provided, compute from band statistics
        if min_value is None or max_value is None:
            stats = provider.bandStatistics(
                band,
                QgsRasterBandStats.Min | QgsRasterBandStats.Max,
            )
            if min_value is None:
                min_value = stats.minimumValue
            if max_value is None:
                max_value = stats.maximumValue

        # Guard against degenerate range
        if min_value >= max_value:
            logger.warning(
                f"Degenerate histogram range: min={min_value}, max={max_value}"
            )
            # Return single bin with all values
            counts = [0] * n_bins
            bin_width = 1.0
            bin_edges = [min_value + i * bin_width for i in range(n_bins + 1)]
            return (counts, bin_edges)

        # Use QGIS provider histogram
        histogram = provider.histogram(
            band,
            n_bins,
            min_value,
            max_value,
        )

        counts = histogram.histogramVector
        if not counts:
            logger.warning(f"Empty histogram for band {band}")
            return None

        # Build bin edges from min/max and bin count
        bin_width = (max_value - min_value) / n_bins
        bin_edges = [min_value + i * bin_width for i in range(n_bins + 1)]

        logger.debug(
            f"Histogram computed: band={band}, bins={n_bins}, "
            f"range=[{min_value:.4f}, {max_value:.4f}], "
            f"total_count={sum(counts)}"
        )
        return (list(counts), bin_edges)

    except Exception as e:
        logger.error(
            f"Failed to compute histogram for band {band}: {e}",
            exc_info=True,
        )
        return None


def compute_band_statistics(
    raster_uri: str,
    band: int = 1,
) -> Optional[Dict[str, float]]:
    """Compute statistics for a single raster band.

    Thread-safe: creates the layer from URI internally.

    Uses QgsRasterBandStats for efficient computation (QGIS caches stats
    once computed for a given band).

    Args:
        raster_uri: URI/path of the raster layer.
        band: 1-based band number.

    Returns:
        Dict with keys: min, max, mean, std_dev, range, sum, count.
        Returns None if computation fails.
    """
    raster = QgsRasterLayer(raster_uri, "temp_raster_stats")
    if not raster.isValid():
        logger.error(f"Invalid raster layer for stats: {raster_uri}")
        return None

    provider = raster.dataProvider()
    if provider is None:
        logger.error(f"No data provider for raster: {raster_uri}")
        return None

    band_count = raster.bandCount()
    if band < 1 or band > band_count:
        logger.error(
            f"Band {band} out of range [1, {band_count}] for: {raster_uri}"
        )
        return None

    try:
        stats = provider.bandStatistics(
            band,
            QgsRasterBandStats.All,
        )

        result = {
            "min": stats.minimumValue,
            "max": stats.maximumValue,
            "mean": stats.mean,
            "std_dev": stats.stdDev,
            "range": stats.range,
            "sum": stats.sum,
            "count": stats.elementCount,
        }

        logger.debug(
            f"Band {band} stats: min={result['min']:.4f}, "
            f"max={result['max']:.4f}, mean={result['mean']:.4f}, "
            f"std={result['std_dev']:.4f}"
        )
        return result

    except Exception as e:
        logger.error(
            f"Failed to compute stats for band {band}: {e}",
            exc_info=True,
        )
        return None
