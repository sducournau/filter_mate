# -*- coding: utf-8 -*-
"""
Unit tests for Dependency Injection Container.

Tests the DI container functionality without QGIS dependencies.
"""
import pytest
from abc import ABC, abstractmethod


class TestContainer:
    """Tests for the Container class."""
    
    @pytest.fixture
    def container(self):
        """Create a fresh container for each test."""
        from infrastructure.di.container import Container
        return Container()
    
    def test_register_and_resolve_singleton(self, container):
        """Test singleton registration and resolution."""
        class MyService:
            def __init__(self):
                self.value = 42
        
        container.register_singleton(
            MyService,
            lambda c: MyService()
        )
        
        # Resolve twice, should get same instance
        instance1 = container.resolve(MyService)
        instance2 = container.resolve(MyService)
        
        assert instance1 is instance2
        assert instance1.value == 42
    
    def test_register_and_resolve_transient(self, container):
        """Test transient registration and resolution."""
        class MyService:
            pass
        
        container.register_transient(
            MyService,
            lambda c: MyService()
        )
        
        # Resolve twice, should get different instances
        instance1 = container.resolve(MyService)
        instance2 = container.resolve(MyService)
        
        assert instance1 is not instance2
    
    def test_register_instance(self, container):
        """Test registering a pre-created instance."""
        class MyService:
            def __init__(self, value):
                self.value = value
        
        existing = MyService(value=100)
        container.register_instance(MyService, existing)
        
        resolved = container.resolve(MyService)
        assert resolved is existing
        assert resolved.value == 100
    
    def test_resolve_unregistered_raises_keyerror(self, container):
        """Test that resolving unregistered service raises KeyError."""
        class NotRegistered:
            pass
        
        with pytest.raises(KeyError) as exc_info:
            container.resolve(NotRegistered)
        
        assert "NotRegistered" in str(exc_info.value)
    
    def test_try_resolve_returns_none_for_unregistered(self, container):
        """Test try_resolve returns None for unregistered services."""
        class NotRegistered:
            pass
        
        result = container.try_resolve(NotRegistered)
        assert result is None
    
    def test_is_registered(self, container):
        """Test is_registered method."""
        class MyService:
            pass
        
        assert not container.is_registered(MyService)
        
        container.register_singleton(MyService, lambda c: MyService())
        
        assert container.is_registered(MyService)
    
    def test_contains_operator(self, container):
        """Test __contains__ operator."""
        class MyService:
            pass
        
        assert MyService not in container
        
        container.register_singleton(MyService, lambda c: MyService())
        
        assert MyService in container
    
    def test_dependency_injection(self, container):
        """Test that dependencies are properly injected."""
        class DependencyA:
            def __init__(self):
                self.name = "A"
        
        class ServiceB:
            def __init__(self, dep_a: DependencyA):
                self.dep_a = dep_a
        
        container.register_singleton(DependencyA, lambda c: DependencyA())
        container.register_singleton(
            ServiceB,
            lambda c: ServiceB(c.resolve(DependencyA))
        )
        
        service = container.resolve(ServiceB)
        assert service.dep_a.name == "A"
    
    def test_fluent_registration(self, container):
        """Test fluent API for registration."""
        class A:
            pass
        class B:
            pass
        class C:
            pass
        
        result = (
            container
            .register_singleton(A, lambda c: A())
            .register_singleton(B, lambda c: B())
            .register_transient(C, lambda c: C())
        )
        
        assert result is container
        assert container.is_registered(A)
        assert container.is_registered(B)
        assert container.is_registered(C)
    
    def test_cleanup_calls_cleanup_method(self, container):
        """Test that cleanup calls cleanup on singleton instances."""
        class MyService:
            def __init__(self):
                self.cleaned_up = False
            
            def cleanup(self):
                self.cleaned_up = True
        
        container.register_singleton(MyService, lambda c: MyService())
        instance = container.resolve(MyService)
        
        assert not instance.cleaned_up
        
        container.cleanup()
        
        assert instance.cleaned_up


class TestScope:
    """Tests for scoped services."""
    
    @pytest.fixture
    def container(self):
        """Create a fresh container for each test."""
        from infrastructure.di.container import Container
        return Container()
    
    def test_scoped_service_same_within_scope(self, container):
        """Test that scoped service returns same instance within scope."""
        class ScopedService:
            pass
        
        container.register_scoped(ScopedService, lambda c: ScopedService())
        
        with container.create_scope() as scope:
            instance1 = scope.resolve(ScopedService)
            instance2 = scope.resolve(ScopedService)
            assert instance1 is instance2
    
    def test_scoped_service_different_between_scopes(self, container):
        """Test that scoped service returns different instances between scopes."""
        class ScopedService:
            pass
        
        container.register_scoped(ScopedService, lambda c: ScopedService())
        
        with container.create_scope() as scope1:
            instance1 = scope1.resolve(ScopedService)
        
        with container.create_scope() as scope2:
            instance2 = scope2.resolve(ScopedService)
        
        assert instance1 is not instance2
    
    def test_scope_can_resolve_singletons(self, container):
        """Test that scope can resolve singleton services from parent."""
        class SingletonService:
            pass
        
        container.register_singleton(SingletonService, lambda c: SingletonService())
        
        parent_instance = container.resolve(SingletonService)
        
        with container.create_scope() as scope:
            scoped_instance = scope.resolve(SingletonService)
            assert scoped_instance is parent_instance
    
    def test_scope_dispose_calls_cleanup(self, container):
        """Test that scope dispose calls cleanup on scoped instances."""
        class ScopedService:
            def __init__(self):
                self.cleaned_up = False
            
            def cleanup(self):
                self.cleaned_up = True
        
        container.register_scoped(ScopedService, lambda c: ScopedService())
        
        with container.create_scope() as scope:
            instance = scope.resolve(ScopedService)
            assert not instance.cleaned_up
        
        # After scope exits, cleanup should have been called
        assert instance.cleaned_up
    
    def test_resolve_scoped_without_scope_raises(self, container):
        """Test that resolving scoped service without scope raises error."""
        class ScopedService:
            pass
        
        container.register_scoped(ScopedService, lambda c: ScopedService())
        
        with pytest.raises(RuntimeError) as exc_info:
            container.resolve(ScopedService)
        
        assert "must be resolved within a scope" in str(exc_info.value)


class TestGlobalContainer:
    """Tests for global container functions."""
    
    def test_get_container_returns_same_instance(self):
        """Test get_container returns the same instance."""
        from infrastructure.di.container import get_container, reset_container
        
        reset_container()
        
        container1 = get_container()
        container2 = get_container()
        
        assert container1 is container2
    
    def test_reset_container_creates_new_instance(self):
        """Test reset_container creates a new container."""
        from infrastructure.di.container import get_container, reset_container
        
        container1 = get_container()
        
        reset_container()
        
        container2 = get_container()
        
        assert container1 is not container2
    
    def test_reset_container_calls_cleanup(self):
        """Test reset_container calls cleanup on old container."""
        from infrastructure.di.container import get_container, reset_container
        
        reset_container()
        container = get_container()
        
        class MyService:
            def __init__(self):
                self.cleaned_up = False
            
            def cleanup(self):
                self.cleaned_up = True
        
        container.register_singleton(MyService, lambda c: MyService())
        instance = container.resolve(MyService)
        
        reset_container()
        
        assert instance.cleaned_up
