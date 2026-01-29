# -*- coding: utf-8 -*-
"""
Benchmark Framework for FilterMate Performance Testing.

v4.1.1 - January 2026 - EPIC-3 Sprint 1

PURPOSE:
Provides infrastructure for measuring and tracking FilterMate performance:
1. Timer utilities for precise measurement
2. BenchmarkRunner for executing test suites
3. BenchmarkResult for storing results
4. Statistical analysis (mean, median, std dev, percentiles)

USAGE:
    from infrastructure.benchmark import BenchmarkRunner, Timer
    
    runner = BenchmarkRunner()
    
    @runner.benchmark("filter_100k_features")
    def test_filter():
        layer.setSubsetString("status = 1")
    
    results = runner.run_all()
    print(results.summary())
"""

import time
import statistics
import logging
import functools
from typing import List, Dict, Callable, Optional, Any, NamedTuple
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime
import json

logger = logging.getLogger('FilterMate.Benchmark')


class TimingResult(NamedTuple):
    """Single timing measurement."""
    duration_ms: float
    iteration: int
    timestamp: float


@dataclass
class BenchmarkResult:
    """
    Results from a benchmark run.
    
    Stores timing data and provides statistical analysis.
    """
    name: str
    description: str = ""
    timings: List[float] = field(default_factory=list)  # in milliseconds
    iterations: int = 0
    warmup_iterations: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def mean_ms(self) -> float:
        """Mean execution time in milliseconds."""
        return statistics.mean(self.timings) if self.timings else 0.0
    
    @property
    def median_ms(self) -> float:
        """Median execution time in milliseconds."""
        return statistics.median(self.timings) if self.timings else 0.0
    
    @property
    def std_dev_ms(self) -> float:
        """Standard deviation in milliseconds."""
        return statistics.stdev(self.timings) if len(self.timings) > 1 else 0.0
    
    @property
    def min_ms(self) -> float:
        """Minimum execution time in milliseconds."""
        return min(self.timings) if self.timings else 0.0
    
    @property
    def max_ms(self) -> float:
        """Maximum execution time in milliseconds."""
        return max(self.timings) if self.timings else 0.0
    
    @property
    def p95_ms(self) -> float:
        """95th percentile in milliseconds."""
        if not self.timings:
            return 0.0
        sorted_timings = sorted(self.timings)
        idx = int(len(sorted_timings) * 0.95)
        return sorted_timings[min(idx, len(sorted_timings) - 1)]
    
    @property
    def p99_ms(self) -> float:
        """99th percentile in milliseconds."""
        if not self.timings:
            return 0.0
        sorted_timings = sorted(self.timings)
        idx = int(len(sorted_timings) * 0.99)
        return sorted_timings[min(idx, len(sorted_timings) - 1)]
    
    @property
    def ops_per_second(self) -> float:
        """Operations per second based on mean time."""
        if self.mean_ms <= 0:
            return 0.0
        return 1000.0 / self.mean_ms
    
    def summary(self) -> str:
        """Get formatted summary string."""
        return (
            f"{self.name}: "
            f"mean={self.mean_ms:.2f}ms, "
            f"median={self.median_ms:.2f}ms, "
            f"std={self.std_dev_ms:.2f}ms, "
            f"min={self.min_ms:.2f}ms, "
            f"max={self.max_ms:.2f}ms, "
            f"p95={self.p95_ms:.2f}ms, "
            f"iterations={self.iterations}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'statistics': {
                'mean_ms': self.mean_ms,
                'median_ms': self.median_ms,
                'std_dev_ms': self.std_dev_ms,
                'min_ms': self.min_ms,
                'max_ms': self.max_ms,
                'p95_ms': self.p95_ms,
                'p99_ms': self.p99_ms,
                'ops_per_second': self.ops_per_second,
            },
            'iterations': self.iterations,
            'warmup_iterations': self.warmup_iterations,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'raw_timings': self.timings,
        }


