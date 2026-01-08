# -*- coding: utf-8 -*-
"""
Regression Test Configuration

Provides pytest configuration for regression tests.
"""
import pytest


def pytest_configure(config):
    """Register custom markers for regression tests."""
    config.addinivalue_line("markers", "regression: Regression tests for known issues")
