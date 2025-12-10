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

    with open(DIR_CONFIG +  os.sep + 'config.json') as f:
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
            try:
                with open(DIR_CONFIG + os.sep + 'config.json', 'w') as outfile:
                    outfile.write(json.dumps(CONFIG_DATA, indent=4))
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Could not update config.json with new path: {e}",
                    "FilterMate",
                    Qgis.Warning
                )
    else:
        # Use os.path.join for proper cross-platform path construction
        PLUGIN_CONFIG_DIRECTORY = os.path.normpath(os.path.join(QGIS_SETTINGS_PATH, 'FilterMate'))
        CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"] = PLUGIN_CONFIG_DIRECTORY
        try:
            with open(DIR_CONFIG + os.sep + 'config.json', 'w') as outfile:
                outfile.write(json.dumps(CONFIG_DATA, indent=4))
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Could not update config.json: {e}",
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


