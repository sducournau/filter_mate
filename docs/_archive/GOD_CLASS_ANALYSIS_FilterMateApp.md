# FilterMateApp God Class Analysis

**File**: [filter_mate_app.py](../filter_mate_app.py)  
**Total Lines**: 6,041  
**Total Methods**: 101  
**Analysis Date**: January 9, 2026

---

## 📊 Executive Summary

| Metric                        | Value                    |
| ----------------------------- | ------------------------ |
| Total methods                 | 101                      |
| Nested/Local functions        | ~35                      |
| Top-level class methods       | ~66                      |
| Already extracted to adapters | ~20 (duplicated)         |
| Migration priority            | HIGH - Core orchestrator |

---

## 📋 Complete Method List by Category

### 1. 🔧 Initialization & Setup Methods

| Method                                 | Line | Lines Est. | Extracted?      |
| -------------------------------------- | ---- | ---------- | --------------- |
| `__init__`                             | 526  | ~135       | ❌ No           |
| `_init_hexagonal_services` (static)    | 98   | 3          | ✅ Wrapper only |
| `_cleanup_hexagonal_services` (static) | 101  | 3          | ✅ Wrapper only |
| `_hexagonal_initialized` (static)      | 104  | 3          | ✅ Wrapper only |
| `_get_history_max_size_from_config`    | 663  | ~20        | ❌ No           |
| `_init_feedback_level`                 | 683  | ~18        | ❌ No           |
| `_get_dock_position`                   | 701  | ~31        | ❌ No           |
| `run`                                  | 996  | ~420       | ❌ No (complex) |

**Subtotal**: 8 methods, ~633 lines  
**Migration Status**: Partial - hexagonal services wrapped

---

### 2. ⚡ Task Management Methods

| Method                           | Line | Lines Est. | Extracted?              |
| -------------------------------- | ---- | ---------- | ----------------------- |
| `manage_task`                    | 1830 | ~430       | ⚠️ Partial (TaskBridge) |
| `_try_delegate_to_controller`    | 2566 | ~68        | ✅ Uses TaskBridge      |
| `get_task_parameters`            | 3412 | ~328       | ❌ No                   |
| `_build_common_task_params`      | 3273 | ~116       | ❌ No                   |
| `_build_layer_management_params` | 3389 | ~23        | ❌ No                   |
| `_safe_cancel_all_tasks`         | 2264 | ~23        | ❌ No                   |
| `_cancel_layer_tasks`            | 2287 | ~28        | ❌ No                   |
| `_handle_layer_task_terminated`  | 2315 | ~71        | ❌ No                   |
| `_process_add_layers_queue`      | 2386 | ~35        | ❌ No                   |

**Subtotal**: 9 methods, ~1,122 lines  
**Extracted Adapter**: [adapters/task_bridge.py](../adapters/task_bridge.py), [adapters/task_builder.py](../adapters/task_builder.py)

---

### 3. 🔄 Project/Layer Lifecycle Methods

| Method                              | Line | Lines Est. | Extracted?              |
| ----------------------------------- | ---- | ---------- | ----------------------- |
| `_handle_project_initialization`    | 1584 | ~246       | ❌ No                   |
| `_handle_remove_all_layers`         | 1519 | ~65        | ❌ No                   |
| `_on_layers_added`                  | 271  | ~109       | ❌ No                   |
| `_filter_usable_layers`             | 184  | ~87        | ❌ No                   |
| `cleanup`                           | 380  | ~61        | ❌ No                   |
| `_cleanup_postgresql_session_views` | 441  | ~85        | ❌ No                   |
| `force_reload_layers`               | 826  | ~170       | ❌ No                   |
| `_is_layer_valid`                   | 976  | ~20        | ✅ object_safety module |

**Subtotal**: 8 methods, ~843 lines  
**Extracted Service**: ❌ Not yet (candidate for LayerLifecycleService)

---

### 4. 🎯 Filter Execution Methods

