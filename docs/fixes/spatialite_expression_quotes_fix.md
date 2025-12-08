# Fix: Spatialite Expression Quotes Bug

## Date
2025-12-08

## Severity
**CRITICAL** - Filters completely broken for Spatialite layers with case-sensitive field names

## Problem Description

### User Report
User reported: `"HOMECOUNT" > 100` becomes `HOMECOUNT > 100` and the layer is not filtered correctly.

### Technical Analysis

The bug was in the `qgis_expression_to_spatialite()` function in `modules/appTasks.py` (lines ~1270-1290).

**Problematic Code:**
```python
# WRONG - This removed the closing quote from field names!
expression = expression.replace('" >', ' ').replace('">', ' ')
expression = expression.replace('" <', ' ').replace('"<', ' ')
expression = expression.replace('" +', ' ').replace('"+', ' ')
expression = expression.replace('" -', ' ').replace('"-', ' ')
```

### Why This Was Wrong

1. **Spatialite requires quotes for case-sensitive field names**, just like PostgreSQL
2. The code was trying to handle numeric comparisons by removing quotes
3. This caused expressions like `"HOMECOUNT" > 100` to become `HOMECOUNT > 100`
4. Without quotes, Spatialite treats field names as case-insensitive or may fail entirely
5. For a field actually named `HOMECOUNT` (uppercase), this breaks the filter

### Comparison with PostgreSQL

The PostgreSQL version (`qgis_expression_to_postgis()`) does it correctly:

```python
# CORRECT - Keeps quotes and adds type casting
expression = expression.replace('" >', '"::numeric >').replace('">', '"::numeric >')
expression = expression.replace('" <', '"::numeric <').replace('"<', '"::numeric <')
```

## Solution

### Fixed Code

Removed all quote-stripping code and added clear documentation:

```python
# CRITICAL FIX: Do NOT remove quotes from field names!
# Spatialite needs quotes for case-sensitive field names, just like PostgreSQL.
# Unlike the PostgreSQL version that adds ::numeric for type casting,
# Spatialite will do implicit type conversion when needed.
# The quotes MUST be preserved for field names like "HOMECOUNT".
#
# Note: The old code had these lines which REMOVED quotes:
#   expression = expression.replace('" >', ' ').replace('">', ' ')
# This was WRONG and caused "HOMECOUNT" > 100 to become HOMECOUNT > 100

# Spatial functions compatibility (most are identical, but document them)
# ST_Buffer, ST_Intersects, ST_Contains, ST_Distance, ST_Union, ST_Transform
# all work the same in Spatialite as in PostGIS

return expression
```

### Why This Works

1. **Spatialite supports implicit type conversion**: If a field is numeric, `"FIELD" > 100` works without explicit casting
2. **Quotes are preserved**: Case-sensitive field names remain functional
3. **Simpler code**: No need for complex CAST() injection
4. **Compatible with existing patterns**: LIKE, CASE, and other SQL constructs still work

## Testing

Created comprehensive test suite: `tests/test_spatialite_expression_quotes.py`

### Test Results

```
Test 1: Expression simple avec guillemets (le bug rapporté)
  Input:  "HOMECOUNT" > 100
  Output: "HOMECOUNT" > 100
  ✓ OK - Les guillemets sont préservés!

Test 2: Expression avec espace avant l'opérateur
  Input:  ' "HOMECOUNT" > 100'
  Output: ' "HOMECOUNT" > 100'
  ✓ OK

Test 3: Expression avec égalité
  Input:  "POPULATION" = 5000
  Output: "POPULATION" = 5000
  ✓ OK

Test 4: Expression avec opérateur <=
  Input:  "AREA" <= 100.5
  Output: "AREA" <= 100.5
  ✓ OK

Test 5: Expression complexe avec AND
  Input:  "HOMECOUNT" > 100 AND "POPULATION" < 50000
  Output: "HOMECOUNT" > 100 AND "POPULATION" < 50000
  ✓ OK

Test 6: Expression avec nom de table qualifié
  Input:  "table"."HOMECOUNT" > 100
  Output: "table"."HOMECOUNT" > 100
  ✓ OK - Les guillemets sont préservés

Test 8: Expression avec CAST explicite
  Input:  "FIELD"::numeric > 100
  Output: CAST("FIELD" AS REAL) > 100
  ✓ OK
```

