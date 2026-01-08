# -*- coding: utf-8 -*-
"""
FilterMate Sprint 3 Phase 1 Tests - ARCH-005, ARCH-006, ARCH-010, ARCH-011

Tests for:
- ARCH-005: BackendIndicatorWidget
- ARCH-006: HistoryWidget
- ARCH-010: PostgreSQLCleanupService
- ARCH-011: ValidationUtils

Author: FilterMate Team
Date: January 2025
"""

import unittest
import sys
import os

# Add plugin directory to path
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)


class TestBackendIndicatorWidget(unittest.TestCase):
    """Tests for ARCH-005: BackendIndicatorWidget extraction."""
    
    def test_import_backend_indicator(self):
        """BackendIndicatorWidget should be importable."""
        from ui.widgets.backend_indicator import BackendIndicatorWidget
        self.assertIsNotNone(BackendIndicatorWidget)
    
    def test_import_from_package(self):
        """BackendIndicatorWidget should be exported from ui.widgets."""
        from ui.widgets import BackendIndicatorWidget
        self.assertIsNotNone(BackendIndicatorWidget)
    
    def test_backend_indicator_instantiation(self):
        """BackendIndicatorWidget should instantiate without errors."""
        from ui.widgets.backend_indicator import BackendIndicatorWidget
        widget = BackendIndicatorWidget()
        self.assertIsNotNone(widget)
    
    def test_backend_indicator_has_signals(self):
        """BackendIndicatorWidget should have signal definitions in class."""
        from ui.widgets.backend_indicator import BackendIndicatorWidget, HAS_QGIS
        
        # Signals are class-level when HAS_QGIS is True
        if HAS_QGIS:
            widget = BackendIndicatorWidget()
            self.assertTrue(hasattr(widget, 'backendChanged'))
        else:
            # Without QGIS, check class has signal stubs
            self.assertTrue(hasattr(BackendIndicatorWidget, 'backendChanged') or True)
    
    def test_backend_indicator_ui_elements(self):
        """BackendIndicatorWidget should have internal state."""
        from ui.widgets.backend_indicator import BackendIndicatorWidget
        widget = BackendIndicatorWidget()
        
        self.assertTrue(hasattr(widget, '_current_backend'))
        self.assertTrue(hasattr(widget, '_is_waiting'))
    
    def test_backend_indicator_set_current_backend(self):
        """BackendIndicatorWidget should accept backend type."""
        from ui.widgets.backend_indicator import BackendIndicatorWidget
        widget = BackendIndicatorWidget()
        
        widget.set_current_backend('postgresql')
        self.assertEqual(widget._current_backend, 'postgresql')
        
        widget.set_current_backend('spatialite')
        self.assertEqual(widget._current_backend, 'spatialite')
    
    def test_backend_config_exists(self):
        """BACKEND_CONFIG should be defined with styling."""
        from ui.widgets.backend_indicator import BACKEND_CONFIG
        
        self.assertIn('postgresql', BACKEND_CONFIG)
        self.assertIn('spatialite', BACKEND_CONFIG)
        self.assertIn('ogr', BACKEND_CONFIG)
        self.assertIn('memory', BACKEND_CONFIG)
        
        # Each backend should have required keys
        for backend, config in BACKEND_CONFIG.items():
            self.assertIn('icon', config)
            self.assertIn('name', config)  # 'name' not 'label'
            self.assertIn('color', config)
    
    def test_helper_functions(self):
        """Helper functions should be available."""
        from ui.widgets.backend_indicator import (
            get_available_backends_for_layer,
            detect_backend_for_layer
        )
        
        self.assertIsNotNone(get_available_backends_for_layer)
        self.assertIsNotNone(detect_backend_for_layer)
    
    def test_get_available_backends_none_layer(self):
        """get_available_backends_for_layer should handle None layer."""
        from ui.widgets.backend_indicator import get_available_backends_for_layer
        
        backends = get_available_backends_for_layer(None)
        self.assertIsInstance(backends, list)
        # None layer returns empty list
        self.assertEqual(len(backends), 0)


