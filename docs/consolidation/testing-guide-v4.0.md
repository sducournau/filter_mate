# FilterMate v4.0 - Testing Guide

**Version**: 4.0  
**Date**: 2026-01-10  
**Phase**: 4 - Testing & Validation  
**Status**: Draft (to be completed in Phase 4)

---

## 🎯 Overview

This guide provides comprehensive testing strategies for FilterMate v4.0's **Layered Hybrid Architecture** (v3.x MVC Controllers + v4.x Hexagonal Services).

**Testing Objectives**:

- ✅ 80% code coverage for hexagonal services
- ✅ 70% code coverage for UI controllers
- ✅ Critical workflows covered by E2E tests
- ✅ Production-ready quality before fallback removal

---

## 📋 Test Strategy

### Test Pyramid

```
           ┌─────────────┐
           │  E2E Tests  │  10% - Critical workflows
           │   (Slow)    │
           └─────────────┘
         ┌─────────────────┐
         │Integration Tests│  30% - Controllers + Services
         │    (Medium)     │
         └─────────────────┘
    ┌──────────────────────────┐
    │     Unit Tests           │  60% - Services, utilities
    │      (Fast)              │
    └──────────────────────────┘
```

### Coverage Targets by Layer

| Layer                  | Target Coverage | Priority    | Estimated Time |
| ---------------------- | --------------- | ----------- | -------------- |
| **Hexagonal Services** | 80%             | 🔴 Critical | 6h             |
| **UI Controllers**     | 70%             | 🟠 High     | 3h             |
| **E2E Workflows**      | Critical paths  | 🟡 Medium   | 1h             |
| **Total**              | -               | -           | **10h**        |

---

## 🧪 Test Infrastructure

### Directory Structure

```
tests/
├── unit/                       # Unit tests (fast)
│   ├── services/
│   │   ├── test_layer_lifecycle_service.py
│   │   ├── test_task_management_service.py
│   │   └── test_filter_service.py
│   ├── adapters/
│   │   └── test_task_builder.py
│   └── utils/
│       └── test_helpers.py
│
├── integration/                # Integration tests (medium)
│   ├── controllers/
│   │   ├── test_filtering_controller.py
│   │   ├── test_exploring_controller.py
│   │   └── test_controller_integration.py
│   └── services/
│       └── test_service_delegation.py
│
├── e2e/                        # End-to-end tests (slow)
│   ├── test_filter_workflow.py
│   ├── test_explore_workflow.py
│   └── test_export_workflow.py
│
├── fixtures/                   # Reusable test data
│   ├── qgis_fixtures.py       # QGIS mocks
│   ├── layer_fixtures.py      # Test layers
│   └── data/                  # Test datasets
│
├── mocks/                      # Mock objects
│   ├── qgis_mocks.py          # QgsVectorLayer, etc.
│   └── service_mocks.py       # Service stubs
│
└── conftest.py                 # pytest configuration
```

---

## 🔧 Test Setup

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Contents of requirements-test.txt:
# pytest>=7.0.0
# pytest-cov>=4.0.0
# pytest-qgis>=1.0.0  # QGIS testing utilities
# pytest-mock>=3.0.0
# coverage>=7.0.0
```

### pytest Configuration

**File**: `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --cov=.
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=70
    --strict-markers
markers =
    unit: Unit tests (fast)
    integration: Integration tests (medium)
    e2e: End-to-end tests (slow)
    qgis: Requires QGIS environment
    postgres: Requires PostgreSQL
```

### conftest.py

**File**: `tests/conftest.py`

```python
"""
pytest configuration and global fixtures.
"""
import pytest
from unittest.mock import Mock, MagicMock
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.testing import start_app, stop_app


@pytest.fixture(scope="session")
def qgis_app():
    """Initialize QGIS application for testing."""
    app = start_app()
    yield app
    stop_app()


@pytest.fixture
def qgis_project():
    """Clean QgsProject instance for each test."""
    project = QgsProject.instance()
    project.clear()
    yield project
    project.clear()


@pytest.fixture
def mock_iface():
    """Mock QGIS interface."""
    iface = Mock()
    iface.messageBar.return_value = Mock()
    iface.mapCanvas.return_value = Mock()
    return iface


@pytest.fixture
def sample_layer():
    """Create a sample vector layer for testing."""
    layer = QgsVectorLayer("Point?crs=epsg:4326", "test_layer", "memory")
    return layer


# Add more fixtures as needed...
```

---

## 📝 Unit Tests (Services)

### Example: LayerLifecycleService Tests

**File**: `tests/unit/services/test_layer_lifecycle_service.py`

```python
"""
Unit tests for LayerLifecycleService.

Target: 80% coverage for all 7 methods.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.services.layer_lifecycle_service import LayerLifecycleService
from qgis.core import QgsVectorLayer, QgsProject


class TestLayerLifecycleService:
    """Tests for LayerLifecycleService."""

    @pytest.fixture
    def service(self, mock_iface):
        """Create service instance."""
        return LayerLifecycleService(
            iface=mock_iface,
            project=QgsProject.instance(),
            logger=Mock()
        )

    # === filter_usable_layers() tests ===

    def test_filter_usable_layers_valid_layers_only(self, service):
        """Should return only valid vector layers."""
        # Arrange
        valid_layer = Mock(spec=QgsVectorLayer)
        valid_layer.isValid.return_value = True
        valid_layer.providerType.return_value = 'postgres'

        invalid_layer = Mock(spec=QgsVectorLayer)
        invalid_layer.isValid.return_value = False

        layers = [valid_layer, invalid_layer]

        # Act
        result = service.filter_usable_layers(layers)

        # Assert
        assert len(result) == 1
        assert result[0] == valid_layer

    def test_filter_usable_layers_excludes_unsupported_providers(self, service):
        """Should exclude layers with unsupported provider types."""
        # Arrange
        postgres_layer = Mock(spec=QgsVectorLayer)
        postgres_layer.isValid.return_value = True
        postgres_layer.providerType.return_value = 'postgres'

        wms_layer = Mock(spec=QgsVectorLayer)
        wms_layer.isValid.return_value = True
        wms_layer.providerType.return_value = 'wms'

        layers = [postgres_layer, wms_layer]

        # Act
        result = service.filter_usable_layers(layers)

        # Assert
        assert len(result) == 1
        assert result[0] == postgres_layer

    def test_filter_usable_layers_defaults_to_project_layers(self, service, qgis_project):
        """Should use project layers when no layers provided."""
        # Arrange
        with patch.object(QgsProject, 'instance') as mock_project:
            mock_layer = Mock(spec=QgsVectorLayer)
            mock_layer.isValid.return_value = True
            mock_layer.providerType.return_value = 'postgres'
            mock_project.return_value.mapLayers.return_value.values.return_value = [mock_layer]

            # Act
            result = service.filter_usable_layers()

            # Assert
            assert len(result) == 1
            assert result[0] == mock_layer

    # === cleanup_postgresql_session_views() tests ===

    @pytest.mark.postgres
    def test_cleanup_postgresql_session_views_success(self, service):
        """Should cleanup PostgreSQL views successfully."""
        # Arrange
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.dataProvider.return_value.uri.return_value = Mock()

        with patch('modules.appUtils.get_datasource_connexion_from_layer') as mock_conn:
            mock_conn.return_value = (Mock(), Mock())

            # Act
            result = service.cleanup_postgresql_session_views(mock_layer)

            # Assert
            assert result is True

    def test_cleanup_postgresql_session_views_non_postgres(self, service):
        """Should skip cleanup for non-PostgreSQL layers."""
        # Arrange
        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.providerType.return_value = 'spatialite'

        # Act
        result = service.cleanup_postgresql_session_views(mock_layer)

        # Assert
        assert result is False

    # === cleanup() tests ===

    def test_cleanup_removes_all_layers(self, service, qgis_project):
        """Should remove all layers during cleanup."""
        # Arrange
        mock_layer1 = Mock(spec=QgsVectorLayer)
        mock_layer1.id.return_value = 'layer1'
        mock_layer2 = Mock(spec=QgsVectorLayer)
        mock_layer2.id.return_value = 'layer2'

        with patch.object(QgsProject, 'instance') as mock_project:
            mock_project.return_value.mapLayers.return_value.values.return_value = [
                mock_layer1, mock_layer2
            ]

            # Act
            service.cleanup()

            # Assert
            mock_project.return_value.removeMapLayer.assert_called()

    # === force_reload_layers() tests ===

    def test_force_reload_layers_refreshes_all(self, service):
        """Should refresh all valid layers."""
        # TODO: Implement test
        pass

    # === handle_remove_all_layers() tests ===

    def test_handle_remove_all_layers_clears_project(self, service):
        """Should clear project when all layers removed."""
        # TODO: Implement test
        pass

    # === handle_project_initialization() tests ===

    def test_handle_project_initialization_loads_config(self, service):
        """Should load configuration on project init."""
        # TODO: Implement test
        pass

    # === handle_layers_added() tests ===

    def test_handle_layers_added_notifies_listeners(self, service):
        """Should notify listeners when layers added."""
        # Arrange
        callback = Mock()
        service.add_layers_added_listener(callback)

        mock_layer = Mock(spec=QgsVectorLayer)
        mock_layer.isValid.return_value = True
        mock_layer.providerType.return_value = 'postgres'

        # Act
        service.handle_layers_added([mock_layer])

        # Assert
        callback.assert_called_once()


# Run with: pytest tests/unit/services/test_layer_lifecycle_service.py -v
```

### Coverage Check

```bash
# Run tests with coverage report
pytest tests/unit/services/test_layer_lifecycle_service.py --cov=core/services/layer_lifecycle_service --cov-report=term-missing

# Expected output:
# Name                                         Stmts   Miss  Cover   Missing
# --------------------------------------------------------------------------
# core/services/layer_lifecycle_service.py      150     30    80%   45-52, 89-95
```

---

## 🔗 Integration Tests (Controllers)

### Example: FilteringController Tests

**File**: `tests/integration/controllers/test_filtering_controller.py`

```python
"""
Integration tests for FilteringController.

