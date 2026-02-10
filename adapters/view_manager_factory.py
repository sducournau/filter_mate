# -*- coding: utf-8 -*-
"""
Materialized View Factory - FilterMate v4.2

Factory for creating the appropriate view manager based on backend type.
Provides unified creation API for PostgreSQL MVs and Spatialite temp tables.

Usage:
    # Auto-detect from layer
    manager = create_view_manager_for_layer(layer)

    # Explicit backend
    manager = create_view_manager(backend_type='postgresql', connection=conn)
    manager = create_view_manager(backend_type='spatialite', db_path='/path/to/db.sqlite')

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Any

from ..core.ports.materialized_view_port import (
    MaterializedViewPort,
    ViewConfig,
    ViewType
)

logger = logging.getLogger('FilterMate.Backend.ViewManagerFactory')


def create_view_manager(
    backend_type: str,
    connection: Any = None,
    db_path: Optional[str] = None,
    session_id: Optional[str] = None,
    config: Optional[ViewConfig] = None
) -> MaterializedViewPort:
    """
    Create a view manager for the specified backend.

    Args:
        backend_type: 'postgresql' or 'spatialite'
        connection: Database connection (for PostgreSQL: connection pool, for Spatialite: sqlite3.Connection)
        db_path: Database path (Spatialite only)
        session_id: Session ID for scoping
        config: Optional ViewConfig

    Returns:
        MaterializedViewPort implementation

    Raises:
        ValueError: If backend_type is not supported
        ImportError: If required backend module is not available
    """
    backend_type = backend_type.lower()

    if backend_type in ('postgresql', 'postgres', 'postgis'):
        return _create_postgresql_manager(
            connection_pool=connection,
            session_id=session_id,
            config=config
        )

    elif backend_type in ('spatialite', 'sqlite', 'geopackage', 'gpkg'):
        return _create_spatialite_manager(
            db_path=db_path,
            connection=connection,
            session_id=session_id,
            config=config
        )

    else:
        raise ValueError(
            f"Unsupported backend type: {backend_type}. "
            "Supported: 'postgresql', 'spatialite'"
        )


def _create_postgresql_manager(
    connection_pool: Any = None,
    session_id: Optional[str] = None,
    config: Optional[ViewConfig] = None
) -> MaterializedViewPort:
    """Create PostgreSQL MaterializedViewManager."""
    try:
        from .backends.postgresql.mv_manager import (
            MaterializedViewManager,
            MVConfig
        )
    except ImportError as e:
        logger.error(f"[Factory] PostgreSQL MV manager not available: {e}")
        raise ImportError(
            "PostgreSQL backend not available. "
            "Ensure psycopg2 is installed."
        )

    # Convert ViewConfig to MVConfig if needed
    mv_config = None
    if config:
        mv_config = MVConfig(
            feature_threshold=config.feature_threshold,
            complexity_threshold=config.complexity_threshold,
            with_data=config.with_data,
            create_spatial_index=config.create_spatial_index,
            create_btree_indexes=config.create_btree_indexes,
            auto_refresh=config.auto_refresh,
            refresh_on_change=config.refresh_on_change,
            concurrent_refresh=config.concurrent_refresh
        )

    return MaterializedViewManager(
        connection_pool=connection_pool,
        config=mv_config,
        session_id=session_id
    )


def _create_spatialite_manager(
    db_path: Optional[str] = None,
    connection: Any = None,
    session_id: Optional[str] = None,
    config: Optional[ViewConfig] = None
) -> MaterializedViewPort:
    """Create Spatialite TempTableManager."""
    try:
        from .backends.spatialite.temp_table_manager import (
            SpatialiteTempTableManager
        )
    except ImportError as e:
        logger.error(f"[Factory] Spatialite temp table manager not available: {e}")
        raise ImportError(
            "Spatialite backend not available."
        )

    return SpatialiteTempTableManager(
        db_path=db_path,
        connection=connection,
        config=config,
        session_id=session_id
    )


def create_view_manager_for_layer(
    layer,
    session_id: Optional[str] = None,
    config: Optional[ViewConfig] = None
) -> Optional[MaterializedViewPort]:
    """
    Create a view manager based on layer provider type.

    Auto-detects the appropriate backend from the QGIS layer.

    Args:
        layer: QgsVectorLayer
        session_id: Session ID for scoping
        config: Optional ViewConfig

    Returns:
        MaterializedViewPort implementation or None if not supported
    """
    if not layer:
        logger.warning("[Factory] Cannot create view manager: layer is None")
        return None

    try:
        provider_type = layer.providerType()
    except Exception as e:
        logger.warning(f"[Factory] Cannot get layer provider type: {e}")
        return None

    logger.debug(f"[Factory] Creating view manager for provider: {provider_type}")

    if provider_type == 'postgres':
        # PostgreSQL layer
        try:
            connection = _get_postgresql_connection_from_layer(layer)
            return create_view_manager(
                backend_type='postgresql',
                connection=connection,
                session_id=session_id,
                config=config
            )
        except Exception as e:
            logger.warning(f"[Factory] PostgreSQL manager creation failed: {e}")
            return None

    elif provider_type in ('spatialite', 'ogr'):
        # Spatialite or GeoPackage/OGR layer
        try:
            db_path = _get_spatialite_path_from_layer(layer)
            if db_path:
                return create_view_manager(
                    backend_type='spatialite',
                    db_path=db_path,
                    session_id=session_id,
                    config=config
                )
        except Exception as e:
            logger.warning(f"[Factory] Spatialite manager creation failed: {e}")
            return None

    logger.info(f"[Factory] No view manager available for provider: {provider_type}")
    return None


def _get_postgresql_connection_from_layer(layer) -> Any:
    """Extract PostgreSQL connection from layer."""
    try:
        # Try to get connection from layer data source
        from ..adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE
        if not POSTGRESQL_AVAILABLE:
            raise ImportError("psycopg2 not available")

        import psycopg2

        # Parse connection string from layer
        layer.source()
        uri = layer.dataProvider().uri()

        conn_params = {
            'host': uri.host() or 'localhost',
            'port': uri.port() or '5432',
            'dbname': uri.database(),
            'user': uri.username(),
            'password': uri.password()
        }

        # Remove empty parameters
        conn_params = {k: v for k, v in conn_params.items() if v}

        return psycopg2.connect(**conn_params)

    except Exception as e:
        logger.error(f"[Factory] Failed to get PostgreSQL connection: {e}")
        raise


def _get_spatialite_path_from_layer(layer) -> Optional[str]:
    """Extract Spatialite database path from layer."""
    try:
        source = layer.source()

        # Parse source for database path
        # Format varies: "dbname='/path/to/db.sqlite' table=..."
        if 'dbname=' in source:
            import re
            match = re.search(r"dbname='([^']+)'", source)
            if match:
                return match.group(1)

        # For GeoPackage/OGR format
        uri = layer.dataProvider().uri()
        if uri.database():
            return uri.database()

        # Simple file path format
        if source.endswith(('.sqlite', '.db', '.gpkg', '.spatialite')):
            # May have |layername=... suffix
            return source.split('|')[0]

        return None

    except Exception as e:
        logger.warning(f"[Factory] Failed to get Spatialite path: {e}")
        return None


def get_view_type_for_backend(backend_type: str) -> ViewType:
    """
    Get the view type used by a backend.

    Args:
        backend_type: 'postgresql' or 'spatialite'

    Returns:
        ViewType enum value
    """
    backend_type = backend_type.lower()

    if backend_type in ('postgresql', 'postgres', 'postgis'):
        return ViewType.MATERIALIZED_VIEW

    elif backend_type in ('spatialite', 'sqlite', 'geopackage', 'gpkg'):
        return ViewType.TEMP_TABLE

    return ViewType.VIRTUAL_VIEW


__all__ = [
    'create_view_manager',
    'create_view_manager_for_layer',
    'get_view_type_for_backend',
]
