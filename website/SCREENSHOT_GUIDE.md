# FilterMate Screenshots - Capture Guide & Specifications

**Phase 2 Visual Content** - Screenshot Capture & Annotation Guide

## Overview

This document provides detailed specifications for the 7 primary screenshots specified in `VISUAL_ASSETS_GUIDE.md`. Each specification includes:
- **Scene setup instructions**
- **Elements to highlight**
- **Annotation requirements**
- **Capture settings**
- **Post-processing steps**

## Capture Standards

### Technical Specifications

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Resolution (Full)** | 1920x1080 | Standard Full HD |
| **Resolution (Detail)** | 800x600 | UI component focus |
| **Format** | PNG | Lossless quality |
| **Color Depth** | 24-bit RGB | True color |
| **Compression** | Optimized PNG | Balance quality/size |
| **File Size** | <500 KB | Web performance |

### Capture Tools

**Recommended**: Built-in screenshot tools
- **Windows**: Win + Shift + S (Snipping Tool)
- **Linux**: Spectacle, Flameshot
- **macOS**: Cmd + Shift + 4

**Annotation Tools**:
- **Figma** (recommended) - https://figma.com - Professional annotations
- **Inkscape** - https://inkscape.org - Open-source vector editor
- **GIMP** - https://gimp.org - Raster image editor
- **Ksnip** - https://github.com/ksnip/ksnip - Screenshot + annotation

### Annotation Standards

**Text**:
- Font: Inter or Roboto (sans-serif)
- Size: 14-18px for labels, 12-14px for descriptions
- Color: White text with black outline (for visibility)
- Background: Semi-transparent dark box for longer text

