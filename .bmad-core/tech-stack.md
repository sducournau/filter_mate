# FilterMate - Technology Stack

## 📋 Document Info

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Last Updated** | December 20, 2025 |

---

## 1. Core Technologies

### 1.1 Programming Language

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.7+ | Primary language |
| **SQL** | - | Database queries |

**Python Version Requirements**:
- Minimum: Python 3.7 (matches QGIS 3.0)
- Tested on: Python 3.9, 3.10, 3.11
- Future: Will follow QGIS requirements

### 1.2 Platform Framework

| Technology | Version | Purpose |
|------------|---------|---------|
| **QGIS** | 3.0+ | Host application |
| **PyQGIS** | 3.0+ | QGIS Python API |
| **PyQt5** | 5.x | UI framework |
| **Qt** | 5.x | Cross-platform GUI |

---

## 2. Database Technologies

### 2.1 Primary Databases

| Database | Required | Purpose | Module |
|----------|----------|---------|--------|
| **PostgreSQL** | ❌ Optional | High-performance backend | psycopg2 |
| **PostGIS** | ❌ Optional | Spatial extension | - |
| **Spatialite** | ✅ Built-in | Local spatial database | sqlite3 |
| **SQLite** | ✅ Built-in | Metadata storage | sqlite3 |

### 2.2 File Formats (via OGR)

| Format | Extension | Read | Write |
|--------|-----------|:----:|:-----:|
| GeoPackage | .gpkg | ✅ | ✅ |
| Shapefile | .shp | ✅ | ✅ |
| GeoJSON | .geojson | ✅ | ✅ |
| KML | .kml | ✅ | ✅ |
| DXF | .dxf | ✅ | ✅ |
| CSV | .csv | ✅ | ✅ |
| File GDB | .gdb | ✅ | ❌ |

---

## 3. Python Dependencies

### 3.1 Required Dependencies (Bundled with QGIS)

| Package | Purpose |
|---------|---------|
| `qgis.core` | Core QGIS functionality |
| `qgis.gui` | GUI components |
| `qgis.PyQt.QtCore` | Qt core classes |
| `qgis.PyQt.QtWidgets` | UI widgets |
| `qgis.PyQt.QtGui` | Graphics classes |
| `sqlite3` | SQLite/Spatialite access |
| `json` | Configuration handling |
| `os`, `sys` | System operations |
| `typing` | Type hints |
| `datetime` | Timestamps |
| `logging` | Logging system |

### 3.2 Optional Dependencies

| Package | Purpose | Fallback |
|---------|---------|----------|
| `psycopg2` | PostgreSQL connection | Use Spatialite/OGR |
| `psycopg2-binary` | Pre-compiled psycopg2 | Same as above |

### 3.3 Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing framework |
| `pytest-cov` | Coverage reporting |
| `pylint` | Code quality |
| `black` | Code formatting |
| `mypy` | Type checking |

---

## 4. Architecture Patterns

### 4.1 Design Patterns Used

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Factory** | `backends/factory.py` | Backend selection |
| **Abstract Base Class** | `backends/base_backend.py` | Backend interface |
| **Observer** | Signal/Slot system | Event handling |
| **Singleton** | Configuration loader | Global config |
| **Strategy** | Backend implementations | Algorithm selection |
| **Command** | Filter history | Undo/redo |
| **Facade** | `filter_mate_app.py` | Simplify complexity |

### 4.2 QGIS-Specific Patterns

| Pattern | Usage |
|---------|-------|
| **QgsTask** | Async operations |
| **QgsProject** | Project persistence |
| **QgsVectorLayer** | Layer operations |
| **QgsExpression** | Filter expressions |
| **QgsCoordinateTransform** | CRS conversion |

---

## 5. Build & Distribution

### 5.1 Build Tools

| Tool | Purpose |
|------|---------|
| `pyrcc5` | Compile Qt resources |
| `pyuic5` | Compile UI files |
| `lrelease` | Compile translations |

### 5.2 Distribution

| Method | Location |
|--------|----------|
| GitHub Releases | https://github.com/sducournau/filter_mate |
| QGIS Plugin Repository | (Pending) |
| Manual Install | Copy to plugins folder |

### 5.3 Package Structure

```
filter_mate/
├── __init__.py
├── filter_mate.py
├── filter_mate_app.py
├── filter_mate_dockwidget.py
├── filter_mate_dockwidget_base.py
├── resources.py            # Compiled resources
├── metadata.txt            # Plugin metadata
├── config/
├── modules/
├── icons/
├── i18n/
└── ...
```