Tests interaction with services via dependency injection.
Target: 70% coverage.
"""
import pytest
from unittest.mock import Mock, patch
from ui.controllers.filtering_controller import FilteringController
from core.services.layer_lifecycle_service import LayerLifecycleService


class TestFilteringController:
    """Integration tests for FilteringController."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Mock dockwidget."""
        dockwidget = Mock()
        dockwidget.cmbComboBoxLayer = Mock()
        dockwidget.cmbPredicateType = Mock()
        return dockwidget

    @pytest.fixture
    def mock_layer_service(self):
        """Mock LayerLifecycleService."""
        service = Mock(spec=LayerLifecycleService)
        service.filter_usable_layers.return_value = []
        return service

    @pytest.fixture
    def controller(self, mock_dockwidget, mock_layer_service):
        """Create controller with mocked dependencies."""
        return FilteringController(
            dockwidget=mock_dockwidget,
            filter_service=Mock(),
            layer_lifecycle_service=mock_layer_service
        )

    def test_populate_layers_calls_service(self, controller, mock_layer_service):
        """Should delegate layer population to service."""
        # Arrange
        mock_layer1 = Mock()
        mock_layer1.name.return_value = "Layer 1"
        mock_layer_service.filter_usable_layers.return_value = [mock_layer1]

        # Act
        controller._populate_layers()

        # Assert
        mock_layer_service.filter_usable_layers.assert_called_once()
        controller.dockwidget.cmbComboBoxLayer.addItem.assert_called()

    def test_setup_connects_signals(self, controller):
        """Should connect all signals during setup."""
        # Act
        controller.setup()

        # Assert
        # Verify signal connections (implementation-specific)
        assert controller._is_setup is True

    # TODO: Add more integration tests...


