# FilterMateDockWidget God Class Analysis

**File**: `filter_mate_dockwidget.py`  
**Total Lines**: 13,067  
**Total Methods**: 248 (including nested functions)  
**Analysis Date**: January 9, 2026

---

## Executive Summary

The `FilterMateDockWidget` class is a "god class" containing 248 methods across multiple responsibility domains. This analysis categorizes all methods and identifies migration opportunities to the new modular architecture.

### Key Statistics

| Category            | Methods | Approx. Lines | % of Total |
| ------------------- | ------- | ------------- | ---------- |
| Layout/UI Setup     | 42      | ~2,100        | 16%        |
| Style/Theme         | 15      | ~550          | 4%         |
| Filtering Logic     | 18      | ~750          | 6%         |
| Exploring Logic     | 38      | ~3,200        | 24%        |
| Exporting Logic     | 10      | ~400          | 3%         |
| Config/Settings     | 24      | ~1,200        | 9%         |
| Layer Sync          | 22      | ~1,800        | 14%        |
| Signal/Slot         | 12      | ~600          | 5%         |
| Property Management | 16      | ~1,000        | 8%         |
| Favorites           | 16      | ~900          | 7%         |
| Undo/Redo           | 2       | ~30           | <1%        |
| Backend             | 20      | ~1,000        | 8%         |
| Utilities/Events    | 33      | ~540          | 4%         |

---

## Detailed Method Analysis by Category

### 1. Layout/UI Setup Methods (42 methods, ~2,100 lines)

| Line  | Method                                           | Responsibility              |
| ----- | ------------------------------------------------ | --------------------------- |
| 680   | `setupUiCustom`                                  | Main UI setup orchestration |
| 703   | `_setup_main_splitter`                           | Splitter configuration      |
| 789   | `_apply_splitter_frame_policies`                 | Frame policies              |
| 829   | `_set_initial_splitter_sizes`                    | Initial sizes               |
| 857   | `apply_dynamic_dimensions`                       | Dynamic sizing              |
| 897   | `_apply_dockwidget_dimensions`                   | Widget dimensions           |
| 925   | `_apply_widget_dimensions`                       | Sub-widget sizing           |
| 973   | `_apply_frame_dimensions`                        | Frame sizing                |
| 1062  | `_harmonize_checkable_pushbuttons`               | Button harmonization        |
| 1174  | `_apply_layout_spacing`                          | Layout spacing              |
| 1286  | `_harmonize_spacers`                             | Spacer adjustment           |
| 1355  | `_apply_qgis_widget_dimensions`                  | QGIS widget sizing          |
| 1424  | `_align_key_layouts`                             | Layout alignment            |
| 1567  | `_adjust_row_spacing`                            | Row spacing                 |
| 4067  | `_setup_action_bar_layout`                       | Action bar setup            |
| 4101  | `_get_action_bar_position`                       | Position getter             |
| 4116  | `_get_action_bar_vertical_alignment`             | Alignment getter            |
| 4133  | `_apply_action_bar_position`                     | Position application        |
| 4185  | `_adjust_header_for_side_position`               | Header adjustment           |
| 4253  | `_restore_header_from_wrapper`                   | Header restoration          |
| 4299  | `_clear_action_bar_layout`                       | Layout clearing             |
| 4319  | `_create_horizontal_action_layout`               | Horizontal layout           |
| 4348  | `_create_vertical_action_layout`                 | Vertical layout             |
| 4372  | `_apply_action_bar_size_constraints`             | Size constraints            |
| 4417  | `_reposition_action_bar_in_main_layout`          | Repositioning               |
| 4443  | `_create_horizontal_wrapper_for_side_action_bar` | Side wrapper                |
| 4560  | `_restore_side_action_bar_layout`                | Side restoration            |
| 4606  | `_restore_original_layout`                       | Original restoration        |
| 4632  | `_setup_exploring_tab_widgets`                   | Exploring tab setup         |
| 4915  | `_setup_filtering_tab_widgets`                   | Filtering tab setup         |
| 4986  | `_setup_exporting_tab_widgets`                   | Exporting tab setup         |
| 5749  | `_setup_reload_button`                           | Reload button setup         |
| 6306  | `_configure_key_widgets_sizes`                   | Key widget sizes            |
| 12825 | `_setup_truncation_tooltips`                     | Tooltip setup               |
| 12977 | `_setup_keyboard_shortcuts`                      | Keyboard shortcuts          |
| 656   | `_fix_toolbox_icons`                             | Toolbox icon fix            |
| 598   | `reset_multiple_checkable_combobox`              | ComboBox reset              |
| 652   | `set_multiple_checkable_combobox`                | ComboBox setup              |
| 1633  | `_setup_backend_indicator`                       | Backend indicator           |
| 5812  | `set_widget_icon`                                | Widget icon setting         |
| 5843  | `switch_widget_icon`                             | Icon switching              |
| 5857  | `icon_per_geometry_type`                         | Geometry icons              |

