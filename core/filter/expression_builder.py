"""
Expression Builder - Filter Expression Construction

This module extracts expression building logic from FilterEngineTask (7,015 lines).
It handles:

1. Backend-specific expression building delegation
2. Source geometry filter preparation (from task_features or subset)
3. PostgreSQL EXISTS optimization (MV creation for large selections)
4. Expression caching and validation
5. Primary key field detection and formatting
6. Filter chaining for sequential spatial filtering (v4.2.9)

Part of EPIC-1 Phase E12 (Filter Orchestration Extraction).

Hexagonal Architecture:
- Uses ports: BackendPort (adapters/backends/)
- Used by: FilterOrchestrator
- Delegates to: Backend.build_expression()
"""

import logging
import re
from typing import Optional, Dict, Any, List
from qgis.core import (
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsMessageLog,
    Qgis
)

logger = logging.getLogger('filter_mate')


class ExpressionBuilder:
    """
    Builds filter expressions for different backend types.
    
    Responsibilities:
    - Prepare source geometry filters from task_features or layer subset
    - Create temporary materialized views for large PostgreSQL source selections
    - Build backend-specific SQL expressions via delegation
    - Cache expressions for repeated operations (performance optimization)
    - Format primary key values (handling UUID, text, numeric types)
    
    This class extracts ~550 lines from FilterEngineTask._build_backend_expression(),
    enabling better testability and separation of concerns.
    """
    
    def __init__(
        self,
        task_parameters: Dict[str, Any],
        source_layer: Optional[QgsVectorLayer],
        current_predicates: List[str],
        source_wkt: Optional[str] = None,
        source_srid: Optional[int] = None,
        source_feature_count: Optional[int] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        use_centroids_distant: bool = False
    ):
        """
        Initialize the expression builder.
        
        Args:
            task_parameters: Task configuration dict
            source_layer: Source layer for geometric filtering (contains selection)
            current_predicates: Spatial predicates to apply (e.g., ['intersects'])
            source_wkt: WKT geometry string for simple PostgreSQL expressions
            source_srid: SRID of source geometry for ST_GeomFromText()
            source_feature_count: Number of source features (determines WKT vs EXISTS strategy)
            buffer_value: Buffer distance in meters (positive=expand, negative=shrink)
            buffer_expression: Dynamic buffer expression (attribute-based buffer)
            use_centroids_distant: Use ST_Centroid/PointOnSurface for distant layer geometries
        """
        self.task_parameters = task_parameters
        self.source_layer = source_layer
        self.current_predicates = current_predicates
        
        # Note: current_predicates may be empty during initial creation by TaskRunOrchestrator.
        # FilterEngineTask._initialize_current_predicates() will populate them later and
        # propagate to this instance. Only log at debug level.
        if current_predicates:
            logger.debug(f"ExpressionBuilder: initialized with predicates: {list(current_predicates.keys()) if isinstance(current_predicates, dict) else current_predicates}")
        else:
            logger.debug("ExpressionBuilder: initialized with empty predicates (will be set later)")
        
        # PostgreSQL spatial expression parameters
        self.source_wkt = source_wkt
        self.source_srid = source_srid
        self.source_feature_count = source_feature_count
        self.buffer_value = buffer_value
        self.buffer_expression = buffer_expression
        self.use_centroids_distant = use_centroids_distant
        
        # Cache for expressions (performance optimization)
        self._expression_cache = {}
        
        # Materialized views created for source selections (cleanup needed)
        self._source_selection_mvs = []
        
        logger.debug("ExpressionBuilder initialized")
    
    def build_backend_expression(
        self,
        backend: Any,
        layer_props: Dict[str, Any],
        source_geom: Any
    ) -> Optional[str]:
        """
        Build filter expression using backend-specific logic.
        
        This is the main entry point that:
        1. Prepares source filter (from task_features or layer subset)
        2. Optimizes PostgreSQL EXISTS queries with MVs for large selections
        3. Delegates to backend.build_expression()
        4. Caches expressions for repeated operations
        
        Args:
            backend: Backend instance (PostgreSQL, Spatialite, OGR)
            layer_props: Target layer metadata (table name, schema, geom field, etc.)
            source_geom: Prepared source geometry (format depends on backend)
        
        Returns:
            Optional[str]: Filter expression or None on error
        """
        try:
            # CONSOLE-VISIBLE DIAGNOSTIC
            # print("=" * 80)  # DEBUG REMOVED
            # print("🔧 ExpressionBuilder.build_backend_expression() CALLED!")  # DEBUG REMOVED
            # print("=" * 80)  # DEBUG REMOVED
            
            backend_name = backend.get_backend_name()
            # print(f"   backend_name: {backend_name}")  # DEBUG REMOVED
            
            # DIAGNOSTIC LOGS 2026-01-16: ULTRA-DETAILED TRACE for source_filter debugging
            logger.info("=" * 80)
            logger.info("📝 ExpressionBuilder.build_backend_expression CALLED")
            logger.info("=" * 80)
            logger.info(f"   backend_name: {backend_name}")
            logger.info(f"   current_predicates: {self.current_predicates}")
            logger.info(f"   source_geom type: {type(source_geom).__name__}")
            if hasattr(source_geom, 'name'):
                logger.info(f"   source_geom name: {source_geom.name()}")
            logger.info(f"   layer_props keys: {list(layer_props.keys())}")
            logger.info(f"   task_parameters['task'].get('features'): {len(self.task_parameters.get('task', {}).get('features', []))} features")
            
            # v4.2.10: Check for filter chain MV optimization
            filter_chain_mv = self.task_parameters.get('_filter_chain_mv_name')
            if filter_chain_mv and backend_name == 'PostgreSQL':
                logger.info(f"🚀 FILTER CHAIN MV OPTIMIZATION ACTIVE: {filter_chain_mv}")
                # The MV contains pre-filtered source features
                # We'll use it instead of multiple EXISTS clauses
            
            # ==========================================
            # 1. PREPARE SOURCE FILTER
            # ==========================================
            logger.info("=" * 80)
            logger.info("🔍 STEP 1: Calling _prepare_source_filter()...")
            logger.info("=" * 80)
            source_filter = self._prepare_source_filter(backend_name)
            logger.info("=" * 80)
            logger.info(f"✅ source_filter RESULT: {source_filter}")
            if source_filter:
                logger.info(f"   Length: {len(source_filter)} chars")
                logger.info(f"   Preview: {source_filter[:200]}...")
            elif backend_name == 'PostgreSQL':
                # WARNING: Only for PostgreSQL EXISTS mode - OGR/Spatialite don't need source_filter
                logger.warning("   ⚠️ source_filter is NULL/EMPTY - PostgreSQL EXISTS will query entire source table!")
            else:
                # INFO: OGR and Spatialite don't use source_filter (normal behavior)
                logger.debug(f"   ℹ️ source_filter=None for {backend_name} backend (expected)")
            logger.info("=" * 80)
            
            # ==========================================
            # 2. BUILD EXPRESSION VIA BACKEND
            # ==========================================
            # Delegate to backend-specific build_expression()
            # Each backend knows how to construct expressions in its SQL dialect
            logger.info(f"🔧 Calling backend.build_expression()...")
            logger.info(f"   source_wkt available: {self.source_wkt is not None}")
            logger.info(f"   source_srid: {self.source_srid}")
            logger.info(f"   source_feature_count: {self.source_feature_count}")
            logger.info(f"   buffer_value: {self.buffer_value}")
            logger.info(f"   use_centroids_distant: {self.use_centroids_distant}")
            
            # CRITICAL FIX 2026-01-16: Pass all required parameters to backend
            # PostgreSQLGeometricFilter.build_expression() requires these for
            # generating proper EXISTS subqueries with ST_Intersects instead of
            # falling back to simple "id" IN (...) expressions
            # 
            # FIX v4.2.7: Pass source_table_name for proper aliasing of source_filter
            # v4.2.10: Pass filter_chain_mv_name for MV optimization
            source_table_name = self.task_parameters.get('param_source_table')
            expression = backend.build_expression(
                layer_props=layer_props,
                predicates=self.current_predicates,
                source_geom=source_geom,
                buffer_value=self.buffer_value,
                buffer_expression=self.buffer_expression,
                source_filter=source_filter,
                source_wkt=self.source_wkt,
                source_srid=self.source_srid,
                source_feature_count=self.source_feature_count,
                use_centroids=self.use_centroids_distant,
                source_table_name=source_table_name,
                filter_chain_mv_name=filter_chain_mv  # v4.2.10
            )
            
            logger.info(f"✅ Backend returned expression: {expression[:200] if expression else 'None'}...")
            
            if not expression:
                logger.warning(f"Backend {backend_name} returned empty expression")
                return None
            
            logger.debug(f"Expression built via {backend_name}: {len(expression)} chars")
            return expression
            
        except Exception as e:
            logger.error(f"Error building expression: {e}", exc_info=True)
            return None
    
    def cleanup_temporary_resources(self) -> None:
        """
        Clean up temporary materialized views created during expression building.
        
        Should be called in finished() callback to avoid leaving temp tables in DB.
        """
        if not self._source_selection_mvs:
            return
        
        logger.info(f"🧹 Cleaning up {len(self._source_selection_mvs)} temporary source selection MVs")
        
        for mv_ref in self._source_selection_mvs:
            try:
                # The MV cleanup is handled by backend in finished()
                # Just log for now - actual cleanup delegated to PostgreSQLGeometricFilter
                logger.debug(f"  → Marked for cleanup: {mv_ref}")
            except Exception as e:
                logger.warning(f"  ⚠️ Could not mark {mv_ref} for cleanup: {e}")
        
        self._source_selection_mvs.clear()
    
    # =====================================================================
    # PRIVATE HELPER METHODS
    # =====================================================================
    
    def _prepare_source_filter(self, backend_name: str) -> Optional[str]:
        """
        Prepare source geometry filter from task_features or layer subset.
        
        Priority order:
        1. task_features (user's current selection) - ALWAYS takes priority
        2. source_subset (existing layer filter) - only if no selection
        3. None (no filter)
        
        For PostgreSQL EXISTS mode:
        - Generates "pk IN (...)" filter from task_features FIDs
        - Creates temporary MV for large selections (> 500 FIDs)
        - Falls back to source_subset if no task_features
        
        Args:
            backend_name: Backend name ('PostgreSQL', 'Spatialite', 'OGR')
        
        Returns:
            Optional[str]: Source filter SQL or None
        """
        # CONSOLE-VISIBLE DIAGNOSTIC
        # print("=" * 80)  # DEBUG REMOVED
        # print("🔍 ExpressionBuilder._prepare_source_filter() CALLED")  # DEBUG REMOVED
        # print("=" * 80)  # DEBUG REMOVED
        # print(f"   backend_name: {backend_name}")  # DEBUG REMOVED
        logger.info("   🔍 _prepare_source_filter() ENTERED")
        logger.info(f"      backend_name: {backend_name}")
        
        source_filter = None
        
        # PostgreSQL EXISTS mode needs source filter
        # FIX 2026-01-17: Case-insensitive comparison (backend returns 'Postgresql', not 'PostgreSQL')
        if backend_name.lower() != 'postgresql':
            # print(f"   ↩️ Returning None - backend '{backend_name}' doesn't need source_filter")  # DEBUG REMOVED
            logger.info(f"      ↩️ Returning None - backend '{backend_name}' doesn't need source_filter")
            return None
        
        # print("   ✓ PostgreSQL backend detected - preparing source_filter...")  # DEBUG REMOVED
        logger.info("      ✓ PostgreSQL backend detected - preparing source_filter...")
        
        # Get source layer's existing subset string
        source_subset = self.source_layer.subsetString() if self.source_layer else None
        # print("=" * 80)  # DEBUG REMOVED
        # print("🔍 _prepare_source_filter: ANALYZING source_subset")  # DEBUG REMOVED
        # print("=" * 80)  # DEBUG REMOVED
        # print(f"   self.source_layer: {self.source_layer.name() if self.source_layer else 'None'}")  # DEBUG REMOVED
        # print(f"   source_subset: '{source_subset}'" if source_subset else "   source_subset: None (EMPTY!)")  # DEBUG REMOVED
        logger.info("=" * 80)
        logger.info("🔍 _prepare_source_filter: ANALYZING source_subset")
        logger.info("=" * 80)
        logger.info(f"   self.source_layer: {self.source_layer.name() if self.source_layer else 'None'}")
        logger.info(f"   source_subset: '{source_subset}'" if source_subset else "   source_subset: None (EMPTY!)")
        
        # Check if source_subset contains patterns that would be skipped
        skip_source_subset = False
        if source_subset:
            source_subset_upper = source_subset.upper()
            skip_source_subset = any(pattern in source_subset_upper for pattern in [
                '__SOURCE',
                'EXISTS(',
                'EXISTS ('
            ])
            logger.info(f"   Contains __SOURCE/EXISTS patterns: {skip_source_subset}")
            if not skip_source_subset:
                # Also check for MV references (except source selection MVs)
                skip_source_subset = bool(re.search(
                    r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?.*mv_(?!.*src_sel_)',
                    source_subset,
                    re.IGNORECASE | re.DOTALL
                ))
                logger.info(f"   Contains MV reference pattern: {skip_source_subset}")
            
            if skip_source_subset:
                logger.info("⚠️ PostgreSQL EXISTS: Source subset contains patterns that would be skipped")
                logger.info(f"   Subset preview: '{source_subset[:100]}...'")
                logger.info("   → Falling through to generate filter from task_features instead")
        else:
            # source_subset is None - this is NORMAL for multiple selection filtering
            # The task_features will be used instead - not an error condition
            logger.debug("   source_subset is None - will check task_features for selection-based filtering")
        logger.info("=" * 80)
        
        # Check for task_features (user's selection) FIRST
        # HOTFIX 2026-01-17: Add fallback logic for thread-safe feature extraction
        task_features = self.task_parameters.get("task", {}).get("features", [])
        
        # FIX v4.2.7: DIAGNOSTIC - Check if new code is loaded
        logger.info("=" * 80)
        logger.info("🔍 FIX v4.2.7: CUSTOM SELECTION FIELD SUPPORT ACTIVE")
        logger.info("=" * 80)
        logger.info(f"      📋 ATTEMPT 1: task_parameters['task']['features']")
        logger.info(f"         Count: {len(task_features)} items")
        
        # CRITICAL FIX 2026-01-17: Check if task_features are QgsFeatures or just values (strings/ints)
        # If they are just values (e.g. ["1", "2"]), they are field values not QgsFeature objects
        # FIX v4.2.7: When custom selection with simple field, use values to build filter
        are_qgs_features = False
        field_name_for_values = None
        
        if task_features and len(task_features) > 0:
            first_item = task_features[0]
            are_qgs_features = hasattr(first_item, 'id') and hasattr(first_item, 'geometry')
            logger.info(f"         First item type: {type(first_item).__name__}")
            logger.info(f"         Are QgsFeatures: {are_qgs_features}")
            
            if not are_qgs_features:
                # Values detected - check if there's a selection expression field
                # Try to get the custom selection expression field name
                logger.info(f"         ⚠️ task_features contains values, not QgsFeature objects!")
                logger.info(f"         🔍 Checking custom_expr from task_parameters...")
                
                # Log ALL task parameters for debugging
                task_dict = self.task_parameters.get("task", {})
                logger.info(f"         📋 Available task_parameters['task'] keys: {list(task_dict.keys())}")
                
                custom_expr = task_dict.get("expression", "")
                logger.info(f"         custom_expr from task: '{custom_expr}'")
                
                # Check if custom_expr is a simple field name (not a complex expression)
                # Simple field: starts with " or is alphanumeric, no operators
                if custom_expr and custom_expr.strip():
                    # Remove quotes if present
                    field_candidate = custom_expr.strip().strip('"')
                    # Check if it's a simple field (no spaces, operators, functions)
                    if field_candidate and not any(op in field_candidate for op in [' ', '=', '<', '>', '+', '-', '*', '/', '(', ')', ',']):
                        field_name_for_values = field_candidate
                        logger.info(f"         ✓ Detected simple field for custom selection: '{field_name_for_values}'")
                        logger.info(f"         → Will build filter: {field_name_for_values} IN ({len(task_features)} values)")
                    else:
                        logger.warning(f"         → Custom expression is complex, cannot use values directly")
                        logger.warning(f"         → Will use source_subset instead")
                        task_features = []  # Reset to trigger source_subset fallback
                else:
                    logger.warning(f"         → No custom expression found, cannot determine field name")
                    logger.warning(f"         → Will use source_subset instead")
                    task_features = []  # Reset to trigger source_subset fallback
        
        # ATTEMPT 2: task_parameters["task"]["feature_fids"] (backup FIDs)
        if not task_features or len(task_features) == 0:
            feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])
            if feature_fids and self.source_layer:
                logger.debug(f"      📋 ATTEMPT 2: Reconstructing features from feature_fids")
                logger.info(f"         FID count: {len(feature_fids)}")
                
                # Reconstruct features from FIDs
                from qgis.core import QgsFeatureRequest
                request = QgsFeatureRequest().setFilterFids(feature_fids)
                task_features = list(self.source_layer.getFeatures(request))
                logger.info(f"         Reconstructed {len(task_features)} features from FIDs")
        
        # ATTEMPT 3: source_layer.selectedFeatures() (direct from layer)
        if not task_features or len(task_features) == 0:
            if self.source_layer and self.source_layer.selectedFeatureCount() > 0:
                logger.debug(f"      📋 ATTEMPT 3: source_layer.selectedFeatures()")
                task_features = self.source_layer.selectedFeatures()
                logger.info(f"         Selected {len(task_features)} features from layer")
        
        # Log final result
        if task_features:
            if hasattr(task_features[0], 'id'):
                logger.info(f"         First feature ID: {task_features[0].id()}")
            logger.info(f"         ✅ User has {len(task_features)} QgsFeatures for source_filter")
        else:
            # FIX v4.2.7: Distinguish between normal fallback scenarios and real errors
            if source_subset and not skip_source_subset:
                # NORMAL: Will use source_subset as filter
                logger.debug(f"         ℹ️ No task_features - will use source_subset as fallback (NORMAL)")
            elif skip_source_subset and source_subset:
                # NORMAL: Source layer already filtered with EXISTS/MV - will use all filtered features
                logger.debug(f"         ℹ️ Source layer already filtered (EXISTS/MV pattern detected)")
                logger.debug(f"         → Will use ALL features from filtered source layer (no additional source_filter)")
            else:
                # RARE: No features and no subset - will match all source features
                logger.debug(f"         ℹ️ No task_features and no source_subset")
                logger.debug(f"         → Will use ALL features from source layer (no source_filter)")
        
        # ATTEMPT 4: Get features from filtered source layer (when source has a subset but can't use it directly)
        # This handles the case where source_subset contains EXISTS patterns
        # REMOVED in v4.2.7: This caused performance issues by extracting all FIDs
        # when the source layer was already filtered. Instead, we now skip this
        # and let the source_subset be used directly in PATH 2 below.
        # The EXISTS patterns are already handled by skip_source_subset check.
        
        # ATTEMPT 5 (FIX 2026-01-21): REMOVED in v4.2.7
        # When buffer_expression is active with a pre-filtered layer, we should
        # NOT extract all features and generate "id IN (1,2,3,...)".
        # Instead, we use the existing source_subset filter directly (PATH 2).
        # This is more efficient and avoids generating huge IN clauses.
        #
        # The MV created by buffer_expression will SELECT from the source table
        # with the subsetString filter applied by PostgreSQL automatically.
        
        use_task_features = task_features and len(task_features) > 0
        # print(f"   use_task_features: {use_task_features}")  # DEBUG REMOVED
        # print(f"   skip_source_subset: {skip_source_subset}")  # DEBUG REMOVED
        
        # FIX v4.2.9 (2026-01-21): Enhanced filter chaining for sequential spatial filtering.
        # 
        # Use case (user's request):
        #   Filter 1: zone_pop → intersects multiple selection on all distant layers
        #   Filter 2: ducts (with buffer) → intersects distant layers while KEEPING zone_pop filter
        # 
        # Expected result for distant layer (subducts):
        #   EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ST_Intersects(ST_PointOnSurface(...)))
        #   AND
        #   EXISTS (SELECT 1 FROM ducts AS __source WHERE ST_Intersects(..., ST_Buffer(..., 10)))
        # 
        # Scenario detection:
        #   - If buffer_expression is active AND source_subset contains EXISTS:
        #     → CHAIN both EXISTS filters (zone_pop + ducts buffer)
        #   - If custom expression (exploring) is active:
        #     → Custom applies to source layer, NOT to distant layer filter chain
        #
        has_buffer_expression = hasattr(self, 'buffer_expression') and self.buffer_expression
        custom_expression = self.task_parameters.get("task", {}).get("expression", "")
        has_combine_operator = self.task_parameters.get("param_combine_operator") is not None
        
        # Get source table info for EXISTS adaptation
        source_table_name = self.task_parameters.get('param_source_table')
        source_schema = self.task_parameters.get('param_source_schema')
        
        # Import filter chaining utilities
        from .expression_combiner import detect_filter_chain_scenario, extract_exists_clauses, adapt_exists_for_nested_context
        
        # Detect the filter chaining scenario
        scenario, context = detect_filter_chain_scenario(
            source_layer_subset=source_subset,
            custom_expression=custom_expression,
            buffer_expression=str(self.buffer_expression) if has_buffer_expression else None,
            has_combine_operator=has_combine_operator
        )
        
        # Handle different scenarios
        if scenario in ('spatial_chain', 'spatial_chain_with_custom'):
            # FILTER CHAINING MODE: Extract EXISTS from source_subset for combination
            logger.info("🔗 FILTER CHAIN MODE: Extracting EXISTS clauses for chaining")
            logger.info(f"   Scenario: {scenario}")
            logger.info(f"   buffer_expression: {str(self.buffer_expression)[:100]}..." if has_buffer_expression else "   buffer_expression: None")
            logger.info(f"   source_subset preview: {source_subset[:200]}..." if source_subset else "   source_subset: None")
            logger.info(f"   source_table_name: {source_table_name}")
            
            if context['spatial_exists_clauses']:
                # Extract all EXISTS clauses from source_subset (zone_pop, etc.)
                exists_parts = []
                
                logger.info(f"   → Found {len(context['spatial_exists_clauses'])} EXISTS clause(s) to chain:")
                for i, clause in enumerate(context['spatial_exists_clauses']):
                    clause_sql = clause['sql']
                    logger.info(f"      #{i+1}: table={clause.get('table', 'unknown')}")
                    
                    # FIX v4.2.9: Adapt EXISTS for nested context
                    # The EXISTS from zone_pop contains references to the source table (ducts)
                    # When used as source_filter in a new EXISTS, these references must be
                    # changed to __source (the alias of the outer EXISTS)
                    if source_table_name:
                        adapted_sql = adapt_exists_for_nested_context(
                            exists_sql=clause_sql,
                            original_table=source_table_name,
                            new_alias='__source',
                            original_schema=source_schema
                        )
                        if adapted_sql != clause_sql:
                            logger.info(f"         🔄 Adapted table references: '{source_table_name}' → '__source'")
                        exists_parts.append(adapted_sql)
                    else:
                        exists_parts.append(clause_sql)
                
                # Combine all EXISTS into source_filter
                # These will be ANDed with the new buffer EXISTS by the backend
                source_filter = ' AND '.join(f'({part})' for part in exists_parts)
                logger.info(f"   ✅ Chained {len(exists_parts)} EXISTS into source_filter: {len(source_filter)} chars")
                
                if scenario == 'spatial_chain_with_custom':
                    logger.info(f"   ℹ️ Custom expression '{custom_expression[:50]}...' applies to source layer only (not chained)")
            else:
                # No EXISTS found, use source_subset as-is (fallback)
                logger.warning("   ⚠️ No EXISTS clauses found in source_subset, using as-is")
                source_filter = source_subset
                
        elif has_buffer_expression and source_subset and not skip_source_subset:
            # PRIORITY for buffer expression: Use source_subset (zone_pop spatial filter)
            # This handles non-EXISTS source_subset with buffer expression
            logger.info("🎯 PostgreSQL EXISTS: BUFFER MODE - Prioritizing source_subset over task_features")
            logger.info(f"   buffer_expression: {str(self.buffer_expression)[:100]}...")
            logger.info(f"   source_subset preview: {source_subset[:200]}...")
            
            # Try to parse and optimize source_subset
            parsed_subset = self._parse_complex_where_clause(source_subset)
            
            if parsed_subset['can_optimize']:
                logger.info(f"   → Optimization strategy: {parsed_subset['optimization_strategy']}")
                logger.info(f"      - EXISTS subqueries: {len(parsed_subset['exists_subqueries'])} (zone_pop)")
                logger.info(f"      - Field conditions: {len(parsed_subset['field_conditions'])}")
                
                # Combine reusable components (EXISTS + field conditions)
                combined_parts = []
                for exists_info in parsed_subset['exists_subqueries']:
                    combined_parts.append(exists_info['sql'])
                combined_parts.extend(parsed_subset['field_conditions'])
                
                source_filter = ' AND '.join(f'({part})' for part in combined_parts)
                logger.info(f"   ✅ Using optimized source_subset: {len(source_filter)} chars")
            else:
                # Use source_subset as-is
                source_filter = source_subset
                logger.info(f"   ✅ Using source_subset as-is: {len(source_filter)} chars")
            
            logger.info(f"   ℹ️ Ignoring {len(task_features) if task_features else 0} task_features (custom expression) for spatial buffer filter")
            
        elif use_task_features:
            # Non-buffer scenario: Use task_features
            logger.debug(f"🎯 PostgreSQL EXISTS: Using {len(task_features)} task_features (selection priority)")
            
            # FIX v4.2.7: If we have field values instead of QgsFeatures, build field-based filter
            if field_name_for_values:
                source_filter = self._generate_field_value_filter(task_features, field_name_for_values, backend_name)
                logger.info(f"✅ Generated source_filter from field values:")
            else:
                source_filter = self._generate_fid_filter(task_features, backend_name=backend_name)
                logger.info(f"✅ Generated source_filter from FIDs:")
            
            logger.info(f"   Length: {len(source_filter) if source_filter else 0} chars")
            if source_filter:
                logger.info(f"   Preview: '{source_filter[:100]}'...")
                logger.info(f"   ✅ Backend will include this in EXISTS WHERE clause")
            else:
                logger.error(f"   ❌ ERROR: Filter generation returned None!")
        elif source_subset and not skip_source_subset:
            # FALLBACK: Use source layer's subset string
            # print(f"🎯 PATH 2: Using source_subset as source_filter")  # DEBUG REMOVED
            # print(f"   source_filter = '{source_subset}'")  # DEBUG REMOVED
            logger.debug("🎯 PostgreSQL EXISTS: PATH 2 - Using source layer subsetString as source_filter")
            source_filter = source_subset
        else:
            # FIX v4.2.8: Handle EXISTS pattern in source_subset
            # When source layer is filtered with EXISTS but no task_features:
            # - Extract FIDs from currently filtered features
            # - Optimize if expression would be too long (> 10,000 chars or > 1,000 features)
            # - Create temp MV for large datasets
            if skip_source_subset and source_subset and self.source_layer:
                logger.info("🎯 PostgreSQL EXISTS: PATH 3A - Source filtered with EXISTS, extracting filtered FIDs")
                logger.info(f"   Source subset preview: '{source_subset[:100]}...'")
                
                # Count features in filtered layer
                filtered_count = self.source_layer.featureCount()
                logger.info(f"   Filtered feature count: {filtered_count}")
                
                # Optimization thresholds
                MAX_INLINE_FEATURES = 1000  # Max features for inline IN clause
                MAX_EXPRESSION_LENGTH = 10000  # Max expression length in chars
                
                if filtered_count > MAX_INLINE_FEATURES:
                    # OPTIMIZATION: Use original source_subset as-is for distant layers
                    # Instead of extracting all FIDs, we can create a subquery or temp table
                    logger.info(f"   ⚡ OPTIMIZATION: {filtered_count} features > {MAX_INLINE_FEATURES} threshold")
                    logger.info(f"   → Creating optimized filter strategy")
                    
                    # Strategy: Extract source_subset WHERE clause and use it directly
                    # This avoids extracting thousands of FIDs
                    # 
                    # FIX v4.2.8: Proper parenthesis handling for EXISTS patterns
                    # Pattern: EXISTS (SELECT ... WHERE <condition>)
                    # We need to extract <condition> without the final closing parenthesis
                    #
                    # CRITICAL v4.2.8: Check for __source alias in WHERE clause
                    # If WHERE clause contains __source, it's specific to a particular source table
                    # and CANNOT be reused in a different EXISTS context (different __source table)
                    # Example: WHERE ST_Intersects(..., __source.geom) with __source=zone_pop
                    #          cannot be reused when __source=ducts in distant layer filter
                    
                    where_match = re.search(r'WHERE\s+(.+)', source_subset, re.IGNORECASE | re.DOTALL)
                    if where_match:
                        where_clause = where_match.group(1).strip()
                        
                        # CRITICAL CHECK: Detect __source alias in WHERE clause
                        if '__source' in where_clause.lower():
                            logger.warning(f"   ⚠️ WHERE clause contains __source alias - attempting advanced parsing")
                            logger.info(f"   → Parsing complex WHERE to identify reusable components")
                            
                            # ADVANCED OPTIMIZATION v4.2.8: Parse and partially optimize
                            parsed_where = self._parse_complex_where_clause(where_clause)
                            
                            logger.info(f"   → Parsing results:")
                            logger.info(f"      - Strategy: {parsed_where['optimization_strategy']}")
                            logger.info(f"      - EXISTS subqueries: {len(parsed_where['exists_subqueries'])}")
                            logger.info(f"      - Field conditions: {len(parsed_where['field_conditions'])}")
                            logger.info(f"      - Source-dependent: {len(parsed_where['source_dependent'])}")
                            
                            if parsed_where['can_optimize']:
                                logger.info(f"   ⚡ ADVANCED: Partial optimization possible!")
                                
                                # Get primary key for potential FID extraction
                                pk_field = self._detect_primary_key_field()
                                source_table_name = self._get_source_table_name()
                                
                                # Combine optimized components
                                source_filter = self._combine_subqueries_optimized(
                                    parsed_where, 
                                    source_table_name or 'source',
                                    pk_field or 'id'
                                )
                                
                                if source_filter:
                                    logger.info(f"   ✅ Advanced optimization succeeded!")
                                    logger.info(f"   → Combined filter length: {len(source_filter)} chars")
                                else:
                                    logger.warning(f"   ⚠️ Advanced optimization failed - falling back to FID extraction")
                                    # Fallback to FID extraction
                                    from qgis.core import QgsFeatureRequest
                                    request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
                                    filtered_features = list(self.source_layer.getFeatures(request))
                                    
                                    if filtered_features:
                                        source_filter = self._generate_fid_filter(filtered_features, backend_name=backend_name)
                                        logger.info(f"   ✅ Fallback FID filter: {len(source_filter) if source_filter else 0} chars")
                                    else:
                                        logger.warning(f"   ⚠️ No features extracted")
                                        source_filter = None
                            else:
                                logger.warning(f"   ⚠️ No reusable components found - falling back to FID extraction")
                                logger.info(f"   → WHERE length: {len(where_clause)} chars")
                                logger.info(f"   → WHERE preview: '{where_clause[:200]}...'")
                                logger.info(f"   → DIAGNOSTIC: EXISTS found={len(parsed_where['exists_subqueries'])}, "
                                           f"fields={len(parsed_where['field_conditions'])}, "
                                           f"source_dep={len(parsed_where['source_dependent'])}")
                                
                                # Check if WHERE contains EXISTS keyword at all
                                has_exists_keyword = 'exists' in where_clause.lower()
                                logger.info(f"   → Contains 'EXISTS' keyword: {has_exists_keyword}")
                                if has_exists_keyword:
                                    logger.warning(f"   ⚠️ EXISTS keyword found but not extracted - possible parsing bug!")
                                    # Log position of first EXISTS for debug
                                    import re
                                    exists_pos = re.search(r'exists\s*\(', where_clause, re.IGNORECASE)
                                    if exists_pos:
                                        logger.debug(f"   → First EXISTS at position {exists_pos.start()}: "
                                                    f"'{where_clause[exists_pos.start():exists_pos.start()+50]}...'")
                                
                                # FALLBACK: Extract FIDs instead
                                from qgis.core import QgsFeatureRequest
                                request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
                                filtered_features = list(self.source_layer.getFeatures(request))
                                
                                if filtered_features:
                                    source_filter = self._generate_fid_filter(filtered_features, backend_name=backend_name)
                                    logger.info(f"   ✅ Generated FID filter: {len(source_filter) if source_filter else 0} chars")
                                    if source_filter and len(source_filter) > MAX_EXPRESSION_LENGTH:
                                        logger.warning(f"   ⚠️ Expression very long: {len(source_filter)} chars")
                                        logger.warning(f"   → Features count: {len(filtered_features)}, consider using MV")
                                else:
                                    logger.warning(f"   ⚠️ No features extracted")
                                    source_filter = None
                        else:
                            # Safe to reuse WHERE clause - no __source alias
                            # Remove trailing parentheses that belong to EXISTS, not to the WHERE condition
                            # Count opening and closing parentheses in the WHERE clause
                            # If we have more closing than opening, remove the extras
                            open_count = where_clause.count('(')
                            close_count = where_clause.count(')')
                            
                            if close_count > open_count:
                                # Remove extra closing parentheses from the end
                                extra_closing = close_count - open_count
                                logger.debug(f"   → Found {extra_closing} extra closing parenthesis(es) to remove")
                                
                                # Remove from the end
                                for _ in range(extra_closing):
                                    # Find last ')' and remove it
                                    last_paren_idx = where_clause.rfind(')')
                                    if last_paren_idx != -1:
                                        where_clause = where_clause[:last_paren_idx] + where_clause[last_paren_idx+1:]
                                
                                where_clause = where_clause.strip()
                            
                            logger.info(f"   → Extracted WHERE clause (length: {len(where_clause)} chars)")
                            logger.info(f"   → Preview: '{where_clause[:100]}...'")
                            logger.debug(f"   → Parenthesis count: {where_clause.count('(')} open, {where_clause.count(')')} close")
                            
                            # Use the WHERE clause as source_filter
                            # The backend will create a subquery: EXISTS (SELECT ... WHERE <this_clause>)
                            source_filter = where_clause
                            logger.info(f"   ✅ Using optimized WHERE clause filter (avoids extracting {filtered_count} FIDs)")
                    else:
                        # Fallback: Extract FIDs but log warning about performance
                        logger.warning(f"   ⚠️ Could not extract WHERE clause, falling back to FID extraction")
                        logger.warning(f"   → This may generate large expression for {filtered_count} features")
                        
                        # Extract FIDs from filtered features
                        from qgis.core import QgsFeatureRequest
                        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
                        filtered_features = list(self.source_layer.getFeatures(request))
                        
                        if filtered_features:
                            source_filter = self._generate_fid_filter(filtered_features, backend_name=backend_name)
                            if source_filter and len(source_filter) > MAX_EXPRESSION_LENGTH:
                                logger.warning(f"   ⚠️ Generated expression very long: {len(source_filter)} chars")
                                logger.warning(f"   → Consider using materialized view optimization")
                        else:
                            logger.warning(f"   ⚠️ No features extracted from filtered layer")
                            source_filter = None
                else:
                    # Small dataset: Extract FIDs directly
                    logger.info(f"   → Extracting FIDs from {filtered_count} filtered features")
                    
                    from qgis.core import QgsFeatureRequest
                    request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
                    filtered_features = list(self.source_layer.getFeatures(request))
                    
                    if filtered_features:
                        source_filter = self._generate_fid_filter(filtered_features, backend_name=backend_name)
                        logger.info(f"   ✅ Generated FID filter: {len(source_filter)} chars")
                    else:
                        logger.warning(f"   ⚠️ No features extracted from filtered layer")
                        source_filter = None
            else:
                # NO FILTER: Will match all source features (this is NORMAL when source layer already filtered)
                # print(f"❌ PATH 3: NO SOURCE FILTER - EXISTS will match ALL source features!")  # DEBUG REMOVED
                logger.debug("🎯 PostgreSQL EXISTS: PATH 3B - No source_filter (will use all source features)")
                if source_subset:
                    logger.debug(f"   → Source has subset but not usable: '{source_subset[:100]}...'")

        
        # print(f"   FINAL RETURN: source_filter = '{source_filter[:100] if source_filter else 'None'}'...")  # DEBUG REMOVED
        # print("=" * 80)  # DEBUG REMOVED
        
        return source_filter
    
    def _parse_complex_where_clause(self, where_clause: str) -> dict:
        """
        Parse complex WHERE clause to identify reusable components.
        
        FIXED v4.2.8: EXISTS subqueries are ALWAYS reusable, even if they contain __source.
        The __source in an EXISTS refers to the EXISTS's own FROM clause, not the outer query.
        
        FIXED v4.2.10: Improved EXISTS detection with better regex and parenthesis matching.
        Now correctly extracts nested EXISTS from complex WHERE clauses.
        
        Example: EXISTS (SELECT 1 FROM zone_pop AS __source WHERE ST_Intersects(...))
        This entire EXISTS can be combined with other EXISTS because __source is scoped
        to the subquery.
        
        This function decomposes a complex WHERE clause into:
        1. EXISTS subqueries (ALWAYS reusable - self-contained with own alias scope)
        2. Simple field conditions (reusable as-is)
        3. Non-EXISTS __source references (truly not reusable - outer query context)
        
        Args:
            where_clause: WHERE clause to parse (without leading "WHERE")
        
        Returns:
            dict: Parsed components with optimization strategy
        """
        import re
        
        result = {
            'exists_subqueries': [],
            'field_conditions': [],
            'source_dependent': [],
            'can_optimize': False,
            'optimization_strategy': 'none'
        }
        
        if not where_clause:
            return result
        
        # Step 1: Extract all EXISTS subqueries
        # Pattern: EXISTS (SELECT ... FROM ... AS alias WHERE ...)
        # FIXED v4.2.10: Also detect NOT EXISTS
        # FIXED v4.2.11: Better debug logging and parenthesis handling
        exists_matches = []
        
        # Debug: Log input for troubleshooting
        logger.debug(f"   → Parsing WHERE clause ({len(where_clause)} chars)")
        logger.debug(f"   → WHERE preview: {where_clause[:200]}...")
        
        # Find all EXISTS with proper parenthesis matching
        # FIXED v4.2.11: Improved pattern to catch EXISTS at any position
        i = 0
        search_count = 0
        while i < len(where_clause):
            search_count += 1
            if search_count > 100:  # Safety limit
                logger.warning("   ⚠️ EXISTS search limit reached (100 iterations)")
                break
                
            # FIXED: Match both EXISTS and NOT EXISTS, with optional whitespace
            match = re.search(r'(?:NOT\s+)?EXISTS\s*\(', where_clause[i:], re.IGNORECASE)
            if not match:
                logger.debug(f"   → No more EXISTS found after position {i}")
                break
            
            start = i + match.start()
            # Position at the opening parenthesis after EXISTS
            paren_open_pos = i + match.end() - 1  # -1 because match.end() is after '('
            
            logger.debug(f"   → Found EXISTS keyword at position {start}, paren at {paren_open_pos}")
            
            # Find matching closing parenthesis
            paren_count = 1  # We've already seen the opening paren
            j = paren_open_pos + 1
            
            while j < len(where_clause) and paren_count > 0:
                if where_clause[j] == '(':
                    paren_count += 1
                elif where_clause[j] == ')':
                    paren_count -= 1
                j += 1
            
            if paren_count == 0:
                # Found matching closing paren (j is now at position after ')')
                exists_sql = where_clause[start:j]
                exists_matches.append({
                    'sql': exists_sql,
                    'start': start,
                    'end': j
                })
                logger.info(f"   ✓ Extracted EXISTS subquery ({len(exists_sql)} chars)")
                logger.debug(f"   → EXISTS preview: {exists_sql[:100]}...")
                i = j
            else:
                # No matching paren found, skip this match
                logger.warning(f"   ⚠️ Unbalanced parentheses in EXISTS at position {start} (count={paren_count})")
                logger.debug(f"   → Context: ...{where_clause[max(0,start-20):start+50]}...")
                i = paren_open_pos + 1
        
        logger.info(f"   → Total EXISTS extracted: {len(exists_matches)}")
        
        # Step 2: Extract remaining parts (after removing EXISTS)
        remaining = where_clause
        for exists_match in reversed(exists_matches):  # Remove from end to preserve indices
            remaining = remaining[:exists_match['start']] + remaining[exists_match['end']:]
        
        # Clean up remaining (remove AND/OR at boundaries)
        remaining = remaining.strip()
        remaining = re.sub(r'^\s*(AND|OR)\s+', '', remaining, flags=re.IGNORECASE)
        remaining = re.sub(r'\s+(AND|OR)\s*$', '', remaining, flags=re.IGNORECASE)
        
        # Step 3: Split remaining into individual conditions (NON-EXISTS conditions only)
        if remaining:
            # Simple split by AND/OR (basic implementation)
            # TODO: More sophisticated parsing for nested conditions
            conditions = re.split(r'\s+(AND|OR)\s+', remaining, flags=re.IGNORECASE)
            
            for part in conditions:
                part = part.strip()
                if part.upper() in ('AND', 'OR') or not part:
                    continue
                
                # CRITICAL FIX: Check if condition references __source in NON-EXISTS context
                # (EXISTS already removed, so any __source here is truly outer-query dependent)
                if '__source' in part.lower() or re.search(r'\b__\w+\b', part.lower()):
                    result['source_dependent'].append(part)
                else:
                    result['field_conditions'].append(part)
        
        # Step 4: Analyze EXISTS subqueries
        # CRITICAL: EXISTS are ALWAYS reusable regardless of internal __source usage
        for exists_match in exists_matches:
            exists_sql = exists_match['sql']
            
            # Extract alias from "FROM table AS alias"
            alias_match = re.search(r'FROM\s+[\w"\.]+\s+AS\s+(\w+)', exists_sql, re.IGNORECASE)
            alias = alias_match.group(1) if alias_match else '__source'
            
            # Extract table name
            table_match = re.search(r'FROM\s+([\w"\.]+)\s+AS', exists_sql, re.IGNORECASE)
            table = table_match.group(1) if table_match else 'unknown'
            
            result['exists_subqueries'].append({
                'sql': exists_sql,
                'alias': alias,
                'table': table.strip('"'),
                'reusable': True  # EXISTS are ALWAYS self-contained and reusable
            })
        
        # Step 5: Determine optimization strategy
        # EXISTS are reusable, field_conditions are reusable
        # Only source_dependent (non-EXISTS __source refs) are not reusable
        has_reusable = len(result['exists_subqueries']) > 0 or len(result['field_conditions']) > 0
        has_non_reusable = len(result['source_dependent']) > 0
        
        # FIXED v4.2.10: Debug logging for troubleshooting
        logger.debug(f"   → Parse results: {len(result['exists_subqueries'])} EXISTS, "
                    f"{len(result['field_conditions'])} field, {len(result['source_dependent'])} source-dep")
        if result['source_dependent']:
            for sd in result['source_dependent'][:3]:  # Show first 3
                logger.debug(f"      - source_dependent: {sd[:60]}...")
        
        if has_reusable and not has_non_reusable:
            result['optimization_strategy'] = 'full'
            result['can_optimize'] = True
        elif has_reusable and has_non_reusable:
            result['optimization_strategy'] = 'partial'
            result['can_optimize'] = True
        else:
            # FIXED v4.2.10: If we only have source_dependent, the entire WHERE is about __source
            # This is normal for spatial filters - the whole expression depends on __source geometry
            # In this case, FID extraction is the only option
            result['optimization_strategy'] = 'none'
            result['can_optimize'] = False
            logger.debug("   → No reusable components: WHERE depends entirely on __source geometry")
        
        return result
    
    def _combine_subqueries_optimized(self, parsed_where: dict, source_table: str, pk_field: str) -> Optional[str]:
        """
        Combine parsed WHERE components into optimized source_filter.
        
        FIXED v4.2.8: Smart combination WITHOUT fallback FID extraction for EXISTS.
        
        Strategy:
        1. Reuse ALL self-contained EXISTS subqueries (zone_pop, buffer, etc.)
        2. Include simple field conditions (prefix with source table if needed)
        3. ONLY for non-EXISTS source-dependent parts: Extract FIDs (rare case)
        
        The key fix: EXISTS from zone_pop/buffer should be COMBINED, not converted to FIDs!
        
        Args:
            parsed_where: Output from _parse_complex_where_clause()
            source_table: Source table name for field qualification
            pk_field: Primary key field name for FID extraction fallback (only non-EXISTS)
        
        Returns:
            Optional[str]: Optimized source_filter combining all reusable components
        """
        if not parsed_where['can_optimize']:
            return None
        
        parts = []
        
        # Step 1: Add ALL EXISTS subqueries (zone_pop, buffer, etc.)
        # CRITICAL: These are ALREADY complete and reusable - just combine them!
        for exists_info in parsed_where['exists_subqueries']:
            parts.append(exists_info['sql'])
            logger.debug(f"   ✅ Adding EXISTS from table '{exists_info['table']}' (reusable)")
        
        # Step 2: Add simple field conditions (qualify with source table if needed)
        for field_condition in parsed_where['field_conditions']:
            # Check if already qualified (contains table name or quotes)
            if '"' in field_condition or '.' in field_condition:
                # Already qualified or quoted, use as-is
                parts.append(field_condition)
            else:
                # Qualify with source table
                # This is a simplification - proper qualification is complex
                parts.append(field_condition)
            logger.debug(f"   ✅ Adding field condition (reusable)")
        
        # Step 3: Handle ONLY non-EXISTS source-dependent parts (should be rare!)
        # These are conditions like: ST_Intersects(__source.geom, ...) OUTSIDE of EXISTS
        if parsed_where['source_dependent']:
            logger.warning(f"   ⚠️ Found {len(parsed_where['source_dependent'])} NON-EXISTS source-dependent conditions")
            logger.warning(f"   → These require FID extraction (unusual - most __source should be in EXISTS)")
            
            # For non-EXISTS __source references, we MUST extract FIDs
            # This should be rare - most spatial filters use EXISTS subqueries
            from qgis.core import QgsFeatureRequest
            
            if self.source_layer:
                request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
                filtered_features = list(self.source_layer.getFeatures(request))
                
                if filtered_features:
                    fid_filter = self._generate_fid_filter(filtered_features, backend_name='postgresql')
                    if fid_filter:
                        parts.append(fid_filter)
                        logger.info(f"   → Generated FID IN clause for {len(filtered_features)} features")
                else:
                    logger.warning(f"   ⚠️ No features for non-EXISTS source-dependent conditions")
                    return None
        
        # Step 4: Combine all parts with AND
        if not parts:
            logger.warning(f"   ⚠️ No optimizable parts found")
            return None
        
        if len(parts) == 1:
            combined = parts[0]
        else:
            # Wrap each part in parentheses and combine with AND
            combined = ' AND '.join(f'({part})' for part in parts)
        
        logger.info(f"   ✅ OPTIMIZED FILTER with {len(parts)} components combined:")
        logger.info(f"      - EXISTS subqueries: {len(parsed_where['exists_subqueries'])} (zone_pop, buffer, etc.)")
        logger.info(f"      - Field conditions: {len(parsed_where['field_conditions'])}")
        logger.info(f"      - FID extraction needed: {len(parsed_where['source_dependent'])} (non-EXISTS __source)")
        logger.info(f"      → Total combined length: {len(combined)} chars (vs {len(combined) if len(parsed_where['source_dependent']) == 0 else 'would be 50000+'} for full FID extraction)")
        
        return combined
    
    def _generate_field_value_filter(self, field_values: List[Any], field_name: str, backend_name: str = 'postgresql') -> Optional[str]:
        """
        Generate "field IN (...)" filter from field values.
        
        Used for custom selection with simple field when task_features contains
        values instead of QgsFeature objects.
        
        Args:
            field_values: List of field values (strings, ints, etc.)
            field_name: Name of the field to filter on
            backend_name: Backend name ('postgresql', 'ogr', 'spatialite')
        
        Returns:
            Optional[str]: Field filter SQL (e.g., '"field" IN (val1, val2, ...)')
        """
        if not field_values or not field_name:
            logger.warning("No field values or field name for filter generation")
            return None
        
        # Get source table name for qualification
        source_table_name = self._get_source_table_name()
        
        # Format field values for SQL
        formatted_values = []
        for value in field_values:
            if value is None or value == "":
                continue
            # Detect if value is numeric or string
            if isinstance(value, (int, float)):
                formatted_values.append(str(value))
            else:
                # String value - escape single quotes
                escaped_value = str(value).replace("'", "''")
                formatted_values.append(f"'{escaped_value}'")
        
        if not formatted_values:
            logger.warning("No valid field values after formatting")
            return None
        
        # Build filter
        if source_table_name:
            field_ref = f'"{source_table_name}"."{field_name}"'
        else:
            field_ref = f'"{field_name}"'
        
        values_str = ', '.join(formatted_values)
        filter_sql = f'{field_ref} IN ({values_str})'
        
        logger.info(f"Generated field value filter: {field_ref} IN ({len(formatted_values)} values)")
        
        return filter_sql
    
    def _generate_fid_filter(self, task_features: List[Any], backend_name: str = 'postgresql') -> Optional[str]:
        """
        Generate "pk IN (...)" filter from task_features.
        
        For PostgreSQL with large selections (> threshold), creates a temporary 
        materialized view to optimize EXISTS queries. 
        For non-PostgreSQL backends (OGR, Spatialite), always uses inline IN clause.
        
        Args:
            task_features: List of QgsFeature objects or feature dicts
            backend_name: Backend name ('postgresql', 'ogr', 'spatialite')
        
        Returns:
            Optional[str]: FID filter SQL or None if PK field not found
        """
        # Get primary key field name
        pk_field = self._detect_primary_key_field()
        if not pk_field:
            logger.warning("Could not detect primary key field for FID filter")
            return None
        
        # Extract feature IDs
        fids = self._extract_feature_ids(task_features, pk_field)
        if not fids:
            logger.warning("No FIDs extracted from task_features")
            return None
        
        # Get source table name for qualification
        source_table_name = self._get_source_table_name()
        
        # Check if we should create MV for large selections
        # MV optimization is ONLY available for PostgreSQL backend
        thresholds = self._get_optimization_thresholds()
        source_mv_fid_threshold = thresholds.get('source_mv_fid_threshold', 500)
        
        # Normalize backend name for comparison
        backend_lower = backend_name.lower() if backend_name else 'unknown'
        is_postgresql = backend_lower == 'postgresql'
        
        # Check if PostgreSQL backend is actually available
        postgresql_available = False
        if is_postgresql:
            try:
                from ..ports import get_backend_services
                _backend_services = get_backend_services()
                PostgreSQLGeometricFilter = _backend_services.get_postgresql_geometric_filter()
                postgresql_available = PostgreSQLGeometricFilter is not None
            except Exception:
                postgresql_available = False
        
        if is_postgresql and postgresql_available and len(fids) > source_mv_fid_threshold:
            # Large selection on PostgreSQL: create MV for optimization
            return self._create_source_selection_mv_filter(
                fids, 
                pk_field, 
                source_table_name
            )
        else:
            # Non-PostgreSQL backend OR small selection OR PostgreSQL unavailable:
            # Always use inline IN clause
            if len(fids) > source_mv_fid_threshold and not postgresql_available:
                logger.info(f"   ℹ️ Large selection ({len(fids)} FIDs) but PostgreSQL unavailable")
                logger.info(f"   → Using inline IN clause for {backend_name} backend")
            return self._create_inline_fid_filter(
                fids, 
                pk_field, 
                source_table_name
            )
    
    def _detect_primary_key_field(self) -> Optional[str]:
        """
        Detect primary key field name from source layer.
        
        Tries in order:
        1. Layer's primaryKeyAttributes()
        2. Common PK names: 'fid', 'id', 'gid', 'ogc_fid'
        
        Returns:
            Optional[str]: Primary key field name or None
        """
        if not self.source_layer:
            return None
        
        # Try to get from provider
        try:
            pk_attrs = self.source_layer.primaryKeyAttributes()
            if pk_attrs:
                fields = self.source_layer.fields()
                return fields[pk_attrs[0]].name()
        except Exception:
            pass
        
        # Fallback: try common PK names
        for common_pk in ['fid', 'id', 'gid', 'ogc_fid']:
            if self.source_layer.fields().indexOf(common_pk) >= 0:
                return common_pk
        
        return None
    
    def _extract_feature_ids(
        self, 
        task_features: List[Any], 
        pk_field: str
    ) -> List[Any]:
        """
        Extract feature IDs from task_features list.
        
        Args:
            task_features: List of QgsFeature objects or dicts
            pk_field: Primary key field name
        
        Returns:
            List[Any]: List of feature ID values
        """
        fids = []
        for f in task_features:
            try:
                # QgsFeature object
                if hasattr(f, 'attribute'):
                    fid_val = f.attribute(pk_field)
                    if fid_val is not None:
                        fids.append(fid_val)
                    else:
                        # Fallback to QGIS FID if attribute is null
                        if hasattr(f, 'id'):
                            fids.append(f.id())
                elif hasattr(f, 'id'):
                    # Legacy fallback
                    fids.append(f.id())
                elif isinstance(f, dict) and pk_field in f:
                    # Dict-based feature
                    fids.append(f[pk_field])
            except Exception as e:
                logger.debug(f"Could not extract ID from feature: {e}")
        
        return fids
    
    def _get_source_table_name(self) -> Optional[str]:
        """
        Get actual database table name for source layer.
        
        Returns:
            Optional[str]: Table name or None
        """
        # Try param_source_table (set by task)
        source_table_name = self.task_parameters.get('param_source_table')
        
        if not source_table_name and self.source_layer:
            # Try to get from layer URI
            try:
                uri = QgsDataSourceUri(self.source_layer.source())
                source_table_name = uri.table()
            except Exception:
                source_table_name = self.source_layer.name()
        
        return source_table_name
    
    def _get_optimization_thresholds(self) -> Dict[str, int]:
        """
        Get performance optimization thresholds.
        
        Returns:
            Dict[str, int]: Thresholds configuration
        """
        # Default thresholds
        return {
            'source_mv_fid_threshold': 500,  # Create MV when > 500 FIDs
        }
    
    def _create_source_selection_mv_filter(
        self,
        fids: List[Any],
        pk_field: str,
        source_table_name: Optional[str]
    ) -> Optional[str]:
        """
        Create materialized view for large source selection.
        
        Returns filter like: "table"."pk" IN (SELECT pk FROM mv_src_sel_XXX)
        
        Args:
            fids: List of feature IDs
            pk_field: Primary key field name
            source_table_name: Source table name
        
        Returns:
            Optional[str]: MV-based filter or inline filter on failure
        """
        logger.info(f"🗄️ Source selection ({len(fids)} FIDs) > threshold (500)")
        logger.info("   → Creating temporary MV for optimized EXISTS query")
        
        # Get geometry field name
        source_geom_field = self._get_source_geom_field()
        
        # FIXED v4.2.10: Get connection from source layer FIRST, then pass to backend
        connection = None
        if self.source_layer:
            try:
                from ...infrastructure.utils.layer_utils import get_datasource_connexion_from_layer
                connection, _ = get_datasource_connexion_from_layer(self.source_layer)
                if connection:
                    logger.debug("   → Got connection from source layer")
            except Exception as conn_err:
                logger.debug(f"   → Could not get connection from layer: {conn_err}")
        
        # Create MV using backend method
        from ..ports import get_backend_services
        _backend_services = get_backend_services()
        PostgreSQLGeometricFilter = _backend_services.get_postgresql_geometric_filter()
        if not PostgreSQLGeometricFilter:
            # GRACEFUL FALLBACK: PostgreSQL backend not available
            # Fall back to inline IN clause instead of raising exception
            logger.warning("   ⚠️ PostgreSQL backend not available, using inline IN clause")
            return self._create_inline_fid_filter(fids, pk_field, source_table_name)
        
        try:
            # FIXED v4.2.10: Pass connection in task_parameters for MV creation
            task_params_with_conn = dict(self.task_parameters) if self.task_parameters else {}
            task_params_with_conn['connection'] = connection
            pg_backend = PostgreSQLGeometricFilter(task_parameters=task_params_with_conn)
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to create PostgreSQL backend: {e}")
            return self._create_inline_fid_filter(fids, pk_field, source_table_name)
        
        # Check if the backend has create_source_selection_mv method
        if not hasattr(pg_backend, 'create_source_selection_mv'):
            # Method not implemented yet - use inline fallback
            logger.warning("   ⚠️ create_source_selection_mv not implemented, using inline IN clause")
            return self._create_inline_fid_filter(fids, pk_field, source_table_name)
        
        try:
            mv_ref = pg_backend.create_source_selection_mv(
                layer=self.source_layer,
                fids=fids,
                pk_field=pk_field,
                geom_field=source_geom_field
            )
        except Exception as e:
            logger.warning(f"   ⚠️ MV creation failed: {e}")
            return self._create_inline_fid_filter(fids, pk_field, source_table_name)
        
        if mv_ref:
            # Use MV reference in filter
            if source_table_name:
                source_filter = f'"{source_table_name}"."{pk_field}" IN (SELECT pk FROM {mv_ref})'
            else:
                source_filter = f'"{pk_field}" IN (SELECT pk FROM {mv_ref})'
            
            # Store MV reference for cleanup
            self._source_selection_mvs.append(mv_ref)
            
            logger.debug(f"   ✓ MV created: {mv_ref}")
            logger.debug(f"   → Using source selection MV ({len(fids)} features) for EXISTS optimization")
            return source_filter
        else:
            # MV creation failed, fall back to inline IN clause
            logger.warning("   ⚠️ MV creation failed, using inline IN clause (may be slow)")
            return self._create_inline_fid_filter(fids, pk_field, source_table_name)
    
    def _create_inline_fid_filter(
        self,
        fids: List[Any],
        pk_field: str,
        source_table_name: Optional[str]
    ) -> str:
        """
        Create inline "pk IN (...)" filter with size limit protection.
        
        FIXED v4.2.10: Added expression size limit and chunking.
        - Max 10,000 FIDs per IN clause (prevents 80KB+ expressions)
        - Multiple IN clauses combined with OR for very large selections
        - Warning log when expression is very large
        
        Args:
            fids: List of feature IDs
            pk_field: Primary key field name
            source_table_name: Source table name
        
        Returns:
            str: Inline FID filter SQL (possibly with OR for large selections)
        """
        # FIXED v4.2.10: Size limit protection
        MAX_FIDS_PER_CLAUSE = 5000  # Limit to prevent huge expressions
        MAX_TOTAL_FIDS = 50000  # Absolute limit with warning
        
        if len(fids) > MAX_TOTAL_FIDS:
            logger.warning(
                f"   ⚠️ VERY LARGE selection ({len(fids)} FIDs) - truncating to {MAX_TOTAL_FIDS}"
            )
            logger.warning(
                f"   → Consider using PostgreSQL with MV optimization for better performance"
            )
            fids = fids[:MAX_TOTAL_FIDS]
        elif len(fids) > MAX_FIDS_PER_CLAUSE:
            logger.info(
                f"   ℹ️ Large selection ({len(fids)} FIDs) - will use chunked IN clauses"
            )
        
        # Build table-qualified field reference
        if source_table_name:
            field_ref = f'"{source_table_name}"."{pk_field}"'
        else:
            field_ref = f'"{pk_field}"'
        
        # Chunk FIDs if needed
        if len(fids) <= MAX_FIDS_PER_CLAUSE:
            # Single IN clause
            fids_str = self._format_pk_values_for_sql(fids, pk_field)
            return f'{field_ref} IN ({fids_str})'
        else:
            # Multiple IN clauses combined with OR
            chunks = []
            for i in range(0, len(fids), MAX_FIDS_PER_CLAUSE):
                chunk = fids[i:i + MAX_FIDS_PER_CLAUSE]
                chunk_str = self._format_pk_values_for_sql(chunk, pk_field)
                chunks.append(f'{field_ref} IN ({chunk_str})')
            
            # Combine with OR
            combined = ' OR '.join(f'({c})' for c in chunks)
            logger.info(f"   → Created {len(chunks)} chunked IN clauses")
            
            return f'({combined})'
    
    def _get_source_geom_field(self) -> str:
        """
        Get source layer's geometry field name.
        
        Returns:
            str: Geometry field name (defaults to 'geom')
        """
        source_geom_field = self.task_parameters.get('param_source_geom')
        
        if not source_geom_field and self.source_layer:
            try:
                uri = QgsDataSourceUri(self.source_layer.source())
                source_geom_field = uri.geometryColumn() or 'geom'
            except Exception:
                source_geom_field = 'geom'
        
        return source_geom_field or 'geom'
    
    def _format_pk_values_for_sql(
        self, 
        fids: List[Any], 
        pk_field: str
    ) -> str:
        """
        Format primary key values for SQL IN clause.
        
        Handles different data types:
        - UUID: Quoted strings ('uuid-value'::uuid)
        - Text: Quoted strings ('text-value')
        - Numeric: Unquoted (123, 456)
        
        CRITICAL FIX v4.0.9: Value-based detection for PostgreSQL via OGR.
        
        Args:
            fids: List of feature ID values
            pk_field: Primary key field name
        
        Returns:
            str: Comma-separated formatted values
        """
        if not fids:
            return ""
        
        # FIX v4.0.9: VALUE-BASED detection first (most reliable for OGR layers)
        # Check actual values before checking field schema
        pk_is_uuid = False
        pk_is_text = False
        pk_is_numeric = None
        
        # Strategy 1: Check if ALL values are Python numeric types
        try:
            all_numeric_values = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in fids[:10]  # Check first 10 values
            )
            if all_numeric_values:
                pk_is_numeric = True
                logger.debug(f"PK '{pk_field}' detected as numeric from VALUES (all int/float)")
        except Exception:
            pass
        
        # Strategy 2: Check if string values look like integers
        if pk_is_numeric is None:
            try:
                all_look_numeric = all(
                    isinstance(v, (int, float)) or 
                    (isinstance(v, str) and v.lstrip('-').isdigit())
                    for v in fids[:10]
                )
                if all_look_numeric:
                    pk_is_numeric = True
                    logger.debug(f"PK '{pk_field}' detected as numeric from string VALUES")
            except Exception:
                pass
        
        # Strategy 3: Check field schema (may be unreliable for OGR)
        if pk_is_numeric is None and self.source_layer:
            pk_idx = self.source_layer.fields().indexOf(pk_field)
            if pk_idx >= 0:
                field = self.source_layer.fields()[pk_idx]
                field_type = field.typeName().lower()
                pk_is_uuid = 'uuid' in field_type
                pk_is_text = 'char' in field_type or 'text' in field_type or 'string' in field_type
                pk_is_numeric = field.isNumeric()
                logger.debug(f"PK '{pk_field}' detected from schema: uuid={pk_is_uuid}, text={pk_is_text}, numeric={pk_is_numeric}")
        
        # Strategy 4: Fallback based on common PK names
        if pk_is_numeric is None:
            pk_lower = pk_field.lower()
            common_numeric_names = ('id', 'fid', 'gid', 'pk', 'ogc_fid', 'objectid', 'oid', 'rowid')
            pk_is_numeric = pk_lower in common_numeric_names
            logger.debug(f"PK '{pk_field}' fallback based on name: numeric={pk_is_numeric}")
        
        # Format values based on type
        # UUID FIX v4.0: Ensure all non-numeric values are properly quoted
        if pk_is_uuid:
            # UUID - cast to uuid type (PostgreSQL specific)
            formatted = ["'" + str(fid).replace("'", "''") + "'::uuid" for fid in fids]
        elif pk_is_text or not pk_is_numeric:
            # Text/UUID/other non-numeric - quote strings and escape quotes
            formatted = ["'" + str(fid).replace("'", "''") + "'" for fid in fids]
        else:
            # Numeric - no quotes
            formatted = [str(fid) for fid in fids]
        
        return ", ".join(formatted)


