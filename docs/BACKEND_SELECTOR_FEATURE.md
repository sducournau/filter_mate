# Backend Selector Feature - FilterMate v2.3.0

**Date:** December 17, 2025  
**Feature:** Interactive backend indicator with manual backend selection

## Overview

FilterMate now allows users to **manually force** a specific backend for filtering operations by clicking on the backend indicator badge. This gives users fine-grained control over performance vs compatibility tradeoffs.

## Visual Indicator

The backend indicator appears as a **colored badge** in the top-right corner of the FilterMate dockwidget:

- 🐘 **PostgreSQL** (Green `#27ae60`) - High performance
- 💾 **Spatialite** (Purple `#9b59b6`) - Good performance
- 📁 **OGR** (Blue `#3498db`) - Universal compatibility
- 📁 **OGR*** (Orange `#e67e22`) - Fallback mode (PostgreSQL unavailable)

### Forced Backend Indicator

When a backend is manually forced, the badge displays a **lightning bolt** symbol (⚡):
- Example: `PostgreSQL⚡`
- Tooltip shows: `Backend: PostgreSQL (High Performance) (Forced: postgresql)`

## User Interaction

### 1. Clicking the Backend Indicator

**Action:** Click on the backend badge  
**Result:** Context menu appears with available backends

**Menu Structure:**
```
┌──────────────────────────────────────────┐
│ Select Backend:                          │
├──────────────────────────────────────────┤
│ 🐘 PostgreSQL                           │  (if available)
│ 💾 Spatialite                           │  (if compatible)
│ 📁 OGR                                   │  (always available)
├──────────────────────────────────────────┤
│ ⚙️ Auto (Default) ✓                     │  (current selection)
├──────────────────────────────────────────┤
│ 🎯 Auto-select Optimal for All Layers   │  (NEW!)
└──────────────────────────────────────────┘
```

**Current Selection:** Marked with checkmark (✓)

### 2. Selecting a Backend

**Action:** Click on a backend option  
**Result:** 
- Backend is forced for the current layer
- Indicator updates to show forced backend with ⚡ symbol
- Success message displayed: `Backend forced to POSTGRESQL for layer 'LayerName'`

### 3. Returning to Auto Mode

**Action:** Click "⚙️ Auto (Default)" in menu  
**Result:**
- Forced backend removed
- FilterMate automatically selects best backend
- Info message displayed: `Backend set to Auto for layer 'LayerName'`

### 4. Auto-select Optimal for All Layers 🎯

**Action:** Click "🎯 Auto-select Optimal for All Layers" in menu  
**Result:**
- Analyzes ALL layers in the project
- Automatically selects optimal backend for each layer based on:
  - Provider type (PostgreSQL, Spatialite, OGR)
  - Feature count (small/medium/large datasets)
  - Data source type (server-based vs file-based)
  - PostgreSQL availability (psycopg2 installed)
- Shows comprehensive summary message with results
- Updates all backend indicators with ⚡ symbol

**Example Summary:**
```
Optimized 5 layer(s): 2 POSTGRESQL, 1 SPATIALITE, 2 OGR
```

**Optimization Logic:**
- **PostgreSQL layers:**
  - < 10,000 features → OGR (memory optimization, faster)
  - ≥ 10,000 features → PostgreSQL (server-side operations, optimal)
  - psycopg2 unavailable → OGR (fallback)
  
- **SQLite/GeoPackage layers:**
  - > 5,000 features → Spatialite (R-tree indexes, efficient)
  - ≤ 5,000 features → OGR (sufficient performance)
  
- **Shapefiles/GeoJSON:**
  - Always → OGR (native support, adequate)

**When to Use:**
- ✅ After loading a new project with many layers
- ✅ When unsure which backend to use for each layer
- ✅ To quickly optimize performance across all layers
- ✅ When switching between projects with different data types

## Backend Selection Logic

### Intelligent Auto-Selection Algorithm 🎯

**NEW in v2.3.6:** FilterMate includes an intelligent optimization algorithm that analyzes layer characteristics and automatically selects the optimal backend.

**Decision Tree:**

```
Layer Analysis
    ├── PostgreSQL Provider?
    │   ├── psycopg2 available?
    │   │   ├── < 10k features → OGR (memory optimization)
    │   │   └── ≥ 10k features → PostgreSQL (server-side power)
    │   └── psycopg2 unavailable → OGR (fallback)
    │
    ├── Spatialite Provider OR SQLite/GeoPackage?
    │   ├── > 5k features → Spatialite (R-tree indexes)
    │   └── ≤ 5k features → OGR (lightweight)
    │
    └── OGR Provider (Shapefile, GeoJSON, etc.)
        ├── GeoPackage/SQLite source?
        │   ├── > 5k features → Spatialite
        │   └── ≤ 5k features → OGR
        └── Other formats → OGR
```

