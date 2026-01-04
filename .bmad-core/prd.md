# FilterMate - Product Requirements Document (PRD)

## 📋 Document Info

| Field                | Value           |
| -------------------- | --------------- |
| **Document Version** | 2.0             |
| **Product Version**  | 2.8.5           |
| **Last Updated**     | January 4, 2026 |
| **Status**           | Approved        |

---

## 1. Executive Summary

FilterMate is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data. It enables users to explore, filter, and export vector layers intuitively with automatic performance optimization based on data source type.

### Key Value Propositions

1. **Universal Data Source Support** - Works with any QGIS-compatible vector format
2. **Automatic Performance Optimization** - Selects optimal backend (PostgreSQL/Spatialite/OGR)
3. **Intuitive User Experience** - Complex spatial operations made simple
4. **Professional-Grade Quality** - Robust error handling and recovery

---

## 2. Problem Statement

### Current Challenges (Pre-FilterMate)

| Challenge                                                | Impact                      |
| -------------------------------------------------------- | --------------------------- |
| Complex spatial filtering in QGIS requires SQL knowledge | Limits accessibility        |
| No unified interface for different data sources          | Inconsistent workflows      |
| Performance issues with large datasets                   | Productivity loss           |
| Manual filter management                                 | Error-prone, time-consuming |
| No filter history/undo                                   | Risky for data exploration  |

### Solution

FilterMate provides a single, intuitive interface that:

- Abstracts complexity behind user-friendly widgets
- Automatically optimizes queries for each data source
- Maintains filter history with undo/redo support
- Handles errors gracefully with automatic recovery

---

## 3. User Personas

### Persona 1: GIS Analyst (Primary)

- **Name**: Marie, Environmental Analyst
- **Goals**: Quick data exploration, spatial analysis, report generation
- **Pain Points**: Slow workflows, complex queries, data export hassles
- **FilterMate Benefits**: Intuitive filtering, fast performance, easy export

### Persona 2: Data Engineer (Secondary)

- **Name**: Thomas, Spatial Data Engineer
- **Goals**: Automate workflows, integrate with databases, optimize performance
- **Pain Points**: Database connectivity, query optimization
- **FilterMate Benefits**: PostgreSQL/PostGIS integration, backend control

### Persona 3: Occasional User (Tertiary)

- **Name**: Julie, Urban Planner
- **Goals**: Quick data subset, simple filtering, visualization
- **Pain Points**: QGIS complexity, filter syntax
- **FilterMate Benefits**: Simple UI, saved filters, favorites system

---

## 4. Functional Requirements

### 4.1 Core Filtering Features (FR-FILTER)

| ID            | Requirement                                    | Priority | Status  |
| ------------- | ---------------------------------------------- | -------- | ------- |
| FR-FILTER-001 | Filter layers by attribute expression          | P0       | ✅ Done |
| FR-FILTER-002 | Filter layers by geometric predicates          | P0       | ✅ Done |
| FR-FILTER-003 | Support buffer distance on geometric filters   | P0       | ✅ Done |
| FR-FILTER-004 | Apply filter to multiple layers simultaneously | P0       | ✅ Done |
| FR-FILTER-005 | Combine attribute and geometric filters        | P0       | ✅ Done |
| FR-FILTER-006 | Save/load filter configurations                | P1       | ✅ Done |
| FR-FILTER-007 | Filter favorites with tags and search          | P1       | ✅ Done |

### 4.2 Layer Management Features (FR-LAYER)

| ID           | Requirement                                      | Priority | Status  |
| ------------ | ------------------------------------------------ | -------- | ------- |
| FR-LAYER-001 | Auto-detect layer properties (geometry, CRS, PK) | P0       | ✅ Done |
| FR-LAYER-002 | Support PostgreSQL/PostGIS layers                | P0       | ✅ Done |
| FR-LAYER-003 | Support Spatialite layers                        | P0       | ✅ Done |
| FR-LAYER-004 | Support OGR layers (Shapefile, GeoPackage, etc.) | P0       | ✅ Done |
| FR-LAYER-005 | Automatic CRS reprojection                       | P0       | ✅ Done |
| FR-LAYER-006 | Handle geographic CRS (auto-convert to metric)   | P0       | ✅ Done |

### 4.3 Export Features (FR-EXPORT)

