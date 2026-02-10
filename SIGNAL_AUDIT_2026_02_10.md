# FilterMate - Signal Connect/Disconnect Audit

**Date:** 2026-02-10
**Version:** 4.3.x (branch `main`)
**Auditor:** Marco (GIS Lead Developer Agent)
**Scope:** All `.connect()` / `.disconnect()` calls on Qt signals in Python source files
**Method:** Exhaustive grep + manual classification of each unmatched connect

---

## 1. Executive Summary

The codebase has **267 `.connect(` calls** across 53 files and **104 `.disconnect(` calls** across 20 files, yielding a raw ratio of **2.57:1**.

However, after excluding non-Qt calls (`sqlite3.connect`, `psycopg2.connect`, `base_executor.connect`) and `SignalManager` wrapper methods, the **effective Qt signal ratio** is:

| Metric | Count |
|--------|-------|
| Qt signal `.connect()` calls | **196** |
| Qt signal `.disconnect()` calls | **92** |
| **Effective ratio** | **2.13:1** |
| Connects with matching disconnect | ~92 |
| Connects without explicit disconnect | ~104 |
| Of those, classified OK (same lifecycle) | ~72 |
| Of those, classified potential leak | ~22 |
| Of those, classified to fix | ~10 |

---

## 2. Non-Qt Calls Excluded from Audit

The following calls are database/network connections, not Qt signals:

| File | Count | Type |
|------|-------|------|
| `core/services/favorites_migration_service.py` | 9 | `sqlite3.connect()` |
| `core/domain/favorites_manager.py` | 9 | `sqlite3.connect()` |
| `infrastructure/database/connection_pool.py` | 1 | `psycopg2.connect()` |
| `infrastructure/utils/layer_utils.py` | 2 | `psycopg2.connect()` + `sqlite3.connect()` |
| `infrastructure/utils/task_utils.py` | 2 | `sqlite3.connect()` |
| `infrastructure/database/sql_utils.py` | 1 | `sqlite3.connect()` |
| `infrastructure/cache/spatialite_persistent_cache.py` | 1 | `sqlite3.connect()` |
| `infrastructure/resilience.py` | 2 | `psycopg2.connect()` (docstring examples) |
| `adapters/backends/spatialite/backend.py` | 1 | `sqlite3.connect()` |
| `adapters/backends/spatialite/temp_table_manager.py` | 1 | `sqlite3.connect()` |
| `adapters/backends/spatialite/filter_executor.py` | 1 | `sqlite3.connect()` |
| `adapters/backends/spatialite/interruptible_query.py` | 2 | `sqlite3.connect()` |
| `adapters/backends/postgresql_availability.py` | 1 | `psycopg2.connect()` (docstring) |
| `adapters/backends/base_executor.py` | 2 | DB `connect()`/`disconnect()` |
| `adapters/view_manager_factory.py` | 1 | `psycopg2.connect()` |
| `core/tasks/layer_management_task.py` | 1 | `sqlite3.connect()` |
| `core/tasks/filter_task.py` | 1 | `sqlite3.connect()` |
| `core/services/favorites_service.py` | 1 | `sqlite3.connect()` |
| `ui/controllers/backend_controller.py` | 1 | `sqlite3.connect()` |
| **Total excluded** | **41** | |

Also excluded from the Qt ratio:
- `adapters/qgis/signals/signal_manager.py`: internal `signal.connect()` / `signal.disconnect()` inside the managed `SignalManager.connect()` / `SignalManager.disconnect()` wrapper (5 connect, 8 disconnect internally). These are properly managed by the `SignalManager` lifecycle.
- `adapters/qgis/signals/migration_helper.py`: 3 calls inside migration wrapper (2 docstring/comments, 1 delegating to `SignalManager`).
- `infrastructure/signal_utils.py`: 4 connects and 3 disconnects inside `TemporaryConnection` / `ConnectionManager` utilities. These are self-contained utilities that manage their own lifecycle.
- `ui/controllers/base_controller.py`: 2 connects inside `_connect_signal()` method (1 raw fallback + 1 via SignalManager). 2 disconnects via SignalManager. Properly paired.

