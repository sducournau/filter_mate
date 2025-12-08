---
sidebar_position: 5
---

# Troubleshooting Guide

Common issues and solutions for FilterMate.

## Installation Issues

### Plugin Not Visible in QGIS

**Symptoms:**
- FilterMate not in Plugin menu
- Not listed in Plugin Manager

**Solutions:**

1. **Check installation:**
   ```bash
   # Linux
   ls ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate
   
   # Windows
   dir %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\filter_mate
   ```

2. **Verify metadata.txt exists**

3. **Enable in Plugin Manager:**
   - Plugins → Manage and Install Plugins
   - Installed tab
   - Check "FilterMate"

4. **Restart QGIS**

### Import Errors on Startup

**Error:**
```
ModuleNotFoundError: No module named 'psycopg2'
```

**Solution:**
psycopg2 is optional. If you don't use PostgreSQL:
1. Open `config/config.json`
2. Set `"POSTGRESQL_AVAILABLE": false`
3. Restart QGIS

To install psycopg2:
```bash
pip install psycopg2-binary
```

## Connection Issues

### PostgreSQL Connection Failed

**Symptoms:**
- "Cannot connect to database"
- "Connection refused"

**Solutions:**

1. **Check PostgreSQL is running:**
   ```bash
   sudo systemctl status postgresql
   ```

2. **Verify connection parameters:**
   - Host: correct address
   - Port: default 5432
   - Database: exists
   - User: has permissions

3. **Test connection in QGIS:**
   - Layer → Add Layer → Add PostGIS Layer
   - Try connecting directly

4. **Check psycopg2 installation:**
   ```python
   # In QGIS Python Console
   import psycopg2
   print(psycopg2.__version__)
   ```

### Spatialite Database Locked

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Causes:**
- Another process using database
- QGIS project auto-save
- Incomplete previous operation

**Solutions:**

1. **Automatic retry (built-in):**
   - FilterMate retries 5 times automatically
   - Wait a few seconds

2. **Close other connections:**
   - Close other QGIS projects using same database
   - Check DB Browser for SQLite

3. **Restart QGIS:**
   - Save project
   - Restart QGIS
   - Reopen project

## Filtering Issues

### Filter Not Applied

**Symptoms:**
- Layer still shows all features
- No visible change

**Check:**

1. **Expression syntax:**
   ```sql
   # Correct
   population > 10000
   
   # Wrong
   population > 10,000  # No commas in numbers
   ```

2. **Field names:**
   - Case-sensitive
   - Use quotes for special characters: `"Field Name"`

3. **Layer provider:**
   - PostgreSQL: Server-side filtering
   - Others: QGIS expression engine

4. **Backend warnings:**
   - Check message bar for warnings
   - May indicate performance issues

### Geometric Filter Returns No Features

**Possible Causes:**

1. **CRS mismatch:**
   ```python
   # Check CRS
   Source CRS: EPSG:4326 (WGS84)
   Target CRS: EPSG:3857 (Web Mercator)
   # FilterMate automatically reprojects
   ```

2. **Buffer too small/large:**
   - Units in layer CRS
   - Check unit (meters vs degrees)

3. **Invalid geometries:**
   - FilterMate attempts automatic repair
   - Check QGIS message bar

**Solutions:**

1. **Verify CRS:**
   - Layer Properties → Information
   - Ensure both layers have valid CRS

2. **Test without buffer:**
   - Set buffer to 0
   - Test predicate alone

3. **Repair geometries:**
   - Vector → Geometry Tools → Fix Geometries

### Expression Conversion Failed

**Error:**
```
Cannot convert expression to backend SQL
```

**Cause:**
- QGIS expression not supported by backend

**Solutions:**

1. **Use simpler expressions:**
   ```sql
   # Instead of
   to_string($area) LIKE '1000%'
   
   # Use
   $area >= 1000 AND $area < 2000
   ```

2. **Check backend compatibility:**
   - PostgreSQL: Full PostGIS functions
   - Spatialite: ~90% PostGIS compatible
   - OGR: Limited expressions

## Performance Issues

### Filtering Very Slow

**Symptoms:**
- Operation takes > 30 seconds
- UI freezes

**Solutions:**

1. **Check dataset size:**
   ```python
   layer.featureCount()
   # > 50,000: Consider PostgreSQL
   ```

2. **Use PostgreSQL backend:**
   ```bash
   pip install psycopg2-binary
   ```
   - Convert data to PostGIS
   - 10-100× faster for large datasets

3. **Optimize expression:**
   ```sql
   # Slow: Complex expression
   to_string($area) LIKE '%000'
   
   # Fast: Simple comparison
   $area > 1000
   ```

4. **Reduce buffer distance:**
   - Smaller buffers = faster processing

