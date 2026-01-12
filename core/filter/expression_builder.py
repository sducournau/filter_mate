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
        current_predicates: List[str]
    ):
        """
        Initialize the expression builder.
        
        Args:
            task_parameters: Task configuration dict
            source_layer: Source layer for geometric filtering (contains selection)
            current_predicates: Spatial predicates to apply (e.g., ['intersects'])
        """
        self.task_parameters = task_parameters
        self.source_layer = source_layer
        self.current_predicates = current_predicates
        
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
            backend_name = backend.get_backend_name()
            
            # ==========================================
            # 1. PREPARE SOURCE FILTER
            # ==========================================
            source_filter = self._prepare_source_filter(backend_name)
            
            # ==========================================
            # 2. BUILD EXPRESSION VIA BACKEND
            # ==========================================
            # Delegate to backend-specific build_expression()
            # Each backend knows how to construct expressions in its SQL dialect
            expression = backend.build_expression(
                predicates=self.current_predicates,
                source_geom=source_geom,
                layer_props=layer_props,
                source_filter=source_filter
            )
            
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
        source_filter = None
        
        # PostgreSQL EXISTS mode needs source filter
        if backend_name != 'PostgreSQL':
            return None
        
        # Get source layer's existing subset string
        source_subset = self.source_layer.subsetString() if self.source_layer else None
        
        # Check if source_subset contains patterns that would be skipped
        skip_source_subset = False
        if source_subset:
            source_subset_upper = source_subset.upper()
            skip_source_subset = any(pattern in source_subset_upper for pattern in [
                '__SOURCE',
                'EXISTS(',
                'EXISTS ('
            ])
            if not skip_source_subset:
                # Also check for MV references (except source selection MVs)
                skip_source_subset = bool(re.search(
                    r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?.*mv_(?!.*src_sel_)',
                    source_subset,
                    re.IGNORECASE | re.DOTALL
                ))
            
            if skip_source_subset:
                logger.info("⚠️ PostgreSQL EXISTS: Source subset contains patterns that would be skipped")
                logger.info(f"   Subset preview: '{source_subset[:100]}...'")
                logger.info("   → Falling through to generate filter from task_features instead")
        
        # Check for task_features (user's selection) FIRST
        task_features = self.task_parameters.get("task", {}).get("features", [])
        use_task_features = task_features and len(task_features) > 0
        
        if use_task_features:
            # PRIORITY: Generate filter from task_features
            logger.debug(f"🎯 PostgreSQL EXISTS: Using {len(task_features)} task_features (selection priority)")
            source_filter = self._generate_fid_filter(task_features)
        elif source_subset and not skip_source_subset:
            # FALLBACK: Use source layer's subset string
            logger.debug("PostgreSQL EXISTS: Using source layer subsetString as source_filter")
            source_filter = source_subset
        else:
            # NO FILTER: Will match all source features
            logger.debug("PostgreSQL EXISTS: No source filter (will match all source features)")
        
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
        from adapters.backends.postgresql.filter_executor import PostgreSQLGeometricFilter
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
        
        if self.source_layer:
            pk_idx = self.source_layer.fields().indexOf(pk_field)
            if pk_idx >= 0:
                field_type = self.source_layer.fields()[pk_idx].typeName().lower()
                pk_is_uuid = 'uuid' in field_type
                pk_is_text = 'char' in field_type or 'text' in field_type or 'string' in field_type
        
        # Format values based on type
        if pk_is_uuid:
            # UUID - cast to uuid type
            formatted = ["'" + str(fid).replace("'", "''") + "'::uuid" for fid in fids]
        elif pk_is_text:
            # Text - quote strings
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
        return (
            f'{param_source_old_subset} {param_old_subset_where_clause} '
            f'{combine_operator} {new_expression}'
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