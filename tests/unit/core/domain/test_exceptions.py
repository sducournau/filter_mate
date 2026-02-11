# -*- coding: utf-8 -*-
"""
Tests for FilterMate exception hierarchy.

These are PURE PYTHON tests -- no QGIS dependency.
Tests verify:
    - Exception inheritance tree
    - Error messages
    - Cause preservation (__cause__)
    - SignalStateChangeError special attributes
    - Broad vs. fine-grained catch semantics

Module tested: core.domain.exceptions
"""
import pytest

from core.domain.exceptions import (
    FilterMateError,
    # Filter errors
    FilterError,
    FilterExpressionError,
    FilterTimeoutError,
    FilterCancelledError,
    # Backend errors
    BackendError,
    PostgreSQLError,
    SpatialiteError,
    OGRError,
    BackendNotAvailableError,
    # Layer errors
    LayerError,
    LayerInvalidError,
    LayerNotFoundError,
    CRSMismatchError,
    # Export errors
    ExportError,
    ExportPathError,
    ExportFormatError,
    # Config & signals
    ConfigurationError,
    ExpressionValidationError,
    SignalStateChangeError,
)


# =========================================================================
# Base exception
# =========================================================================

class TestFilterMateError:
    """Tests for the base exception class."""

    def test_is_exception(self):
        assert issubclass(FilterMateError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(FilterMateError):
            raise FilterMateError("base error")

    def test_message_preserved(self):
        try:
            raise FilterMateError("test message")
        except FilterMateError as e:
            assert str(e) == "test message"

    def test_catches_all_filtermate_errors(self):
        """Verify broad catch: FilterMateError catches all subclasses."""
        errors = [
            FilterError("f"),
            BackendError("b"),
            LayerError("l"),
            ExportError("e"),
            ConfigurationError("c"),
            ExpressionValidationError("v"),
            SignalStateChangeError(),
        ]
        for error in errors:
            with pytest.raises(FilterMateError):
                raise error


# =========================================================================
# Filter error hierarchy
# =========================================================================

class TestFilterErrors:
    """Tests for filter-related exception hierarchy."""

    def test_filter_error_inherits_base(self):
        assert issubclass(FilterError, FilterMateError)

    def test_filter_expression_error_inherits_filter(self):
        assert issubclass(FilterExpressionError, FilterError)
        assert issubclass(FilterExpressionError, FilterMateError)

    def test_filter_timeout_error_inherits_filter(self):
        assert issubclass(FilterTimeoutError, FilterError)

    def test_filter_cancelled_error_inherits_filter(self):
        assert issubclass(FilterCancelledError, FilterError)

    def test_catch_filter_error_catches_subtypes(self):
        """FilterError should catch expression, timeout, and cancelled."""
        with pytest.raises(FilterError):
            raise FilterExpressionError("bad expression")
        with pytest.raises(FilterError):
            raise FilterTimeoutError("timed out")
        with pytest.raises(FilterError):
            raise FilterCancelledError("user cancelled")

    def test_filter_expression_error_not_caught_by_backend(self):
        """FilterExpressionError should NOT be caught by BackendError."""
        with pytest.raises(FilterExpressionError):
            try:
                raise FilterExpressionError("parse failure")
            except BackendError:
                pytest.fail("BackendError should not catch FilterExpressionError")


# =========================================================================
# Backend error hierarchy
# =========================================================================

class TestBackendErrors:
    """Tests for backend-related exception hierarchy."""

    def test_backend_error_inherits_base(self):
        assert issubclass(BackendError, FilterMateError)

    def test_postgresql_error_inherits_backend(self):
        assert issubclass(PostgreSQLError, BackendError)
        assert issubclass(PostgreSQLError, FilterMateError)

    def test_spatialite_error_inherits_backend(self):
        assert issubclass(SpatialiteError, BackendError)

    def test_ogr_error_inherits_backend(self):
        assert issubclass(OGRError, BackendError)

    def test_backend_not_available_inherits_backend(self):
        assert issubclass(BackendNotAvailableError, BackendError)

    def test_catch_backend_error_catches_all_backends(self):
        with pytest.raises(BackendError):
            raise PostgreSQLError("pg connection failed")
        with pytest.raises(BackendError):
            raise SpatialiteError("spatialite extension not found")
        with pytest.raises(BackendError):
            raise OGRError("ogr driver error")
        with pytest.raises(BackendError):
            raise BackendNotAvailableError("psycopg2 not installed")

    def test_postgresql_error_not_caught_by_layer(self):
        """PostgreSQLError should NOT be caught by LayerError."""
        with pytest.raises(PostgreSQLError):
            try:
                raise PostgreSQLError("connection refused")
            except LayerError:
                pytest.fail("LayerError should not catch PostgreSQLError")


# =========================================================================
# Layer error hierarchy
# =========================================================================

class TestLayerErrors:
    """Tests for layer-related exception hierarchy."""

    def test_layer_error_inherits_base(self):
        assert issubclass(LayerError, FilterMateError)

    def test_layer_invalid_inherits_layer(self):
        assert issubclass(LayerInvalidError, LayerError)

    def test_layer_not_found_inherits_layer(self):
        assert issubclass(LayerNotFoundError, LayerError)

    def test_crs_mismatch_inherits_layer(self):
        assert issubclass(CRSMismatchError, LayerError)

    def test_catch_layer_error_catches_all_subtypes(self):
        with pytest.raises(LayerError):
            raise LayerInvalidError("layer deleted")
        with pytest.raises(LayerError):
            raise LayerNotFoundError("layer_abc not in project")
        with pytest.raises(LayerError):
            raise CRSMismatchError("EPSG:4326 vs EPSG:3857")


# =========================================================================
# Export error hierarchy
# =========================================================================

class TestExportErrors:
    """Tests for export-related exception hierarchy."""

    def test_export_error_inherits_base(self):
        assert issubclass(ExportError, FilterMateError)

    def test_export_path_error_inherits_export(self):
        assert issubclass(ExportPathError, ExportError)

    def test_export_format_error_inherits_export(self):
        assert issubclass(ExportFormatError, ExportError)

    def test_catch_export_error_catches_subtypes(self):
        with pytest.raises(ExportError):
            raise ExportPathError("/invalid/path is not writable")
        with pytest.raises(ExportError):
            raise ExportFormatError("GML format unsupported")


# =========================================================================
# Configuration & signal errors
# =========================================================================

class TestConfigurationErrors:
    """Tests for configuration and signal exceptions."""

    def test_configuration_error_inherits_base(self):
        assert issubclass(ConfigurationError, FilterMateError)

    def test_expression_validation_inherits_base(self):
        assert issubclass(ExpressionValidationError, FilterMateError)


# =========================================================================
# SignalStateChangeError (special attributes)
# =========================================================================

class TestSignalStateChangeError:
    """Tests for SignalStateChangeError with its custom attributes."""

    def test_inherits_base(self):
        assert issubclass(SignalStateChangeError, FilterMateError)

    def test_default_attributes(self):
        err = SignalStateChangeError()
        assert err.state is None
        assert err.widget_path == []
        # Default message is generated from widget_path
        assert "None" in err.message or "Signal state change failed" in err.message

    def test_custom_attributes(self):
        err = SignalStateChangeError(
            state=True,
            widget_path=["EXPLORING", "IS_SELECTING"],
            message="Cannot disconnect signal",
        )
        assert err.state is True
        assert err.widget_path == ["EXPLORING", "IS_SELECTING"]
        assert err.message == "Cannot disconnect signal"
        assert str(err) == "Cannot disconnect signal"

    def test_generated_message_from_widget_path(self):
        err = SignalStateChangeError(
            state=False,
            widget_path=["ACTION", "FILTER"],
        )
        assert "ACTION" in err.message or "FILTER" in err.message

    def test_catches_as_filtermate_error(self):
        with pytest.raises(FilterMateError):
            raise SignalStateChangeError(message="signal issue")


# =========================================================================
# Cause preservation (__cause__)
# =========================================================================

class TestCausePreservation:
    """Test that exception chaining works correctly with 'from'."""

    def test_cause_preserved_on_raise_from(self):
        original = ValueError("original cause")
        try:
            try:
                raise original
            except ValueError as e:
                raise PostgreSQLError("wrapped") from e
        except PostgreSQLError as pg_err:
            assert pg_err.__cause__ is original
            assert str(pg_err.__cause__) == "original cause"

    def test_nested_cause_chain(self):
        try:
            try:
                try:
                    raise ConnectionError("TCP timeout")
                except ConnectionError as e:
                    raise PostgreSQLError("connection failed") from e
            except PostgreSQLError as e:
                raise FilterError("filter execution failed") from e
        except FilterError as top_err:
            assert isinstance(top_err.__cause__, PostgreSQLError)
            assert isinstance(top_err.__cause__.__cause__, ConnectionError)

    def test_cause_none_by_default(self):
        err = BackendError("no cause")
        assert err.__cause__ is None


# =========================================================================
# __all__ exports
# =========================================================================

class TestModuleExports:
    """Verify that __all__ includes all expected exception classes."""

    def test_all_exceptions_exported(self):
        from core.domain import exceptions
        expected = [
            'FilterMateError',
            'FilterError', 'FilterExpressionError', 'FilterTimeoutError', 'FilterCancelledError',
            'BackendError', 'PostgreSQLError', 'SpatialiteError', 'OGRError', 'BackendNotAvailableError',
            'LayerError', 'LayerInvalidError', 'LayerNotFoundError', 'CRSMismatchError',
            'ExportError', 'ExportPathError', 'ExportFormatError',
            'ConfigurationError', 'ExpressionValidationError', 'SignalStateChangeError',
        ]
        for name in expected:
            assert name in exceptions.__all__, f"{name} not in __all__"
            assert hasattr(exceptions, name), f"{name} not defined in module"
