"""
Backend Port Interface.

Abstract interface for all filter backends.
Implements the Port in Hexagonal Architecture pattern.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Flag, auto


class BackendCapability(Flag):
    """
    Capabilities that a backend may support.

    Used to query backend features at runtime and make
    intelligent decisions about optimization strategies.
    """
    NONE = 0
    SPATIAL_FILTER = auto()          # Supports spatial predicates
    MATERIALIZED_VIEW = auto()       # Supports MV optimization
    SPATIAL_INDEX = auto()           # Supports spatial indexing
    PARALLEL_EXECUTION = auto()      # Supports parallel queries
    CACHED_RESULTS = auto()          # Supports result caching
    COMPLEX_EXPRESSIONS = auto()     # Supports complex SQL expressions
    BUFFER_OPERATIONS = auto()       # Supports buffer geometry operations
    STREAMING = auto()               # Supports streaming large datasets
    TRANSACTIONS = auto()            # Supports database transactions


@dataclass(frozen=True)
class BackendInfo:
    """
    Information about a backend implementation.

    Attributes:
        name: Human-readable backend name
        version: Backend version string
        capabilities: Supported capabilities flags
        priority: Priority for backend selection (higher = preferred)
        max_features: Maximum features supported (None = unlimited)
        description: Optional description
    """
    name: str
    version: str
    capabilities: BackendCapability
    priority: int
    max_features: Optional[int] = None
    description: str = ""

    @property
    def supports_spatial(self) -> bool:
        """Check if backend supports spatial filtering."""
        return bool(self.capabilities & BackendCapability.SPATIAL_FILTER)

    @property
    def supports_mv(self) -> bool:
        """Check if backend supports materialized views."""
        return bool(self.capabilities & BackendCapability.MATERIALIZED_VIEW)

    @property
    def supports_spatial_index(self) -> bool:
        """Check if backend supports spatial indexing."""
        return bool(self.capabilities & BackendCapability.SPATIAL_INDEX)


class BackendPort(ABC):
    """
    Abstract interface for filter backends.

    All concrete backends (PostgreSQL, Spatialite, OGR, Memory)
    must implement this interface. This follows the Hexagonal
    Architecture pattern where the core domain depends on ports
    (interfaces), not concrete implementations.

    Example:
        class PostgreSQLBackend(BackendPort):
            def execute(self, expression, layer_info):
                # PostgreSQL-specific implementation
                conn = self._get_connection(layer_info)
                sql = expression.sql
                cursor = conn.cursor()
                cursor.execute(sql)
                ...
    """

    @abstractmethod
    def execute(
        self,
        expression: 'FilterExpression',
        layer_info: 'LayerInfo',
        target_layer_infos: Optional[List['LayerInfo']] = None
    ) -> 'FilterResult':
        """
        Execute a filter expression and return matching feature IDs.

        Args:
            expression: Validated filter expression with SQL
            layer_info: Source layer information
            target_layer_infos: Optional target layers for multi-layer filtering

        Returns:
            FilterResult with matching feature IDs or error

        Raises:
            Should not raise - errors returned via FilterResult.error()

        Note:
            Implementations should handle cancellation appropriately
            and return FilterResult.cancelled() if interrupted.
        """

    @abstractmethod
    def supports_layer(self, layer_info: 'LayerInfo') -> bool:
        """
        Check if this backend can handle the given layer.

        Args:
            layer_info: Layer to check

        Returns:
            True if backend can process this layer type

        Example:
            >>> backend.supports_layer(postgresql_layer)
            True
            >>> backend.supports_layer(shapefile_layer)
            False
        """

    @abstractmethod
    def get_info(self) -> BackendInfo:
        """
        Get backend information and capabilities.

        Returns:
            BackendInfo with name, version, and capabilities
        """

    @abstractmethod
    def cleanup(self) -> None:
        """
        Clean up temporary resources.

        Called during shutdown or when switching backends.
        Should clean up:
        - Materialized views
        - Temporary tables
        - Connection pools
        - Cached data

        Should be idempotent and safe to call multiple times.
        """

    @abstractmethod
    def estimate_execution_time(
        self,
        expression: 'FilterExpression',
        layer_info: 'LayerInfo'
    ) -> float:
        """
        Estimate execution time for planning purposes.

        Used by FilterService to select optimal backend when
        multiple backends can handle a layer.

        Args:
            expression: Filter expression
            layer_info: Source layer

        Returns:
            Estimated execution time in milliseconds
        """

    def has_capability(self, capability: BackendCapability) -> bool:
        """
        Check if backend has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if backend has the capability
        """
        return bool(self.get_info().capabilities & capability)

    @property
    def name(self) -> str:
        """Backend display name."""
        return self.get_info().name

    @property
    def priority(self) -> int:
        """Backend priority (higher = preferred)."""
        return self.get_info().priority

    @property
    def capabilities(self) -> BackendCapability:
        """Backend capabilities."""
        return self.get_info().capabilities

    def validate_expression(
        self,
        expression: 'FilterExpression'
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate expression for this backend.

        Args:
            expression: Expression to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default implementation - subclasses can override
        return True, None

    def prepare(self, layer_info: 'LayerInfo') -> bool:
        """
        Prepare backend for operations on a layer.

        Called before execute() to allow backends to set up
        connections, caches, or other resources.

        Args:
            layer_info: Layer that will be processed

        Returns:
            True if preparation successful
        """
        # Default implementation - no preparation needed
        return True

    def get_statistics(self) -> dict:
        """
        Get backend execution statistics.

        Returns:
            Dictionary with statistics like:
            - total_executions
            - total_time_ms
            - cache_hits
            - cache_misses
        """
        # Default implementation - no statistics
        return {}

    def reset_statistics(self) -> None:
        """Reset backend execution statistics."""
        # Default implementation - no statistics to reset

    def __str__(self) -> str:
        """Human-readable representation."""
        info = self.get_info()
        return f"{info.name} v{info.version} (priority: {info.priority})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        info = self.get_info()
        return (
            f"<{self.__class__.__name__} name={info.name!r} "
            f"version={info.version!r} priority={info.priority}>"
        )


# Type hints for forward references
# These are imported at runtime by implementations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..domain import FilterExpression, FilterResult, LayerInfo