---

## 3. Per-File Statistics (Qt Signals Only)

| File | Connects | Disconnects | Delta | Ratio |
|------|----------|-------------|-------|-------|
| `filter_mate_dockwidget.py` | 35 | 22 | +13 | 1.59:1 |
| `filter_mate_app.py` | 23 | 15 | +8 | 1.53:1 |
| `ui/controllers/integration.py` | 18 | 18 | 0 | 1.00:1 |
| `ui/widgets/custom_widgets.py` | 17 | 2 | +15 | 8.50:1 |
| `core/services/app_initializer.py` | 13 | 1 | +12 | 13.0:1 |
| `ui/dialogs/config_editor_widget.py` | 13 | 0 | +13 | -- |
| `ui/managers/dockwidget_signal_manager.py` | 11 | 11 | 0 | 1.00:1 |
| `core/tasks/expression_evaluation_task.py` | 8 | 0 | +8 | -- |
| `ui/widgets/history_widget.py` | 8 | 0 | +8 | -- |
| `filter_mate.py` | 10 | 7 | +3 | 1.43:1 |
| `ui/dialogs/favorites_manager.py` | 7 | 0 | +7 | -- |
| `ui/widgets/json_view/*` (6 files) | 18 | 0 | +18 | -- |
| `ui/dialogs/optimization_dialog.py` | 5 | 0 | +5 | -- |
| `ui/controllers/exploring_controller.py` | 4 | 1 | +3 | 4.00:1 |
| `ui/controllers/favorites_controller.py` | 4 | 1 | +3 | 4.00:1 |
| `ui/dialogs/postgres_info_dialog.py` | 3 | 0 | +3 | -- |
| `ui/styles/theme_watcher.py` | 2 | 1 | +1 | 2.00:1 |
| `ui/controllers/layer_sync_controller.py` | 3 | 0 | +3 | -- |
| `ui/controllers/config_controller.py` | 2 | 0 | +2 | -- |
| `ui/controllers/backend_controller.py` | 1 | 0 | +1 | -- |
| `ui/widgets/favorites_widget.py` | 2 | 0 | +2 | -- |
| `ui/managers/configuration_manager.py` | 1 | 0 | +1 | -- |
| `adapters/qgis/signals/debouncer.py` | 1 | 0 | +1 | -- |
| `adapters/qgis/signals/layer_signal_handler.py` | 2 | 4 | -2 | 0.50:1 |
| `adapters/qgis/filter_optimizer.py` | 1 | 0 | +1 | -- |
| `core/services/layer_lifecycle_service.py` | 0 | 1 | -1 | -- |

---

## 4. Detailed Classification of Unmatched Connects

### 4.1 `filter_mate_dockwidget.py` (35 connect, 22 disconnect, delta +13)

#### OK sans disconnect -- Same lifecycle (parent-child, one-time init)

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 247 | `_expression_debounce_timer.timeout` | `_execute_debounced_expression_change` | QTimer is child of dockwidget. Same lifecycle. |
| 2304 | `config_model.itemChanged` | `data_changed_configuration_model` | Paired with disconnect at L2289. Counted as paired. |
| 2347 | `buttonBox.accepted` | `on_config_buttonbox_accepted` | UI widget child of dockwidget. Same lifecycle. |
| 2348 | `buttonBox.rejected` | `on_config_buttonbox_rejected` | UI widget child of dockwidget. Same lifecycle. |
| 2358 | `pushButton_reload_plugin.clicked` | `_on_reload_button_clicked` | UI widget child of dockwidget. Same lifecycle. |
| 7063 | `_reload_shortcut.activated` | `_on_reload_layers_shortcut` | QShortcut child of `self`. Same lifecycle. |
| 7064 | `_undo_shortcut.activated` | `_on_undo_shortcut` | QShortcut child of `self`. Same lifecycle. |
| 7065 | `_redo_shortcut.activated` | `_on_redo_shortcut` | QShortcut child of `self`. Same lifecycle. |
| 6968 | various tooltip signals (loop) | tooltip update lambdas | Widgets are children of dockwidget. Same lifecycle. Connected once during init. |

