"""
Layer Validator
===============

Extracted from filter_mate_app.py (MIG-024) for God Class reduction.

Handles layer validation and filtering with:
- Vector layer type validation
- C++ object deletion detection
- Source availability checking
- PostgreSQL-specific handling

Author: FilterMate Team
Version: 2.8.6
"""

from typing import List, Optional, Tuple, Dict

try:
    from qgis.core import QgsVectorLayer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = object

try:
    from ..infrastructure.logging import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(name)

try:
    from ..infrastructure.utils.validation_utils import (
        is_layer_valid as is_valid_layer,
        is_sip_deleted,
        is_layer_source_available
    )
except ImportError:
    # Mocks for testing
    def is_valid_layer(layer):
        return layer is not None and hasattr(layer, 'isValid') and layer.isValid()

    def is_sip_deleted(obj):
        return False

    def is_layer_source_available(layer, require_psycopg2=False):
        return layer is not None

logger = get_logger(__name__)


class LayerValidator:
    """
    Validates and filters layers for FilterMate operations.

    Features:
    - Checks if layers are valid vector layers
    - Detects deleted C++ objects
    - Verifies source availability
    - Handles PostgreSQL layers specially
    """

    # Add static method for backwards compatibility
    # Some code may call LayerValidator.is_valid_layer() as a class method
    @staticmethod
    def is_valid_layer(layer) -> bool:
        """
        Static method wrapper for is_valid_layer function.

        Provides backwards compatibility for code that calls
        LayerValidator.is_valid_layer() instead of using the
        function from object_safety module.

        Args:
            layer: Layer to validate

        Returns:
            True if layer is valid
        """
        return is_valid_layer(layer)

    def __init__(self, postgresql_available: bool = True):
        """
        Initialize LayerValidator.

        Args:
            postgresql_available: Whether psycopg2 is available
        """
        self._postgresql_available = postgresql_available

    def filter_usable_layers(
        self,
        layers: List,
        require_source: bool = True
    ) -> List['QgsVectorLayer']:
        """
        Return only layers that are valid vector layers with available sources.

        STABILITY FIX v2.3.9: Uses is_valid_layer() from object_safety module
        to prevent access violations from deleted C++ objects.

        Args:
            layers: List of layers to filter
            require_source: Whether to require source availability

        Returns:
            List of usable vector layers
        """
        try:
            input_count = len(layers or [])
            usable = []
            filtered_reasons = []

            logger.info(f"filter_usable_layers: Processing {input_count} layers (POSTGRESQL_AVAILABLE={self._postgresql_available})")

            for layer in (layers or []):
                reason = self._validate_layer(layer, require_source)
                if reason:
                    filtered_reasons.append(reason)
                else:
                    usable.append(layer)

            self._log_filtering_results(input_count, usable, filtered_reasons)
            return usable

        except Exception as e:
            logger.error(f"filter_usable_layers error: {e}", exc_info=True)
            return []

    def _validate_layer(
        self,
        layer,
        require_source: bool = True
    ) -> Optional[str]:
        """
        Validate a single layer.

        Args:
            layer: Layer to validate
            require_source: Whether to require source availability

        Returns:
            Reason string if invalid, None if valid
        """
        # Check if C++ object was deleted
        if is_sip_deleted(layer):
            return "unknown: C++ object deleted"

        # Check if it's a vector layer
        if not isinstance(layer, QgsVectorLayer):
            try:
                name = layer.name() if hasattr(layer, 'name') else 'unknown'
            except RuntimeError:
                name = 'unknown'
            return f"{name}: not a vector layer"

        # Check if layer is valid using object_safety module
        is_postgres = layer.providerType() == 'postgres'

        if not is_valid_layer(layer):
            try:
                name = layer.name()
                is_valid_qgis = layer.isValid()
            except RuntimeError:
                name = 'unknown'
                is_valid_qgis = False
            reason = f"{name}: invalid layer (isValid={is_valid_qgis}, C++ object may be deleted)"
            if is_postgres:
                reason += " [PostgreSQL]"
                logger.warning(f"PostgreSQL layer '{name}' failed is_valid_layer check (isValid={is_valid_qgis})")
            return reason

        # For PostgreSQL: include even if source check fails (connection may be initializing)
        if is_postgres:
            logger.info(f"PostgreSQL layer '{layer.name()}': including despite any source availability issues")
            return None

        # Check source availability for non-PostgreSQL layers
        if require_source and not is_layer_source_available(layer, require_psycopg2=False):
            return f"{layer.name()}: source not available (provider={layer.providerType()})"

        return None  # Layer is valid

    def _log_filtering_results(
        self,
        input_count: int,
        usable: List,
        filtered_reasons: List[str]
    ) -> None:
        """Log filtering results with grouped reasons."""
        if filtered_reasons and input_count != len(usable):
            logger.info(f"filter_usable_layers: {input_count} input layers -> {len(usable)} usable layers. Filtered: {len(filtered_reasons)}")

            # Group filtered reasons by type for cleaner logging
            reason_types: Dict[str, List[str]] = {}
            for reason in filtered_reasons:
                reason_key = reason.split(':')[1].strip() if ':' in reason else reason
                if reason_key not in reason_types:
                    reason_types[reason_key] = []
                layer_name = reason.split(':')[0] if ':' in reason else 'unknown'
                reason_types[reason_key].append(layer_name)

            for reason_type, layers in reason_types.items():
                preview = ', '.join(layers[:5])
                suffix = '...' if len(layers) > 5 else ''
                logger.info(f"  Filtered ({reason_type}): {len(layers)} layer(s) - {preview}{suffix}")
        else:
            logger.info(f"filter_usable_layers: All {input_count} layers are usable")

    def is_layer_usable(self, layer) -> Tuple[bool, Optional[str]]:
        """
        Check if a single layer is usable.

        Args:
            layer: Layer to check

        Returns:
            Tuple of (is_usable, reason_if_not)
        """
        reason = self._validate_layer(layer, require_source=True)
        return (reason is None, reason)

    def is_vector_layer(self, layer) -> bool:
        """
        Check if layer is a valid vector layer.

        Args:
            layer: Layer to check

        Returns:
            True if valid vector layer, False otherwise
        """
        if is_sip_deleted(layer):
            return False
        return isinstance(layer, QgsVectorLayer)

    def is_postgres_layer(self, layer) -> bool:
        """
        Check if layer is a PostgreSQL layer.

        Args:
            layer: Layer to check

        Returns:
            True if PostgreSQL layer, False otherwise
        """
        if not self.is_vector_layer(layer):
            return False
        try:
            return layer.providerType() == 'postgres'
        except (RuntimeError, AttributeError):
            return False

    def is_spatialite_layer(self, layer) -> bool:
        """
        Check if layer is a Spatialite layer.

        Args:
            layer: Layer to check

        Returns:
            True if Spatialite layer, False otherwise
        """
        if not self.is_vector_layer(layer):
            return False
        try:
            return layer.providerType() == 'spatialite'
        except (RuntimeError, AttributeError):
            return False

    def get_provider_type(self, layer) -> str:
        """
        Get the provider type of a layer safely.

        Args:
            layer: Layer to check

        Returns:
            Provider type string or 'unknown'
        """
        if not self.is_vector_layer(layer):
            return 'unknown'
        try:
            provider = layer.providerType()
            # Normalize 'postgres' to 'postgresql' for consistency
            if provider == 'postgres':
                return 'postgresql'
            return provider
        except (RuntimeError, AttributeError):
            return 'unknown'

    def validate_postgres_layers_on_project_load(
        self,
        project,
        show_warning_callback=None
    ) -> List[str]:
        """
        Validate PostgreSQL layers for orphaned materialized view references.

        Sprint 17: Extracted from FilterMateApp._validate_postgres_layers_on_project_load()

        v2.8.1: When QGIS/FilterMate is closed and reopened, materialized views
        created for filtering are no longer present in the database. However,
        the layer's subset string may still reference them, causing
        "relation does not exist" errors.

        This method detects such orphaned references and clears them,
        restoring the layer to its unfiltered state.

        Args:
            project: QgsProject instance
            show_warning_callback: Optional callback(title, message) to show warnings

        Returns:
            List of layer names that were cleaned
        """
        try:
            from ..infrastructure.utils import validate_and_cleanup_postgres_layers
        except ImportError:
            logger.debug("validate_and_cleanup_postgres_layers not available")
            return []

        try:
            # Get all PostgreSQL layers from the project
            postgres_layers = []
            for layer in project.mapLayers().values():
                if self.is_postgresql_layer(layer):
                    postgres_layers.append(layer)

            if not postgres_layers:
                logger.debug("No PostgreSQL layers to validate for orphaned MVs")
                return []

            logger.debug(f"Validating {len(postgres_layers)} PostgreSQL layer(s) for orphaned MV references")

            # Validate and cleanup orphaned MV references
            cleaned_layers = validate_and_cleanup_postgres_layers(postgres_layers)

            if cleaned_layers:
                # Show warning to user about cleared filters
                layer_list = ", ".join(cleaned_layers[:3])
                if len(cleaned_layers) > 3:
                    layer_list += f" (+{len(cleaned_layers) - 3} other(s))"

                warning_msg = (
                    f"Cleared orphaned filter(s) from {len(cleaned_layers)} layer(s): {layer_list}. "
                    "Previous filters referenced temporary views that no longer exist."
                )

                if show_warning_callback:
                    show_warning_callback("FilterMate", warning_msg)

                logger.warning(
                    f"Cleared orphaned MV references from {len(cleaned_layers)} PostgreSQL layer(s) on project load"
                )
                return cleaned_layers
            else:
                logger.debug("No orphaned MV references found in PostgreSQL layers")
                return []

        except Exception as e:
            # Non-critical - don't fail project load
            logger.debug(f"Error validating PostgreSQL layers for orphaned MVs: {e}")
            return []
