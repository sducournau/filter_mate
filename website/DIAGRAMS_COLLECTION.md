# FilterMate Documentation Diagrams Collection

**Date**: December 8, 2025
**Purpose**: Mermaid diagram templates for documentation update

---

## 1. Backend Selection Flow (Priority 1)

**Target File**: `backends/backend-selection.md`
**Purpose**: Show how FilterMate automatically selects the optimal backend

```mermaid
flowchart TD
    Start([Layer Added to QGIS]) --> Detect{Detect<br/>Provider Type}
    
    Detect -->|postgres| CheckPsycopg{psycopg2<br/>installed?}
    Detect -->|spatialite| Spatialite[Spatialite Backend]
    Detect -->|ogr/other| OGR[OGR Backend]
    
    CheckPsycopg -->|Yes| PostgreSQL[PostgreSQL Backend<br/>⚡ Optimal Performance]
    CheckPsycopg -->|No| CheckSize{Feature<br/>Count?}
    
    CheckSize -->|> 50,000| Warning[⚠️ Performance Warning<br/>Recommend psycopg2]
    CheckSize -->|< 50,000| Spatialite
    
    Warning --> Spatialite
    
    PostgreSQL --> Features1[✓ Materialized Views<br/>✓ Server-side Processing<br/>✓ GIST Indexes]
    Spatialite --> Features2[✓ Temporary Tables<br/>✓ R*Tree Indexes<br/>✓ Local Processing]
    OGR --> Features3[✓ Universal Compatibility<br/>✓ Memory Layers<br/>✓ QGIS Processing]
    
    Features1 --> End([Backend Active])
    Features2 --> End
    Features3 --> End
    
    classDef optimal fill:#90EE90,stroke:#2d6a2d,stroke-width:2px
    classDef good fill:#87CEEB,stroke:#1e5f8f,stroke-width:2px
    classDef fallback fill:#FFD700,stroke:#b8860b,stroke-width:2px
    classDef warning fill:#FF6347,stroke:#8b0000,stroke-width:2px
    
    class PostgreSQL,Features1 optimal
    class Spatialite,Features2 good
    class OGR,Features3 fallback
    class Warning warning
```

---

## 2. Multi-Backend Architecture (Priority 1)

**Target File**: `backends/overview.md`
**Purpose**: Show class hierarchy and backend inheritance

```mermaid
classDiagram
    class GeometricFilterBackend {
        <<abstract>>
        +layer: QgsVectorLayer
        +source_layer_id: str
        +expression: str
        +apply_geometric_filter()*
        +create_filtered_layer()*
        +supports_buffer()
        +supports_predicates()
        +get_capabilities()
        +cleanup()
    }
    
    class PostgresqlBackend {
        +conn: psycopg2.connection
        +schema: str
        +use_materialized_view: bool
        +apply_geometric_filter()
        +create_materialized_view()
        +refresh_view()
        +get_server_version()
        +supports_buffer() ✓
        +supports_predicates() ✓
    }
    
    class SpatialiteBackend {
        +db_path: str
        +conn: sqlite3.connection
        +temp_table_prefix: str
        +apply_geometric_filter()
        +create_temp_table()
        +create_spatial_index()
        +vacuum_analyze()
        +supports_buffer() ✓
        +supports_predicates() ✓
    }
    
    class OgrBackend {
        +source_format: str
        +memory_layer: QgsVectorLayer
        +apply_geometric_filter()
        +create_memory_layer()
        +copy_features()
        +supports_buffer() Limited
        +supports_predicates() Limited
    }
    
    class BackendFactory {
        <<factory>>
        +get_backend(layer) Backend
        +detect_provider(layer) str
        +check_postgresql_available() bool
        +recommend_backend(layer) str
    }
    
    GeometricFilterBackend <|-- PostgresqlBackend : inherits
    GeometricFilterBackend <|-- SpatialiteBackend : inherits
    GeometricFilterBackend <|-- OgrBackend : inherits
    
    BackendFactory ..> GeometricFilterBackend : creates
    BackendFactory ..> PostgresqlBackend : instantiates
    BackendFactory ..> SpatialiteBackend : instantiates
    BackendFactory ..> OgrBackend : instantiates
```

