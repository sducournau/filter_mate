"""
FilterMate Provider Utilities.

Consolidated provider detection logic to eliminate duplicate patterns.
This module replaces 15+ instances of inline provider detection.

v4.1.5: ProviderType is now imported from core.domain.filter_expression
to ensure a single source of truth.
"""
from typing import Optional, Dict, Any

try:
    from qgis.core import QgsVectorLayer, QgsDataSourceUri
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    QgsVectorLayer = None

# v4.1.5: Import canonical ProviderType from domain layer
from ...core.domain.filter_expression import ProviderType


# Mapping from QGIS provider names to our enum
_PROVIDER_MAP: Dict[str, ProviderType] = {
    # PostgreSQL variants
    'postgres': ProviderType.POSTGRESQL,
    'postgresql': ProviderType.POSTGRESQL,
    'postgis': ProviderType.POSTGRESQL,

    # Spatialite variants
    'spatialite': ProviderType.SPATIALITE,
    'gpkg': ProviderType.SPATIALITE,  # GeoPackage uses spatialite provider

    # OGR provider
    'ogr': ProviderType.OGR,

    # Memory/Virtual providers
    'memory': ProviderType.MEMORY,
    'virtual': ProviderType.MEMORY,
}

# Backend availability status (can be updated at runtime)
_BACKEND_AVAILABILITY: Dict[ProviderType, bool] = {
    ProviderType.POSTGRESQL: None,  # Will be checked lazily
    ProviderType.SPATIALITE: True,  # Always available
    ProviderType.OGR: True,  # Always available
    ProviderType.MEMORY: True,  # Always available
    ProviderType.UNKNOWN: False,
}


def detect_provider_type(layer) -> ProviderType:
    """
    Detect the provider type for a layer.

    This is the canonical way to detect provider type in FilterMate.
    Replaces all inline if/elif chains.

    Args:
        layer: QGIS vector layer (QgsVectorLayer)

    Returns:
        ProviderType enum value

    Example:
        >>> provider = detect_provider_type(my_layer)
        >>> if provider == ProviderType.POSTGRESQL:
        ...     use_postgresql_optimizations()
    """
    if layer is None:
        return ProviderType.UNKNOWN

    # Check for deleted Qt object
    try:
        if not layer.isValid():
            return ProviderType.UNKNOWN
        qgis_provider = layer.providerType().lower()
    except RuntimeError:
        # Layer C++ object deleted
        return ProviderType.UNKNOWN

    # Check for GeoPackage (special case - uses OGR but we treat as Spatialite)
    if qgis_provider == 'ogr':
        try:
            source = layer.source().lower()
            if '.gpkg' in source:
                return ProviderType.SPATIALITE
        except (RuntimeError, AttributeError):
            pass

    return _PROVIDER_MAP.get(qgis_provider, ProviderType.UNKNOWN)


def is_postgresql(layer) -> bool:
    """
    Check if layer is PostgreSQL/PostGIS.

    Args:
        layer: QGIS vector layer

    Returns:
        True if layer uses PostgreSQL provider
    """
    return detect_provider_type(layer) == ProviderType.POSTGRESQL


def is_spatialite(layer) -> bool:
    """
    Check if layer is Spatialite or GeoPackage.

    Note: GeoPackage layers are treated as Spatialite for backend purposes.

    Args:
        layer: QGIS vector layer

    Returns:
        True if layer uses Spatialite provider
    """
    return detect_provider_type(layer) == ProviderType.SPATIALITE


def is_ogr(layer) -> bool:
    """
    Check if layer uses OGR provider.

    Note: GeoPackage layers return False (treated as Spatialite).

    Args:
        layer: QGIS vector layer

    Returns:
        True if layer uses OGR provider
    """
    return detect_provider_type(layer) == ProviderType.OGR


def is_memory(layer) -> bool:
    """
    Check if layer is in-memory or virtual.

    Args:
        layer: QGIS vector layer

    Returns:
        True if layer is memory-based
    """
    return detect_provider_type(layer) == ProviderType.MEMORY


def is_geopackage(layer) -> bool:
    """
    Check if layer is specifically a GeoPackage.

    Args:
        layer: QGIS vector layer

    Returns:
        True if layer source is a GeoPackage file
    """
    if layer is None:
        return False

    try:
        source = layer.source().lower()
        return '.gpkg' in source
    except (RuntimeError, AttributeError):
        return False


def get_provider_display_name(provider: ProviderType) -> str:
    """
    Get human-readable name for provider.

    Args:
        provider: ProviderType enum value

    Returns:
        Display-friendly name string
    """
    names = {
        ProviderType.POSTGRESQL: "PostgreSQL",
        ProviderType.SPATIALITE: "Spatialite",
        ProviderType.OGR: "OGR",
        ProviderType.MEMORY: "Memory",
        ProviderType.UNKNOWN: "Unknown",
    }
    return names.get(provider, "Unknown")


