"""
ExploringSignalManager - Centralized Signal Lifecycle Management

Purpose:
    Manages all PyQt signal connections for the FilterMate Exploring tab.
    Provides auto-healing, health monitoring, and atomic operations.

Author: Winston (Solution Architect) + Amelia (Developer)
Date: 2026-01-15
Related ADR: ADR-008-ExploringSignalManager.md
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Callable, Optional
from qgis.PyQt.QtCore import QObject
from infrastructure.logging.logger import LoggerManager

logger = LoggerManager.get_logger("signal_manager")


@dataclass
class SignalConnection:
    """
    Metadata for a single signal connection.
    
    Attributes:
        signal_id: Unique identifier (e.g., "SINGLE_EXPRESSION.fieldChanged")
        widget_or_layer: QObject emitting the signal
        signal_name: Name of the signal (e.g., "fieldChanged")
        handler: Slot/callback function
        auto_reconnect: Enable auto-healing for this signal
        connected_at: Timestamp of last successful connection
        is_connected: Current connection status
    """
    signal_id: str
    widget_or_layer: QObject
    signal_name: str
    handler: Callable
    auto_reconnect: bool = True
    connected_at: Optional[datetime] = None
    is_connected: bool = False


class ExploringSignalManager:
    """
    Centralized manager for all Exploring tab signal connections.
    
    Responsibilities:
        - Maintain registry of all signal connections
        - Provide atomic connect/disconnect/reconnect operations
        - Implement auto-healing for lost signals
        - Expose health check API
    
    Usage:
        manager = ExploringSignalManager(dockwidget, controller)
        manager.register_and_connect(
            "SINGLE_EXPRESSION.fieldChanged",
            widget,
            "fieldChanged",
            handler_function
        )
        
        # After widget reload
        manager.reconnect_all()
        
        # Check health
        health = manager.health_check()
    """
    
    def __init__(self, dockwidget, controller):
        """
        Initialize signal manager.
        
        Args:
            dockwidget: FilterMateDockWidget instance (owner)
            controller: ExploringController instance (business logic)
        """
        self.dockwidget = dockwidget
        self.controller = controller
        self.signal_registry: Dict[str, SignalConnection] = {}
        self.auto_heal_enabled = True
        self.max_heal_attempts = 3
        self.heal_attempt_count: Dict[str, int] = {}
        
        logger.info("ExploringSignalManager initialized")
    
    def register_and_connect(
        self,
        signal_id: str,
        widget_or_layer: QObject,
        signal_name: str,
        handler: Callable,
        auto_reconnect: bool = True
    ) -> bool:
        """
        Register a signal in the registry and connect it immediately.
        
        Args:
            signal_id: Unique identifier (e.g., "SINGLE_EXPRESSION.fieldChanged")
            widget_or_layer: QObject emitting the signal
            signal_name: Name of the signal attribute (e.g., "fieldChanged")
            handler: Slot/callback function
            auto_reconnect: Enable auto-healing for this signal
        
        Returns:
            True if registration and connection successful
        
        Example:
            manager.register_and_connect(
                "SINGLE_EXPRESSION.fieldChanged",
                self.mFieldExpressionWidget_exploring_single_selection,
                "fieldChanged",
                lambda field: self._refresh_feature_pickers_for_field_change("single_selection", field)
            )
        """
        # TODO Phase 2.1: Implementation
        # 1. Create SignalConnection object
        # 2. Add to signal_registry
        # 3. Call _connect_signal()
        # 4. Update connected_at timestamp
        # 5. Log success/failure
        pass
    
    def disconnect(self, signal_id: str) -> bool:
        """
        Disconnect a specific signal by ID.
        
        Args:
            signal_id: Unique identifier of signal to disconnect
        
        Returns:
            True if disconnection successful
        """
        # TODO Phase 2.1: Implementation
        # 1. Check signal exists in registry
        # 2. Call _disconnect_signal()
        # 3. Update is_connected flag
        # 4. Log result
        pass
    
    def disconnect_all(self) -> int:
        """
        Disconnect ALL registered signals atomically.
        
        Returns:
            Number of signals successfully disconnected
        
        Note:
            This is idempotent - safe to call multiple times.
            Used before widget reload operations.
        """
        # TODO Phase 2.2: Implementation
        # 1. Iterate signal_registry
        # 2. Call _disconnect_signal() for each
        # 3. Count successes
        # 4. Log summary
        pass
    
    def reconnect_all(self) -> int:
        """
        Reconnect ALL registered signals atomically.
        
        Returns:
            Number of signals successfully reconnected
        
        Note:
            This is the CRITICAL method for fixing signal loss.
            Guarantees 100% reconnection (atomic operation).
            Used after widget reload operations.
        """
        # TODO Phase 2.2: Implementation
        # 1. Iterate signal_registry
        # 2. Call _connect_signal() for each
        # 3. Update connected_at timestamps
        # 4. Reset heal_attempt_count
        # 5. Log summary
        pass
    
    def health_check(self) -> Dict[str, bool]:
        """
        Check connection health of all registered signals.
        
        Returns:
            Dictionary mapping signal_id to connection status
            Example: {"SINGLE_EXPRESSION.fieldChanged": True, "LAYER.selectionChanged": False}
        
        Note:
            If auto_heal_enabled=True, will attempt to heal failed signals.
        """
        # TODO Phase 2.3: Implementation
        # 1. Iterate signal_registry
        # 2. For each signal, check is_connected flag
        # 3. If auto_heal_enabled and not connected, attempt heal
        # 4. Respect max_heal_attempts (circuit breaker)
        # 5. Return health status dict
        pass
    
    def _connect_signal(self, connection: SignalConnection) -> bool:
        """
        Internal: Connect a single signal (idempotent).
        
        Args:
            connection: SignalConnection object
        
        Returns:
            True if connection successful
        """
        # TODO Phase 2.1: Implementation
        # 1. Get signal from widget_or_layer using signal_name
        # 2. Disconnect first (idempotent - ignore TypeError)
        # 3. Connect to handler
        # 4. Update connection metadata
        # 5. Return success status
        pass
    
    def _disconnect_signal(self, connection: SignalConnection) -> bool:
        """
        Internal: Disconnect a single signal (idempotent).
        
        Args:
            connection: SignalConnection object
        
        Returns:
            True if disconnection successful
        """
        # TODO Phase 2.1: Implementation
        # 1. Get signal from widget_or_layer
        # 2. Disconnect (ignore TypeError if not connected)
        # 3. Update is_connected flag
        # 4. Return success status
        pass
    
    def _auto_heal_signal(self, connection: SignalConnection) -> bool:
        """
        Internal: Auto-heal a lost signal connection.
        
        Args:
            connection: SignalConnection object with is_connected=False
        
        Returns:
            True if healing successful
        
        Note:
            Respects max_heal_attempts to prevent infinite loops.
        """
        # TODO Phase 2.3: Implementation
        # 1. Check heal_attempt_count < max_heal_attempts
        # 2. Increment heal_attempt_count
        # 3. Call _connect_signal()
        # 4. Log heal attempt
        # 5. Return success status
        pass
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about signal manager state.
        
        Returns:
            Dictionary with stats:
            - total_signals: Number of registered signals
            - connected_signals: Number currently connected
            - auto_heal_enabled: Whether auto-healing is active
            - heal_attempts: Dict of heal attempt counts
        """
        # TODO Phase 2.4: Implementation (nice-to-have)
        pass
    
    def __repr__(self) -> str:
        return f"<ExploringSignalManager: {len(self.signal_registry)} signals registered>"