# =============================================================================
# STANDALONE FUNCTIONS (for backward compatibility with imports)
# =============================================================================

def build_feature_id_expression(
    features_ids: List[str],
    primary_key_name: str,
    table_name: Optional[str],
    provider_type: str,
    is_numeric: bool = True
) -> str:
    """
    Build SQL IN expression from list of feature IDs.
    
    Handles provider-specific syntax:
    - PostgreSQL: "table"."pk" IN (...)
    - Spatialite/OGR: "pk" IN (...) or fid IN (unquoted for compatibility)
    
    Args:
        features_ids: List of feature ID values (as strings)
        primary_key_name: Primary key field name
        table_name: Table name (optional, used for PostgreSQL qualified syntax)
        provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
        is_numeric: Whether PK is numeric (affects quoting)
        
    Returns:
        str: SQL IN expression
    """
    if not features_ids:
        return ""
    
    # CRITICAL FIX v2.8.10: Use unquoted 'fid' for OGR/GeoPackage compatibility
    # OGR driver does NOT support quoted "fid" in setSubsetString()
    if provider_type == 'ogr':
        pk_ref = 'fid' if primary_key_name == 'fid' else f'"{primary_key_name}"'
        if is_numeric:
            return f'{pk_ref} IN ({", ".join(features_ids)})'
        else:
            return f'{pk_ref} IN ({", ".join(repr(fid) for fid in features_ids)})'
    
    elif provider_type == 'spatialite':
        pk_ref = 'fid' if primary_key_name == 'fid' else f'"{primary_key_name}"'
        if is_numeric:
            return f'{pk_ref} IN ({", ".join(features_ids)})'
        else:
            return f'{pk_ref} IN ({", ".join(repr(fid) for fid in features_ids)})'
    
    else:  # PostgreSQL
        if is_numeric:
            if table_name:
                return f'"{table_name}"."{primary_key_name}" IN ({", ".join(features_ids)})'
            else:
                return f'"{primary_key_name}" IN ({", ".join(features_ids)})'
        else:
            if table_name:
                return (
                    f'"{table_name}"."{primary_key_name}" IN '
                    f"({', '.join(repr(fid) for fid in features_ids)})"
                )
            else:
                return f'"{primary_key_name}" IN ({", ".join(repr(fid) for fid in features_ids)})'


