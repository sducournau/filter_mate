# FilterMate Testing

## Running Tests

### Prerequisites
```bash
pip install pytest pytest-qgis pytest-cov
```

### Run all tests
```bash
pytest tests/
```

### Run with coverage
```bash
pytest tests/ --cov=. --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_plugin_loading.py -v
```

### Run specific test
```bash
pytest tests/test_plugin_loading.py::test_plugin_module_imports -v
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                     # Pytest configuration and fixtures
├── test_plugin_loading.py          # Smoke tests
├── test_undo_redo.py               # Undo/Redo system tests
├── test_filter_preservation.py     # NEW: Filter preservation tests
├── test_backends/                  # Backend-specific tests
│   ├── test_spatialite_backend.py
│   ├── test_ogr_backend.py
│   └── test_postgresql_backend.py
├── test_filter_operations.py      # Filter logic tests
└── test_ui_components.py          # UI widget tests
```

### New Test Files

#### test_filter_preservation.py (v2.3.0+)
Tests automatic filter preservation functionality:
- Default AND operator when no operator specified
- Explicit OR and AND NOT operators
- Filter preservation on layer switch
- Multi-layer filter preservation
- Complex WHERE clause handling

## Writing Tests

### Example Test
```python
def test_something():
    """Test description."""
    from module import function
    
    result = function(input_data)
    
    assert result == expected_value
```

### Using Fixtures
```python
def test_with_mock_layer(mock_qgs_project):
    """Test using project fixture."""
    layer = mock_qgs_project.mapLayers()
    assert layer is not None
```

## Test Coverage Goals

- Phase 1: 30% coverage (core functionality)
- Phase 2: 50% coverage (most features)
- Final: 70%+ coverage (comprehensive)

## CI/CD Integration

Tests run automatically on:
- Every commit to main
- Every pull request
- Before releases

See `.github/workflows/test.yml` for CI configuration.
