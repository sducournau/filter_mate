"""
FilterMate Infrastructure Config.

Configuration management and schema validation.
"""
from typing import Any, Dict, Optional  # noqa: F401


def set_config_value(config_data: Dict, *keys, value: Any) -> None:
    """
    Set a configuration value by nested keys.

    Args:
        config_data: The configuration dictionary to modify
        *keys: The nested keys path (e.g., 'app', 'theme', 'name')
        value: The value to set

    Example:
        set_config_value(config, 'app', 'theme', 'name', value='dark')
        # Results in: config['app']['theme']['name'] = 'dark'
    """
    if not keys:
        return

    current = config_data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def get_config_value(config_data: Dict, *keys, default: Any = None) -> Any:
    """
    Get a configuration value by nested keys.

    Args:
        config_data: The configuration dictionary
        *keys: The nested keys path
        default: Default value if key not found

    Returns:
        The value at the key path, or default if not found
    """
    current = config_data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


__all__ = [
    'set_config_value',
    'get_config_value',
]
