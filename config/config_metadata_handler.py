# -*- coding: utf-8 -*-
"""
Configuration Metadata Handler for FilterMate

This module provides utilities for integrating ConfigMetadata with 
qt_json_view and other UI components. It wraps JSON models with metadata
awareness for tooltips and widget type hints.

Migrated from: before_migration/modules/config_metadata_handler.py (313 lines)
Location: config/config_metadata_handler.py

Usage:
    from config.config_metadata_handler import (
        ConfigMetadataHandler,
        MetadataAwareConfigModel,
        enhance_config_editor_with_metadata
    )
    
    # Enhance existing model with metadata
    enhanced_model = MetadataAwareConfigModel(json_model, metadata)

Author: FilterMate Team
Date: December 2025 (migrated January 2026)
"""

from typing import Any, Dict, List, Optional


class ConfigMetadataHandler:
    """
    Handles metadata integration for configuration editors.
    
    This class provides static methods to extract metadata information
    and format it for UI components.
    """
    
    @staticmethod
    def get_tooltip_for_path(metadata, config_path: str) -> str:
        """
        Generate a rich tooltip for a configuration parameter.
        
        Args:
            metadata: ConfigMetadata instance
            config_path: Dot-separated path to config parameter
            
        Returns:
            Formatted tooltip string with description, type, and default value
        """
        meta = metadata.get_metadata(config_path)
        if not meta:
            return config_path
            
        tooltip_parts = []
        
        # Description
        if 'description' in meta:
            tooltip_parts.append(meta['description'])
            
        # Data type
        if 'data_type' in meta:
            tooltip_parts.append(f"\nType: {meta['data_type']}")
            
        # Default value
        if 'default' in meta:
            default = meta['default']
            if isinstance(default, str):
                tooltip_parts.append(f"Default: \"{default}\"")
            else:
                tooltip_parts.append(f"Default: {default}")
                
        # Allowed values
        if 'validation' in meta and 'allowed_values' in meta['validation']:
            values = ', '.join(str(v) for v in meta['validation']['allowed_values'])
            tooltip_parts.append(f"Allowed: {values}")
            
        # Range for numbers
        if 'validation' in meta:
            val = meta['validation']
            if 'min' in val or 'max' in val:
                range_str = f"Range: {val.get('min', '?')} to {val.get('max', '?')}"
                tooltip_parts.append(range_str)
                
        return '\n'.join(tooltip_parts)
    
    @staticmethod
    def get_widget_type_for_path(metadata, config_path: str) -> str:
        """
        Get the recommended widget type for a configuration parameter.
        
        Args:
            metadata: ConfigMetadata instance
            config_path: Dot-separated path to config parameter
            
        Returns:
            Widget type string: 'checkbox', 'combobox', 'textbox', 'spinbox', 'colorpicker'
        """
        return metadata.get_widget_type(config_path)
    
    @staticmethod
    def get_combobox_items(metadata, config_path: str) -> List[str]:
        """
        Get items for a combobox widget.
        
        Args:
            metadata: ConfigMetadata instance
            config_path: Dot-separated path to config parameter
            
        Returns:
            List of allowed values for combobox, or empty list
        """
        allowed = metadata.get_allowed_values(config_path)
        if allowed:
            return [str(v) for v in allowed]
        return []
    
    @staticmethod
    def format_label(config_path: str) -> str:
        """
        Format a configuration path into a user-friendly label.
        
        Args:
            config_path: Dot-separated path like 'app.ui.profile'
            
        Returns:
            Formatted label like 'Profile'
        """
        # Take last part of path
        name = config_path.split('.')[-1]
        # Replace underscores with spaces and capitalize
        return name.replace('_', ' ').title()
    
    @staticmethod
    def get_section_title(config_path: str) -> str:
        """
        Get section title from configuration path.
        
        Args:
            config_path: Dot-separated path like 'app.ui.profile'
            
        Returns:
            Section title like 'UI' (second level of path)
        """
        parts = config_path.split('.')
        if len(parts) >= 2:
            return parts[1].replace('_', ' ').title()
        return 'General'