**New Architecture Equivalent**: `ui/layout/` module

- `SplitterManager` (partial - splitter methods)
- `DimensionsManager` (partial - dimension methods)
- `SpacingManager` (partial - spacing methods)
- `ActionBarManager` (partial - action bar methods)

**Migration Status**: 🟡 Partial (~40% extracted)

---

### 2. Style/Theme Methods (15 methods, ~550 lines)

| Line  | Method                              | Responsibility           |
| ----- | ----------------------------------- | ------------------------ |
| 6156  | `_apply_auto_configuration`         | Auto config              |
| 6181  | `_apply_stylesheet`                 | Stylesheet application   |
| 6193  | `_configure_pushbuttons`            | Button configuration     |
| 6272  | `_configure_other_widgets`          | Widget configuration     |
| 6343  | `manage_ui_style`                   | Style orchestration      |
| 6397  | `_setup_theme_watcher`              | Theme watching           |
| 6431  | `_on_qgis_theme_changed`            | Theme change handler     |
| 6471  | `_refresh_icons_for_theme`          | Icon refresh             |
| 5303  | `_apply_theme_change`               | Theme change application |
| 5350  | `_apply_ui_profile_change`          | Profile change           |
| 5410  | `_apply_action_bar_position_change` | Position change          |
| 5479  | `_apply_export_style_change`        | Export style             |
| 5521  | `_apply_export_format_change`       | Export format            |
| 12859 | `_update_combo_tooltip`             | Combo tooltips           |
| 12878 | `_update_checkable_combo_tooltip`   | Checkable tooltips       |

**New Architecture Equivalent**: `ui/styles/` module

- `ThemeManager` ✅
- `IconManager` ✅
- `ButtonStyler` ✅
- `BaseStyler` ✅

**Migration Status**: 🟢 Mostly extracted (~70%)

---

### 3. Filtering Logic Methods (18 methods, ~750 lines)

| Line  | Method                                           | Responsibility          |
| ----- | ------------------------------------------------ | ----------------------- |
| 5890  | `filtering_populate_predicates_chekableCombobox` | Predicate population    |
| 5896  | `filtering_populate_buffer_type_combobox`        | Buffer type population  |
| 5906  | `filtering_populate_layers_chekableCombobox`     | Layers population       |
| 9533  | `get_layers_to_filter`                           | Get filter layers       |
| 11561 | `filtering_init_buffer_property`                 | Buffer init             |
| 11610 | `filtering_buffer_property_changed`              | Buffer change           |
| 11679 | `get_buffer_property_state`                      | Buffer state            |
| 11683 | `filtering_layers_to_filter_state_changed`       | Layer state change      |
| 11699 | `filtering_combine_operator_state_changed`       | Combine operator change |
| 11715 | `filtering_geometric_predicates_state_changed`   | Predicates change       |
| 11730 | `filtering_buffer_type_state_changed`            | Buffer type change      |
| 11745 | `_update_centroids_source_checkbox_state`        | Centroid checkbox       |
| 11865 | `filtering_auto_current_layer_changed`           | Auto layer change       |
| 12443 | `_reset_filtering_button_states`                 | Button reset            |
| 5038  | `_index_to_combine_operator`                     | Index to operator       |
| 5057  | `_combine_operator_to_index`                     | Operator to index       |
| 11214 | `_update_buffer_spinbox_style`                   | Buffer style            |
| 11243 | `_update_buffer_validation`                      | Buffer validation       |

