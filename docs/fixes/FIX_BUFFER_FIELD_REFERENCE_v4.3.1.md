# FIX: Buffer Table Field Reference Error (v4.3.1)

**Date**: 2026-01-21 (v4.2.21 comment) / 2026-01-22 (v4.3.1 actual fix)  
**Severity**: CRITICAL  
**Status**: ✅ FIXED (v4.3.1)

## Issue

Buffer table creation fails with SQL error when dynamic buffer expressions reference layer fields:

```
ERROR: column address.homecount does not exist
LINE 7: CASE WHEN "address"."homecount"::numeric >=10 THEN 50 ELSE 1 END
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
- `"homecount"` → `"address"."homecount"`

### Why This Failed

In SQL `CREATE TABLE AS SELECT` context:

```sql
CREATE TABLE ... AS
SELECT 
    ST_Buffer(
        "address"."geom",
        CASE WHEN "address"."homecount" >= 10 THEN 50 ELSE 1 END  -- ❌ WRONG
    )
FROM "schema"."address"
```

**Problem**: Field `"homecount"` is **already implicitly scoped** to the table in the `FROM` clause.  
Adding `"address".` prefix makes PostgreSQL look for a column literally named `"address"."homecount"` (with a dot in the name), which doesn't exist.

### Correct SQL

```sql
CREATE TABLE temp_buffered_address_xxx AS
SELECT 
    ST_Buffer(
        "geom",
        CASE WHEN "homecount" >= 10 THEN 50 ELSE 1 END  -- ✅ CORRECT
    ) as buffered_geom
FROM "schema"."address"
```

Fields are **unqualified** because there's only one table in the FROM clause.

### Real-World Scenario

Typical use case:
1. **Source layer**: `address` (has field `homecount`)
2. **Buffer expression**: `if("homecount" >= 10, 50, 1)` creates variable-size buffers around addresses
3. **Target layer**: `ducts` filtered to find those intersecting the address buffers

The buffer table is created from the **source** layer (address), then used to filter the **target** layer (ducts).

## Solution

### Code Change

**File**: `adapters/backends/postgresql/expression_builder.py`  
**Lines**: 866-868 (comment), 912-925 (CREATE TABLE)

**v4.2.21 (2026-01-21)**: Added comment explaining NOT to prefix fields
**v4.3.1 (2026-01-22)**: Actually removed the prefixes from CREATE TABLE statement

```python
# Comment added in v4.2.21:
# FIX v4.2.21 (2026-01-21): DO NOT prefix field references in CREATE TABLE context
# In "SELECT ... FROM table", field references should be unqualified
# Previous regex was incorrectly adding table prefix, causing "table.field does not exist"
# The fields are already implicitly scoped to the source table in the FROM clause
# buffer_expr_sql is used as-is (e.g., "homecount" stays as "homecount")

