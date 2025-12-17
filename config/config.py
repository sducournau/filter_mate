from qgis.core import QgsApplication, QgsProject, QgsUserProfileManager, QgsUserProfile, QgsMessageLog, Qgis
import os, sys
import json


ENV_VARS = {}

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


def init_env_vars():
    """
    Initialize environment variables and configuration paths.
    
    Now reads config.json from PLUGIN_CONFIG_DIRECTORY (same as SQLite database)
    instead of the plugin directory. If config.json doesn't exist there,
    copies config.default.json from the plugin directory.
    
    Automatically detects and migrates/resets obsolete configurations.
    """
    from qgis.core import QgsMessageLog
    
    PROJECT = QgsProject.instance()
    PLATFORM = sys.platform

    # Plugin directory (where config.default.json is located)
    DIR_CONFIG = os.path.normpath(os.path.dirname(__file__))
    PATH_ABSOLUTE_PROJECT = os.path.normpath(PROJECT.readPath("./"))
    if PATH_ABSOLUTE_PROJECT =='./':
        if PLATFORM.startswith('win'):
            PATH_ABSOLUTE_PROJECT =  os.path.normpath(os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop'))
        else:
            PATH_ABSOLUTE_PROJECT =  os.path.normpath(os.environ['HOME'])

    QGIS_SETTINGS_PATH = QgsApplication.qgisSettingsDirPath()
    # Remove trailing separator if present
    QGIS_SETTINGS_PATH = QGIS_SETTINGS_PATH.rstrip(os.sep).rstrip('/')
    
    # Start with default PLUGIN_CONFIG_DIRECTORY
    PLUGIN_CONFIG_DIRECTORY = os.path.normpath(os.path.join(QGIS_SETTINGS_PATH, 'FilterMate'))
    
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
    
    # Path to config.json in PLUGIN_CONFIG_DIRECTORY
    config_json_path = os.path.join(PLUGIN_CONFIG_DIRECTORY, 'config.json')
    config_default_path = os.path.join(DIR_CONFIG, 'config.default.json')
    
    # If config.json doesn't exist in PLUGIN_CONFIG_DIRECTORY, copy default first
    if not os.path.exists(config_json_path):
        try:
            import shutil
            shutil.copy2(config_default_path, config_json_path)
            QgsMessageLog.logMessage(
                f"FilterMate: Configuration créée avec les valeurs par défaut",
                "FilterMate",
                Qgis.Info
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"FilterMate: Impossible de copier la configuration par défaut: {e}",
                "FilterMate",
                Qgis.Warning
            )
            # Fallback: use config.json from plugin directory
            config_json_path = os.path.join(DIR_CONFIG, 'config.json')
    
    # Load configuration
    CONFIG_DATA = None
    try:
        with open(config_json_path) as f:
            CONFIG_DATA = json.load(f)
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Failed to load config from {config_json_path}: {e}",
            "FilterMate",
            Qgis.Critical
        )
        # Try to load default config as last resort
        try:
            with open(config_default_path) as f:
                CONFIG_DATA = json.load(f)
        except Exception as e2:
            QgsMessageLog.logMessage(
                f"Failed to load default config: {e2}",
                "FilterMate",
                Qgis.Critical
            )
            raise

    # Validate that CONFIG_DATA has the expected structure
    # Support both uppercase (config.default.json) and lowercase (migrated config.json) keys
    has_app_config = isinstance(CONFIG_DATA, dict) and ("APP" in CONFIG_DATA or "app" in CONFIG_DATA)
    if not has_app_config:
        QgsMessageLog.logMessage(
            f"FilterMate: Configuration invalide détectée, réinitialisation aux valeurs par défaut",
            "FilterMate",
            Qgis.Warning
        )
        # Reset to default
        try:
            import shutil
            shutil.copy2(config_default_path, config_json_path)
            with open(config_json_path) as f:
                CONFIG_DATA = json.load(f)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"FilterMate: Impossible de réinitialiser la configuration: {e}",
                "FilterMate",
                Qgis.Critical
            )
            raise

    # Ensure OPTIONS exists in APP (support both uppercase and lowercase keys)
    app_key = "APP" if "APP" in CONFIG_DATA else "app"
    if app_key not in CONFIG_DATA:
        CONFIG_DATA[app_key] = {}
    if "OPTIONS" not in CONFIG_DATA.get(app_key, {}):
        CONFIG_DATA[app_key]["OPTIONS"] = {"APP_SQLITE_PATH": "", "FRESH_RELOAD_FLAG": False}

    # Validate APP_SQLITE_PATH from config
    app_sqlite_path = CONFIG_DATA.get(app_key, {}).get("OPTIONS", {}).get("APP_SQLITE_PATH", "")
    if app_sqlite_path != '':
        configured_path = os.path.normpath(app_sqlite_path)
        
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
                        f"Configured path parent directory is not writable: {parent_dir}. Using default profile.",
                        "FilterMate",
                        Qgis.Warning
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Cannot access configured path: {configured_path}. Error: {e}. Using default profile.",
                    "FilterMate",
                    Qgis.Warning
                )
        else:
            QgsMessageLog.logMessage(
                f"Configured path parent directory does not exist: {parent_dir}. Using default profile.",
                "FilterMate",
                Qgis.Warning
            )
        
        if path_is_valid:
            PLUGIN_CONFIG_DIRECTORY = configured_path
            # Update config_json_path if directory changed
            config_json_path = os.path.join(PLUGIN_CONFIG_DIRECTORY, 'config.json')
    
    # Update APP_SQLITE_PATH in config if needed
    current_sqlite_path = CONFIG_DATA.get(app_key, {}).get("OPTIONS", {}).get("APP_SQLITE_PATH", "")
    if current_sqlite_path != PLUGIN_CONFIG_DIRECTORY:
        CONFIG_DATA[app_key]["OPTIONS"]["APP_SQLITE_PATH"] = PLUGIN_CONFIG_DIRECTORY
        try:
            with open(config_json_path, 'w') as outfile:
                outfile.write(json.dumps(CONFIG_DATA, indent=4))
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Could not update config.json with path: {e}",
                "FilterMate",
                Qgis.Warning
            )

    global ENV_VARS
    ENV_VARS["PROJECT"] = PROJECT
    ENV_VARS["PLATFORM"] = PLATFORM
    ENV_VARS["DIR_CONFIG"] = DIR_CONFIG
    ENV_VARS["PATH_ABSOLUTE_PROJECT"] = PATH_ABSOLUTE_PROJECT
    ENV_VARS["CONFIG_DATA"] = CONFIG_DATA
    ENV_VARS["QGIS_SETTINGS_PATH"] = QGIS_SETTINGS_PATH
    ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] = PLUGIN_CONFIG_DIRECTORY
    ENV_VARS["CONFIG_JSON_PATH"] = config_json_path  # Store active config path


