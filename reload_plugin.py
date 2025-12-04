"""
Script to reload FilterMate plugin in QGIS

Run this script from the QGIS Python console:
    exec(open('/path/to/filter_mate/reload_plugin.py').read())

Or use the Plugin Reloader plugin:
    https://plugins.qgis.org/plugins/plugin_reloader/
"""

from qgis.utils import plugins, reloadPlugin

plugin_name = 'filter_mate'

if plugin_name in plugins:
    print(f"🔄 Reloading {plugin_name} plugin...")
    reloadPlugin(plugin_name)
    print(f"✅ {plugin_name} reloaded successfully!")
else:
    print(f"❌ Plugin '{plugin_name}' not found. Available plugins:")
    for name in plugins.keys():
        print(f"  - {name}")
