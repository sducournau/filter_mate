---
sidebar_position: 8
---

# Filter Favorites

Save, organize, and quickly apply frequently-used filter configurations with FilterMate's built-in favorites system.

:::info Version 2.0+
The favorites system is available in FilterMate v2.0 and later, with SQLite persistence and export/import capabilities.
:::

## Overview

**Filter Favorites** allow you to save complex filter configurations—including expressions, spatial predicates, buffer settings, and multi-layer selections—for quick reuse across sessions.

### Key Features

- ⭐ **Save complex filters** with descriptive names and notes
- 📊 **Track usage statistics** (application count, last used)
- 💾 **SQLite persistence** - favorites saved to database
- 📤 **Export/Import** - share favorites via JSON files
- 🔍 **Search & organize** - find favorites by name or tags
- 🎯 **Multi-layer support** - save configurations affecting multiple layers

## Favorites Indicator

The **★ Favorites indicator** is located in the header bar at the top of the FilterMate panel, next to the backend indicator.

### Indicator States

| Display | Meaning | Tooltip |
|---------|---------|---------|
| **★** (gray) | No favorites saved | Click to add current filter |
| **★ 5** (gold) | 5 favorites saved | Click to apply or manage |

**Clicking the indicator** opens the favorites context menu.

---

## Adding Favorites

### Method 1: From Current Filter

1. **Configure your filter** in the FILTERING tab:
   - Set expression
   - Choose spatial predicates
   - Configure buffer distance
   - Select layers to filter

2. **Click the ★ indicator** in the header

3. **Select "⭐ Add Current Filter to Favorites"**

4. **Enter details** in the dialog:
   - **Name**: Short, descriptive name (e.g., "Large residential parcels")
   - **Description** (optional): Detailed notes about the filter
   - **Tags** (optional): Keywords for search (comma-separated)

5. **Click OK** to save

:::tip Naming Convention
Use clear, action-oriented names:
- ✅ "Buildings within 200m of metro"
- ✅ "High-value properties > 500k"
- ❌ "filter1", "test", "query"
:::

### What Gets Saved

A favorite captures:

- **Filter expression**: The QGIS expression text
- **Source layer**: Reference layer name and ID
- **Remote layers**: List of filtered layers (if multi-layer)
- **Spatial predicates**: Selected geometric relationships
- **Buffer settings**: Distance, unit, type
- **Combine operator**: AND/OR/AND NOT
- **Metadata**: Creation date, usage count, last used

---

## Applying Favorites

### From the ★ Menu

1. **Click the ★ indicator**

2. **Recent favorites** are shown (up to 10 most recent)

3. **Click a favorite** to apply it:
   - Expression restored
   - Layers selected
   - Spatial settings configured
   - Ready to apply with **Filter** button

4. **Click "Filter"** to execute the saved configuration

:::warning Layer Availability
If a saved layer no longer exists in the project, FilterMate will:
- Skip the missing layer with a warning message
- Apply the filter to available layers only
:::

### Favorite Display Format

```
★ Building proximity (3 layers)
  Used 12 times • Last: Dec 18
```

**Shows**:
- Name
- Number of layers involved
- Usage count
- Last used date

---

## Managing Favorites

### Favorites Manager Dialog

**Access**: Click ★ indicator → **"⚙️ Manage Favorites..."**

The manager provides:

#### Left Panel: Favorites List
- All saved favorites
- Shows name, layer count, usage stats
- Click to view details

#### Right Panel: Details & Editing

**Tab 1: General**
- **Name**: Edit favorite name
- **Expression**: View/edit filter expression
- **Description**: Add notes

**Tab 2: Layers**
- **Source Layer**: Reference layer info
- **Remote Layers**: List of filtered layers

**Tab 3: Settings**
- **Spatial Predicates**: Geometric relationships
- **Buffer**: Distance and type
- **Combine Operator**: AND/OR/AND NOT

**Tab 4: Usage Stats**
- Times used
- Created date
- Last used date

#### Actions

- **Save Changes**: Update the selected favorite
- **Delete**: Remove the favorite (with confirmation)
- **Apply**: Close dialog and apply favorite

---

## Export & Import

### Export Favorites

Share your favorite filters with colleagues or backup to file:

1. **Click ★ indicator** → **"📤 Export Favorites..."**

2. **Choose location** and filename (e.g., `filtermate_favorites.json`)

3. **All favorites exported** to JSON format

**Use Cases**:
- Share with team members
- Backup before plugin updates
- Transfer between projects

---

### Import Favorites

Load favorites from a JSON file:

1. **Click ★ indicator** → **"📥 Import Favorites..."**

2. **Select JSON file**

3. **Choose import mode**:
   - **Merge**: Add to existing favorites
   - **Replace**: Delete all and import new

4. **Favorites loaded** and ready to use

:::tip Team Workflows
Establish a team favorites library:
1. Expert user creates optimized filters
2. Exports to shared drive/repository
3. Team members import standardized filters
4. Ensures consistency across analyses
:::

---

## Search & Filter

### Finding Favorites

**In Favorites Manager**:
- Type in search box to filter by:
  - Name
  - Expression text
  - Tags
  - Description

**Case-insensitive** and matches partial text.

---

## Advanced Features

### Usage Statistics

FilterMate tracks:
- **Application count**: How many times you've used this favorite
- **Last used**: Timestamp of most recent use
- **Created**: When the favorite was first saved

**Benefit**: Identify your most valuable filters and optimize workflows.

---

### Multi-Layer Favorites

When you save a favorite with **remote layers** (Layers to Filter enabled):

