"""
Config Provider Module

EPIC-1 Phase E7.5: Extracted from modules/tasks/filter_task.py

Provides configuration extraction utilities for:
- Optimization thresholds
- Geometry simplification settings
- Other runtime configuration

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E7.5)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('FilterMate.Core.Optimization.ConfigProvider')


# Default optimization thresholds
DEFAULT_OPTIMIZATION_THRESHOLDS = {
    'large_dataset_warning': 50000,
    'async_expression_threshold': 10000,
    'update_extents_threshold': 50000,
    'centroid_optimization_threshold': 5000,
    'exists_subquery_threshold': 100000,
    'parallel_processing_threshold': 100000,
    'progress_update_batch_size': 100,
    'source_mv_fid_threshold': 500
}

# Default simplification configuration
DEFAULT_SIMPLIFICATION_CONFIG = {
    'enabled': True,
    'max_wkt_length': 100000,
    'preserve_topology': True,
    'min_tolerance_meters': 1.0,
    'max_tolerance_meters': 100.0,
    'show_warnings': True
}


def get_optimization_thresholds(task_parameters: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """
    Get optimization thresholds configuration from task parameters or defaults.
    
    Thresholds control:
    - large_dataset_warning: Feature count for performance warnings
    - async_expression_threshold: Feature count for async expressions
    - update_extents_threshold: Feature count for auto extent update
    - centroid_optimization_threshold: Feature count for centroid optimization
    - exists_subquery_threshold: WKT length for EXISTS mode
    - parallel_processing_threshold: Feature count for parallel processing
    - progress_update_batch_size: Features per progress update
    - source_mv_fid_threshold: Max FIDs for inline IN clause (above creates MV)
    
    Args:
        task_parameters: Task parameters dict containing config section
        
    Returns:
        dict: Optimization thresholds
    """
    if not task_parameters:
        return DEFAULT_OPTIMIZATION_THRESHOLDS.copy()
    
    config = task_parameters.get('config', {})
    app_config = config.get('APP', {})
    settings = app_config.get('SETTINGS', {})
    opt_config = settings.get('OPTIMIZATION_THRESHOLDS', {})
    
    if not opt_config:
        return DEFAULT_OPTIMIZATION_THRESHOLDS.copy()
    
    return {
        'large_dataset_warning': opt_config.get('large_dataset_warning', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['large_dataset_warning']),
        'async_expression_threshold': opt_config.get('async_expression_threshold', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['async_expression_threshold']),
        'update_extents_threshold': opt_config.get('update_extents_threshold', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['update_extents_threshold']),
        'centroid_optimization_threshold': opt_config.get('centroid_optimization_threshold', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['centroid_optimization_threshold']),
        'exists_subquery_threshold': opt_config.get('exists_subquery_threshold', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['exists_subquery_threshold']),
        'parallel_processing_threshold': opt_config.get('parallel_processing_threshold', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['parallel_processing_threshold']),
        'progress_update_batch_size': opt_config.get('progress_update_batch_size', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['progress_update_batch_size']),
        'source_mv_fid_threshold': opt_config.get('source_mv_fid_threshold', {}).get('value', DEFAULT_OPTIMIZATION_THRESHOLDS['source_mv_fid_threshold'])
    }


def get_simplification_config(task_parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get geometry simplification configuration from task parameters or defaults.
    
    Configuration controls:
    - enabled: Whether simplification is enabled
    - max_wkt_length: Maximum WKT string length
    - preserve_topology: Whether to preserve topology during simplification
    - min_tolerance_meters: Minimum tolerance in meters
    - max_tolerance_meters: Maximum tolerance in meters
    - show_warnings: Whether to show simplification warnings
    
    Args:
        task_parameters: Task parameters dict containing config section
        
    Returns:
        dict: Simplification configuration
    """
    if not task_parameters:
        return DEFAULT_SIMPLIFICATION_CONFIG.copy()
    
    config = task_parameters.get('config', {})
    app_config = config.get('APP', {})
    settings = app_config.get('SETTINGS', {})
    simp_config = settings.get('GEOMETRY_SIMPLIFICATION', {})
    
    if not simp_config:
        return DEFAULT_SIMPLIFICATION_CONFIG.copy()
    
    return {
        'enabled': simp_config.get('enabled', {}).get('value', DEFAULT_SIMPLIFICATION_CONFIG['enabled']),
        'max_wkt_length': simp_config.get('max_wkt_length', {}).get('value', DEFAULT_SIMPLIFICATION_CONFIG['max_wkt_length']),
        'preserve_topology': simp_config.get('preserve_topology', {}).get('value', DEFAULT_SIMPLIFICATION_CONFIG['preserve_topology']),
        'min_tolerance_meters': simp_config.get('min_tolerance_meters', {}).get('value', DEFAULT_SIMPLIFICATION_CONFIG['min_tolerance_meters']),
        'max_tolerance_meters': simp_config.get('max_tolerance_meters', {}).get('value', DEFAULT_SIMPLIFICATION_CONFIG['max_tolerance_meters']),
        'show_warnings': simp_config.get('show_simplification_warnings', {}).get('value', DEFAULT_SIMPLIFICATION_CONFIG['show_warnings'])
    }
