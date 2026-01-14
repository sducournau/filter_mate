# -*- coding: utf-8 -*-
"""
Task Dispatchers Module

Phase E13 Step 6: Action dispatching and coordination.

Provides:
- ActionDispatcher: Routes task actions to appropriate handlers
"""

from .action_dispatcher import ActionDispatcher, ActionResult, ActionHandler

__all__ = ['ActionDispatcher', 'ActionResult', 'ActionHandler']
