"""
Infrastructure Parallel Package

Provides multi-threaded execution utilities for FilterMate operations.
Uses ThreadPoolExecutor for efficient parallel processing on multi-core systems.

This is part of the Hexagonal Architecture - Infrastructure Layer.

Exported Symbols:
    - FilterResult: Dataclass for single layer filtering result
    - ParallelFilterExecutor: Multi-threaded executor for layer filtering
    - ParallelConfig: Configuration for parallel execution tuning

Thread Safety:
    - QGIS layers (QgsVectorLayer) are NOT thread-safe
    - OGR operations MUST run sequentially (direct layer manipulation)
    - PostgreSQL/Spatialite CAN run in parallel (database-only operations)
    - Geometric filtering MUST run sequentially (uses selectByLocation)

Performance:
    - 2-4× faster on multi-core systems for database-backed layers
    - Configurable thread pool size based on CPU count
    - Adaptive delays for SQLite databases to prevent locking

Migration History:
    - v3.0: Created infrastructure/parallel/ package (EPIC-1)
    - v3.0: Migrated from modules/tasks/parallel_executor.py
"""

from .parallel_executor import (
    FilterResult,
    ParallelFilterExecutor,
    ParallelConfig
)

__all__ = [
    'FilterResult',
    'ParallelFilterExecutor',
    'ParallelConfig'
]
