# -*- coding: utf-8 -*-
"""
FilterMate Configuration Module.

Provides configuration management, metadata handling, and schema validation.
"""

from .config import ENV_VARS  # noqa: F401
from .config_metadata import ConfigMetadata, get_config_metadata, validate_config_value_with_metadata  # noqa: F401
from .config_metadata_handler import (  # noqa: F401
    ConfigMetadataHandler,
    MetadataAwareConfigModel,
    enhance_config_editor_with_metadata,
    create_grouped_config_data
)
from .feedback_config import FeedbackLevel, get_feedback_level, should_show_message  # noqa: F401
from .theme_helpers import (  # noqa: F401
    get_config_value,
    get_active_theme,
    get_theme_colors,
    get_background_colors,
    get_font_colors,
    get_accent_colors,
    get_available_themes,
)

__all__ = [
    # Core config
    'ENV_VARS',
    # Metadata
    'ConfigMetadata',
    'get_config_metadata',
    'validate_config_value_with_metadata',
    # Metadata handler
    'ConfigMetadataHandler',
    'MetadataAwareConfigModel',
    'enhance_config_editor_with_metadata',
    'create_grouped_config_data',
    # Feedback
    'FeedbackLevel',
    'get_feedback_level',
    'should_show_message',
    # Theme
    'get_config_value',
    'get_active_theme',
    'get_theme_colors',
    'get_background_colors',
    'get_font_colors',
    'get_accent_colors',
    'get_available_themes',
]
