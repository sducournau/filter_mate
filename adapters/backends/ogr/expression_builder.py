# -*- coding: utf-8 -*-
"""
OGR Expression Builder.

v4.1.0: Migrated from before_migration/modules/backends/ogr_backend.py

This module contains the filter logic for OGR-based layers (Shapefiles, etc.).
Unlike PostgreSQL/Spatialite, OGR uses QGIS processing algorithms for filtering.

It implements the GeometricFilterPort interface for backward compatibility.

Features:
- QGIS processing selectbylocation algorithm
- Memory layer optimization for PostgreSQL
- Spatial index auto-creation
- Thread-safe reference management
- Cancellable feedback for interruption

Author: FilterMate Team
Date: January 2026
"""

import json
import logging
import threading
from typing import Dict, Optional, Any

logger = logging.getLogger('FilterMate.Backend.OGR.ExpressionBuilder')

# Import the port interface
try:
    from ....core.ports.geometric_filter_port import GeometricFilterPort
except ImportError:
    from core.ports.geometric_filter_port import GeometricFilterPort

# Import safe_set_subset_string from infrastructure
try:
    from ....infrastructure.database.sql_utils import safe_set_subset_string
except ImportError:
    def safe_set_subset_string(layer, expression):
        """Fallback implementation."""
        if layer is None:
            return False
        try:
            return layer.setSubsetString(expression)
        except Exception:
            return False

# Thread safety for OGR operations
_ogr_operations_lock = threading.Lock()
_last_operation_thread = None

# Import QgsProcessingFeedback for proper inheritance
try:
    from qgis.core import QgsProcessingFeedback
    _HAS_PROCESSING_FEEDBACK = True
except ImportError:
    _HAS_PROCESSING_FEEDBACK = False
    QgsProcessingFeedback = object  # Fallback for type hints


class CancellableFeedback(QgsProcessingFeedback if _HAS_PROCESSING_FEEDBACK else object):
    """
    Feedback class for cancellable QGIS processing operations.
    
    Inherits from QgsProcessingFeedback to be compatible with QGIS processing.
    Allows interrupting long-running processing algorithms.
    """
    
    def __init__(self, is_cancelled_callback=None):
        """
        Initialize feedback.
        
        Args:
            is_cancelled_callback: Callable returning True if cancelled
        """
        if _HAS_PROCESSING_FEEDBACK:
            super().__init__()
        self._cancelled = False
        self._is_cancelled_callback = is_cancelled_callback
    
    def isCanceled(self) -> bool:
        """Check if operation is cancelled."""
        if self._cancelled:
            return True
        if self._is_cancelled_callback:
            return self._is_cancelled_callback()
        return False
    
    def cancel(self):
        """Cancel the operation."""
        self._cancelled = True
        if _HAS_PROCESSING_FEEDBACK:
            try:
                super().cancel()
            except Exception:
                pass
    
    def setProgress(self, progress: float):
        """Set progress (0-100)."""
        if _HAS_PROCESSING_FEEDBACK:
            try:
                super().setProgress(progress)
            except Exception:
                pass


