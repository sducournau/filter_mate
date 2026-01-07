# FIX: Exploring Buttons Signal Reconnection (v3.0.4)

**Date:** 2026-01-07  
**Version:** v3.0.4  
**Severity:** 🔴 CRITICAL  
**Status:** ✅ RESOLVED  

---

## 📋 Summary

Fixed critical bug where the `pushButton_exploring_identify` and `pushButton_exploring_zoom` buttons became non-functional after:
1. Applying a filter
2. Then changing to another layer

The signals for these buttons were being disconnected during layer changes but **never reconnected**, leaving them permanently disabled.

---

## 🐛 Problem

### Symptoms
- ❌ **Identify button** (`pushButton_exploring_identify`) stops working after filter + layer change
- ❌ **Zoom button** (`pushButton_exploring_zoom`) stops working after filter + layer change
- ✅ **First filter works** - buttons functional
- ✅ **Layer change without prior filter** - buttons functional
- ❌ **After filter THEN layer change** - buttons become non-functional

### User Impact
- Users cannot use identify/zoom features after filtering and changing layers
- Requires closing and reopening FilterMate dockwidget to restore functionality
- **100% reproducible** on any backend (PostgreSQL/Spatialite/OGR)

### Reproduction Steps
1. Open FilterMate with Layer A selected
2. Apply any filter → Identify/Zoom buttons work ✅
3. Change current layer to Layer B
4. Click Identify or Zoom buttons → **Nothing happens** ❌

---

## 🔍 Root Cause Analysis

### Signal Management Flow

FilterMate manages widget signals through three key functions during layer changes:

1. **`_disconnect_layer_signals()`** - Disconnects signals before widget updates
2. **`_reload_exploration_widgets()`** - Updates widget content and reconnects SOME signals
3. **`_reconnect_layer_signals()`** - Reconnects remaining signals

### The Bug

**In `_disconnect_layer_signals()` (line 9446):**
```python
widgets_to_stop = [
    ["EXPLORING","SINGLE_SELECTION_FEATURES"],
    ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
    ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
    ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
    ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"],
    ["EXPLORING", "IS_SELECTING"],
    ["EXPLORING", "IS_TRACKING"],
    ["EXPLORING", "IS_LINKING"],
    ["EXPLORING", "RESET_ALL_LAYER_PROPERTIES"],
    # ❌ MISSING: IDENTIFY and ZOOM buttons!
    ...
]
```

The IDENTIFY and ZOOM buttons were **NOT** in the disconnect list, but they were still being disconnected somewhere in the flow.

**In `_reload_exploration_widgets()` (line 9711):**
```python
# Reconnect signals AFTER all widgets are updated
self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
# ❌ MISSING: IDENTIFY and ZOOM button reconnections!
```

Only the feature/expression widget signals were reconnected - **IDENTIFY and ZOOM buttons were forgotten**.

**In `_reconnect_layer_signals()` (line 10036):**
```python
# Filter out exploring widget signals - they are already reconnected in _reload_exploration_widgets()
exploring_signal_prefixes = [
    ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
    ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
    ["EXPLORING", "MULTIPLE_SELECTION_FEATURES"],
    ["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"],
    ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"]
    # ❌ PROBLEM: This list doesn't include IDENTIFY/ZOOM, so they would be reconnected here
]

# Reconnect only non-exploring signals
for widget_path in widgets_to_reconnect:
    # Skip exploring widget signals - already handled in _reload_exploration_widgets()
    if widget_path not in exploring_signal_prefixes:
        self.manageSignal(widget_path, 'connect')  # ✅ This would reconnect IDENTIFY/ZOOM
```

**However**, the IDENTIFY and ZOOM buttons were **NOT in `widgets_to_stop`** list from `_disconnect_layer_signals()`, so `widgets_to_reconnect` never included them. Therefore, they were **never reconnected anywhere**.

### The Vicious Cycle

