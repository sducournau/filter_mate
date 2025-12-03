# Task Completion Checklist

## When a coding task is completed:

### 1. Code Quality Checks
- [ ] Code follows PEP 8 conventions
- [ ] Maximum line length (120 chars) respected
- [ ] Proper naming conventions used
- [ ] Docstrings added for new classes/functions
- [ ] Comments explain why, not what
- [ ] No unused imports
- [ ] POSTGRESQL_AVAILABLE check before PostgreSQL operations

### 2. QGIS-Specific Checks
- [ ] Provider type detection correct (postgres/spatialite/ogr)
- [ ] Error messages use iface.messageBar()
- [ ] Long operations use QgsTask for async execution
- [ ] Layer changes trigger appropriate signals
- [ ] No blocking operations in main thread

### 3. Testing
- [ ] Manually test in QGIS with different data sources:
  - PostgreSQL (if available)
  - Spatialite
  - Shapefile
  - GeoPackage
- [ ] Test with small dataset (<1k features)
- [ ] Test with medium dataset (10k-100k features)
- [ ] Test with large dataset (>100k features) if PostgreSQL available
- [ ] Check QGIS Python Console for errors
- [ ] Check QGIS Log Messages panel

### 4. Performance
- [ ] No full file reads when using Serena tools
- [ ] Database connections properly closed
- [ ] Performance warnings shown for large datasets without PostgreSQL
- [ ] Async tasks used for heavy operations

### 5. Multi-Backend Support
- [ ] PostgreSQL path implemented and tested
- [ ] Spatialite fallback implemented
- [ ] OGR fallback works
- [ ] Appropriate backend selected automatically

### 6. Documentation
- [ ] README.md updated if user-facing changes
- [ ] CHANGELOG.md entry added
- [ ] .github/copilot-instructions.md updated if new patterns
- [ ] Comments added for complex logic

### 7. Git
```cmd
git status
git add .
git commit -m "feat: descriptive message following conventional commits"
git push origin main
```

### 8. Plugin Reload
- Restart QGIS or use Plugin Reloader
- Test that changes work in QGIS environment

### 9. Phase-Specific Checks

#### Phase 2 (Current - Spatialite Backend)
- [ ] Spatialite alternative to PostgreSQL function created
- [ ] Conditional logic added for provider type
- [ ] Performance comparable to PostgreSQL for small/medium datasets
- [ ] Spatial indexes created for Spatialite tables
- [ ] QGIS expression conversion to Spatialite SQL

#### Phase 3 (Future - Tests & Documentation)
- [ ] Unit tests written and passing
- [ ] Integration tests for multi-backend
- [ ] User documentation complete
- [ ] Developer documentation updated

### 10. Known Issues Check
Review and update if applicable:
- Combobox layer icons display issue
- Geometry type representation
- Any new bugs discovered during testing

## Commit Message Format
Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code restructuring
- `perf:` Performance improvement
- `style:` Code style/formatting

## Example Workflow
```cmd
# 1. Make changes
# 2. Check code quality
# 3. Test in QGIS
cd C:\Users\Simon\OneDrive\Documents\GitHub\filter_mate
git status
git add modules\appTasks.py
git add filter_mate_dockwidget.py
git commit -m "fix: correct geometry type icon display in combobox"
git push origin main
# 4. Reload plugin in QGIS and verify
```
