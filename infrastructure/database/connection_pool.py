# -*- coding: utf-8 -*-
"""
PostgreSQL Connection Pool for FilterMate

Provides connection pooling for PostgreSQL database connections.
Improves performance by reusing database connections.

Usage:
    from infrastructure.database.connection_pool import cleanup_pools
    
    # Cleanup on unload
    cleanup_pools()

Author: FilterMate Team
Date: January 2026
Migration: EPIC-1 Phase E6 - Hexagonal Architecture
"""
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger('FilterMate.ConnectionPool')

# Global pool registry
_pools: Dict[str, Any] = {}


def cleanup_pools() -> None:
    """
    Cleanup all database connection pools.
    
    Should be called when unloading the plugin to properly
    release database resources.
    """
    global _pools
    
    if not _pools:
        logger.debug("No connection pools to cleanup")
        return
    
    logger.info(f"Cleaning up {len(_pools)} connection pool(s)")
    
    for pool_name, pool in list(_pools.items()):
        try:
            if hasattr(pool, 'closeall'):
                pool.closeall()
                logger.debug(f"Closed pool: {pool_name}")
            elif hasattr(pool, 'close'):
                pool.close()
                logger.debug(f"Closed pool: {pool_name}")
        except Exception as e:
            logger.warning(f"Error closing pool {pool_name}: {e}")
    
    _pools.clear()
    logger.debug("All connection pools cleaned up")


def get_pool(name: str) -> Optional[Any]:
    """
    Get a named connection pool.
    
    Args:
        name: Pool name
    
    Returns:
        Connection pool or None if not found
    """
    return _pools.get(name)


def register_pool(name: str, pool: Any) -> None:
    """
    Register a connection pool.
    
    Args:
        name: Pool name
        pool: Pool instance (psycopg2.pool.SimpleConnectionPool, etc.)
    """
    _pools[name] = pool
    logger.debug(f"Registered connection pool: {name}")


def unregister_pool(name: str) -> None:
    """
    Unregister a connection pool.
    
    Args:
        name: Pool name
    """
    if name in _pools:
        del _pools[name]
        logger.debug(f"Unregistered connection pool: {name}")


__all__ = [
    'cleanup_pools',
    'get_pool',
    'register_pool',
    'unregister_pool',
]
