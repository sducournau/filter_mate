# -*- coding: utf-8 -*-
"""
Integration Test Utilities.

Provides signal spy, custom assertions, and other
testing utilities for FilterMate integration tests.
"""
from .signal_spy import SignalSpy, SignalBlocker, MockSignal, create_mock_signal
from .assertions import (
    assert_filter_result_success,
    assert_filter_result_failure,
    assert_layer_subset_string,
    assert_layer_subset_contains,
    assert_layer_no_subset,
    assert_backend_used,
    assert_optimization_used,
    assert_feature_ids_equal,
    assert_execution_time_within,
    assert_controller_state,
    assert_signal_emitted,
    assert_no_signal_emitted,
    assert_expression_valid
)

__all__ = [
    # Signal utilities
    'SignalSpy',
    'SignalBlocker',
    'MockSignal',
    'create_mock_signal',
    # Assertions
    'assert_filter_result_success',
    'assert_filter_result_failure',
    'assert_layer_subset_string',
    'assert_layer_subset_contains',
    'assert_layer_no_subset',
    'assert_backend_used',
    'assert_optimization_used',
    'assert_feature_ids_equal',
    'assert_execution_time_within',
    'assert_controller_state',
    'assert_signal_emitted',
    'assert_no_signal_emitted',
    'assert_expression_valid'
]
