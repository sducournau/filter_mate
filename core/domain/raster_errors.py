# -*- coding: utf-8 -*-
"""
Raster Error Handling Module.

EPIC-2: Raster Integration
US-11: Error Handling

Provides comprehensive error handling for raster operations:
- Typed exception hierarchy
- Error recovery strategies
- User-friendly error messages
- Error logging and reporting

Author: FilterMate Team
Date: January 2026
"""
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger('FilterMate.Core.RasterErrors')

T = TypeVar('T')


# =============================================================================
# Error Severity Levels
# =============================================================================

class ErrorSeverity(Enum):
    """Severity level of errors."""
    DEBUG = auto()      # Developer-level, not shown to user
    INFO = auto()       # Informational, may be shown
    WARNING = auto()    # Non-fatal issue
    ERROR = auto()      # Operation failed
    CRITICAL = auto()   # System-level failure


# =============================================================================
# Error Categories
# =============================================================================

class RasterErrorCategory(Enum):
    """Category of raster errors for targeted handling."""
    LAYER_ACCESS = "layer_access"       # Layer not found, invalid, etc.
    STATISTICS = "statistics"           # Stats computation failures
    HISTOGRAM = "histogram"             # Histogram generation failures
    TRANSPARENCY = "transparency"       # Transparency application errors
    IDENTIFY = "identify"               # Pixel identification errors
    RENDERING = "rendering"             # Rendering/display errors
    CACHE = "cache"                     # Cache operation errors
    IO = "io"                           # File/network I/O errors
    MEMORY = "memory"                   # Memory allocation errors
    CONFIGURATION = "configuration"     # Config/settings errors
    UNKNOWN = "unknown"                 # Unclassified errors


# =============================================================================
# Exception Hierarchy
# =============================================================================

