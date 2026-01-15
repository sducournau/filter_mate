"""
State management infrastructure.

Provides thread-safe state management utilities for FilterMate,
including flags for coordinating asynchronous operations.

Migrated from before_migration/modules/flag_manager.py (January 2026)
"""

from .flag_manager import (
    FlagState,
    FlagStats,
    TimedFlag,
    AtomicFlag,
    TemporaryFlag,
    FlagManager,
    get_loading_flag,
    get_initializing_flag,
    get_processing_flag
)

__all__ = [
    'FlagState',
    'FlagStats',
    'TimedFlag',
    'AtomicFlag',
    'TemporaryFlag',
    'FlagManager',
    'get_loading_flag',
    'get_initializing_flag',
    'get_processing_flag'
]
