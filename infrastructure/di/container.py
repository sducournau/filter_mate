# -*- coding: utf-8 -*-
"""
Dependency Injection Container.

Lightweight DI container for managing service lifecycles
and dependency resolution in FilterMate.

Follows the Composition Root pattern where all dependencies
are configured at application startup.

Author: FilterMate Team
Date: January 2026
"""

from typing import TypeVar, Dict, Callable, Optional, Type, Any
from enum import Enum
from dataclasses import dataclass
import logging
import threading

logger = logging.getLogger('FilterMate.DI')

T = TypeVar('T')


class Lifecycle(Enum):
    """Service lifecycle options."""
    TRANSIENT = "transient"    # New instance each time
    SINGLETON = "singleton"    # Single shared instance
    SCOPED = "scoped"          # One instance per scope


@dataclass
class ServiceDescriptor:
    """Describes a registered service."""
    service_type: Type
    factory: Callable[..., Any]
    lifecycle: Lifecycle
    instance: Optional[Any] = None


class Scope:
    """
    Scoped container for request-scoped services.
    
    Usage:
        with container.create_scope() as scope:
            service = scope.resolve(MyService)
    """
    
    def __init__(self, parent: 'Container'):
        self._parent = parent
        self._instances: Dict[Type, Any] = {}
        self._is_disposed = False
    
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service within this scope.
        
        Args:
            service_type: The type to resolve
            
        Returns:
            Service instance
        """
        if self._is_disposed:
            raise RuntimeError("Scope has been disposed")
        
        # Check if we have a scoped instance
        if service_type in self._instances:
            return self._instances[service_type]
        
        descriptor = self._parent._get_descriptor(service_type)
        if descriptor is None:
            raise KeyError(f"Service not registered: {service_type.__name__}")
        
        if descriptor.lifecycle == Lifecycle.SCOPED:
            # Create new instance for this scope
            instance = descriptor.factory(self)
            self._instances[service_type] = instance
            return instance
        else:
            # Delegate to parent for singletons and transients
            return self._parent.resolve(service_type)
    
    def dispose(self) -> None:
        """Clean up scoped instances."""
        self._is_disposed = True
        for instance in self._instances.values():
            if hasattr(instance, 'cleanup'):
                try:
                    instance.cleanup()
                except Exception as e:
                    logger.warning(f"Error during scope cleanup: {e}")
        self._instances.clear()
    
    def __enter__(self) -> 'Scope':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.dispose()


class Container:
    """
    Lightweight dependency injection container.
    
    Supports three lifecycles:
    - TRANSIENT: New instance created each time
    - SINGLETON: Single instance shared across application
    - SCOPED: One instance per scope (e.g., per request)
    
    Example:
        container = Container()
        
        # Register services
        container.register_singleton(
            CachePort,
            lambda c: MemoryCache(max_size=1000)
        )
        container.register_transient(
            BackendPort,
            lambda c: PostgreSQLBackend(c.resolve(ConnectionPool))
        )
        
        # Resolve services
        cache = container.resolve(CachePort)
        backend = container.resolve(BackendPort)
    """
    
    def __init__(self):
        self._descriptors: Dict[Type, ServiceDescriptor] = {}
        self._lock = threading.RLock()
        self._initialized = False
    
    def register(
        self,
        service_type: Type[T],
        factory: Callable[['Container'], T],
        lifecycle: Lifecycle = Lifecycle.TRANSIENT
    ) -> 'Container':
        """
        Register a service with custom lifecycle.
        
        Args:
            service_type: The interface/type to register
            factory: Factory function that creates the instance
            lifecycle: Service lifecycle
            
        Returns:
            Self for fluent chaining
        """
        with self._lock:
            self._descriptors[service_type] = ServiceDescriptor(
                service_type=service_type,
                factory=factory,
                lifecycle=lifecycle
            )
        return self
    
    def register_singleton(
        self,
        service_type: Type[T],
        factory: Callable[['Container'], T]
    ) -> 'Container':
        """
        Register a singleton service.
        
        Args:
            service_type: The interface/type to register
            factory: Factory function that creates the instance
            
        Returns:
            Self for fluent chaining
        """
        return self.register(service_type, factory, Lifecycle.SINGLETON)
    
    def register_transient(
        self,
        service_type: Type[T],
        factory: Callable[['Container'], T]
    ) -> 'Container':
        """
        Register a transient service.
        
        Args:
            service_type: The interface/type to register
            factory: Factory function that creates the instance
            
        Returns:
            Self for fluent chaining
        """
        return self.register(service_type, factory, Lifecycle.TRANSIENT)
    
    def register_scoped(
        self,
        service_type: Type[T],
        factory: Callable[['Container'], T]
    ) -> 'Container':
        """
        Register a scoped service.
        
        Args:
            service_type: The interface/type to register
            factory: Factory function that creates the instance
            
        Returns:
            Self for fluent chaining
        """
        return self.register(service_type, factory, Lifecycle.SCOPED)
    
    def register_instance(
        self,
        service_type: Type[T],
        instance: T
    ) -> 'Container':
        """
        Register an existing instance as singleton.
        
        Args:
            service_type: The interface/type to register
            instance: The pre-created instance
            
        Returns:
            Self for fluent chaining
        """
        with self._lock:
            self._descriptors[service_type] = ServiceDescriptor(
                service_type=service_type,
                factory=lambda _: instance,
                lifecycle=Lifecycle.SINGLETON,
                instance=instance
            )
        return self
    
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service by type.
        
        Args:
            service_type: The type to resolve
            
        Returns:
            Service instance
            
        Raises:
            KeyError: If service is not registered
        """
        descriptor = self._get_descriptor(service_type)
        if descriptor is None:
            raise KeyError(f"Service not registered: {service_type.__name__}")
        
        if descriptor.lifecycle == Lifecycle.SINGLETON:
            with self._lock:
                if descriptor.instance is None:
                    descriptor.instance = descriptor.factory(self)
                return descriptor.instance
        elif descriptor.lifecycle == Lifecycle.TRANSIENT:
            return descriptor.factory(self)
        else:
            # SCOPED - requires a scope
            raise RuntimeError(
                f"Scoped service {service_type.__name__} must be resolved within a scope"
            )
    
    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """
        Try to resolve a service, returning None if not registered.
        
        Args:
            service_type: The type to resolve
            
        Returns:
            Service instance or None
        """
        try:
            return self.resolve(service_type)
        except KeyError:
            return None
    
    def is_registered(self, service_type: Type) -> bool:
        """
        Check if a service is registered.
        
        Args:
            service_type: The type to check
            
        Returns:
            True if registered
        """
        return service_type in self._descriptors
    
    def create_scope(self) -> Scope:
        """
        Create a new scope for scoped services.
        
        Returns:
            New Scope instance
        """
        return Scope(self)
    
    def _get_descriptor(self, service_type: Type) -> Optional[ServiceDescriptor]:
        """Get service descriptor if registered."""
        return self._descriptors.get(service_type)
    
    def cleanup(self) -> None:
        """
        Clean up all singleton instances.
        
        Call this during application shutdown.
        """
        with self._lock:
            for descriptor in self._descriptors.values():
                if descriptor.instance is not None:
                    if hasattr(descriptor.instance, 'cleanup'):
                        try:
                            descriptor.instance.cleanup()
                        except Exception as e:
                            logger.warning(f"Error during cleanup: {e}")
                    descriptor.instance = None
            self._initialized = False
    
    def __contains__(self, service_type: Type) -> bool:
        """Check if service is registered."""
        return self.is_registered(service_type)


# Global container instance
_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    """
    Get the global container instance.
    
    Creates a new container if none exists.
    
    Returns:
        Global Container instance
    """
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
    return _container


def reset_container() -> None:
    """
    Reset the global container.
    
    Cleans up existing container and creates a new one.
    Useful for testing.
    """
    global _container
    with _container_lock:
        if _container is not None:
            _container.cleanup()
            _container = None
