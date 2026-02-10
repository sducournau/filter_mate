# -*- coding: utf-8 -*-
"""
Style Filter Fixer for PostgreSQL Type Mismatches.

Scans and fixes layer style/renderer filter expressions that have type mismatches
between VARCHAR fields and numeric comparisons.

This fixes the error:
    ERROR: operator does not exist: character varying < integer

The issue happens when a layer has a rule-based renderer with filters like
"importance" < 4, but the PostgreSQL column 'importance' is VARCHAR not INTEGER.

FIX v4.8.3 (2026-01-26): Created to fix style filter type mismatches.

Author: FilterMate Team
"""
import re
import logging
from typing import List, Tuple, Dict

logger = logging.getLogger('FilterMate.StyleFilterFixer')

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsRuleBasedRenderer,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


def apply_type_casting_to_expression(expression: str, varchar_fields: List[str] = None) -> str:
    """
    Apply PostgreSQL type casting to numeric comparisons in an expression.

    Converts expressions like:
        "importance" < 4  →  "importance"::integer < 4
        "level" >= 2      →  "level"::integer >= 2

    Args:
        expression: SQL/QGIS filter expression
        varchar_fields: Optional list of known VARCHAR field names (lowercase)
                        If provided, only these fields get ::integer cast.
                        If None, all fields in numeric comparisons get cast.

    Returns:
        Expression with type casting applied

    Example:
        >>> apply_type_casting_to_expression('"importance" < 4')
        '"importance"::integer < 4'
    """
    if not expression:
        return expression

    # Pattern: "field"<op><number> where field is NOT already casted
    # Captures: field name, whitespace, operator, whitespace, number
    pattern = r'"([^"]+)"(?!::)(\s*)(<|>|<=|>=|=)(\s*)(\d+(?:\.\d+)?)'

    def add_cast(match):
        field = match.group(1)
        space1 = match.group(2)
        operator = match.group(3)
        space2 = match.group(4)
        number = match.group(5)

        # If varchar_fields specified, only cast those fields
        if varchar_fields is not None:
            if field.lower() not in varchar_fields:
                # Not a varchar field, leave unchanged
                return match.group(0)

        # Determine cast type based on number format
        if '.' in number:
            cast_type = '::numeric'
        else:
            cast_type = '::integer'

        return f'"{field}"{cast_type}{space1}{operator}{space2}{number}'

    return re.sub(pattern, add_cast, expression)


def fix_rule_based_renderer_filters(
    layer: 'QgsVectorLayer',
    varchar_fields: List[str] = None,
    dry_run: bool = False
) -> Tuple[bool, List[str]]:
    """
    Fix type mismatch issues in rule-based renderer filters.

    Scans all rules in a QgsRuleBasedRenderer and applies ::integer
    cast to VARCHAR fields used in numeric comparisons.

    Args:
        layer: QGIS vector layer with rule-based renderer
        varchar_fields: List of VARCHAR field names (lowercase) to fix.
                        If None, detects from layer automatically.
        dry_run: If True, only report changes without applying them

    Returns:
        Tuple of (success, list of changed rules/filters)

    Example:
        >>> success, changes = fix_rule_based_renderer_filters(layer)
        >>> print(changes)
        ['Rule "Roads": "importance" < 4 → "importance"::integer < 4']
    """
    if not QGIS_AVAILABLE or not layer:
        return False, []

    renderer = layer.renderer()
    if not renderer or not isinstance(renderer, QgsRuleBasedRenderer):
        logger.debug(f"Layer '{layer.name()}' does not use rule-based renderer")
        return False, []

    # Get VARCHAR fields if not provided
    if varchar_fields is None:
        try:
            from .field_type_detector import get_field_types_from_layer, get_postgresql_field_types

            # Prefer PostgreSQL types if available
            if layer.providerType() == 'postgres':
                field_types = get_postgresql_field_types(layer)
            else:
                field_types = get_field_types_from_layer(layer)

            # Filter to VARCHAR/TEXT types
            varchar_fields = [
                name for name, ftype in field_types.items()
                if ftype.lower() in ('varchar', 'character varying', 'text', 'char', 'character')
                or ftype.lower().startswith('varchar(')
            ]

            logger.debug(f"Detected VARCHAR fields: {varchar_fields}")

        except Exception as e:
            logger.warning(f"Could not detect field types: {e}")
            varchar_fields = []  # Apply to all fields

    changes = []
    root_rule = renderer.rootRule()

    def process_rule(rule, path=""):
        """Recursively process rules and their children."""
        rule_label = rule.label() or "(unnamed)"
        full_path = f"{path}/{rule_label}" if path else rule_label

        filter_expr = rule.filterExpression()
        if filter_expr and filter_expr.strip():
            # Apply type casting
            fixed_expr = apply_type_casting_to_expression(filter_expr, varchar_fields)

            if fixed_expr != filter_expr:
                change_desc = f'Rule "{full_path}": {filter_expr} → {fixed_expr}'
                changes.append(change_desc)
                logger.info(f"🔧 {change_desc}")

                if not dry_run:
                    rule.setFilterExpression(fixed_expr)

        # Process child rules
        for child in rule.children():
            process_rule(child, full_path)

    # Process all rules starting from root
    for child in root_rule.children():
        process_rule(child)

    # Refresh renderer if changes were made
    if changes and not dry_run:
        layer.triggerRepaint()
        logger.info(f"✅ Fixed {len(changes)} rule filters in layer '{layer.name()}'")

    return True, changes


