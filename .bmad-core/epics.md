# Epic: Multi-Backend Filtering System

## 📋 Epic Overview

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-001 |
| **Title** | Multi-Backend Filtering System |
| **Status** | ✅ Complete |
| **Priority** | P0 - Critical |
| **Completed** | December 2025 |

## 🎯 Goal

Implement a flexible filtering system that automatically selects the optimal backend (PostgreSQL, Spatialite, or OGR) based on the data source, with user override capability.

## 📖 User Stories

### STORY-001: Automatic Backend Selection
**As a** GIS analyst  
**I want** FilterMate to automatically select the best backend for my data  
**So that** I get optimal performance without manual configuration

**Acceptance Criteria**:
- [x] PostgreSQL layers use PostgreSQL backend
- [x] Spatialite layers use Spatialite backend
- [x] OGR layers (Shapefile, GeoPackage) use OGR backend
- [x] Graceful fallback when psycopg2 unavailable

### STORY-002: Forced Backend Selection
**As a** power user  
**I want** to manually select a backend for any layer  
**So that** I can control performance vs compatibility trade-offs

**Acceptance Criteria**:
- [x] UI indicator shows current backend
- [x] User can change backend per layer
- [x] Forced selection persists across sessions
- [x] Warning shown for incompatible choices

### STORY-003: PostgreSQL Materialized Views
**As a** user with large PostgreSQL datasets  
**I want** FilterMate to use materialized views  
**So that** filtering millions of features is fast

**Acceptance Criteria**:
- [x] Materialized views created for complex filters
- [x] GIST spatial indexes auto-created
- [x] UNLOGGED tables for temporary data
- [x] Automatic cleanup after operation

### STORY-004: Spatialite Fallback
**As a** user without PostgreSQL  
**I want** FilterMate to work with Spatialite  
**So that** I can filter local databases

**Acceptance Criteria**:
- [x] Temporary tables created for filtering
- [x] R-tree indexes auto-created
- [x] Lock retry mechanism (5 attempts)
- [x] Expression conversion from QGIS to Spatialite

### STORY-005: OGR Universal Fallback
**As a** user with diverse data formats  
**I want** FilterMate to work with any QGIS-supported format  
**So that** I'm not limited by data source

**Acceptance Criteria**:
- [x] Works with Shapefiles
- [x] Works with GeoPackage
- [x] Works with GeoJSON
- [x] Uses QGIS processing framework

## 🔧 Technical Tasks

| Task | Status | Assignee |
|------|--------|----------|
| Create BaseBackend abstract class | ✅ Done | - |
| Implement PostgreSQLBackend | ✅ Done | - |
| Implement SpatialiteBackend | ✅ Done | - |
| Implement OGRBackend | ✅ Done | - |
| Create BackendFactory | ✅ Done | - |
| Add forced_backends to UI | ✅ Done | - |
| Add POSTGRESQL_AVAILABLE check | ✅ Done | - |
| Expression conversion (QGIS → SQL) | ✅ Done | - |
| Performance benchmarking | ✅ Done | - |

## 📊 Performance Metrics

| Backend | Dataset Size | Target Time | Achieved |
|---------|--------------|-------------|----------|
| PostgreSQL | 1M features | <1s | ✅ 0.5s |
| Spatialite | 100k features | <10s | ✅ 5s |
| OGR | 10k features | <30s | ✅ 15s |

---

# Epic: Undo/Redo System

## 📋 Epic Overview

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-002 |
| **Title** | Global Undo/Redo System |
| **Status** | ✅ Complete |
| **Priority** | P0 - Critical |
| **Completed** | December 2025 |

## 🎯 Goal

Implement an intelligent undo/redo system that maintains filter history and supports both source-only and global restoration modes.

## 📖 User Stories

### STORY-006: Filter History
**As a** user exploring data  
**I want** FilterMate to remember my filter history  
**So that** I can go back to previous states

**Acceptance Criteria**:
- [x] All filter operations recorded
- [x] History persists during session
- [x] Clear history option available

### STORY-007: Intelligent Undo
**As a** user  
**I want** undo to work intelligently based on context  
**So that** I get the expected behavior

**Acceptance Criteria**:
- [x] Source-only mode when no remote layers selected
- [x] Global mode restores all layers atomically
- [x] Auto-detection based on layer selection

### STORY-008: Redo Support
**As a** user  
**I want** to redo undone operations  
**So that** I can explore different filter paths

**Acceptance Criteria**:
- [x] Redo button enabled after undo
- [x] Redo reapplies exact previous state
- [x] Redo stack cleared on new filter

### STORY-009: UI State Management
**As a** user  
**I want** undo/redo buttons to show availability  
**So that** I know what actions are possible

**Acceptance Criteria**:
- [x] Undo button disabled when no history
- [x] Redo button disabled when no redo available
- [x] Buttons update automatically

---

# Epic: Configuration System v2.0

## 📋 Epic Overview

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-003 |
| **Title** | Configuration System v2.0 |
| **Status** | ✅ Complete |
| **Priority** | P0 - Critical |
| **Completed** | December 17, 2025 |

## 🎯 Goal

