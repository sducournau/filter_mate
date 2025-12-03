"""
Tests for FilterMate Signal Utilities

Unit tests for modules/signal_utils.py to ensure signal blocking
and connection management work correctly.
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.signal_utils import (
    SignalBlocker,
    SignalConnection,
    SignalBlockerGroup,
    block_signals,
    connect_signal,
)


class TestSignalBlocker:
    """Test SignalBlocker context manager"""
    
    def test_signal_blocker_single_widget(self):
        """Test blocking signals for single widget"""
        widget = Mock()
        widget.signalsBlocked.return_value = False
        
        with SignalBlocker(widget):
            widget.blockSignals.assert_called_once_with(True)
        
        # Should restore previous state
        assert widget.blockSignals.call_count == 2
        widget.blockSignals.assert_called_with(False)
    
    def test_signal_blocker_multiple_widgets(self):
        """Test blocking signals for multiple widgets"""
        widget1 = Mock()
        widget1.signalsBlocked.return_value = False
        widget2 = Mock()
        widget2.signalsBlocked.return_value = False
        widget3 = Mock()
        widget3.signalsBlocked.return_value = False
        
        with SignalBlocker(widget1, widget2, widget3):
            assert widget1.blockSignals.call_count == 1
            assert widget2.blockSignals.call_count == 1
            assert widget3.blockSignals.call_count == 1
        
        # All should be restored
        assert widget1.blockSignals.call_count == 2
        assert widget2.blockSignals.call_count == 2
        assert widget3.blockSignals.call_count == 2
    
    def test_signal_blocker_preserves_previous_state(self):
        """Test that previous signal state is preserved"""
        widget = Mock()
        widget.signalsBlocked.return_value = True  # Already blocked
        
        with SignalBlocker(widget):
            pass
        
        # Should restore to True (previous state)
        widget.blockSignals.assert_called_with(True)
    
    def test_signal_blocker_exception_safety(self):
        """Test that signals are restored even if exception occurs"""
        widget = Mock()
        widget.signalsBlocked.return_value = False
        
        try:
            with SignalBlocker(widget):
                widget.blockSignals.assert_called_once_with(True)
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Signals should still be restored
        assert widget.blockSignals.call_count == 2
        widget.blockSignals.assert_called_with(False)
    
    def test_signal_blocker_handles_none_widget(self):
        """Test that None widgets are handled gracefully"""
        widget = Mock()
        widget.signalsBlocked.return_value = False
        
        # Should not raise exception
        with SignalBlocker(None, widget, None):
            pass
        
        # Valid widget should still be processed
        assert widget.blockSignals.call_count == 2
    
    def test_signal_blocker_handles_deleted_widget(self):
        """Test handling of deleted/invalid widgets"""
        widget = Mock()
        widget.signalsBlocked.side_effect = RuntimeError("Widget deleted")
        
        # Should not raise exception
        with SignalBlocker(widget):
            pass
    
    def test_signal_blocker_nested_contexts(self):
        """Test nested SignalBlocker contexts"""
        widget1 = Mock()
        widget1.signalsBlocked.return_value = False
        widget2 = Mock()
        widget2.signalsBlocked.return_value = False
        
        with SignalBlocker(widget1):
            assert widget1.blockSignals.call_count == 1
            
            with SignalBlocker(widget2):
                assert widget2.blockSignals.call_count == 1
                # Both should be blocked
            
            # widget2 restored, widget1 still blocked
            assert widget2.blockSignals.call_count == 2
        
        # Both restored
        assert widget1.blockSignals.call_count == 2
    
    def test_signal_blocker_is_active(self):
        """Test is_active() method"""
        widget = Mock()
        widget.signalsBlocked.return_value = False
        
        blocker = SignalBlocker(widget)
        assert blocker.is_active() is False
        
        with blocker:
            assert blocker.is_active() is True
        
        assert blocker.is_active() is False


class TestSignalConnection:
    """Test SignalConnection context manager"""
    
    def test_signal_connection_basic(self):
        """Test basic signal connection and disconnection"""
        signal = Mock()
        slot = Mock()
        
        with SignalConnection(signal, slot):
            signal.connect.assert_called_once_with(slot)
        
        signal.disconnect.assert_called_once_with(slot)
    
    def test_signal_connection_exception_safety(self):
        """Test that signal is disconnected even if exception occurs"""
        signal = Mock()
        slot = Mock()
        
        try:
            with SignalConnection(signal, slot):
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        signal.disconnect.assert_called_once_with(slot)
    
    def test_signal_connection_handles_connection_error(self):
        """Test handling of connection errors"""
        signal = Mock()
        signal.connect.side_effect = RuntimeError("Connection failed")
        slot = Mock()
        
        # Should not raise exception
        with SignalConnection(signal, slot):
            pass
        
        # Should not try to disconnect if connection failed
        signal.disconnect.assert_not_called()
    
    def test_signal_connection_handles_disconnection_error(self):
        """Test handling of disconnection errors"""
        signal = Mock()
        signal.disconnect.side_effect = RuntimeError("Disconnection failed")
        slot = Mock()
        
        # Should not raise exception
        with SignalConnection(signal, slot):
            pass


class TestSignalBlockerGroup:
    """Test SignalBlockerGroup for managing multiple widget groups"""
    
    def test_add_group(self):
        """Test adding widget groups"""
        group = SignalBlockerGroup()
        widget1 = Mock()
        widget2 = Mock()
        
        group.add_group('test_group', widget1, widget2)
        
        assert 'test_group' in group.list_groups()
        assert len(group.get_group('test_group')) == 2
    
    def test_remove_group(self):
        """Test removing widget groups"""
        group = SignalBlockerGroup()
        widget = Mock()
        
        group.add_group('test_group', widget)
        assert 'test_group' in group.list_groups()
        
        group.remove_group('test_group')
        assert 'test_group' not in group.list_groups()
    
    def test_block_single_group(self):
        """Test blocking a single group"""
        group = SignalBlockerGroup()
        widget1 = Mock()
        widget1.signalsBlocked.return_value = False
        widget2 = Mock()
        widget2.signalsBlocked.return_value = False
        
        group.add_group('group1', widget1)
        group.add_group('group2', widget2)
        
        with group.block('group1'):
            assert widget1.blockSignals.call_count == 1
            assert widget2.blockSignals.call_count == 0
        
        assert widget1.blockSignals.call_count == 2
    
    def test_block_multiple_groups(self):
        """Test blocking multiple groups"""
        group = SignalBlockerGroup()
        widget1 = Mock()
        widget1.signalsBlocked.return_value = False
        widget2 = Mock()
        widget2.signalsBlocked.return_value = False
        widget3 = Mock()
        widget3.signalsBlocked.return_value = False
        
        group.add_group('group1', widget1, widget2)
        group.add_group('group2', widget3)
        
        with group.block('group1', 'group2'):
            assert widget1.blockSignals.call_count == 1
            assert widget2.blockSignals.call_count == 1
            assert widget3.blockSignals.call_count == 1
    
    def test_block_all(self):
        """Test blocking all groups"""
        group = SignalBlockerGroup()
        widget1 = Mock()
        widget1.signalsBlocked.return_value = False
        widget2 = Mock()
        widget2.signalsBlocked.return_value = False
        widget3 = Mock()
        widget3.signalsBlocked.return_value = False
        
        group.add_group('group1', widget1)
        group.add_group('group2', widget2, widget3)
        
        with group.block_all():
            assert widget1.blockSignals.call_count == 1
            assert widget2.blockSignals.call_count == 1
            assert widget3.blockSignals.call_count == 1
    
    def test_block_nonexistent_group(self):
        """Test blocking nonexistent group (should handle gracefully)"""
        group = SignalBlockerGroup()
        
        # Should not raise exception
        with group.block('nonexistent_group'):
            pass
    
    def test_get_group(self):
        """Test retrieving widgets from a group"""
        group = SignalBlockerGroup()
        widget1 = Mock()
        widget2 = Mock()
        
        group.add_group('test_group', widget1, widget2)
        
        widgets = group.get_group('test_group')
        assert len(widgets) == 2
        assert widget1 in widgets
        assert widget2 in widgets
    
    def test_get_nonexistent_group(self):
        """Test retrieving nonexistent group"""
        group = SignalBlockerGroup()
        
        result = group.get_group('nonexistent')
        assert result is None
    
    def test_list_groups(self):
        """Test listing all groups"""
        group = SignalBlockerGroup()
        widget = Mock()
        
        group.add_group('group1', widget)
        group.add_group('group2', widget)
        group.add_group('group3', widget)
        
        groups = group.list_groups()
        assert len(groups) == 3
        assert 'group1' in groups
        assert 'group2' in groups
        assert 'group3' in groups


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_block_signals_function(self):
        """Test block_signals convenience function"""
        widget = Mock()
        widget.signalsBlocked.return_value = False
        
        with block_signals(widget):
            widget.blockSignals.assert_called_once_with(True)
        
        assert widget.blockSignals.call_count == 2
    
    def test_connect_signal_function(self):
        """Test connect_signal convenience function"""
        signal = Mock()
        slot = Mock()
        
        with connect_signal(signal, slot):
            signal.connect.assert_called_once_with(slot)
        
        signal.disconnect.assert_called_once_with(slot)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