class RasterError(Exception):
    """
    Base exception for all raster-related errors.
    
    Attributes:
        message: Human-readable error message
        category: Error category for handling
        severity: Error severity level
        layer_id: Associated layer ID (if any)
        cause: Original exception (if wrapped)
        recovery_hint: Suggested recovery action
    """
    
    def __init__(
        self,
        message: str,
        category: RasterErrorCategory = RasterErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        layer_id: Optional[str] = None,
        cause: Optional[Exception] = None,
        recovery_hint: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.layer_id = layer_id
        self.cause = cause
        self.recovery_hint = recovery_hint
    
    def __str__(self) -> str:
        parts = [self.message]
        if self.layer_id:
            parts.append(f"(layer: {self.layer_id})")
        if self.cause:
            parts.append(f"caused by: {self.cause}")
        return " ".join(parts)
    
    @property
    def user_message(self) -> str:
        """Get user-friendly error message."""
        msg = self.message
        if self.recovery_hint:
            msg = f"{msg}\n\n💡 {self.recovery_hint}"
        return msg


class LayerNotFoundError(RasterError):
    """Raised when a layer cannot be found."""
    
    def __init__(
        self,
        layer_id: str,
        message: Optional[str] = None
    ):
        super().__init__(
            message or f"Raster layer not found: {layer_id}",
            category=RasterErrorCategory.LAYER_ACCESS,
            severity=ErrorSeverity.ERROR,
            layer_id=layer_id,
            recovery_hint="Please select a valid raster layer."
        )


class LayerInvalidError(RasterError):
    """Raised when a layer is invalid for the operation."""
    
    def __init__(
        self,
        layer_id: str,
        reason: str = "unknown"
    ):
        super().__init__(
            f"Layer is not valid for this operation: {reason}",
            category=RasterErrorCategory.LAYER_ACCESS,
            severity=ErrorSeverity.ERROR,
            layer_id=layer_id,
            recovery_hint="Check that the layer is loaded correctly."
        )


class StatisticsComputationError(RasterError):
    """Raised when statistics computation fails."""
    
    def __init__(
        self,
        layer_id: str,
        reason: str,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Failed to compute statistics: {reason}",
            category=RasterErrorCategory.STATISTICS,
            severity=ErrorSeverity.ERROR,
            layer_id=layer_id,
            cause=cause,
            recovery_hint="Try refreshing or use a smaller sample size."
        )


class HistogramComputationError(RasterError):
    """Raised when histogram computation fails."""
    
    def __init__(
        self,
        layer_id: str,
        band: int,
        reason: str,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Failed to compute histogram for band {band}: {reason}",
            category=RasterErrorCategory.HISTOGRAM,
            severity=ErrorSeverity.WARNING,
            layer_id=layer_id,
            cause=cause,
            recovery_hint="Histogram may not be available for this band."
        )
        self.band = band


class TransparencyApplicationError(RasterError):
    """Raised when transparency settings cannot be applied."""
    
    def __init__(
        self,
        layer_id: str,
        reason: str,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Failed to apply transparency: {reason}",
            category=RasterErrorCategory.TRANSPARENCY,
            severity=ErrorSeverity.WARNING,
            layer_id=layer_id,
            cause=cause,
            recovery_hint="Try using basic opacity instead."
        )


class PixelIdentifyError(RasterError):
    """Raised when pixel identification fails."""
    
    def __init__(
        self,
        layer_id: str,
        x: float,
        y: float,
        reason: str
    ):
        super().__init__(
            f"Failed to identify pixel at ({x:.2f}, {y:.2f}): {reason}",
            category=RasterErrorCategory.IDENTIFY,
            severity=ErrorSeverity.WARNING,
            layer_id=layer_id,
            recovery_hint="Ensure coordinates are within layer extent."
        )
        self.x = x
        self.y = y


class CacheError(RasterError):
    """Raised when cache operations fail."""
    
    def __init__(
        self,
        operation: str,
        reason: str,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Cache {operation} failed: {reason}",
            category=RasterErrorCategory.CACHE,
            severity=ErrorSeverity.WARNING,
            cause=cause,
            recovery_hint="Cache will be bypassed, operations may be slower."
        )
        self.operation = operation


class MemoryError(RasterError):
    """Raised when memory allocation fails."""
    
    def __init__(
        self,
        operation: str,
        required_mb: float,
        available_mb: Optional[float] = None
    ):
        msg = f"Insufficient memory for {operation}: need {required_mb:.1f} MB"
        if available_mb is not None:
            msg += f", only {available_mb:.1f} MB available"
        
        super().__init__(
            msg,
            category=RasterErrorCategory.MEMORY,
            severity=ErrorSeverity.ERROR,
            recovery_hint=(
                "Close other applications or use sampling "
                "to reduce memory usage."
            )
        )
        self.required_mb = required_mb
        self.available_mb = available_mb


# =============================================================================
# Error Result Container
# =============================================================================

@dataclass
class ErrorResult:
    """
    Container for operation results that may fail.
    
    Use instead of exceptions for recoverable errors
    that should be reported to the user.
    
    Attributes:
        success: Whether the operation succeeded
        value: Result value (if successful)
        error: Error information (if failed)
        warnings: Non-fatal warnings
    """
    success: bool
    value: Any = None
    error: Optional[RasterError] = None
    warnings: List[str] = field(default_factory=list)
    
    @classmethod
    def ok(cls, value: Any) -> 'ErrorResult':
        """Create successful result."""
        return cls(success=True, value=value)
    
    @classmethod
    def fail(cls, error: RasterError) -> 'ErrorResult':
        """Create failed result."""
        return cls(success=False, error=error)
    
    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        category: RasterErrorCategory = RasterErrorCategory.UNKNOWN
    ) -> 'ErrorResult':
        """Create result from exception."""
        if isinstance(exception, RasterError):
            error = exception
        else:
            error = RasterError(
                str(exception),
                category=category,
                cause=exception
            )
        return cls(success=False, error=error)
    
    def add_warning(self, message: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(message)
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0


# =============================================================================
# Error Handler
# =============================================================================

class RasterErrorHandler:
    """
    Centralized error handler for raster operations.
    
    Provides:
    - Error logging
    - User notification
    - Recovery suggestions
    - Error statistics
    
    Example:
        >>> handler = RasterErrorHandler()
        >>> try:
        ...     compute_stats()
        ... except RasterError as e:
        ...     handler.handle(e)
    """
    
    def __init__(self):
        """Initialize error handler."""
        self._error_counts: Dict[RasterErrorCategory, int] = {}
        self._last_errors: Dict[RasterErrorCategory, RasterError] = {}
        self._callbacks: List[Callable[[RasterError], None]] = []
    
    def handle(
        self,
        error: RasterError,
        notify_user: bool = True
    ) -> None:
        """
        Handle a raster error.
        
        Args:
            error: The error to handle
            notify_user: Whether to show user notification
        """
        # Log error
        self._log_error(error)
        
        # Update statistics
        self._error_counts[error.category] = (
            self._error_counts.get(error.category, 0) + 1
        )
        self._last_errors[error.category] = error
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.warning(f"Error callback failed: {e}")
        
        # User notification
        if notify_user:
            self._notify_user(error)
    
    def register_callback(
        self,
        callback: Callable[[RasterError], None]
    ) -> None:
        """Register error callback."""
        self._callbacks.append(callback)
    
    def get_error_stats(self) -> Dict[str, int]:
        """Get error statistics by category."""
        return {
            cat.value: count
            for cat, count in self._error_counts.items()
        }
    
    def get_last_error(
        self,
        category: Optional[RasterErrorCategory] = None
    ) -> Optional[RasterError]:
        """Get last error, optionally by category."""
        if category:
            return self._last_errors.get(category)
        # Return most recent
        if self._last_errors:
            return list(self._last_errors.values())[-1]
        return None
    
    def clear_stats(self) -> None:
        """Clear error statistics."""
        self._error_counts.clear()
        self._last_errors.clear()
    
    def _log_error(self, error: RasterError) -> None:
        """Log error at appropriate level."""
        log_msg = f"[{error.category.value}] {error}"
        
        if error.severity == ErrorSeverity.DEBUG:
            logger.debug(log_msg)
        elif error.severity == ErrorSeverity.INFO:
            logger.info(log_msg)
        elif error.severity == ErrorSeverity.WARNING:
            logger.warning(log_msg)
        elif error.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_msg)
        else:
            logger.error(log_msg)
        
        # Log traceback for cause
        if error.cause:
            logger.debug(f"Caused by: {error.cause}", exc_info=error.cause)
    
    def _notify_user(self, error: RasterError) -> None:
        """Show user notification via QGIS message bar."""
        try:
            from qgis.utils import iface
            if iface is None:
                return
            
            msg_bar = iface.messageBar()
            title = "FilterMate Raster"
            message = error.user_message
            
            if error.severity == ErrorSeverity.WARNING:
                msg_bar.pushWarning(title, message)
            elif error.severity == ErrorSeverity.CRITICAL:
                msg_bar.pushCritical(title, message)
            elif error.severity == ErrorSeverity.INFO:
                msg_bar.pushInfo(title, message)
            else:
                msg_bar.pushCritical(title, message)
                
        except ImportError:
            # QGIS not available (testing)
            pass
        except Exception as e:
            logger.warning(f"Failed to show user notification: {e}")


