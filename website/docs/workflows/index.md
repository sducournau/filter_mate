---
sidebar_position: 1
---

# Real-World Workflows

Practical, scenario-based tutorials showing how to use FilterMate for common GIS tasks.

## About These Workflows

Each workflow tutorial is designed to:
- ✅ **Solve a real-world problem** faced by GIS professionals
- ✅ **Teach multiple FilterMate features** in practical context
- ✅ **Be completed in 10-15 minutes** with provided sample data
- ✅ **Include best practices** for performance and accuracy

## Available Workflows

### 🏙️ Urban Planning & Development

**[Finding Properties Near Transit](/docs/workflows/urban-planning-transit)**
- **Scenario**: Identify all residential parcels within 500m of subway stations
- **Skills**: Buffer operations, spatial predicates, multi-layer filtering
- **Backend**: PostgreSQL (recommended for large parcel datasets)
- **Time**: ~10 minutes
- **Difficulty**: ⭐⭐ Intermediate

---

### 🌳 Environmental Analysis

**[Protected Zone Impact Assessment](/docs/workflows/environmental-protection)**
- **Scenario**: Find industrial sites within protected water buffer zones
- **Skills**: Geometric filtering, attribute constraints, geometry repair
- **Backend**: Spatialite (good for regional datasets)
- **Time**: ~15 minutes
- **Difficulty**: ⭐⭐⭐ Advanced

---

### 🚒 Emergency Services

**[Service Coverage Analysis](/docs/workflows/emergency-services)**
- **Scenario**: Identify areas more than 5km from nearest fire station
- **Skills**: Inverse spatial queries, distance calculations, export results
- **Backend**: OGR (universal compatibility)
- **Time**: ~12 minutes
- **Difficulty**: ⭐⭐ Intermediate

---

### 🏠 Real Estate Analysis

**[Market Filtering & Export](/docs/workflows/real-estate-analysis)**
- **Scenario**: Filter properties by price, area, and school proximity
- **Skills**: Combined attribute + geometric filtering, history management
- **Backend**: Multi-backend comparison
- **Time**: ~8 minutes
- **Difficulty**: ⭐ Beginner

---

### 🚗 Transportation Planning

**[Road Network Data Preparation](/docs/workflows/transportation-planning)**
- **Scenario**: Export road segments within municipality with specific attributes
- **Skills**: Attribute filtering, CRS transformation, batch export
- **Backend**: Any (focuses on export features)
- **Time**: ~10 minutes
- **Difficulty**: ⭐ Beginner

---

## Workflow Structure

Each tutorial follows a consistent format:

1. **Scenario Overview** - The real-world problem
2. **Prerequisites** - Required data and setup
3. **Step-by-Step Instructions** - Detailed walkthrough with screenshots
4. **Understanding the Results** - Interpreting output
5. **Best Practices** - Tips for optimization
6. **Common Issues** - Troubleshooting guide
7. **Next Steps** - Related workflows and advanced techniques

## Sample Data

Most workflows can be completed with **OpenStreetMap data**:

- Download from [Geofabrik](https://download.geofabrik.de/)
- Use QGIS **QuickOSM** plugin to fetch specific areas
- Or use your own project data

:::tip Getting Sample Data
Install the **QuickOSM** plugin in QGIS:
1. Plugins → Manage and Install Plugins
2. Search "QuickOSM"
3. Install and restart QGIS
4. Vector → QuickOSM → Quick Query
:::

## Choose Your Learning Path

### New to FilterMate?
Start with **beginner workflows** (⭐):
1. [Real Estate Analysis](/docs/workflows/real-estate-analysis) - Simple filtering
2. [Transportation Planning](/docs/workflows/transportation-planning) - Export focus

### Comfortable with Basics?
Try **intermediate workflows** (⭐⭐):
1. [Urban Planning](/docs/workflows/urban-planning-transit) - Spatial operations
2. [Emergency Services](/docs/workflows/emergency-services) - Distance analysis

### Ready for Complex Tasks?
Tackle **advanced workflows** (⭐⭐⭐):
1. [Environmental Analysis](/docs/workflows/environmental-protection) - Multi-criteria filtering

---

## Workflow Goals

By completing these workflows, you'll learn:

- 🎯 **Efficient filtering** - Attribute and geometric techniques
- 📐 **Spatial analysis** - Buffers, predicates, distance calculations
- 🗺️ **Multi-layer operations** - Working with related datasets
- 💾 **Export strategies** - Format selection and CRS transformation
- ⚡ **Performance optimization** - Backend selection and tuning
- 🔧 **Troubleshooting** - Common issues and solutions
- 📝 **History management** - Undo/redo system

---

## Contributing Workflows

Have a real-world use case? We'd love to add it!

**Submit your workflow:**
1. Open an issue on [GitHub](https://github.com/sducournau/filter_mate/issues)
2. Describe your scenario and data requirements
3. Include screenshots if possible
4. We'll help you create a tutorial

---

## Need Help?

- 📖 **Reference Docs**: [User Guide](/docs/user-guide/introduction)
- 🐛 **Report Issues**: [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Ask Questions**: [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 🎥 **Watch Tutorial**: [YouTube Video](https://www.youtube.com/watch?v=2gOEPrdl2Bo)
