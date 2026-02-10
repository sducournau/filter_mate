# -*- coding: utf-8 -*-
"""
FilterMate Base Task - ARCH-046

Abstract base class for all FilterMate QGIS tasks.
Provides common functionality for progress, cancellation, and error handling.

Part of Phase 4 Task Refactoring.

Features:
- Structured progress reporting
- Cancellation handling
- Error handling and logging
- Result packaging

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from abc import abstractmethod
from typing import Optional, Any, Callable, Dict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger('FilterMate.Tasks.Base')


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TaskResult:
    """
    Result from task execution.

    Attributes:
        success: Whether task completed successfully
        status: Final task status
        data: Optional result data
        error_message: Error message if failed
        execution_time_ms: Total execution time
        metrics: Optional metrics dict
    """
    success: bool
    status: TaskStatus
    data: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        data: Any = None,
        execution_time_ms: float = 0.0,
        metrics: Optional[Dict[str, Any]] = None
    ) -> 'TaskResult':
        """Create successful result."""
        return cls(
            success=True,
            status=TaskStatus.COMPLETED,
            data=data,
            execution_time_ms=execution_time_ms,
            metrics=metrics or {}
        )

    @classmethod
    def error_result(
        cls,
        error_message: str,
        execution_time_ms: float = 0.0
    ) -> 'TaskResult':
        """Create error result."""
        return cls(
            success=False,
            status=TaskStatus.FAILED,
            error_message=error_message,
            execution_time_ms=execution_time_ms
        )

    @classmethod
    def cancelled_result(cls) -> 'TaskResult':
        """Create cancelled result."""
        return cls(
            success=False,
            status=TaskStatus.CANCELLED
        )


# Import QgsTask only when needed to avoid import errors outside QGIS
def _get_qgs_task_base():
    """Get QgsTask base class, with fallback for testing."""
    try:
        from qgis.core import QgsTask
        return QgsTask
    except ImportError:
        # Fallback for testing outside QGIS
        class MockQgsTask:
            """Mock QgsTask for testing."""
            CanCancel = 1

            def __init__(self, description, flags=0):
                self._description = description
                self._progress = 0
                self._cancelled = False

            def description(self):
                return self._description

            def setProgress(self, progress):
                self._progress = progress

            def isCanceled(self):
                return self._cancelled

            def cancel(self):
                self._cancelled = True

        return MockQgsTask


class BaseFilterMateTask(_get_qgs_task_base()):
    """
    Abstract base class for FilterMate tasks.

    Provides:
    - Structured progress reporting
    - Cancellation handling
    - Error handling and logging
    - Result packaging

    Subclasses must implement:
    - _execute(): Main task logic
    - _on_completed(): Success handler (optional)
    - _on_failed(): Error handler (optional)

    Example:
        class MyTask(BaseFilterMateTask):
            def _execute(self):
                for i in range(100):
                    if self.check_cancelled():
                        return TaskResult.cancelled_result()
                    self.report_progress(i, 100, f"Step {i}")
                return TaskResult.success_result(data=result)
    """

    def __init__(
        self,
        description: str,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize task.

        Args:
            description: Task description for UI
            on_complete: Callback for successful completion
            on_error: Callback for errors
            on_progress: Callback for progress updates
        """
        try:
            from qgis.core import QgsTask
            super().__init__(description, QgsTask.CanCancel)
        except ImportError:
            super().__init__(description, 1)

        self._on_complete_callback = on_complete
        self._on_error_callback = on_error
        self._on_progress_callback = on_progress
        self._result: Optional[TaskResult] = None
        self._start_time: Optional[float] = None
        self._status = TaskStatus.PENDING
        self._current_step = ""

    def run(self) -> bool:
        """
        Execute the task (called by QGIS task manager).

        Returns:
            True if task completed successfully
        """
        self._status = TaskStatus.RUNNING
        self._start_time = time.time()

        try:
            logger.info(f"Starting task: {self.description()}")

            self._result = self._execute()

            # Calculate execution time
            if self._result and self._start_time:
                self._result.execution_time_ms = (time.time() - self._start_time) * 1000

            if self._result and self._result.success:
                self._status = TaskStatus.COMPLETED
                return True
            else:
                self._status = self._result.status if self._result else TaskStatus.FAILED
                return False

        except Exception as e:
            logger.exception(f"Task failed with exception: {e}")
            self._status = TaskStatus.FAILED
            execution_time = (time.time() - self._start_time) * 1000 if self._start_time else 0
            self._result = TaskResult.error_result(
                error_message=str(e),
                execution_time_ms=execution_time
            )
            return False

    def finished(self, result: bool) -> None:
        """
        Called when task finishes (success or failure).

        Args:
            result: True if run() returned True
        """
        if result:
            logger.info(
                f"Task completed: {self.description()} "
                f"in {self._result.execution_time_ms:.1f}ms"
            )
            self._on_completed(self._result)
            if self._on_complete_callback:
                try:
                    self._on_complete_callback(self._result)
                except Exception as e:
                    logger.error(f"Error in complete callback: {e}")
        else:
            logger.warning(f"Task failed: {self.description()}")
            self._on_failed(self._result)
            if self._on_error_callback:
                try:
                    self._on_error_callback(self._result)
                except Exception as e:
                    logger.error(f"Error in error callback: {e}")

    @abstractmethod
    def _execute(self) -> TaskResult:
        """
        Execute the main task logic.

        Must be implemented by subclasses.

        Returns:
            TaskResult with success/failure and data
        """

    def _on_completed(self, result: TaskResult) -> None:
        """
        Handle successful completion.

        Override for custom success handling.
        """

    def _on_failed(self, result: TaskResult) -> None:
        """
        Handle task failure.

        Override for custom error handling.
        """

    def report_progress(
        self,
        current: int,
        total: int,
        message: Optional[str] = None
    ) -> None:
        """
        Report progress to QGIS task manager.

        Args:
            current: Current step
            total: Total steps
            message: Optional progress message
        """
        if total > 0:
            progress = int((current / total) * 100)
            self.setProgress(progress)

        if message:
            self._current_step = message
            logger.debug(f"Task progress: {message}")

        if self._on_progress_callback:
            try:
                progress_pct = int((current / total) * 100) if total > 0 else 0
                self._on_progress_callback(progress_pct, message or "")
            except Exception as e:
                logger.debug(f"Ignored in progress callback: {e}")

    def check_cancelled(self) -> bool:
        """
        Check if task was cancelled and update status.

        Returns:
            True if cancelled
        """
        if self.isCanceled():
            self._status = TaskStatus.CANCELLED
            return True
        return False

    @property
    def status(self) -> TaskStatus:
        """Get current task status."""
        return self._status

    @property
    def result(self) -> Optional[TaskResult]:
        """Get task result (available after completion)."""
        return self._result

    @property
    def current_step(self) -> str:
        """Get current step description."""
        return self._current_step

    @property
    def elapsed_time_ms(self) -> float:
        """Get elapsed time since start."""
        if self._start_time:
            return (time.time() - self._start_time) * 1000
        return 0.0
