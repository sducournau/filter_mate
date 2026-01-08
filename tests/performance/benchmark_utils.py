# -*- coding: utf-8 -*-
"""
Performance Benchmark Utilities - ARCH-052

Utilities for running and reporting performance benchmarks.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import json
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class BenchmarkResult:
    """
    Result of a single benchmark run.
    
    Attributes:
        name: Benchmark name
        operation: Operation type (filter, export, etc.)
        backend: Backend used
        dataset_size: Number of features
        duration_ms: Execution time in milliseconds
        memory_mb: Peak memory usage in MB
        used_optimization: Whether optimization was used
        iterations: Number of iterations
        metadata: Additional metadata
    """
    name: str
    operation: str
    backend: str
    dataset_size: int
    duration_ms: float
    memory_mb: float = 0.0
    used_optimization: bool = False
    iterations: int = 1
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class BenchmarkSummary:
    """
    Summary of benchmark run.
    
    Attributes:
        generated_at: Timestamp
        version: FilterMate version
        total_tests: Number of benchmarks
        passed: Number passed
        failed: Number with regression
        regressions: List of regression details
        results: All benchmark results
    """
    generated_at: str
    version: str
    total_tests: int
    passed: int
    failed: int
    regressions: List[Dict[str, Any]]
    results: List[BenchmarkResult]
    
    def has_regressions(self) -> bool:
        """Check if any regressions detected."""
        return len(self.regressions) > 0


class BenchmarkRunner:
    """
    Runs and collects benchmark results.
    
    Example:
        runner = BenchmarkRunner()
        
        with runner.benchmark("filter_postgresql", "filter", "postgresql"):
            # Run operation
            pass
        
        summary = runner.get_summary()
    """
    
    # Baseline values (v2.x measurements)
    BASELINES = {
        "filter_1k_postgresql": 45.0,
        "filter_10k_postgresql": 120.0,
        "filter_100k_postgresql": 450.0,
        "filter_1k_spatialite": 80.0,
        "filter_10k_spatialite": 250.0,
        "filter_1k_ogr": 150.0,
        "filter_10k_ogr": 800.0,
    }
    
    REGRESSION_THRESHOLD = 0.05  # 5%
    
    def __init__(self, version: str = "3.0.0"):
        """
        Initialize benchmark runner.
        
        Args:
            version: FilterMate version being benchmarked
        """
        self.version = version
        self.results: List[BenchmarkResult] = []
        self.regressions: List[Dict[str, Any]] = []
        self._current_result: Optional[BenchmarkResult] = None
    
    def benchmark(
        self,
        name: str,
        operation: str,
        backend: str,
        dataset_size: int = 1000
    ):
        """
        Context manager for running a benchmark.
        
        Args:
            name: Benchmark name
            operation: Operation type
            backend: Backend name
            dataset_size: Dataset size
            
        Returns:
            Context manager that measures execution time
        """
        return _BenchmarkContext(self, name, operation, backend, dataset_size)
    
    def record_result(self, result: BenchmarkResult) -> None:
        """
        Record a benchmark result and check for regression.
        
        Args:
            result: Benchmark result to record
        """
        self.results.append(result)
        
        # Check for regression
        baseline_key = f"{result.operation}_{result.dataset_size // 1000}k_{result.backend}"
        baseline = self.BASELINES.get(baseline_key)
        
        if baseline:
            regression = (result.duration_ms - baseline) / baseline
            if regression > self.REGRESSION_THRESHOLD:
                self.regressions.append({
                    "name": result.name,
                    "baseline_ms": baseline,
                    "measured_ms": result.duration_ms,
                    "regression_percent": regression * 100
                })
    
    def get_summary(self) -> BenchmarkSummary:
        """
        Get benchmark summary.
        
        Returns:
            Summary with all results and regression info
        """
        return BenchmarkSummary(
            generated_at=datetime.now().isoformat(),
            version=self.version,
            total_tests=len(self.results),
            passed=len(self.results) - len(self.regressions),
            failed=len(self.regressions),
            regressions=self.regressions,
            results=self.results
        )
    
    def save_report(self, output_path: Path) -> None:
        """
        Save benchmark report to file.
        
        Args:
            output_path: Path to save report
        """
        summary = self.get_summary()
        
        # Save JSON
        json_path = output_path.with_suffix(".json")
        with open(json_path, "w") as f:
            json.dump({
                "generated_at": summary.generated_at,
                "version": summary.version,
                "total_tests": summary.total_tests,
                "passed": summary.passed,
                "failed": summary.failed,
                "regressions": summary.regressions,
                "results": [r.to_dict() for r in summary.results]
            }, f, indent=2)


class _BenchmarkContext:
    """Context manager for individual benchmark."""
    
    def __init__(
        self,
        runner: BenchmarkRunner,
        name: str,
        operation: str,
        backend: str,
        dataset_size: int
    ):
        self.runner = runner
        self.name = name
        self.operation = operation
        self.backend = backend
        self.dataset_size = dataset_size
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        result = BenchmarkResult(
            name=self.name,
            operation=self.operation,
            backend=self.backend,
            dataset_size=self.dataset_size,
            duration_ms=duration_ms
        )
        
        self.runner.record_result(result)
        return False


class MemoryTracker:
    """
    Track memory usage during operations.
    
    Example:
        with MemoryTracker() as tracker:
            # Run operation
            pass
        
        print(f"Peak memory: {tracker.peak_mb}MB")
    """
    
    def __init__(self):
        self.initial_mb = 0.0
        self.peak_mb = 0.0
        self.final_mb = 0.0
    
    def __enter__(self):
        # In real implementation, would use psutil or similar
        self.initial_mb = self._get_memory_mb()
        return self
    
    def __exit__(self, *args):
        self.final_mb = self._get_memory_mb()
        return False
    
    def _get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024  # Convert to MB
        except ImportError:
            return 0.0
    
    @property
    def delta_mb(self) -> float:
        """Memory change during operation."""
        return self.final_mb - self.initial_mb


def format_benchmark_report(summary: BenchmarkSummary) -> str:
    """
    Format benchmark summary as readable text.
    
    Args:
        summary: Benchmark summary
        
    Returns:
        Formatted text report
    """
    lines = [
        "=" * 60,
        "FilterMate Performance Benchmark Report",
        "=" * 60,
        f"Version: {summary.version}",
        f"Generated: {summary.generated_at}",
        "",
        f"Total Tests: {summary.total_tests}",
        f"Passed: {summary.passed}",
        f"Failed (Regressions): {summary.failed}",
        "",
    ]
    
    if summary.regressions:
        lines.append("REGRESSIONS DETECTED:")
        lines.append("-" * 40)
        for reg in summary.regressions:
            lines.append(
                f"  {reg['name']}: "
                f"{reg['measured_ms']:.2f}ms vs {reg['baseline_ms']:.2f}ms "
                f"(+{reg['regression_percent']:.1f}%)"
            )
        lines.append("")
    
    lines.append("All Results:")
    lines.append("-" * 40)
    for result in summary.results:
        lines.append(
            f"  {result.name}: {result.duration_ms:.2f}ms "
            f"({result.backend}, {result.dataset_size} features)"
        )
    
    lines.append("=" * 60)
    
    return "\n".join(lines)
