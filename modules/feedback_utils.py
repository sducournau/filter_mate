"""
FilterMate User Feedback Utilities

This module provides standardized user feedback messages with backend awareness
and consistent formatting for QGIS message bar notifications.

Usage:
    from modules.feedback_utils import show_backend_info, show_progress_message
    
    show_backend_info(iface, 'postgresql', layer_count=5)
    show_progress_message(iface, 'Filtering layers', progress=3, total=10)
"""

from qgis.core import Qgis

try:
    from config.feedback_config import should_show_message
except ImportError:
    # Fallback if config module not available
    def should_show_message(category):
        return True  # Show all messages by default


# =============================================================================
# Generic Feedback Functions (for centralized message bar access)
# =============================================================================

def show_info(message: str, title: str = "FilterMate"):
    """
    Show an info message in the QGIS message bar.
    
    Args:
        message: The message to display
        title: The message title (default: "FilterMate")
    
    Example:
        >>> show_info("Operation completed successfully")
    """
    try:
        from qgis.utils import iface
        if iface and should_show_message('info'):
            iface.messageBar().pushInfo(title, message)
    except Exception:
        pass  # Graceful fallback if iface not available


def show_warning(message: str, title: str = "FilterMate"):
    """
    Show a warning message in the QGIS message bar.
    
    Args:
        message: The message to display
        title: The message title (default: "FilterMate")
    
    Example:
        >>> show_warning("Large dataset detected. Performance may be reduced.")
    """
    try:
        from qgis.utils import iface
        if iface and should_show_message('warning'):
            iface.messageBar().pushWarning(title, message)
    except Exception:
        pass  # Graceful fallback if iface not available


def show_error(message: str, title: str = "FilterMate"):
    """
    Show an error message in the QGIS message bar.
    
    Args:
        message: The message to display
        title: The message title (default: "FilterMate")
    
    Example:
        >>> show_error("Failed to apply filter: connection refused")
    """
    try:
        from qgis.utils import iface
        if iface and should_show_message('error'):
            iface.messageBar().pushCritical(title, message)
    except Exception:
        pass  # Graceful fallback if iface not available


def show_success(message: str, title: str = "FilterMate"):
    """
    Show a success message in the QGIS message bar.
    
    Args:
        message: The message to display
        title: The message title (default: "FilterMate")
    
    Example:
        >>> show_success("Filter applied successfully")
    """
    try:
        from qgis.utils import iface
        if iface and should_show_message('success'):
            iface.messageBar().pushSuccess(title, message)
    except Exception:
        pass  # Graceful fallback if iface not available


# Backend display names and icons
BACKEND_INFO = {
    'postgresql': {
        'name': 'PostgreSQL',
        'icon': '🐘',
        'description': 'High-performance database backend',
        'color': '#336791'
    },
    'spatialite': {
        'name': 'Spatialite',
        'icon': '💾',
        'description': 'File-based database backend',
        'color': '#4A90E2'
    },
    'ogr': {
        'name': 'OGR',
        'icon': '📁',
        'description': 'File-based data source',
        'color': '#7CB342'
    },
    'memory': {
        'name': 'Memory',
        'icon': '⚡',
        'description': 'Temporary in-memory layer',
        'color': '#FFA000'
    }
}


def get_backend_display_name(provider_type):
    """
    Get user-friendly display name for backend.
    
    Args:
        provider_type (str): Backend type ('postgresql', 'spatialite', 'ogr', etc.)
    
    Returns:
        str: Display name with icon (e.g., '🐘 PostgreSQL')
    """
    backend = BACKEND_INFO.get(provider_type.lower(), {
        'name': provider_type.title(),
        'icon': '❓',
        'description': 'Unknown backend',
        'color': '#757575'
    })
    return f"{backend['icon']} {backend['name']}"


def show_backend_info(iface, provider_type, layer_count=1, operation='filter', duration=3, is_fallback=False):
    """
    Show informational message about which backend is being used.
    
    Args:
        iface: QGIS interface object
        provider_type (str): Backend type ('postgresql', 'spatialite', 'ogr')
        layer_count (int): Number of layers being processed
        operation (str): Operation type ('filter', 'export', 'reset')
        duration (int): Message duration in seconds (default: 3)
        is_fallback (bool): True if using OGR as fallback for PostgreSQL layer
    
    Example:
        >>> show_backend_info(iface, 'postgresql', layer_count=5)
        # Shows: "FilterMate - 🐘 PostgreSQL: Starting filter on 5 layer(s)..."
    """
    backend_name = get_backend_display_name(provider_type)
    
    operation_text = {
        'filter': f"Starting filter on {layer_count} layer(s)",
        'unfilter': f"Removing filters from {layer_count} layer(s)",
        'reset': f"Resetting {layer_count} layer(s)",
        'export': f"Exporting {layer_count} layer(s)"
    }.get(operation, f"Processing {layer_count} layer(s)")
    
    # Add fallback indicator for PostgreSQL layers using OGR
    if is_fallback:
        message = f"💾 OGR (fallback for PostgreSQL): {operation_text}..."
    else:
        message = f"{backend_name}: {operation_text}..."
    
    if should_show_message('backend_info'):
        iface.messageBar().pushInfo("FilterMate", message)