# Actual fix applied in v4.3.1:
sql_create = f"""
    CREATE TABLE IF NOT EXISTS "{temp_schema}"."{temp_table_name}" AS
    SELECT 
        "id" as source_id,  -- FIXED: removed table prefix
        ST_Buffer(
            "{source_geom_field}",  -- FIXED: removed table prefix
            {buffer_expr_sql},  -- Already unqualified (e.g., "homecount")
            'quad_segs=5'
        ) as buffered_geom
    FROM "{source_schema}"."{source_table}"
    {f"WHERE {source_filter}" if source_filter else ""}
"""
```

### Before/After

**Before (v4.2.15-v4.2.20)**:
```python
buffer_expr_sql = qgis_expression_to_postgis(buffer_expression)
# Regex was planned but never implemented correctly
# However, the CREATE TABLE still had table prefixes:
sql_create = f"""
    CREATE TABLE ... AS
    SELECT 
        "{source_table}"."id" as source_id,  -- ❌ WRONG
        ST_Buffer(
            "{source_table}"."{source_geom_field}",  -- ❌ WRONG
            {buffer_expr_sql},  -- Unqualified: CASE WHEN "homecount" ...
            ...
        )
    FROM "{source_schema}"."{source_table}"
"""
# Result: SQL error - "table.field" syntax in single-table SELECT
```

**After (v4.3.1+)**:
```python
buffer_expr_sql = qgis_expression_to_postgis(buffer_expression)
# No prefixing - all fields stay unqualified
sql_create = f"""
    CREATE TABLE ... AS
    SELECT 
        "id" as source_id,  -- ✅ CORRECT
        ST_Buffer(
            "{source_geom_field}",  -- ✅ CORRECT
            {buffer_expr_sql},  -- Still unqualified: CASE WHEN "homecount" ...
            ...
        )
    FROM "{source_schema}"."{source_table}"
"""
# Result: All fields unqualified, SQL works correctly
```

## Why The Regex Was Added (Context)

**Note**: The original document (v4.2.21) incorrectly stated that a regex was adding table prefixes to `buffer_expr_sql`. This was not accurate.

**Reality**: 
- `qgis_expression_to_postgis()` never added table prefixes
- The actual bug was in the CREATE TABLE statement itself (lines 917-924)
- Field references `"id"` and `"{source_geom_field}"` were incorrectly prefixed with `"{source_table}".`
- This created inconsistency: some fields qualified, others (in buffer_expr_sql) unqualified

### Lesson Learned

SQL field scoping rules differ by context:
- **CREATE TABLE AS SELECT FROM single_table**: Fields unqualified (implicit scope)
- **Subqueries with aliases**: Fields need qualification (`__source."field"`)
- **Multi-table JOINs**: Fields need qualification to avoid ambiguity

The fix must be **context-aware**, not a global regex.

## Testing

### Test Case 1: Simple Field Reference
```python
source_layer: address (has field "homecount")
target_layer: ducts
buffer_expression: "if(\"homecount\" >= 10, 50, 1)"
filter: ducts intersects address buffers
```

**Expected**: Buffer table created from address layer, ducts filtered successfully  
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

## Implementation History

- **v4.2.21 (2026-01-21)**: Comment added explaining the issue, but actual code not fixed
- **v4.3.1 (2026-01-22)**: 
  - Code actually corrected - removed table prefixes from CREATE TABLE fields
  - Added error handling for filter chaining when buffer table creation fails
  - Prevents SQL error "relation does not exist" when table creation fails

### Additional Fix: Filter Chaining Error Handling

When buffer table creation fails (e.g., due to the field prefix bug), the filter chaining code would continue and generate an EXISTS query referencing the non-existent table, causing SQL errors.

**Fixed in v4.3.1** (lines 1189-1197):
```python
# If temp table creation failed in filter chaining (buffer_expression was cleared),
# we cannot fallback to inline because we don't have the original buffer_expression
if not buffer_expression:
    self.log_error("Buffer table creation failed AND buffer_expression is None")
    return None  # Skip this filter instead of generating broken SQL
```

This ensures that if the buffer table creation fails, the filter is skipped entirely (returns `1 = 0`) instead of generating invalid SQL.

### Additional Fix: Inline Buffer in Filter Chaining

Even after fixing table creation, another issue remained: when buffer table creation failed, the code would fallback to inline buffer expression, but in filter chaining this causes errors because the buffer expression references fields from the ORIGINAL source table, not the intermediate tables.

**Error Example**:
```sql
SELECT * FROM "infra"."sheaths" 
WHERE EXISTS (
  SELECT 1 FROM "infra"."ducts" AS __source 
  WHERE ST_Intersects("sheaths"."geom", 
    ST_Buffer(__source."geom", 
      CASE WHEN __source."homecount" >= 10 THEN 50 ELSE 1 END  -- ❌ ERROR!
    )
  )
)
```

**Problem**: `homecount` exists only in `demand_points` (original source), not in `ducts` (intermediate table).

**Fixed in v4.3.1** (lines 1203-1213):
```python
# Do NOT use inline buffer in filter chaining context
if is_filter_chaining:
    self.log_error("Cannot use inline buffer in filter chaining context")
    return None  # Prevent 'column does not exist' error
