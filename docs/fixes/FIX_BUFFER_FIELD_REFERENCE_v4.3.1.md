# FIX: Buffer Table Field Reference Error (v4.3.1)

**Date**: 2026-01-21  
**Severity**: CRITICAL  
**Status**: ✅ FIXED

## Issue

Buffer table creation fails with SQL error when dynamic buffer expressions reference layer fields:

```
ERROR: column ducts.homecount does not exist
LINE 7: CASE WHEN "ducts"."homecount"::numeric >=10 THEN 50 ELSE 1 END
                  ^
```

**User Impact**: 
- Dynamic buffer expressions with field references fail (e.g., `if("homecount" >= 10, 50, 1)`)
- Fallback to slow inline buffer (performance degradation)
- Potential QGIS freezes on large datasets

## Root Cause

### The Bug (v4.2.15)

In `expression_builder.py` line 871-876, field references were incorrectly prefixed with table name:

```python
# WRONG: Added table prefix in all contexts
buffer_expr_sql = re.sub(
    r'(?<![.\w])"([^"]+)"(?!\s*\.)',
    rf'"{source_table}"."\1"',
    buffer_expr_sql
)
```

This transformed:
- `"homecount"` → `"ducts"."homecount"`

### Why This Failed

In SQL `CREATE TABLE AS SELECT` context:

```sql
CREATE TABLE ... AS
SELECT 
    ST_Buffer(
        "ducts"."geom",
        CASE WHEN "ducts"."homecount" >= 10 THEN 50 ELSE 1 END  -- ❌ WRONG
    )
FROM "infra"."ducts"
```

**Problem**: Field `"homecount"` is **already implicitly scoped** to the table in the `FROM` clause.  
Adding `"ducts".` prefix makes PostgreSQL look for a column literally named `"ducts"."homecount"` (with a dot in the name), which doesn't exist.

### Correct SQL

```sql
CREATE TABLE ... AS
SELECT 
    ST_Buffer(
        "geom",
        CASE WHEN "homecount" >= 10 THEN 50 ELSE 1 END  -- ✅ CORRECT
    )
FROM "infra"."ducts"
```

Fields are **unqualified** because there's only one table in the FROM clause.

## Solution

### Code Change

**File**: `adapters/backends/postgresql/expression_builder.py`  
**Lines**: 866-868

```python
# FIX v4.2.21 (2026-01-21): DO NOT prefix field references in CREATE TABLE context
# In "SELECT ... FROM table", field references should be unqualified
# Previous regex was incorrectly adding table prefix, causing "table.field does not exist"
# The fields are already implicitly scoped to the source table in the FROM clause
# buffer_expr_sql is used as-is (e.g., "homecount" stays as "homecount")
```

### Before/After

**Before (v4.2.15-v4.2.20)**:
```python
buffer_expr_sql = qgis_expression_to_postgis(buffer_expression)
# Regex adds table prefix
buffer_expr_sql = re.sub(r'(?<![.\w])"([^"]+)"(?!\s*\.)', rf'"{source_table}"."\1"', buffer_expr_sql)
# Result: CASE WHEN "ducts"."homecount" >= 10 ... ❌
```

**After (v4.2.21+)**:
```python
buffer_expr_sql = qgis_expression_to_postgis(buffer_expression)
# No prefixing - fields stay as-is
# Result: CASE WHEN "homecount" >= 10 ... ✅
```

## Why The Regex Was Added (Context)

The regex was added in v4.2.15 to fix a **different** issue where field references in **subqueries** needed qualification. However, it was applied **too broadly**, affecting the CREATE TABLE context where it caused this bug.

### Lesson Learned

SQL field scoping rules differ by context:
- **CREATE TABLE AS SELECT FROM single_table**: Fields unqualified (implicit scope)
- **Subqueries with aliases**: Fields need qualification (`__source."field"`)
- **Multi-table JOINs**: Fields need qualification to avoid ambiguity

The fix must be **context-aware**, not a global regex.

## Testing

### Test Case 1: Simple Field Reference
```python
layer: ducts
buffer_expression: "if(\"homecount\" >= 10, 50, 1)"
```

**Expected**: Buffer table created successfully  
**Result**: ✅ PASS

### Test Case 2: Complex Expression
```python
layer: demand_points
buffer_expression: "if(\"homecount\" >= 100, 100, if(\"homecount\" >= 10, 50, 1))"
```

**Expected**: Buffer table created with nested CASE  
**Result**: ✅ PASS

### Test Case 3: Filter Chaining
```python
source: demand_points (buffer: if("homecount" >= 10, 50, 1))
filter1: ducts (intersects demand_points buffer)
filter2: sheaths (intersects ducts) -> references demand_points buffer
```

**Expected**: Both filters succeed, reusing buffer table  
**Result**: ✅ PASS

## Performance Impact

### Before Fix (Fallback to Inline)
- Buffer table creation fails
- Falls back to inline `ST_Buffer(CASE WHEN...)` in EXISTS
- Performance: O(N×M) calculations = potential freeze

### After Fix (Pre-calculated Table)
- Buffer table created successfully
- Buffers pre-calculated once, indexed
- Performance: O(N + M) = < 1 second

**Improvement**: 99.7% faster (see v4.3.0 performance metrics)

## Related Issues

- **v4.3.0**: Dynamic buffer performance optimization (parent fix)
- **v4.2.15**: Original regex introduction (caused this bug)
- **v4.2.20**: Buffer table name stability for filter chaining

## Changelog Entry

See `CHANGELOG.md` v4.3.1 for user-facing description.

---

**Fixed by**: Simon Ducourneau  
**Version**: 4.3.1  
**Commit**: [To be added]
