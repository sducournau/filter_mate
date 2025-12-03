"""
Unit Tests for FilterMate Filter History Module

Tests for the filter_history.py module that implements undo/redo functionality.
"""

import pytest
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.filter_history import FilterState, FilterHistory, HistoryManager


class TestFilterState:
    """Tests for FilterState class"""
    
    def test_filter_state_creation(self):
        """Test creating a filter state"""
        state = FilterState("population > 10000", 150, "Large cities")
        
        assert state.expression == "population > 10000"
        assert state.feature_count == 150
        assert state.description == "Large cities"
        assert isinstance(state.timestamp, datetime)
        assert state.metadata == {}
    
    def test_filter_state_with_metadata(self):
        """Test creating filter state with metadata"""
        metadata = {"backend": "postgresql", "operation": "filter"}
        state = FilterState("area > 500", 75, metadata=metadata)
        
        assert state.metadata == metadata
    
    def test_auto_description_short_expression(self):
        """Test auto-generated description for short expression"""
        state = FilterState("population > 10000", 150)
        
        assert state.description == "population > 10000"
    
    def test_auto_description_long_expression(self):
        """Test auto-generated description truncation for long expression"""
        long_expr = "a" * 100
        state = FilterState(long_expr, 150)
        
        assert len(state.description) <= 60
        assert state.description.endswith("...")
    
    def test_auto_description_empty_expression(self):
        """Test auto-generated description for empty expression"""
        state = FilterState("", 1000)
        
        assert "no filter" in state.description.lower()
    
    def test_filter_state_repr(self):
        """Test string representation of filter state"""
        state = FilterState("test_expr", 100, "Test Filter")
        repr_str = repr(state)
        
        assert "Test Filter" in repr_str
        assert "100" in repr_str


class TestFilterHistory:
    """Tests for FilterHistory class"""
    
    def test_filter_history_creation(self):
        """Test creating a filter history"""
        history = FilterHistory("layer_001", max_size=50)
        
        assert history.layer_id == "layer_001"
        assert history.max_size == 50
        assert not history.can_undo()
        assert not history.can_redo()
    
    def test_push_single_state(self):
        """Test pushing a single state"""
        history = FilterHistory("layer_001")
        history.push_state("pop > 1000", 50, "Test filter")
        
        assert not history.can_undo()  # Only one state, nothing to undo to
        assert not history.can_redo()
        
        current = history.get_current_state()
        assert current.expression == "pop > 1000"
        assert current.feature_count == 50
    
    def test_push_multiple_states(self):
        """Test pushing multiple states"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "No filter")
        history.push_state("pop > 1000", 500, "Filter 1")
        history.push_state("pop > 5000", 200, "Filter 2")
        
        assert history.can_undo()
        assert not history.can_redo()
        
        current = history.get_current_state()
        assert current.description == "Filter 2"
    
    def test_undo_single_step(self):
        """Test undoing one step"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "State 1")
        history.push_state("pop > 1000", 500, "State 2")
        
        previous = history.undo()
        
        assert previous is not None
        assert previous.description == "State 1"
        assert history.can_redo()
    
    def test_undo_multiple_steps(self):
        """Test undoing multiple steps"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "State 1")
        history.push_state("filter1", 500, "State 2")
        history.push_state("filter2", 200, "State 3")
        
        state = history.undo()
        assert state.description == "State 2"
        
        state = history.undo()
        assert state.description == "State 1"
        
        assert not history.can_undo()  # At beginning
    
    def test_redo_after_undo(self):
        """Test redoing after undo"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "State 1")
        history.push_state("filter1", 500, "State 2")
        
        history.undo()
        state = history.redo()
        
        assert state is not None
        assert state.description == "State 2"
        assert not history.can_redo()
    
    def test_push_after_undo_clears_future(self):
        """Test that pushing after undo clears future states"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "State 1")
        history.push_state("filter1", 500, "State 2")
        history.push_state("filter2", 200, "State 3")
        
        history.undo()  # Back to State 2
        history.undo()  # Back to State 1
        
        history.push_state("new_filter", 300, "New State")
        
        # Should have cleared State 2 and State 3
        assert not history.can_redo()
        assert history.get_current_state().description == "New State"
    
    def test_max_size_enforcement(self):
        """Test that history respects max_size"""
        history = FilterHistory("layer_001", max_size=3)
        
        for i in range(5):
            history.push_state(f"filter{i}", 100 * i, f"State {i}")
        
        stats = history.get_stats()
        assert stats["total_states"] == 3  # Only keeps last 3
    
    def test_cannot_undo_at_beginning(self):
        """Test that undo returns None at beginning"""
        history = FilterHistory("layer_001")
        history.push_state("", 1000, "State 1")
        
        result = history.undo()
        assert result is None
        assert not history.can_undo()
    
    def test_cannot_redo_at_end(self):
        """Test that redo returns None at end"""
        history = FilterHistory("layer_001")
        history.push_state("", 1000, "State 1")
        
        result = history.redo()
        assert result is None
        assert not history.can_redo()
    
    def test_get_history_recent_items(self):
        """Test getting recent history items"""
        history = FilterHistory("layer_001")
        
        for i in range(5):
            history.push_state(f"filter{i}", 100, f"State {i}")
        
        recent = history.get_history(max_items=3)
        
        assert len(recent) == 3
        # Most recent first
        assert recent[0].description == "State 4"
        assert recent[1].description == "State 3"
        assert recent[2].description == "State 2"
    
    def test_clear_history(self):
        """Test clearing all history"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "State 1")
        history.push_state("filter1", 500, "State 2")
        
        history.clear()
        
        assert not history.can_undo()
        assert not history.can_redo()
        assert history.get_current_state() is None
    
    def test_get_stats(self):
        """Test getting history statistics"""
        history = FilterHistory("layer_001", max_size=50)
        
        history.push_state("", 1000, "State 1")
        history.push_state("filter1", 500, "State 2")
        history.undo()
        
        stats = history.get_stats()
        
        assert stats["layer_id"] == "layer_001"
        assert stats["total_states"] == 2
        assert stats["current_position"] == 1
        assert stats["can_undo"] == False
        assert stats["can_redo"] == True
        assert stats["max_size"] == 50
    
    def test_serialization_roundtrip(self):
        """Test serializing and deserializing history"""
        history = FilterHistory("layer_001")
        
        history.push_state("", 1000, "State 1", {"backend": "postgresql"})
        history.push_state("filter1", 500, "State 2")
        
        # Serialize
        data = history.to_dict()
        
        # Deserialize
        restored = FilterHistory.from_dict(data)
        
        assert restored.layer_id == history.layer_id
        assert restored.get_stats()["total_states"] == 2
        assert restored.get_current_state().description == "State 2"


