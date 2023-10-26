from qgis.core import *
from pathlib import Path
import os.path
import json
from shutil import copyfile


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
ROOT = PROJECT.layerTreeRoot()
DIR_PLUGIN = os.path.normpath(os.path.dirname(__file__))
PATH_ABSOLUTE_PROJECT = os.path.normpath(PROJECT.readPath("./"))
if PATH_ABSOLUTE_PROJECT =='./':
    PATH_ABSOLUTE_PROJECT = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')


CONFIG_DATA = None
DIR_CONFIG =  os.getenv('APPDATA') + os.sep + 'Circet' + os.sep +  'Filter'

if not os.path.isdir(DIR_CONFIG):
    try:
        os.makedirs(DIR_CONFIG +  os.sep + 'config', exist_ok = True)
    except OSError as error:
        pass
    if not os.path.isfile(DIR_CONFIG + '/config/config.json'):
        copyfile(DIR_PLUGIN + '/config/config.json', DIR_CONFIG + '/config/config.json')

with open(DIR_CONFIG +  os.sep + '/config/config.json') as f:
  CONFIG_DATA = json.load(f)

LAYERS = CONFIG_DATA['LAYERS']
COLORS = CONFIG_DATA['COLORS']
CONFIG_SCOPE = 0
WIDGETS = {}
WIDGETS['items'] = {}
WIDGETS['NEW'] = None