---

## 3. Filter Operation Data Flow (Priority 1)

**Target File**: `developer-guide/architecture.md`
**Purpose**: Show complete filtering workflow from user action to result

```mermaid
sequenceDiagram
    actor User
    participant UI as FilterMateDockWidget
    participant App as FilterMateApp
    participant Task as FilterEngineTask
    participant Factory as BackendFactory
    participant Backend
    participant DB as Database/File
    participant QGIS
    
    User->>UI: 1. Configure filter options
    User->>UI: 2. Click "Apply Filter"
    
    UI->>App: 3. manage_task('filter')
    Note over App: Validates parameters<br/>Checks layer state
    
    App->>Task: 4. Create FilterEngineTask
    activate Task
    
    Task->>Factory: 5. get_backend(layer)
    Factory->>Factory: Detect provider type
    Factory->>Factory: Check capabilities
    Factory-->>Task: Return optimal backend
    
    Task->>Backend: 6. apply_geometric_filter(params)
    activate Backend
    
    Backend->>Backend: 7. Build spatial query
    Note over Backend: Convert QGIS expression<br/>Add geometric predicates<br/>Apply buffer if needed
    
    Backend->>DB: 8. Execute query
    activate DB
    DB-->>Backend: Query result
    deactivate DB
    
    Backend->>Backend: 9. Create filtered view/table
    Backend->>QGIS: 10. Create temporary layer
    
    Backend-->>Task: Filtered layer ready
    deactivate Backend
    
    Task-->>App: 11. Task completed signal
    deactivate Task
    
    App->>UI: 12. Update UI state
    App->>QGIS: 13. Add layer to project
    
    QGIS->>User: 14. Display filtered results
    
    Note over User,QGIS: Filter applied successfully ✓
```

---

## 4. Performance Comparison Visualization (Priority 1)

**Target File**: `backends/performance-comparison.md`
**Purpose**: Visual decision matrix for backend selection

```mermaid
graph TD
    Start([Dataset Size?]) --> Size1{< 10k features}
    Start --> Size2{10k - 50k}
    Start --> Size3{50k - 500k}
    Start --> Size4{> 500k}
    
    Size1 --> AllEqual[All Backends<br/>~Equal Performance<br/>⚡ < 1 second]
    
    Size2 --> Optimal1[Spatialite Optimal<br/>✓ Fast<br/>✓ No setup required]
    Size2 -.Postgres OK.-> PG1[PostgreSQL Also Good<br/>If already configured]
    
    Size3 --> Recommended[PostgreSQL Recommended<br/>✓ 2-5x faster<br/>✓ Server-side processing]
    Size3 -.Spatialite OK.-> SP1[Spatialite Acceptable<br/>⚠️ May be slower]
    
    Size4 --> Required[PostgreSQL Required<br/>✓ Only viable option<br/>✓ Sub-second queries]
    Size4 -.Warning.-> Warn[Spatialite/OGR<br/>❌ Very slow<br/>⚠️ May timeout]
    
    classDef optimal fill:#90EE90,stroke:#2d6a2d,stroke-width:3px
    classDef recommended fill:#87CEEB,stroke:#1e5f8f,stroke-width:3px
    classDef acceptable fill:#FFD700,stroke:#b8860b,stroke-width:2px
    classDef warning fill:#FF6347,stroke:#8b0000,stroke-width:2px
    
    class AllEqual,Optimal1 optimal
    class Recommended,PG1 recommended
    class SP1 acceptable
    class Required optimal
    class Warn warning
```

### Performance Metrics Table

| Dataset Size | PostgreSQL | Spatialite | OGR | Recommendation |
|--------------|-----------|-----------|-----|----------------|
| < 10k | ~0.5s ⚡ | ~0.5s ⚡ | ~0.8s ⚡ | Any backend |
| 10k - 50k | ~1s ⚡ | ~2s ⚡ | ~5s 🐌 | Spatialite |
| 50k - 500k | ~2s ⚡ | ~10s 🐌 | ~30s 🐌 | **PostgreSQL** |
| > 500k | ~3s ⚡ | ~60s+ 🐌 | Timeout ❌ | **PostgreSQL only** |

