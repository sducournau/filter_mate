---
sidebar_position: 9
---

# Workflows & Process Diagrams

This guide provides detailed workflow diagrams for FilterMate's core operations, helping you understand the complete process from user action to result.

## 🔍 Basic Filtering Workflow

### Simple Geometric Filtering

This is the most common workflow: filtering layers based on spatial relationships.

```mermaid
sequenceDiagram
    participant U as User
    participant UI as FilterMate UI
    participant App as FilterMateApp
    participant Task as FilterEngineTask
    participant Backend as Backend (Auto-Selected)
    participant Layer as QGIS Layer

    U->>UI: 1. Select source layer
    U->>UI: 2. Select target layers (multi-select)
    U->>UI: 3. Choose spatial predicate<br/>(intersects, contains, within...)
    U->>UI: 4. Set buffer distance (optional)
    U->>UI: 5. Click "Filter" button
    
    UI->>App: launchingTask('filter', parameters)
    App->>App: Validate parameters
    App->>Task: Create FilterEngineTask
    
    Task->>Backend: Get optimal backend
    Backend->>Backend: Detect provider type
    
    alt PostgreSQL Available
        Backend->>Backend: Create materialized view
        Backend->>Backend: Build GIST spatial index
        Note over Backend: ~1s for 1M features
    else Spatialite Source
        Backend->>Backend: Create temporary table
        Backend->>Backend: Build R-tree index
        Note over Backend: ~5s for 100k features
    else OGR/Shapefile
        Backend->>Backend: QGIS Processing
        Backend->>Backend: Memory layer operations
        Note over Backend: ~30s for 100k features
    end
    
    Backend-->>Task: Filtered feature IDs
    Task-->>App: taskCompleted signal
    App->>Layer: setSubsetString(expression)
    Layer-->>U: ✅ Layers filtered on map canvas
    
    Note over U,Layer: Filter applied instantly, no data modification
```

### Key Points

- **Non-destructive**: Original data never modified
- **Reversible**: Clear filter button restores all features
- **Fast**: Backend automatically optimized for data source
- **Visual**: Results appear immediately on map

---

## 📤 Export Workflow

### Export with CRS Reprojection

```mermaid
flowchart TD
    Start[User: Export Filtered Features] --> CheckFilter{Features<br/>filtered?}
    
    CheckFilter -->|No| WarnNoFilter[⚠️ Warning: Export all features?]
    CheckFilter -->|Yes| GetCount[Get filtered count]
    WarnNoFilter --> Confirm{User confirms?}
    Confirm -->|No| Cancel[❌ Cancel export]
    Confirm -->|Yes| GetCount
    
    GetCount --> SelectFormat{Choose format}
    SelectFormat -->|GeoPackage| GPKG[GPKG format]
    SelectFormat -->|Shapefile| SHP[Shapefile format]
    SelectFormat -->|GeoJSON| JSON[GeoJSON format]
    SelectFormat -->|Other| Other[KML/DXF/CSV]
    
    GPKG --> SelectFields[Select fields to export]
    SHP --> SelectFields
    JSON --> SelectFields
    Other --> SelectFields
    
    SelectFields --> CheckCRS{Target CRS<br/>different?}
    
    CheckCRS -->|Yes| Reproject[Automatic reprojection]
    CheckCRS -->|No| DirectExport[Direct export]
    
    Reproject --> CheckStyle{Export style?}
    DirectExport --> CheckStyle
    
    CheckStyle -->|QML| AddQML[Include QML style file]
    CheckStyle -->|SLD| AddSLD[Include SLD style file]
    CheckStyle -->|None| NoStyle[No style export]
    
    AddQML --> Execute[Execute export task]
    AddSLD --> Execute
    NoStyle --> Execute
    
    Execute --> Progress[Show progress bar]
    Progress --> Success{Export<br/>successful?}
    
    Success -->|Yes| Complete[✅ Export complete<br/>File saved]
    Success -->|No| Error[❌ Error: Check logs]
    
    Complete --> AddToMap{Add to<br/>QGIS project?}
    AddToMap -->|Yes| LoadLayer[Load exported layer]
    AddToMap -->|No| Done[Done]
    LoadLayer --> Done
    
    style Complete fill:#51cf66
    style Error fill:#ff6b6b
    style Done fill:#51cf66
```

### Export Configuration Options

