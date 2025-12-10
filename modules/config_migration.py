"""
Configuration Migration Helper

This module provides helper functions for managing configuration file migration
from the plugin directory to the APP_SQLITE_PATH directory.
"""

import os
from qgis.core import QgsMessageLog, Qgis
from ..config.config import get_config_path, ENV_VARS


def get_config_location_info():
    """
    Get information about config.json location.
    
    Returns:
        dict: Dictionary with config location information:
            - config_path: Full path to config.json
            - sqlite_path: APP_SQLITE_PATH directory
            - plugin_dir: Plugin installation directory
            - is_migrated: Whether config is in SQLite directory
    """
    config_path = get_config_path()
    sqlite_path = ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "")
    plugin_dir = ENV_VARS.get("DIR_CONFIG", "")
    
    # Check if config is in SQLite directory
    is_migrated = False
    if sqlite_path and config_path:
        is_migrated = os.path.dirname(config_path) == sqlite_path
    
    return {
        "config_path": config_path,
        "sqlite_path": sqlite_path,
        "plugin_dir": plugin_dir,
        "is_migrated": is_migrated
    }


def log_config_location():
    """
    Log the current configuration location for debugging.
    """
    info = get_config_location_info()
    
    QgsMessageLog.logMessage(
        f"Config location info:\n"
        f"  Config path: {info['config_path']}\n"
        f"  SQLite directory: {info['sqlite_path']}\n"
        f"  Plugin directory: {info['plugin_dir']}\n"
        f"  Is migrated: {info['is_migrated']}",
        "FilterMate",
        Qgis.Info
    )
    
    return info


def verify_config_accessible():
    """
    Verify that config.json is accessible.
    
    Returns:
        bool: True if config is accessible, False otherwise
    """
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        QgsMessageLog.logMessage(
            f"Config file does not exist: {config_path}",
            "FilterMate",
            Qgis.Warning
        )
        return False
    
    if not os.access(config_path, os.R_OK):
        QgsMessageLog.logMessage(
            f"Config file is not readable: {config_path}",
            "FilterMate",
            Qgis.Warning
        )
        return False
    
    if not os.access(config_path, os.W_OK):
        QgsMessageLog.logMessage(
            f"Config file is not writable: {config_path}",
            "FilterMate",
            Qgis.Warning
        )
        return False
    
    return True
