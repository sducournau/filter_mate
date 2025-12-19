---
sidebar_position: 1.5
---

# 3-Minute Quick Start

Get your first filter working in just 3 minutes!

:::info What You'll Learn
- How to open FilterMate
- How to apply an attribute filter
- How to see results on the map
:::

**Time**: ⏱️ 3 minutes  
**Difficulty**: ⭐ Absolute Beginner  
**Prerequisites**: QGIS installed + any vector layer loaded

---

## The Goal

**Filter a cities layer to show only large cities** (population > 100,000)

---

## Step 1: Open FilterMate (30 seconds)

1. Look for the FilterMate icon in your QGIS toolbar:

   <img src="/filter_mate/icons/logo.png" alt="FilterMate icon" width="32"/>

2. Click it, or go to **Vector** → **FilterMate**
3. The FilterMate panel appears (usually on the right side)

:::tip Panel Position
You can drag the panel to any edge of your QGIS window, or make it floating.
:::

---

## Step 2: Select Your Layer (30 seconds)

In the **Layer Selection** dropdown at the top of the FilterMate panel:

1. Click the dropdown
2. Choose your cities/municipalities layer
3. FilterMate analyzes the layer and shows:
   - Backend type (PostgreSQL⚡ / Spatialite / OGR)
   - Feature count (e.g., "450 features")
   - Available fields

**Don't have a cities layer?**
- Use any layer with a numeric field
- Or download our [sample dataset](https://github.com/sducournau/filter_mate/releases) (5 MB)

---

## Step 3: Write a Filter Expression (1 minute)

Now let's filter to show only features where population is greater than 100,000.

### Find the Expression Box

In the FilterMate panel, look for the **expression builder** - it's the text input area in the FILTERING or EXPLORING tab.

### Type Your Expression

```sql
"population" > 100000
```

:::caution Field Names
- Field names are **case-sensitive**
- Use **double quotes** around field names: `"population"`
- Use **single quotes** for text values: `'Paris'`
:::

**Alternative Expressions** (adapt to your data):

<details>
<summary>For a layer with different field names</summary>

```sql
-- If your field is called "POPULATION" (uppercase)
"POPULATION" > 100000

-- If your field is called "pop" or "habitants"
"pop" > 100000
"habitants" > 100000

-- Multiple conditions
"population" > 100000 AND "country" = 'France'
```

</details>

---

## Step 4: Apply the Filter (30 seconds)

1. Look for the **Apply Filter** button (usually has a funnel icon 🔽)
2. Click it
3. **Watch the magic happen!** ✨

**What you should see:**
- The map updates to show only filtered features
- The feature count updates (e.g., "Showing 42 of 450 features")
- Filtered features are highlighted on the map

---

## ✅ Success! What Just Happened?

FilterMate applied your expression to every feature in the layer:
- Features with `population > 100000`: ✅ **Shown**
- Features with `population ≤ 100000`: ❌ **Hidden**

The original data is **unchanged** - FilterMate creates a temporary filtered view.

---

## 🎓 What's Next?

### Learn More Filtering Techniques

**Geometric Filtering** (10 min)  
Find features based on location and spatial relationships  
[▶️ Your First Geometric Filter](./first-filter)

**Export Your Results** (5 min)  
Save filtered features to GeoPackage, Shapefile, or PostGIS  
[▶️ Export Guide](../user-guide/export-features)

**Undo/Redo** (3 min)  
Navigate your filter history with intelligent undo/redo  
[▶️ Filter History](../user-guide/filter-history)

### Explore Real-World Workflows

**Urban Planning** (10 min)  
Find properties near transit stations  
[▶️ Transit-Oriented Development](../workflows/urban-planning-transit)

**Real Estate** (8 min)  
Multi-criteria property filtering  
[▶️ Market Analysis](../workflows/real-estate-analysis)

---

## 🆘 Troubleshooting

### "No features match"

**Possible causes:**
1. **Expression syntax error** - Check for typos
2. **Field name incorrect** - Right-click layer → Open Attribute Table to verify field names
3. **Threshold too high** - Try a lower value: `"population" > 10000`

**Quick fix:**
```sql
-- Try this simpler expression first
"population" IS NOT NULL
```

This should show all features with a population value.

---

### "Field not found" error

**Cause**: Field name doesn't match exactly

**Solution:**
1. Right-click your layer → **Open Attribute Table**
2. Find the column with population data
3. Note the **exact** field name (including capitalization)
4. Use that exact name in quotes: `"YourFieldName"`

---

### Can't find the Apply button

**The Apply Filter button location depends on your configuration:**
- **Bottom of panel** (default)
- **Top near layer selector**
- **Left or right side** (if configured)

Look for a button with a funnel icon (🔽) or the text "Apply Filter".

---

## 💡 Pro Tips

### 1. Use the Field List
Most FilterMate interfaces show a list of available fields. Click a field name to insert it into your expression automatically.

### 2. Check Expression Validity
FilterMate validates your expression in real-time:
- ✅ Green checkmark = Valid
- ❌ Red X = Syntax error (hover for details)

### 3. Combine with Map Selection
You can combine FilterMate filters with QGIS's manual selection tool:
1. Apply FilterMate filter
2. Use Select tool to refine further
3. Only filtered features are selectable

---

## 🎉 Congratulations!

You've successfully applied your first filter! You're now ready to explore FilterMate's more advanced features.

**Continue Learning:**
- [Filtering Basics](../user-guide/filtering-basics) - Master QGIS expressions
- [Geometric Filtering](../user-guide/geometric-filtering) - Spatial relationships
- [All Workflows](../workflows/) - Real-world scenarios

**Need Help?**
- 📖 [User Guide](../user-guide/introduction)
- 🐛 [Report Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 [Ask Questions](https://github.com/sducournau/filter_mate/discussions)
