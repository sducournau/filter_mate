# 🎫 GitHub Issues - TODO Tracking

**Date:** 14 janvier 2026  
**Agent:** BMAD Master (Simon)  
**Source:** Phase 2B TODO Analysis  
**Total Issues:** 6

---

## 📋 INSTRUCTIONS D'UTILISATION

1. Copier chaque section "Issue #X" ci-dessous
2. Créer une nouvelle issue sur GitHub
3. Coller le titre et le corps
4. Ajouter les labels appropriés
5. Assigner au milestone correspondant

---

# Issue #1: Feature - Batch ZIP Archive Export

**Title:** Feature: Batch ZIP archive export for multiple layers

**Labels:** `enhancement`, `export`, `nice-to-have`, `p3`

**Milestone:** v5.0

**Body:**

## Description

Implement ZIP archive creation for batch export of multiple layers. Currently, when `config.batch_zip` is set, the system falls back to directory export.

## Current Behavior

```python
# core/export/layer_exporter.py:399
if config.batch_zip:
    logger.warning("Batch ZIP export not yet implemented, using directory export")
    return self.export_multiple_to_directory(config)
```

The system warns the user and falls back to directory export.

## Expected Behavior

- Create a ZIP archive containing all exported layers
- Support configurable compression level
- Include metadata file (export_summary.json)
- Preserve directory structure within ZIP

## Implementation Notes

**File:** `core/export/layer_exporter.py`  
**Method:** `export_multiple_to_zip()`  
**Dependencies:** Python `zipfile` module (standard library)

**Suggested Approach:**
1. Create temporary directory with exports
2. Use `zipfile.ZipFile()` to create archive
3. Add each exported file to ZIP
4. Add metadata JSON
5. Clean up temporary directory
6. Return path to ZIP file

## Benefits

- Easier sharing of batch exports
- Reduced storage (compression)
- Single-file download for users
- Professional export workflow

## Priority

**P3** - Nice-to-have feature, not blocking

## References

