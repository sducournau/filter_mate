# -*- coding: utf-8 -*-
"""
Configuration Metadata Module for FilterMate

This module provides utilities to work with configuration metadata,
including widget type detection, validation, and user-friendly descriptions.

The metadata is stored in config_schema.json and provides:
- User-friendly descriptions for each configuration parameter
- Widget type recommendations (checkbox, combobox, textbox, spinbox, colorpicker)
- Data types (boolean, string, integer)
- Validation rules (required, allowed_values, min/max, patterns)
- Default values

Migrated from: before_migration/modules/config_metadata.py (375 lines)
Location: config/config_metadata.py

Usage:
    from ..config.config_metadata import get_config_metadata, ConfigMetadata    
    metadata = get_config_metadata()
    widget_type = metadata.get_widget_type('app.ui.profile')
    description = metadata.get_description('app.ui.profile')

Author: FilterMate Team
Date: December 2025 (migrated January 2026)
"""

import json
import os
import re
from typing import Dict, Any, Optional, List, Tuple


class ConfigMetadata:
    """
    Manages configuration metadata and provides utilities for UI generation.
    """

    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize ConfigMetadata with schema file.

        Args:
            schema_path: Path to config_schema.json. If None, uses default location.
        """
        if schema_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(current_dir, "config_schema.json")

        self.schema_path = os.path.abspath(schema_path)
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        """
        Load configuration schema from JSON file.

        Returns:
            Dictionary containing the configuration schema
        """
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    def get_metadata(self, config_path: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific configuration parameter.

        Args:
            config_path: Dot-separated path to config parameter (e.g., 'app.ui.profile')

        Returns:
            Dictionary containing metadata, or None if not found

        Example:
            >>> metadata = ConfigMetadata()
            >>> info = metadata.get_metadata('app.ui.profile')
            >>> print(info['description'])
            'UI layout profile - auto detects screen size...'
        """
        keys = config_path.split('.')
        current = self.schema

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        # Only return if this is a leaf node with metadata
        if isinstance(current, dict) and 'widget_type' in current:
            return current

        return None

    def get_widget_type(self, config_path: str) -> str:
        """
        Get recommended widget type for a configuration parameter.

        Args:
            config_path: Dot-separated path to config parameter

        Returns:
            Widget type string: 'checkbox', 'combobox', 'textbox', 'spinbox', 'colorpicker'
            Returns 'textbox' as default fallback

        Example:
            >>> metadata = ConfigMetadata()
            >>> widget = metadata.get_widget_type('app.auto_activate')
            >>> print(widget)
            'checkbox'
        """
        meta = self.get_metadata(config_path)
        if meta:
            return meta.get('widget_type', 'textbox')
        return 'textbox'

    def get_description(self, config_path: str) -> str:
        """
        Get user-friendly description for a configuration parameter.

        Args:
            config_path: Dot-separated path to config parameter

        Returns:
            Description string, or empty string if not found
        """
        meta = self.get_metadata(config_path)
        if meta:
            return meta.get('description', '')
        return ''

    def get_user_friendly_label(self, config_path: str) -> str:
        """
        Get user-friendly label for UI display.

        Args:
            config_path: Dot-separated path to config parameter

        Returns:
            User-friendly label, or the last part of the path as fallback
        """
        meta = self.get_metadata(config_path)
        if meta and 'user_friendly_label' in meta:
            return meta['user_friendly_label']

        # Fallback: capitalize last part of path
        return config_path.split('.')[-1].replace('_', ' ').title()

    def get_default_value(self, config_path: str) -> Any:
        """
        Get default value for a configuration parameter.

        Args:
            config_path: Dot-separated path to config parameter

        Returns:
            Default value, or None if not found
        """
        meta = self.get_metadata(config_path)
        if meta:
            return meta.get('default')
        return None

    def get_allowed_values(self, config_path: str) -> Optional[List[Any]]:
        """
        Get list of allowed values for a configuration parameter.

        Args:
            config_path: Dot-separated path to config parameter

        Returns:
            List of allowed values, or None if not applicable
        """
        meta = self.get_metadata(config_path)
        if meta and 'validation' in meta:
            return meta['validation'].get('allowed_values')
        return None

    def get_data_type(self, config_path: str) -> str:
        """
        Get data type for a configuration parameter.

        Args:
            config_path: Dot-separated path to config parameter

        Returns:
            Data type string: 'boolean', 'string', 'integer', 'number'
        """
        meta = self.get_metadata(config_path)
        if meta:
            return meta.get('data_type', 'string')
        return 'string'

    def validate_value(self, config_path: str, value: Any) -> Tuple[bool, str]:
        """
        Validate a configuration value against schema rules.

        Args:
            config_path: Dot-separated path to config parameter
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            >>> metadata = ConfigMetadata()
            >>> valid, error = metadata.validate_value('app.ui.profile', 'auto')
            >>> print(valid)
            True
        """
        meta = self.get_metadata(config_path)
        if not meta:
            return True, ""  # No validation rules = accept anything

        validation = meta.get('validation', {})

        # Check required
        if validation.get('required', False) and value is None:
            return False, f"{self.get_user_friendly_label(config_path)} is required"

        if value is None:
            return True, ""  # Optional and not provided

        # Check data type
        data_type = meta.get('data_type', 'string')
        if data_type == 'boolean' and not isinstance(value, bool):
            return False, "Expected boolean value"
        elif data_type == 'integer' and not isinstance(value, int):
            return False, "Expected integer value"
        elif data_type == 'string' and not isinstance(value, str):
            return False, "Expected string value"

        # Check allowed values
        allowed = validation.get('allowed_values')
        if allowed and value not in allowed:
            return False, f"Value must be one of: {', '.join(map(str, allowed))}"

        # Check min/max for numbers
        if data_type in ['integer', 'number']:
            min_val = validation.get('min')
            max_val = validation.get('max')
            if min_val is not None and value < min_val:
                return False, f"Value must be at least {min_val}"
            if max_val is not None and value > max_val:
                return False, f"Value must be at most {max_val}"

        # Check pattern for strings
        if data_type == 'string' and 'pattern' in validation:
            pattern = validation['pattern']
            if not re.match(pattern, value):
                return False, "Value does not match required format"

        return True, ""

    def get_all_config_paths(self, prefix: str = "app") -> List[str]:
        """
        Get all configuration paths that have metadata defined.

        Args:
            prefix: Starting prefix to filter paths (default: 'app')

        Returns:
            List of configuration paths as dot-separated strings
        """
        paths = []

        def traverse(node, current_path):
            if isinstance(node, dict):
                if 'widget_type' in node:
                    # This is a leaf node with metadata
                    paths.append(current_path)
                else:
                    # This is a container node, recurse
                    for key, value in node.items():
                        if not key.startswith('_'):  # Skip metadata keys
                            new_path = f"{current_path}.{key}" if current_path else key
                            traverse(value, new_path)

        # Start traversal from the prefix
        keys = prefix.split('.')
        current = self.schema
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return []

        traverse(current, prefix)
        return sorted(paths)

    def get_config_groups(self) -> Dict[str, List[str]]:
        """
        Get configuration parameters grouped by category.

        Returns:
            Dictionary mapping category names to lists of config paths

        Example:
            >>> metadata = ConfigMetadata()
            >>> groups = metadata.get_config_groups()
            >>> print(groups['UI'])
            ['app.ui.profile', 'app.ui.theme.active', ...]
        """
        all_paths = self.get_all_config_paths()
        groups = {}

        for path in all_paths:
            # Extract category from path (e.g., 'app.ui.profile' -> 'UI')
            parts = path.split('.')
            if len(parts) >= 2:
                category = parts[1].replace('_', ' ').title()
                if category not in groups:
                    groups[category] = []
                groups[category].append(path)

        return groups

    def export_schema_to_markdown(self, output_path: Optional[str] = None) -> str:
        """
        Export configuration schema to Markdown documentation.

        Args:
            output_path: Path to save markdown file. If None, returns string only.

        Returns:
            Markdown formatted string
        """
        md_lines = ["# FilterMate Configuration Reference\n"]
        md_lines.append("This document describes all available configuration parameters.\n")

        groups = self.get_config_groups()

        for category, paths in sorted(groups.items()):
            md_lines.append(f"\n## {category}\n")

            for path in paths:
                meta = self.get_metadata(path)
                if not meta:
                    continue

                label = self.get_user_friendly_label(path)
                md_lines.append(f"\n### {label}\n")
                md_lines.append(f"**Path**: `{path}`\n\n")
                md_lines.append(f"{meta['description']}\n\n")
                md_lines.append(f"- **Widget Type**: {meta['widget_type']}\n")
                md_lines.append(f"- **Data Type**: {meta['data_type']}\n")
                md_lines.append(f"- **Default**: `{meta.get('default', 'N/A')}`\n")

                if 'validation' in meta:
                    val = meta['validation']
                    if 'allowed_values' in val:
                        md_lines.append(f"- **Allowed Values**: {', '.join(f'`{v}`' for v in val['allowed_values'])}\n")
                    if 'min' in val or 'max' in val:
                        range_str = f"{val.get('min', '?')} to {val.get('max', '?')}"
                        md_lines.append(f"- **Range**: {range_str}\n")

        markdown = '\n'.join(md_lines)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

        return markdown


# Global singleton instance
_metadata_instance = None


def get_config_metadata() -> ConfigMetadata:
    """
    Get global ConfigMetadata instance (singleton pattern).

    Returns:
        ConfigMetadata instance
    """
    global _metadata_instance
    if _metadata_instance is None:
        _metadata_instance = ConfigMetadata()
    return _metadata_instance


def validate_config_value_with_metadata(config_path: str, value: Any) -> Tuple[bool, str]:
    """
    Validate a configuration value using global metadata instance.
    
    Args:
        config_path: Dot-separated path to config parameter
        value: Value to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    metadata = get_config_metadata()
    return metadata.validate_value(config_path, value)
