"""
FilterMate Signal Manager.

Centralized signal management with tracking and cleanup.
Reduces coupling and prevents memory leaks from untracked connections.

Story: MIG-084
Phase: 6 - God Class DockWidget Migration
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Callable, Optional, List, Any, Iterator
from weakref import ref
import logging

logger = logging.getLogger(__name__)


@dataclass
class SignalConnection:
    """Tracked signal connection metadata."""
    id: str
    sender_ref: Any  # weakref to sender
    signal_name: str
    receiver: Callable
    context: Optional[str] = None

    @property
    def sender(self):
        """Get sender if still alive."""
        if self.sender_ref is None:
            return None
        obj = self.sender_ref()
        return obj


class SignalManager:
    """
    Centralized signal management with tracking and cleanup.

    Features:
    - Connection tracking with unique IDs
    - Automatic cleanup on shutdown
    - Debug logging for signal events
    - Context-based grouping for bulk operations
    - Weak references to prevent memory leaks

    Usage:
        signal_manager = SignalManager(debug=True)

        # Connect with tracking
        conn_id = signal_manager.connect(
            sender=my_button,
            signal_name='clicked',
            receiver=self.on_button_clicked,
            context='main_ui'
        )

        # Disconnect by ID
        signal_manager.disconnect(conn_id)

        # Disconnect all from context
        signal_manager.disconnect_by_context('main_ui')

        # Full cleanup
        signal_manager.cleanup()
    """

    def __init__(self, debug: bool = False):
        """
        Initialize SignalManager.

        Args:
            debug: Enable debug logging for signal events
        """
        self._connections: Dict[str, SignalConnection] = {}
        self._counter = 0
        self._debug = debug
        self._blocked_contexts: set = set()

    def connect(
        self,
        sender,
        signal_name: str,
        receiver: Callable,
        context: str = None
    ) -> str:
        """
        Connect a signal and track it.

        Args:
            sender: Object emitting the signal (QObject or any object with signals)
            signal_name: Name of the signal (e.g., 'clicked', 'valueChanged')
            receiver: Slot/callback to receive the signal
            context: Optional context string for grouping (e.g., 'layer_signals', 'ui_buttons')

        Returns:
            Connection ID string for later disconnection

        Raises:
            ValueError: If signal not found on sender
            RuntimeError: If sender is deleted
        """
        # Check sender is valid
        try:
            signal = getattr(sender, signal_name, None)
        except RuntimeError as e:
            raise RuntimeError(f"Sender object is deleted: {e}")

        if signal is None:
            raise ValueError(
                f"Signal '{signal_name}' not found on {type(sender).__name__}"
            )

        # Connect the signal
        signal.connect(receiver)

        # Generate unique ID
        self._counter += 1
        conn_id = f"sig_{self._counter:05d}"

        # Create weak reference to sender
        try:
            sender_ref = ref(sender)
        except TypeError:
            # Some objects can't be weakly referenced
            sender_ref = lambda: sender  # noqa: E731

        # Store connection metadata
        self._connections[conn_id] = SignalConnection(
            id=conn_id,
            sender_ref=sender_ref,
            signal_name=signal_name,
            receiver=receiver,
            context=context
        )

        if self._debug:
            sender_name = type(sender).__name__
            receiver_name = getattr(receiver, '__name__', repr(receiver))
            logger.debug(
                f"Connected {conn_id}: {sender_name}.{signal_name} -> "
                f"{receiver_name} [{context or 'no context'}]"
            )

        return conn_id

    def disconnect(self, connection_id: str) -> bool:
        """
        Disconnect a specific signal by connection ID.

        Args:
            connection_id: The ID returned from connect()

        Returns:
            True if disconnected successfully, False if not found
        """
        if connection_id not in self._connections:
            if self._debug:
                logger.debug(f"Connection {connection_id} not found")
            return False

        conn = self._connections[connection_id]
        sender = conn.sender

        if sender is not None:
            try:
                signal = getattr(sender, conn.signal_name)
                signal.disconnect(conn.receiver)
                if self._debug:
                    logger.debug(f"Disconnected {connection_id}")
            except (RuntimeError, TypeError) as e:
                # Object deleted or signal already disconnected
                if self._debug:
                    logger.warning(f"Failed to disconnect {connection_id}: {e}")
        else:
            if self._debug:
                logger.debug(f"Sender for {connection_id} already deleted")

        del self._connections[connection_id]
        return True

    def disconnect_by_sender(self, sender) -> int:
        """
        Disconnect all signals from a specific sender.

        Args:
            sender: The sender object to disconnect all signals from

        Returns:
            Number of connections disconnected
        """
        count = 0
        for conn_id in list(self._connections.keys()):
            conn = self._connections.get(conn_id)
            if conn and conn.sender is sender:
                if self.disconnect(conn_id):
                    count += 1

        if self._debug and count > 0:
            logger.debug(f"Disconnected {count} signals from {type(sender).__name__}")

        return count

    def disconnect_by_context(self, context: str) -> int:
        """
        Disconnect all signals with a specific context.

        Args:
            context: The context string to match

        Returns:
            Number of connections disconnected
        """
        count = 0
        for conn_id in list(self._connections.keys()):
            conn = self._connections.get(conn_id)
            if conn and conn.context == context:
                if self.disconnect(conn_id):
                    count += 1

        if self._debug and count > 0:
            logger.debug(f"Disconnected {count} signals with context '{context}'")

        return count

    def disconnect_all(self) -> int:
        """
        Disconnect all tracked signals.

        Returns:
            Number of connections disconnected
        """
        count = 0
        for conn_id in list(self._connections.keys()):
            if self.disconnect(conn_id):
                count += 1

        if self._debug:
            logger.debug(f"Disconnected all {count} signals")

        return count

    def block_context(self, context: str):
        """
        Block all signals for a context (temporarily).

        Args:
            context: The context to block
        """
        self._blocked_contexts.add(context)

        for conn in self._connections.values():
            if conn.context == context:
                sender = conn.sender
                if sender is not None:
                    try:
                        signal = getattr(sender, conn.signal_name)
                        signal.disconnect(conn.receiver)
                    except (RuntimeError, TypeError):
                        pass

        if self._debug:
            logger.debug(f"Blocked context '{context}'")

    def unblock_context(self, context: str):
        """
        Unblock a previously blocked context.

        Args:
            context: The context to unblock
        """
        self._blocked_contexts.discard(context)

        for conn in self._connections.values():
            if conn.context == context:
                sender = conn.sender
                if sender is not None:
                    try:
                        signal = getattr(sender, conn.signal_name)
                        signal.connect(conn.receiver)
                    except (RuntimeError, TypeError):
                        pass

        if self._debug:
            logger.debug(f"Unblocked context '{context}'")

    def is_context_blocked(self, context: str) -> bool:
        """Check if a context is currently blocked."""
        return context in self._blocked_contexts

    def get_connection_count(self) -> int:
        """
        Get number of active tracked connections.

        Returns:
            Number of connections
        """
        return len(self._connections)

    def get_connections_by_context(self, context: str) -> List[str]:
        """
        Get all connection IDs for a context.

        Args:
            context: The context to filter by

        Returns:
            List of connection IDs
        """
        return [
            conn.id for conn in self._connections.values()
            if conn.context == context
        ]

    def get_connections_summary(self) -> str:
        """
        Get a human-readable summary of all connections.

        Returns:
            Multi-line string summary
        """
        lines = [f"SignalManager: {len(self._connections)} active connections"]

        # Group by context
        by_context: Dict[str, List[SignalConnection]] = {}
        for conn in self._connections.values():
            ctx = conn.context or "(no context)"
            if ctx not in by_context:
                by_context[ctx] = []
            by_context[ctx].append(conn)

        for ctx, conns in sorted(by_context.items()):
            blocked = " [BLOCKED]" if ctx in self._blocked_contexts else ""
            lines.append(f"\n  [{ctx}]{blocked} ({len(conns)} connections):")
            for conn in conns:
                sender = conn.sender
                sender_name = type(sender).__name__ if sender else "(deleted)"
                receiver_name = getattr(conn.receiver, '__name__', '?')
                lines.append(
                    f"    {conn.id}: {sender_name}.{conn.signal_name} -> {receiver_name}"
                )

        return "\n".join(lines)

    def prune_dead_connections(self) -> int:
        """
        Remove connections where sender has been deleted.

        Returns:
            Number of dead connections pruned
        """
        count = 0
        for conn_id in list(self._connections.keys()):
            conn = self._connections.get(conn_id)
            if conn and conn.sender is None:
                del self._connections[conn_id]
                count += 1

        if self._debug and count > 0:
            logger.debug(f"Pruned {count} dead connections")

        return count

    def cleanup(self):
        """
        Full cleanup - disconnect all and clear state.

        Call this on application shutdown.
        """
        self.disconnect_all()
        self._connections.clear()
        self._blocked_contexts.clear()
        self._counter = 0

        if self._debug:
            logger.debug("SignalManager fully cleaned up")

    def is_connected(self, connection_id: str) -> bool:
        """
        Check if a specific connection is still active.

        Args:
            connection_id: The connection ID to check

        Returns:
            True if connection exists and sender is still alive
        """
        if connection_id not in self._connections:
            return False

        conn = self._connections[connection_id]
        return conn.sender is not None

    def is_signal_connected_by_name(
        self,
        sender,
        signal_name: str
    ) -> bool:
        """
        Check if a signal is connected from a specific sender.

        Args:
            sender: The sender object
            signal_name: Name of the signal

        Returns:
            True if any connection exists for this sender/signal
        """
        for conn in self._connections.values():
            if conn.sender is sender and conn.signal_name == signal_name:
                return True
        return False

    def force_reconnect_context(self, context: str) -> int:
        """
        Force reconnect all signals in a context.

        Disconnects and reconnects to ensure clean state.

        Args:
            context: The context to reconnect

        Returns:
            Number of signals reconnected
        """
        count = 0
        for conn in list(self._connections.values()):
            if conn.context != context:
                continue

            sender = conn.sender
            if sender is None:
                continue

            try:
                signal = getattr(sender, conn.signal_name)
                # Disconnect
                try:
                    signal.disconnect(conn.receiver)
                except (RuntimeError, TypeError):
                    pass
                # Reconnect
                signal.connect(conn.receiver)
                count += 1
            except (RuntimeError, AttributeError) as e:
                if self._debug:
                    logger.warning(f"Failed to reconnect {conn.id}: {e}")

        if self._debug:
            logger.debug(f"Force reconnected {count} signals in '{context}'")

        return count

    def force_reconnect_action_signals(self) -> int:
        """
        Force reconnect all action-related signals.

        Convenience method for action buttons and toolbar items.

        Returns:
            Number of signals reconnected
        """
        return self.force_reconnect_context('actions')

    def force_reconnect_exploring_signals(self) -> int:
        """
        Force reconnect all exploring-related signals.

        Convenience method for exploring groupboxes and widgets.

        Returns:
            Number of signals reconnected
        """
        return self.force_reconnect_context('exploring')

    @contextmanager
    def block_all_signals(self) -> Iterator[None]:
        """
        Context manager to temporarily block all tracked signals.

        Usage:
            with signal_manager.block_all_signals():
                # Do work without triggering signals
                update_ui_elements()

        Yields:
            None
        """
        disconnected = []

        try:
            # Disconnect all signals temporarily
            for conn in self._connections.values():
                sender = conn.sender
                if sender is not None:
                    try:
                        signal = getattr(sender, conn.signal_name)
                        signal.disconnect(conn.receiver)
                        disconnected.append(conn)
                    except (RuntimeError, TypeError):
                        pass

            if self._debug:
                logger.debug(f"Blocked {len(disconnected)} signals")

            yield

        finally:
            # Reconnect all signals
            reconnected = 0
            for conn in disconnected:
                sender = conn.sender
                if sender is not None:
                    try:
                        signal = getattr(sender, conn.signal_name)
                        signal.connect(conn.receiver)
                        reconnected += 1
                    except (RuntimeError, TypeError):
                        pass

            if self._debug:
                logger.debug(f"Unblocked {reconnected} signals")

    @contextmanager
    def block_context_signals(self, context: str) -> Iterator[None]:
        """
        Context manager to temporarily block signals for a specific context.

        Args:
            context: The context to block

        Yields:
            None
        """
        self.block_context(context)
        try:
            yield
        finally:
            self.unblock_context(context)

    def __len__(self) -> int:
        """Return number of active connections."""
        return len(self._connections)

    def __repr__(self) -> str:
        """String representation."""
        return f"<SignalManager: {len(self._connections)} connections>"
