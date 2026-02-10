# -*- coding: utf-8 -*-
"""
FilterMate Progress Handler - ARCH-047

Centralized progress reporting for FilterMate tasks.
Provides consistent progress updates across all task types.

Part of Phase 4 Task Refactoring.

Features:
- Structured progress events
- Multi-phase progress tracking
- UI integration hooks
- Logging integration

Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
from enum import Enum

logger = logging.getLogger('FilterMate.Tasks.Progress')


class ProgressPhase(Enum):
    """Standard progress phases for filter operations."""
    INITIALIZING = "initializing"
    LOADING_DATA = "loading_data"
    BUILDING_PLAN = "building_plan"
    EXECUTING_FILTER = "executing_filter"
    APPLYING_RESULT = "applying_result"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    """Progress event with detailed information."""
    phase: ProgressPhase
    percent: int  # 0-100
    message: str
    timestamp: float = field(default_factory=time.time)

    # Optional detailed info
    current_step: int = 0
    total_steps: int = 0
    items_processed: int = 0
    items_total: int = 0
    elapsed_ms: float = 0.0
    estimated_remaining_ms: float = 0.0

    # Metadata
    layer_name: Optional[str] = None
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'phase': self.phase.value,
            'percent': self.percent,
            'message': self.message,
            'timestamp': self.timestamp,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'items_processed': self.items_processed,
            'items_total': self.items_total,
            'elapsed_ms': self.elapsed_ms,
            'estimated_remaining_ms': self.estimated_remaining_ms,
            'layer_name': self.layer_name,
            'task_id': self.task_id
        }


class ProgressHandler:
    """
    Centralized progress handler for task operations.

    Provides:
    - Consistent progress calculation
    - Multi-phase tracking
    - UI callback integration
    - Progress event history

    Example:
        handler = ProgressHandler(
            task_id="filter_123",
            on_progress=update_ui_progress
        )

        handler.start_phase(ProgressPhase.LOADING_DATA)
        for i, item in enumerate(items):
            handler.update(i, len(items), f"Processing {item}")
        handler.complete_phase()
    """

    # Default phase weights (must sum to 100)
    DEFAULT_PHASE_WEIGHTS = {
        ProgressPhase.INITIALIZING: 5,
        ProgressPhase.LOADING_DATA: 15,
        ProgressPhase.BUILDING_PLAN: 10,
        ProgressPhase.EXECUTING_FILTER: 50,
        ProgressPhase.APPLYING_RESULT: 15,
        ProgressPhase.FINALIZING: 5
    }

    def __init__(
        self,
        task_id: Optional[str] = None,
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
        on_phase_change: Optional[Callable[[ProgressPhase], None]] = None,
        phase_weights: Optional[Dict[ProgressPhase, int]] = None,
        log_progress: bool = True
    ):
        """
        Initialize progress handler.

        Args:
            task_id: Optional task identifier
            on_progress: Callback for progress updates
            on_phase_change: Callback for phase transitions
            phase_weights: Custom phase weights (must sum to 100)
            log_progress: Whether to log progress events
        """
        self._task_id = task_id
        self._on_progress = on_progress
        self._on_phase_change = on_phase_change
        self._phase_weights = phase_weights or self.DEFAULT_PHASE_WEIGHTS
        self._log_progress = log_progress

        # State
        self._start_time: float = 0.0
        self._current_phase: ProgressPhase = ProgressPhase.INITIALIZING
        self._phase_start_time: float = 0.0
        self._completed_phases: List[ProgressPhase] = []
        self._history: List[ProgressEvent] = []
        self._last_percent: int = 0

    def start(self, layer_name: Optional[str] = None) -> None:
        """Start progress tracking."""
        self._start_time = time.time()
        self._layer_name = layer_name
        self._emit_event(
            ProgressPhase.INITIALIZING,
            0,
            "Starting..."
        )

    def start_phase(self, phase: ProgressPhase, message: str = "") -> None:
        """
        Start a new progress phase.

        Args:
            phase: Phase to start
            message: Optional message
        """
        if self._current_phase != phase:
            if self._current_phase not in self._completed_phases:
                self._completed_phases.append(self._current_phase)

            self._current_phase = phase
            self._phase_start_time = time.time()

            if self._on_phase_change:
                try:
                    self._on_phase_change(phase)
                except Exception:
                    pass

        base_percent = self._get_phase_start_percent(phase)
        self._emit_event(phase, base_percent, message or f"{phase.value}...")

    def update(
        self,
        current: int,
        total: int,
        message: str = "",
        items_processed: int = 0
    ) -> None:
        """
        Update progress within current phase.

        Args:
            current: Current item index (0-based)
            total: Total items
            message: Progress message
            items_processed: Optional item count for display
        """
        if total <= 0:
            return

        # Calculate percent within phase
        phase_progress = (current / total) * 100
        phase_weight = self._phase_weights.get(self._current_phase, 10)
        base_percent = self._get_phase_start_percent(self._current_phase)

        percent = int(base_percent + (phase_progress * phase_weight / 100))
        percent = min(percent, 100)

        # Only emit if percent changed significantly
        if abs(percent - self._last_percent) >= 1 or message:
            elapsed = (time.time() - self._start_time) * 1000
            estimated_remaining = 0.0

            if current > 0 and total > 0:
                rate = elapsed / current
                estimated_remaining = rate * (total - current)

            self._emit_event(
                self._current_phase,
                percent,
                message,
                current_step=current + 1,
                total_steps=total,
                items_processed=items_processed,
                elapsed_ms=elapsed,
                estimated_remaining_ms=estimated_remaining
            )
            self._last_percent = percent

    def complete_phase(self, message: str = "") -> None:
        """Complete current phase."""
        if self._current_phase not in self._completed_phases:
            self._completed_phases.append(self._current_phase)

        phase_end_percent = self._get_phase_end_percent(self._current_phase)
        self._emit_event(
            self._current_phase,
            phase_end_percent,
            message or f"{self._current_phase.value} complete"
        )

    def complete(self, message: str = "Complete") -> None:
        """Mark task as complete."""
        elapsed = (time.time() - self._start_time) * 1000
        self._emit_event(
            ProgressPhase.COMPLETE,
            100,
            message,
            elapsed_ms=elapsed
        )

    def error(self, message: str) -> None:
        """Mark task as errored."""
        elapsed = (time.time() - self._start_time) * 1000
        self._emit_event(
            ProgressPhase.ERROR,
            self._last_percent,
            f"Error: {message}",
            elapsed_ms=elapsed
        )

    def cancel(self) -> None:
        """Mark task as cancelled."""
        elapsed = (time.time() - self._start_time) * 1000
        self._emit_event(
            ProgressPhase.CANCELLED,
            self._last_percent,
            "Cancelled",
            elapsed_ms=elapsed
        )

    def _get_phase_start_percent(self, phase: ProgressPhase) -> int:
        """Get starting percent for a phase."""
        percent = 0
        phases_order = list(self.DEFAULT_PHASE_WEIGHTS.keys())

        for p in phases_order:
            if p == phase:
                break
            percent += self._phase_weights.get(p, 0)

        return percent

    def _get_phase_end_percent(self, phase: ProgressPhase) -> int:
        """Get ending percent for a phase."""
        start = self._get_phase_start_percent(phase)
        weight = self._phase_weights.get(phase, 0)
        return start + weight

    def _emit_event(
        self,
        phase: ProgressPhase,
        percent: int,
        message: str,
        **kwargs
    ) -> None:
        """Emit a progress event."""
        event = ProgressEvent(
            phase=phase,
            percent=percent,
            message=message,
            layer_name=getattr(self, '_layer_name', None),
            task_id=self._task_id,
            **kwargs
        )

        self._history.append(event)

        if self._log_progress:
            logger.debug(
                f"[{self._task_id or 'task'}] {percent}% - {message}"
            )

        if self._on_progress:
            try:
                self._on_progress(event)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._start_time:
            return (time.time() - self._start_time) * 1000
        return 0.0

    @property
    def current_phase(self) -> ProgressPhase:
        """Get current phase."""
        return self._current_phase

    @property
    def history(self) -> List[ProgressEvent]:
        """Get progress event history."""
        return list(self._history)

    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary."""
        return {
            'task_id': self._task_id,
            'elapsed_ms': self.elapsed_ms,
            'current_phase': self._current_phase.value,
            'last_percent': self._last_percent,
            'phases_completed': [p.value for p in self._completed_phases],
            'events_count': len(self._history)
        }


