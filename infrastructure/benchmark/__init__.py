# -*- coding: utf-8 -*-
"""
Infrastructure Benchmark Package

Provides benchmarking infrastructure for FilterMate performance testing:
- framework: Core benchmarking utilities (Timer, BenchmarkRunner)
- filter_benchmarks: Filter operation benchmarks
- spatial_benchmarks: Spatial query benchmarks
- report_generator: Report generation (JSON, HTML, Markdown)

EPIC-3 Sprint 1 - January 2026
"""

from .framework import (
    TimingResult,
    BenchmarkResult,
    BenchmarkConfig,
    BenchmarkRunner,
    BenchmarkSuite,
    Timer,
    timed_block,
    measure_memory_usage,
    memory_tracker,
)

from .filter_benchmarks import (
    FilterBenchmarkConfig,
    FilterBenchmarks,
    run_filter_benchmarks,
)

from .spatial_benchmarks import (
    SpatialBenchmarkConfig,
    SpatialBenchmarks,
    run_spatial_benchmarks,
)

from .report_generator import (
    ReportMetadata,
    ReportGenerator,
    generate_report,
)

__all__ = [
    # Framework
    'TimingResult',
    'BenchmarkResult',
    'BenchmarkConfig',
    'BenchmarkRunner',
    'BenchmarkSuite',
    'Timer',
    'timed_block',
    'measure_memory_usage',
    'memory_tracker',
    # Filter benchmarks
    'FilterBenchmarkConfig',
    'FilterBenchmarks',
    'run_filter_benchmarks',
    # Spatial benchmarks
    'SpatialBenchmarkConfig',
    'SpatialBenchmarks',
    'run_spatial_benchmarks',
    # Report generator
    'ReportMetadata',
    'ReportGenerator',
    'generate_report',
]