Implement a robust configuration system with integrated metadata, automatic migration, and real-time updates.

## 📖 User Stories

### STORY-010: Configuration with Metadata
**As a** developer  
**I want** configuration to include metadata  
**So that** UI can be auto-generated

**Acceptance Criteria**:
- [x] Parameters include value + choices + description
- [x] Metadata drives tooltip generation
- [x] Single source of truth for config

### STORY-011: Auto-Migration
**As a** user upgrading FilterMate  
**I want** my old config to auto-migrate  
**So that** I don't lose settings

**Acceptance Criteria**:
- [x] v1.0 → v2.0 migration automatic
- [x] Backup created before migration
- [x] Rollback on migration failure

### STORY-012: Real-Time Updates
**As a** user  
**I want** config changes to apply immediately  
**So that** I don't need to restart QGIS

**Acceptance Criteria**:
- [x] Theme changes apply instantly
- [x] UI profile changes resize immediately
- [x] Settings persist to file

### STORY-013: Invalid Config Recovery
**As a** user with corrupted config  
**I want** FilterMate to recover automatically  
**So that** the plugin still works

**Acceptance Criteria**:
- [x] Invalid config detected on load
- [x] Backup of corrupted config created
- [x] Default config restored
- [x] User notified of recovery

---

# Epic: Dark Mode & Theming

## 📋 Epic Overview

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-004 |
| **Title** | Automatic Dark Mode Support |
| **Status** | ✅ Complete |
| **Priority** | P1 - High |
| **Completed** | December 18, 2025 |

## 🎯 Goal

Implement automatic detection and synchronization with QGIS theme, including icon inversion for dark mode.

## 📖 User Stories

### STORY-014: Theme Detection
**As a** user with QGIS dark mode  
**I want** FilterMate to detect my theme  
**So that** the UI matches QGIS

**Acceptance Criteria**:
- [x] Detect QGIS theme at startup
- [x] Real-time detection on theme change
- [x] Apply matching styles

### STORY-015: Icon Inversion
**As a** dark mode user  
**I want** icons to be visible  
**So that** I can see UI elements

**Acceptance Criteria**:
- [x] PNG icons inverted for dark mode
- [x] Icon cache for performance
- [x] Automatic refresh on theme change

### STORY-016: JsonView Theme Sync
**As a** user editing config  
**I want** the JSON editor to match theme  
**So that** the experience is consistent

**Acceptance Criteria**:
- [x] JSON tree view updates with theme
- [x] Syntax colors adapted
- [x] Scrollbar styled

---

# Epic: Filter Favorites

## 📋 Epic Overview

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-005 |
| **Title** | Filter Favorites System |
| **Status** | ✅ Complete |
| **Priority** | P1 - High |
| **Completed** | December 18, 2025 |

## 🎯 Goal

Allow users to save, organize, and reuse complex filter configurations.

## 📖 User Stories

### STORY-017: Save Favorite
**As a** user with complex filters  
**I want** to save filter configurations  
**So that** I can reuse them later

**Acceptance Criteria**:
- [x] Save current filter as favorite
- [x] Assign name and description
- [x] Add tags for organization

### STORY-018: Apply Favorite
**As a** user with saved favorites  
**I want** to quickly apply a saved filter  
**So that** I save time on repeated tasks

**Acceptance Criteria**:
- [x] List favorites in UI
- [x] One-click apply
- [x] Track usage count

### STORY-019: Favorites Persistence
**As a** user across sessions  
**I want** favorites to persist  
**So that** I don't lose my saved filters

**Acceptance Criteria**:
- [x] SQLite storage
- [x] Persist across sessions
- [x] Export/import via JSON

### STORY-020: Favorites Search
**As a** user with many favorites  
**I want** to search and filter  
**So that** I find what I need quickly

**Acceptance Criteria**:
- [x] Search by name
- [x] Filter by tags
- [x] Sort by usage/date

---

# Epic: Project Change Stability

## 📋 Epic Overview

| Field | Value |
|-------|-------|
| **Epic ID** | EPIC-006 |
| **Title** | Project Change Stability |
| **Status** | ✅ Complete |
| **Priority** | P0 - Critical |
| **Completed** | December 18, 2025 |

## 🎯 Goal

Ensure reliable plugin behavior when switching between QGIS projects.

## 📖 User Stories

### STORY-021: Project Switch Handling
**As a** user switching projects  
**I want** FilterMate to properly reinitialize  
**So that** layers are correct for new project

**Acceptance Criteria**:
- [x] Detect project change
- [x] Clean up previous state
- [x] Reinitialize for new project
- [x] Handle signal timing issues

### STORY-022: Project Close Handling
**As a** user closing projects  
**I want** FilterMate state to reset  
**So that** no stale data remains

**Acceptance Criteria**:
- [x] Detect project cleared signal
- [x] Reset all state
- [x] Clear layer references

### STORY-023: Manual Recovery
**As a** user when auto-detection fails  
**I want** a manual reload option  
**So that** I can recover without restart

**Acceptance Criteria**:
- [x] F5 shortcut to force reload
- [x] Complete layer reload
- [x] State reset on demand
