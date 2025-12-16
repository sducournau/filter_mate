"""
Test PostgreSQL layer handling when psycopg2 is not available.

This test verifies that FilterMate correctly handles PostgreSQL layers
when psycopg2 is not installed, displaying appropriate warnings and
preventing activation attempts that would fail.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)


class TestPostgreSQLLayerHandling(unittest.TestCase):
    """Test PostgreSQL layer detection and warning system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QGIS dependencies
        self.mock_qgs_vector_layer = Mock()
        self.mock_qgs_vector_layer.return_value.isValid.return_value = True
        self.mock_qgs_vector_layer.return_value.providerType.return_value = 'postgres'
        self.mock_qgs_vector_layer.return_value.name.return_value = "Test PostgreSQL Layer"
        
    @patch('filter_mate.modules.appUtils.POSTGRESQL_AVAILABLE', False)
    @patch('filter_mate.modules.appUtils.psycopg2', None)
    def test_is_layer_source_available_postgres_without_psycopg2(self):
        """Test that PostgreSQL layers are rejected when psycopg2 is not available."""
        from filter_mate.modules.appUtils import is_layer_source_available, POSTGRESQL_AVAILABLE
        
        # Verify psycopg2 is mocked as unavailable
        self.assertFalse(POSTGRESQL_AVAILABLE)
        
        # Create a mock PostgreSQL layer
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "Test PostgreSQL Layer"
        
        # Should return False because psycopg2 is not available
        result = is_layer_source_available(mock_layer)
        
        self.assertFalse(
            result,
            "PostgreSQL layer should be rejected when psycopg2 is not available"
        )
    
    @patch('filter_mate.modules.appUtils.POSTGRESQL_AVAILABLE', True)
    @patch('filter_mate.modules.appUtils.psycopg2', MagicMock())
    def test_is_layer_source_available_postgres_with_psycopg2(self):
        """Test that PostgreSQL layers are accepted when psycopg2 is available."""
        from filter_mate.modules.appUtils import is_layer_source_available, POSTGRESQL_AVAILABLE
        
        # Verify psycopg2 is mocked as available
        self.assertTrue(POSTGRESQL_AVAILABLE)
        
        # Create a mock PostgreSQL layer
        mock_layer = Mock()
        mock_layer.isValid.return_value = True
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "Test PostgreSQL Layer"
        
        # Mock detect_layer_provider_type to return 'postgresql'
        with patch('filter_mate.modules.appUtils.detect_layer_provider_type', return_value='postgresql'):
            result = is_layer_source_available(mock_layer)
        
        self.assertTrue(
            result,
            "PostgreSQL layer should be accepted when psycopg2 is available"
        )
    
    @patch('filter_mate.modules.appUtils.POSTGRESQL_AVAILABLE', False)
    def test_filter_usable_layers_excludes_postgres_without_psycopg2(self):
        """Test that _filter_usable_layers excludes PostgreSQL layers when psycopg2 is unavailable."""
        from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
        
        # Verify psycopg2 is unavailable
        self.assertFalse(POSTGRESQL_AVAILABLE)
        
        # Create mock layers: 1 PostgreSQL, 1 Spatialite
        postgres_layer = Mock()
        postgres_layer.isValid.return_value = True
        postgres_layer.providerType.return_value = 'postgres'
        postgres_layer.name.return_value = "PostgreSQL Layer"
        
        spatialite_layer = Mock()
        spatialite_layer.isValid.return_value = True
        spatialite_layer.providerType.return_value = 'spatialite'
        spatialite_layer.source.return_value = "/path/to/db.sqlite"
        spatialite_layer.name.return_value = "Spatialite Layer"
        
        # Mock is_layer_source_available to reject PostgreSQL without psycopg2
        def mock_source_available(layer):
            if layer.providerType() == 'postgres':
                return POSTGRESQL_AVAILABLE  # False
            return True
        
        with patch('filter_mate.modules.appUtils.is_layer_source_available', side_effect=mock_source_available):
            from filter_mate.filter_mate_app import FilterMateApp
            
            # Create mock app instance
            app = Mock(spec=FilterMateApp)
            app._filter_usable_layers = FilterMateApp._filter_usable_layers.__get__(app, FilterMateApp)
            
            # Test filtering
            layers = [postgres_layer, spatialite_layer]
            filtered = app._filter_usable_layers(layers)
            
            # Only Spatialite layer should be included
            self.assertEqual(
                len(filtered), 1,
                "Should filter out PostgreSQL layer when psycopg2 unavailable"
            )
            self.assertEqual(
                filtered[0].providerType(), 'spatialite',
                "Remaining layer should be Spatialite"
            )
    
    def test_warning_message_format(self):
        """Test that PostgreSQL unavailable warnings have correct format."""
        # Test warning message contains necessary information
        warning_template = (
            "Couches PostgreSQL détectées ({layer_names}) mais psycopg2 n'est pas installé. "
            "Le plugin ne peut pas utiliser ces couches. "
            "Installez psycopg2 pour activer le support PostgreSQL."
        )
        
        layer_names = "layer1, layer2, layer3"
        message = warning_template.format(layer_names=layer_names)
        
        # Verify key phrases are present
        self.assertIn("PostgreSQL", message)
        self.assertIn("psycopg2", message)
        self.assertIn("installé", message.lower())
        self.assertIn(layer_names, message)
    
    @patch('filter_mate.modules.appUtils.POSTGRESQL_AVAILABLE', False)
    def test_get_datasource_connexion_returns_none_without_psycopg2(self):
        """Test that get_datasource_connexion_from_layer returns None when psycopg2 unavailable."""
        from filter_mate.modules.appUtils import get_datasource_connexion_from_layer, POSTGRESQL_AVAILABLE
        
        # Verify psycopg2 is unavailable
        self.assertFalse(POSTGRESQL_AVAILABLE)
        
        # Create mock PostgreSQL layer
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "Test Layer"
        
        # Should return (None, None) when psycopg2 not available
        connection, source_uri = get_datasource_connexion_from_layer(mock_layer)
        
        self.assertIsNone(
            connection,
            "Connection should be None when psycopg2 unavailable"
        )
        self.assertIsNone(
            source_uri,
            "Source URI should be None when psycopg2 unavailable"
        )