| ID            | Requirement                                         | Priority | Status  |
| ------------- | --------------------------------------------------- | -------- | ------- |
| FR-EXPORT-001 | Export filtered features to file                    | P0       | ✅ Done |
| FR-EXPORT-002 | Support multiple formats (GPKG, SHP, GeoJSON, etc.) | P0       | ✅ Done |
| FR-EXPORT-003 | Export layer styles (QML, SLD)                      | P1       | ✅ Done |
| FR-EXPORT-004 | Field selection for export                          | P1       | ✅ Done |
| FR-EXPORT-005 | CRS transformation on export                        | P1       | ✅ Done |

### 4.4 History & Undo Features (FR-HISTORY)

| ID             | Requirement                                           | Priority | Status  |
| -------------- | ----------------------------------------------------- | -------- | ------- |
| FR-HISTORY-001 | Maintain filter history                               | P0       | ✅ Done |
| FR-HISTORY-002 | Undo last filter operation                            | P0       | ✅ Done |
| FR-HISTORY-003 | Redo undone filter operation                          | P0       | ✅ Done |
| FR-HISTORY-004 | Intelligent context detection (source-only vs global) | P1       | ✅ Done |
| FR-HISTORY-005 | Clear filter history                                  | P2       | ✅ Done |

### 4.5 Configuration Features (FR-CONFIG)

| ID            | Requirement                         | Priority | Status  |
| ------------- | ----------------------------------- | -------- | ------- |
| FR-CONFIG-001 | JSON-based configuration system     | P0       | ✅ Done |
| FR-CONFIG-002 | Configuration v2.0 with metadata    | P0       | ✅ Done |
| FR-CONFIG-003 | Auto-migration from v1.0 to v2.0    | P0       | ✅ Done |
| FR-CONFIG-004 | Real-time configuration updates     | P1       | ✅ Done |
| FR-CONFIG-005 | Per-layer configuration persistence | P1       | ✅ Done |
| FR-CONFIG-006 | User-selectable backend per layer   | P1       | ✅ Done |

---

## 5. Non-Functional Requirements

### 5.1 Performance (NFR-PERF)

| ID           | Requirement                            | Target | Current |
| ------------ | -------------------------------------- | ------ | ------- |
| NFR-PERF-001 | PostgreSQL query time (<1M features)   | <1s    | ✅ Met  |
| NFR-PERF-002 | Spatialite query time (<100k features) | <10s   | ✅ Met  |
| NFR-PERF-003 | OGR query time (<10k features)         | <30s   | ✅ Met  |
| NFR-PERF-004 | UI responsiveness (non-blocking)       | <100ms | ✅ Met  |
| NFR-PERF-005 | Memory usage                           | <500MB | ✅ Met  |

### 5.2 Reliability (NFR-REL)

| ID          | Requirement                           | Target     | Current |
| ----------- | ------------------------------------- | ---------- | ------- |
| NFR-REL-001 | Graceful degradation without psycopg2 | 100%       | ✅ Met  |
| NFR-REL-002 | Database lock retry mechanism         | 5 attempts | ✅ Met  |
| NFR-REL-003 | Automatic geometry repair             | 100%       | ✅ Met  |
| NFR-REL-004 | Error recovery without crash          | 100%       | ✅ Met  |

### 5.3 Usability (NFR-USE)

| ID          | Requirement                     | Target      | Current |
| ----------- | ------------------------------- | ----------- | ------- |
| NFR-USE-001 | Theme synchronization with QGIS | Auto        | ✅ Met  |
| NFR-USE-002 | Responsive UI layout            | Adaptive    | ✅ Met  |
| NFR-USE-003 | WCAG 2.1 AA accessibility       | AA          | ✅ Met  |
| NFR-USE-004 | Internationalization            | 7 languages | ✅ Met  |

### 5.4 Maintainability (NFR-MAINT)

| ID            | Requirement            | Target  | Current   |
| ------------- | ---------------------- | ------- | --------- |
| NFR-MAINT-001 | Code quality score     | ≥8.5/10 | 9.0/10 ✅ |
| NFR-MAINT-002 | Test coverage          | ≥80%    | ~70% 🔄   |
| NFR-MAINT-003 | Documentation coverage | ≥90%    | ✅ Met    |
| NFR-MAINT-004 | PEP 8 compliance       | ≥95%    | ✅ Met    |

