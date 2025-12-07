# Testing & Quality Assurance - FilterMate v2.1.0

## Test Structure

```
tests/
├── conftest.py                      # Pytest configuration and fixtures
├── README.md                        # Testing documentation
├── requirements-test.txt            # Test dependencies
├── benchmark_simple.py              # Interactive performance demos
├── test_appUtils.py                 # Utility function tests
├── test_backends.py                 # Backend system tests
├── test_buffer_error_handling.py    # Buffer operation tests
├── test_buffer_type.py              # Buffer type validation
├── test_constants.py                # Constants validation
├── test_feedback_utils.py           # User feedback tests
├── test_filter_history.py           # Filter history tests
├── test_filter_history_integration.py # History integration tests
├── test_geometry_repair.py          # Geometry repair tests
├── test_geopackage_detection.py     # GeoPackage detection tests
├── test_performance.py              # Performance optimization tests
├── test_prepared_statements.py      # SQL prepared statements tests
└── test_qt_json_view_themes.py      # JSON view theme tests
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

**Run Command:**
```bash
pytest tests/test_backends.py -v
```

### 3. Performance Tests

**Purpose:** Validate optimizations and measure improvements

**File:** `test_performance.py` (450 lines)

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

### 4. Interactive Benchmarks

**Purpose:** Visual demonstration of performance improvements

**File:** `benchmark_simple.py` (350 lines)

**Features:**
- Before/after comparisons
- Real-time measurements
- Interactive demos
- Progress visualization

**Run Command:**
```bash
python tests/benchmark_simple.py
```

### 5. Integration Tests

**Purpose:** Test multi-component interactions

**Files:**
- `test_filter_history_integration.py`
- Tests across multiple backends
- Multi-layer filtering operations

**Run Command:**
```bash
pytest tests/test_filter_history_integration.py -v
```

## Test Fixtures (conftest.py)

### Available Fixtures

1. **`qgis_app`**: QGIS application instance
2. **`temp_spatialite_db`**: Temporary Spatialite database
3. **`temp_geopackage`**: Temporary GeoPackage file
4. **`mock_layer`**: Mock QGIS vector layer
5. **`sample_geometries`**: Test geometry objects
6. **`postgresql_available`**: Check if PostgreSQL backend available

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
```

### Performance Tests Only
```bash
pytest tests/test_performance.py -v -m performance
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

## Test Coverage Report

### Current Coverage
- Backends: ~85%
- Utility functions: ~90%
- Filter history: ~80%
- Geometry operations: ~75%

### Generate Report
```bash
pytest tests/ --cov=modules --cov-report=html
# Open htmlcov/index.html in browser
```

## Known Test Limitations

### 1. PostgreSQL Tests
- Require PostgreSQL server running
- Require psycopg2 installed
- Skipped automatically if not available

### 2. QGIS Integration Tests
- Require QGIS environment
- May need X11 display (Linux)
- Use `QgsApplication.setPrefixPath()` in CI

### 3. Performance Tests
- Results vary by hardware
- Use relative comparisons (before/after)
- May be marked as "slow"

## Manual Testing

### Testing Checklist
See `.github/copilot-instructions.md` for comprehensive manual testing checklist:

1. Test without psycopg2 installed
2. Test with Shapefile/GeoPackage
3. Test with PostgreSQL (if available)
4. Test with large datasets (performance)
5. Verify error messages are clear
6. Test UI themes and dimensions
7. Test filter history undo/redo
8. Test geometric filtering with all predicates
9. Test buffer operations

## Regression Tests

### Critical Functionality
Tests ensure no regression on:
- Undo/redo functionality
- Field selection (including "id" fields)
- SQLite lock handling
- Geometry repair
- Backend selection
- Predicate ordering

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

## CI/CD Integration

### GitHub Actions (if configured)
```yaml
- name: Run tests
  run: pytest tests/ -v --cov=modules
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
5. Update this documentation

### Updating Tests
- Keep tests in sync with code changes
- Update expected results if behavior changes intentionally
- Document breaking changes in test comments
- Maintain backwards compatibility where possible

## Documentation

### Test Documentation Files
- `tests/README.md`: General testing guide
- `.github/copilot-instructions.md`: Manual testing checklist
- `docs/DEVELOPER_ONBOARDING.md`: Developer setup including testing

## Future Testing Goals

### Planned Improvements
- Increase coverage to 90%+
- Add UI automation tests (pytest-qt)
- Performance regression tracking
- Load testing for very large datasets
- Multi-platform testing (Windows/Linux/macOS)
