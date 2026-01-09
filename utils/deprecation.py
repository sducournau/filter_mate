"""
Deprecation utilities for FilterMate.

Provides decorators and utilities for marking deprecated code.
Prepares users for API changes in v4.0.

Story: MIG-088
Phase: 6 - God Class DockWidget Migration
"""

import functools
import warnings
import logging
from typing import Callable, Optional, Dict, Set, Any, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Deprecation Registry
# ─────────────────────────────────────────────────────────────────

@dataclass
class DeprecationInfo:
    """Information about a deprecated item."""
    
    name: str
    version: str
    reason: str
    replacement: Optional[str]
    first_warned: Optional[datetime] = None
    call_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'version': self.version,
            'reason': self.reason,
            'replacement': self.replacement,
            'first_warned': self.first_warned.isoformat() if self.first_warned else None,
            'call_count': self.call_count,
        }


class DeprecationRegistry:
    """
    Registry for tracking deprecated items.
    
    Provides visibility into which deprecated items are still being used,
    useful for migration tracking and cleanup.
    """
    
    _instance: Optional['DeprecationRegistry'] = None
    
    def __new__(cls) -> 'DeprecationRegistry':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._items: Dict[str, DeprecationInfo] = {}
            cls._instance._warned: Set[str] = set()
        return cls._instance
    
    def register(
        self,
        name: str,
        version: str,
        reason: str,
        replacement: Optional[str] = None
    ) -> None:
        """
        Register a deprecated item.
        
        Args:
            name: Fully qualified name of the item
            version: Version when it will be removed
            reason: Why it's deprecated
            replacement: What to use instead
        """
        if name not in self._items:
            self._items[name] = DeprecationInfo(
                name=name,
                version=version,
                reason=reason,
                replacement=replacement,
            )
    
    def mark_warned(self, name: str) -> bool:
        """
        Mark an item as having issued a warning.
        
        Args:
            name: Name of the item
            
        Returns:
            bool: True if this is the first warning
        """
        is_first = name not in self._warned
        self._warned.add(name)
        
        if name in self._items:
            item = self._items[name]
            item.call_count += 1
            if is_first:
                item.first_warned = datetime.now()
        
        return is_first
    
    def has_warned(self, name: str) -> bool:
        """Check if warning has been issued for this item."""
        return name in self._warned
    
    def get_all_deprecated(self) -> List[DeprecationInfo]:
        """Get all registered deprecated items."""
        return list(self._items.values())
    
    def get_warned_items(self) -> List[DeprecationInfo]:
        """Get items that have issued warnings (are being used)."""
        return [
            item for name, item in self._items.items()
            if name in self._warned
        ]
    
    def get_usage_report(self) -> Dict[str, Any]:
        """
        Get a usage report of deprecated items.
        
        Returns:
            dict: Report with deprecated items and usage stats
        """
        return {
            'total_deprecated': len(self._items),
            'total_used': len(self._warned),
            'items': [item.to_dict() for item in self._items.values()],
        }
    
    def reset(self) -> None:
        """Reset the registry (for testing)."""
        self._items.clear()
        self._warned.clear()
    
    @classmethod
    def get_instance(cls) -> 'DeprecationRegistry':
        """Get the singleton instance."""
        return cls()


# ─────────────────────────────────────────────────────────────────
# Decorators
# ─────────────────────────────────────────────────────────────────

def deprecated(
    version: str,
    reason: str,
    replacement: Optional[str] = None,
    emit_once: bool = True
) -> Callable:
    """
    Mark a function or method as deprecated.
    
    Emits a DeprecationWarning on first call (or every call if emit_once=False)
    and logs it. Also registers with the DeprecationRegistry.
    
    Args:
        version: Version when the function will be removed (e.g., "4.0")
        reason: Why it's deprecated (e.g., "Moved to controller")
        replacement: What to use instead (e.g., "FilteringController.apply_filter()")
        emit_once: If True, only emit warning on first call
        
    Returns:
        Callable: The decorator
        
    Usage:
        @deprecated(
            version="4.0",
            reason="Moved to controller",
            replacement="FilteringController.apply_filter()"
        )
        def apply_filter(self, expression):
            return self._filtering_controller.apply_filter(expression)
    """
    def decorator(func: Callable) -> Callable:
        # Get qualified name for registration
        qualname = getattr(func, '__qualname__', func.__name__)
        
        # Register with global registry
        registry = DeprecationRegistry.get_instance()
        registry.register(qualname, version, reason, replacement)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            should_warn = True
            
            if emit_once:
                should_warn = not registry.has_warned(qualname)
            
            if should_warn:
                # Build warning message
                msg = f"{qualname} is deprecated"
                if reason:
                    msg += f": {reason}"
                msg += f". Will be removed in v{version}."
                if replacement:
                    msg += f" Use {replacement} instead."
                
                # Emit warning
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                
                # Log it
                logger.warning(msg)
                
                # Mark as warned
                registry.mark_warned(qualname)
            else:
                # Still increment call count
                if qualname in registry._items:
                    registry._items[qualname].call_count += 1
            
            return func(*args, **kwargs)
        
        # Add metadata for introspection
        wrapper._deprecated_version = version
        wrapper._deprecated_reason = reason
        wrapper._deprecated_replacement = replacement
        wrapper._is_deprecated = True
        
        return wrapper
    return decorator


