# FilterMate GIF Animations - Storyboards & Specifications

**Phase 2 Visual Content** - Technical Storyboards for Animation Creation

## Overview

This document provides detailed storyboards for the 6 GIF animations specified in `VISUAL_ASSETS_GUIDE.md`. Each storyboard includes:
- **Frame-by-frame breakdown** with timestamps
- **Mouse movements and clicks**
- **UI elements to highlight**
- **Annotations and callouts**
- **Recording settings**

## Recording Standards

### Technical Specifications

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Resolution** | 1280x720 (720p) | Balance quality/file size |
| **Frame Rate** | 15 fps | Smooth for UI, small file |
| **Duration** | 8-15 seconds | Attention span optimal |
| **File Size** | <2 MB per GIF | Web performance |
| **Format** | Optimized GIF | Universal compatibility |

### Recording Tools

**Recommended**: ScreenToGif (Windows) - https://www.screentogif.com/
- Free, open-source
- Built-in editor with annotations
- Excellent optimization

**Alternatives**:
- Peek (Linux) - https://github.com/phw/peek
- LICEcap (macOS/Windows) - https://www.cockos.com/licecap/
- Kap (macOS) - https://getkap.co/

### Recording Checklist

- [ ] QGIS window maximized at 1920x1080
- [ ] FilterMate dockwidget visible and styled
- [ ] Sample data (paris_10th.gpkg) loaded
- [ ] Layers symbolized with appropriate styles
- [ ] Clean workspace (no unnecessary panels)
- [ ] Mouse cursor visible and not too fast
- [ ] Prepare actions in advance (know what to click)
- [ ] Record 2-3 takes and select best

---

## GIF 1: Apply Filter (apply-filter.gif)

**Duration**: 10 seconds  
**Purpose**: Show basic filter application workflow  
**Key Message**: "Filtering is quick and intuitive"

### Setup

**Layers**:
- `buildings` layer active (3,199 features)
- Zoom level: Show ~200 buildings on screen
- Style: Buildings in light gray

**FilterMate State**:
- Dockwidget open on right side
- Clean state (no previous filter)
- Expression field empty

### Storyboard

| Time | Frame | Action | Visual | Annotation |
|------|-------|--------|--------|------------|
| 0:00 | 1 | Initial view | Map with all buildings visible | "3,199 buildings" |
| 0:01 | 2 | Mouse move to expression field | Cursor moves to expression field | |
| 0:02 | 3 | Click expression field | Field gains focus (border highlight) | |
| 0:03 | 4 | Type expression | `"area_m2" > 500` appears character by character | Callout: "Filter large buildings" |
| 0:06 | 5 | Mouse move to Apply button | Cursor moves down to green Apply button | |
| 0:07 | 6 | Hover Apply button | Button highlights (hover state) | |
| 0:08 | 7 | Click Apply button | Button pressed animation | |
| 0:08 | 8 | Processing indicator | Brief loading spinner (0.5s) | |
| 0:09 | 9 | Filter applied | Map updates - smaller buildings disappear | Arrow pointing to filtered buildings |
| 0:10 | 10 | Final state | Fewer buildings visible, counter updates | "892 buildings" with checkmark |

### Recording Notes

- **Pre-type expression** in a text editor to copy-paste (or type slowly and clearly)
- **Pause 1 second** on final frame to show result
- **Highlight** the feature count change (3,199 → 892)
- **Optional**: Add subtle zoom to show detail

### Post-Processing

1. Add text annotations:
   - Frame 1: "Before: 3,199 buildings"
   - Frame 4: Speech bubble: "area_m2 > 500"
   - Frame 10: "After: 892 buildings ✓"

2. Add arrow/circle callouts:
   - Frame 5: Circle around Apply button
   - Frame 9: Arrow pointing to filtered area

3. Optimize GIF:
   - Reduce colors to 128 (sufficient for UI)
   - Remove duplicate frames
   - Target: <1.5 MB

### Expected Output

```
apply-filter.gif
Size: 1.2-1.5 MB
Dimensions: 1280x720
Duration: 10s
Frames: ~150 frames @ 15fps
```

---

## GIF 2: Undo/Redo (undo-redo.gif)

**Duration**: 8 seconds  
**Purpose**: Demonstrate undo/redo functionality  
**Key Message**: "Experiment safely with filters"

### Setup

**Layers**:
- `schools` layer active (28 features)
- Zoom level: Show all schools in Paris 10th
- Style: Schools in red markers

