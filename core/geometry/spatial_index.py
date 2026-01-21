# -*- coding: utf-8 -*-
"""
FilterMate Spatial Index Utilities

Provides spatial index verification and creation for vector layers.
Extracted from filter_task.py as part of Phase E7.5.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional

from qgis.core import QgsFeatureSource

logger = logging.getLogger('FilterMate.Core.Geometry.SpatialIndex')


def verify_and_create_spatial_index(layer, layer_name: Optional[str] = None) -> bool:
    """
    Verify that spatial index exists on layer, create if missing.
    
    This method checks if a layer has a spatial index and creates one automatically
    if it's missing. Spatial indexes dramatically improve performance of spatial
    operations (intersect, contains, etc.).
    
    Args:
        layer: QgsVectorLayer to check
        layer_name: Optional display name for user messages
        
    Returns:
        bool: True if index exists or was created successfully, False otherwise
    """
    if not layer or not layer.isValid():
        logger.warning("Cannot verify spatial index: invalid layer")
        return False
    
    display_name = layer_name or layer.name()
    
    # Check if layer already has spatial index
    # NOTE: hasSpatialIndex() returns an enum QgsFeatureSource.SpatialIndexPresence:
    #   0 = SpatialIndexUnknown
    #   1 = SpatialIndexNotPresent
    #   2 = SpatialIndexPresent
    if layer.hasSpatialIndex() == QgsFeatureSource.SpatialIndexPresent:
        logger.debug(f"Spatial index already exists for layer: {display_name}")
        return True
    
    # No spatial index - create one
    logger.info(f"Creating spatial index for layer: {display_name}")
    
    # NOTE: Cannot display message bar from worker thread - would cause crash
    # Message bar operations MUST run in main thread
    # Spatial index creation is logged instead
    
    # Create spatial index
    try:
        import processing
        processing.run('qgis:createspatialindex', {
            'INPUT': layer
        })
        logger.info(f"Successfully created spatial index for: {display_name}")
        return True
        
    except Exception as e:
        logger.warning(f"Could not create spatial index for {display_name}: {e}")
        logger.info(f"Proceeding without spatial index - performance may be reduced")
        return False


def has_spatial_index(layer) -> bool:
    """
    Check if a layer has a spatial index.
    
    Note: hasSpatialIndex() returns an enum QgsFeatureSource.SpatialIndexPresence:
        - 0 = SpatialIndexUnknown
        - 1 = SpatialIndexNotPresent  
        - 2 = SpatialIndexPresent
    
    Args:
        layer: QgsVectorLayer to check
        
    Returns:
        bool: True if index is confirmed present, False otherwise
    """
    if not layer or not layer.isValid():
        return False
    
    try:
        return layer.hasSpatialIndex() == QgsFeatureSource.SpatialIndexPresent
    except Exception:
        return False
