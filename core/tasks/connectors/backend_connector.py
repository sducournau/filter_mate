"""
Backend Connector

Manages database connections for different backends (PostgreSQL, Spatialite, OGR).
Extracted from FilterEngineTask as part of Phase E13 refactoring (January 2026).

Responsibilities:
- Connection lifecycle management
- Provider type detection
- Connection validation
- Backend registry integration

Location: core/tasks/connectors/backend_connector.py
"""

import logging
from typing import Optional, Any, Dict

# Import constants
from ....infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
)

# Import PostgreSQL availability
from ....adapters.backends.postgresql_availability import (
    psycopg2, POSTGRESQL_AVAILABLE
)

# Import utilities
from ....infrastructure.utils import (
    detect_layer_provider_type,
    safe_spatialite_connect,
    get_datasource_connexion_from_layer
)

logger = logging.getLogger('FilterMate.Tasks.BackendConnector')


class BackendConnector:
    """
    Manages database connections for different backends.
    
    Provides unified interface for connecting to PostgreSQL, Spatialite, and OGR
    data sources. Handles connection validation, cleanup, and backend detection.
    
    Responsibilities:
    - PostgreSQL connection management
    - Spatialite connection management
    - OGR data source handling
    - Provider type detection
    - Backend registry integration
    - Connection pooling (future enhancement)
    
    Extracted from FilterEngineTask (lines 408-560) in Phase E13.
    
    Example:
        connector = BackendConnector(
            layer=source_layer,
            backend_registry=registry
        )
        
        # Get connection for layer's backend
        if connector.is_postgresql_available():
            conn = connector.get_postgresql_connection()
            try:
                # Use connection
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
            finally:
                conn.close()
        
        # Cleanup all resources
        connector.cleanup()
    """
    
    def __init__(
        self,
        layer: Optional[Any] = None,  # QgsVectorLayer
        backend_registry: Optional[Any] = None
    ):
        """
        Initialize BackendConnector.
        
        Args:
            layer: QGIS vector layer (optional)
            backend_registry: Optional backend registry for hexagonal architecture
        """
        self.layer = layer
        self.backend_registry = backend_registry
        
        # Detect provider type if layer provided
        self.provider_type = None
        if layer:
            self.provider_type = detect_layer_provider_type(layer)
        
        # Cache for connections (lazy initialization)
        self._postgresql_connection = None
        self._spatialite_connection = None
        
        logger.debug(
            f"BackendConnector initialized: "
            f"provider={self.provider_type}, "
            f"has_registry={backend_registry is not None}"
        )
    
    def get_backend_executor(self, layer_info: Dict) -> Optional[Any]:
        """
        Get appropriate backend executor for a layer.
        
        Extracted from FilterEngineTask._get_backend_executor (lines 408-427).
        
        Uses BackendRegistry if available (hexagonal pattern),
        otherwise falls back to legacy direct imports (Strangler Fig).
        
        Args:
            layer_info: Dict with 'layer_provider_type' key
            
        Returns:
            FilterExecutorPort implementation or None
        """
        if self.backend_registry:
            try:
                return self.backend_registry.get_executor(layer_info)
            except Exception as e:
                logger.warning(
                    f"BackendRegistry.get_executor failed: {e}, "
                    f"using legacy imports"
                )
        
        # Fallback: return None, caller should use legacy imports
        return None
    
    def has_backend_registry(self) -> bool:
        """
        Check if backend registry is available.
        
        Extracted from FilterEngineTask._has_backend_registry (lines 430-432).
        
        Returns:
            True if registry is available
        """
        return self.backend_registry is not None
    
    def is_postgresql_available(self) -> bool:
        """
        Check if PostgreSQL backend is available.
        
        Extracted from FilterEngineTask._is_postgresql_available (lines 434-444).
        
        Uses registry if available, otherwise checks global constant.
        
        Returns:
            True if PostgreSQL (psycopg2) is available
        """
        if self.backend_registry:
            return self.backend_registry.postgresql_available
        
        # Fallback to global constant
        return POSTGRESQL_AVAILABLE
    
    def get_postgresql_connection(self) -> Optional[Any]:
        """
        Get valid PostgreSQL connection for layer.
        
        Extracted from FilterEngineTask._get_valid_postgresql_connection (lines 549+).
        
        Returns:
            psycopg2 connection object or None if unavailable
            
        Raises:
            Exception if connection fails
        """
        if not self.is_postgresql_available():
            logger.warning("PostgreSQL not available (psycopg2 not installed)")
            return None
        
        if not self.layer:
            logger.warning("No layer provided for PostgreSQL connection")
            return None
        
        if self.provider_type != PROVIDER_POSTGRES:
            logger.warning(
                f"Layer provider is '{self.provider_type}', not PostgreSQL"
            )
            return None
        
        # Use cached connection if valid
        if self._postgresql_connection:
            try:
                # Test connection with simple query
                cursor = self._postgresql_connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                logger.debug("Reusing cached PostgreSQL connection")
                return self._postgresql_connection
            except Exception:
                # Connection invalid, will create new one
                logger.debug("Cached PostgreSQL connection invalid, creating new")
                self._postgresql_connection = None
        
        # Get fresh connection from layer
        try:
            connection, source_uri = get_datasource_connexion_from_layer(self.layer)
            
            if connection:
                self._postgresql_connection = connection
                logger.debug("Created new PostgreSQL connection")
                return connection
            else:
                logger.warning("Failed to get PostgreSQL connection from layer")
                return None
        
        except Exception as e:
            logger.error(f"Error getting PostgreSQL connection: {e}")
            raise
    
    def get_spatialite_connection(self, db_path: Optional[str] = None) -> Optional[Any]:
        """
        Get Spatialite connection.
        
        Extracted from FilterEngineTask._safe_spatialite_connect (line 547).
        
        Args:
            db_path: Path to Spatialite database (optional, uses layer if None)
            
        Returns:
            sqlite3 connection with Spatialite extension loaded
        """
        # Determine database path
        if not db_path and self.layer:
            # Extract path from layer data source
            source = self.layer.dataProvider().dataSourceUri()
            # For Spatialite, source is usually the file path
            db_path = source.split('|')[0] if '|' in source else source
        
        if not db_path:
            logger.warning("No database path provided for Spatialite connection")
            return None
        
        # Use infrastructure utility for safe connection
        try:
            conn = safe_spatialite_connect(db_path)
            
            if conn:
                self._spatialite_connection = conn
                logger.debug(f"Created Spatialite connection to {db_path}")
                return conn
            else:
                logger.warning(f"Failed to create Spatialite connection to {db_path}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting Spatialite connection: {e}")
            raise
    
    def cleanup_backend_resources(self):
        """
        Cleanup backend resources.
        
        Extracted from FilterEngineTask._cleanup_backend_resources (lines 506-517).
        
        Closes open connections and delegates to BackendRegistry if available.
        """
        # Close PostgreSQL connection
        if self._postgresql_connection:
            try:
                self._postgresql_connection.close()
                logger.debug("Closed PostgreSQL connection")
            except Exception as e:
                logger.debug(f"Error closing PostgreSQL connection: {e}")
            finally:
                self._postgresql_connection = None
        
        # Close Spatialite connection
        if self._spatialite_connection:
            try:
                self._spatialite_connection.close()
                logger.debug("Closed Spatialite connection")
            except Exception as e:
                logger.debug(f"Error closing Spatialite connection: {e}")
            finally:
                self._spatialite_connection = None
        
        # Delegate to registry
        if self.backend_registry:
            try:
                self.backend_registry.cleanup_all()
                logger.debug("Backend resources cleaned up via registry")
            except Exception as e:
                logger.debug(f"Registry cleanup failed: {e}")
    
    def detect_provider_type(self, layer: Optional[Any] = None) -> str:  # layer: Optional[QgsVectorLayer]
        """
        Detect provider type for layer.
        
        Args:
            layer: Layer to detect (uses self.layer if None)
            
        Returns:
            Provider type string (postgresql, spatialite, ogr, etc.)
        """
        target_layer = layer or self.layer
        
        if not target_layer:
            return 'unknown'
        
        provider_type = detect_layer_provider_type(target_layer)
        
        logger.debug(f"Detected provider type: {provider_type}")
        
        return provider_type
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup_backend_resources()
        return False
