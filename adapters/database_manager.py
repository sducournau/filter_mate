# -*- coding: utf-8 -*-
"""
Database Manager for FilterMate v3.0

Manages Spatialite database operations including initialization, schema migration,
and project configuration storage.

Extracted from filter_mate_app.py as part of MIG-024 (God Class reduction).

Author: FilterMate Team
Date: January 2026
"""
import os
import json
import uuid
import logging
from typing import Optional, Dict, Any, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsExpressionContextUtils,
    QgsProject
)

from ..infrastructure.utils.task_utils import sqlite_connect
from ..infrastructure.feedback import show_error

logger = logging.getLogger('FilterMate.DatabaseManager')


class DatabaseManager:
    """
    Manages FilterMate's Spatialite database.
    
    Responsibilities:
    - Database file creation and initialization
    - Schema management and migrations
    - Project configuration storage
    - Connection management
    
    This class centralizes all Spatialite database operations that were
    previously scattered in FilterMateApp.
    """
    
    # Database schema version for migrations
    SCHEMA_VERSION = "1.6"
    
    def __init__(self, config_directory: str, project: QgsProject):
        """
        Initialize the database manager.
        
        Args:
            config_directory: Path to FilterMate configuration directory
            project: QGIS project instance
        """
        self._config_directory = config_directory
        self._project = project
        self._db_name = 'filterMate_db.sqlite'
        self._db_file_path = os.path.normpath(
            os.path.join(config_directory, self._db_name)
        )
        self._project_uuid: Optional[str] = None
    
    @property
    def db_file_path(self) -> str:
        """Get the database file path."""
        return self._db_file_path
    
    @property
    def project_uuid(self) -> Optional[str]:
        """Get the current project UUID."""
        return self._project_uuid
    
    @project_uuid.setter
    def project_uuid(self, value: str) -> None:
        """Set the project UUID."""
        self._project_uuid = value
    
    def _clean_for_json(self, obj: Any) -> Any:
        """
        Recursively clean an object for JSON serialization.
        
        Removes non-serializable objects like database connections.
        
        Args:
            obj: Object to clean
            
        Returns:
            JSON-serializable version of the object
        """
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            cleaned = {}
            for key, value in obj.items():
                # Skip connection objects (psycopg2, sqlite3, etc.)
                if hasattr(value, 'cursor') and callable(getattr(value, 'cursor', None)):
                    cleaned[key] = None  # Replace connection with None
                else:
                    cleaned[key] = self._clean_for_json(value)
            return cleaned
        elif isinstance(obj, (list, tuple)):
            return [self._clean_for_json(item) for item in obj]
        else:
            # Try to convert to string for unknown types
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return None
    
    def get_connection(self):
        """
        Get a SQLite connection with proper error handling.
        
        Note: Uses sqlite_connect (not spatialite_connect) because
        the FilterMate configuration database doesn't need spatial functions.
        
        Returns:
            Connection object or None if connection fails
        """
        if not os.path.exists(self._db_file_path):
            logger.error(f"Database file does not exist: {self._db_file_path}")
            show_error(f"Database file does not exist: {self._db_file_path}")
            return None
        
        try:
            conn = sqlite_connect(self._db_file_path)
            return conn
        except Exception as error:
            error_msg = f"Failed to connect to database {self._db_file_path}: {error}"
            logger.error(error_msg)
            show_error(error_msg)
            return None
    
    def _ensure_db_directory(self) -> bool:
        """
        Ensure database directory exists, create if missing.
        
        Returns:
            bool: True if directory exists or was created, False on error
        """
        db_dir = os.path.dirname(self._db_file_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
                return True
            except OSError as error:
                error_msg = f"Could not create database directory {db_dir}: {error}"
                logger.error(error_msg)
                show_error(error_msg)
                return False
        return True
    
    def _create_db_file(self, crs: QgsCoordinateReferenceSystem) -> bool:
        """
        Create SQLite database file if it doesn't exist.
        
        Note: Uses standard SQLite (not Spatialite) because the FilterMate
        configuration database doesn't need spatial functions.
        
        Args:
            crs: QgsCoordinateReferenceSystem for database creation
            
        Returns:
            bool: True if file exists or was created, False on error
        """
        if os.path.exists(self._db_file_path):
            return True
        
        memory_uri = (
            'NoGeometry?field=plugin_name:string(255,0)'
            '&field=_created_at:date(0,0)'
            '&field=_updated_at:date(0,0)'
            '&field=_version:string(255,0)'
        )
        layer_name = 'filterMate_db'
        layer = QgsVectorLayer(memory_uri, layer_name, "memory")
        
        try:
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "SQLite"
            save_options.fileEncoding = "utf-8"
            # Don't require Spatialite - use standard SQLite
            save_options.datasourceOptions = ["SQLITE_MAX_LENGTH=100000000"]
            
            writer = QgsVectorFileWriter.create(
                self._db_file_path,
                layer.fields(),
                layer.wkbType(),
                crs,
                QgsCoordinateTransformContext(),
                save_options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                logger.error(f"Error creating database file: {writer.errorMessage()}")
                return False
            
            del writer  # Ensure file is closed
            return True
        except Exception as error:
            error_msg = f"Failed to create database file {self._db_file_path}: {error}"
            logger.error(error_msg)
            show_error(error_msg)
            return False
    
    def _initialize_schema(self, cursor, project_settings: Dict[str, Any]) -> None:
        """
        Initialize database schema with fresh tables and project entry.
        
        Args:
            cursor: Database cursor
            project_settings: Project configuration dictionary
        """
        project_file_name = os.path.basename(self._project.absoluteFilePath())
        project_file_path = self._project.absolutePath()
        
        cursor.execute("""
            INSERT INTO filterMate_db VALUES(
                1, 'FilterMate', datetime(), datetime(), '{version}'
            );
        """.format(version=self.SCHEMA_VERSION))
        
        cursor.execute("""
            CREATE TABLE fm_projects (
                project_id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                _created_at DATETIME NOT NULL,
                _updated_at DATETIME NOT NULL,
                project_name VARYING CHARACTER(255) NOT NULL,
                project_path VARYING CHARACTER(255) NOT NULL,
                project_settings TEXT NOT NULL
            );
        """)
        
        cursor.execute("""
            CREATE TABLE fm_subset_history (
                id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                _updated_at DATETIME NOT NULL,
                fk_project VARYING CHARACTER(255) NOT NULL,
                layer_id VARYING CHARACTER(255) NOT NULL,
                layer_source_id VARYING CHARACTER(255) NOT NULL,
                seq_order INTEGER NOT NULL,
                subset_string TEXT NOT NULL,
                FOREIGN KEY (fk_project) REFERENCES fm_projects(project_id)
            );
        """)
        
        cursor.execute("""
            CREATE TABLE fm_project_layers_properties (
                id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                _updated_at DATETIME NOT NULL,
                fk_project VARYING CHARACTER(255) NOT NULL,
                layer_id VARYING CHARACTER(255) NOT NULL,
                meta_type VARYING CHARACTER(255) NOT NULL,
                meta_key VARYING CHARACTER(255) NOT NULL,
                meta_value TEXT NOT NULL,
                FOREIGN KEY (fk_project) REFERENCES fm_projects(project_id),
                CONSTRAINT property_unicity
                UNIQUE(fk_project, layer_id, meta_type, meta_key) ON CONFLICT REPLACE
            );
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_layer_properties_lookup 
            ON fm_project_layers_properties(fk_project, layer_id, meta_type);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_layer_properties_by_project 
            ON fm_project_layers_properties(fk_project);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subset_history_by_project 
            ON fm_subset_history(fk_project, layer_id);
        """)
        
        logger.info("✓ Created database indexes for optimized queries")
        
        self._project_uuid = str(uuid.uuid4())
        
        # FIX 2026-01-19: Use parameterized query
        cursor.execute("""
            INSERT INTO fm_projects VALUES(
                ?, datetime(), datetime(), 
                ?, ?, ?
            );
        """, (
            self._project_uuid,
            project_file_name,
            project_file_path,
            json.dumps(project_settings)
        ))
        
        # Set the project UUID for newly initialized database
        QgsExpressionContextUtils.setProjectVariable(
            self._project, 'filterMate_db_project_uuid', self._project_uuid
        )
    
    def _migrate_schema_if_needed(self, cursor) -> bool:
        """
        Migrate database schema if needed (add fm_subset_history table for v1.6+).
        
        Args:
            cursor: Database cursor
            
        Returns:
            bool: True if subset history table exists
        """
        cursor.execute("""
            SELECT count(*) FROM sqlite_master 
            WHERE type='table' AND name='fm_subset_history';
        """)
        subset_history_exists = cursor.fetchone()[0] > 0
        
        if not subset_history_exists:
            logger.info("Migrating database: creating fm_subset_history table")
            cursor.execute("""
                CREATE TABLE fm_subset_history (
                    id VARYING CHARACTER(255) NOT NULL PRIMARY KEY,
                    _updated_at DATETIME NOT NULL,
                    fk_project VARYING CHARACTER(255) NOT NULL,
                    layer_id VARYING CHARACTER(255) NOT NULL,
                    layer_source_id VARYING CHARACTER(255) NOT NULL,
                    seq_order INTEGER NOT NULL,
                    subset_string TEXT NOT NULL,
                    FOREIGN KEY (fk_project) REFERENCES fm_projects(project_id)
                );
            """)
            logger.info("Migration completed: fm_subset_history table created")
        
        return subset_history_exists
    
    def _load_or_create_project(
        self, 
        cursor, 
        project_settings: Dict[str, Any],
        config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Load existing project from database or create new entry.
        
        Args:
            cursor: Database cursor
            project_settings: Project configuration dictionary
            config_data: Main configuration dictionary to update
            
        Returns:
            Updated config_data with CURRENT_PROJECT loaded
        """
        project_file_name = os.path.basename(self._project.absoluteFilePath())
        project_file_path = self._project.absolutePath()
        
        # FIX 2026-01-19: Check if project is actually saved (has a name)
        # Unsaved projects have empty name/path which causes orphan favorites
        is_unsaved_project = not project_file_name or project_file_name == '' or not project_file_path
        
        if is_unsaved_project:
            logger.warning("⚠️ Project is not saved yet (no filename). Favorites may become orphaned.")
            logger.warning("   Save the project to ensure favorites persist correctly.")
        
        # FIX 2026-01-19: Use parameterized queries to avoid SQL injection
        # and handle special characters (apostrophes, etc.) in paths
        cursor.execute("""
            SELECT * FROM fm_projects 
            WHERE project_name = ? AND project_path = ? 
            LIMIT 1;
        """, (project_file_name, project_file_path))
        
        results = cursor.fetchall()
        
        logger.debug(f"Looking for project: name='{project_file_name}', path='{project_file_path}'")
        logger.debug(f"Found {len(results)} matching project(s) in database")
        
        if len(results) == 1:
            result = results[0]
            project_settings_str = result[-1].replace("''", "'")
            self._project_uuid = result[0]
            logger.info(f"✓ Found existing project in database: UUID={self._project_uuid[:8]}...")
            config_data["CURRENT_PROJECT"] = json.loads(project_settings_str)
            QgsExpressionContextUtils.setProjectVariable(
                self._project, 'filterMate_db_project_uuid', self._project_uuid
            )
        else:
            # FIX 2026-01-19: For unsaved projects, check if there's already an orphan project
            # we can reuse instead of creating a new one
            if is_unsaved_project:
                cursor.execute("""
                    SELECT project_id FROM fm_projects 
                    WHERE (project_name = '' OR project_name IS NULL)
                      AND (project_path = '' OR project_path IS NULL)
                    ORDER BY _created_at DESC
                    LIMIT 1;
                """)
                orphan = cursor.fetchone()
                if orphan:
                    self._project_uuid = orphan[0]
                    logger.info(f"✓ Reusing existing orphan project: UUID={self._project_uuid[:8]}...")
                    QgsExpressionContextUtils.setProjectVariable(
                        self._project, 'filterMate_db_project_uuid', self._project_uuid
                    )
                    return config_data
            
            self._project_uuid = str(uuid.uuid4())
            logger.info(f"Creating new project entry in database: UUID={self._project_uuid[:8]}...")
            # FIX 2026-01-19: Use parameterized query for INSERT as well
            cursor.execute("""
                INSERT INTO fm_projects VALUES(
                    ?, datetime(), datetime(), 
                    ?, ?, ?
                );
            """, (
                self._project_uuid,
                project_file_name,
                project_file_path,
                json.dumps(project_settings)
            ))
            QgsExpressionContextUtils.setProjectVariable(
                self._project, 'filterMate_db_project_uuid', self._project_uuid
            )
        
        return config_data
    
    def initialize_database(
        self,
        config_data: Dict[str, Any],
        fresh_reload: bool = False,
        config_json_path: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Initialize FilterMate Spatialite database with required schema.
        
        Creates database file and tables if they don't exist. Sets up schema for
        storing project configurations, layer properties, and datasource information.
        
        Args:
            config_data: Main configuration dictionary
            fresh_reload: If True, delete and recreate database
            config_json_path: Path to config.json for updating fresh_reload flag
            
        Returns:
            Tuple of (success, updated_config_data)
        """
        if self._project is None:
            return False, config_data
        
        # Ensure database directory exists
        if not self._ensure_db_directory():
            return False, config_data
        
        logger.debug(f"Database file path: {self._db_file_path}")
        
        # Handle fresh reload
        if fresh_reload:
            try:
                os.remove(self._db_file_path)
                config_data["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] = False
                if config_json_path:
                    with open(config_json_path, 'w') as outfile:
                        outfile.write(json.dumps(config_data, indent=4))
            except OSError as error:
                logger.error(f"Failed to remove database file: {error}")
        
        project_settings = config_data.get("CURRENT_PROJECT", {})
        
        # Create database file if missing
        crs = QgsCoordinateReferenceSystem("epsg:4326")
        if not self._create_db_file(crs):
            return False, config_data
        
        try:
            conn = self.get_connection()
            if conn is None:
                error_msg = "Cannot initialize FilterMate database: connection failed"
                logger.error(error_msg)
                show_error(error_msg)
                return False, config_data
        except Exception as e:
            error_msg = f"Critical error connecting to database: {str(e)}"
            logger.error(error_msg)
            show_error(error_msg)
            return False, config_data
        
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys = ON;")
                
                # Check if database is already initialized
                cur.execute("""
                    SELECT count(*) FROM sqlite_master 
                    WHERE type='table' AND name='fm_projects';
                """)
                tables_exist = cur.fetchone()[0] > 0
                
                if not tables_exist:
                    # Initialize fresh schema
                    self._initialize_schema(cur, project_settings)
                    conn.commit()
                else:
                    # Database already initialized - migrate if needed
                    self._migrate_schema_if_needed(cur)
                    
                    # Load or create project entry
                    config_data = self._load_or_create_project(
                        cur, project_settings, config_data
                    )
                    conn.commit()
            
            return True, config_data
            
        except Exception as e:
            error_msg = f"Error during database initialization: {str(e)}"
            logger.error(error_msg)
            show_error(error_msg)
            return False, config_data
        finally:
            if conn:
                try:
                    cur.close()
                    conn.close()
                except Exception as e:
                    logger.debug(f"Error closing database connection: {e}")
    
    def save_project_variables(
        self,
        config_data: Dict[str, Any],
        project_name: Optional[str] = None
    ) -> bool:
        """
        Save project variables to database.
        
        Args:
            config_data: Configuration data to save
            project_name: Optional new project name
            
        Returns:
            bool: True if save successful
        """
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if conn is None:
                return False
            cur = conn.cursor()
            
            project_file_name = project_name or os.path.basename(
                self._project.absoluteFilePath()
            )
            project_file_path = self._project.absolutePath()
            project_settings = config_data.get("CURRENT_PROJECT", {})
            
            # Clean non-serializable objects (e.g., psycopg2 connections) before JSON serialization
            project_settings_clean = self._clean_for_json(project_settings)
            
            cur.execute(
                """UPDATE fm_projects SET 
                   _updated_at = datetime(),
                   project_name = ?,
                   project_path = ?,
                   project_settings = ?
                   WHERE project_id = ?""",
                (project_file_name, project_file_path,
                 json.dumps(project_settings_clean), str(self._project_uuid))
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save project variables: {e}")
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def save_layer_property(
        self,
        layer_id: str,
        key_group: str,
        key: str,
        value: Any
    ) -> bool:
        """
        Save a single layer property to the database.
        
        Args:
            layer_id: Layer ID
            key_group: Property group (e.g., 'filtering', 'exploring')
            key: Property key
            value: Property value
            
        Returns:
            bool: True if save successful
        """
        if not self._project_uuid:
            logger.warning("Cannot save layer property: no project UUID")
            return False
        
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if conn is None:
                return False
            cur = conn.cursor()
            
            property_id = str(uuid.uuid4())
            value_json = json.dumps(value).replace("'", "''") if not isinstance(value, str) else value
            
            cur.execute("""
                INSERT OR REPLACE INTO fm_project_layers_properties 
                (id, _updated_at, fk_project, layer_id, meta_type, meta_key, meta_value)
                VALUES (?, datetime(), ?, ?, ?, ?, ?)
            """, (property_id, str(self._project_uuid), layer_id, key_group, key, value_json))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save layer property: {e}")
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
