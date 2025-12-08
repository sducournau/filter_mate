# Known Issues & Bug Fixes - FilterMate

## Recently Fixed (v2.2.4)

### Spatialite Field Name Quote Preservation
**Status:** ✅ FIXED in v2.2.4 (December 8, 2025)

**Issue:**
- Field name quotes were incorrectly removed during Spatialite expression conversion
- `"HOMECOUNT" > 100` was converted to `HOMECOUNT > 100`
- Caused filter failures on layers with case-sensitive field names

**Impact:**
- CRITICAL: Filters failed on Spatialite layers with case-sensitive fields
- Affected all Spatialite datasets using quoted field names
- Common in PostgreSQL-migrated data or GeoPackage imports

**Root Cause:**
- `qgis_expression_to_spatialite()` in `modules/backends/spatialite_backend.py`
- Code explicitly stripped double quotes around field names
- Incorrect assumption that Spatialite didn't need quoted identifiers

**Solution:**
- Removed quote-stripping code
- Spatialite now preserves field name quotes
- Relies on implicit type conversion (working correctly)
- Added comprehensive test suite

**Files Changed:**
- `modules/backends/spatialite_backend.py`: Removed quote stripping
- `tests/test_spatialite_expression_quotes.py`: New test suite (comprehensive)

**Test Coverage:**
```python
# Critical test case
def test_quoted_field_names_preserved():
    expr = '"HOMECOUNT" > 100'
    converted = qgis_expression_to_spatialite(expr)
    assert '"HOMECOUNT"' in converted  # Quotes preserved
```

**References:**
- Fix commit: December 8, 2025
- Test file: `tests/test_spatialite_expression_quotes.py`
- Documentation: CHANGELOG.md v2.2.4 section

---

## Recently Fixed (v2.2.3)

### Color Contrast & Accessibility
**Status:** ✅ FIXED in v2.2.3 (December 8, 2025)

**Issue:**
- Insufficient color contrast between UI elements
- Frame backgrounds too similar to widget backgrounds
- Border colors not visible enough
- Text contrast didn't meet WCAG 2.1 standards

**Impact:**
- Poor readability in `default` and `light` themes
- Eye strain during long work sessions
- Accessibility issues for users with mild visual impairments

**Solution:**
- Enhanced frame contrast: +300% improvement
- WCAG 2.1 AA/AAA compliance achieved
- Primary text: 17.4:1 contrast ratio (AAA)
- Secondary text: 8.86:1 contrast ratio (AAA)
- Disabled text: 4.6:1 contrast ratio (AA)
- Darker borders: +40% visibility improvement

**Files Changed:**
- `modules/ui_styles.py`: Color palette adjustments
- `tests/test_color_contrast.py`: WCAG validation tests
- `docs/COLOR_HARMONIZATION.md`: Complete documentation

**Test Coverage:**
```python
def test_wcag_aaa_primary_text():
    contrast = calculate_contrast(text_color, bg_color)
    assert contrast >= 7.0  # AAA standard
```

---

## Recently Fixed (v2.2.2)

### Configuration Reactivity
**Status:** ✅ IMPLEMENTED in v2.2.2 (December 8, 2025)

**Previous Limitation:**
- Configuration changes required plugin restart
- UI profile changes not applied immediately
- Theme switching needed QGIS restart
- Poor user experience for configuration testing

**Solution:**
- Real-time configuration updates without restart
- Dynamic UI profile switching (compact/normal/auto)
- Live theme changes
- Icon updates on configuration change
- Auto-save configuration changes

**Files Changed:**
- `filter_mate_dockwidget.py`: Added `_on_config_item_changed()` handler
- `modules/config_helpers.py`: Configuration utilities with ChoicesType support
- `tests/test_config_json_reactivity.py`: Reactivity test suite

---

## Active Monitoring

### PostgreSQL Optional Dependency
**Status:** ✅ Working as designed

