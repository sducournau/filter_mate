---
sidebar_position: 1
---

# Simplified Architecture Guide

This guide provides a user-friendly explanation of FilterMate's architecture, designed for developers who want to understand or contribute to the project.

## 🏗️ High-Level Architecture

FilterMate follows a layered architecture with clear separation of concerns:

```mermaid
graph TB
    subgraph "User Interface Layer"
        UI[FilterMate Dockwidget<br/>PyQt5 Widgets]
    end
    
    subgraph "Application Layer"
        App[FilterMateApp<br/>Central Orchestrator]
        Tasks[Async Tasks<br/>QgsTask]
    end
    
    subgraph "Backend Layer"
        Factory[BackendFactory<br/>Auto-selection]
        PG[PostgreSQL Backend]
        SL[Spatialite Backend]
        OGR[OGR Backend]
    end
    
    subgraph "Data Sources"
        DB[(PostgreSQL<br/>Database)]
        SQLite[(Spatialite<br/>File)]
        Files[Shapefiles<br/>GeoPackage<br/>etc.]
    end
    
    subgraph "QGIS Integration"
        QGIS[QGIS Core<br/>Map Canvas<br/>Layers]
    end
    
    UI -->|Signals| App
    App -->|Dispatch| Tasks
    Tasks -->|Select Backend| Factory
    Factory -.->|Optimal| PG
    Factory -.->|Good| SL
    Factory -.->|Fallback| OGR
    
    PG <-->|SQL| DB
    SL <-->|SQL| SQLite
    OGR <-->|GDAL/OGR| Files
    
    App <-->|Layers & Filters| QGIS
    Tasks -->|Results| App
    
    style UI fill:#e3f2fd
    style App fill:#fff3e0
    style Factory fill:#f3e5f5
    style PG fill:#51cf66
    style SL fill:#ffd43b
    style OGR fill:#74c0fc
    style QGIS fill:#ffebee
```

---

## 📦 Core Components

### 1. Plugin Entry Point
**File:** `filter_mate.py`  
**Purpose:** QGIS plugin integration

```mermaid
flowchart LR
    QGIS[QGIS Plugin Manager] --> Init[initGui]
    Init --> Create[Create Dockwidget]
    Create --> Register[Register with QGIS]
    Register --> Ready[Plugin Ready]
    
    Ready --> User[User Closes Plugin]
    User --> Cleanup[unload]
    Cleanup --> Remove[Remove from QGIS]
    
    style Ready fill:#51cf66
```

**Key Responsibilities:**
- Plugin lifecycle management
- QGIS integration
- Menu and toolbar registration

---

### 2. Application Orchestrator
**File:** `filter_mate_app.py`  
**Purpose:** Central coordinator

```mermaid
graph TB
    App[FilterMateApp] --> State[State Management]
    App --> TaskMgmt[Task Management]
    App --> Config[Configuration]
    App --> Signals[Signal Coordination]
    
    State --> Layers[PROJECT_LAYERS dict]
    State --> History[Filter History]
    
    TaskMgmt --> Dispatch[manage_task]
    TaskMgmt --> Complete[task_completed handlers]
    
    Config --> Load[Load config.json]
    Config --> Save[Save project properties]
    
    Signals --> ToUI[Signals to Dockwidget]
    Signals --> FromUI[Signals from Dockwidget]
    
    style App fill:#fff3e0
```

**Key Methods:**
```python
class FilterMateApp:
    # Central task dispatcher
    def manage_task(task_type, parameters):
        # Create and launch appropriate QgsTask
        
    # Result handlers
    def filter_engine_task_completed(result):
        # Apply filter to layers
        
    def layer_management_engine_task_completed(result):
        # Update PROJECT_LAYERS state
```

---

### 3. User Interface
**File:** `filter_mate_dockwidget.py`  
**Purpose:** User interaction

```mermaid
graph TB
    Dock[FilterMateDockWidget] --> Frames[UI Sections]
    Dock --> Widgets[Custom Widgets]
    Dock --> SignalMgmt[Signal Management]
    
    Frames --> Explore[Exploring Frame]
    Frames --> Filter[Filtering Frame]
    Frames --> Export[Export Frame]
    Frames --> ConfigTree[Configuration Tab]
    
    Widgets --> LayerCombo[Checkable Layer ComboBox]
    Widgets --> FeaturePicker[Feature Picker Widget]
    Widgets --> JSONView[JSON Tree View]
    
    SignalMgmt --> Emit[Emit to App]
    SignalMgmt --> Receive[Receive from App]
    
    style Dock fill:#e3f2fd
```

