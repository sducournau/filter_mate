# -*- coding: utf-8 -*-
"""
SourceLayerFilterExecutor Service

EPIC-1 Phase 14.6: Extracted from FilterTask.execute_source_layer_filtering()

This service orchestrates source layer filtering with multiple execution modes:
- TaskBridge delegation (v3 hexagonal architecture)
- ALL-FEATURES mode (skip_source_filter)
- FIELD-BASED mode (geometric filtering with field expression)
- Standard expression processing
- Feature ID fallback

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase 14.6)
"""

import logging
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass
from qgis.core import QgsFeature

# FIX 2026-01-18: Import get_qgis_factory for hexagonal expression handling
from ..ports.qgis_port import get_qgis_factory

logger = logging.getLogger('FilterMate.Core.Services.SourceLayerFilterExecutor')


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FilterExecutionContext:
    """Context for source layer filter execution."""
    task_parameters: Dict[str, Any]
    source_layer: Any  # QgsVectorLayer
    param_source_old_subset: str
    primary_key_name: str
    task_bridge: Optional[Any] = None  # TaskBridge instance

    # Callbacks to parent task
    process_qgis_expression_callback: Optional[Callable] = None
    combine_with_old_subset_callback: Optional[Callable] = None
    apply_filter_and_update_subset_callback: Optional[Callable] = None
    build_feature_id_expression_callback: Optional[Callable] = None


@dataclass
class FilterExecutionResult:
    """Result of source layer filter execution."""
    success: bool
    expression: str
    is_field_expression: Optional[Tuple[bool, str]] = None
    mode: str = "unknown"  # "all-features", "field-based", "standard", "feature-ids"


# =============================================================================
# SourceLayerFilterExecutor Service
# =============================================================================