class MetadataAwareConfigModel:
    """
    Wrapper for JSON models that adds metadata awareness.
    
    This class wraps a base JSON model and enhances it with
    metadata-driven tooltips, widget types, and validation.
    
    Used with qt_json_view or similar JSON editing components.
    """
    
    def __init__(self, base_model: Any, metadata: Any):
        """
        Initialize the metadata-aware wrapper.
        
        Args:
            base_model: The underlying JSON model to wrap
            metadata: ConfigMetadata instance for metadata lookup
        """
        self._base_model = base_model
        self._metadata = metadata
        self._path_cache: Dict[str, str] = {}
        
    @property
    def base_model(self) -> Any:
        """Get the underlying base model."""
        return self._base_model
        
    @property
    def metadata(self) -> Any:
        """Get the metadata instance."""
        return self._metadata
        
    def get_tooltip(self, index) -> str:
        """
        Get tooltip for a model index.
        
        Args:
            index: Model index (Qt model index or similar)
            
        Returns:
            Tooltip string from metadata
        """
        config_path = self._get_path_for_index(index)
        if config_path:
            return ConfigMetadataHandler.get_tooltip_for_path(
                self._metadata, config_path
            )
        return ""
        
    def get_widget_type(self, index) -> str:
        """
        Get recommended widget type for a model index.
        
        Args:
            index: Model index
            
        Returns:
            Widget type string
        """
        config_path = self._get_path_for_index(index)
        if config_path:
            return ConfigMetadataHandler.get_widget_type_for_path(
                self._metadata, config_path
            )
        return "textbox"
        
    def _get_path_for_index(self, index) -> Optional[str]:
        """
        Convert a model index to a config path string.
        
        Args:
            index: Model index
            
        Returns:
            Dot-separated configuration path, or None
        """
        # This method should be overridden based on the actual model structure
        # Default implementation tries to use index.data() or path attribute
        
        if hasattr(index, 'data') and callable(index.data):
            try:
                return index.data()  # Simplified - real implementation may differ
            except Exception:
                pass
                
        if hasattr(index, 'path'):
            return index.path
            
        return None
        
    def validate_at_index(self, index, value: Any) -> tuple:
        """
        Validate a value at a specific model index.
        
        Args:
            index: Model index
            value: Value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        config_path = self._get_path_for_index(index)
        if config_path and self._metadata:
            return self._metadata.validate_value(config_path, value)
        return True, ""


def enhance_config_editor_with_metadata(editor_widget, metadata) -> None:
    """
    Enhance a config editor widget with metadata-driven features.
    
    This function adds tooltips, descriptions, and validation to
    an existing configuration editor widget.
    
    Args:
        editor_widget: The editor widget to enhance (ConfigEditorWidget or similar)
        metadata: ConfigMetadata instance
        
    Usage:
        from config.config_metadata import get_config_metadata
        from config.config_metadata_handler import enhance_config_editor_with_metadata
        
        metadata = get_config_metadata()
        editor = ConfigEditorWidget(config_data)
        enhance_config_editor_with_metadata(editor, metadata)
    """
    if not editor_widget or not metadata:
        return
        
    # Check if editor has methods we can enhance
    if hasattr(editor_widget, 'set_metadata'):
        editor_widget.set_metadata(metadata)
        return
        
    # Alternative: iterate through editor's widgets and add tooltips
    if hasattr(editor_widget, 'config_widgets'):
        for config_path, widget in editor_widget.config_widgets.items():
            tooltip = ConfigMetadataHandler.get_tooltip_for_path(metadata, config_path)
            if hasattr(widget, 'setToolTip'):
                widget.setToolTip(tooltip)


def create_grouped_config_data(metadata, config_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Organize flat configuration data into groups based on metadata.
    
    Args:
        metadata: ConfigMetadata instance
        config_data: Flat dictionary of config path -> value
        
    Returns:
        Nested dictionary organized by groups
        
    Example:
        >>> grouped = create_grouped_config_data(metadata, {'app.ui.profile': 'auto'})
        >>> print(grouped)
        {'UI': {'profile': 'auto'}}
    """
    groups = metadata.get_config_groups()
    result = {}
    
    for group_name, paths in groups.items():
        group_data = {}
        for path in paths:
            if path in config_data:
                # Use last part of path as key within group
                key = path.split('.')[-1]
                group_data[key] = config_data[path]
        if group_data:
            result[group_name] = group_data
            
    return result
