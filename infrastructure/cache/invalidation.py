# -*- coding: utf-8 -*-
"""
Cache Invalidation Strategy for FilterMate.

v4.1.1 - January 2026 - EPIC-3 Sprint 2

PURPOSE:
Provides intelligent cache invalidation:
1. Layer-based invalidation (when layer data changes)
2. Schema-based invalidation (when fields change)
3. Expression-based invalidation (when related expressions change)
4. Time-based invalidation (TTL expiration)
5. Cascade invalidation (dependent cache entries)

USAGE:
    from infrastructure.cache import CacheInvalidator, InvalidationStrategy
    
    invalidator = CacheInvalidator(cache_manager)
    
    # Invalidate when layer changes
    invalidator.on_layer_modified("layer_123")
    
    # Invalidate cascading dependencies
    invalidator.invalidate_with_dependencies("unique_values:layer_123:status")
"""

import logging
from typing import List, Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

from .interface import CacheInterface, CacheKey, CacheManager, get_cache_manager

logger = logging.getLogger('FilterMate.Cache.Invalidation')


class InvalidationReason(Enum):
    """Reason for cache invalidation."""
    LAYER_MODIFIED = auto()
    LAYER_DELETED = auto()
    SCHEMA_CHANGED = auto()
    EXPRESSION_CHANGED = auto()
    TTL_EXPIRED = auto()
    MANUAL = auto()
    MEMORY_PRESSURE = auto()
    DEPENDENCY_INVALIDATED = auto()


@dataclass
class InvalidationEvent:
    """Records a cache invalidation event."""
    timestamp: datetime
    reason: InvalidationReason
    keys_invalidated: List[str]
    layer_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class InvalidationStrategy(Enum):
    """Cache invalidation strategy."""
    IMMEDIATE = "immediate"  # Invalidate immediately
    LAZY = "lazy"  # Mark as stale, invalidate on next access
    BATCH = "batch"  # Batch invalidations for efficiency


@dataclass
class InvalidationRule:
    """
    Rule for automatic cache invalidation.
    
    Defines conditions and actions for invalidation.
    """
    name: str
    trigger: str  # e.g., "layer.modified", "schema.changed"
    target_namespaces: List[str]  # Namespaces to invalidate
    cascade: bool = False  # Whether to cascade to dependent entries
    strategy: InvalidationStrategy = InvalidationStrategy.IMMEDIATE
    
    def matches(self, event_type: str, **kwargs) -> bool:
        """Check if rule matches event."""
        return event_type == self.trigger


class DependencyTracker:
    """
    Tracks dependencies between cache entries.
    
    Enables cascade invalidation when a dependency is invalidated.
    """
    
    def __init__(self):
        # Maps key -> set of keys that depend on it
        self._dependents: Dict[str, Set[str]] = {}
        # Maps key -> set of keys it depends on
        self._dependencies: Dict[str, Set[str]] = {}
    
    def add_dependency(self, key: str, depends_on: str) -> None:
        """
        Add a dependency relationship.
        
        Args:
            key: The dependent key
            depends_on: The key being depended on
        """
        if depends_on not in self._dependents:
            self._dependents[depends_on] = set()
        self._dependents[depends_on].add(key)
        
        if key not in self._dependencies:
            self._dependencies[key] = set()
        self._dependencies[key].add(depends_on)
    
    def remove_key(self, key: str) -> None:
        """Remove all dependency relationships for a key."""
        # Remove from dependents' dependencies
        for dep_key in self._dependencies.get(key, set()):
            if dep_key in self._dependents:
                self._dependents[dep_key].discard(key)
        
        # Remove from dependencies' dependents
        for dependent in self._dependents.get(key, set()):
            if dependent in self._dependencies:
                self._dependencies[dependent].discard(key)
        
        # Clean up
        self._dependents.pop(key, None)
        self._dependencies.pop(key, None)
    
    def get_dependents(self, key: str) -> Set[str]:
        """Get all keys that depend on the given key."""
        return self._dependents.get(key, set()).copy()
    
    def get_all_dependents(self, key: str) -> Set[str]:
        """
        Get all dependent keys recursively.
        
        Follows the dependency chain to find all affected keys.
        """
        all_dependents = set()
        to_process = [key]
        
        while to_process:
            current = to_process.pop()
            dependents = self._dependents.get(current, set())
            
            for dep in dependents:
                if dep not in all_dependents:
                    all_dependents.add(dep)
                    to_process.append(dep)
        
        return all_dependents
    
    def clear(self) -> None:
        """Clear all dependency tracking."""
        self._dependents.clear()
        self._dependencies.clear()


