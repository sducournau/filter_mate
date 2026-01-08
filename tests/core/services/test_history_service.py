"""
Tests for HistoryService.

Part of Phase 3 Core Domain Layer implementation.
"""
import pytest
from core.services.history_service import (
    HistoryService, HistoryEntry
)


class TestHistoryEntryCreation:
    """Tests for HistoryEntry creation."""

    def test_create_simple_entry(self):
        """Test creating a simple history entry."""
        entry = HistoryEntry.create(
            expression="\"name\" = 'test'",
            layer_ids=["layer_123"],
            previous_filters=[("layer_123", "")]
        )
        assert entry.expression == "\"name\" = 'test'"
        assert "layer_123" in entry.layer_ids
        assert entry.entry_id.startswith("hist_")

    def test_create_with_description(self):
        """Test creating entry with custom description."""
        entry = HistoryEntry.create(
            expression="\"name\" = 'test'",
            layer_ids=["layer_123"],
            previous_filters=[],
            description="Custom description"
        )
        assert entry.description == "Custom description"

    def test_create_auto_description(self):
        """Test auto-generated description."""
        entry = HistoryEntry.create(
            expression="\"name\" = 'test'",
            layer_ids=["layer_123"],
            previous_filters=[]
        )
        assert "Filter:" in entry.description
        assert "name" in entry.description

    def test_create_with_metadata(self):
        """Test creating entry with metadata."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_123"],
            previous_filters=[],
            metadata={"key": "value"}
        )
        assert entry.get_metadata_value("key") == "value"

    def test_layer_count(self):
        """Test layer_count property."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_1", "layer_2", "layer_3"],
            previous_filters=[]
        )
        assert entry.layer_count == 3


class TestHistoryEntryImmutability:
    """Tests for HistoryEntry immutability."""

    def test_entry_is_frozen(self):
        """Test that entry cannot be modified."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_123"],
            previous_filters=[]
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.expression = "modified"

    def test_layer_ids_is_tuple(self):
        """Test that layer_ids is immutable tuple."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_123"],
            previous_filters=[]
        )
        assert isinstance(entry.layer_ids, tuple)


