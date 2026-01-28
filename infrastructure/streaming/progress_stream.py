# -*- coding: utf-8 -*-
"""
ProgressStreamer - Real-time progress streaming for UI updates.

v4.1.1 - January 2026

PURPOSE:
Provides smooth, responsive progress feedback during long operations:
1. Throttled updates to prevent UI flooding
2. ETA calculation with rolling average
3. Multi-stage progress support
4. Thread-safe signal emission
5. Cancellation propagation

PERFORMANCE:
- Updates throttled to max 30 Hz (every 33ms)
- Minimal overhead on processing loop
- Non-blocking UI updates via Qt signals
"""

import time
import logging
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque

try:
    from qgis.PyQt.QtCore import QObject, pyqtSignal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QObject = object

logger = logging.getLogger('FilterMate.ProgressStreamer')


class ProgressState(Enum):
    """Progress operation states."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    ERROR = auto()


@dataclass
class ProgressInfo:
    """
    Detailed progress information.
    
    Attributes:
        current: Current progress value
        total: Total progress value (0 = indeterminate)
        percent: Percentage complete (0-100)
        message: Current status message
        stage: Current stage name (for multi-stage operations)
        stage_index: Current stage index (0-based)
        total_stages: Total number of stages
        elapsed_ms: Elapsed time in milliseconds
        eta_ms: Estimated time remaining in milliseconds
        items_per_second: Processing rate
        state: Current progress state
    """
    current: int = 0
    total: int = 0
    percent: float = 0.0
    message: str = ""
    stage: str = ""
    stage_index: int = 0
    total_stages: int = 1
    elapsed_ms: float = 0.0
    eta_ms: float = -1.0
    items_per_second: float = 0.0
    state: ProgressState = ProgressState.IDLE
    
    @property
    def is_indeterminate(self) -> bool:
        """Check if progress is indeterminate (unknown total)."""
        return self.total <= 0
    
    @property
    def is_complete(self) -> bool:
        """Check if progress is complete."""
        return self.state == ProgressState.COMPLETED
    
    @property
    def eta_formatted(self) -> str:
        """Get formatted ETA string."""
        if self.eta_ms < 0:
            return "Calculating..."
        
        seconds = int(self.eta_ms / 1000)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"
    
    @property
    def elapsed_formatted(self) -> str:
        """Get formatted elapsed time string."""
        seconds = int(self.elapsed_ms / 1000)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"


if QT_AVAILABLE:
    class ProgressSignals(QObject):
        """
        Qt signals for thread-safe progress updates.
        
        Signals:
            progress_updated(ProgressInfo): Emitted on progress change
            stage_changed(stage_name, stage_index): Emitted when stage changes
            completed(success, message): Emitted when operation completes
            cancelled(): Emitted when operation is cancelled
            error(message): Emitted on error
        """
        progress_updated = pyqtSignal(object)  # ProgressInfo
        stage_changed = pyqtSignal(str, int)   # stage_name, stage_index
        completed = pyqtSignal(bool, str)      # success, message
        cancelled = pyqtSignal()
        error = pyqtSignal(str)
else:
    class ProgressSignals:
        """Dummy signals when Qt is not available."""
        def __init__(self):
            self.progress_updated = None
            self.stage_changed = None
            self.completed = None
            self.cancelled = None
            self.error = None


class ProgressStreamer:
    """
    Streams progress updates with throttling and ETA calculation.
    
    KEY FEATURES:
    - Throttles updates to prevent UI flooding (default 30 Hz)
    - Calculates ETA using rolling average of recent rates
    - Supports multi-stage operations with stage tracking
    - Thread-safe Qt signal emission
    - Cancellation support
    
    Example:
        streamer = ProgressStreamer(
            total=10000,
            message="Processing features",
            update_interval_ms=50  # 20 updates/second
        )
        
        # Connect UI
        streamer.signals.progress_updated.connect(update_progress_bar)
        
        streamer.start()
        for i, feature in enumerate(features):
            if streamer.is_cancelled:
                break
            process(feature)
            streamer.update(i + 1)
        
        streamer.complete()
    """
    
    # Default update interval (33ms = ~30 Hz)
    DEFAULT_UPDATE_INTERVAL_MS = 33
    
    # Number of samples for ETA rolling average
    ETA_SAMPLE_COUNT = 10
    
    def __init__(
        self,
        total: int = 0,
        message: str = "",
        stages: List[str] = None,
        update_interval_ms: int = DEFAULT_UPDATE_INTERVAL_MS,
        on_progress: Callable[[ProgressInfo], None] = None,
    ):
        """
        Initialize progress streamer.
        
        Args:
            total: Total items (0 = indeterminate)
            message: Initial status message
            stages: List of stage names for multi-stage operations
            update_interval_ms: Minimum interval between updates
            on_progress: Optional callback for progress updates
        """
        self._total = total
        self._message = message
        self._stages = stages or ["Processing"]
        self._update_interval_ms = update_interval_ms
        self._on_progress = on_progress
        
        # State
        self._current = 0
        self._state = ProgressState.IDLE
        self._current_stage_index = 0
        self._start_time: Optional[float] = None
        self._last_update_time: float = 0
        self._cancelled = False
        
        # ETA calculation
        self._rate_samples: deque = deque(maxlen=self.ETA_SAMPLE_COUNT)
        self._last_rate_sample_time: float = 0
        self._last_rate_sample_count: int = 0
        
        # Qt signals
        self.signals = ProgressSignals()
    
    @property
    def is_cancelled(self) -> bool:
        """Check if operation has been cancelled."""
        return self._cancelled
    
    @property
    def is_running(self) -> bool:
        """Check if operation is running."""
        return self._state == ProgressState.RUNNING
    
    @property
    def current_stage(self) -> str:
        """Get current stage name."""
        if 0 <= self._current_stage_index < len(self._stages):
            return self._stages[self._current_stage_index]
        return ""
    
    def start(self, message: str = None) -> None:
        """
        Start progress tracking.
        
        Args:
            message: Optional new message
        """
        self._start_time = time.time()
        self._last_update_time = 0
        self._current = 0
        self._state = ProgressState.RUNNING
        self._cancelled = False
        self._rate_samples.clear()
        self._last_rate_sample_time = self._start_time
        self._last_rate_sample_count = 0
        
        if message:
            self._message = message
        
        logger.debug(f"Progress started: {self._message}")
        self._emit_update()
    
    def update(
        self,
        current: int = None,
        message: str = None,
        force: bool = False
    ) -> None:
        """
        Update progress.
        
        Args:
            current: New current value (None = increment by 1)
            message: Optional new message
            force: Force emit even if throttled
        """
        if self._state != ProgressState.RUNNING:
            return
        
        # Update current
        if current is not None:
            self._current = current
        else:
            self._current += 1
        
        if message:
            self._message = message
        
        # Update rate samples
        now = time.time()
        sample_elapsed = now - self._last_rate_sample_time
        if sample_elapsed >= 0.1:  # Sample rate every 100ms
            items_in_sample = self._current - self._last_rate_sample_count
            if items_in_sample > 0:
                rate = items_in_sample / sample_elapsed
                self._rate_samples.append(rate)
            self._last_rate_sample_time = now
            self._last_rate_sample_count = self._current
        
        # Throttle updates
        elapsed_since_update = (now - self._last_update_time) * 1000
        if not force and elapsed_since_update < self._update_interval_ms:
            return
        
        self._last_update_time = now
        self._emit_update()
    
    def set_stage(self, stage_index: int, message: str = None) -> None:
        """
        Move to a specific stage.
        
        Args:
            stage_index: Stage index (0-based)
            message: Optional new message
        """
        if 0 <= stage_index < len(self._stages):
            self._current_stage_index = stage_index
            self._current = 0  # Reset progress for new stage
            
            if message:
                self._message = message
            
            # Emit stage change signal
            if QT_AVAILABLE and self.signals.stage_changed:
                self.signals.stage_changed.emit(
                    self._stages[stage_index],
                    stage_index
                )
            
            self._emit_update()
    
    def next_stage(self, message: str = None) -> None:
        """
        Move to next stage.
        
        Args:
            message: Optional new message
        """
        self.set_stage(self._current_stage_index + 1, message)
    
    def complete(self, message: str = None) -> None:
        """
        Mark operation as complete.
        
        Args:
            message: Optional completion message
        """
        self._state = ProgressState.COMPLETED
        self._current = self._total
        
        if message:
            self._message = message
        
        self._emit_update()
        
        # Emit completed signal
        if QT_AVAILABLE and self.signals.completed:
            self.signals.completed.emit(True, self._message)
        
        elapsed = (time.time() - self._start_time) * 1000 if self._start_time else 0
        logger.debug(f"Progress completed: {self._message} ({elapsed:.0f}ms)")
    
    def cancel(self) -> None:
        """Cancel the operation."""
        self._cancelled = True
        self._state = ProgressState.CANCELLED
        
        self._emit_update()
        
        if QT_AVAILABLE and self.signals.cancelled:
            self.signals.cancelled.emit()
        
        logger.debug("Progress cancelled")
    
    def error(self, message: str) -> None:
        """
        Report an error.
        
        Args:
            message: Error message
        """
        self._state = ProgressState.ERROR
        self._message = message
        
        self._emit_update()
        
        if QT_AVAILABLE and self.signals.error:
            self.signals.error.emit(message)
        
        logger.error(f"Progress error: {message}")
    
    def get_info(self) -> ProgressInfo:
        """
        Get current progress information.
        
        Returns:
            ProgressInfo with current state
        """
        now = time.time()
        elapsed_ms = (now - self._start_time) * 1000 if self._start_time else 0
        
        # Calculate percentage
        percent = 0.0
        if self._total > 0:
            percent = min(100.0, (self._current / self._total) * 100)
        
        # Calculate ETA from rolling average
        eta_ms = -1.0
        items_per_second = 0.0
        
        if self._rate_samples:
            avg_rate = sum(self._rate_samples) / len(self._rate_samples)
            items_per_second = avg_rate
            
            if avg_rate > 0 and self._total > 0:
                remaining = self._total - self._current
                eta_ms = (remaining / avg_rate) * 1000
        
        return ProgressInfo(
            current=self._current,
            total=self._total,
            percent=percent,
            message=self._message,
            stage=self.current_stage,
            stage_index=self._current_stage_index,
            total_stages=len(self._stages),
            elapsed_ms=elapsed_ms,
            eta_ms=eta_ms,
            items_per_second=items_per_second,
            state=self._state,
        )
    
    def _emit_update(self) -> None:
        """Emit progress update signal."""
        info = self.get_info()
        
        # Callback
        if self._on_progress:
            try:
                self._on_progress(info)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
        
        # Qt signal
        if QT_AVAILABLE and self.signals.progress_updated:
            self.signals.progress_updated.emit(info)


class MultiStageProgress:
    """
    Convenience wrapper for multi-stage operations.
    
    Tracks progress across multiple stages with weighted progress.
    
    Example:
        progress = MultiStageProgress([
            ("Loading", 10),      # 10% weight
            ("Processing", 70),   # 70% weight
            ("Saving", 20),       # 20% weight
        ])
        
        progress.signals.progress_updated.connect(update_ui)
        progress.start()
        
        # Stage 1
        progress.begin_stage(0, total=100)
        for i in range(100):
            progress.update(i + 1)
        
        # Stage 2
        progress.begin_stage(1, total=1000)
        for i in range(1000):
            progress.update(i + 1)
        
        # Stage 3
        progress.begin_stage(2, total=50)
        for i in range(50):
            progress.update(i + 1)
        
        progress.complete()
    """
    
    def __init__(
        self,
        stages: List[tuple],  # (name, weight)
        update_interval_ms: int = 33,
    ):
        """
        Initialize multi-stage progress.
        
        Args:
            stages: List of (stage_name, weight) tuples
            update_interval_ms: Update interval
        """
        self._stages = stages
        self._stage_names = [s[0] for s in stages]
        self._weights = [s[1] for s in stages]
        self._total_weight = sum(self._weights)
        
        self._streamer = ProgressStreamer(
            total=100,  # Overall percent
            stages=self._stage_names,
            update_interval_ms=update_interval_ms,
        )
        
        self._current_stage_index = 0
        self._stage_total = 0
        self._stage_current = 0
    
    @property
    def signals(self) -> ProgressSignals:
        """Get Qt signals."""
        return self._streamer.signals
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self._streamer.is_cancelled
    
    def start(self, message: str = None) -> None:
        """Start progress tracking."""
        self._streamer.start(message)
    
    def begin_stage(self, stage_index: int, total: int, message: str = None) -> None:
        """
        Begin a new stage.
        
        Args:
            stage_index: Stage index
            total: Total items in this stage
            message: Optional message
        """
        self._current_stage_index = stage_index
        self._stage_total = total
        self._stage_current = 0
        
        self._streamer.set_stage(stage_index, message or self._stage_names[stage_index])
    
    def update(self, current: int = None, message: str = None) -> None:
        """
        Update progress within current stage.
        
        Args:
            current: Current item in stage
            message: Optional message
        """
        if current is not None:
            self._stage_current = current
        else:
            self._stage_current += 1
        
        # Calculate overall progress
        completed_weight = sum(self._weights[:self._current_stage_index])
        
        stage_weight = self._weights[self._current_stage_index]
        stage_progress = 0
        if self._stage_total > 0:
            stage_progress = self._stage_current / self._stage_total
        
        overall = (completed_weight + stage_weight * stage_progress) / self._total_weight * 100
        
        self._streamer._total = 100
        self._streamer.update(int(overall), message)
    
    def cancel(self) -> None:
        """Cancel operation."""
        self._streamer.cancel()
    
    def complete(self, message: str = None) -> None:
        """Complete operation."""
        self._streamer.complete(message)
    
    def get_info(self) -> ProgressInfo:
        """Get current progress info."""
        return self._streamer.get_info()


def create_progress_streamer(
    total: int = 0,
    message: str = "",
    stages: List[str] = None,
    on_progress: Callable[[ProgressInfo], None] = None,
) -> ProgressStreamer:
    """
    Factory function to create a progress streamer.
    
    Args:
        total: Total items
        message: Initial message
        stages: Stage names for multi-stage
        on_progress: Progress callback
        
    Returns:
        Configured ProgressStreamer
    """
    return ProgressStreamer(
        total=total,
        message=message,
        stages=stages,
        on_progress=on_progress,
    )
