# -*- coding: utf-8 -*-
"""
Tests for Phase 4 Task Components

Tests for refactored task system:
- BaseFilterMateTask
- FilterTask
- SpatialTask
- ExportTask
- LayerTask

ARCH-048: Phase 4 Tests
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


# =============================================================================
# Base Task Tests
# =============================================================================

class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_statuses(self):
        """Test all status values exist."""
        from adapters.qgis.tasks.base_task import TaskStatus
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.FAILED.value == "failed"


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self):
        """Test creating success result."""
        from adapters.qgis.tasks.base_task import TaskResult, TaskStatus
        result = TaskResult.success_result(
            data={"count": 10},
            execution_time_ms=150.5
        )
        assert result.success is True
        assert result.status == TaskStatus.COMPLETED
        assert result.data == {"count": 10}
        assert result.execution_time_ms == 150.5
        assert result.error_message is None

    def test_error_result(self):
        """Test creating error result."""
        from adapters.qgis.tasks.base_task import TaskResult, TaskStatus
        result = TaskResult.error_result(
            error_message="Something went wrong",
            execution_time_ms=50.0
        )
        assert result.success is False
        assert result.status == TaskStatus.FAILED
        assert result.error_message == "Something went wrong"
        assert result.data is None

    def test_cancelled_result(self):
        """Test creating cancelled result."""
        from adapters.qgis.tasks.base_task import TaskResult, TaskStatus
        result = TaskResult.cancelled_result()
        assert result.success is False
        assert result.status == TaskStatus.CANCELLED


class TestBaseFilterMateTask:
    """Tests for BaseFilterMateTask."""

    def test_init(self):
        """Test task initialization."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskStatus

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                from adapters.qgis.tasks.base_task import TaskResult
                return TaskResult.success_result()

        task = TestTask(description="Test task")
        assert task.status == TaskStatus.PENDING
        assert task.result is None

    def test_callbacks(self):
        """Test callbacks are stored."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskResult

        on_complete = Mock()
        on_error = Mock()

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                return TaskResult.success_result()

        task = TestTask(
            description="Test task",
            on_complete=on_complete,
            on_error=on_error
        )
        assert task._on_complete_callback == on_complete
        assert task._on_error_callback == on_error

    def test_run_success(self):
        """Test successful task run."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskResult, TaskStatus

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                return TaskResult.success_result(data={"result": 42})

        task = TestTask(description="Test task")
        result = task.run()
        assert result is True
        assert task.status == TaskStatus.COMPLETED
        assert task.result.success is True
        assert task.result.data == {"result": 42}

    def test_run_failure(self):
        """Test failed task run."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskResult, TaskStatus

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                return TaskResult.error_result("Test error")

        task = TestTask(description="Test task")
        result = task.run()
        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.result.error_message == "Test error"

    def test_run_exception(self):
        """Test task that raises exception."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskStatus

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                raise ValueError("Test exception")

        task = TestTask(description="Test task")
        result = task.run()
        assert result is False
        assert task.status == TaskStatus.FAILED
        assert "Test exception" in task.result.error_message

    def test_report_progress(self):
        """Test progress reporting."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskResult

        progress_callback = Mock()

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                self.report_progress(50, 100, "Halfway")
                return TaskResult.success_result()

        task = TestTask(
            description="Test task",
            on_progress=progress_callback
        )
        task.run()
        progress_callback.assert_called_once_with(50, "Halfway")

    def test_check_cancelled(self):
        """Test cancellation check."""
        from adapters.qgis.tasks.base_task import BaseFilterMateTask, TaskResult, TaskStatus

        class TestTask(BaseFilterMateTask):
            def _execute(self):
                if self.check_cancelled():
                    return TaskResult.cancelled_result()
                return TaskResult.success_result()

        task = TestTask(description="Test task")
        # Simulate cancellation
        task._cancelled = True
        task.run()
        assert task.status == TaskStatus.CANCELLED


# =============================================================================
# Filter Task Tests
# =============================================================================

class TestFilterTask:
    """Tests for FilterTask."""

    @pytest.fixture
    def mock_expression(self):
        """Create mock filter expression."""
        expr = Mock()
        expr.raw = "field = 'value'"
        return expr

    @pytest.fixture
    def mock_layer_info(self):
        """Create mock layer info."""
        info = Mock()
        info.layer_id = "layer123"
        info.name = "Test Layer"
        return info

    def test_init(self, mock_expression, mock_layer_info):
        """Test FilterTask initialization."""
        from adapters.qgis.tasks.filter_task import FilterTask

        task = FilterTask(
            expression=mock_expression,
            source_layer_info=mock_layer_info,
            target_layer_infos=[mock_layer_info]
        )
        assert task._expression == mock_expression
        assert task._source_layer == mock_layer_info
        assert len(task._target_layers) == 1

    def test_results_property(self, mock_expression, mock_layer_info):
        """Test results property."""
        from adapters.qgis.tasks.filter_task import FilterTask

        task = FilterTask(
            expression=mock_expression,
            source_layer_info=mock_layer_info,
            target_layer_infos=[]
        )
        assert task.results == {}


class TestClearFilterTask:
    """Tests for ClearFilterTask."""

    def test_init(self):
        """Test ClearFilterTask initialization."""
        from adapters.qgis.tasks.filter_task import ClearFilterTask

        task = ClearFilterTask(layer_ids=["layer1", "layer2"])
        assert len(task._layer_ids) == 2
        assert task._cleared == 0


# =============================================================================
# Spatial Task Tests
# =============================================================================

class TestSpatialFilterTask:
    """Tests for SpatialFilterTask."""

    def test_init(self):
        """Test SpatialFilterTask initialization."""
        from adapters.qgis.tasks.spatial_task import SpatialFilterTask

        task = SpatialFilterTask(
            source_layer_id="source123",
            target_layer_ids=["target1", "target2"],
            predicate="intersects"
        )
        assert task._source_layer_id == "source123"
        assert len(task._target_layer_ids) == 2
        assert task._predicate == "intersects"

    def test_predicates(self):
        """Test spatial predicates constants."""
        from adapters.qgis.tasks.spatial_task import SpatialFilterTask

        assert SpatialFilterTask.INTERSECTS == "intersects"
        assert SpatialFilterTask.CONTAINS == "contains"
        assert SpatialFilterTask.WITHIN == "within"


class TestBufferFilterTask:
    """Tests for BufferFilterTask."""

    def test_init(self):
        """Test BufferFilterTask initialization."""
        from adapters.qgis.tasks.spatial_task import BufferFilterTask

        task = BufferFilterTask(
            source_layer_id="source123",
            target_layer_ids=["target1"],
            buffer_distance=100.0
        )
        assert task._source_layer_id == "source123"
        assert task._buffer_distance == 100.0
        assert task._buffer_segments == 8  # Default


# =============================================================================
# Export Task Tests
# =============================================================================

class TestExportTask:
    """Tests for ExportTask."""

    def test_init(self):
        """Test ExportTask initialization."""
        from adapters.qgis.tasks.export_task import ExportTask

        task = ExportTask(
            layer_id="layer123",
            output_path="/tmp/output.gpkg"
        )
        assert task._layer_id == "layer123"
        assert task._output_format == "GPKG"  # Auto-detected

    def test_format_detection(self):
        """Test format auto-detection."""
        from adapters.qgis.tasks.export_task import ExportTask

        task_gpkg = ExportTask(layer_id="layer", output_path="/tmp/out.gpkg")
        assert task_gpkg._output_format == "GPKG"

        task_shp = ExportTask(layer_id="layer", output_path="/tmp/out.shp")
        assert task_shp._output_format == "ESRI Shapefile"

        task_json = ExportTask(layer_id="layer", output_path="/tmp/out.geojson")
        assert task_json._output_format == "GeoJSON"

    def test_supported_formats(self):
        """Test supported formats dict."""
        from adapters.qgis.tasks.export_task import ExportTask

        assert '.gpkg' in ExportTask.FORMATS
        assert '.shp' in ExportTask.FORMATS
        assert '.geojson' in ExportTask.FORMATS


class TestBatchExportTask:
    """Tests for BatchExportTask."""

    def test_init(self):
        """Test BatchExportTask initialization."""
        from adapters.qgis.tasks.export_task import BatchExportTask

        exports = [
            ("layer1", "/tmp/out1.gpkg", None),
            ("layer2", "/tmp/out2.gpkg", None)
        ]
        task = BatchExportTask(exports=exports)
        assert len(task._exports) == 2
        assert task._successful == 0
        assert task._failed == 0


# =============================================================================
# Layer Task Tests
# =============================================================================

class TestGatherLayerInfoTask:
    """Tests for GatherLayerInfoTask."""

    def test_init(self):
        """Test GatherLayerInfoTask initialization."""
        from adapters.qgis.tasks.layer_task import GatherLayerInfoTask

        task = GatherLayerInfoTask(
            layer_ids=["layer1", "layer2", "layer3"],
            include_feature_count=True,
            include_extent=False
        )
        assert len(task._layer_ids) == 3
        assert task._include_feature_count is True
        assert task._include_extent is False

    def test_layer_infos_property(self):
        """Test layer_infos property."""
        from adapters.qgis.tasks.layer_task import GatherLayerInfoTask

        task = GatherLayerInfoTask(layer_ids=[])
        assert task.layer_infos == {}


class TestValidateExpressionsTask:
    """Tests for ValidateExpressionsTask."""

    def test_init(self):
        """Test ValidateExpressionsTask initialization."""
        from adapters.qgis.tasks.layer_task import ValidateExpressionsTask

        validations = [
            ("layer1", "field = 'value'"),
            ("layer2", "count > 10")
        ]
        task = ValidateExpressionsTask(validations=validations)
        assert len(task._validations) == 2


class TestCreateSpatialIndexTask:
    """Tests for CreateSpatialIndexTask."""

    def test_init(self):
        """Test CreateSpatialIndexTask initialization."""
        from adapters.qgis.tasks.layer_task import CreateSpatialIndexTask

        task = CreateSpatialIndexTask(
            layer_ids=["layer1", "layer2"]
        )
        assert len(task._layer_ids) == 2
        assert task._created == 0
        assert task._skipped == 0
        assert task._failed == 0