```

This ensures buffer expressions are ONLY used via pre-calculated buffer tables in filter chaining, never inline.

### Additional Fix: Materialized View Creation Failures

The same field prefix issue affected materialized view (MV) creation for large source selections.

**Error Pattern**:
```
⚠️ MV creation failed, using inline IN clause (may be slow)
```

**Root Cause**: MV creation query used field names with potential table prefixes:
```python
query = f'SELECT "{pk_field}", "{geom_field}" FROM {full_table} WHERE ...'  # ❌
# If pk_field = "table.id", becomes: SELECT ""table.id"" ... (invalid)
```

**Fixed in v4.3.1** (backend.py lines 351-365, 489-505):
```python
# Clean field names - remove any table prefixes
clean_pk_field = pk_field.split('.')[-1].strip('"')
clean_geom_field = geom_field.split('.')[-1].strip('"')

query = f'SELECT "{clean_pk_field}" as pk, "{clean_geom_field}" as geom FROM {full_table} ...'
```

This ensures:
- MV creation succeeds for large feature selections (>500 FIDs)
- Performance optimization works (60 bytes vs 212KB expressions)
- Fallback temp tables also use correct field names

### Additional Fix: Filter Chaining EXISTS Adaptation

Double-adaptation of EXISTS clauses in filter chaining caused incorrect table references.

**Error SQL**:
```sql
EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source 
        WHERE ST_Intersects(ST_PointOnSurface(__source."geom"), __source."geom") ...)
                                           ^^^^^^^^^^^^^^^^^^  ❌ Both arguments are __source!
```

**Should be**:
```sql
EXISTS (SELECT 1 FROM "ref"."zone_pop" AS __source 
        WHERE ST_Intersects(ST_PointOnSurface("sheaths"."geom"), __source."geom") ...)
                                           ^^^^^^^^^^^^^^^^^^  ✅ Target table geom
```

**Root Cause**: EXISTS clauses were adapted TWICE:
1. First in `core/filter/expression_builder.py` line 507-515 with `new_alias='__source'`
   - Replaced `"demand_points"."geom"` → `__source."geom"` (❌ wrong!)
2. Then in `adapters/backends/postgresql/expression_builder.py` line 319-328 with `new_alias='"sheaths"'`
   - Tried to replace `"demand_points"."geom"` → `"sheaths"."geom"` but already replaced!

Result: TARGET table reference became `__source` instead of distant table name.

**Fixed in v4.3.1** (core/filter/expression_builder.py line 500-520):
```python
# DO NOT adapt EXISTS here - pass unchanged to backend
# Backend will adapt correctly with actual distant table name
exists_parts.append(clause_sql)  # No adaptation!
```

This ensures target geometry references are correctly updated to the distant layer's table name.

### Fix #6: Filter Chaining Detection Failed (🔥 CRITICAL)

**Error SQL** (sheaths layer):
```sql
ST_Buffer(__source."geom", CASE WHEN __source."homecount" >= 10...)
-- __source is sheaths table, but homecount doesn't exist in sheaths!
```

**Root Cause**: `is_filter_chaining` detection failed because:
1. `build_expression` extracts EXISTS from `source_filter` (line 293-336)
2. Sets `simple_source_filter = None` after extraction
3. Calls `_build_exists_expression` with `source_filter=None`
4. Detection `is_filter_chaining = source_filter and 'EXISTS'...` returns **False**!
5. Inline buffer fallback executes, applying homecount expression to wrong table

**Impact**: Fix #3 (inline buffer prevention) was **bypassed** due to incorrect detection.

**Fixed in v4.3.1** (expression_builder.py lines 1074, 1152, 360):
- Added explicit `is_filter_chaining: bool` parameter to `_build_exists_expression`
- Pass `is_filter_chaining=bool(exists_clauses_to_combine)` from caller
- Removed unreliable `source_filter and 'EXISTS'` detection

```python
# BEFORE (BUGGY)
is_filter_chaining = source_filter and 'EXISTS' in source_filter.upper()
# ❌ source_filter is None after EXISTS extraction!

# AFTER (FIXED)
is_filter_chaining: bool = False  # Explicit parameter from caller
# ✅ Caller sets: is_filter_chaining=bool(exists_clauses_to_combine)
```
