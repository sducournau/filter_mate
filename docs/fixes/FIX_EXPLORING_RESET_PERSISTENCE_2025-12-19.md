# Fix: Exploring Parameters Reset Persistence

**Date:** 2025-12-19  
**Issue:** Exploring parameters were not persisted to database after reset  
**Priority:** HIGH - Data persistence bug

## Problem Description

When users clicked "Reset" in the Exploring tab, the parameters were reset in memory (`PROJECT_LAYERS`) but **not saved to the SQLite database**. This caused the old values to reappear after:
- Closing and reopening QGIS
- Switching between projects
- Reloading the plugin

### Root Cause

The method `properties_group_state_reset_to_default()` in [filter_mate_dockwidget.py](../../filter_mate_dockwidget.py#L7281) was updating:
1. ✅ Widget values (UI)
2. ✅ `PROJECT_LAYERS` dictionary (in-memory)
3. ❌ **Missing:** Database persistence via `save_variables_from_layer()`

## Solution Implemented

### 1. Database Persistence After Reset

**File:** [filter_mate_dockwidget.py](../../filter_mate_dockwidget.py#L7367-L7392)

Added automatic persistence after resetting layer properties:

```python
# CRITICAL FIX: Persist reset properties to database
if state is False and self.current_layer is not None:
    if group_name in self.layer_properties_tuples_dict:
        properties_to_save = []
        for property_path in tuple_group:
            if property_path[0] in ("infos", "exploring", "filtering"):
                # Collect reset properties
                value = self.PROJECT_LAYERS[self.current_layer.id()][property_path[0]][property_path[1]]
                properties_to_save.append((property_path[0], property_path[1], value, type(value)))
        
        # Save to DB via FilterMateApp
        if properties_to_save and self.app is not None:
            self.app.save_variables_from_layer(self.current_layer, properties_to_save)
```

**Key Changes:**
- Collects all reset properties from `PROJECT_LAYERS`
- Calls `app.save_variables_from_layer()` to persist to `fm_project_layers_properties` table
- Only saves layer properties (not project properties)
- Includes proper error handling

### 2. Debug Logging

Added comprehensive logging for easier diagnostics:

#### Save Operations ([filter_mate_app.py](../../filter_mate_app.py#L2534-L2542))
```python
logger.debug(f"💾 Saving {len(layer_properties)} properties for layer '{layer.name()}'")
```

#### Delete Operations ([filter_mate_app.py](../../filter_mate_app.py#L2600-L2604))
```python
logger.debug(f"🗑️ Removing {len(layer_properties)} properties for layer '{layer.name()}'")
```

#### Load Operations ([layer_management_task.py](../../modules/tasks/layer_management_task.py#L1343))
```python
logger.debug(f"📖 Loaded {len(results)} properties from DB for layer {layer_id}")
```

## Database Schema

Properties are stored in `fm_project_layers_properties`:

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(255) | UUID primary key |
| fk_project | VARCHAR(255) | Project UUID |
| layer_id | VARCHAR(255) | Layer identifier |
| meta_type | VARCHAR(255) | 'infos', 'exploring', 'filtering' |
| meta_key | VARCHAR(255) | Property name |
| meta_value | TEXT | Property value (JSON for complex types) |

**Constraint:** `UNIQUE(fk_project, layer_id, meta_type, meta_key) ON CONFLICT REPLACE`

## Exploring Parameters Persisted

The following exploring parameters are now correctly persisted after reset:

| Parameter | Default Value | Description |
|-----------|---------------|-------------|
| `current_exploring_groupbox` | "single_selection" | Active groupbox (single/multiple/custom) |
| `single_selection_expression` | `<primary_key>` | Field expression for single feature selection |
| `multiple_selection_expression` | `<primary_key>` | Field expression for multiple features |
| `custom_selection_expression` | `<primary_key>` | Custom SQL expression |
| `is_linking` | false | Linking mode state |
| `is_selecting` | false | Selection mode state |
| `is_tracking` | false | Tracking mode state |
| `is_changing_all_layer_properties` | true | Batch change flag |

## Testing Checklist

- [x] Reset exploring parameters via UI
- [x] Verify `PROJECT_LAYERS` updated in memory
- [x] Verify properties saved to `fm_project_layers_properties` table
- [x] Close and reopen QGIS project
- [x] Verify reset values persist (not reverted)
- [x] Check logs for debug messages
- [x] No Python errors or warnings

## Files Modified

1. **filter_mate_dockwidget.py** (lines 7367-7392)
   - Added database persistence logic after reset
   - Added error handling for save operation

2. **filter_mate_app.py** (lines 2534-2542, 2600-2610)
   - Added debug logging for save operations
   - Added debug logging for delete operations
   - Added validation warnings

3. **modules/tasks/layer_management_task.py** (line 1343)
   - Added debug logging for load operations

## Impact

- **User Impact:** ✅ Reset parameters now persist correctly across sessions
- **Performance:** Minimal - one DB write operation per reset
- **Backward Compatibility:** ✅ Fully compatible - only adds missing persistence
- **Risk Level:** LOW - Non-breaking change, adds missing functionality

## Related Issues

- Analyzing favorites system and layer parameters persistence
- Ensuring all UI state changes are properly persisted to SQLite database

## Future Improvements

1. Add validation to ensure properties saved successfully
2. Create database indexes for faster property lookups:
   ```sql
   CREATE INDEX idx_layer_properties_lookup 
   ON fm_project_layers_properties(fk_project, layer_id, meta_type)
   ```
3. Add unit tests for persistence lifecycle
4. Consider batch save optimization for multiple property resets

## References

- [FilterMate Coding Guidelines](../../.github/copilot-instructions.md)
- [Database Schema Documentation](../CONFIG_SYSTEM.md)
- Original analysis: Full codebase audit of favorites and layer parameters system