class TestHistoryManager:
    """Tests for HistoryManager class"""
    
    def test_history_manager_creation(self):
        """Test creating a history manager"""
        manager = HistoryManager(max_size=75)
        
        assert manager.max_size == 75
    
    def test_get_or_create_new_history(self):
        """Test getting or creating a new history"""
        manager = HistoryManager()
        
        history = manager.get_or_create_history("layer_001")
        
        assert history is not None
        assert history.layer_id == "layer_001"
        assert history.max_size == manager.max_size
    
    def test_get_or_create_existing_history(self):
        """Test getting an existing history"""
        manager = HistoryManager()
        
        history1 = manager.get_or_create_history("layer_001")
        history1.push_state("filter1", 100)
        
        history2 = manager.get_or_create_history("layer_001")
        
        assert history1 is history2  # Same instance
        assert history2.get_current_state() is not None
    
    def test_get_nonexistent_history(self):
        """Test getting a history that doesn't exist"""
        manager = HistoryManager()
        
        history = manager.get_history("nonexistent")
        
        assert history is None
    
    def test_remove_history(self):
        """Test removing a layer's history"""
        manager = HistoryManager()
        
        manager.get_or_create_history("layer_001")
        manager.remove_history("layer_001")
        
        assert manager.get_history("layer_001") is None
    
    def test_clear_all_histories(self):
        """Test clearing all histories"""
        manager = HistoryManager()
        
        manager.get_or_create_history("layer_001")
        manager.get_or_create_history("layer_002")
        
        manager.clear_all()
        
        assert manager.get_history("layer_001") is None
        assert manager.get_history("layer_002") is None
    
    def test_get_all_stats(self):
        """Test getting stats for all histories"""
        manager = HistoryManager()
        
        hist1 = manager.get_or_create_history("layer_001")
        hist1.push_state("filter1", 100)
        
        hist2 = manager.get_or_create_history("layer_002")
        hist2.push_state("filter2", 200)
        hist2.push_state("filter3", 150)
        
        all_stats = manager.get_all_stats()
        
        assert len(all_stats) == 2
        assert all_stats["layer_001"]["total_states"] == 1
        assert all_stats["layer_002"]["total_states"] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=modules.filter_history', '--cov-report=term-missing'])
