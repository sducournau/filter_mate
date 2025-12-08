"""
Unit tests for UI History Widgets

Tests all history widget components:
- HistoryDropdown
- HistoryNavigationWidget
- HistoryListWidget
- CompactHistoryWidget

Author: FilterMate Development Team
Date: December 2025
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Test imports will work when run in QGIS environment
# Mock QGIS imports for standalone test runs
try:
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtWidgets import QApplication
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    pytest.skip("QGIS not available - these tests require QGIS environment", allow_module_level=True)

from modules.ui_history_widgets import (
    HistoryDropdown,
    HistoryNavigationWidget,
    HistoryListWidget,
    CompactHistoryWidget
)
from modules.filter_history import FilterState, FilterHistory


@pytest.fixture
def qapp():
    """Provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_history_manager():
    """Create mock history manager."""
    manager = Mock()
    manager.get_history = Mock()
    return manager


@pytest.fixture
def sample_history():
    """Create sample FilterHistory with states."""
    history = FilterHistory(layer_id="test_layer", max_size=50)
    
    # Add some states
    for i in range(5):
        state = FilterState(
            expression=f"field = {i}",
            description=f"Filter state {i}",
            feature_count=100 * (i + 1),
            geometry_type="Point",
            timestamp=datetime(2025, 12, 8, 10, i, 0)
        )
        history.add_state(state)
    
    return history


class TestHistoryDropdown:
    """Test suite for HistoryDropdown widget."""
    
    def test_initialization(self, qapp):
        """Test dropdown initializes correctly."""
        dropdown = HistoryDropdown(max_items=10)
        
        assert dropdown.max_items == 10
        assert dropdown.count() == 1  # "No history available"
        assert not dropdown.isEnabled()
        assert dropdown.minimumWidth() >= 200
    
    def test_set_history_manager(self, qapp, mock_history_manager):
        """Test setting history manager."""
        dropdown = HistoryDropdown()
        dropdown.set_history_manager(mock_history_manager)
        
        assert dropdown._history_manager == mock_history_manager
    
    def test_update_with_no_history(self, qapp, mock_history_manager):
        """Test update when no history available."""
        mock_history_manager.get_history.return_value = None
        
        dropdown = HistoryDropdown()
        dropdown.set_history_manager(mock_history_manager)
        dropdown.set_current_layer("test_layer")
        
        assert dropdown.count() == 1
        assert dropdown.itemText(0) == "No history available"
        assert not dropdown.isEnabled()
    
    def test_update_with_history(self, qapp, mock_history_manager, sample_history):
        """Test update with actual history."""
        mock_history_manager.get_history.return_value = sample_history
        
        dropdown = HistoryDropdown()
        dropdown.set_history_manager(mock_history_manager)
        dropdown.set_current_layer("test_layer")
        
        # Should have 5 states
        assert dropdown.count() == 5
        assert dropdown.isEnabled()
        
        # Check first item (most recent)
        first_text = dropdown.itemText(0)
        assert "10:04:00" in first_text
        assert "Filter state 4" in first_text
        assert "(500 features)" in first_text
    
    def test_max_items_limit(self, qapp, mock_history_manager):
        """Test that dropdown respects max_items limit."""
        # Create history with 20 states
        history = FilterHistory(layer_id="test", max_size=50)
        for i in range(20):
            state = FilterState(
                expression=f"field = {i}",
                description=f"State {i}",
                feature_count=100,
                geometry_type="Point"
            )
            history.add_state(state)
        
        mock_history_manager.get_history.return_value = history
        
        dropdown = HistoryDropdown(max_items=10)
        dropdown.set_history_manager(mock_history_manager)
        dropdown.set_current_layer("test")
        
        # Should only show last 10 items
        assert dropdown.count() == 10
    
    def test_state_selection_signal(self, qapp, mock_history_manager, sample_history):
        """Test that selecting a state emits signal."""
        mock_history_manager.get_history.return_value = sample_history
        
        dropdown = HistoryDropdown()
        dropdown.set_history_manager(mock_history_manager)
        dropdown.set_current_layer("test_layer")
        
        # Connect signal spy
        signal_received = []
        dropdown.stateSelected.connect(lambda idx: signal_received.append(idx))
        
        # Select item (index 2 in dropdown = state index 2 in history)
        dropdown.setCurrentIndex(2)
        
        # Signal should be emitted
        assert len(signal_received) == 1
        assert signal_received[0] == 2  # Actual history index
    
    def test_current_state_highlighting(self, qapp, mock_history_manager, sample_history):
        """Test that current state is highlighted."""
        # Set current index to middle state
        sample_history._current_index = 2
        mock_history_manager.get_history.return_value = sample_history
        
        dropdown = HistoryDropdown()
        dropdown.set_history_manager(mock_history_manager)
        dropdown.set_current_layer("test_layer")
        
        # The current state should have bold font
        # Current index 2 = dropdown position (len-1-2) = position 2
        dropdown_position = len(sample_history._states) - 1 - sample_history._current_index
        item_font = dropdown.itemData(dropdown_position, Qt.FontRole)
        assert item_font is not None
        assert item_font.bold()