#### Fuite potentielle -- Different lifecycles

| Line | Signal | Slot | Risk | Severity |
|------|--------|------|------|----------|
| 1974 | `current_layer.selectionChanged` | `on_layer_selection_changed` | Layer may be removed while dockwidget lives. Multiple connects at L342, L1974, L4794, L4817, L5689 with only 2 disconnect points (L337, L5322). Self-healing pattern at L4815-4818 can cause stacking. | **High** |
| 379 | `layer.willBeDeleted` | `_on_feature_picker_layer_deleted` | Connected per feature picker layer. Paired with disconnect at L395, but called from handler that may not fire if layer deleted differently. | Medium |
| 4137 | `picker_widget.featureChanged` | `exploring_features_changed` | Feature picker connected during layer setup. Paired with disconnect at L4133. OK. | Low |

#### A corriger -- Repeated connects in handlers

| Line | Signal | Slot | Problem | Severity |
|------|--------|------|---------|----------|
| 342, 1974, 4794, 4817, 5689, 2920 (exploring_controller) | `current_layer.selectionChanged` | `on_layer_selection_changed` | **6 connect points, 2 disconnect points.** Self-healing at L4815 and L2918 can stack connections. The `current_layer_selection_connection` flag helps, but race conditions are possible if the flag is not atomically updated. | **Critical** |
| 1748, 4137, 5628, 5988 | `picker.featureChanged` | `exploring_features_changed` | Connected in 4 places during layer change workflows. Disconnected in 3 places (L1725, L4133, L5625). Net excess: +1. | Medium |

---

### 4.2 `filter_mate_app.py` (23 connect, 15 disconnect, delta +8)

#### OK sans disconnect -- Properly managed

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 781-785 | `MapLayerStore.layersAdded/layersWillBeRemoved/allLayersRemoved` | various | Paired with disconnect at L868-870. Properly managed. |
| 814-853 | `dockwidget.launchingTask/currentLayerChanged/settingLayerVariable/etc` | various | Paired with disconnect at L879-885. Properly managed via `_disconnect_all_signals()`. |
| 846 | `PROJECT.fileNameChanged` | lambda | Disconnected at L2334 before reconnect at L2337. OK with guard. |

#### Fuite potentielle -- Task signal connections

| Line | Signal | Slot | Risk | Severity |
|------|--------|------|------|----------|
| 1083 | `appTasks[task_name].taskCompleted` | `filter_engine_task_completed` (lambda) | Connected per task creation. Tasks are replaced in `appTasks` dict. Old task's signal should be collected with the task, but if QGIS TaskManager keeps a reference, the lambda closure holds references to `current_layer` and `task_parameters`. | **High** |
| 1108 | `appTasks[task_name].begun` | `dockwidget.disconnect_widgets_signals` | Same pattern: per-task connect, no explicit disconnect. Task lifecycle managed by QgsTaskManager. | Medium |
| 1112 | `appTasks[task_name].begun` | `on_remove_layer_task_begun` | Same pattern. | Medium |
| 1115-1133 | `appTasks[task_name].resultingLayers/savingLayerVariable/removingLayerVariable/taskTerminated` | various lambdas | 4 signals connected per `_execute_layer_task()` call. No explicit disconnect. Relies on task GC. | **High** |
| 994-997 | `MapLayerStore.layersAdded/etc` (after re-assign) | various | Connected after MapLayerStore re-assignment. Old store disconnected at L987-989. OK. |
| 2149 | `favorites_manager.favorites_changed` | `controller._on_favorites_loaded` | Paired disconnect at L2146. Properly guarded. OK. |
| 2337 | `PROJECT.fileNameChanged` | lambda | Disconnect at L2334 before reconnect. OK. |

#### A corriger

| Line | Signal | Slot | Problem | Severity |
|------|--------|------|---------|----------|
| 1083, 1108, 1112, 1115-1133 | Task signals (`taskCompleted`, `begun`, `resultingLayers`, etc.) | Various lambdas | **No explicit disconnect before reassigning `appTasks[task_name]`.** If a new task is created before the old one finishes, the old task's signals remain connected to lambdas holding stale closures. The pattern should disconnect old task signals before creating a new task. | **Critical** |