**Implementation:**
- `POSTGRESQL_AVAILABLE` flag in `modules/appUtils.py`
- Graceful degradation when psycopg2 not installed
- Performance warnings for large datasets without PostgreSQL
- Clear user feedback about backend selection

**No Action Needed:** System working correctly

---

### Large Dataset Performance
**Status:** ✅ Optimized (v2.1.0)

**Previous Performance:**
- Slow filtering on 50k+ features with OGR backend
- No spatial index automation
- Inefficient predicate evaluation

**Optimizations Applied:**
- Automatic spatial index creation (OGR)
- Temporary geometry tables (Spatialite)
- Predicate ordering optimization
- Source geometry caching

**Results:**
- 3-45× performance improvement
- Sub-second queries with PostgreSQL
- 1-10s queries with Spatialite (50k features)

**Files:**
- `modules/backends/ogr_backend.py`: Spatial index automation
- `modules/backends/spatialite_backend.py`: Temp tables + R-tree indexes
- `modules/appTasks.py`: Geometry caching

---

## Historical Fixes (Archived)

### SQLite Database Lock Fix
**Status:** ✅ FIXED (v2.1.0)

**Issue:** Database locked errors when multiple operations accessed Spatialite
**Solution:** Retry mechanism with exponential backoff (5 attempts)
**Files:** `modules/appUtils.py` - `spatialite_connect()`
**Documentation:** `docs/archived/fixes/SQLITE_LOCK_FIX.md`

### Field Selection Fix
**Status:** ✅ FIXED (v2.1.0)

**Issue:** Field selection widget didn't show "id" fields
**Solution:** Corrected `QgsFieldExpressionWidget` filter configuration
**Files:** `filter_mate_dockwidget.py` - field widget initialization
**Documentation:** `docs/archived/fixes/FIELD_SELECTION_FIX.md`

### Source Table Name Detection
**Status:** ✅ FIXED (v2.1.0)

**Issue:** Failed to detect source table for PostgreSQL layers
**Solution:** Enhanced URI parsing for PostgreSQL data sources
**Files:** `modules/appUtils.py` - `get_datasource_connexion_from_layer()`
**Documentation:** `docs/archived/fixes/SOURCE_TABLE_NAME_FIX.md`

### Undo/Redo Functionality
**Status:** ✅ FIXED (v2.1.0)

**Issue:** Undo/redo not working properly with filter history
**Solution:** Complete filter history system rewrite
**Files:** `modules/filter_history.py` (new), integration in `filter_mate_app.py`
**Documentation:** `docs/FILTER_HISTORY_INTEGRATION.md`

---

## Known Limitations (Not Bugs)

### 1. Expression Translation
**Description:** Some QGIS expressions may not translate to all backends
**Workaround:** Use standard SQL expressions when possible
**Affected:** Complex QGIS-specific functions
**Priority:** Low (rare use case)

### 2. Very Large Exports
**Description:** Exports > 1M features may require significant disk space
**Workaround:** Export in batches or use PostgreSQL backend
**Affected:** All backends
**Priority:** Low (documented limitation)

### 3. PostgreSQL Dependency
**Description:** Best performance requires psycopg2 package
**Workaround:** Install psycopg2 or use Spatialite for medium datasets
**Affected:** Large datasets (> 50k features)
**Priority:** Medium (documented, warnings provided)

### 4. Special Characters in Field Names
**Description:** Field names with spaces or special chars need quoting
**Workaround:** Use double quotes: `"Field Name"` instead of `Field Name`
**Affected:** All backends
**Priority:** Low (standard SQL practice)
**Status:** v2.2.4 improved handling for case-sensitive names

---

## Debugging Tips

### Common Issues

#### 1. Filter Not Working
**Check:**
- Field name quoting (use `"FIELD"` for case-sensitive)
- Expression syntax
- Layer provider type
- Backend availability

