# -*- coding: utf-8 -*-
"""
Dependency Injection Container.

Provides dependency injection for FilterMate's hexagonal architecture.
Centralizes service creation and lifecycle management.
"""

from .container import Container, get_container, reset_container
from .providers import BackendProvider, ServiceProvider

__all__ = [
    'Container',
    'get_container',
    'reset_container',
    'BackendProvider',
    'ServiceProvider',
]