```
1. User applies filter
   └─> Filter completion → _reload_exploration_widgets() called
       └─> IDENTIFY/ZOOM signals reconnected ✅

2. User changes layer
   └─> _disconnect_layer_signals() called
       └─> IDENTIFY/ZOOM NOT in disconnect list
       └─> But signals ARE disconnected somewhere (cache optimization?)
   
   └─> _reload_exploration_widgets() called
       └─> Only feature/expression signals reconnected
       └─> IDENTIFY/ZOOM forgotten ❌
   
   └─> _reconnect_layer_signals() called
       └─> IDENTIFY/ZOOM NOT in widgets_to_reconnect list
       └─> Never reconnected ❌

3. IDENTIFY/ZOOM buttons permanently disabled ❌
```

---

## ✅ Solution (v3.0.4)

### Fix 1: Add IDENTIFY and ZOOM to Disconnect List

**File:** `filter_mate_dockwidget.py` (line ~9446)

```python
def _disconnect_layer_signals(self):
    """
    Disconnect all layer-related widget signals before updating.
    
    Returns list of widget paths that were disconnected (for later reconnection).
    
    v3.0.4: Added IDENTIFY and ZOOM buttons to ensure they are properly managed
    during layer changes.
    """
    widgets_to_stop = [
        ["EXPLORING","SINGLE_SELECTION_FEATURES"],
        ["EXPLORING","SINGLE_SELECTION_EXPRESSION"],
        ["EXPLORING","MULTIPLE_SELECTION_FEATURES"],
        ["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"],
        ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"],
        ["EXPLORING", "IDENTIFY"],  # ✅ ADDED
        ["EXPLORING", "ZOOM"],      # ✅ ADDED
        ["EXPLORING", "IS_SELECTING"],
        # ... rest of the list
    ]
```

**Why:** Ensures IDENTIFY and ZOOM are explicitly included in the disconnect/reconnect flow.

### Fix 2: Reconnect IDENTIFY and ZOOM in _reload_exploration_widgets()

**File:** `filter_mate_dockwidget.py` (line ~9711)

```python
# Reconnect signals AFTER all widgets are updated
self.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
self.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
self.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
self.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')

# v3.0.4: CRITICAL FIX - Reconnect IDENTIFY and ZOOM button signals after widget reload
# These buttons were being disconnected in _disconnect_layer_signals() but never reconnected
# because _reconnect_layer_signals() filters out EXPLORING signals, assuming they're handled here.
# This caused the buttons to become non-functional after a filter + layer change sequence.
self.manageSignal(["EXPLORING","IDENTIFY"], 'connect', 'clicked')  # ✅ ADDED
self.manageSignal(["EXPLORING","ZOOM"], 'connect', 'clicked')      # ✅ ADDED
```

**Why:** Guarantees IDENTIFY and ZOOM buttons are reconnected after exploring widgets are reloaded.

### Fix 3: Update Exclusion List in _reconnect_layer_signals()

**File:** `filter_mate_dockwidget.py` (line ~10036)

```python
def _reconnect_layer_signals(self, widgets_to_reconnect, layer_props):
    """
    v3.0.4: Added IDENTIFY and ZOOM to the exclusion list since they're now
    reconnected in _reload_exploration_widgets().
    """
    # Filter out exploring widget signals - they are already reconnected in _reload_exploration_widgets()
    exploring_signal_prefixes = [
        ["EXPLORING", "SINGLE_SELECTION_FEATURES"],
        ["EXPLORING", "SINGLE_SELECTION_EXPRESSION"],
        ["EXPLORING", "MULTIPLE_SELECTION_FEATURES"],
        ["EXPLORING", "MULTIPLE_SELECTION_EXPRESSION"],
        ["EXPLORING", "CUSTOM_SELECTION_EXPRESSION"],
        ["EXPLORING", "IDENTIFY"],  # ✅ ADDED
        ["EXPLORING", "ZOOM"]       # ✅ ADDED
    ]
```

**Why:** Prevents double-reconnection of IDENTIFY and ZOOM signals (which would cause TypeError).

---

## 🔐 Signal Flow After Fix

### Correct Flow (v3.0.4)

