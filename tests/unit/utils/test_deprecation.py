"""
Tests for deprecation utilities.

Story: MIG-088
Phase: 6 - God Class DockWidget Migration
"""

import pytest
import warnings
import sys
from pathlib import Path
from unittest.mock import patch

# Add plugin path
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

from utils.deprecation import (
    deprecated,
    deprecated_property,
    deprecated_class,
    DeprecationRegistry,
    DeprecationInfo,
    get_deprecation_info,
    is_deprecated,
)


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the deprecation registry before each test."""
    registry = DeprecationRegistry.get_instance()
    registry.reset()
    yield
    registry.reset()


# ─────────────────────────────────────────────────────────────────
# Test DeprecationInfo
# ─────────────────────────────────────────────────────────────────

class TestDeprecationInfo:
    """Tests for DeprecationInfo dataclass."""
    
    def test_init(self):
        """Test initialization."""
        info = DeprecationInfo(
            name='test.func',
            version='4.0',
            reason='Testing',
            replacement='new.func'
        )
        
        assert info.name == 'test.func'
        assert info.version == '4.0'
        assert info.reason == 'Testing'
        assert info.replacement == 'new.func'
        assert info.first_warned is None
        assert info.call_count == 0
    
    def test_to_dict(self):
        """Test to_dict method."""
        info = DeprecationInfo(
            name='test.func',
            version='4.0',
            reason='Testing',
            replacement='new.func',
            call_count=5
        )
        
        result = info.to_dict()
        
        assert result['name'] == 'test.func'
        assert result['version'] == '4.0'
        assert result['call_count'] == 5


# ─────────────────────────────────────────────────────────────────
# Test DeprecationRegistry
# ─────────────────────────────────────────────────────────────────

class TestDeprecationRegistry:
    """Tests for DeprecationRegistry."""
    
    def test_singleton(self):
        """Test singleton pattern."""
        reg1 = DeprecationRegistry.get_instance()
        reg2 = DeprecationRegistry.get_instance()
        
        assert reg1 is reg2
    
    def test_register(self):
        """Test registering a deprecated item."""
        registry = DeprecationRegistry.get_instance()
        
        registry.register(
            name='test.func',
            version='4.0',
            reason='Testing',
            replacement='new.func'
        )
        
        items = registry.get_all_deprecated()
        assert len(items) == 1
        assert items[0].name == 'test.func'
    
    def test_register_duplicate(self):
        """Test registering same item twice."""
        registry = DeprecationRegistry.get_instance()
        
        registry.register('test.func', '4.0', 'First', None)
        registry.register('test.func', '4.0', 'Second', None)
        
        items = registry.get_all_deprecated()
        assert len(items) == 1
        assert items[0].reason == 'First'  # First registration wins
    
    def test_mark_warned(self):
        """Test marking an item as warned."""
        registry = DeprecationRegistry.get_instance()
        registry.register('test.func', '4.0', 'Testing', None)
        
        is_first = registry.mark_warned('test.func')
        
        assert is_first is True
        assert registry.has_warned('test.func')
    
    def test_mark_warned_twice(self):
        """Test marking warned twice returns False second time."""
        registry = DeprecationRegistry.get_instance()
        registry.register('test.func', '4.0', 'Testing', None)
        
        is_first_1 = registry.mark_warned('test.func')
        is_first_2 = registry.mark_warned('test.func')
        
        assert is_first_1 is True
        assert is_first_2 is False
    
    def test_get_warned_items(self):
        """Test getting warned items."""
        registry = DeprecationRegistry.get_instance()
        registry.register('used.func', '4.0', 'Testing', None)
        registry.register('unused.func', '4.0', 'Testing', None)
        
        registry.mark_warned('used.func')
        
        warned = registry.get_warned_items()
        
        assert len(warned) == 1
        assert warned[0].name == 'used.func'
    
    def test_get_usage_report(self):
        """Test getting usage report."""
        registry = DeprecationRegistry.get_instance()
        registry.register('func1', '4.0', 'Testing', None)
        registry.register('func2', '4.0', 'Testing', None)
        registry.mark_warned('func1')
        
        report = registry.get_usage_report()
        
        assert report['total_deprecated'] == 2
        assert report['total_used'] == 1
        assert len(report['items']) == 2
    
    def test_reset(self):
        """Test resetting the registry."""
        registry = DeprecationRegistry.get_instance()
        registry.register('test.func', '4.0', 'Testing', None)
        registry.mark_warned('test.func')
        
        registry.reset()
        
        assert len(registry.get_all_deprecated()) == 0
        assert not registry.has_warned('test.func')


# ─────────────────────────────────────────────────────────────────
# Test @deprecated Decorator
# ─────────────────────────────────────────────────────────────────

class TestDeprecatedDecorator:
    """Tests for @deprecated decorator."""
    
    def test_warning_emitted(self):
        """Test that deprecation warning is emitted."""
        @deprecated(version='4.0', reason='Testing', replacement='new_func')
        def old_func():
            return 'result'
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert 'old_func' in str(w[0].message)
            assert 'v4.0' in str(w[0].message)
            assert 'new_func' in str(w[0].message)
            assert result == 'result'
    
    def test_warning_once(self):
        """Test that warning is only emitted once by default."""
        @deprecated(version='4.0', reason='Testing')
        def old_func():
            return 'result'
        
        # First call - warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()
            assert len(w) == 1
        
        # Second call - no warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()
            assert len(w) == 0
    
    def test_warning_every_call(self):
        """Test emit_once=False emits every call."""
        @deprecated(version='4.0', reason='Testing', emit_once=False)
        def old_func():
            return 'result'
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()
            old_func()
            
            assert len(w) == 2
    
    def test_function_still_works(self):
        """Test that decorated function still works."""
        @deprecated(version='4.0', reason='Testing')
        def add(a, b):
            return a + b
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = add(2, 3)
        
        assert result == 5
    
    def test_preserves_docstring(self):
        """Test that docstring is preserved."""
        @deprecated(version='4.0', reason='Testing')
        def documented_func():
            """This is the docstring."""
            pass
        
        assert documented_func.__doc__ == "This is the docstring."
    
    def test_preserves_name(self):
        """Test that function name is preserved."""
        @deprecated(version='4.0', reason='Testing')
        def my_function():
            pass
        
        assert my_function.__name__ == 'my_function'
    
    def test_metadata_added(self):
        """Test that deprecation metadata is added."""
        @deprecated(version='4.0', reason='Testing', replacement='new')
        def old_func():
            pass
        
        assert old_func._is_deprecated is True
        assert old_func._deprecated_version == '4.0'
        assert old_func._deprecated_reason == 'Testing'
        assert old_func._deprecated_replacement == 'new'
    
    def test_registered_in_registry(self):
        """Test that decorated function is registered."""
        @deprecated(version='4.0', reason='Testing')
        def registered_func():
            pass
        
        registry = DeprecationRegistry.get_instance()
        items = registry.get_all_deprecated()
        
        assert any('registered_func' in item.name for item in items)


# ─────────────────────────────────────────────────────────────────
# Test @deprecated_property Decorator
# ─────────────────────────────────────────────────────────────────

class TestDeprecatedProperty:
    """Tests for @deprecated_property decorator."""
    
    def test_warning_emitted(self):
        """Test that deprecation warning is emitted."""
        class MyClass:
            @deprecated_property(version='4.0', reason='Testing')
            def old_prop(self):
                return 'value'
        
        obj = MyClass()
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = obj.old_prop
            
            assert len(w) == 1
            assert 'old_prop' in str(w[0].message)
            assert result == 'value'
    
    def test_warning_once(self):
        """Test that property warning is only emitted once."""
        class MyClass:
            @deprecated_property(version='4.0', reason='Testing')
            def old_prop(self):
                return 'value'
        
        obj = MyClass()
        
        # First access
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = obj.old_prop
            assert len(w) == 1
        
        # Second access - no warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = obj.old_prop
            assert len(w) == 0
    
    def test_returns_value(self):
        """Test that property returns correct value."""
        class MyClass:
            @deprecated_property(version='4.0', reason='Testing')
            def my_value(self):
                return 42
        
        obj = MyClass()
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert obj.my_value == 42


# ─────────────────────────────────────────────────────────────────
# Test @deprecated_class Decorator
# ─────────────────────────────────────────────────────────────────

class TestDeprecatedClass:
    """Tests for @deprecated_class decorator."""
    
    def test_warning_on_instantiation(self):
        """Test that warning is emitted on instantiation."""
        @deprecated_class(version='4.0', reason='Testing', replacement='NewClass')
        class OldClass:
            pass
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            obj = OldClass()
            
            assert len(w) == 1
            assert 'OldClass' in str(w[0].message)
            assert 'NewClass' in str(w[0].message)
    
    def test_class_still_works(self):
        """Test that class still functions."""
        @deprecated_class(version='4.0', reason='Testing')
        class OldClass:
            def __init__(self, value):
                self.value = value
            
            def get_value(self):
                return self.value
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            obj = OldClass(42)
        
        assert obj.value == 42
        assert obj.get_value() == 42
    
    def test_metadata_added(self):
        """Test that class has deprecation metadata."""
        @deprecated_class(version='4.0', reason='Testing')
        class OldClass:
            pass
        
        assert OldClass._is_deprecated is True
        assert OldClass._deprecated_version == '4.0'


# ─────────────────────────────────────────────────────────────────
# Test Utility Functions
# ─────────────────────────────────────────────────────────────────

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_get_deprecation_info(self):
        """Test get_deprecation_info function."""
        @deprecated(version='4.0', reason='Testing', replacement='new')
        def old_func():
            pass
        
        info = get_deprecation_info(old_func)
        
        assert info is not None
        assert info['version'] == '4.0'
        assert info['reason'] == 'Testing'
        assert info['replacement'] == 'new'
    
    def test_get_deprecation_info_not_deprecated(self):
        """Test get_deprecation_info on non-deprecated object."""
        def normal_func():
            pass
        
        info = get_deprecation_info(normal_func)
        
        assert info is None
    
    def test_is_deprecated_true(self):
        """Test is_deprecated returns True for deprecated."""
        @deprecated(version='4.0', reason='Testing')
        def old_func():
            pass
        
        assert is_deprecated(old_func) is True
    
    def test_is_deprecated_false(self):
        """Test is_deprecated returns False for non-deprecated."""
        def normal_func():
            pass
        
        assert is_deprecated(normal_func) is False


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestDeprecationIntegration:
    """Integration tests for deprecation system."""
    
    def test_multiple_deprecated_methods(self):
        """Test class with multiple deprecated methods."""
        class LegacyClass:
            @deprecated(version='4.0', reason='Use new_method_a')
            def old_method_a(self):
                return 'a'
            
            @deprecated(version='4.0', reason='Use new_method_b')
            def old_method_b(self):
                return 'b'
        
        obj = LegacyClass()
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            obj.old_method_a()
            obj.old_method_b()
            
            assert len(w) == 2
    
    def test_call_count_tracking(self):
        """Test that call count is tracked."""
        @deprecated(version='4.0', reason='Testing')
        def tracked_func():
            pass
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tracked_func()
            tracked_func()
            tracked_func()
        
        registry = DeprecationRegistry.get_instance()
        items = registry.get_warned_items()
        
        # Find our function
        item = next(i for i in items if 'tracked_func' in i.name)
        assert item.call_count == 3
    
    def test_usage_report(self):
        """Test generating usage report."""
        @deprecated(version='4.0', reason='Testing')
        def used_func():
            pass
        
        @deprecated(version='4.0', reason='Testing')
        def unused_func():
            pass
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            used_func()
        
        registry = DeprecationRegistry.get_instance()
        report = registry.get_usage_report()
        
        assert report['total_deprecated'] == 2
        assert report['total_used'] == 1