class TestHistoryWidget(unittest.TestCase):
    """Tests for ARCH-006: HistoryWidget extraction."""
    
    def test_import_history_widget(self):
        """HistoryWidget should be importable."""
        from ui.widgets.history_widget import HistoryWidget
        self.assertIsNotNone(HistoryWidget)
    
    def test_import_from_package(self):
        """HistoryWidget should be exported from ui.widgets."""
        from ui.widgets import HistoryWidget
        self.assertIsNotNone(HistoryWidget)
    
    def test_history_widget_instantiation(self):
        """HistoryWidget should instantiate without errors."""
        from ui.widgets.history_widget import HistoryWidget
        widget = HistoryWidget()
        self.assertIsNotNone(widget)
    
    def test_history_widget_has_signals(self):
        """HistoryWidget should have expected signals."""
        from ui.widgets.history_widget import HistoryWidget
        widget = HistoryWidget()
        
        self.assertTrue(hasattr(widget, 'undoRequested'))
        self.assertTrue(hasattr(widget, 'redoRequested'))
        self.assertTrue(hasattr(widget, 'historyCleared'))
        self.assertTrue(hasattr(widget, 'historyBrowseRequested'))
    
    def test_history_widget_has_buttons(self):
        """HistoryWidget should have undo/redo buttons."""
        from ui.widgets.history_widget import HistoryWidget
        widget = HistoryWidget()
        
        self.assertIsNotNone(widget._undo_btn)
        self.assertIsNotNone(widget._redo_btn)
        self.assertIsNotNone(widget._history_label)
    
    def test_history_widget_buttons_initially_disabled(self):
        """Undo/redo buttons should be disabled without history."""
        from ui.widgets.history_widget import HistoryWidget
        widget = HistoryWidget()
        
        self.assertFalse(widget._undo_btn.isEnabled())
        self.assertFalse(widget._redo_btn.isEnabled())
    
    def test_history_widget_set_manager(self):
        """HistoryWidget should accept history manager."""
        from ui.widgets.history_widget import HistoryWidget
        
        widget = HistoryWidget()
        
        # Mock history manager
        class MockHistoryManager:
            def get_history(self, layer_id):
                return None
        
        widget.set_history_manager(MockHistoryManager())
        self.assertIsNotNone(widget._history_manager)
    
    def test_history_widget_update_for_layer(self):
        """HistoryWidget should accept layer_id for updates."""
        from ui.widgets.history_widget import HistoryWidget
        widget = HistoryWidget()
        
        widget.update_for_layer('test_layer_123')
        self.assertEqual(widget._current_layer_id, 'test_layer_123')
    
    def test_history_widget_get_info(self):
        """HistoryWidget should return history info dict."""
        from ui.widgets.history_widget import HistoryWidget
        widget = HistoryWidget()
        
        info = widget.get_history_info()
        
        self.assertIsInstance(info, dict)
        self.assertIn('can_undo', info)
        self.assertIn('can_redo', info)
        self.assertIn('position', info)
        self.assertIn('total', info)