---

### 4.3 `ui/controllers/integration.py` (18 connect, 18 disconnect, delta 0)

**Fully balanced.** All connects in `_connect_signals()` (L377-485) are symmetrically disconnected in `_disconnect_signals()` (L497-541) via the `_connections` tracking list. This is the model pattern.

---

### 4.4 `ui/managers/dockwidget_signal_manager.py` (11 connect, 11 disconnect, delta 0)

**Fully balanced.** Uses a `disconnect_all -> reconnect` pattern: always calls `widget.clicked.disconnect()` before `widget.clicked.connect(handler)`. The `_signal_connection_states` dict tracks state. Properly implemented.

---

### 4.5 `ui/widgets/custom_widgets.py` (17 connect, 2 disconnect, delta +15)

#### OK sans disconnect -- Same lifecycle (parent-child, __init__ connections)

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 215-229 | `action_*.triggered` | `select_all/deselect_all/select_by_geometry` | QAction created with `self` as parent. Connected in `__init__`. Same lifecycle as widget. (10 connects in `QgsCheckableComboBoxLayer.__init__`) |
| 648-660 | `action_*.triggered` | `select_all/deselect_all` (lambda) | QAction child of `QgsCheckableComboBoxLayerValues.__init__`. Same lifecycle. (6 connects) |
| 710 | `_filter_debounce_timer.timeout` | `_execute_filter` | QTimer child of widget. Same lifecycle. |

#### A corriger

| Line | Signal | Slot | Problem | Severity |
|------|--------|------|---------|----------|
| 1242 | `filter_le.textChanged` | `_on_filter_text_changed` | Connected after `disconnect()` at L1239/L1245 in `connect_filter_events()`. Called repeatedly when layer changes. The try/except disconnect pattern works, but the alternation between `textChanged` and `editingFinished` (L1248) creates confusing signal states. | Low |

---

### 4.6 `core/services/app_initializer.py` (13 connect, 1 disconnect, delta +12)

#### OK sans disconnect -- Delegated lifecycle

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 385 | `favorites_manager.favorites_changed` | `controller._on_favorites_loaded` | Preceded by disconnect at L382. Properly guarded. |

#### Fuite potentielle -- No matching disconnects

| Line | Signal | Slot | Risk | Severity |
|------|--------|------|------|----------|
| 407 | `dockwidget.widgetsInitialized` | `_on_widgets_initialized` | **No disconnect in app_initializer.** Relies on `filter_mate_app._disconnect_all_signals()` which disconnects `widgetsInitialized` globally. Works in practice but fragile -- if app_initializer is used standalone, signals leak. | Medium |
| 413 | `dockwidget.widgetsInitialized` | `task_orchestrator.on_widgets_initialized` | Same issue. Second connection to same signal. No disconnect. | Medium |
| 638 | `map_layer_store.layersAdded` | `_on_layers_added` | **No disconnect in app_initializer.** Relies on `filter_mate_app._disconnect_all_signals()`. | Medium |
| 639 | `map_layer_store.layersWillBeRemoved` | lambda | Same issue. Lambda cannot be individually disconnected. | **High** |
| 640 | `map_layer_store.allLayersRemoved` | lambda | Same issue. Lambda cannot be individually disconnected. | **High** |
| 662 | `dockwidget.launchingTask` | lambda | Lambda wrapping `_manage_task`. Cannot be individually disconnected. Relies on global disconnect. | Medium |
| 666 | `dockwidget.currentLayerChanged` | `_update_undo_redo_buttons` | Same pattern. | Medium |
| 670-678 | `dockwidget.resettingLayerVariableOnError/settingLayerVariable/resettingLayerVariable` | lambdas | 3 lambda connections. Cannot be individually disconnected. | **High** |
| 682 | `dockwidget.settingProjectVariables` | `_save_project_variables` | Same pattern. | Medium |
| 683 | `project.fileNameChanged` | lambda | **No disconnect anywhere in app_initializer.** Relies on `filter_mate_app` L2334 disconnect or project destruction. | **High** |

