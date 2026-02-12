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

from qgis.core import QgsVectorLayer

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
        self.log_info("📐 OGR buffer parameters:")
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
                    "⚠️ OGR apply_filter called from different thread! "
                    f"Previous: {_last_operation_thread}, Current: {current_thread}"
                )
            _last_operation_thread = current_thread

        try:
            from qgis import processing
            from qgis.core import QgsVectorLayer

            # Parse parameters
            params = json.loads(expression) if expression else {}
            predicates = params.get('predicates', ['intersects'])
            buffer_value = params.get('buffer_value')
            buffer_expression = params.get('buffer_expression')

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

            # FIX v4.2.11: Apply buffer to source layer if needed (static or dynamic)
            if buffer_expression and buffer_expression.strip():
                self.log_info(f"  - Applying dynamic buffer expression: {buffer_expression[:50]}...")
                source_layer = self._apply_buffer_expression_to_layer(source_layer, buffer_expression)
                if source_layer is None:
                    self.log_error("Failed to apply buffer expression")
                    return False
                self.log_info(f"  - Buffered source: {source_layer.featureCount()} features")
            elif buffer_value is not None and buffer_value != 0:
                self.log_info(f"  - Applying static buffer: {buffer_value}m")
                source_layer = self._apply_buffer_to_layer(source_layer, buffer_value)
                if source_layer is None:
                    self.log_error("Failed to apply buffer")
                    return False
                self.log_info(f"  - Buffered source: {source_layer.featureCount()} features")

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
                processing.run(
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

            # FIX v4.0.8: For PostgreSQL layers via OGR, we need actual PK values, not QGIS internal FIDs
            # selectedFeatureIds() returns QGIS internal feature IDs, which don't match PostgreSQL PK values
            pk_field = self._get_primary_key(layer)
            storage_type = ""
            try:
                storage_type = layer.dataProvider().storageType().lower()
            except Exception:
                pass

            # Check if this is a PostgreSQL layer accessed via OGR
            is_postgres_via_ogr = 'postgresql' in storage_type or 'postgis' in storage_type

            if is_postgres_via_ogr and pk_field:
                # Get actual PK values from selected features
                self.log_info(f"  - PostgreSQL via OGR detected: fetching actual PK values from '{pk_field}'")
                pk_values = []
                for fid in selected_ids:
                    feature = layer.getFeature(fid)
                    if feature.isValid():
                        pk_value = feature[pk_field]
                        if pk_value is not None:
                            pk_values.append(pk_value)

                if pk_values:
                    self.log_info(f"  - Retrieved {len(pk_values)} actual PK values")
                    # Build filter with actual PK values
                    fid_filter = self._build_fid_filter_with_values(layer, pk_values, pk_field)
                else:
                    self.log_warning("  - Could not retrieve PK values, falling back to FID-based filter")
                    fid_filter = self._build_fid_filter(layer, selected_ids)
            else:
                # Build FID filter normally for non-PostgreSQL layers
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
            self.log_info(f"  - Applying filter: {final_filter[:200]}..." if len(final_filter) > 200 else f"  - Applying filter: {final_filter}")
            success = safe_set_subset_string(layer, final_filter)

            if success:
                self.log_info(f"✓ OGR filter applied: {len(selected_ids)} features")
            else:
                self.log_error(f"✗ Failed to apply FID filter to {layer.name()}")
                self.log_error(f"  - Filter expression: {final_filter[:500]}...")
                self.log_error(f"  - Primary key field: {self._get_primary_key(layer)}")
                self.log_error(f"  - Number of FIDs: {len(selected_ids)}")
                # Try to get more diagnostic info
                try:
                    provider = layer.dataProvider()
                    self.log_error(f"  - Provider capabilities: {provider.capabilities()}")
                    self.log_error(f"  - Storage type: {provider.storageType()}")
                except Exception as diag_e:
                    self.log_error(f"  - Could not get diagnostics: {diag_e}")

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
        """
        Build FID-based filter expression for OGR layers (v4.0.7).

        Improved to handle various primary key types:
        - Numeric IDs: fid IN (1, 2, 3)
        - UUIDs: uuid IN ('abc-123', 'def-456')
        - GeoPackage: "fid" IN (1, 2, 3)
        - Shapefiles: fid IN (1, 2, 3)

        Args:
            layer: QGIS vector layer
            fids: List of feature IDs

        Returns:
            Filter expression string
        """
        if not fids:
            return "1 = 0"

        # Get storage type and primary key
        storage_type = ""
        try:
            storage_type = layer.dataProvider().storageType().lower()
        except Exception:
            pass

        pk_field = self._get_primary_key(layer)
        pk_field_lower = pk_field.lower()

        # Check if PK field is numeric or text (for quoting values)
        is_numeric_pk = True
        try:
            fields = layer.fields()
            pk_idx = fields.indexOf(pk_field)
            if pk_idx >= 0:
                from qgis.PyQt.QtCore import QVariant
                field_type = fields.at(pk_idx).type()
                is_numeric_pk = field_type in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong, QVariant.Double)
        except Exception:
            pass

        # Build value list based on PK type
        if is_numeric_pk:
            fid_list = ", ".join(str(fid) for fid in fids)
        else:
            # Quote string values (UUID, etc.)
            fid_list = ", ".join(f"'{fid}'" for fid in fids)

        # Shapefile special case: QGIS 3.x requires lowercase 'fid' for setSubsetString
        if 'shapefile' in storage_type or 'esri' in storage_type:
            self.log_info("  - Shapefile detected: using lowercase 'fid' for QGIS subset")
            return f'fid IN ({fid_list})'

        # GeoPackage and SQLite-based formats: use quoted field name
        if 'geopackage' in storage_type or 'gpkg' in storage_type or 'sqlite' in storage_type:
            self.log_info(f"  - GeoPackage/SQLite detected: using quoted '{pk_field}'")
            return f'"{pk_field}" IN ({fid_list})'

        # For other OGR formats with detected primary key
        if pk_field and pk_field_lower not in ['fid']:
            self.log_info(f"  - Using detected primary key: {pk_field}")
            return f'"{pk_field}" IN ({fid_list})'

        # Default: try lowercase fid (more compatible with QGIS setSubsetString)
        self.log_info(f"  - Unknown format ({storage_type}): using lowercase 'fid' syntax")
        return f'fid IN ({fid_list})'

    def _build_fid_filter_with_values(self, layer, pk_values: list, pk_field: str) -> str:
        """
        Build filter expression using actual PK values (v4.0.8).

        This method is used for PostgreSQL layers accessed via OGR, where we
        need to use actual PK column values instead of QGIS internal FIDs.

        Args:
            layer: QGIS vector layer
            pk_values: List of actual primary key values from the PK column
            pk_field: Name of the primary key field

        Returns:
            Filter expression string like "id" IN (1, 2, 3)
        """
        if not pk_values:
            return "1 = 0"

        # FIX v4.0.9: IMPROVED numeric detection for PostgreSQL via OGR
        # QGIS OGR provider may return incorrect field types for PostgreSQL.
        # Use multiple detection strategies with VALUE-BASED priority.
        is_numeric_pk = None

        # Strategy 1: Check ACTUAL VALUES first (most reliable)
        # If all values are Python int/float, they're numeric
        try:
            all_numeric_values = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in pk_values[:10]  # Check first 10 values
            )
            if all_numeric_values:
                is_numeric_pk = True
                self.log_info("  - PK type detected from VALUES: numeric (all values are int/float)")
        except Exception as val_e:
            self.log_debug(f"  - Value-based detection failed: {val_e}")

        # Strategy 2: Check if string values look like integers
        if is_numeric_pk is None:
            try:
                sample_values = pk_values[:10]
                all_look_numeric = all(
                    isinstance(v, (int, float)) or
                    (isinstance(v, str) and v.lstrip('-').isdigit())
                    for v in sample_values
                )
                if all_look_numeric:
                    is_numeric_pk = True
                    self.log_info("  - PK type detected from string VALUES: numeric (all values look like integers)")
            except Exception:
                pass

        # Strategy 3: Check field type from layer fields (may be unreliable for OGR)
        if is_numeric_pk is None:
            try:
                fields = layer.fields()
                pk_idx = fields.indexOf(pk_field)
                if pk_idx >= 0:
                    from qgis.PyQt.QtCore import QVariant
                    field_type = fields.at(pk_idx).type()
                    numeric_types = (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong, QVariant.Double)
                    is_numeric_pk = field_type in numeric_types
                    self.log_info(f"  - PK type detected from field schema: {'numeric' if is_numeric_pk else 'text'} (QVariant type={field_type})")
            except Exception as field_e:
                self.log_debug(f"  - Field type detection failed: {field_e}")

        # Default: assume numeric for common PK field names
        if is_numeric_pk is None:
            pk_lower = pk_field.lower()
            common_numeric_names = ('id', 'fid', 'gid', 'pk', 'ogc_fid', 'objectid', 'oid', 'rowid')
            is_numeric_pk = pk_lower in common_numeric_names
            self.log_info(f"  - PK type FALLBACK: {'numeric' if is_numeric_pk else 'text'} (based on field name '{pk_field}')")

        # Build value list based on PK type
        if is_numeric_pk:
            # Numeric: no quotes - convert all values to int if possible
            formatted_values = []
            for v in pk_values:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    formatted_values.append(str(int(v)))
                elif isinstance(v, str) and v.lstrip('-').isdigit():
                    formatted_values.append(v)  # Already a numeric string
                else:
                    formatted_values.append(str(v))  # Best effort
            value_list = ", ".join(formatted_values)
            self.log_info(f"  - Building NUMERIC IN clause for '{pk_field}': {len(pk_values)} values")
            self.log_debug(f"    Sample: {value_list[:100]}...")
        else:
            # String/UUID: single quotes
            value_list = ", ".join(f"'{v}'" for v in pk_values)
            self.log_info(f"  - Building STRING IN clause for '{pk_field}': {len(pk_values)} values")
            self.log_debug(f"    Sample: {value_list[:100]}...")

        # Always use quoted field name for PostgreSQL
        return f'"{pk_field}" IN ({value_list})'

    def _apply_buffer_to_layer(
        self,
        layer: 'QgsVectorLayer',
        buffer_value: float
    ) -> Optional['QgsVectorLayer']:
        """
        Apply static buffer to source layer using QGIS processing.

        FIX v4.2.11: Add support for static buffer via processing.

        Args:
            layer: Source layer to buffer
            buffer_value: Buffer distance in layer units

        Returns:
            Buffered memory layer, or None on failure
        """
        try:
            from qgis import processing

            result = processing.run(
                'native:buffer',
                {
                    'INPUT': layer,
                    'DISTANCE': buffer_value,
                    'SEGMENTS': 8,
                    'END_CAP_STYLE': 0,  # Round
                    'JOIN_STYLE': 0,  # Round
                    'MITER_LIMIT': 2,
                    'DISSOLVE': False,
                    'OUTPUT': 'memory:'
                },
                feedback=self._feedback if hasattr(self, '_feedback') else None
            )

            buffered_layer = result.get('OUTPUT')
            if buffered_layer and isinstance(buffered_layer, QgsVectorLayer):
                self._source_layer_keep_alive.append(buffered_layer)
                return buffered_layer

            self.log_error("Buffer processing returned no valid layer")
            return None

        except Exception as e:
            self.log_error(f"Failed to apply static buffer: {e}")
            return None

    def _apply_buffer_expression_to_layer(
        self,
        layer: 'QgsVectorLayer',
        buffer_expression: str
    ) -> Optional['QgsVectorLayer']:
        """
        Apply dynamic buffer expression to source layer.

        FIX v4.2.12: Support QGIS expressions for dynamic buffer values.
        Strategy:
        1. Try native:bufferbym if expression is a simple field reference
        2. Fallback to computing average buffer and using static buffer
        3. Last resort: extract numeric default from expression

        Args:
            layer: Source layer to buffer
            buffer_expression: QGIS expression returning buffer distance

        Returns:
            Buffered memory layer, or None on failure
        """
        try:
            from qgis import processing
            import re

            self.log_debug(f"Dynamic buffer expression: {buffer_expression}")

            # Strategy 1: Check if it's a simple field reference - use bufferbym
            field_match = re.match(r'^"?(\w+)"?$', buffer_expression.strip())
            if field_match:
                field_name = field_match.group(1)
                if field_name in [f.name() for f in layer.fields()]:
                    self.log_info(f"  Using native:bufferbym with field '{field_name}'")
                    try:
                        result = processing.run(
                            'native:bufferbym',
                            {
                                'INPUT': layer,
                                'FIELD': field_name,
                                'SEGMENTS': 8,
                                'END_CAP_STYLE': 0,
                                'JOIN_STYLE': 0,
                                'MITER_LIMIT': 2,
                                'OUTPUT': 'memory:'
                            },
                            feedback=self._feedback if hasattr(self, '_feedback') else None
                        )
                        buffered_layer = result.get('OUTPUT')
                        if buffered_layer and isinstance(buffered_layer, QgsVectorLayer):
                            self._source_layer_keep_alive.append(buffered_layer)
                            self.log_info("  ✅ Dynamic buffer (field) applied successfully")
                            return buffered_layer
                    except Exception as e:
                        self.log_warning(f"  bufferbym failed: {e}, trying alternatives")

            # Strategy 2: Compute average buffer value from expression and use static buffer
            self.log_info("  Computing average buffer from expression...")
            avg_buffer = self._compute_average_buffer(layer, buffer_expression)

            if avg_buffer is not None and avg_buffer > 0:
                self.log_info(f"  Using computed average buffer: {avg_buffer:.2f}m")
                return self._apply_buffer_to_layer(layer, avg_buffer)

            # Strategy 3: Fallback to extracting numeric default
            return self._fallback_buffer_from_expression(layer, buffer_expression)

        except Exception as e:
            self.log_error(f"Failed to apply dynamic buffer: {e}")
            return self._fallback_buffer_from_expression(layer, buffer_expression)

    def _compute_average_buffer(
        self,
        layer: 'QgsVectorLayer',
        buffer_expression: str
    ) -> Optional[float]:
        """
        Compute average buffer value by evaluating expression on sample features.

        Args:
            layer: Source layer
            buffer_expression: QGIS expression returning buffer distance

        Returns:
            Average buffer value, or None if cannot compute
        """
        try:
            from qgis.core import (
                QgsExpression, QgsExpressionContext,
                QgsExpressionContextUtils, QgsFeatureRequest
            )

            expr = QgsExpression(buffer_expression)
            if expr.hasParserError():
                self.log_warning(f"  Expression parse error: {expr.parserErrorString()}")
                return None

            # Sample up to 100 features for average
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))

            buffer_values = []
            request = QgsFeatureRequest().setLimit(100)

            for feature in layer.getFeatures(request):
                context.setFeature(feature)
                result = expr.evaluate(context)
                if result is not None:
                    try:
                        val = float(result)
                        if val > 0:  # Only positive buffers
                            buffer_values.append(val)
                    except (TypeError, ValueError):
                        pass

            if buffer_values:
                avg = sum(buffer_values) / len(buffer_values)
                self.log_debug(f"  Computed average buffer from {len(buffer_values)} features: {avg:.2f}")
                return avg

            return None

        except Exception as e:
            self.log_warning(f"  Could not compute average buffer: {e}")
            return None

    def _fallback_buffer_from_expression(
        self,
        layer: 'QgsVectorLayer',
        buffer_expression: str
    ) -> Optional['QgsVectorLayer']:
        """
        Fallback: extract numeric default from expression and apply static buffer.

        Handles expressions like 'if("field" > 100, 50, 10)' by extracting
        the else value (10) as a safe default.

        Args:
            layer: Source layer
            buffer_expression: Original expression that failed

        Returns:
            Statically buffered layer, or original layer
        """
        import re

        self.log_warning(f"Using fallback for expression: {buffer_expression}")

        # Try to extract a default numeric value
        # Pattern: if(..., ..., DEFAULT) - get the last number
        numbers = re.findall(r'[-+]?\d*\.?\d+', buffer_expression)

        if numbers:
            try:
                # Use the last number as default (else clause)
                default_buffer = float(numbers[-1])
                self.log_info(f"  Fallback buffer value: {default_buffer}")
                return self._apply_buffer_to_layer(layer, default_buffer)
            except ValueError:
                pass

        self.log_warning("Could not extract default buffer, using original layer")
        return layer

    def _get_primary_key(self, layer) -> str:
        """
        Get primary key field name with improved detection (v4.0.7).

        Priority order:
        1. Provider-declared primary key
        2. Exact PK names: id, fid, pk, gid, ogc_fid, objectid, oid, rowid
        3. UUID fields (uuid, guid in name)
        4. Numeric fields with ID patterns (_id, id_, identifier, etc.)
        5. First numeric integer field
        6. Default to "fid"

        Args:
            layer: QGIS vector layer

        Returns:
            Primary key field name
        """
        # Common primary key field names (exact match, case-insensitive)
        PK_EXACT_NAMES = ['id', 'fid', 'pk', 'gid', 'ogc_fid', 'objectid', 'oid', 'rowid']
        # UUID field patterns (contains, case-insensitive)
        UUID_PATTERNS = ['uuid', 'guid']
        # ID field patterns (contains, case-insensitive)
        ID_PATTERNS = ['_id', 'id_', 'identifier', 'feature_id', 'object_id']

        try:
            from qgis.PyQt.QtCore import QVariant

            fields = layer.fields()
            if not fields:
                return "fid"

            # 1. Try provider-declared primary key
            try:
                pk_indexes = layer.dataProvider().pkAttributeIndexes()
                if pk_indexes:
                    pk_name = fields.at(pk_indexes[0]).name()
                    self.log_debug(f"Using provider PK: {pk_name}")
                    return pk_name
            except Exception:
                pass

            # 2. Look for exact match PK names
            for field in fields:
                if field.name().lower() in PK_EXACT_NAMES:
                    self.log_debug(f"Found exact PK name: {field.name()}")
                    return field.name()

            # 3. Look for UUID fields
            for field in fields:
                field_name_lower = field.name().lower()
                for pattern in UUID_PATTERNS:
                    if pattern in field_name_lower:
                        self.log_debug(f"Found UUID field: {field.name()}")
                        return field.name()

            # 4. Look for numeric fields with ID patterns
            numeric_types = (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong)
            for field in fields:
                field_name_lower = field.name().lower()
                if field.type() in numeric_types:
                    for pattern in ID_PATTERNS:
                        if pattern in field_name_lower:
                            self.log_debug(f"Found numeric ID field: {field.name()}")
                            return field.name()

            # 5. First numeric integer field
            for field in fields:
                if field.type() in numeric_types:
                    self.log_debug(f"Using first numeric field: {field.name()}")
                    return field.name()

        except Exception as e:
            self.log_warning(f"Error detecting primary key: {e}")

        # 6. Default to fid
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
