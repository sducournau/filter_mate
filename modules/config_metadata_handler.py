"""
Configuration Metadata Handler for qt_json_view

Handles intelligent extraction and presentation of metadata (descriptions)
embedded within configuration parameters.

Features:
- Extracts metadata from config with integrated descriptions
- Makes metadata visible in tooltips and UI
- Filters out metadata from editable fields
- Preserves metadata structure for documentation
"""

from typing import Dict, Any, List, Optional, Tuple


class ConfigMetadataHandler:
    """Handle metadata within configuration structures for qt_json_view"""
    
    # Keys that contain metadata instead of actual config values
    METADATA_KEYS = {
        "description",
        "tooltip",
        "help",
        "applies_to",
        "categories_affected",
        "available_translations",
        "auto_detection_thresholds"
    }
    
    @staticmethod
    def has_description(config_item: Any) -> bool:
        """
        Check if a configuration item has metadata.
        
        Args:
            config_item: Configuration item to check
        
        Returns:
            True if item has description or metadata
        """
        if not isinstance(config_item, dict):
            return False
        
        return any(key in config_item for key in ConfigMetadataHandler.METADATA_KEYS)
    
    @staticmethod
    def extract_metadata(config_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from configuration item.
        
        Args:
            config_item: Configuration item
        
        Returns:
            Dictionary of metadata
        """
        if not isinstance(config_item, dict):
            return {}
        
        metadata = {}
        for key in ConfigMetadataHandler.METADATA_KEYS:
            if key in config_item:
                metadata[key] = config_item[key]
        
        return metadata
    
    @staticmethod
    def get_description(config_item: Any, default: str = "") -> str:
        """
        Get description from configuration item.
        
        Args:
            config_item: Configuration item
            default: Default description if not found
        
        Returns:
            Description string
        """
        if not isinstance(config_item, dict):
            return default
        
        # Priority: description > tooltip > help
        for key in ["description", "tooltip", "help"]:
            if key in config_item:
                return str(config_item[key])
        
        return default
    
    @staticmethod
    def is_editable_value(key: str, value: Any) -> bool:
        """
        Check if a value should be editable in the UI.
        
        Args:
            key: Configuration key
            value: Configuration value
        
        Returns:
            True if value should be editable
        """
        # Metadata-only items should not be editable
        if key in ConfigMetadataHandler.METADATA_KEYS:
            return False
        
        # Items with only metadata should not be fully editable
        if isinstance(value, dict) and "value" not in value:
            # If it has description but no value, it's metadata-only
            if ConfigMetadataHandler.has_description(value) and len(value) <= len(ConfigMetadataHandler.METADATA_KEYS):
                # Check if ALL keys are metadata keys
                if all(k in ConfigMetadataHandler.METADATA_KEYS for k in value.keys()):
                    return False
        
        return True
    
    @staticmethod
    def get_displayable_value(config_item: Any) -> Tuple[Any, str]:
        """
        Get the actual displayable value and its type for qt_json_view.
        
        Args:
            config_item: Configuration item (may contain value + metadata)
        
        Returns:
            Tuple of (value, value_type)
        """
        if not isinstance(config_item, dict):
            return config_item, "raw"
        
        # If it has a "value" key, use that
        if "value" in config_item:
            actual_value = config_item["value"]
            
            # Determine value type
            if "choices" in config_item:
                return actual_value, "choice"
            elif isinstance(actual_value, bool):
                return actual_value, "boolean"
            elif isinstance(actual_value, (int, float)):
                return actual_value, "number"
            elif isinstance(actual_value, str):
                # Check for color
                if actual_value.startswith("#") and len(actual_value) in [7, 9]:
                    return actual_value, "color"
                return actual_value, "string"
            else:
                return actual_value, "unknown"
        
        # No explicit value, return the item as-is
        return config_item, "raw"
    
    @staticmethod
    def format_metadata_for_tooltip(config_item: Dict[str, Any]) -> str:
        """
        Format metadata as a tooltip string for UI display.
        
        Args:
            config_item: Configuration item
        
        Returns:
            Formatted tooltip string
        """
        metadata = ConfigMetadataHandler.extract_metadata(config_item)
        
        if not metadata:
            return ""
        
        tooltip_parts = []
        
        # Description first
        if "description" in metadata:
            tooltip_parts.append(str(metadata["description"]))
        
        # Additional metadata
        for key in ["applies_to", "help", "tooltip"]:
            if key in metadata:
                tooltip_parts.append(f"\n{key}: {metadata[key]}")
        
        # Available options
        if "available_translations" in metadata:
            tooltip_parts.append("\nAvailable languages:")
            for lang in metadata["available_translations"]:
                tooltip_parts.append(f"  • {lang}")
        
        if "categories_affected" in metadata:
            tooltip_parts.append("\nAffects:")
            for cat in metadata["categories_affected"]:
                tooltip_parts.append(f"  • {cat}")
        
        return "".join(tooltip_parts)
    
    @staticmethod
    def clean_config_for_editing(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean configuration by removing pure metadata entries.
        
        Keeps metadata integrated in value items, but removes standalone metadata items.
        
        Args:
            config_data: Configuration data
        
        Returns:
            Cleaned configuration
        """
        cleaned = {}
        
        for key, value in config_data.items():
            # Skip pure metadata items (those starting with underscore or all metadata keys)
            if key.startswith("_"):
                continue
            
            if isinstance(value, dict):
                # Check if this is a pure metadata dict (no actual values)
                has_value_keys = any(k not in ConfigMetadataHandler.METADATA_KEYS for k in value.keys())
                
                if not has_value_keys:
                    # Skip pure metadata
                    continue
                
                # Recursively clean nested dicts
                if "value" in value or "choices" in value:
                    # This is a config item with metadata, keep it
                    cleaned[key] = value
                else:
                    # This is a container, recurse
                    cleaned[key] = ConfigMetadataHandler.clean_config_for_editing(value)
            else:
                # Keep raw values
                cleaned[key] = value
        
        return cleaned


class MetadataAwareConfigModel:
    """
    Wrapper for configuration data that extracts and manages metadata.
    
    Integrates with qt_json_view to provide metadata-aware display.
    """
    
    def __init__(self, config_data: Dict[str, Any]):
        """
        Initialize the model.
        
        Args:
            config_data: Raw configuration data
        """
        self.raw_config = config_data
        self.metadata_handler = ConfigMetadataHandler()
    
    def get_metadata(self, path: List[str]) -> Dict[str, Any]:
        """
        Get metadata for a specific configuration path.
        
        Args:
            path: List of keys representing path (e.g., ["APP", "DOCKWIDGET", "LANGUAGE"])
        
        Returns:
            Dictionary of metadata for that item
        """
        item = self._get_item_at_path(path)
        if item is None:
            return {}
        
        return self.metadata_handler.extract_metadata(item)
    
    def get_description(self, path: List[str]) -> str:
        """
        Get description for a specific configuration path.
        
        Args:
            path: List of keys representing path
        
        Returns:
            Description string
        """
        item = self._get_item_at_path(path)
        if item is None:
            return ""
        
        return self.metadata_handler.get_description(item)
    
    def _get_item_at_path(self, path: List[str]) -> Optional[Any]:
        """Get configuration item at specified path."""
        current = self.raw_config
        
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


def enhance_config_editor_with_metadata(config_data: Dict[str, Any]) -> Tuple[Dict[str, Any], MetadataAwareConfigModel]:
    """
    Prepare configuration data and metadata model for qt_json_view.
    
    Args:
        config_data: Raw configuration data
    
    Returns:
        Tuple of (cleaned_config, metadata_model)
    """
    metadata_model = MetadataAwareConfigModel(config_data)
    
    # For display, we can optionally clean pure metadata items
    # but keep integrated metadata
    cleaned_config = config_data  # Keep as-is for now to preserve metadata
    
    return cleaned_config, metadata_model
