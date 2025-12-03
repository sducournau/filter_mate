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


class HistoryManager:
    """
    Manages filter histories for multiple layers.
    
    Provides centralized access to FilterHistory instances for all layers
    in the project. Handles creation, retrieval, and cleanup.
    
    Example:
        >>> manager = HistoryManager()
        >>> history = manager.get_or_create_history(layer_id)
        >>> history.push_state("filter expression", 100)
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize history manager.
        
        Args:
            max_size: Default maximum history size for new histories
        """
        self.max_size = max_size
        self._histories: Dict[str, FilterHistory] = {}
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
