from qgis.core import QgsProject, QgsUserProfileManager, QgsUserProfile
import os
import json

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

PROJECT = QgsProject.instance()

DIR_CONFIG = os.path.normpath(os.path.dirname(__file__))
PATH_ABSOLUTE_PROJECT = os.path.normpath(PROJECT.readPath("./"))
if PATH_ABSOLUTE_PROJECT =='./':
    PATH_ABSOLUTE_PROJECT =  os.path.normpath(os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop'))

CONFIG_DATA = None

with open(DIR_CONFIG +  os.sep + 'config.json') as f:
  CONFIG_DATA = json.load(f)

if CONFIG_DATA["APP"]["SQLITE_PATH"] != '':
    PLUGIN_CONFIG_DIRECTORY = os.path.normpath(CONFIG_DATA["APP"]["SQLITE_PATH"])
else:
    PLUGIN_CONFIG_DIRECTORY = os.path.normpath(os.environ['APPDATA'] + '\QGIS\QGIS3\profiles\default\FilterMate')
    CONFIG_DATA["APP"]["SQLITE_PATH"] = PLUGIN_CONFIG_DIRECTORY
    with open(DIR_CONFIG +  os.sep + 'config.json', 'w') as outfile:
        outfile.write(json.dumps(CONFIG_DATA, indent=4))

if not os.path.isdir(PLUGIN_CONFIG_DIRECTORY):
    try:
        os.makedirs(PLUGIN_CONFIG_DIRECTORY, exist_ok = True)
    except OSError as error:
        pass