# Run with: pytest tests/integration/controllers/ -v
```

---

## 🌐 E2E Tests (Workflows)

### Example: Filter Workflow Test

**File**: `tests/e2e/test_filter_workflow.py`

```python
"""
End-to-end test for complete filter workflow.

Tests full user journey from UI to database.
"""
import pytest
from qgis.core import QgsProject, QgsVectorLayer


@pytest.mark.e2e
@pytest.mark.qgis
class TestFilterWorkflow:
    """E2E tests for filter workflow."""

    def test_apply_filter_complete_workflow(self, qgis_app, qgis_project):
        """
        Test complete filter workflow:
        1. Load layer
        2. Select layer in UI
        3. Set filter expression
        4. Apply filter
        5. Verify results
        """
        # TODO: Implement E2E test
        # This requires QGIS running and real plugin initialization
        pass


# Run with: pytest tests/e2e/ -v -m e2e
```

---

## 🎯 Running Tests

### Run All Tests

```bash
# Run full test suite
pytest

# With coverage report
pytest --cov=. --cov-report=html
```

### Run Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only (slow, requires QGIS)
pytest tests/e2e/ -v -m e2e
```

### Run Specific Service Tests

```bash
# LayerLifecycleService only
pytest tests/unit/services/test_layer_lifecycle_service.py -v

# With coverage
pytest tests/unit/services/test_layer_lifecycle_service.py --cov=core/services/layer_lifecycle_service --cov-report=term-missing
```

---

## 📊 Coverage Reports

### Generate HTML Report

```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View in browser
```

### Coverage by Layer

```bash
# Services only
pytest --cov=core/services --cov-report=term

# Controllers only
pytest --cov=ui/controllers --cov-report=term

# Adapters only
pytest --cov=adapters --cov-report=term
```

---

## 🚀 CI/CD Integration

### GitHub Actions Example

**File**: `.github/workflows/tests.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.9"

      - name: Install QGIS
        run: |
          # Install QGIS dependencies
          sudo apt-get update
          sudo apt-get install -y qgis python3-qgis

      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt

      - name: Run tests
        run: |
          pytest --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

## ✅ Phase 4 Checklist

### Week 1: Unit Tests (6h)

- [ ] Setup pytest infrastructure (conftest.py, fixtures)
- [ ] Write TaskParameterBuilder tests (1h)
- [ ] Write LayerLifecycleService tests (3h)
- [ ] Write TaskManagementService tests (2h)
- [ ] Verify 80% coverage for all services

### Week 2: Integration Tests (3h)

- [ ] Write FilteringController integration tests (1h)
- [ ] Write ControllerIntegration tests (1h)
- [ ] Write service delegation tests (1h)
- [ ] Verify 70% coverage for controllers

### Week 3: E2E Tests (1h)

- [ ] Write filter workflow E2E test
- [ ] Write explore workflow E2E test
- [ ] Write export workflow E2E test
- [ ] Verify critical paths covered

### Final: Documentation & CI

- [ ] Complete this testing guide
- [ ] Setup CI/CD pipeline (optional)
- [ ] Generate coverage reports
- [ ] Review with team

---

## 📚 References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-qt](https://pytest-qt.readthedocs.io/) - Qt testing
- [QGIS Testing](https://docs.qgis.org/testing/) - QGIS test utilities
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) - Mocking

---

**Status**: Draft (to be completed in Phase 4)  
**Next**: Implement tests for LayerLifecycleService  
**Last Updated**: 2026-01-10