```mermaid
graph LR
    Export[Export Configuration] --> Format[Format Selection]
    Export --> Fields[Field Selection]
    Export --> CRS[CRS Transformation]
    Export --> Style[Style Export]
    
    Format --> F1[GeoPackage]
    Format --> F2[Shapefile]
    Format --> F3[GeoJSON]
    Format --> F4[KML]
    Format --> F5[DXF]
    Format --> F6[CSV]
    
    Fields --> FA[All fields]
    Fields --> FB[Selected fields only]
    
    CRS --> C1[Keep source CRS]
    CRS --> C2[Reproject to target]
    CRS --> C3[Common CRS<br/>EPSG:4326]
    
    Style --> S1[QML - QGIS]
    Style --> S2[SLD - Standards]
    Style --> S3[None]
    
    style Export fill:#4299e1
```

---

## 🔄 Filter History Navigation

### Undo/Redo Mechanism

```mermaid
stateDiagram-v2
    [*] --> NoFilter: Initial state
    
    NoFilter --> Filter1: Apply filter A
    Filter1 --> Filter2: Apply filter B
    Filter2 --> Filter3: Apply filter C
    
    Filter3 --> Filter2: Undo
    Filter2 --> Filter1: Undo
    Filter1 --> NoFilter: Undo
    
    Filter1 --> Filter2: Redo
    Filter2 --> Filter3: Redo
    
    Filter2 --> Filter4: Apply new filter D
    note right of Filter4: Redo history cleared<br/>after new filter
    
    Filter4 --> [*]: Clear all filters
    
    NoFilter --> [*]: Close plugin
```

### Filter History Timeline

```mermaid
gitGraph
    commit id: "No filter"
    commit id: "Population > 10000" tag: "Filter 1"
    branch experiment
    commit id: "Add buffer 100m" tag: "Test A"
    commit id: "Intersects roads" tag: "Test B"
    checkout main
    commit id: "Area > 5000" tag: "Filter 2"
    merge experiment tag: "Merge best config"
    commit id: "Final filter" tag: "Approved"
```

**Use Cases:**
- 🔄 Test different filter parameters
- 🎯 Compare alternative scenarios
- ↩️ Quick rollback to previous state
- 💾 Reproducible analysis workflow

---

## 🔧 Backend Selection Logic

### Automatic Backend Decision Tree

```mermaid
flowchart TD
    Start[Layer loaded in FilterMate] --> DetectProvider{Detect<br/>Provider Type}
    
    DetectProvider -->|postgres| CheckPsycopg{psycopg2<br/>installed?}
    DetectProvider -->|spatialite| UseSpatialite[Spatialite Backend]
    DetectProvider -->|ogr| UseOGR[OGR Backend]
    DetectProvider -->|other| UseOGR
    
    CheckPsycopg -->|Yes ✅| UsePostgres[PostgreSQL Backend]
    CheckPsycopg -->|No ❌| ShowWarning[⚠️ Warning:<br/>Install psycopg2<br/>for better performance]
    
    ShowWarning --> CheckSize{Dataset size}
    CheckSize -->|> 50k features| Recommend[Strongly recommend<br/>PostgreSQL]
    CheckSize -->|< 50k features| UseSpatialiteAlt[Use Spatialite<br/>as fallback]
    
    Recommend --> UseSpatialiteAlt
    
    UsePostgres --> PG_Features[• Materialized views<br/>• GIST indexes<br/>• Sub-second queries<br/>• Million+ features]
    UseSpatialite --> SL_Features[• Temp tables<br/>• R-tree indexes<br/>• Good for 10k-50k<br/>• Built-in support]
    UseOGR --> OGR_Features[• QGIS Processing<br/>• Memory layers<br/>• Universal compatibility<br/>• Slower on large data]
    
    PG_Features --> Execute[Execute filtering]
    SL_Features --> Execute
    OGR_Features --> Execute
    
    Execute --> Result[✅ Filtered results]
    
    style UsePostgres fill:#51cf66
    style UseSpatialite fill:#ffd43b
    style UseOGR fill:#74c0fc
    style Result fill:#51cf66
```

### Performance Comparison by Backend

```mermaid
gantt
    title Filtering Time: 100,000 Features
    dateFormat X
    axisFormat %Ss
    
    section PostgreSQL
    Query execution: 0, 1
    
    section Spatialite
    Query execution: 0, 5
    
    section OGR
    Query execution: 0, 30
```