**FilterMate State**:
- Previous filter applied: `"school_type" = 'primary'` (15 features)
- Undo/Redo buttons visible and enabled

### Storyboard

| Time | Frame | Action | Visual | Annotation |
|------|-------|--------|--------|------------|
| 0:00 | 1 | Initial state | 15 primary schools visible | "15 schools filtered" |
| 0:01 | 2 | Mouse to Undo button | Cursor moves to Undo (↶) icon | Circle highlight |
| 0:02 | 3 | Click Undo | Undo button pressed | |
| 0:03 | 4 | Undo animation | Schools reappear with fade-in effect | Arrow: "Restored" |
| 0:04 | 5 | All schools visible | Map shows all 28 schools | "28 schools (all)" |
| 0:05 | 6 | Mouse to Redo button | Cursor moves to Redo (↷) icon | Circle highlight |
| 0:06 | 7 | Click Redo | Redo button pressed | |
| 0:07 | 8 | Redo animation | Schools filter reapplied, some fade out | Arrow: "Reapplied" |
| 0:08 | 9 | Final state | 15 primary schools visible again | "15 schools ✓" |

### Recording Notes

- **Clear separation** between Undo and Redo actions (2s pause)
- **Emphasize** the feature count changes (15 → 28 → 15)
- **Show** Undo/Redo button states (enabled/disabled)
- **Optional**: Add keyboard shortcut overlay (Ctrl+Z / Ctrl+Y)

### Post-Processing

1. Add icon overlays:
   - Frame 2: Undo icon enlarged
   - Frame 6: Redo icon enlarged

2. Add text annotations:
   - Frame 4: "Undo restores all features"
   - Frame 8: "Redo reapplies filter"

3. Add visual effects:
   - Subtle highlight glow on Undo/Redo buttons
   - Feature count badge animation

### Expected Output

```
undo-redo.gif
Size: 1.0-1.2 MB
Dimensions: 1280x720
Duration: 8s
Frames: ~120 frames @ 15fps
```

---

## GIF 3: Export Workflow (export-workflow.gif)

**Duration**: 12 seconds  
**Purpose**: Show complete export process  
**Key Message**: "Export filtered data easily"

### Setup

**Layers**:
- `roads` layer active with filter applied
- Filter: `"road_type" IN ('primary', 'secondary')`
- Result: 45 main roads

**FilterMate State**:
- Filter applied and visible
- Export tab selected
- Output path empty

### Storyboard

| Time | Frame | Action | Visual | Annotation |
|------|-------|--------|--------|------------|
| 0:00 | 1 | Initial view | Filtered roads visible on map | "45 main roads" |
| 0:01 | 2 | Click Export tab | Export tab becomes active | Tab highlights |
| 0:02 | 3 | Export panel visible | Shows format dropdown, path field, options | |
| 0:03 | 4 | Click Format dropdown | Dropdown opens: GeoPackage, Shapefile, GeoJSON | Circle: dropdown |
| 0:04 | 5 | Select GeoPackage | "GeoPackage (.gpkg)" selected | Checkmark |
| 0:05 | 6 | Click Browse button | File picker icon button | Circle: button |
| 0:06 | 7 | File dialog opens | Native file picker dialog | Overlay: "Choose location" |
| 0:07 | 8 | Select path | Path: `C:/exports/main_roads.gpkg` | |
| 0:08 | 9 | Path populated | Export path field shows selected path | |
| 0:09 | 10 | Click Export button | Green "Export" button pressed | Circle: button |
| 0:10 | 11 | Progress indicator | Export progress bar (0% → 100%) | "Exporting..." |
| 0:11 | 12 | Success message | QGIS message bar: "Export successful" | Green checkmark |
| 0:12 | 13 | Final state | Success confirmation visible | "✓ 45 features exported" |

### Recording Notes

- **Speed up** file dialog (users know how to navigate)
- **Emphasize** format selection (common question)
- **Show** progress bar even for quick exports
- **Include** success message (validation)

### Post-Processing

1. Add step numbers:
   - Frame 2: "1. Select Export tab"
   - Frame 4: "2. Choose format"
   - Frame 6: "3. Select path"
   - Frame 10: "4. Export"

2. Add annotations:
   - Frame 5: "GeoPackage recommended"
   - Frame 12: "Export complete!"

3. Compress dialog transition:
   - Reduce frames 6-8 (file dialog) to 1 second

### Expected Output

```
export-workflow.gif
Size: 1.8-2.0 MB
Dimensions: 1280x720
Duration: 12s
Frames: ~180 frames @ 15fps
```

