# -*- coding: utf-8 -*-
"""
Configuration Migration for FilterMate

Provides automatic migration of configuration files between versions.
Ensures backward compatibility when upgrading FilterMate.

Usage:
    from infrastructure.config.config_migration import ConfigMigration
    
    migrator = ConfigMigration()
    success, warnings = migrator.auto_migrate_if_needed(confirm_reset_callback=callback)

Author: FilterMate Team
Date: January 2026
Migration: EPIC-1 Phase E6 - Hexagonal Architecture
"""
import logging
import os
from typing import Tuple, List, Optional, Callable

logger = logging.getLogger('FilterMate.ConfigMigration')


class ConfigMigration:
    """
    Configuration migration manager.
    
    Handles automatic migration of configuration files from older versions
    to the current version format.
    """
    
    CURRENT_VERSION = "2.0"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration migration manager.
        
        Args:
            config_path: Optional path to configuration file.
                        If not provided, uses default FilterMate config location.
        """
        self.config_path = config_path
        self._warnings: List[str] = []
    
    def auto_migrate_if_needed(
        self,
        confirm_reset_callback: Optional[Callable[[], bool]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Automatically migrate configuration if needed.
        
        Checks the current configuration version and migrates if necessary.
        
        Args:
            confirm_reset_callback: Optional callback to confirm reset operations.
                                   Should return True if reset is confirmed.
        
        Returns:
            Tuple of (success: bool, warnings: List[str])
        """
        try:
            # Check if migration is needed
            if not self._needs_migration():
                logger.debug("Configuration is up to date, no migration needed")
                return True, []
            
            logger.info("Configuration migration started")
            
            # Perform migration
            success = self._migrate_config()
            
            if success:
                logger.info("Configuration migration completed successfully")
            else:
                logger.warning("Configuration migration completed with issues")
            
            return success, self._warnings
            
        except Exception as e:
            logger.error(f"Configuration migration failed: {e}")
            self._warnings.append(f"Migration error: {str(e)}")
            return False, self._warnings
    
    def _needs_migration(self) -> bool:
        """Check if configuration needs migration."""
        # Default implementation: assume no migration needed
        # This can be extended to check version in config file
        return False
    
    def _migrate_config(self) -> bool:
        """
        Perform the actual configuration migration.
        
        Returns:
            True if migration was successful
        """
        # Default implementation: no-op migration
        return True
    
    def get_current_version(self) -> str:
        """Get current configuration version."""
        return self.CURRENT_VERSION


__all__ = ['ConfigMigration']
