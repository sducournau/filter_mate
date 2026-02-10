# -*- coding: utf-8 -*-
"""
PostgreSQL Field Type Detector.

Detects field types from PostgreSQL layers to prevent type mismatch errors.

FIX v4.8.2 (2026-01-25): Created to prevent "operator does not exist: character varying < integer"

Author: FilterMate Team (Bmad Master)
Date: 2026-01-25
"""
import logging
from typing import Optional, Dict

logger = logging.getLogger('FilterMate.FieldTypeDetector')

try:
    from qgis.core import QgsVectorLayer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = object


def get_field_types_from_layer(layer: 'QgsVectorLayer') -> Dict[str, str]:
    """
    Extract field types from a QGIS layer.

    Returns a dict mapping lowercase field names to their PostgreSQL types.

    Args:
        layer: QGIS vector layer

    Returns:
        Dict mapping field names (lowercase) to type names (lowercase)
        e.g., {'importance': 'varchar', 'fid': 'integer'}

    Example:
        >>> field_types = get_field_types_from_layer(roads_layer)
        >>> print(field_types)
        {'fid': 'integer', 'importance': 'varchar', 'nature': 'varchar'}
    """
    if not QGIS_AVAILABLE or not layer:
        return {}

    field_types = {}

    try:
        for field in layer.fields():
            field_name = field.name().lower()
            type_name = field.typeName().lower()
            field_types[field_name] = type_name

        logger.debug(f"Extracted {len(field_types)} field types from layer '{layer.name()}'")

    except (RuntimeError, AttributeError) as e:
        logger.warning(f"Could not extract field types from layer: {e}")

    return field_types


def get_postgresql_field_types(layer: 'QgsVectorLayer', connection=None) -> Dict[str, str]:
    """
    Get field types directly from PostgreSQL schema (more accurate).

    This queries information_schema.columns to get the exact PostgreSQL types,
    which is more reliable than QGIS field.typeName() that may be normalized.

    Args:
        layer: PostgreSQL layer
        connection: Optional psycopg2 connection (if None, attempts to create one)

    Returns:
        Dict mapping field names (lowercase) to PostgreSQL types (lowercase)
        Empty dict if not PostgreSQL or query fails

    Example:
        >>> types = get_postgresql_field_types(pg_layer)
        >>> print(types['importance'])
        'character varying'  # Full PostgreSQL type name
    """
    if not QGIS_AVAILABLE or not layer:
        return {}

    # Check if PostgreSQL layer
    if layer.providerType() != 'postgres':
        logger.debug("Layer is not PostgreSQL, using QGIS field types")
        return get_field_types_from_layer(layer)

    # Try to get connection
    conn = connection
    close_conn = False

    if conn is None:
        try:
            from ..utils.layer_utils import get_datasource_connexion_from_layer
            conn, _ = get_datasource_connexion_from_layer(layer)
            close_conn = True
        except ImportError:
            logger.debug("Could not import connection utils, falling back to QGIS types")
            return get_field_types_from_layer(layer)

    if conn is None:
        logger.debug("No PostgreSQL connection available, using QGIS field types")
        return get_field_types_from_layer(layer)

    # Extract schema and table name
    try:
        from qgis.core import QgsDataSourceUri
        uri = QgsDataSourceUri(layer.source())
        schema = uri.schema() or 'public'
        table = uri.table()

        if not table:
            logger.warning("Could not extract table name from layer source")
            return get_field_types_from_layer(layer)

        # Query PostgreSQL information_schema
        query = """
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position;
        """

        cursor = conn.cursor()
        cursor.execute(query, (schema, table))
        rows = cursor.fetchall()

        field_types = {}
        for row in rows:
            column_name = row[0].lower()
            data_type = row[1].lower()

            # Handle specific types
            if data_type == 'character varying':
                max_length = row[2]
                if max_length:
                    data_type = f'varchar({max_length})'
                else:
                    data_type = 'varchar'
            elif data_type in ('numeric', 'decimal'):
                precision = row[3]
                scale = row[4]
                if precision and scale:
                    data_type = f'numeric({precision},{scale})'

            field_types[column_name] = data_type

        cursor.close()

        logger.info(
            f"Retrieved {len(field_types)} field types from PostgreSQL "
            f"schema '{schema}'.'{table}'"
        )

        return field_types

    except Exception as e:
        logger.warning(f"Failed to query PostgreSQL schema: {e}")
        logger.debug("Falling back to QGIS field types")
        return get_field_types_from_layer(layer)

    finally:
        if close_conn and conn:
            try:
                conn.close()
            except Exception:
                pass


def suggest_type_cast(field_name: str, field_type: str, comparison_type: str) -> Optional[str]:
    """
    Suggest appropriate type cast for a field comparison.

    Args:
        field_name: Field name (e.g., "importance")
        field_type: PostgreSQL type (e.g., "varchar", "integer")
        comparison_type: 'numeric' or 'string'

    Returns:
        Suggested cast syntax, or None if no cast needed

    Example:
        >>> suggest_type_cast('importance', 'varchar', 'numeric')
        '"importance"::integer'

        >>> suggest_type_cast('name', 'integer', 'string')
        '"name"::text'
    """
    field_type_lower = field_type.lower()

    if comparison_type == 'numeric':
        # Suggest cast for string types used in numeric comparisons
        if field_type_lower in ('varchar', 'character varying', 'text', 'char', 'character'):
            return f'"{field_name}"::integer'

    elif comparison_type == 'string':
        # Suggest cast for numeric types used in string comparisons (LIKE/ILIKE)
        if field_type_lower in (
            'integer', 'smallint', 'bigint',
            'numeric', 'decimal', 'real', 'double precision',
            'int', 'int2', 'int4', 'int8'
        ):
            return f'"{field_name}"::text'

    return None