| Method                              | Line | Lines Est. | Extracted? |
| ----------------------------------- | ---- | ---------- | ---------- |
| `filter_engine_task_completed`      | 4275 | ~417       | ⚠️ Partial |
| `apply_subset_filter`               | 4692 | ~92        | ❌ No      |
| `_build_layers_to_filter`           | 2990 | ~219       | ❌ No      |
| `_initialize_filter_history`        | 3209 | ~64        | ❌ No      |
| `_check_and_confirm_optimizations`  | 2634 | ~258       | ❌ No      |
| `_apply_optimization_to_ui_widgets` | 2892 | ~98        | ❌ No      |

**Subtotal**: 6 methods, ~1,148 lines  
**Extracted Service**: [core/services/filter_service.py](../core/services/filter_service.py) (FilterService class)

---

### 5. ↩️ Undo/Redo Methods

| Method                     | Line | Lines Est. | Extracted?         |
| -------------------------- | ---- | ---------- | ------------------ |
| `handle_undo`              | 3893 | ~161       | ✅ UndoRedoHandler |
| `handle_redo`              | 4054 | ~161       | ✅ UndoRedoHandler |
| `update_undo_redo_buttons` | 3851 | ~42        | ✅ UndoRedoHandler |
| `_push_filter_to_history`  | 3791 | ~60        | ✅ UndoRedoHandler |
| `_clear_filter_history`    | 4215 | ~29        | ✅ UndoRedoHandler |

**Subtotal**: 5 methods, ~453 lines  
**Extracted Adapter**: [adapters/undo_redo_handler.py](../adapters/undo_redo_handler.py) ✅ Complete

---

### 6. 💾 Database/Persistence Methods

| Method                        | Line | Lines Est. | Extracted?              |
| ----------------------------- | ---- | ---------- | ----------------------- |
| `init_filterMate_db`          | 5306 | ~101       | ✅ DatabaseManager      |
| `get_spatialite_connection`   | 1497 | ~22        | ✅ DatabaseManager      |
| `_ensure_db_directory`        | 5107 | ~20        | ✅ DatabaseManager      |
| `_create_db_file`             | 5127 | ~45        | ✅ DatabaseManager      |
| `_initialize_schema`          | 5172 | ~72        | ✅ DatabaseManager      |
| `_migrate_schema_if_needed`   | 5244 | ~30        | ✅ DatabaseManager      |
| `_load_or_create_project`     | 5274 | ~32        | ✅ DatabaseManager      |
| `add_project_datasource`      | 5407 | ~32        | ❌ No                   |
| `save_project_variables`      | 5439 | ~47        | ✅ ProjectSettingsSaver |
| `update_datasource`           | 5928 | ~63        | ❌ No                   |
| `create_foreign_data_wrapper` | 5991 | ~31        | ❌ No                   |

**Subtotal**: 11 methods, ~495 lines  
**Extracted Adapter**: [adapters/database_manager.py](../adapters/database_manager.py) ✅ Mostly complete

---

### 7. 📦 Variables/Properties Persistence Methods

| Method                        | Line | Lines Est. | Extracted?                     |
| ----------------------------- | ---- | ---------- | ------------------------------ |
| `_save_single_property`       | 4784 | ~108       | ✅ VariablesPersistenceManager |
| `save_variables_from_layer`   | 4892 | ~85        | ✅ VariablesPersistenceManager |
| `remove_variables_from_layer` | 4977 | ~115       | ✅ VariablesPersistenceManager |

**Subtotal**: 3 methods, ~308 lines  
**Extracted Adapter**: [adapters/variables_manager.py](../adapters/variables_manager.py) ✅ Complete

---

### 8. 🖼️ UI Refresh/Coordination Methods