**Performance Thresholds:**
- **10,000 features**: PostgreSQL vs OGR decision point
- **5,000 features**: Spatialite vs OGR decision point

**Rationale:**
- Small PostgreSQL datasets: Connection overhead + query planning time > in-memory processing
- Large PostgreSQL datasets: Server-side spatial indexes + optimized queries >> client-side processing
- Medium SQLite datasets: Spatialite R-tree indexes provide significant speedup
- Small SQLite datasets: OGR simplicity sufficient, minimal overhead

### Automatic Selection (Default)

FilterMate automatically selects the best backend based on:

1. **Layer provider type** (PostgreSQL, Spatialite, OGR)
2. **Available dependencies** (psycopg2 for PostgreSQL)
3. **Layer characteristics** (data source, connection availability)

**Selection Priority:**
- **PostgreSQL layers** + psycopg2 installed → PostgreSQL backend
- **Spatialite/GeoPackage layers** → Spatialite backend
- **Other layers** (Shapefiles, GeoJSON) → OGR backend
- **Fallback** → OGR backend (universal compatibility)

### Manual Override

Users can **override** the automatic selection by forcing a specific backend:

**Use Cases:**
- **Performance testing:** Compare backend performance
- **Compatibility issues:** Force OGR if Spatialite has issues
- **Debugging:** Test specific backend behavior
- **Optimization:** Force faster backend for specific workflows

**Limitations:**
- Only **available** backends are shown in menu
- **Incompatible backends** cannot be forced (e.g., PostgreSQL for Shapefile)
- Backend preference is **per-layer** (each layer can have different backend)

## Technical Implementation

### Architecture Changes

#### 1. Dockwidget Changes (`filter_mate_dockwidget.py`)

**New Properties:**
```python
self.forced_backends = {}  # layer_id -> backend_type mapping
self._current_provider_type = None  # Current layer provider
self._current_postgresql_available = None  # PostgreSQL availability
```

**New Methods:**
- `_on_backend_indicator_clicked(event)` - Handle click on indicator
- `_get_available_backends_for_layer(layer)` - Get available backends
- `_detect_current_backend(layer)` - Detect current backend
- `_set_forced_backend(layer_id, backend_type)` - Force backend
- `get_forced_backend_for_layer(layer_id)` - Get forced backend
- `_get_optimal_backend_for_layer(layer)` - Analyze and determine optimal backend
- `auto_select_optimal_backends()` - Auto-optimize all project layers

**Updated Methods:**
- `_setup_backend_indicator()` - Add click handler and cursor
- `_update_backend_indicator()` - Show forced backend indicator (⚡)

#### 2. App Changes (`filter_mate_app.py`)

**Updated Methods:**
- `_build_common_task_params()` - Pass `forced_backends` to tasks

**Modification:**
```python
if self.dockwidget and hasattr(self.dockwidget, 'forced_backends'):
    params["forced_backends"] = self.dockwidget.forced_backends
```

#### 3. Task Changes (`modules/tasks/filter_task.py`)

**Backend Selection Logic:**
```python
# Check if backend is forced for this layer
forced_backends = self.task_parameters.get('forced_backends', {})
forced_backend = forced_backends.get(layer.id())

if forced_backend:
    logger.info(f"  ⚡ Using FORCED backend '{forced_backend}' for layer '{layer_name}'")
    effective_provider_type = forced_backend

# Get backend from factory with forced type
backend = BackendFactory.get_backend(effective_provider_type, layer, self.task_parameters)
```

### Data Structures

#### Forced Backends Storage
```python
forced_backends = {
    'layer_uuid_123': 'postgresql',
    'layer_uuid_456': 'ogr',
    # layer_id -> backend_type
}
```

#### Available Backends Format
```python
available_backends = [
    ('postgresql', 'PostgreSQL', '🐘'),
    ('spatialite', 'Spatialite', '💾'),
    ('ogr', 'OGR', '📁'),
    # (backend_type, display_name, icon)
]
```

## Performance Considerations

### Backend Performance Characteristics