---

## 🎨 Configuration Update Workflow (v2.2.2+)

### Real-Time Configuration Reactivity

```mermaid
sequenceDiagram
    participant U as User
    participant JSON as JSON Tree View
    participant Handler as Config Handler
    participant UI as FilterMate UI
    participant Config as config.json
    participant QGIS as QGIS
    
    U->>JSON: Click dropdown (UI_PROFILE)
    JSON->>JSON: Show choices:<br/>auto, compact, normal
    U->>JSON: Select "compact"
    
    JSON->>Handler: itemChanged signal
    Handler->>Handler: Extract new value
    Handler->>Handler: Validate (ChoicesType)
    
    alt UI_PROFILE changed
        Handler->>UI: update_dimensions()
        UI->>UI: Recalculate all dimensions
        UI->>UI: Apply compact sizes
        Note over UI: Instant visual update!
    else ACTIVE_THEME changed
        Handler->>UI: apply_theme()
        UI->>UI: Load theme QSS
        UI->>UI: Update all widgets
    else THEME_SOURCE changed
        Handler->>QGIS: Detect QGIS theme
        QGIS-->>Handler: Current theme
        Handler->>UI: Sync theme
    end
    
    Handler->>Config: Auto-save changes
    Config-->>U: ✅ Success notification
    
    Note over U,QGIS: No restart required!
```

### Theme Synchronization States

```mermaid
stateDiagram-v2
    [*] --> DetectSource: Plugin starts
    
    DetectSource --> ConfigMode: THEME_SOURCE = "config"
    DetectSource --> QGISMode: THEME_SOURCE = "qgis"
    DetectSource --> SystemMode: THEME_SOURCE = "system"
    
    ConfigMode --> ReadConfig: Read ACTIVE_THEME
    ReadConfig --> LightTheme: theme = "light"
    ReadConfig --> DarkTheme: theme = "dark"
    ReadConfig --> AutoTheme: theme = "auto"
    
    QGISMode --> DetectQGIS: Detect QGIS theme
    DetectQGIS --> BlendOfGray: Blend of Gray
    DetectQGIS --> NightMapping: Night Mapping
    DetectQGIS --> DefaultTheme: Default
    
    SystemMode --> DetectSystem: Query OS theme
    DetectSystem --> SystemLight: Light mode
    DetectSystem --> SystemDark: Dark mode
    
    BlendOfGray --> LightTheme
    DefaultTheme --> LightTheme
    NightMapping --> DarkTheme
    SystemLight --> LightTheme
    SystemDark --> DarkTheme
    
    AutoTheme --> DetectTime: Check time
    DetectTime --> LightTheme: 6:00-18:00
    DetectTime --> DarkTheme: 18:00-6:00
    
    LightTheme --> ApplyLight: Apply light QSS
    DarkTheme --> ApplyDark: Apply dark QSS
    
    ApplyLight --> [*]: UI rendered
    ApplyDark --> [*]: UI rendered
    
    note right of QGISMode: Default mode<br/>Auto-sync with QGIS
```

---

## 🔍 Feature Exploration Workflow

### Interactive Feature Selection

```mermaid
flowchart TD
    Start[User opens Exploring frame] --> LoadLayer[Load current layer]
    LoadLayer --> PopulateTask[Launch PopulateListEngineTask]
    
    PopulateTask --> Background[Async: Load features]
    Background --> GetFeatures[Query layer features]
    GetFeatures --> BuildList[Build feature list]
    BuildList --> ApplyExpr{Display<br/>expression set?}
    
    ApplyExpr -->|Yes| FormatList[Format: display_expression]
    ApplyExpr -->|No| DefaultList[Format: Feature ID]
    
    FormatList --> ShowList[Show in combobox]
    DefaultList --> ShowList
    
    ShowList --> UserSelect{User action}
    
    UserSelect -->|Single select| SingleMode[Single selection mode]
    UserSelect -->|Multi select| MultiMode[Multiple selection mode]
    UserSelect -->|Search| SearchMode[Filter list]
    
    SingleMode --> Expression1[Generate expression:<br/>fid = 123]
    MultiMode --> Expression2[Generate expression:<br/>fid IN (1,2,3...)]
    SearchMode --> FilterList[Filter combobox items]
    
    Expression1 --> ApplyHighlight[Highlight on map]
    Expression2 --> ApplyHighlight
    FilterList --> ShowList
    
    ApplyHighlight --> UseAsFilter{Use as<br/>filter source?}
    
    UseAsFilter -->|Yes| FilterOthers[Filter other layers<br/>based on selection]
    UseAsFilter -->|No| Done[Done: Visual only]
    
    FilterOthers --> Done
    
    style Done fill:#51cf66
```

