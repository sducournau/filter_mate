"""
Test script for Undo/Redo functionality in FilterMate

This script validates the undo/redo implementation by simulating
various scenarios without requiring QGIS to be running.

Run with: python3 tests/test_undo_redo.py
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.filter_history import FilterState, FilterHistory, GlobalFilterState, HistoryManager


def test_filter_state():
    """Test FilterState class"""
    print("\n=== Testing FilterState ===")
    
    # Test basic state
    state = FilterState("population > 10000", 150, "Large cities")
    assert state.expression == "population > 10000"
    assert state.feature_count == 150
    assert state.description == "Large cities"
    assert isinstance(state.timestamp, datetime)
    print("✓ FilterState creation works")
    
    # Test automatic description
    state2 = FilterState("", 1000)
    assert "No filter" in state2.description
    print("✓ Automatic description for empty filter works")
    
    # Test long expression truncation
    long_expr = "a" * 100
    state3 = FilterState(long_expr, 50)
    assert len(state3.description) <= 63
    assert "..." in state3.description
    print("✓ Long expression truncation works")


def test_filter_history():
    """Test FilterHistory class"""
    print("\n=== Testing FilterHistory ===")
    
    history = FilterHistory("layer_1", max_size=5)
    
    # Test initial state
    assert not history.can_undo()
    assert not history.can_redo()
    print("✓ Initial state correct")
    
    # Push first state
    history.push_state("filter1", 100, "First filter")
    assert history.can_undo() == False  # Can't undo from first state
    assert not history.can_redo()
    print("✓ First state push works")
    
    # Push second state
    history.push_state("filter2", 50, "Second filter")
    assert history.can_undo()
    assert not history.can_redo()
    print("✓ Second state push works")
    
    # Undo
    prev_state = history.undo()
    assert prev_state.expression == "filter1"
    assert history.can_undo() == False
    assert history.can_redo()
    print("✓ Undo works")
    
    # Redo
    next_state = history.redo()
    assert next_state.expression == "filter2"
    assert history.can_undo()
    assert not history.can_redo()
    print("✓ Redo works")
    
    # Test max size
    for i in range(3, 10):
        history.push_state(f"filter{i}", i * 10, f"Filter {i}")
    
    assert len(history._states) == 5  # Max size enforced
    print("✓ Max size enforcement works")
    
    # Test branching (clearing future states)
    history.undo()
    history.undo()
    history.push_state("new_branch", 25, "New branch")
    assert not history.can_redo()  # Future cleared
    print("✓ History branching works")


def test_global_filter_state():
    """Test GlobalFilterState class"""
    print("\n=== Testing GlobalFilterState ===")
    
    # Test without remote layers
    state1 = GlobalFilterState(
        source_layer_id="layer1",
        source_expression="filter1",
        source_feature_count=100
    )
    assert not state1.has_remote_layers()
    assert "source layer" in state1.description.lower()
    print("✓ GlobalFilterState without remote layers works")
    
    # Test with remote layers
    remote = {
        "layer2": ("filter2", 50),
        "layer3": ("filter3", 75)
    }
    state2 = GlobalFilterState(
        source_layer_id="layer1",
        source_expression="filter1",
        source_feature_count=100,
        remote_layers=remote
    )
    assert state2.has_remote_layers()
    assert "3 layers" in state2.description
    print("✓ GlobalFilterState with remote layers works")


def test_history_manager():
    """Test HistoryManager class"""
    print("\n=== Testing HistoryManager ===")
    
    manager = HistoryManager(max_size=100)
    
    # Test layer history creation
    history1 = manager.get_or_create_history("layer1")
    assert isinstance(history1, FilterHistory)
    
    history2 = manager.get_or_create_history("layer1")
    assert history1 is history2  # Same instance
    print("✓ Layer history get_or_create works")
    
    # Test global history
    assert not manager.can_undo_global()
    assert not manager.can_redo_global()
    
    manager.push_global_state(
        source_layer_id="layer1",
        source_expression="filter1",
        source_feature_count=100,
        remote_layers={"layer2": ("filter2", 50)}
    )
    
    assert manager.can_undo_global() == False  # First state
    assert not manager.can_redo_global()
    print("✓ Global history push works")
    
    manager.push_global_state(
        source_layer_id="layer1",
        source_expression="filter1b",
        source_feature_count=80,
        remote_layers={"layer2": ("filter2b", 40)}
    )
    
    assert manager.can_undo_global()
    print("✓ Multiple global states work")
    
    # Test global undo
    prev_global = manager.undo_global()
    assert prev_global.source_expression == "filter1"
    assert manager.can_redo_global()
    print("✓ Global undo works")
    
    # Test global redo
    next_global = manager.redo_global()
    assert next_global.source_expression == "filter1b"
    print("✓ Global redo works")
    
    # Test history removal
    manager.remove_history("layer1")
    assert manager.get_history("layer1") is None
    print("✓ History removal works")
    
    # Test global history clearing
    manager.clear_global_history()
    assert not manager.can_undo_global()
    assert len(manager._global_states) == 0
    print("✓ Global history clearing works")


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n=== Testing Edge Cases ===")
    
    manager = HistoryManager()
    
    # Undo/redo when empty
    assert manager.undo_global() is None
    assert manager.redo_global() is None
    print("✓ Empty history undo/redo returns None")
    
    # Undo at beginning
    manager.push_global_state("layer1", "f1", 100, {})
    assert manager.undo_global() is None
    print("✓ Undo at beginning returns None")
    
    # Redo at end
    manager.push_global_state("layer1", "f2", 100, {})
    assert manager.redo_global() is None
    print("✓ Redo at end returns None")
    
    # Stats when empty
    stats = manager.get_global_stats()
    assert stats["total_states"] >= 0
    assert stats["can_undo"] in [True, False]
    print("✓ Stats work correctly")


def test_serialization():
    """Test history serialization"""
    print("\n=== Testing Serialization ===")
    
    # Create and populate history
    history = FilterHistory("layer1", max_size=10)
    history.push_state("filter1", 100, "Test 1")
    history.push_state("filter2", 50, "Test 2")
    
    # Serialize
    data = history.to_dict()
    assert data["layer_id"] == "layer1"
    assert len(data["states"]) == 2
    print("✓ History serialization works")
    
    # Deserialize
    restored = FilterHistory.from_dict(data)
    assert restored.layer_id == "layer1"
    assert len(restored._states) == 2
    assert restored._states[0].expression == "filter1"
    print("✓ History deserialization works")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*60)
    print("FilterMate Undo/Redo Test Suite")
    print("="*60)
    
    try:
        test_filter_state()
        test_filter_history()
        test_global_filter_state()
        test_history_manager()
        test_edge_cases()
        test_serialization()
        
        print("\n" + "="*60)
        print("✓ All tests passed successfully!")
        print("="*60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
