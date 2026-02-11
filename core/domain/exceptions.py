# -*- coding: utf-8 -*-
"""
FilterMate Domain Exceptions

Hierarchical exception system for FilterMate.
All plugin-specific exceptions inherit from FilterMateError,
enabling both fine-grained and broad exception handling.

Usage::

    from core.domain.exceptions import BackendError, PostgreSQLError

    try:
        execute_query(...)
    except PostgreSQLError as e:
        handle_pg_specific(e)
    except BackendError as e:
        handle_any_backend(e)
    except FilterMateError as e:
        handle_any_filtermate(e)
"""


# ──────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────

class FilterMateError(Exception):
    """Base exception for all FilterMate errors."""


# ──────────────────────────────────────────────
# Filter errors
# ──────────────────────────────────────────────

class FilterError(FilterMateError):
    """Error during a filter operation."""


class FilterExpressionError(FilterError):
    """Error building or validating a filter expression."""


class FilterTimeoutError(FilterError):
    """Filter operation exceeded the allowed time."""


class FilterCancelledError(FilterError):
    """Filter operation was cancelled by the user."""


# ──────────────────────────────────────────────
# Backend errors
# ──────────────────────────────────────────────

class BackendError(FilterMateError):
    """Error in a data backend (PostgreSQL, SpatiaLite, OGR, Memory)."""


class PostgreSQLError(BackendError):
    """Error specific to the PostgreSQL/PostGIS backend."""


class SpatialiteError(BackendError):
    """Error specific to the SpatiaLite backend."""


class OGRError(BackendError):
    """Error specific to the OGR backend."""


class BackendNotAvailableError(BackendError):
    """A required backend is not available (e.g. psycopg2 not installed)."""


# ──────────────────────────────────────────────
# Layer errors
# ──────────────────────────────────────────────

class LayerError(FilterMateError):
    """Error related to layer operations."""


class LayerInvalidError(LayerError):
    """Layer is invalid or has been deleted."""


class LayerNotFoundError(LayerError):
    """Layer could not be found in the project."""


class CRSMismatchError(LayerError):
    """Coordinate reference systems are incompatible."""


# ──────────────────────────────────────────────
# Export errors
# ──────────────────────────────────────────────

class ExportError(FilterMateError):
    """Error during an export operation."""


class ExportPathError(ExportError):
    """Export target path is invalid or inaccessible."""


class ExportFormatError(ExportError):
    """Requested export format is unsupported or misconfigured."""


# ──────────────────────────────────────────────
# Configuration & signals
# ──────────────────────────────────────────────

class ConfigurationError(FilterMateError):
    """Configuration is invalid or missing."""


class ExpressionValidationError(FilterMateError):
    """A QGIS expression failed validation."""


class SignalStateChangeError(FilterMateError):
    """Signal state change operation failed (block/unblock, connect/disconnect).

    Args:
        state: The signal state at the time of failure (True/False/None).
        widget_path: Path to the widget involved in the failure.
        message: Optional human-readable description.
    """

    def __init__(self, state=None, widget_path=None, message=""):
        self.state = state
        self.widget_path = widget_path or []
        self.message = message or f"Signal state change failed for {widget_path}"
        super().__init__(self.message)


__all__ = [
    # Base
    'FilterMateError',
    # Filter
    'FilterError',
    'FilterExpressionError',
    'FilterTimeoutError',
    'FilterCancelledError',
    # Backend
    'BackendError',
    'PostgreSQLError',
    'SpatialiteError',
    'OGRError',
    'BackendNotAvailableError',
    # Layer
    'LayerError',
    'LayerInvalidError',
    'LayerNotFoundError',
    'CRSMismatchError',
    # Export
    'ExportError',
    'ExportPathError',
    'ExportFormatError',
    # Configuration & signals
    'ConfigurationError',
    'ExpressionValidationError',
    'SignalStateChangeError',
]
