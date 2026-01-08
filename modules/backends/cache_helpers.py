# -*- coding: utf-8 -*-
"""
Cache Helpers for FilterMate Backends

v2.8.6: Extracted from OGR and Spatialite backends to reduce code duplication.

This module provides shared functions for multi-step filter cache operations,
ensuring consistent behavior across all backends.
"""

from typing import List, Optional, Set, Tuple, Any, Dict, Callable

# QGIS imports - graceful degradation if not available (for testing)
try:
    from qgis.core import QgsVectorLayer, QgsMessageLog, Qgis
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = Any  # type: ignore
    QgsMessageLog = None
    Qgis = None

# Import cache functions with availability check
try:
    from .spatialite_cache import (
        store_filter_fids,
        intersect_filter_fids,
        get_previous_filter_fids
    )
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    store_filter_fids = None
    intersect_filter_fids = None
    get_previous_filter_fids = None

# Import clean_buffer_value for consistent precision
try:
    from ..appUtils import clean_buffer_value
except ImportError:
    def clean_buffer_value(val: float, decimals: int = 6) -> float:
        """Fallback: Round to 6 decimal places."""
        return round(float(val), decimals) if val else 0.0


class CacheOperationResult:
    """
    Result of a cache operation for multi-step filtering.
    
    Attributes:
        matching_fids: Set of FIDs after cache operation (intersection or original)
        step_number: Current step number in multi-step chain
        cache_key: Key used for cache storage (None if not stored)
        was_intersected: True if cache intersection was performed
        operator_used: Operator used ('AND', 'OR', 'NOT AND', or None)
        error: Error message if operation failed (None on success)
    """
    
    def __init__(
        self,
        matching_fids: Set[int],
        step_number: int = 1,
        cache_key: Optional[str] = None,
        was_intersected: bool = False,
        operator_used: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.matching_fids = matching_fids
        self.step_number = step_number
        self.cache_key = cache_key
        self.was_intersected = was_intersected
        self.operator_used = operator_used
        self.error = error
    
    @property
    def fid_count(self) -> int:
        """Number of FIDs in result."""
        return len(self.matching_fids)
    
    @property
    def fid_list(self) -> List[int]:
        """FIDs as list for compatibility."""
        return list(self.matching_fids)
    
    @property
    def success(self) -> bool:
        """True if operation succeeded without errors."""
        return self.error is None


def perform_cache_intersection(
    layer: QgsVectorLayer,
    matching_fids: List[int],
    source_wkt: str,
    buffer_value: float,
    predicates_list: List[str],
    old_subset: Optional[str],
    combine_operator: Optional[str],
    logger: Optional[Any] = None,
    backend_name: str = "Backend"
) -> CacheOperationResult:
    """
    Perform multi-step cache operation for filter chaining.
    
    v2.8.6: Shared implementation extracted from OGR and Spatialite backends.
    v2.8.7: Full operator support (AND, OR, NOT AND).
    
    This function handles the complete cache operation workflow:
    1. Check if cache is available
    2. Get previous FIDs from cache
    3. Apply operator-specific set operation
    4. Return result with step tracking
    
    Supported operators:
        - AND (default): Intersection - keep FIDs matching BOTH filters
          Result = new_fids ∩ previous_fids
        - OR: Union - keep FIDs matching EITHER filter
          Result = new_fids ∪ previous_fids
        - NOT AND: Difference - keep previous FIDs NOT matching new filter
          Result = previous_fids - new_fids (excludes new matches)
    
    Args:
        layer: Target QGIS layer
        matching_fids: List of FIDs from current filter operation
        source_wkt: WKT of source geometry
        buffer_value: Buffer distance (already cleaned via clean_buffer_value)
        predicates_list: List of predicate names (e.g., ['intersects'])
        old_subset: Previous subset string (None if no previous filter)
        combine_operator: Operator to combine filters ('AND', 'OR', 'NOT AND', or None)
        logger: Optional logger instance with log_info/log_warning methods
        backend_name: Name of calling backend for log messages
    
    Returns:
        CacheOperationResult with operation results
    
    Example:
        # AND intersection
        result = perform_cache_intersection(
            layer=target_layer,
            matching_fids=[1, 2, 3, 4, 5],
            source_wkt="POLYGON((...))",
            buffer_value=100.0,
            predicates_list=['intersects'],
            old_subset="fid IN (2, 3, 4)",
            combine_operator="AND",
            logger=self,
            backend_name="OGRBackend"
        )
        
        if result.was_intersected:
            print(f"Step {result.step_number}: {result.fid_count} FIDs after intersection")
    """
    
    def log_info(msg: str):
        if logger and hasattr(logger, 'log_info'):
            logger.log_info(msg)
    
    def log_warning(msg: str):
        if logger and hasattr(logger, 'log_warning'):
            logger.log_warning(msg)
    
    def log_debug(msg: str):
        if logger and hasattr(logger, 'log_debug'):
            logger.log_debug(msg)
    
    # Initialize result with original FIDs
    result = CacheOperationResult(
        matching_fids=set(matching_fids),
        step_number=1,
        operator_used=combine_operator
    )
    
    # Check cache availability
    if not CACHE_AVAILABLE or not intersect_filter_fids:
        log_debug(f"[{backend_name}] Cache not available for multi-step")
        return result
    
    # No previous subset = first filter, no intersection needed
    if not old_subset:
        log_debug(f"[{backend_name}] No old_subset, first filter step")
        return result
    
    # Clean buffer value for consistent cache matching
    buffer_val = clean_buffer_value(buffer_value)
    
    # v2.8.7: Full operator support for multi-step cache operations
    # AND: intersection (new ∩ previous) - keep only FIDs that match both
    # OR: union (new ∪ previous) - keep FIDs that match either
    # NOT AND: difference (previous - new) - keep previous FIDs that don't match new filter
    
    try:
        previous_fids = get_previous_filter_fids(
            layer, source_wkt, buffer_val, predicates_list
        )
        
        if previous_fids is not None:
            original_count = len(matching_fids)
            new_fids_set = set(matching_fids)
            
            # Apply operator-specific set operation
            if combine_operator == 'OR':
                # Union: keep FIDs matching either filter
                combined_fids = new_fids_set | previous_fids
                operation_symbol = "∪"
                log_info(
                    f"  🔄 Multi-step UNION: {original_count} ∪ "
                    f"{len(previous_fids)} = {len(combined_fids)}"
                )
                
            elif combine_operator == 'NOT AND':
                # Difference: keep previous FIDs that DON'T match new filter
                # This is "A AND NOT B" logic
                combined_fids = previous_fids - new_fids_set
                operation_symbol = "-"
                log_info(
                    f"  🔄 Multi-step DIFFERENCE: {len(previous_fids)} - "
                    f"{original_count} = {len(combined_fids)}"
                )
                
            else:
                # Default AND: Intersection - keep only FIDs matching both
                matching_fids_set, step_number_cache = intersect_filter_fids(
                    layer, new_fids_set, source_wkt, buffer_val, predicates_list
                )
                combined_fids = matching_fids_set
                operation_symbol = "∩"
                result.step_number = step_number_cache
                log_info(
                    f"  🔄 Multi-step INTERSECTION: {original_count} ∩ "
                    f"{len(previous_fids)} = {len(combined_fids)}"
                )
            
            result.matching_fids = combined_fids
            result.was_intersected = True
            result.operator_used = combine_operator
            
            if QGIS_AVAILABLE and QgsMessageLog:
                QgsMessageLog.logMessage(
                    f"  → {backend_name} Multi-step step {result.step_number}: "
                    f"{original_count} {operation_symbol} {len(previous_fids)} = {len(combined_fids)} FIDs",
                    "FilterMate", Qgis.Info
                )
        else:
            log_debug(f"[{backend_name}] No previous cache found for multi-step operation")
            
    except Exception as e:
        log_debug(f"[{backend_name}] Cache operation failed (non-fatal): {e}")
        result.error = str(e)
    
    return result


def store_filter_result(
    layer: QgsVectorLayer,
    matching_fids: List[int],
    source_wkt: str,
    buffer_value: float,
    predicates_list: List[str],
    step_number: int = 1,
    logger: Optional[Any] = None,
    backend_name: str = "Backend"
) -> Optional[str]:
    """
    Store filter results in cache for future multi-step operations.
    
    v2.8.6: Shared implementation extracted from OGR and Spatialite backends.
    
    Args:
        layer: Target QGIS layer
        matching_fids: List of FIDs to store
        source_wkt: WKT of source geometry
        buffer_value: Buffer distance
        predicates_list: List of predicate names
        step_number: Current step number
        logger: Optional logger instance
        backend_name: Name of calling backend for log messages
    
    Returns:
        Cache key if stored successfully, None otherwise
    
    Example:
        cache_key = store_filter_result(
            layer=target_layer,
            matching_fids=[1, 2, 3],
            source_wkt="POLYGON((...))",
            buffer_value=100.0,
            predicates_list=['intersects'],
            step_number=2,
            logger=self,
            backend_name="SpatialiteBackend"
        )
    """
    
    def log_info(msg: str):
        if logger and hasattr(logger, 'log_info'):
            logger.log_info(msg)
    
    def log_debug(msg: str):
        if logger and hasattr(logger, 'log_debug'):
            logger.log_debug(msg)
    
    # Check cache availability
    if not CACHE_AVAILABLE or not store_filter_fids:
        log_debug(f"[{backend_name}] Cache not available for storage")
        return None
    
    # Don't store empty results
    if not matching_fids:
        log_debug(f"[{backend_name}] No FIDs to store in cache")
        return None
    
    # Clean buffer value
    buffer_val = clean_buffer_value(buffer_value)
    
    try:
        cache_key = store_filter_fids(
            layer=layer,
            fids=matching_fids,
            source_geom_wkt=source_wkt,
            predicates=predicates_list,
            buffer_value=buffer_val,
            step_number=step_number
        )
        
        key_preview = cache_key[:8] if cache_key else 'N/A'
        log_info(
            f"  💾 {backend_name} Cached {len(matching_fids)} FIDs "
            f"(key={key_preview}, step={step_number})"
        )
        if QGIS_AVAILABLE and QgsMessageLog:
            QgsMessageLog.logMessage(
                f"  💾 {backend_name} cached {len(matching_fids)} FIDs "
                f"(key={key_preview}, step={step_number})",
                "FilterMate", Qgis.Info
            )
        
        return cache_key
        
    except Exception as e:
        log_debug(f"[{backend_name}] Cache storage failed (non-fatal): {e}")
        return None


def get_cache_parameters_from_task(task_params: Dict) -> Tuple[str, float, List[str]]:
    """
    Extract cache parameters from task_params dictionary.
    
    v2.8.6: Helper to standardize parameter extraction across backends.
    
    Args:
        task_params: Task parameters dictionary
    
    Returns:
        Tuple of (source_wkt, buffer_value, predicates_list)
    
    Example:
        source_wkt, buffer_val, predicates = get_cache_parameters_from_task(self.task_params)
    """
    if not task_params:
        return "", 0.0, []
    
    # Source WKT from infos
    infos = task_params.get('infos', {})
    source_wkt = infos.get('source_geom_wkt', '')
    
    # Buffer value from filtering
    filtering = task_params.get('filtering', {})
    buffer_value = filtering.get('buffer_value', 0.0)
    buffer_value = clean_buffer_value(buffer_value)
    
    # Predicates from filtering
    geom_preds = filtering.get('geometric_predicates', [])
    if isinstance(geom_preds, dict):
        predicates_list = list(geom_preds.keys())
    elif isinstance(geom_preds, list):
        predicates_list = geom_preds
    else:
        predicates_list = []
    
    return source_wkt, buffer_value, predicates_list


def get_combine_operator_from_task(task_params: Dict) -> Optional[str]:
    """
    Get current combine operator from task_params.
    
    v2.8.6: Helper to standardize operator extraction across backends.
    
    Args:
        task_params: Task parameters dictionary
    
    Returns:
        Combine operator string ('AND', 'OR', 'NOT AND') or None
    """
    if not task_params:
        return None
    
    return task_params.get('_current_combine_operator')


# Export availability flag
__all__ = [
    'CACHE_AVAILABLE',
    'CacheOperationResult',
    'perform_cache_intersection',
    'store_filter_result',
    'get_cache_parameters_from_task',
    'get_combine_operator_from_task',
    'clean_buffer_value'
]
