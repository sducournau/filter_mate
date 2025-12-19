---
sidebar_position: 1
---

# Expression Quick Reference

Fast lookup for QGIS expression syntax, operators, and functions used in FilterMate.

## Basic Syntax

### Literals

```sql
-- Numbers
42
3.14159
-17.5

-- Text (single quotes)
'Paris'
'Hello World'

-- Boolean
TRUE
FALSE

-- NULL
NULL
```

---

## Comparison Operators

| Operator | Description | Example | Result |
|----------|-------------|---------|--------|
| `=` | Equal to | `city = 'Paris'` | TRUE if match |
| `!=` or `<>` | Not equal | `status != 'inactive'` | TRUE if different |
| `>` | Greater than | `population > 100000` | TRUE if greater |
| `>=` | Greater or equal | `year >= 2020` | TRUE if ≥ |
| `<` | Less than | `price < 500000` | TRUE if less |
| `<=` | Less or equal | `age <= 18` | TRUE if ≤ |
| `BETWEEN` | Range (inclusive) | `area BETWEEN 100 AND 500` | TRUE if in range |
| `IN` | Value in list | `type IN ('A', 'B', 'C')` | TRUE if in list |
| `NOT IN` | Value not in list | `code NOT IN (1, 2, 3)` | TRUE if not in list |
| `LIKE` | Pattern match | `name LIKE 'Saint%'` | TRUE if matches |
| `ILIKE` | Case-insensitive LIKE | `name ILIKE 'paris'` | TRUE if matches |
| `IS NULL` | Check for NULL | `description IS NULL` | TRUE if NULL |
| `IS NOT NULL` | Check not NULL | `email IS NOT NULL` | TRUE if has value |

---

## Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Both conditions true | `city = 'Paris' AND population > 1000000` |
| `OR` | At least one true | `type = 'city' OR type = 'town'` |
| `NOT` | Negation | `NOT (status = 'inactive')` |

**Precedence**: `NOT` > `AND` > `OR`

**Use Parentheses** for clarity:
```sql
(city = 'Paris' OR city = 'Lyon') AND population > 50000
```

---

## String Functions

### Case Conversion

```sql
-- To uppercase
upper(name)
upper('paris') → 'PARIS'

-- To lowercase
lower(name)
lower('PARIS') → 'paris'

-- Title case (first letter uppercase)
title('hello world') → 'Hello World'
```

---

### String Manipulation

```sql
-- Concatenation
city || ', ' || country
'Paris' || ', ' || 'France' → 'Paris, France'

-- Substring (start position, length)
substr(name, 1, 5)
substr('FilterMate', 1, 6) → 'Filter'

-- Replace text
replace(name, 'Street', 'St.')
replace('Main Street', 'Street', 'St.') → 'Main St.'

-- Trim whitespace
trim('  Paris  ') → 'Paris'
ltrim('  Paris') → 'Paris'  -- Left trim
rtrim('Paris  ') → 'Paris'  -- Right trim
```

---

### String Tests

```sql
-- Length
length(name)
length('Paris') → 5

-- Starts with
name LIKE 'Saint%'

-- Ends with
name LIKE '%ville'

-- Contains
name LIKE '%bridge%'

-- Case-insensitive contains
name ILIKE '%bridge%'
```

---

### Pattern Wildcards

| Pattern | Meaning | Example | Matches |
|---------|---------|---------|---------|
| `%` | Any characters (0+) | `'A%'` | A, ABC, A123 |
| `_` | Exactly one character | `'A_C'` | ABC, A1C |
| `'A%B'` | Starts A, ends B | `'A%B'` | AB, A123B |
| `'%city%'` | Contains "city" | `'%city%'` | city, New York City |

---

## Numeric Functions

### Arithmetic

```sql
-- Basic operations
area + 100        -- Addition
price - 50000     -- Subtraction
length * width    -- Multiplication
area / 10000      -- Division (m² to hectares)
2 ^ 3             -- Exponentiation (2³ = 8)
population % 100  -- Modulo (remainder)

-- Order of operations (PEMDAS)
(price - cost) * 1.2
```