**Shapes**:
- Arrows: 3px thick, yellow or red for attention
- Circles: 2px stroke, red or yellow
- Rectangles: 2px stroke, rounded corners (4px)
- Colors: Red (#FF3B30), Yellow (#FFCC00), Blue (#007AFF)

**Numbering**:
- Circular badges with numbers (1, 2, 3...)
- Size: 24x24px
- Background: Primary color (#007AFF)
- Text: White, bold

---

## Screenshot 1: Interface Full Overview (interface-full.png)

**Purpose**: Show complete FilterMate interface in context  
**Resolution**: 1920x1080  
**File Size Target**: <400 KB

### Scene Setup

**QGIS Configuration**:
- Window maximized at 1920x1080
- Standard layout: map canvas center, panels around
- Clean workspace (no floating dialogs)

**Layers**:
- `buildings` layer loaded (Paris 10th)
- `roads` layer loaded
- `metro_stations` layer loaded
- Layers panel visible on left
- All layers styled and visible

**FilterMate State**:
- Dockwidget open on right side (default position)
- Filtering tab active (first tab)
- Example filter applied: `"area_m2" > 500`
- Feature count visible: "892 features"
- Map showing filtered results

**Other Panels**:
- Layers panel (left): Standard size
- Processing Toolbox: Hidden
- Browser panel: Hidden
- Toolbar: Main toolbar visible at top

### Capture Instructions

1. **Position QGIS window**:
   - Maximize to 1920x1080
   - Center on screen

2. **Arrange elements**:
   - FilterMate dockwidget: right side, 400px width
   - Layers panel: left side, 250px width
   - Map canvas: center, showing Paris 10th area

3. **Zoom level**:
   - Show ~200 buildings on screen
   - Readable street names
   - Clear filter effect visible

4. **Capture**:
   - Use native screenshot tool
   - Capture entire QGIS window
   - Save as PNG

### Annotations to Add

Use Figma or Inkscape to add:

1. **Numbered Callouts** (blue circles with white numbers):
   - ① Layers Panel (arrow pointing to layers)
   - ② Map Canvas (arrow pointing to center)
   - ③ FilterMate Dockwidget (arrow pointing to dockwidget)
   - ④ Filtered Results (arrow pointing to features on map)

2. **Text Labels**:
   - Top overlay: "FilterMate Interface Overview"
   - Bottom right: "Filtering 3,199 buildings → 892 results"

3. **Highlight Boxes**:
   - Red rectangle around FilterMate dockwidget (2px stroke)
   - Yellow circle around feature count

4. **Legend** (bottom left corner):
   - Small box explaining numbered callouts
   ```
   ① Layers Panel - Manage your data
   ② Map Canvas - Visualize results
   ③ FilterMate - Apply filters
   ④ Results - Filtered features
   ```

### Post-Processing

1. **Crop** if needed (remove taskbar, extra space)
2. **Add annotations** in Figma:
   - Import PNG
   - Add numbered badges (24x24px circles)
   - Add arrows (3px stroke)
   - Add text labels
   - Export as PNG

3. **Optimize**:
   - Use TinyPNG or similar
   - Target: <400 KB
   - Maintain clarity

### Expected Output

```
interface-full.png
Size: 350-400 KB
Dimensions: 1920x1080
Purpose: Documentation homepage, intro.md
Annotations: 4 numbered callouts + 2 text labels
```

---

## Screenshot 2: Filtering Tab Detail (tab-filtering.png)

**Purpose**: Detailed view of Filtering tab UI  
**Resolution**: 800x600  
**File Size Target**: <300 KB

### Scene Setup

**Focus Area**: FilterMate dockwidget only (cropped)

**FilterMate State**:
- Filtering tab active
- Expression field: `"population" > 10000 AND "area_m2" > 500`
- Expression Builder button (fx) visible
- Apply button (green) prominent
- Undo/Redo buttons visible and enabled
- Feature count: "245 features" displayed
- Layer selector: "buildings" selected

**UI Elements Visible**:
- Tab bar (Filtering, Buffer, Export, Settings)
- Layer dropdown
- Expression text field (multi-line)
- Expression Builder button
- Apply/Clear buttons
- Undo/Redo buttons
- Feature count badge
- Status indicator (green = filter active)

### Capture Instructions

1. **Zoom QGIS window** so FilterMate dockwidget fills most of screen
2. **Capture only dockwidget** (crop to 800x600)
3. **Ensure all UI elements** clearly visible
4. **Use light theme** (better contrast)

### Annotations to Add

1. **Element Labels** (with arrows):
   - "Layer Selector" → dropdown
   - "Expression Field" → text area
   - "Expression Builder (fx)" → fx button
   - "Apply Filter" → green button
   - "Undo/Redo" → circular arrows
   - "Feature Count" → badge showing count

2. **Interaction Hints**:
   - Green checkmark next to Apply button: "Active Filter"
   - Tooltip-style bubble: "Type QGIS expression or use Builder"

3. **Color Coding**:
   - Green outline around Apply button (action)
   - Blue outline around expression field (input)

### Post-Processing

1. **Crop to 800x600** (centered on dockwidget)
2. **Add semi-transparent overlay** at bottom:
   - Dark box (opacity 80%)
   - Text: "Filtering Tab - Your command center for data filtering"
3. **Add arrows and labels** with Figma
4. **Optimize** to <300 KB

### Expected Output

```
tab-filtering.png
Size: 250-300 KB
Dimensions: 800x600
Purpose: User guide, filtering-basics.md
Annotations: 6 element labels + 2 hints
```

---

## Screenshot 3: Buffer Operations Tab (tab-buffer.png)

**Purpose**: Showcase buffer operations interface  
**Resolution**: 800x600  
**File Size Target**: <300 KB

### Scene Setup

**FilterMate State**:
- Buffer Operations tab active
- Source layer: "metro_stations" (12 features)
- Distance slider: 300 meters
- Unit dropdown: "meters"
- Buffer style: "Outline"
- Preview checkbox: checked (ON)
- Preview visible on map (semi-transparent circles)

**Map View** (background):
- Metro stations visible as points
- 300m buffers shown as semi-transparent orange circles
- Zoom level: Show 3-4 metro stations with buffers

### Capture Instructions

1. **Arrange view**: Half dockwidget, half map
2. **Show preview mode**: Buffers visible on map
3. **Capture 800x600**: Balanced composition
4. **Ensure slider** clearly shows 300m position

### Annotations to Add

1. **UI Element Labels**:
   - "Distance Slider" → slider control
   - "Preview Mode" → checkbox
   - "Buffer Style" → dropdown
   - "Apply Buffer" → button

2. **Connection Arrows**:
   - Arrow from slider to buffers on map: "Real-time preview"
   - Arrow from station to buffer: "300m radius"

3. **Distance Badge**:
   - Floating badge on map: "300m" next to a buffer

4. **Action Indicator**:
   - "Drag to adjust" hint near slider
   - Preview badge (orange): "Preview Mode"

### Post-Processing

1. **Composite**: Overlay dockwidget and map view
2. **Add connection arrows** between UI and map
3. **Add distance indicators** on map
4. **Optimize** to <300 KB

### Expected Output

```
tab-buffer.png
Size: 250-300 KB
Dimensions: 800x600
Purpose: User guide, buffer-operations.md
Annotations: 4 UI labels + 2 connection arrows + distance badge
```

---

## Screenshot 4: Export Tab (tab-export.png)

**Purpose**: Demonstrate export functionality  
**Resolution**: 800x600  
**File Size Target**: <300 KB

### Scene Setup

**FilterMate State**:
- Export tab active
- Format dropdown: "GeoPackage (.gpkg)" selected
- Output path: `C:/exports/filtered_buildings.gpkg`
- Options expanded:
  - "Export only selected features": unchecked
  - "Export with filter applied": checked
  - "Add to project": checked
- Export button: green, enabled
- Status: "Ready to export 892 features"

### Capture Instructions

1. **Focus on Export tab** (800x600)
2. **Show all export options** clearly
3. **Realistic output path** visible
4. **Feature count** prominent

### Annotations to Add

1. **Step Numbers** (workflow):
   - ① "Choose Format" → dropdown
   - ② "Select Path" → browse button
   - ③ "Configure Options" → checkboxes
   - ④ "Export" → export button

2. **Format Highlight**:
   - Checkmark next to GeoPackage: "Recommended"
   - Info icon: "Preserves CRS and attributes"

3. **Feature Count Badge**:
   - "892 features ready" with green checkmark

4. **Tooltips**:
   - Near options: "Configure export settings"
   - Near path field: "Click folder icon to browse"

### Post-Processing

1. **Add step numbers** (circular badges)
2. **Add checkmarks and icons**
3. **Highlight key elements** (format dropdown, export button)
4. **Optimize** to <300 KB

### Expected Output

```
tab-export.png
Size: 250-300 KB
Dimensions: 800x600
Purpose: User guide, export-results.md
Annotations: 4 step numbers + 2 tooltips + badges
```

---

## Screenshot 5: Settings Tab (tab-settings.png)

**Purpose**: Show configuration options  
**Resolution**: 800x600  
**File Size Target**: <300 KB

### Scene Setup

**FilterMate State**:
- Settings/Config tab active
- Sections visible:
  - **Backend Selection**:
    - Auto-detect: ON (toggle)
    - Current backend: "PostgreSQL ⚡"
    - Manual dropdown: grayed out
  - **Performance**:
    - Use spatial indexes: checked
    - Cache queries: checked
    - Max features preview: 1000
  - **UI Options**:
    - Show feature count: checked
    - Confirm before apply: unchecked
    - Theme: "Auto (follow QGIS)"

### Capture Instructions

1. **Capture full Settings tab** (800x600)
2. **All sections expanded** and visible
3. **Clear section headers**
4. **Toggle states** clearly shown

### Annotations to Add

1. **Section Labels** (side markers):
   - "Backend Configuration" → backend section
   - "Performance Settings" → performance section
   - "User Interface" → UI section

2. **Feature Highlights**:
   - Green badge next to "PostgreSQL": "Optimal"
   - Info icon next to "Spatial indexes": "Recommended for large datasets"
   - Warning icon next to "Confirm before apply": "May interrupt workflow"

3. **Tips Overlay** (bottom):
   - "Auto-detect backend: Let FilterMate choose the best option"

### Post-Processing

1. **Add section markers** (colored bars on left)
2. **Add feature badges** (green/yellow/red)
3. **Add info tooltips**
4. **Optimize** to <300 KB

### Expected Output

```
tab-settings.png
Size: 250-300 KB
Dimensions: 800x600
Purpose: User guide, configuration.md
Annotations: 3 section labels + 3 feature badges + tips
```

---

## Screenshot 6: Backend Indicator (backend-indicator.png)

**Purpose**: Show backend selection indicator  
**Resolution**: 400x200  
**File Size Target**: <100 KB

### Scene Setup

**Focus**: Backend indicator badge (small widget)

**Three States to Capture**:

#### Variant A: PostgreSQL (Optimal)
- Badge: "PostgreSQL ⚡"
- Color: Green background
- Icon: Lightning bolt (⚡)
- Tooltip: "Using PostgreSQL backend (optimal performance)"

#### Variant B: Spatialite (Good)
- Badge: "Spatialite 📦"
- Color: Blue background
- Icon: Package (📦)
- Tooltip: "Using Spatialite backend (good performance)"

#### Variant C: QGIS Processing (Fallback)
- Badge: "QGIS Processing ⚙️"
- Color: Yellow background
- Icon: Gear (⚙️)
- Tooltip: "Using QGIS backend (universal compatibility)"

### Capture Instructions

1. **Capture 3 separate screenshots** (one per backend)
2. **Crop tightly** around indicator (400x200 each)
3. **Include tooltip** when hovering
4. **Clear, readable text**

### Annotations to Add

1. **Performance Indicators**:
   - PostgreSQL: "Fast ⚡" badge
   - Spatialite: "Medium 📦" badge
   - QGIS: "Slower ⚙️" badge

2. **Comparison Table** (composite image):
   ```
   Backend      | Speed | Best For
   -------------|-------|----------
   PostgreSQL   | ⚡⚡⚡ | Large datasets
   Spatialite   | ⚡⚡   | Medium datasets
   QGIS         | ⚡     | All datasets
   ```

3. **Callout**: "Click to change backend"

### Post-Processing

1. **Create composite** (3 variants side-by-side)
2. **Add comparison annotations**
3. **Add "Automatic detection" label**
4. **Optimize** to <100 KB

### Expected Output

```
backend-indicator.png (composite)
Size: 80-100 KB
Dimensions: 400x200 (or 1200x200 for all 3)
Purpose: Backends documentation, overview.md
Annotations: Performance badges + comparison table
```

---

## Screenshot 7: Expression Builder (expression-builder.png)

**Purpose**: Show QGIS Expression Builder integration  
**Resolution**: 1200x800  
**File Size Target**: <400 KB

### Scene Setup

**Dialog State**:
- QGIS Expression Builder dialog open
- Left panel: Function categories expanded
- Center panel: Expression text area
- Right panel: Function help visible
- Expression: `intersects($geometry, buffer(geometry(get_feature('metro_stations', 'osm_id', 1)), 300))`
- Preview: "Expression is valid" (green checkmark)

**Categories Visible**:
- Geometry functions (expanded)
- Fields and Values
- Variables
- Recent expressions

**Function Help** (right panel):
- `intersects()` function documentation
- Syntax examples
- Usage notes

### Capture Instructions

1. **Open Expression Builder** from FilterMate
2. **Expand Geometry category**
3. **Type spatial expression** (as above)
4. **Show preview result** (green checkmark)
5. **Capture full dialog** (1200x800)

### Annotations to Add

1. **Area Labels** (numbered regions):
   - ① "Function Categories" → left panel
   - ② "Expression Editor" → center area
   - ③ "Function Help" → right panel
   - ④ "Expression Preview" → bottom status

2. **Interaction Hints**:
   - Double-click arrow: "Double-click to insert" (next to functions)
   - Green checkmark: "Valid expression ✓"
   - Syntax highlighting indication

3. **Feature Highlight**:
   - Yellow outline around expression text area
   - Blue outline around Geometry category

4. **Usage Tip** (bottom overlay):
   - "Use Expression Builder for complex spatial queries"

### Post-Processing

1. **Add numbered region markers**
2. **Add interaction hints** (small arrows, tooltips)
3. **Highlight expression syntax** (if possible)
4. **Add usage tip overlay**
5. **Optimize** to <400 KB

### Expected Output

```
expression-builder.png
Size: 350-400 KB
Dimensions: 1200x800
Purpose: User guide, expression-builder.md, spatial-predicates.md
Annotations: 4 area labels + interaction hints + usage tip
```

---

## Additional Screenshots (Workflow-Specific)

### Screenshot 8-17: Workflow Examples

These screenshots illustrate specific workflows (urban planning, real estate, environmental). Each should follow the pattern:

**Structure**:
1. **Before state**: Original data
2. **FilterMate interaction**: Filter being applied
3. **After state**: Filtered results
4. **Action highlight**: Key UI element used

**Examples**:

#### Urban Planning Workflow (3 screenshots)
- **urban-workflow-01.png**: Schools layer + expression for distance filter
- **urban-workflow-02.png**: Buffer operation on metro stations
- **urban-workflow-03.png**: Final filtered schools near metro (result)

#### Real Estate Workflow (3 screenshots)
- **real-estate-01.png**: Buildings layer + area filter
- **real-estate-02.png**: Combined filter (area + proximity)
- **real-estate-03.png**: Export dialog with results

#### Environmental Workflow (2 screenshots)
- **environmental-01.png**: Green spaces layer + size filter
- **environmental-02.png**: Intersection with residential areas

### Capture Guidelines for Workflow Screenshots

1. **Consistent framing**: Same zoom level within workflow
2. **Clear progression**: Before → During → After
3. **Realistic data**: Use paris_10th.gpkg sample data
4. **Annotations**: Step numbers (1→2→3), arrows showing changes
5. **File size**: <300 KB each
6. **Resolution**: 1200x700 (landscape)

---

## Production Workflow

### Pre-Production Checklist

- [ ] Generate paris_10th.gpkg (or use existing)
- [ ] Load data in QGIS with styles
- [ ] Position FilterMate dockwidget consistently (right side)
- [ ] Set QGIS window to appropriate size (1920x1080 for full, smaller for details)
- [ ] Clean workspace (hide unnecessary panels/toolbars)
- [ ] Configure theme (light or dark - consistency)
- [ ] Prepare expressions and settings in advance
- [ ] Test capture tool (screenshot + save path)

### Capture Process

1. **Setup Scene**
   - Arrange QGIS layout as specified
   - Load appropriate layers
   - Configure FilterMate state
   - Verify all elements visible

2. **Capture**
   - Use native screenshot tool (Win+Shift+S, etc.)
   - Select area or full window as needed
   - Save as PNG with descriptive name
   - Verify capture (no cut-off elements)

3. **Immediate Review**
   - Check resolution (1920x1080 or 800x600)
   - Verify clarity (no blur, readable text)
   - Ensure all required elements visible
   - Retake if needed

### Annotation Process (Figma Recommended)

1. **Import Screenshot**
   - Drag PNG into Figma
   - Lock layer (prevent accidental move)
   - Create annotation layer above

2. **Add Numbered Callouts**
   - Create circle shape (24x24px)
   - Fill: Primary blue (#007AFF)
   - Add text (white, bold, center-aligned)
   - Duplicate for multiple callouts

3. **Add Arrows**
   - Use Figma pen tool
   - Stroke: 3px, solid
   - Color: Yellow (#FFCC00) or Red (#FF3B30)
   - Add arrowhead (triangle)

4. **Add Text Labels**
   - Use Inter or Roboto font
   - Size: 14-16px
   - Color: White text
   - Add background rectangle (dark, 80% opacity, 4px rounded corners)

5. **Add Highlight Boxes**
   - Rectangle with no fill
   - Stroke: 2-3px, solid
   - Color: Red, Yellow, or Blue
   - Rounded corners: 4px

6. **Add Overlay Elements**
   - Bottom overlay: Dark box for tips/descriptions
   - Badges: Small icons with text (✓, ⚠️, ⚡)
   - Icons: Use Feather Icons or similar

7. **Export**
   - Select all layers (screenshot + annotations)
   - Export as PNG
   - Scale: 1x (original size)
   - Format: PNG

### Alternative: Annotation with GIMP

1. **Open screenshot** in GIMP
2. **Create new layer** (annotations)
3. **Add shapes**: Use ellipse/rectangle select tools, stroke selection
4. **Add text**: Text tool, white color, add drop shadow for visibility
5. **Add arrows**: Use brush/pencil tool with arrowhead
6. **Export**: File → Export As → PNG

### Optimization

1. **TinyPNG** (https://tinypng.com/):
   - Upload PNG
   - Download optimized version
   - Typically reduces size by 60-70%

2. **ImageOptim** (macOS):
   - Drag and drop images
   - Automatic optimization
   - Preserves quality

3. **pngquant** (Command line):
   ```bash
   pngquant --quality=80-95 screenshot.png
   ```

4. **Squoosh** (Web-based):
   - https://squoosh.app/
   - Visual quality comparison
   - Multiple format options

### Quality Assurance Checklist

- [ ] Resolution correct (1920x1080 or 800x600)
- [ ] File size <500 KB (preferably <400 KB)
- [ ] All text readable at 100% zoom
- [ ] Annotations clear and professional
- [ ] Colors consistent (match design system)
- [ ] No personal/sensitive data visible
- [ ] Proper file naming (tab-filtering.png, etc.)
- [ ] PNG format (not JPG)
- [ ] No artifacts or compression issues
- [ ] Consistent styling across all screenshots

---

## File Organization

```
website/
└── static/
    └── img/
        ├── screenshots/
        │   ├── interface-full.png           (350-400 KB)
        │   ├── tab-filtering.png            (250-300 KB)
        │   ├── tab-buffer.png               (250-300 KB)
        │   ├── tab-export.png               (250-300 KB)
        │   ├── tab-settings.png             (250-300 KB)
        │   ├── backend-indicator.png        (80-100 KB)
        │   └── expression-builder.png       (350-400 KB)
        │
        └── workflows/
            ├── urban-workflow-01.png        (250-300 KB)
            ├── urban-workflow-02.png        (250-300 KB)
            ├── urban-workflow-03.png        (250-300 KB)
            ├── real-estate-01.png           (250-300 KB)
            ├── real-estate-02.png           (250-300 KB)
            ├── real-estate-03.png           (250-300 KB)
            ├── environmental-01.png         (250-300 KB)
            └── environmental-02.png         (250-300 KB)

Total: ~3-4 MB (7 main + 8 workflow screenshots)
```

---

## Embedding in Documentation

### Basic Markdown

```markdown
## FilterMate Interface

FilterMate integrates seamlessly with QGIS:

![FilterMate Interface Overview](../../static/img/screenshots/interface-full.png)

The interface consists of four main areas:
1. **Layers Panel** - Manage your data sources
2. **Map Canvas** - Visualize filtered results
3. **FilterMate Dockwidget** - Control filtering operations
4. **Results Display** - See your filtered features
```

### With Figure Caption

```markdown
<figure>
  <img src="/img/screenshots/tab-filtering.png" alt="Filtering Tab Detail" />
  <figcaption>
    <strong>Figure 1:</strong> The Filtering tab provides intuitive controls for applying data filters.
  </figcaption>
</figure>
```

### Lightbox/Modal Support

```markdown
[![FilterMate Interface](../../static/img/screenshots/interface-full.png)](../../static/img/screenshots/interface-full.png)

*Click to enlarge*
```

### Docusaurus Image Component

```jsx
import ThemedImage from '@theme/ThemedImage';

<ThemedImage
  alt="FilterMate Interface"
  sources={{
    light: useBaseUrl('/img/screenshots/interface-full.png'),
    dark: useBaseUrl('/img/screenshots/interface-full-dark.png'),
  }}
/>
```

---

## Accessibility

### Alt Text Examples

```markdown
<!-- Good alt text -->
![FilterMate filtering tab showing expression field with 'area_m2 > 500' filter, Apply button, and feature count of 892](tab-filtering.png)

<!-- Better: Descriptive for screen readers -->
![FilterMate filtering tab interface displaying a text field with the expression 'area_m2 > 500', a green Apply button, undo and redo icons, and a badge showing 892 filtered features out of 3,199 total](tab-filtering.png)
```

### Providing Text Alternatives

Always accompany screenshots with descriptive text:

```markdown
## Filtering Tab

The Filtering tab (shown below) contains:
- **Layer Selector**: Choose which layer to filter
- **Expression Field**: Enter your QGIS expression
- **Expression Builder**: Click (fx) to open the builder
- **Apply Button**: Execute the filter
- **Undo/Redo**: Revert or reapply filters
- **Feature Count**: Shows filtered vs. total features

![Filtering Tab Screenshot](tab-filtering.png)
```

---

## Timeline Estimate

| Task | Duration | Notes |
|------|----------|-------|
| Setup (QGIS + Figma) | 30 min | One-time setup |
| Capture 7 main screenshots | 1 hour | ~8-10 min per screenshot |
| Capture 8 workflow screenshots | 1.5 hours | ~10-12 min per screenshot |
| Annotation (Figma) | 2.5 hours | ~10 min per screenshot |
| Optimization | 30 min | Batch process |
| Embedding in docs | 1 hour | Add to markdown files |
| QA & Testing | 30 min | Review all screenshots |
| **TOTAL** | **7.5 hours** | Phase 2 screenshots |

Combined with GIFs (7 hours), Phase 2 Visual Content = **~15 hours total**

---

## Success Criteria

- [ ] 7 main screenshots captured and annotated
- [ ] 8 workflow screenshots captured and annotated
- [ ] All screenshots <500 KB each
- [ ] Consistent styling and branding
- [ ] Clear, professional annotations
- [ ] Embedded in documentation
- [ ] Alt text provided for accessibility
- [ ] Tested on desktop and mobile views
- [ ] User feedback positive
- [ ] No sensitive data visible

---

## Tips & Best Practices

### Consistency

- Use **same QGIS theme** across all screenshots (light recommended for clarity)
- Use **same FilterMate position** (right dockwidget)
- Use **same annotation style** (colors, fonts, sizes)
- Use **same zoom levels** for similar content

### Clarity

- **Clean workspace**: Hide unnecessary UI elements
- **Readable text**: Ensure all text is legible at 100%
- **High contrast**: Use light theme with dark text
- **Realistic data**: Use sample data, not random test data

### Professionalism

- **No clutter**: Remove temporary files, test layers
- **Proper naming**: Use descriptive layer names
- **Styled layers**: Apply appropriate symbolization
- **Consistent branding**: Use FilterMate colors/icons

### Efficiency

- **Batch capture**: Capture all screenshots in one session
- **Template annotations**: Create reusable Figma components
- **Script optimization**: Automate image compression
- **Version control**: Keep original uncompressed versions

---

**Next Steps**: Execute screenshot capture workflow using this guide.

**Tools Ready**: QGIS configured, Figma account, screenshot tools installed.

**Expected Outcome**: 15 professional annotated screenshots for documentation.

---

*Generated: December 2025*  
*FilterMate Version: v2.3.7*  
*Document Version: 1.0.0*
