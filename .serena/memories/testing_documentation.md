# Testing & Quality Assurance - FilterMate v2.4.10

**Last Updated**: December 23, 2025

## Test Structure

```
tests/
├── conftest.py                          # Pytest configuration and fixtures
├── README.md                            # Testing documentation
├── requirements-test.txt                # Test dependencies
├── benchmark_simple.py                  # Interactive performance demos
├── verify_optimizations.py              # Optimization validation
│
├── test_appUtils.py                     # Utility function tests
├── test_backends.py                     # Backend system tests
├── test_buffer_error_handling.py        # Buffer operation tests
├── test_buffer_type.py                  # Buffer type validation
├── test_choices_type_config.py          # ChoicesType configuration tests
├── test_color_contrast.py               # WCAG color contrast validation (v2.2.3)
├── test_config_json_reactivity.py       # Configuration reactivity tests (v2.2.2)
├── test_constants.py                    # Constants validation
├── test_feedback_utils.py               # User feedback tests
├── test_filter_history.py               # Filter history tests
├── test_filter_history_integration.py   # History integration tests
├── test_geometry_repair.py              # Geometry repair tests
├── test_geopackage_detection.py         # GeoPackage detection tests
├── test_layer_provider_type_migration.py # Provider type migration tests
├── test_ogr_type_handling.py            # OGR type handling tests
├── test_performance.py                  # Performance optimization tests (~450 lines)
├── test_prepared_statements.py          # SQL prepared statements tests
├── test_qt_json_view_themes.py          # JSON view theme tests
├── test_refactored_helpers_appTasks.py  # AppTasks helper tests
├── test_refactored_helpers_dockwidget.py # Dockwidget helper tests
├── test_undo_redo.py                    # Undo/redo functionality tests (NEW)
├── test_signal_type_fix.py              # Signal type fix tests
├── test_signal_utils.py                 # Signal utility tests
├── test_source_table_name.py            # Source table name tests
├── test_spatialite_expression_quotes.py # Spatialite quote handling (v2.2.4)
├── test_spatialite_temp_table_fix.py    # Spatialite temp table tests
├── test_sqlite_lock_handling.py         # SQLite lock handling tests
├── test_theme_detection.py              # Theme detection tests
├── test_ui_config.py                    # UI configuration tests
├── test_ui_config_ratios.py             # UI dimension ratio tests
├── test_ui_styles.py                    # UI styles tests
└── generate_color_preview.py            # Color preview HTML generator (v2.2.3)
```

## Test Categories

### 1. Unit Tests (pytest)

**Purpose:** Test individual functions and methods in isolation

**Coverage Areas:**
- Utility functions (`test_appUtils.py`)
- Constants and enums (`test_constants.py`)
- Buffer operations (`test_buffer_type.py`, `test_buffer_error_handling.py`)
- Geometry repair (`test_geometry_repair.py`)
- Filter history (`test_filter_history.py`)
- Prepared statements (`test_prepared_statements.py`)
- Feedback utilities (`test_feedback_utils.py`)
- Signal utilities (`test_signal_utils.py`)

**Run Command:**
```bash
pytest tests/ -v
```

### 2. Backend Tests

**Purpose:** Validate multi-backend architecture

**File:** `test_backends.py`

**Tests:**
- Backend factory pattern
- PostgreSQL backend operations (if available)
- Spatialite backend operations
- OGR backend operations
- Backend selection logic
- Fallback mechanisms
- Expression conversion (including quote preservation)

**Run Command:**
```bash
pytest tests/test_backends.py -v
```

### 3. Spatialite Expression Tests (v2.2.4)

**Purpose:** Validate expression conversion and field name handling

**File:** `test_spatialite_expression_quotes.py`

**Tests:**
- Field name quote preservation (CRITICAL)
- Case-sensitive field name handling
- Expression conversion accuracy
- Various expression types (comparison, logical, spatial)
- Edge cases and special characters

**Critical Test:**
```python
def test_field_name_quotes_preserved():
    # Ensures "HOMECOUNT" > 100 stays quoted
    # Bug fix for v2.2.4
```

**Run Command:**
```bash
pytest tests/test_spatialite_expression_quotes.py -v
```

### 4. Performance Tests

**Purpose:** Validate optimizations and measure improvements

**File:** `test_performance.py` (~450 lines)

**Tests:**
- Spatial index creation
- Geometry cache performance
- Predicate ordering optimization
- Temporary table performance
- Large dataset handling

**Expected Gains:**
- Spatialite temp table: 44.6× faster
- Geometry cache: 5.0× faster
- Predicate ordering: 2.3× faster
- OGR spatial index: 19.5× faster

**Run Command:**
```bash
pytest tests/test_performance.py -v
```

### 5. Accessibility Tests (v2.2.3)

**Purpose:** Validate WCAG 2.1 compliance

**File:** `test_color_contrast.py`

**Tests:**
- Primary text contrast ratios (≥7:1 for AAA)
- Secondary text contrast ratios (≥4.5:1 for AA)
- Disabled text contrast ratios (≥3:1 for AA Large)
- Frame/widget color separation
- Border visibility
- All theme variants (default, light, dark)

**WCAG Standards:**
- **AAA**: 7:1 contrast ratio (primary text)
- **AA**: 4.5:1 contrast ratio (normal text)
- **AA Large**: 3:1 contrast ratio (large/bold text)

**Run Command:**
```bash
pytest tests/test_color_contrast.py -v
```

**Visual Preview:**
```bash
python tests/generate_color_preview.py
# Creates docs/color_harmonization_preview.html
```

### 6. Configuration Reactivity Tests (v2.2.2)

**Purpose:** Validate real-time configuration updates

**File:** `test_config_json_reactivity.py`

**Tests:**
- ChoicesType value extraction
- Configuration validation
- UI profile switching
- Theme changes without restart
- Auto-save functionality
- Invalid value rejection

**Run Command:**
```bash
pytest tests/test_config_json_reactivity.py -v
```

### 7. Integration Tests

**Purpose:** Test multi-component interactions

**Files:**
- `test_filter_history_integration.py`
- Tests across multiple backends
- Multi-layer filtering operations
- Configuration + UI interactions

**Run Command:**
```bash
pytest tests/test_filter_history_integration.py -v
```

### 8. Interactive Benchmarks

**Purpose:** Visual demonstration of performance improvements

**File:** `benchmark_simple.py` (~350 lines)

**Features:**
- Before/after comparisons
- Real-time measurements
- Interactive demos
- Progress visualization
- Backend-specific benchmarks

**Run Command:**
```bash
python tests/benchmark_simple.py
```

## Test Fixtures (conftest.py)

### Available Fixtures

1. **`qgis_app`**: QGIS application instance
2. **`temp_spatialite_db`**: Temporary Spatialite database
3. **`temp_geopackage`**: Temporary GeoPackage file
4. **`mock_layer`**: Mock QGIS vector layer
5. **`sample_geometries`**: Test geometry objects
6. **`postgresql_available`**: Check if PostgreSQL backend available
7. **`test_config`**: Temporary configuration for testing

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Specific Test File
```bash
pytest tests/test_backends.py -v
```

### Specific Test Function
```bash
pytest tests/test_performance.py::test_spatial_index_performance -v
```

### With Coverage
```bash
pytest tests/ --cov=modules --cov-report=html
# Open htmlcov/index.html
```

### Performance Tests Only
```bash
pytest tests/test_performance.py -v -m performance
```

### Accessibility Tests Only
```bash
pytest tests/test_color_contrast.py -v
```

### Backend-Specific Tests
```bash
# PostgreSQL tests (requires psycopg2)
pytest tests/test_backends.py -v -k postgresql

# Spatialite tests
pytest tests/test_backends.py -v -k spatialite

# OGR tests
pytest tests/test_backends.py -v -k ogr
```

## Test Requirements

### Installation
```bash
pip install -r tests/requirements-test.txt
```

### Key Dependencies
- pytest
- pytest-cov
- pytest-mock
- pytest-qt
- qgis (development environment)

## Continuous Testing

### Pre-Commit Tests (Recommended)
```bash
# Run fast tests before commit
pytest tests/ -v -k "not slow"
```

### Pre-Push Tests (Recommended)
```bash
# Run all tests including slow ones
pytest tests/ -v
```

### Critical Regression Tests
```bash
# Tests for known bugs fixed in v2.2.x
pytest tests/test_spatialite_expression_quotes.py -v
pytest tests/test_color_contrast.py -v
pytest tests/test_config_json_reactivity.py -v
```

## Test Coverage Report

### Current Coverage
- Backends: ~85%
- Utility functions: ~90%
- Filter history: ~80%
- Geometry operations: ~75%
- Configuration helpers: ~85%
- UI components: ~70%

### Generate Report
```bash
pytest tests/ --cov=modules --cov-report=html
# Open htmlcov/index.html in browser
```

### Coverage by Module
```bash
pytest tests/ --cov=modules.backends --cov-report=term-missing
pytest tests/ --cov=modules.config_helpers --cov-report=term-missing
pytest tests/ --cov=modules.ui_config --cov-report=term-missing
```

## Known Test Limitations

### 1. PostgreSQL Tests
- Require PostgreSQL server running
- Require psycopg2 installed
- Skipped automatically if not available
- `@pytest.mark.skipif(not POSTGRESQL_AVAILABLE)`

### 2. QGIS Integration Tests
- Require QGIS environment
- May need X11 display (Linux)
- Use `QgsApplication.setPrefixPath()` in CI
- Some UI tests may be flaky in headless mode

### 3. Performance Tests
- Results vary by hardware
- Use relative comparisons (before/after)
- May be marked as "slow"
- Consider machine load during testing