---

### Math Functions

```sql
-- Absolute value
abs(-42) → 42

-- Rounding
round(3.14159, 2) → 3.14     -- Round to 2 decimals
floor(3.7) → 3               -- Round down
ceil(3.1) → 4                -- Round up

-- Square root
sqrt(16) → 4

-- Power
pow(2, 3) → 8  -- 2³ = 8

-- Minimum/Maximum
min(10, 20, 5) → 5
max(10, 20, 5) → 20

-- Random number (0 to 1)
rand() → 0.7234...
```

---

## Date/Time Functions

### Extracting Components

```sql
-- Year
year(date_field)
year('2024-03-15') → 2024

-- Month (1-12)
month(date_field)
month('2024-03-15') → 3

-- Day (1-31)
day(date_field)
day('2024-03-15') → 15

-- Day of week (1-7, Sunday=1)
day_of_week(date_field)

-- Day of year (1-366)
day_of_year(date_field)
```

---

### Date Comparisons

```sql
-- Current date/time
now()  -- Returns current timestamp

-- Compare dates
date_field > '2024-01-01'
year(date_field) = 2024
year(date_field) BETWEEN 2020 AND 2024

-- Date within last N days
age(now(), date_field) < interval '30 days'
```

---

### Date Formatting

```sql
-- Format date
format_date(date_field, 'yyyy-MM-dd')
format_date('2024-03-15', 'MMM dd, yyyy') → 'Mar 15, 2024'

-- Common formats
'yyyy-MM-dd'      → 2024-03-15
'dd/MM/yyyy'      → 15/03/2024
'MMM dd, yyyy'    → Mar 15, 2024
```

---

## NULL Handling

### Checking for NULL

```sql
-- Test if NULL
field IS NULL
field IS NOT NULL

-- Not equal doesn't work with NULL!
❌ field = NULL     -- Always FALSE (wrong!)
✅ field IS NULL    -- Correct
```

---

### NULL Replacement

```sql
-- COALESCE: Return first non-NULL value
COALESCE(population, 0)
COALESCE(name, description, 'Unknown')

-- Example: Safe division
COALESCE(sales, 0) / COALESCE(target, 1)
```

---

## Conditional Logic

### CASE Statement

```sql
-- Simple CASE
CASE 
  WHEN population > 1000000 THEN 'Large'
  WHEN population > 100000 THEN 'Medium'
  WHEN population > 10000 THEN 'Small'
  ELSE 'Very Small'
END

-- With values
CASE type
  WHEN 'A' THEN 'Residential'
  WHEN 'B' THEN 'Commercial'
  WHEN 'C' THEN 'Industrial'
  ELSE 'Unknown'
END
```

---

### IF Statement

```sql
-- Ternary operator
if(condition, value_if_true, value_if_false)

-- Examples
if(population > 100000, 'Large', 'Small')
if(area > 0, population / area, 0)  -- Density with zero-division check
```

---

## Geometry Functions

### Measurements

```sql
-- Area (in layer's CRS units)
area($geometry)
$area  -- Shorthand

-- Perimeter/Length
perimeter($geometry)
$length

-- X/Y coordinates (centroid)
x($geometry)
y($geometry)

-- Number of vertices
num_points($geometry)
```

---

### Geometry Tests

```sql
-- Geometry type
geometry_type($geometry)
-- Returns: 'Point', 'LineString', 'Polygon', etc.

-- Is valid?
is_valid($geometry)

-- Has geometry?
$geometry IS NOT NULL
```

---

### Coordinate Access

```sql
-- Get specific point from line/polygon
point_n($geometry, 1)  -- First point

-- Start/end points
start_point($geometry)
end_point($geometry)

-- Centroid
centroid($geometry)
$x  -- Centroid X
$y  -- Centroid Y
```

---

## Aggregation Functions

Use in Field Calculator or Virtual Fields:

```sql
-- Count
count(field_name)

-- Sum
sum(field_name)

-- Average
mean(field_name)

-- Min/Max
min(field_name)
max(field_name)

-- Standard deviation
stdev(field_name)
```

---

