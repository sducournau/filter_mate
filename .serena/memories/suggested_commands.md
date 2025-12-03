# Suggested Commands for FilterMate Development

## Windows Commands (Primary Development Environment)

### Directory Navigation
```cmd
cd C:\Users\Simon\OneDrive\Documents\GitHub\filter_mate
dir  # List files
```

### Git Commands
```cmd
git status
git add .
git commit -m "Description of changes"
git push origin main
```

### Python Environment (QGIS Python)
FilterMate runs within QGIS Python environment. To test:
1. Open QGIS
2. Go to Plugins → Python Console
3. Load plugin: `import filter_mate`

### Installing Dependencies
```python
# In QGIS Python Console
import pip
pip.main(['install', 'psycopg2-binary'])
```

### Alternative: OSGeo4W Shell (Windows)
```cmd
# Open OSGeo4W Shell as Administrator
py3_env
pip install psycopg2-binary
```

### File Operations
```cmd
# Copy files
copy source_file destination_file

# Move/Rename files  
move old_name new_name

# Delete files
del filename

# Search for text in files
findstr /s /i "search_text" *.py
```

### QGIS Plugin Development
```cmd
# Reload plugin in QGIS
# Use Plugin Reloader plugin or restart QGIS
```

## Testing
```python
# Unit tests (to be implemented in Phase 3)
python -m unittest discover -s . -p "test_*.py"
```

## Debugging
```python
# In QGIS Python Console
import filter_mate
from filter_mate import filter_mate_app
# Access application instance
app = filter_mate.FilterMateApp(plugin_dir)
```

## Common Development Tasks

### Check for Errors
1. Open QGIS
2. Load FilterMate plugin
3. Check QGIS Python Console for errors
4. Check QGIS Log Messages panel

### Test with Different Data Sources
```python
# PostgreSQL test
layer = QgsVectorLayer("dbname='test' host=localhost port=5432 ...", "test", "postgres")

# Spatialite test
layer = QgsVectorLayer("C:/path/to/database.sqlite|layername=layer1", "test", "spatialite")

# Shapefile test
layer = QgsVectorLayer("C:/path/to/file.shp", "test", "ogr")
```

### Check Plugin Installation
```cmd
# Plugin directory (Windows)
C:\Users\Simon\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\filter_mate
```

## Linting and Formatting (Future - Phase 3)
```cmd
# Pylint (to be added)
pylint filter_mate_app.py

# Black formatter (to be added)
black filter_mate_app.py
```

## Building/Packaging
```cmd
# Create plugin zip
# (Manual process: zip the plugin directory excluding .git, .github, .serena)
```

## Performance Profiling (Development)
```python
# In QGIS Python Console
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# Run plugin operation
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)
```

## Useful QGIS Commands
```python
# Get active layer
iface.activeLayer()

# Get all layers
QgsProject.instance().mapLayers()

# Refresh map canvas
iface.mapCanvas().refresh()

# Open expression builder
from qgis.gui import QgsExpressionBuilderDialog
dialog = QgsExpressionBuilderDialog(layer)
dialog.exec_()
```