### 4. Accessibility Tests
- Color contrast calculations are precise
- Monitor calibration doesn't affect tests
- Tests use programmatic color values

## Manual Testing

### Testing Checklist
See `.github/copilot-instructions.md` for comprehensive manual testing checklist:

1. **Backend Testing**
   - Test without psycopg2 installed
   - Test with Shapefile/GeoPackage
   - Test with PostgreSQL (if available)
   - Test with Spatialite
   - Verify backend auto-selection

2. **Performance Testing**
   - Test with large datasets (> 50k features)
   - Verify performance warnings
   - Check spatial index creation

3. **UI Testing**
   - Test all themes (default, light, dark)
   - Test UI profiles (compact, normal, auto)
   - Verify WCAG contrast in different themes
   - Test configuration changes without restart
   - Verify ChoicesType dropdowns

4. **Expression Testing** (v2.2.4 critical)
   - Test case-sensitive field names
   - Test quoted field names (e.g., "HOMECOUNT")
   - Test various expression types
   - Verify Spatialite quote preservation

5. **Error Handling**
   - Test geometry repair
   - Test SQLite lock handling
   - Verify clear error messages
   - Test cancellation

6. **Filter History**
   - Test undo/redo functionality
   - Test history persistence
   - Test multi-layer history

7. **Export Operations**
   - Test all export formats
   - Test field selection
   - Test CRS transformation

## Regression Tests

### Critical Functionality
Tests ensure no regression on:
- Undo/redo functionality
- Field selection (including "id" fields)
- SQLite lock handling
- Geometry repair
- Backend selection
- Predicate ordering
- **NEW (v2.2.4)**: Field name quote preservation
- **NEW (v2.2.3)**: WCAG color contrast
- **NEW (v2.2.2)**: Configuration reactivity

### Run Regression Suite
```bash
pytest tests/ -v -m regression
```

## Performance Benchmarks

### Quick Performance Check
```bash
python tests/benchmark_simple.py
```

### Full Performance Analysis
```bash
pytest tests/test_performance.py -v --benchmark
```

### Verify Optimizations
```bash
python tests/verify_optimizations.py
```

## CI/CD Integration

### GitHub Actions (if configured)
```yaml
- name: Run tests
  run: |
    pip install -r tests/requirements-test.txt
    pytest tests/ -v --cov=modules --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

### Local CI Simulation
```bash
# Simulate CI environment
pytest tests/ -v --strict-markers --tb=short
```

## Test Maintenance

### Adding New Tests
1. Follow existing test structure
2. Use appropriate fixtures from `conftest.py`
3. Add docstrings explaining test purpose
4. Mark slow tests with `@pytest.mark.slow`
5. Mark regression tests with `@pytest.mark.regression`
6. Update this documentation
7. Update `tests/README.md` if needed

### Updating Tests
- Keep tests in sync with code changes
- Update expected results if behavior changes intentionally
- Document breaking changes in test comments
- Maintain backwards compatibility where possible
- Add regression tests for fixed bugs

### Test Naming Convention
- `test_<feature>_<aspect>.py` for feature tests
- `test_<component>_<function>.py` for unit tests
- Use descriptive test function names
- Group related tests in classes

## Documentation

### Test Documentation Files
- `tests/README.md`: General testing guide
- `.github/copilot-instructions.md`: Manual testing checklist
- `docs/DEVELOPER_ONBOARDING.md`: Developer setup including testing
- `docs/COLOR_HARMONIZATION.md`: Accessibility testing guide

## Recent Test Additions (v2.2.x-2.3.x)

### v2.3.0-alpha (December 2025)
- ✅ `test_undo_redo.py`: Undo/redo functionality tests
- ✅ GlobalFilterState and HistoryManager tests
- ✅ Source-only vs global mode detection tests

### v2.2.4
- ✅ `test_spatialite_expression_quotes.py`: Field name quote preservation
- ✅ Comprehensive expression conversion test suite
- ✅ Case-sensitive field name handling tests

### v2.2.3
- ✅ `test_color_contrast.py`: WCAG 2.1 compliance validation
- ✅ `generate_color_preview.py`: Visual comparison tool
- ✅ Automated accessibility testing

### v2.2.2
- ✅ `test_config_json_reactivity.py`: Configuration reactivity tests
- ✅ `test_choices_type_config.py`: ChoicesType validation
- ✅ Real-time update testing

## Future Testing Goals

### Planned Improvements
- Increase coverage to 90%+ across all modules
- Add more UI automation tests (pytest-qt)
- Performance regression tracking over versions
- Load testing for very large datasets (1M+ features)
- Multi-platform testing (Windows/Linux/macOS)
- Automated accessibility audits
- Integration tests with real QGIS projects
- End-to-end workflow tests

### Testing Tools to Explore
- pytest-benchmark for detailed performance tracking
- pytest-xdist for parallel test execution
- pytest-timeout for slow test detection
- tox for multi-environment testing