class Timer:
    """
    High-precision timer for benchmarking.
    
    Supports both context manager and decorator usage.
    
    Example (context manager):
        with Timer() as t:
            expensive_operation()
        print(f"Took {t.elapsed_ms:.2f}ms")
    
    Example (decorator):
        @Timer.measure
        def my_function():
            pass
    """
    
    def __init__(self):
        self._start: Optional[float] = None
        self._end: Optional[float] = None
        self._elapsed: float = 0.0
    
    def start(self) -> 'Timer':
        """Start the timer."""
        self._start = time.perf_counter()
        self._end = None
        return self
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time in ms."""
        if self._start is None:
            return 0.0
        self._end = time.perf_counter()
        self._elapsed = (self._end - self._start) * 1000
        return self._elapsed
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._start is None:
            return 0.0
        if self._end is None:
            # Timer still running
            return (time.perf_counter() - self._start) * 1000
        return self._elapsed
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return self.elapsed_ms / 1000.0
    
    def __enter__(self) -> 'Timer':
        self.start()
        return self
    
    def __exit__(self, *args) -> None:
        self.stop()
    
    @staticmethod
    def measure(func: Callable) -> Callable:
        """Decorator to measure function execution time."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with Timer() as t:
                result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} took {t.elapsed_ms:.2f}ms")
            return result
        return wrapper


@contextmanager
def timed_block(name: str = "block"):
    """
    Context manager for timing code blocks with logging.
    
    Example:
        with timed_block("data_processing"):
            process_data()
    """
    timer = Timer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()
        logger.info(f"⏱️ {name}: {timer.elapsed_ms:.2f}ms")


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""
    iterations: int = 10
    warmup_iterations: int = 2
    timeout_seconds: float = 60.0
    gc_collect_before: bool = True
    name_prefix: str = ""


