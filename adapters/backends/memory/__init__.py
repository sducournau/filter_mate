"""
FilterMate Memory Backend Package.

In-memory layer support for temporary operations.
Lightweight backend optimized for speed.

Part of Phase 4 Backend Refactoring (ARCH-045).
"""
from .backend import MemoryBackend, create_memory_backend  # noqa: F401

__all__ = [
    'MemoryBackend',
    'create_memory_backend',
]
