"""
Variables Persistence Manager
=============================

Extracted from filter_mate_app.py (MIG-024) for God Class reduction.

Handles persistence of layer variables and project settings to:
1. QGIS layer variables (runtime access)
2. Spatialite database (persistent storage)

Author: FilterMate Team
Version: 2.8.6
"""

import json
import uuid
from typing import Optional, List, Tuple, Any, Dict, Callable

try:
    from qgis.core import (
        QgsProject,
        QgsExpressionContextUtils,
        QgsVectorLayer
    )
    import sip
except ImportError:
    # Mock for testing
    sip = None

try:
    from ..infrastructure.logging import get_logger
except ImportError:
    # Fallback for testing
    import logging

    def get_logger(name):
        return logging.getLogger(name)

try:
    from ..infrastructure.utils import (
        is_layer_valid as is_valid_layer,
        is_qgis_alive,
        safe_set_layer_variable
    )
except ImportError:
    # Mock for testing without QGIS
    def is_valid_layer(layer):
        return layer is not None

    def is_qgis_alive():
        return True

    def safe_set_layer_variable(layer_id, name, value):
        return True

logger = get_logger(__name__)


class VariablesPersistenceManager:
    """
    Manages persistence of FilterMate layer variables and project settings.

    Extracted from FilterMateApp to reduce God Class complexity.
    Uses Spatialite for persistence and QGIS variables for runtime access.

    Architecture:
        - Uses dependency injection for callbacks
        - No direct access to FilterMateApp internals
        - Thread-safe database operations with context managers
    """

    def __init__(
        self,
        get_spatialite_connection: Callable,
        get_project_uuid: Callable[[], str],
        get_project_layers: Callable[[], Dict],
        return_typped_value: Callable[[Any, str], Tuple[Any, type]],
        cancel_layer_tasks: Optional[Callable[[str], None]] = None,
        is_layer_change_in_progress: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize VariablesPersistenceManager.

        Args:
            get_spatialite_connection: Callback to get Spatialite connection
            get_project_uuid: Callback to get current project UUID
            get_project_layers: Callback to get PROJECT_LAYERS dictionary
            return_typped_value: Callback to convert values to typed format
            cancel_layer_tasks: Optional callback to cancel tasks before save
            is_layer_change_in_progress: Optional callback to check layer update status
        """
        self._get_connection = get_spatialite_connection
        self._get_project_uuid = get_project_uuid
        self._get_project_layers = get_project_layers
        self._return_typped_value = return_typped_value
        self._cancel_layer_tasks = cancel_layer_tasks
        self._is_layer_change_in_progress = is_layer_change_in_progress

    def save_single_property(
        self,
        layer: 'QgsVectorLayer',
        cursor,
        key_group: str,
        key: str,
        value: Any
    ) -> bool:
        """
        Save a single property to QGIS variable and Spatialite database.

        CRASH FIX (v2.3.18): Multiple safety checks for layer validity.

        Args:
            layer: Layer to save property for
            cursor: SQLite cursor for database operations
            key_group: Property group ('infos', 'exploring', 'filtering')
            key: Property key name
            value: Property value to save

        Returns:
            bool: True if saved successfully, False otherwise
        """
        # CRASH FIX: Check if QGIS is still alive
        if not is_qgis_alive():
            logger.debug(f"save_single_property: QGIS shutting down, skipping {key_group}.{key}")
            return False

        # Check if layer change is in progress
        skip_qgis_variable = False
        if self._is_layer_change_in_progress and self._is_layer_change_in_progress():
            logger.debug(f"save_single_property: layer change in progress, deferring {key_group}.{key}")
            skip_qgis_variable = True

        # Validate layer
        if not is_valid_layer(layer):
            logger.debug(f"save_single_property: layer invalid, skipping {key_group}.{key}")
            return False

        # Get layer ID safely
        try:
            layer_id = layer.id()
            if not layer_id:
                return False
        except (RuntimeError, OSError, SystemError):
            logger.debug(f"save_single_property: layer.id() failed for {key_group}.{key}")
            return False

        # Re-fetch fresh layer reference
        fresh_layer = QgsProject.instance().mapLayer(layer_id)
        if fresh_layer is None or not is_valid_layer(fresh_layer):
            logger.debug(f"save_single_property: layer {layer_id} not in project, skipping {key_group}.{key}")
            return False

        # Convert value to typed format
        value_typped, type_returned = self._return_typped_value(value, 'save')
        if type_returned in (list, dict):
            value_typped = json.dumps(value_typped)

        # Save to QGIS variable if safe
        project_layer = QgsProject.instance().mapLayer(layer_id)
        if project_layer is not None and not skip_qgis_variable:
            if sip is not None and not sip.isdeleted(project_layer):
                # Cancel running tasks to prevent race conditions
                if self._cancel_layer_tasks:
                    self._cancel_layer_tasks(layer_id)

                # Use safe wrapper for variable setting
                variable_name = f"{key_group}_{key}"
                if not safe_set_layer_variable(layer_id, variable_name, value_typped):
                    logger.debug(f"save_single_property: safe_set_layer_variable failed for {layer_id}.{variable_name}")

        # Always save to database (even if QGIS variable failed)
        project_uuid = self._get_project_uuid()
        cursor.execute(
            """INSERT INTO fm_project_layers_properties
               VALUES(?, datetime(), ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), str(project_uuid), layer_id,
             key_group, key, str(value_typped))
        )

        return True

    def save_variables_from_layer(
        self,
        layer: 'QgsVectorLayer',
        layer_properties: Optional[List[Tuple]] = None
    ) -> bool:
        """
        Save layer filtering properties to QGIS variables and Spatialite database.

        Stores layer properties in two locations for redundancy:
        1. QGIS layer variables (runtime access)
        2. Spatialite database (persistence across sessions)

        Args:
            layer: Layer to save properties for
            layer_properties: List of tuples (key_group, key, value, type)
                If None or empty, saves all properties

        Returns:
            bool: True if saved successfully, False otherwise
        """
        if layer_properties is None:
            layer_properties = []

        layer_all_properties_flag = len(layer_properties) == 0

        # Validate layer
        if not is_valid_layer(layer):
            logger.debug("save_variables_from_layer: layer invalid, skipping")
            return False

        # Get layer info safely
        try:
            layer_name = layer.name()
            layer_id = layer.id()
            if layer_all_properties_flag:
                logger.debug(f"💾 Saving ALL properties for '{layer_name}' ({layer_id})")
            else:
                logger.debug(f"💾 Saving {len(layer_properties)} properties for '{layer_name}' ({layer_id})")
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"save_variables_from_layer: layer access failed: {e}")
            return False

        # Check if layer is in PROJECT_LAYERS
        project_layers = self._get_project_layers()
        if layer_id not in project_layers.keys():
            logger.warning(f"Layer {layer_name} not in PROJECT_LAYERS, cannot save properties")
            return False

        # Get database connection
        conn = self._get_connection()
        if conn is None:
            return False

        saved_count = 0
        try:
            with conn:
                cur = conn.cursor()

                if layer_all_properties_flag:
                    # Save all properties from all groups
                    for key_group in ("infos", "exploring", "filtering"):
                        if key_group in project_layers[layer_id]:
                            for key, value in project_layers[layer_id][key_group].items():
                                if self.save_single_property(layer, cur, key_group, key, value):
                                    saved_count += 1
                else:
                    # Save specific properties
                    for layer_property in layer_properties:
                        key_group, key = layer_property[0], layer_property[1]
                        if key_group not in ("infos", "exploring", "filtering"):
                            continue

                        if (key_group in project_layers[layer_id] and
                                key in project_layers[layer_id][key_group]):
                            value = project_layers[layer_id][key_group][key]
                            if self.save_single_property(layer, cur, key_group, key, value):
                                saved_count += 1
        finally:
            pass  # Context manager handles connection cleanup

        logger.debug(f"💾 Saved {saved_count} properties for layer {layer_id}")
        return saved_count > 0

    def remove_variables_from_layer(
        self,
        layer: 'QgsVectorLayer',
        layer_properties: Optional[List[Tuple]] = None
    ) -> bool:
        """
        Remove layer filtering properties from QGIS variables and Spatialite database.

        Clears stored properties from both runtime variables and persistent storage.
        Used when resetting filters or cleaning up removed layers.

        Args:
            layer: Layer to remove properties from
            layer_properties: List of tuples (key_group, key)
                If None or empty, removes ALL filterMate variables for the layer

        Returns:
            bool: True if removed successfully, False otherwise
        """
        if layer_properties is None:
            layer_properties = []

        layer_all_properties_flag = len(layer_properties) == 0

        # Validate layer
        if not is_valid_layer(layer):
            logger.debug("remove_variables_from_layer: layer invalid, skipping")
            return False

        # Get layer ID safely
        try:
            layer_id = layer.id()
            if not layer_id:
                return False
        except (RuntimeError, OSError, SystemError):
            logger.debug("remove_variables_from_layer: layer.id() failed")
            return False

        # Re-fetch fresh layer reference
        fresh_layer = QgsProject.instance().mapLayer(layer_id)
        if fresh_layer is None or not is_valid_layer(fresh_layer):
            logger.debug(f"remove_variables_from_layer: layer {layer_id} not in project")
            return False

        # Log operation
        try:
            layer_name = fresh_layer.name()
            if layer_all_properties_flag:
                logger.debug(f"🗑️ Removing ALL properties for '{layer_name}' ({layer_id})")
            else:
                logger.debug(f"🗑️ Removing {len(layer_properties)} properties for '{layer_name}' ({layer_id})")
        except (RuntimeError, OSError, SystemError) as e:
            logger.debug(f"remove_variables_from_layer: layer access failed: {e}")
            return False

        # Check if layer is in PROJECT_LAYERS
        project_layers = self._get_project_layers()
        if layer_id not in project_layers.keys():
            logger.warning(f"Layer {layer_id} not in PROJECT_LAYERS, cannot remove properties")
            return False

        # Get database connection
        conn = self._get_connection()
        if conn is None:
            return False

        project_uuid = self._get_project_uuid()

        try:
            with conn:
                cur = conn.cursor()

                if layer_all_properties_flag:
                    # Remove all properties for layer
                    cur.execute(
                        """DELETE FROM fm_project_layers_properties
                           WHERE fk_project = ? and layer_id = ?""",
                        (str(project_uuid), layer_id)
                    )
                    # Clear QGIS layer variables
                    if sip is not None and not sip.isdeleted(fresh_layer):
                        try:
                            QgsExpressionContextUtils.setLayerVariables(fresh_layer, {})
                        except (RuntimeError, OSError, SystemError) as e:
                            logger.warning(f"remove_variables_from_layer: setLayerVariables failed: {e}")
                else:
                    # Remove specific properties
                    for layer_property in layer_properties:
                        key_group, key = layer_property[0], layer_property[1]
                        if key_group not in ("infos", "exploring", "filtering"):
                            continue

                        if (key_group in project_layers[layer_id] and
                                key in project_layers[layer_id][key_group]):
                            cur.execute(
                                """DELETE FROM fm_project_layers_properties
                                   WHERE fk_project = ? and layer_id = ?
                                   and meta_type = ? and meta_key = ?""",
                                (str(project_uuid), layer_id, key_group, key)
                            )
        finally:
            pass  # Context manager handles connection cleanup

        return True