| Method                               | Line | Lines Est. | Extracted?                 |
| ------------------------------------ | ---- | ---------- | -------------------------- |
| `_refresh_layers_and_canvas`         | 3740 | ~51        | ✅ LayerRefreshManager     |
| `_show_task_completion_message`      | 4244 | ~31        | ✅ TaskCompletionMessenger |
| `_force_ui_refresh_after_reload`     | 5727 | ~100       | ❌ No                      |
| `_refresh_ui_after_project_load`     | 5827 | ~52        | ❌ No                      |
| `_on_widgets_initialized`            | 2509 | ~27        | ❌ No                      |
| `_is_dockwidget_ready_for_filtering` | 2461 | ~48        | ❌ No                      |
| `_warm_query_cache_for_layers`       | 2421 | ~40        | ❌ No                      |

**Subtotal**: 7 methods, ~349 lines  
**Extracted Adapter**: [adapters/layer_refresh_manager.py](../adapters/layer_refresh_manager.py) ✅ Partial

---

### 9. 🔌 Layer Management Engine Methods

| Method                                      | Line | Lines Est. | Extracted? |
| ------------------------------------------- | ---- | ---------- | ---------- |
| `layer_management_engine_task_completed`    | 5486 | ~144       | ❌ No      |
| `_validate_layer_info`                      | 5630 | ~28        | ❌ No      |
| `_update_datasource_for_layer`              | 5658 | ~37        | ❌ No      |
| `_remove_datasource_for_layer`              | 5695 | ~32        | ❌ No      |
| `_validate_postgres_layers_on_project_load` | 5879 | ~49        | ❌ No      |
| `create_spatial_index_for_layer`            | 5092 | ~15        | ❌ No      |

**Subtotal**: 6 methods, ~305 lines  
**Extracted Service**: ❌ Not yet (candidate for LayerManagementService)

---

### 10. 🛡️ Stability/Safety Methods

| Method                             | Line | Lines Est. | Extracted? |
| ---------------------------------- | ---- | ---------- | ---------- |
| `_check_and_reset_stale_flags`     | 732  | ~66        | ❌ No      |
| `_set_loading_flag`                | 798  | ~14        | ❌ No      |
| `_set_initializing_flag`           | 812  | ~14        | ❌ No      |
| `_safe_layer_operation`            | 1418 | ~79        | ❌ No      |
| `safe_show_message` (module-level) | 119  | ~32        | ❌ No      |
| `on_remove_layer_task_begun`       | 2536 | ~30        | ❌ No      |

**Subtotal**: 6 methods, ~235 lines  
**Extracted Module**: [modules/object_safety.py](../modules/object_safety.py) (partial)

---

### 11. 🔧 Utility Methods

| Method                            | Line | Lines Est. | Extracted?               |
| --------------------------------- | ---- | ---------- | ------------------------ |
| `can_cast`                        | 6022 | ~8         | ✅ modules/type_utils.py |
| `return_typped_value`             | 6030 | ~8         | ✅ modules/type_utils.py |
| `zoom_to_features` (module-level) | 6038 | ~5         | ❌ No                    |

**Subtotal**: 3 methods, ~21 lines  
**Migration Status**: ✅ Complete

---

### 12. 🔗 Nested/Local Functions (Internal Callbacks)

These are defined inside other methods and represent significant complexity:

| Parent Method                            | Nested Function                  | Line | Purpose                  |
| ---------------------------------------- | -------------------------------- | ---- | ------------------------ |
| `_on_layers_added`                       | `safe_callback`                  | 286  | Safe callback wrapper    |
| `_on_layers_added`                       | `retry_postgres`                 | 346  | PostgreSQL retry logic   |
| `force_reload_layers`                    | `safe_add_layers`                | 936  | Safe layer addition      |
| `force_reload_layers`                    | `safe_ui_refresh`                | 945  | Safe UI refresh          |
| `run`                                    | `wait_for_widget_initialization` | 1127 | Widget init wait         |
| `run`                                    | `check_and_add`                  | 1132 | Check and add layers     |
| `run`                                    | `safe_wait_init`                 | 1149 | Safe initialization wait |
| `run`                                    | `ensure_ui_enabled`              | 1158 | Ensure UI enabled        |
| `run`                                    | `safe_retry_add`                 | 1217 | Safe retry add           |
| `run`                                    | `ensure_ui_enabled_final`        | 1250 | Final UI enable          |
| `run`                                    | `safe_ensure_ui`                 | 1317 | Safe UI ensure           |
| `run`                                    | `safe_add_new_layers`            | 1362 | Safe add new layers      |
| `run`                                    | `safe_add_layers_refresh`        | 1377 | Safe refresh             |
| `_safe_layer_operation`                  | `deferred_operation`             | 1457 | Deferred operation       |
| `_handle_project_initialization`         | `trigger_add_layers`             | 1736 | Trigger layer add        |
| `_handle_project_initialization`         | `retry_postgres_layers`          | 1750 | PostgreSQL retry         |
| `_handle_project_initialization`         | `refresh_after_load`             | 1790 | Refresh after load       |
| `manage_task`                            | `safe_deferred_task`             | 1911 | Safe deferred task       |
| `manage_task`                            | `safe_emergency_retry`           | 1946 | Emergency retry          |
| `manage_task`                            | `safe_filter_retry`              | 1960 | Filter retry             |
| `_handle_layer_task_terminated`          | `safe_layer_retry`               | 2360 | Safe layer retry         |
| `_on_widgets_initialized`                | `safe_process_queue`             | 2530 | Safe queue process       |
| `_refresh_layers_and_canvas`             | `do_refresh`                     | 3762 | Do refresh               |
| `handle_undo`                            | `restore_combobox_if_needed`     | 4020 | Restore combobox         |
| `handle_redo`                            | `restore_combobox_if_needed`     | 4181 | Restore combobox         |
| `filter_engine_task_completed`           | `restore_combobox_if_needed`     | 4625 | Restore combobox         |
| `layer_management_engine_task_completed` | `safe_process_queue_on_complete` | 5611 | Safe queue complete      |
| `layer_management_engine_task_completed` | `safe_ui_refresh`                | 5624 | Safe UI refresh          |
| `_force_ui_refresh_after_reload`         | `safe_force_refresh_retry`       | 5755 | Safe refresh retry       |

**Subtotal**: ~35 nested functions (significant complexity hidden inside methods)

---

## 📈 Migration Status Summary

| Category                | Methods | Lines Est. | Extracted | Coverage    |
| ----------------------- | ------- | ---------- | --------- | ----------- |
| Initialization          | 8       | 633        | 3         | 37%         |
| Task Management         | 9       | 1,122      | 2         | 22%         |
| Project/Layer Lifecycle | 8       | 843        | 1         | 12%         |
| Filter Execution        | 6       | 1,148      | 1         | 17%         |
| Undo/Redo               | 5       | 453        | 5         | **100%** ✅ |
| Database/Persistence    | 11      | 495        | 8         | **73%**     |
| Variables Persistence   | 3       | 308        | 3         | **100%** ✅ |
| UI Refresh              | 7       | 349        | 2         | 29%         |
| Layer Management Engine | 6       | 305        | 0         | 0%          |
| Stability/Safety        | 6       | 235        | 0         | 0%          |
| Utilities               | 3       | 21         | 2         | 67%         |
| **TOTAL**               | **72**  | **5,912**  | **27**    | **37%**     |

---

## 🎯 Extracted Adapters & Services (New Architecture)

### Already Extracted

| Adapter/Service             | File                                | Methods | Status      |
| --------------------------- | ----------------------------------- | ------- | ----------- |
| UndoRedoHandler             | `adapters/undo_redo_handler.py`     | 12      | ✅ Complete |
| VariablesPersistenceManager | `adapters/variables_manager.py`     | 4       | ✅ Complete |
| DatabaseManager             | `adapters/database_manager.py`      | 10      | ✅ Complete |
| LayerRefreshManager         | `adapters/layer_refresh_manager.py` | 5       | ✅ Complete |
| TaskCompletionMessenger     | `adapters/layer_refresh_manager.py` | 4       | ✅ Complete |
| TaskBridge                  | `adapters/task_bridge.py`           | 15      | ✅ Complete |
| FilterService               | `core/services/filter_service.py`   | 15      | ✅ Complete |
| HistoryService              | `core/services/history_service.py`  | 12      | ✅ Complete |