**UI Organization:**
- **Tab 1: Filtering & Exploring**: Main filtering interface
- **Tab 2: Configuration**: JSON tree view for settings

---

### 4. Asynchronous Tasks
**File:** `modules/appTasks.py`  
**Purpose:** Non-blocking operations

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant App
    participant Task
    participant Backend
    
    User->>UI: Click "Filter"
    UI->>App: launchingTask signal
    App->>Task: Create FilterEngineTask
    Task->>Task: run() in background thread
    
    Note over Task,Backend: Heavy computation<br/>does not block UI
    
    Task->>Backend: execute_filter()
    Backend-->>Task: Results
    
    Task->>Task: finished() in main thread
    Task->>App: taskCompleted signal
    App->>UI: Update display
    UI-->>User: Results visible
```

**Key Task Types:**
- `FilterEngineTask`: Execute filtering operations
- `LayersManagementEngineTask`: Add/remove layers
- `PopulateListEngineTask`: Load feature lists
- `ExportEngineTask`: Export filtered data

---

## 🔄 Data Flow Examples

### Example 1: User Applies a Filter

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as Dockwidget
    participant App as FilterMateApp
    participant Task as FilterEngineTask
    participant Backend as Backend
    participant Layer as QGIS Layer
    
    U->>UI: Select layers & predicate
    U->>UI: Click "Filter"
    
    UI->>App: launchingTask('filter', params)
    App->>App: get_task_parameters()
    App->>Task: Create task instance
    
    Task->>Backend: BackendFactory.get_backend()
    Backend->>Backend: Detect optimal backend
    Backend->>Backend: Execute spatial query
    Backend-->>Task: Return feature IDs
    
    Task->>App: taskCompleted signal
    App->>Layer: setSubsetString(expression)
    Layer-->>U: Filtered view on map
```

### Example 2: Layer Added to Project

```mermaid
flowchart TD
    Start[User adds layer to QGIS] --> Signal[QgsProject.layersAdded signal]
    Signal --> App[FilterMateApp receives signal]
    App --> CreateTask[Create LayersManagementEngineTask]
    
    CreateTask --> Extract[Extract layer metadata]
    Extract --> Meta1[Provider type]
    Extract --> Meta2[Geometry type]
    Extract --> Meta3[CRS]
    Extract --> Meta4[Primary key]
    Extract --> Meta5[Field list]
    
    Meta1 --> Store[Store in PROJECT_LAYERS]
    Meta2 --> Store
    Meta3 --> Store
    Meta4 --> Store
    Meta5 --> Store
    
    Store --> Notify[Emit getProjectLayersEvent]
    Notify --> UI[Dockwidget updates UI]
    UI --> Populate[Populate layer combobox]
    
    style Store fill:#fff3e0
    style Populate fill:#e3f2fd
```

---

## 🔌 Backend System

### Backend Factory Pattern

```mermaid
flowchart TD
    Request[Filtering Request] --> Factory[BackendFactory.get_backend]
    
    Factory --> Check1{Provider Type}
    
    Check1 -->|postgres| Check2{psycopg2<br/>available?}
    Check1 -->|spatialite| CreateSL[Create SpatialiteBackend]
    Check1 -->|ogr or other| CreateOGR[Create OGRBackend]
    
    Check2 -->|Yes| CreatePG[Create PostgreSQLBackend]
    Check2 -->|No| Warn[Show warning]
    Warn --> CreateSL
    
    CreatePG --> Return[Return backend instance]
    CreateSL --> Return
    CreateOGR --> Return
    
    Return --> Use[Use backend for operation]
    Use --> Cleanup[backend.cleanup]
    
    style Factory fill:#f3e5f5
    style CreatePG fill:#51cf66
    style CreateSL fill:#ffd43b
    style CreateOGR fill:#74c0fc
```

### Backend Interface

All backends implement the same interface:

