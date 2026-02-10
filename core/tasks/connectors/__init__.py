"""
Task-level connectors.

This package contains connector classes extracted from FilterEngineTask
as part of Phase E13 refactoring (January 2026).
"""

from .backend_connector import BackendConnector  # noqa: F401

__all__ = ['BackendConnector']
