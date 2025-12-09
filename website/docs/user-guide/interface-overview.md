---
sidebar_position: 2
---

# Interface Overview

Quick guide to FilterMate's main interface components and workflows.

## Opening FilterMate

1. **Menu:** Vector → FilterMate
2. **Toolbar:** Click FilterMate icon 

    <img src="/filter_mate/icons/logo.png" alt="FilterMate plugin icon" width="32"/>

3. **Keyboard:** Configure in QGIS settings

## Main Tabs

FilterMate organizes features into 3 main tabs:

### 🎯 FILTERING Tab

**Purpose:** Create filtered subsets of your data

**Key Components:**

  - **Reference Layer:**

    <img src="/filter_mate/icons/auto_layer_white.png" alt="Auto sync layer button" width="32"/>

    Choose a source layer for spatial filtering / Sync active layer with plugin

  - **Layer Selector:**

    <img src="/filter_mate/icons/layers.png" alt="Layer selector icon" width="32"/>

    Choose which layers to filter (multi-selection supported)

  - **Combination settings:**

    <img src="/filter_mate/icons/add_multi.png" alt="Combine operator icon" width="32"/>

    Combine multiple filters with AND/OR operators

  - **Spatial Predicates:**

    <img src="/filter_mate/icons/geo_predicates.png" alt="Spatial predicates icon" width="32"/>

    Select geometric relationships (Intersects, Contains, Within, etc.)

  - **Buffer Settings:**

    <img src="/filter_mate/icons/geo_tampon.png" alt="Buffer distance icon" width="32"/>

    Add proximity zones (distance, unit, type)

  - **Buffer Type Settings:**

    <img src="/filter_mate/icons/buffer_type.png" alt="Buffer type icon" width="32"/>

    Choose buffer geometry type (planar, geodesic, ellipsoidal)

**Use Cases:**
- Find features matching criteria (e.g., population > 100,000)
- Select geometries within/near other features
- Create temporary subsets for analysis

**See:** [Filtering Basics](./filtering-basics.md), [Geometric Filtering](./geometric-filtering.md), [Buffer Operations](./buffer-operations.md)

---

### 🔍 EXPLORING Tab

**Purpose:** Visualize and interact with features from the current active QGIS layer

**Key Components:**
- **Action Buttons:** 6 interactive buttons
  - **Identify:** 
  
    <img src="/filter_mate/icons/identify.png" alt="Identify button" width="32"/> 

    Highlight features on map


  - **Zoom:** 
  
    <img src="/filter_mate/icons/zoom.png" alt="Zoom button" width="32"/> 
  
    Center map on features
  - **Select:** 
    
    <img src="/filter_mate/icons/select_black.png" alt="Select button" width="32"/> 
  
    Enable interactive selection mode
  
  - **Track:** 
  
    <img src="/filter_mate/icons/track.png" alt="Track button" width="32"/> 
    
    Sync selections between widgets and map

  - **Link:** 
  
    <img src="/filter_mate/icons/link.png" alt="Link button" width="32"/> 
  
    Share configuration across widgets
  
  - **Reset parameters:** 
  
    <img src="/filter_mate/icons/auto_save.png" alt="Reset parameters button" width="32"/> 
  
    Restore layer defaults parameters

- **Selection Widgets:**
  - **Single Selection:** Pick one feature (dropdown)
  - **Multiple Selection:** Select many features (checkboxes)
  - **Custom Selection:** Use expressions to filter widget

**Important:** EXPLORING always works on QGIS's **current active layer** only. To change layer, update it in QGIS Layer Panel.

**Use Cases:**
- Browse features interactively
- Identify and zoom to specific features
- View attribute details
- Manual feature selection

:::tip EXPLORING vs FILTERING
- **EXPLORING:** Temporary visualization of current layer (no data modification)
- **FILTERING:** Permanent filtered subsets on selected layers (can be multiple)
:::

---

### 📤 EXPORTING Tab


**Purpose:** Export layers (filtered or unfiltered) to various formats

**Key Components:**
- **Layer Selector:**

  <img src="/filter_mate/icons/layers.png" alt="layers" width="32"/>

  Choose layers to export

- **CRS Transformation:**

  <img src="/filter_mate/icons/projection_black.png" alt="projection_black" width="32"/>

  Reproject to different coordinate system

- **Style Export:**

  <img src="/filter_mate/icons/styles_white.png" alt="styles" width="32"/>
 
  Save QGIS styles (QML, SLD, ArcGIS)

- **Format:** 

  <img src="/filter_mate/icons/datatype.png" alt="datatype" width="32"/>

  GPKG, Shapefile, GeoJSON, KML, CSV, PostGIS, Spatialite

- **Batch Mode:** Export each layer to separate file
- **Output Folder:**

  <img src="/filter_mate/icons/folder.png" alt="folder" width="32"/>

  Select destination directory
- **ZIP Compression:**

  <img src="/filter_mate/icons/zip.png" alt="zip" width="32"/>

  Package outputs for delivery

**Use Cases:**
- Share filtered data with colleagues
- Archive analysis snapshots
- Convert between formats
- Prepare data for web mapping

**See:** [Export Features](./export-features.md)

---

### ⚙️ CONFIGURATION Tab

**Purpose:** Customize FilterMate behavior and appearance

**Key Components:**
- **JSON Tree View:** Edit full configuration
- **Theme Selector:** Choose UI theme (default/dark/light/auto)
- **Advanced Options:** Plugin settings

**See:** [Configuration](../advanced/configuration.md)

---

## Action Buttons (Top Bar)

Always visible regardless of active tab:

