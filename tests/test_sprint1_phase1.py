"""
Unit tests for Sprint 1 Phase 1 implementations.

Tests cover:
- ARCH-007: SignalManager
- ARCH-008: Debouncer
- ARCH-009: ProviderUtils
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSignalManager(unittest.TestCase):
    """Test cases for SignalManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        from adapters.qgis.signals.signal_manager import SignalManager
        self.manager = SignalManager(debug=True)
    
    def tearDown(self):
        """Clean up after tests."""
        self.manager.cleanup()
    
    def test_initialization(self):
        """Test SignalManager initializes correctly."""
        self.assertEqual(self.manager.get_connection_count(), 0)
        self.assertEqual(len(self.manager), 0)
    
    def test_connect_signal(self):
        """Test connecting a signal."""
        sender = Mock()
        sender.clicked = Mock()
        receiver = Mock()
        
        conn_id = self.manager.connect(sender, 'clicked', receiver)
        
        self.assertIsNotNone(conn_id)
        self.assertTrue(conn_id.startswith('sig_'))
        self.assertEqual(self.manager.get_connection_count(), 1)
        sender.clicked.connect.assert_called_once_with(receiver)
    
    def test_connect_with_context(self):
        """Test connecting with context."""
        sender = Mock()
        sender.clicked = Mock()
        
        conn_id = self.manager.connect(
            sender, 'clicked', Mock(), context='test_context'
        )
        
        connections = self.manager.get_connections_by_context('test_context')
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0], conn_id)
    
    def test_disconnect_by_id(self):
        """Test disconnecting by connection ID."""
        sender = Mock()
        sender.clicked = Mock()
        receiver = Mock()
        
        conn_id = self.manager.connect(sender, 'clicked', receiver)
        self.assertEqual(self.manager.get_connection_count(), 1)
        
        result = self.manager.disconnect(conn_id)
        
        self.assertTrue(result)
        self.assertEqual(self.manager.get_connection_count(), 0)
        sender.clicked.disconnect.assert_called_once_with(receiver)
    
    def test_disconnect_nonexistent(self):
        """Test disconnecting non-existent connection."""
        result = self.manager.disconnect('nonexistent_id')
        self.assertFalse(result)
    
    def test_disconnect_by_sender(self):
        """Test disconnecting all from a sender."""
        sender = Mock()
        sender.clicked = Mock()
        sender.changed = Mock()
        
        self.manager.connect(sender, 'clicked', Mock())
        self.manager.connect(sender, 'changed', Mock())
        self.assertEqual(self.manager.get_connection_count(), 2)
        
        count = self.manager.disconnect_by_sender(sender)
        
        self.assertEqual(count, 2)
        self.assertEqual(self.manager.get_connection_count(), 0)
    
    def test_disconnect_by_context(self):
        """Test disconnecting all from context."""
        sender1 = Mock()
        sender1.clicked = Mock()
        sender2 = Mock()
        sender2.clicked = Mock()
        
        self.manager.connect(sender1, 'clicked', Mock(), context='ctx_a')
        self.manager.connect(sender2, 'clicked', Mock(), context='ctx_a')
        self.manager.connect(sender1, 'clicked', Mock(), context='ctx_b')
        
        count = self.manager.disconnect_by_context('ctx_a')
        
        self.assertEqual(count, 2)
        self.assertEqual(self.manager.get_connection_count(), 1)
    
    def test_disconnect_all(self):
        """Test disconnecting all signals."""
        for i in range(5):
            sender = Mock()
            sender.clicked = Mock()
            self.manager.connect(sender, 'clicked', Mock())
        
        self.assertEqual(self.manager.get_connection_count(), 5)
        
        count = self.manager.disconnect_all()
        
        self.assertEqual(count, 5)
        self.assertEqual(self.manager.get_connection_count(), 0)
    
    def test_block_context(self):
        """Test blocking a context."""
        sender = Mock()
        sender.clicked = Mock()
        
        self.manager.connect(sender, 'clicked', Mock(), context='blockable')
        self.manager.block_context('blockable')
        
        self.assertTrue(self.manager.is_context_blocked('blockable'))
        sender.clicked.disconnect.assert_called()
    
    def test_unblock_context(self):
        """Test unblocking a context."""
        sender = Mock()
        sender.clicked = Mock()
        receiver = Mock()
        
        self.manager.connect(sender, 'clicked', receiver, context='blockable')
        self.manager.block_context('blockable')
        self.manager.unblock_context('blockable')
        
        self.assertFalse(self.manager.is_context_blocked('blockable'))
    
    def test_get_connections_summary(self):
        """Test getting connections summary."""
        sender = Mock()
        sender.clicked = Mock()
        
        self.manager.connect(sender, 'clicked', Mock(), context='ui')
        
        summary = self.manager.get_connections_summary()
        
        self.assertIn('SignalManager:', summary)
        self.assertIn('1 active connections', summary)
        self.assertIn('[ui]', summary)
    
    def test_prune_dead_connections(self):
        """Test pruning dead connections."""
        # Create a connection with a "dead" sender
        sender = Mock()
        sender.clicked = Mock()
        
        self.manager.connect(sender, 'clicked', Mock())
        
        # Simulate sender deletion by making weakref return None
        # Note: This requires internal access for testing
        conn_id = list(self.manager._connections.keys())[0]
        self.manager._connections[conn_id].sender_ref = lambda: None
        
        count = self.manager.prune_dead_connections()
        
        self.assertEqual(count, 1)
        self.assertEqual(self.manager.get_connection_count(), 0)
    
    def test_cleanup(self):
        """Test full cleanup."""
        sender = Mock()
        sender.clicked = Mock()
        
        self.manager.connect(sender, 'clicked', Mock(), context='test')
        self.manager.block_context('test')
        
        self.manager.cleanup()
        
        self.assertEqual(self.manager.get_connection_count(), 0)
        self.assertEqual(len(self.manager._blocked_contexts), 0)
    
    def test_signal_not_found_raises(self):
        """Test that connecting to non-existent signal raises."""
        sender = Mock(spec=[])  # No signals
        
        with self.assertRaises(ValueError):
            self.manager.connect(sender, 'nonexistent', Mock())
    
    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.manager)
        self.assertIn('SignalManager', repr_str)
        self.assertIn('0 connections', repr_str)