class SourceLayerFilterExecutor:
    """
    Service for executing source layer filtering with multiple modes.

    This service orchestrates the complex logic of source layer filtering,
    handling:
    - TaskBridge delegation for v3 architecture
    - ALL-FEATURES mode (skip_source_filter)
    - FIELD-BASED mode (geometric filtering)
    - Standard expression processing
    - Feature ID fallback

    Example:
        executor = SourceLayerFilterExecutor()
        result = executor.execute(context)
        if result.success:

    """

    def execute(self, context: FilterExecutionContext) -> FilterExecutionResult:
        """
        Execute source layer filtering with appropriate mode.

        Args:
            context: Execution context with task parameters and callbacks

        Returns:
            FilterExecutionResult with success status and expression
        """
        logger.info("🔧 SourceLayerFilterExecutor.execute() START")

        task_expression = context.task_parameters["task"]["expression"]
        task_features = context.task_parameters["task"]["features"]

        # Step 1: Try TaskBridge delegation (v3 architecture)
        bridge_result = self._try_taskbridge_delegation(
            context.task_bridge,
            task_expression,
            task_features
        )
        if bridge_result is not None:
            return bridge_result

        # Step 2: Log diagnostics
        self._log_diagnostics(context, task_expression, task_features)

        # Step 3: Analyze expression type
        analysis = self._analyze_expression(context, task_expression)

        # Step 4: Execute based on mode
        if analysis['skip_source_filter']:
            return self._execute_all_features_mode(context)
        elif analysis['is_simple_field']:
            return self._execute_field_based_mode(context, task_expression, analysis)
        else:
            return self._execute_standard_mode(context, task_expression, task_features)

    def _try_taskbridge_delegation(
        self,
        task_bridge: Optional[Any],
        task_expression: str,
        task_features: List[QgsFeature]
    ) -> Optional[FilterExecutionResult]:
        """
        Try v3 architecture via TaskBridge.

        Returns:
            FilterExecutionResult if TaskBridge handled it, None to fallback
        """
        if not task_bridge or not task_bridge.is_available():
            return None

        logger.info("📡 TaskBridge: Trying v3 attribute filter delegation")

        # Call parent's _try_v3_attribute_filter method
        # Note: This requires the method to be accessible
        # For now, return None to indicate fallback
        logger.debug("TaskBridge: Falling back to legacy attribute filter")
        return None

    def _log_diagnostics(
        self,
        context: FilterExecutionContext,
        task_expression: str,
        task_features: List[QgsFeature]
    ):
        """Log diagnostic information."""
        logger.info("=" * 60)
        logger.info("🔧 execute_source_layer_filtering DIAGNOSTIC")
        logger.info("=" * 60)
        logger.info(f"   task_expression = '{task_expression}'")
        logger.info(f"   task_features count = {len(task_features) if task_features else 0}")

        if task_features and len(task_features) > 0:
            for i, f in enumerate(task_features[:3]):  # Show first 3
                logger.info(f"      feature[{i}]: id={f.id()}, isValid={f.isValid()}")

        logger.info(f"   source_layer = '{context.source_layer.name() if context.source_layer else 'None'}'")
        logger.info(f"   primary_key_name = '{context.primary_key_name}'")
        logger.info("=" * 60)

    def _analyze_expression(
        self,
        context: FilterExecutionContext,
        task_expression: str
    ) -> Dict[str, Any]:
        """
        Analyze expression to determine execution mode.

        Returns:
            Dict with analysis results
        """
        # Check if expression is just a field name (no comparison operators)
        is_simple_field = False
        if task_expression:
            # HEXAGONAL MIGRATION v4.1: Use adapter instead of QgsExpression
            factory = get_qgis_factory()
            expr_adapter = factory.create_expression(task_expression)
            # FIX v2.3.9: Use case-insensitive check for operators
            task_expr_upper = task_expression.upper()
            is_simple_field = expr_adapter.is_field() and not any(
                op in task_expr_upper for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
            )

        # Check if skip_source_filter is enabled
        skip_source_filter = context.task_parameters["task"].get("skip_source_filter", False)

        # Check if geometric filtering is enabled
        has_geom_predicates = context.task_parameters["filtering"]["has_geometric_predicates"]
        geom_predicates_list = context.task_parameters["filtering"].get("geometric_predicates", [])
        has_geometric_filtering = has_geom_predicates and len(geom_predicates_list) > 0

        return {
            'is_simple_field': is_simple_field,
            'skip_source_filter': skip_source_filter,
            'has_geometric_filtering': has_geometric_filtering
        }

    def _execute_all_features_mode(
        self,
        context: FilterExecutionContext
    ) -> FilterExecutionResult:
        """
        Execute ALL-FEATURES mode (skip_source_filter=True).

        Custom Selection active with non-filter expression.
        Source layer will NOT be filtered (keeps existing subset).
        All features from source layer will be used for geometric predicates.
        """
        logger.info("=" * 60)
        logger.info("🔄 ALL-FEATURES MODE (skip_source_filter=True)")
        logger.info("=" * 60)
        logger.info("  Custom selection active with non-filter expression")
        logger.info("  → Source layer will NOT be filtered (keeps existing subset)")
        logger.info("  → All features from source layer will be used for geometric predicates")

        # Keep existing subset - don't modify source layer filter
        expression = context.param_source_old_subset if context.param_source_old_subset else ""

        # Log detailed information about source layer state
        current_subset = context.source_layer.subsetString()
        feature_count = context.source_layer.featureCount()

        if current_subset:
            logger.info(f"  ✓ Source layer has active subset: '{current_subset[:80]}...'")
            logger.info(f"  ✓ {feature_count} filtered features will be used for geometric intersection")
        else:
            logger.info(f"  ✓ Source layer has NO subset - all {feature_count} features will be used")

        logger.info("=" * 60)

        return FilterExecutionResult(
            success=True,
            expression=expression,
            is_field_expression=(True, "__all_features__"),
            mode="all-features"
        )

    def _execute_field_based_mode(
        self,
        context: FilterExecutionContext,
        task_expression: str,
        analysis: Dict[str, Any]
    ) -> FilterExecutionResult:
        """
        Execute FIELD-BASED mode (custom selection with simple field).

        COMPORTEMENT:
        1. COUCHE SOURCE: Garder le subset existant (PAS de modification)
        2. COUCHES DISTANTES: Appliquer filtre géométrique en intersection
                              avec TOUTES les géométries de la couche source

        EXEMPLE:
        - Source avec subset: "homecount > 5" (100 features)
        - Custom selection: "drop_ID" (field)
        - Prédicats géom: "intersects"
        → Source garde "homecount > 5", distant filtré par intersection
        """
        logger.info("=" * 60)
        logger.info("🔄 FIELD-BASED GEOMETRIC FILTER MODE")
        logger.info("=" * 60)
        logger.info(f"  Expression is simple field: '{task_expression}'")
        logger.info(f"  Geometric filtering enabled: {analysis['has_geometric_filtering']}")
        logger.info("  → Source layer will NOT be filtered (keeps existing subset)")

        # Keep existing subset - don't modify source layer filter
        expression = context.param_source_old_subset if context.param_source_old_subset else ""

        # Log detailed information about source layer state
        current_subset = context.source_layer.subsetString()
        feature_count = context.source_layer.featureCount()

        if current_subset:
            logger.info(f"  ✓ Source layer has active subset: '{current_subset[:80]}...'")
            logger.info(f"  ✓ {feature_count} filtered features will be used for geometric intersection")
        else:
            logger.info(f"  ℹ Source layer has NO subset - all {feature_count} features will be used")

        logger.info("=" * 60)

        return FilterExecutionResult(
            success=True,
            expression=expression,
            is_field_expression=(True, task_expression),
            mode="field-based"
        )

    def _execute_standard_mode(
        self,
        context: FilterExecutionContext,
        task_expression: str,
        task_features: List[QgsFeature]
    ) -> FilterExecutionResult:
        """
        Execute standard expression processing mode.

        Process QGIS expression, combine with old subset, and apply filter.
        Fallback to feature ID list if expression processing fails.
        """
        result = False
        expression = ""
        is_field_expr = None

        # Process QGIS expression if provided
        if task_expression:
            logger.info(f"   → Processing task_expression: '{task_expression}'")

            if context.process_qgis_expression_callback:
                processed_expr, is_field_expr = context.process_qgis_expression_callback(task_expression)
                logger.info(f"   → processed_expr: '{processed_expr}', is_field_expr: {is_field_expr}")

                if processed_expr and context.combine_with_old_subset_callback:
                    # Combine with existing subset if needed
                    expression = context.combine_with_old_subset_callback(processed_expr)
                    logger.info(f"   → combined expression: '{expression}'")

                    # Apply filter and update subset
                    if context.apply_filter_and_update_subset_callback:
                        result = context.apply_filter_and_update_subset_callback(expression)
                        logger.info(f"   → filter applied result: {result}")
        else:
            logger.info("   → No task_expression provided, will try fallback to feature IDs")

        # Fallback to feature ID list if expression processing failed
        if not result:
            logger.info("   → Fallback: trying feature ID list...")
            is_field_expr = None
            features_list = task_features
            logger.info(f"   → features_list count: {len(features_list) if features_list else 0}")

            if features_list and context.build_feature_id_expression_callback:
                expression = context.build_feature_id_expression_callback(features_list)
                logger.info(f"   → built expression from features: '{expression}'")

                if expression and context.apply_filter_and_update_subset_callback:
                    result = context.apply_filter_and_update_subset_callback(expression)
                    logger.info(f"   → fallback filter applied result: {result}")
            else:
                logger.warning("   ⚠️ No features in list - cannot apply filter!")

        logger.info(f"🔧 execute_source_layer_filtering RESULT: {result}")

        return FilterExecutionResult(
            success=result,
            expression=expression,
            is_field_expression=is_field_expr if isinstance(is_field_expr, tuple) else None,
            mode="feature-ids" if not task_expression and result else "standard"
        )