```python
class GeometricFilterBackend(ABC):
    @abstractmethod
    def execute_filter(self, expression, predicates, buffer):
        """Execute filtering operation"""
        pass
    
    @abstractmethod
    def get_feature_count(self):
        """Get result count"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources"""
        pass
```

---

## 🎨 UI System Architecture

### Dynamic Dimensions System

```mermaid
stateDiagram-v2
    [*] --> DetectScreen: Plugin starts
    
    DetectScreen --> CheckResolution: Get screen resolution
    
    CheckResolution --> AutoMode: UI_PROFILE = "auto"
    CheckResolution --> CompactMode: UI_PROFILE = "compact"
    CheckResolution --> NormalMode: UI_PROFILE = "normal"
    
    AutoMode --> IsSmall{Resolution<br/>< 1920x1080?}
    IsSmall -->|Yes| CompactMode
    IsSmall -->|No| NormalMode
    
    CompactMode --> ApplyCompact[Apply compact dimensions<br/>18px buttons<br/>24px inputs<br/>3px spacing]
    
    NormalMode --> ApplyNormal[Apply normal dimensions<br/>24px buttons<br/>30px inputs<br/>6px spacing]
    
    ApplyCompact --> [*]: UI Ready
    ApplyNormal --> [*]: UI Ready
```

### Theme System

```mermaid
graph LR
    Start[Plugin UI] --> ThemeSource{THEME_SOURCE}
    
    ThemeSource -->|qgis| DetectQGIS[Detect QGIS theme]
    ThemeSource -->|config| ReadConfig[Read ACTIVE_THEME]
    ThemeSource -->|system| DetectOS[Detect OS theme]
    
    DetectQGIS --> QGISTheme[Blend of Gray /<br/>Night Mapping]
    ReadConfig --> ConfigTheme[light / dark / auto]
    DetectOS --> OSTheme[System preference]
    
    QGISTheme --> ApplyQSS[Apply QSS stylesheet]
    ConfigTheme --> ApplyQSS
    OSTheme --> ApplyQSS
    
    ApplyQSS --> Themed[Themed UI]
    
    style Themed fill:#e3f2fd
```

---

## 📊 State Management

### Layer State Storage

```mermaid
graph TB
    State[PROJECT_LAYERS] --> Layer1[Layer ID: abc123]
    State --> Layer2[Layer ID: def456]
    State --> LayerN[...]
    
    Layer1 --> Info1[infos: metadata]
    Layer1 --> Explore1[exploring: selection]
    Layer1 --> Filter1[filtering: parameters]
    
    Info1 --> I1[layer_name]
    Info1 --> I2[provider_type]
    Info1 --> I3[geometry_type]
    Info1 --> I4[CRS]
    
    Explore1 --> E1[selected_features]
    Explore1 --> E2[display_expression]
    
    Filter1 --> F1[layers_to_filter]
    Filter1 --> F2[predicates]
    Filter1 --> F3[buffer_distance]
    
    style State fill:#fff3e0
```

**Persistence:** Saved as QGIS project custom property

```python
# Save
QgsProject.instance().setCustomProperty(
    'filterMate_layers', 
    json.dumps(PROJECT_LAYERS)
)

# Load
PROJECT_LAYERS = json.loads(
    QgsProject.instance().readCustomProperty(
        'filterMate_layers', 
        '{}'
    )
)
```

---

## 🔧 Configuration System

### Configuration Hierarchy

```mermaid
graph TD
    Config[Configuration] --> Static[Static Config<br/>config.json]
    Config --> Dynamic[Dynamic Config<br/>Project Properties]
    Config --> Runtime[Runtime State<br/>In-memory]
    
    Static --> S1[UI_PROFILE]
    Static --> S2[ACTIVE_THEME]
    Static --> S3[ICON_PATH]
    Static --> S4[Backend settings]
    
    Dynamic --> D1[Layer properties]
    Dynamic --> D2[Filter history]
    Dynamic --> D3[Export settings]
    
    Runtime --> R1[Current selections]
    Runtime --> R2[UI state]
    Runtime --> R3[Task status]
    
    style Config fill:#f3e5f5
```

### Configuration Reactivity (v2.2.2+)

