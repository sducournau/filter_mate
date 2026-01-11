"""
FilterMate OGR Backend Package.

OGR provider implementations for file-based formats.
Universal fallback for unsupported providers.

Part of Phase 4 Backend Refactoring (ARCH-044).
"""
from .backend import OGRBackend, create_ogr_backend
from .filter_executor import (
    build_ogr_filter_from_selection,
    format_ogr_pk_values,
    normalize_column_names_for_ogr,
    build_ogr_simple_filter,
    apply_ogr_subset,
    combine_ogr_filters,
    # EPIC-1 Phase E4-S7: OGR Source Geometry Preparation
    OGRSourceContext,
    validate_task_features,
    recover_features_from_fids,
    determine_source_mode,
    validate_ogr_result_layer,
    prepare_ogr_source_geom,
)

__all__ = [
    'OGRBackend',
    'create_ogr_backend',
    # Filter executor functions
    'build_ogr_filter_from_selection',
    'format_ogr_pk_values',
    'normalize_column_names_for_ogr',
    'build_ogr_simple_filter',
    'apply_ogr_subset',
    'combine_ogr_filters',
    # EPIC-1 Phase E4-S7
    'OGRSourceContext',
    'validate_task_features',
    'recover_features_from_fids',
    'determine_source_mode',
    'validate_ogr_result_layer',
    'prepare_ogr_source_geom',
]
