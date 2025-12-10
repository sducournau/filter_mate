from qgis.core import QgsApplication, QgsProject, QgsUserProfileManager, QgsUserProfile, QgsMessageLog, Qgis
import os, sys
import json
import shutil
from datetime import datetime


ENV_VARS = {}


def get_config_path():
    """
    Get the full path to config.json file.
    Uses PLUGIN_CONFIG_DIRECTORY if available, otherwise falls back to plugin directory.
    
    Returns:
        str: Full path to config.json
    """
    if "PLUGIN_CONFIG_DIRECTORY" in ENV_VARS:
        return os.path.join(ENV_VARS["PLUGIN_CONFIG_DIRECTORY"], 'config.json')
    else:
        dir_config = os.path.normpath(os.path.dirname(__file__))
        return os.path.join(dir_config, 'config.json')

def merge(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass # same leaf value

        else:
            a[key] = b[key]
    return a


def load_default_config():
    """
    Load the default configuration from config.default.json.
    
    Returns:
        dict: Default configuration data
    """
    # Default config is in the plugin directory
    dir_config = os.path.normpath(os.path.dirname(__file__))
    default_config_path = os.path.join(dir_config, 'config.default.json')
    
    try:
        with open(default_config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error loading default config: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return None


def reset_config_to_default(backup=True, preserve_app_settings=True):
    """
    Reset config.json to default values from config.default.json.
    
    Args:
        backup (bool): If True, create a backup of current config before resetting
        preserve_app_settings (bool): If True, preserve APP_SQLITE_PATH and other app settings
    
    Returns:
        bool: True if successful, False otherwise
    """
    config_path = get_config_path()
    
    # Default config is always in plugin directory
    dir_config = os.path.normpath(os.path.dirname(__file__))
    default_config_path = os.path.join(dir_config, 'config.default.json')
    
    try:
        # Load current config to preserve some settings if needed
        current_config = None
        if preserve_app_settings and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                current_config = json.load(f)
        
        # Create backup if requested
        if backup and os.path.exists(config_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(dir_config, f'config.backup.{timestamp}.json')
            shutil.copy2(config_path, backup_path)
            QgsMessageLog.logMessage(
                f"Config backup created: {backup_path}",
                "FilterMate",
                Qgis.Info
            )
        
        # Load default config
        with open(default_config_path, 'r') as f:
            new_config = json.load(f)
        
        # Preserve specific app settings if requested
        if preserve_app_settings and current_config:
            if "APP" in current_config and "OPTIONS" in current_config["APP"]:
                if "APP_SQLITE_PATH" in current_config["APP"]["OPTIONS"]:
                    new_config["APP"]["OPTIONS"]["APP_SQLITE_PATH"] = current_config["APP"]["OPTIONS"]["APP_SQLITE_PATH"]
        
        # Write new config
        with open(config_path, 'w') as f:
            f.write(json.dumps(new_config, indent=4))
        
        QgsMessageLog.logMessage(
            "Configuration reset to default values",
            "FilterMate",
            Qgis.Success
        )
        
        return True
        
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error resetting config to default: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return False


def reload_config():
    """
    Reload configuration from config.json file and update ENV_VARS.
    
    Returns:
        dict: Reloaded configuration data, or None if failed
    """
    config_path = get_config_path()
    
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Update global ENV_VARS if it exists
        if "CONFIG_DATA" in ENV_VARS:
            ENV_VARS["CONFIG_DATA"] = config_data
        
        QgsMessageLog.logMessage(
            "Configuration reloaded successfully",
            "FilterMate",
            Qgis.Info
        )
        
        return config_data
        
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error reloading config: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return None


def save_config(config_data):
    """
    Save configuration data to config.json file.
    
    Args:
        config_data (dict): Configuration data to save
    
    Returns:
        bool: True if successful, False otherwise
    """
    config_path = get_config_path()
    
    try:
        with open(config_path, 'w') as f:
            f.write(json.dumps(config_data, indent=4))
        
        QgsMessageLog.logMessage(
            "Configuration saved successfully",
            "FilterMate",
            Qgis.Info
        )
        
        return True
        
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error saving config: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return False


def migrate_config_to_sqlite_dir():
    """
    Migrate config.json from plugin directory to APP_SQLITE_PATH directory.
    This is a one-time migration for users updating from older versions.
    
    Returns:
        bool: True if migration was performed or not needed, False on error
    """
    dir_config = os.path.normpath(os.path.dirname(__file__))
    old_config_path = os.path.join(dir_config, 'config.json')
    
    # First read the config to get APP_SQLITE_PATH
    if not os.path.exists(old_config_path):
        return True  # Nothing to migrate
    
    try:
        with open(old_config_path, 'r') as f:
            config_data = json.load(f)
        
        # Get the target directory
        app_sqlite_path = config_data.get("APP", {}).get("OPTIONS", {}).get("APP_SQLITE_PATH", "")
        
        if not app_sqlite_path:
            # Will be set later in init_env_vars
            return True
        
        app_sqlite_path = os.path.normpath(app_sqlite_path)
        new_config_path = os.path.join(app_sqlite_path, 'config.json')
        
        # If config already exists in new location, don't migrate
        if os.path.exists(new_config_path):
            QgsMessageLog.logMessage(
                f"Config already exists in {app_sqlite_path}, skipping migration",
                "FilterMate",
                Qgis.Info
            )
            return True
        
        # Create target directory if needed
        if not os.path.exists(app_sqlite_path):
            os.makedirs(app_sqlite_path, exist_ok=True)
        
        # Copy config to new location
        shutil.copy2(old_config_path, new_config_path)
        
        QgsMessageLog.logMessage(
            f"Config migrated from {dir_config} to {app_sqlite_path}",
            "FilterMate",
            Qgis.Success
        )
        
        # Keep old config as backup
        backup_path = os.path.join(dir_config, 'config.json.migrated')
        shutil.move(old_config_path, backup_path)
        
        return True
        
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error migrating config: {e}",
            "FilterMate",
            Qgis.Warning
        )
        return False


def init_env_vars():
    PROJECT = QgsProject.instance()

    PLATFORM = sys.platform


    DIR_CONFIG = os.path.normpath(os.path.dirname(__file__))
    PATH_ABSOLUTE_PROJECT = os.path.normpath(PROJECT.readPath("./"))
    if PATH_ABSOLUTE_PROJECT =='./':
        if PLATFORM.startswith('win'):
            PATH_ABSOLUTE_PROJECT =  os.path.normpath(os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop'))
        else:
            PATH_ABSOLUTE_PROJECT =  os.path.normpath(os.environ['HOME'])

    CONFIG_DATA = None

    # First, try to load config from plugin directory to get APP_SQLITE_PATH
    old_config_path = os.path.join(DIR_CONFIG, 'config.json')
    default_config_path = os.path.join(DIR_CONFIG, 'config.default.json')
    
    # If no config exists yet, use default
    if not os.path.exists(old_config_path):
        if os.path.exists(default_config_path):
            with open(default_config_path, 'r') as f:
                CONFIG_DATA = json.load(f)
        else:
            QgsMessageLog.logMessage(
                "No config.json or config.default.json found",
                "FilterMate",
                Qgis.Critical
            )
            CONFIG_DATA = {"APP": {"OPTIONS": {"APP_SQLITE_PATH": ""}}}
    else:
        with open(old_config_path, 'r') as f:
            CONFIG_DATA = json.load(f)

    QGIS_SETTINGS_PATH = QgsApplication.qgisSettingsDirPath()
    # Remove trailing separator if present
    QGIS_SETTINGS_PATH = QGIS_SETTINGS_PATH.rstrip(os.sep).rstrip('/')

    # Determine the plugin config directory
    if CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"] != '':
        configured_path = os.path.normpath(CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"])
        
        # Validate that parent directories exist and are accessible
        parent_dir = os.path.dirname(configured_path)
        path_is_valid = False
        
        if parent_dir and os.path.exists(parent_dir):
            # Check if parent directory is accessible
            try:
                if os.access(parent_dir, os.W_OK):
                    path_is_valid = True
                else:
                    QgsMessageLog.logMessage(
                        f"Configured path parent directory is not writable: {parent_dir}. Falling back to current profile.",
                        "FilterMate",
                        Qgis.Warning
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Cannot access configured path: {configured_path}. Error: {e}. Falling back to current profile.",
                    "FilterMate",
                    Qgis.Warning
                )
        else:
            QgsMessageLog.logMessage(
                f"Configured path parent directory does not exist: {parent_dir}. Falling back to current profile.",
                "FilterMate",
                Qgis.Warning
            )
        
        if path_is_valid:
            PLUGIN_CONFIG_DIRECTORY = configured_path
        else:
            # Fall back to current profile
            PLUGIN_CONFIG_DIRECTORY = os.path.normpath(os.path.join(QGIS_SETTINGS_PATH, 'FilterMate'))
            CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"] = PLUGIN_CONFIG_DIRECTORY
    else:
        # Use os.path.join for proper cross-platform path construction
        PLUGIN_CONFIG_DIRECTORY = os.path.normpath(os.path.join(QGIS_SETTINGS_PATH, 'FilterMate'))
        CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"] = PLUGIN_CONFIG_DIRECTORY

    global ENV_VARS
    ENV_VARS["PROJECT"] = PROJECT
    ENV_VARS["PLATFORM"] = PLATFORM
    ENV_VARS["DIR_CONFIG"] = DIR_CONFIG
    ENV_VARS["PATH_ABSOLUTE_PROJECT"] = PATH_ABSOLUTE_PROJECT
    ENV_VARS["CONFIG_DATA"] = CONFIG_DATA
    ENV_VARS["QGIS_SETTINGS_PATH"] = QGIS_SETTINGS_PATH
    ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] = PLUGIN_CONFIG_DIRECTORY

    # Create the plugin config directory if it doesn't exist
    if not os.path.isdir(PLUGIN_CONFIG_DIRECTORY):
        try:
            os.makedirs(PLUGIN_CONFIG_DIRECTORY, exist_ok=True)
            QgsMessageLog.logMessage(
                f"Created plugin config directory: {PLUGIN_CONFIG_DIRECTORY}",
                "FilterMate",
                Qgis.Info
            )
        except OSError as error:
            QgsMessageLog.logMessage(
                f"Could not create config directory {PLUGIN_CONFIG_DIRECTORY}: {error}",
                "FilterMate",
                Qgis.Critical
            )
    
    # Now migrate config.json to the SQLite directory if needed
    migrate_config_to_sqlite_dir()
    
    # Load config from new location (SQLite directory)
    new_config_path = os.path.join(PLUGIN_CONFIG_DIRECTORY, 'config.json')
    if os.path.exists(new_config_path):
        try:
            with open(new_config_path, 'r') as f:
                CONFIG_DATA = json.load(f)
            ENV_VARS["CONFIG_DATA"] = CONFIG_DATA
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading config from {new_config_path}: {e}",
                "FilterMate",
                Qgis.Warning
            )
    else:
        # Create initial config in new location
        try:
            with open(new_config_path, 'w') as f:
                f.write(json.dumps(CONFIG_DATA, indent=4))
            QgsMessageLog.logMessage(
                f"Created initial config at {new_config_path}",
                "FilterMate",
                Qgis.Info
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Could not create config at {new_config_path}: {e}",
                "FilterMate",
                Qgis.Warning
            )