class TestDebouncer(unittest.TestCase):
    """Test cases for Debouncer."""
    
    def test_initialization(self):
        """Test Debouncer initializes correctly."""
        from adapters.qgis.signals.debouncer import Debouncer
        
        debouncer = Debouncer(delay_ms=500)
        
        self.assertEqual(debouncer.delay_ms, 500)
        self.assertFalse(debouncer.is_pending())
    
    def test_delay_property(self):
        """Test delay property getter/setter."""
        from adapters.qgis.signals.debouncer import Debouncer
        
        debouncer = Debouncer(delay_ms=300)
        
        self.assertEqual(debouncer.delay_ms, 300)
        
        debouncer.delay_ms = 500
        self.assertEqual(debouncer.delay_ms, 500)
        
        # Negative values should be clamped to 0
        debouncer.delay_ms = -100
        self.assertEqual(debouncer.delay_ms, 0)
    
    def test_cancel(self):
        """Test cancelling pending call."""
        from adapters.qgis.signals.debouncer import Debouncer, HAS_QT
        
        debouncer = Debouncer(delay_ms=300)
        callback = Mock()
        
        # Note: Without Qt, call() executes immediately (fallback behavior)
        # This test verifies cancel behavior when Qt is available
        if HAS_QT:
            debouncer.call(callback, 'arg1')
            debouncer.cancel()
            
            self.assertFalse(debouncer.is_pending())
            callback.assert_not_called()
        else:
            # Without Qt, we just verify cancel doesn't raise
            debouncer.cancel()
            self.assertFalse(debouncer.is_pending())
    
    def test_cleanup(self):
        """Test cleanup."""
        from adapters.qgis.signals.debouncer import Debouncer
        
        debouncer = Debouncer(delay_ms=300)
        debouncer.call(Mock())
        debouncer.cleanup()
        
        self.assertFalse(debouncer.is_pending())


