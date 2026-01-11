"""
Type Utilities Module

Provides type casting and conversion utilities used throughout FilterMate.

Migrated from modules/type_utils.py to utils/type_utils.py

Functions:
    - can_cast: Check if a value can be cast to a target type
    - return_typed_value: Convert string to typed value with auto-detection
"""

import json
import logging

# Setup logger
logger = logging.getLogger('FilterMate.TypeUtils')


def can_cast(dest_type, source_value):
    """
    Check if a value can be cast to a destination type.
    
    Args:
        dest_type (type): Target type (int, float, str, dict, list, bool)
        source_value: Value to check for castability
        
    Returns:
        bool: True if the value can be cast to dest_type, False otherwise
        
    Examples:
        >>> can_cast(int, "123")
        True
        >>> can_cast(int, "abc")
        False
        >>> can_cast(float, "3.14")
        True
    """
    try:
        dest_type(source_value)
        return True
    except (ValueError, TypeError, OverflowError):
        return False


def return_typed_value(value_as_string, action=None):
    """
    Convert string value to typed value with automatic type detection.
    
    Detects and converts to: dict, list, bool, float, int, or str (fallback).
    
    Args:
        value_as_string: String value to convert
        action (str, optional): 'save' for serialization, 'load' for deserialization
            - 'save': Converts dict/list to JSON string
            - 'load': Parses JSON string to dict/list
            - None: Returns typed value as-is
            
    Returns:
        tuple: (typed_value, type_class)
            - typed_value: The converted value
            - type_class: The Python type class (dict, list, bool, float, int, str)
            
    Examples:
        >>> return_typed_value("123")
        (123, <class 'int'>)
        >>> return_typed_value("3.14")
        (3.14, <class 'float'>)
        >>> return_typed_value("true")
        (True, <class 'bool'>)
        >>> return_typed_value('{"key": "value"}', action='load')
        ({'key': 'value'}, <class 'dict'>)
    """
    value_typed = None
    type_returned = None

    # Handle None or empty string
    if value_as_string is None or value_as_string == '':
        value_typed = str('')
        type_returned = str
        
    # Handle dict (JSON object)
    elif str(value_as_string).find('{') == 0 and can_cast(dict, value_as_string):
        if action == 'save':
            value_typed = json.dumps(dict(value_as_string))
        elif action == 'load':
            value_typed = dict(json.loads(value_as_string))
        else:
            value_typed = value_as_string
        type_returned = dict
        
    # Handle list (JSON array)
    elif str(value_as_string).find('[') == 0 and can_cast(list, value_as_string):
        if action == 'save':
            value_typed = list(value_as_string)
        elif action == 'load':
            value_typed = list(json.loads(value_as_string))
        else:
            value_typed = value_as_string
        type_returned = list
        
    # Handle bool (case-insensitive TRUE/FALSE)
    elif can_cast(bool, value_as_string) and str(value_as_string).upper() in ('FALSE', 'TRUE'):
        # Explicit bool conversion (Python's bool('False') returns True!)
        if str(value_as_string).upper() == 'FALSE':
            value_typed = False
        elif str(value_as_string).upper() == 'TRUE':
            value_typed = True
        type_returned = bool
        
    # Handle float (must contain decimal point)
    elif can_cast(float, value_as_string) and len(str(value_as_string).split('.')) > 1:
        value_typed = float(value_as_string)
        type_returned = float
        
    # Handle int
    elif can_cast(int, value_as_string):
        value_typed = int(value_as_string)
        type_returned = int
        
    # Fallback to string
    else:
        value_typed = str(value_as_string)
        type_returned = str

    return value_typed, type_returned


# Alias for backwards compatibility with method name typo
return_typped_value = return_typed_value
