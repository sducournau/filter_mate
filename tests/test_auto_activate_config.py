"""
Tests for AUTO_ACTIVATE configuration behavior.

Ensures that when AUTO_ACTIVATE is set to false in configuration,
the plugin never opens automatically.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add plugin directory to path
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)


class TestAutoActivateConfig(unittest.TestCase):
    """Test AUTO_ACTIVATE configuration behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS imports
        self.qgis_core = MagicMock()
        self.qgis_gui = MagicMock()
        self.qgis_pyqt = MagicMock()
        
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = self.qgis_core
        sys.modules['qgis.gui'] = self.qgis_gui
        sys.modules['qgis.PyQt'] = self.qgis_pyqt
        sys.modules['qgis.PyQt.QtCore'] = MagicMock()
        sys.modules['qgis.PyQt.QtGui'] = MagicMock()
        sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()
        sys.modules['qgis.utils'] = MagicMock()
    
    @patch('filter_mate.logger')
    def test_auto_activate_disabled_in_config(self, mock_logger):
        """Test that _auto_activate_plugin returns early when AUTO_ACTIVATE is false."""
        # Mock config with AUTO_ACTIVATE = false
        mock_env_vars = {
            'CONFIG_DATA': {
                'APP': {
                    'AUTO_ACTIVATE': {
                        'value': False
                    }
                }
            }
        }
        
        with patch('filter_mate.ENV_VARS', mock_env_vars):
            from filter_mate import FilterMate
            
            # Mock iface
            mock_iface = MagicMock()
            mock_iface.mainWindow.return_value = MagicMock()
            
            # Create plugin instance
            plugin = FilterMate(mock_iface)
            plugin.pluginIsActive = False
            
            # Mock run method to track if it was called
            plugin.run = Mock()
            
            # Call _auto_activate_plugin
            plugin._auto_activate_plugin()
            
            # Verify run was NOT called
            plugin.run.assert_not_called()
            
            # Verify debug log was called
            mock_logger.debug.assert_called_with(
                "FilterMate: Auto-activation disabled, skipping auto-activation"
            )
    
    @patch('filter_mate.logger')
    def test_auto_activate_for_new_layers_disabled_in_config(self, mock_logger):
        """Test that _auto_activate_for_new_layers returns early when AUTO_ACTIVATE is false."""
        # Mock config with AUTO_ACTIVATE = false
        mock_env_vars = {
            'CONFIG_DATA': {
                'APP': {
                    'AUTO_ACTIVATE': {
                        'value': False
                    }
                }
            }
        }
        
        with patch('filter_mate.ENV_VARS', mock_env_vars):
            from filter_mate import FilterMate
            
            # Mock iface
            mock_iface = MagicMock()
            mock_iface.mainWindow.return_value = MagicMock()
            
            # Create plugin instance
            plugin = FilterMate(mock_iface)
            plugin.pluginIsActive = False
            
            # Mock run method to track if it was called
            plugin.run = Mock()
            
            # Mock vector layers
            mock_layer = MagicMock()
            mock_layer.__class__.__name__ = 'QgsVectorLayer'
            
            # Call _auto_activate_for_new_layers
            plugin._auto_activate_for_new_layers([mock_layer])
            
            # Verify run was NOT called
            plugin.run.assert_not_called()
            
            # Verify debug log was called
            mock_logger.debug.assert_called_with(
                "FilterMate: Auto-activation disabled, skipping layersAdded auto-activation"
            )
    
    @patch('filter_mate.logger')
    def test_connect_auto_activation_signals_disabled_in_config(self, mock_logger):
        """Test that _connect_auto_activation_signals disconnects signals when AUTO_ACTIVATE is false."""
        # Mock config with AUTO_ACTIVATE = false
        mock_env_vars = {
            'CONFIG_DATA': {
                'APP': {
                    'AUTO_ACTIVATE': {
                        'value': False
                    }
                }
            }
        }
        
        with patch('filter_mate.ENV_VARS', mock_env_vars):
            from filter_mate import FilterMate
            
            # Mock iface
            mock_iface = MagicMock()
            mock_iface.mainWindow.return_value = MagicMock()
            
            # Create plugin instance
            plugin = FilterMate(mock_iface)
            plugin._auto_activation_signals_connected = True
            
            # Mock _disconnect_auto_activation_signals
            plugin._disconnect_auto_activation_signals = Mock()
            
            # Call _connect_auto_activation_signals
            plugin._connect_auto_activation_signals()
            
            # Verify disconnect was called
            plugin._disconnect_auto_activation_signals.assert_called_once()
            
            # Verify info log was called
            mock_logger.info.assert_called_with(
                "FilterMate: Auto-activation disabled in configuration"
            )
    
    @patch('filter_mate.logger')
    def test_auto_activate_enabled_in_config(self, mock_logger):
        """Test that _auto_activate_plugin works normally when AUTO_ACTIVATE is true."""
        # Mock config with AUTO_ACTIVATE = true
        mock_env_vars = {
            'CONFIG_DATA': {
                'APP': {
                    'AUTO_ACTIVATE': {
                        'value': True
                    }
                }
            }
        }
        
        # Mock QgsProject and vector layers
        mock_project = MagicMock()
        mock_layer = MagicMock()
        mock_layer.__class__.__name__ = 'QgsVectorLayer'
        mock_project.instance.return_value.mapLayers.return_value.values.return_value = [mock_layer]
        
        with patch('filter_mate.ENV_VARS', mock_env_vars), \
             patch('filter_mate.QgsProject', mock_project), \
             patch('filter_mate.QgsVectorLayer', MagicMock()):
            from filter_mate import FilterMate
            
            # Mock iface
            mock_iface = MagicMock()
            mock_iface.mainWindow.return_value = MagicMock()
            
            # Create plugin instance
            plugin = FilterMate(mock_iface)
            plugin.pluginIsActive = False
            
            # Mock run method and QTimer
            plugin.run = Mock()
            mock_timer = MagicMock()
            
            with patch('filter_mate.QTimer', mock_timer):
                # Call _auto_activate_plugin
                plugin._auto_activate_plugin()
                
                # Verify QTimer.singleShot was called (meaning activation was scheduled)
                mock_timer.singleShot.assert_called_once()


if __name__ == '__main__':
    unittest.main()
