---
sidebar_position: 4
---

# Known Issues

Current limitations, known bugs, and workarounds for FilterMate. This page is regularly updated as issues are discovered and resolved.

:::tip Reporting Issues
Found a new issue? [Report it on GitHub](https://github.com/sducournau/filter_mate/issues) with details about your environment and steps to reproduce.
:::

## Current Limitations

### Backend-Specific Limitations

#### PostgreSQL Backend

**✅ Fully Supported**

No significant limitations. PostgreSQL/PostGIS provides complete functionality.

**Minor Notes**:
- Requires `psycopg2` package installation
- Network latency affects remote database performance
- Materialized views require database write permissions

#### Spatialite Backend

**⚠️ Good with Minor Limitations**

| Feature | Support | Notes |
|---------|---------|-------|
| Spatial predicates | ✅ Full | All predicates supported |
| Buffer operations | ✅ Full | Fixed and dynamic buffers |
| Negative buffers | ⚠️ Limited | Can fail on complex geometries |
| Very large datasets | ⚠️ Slow | > 500k features slow |
| Concurrent access | ⚠️ Limited | SQLite file locking issues |

**Workarounds**:
- For > 500k features: Use PostgreSQL
- For concurrent access: Copy database per instance
- For negative buffers: Simplify geometries first

#### OGR Backend

**⚠️ Universal but Limited**

| Feature | Support | Notes |
|---------|---------|-------|
| Spatial predicates | ⚠️ Basic | Only intersects, contains, within |
| Buffer operations | ✅ Good | Fixed buffers work well |
| Dynamic buffers | ❌ No | Not supported |
| Touches predicate | ❌ No | Use intersects instead |
| Crosses predicate | ❌ No | Use intersects instead |
| Overlaps predicate | ❌ No | Use intersects instead |

**Workarounds**:
- Use PostgreSQL or Spatialite for advanced predicates
- Convert Shapefiles to GeoPackage for better performance
- Use QGIS Processing for complex operations

### Data Source Limitations

#### Shapefile Format

**Known Issues**:
- Field names limited to 10 characters
- No native spatial index (created in memory)
- Single file size limit (2GB)
- Limited attribute types

**Recommendations**:
- Convert to GeoPackage for better performance
- Use PostgreSQL for large datasets
- Enable spatial indexing in QGIS

#### GeoJSON Format

**Known Issues**:
- Large files load slowly
- No built-in spatial index
- Memory-intensive for > 100k features

**Recommendations**:
- Convert to GeoPackage or PostgreSQL
- Split large files into smaller chunks
- Use streamed processing for very large files

### CRS and Projection Issues

#### Mixed CRS Datasets

**Issue**: Filtering with different CRS can give incorrect results

**Symptoms**:
- Features not filtered when they should be
- Buffer distances incorrect
- Geometric predicates fail

**Solution**: Ensure all layers use the same CRS
```python
# Reproject before filtering
processing.run("native:reprojectlayer", {
    'INPUT': layer,
    'TARGET_CRS': 'EPSG:3857'
})
```

#### Geographic CRS Buffers

**Issue**: Buffer distances in degrees don't represent real-world distances

**Example**:
```python
# ❌ Bad - 100 degrees is huge!
buffer_distance = 100  # EPSG:4326

# ✅ Good - 100 meters makes sense
buffer_distance = 100  # EPSG:3857
```

**Solution**: Always reproject to meters-based CRS before buffering

### Geometry Issues

#### Invalid Geometries

**Issue**: Invalid geometries cause filter failures

**Common Problems**:
- Self-intersecting polygons
- Unclosed rings
- Duplicate vertices
- Null geometries

**FilterMate Handling**:
- ✅ Auto-repair attempted with ST_MakeValid
- ⚠️ May skip features that can't be repaired
- 📝 Warning message shown in QGIS

**Manual Fix**:
```python
# Fix invalid geometries
processing.run("native:fixgeometries", {
    'INPUT': layer,
    'OUTPUT': 'fixed_layer.gpkg'
})
```

#### Empty Geometries

**Issue**: Features with NULL or empty geometries are skipped

**Workaround**: Remove before filtering
```python
# Remove empty geometries
expression = "geometry IS NOT NULL AND NOT is_empty(geometry)"
layer.setSubsetString(expression)
```

## Known Bugs

### High Priority

#### 1. psycopg2 Import Issues on Windows

**Status**: ⚠️ Known Issue  
**Affects**: Windows users with QGIS standalone installer  
**Severity**: High

**Symptoms**:
- FilterMate shows "PostgreSQL not available"
- Import error: "DLL load failed"

**Workaround**:
```bash
# Use OSGeo4W Shell (as Administrator)
py3_env
pip install psycopg2-binary --force-reinstall
```

**Permanent Fix**: Use QGIS with OSGeo4W installer

#### 2. Spatialite Lock Issues on Network Drives

**Status**: ⚠️ Known Issue  
**Affects**: Spatialite databases on network drives  
**Severity**: Medium

**Symptoms**:
- "Database is locked" error
- Filters fail intermittently
- Slow performance

**Workaround**:
```python
# Copy database to local drive
import shutil
shutil.copy('/network/path/data.db', '/tmp/data.db')
# Work with local copy
```

**Permanent Fix**: Store Spatialite databases on local drives

### Medium Priority

#### 3. Theme Detection on macOS

**Status**: ⚠️ Known Issue  
**Affects**: macOS with dark mode  
**Severity**: Low

**Symptoms**:
- Theme detection may not match system theme
- Manual theme selection required

**Workaround**:
```json
{
    "COLORS": {
        "ACTIVE_THEME": {"value": "dark"}  // Force dark theme
    }
}
```

#### 4. Large Export Memory Usage

**Status**: ⚠️ Known Issue  
**Affects**: Exports > 100k features  
**Severity**: Medium

**Symptoms**:
- High memory usage during export
- QGIS may become unresponsive
- Out of memory on 32-bit systems

**Workaround**:
- Export in smaller batches
- Use PostgreSQL backend (server-side export)
- Close other applications
- Increase system swap space

### Low Priority

#### 5. Icon Scaling on HiDPI Displays

**Status**: ⚠️ Known Issue  
**Affects**: 4K and HiDPI displays  
**Severity**: Low

**Symptoms**:
- Icons may appear blurry
- Inconsistent sizing

**Workaround**:
```json
{
    "PushButton": {
        "ICONS_SIZES": {
            "ACTION": 35,  // Increase from 25
            "OTHERS": 28   // Increase from 20
        }
    }
}
```

## Compatibility Issues

### QGIS Versions

| QGIS Version | Support Status | Notes |
|--------------|---------------|-------|
| **3.34+** | ✅ Fully Supported | Recommended |
| **3.28 - 3.32** | ✅ Supported | All features work |
| **3.22 - 3.26** | ⚠️ Partial | Some UI issues |
| **< 3.22** | ❌ Not Supported | Critical bugs |

**Recommendation**: Use QGIS 3.28 or newer

### Python Versions

| Python Version | Support Status | Notes |
|----------------|---------------|-------|
| **3.9+** | ✅ Fully Supported | Recommended |
| **3.7 - 3.8** | ✅ Supported | Works well |
| **3.6** | ⚠️ Deprecated | Security issues |
| **< 3.6** | ❌ Not Supported | Missing features |

### Operating Systems

| OS | Support Status | Notes |
|----|---------------|-------|
| **Windows 10/11** | ✅ Fully Supported | Tested regularly |
| **Linux (Ubuntu)** | ✅ Fully Supported | Tested regularly |
| **macOS** | ⚠️ Partial | Theme detection issues |
| **Windows 7/8** | ⚠️ Limited | No longer tested |

## Performance Issues

### Slow First Filter

**Not a Bug**: Expected behavior

**Cause**: FilterMate performs one-time setup:
- Creates spatial indexes
- Caches geometry sources
- Analyzes layer structure

**Timeline**:
- First filter: 2-10 seconds
- Subsequent filters: 0.5-2 seconds (5× faster)

**This is normal and expected!**

### Slow on Large Datasets

**Expected Behavior**: Large datasets take time

**Guidelines**:
- 10k features: < 1s ✅
- 100k features: 2-10s ✅
- 1M features: 10-60s ✅
- 10M features: 1-5 minutes ⚠️

**If slower than expected**:
1. Check spatial index exists
2. Use PostgreSQL backend
3. Update database statistics (ANALYZE)
4. See [Performance Tuning](./performance-tuning.md)

## Workarounds Reference

### Issue: PostgreSQL Not Available

**Solutions** (try in order):
1. Install psycopg2: `pip install psycopg2-binary`
2. Restart QGIS
3. Use OSGeo4W Shell on Windows
4. Check Python environment

### Issue: Database Locked

**Solutions**:
1. Close other connections to database
2. Copy database to local drive
3. Use PostgreSQL instead of Spatialite
4. Check file permissions

### Issue: Invalid Geometries

**Solutions**:
1. Let FilterMate auto-repair (default)
2. Use QGIS fix geometries tool
3. Simplify before filtering
4. Remove problematic features

### Issue: Slow Performance

**Solutions**:
1. Create spatial indexes
2. Use right backend for dataset size
3. Update database statistics
4. Use projected CRS
5. See [Performance Tuning](./performance-tuning.md)

### Issue: Filter Not Applied

**Solutions**:
1. Check layer is not empty
2. Verify CRS matches
3. Check for invalid geometries
4. Review filter expression
5. Check QGIS message bar for errors

## Planned Improvements

### Roadmap

#### Version 2.3 (Q1 2026)

- [ ] **Improved macOS support** - Better theme detection
- [ ] **Batch export optimization** - Reduce memory usage
- [ ] **Connection pooling** - Better multi-instance support
- [ ] **Expression builder** - GUI for complex filters

#### Version 2.4 (Q2 2026)

- [ ] **Remote backend support** - Filter on remote servers
- [ ] **Async exports** - Non-blocking large exports
- [ ] **Custom predicates** - User-defined spatial functions
- [ ] **Performance profiles** - Preset optimization strategies

#### Version 3.0 (Q3 2026)

- [ ] **Distributed filtering** - Multi-server processing
- [ ] **Real-time filtering** - Update as data changes
- [ ] **Web services** - REST API for filtering
- [ ] **Cloud backends** - AWS, Azure, GCP support

## Reporting New Issues

### Before Reporting

**Check**:
1. Is it in this known issues list?
2. Are you using latest FilterMate version?
3. Are you using supported QGIS version?
4. Have you tried workarounds?

### What to Include

**Essential Information**:
```markdown
**FilterMate Version**: 2.2.4
**QGIS Version**: 3.34.1
**OS**: Windows 11 / Ubuntu 22.04 / macOS 13
**Python Version**: 3.9.5

**Backend**: PostgreSQL / Spatialite / OGR
**Dataset Size**: ~10,000 features
**Layer CRS**: EPSG:4326 / EPSG:3857

**Issue Description**:
Clear description of the problem

**Steps to Reproduce**:
1. Step one
2. Step two
3. Step three

**Expected Behavior**:
What should happen

**Actual Behavior**:
What actually happens

**Error Messages**:
```
Paste any error messages from QGIS message bar or Python console
```

**Screenshots**:
Attach if relevant
```

### Where to Report

- **GitHub Issues**: https://github.com/sducournau/filter_mate/issues
- **GitHub Discussions**: For questions and help
- **Email**: For security issues only

## FAQ

### Q: Why is PostgreSQL not detected?

**A**: Install psycopg2 package:
```bash
pip install psycopg2-binary
```

### Q: Why is first filter slow?

**A**: Normal - FilterMate creates indexes and caches data. Subsequent filters are much faster.

### Q: Can I use FilterMate with very large datasets?

**A**: Yes! Use PostgreSQL backend for datasets > 500k features. It's designed for this.

### Q: Does FilterMate work offline?

**A**: Yes, fully offline for Spatialite and OGR backends. PostgreSQL requires network if database is remote.

### Q: Is there a performance limit?

**A**: PostgreSQL backend handles 10M+ features. Practical limit is your hardware and patience.

### Q: Can I contribute fixes?

**A**: Absolutely! See [Contributing Guide](../developer-guide/contributing.md)

## See Also

- [Troubleshooting Guide](./troubleshooting.md) - General troubleshooting
- [Performance Tuning](./performance-tuning.md) - Optimization guide
- [Backend Selection](../backends/backend-selection.md) - Choose right backend
- [GitHub Issues](https://github.com/sducournau/filter_mate/issues) - Report problems

---

*Last updated: December 8, 2025*  
*Issues in this document are current as of FilterMate v2.2.4*