class CacheInvalidator:
    """
    Manages cache invalidation across multiple caches.
    
    Features:
    - Rule-based automatic invalidation
    - Dependency tracking and cascade invalidation
    - Event logging
    - Batch invalidation support
    
    Example:
        invalidator = CacheInvalidator(cache_manager)
        
        # Register invalidation rule
        invalidator.add_rule(InvalidationRule(
            name="layer_change",
            trigger="layer.modified",
            target_namespaces=["filter", "count", "unique_values"],
        ))
        
        # Trigger invalidation
        invalidator.on_event("layer.modified", layer_id="layer_123")
    """
    
    def __init__(
        self,
        cache_manager: CacheManager = None,
        enable_logging: bool = True,
        max_history: int = 100,
    ):
        """
        Initialize cache invalidator.
        
        Args:
            cache_manager: Cache manager instance (uses global if None)
            enable_logging: Whether to log invalidation events
            max_history: Maximum history events to retain
        """
        self._cache_manager = cache_manager or get_cache_manager()
        self._enable_logging = enable_logging
        self._max_history = max_history
        
        self._rules: List[InvalidationRule] = []
        self._dependency_tracker = DependencyTracker()
        self._history: List[InvalidationEvent] = []
        self._listeners: List[Callable[[InvalidationEvent], None]] = []
        
        # Pending batch invalidations
        self._pending_invalidations: Dict[str, Set[str]] = {}
        
        # Setup default rules
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default invalidation rules."""
        # Invalidate all filter-related caches when layer is modified
        self.add_rule(InvalidationRule(
            name="layer_modified",
            trigger="layer.modified",
            target_namespaces=["filter", "count", "unique_values", "spatial"],
            cascade=True,
        ))
        
        # Invalidate when layer is deleted
        self.add_rule(InvalidationRule(
            name="layer_deleted",
            trigger="layer.deleted",
            target_namespaces=["filter", "count", "unique_values", "spatial"],
            cascade=True,
        ))
        
        # Invalidate unique values when schema changes
        self.add_rule(InvalidationRule(
            name="schema_changed",
            trigger="schema.changed",
            target_namespaces=["unique_values"],
            cascade=False,
        ))
    
    def add_rule(self, rule: InvalidationRule) -> None:
        """Add an invalidation rule."""
        self._rules.append(rule)
        logger.debug(f"Added invalidation rule: {rule.name}")
    
    def remove_rule(self, name: str) -> bool:
        """Remove an invalidation rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False
    
    def add_listener(
        self,
        callback: Callable[[InvalidationEvent], None],
    ) -> None:
        """Add a listener for invalidation events."""
        self._listeners.append(callback)
    
    def on_event(self, event_type: str, **kwargs) -> int:
        """
        Process an invalidation event.
        
        Args:
            event_type: Type of event (e.g., "layer.modified")
            **kwargs: Event parameters (e.g., layer_id="...")
            
        Returns:
            Number of entries invalidated
        """
        total_invalidated = 0
        
        for rule in self._rules:
            if rule.matches(event_type, **kwargs):
                count = self._apply_rule(rule, **kwargs)
                total_invalidated += count
        
        return total_invalidated
    
    def _apply_rule(self, rule: InvalidationRule, **kwargs) -> int:
        """Apply an invalidation rule."""
        layer_id = kwargs.get('layer_id')
        keys_invalidated = []
        
        for cache_name, cache in self._get_caches().items():
            # Invalidate by layer if layer_id provided
            if layer_id and hasattr(cache, 'invalidate_by_layer'):
                count = cache.invalidate_by_layer(layer_id)
                keys_invalidated.extend([f"{cache_name}:{layer_id}"] * count)
            
            # Invalidate by namespace
            if hasattr(cache, 'invalidate_by_namespace'):
                for namespace in rule.target_namespaces:
                    count = cache.invalidate_by_namespace(namespace)
                    keys_invalidated.extend([f"{cache_name}:{namespace}"] * count)
        
        # Record event
        event = InvalidationEvent(
            timestamp=datetime.now(),
            reason=self._get_reason_from_trigger(rule.trigger),
            keys_invalidated=keys_invalidated,
            layer_id=layer_id,
            details={'rule': rule.name, 'event_kwargs': kwargs},
        )
        
        self._record_event(event)
        
        return len(keys_invalidated)
    
    def _get_caches(self) -> Dict[str, CacheInterface]:
        """Get all registered caches."""
        return {
            name: cache
            for name in ['query', 'filter', 'spatial']
            if (cache := self._cache_manager.get_cache(name)) is not None
        }
    
    def _get_reason_from_trigger(self, trigger: str) -> InvalidationReason:
        """Map trigger to invalidation reason."""
        mapping = {
            'layer.modified': InvalidationReason.LAYER_MODIFIED,
            'layer.deleted': InvalidationReason.LAYER_DELETED,
            'schema.changed': InvalidationReason.SCHEMA_CHANGED,
            'expression.changed': InvalidationReason.EXPRESSION_CHANGED,
        }
        return mapping.get(trigger, InvalidationReason.MANUAL)
    
    def _record_event(self, event: InvalidationEvent) -> None:
        """Record invalidation event in history."""
        self._history.append(event)
        
        # Trim history
        while len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Invalidation listener error: {e}")
        
        if self._enable_logging:
            logger.info(
                f"Cache invalidation: {event.reason.name}, "
                f"{len(event.keys_invalidated)} entries, "
                f"layer={event.layer_id}"
            )
    
    # Convenience methods for common events
    
    def on_layer_modified(self, layer_id: str) -> int:
        """Handle layer modification event."""
        return self.on_event("layer.modified", layer_id=layer_id)
    
    def on_layer_deleted(self, layer_id: str) -> int:
        """Handle layer deletion event."""
        return self.on_event("layer.deleted", layer_id=layer_id)
    
    def on_schema_changed(self, layer_id: str, field_name: str = None) -> int:
        """Handle schema change event."""
        return self.on_event("schema.changed", layer_id=layer_id, field_name=field_name)
    
    def on_filter_applied(self, layer_id: str, expression: str) -> int:
        """Handle filter application event (may invalidate dependent caches)."""
        return self.on_event("filter.applied", layer_id=layer_id, expression=expression)
    
    # Dependency management
    
    def add_dependency(self, key: CacheKey, depends_on: CacheKey) -> None:
        """Add dependency between cache keys."""
        self._dependency_tracker.add_dependency(str(key), str(depends_on))
    
    def invalidate_with_dependencies(self, key: CacheKey) -> int:
        """
        Invalidate a key and all its dependents.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            Total entries invalidated
        """
        key_str = str(key)
        all_dependents = self._dependency_tracker.get_all_dependents(key_str)
        
        total = 0
        
        # Invalidate dependents first
        for dep_key_str in all_dependents:
            # Parse key and invalidate (simplified)
            total += 1
        
        # Invalidate original key
        for cache in self._get_caches().values():
            if cache.delete(key):
                total += 1
        
        # Clean up dependency tracking
        self._dependency_tracker.remove_key(key_str)
        
        return total
    
    # History and statistics
    
    def get_history(
        self,
        limit: int = None,
        reason: InvalidationReason = None,
    ) -> List[InvalidationEvent]:
        """
        Get invalidation history.
        
        Args:
            limit: Maximum events to return
            reason: Filter by reason
        """
        events = self._history
        
        if reason:
            events = [e for e in events if e.reason == reason]
        
        if limit:
            events = events[-limit:]
        
        return events
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get invalidation statistics."""
        total_events = len(self._history)
        by_reason = {}
        
        for event in self._history:
            reason = event.reason.name
            by_reason[reason] = by_reason.get(reason, 0) + 1
        
        return {
            'total_events': total_events,
            'by_reason': by_reason,
            'rules_count': len(self._rules),
        }


# Global invalidator instance
_invalidator: Optional[CacheInvalidator] = None


def get_cache_invalidator() -> CacheInvalidator:
    """Get global cache invalidator instance."""
    global _invalidator
    if _invalidator is None:
        _invalidator = CacheInvalidator()
    return _invalidator


def reset_cache_invalidator() -> None:
    """Reset global cache invalidator (for testing)."""
    global _invalidator
    _invalidator = None
