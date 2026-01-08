# -*- coding: utf-8 -*-
"""
Integration Test Utilities - Custom Assertions - ARCH-049

Custom assertion functions for FilterMate integration testing.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
from typing import Optional, List


class AssertionError(Exception):
    """Custom assertion error with detailed message."""
    pass


def assert_filter_result_success(
    result,
    min_count: Optional[int] = None,
    max_count: Optional[int] = None,
    max_time_ms: Optional[float] = None,
    message: str = ""
) -> None:
    """
    Assert that a filter result is successful.
    
    Args:
        result: Filter result object
        min_count: Minimum expected matched count
        max_count: Maximum expected matched count
        max_time_ms: Maximum expected execution time
        message: Additional error message
        
    Raises:
        AssertionError: If any assertion fails
    """
    prefix = f"{message}: " if message else ""
    
    if not result.success:
        raise AssertionError(
            f"{prefix}Filter result not successful: {result.error_message}"
        )
    
    if min_count is not None and result.matched_count < min_count:
        raise AssertionError(
            f"{prefix}Matched count {result.matched_count} is less than "
            f"minimum {min_count}"
        )
    
    if max_count is not None and result.matched_count > max_count:
        raise AssertionError(
            f"{prefix}Matched count {result.matched_count} is greater than "
            f"maximum {max_count}"
        )
    
    if max_time_ms is not None and result.execution_time_ms > max_time_ms:
        raise AssertionError(
            f"{prefix}Execution time {result.execution_time_ms:.2f}ms exceeds "
            f"maximum {max_time_ms:.2f}ms"
        )


def assert_filter_result_failure(
    result,
    error_contains: Optional[str] = None,
    message: str = ""
) -> None:
    """
    Assert that a filter result failed as expected.
    
    Args:
        result: Filter result object
        error_contains: Expected substring in error message
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    
    if result.success:
        raise AssertionError(
            f"{prefix}Expected filter to fail but it succeeded with "
            f"{result.matched_count} matches"
        )
    
    if error_contains and error_contains not in str(result.error_message):
        raise AssertionError(
            f"{prefix}Error message does not contain '{error_contains}': "
            f"{result.error_message}"
        )


def assert_layer_subset_string(
    layer,
    expected: str,
    message: str = ""
) -> None:
    """
    Assert that a layer has the expected subset string.
    
    Args:
        layer: QGIS vector layer or mock
        expected: Expected subset string
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    actual = layer.subsetString()
    
    if actual != expected:
        raise AssertionError(
            f"{prefix}Layer subset string mismatch.\n"
            f"Expected: '{expected}'\n"
            f"Actual:   '{actual}'"
        )


def assert_layer_subset_contains(
    layer,
    expected_part: str,
    message: str = ""
) -> None:
    """
    Assert that a layer's subset string contains expected text.
    
    Args:
        layer: QGIS vector layer or mock
        expected_part: Expected substring in subset string
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    actual = layer.subsetString()
    
    if expected_part not in actual:
        raise AssertionError(
            f"{prefix}Layer subset string does not contain '{expected_part}'.\n"
            f"Actual: '{actual}'"
        )


def assert_layer_no_subset(layer, message: str = "") -> None:
    """
    Assert that a layer has no subset string (filter cleared).
    
    Args:
        layer: QGIS vector layer or mock
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    actual = layer.subsetString()
    
    if actual:
        raise AssertionError(
            f"{prefix}Expected empty subset string but got: '{actual}'"
        )


def assert_backend_used(
    result,
    expected_backend: str,
    message: str = ""
) -> None:
    """
    Assert that the expected backend was used for execution.
    
    Args:
        result: Filter result with backend info
        expected_backend: Expected backend name
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    actual = getattr(result, 'backend_used', None)
    
    if actual != expected_backend:
        raise AssertionError(
            f"{prefix}Expected backend '{expected_backend}' but "
            f"'{actual}' was used"
        )


