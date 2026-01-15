"""
History Service.

Undo/redo history management for filter operations.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)


class LayerHistory:
    """
    Per-layer history wrapper for backward compatibility with old HistoryManager API.
    
    This class provides the old FilterHistory-like interface while delegating
    to the global HistoryService. It's used by undo_redo_handler.py which expects
    the old per-layer API.
    """
    
    def __init__(self, layer_id: str, parent_service: 'HistoryService'):
        """
        Initialize per-layer history wrapper.
        
        Args:
            layer_id: Layer ID this wrapper represents
            parent_service: Parent HistoryService instance
        """
        self.layer_id = layer_id
        self._parent = parent_service
        self._states = []  # Simulated per-layer states for compatibility
    
    def push_state(self, expression: str, feature_count: int, 
                   description: str = "", metadata: Optional[Dict] = None):
        """
        Push a filter state for this layer (compatibility method).
        
        This creates a HistoryEntry and pushes it to the parent service.
        
        Args:
            expression: Filter expression
            feature_count: Feature count (stored in metadata)
            description: Optional description
            metadata: Optional metadata
        """
        # Build metadata with feature count
        full_metadata = metadata or {}
        full_metadata['feature_count'] = feature_count
        
        # Create history entry
        entry = HistoryEntry.create(
            expression=expression,
            layer_ids=[self.layer_id],
            previous_filters=[],  # Will be filled by caller if needed
            description=description or f"Filter on layer {self.layer_id}",
            metadata=full_metadata
        )
        
        # Add to simulated per-layer states
        self._states.append({
            'expression': expression,
            'feature_count': feature_count,
            'description': description,
            'timestamp': entry.timestamp,
            'metadata': full_metadata
        })
        
        logger.debug(f"LayerHistory: Pushed state for layer {self.layer_id}")


@dataclass(frozen=True)
class HistoryEntry:
    """
    Immutable history entry for a filter operation.

    Contains all information needed to undo/redo a filter operation,
    including the previous state of affected layers.

    Attributes:
        entry_id: Unique identifier for this entry
        expression: The filter expression applied
        layer_ids: Tuple of layer IDs that were filtered
        previous_filters: Tuple of (layer_id, previous_subset_string) pairs
        timestamp: When the operation was performed
        description: Human-readable description
        metadata: Additional metadata (optional)
    """
    entry_id: str
    expression: str
    layer_ids: tuple
    previous_filters: tuple  # ((layer_id, previous_subset_string), ...)
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""
    metadata: tuple = field(default_factory=tuple)  # Immutable metadata

    @classmethod
    def create(
        cls,
        expression: str,
        layer_ids: List[str],
        previous_filters: List[tuple],
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'HistoryEntry':
        """
        Factory method for creating history entry.
        
        Args:
            expression: Filter expression applied
            layer_ids: List of layer IDs affected
            previous_filters: List of (layer_id, previous_filter) tuples
            description: Human-readable description
            metadata: Optional additional metadata
            
        Returns:
            New HistoryEntry instance
        """
        # Generate unique ID
        entry_id = f"hist_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Create description if not provided
        if not description:
            expr_preview = expression[:30] + "..." if len(expression) > 30 else expression
            description = f"Filter: {expr_preview}"
        
        # Convert metadata to immutable tuple of tuples
        meta_tuple = tuple(sorted(metadata.items())) if metadata else tuple()
        
        return cls(
            entry_id=entry_id,
            expression=expression,
            layer_ids=tuple(layer_ids),
            previous_filters=tuple(tuple(pf) for pf in previous_filters),
            description=description,
            metadata=meta_tuple
        )

    @property
    def layer_count(self) -> int:
        """Number of layers affected."""
        return len(self.layer_ids)

    @property
    def has_previous_filters(self) -> bool:
        """Check if there are previous filters to restore."""
        return len(self.previous_filters) > 0

    def get_previous_filter(self, layer_id: str) -> Optional[str]:
        """
        Get previous filter for a specific layer.
        
        Args:
            layer_id: Layer ID to look up
            
        Returns:
            Previous filter string or None
        """
        for lid, prev_filter in self.previous_filters:
            if lid == layer_id:
                return prev_filter
        return None

    def get_metadata_value(self, key: str) -> Optional[Any]:
        """Get value from metadata by key."""
        for k, v in self.metadata:
            if k == key:
                return v
        return None

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"HistoryEntry({self.entry_id}: {self.description})"


@dataclass
class HistoryState:
    """
    State information about history position.
    
    Attributes:
        can_undo: Whether undo is available
        can_redo: Whether redo is available
        undo_description: Description of next undo action
        redo_description: Description of next redo action
        undo_count: Number of available undo steps
        redo_count: Number of available redo steps
    """
    can_undo: bool
    can_redo: bool
    undo_description: str
    redo_description: str
    undo_count: int
    redo_count: int


class HistoryService:
    """
    Service for managing filter operation history.

    Provides undo/redo functionality with configurable history depth
    and optional change notifications.

    The service maintains two stacks:
    - Undo stack: Operations that can be undone
    - Redo stack: Operations that can be redone (cleared on new operation)

    Example:
        history = HistoryService(max_depth=50)
        
        # Record a filter operation
        entry = HistoryEntry.create(
            expression="name = 'test'",
            layer_ids=["layer_123"],
            previous_filters=[("layer_123", "")]
        )
        history.push(entry)
        
        # Undo
        if history.can_undo:
            undone = history.undo()
            # Restore layer filters from undone.previous_filters
        
        # Redo
        if history.can_redo:
            redone = history.redo()
            # Reapply filter from redone.expression
    """

    def __init__(
        self,
        max_depth: int = 50,
        on_change: Optional[Callable[['HistoryState'], None]] = None
    ):
        """
        Initialize HistoryService.

        Args:
            max_depth: Maximum history entries to keep
            on_change: Callback when history state changes
        """
        self._undo_stack: deque = deque(maxlen=max_depth)
        self._redo_stack: deque = deque(maxlen=max_depth)
        self._max_depth = max_depth
        self._on_change = on_change
        self._is_performing_undo_redo = False
        
        # Per-layer history wrappers (for backward compatibility)
        self._layer_histories: Dict[str, LayerHistory] = {}

    def push(self, entry: HistoryEntry) -> None:
        """
        Push a new history entry.

        Clears redo stack when a new operation is performed
        (can't redo after a new operation).

        Args:
            entry: History entry to push
        """
        if self._is_performing_undo_redo:
            # Don't push during undo/redo operations
            return
            
        self._undo_stack.append(entry)
        self._redo_stack.clear()
        self._notify_change()
        
        logger.debug(f"History: pushed {entry.entry_id}, undo depth={len(self._undo_stack)}")

    def undo(self) -> Optional[HistoryEntry]:
        """
        Pop from undo stack and push to redo.

        Returns:
            The entry being undone, or None if stack empty
        """
        if not self._undo_stack:
            return None

        self._is_performing_undo_redo = True
        try:
            entry = self._undo_stack.pop()
            self._redo_stack.append(entry)
            self._notify_change()
            
            logger.debug(f"History: undo {entry.entry_id}")
            return entry
        finally:
            self._is_performing_undo_redo = False

    def redo(self) -> Optional[HistoryEntry]:
        """
        Pop from redo stack and push to undo.

        Returns:
            The entry being redone, or None if stack empty
        """
        if not self._redo_stack:
            return None

        self._is_performing_undo_redo = True
        try:
            entry = self._redo_stack.pop()
            self._undo_stack.append(entry)
            self._notify_change()
            
            logger.debug(f"History: redo {entry.entry_id}")
            return entry
        finally:
            self._is_performing_undo_redo = False

    def peek_undo(self) -> Optional[HistoryEntry]:
        """
        Peek at next undo entry without modifying stacks.
        
        Returns:
            Next entry to undo, or None if stack empty
        """
        return self._undo_stack[-1] if self._undo_stack else None

    def peek_redo(self) -> Optional[HistoryEntry]:
        """
        Peek at next redo entry without modifying stacks.
        
        Returns:
            Next entry to redo, or None if stack empty
        """
        return self._redo_stack[-1] if self._redo_stack else None

    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0

    @property
    def undo_count(self) -> int:
        """Number of available undo steps."""
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        """Number of available redo steps."""
        return len(self._redo_stack)

    @property
    def total_entries(self) -> int:
        """Total number of history entries."""
        return len(self._undo_stack) + len(self._redo_stack)

    def get_state(self) -> HistoryState:
        """
        Get current history state.
        
        Returns:
            HistoryState with current undo/redo availability
        """
        undo_desc = ""
        redo_desc = ""
        
        if self._undo_stack:
            undo_desc = self._undo_stack[-1].description
        if self._redo_stack:
            redo_desc = self._redo_stack[-1].description
            
        return HistoryState(
            can_undo=self.can_undo,
            can_redo=self.can_redo,
            undo_description=undo_desc,
            redo_description=redo_desc,
            undo_count=self.undo_count,
            redo_count=self.redo_count
        )

    def get_undo_stack(self) -> List[HistoryEntry]:
        """
        Get copy of undo stack (newest last).
        
        Returns:
            List of history entries
        """
        return list(self._undo_stack)

    def get_redo_stack(self) -> List[HistoryEntry]:
        """
        Get copy of redo stack (next-to-redo last).
        
        Returns:
            List of history entries
        """
        return list(self._redo_stack)

    def get_history_for_layer(self, layer_id: str) -> List[HistoryEntry]:
        """
        Get history entries that affected a specific layer.
        
        Args:
            layer_id: Layer ID to filter by
            
        Returns:
            List of relevant history entries (oldest first)
        """
        entries = []
        for entry in self._undo_stack:
            if layer_id in entry.layer_ids:
                entries.append(entry)
        return entries
    
    def get_or_create_history(self, layer_id: str) -> LayerHistory:
        """
        Get or create per-layer history wrapper (backward compatibility).
        
        This method provides compatibility with the old HistoryManager API
        that returned FilterHistory objects per layer.
        
        Args:
            layer_id: Layer ID
            
        Returns:
            LayerHistory wrapper for this layer
        """
        if layer_id not in self._layer_histories:
            self._layer_histories[layer_id] = LayerHistory(layer_id, self)
            logger.debug(f"Created LayerHistory wrapper for layer {layer_id}")
        return self._layer_histories[layer_id]

    def clear(self) -> int:
        """
        Clear all history.
        
        Returns:
            Number of entries cleared
        """
        count = len(self._undo_stack) + len(self._redo_stack)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify_change()
        
        logger.debug(f"History: cleared {count} entries")
        return count

    def clear_redo(self) -> int:
        """
        Clear redo stack only.
        
        Returns:
            Number of entries cleared
        """
        count = len(self._redo_stack)
        self._redo_stack.clear()
        self._notify_change()
        return count

    def set_on_change(
        self, 
        callback: Optional[Callable[['HistoryState'], None]]
    ) -> None:
        """
        Set or clear the change callback.
        
        Args:
            callback: Callback function or None to clear
        """
        self._on_change = callback

    def _notify_change(self) -> None:
        """Notify listener of state change."""
        if self._on_change:
            try:
                self._on_change(self.get_state())
            except Exception as e:
                logger.warning(f"History change callback failed: {e}")

    @property
    def max_depth(self) -> int:
        """Maximum history depth."""
        return self._max_depth

    def set_max_depth(self, depth: int) -> None:
        """
        Change maximum history depth.
        
        Note: Does not truncate existing entries beyond new depth.
        They will be removed as new entries are added.
        
        Args:
            depth: New maximum depth
        """
        if depth < 1:
            raise ValueError("Max depth must be at least 1")
        self._max_depth = depth
        # Recreate deques with new maxlen
        self._undo_stack = deque(self._undo_stack, maxlen=depth)
        self._redo_stack = deque(self._redo_stack, maxlen=depth)

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize history for persistence.
        
        Returns:
            Dictionary representation of history
        """
        def entry_to_dict(entry: HistoryEntry) -> Dict:
            return {
                'entry_id': entry.entry_id,
                'expression': entry.expression,
                'layer_ids': list(entry.layer_ids),
                'previous_filters': [list(pf) for pf in entry.previous_filters],
                'timestamp': entry.timestamp.isoformat(),
                'description': entry.description,
                'metadata': dict(entry.metadata),
            }
        
        return {
            'undo_stack': [entry_to_dict(e) for e in self._undo_stack],
            'redo_stack': [entry_to_dict(e) for e in self._redo_stack],
            'max_depth': self._max_depth,
        }

    def deserialize(self, data: Dict[str, Any]) -> None:
        """
        Restore history from serialized data.
        
        Args:
            data: Dictionary from serialize()
        """
        def dict_to_entry(d: Dict) -> HistoryEntry:
            return HistoryEntry(
                entry_id=d['entry_id'],
                expression=d['expression'],
                layer_ids=tuple(d['layer_ids']),
                previous_filters=tuple(tuple(pf) for pf in d['previous_filters']),
                timestamp=datetime.fromisoformat(d['timestamp']),
                description=d['description'],
                metadata=tuple(sorted(d.get('metadata', {}).items())),
            )
        
        self._max_depth = data.get('max_depth', 50)
        self._undo_stack = deque(
            [dict_to_entry(d) for d in data.get('undo_stack', [])],
            maxlen=self._max_depth
        )
        self._redo_stack = deque(
            [dict_to_entry(d) for d in data.get('redo_stack', [])],
            maxlen=self._max_depth
        )
        self._notify_change()

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"HistoryService(undo={self.undo_count}, redo={self.redo_count})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"HistoryService(undo_count={self.undo_count}, "
            f"redo_count={self.redo_count}, max_depth={self._max_depth})"
        )