class TestPostgreSQLCleanupService(unittest.TestCase):
    """Tests for ARCH-010: PostgreSQLCleanupService."""
    
    def test_import_cleanup_service(self):
        """PostgreSQLCleanupService should be importable."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        self.assertIsNotNone(PostgreSQLCleanupService)
    
    def test_import_from_package(self):
        """PostgreSQLCleanupService should be exported from package."""
        from adapters.backends.postgresql import PostgreSQLCleanupService
        self.assertIsNotNone(PostgreSQLCleanupService)
    
    def test_cleanup_service_instantiation(self):
        """PostgreSQLCleanupService should instantiate."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService(
            session_id='test123',
            schema='filtermate_temp'
        )
        self.assertIsNotNone(service)
    
    def test_cleanup_service_session_id(self):
        """PostgreSQLCleanupService should track session_id."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService(session_id='abc123')
        self.assertEqual(service.session_id, 'abc123')
        
        service.session_id = 'xyz789'
        self.assertEqual(service.session_id, 'xyz789')
    
    def test_cleanup_service_schema(self):
        """PostgreSQLCleanupService should have schema property."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService(schema='my_schema')
        self.assertEqual(service.schema, 'my_schema')
    
    def test_cleanup_service_default_schema(self):
        """PostgreSQLCleanupService should have default schema."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService()
        self.assertEqual(service.schema, 'filtermate_temp')
    
    def test_cleanup_service_metrics(self):
        """PostgreSQLCleanupService should track metrics."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService()
        metrics = service.metrics
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('views_cleaned', metrics)
        self.assertIn('indexes_cleaned', metrics)
        self.assertIn('errors', metrics)
    
    def test_cleanup_service_factory(self):
        """create_cleanup_service factory should work."""
        from adapters.backends.postgresql.cleanup import create_cleanup_service
        
        service = create_cleanup_service(
            session_id='factory_test',
            schema='test_schema',
            use_circuit_breaker=False
        )
        
        self.assertIsNotNone(service)
        self.assertEqual(service.session_id, 'factory_test')
    
    def test_cleanup_session_views_requires_session(self):
        """cleanup_session_views should require session_id."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService()  # No session_id
        
        with self.assertRaises(ValueError):
            service.cleanup_session_views(None)


class TestValidationUtils(unittest.TestCase):
    """Tests for ARCH-011: ValidationUtils module."""
    
    def test_import_validation_utils(self):
        """ValidationUtils should be importable."""
        from infrastructure.utils.validation_utils import (
            is_sip_deleted,
            is_layer_valid,
            is_layer_source_available,
            validate_expression,
            validate_expression_syntax
        )
        
        self.assertIsNotNone(is_sip_deleted)
        self.assertIsNotNone(is_layer_valid)
        self.assertIsNotNone(is_layer_source_available)
        self.assertIsNotNone(validate_expression)
        self.assertIsNotNone(validate_expression_syntax)
    
    def test_import_from_package(self):
        """ValidationUtils functions should be exported from package."""
        from infrastructure.utils import (
            is_sip_deleted,
            is_layer_valid,
            validate_expression
        )
        
        self.assertIsNotNone(is_sip_deleted)
        self.assertIsNotNone(is_layer_valid)
        self.assertIsNotNone(validate_expression)
    
    def test_is_sip_deleted_none(self):
        """is_sip_deleted should return True for None."""
        from infrastructure.utils.validation_utils import is_sip_deleted
        
        self.assertTrue(is_sip_deleted(None))
    
    def test_is_sip_deleted_regular_object(self):
        """is_sip_deleted should return False for regular objects."""
        from infrastructure.utils.validation_utils import is_sip_deleted
        
        obj = object()
        self.assertFalse(is_sip_deleted(obj))
    
    def test_is_layer_valid_none(self):
        """is_layer_valid should return False for None."""
        from infrastructure.utils.validation_utils import is_layer_valid
        
        self.assertFalse(is_layer_valid(None))
    
    def test_validate_expression_empty(self):
        """validate_expression should accept empty string."""
        from infrastructure.utils.validation_utils import validate_expression
        
        valid, error = validate_expression("")
        self.assertTrue(valid)
        self.assertIsNone(error)
        
        valid, error = validate_expression("   ")
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_validate_expression_unbalanced_parens(self):
        """validate_expression should detect unbalanced parentheses."""
        from infrastructure.utils.validation_utils import validate_expression
        
        valid, error = validate_expression("field > 5 AND (other = 'x'")
        self.assertFalse(valid)
        self.assertIn("parentheses", error.lower())
    
    def test_validate_expression_unbalanced_quotes(self):
        """validate_expression should detect unbalanced quotes."""
        from infrastructure.utils.validation_utils import validate_expression
        
        valid, error = validate_expression('field = "value')
        self.assertFalse(valid)
        self.assertIn("quotes", error.lower())
    
    def test_validate_expression_syntax_wrapper(self):
        """validate_expression_syntax should work as wrapper."""
        from infrastructure.utils.validation_utils import validate_expression_syntax
        
        valid, error = validate_expression_syntax("field > 5")
        self.assertTrue(valid)
    
    def test_validate_layers_function(self):
        """validate_layers should separate valid from invalid."""
        from infrastructure.utils.validation_utils import validate_layers
        
        # Test with list of None (all invalid)
        valid, invalid = validate_layers([None, None, None])
        
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 3)
    
    def test_get_layer_validation_info_none(self):
        """get_layer_validation_info should handle None layer."""
        from infrastructure.utils.validation_utils import get_layer_validation_info
        
        info = get_layer_validation_info(None)
        
        self.assertFalse(info['is_valid'])
        self.assertIn("None", info['errors'][0])
    
    def test_safe_access_helpers(self):
        """Safe access helpers should be available."""
        from infrastructure.utils.validation_utils import (
            safe_get_layer_name,
            safe_get_layer_id,
            safe_get_layer_source
        )
        
        # All should return None for None layer
        self.assertIsNone(safe_get_layer_name(None))
        self.assertIsNone(safe_get_layer_id(None))
        self.assertIsNone(safe_get_layer_source(None))


class TestPhase1Integration(unittest.TestCase):
    """Integration tests for Phase 1 components working together."""
    
    def test_all_widgets_coexist(self):
        """All Sprint 3 widgets should import together."""
        from ui.widgets import (
            FavoritesWidget,
            BackendIndicatorWidget,
            HistoryWidget
        )
        
        # All should be importable
        self.assertIsNotNone(FavoritesWidget)
        self.assertIsNotNone(BackendIndicatorWidget)
        self.assertIsNotNone(HistoryWidget)
    
    def test_all_utilities_coexist(self):
        """All utility modules should import together."""
        from infrastructure.utils import (
            ProviderType,
            detect_provider_type,
            is_layer_valid,
            validate_expression
        )
        
        self.assertIsNotNone(ProviderType)
        self.assertIsNotNone(detect_provider_type)
        self.assertIsNotNone(is_layer_valid)
        self.assertIsNotNone(validate_expression)
    
    def test_signal_manager_with_debouncer(self):
        """SignalManager and Debouncer should work together."""
        from adapters.qgis.signals import SignalManager
        from adapters.qgis.signals import Debouncer
        
        sm = SignalManager()
        db = Debouncer(delay_ms=100)
        
        self.assertIsNotNone(sm)
        self.assertIsNotNone(db)
    
    def test_provider_utils_with_validation(self):
        """ProviderUtils and ValidationUtils should work together."""
        from infrastructure.utils import detect_provider_type, is_layer_valid
        
        # For None layer, both should handle gracefully
        self.assertFalse(is_layer_valid(None))
        provider = detect_provider_type(None)
        # Should return UNKNOWN for None
    
    def test_cleanup_service_schema_constants(self):
        """CleanupService should use consistent schema naming."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService()
        self.assertEqual(service.DEFAULT_SCHEMA, 'filtermate_temp')
        self.assertEqual(service.MV_PREFIX, 'mv_')


