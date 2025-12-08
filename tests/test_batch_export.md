# Test: Batch Export Functionality

## Description
Tests the batch export feature that allows exporting multiple layers individually.

## Test Cases

### 1. Batch Export to Folder
**Objective**: Export multiple layers as individual files to a folder

**Steps**:
1. Load a QGIS project with multiple vector layers
2. Open FilterMate plugin
3. Go to EXPORTING tab
4. Select multiple layers in "Layers to export"
5. Check "Mode batch" checkbox next to "Output folder" field
6. Select output format (e.g., Shapefile, GeoJSON)
7. Click the output folder button and select a destination folder
8. Run export

**Expected Result**:
- Each layer is exported as a separate file in the selected folder
- Files are named after their layer names
- Message shows: "Batch export: N layer(s) exported to [folder_path]"

**Success Criteria**:
- One file per layer
- All layers exported successfully
- No errors in QGIS log

---

### 2. Batch Export to ZIP
**Objective**: Export multiple layers as individual ZIP files

**Steps**:
1. Load a QGIS project with multiple vector layers
2. Open FilterMate plugin
3. Go to EXPORTING tab
4. Select multiple layers in "Layers to export"
5. Check "Mode batch" checkbox next to "ZIP file" field
6. Select output format (e.g., Shapefile, GeoJSON)
7. Click the ZIP button and select a destination folder
8. Run export

**Expected Result**:
- Each layer is exported to its own ZIP archive
- ZIP files are named: [layer_name].zip
- Message shows: "Batch ZIP export: N ZIP file(s) created in [folder_path]"

**Success Criteria**:
- One ZIP file per layer
- Each ZIP contains the layer data in the selected format
- All layers exported successfully
- No errors in QGIS log

---

### 3. Standard Export (Non-Batch)
**Objective**: Ensure standard export still works when batch mode is OFF

**Steps**:
1. Load a QGIS project with multiple vector layers
2. Open FilterMate plugin
3. Go to EXPORTING tab
4. Select multiple layers in "Layers to export"
5. Ensure both "Mode batch" checkboxes are UNCHECKED
6. Select output format
7. Select output folder/file
8. Run export

**Expected Result**:
- Layers exported using standard behavior (GPKG or directory)
- Standard export message displayed

**Success Criteria**:
- Standard export works as before
- No batch-related messages

---

## Code Changes Summary

### Files Modified:

1. **modules/appTasks.py**
   - Added `_export_batch_to_folder()`: Exports one file per layer to directory
   - Added `_export_batch_to_zip()`: Exports one ZIP per layer
   - Modified `execute_exporting()`: Detects batch mode and routes to appropriate method
   - Modified `_validate_export_parameters()`: Extracts batch flags from config

2. **filter_mate_dockwidget.py**
   - Added `BATCH_OUTPUT_FOLDER` and `BATCH_ZIP` to widgets dictionary
   - Added batch flags to JSON template
   - Added CheckBox support in `set_exporting_properties()`
   - Added CheckBox support in `properties_group_state_reset_to_default()`

### Key Behavior:

- **Batch Output Folder Mode** (checkBox_batch_exporting_output_folder):
  - Creates one file per layer in selected directory
  - File naming: [layer_name].[extension]
  - Progress shown: "Batch export: layer N/M: [name]"

- **Batch ZIP Mode** (checkBox_batch_exporting_zip):
  - Creates one ZIP per layer in selected directory
  - ZIP naming: [layer_name].zip
  - Each ZIP contains the layer in selected format
  - Temporary directories used during export (cleaned up after)
  - Progress shown: "Batch ZIP export: layer N/M: [name]"

### Parameters Flow:

1. User checks `checkBox_batch_exporting_output_folder` or `checkBox_batch_exporting_zip`
2. CheckBox state stored in `project_props['EXPORTING']['BATCH_OUTPUT_FOLDER']` or `BATCH_ZIP`
3. FilterMateApp.get_task_parameters() passes entire `project_props['EXPORTING']` to task
4. FilterEngineTask._validate_export_parameters() extracts batch flags
5. FilterEngineTask.execute_exporting() routes to batch methods if flags are True

---

## Manual Testing Checklist

- [ ] Test batch folder export with 3+ layers
- [ ] Test batch ZIP export with 3+ layers
- [ ] Test with different formats (Shapefile, GeoJSON, GPKG)
- [ ] Test cancellation during batch export
- [ ] Test error handling (invalid paths, permissions)
- [ ] Verify temporary directories are cleaned up after batch ZIP
- [ ] Test mixed: batch mode ON with single layer selected
- [ ] Test standard export still works (batch OFF)
- [ ] Verify progress messages update correctly
- [ ] Check QGIS logs for errors/warnings

---

## Known Limitations

1. **GPKG Format**: Batch mode may not be ideal for GPKG since it's designed as a multi-layer container
2. **Large Datasets**: Batch export may take longer for many layers
3. **Temporary Disk Space**: Batch ZIP mode requires temporary disk space

---

## Future Enhancements

- [ ] Add option to include styles in batch exports
- [ ] Progress bar for overall batch progress
- [ ] Option to batch export with custom naming pattern
- [ ] Parallel batch export for faster processing