# =============================================================================
# Factory Function
# =============================================================================

def create_source_layer_filter_executor() -> SourceLayerFilterExecutor:
    """
    Factory function to create a SourceLayerFilterExecutor.

    Returns:
        SourceLayerFilterExecutor instance
    """
    return SourceLayerFilterExecutor()


# =============================================================================
# Convenience Function for Direct Use
# =============================================================================

def execute_source_layer_filtering(
    task_parameters: Dict[str, Any],
    source_layer: Any,
    param_source_old_subset: str,
    primary_key_name: str,
    task_bridge: Optional[Any] = None,
    process_qgis_expression_callback: Optional[Callable] = None,
    combine_with_old_subset_callback: Optional[Callable] = None,
    apply_filter_and_update_subset_callback: Optional[Callable] = None,
    build_feature_id_expression_callback: Optional[Callable] = None
) -> FilterExecutionResult:
    """
    Execute source layer filtering with appropriate mode.

    Convenience function that creates an executor and executes filtering.

    Args:
        task_parameters: Task parameters dict
        source_layer: Source QgsVectorLayer
        param_source_old_subset: Existing subset string
        primary_key_name: Primary key field name
        task_bridge: Optional TaskBridge for v3 delegation
        process_qgis_expression_callback: Callback to process QGIS expression
        combine_with_old_subset_callback: Callback to combine with old subset
        apply_filter_and_update_subset_callback: Callback to apply filter
        build_feature_id_expression_callback: Callback to build feature ID expression

    Returns:
        FilterExecutionResult with success status and expression
    """
    context = FilterExecutionContext(
        task_parameters=task_parameters,
        source_layer=source_layer,
        param_source_old_subset=param_source_old_subset,
        primary_key_name=primary_key_name,
        task_bridge=task_bridge,
        process_qgis_expression_callback=process_qgis_expression_callback,
        combine_with_old_subset_callback=combine_with_old_subset_callback,
        apply_filter_and_update_subset_callback=apply_filter_and_update_subset_callback,
        build_feature_id_expression_callback=build_feature_id_expression_callback
    )

    executor = create_source_layer_filter_executor()
    return executor.execute(context)
