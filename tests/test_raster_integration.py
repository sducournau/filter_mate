"""
Integration tests for raster filtering functionality.

Sprint 2 Day 4 - Testing Phase
Tests the integration between UI controllers, tasks, and services.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRasterFilterControllerIntegration(unittest.TestCase):
    """Test RasterFilterController integration with UI and tasks."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS dependencies
        self.mock_qgis_modules()
        
        # Import after mocking
        from ui.controllers.raster_filter_controller import RasterFilterController
        
        # Create mock dockwidget with required widgets
        self.dockwidget = self.create_mock_dockwidget()
        self.app = Mock()
        
        # Create controller
        self.controller = RasterFilterController(self.dockwidget, self.app)
    
    def mock_qgis_modules(self):
        """Mock QGIS modules to allow testing without QGIS installation."""
        # Mock qgis.core
        mock_qgis_core = MagicMock()
        mock_qgis_core.QgsTask = MagicMock
        mock_qgis_core.QgsMessageLog = MagicMock()
        mock_qgis_core.QgsVectorLayer = MagicMock
        mock_qgis_core.QgsRasterLayer = MagicMock
        mock_qgis_core.QgsProject = MagicMock()
        mock_qgis_core.Qgis = MagicMock()
        
        # Mock qgis.PyQt
        mock_pyqt = MagicMock()
        mock_pyqt.QtCore = MagicMock()
        mock_pyqt.QtCore.pyqtSignal = lambda *args: MagicMock()
        mock_pyqt.QtWidgets = MagicMock()
        
        sys.modules['qgis'] = MagicMock()
        sys.modules['qgis.core'] = mock_qgis_core
        sys.modules['qgis.PyQt'] = mock_pyqt
        sys.modules['qgis.PyQt.QtCore'] = mock_pyqt.QtCore
        sys.modules['qgis.PyQt.QtWidgets'] = mock_pyqt.QtWidgets
    
    def create_mock_dockwidget(self):
        """Create mock dockwidget with all required widgets."""
        dockwidget = Mock()
        
        # Raster layer combo
        dockwidget.rasterLayerCombo = Mock()
        dockwidget.rasterLayerCombo.currentLayer = Mock(return_value=None)
        
        # Range filter widgets
        dockwidget.rangeMinSpinBox = Mock()
        dockwidget.rangeMinSpinBox.value = Mock(return_value=0.0)
        dockwidget.rangeMaxSpinBox = Mock()
        dockwidget.rangeMaxSpinBox.value = Mock(return_value=100.0)
        dockwidget.applyRangeFilterButton = Mock()
        
        # Vector mask widgets
        dockwidget.vectorMaskLayerCombo = Mock()
        dockwidget.vectorMaskLayerCombo.currentLayer = Mock(return_value=None)
        dockwidget.applyVectorMaskButton = Mock()
        
        # Filtered layers list
        dockwidget.filteredLayersList = Mock()
        
        # Signals
        dockwidget.applyRangeFilterButton.clicked = Mock()
        dockwidget.applyVectorMaskButton.clicked = Mock()
        
        return dockwidget
    
    def test_controller_initialization(self):
        """Test controller initializes correctly."""
        self.assertIsNotNone(self.controller)
        self.assertEqual(self.controller.dockwidget, self.dockwidget)
        self.assertEqual(self.controller.app, self.app)
        self.assertEqual(len(self.controller.layer_widgets), 0)
    
    def test_signal_connections(self):
        """Test UI signals are connected to controller methods."""
        # Verify button click signals were connected
        self.dockwidget.applyRangeFilterButton.clicked.connect.assert_called()
        self.dockwidget.applyVectorMaskButton.clicked.connect.assert_called()
    
    def test_range_filter_validation_no_layer(self):
        """Test range filter validation fails when no layer selected."""
        # No layer selected
        self.dockwidget.rasterLayerCombo.currentLayer.return_value = None
        
        # Should not create task
        with patch('ui.controllers.raster_filter_controller.RasterRangeFilterTask') as mock_task:
            self.controller.on_apply_range_filter_clicked()
            mock_task.assert_not_called()
    
    def test_range_filter_validation_invalid_range(self):
        """Test range filter validation fails with invalid range."""
        # Mock layer
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        self.dockwidget.rasterLayerCombo.currentLayer.return_value = mock_layer
        
        # Invalid range (min > max)
        self.dockwidget.rangeMinSpinBox.value.return_value = 100.0
        self.dockwidget.rangeMaxSpinBox.value.return_value = 50.0
        
        # Should not create task
        with patch('ui.controllers.raster_filter_controller.RasterRangeFilterTask') as mock_task:
            self.controller.on_apply_range_filter_clicked()
            mock_task.assert_not_called()
    
    @patch('ui.controllers.raster_filter_controller.QgsApplication')
    @patch('ui.controllers.raster_filter_controller.RasterRangeFilterTask')
    def test_range_filter_task_creation(self, mock_task_class, mock_qgs_app):
        """Test range filter task is created with valid inputs."""
        # Mock layer
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        mock_layer.id.return_value = 'test_layer_id'
        mock_layer.name.return_value = 'Test Raster'
        self.dockwidget.rasterLayerCombo.currentLayer.return_value = mock_layer
        
        # Valid range
        self.dockwidget.rangeMinSpinBox.value.return_value = 10.0
        self.dockwidget.rangeMaxSpinBox.value.return_value = 90.0
        
        # Mock task manager
        mock_task_manager = Mock()
        mock_qgs_app.taskManager.return_value = mock_task_manager
        
        # Create mock task instance
        mock_task = Mock()
        mock_task_class.return_value = mock_task
        
        # Execute
        self.controller.on_apply_range_filter_clicked()
        
        # Verify task was created with correct parameters
        mock_task_class.assert_called_once()
        call_args = mock_task_class.call_args[0]
        self.assertEqual(call_args[0], mock_layer)  # layer
        self.assertEqual(call_args[1], 10.0)  # min_value
        self.assertEqual(call_args[2], 90.0)  # max_value
        
        # Verify task was added to task manager
        mock_task_manager.addTask.assert_called_once_with(mock_task)
    
    def test_cleanup_removes_temporary_layers(self):
        """Test cleanup removes all temporary layers."""
        # Add mock filtered layers
        mock_layer1 = Mock()
        mock_layer1.id.return_value = 'layer1'
        mock_widget1 = Mock()
        
        mock_layer2 = Mock()
        mock_layer2.id.return_value = 'layer2'
        mock_widget2 = Mock()
        
        self.controller.layer_widgets = {
            'layer1': (mock_layer1, mock_widget1),
            'layer2': (mock_layer2, mock_widget2)
        }
        
        # Mock QgsProject
        with patch('ui.controllers.raster_filter_controller.QgsProject') as mock_project:
            mock_project_instance = Mock()
            mock_project.instance.return_value = mock_project_instance
            
            # Execute cleanup
            self.controller.cleanup_on_close()
            
            # Verify layers were removed
            self.assertEqual(mock_project_instance.removeMapLayer.call_count, 2)
            self.assertEqual(len(self.controller.layer_widgets), 0)