---

## 🚀 Performance Optimization Workflow

### Large Dataset Handling

```mermaid
flowchart TD
    Start[User loads layer] --> CheckCount{Feature count}
    
    CheckCount -->|< 10k| Small[Small dataset]
    CheckCount -->|10k - 50k| Medium[Medium dataset]
    CheckCount -->|> 50k| Large[Large dataset]
    
    Small --> AnyBackend[All backends OK]
    AnyBackend --> NoWarning[No performance warning]
    
    Medium --> CheckBackend1{Backend type}
    CheckBackend1 -->|PostgreSQL| Optimal1[✅ Optimal performance]
    CheckBackend1 -->|Spatialite| Good1[✅ Good performance]
    CheckBackend1 -->|OGR| Warn1[⚠️ Recommend Spatialite]
    
    Large --> CheckBackend2{Backend type}
    CheckBackend2 -->|PostgreSQL| Optimal2[✅ Optimal: < 1s]
    CheckBackend2 -->|Spatialite| Acceptable[⚠️ Acceptable: 5-10s]
    CheckBackend2 -->|OGR| Critical[❌ Critical: > 30s]
    
    Critical --> Recommend[Recommend actions:<br/>1. Install psycopg2<br/>2. Convert to PostgreSQL<br/>3. Reduce dataset]
    
    Warn1 --> MinorWarn[Show info message]
    Acceptable --> MinorWarn
    
    Optimal1 --> Proceed[Proceed with filtering]
    Good1 --> Proceed
    NoWarning --> Proceed
    Optimal2 --> Proceed
    MinorWarn --> Proceed
    
    Recommend --> UserChoice{User choice}
    UserChoice -->|Install PostgreSQL| Install[Follow installation guide]
    UserChoice -->|Continue anyway| SlowProceed[⏳ Proceed with warning]
    UserChoice -->|Cancel| Cancel[Cancel operation]
    
    Install --> Proceed
    SlowProceed --> Proceed
    
    Proceed --> Execute[Execute filter task]
    Execute --> Monitor[Monitor progress]
    Monitor --> Success[✅ Complete]
    
    style Success fill:#51cf66
    style Cancel fill:#ff6b6b
    style Critical fill:#ff6b6b
```

---

## 📚 Workflow Patterns Summary

### Common Workflow Types

| Workflow | Complexity | Duration | Key Steps |
|----------|------------|----------|-----------|
| Simple geometric filter | Low | 30 seconds | Select layers → Choose predicate → Filter |
| Buffer analysis | Medium | 1-2 minutes | Select source → Set buffer → Filter → Review |
| Multi-criteria filter | High | 5-10 minutes | Multiple filters → Test alternatives → Refine → Export |
| Export with reprojection | Medium | 1-3 minutes | Filter → Choose format → Set CRS → Export |
| Iterative analysis | High | 10-30 minutes | Filter → Review → Undo → Adjust → Repeat |

### Best Practices by Workflow

**Quick Filtering (< 1 minute)**
- ✅ Use single geometric predicate
- ✅ Pre-filtered source layer
- ✅ PostgreSQL backend for speed

**Exploratory Analysis (5-15 minutes)**
- ✅ Use filter history for testing
- ✅ Save intermediate results
- ✅ Document successful parameters

**Production Workflows (repeatable)**
- ✅ Save expressions in project
- ✅ Create export templates
- ✅ Document process steps

**Team Collaboration**
- ✅ Export configuration JSON
- ✅ Share filter expressions
- ✅ Standardize naming conventions

---

## 🎯 Next Steps

- **Learn by doing**: Try the [Quick Start Tutorial](../getting-started/quick-start.md)
- **See real examples**: Check [User Stories](./user-stories.md)
- **Optimize performance**: Read [Backend Selection Guide](../backends/backend-selection.md)
- **Advanced techniques**: Explore [Advanced Features](./advanced-features.md)

Have questions about a specific workflow? [Open an issue on GitHub](https://github.com/sducournau/filter_mate/issues) for support.