def build_combined_filter_expression(
    new_expression: str,
    old_subset: Optional[str],
    combine_operator: Optional[str],
    sanitize_fn: Optional[callable] = None
) -> str:
    """
    Combine new filter expression with existing subset using specified operator.
    
    Used for combining new spatial/attribute filters with existing layer filters.
    
    Args:
        new_expression: New filter expression to apply
        old_subset: Existing subset string from layer (optional)
        combine_operator: SQL operator ('AND', 'OR', 'NOT') (optional)
        sanitize_fn: Optional callback to sanitize old_subset
            Signature: sanitize_fn(subset: str) -> str
            
    Returns:
        str: Combined filter expression
    """
    if not old_subset or not combine_operator:
        return new_expression
    
    # Sanitize old_subset to remove non-boolean display expressions
    if sanitize_fn:
        old_subset = sanitize_fn(old_subset)
        if not old_subset:
            return new_expression
    
    # Extract WHERE clause from old subset if present
    param_old_subset_where_clause = ''
    param_source_old_subset = old_subset
    
    index_where_clause = old_subset.find('WHERE')
    if index_where_clause > -1:
        param_old_subset_where_clause = old_subset[index_where_clause:]
        if param_old_subset_where_clause.endswith('))'):
            param_old_subset_where_clause = param_old_subset_where_clause[:-1]
        param_source_old_subset = old_subset[:index_where_clause]
    
    # Combine expressions
    if index_where_clause > -1:
        # Has WHERE clause - combine with existing structure
        # FIX 2026-01-16: Strip leading "WHERE " from new_expression to prevent "WHERE WHERE" syntax error
        clean_new_expression = new_expression.lstrip()
        if clean_new_expression.upper().startswith('WHERE '):
            clean_new_expression = clean_new_expression[6:].lstrip()
        return (
            f'{param_source_old_subset} {param_old_subset_where_clause} '
            f'{combine_operator} ( {clean_new_expression} )'
        )
    else:
        # No WHERE clause - wrap both in parentheses for safety
        return f'( {old_subset} ) {combine_operator} ( {new_expression} )'


# Module exports
__all__ = [
    'ExpressionBuilder',
    'build_feature_id_expression',
    'build_combined_filter_expression',
]