---

## GIF 4: Geometric Filter (geometric-filter.gif)

**Duration**: 15 seconds  
**Purpose**: Demonstrate spatial filtering with buffer  
**Key Message**: "Powerful spatial filtering"

### Setup

**Layers**:
- `schools` layer (28 features)
- `metro_stations` layer (12 features)
- Both layers visible
- Metro stations symbolized with blue markers

**FilterMate State**:
- schools layer active
- Expression Builder open

### Storyboard

| Time | Frame | Action | Visual | Annotation |
|------|-------|--------|--------|------------|
| 0:00 | 1 | Initial view | All schools and metro stations visible | "Find schools near metro" |
| 0:01 | 2 | Click Expression Builder | Builder button (fx icon) pressed | |
| 0:02 | 3 | Builder dialog opens | Expression Builder dialog visible | |
| 0:03 | 4 | Navigate to Geometry | Click "Geometry" category in function tree | |
| 0:04 | 5 | Select $geometry | `$geometry` highlighted | |
| 0:05 | 6 | Type expression | `intersects($geometry, buffer(geometry(get_feature('metro_stations', 'station_name', 'Gare de l'Est')), 300))` | Simplified shown |
| 0:09 | 7 | Expression preview | Preview shows: "Valid expression" | Green checkmark |
| 0:10 | 8 | Click OK | Expression Builder closes | |
| 0:11 | 9 | Expression in field | Full expression visible in FilterMate | Tooltip: "Within 300m" |
| 0:12 | 10 | Click Apply | Apply button pressed | |
| 0:13 | 11 | Buffer visualization | Brief flash: 300m buffer circle around metro | Highlight circle |
| 0:14 | 12 | Filter applied | Only schools within buffer visible | "8 schools" |
| 0:15 | 13 | Final zoom | Zoom to filtered schools with metro station | Arrows connecting |

### Recording Notes

- **Simplify expression** in visualization (show concept, not full syntax)
- **Add visual cue** for 300m buffer (temporary circle overlay)
- **Highlight** spatial relationship (arrows from metro to schools)
- **Show** both layers to clarify spatial logic

### Post-Processing

1. Add simplified expression overlay:
   - Frame 6: Show: `$geometry intersects buffer(metro, 300m)`
   - Full expression in tooltip

2. Add spatial visualization:
   - Frame 11: Add 300m buffer circle (semi-transparent blue)
   - Frame 13: Add connection arrows (metro → schools)

3. Add annotations:
   - Frame 1: "28 schools, 12 metro stations"
   - Frame 12: "8 schools within 300m of metro"

### Expected Output

```
geometric-filter.gif
Size: 1.8-2.0 MB
Dimensions: 1280x720
Duration: 15s
Frames: ~225 frames @ 15fps
```

---

## GIF 5: Buffer Distance (buffer-distance.gif)

**Duration**: 10 seconds  
**Purpose**: Show buffer operation UI  
**Key Message**: "Easy buffer operations"

### Setup

**Layers**:
- `metro_stations` layer active (12 features)
- Zoom: Show central Paris 10th area

**FilterMate State**:
- Buffer Operations tab selected
- Clean state

### Storyboard

| Time | Frame | Action | Visual | Annotation |
|------|-------|--------|--------|------------|
| 0:00 | 1 | Initial view | Metro stations as points | "12 metro stations" |
| 0:01 | 2 | Click Buffer tab | Buffer Operations tab active | Tab highlights |
| 0:02 | 3 | Buffer panel visible | Shows: distance slider, unit dropdown, style | |
| 0:03 | 4 | Adjust distance slider | Slider moves: 0 → 300 meters | Value updates |
| 0:04 | 5 | Preview starts | Semi-transparent buffers appear | "Preview mode" |
| 0:05 | 6 | Continue sliding | Slider continues: 300 → 500 meters | Buffers grow |
| 0:06 | 7 | Final distance | Slider at 500 meters | "500m" badge |
| 0:07 | 8 | Click Apply Buffer | Apply button pressed | |
| 0:08 | 9 | Buffers created | Solid buffer polygons appear | "12 buffers created" |
| 0:09 | 10 | Select buffer style | Dropdown: Fill, Outline, Both | "Outline" selected |
| 0:10 | 11 | Style applied | Buffers change to outline style | Visual difference |

### Recording Notes

- **Smooth slider movement** (not jerky)
- **Real-time preview** is key feature to emphasize
- **Show scale** of buffers relative to features
- **Demonstrate** style options