---

## 6. Geometric Predicates Supported

| Predicate    | Description                         | PostgreSQL | Spatialite | OGR |
| ------------ | ----------------------------------- | :--------: | :--------: | :-: |
| `intersects` | Geometries share any space          |     ✅     |     ✅     | ✅  |
| `within`     | Source completely inside target     |     ✅     |     ✅     | ✅  |
| `contains`   | Source completely contains target   |     ✅     |     ✅     | ✅  |
| `overlaps`   | Geometries overlap (same dimension) |     ✅     |     ✅     | ✅  |
| `touches`    | Geometries share only boundary      |     ✅     |     ✅     | ✅  |
| `crosses`    | Geometries cross each other         |     ✅     |     ✅     | ✅  |
| `disjoint`   | Geometries share no space           |     ✅     |     ✅     | ✅  |

---

## 7. Export Formats Supported

| Format     | Extension | Style Export | Field Selection |
| ---------- | --------- | :----------: | :-------------: |
| GeoPackage | .gpkg     |      ✅      |       ✅        |
| Shapefile  | .shp      |      ✅      |       ✅        |
| GeoJSON    | .geojson  |      ❌      |       ✅        |
| KML        | .kml      |      ❌      |       ✅        |
| DXF        | .dxf      |      ❌      |       ✅        |
| CSV        | .csv      |      ❌      |       ✅        |

---

## 8. Configuration Parameters

### UI Settings

| Parameter    | Type   | Default | Description                          |
| ------------ | ------ | ------- | ------------------------------------ |
| UI_PROFILE   | choice | auto    | Layout profile (auto/compact/normal) |
| ACTIVE_THEME | choice | auto    | Theme (auto/default/dark/light)      |
| THEME_SOURCE | choice | qgis    | Theme source (config/qgis/system)    |

### Backend Settings

| Parameter               | Type   | Default | Description               |
| ----------------------- | ------ | ------- | ------------------------- |
| POSTGRESQL_AVAILABLE    | bool   | auto    | PostgreSQL availability   |
| DEFAULT_BACKEND         | choice | auto    | Default backend selection |
| ENABLE_BACKEND_WARNINGS | bool   | true    | Show performance warnings |

### Export Settings

| Parameter          | Type   | Default | Description           |
| ------------------ | ------ | ------- | --------------------- |
| DATATYPE_TO_EXPORT | choice | GPKG    | Default export format |
| STYLES_TO_EXPORT   | choice | QML     | Default style format  |

---

## 9. Acceptance Criteria

### Epic: Multi-Backend Filtering

- [x] Filter works with PostgreSQL/PostGIS layers
- [x] Filter works with Spatialite layers
- [x] Filter works with OGR layers (Shapefile, GeoPackage)
- [x] Automatic backend selection based on data source
- [x] User can force specific backend per layer
- [x] Graceful fallback when psycopg2 unavailable

### Epic: Filter History

- [x] All filter operations recorded
- [x] Undo restores previous state
- [x] Redo reapplies undone operation
- [x] Intelligent context detection (source-only vs global)
- [x] UI buttons enable/disable based on history state

### Epic: Configuration System

- [x] Configuration loads from JSON
- [x] v1.0 configs auto-migrate to v2.0
- [x] Changes apply in real-time (no restart)
- [x] Invalid configs reset with backup
- [x] Metadata drives UI generation

---

## 10. Out of Scope (v2.x)

The following features are NOT included in the current version:

| Feature                   | Reason                  | Planned Version |
| ------------------------- | ----------------------- | --------------- |
| Raster filtering          | Focus on vector data    | v3.0+           |
| Cloud data sources        | Complexity              | v3.0+           |
| Plugin API for extensions | Architecture evolution  | v3.0+           |
| Query caching system      | Optimization phase      | v2.4+           |
| Parallel execution        | Performance enhancement | v2.5+           |

---

## 11. Revision History

| Version | Date     | Author    | Changes                         |
| ------- | -------- | --------- | ------------------------------- |
| 1.0     | 2023     | imagodata | Initial release                 |
| 1.5     | Oct 2024 | imagodata | Multi-backend architecture      |
| 2.0     | Dec 2025 | imagodata | Configuration v2.0, Undo/Redo   |
| 2.3     | Dec 2025 | imagodata | Dark mode, Favorites, Stability |