class TestHistoryEntryPreviousFilters:
    """Tests for HistoryEntry previous filter handling."""

    def test_has_previous_filters_true(self):
        """Test has_previous_filters when filters exist."""
        entry = HistoryEntry.create(
            expression="new filter",
            layer_ids=["layer_123"],
            previous_filters=[("layer_123", "old filter")]
        )
        assert entry.has_previous_filters

    def test_has_previous_filters_false(self):
        """Test has_previous_filters when no filters."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_123"],
            previous_filters=[]
        )
        assert not entry.has_previous_filters

    def test_get_previous_filter_found(self):
        """Test getting previous filter for layer."""
        entry = HistoryEntry.create(
            expression="new",
            layer_ids=["layer_1", "layer_2"],
            previous_filters=[
                ("layer_1", "old_1"),
                ("layer_2", "old_2")
            ]
        )
        assert entry.get_previous_filter("layer_1") == "old_1"
        assert entry.get_previous_filter("layer_2") == "old_2"

    def test_get_previous_filter_not_found(self):
        """Test getting previous filter for unknown layer."""
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_123"],
            previous_filters=[]
        )
        assert entry.get_previous_filter("unknown") is None


class TestHistoryServiceBasic:
    """Tests for basic HistoryService operations."""

    def test_create_service(self):
        """Test creating history service."""
        history = HistoryService(max_depth=50)
        assert history.max_depth == 50
        assert not history.can_undo
        assert not history.can_redo

    def test_push_single_entry(self):
        """Test pushing single entry."""
        history = HistoryService()
        entry = HistoryEntry.create(
            expression="test",
            layer_ids=["layer_123"],
            previous_filters=[]
        )
        
        history.push(entry)
        
        assert history.can_undo
        assert history.undo_count == 1

    def test_push_clears_redo(self):
        """Test that pushing clears redo stack."""
        history = HistoryService()
        
        # Push and undo
        entry1 = HistoryEntry.create("test1", ["l1"], [])
        history.push(entry1)
        history.undo()
        assert history.can_redo
        
        # Push new entry
        entry2 = HistoryEntry.create("test2", ["l1"], [])
        history.push(entry2)
        
        # Redo should be cleared
        assert not history.can_redo


class TestHistoryServiceUndoRedo:
    """Tests for undo/redo functionality."""

    def test_undo_returns_entry(self):
        """Test undo returns the undone entry."""
        history = HistoryService()
        entry = HistoryEntry.create("test", ["l1"], [])
        history.push(entry)
        
        undone = history.undo()
        
        assert undone is entry
        assert not history.can_undo
        assert history.can_redo

    def test_undo_empty_returns_none(self):
        """Test undo on empty stack returns None."""
        history = HistoryService()
        result = history.undo()
        assert result is None

    def test_redo_returns_entry(self):
        """Test redo returns the redone entry."""
        history = HistoryService()
        entry = HistoryEntry.create("test", ["l1"], [])
        history.push(entry)
        history.undo()
        
        redone = history.redo()
        
        assert redone is entry
        assert history.can_undo
        assert not history.can_redo

    def test_redo_empty_returns_none(self):
        """Test redo on empty stack returns None."""
        history = HistoryService()
        result = history.redo()
        assert result is None

    def test_multiple_undo_redo(self):
        """Test multiple undo/redo operations."""
        history = HistoryService()
        
        entries = [
            HistoryEntry.create(f"test{i}", ["l1"], [])
            for i in range(3)
        ]
        for entry in entries:
            history.push(entry)
        
        assert history.undo_count == 3
        
        # Undo all
        assert history.undo() == entries[2]
        assert history.undo() == entries[1]
        assert history.undo() == entries[0]
        assert not history.can_undo
        assert history.redo_count == 3
        
        # Redo all
        assert history.redo() == entries[0]
        assert history.redo() == entries[1]
        assert history.redo() == entries[2]
        assert not history.can_redo


class TestHistoryServicePeek:
    """Tests for peek operations."""

    def test_peek_undo(self):
        """Test peeking at undo entry."""
        history = HistoryService()
        entry = HistoryEntry.create("test", ["l1"], [])
        history.push(entry)
        
        peeked = history.peek_undo()
        
        assert peeked is entry
        assert history.can_undo  # Stack unchanged

    def test_peek_undo_empty(self):
        """Test peeking at empty undo stack."""
        history = HistoryService()
        assert history.peek_undo() is None

    def test_peek_redo(self):
        """Test peeking at redo entry."""
        history = HistoryService()
        entry = HistoryEntry.create("test", ["l1"], [])
        history.push(entry)
        history.undo()
        
        peeked = history.peek_redo()
        
        assert peeked is entry
        assert history.can_redo  # Stack unchanged


class TestHistoryServiceState:
    """Tests for HistoryState."""

    def test_get_state_empty(self):
        """Test state for empty history."""
        history = HistoryService()
        state = history.get_state()
        
        assert not state.can_undo
        assert not state.can_redo
        assert state.undo_count == 0
        assert state.redo_count == 0

    def test_get_state_with_entries(self):
        """Test state with entries."""
        history = HistoryService()
        entry = HistoryEntry.create("test", ["l1"], [], description="Test operation")
        history.push(entry)
        
        state = history.get_state()
        
        assert state.can_undo
        assert state.undo_description == "Test operation"
        assert state.undo_count == 1


class TestHistoryServiceMaxDepth:
    """Tests for max depth behavior."""

    def test_respects_max_depth(self):
        """Test that history respects max depth."""
        history = HistoryService(max_depth=3)
        
        for i in range(5):
            entry = HistoryEntry.create(f"test{i}", ["l1"], [])
            history.push(entry)
        
        # Only 3 entries should remain
        assert history.undo_count == 3

    def test_set_max_depth(self):
        """Test changing max depth."""
        history = HistoryService(max_depth=10)
        history.set_max_depth(5)
        assert history.max_depth == 5

    def test_set_max_depth_invalid(self):
        """Test setting invalid max depth."""
        history = HistoryService()
        with pytest.raises(ValueError, match="at least 1"):
            history.set_max_depth(0)


class TestHistoryServiceClear:
    """Tests for clear operations."""

    def test_clear_all(self):
        """Test clearing all history."""
        history = HistoryService()
        for i in range(3):
            history.push(HistoryEntry.create(f"test{i}", ["l1"], []))
        history.undo()
        
        count = history.clear()
        
        assert count == 3
        assert not history.can_undo
        assert not history.can_redo

    def test_clear_redo(self):
        """Test clearing only redo stack."""
        history = HistoryService()
        history.push(HistoryEntry.create("test1", ["l1"], []))
        history.push(HistoryEntry.create("test2", ["l1"], []))
        history.undo()
        
        count = history.clear_redo()
        
        assert count == 1
        assert history.can_undo  # Undo stack unchanged
        assert not history.can_redo


class TestHistoryServiceCallback:
    """Tests for change callback."""

    def test_callback_on_push(self):
        """Test callback called on push."""
        states = []
        history = HistoryService(on_change=lambda s: states.append(s))
        
        history.push(HistoryEntry.create("test", ["l1"], []))
        
        assert len(states) == 1
        assert states[0].can_undo

    def test_callback_on_undo(self):
        """Test callback called on undo."""
        states = []
        history = HistoryService(on_change=lambda s: states.append(s))
        history.push(HistoryEntry.create("test", ["l1"], []))
        states.clear()
        
        history.undo()
        
        assert len(states) == 1
        assert states[0].can_redo

    def test_set_callback(self):
        """Test setting callback after creation."""
        states = []
        history = HistoryService()
        history.set_on_change(lambda s: states.append(s))
        
        history.push(HistoryEntry.create("test", ["l1"], []))
        
        assert len(states) == 1


class TestHistoryServiceSerialization:
    """Tests for serialization."""

    def test_serialize_empty(self):
        """Test serializing empty history."""
        history = HistoryService()
        data = history.serialize()
        
        assert data['undo_stack'] == []
        assert data['redo_stack'] == []
        assert data['max_depth'] == 50

    def test_serialize_with_entries(self):
        """Test serializing history with entries."""
        history = HistoryService()
        history.push(HistoryEntry.create("test", ["l1"], []))
        
        data = history.serialize()
        
        assert len(data['undo_stack']) == 1
        assert data['undo_stack'][0]['expression'] == "test"

    def test_deserialize(self):
        """Test deserializing history."""
        history1 = HistoryService()
        history1.push(HistoryEntry.create("test", ["l1"], []))
        history1.undo()
        
        data = history1.serialize()
        
        history2 = HistoryService()
        history2.deserialize(data)
        
        assert history2.can_redo
        assert history2.peek_redo().expression == "test"

    def test_roundtrip(self):
        """Test serialize/deserialize roundtrip."""
        history1 = HistoryService(max_depth=25)
        for i in range(3):
            history1.push(HistoryEntry.create(f"expr{i}", [f"l{i}"], []))
        history1.undo()
        
        data = history1.serialize()
        
        history2 = HistoryService()
        history2.deserialize(data)
        
        assert history2.undo_count == 2
        assert history2.redo_count == 1
        assert history2.max_depth == 25


class TestHistoryServiceLayerFiltering:
    """Tests for layer-specific history queries."""

    def test_get_history_for_layer(self):
        """Test getting history for specific layer."""
        history = HistoryService()
        history.push(HistoryEntry.create("test1", ["layer_1"], []))
        history.push(HistoryEntry.create("test2", ["layer_2"], []))
        history.push(HistoryEntry.create("test3", ["layer_1", "layer_2"], []))
        
        layer1_history = history.get_history_for_layer("layer_1")
        
        assert len(layer1_history) == 2
        assert all("layer_1" in e.layer_ids for e in layer1_history)

    def test_get_history_for_unknown_layer(self):
        """Test getting history for unknown layer."""
        history = HistoryService()
        history.push(HistoryEntry.create("test", ["layer_1"], []))
        
        result = history.get_history_for_layer("unknown")
        
        assert result == []