## Impact Assessment

### Affected Users
- **All Spatialite users** with case-sensitive field names
- **Common scenario**: GeoPackage layers with uppercase field names (e.g., from exports)
- **Frequency**: HIGH - Many GIS datasets use uppercase field naming conventions

### Severity Justification
- **CRITICAL** because filtering is a core function
- **Complete failure** for affected field names
- **No workaround** available to users
- **Silent failure** - users may not realize filters aren't working

## Side Effects & Risks

### Minimal Risk
1. **Spatialite implicit casting**: Spatialite is very good at implicit type conversion
2. **Existing :: casts preserved**: Expressions with `::numeric` still get converted to `CAST()`
3. **No impact on PostgreSQL**: Different code path
4. **No impact on OGR**: Different code path (keeps QGIS expressions as-is)

### Potential Issues (Low Risk)
1. **Edge case**: Very strict Spatialite configurations that require explicit casting
   - **Mitigation**: Users can use explicit `CAST()` in expressions if needed
2. **Performance**: Implicit casting might be slightly slower than explicit
   - **Mitigation**: Negligible for typical dataset sizes (<100k features)

## Related Code

### Files Modified
- `modules/appTasks.py` - Fixed `qgis_expression_to_spatialite()` function
- `CHANGELOG.md` - Documented the fix
- `tests/test_spatialite_expression_quotes.py` - New test file

### Related Functions
- `qgis_expression_to_postgis()` - Correctly preserves quotes with `::numeric`
- `_process_qgis_expression()` - Calls the conversion functions
- `safe_set_subset_string()` in `modules/appUtils.py` - Applies the final expression

## Prevention

### Code Review Guidelines
1. **Always preserve SQL identifier quotes** unless explicitly removing for a reason
2. **Test with case-sensitive field names** (uppercase/mixed case)
3. **Compare behavior across backends** (PostgreSQL, Spatialite, OGR)
4. **Document quote handling** in expression conversion functions

### Testing Checklist
- [ ] Test with uppercase field names
- [ ] Test with mixed-case field names
- [ ] Test with qualified names (`"table"."field"`)
- [ ] Test with complex expressions (AND/OR)
- [ ] Test with spatial functions
- [ ] Test with CAST expressions

## References

### Spatialite Documentation
- [Spatialite SQL](https://www.gaia-gis.it/gaia-sins/spatialite-sql-latest.html)
- [SQL Identifier Quoting](https://www.sqlite.org/lang_keywords.html)

### Related Issues
- User report: December 8, 2025
- No GitHub issue (direct user feedback)

### Related Code Patterns
- PostgreSQL backend: Uses `::numeric` for explicit casting
- OGR backend: Keeps QGIS expressions unmodified
- Spatialite backend: Now relies on implicit conversion

## Commit Message

```
fix: preserve field name quotes in Spatialite expressions

CRITICAL: Fixed bug where double quotes around field names were 
incorrectly removed during Spatialite expression conversion.

Before: "HOMECOUNT" > 100 → HOMECOUNT > 100 (WRONG)
After:  "HOMECOUNT" > 100 → "HOMECOUNT" > 100 (CORRECT)

Impact:
- All Spatialite/GeoPackage layers with case-sensitive field names
- Filtering completely broken for affected fields
- Common scenario: uppercase field names from exports

Solution:
- Removed quote-stripping code in qgis_expression_to_spatialite()
- Spatialite handles implicit type conversion correctly
- Quotes preserved for case-sensitive field name matching
- Added comprehensive test suite

Files:
- modules/appTasks.py: Fixed qgis_expression_to_spatialite()
- tests/test_spatialite_expression_quotes.py: New test suite
- CHANGELOG.md: Documented fix

Closes: User report 2025-12-08
```
