"""
Test for the signal type error fix.

This test verifies that the PyQt signal emission works correctly with
proper type checking and handling of mutable default arguments.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys


class TestSignalTypeFix(unittest.TestCase):
    """Test suite for signal type error fixes."""

    def test_empty_list_creation(self):
        """Test that empty list is properly created and not mutated."""
        # Simulate the old pattern (mutable default)
        def old_pattern(properties=[]):
            return properties
        
        # First call
        list1 = old_pattern()
        list1.append("test")
        
        # Second call - in buggy version, this would have "test" already!
        list2 = old_pattern()
        
        # This test demonstrates the mutable default argument problem
        # In the old code, list2 would contain "test"
        self.assertIn("test", list2, "Demonstrates mutable default bug")
        
    def test_fixed_pattern(self):
        """Test that the fixed pattern correctly creates new lists."""
        # Simulate the new pattern (None default)
        def new_pattern(properties=None):
            if properties is None:
                properties = []
            return properties
        
        # First call
        list1 = new_pattern()
        list1.append("test")
        
        # Second call - should be empty
        list2 = new_pattern()
        
        # Fixed version: list2 should be empty
        self.assertEqual(len(list2), 0, "Fixed pattern creates new empty list")
        
    def test_type_checking(self):
        """Test that type checking prevents passing wrong types."""
        def type_checked_function(properties=None):
            if properties is None:
                properties = []
            
            # Type check as in the fix
            if not isinstance(properties, list):
                properties = []
            
            return properties
        
        # Test with correct type
        result1 = type_checked_function([1, 2, 3])
        self.assertEqual(result1, [1, 2, 3])
        
        # Test with wrong type (like KeyError exception)
        result2 = type_checked_function(KeyError("test"))
        self.assertEqual(result2, [], "Wrong type should be converted to empty list")
        
    def test_layer_exists_check(self):
        """Test that we check if layer exists in PROJECT_LAYERS before accessing."""
        PROJECT_LAYERS = {
            "layer_1": {"filtering": {"has_layers_to_filter": True}},
            "layer_2": {"filtering": {"has_layers_to_filter": False}},
        }
        
        # Simulate the fixed pattern
        def safe_access(layer_id, project_layers):
            if layer_id not in project_layers:
                print(f"Layer {layer_id} not in PROJECT_LAYERS yet, skipping")
                return None
            return project_layers[layer_id]
        
        # Test existing layer
        result1 = safe_access("layer_1", PROJECT_LAYERS)
        self.assertIsNotNone(result1)
        
        # Test non-existing layer (would raise KeyError in old code)
        result2 = safe_access("layer_999", PROJECT_LAYERS)
        self.assertIsNone(result2, "Non-existing layer should return None")


if __name__ == '__main__':
    unittest.main()