# =============================================================================
# Error Recovery Decorators
# =============================================================================

def handle_raster_errors(
    category: RasterErrorCategory = RasterErrorCategory.UNKNOWN,
    default: Any = None,
    log_errors: bool = True,
    reraise: bool = False
):
    """
    Decorator for handling raster errors in functions.
    
    Args:
        category: Error category for unclassified errors
        default: Default return value on error
        log_errors: Whether to log errors
        reraise: Whether to re-raise after handling
    
    Example:
        @handle_raster_errors(category=RasterErrorCategory.STATISTICS)
        def compute_stats(layer_id):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except RasterError as e:
                if log_errors:
                    logger.error(f"[{e.category.value}] {e}")
                if reraise:
                    raise
                return default
            except Exception as e:
                wrapped = RasterError(
                    str(e),
                    category=category,
                    cause=e
                )
                if log_errors:
                    logger.error(f"[{category.value}] {wrapped}")
                if reraise:
                    raise wrapped from e
                return default
        return wrapper
    return decorator


def with_error_result(
    category: RasterErrorCategory = RasterErrorCategory.UNKNOWN
):
    """
    Decorator that returns ErrorResult instead of raising.
    
    Args:
        category: Default error category
    
    Example:
        @with_error_result(category=RasterErrorCategory.STATISTICS)
        def compute_stats(layer_id):
            # Returns ErrorResult.ok(stats) or ErrorResult.fail(error)
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., ErrorResult]:
        def wrapper(*args, **kwargs) -> ErrorResult:
            try:
                result = func(*args, **kwargs)
                return ErrorResult.ok(result)
            except RasterError as e:
                return ErrorResult.fail(e)
            except Exception as e:
                return ErrorResult.from_exception(e, category)
        return wrapper
    return decorator


# =============================================================================
# Global Error Handler
# =============================================================================

_global_handler: Optional[RasterErrorHandler] = None


def get_error_handler() -> RasterErrorHandler:
    """Get global raster error handler."""
    global _global_handler
    if _global_handler is None:
        _global_handler = RasterErrorHandler()
    return _global_handler


def reset_error_handler() -> None:
    """Reset global error handler (for testing)."""
    global _global_handler
    _global_handler = None