5. **Filter in stages:**
   - Apply attribute filter first
   - Then geometric filter

### UI Not Responsive

**Cause:**
- Heavy operation running

**Check:**
1. **Task progress:**
   - Look for progress bar in QGIS
   - Bottom-right corner

2. **Cancel if needed:**
   - Click "X" on progress bar
   - Or wait for completion

**Prevention:**
- Use PostgreSQL for large datasets
- Test on subset first

## Export Issues

### Export Failed

**Error:**
```
Cannot write to output file
```

**Causes:**

1. **File permissions:**
   ```bash
   # Check write permissions
   touch /path/to/output.gpkg
   ```

2. **File already open:**
   - Close in QGIS
   - Close in external applications

3. **Disk space:**
   ```bash
   df -h  # Check available space
   ```

4. **Invalid path:**
   - Use absolute paths
   - Avoid special characters

### Export Incomplete

**Symptoms:**
- Fewer features than expected
- Missing attributes

**Check:**

1. **Active filter:**
   - Export exports filtered features
   - Clear filter to export all

2. **Field selection:**
   - Verify all fields selected
   - Check "Select All"

3. **CRS transformation:**
   - Some features may be outside target CRS bounds

### Styles Not Exported

**Check:**

1. **Style export enabled:**
   - Configuration → STYLES_TO_EXPORT
   - Set to "QML" or "SLD"

2. **Format supports styles:**
   - GeoPackage: Yes
   - Shapefile: Yes (.qml/.sld file)
   - GeoJSON: No (no style support)

## UI Issues

### Interface Too Large/Small

**Solution:**

1. **Change UI profile:**
   - Configuration tab
   - UI_PROFILE → "compact" or "normal"

2. **Auto mode:**
   - Set to "auto"
   - Adapts to screen resolution

### Theme Not Applied

**Check:**

1. **Theme setting:**
   - Configuration → ACTIVE_THEME
   - Options: auto, default, dark, light

2. **Theme source:**
   - THEME_SOURCE → "qgis" to match QGIS

3. **Restart may be needed:**
   - Close and reopen FilterMate panel

### Configuration Changes Not Saved

**Check:**

1. **Auto-save enabled (v2.2.2+):**
   - Changes save automatically
   - No manual save needed

2. **File permissions:**
   ```bash
   # Check config file writable
   ls -l config/config.json
   ```

3. **Valid JSON:**
   - Syntax errors prevent saving
   - Check QGIS message bar

## Geometry Issues

### Invalid Geometry Warning

**Message:**
```
Invalid geometry detected. Attempting repair...
```

**FilterMate Action:**
- Automatic repair with 5 strategies
- Usually succeeds

**If Fails:**

1. **Manual repair:**
   - Vector → Geometry Tools → Fix Geometries

2. **Check geometry:**
   ```python
   # In QGIS Python Console
   layer = iface.activeLayer()
   for f in layer.getFeatures():
       if not f.geometry().isGeosValid():
           print(f"Invalid: {f.id()}")
   ```

3. **Simplify geometry:**
   - Vector → Geometry Tools → Simplify

### Buffer Operation Failed

**Causes:**

1. **Invalid source geometry**
   - See "Invalid Geometry Warning" above

2. **Negative buffer:**
   - Use positive values only

3. **Buffer too large:**
   - May exceed system memory
   - Reduce buffer distance

## Debug Mode

### Enable Debug Logging

1. **Set in configuration:**
   ```json
   {
     "ENABLE_DEBUG_LOGGING": true
   }
   ```

2. **Restart FilterMate**

3. **View logs:**
   - QGIS Python Console
   - Or check log file (if configured)

### Log Locations

**Linux:**
```bash
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/logs/
```

**Windows:**
```
%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\filter_mate\logs\
```

**macOS:**
```bash
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/logs/
```

## Getting Help

### Before Reporting Issues

1. **Check this guide**
2. **Enable debug logging**
3. **Try with test data**
4. **Check QGIS version compatibility**

### Reporting Issues

Include:

1. **FilterMate version**
2. **QGIS version**
3. **Operating system**
4. **Backend type** (PostgreSQL/Spatialite/OGR)
5. **Error message** (from QGIS console)
6. **Steps to reproduce**
7. **Debug logs** (if enabled)

### Where to Get Help

- **GitHub Issues:** https://github.com/sducournau/filter_mate/issues
- **QGIS Forum:** Tag with "filtermate"
- **Email:** simon.ducournau+filter_mate@gmail.com

## Known Issues

See [Known Issues](./known-issues.md) for current limitations and workarounds.

## Further Reading

- [Installation Guide](../installation.md)
- [Configuration Guide](./configuration.md)
- [Performance Tuning](./performance-tuning.md)
