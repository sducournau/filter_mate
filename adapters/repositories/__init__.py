"""
FilterMate Repository Adapters.

Data access patterns for configuration, favorites, and history.
"""

from .history_repository import (  # noqa: F401
    HistoryRepository,
    HistoryEntry,
    create_history_repository,
)

__all__ = [
    'HistoryRepository',
    'HistoryEntry',
    'create_history_repository',
]