def deprecated_property(
    version: str,
    reason: str,
    replacement: Optional[str] = None,
    emit_once: bool = True
) -> Callable:
    """
    Mark a property as deprecated.
    
    Similar to @deprecated but works with @property decorator.
    Should be used instead of @property for deprecated properties.
    
    Args:
        version: Version when the property will be removed
        reason: Why it's deprecated
        replacement: What to use instead
        emit_once: If True, only emit warning on first access
        
    Returns:
        Callable: Property decorator
        
    Usage:
        @deprecated_property(
            version="4.0",
            reason="Moved to controller",
            replacement="layer_sync_controller.current_layer"
        )
        def current_layer(self):
            return self._layer_sync_controller.current_layer
    """
    def decorator(func: Callable) -> property:
        qualname = getattr(func, '__qualname__', func.__name__)
        
        # Register with global registry
        registry = DeprecationRegistry.get_instance()
        registry.register(qualname, version, reason, replacement)
        
        @functools.wraps(func)
        def wrapper(self):
            should_warn = True
            
            if emit_once:
                should_warn = not registry.has_warned(qualname)
            
            if should_warn:
                msg = f"{qualname} property is deprecated"
                if reason:
                    msg += f": {reason}"
                msg += f". Will be removed in v{version}."
                if replacement:
                    msg += f" Use {replacement} instead."
                
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                logger.warning(msg)
                registry.mark_warned(qualname)
            else:
                if qualname in registry._items:
                    registry._items[qualname].call_count += 1
            
            return func(self)
        
        wrapper._deprecated_version = version
        wrapper._deprecated_reason = reason
        wrapper._deprecated_replacement = replacement
        wrapper._is_deprecated = True
        
        return property(wrapper)
    return decorator


def deprecated_class(
    version: str,
    reason: str,
    replacement: Optional[str] = None
) -> Callable:
    """
    Mark a class as deprecated.
    
    Emits warning when the class is instantiated.
    
    Args:
        version: Version when the class will be removed
        reason: Why it's deprecated
        replacement: What to use instead
        
    Returns:
        Callable: Class decorator
        
    Usage:
        @deprecated_class(
            version="4.0",
            reason="Use new OrchestratedDockWidget",
            replacement="ui.DockWidgetOrchestrator"
        )
        class LegacyDockWidget:
            pass
    """
    def decorator(cls):
        # Register with global registry
        registry = DeprecationRegistry.get_instance()
        registry.register(cls.__name__, version, reason, replacement)
        
        original_init = cls.__init__
        
        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            should_warn = not registry.has_warned(cls.__name__)
            
            if should_warn:
                msg = f"{cls.__name__} class is deprecated"
                if reason:
                    msg += f": {reason}"
                msg += f". Will be removed in v{version}."
                if replacement:
                    msg += f" Use {replacement} instead."
                
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                logger.warning(msg)
                registry.mark_warned(cls.__name__)
            
            original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        cls._deprecated_version = version
        cls._deprecated_reason = reason
        cls._deprecated_replacement = replacement
        cls._is_deprecated = True
        
        return cls
    return decorator


# ─────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────

def get_deprecation_info(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Get deprecation information from a decorated object.
    
    Args:
        obj: A function, method, property, or class
        
    Returns:
        dict: Deprecation info or None if not deprecated
    """
    if not getattr(obj, '_is_deprecated', False):
        return None
    
    return {
        'version': getattr(obj, '_deprecated_version', None),
        'reason': getattr(obj, '_deprecated_reason', None),
        'replacement': getattr(obj, '_deprecated_replacement', None),
    }


def is_deprecated(obj: Any) -> bool:
    """
    Check if an object is deprecated.
    
    Args:
        obj: A function, method, property, or class
        
    Returns:
        bool: True if deprecated
    """
    return getattr(obj, '_is_deprecated', False)


def print_deprecation_report() -> None:
    """Print a report of deprecated items usage to stdout."""
    registry = DeprecationRegistry.get_instance()
    report = registry.get_usage_report()
    
    print("\n" + "=" * 60)
    print("FilterMate Deprecation Report")
    print("=" * 60)
    print(f"Total deprecated items: {report['total_deprecated']}")
    print(f"Items in use: {report['total_used']}")
    print("-" * 60)
    
    for item in report['items']:
        status = "🔴 IN USE" if item['call_count'] > 0 else "⚪ Not used"
        print(f"\n{status}: {item['name']}")
        print(f"  Version: {item['version']}")
        print(f"  Reason: {item['reason']}")
        if item['replacement']:
            print(f"  Replace with: {item['replacement']}")
        if item['call_count'] > 0:
            print(f"  Call count: {item['call_count']}")
    
    print("\n" + "=" * 60)
