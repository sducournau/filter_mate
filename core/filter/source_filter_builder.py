"""
Source Filter Builder Module

EPIC-1 Phase E5: Extracted from modules/tasks/filter_task.py

This module provides functions for building source filters for backend expressions:
- Pattern detection for skippable subsets
- Feature ID extraction and filter generation
- Source filter generation from visible features
- WKT and SRID extraction for PostgreSQL simple mode

These functions are used by FilterEngineTask._build_backend_expression()
to construct source filters for PostgreSQL EXISTS subqueries.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E5)
"""

import re
import logging
from typing import List, Optional, Tuple, Any

logger = logging.getLogger("FilterMate")


def should_skip_source_subset(source_subset: Optional[str]) -> bool:
    """
    Check if source_subset contains patterns that should be skipped.

    These patterns indicate the subset was created by a previous FilterMate
    operation and would cause issues if reused directly in EXISTS subqueries.

    Patterns that get skipped:
    - EXISTS( or EXISTS ( - geometric filter from previous FilterMate operation
    - __source - already adapted filter
    - "filter_mate_temp"."mv_" - materialized view reference (except mv_src_sel_)

    Args:
        source_subset: The source layer's subsetString

    Returns:
        bool: True if subset should be skipped, False otherwise
    """
    if not source_subset:
        return False

    source_subset_upper = source_subset.upper()

    # Check for simple skip patterns
    if any(pattern in source_subset_upper for pattern in [
        '__SOURCE',
        'EXISTS(',
        'EXISTS ('
    ]):
        return True

    # Check for MV references (except source selection MVs which are allowed)
    # Use negative lookahead to exclude mv_src_sel_ (source selection MVs)
    if re.search(
        r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?.*mv_(?!.*src_sel_)',
        source_subset,
        re.IGNORECASE | re.DOTALL
    ):
        return True

    return False


def get_primary_key_field(layer) -> Optional[str]:
    """
    Get the primary key field name from a layer.

    Tries multiple methods to determine the PK:
    1. Layer's primaryKeyAttributes()
    2. Common PK names: fid, id, gid, ogc_fid

    Args:
        layer: QgsVectorLayer instance

    Returns:
        str: Primary key field name, or None if not found
    """
    if not layer:
        return None

    # Try to get primary key from provider
    try:
        pk_attrs = layer.primaryKeyAttributes()
        if pk_attrs:
            fields = layer.fields()
            return fields[pk_attrs[0]].name()
    except Exception as e:
        logger.debug(f"Ignored in primary key detection from provider: {e}")

    # Fallback: try common PK names
    for common_pk in ['fid', 'id', 'gid', 'ogc_fid']:
        if layer.fields().indexOf(common_pk) >= 0:
            return common_pk

    return None


def get_source_table_name(layer, param_source_table: Optional[str] = None) -> Optional[str]:
    """
    Get the actual database table name for a layer.

    Uses param_source_table if available, otherwise extracts from layer URI.

    Args:
        layer: QgsVectorLayer instance
        param_source_table: Pre-computed source table name (optional)

    Returns:
        str: Database table name, or None if not found
    """
    if param_source_table:
        return param_source_table

    if not layer:
        return None

    try:
        from qgis.core import QgsDataSourceUri
        uri = QgsDataSourceUri(layer.source())
        return uri.table()
    except Exception as e:
        logger.debug(f"Ignored in source table name extraction from URI: {e}")
        return layer.name() if hasattr(layer, 'name') else None


def extract_feature_ids(
    features: List[Any],
    pk_field: str,
    layer=None
) -> List[Any]:
    """
    Extract primary key values from a list of features.

    Handles both QgsFeature objects and dict-like structures.
    Uses attribute(pk_field) instead of id() to get the actual DB primary key.

    Args:
        features: List of QgsFeature objects or dicts
        pk_field: Name of the primary key field
        layer: Optional layer for fallback (not used currently)

    Returns:
        List of primary key values
    """
    fids = []

    for f in features:
        try:
            # task_features are QgsFeature objects
            # CRITICAL: Use attribute(pk_field) NOT id()!
            # f.id() returns QGIS internal FID which may differ from DB primary key
            if hasattr(f, 'attribute'):
                fid_val = f.attribute(pk_field)
                if fid_val is not None:
                    fids.append(fid_val)
                else:
                    # Fallback to QGIS FID if attribute is null
                    if hasattr(f, 'id'):
                        fids.append(f.id())
            elif hasattr(f, 'id'):
                # Legacy fallback for non-QgsFeature objects
                fids.append(f.id())
            elif isinstance(f, dict) and pk_field in f:
                fids.append(f[pk_field])
        except Exception as e:
            logger.debug(f"Could not extract ID from feature: {e}")

    return fids