def show_progress_message(iface, operation, current=None, total=None, duration=2):
    """
    Show progress message for long operations.
    
    Args:
        iface: QGIS interface object
        operation (str): Operation description (e.g., 'Filtering layers')
        current (int, optional): Current item number
        total (int, optional): Total number of items
        duration (int): Message duration in seconds (default: 2)
    
    Example:
        >>> show_progress_message(iface, 'Filtering layers', current=3, total=10)
        # Shows: "FilterMate: Filtering layers (3/10)..."
    """
    if current is not None and total is not None:
        message = f"{operation} ({current}/{total})..."
    else:
        message = f"{operation}..."
    
    if should_show_message('progress_info'):
        iface.messageBar().pushInfo("FilterMate", message)


def show_success_with_backend(iface, provider_type, operation='filter', layer_count=1, duration=3):
    """
    Show success message with backend information.
    
    Args:
        iface: QGIS interface object
        provider_type (str): Backend type
        operation (str): Operation type
        layer_count (int): Number of layers processed
        duration (int): Message duration in seconds (default: 3)
    
    Example:
        >>> show_success_with_backend(iface, 'postgresql', 'filter', layer_count=5)
        # Shows: "FilterMate - 🐘 PostgreSQL: Successfully filtered 5 layer(s)"
    """
    backend_name = get_backend_display_name(provider_type)
    
    operation_text = {
        'filter': f"Successfully filtered {layer_count} layer(s)",
        'unfilter': f"Successfully removed filters from {layer_count} layer(s)",
        'reset': f"Successfully reset {layer_count} layer(s)",
        'export': f"Successfully exported {layer_count} layer(s)"
    }.get(operation, f"Successfully processed {layer_count} layer(s)")
    
    message = f"{backend_name}: {operation_text}"
    
    iface.messageBar().pushSuccess("FilterMate", message)


def show_performance_warning(iface, provider_type, feature_count, duration=10):
    """
    Show performance warning for large datasets without PostgreSQL.
    
    Args:
        iface: QGIS interface object
        provider_type (str): Backend type being used
        feature_count (int): Number of features in dataset
        duration (int): Message duration in seconds (default: 10)
    
    Example:
        >>> show_performance_warning(iface, 'spatialite', 150000)
        # Shows warning about large dataset without PostgreSQL
    """
    if provider_type == 'postgresql':
        return  # No warning needed for PostgreSQL
    
    backend_name = get_backend_display_name(provider_type)
    
    if feature_count > 100000:
        message = (
            f"Large dataset ({feature_count:,} features) using {backend_name}. "
            "Performance may be reduced. Consider using PostgreSQL for optimal performance."
        )
        iface.messageBar().pushWarning("FilterMate - Performance", message)
    elif feature_count > 50000:
        message = (
            f"Medium-large dataset ({feature_count:,} features) using {backend_name}. "
            "PostgreSQL recommended for better performance."
        )
        iface.messageBar().pushInfo("FilterMate - Performance", message)


def show_error_with_context(iface, error_message, provider_type=None, operation=None, duration=5):
    """
    Show error message with contextual information.
    
    Args:
        iface: QGIS interface object
        error_message (str): Error description
        provider_type (str, optional): Backend type where error occurred
        operation (str, optional): Operation that failed
        duration (int): Message duration in seconds (default: 5)
    
    Example:
        >>> show_error_with_context(iface, "Connection failed", 'postgresql', 'filter')
        # Shows: "FilterMate - 🐘 PostgreSQL: Filter failed - Connection failed"
    """
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
    
    iface.messageBar().pushCritical("FilterMate", message)


def format_backend_summary(provider_counts):
    """
    Format a summary of layers by backend type.
    
    Args:
        provider_counts (dict): Dictionary of provider_type -> count
    
    Returns:
        str: Formatted summary (e.g., "🐘 PostgreSQL: 3, 💾 Spatialite: 2")
    
    Example:
        >>> counts = {'postgresql': 3, 'spatialite': 2}
        >>> format_backend_summary(counts)
        "🐘 PostgreSQL: 3, 💾 Spatialite: 2"
    """
    parts = []
    for provider_type, count in provider_counts.items():
        backend_name = get_backend_display_name(provider_type)
        parts.append(f"{backend_name}: {count}")
    return ", ".join(parts)
