#!/usr/bin/env python3
"""
Quick test runner for FilterChain system.

Adds project to PYTHONPATH and runs tests.
"""

import sys
import os

# Add project root to PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now import and run tests
import unittest

# Import test module
from tests.core.filter.test_filter_chain import (
    TestFilterType,
    TestFilter,
    TestFilterChain,
    TestRealWorldScenarios
)

if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFilterType))
    suite.addTests(loader.loadTestsFromTestCase(TestFilter))
    suite.addTests(loader.loadTestsFromTestCase(TestFilterChain))
    suite.addTests(loader.loadTestsFromTestCase(TestRealWorldScenarios))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