def build_source_filter_inline(
    fids: List[Any],
    pk_field: str,
    source_table_name: Optional[str],
    format_pk_values_func
) -> str:
    """
    Build an inline IN clause source filter.

    Args:
        fids: List of feature IDs
        pk_field: Primary key field name
        source_table_name: Table name for qualification
        format_pk_values_func: Function to format PK values for SQL

    Returns:
        str: SQL filter expression like '"table"."pk" IN (1,2,3)'
    """
    fids_str = format_pk_values_func(fids)

    if source_table_name:
        # Use qualified column name: "table"."column"
        return f'"{source_table_name}"."{pk_field}" IN ({fids_str})'
    else:
        # Fallback: unqualified (may still be ambiguous)
        return f'"{pk_field}" IN ({fids_str})'


def build_source_filter_with_mv(
    fids: List[Any],
    pk_field: str,
    source_table_name: str,
    mv_ref: str
) -> str:
    """
    Build a source filter using a materialized view reference.

    Args:
        fids: List of feature IDs (for documentation only)
        pk_field: Primary key field name
        source_table_name: Table name for qualification
        mv_ref: Materialized view reference (e.g., 'filter_mate_temp.mv_src_sel_xxx')

    Returns:
        str: SQL filter expression using MV reference
    """
    return f'"{source_table_name}"."{pk_field}" IN (SELECT pk FROM {mv_ref})'  # nosec B608 - source_table_name/pk_field from QGIS layer metadata, mv_ref from internal MV manager


def get_visible_feature_ids(layer, pk_field: str) -> List[Any]:
    """
    Get primary key values for all visible features in a layer.

    "Visible" means respecting the current subsetString filter.

    Args:
        layer: QgsVectorLayer instance
        pk_field: Primary key field name

    Returns:
        List of primary key values for visible features
    """
    visible_fids = []

    try:
        for feature in layer.getFeatures():
            try:
                fid_val = feature.attribute(pk_field)
                if fid_val is not None:
                    visible_fids.append(fid_val)
            except Exception as e:
                logger.debug(f"Ignored in visible feature ID extraction: {e}")
    except Exception as e:
        logger.error(f"Failed to get visible features: {e}")

    return visible_fids


def get_source_wkt_and_srid(
    source_layer,
    spatialite_source_geom: Optional[str],
    source_layer_crs_authid: Optional[str]
) -> Tuple[Optional[str], Optional[int]]:
    """
    Extract WKT geometry and SRID for PostgreSQL simple mode.

    PostgreSQL can use WKT instead of EXISTS for small datasets,
    which produces simpler expressions.

    Args:
        source_layer: Source layer (for fallback CRS)
        spatialite_source_geom: Pre-computed WKT string
        source_layer_crs_authid: CRS authority ID (e.g., 'EPSG:4326')

    Returns:
        Tuple of (wkt_string, srid_int) or (None, None) if not available
    """
    if not spatialite_source_geom:
        return None, None

    source_wkt = spatialite_source_geom
    source_srid = 4326  # Default to WGS84

    if source_layer_crs_authid:
        try:
            source_srid = int(source_layer_crs_authid.split(':')[1])
        except (ValueError, IndexError):
            pass

    return source_wkt, source_srid


def get_source_feature_count(
    task_features: List[Any],
    ogr_source_geom,
    source_layer
) -> Optional[int]:
    """
    Get the source feature count for PostgreSQL optimization.

    Priority order:
    1. task_features (selected features from main thread)
    2. ogr_source_geom feature count (if available)
    3. source_layer.featureCount() (fallback)

    Args:
        task_features: Features selected by user
        ogr_source_geom: OGR source geometry layer (if available)
        source_layer: Source layer for fallback

    Returns:
        int: Feature count, or None if not determinable
    """
    from qgis.core import QgsVectorLayer

    if task_features and len(task_features) > 0:
        logger.debug(f"Using task_features count: {len(task_features)} selected features")
        return len(task_features)

    if ogr_source_geom:
        if isinstance(ogr_source_geom, QgsVectorLayer):
            count = ogr_source_geom.featureCount()
            logger.debug(f"Using ogr_source_geom feature count: {count}")
            return count
        else:
            # ogr_source_geom exists but is not a layer (might be a geometry)
            logger.debug(f"ogr_source_geom is {type(ogr_source_geom).__name__}, assuming 1 feature")
            return 1

    if source_layer and hasattr(source_layer, 'featureCount'):
        count = source_layer.featureCount()
        logger.debug(f"Using source_layer feature count (fallback): {count}")
        return count

    return None