**Debug:**
```python
# In QGIS Python console
layer = iface.activeLayer()
print(f"Provider: {layer.providerType()}")
print(f"Expression: {layer.subsetString()}")
```

#### 2. Performance Issues
**Check:**
- Feature count (`layer.featureCount()`)
- Backend type (PostgreSQL > Spatialite > OGR)
- Spatial index existence

**Debug:**
```bash
# Run performance tests
python tests/benchmark_simple.py
```

#### 3. Configuration Not Applying
**Check:**
- config.json syntax (valid JSON)
- ChoicesType format (v2.2.2+)
- File permissions

**Debug:**
```python
from modules.config_helpers import get_config_value
print(get_config_value('UI_PROFILE'))
```

#### 4. Theme Issues
**Check:**
- QGIS theme detection
- QSS file availability
- Theme source setting

**Debug:**
```python
from modules.ui_styles import UIStyles
print(UIStyles.detect_qgis_theme())
```

---

## Reporting New Issues

### Before Reporting
1. Check CHANGELOG.md for recent fixes
2. Verify plugin version (current: 2.2.4)
3. Test with latest version
4. Check documentation

### Issue Template
```markdown
**FilterMate Version:** 2.2.4
**QGIS Version:** X.XX
**OS:** Windows/Linux/macOS
**Layer Type:** PostgreSQL/Spatialite/Shapefile/GeoPackage

**Description:**
Clear description of the issue

**Steps to Reproduce:**
1. ...
2. ...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Error Messages:**
Any error messages from QGIS console

**Screenshots:**
If applicable
```

### Where to Report
- GitHub Issues: https://github.com/sducournau/filter_mate/issues
- Include QGIS Python console output
- Attach sample data if possible (anonymized)

---

## Test Coverage for Bug Prevention

### Critical Bug Tests
- `test_spatialite_expression_quotes.py`: Field name quote preservation
- `test_color_contrast.py`: WCAG compliance
- `test_config_json_reactivity.py`: Configuration reactivity
- `test_sqlite_lock_handling.py`: Database lock handling
- `test_geometry_repair.py`: Geometry validation
- `test_filter_history.py`: Undo/redo functionality

### Run Regression Tests
```bash
# All regression tests
pytest tests/ -v -m regression

# Critical bug fixes only
pytest tests/test_spatialite_expression_quotes.py -v
pytest tests/test_sqlite_lock_handling.py -v
pytest tests/test_filter_history.py -v
```

---

## Version History of Major Fixes

| Version | Date | Major Fix | Impact |
|---------|------|-----------|--------|
| 2.2.4 | 2025-12-08 | Spatialite quote preservation | CRITICAL: Case-sensitive fields |
| 2.2.3 | 2025-12-08 | WCAG color compliance | HIGH: Accessibility |
| 2.2.2 | 2025-12-08 | Configuration reactivity | MEDIUM: User experience |
| 2.1.0 | 2024-12 | Multi-backend system | HIGH: Performance |
| 2.1.0 | 2024-12 | SQLite lock handling | HIGH: Stability |
| 2.1.0 | 2024-12 | Filter history rewrite | MEDIUM: Undo/redo |
| 2.1.0 | 2024-12 | Field selection fix | MEDIUM: UI functionality |

---

## Prevention Strategies

### Code Review Checklist
- [ ] Test with case-sensitive field names
- [ ] Verify WCAG color contrast
- [ ] Test configuration changes
- [ ] Check SQLite lock handling
- [ ] Validate geometry operations
- [ ] Test all backends (PostgreSQL, Spatialite, OGR)
- [ ] Verify undo/redo functionality
- [ ] Check field name quote handling

### Automated Testing
- Run full test suite before each release
- Perform regression tests on critical bugs
- Validate accessibility with automated tools
- Benchmark performance on each backend

### Documentation
- Update CHANGELOG.md for each fix
- Document workarounds for limitations
- Maintain comprehensive test coverage
- Keep bug tracker up to date
