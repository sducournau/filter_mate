"""
FilterMate Base Controller.

Abstract base class for all tab controllers in the MVC pattern.
Provides common infrastructure for signal management, lifecycle, and service access.
"""
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Optional, List, Callable, Any

from qgis.PyQt.QtCore import QObject

# Resolve metaclass conflict between QObject (sip.wrappertype) and ABC (ABCMeta)
# by creating a combined metaclass
try:
    from sip import wrappertype
    class QObjectABCMeta(wrappertype, ABCMeta):
        """Combined metaclass for QObject + ABC compatibility."""
        pass
except ImportError:
    # Fallback for different sip versions
    class QObjectABCMeta(type(QObject), ABCMeta):
        """Combined metaclass for QObject + ABC compatibility."""
        pass

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...core.services.filter_service import FilterService
    from ...adapters.qgis.signals.signal_manager import SignalManager


class BaseController(QObject, metaclass=QObjectABCMeta):
    """
    Abstract base class for all tab controllers.

    Provides common infrastructure for:
    - PyQt signal support (inherits QObject)
    - Signal management via SignalManager
    - Service access (FilterService, etc.)
    - Lifecycle management (setup/teardown)
    - Tab activation/deactivation hooks

    Usage:
        class MyController(BaseController):
            my_signal = pyqtSignal(str)  # Can use signals!
            
            def setup(self) -> None:
                self._connect_signal(widget, 'clicked', self._on_click)

            def teardown(self) -> None:
                self._disconnect_all_signals()

            def on_tab_activated(self) -> None:
                super().on_tab_activated()
                self._refresh_data()
    """

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        filter_service: Optional['FilterService'] = None,
        signal_manager: Optional['SignalManager'] = None
    ):
        """
        Initialize the controller.

        Args:
            dockwidget: Parent dockwidget for UI access
            filter_service: Filter service for business logic
            signal_manager: Centralized signal manager for connections
        """
        # Initialize QObject with dockwidget as parent for proper Qt object tree
        super().__init__(dockwidget if dockwidget else None)
        self._dockwidget = dockwidget
        self._filter_service = filter_service
        self._signal_manager = signal_manager
        self._is_active: bool = False
        self._connection_ids: List[str] = []

    # === Properties ===

    @property
    def dockwidget(self) -> 'FilterMateDockWidget':
        """Access to parent dockwidget for UI operations."""
        return self._dockwidget

    @property
    def filter_service(self) -> Optional['FilterService']:
        """Access to filter service for business logic."""
        return self._filter_service

    @property
    def signal_manager(self) -> Optional['SignalManager']:
        """Access to centralized signal manager."""
        return self._signal_manager

    @property
    def is_active(self) -> bool:
        """Whether this controller's tab is currently active."""
        return self._is_active

    # === Abstract Methods (must be implemented by subclasses) ===

    @abstractmethod
    def setup(self) -> None:
        """
        Initialize the controller.

        Called once during dockwidget initialization.
        Set up widgets, connect signals, initialize state.

        Subclasses MUST call super().setup() if they override.
        """

    @abstractmethod
    def teardown(self) -> None:
        """
        Clean up the controller.

        Called when dockwidget is closing.
        Disconnect signals, release resources.

        Subclasses MUST call super().teardown() if they override.
        """

    # === Tab Lifecycle Hooks ===

    def on_tab_activated(self) -> None:
        """
        Called when this controller's tab becomes active.

        Override to refresh data or update UI.
        Always call super().on_tab_activated() first.
        """
        self._is_active = True

    def on_tab_deactivated(self) -> None:
        """
        Called when switching away from this controller's tab.

        Override to save state or cancel pending operations.
        Always call super().on_tab_deactivated() first.
        """
        self._is_active = False

    # === Signal Management Helpers ===

    def _connect_signal(
        self,
        sender: Any,
        signal_name: str,
        receiver: Callable,
        context: Optional[str] = None
    ) -> Optional[str]:
        """
        Connect a signal using SignalManager and track the connection.

        Args:
            sender: Object emitting the signal
            signal_name: Name of the signal (e.g., 'clicked', 'valueChanged')
            receiver: Slot/callback to receive the signal
            context: Optional context for debugging (defaults to class name)

        Returns:
            Connection ID for manual disconnection, or None if no SignalManager

        Example:
            self._connect_signal(
                self.dockwidget.buttonFilter,
                'clicked',
                self._on_filter_clicked,
                'filtering'
            )
        """
        if self._signal_manager is None:
            # Fallback: direct connection without tracking
            try:
                signal = getattr(sender, signal_name)
                signal.connect(receiver)
            except (AttributeError, RuntimeError):
                pass
            return None

        try:
            conn_id = self._signal_manager.connect(
                sender=sender,
                signal_name=signal_name,
                receiver=receiver,
                context=context or self.__class__.__name__
            )
            self._connection_ids.append(conn_id)
            return conn_id
        except (ValueError, RuntimeError) as e:
            # Log error but don't crash
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to connect signal {signal_name}: {e}"
            )
            return None

    def _disconnect_signal(self, connection_id: str) -> bool:
        """
        Disconnect a specific signal by connection ID.

        Args:
            connection_id: The ID returned from _connect_signal()

        Returns:
            True if successfully disconnected, False otherwise
        """
        if self._signal_manager is None:
            return False

        if connection_id in self._connection_ids:
            success = self._signal_manager.disconnect(connection_id)
            if success:
                self._connection_ids.remove(connection_id)
            return success
        return False

    def _disconnect_all_signals(self) -> int:
        """
        Disconnect all signals registered by this controller.

        Returns:
            Number of signals successfully disconnected
        """
        if self._signal_manager is None:
            self._connection_ids.clear()
            return 0

        count = 0
        for conn_id in list(self._connection_ids):
            if self._signal_manager.disconnect(conn_id):
                count += 1
        self._connection_ids.clear()
        return count

    # === Utility Methods ===

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            from ...config.config import ENV_VARS
            return ENV_VARS.get(key, default)
        except ImportError:
            return default

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<{self.__class__.__name__} "
            f"active={self._is_active} "
            f"connections={len(self._connection_ids)}>"
        )