---

### 4.7 `core/tasks/expression_evaluation_task.py` (8 connect, 0 disconnect, delta +8)

#### OK sans disconnect -- Task lifecycle

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 93 | `task.signals.finished` | `on_evaluation_complete` | Docstring example. Not production code. |
| 463-469 | `task.signals.finished/error/progress/cancelled` | callbacks | Task-scoped connections. Task is added to QgsTaskManager and GC'd after completion. Signals die with task. **OK** as long as callbacks don't prevent GC. |
| 476-478 | `task.signals.finished/error/cancelled` | `_on_task_done` | Cleanup handler that removes task from `_active_tasks`. Same lifecycle as task. **OK.** |

---

### 4.8 `ui/widgets/history_widget.py` (8 connect, 0 disconnect, delta +8)

#### OK sans disconnect -- Parent-child, same lifecycle

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 260, 269 | `_undo_btn.clicked / _redo_btn.clicked` | `_on_undo_clicked / _on_redo_clicked` | Buttons are children of widget. Connected in `__init__`. Same lifecycle. |
| 408, 414, 423, 431 | `undo_action/redo_action/clear_action/browse_action.triggered` | various | QActions created in `_show_context_menu()`. They are parented to the context menu which is destroyed after exec. **OK.** |

---

### 4.9 `filter_mate.py` (10 connect, 7 disconnect, delta +3)

#### OK sans disconnect -- Same lifecycle

| Line | Signal | Slot | Justification |
|------|--------|------|---------------|
| 202 | `action.triggered` | `callback` | QAction child of QGIS main window. Plugin lifecycle. |
| 1304 | `discord_btn.clicked` | lambda (openUrl) | Dialog-scoped button. Destroyed with dialog. |
| 1313 | `close_btn.clicked` | `dlg.accept` | Dialog-scoped button. Destroyed with dialog. |

#### Fuite potentielle

| Line | Signal | Slot | Risk | Severity |
|------|--------|------|------|----------|
| 556 | `QgsProject.instance().readProject` | `on_project_read` | Disconnected at L1108. OK with guard, but if `_auto_activate_on_project_read` is called multiple times before disconnect, stacking occurs. | Medium |

---

### 4.10 `ui/dialogs/*` (25 connect, 0 disconnect, delta +25)

All dialog connects are to child widgets within the dialog. The dialog is destroyed when closed (`QDialog` lifecycle). **All OK.**

| File | Connects | Status |
|------|----------|--------|
| `config_editor_widget.py` | 13 | OK -- dialog child widgets |
| `favorites_manager.py` | 7 | OK -- dialog child widgets |
| `optimization_dialog.py` | 5 | OK -- dialog child widgets |
| `postgres_info_dialog.py` | 3 | OK -- dialog child widgets |

---

### 4.11 `ui/widgets/json_view/*` (18 connect, 0 disconnect, delta +18)

All connects are between parent widgets and their child UI elements. **All OK.**

| File | Connects | Status |
|------|----------|--------|
| `searchable_view.py` | 5 | OK -- child widgets, shortcuts |
| `view.py` | 1 | OK -- `customContextMenuRequested` to self |
| `theme_demo.py` | 3 | OK -- child widgets |
| `example_themes.py` | 1 | OK -- child widget |
| `model.py` | 2 | OK -- dialog buttonBox |
| `datatypes.py` | 6 | OK -- QActions in context menus (short-lived) |

---

### 4.12 `ui/controllers/exploring_controller.py` (4 connect, 1 disconnect, delta +3)

| Line | Signal | Slot | Classification | Severity |
|------|--------|------|----------------|----------|
| 1980 | `task.taskCompleted` | `_on_complete` | OK -- task lifecycle. GC'd after completion. | OK |
| 1981 | `task.taskTerminated` | `_on_error` | OK -- task lifecycle. | OK |
| 2844 | `btn_widget.clicked` | `handler` | Preceded by disconnect at L2841. Properly guarded. | OK |
| 2920 | `current_layer.selectionChanged` | `on_layer_selection_changed` | **Self-healing reconnect.** Part of the 6-connect/2-disconnect selectionChanged problem. | **High** |

