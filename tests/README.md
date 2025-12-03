# FilterMate Test Suite

Comprehensive unit tests for FilterMate plugin, targeting 80% code coverage.

## Overview

The test suite covers:
- **58 helper methods** from `modules/appTasks.py` refactoring
- **14 helper methods** from `filter_mate_dockwidget.py` refactoring  
- **New modules**: `feedback_utils.py` for user messaging

**Total Test Cases**: ~150+ tests across all modules

## Setup

### Install Test Dependencies

```bash
# From project root
pip install -r tests/requirements-test.txt
```

Or install manually:
```bash
pip install pytest pytest-cov pytest-mock pytest-qt
```

### QGIS Mocks

Tests use mocked QGIS modules (configured in `conftest.py`) so you don't need QGIS installed to run tests.

## Running Tests

### Run All Tests
```bash
# From project root
pytest tests/

# With verbose output
pytest tests/ -v

# With coverage report
pytest tests/ --cov=modules --cov-report=html
```

### Run Specific Test Files
```bash
# Test refactored appTasks helpers
pytest tests/test_refactored_helpers_appTasks.py -v

# Test refactored dockwidget helpers
pytest tests/test_refactored_helpers_dockwidget.py -v

# Test feedback utilities
pytest tests/test_feedback_utils.py -v

# Test backends
pytest tests/test_backends.py -v
```

### Run Specific Test Classes
```bash
# Test only subset string management
pytest tests/test_refactored_helpers_appTasks.py::TestManageLayerSubsetStrings -v

# Test only export functionality
pytest tests/test_refactored_helpers_appTasks.py::TestExecuteExporting -v
```

### Run with Coverage
```bash
# Generate HTML coverage report
pytest tests/ --cov=modules --cov=filter_mate_app --cov-report=html

# Open coverage report
# Windows:
start htmlcov/index.html

# Linux:
xdg-open htmlcov/index.html
```

## Test Structure

```
tests/
├── conftest.py                              # Shared fixtures and QGIS mocks
├── requirements-test.txt                    # Test dependencies
├── test_appUtils.py                         # Utility function tests
├── test_backends.py                         # Backend architecture tests
├── test_constants.py                        # Constants module tests
├── test_signal_utils.py                     # Signal utilities tests
├── test_feedback_utils.py                   # NEW: User feedback tests (100% impl)
├── test_refactored_helpers_appTasks.py      # NEW: 58 helper method tests (structure)
├── test_refactored_helpers_dockwidget.py    # NEW: 14 helper method tests (structure)
└── README.md                                # This file
```

## Coverage Goals

| Module | Target Coverage | Current Status |
|--------|-----------------|----------------|
| `modules/feedback_utils.py` | 90%+ | ✅ Tests complete |
| `modules/appTasks.py` helpers | 80%+ | 🚧 Structure ready |
| `filter_mate_dockwidget.py` helpers | 80%+ | 🚧 Structure ready |
| `modules/backends/` | 85%+ | ✅ Existing tests |
| `modules/appUtils.py` | 75%+ | ✅ Existing tests |

## Writing Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<Functionality>`
- Test methods: `test_<what_it_tests>_<scenario>`

Example:
```python
class TestBackendSelection:
    def test_determine_backend_postgresql_available(self):
        """Test PostgreSQL backend selection when available"""
        pass
    
    def test_determine_backend_spatialite_fallback(self):
        """Test Spatialite fallback when PostgreSQL unavailable"""
        pass
```

### Using Fixtures

Common fixtures are defined in `conftest.py`:

```python
def test_something(mock_qgis_iface, mock_qgis_project, sample_point_layer):
    """Test with QGIS mocks"""
    # Use mocked QGIS components
    iface = mock_qgis_iface
    project = mock_qgis_project
    layer = sample_point_layer
    
    # Your test logic here
    assert layer.featureCount() == 10
```

### Mocking Database Connections

```python
@pytest.fixture
def mock_spatialite_connection():
    """Mock Spatialite database connection"""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = (1, 'test_value')
    return conn

def test_database_query(mock_spatialite_connection):
    """Test database query execution"""
    result = mock_spatialite_connection.cursor().fetchone()
    assert result[0] == 1
```

## Continuous Integration

Tests are designed to run in CI environments without QGIS:

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r tests/requirements-test.txt
      - run: pytest tests/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Test Implementation Status

### ✅ Completed (Ready to Run)
- `test_feedback_utils.py` - 15 tests fully implemented
- Test infrastructure and fixtures in `conftest.py`

### 🚧 Structure Ready (Needs Implementation)
- `test_refactored_helpers_appTasks.py` - 58 test stubs
- `test_refactored_helpers_dockwidget.py` - 14 test stubs

These files have:
- ✅ All test method signatures defined
- ✅ Proper class organization
- ✅ Fixture setup
- ⏳ Test implementation (marked with `pass`)

**Next Steps**: Implement the test logic for each `pass` statement.

## Example: Implementing a Test

Replace `pass` with actual test logic:

**Before (stub):**
```python
def test_determine_backend_postgresql_available(self):
    """Test PostgreSQL backend selection when available"""
    pass
```

**After (implemented):**
```python
def test_determine_backend_postgresql_available(self):
    """Test PostgreSQL backend selection when available"""
    # Arrange
    task = FilterEngineTask('test', 'filter', {})
    task.param_source_provider_type = 'postgresql'
    
    # Act
    with patch('modules.appTasks.POSTGRESQL_AVAILABLE', True):
        backend = task._determine_backend()
    
    # Assert
    assert backend == 'postgresql'
```

## Troubleshooting

### Import Errors
If you see `Import "pytest" could not be resolved`:
```bash
pip install pytest pytest-cov pytest-mock
```

### QGIS Module Not Found
Tests use mocked QGIS modules. If errors persist:
1. Check `conftest.py` has all QGIS mocks
2. Ensure tests run from project root: `pytest tests/`

### Coverage Not Updating
Clear coverage cache:
```bash
rm -rf .coverage htmlcov/
pytest tests/ --cov=modules --cov-report=html
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [QGIS Testing Cookbook](https://docs.qgis.org/testing/)

## Contributing

When adding new functionality:

1. **Write tests first** (TDD approach)
2. **Run tests locally** before committing
3. **Maintain >80% coverage** for new code
4. **Update this README** if adding new test categories

---

**Last Updated**: December 3, 2025  
**Test Suite Version**: 1.0  
**Target Coverage**: 80%+
