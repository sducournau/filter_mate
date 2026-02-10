# -*- coding: utf-8 -*-
"""
Dependency Injection Container.

Provides dependency injection for FilterMate's hexagonal architecture.
Centralizes service creation and lifecycle management.
"""

from .container import Container, get_container, reset_container  # noqa: F401
from .providers import BackendProvider, ServiceProvider  # noqa: F401

__all__ = [
    'Container',
    'get_container',
    'reset_container',
    'BackendProvider',
    'ServiceProvider',
]