---

### 4.13 `ui/controllers/favorites_controller.py` (4 connect, 1 disconnect, delta +3)

| Line | Signal | Slot | Classification | Severity |
|------|--------|------|----------------|----------|
| 67 | `controller.favorite_added` | `on_favorite_added` | Docstring example. Not production code. | OK |
| 111 | `favorites_manager.favorites_changed` | `_on_favorites_loaded` | Connected in `__init__`. | Medium |
| 154 | `favorites_manager.favorites_changed` | `_on_favorites_loaded` | Connected in `sync_with_dockwidget_manager()` after disconnect at L144. OK with guard. | OK |
| 475 | `dialog.favoriteApplied` | `apply_favorite` | Dialog-scoped. Dialog destroyed after exec. | OK |

#### Fuite potentielle

| Line | Signal | Slot | Risk | Severity |
|------|--------|------|------|----------|
| 111 | `favorites_manager.favorites_changed` | `_on_favorites_loaded` | Connected in `__init__` without matching disconnect in `__del__` or cleanup. If `FavoritesController` is destroyed while `favorites_manager` lives, the signal still fires into a dead controller. | Medium |

---

### 4.14 `ui/controllers/layer_sync_controller.py` (3 connect, 0 disconnect, delta +3)

| Line | Signal | Slot | Classification | Severity |
|------|--------|------|----------------|----------|
| 56-57 | `controller.layer_synchronized/sync_blocked` | callbacks | Docstring examples. Not production code. | OK |
| 1140 | `current_layer.selectionChanged` | `dw.on_layer_selection_changed` | **Another selectionChanged connect point!** Part of the same problem as the 6-point connect pattern. No disconnect. | **High** |

---

### 4.15 `ui/controllers/property_controller.py` (1 connect, 1 disconnect, delta 0)

| Line | Signal | Slot | Classification |
|------|--------|------|----------------|
| 681 | `picker.featureChanged` | `dw.exploring_features_changed` | Preceded by disconnect at L678. Properly guarded. OK. |

---

### 4.16 Other files

| File | Connects | Classification |
|------|----------|----------------|
| `ui/styles/theme_watcher.py` | 2 connect (L29 docstring, L69 `paletteChanged`) | L69 paired with disconnect at L87. OK. |
| `adapters/qgis/signals/debouncer.py` | 1 connect (`timer.timeout`) | QTimer child of debouncer. Same lifecycle. OK. |
| `adapters/qgis/signals/layer_signal_handler.py` | 2 connect (L173 via SignalManager, L182 raw fallback) | Both disconnected via `disconnect_layer()` at L219-229. OK. |
| `ui/widgets/favorites_widget.py` | 2 connect (`buttonBox.accepted/rejected`) | Dialog-scoped. OK. |
| `ui/managers/configuration_manager.py` | 1 (commented out `#widget.fieldChanged.connect(...)`) | Not active code. OK. |
| `adapters/qgis/filter_optimizer.py` | 1 (`psycopg2.connect` -- not Qt) | Excluded. |

---

## 5. Consolidated Issues Table

### Critical (must fix)

| ID | File(s) | Lines | Signal | Problem | Impact |
|----|---------|-------|--------|---------|--------|
| C1 | `filter_mate_dockwidget.py`, `exploring_controller.py`, `layer_sync_controller.py` | DW:342,1974,4794,4817,5689 / EC:2920 / LSC:1140 | `current_layer.selectionChanged` | **7 connect points, only 2 disconnect points** (DW:337, DW:5322). Self-healing at DW:4815 and EC:2918 can stack connections. The `current_layer_selection_connection` boolean flag is insufficient for a multi-point connect pattern. | Signal stacking causes handler to fire N times per event. Memory leak if old layer is kept alive by signal reference. |
| C2 | `filter_mate_app.py` | 1083,1108,1112,1115-1133 | `appTasks[task_name].*` (taskCompleted, begun, resultingLayers, savingLayerVariable, removingLayerVariable, taskTerminated) | **6-7 signals connected per task creation, never explicitly disconnected.** If task is replaced in `appTasks` dict before completion, old task signals remain connected to lambdas holding stale closures. | Lambda closures hold references to `current_layer`, `task_parameters`. Stale closures can trigger actions on wrong layer. |

