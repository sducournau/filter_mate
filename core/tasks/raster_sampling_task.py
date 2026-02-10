"""
RasterSamplingTask - Asynchronous raster value sampling for vector features.

QgsTask that samples raster values at vector feature locations in a background
thread. Uses URI-based layer construction for thread safety.

Phase 1: Point-based sampling (centroid / pointOnSurface).
Phase 3+: Mean-under-polygon via QgsZonalStatistics.

Thread Safety Contract:
    - Layer URIs are stored in __init__ (main thread)
    - Layers are recreated from URIs in run() (worker thread)
    - Results are communicated via QObject-based signals (thread-safe)
    - NO QgsMapLayer objects cross thread boundaries

Usage:
    from ...core.tasks.raster_sampling_task import RasterSamplingTask

    task = RasterSamplingTask(
        raster_uri="/path/to/dem.tif",
        vector_uri="/path/to/parcels.gpkg",
        band=1,
        method="point_on_surface",
    )
    task.signals.completed.connect(on_sampling_complete)
    task.signals.error.connect(on_sampling_error)
    QgsApplication.taskManager().addTask(task)
"""
import time
import logging
from typing import Dict, Optional

from qgis.core import QgsTask, QgsFeedback
from qgis.PyQt.QtCore import pyqtSignal, QObject

from ...core.domain.raster_filter_criteria import (
    ComparisonOperator,
    RasterSamplingCriteria,
    RasterSamplingResult,
    SamplingStats,
)

logger = logging.getLogger(__name__)


class RasterSamplingSignals(QObject):
    """Signals for RasterSamplingTask thread-safe communication.

    Using QObject-based signals (not task signals) for reliable
    cross-thread delivery following the ExpressionEvaluationSignals pattern.
    """
    # Emitted on successful completion
    # Args: (result: RasterSamplingResult, task_id: str)
    completed = pyqtSignal(object, str)

    # Emitted on error
    # Args: (error_message: str, task_id: str)
    error = pyqtSignal(str, str)

    # Emitted during sampling progress
    # Args: (processed: int, total: int)
    progress_updated = pyqtSignal(int, int)


class RasterSamplingTask(QgsTask):
    """QgsTask for sampling raster values at vector feature locations.

    Runs in a QGIS background thread. Creates disposable layer instances
    from URIs to ensure thread safety.

    Args:
        raster_uri: URI/path of the raster layer to sample.
        vector_uri: URI/path of the vector layer with feature geometries.
        band: 1-based band number (default 1).
        method: Sampling method string ("centroid", "point_on_surface").
        operator: ComparisonOperator for filtering (default GREATER_EQUAL).
        threshold: Primary threshold value (default 0.0).
        threshold_max: Upper bound for BETWEEN operator.
        description: Task description shown in QGIS task manager.

    Example:
        task = RasterSamplingTask(
            raster_uri="/data/mnt_ign_75m.tif",
            vector_uri="/data/communes.gpkg",
            band=1,
            method="point_on_surface",
            operator=ComparisonOperator.GREATER_EQUAL,
            threshold=500.0,
        )
        task.signals.completed.connect(handle_result)
        QgsApplication.taskManager().addTask(task)
    """

    # Progress reporting batch size (avoid flooding UI thread)
    PROGRESS_BATCH_SIZE = 50

    def __init__(
        self,
        raster_uri: str,
        vector_uri: str,
        band: int = 1,
        method: str = "point_on_surface",
        operator: ComparisonOperator = ComparisonOperator.GREATER_EQUAL,
        threshold: float = 0.0,
        threshold_max: Optional[float] = None,
        description: str = "Raster Sampling",
    ):
        super().__init__(description, QgsTask.CanCancel)

        # Store URIs (NOT layer objects) for thread safety
        self._raster_uri = raster_uri
        self._vector_uri = vector_uri
        self._band = band
        self._method = method
        self._operator = operator
        self._threshold = threshold
        self._threshold_max = threshold_max

        # Unique task identifier
        self._task_id = f"raster_sampling_{id(self)}"

        # Thread-safe signals
        self.signals = RasterSamplingSignals()

        # Result storage
        self._result: Optional[RasterSamplingResult] = None
        self._exception: Optional[Exception] = None

        # Performance tracking
        self._start_time: float = 0.0

    @property
    def task_id(self) -> str:
        """Unique identifier for this task instance."""
        return self._task_id

    def run(self) -> bool:
        """Execute raster sampling in background thread.

        Creates layers from URIs, samples raster values at feature locations,
        applies filter criteria, and stores results.

        Returns:
            True on success, False on failure.
        """
        self._start_time = time.time()

        try:
            # Import sampling functions (deferred to avoid import issues)
            from ...infrastructure.raster.sampling import sample_raster_for_features

            logger.info(
                f"RasterSamplingTask starting: band={self._band}, "
                f"method={self._method}, operator={self._operator.symbol}, "
                f"threshold={self._threshold}"
            )

            # -- 1. Create feedback for cancellation --
            feedback = QgsFeedback()

            # -- 2. Sample raster values --
            feature_values = sample_raster_for_features(
                raster_uri=self._raster_uri,
                vector_uri=self._vector_uri,
                band=self._band,
                method=self._method,
                feedback=feedback,
            )

            # Check cancellation after sampling
            if self.isCanceled():
                logger.info("RasterSamplingTask cancelled after sampling")
                return False

            # -- 3. Apply filter criteria --
            total_features = len(feature_values)
            sampled_count = 0
            nodata_count = 0
            matching_ids = []
            valid_values = []

            processed = 0
            for fid, value in feature_values.items():
                if self.isCanceled():
                    return False

                if value is None:
                    nodata_count += 1
                else:
                    sampled_count += 1
                    valid_values.append(value)

                    # Apply comparison operator
                    if self._operator.evaluate(
                        value, self._threshold, self._threshold_max
                    ):
                        matching_ids.append(fid)

                processed += 1
                if processed % self.PROGRESS_BATCH_SIZE == 0:
                    self.signals.progress_updated.emit(processed, total_features)
                    # Also update QGIS task manager progress bar
                    if total_features > 0:
                        self.setProgress((processed / total_features) * 100)

            # -- 4. Compute statistics --
            stats = SamplingStats.from_values(valid_values)

            # -- 5. Build result --
            self._result = RasterSamplingResult(
                feature_values=feature_values,
                matching_ids=matching_ids,
                total_features=total_features,
                sampled_count=sampled_count,
                nodata_count=nodata_count,
                stats=stats,
            )

            elapsed = time.time() - self._start_time
            logger.info(
                f"RasterSamplingTask complete in {elapsed:.2f}s: "
                f"{self._result.summary()}"
            )
            return True

        except Exception as e:
            self._exception = e
            logger.error(f"RasterSamplingTask failed: {e}", exc_info=True)
            return False

    def finished(self, result: bool) -> None:
        """Called in main thread after run() completes.

        Emits appropriate signal based on success/failure.

        Args:
            result: True if run() returned True, False otherwise.
        """
        if self.isCanceled():
            logger.info(f"RasterSamplingTask {self._task_id} was cancelled")
            return

        if result and self._result is not None:
            self.signals.completed.emit(self._result, self._task_id)
        else:
            error_msg = str(self._exception) if self._exception else "Unknown error"
            self.signals.error.emit(error_msg, self._task_id)

    def cancel(self) -> None:
        """Handle task cancellation.

        Uses Python logger (not QgsMessageLog) for thread safety during shutdown.
        """
        logger.info(f"RasterSamplingTask {self._task_id} cancellation requested")
        super().cancel()