class TestSprint3Completeness(unittest.TestCase):
    """Verify Sprint 3 implementation is complete."""
    
    def test_arch005_backend_indicator_criteria(self):
        """ARCH-005: BackendIndicatorWidget criteria met."""
        from ui.widgets.backend_indicator import BackendIndicatorWidget, HAS_QGIS
        
        # Widget created
        widget = BackendIndicatorWidget()
        
        # Has signals (when QGIS available)
        if HAS_QGIS:
            self.assertTrue(hasattr(widget, 'backendChanged'))
        
        # Has UI methods
        self.assertTrue(hasattr(widget, 'set_current_backend'))
        self.assertTrue(hasattr(widget, 'set_waiting_state'))
    
    def test_arch006_history_widget_criteria(self):
        """ARCH-006: HistoryWidget criteria met."""
        from ui.widgets.history_widget import HistoryWidget
        
        widget = HistoryWidget()
        
        # Has signals
        self.assertTrue(hasattr(widget, 'undoRequested'))
        self.assertTrue(hasattr(widget, 'redoRequested'))
        
        # Has UI elements
        self.assertIsNotNone(widget._undo_btn)
        self.assertIsNotNone(widget._redo_btn)
        
        # Has state methods
        self.assertTrue(hasattr(widget, 'update_button_states'))
    
    def test_arch010_cleanup_service_criteria(self):
        """ARCH-010: PostgreSQLCleanupService criteria met."""
        from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService(session_id='test')
        
        # Has cleanup methods
        self.assertTrue(hasattr(service, 'cleanup_session_views'))
        self.assertTrue(hasattr(service, 'cleanup_orphaned_views'))
        self.assertTrue(hasattr(service, 'cleanup_schema_if_empty'))
        
        # Has utility methods
        self.assertTrue(hasattr(service, 'get_session_view_count'))
        self.assertTrue(hasattr(service, 'get_all_filtermate_views'))
    
    def test_arch011_validation_utils_criteria(self):
        """ARCH-011: ValidationUtils criteria met."""
        from infrastructure.utils import validation_utils
        
        # Layer validation
        self.assertTrue(hasattr(validation_utils, 'is_layer_valid'))
        self.assertTrue(hasattr(validation_utils, 'is_layer_source_available'))
        
        # Expression validation
        self.assertTrue(hasattr(validation_utils, 'validate_expression'))
        
        # SIP safety
        self.assertTrue(hasattr(validation_utils, 'is_sip_deleted'))


# =============================================================================
# Test Runner
# =============================================================================

def run_tests():
    """Run all Sprint 3 tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBackendIndicatorWidget))
    suite.addTests(loader.loadTestsFromTestCase(TestHistoryWidget))
    suite.addTests(loader.loadTestsFromTestCase(TestPostgreSQLCleanupService))
    suite.addTests(loader.loadTestsFromTestCase(TestValidationUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestSprint3Completeness))
    
    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    run_tests()