### High (should fix)

| ID | File(s) | Lines | Signal | Problem | Impact |
|----|---------|-------|--------|---------|--------|
| H1 | `core/services/app_initializer.py` | 639,640 | `map_layer_store.layersWillBeRemoved/allLayersRemoved` | Lambda connections cannot be individually disconnected. `disconnect()` without args disconnects ALL receivers. | Risk of disconnecting other receivers during cleanup. |
| H2 | `core/services/app_initializer.py` | 670-678 | `dockwidget.resettingLayerVariableOnError/settingLayerVariable/resettingLayerVariable` | 3 lambda connections with no disconnect in app_initializer. | Signals fire into dead lambdas if app_initializer is destroyed before dockwidget. |
| H3 | `core/services/app_initializer.py` | 683 | `project.fileNameChanged` | Lambda connection to `_save_project_variables()`. No disconnect in app_initializer. | Stale lambda after project change if not cleaned up by `filter_mate_app`. |
| H4 | `filter_mate_dockwidget.py` | 1748,4137,5628,5988 | `picker.featureChanged` | 4 connect points, 3 disconnect points. Net +1 per layer change cycle. | Gradual signal stacking over time. |

### Medium (monitor)

| ID | File(s) | Lines | Signal | Problem |
|----|---------|-------|--------|---------|
| M1 | `core/services/app_initializer.py` | 407,413 | `dockwidget.widgetsInitialized` | 2 different receivers connected, no disconnect. Relies on `filter_mate_app._disconnect_all_signals()`. |
| M2 | `core/services/app_initializer.py` | 638,662,666,682 | `map_layer_store.layersAdded`, `dockwidget.launchingTask/currentLayerChanged/settingProjectVariables` | No disconnect in app_initializer. Relies on `filter_mate_app`. |
| M3 | `filter_mate.py` | 556 | `QgsProject.instance().readProject` | Possible stacking if `_auto_activate_on_project_read` called multiple times. |
| M4 | `ui/controllers/favorites_controller.py` | 111 | `favorites_manager.favorites_changed` | No disconnect in `__init__`. Controller may outlive manager reassignment. |
| M5 | `filter_mate_dockwidget.py` | 379 | `layer.willBeDeleted` | Connected per feature picker layer. Disconnect at L395 may not fire if layer deleted unexpectedly. |

### Low / OK (no action needed)

All dialog, widget `__init__`, and json_view connects are between parent-child Qt objects with the same lifecycle. These are safe and do not require explicit disconnect.

---

## 6. Architecture Observations

### 6.1 The `app_initializer.py` Problem

`app_initializer.py` connects 12 signals but has only 1 disconnect (favorites). It is designed as a **one-shot setup helper** but has no `teardown()` or `disconnect_all()` method. It relies entirely on `filter_mate_app._disconnect_all_signals()` to clean up, which uses blanket `signal.disconnect()` (no args) to disconnect ALL receivers. This works but:

1. Disconnects receivers connected by OTHER components (integration.py, dockwidget, etc.)
2. Cannot selectively disconnect app_initializer's lambda connections
3. Is fragile if call order changes

**Recommendation:** Add a `_disconnect_all()` method to `app_initializer.py` that mirrors `_connect_*` methods. Store connection references (not lambdas) for disconnection.

### 6.2 The `selectionChanged` Problem

The `current_layer.selectionChanged` signal is connected in **7 different code paths** across 3 files:

1. `filter_mate_dockwidget.py` L342 -- `_update_current_layer_connections()`
2. `filter_mate_dockwidget.py` L1974 -- `init_widgets()` guard
3. `filter_mate_dockwidget.py` L4794 -- `_ensure_selection_changed_connected()`
4. `filter_mate_dockwidget.py` L4817 -- `on_layer_selection_changed()` self-healing
5. `filter_mate_dockwidget.py` L5689 -- `_update_exploring_widgets()`
6. `ui/controllers/exploring_controller.py` L2920 -- `handle_layer_selection_changed()` self-healing
7. `ui/controllers/layer_sync_controller.py` L1140 -- `_reconnect_selection_signal()`

