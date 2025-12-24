# Undo/Redo System - FilterMate v2.4.10

**Last Updated:** December 23, 2025
**Status:** ✅ Fully Implemented

## Overview

FilterMate implements an intelligent undo/redo system with context-aware behavior that handles both source layer filters and multi-layer filter operations.

## Architecture

### Core Classes

#### 1. FilterState (modules/filter_history.py)
Basic filter state for single layer:
```python
class FilterState:
    layer_id: str
    expression: str
    feature_count: int
    timestamp: datetime
    metadata: dict
```

#### 2. GlobalFilterState (modules/filter_history.py)
Multi-layer state for source + remote layers:
```python
class GlobalFilterState:
    source_layer_id: str
    source_expression: str
    source_feature_count: int
    remote_layers: Dict[str, Tuple[str, int]]  # {layer_id: (expression, count)}
    timestamp: datetime
    metadata: dict
    
    def has_remote_layers() -> bool
```

#### 3. FilterHistory (modules/filter_history.py)
Per-layer history management:
```python
class FilterHistory:
    - push_state(state)
    - undo() -> Optional[FilterState]
    - redo() -> Optional[FilterState]
    - can_undo() -> bool
    - can_redo() -> bool
    - get_current_state()
    - clear()
```

#### 4. HistoryManager (modules/filter_history.py)
Global history management:
```python
class HistoryManager:
    # Per-layer histories
    - get_or_create_history(layer_id) -> FilterHistory
    - get_history(layer_id) -> Optional[FilterHistory]
    - remove_history(layer_id)
    - clear_all()
    
    # Global history (source + remote layers)
    - push_global_state(state: GlobalFilterState)
    - undo_global() -> Optional[GlobalFilterState]
    - redo_global() -> Optional[GlobalFilterState]
    - can_undo_global() -> bool
    - can_redo_global() -> bool
    - get_current_global_state()
    - clear_global_history()
```

## Undo/Redo Logic

### Context Detection

The system uses intelligent context detection to choose the appropriate undo/redo mode:

#### Source Layer Only Mode
**When?** No remote layers are selected in "Layers to filter" list

**Behavior:**
- Uses per-layer `FilterHistory`
- Undo/redo affects only the source layer
- Fast, lightweight operations

#### Global Mode
**When?** Remote layers are selected AND have active filters

**Behavior:**
- Uses `GlobalFilterState` via `HistoryManager`
- Undo/redo affects ALL layers (source + remote) simultaneously
- Atomic state restoration

### Implementation in filter_mate_app.py

```python
def handle_undo(self):
    """Intelligent undo with context detection"""
    layer_id = self.current_layer_id
    
    # Check if we have remote layers with filters
    has_remote_filters = self._check_remote_filters()
    
    if has_remote_filters and self.history_manager.can_undo_global():
        # Global undo
        state = self.history_manager.undo_global()
        self._restore_global_state(state)
        show_info("Undo appliqué (toutes les couches)")
    elif self.history_manager.can_undo(layer_id):
        # Source-only undo
        state = self.history_manager.undo(layer_id)
        self._restore_layer_state(layer_id, state)
        show_info("Undo appliqué (couche source)")
    
    self.update_undo_redo_buttons()

def handle_redo(self):
    """Intelligent redo with context detection"""
    # Similar logic to handle_undo()
    ...

def update_undo_redo_buttons(self):
    """Update button enabled state based on history availability"""
    layer_id = self.current_layer_id
    
    can_undo = (self.history_manager.can_undo_global() or 
                self.history_manager.can_undo(layer_id))
    can_redo = (self.history_manager.can_redo_global() or 
                self.history_manager.can_redo(layer_id))
    
    self.dockwidget.pushButton_action_undo_filter.setEnabled(can_undo)
    self.dockwidget.pushButton_action_redo_filter.setEnabled(can_redo)
```

## State Capture Workflow

### When Filter is Applied

```
1. filter_engine_task_completed()
   ↓
2. _push_filter_to_history()
   ├─ Capture source layer state (FilterState)
   ├─ If remote layers exist:
   │   └─ Capture global state (GlobalFilterState)
   └─ Push to appropriate history
   ↓
3. update_undo_redo_buttons()
   └─ Enable undo button, disable redo
```

### When Undo is Triggered

```
1. handle_undo()
   ↓
2. Check context (source-only or global?)
   ↓
3a. Global mode:
    ├─ history_manager.undo_global()
    └─ Restore all layer expressions
   
3b. Source-only mode:
    ├─ history_manager.undo(layer_id)
    └─ Restore source layer expression only
   ↓
4. Refresh layers and canvas
   ↓
5. update_undo_redo_buttons()
```

## UI Integration

### Buttons
- `pushButton_action_undo_filter`: Undo button (connects to `handle_undo()`)
- `pushButton_action_redo_filter`: Redo button (connects to `handle_redo()`)

### Signals
- `currentLayerChanged`: Emitted when user switches layers
  - Connected to `update_undo_redo_buttons()` for immediate UI update

### User Feedback
- Success message indicates which mode was used
- "Undo appliqué (toutes les couches)" - Global mode
- "Undo appliqué (couche source)" - Source-only mode

## Configuration

### History Stack Size
- Default: 100 states per layer
- Global history: 100 states
- Configurable via HistoryManager initialization

### Memory Management
- States are lightweight (only expressions, not geometries)
- Automatic cleanup when layers are removed
- History cleared on project close

## Testing

### Test File: tests/test_undo_redo.py

**Test Categories:**
1. FilterState creation and representation
2. GlobalFilterState creation and remote layer detection
3. FilterHistory push/undo/redo operations
4. HistoryManager per-layer operations
5. HistoryManager global operations
6. Context detection logic
7. Button state updates

### Running Tests
```bash
pytest tests/test_undo_redo.py -v
```

## Documentation

- `docs/UNDO_REDO_IMPLEMENTATION.md`: Technical implementation guide
- `docs/USER_GUIDE_UNDO_REDO.md`: End-user documentation

## Files Modified

### filter_mate_app.py
- Added `handle_undo()` method
- Added `handle_redo()` method
- Added `update_undo_redo_buttons()` method
- Extended `_push_filter_to_history()` with global state support
- Connected button signals

### modules/filter_history.py
- Added `GlobalFilterState` class
- Extended `HistoryManager` with global history methods:
  - `push_global_state()`
  - `undo_global()`
  - `redo_global()`
  - `can_undo_global()`
  - `can_redo_global()`
  - `get_current_global_state()`
  - `clear_global_history()`

### filter_mate_dockwidget.py
- Added `currentLayerChanged` signal

## Usage Example

```python
# In filter_mate_app.py

# Connect buttons
self.dockwidget.pushButton_action_undo_filter.clicked.connect(self.handle_undo)
self.dockwidget.pushButton_action_redo_filter.clicked.connect(self.handle_redo)

# Connect layer change signal
self.dockwidget.currentLayerChanged.connect(self.update_undo_redo_buttons)

# When filter is applied:
def filter_engine_task_completed(self, result):
    # ... apply filter ...
    self._push_filter_to_history()
    self.update_undo_redo_buttons()
```

## Edge Cases Handled

1. **No history available**: Buttons disabled, no action on click
2. **Layer removed during session**: History cleaned up automatically
3. **Mixed mode transitions**: System adapts based on current layer selection
4. **Empty filter expressions**: Treated as valid state (clear filter)
5. **Rapid undo/redo**: Queue-based processing prevents race conditions