class ProjectSettingsSaver:
    """
    Handles saving project-level settings to database and config file.

    Separated from VariablesPersistenceManager as it deals with project
    settings rather than layer variables.
    """

    def __init__(
        self,
        get_spatialite_connection: Callable,
        get_project_uuid: Callable[[], str],
        get_config_data: Callable[[], Dict],
        config_json_path: str
    ):
        """
        Initialize ProjectSettingsSaver.

        Args:
            get_spatialite_connection: Callback to get Spatialite connection
            get_project_uuid: Callback to get current project UUID
            get_config_data: Callback to get CONFIG_DATA dictionary
            config_json_path: Path to config.json file
        """
        self._get_connection = get_spatialite_connection
        self._get_project_uuid = get_project_uuid
        self._get_config_data = get_config_data
        self._config_json_path = config_json_path

        self.project_file_name: Optional[str] = None
        self.project_file_path: Optional[str] = None
        self.favorites_manager = None

    def save_project_variables(
        self,
        name: Optional[str] = None,
        project_absolute_path: Optional[str] = None
    ) -> bool:
        """
        Save project settings to database and config file.

        Args:
            name: Project file name (optional)
            project_absolute_path: Project absolute path (optional)

        Returns:
            bool: True if saved successfully, False otherwise
        """
        config_data = self._get_config_data()
        if config_data is None:
            return False

        conn = None
        cur = None

        try:
            conn = self._get_connection()
            if conn is None:
                return False
            cur = conn.cursor()

            if name is not None:
                self.project_file_name = name
            if project_absolute_path is not None:
                self.project_file_path = project_absolute_path

            project_settings = config_data.get("CURRENT_PROJECT", {})
            project_uuid = self._get_project_uuid()

            cur.execute(
                """UPDATE fm_projects SET
                   _updated_at = datetime(),
                   project_name = ?,
                   project_path = ?,
                   project_settings = ?
                   WHERE project_id = ?""",
                (self.project_file_name, self.project_file_path,
                 json.dumps(project_settings), str(project_uuid))
            )
            conn.commit()

        except Exception as e:
            logger.error(f"save_project_variables: database error: {e}")
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        # Save to config.json
        try:
            with open(self._config_json_path, 'w') as outfile:
                outfile.write(json.dumps(config_data, indent=4))
        except Exception as e:
            logger.error(f"save_project_variables: config file error: {e}")
            return False

        # Save favorites if manager is available
        if self.favorites_manager is not None:
            try:
                self.favorites_manager.save_to_project()
                logger.debug(f"Saved {self.favorites_manager.count} favorites to project")
            except Exception as e:
                logger.warning(f"save_project_variables: favorites save failed: {e}")

        return True