---

## 5. Configuration System Architecture (Priority 2)

**Target File**: `advanced/configuration.md`
**Purpose**: Show reactive configuration system

```mermaid
graph TB
    subgraph "Configuration Layer"
        ConfigJSON[config.json<br/>📄 Source of Truth]
        ConfigManager[ConfigManager<br/>🔧 Parser & Validator]
    end
    
    subgraph "UI Layer"
        JsonView[QtJsonView<br/>🎨 Visual Editor]
        ChoicesType[ChoicesType Dropdowns<br/>📋 Validated Selectors]
        Widgets[UI Widgets<br/>🖥️ Dynamic Controls]
    end
    
    subgraph "Reactive System"
        SignalManager[Signal Manager<br/>📡 Change Detection]
        AutoSave[Auto-save Handler<br/>💾 Persistence]
        LiveUpdate[Live Update Engine<br/>⚡ Instant Apply]
    end
    
    subgraph "Application Systems"
        ThemeSystem[Theme System<br/>🎨 Colors & Styles]
        LayoutEngine[Layout Engine<br/>📐 UI Profiles]
        IconManager[Icon Manager<br/>🖼️ Dynamic Icons]
    end
    
    ConfigJSON --> ConfigManager
    ConfigManager --> JsonView
    ConfigManager --> ChoicesType
    ConfigManager --> Widgets
    
    JsonView --> SignalManager
    ChoicesType --> SignalManager
    Widgets --> SignalManager
    
    SignalManager --> AutoSave
    SignalManager --> LiveUpdate
    
    LiveUpdate --> ThemeSystem
    LiveUpdate --> LayoutEngine
    LiveUpdate --> IconManager
    
    AutoSave --> ConfigJSON
    
    classDef config fill:#E8F4F8,stroke:#0288D1,stroke-width:2px
    classDef ui fill:#FFF9C4,stroke:#F57F17,stroke-width:2px
    classDef reactive fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    classDef system fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    
    class ConfigJSON,ConfigManager config
    class JsonView,ChoicesType,Widgets ui
    class SignalManager,AutoSave,LiveUpdate reactive
    class ThemeSystem,LayoutEngine,IconManager system
```

---

## 6. UI Profile Auto-Detection (Priority 2)

**Target File**: `advanced/configuration.md`
**Purpose**: Show automatic UI profile selection logic

```mermaid
flowchart TD
    Start([Plugin Initialization]) --> CheckConfig{UI_PROFILE<br/>setting?}
    
    CheckConfig -->|"auto"| DetectScreen[Detect Screen<br/>Resolution]
    CheckConfig -->|"compact"| ForceCompact[Force Compact Mode]
    CheckConfig -->|"normal"| ForceNormal[Force Normal Mode]
    
    DetectScreen --> GetWidth[Get Screen Width]
    DetectScreen --> GetHeight[Get Screen Height]
    
    GetWidth --> CheckThresholds{Width < 1920px<br/>OR<br/>Height < 1080px?}
    GetHeight --> CheckThresholds
    
    CheckThresholds -->|Yes| AutoCompact[Auto: Compact Mode<br/>📱 Small Screen]
    CheckThresholds -->|No| AutoNormal[Auto: Normal Mode<br/>🖥️ Large Screen]
    
    ForceCompact --> ApplyCompact[Apply Compact Layout]
    AutoCompact --> ApplyCompact
    
    ForceNormal --> ApplyNormal[Apply Normal Layout]
    AutoNormal --> ApplyNormal
    
    ApplyCompact --> CompactSettings[✓ Reduced padding<br/>✓ Smaller icons<br/>✓ Compact spacing<br/>✓ Optimized for < 1920x1080]
    
    ApplyNormal --> NormalSettings[✓ Standard padding<br/>✓ Larger icons<br/>✓ Comfortable spacing<br/>✓ Optimized for ≥ 1920x1080]
    
    CompactSettings --> Ready([UI Ready])
    NormalSettings --> Ready
    
    classDef auto fill:#87CEEB,stroke:#1e5f8f,stroke-width:2px
    classDef forced fill:#FFD700,stroke:#b8860b,stroke-width:2px
    classDef result fill:#90EE90,stroke:#2d6a2d,stroke-width:2px
    
    class DetectScreen,AutoCompact,AutoNormal auto
    class ForceCompact,ForceNormal forced
    class CompactSettings,NormalSettings result
```