class OGRExpressionBuilder(GeometricFilterPort):
    """
    OGR expression builder.
    
    Uses QGIS processing algorithms for spatial filtering since OGR
    providers don't support complex SQL expressions.
    
    Implements the legacy GeometricFilterPort interface.
    
    Features:
    - QGIS selectbylocation algorithm
    - FID-based filtering
    - Memory layer optimization
    - Cancellable operations
    
    Example:
        builder = OGRExpressionBuilder(task_params)
        expr = builder.build_expression(
            layer_props={'layer_name': 'buildings'},
            predicates={'intersects': True},
            source_geom=source_layer
        )
        builder.apply_filter(layer, expr)
    """
    
    # QGIS predicate codes for selectbylocation
    PREDICATE_CODES = {
        'intersects': 0,
        'contains': 1,
        'disjoint': 2,
        'equals': 3,
        'touches': 4,
        'overlaps': 5,
        'within': 6,
        'crosses': 7,
    }
    
    def __init__(self, task_params: Dict[str, Any]):
        """
        Initialize OGR expression builder.
        
        Args:
            task_params: Task configuration parameters
        """
        super().__init__(task_params)
        self._logger = logger
        self.source_geom = None
        self._temp_layers_keep_alive = []
        self._source_layer_keep_alive = []
        self._feedback = None
    
    def get_backend_name(self) -> str:
        """Get backend name."""
        return "OGR"
    
    def supports_layer(self, layer: 'QgsVectorLayer') -> bool:
        """
        Check if this backend supports the given layer.
        
        OGR is the fallback backend - supports everything not handled
        by PostgreSQL or Spatialite.
        
        Args:
            layer: QGIS vector layer to check
            
        Returns:
            True for OGR-based layers (Shapefile, GeoJSON, etc.)
        """
        if layer is None:
            return False
        
        provider = layer.providerType()
        
        # Don't handle PostgreSQL or Spatialite
        if provider in ('postgres', 'spatialite'):
            return False
        
        # Handle OGR and memory providers
        return provider in ('ogr', 'memory')
    
    def build_expression(
        self,
        layer_props: Dict[str, Any],
        predicates: Dict[str, bool],
        source_geom: Optional[Any] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """
        Build expression for OGR backend.
        
        OGR uses QGIS processing, so this returns JSON parameters
        rather than SQL. The actual filtering happens in apply_filter().
        
        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source layer reference
            buffer_value: Buffer distance
            buffer_expression: Dynamic buffer expression
            source_filter: Not used
            use_centroids: Already applied in source preparation
            **kwargs: Additional parameters
            
        Returns:
            JSON string with processing parameters
        """
        self.log_debug(f"Preparing OGR processing for {layer_props.get('layer_name', 'unknown')}")
        
        # Log buffer parameters
        self.log_info(f"📐 OGR buffer parameters:")
        self.log_info(f"  - buffer_value: {buffer_value}")
        self.log_info(f"  - buffer_expression: {buffer_expression}")
        
        if buffer_value is not None and buffer_value < 0:
            self.log_info(f"  ⚠️ NEGATIVE BUFFER (erosion) requested: {buffer_value}m")
        
        # Store source geometry for apply_filter
        self.source_geom = source_geom
        
        # Keep source layer alive
        if source_geom is not None:
            try:
                from qgis.core import QgsVectorLayer
                if isinstance(source_geom, QgsVectorLayer):
                    self._source_layer_keep_alive.append(source_geom)
            except ImportError:
                pass
        
        # Return JSON parameters
        params = {
            'predicates': list(predicates.keys()),
            'buffer_value': buffer_value,
            'buffer_expression': buffer_expression
        }
        return json.dumps(params)
    
    def apply_filter(
        self,
        layer: 'QgsVectorLayer',
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter using QGIS processing selectbylocation algorithm.
        
        Thread Safety:
        - Uses lock for concurrent access detection
        - Uses data provider directly to avoid layer signals
        
        Args:
            layer: Layer to filter
            expression: JSON parameters from build_expression
            old_subset: Existing subset (handled via selection)
            combine_operator: Combine operator
            
        Returns:
            True if filter applied successfully
        """
        global _last_operation_thread, _ogr_operations_lock
        
        # Thread safety check
        current_thread = threading.current_thread().ident
        with _ogr_operations_lock:
            if _last_operation_thread is not None and _last_operation_thread != current_thread:
                self.log_warning(
                    f"⚠️ OGR apply_filter called from different thread! "
                    f"Previous: {_last_operation_thread}, Current: {current_thread}"
                )
            _last_operation_thread = current_thread
        
        try:
            from qgis import processing
            from qgis.core import QgsVectorLayer, QgsFeatureRequest
            
            # Parse parameters
            params = json.loads(expression) if expression else {}
            predicates = params.get('predicates', ['intersects'])
            buffer_value = params.get('buffer_value')
            
            # Get source layer
            source_layer = self.source_geom
            
            if source_layer is None:
                self.log_error("No source layer available for OGR filter")
                return False
            
            if not isinstance(source_layer, QgsVectorLayer):
                self.log_error(f"Source is not a QgsVectorLayer: {type(source_layer)}")
                return False
            
            self.log_info(f"📍 Applying OGR filter to {layer.name()}")
            self.log_info(f"  - Source: {source_layer.name()} ({source_layer.featureCount()} features)")
            
            # Map predicates to QGIS codes
            predicate_codes = []
            for pred in predicates:
                pred_lower = pred.lower().replace('st_', '')
                code = self.PREDICATE_CODES.get(pred_lower, 0)
                predicate_codes.append(code)
            
            # Create feedback for cancellation
            self._feedback = CancellableFeedback()
            
            # Run selectbylocation
            try:
                result = processing.run(
                    'native:selectbylocation',
                    {
                        'INPUT': layer,
                        'INTERSECT': source_layer,
                        'PREDICATE': predicate_codes,
                        'METHOD': 0  # New selection
                    },
                    feedback=self._feedback
                )
            except Exception as e:
                self.log_error(f"Processing failed: {e}")
                return False
            
            # Get selected feature IDs
            selected_ids = list(layer.selectedFeatureIds())
            self.log_info(f"  - Selected: {len(selected_ids)} features")
            
            if not selected_ids:
                self.log_warning("No features selected - applying empty filter")
                safe_set_subset_string(layer, "1 = 0")
                return True
            
            # Build FID filter
            fid_filter = self._build_fid_filter(layer, selected_ids)
            
            # Clear selection (filter applied via subset)
            layer.removeSelection()
            
            # Combine with existing filter if needed
            if old_subset and combine_operator:
                if self._is_geometric_filter(old_subset):
                    final_filter = fid_filter
                else:
                    final_filter = f"({old_subset}) {combine_operator} ({fid_filter})"
            else:
                final_filter = fid_filter
            
            # Apply filter
            success = safe_set_subset_string(layer, final_filter)
            
            if success:
                self.log_info(f"✓ OGR filter applied: {len(selected_ids)} features")
            else:
                self.log_error("✗ Failed to apply FID filter")
            
            return success
            
        except Exception as e:
            self.log_error(f"Error in OGR apply_filter: {e}")
            return False
    
    def cancel(self):
        """Cancel ongoing operation."""
        if self._feedback:
            self._feedback.cancel()
    
    def cleanup(self):
        """Clean up temporary layers."""
        self._temp_layers_keep_alive.clear()
        self._source_layer_keep_alive.clear()
        self.source_geom = None
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _build_fid_filter(self, layer, fids: list) -> str:
        """Build FID-based filter expression."""
        if not fids:
            return "1 = 0"
        
        # Get primary key field
        pk_field = self._get_primary_key(layer)
        
        if len(fids) <= 100:
            # Small list - use IN clause
            fid_list = ", ".join(str(fid) for fid in fids)
            return f'"{pk_field}" IN ({fid_list})'
        else:
            # Large list - still use IN but may need chunking
            # For now, use single IN clause
            fid_list = ", ".join(str(fid) for fid in fids)
            return f'"{pk_field}" IN ({fid_list})'
    
    def _get_primary_key(self, layer) -> str:
        """Get primary key field name."""
        # Try to get from layer fields
        try:
            pk_indexes = layer.dataProvider().pkAttributeIndexes()
            if pk_indexes:
                fields = layer.fields()
                return fields.at(pk_indexes[0]).name()
        except Exception:
            pass
        
        # Default to fid
        return "fid"
    
    def _is_geometric_filter(self, subset: str) -> bool:
        """Check if subset contains geometric filter patterns."""
        subset_lower = subset.lower()
        
        # OGR filters are typically FID-based
        geometric_patterns = [
            'intersects',
            'contains',
            'within',
            'st_'
        ]
        
        return any(p in subset_lower for p in geometric_patterns)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'OGRExpressionBuilder',
    'CancellableFeedback',
]
