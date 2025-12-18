# Visual Assets Creation Guide - Phase 2

**Goal**: Create GIFs, screenshots, and infographics for FilterMate documentation  
**Estimated Time**: 8 hours total  
**Tools**: ScreenToGif, QGIS, Figma/Inkscape

---

## 📋 Required Assets Inventory

### Priority 1: Essential GIFs (3 hours)

| Asset | Location | Duration | Size | Priority |
|-------|----------|----------|------|----------|
| **apply-filter.gif** | user-guide/filtering-basics.md | 10s | <2MB | 🔴 Critical |
| **undo-redo.gif** | user-guide/undo-redo.md | 8s | <1.5MB | 🔴 Critical |
| **export-workflow.gif** | user-guide/export-features.md | 12s | <2MB | 🔴 Critical |
| **geometric-filter.gif** | user-guide/geometric-filtering.md | 15s | <2.5MB | 🟡 High |
| **buffer-distance.gif** | user-guide/buffer-operations.md | 10s | <2MB | 🟡 High |
| **backend-switch.gif** | backends/overview.md | 8s | <1.5MB | 🟢 Medium |

### Priority 2: Interface Screenshots (2 hours)

| Asset | Location | Resolution | Format | Priority |
|-------|----------|------------|--------|----------|
| **interface-full.png** | user-guide/interface-overview.md | 1920x1080 | PNG | 🔴 Critical |
| **attribute-tab.png** | user-guide/filtering-basics.md | 800x600 | PNG | 🔴 Critical |
| **filtering-tab.png** | user-guide/geometric-filtering.md | 800x600 | PNG | 🔴 Critical |
| **export-tab.png** | user-guide/export-features.md | 800x600 | PNG | 🔴 Critical |
| **history-tab.png** | user-guide/filter-history.md | 800x600 | PNG | 🟡 High |
| **backend-indicator.png** | backends/overview.md | 400x200 | PNG | 🟡 High |
| **config-editor.png** | advanced/configuration.md | 1000x800 | PNG | 🟢 Medium |

### Priority 3: Infographics (2 hours)

| Asset | Location | Type | Priority |
|-------|----------|------|----------|
| **backend-comparison.svg** | backends/overview.md | Flowchart | 🔴 Critical |
| **performance-chart.svg** | backends/performance-benchmarks.md | Bar chart | 🟡 High |
| **spatial-predicates-visual.svg** | reference/cheat-sheets/spatial-predicates.md | Diagram | 🟢 Medium |

### Priority 4: Workflow Screenshots (1 hour)

| Workflow | Screenshots Needed | Priority |
|----------|-------------------|----------|
| Urban Planning | 3 screenshots | 🟡 High |
| Real Estate | 3 screenshots | 🟡 High |
| Environmental | 2 screenshots | 🟢 Medium |
| Emergency Services | 2 screenshots | 🟢 Low |

---

## 🎬 GIF Creation Specifications

### General Settings

**Tools**:
- **ScreenToGif** (Windows): https://www.screentogif.com/
- **Peek** (Linux): https://github.com/phw/peek
- **LICEcap** (Mac/Windows): https://www.cockos.com/licecap/

**Settings**:
- **Frame Rate**: 15 FPS (smooth but small file)
- **Resolution**: 1280x720 (scale to fit documentation)
- **Compression**: High (target <2MB per GIF)
- **Loop**: Infinite
- **Delay between loops**: 2 seconds

---

### 1. apply-filter.gif (Critical Priority)

**Location**: `website/docs/user-guide/filtering-basics.md`

**Scenario**: Basic attribute filter application

**Steps** (10 seconds):
1. **0-2s**: Open FilterMate panel, select buildings layer
2. **2-5s**: Type expression: `"height" > 20`
3. **5-7s**: Click "Apply Filter" button
4. **7-10s**: Map updates, showing only tall buildings (add zoom)

**QGIS Setup**:
- Sample dataset: paris_10th.gpkg
- Layer: buildings (3,187 features)
- View: Zoom to full extent
- Style: Buildings colored by height (gradient)

**Recording Tips**:
- Clean workspace (close unnecessary panels)
- Large font size (readable in GIF)
- Smooth mouse movements
- Highlight button clicks

