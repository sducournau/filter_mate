"""
Attribute Filter Executor

Specialized class for attribute-based filtering operations.
Extracted from FilterEngineTask as part of Phase E13 refactoring (January 2026).

Responsibilities:
- QGIS expression processing and validation
- SQL conversion (PostgreSQL, Spatialite, OGR)
- Feature ID expression building
- Expression combination logic
- TaskBridge delegation for v3 architecture

Location: core/tasks/executors/attribute_filter_executor.py
"""

import logging
from typing import Optional, Tuple, List, Dict, Any

from qgis.core import (
    QgsExpression,
    QgsFeature,
    QgsVectorLayer
)

# Import constants
from ....infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
)

# Import utilities
from ....infrastructure.utils import safe_set_subset_string

logger = logging.getLogger('FilterMate.Tasks.AttributeFilterExecutor')


class AttributeFilterExecutor:
    """
    Handles attribute-based filtering operations.
    
    Responsibilities:
    - Expression validation and processing
    - SQL dialect conversion (QGIS → PostgreSQL/Spatialite/OGR)
    - Feature ID expression building
    - TaskBridge delegation for v3 architecture
    
    Extracted from FilterEngineTask (lines 899-987, 1265-1410) in Phase E13.
    
    Example:
        executor = AttributeFilterExecutor(
            layer=source_layer,
            provider_type='postgresql',
            primary_key='id',
            table_name='my_table'
        )
        
        success, expression = executor.process_qgis_expression("population > 1000")
        if success:
            executor.apply_filter(expression)
    """
    
    def __init__(
        self,
        layer: QgsVectorLayer,
        provider_type: str,
        primary_key: str,
        table_name: Optional[str] = None,
        old_subset: Optional[str] = None,
        combine_operator: str = 'AND',
        task_bridge: Optional[Any] = None
    ):
        """
        Initialize AttributeFilterExecutor.
        
        Args:
            layer: QGIS vector layer to filter
            provider_type: Provider type (postgresql, spatialite, ogr)
            primary_key: Primary key field name
            table_name: Table/layer name (for PostgreSQL)
            old_subset: Existing subset string (for combination)
            combine_operator: Operator to combine expressions (AND/OR)
            task_bridge: Optional TaskBridge for v3 delegation
        """
        self.layer = layer
        self.provider_type = provider_type
        self.primary_key = primary_key
        self.table_name = table_name
        self.old_subset = old_subset
        self.combine_operator = combine_operator
        self.task_bridge = task_bridge
        
        # Get layer field names
        self.field_names = [field.name() for field in layer.fields()]
        
        logger.debug(
            f"AttributeFilterExecutor initialized: "
            f"provider={provider_type}, pk={primary_key}, "
            f"fields={len(self.field_names)}"
        )
    
    def try_v3_attribute_filter(
        self,
        expression: str,
        features_list: Optional[List[QgsFeature]] = None
    ) -> Optional[bool]:
        """
        Try v3 TaskBridge attribute filter.
        
        Extracted from FilterEngineTask._try_v3_attribute_filter (lines 899-987).
        
        Args:
            expression: QGIS expression string
            features_list: Optional list of features (for feature-based mode)
            
        Returns:
            True if v3 succeeded, False if failed, None to fallback to legacy
        """
        if not self.task_bridge:
            return None
        
        # Skip if no expression (field-only mode)
        if not expression or not expression.strip():
            logger.debug("TaskBridge: no expression - using legacy code")
            return None
        
        # Check if expression is just a field name (no operators)
        qgs_expr = QgsExpression(expression)
        expr_upper = expression.upper()
        is_simple_field = qgs_expr.isField() and not any(
            op in expr_upper for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
        )
        
        if is_simple_field:
            logger.debug("TaskBridge: field-only expression - using legacy code")
            return None
        
        # Try v3 attribute filter
        try:
            logger.info("=" * 60)
            logger.info("🚀 V3 TASKBRIDGE: Attempting attribute filter")
            logger.info("=" * 60)
            logger.info(f"   Expression: '{expression}'")
            logger.info(f"   Layer: '{self.layer.name()}'")
            
            bridge_result = self.task_bridge.execute_attribute_filter(
                layer=self.layer,
                expression=expression,
                combine_with_existing=True
            )
            
            if bridge_result.status == 'SUCCESS' and bridge_result.success:
                # V3 succeeded - apply the result
                logger.info(f"✅ V3 TaskBridge SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Feature count: {bridge_result.feature_count}")
                logger.info(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")
                
                # Build filter expression from feature IDs
                filter_expr = expression
                if bridge_result.feature_ids:
                    pk = self.primary_key or '$id'
                    ids_str = ', '.join(str(fid) for fid in bridge_result.feature_ids[:1000])
                    if len(bridge_result.feature_ids) > 1000:
                        logger.warning("TaskBridge: Truncating feature IDs to 1000 for expression")
                    filter_expr = f'"{pk}" IN ({ids_str})'
                
                # Apply subset string
                result = safe_set_subset_string(self.layer, filter_expr)
                if result:
                    logger.info(f"   ✓ Filter applied successfully")
                    return True
                else:
                    logger.warning(f"   ✗ Failed to apply filter expression")
                    return None  # Fallback to legacy
            
            elif bridge_result.status == 'FALLBACK':
                logger.info(f"⚠️ V3 TaskBridge: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None  # Use legacy code
            
            elif bridge_result.status == 'NOT_AVAILABLE':
                logger.debug("TaskBridge: not available - using legacy code")
                return None
            
            else:
                # Error occurred
                logger.warning(f"⚠️ V3 TaskBridge: ERROR")
                logger.warning(f"   Error: {bridge_result.error_message}")
                return None  # Fallback to legacy
        
        except Exception as e:
            logger.warning(f"TaskBridge delegation failed: {e}")
            return None  # Fallback to legacy
    
    def process_qgis_expression(
        self,
        expression: str
    ) -> Tuple[Optional[str], Optional[bool]]:
        """
        Process and validate a QGIS expression, converting it to appropriate SQL.
        
        Extracted from FilterEngineTask._process_qgis_expression (lines 1265-1330).
        
        Args:
            expression: QGIS expression string
            
        Returns:
            (processed_expression, is_field_expression) or (None, None) if invalid
        """
        # FIXED: Only reject if expression is JUST a field name (no operators)
        # Allow expressions like "HOMECOUNT = 10" or "field > 5"
        qgs_expr = QgsExpression(expression)
        # FIX v2.3.9: Use case-insensitive check for operators
        expr_upper = expression.upper()
        if qgs_expr.isField() and not any(
            op in expr_upper for op in ['=', '>', '<', '!', 'IN', 'LIKE', 'AND', 'OR']
        ):
            logger.debug(
                f"Rejecting expression '{expression}' - "
                f"it's just a field name without comparison"
            )
            return None, None
        
        if not qgs_expr.isValid():
            logger.warning(f"Invalid QGIS expression: '{expression}'")
            return None, None
        
        # CRITICAL FIX: Reject "display expressions" that don't return boolean values
        # Display expressions like coalesce("field",'<NULL>') are valid QGIS expressions
        # but they return string/value types, not boolean
        comparison_operators = [
            '=', '>', '<', '!=', '<>', 'IN', 'LIKE', 'ILIKE', 
            'IS NULL', 'IS NOT NULL', 'BETWEEN', 'NOT', 'AND', 'OR', 
            '~', 'SIMILAR TO', '@', '&&'
        ]
        has_comparison = any(op in expression.upper() for op in comparison_operators)
        
        if not has_comparison:
            # Expression doesn't contain comparison operators - likely a display expression
            logger.debug(
                f"Rejecting expression '{expression}' - "
                f"no comparison operators found (display expression, not filter)"
            )
            return None, None
        
        # Add leading space and check for field equality
        expression = " " + expression
        is_field_expression = QgsExpression().isFieldEqualityExpression(expression)
        
        # Qualify field names (delegate to helper method)
        expression = self._qualify_field_names(expression)
        
        # Convert to provider-specific SQL
        if self.provider_type == PROVIDER_POSTGRES:
            expression = self._convert_to_postgis(expression)
        elif self.provider_type == PROVIDER_SPATIALITE:
            expression = self._convert_to_spatialite(expression)
        # else: OGR providers - keep QGIS expression as-is
        
        expression = expression.strip()
        
        # Handle CASE statements
        if expression.startswith("CASE"):
            expression = 'SELECT ' + expression
        
        return expression, is_field_expression[0] if is_field_expression else False
    
    def build_feature_id_expression(
        self,
        features_list: List[QgsFeature],
        is_numeric: bool = True
    ) -> Optional[str]:
        """
        Build feature ID expression from feature list.
        
        Extracted from FilterEngineTask._build_feature_id_expression (lines 1358-1397).
        
        Args:
            features_list: List of features
            is_numeric: Whether primary key is numeric
            
        Returns:
            Filter expression string or None
        """
        from ...filter.expression_builder import build_feature_id_expression
        from ...filter.expression_combiner import combine_with_old_subset
        from ...filter.expression_sanitizer import optimize_duplicate_in_clauses
        
        # Extract feature IDs
        # CRITICAL FIX: Handle ctid (PostgreSQL internal identifier)
        if self.primary_key == 'ctid':
            features_ids = [str(feature.id()) for feature in features_list]
        else:
            features_ids = [str(feature[self.primary_key]) for feature in features_list]
        
        if not features_ids:
            return None
        
        # Build base IN expression
        expression = build_feature_id_expression(
            features_ids=features_ids,
            primary_key_name=self.primary_key,
            table_name=self.table_name if self.provider_type == PROVIDER_POSTGRES else None,
            provider_type=self.provider_type,
            is_numeric=is_numeric
        )
        
        # Combine with old subset if needed
        if self.old_subset:
            combined = combine_with_old_subset(
                new_expression=expression,
                old_subset=self.old_subset,
                combine_operator=self.combine_operator,
                provider_type=self.provider_type,
                optimize_duplicates_fn=lambda expr: optimize_duplicate_in_clauses(expr)
            )
            return combined
        
        return expression
    
    def combine_with_old_subset(self, expression: str) -> str:
        """
        Combine new expression with existing subset.
        
        Extracted from FilterEngineTask._combine_with_old_subset (lines 1332-1356).
        
        Args:
            expression: New filter expression
            
        Returns:
            Combined expression
        """
        from ...filter.expression_combiner import combine_with_old_subset
        from ...filter.expression_sanitizer import optimize_duplicate_in_clauses
        
        # If no existing filter, return new expression
        if not self.old_subset:
            return expression
        
        # Delegate to core module
        return combine_with_old_subset(
            new_expression=expression,
            old_subset=self.old_subset,
            combine_operator=self.combine_operator,
            provider_type=self.provider_type,
            optimize_duplicates_fn=lambda expr: optimize_duplicate_in_clauses(expr)
        )
    
    def apply_filter(self, expression: str) -> bool:
        """
        Apply filter expression to layer.
        
        Args:
            expression: SQL filter expression
            
        Returns:
            True if successful
        """
        return safe_set_subset_string(self.layer, expression)
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    def _qualify_field_names(self, expression: str) -> str:
        """
        Qualify field names in expression with table prefix.
        
        Delegates to core.filter.expression_builder module.
        
        v4.0: Extracted from FilterEngineTask._qualify_field_names_in_expression
        """
        if not expression or not self.layer:
            return expression
        
        try:
            from ....core.filter.expression_builder import qualify_field_names_in_expression
            
            # Get field names from layer
            field_names = [field.name() for field in self.layer.fields()]
            
            # Determine if PostgreSQL
            is_postgresql = self.provider_type == PROVIDER_POSTGRES
            
            return qualify_field_names_in_expression(
                expression=expression,
                field_names=field_names,
                primary_key_name=None,  # Will be auto-detected
                table_name=self.layer.name(),
                is_postgresql=is_postgresql,
                provider_type=self.provider_type,
                normalize_columns_fn=None
            )
        except ImportError:
            logger.debug("expression_builder not available, returning expression unchanged")
            return expression
        except Exception as e:
            logger.warning(f"qualify_field_names failed: {e}")
            return expression
    
    def _convert_to_postgis(self, expression: str) -> str:
        """
        Convert QGIS expression to PostGIS SQL.
        
        Delegates to ExpressionService for dialect-specific conversion.
        
        v4.0: Extracted from FilterEngineTask.qgis_expression_to_postgis
        """
        if not expression:
            return expression
        
        try:
            from ....core.services.expression_service import ExpressionService
            from ....core.domain.filter_expression import ProviderType
            
            geom_col = 'geometry'  # Default geometry column
            return ExpressionService().to_sql(expression, ProviderType.POSTGRESQL, geom_col)
        except ImportError:
            logger.debug("ExpressionService not available, returning expression unchanged")
            return expression
        except Exception as e:
            logger.warning(f"convert_to_postgis failed: {e}")
            return expression
    
    def _convert_to_spatialite(self, expression: str) -> str:
        """
        Convert QGIS expression to Spatialite SQL.
        
        Delegates to ExpressionService for dialect-specific conversion.
        
        v4.0: Extracted from FilterEngineTask.qgis_expression_to_spatialite
        """
        if not expression:
            return expression
        
        try:
            from ....core.services.expression_service import ExpressionService
            from ....core.domain.filter_expression import ProviderType
            
            geom_col = 'geometry'  # Default geometry column
            return ExpressionService().to_sql(expression, ProviderType.SPATIALITE, geom_col)
        except ImportError:
            logger.debug("ExpressionService not available, returning expression unchanged")
            return expression
        except Exception as e:
            logger.warning(f"convert_to_spatialite failed: {e}")
            return expression