def get_provider_icon_name(provider: ProviderType) -> str:
    """
    Get icon filename for provider.

    Args:
        provider: ProviderType enum value

    Returns:
        Icon filename (without path)
    """
    icons = {
        ProviderType.POSTGRESQL: "postgresql.svg",
        ProviderType.SPATIALITE: "spatialite.svg",
        ProviderType.OGR: "ogr.svg",
        ProviderType.MEMORY: "memory.svg",
        ProviderType.UNKNOWN: "unknown.svg",
    }
    return icons.get(provider, "unknown.svg")


def is_backend_available(provider: ProviderType) -> bool:
    """
    Check if a backend is available for use.

    For PostgreSQL, this checks if psycopg2 is installed.
    Other backends are always available.

    Args:
        provider: ProviderType enum value

    Returns:
        True if backend can be used
    """
    global _BACKEND_AVAILABILITY

    if provider == ProviderType.POSTGRESQL:
        if _BACKEND_AVAILABILITY[ProviderType.POSTGRESQL] is None:
            # Lazy check for psycopg2
            try:
                import psycopg2  # noqa: F401
                _BACKEND_AVAILABILITY[ProviderType.POSTGRESQL] = True
            except ImportError:
                _BACKEND_AVAILABILITY[ProviderType.POSTGRESQL] = False
        return _BACKEND_AVAILABILITY[ProviderType.POSTGRESQL]

    return _BACKEND_AVAILABILITY.get(provider, False)


def get_optimal_backend_for_layer(layer) -> ProviderType:
    """
    Determine the optimal backend for a layer.

    Considers:
    - Layer's native provider
    - Backend availability
    - Performance characteristics

    Args:
        layer: QGIS vector layer

    Returns:
        Best available ProviderType for the layer
    """
    native_provider = detect_provider_type(layer)

    # If native provider's backend is available, use it
    if is_backend_available(native_provider):
        return native_provider

    # PostgreSQL not available, fall back
    if native_provider == ProviderType.POSTGRESQL:
        # Try Spatialite, then OGR
        if is_backend_available(ProviderType.SPATIALITE):
            return ProviderType.SPATIALITE
        return ProviderType.OGR

    # Default fallback
    return ProviderType.OGR


def get_connection_info(layer) -> Optional[Dict[str, Any]]:
    """
    Extract connection information from layer.

    Args:
        layer: QGIS vector layer

    Returns:
        Dict with connection info, or None if not extractable
    """
    if layer is None:
        return None

    provider = detect_provider_type(layer)

    try:
        if provider == ProviderType.POSTGRESQL and HAS_QGIS:
            uri = QgsDataSourceUri(layer.source())
            return {
                'provider': provider,
                'host': uri.host(),
                'port': uri.port() or '5432',
                'database': uri.database(),
                'schema': uri.schema() or 'public',
                'table': uri.table(),
                'geometry_column': uri.geometryColumn(),
                'username': uri.username(),
                'srid': uri.srid(),
            }

        elif provider == ProviderType.SPATIALITE:
            source = layer.source()
            # Parse Spatialite/GPKG source
            # Format: "/path/to/file.gpkg|layername=table_name"
            parts = source.split('|')
            db_path = parts[0]
            table_name = None
            if len(parts) > 1:
                for part in parts[1:]:
                    if part.startswith('layername='):
                        table_name = part.replace('layername=', '')

            return {
                'provider': provider,
                'database': db_path,
                'table': table_name or layer.name(),
                'is_geopackage': is_geopackage(layer),
            }

        elif provider == ProviderType.OGR:
            return {
                'provider': provider,
                'source': layer.source(),
            }

        elif provider == ProviderType.MEMORY:
            return {
                'provider': provider,
                'name': layer.name(),
            }

    except (RuntimeError, AttributeError, ValueError):
        pass

    return {'provider': provider}


def supports_subset_string(layer) -> bool:
    """
    Check if layer supports subset string (filter expression).

    Args:
        layer: QGIS vector layer

    Returns:
        True if layer supports setSubsetString()
    """
    if layer is None:
        return False

    try:
        provider = layer.dataProvider()
        if provider is None:
            return False
        return bool(provider.capabilities() & provider.SelectAtId)
    except (RuntimeError, AttributeError):
        return False


def get_all_provider_types() -> list:
    """
    Get list of all provider types.

    Returns:
        List of ProviderType values (excluding UNKNOWN)
    """
    return [p for p in ProviderType if p != ProviderType.UNKNOWN]


def get_available_backends() -> list:
    """
    Get list of currently available backends.

    Returns:
        List of available ProviderType values
    """
    return [p for p in ProviderType if is_backend_available(p)]