class TestHistoryNavigationWidget:
    """Test suite for HistoryNavigationWidget."""
    
    def test_initialization(self, qapp):
        """Test widget initializes correctly."""
        widget = HistoryNavigationWidget()
        
        assert widget.undo_button is not None
        assert widget.redo_button is not None
        assert widget.state_label is not None
        
        # Should be disabled initially
        assert not widget.undo_button.isEnabled()
        assert not widget.redo_button.isEnabled()
        assert widget.state_label.text() == "No history"
    
    def test_set_history_manager(self, qapp, mock_history_manager):
        """Test setting history manager."""
        widget = HistoryNavigationWidget()
        widget.set_history_manager(mock_history_manager)
        
        assert widget._history_manager == mock_history_manager
    
    def test_update_with_no_history(self, qapp, mock_history_manager):
        """Test update when no history available."""
        mock_history_manager.get_history.return_value = None
        
        widget = HistoryNavigationWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        assert not widget.undo_button.isEnabled()
        assert not widget.redo_button.isEnabled()
        assert widget.state_label.text() == "No history"
    
    def test_update_with_history(self, qapp, mock_history_manager, sample_history):
        """Test update with actual history."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = HistoryNavigationWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # At newest state: can undo, cannot redo
        assert widget.undo_button.isEnabled()
        assert not widget.redo_button.isEnabled()
        assert widget.state_label.text() == "5/5"
    
    def test_update_after_undo(self, qapp, mock_history_manager, sample_history):
        """Test button states after undo."""
        # Undo once
        sample_history.undo()
        mock_history_manager.get_history.return_value = sample_history
        
        widget = HistoryNavigationWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Can both undo and redo
        assert widget.undo_button.isEnabled()
        assert widget.redo_button.isEnabled()
        assert widget.state_label.text() == "4/5"
    
    def test_undo_signal(self, qapp):
        """Test that undo button emits signal."""
        widget = HistoryNavigationWidget()
        
        # Enable button
        widget.undo_button.setEnabled(True)
        
        # Connect signal spy
        signal_received = []
        widget.undoRequested.connect(lambda: signal_received.append("undo"))
        
        # Click button
        widget.undo_button.click()
        
        assert signal_received == ["undo"]
    
    def test_redo_signal(self, qapp):
        """Test that redo button emits signal."""
        widget = HistoryNavigationWidget()
        
        # Enable button
        widget.redo_button.setEnabled(True)
        
        # Connect signal spy
        signal_received = []
        widget.redoRequested.connect(lambda: signal_received.append("redo"))
        
        # Click button
        widget.redo_button.click()
        
        assert signal_received == ["redo"]
    
    def test_button_tooltips(self, qapp):
        """Test that buttons have appropriate tooltips."""
        widget = HistoryNavigationWidget()
        
        assert "Undo" in widget.undo_button.toolTip()
        assert "Ctrl+Z" in widget.undo_button.toolTip()
        
        assert "Redo" in widget.redo_button.toolTip()
        assert "Ctrl+Y" in widget.redo_button.toolTip()


class TestHistoryListWidget:
    """Test suite for HistoryListWidget."""
    
    def test_initialization(self, qapp):
        """Test widget initializes correctly."""
        widget = HistoryListWidget()
        
        assert widget.list_widget is not None
        assert widget.info_label is not None
        assert widget.info_label.text() == "No history available"
        assert widget.info_label.isVisible()
    
    def test_set_history_manager(self, qapp, mock_history_manager):
        """Test setting history manager."""
        widget = HistoryListWidget()
        widget.set_history_manager(mock_history_manager)
        
        assert widget._history_manager == mock_history_manager
    
    def test_update_with_no_history(self, qapp, mock_history_manager):
        """Test update when no history available."""
        mock_history_manager.get_history.return_value = None
        
        widget = HistoryListWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        assert widget.list_widget.count() == 0
        assert widget.info_label.isVisible()
        assert not widget.list_widget.isVisible()
    
    def test_update_with_history(self, qapp, mock_history_manager, sample_history):
        """Test update with actual history."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = HistoryListWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Should show all 5 states
        assert widget.list_widget.count() == 5
        assert not widget.info_label.isVisible()
        assert widget.list_widget.isVisible()
        
        # Check first item (most recent)
        first_item = widget.list_widget.item(0)
        assert "Filter state 4" in first_item.text()
        assert "500 features" in first_item.text()
    
    def test_current_state_highlighting(self, qapp, mock_history_manager, sample_history):
        """Test that current state is highlighted in list."""
        sample_history._current_index = 2
        mock_history_manager.get_history.return_value = sample_history
        
        widget = HistoryListWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Current index 2 = list position (len-1-2) = position 2
        list_position = len(sample_history._states) - 1 - sample_history._current_index
        current_item = widget.list_widget.item(list_position)
        
        assert current_item.font().bold()
        assert "Current state" in current_item.toolTip()
    
    def test_state_selection_signal(self, qapp, mock_history_manager, sample_history):
        """Test that double-clicking emits signal."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = HistoryListWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Connect signal spy
        signal_received = []
        widget.stateSelected.connect(lambda idx: signal_received.append(idx))
        
        # Double-click item
        item = widget.list_widget.item(1)
        widget._on_item_double_clicked(item)
        
        # Signal should be emitted with correct index
        assert len(signal_received) == 1
        assert signal_received[0] == 3  # Index in history


class TestCompactHistoryWidget:
    """Test suite for CompactHistoryWidget."""
    
    def test_initialization(self, qapp):
        """Test widget initializes correctly."""
        widget = CompactHistoryWidget()
        
        assert widget.undo_button is not None
        assert widget.redo_button is not None
        assert widget.dropdown is not None
        
        # Buttons disabled initially
        assert not widget.undo_button.isEnabled()
        assert not widget.redo_button.isEnabled()
    
    def test_set_history_manager(self, qapp, mock_history_manager):
        """Test setting history manager propagates."""
        widget = CompactHistoryWidget()
        widget.set_history_manager(mock_history_manager)
        
        assert widget._history_manager == mock_history_manager
        assert widget.dropdown._history_manager == mock_history_manager
    
    def test_set_current_layer(self, qapp, mock_history_manager, sample_history):
        """Test setting layer updates all components."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = CompactHistoryWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Dropdown should be updated
        assert widget.dropdown.count() == 5
        
        # Buttons should be updated
        assert widget.undo_button.isEnabled()
        assert not widget.redo_button.isEnabled()
    
    def test_undo_signal_propagation(self, qapp):
        """Test undo signal is propagated."""
        widget = CompactHistoryWidget()
        widget.undo_button.setEnabled(True)
        
        # Connect signal spy
        signal_received = []
        widget.undoRequested.connect(lambda: signal_received.append("undo"))
        
        # Click button
        widget.undo_button.click()
        
        assert signal_received == ["undo"]
    
    def test_redo_signal_propagation(self, qapp):
        """Test redo signal is propagated."""
        widget = CompactHistoryWidget()
        widget.redo_button.setEnabled(True)
        
        # Connect signal spy
        signal_received = []
        widget.redoRequested.connect(lambda: signal_received.append("redo"))
        
        # Click button
        widget.redo_button.click()
        
        assert signal_received == ["redo"]
    
    def test_state_selection_propagation(self, qapp, mock_history_manager, sample_history):
        """Test state selection from dropdown is propagated."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = CompactHistoryWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Connect signal spy
        signal_received = []
        widget.stateSelected.connect(lambda idx: signal_received.append(idx))
        
        # Simulate dropdown selection
        widget.dropdown.setCurrentIndex(2)
        
        # Signal should be propagated
        assert len(signal_received) == 1
        assert signal_received[0] == 2
    
    def test_update_history_updates_all(self, qapp, mock_history_manager, sample_history):
        """Test update_history updates all components."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = CompactHistoryWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Modify history
        sample_history.undo()
        
        # Update
        widget.update_history()
        
        # Both buttons should be enabled now
        assert widget.undo_button.isEnabled()
        assert widget.redo_button.isEnabled()