**Saved**:
- Source layer configuration
- All remote layer IDs
- Geometric predicates
- Buffer settings

**On Apply**:
- All saved layers re-selected (if available)
- Spatial relationships restored
- Ready for multi-layer filtering

**Example**: "Urban parcels near transit"
- Source: metro_stations
- Remote layers: parcels, buildings, roads
- Predicate: intersects
- Buffer: 500m

---

## Favorites Persistence

### Storage Location

Favorites are saved in:
```
<QGIS profile>/python/plugins/filter_mate/config/filterMate_db.sqlite
```

**Table**: `fm_favorites`

**Per-Project**: Favorites are organized by project UUID, so different QGIS projects can have separate favorite collections.

---

### Backup Strategy

Favorites are automatically backed up when:
- Plugin configuration is saved
- Project is closed
- FilterMate is unloaded

**Manual Backup**: Use **Export Favorites** to create JSON backups.

---

## Best Practices

### Naming Favorites

✅ **Good Names**:
- "Properties > 500k near schools"
- "Industrial zones 1km from water"
- "High-traffic roads (AADT > 10k)"

❌ **Avoid**:
- "Test", "Query1", "Temp"
- Single words without context
- Overly technical jargon

---

### Organizing with Tags

Use **tags** to categorize:
- By purpose: `analysis`, `export`, `reporting`
- By geography: `downtown`, `suburbs`, `region-north`
- By data type: `parcels`, `roads`, `buildings`

**Example**:
```
Name: Large residential parcels
Tags: parcels, residential, analysis, urban-planning
```

---

### Maintenance

**Regularly**:
- ✅ Delete unused favorites
- ✅ Update descriptions as workflows evolve
- ✅ Export backups before major changes
- ✅ Review and consolidate similar favorites

**Keep favorites count**: ~20-50 active favorites is optimal (avoid clutter).

---

## Troubleshooting

### Favorite Doesn't Apply Correctly

**Symptoms**: Filter applies but results differ from expected.

**Causes & Solutions**:

1. **Layer renamed or moved**
   - Solution: Edit favorite, update layer references

2. **CRS changed**
   - Solution: Re-save favorite with current CRS

3. **Data structure changed** (new fields, etc.)
   - Solution: Edit expression to match current schema

---

### Favorites Not Persisting

**Symptom**: Favorites disappear after restart.

**Solutions**:

1. **Check database file**:
   ```bash
   # Verify exists:
   ls <profile>/python/plugins/filter_mate/config/filterMate_db.sqlite
   ```

2. **File permissions**: Ensure write access to config directory

3. **Export backup**: Use JSON export as fallback storage

---

### Import Fails

**Error**: "No favorites imported"

**Causes**:
- Invalid JSON format
- File corrupted
- Incompatible version

**Solution**: 
- Verify JSON structure
- Try re-exporting from source
- Check FilterMate versions match (v2.0+)

---

## Example Workflows

### Workflow 1: Standardized Team Filters

**Scenario**: 5-person GIS team needs consistent filtering

**Setup**:
1. Team lead creates 10 core favorites
2. Exports to `team_filters.json`
3. Shares via repository/drive
4. Team members import on first use

**Result**: Everyone uses identical filter logic

---

### Workflow 2: Progressive Analysis

**Task**: Multi-step urban analysis

**Favorites**:
1. "Step 1: Residential parcels"
2. "Step 2: Near transit (500m)"
3. "Step 3: High-value (>300k)"
4. "Step 4: Final selection"

**Process**: Apply each favorite in sequence, export results at each stage.

---

### Workflow 3: Quality Assurance

**Use Case**: Validate data imports

**Favorites**:
- "QA: Missing attributes"
- "QA: Invalid geometries"
- "QA: Duplicate records"
- "QA: Out of bounds"

**Process**: Apply each QA filter, review flagged features, fix issues.

---

## API Reference

### FilterFavorite Class

Location: `modules/filter_favorites.py`

**Properties**:
- `id`: Unique UUID
- `name`: Display name
- `expression`: Filter expression
- `description`: Optional notes
- `tags`: List of keywords
- `source_layer_id`: Reference layer
- `remote_layers`: List of filtered layers
- `created_at`: Timestamp
- `last_used`: Timestamp
- `use_count`: Application counter

**Methods**:
- `mark_used()`: Increment usage counter
- `to_dict()`: Serialize to JSON
- `from_dict()`: Deserialize from JSON

---

### FavoritesManager Class

Location: `modules/filter_favorites.py`

**Methods**:
- `add_favorite(fav)`: Add to collection
- `remove_favorite(id)`: Delete by ID
- `get_favorite(id)`: Retrieve by ID
- `get_all_favorites()`: List all (sorted by name)
- `get_recent_favorites(limit)`: Most recently used
- `search_favorites(query)`: Search by keyword
- `export_to_file(path)`: Save to JSON
- `import_from_file(path)`: Load from JSON

---

## Related Documentation

- **[Filter History](./filter-history)** - Undo/redo system
- **[Filtering Basics](./filtering-basics)** - Creating filters
- **[Interface Overview](./interface-overview)** - UI components
- **[Why FilterMate?](../getting-started/why-filtermate)** - Feature comparison

---

## Summary

Filter Favorites in FilterMate provide:

✅ **Save complex configurations** for reuse  
✅ **Organize workflows** with names, descriptions, tags  
✅ **Track usage** to identify valuable filters  
✅ **Share with team** via JSON export/import  
✅ **Persist across sessions** with SQLite storage  

**Next Steps**:
1. Create your first favorite from a useful filter
2. Add descriptive name and tags
3. Apply it in different projects
4. Export for team sharing
