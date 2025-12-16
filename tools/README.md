# FilterMate Development Tools

This directory contains utility scripts for development and maintenance tasks.
These scripts are not part of the plugin runtime and are used for build, translation, and diagnostic purposes.

## Directory Structure

```
tools/
├── cleanup_postgresql_virtual_id.py  # 🆕 Fix corrupted PostgreSQL layers
├── build/              # Build and release scripts
│   └── create_release_zip.py
├── diagnostic/         # Diagnostic and testing utilities
│   ├── diagnose_before_load.py
│   ├── diagnose_freeze.py
│   ├── test_color_picker.py
│   ├── test_load_simple.py
│   └── validate_config_helpers.py
├── i18n/              # Translation utilities
│   ├── add_ui_tooltips_translations.py
│   ├── compile_translations.bat
│   ├── compile_ts_to_qm.py
│   ├── open_qt_linguist.bat
│   ├── simple_qm_compiler.py
│   ├── update_translations.py
│   └── verify_translations.py
└── ui/                # UI modification utilities
    ├── fix_ui_suffixes.py
    ├── remove_ui_suffixes.py
    ├── update_ui_tooltips.py
    └── verify_ui_fix.py
```

## Maintenance Scripts

### cleanup_postgresql_virtual_id.py 🆕
**Purpose:** Fix corrupted PostgreSQL layers that were incorrectly configured with `virtual_id` as their primary key field.

**Problem:** 
- Older versions of FilterMate allowed PostgreSQL layers without unique fields to use virtual_id
- Virtual fields only exist in QGIS memory, not in the PostgreSQL database
- This causes "column virtual_id does not exist" errors when filtering

**Usage:**
```bash
# From command line
python cleanup_postgresql_virtual_id.py

# From QGIS Python console
exec(open('/path/to/cleanup_postgresql_virtual_id.py').read())
```

**What it does:**
1. Scans FilterMate's database for PostgreSQL layers with virtual_id
2. Creates a backup of the database
3. Removes corrupted layer properties
4. Shows which PostgreSQL tables need PRIMARY KEY constraints

**After running:**
- Restart QGIS
- Add PRIMARY KEY to your PostgreSQL tables
- Re-add the layers to FilterMate

See `docs/fixes/POSTGRESQL_VIRTUAL_ID_FIX_2025-12-16.md` for full details.

## Build Scripts

### create_release_zip.py
Creates a distributable ZIP archive of the plugin for QGIS Plugin Manager.

```bash
cd tools/build
python create_release_zip.py
```

## Translation Scripts

### compile_ts_to_qm.py / simple_qm_compiler.py
Compile Qt `.ts` translation files to binary `.qm` format.

```bash
cd tools/i18n
python compile_ts_to_qm.py
```

### update_translations.py
Add new translation strings to all `FilterMate_*.ts` files.

### verify_translations.py
Verify all translations are correctly configured.

### add_ui_tooltips_translations.py
Add missing tooltip translations to translation files.

### Windows Batch Files
- `compile_translations.bat`: Compile all translations
- `open_qt_linguist.bat`: Open Qt Linguist for translation editing

## UI Utilities

### fix_ui_suffixes.py / remove_ui_suffixes.py
Fix widget naming issues in the `.ui` file when Qt Designer adds unwanted suffixes.

### update_ui_tooltips.py
Update tooltip text in the `.ui` file (e.g., translate from French to English).

### verify_ui_fix.py
Verify all expected widgets are present in the generated `.py` file.

## Diagnostic Tools

### diagnose_before_load.py
Run in QGIS Python console BEFORE loading the plugin to check the environment.

### diagnose_freeze.py
Debug script to identify where FilterMate freezes during initialization.

### test_load_simple.py
Simple module loading test without QGIS dependency.

### test_color_picker.py
Test script for ColorType in Qt JSON View.

### validate_config_helpers.py
Quick validation script for config harmonization.

## Usage Notes

1. **Always run from the tools subdirectory** or adjust paths accordingly
2. **Windows users**: Use the `.bat` files for convenience
3. **Translation workflow**: 
   - Edit `.ts` files with Qt Linguist
   - Compile to `.qm` with compile scripts
   - Verify with verification scripts

## Adding New Tools

When adding new development tools:
1. Place them in the appropriate subdirectory
2. Update this README
3. Ensure they work from both the tools directory and plugin root
4. Add appropriate error handling for missing dependencies
