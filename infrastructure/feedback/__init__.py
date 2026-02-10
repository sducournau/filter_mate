"""
FilterMate Infrastructure Feedback.

User feedback utilities (message bar, dialogs, etc.) with backend awareness
and consistent formatting for QGIS message bar notifications.

Usage:
    from ...infrastructure.feedback import show_info, show_success, show_warning, show_error  # noqa: F401
    show_info("Operation completed")
    show_success("Filter applied successfully")
    show_warning("Large dataset detected")
    show_error("Connection failed")
"""

from qgis.core import Qgis  # noqa: F401

try:
    from ...config.feedback_config import should_show_message  # noqa: F401
except ImportError:
    def should_show_message(category):
        return True


# Backend display names and icons
BACKEND_INFO = {
    'postgresql': {'name': 'PostgreSQL', 'icon': '🐘', 'color': '#336791'},
    'postgresql (v4)': {'name': 'PostgreSQL v4', 'icon': '🐘✨', 'color': '#336791'},
    'postgresql (legacy)': {'name': 'PostgreSQL (Legacy)', 'icon': '🐘⚙️', 'color': '#336791'},
    'spatialite': {'name': 'Spatialite', 'icon': '💾', 'color': '#4A90E2'},
    'ogr': {'name': 'OGR', 'icon': '📁', 'color': '#7CB342'},
    'memory': {'name': 'Memory', 'icon': '⚡', 'color': '#FFA000'}
}


def get_backend_display_name(provider_type: str) -> str:
    """Get user-friendly display name for backend with icon."""
    backend = BACKEND_INFO.get(provider_type.lower(), {
        'name': provider_type.title(), 'icon': '❓', 'color': '#757575'
    })
    return f"{backend['icon']} {backend['name']}"


def show_info(message: str, title: str = "FilterMate"):
    """Show an info message in the QGIS message bar."""
    try:
        from qgis.utils import iface  # noqa: F401
        if iface and should_show_message('info'):
            iface.messageBar().pushInfo(title, message)
    except Exception:
        pass


def show_warning(message: str, title: str = "FilterMate"):
    """Show a warning message in the QGIS message bar."""
    try:
        from qgis.utils import iface  # noqa: F401
        if iface and should_show_message('warning'):
            iface.messageBar().pushWarning(title, message)
    except Exception:
        pass


def show_error(message: str, title: str = "FilterMate"):
    """Show an error message in the QGIS message bar."""
    try:
        from qgis.utils import iface  # noqa: F401
        if iface and should_show_message('error'):
            iface.messageBar().pushCritical(title, message)
    except Exception:
        pass


def show_success(message: str, title: str = "FilterMate"):
    """Show a success message in the QGIS message bar."""
    try:
        from qgis.utils import iface  # noqa: F401
        if iface and should_show_message('success'):
            iface.messageBar().pushSuccess(title, message)
    except Exception:
        pass


def show_progress_message(message: str, current: int = None, total: int = None):
    """Show progress message for long operations."""
    try:
        from qgis.utils import iface  # noqa: F401
        if current is not None and total is not None:
            full_message = f"{message} ({current}/{total})..."
        else:
            full_message = f"{message}..."

        if iface and should_show_message('progress_info'):
            iface.messageBar().pushInfo("FilterMate", full_message)
    except Exception:
        pass


def show_backend_info(provider_type: str, layer_count: int = 1,
                      operation: str = 'filter', is_fallback: bool = False):
    """Show informational message about which backend is being used."""
    try:
        from qgis.utils import iface  # noqa: F401
        backend_name = get_backend_display_name(provider_type)

        operation_text = {
            'filter': f"Starting filter on {layer_count} layer(s)",
            'unfilter': f"Removing filters from {layer_count} layer(s)",
            'reset': f"Resetting {layer_count} layer(s)",
            'export': f"Exporting {layer_count} layer(s)"
        }.get(operation, f"Processing {layer_count} layer(s)")

        if is_fallback:
            message = f"📦 OGR (fallback): {operation_text}..."
        else:
            message = f"{backend_name}: {operation_text}..."

        if iface and should_show_message('backend_info'):
            iface.messageBar().pushInfo("FilterMate", message)
    except Exception:
        pass


def show_success_with_backend(provider_type: str, operation: str = 'filter',
                              layer_count: int = 1, is_fallback: bool = False):
    """Show success message with backend information."""
    try:
        from qgis.utils import iface  # noqa: F401
        backend_name = get_backend_display_name(provider_type)

        operation_text = {
            'filter': f"Successfully filtered {layer_count} layer(s)",
            'unfilter': f"Successfully removed filters from {layer_count} layer(s)",
            'reset': f"Successfully reset {layer_count} layer(s)",
            'export': f"Successfully exported {layer_count} layer(s)"
        }.get(operation, f"Successfully processed {layer_count} layer(s)")

        if is_fallback:
            message = f"📦 OGR (fallback): {operation_text}"
        else:
            message = f"{backend_name}: {operation_text}"

        if iface:
            iface.messageBar().pushSuccess("FilterMate", message)
    except Exception:
        pass


def show_performance_warning(provider_type: str, feature_count: int):
    """Show performance warning for large datasets without PostgreSQL."""
    try:
        from qgis.utils import iface  # noqa: F401
        if provider_type == 'postgresql':
            return

        backend_name = get_backend_display_name(provider_type)

        if feature_count > 100000:
            message = (
                f"Large dataset ({feature_count:,} features) using {backend_name}. "
                "Consider using PostgreSQL for optimal performance."
            )
            if iface:
                iface.messageBar().pushWarning("FilterMate - Performance", message)
        elif feature_count > 50000:
            message = (
                f"Medium-large dataset ({feature_count:,} features) using {backend_name}. "
                "PostgreSQL recommended for better performance."
            )
            if iface:
                iface.messageBar().pushInfo("FilterMate - Performance", message)
    except Exception:
        pass


def show_error_with_context(error_message: str, provider_type: str = None,
                            operation: str = None):
    """Show error message with contextual information."""
    try:
        from qgis.utils import iface  # noqa: F401
        context_parts = []

        if provider_type:
            backend_name = get_backend_display_name(provider_type)
            context_parts.append(backend_name)

        if operation:
            context_parts.append(operation.title())

        if context_parts:
            prefix = " - ".join(context_parts)
            message = f"{prefix}: {error_message}"
        else:
            message = error_message

        if iface:
            iface.messageBar().pushCritical("FilterMate", message)
    except Exception:
        pass


def format_backend_summary(provider_counts: dict) -> str:
    """Format a summary of layers by backend type."""
    parts = []
    for provider_type, count in provider_counts.items():
        backend_name = get_backend_display_name(provider_type)
        parts.append(f"{backend_name}: {count}")
    return ", ".join(parts)


__all__ = [
    'BACKEND_INFO',
    'get_backend_display_name',
    'show_info',
    'show_warning',
    'show_error',
    'show_success',
    'show_progress_message',
    'show_backend_info',
    'show_success_with_backend',
    'show_performance_warning',
    'show_error_with_context',
    'format_backend_summary',
]
