---
sidebar_position: 6
---

# Undo/Redo System

FilterMate v2.3.0+ includes a **global undo/redo system with intelligent context detection**, allowing you to easily revert filtering operations.

## Overview

The undo/redo system tracks all filtering operations and provides:

- **Global Undo/Redo**: Works across all layers in your project
- **Intelligent Context Detection**: Automatically detects source-only vs. multi-layer operations
- **Per-Layer History**: Maintains separate history for each layer
- **Smart Button Management**: Automatically enables/disables based on available history
- **Keyboard Shortcuts**: Standard Ctrl+Z / Ctrl+Y (Cmd+Z / Cmd+Y on macOS)

## Key Concepts

### Operation Types

FilterMate tracks two types of operations:

1. **Source-Only Operations**
   - Filtering applied only to the source layer
   - No geometric predicates involved
   - Expression-based filtering
   - **Undo affects**: Source layer only

2. **Multi-Layer Operations**
   - Filtering with geometric predicates (intersects, contains, etc.)
   - Involves source layer + filtered layers
   - **Undo affects**: All involved layers

### History Scope

**Global History**: Shared across all layers
- All operations stored chronologically
- Undo/redo works project-wide
- Preserved during QGIS session (lost on project close)

**Per-Layer History**: Individual layer tracking
- Each layer maintains its own filter state
- Allows precise restoration
- Independent of other layers

## How to Use

### Basic Undo/Redo

1. **Apply a filter** using FilterMate
2. **Click Undo button** (or press Ctrl+Z) to revert
3. **Click Redo button** (or press Ctrl+Shift+Z) to reapply

:::tip Button States
- **Enabled** ✅: History available
- **Disabled** ❌: No history to undo/redo
- **Tooltip**: Shows what will be undone/redone
:::

### Intelligent Context Detection

FilterMate automatically detects operation scope:

#### Example 1: Source-Only Filtering

```sql
-- User filters buildings layer by attribute
population > 10000
```

**Undo behavior**:
- ✅ Reverts filter on `buildings` layer
- ❌ Does NOT affect other layers
- 📝 Removes last entry from source layer history only

#### Example 2: Multi-Layer Geometric Filtering

```sql
-- User filters buildings within selected district
```

**Undo behavior**:
- ✅ Reverts filter on `buildings` layer (filtered layer)
- ✅ Clears selection on `districts` layer (source layer)
- 📝 Removes entries from both layers' histories

## User Interface

### Undo/Redo Buttons

Located in the FilterMate toolbar:

```
[🔄 Reload] [↶ Undo] [↷ Redo] [Filter] [Export]
              ↑ Ctrl+Z   ↑ Ctrl+Shift+Z
```

**Button Tooltips** show:
- Number of available undo/redo operations
- Last operation description
- Affected layers

### Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|--------------|-------|
| **Undo** | `Ctrl+Z` | `Cmd+Z` |
| **Redo** | `Ctrl+Shift+Z` | `Cmd+Shift+Z` |

:::note
Keyboard shortcuts are only active when FilterMate panel has focus.
:::

## Technical Details

### Architecture

**Components**:

1. **FilterHistory** (`modules/filter_history.py`)
   - Main history manager
   - Stores operations in chronological order
   - Provides undo/redo logic

2. **FilterMateApp.handle_undo()** (`filter_mate_app.py`)
   - Intelligent context detection
   - Determines operation scope
   - Restores layer states

3. **FilterMateApp.update_undo_redo_buttons()**
   - Updates button states
   - Manages tooltips
   - Enables/disables based on history

### History Entry Structure

Each history entry contains:

```python
{
    "timestamp": "2025-12-18T14:30:00",
    "source_layer_id": "layer_abc123",
    "source_layer_name": "Districts",
    "source_expression": "id = 5",
    "filtered_layers": [
        {
            "layer_id": "layer_xyz789",
            "layer_name": "Buildings",
            "previous_filter": "population > 5000",
            "new_filter": "population > 10000",
            "geometric_predicates": ["intersects"],
            "buffer_distance": 0
        }
    ],
    "is_global": True  # Affects multiple layers
}
```

### Context Detection Algorithm

```python
def handle_undo(self):
    """Intelligent undo with context detection."""
    
    # 1. Get last operation from global history
    last_op = self.history_manager.undo()
    
    # 2. Detect operation scope
    if last_op.get('filtered_layers'):
        # Multi-layer operation
        scope = 'global'
        affected_layers = [source] + filtered_layers
    else:
        # Source-only operation
        scope = 'source_only'
        affected_layers = [source]
    
    # 3. Restore layer states
    for layer in affected_layers:
        restore_previous_filter(layer)
    
    # 4. Update UI
    self.update_undo_redo_buttons()
    self.refresh_layers_and_canvas()
```

## Best Practices

### When to Use Undo/Redo

✅ **Good Use Cases**:
- Reverting incorrect filter expressions
- Testing different geometric predicates
- Comparing filtered results
- Quick exploration of data

❌ **Not Suitable For**:
- Long-term state management (use QGIS projects instead)
- Collaborative workflows (history is local)
- Export operations (use version control for outputs)

### History Limitations

**Size**: Limited to **50 operations** by default
- Oldest operations are removed when limit reached
- Configurable via `config.json` (future feature)

**Persistence**: History is **session-based**
- Lost when closing QGIS project
- Not saved with `.qgs` files
- Consider using named filters for permanent storage

**Scope**: **Per-QGIS-instance**
- Each QGIS instance has separate history
- Not synchronized across machines

## Troubleshooting

### Undo Button Disabled

**Symptom**: Undo button is grayed out

**Possible Causes**:
1. No operations performed yet
2. Already at oldest history point
3. History cleared (plugin reload, project change)

**Solution**: Apply a filter operation to create history

### Undo Doesn't Restore Expected State

**Symptom**: Undo restores wrong filter or affects wrong layers

**Diagnosis**:
- Check operation type in history tooltip
- Verify which layers were involved

**Solution**:
- Use multiple undo operations to reach desired state
- Review filter history in debug mode (F12 console)

### Performance with Large History

**Symptom**: Undo/redo becomes slow with many operations

**Solution**:
- Clear history using plugin reload (F5)
- Reduce history limit in configuration
- Use fewer exploratory operations

## Advanced Usage

### Programmatic Access

Python Console access to history:

```python
# Get FilterMate app instance
from filter_mate import FilterMate
app = FilterMate.instance().app

# Check history status
print(f"Can undo: {app.history_manager.can_undo()}")
print(f"Can redo: {app.history_manager.can_redo()}")

# Get history size
print(f"Operations: {len(app.history_manager.history)}")

# Clear history
app._clear_filter_history()
```

### Debug Mode

Enable detailed history logging:

```python
# In config.json
{
  "ENABLE_DEBUG_LOGGING": true
}
```

View logs in QGIS Python Console (Ctrl+Alt+P):
- Undo/redo operations
- Context detection results
- Layer state changes

## See Also

- [Filter History](../user-guide/filter-history.md) - User guide for filter history
- [Architecture Overview](../developer-guide/architecture.md) - Technical architecture
- [Configuration Guide](../advanced/configuration.md) - Configuration settings

## Version History

- **v2.3.0** - Initial undo/redo system with intelligent context detection
- **v2.3.7** - Improved button state management and tooltips