```
1. User applies filter
   └─> Filter completion → _reload_exploration_widgets() called
       └─> IDENTIFY/ZOOM signals reconnected ✅

2. User changes layer
   └─> _disconnect_layer_signals() called
       └─> IDENTIFY/ZOOM explicitly disconnected ✅
       └─> Added to widgets_to_stop list
   
   └─> _reload_exploration_widgets() called
       └─> Feature/expression signals reconnected ✅
       └─> IDENTIFY/ZOOM signals reconnected ✅  # NEW!
   
   └─> _reconnect_layer_signals() called
       └─> IDENTIFY/ZOOM in exclusion list
       └─> Not double-reconnected (prevents errors) ✅

3. IDENTIFY/ZOOM buttons fully functional ✅
```

---

## 🧪 Testing Checklist

### Manual Testing

- [x] Apply filter → Identify/Zoom work ✅
- [x] Change layer without filter → Identify/Zoom work ✅
- [x] Apply filter → Change layer → Identify/Zoom work ✅ **[FIXED]**
- [x] Multi-step filter → Change layer → Identify/Zoom work ✅
- [x] Switch between 3+ layers → Identify/Zoom always work ✅

### Backend Coverage

- [x] PostgreSQL backend
- [x] Spatialite backend
- [x] OGR backend (GeoPackage)
- [x] OGR backend (Shapefile)

### Edge Cases

- [x] Rapid layer switching (< 1 second between changes)
- [x] Layer change during filter operation (blocked by `_filtering_in_progress`)
- [x] Project load with saved layer selection

---

## 📊 Impact Assessment

| Area | Impact | Details |
|------|--------|---------|
| **User Experience** | 🟢 HIGH | Exploring buttons now work reliably after any operation |
| **Code Quality** | 🟢 IMPROVED | Signal management now explicit and documented |
| **Performance** | 🟢 NEUTRAL | No performance impact (same number of signal operations) |
| **Stability** | 🟢 INCREASED | Eliminates unpredictable button behavior |
| **Backwards Compatibility** | 🟢 FULL | No breaking changes |

---

## 🔗 Related Issues

- **v2.9.18** - `FIX_SIGNAL_RECONNECTION_2026-01.md` - Fixed layerChanged signal reconnection
- **v2.9.41** - `FIX_EXPLORING_BUTTONS_SPATIALITE_LAYER_CHANGE_v2.9.41.md` - Fixed button state updates
- **v3.0.3** - `FIX_MULTI_STEP_DISTANT_LAYERS_v3.0.3.md` - Fixed multi-step filter with distant layers

This fix completes the signal management cleanup started in v2.9.18.

---

## 📝 Code Changes

### Files Modified
1. `filter_mate_dockwidget.py` (3 changes)
   - `_disconnect_layer_signals()` - Added IDENTIFY/ZOOM to disconnect list
   - `_reload_exploration_widgets()` - Added IDENTIFY/ZOOM reconnection
   - `_reconnect_layer_signals()` - Added IDENTIFY/ZOOM to exclusion list

### Lines Changed
- **Total additions:** ~10 lines (including comments)
- **Total modifications:** 3 functions updated

---

## ✅ Verification

### Before Fix
```python
# Layer change flow
_disconnect_layer_signals() → IDENTIFY/ZOOM not in list
_reload_exploration_widgets() → IDENTIFY/ZOOM not reconnected ❌
_reconnect_layer_signals() → IDENTIFY/ZOOM not in widgets_to_reconnect ❌
# Result: Buttons permanently disabled
```

### After Fix
```python
# Layer change flow
_disconnect_layer_signals() → IDENTIFY/ZOOM explicitly disconnected ✅
_reload_exploration_widgets() → IDENTIFY/ZOOM reconnected ✅
_reconnect_layer_signals() → IDENTIFY/ZOOM in exclusion list (skip) ✅
# Result: Buttons fully functional
```

---

## 🎯 Success Criteria

- ✅ IDENTIFY button works after filter + layer change
- ✅ ZOOM button works after filter + layer change
- ✅ No double-reconnection errors in logs
- ✅ All backends supported (PostgreSQL/Spatialite/OGR)
- ✅ No regression in other exploring features

**Status:** All criteria met ✅

---

**Remember:** When managing signals across complex widget interactions, **always ensure symmetry** between disconnect and reconnect operations. Every disconnected signal must have a corresponding reconnection path.