def fix_layer_style_filters(
    layer: 'QgsVectorLayer',
    dry_run: bool = False
) -> Tuple[bool, List[str]]:
    """
    Fix type mismatch issues in ANY layer style/renderer filters.

    Handles multiple renderer types:
    - Rule-based renderer
    - Categorized renderer (if has filter)
    - Graduated renderer (if has filter)

    Args:
        layer: QGIS vector layer
        dry_run: If True, only report changes without applying them

    Returns:
        Tuple of (success, list of changes)
    """
    if not QGIS_AVAILABLE or not layer:
        return False, []

    renderer = layer.renderer()
    if not renderer:
        return False, []

    # Get VARCHAR fields
    try:
        from .field_type_detector import get_postgresql_field_types, get_field_types_from_layer

        if layer.providerType() == 'postgres':
            field_types = get_postgresql_field_types(layer)
        else:
            field_types = get_field_types_from_layer(layer)

        varchar_fields = [
            name for name, ftype in field_types.items()
            if ftype.lower() in ('varchar', 'character varying', 'text', 'char', 'character')
            or ftype.lower().startswith('varchar(')
        ]
    except Exception as e:
        logger.debug(f"Ignored in fix_layer_style_filters field type detection: {e}")
        varchar_fields = None  # Apply to all fields

    if isinstance(renderer, QgsRuleBasedRenderer):
        return fix_rule_based_renderer_filters(layer, varchar_fields, dry_run)

    # For other renderers, check if they have filter expressions
    # (Categorized/Graduated don't typically have WHERE filters but may have expressions)

    return False, []


def scan_layers_for_type_mismatches(
    layers: List['QgsVectorLayer'] = None,
    fix: bool = False
) -> Dict[str, List[str]]:
    """
    Scan multiple layers for type mismatch issues in style filters.

    Args:
        layers: List of layers to scan (if None, scans all project layers)
        fix: If True, also fix the issues found

    Returns:
        Dict mapping layer names to lists of issues found

    Example:
        >>> issues = scan_layers_for_type_mismatches()
        >>> print(issues)
        {'troncon_de_route': ['Rule "Roads": "importance" < 4']}
    """
    if not QGIS_AVAILABLE:
        return {}

    try:
        from qgis.core import QgsProject

        if layers is None:
            layers = [
                layer for layer in QgsProject.instance().mapLayers().values()
                if isinstance(layer, QgsVectorLayer) and layer.providerType() == 'postgres'
            ]
    except ImportError:
        return {}

    results = {}

    for layer in layers:
        try:
            success, changes = fix_layer_style_filters(layer, dry_run=not fix)
            if changes:
                results[layer.name()] = changes
        except Exception as e:
            logger.warning(f"Error scanning layer '{layer.name()}': {e}")

    if results:
        total_issues = sum(len(v) for v in results.values())
        if fix:
            logger.info(f"✅ Fixed {total_issues} type mismatch issues in {len(results)} layers")
        else:
            logger.warning(f"⚠️ Found {total_issues} type mismatch issues in {len(results)} layers")

    return results


def fix_expression_for_postgresql(
    expression: str,
    layer: 'QgsVectorLayer' = None
) -> str:
    """
    Fix a single expression for PostgreSQL type compatibility.

    This is a convenience function to fix any expression, useful for:
    - Subset strings
    - Filter expressions
    - Style rules

    Args:
        expression: Expression to fix
        layer: Optional layer to detect VARCHAR fields from

    Returns:
        Fixed expression with type casts applied
    """
    if not expression:
        return expression

    varchar_fields = None

    if layer and QGIS_AVAILABLE:
        try:
            from .field_type_detector import get_postgresql_field_types, get_field_types_from_layer

            if layer.providerType() == 'postgres':
                field_types = get_postgresql_field_types(layer)
            else:
                field_types = get_field_types_from_layer(layer)

            varchar_fields = [
                name for name, ftype in field_types.items()
                if ftype.lower() in ('varchar', 'character varying', 'text', 'char', 'character')
                or ftype.lower().startswith('varchar(')
            ]
        except Exception as e:
            logger.debug(f"Ignored in fix_expression_for_postgresql field detection: {e}")

    return apply_type_casting_to_expression(expression, varchar_fields)
