# FilterMate - Migration Guide v1.8 → v1.9

**Quick Guide for Existing Users**

---

## 🎯 What Changed?

### Summary

FilterMate v1.9 now works **WITHOUT PostgreSQL**! 🎉

- ✅ **Before (v1.8)**: Required PostgreSQL + psycopg2 (or plugin wouldn't start)
- ✅ **Now (v1.9)**: Works with any data source (PostgreSQL optional)

---

## 🚀 Quick Migration

### If You Use PostgreSQL

**No changes needed!** Everything works exactly as before.

✅ Your PostgreSQL workflows are **100% compatible**  
✅ Performance is **identical** (no regression)  
✅ All features work **the same way**

### If You Don't Use PostgreSQL

**Great news!** FilterMate now works for you too.

✅ Load Shapefiles, GeoPackages, or Spatialite  
✅ Use FilterMate normally  
✅ Filtering works automatically (Spatialite backend)

---

## 📊 Backend Selection (Automatic)

FilterMate automatically chooses the best backend:

```
Your Data → Detected Automatically:

PostgreSQL layer + psycopg2 installed
  ↓
  Use PostgreSQL backend (fastest)

Spatialite layer OR PostgreSQL unavailable
  ↓
  Use Spatialite backend (fast)

Shapefile / GeoPackage / Other
  ↓
  Use Local backend (good for small datasets)
```

**You don't configure anything** - it's automatic! 🤖

---

## 🔧 Do I Need to Reinstall?

### If You Have psycopg2

**No action needed.**

FilterMate will automatically use PostgreSQL when available.

### If You Don't Have psycopg2

**No action needed.**

FilterMate will work fine without it! You'll see an info message:

```
"FilterMate: PostgreSQL support disabled (psycopg2 not found).
Plugin will work with local files (Shapefile, GeoPackage, etc.) and Spatialite."
```

This is **informational only** - not an error!

---

## ⚡ Performance Comparison

| Your Data | v1.8 (PostgreSQL only) | v1.9 (Multi-backend) |
|-----------|------------------------|----------------------|
| **PostgreSQL layer** | ⚡⚡⚡ Fast | ⚡⚡⚡ Fast (same) |
| **Spatialite** | ❌ Didn't work | ⚡⚡ Fast (new!) |
| **Shapefile** | ❌ Didn't work | ⚡ Good (new!) |
| **GeoPackage** | ❌ Didn't work | ⚡ Good (new!) |

---

## 💡 Recommendations

### Small Projects (< 10k features)

Use any format you want:
- Shapefile ✅
- GeoPackage ✅
- Spatialite ✅

Performance is good with all backends.

### Medium Projects (10k - 50k)

**Best**: Spatialite or PostgreSQL  
**OK**: Shapefile/GeoPackage (but slower)

### Large Projects (> 50k)

**Best**: PostgreSQL (highly recommended)  
**Acceptable**: Spatialite (but you'll see performance warnings)  
**Not recommended**: Shapefile

---

## 🆕 New Messages You Might See

### "Large dataset (X features) using Spatialite backend"

**Meaning**: You're filtering >50k features without PostgreSQL

**Action**:
- ✅ **Continue**: Works fine, just a bit slower
- ⚡ **Install PostgreSQL**: For better performance (optional)

**This is INFO, not an error!**

### "Filtering with Spatialite backend..."

**Meaning**: FilterMate is using Spatialite for your data

**Action**: None needed! This is just informational.

### "FilterMate: PostgreSQL support disabled"

**Meaning**: psycopg2 not installed (plugin works fine without it)

**Action**:
- ✅ **Continue**: Use Spatialite backend
- 📦 **Install psycopg2**: For PostgreSQL support (optional)

---

## 🐛 Known Issues & Solutions

### Issue: "Plugin is slower than before"

**Possible causes**:
1. You migrated from PostgreSQL to Shapefile
2. Dataset is large (>50k features)

**Solutions**:
- Keep using PostgreSQL layers (same speed as v1.8)
- Convert Shapefile → Spatialite (faster)
- For large datasets: Use PostgreSQL

### Issue: "Where did my PostgreSQL connection go?"

**Answer**: It's still there! If you had PostgreSQL working in v1.8, it still works in v1.9.

Check:
```python
# QGIS Python Console:
from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
print(POSTGRESQL_AVAILABLE)  # Should be True
```

If `False`, reinstall psycopg2:
```python
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
```

---

## 📝 Changelog Details

### What's New in v1.9

**Phase 1** (Import conditionnel):
- ✅ Plugin starts without psycopg2
- ✅ Graceful degradation to Spatialite

**Phase 2** (Backend Spatialite):
- ✅ Full Spatialite backend implementation
- ✅ Automatic backend selection
- ✅ Support for all OGR formats
- ✅ Performance warnings for large datasets

**Phase 3** (Polish):
- ✅ User-friendly messages
- ✅ Improved error handling
- ✅ Comprehensive documentation

### What's Preserved

- ✅ All PostgreSQL features (100% compatible)
- ✅ All UI elements (same interface)
- ✅ All keyboard shortcuts (unchanged)
- ✅ All configuration settings (compatible)
- ✅ Filter history (works across backends)

---

## 🔄 Rollback (If Needed)

If you encounter issues with v1.9, you can roll back:

1. **Uninstall v1.9**:
   - QGIS → Plugins → Manage and Install Plugins
   - Find FilterMate → Uninstall

2. **Install v1.8**:
   - Download v1.8 from [GitHub Releases](https://github.com/sducournau/filter_mate/releases)
   - Manual install to plugins directory

3. **Restart QGIS**

**Note**: We don't expect rollbacks to be necessary - v1.9 is very stable!

---

## 🆘 Getting Help

### Check Your Setup

```python
# QGIS Python Console:
from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE

print(f"PostgreSQL available: {POSTGRESQL_AVAILABLE}")
print(f"Active layer provider: {iface.activeLayer().providerType()}")
print(f"Feature count: {iface.activeLayer().featureCount()}")
```

### Report Issues

If something doesn't work:

1. **Check QGIS logs**: View → Panels → Log Messages
2. **Report on GitHub**: https://github.com/sducournau/filter_mate/issues
3. **Include**:
   - QGIS version
   - FilterMate version (1.9.x)
   - Data source type (PostgreSQL/Shapefile/etc.)
   - Error message (if any)

---

## ✅ Migration Checklist

- [ ] Update FilterMate to v1.9
- [ ] Restart QGIS
- [ ] Test with your existing PostgreSQL layers (should work identically)
- [ ] Try with a Shapefile (should work now!)
- [ ] Check QGIS logs for any warnings
- [ ] Read new documentation (INSTALLATION.md)
- [ ] 🎉 Enjoy multi-backend FilterMate!

---

## 🎉 Conclusion

**v1.9 is a major upgrade that makes FilterMate more accessible while preserving all existing functionality.**

Key takeaways:
- ✅ **PostgreSQL users**: No changes needed
- ✅ **New users**: Can use any data format
- ✅ **Performance**: Same or better than v1.8
- ✅ **Compatibility**: 100% backward compatible

**Questions?** Check [INSTALLATION.md](INSTALLATION.md) or open a GitHub issue.

---

**Last Updated**: December 2, 2025  
**From Version**: 1.8.x  
**To Version**: 1.9.0