### Post-Processing

1. Add distance indicator:
   - Frames 4-7: Distance label follows slider thumb
   - Frame 7: Enlarge "500m" label

2. Add buffer visualization:
   - Frame 5: Add "Preview" badge (orange)
   - Frame 9: Add "Applied" badge (green)

3. Add annotations:
   - Frame 3: "Adjust buffer distance"
   - Frame 9: "✓ Buffers created as new layer"

### Expected Output

```
buffer-distance.gif
Size: 1.2-1.5 MB
Dimensions: 1280x720
Duration: 10s
Frames: ~150 frames @ 15fps
```

---

## GIF 6: Backend Switch (backend-switch.gif)

**Duration**: 8 seconds  
**Purpose**: Show backend auto-detection and manual switch  
**Key Message**: "Flexible backend support"

### Setup

**Layers**:
- `buildings` layer from PostgreSQL (3,199 features)
- Backend indicator showing "PostgreSQL"

**FilterMate State**:
- Settings/Config tab visible
- Backend section expanded

### Storyboard

| Time | Frame | Action | Visual | Annotation |
|------|-------|--------|--------|------------|
| 0:00 | 1 | Initial state | Backend indicator: "PostgreSQL ⚡" | "Optimal backend" |
| 0:01 | 2 | Click Settings icon | Settings/gear icon pressed | |
| 0:02 | 3 | Settings panel opens | Backend options visible | |
| 0:03 | 4 | Backend section | Shows: Auto-detect toggle, Manual dropdown | Toggle ON (green) |
| 0:04 | 5 | Toggle Auto-detect OFF | Toggle switches to OFF position | Toggle gray |
| 0:05 | 6 | Manual dropdown enabled | Dropdown becomes active (not grayed) | |
| 0:06 | 7 | Click dropdown | Dropdown opens: PostgreSQL, Spatialite, QGIS | |
| 0:07 | 8 | Select QGIS Processing | "QGIS Processing" selected | |
| 0:08 | 9 | Backend changed | Backend indicator updates: "QGIS Processing" | Warning: "Slower" |
| 0:08 | 10 | Final state | Manual backend mode active | Info tooltip |

### Recording Notes

- **Clear contrast** between Auto and Manual modes
- **Show** backend indicator changes
- **Include** performance hint (QGIS slower than PostgreSQL)
- **Brief pause** on final state to read tooltip

### Post-Processing

1. Add status badges:
   - Frame 1: "Auto ✓" badge on indicator
   - Frame 9: "Manual ⚙" badge on indicator

2. Add comparison overlay:
   - Frame 1: "PostgreSQL: Fast ⚡"
   - Frame 9: "QGIS: Compatible ⚠️"

3. Add annotations:
   - Frame 4: "Auto-detect (recommended)"
   - Frame 7: "Manual override available"

### Expected Output

```
backend-switch.gif
Size: 0.8-1.0 MB
Dimensions: 1280x720
Duration: 8s
Frames: ~120 frames @ 15fps
```

---

## Production Workflow

### Pre-Production Checklist

- [ ] Install ScreenToGif (or alternative)
- [ ] Generate paris_10th.gpkg dataset
- [ ] Load dataset in QGIS with styles
- [ ] Position FilterMate dockwidget consistently
- [ ] Set QGIS window to 1920x1080
- [ ] Clean workspace (hide unnecessary panels)
- [ ] Prepare expression text in advance
- [ ] Test each action sequence 2-3 times

### Recording Process

1. **Open ScreenToGif**
   - Click "Recorder"
   - Select recording area: 1280x720
   - Position over QGIS window
   - Set FPS to 15

2. **Record**
   - Click Record button (or F7)
   - Perform action sequence (slowly and deliberately)
   - Click Stop (or F8)

3. **Edit**
   - Delete unnecessary frames (start/end)
   - Add delays (pause frames) where needed
   - Reduce framerate of slow sections
   - Crop to remove borders

4. **Annotate**
   - Add text overlays (white text, black outline)
   - Add arrows/circles (yellow or red)
   - Add callout bubbles for explanations
   - Keep annotations simple and minimal

5. **Optimize**
   - Reduce colors (128 or 64 colors)
   - Remove duplicate frames
   - Apply lossy compression
   - Target: <2 MB

6. **Export**
   - Format: GIF
   - Encoder: FFmpeg (best compression)
   - File name: as specified above
   - Test in browser

### Post-Production Tools