class TestPostgreSQLLayerWarnings(unittest.TestCase):
    """Test warning system for PostgreSQL layers without psycopg2."""
    
    @patch('filter_mate.modules.appUtils.POSTGRESQL_AVAILABLE', False)
    @patch('qgis.utils.iface')
    def test_on_layers_added_shows_warning_for_postgres(self, mock_iface):
        """Test that _on_layers_added shows warning when PostgreSQL layers added without psycopg2."""
        from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
        
        # Verify psycopg2 unavailable
        self.assertFalse(POSTGRESQL_AVAILABLE)
        
        # Create mock PostgreSQL layers
        postgres_layer1 = Mock()
        postgres_layer1.providerType.return_value = 'postgres'
        postgres_layer1.name.return_value = "PostgreSQL Layer 1"
        
        postgres_layer2 = Mock()
        postgres_layer2.providerType.return_value = 'postgres'
        postgres_layer2.name.return_value = "PostgreSQL Layer 2"
        
        # Mock message bar
        mock_message_bar = Mock()
        mock_iface.messageBar.return_value = mock_message_bar
        
        from filter_mate.filter_mate_app import FilterMateApp
        
        # Create mock app
        app = Mock(spec=FilterMateApp)
        app._on_layers_added = FilterMateApp._on_layers_added.__get__(app, FilterMateApp)
        app._filter_usable_layers = Mock(return_value=[])
        app.manage_task = Mock()
        
        # Call _on_layers_added with PostgreSQL layers
        layers = [postgres_layer1, postgres_layer2]
        app._on_layers_added(layers)
        
        # Verify warning was shown
        mock_message_bar.pushWarning.assert_called_once()
        
        # Get the actual warning message
        call_args = mock_message_bar.pushWarning.call_args
        message = call_args[0][1] if len(call_args[0]) > 1 else ""
        
        # Verify message contains key information
        self.assertIn("PostgreSQL", message)
        self.assertIn("psycopg2", message)
    
    @patch('filter_mate.modules.tasks.layer_management_task.POSTGRESQL_AVAILABLE', True)
    def test_postgresql_layer_without_primary_key_rejected(self):
        """
        Test that PostgreSQL layers without a unique field are rejected.
        
        Virtual fields (like virtual_id) cannot be used in SQL queries that 
        execute on the PostgreSQL server, so layers without a real unique 
        field must be rejected.
        """
        from filter_mate.modules.tasks.layer_management_task import LayersManagementEngineTask
        
        # Create mock layer without unique field
        mock_layer = Mock()
        mock_layer.providerType.return_value = 'postgres'
        mock_layer.name.return_value = "PostgreSQL Table Without PK"
        mock_layer.featureCount.return_value = 100
        mock_layer.primaryKeyAttributes.return_value = []  # No declared primary key
        
        # Create mock fields without 'id' in name and no unique values
        mock_field1 = Mock()
        mock_field1.name.return_value = "name"
        mock_field1.typeName.return_value = "VARCHAR"
        mock_field1.isNumeric.return_value = False
        
        mock_field2 = Mock()
        mock_field2.name.return_value = "status"
        mock_field2.typeName.return_value = "VARCHAR"
        mock_field2.isNumeric.return_value = False
        
        mock_fields = Mock()
        mock_fields.__iter__ = Mock(return_value=iter([mock_field1, mock_field2]))
        mock_layer.fields.return_value = mock_fields
        
        # uniqueValues should return non-unique counts (< feature_count)
        mock_layer.uniqueValues.return_value = [1, 2]  # Only 2 unique values, but 100 features
        
        # Create task
        task = LayersManagementEngineTask("Test Task", {})
        
        # Should raise ValueError because PostgreSQL layers cannot use virtual_id
        with self.assertRaises(ValueError) as context:
            task.search_primary_key_from_layer(mock_layer)
        
        # Verify error message is informative
        error_message = str(context.exception)
        self.assertIn("PostgreSQL", error_message)
        self.assertIn("virtual_id", error_message.lower())
        self.assertIn("PRIMARY KEY", error_message)


if __name__ == '__main__':
    unittest.main()
