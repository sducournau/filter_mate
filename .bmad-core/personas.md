# FilterMate - User Personas

## 📋 Document Info

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Last Updated** | December 20, 2025 |

---

## Primary Personas

### 👩‍💻 Persona 1: Marie - GIS Analyst

**Demographics**
| Field | Value |
|-------|-------|
| Role | Environmental GIS Analyst |
| Experience | 5+ years with QGIS |
| Organization | Environmental consulting firm |
| Technical Level | Intermediate |

**Goals**
- Quick data exploration and analysis
- Generate filtered datasets for reports
- Perform spatial queries (buffer, intersection)
- Export data in multiple formats

**Pain Points**
- Complex SQL queries are time-consuming
- Switching between data sources breaks workflow
- Large datasets cause performance issues
- Losing filters when closing projects

**FilterMate Benefits**
- ✅ Intuitive UI for complex spatial queries
- ✅ Automatic backend selection for performance
- ✅ Filter favorites for reusable queries
- ✅ Undo/redo for safe exploration

**Typical Workflow**
1. Load multiple vector layers
2. Select features by attribute
3. Apply spatial buffer
4. Filter related layers
5. Export filtered data for report

**Quote**
> "I need to quickly subset data for environmental impact reports. Complex queries shouldn't require writing SQL every time."

---

### 👨‍💼 Persona 2: Thomas - Spatial Data Engineer

**Demographics**
| Field | Value |
|-------|-------|
| Role | Spatial Database Engineer |
| Experience | 8+ years with PostgreSQL/PostGIS |
| Organization | Large municipality |
| Technical Level | Expert |

**Goals**
- Optimize query performance
- Integrate QGIS with enterprise databases
- Automate repetitive spatial operations
- Control backend behavior precisely

**Pain Points**
- Generic tools don't leverage PostgreSQL features
- Poor performance on million-feature datasets
- Lack of control over query execution
- Integration issues with existing infrastructure

**FilterMate Benefits**
- ✅ PostgreSQL materialized views for speed
- ✅ Forced backend selection per layer
- ✅ Sub-second queries on large datasets
- ✅ UNLOGGED tables for temporary data

**Typical Workflow**
1. Connect to PostGIS database
2. Force PostgreSQL backend
3. Run complex spatial operations
4. Verify MV and index creation
5. Export optimized results

**Quote**
> "I manage datasets with millions of features. I need a tool that actually uses PostgreSQL properly, not just basic queries."

---

### 👩‍🎓 Persona 3: Julie - Urban Planner

**Demographics**
| Field | Value |
|-------|-------|
| Role | Urban Planning Officer |
| Experience | 2 years with GIS |
| Organization | City planning department |
| Technical Level | Beginner |

**Goals**
- Simple data filtering
- Create maps for presentations
- Find features near specific locations
- Share filtered data with colleagues

**Pain Points**
- QGIS expression syntax is confusing
- Afraid of breaking data
- Too many options overwhelm
- Needs guided workflow

**FilterMate Benefits**
- ✅ Simple point-and-click filtering
- ✅ Undo/redo for safe exploration
- ✅ Clear visual feedback
- ✅ Filter favorites as templates

**Typical Workflow**
1. Open project with city layers
2. Select a neighborhood
3. Find buildings within 500m
4. Save filter for reuse
5. Export for presentation

**Quote**
> "I just need to find all buildings near the new transit station. I don't want to learn SQL to do that."

---

## Secondary Personas

### 🔬 Persona 4: Alex - Research Scientist

**Demographics**
| Field | Value |
|-------|-------|
| Role | Climate Research Scientist |
| Experience | 10+ years data analysis |
| Organization | University research lab |
| Technical Level | Advanced (Python, R) |

**Goals**
- Process large climate datasets
- Reproducible spatial analysis
- Integrate with Python workflows
- Batch processing capabilities

**FilterMate Benefits**
- ✅ Handles large datasets efficiently
- ✅ Filter history for reproducibility
- ✅ Export in multiple formats
- ✅ Consistent behavior across backends

---

### 🏗️ Persona 5: Marco - Field Surveyor

**Demographics**
| Field | Value |
|-------|-------|
| Role | Land Surveyor |
| Experience | 15+ years, 3 years GIS |
| Organization | Surveying company |
| Technical Level | Basic |

**Goals**
- Work with local Shapefiles
- Quick data subset for fieldwork
- Export to GPS-compatible formats
- Work offline without database

**FilterMate Benefits**
- ✅ Works with any file format
- ✅ No database required
- ✅ OGR backend for compatibility
- ✅ Simple export options

---

## Persona Matrix

| Persona | Data Size | Tech Level | Backend | Key Feature |
|---------|-----------|------------|---------|-------------|
| Marie (Analyst) | Medium | Intermediate | Auto | Spatial queries |
| Thomas (Engineer) | Large | Expert | PostgreSQL | Performance |
| Julie (Planner) | Small | Beginner | OGR | Simple UI |
| Alex (Scientist) | Large | Advanced | Mixed | Reproducibility |
| Marco (Surveyor) | Small | Basic | OGR | Offline |

---

## Feature Prioritization by Persona

| Feature | Marie | Thomas | Julie | Alex | Marco |
|---------|:-----:|:------:|:-----:|:----:|:-----:|
| Spatial predicates | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Buffer operations | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| PostgreSQL MVs | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| Filter favorites | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| Undo/redo | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Dark mode | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ |
| Export options | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Backend control | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ |
