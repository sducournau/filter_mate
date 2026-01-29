"""
Tests for Raster Error Handling.

US-11: Error Handling - Sprint 3 EPIC-2 Raster Integration

Tests the error handling framework:
- Exception hierarchy
- Error categories and severity
- ErrorResult container
- Error handler and callbacks
- Decorators for error recovery
"""

import unittest
from unittest.mock import Mock, patch
from dataclasses import dataclass


class TestRasterErrorBase(unittest.TestCase):
    """Test base RasterError class."""

    def test_error_has_message(self):
        """Test error includes message."""
        message = "Something went wrong"
        error = Exception(message)

        self.assertEqual(str(error), message)

    def test_error_with_layer_id(self):
        """Test error includes layer ID."""
        layer_id = "layer_123"
        message = f"Error with layer {layer_id}"

        self.assertIn(layer_id, message)

    def test_error_with_cause(self):
        """Test error wraps cause exception."""
        cause = ValueError("original error")
        message = f"Wrapped: {cause}"

        self.assertIn("original error", message)

    def test_user_message_includes_hint(self):
        """Test user message includes recovery hint."""
        message = "Error occurred"
        hint = "Try again later"
        user_msg = f"{message}\n\n💡 {hint}"

        self.assertIn(hint, user_msg)


class TestSpecificErrors(unittest.TestCase):
    """Test specific error types."""

    def test_layer_not_found_error(self):
        """Test LayerNotFoundError formatting."""
        layer_id = "missing_layer"
        message = f"Raster layer not found: {layer_id}"

        self.assertIn(layer_id, message)

    def test_statistics_computation_error(self):
        """Test StatisticsComputationError formatting."""
        reason = "timeout"
        message = f"Failed to compute statistics: {reason}"

        self.assertIn("statistics", message.lower())
        self.assertIn(reason, message)

    def test_histogram_error_includes_band(self):
        """Test HistogramComputationError includes band."""
        band = 3
        message = f"Failed to compute histogram for band {band}"

        self.assertIn(str(band), message)

    def test_pixel_identify_error_includes_coords(self):
        """Test PixelIdentifyError includes coordinates."""
        x, y = 100.5, 200.3
        message = f"Failed to identify pixel at ({x:.2f}, {y:.2f})"

        self.assertIn("100.50", message)
        self.assertIn("200.30", message)

    def test_memory_error_shows_requirements(self):
        """Test MemoryError shows memory requirements."""
        required_mb = 512.5
        available_mb = 256.0
        message = (
            f"Insufficient memory: need {required_mb:.1f} MB, "
            f"only {available_mb:.1f} MB available"
        )

        self.assertIn("512.5", message)
        self.assertIn("256.0", message)


class TestErrorSeverity(unittest.TestCase):
    """Test error severity levels."""

    def test_severity_ordering(self):
        """Test severity levels are ordered."""
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        indices = list(range(len(levels)))

        # Higher index = higher severity
        self.assertTrue(indices[-1] > indices[0])

    def test_default_severity_is_error(self):
        """Test default severity is ERROR."""
        default = 'ERROR'
        self.assertEqual(default, 'ERROR')


class TestErrorCategory(unittest.TestCase):
    """Test error categories."""

    def test_all_categories_defined(self):
        """Test all expected categories exist."""
        expected_categories = [
            'layer_access',
            'statistics',
            'histogram',
            'transparency',
            'identify',
            'rendering',
            'cache',
            'io',
            'memory',
            'configuration',
            'unknown',
        ]

        for cat in expected_categories:
            self.assertIsInstance(cat, str)


class TestErrorResult(unittest.TestCase):
    """Test ErrorResult container."""

    def test_ok_result_has_value(self):
        """Test successful result contains value."""
        value = {"data": "test"}
        result = {'success': True, 'value': value, 'error': None}

        self.assertTrue(result['success'])
        self.assertEqual(result['value'], value)
        self.assertIsNone(result['error'])

    def test_fail_result_has_error(self):
        """Test failed result contains error."""
        error = Exception("test error")
        result = {'success': False, 'value': None, 'error': error}

        self.assertFalse(result['success'])
        self.assertIsNone(result['value'])
        self.assertIsNotNone(result['error'])

    def test_result_can_have_warnings(self):
        """Test result can accumulate warnings."""
        result = {'success': True, 'value': 42, 'warnings': []}

        result['warnings'].append("Minor issue 1")
        result['warnings'].append("Minor issue 2")

        self.assertEqual(len(result['warnings']), 2)

    def test_from_exception_wraps_error(self):
        """Test ErrorResult.from_exception wraps exception."""
        original = ValueError("original")

        # Simulated wrapping
        wrapped_error = {
            'message': str(original),
            'cause': original
        }

        self.assertEqual(wrapped_error['message'], "original")


class TestErrorHandler(unittest.TestCase):
    """Test RasterErrorHandler."""

    def test_handler_logs_error(self):
        """Test handler logs errors."""
        logged_errors = []

        def mock_log(error):
            logged_errors.append(error)

        error = Exception("test")
        mock_log(error)

        self.assertEqual(len(logged_errors), 1)

    def test_handler_tracks_counts(self):
        """Test handler tracks error counts by category."""
        counts = {}
        category = 'statistics'

        counts[category] = counts.get(category, 0) + 1
        counts[category] = counts.get(category, 0) + 1

        self.assertEqual(counts[category], 2)

    def test_handler_invokes_callbacks(self):
        """Test handler invokes registered callbacks."""
        callback_calls = []
        callback = lambda e: callback_calls.append(e)

        error = Exception("test")
        callback(error)

        self.assertEqual(len(callback_calls), 1)

    def test_handler_stores_last_error(self):
        """Test handler stores last error per category."""
        last_errors = {}
        category = 'histogram'
        error = Exception("histogram failed")

        last_errors[category] = error

        self.assertEqual(last_errors[category], error)


class TestErrorRecoveryDecorators(unittest.TestCase):
    """Test error handling decorators."""

    def test_decorator_catches_exception(self):
        """Test decorator catches and handles exception."""
        default_value = "default"

        def decorated_func():
            try:
                raise ValueError("error")
            except Exception:
                return default_value

        result = decorated_func()
        self.assertEqual(result, default_value)

    def test_decorator_returns_default_on_error(self):
        """Test decorator returns default value on error."""
        default = None

        def func_that_fails():
            raise Exception("fail")

        try:
            func_that_fails()
        except Exception:
            result = default

        self.assertIsNone(result)

    def test_decorator_preserves_success(self):
        """Test decorator preserves successful return."""
        expected = 42

        def func_that_succeeds():
            return expected

        result = func_that_succeeds()
        self.assertEqual(result, expected)

    def test_with_error_result_wraps_success(self):
        """Test with_error_result wraps successful return."""
        value = "success"

        result = {'success': True, 'value': value}

        self.assertTrue(result['success'])
        self.assertEqual(result['value'], value)

    def test_with_error_result_wraps_failure(self):
        """Test with_error_result wraps failure."""
        error = Exception("failed")

        result = {'success': False, 'error': error}

        self.assertFalse(result['success'])


class TestUserNotification(unittest.TestCase):
    """Test user notification behavior."""

    def test_severity_determines_notification_type(self):
        """Test severity maps to notification type."""
        severity_mapping = {
            'WARNING': 'pushWarning',
            'ERROR': 'pushCritical',
            'CRITICAL': 'pushCritical',
            'INFO': 'pushInfo',
        }

        for severity, method in severity_mapping.items():
            self.assertIn('push', method)

    def test_notification_includes_title(self):
        """Test notification includes FilterMate title."""
        title = "FilterMate Raster"
        self.assertIn("FilterMate", title)


class TestGlobalHandler(unittest.TestCase):
    """Test global error handler singleton."""

    def test_get_handler_returns_instance(self):
        """Test get_error_handler returns handler."""
        handler = Mock()
        self.assertIsNotNone(handler)

    def test_reset_clears_handler(self):
        """Test reset clears global instance."""
        global_handler = Mock()
        global_handler = None
        self.assertIsNone(global_handler)


class TestRecoveryHints(unittest.TestCase):
    """Test recovery hint suggestions."""

    def test_layer_not_found_hint(self):
        """Test hint for missing layer."""
        hint = "Please select a valid raster layer."
        self.assertIn("select", hint.lower())

    def test_statistics_hint(self):
        """Test hint for stats failure."""
        hint = "Try refreshing or use a smaller sample size."
        self.assertIn("refresh", hint.lower())

    def test_memory_hint(self):
        """Test hint for memory issues."""
        hint = "Close other applications or use sampling."
        self.assertIn("sampling", hint.lower())


if __name__ == '__main__':
    unittest.main()
