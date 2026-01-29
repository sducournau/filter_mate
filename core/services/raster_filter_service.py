# -*- coding: utf-8 -*-
"""
Raster Filter Service.

EPIC-3: Raster-Vector Integration
US-R2V-01: Raster as Filter Source

This service orchestrates raster-based filtering operations,
implementing the business logic for:
- Filtering vector features by raster values
- Creating value-based masks for visualization
- Computing zonal statistics
- Managing raster filter context state

Architecture:
- Uses RasterFilterPort for backend operations (QGIS/GDAL)
- Emits signals for UI updates
- Integrates with FilteringController for FILTERING tab

Author: FilterMate Team
Date: January 2026
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any, Callable

try:
    from qgis.PyQt.QtCore import QObject, pyqtSignal
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    # Fallback for testing without QGIS
    class QObject:
        pass
    
    def pyqtSignal(*args):
        return None

from ..ports.raster_filter_port import (
    RasterFilterPort,
    RasterValuePredicate,
    SamplingMethod,
    RasterOperation,
    RasterSampleResult,
    RasterFilterResult,
    RasterMaskResult,
    ZonalStatisticsResult
)


logger = logging.getLogger("FilterMate.RasterFilterService")


# =============================================================================
# State Management
# =============================================================================

class RasterFilterMode(Enum):
    """
    Active raster filter mode.
    
    EPIC-3: Defines the current operational mode of the service.
    """
    IDLE = auto()                  # No active raster filter
    SINGLE_VALUE = auto()          # Filter by single value
    VALUE_RANGE = auto()           # Filter by value range
    MULTI_RANGE = auto()           # Filter by multiple ranges
    NODATA = auto()                # Filter by NoData status
    ZONAL_STATS = auto()           # Computing zonal statistics


@dataclass
class RasterFilterContext:
    """
    Current state of raster filter configuration.
    
    EPIC-3: Captures all parameters for the active raster filter.
    
    Attributes:
        raster_layer_id: ID of the source raster layer
        raster_layer_name: Display name of raster
        band: Active band number
        band_name: Display name of band
        mode: Current filter mode
        predicate: Value comparison predicate
        min_value: Minimum value for range filters
        max_value: Maximum value for range filters
        single_value: Value for exact match filters
        tolerance: Tolerance for value matching (default 0.01)
        sampling_method: How to sample at features
        active_ranges: List of (min, max) tuples for multi-range
        invert: If True, invert the filter result
        target_layers: List of vector layer IDs to filter
        source_geometry_wkt: Optional source geometry for spatial constraint
    """
    raster_layer_id: str = ""
    raster_layer_name: str = ""
    band: int = 1
    band_name: str = "Band 1"
    mode: RasterFilterMode = RasterFilterMode.IDLE
    predicate: RasterValuePredicate = RasterValuePredicate.WITHIN_RANGE
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    single_value: Optional[float] = None
    tolerance: float = 0.01
    sampling_method: SamplingMethod = SamplingMethod.CENTROID
    active_ranges: List[Tuple[float, float]] = field(default_factory=list)
    invert: bool = False
    target_layers: List[str] = field(default_factory=list)
    source_geometry_wkt: Optional[str] = None
    
    @property
    def is_configured(self) -> bool:
        """Check if context has minimum required configuration."""
        return bool(self.raster_layer_id) and self.mode != RasterFilterMode.IDLE
    
    @property
    def has_value_criteria(self) -> bool:
        """Check if value criteria are set."""
        if self.mode == RasterFilterMode.SINGLE_VALUE:
            return self.single_value is not None
        elif self.mode == RasterFilterMode.VALUE_RANGE:
            return self.min_value is not None and self.max_value is not None
        elif self.mode == RasterFilterMode.MULTI_RANGE:
            return len(self.active_ranges) > 0
        elif self.mode == RasterFilterMode.NODATA:
            return True  # NoData doesn't need values
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            'raster_layer_id': self.raster_layer_id,
            'raster_layer_name': self.raster_layer_name,
            'band': self.band,
            'band_name': self.band_name,
            'mode': self.mode.name,
            'predicate': self.predicate.name,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'single_value': self.single_value,
            'tolerance': self.tolerance,
            'sampling_method': self.sampling_method.name,
            'active_ranges': self.active_ranges,
            'invert': self.invert,
            'target_layers': self.target_layers,
            'source_geometry_wkt': self.source_geometry_wkt
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RasterFilterContext':
        """Create context from dictionary."""
        ctx = cls()
        ctx.raster_layer_id = data.get('raster_layer_id', '')
        ctx.raster_layer_name = data.get('raster_layer_name', '')
        ctx.band = data.get('band', 1)
        ctx.band_name = data.get('band_name', 'Band 1')
        ctx.mode = RasterFilterMode[data.get('mode', 'IDLE')]
        ctx.predicate = RasterValuePredicate[data.get('predicate', 'WITHIN_RANGE')]
        ctx.min_value = data.get('min_value')
        ctx.max_value = data.get('max_value')
        ctx.single_value = data.get('single_value')
        ctx.tolerance = data.get('tolerance', 0.01)
        ctx.sampling_method = SamplingMethod[data.get('sampling_method', 'CENTROID')]
        ctx.active_ranges = data.get('active_ranges', [])
        ctx.invert = data.get('invert', False)
        ctx.target_layers = data.get('target_layers', [])
        ctx.source_geometry_wkt = data.get('source_geometry_wkt')
        return ctx


# =============================================================================
# Service Implementation
# =============================================================================

class RasterFilterService(QObject if HAS_QGIS else object):
    """
    Service for raster-based filtering operations.
    
    EPIC-3: Raster-Vector Integration
    
    This service:
    1. Manages raster filter context state
    2. Orchestrates filtering operations via RasterFilterPort
    3. Emits signals for UI updates
    4. Handles batch operations on multiple target layers
    
    Signals:
        context_changed: Emitted when filter context changes
        filter_started: Emitted when a filter operation starts
        filter_progress: Emitted with progress updates (0-100)
        filter_completed: Emitted with RasterFilterResult
        filter_error: Emitted with error message
        mask_created: Emitted when a value mask is created
        zonal_stats_completed: Emitted with zonal statistics results
    """
    
    # Qt Signals (only if QGIS is available)
    if HAS_QGIS:
        context_changed = pyqtSignal(dict)  # RasterFilterContext.to_dict()
        filter_started = pyqtSignal(str)    # operation description
        filter_progress = pyqtSignal(int)   # 0-100
        filter_completed = pyqtSignal(object)  # RasterFilterResult
        filter_error = pyqtSignal(str)      # error message
        mask_created = pyqtSignal(object)   # RasterMaskResult
        zonal_stats_completed = pyqtSignal(list)  # List[ZonalStatisticsResult]
    
    def __init__(self, backend: Optional[RasterFilterPort] = None):
        """
        Initialize the service.
        
        Args:
            backend: Optional RasterFilterPort implementation.
                     If None, use default QGIS backend.
        """
        if HAS_QGIS:
            super().__init__()
        
        self._backend = backend
        self._context = RasterFilterContext()
        self._last_result: Optional[RasterFilterResult] = None
        self._operation_cancelled = False
        
        # Progress callback for long operations
        self._progress_callback: Optional[Callable[[int], None]] = None
        
        logger.info("RasterFilterService initialized")
    
    # =========================================================================
    # Backend Management
    # =========================================================================
    
    def set_backend(self, backend: RasterFilterPort) -> None:
        """
        Set the backend implementation.
        
        Args:
            backend: RasterFilterPort implementation
        """
        self._backend = backend
        logger.debug(f"Backend set to: {type(backend).__name__}")
    
    def get_backend(self) -> Optional[RasterFilterPort]:
        """Get the current backend."""
        return self._backend
    
    def _ensure_backend(self) -> RasterFilterPort:
        """
        Ensure a backend is available, raising if not.
        
        Returns:
            The configured backend
        
        Raises:
            RuntimeError: If no backend is configured
        """
        if self._backend is None:
            raise RuntimeError(
                "No RasterFilterPort backend configured. "
                "Call set_backend() or provide backend in constructor."
            )
        return self._backend
    
    # =========================================================================
    # Context Management
    # =========================================================================
    
    @property
    def context(self) -> RasterFilterContext:
        """Get the current filter context."""
        return self._context
    
    def update_context(self, **kwargs) -> None:
        """
        Update filter context with new values.
        
        Emits context_changed signal after update.
        
        Args:
            **kwargs: Context attributes to update
        """
        changed = False
        
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                current = getattr(self._context, key)
                if current != value:
                    setattr(self._context, key, value)
                    changed = True
                    logger.debug(f"Context.{key} = {value}")
            else:
                logger.warning(f"Unknown context attribute: {key}")
        
        if changed and HAS_QGIS:
            self.context_changed.emit(self._context.to_dict())
    
    def set_raster_source(
        self,
        layer_id: str,
        layer_name: str = "",
        band: int = 1,
        band_name: str = ""
    ) -> None:
        """
        Set the raster layer source for filtering.
        
        Args:
            layer_id: QGIS layer ID
            layer_name: Display name
            band: Band number (1-indexed)
            band_name: Display name for band
        """
        self.update_context(
            raster_layer_id=layer_id,
            raster_layer_name=layer_name,
            band=band,
            band_name=band_name or f"Band {band}"
        )
        logger.info(f"Raster source set: {layer_name} ({layer_id}), band {band}")
    
    def set_value_range(
        self,
        min_value: float,
        max_value: float,
        predicate: RasterValuePredicate = RasterValuePredicate.WITHIN_RANGE
    ) -> None:
        """
        Set value range for filtering.
        
        Args:
            min_value: Minimum value
            max_value: Maximum value
            predicate: WITHIN_RANGE or OUTSIDE_RANGE
        """
        self.update_context(
            mode=RasterFilterMode.VALUE_RANGE,
            min_value=min_value,
            max_value=max_value,
            predicate=predicate
        )
        logger.info(f"Value range set: [{min_value}, {max_value}] ({predicate.name})")
    
    def set_single_value(
        self,
        value: float,
        tolerance: float = 0.01
    ) -> None:
        """
        Set single value for exact match filtering.
        
        Args:
            value: Target value
            tolerance: Acceptable tolerance (default 0.01)
        """
        self.update_context(
            mode=RasterFilterMode.SINGLE_VALUE,
            single_value=value,
            tolerance=tolerance,
            predicate=RasterValuePredicate.EQUALS_VALUE
        )
        logger.info(f"Single value set: {value} (±{tolerance})")
    
    def set_nodata_filter(self, include_nodata: bool = False) -> None:
        """
        Set filter to include/exclude NoData pixels.
        
        Args:
            include_nodata: If True, filter TO NoData; if False, filter AWAY from NoData
        """
        predicate = (
            RasterValuePredicate.IS_NODATA if include_nodata 
            else RasterValuePredicate.IS_NOT_NODATA
        )
        self.update_context(
            mode=RasterFilterMode.NODATA,
            predicate=predicate
        )
        logger.info(f"NoData filter set: include_nodata={include_nodata}")
    
    def add_target_layer(self, layer_id: str) -> None:
        """
        Add a target vector layer for filtering.
        
        Args:
            layer_id: QGIS layer ID
        """
        if layer_id not in self._context.target_layers:
            new_targets = self._context.target_layers + [layer_id]
            self.update_context(target_layers=new_targets)
            logger.debug(f"Target layer added: {layer_id}")
    
    def remove_target_layer(self, layer_id: str) -> None:
        """
        Remove a target vector layer.
        
        Args:
            layer_id: QGIS layer ID
        """
        if layer_id in self._context.target_layers:
            new_targets = [lid for lid in self._context.target_layers if lid != layer_id]
            self.update_context(target_layers=new_targets)
            logger.debug(f"Target layer removed: {layer_id}")
    
    def set_target_layers(self, layer_ids: List[str]) -> None:
        """
        Set all target layers at once.
        
        Args:
            layer_ids: List of QGIS layer IDs
        """
        self.update_context(target_layers=list(layer_ids))
        logger.info(f"Target layers set: {len(layer_ids)} layers")
    
    def clear_context(self) -> None:
        """Reset context to initial state."""
        self._context = RasterFilterContext()
        if HAS_QGIS:
            self.context_changed.emit(self._context.to_dict())
        logger.info("Context cleared")
    
    # =========================================================================
    # Filtering Operations
    # =========================================================================
    
    def filter_features(
        self,
        vector_layer_id: Optional[str] = None,
        feature_ids: Optional[List[int]] = None
    ) -> RasterFilterResult:
        """
        Filter vector features by current raster context.
        
        Uses the current context configuration to filter features
        in the specified (or all target) vector layers.
        
        Args:
            vector_layer_id: Optional specific layer to filter.
                            If None, uses all target_layers from context.
            feature_ids: Optional specific features to evaluate.
        
        Returns:
            RasterFilterResult with matching features
        
        Raises:
            ValueError: If context is not properly configured
            RuntimeError: If no backend is configured
        """
        # Validate context
        if not self._context.is_configured:
            raise ValueError(
                "Filter context not configured. "
                "Set raster source and filter mode first."
            )
        
        if not self._context.has_value_criteria:
            raise ValueError(
                "No value criteria set. "
                "Call set_value_range(), set_single_value(), or set_nodata_filter()."
            )
        
        backend = self._ensure_backend()
        
        # Determine target layers
        target_ids = [vector_layer_id] if vector_layer_id else self._context.target_layers
        if not target_ids:
            raise ValueError("No target layers specified.")
        
        # Emit start signal
        if HAS_QGIS:
            self.filter_started.emit(
                f"Filtering {len(target_ids)} layer(s) by raster values"
            )
        
        logger.info(
            f"Starting raster filter: {self._context.raster_layer_name}, "
            f"band {self._context.band}, {self._context.predicate.name}"
        )
        
        # Prepare value parameters
        min_val = self._context.min_value
        max_val = self._context.max_value
        
        if self._context.mode == RasterFilterMode.SINGLE_VALUE:
            # Convert single value to range with tolerance
            min_val = self._context.single_value - self._context.tolerance
            max_val = self._context.single_value + self._context.tolerance
        
        # Aggregate results from all target layers
        all_matching_ids: List[int] = []
        total_features = 0
        
        for i, layer_id in enumerate(target_ids):
            try:
                result = backend.filter_features_by_value(
                    raster_layer_id=self._context.raster_layer_id,
                    vector_layer_id=layer_id,
                    band=self._context.band,
                    predicate=self._context.predicate,
                    min_value=min_val,
                    max_value=max_val,
                    method=self._context.sampling_method,
                    feature_ids=feature_ids
                )
                
                all_matching_ids.extend(result.matching_feature_ids)
                total_features += result.total_features
                
                # Progress update
                progress = int(((i + 1) / len(target_ids)) * 100)
                if HAS_QGIS:
                    self.filter_progress.emit(progress)
                
            except Exception as e:
                logger.error(f"Filter error on layer {layer_id}: {e}")
                if HAS_QGIS:
                    self.filter_error.emit(f"Error filtering layer: {str(e)}")
                continue
        
        # Invert if requested
        if self._context.invert:
            # Note: inversion needs feature IDs from all layers
            # This is a simplified version - full inversion requires layer access
            logger.warning("Invert mode requires feature iteration - simplified result")
        
        # Build aggregated result
        aggregated_result = RasterFilterResult(
            matching_feature_ids=all_matching_ids,
            total_features=total_features,
            matching_count=len(all_matching_ids),
            predicate=self._context.predicate,
            value_range=(min_val or 0.0, max_val or 0.0),
            band=self._context.band,
            sampling_method=self._context.sampling_method
        )
        
        self._last_result = aggregated_result
        
        logger.info(
            f"Filter complete: {aggregated_result.matching_count}/{aggregated_result.total_features} "
            f"features ({aggregated_result.match_percentage:.1f}%)"
        )
        
        if HAS_QGIS:
            self.filter_completed.emit(aggregated_result)
        
        return aggregated_result
    
    def sample_at_features(
        self,
        vector_layer_id: str,
        feature_ids: Optional[List[int]] = None
    ) -> List[RasterSampleResult]:
        """
        Sample raster values at vector feature locations.
        
        Args:
            vector_layer_id: ID of the vector layer
            feature_ids: Optional specific feature IDs
        
        Returns:
            List of RasterSampleResult for each feature
        """
        if not self._context.raster_layer_id:
            raise ValueError("No raster source configured.")
        
        backend = self._ensure_backend()
        
        return backend.sample_at_features(
            raster_layer_id=self._context.raster_layer_id,
            vector_layer_id=vector_layer_id,
            band=self._context.band,
            method=self._context.sampling_method,
            feature_ids=feature_ids
        )
    
    # =========================================================================
    # Mask Operations
    # =========================================================================
    
    def create_value_mask(
        self,
        output_name: Optional[str] = None,
        invert: bool = False
    ) -> RasterMaskResult:
        """
        Create a binary mask based on current value criteria.
        
        Args:
            output_name: Optional name for output layer
            invert: If True, mask values WITHIN range
        
        Returns:
            RasterMaskResult describing created mask
        """
        if not self._context.is_configured:
            raise ValueError("Filter context not configured.")
        
        if not self._context.has_value_criteria:
            raise ValueError("No value criteria set.")
        
        backend = self._ensure_backend()
        
        min_val = self._context.min_value
        max_val = self._context.max_value
        
        if self._context.mode == RasterFilterMode.SINGLE_VALUE:
            min_val = self._context.single_value - self._context.tolerance
            max_val = self._context.single_value + self._context.tolerance
        
        result = backend.generate_value_mask(
            raster_layer_id=self._context.raster_layer_id,
            band=self._context.band,
            min_value=min_val,
            max_value=max_val,
            output_name=output_name,
            invert=invert or self._context.invert
        )
        
        logger.info(
            f"Mask created: {result.layer_name}, "
            f"{result.mask_percentage:.1f}% masked"
        )
        
        if HAS_QGIS:
            self.mask_created.emit(result)
        
        return result
    
    # =========================================================================
    # Zonal Statistics
    # =========================================================================
    
    def compute_zonal_statistics(
        self,
        vector_layer_id: str,
        statistics: Optional[List[str]] = None,
        feature_ids: Optional[List[int]] = None
    ) -> List[ZonalStatisticsResult]:
        """
        Compute zonal statistics for raster within vector zones.
        
        Args:
            vector_layer_id: ID of the zone layer
            statistics: List of stats to compute (default all)
            feature_ids: Optional specific zone feature IDs
        
        Returns:
            List of ZonalStatisticsResult for each zone
        """
        if not self._context.raster_layer_id:
            raise ValueError("No raster source configured.")
        
        self.update_context(mode=RasterFilterMode.ZONAL_STATS)
        
        backend = self._ensure_backend()
        
        results = backend.compute_zonal_statistics(
            raster_layer_id=self._context.raster_layer_id,
            vector_layer_id=vector_layer_id,
            band=self._context.band,
            statistics=statistics or ['min', 'max', 'mean', 'std', 'count'],
            feature_ids=feature_ids
        )
        
        logger.info(f"Zonal statistics computed for {len(results)} zones")
        
        if HAS_QGIS:
            self.zonal_stats_completed.emit(results)
        
        return results
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_last_result(self) -> Optional[RasterFilterResult]:
        """Get the last filter result."""
        return self._last_result
    
    def cancel_operation(self) -> None:
        """Cancel the current operation."""
        self._operation_cancelled = True
        logger.info("Operation cancelled")
    
    def is_ready(self) -> bool:
        """
        Check if service is ready to perform filtering.
        
        Returns:
            True if backend and context are configured
        """
        return (
            self._backend is not None and
            self._context.is_configured and
            self._context.has_value_criteria
        )
    
    def get_status_summary(self) -> str:
        """
        Get a human-readable status summary.
        
        Returns:
            Status string describing current configuration
        """
        if not self._context.raster_layer_id:
            return "No raster source selected"
        
        status_parts = [
            f"Source: {self._context.raster_layer_name}",
            f"Band: {self._context.band_name}",
            f"Mode: {self._context.mode.name}"
        ]
        
        if self._context.mode == RasterFilterMode.VALUE_RANGE:
            status_parts.append(
                f"Range: [{self._context.min_value}, {self._context.max_value}]"
            )
        elif self._context.mode == RasterFilterMode.SINGLE_VALUE:
            status_parts.append(
                f"Value: {self._context.single_value} (±{self._context.tolerance})"
            )
        
        if self._context.target_layers:
            status_parts.append(f"Targets: {len(self._context.target_layers)} layers")
        
        return " | ".join(status_parts)
