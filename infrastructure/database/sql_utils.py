# -*- coding: utf-8 -*-
"""
SQL Utilities for FilterMate

Provides SQL sanitization and safety functions.

Migrated from modules/appUtils.py to infrastructure/database/sql_utils.py
"""

import re
import logging

logger = logging.getLogger('FilterMate.Infrastructure.Database.SQLUtils')


def sanitize_sql_identifier(identifier: str) -> str:
    """
    Sanitize SQL identifier (table name, column name, schema name).

    Removes or replaces dangerous characters that could lead to SQL injection
    or syntax errors.

    Args:
        identifier: Raw SQL identifier (table, column, schema name)

    Returns:
        str: Sanitized identifier safe for SQL queries

    Examples:
        >>> sanitize_sql_identifier("my_table")
        'my_table'
        >>> sanitize_sql_identifier("table; DROP TABLE users;")
        'table_DROP_TABLE_users'
        >>> sanitize_sql_identifier("schema.table")
        'schema.table'
    """
    if not identifier:
        return ""

    # Remove dangerous characters, keep only alphanumeric, underscore, dot, quotes
    # Allow dots for schema.table notation
    # Allow double quotes for PostgreSQL quoted identifiers
    sanitized = re.sub(r'[^\w\.\"]', '_', str(identifier))

    # Remove leading/trailing underscores added by sanitization
    sanitized = sanitized.strip('_')

    return sanitized


def safe_set_subset_string(layer, subset_expression: str) -> bool:
    """
    Safely set subset string (filter) on a QGIS layer.

    Handles edge cases:
    - Layer is None or invalid
    - setSubsetString method not available (rare)
    - Exception during filter application

    FIX v4.8.1 (2026-01-25): Automatically apply PostgreSQL type casting
    for PostgreSQL layers to prevent "operator does not exist" errors
    when comparing varchar fields to numeric literals.

    Args:
        layer: QgsVectorLayer to filter
        subset_expression: SQL WHERE clause (without WHERE keyword)

    Returns:
        bool: True if filter applied successfully, False otherwise

    Examples:
        >>> safe_set_subset_string(layer, "population > 10000")
        True
        >>> safe_set_subset_string(None, "any expression")
        False
    """
    if not layer:
        logger.warning("safe_set_subset_string: layer is None")
        return False

    try:
        if hasattr(layer, 'setSubsetString'):
            # FIX v4.2.13: Enhanced diagnostics for setSubsetString failures
            logger.debug(f"[SQL] Applying subset to layer '{layer.name()}':")
            logger.debug(f"[SQL]   Provider: {layer.providerType()}")
            logger.debug(f"[SQL]   Expression length: {len(subset_expression) if subset_expression else 0} chars")

            # FIX v4.8.2: Detect type mismatches BEFORE applying to PostgreSQL
            # Prevents "operator does not exist: character varying < integer" errors
            if subset_expression and layer.providerType() == 'postgres':
                try:
                    from ..database.field_type_detector import get_field_types_from_layer
                    from ...core.services.expression_service import ExpressionService

                    field_types = get_field_types_from_layer(layer)
                    service = ExpressionService()
                    warnings = service.detect_type_mismatches(subset_expression, field_types)

                    if warnings:
                        logger.warning("⚠️ Type mismatch detected in PostgreSQL expression:")
                        for warning in warnings:
                            logger.warning(f"  - {warning}")

                        # Show warning to user via QGIS message bar
                        try:
                            from qgis.utils import iface
                            if iface:
                                message = f"Type mismatch in filter: {warnings[0][:100]}..."
                                iface.messageBar().pushWarning(
                                    "FilterMate - PostgreSQL Type Warning",
                                    message
                                )
                        except (ImportError, AttributeError):
                            pass  # No UI available (testing environment)

                        logger.info("💡 FilterMate will auto-apply type casting to fix this.")
                except Exception as type_check_err:
                    logger.debug(f"Type mismatch detection failed (non-critical): {type_check_err}")

            # FIX v4.8.1: Apply PostgreSQL type casting for PostgreSQL layers
            # This ensures numeric comparisons have ::numeric casting
            if subset_expression and layer.providerType() == 'postgres':
                try:
                    # Import from adapters (infrastructure/database -> adapters/backends)
                    from filter_mate.adapters.backends.postgresql.filter_executor import apply_postgresql_type_casting
                    subset_expression = apply_postgresql_type_casting(subset_expression, layer)
                    logger.debug("[SQL]   PostgreSQL type casting applied")
                except ImportError:
                    # Fallback: inline type casting if import fails
                    import re
                    pattern = r'"([^"]+)"(?!::)(\s*)(<|>|<=|>=|=)(\s*)(\d+(?:\.\d+)?)'

                    def add_cast(m):
                        return f'"{m.group(1)}"::numeric{m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}'
                    subset_expression = re.sub(pattern, add_cast, subset_expression)
                    logger.debug("[SQL]   PostgreSQL type casting applied (fallback)")

            if subset_expression:
                # Log first 500 chars of expression for debugging
                preview = subset_expression[:500]
                if len(subset_expression) > 500:
                    preview += f"... ({len(subset_expression) - 500} more chars)"
                logger.debug(f"[SQL]   Expression: {preview}")

            result = layer.setSubsetString(subset_expression)

            if not result:
                logger.warning(f"setSubsetString returned False for layer {layer.name()}")
                # Additional diagnostics for failure
                logger.warning("[SQL] ❌ FAILED - Diagnostics:")
                logger.warning(f"[SQL]   Layer source: {layer.source()[:200]}...")
                logger.warning(f"[SQL]   Feature count before: {layer.featureCount()}")
                logger.warning(f"[SQL]   Current subset: {layer.subsetString()[:200] if layer.subsetString() else 'None'}...")

                # Try to get provider error
                try:
                    provider = layer.dataProvider()
                    if provider and hasattr(provider, 'error') and provider.error():
                        logger.warning(f"[SQL]   Provider error: {provider.error().message()}")
                except Exception as diag_e:
                    logger.debug(f"[SQL]   Could not get provider error: {diag_e}")

                # Log the full expression to a separate line for easy copy/paste
                logger.warning(f"[SQL] Full expression that FAILED:\n{subset_expression}")
            else:
                logger.debug(f"[SQL] ✓ Success - {layer.featureCount()} features after filter")

            return result
        else:
            logger.error(f"Layer {layer.name()} does not have setSubsetString method")
            return False
    except Exception as e:
        logger.error(f"Error setting subset string on layer {layer.name()}: {e}")
        logger.error(f"[SQL] Exception details - Expression:\n{subset_expression}")
        return False


