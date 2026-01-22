"""
Shared test fixtures and configuration for ui tests.

This file configures QGIS mocks that work for all UI modules (layout, styles, dialogs).
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[3]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# ============================================================================
# QGIS Mock Configuration
# ============================================================================


def _configure_qgis_mocks():
    """Configure QGIS mocks to work with all UI modules."""
    
    # Skip if already configured by another conftest
    if 'qgis' in sys.modules and hasattr(sys.modules['qgis'], '_test_configured'):
        return
    
    # Create base mock structure
    _qgis_mock = MagicMock()
    _qgis_mock._test_configured = True  # Mark as configured
    
    # Configure QgsApplication for theme detection
    _qgis_app_mock = MagicMock()
    _palette_mock = MagicMock()
    
    # Configure palette for dark mode detection
    _bg_color_mock = MagicMock()
    _bg_color_mock.red.return_value = 30
    _bg_color_mock.green.return_value = 30
    _bg_color_mock.blue.return_value = 30
    _palette_mock.color.return_value = _bg_color_mock
    _palette_mock.Window = 0
    _qgis_app_mock.palette.return_value = _palette_mock
    _qgis_mock.core.QgsApplication.instance.return_value = _qgis_app_mock
    
    # Configure QtCore with a proper QObject class that works with multiple inheritance
    _qt_core_mock = MagicMock()
    
    class MockQObject:
        """Mock QObject that works with StylerBase inheritance."""
        def __init__(self, *args, **kwargs):
            pass
    
    _qt_core_mock.QObject = MockQObject
    _qt_core_mock.pyqtSignal = lambda *args, **kwargs: MagicMock()
    _qt_core_mock.Qt = MagicMock()
    _qt_core_mock.Qt.PointingHandCursor = 13
    _qt_core_mock.Qt.Horizontal = 1
    _qt_core_mock.Qt.Vertical = 2
    _qt_core_mock.QSize = Mock
    
    # Configure QtWidgets with proper QSizePolicy
    _qt_widgets_mock = MagicMock()
    
    class MockQSizePolicy:
        Fixed = 0
        Minimum = 1
        Maximum = 4
        Preferred = 5
        Expanding = 7
        MinimumExpanding = 3
        Ignored = 13
    
    _qt_widgets_mock.QSizePolicy = MockQSizePolicy
    _qt_widgets_mock.QPushButton = MagicMock
    _qt_widgets_mock.QToolButton = MagicMock
    _qt_widgets_mock.QAbstractButton = MagicMock
    _qt_widgets_mock.QWidget = MagicMock
    _qt_widgets_mock.QSplitter = MagicMock
    _qt_widgets_mock.QScrollArea = MagicMock
    _qt_widgets_mock.QFrame = MagicMock
    _qt_widgets_mock.QDockWidget = MagicMock
    _qt_widgets_mock.QDialog = MagicMock
    _qt_widgets_mock.QVBoxLayout = MagicMock
    _qt_widgets_mock.QHBoxLayout = MagicMock
    _qt_widgets_mock.QListWidget = MagicMock
    _qt_widgets_mock.QLineEdit = MagicMock
    _qt_widgets_mock.QLabel = MagicMock
    
    # Configure QtGui
    _qt_gui_mock = MagicMock()
    _qt_gui_mock.QIcon = MagicMock()
    _qt_gui_mock.QColor = MagicMock()
    _qt_gui_mock.QPixmap = MagicMock()
    _qt_gui_mock.QPainter = MagicMock()
    _qt_gui_mock.QCursor = MagicMock  # Use MagicMock class, not instance
    _qt_gui_mock.QPalette = MagicMock()
    _qt_gui_mock.QPalette.Window = 0
    
    # Configure PyQt wrapper
    _qgis_mock.PyQt = MagicMock()
    _qgis_mock.PyQt.QtCore = _qt_core_mock
    _qgis_mock.PyQt.QtWidgets = _qt_widgets_mock
    _qgis_mock.PyQt.QtGui = _qt_gui_mock
    
    # Register all modules
    sys.modules['qgis'] = _qgis_mock
    sys.modules['qgis.PyQt'] = _qgis_mock.PyQt
    sys.modules['qgis.PyQt.QtCore'] = _qt_core_mock
    sys.modules['qgis.PyQt.QtWidgets'] = _qt_widgets_mock
    sys.modules['qgis.PyQt.QtGui'] = _qt_gui_mock
    sys.modules['qgis.core'] = _qgis_mock.core
    sys.modules['qgis.gui'] = MagicMock()
    sys.modules['qgis.utils'] = MagicMock()
    
    # Mock ui.config
    _mock_ui_config = MagicMock()
    _mock_ui_config.UIConfig = MagicMock()
    _mock_ui_config.UIConfig.get_active_profile = MagicMock(return_value='normal')
    sys.modules['modules'] = MagicMock()
    sys.modules['ui.config'] = _mock_ui_config
    sys.modules['ui.styles'] = MagicMock()


# Configure mocks when this conftest is loaded
_configure_qgis_mocks()


# ============================================================================
# Shared Fixtures
# ============================================================================

@pytest.fixture
def mock_dockwidget():
    """Create mock dockwidget with standard buttons and attributes."""
    dockwidget = Mock()
    dockwidget.plugin_dir = str(plugin_path)
    dockwidget.setStyleSheet = Mock()
    
    # Create mock buttons
    dockwidget.btn_filtering = Mock()
    dockwidget.btn_filtering.objectName.return_value = 'btn_filtering'
    dockwidget.btn_filtering.isCheckable.return_value = False
    dockwidget.btn_filtering.isChecked.return_value = False
    dockwidget.btn_filtering.isEnabled.return_value = True
    
    dockwidget.btn_exploring = Mock()
    dockwidget.btn_exploring.objectName.return_value = 'btn_exploring'
    dockwidget.btn_exploring.isCheckable.return_value = False
    
    dockwidget.btn_exporting = Mock()
    dockwidget.btn_exporting.objectName.return_value = 'btn_exporting'
    dockwidget.btn_exporting.isCheckable.return_value = False
    
    # Mock findChildren to return empty by default
    dockwidget.findChildren.return_value = []
    
    return dockwidget