def assert_optimization_used(
    result,
    expected: bool = True,
    message: str = ""
) -> None:
    """
    Assert whether optimization was used.
    
    Args:
        result: Filter result with optimization info
        expected: Whether optimization should have been used
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    actual = getattr(result, 'used_optimization', False)
    
    if actual != expected:
        if expected:
            raise AssertionError(f"{prefix}Expected optimization to be used")
        else:
            raise AssertionError(
                f"{prefix}Expected optimization NOT to be used"
            )


def assert_feature_ids_equal(
    actual: List[int],
    expected: List[int],
    message: str = ""
) -> None:
    """
    Assert that two lists of feature IDs are equal (order-independent).
    
    Args:
        actual: Actual feature IDs
        expected: Expected feature IDs
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    
    actual_set = set(actual)
    expected_set = set(expected)
    
    if actual_set != expected_set:
        missing = expected_set - actual_set
        extra = actual_set - expected_set
        
        details = []
        if missing:
            details.append(f"Missing IDs: {sorted(missing)[:10]}...")
        if extra:
            details.append(f"Extra IDs: {sorted(extra)[:10]}...")
        
        raise AssertionError(
            f"{prefix}Feature ID mismatch.\n"
            f"Expected {len(expected)} IDs, got {len(actual)}.\n"
            + "\n".join(details)
        )


def assert_execution_time_within(
    result,
    baseline_ms: float,
    max_regression: float = 0.05,
    message: str = ""
) -> None:
    """
    Assert that execution time is within acceptable regression threshold.
    
    Args:
        result: Filter result with timing
        baseline_ms: Baseline execution time in ms
        max_regression: Maximum allowed regression (default 5%)
        message: Additional error message
        
    Raises:
        AssertionError: If regression exceeds threshold
    """
    prefix = f"{message}: " if message else ""
    actual = result.execution_time_ms
    max_allowed = baseline_ms * (1 + max_regression)
    
    if actual > max_allowed:
        regression = (actual - baseline_ms) / baseline_ms
        raise AssertionError(
            f"{prefix}Performance regression of {regression:.1%} exceeds "
            f"threshold of {max_regression:.1%}.\n"
            f"Baseline: {baseline_ms:.2f}ms, Actual: {actual:.2f}ms"
        )


def assert_controller_state(
    controller,
    is_active: bool,
    message: str = ""
) -> None:
    """
    Assert that a controller is in the expected state.
    
    Args:
        controller: Controller instance
        is_active: Expected active state
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    actual = controller.is_active
    
    if actual != is_active:
        state = "active" if is_active else "inactive"
        raise AssertionError(
            f"{prefix}Expected controller to be {state}"
        )


def assert_signal_emitted(
    spy,
    count: Optional[int] = None,
    min_count: int = 1,
    message: str = ""
) -> None:
    """
    Assert that a signal was emitted.
    
    Args:
        spy: SignalSpy instance
        count: Exact expected emission count (optional)
        min_count: Minimum expected emissions (default 1)
        message: Additional error message
        
    Raises:
        AssertionError: If assertion fails
    """
    prefix = f"{message}: " if message else ""
    
    if count is not None:
        if spy.count != count:
            raise AssertionError(
                f"{prefix}Expected signal to be emitted {count} times "
                f"but was emitted {spy.count} times"
            )
    elif spy.count < min_count:
        raise AssertionError(
            f"{prefix}Expected signal to be emitted at least {min_count} "
            f"times but was emitted {spy.count} times"
        )


def assert_no_signal_emitted(spy, message: str = "") -> None:
    """
    Assert that a signal was not emitted.
    
    Args:
        spy: SignalSpy instance
        message: Additional error message
        
    Raises:
        AssertionError: If signal was emitted
    """
    prefix = f"{message}: " if message else ""
    
    if spy.count > 0:
        raise AssertionError(
            f"{prefix}Expected signal NOT to be emitted but was "
            f"emitted {spy.count} times"
        )


def assert_expression_valid(
    expression: str,
    provider: str = "ogr",
    message: str = ""
) -> None:
    """
    Assert that an expression is syntactically valid.
    
    Args:
        expression: Filter expression
        provider: Provider type for validation
        message: Additional error message
        
    Raises:
        AssertionError: If expression is invalid
    """
    prefix = f"{message}: " if message else ""
    
    # Basic syntax checks
    if not expression or not expression.strip():
        raise AssertionError(f"{prefix}Expression is empty")
    
    # Check balanced quotes
    single_quotes = expression.count("'") - expression.count("\\'")
    if single_quotes % 2 != 0:
        raise AssertionError(f"{prefix}Unbalanced single quotes in expression")
    
    double_quotes = expression.count('"') - expression.count('\\"')
    if double_quotes % 2 != 0:
        raise AssertionError(f"{prefix}Unbalanced double quotes in expression")
    
    # Check balanced parentheses
    parens = 0
    for char in expression:
        if char == '(':
            parens += 1
        elif char == ')':
            parens -= 1
        if parens < 0:
            raise AssertionError(
                f"{prefix}Unbalanced parentheses in expression"
            )
    
    if parens != 0:
        raise AssertionError(f"{prefix}Unbalanced parentheses in expression")
