"""
EPIC-1 Phase E6: Task completion handler for FilterTask.

Extracted from filter_task.py finished() method to reduce complexity.
This module handles post-task operations like subset application and canvas refresh.
"""

import logging
from typing import List, Tuple, Optional, Any, Callable

from ..ports.qgis_port import get_qgis_factory
from qgis.core import QgsMessageLog, Qgis
from qgis.utils import iface
from qgis.PyQt.QtCore import QTimer

logger = logging.getLogger(__name__)

# Import centralized validation (v4.0.4 - eliminate duplication)
try:
    from ...infrastructure.utils import is_layer_valid as is_valid_layer
except ImportError:
    # Fallback for testing or import issues
    def is_valid_layer(layer: Any) -> bool:
        """Check if layer is valid and accessible (fallback)."""
        if layer is None:
            return False
        try:
            return hasattr(layer, 'isValid') and layer.isValid() and hasattr(layer, 'id')
        except RuntimeError:
            return False


def display_warning_messages(warning_messages: List[str]) -> None:
    """
    Display warning messages stored during worker thread execution.
    
    These warnings could not be displayed from worker thread due to
    Qt thread safety requirements.
    
    Args:
        warning_messages: List of warning message strings to display
    """
    if not warning_messages:
        return
    
    for warning_msg in warning_messages:
        try:
            iface.messageBar().pushWarning("FilterMate", warning_msg)
        except Exception as e:
            logger.warning(f"Could not display warning: {e}")


def should_skip_subset_application(
    is_canceled: bool,
    has_pending_requests: bool,
    pending_requests: List,
    result: Optional[bool]
) -> bool:
    """
    Determine if pending subset requests should be skipped.
    
    Args:
        is_canceled: Whether task.isCanceled() is True
        has_pending_requests: Whether there are pending requests
        pending_requests: The actual pending requests list
        result: The task result (True/False/None)
        
    Returns:
        bool: True if subset application should be skipped
    """
    # v3.0.8: Only skip if TRULY canceled (not just marked as canceled)
    # Check if we have pending requests AND if the task actually returned False (failed)
    # If the task succeeded (result=True), we should still apply the subsets even if
    # isCanceled() returns True (which can happen due to race conditions in QGIS)
    truly_canceled = (
        is_canceled and 
        not (has_pending_requests and pending_requests and result is not False)
    )
    
    return truly_canceled and has_pending_requests and not pending_requests


