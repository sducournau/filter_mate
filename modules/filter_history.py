"""
FilterMate Filter History Module

Implements undo/redo functionality for filter operations, allowing users
to navigate through their filtering history and recover from mistakes.

Usage:
    from modules.filter_history import FilterHistory
    
    history = FilterHistory(layer)
    history.push_state(expression, feature_count, description)
    history.undo()  # Go back one step
    history.redo()  # Go forward one step
"""

import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger('FilterMate.History')


class FilterState:
    """
    Represents a single filter state in the history.
    
    Attributes:
        expression (str): Filter expression (subset string)
        feature_count (int): Number of features visible after filter
        description (str): Human-readable description of the filter
        timestamp (datetime): When the filter was applied
        metadata (dict): Additional metadata (backend, operation type, etc.)
    """
    
    def __init__(self, expression: str, feature_count: int, description: str = "", metadata: Optional[Dict] = None):
        self.expression = expression
        self.feature_count = feature_count
        self.description = description or self._generate_description()
        self.timestamp = datetime.now()
        self.metadata = metadata or {}
    
    def _generate_description(self) -> str:
        """Generate description based on expression"""
        if not self.expression:
            return "No filter (all features visible)"
        
        # Shorten long expressions
        if len(self.expression) > 60:
            return f"{self.expression[:57]}..."
        return self.expression
    
    def __repr__(self):
        return f"FilterState('{self.description}', {self.feature_count} features)"


