"""
Filter Result Value Object.

Immutable representation of a filter operation result
with execution statistics and error handling.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from dataclasses import dataclass, field
from typing import Optional, FrozenSet, Sequence
from datetime import datetime
from enum import Enum


class FilterStatus(Enum):
    """
    Status of a filter operation.
    
    Represents the outcome state of a filter execution.
    """
    SUCCESS = "success"
    PARTIAL = "partial"  # Some layers filtered, some failed
    CANCELLED = "cancelled"
    ERROR = "error"
    NO_MATCHES = "no_matches"


@dataclass(frozen=True)
class FilterResult:
    """
    Immutable value object representing filter operation result.

    This object encapsulates:
    - The set of matching feature IDs
    - Execution statistics (time, cache status)
    - Operation status and error information

    Use factory methods for proper construction:
    - `success()`: Create a successful result
    - `error()`: Create an error result
    - `cancelled()`: Create a cancelled result
    - `from_cache()`: Create a cached result

    Attributes:
        feature_ids: Frozen set of matching feature IDs
        layer_id: Target layer QGIS ID
        expression_raw: Original expression that produced this result
        status: Operation status
        execution_time_ms: Execution time in milliseconds
        is_cached: Whether result was retrieved from cache
        timestamp: When the result was created
        error_message: Error message if status is ERROR
        backend_name: Name of backend that executed the filter
        
    Example:
        >>> result = FilterResult.success(
        ...     feature_ids=(1, 2, 3),
        ...     layer_id="layer_123",
        ...     expression_raw="field = 'value'",
        ...     execution_time_ms=42.5
        ... )
        >>> result.count
        3
        >>> result.is_success
        True
    """
    feature_ids: FrozenSet[int]
    layer_id: str
    expression_raw: str
    status: FilterStatus = FilterStatus.SUCCESS
    execution_time_ms: float = 0.0
    is_cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    backend_name: str = ""

    @classmethod
    def success(
        cls,
        feature_ids: Sequence[int],
        layer_id: str,
        expression_raw: str,
        execution_time_ms: float = 0.0,
        backend_name: str = ""
    ) -> 'FilterResult':
        """
        Create a successful filter result.
        
        Args:
            feature_ids: Sequence of matching feature IDs
            layer_id: Target layer QGIS ID
            expression_raw: Original expression string
            execution_time_ms: Execution time in milliseconds
            backend_name: Name of backend that executed the filter
            
        Returns:
            FilterResult with SUCCESS or NO_MATCHES status
        """
        fids = frozenset(feature_ids)
        status = FilterStatus.SUCCESS if fids else FilterStatus.NO_MATCHES
        return cls(
            feature_ids=fids,
            layer_id=layer_id,
            expression_raw=expression_raw,
            status=status,
            execution_time_ms=execution_time_ms,
            backend_name=backend_name
        )

    @classmethod
    def error(
        cls,
        layer_id: str,
        expression_raw: str,
        error_message: str,
        backend_name: str = ""
    ) -> 'FilterResult':
        """
        Create an error filter result.
        
        Args:
            layer_id: Target layer QGIS ID
            expression_raw: Original expression string
            error_message: Description of the error
            backend_name: Name of backend that failed
            
        Returns:
            FilterResult with ERROR status
        """
        return cls(
            feature_ids=frozenset(),
            layer_id=layer_id,
            expression_raw=expression_raw,
            status=FilterStatus.ERROR,
            error_message=error_message,
            backend_name=backend_name
        )

    @classmethod
    def cancelled(
        cls,
        layer_id: str,
        expression_raw: str
    ) -> 'FilterResult':
        """
        Create a cancelled filter result.
        
        Args:
            layer_id: Target layer QGIS ID
            expression_raw: Original expression string
            
        Returns:
            FilterResult with CANCELLED status
        """
        return cls(
            feature_ids=frozenset(),
            layer_id=layer_id,
            expression_raw=expression_raw,
            status=FilterStatus.CANCELLED
        )

    @classmethod
    def from_cache(
        cls,
        feature_ids: Sequence[int],
        layer_id: str,
        expression_raw: str,
        original_execution_time_ms: float = 0.0,
        backend_name: str = ""
    ) -> 'FilterResult':
        """
        Create a cached filter result.
        
        Args:
            feature_ids: Sequence of matching feature IDs
            layer_id: Target layer QGIS ID
            expression_raw: Original expression string
            original_execution_time_ms: Original execution time
            backend_name: Name of backend that originally executed
            
        Returns:
            FilterResult marked as is_cached=True
        """
        fids = frozenset(feature_ids)
        status = FilterStatus.SUCCESS if fids else FilterStatus.NO_MATCHES
        return cls(
            feature_ids=fids,
            layer_id=layer_id,
            expression_raw=expression_raw,
            status=status,
            execution_time_ms=original_execution_time_ms,
            is_cached=True,
            backend_name=backend_name
        )

    @classmethod
    def partial(
        cls,
        feature_ids: Sequence[int],
        layer_id: str,
        expression_raw: str,
        error_message: str,
        execution_time_ms: float = 0.0,
        backend_name: str = ""
    ) -> 'FilterResult':
        """
        Create a partial success result (some succeeded, some failed).
        
        Args:
            feature_ids: Sequence of successfully matched feature IDs
            layer_id: Target layer QGIS ID
            expression_raw: Original expression string
            error_message: Description of partial failure
            execution_time_ms: Execution time in milliseconds
            backend_name: Name of backend
            
        Returns:
            FilterResult with PARTIAL status
        """
        return cls(
            feature_ids=frozenset(feature_ids),
            layer_id=layer_id,
            expression_raw=expression_raw,
            status=FilterStatus.PARTIAL,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            backend_name=backend_name
        )

    @property
    def count(self) -> int:
        """Number of matching features."""
        return len(self.feature_ids)

    @property
    def is_empty(self) -> bool:
        """Check if no features matched."""
        return len(self.feature_ids) == 0

    @property
    def has_error(self) -> bool:
        """Check if result represents an error."""
        return self.status == FilterStatus.ERROR

    @property
    def is_success(self) -> bool:
        """
        Check if result represents success (with or without matches).
        
        Note: NO_MATCHES is considered success because the operation
        completed without errors.
        """
        return self.status in (FilterStatus.SUCCESS, FilterStatus.NO_MATCHES)

    @property
    def was_cancelled(self) -> bool:
        """Check if operation was cancelled."""
        return self.status == FilterStatus.CANCELLED

    @property
    def is_partial(self) -> bool:
        """Check if result is partial (some success, some failure)."""
        return self.status == FilterStatus.PARTIAL

    def with_cached(self, is_cached: bool = True) -> 'FilterResult':
        """
        Return new result marked as from cache.
        
        Args:
            is_cached: Whether to mark as cached
            
        Returns:
            New FilterResult with updated is_cached flag
        """
        return FilterResult(
            feature_ids=self.feature_ids,
            layer_id=self.layer_id,
            expression_raw=self.expression_raw,
            status=self.status,
            execution_time_ms=self.execution_time_ms,
            is_cached=is_cached,
            timestamp=self.timestamp,
            error_message=self.error_message,
            backend_name=self.backend_name
        )

    def with_backend(self, backend_name: str) -> 'FilterResult':
        """
        Return new result with updated backend name.
        
        Args:
            backend_name: New backend name
            
        Returns:
            New FilterResult with updated backend
        """
        return FilterResult(
            feature_ids=self.feature_ids,
            layer_id=self.layer_id,
            expression_raw=self.expression_raw,
            status=self.status,
            execution_time_ms=self.execution_time_ms,
            is_cached=self.is_cached,
            timestamp=self.timestamp,
            error_message=self.error_message,
            backend_name=backend_name
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        if self.has_error:
            return f"FilterResult(ERROR: {self.error_message})"
        if self.was_cancelled:
            return "FilterResult(CANCELLED)"
        cache_info = " [cached]" if self.is_cached else ""
        partial_info = " [partial]" if self.is_partial else ""
        return f"FilterResult({self.count} features, {self.execution_time_ms:.1f}ms{cache_info}{partial_info})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"FilterResult("
            f"count={self.count}, "
            f"layer_id={self.layer_id!r}, "
            f"status={self.status.value}, "
            f"execution_time_ms={self.execution_time_ms}, "
            f"is_cached={self.is_cached})"
        )