---

## 7. Layer Addition Flow (Priority 2)

**Target File**: `developer-guide/architecture.md`
**Purpose**: Show complete layer addition workflow

```mermaid
flowchart TD
    UserAction([User adds layer<br/>to QGIS project]) --> QGISSignal[QGIS emits<br/>layersAdded signal]
    
    QGISSignal --> AppReceives[FilterMateApp<br/>receives signal]
    
    AppReceives --> CreateTask[Create<br/>LayersManagementEngineTask]
    
    CreateTask --> TaskStart[Task starts<br/>in background thread]
    
    subgraph "Background Processing"
        TaskStart --> Extract1[Extract layer metadata]
        Extract1 --> Extract2[Determine provider type<br/>postgres/spatialite/ogr]
        Extract2 --> Extract3[Get geometry type<br/>Point/Line/Polygon]
        Extract3 --> Extract4[Find primary key field]
        Extract4 --> Extract5[Collect field information<br/>names/types]
        Extract5 --> Extract6[Check capabilities]
    end
    
    Extract6 --> TaskComplete[Task completed signal]
    
    TaskComplete --> Callback[layer_management_engine<br/>_task_completed callback]
    
    Callback --> UpdateDict[Update PROJECT_LAYERS<br/>dictionary in memory]
    
    UpdateDict --> SaveDB[Store metadata in<br/>Spatialite database]
    
    SaveDB --> UpdateUI[Update FilterMateDockWidget]
    
    UpdateUI --> RefreshCombo[Refresh layer comboboxes]
    RefreshCombo --> UpdateCount[Update layer count display]
    UpdateCount --> ShowBackend[Show backend indicator]
    
    ShowBackend --> Ready([Layer ready<br/>for filtering])
    
    classDef qgis fill:#93C572,stroke:#4E8031,stroke-width:2px
    classDef task fill:#87CEEB,stroke:#1e5f8f,stroke-width:2px
    classDef storage fill:#FFD700,stroke:#b8860b,stroke-width:2px
    classDef ui fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    
    class UserAction,QGISSignal qgis
    class TaskStart,Extract1,Extract2,Extract3,Extract4,Extract5,Extract6 task
    class UpdateDict,SaveDB storage
    class UpdateUI,RefreshCombo,UpdateCount,ShowBackend ui
```

---

## 8. Theme System Architecture (Priority 2)

**Target File**: `themes/overview.md`
**Purpose**: Show complete theme system