### Still in God Class (Needs Extraction)

| Candidate Service         | Methods | Priority | Rationale                      |
| ------------------------- | ------- | -------- | ------------------------------ |
| LayerLifecycleService     | 8       | **HIGH** | Project init, layer add/remove |
| TaskParameterBuilder      | 4       | **HIGH** | Complex param construction     |
| FilterOptimizationService | 2       | MEDIUM   | Optimization confirmation      |
| LayerManagementService    | 6       | MEDIUM   | Layer engine completion        |
| StabilityGuardService     | 6       | LOW      | Flag management                |

---

## 🚦 Migration Priority Recommendations

### 🔴 HIGH Priority (Next Phase)

1. **TaskParameterBuilder** (extract `get_task_parameters`, `_build_*_params`)

   - 4 methods, ~467 lines
   - Reason: Pure data transformation, no side effects
   - Target: `adapters/task_builder.py` (extend existing)

2. **LayerLifecycleService** (extract lifecycle methods)

   - 8 methods, ~843 lines
   - Reason: Core business logic, reusable
   - Target: `core/services/layer_lifecycle_service.py`

3. **Refactor `manage_task`** (break into smaller methods)
   - 1 method, ~430 lines
   - Reason: Central dispatcher too complex
   - Target: Split into task-specific handlers

### 🟡 MEDIUM Priority

4. **LayerManagementService** (extract engine completion)

   - 6 methods, ~305 lines
   - Target: `core/services/layer_management_service.py`

5. **FilterOptimizationService** (extract optimization logic)
   - 2 methods, ~356 lines
   - Target: `core/services/filter_optimizer.py` (extend existing)

### 🟢 LOW Priority

6. **StabilityGuardService** (extract flag management)
   - 6 methods, ~235 lines
   - Target: `infrastructure/stability.py`

---

## 📉 Complexity Hotspots

### Methods with Most Nested Functions

| Method                           | Nested Count | Total Lines |
| -------------------------------- | ------------ | ----------- |
| `run`                            | 8            | ~420        |
| `manage_task`                    | 3            | ~430        |
| `_handle_project_initialization` | 3            | ~246        |
| `filter_engine_task_completed`   | 1            | ~417        |

### Recommendation

These methods should be decomposed into smaller, testable units. The nested functions indicate callback complexity that could be replaced with async/await patterns or dedicated handler classes.

---

## 🔄 Strangler Fig Pattern Progress

The codebase uses the Strangler Fig pattern (see `_try_delegate_to_controller`):

```python
# v3.0: MIG-025 - Try delegating to hexagonal controllers
if task_name in ('filter', 'unfilter', 'reset'):
    if self._try_delegate_to_controller(task_name, data):
        logger.info(f"v3.0: Task '{task_name}' delegated to controller successfully")
```

**Current State**:

- Filter/unfilter/reset: Delegable via TaskBridge
- Layer management: Still in legacy code
- Project lifecycle: Still in legacy code

---

## ✅ Conclusion

FilterMateApp remains a God Class with **72 public methods** and **35+ nested functions** totaling **~6,000 lines**. However, significant progress has been made:

- **37% of methods** already have extracted equivalents
- **Undo/Redo** and **Variables Persistence** are **100% extracted**
- **Database operations** are **73% extracted**

Next steps should focus on:

1. Completing TaskParameterBuilder extraction
2. Creating LayerLifecycleService
3. Breaking down `manage_task` and `run` methods
4. Incrementally delegating more operations via Strangler Fig pattern

The goal is to reduce FilterMateApp to a thin orchestration layer that delegates to specialized services.
