"""
FilterMate OGR Backend Package.

OGR provider implementations for file-based formats.
Universal fallback for unsupported providers.

Part of Phase 4 Backend Refactoring (ARCH-044).
"""
from .backend import OGRBackend, create_ogr_backend

__all__ = [
    'OGRBackend',
    'create_ogr_backend',
]
