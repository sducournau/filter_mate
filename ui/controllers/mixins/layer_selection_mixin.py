"""
FilterMate Layer Selection Mixin.

Provides common layer selection functionality for controllers.
"""
from typing import Optional, List, Dict, Any

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsProject,
        QgsMapLayerType,
        QgsWkbTypes
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    # Mock types for testing
    QgsVectorLayer = Any
    QgsProject = Any

# Import centralized provider detection (v4.0.4 - eliminate duplication)
try:
    from ....infrastructure.utils import detect_provider_type
    _HAS_PROVIDER_UTILS = True
except ImportError:
    _HAS_PROVIDER_UTILS = False

# v4.0.10: Import centralized layer validation (eliminate duplication)
try:
    from ....infrastructure.utils import is_layer_valid as _is_layer_valid_util
    _HAS_VALIDATION_UTILS = True
except ImportError:
    _HAS_VALIDATION_UTILS = False


class LayerSelectionMixin:
    """
    Mixin providing common layer selection functionality.

    Use with controllers that need layer selection capabilities.
    Provides utilities for:
    - Layer validity checking
    - Provider type detection and normalization
    - Layer listing and retrieval
    - Layer information extraction

    Usage:
        class MyController(BaseController, LayerSelectionMixin):
            def get_current_layer(self) -> Optional[QgsVectorLayer]:
                return self._current_layer

            def on_layer_change(self, layer):
                if self.is_layer_valid(layer):
                    provider = self.get_layer_provider_type(layer)
                    info = self.get_layer_info(layer)
    """

    # Provider type normalization mapping
    PROVIDER_TYPE_MAP = {
        'postgres': 'postgresql',
        'spatialite': 'spatialite',
        'ogr': 'ogr',
        'memory': 'memory',
        'virtual': 'virtual',
        'delimitedtext': 'csv',
        'gpx': 'gpx',
        'wfs': 'wfs',
    }

    def get_current_layer(self) -> Optional[QgsVectorLayer]:
        """
        Get currently selected layer.

        Must be implemented by subclass.

        Returns:
            Currently selected vector layer or None

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError(
            "Subclass must implement get_current_layer()"
        )

    def is_layer_valid(self, layer: Optional[QgsVectorLayer]) -> bool:
        """
        Check if layer is valid for operations.

        v4.0.10: Delegates to centralized validation_utils.is_layer_valid()
        which includes SIP deletion check for robustness.

        Args:
            layer: Layer to validate

        Returns:
            True if layer is valid and usable, False otherwise
        """
        # v4.0.10: Delegate to centralized validation (includes SIP check)
        if _HAS_VALIDATION_UTILS:
            return _is_layer_valid_util(layer)

        # Fallback for testing or import issues
        if layer is None:
            return False

        if not QGIS_AVAILABLE:
            # For testing, just check it's not None
            return layer is not None

        # Check it's a QgsVectorLayer
        if not isinstance(layer, QgsVectorLayer):
            return False

        # Check layer is valid
        if not layer.isValid():
            return False

        return True

    def get_layer_provider_type(self, layer: QgsVectorLayer) -> str:
        """
        Get normalized provider type for layer.

        Normalizes QGIS provider names to consistent internal names:
        - 'postgres' → 'postgresql'
        - 'spatialite' → 'spatialite'
        - 'ogr' → 'ogr'
        - 'memory' → 'memory'

        Args:
            layer: Vector layer to check

        Returns:
            Normalized provider type string ('postgresql', 'spatialite', 'ogr', etc.)
            Returns 'unknown' if provider not recognized
        """
        # v4.0.4: Delegate to centralized provider detection
        if _HAS_PROVIDER_UTILS:
            provider_type = detect_provider_type(layer)
            return str(provider_type) if provider_type else 'unknown'

        # Fallback to local mapping
        if layer is None:
            return 'unknown'

        try:
            provider = layer.providerType()
        except (AttributeError, RuntimeError):
            return 'unknown'

        return self.PROVIDER_TYPE_MAP.get(provider, 'unknown')

    def get_all_vector_layers(self) -> List[QgsVectorLayer]:
        """
        Get all vector layers in current project.

        Returns:
            List of all vector layers in the project
        """
        if not QGIS_AVAILABLE:
            return []

        try:
            project = QgsProject.instance()
            layers = []

            for layer in project.mapLayers().values():
                if layer.type() == QgsMapLayerType.VectorLayer:
                    layers.append(layer)

            return layers
        except (RuntimeError, AttributeError):
            return []

    def get_layer_by_id(self, layer_id: str) -> Optional[QgsVectorLayer]:
        """
        Get layer by ID.

        Args:
            layer_id: QGIS layer ID string

        Returns:
            Vector layer if found and valid, None otherwise
        """
        if not layer_id:
            return None

        if not QGIS_AVAILABLE:
            return None

        try:
            project = QgsProject.instance()
            layer = project.mapLayer(layer_id)

            if isinstance(layer, QgsVectorLayer):
                return layer
            return None
        except (RuntimeError, AttributeError):
            return None

    def get_layer_by_name(self, name: str) -> Optional[QgsVectorLayer]:
        """
        Get layer by name.

        Args:
            name: Layer name

        Returns:
            First vector layer matching name, None if not found
        """
        if not name:
            return None

        if not QGIS_AVAILABLE:
            return None

        try:
            project = QgsProject.instance()
            layers = project.mapLayersByName(name)

            for layer in layers:
                if isinstance(layer, QgsVectorLayer):
                    return layer
            return None
        except (RuntimeError, AttributeError):
            return None

    def get_layer_info(self, layer: QgsVectorLayer) -> Dict[str, Any]:
        """
        Get layer information dictionary.

        Args:
            layer: Vector layer to get info from

        Returns:
            Dictionary with layer information:
            - id: Layer ID
            - name: Layer name
            - provider: Normalized provider type
            - feature_count: Number of features
            - geometry_type: Geometry type name
            - crs: CRS auth ID (e.g., 'EPSG:4326')
            - is_valid: Whether layer is valid
            - has_geometry: Whether layer has geometry
        """
        if layer is None:
            return {
                'id': None,
                'name': None,
                'provider': 'unknown',
                'feature_count': 0,
                'geometry_type': 'unknown',
                'crs': None,
                'is_valid': False,
                'has_geometry': False
            }

        try:
            geometry_type = self._get_geometry_type_name(layer)
            has_geometry = geometry_type not in ('NoGeometry', 'unknown')

            return {
                'id': layer.id(),
                'name': layer.name(),
                'provider': self.get_layer_provider_type(layer),
                'feature_count': layer.featureCount(),
                'geometry_type': geometry_type,
                'crs': layer.crs().authid() if layer.crs().isValid() else None,
                'is_valid': layer.isValid(),
                'has_geometry': has_geometry
            }
        except (AttributeError, RuntimeError):
            return {
                'id': None,
                'name': None,
                'provider': 'unknown',
                'feature_count': 0,
                'geometry_type': 'unknown',
                'crs': None,
                'is_valid': False,
                'has_geometry': False
            }

    def _get_geometry_type_name(self, layer: QgsVectorLayer) -> str:
        """
        Get human-readable geometry type name.

        Args:
            layer: Vector layer

        Returns:
            Geometry type name string
        """
        if not QGIS_AVAILABLE:
            return 'unknown'

        try:
            geom_type = layer.geometryType()

            # Map QGIS geometry types to readable names
            type_names = {
                QgsWkbTypes.PointGeometry: 'Point',
                QgsWkbTypes.LineGeometry: 'Line',
                QgsWkbTypes.PolygonGeometry: 'Polygon',
                QgsWkbTypes.UnknownGeometry: 'Unknown',
                QgsWkbTypes.NullGeometry: 'NoGeometry',
            }

            return type_names.get(geom_type, 'unknown')
        except (AttributeError, RuntimeError):
            return 'unknown'

    def get_layer_fields(self, layer: QgsVectorLayer) -> List[Dict[str, Any]]:
        """
        Get list of field information for a layer.

        Args:
            layer: Vector layer

        Returns:
            List of field dictionaries with name, type, length
        """
        if layer is None:
            return []

        try:
            fields = []
            for field in layer.fields():
                fields.append({
                    'name': field.name(),
                    'type': field.typeName(),
                    'length': field.length(),
                    'precision': field.precision(),
                    'comment': field.comment()
                })
            return fields
        except (AttributeError, RuntimeError):
            return []

    def is_postgresql_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if layer is a PostgreSQL layer.

        Args:
            layer: Vector layer to check

        Returns:
            True if PostgreSQL layer, False otherwise
        """
        return self.get_layer_provider_type(layer) == 'postgresql'

    def is_spatialite_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if layer is a Spatialite layer.

        Args:
            layer: Vector layer to check

        Returns:
            True if Spatialite layer, False otherwise
        """
        return self.get_layer_provider_type(layer) == 'spatialite'

    def is_file_based_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if layer is file-based (OGR, CSV, etc.).

        Args:
            layer: Vector layer to check

        Returns:
            True if file-based layer, False otherwise
        """
        provider = self.get_layer_provider_type(layer)
        return provider in ('ogr', 'csv', 'gpx')