**Post-Processing**:
- Add text overlays: "1. Select layer" "2. Write expression" "3. Apply"
- Trim unnecessary frames
- Optimize: reduce colors if >2MB

**Expected Result**: 
- Clear demonstration of basic workflow
- File size: ~1.5-2MB
- Embedded in documentation with caption

---

### 2. undo-redo.gif (Critical Priority)

**Location**: `website/docs/user-guide/undo-redo.md`

**Scenario**: Demonstrate Undo/Redo functionality

**Steps** (8 seconds):
1. **0-2s**: Apply filter: `"population" > 10000`
2. **2-4s**: Click Undo button (Ctrl+Z), filter removed
3. **4-6s**: Click Redo button (Ctrl+Y), filter reapplied
4. **6-8s**: Apply different filter, undo again

**QGIS Setup**:
- Layer: schools or buildings
- Focus on toolbar buttons (zoom if needed)
- Show status messages ("Filter undone", "Filter redone")

**Post-Processing**:
- Add arrows pointing to Undo/Redo buttons
- Highlight keyboard shortcuts in corner

---

### 3. export-workflow.gif (Critical Priority)

**Location**: `website/docs/user-guide/export-features.md`

**Scenario**: Complete export process

**Steps** (12 seconds):
1. **0-2s**: Apply filter to select subset
2. **2-4s**: Click EXPORT tab
3. **4-7s**: Configure: Format (GeoPackage), filename, options
4. **7-10s**: Click "Export" button
5. **10-12s**: Success message, file saved

**QGIS Setup**:
- Pre-applied filter: `"height" BETWEEN 15 AND 25`
- Export dialog visible
- File browser showing output folder

**Post-Processing**:
- Add step numbers overlay
- Show file icon appearing in folder

---

### 4. geometric-filter.gif (High Priority)

**Location**: `website/docs/user-guide/geometric-filtering.md`

**Scenario**: Spatial filtering with reference layer

**Steps** (15 seconds):
1. **0-3s**: Select buildings layer
2. **3-6s**: In FILTERING tab, choose "metro_stations" reference
3. **6-9s**: Set predicate: Intersects, buffer: 300m
4. **9-12s**: Click "Apply Geometric Filter"
5. **12-15s**: Map shows buildings within 300m of metro

**QGIS Setup**:
- Layers: buildings + metro_stations visible
- Show buffer visualization (transparent circles)
- Result: subset highlighted

**Post-Processing**:
- Add buffer circle animation (optional)
- Label reference layer and target layer

---

### 5. buffer-distance.gif (High Priority)

**Location**: `website/docs/user-guide/buffer-operations.md`

**Scenario**: Demonstrate buffer distance impact

**Steps** (10 seconds):
1. **0-3s**: Apply filter with 100m buffer
2. **3-5s**: Result: few features selected
3. **5-7s**: Change buffer to 500m
4. **7-10s**: Result: many more features selected

**QGIS Setup**:
- Reference layer: roads or metro_stations
- Target: buildings
- Show count change (status bar)

**Post-Processing**:
- Add distance labels (100m, 500m)
- Show feature count overlay

---

### 6. backend-switch.gif (Medium Priority)

**Location**: `website/docs/backends/overview.md`

**Scenario**: Backend indicator and layer info

**Steps** (8 seconds):
1. **0-2s**: Load PostgreSQL layer, indicator shows "PostgreSQL"
2. **2-4s**: Load Spatialite layer, indicator changes
3. **4-6s**: Click indicator to see layer info
4. **6-8s**: Info popup shows backend details

**QGIS Setup**:
- Multiple layers from different sources
- Backend indicator visible in FilterMate panel

**Post-Processing**:
- Highlight backend indicator with circle
- Add labels: "PostgreSQL", "Spatialite", "OGR"

---

## 📸 Screenshot Creation Specifications

### General Settings

**Tool**: QGIS built-in or system screenshot

**Settings**:
- **Resolution**: Native (1920x1080 recommended)
- **Format**: PNG (lossless)
- **DPI**: 96 (web standard)
- **Color depth**: 24-bit RGB