**New Architecture Equivalent**: `ui/controllers/filtering_controller.py` + `core/services/filter_service.py`

**Migration Status**: 🔴 Minimal (~20% extracted)

---

### 4. Exploring Logic Methods (38 methods, ~3,200 lines)

| Line  | Method                                        | Responsibility         |
| ----- | --------------------------------------------- | ---------------------- |
| 7115  | `exploring_groupbox_init`                     | Groupbox init          |
| 7143  | `_update_exploring_buttons_state`             | Button state update    |
| 7196  | `_configure_single_selection_groupbox`        | Single selection       |
| 7286  | `_configure_multiple_selection_groupbox`      | Multiple selection     |
| 7363  | `_configure_custom_selection_groupbox`        | Custom selection       |
| 7430  | `exploring_groupbox_changed`                  | Groupbox change        |
| 7484  | `exploring_identify_clicked`                  | Identify click         |
| 7562  | `get_current_features`                        | Get features           |
| 7834  | `exploring_zoom_clicked`                      | Zoom click             |
| 7909  | `get_filtered_layer_extent`                   | Layer extent           |
| 7975  | `_compute_zoom_extent_for_mode`               | Zoom extent            |
| 8093  | `zooming_to_features`                         | Feature zooming        |
| 8237  | `on_layer_selection_changed`                  | Selection change       |
| 8310  | `_sync_widgets_from_qgis_selection`           | Widget sync            |
| 8381  | `_sync_single_selection_from_qgis`            | Single sync            |
| 8433  | `_sync_multiple_selection_from_qgis`          | Multiple sync          |
| 8588  | `exploring_source_params_changed`             | Params change          |
| 8725  | `exploring_custom_selection`                  | Custom selection       |
| 8778  | `exploring_deselect_features`                 | Deselect               |
| 8791  | `exploring_select_features`                   | Select                 |
| 8830  | `exploring_features_changed`                  | Features change        |
| 8950  | `_handle_exploring_features_result`           | Result handler         |
| 9026  | `get_exploring_features`                      | Get features           |
| 9275  | `get_exploring_features_async`                | Async features         |
| 9363  | `cancel_async_expression_evaluation`          | Cancel async           |
| 9374  | `should_use_async_expression`                 | Async decision         |
| 9397  | `exploring_link_widgets`                      | Widget linking         |
| 12421 | `_reset_exploring_button_states`              | Button reset           |
| 12736 | `get_exploring_cache_stats`                   | Cache stats            |
| 12752 | `invalidate_exploring_cache`                  | Cache invalidation     |
| 4660  | `_setup_expression_widget_direct_connections` | Expression connections |
| 4691  | `_schedule_expression_change`                 | Schedule change        |
| 4714  | `_execute_debounced_expression_change`        | Debounced execution    |
| 4747  | `_execute_expression_params_change`           | Params change          |
| 4803  | `_set_expression_loading_state`               | Loading state          |
| 4837  | `_get_cached_expression_result`               | Cache get              |
| 4873  | `_set_cached_expression_result`               | Cache set              |
| 4897  | `invalidate_expression_cache`                 | Cache invalidation     |

**New Architecture Equivalent**: `ui/controllers/exploring_controller.py` + `core/services/expression_service.py`