class TestProviderUtils(unittest.TestCase):
    """Test cases for ProviderUtils."""
    
    def test_provider_type_enum(self):
        """Test ProviderType enum values."""
        from infrastructure.utils.provider_utils import ProviderType
        
        self.assertEqual(str(ProviderType.POSTGRESQL), 'postgresql')
        self.assertEqual(str(ProviderType.SPATIALITE), 'spatialite')
        self.assertEqual(str(ProviderType.OGR), 'ogr')
        self.assertEqual(str(ProviderType.MEMORY), 'memory')
        self.assertEqual(str(ProviderType.UNKNOWN), 'unknown')
    
    def test_detect_postgresql(self):
        """Test PostgreSQL detection."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'postgres'
        layer.source.return_value = '/some/source'
        
        result = detect_provider_type(layer)
        
        self.assertEqual(result, ProviderType.POSTGRESQL)
    
    def test_detect_spatialite(self):
        """Test Spatialite detection."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'spatialite'
        layer.source.return_value = '/path/to/db.sqlite'
        
        result = detect_provider_type(layer)
        
        self.assertEqual(result, ProviderType.SPATIALITE)
    
    def test_detect_geopackage_as_spatialite(self):
        """Test GeoPackage detected as Spatialite."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'ogr'
        layer.source.return_value = '/path/to/data.gpkg|layername=test'
        
        result = detect_provider_type(layer)
        
        self.assertEqual(result, ProviderType.SPATIALITE)
    
    def test_detect_ogr(self):
        """Test OGR detection."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'ogr'
        layer.source.return_value = '/path/to/shapefile.shp'
        
        result = detect_provider_type(layer)
        
        self.assertEqual(result, ProviderType.OGR)
    
    def test_detect_memory(self):
        """Test memory layer detection."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'memory'
        layer.source.return_value = ''
        
        result = detect_provider_type(layer)
        
        self.assertEqual(result, ProviderType.MEMORY)
    
    def test_detect_none_layer(self):
        """Test None layer returns UNKNOWN."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        result = detect_provider_type(None)
        
        self.assertEqual(result, ProviderType.UNKNOWN)
    
    def test_detect_invalid_layer(self):
        """Test invalid layer returns UNKNOWN."""
        from infrastructure.utils.provider_utils import detect_provider_type, ProviderType
        
        layer = Mock()
        layer.isValid.return_value = False
        
        result = detect_provider_type(layer)
        
        self.assertEqual(result, ProviderType.UNKNOWN)
    
    def test_is_postgresql(self):
        """Test is_postgresql helper."""
        from infrastructure.utils.provider_utils import is_postgresql
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'postgres'
        layer.source.return_value = ''
        
        self.assertTrue(is_postgresql(layer))
    
    def test_is_spatialite(self):
        """Test is_spatialite helper."""
        from infrastructure.utils.provider_utils import is_spatialite
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'spatialite'
        layer.source.return_value = ''
        
        self.assertTrue(is_spatialite(layer))
    
    def test_is_ogr(self):
        """Test is_ogr helper."""
        from infrastructure.utils.provider_utils import is_ogr
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'ogr'
        layer.source.return_value = '/data.shp'  # Not GPKG
        
        self.assertTrue(is_ogr(layer))
    
    def test_is_memory(self):
        """Test is_memory helper."""
        from infrastructure.utils.provider_utils import is_memory
        
        layer = Mock()
        layer.isValid.return_value = True
        layer.providerType.return_value = 'memory'
        layer.source.return_value = ''
        
        self.assertTrue(is_memory(layer))
    
    def test_is_geopackage(self):
        """Test is_geopackage function."""
        from infrastructure.utils.provider_utils import is_geopackage
        
        gpkg_layer = Mock()
        gpkg_layer.source.return_value = '/path/to/data.gpkg|layername=test'
        
        shp_layer = Mock()
        shp_layer.source.return_value = '/path/to/data.shp'
        
        self.assertTrue(is_geopackage(gpkg_layer))
        self.assertFalse(is_geopackage(shp_layer))
        self.assertFalse(is_geopackage(None))
    
    def test_get_provider_display_name(self):
        """Test display name mapping."""
        from infrastructure.utils.provider_utils import (
            get_provider_display_name, ProviderType
        )
        
        self.assertEqual(get_provider_display_name(ProviderType.POSTGRESQL), "PostgreSQL")
        self.assertEqual(get_provider_display_name(ProviderType.SPATIALITE), "Spatialite")
        self.assertEqual(get_provider_display_name(ProviderType.OGR), "OGR")
        self.assertEqual(get_provider_display_name(ProviderType.MEMORY), "Memory")
        self.assertEqual(get_provider_display_name(ProviderType.UNKNOWN), "Unknown")
    
    def test_get_provider_icon_name(self):
        """Test icon name mapping."""
        from infrastructure.utils.provider_utils import (
            get_provider_icon_name, ProviderType
        )
        
        self.assertEqual(get_provider_icon_name(ProviderType.POSTGRESQL), "postgresql.svg")
        self.assertEqual(get_provider_icon_name(ProviderType.SPATIALITE), "spatialite.svg")
    
    def test_is_backend_available_spatialite(self):
        """Test Spatialite always available."""
        from infrastructure.utils.provider_utils import (
            is_backend_available, ProviderType
        )
        
        self.assertTrue(is_backend_available(ProviderType.SPATIALITE))
        self.assertTrue(is_backend_available(ProviderType.OGR))
        self.assertTrue(is_backend_available(ProviderType.MEMORY))
    
    def test_get_all_provider_types(self):
        """Test getting all provider types."""
        from infrastructure.utils.provider_utils import (
            get_all_provider_types, ProviderType
        )
        
        types = get_all_provider_types()
        
        self.assertIn(ProviderType.POSTGRESQL, types)
        self.assertIn(ProviderType.SPATIALITE, types)
        self.assertIn(ProviderType.OGR, types)
        self.assertIn(ProviderType.MEMORY, types)
        self.assertNotIn(ProviderType.UNKNOWN, types)
    
    def test_get_available_backends(self):
        """Test getting available backends."""
        from infrastructure.utils.provider_utils import get_available_backends
        
        backends = get_available_backends()
        
        # Spatialite, OGR, Memory should always be available
        self.assertGreaterEqual(len(backends), 3)