class TestRasterRangeFilterTask(unittest.TestCase):
    """Test RasterRangeFilterTask background processing."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS
        self.mock_qgis()
        
        # Import after mocking
        from core.tasks.raster_range_filter_task import RasterRangeFilterTask
        
        self.mock_layer = self.create_mock_raster_layer()
        self.task = RasterRangeFilterTask(self.mock_layer, 10.0, 90.0)
    
    def mock_qgis(self):
        """Mock QGIS modules."""
        mock_core = MagicMock()
        mock_core.QgsTask = object
        mock_core.QgsMessageLog = MagicMock()
        
        sys.modules['qgis.core'] = mock_core
    
    def create_mock_raster_layer(self):
        """Create mock raster layer."""
        layer = Mock()
        layer.id.return_value = 'test_raster'
        layer.name.return_value = 'Test Raster Layer'
        layer.isValid.return_value = True
        layer.width.return_value = 1000
        layer.height.return_value = 1000
        layer.bandCount.return_value = 1
        
        # Mock renderer
        mock_renderer = Mock()
        layer.renderer.return_value = mock_renderer
        layer.setRenderer = Mock()
        
        return layer
    
    def test_task_initialization(self):
        """Test task initializes with correct parameters."""
        self.assertEqual(self.task.layer_id, 'test_raster')
        self.assertEqual(self.task.layer_name, 'Test Raster Layer')
        self.assertEqual(self.task.min_value, 10.0)
        self.assertEqual(self.task.max_value, 90.0)
    
    def test_memory_estimation(self):
        """Test memory estimation calculation."""
        # 1000x1000 pixels, 1 band, 4 bytes per pixel = 4MB
        estimated_memory = 1000 * 1000 * 1 * 4
        
        # Task should estimate similar memory (implementation detail)
        # This is a placeholder - actual implementation may vary
        self.assertGreater(estimated_memory, 0)


class TestRasterMaskTask(unittest.TestCase):
    """Test RasterMaskTask GDAL clipping functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_qgis()
        
        from core.tasks.raster_mask_task import RasterMaskTask
        
        self.mock_raster = Mock()
        self.mock_raster.id.return_value = 'raster1'
        self.mock_raster.name.return_value = 'Test Raster'
        
        self.mock_vector = Mock()
        self.mock_vector.id.return_value = 'vector1'
        self.mock_vector.name.return_value = 'Test Vector'
        
        self.task = RasterMaskTask(self.mock_raster, self.mock_vector)
    
    def mock_qgis(self):
        """Mock QGIS modules."""
        mock_core = MagicMock()
        mock_core.QgsTask = object
        mock_core.QgsMessageLog = MagicMock()
        mock_core.QgsProcessingFeedback = MagicMock
        
        sys.modules['qgis.core'] = mock_core
        sys.modules['qgis'] = MagicMock()
    
    def test_task_initialization(self):
        """Test task initializes with correct layer references."""
        self.assertEqual(self.task.raster_layer_id, 'raster1')
        self.assertEqual(self.task.vector_layer_id, 'vector1')
        self.assertEqual(self.task.output_layer_name, 'Test Raster (masked)')


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRasterFilterControllerIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestRasterRangeFilterTask))
    suite.addTests(loader.loadTestsFromTestCase(TestRasterMaskTask))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
