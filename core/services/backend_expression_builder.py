"""
Backend Expression Builder Service

Extracted from filter_task.py (Phase 14.1 - God Class Reduction)
January 12, 2026

This service handles building filter expressions for different backends:
- PostgreSQL (with EXISTS mode, MV optimization)
- Spatialite
- OGR

Location: core/services/backend_expression_builder.py
"""

import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple, Callable

from qgis.core import QgsMessageLog, Qgis

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Services.BackendExpressionBuilder',
    level=logging.INFO
)

# Import source filter builder functions
from ..filter.source_filter_builder import (
    should_skip_source_subset,
    get_primary_key_field as sfb_get_primary_key_field,
    get_source_table_name as sfb_get_source_table_name,
    extract_feature_ids,
    build_source_filter_inline,
    build_source_filter_with_mv,
    get_visible_feature_ids,
    get_source_wkt_and_srid,
    get_source_feature_count,
)


class BackendExpressionBuilder:
    """
    Builds filter expressions for different backends.
    
    Extracted from FilterEngineTask._build_backend_expression() to reduce
    God Class size while maintaining identical functionality.
    
    Features:
    - PostgreSQL EXISTS mode with source filter handling
    - Materialized View optimization for large selections
    - Expression caching (Phase 4 optimization)
    - Centroid optimization support
    - Buffer simplification support
    
    Usage:
        builder = BackendExpressionBuilder(
            source_layer=source_layer,
            task_parameters=task_parameters,
            expr_cache=expr_cache,
            format_pk_values_callback=format_pk_values_callback
        )
        expression = builder.build(backend, layer_props, source_geom)
    """
    
    def __init__(
        self,
        source_layer: Optional[Any],  # QgsVectorLayer
        task_parameters: Dict[str, Any],
        expr_cache: Optional[Any] = None,
        format_pk_values_callback: Optional[Callable] = None,
        get_optimization_thresholds_callback: Optional[Callable] = None
    ):
        """
        Initialize the expression builder.
        
        Args:
            source_layer: The source layer for filtering
            task_parameters: Task parameters dict
            expr_cache: Optional expression cache (QueryExpressionCache)
            format_pk_values_callback: Callback to format PK values for SQL
            get_optimization_thresholds_callback: Callback to get optimization thresholds
        """
        self.source_layer = source_layer
        self.task_parameters = task_parameters
        self.expr_cache = expr_cache
        self._format_pk_values_callback = format_pk_values_callback
        self._get_optimization_thresholds = get_optimization_thresholds_callback or (lambda: {})
        
        # Storage for created MVs (for cleanup)
        self._source_selection_mvs: List[str] = []
        
        # Params that may be set externally
        self.param_buffer_value: Optional[float] = None
        self.param_buffer_expression: Optional[str] = None
        self.param_use_centroids_distant_layers: bool = False
        self.param_use_centroids_source_layer: bool = False
        self.param_source_table: Optional[str] = None
        self.param_source_geom: Optional[str] = None
        self.current_predicates: List[str] = []
        self.approved_optimizations: Dict[str, Dict] = {}
        self.auto_apply_optimizations: bool = False
        
        # WKT sources
        self.spatialite_source_geom: Optional[str] = None
        self.ogr_source_geom: Optional[Any] = None
        self.source_layer_crs_authid: Optional[str] = None
    
    def get_created_mvs(self) -> List[str]:
        """Get list of MVs created during expression building (for cleanup)."""
        return self._source_selection_mvs.copy()
    
    def clear_created_mvs(self):
        """Clear the list of created MVs."""
        self._source_selection_mvs.clear()
    
    def _format_pk_values_for_sql(self, values, layer=None, pk_field=None):
        """Format PK values for SQL using callback or default implementation."""
        if self._format_pk_values_callback:
            return self._format_pk_values_callback(values, layer=layer, pk_field=pk_field)
        # Default: join as comma-separated values
        return ','.join(str(v) for v in values)
    
    def _get_source_filter_for_postgresql(self) -> Optional[str]:
        """
        Determine the source filter for PostgreSQL EXISTS mode.
        
        This handles three scenarios:
        1. task_features present (user selection) - highest priority
        2. source_subset available and usable
        3. Generate from visible features when source_subset has unadaptable patterns
        
        Returns:
            str or None: The source filter SQL expression
        """
        source_filter = None
        source_subset = self.source_layer.subsetString() if self.source_layer else None
        
        # Check if source_subset should be skipped
        skip_source_subset = should_skip_source_subset(source_subset)
        
        if skip_source_subset:
            logger.info(f"⚠️ PostgreSQL EXISTS: Source subset contains patterns that would be skipped")
            if source_subset:
                logger.info(f"   Subset preview: '{source_subset[:100]}...'")
            logger.info(f"   → Falling through to generate filter from task_features instead")
        
        # Check for task_features (user selection)
        task_features = self.task_parameters.get("task", {}).get("features", [])
        use_task_features = task_features and len(task_features) > 0
        
        if use_task_features:
            source_filter = self._build_filter_from_task_features(task_features)
        elif source_subset and not skip_source_subset:
            source_filter = source_subset
            logger.info(f"🎯 PostgreSQL EXISTS: Using full source filter ({len(source_filter)} chars)")
            logger.debug(f"   Source filter preview: '{source_filter[:100]}...'")
        elif skip_source_subset and source_subset and self.source_layer:
            source_filter = self._build_filter_from_visible_features()
        else:
            logger.debug(f"Geometric filtering: Source layer has no subsetString and no selection")
        
        return source_filter
    
    def _build_filter_from_task_features(self, task_features: List) -> Optional[str]:
        """
        Build source filter from task_features (user's selected features).
        
        Args:
            task_features: List of selected features
            
        Returns:
            str or None: The source filter expression
        """
        logger.debug(f"🎯 PostgreSQL EXISTS: Using {len(task_features)} task_features (selection priority)")
        
        pk_field = sfb_get_primary_key_field(self.source_layer)
        if not pk_field:
            logger.warning(f"⚠️ PostgreSQL EXISTS: Could not determine primary key field for source layer")
            return None
        
        fids = extract_feature_ids(task_features, pk_field, self.source_layer)
        if not fids:
            logger.warning(f"⚠️ PostgreSQL EXISTS: Could not extract feature IDs from task_features")
            return None
        
        source_table_name = sfb_get_source_table_name(
            self.source_layer,
            self.param_source_table
        )
        
        # Check if we should create MV for large selections
        thresholds = self._get_optimization_thresholds()
        source_mv_fid_threshold = thresholds.get('source_mv_fid_threshold', 500)
        
        if len(fids) > source_mv_fid_threshold:
            return self._build_filter_with_mv(fids, pk_field, source_table_name, source_mv_fid_threshold)
        else:
            # Small selection: use inline IN clause
            source_filter = build_source_filter_inline(
                fids, pk_field, source_table_name,
                lambda vals: self._format_pk_values_for_sql(vals, layer=self.source_layer, pk_field=pk_field)
            )
            logger.debug(f"🎯 PostgreSQL EXISTS: Generated selection filter from {len(fids)} features")
            return source_filter
    
    def _build_filter_with_mv(
        self,
        fids: List,
        pk_field: str,
        source_table_name: str,
        threshold: int
    ) -> Optional[str]:
        """
        Build filter using Materialized View for large selections.
        
        Args:
            fids: List of feature IDs
            pk_field: Primary key field name
            source_table_name: Source table name
            threshold: MV threshold value
            
        Returns:
            str or None: The source filter expression
        """
        logger.info(f"🗄️ v2.8.0: Source selection ({len(fids)} FIDs) > threshold ({threshold})")
        logger.info(f"   → Creating temporary MV for optimized EXISTS query")
        
        # Get geometry field name
        source_geom_field = self.param_source_geom
        if not source_geom_field and self.source_layer:
            try:
                # Extract geometry column from layer source (duck typing)
                source_uri = self.source_layer.source()
                # Try to extract geometryColumn if available
                if hasattr(self.source_layer.dataProvider(), 'uri'):
                    uri_obj = self.source_layer.dataProvider().uri()
                    source_geom_field = uri_obj.geometryColumn() or 'geom'
                else:
                    source_geom_field = 'geom'
            except Exception:
                source_geom_field = 'geom'
        
        # Create MV using backend method
        try:
            from ..ports import get_backend_services
            PostgreSQLGeometricFilter = get_backend_services().get_postgresql_geometric_filter()
            if not PostgreSQLGeometricFilter:
                raise ImportError("PostgreSQLGeometricFilter not available")
            pg_backend = PostgreSQLGeometricFilter(self.task_parameters)
            
            mv_ref = pg_backend.create_source_selection_mv(
                layer=self.source_layer,
                fids=fids,
                pk_field=pk_field,
                geom_field=source_geom_field
            )
            
            if mv_ref:
                source_filter = build_source_filter_with_mv(
                    fids, pk_field, source_table_name, mv_ref
                )
                self._source_selection_mvs.append(mv_ref)
                logger.debug(f"   ✓ MV created: {mv_ref}")
                logger.debug(f"   → v2.8.0: Using source selection MV ({len(fids)} features) for EXISTS optimization")
                return source_filter
            else:
                logger.warning(f"   ⚠️ MV creation failed, using inline IN clause (may be slow)")
        except Exception as e:
            logger.warning(f"   ⚠️ MV creation failed with error: {e}")
        
        # Fallback to inline IN clause
        return build_source_filter_inline(
            fids, pk_field, source_table_name,
            lambda vals: self._format_pk_values_for_sql(vals, layer=self.source_layer, pk_field=pk_field)
        )
    
    def _build_filter_from_visible_features(self) -> Optional[str]:
        """
        Build filter from currently visible features in source layer.
        
        Used when source_subset contains unadaptable patterns (EXISTS, MV).
        
        Returns:
            str or None: The source filter expression
        """
        logger.info(f"🔄 PostgreSQL EXISTS: Generating filter from currently visible source features")
        logger.info(f"   → Source layer has filtered subset but it contains unadaptable patterns")
        logger.info(f"   → Fetching visible feature IDs to create new source_filter")
        
        try:
            pk_field = sfb_get_primary_key_field(self.source_layer)
            if not pk_field:
                logger.warning(f"   ⚠️ Could not determine primary key field for source layer")
                return None
            
            visible_fids = get_visible_feature_ids(self.source_layer, pk_field)
            if not visible_fids:
                logger.warning(f"   ⚠️ No visible features found in source layer!")
                return None
            
            source_table_name = sfb_get_source_table_name(
                self.source_layer,
                self.param_source_table
            )
            
            # Check if we should use MV
            thresholds = self._get_optimization_thresholds()
            source_mv_fid_threshold = thresholds.get('source_mv_fid_threshold', 500)
            
            if len(visible_fids) > source_mv_fid_threshold:
                source_filter = self._build_filter_with_mv(
                    visible_fids, pk_field, source_table_name, source_mv_fid_threshold
                )
            else:
                source_filter = build_source_filter_inline(
                    visible_fids, pk_field, source_table_name,
                    lambda vals: self._format_pk_values_for_sql(vals, layer=self.source_layer, pk_field=pk_field)
                )
            
            if source_filter:
                logger.info(f"   ✓ Generated source_filter from {len(visible_fids)} visible features")
                logger.debug(f"   → Filter preview: '{source_filter[:100]}...'")
            
            return source_filter
            
        except Exception as e:
            logger.error(f"   ❌ Failed to generate filter from visible features: {e}")
            import traceback
            logger.debug(f"   Traceback: {traceback.format_exc()}")
            return None
    
    def _get_source_wkt_info(self) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        Get source WKT, SRID, and feature count for PostgreSQL simple mode.
        
        Returns:
            Tuple of (source_wkt, source_srid, source_feature_count)
        """
        task_features = self.task_parameters.get("task", {}).get("features", [])
        source_feature_count = get_source_feature_count(
            task_features=task_features,
            ogr_source_geom=self.ogr_source_geom,
            source_layer=self.source_layer
        )
        
        source_wkt, source_srid = get_source_wkt_and_srid(
            self.spatialite_source_geom,
            self.source_layer_crs_authid
        )
        
        if source_wkt:
            logger.debug(f"PostgreSQL simple mode: {source_feature_count} features, SRID={source_srid}")
            QgsMessageLog.logMessage(
                f"v2.7.3: PostgreSQL will use WKT mode (count={source_feature_count}, wkt_len={len(source_wkt)}, srid={source_srid})",
                "FilterMate", Qgis.Info
            )
        else:
            logger.debug(
                f"PostgreSQL: spatialite_source_geom not available (expected for EXISTS mode with source_filter)"
            )
        
        return source_wkt, source_srid, source_feature_count
    
    def _compute_cache_key(
        self,
        layer,
        source_geom,
        provider_type: str,
        source_filter: Optional[str]
    ) -> Optional[str]:
        """
        Compute expression cache key.
        
        Args:
            layer: Target layer
            source_geom: Source geometry
            provider_type: Provider type string
            source_filter: Source filter (for PostgreSQL EXISTS mode)
            
        Returns:
            str or None: Cache key or None if caching disabled
        """
        if not self.expr_cache:
            return None
        
        layer_id = layer.id() if layer and hasattr(layer, 'id') else None
        if not layer_id:
            return None
        
        source_hash = self.expr_cache.compute_source_hash(source_geom)
        
        # Include source_filter hash for PostgreSQL EXISTS mode
        source_filter_hash = None
        if source_filter:
            source_filter_hash = hashlib.md5(source_filter.encode()).hexdigest()[:16]
            logger.debug(f"  Cache: source_filter_hash={source_filter_hash} (filter length: {len(source_filter)})")
        
        cache_key = self.expr_cache.get_cache_key(
            layer_id=layer_id,
            predicates=self.current_predicates,
            buffer_value=self.param_buffer_value,
            source_geometry_hash=source_hash,
            provider_type=provider_type,
            source_filter_hash=source_filter_hash,
            use_centroids=self.param_use_centroids_distant_layers,
            use_centroids_source=self.param_use_centroids_source_layer
        )
        
        return cache_key
    
    def _check_auto_optimizations(self, layer, source_wkt: Optional[str]) -> bool:
        """
        Check and apply auto-optimizations for the layer.
        
        Args:
            layer: Target layer
            source_wkt: Source WKT (if available)
            
        Returns:
            bool: Updated value for use_centroids_distant
        """
        use_centroids = self.param_use_centroids_distant_layers
        
        # Check pre-approved optimizations
        layer_id = layer.id() if layer else None
        if layer_id and layer_id in self.approved_optimizations:
            layer_opts = self.approved_optimizations[layer_id]
            if layer_opts.get('use_centroid_distant', False):
                use_centroids = True
                logger.info(f"🎯 USER-APPROVED OPTIMIZATION: Centroid mode for {layer.name()}")
        
        # Auto-detection fallback
        if not use_centroids and self.auto_apply_optimizations:
            try:
                from ..ports import get_backend_services
                _services = get_backend_services()
                AUTO_OPTIMIZER_AVAILABLE = _services.is_auto_optimizer_available()
                if AUTO_OPTIMIZER_AVAILABLE and layer:
                    source_wkt_len = len(source_wkt) if source_wkt else 0
                    has_buffer = self.param_buffer_value is not None and self.param_buffer_value != 0
                    
                    optimization_plan = _services.get_optimization_plan(
                        target_layer=layer,
                        source_layer=self.source_layer,
                        source_wkt_length=source_wkt_len,
                        predicates=self.current_predicates,
                        user_requested_centroids=None,
                        has_buffer=has_buffer,
                        buffer_value=self.param_buffer_value if self.param_buffer_value else 0.0
                    )
                    
                    if optimization_plan:
                        if optimization_plan.final_use_centroids:
                            use_centroids = True
                            logger.info(f"🎯 AUTO-OPTIMIZATION: Centroid mode enabled for {layer.name()}")
                            if optimization_plan.recommendations:
                                logger.info(f"   Reason: {optimization_plan.recommendations[0].reason}")
                            logger.info(f"   Expected speedup: ~{optimization_plan.estimated_total_speedup:.1f}x")
                        
                        # Apply buffer simplification if recommended
                        if optimization_plan.final_simplify_tolerance and optimization_plan.final_simplify_tolerance > 0:
                            filtering_params = self.task_parameters.get("filtering", {})
                            if not filtering_params.get("has_simplify_tolerance", False):
                                filtering_params["has_simplify_tolerance"] = True
                                filtering_params["simplify_tolerance"] = optimization_plan.final_simplify_tolerance
                                self.task_parameters["filtering"] = filtering_params
                                logger.info(f"🎯 AUTO-OPTIMIZATION: Buffer simplification enabled")
                                logger.info(f"   Tolerance: {optimization_plan.final_simplify_tolerance:.2f}m")
            except Exception as e:
                logger.debug(f"Auto-optimization check failed: {e}")
        
        return use_centroids
    
    def build(self, backend, layer_props: Dict, source_geom) -> Optional[str]:
        """
        Build filter expression using the specified backend.
        
        This is the main entry point that orchestrates expression building:
        1. Determine source_filter for PostgreSQL EXISTS mode
        2. Get WKT/SRID for PostgreSQL simple mode
        3. Check expression cache
        4. Apply optimizations
        5. Call backend.build_expression()
        6. Store result in cache
        
        Args:
            backend: Backend instance (PostgreSQL, Spatialite, or OGR)
            layer_props: Layer properties dict
            source_geom: Prepared source geometry
            
        Returns:
            str or None: Filter expression, or None on error
        """
        # Step 1: Determine source_filter for PostgreSQL EXISTS mode
        source_filter = None
        if backend.get_backend_name() == 'PostgreSQL':
            source_filter = self._get_source_filter_for_postgresql()
        else:
            logger.debug(f"Geometric filtering: Non-PostgreSQL backend, source_filter=None")
        
        # Step 2: Get WKT/SRID for PostgreSQL simple mode
        source_wkt = None
        source_srid = None
        source_feature_count = None
        
        if backend.get_backend_name() == 'PostgreSQL':
            source_wkt, source_srid, source_feature_count = self._get_source_wkt_info()
        
        # Step 3: Check expression cache
        layer = layer_props.get('layer')
        provider_type = backend.get_backend_name().lower()
        cache_key = self._compute_cache_key(layer, source_geom, provider_type, source_filter)
        
        if cache_key and self.expr_cache:
            cached_expression = self.expr_cache.get(cache_key)
            if cached_expression:
                logger.info(f"✓ Expression cache HIT for {layer.name() if layer else 'unknown'}")
                return cached_expression
        
        # Step 4: Log buffer values and apply optimizations
        logger.info(f"📐 BackendExpressionBuilder.build - Buffer being passed to backend:")
        logger.info(f"  - param_buffer_value: {self.param_buffer_value}")
        logger.info(f"  - param_buffer_expression: {self.param_buffer_expression}")
        logger.info(f"  - use_centroids_distant_layers: {self.param_use_centroids_distant_layers}")
        
        if self.param_buffer_value is not None and self.param_buffer_value < 0:
            logger.info(f"  ⚠️ NEGATIVE BUFFER (erosion) will be passed: {self.param_buffer_value}m")
        
        # Check auto-optimizations
        use_centroids = self._check_auto_optimizations(layer, source_wkt)
        
        # Step 5: Call backend.build_expression()
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=self.current_predicates,
            source_geom=source_geom,
            buffer_value=self.param_buffer_value,
            buffer_expression=self.param_buffer_expression,
            source_filter=source_filter,
            source_wkt=source_wkt,
            source_srid=source_srid,
            source_feature_count=source_feature_count,
            use_centroids=use_centroids
        )
        
        # Check for OGR fallback sentinel
        if expression == "__USE_OGR_FALLBACK__":
            logger.warning(f"Backend returned USE_OGR_FALLBACK sentinel - forcing OGR fallback")
            logger.info(f"  → GeometryCollection conversion failed, RTTOPO MakeValid would error")
            return None
        
        if not expression:
            logger.warning(f"No expression generated by backend")
            return None
        
        # Step 6: Store in cache
        if cache_key and self.expr_cache:
            self.expr_cache.put(cache_key, expression)
            logger.debug(f"Expression cached for {layer.name() if layer else 'unknown'}")
        
        return expression


def create_expression_builder(
    source_layer: Optional[Any],  # QgsVectorLayer
    task_parameters: Dict[str, Any],
    expr_cache: Optional[Any] = None,
    format_pk_values_callback: Optional[Callable] = None,
    get_optimization_thresholds_callback: Optional[Callable] = None
) -> BackendExpressionBuilder:
    """
    Factory function to create a BackendExpressionBuilder.
    
    Args:
        source_layer: The source layer for filtering
        task_parameters: Task parameters dict
        expr_cache: Optional expression cache
        format_pk_values_callback: Callback to format PK values for SQL
        get_optimization_thresholds_callback: Callback to get optimization thresholds
        
    Returns:
        BackendExpressionBuilder instance
    """
    return BackendExpressionBuilder(
        source_layer=source_layer,
        task_parameters=task_parameters,
        expr_cache=expr_cache,
        format_pk_values_callback=format_pk_values_callback,
        get_optimization_thresholds_callback=get_optimization_thresholds_callback
    )