**Migration Status**: 🔴 Minimal (~15% extracted)

---

### 5. Exporting Logic Methods (10 methods, ~400 lines)

| Line  | Method                         | Responsibility      |
| ----- | ------------------------------ | ------------------- |
| 6023  | `exporting_populate_combobox`  | ComboBox population |
| 9570  | `get_layers_to_export`         | Get export layers   |
| 9583  | `get_current_crs_authid`       | CRS getter          |
| 11349 | `set_exporting_properties`     | Properties setter   |
| 11771 | `dialog_export_output_path`    | Output path dialog  |
| 11821 | `reset_export_output_path`     | Path reset          |
| 11831 | `dialog_export_output_pathzip` | Zip path dialog     |
| 11855 | `reset_export_output_pathzip`  | Zip reset           |
| 12898 | `_update_export_buttons_state` | Button state        |
| 5804  | `manage_output_name`           | Output name         |

**New Architecture Equivalent**: `ui/controllers/exporting_controller.py`

**Migration Status**: 🔴 Not extracted (~5%)

---

### 6. Config/Settings Methods (24 methods, ~1,200 lines)

| Line  | Method                               | Responsibility        |
| ----- | ------------------------------------ | --------------------- |
| 5102  | `dockwidget_widgets_configuration`   | Widget config         |
| 5266  | `data_changed_configuration_model`   | Model change          |
| 5564  | `apply_pending_config_changes`       | Apply changes         |
| 5609  | `cancel_pending_config_changes`      | Cancel changes        |
| 5659  | `on_config_buttonbox_accepted`       | Accept handler        |
| 5665  | `on_config_buttonbox_rejected`       | Reject handler        |
| 5671  | `reload_configuration_model`         | Reload model          |
| 5694  | `save_configuration_model`           | Save model            |
| 5706  | `manage_configuration_model`         | Manage model          |
| 5778  | `_on_reload_button_clicked`          | Reload click          |
| 3559  | `_toggle_optimization_enabled`       | Optimization toggle   |
| 3571  | `_toggle_centroid_auto`              | Centroid toggle       |
| 3583  | `_toggle_optimization_ask_before`    | Ask before toggle     |
| 3595  | `_analyze_layer_optimizations`       | Analyze optimizations |
| 3711  | `_show_optimization_settings_dialog` | Settings dialog       |
| 3777  | `_show_backend_optimization_dialog`  | Backend dialog        |
| 3834  | `get_backend_optimization_setting`   | Get setting           |
| 3859  | `_is_centroid_already_enabled`       | Centroid check        |
| 3893  | `should_use_centroid_for_layer`      | Should use centroid   |
| 3953  | `get_optimization_state`             | Get state             |
| 3968  | `restore_optimization_state`         | Restore state         |
| 3983  | `auto_select_optimal_backends`       | Auto select           |
| 12917 | `_update_expression_tooltip`         | Expression tooltip    |
| 12936 | `_update_feature_picker_tooltip`     | Picker tooltip        |

**New Architecture Equivalent**: `ui/controllers/config_controller.py` + `ui/config/`

**Migration Status**: 🟡 Partial (~35% extracted)

---

### 7. Layer Sync Methods (22 methods, ~1,800 lines)