def apply_pending_subset_requests(
    pending_requests: List[Tuple[Any, str]],  # List[Tuple[QgsVectorLayer, str]]
    safe_set_subset_fn: Callable[[Any, str], bool]  # Callable[[QgsVectorLayer, str], bool]
) -> int:
    """
    Apply pending subset string requests on main thread.
    
    This is called from the main Qt thread (unlike run() which is on a worker thread).
    Fully extracted from FilterTask.finished() in Phase E6.
    
    Args:
        pending_requests: List of (layer, expression) tuples
        safe_set_subset_fn: Function to safely set subset string
        
    Returns:
        int: Number of successfully applied filters
    """
    if not pending_requests:
        return 0
    
    QgsMessageLog.logMessage(
        f"📥 Applying {len(pending_requests)} pending subset requests on main thread",
        "FilterMate", Qgis.Info
    )
    logger.info(f"finished(): Applying {len(pending_requests)} pending subset requests on main thread")
    
    # Log all pending requests details
    for idx, (lyr, expr) in enumerate(pending_requests):
        lyr_name = lyr.name() if lyr and is_valid_layer(lyr) else "INVALID"
        expr_preview = (expr[:80] + '...') if expr and len(expr) > 80 else (expr or 'EMPTY')
        logger.debug(f"  [{idx+1}] {lyr_name}: {expr_preview}")
    
    # Performance thresholds
    MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000
    MAX_EXPRESSION_FOR_DIRECT_APPLY = 100000  # 100KB
    
    # Collect large expressions for deferred application
    large_expressions = []
    applied_count = 0
    
    for layer, expression in pending_requests:
        try:
            if not layer or not is_valid_layer(layer):
                QgsMessageLog.logMessage(
                    f"finished() ✗ Layer invalid: {layer.name() if layer else 'None'}",
                    "FilterMate", Qgis.Warning
                )
                continue
                
            current_subset = layer.subsetString() or ''
            expression_str = expression or ''
            
            # Check if expression is too large for direct application
            if expression_str and len(expression_str) > MAX_EXPRESSION_FOR_DIRECT_APPLY:
                logger.warning(f"  ⚠️ Large expression ({len(expression_str)} chars) for {layer.name()} - deferring")
                large_expressions.append((layer, expression_str))
                continue
            
            # Check if filter already applied
            if current_subset.strip() == expression_str.strip():
                # Filter already applied - force reload for PostgreSQL/Spatialite/OGR layers
                if layer.providerType() in ('postgres', 'spatialite', 'ogr'):
                    try:
                        layer.blockSignals(True)
                        layer.reload()
                    finally:
                        layer.blockSignals(False)
                
                # Update extents for smaller layers
                feature_count = layer.featureCount()
                if feature_count is not None and feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                    try:
                        layer.updateExtents()
                    except Exception:
                        pass
                
                layer.triggerRepaint()
                
                # FIX v2.9.24: Clear selection for Spatialite layers after reload
                if layer.providerType() == 'spatialite':
                    try:
                        layer.removeSelection()
                        logger.debug(f"Cleared selection after Spatialite filter (already applied)")
                    except Exception as sel_err:
                        logger.debug(f"Could not clear selection: {sel_err}")
                
                count_str = f"{feature_count} features" if feature_count >= 0 else "(count pending)"
                logger.debug(f"  ✓ Filter already applied to {layer.name()}, triggered reload+repaint")
                QgsMessageLog.logMessage(
                    f"finished() ✓ Repaint: {layer.name()} → {count_str} (filter already applied)",
                    "FilterMate", Qgis.Info
                )
                applied_count += 1
            else:
                # Apply new filter
                success = safe_set_subset_fn(layer, expression_str)
                if success:
                    # Force reload for PostgreSQL/Spatialite/OGR layers
                    if layer.providerType() in ('postgres', 'spatialite', 'ogr'):
                        try:
                            layer.blockSignals(True)
                            layer.reload()
                        finally:
                            layer.blockSignals(False)
                    
                    # Update extents for smaller layers
                    feature_count = layer.featureCount()
                    if feature_count is not None and feature_count >= 0 and feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                        try:
                            layer.updateExtents()
                        except Exception:
                            pass
                    
                    layer.triggerRepaint()
                    
                    # FIX v2.9.24: Clear selection for Spatialite layers
                    if layer.providerType() == 'spatialite':
                        try:
                            layer.removeSelection()
                            logger.debug(f"Cleared selection after Spatialite filter (new filter)")
                        except Exception as sel_err:
                            logger.debug(f"Could not clear selection: {sel_err}")
                    
                    logger.debug(f"  ✓ Applied filter to {layer.name()}: {len(expression_str)} chars")
                    
                    # Handle feature count and logging
                    feature_count = layer.featureCount()
                    if feature_count >= 0:
                        QgsMessageLog.logMessage(
                            f"✓ Filter APPLIED: {layer.name()} → {feature_count} features",
                            "FilterMate", Qgis.Info
                        )
                        # Diagnostic for layers with 0 features
                        if feature_count == 0:
                            logger.warning(f"  ⚠️ Layer {layer.name()} has 0 features after filtering!")
                            logger.warning(f"    → Expression length: {len(expression_str)} chars")
                            QgsMessageLog.logMessage(
                                f"⚠️ {layer.name()} → 0 features (filter may be too restrictive)",
                                "FilterMate", Qgis.Warning
                            )
                    else:
                        QgsMessageLog.logMessage(
                            f"✓ Filter APPLIED: {layer.name()} → (count pending)",
                            "FilterMate", Qgis.Info
                        )
                    
                    applied_count += 1
                else:
                    # Enhanced diagnostic for failed filters
                    error_msg = 'Unknown error'
                    if layer.error():
                        error_msg = layer.error().message()
                    logger.warning(f"  ✗ Failed to apply filter to {layer.name()}")
                    logger.warning(f"    → Error: {error_msg}")
                    logger.warning(f"    → Expression ({len(expression_str)} chars): {expression_str[:200]}...")
                    logger.warning(f"    → Provider: {layer.providerType()}")
                    QgsMessageLog.logMessage(
                        f"finished() ✗ FAILED: {layer.name()} - {error_msg}",
                        "FilterMate", Qgis.Critical
                    )
                    
        except Exception as e:
            import traceback
            logger.error(f"  ✗ Error applying subset string: {e}")
            logger.error(f"    → Traceback: {traceback.format_exc()}")
            QgsMessageLog.logMessage(
                f"finished() ✗ Exception: {layer.name() if layer else 'Unknown'} - {str(e)}",
                "FilterMate", Qgis.Critical
            )
    
    # Handle large expressions with deferred application
    if large_expressions:
        logger.info(f"  📦 Applying {len(large_expressions)} large expressions with deferred processing")
        _schedule_deferred_filter_application(large_expressions, safe_set_subset_fn)
    
    return applied_count


