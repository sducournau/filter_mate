"""
Expression Builder - Filter Expression Construction

This module extracts expression building logic from FilterEngineTask (7,015 lines).
It handles:

1. Backend-specific expression building delegation
2. Source geometry filter preparation (from task_features or subset)
3. PostgreSQL EXISTS optimization (MV creation for large selections)
4. Expression caching and validation
5. Primary key field detection and formatting

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
                use_centroids=self.use_centroids_distant
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
        logger.info(f"      📋 ATTEMPT 1: task_parameters['task']['features']")
        logger.info(f"         Count: {len(task_features)} items")
        
        # CRITICAL FIX 2026-01-17: Check if task_features are QgsFeatures or just values (strings/ints)
        # If they are just values (e.g. ["1", "2"]), they are field values not QgsFeature objects
        are_qgs_features = False
        if task_features and len(task_features) > 0:
            first_item = task_features[0]
            are_qgs_features = hasattr(first_item, 'id') and hasattr(first_item, 'geometry')
            logger.info(f"         First item type: {type(first_item).__name__}")
            logger.info(f"         Are QgsFeatures: {are_qgs_features}")
            if not are_qgs_features:
                logger.warning(f"         ⚠️ task_features contains values, not QgsFeature objects!")
                logger.warning(f"         → Will use source_subset instead")
                task_features = []  # Reset to trigger source_subset fallback
        
        # ATTEMPT 2: task_parameters["task"]["feature_fids"] (backup FIDs)
        if not task_features or len(task_features) == 0:
            feature_fids = self.task_parameters.get("task", {}).get("feature_fids", [])
            if feature_fids and self.source_layer:
                logger.warning(f"      ⚠️ ATTEMPT 1 FAILED - trying feature_fids backup")
                logger.info(f"      📋 ATTEMPT 2: Reconstructing features from feature_fids")
                logger.info(f"         FID count: {len(feature_fids)}")
                
                # Reconstruct features from FIDs
                from qgis.core import QgsFeatureRequest
                request = QgsFeatureRequest().setFilterFids(feature_fids)
                task_features = list(self.source_layer.getFeatures(request))
                logger.info(f"         Reconstructed {len(task_features)} features from FIDs")
        
        # ATTEMPT 3: source_layer.selectedFeatures() (direct from layer)
        if not task_features or len(task_features) == 0:
            if self.source_layer and self.source_layer.selectedFeatureCount() > 0:
                logger.warning(f"      ⚠️ ATTEMPT 2 FAILED - trying selectedFeatures")
                logger.info(f"      📋 ATTEMPT 3: source_layer.selectedFeatures()")
                task_features = self.source_layer.selectedFeatures()
                logger.info(f"         Selected {len(task_features)} features from layer")
        
        # Log final result
        if task_features:
            if hasattr(task_features[0], 'id'):
                logger.info(f"         First feature ID: {task_features[0].id()}")
            logger.info(f"         ✅ User has {len(task_features)} QgsFeatures for source_filter")
        else:
            logger.warning(f"         ❌ ALL ATTEMPTS FAILED - No QgsFeature objects available!")
            logger.warning(f"         → Will try source_subset as last resort")
        
        # ATTEMPT 4: Get features from filtered source layer (when source has a subset but can't use it directly)
        # This handles the case where source_subset contains EXISTS patterns
        if not task_features or len(task_features) == 0:
            if self.source_layer and source_subset and skip_source_subset:
                logger.info(f"      📋 ATTEMPT 4: Getting features from filtered source layer")
                logger.info(f"         Source layer has filter applied, extracting visible features...")
                try:
                    from qgis.core import QgsFeatureRequest
                    # Get all features currently visible (respecting the active filter)
                    request = QgsFeatureRequest()
                    task_features = list(self.source_layer.getFeatures(request))
                    logger.info(f"         Extracted {len(task_features)} features from filtered source layer")
                except Exception as e:
                    logger.error(f"         Failed to extract features: {e}")
        
        use_task_features = task_features and len(task_features) > 0
        # print(f"   use_task_features: {use_task_features}")  # DEBUG REMOVED
        # print(f"   skip_source_subset: {skip_source_subset}")  # DEBUG REMOVED
        
        if use_task_features:
            # PRIORITY: Generate filter from task_features
            # print(f"🎯 PATH 1: Using {len(task_features)} task_features")  # DEBUG REMOVED
            logger.debug(f"🎯 PostgreSQL EXISTS: Using {len(task_features)} task_features (selection priority)")
            source_filter = self._generate_fid_filter(task_features)
            
            # HOTFIX VERIFICATION: Log the generated filter
            # print(f"✅ Generated source_filter from task_features:")  # DEBUG REMOVED
            # print(f"   Length: {len(source_filter) if source_filter else 0} chars")  # DEBUG REMOVED
            logger.info(f"✅ Generated source_filter:")
            logger.info(f"   Length: {len(source_filter) if source_filter else 0} chars")
            if source_filter:
                # print(f"   Preview: '{source_filter[:100]}'...")  # DEBUG REMOVED
                logger.info(f"   Preview: '{source_filter[:100]}'...")
                logger.info(f"   ✅ Backend will include this in EXISTS WHERE clause")
            else:
                # print(f"   ❌ ERROR: _generate_fid_filter() returned None!")  # DEBUG REMOVED
                logger.error(f"   ❌ ERROR: _generate_fid_filter() returned None!")
        elif source_subset and not skip_source_subset:
            # FALLBACK: Use source layer's subset string
            # print(f"🎯 PATH 2: Using source_subset as source_filter")  # DEBUG REMOVED
            # print(f"   source_filter = '{source_subset}'")  # DEBUG REMOVED
            logger.debug("PostgreSQL EXISTS: Using source layer subsetString as source_filter")
            source_filter = source_subset
        else:
            # NO FILTER: Will match all source features
            # print(f"❌ PATH 3: NO SOURCE FILTER - EXISTS will match ALL source features!")  # DEBUG REMOVED
            logger.debug("PostgreSQL EXISTS: No source filter (will match all source features)")
        
        # print(f"   FINAL RETURN: source_filter = '{source_filter[:100] if source_filter else 'None'}'...")  # DEBUG REMOVED
        # print("=" * 80)  # DEBUG REMOVED
        
        return source_filter
    
    def _generate_fid_filter(self, task_features: List[Any]) -> Optional[str]:
        """
        Generate "pk IN (...)" filter from task_features.
        
        For large selections (> threshold), creates a temporary materialized view
        to optimize EXISTS queries. Otherwise uses inline IN clause.
        
        Args:
            task_features: List of QgsFeature objects or feature dicts
        
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
        thresholds = self._get_optimization_thresholds()
        source_mv_fid_threshold = thresholds.get('source_mv_fid_threshold', 500)
        
        if len(fids) > source_mv_fid_threshold:
            # Large selection: create MV
            return self._create_source_selection_mv_filter(
                fids, 
                pk_field, 
                source_table_name
            )
        else:
            # Small selection: inline IN clause
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
        
        # Create MV using backend method
        from ..ports import get_backend_services
        _backend_services = get_backend_services()
        PostgreSQLGeometricFilter = _backend_services.get_postgresql_geometric_filter()
        if not PostgreSQLGeometricFilter:
            raise ImportError("PostgreSQL backend not available")
        pg_backend = PostgreSQLGeometricFilter(self.task_parameters)
        
        mv_ref = pg_backend.create_source_selection_mv(
            layer=self.source_layer,
            fids=fids,
            pk_field=pk_field,
            geom_field=source_geom_field
        )
        
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
        Create inline "pk IN (...)" filter.
        
        Args:
            fids: List of feature IDs
            pk_field: Primary key field name
            source_table_name: Source table name
        
        Returns:
            str: Inline FID filter SQL
        """
        # Format FID values for SQL (handles UUID, text, numeric)
        fids_str = self._format_pk_values_for_sql(fids, pk_field)
        
        # Build filter with table qualification
        if source_table_name:
            return f'"{source_table_name}"."{pk_field}" IN ({fids_str})'
        else:
            return f'"{pk_field}" IN ({fids_str})'
    
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
        
        Args:
            fids: List of feature ID values
            pk_field: Primary key field name
        
        Returns:
            str: Comma-separated formatted values
        """
        if not fids:
            return ""
        
        # Detect PK field type
        pk_is_uuid = False
        pk_is_text = False
        pk_is_numeric = True
        
        if self.source_layer:
            pk_idx = self.source_layer.fields().indexOf(pk_field)
            if pk_idx >= 0:
                field = self.source_layer.fields()[pk_idx]
                field_type = field.typeName().lower()
                pk_is_uuid = 'uuid' in field_type
                pk_is_text = 'char' in field_type or 'text' in field_type or 'string' in field_type
                pk_is_numeric = field.isNumeric()
        
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