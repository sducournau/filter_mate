# -*- coding: utf-8 -*-
"""
Unit tests for FilterApplicationService.

Tests filter application, unfilter, and reset operations.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys

# Mock QGIS modules before importing
sys.modules['qgis'] = MagicMock()
sys.modules['qgis.core'] = MagicMock()
sys.modules['qgis.gui'] = MagicMock()
sys.modules['qgis.PyQt'] = MagicMock()
sys.modules['qgis.PyQt.QtCore'] = MagicMock()
sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()


class TestFilterApplicationService:
    """Tests for FilterApplicationService class."""
    
    @pytest.fixture
    def mock_layer(self):
        """Create a mock QgsVectorLayer."""
        layer = Mock()
        layer.id.return_value = "layer_123"
        layer.name.return_value = "Test Layer"
        layer.subsetString.return_value = ""
        layer.isValid.return_value = True
        return layer
    
    @pytest.fixture
    def mock_history_manager(self):
        """Create a mock HistoryManager."""
        manager = Mock()
        return manager
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock Spatialite connection."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        return conn
    
    @pytest.fixture
    def project_layers(self):
        """Create sample PROJECT_LAYERS dict."""
        return {
            "layer_123": {
                "infos": {
                    "is_already_subset": False
                }
            }
        }
    
    @pytest.fixture
    def service(self, mock_history_manager, mock_connection, project_layers):
        """Create FilterApplicationService instance."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            from core.services.filter_application_service import FilterApplicationService
            
            return FilterApplicationService(
                history_manager=mock_history_manager,
                get_spatialite_connection=lambda: mock_connection,
                get_project_uuid=lambda: "project-uuid-123",
                get_project_layers=lambda: project_layers,
                show_warning=Mock()
            )
    
    def test_init(self, mock_history_manager, mock_connection, project_layers):
        """Test service initialization."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            from core.services.filter_application_service import FilterApplicationService
            
            svc = FilterApplicationService(
                history_manager=mock_history_manager,
                get_spatialite_connection=lambda: mock_connection,
                get_project_uuid=lambda: "uuid",
                get_project_layers=lambda: project_layers
            )
            
            assert svc._history_manager == mock_history_manager
    
    def test_apply_subset_filter_invalid_layer(self, service, mock_layer):
        """Test apply_subset_filter with invalid layer."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=False):
            result = service.apply_subset_filter('filter', mock_layer)
            
            assert result is False
            service._show_warning.assert_called()
    
    def test_apply_subset_filter_unknown_task(self, service, mock_layer):
        """Test apply_subset_filter with unknown task name."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            result = service.apply_subset_filter('unknown_task', mock_layer)
            
            assert result is False
    
    def test_handle_unfilter_with_history(self, service, mock_layer, mock_history_manager):
        """Test unfilter operation when history is available."""
        # Setup history mock
        history = Mock()
        history.can_undo.return_value = True
        previous_state = Mock()
        previous_state.expression = "id > 5"
        previous_state.description = "Previous filter"
        history.undo.return_value = previous_state
        mock_history_manager.get_history.return_value = history
        
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            with patch('core.services.filter_application_service.safe_set_subset_string') as mock_set:
                result = service.apply_subset_filter('unfilter', mock_layer)
                
                assert result is True
                mock_set.assert_called_with(mock_layer, "id > 5")
    
    def test_handle_unfilter_no_history(self, service, mock_layer, mock_history_manager):
        """Test unfilter operation when no history available."""
        history = Mock()
        history.can_undo.return_value = False
        mock_history_manager.get_history.return_value = history
        
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            with patch('core.services.filter_application_service.safe_set_subset_string') as mock_set:
                result = service.apply_subset_filter('unfilter', mock_layer)
                
                assert result is True
                mock_set.assert_called_with(mock_layer, '')
    
    def test_handle_filter_with_db_history(self, service, mock_layer, mock_connection):
        """Test filter operation using database history."""
        # Setup cursor mock to return filter expression
        cursor = mock_connection.cursor.return_value
        cursor.fetchall.return_value = [
            (1, "project-uuid", "layer_123", "desc", "user", "2024-01-01", "name = 'test'", 1)
        ]
        
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            with patch('core.services.filter_application_service.safe_set_subset_string') as mock_set:
                result = service.apply_subset_filter('filter', mock_layer)
                
                assert result is True
                mock_set.assert_called_with(mock_layer, "name = 'test'")
    
    def test_handle_reset_clears_filter(self, service, mock_layer, mock_connection):
        """Test reset operation clears filter."""
        cursor = mock_connection.cursor.return_value
        cursor.fetchall.return_value = []
        
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            with patch('core.services.filter_application_service.safe_set_subset_string') as mock_set:
                result = service.apply_subset_filter('reset', mock_layer)
                
                assert result is True
                mock_set.assert_called_with(mock_layer, '')
    
    def test_update_subset_flag(self, service, project_layers, mock_layer):
        """Test _update_subset_flag updates PROJECT_LAYERS."""
        service._update_subset_flag(project_layers, "layer_123", True)
        
        assert project_layers["layer_123"]["infos"]["is_already_subset"] is True
        
        service._update_subset_flag(project_layers, "layer_123", False)
        
        assert project_layers["layer_123"]["infos"]["is_already_subset"] is False
    
    def test_default_warning(self, mock_history_manager, mock_connection, project_layers):
        """Test default warning handler uses logger."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            from core.services.filter_application_service import FilterApplicationService
            
            # Create service without custom warning handler
            svc = FilterApplicationService(
                history_manager=mock_history_manager,
                get_spatialite_connection=lambda: mock_connection,
                get_project_uuid=lambda: "uuid",
                get_project_layers=lambda: project_layers
            )
            
            # Call default warning - should not raise
            svc._default_warning("Test", "Warning message")
    
    def test_filter_no_connection(self, mock_history_manager, project_layers, mock_layer):
        """Test filter when Spatialite connection unavailable."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            from core.services.filter_application_service import FilterApplicationService
            
            svc = FilterApplicationService(
                history_manager=mock_history_manager,
                get_spatialite_connection=lambda: None,  # No connection
                get_project_uuid=lambda: "uuid",
                get_project_layers=lambda: project_layers
            )
            
            result = svc.apply_subset_filter('filter', mock_layer)
            
            assert result is False


class TestSafeSetSubsetString:
    """Tests for safe_set_subset_string helper function."""
    
    def test_safe_set_subset_string_calls_layer(self):
        """Test that safe_set_subset_string calls layer.setSubsetString."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            from core.services.filter_application_service import safe_set_subset_string
            
            layer = Mock()
            
            safe_set_subset_string(layer, "id > 10")
            
            layer.setSubsetString.assert_called_with("id > 10")
    
    def test_safe_set_subset_string_handles_none_layer(self):
        """Test safe_set_subset_string handles None layer gracefully."""
        with patch('core.services.filter_application_service.is_layer_source_available', return_value=True):
            from core.services.filter_application_service import safe_set_subset_string
            
            # Should not raise
            safe_set_subset_string(None, "id > 10")