**ScreenToGif Built-in Editor**:
- Crop, resize, rotate
- Add text, drawings, watermarks
- Optimize (reduce colors, remove duplicates)
- Export to GIF, video, or frames

**Alternative: ezgif.com** (web-based):
- Upload GIF
- Optimize → Reduce colors, remove frames
- Effects → Add text, crop
- Download optimized GIF

**Alternative: GIMP** (advanced):
- Open GIF as layers
- Edit each frame
- Add annotations
- Export as optimized GIF

### Quality Assurance

- [ ] File size <2 MB
- [ ] Resolution: 1280x720
- [ ] Duration: within spec (±1s)
- [ ] Smooth playback (no jerky movements)
- [ ] Annotations visible and readable
- [ ] Colors accurate (not over-compressed)
- [ ] Loops seamlessly (if looped)
- [ ] Text readable at 50% zoom
- [ ] Mouse cursor visible (when relevant)
- [ ] No sensitive data visible

---

## Embedding in Documentation

### Markdown Syntax

```markdown
<!-- docs/user-guide/filtering-basics.md -->

## Applying Your First Filter

Follow these simple steps to apply a filter:

![Apply Filter](../../static/img/gifs/apply-filter.gif)

1. Select your layer in the Layers panel
2. Type your filter expression (e.g., `"area_m2" > 500`)
3. Click the green **Apply** button
4. See your filtered results instantly!
```

### HTML with Fallback

```html
<!-- For more control -->
<div class="gif-container">
  <img 
    src="/img/gifs/apply-filter.gif" 
    alt="Apply filter demonstration"
    loading="lazy"
    style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"
  />
  <p class="caption">Applying a filter to show only large buildings (&gt;500m²)</p>
</div>
```

### Docusaurus Admonition

```markdown
:::tip Interactive Demo

Watch this 10-second demo to see how easy filtering is:

![Apply Filter](../../static/img/gifs/apply-filter.gif)

**Try it yourself** with the sample data!

:::
```

---

## File Organization

```
website/
└── static/
    └── img/
        └── gifs/
            ├── apply-filter.gif          (1.2-1.5 MB)
            ├── undo-redo.gif             (1.0-1.2 MB)
            ├── export-workflow.gif       (1.8-2.0 MB)
            ├── geometric-filter.gif      (1.8-2.0 MB)
            ├── buffer-distance.gif       (1.2-1.5 MB)
            └── backend-switch.gif        (0.8-1.0 MB)
            
            Total: ~9 MB (6 files)
```

---

## Accessibility Considerations

### Alt Text

Provide descriptive alt text for each GIF:

```markdown
![FilterMate interface showing the apply filter workflow: typing an expression in the filter field, clicking the Apply button, and seeing the map update with filtered results](apply-filter.gif)
```

### Text Alternatives

Always accompany GIFs with written instructions:

```markdown
## Applying a Filter

**Watch**: [Apply Filter GIF]

**Steps**:
1. Click in the expression field
2. Type your filter: `"area_m2" > 500`
3. Click **Apply** button
4. View filtered results

**Result**: Map shows only features matching your criteria.
```

### Performance

- Use `loading="lazy"` for GIFs below fold
- Consider WebP format for modern browsers
- Provide video alternative for long GIFs

---

## Timeline Estimate

| Task | Duration | Notes |
|------|----------|-------|
| Setup (QGIS + data) | 30 min | One-time setup |
| Recording (6 GIFs) | 2 hours | ~20 min per GIF |
| Editing & Annotations | 2 hours | ~20 min per GIF |
| Optimization | 1 hour | ~10 min per GIF |
| Testing & QA | 30 min | Verify all GIFs |
| Documentation embed | 1 hour | Add to docs |
| **TOTAL** | **7 hours** | Phase 2 core task |

---

## Success Criteria

- [ ] 6 GIFs created and optimized
- [ ] All GIFs <2 MB each
- [ ] Smooth playback at 15 fps
- [ ] Annotations clear and professional
- [ ] Embedded in documentation
- [ ] Alt text provided
- [ ] Tested on desktop and mobile
- [ ] User feedback positive

---

**Next Steps**: Execute recording workflow using this storyboard guide.

**Tools Ready**: ScreenToGif installed, QGIS configured, sample data loaded.

**Expected Outcome**: 6 professional GIF animations showcasing FilterMate's key features.

---

*Generated: December 2025*  
*FilterMate Version: v2.3.7*  
*Document Version: 1.0.0*