| Button | Icon | Action | Shortcut |
|--------|------|--------|----------|
| **FILTER** | <img src="/filter_mate/icons/filter.png" alt="Filter" width="32"/> | Apply configured filters | F5 |
| **UNDO** | <img src="/filter_mate/icons/undo.png" alt="Undo" width="32"/> | Revert last filter | Ctrl+Z |
| **REDO** | <img src="/filter_mate/icons/redo.png" alt="Redo" width="32"/> | Reapply undone filter | Ctrl+Y |
| **RESET** | <img src="/filter_mate/icons/reset.png" alt="Reset" width="32"/> | Clear all filters | Ctrl+Shift+C |
| **EXPORT** | <img src="/filter_mate/icons/export.png" alt="Export" width="32"/> | Quick export | Ctrl+E |
| **ABOUT** | <img src="/filter_mate/icons/icon.png" alt="Icon" width="32"/> | Plugin information | - |

---

## Backend Indicators

Visual badges show data source type:

- **PostgreSQL ⚡:** Best performance (more than 50k features)
- **Spatialite 📦:** Good performance (less than 50k features)
- **OGR/Shapefile 📄:** Basic compatibility

Backend detected automatically based on layer type.

---

## Quick Keyboard Shortcuts

- **Ctrl+F:** Focus expression builder
- **F5:** Execute filter
- **Ctrl+Z / Ctrl+Y:** Undo / Redo
- **Tab:** Navigate between fields
- **Ctrl+Tab:** Switch between tabs

---

## Learn More

- **Getting Started:** [Quick Start Guide](../getting-started/quick-start.md)
- **Detailed Usage:** [Filtering Basics](./filtering-basics.md), [Geometric Filtering](./geometric-filtering.md)
- **Export Options:** [Export Features](./export-features.md)
- **Advanced:** [Configuration](../advanced/configuration.md), [Performance Tuning](../advanced/performance-tuning.md)

## Interface Layout

```mermaid
graph TB
    subgraph "FilterMate Panel"
        LS[Layer Selector - Multi-selection]
        AB["Action Buttons: Filter / Undo / Redo / Reset / Export / About"]
        TB[Tab Bar]
        
        subgraph "FILTERING Tab"
            LSF[Layer Selection + Auto Current]
            EXP[Expression Builder - Attribute Filtering]
            PRED[Spatial Predicates - Multi-selection]
            REF[Reference Layer + Combine Operator]
            BUF[Buffer Settings: Distance + Unit + Type]
            IND[Status Indicators]
        end
        
        subgraph "EXPLORING Tab"
            BTN[Push Buttons: Identify | Zoom | Select | Track | Link | Reset]
            SS[Single Selection - Feature Picker]
            MS[Multiple Selection - List Widget]
            CS[Custom Selection - Expression]
            FE[Field Expression Widget]
            TBL[Feature Attribute Table]
        end
        
        subgraph "EXPORTING Tab"
            LYR[Layers to Export - Multi-selection]
            FMT[Format Selector: GPKG | SHP | GeoJSON | etc.]
            CRS[CRS Transformation]
            STY[Style Export: QML | SLD | ArcGIS]
            OUT[Output Folder + Batch Mode]
            ZIP[ZIP Compression]
        end
        
        subgraph "CONFIGURATION Tab"
            JSON[JSON Tree View - Full Config]
            THEMES[Theme Selector + Preview]
            OPTS[Advanced Options]
        end
    end
    
    LS --> AB
    AB --> TB
    TB --> LSF
    TB --> BTN
    TB --> LYR
    TB --> JSON
```

## Layer Selector

### Features

- 📋 **Multi-selection:** Filter multiple layers at once
- 🔍 **Search:** Quick layer filtering
- 🎨 **Icons:** Geometry type indicators
  - 🔵 Point layers
  - 🟢 Line layers
  - 🟪 Polygon layers

### Usage

```
☑ Layer 1 (Polygon) — PostgreSQL ⚡
☑ Layer 2 (Point) — Spatialite
☐ Layer 3 (Line) — Shapefile
```

**Backend Indicators:**
- ⚡ PostgreSQL (high performance)
- 📦 Spatialite (medium performance)
- 📄 OGR (universal compatibility)

## Further Reading

For detailed guides on each feature:

- **[Filtering Basics](./filtering-basics.md)** - Complete guide to attribute filtering and QGIS expressions
- **[Geometric Filtering](./geometric-filtering.md)** - Spatial predicates, buffer operations, and geometric workflows
- **[Buffer Operations](./buffer-operations.md)** - Buffer configuration, types, and distance settings
- **[Export Features](./export-features.md)** - Export formats, CRS transformation, and batch operations
- **[Filter History](./filter-history.md)** - History management, undo/redo, and favorites

For getting started:

- **[Quick Start Guide](../getting-started/quick-start.md)** - 5-minute introduction
- **[Your First Filter](../getting-started/first-filter.md)** - Step-by-step tutorial

---

## Icon Usage Guidelines

### Accessibility
- All icons have been designed with high contrast ratios
- Theme-aware icons automatically adapt to light/dark modes
- Icons are sized appropriately for 16px, 24px, and 32px displays

### Consistency
- Each icon represents a specific, consistent action across the interface
- Workflow icons (selection_1-7, zoom_1-5, etc.) show process progression
- Light/dark variants maintain visual consistency across themes

### Context
- Icons appear in buttons, status indicators, and documentation
- Hover tooltips provide additional context for all interactive icons
- Sequential icons guide users through multi-step operations

---

## Interface Customization

You can customize the appearance of FilterMate icons and themes in the **CONFIGURATION** tab. See [Configuration Guide](../advanced/configuration.md) for details on:

- Switching between light/dark/auto themes
- Adjusting icon sizes (if supported by theme)
- Creating custom theme configurations

---