def reset_config_to_default():
    """
    Reset configuration to default by copying config.default.json 
    to the active config location (PLUGIN_CONFIG_DIRECTORY/config.json).
    
    Use this when reinitializing the config and SQLite database.
    
    Returns:
        bool: True if reset successful, False otherwise
    """
    try:
        import shutil
        
        if "DIR_CONFIG" not in ENV_VARS or "CONFIG_JSON_PATH" not in ENV_VARS:
            QgsMessageLog.logMessage(
                "Environment variables not initialized. Call init_env_vars() first.",
                "FilterMate",
                Qgis.Critical
            )
            return False
        
        config_default_path = os.path.join(ENV_VARS["DIR_CONFIG"], 'config.default.json')
        config_json_path = ENV_VARS["CONFIG_JSON_PATH"]
        
        # Backup existing config if it exists
        if os.path.exists(config_json_path):
            backup_path = config_json_path + '.backup'
            shutil.copy2(config_json_path, backup_path)
            QgsMessageLog.logMessage(
                f"Backed up existing config to: {backup_path}",
                "FilterMate",
                Qgis.Info
            )
        
        # Copy default config
        shutil.copy2(config_default_path, config_json_path)
        
        # Reload config
        with open(config_json_path) as f:
            ENV_VARS["CONFIG_DATA"] = json.load(f)
        
        QgsMessageLog.logMessage(
            f"Configuration reset to default: {config_json_path}",
            "FilterMate",
            Qgis.Info
        )
        
        return True
        
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Failed to reset configuration: {e}",
            "FilterMate",
            Qgis.Critical
        )
        return False