| Line  | Method                            | Responsibility       |
| ----- | --------------------------------- | -------------------- |
| 9589  | `_validate_and_prepare_layer`     | Layer validation     |
| 9680  | `_reset_layer_expressions`        | Expression reset     |
| 9748  | `_disconnect_layer_signals`       | Signal disconnect    |
| 9804  | `_detect_multi_step_filter`       | Multi-step detection |
| 9872  | `_synchronize_layer_widgets`      | Widget sync          |
| 10047 | `_reload_exploration_widgets`     | Widget reload        |
| 10281 | `_restore_groupbox_ui_state`      | UI state restore     |
| 10372 | `_reconnect_layer_signals`        | Signal reconnect     |
| 10483 | `_ensure_valid_current_layer`     | Layer validation     |
| 10543 | `_is_layer_truly_deleted`         | Deletion check       |
| 10607 | `current_layer_changed`           | Layer change handler |
| 11884 | `_update_project_layers_data`     | Layers update        |
| 11908 | `_determine_active_layer`         | Active layer         |
| 11962 | `_activate_layer_ui`              | UI activation        |
| 12018 | `_refresh_layer_specific_widgets` | Widget refresh       |
| 12059 | `get_project_layers_from_app`     | Get layers           |
| 12252 | `setLayerVariableEvent`           | Set variable         |
| 12285 | `resetLayerVariableOnErrorEvent`  | Reset on error       |
| 12315 | `resetLayerVariableEvent`         | Reset variable       |
| 12496 | `setProjectVariablesEvent`        | Project variables    |
| 12679 | `getProjectLayersEvent`           | Get layers event     |
| 12956 | `retranslate_dynamic_tooltips`    | Tooltip translation  |

**New Architecture Equivalent**: `ui/controllers/layer_sync_controller.py` + `core/services/layer_service.py`

**Migration Status**: 🟡 Partial (~30% extracted)

---

### 8. Signal/Slot Connection Methods (12 methods, ~600 lines)

| Line | Method                                | Responsibility         |
| ---- | ------------------------------------- | ---------------------- |
| 424  | `getSignal`                           | Signal getter          |
| 462  | `manageSignal`                        | Signal management      |
| 534  | `changeSignalState`                   | State change           |
| 6527 | `set_widgets_enabled_state`           | Enable state           |
| 6573 | `connect_widgets_signals`             | Connect signals        |
| 6597 | `disconnect_widgets_signals`          | Disconnect signals     |
| 6626 | `force_reconnect_action_signals`      | Reconnect action       |
| 6694 | `force_reconnect_exploring_signals`   | Reconnect exploring    |
| 6786 | `manage_interactions`                 | Interaction management |
| 6855 | `select_tabTools_index`               | Tab selection          |
| 6898 | `_connect_groupbox_signals_directly`  | Groupbox signals       |
| 6949 | `_force_exploring_groupbox_exclusive` | Exclusive groupbox     |

**New Architecture Equivalent**: `ui/controllers/base_controller.py` + `ui/controllers/mixins/`

**Migration Status**: 🔴 Not extracted (~10%)

---

### 9. Property Management Methods (16 methods, ~1,000 lines)

| Line  | Method                                     | Responsibility          |
| ----- | ------------------------------------------ | ----------------------- |
| 10842 | `project_property_changed`                 | Project property change |
| 10925 | `_parse_property_data`                     | Data parsing            |
| 10950 | `_find_property_path`                      | Path finding            |
| 10967 | `_update_is_property`                      | Is property update      |
| 11009 | `_update_selection_expression_property`    | Selection update        |
| 11034 | `_update_other_property`                   | Other update            |
| 11136 | `layer_property_changed`                   | Layer property change   |
| 11196 | `layer_property_changed_with_buffer_style` | Buffer style            |
| 11420 | `properties_group_state_enabler`           | State enabler           |
| 11450 | `properties_group_state_reset_to_default`  | Reset to default        |
| 7013  | `_on_groupbox_clicked`                     | Groupbox click          |
| 7091  | `_on_groupbox_collapse_changed`            | Collapse change         |
| 273   | `_safe_get_layer_props`                    | Safe getter             |
| 296   | `_initialize_layer_state`                  | State init              |
| 419   | `_deferred_manage_interactions`            | Deferred management     |
| 12778 | `launchTaskEvent`                          | Task launch             |

**New Architecture Equivalent**: `ui/controllers/property_controller.py`

**Migration Status**: 🟢 Mostly extracted (~60%)

---

### 10. Favorites Management Methods (16 methods, ~900 lines)

