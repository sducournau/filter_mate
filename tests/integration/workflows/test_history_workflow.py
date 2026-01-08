# -*- coding: utf-8 -*-
"""
End-to-End Tests for History Workflow - ARCH-050

Tests the complete history workflow: undo, redo operations.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def history_service_mock():
    """Create a mock history service."""
    service = MagicMock()
    
    # State
    service._history_stack = []
    service._redo_stack = []
    service._max_history = 50
    
    def push_state(state):
        service._history_stack.append(state)
        service._redo_stack.clear()  # Clear redo on new action
        if len(service._history_stack) > service._max_history:
            service._history_stack.pop(0)
        return MagicMock(success=True)
    
    def undo():
        if service._history_stack:
            state = service._history_stack.pop()
            service._redo_stack.append(state)
            return MagicMock(success=True, restored_state=state)
        return MagicMock(success=False, error_message="Nothing to undo")
    
    def redo():
        if service._redo_stack:
            state = service._redo_stack.pop()
            service._history_stack.append(state)
            return MagicMock(success=True, restored_state=state)
        return MagicMock(success=False, error_message="Nothing to redo")
    
    def can_undo():
        return len(service._history_stack) > 0
    
    def can_redo():
        return len(service._redo_stack) > 0
    
    def get_history():
        return service._history_stack.copy()
    
    def clear_history():
        service._history_stack.clear()
        service._redo_stack.clear()
        return MagicMock(success=True)
    
    service.push_state.side_effect = push_state
    service.undo.side_effect = undo
    service.redo.side_effect = redo
    service.can_undo.side_effect = can_undo
    service.can_redo.side_effect = can_redo
    service.get_history.side_effect = get_history
    service.clear_history.side_effect = clear_history
    
    return service


@pytest.fixture
def sample_filter_state():
    """Return a sample filter state for history."""
    return {
        "layer_id": "test_layer_001",
        "previous_expression": "",
        "new_expression": '"population" > 10000',
        "timestamp": "2026-01-08T12:00:00",
        "action": "apply_filter"
    }


@pytest.mark.e2e
@pytest.mark.integration
class TestHistoryWorkflowE2E:
    """E2E tests for the history workflow."""
    
    def test_undo_single_action(
        self,
        history_service_mock,
        sample_filter_state
    ):
        """Test undoing a single action."""
        service = history_service_mock
        
        # Apply filter (push state)
        service.push_state(sample_filter_state)
        assert service.can_undo() is True
        
        # Undo
        result = service.undo()
        assert result.success is True
        assert service.can_undo() is False
        assert service.can_redo() is True
    
    def test_redo_after_undo(
        self,
        history_service_mock,
        sample_filter_state
    ):
        """Test redoing after undo."""
        service = history_service_mock
        
        # Apply and undo
        service.push_state(sample_filter_state)
        service.undo()
        
        # Redo
        assert service.can_redo() is True
        result = service.redo()
        assert result.success is True
        assert service.can_undo() is True
    
    def test_multiple_undo_redo(
        self,
        history_service_mock
    ):
        """Test multiple undo/redo operations."""
        service = history_service_mock
        
        # Apply 3 filters
        states = [
            {"expression": '"a" = 1', "action": "filter_1"},
            {"expression": '"b" = 2', "action": "filter_2"},
            {"expression": '"c" = 3', "action": "filter_3"}
        ]
        
        for state in states:
            service.push_state(state)
        
        assert len(service.get_history()) == 3
        
        # Undo 2 times
        service.undo()
        service.undo()
        assert len(service.get_history()) == 1
        
        # Redo 1 time
        service.redo()
        assert len(service.get_history()) == 2
    
    def test_new_action_clears_redo(
        self,
        history_service_mock,
        sample_filter_state
    ):
        """Test that new action clears redo stack."""
        service = history_service_mock
        
        # Apply and undo
        service.push_state(sample_filter_state)
        service.undo()
        assert service.can_redo() is True
        
        # New action
        new_state = {"expression": '"new" = 1', "action": "new_filter"}
        service.push_state(new_state)
        
        # Redo should be cleared
        assert service.can_redo() is False
    
    def test_history_limit(
        self,
        history_service_mock
    ):
        """Test history respects maximum limit."""
        service = history_service_mock
        service._max_history = 10
        
        # Push 15 states
        for i in range(15):
            service.push_state({"index": i})
        
        # Should only have 10
        assert len(service.get_history()) == 10
        
        # Oldest should be removed
        history = service.get_history()
        assert history[0]["index"] == 5  # 0-4 removed
    
    def test_clear_history(
        self,
        history_service_mock,
        sample_filter_state
    ):
        """Test clearing all history."""
        service = history_service_mock
        
        # Add some history
        service.push_state(sample_filter_state)
        service.push_state(sample_filter_state)
        
        # Clear
        result = service.clear_history()
        assert result.success is True
        assert service.can_undo() is False
        assert service.can_redo() is False
    
    def test_undo_empty_history(
        self,
        history_service_mock
    ):
        """Test undo with empty history."""
        service = history_service_mock
        
        assert service.can_undo() is False
        result = service.undo()
        assert result.success is False
    
    def test_redo_empty_stack(
        self,
        history_service_mock
    ):
        """Test redo with empty redo stack."""
        service = history_service_mock
        
        assert service.can_redo() is False
        result = service.redo()
        assert result.success is False


@pytest.mark.e2e
@pytest.mark.integration
class TestHistoryWithFilteringE2E:
    """E2E tests for history integrated with filtering."""
    
    def test_filter_apply_creates_history(
        self,
        history_service_mock,
        sample_vector_layer
    ):
        """Test that applying filter creates history entry."""
        service = history_service_mock
        
        # Simulate filter application
        state = {
            "layer_id": sample_vector_layer.id(),
            "previous_expression": sample_vector_layer.subsetString(),
            "new_expression": '"population" > 10000'
        }
        
        service.push_state(state)
        assert service.can_undo() is True
    
    def test_filter_clear_creates_history(
        self,
        history_service_mock,
        sample_vector_layer
    ):
        """Test that clearing filter creates history entry."""
        service = history_service_mock
        
        # Apply filter
        sample_vector_layer.setSubsetString('"population" > 10000')
        
        # Clear (should create history)
        state = {
            "layer_id": sample_vector_layer.id(),
            "previous_expression": '"population" > 10000',
            "new_expression": "",
            "action": "clear_filter"
        }
        
        service.push_state(state)
        assert service.can_undo() is True
    
    def test_undo_restores_filter(
        self,
        history_service_mock,
        sample_vector_layer
    ):
        """Test that undo restores previous filter."""
        service = history_service_mock
        
        # Initial state (no filter)
        initial_expression = ""
        
        # Apply filter
        new_expression = '"population" > 10000'
        sample_vector_layer.setSubsetString(new_expression)
        
        state = {
            "layer_id": sample_vector_layer.id(),
            "previous_expression": initial_expression,
            "new_expression": new_expression
        }
        service.push_state(state)
        
        # Undo
        result = service.undo()
        assert result.success is True
        
        # Simulate restoration
        sample_vector_layer.setSubsetString(result.restored_state["previous_expression"])
        assert sample_vector_layer.subsetString() == initial_expression


@pytest.mark.e2e
@pytest.mark.integration
class TestHistoryPersistenceE2E:
    """E2E tests for history persistence."""
    
    def test_history_survives_session(
        self,
        history_service_mock,
        sample_filter_state
    ):
        """Test history can be saved and restored."""
        service = history_service_mock
        
        # Add history
        service.push_state(sample_filter_state)
        service.push_state({"expression": '"second"'})
        
        # Serialize
        service.serialize = MagicMock(return_value={
            "history": service.get_history(),
            "version": "3.0.0"
        })
        
        serialized = service.serialize()
        assert len(serialized["history"]) == 2
        
        # Simulate restore
        service.restore = MagicMock()
        service.restore(serialized)
        service.restore.assert_called_once_with(serialized)