- Source file: [core/export/layer_exporter.py](../core/export/layer_exporter.py#L399)
- TODO Analysis: [PHASE-2B-TODO-ANALYSIS-20260114.md](../_bmad-output/PHASE-2B-TODO-ANALYSIS-20260114.md)

---

# Issue #2: Enhancement - FavoritesService Internal Storage Fallback

**Title:** Enhancement: Implement FavoritesService internal storage fallback

**Labels:** `enhancement`, `robustness`, `services`, `p2`

**Milestone:** v4.2

**Body:**

## Description

Implement internal database storage and project loading for `FavoritesService` when `FavoritesManager` is not available. This improves robustness and allows the service to function independently.

## Current Behavior

```python
# core/services/favorites_service.py:176
if self._favorites_manager and hasattr(self._favorites_manager, 'set_database'):
    self._favorites_manager.set_database(db_path, project_uuid)
else:
    # TODO: Implement internal database storage when manager not available
    logger.debug(f"FavoritesService: Database set to {db_path} (stub - no manager)")

# core/services/favorites_service.py:187
if self._favorites_manager and hasattr(self._favorites_manager, 'load_from_project'):
    self._favorites_manager.load_from_project()
else:
    # TODO: Implement internal project loading when manager not available
    logger.debug("FavoritesService: Loading from project (stub - no manager)")
```

Service logs stub behavior when manager is unavailable.

## Expected Behavior

- Service should handle database storage internally if manager unavailable
- Service should load favorites from project independently
- Graceful degradation with full functionality preserved

## Implementation Notes

**File:** `core/services/favorites_service.py`  
**Methods:** `set_database()`, `load_from_project()`  

**Suggested Approach:**
1. Add internal `_db_path` and `_project_uuid` attributes
2. Implement SQLite storage directly in service (if needed)
3. Or use JSON storage in QGIS project file
4. Maintain compatibility with FavoritesManager when available

## Benefits

- **Robustness:** Service works without external dependencies
- **Flexibility:** Easier testing and standalone usage
- **Reliability:** No silent failures in fallback mode

## Priority

**P2** - Important for service robustness

## References

- Source file: [core/services/favorites_service.py](../core/services/favorites_service.py#L176)
- Lines: 176, 187
- Related: FavoritesManager integration

---

# Issue #3: Feature - User-Configurable Menu and Toolbar Settings

**Title:** Feature: User-configurable menu and toolbar settings

**Labels:** `enhancement`, `ui`, `configuration`, `nice-to-have`, `p3`

**Milestone:** v5.0

**Body:**

## Description

Allow users to configure menu and toolbar settings through the plugin configuration interface.

## Current Behavior

```python
# filter_mate.py:105
self.menu = self.tr(u'&FilterMate')
# TODO: We are going to let the user set this up in a future iteration

self.toolbar = self.iface.addToolBar(u'FilterMate')
self.toolbar.setObjectName(u'FilterMate')
```

Menu and toolbar names are hardcoded.

## Expected Behavior

Users should be able to configure:
- Menu name/label
- Toolbar name
- Toolbar position (left/right/top/bottom)
- Icon theme
- Keyboard shortcuts

## Implementation Notes

**File:** `filter_mate.py`, `config/config.json`  

**Configuration Schema Addition:**
```json
{
  "ui": {
    "menu_label": "FilterMate",
    "toolbar_name": "FilterMate",
    "toolbar_area": "top",
    "icon_theme": "auto"
  }
}
```

**Suggested Approach:**
1. Add UI configuration section to config schema
2. Load configuration in `__init__()`
3. Apply custom menu/toolbar names
4. Add configuration UI in settings dialog

## Benefits

- User customization
- Better workspace integration
- Accessibility improvements
- Professional appearance

## Priority

**P3** - Nice-to-have, low user demand

## References

- Source file: [filter_mate.py](../filter_mate.py#L105)
- Config system: [config/config.py](../config/config.py)

---

# Issue #4: EPIC-1 Phase E14 - Complete Unfilter/Reset Controller Delegation

**Title:** EPIC-1 Phase E14: Complete unfilter/reset controller delegation

**Labels:** `epic-1`, `mvc-migration`, `architecture`, `p1`

**Milestone:** v4.1

**Body:**

## Description

Complete MVC migration by implementing `delegate_unfilter()` and `delegate_reset()` methods in controllers, removing remaining legacy code paths.

## Current Behavior

Multiple locations still have TODO comments for unfilter/reset delegation:

```python
# core/services/task_orchestrator.py:451
elif task_name == 'unfilter':
    # TODO: Implement delegate_unfilter()
    logger.debug("Controller delegation for 'unfilter' not yet implemented")

# core/services/task_orchestrator.py:454
elif task_name == 'reset':
    # TODO: Implement delegate_reset()
    logger.debug("Controller delegation for 'reset' not yet implemented")

# filter_mate_app.py:1209
elif task_name == 'unfilter':
    # TODO: Implement delegate_unfilter() in controllers
    logger.debug("Controller delegation for 'unfilter' not yet implemented")
    return False

# filter_mate_app.py:1215
elif task_name == 'reset':
    # TODO: Implement delegate_reset() in controllers
    logger.debug("Controller delegation for 'reset' not yet implemented")
    return False
```

System falls back to legacy code for these operations.

## Expected Behavior

- `FilteringController.delegate_unfilter()` handles unfilter operation
- `FilteringController.delegate_reset()` handles reset operation
- Legacy code paths removed
- Full MVC compliance

## Implementation Notes

**Files:**
- `ui/controllers/filtering_controller.py` (add methods)
- `core/services/task_orchestrator.py` (update delegation)
- `filter_mate_app.py` (remove legacy fallbacks)

**Suggested Approach:**
1. Implement `delegate_unfilter()` in FilteringController
   - Clear subset strings from all layers
   - Reset UI state
   - Emit appropriate signals
2. Implement `delegate_reset()` in FilteringController
   - Reset all filters
   - Clear layer selection
   - Restore default state
3. Update TaskOrchestrator to call new methods
4. Remove legacy code from FilterMateApp
5. Add tests for new delegation paths

## Dependencies

- Part of EPIC-1 Phase E14 (Complete MVC Migration)
- Related to Issue #5 (FilterService integration)

## Benefits

- **Architecture:** Complete hexagonal architecture
- **Maintainability:** Single code path, no legacy fallbacks
- **Testability:** Controllers fully unit-testable
- **Performance:** Streamlined execution flow

## Priority

**P1** - Critical for completing EPIC-1

## References

- Source files: 
  - [core/services/task_orchestrator.py](../core/services/task_orchestrator.py#L451)
  - [filter_mate_app.py](../filter_mate_app.py#L1209)
- EPIC-1 Plan: [PHASE-E13-REFACTORING-PLAN.md](../_bmad-output/PHASE-E13-REFACTORING-PLAN.md)

---

# Issue #5: EPIC-1 Phase E15 - FilterService Integration in FilteringController

**Title:** EPIC-1 Phase E15: Complete FilterService integration in FilteringController

**Labels:** `epic-1`, `mvc-migration`, `architecture`, `services`, `p1`

**Milestone:** v4.1

**Body:**

## Description

Complete the Strangler Fig Pattern migration by actually using `FilterService` in `FilteringController` instead of delegating to legacy code.

## Current Behavior

```python
# ui/controllers/filtering_controller.py:709
# TODO Phase 2: Actually use FilterService here
# For now, return False to use legacy path while we verify integration
# The controller is connected and config is valid - legacy will handle execution
logger.debug("FilteringController: Delegating to legacy (Phase 1 - verification)")
return False
```

Controller builds configuration correctly but still delegates to legacy code for actual filtering execution.

## Expected Behavior

- `FilteringController` calls `FilterService.apply_filter()` directly
- No fallback to legacy code
- Full service-based filtering workflow

## Implementation Notes

**File:** `ui/controllers/filtering_controller.py`  
**Method:** `on_apply_filter_clicked()`  

**Current Status:**
- ✅ TaskParameters built correctly
- ✅ FilterService injected
- ❌ Service not actually called (returns False)

**Suggested Approach:**
1. Replace `return False` with actual FilterService call:
   ```python
   result = self._filter_service.apply_filter(task_params)
   if result.success:
       logger.info("Filter applied via FilterService")
       return True
   else:
       logger.error(f"FilterService error: {result.error}")
       return False
   ```
2. Remove legacy fallback from `FilterMateApp`
3. Add error handling for service failures
4. Update tests to verify service integration

## Dependencies

- Requires Issue #4 completed (unfilter/reset delegation)
- Part of EPIC-1 Phase E15
- Critical path for removing legacy code

## Benefits

- **Clean Architecture:** Pure hexagonal architecture
- **Testability:** Full mocking capability
- **Performance:** Direct service calls (no legacy overhead)
- **Maintainability:** Single source of truth

## Priority

**P1** - Critical path for EPIC-1 completion

## Migration Path

```
Phase E14 (Issue #4): Complete controller delegation
  ↓
Phase E15 (This issue): Use FilterService
  ↓
Phase E16: Remove legacy code entirely
```

## References

- Source file: [ui/controllers/filtering_controller.py](../ui/controllers/filtering_controller.py#L709)
- FilterService: [core/services/filter_service.py](../core/services/filter_service.py)
- EPIC-1 Plan: [PHASE-E13-REFACTORING-PLAN.md](../_bmad-output/PHASE-E13-REFACTORING-PLAN.md)

---

# Issue #6: Enhancement - Bidirectional Widget-Controller State Sync

**Title:** Enhancement: Implement bidirectional widget-controller state synchronization

**Labels:** `enhancement`, `mvc`, `ui`, `p2`

**Milestone:** v4.2

**Body:**

## Description

Implement bidirectional state synchronization between UI widgets and controllers, allowing controllers to update widget states programmatically.

## Current Behavior

```python
# ui/controllers/integration.py:1523
# TODO: Implement widget updates based on controller state
# This would update combo boxes, text fields, etc.
logger.debug("Dockwidget synchronized from controller state")
```

Controllers can receive widget events, but cannot update widget states.

## Expected Behavior

Controllers should be able to:
- Update combo box selections programmatically
- Set text field values
- Enable/disable widgets based on state
- Synchronize UI with controller state after operations

## Use Cases

1. **Restore Session:** Load previous filter configuration and update UI
2. **Favorites:** Apply favorite filter and sync all widgets
3. **Undo/Redo:** Restore UI state after undo operation
4. **Programmatic Operations:** API calls update UI automatically

## Implementation Notes

**File:** `ui/controllers/integration.py`  
**Method:** `sync_widgets_from_controllers()`  

**Suggested Approach:**
1. Add `set_widget_value()` methods to controllers
2. Implement state getters in controllers
3. Create sync mechanism in ControllerIntegration
4. Block signals during programmatic updates (avoid loops)
5. Emit `state_changed` signal after sync

**Example:**
```python
def sync_widgets_from_controllers(self):
    """Synchronize UI widgets with controller state."""
    if not self._is_setup:
        return
    
    # Block signals to avoid loops
    with self._signal_blocker():
        # Update exploring widgets
        self._exploring_controller.sync_to_widgets(self._dockwidget)
        
        # Update filtering widgets
        self._filtering_controller.sync_to_widgets(self._dockwidget)
        
        # Update exporting widgets
        self._exporting_controller.sync_to_widgets(self._dockwidget)
```

## Benefits

- **User Experience:** Consistent UI state
- **Reliability:** No state desync bugs
- **Features:** Enables favorites, undo/redo, session restore
- **Professionalism:** Expected behavior in modern applications

## Priority

**P2** - Important for user experience

## References

- Source file: [ui/controllers/integration.py](../ui/controllers/integration.py#L1523)
- Related: Favorites system, Undo/Redo system

---

# Issue #7: Performance - Restore Async Task-Based Feature List Population

**Title:** Performance: Restore async task-based feature list population (PopulateListEngineTask)

**Labels:** `performance`, `ui`, `regression`, `p2`

**Milestone:** v4.2

**Body:**

## Description

Restore asynchronous task-based feature list population that existed in v2.x. Current synchronous implementation causes UI freezes with large datasets.

## Current Behavior

```python
# ui/widgets/custom_widgets.py:830
# Build features list synchronously for now
# TODO: Restore async task-based population (PopulateListEngineTask)
self._populate_features_sync(working_expression)
```

Features are loaded synchronously, blocking the UI thread.

## Impact

- **UI Freeze:** Large layers (>10k features) cause noticeable lag
- **Poor UX:** No progress indicator during population
- **Regression:** v2.x had async task that was removed during migration

## Expected Behavior

- Feature list population runs in background QgsTask
- Progress bar shows population status
- UI remains responsive during loading
- Cancel button allows stopping long operations

## Implementation Notes

**File:** `ui/widgets/custom_widgets.py`  
**Class:** `QgsCheckableComboBoxFeaturesListPickerWidget`  

**Previous Implementation:**
- v2.x had `PopulateListEngineTask` (QgsTask)
- Removed during hexagonal migration
- Need to restore with new architecture

**Suggested Approach:**
1. Create `PopulateFeatureListTask` extending QgsTask
2. Move population logic to task's `run()` method
3. Emit signals from `finished()` to update UI
4. Add progress reporting
5. Add cancel capability
6. Update widget to use task instead of sync method

**Example Structure:**
```python
class PopulateFeatureListTask(QgsTask):
    """Background task for populating feature list."""
    
    def __init__(self, layer, expression, display_field):
        super().__init__(f"Populating features from {layer.name()}")
        self.layer = layer
        self.expression = expression
        self.display_field = display_field
        self.features = []
    
    def run(self):
        """Execute in background thread."""
        request = QgsFeatureRequest()
        request.setFilterExpression(self.expression)
        
        for i, feature in enumerate(self.layer.getFeatures(request)):
            if self.isCanceled():
                return False
            self.features.append(feature)
            self.setProgress((i + 1) / self.layer.featureCount() * 100)
        
        return True
    
    def finished(self, result):
        """Update UI on main thread."""
        if result:
            # Emit signal to populate widget
            pass
```

## Performance Targets

| Dataset Size | Current | Target |
|--------------|---------|--------|
| 1k features | 100ms | 100ms (acceptable) |
| 10k features | 1s (freeze) | <200ms + background |
| 100k features | 10s+ (freeze) | <500ms + background |

## Benefits

- **UX:** No UI freezes
- **Performance:** Better perceived performance
- **Professional:** Progress indication
- **Scalability:** Handles large datasets

## Priority

**P2** - Performance regression affecting UX

## References

- Source file: [ui/widgets/custom_widgets.py](../ui/widgets/custom_widgets.py#L830)
- v2.x implementation: `before_migration/modules/tasks/populate_list_task.py` (if exists)
- QGIS Task API: https://qgis.org/pyqgis/latest/core/QgsTask.html

---

## 📊 SUMMARY

**Total Issues Created:** 7  
**Priority Breakdown:**
- **P1 (Critical):** 2 issues (EPIC-1 Phase E14-E15)
- **P2 (Important):** 3 issues (Robustness, UX, Performance)
- **P3 (Nice-to-Have):** 2 issues (Future features)

**Milestones:**
- **v4.1:** Issues #4, #5 (EPIC-1 completion)
- **v4.2:** Issues #2, #6, #7 (Enhancements, Performance)
- **v5.0:** Issues #1, #3 (Future features)

**Labels Used:**
- `epic-1`, `mvc-migration`, `architecture`
- `enhancement`, `performance`, `regression`
- `ui`, `services`, `export`, `robustness`
- `p1`, `p2`, `p3`, `nice-to-have`

---

**Status:** ✅ Ready to create on GitHub

**Next Steps:**
1. Review issues above
2. Create on https://github.com/sducournau/filter_mate/issues
3. Update project board
4. Link to EPIC-1 tracking

**Agent:** BMAD Master  
**Date:** 2026-01-14