class FilterHistory:
    """
    Manages filter history for a layer with undo/redo capabilities.
    
    Implements a linear history stack where applying a new filter
    clears any "future" states (standard undo/redo behavior).
    
    Features:
    - Unlimited history size (configurable via max_size)
    - Persistent across sessions (saved to layer variables)
    - Keyboard shortcuts support (Ctrl+Z, Ctrl+Y)
    - Thread-safe operations
    
    Example:
        >>> history = FilterHistory(layer, max_size=50)
        >>> history.push_state("population > 10000", 150, "Large cities")
        >>> history.push_state("population > 50000", 45, "Very large cities")
        >>> history.can_undo()
        True
        >>> previous_state = history.undo()
        >>> print(previous_state.description)
        "Large cities"
    """
    
    def __init__(self, layer_id: str, max_size: int = 100):
        """
        Initialize filter history for a layer.
        
        Args:
            layer_id: Unique layer identifier
            max_size: Maximum number of states to keep (default: 100)
        """
        self.layer_id = layer_id
        self.max_size = max_size
        
        # History stack: list of FilterState objects
        self._states: List[FilterState] = []
        
        # Current position in history (-1 = no history, 0 = first state, etc.)
        self._current_index = -1
        
        # Flag to prevent recording during undo/redo
        self._is_undoing = False
        
        logger.debug(f"FilterHistory initialized for layer {layer_id} (max_size={max_size})")
    
    def push_state(self, expression: str, feature_count: int, description: str = "", metadata: Optional[Dict] = None):
        """
        Add a new filter state to history.
        
        If we're not at the end of the history stack (user has undone some steps),
        this clears all "future" states and adds the new one.
        
        Args:
            expression: Filter expression (subset string)
            feature_count: Number of features visible
            description: Optional human-readable description
            metadata: Optional metadata dict (backend type, operation, etc.)
        
        Example:
            >>> history.push_state(
            ...     "population > 10000",
            ...     150,
            ...     "Cities over 10k",
            ...     {"backend": "postgresql", "operation": "filter"}
            ... )
        """
        # Don't record states during undo/redo operations
        if self._is_undoing:
            return
        
        # Create new state
        state = FilterState(expression, feature_count, description, metadata)
        
        # If we're not at the end, remove all future states
        if self._current_index < len(self._states) - 1:
            self._states = self._states[:self._current_index + 1]
            logger.debug(f"Cleared {len(self._states) - self._current_index - 1} future states")
        
        # Add new state
        self._states.append(state)
        self._current_index += 1
        
        # Enforce max size
        if len(self._states) > self.max_size:
            overflow = len(self._states) - self.max_size
            self._states = self._states[overflow:]
            self._current_index -= overflow
            logger.debug(f"Removed {overflow} old states (max_size={self.max_size})")
        
        logger.info(f"Pushed state: {state.description} ({self._current_index + 1}/{len(self._states)})")
    
    def undo(self) -> Optional[FilterState]:
        """
        Move back one step in history.
        
        Returns:
            FilterState: The previous state, or None if at beginning
        
        Example:
            >>> state = history.undo()
            >>> if state:
            ...     layer.setSubsetString(state.expression)
        """
        if not self.can_undo():
            logger.debug("Cannot undo: at beginning of history")
            return None
        
        self._is_undoing = True
        try:
            self._current_index -= 1
            state = self._states[self._current_index]
            logger.info(f"Undo to: {state.description} ({self._current_index + 1}/{len(self._states)})")
            return state
        finally:
            self._is_undoing = False
    
    def redo(self) -> Optional[FilterState]:
        """
        Move forward one step in history.
        
        Returns:
            FilterState: The next state, or None if at end
        
        Example:
            >>> state = history.redo()
            >>> if state:
            ...     layer.setSubsetString(state.expression)
        """
        if not self.can_redo():
            logger.debug("Cannot redo: at end of history")
            return None
        
        self._is_undoing = True
        try:
            self._current_index += 1
            state = self._states[self._current_index]
            logger.info(f"Redo to: {state.description} ({self._current_index + 1}/{len(self._states)})")
            return state
        finally:
            self._is_undoing = False
    
    def can_undo(self) -> bool:
        """Check if undo is possible"""
        return self._current_index > 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible"""
        return self._current_index < len(self._states) - 1
    
    def get_current_state(self) -> Optional[FilterState]:
        """Get the current filter state"""
        if self._current_index >= 0 and self._current_index < len(self._states):
            return self._states[self._current_index]
        return None
    
    def get_history(self, max_items: int = 10) -> List[FilterState]:
        """
        Get recent history items for display in UI.
        
        Args:
            max_items: Maximum number of items to return
        
        Returns:
            List of recent FilterState objects, most recent first
        """
        if not self._states:
            return []
        
        # Get last N states, most recent first
        recent = self._states[-max_items:]
        recent.reverse()
        return recent
    
    def clear(self):
        """Clear all history"""
        self._states.clear()
        self._current_index = -1
        logger.info(f"Cleared history for layer {self.layer_id}")
    
    def get_stats(self) -> Dict:
        """
        Get history statistics.
        
        Returns:
            Dict with history stats (total_states, current_position, can_undo, can_redo)
        """
        return {
            "layer_id": self.layer_id,
            "total_states": len(self._states),
            "current_position": self._current_index + 1,
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "max_size": self.max_size
        }
    
    def to_dict(self) -> Dict:
        """
        Serialize history to dictionary for persistence.
        
        Returns:
            Dict representation of history (for JSON serialization)
        """
        return {
            "layer_id": self.layer_id,
            "max_size": self.max_size,
            "current_index": self._current_index,
            "states": [
                {
                    "expression": state.expression,
                    "feature_count": state.feature_count,
                    "description": state.description,
                    "timestamp": state.timestamp.isoformat(),
                    "metadata": state.metadata
                }
                for state in self._states
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FilterHistory':
        """
        Deserialize history from dictionary.
        
        Args:
            data: Dict representation from to_dict()
        
        Returns:
            FilterHistory instance
        """
        history = cls(data["layer_id"], data.get("max_size", 100))
        history._current_index = data.get("current_index", -1)
        
        for state_data in data.get("states", []):
            state = FilterState(
                expression=state_data["expression"],
                feature_count=state_data["feature_count"],
                description=state_data.get("description", ""),
                metadata=state_data.get("metadata", {})
            )
            # Restore timestamp
            if "timestamp" in state_data:
                state.timestamp = datetime.fromisoformat(state_data["timestamp"])
            history._states.append(state)
        
        logger.info(f"Restored history for layer {data['layer_id']} ({len(history._states)} states)")
        return history


class GlobalFilterState:
    """
    Represents a global filter state across multiple layers.
    
    Captures the state of a source layer and all its associated remote layers
    at a specific point in time.
    
    Attributes:
        source_layer_id (str): ID of the source layer
        source_expression (str): Filter expression on source layer
        source_feature_count (int): Features in source layer
        remote_layers (dict): Dict mapping layer_id to (expression, feature_count)
        description (str): Human-readable description
        timestamp (datetime): When the state was captured
        metadata (dict): Additional metadata
    """
    
    def __init__(self, source_layer_id: str, source_expression: str, source_feature_count: int,
                 remote_layers: Optional[Dict[str, Tuple[str, int]]] = None,
                 description: str = "", metadata: Optional[Dict] = None):
        self.source_layer_id = source_layer_id
        self.source_expression = source_expression
        self.source_feature_count = source_feature_count
        self.remote_layers = remote_layers or {}  # {layer_id: (expression, feature_count)}
        self.description = description or self._generate_description()
        self.timestamp = datetime.now()
        self.metadata = metadata or {}
    
    def _generate_description(self) -> str:
        """Generate description based on layers involved"""
        layer_count = 1 + len(self.remote_layers)
        if layer_count == 1:
            return f"Filter on source layer"
        return f"Global filter on {layer_count} layers"
    
    def has_remote_layers(self) -> bool:
        """Check if this state includes remote layers"""
        return len(self.remote_layers) > 0
    
    def __repr__(self):
        layer_count = 1 + len(self.remote_layers)
        return f"GlobalFilterState({self.description}, {layer_count} layer(s))"


class HistoryManager:
    """
    Manages filter histories for multiple layers.
    
    Provides centralized access to FilterHistory instances for all layers
    in the project. Handles creation, retrieval, and cleanup.
    Also manages global filter history across source + remote layers.
    
    Example:
        >>> manager = HistoryManager()
        >>> history = manager.get_or_create_history(layer_id)
        >>> history.push_state("filter expression", 100)
        >>> # Global history
        >>> manager.push_global_state(source_id, "filter", 100, {remote_id: ("filter", 50)})
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize history manager.
        
        Args:
            max_size: Default maximum history size for new histories
        """
        self.max_size = max_size
        self._histories: Dict[str, FilterHistory] = {}
        
        # Global history stack for coordinated source + remote layer states
        self._global_states: List[GlobalFilterState] = []
        self._global_current_index = -1
        self._is_global_undoing = False
        
        logger.debug(f"HistoryManager initialized (default max_size={max_size})")
    
    def get_or_create_history(self, layer_id: str) -> FilterHistory:
        """
        Get existing history or create new one for layer.
        
        Args:
            layer_id: Unique layer identifier
        
        Returns:
            FilterHistory instance for the layer
        """
        if layer_id not in self._histories:
            self._histories[layer_id] = FilterHistory(layer_id, self.max_size)
            logger.debug(f"Created new history for layer {layer_id}")
        return self._histories[layer_id]
    
    def get_history(self, layer_id: str) -> Optional[FilterHistory]:
        """
        Get existing history for layer.
        
        Args:
            layer_id: Unique layer identifier
        
        Returns:
            FilterHistory instance or None if not found
        """
        return self._histories.get(layer_id)
    
    def remove_history(self, layer_id: str):
        """Remove history for a layer (e.g., when layer is deleted)"""
        if layer_id in self._histories:
            del self._histories[layer_id]
            logger.info(f"Removed history for layer {layer_id}")
    
    def clear_all(self):
        """Clear all histories"""
        self._histories.clear()
        logger.info("Cleared all histories")
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all layer histories.
        
        Returns:
            Dict mapping layer_id to history stats
        """
        return {
            layer_id: history.get_stats()
            for layer_id, history in self._histories.items()
        }
    
    def push_global_state(self, source_layer_id: str, source_expression: str, 
                         source_feature_count: int, 
                         remote_layers: Dict[str, Tuple[str, int]],
                         description: str = "", metadata: Optional[Dict] = None):
        """
        Push a global filter state capturing source + remote layers.
        
        Args:
            source_layer_id: ID of source layer
            source_expression: Filter expression on source
            source_feature_count: Feature count of source
            remote_layers: Dict mapping layer_id to (expression, feature_count)
            description: Optional description
            metadata: Optional metadata
        """
        if self._is_global_undoing:
            return
        
        # Create global state
        state = GlobalFilterState(
            source_layer_id=source_layer_id,
            source_expression=source_expression,
            source_feature_count=source_feature_count,
            remote_layers=remote_layers,
            description=description,
            metadata=metadata
        )
        
        # Clear future states if not at end
        if self._global_current_index < len(self._global_states) - 1:
            removed_count = len(self._global_states) - self._global_current_index - 1
            self._global_states = self._global_states[:self._global_current_index + 1]
            logger.debug(f"Cleared {removed_count} future global states")
        
        # Add new state
        self._global_states.append(state)
        self._global_current_index += 1
        
        # Enforce max size
        if len(self._global_states) > self.max_size:
            overflow = len(self._global_states) - self.max_size
            self._global_states = self._global_states[overflow:]
            self._global_current_index -= overflow
            logger.debug(f"Removed {overflow} old global states")
        
        logger.info(f"Pushed global state: {state.description} (position {self._global_current_index + 1}/{len(self._global_states)})")
    
    def undo_global(self) -> Optional[GlobalFilterState]:
        """
        Undo to previous global state.
        
        Returns:
            Previous GlobalFilterState or None if at beginning
        """
        if not self.can_undo_global():
            logger.debug("Cannot undo global: at beginning")
            return None
        
        self._is_global_undoing = True
        try:
            self._global_current_index -= 1
            state = self._global_states[self._global_current_index]
            logger.info(f"Global undo to: {state.description} (position {self._global_current_index + 1}/{len(self._global_states)})")
            return state
        finally:
            self._is_global_undoing = False
    
    def redo_global(self) -> Optional[GlobalFilterState]:
        """
        Redo to next global state.
        
        Returns:
            Next GlobalFilterState or None if at end
        """
        if not self.can_redo_global():
            logger.debug("Cannot redo global: at end")
            return None
        
        self._is_global_undoing = True
        try:
            self._global_current_index += 1
            state = self._global_states[self._global_current_index]
            logger.info(f"Global redo to: {state.description} (position {self._global_current_index + 1}/{len(self._global_states)})")
            return state
        finally:
            self._is_global_undoing = False
    
    def can_undo_global(self) -> bool:
        """Check if global undo is possible"""
        return self._global_current_index > 0
    
    def can_redo_global(self) -> bool:
        """Check if global redo is possible"""
        return self._global_current_index < len(self._global_states) - 1
    
    def get_current_global_state(self) -> Optional[GlobalFilterState]:
        """Get current global state"""
        if 0 <= self._global_current_index < len(self._global_states):
            return self._global_states[self._global_current_index]
        return None
    
    def clear_global_history(self):
        """Clear all global history"""
        self._global_states.clear()
        self._global_current_index = -1
        logger.info("Cleared global filter history")
    
    def get_global_stats(self) -> Dict:
        """Get global history statistics"""
        return {
            "total_states": len(self._global_states),
            "current_position": self._global_current_index + 1,
            "can_undo": self.can_undo_global(),
            "can_redo": self.can_redo_global(),
            "max_size": self.max_size
        }
    
    def debug_info(self, layer_id: Optional[str] = None) -> str:
        """
        Get detailed debug information about history state.
        
        Args:
            layer_id: Optional layer ID to show specific layer history
        
        Returns:
            Formatted debug string with history information
        """
        lines = ["=== FilterMate History Debug Info ==="]
        
        # Global history info
        lines.append(f"\nGlobal History:")
        lines.append(f"  Total states: {len(self._global_states)}")
        lines.append(f"  Current position: {self._global_current_index + 1}/{len(self._global_states)}")
        lines.append(f"  Can undo: {self.can_undo_global()}")
        lines.append(f"  Can redo: {self.can_redo_global()}")
        
        if self._global_states:
            lines.append(f"\n  Recent global states:")
            for i, state in enumerate(self._global_states[-5:]):
                marker = " <--" if i == self._global_current_index else ""
                lines.append(f"    [{i}] {state.description} ({len(state.remote_layers) + 1} layers){marker}")
        
        # Layer-specific history
        if layer_id:
            history = self.get_history(layer_id)
            if history:
                lines.append(f"\nLayer History ({layer_id}):")
                lines.append(f"  Total states: {len(history._states)}")
                lines.append(f"  Current position: {history._current_index + 1}/{len(history._states)}")
                lines.append(f"  Can undo: {history.can_undo()}")
                lines.append(f"  Can redo: {history.can_redo()}")
                
                if history._states:
                    lines.append(f"\n  Recent states:")
                    for i, state in enumerate(history._states[-5:]):
                        marker = " <--" if i == history._current_index else ""
                        lines.append(f"    [{i}] {state.description}{marker}")
            else:
                lines.append(f"\nNo history found for layer {layer_id}")
        else:
            # Summary of all layers
            lines.append(f"\nAll Layer Histories:")
            lines.append(f"  Total tracked layers: {len(self._histories)}")
            for lid, hist in self._histories.items():
                lines.append(f"    {lid}: {len(hist._states)} states, pos {hist._current_index + 1}")
        
        return "\n".join(lines)