## Field References

### Current Feature

```sql
-- By name
field_name
"field_name"  -- Use quotes if spaces/special chars

-- All fields shorthand
$fieldname

-- Example
population
"Population (2020)"  -- Spaces require quotes
```

---

### Special Variables

```sql
-- Current feature ID
$id

-- Current feature geometry
$geometry

-- Area/Length shortcuts
$area
$length
$perimeter

-- Centroid coordinates
$x
$y

-- Current layer
@layer_name

-- Current project
@project_title
```

---

## Common Patterns

### Filter by Multiple Values

```sql
-- Multiple ORs (verbose)
city = 'Paris' OR city = 'Lyon' OR city = 'Marseille'

-- Better: IN operator
city IN ('Paris', 'Lyon', 'Marseille')
```

---

### Range Queries

```sql
-- Verbose
population >= 10000 AND population <= 50000

-- Better: BETWEEN
population BETWEEN 10000 AND 50000
```

---

### Safe Division (Avoid Divide by Zero)

```sql
-- Without protection (may error)
❌ population / area

-- With NULL check
✅ CASE WHEN area > 0 THEN population / area ELSE 0 END

-- With COALESCE
✅ population / COALESCE(NULLIF(area, 0), 1)
```

---

### Case-Insensitive Text Comparison

```sql
-- Convert both to uppercase
upper(city) = upper('paris')
upper(city) = 'PARIS'

-- Or use ILIKE (PostgreSQL/Spatialite)
city ILIKE 'paris'
```

---

### Percentage Calculation

```sql
-- Percentage of total
(field_value / total_value) * 100

-- Example: Approval rate
(votes_yes / (votes_yes + votes_no)) * 100
```

---

### Date Range (Last N Days)

```sql
-- Last 30 days
date_field > now() - interval '30 days'

-- This year
year(date_field) = year(now())

-- Last year
year(date_field) = year(now()) - 1
```

---

## Performance Tips

### Optimize Expression Order

```sql
-- ✅ Good: Filter cheapest condition first
population > 100000 AND expensive_spatial_function()

-- ❌ Bad: Expensive operation first
expensive_spatial_function() AND population > 100000
```

---

### Use Indexes

If filtering frequently on a field, ensure it's indexed in the database:
```sql
-- PostgreSQL
CREATE INDEX idx_population ON table_name(population);
```

---

### Avoid Functions in Comparisons (When Possible)

```sql
-- ❌ Slower: Function on field
upper(city) = 'PARIS'

-- ✅ Faster: Store uppercase in separate field
city_upper = 'PARIS'
```

---

## Debugging Expressions

### Test in Expression Dialog

1. Open **Attribute Table**
2. Click **Field Calculator**
3. Enter expression in top panel
4. Click **Preview** to test on first feature

---

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `syntax error` | Invalid syntax | Check quotes, parentheses |
| `column not found` | Typo in field name | Check spelling, use quotes |
| `type mismatch` | Wrong data type | Cast or convert types |
| `division by zero` | Dividing by 0 | Use NULLIF or CASE |

---

## Expression Examples

### Real-World Filters

```sql
-- Urban areas with high density
population > 50000 AND (population / area) > 1000

-- Recent residential developments
land_use = 'residential' AND year_built >= 2020

-- Properties in price range near transit
price BETWEEN 200000 AND 400000 
AND EXISTS (SELECT 1 FROM transit_stations WHERE ...)

-- Roads needing maintenance
surface_type IN ('gravel', 'dirt') 
AND condition = 'poor' 
AND last_repaired < '2020-01-01'

-- Environmental risk areas
land_use = 'industrial' 
AND distance_to_water < 100
AND permits IS NULL
```

---

## See Also

- [Spatial Predicates Reference](./spatial-predicates.md)
- [Filtering Basics](../../user-guide/filtering-basics.md)
- [QGIS Expression Documentation](https://docs.qgis.org/latest/en/docs/user_manual/expressions/index.html)

---

## Contribute

Found an error or have a useful pattern to share? [Submit on GitHub](https://github.com/sducournau/filter_mate/issues)