```mermaid
graph TB
    subgraph "Theme Sources"
        ThemeConfig[config.json<br/>THEMES section]
        ThemeClasses[Theme Classes<br/>Python modules]
        QGIS[QGIS Theme API]
    end
    
    subgraph "Theme Manager"
        Detector[Theme Detector<br/>Auto/Manual Selection]
        Loader[Theme Loader<br/>Parse & Validate]
        Cache[Theme Cache<br/>Performance]
    end
    
    subgraph "Theme Application"
        QSSGenerator[QSS Generator<br/>Replace placeholders]
        ColorMapper[Color Mapper<br/>Map theme to widgets]
        StyleApplier[Style Applier<br/>setStyleSheet()]
    end
    
    subgraph "UI Components"
        Widgets[All Widgets]
        Frames[Frames & Containers]
        Buttons[Buttons & Controls]
        JsonView[JSON View Editor]
    end
    
    subgraph "Theme Features"
        ColorContrast[Color Contrast<br/>WCAG Compliance]
        Harmonization[Color Harmonization<br/>Visual Distinction]
        Accessibility[Accessibility<br/>17.4:1 ratio]
    end
    
    ThemeConfig --> Detector
    ThemeClasses --> Loader
    QGIS --> Detector
    
    Detector --> Loader
    Loader --> Cache
    
    Cache --> QSSGenerator
    QSSGenerator --> ColorMapper
    ColorMapper --> StyleApplier
    
    StyleApplier --> Widgets
    StyleApplier --> Frames
    StyleApplier --> Buttons
    StyleApplier --> JsonView
    
    ColorMapper --> ColorContrast
    ColorMapper --> Harmonization
    ColorMapper --> Accessibility
    
    classDef source fill:#E8F4F8,stroke:#0288D1,stroke-width:2px
    classDef manager fill:#FFF9C4,stroke:#F57F17,stroke-width:2px
    classDef application fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    classDef ui fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    classDef features fill:#D1C4E9,stroke:#7B1FA2,stroke-width:2px
    
    class ThemeConfig,ThemeClasses,QGIS source
    class Detector,Loader,Cache manager
    class QSSGenerator,ColorMapper,StyleApplier application
    class Widgets,Frames,Buttons,JsonView ui
    class ColorContrast,Harmonization,Accessibility features
```

---

## 9. Export Workflow (Priority 2)

**Target File**: `user-guide/export-features.md`
**Purpose**: Show export operation flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Export Tab
    participant App as FilterMateApp
    participant Task as ExportEngineTask
    participant Backend
    participant Writer as File Writer
    participant QGIS
    
    User->>UI: 1. Configure export options
    Note over User,UI: Select layers<br/>Choose format<br/>Set output folder
    
    User->>UI: 2. Click "Export"
    
    UI->>App: 3. manage_task('export')
    Note over App: Validate selections<br/>Check output path
    
    App->>Task: 4. Create ExportEngineTask
    activate Task
    
    loop For each layer
        Task->>Backend: 5. Get filtered features
        activate Backend
        Backend-->>Task: Feature collection
        deactivate Backend
        
        alt CRS Reprojection Needed
            Task->>Task: 6. Transform coordinates
            Note over Task: Source CRS → Target CRS
        end
        
        alt Style Export Enabled
            Task->>QGIS: 7. Get layer style
            QGIS-->>Task: QML style definition
        end
        
        Task->>Writer: 8. Write features to file
        activate Writer
        Note over Writer: Format: GeoPackage,<br/>Shapefile, GeoJSON, etc.
        Writer-->>Task: File created
        deactivate Writer
    end
    
    alt ZIP Archive Requested
        Task->>Task: 9. Create ZIP archive
        Note over Task: Compress all outputs
    end
    
    Task-->>App: 10. Export completed
    deactivate Task
    
    App->>UI: 11. Update status
    App->>User: 12. Success notification
    
    Note over User,QGIS: Export complete ✓
```

---

## 10. Filter History System (Priority 3)

**Target File**: `user-guide/filter-history.md`
**Purpose**: Show state management for undo/redo

```mermaid
stateDiagram-v2
    [*] --> NoHistory: Plugin starts
    
    NoHistory --> FirstFilter: Apply first filter
    
    FirstFilter --> HasHistory: Filter stored
    
    HasHistory --> MoreFilters: Apply another filter
    MoreFilters --> HasHistory: Store in history
    
    HasHistory --> UndoState: User clicks Undo
    UndoState --> PreviousFilter: Restore previous filter
    PreviousFilter --> CanRedo: History position updated
    
    CanRedo --> RedoState: User clicks Redo
    RedoState --> NextFilter: Restore next filter
    NextFilter --> HasHistory: History position updated
    
    HasHistory --> ClearHistory: User clears history
    ClearHistory --> NoHistory: All history removed
    
    CanRedo --> NewFilter: Apply new filter
    NewFilter --> HistoryBranch: Future history cleared
    HistoryBranch --> HasHistory: New branch created
    
    note right of HasHistory
        History stored as:
        - Filter expression
        - Layer ID
        - Timestamp
        - Parameters
    end note
    
    note right of CanRedo
        Can navigate:
        - Backward (Undo)
        - Forward (Redo)
        Max 50 entries
    end note
```

---

## 11. Testing Architecture (Priority 2)

**Target File**: `developer-guide/testing.md`
**Purpose**: Show test structure and workflow

```mermaid
graph TB
    subgraph "Test Categories"
        Unit[Unit Tests<br/>test_*.py]
        Integration[Integration Tests<br/>test_*_integration.py]
        Performance[Performance Tests<br/>test_performance.py]
        UI[UI Tests<br/>test_ui_*.py]
    end
    
    subgraph "Test Infrastructure"
        Pytest[Pytest Framework]
        Fixtures[Fixtures<br/>conftest.py]
        Mocks[Mock Objects<br/>QGIS mocks]
        Coverage[Coverage.py<br/>Code coverage]
    end
    
    subgraph "Test Execution"
        Local[Local Testing<br/>pytest command]
        CI[CI/CD Pipeline<br/>GitHub Actions]
        Reports[Coverage Reports<br/>HTML/XML]
    end
    
    subgraph "Test Areas"
        BackendTests[Backend Tests<br/>PostgreSQL/Spatialite/OGR]
        UtilTests[Utility Tests<br/>appUtils.py functions]
        ConfigTests[Config Tests<br/>Reactivity & validation]
        ThemeTests[Theme Tests<br/>Color & accessibility]
    end
    
    Unit --> Pytest
    Integration --> Pytest
    Performance --> Pytest
    UI --> Pytest
    
    Pytest --> Fixtures
    Pytest --> Mocks
    Pytest --> Coverage
    
    Fixtures --> Local
    Mocks --> Local
    Coverage --> Reports
    
    Local --> CI
    CI --> Reports
    
    Pytest --> BackendTests
    Pytest --> UtilTests
    Pytest --> ConfigTests
    Pytest --> ThemeTests
    
    classDef category fill:#E8F4F8,stroke:#0288D1,stroke-width:2px
    classDef infra fill:#FFF9C4,stroke:#F57F17,stroke-width:2px
    classDef execution fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    classDef areas fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    
    class Unit,Integration,Performance,UI category
    class Pytest,Fixtures,Mocks,Coverage infra
    class Local,CI,Reports execution
    class BackendTests,UtilTests,ConfigTests,ThemeTests areas
```

---

## 12. Backend Capabilities Matrix (Priority 1)

**Target File**: `backends/overview.md`
**Purpose**: Show feature comparison across backends

```mermaid
graph LR
    subgraph PostgreSQL
        PG_MV[Materialized Views ✓]
        PG_SS[Server-side Processing ✓]
        PG_GIST[GIST Indexes ✓]
        PG_BUFFER[Buffer Operations ✓]
        PG_PRED[All Predicates ✓]
        PG_PERF[Best Performance ⚡]
    end
    
    subgraph Spatialite
        SP_TT[Temporary Tables ✓]
        SP_RTREE[R*Tree Indexes ✓]
        SP_LOCAL[Local Processing ✓]
        SP_BUFFER[Buffer Operations ✓]
        SP_PRED[Most Predicates ✓]
        SP_PERF[Good Performance ⚡]
    end
    
    subgraph OGR
        OGR_MEM[Memory Layers ✓]
        OGR_COMPAT[Universal Compatibility ✓]
        OGR_PROC[QGIS Processing ✓]
        OGR_BUFFER[Buffer Operations ⚠️]
        OGR_PRED[Basic Predicates ⚠️]
        OGR_PERF[Limited Performance 🐌]
    end
    
    classDef excellent fill:#90EE90,stroke:#2d6a2d,stroke-width:2px
    classDef good fill:#87CEEB,stroke:#1e5f8f,stroke-width:2px
    classDef limited fill:#FFD700,stroke:#b8860b,stroke-width:2px
    
    class PG_MV,PG_SS,PG_GIST,PG_BUFFER,PG_PRED,PG_PERF excellent
    class SP_TT,SP_RTREE,SP_LOCAL,SP_BUFFER,SP_PRED,SP_PERF good
    class OGR_MEM,OGR_COMPAT,OGR_PROC,OGR_BUFFER,OGR_PRED,OGR_PERF limited
