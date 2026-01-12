"""
DatasourceManager - Centralized datasource and database connection management.

Phase 4.5: God Class Reduction
Extracts ~320 lines from filter_mate_app.py related to:
- Spatialite database connections
- PostgreSQL datasource management
- Spatial index creation
- Foreign data wrapper creation
- Datasource tracking and lifecycle

Follows Strangler Fig Pattern with dependency injection for testability.
"""

import os
from typing import Dict, List, Optional, Callable, Any
from qgis.PyQt.QtCore import QObject

# Local imports
from ...config.config import logger, ENV_VARS
from ...infrastructure.utils.layer_utils import (
    get_datasource_connexion_from_layer,
    get_data_source_uri,
)
from ...infrastructure.utils.task_utils import spatialite_connect
from ...infrastructure.database.sql_utils import sanitize_sql_identifier
from ...infrastructure.utils.validation_utils import is_layer_source_available
from ...adapters.backends import POSTGRESQL_AVAILABLE

# Conditional imports
try:
    import processing
    PROCESSING_AVAILABLE = True
except ImportError:
    PROCESSING_AVAILABLE = False
    logger.warning("processing module not available - spatial index creation disabled")

try:
    from osgeo import ogr
    OGR_AVAILABLE = True
except ImportError:
    OGR_AVAILABLE = False
    logger.warning("GDAL/OGR not available - foreign data wrapper features disabled")