**QGIS Setup**:
- Clean UI (close unnecessary panels)
- Default QGIS theme or light theme
- FilterMate panel docked on right
- No personal information visible

---

### 1. interface-full.png (Critical)

**Location**: `website/docs/user-guide/interface-overview.md`

**Content**: Full FilterMate interface with all tabs visible

**Requirements**:
- All 4 tabs visible (ATTRIBUTE, FILTERING, EXPORT, HISTORY)
- Sample layer loaded
- Clear labels and buttons
- 1920x1080 resolution

**Annotations** (add in post-processing):
1. Red box: Main tab selector
2. Blue box: Layer selector dropdown
3. Green box: Action buttons area
4. Yellow box: Status information

**Figma/Inkscape**:
- Import PNG
- Add numbered labels (1-10)
- Export annotated version

---

### 2. attribute-tab.png (Critical)

**Location**: `website/docs/user-guide/filtering-basics.md`

**Content**: ATTRIBUTE tab with expression editor

**Focus Area**: 800x600 (crop to tab content)

**Requirements**:
- Expression editor visible
- Example expression: `"population" > 10000 AND "type" = 'residential'`
- Syntax highlighting visible
- Clear button states

**Annotations**:
- Arrow pointing to expression editor
- Label: "Write your QGIS expression here"

---

### 3. filtering-tab.png (Critical)

**Location**: `website/docs/user-guide/geometric-filtering.md`

**Content**: FILTERING tab configuration

**Requirements**:
- Reference layer dropdown
- Spatial predicate selector
- Buffer distance field
- Apply button

**Annotations**:
1. Reference layer: "metro_stations"
2. Predicate: "Intersects"
3. Buffer: "300"
4. Units indicator: "meters"

---

### 4. export-tab.png (Critical)

**Location**: `website/docs/user-guide/export-features.md`

**Content**: EXPORT tab with format options

**Requirements**:
- Format dropdown (GeoPackage, Shapefile, etc.)
- Filename input field
- Export options checkboxes
- Progress bar (if possible)

**Annotations**:
- Highlight recommended format (GeoPackage)
- Show file path

---

### 5. history-tab.png (High Priority)

**Location**: `website/docs/user-guide/filter-history.md`

**Content**: HISTORY tab with past filters

**Requirements**:
- List of 3-5 previous filters
- Timestamps visible
- Reapply/Delete buttons
- Filter expressions readable

**Annotations**:
- Number each history item
- Highlight action buttons

---

### 6. backend-indicator.png (High Priority)

**Location**: `website/docs/backends/overview.md`

**Content**: Backend indicator widget close-up

**Size**: 400x200 (zoomed detail)

**Requirements**:
- Text: "Backend: PostgreSQL" (or other)
- Icon or color indicator
- Feature count
- Clickable appearance

**Annotations**:
- Arrow: "Click for layer info"
- Label: "Current backend type"

---

### 7. config-editor.png (Medium Priority)

**Location**: `website/docs/advanced/configuration.md`

**Content**: Configuration editor dialog

**Size**: 1000x800

**Requirements**:
- JSON editor with syntax highlighting
- Save/Cancel buttons
- Validation status
- Example configuration visible

**Annotations**:
- Highlight key sections (logging, performance, ui)
- Add tooltips for each section

---

## 🎨 Infographic Creation

### Tools

**Vector Graphics**:
- **Figma**: https://www.figma.com/ (recommended, web-based)
- **Inkscape**: https://inkscape.org/ (free, desktop)
- **Adobe Illustrator**: Professional option

**Charts**:
- **Chart.js**: JavaScript charting
- **Plotly**: Python data visualization
- **Excel/Google Sheets**: Export as SVG

---

### 1. backend-comparison.svg (Critical)

**Location**: `website/docs/backends/overview.md`

**Type**: Flowchart with performance comparison

**Content**:

```
[Dataset Size]
      |
      v
< 10k features ──→ [Any Backend] ──→ ⚡ Fast
      |
10k-50k ──→ [Spatialite] ──→ ⚡⚡ Very Fast
      |            └─→ [PostgreSQL] ──→ ⚡⚡⚡ Ultra Fast
      |
> 50k ──→ [PostgreSQL Required] ──→ ⚡⚡⚡ Ultra Fast
```

