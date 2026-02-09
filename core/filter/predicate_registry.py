# -*- coding: utf-8 -*-
"""
FilterMate - Unified Spatial Predicate Registry

Consolidates spatial predicate mappings from PostgreSQL, Spatialite, and OGR
expression builders into a single source of truth.

v6.0 Phase 2.1: Extract common logic from 3 separate predicate dictionaries.
"""

from typing import Dict, Optional, Union


# Unified predicate registry: maps predicate name to dialect-specific representation
PREDICATES: Dict[str, Dict[str, Union[str, int]]] = {
    'intersects': {
        'postgresql': 'ST_Intersects',
        'spatialite': 'Intersects',
        'ogr': 0,
    },
    'contains': {
        'postgresql': 'ST_Contains',
        'spatialite': 'Contains',
        'ogr': 1,
    },
    'within': {
        'postgresql': 'ST_Within',
        'spatialite': 'Within',
        'ogr': 6,
    },
    'touches': {
        'postgresql': 'ST_Touches',
        'spatialite': 'Touches',
        'ogr': 4,
    },
    'overlaps': {
        'postgresql': 'ST_Overlaps',
        'spatialite': 'Overlaps',
        'ogr': 5,
    },
    'crosses': {
        'postgresql': 'ST_Crosses',
        'spatialite': 'Crosses',
        'ogr': 7,
    },
    'disjoint': {
        'postgresql': 'ST_Disjoint',
        'spatialite': 'Disjoint',
        'ogr': 2,
    },
    'equals': {
        'postgresql': 'ST_Equals',
        'spatialite': 'Equals',
        'ogr': 3,
    },
    'covers': {
        'postgresql': 'ST_Covers',
        'spatialite': 'Covers',
        'ogr': None,  # Not supported in QGIS selectbylocation
    },
    'coveredby': {
        'postgresql': 'ST_CoveredBy',
        'spatialite': 'CoveredBy',
        'ogr': None,  # Not supported in QGIS selectbylocation
    },
}

# Selectivity order (most selective first) for query optimization
SELECTIVITY_ORDER: Dict[str, int] = {
    'within': 1,
    'contains': 2,
    'disjoint': 3,
    'equals': 4,
    'touches': 5,
    'crosses': 6,
    'overlaps': 7,
    'intersects': 8,
    'covers': 9,
    'coveredby': 10,
}


def get_predicate_function(predicate_name: str, dialect: str) -> Optional[Union[str, int]]:
    """
    Get the dialect-specific function/code for a spatial predicate.

    Args:
        predicate_name: Predicate name (e.g., 'intersects', 'within')
        dialect: Backend dialect ('postgresql', 'spatialite', 'ogr')

    Returns:
        Dialect-specific representation:
        - PostgreSQL: ST_* function name (str)
        - Spatialite: function name (str)
        - OGR: QGIS processing predicate code (int)
        - None if predicate not supported for dialect
    """
    predicate = PREDICATES.get(predicate_name.lower())
    if predicate is None:
        return None
    return predicate.get(dialect)


def get_predicate_functions(dialect: str) -> Dict[str, Union[str, int]]:
    """
    Get all predicate mappings for a specific dialect.

    Args:
        dialect: Backend dialect ('postgresql', 'spatialite', 'ogr')

    Returns:
        Dictionary mapping predicate names to dialect-specific values.
        Excludes predicates not supported by the dialect.
    """
    result = {}
    for name, mappings in PREDICATES.items():
        value = mappings.get(dialect)
        if value is not None:
            result[name] = value
    return result


def get_selectivity_order(predicate_name: str) -> int:
    """
    Get the selectivity order for query optimization.

    Lower values = more selective = should be evaluated first.

    Args:
        predicate_name: Predicate name

    Returns:
        Selectivity order (1-10), defaults to 99 for unknown predicates
    """
    return SELECTIVITY_ORDER.get(predicate_name.lower(), 99)


def sort_predicates_by_selectivity(predicate_names: list) -> list:
    """
    Sort predicate names by selectivity (most selective first).

    Args:
        predicate_names: List of predicate names to sort

    Returns:
        Sorted list of predicate names
    """
    return sorted(predicate_names, key=lambda p: get_selectivity_order(p))