| Backend    | Best For             | Feature Count | Query Time    |
|-----------|----------------------|---------------|---------------|
| PostgreSQL | > 50,000 features   | Millions      | < 1s          |
| Spatialite | 10,000 - 50,000     | 100,000       | 1-10s         |
| OGR        | < 10,000 features   | 10,000        | 10-60s        |

### When to Force Backend

**Force PostgreSQL:**
- Large datasets on PostgreSQL server
- Complex spatial operations
- Need materialized views

**Force Spatialite:**
- Medium datasets in GeoPackage/SQLite
- Local file-based operations
- Good balance of speed and simplicity

**Force OGR:**
- Small datasets
- Maximum compatibility
- Simple operations
- Debugging backend issues

## User Messages

### Success Messages
```python
iface.messageBar().pushSuccess(
    "FilterMate", 
    f"Backend forced to {backend_type.upper()} for layer '{layer_name}'"
)
```

### Info Messages
```python
iface.messageBar().pushInfo(
    "FilterMate", 
    f"Backend set to Auto for layer '{layer_name}'"
)
```

### Warning Messages
```python
iface.messageBar().pushWarning(
    "FilterMate", 
    "No alternative backends available for this layer"
)
```

## Tooltips

### Default Tooltip
```
Backend: PostgreSQL (High Performance)
Click to change backend
```

### Forced Backend Tooltip
```
Backend: PostgreSQL (High Performance) (Forced: postgresql)
Click to change backend
```

### Fallback Tooltip
```
Backend: OGR (Fallback - PostgreSQL connection unavailable)
Click to change backend
```

## Persistence

**Current Implementation:**
- Backend preferences are **session-based**
- Preferences are **lost** when QGIS is closed
- Each layer can have different forced backend

**Future Enhancements (Planned):**
- Save forced backends in project variables
- Persist preferences across QGIS sessions
- User-configurable default backend per layer type

## Testing

### Manual Testing Checklist

1. **Backend Indicator Display**
   - [ ] Badge shows correct backend (PostgreSQL/Spatialite/OGR)
   - [ ] Correct color for each backend
   - [ ] Cursor changes to pointer on hover
   - [ ] Tooltip shows backend info

2. **Click Interaction**
   - [ ] Click opens context menu
   - [ ] Menu shows available backends
   - [ ] Current backend marked with ✓
   - [ ] Menu styled correctly

3. **Backend Selection**
   - [ ] Forcing backend shows ⚡ symbol
   - [ ] Success message appears
   - [ ] Tooltip updates with forced info
   - [ ] Backend actually used in filtering

4. **Auto Mode**
   - [ ] Returning to Auto removes ⚡
   - [ ] Info message appears
   - [ ] Backend auto-selected correctly

5. **Multiple Layers**
   - [ ] Each layer can have different backend
   - [ ] Switching layers updates indicator
   - [ ] Forced backends preserved per layer

6. **Edge Cases**
   - [ ] No alternative backends shows warning
   - [ ] Invalid backend fallback works
   - [ ] PostgreSQL unavailable shows OGR*

### Automated Testing

**Test File:** `tests/test_backend_selector.py` (to be created)

**Test Cases:**
- `test_backend_indicator_display()`
- `test_get_available_backends_for_layer()`
- `test_set_forced_backend()`
- `test_forced_backend_used_in_task()`
- `test_auto_mode_removes_forced_backend()`

## Known Issues

**None currently identified**

## Future Enhancements

1. **Persistence** - Save forced backends in QGIS project file
2. **Performance Metrics** - Show execution time for each backend
3. **Backend Comparison** - Side-by-side performance comparison
4. **Auto-Recommendation** - Suggest optimal backend based on data
5. **Backend Statistics** - Track backend usage and performance
6. **Keyboard Shortcut** - Quick backend switching with hotkey

## Related Documentation

- [Backend Architecture](backend_architecture.md)
- [Performance Optimizations](PERFORMANCE_STABILITY_IMPROVEMENTS_2025-12-17.md)
- [UI System](../website/docs/guide/ui-system.md)

## Code References

**Main Files:**
- `filter_mate_dockwidget.py` - UI and interaction logic
- `filter_mate_app.py` - Task parameter building
- `modules/tasks/filter_task.py` - Backend selection in tasks
- `modules/backends/factory.py` - Backend factory pattern

**Key Methods:**
- `FilterMateDockWidget._on_backend_indicator_clicked()`
- `FilterMateDockWidget._get_available_backends_for_layer()`
- `FilterMateApp._build_common_task_params()`
- `BackendFactory.get_backend()`
