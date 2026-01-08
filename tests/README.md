# FilterMate Testing

## Overview

FilterMate v3.0 uses a comprehensive testing strategy with unit tests,
integration tests, end-to-end tests, and performance benchmarks.

## Running Tests

### Prerequisites

```bash
pip install pytest pytest-qgis pytest-cov pytest-benchmark
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

### Run by marker

```bash
# Run only unit tests
pytest tests/ -m "not integration and not e2e"

# Run integration tests
pytest tests/ -m integration

# Run end-to-end tests
pytest tests/ -m e2e

# Run backend-specific tests
pytest tests/ -m postgresql
pytest tests/ -m spatialite
pytest tests/ -m ogr

# Run performance benchmarks
pytest tests/ -m benchmark --benchmark-enable

# Run regression tests
pytest tests/ -m regression
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                       # Root pytest configuration
├── README.md                         # This file
│
├── core/                             # Core domain/service tests
│   └── ...
│
├── integration/                      # Integration tests (Phase 5)
│   ├── __init__.py
│   ├── conftest.py                   # Integration test fixtures
│   ├── fixtures/                     # Test factories
│   │   └── __init__.py               # LayerFactory, BackendFactory
│   ├── utils/                        # Testing utilities
│   │   ├── __init__.py
│   │   ├── signal_spy.py             # Qt signal verification
│   │   └── assertions.py             # Custom assertions
│   ├── workflows/                    # E2E workflow tests
│   │   └── __init__.py
│   └── test_phase2_integration.py    # Controller integration tests
│
├── test_backends/                    # Backend-specific tests
│   ├── test_spatialite_backend.py
│   ├── test_ogr_backend.py
│   └── test_postgresql_backend.py
│
├── test_plugin_loading.py            # Smoke tests
├── test_undo_redo.py                 # Undo/Redo system tests
├── test_filter_preservation.py       # Filter preservation tests
├── test_controller_*.py              # Controller tests
└── test_*.py                         # Other tests
```

## Test Categories

### Unit Tests

Fast, isolated tests for individual components.

```bash
pytest tests/ -m "not integration and not e2e and not benchmark"
```

### Integration Tests

Tests for component interactions and data flow.

```bash
pytest tests/integration/ -v
```

### End-to-End (E2E) Tests

Complete workflow tests from user action to result.

```bash
pytest tests/integration/workflows/ -m e2e -v
```

### Performance Benchmarks

Measure execution time and detect regressions.

```bash
pytest tests/ -m benchmark --benchmark-enable --benchmark-autosave
```

## Test Markers

| Marker        | Description                      |
| ------------- | -------------------------------- |
| `integration` | Integration test                 |
| `e2e`         | End-to-end workflow test         |
| `postgresql`  | Requires PostgreSQL backend      |
| `spatialite`  | Requires Spatialite backend      |
| `ogr`         | OGR/GDAL backend test            |
| `benchmark`   | Performance benchmark            |
| `regression`  | Regression test for known issues |
| `slow`        | Slow-running test                |

## Test Fixtures

### From `conftest.py` (Root)

- `mock_iface` - Mock QGIS interface
- `mock_qgs_project` - Mock QGIS project
- `sample_layer_metadata` - Sample layer metadata dict
- `sample_filter_params` - Sample filter parameters dict

### From `integration/conftest.py`

- `mock_qgis_interface` - Enhanced mock QGIS interface
- `mock_postgresql_backend` - Mock PostgreSQL backend
- `mock_spatialite_backend` - Mock Spatialite backend
- `mock_ogr_backend` - Mock OGR backend
- `all_mock_backends` - Dictionary of all backend mocks
- `sample_vector_layer` - Sample vector layer mock
- `postgresql_layer` - PostgreSQL layer mock
- `spatialite_layer` - Spatialite layer mock
- `multiple_layers` - Multiple layer mocks
- `test_expressions` - Various test expressions
- `mock_filter_service` - Mock filter service

### From `integration/fixtures/__init__.py`

- `layer_factory` - LayerFactory class
- `backend_factory` - BackendFactory class
- `create_test_layer` - Factory function for layers
- `generate_test_layers` - Generate multiple layers

## Custom Assertions

Import from `tests.integration.utils`:

```python
from tests.integration.utils import (
    assert_filter_result_success,
    assert_filter_result_failure,
    assert_layer_subset_string,
    assert_backend_used,
    assert_optimization_used,
    assert_feature_ids_equal,
    assert_execution_time_within,
    assert_signal_emitted
)
```

## Signal Testing

Use `SignalSpy` for Qt signal verification:

```python
from tests.integration.utils import SignalSpy

def test_signal_emission(widget):
    spy = SignalSpy(widget.valueChanged)
    widget.setValue(10)
    assert spy.count == 1
    assert spy.last_args == (10,)
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