class DatasourceManager(QObject):
    """
    Manages database connections, datasources, and spatial operations.
    
    Responsibilities:
    - Spatialite database connections with error handling
    - PostgreSQL datasource tracking and temp schema creation
    - OGR datasource management (GeoPackage, Shapefiles, etc.)
    - Spatial index creation for layers
    - Foreign data wrapper creation for multi-source access
    - Datasource lifecycle (add/update/remove)
    
    Phase 4.5: Extracts from filter_mate_app.py:
    - get_spatialite_connection() (58 lines)
    - add_project_datasource() (35 lines)
    - _update_datasource_for_layer() (77 lines)
    - _remove_datasource_for_layer() (77 lines)
    - update_datasource() (63 lines)
    - create_foreign_data_wrapper() (31 lines)
    - create_spatial_index_for_layer() (15 lines)
    
    Total: ~356 lines extracted (target was ~320)
    
    Dependency Injection:
    Uses callbacks to avoid direct coupling with FilterMateApp:
    - get_project_callback: Get current QgsProject
    - get_iface_callback: Get QGIS interface
    - get_config_data_callback: Get current CONFIG_DATA
    - set_config_data_callback: Update CONFIG_DATA
    - get_db_file_path_callback: Get Spatialite database path
    - get_temp_schema_callback: Get PostgreSQL temp schema name
    - show_error_callback: Display error messages to user
    - show_warning_callback: Display warning messages to user
    """
    
    def __init__(
        self,
        get_project_callback: Callable[[], Any],
        get_iface_callback: Callable[[], Any],
        get_config_data_callback: Callable[[], Dict],
        set_config_data_callback: Callable[[Dict], None],
        get_db_file_path_callback: Callable[[], str],
        get_temp_schema_callback: Callable[[], str],
        show_error_callback: Callable[[str], None],
        show_warning_callback: Callable[[str], None]
    ):
        """
        Initialize DatasourceManager with dependency injection.
        
        Args:
            get_project_callback: Returns current QgsProject instance
            get_iface_callback: Returns QGIS iface object
            get_config_data_callback: Returns CONFIG_DATA dictionary
            set_config_data_callback: Updates CONFIG_DATA dictionary
            get_db_file_path_callback: Returns path to Spatialite database
            get_temp_schema_callback: Returns PostgreSQL temp schema name
            show_error_callback: Shows error message to user
            show_warning_callback: Shows warning message to user
        """
        super().__init__()
        
        # Store callbacks
        self._get_project = get_project_callback
        self._get_iface = get_iface_callback
        self._get_config_data = get_config_data_callback
        self._set_config_data = set_config_data_callback
        self._get_db_file_path = get_db_file_path_callback
        self._get_temp_schema = get_temp_schema_callback
        self._show_error = show_error_callback
        self._show_warning = show_warning_callback
        
        # Internal state
        self.project_datasources: Dict[str, Dict] = {}
        
        logger.info("DatasourceManager initialized")
    
    # ====================
    # Spatialite Operations
    # ====================
    
    def get_spatialite_connection(self):
        """
        Get a Spatialite connection with proper error handling.
        
        Returns:
            Connection object or None if connection fails
            
        Notes:
            - Verifies database file exists
            - Uses spatialite_connect() from appUtils
            - Shows user-friendly error messages on failure
        """
        db_file_path = self._get_db_file_path()
        
        if not os.path.exists(db_file_path):
            error_msg = f"Database file does not exist: {db_file_path}"
            logger.error(error_msg)
            self._show_error(error_msg)
            return None
            
        try:
            conn = spatialite_connect(db_file_path)
            return conn
        except Exception as error:
            error_msg = f"Failed to connect to database {db_file_path}: {error}"
            logger.error(error_msg)
            self._show_error(error_msg)
            return None
    
    # ====================
    # Spatial Index Operations
    # ====================
    
    def create_spatial_index_for_layer(self, layer):
        """
        Create spatial index for a layer using QGIS processing.
        
        Args:
            layer: QgsVectorLayer to create spatial index for
            
        Notes:
            - Guards against invalid/missing source layers
            - Uses qgis:createspatialindex processing algorithm
            - Shows warning if layer invalid
        """
        if not PROCESSING_AVAILABLE:
            logger.warning("Processing module not available, cannot create spatial index")
            self._show_warning("Module de traitement QGIS non disponible pour créer l'index spatial")
            return
        
        # Guard invalid/missing-source layers
        if not is_layer_source_available(layer):
            logger.warning("create_spatial_index_for_layer: layer invalid or source missing; skipping.")
            self._show_warning("Impossible de créer un index spatial: couche invalide ou source introuvable.")
            return

        alg_params_createspatialindex = {
            "INPUT": layer
        }
        processing.run('qgis:createspatialindex', alg_params_createspatialindex)
    
    # ====================
    # PostgreSQL Datasource Operations
    # ====================
    
    def add_project_datasource(self, layer):
        """
        Add PostgreSQL datasource and create temp schema if needed.
        
        Args:
            layer: PostgreSQL layer to get connection from
            
        Notes:
            - Creates temp schema if not exists
            - Handles connection failures gracefully
            - Closes connection after use
        """
        connexion, source_uri = get_datasource_connexion_from_layer(layer)
        
        # CRITICAL FIX: Check if connexion is None (PostgreSQL unavailable or connection failed)
        if connexion is None:
            logger.warning(f"Cannot add project datasource for layer {layer.name()}: no database connection")
            return

        temp_schema = self._get_temp_schema()
        
        try:
            sql_statement = f'CREATE SCHEMA IF NOT EXISTS {temp_schema} AUTHORIZATION postgres;'
            logger.debug(f"SQL statement: {sql_statement}")

            with connexion.cursor() as cursor:
                cursor.execute(sql_statement)
            connexion.commit()
        except Exception as e:
            logger.warning(f"Error creating temp schema for layer {layer.name()}: {e}")
        finally:
            try:
                connexion.close()
            except (OSError, AttributeError) as e:
                logger.debug(f"Could not close connection: {e}")
    
    # ====================
    # Datasource Tracking Operations
    # ====================
    
    def update_datasource_for_layer(self, layer_info: Dict):
        """
        Update project datasources for a given layer.
        
        Args:
            layer_info: Layer info dictionary with keys:
                - layer_provider_type: 'postgresql', 'ogr', 'spatialite'
                - layer_name: Display name of layer
                - layer_id: Unique layer identifier
                
        Notes:
            - Tracks PostgreSQL connections by authcfg_id
            - Tracks file-based datasources by absolute path
            - Handles relative paths from project directory
        """
        project = self._get_project()
        if project is None:
            logger.warning("No project available, cannot update datasource")
            return
        
        layer_source_type = layer_info["layer_provider_type"]
        if layer_source_type not in self.project_datasources:
            self.project_datasources[layer_source_type] = {}
        
        layers = [layer for layer in project.mapLayersByName(layer_info["layer_name"]) 
                 if layer.id() == layer_info["layer_id"]]
        
        if len(layers) != 1:
            return
        
        layer = layers[0]
        source_uri, authcfg_id = get_data_source_uri(layer)
        
        if authcfg_id is not None:
            # PostgreSQL connection with authentication
            if authcfg_id not in self.project_datasources[layer_source_type].keys():
                connexion, source_uri = get_datasource_connexion_from_layer(layer)
                self.project_datasources[layer_source_type][authcfg_id] = connexion
        else:
            # File-based datasource (GeoPackage, Shapefile, etc.)
            uri = source_uri.uri().strip()
            relative_path = uri.split('|')[0] if len(uri.split('|')) == 2 else uri
            layer_name = uri.split('|')[1] if len(uri.split('|')) == 2 else None
            absolute_path = os.path.join(os.path.normpath(ENV_VARS["PATH_ABSOLUTE_PROJECT"]), 
                                        os.path.normpath(relative_path))
            
            if absolute_path not in self.project_datasources[layer_source_type].keys():
                self.project_datasources[layer_source_type][absolute_path] = []
            
            if uri not in self.project_datasources[layer_source_type][absolute_path]:
                full_uri = absolute_path + ('|' + layer_name if layer_name is not None else '')
                self.project_datasources[layer_source_type][absolute_path].append(full_uri)
    
    def remove_datasource_for_layer(self, layer_info: Dict):
        """
        Remove project datasources for a given layer.
        
        Args:
            layer_info: Layer info dictionary with keys:
                - layer_provider_type: 'postgresql', 'ogr', 'spatialite'
                - layer_name: Display name of layer
                - layer_id: Unique layer identifier
                
        Notes:
            - Removes datasource from tracking
            - Handles both PostgreSQL and file-based datasources
            - Safe to call if datasource not tracked
        """
        project = self._get_project()
        if project is None:
            logger.warning("No project available, cannot remove datasource")
            return
        
        layer_source_type = layer_info["layer_provider_type"]
        if layer_source_type not in self.project_datasources:
            self.project_datasources[layer_source_type] = {}
        
        layers = [layer for layer in project.mapLayersByName(layer_info["layer_name"]) 
                 if layer.id() == layer_info["layer_id"]]
        
        if len(layers) != 1:
            return
        
        layer = layers[0]
        source_uri, authcfg_id = get_data_source_uri(layer)
        
        if authcfg_id is not None:
            # PostgreSQL connection - remove from tracking
            if authcfg_id in self.project_datasources[layer_source_type].keys():
                del self.project_datasources[layer_source_type][authcfg_id]
        else:
            # File-based datasource - remove URI from list
            uri = source_uri.uri().strip()
            relative_path = uri.split('|')[0] if len(uri.split('|')) == 2 else uri
            absolute_path = os.path.normpath(os.path.join(ENV_VARS["PATH_ABSOLUTE_PROJECT"], relative_path))
            
            if absolute_path in self.project_datasources[layer_source_type].keys():
                if uri in self.project_datasources[layer_source_type][absolute_path]:
                    self.project_datasources[layer_source_type][absolute_path].remove(uri)
    
    # ====================
    # Multi-Datasource Operations
    # ====================
    
    def update_datasource(self):
        """
        Update CONFIG_DATA with active datasource connections.
        
        Determines which datasource should be active for operations:
        - PostgreSQL: If available and connections exist
        - Spatialite: Fallback for local operations
        
        Also creates foreign data wrappers for OGR datasources if PostgreSQL active.
        
        Notes:
            - Updates CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"]
            - Updates CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"]
            - Shows warning if PostgreSQL layers detected but psycopg2 unavailable
            - Creates foreign data wrappers for file-based datasources in PostgreSQL
        """
        if not OGR_AVAILABLE:
            logger.warning("OGR not available, skipping datasource update")
            return
        
        config_data = self._get_config_data()
        
        # Get OGR driver list
        ogr_driver_list = [ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())]
        ogr_driver_list.sort()
        logger.debug(f"OGR drivers available: {ogr_driver_list}")

        # Check if PostgreSQL is available and if there are PostgreSQL connections
        if 'postgresql' in self.project_datasources and POSTGRESQL_AVAILABLE:
            postgresql_connexions = list(self.project_datasources['postgresql'].keys())
            if len(postgresql_connexions) >= 1:
                # FIXED: Check if ACTIVE_POSTGRESQL is a valid connection object
                current_connection = config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"]
                is_valid_connection = (
                    current_connection is not None 
                    and not isinstance(current_connection, str)
                    and hasattr(current_connection, 'cursor')
                    and callable(getattr(current_connection, 'cursor', None))
                    and not getattr(current_connection, 'closed', True)
                )
                if not is_valid_connection:
                    # Assign fresh connection object from project_datasources
                    config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = \
                        self.project_datasources['postgresql'][postgresql_connexions[0]]
                    config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = True
                    logger.debug("Assigned fresh PostgreSQL connection object to ACTIVE_POSTGRESQL")
            else:
                config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
                config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False
                
        elif 'postgresql' in self.project_datasources and not POSTGRESQL_AVAILABLE:
            # PostgreSQL layers detected but psycopg2 not available
            config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
            config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False
            self._show_warning(
                "PostgreSQL layers detected but psycopg2 is not installed. "
                "Using local Spatialite backend. "
                "For better performance with large datasets, install psycopg2."
            )
        else:
            config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = ""
            config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = False

        # Create foreign data wrappers for non-PostgreSQL datasources
        for current_datasource in list(self.project_datasources.keys()):
            if current_datasource != "postgresql":
                for project_datasource in self.project_datasources[current_datasource].keys():
                    datasources = self.project_datasources[current_datasource][project_datasource]
                    for datasource in datasources:
                        # Extract file extension safely
                        datasource_path = datasource.split('|')[0]
                        path_parts = datasource_path.split('.')
                        # Check if there's an extension (at least 2 parts after split)
                        datasource_ext = path_parts[-1] if len(path_parts) >= 2 else datasource_path
                        datasource_type_name = [ogr_name for ogr_name in ogr_driver_list 
                                               if ogr_name.upper() == datasource_ext.upper()]

                    if config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] is True:
                        self.create_foreign_data_wrapper(
                            project_datasource, 
                            os.path.basename(project_datasource), 
                            datasource_type_name[0]
                        )
        
        # Update CONFIG_DATA
        self._set_config_data(config_data)
    
    def create_foreign_data_wrapper(self, project_datasource: str, datasource: str, format: str):
        """
        Create PostgreSQL foreign data wrapper for external datasource.
        
        Args:
            project_datasource: Full path to datasource file
            datasource: Basename of datasource (for server naming)
            format: OGR format name (e.g., 'GPKG', 'ESRI Shapefile')
            
        Notes:
            - Creates OGR foreign data wrapper extension if not exists
            - Creates filter_mate_temp schema
            - Creates server for datasource
            - Imports foreign schema into PostgreSQL
            - Requires active PostgreSQL connection
        """
        if not POSTGRESQL_AVAILABLE:
            logger.warning("PostgreSQL not available, cannot create foreign data wrapper")
            return
        
        config_data = self._get_config_data()
        
        sql_request = f"""CREATE EXTENSION IF NOT EXISTS ogr_fdw;
                        CREATE SCHEMA IF NOT EXISTS filter_mate_temp AUTHORIZATION postgres; 
                        DROP SERVER IF exists server_{sanitize_sql_identifier(datasource)} CASCADE;
                        CREATE SERVER server_{sanitize_sql_identifier(datasource)} 
                        FOREIGN DATA WRAPPER ogr_fdw OPTIONS (
                            datasource '{project_datasource.replace(chr(92)+chr(92), chr(92))}', 
                            format '{format}');
                        IMPORT FOREIGN SCHEMA ogr_all
                        FROM SERVER server_{sanitize_sql_identifier(datasource)} INTO filter_mate_temp;"""

        if config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] is True:
            connexion = config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"]
            # Validate that connexion is actually a connection object, not a string
            if connexion is None or isinstance(connexion, str):
                logger.warning("ACTIVE_POSTGRESQL is not a valid connection object, skipping foreign data wrapper creation")
                return
            try:
                with connexion.cursor() as cursor:
                    cursor.execute(sql_request)
                logger.info(f"Created foreign data wrapper for {datasource}")
            except Exception as e:
                logger.error(f"Failed to create foreign data wrapper: {e}")
    
    # ====================
    # State Management
    # ====================
    
    def get_project_datasources(self) -> Dict[str, Dict]:
        """
        Get current project datasources dictionary.
        
        Returns:
            Dictionary with structure:
            {
                'postgresql': {authcfg_id: connection_object, ...},
                'ogr': {absolute_path: [uri1, uri2, ...], ...},
                'spatialite': {absolute_path: [uri1, uri2, ...], ...}
            }
        """
        return self.project_datasources
    
    def set_project_datasources(self, datasources: Dict[str, Dict]):
        """
        Set project datasources dictionary.
        
        Args:
            datasources: Dictionary with datasource structure
        """
        self.project_datasources = datasources
        logger.debug(f"Updated project_datasources: {len(datasources)} provider types")
    
    def clear_project_datasources(self):
        """
        Clear all project datasources.
        
        Useful when closing project or resetting state.
        """
        self.project_datasources = {}
        logger.info("Cleared all project datasources")
