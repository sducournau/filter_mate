"""
Filter Orchestrator - Core Geometric Filtering Coordination

This module extracts the geometric filtering orchestration logic from
the FilterEngineTask God Class (7,015 lines). It coordinates:

1. Backend selection and preparation (PostgreSQL/Spatialite/OGR)
2. Source geometry preparation per backend requirements
3. Filter expression building delegation
4. Backend execution with intelligent fallback mechanisms
5. Subset string management and combination strategies

Part of EPIC-1 Phase E12 (Filter Orchestration Extraction).

Hexagonal Architecture:
- Uses ports: BackendPort (adapters/backends/)
- Used by: FilterEngineTask (modules/tasks/)
- Delegates to: ExpressionBuilder, ResultProcessor
"""

import logging
from typing import Optional, Dict, Any, Tuple
from qgis.core import (
    QgsVectorLayer,
    QgsMessageLog,
    Qgis
)

from ..ports import get_backend_services
from ...infrastructure.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR

_backend_services = get_backend_services()
BackendFactory = _backend_services.get_backend_factory()

logger = logging.getLogger('filter_mate')


class FilterOrchestrator:
    """
    Orchestrates geometric filtering across different backend types.

    Responsibilities:
    - Select appropriate backend based on layer provider and forced settings
    - Prepare source geometries in formats required by each backend
    - Coordinate filter application with intelligent fallback chains
    - Manage subset string combination strategies (REPLACE vs COMBINE)
    - Handle backend failures gracefully (Spatialite → OGR, PostgreSQL → OGR)

    This class extracts ~500 lines of orchestration logic from FilterEngineTask,
    enabling cleaner separation of concerns and easier testing.
    """

    def __init__(
        self,
        task_parameters: Dict[str, Any],
        subset_queue_callback: callable,
        parent_task: Any,
        get_predicates_callback: callable
    ):
        """
        Initialize the filter orchestrator.

        Args:
            task_parameters: Task configuration dict (contains forced_backends, etc.)
            subset_queue_callback: Callback to queue subset strings for main thread application
            parent_task: Reference to parent FilterEngineTask (for cancellation checks)
            get_predicates_callback: Callable returning current predicates dict
                                     (called lazily during filter execution)

        ARCHITECTURE FIX 2026-01-16 (Winston):
        Callback pattern replaces passing current_predicates by value.
        This ensures predicates are fetched AFTER _initialize_current_predicates()
        has run, preventing empty predicates bug on distant PostgreSQL layers.
        """
        self.task_parameters = task_parameters
        self.subset_queue_callback = subset_queue_callback
        self.parent_task = parent_task
        self._get_predicates_callback = get_predicates_callback

        # Inject callbacks into task_parameters for backends to use
        self.task_parameters['_subset_queue_callback'] = subset_queue_callback
        self.task_parameters['_parent_task'] = parent_task

        logger.debug("FilterOrchestrator initialized with callback pattern (predicates fetched lazily)")

    def orchestrate_geometric_filter(
        self,
        layer: QgsVectorLayer,
        layer_provider_type: str,
        layer_props: Dict[str, Any],
        source_geometries: Dict[str, Any],
        expression_builder: Any
    ) -> bool:
        """
        Execute complete geometric filtering workflow on a single layer.

        This is the main entry point that:
        1. Validates layer is still valid
        2. Selects appropriate backend (respecting forced backends)
        3. Prepares source geometry for selected backend
        4. Builds filter expression via ExpressionBuilder
        5. Applies filter with fallback handling
        6. Manages subset string combination (REPLACE geometric, COMBINE attribute)

        Args:
            layer: QGIS vector layer to filter
            layer_provider_type: Original provider type ('postgresql', 'spatialite', 'ogr')
            layer_props: Layer metadata dict (table name, schema, geometry field, etc.)
            source_geometries: Dict mapping provider types to prepared source geometries
                               Keys: 'postgresql', 'spatialite', 'ogr'
                               Values: Geometry in appropriate format for each backend
            expression_builder: ExpressionBuilder instance for building filter expressions

        Returns:
            bool: True if filtering succeeded, False otherwise

        Raises:
            LayerInvalidError: If layer is invalid or deleted
            BackendNotAvailableError: If no backend can handle the layer
        """
        try:
            # ==========================================
            # 1. LAYER VALIDATION
            # ==========================================
            if not self._validate_layer(layer):
                return False

            # ==========================================
            # 2. BACKEND SELECTION
            # ==========================================
            effective_provider_type = layer_props.get("_effective_provider_type", layer_provider_type)
            is_postgresql_fallback = layer_props.get("_postgresql_fallback", False)

            # DIAGNOSTIC LOGS 2026-01-15: Trace predicates et backend selection
            logger.info(f"🔍 orchestrate_geometric_filter: {layer.name()}")
            logger.debug(f"   effective_provider_type: {effective_provider_type}")
            logger.info(f"   is_postgresql_fallback: {is_postgresql_fallback}")
            logger.info(f"   source_geometries keys: {list(source_geometries.keys())}")

            # ARCHITECTURE FIX 2026-01-16: Récupérer prédicats dynamiquement via callback
            current_predicates = self._get_predicates_callback()
            logger.info(f"   current_predicates (fetched via callback): {current_predicates}")

            # Validation robuste des prédicats
            if not current_predicates:
                logger.error("❌ No predicates available for layer: {}".format(layer.name()))
                logger.error("   Check TaskRunOrchestrator._initialize_current_predicates()")
                logger.error("   Callback returned empty predicates - aborting geometric filtering.")
                return False

            logger.info(f"✓ Predicates loaded dynamically: {list(current_predicates.keys())}")

            if is_postgresql_fallback:
                logger.info(f"Executing geometric filtering for {layer.name()} (PostgreSQL → OGR fallback)")
            else:
                logger.debug(f"Executing geometric filtering for {layer.name()} ({effective_provider_type})")

            # Check for forced backend
            backend, backend_name, geometry_provider = self._select_backend(
                layer,
                effective_provider_type
            )

            # ==========================================
            # 3. SOURCE GEOMETRY PREPARATION
            # ==========================================
            # Enhanced logging to diagnose geometry availability issues
            logger.info(f"📦 SOURCE GEOMETRY CHECK for geometry_provider='{geometry_provider}':")
            for provider_key, geom_value in source_geometries.items():
                status = "✓ AVAILABLE" if geom_value else "✗ None"
                geom_info = ""
                if geom_value:
                    if hasattr(geom_value, 'name'):
                        geom_info = f" ({type(geom_value).__name__}: {geom_value.name()})"
                    elif isinstance(geom_value, str):
                        geom_info = f" (str, len={len(geom_value)}, preview='{geom_value[:50]}...')"
                    else:
                        geom_info = f" ({type(geom_value).__name__})"
                logger.info(f"   {provider_key}: {status}{geom_info}")

            source_geom = source_geometries.get(geometry_provider)
            if not source_geom:
                logger.error(
                    f"❌ Failed to get source geometry for provider '{geometry_provider}' "
                    f"(backend: {backend_name}, layer: {layer.name()})"
                )
                logger.error(f"   Available providers: {[k for k, v in source_geometries.items() if v]}")
                logger.error("   💡 Check if prepare_*_source_geom() was called for this provider type")
                # Log to QGIS message panel for visibility
                QgsMessageLog.logMessage(
                    f"FilterMate: No source geometry for {geometry_provider} backend (layer: {layer.name()})",
                    "FilterMate", Qgis.Critical
                )
                return False

            logger.info(f"  ✓ Source geometry ready: {type(source_geom).__name__}")

            # ==========================================
            # 4. PRE-FILTER CLEANUP
            # ==========================================
            self._clean_corrupted_subsets(layer)

            # ==========================================
            # 5. EXPRESSION BUILDING
            # ==========================================
            logger.info("=" * 80)
            logger.info("🏗️ STEP 5: EXPRESSION BUILDING")
            logger.info("=" * 80)
            logger.info("   Calling expression_builder.build_backend_expression()...")
            logger.info(f"   Backend: {backend_name}")
            logger.info(f"   Layer: {layer.name()}")
            logger.info(f"   Source geom type: {type(source_geom).__name__}")

            expression = expression_builder.build_backend_expression(
                backend=backend,
                layer_props=layer_props,
                source_geom=source_geom
            )

            logger.info("=" * 80)
            logger.info("✅ EXPRESSION BUILDING COMPLETE")
            logger.info("=" * 80)

            if not expression:
                # Try OGR fallback if primary backend failed
                return self._try_fallback_backend(
                    layer=layer,
                    layer_props=layer_props,
                    backend_name=backend_name,
                    source_geometries=source_geometries,
                    expression_builder=expression_builder
                )

            logger.info(f"  ✓ Expression built: {len(expression)} chars")
            logger.info(f"  → Expression preview: {expression[:200]}...")

            # DIAGNOSTIC 2026-01-19: Print expression for console visibility

            # ==========================================
            # 6. SUBSET STRING STRATEGY
            # ==========================================
            old_subset, combine_operator = self._determine_subset_strategy(layer)

            # ==========================================
            # 7. BACKEND EXECUTION
            # ==========================================
            # Enhanced logging before apply_filter for debugging PostgreSQL failures
            logger.info("=" * 80)
            logger.info("🎯 STEP 7: BACKEND EXECUTION")
            logger.info("=" * 80)
            logger.info(f"   Backend: {backend_name.upper()}")
            logger.info(f"   Layer: {layer.name()}")
            logger.info(f"   Expression length: {len(expression)} chars")
            logger.info(f"   Old subset: {bool(old_subset)}")
            logger.info(f"   Combine operator: {combine_operator}")

            # Log full expression for PostgreSQL debugging
            if backend_name == 'postgresql':
                logger.info("   📝 Full PostgreSQL expression:")
                logger.info(f"   {expression}")

            result = backend.apply_filter(layer, expression, old_subset, combine_operator)

            logger.info(f"   → apply_filter() result: {result}")
            if not result:
                logger.warning(f"   ❌ Backend {backend_name.upper()} FAILED for {layer.name()}")
            else:
                logger.info(f"   ✓ Backend {backend_name.upper()} succeeded for {layer.name()}")

            logger.info("=" * 80)

            # Collect warnings from backend
            self._collect_backend_warnings(backend)

            # ==========================================
            # 8. FALLBACK HANDLING
            # ==========================================
            if not result and backend_name in ('spatialite', 'postgresql'):
                return self._handle_backend_failure(
                    layer=layer,
                    layer_props=layer_props,
                    backend_name=backend_name,
                    source_geometries=source_geometries,
                    expression_builder=expression_builder,
                    old_subset=old_subset,
                    combine_operator=combine_operator
                )

            # ==========================================
            # 9. VALIDATION & LOGGING
            # ==========================================
            if result:
                self._log_filter_success(layer, backend_name)
            else:
                self._log_filter_failure(layer, backend_name)

            return result

        except Exception as e:
            QgsMessageLog.logMessage(
                f"orchestrate_geometric_filter EXCEPTION for {layer.name()}: {e}",
                "FilterMate", Qgis.Critical
            )
            logger.error(f"Error in orchestrate_geometric_filter for {layer.name()}: {e}", exc_info=True)
            return False

    # =====================================================================
    # PRIVATE HELPER METHODS
    # =====================================================================

    def _validate_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Validate layer is still valid and accessible.

        Args:
            layer: Layer to validate

        Returns:
            bool: True if layer is valid, False otherwise
        """
        try:
            layer.id()
            layer_name = layer.name()

            if not layer.isValid():
                logger.error(f"Layer {layer_name} is not valid - skipping filtering")
                return False

            return True

        except (RuntimeError, AttributeError) as e:
            logger.error(f"Layer access error (C++ object may be deleted): {e}")
            return False

    def _select_backend(
        self,
        layer: QgsVectorLayer,
        effective_provider_type: str
    ) -> Tuple[Any, str, str]:
        """
        Select appropriate backend for this layer.

        Respects forced backends from task_parameters. Returns backend instance,
        backend name, and geometry provider type.

        Args:
            layer: Layer to filter
            effective_provider_type: Provider type (may be different from layer.providerType())

        Returns:
            Tuple[backend, backend_name, geometry_provider]:
                - backend: Backend instance
                - backend_name: Backend name ('postgresql', 'spatialite', 'ogr', 'memory')
                - geometry_provider: Geometry format needed (PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR)
        """
        # Check if backend is forced for this layer
        forced_backends = self.task_parameters.get('forced_backends', {})
        forced_backend = forced_backends.get(layer.id())

        if forced_backend:
            logger.debug(f"  ⚡ Using FORCED backend '{forced_backend}' for layer '{layer.name()}'")
            effective_provider_type = forced_backend

        # Get backend from factory
        backend = BackendFactory.get_backend(effective_provider_type, layer, self.task_parameters)
        backend_name = backend.get_backend_name().lower()

        logger.debug(f"_select_backend: {layer.name()} → backend={backend_name.upper()}")

        # Log if forced backend differs from actual backend
        if forced_backend and backend_name != forced_backend:
            logger.warning(
                f"  ⚠️ Forced backend '{forced_backend}' but got '{backend_name}' "
                "(backend may not support layer)"
            )
        else:
            logger.debug(f"  ✓ Using backend: {backend_name.upper()}")

        # Store actual backend for UI indicator
        if 'actual_backends' not in self.task_parameters:
            self.task_parameters['actual_backends'] = {}
        self.task_parameters['actual_backends'][layer.id()] = backend_name

        # Determine geometry provider based on backend type
        if backend_name == 'spatialite':
            geometry_provider = PROVIDER_SPATIALITE
            logger.info("  → Backend is Spatialite - using WKT geometry format")
        elif backend_name == 'ogr':
            geometry_provider = PROVIDER_OGR
            if effective_provider_type == PROVIDER_POSTGRES:
                logger.info("  → Backend is OGR but provider is PostgreSQL - using OGR geometry format (fallback)")
            else:
                logger.info("  → Backend is OGR - using QgsVectorLayer geometry format")
        elif backend_name == 'postgresql':
            geometry_provider = PROVIDER_POSTGRES
            logger.info("  → Backend is PostgreSQL - using SQL expression geometry format")
        elif backend_name == 'memory':
            geometry_provider = PROVIDER_OGR
            logger.debug("  → Backend is Memory - using OGR geometry format (QgsVectorLayer)")
        else:
            geometry_provider = effective_provider_type
            logger.warning(f"  → Unknown backend '{backend_name}' - using provider type {effective_provider_type}")

        return backend, backend_name, geometry_provider

    def _clean_corrupted_subsets(self, layer: QgsVectorLayer) -> None:
        """
        Clean corrupted subset strings containing invalid __source aliases.

        CRITICAL FIX 2026-01-18: Only clean TRULY corrupted subsets, not valid EXISTS expressions!
        Valid EXISTS format: EXISTS (SELECT 1 FROM "schema"."table" AS __source WHERE ...)
        Corrupted format: Partial/malformed expressions from failed operations.

        Args:
            layer: Layer to check and clean
        """
        import re
        current_subset = layer.subsetString()

        if not current_subset or '__source' not in current_subset.lower():
            return

        # Check if this is a VALID EXISTS expression (well-formed)
        # Pattern: EXISTS (SELECT ... FROM ... AS __source WHERE ...)
        is_valid_exists = bool(re.match(
            r'^\s*EXISTS\s*\(\s*SELECT\s+.+\s+FROM\s+.+\s+AS\s+__source\s+WHERE\s+.+\)\s*$',
            current_subset,
            re.IGNORECASE | re.DOTALL
        ))

        if is_valid_exists:
            logger.debug(f"✓ Layer {layer.name()} has VALID EXISTS expression - keeping it")
            logger.debug(f"  → Expression: '{current_subset[:100]}'...")
            return

        # If we reach here, it's a CORRUPTED expression with __source
        logger.warning(f"🧹 CLEANING corrupted subset on {layer.name()} BEFORE filtering")
        logger.warning(f"  → Corrupted subset found: '{current_subset[:100]}'...")
        logger.warning("  → Clearing it to prevent SQL errors (NOT a valid EXISTS expression)")

        # Queue subset clear for main thread application
        self.subset_queue_callback(layer, "")
        logger.info(f"  ✓ Queued subset clear for {layer.name()} - ready for fresh filter")

    def _determine_subset_strategy(
        self,
        layer: QgsVectorLayer
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Determine whether to REPLACE or COMBINE existing subset string.

        Strategy:
        - REPLACE: If subset contains geometric patterns (EXISTS, ST_*, __source)
        - REPLACE: If subset contains style/display expressions (CASE, coalesce)
        - COMBINE: If subset is simple attribute filter (preserve user's filter)
        - SPECIAL: If FID-only filter from previous step, keep for cache but don't combine in SQL

        Args:
            layer: Layer with potential existing subset

        Returns:
            Tuple[old_subset, combine_operator]:
                - old_subset: Existing subset to combine with (or None to replace)
                - combine_operator: SQL operator ('AND', 'OR', 'AND NOT', or None)
        """
        import re

        old_subset = layer.subsetString() if layer.subsetString() != '' else None
        combine_operator = self._get_combine_operator()

        # Store combine operator in task params for cache validation
        self.task_parameters['_current_combine_operator'] = combine_operator

        if not old_subset:
            return None, None

        old_subset_upper = old_subset.upper()

        # Check for geometric filter patterns
        is_geometric_filter = (
            '__source' in old_subset.lower() or
            'EXISTS (' in old_subset_upper or
            'EXISTS(' in old_subset_upper or
            any(pred in old_subset_upper for pred in [
                'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN', 'ST_TOUCHES',
                'ST_OVERLAPS', 'ST_CROSSES', 'ST_DISJOINT', 'ST_EQUALS',
                'ST_DWITHIN', 'ST_COVERS', 'ST_COVEREDBY', 'ST_BUFFER'
            ])
        )

        # Check for FID-only filters from previous spatial steps
        is_fid_only_filter = bool(re.match(
            r'^\s*\(?\s*(["\']?)fid\1\s+(IN\s*\(|=\s*-?\d+)',
            old_subset,
            re.IGNORECASE
        ))

        # Check for style/display expression patterns
        is_style_expression = any(re.search(pattern, old_subset, re.IGNORECASE | re.DOTALL) for pattern in [
            r'AND\s+TRUE\s*\)',              # Rule-based style
            r'THEN\s+true\b',                # CASE THEN true
            r'THEN\s+false\b',               # CASE THEN false
            r'coalesce\s*\([^)]+,\s*\'',     # Display expression
            r'SELECT\s+CASE\s+',             # SELECT CASE expression
            r'\(\s*CASE\s+WHEN\s+.+THEN\s+true',  # CASE WHEN ... THEN true
        ])

        # Apply strategy
        if is_geometric_filter:
            logger.info(f"🔄 Existing subset on {layer.name()} contains GEOMETRIC filter - will be REPLACED")
            logger.info(f"  → Existing: '{old_subset[:100]}...'")
            logger.info("  → Reason: Cannot nest geometric filters (EXISTS, ST_*, __source)")
            return None, None

        elif is_fid_only_filter:
            logger.info(f"🔄 Existing subset on {layer.name()} is FID filter from PREVIOUS spatial step")
            logger.info(f"  → Existing: '{old_subset[:100]}...'")
            logger.info("  → Strategy: Keep for cache intersection, but DON'T combine in SQL")
            return old_subset, None  # combine_operator=None tells backend not to combine

        elif is_style_expression:
            logger.info(f"🔄 Existing subset on {layer.name()} contains STYLE expression - will be REPLACED")
            logger.info(f"  → Existing: '{old_subset[:100]}...'")
            logger.info("  → Reason: Style expressions cause type mismatch errors")
            return None, None

        else:
            # Simple attribute filter - combine with new geometric filter
            logger.info(f"✅ Existing subset on {layer.name()} is ATTRIBUTE filter - will be COMBINED")
            logger.info(f"  → Existing: '{old_subset[:100]}...'")
            logger.info("  → Reason: Preserving user's attribute filter with geometric filter")
            return old_subset, combine_operator

    def _get_combine_operator(self) -> Optional[str]:
        """
        Get the logical operator for combining filters.

        Returns:
            str: 'AND', 'OR', 'AND NOT', or None
        """
        # This would come from task_parameters or parent_task
        # Placeholder implementation
        return self.task_parameters.get('combine_operator', 'AND')

    def _try_fallback_backend(
        self,
        layer: QgsVectorLayer,
        layer_props: Dict[str, Any],
        backend_name: str,
        source_geometries: Dict[str, Any],
        expression_builder: Any
    ) -> bool:
        """
        Try OGR backend when primary backend fails to build expression.

        This handles cases like:
        - Spatialite source geometry not available
        - PostgreSQL WKT too large for embedding

        Args:
            layer: Layer to filter
            layer_props: Layer metadata
            backend_name: Name of backend that failed
            source_geometries: Available source geometries
            expression_builder: ExpressionBuilder instance

        Returns:
            bool: True if fallback succeeded, False otherwise
        """
        if backend_name not in ('spatialite', 'postgresql'):
            return False

        logger.warning(f"⚠️ {backend_name.upper()} expression building failed for {layer.name()}")
        logger.warning("  → Attempting OGR fallback (QGIS processing)...")

        try:
            ogr_backend = BackendFactory.get_backend('ogr', layer, self.task_parameters)
            ogr_source_geom = source_geometries.get(PROVIDER_OGR)

            if not ogr_source_geom:
                logger.error("  ✗ OGR source geometry not available")
                return False

            ogr_expression = expression_builder.build_backend_expression(
                backend=ogr_backend,
                layer_props=layer_props,
                source_geom=ogr_source_geom
            )

            if not ogr_expression:
                logger.error("  ✗ Could not build OGR expression for fallback")
                return False

            logger.info(f"  → OGR expression built: {ogr_expression[:100]}...")

            # Get subset strategy
            old_subset, combine_operator = self._determine_subset_strategy(layer)

            # Apply OGR filter
            result = ogr_backend.apply_filter(layer, ogr_expression, old_subset, combine_operator)

            self._collect_backend_warnings(ogr_backend)

            if result:
                logger.info(f"✓ OGR fallback SUCCEEDED for {layer.name()}")
                self.task_parameters['actual_backends'][layer.id()] = 'ogr'
                return True
            else:
                logger.error(f"✗ OGR fallback also FAILED for {layer.name()}")
                return False

        except Exception as e:
            logger.error(f"✗ OGR fallback exception: {e}", exc_info=True)
            return False

    def _handle_backend_failure(
        self,
        layer: QgsVectorLayer,
        layer_props: Dict[str, Any],
        backend_name: str,
        source_geometries: Dict[str, Any],
        expression_builder: Any,
        old_subset: Optional[str],
        combine_operator: Optional[str]
    ) -> bool:
        """
        Handle backend failure with intelligent OGR fallback.

        Triggers fallback for:
        - Forced backends that fail (layer may not support backend)
        - Spatialite failures (functions not available, geometry issues)
        - PostgreSQL failures (timeout, connection, SQL errors)

        Args:
            layer: Layer that failed to filter
            layer_props: Layer metadata
            backend_name: Name of backend that failed
            source_geometries: Available source geometries
            expression_builder: ExpressionBuilder instance
            old_subset: Existing subset string
            combine_operator: Combination operator

        Returns:
            bool: True if fallback succeeded, False otherwise
        """
        forced_backends = self.task_parameters.get('forced_backends', {})
        was_forced = layer.id() in forced_backends

        # Check if this is large PostgreSQL table (skip fallback)
        feature_count = layer.featureCount()
        if feature_count is None or feature_count < 0:
            feature_count = 0

        is_large_pg_table = (
            backend_name == 'postgresql' and
            layer.providerType() == 'postgres' and
            feature_count > 100000
        )

        if is_large_pg_table:
            logger.error(f"⚠️ PostgreSQL query FAILED for large table {layer.name()} ({feature_count:,} features)")
            logger.error("  → OGR fallback is NOT available for tables > 100k features")
            logger.error("  → Solutions: Reduce source count, increase timeout, add spatial index")
            QgsMessageLog.logMessage(
                f"⚠️ {layer.name()}: PostgreSQL timeout on {feature_count:,} features",
                "FilterMate", Qgis.Critical
            )
            return False

        # Log reason for fallback
        if was_forced:
            logger.warning(f"⚠️ {backend_name.upper()} backend FAILED for forced layer {layer.name()}")
        elif backend_name == 'postgresql':
            logger.warning(f"⚠️ PostgreSQL backend FAILED for {layer.name()}")
            logger.warning("  → Query may have timed out or connection failed")
        else:
            logger.warning(f"⚠️ {backend_name.upper()} backend FAILED for {layer.name()}")

        logger.warning("  → Attempting OGR fallback...")
        QgsMessageLog.logMessage(
            f"🔄 {layer.name()}: Attempting OGR fallback...",
            "FilterMate", Qgis.Info
        )

        try:
            # Get OGR backend
            ogr_backend = BackendFactory.get_backend('ogr', layer, self.task_parameters, force_ogr=True)
            ogr_source_geom = source_geometries.get(PROVIDER_OGR)

            if not ogr_source_geom:
                logger.error("  ✗ OGR source geometry not available for fallback")
                return False

            # Build OGR expression
            ogr_expression = expression_builder.build_backend_expression(
                backend=ogr_backend,
                layer_props=layer_props,
                source_geom=ogr_source_geom
            )

            if not ogr_expression:
                logger.error("  ✗ Could not build OGR expression for fallback")
                return False

            logger.info(f"  → OGR expression built: {ogr_expression[:100]}...")

            # Apply OGR filter
            ogr_backend._is_ogr_fallback = True  # Skip spurious cancellation checks
            result = ogr_backend.apply_filter(layer, ogr_expression, old_subset, combine_operator)

            self._collect_backend_warnings(ogr_backend)

            if result:
                logger.info(f"✓ OGR fallback SUCCEEDED for {layer.name()}")
                QgsMessageLog.logMessage(
                    f"✓ OGR fallback SUCCEEDED for {layer.name()}",
                    "FilterMate", Qgis.Info
                )
                self.task_parameters['actual_backends'][layer.id()] = 'ogr'
                return True
            else:
                logger.error(f"✗ OGR fallback also FAILED for {layer.name()}")
                QgsMessageLog.logMessage(
                    f"⚠️ OGR fallback FAILED for {layer.name()}",
                    "FilterMate", Qgis.Warning
                )
                return False

        except Exception as e:
            logger.error(f"✗ OGR fallback exception: {e}", exc_info=True)
            QgsMessageLog.logMessage(
                f"⚠️ OGR fallback exception for {layer.name()}: {str(e)[:100]}",
                "FilterMate", Qgis.Warning
            )
            return False

    def _collect_backend_warnings(self, backend: Any) -> None:
        """
        Collect user warnings from backend for display in finished().

        Args:
            backend: Backend instance that may have warnings
        """
        if hasattr(backend, 'user_warnings') and backend.user_warnings:
            if not hasattr(self.parent_task, 'backend_warnings'):
                self.parent_task.backend_warnings = []
            self.parent_task.backend_warnings.extend(backend.user_warnings)

    def _log_filter_success(self, layer: QgsVectorLayer, backend_name: str) -> None:
        """
        Log successful filter application.

        Args:
            layer: Filtered layer
            backend_name: Backend that applied the filter
        """
        final_expression = layer.subsetString()
        feature_count = layer.featureCount()

        logger.debug(f"✓ orchestrate_geometric_filter: {layer.name()} → backend returned SUCCESS")
        logger.info(f"  - Features after filter: {feature_count:,}")
        logger.info(f"  - Subset string applied: {final_expression[:200] if final_expression else '(empty)'}")
        logger.info(f"  - Layer is valid: {layer.isValid()}")
        logger.info(f"  - Provider: {layer.providerType()}")
        logger.info(f"  - CRS: {layer.crs().authid()}")

        # Trigger layer repaint
        try:
            layer.triggerRepaint()
            logger.debug("  - Triggered layer repaint")
        except Exception as e:
            logger.warning(f"  - Could not trigger repaint: {e}")

        # Warn if no features after filtering
        if feature_count == 0:
            logger.warning(
                f"⚠️ WARNING: {layer.name()} has ZERO features after filtering!\n"
                f"   Provider: {backend_name}, Expression length: {len(final_expression) if final_expression else 0}"
            )

        logger.info(f"✓ Successfully filtered {layer.name()}: {feature_count:,} features match")

    def _log_filter_failure(self, layer: QgsVectorLayer, backend_name: str) -> None:
        """
        Log filter application failure.

        Args:
            layer: Layer that failed to filter
            backend_name: Backend that failed
        """
        logger.error(f"✗ Backend returned FAILURE for {layer.name()}")
        logger.error("  - Check backend logs for details")

        QgsMessageLog.logMessage(
            f"orchestrate_geometric_filter ✗ {layer.name()} → backend returned FAILURE",
            "FilterMate", Qgis.Warning
        )
