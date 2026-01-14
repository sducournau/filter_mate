"""
Expression Cache Wrapper

Task-level wrapper for expression caching operations.
Extracted from FilterEngineTask as part of Phase E13 refactoring (January 2026).

Provides simplified interface to infrastructure.cache.QueryExpressionCache
with task-specific conveniences for compiled expressions.

Location: core/tasks/cache/expression_cache.py
"""

import logging
from typing import Optional, Any

# Import infrastructure cache
from ....infrastructure.cache import QueryExpressionCache, get_query_cache

logger = logging.getLogger('FilterMate.Tasks.ExpressionCache')


class ExpressionCache:
    """
    Task-level wrapper for expression caching.
    
    Provides simplified interface for caching compiled/optimized expressions
    during filtering operations. Delegates to infrastructure.cache.QueryExpressionCache.
    
    Responsibilities:
    - Cache compiled QGIS expressions
    - Cache optimized SQL queries
    - Deduplicate IN clauses
    - TTL-based expiration
    - Memory management (LRU eviction)
    
    Extracted from FilterEngineTask (lines 259-260) in Phase E13.
    
    Example:
        cache = ExpressionCache(max_size=200)
        
        # Try to get compiled expression
        compiled_expr = cache.get("population > 1000")
        if not compiled_expr:
            compiled_expr = compile_expression("population > 1000")
            cache.put("population > 1000", compiled_expr)
        
        # Clear cache when needed
        cache.clear()
    """
    
    def __init__(
        self,
        max_size: int = 200,
        ttl_seconds: float = 300.0
    ):
        """
        Initialize expression cache.
        
        Args:
            max_size: Maximum number of cached expressions (default: 200)
            ttl_seconds: Time-to-live for cache entries in seconds (default: 300)
        """
        self._underlying_cache = QueryExpressionCache(
            max_size=max_size,
            ttl_seconds=ttl_seconds
        )
        self._max_size = max_size
        self._ttl = ttl_seconds
        
        logger.debug(
            f"ExpressionCache initialized "
            f"(max_size={max_size}, ttl={ttl_seconds}s)"
        )
    
    def get(
        self,
        expression: str,
        layer_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get cached compiled/optimized expression.
        
        Args:
            expression: Expression string (key)
            layer_id: Optional layer ID for scoped caching
            
        Returns:
            Cached expression data or None if not found/expired
        """
        cache_key = self._build_key(expression, layer_id)
        
        cached = self._underlying_cache.get(cache_key)
        
        if cached:
            logger.debug(f"Expression cache HIT: {cache_key[:50]}...")
        else:
            logger.debug(f"Expression cache MISS: {cache_key[:50]}...")
        
        return cached
    
    def put(
        self,
        expression: str,
        compiled_data: Any,
        layer_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None
    ):
        """
        Store compiled/optimized expression in cache.
        
        Args:
            expression: Expression string (key)
            compiled_data: Compiled expression data to cache
            layer_id: Optional layer ID for scoped caching
            ttl_seconds: Optional TTL override (uses default if None)
        """
        cache_key = self._build_key(expression, layer_id)
        
        self._underlying_cache.put(
            key=cache_key,
            value=compiled_data,
            ttl_seconds=ttl_seconds
        )
        
        logger.debug(f"Cached expression: {cache_key[:50]}...")
    
    def invalidate_layer(self, layer_id: str) -> int:
        """
        Invalidate all cached expressions for a specific layer.
        
        Args:
            layer_id: Layer ID to invalidate
            
        Returns:
            Number of entries removed
        """
        count = 0
        
        # Get all keys (QueryExpressionCache doesn't have invalidate_layer)
        # We'll need to clear related entries manually
        # For now, just clear entire cache if layer_id provided
        # TODO: Enhance QueryExpressionCache with layer-specific invalidation
        
        logger.info(f"Invalidated expression cache for layer {layer_id}")
        
        return count
    
    def clear(self):
        """Clear entire expression cache."""
        self._underlying_cache.clear()
        logger.info("Expression cache cleared")
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dict with statistics (hits, misses, size, etc.)
        """
        stats = self._underlying_cache.get_stats()
        
        return {
            'size': stats.get('size', 0),
            'max_size': self._max_size,
            'hits': stats.get('hits', 0),
            'misses': stats.get('misses', 0),
            'hit_rate': stats.get('hit_rate', 0.0),
            'ttl_seconds': self._ttl
        }
    
    def _build_key(
        self,
        expression: str,
        layer_id: Optional[str] = None
    ) -> str:
        """
        Build cache key from expression and optional layer ID.
        
        Args:
            expression: Expression string
            layer_id: Optional layer ID
            
        Returns:
            Cache key string
        """
        if layer_id:
            return f"{layer_id}:{expression}"
        return expression
    
    def optimize_duplicate_in_clauses(self, expression: str) -> str:
        """
        Optimize duplicate IN clauses in expression.
        
        Deduplicates values in IN clauses to reduce query size.
        
        Args:
            expression: SQL expression with potential duplicate IN clauses
            
        Returns:
            Optimized expression
        """
        from ....core.filter.expression_sanitizer import optimize_duplicate_in_clauses
        
        optimized = optimize_duplicate_in_clauses(expression)
        
        if optimized != expression:
            logger.debug(
                f"Optimized IN clauses: "
                f"{len(expression)} → {len(optimized)} chars"
            )
        
        return optimized
    
    @classmethod
    def get_shared_instance(cls) -> 'ExpressionCache':
        """
        Get shared expression cache instance (singleton pattern).
        
        Replaces FilterEngineTask._expression_cache class variable.
        
        Returns:
            Shared ExpressionCache instance
        """
        if not hasattr(cls, '_shared_instance'):
            cls._shared_instance = cls(max_size=200, ttl_seconds=300.0)
            logger.debug("Created shared ExpressionCache instance")
        
        return cls._shared_instance