def _schedule_deferred_filter_application(
    large_expressions: List[Tuple[Any, str]],  # List[Tuple[QgsVectorLayer, str]]
    safe_set_subset_fn: Callable[[Any, str], bool]  # Callable[[QgsVectorLayer, str], bool]
) -> None:
    """
    Schedule deferred application of large filter expressions.
    
    This allows the UI to remain responsive during large filter application.
    
    Args:
        large_expressions: List of (layer, expression) tuples with large expressions
        safe_set_subset_fn: Function to safely set subset string
    """
    def apply_deferred_filters():
        """Apply large filter expressions with UI breathing room."""
        for lyr, expr in large_expressions:
            try:
                if lyr and is_valid_layer(lyr):
                    success = safe_set_subset_fn(lyr, expr)
                    if success:
                        lyr.triggerRepaint()
                        QgsMessageLog.logMessage(
                            f"finished() ✓ Deferred: {lyr.name()} → {lyr.featureCount()} features",
                            "FilterMate", Qgis.Info
                        )
                    else:
                        logger.error(f"Failed to apply deferred filter to {lyr.name()}")
            except Exception as e:
                logger.error(f"Error applying deferred filter: {e}")
        
        # Final canvas refresh
        try:
            iface.mapCanvas().refresh()
        except Exception:
            pass
    
    # Defer to allow UI to breathe
    QTimer.singleShot(100, apply_deferred_filters)


def schedule_canvas_refresh(
    is_complex_filter_fn: Callable[[str, str], bool],
    single_refresh_fn: Callable[[], None]
) -> None:
    """
    Schedule canvas refresh with adaptive timing.
    
    Uses longer delay for complex filters to allow provider to process.
    
    Args:
        is_complex_filter_fn: Function to check if filter is complex
        single_refresh_fn: Function to perform single canvas refresh
    """
    try:
        # Stop any ongoing rendering first
        canvas = iface.mapCanvas()
        canvas.stopRendering()
        canvas.refresh()
        logger.debug("Immediate canvas refresh triggered after filter application (with stopRendering)")
    except Exception as refresh_err:
        logger.debug(f"Could not trigger immediate canvas refresh: {refresh_err}")
    
    try:
        # Check if any filter is complex
        has_complex_filter = False
        factory = get_qgis_factory()
        project = factory.get_project()
        for layer_id, layer in project.map_layers().items():
            if layer.type() == 0:  # Vector layer
                subset = layer.subsetString() or ''
                if subset and is_complex_filter_fn(subset, layer.providerType()):
                    has_complex_filter = True
                    break
        
        # Use longer delay for complex filters
        refresh_delay = 1500 if has_complex_filter else 500
        
        # Schedule single comprehensive refresh
        QTimer.singleShot(refresh_delay, single_refresh_fn)
        logger.debug(f"Scheduled single canvas refresh in {refresh_delay}ms (complex={has_complex_filter})")
        
    except Exception as canvas_err:
        logger.warning(f"Failed to schedule canvas refresh: {canvas_err}")
        # Fallback: immediate refresh
        try:
            iface.mapCanvas().refresh()
        except Exception:
            pass


def cleanup_memory_layer(ogr_source_geom: Optional[Any]) -> None:  # Optional[QgsVectorLayer]
    """
    Cleanup memory layer added to project to prevent garbage collection issues.
    
    Args:
        ogr_source_geom: The OGR source geometry layer to cleanup
    """
    if ogr_source_geom is None:
        return
        
    try:
        if ogr_source_geom.isValid() and ogr_source_geom.providerType() == 'memory':
            # Check if layer is in project
            factory = get_qgis_factory()
            project = factory.get_project()
            if project.map_layer(ogr_source_geom.id()):
                logger.debug("finished(): Removing OGR source memory layer from project")
                project.remove_map_layer(ogr_source_geom.id())
    except Exception as e:
        logger.debug(f"Could not cleanup memory layer: {e}")
