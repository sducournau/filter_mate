# -*- coding: utf-8 -*-
"""
Hexagonal Architecture Configuration.

v4.2.0: Configuration and activation utilities for the hexagonal architecture.
This module provides a clean API to enable/disable new backends progressively.

Usage in QGIS Python Console:
    >>> from filter_mate.adapters.backends.hexagonal_config import (
    ...     enable_hexagonal_architecture,
    ...     disable_hexagonal_architecture,
    ...     get_architecture_status,
    ...     enable_backend,
    ...     disable_backend
    ... )
    >>>
    >>> # Check current status
    >>> get_architecture_status()
    {'postgresql': 'legacy', 'spatialite': 'legacy', 'ogr': 'legacy', 'memory': 'legacy'}
    >>>
    >>> # Enable all new backends
    >>> enable_hexagonal_architecture()
    >>>
    >>> # Or enable progressively
    >>> enable_backend('ogr')
    >>> enable_backend('spatialite')
    >>> enable_backend('postgresql')

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger('FilterMate.Hexagonal')


def enable_backend(provider_type: str) -> bool:
    """
    Enable the new hexagonal backend for a specific provider.

    Args:
        provider_type: 'postgresql', 'spatialite', 'ogr', or 'memory'

    Returns:
        True if successfully enabled, False otherwise

    Example:
        >>> enable_backend('ogr')
        True
    """
    try:
        from .legacy_adapter import set_new_backend_enabled
        set_new_backend_enabled(provider_type, True)
        logger.debug(f"✅ Hexagonal backend ENABLED for: {provider_type.upper()}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to enable {provider_type}: {e}")
        return False


def disable_backend(provider_type: str) -> bool:
    """
    Disable the new hexagonal backend, revert to legacy.

    Args:
        provider_type: 'postgresql', 'spatialite', 'ogr', or 'memory'

    Returns:
        True if successfully disabled, False otherwise
    """
    try:
        from .legacy_adapter import set_new_backend_enabled
        set_new_backend_enabled(provider_type, False)
        logger.debug(f"🔙 Hexagonal backend DISABLED for: {provider_type.upper()} (using legacy)")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to disable {provider_type}: {e}")
        return False


def enable_hexagonal_architecture(providers: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    Enable hexagonal architecture for specified providers (or all).

    Args:
        providers: List of providers to enable. If None, enables all.
                  Options: ['postgresql', 'spatialite', 'ogr', 'memory']

    Returns:
        Dict mapping provider to success status

    Example:
        >>> enable_hexagonal_architecture()  # Enable all
        {'postgresql': True, 'spatialite': True, 'ogr': True, 'memory': True}

        >>> enable_hexagonal_architecture(['ogr', 'memory'])  # Enable subset
        {'ogr': True, 'memory': True}
    """
    all_providers = ['postgresql', 'spatialite', 'ogr', 'memory']
    target_providers = providers or all_providers

    results = {}
    for provider in target_providers:
        results[provider] = enable_backend(provider)

    enabled_count = sum(1 for v in results.values() if v)
    logger.debug(f"🚀 Hexagonal architecture enabled for {enabled_count}/{len(target_providers)} backends")

    return results


def disable_hexagonal_architecture() -> Dict[str, bool]:
    """
    Disable all hexagonal backends, revert to legacy architecture.

    Returns:
        Dict mapping provider to success status
    """
    try:
        from .legacy_adapter import disable_all_new_backends
        disable_all_new_backends()
        logger.debug("🔙 Hexagonal architecture DISABLED - all backends using legacy")
        return {'postgresql': True, 'spatialite': True, 'ogr': True, 'memory': True}
    except Exception as e:
        logger.error(f"❌ Failed to disable hexagonal architecture: {e}")
        return {'error': str(e)}


def get_architecture_status() -> Dict[str, str]:
    """
    Get current architecture status for all backends.

    Returns:
        Dict mapping provider to 'hexagonal' or 'legacy'

    Example:
        >>> get_architecture_status()
        {'postgresql': 'legacy', 'spatialite': 'legacy', 'ogr': 'hexagonal', 'memory': 'legacy'}
    """
    try:
        from .legacy_adapter import get_backend_status
        status = get_backend_status()
        # Rename 'new' to 'hexagonal' for clarity
        return {
            provider: ('hexagonal' if state == 'new' else 'legacy')
            for provider, state in status.items()
        }
    except Exception as e:
        logger.error(f"Failed to get architecture status: {e}")
        return {'error': str(e)}


def is_hexagonal_enabled(provider_type: str) -> bool:
    """
    Check if hexagonal architecture is enabled for a provider.

    Args:
        provider_type: Provider to check

    Returns:
        True if hexagonal, False if legacy
    """
    try:
        from .legacy_adapter import is_new_backend_enabled
        return is_new_backend_enabled(provider_type)
    except Exception:
        return False


def enable_progressive_migration():
    """
    Enable progressive migration mode: OGR and Memory first (lowest risk).

    This is the recommended starting point for testing the hexagonal architecture.
    """
    logger.debug("🧪 Starting progressive migration (OGR + Memory first)")
    enable_backend('ogr')
    enable_backend('memory')

    status = get_architecture_status()
    logger.info(f"Current status: {status}")

    return status


def complete_migration():
    """
    Complete the migration by enabling all backends including PostgreSQL.

    ⚠️ Only use after testing with progressive_migration!
    """
    logger.debug("🚀 Completing migration (all backends)")
    return enable_hexagonal_architecture()


# Convenience function for QGIS console
def status():
    """
    Print current architecture status (for QGIS console).

    Example:
        >>> from filter_mate.adapters.backends.hexagonal_config import status
        >>> status()
        🔧 FilterMate Architecture Status:
           postgresql: legacy
           spatialite: legacy
           ogr: hexagonal
           memory: legacy
    """
    current = get_architecture_status()

    for provider, state in current.items():
        icon = "🆕" if state == 'hexagonal' else "📦"

    return current