**Visual Style**:
- Color-coded paths: Green (good), Orange (better), Red (best)
- Icons: Database icons for each backend
- Performance bars below each option

**Dimensions**: 1200x800px  
**Format**: SVG (scalable)

**Figma Steps**:
1. Create artboard 1200x800
2. Add flowchart nodes (rectangles with rounded corners)
3. Connect with arrows
4. Add icons from Flaticon or Material Icons
5. Export as SVG

---

### 2. performance-chart.svg (High Priority)

**Location**: `website/docs/backends/performance-benchmarks.md`

**Type**: Bar chart comparing query times

**Data**:
```
Dataset: 10k features
- PostgreSQL: 0.8s
- Spatialite: 1.2s
- OGR: 3.5s

Dataset: 100k features
- PostgreSQL: 2.1s
- Spatialite: 8.3s
- OGR: 18.7s
```

**Visual Style**:
- Grouped bar chart
- Color legend: Blue (PostgreSQL), Green (Spatialite), Orange (OGR)
- Y-axis: Query time (seconds)
- X-axis: Dataset size

**Tool**: Chart.js or Plotly

**Python (Plotly) Example**:
```python
import plotly.graph_objects as go

fig = go.Figure(data=[
    go.Bar(name='PostgreSQL', x=['10k', '100k'], y=[0.8, 2.1]),
    go.Bar(name='Spatialite', x=['10k', '100k'], y=[1.2, 8.3]),
    go.Bar(name='OGR', x=['10k', '100k'], y=[3.5, 18.7])
])

fig.update_layout(
    title='Backend Performance Comparison',
    xaxis_title='Dataset Size',
    yaxis_title='Query Time (seconds)',
    barmode='group'
)

fig.write_image("performance-chart.svg")
```

---

### 3. spatial-predicates-visual.svg (Medium Priority)

**Location**: `website/docs/reference/cheat-sheets/spatial-predicates.md`

**Type**: Visual diagram showing geometric relationships

**Content**: 
- 8 predicates illustrated
- Each with "TRUE" and "FALSE" example
- Simple geometric shapes (circles, rectangles)

**Layout**:
```
┌─────────────┬─────────────┬─────────────┐
│ Intersects  │   Within    │  Contains   │
│  [diagram]  │  [diagram]  │  [diagram]  │
├─────────────┼─────────────┼─────────────┤
│  Touches    │   Crosses   │  Overlaps   │
│  [diagram]  │  [diagram]  │  [diagram]  │
├─────────────┼─────────────┼─────────────┤
│  Disjoint   │   DWithin   │             │
│  [diagram]  │  [diagram]  │             │
└─────────────┴─────────────┴─────────────┘
```

**Visual Style**:
- Geometry A: Blue fill
- Geometry B: Red fill
- Overlap: Purple (blue+red mix)
- Green checkmark: TRUE
- Red X: FALSE

**Dimensions**: 1600x1200px

---

## 📁 File Organization

### Directory Structure

```
website/docs/assets/
├── gifs/
│   ├── apply-filter.gif
│   ├── undo-redo.gif
│   ├── export-workflow.gif
│   ├── geometric-filter.gif
│   ├── buffer-distance.gif
│   └── backend-switch.gif
├── screenshots/
│   ├── interface/
│   │   ├── interface-full.png
│   │   ├── attribute-tab.png
│   │   ├── filtering-tab.png
│   │   ├── export-tab.png
│   │   └── history-tab.png
│   ├── backends/
│   │   └── backend-indicator.png
│   ├── advanced/
│   │   └── config-editor.png
│   └── workflows/
│       ├── urban-planning-01.png
│       ├── urban-planning-02.png
│       └── ...
└── infographics/
    ├── backend-comparison.svg
    ├── performance-chart.svg
    └── spatial-predicates-visual.svg
```

### Naming Convention

**Pattern**: `{category}-{description}.{ext}`

**Examples**:
- `filter-apply-basic.gif`
- `interface-full-annotated.png`
- `backend-comparison-flowchart.svg`