class TestPackageImports(unittest.TestCase):
    """Test that all packages import correctly."""
    
    def test_import_core(self):
        """Test importing core package."""
        import core
        self.assertIsNotNone(core)
    
    def test_import_adapters(self):
        """Test importing adapters package."""
        import adapters
        self.assertIsNotNone(adapters)
    
    def test_import_ui(self):
        """Test importing ui package."""
        import ui
        self.assertIsNotNone(ui)
    
    def test_import_infrastructure(self):
        """Test importing infrastructure package."""
        import infrastructure
        self.assertIsNotNone(infrastructure)
    
    def test_import_signal_manager(self):
        """Test importing SignalManager."""
        from adapters.qgis.signals import SignalManager
        self.assertIsNotNone(SignalManager)
    
    def test_import_debouncer(self):
        """Test importing Debouncer."""
        from adapters.qgis.signals import Debouncer
        self.assertIsNotNone(Debouncer)
    
    def test_import_provider_utils(self):
        """Test importing provider utilities."""
        from infrastructure.utils import (
            ProviderType,
            detect_provider_type,
            is_postgresql,
            is_spatialite,
        )
        self.assertIsNotNone(ProviderType)
        self.assertIsNotNone(detect_provider_type)


if __name__ == '__main__':
    unittest.main(verbosity=2)
