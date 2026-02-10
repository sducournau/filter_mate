# Suggested Commands for FilterMate Development

**Last Updated:** January 17, 2026 (v4.0.3)

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

## Linting and Formatting
```cmd
# Pylint
pylint filter_mate_app.py modules/*.py

# Black formatter
black filter_mate_app.py modules/

# Flake8
flake8 filter_mate_app.py --max-line-length=120

# All linters via CI
pytest tests/ -v && black --check . && flake8
```

## Testing (pytest)
```cmd
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=modules --cov-report=html

# Run specific test file
pytest tests/test_backends.py -v

# Run specific test
pytest tests/test_undo_redo.py::test_global_filter_state -v

# Quick tests only (no slow markers)
pytest tests/ -v -k "not slow"
```

## Building/Packaging
```cmd
# Create plugin zip (using tools script)
cd tools/build
python create_release_zip.py
```

## Translation Workflow
```cmd
# Compile translations
cd tools/i18n
python compile_ts_to_qm.py

# Verify translations
python verify_translations.py

# Or use batch file (Windows)
compile_translations.bat
```

## UI Development
```cmd
# After modifying .ui file, regenerate .py
scripts/compile_ui.bat

# Fix widget naming issues
cd tools/ui
python fix_ui_suffixes.py

# Verify UI changes
python verify_ui_fix.py
```

## Diagnostic Tools
```cmd
# Test plugin loading without QGIS
cd tools/diagnostic
python test_load_simple.py

# Debug freezes (run in QGIS console)
exec(open('tools/diagnostic/diagnose_freeze.py').read())
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
