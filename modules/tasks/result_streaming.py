# -*- coding: utf-8 -*-
"""
Result Streaming - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to infrastructure/streaming/result_streaming.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.result_streaming import StreamingExporter
- NEW: from infrastructure.streaming import StreamingExporter

All functionality is now available from:
    from infrastructure.streaming import (
        StreamingConfig,
        ExportProgress,
        StreamingExporter,
        estimate_export_memory
    )

This shim provides backward compatibility but will be removed in v3.1.
"""

import warnings

warnings.warn(
    "modules.tasks.result_streaming is deprecated. "
    "Use 'from infrastructure.streaming import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from infrastructure
from infrastructure.streaming import (
    StreamingConfig,
    ExportProgress,
    StreamingExporter,
    estimate_export_memory
)

__all__ = [
    'StreamingConfig',
    'ExportProgress',
    'StreamingExporter',
    'estimate_export_memory'
]