def create_temp_spatialite_table(
    db_path: str,
    table_name: str,
    sql_query: str,
    geom_field: str = 'geometry',
    srid: int = 4326
) -> bool:
    """
    Create temporary table in Spatialite database.

    Alternative to PostgreSQL materialized views for Spatialite backend.
    Creates a temp table populated from a SELECT query with spatial index.

    Args:
        db_path: Path to Spatialite database file
        table_name: Name for temporary table
        sql_query: SELECT query to populate table
        geom_field: Name of geometry column (default: 'geometry')
        srid: SRID for geometry column (default: 4326)

    Returns:
        bool: True if table created successfully

    Example:
        >>> create_temp_spatialite_table(
        ...     "/path/to/db.sqlite",
        ...     "temp_filtered",
        ...     "SELECT * FROM cities WHERE population > 100000",
        ...     "geom",
        ...     3857
        ... )
        True
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)

        # Load Spatialite extension
        try:
            conn.load_extension('mod_spatialite')
        except sqlite3.OperationalError:
            try:
                conn.load_extension('mod_spatialite.dll')  # Windows fallback
            except Exception as e:
                logger.error(f"Failed to load Spatialite extension: {e}")
                conn.close()
                return False

        cursor = conn.cursor()

        # Drop existing table if exists
        cursor.execute(f"DROP TABLE IF EXISTS {sanitize_sql_identifier(table_name)}")  # nosec B608

        # Create table from query
        create_sql = f"CREATE TABLE {sanitize_sql_identifier(table_name)} AS {sql_query}"  # nosec B608
        cursor.execute(create_sql)

        # Create spatial index
        try:
            # Register geometry column
            cursor.execute(f"""
                SELECT RecoverGeometryColumn(
                    '{sanitize_sql_identifier(table_name)}',
                    '{sanitize_sql_identifier(geom_field)}',
                    {srid},
                    'GEOMETRY',
                    'XY'
                )
            """)

            # Create R-tree spatial index
            cursor.execute(f"""
                SELECT CreateSpatialIndex(
                    '{sanitize_sql_identifier(table_name)}',
                    '{sanitize_sql_identifier(geom_field)}'
                )
            """)
        except Exception as e:
            logger.warning(f"Could not create spatial index: {e}")
            # Continue anyway - table is still usable without index

        conn.commit()
        conn.close()

        logger.info(f"Created temporary Spatialite table: {table_name}")
        return True

    except Exception as e:
        logger.error(f"Error creating Spatialite temp table {table_name}: {e}")
        return False


def format_pk_values_for_sql(
    values: list,
    pk_field: str = None,
    layer=None,
    is_numeric: bool = None
) -> str:
    """
    Format primary key values for SQL IN clause.

    CENTRALIZED v4.3.8: Single implementation for all backends.

    Handles different data types:
    - UUID: Quoted strings with ::uuid cast ('uuid-value'::uuid)
    - Text: Quoted strings ('text-value')
    - Numeric: Unquoted (123, 456)

    Detection priority:
    1. Explicit is_numeric parameter
    2. Value-based detection (most reliable for OGR layers)
    3. Field schema detection from layer
    4. Fallback based on common PK names

    Args:
        values: List of feature ID values
        pk_field: Primary key field name (optional)
        layer: QgsVectorLayer for schema inspection (optional)
        is_numeric: Force numeric detection (optional)

    Returns:
        str: Comma-separated formatted values for SQL IN clause

    Examples:
        >>> format_pk_values_for_sql([1, 2, 3], 'id')
        '1, 2, 3'
        >>> format_pk_values_for_sql(['a', 'b'], 'code')
        "'a', 'b'"
        >>> format_pk_values_for_sql(['550e8400-e29b-41d4-a716-446655440000'], 'uuid_pk')
        "'550e8400-e29b-41d4-a716-446655440000'::uuid"
    """
    if not values:
        return ""

    pk_is_uuid = False
    pk_is_text = False
    pk_is_numeric = is_numeric

    # Strategy 1: Check if ALL values are Python numeric types
    if pk_is_numeric is None:
        try:
            all_numeric_values = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in values[:10]  # Check first 10 values
            )
            if all_numeric_values:
                pk_is_numeric = True
                logger.debug(f"PK '{pk_field}' detected as numeric from VALUES (all int/float)")
        except Exception as e:
            logger.debug(f"Ignored in PK numeric detection (strategy 1): {e}")

    # Strategy 2: Check if string values look like integers
    if pk_is_numeric is None:
        try:
            all_look_numeric = all(
                isinstance(v, (int, float)) or
                (isinstance(v, str) and v.lstrip('-').isdigit())
                for v in values[:10]
            )
            if all_look_numeric:
                pk_is_numeric = True
                logger.debug(f"PK '{pk_field}' detected as numeric from string VALUES")
        except Exception as e:
            logger.debug(f"Ignored in PK numeric detection (strategy 2): {e}")

    # Strategy 3: Check field schema (may be unreliable for OGR)
    if pk_is_numeric is None and layer and pk_field:
        try:
            pk_idx = layer.fields().indexOf(pk_field)
            if pk_idx >= 0:
                field = layer.fields()[pk_idx]
                field_type = field.typeName().lower()
                pk_is_uuid = 'uuid' in field_type
                pk_is_text = 'char' in field_type or 'text' in field_type or 'string' in field_type
                pk_is_numeric = field.isNumeric()
                logger.debug(f"PK '{pk_field}' from schema: uuid={pk_is_uuid}, text={pk_is_text}, numeric={pk_is_numeric}")
        except Exception as e:
            logger.debug(f"Could not get field schema: {e}")

    # Strategy 4: Fallback based on common PK names
    if pk_is_numeric is None and pk_field:
        pk_lower = pk_field.lower()
        common_numeric_names = ('id', 'fid', 'gid', 'pk', 'ogc_fid', 'objectid', 'oid', 'rowid')
        pk_is_numeric = pk_lower in common_numeric_names
        logger.debug(f"PK '{pk_field}' fallback based on name: numeric={pk_is_numeric}")

    # Default to non-numeric if still undetermined
    if pk_is_numeric is None:
        pk_is_numeric = False

    # Format values based on type
    if pk_is_uuid:
        # UUID - cast to uuid type (PostgreSQL specific)
        formatted = ["'" + str(fid).replace("'", "''") + "'::uuid" for fid in values]
    elif pk_is_text or not pk_is_numeric:
        # Text/UUID/other non-numeric - quote strings and escape quotes
        formatted = ["'" + str(fid).replace("'", "''") + "'" for fid in values]
    else:
        # Numeric - no quotes
        formatted = [str(fid) for fid in values]

    return ", ".join(formatted)


__all__ = [
    'sanitize_sql_identifier',
    'safe_set_subset_string',
    'create_temp_spatialite_table',
    'format_pk_values_for_sql',
]
