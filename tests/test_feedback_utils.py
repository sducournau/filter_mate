"""
Unit Tests for FilterMate Feedback Utilities

Tests for the new feedback_utils.py module that provides backend-aware
user feedback messages.
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.feedback_utils import (
    get_backend_display_name,
    show_backend_info,
    show_progress_message,
    show_success_with_backend,
    show_performance_warning,
    show_error_with_context,
    format_backend_summary
)


class TestBackendDisplayNames:
    """Tests for backend display name formatting"""
    
    def test_get_backend_display_name_postgresql(self):
        """Test PostgreSQL display name includes elephant emoji"""
        result = get_backend_display_name('postgresql')
        assert '🐘' in result
        assert 'PostgreSQL' in result
    
    def test_get_backend_display_name_spatialite(self):
        """Test Spatialite display name includes disk emoji"""
        result = get_backend_display_name('spatialite')
        assert '💾' in result
        assert 'Spatialite' in result
    
    def test_get_backend_display_name_ogr(self):
        """Test OGR display name includes folder emoji"""
        result = get_backend_display_name('ogr')
        assert '📁' in result
        assert 'OGR' in result
    
    def test_get_backend_display_name_memory(self):
        """Test Memory display name includes lightning emoji"""
        result = get_backend_display_name('memory')
        assert '⚡' in result
        assert 'Memory' in result
    
    def test_get_backend_display_name_unknown(self):
        """Test unknown backend gets question mark emoji"""
        result = get_backend_display_name('unknown_backend')
        assert '❓' in result


class TestBackendInfo:
    """Tests for show_backend_info function"""
    
    def test_show_backend_info_filter_operation(self, mock_iface):
        """Test backend info message for filter operation"""
        show_backend_info(mock_iface, 'postgresql', layer_count=5, operation='filter')
        
        mock_iface.messageBar().pushInfo.assert_called_once()
        args = mock_iface.messageBar().pushInfo.call_args[0]
        
        assert args[0] == "FilterMate"
        assert '🐘 PostgreSQL' in args[1]
        assert '5 layer(s)' in args[1]
        assert 'filter' in args[1].lower()
    
    def test_show_backend_info_export_operation(self, mock_iface):
        """Test backend info message for export operation"""
        show_backend_info(mock_iface, 'spatialite', layer_count=3, operation='export')
        
        args = mock_iface.messageBar().pushInfo.call_args[0]
        assert '💾 Spatialite' in args[1]
        assert '3 layer(s)' in args[1]
        assert 'export' in args[1].lower()
    
    def test_show_backend_info_custom_duration(self, mock_iface):
        """Test backend info with custom message duration"""
        show_backend_info(mock_iface, 'ogr', layer_count=1, duration=5)
        
        args = mock_iface.messageBar().pushInfo.call_args[0]
        # Duration is the 3rd positional argument
        assert args[2] == 5


class TestProgressMessages:
    """Tests for show_progress_message function"""
    
    def test_show_progress_message_with_counts(self, mock_iface):
        """Test progress message with current/total counts"""
        show_progress_message(mock_iface, 'Filtering layers', current=3, total=10)
        
        args = mock_iface.messageBar().pushInfo.call_args[0]
        assert 'Filtering layers' in args[1]
        assert '3/10' in args[1]
    
    def test_show_progress_message_without_counts(self, mock_iface):
        """Test progress message without specific counts"""
        show_progress_message(mock_iface, 'Processing data')
        
        args = mock_iface.messageBar().pushInfo.call_args[0]
        assert 'Processing data' in args[1]
        assert '/' not in args[1]  # No progress fraction


class TestSuccessMessages:
    """Tests for show_success_with_backend function"""
    
    def test_show_success_with_backend_filter(self, mock_iface):
        """Test success message for filter operation with backend"""
        show_success_with_backend(mock_iface, 'postgresql', 'filter', layer_count=5)
        
        mock_iface.messageBar().pushSuccess.assert_called_once()
        args = mock_iface.messageBar().pushSuccess.call_args[0]
        
        assert '🐘 PostgreSQL' in args[1]
        assert 'filtered' in args[1].lower()
        assert '5 layer(s)' in args[1]
    
    def test_show_success_with_backend_export(self, mock_iface):
        """Test success message for export operation"""
        show_success_with_backend(mock_iface, 'spatialite', 'export', layer_count=2)
        
        args = mock_iface.messageBar().pushSuccess.call_args[0]
        assert '💾 Spatialite' in args[1]
        assert 'exported' in args[1].lower()


class TestPerformanceWarnings:
    """Tests for show_performance_warning function"""
    
    def test_show_performance_warning_large_dataset(self, mock_iface):
        """Test performance warning for dataset >100k features"""
        show_performance_warning(mock_iface, 'spatialite', 150000)
        
        mock_iface.messageBar().pushWarning.assert_called_once()
        args = mock_iface.messageBar().pushWarning.call_args[0]
        
        assert 'FilterMate - Performance' in args[0]
        assert '150,000 features' in args[1]
        assert 'PostgreSQL' in args[1]
    
    def test_show_performance_warning_medium_dataset(self, mock_iface):
        """Test info message for dataset 50k-100k features"""
        show_performance_warning(mock_iface, 'ogr', 75000)
        
        # Should show info, not warning
        mock_iface.messageBar().pushInfo.assert_called_once()
        args = mock_iface.messageBar().pushInfo.call_args[0]
        
        assert '75,000 features' in args[1]
    
    def test_show_performance_warning_no_warning_postgresql(self, mock_iface):
        """Test no warning for PostgreSQL backend"""
        show_performance_warning(mock_iface, 'postgresql', 500000)
        
        # Should not call any message bar methods
        mock_iface.messageBar().pushWarning.assert_not_called()
        mock_iface.messageBar().pushInfo.assert_not_called()
    
    def test_show_performance_warning_small_dataset(self, mock_iface):
        """Test no warning for small dataset"""
        show_performance_warning(mock_iface, 'spatialite', 10000)
        
        mock_iface.messageBar().pushWarning.assert_not_called()
        mock_iface.messageBar().pushInfo.assert_not_called()


class TestErrorMessages:
    """Tests for show_error_with_context function"""
    
    def test_show_error_with_context_full(self, mock_iface):
        """Test error message with full context (backend + operation)"""
        show_error_with_context(
            mock_iface,
            "Connection timeout",
            provider_type='postgresql',
            operation='filter'
        )
        
        mock_iface.messageBar().pushCritical.assert_called_once()
        args = mock_iface.messageBar().pushCritical.call_args[0]
        
        assert '🐘 PostgreSQL' in args[1]
        assert 'Filter' in args[1]
        assert 'Connection timeout' in args[1]
    
    def test_show_error_with_context_backend_only(self, mock_iface):
        """Test error message with backend context only"""
        show_error_with_context(
            mock_iface,
            "Invalid geometry",
            provider_type='spatialite'
        )
        
        args = mock_iface.messageBar().pushCritical.call_args[0]
        assert '💾 Spatialite' in args[1]
        assert 'Invalid geometry' in args[1]
    
    def test_show_error_with_context_no_context(self, mock_iface):
        """Test error message without context"""
        show_error_with_context(mock_iface, "Unknown error")
        
        args = mock_iface.messageBar().pushCritical.call_args[0]
        assert args[1] == "Unknown error"


class TestBackendSummary:
    """Tests for format_backend_summary function"""
    
    def test_format_backend_summary_multiple_backends(self):
        """Test summary formatting for multiple backends"""
        counts = {
            'postgresql': 3,
            'spatialite': 2,
            'ogr': 1
        }
        
        result = format_backend_summary(counts)
        
        assert '🐘 PostgreSQL: 3' in result
        assert '💾 Spatialite: 2' in result
        assert '📁 OGR: 1' in result
        assert result.count(',') == 2  # Two commas separating three items
    
    def test_format_backend_summary_single_backend(self):
        """Test summary formatting for single backend"""
        counts = {'postgresql': 5}
        
        result = format_backend_summary(counts)
        
        assert '🐘 PostgreSQL: 5' in result
        assert ',' not in result
    
    def test_format_backend_summary_empty(self):
        """Test summary formatting for empty dict"""
        result = format_backend_summary({})
        assert result == ""


# Fixtures
@pytest.fixture
def mock_iface():
    """Mock QGIS interface with message bar"""
    iface = Mock()
    message_bar = Mock()
    
    # Setup return values for chained calls
    iface.messageBar.return_value = message_bar
    message_bar.pushInfo = Mock()
    message_bar.pushSuccess = Mock()
    message_bar.pushWarning = Mock()
    message_bar.pushCritical = Mock()
    
    return iface


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=modules.feedback_utils', '--cov-report=term-missing'])