class TestIntegrationScenarios:
    """Integration tests for realistic usage scenarios."""
    
    def test_full_navigation_workflow(self, qapp, mock_history_manager, sample_history):
        """Test complete navigation workflow."""
        mock_history_manager.get_history.return_value = sample_history
        
        widget = CompactHistoryWidget()
        widget.set_history_manager(mock_history_manager)
        widget.set_current_layer("test_layer")
        
        # Initial state: at newest (5/5)
        assert widget.undo_button.isEnabled()
        assert not widget.redo_button.isEnabled()
        
        # Undo twice
        sample_history.undo()
        sample_history.undo()
        widget.update_history()
        
        # Middle state: can undo and redo
        assert widget.undo_button.isEnabled()
        assert widget.redo_button.isEnabled()
        
        # Redo once
        sample_history.redo()
        widget.update_history()
        
        # Still can undo and redo
        assert widget.undo_button.isEnabled()
        assert widget.redo_button.isEnabled()
    
    def test_layer_switching(self, qapp, mock_history_manager):
        """Test switching between layers."""
        # Create histories for two layers
        history1 = FilterHistory(layer_id="layer1", max_size=50)
        history2 = FilterHistory(layer_id="layer2", max_size=50)
        
        for i in range(3):
            history1.add_state(FilterState(
                expression=f"field1 = {i}",
                description=f"Layer1 state {i}",
                feature_count=100,
                geometry_type="Point"
            ))
        
        for i in range(5):
            history2.add_state(FilterState(
                expression=f"field2 = {i}",
                description=f"Layer2 state {i}",
                feature_count=200,
                geometry_type="Polygon"
            ))
        
        def get_history(layer_id):
            if layer_id == "layer1":
                return history1
            elif layer_id == "layer2":
                return history2
            return None
        
        mock_history_manager.get_history.side_effect = get_history
        
        widget = CompactHistoryWidget()
        widget.set_history_manager(mock_history_manager)
        
        # Set to layer1
        widget.set_current_layer("layer1")
        assert widget.dropdown.count() == 3
        
        # Switch to layer2
        widget.set_current_layer("layer2")
        assert widget.dropdown.count() == 5
        
        # Switch back to layer1
        widget.set_current_layer("layer1")
        assert widget.dropdown.count() == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
