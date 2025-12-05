"""
Test FilterHistory integration in FilterMate

This test verifies that the FilterHistory module is properly integrated
and that the unfilter button correctly implements undo functionality.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.filter_history import FilterHistory, HistoryManager, FilterState


class TestFilterHistoryIntegration(unittest.TestCase):
    """Test FilterHistory integration with FilterMate"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.layer_id = "test_layer_123"
        self.history_manager = HistoryManager(max_size=100)
    
    def test_history_manager_initialization(self):
        """Test that HistoryManager can be created"""
        self.assertIsNotNone(self.history_manager)
        self.assertEqual(self.history_manager.max_size, 100)
        self.assertEqual(len(self.history_manager._histories), 0)
    
    def test_get_or_create_history(self):
        """Test getting or creating history for a layer"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        self.assertIsNotNone(history)
        self.assertIsInstance(history, FilterHistory)
        self.assertEqual(history.layer_id, self.layer_id)
        
        # Getting again should return same instance
        history2 = self.history_manager.get_or_create_history(self.layer_id)
        self.assertIs(history, history2)
    
    def test_push_filter_state(self):
        """Test pushing filter states to history"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        # Push first state
        history.push_state(
            expression='"population" > 10000',
            feature_count=150,
            description="Filter A",
            metadata={"backend": "postgresql", "operation": "filter"}
        )
        
        self.assertEqual(len(history._states), 1)
        self.assertEqual(history._current_index, 0)
        
        # Push second state
        history.push_state(
            expression='"population" > 50000',
            feature_count=45,
            description="Filter B",
            metadata={"backend": "postgresql", "operation": "filter"}
        )
        
        self.assertEqual(len(history._states), 2)
        self.assertEqual(history._current_index, 1)
    
    def test_undo_functionality(self):
        """Test undo (unfilter) functionality"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        # Push initial state
        history.push_state("", 1000, "Initial - no filter")
        
        # Push filter A
        history.push_state('"population" > 10000', 150, "Filter A")
        
        # Push filter B
        history.push_state('"population" > 50000', 45, "Filter B")
        
        # Current state should be Filter B
        current = history.get_current_state()
        self.assertEqual(current.expression, '"population" > 50000')
        self.assertEqual(current.feature_count, 45)
        
        # Undo to Filter A
        self.assertTrue(history.can_undo())
        previous = history.undo()
        
        self.assertIsNotNone(previous)
        self.assertEqual(previous.expression, '"population" > 10000')
        self.assertEqual(previous.feature_count, 150)
        
        # Undo to initial state
        self.assertTrue(history.can_undo())
        initial = history.undo()
        
        self.assertIsNotNone(initial)
        self.assertEqual(initial.expression, "")
        self.assertEqual(initial.feature_count, 1000)
        
        # Cannot undo further
        self.assertFalse(history.can_undo())
        self.assertIsNone(history.undo())
    
    def test_redo_functionality(self):
        """Test redo functionality (for future UI integration)"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        # Push states
        history.push_state("", 1000, "Initial")
        history.push_state('"population" > 10000', 150, "Filter A")
        history.push_state('"population" > 50000', 45, "Filter B")
        
        # Undo twice
        history.undo()
        history.undo()
        
        # Should be at initial state
        current = history.get_current_state()
        self.assertEqual(current.expression, "")
        
        # Redo to Filter A
        self.assertTrue(history.can_redo())
        next_state = history.redo()
        
        self.assertIsNotNone(next_state)
        self.assertEqual(next_state.expression, '"population" > 10000')
        
        # Redo to Filter B
        self.assertTrue(history.can_redo())
        next_state = history.redo()
        
        self.assertIsNotNone(next_state)
        self.assertEqual(next_state.expression, '"population" > 50000')
        
        # Cannot redo further
        self.assertFalse(history.can_redo())
        self.assertIsNone(history.redo())
    
    def test_new_filter_clears_future(self):
        """Test that pushing new filter clears future states"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        # Push 3 states
        history.push_state("", 1000, "Initial")
        history.push_state('"pop" > 10000', 150, "A")
        history.push_state('"pop" > 50000', 45, "B")
        
        # Undo once
        history.undo()
        self.assertEqual(history._current_index, 1)  # At state A
        
        # Push new filter C - should clear B
        history.push_state('"pop" > 30000', 75, "C")
        
        self.assertEqual(len(history._states), 3)  # Initial, A, C
        self.assertEqual(history._current_index, 2)
        
        # Cannot redo (B was cleared)
        self.assertFalse(history.can_redo())
    
    def test_reset_clears_history(self):
        """Test that reset operation clears history"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        # Push some states
        history.push_state("", 1000, "Initial")
        history.push_state('"pop" > 10000', 150, "A")
        
        self.assertEqual(len(history._states), 2)
        
        # Clear history (simulates reset)
        history.clear()
        
        self.assertEqual(len(history._states), 0)
        self.assertEqual(history._current_index, -1)
        self.assertFalse(history.can_undo())
        self.assertIsNone(history.get_current_state())
    
    def test_history_stats(self):
        """Test history statistics"""
        history = self.history_manager.get_or_create_history(self.layer_id)
        
        # Empty history
        stats = history.get_stats()
        self.assertEqual(stats["total_states"], 0)
        self.assertEqual(stats["current_position"], 0)
        self.assertFalse(stats["can_undo"])
        self.assertFalse(stats["can_redo"])
        
        # With states
        history.push_state("", 1000, "Initial")
        history.push_state('"pop" > 10000', 150, "A")
        
        stats = history.get_stats()
        self.assertEqual(stats["total_states"], 2)
        self.assertEqual(stats["current_position"], 2)
        self.assertTrue(stats["can_undo"])
        self.assertFalse(stats["can_redo"])
    
    def test_max_size_enforcement(self):
        """Test that history respects max_size limit"""
        small_manager = HistoryManager(max_size=5)
        history = small_manager.get_or_create_history(self.layer_id)
        
        # Push 10 states
        for i in range(10):
            history.push_state(f'"pop" > {i * 1000}', 100 - i, f"Filter {i}")
        
        # Should only keep last 5
        self.assertEqual(len(history._states), 5)
        
        # First state should be Filter 5 (0-4 were removed)
        first_state = history._states[0]
        self.assertEqual(first_state.description, "Filter 5")
    
    def test_multiple_layers(self):
        """Test managing history for multiple layers"""
        layer1_id = "layer_1"
        layer2_id = "layer_2"
        
        history1 = self.history_manager.get_or_create_history(layer1_id)
        history2 = self.history_manager.get_or_create_history(layer2_id)
        
        # Different histories
        self.assertIsNot(history1, history2)
        
        # Push to layer 1
        history1.push_state('"pop" > 10000', 150, "Layer 1 Filter")
        
        # Push to layer 2
        history2.push_state('"area" > 1000', 200, "Layer 2 Filter")
        
        # Histories are independent
        self.assertEqual(len(history1._states), 1)
        self.assertEqual(len(history2._states), 1)
        
        stats = self.history_manager.get_all_stats()
        self.assertEqual(len(stats), 2)
        self.assertIn(layer1_id, stats)
        self.assertIn(layer2_id, stats)
    
    def test_filter_state_description_generation(self):
        """Test automatic description generation for long expressions"""
        state1 = FilterState(
            expression='"population" > 10000',
            feature_count=150
        )
        self.assertEqual(state1.description, '"population" > 10000')
        
        # Long expression should be truncated
        long_expr = '"field1" = \'value1\' AND "field2" = \'value2\' AND "field3" > 1000 AND "field4" < 5000'
        state2 = FilterState(
            expression=long_expr,
            feature_count=50
        )
        self.assertEqual(len(state2.description), 60)  # 57 chars + "..."
        self.assertTrue(state2.description.endswith("..."))
    
    def test_empty_expression_description(self):
        """Test description for empty/no filter"""
        state = FilterState(expression="", feature_count=1000)
        self.assertEqual(state.description, "No filter (all features visible)")


class TestFilterHistoryMockIntegration(unittest.TestCase):
    """Test FilterHistory integration with mocked QGIS components"""
    
    @patch('modules.filter_history.logger')
    def test_logging_on_push(self, mock_logger):
        """Test that logging occurs on state push"""
        history = FilterHistory("test_layer", max_size=100)
        
        history.push_state('"pop" > 10000', 150, "Test Filter")
        
        # Verify logging was called
        self.assertTrue(mock_logger.info.called)
    
    def test_thread_safety_flag(self):
        """Test that _is_undoing flag prevents recording during undo/redo"""
        history = FilterHistory("test_layer")
        
        # Push initial states
        history.push_state("", 1000, "Initial")
        history.push_state('"pop" > 10000', 150, "A")
        
        # Undo (sets _is_undoing=True temporarily)
        history.undo()
        
        # Verify flag is reset
        self.assertFalse(history._is_undoing)
        
        # Should still be able to push new state (clears "A" since we undid it)
        history.push_state('"pop" > 20000', 100, "B")
        self.assertEqual(len(history._states), 2)  # Initial and B (A was cleared)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestFilterHistoryIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestFilterHistoryMockIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
