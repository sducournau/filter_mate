"""
FilterMate Infrastructure Feedback.

User feedback utilities (message bar, dialogs, etc.).

This module provides compatibility imports for feedback utilities,
replacing the old infrastructure.feedback imports.
"""

# Re-export from legacy module for now (will be migrated later)
try:
    from infrastructure.feedback import (
        show_info,
        show_success,
        show_warning,
        show_error,
        show_progress_message,
        show_backend_info,
    )
except ImportError:
    # Fallback if modules is removed
    def show_info(title: str, message: str):
        print(f"[INFO] {title}: {message}")
    
    def show_success(title: str, message: str):
        print(f"[SUCCESS] {title}: {message}")
    
    def show_warning(title: str, message: str):
        print(f"[WARNING] {title}: {message}")
    
    def show_error(title: str, message: str):
        print(f"[ERROR] {title}: {message}")
    
    def show_progress_message(message: str):
        print(f"[PROGRESS] {message}")
    
    def show_backend_info(backend_name: str, layer_count: int):
        print(f"[BACKEND] {backend_name}: {layer_count} layers")

__all__ = [
    'show_info',
    'show_success',
    'show_warning',
    'show_error',
    'show_progress_message',
    'show_backend_info',
]
