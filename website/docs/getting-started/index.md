---
sidebar_position: 1
---

# Getting Started

Welcome to FilterMate! These tutorials will help you become productive quickly.

## Tutorials in This Section

### [Quick Start](./quick-start.md)
**Time: 5 minutes**

Learn the essential workflow:
- Opening FilterMate and selecting layers
- Creating your first attribute filter
- Understanding backend selection
- Exporting filtered results

### [Your First Filter](./first-filter.md)
**Time: 10-15 minutes**

Complete step-by-step tutorial:
- Setting up a geometric filter
- Using buffer operations
- Working with spatial predicates
- Reviewing and exporting results

## Before You Start

Make sure you have:

- ✅ **QGIS 3.x** installed
- ✅ **FilterMate plugin** installed ([Installation Guide](../installation.md))
- ✅ **Vector layer** loaded in your project

## Performance Tips

For best results with large datasets:

- 📦 **Medium datasets** (&lt;50k features): Spatialite/OGR work well
- ⚡ **Large datasets** (&gt;50k features): Install `psycopg2` for PostgreSQL support
- 🗄️ **Very large datasets** (&gt;1M features): Use PostGIS layers

## Video Tutorial

Prefer video learning? Watch our complete walkthrough:

[![FilterMate Demo](https://img.youtube.com/vi/2gOEPrdl2Bo/0.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Next Steps

After completing these tutorials:

1. **[Interface Overview](../user-guide/interface-overview.md)** - Explore all UI components
2. **[Filtering Basics](../user-guide/filtering-basics.md)** - Master attribute filtering
3. **[Geometric Filtering](../user-guide/geometric-filtering.md)** - Advanced spatial operations
4. **[Backends Overview](../backends/overview.md)** - Understand performance optimization

:::tip Need Help?
Check the [Troubleshooting Guide](../advanced/troubleshooting.md) or visit [GitHub Issues](https://github.com/sducournau/filter_mate/issues).
:::
