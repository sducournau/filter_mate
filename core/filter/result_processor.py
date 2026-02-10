"""
Result Processor - Task Completion Handling

This module extracts the finished() callback logic from FilterEngineTask (7,015 lines).
It handles:

1. Thread-safe application of queued subset strings (worker → main thread)
2. Filter validation and layer reload for PostgreSQL/Spatialite/OGR
3. Large expression deferred processing to prevent UI freezes
4. Success/failure logging and user feedback
5. Layer extent updates and repaint triggers

Part of EPIC-1 Phase E12 (Filter Orchestration Extraction).

Hexagonal Architecture:
- Used by: FilterEngineTask (modules/tasks/)
- Uses: infrastructure/database/sql_utils.py (safe_set_subset_string)
"""

import logging
from typing import Dict, Any, List, Tuple
from qgis.core import (
    QgsVectorLayer,
    QgsMessageLog,
    Qgis
)
from qgis.utils import iface

from ...infrastructure.database.sql_utils import safe_set_subset_string
from ..ports import get_backend_services

_backend_services = get_backend_services()
is_valid_layer = _backend_services.is_valid_layer

logger = logging.getLogger('filter_mate')

# Performance thresholds
MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000  # Skip updateExtents() for large layers
MAX_EXPRESSION_FOR_DIRECT_APPLY = 100000  # 100KB - defer large expressions


class ResultProcessor:
    """
    Processes task completion results and applies queued filters.

    Responsibilities:
    - Apply pending subset strings on main Qt thread (thread safety)
    - Validate filters are correctly applied and refresh layers
    - Handle large expressions with deferred processing
    - Log success/failure and provide user feedback
    - Trigger layer repaints and extent updates

    This class extracts ~414 lines from FilterEngineTask.finished(),
    enabling better separation between task execution and result handling.
    """

    def __init__(
        self,
        task_action: str,
        task_parameters: Dict[str, Any]
    ):
        """
        Initialize the result processor.

        Args:
            task_action: Task action type ('filter', 'export', etc.)
            task_parameters: Task configuration dict
        """
        self.task_action = task_action
        self.task_parameters = task_parameters

        # Pending subset requests from worker thread
        self._pending_subset_requests: List[Tuple[QgsVectorLayer, str]] = []

        # Warning messages collected during execution
        self.warning_messages: List[str] = []

        # Backend warnings
        self.backend_warnings: List[str] = []

        logger.debug("ResultProcessor initialized")

    def queue_subset_request(self, layer: QgsVectorLayer, expression: str) -> None:
        """
        Queue a subset string to be applied on main thread.

        THREAD SAFETY: This is called from worker thread during run().
        Filters are queued and applied in process_completion() on main thread.

        Args:
            layer: Layer to apply filter to
            expression: Subset string expression
        """
        self._pending_subset_requests.append((layer, expression))
        logger.debug(f"Queued subset request for {layer.name()}: {len(expression)} chars")

    def collect_backend_warning(self, warning: str) -> None:
        """
        Collect a warning from backend for display in process_completion().

        Args:
            warning: Warning message
        """
        self.backend_warnings.append(warning)

    def process_completion(
        self,
        result: bool,
        is_canceled: bool = False
    ) -> None:
        """
        Process task completion on main Qt thread.

        This is the main entry point called from finished() callback.
        Handles:
        1. Display warnings collected during worker thread execution
        2. Apply pending subset strings (if not canceled)
        3. Validate filter application and refresh layers
        4. Handle large expressions with deferred processing

        Args:
            result: Task success/failure status
            is_canceled: Whether task was canceled
        """
        # ==========================================
        # 1. DISPLAY WARNINGS
        # ==========================================
        self._display_warnings()

        # ==========================================
        # 2. CHECK CANCELLATION
        # ==========================================
        # CRITICAL: Only skip subset application if TRULY canceled
        # If task succeeded (result=True), apply subsets even if isCanceled()
        # returns True (due to race conditions in QGIS task manager)
        truly_canceled = is_canceled and not (self._pending_subset_requests and result is not False)

        if truly_canceled and not self._pending_subset_requests:
            logger.info("Task was canceled - skipping pending subset requests")
            self._pending_subset_requests = []
            return

        # ==========================================
        # 3. APPLY PENDING SUBSET REQUESTS
        # ==========================================
        if not self._pending_subset_requests:
            logger.debug("No pending subset requests to apply")
            return

        QgsMessageLog.logMessage(
            f"📥 Applying {len(self._pending_subset_requests)} pending subset requests on main thread",
            "FilterMate", Qgis.Info
        )
        logger.info(f"Applying {len(self._pending_subset_requests)} pending subset requests on main thread")

        # Log details
        for idx, (lyr, expr) in enumerate(self._pending_subset_requests):
            lyr_name = lyr.name() if lyr and is_valid_layer(lyr) else "INVALID"
            expr_preview = (expr[:80] + '...') if expr and len(expr) > 80 else (expr or 'EMPTY')
            logger.debug(f"  [{idx + 1}] {lyr_name}: {expr_preview}")

        # Collect large expressions for deferred processing
        large_expressions = []

        # Apply each pending subset request
        for layer, expression in self._pending_subset_requests:
            try:
                if not layer or not is_valid_layer(layer):
                    logger.warning("  ✗ Layer became invalid before filter could be applied")
                    QgsMessageLog.logMessage(
                        f"finished() ✗ Layer invalid: {layer.name() if layer else 'None'}",
                        "FilterMate", Qgis.Warning
                    )
                    continue

                # Check if expression is too large for direct application
                expression_str = expression or ''
                if expression_str and len(expression_str) > MAX_EXPRESSION_FOR_DIRECT_APPLY:
                    logger.warning(f"  ⚠️ Large expression ({len(expression_str)} chars) for {layer.name()} - deferring")
                    large_expressions.append((layer, expression_str))
                    continue

                # Apply filter
                self._apply_single_subset(layer, expression)

            except Exception as e:
                logger.error(f"  ✗ Error applying subset string: {e}", exc_info=True)
                QgsMessageLog.logMessage(
                    f"finished() ✗ Exception: {layer.name() if layer else 'Unknown'} - {str(e)}",
                    "FilterMate", Qgis.Critical
                )

        # ==========================================
        # 4. DEFERRED PROCESSING FOR LARGE EXPRESSIONS
        # ==========================================
        if large_expressions:
            self._apply_large_expressions_deferred(large_expressions)

        # Clear pending requests
        self._pending_subset_requests = []

    # =====================================================================
    # PRIVATE HELPER METHODS
    # =====================================================================

    def _display_warnings(self) -> None:
        """Display warnings collected during worker thread execution."""
        # Display warnings from worker thread
        if self.warning_messages:
            for warning_msg in self.warning_messages:
                iface.messageBar().pushWarning("FilterMate", warning_msg)
            self.warning_messages = []

        # Display backend warnings
        if self.backend_warnings:
            for warning_msg in self.backend_warnings:
                iface.messageBar().pushWarning("FilterMate", warning_msg)
            self.backend_warnings = []

    def _apply_single_subset(
        self,
        layer: QgsVectorLayer,
        expression: str
    ) -> None:
        """
        Apply subset string to a single layer.

        Handles:
        - Filter already applied → force reload
        - New filter → apply with type casting, reload, and repaint
        - Provider-specific refresh (PostgreSQL, Spatialite, OGR)

        Args:
            layer: Layer to apply filter to
            expression: Subset string expression
        """
        current_subset = layer.subsetString() or ''
        expression_str = expression or ''

        if current_subset.strip() == expression_str.strip():
            # Filter already applied - force reload
            self._reload_layer_after_filter(layer, already_applied=True)
            logger.debug(f"  ✓ Filter already applied to {layer.name()}, triggered reload+repaint")

            feature_count = layer.featureCount()
            count_str = f"{feature_count} features" if feature_count >= 0 else "(count pending)"
            logger.debug(f"finished() ✓ Repaint: {layer.name()} → {count_str} (filter already applied)")
        else:
            # Apply new filter
            success = safe_set_subset_string(layer, expression)

            if success:
                self._reload_layer_after_filter(layer, already_applied=False)
                logger.debug(f"  ✓ Applied filter to {layer.name()}: {len(expression) if expression else 0} chars")

                # Log result
                feature_count = layer.featureCount()
                if feature_count >= 0:
                    count_str = f"{feature_count} features"
                    QgsMessageLog.logMessage(
                        f"✓ Filter APPLIED: {layer.name()} → {feature_count} features",
                        "FilterMate", Qgis.Info
                    )

                    # Warn if 0 features
                    if feature_count == 0:
                        logger.warning(f"  ⚠️ Layer {layer.name()} has 0 features after filtering!")
                        logger.warning(f"    → Expression length: {len(expression)} chars")
                        logger.warning("    → Check if expression is too complex or returns no results")
                        QgsMessageLog.logMessage(
                            f"⚠️ {layer.name()} → 0 features (filter may be too restrictive or expression error)",
                            "FilterMate", Qgis.Warning
                        )
                else:
                    count_str = "(count pending)"
                    QgsMessageLog.logMessage(
                        f"✓ Filter APPLIED: {layer.name()} → (count pending)",
                        "FilterMate", Qgis.Info
                    )

                logger.debug(f"finished() ✓ Applied: {layer.name()} → {count_str}")
            else:
                # Filter application failed
                error_msg = 'Unknown error'
                if layer.error():
                    error_msg = layer.error().message()

                logger.warning(f"  ✗ Failed to apply filter to {layer.name()}")
                logger.warning(f"    → Error: {error_msg}")
                logger.warning(f"    → Expression ({len(expression) if expression else 0} chars): {expression[:200] if expression else '(empty)'}...")
                logger.warning(f"    → Provider: {layer.providerType()}")

                QgsMessageLog.logMessage(
                    f"finished() ✗ FAILED: {layer.name()} - {error_msg}",
                    "FilterMate", Qgis.Critical
                )

    def _reload_layer_after_filter(
        self,
        layer: QgsVectorLayer,
        already_applied: bool = False
    ) -> None:
        """
        Reload layer after filter application.

        Provider-specific refresh:
        - PostgreSQL: reload() to force data refresh
        - Spatialite: reload() + removeSelection()
        - OGR: reload() to get correct feature count

        Args:
            layer: Layer to reload
            already_applied: Whether filter was already applied (skip updateExtents)
        """
        provider_type = layer.providerType()

        # Force reload for PostgreSQL/Spatialite/OGR layers
        if provider_type in ('postgres', 'spatialite', 'ogr'):
            # CRITICAL: Block signals during reload to prevent
            # currentLayerChanged emissions that reset UI combobox
            try:
                layer.blockSignals(True)
                layer.reload()
            finally:
                layer.blockSignals(False)

        # Update extents for small layers
        feature_count = layer.featureCount()
        if feature_count is not None and 0 <= feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
            layer.updateExtents()

        # Trigger repaint
        layer.triggerRepaint()

        # Clear selection for Spatialite layers
        if provider_type == 'spatialite':
            try:
                layer.removeSelection()
                logger.debug(f"Cleared selection after Spatialite filter ({'already applied' if already_applied else 'new filter'})")
            except Exception as e:
                logger.debug(f"Could not clear selection: {e}")

    def _apply_large_expressions_deferred(
        self,
        large_expressions: List[Tuple[QgsVectorLayer, str]]
    ) -> None:
        """
        Apply large filter expressions with deferred processing.

        Uses QTimer to give UI breathing room between applications,
        preventing freezes when applying many large expressions.

        Args:
            large_expressions: List of (layer, expression) tuples
        """
        logger.info(f"  📦 Applying {len(large_expressions)} large expressions with deferred processing")

        from qgis.PyQt.QtCore import QTimer

        def apply_deferred_filters():
            """Apply large filter expressions with UI breathing room."""
            for lyr, expr in large_expressions:
                try:
                    if lyr and is_valid_layer(lyr):
                        logger.info(f"  → Applying deferred filter to {lyr.name()} ({len(expr)} chars)")
                        self._apply_single_subset(lyr, expr)
                    else:
                        logger.warning("  ✗ Layer became invalid during deferred processing")
                except Exception as e:
                    logger.error(f"  ✗ Error in deferred filter application: {e}", exc_info=True)

            logger.info(f"  ✓ Completed {len(large_expressions)} deferred filter applications")

        # Schedule deferred application with 100ms delay
        QTimer.singleShot(100, apply_deferred_filters)
