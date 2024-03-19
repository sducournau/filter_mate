from qgis.core import QgsApplication, QgsProject, QgsUserProfileManager, QgsUserProfile
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
    if QGIS_SETTINGS_PATH[-1] in ('\,/'):
        QGIS_SETTINGS_PATH = QGIS_SETTINGS_PATH[:-1]

    if CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"] != '':
        PLUGIN_CONFIG_DIRECTORY = os.path.normpath(CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"])
    else:
        PLUGIN_CONFIG_DIRECTORY = os.path.normpath(QGIS_SETTINGS_PATH + '\FilterMate')
        CONFIG_DATA["APP"]["OPTIONS"]["APP_SQLITE_PATH"] = PLUGIN_CONFIG_DIRECTORY
        with open(DIR_CONFIG +  os.sep + 'config.json', 'w') as outfile:
            outfile.write(json.dumps(CONFIG_DATA, indent=4))

    global ENV_VARS
    ENV_VARS["PROJECT"] = PROJECT
    ENV_VARS["PLATFORM"] = PLATFORM
    ENV_VARS["DIR_CONFIG"] = DIR_CONFIG
    ENV_VARS["PATH_ABSOLUTE_PROJECT"] = PATH_ABSOLUTE_PROJECT
    ENV_VARS["CONFIG_DATA"] = CONFIG_DATA
    ENV_VARS["QGIS_SETTINGS_PATH"] = QGIS_SETTINGS_PATH
    ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] = PLUGIN_CONFIG_DIRECTORY

    if not os.path.isdir(PLUGIN_CONFIG_DIRECTORY):
        try:
            os.makedirs(PLUGIN_CONFIG_DIRECTORY, exist_ok = True)
        except OSError as error:
            pass


