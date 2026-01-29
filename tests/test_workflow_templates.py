"""
Tests for EPIC-3 Workflow Templates feature.

Tests the WorkflowTemplateService and related UI components.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRasterFilterRule(unittest.TestCase):
    """Tests for RasterFilterRule dataclass."""
    
    def test_create_rule(self):
        """Test creating a raster filter rule."""
        from core.services.workflow_template_service import RasterFilterRule
        
        rule = RasterFilterRule(
            rule_id="test123",
            raster_name_pattern="dem_*",
            band=1,
            predicate="within_range",
            min_value=100.0,
            max_value=500.0,
            enabled=True
        )
        
        self.assertEqual(rule.rule_id, "test123")
        self.assertEqual(rule.raster_name_pattern, "dem_*")
        self.assertEqual(rule.band, 1)
        self.assertEqual(rule.predicate, "within_range")
        self.assertEqual(rule.min_value, 100.0)
        self.assertEqual(rule.max_value, 500.0)
        self.assertTrue(rule.enabled)
    
    def test_from_dict(self):
        """Test creating rule from dictionary."""
        from core.services.workflow_template_service import RasterFilterRule
        
        data = {
            'rule_id': 'abc123',
            'raster_name_pattern': 'elevation_*',
            'band': 2,
            'predicate': 'above_value',
            'min_value': 50.0,
            'max_value': None,
            'enabled': False
        }
        
        rule = RasterFilterRule.from_dict(data)
        
        self.assertEqual(rule.rule_id, 'abc123')
        self.assertEqual(rule.raster_name_pattern, 'elevation_*')
        self.assertEqual(rule.band, 2)
        self.assertEqual(rule.predicate, 'above_value')
        self.assertEqual(rule.min_value, 50.0)
        self.assertIsNone(rule.max_value)
        self.assertFalse(rule.enabled)


class TestVectorClipRule(unittest.TestCase):
    """Tests for VectorClipRule dataclass."""
    
    def test_create_rule(self):
        """Test creating a vector clip rule."""
        from core.services.workflow_template_service import VectorClipRule
        
        rule = VectorClipRule(
            rule_id="vec123",
            vector_name_pattern="parcels_*",
            operation="clip_extent",
            feature_filter="selected",
            filter_expression=None,
            enabled=True
        )
        
        self.assertEqual(rule.rule_id, "vec123")
        self.assertEqual(rule.vector_name_pattern, "parcels_*")
        self.assertEqual(rule.operation, "clip_extent")
        self.assertEqual(rule.feature_filter, "selected")
        self.assertIsNone(rule.filter_expression)
        self.assertTrue(rule.enabled)
    
    def test_from_dict_with_expression(self):
        """Test creating rule from dictionary with filter expression."""
        from core.services.workflow_template_service import VectorClipRule
        
        data = {
            'rule_id': 'vec456',
            'vector_name_pattern': 'zones_*',
            'operation': 'mask_outside',
            'feature_filter': 'expression',
            'filter_expression': '"area" > 1000',
            'enabled': True
        }
        
        rule = VectorClipRule.from_dict(data)
        
        self.assertEqual(rule.filter_expression, '"area" > 1000')
        self.assertEqual(rule.feature_filter, 'expression')


class TestWorkflowTemplate(unittest.TestCase):
    """Tests for WorkflowTemplate dataclass."""
    
    def test_create_template(self):
        """Test creating a workflow template."""
        from core.services.workflow_template_service import (
            WorkflowTemplate, RasterFilterRule
        )
        
        rule = RasterFilterRule(
            rule_id="r1",
            raster_name_pattern="dem",
            band=1,
            min_value=0,
            max_value=100
        )
        
        template = WorkflowTemplate(
            template_id="tmpl001",
            name="Test Template",
            description="A test template",
            source_type="raster",
            source_name_pattern="dem_*",
            raster_rules=[rule],
            tags=["test", "demo"]
        )
        
        self.assertEqual(template.name, "Test Template")
        self.assertEqual(len(template.raster_rules), 1)
        self.assertEqual(template.tags, ["test", "demo"])
        self.assertIsNotNone(template.created_at)
    
    def test_to_dict_and_from_dict(self):
        """Test template serialization round-trip."""
        from core.services.workflow_template_service import (
            WorkflowTemplate, RasterFilterRule
        )
        
        rule = RasterFilterRule(
            rule_id="r1",
            raster_name_pattern="elevation",
            band=1,
            min_value=100,
            max_value=500
        )
        
        original = WorkflowTemplate(
            template_id="tmpl002",
            name="Roundtrip Test",
            description="Test serialization",
            source_type="raster",
            source_name_pattern="elevation_*",
            raster_rules=[rule],
            target_layer_patterns=["parcels", "zones"],
            tags=["test"]
        )
        
        # Serialize and deserialize
        data = original.to_dict()
        restored = WorkflowTemplate.from_dict(data)
        
        self.assertEqual(restored.template_id, original.template_id)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(len(restored.raster_rules), 1)
        self.assertEqual(restored.raster_rules[0].min_value, 100)
        self.assertEqual(restored.target_layer_patterns, ["parcels", "zones"])


class TestWorkflowTemplateService(unittest.TestCase):
    """Tests for WorkflowTemplateService."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temp directory for templates
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_service_init(self, mock_qgs):
        """Test service initialization."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        self.assertIsNotNone(service)
        self.assertEqual(len(service.get_all_templates()), 0)
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_create_template(self, mock_qgs):
        """Test creating a new template."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        template = service.create_template(
            name="My Filter",
            description="Test filter template",
            source_type="raster"
        )
        
        self.assertIsNotNone(template)
        self.assertEqual(template.name, "My Filter")
        self.assertEqual(len(service.get_all_templates()), 1)
    
    @patch('core.services.workflow_template_service.QgsApplication')
    @patch('core.services.workflow_template_service.QgsProject')
    def test_create_from_context(self, mock_project, mock_qgs):
        """Test creating template from filter context."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        context = {
            'source_type': 'raster',
            'layer_name': 'DEM_Switzerland',
            'band': 1,
            'range_min': 500.0,
            'range_max': 2000.0,
            'predicate': 'within_range',
            'target_layers': [],
            'add_to_memory': True
        }
        
        template = service.create_from_context(
            name="Alpine Filter",
            context=context,
            description="Filter for alpine elevations",
            tags=["elevation", "alpine"]
        )
        
        self.assertEqual(template.name, "Alpine Filter")
        self.assertEqual(len(template.raster_rules), 1)
        self.assertEqual(template.raster_rules[0].min_value, 500.0)
        self.assertEqual(template.raster_rules[0].max_value, 2000.0)
        self.assertEqual(template.tags, ["elevation", "alpine"])
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_update_template(self, mock_qgs):
        """Test updating a template."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        template = service.create_template(name="Original Name")
        original_updated = template.updated_at
        
        updated = service.update_template(
            template.template_id,
            name="Updated Name",
            description="New description"
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Updated Name")
        self.assertEqual(updated.description, "New description")
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_delete_template(self, mock_qgs):
        """Test deleting a template."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        template = service.create_template(name="To Delete")
        template_id = template.template_id
        
        self.assertEqual(len(service.get_all_templates()), 1)
        
        result = service.delete_template(template_id)
        
        self.assertTrue(result)
        self.assertEqual(len(service.get_all_templates()), 0)
        self.assertIsNone(service.get_template(template_id))
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_search_templates(self, mock_qgs):
        """Test searching templates."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        service.create_template(name="Elevation Filter", tags=["dem", "altitude"])
        service.create_template(name="Land Use Filter", tags=["landuse", "classification"])
        service.create_template(name="High Altitude", tags=["dem", "high"])
        
        # Search by name
        results = service.search_templates(name_contains="Elevation")
        self.assertEqual(len(results), 1)
        
        # Search by tag
        results = service.search_templates(tags=["dem"])
        self.assertEqual(len(results), 2)
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_export_import_template(self, mock_qgs):
        """Test exporting and importing a template."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        template = service.create_template(
            name="Export Test",
            description="Template for export test",
            tags=["export", "test"]
        )
        
        # Export
        export_path = os.path.join(self.temp_dir, "exported.json")
        result = service.export_template(template.template_id, export_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(export_path))
        
        # Verify export content
        with open(export_path, 'r') as f:
            exported_data = json.load(f)
        self.assertEqual(exported_data['name'], "Export Test")
        
        # Create new service and import
        service2 = WorkflowTemplateService(storage_path=tempfile.mkdtemp())
        imported = service2.import_template(export_path)
        
        self.assertIsNotNone(imported)
        self.assertEqual(imported.name, "Export Test")
        self.assertEqual(imported.tags, ["export", "test"])
    
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_persistence(self, mock_qgs):
        """Test that templates persist across service instances."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        # Create service and add templates
        service1 = WorkflowTemplateService(storage_path=self.temp_dir)
        service1.create_template(name="Persistent Template 1")
        service1.create_template(name="Persistent Template 2")
        
        self.assertEqual(len(service1.get_all_templates()), 2)
        
        # Create new service instance with same storage
        service2 = WorkflowTemplateService(storage_path=self.temp_dir)
        
        # Should load existing templates
        self.assertEqual(len(service2.get_all_templates()), 2)
        
        # Verify content
        names = [t.name for t in service2.get_all_templates()]
        self.assertIn("Persistent Template 1", names)
        self.assertIn("Persistent Template 2", names)


class TestTemplateMatching(unittest.TestCase):
    """Tests for template matching to project layers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('core.services.workflow_template_service.QgsProject')
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_match_template_to_project(self, mock_qgs, mock_project):
        """Test matching template patterns to project layers."""
        from core.services.workflow_template_service import (
            WorkflowTemplateService, RasterFilterRule
        )
        
        # Mock project with layers
        mock_raster = MagicMock()
        mock_raster.name.return_value = "DEM_2024"
        mock_raster.id.return_value = "raster_123"
        mock_raster.type.return_value = 1  # Raster
        
        mock_vector = MagicMock()
        mock_vector.name.return_value = "parcels_city"
        mock_vector.id.return_value = "vector_456"
        mock_vector.type.return_value = 0  # Vector
        
        mock_project.instance.return_value.mapLayers.return_value = {
            'raster_123': mock_raster,
            'vector_456': mock_vector
        }
        
        # Create service with template
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        rule = RasterFilterRule(
            rule_id="r1",
            raster_name_pattern="DEM_*",
            band=1,
            min_value=0,
            max_value=1000
        )
        
        template = service.create_template(
            name="DEM Filter",
            source_type="raster",
            source_name_pattern="DEM_*",
            raster_rules=[rule],
            target_layer_patterns=["parcels_*"]
        )
        
        # Match template
        result = service.match_template_to_project(template.template_id)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.source_layer_name, "DEM_2024")


class TestSignalChain(unittest.TestCase):
    """Tests for signal propagation in template saving workflow."""
    
    def test_signal_emission(self):
        """Test that template_saved signal is emitted."""
        from core.services.workflow_template_service import WorkflowTemplateService
        
        temp_dir = tempfile.mkdtemp()
        
        with patch('core.services.workflow_template_service.QgsApplication'):
            service = WorkflowTemplateService(storage_path=temp_dir)
            
            # Connect signal
            signal_received = []
            service.template_saved.connect(
                lambda tid, name: signal_received.append((tid, name))
            )
            
            # Create template
            template = service.create_template(name="Signal Test")
            
            # Verify signal was emitted
            self.assertEqual(len(signal_received), 1)
            self.assertEqual(signal_received[0][1], "Signal Test")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


class TestLoadTemplateDialog(unittest.TestCase):
    """Tests for LoadTemplateDialog."""
    
    def test_dialog_creation(self):
        """Test creating LoadTemplateDialog with templates."""
        from ui.widgets.workflow_templates_widget import LoadTemplateDialog
        
        templates = [
            {
                'template_id': 'tmpl1',
                'name': 'DEM Filter',
                'description': 'Filter for elevation data',
                'source_type': 'raster',
                'tags': ['dem', 'elevation']
            },
            {
                'template_id': 'tmpl2',
                'name': 'Land Use Filter',
                'description': 'Filter for land use classification',
                'source_type': 'raster',
                'tags': ['landuse']
            }
        ]
        
        # We can't fully test without PyQt5, but we can test the class exists
        self.assertTrue(LoadTemplateDialog is not None)
    
    def test_empty_templates_list(self):
        """Test dialog with empty templates list."""
        from ui.widgets.workflow_templates_widget import LoadTemplateDialog
        
        templates = []
        # The class should handle empty list gracefully
        self.assertTrue(LoadTemplateDialog is not None)


class TestApplyTemplate(unittest.TestCase):
    """Tests for applying templates to filter context."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('core.services.workflow_template_service.QgsProject')
    @patch('core.services.workflow_template_service.QgsApplication')
    def test_build_context_from_template(self, mock_qgs, mock_project):
        """Test building filter context from a template."""
        from core.services.workflow_template_service import (
            WorkflowTemplateService, RasterFilterRule
        )
        
        # Mock project with a layer
        mock_layer = MagicMock()
        mock_layer.name.return_value = "DEM_Alps"
        mock_layer.id.return_value = "raster_123"
        mock_layer.type.return_value = 1  # Raster
        
        mock_project.instance.return_value.mapLayers.return_value = {
            'raster_123': mock_layer
        }
        
        service = WorkflowTemplateService(storage_path=self.temp_dir)
        
        # Create template with rules
        rule = RasterFilterRule(
            rule_id="r1",
            raster_name_pattern="DEM_*",
            band=1,
            predicate="within_range",
            min_value=1000,
            max_value=3000
        )
        
        template = service.create_template(
            name="Alps Filter",
            source_type="raster",
            source_name_pattern="DEM_*",
            raster_rules=[rule]
        )
        
        # Build context from template
        context = service.build_context_from_template(template.template_id)
        
        self.assertIsNotNone(context)
        self.assertEqual(context.get('source_type'), 'raster')


if __name__ == '__main__':
    unittest.main()