```mermaid
sequenceDiagram
    participant User
    participant JSONView
    participant Handler
    participant UI
    participant ConfigFile
    
    User->>JSONView: Edit value in tree
    JSONView->>Handler: itemChanged signal
    
    Handler->>Handler: Validate value
    
    alt Valid change
        Handler->>UI: Apply change immediately
        UI->>UI: Update dimensions/theme
        Handler->>ConfigFile: Auto-save
        ConfigFile-->>User: ✅ Success feedback
    else Invalid change
        Handler->>User: ❌ Error: Invalid value
        Handler->>JSONView: Revert to previous
    end
    
    Note over User,ConfigFile: No restart required!
```

---

## 🧩 Module Organization

```
filter_mate/
├── filter_mate.py                 # Plugin entry point
├── filter_mate_app.py             # Application orchestrator
├── filter_mate_dockwidget.py      # User interface
│
├── modules/                       # Core modules
│   ├── appTasks.py               # Async task implementations
│   ├── appUtils.py               # Database utilities
│   ├── state_manager.py          # State management
│   ├── filter_history.py         # History tracking
│   │
│   ├── backends/                 # Backend system
│   │   ├── base_backend.py      # Abstract interface
│   │   ├── postgresql_backend.py
│   │   ├── spatialite_backend.py
│   │   ├── ogr_backend.py
│   │   └── factory.py           # Backend factory
│   │
│   ├── ui_config.py              # Dynamic dimensions
│   ├── ui_styles.py              # Theme management
│   ├── ui_elements.py            # UI helpers
│   ├── widgets.py                # Custom widgets
│   └── signal_utils.py           # Signal management
│
├── config/                        # Configuration
│   ├── config.json               # Settings
│   └── config.py                 # Config loader
│
└── resources/                     # Assets
    ├── styles/                   # QSS stylesheets
    └── icons/                    # Icon files
```

---

## 🔍 Key Design Patterns

### 1. Factory Pattern (Backend Selection)
```python
# Automatic backend selection
backend = BackendFactory.get_backend(layer)
result = backend.execute_filter(params)
backend.cleanup()
```

### 2. Signal/Slot Pattern (UI ↔ App Communication)
```python
# Dockwidget emits signal
self.launchingTask.emit('filter', parameters)

# App receives and processes
@pyqtSlot(str, dict)
def manage_task(self, task_type, params):
    # Handle task
```

### 3. Observer Pattern (State Management)
```python
# Layers added to project
QgsProject.instance().layersAdded.connect(
    self.on_layers_added
)
```

### 4. Strategy Pattern (Backends)
```python
# Different strategies for different data sources
if provider == 'postgres':
    strategy = PostgreSQLBackend()
elif provider == 'spatialite':
    strategy = SpatialiteBackend()
else:
    strategy = OGRBackend()
```

---

## 🚀 Extension Points

### Adding a New Backend

1. **Create backend class**
```python
from modules.backends.base_backend import GeometricFilterBackend

class MyCustomBackend(GeometricFilterBackend):
    def execute_filter(self, expression, predicates, buffer):
        # Your implementation
        pass
    
    def cleanup(self):
        # Cleanup resources
        pass
```

2. **Register in factory**
```python
# In factory.py
def get_backend(layer):
    if layer.providerType() == 'my_custom':
        return MyCustomBackend(layer)
    # ... existing logic
```

### Adding a New Task Type

1. **Create task class**
```python
class MyCustomTask(QgsTask):
    def __init__(self, description, parameters):
        super().__init__(description, QgsTask.CanCancel)
        self.parameters = parameters
    
    def run(self):
        # Background work
        return True
    
    def finished(self, result):
        # Main thread callback
        pass
```

2. **Add to dispatcher**
```python
# In filter_mate_app.py
def manage_task(self, task_type, params):
    if task_type == 'my_custom':
        task = MyCustomTask('Description', params)
        QgsApplication.taskManager().addTask(task)
```

---

## 📚 Further Reading

- **User Guide**: Understand features from user perspective
- **Backend Guide**: Deep dive into backend implementations
- **API Reference**: Detailed function documentation
- **Contributing Guide**: How to contribute code

## 🤝 Contributing

Want to contribute? Check out:
1. [GitHub Repository](https://github.com/sducournau/filter_mate)
2. [Open Issues](https://github.com/sducournau/filter_mate/issues)
3. [Development Setup Guide](./development-setup.md)

Questions? Open an issue or discussion on GitHub!