**Rules**:
- Lowercase
- Hyphens (no spaces or underscores)
- Descriptive (avoid generic names like "image1.png")

---

## 🔗 Embedding in Documentation

### Markdown Syntax

**GIFs**:
```markdown
![Apply Filter Demo](../assets/gifs/apply-filter.gif)

*Figure 1: Applying an attribute filter in FilterMate*
```

**Screenshots**:
```markdown
![FilterMate Interface](../assets/screenshots/interface/interface-full.png)

**Key Components**:
1. Tab selector
2. Layer dropdown
3. Expression editor
4. Action buttons
```

**Infographics**:
```markdown
![Backend Comparison](../assets/infographics/backend-comparison.svg)

*Choose the right backend based on your dataset size*
```

### Docusaurus Configuration

Add to `docusaurus.config.js`:
```javascript
staticDirectories: ['static', 'docs/assets'],
```

### Optimization

**Before commit**:
1. **GIFs**: Use https://ezgif.com/optimize
2. **PNGs**: Use https://tinypng.com/
3. **SVGs**: Use https://jakearchibald.github.io/svgomg/

**Target sizes**:
- GIFs: < 2MB each
- PNGs: < 500KB each
- SVGs: < 100KB each

---

## ✅ Phase 2 Checklist

### Week 1: GIFs (3 hours)

- [ ] Install ScreenToGif/Peek
- [ ] Load paris_10th.gpkg in QGIS
- [ ] Record apply-filter.gif
- [ ] Record undo-redo.gif
- [ ] Record export-workflow.gif
- [ ] Record geometric-filter.gif
- [ ] Record buffer-distance.gif
- [ ] Record backend-switch.gif
- [ ] Optimize all GIFs (<2MB each)

### Week 2: Screenshots (2 hours)

- [ ] Capture interface-full.png
- [ ] Capture all 4 tab screenshots
- [ ] Capture backend-indicator.png
- [ ] Capture config-editor.png
- [ ] Annotate with Figma/Inkscape
- [ ] Optimize PNGs (<500KB each)

### Week 3: Infographics (2 hours)

- [ ] Create backend-comparison.svg in Figma
- [ ] Create performance-chart.svg with Plotly
- [ ] Create spatial-predicates-visual.svg
- [ ] Export and optimize SVGs

### Week 4: Workflow Screenshots (1 hour)

- [ ] Capture urban-planning workflow (3 shots)
- [ ] Capture real-estate workflow (3 shots)
- [ ] Capture environmental workflow (2 shots)
- [ ] Add to documentation

### Final: Integration

- [ ] Create assets/ directory structure
- [ ] Move all files to correct locations
- [ ] Update all documentation with asset links
- [ ] Test asset loading in Docusaurus
- [ ] Commit and push to repository

---

## 🎯 Quality Standards

### GIF Quality

✅ **Good**:
- Smooth 15 FPS
- Readable text
- Clear mouse actions
- File size < 2MB

❌ **Bad**:
- Choppy < 10 FPS
- Tiny unreadable text
- Fast jerky mouse
- File size > 3MB

### Screenshot Quality

✅ **Good**:
- Clean UI (no clutter)
- High resolution
- Proper annotations
- Consistent style

❌ **Bad**:
- Messy workspace
- Blurry/low-res
- No context
- Inconsistent fonts

### Infographic Quality

✅ **Good**:
- Clear hierarchy
- Color-coded
- Scalable (SVG)
- Professional design

❌ **Bad**:
- Cluttered
- Hard to read
- Raster (pixelated when scaled)
- Amateur design

---

## 📊 Progress Tracking

| Asset Type | Total | Completed | Progress |
|------------|-------|-----------|----------|
| **GIFs** | 6 | 0 | 0% |
| **Screenshots** | 7 | 0 | 0% |
| **Infographics** | 3 | 0 | 0% |
| **Workflow Shots** | 10 | 0 | 0% |
| **TOTAL** | 26 | 0 | 0% |

**Update this table** as assets are created.

---

*Guide version: 1.0 - December 18, 2025*  
*For: FilterMate v2.3.7 Documentation Phase 2*