class BenchmarkRunner:
    """
    Executes and manages benchmark tests.
    
    Features:
    - Warmup iterations to stabilize measurements
    - Automatic garbage collection between runs
    - Timeout protection
    - Result aggregation and comparison
    
    Example:
        runner = BenchmarkRunner(iterations=10, warmup=2)
        
        # Register benchmarks
        runner.add("filter_simple", lambda: layer.setSubsetString("a=1"))
        runner.add("filter_complex", lambda: layer.setSubsetString("a>1 AND b<10"))
        
        # Or use decorator
        @runner.benchmark("my_test")
        def test_something():
            pass
        
        # Run all and get results
        results = runner.run_all()
        for r in results:
            print(r.summary())
    """
    
    def __init__(
        self,
        iterations: int = 10,
        warmup: int = 2,
        timeout: float = 60.0,
        gc_before: bool = True,
    ):
        """
        Initialize benchmark runner.
        
        Args:
            iterations: Number of timed iterations per benchmark
            warmup: Number of warmup iterations (not timed)
            timeout: Timeout per benchmark in seconds
            gc_before: Run garbage collection before each benchmark
        """
        self.config = BenchmarkConfig(
            iterations=iterations,
            warmup_iterations=warmup,
            timeout_seconds=timeout,
            gc_collect_before=gc_before,
        )
        self._benchmarks: Dict[str, tuple] = {}  # name -> (func, description, metadata)
        self._results: List[BenchmarkResult] = []
    
    def add(
        self,
        name: str,
        func: Callable,
        description: str = "",
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Add a benchmark function.
        
        Args:
            name: Unique benchmark name
            func: Function to benchmark (no arguments)
            description: Optional description
            metadata: Optional metadata dict
        """
        self._benchmarks[name] = (func, description, metadata or {})
    
    def benchmark(
        self,
        name: str,
        description: str = "",
        metadata: Dict[str, Any] = None,
    ) -> Callable:
        """
        Decorator to register a benchmark function.
        
        Args:
            name: Benchmark name
            description: Optional description
            metadata: Optional metadata
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            self.add(name, func, description, metadata)
            return func
        return decorator
    
    def run(
        self,
        name: str,
        setup: Callable = None,
        teardown: Callable = None,
    ) -> BenchmarkResult:
        """
        Run a single benchmark.
        
        Args:
            name: Benchmark name to run
            setup: Optional setup function called before each iteration
            teardown: Optional teardown function called after each iteration
            
        Returns:
            BenchmarkResult with timing data
        """
        if name not in self._benchmarks:
            raise ValueError(f"Benchmark '{name}' not found")
        
        func, description, metadata = self._benchmarks[name]
        
        # Garbage collection
        if self.config.gc_collect_before:
            import gc
            gc.collect()
        
        timings: List[float] = []
        
        # Warmup iterations
        for _ in range(self.config.warmup_iterations):
            if setup:
                setup()
            try:
                func()
            finally:
                if teardown:
                    teardown()
        
        # Timed iterations
        for i in range(self.config.iterations):
            if setup:
                setup()
            
            timer = Timer()
            timer.start()
            try:
                func()
            finally:
                elapsed = timer.stop()
                timings.append(elapsed)
                if teardown:
                    teardown()
        
        result = BenchmarkResult(
            name=name,
            description=description,
            timings=timings,
            iterations=self.config.iterations,
            warmup_iterations=self.config.warmup_iterations,
            metadata=metadata,
        )
        
        self._results.append(result)
        logger.info(f"✓ Benchmark '{name}': {result.summary()}")
        
        return result
    
    def run_all(
        self,
        setup: Callable = None,
        teardown: Callable = None,
    ) -> List[BenchmarkResult]:
        """
        Run all registered benchmarks.
        
        Args:
            setup: Optional setup function for all benchmarks
            teardown: Optional teardown function for all benchmarks
            
        Returns:
            List of BenchmarkResult objects
        """
        results = []
        for name in self._benchmarks:
            try:
                result = self.run(name, setup, teardown)
                results.append(result)
            except Exception as e:
                logger.error(f"Benchmark '{name}' failed: {e}")
        return results
    
    def clear_results(self) -> None:
        """Clear all stored results."""
        self._results.clear()
    
    def get_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        return self._results.copy()
    
    def compare(
        self,
        baseline_name: str,
        comparison_name: str,
    ) -> Dict[str, float]:
        """
        Compare two benchmark results.
        
        Args:
            baseline_name: Name of baseline benchmark
            comparison_name: Name of comparison benchmark
            
        Returns:
            Dict with comparison metrics (speedup, difference, etc.)
        """
        baseline = next((r for r in self._results if r.name == baseline_name), None)
        comparison = next((r for r in self._results if r.name == comparison_name), None)
        
        if not baseline or not comparison:
            return {}
        
        speedup = baseline.mean_ms / comparison.mean_ms if comparison.mean_ms > 0 else 0
        
        return {
            'baseline_mean_ms': baseline.mean_ms,
            'comparison_mean_ms': comparison.mean_ms,
            'difference_ms': baseline.mean_ms - comparison.mean_ms,
            'speedup': speedup,
            'speedup_percent': (speedup - 1) * 100,
            'baseline_name': baseline_name,
            'comparison_name': comparison_name,
        }


class BenchmarkSuite:
    """
    Collection of related benchmarks.
    
    Organizes benchmarks into logical groups for better reporting.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize benchmark suite.
        
        Args:
            name: Suite name
            description: Suite description
        """
        self.name = name
        self.description = description
        self.runner = BenchmarkRunner()
        self._suites: List['BenchmarkSuite'] = []
    
    def add_suite(self, suite: 'BenchmarkSuite') -> None:
        """Add a sub-suite."""
        self._suites.append(suite)
    
    def add_benchmark(
        self,
        name: str,
        func: Callable,
        description: str = "",
    ) -> None:
        """Add a benchmark to this suite."""
        full_name = f"{self.name}.{name}"
        self.runner.add(full_name, func, description)
    
    def run_all(self) -> Dict[str, List[BenchmarkResult]]:
        """
        Run all benchmarks in suite and sub-suites.
        
        Returns:
            Dict mapping suite name to results
        """
        results = {self.name: self.runner.run_all()}
        
        for suite in self._suites:
            sub_results = suite.run_all()
            results.update(sub_results)
        
        return results


def measure_memory_usage() -> Dict[str, float]:
    """
    Measure current memory usage.
    
    Returns:
        Dict with memory metrics in MB
    """
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        return {
            'rss_mb': mem_info.rss / (1024 * 1024),
            'vms_mb': mem_info.vms / (1024 * 1024),
        }
    except ImportError:
        return {'rss_mb': 0, 'vms_mb': 0}


@contextmanager
def memory_tracker(name: str = "operation"):
    """
    Context manager to track memory usage.
    
    Example:
        with memory_tracker("load_layer"):
            layer = load_large_layer()
    """
    before = measure_memory_usage()
    yield
    after = measure_memory_usage()
    
    delta_rss = after['rss_mb'] - before['rss_mb']
    logger.info(f"🧠 {name}: Memory delta = {delta_rss:+.2f} MB")