| Line | Method                           | Responsibility   |
| ---- | -------------------------------- | ---------------- |
| 1999 | `_on_favorite_indicator_clicked` | Indicator click  |
| 2136 | `_get_current_filter_expression` | Get expression   |
| 2180 | `_add_current_to_favorites`      | Add to favorites |
| 2296 | `_generate_favorite_description` | Description gen  |
| 2336 | `_apply_favorite`                | Apply favorite   |
| 2444 | `_show_favorites_manager_dialog` | Manager dialog   |
| 2510 | `populate_list` (nested)         | List population  |
| 2531 | `on_search_changed` (nested)     | Search change    |
| 2683 | `on_selection_changed` (nested)  | Selection change |
| 2726 | `on_apply` (nested)              | Apply action     |
| 2731 | `on_save` (nested)               | Save action      |
| 2760 | `on_delete` (nested)             | Delete action    |
| 2821 | `_export_favorites`              | Export           |
| 2838 | `_import_favorites`              | Import           |
| 2873 | `_update_favorite_indicator`     | Indicator update |

**New Architecture Equivalent**: `ui/controllers/favorites_controller.py` + `core/services/favorites_service.py`

**Migration Status**: 🟢 Mostly extracted (~65%)

---

### 11. Backend Selection Methods (20 methods, ~1,000 lines)

| Line  | Method                                 | Responsibility     |
| ----- | -------------------------------------- | ------------------ |
| 1736  | `_on_backend_indicator_clicked`        | Indicator click    |
| 1755  | `_on_backend_indicator_clicked_legacy` | Legacy click       |
| 2927  | `_get_available_backends_for_layer`    | Available backends |
| 2961  | `_detect_current_backend`              | Current detection  |
| 2984  | `_verify_backend_supports_layer`       | Verify support     |
| 3028  | `_set_forced_backend`                  | Set forced         |
| 3046  | `_force_backend_for_all_layers`        | Force all          |
| 3181  | `get_forced_backend_for_layer`         | Get forced         |
| 3195  | `_get_optimal_backend_for_layer`       | Get optimal        |
| 3276  | `_toggle_pg_auto_cleanup`              | PG cleanup toggle  |
| 3290  | `_cleanup_postgresql_session_views`    | Session cleanup    |
| 3366  | `_cleanup_postgresql_schema_if_empty`  | Schema cleanup     |
| 3470  | `_show_postgresql_session_info`        | Session info       |
| 12501 | `_update_backend_indicator`            | Indicator update   |
| 12532 | `_update_backend_indicator_legacy`     | Legacy update      |

**New Architecture Equivalent**: `ui/controllers/backend_controller.py` + `core/services/backend_service.py`

**Migration Status**: 🟢 Mostly extracted (~55%)

---

### 12. Undo/Redo Methods (2 methods, ~30 lines)

| Line  | Method              | Responsibility |
| ----- | ------------------- | -------------- |
| 13040 | `_on_undo_shortcut` | Undo shortcut  |
| 13053 | `_on_redo_shortcut` | Redo shortcut  |

**New Architecture Equivalent**: `core/services/history_service.py` + `adapters/undo_redo_handler.py`

**Migration Status**: 🟢 Extracted (~80%)

---

### 13. Utilities/Events Methods (33 methods, ~540 lines)

| Line  | Method                       | Responsibility  |
| ----- | ---------------------------- | --------------- |
| 204   | `__init__`                   | Constructor     |
| 12685 | `closeEvent`                 | Close event     |
| 12198 | `open_project_page`          | Open page       |
| 12205 | `reload_plugin`              | Reload plugin   |
| 13006 | `_on_reload_layers_shortcut` | Reload shortcut |
| 13016 | `_trigger_reload_layers`     | Trigger reload  |

**Migration Status**: 🔴 Core class methods, not extractable

---

## Migration Priority Recommendations

### Priority 1 - High Impact, Low Risk

