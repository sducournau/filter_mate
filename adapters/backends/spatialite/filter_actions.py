#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spatialite Backend - Filter Actions (Reset/Unfilter/Cleanup)
=============================================================

This module provides action implementations for Spatialite backend,
mirroring the functionality available in PostgreSQL and OGR backends.

Actions:
- execute_reset_action_spatialite(): Clear all filters from layer
- execute_unfilter_action_spatialite(): Restore previous filter state
- cleanup_spatialite_session_tables(): Clean up temporary session tables

Created: 2026-01-17 (Phase 1 - Critical Regression Fixes)
"""

from typing import Optional, Tuple
import logging
from qgis.core import QgsVectorLayer

from .database_manager import cleanup_session_temp_tables

logger = logging.getLogger(__name__)


def execute_reset_action_spatialite(
    layer: QgsVectorLayer,
    name: str,
    layer_props: dict,
    datasource_info: dict
) -> Tuple[bool, str]:
    """
    Execute RESET action for Spatialite layer.
    
    Clears the layer's subset string (filter) and cleans up any
    temporary tables created during the session.
    
    Args:
        layer: The QgsVectorLayer to reset
        name: Action name ('reset')
        layer_props: Layer properties dictionary
        datasource_info: Datasource connection info
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    logger.info(f"Spatialite: Executing RESET action for layer '{layer.name()}'")
    
    try:
        # Clear subset string
        layer.setSubsetString("")
        logger.info(f"   ✅ Subset string cleared")
        
        # Trigger layer refresh
        layer.triggerRepaint()
        layer.reload()
        logger.info(f"   ✅ Layer refreshed")
        
        # Cleanup temporary session tables
        db_path = datasource_info.get('dbname')
        if db_path:
            cleaned_count = cleanup_session_temp_tables(db_path)
            logger.info(f"   ✅ Cleaned {cleaned_count} temporary tables")
        
        message = f"Filter reset successfully for layer '{layer.name()}'"
        return True, message
        
    except Exception as e:
        error_msg = f"Failed to reset Spatialite layer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def execute_unfilter_action_spatialite(
    layer: QgsVectorLayer,
    name: str,
    layer_props: dict,
    datasource_info: dict,
    previous_subset: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Execute UNFILTER action for Spatialite layer.
    
    Restores the previous filter state (subset string) if provided,
    otherwise clears the filter completely.
    
    Args:
        layer: The QgsVectorLayer to unfilter
        name: Action name ('unfilter')
        layer_props: Layer properties dictionary
        datasource_info: Datasource connection info
        previous_subset: Previous subset string to restore (optional)
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    logger.info(f"Spatialite: Executing UNFILTER action for layer '{layer.name()}'")
    logger.info(f"   Previous subset: '{previous_subset}'" if previous_subset else "   No previous subset")
    
    try:
        if previous_subset:
            # Restore previous subset
            layer.setSubsetString(previous_subset)
            logger.info(f"   ✅ Restored previous subset ({len(previous_subset)} chars)")
        else:
            # No previous state - clear filter
            layer.setSubsetString("")
            logger.info(f"   ✅ No previous subset - cleared filter")
        
        # Trigger layer refresh
        layer.triggerRepaint()
        layer.reload()
        logger.info(f"   ✅ Layer refreshed")
        
        message = f"Filter restored for layer '{layer.name()}'"
        return True, message
        
    except Exception as e:
        error_msg = f"Failed to unfilter Spatialite layer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def cleanup_spatialite_session_tables(db_path: str) -> int:
    """
    Clean up temporary session tables in Spatialite database.
    
    This is a convenience wrapper around cleanup_session_temp_tables()
    from database_manager module.
    
    Args:
        db_path: Path to Spatialite database file
    
    Returns:
        int: Number of tables cleaned up
    """
    logger.info(f"Spatialite: Cleaning up session tables in: {db_path}")
    
    try:
        cleaned_count = cleanup_session_temp_tables(db_path)
        logger.info(f"   ✅ Cleaned {cleaned_count} temporary tables")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"   ❌ Failed to cleanup tables: {str(e)}", exc_info=True)
        return 0


# Export all actions
__all__ = [
    'execute_reset_action_spatialite',
    'execute_unfilter_action_spatialite',
    'cleanup_spatialite_session_tables'
]