```

### Detailed Capabilities Table

| Feature | PostgreSQL | Spatialite | OGR |
|---------|-----------|-----------|-----|
| **Spatial Predicates** | | | |
| Intersects | ✅ Full | ✅ Full | ✅ Basic |
| Contains | ✅ Full | ✅ Full | ⚠️ Limited |
| Within | ✅ Full | ✅ Full | ⚠️ Limited |
| Touches | ✅ Full | ✅ Full | ❌ No |
| Crosses | ✅ Full | ✅ Full | ❌ No |
| Overlaps | ✅ Full | ✅ Full | ❌ No |
| Disjoint | ✅ Full | ✅ Full | ⚠️ Limited |
| **Buffer Operations** | | | |
| Point buffer | ✅ Full | ✅ Full | ⚠️ Limited |
| Line buffer | ✅ Full | ✅ Full | ⚠️ Limited |
| Polygon buffer | ✅ Full | ✅ Full | ⚠️ Limited |
| Negative buffer | ✅ Full | ✅ Full | ❌ No |
| **Performance** | | | |
| Small datasets (< 10k) | ⚡ Excellent | ⚡ Excellent | ⚡ Good |
| Medium datasets (10-50k) | ⚡ Excellent | ⚡ Very Good | 🐌 Acceptable |
| Large datasets (50-500k) | ⚡ Excellent | 🐌 Acceptable | 🐌 Slow |
| Very large (> 500k) | ⚡ Excellent | 🐌 Very Slow | ❌ Not viable |
| **Indexing** | | | |
| Spatial indexes | ✅ GIST | ✅ R*Tree | ⚠️ Limited |
| Attribute indexes | ✅ B-Tree | ✅ B-Tree | ⚠️ Limited |
| Automatic index creation | ✅ Yes | ✅ Yes | ❌ No |

---

## Usage Instructions

### How to Add Diagrams to Documentation

1. **Copy the Mermaid code block** from this file
2. **Paste into your markdown file** at the appropriate location
3. **Ensure proper fencing**:
   ````markdown
   ```mermaid
   [diagram code here]
   ```
   ````

4. **Test locally** with Docusaurus:
   ```bash
   cd website
   npm run start
   ```

5. **Verify rendering** in browser at `http://localhost:3000`

### Diagram Customization

#### Colors
- **Optimal/Success**: `#90EE90` (light green)
- **Recommended/Info**: `#87CEEB` (sky blue)
- **Acceptable/Warning**: `#FFD700` (gold)
- **Error/Critical**: `#FF6347` (tomato red)

#### Style Classes
```mermaid
classDef optimal fill:#90EE90,stroke:#2d6a2d,stroke-width:2px
classDef good fill:#87CEEB,stroke:#1e5f8f,stroke-width:2px
classDef warning fill:#FFD700,stroke:#b8860b,stroke-width:2px
classDef error fill:#FF6347,stroke:#8b0000,stroke-width:2px

class NodeName optimal
```

### Accessibility Considerations

All diagrams follow WCAG 2.1 AA standards:
- ✅ Color is not the only means of conveying information
- ✅ Text labels clarify all states
- ✅ Contrast ratios meet accessibility requirements
- ✅ Symbols (✓, ⚠️, ❌) supplement colors

---

## Next Steps

1. ✅ Diagrams designed (this file)
2. ⏳ Implement in documentation pages (see DOCUMENTATION_UPDATE_PLAN_V2.md)
3. ⏳ Test rendering in Docusaurus
4. ⏳ Add screenshots and examples
5. ⏳ Review and iterate

---

*Generated: December 8, 2025*
*Total Diagrams: 12*
*Status: Ready for implementation*