But only 2 disconnect points exist:
1. `filter_mate_dockwidget.py` L337 -- `_update_current_layer_connections()`
2. `filter_mate_dockwidget.py` L5322 -- during layer cleanup

The `current_layer_selection_connection` boolean is used as a guard, but it cannot account for multi-point connections or race conditions.

**Recommendation:** Centralize `selectionChanged` management into a single method (`_connect_selection_signal()` / `_disconnect_selection_signal()`) that is the ONLY way to connect/disconnect this signal. Remove all self-healing reconnects and instead fix the root cause of disconnections.

### 6.3 The Task Signal Pattern

Task signals in `filter_mate_app.py` (L1083-1133) are connected per-task-creation without disconnect. This pattern is acceptable **only if**:
- The old task reference is dropped (GC cleans up signals)
- The old task is cancelled before a new one is created
- Lambda closures don't hold references that prevent GC

Currently, `_cancel_conflicting_tasks()` is called at L1089, which should cancel old tasks. However, if QgsTaskManager holds a reference to the task, the lambdas persist.

**Recommendation:** Explicitly disconnect old task signals before reassigning `appTasks[task_name]`, or use a `weakref` in lambda closures.

### 6.4 Model Pattern: `integration.py`

`ui/controllers/integration.py` is the gold standard: 18 connects, 18 disconnects, tracked via `_connections` list. Every `_connect_signals()` has a symmetric `_disconnect_signals()`. This pattern should be replicated in `app_initializer.py` and `filter_mate_app.py`.

### 6.5 Model Pattern: `dockwidget_signal_manager.py`

Also 11/11, using `disconnect_all -> reconnect` pattern with `_signal_connection_states` tracking. Clean and reliable.

---

## 7. Prioritized Recommendations

| Priority | Action | Files | Effort |
|----------|--------|-------|--------|
| **P0** | Centralize `selectionChanged` connect/disconnect into single entry point | `filter_mate_dockwidget.py`, `exploring_controller.py`, `layer_sync_controller.py` | Medium |
| **P0** | Add explicit disconnect of old task signals before re-creating tasks in `appTasks` | `filter_mate_app.py` | Low |
| **P1** | Add `teardown()` / `_disconnect_all()` to `app_initializer.py` mirroring the connect methods | `core/services/app_initializer.py` | Medium |
| **P1** | Replace lambda connections in `app_initializer.py` with named methods for clean disconnect | `core/services/app_initializer.py` | Medium |
| **P1** | Audit `picker.featureChanged` connect/disconnect balance across all 4 connect points | `filter_mate_dockwidget.py` | Low |
| **P2** | Add cleanup for `favorites_controller` `__init__` connect (L111) | `ui/controllers/favorites_controller.py` | Low |
| **P2** | Guard `readProject` signal stacking in `filter_mate.py` L556 | `filter_mate.py` | Low |

---

## 8. Summary Statistics

```
Total raw .connect( calls:     267 (53 files)
Total raw .disconnect( calls:  104 (20 files)
Raw ratio:                     2.57:1

Non-Qt excluded:               41 connect, 12 disconnect
SignalManager/utils internal:  ~15 connect, ~14 disconnect
Docstring/comment examples:    ~5 connect

Effective Qt signal connects:  ~196
Effective Qt disconnects:      ~92  (including blanket disconnects)
Effective ratio:               2.13:1

Classification of ~104 unmatched:
  OK (same lifecycle):         ~72 (69%)
  Potential leak:              ~22 (21%)
  Must fix:                    ~10 (10%)
```

**Target ratio:** 1.5:1 or lower (some signals legitimately don't need disconnect due to parent-child lifecycle).

**Estimated fixes needed:** 10-15 code changes across 5 files to reach target ratio and eliminate all Critical/High issues.