class ProgressAggregator:
    """
    Aggregates progress from multiple child tasks.

    Useful for batch operations where multiple tasks run in parallel
    or sequence.

    Example:
        aggregator = ProgressAggregator(
            total_tasks=5,
            on_progress=update_batch_progress
        )

        for i, task in enumerate(tasks):
            task.run()
            aggregator.task_complete(i)
    """

    def __init__(
        self,
        total_tasks: int,
        on_progress: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize aggregator.

        Args:
            total_tasks: Total number of tasks to aggregate
            on_progress: Callback with (percent, message)
        """
        self._total_tasks = total_tasks
        self._completed_tasks = 0
        self._on_progress = on_progress
        self._task_progress: Dict[int, int] = {}

    def update_task(self, task_index: int, percent: int, message: str = "") -> None:
        """Update progress for a specific task."""
        self._task_progress[task_index] = percent
        self._emit_aggregate_progress(message)

    def task_complete(self, task_index: int, message: str = "") -> None:
        """Mark a task as complete."""
        self._task_progress[task_index] = 100
        self._completed_tasks += 1
        self._emit_aggregate_progress(
            message or f"Completed {self._completed_tasks}/{self._total_tasks}"
        )

    def _emit_aggregate_progress(self, message: str) -> None:
        """Calculate and emit aggregate progress."""
        if self._total_tasks == 0:
            return

        # Average of all task progress
        total_progress = sum(self._task_progress.values())
        avg_percent = int(total_progress / self._total_tasks)

        if self._on_progress:
            try:
                self._on_progress(avg_percent, message)
            except Exception:
                pass

    @property
    def percent(self) -> int:
        """Get aggregate percent complete."""
        if self._total_tasks == 0:
            return 100
        total_progress = sum(self._task_progress.values())
        return int(total_progress / self._total_tasks)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        return self._completed_tasks >= self._total_tasks
