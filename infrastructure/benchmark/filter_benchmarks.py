# -*- coding: utf-8 -*-
"""
Filter Operation Benchmarks for FilterMate.

v4.1.1 - January 2026 - EPIC-3 Sprint 1

PURPOSE:
Benchmark suite for measuring filter operation performance:
1. Simple expression filters
2. Complex multi-condition filters
3. IN clause filters (large value lists)
4. NULL/NOT NULL filters
5. String pattern matching (LIKE/ILIKE)

USAGE:
    from infrastructure.benchmark import FilterBenchmarks
    
    suite = FilterBenchmarks(layer=my_layer)
    results = suite.run_all()
    
    for result in results:
        print(result.summary())
"""

import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass

from .framework import BenchmarkRunner, BenchmarkResult, BenchmarkSuite, Timer

try:
    from qgis.core import QgsVectorLayer, QgsFeatureRequest, QgsExpression
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

logger = logging.getLogger('FilterMate.Benchmark.Filter')


@dataclass
class FilterBenchmarkConfig:
    """Configuration for filter benchmarks."""
    iterations: int = 10
    warmup: int = 2
    test_expressions: List[str] = None
    
    def __post_init__(self):
        if self.test_expressions is None:
            self.test_expressions = []


class FilterBenchmarks:
    """
    Benchmark suite for filter operations.
    
    Tests various filter expression types against a layer to measure
    performance characteristics.
    
    Example:
        layer = QgsProject.instance().mapLayersByName("my_layer")[0]
        benchmarks = FilterBenchmarks(layer)
        
        # Run all standard benchmarks
        results = benchmarks.run_all()
        
        # Run specific benchmark
        result = benchmarks.benchmark_simple_equality()
    """
    
    def __init__(
        self,
        layer: 'QgsVectorLayer' = None,
        config: FilterBenchmarkConfig = None,
    ):
        """
        Initialize filter benchmarks.
        
        Args:
            layer: Layer to benchmark against
            config: Benchmark configuration
        """
        self.layer = layer
        self.config = config or FilterBenchmarkConfig()
        self.runner = BenchmarkRunner(
            iterations=self.config.iterations,
            warmup=self.config.warmup,
        )
        self._results: List[BenchmarkResult] = []
        
        # Store original filter
        self._original_filter = layer.subsetString() if layer else ""
    
    def _reset_filter(self) -> None:
        """Reset layer filter to original state."""
        if self.layer:
            self.layer.setSubsetString(self._original_filter)
    
    def _apply_filter(self, expression: str) -> int:
        """
        Apply filter and return feature count.
        
        Args:
            expression: Filter expression
            
        Returns:
            Number of features matching filter
        """
        if not self.layer:
            return 0
        
        self.layer.setSubsetString(expression)
        return self.layer.featureCount()
    
    def _get_field_name(self, field_type: str = 'string') -> Optional[str]:
        """Get a field name of the specified type."""
        if not self.layer:
            return None
        
        from qgis.core import QVariant
        
        type_map = {
            'string': [QVariant.String],
            'integer': [QVariant.Int, QVariant.LongLong],
            'double': [QVariant.Double],
            'any': None,
        }
        
        target_types = type_map.get(field_type)
        
        for field in self.layer.fields():
            if target_types is None or field.type() in target_types:
                return field.name()
        
        return None
    
    def benchmark_simple_equality(self, field_name: str = None, value: Any = None) -> BenchmarkResult:
        """
        Benchmark simple equality filter (field = value).
        
        Args:
            field_name: Field to filter on (auto-detect if None)
            value: Value to compare (auto-detect if None)
        """
        if not self.layer:
            return BenchmarkResult(name="simple_equality", description="No layer")
        
        field = field_name or self._get_field_name('string')
        if not field:
            return BenchmarkResult(name="simple_equality", description="No suitable field")
        
        # Get a sample value
        if value is None:
            for feature in self.layer.getFeatures():
                value = feature[field]
                if value is not None:
                    break
        
        if isinstance(value, str):
            expr = f'"{field}" = \'{value}\''
        else:
            expr = f'"{field}" = {value}'
        
        def run_filter():
            self._apply_filter(expr)
        
        self.runner.add(
            "filter.simple_equality",
            run_filter,
            f"Simple equality filter: {expr}",
            {'expression': expr, 'field': field}
        )
        
        result = self.runner.run("filter.simple_equality", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def benchmark_comparison(self, field_name: str = None) -> BenchmarkResult:
        """Benchmark comparison operators (>, <, >=, <=)."""
        if not self.layer:
            return BenchmarkResult(name="comparison", description="No layer")
        
        field = field_name or self._get_field_name('integer') or self._get_field_name('double')
        if not field:
            return BenchmarkResult(name="comparison", description="No numeric field")
        
        # Get median value for comparison
        values = []
        for i, feature in enumerate(self.layer.getFeatures()):
            if i >= 1000:
                break
            val = feature[field]
            if val is not None:
                values.append(val)
        
        if not values:
            return BenchmarkResult(name="comparison", description="No values")
        
        median_val = sorted(values)[len(values) // 2]
        expr = f'"{field}" > {median_val}'
        
        def run_filter():
            self._apply_filter(expr)
        
        self.runner.add(
            "filter.comparison",
            run_filter,
            f"Comparison filter: {expr}",
            {'expression': expr, 'field': field}
        )
        
        result = self.runner.run("filter.comparison", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def benchmark_in_clause(self, field_name: str = None, num_values: int = 100) -> BenchmarkResult:
        """
        Benchmark IN clause filter with multiple values.
        
        Args:
            field_name: Field to filter on
            num_values: Number of values in IN clause
        """
        if not self.layer:
            return BenchmarkResult(name="in_clause", description="No layer")
        
        field = field_name or self._get_field_name('any')
        if not field:
            return BenchmarkResult(name="in_clause", description="No suitable field")
        
        # Collect unique values
        unique_values = set()
        for feature in self.layer.getFeatures():
            val = feature[field]
            if val is not None:
                unique_values.add(val)
            if len(unique_values) >= num_values:
                break
        
        if not unique_values:
            return BenchmarkResult(name="in_clause", description="No values")
        
        # Build IN clause
        values_list = list(unique_values)[:num_values]
        if isinstance(values_list[0], str):
            values_str = ", ".join(f"'{v}'" for v in values_list)
        else:
            values_str = ", ".join(str(v) for v in values_list)
        
        expr = f'"{field}" IN ({values_str})'
        
        def run_filter():
            self._apply_filter(expr)
        
        self.runner.add(
            f"filter.in_clause_{num_values}",
            run_filter,
            f"IN clause filter with {num_values} values",
            {'expression': expr[:100], 'field': field, 'num_values': num_values}
        )
        
        result = self.runner.run(f"filter.in_clause_{num_values}", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def benchmark_like_pattern(self, field_name: str = None) -> BenchmarkResult:
        """Benchmark LIKE pattern matching filter."""
        if not self.layer:
            return BenchmarkResult(name="like_pattern", description="No layer")
        
        field = field_name or self._get_field_name('string')
        if not field:
            return BenchmarkResult(name="like_pattern", description="No string field")
        
        expr = f'"{field}" LIKE \'%a%\''
        
        def run_filter():
            self._apply_filter(expr)
        
        self.runner.add(
            "filter.like_pattern",
            run_filter,
            f"LIKE pattern filter: {expr}",
            {'expression': expr, 'field': field}
        )
        
        result = self.runner.run("filter.like_pattern", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def benchmark_null_check(self, field_name: str = None) -> BenchmarkResult:
        """Benchmark NULL/NOT NULL filter."""
        if not self.layer:
            return BenchmarkResult(name="null_check", description="No layer")
        
        field = field_name or self._get_field_name('any')
        if not field:
            return BenchmarkResult(name="null_check", description="No suitable field")
        
        expr = f'"{field}" IS NOT NULL'
        
        def run_filter():
            self._apply_filter(expr)
        
        self.runner.add(
            "filter.null_check",
            run_filter,
            f"NULL check filter: {expr}",
            {'expression': expr, 'field': field}
        )
        
        result = self.runner.run("filter.null_check", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def benchmark_complex_expression(self, expression: str = None) -> BenchmarkResult:
        """
        Benchmark complex multi-condition filter.
        
        Args:
            expression: Custom expression (auto-generate if None)
        """
        if not self.layer:
            return BenchmarkResult(name="complex", description="No layer")
        
        if expression is None:
            # Generate a complex expression
            str_field = self._get_field_name('string')
            num_field = self._get_field_name('integer') or self._get_field_name('double')
            
            parts = []
            if str_field:
                parts.append(f'"{str_field}" IS NOT NULL')
            if num_field:
                parts.append(f'"{num_field}" > 0')
            
            if not parts:
                return BenchmarkResult(name="complex", description="No suitable fields")
            
            expression = " AND ".join(parts)
        
        def run_filter():
            self._apply_filter(expression)
        
        self.runner.add(
            "filter.complex",
            run_filter,
            f"Complex filter: {expression[:50]}...",
            {'expression': expression}
        )
        
        result = self.runner.run("filter.complex", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def benchmark_clear_filter(self) -> BenchmarkResult:
        """Benchmark clearing filter (empty string)."""
        if not self.layer:
            return BenchmarkResult(name="clear_filter", description="No layer")
        
        # First apply a filter
        self._apply_filter('"fid" IS NOT NULL')
        
        def run_clear():
            self.layer.setSubsetString("")
        
        self.runner.add(
            "filter.clear",
            run_clear,
            "Clear filter (empty string)",
        )
        
        result = self.runner.run("filter.clear", teardown=self._reset_filter)
        self._results.append(result)
        return result
    
    def run_all(self) -> List[BenchmarkResult]:
        """
        Run all standard filter benchmarks.
        
        Returns:
            List of BenchmarkResult objects
        """
        if not self.layer:
            logger.error("No layer configured for benchmarks")
            return []
        
        logger.info(f"🚀 Running filter benchmarks on '{self.layer.name()}'")
        logger.info(f"   Features: {self.layer.featureCount():,}")
        
        results = []
        
        try:
            results.append(self.benchmark_simple_equality())
            results.append(self.benchmark_comparison())
            results.append(self.benchmark_in_clause(num_values=10))
            results.append(self.benchmark_in_clause(num_values=100))
            results.append(self.benchmark_like_pattern())
            results.append(self.benchmark_null_check())
            results.append(self.benchmark_complex_expression())
            results.append(self.benchmark_clear_filter())
        finally:
            self._reset_filter()
        
        logger.info(f"✅ Completed {len(results)} filter benchmarks")
        return results
    
    def get_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        return self._results.copy()


def run_filter_benchmarks(
    layer: 'QgsVectorLayer',
    iterations: int = 10,
) -> List[BenchmarkResult]:
    """
    Convenience function to run all filter benchmarks.
    
    Args:
        layer: Layer to benchmark
        iterations: Number of iterations per benchmark
        
    Returns:
        List of BenchmarkResult objects
    """
    config = FilterBenchmarkConfig(iterations=iterations)
    benchmarks = FilterBenchmarks(layer, config)
    return benchmarks.run_all()