1. **Exploring Logic** (~3,200 lines) - Largest category, complex but well-defined
2. **Filtering Logic** (~750 lines) - Core functionality, needs controller
3. **Exporting Logic** (~400 lines) - Independent, easy to extract

### Priority 2 - Medium Impact

4. **Signal/Slot Methods** (~600 lines) - Foundation for other migrations
5. **Layer Sync Methods** (~1,800 lines) - Partially done, needs completion
6. **Config/Settings** (~1,200 lines) - Partially done

### Priority 3 - Already Advanced

7. **Style/Theme** - 70% done, cleanup remaining
8. **Layout/UI Setup** - 40% done, continue extraction
9. **Property Management** - 60% done
10. **Favorites** - 65% done
11. **Backend** - 55% done

---

## New Architecture Coverage Summary

| New Module                           | Coverage | Status        |
| ------------------------------------ | -------- | ------------- |
| `ui/layout/SplitterManager`          | ~80%     | ✅ Good       |
| `ui/layout/DimensionsManager`        | ~60%     | 🟡 Partial    |
| `ui/layout/SpacingManager`           | ~70%     | 🟡 Partial    |
| `ui/layout/ActionBarManager`         | ~75%     | 🟡 Partial    |
| `ui/styles/ThemeManager`             | ~90%     | ✅ Good       |
| `ui/styles/IconManager`              | ~85%     | ✅ Good       |
| `ui/styles/ButtonStyler`             | ~70%     | 🟡 Partial    |
| `ui/controllers/BackendController`   | ~55%     | 🟡 Partial    |
| `ui/controllers/ConfigController`    | ~35%     | 🔴 Needs work |
| `ui/controllers/ExploringController` | ~15%     | 🔴 Needs work |
| `ui/controllers/ExportingController` | ~5%      | 🔴 Needs work |
| `ui/controllers/FavoritesController` | ~65%     | 🟡 Partial    |
| `ui/controllers/FilteringController` | ~20%     | 🔴 Needs work |
| `ui/controllers/LayerSyncController` | ~30%     | 🔴 Needs work |
| `ui/controllers/PropertyController`  | ~60%     | 🟡 Partial    |
| `core/services/BackendService`       | ~80%     | ✅ Good       |
| `core/services/ExpressionService`    | ~50%     | 🟡 Partial    |
| `core/services/FavoritesService`     | ~80%     | ✅ Good       |
| `core/services/FilterService`        | ~60%     | 🟡 Partial    |
| `core/services/HistoryService`       | ~85%     | ✅ Good       |
| `core/services/LayerService`         | ~50%     | 🟡 Partial    |

---

## Estimated Effort for Complete Migration

| Phase                          | Methods to Extract | Estimated Lines | Complexity |
| ------------------------------ | ------------------ | --------------- | ---------- |
| Complete Layout Extraction     | 15                 | ~600            | Medium     |
| Complete Controller Extraction | 80                 | ~4,500          | High       |
| Complete Service Extraction    | 25                 | ~1,200          | Medium     |
| Refactor Remaining Core        | 50                 | ~2,500          | Low        |
| **Total**                      | **170**            | **~8,800**      | -          |

After full migration, `filter_mate_dockwidget.py` should contain only:

- Constructor (~100 lines)
- Event handlers (~200 lines)
- Delegation methods (~300 lines)
- **Target size: ~600-800 lines** (vs current 13,067)

---

## Recommendations

1. **Create `ExploringController`** - Extract the 38 exploring methods (3,200 lines)
2. **Create `FilteringController`** - Extract the 18 filtering methods (750 lines)
3. **Complete `LayerSyncController`** - Finish extracting layer synchronization
4. **Complete `ConfigController`** - Finish configuration management
5. **Consolidate signal management** - Create dedicated signal handler mixin
6. **Remove deprecated legacy methods** - Clean up `_legacy` suffixed methods
