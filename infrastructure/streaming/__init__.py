# -*- coding: utf-8 -*-
"""
Infrastructure Streaming Package

Provides streaming, pagination and batch processing utilities for large datasets:
- result_streaming: Chunked exports for very large datasets
- paginator: Pagination for large query results
- progress_stream: Real-time progress streaming for UI

Migrated from modules/tasks/ (EPIC-1 v3.0).
Enhanced in EPIC-3 Sprint 3 (v4.1.1).
"""

from .result_streaming import (
    StreamingConfig,
    ExportProgress,
    StreamingExporter,
    estimate_export_memory,
    FeatureBatchIterator,
)

from .paginator import (
    PaginationStrategy,
    PageInfo,
    PaginatedResult,
    BasePaginator,
    FeaturePaginator,
    ListPaginator,
    VirtualScrollAdapter,
    create_feature_paginator,
)

from .progress_stream import (
    ProgressState,
    ProgressInfo,
    ProgressStreamer,
    MultiStageProgress,
    create_progress_streamer,
)

__all__ = [
    # Result streaming
    'StreamingConfig',
    'ExportProgress',
    'StreamingExporter',
    'estimate_export_memory',
    'FeatureBatchIterator',
    # Pagination
    'PaginationStrategy',
    'PageInfo',
    'PaginatedResult',
    'BasePaginator',
    'FeaturePaginator',
    'ListPaginator',
    'VirtualScrollAdapter',
    'create_feature_paginator',
    # Progress streaming
    'ProgressState',
    'ProgressInfo',
    'ProgressStreamer',
    'MultiStageProgress',
    'create_progress_streamer',
]