---

## 6. Testing Stack

### 6.1 Testing Framework

| Tool | Purpose |
|------|---------|
| `pytest` | Test runner |
| `pytest-cov` | Coverage |
| `pytest-mock` | Mocking |
| `unittest.mock` | QGIS mocking |

### 6.2 Test Categories

| Category | Location | Description |
|----------|----------|-------------|
| Unit | `tests/test_*.py` | Individual functions |
| Integration | `tests/integration/` | Component interaction |
| Performance | `tests/benchmark_*.py` | Speed benchmarks |

### 6.3 CI/CD

| Platform | Purpose |
|----------|---------|
| GitHub Actions | Automated testing |
| Local scripts | Development testing |

---

## 7. Internationalization

### 7.1 Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English | en | ✅ Complete |
| French | fr | ✅ Complete |
| German | de | ✅ Complete |
| Spanish | es | ✅ Complete |
| Italian | it | ✅ Complete |
| Dutch | nl | ✅ Complete |
| Portuguese | pt | ✅ Complete |

### 7.2 Translation Tools

| Tool | Purpose |
|------|---------|
| Qt Linguist | Translation editing |
| `lrelease` | Compile .ts → .qm |
| `pylupdate5` | Extract strings |

---

## 8. Spatial Operations

### 8.1 Geometric Predicates

| Predicate | PostgreSQL | Spatialite | OGR |
|-----------|------------|------------|-----|
| `ST_Intersects` | ✅ | ✅ `Intersects` | ✅ |
| `ST_Within` | ✅ | ✅ `Within` | ✅ |
| `ST_Contains` | ✅ | ✅ `Contains` | ✅ |
| `ST_Overlaps` | ✅ | ✅ `Overlaps` | ✅ |
| `ST_Touches` | ✅ | ✅ `Touches` | ✅ |
| `ST_Crosses` | ✅ | ✅ `Crosses` | ✅ |
| `ST_Disjoint` | ✅ | ✅ `Disjoint` | ✅ |

### 8.2 Spatial Indexes

| Backend | Index Type | Creation |
|---------|------------|----------|
| PostgreSQL | GIST | Automatic on MV |
| Spatialite | R-tree | Automatic on temp |
| OGR | .qix/.sbn | Via QGIS |

### 8.3 Geometry Functions

| Function | PostgreSQL | Spatialite | QGIS |
|----------|------------|------------|------|
| Buffer | `ST_Buffer` | `Buffer` | `buffer()` |
| Area | `ST_Area` | `Area` | `$area` |
| Length | `ST_Length` | `Length` | `$length` |
| Centroid | `ST_Centroid` | `Centroid` | `centroid()` |
| Transform | `ST_Transform` | `Transform` | Transform |
| MakeValid | `ST_MakeValid` | `MakeValid` | - |

---

## 9. Performance Characteristics

### 9.1 Backend Performance Comparison

| Operation | PostgreSQL | Spatialite | OGR |
|-----------|------------|------------|-----|
| 1M feature count | 5ms | 500ms | 10s |
| 100k intersect | 0.5s | 5s | 30s |
| MV creation | 18s | N/A | N/A |
| Index creation | 2s | 1s | 5s |

### 9.2 Memory Usage

| Component | Typical | Peak |
|-----------|---------|------|
| Plugin base | 50MB | 100MB |
| 100k features | 200MB | 400MB |
| 1M features | 500MB | 1GB |

---

## 10. Security Considerations

### 10.1 Database Security

| Concern | Mitigation |
|---------|------------|
| SQL Injection | Parameterized queries |
| Credentials | QGIS credential store |
| Connection | SSL where supported |

### 10.2 File Security

| Concern | Mitigation |
|---------|------------|
| Path traversal | Path validation |
| Temp files | Cleanup in finally blocks |
| Permissions | OS-level handling |

---

## 11. Future Technology Considerations

### 11.1 Under Evaluation

| Technology | Purpose | Timeline |
|------------|---------|----------|
| asyncio | Parallel operations | Q2 2026 |
| DuckDB | Analytics backend | Q3 2026 |
| GeoParquet | Modern format | Q4 2026 |

### 11.2 QGIS Version Support

| QGIS Version | Python | Support Status |
|--------------|--------|----------------|
| 3.0 - 3.16 | 3.7 | ✅ Supported |
| 3.18 - 3.28 | 3.9 | ✅ Supported |
| 3.30+ | 3.10+ | ✅ Supported |
| 4.0 (future) | TBD | 🔄 Will adapt |
