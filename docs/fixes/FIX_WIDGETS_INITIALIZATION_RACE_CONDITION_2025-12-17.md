# Fix: Widgets Initialization Race Condition

**Date:** 2025-12-17  
**Issue:** Filter functionality completely broken - infinite retry loop  
**Root Cause:** Race condition in signal emission timing  
**Status:** ✅ FIXED

## Problem Description

### Symptoms
- Filter button clicked but no filtering occurs
- Infinite loop: "Task 'filter' called before dockwidget is ready for filtering, deferring by 500ms..."
- `_widgets_ready` flag permanently stuck at `False`
- No traceback or error messages

### Root Cause Analysis

**Race condition in signal/slot connection timing:**

1. `FilterMateApp.run()` creates dockwidget:
   ```python
   self.dockwidget = FilterMateDockWidget(...)  # Line ~328
   ```

2. **Inside `FilterMateDockWidget.__init__()`:**
   - Calls `setupUiCustom()` → `dockwidget_widgets_configuration()`
   - **Emits `widgetsInitialized` signal** ← Signal emitted at 12:26:28

3. **After dockwidget creation** in `FilterMateApp.run()`:
   ```python
   self.dockwidget.widgetsInitialized.connect(self._on_widgets_initialized)  # Line ~332
   ```
   - **Signal connected** ← Connection made at 12:26:29 (1 second later!)

**Result:** Signal already emitted before connection established → `_on_widgets_initialized()` never called → `_widgets_ready` never set to `True` → infinite retry loop.

## Solution Implemented

### Primary Fix: Post-Connection Sync Check

In `filter_mate_app.py`, after connecting the signal, immediately check if widgets are already initialized:

```python
# Connect to widgetsInitialized signal
self.dockwidget.widgetsInitialized.connect(self._on_widgets_initialized)

# CRITICAL FIX: Signal may have been emitted BEFORE connection
if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
    logger.info("Widgets already initialized before signal connection - syncing state")
    # Call handler directly since signal was already emitted
    self._on_widgets_initialized()
```

**Location:** `filter_mate_app.py`, lines ~331-338

### Secondary Fix: Runtime Fallback

In `_is_dockwidget_ready_for_filtering()`, add fallback to sync flags if signal wasn't received:

```python
if not self._widgets_ready:
    # Check if dockwidget has widgets_initialized=True despite signal not received
    if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
        logger.warning("⚠️ FALLBACK: Syncing _widgets_ready flag")
        self._widgets_ready = True
        # Continue to other checks
    else:
        return False  # Not ready
```

**Location:** `filter_mate_app.py`, lines ~1047-1055

### Tertiary Fix: Infinite Loop Protection

Add retry counter with emergency fallback after 10 attempts (5 seconds):

```python
# Track retry count to prevent infinite loop
retry_count = self._filter_retry_count.get(retry_key, 0)

if retry_count >= 10:  # Max 10 retries
    logger.error("❌ GIVING UP after 10 retries")
    # EMERGENCY FALLBACK: Force sync if dockwidget.widgets_initialized is True
    if hasattr(self.dockwidget, 'widgets_initialized') and self.dockwidget.widgets_initialized:
        self._widgets_ready = True
        QTimer.singleShot(100, lambda: self.manage_task(task_name, data))
    return
```

**Location:** `filter_mate_app.py`, lines ~797-824

## Files Modified

1. **filter_mate_app.py**
   - Added post-connection sync check (~line 331)
   - Added runtime fallback in `_is_dockwidget_ready_for_filtering()` (~line 1047)
   - Added infinite loop protection in `manage_task()` (~line 797)

2. **filter_mate_dockwidget.py**
   - No structural changes (only debug messages removed)

## Testing

### Before Fix
```
✅ widgets_initialized=True, emitting signal (12:26:28)
🔗 Connecting signal (_widgets_ready=False) (12:26:29)
❌ Check failed: _widgets_ready=False (infinite loop)
```

### After Fix
```
✅ widgets_initialized=True, emitting signal
🔗 Connecting signal
✅ Widgets already initialized - syncing state
✅ _widgets_ready=True
✅ Filter executes normally
```

## Prevention Strategy

### Why This Happened
Signal emitted in `__init__` before external code could connect to it. This is a common Qt anti-pattern.

### Best Practice
1. **Don't emit signals in `__init__()`** - emit them after object is fully constructed
2. **Use deferred emission** with QTimer.singleShot(0, ...)
3. **Always check initial state** after connecting to signals

### Recommended Refactoring (Future)
Move `widgetsInitialized.emit()` to a separate `initialize()` method called **after** FilterMateApp connects signals:

```python
# In FilterMateApp.run():
self.dockwidget = FilterMateDockWidget(...)
self.dockwidget.widgetsInitialized.connect(self._on_widgets_initialized)
self.dockwidget.initialize_widgets()  # Emit signal here, after connection
```

## Related Issues

- Phase 1 (Dec 2023): PostgreSQL made optional - similar initialization timing issues
- Phase 2 (Dec 2025): Spatialite backend - initialization order critical
- This fix ensures robust initialization regardless of timing

## Impact

- ✅ Filter functionality fully restored
- ✅ No more infinite loops
- ✅ Robust against timing variations
- ✅ Multiple fallback mechanisms
- ✅ Maintains backward compatibility

## Verification

To verify the fix is working:

1. Open QGIS with FilterMate installed
2. Open FilterMate dockwidget
3. Select a vector layer
4. Configure any filter
5. Click "Filter" button
6. **Expected:** Filter applies immediately without retries
7. Check logs - should see: "Widgets already initialized - syncing state"
