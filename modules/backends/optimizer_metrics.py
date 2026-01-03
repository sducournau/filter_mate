# -*- coding: utf-8 -*-
"""
Optimizer Metrics and Statistics Collection for FilterMate

This module provides:
1. Performance metrics collection for optimization decisions
2. Adaptive threshold tuning based on observed performance
3. Query pattern detection and caching
4. Optimization effectiveness reporting

v2.8.0: Initial implementation
"""

import time
import statistics
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, OrderedDict
from threading import Lock


class OptimizationMetricType(Enum):
    """Types of metrics collected."""
    QUERY_TIME = "query_time"
    SPEEDUP_RATIO = "speedup_ratio"
    MEMORY_USAGE = "memory_usage"
    ROWS_PROCESSED = "rows_processed"
    ROWS_RETURNED = "rows_returned"
    CACHE_HIT = "cache_hit"
    STRATEGY_USED = "strategy_used"


@dataclass
class OptimizationMetric:
    """Single optimization metric measurement."""
    metric_type: OptimizationMetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    layer_id: Optional[str] = None
    strategy: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationSession:
    """Tracks metrics for a single optimization session."""
    session_id: str
    layer_id: str
    layer_name: str
    feature_count: int
    start_time: float
    end_time: Optional[float] = None
    strategy_used: Optional[str] = None
    estimated_speedup: float = 1.0
    actual_speedup: float = 1.0
    metrics: List[OptimizationMetric] = field(default_factory=list)
    
    # Timing breakdown
    analysis_time_ms: float = 0.0
    planning_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    baseline_estimate_ms: float = 0.0
    
    def calculate_actual_speedup(self, baseline_ms: float) -> float:
        """Calculate actual speedup compared to baseline."""
        if self.execution_time_ms > 0 and baseline_ms > 0:
            self.actual_speedup = baseline_ms / self.execution_time_ms
        return self.actual_speedup
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary."""
        total_time = (self.end_time - self.start_time) * 1000 if self.end_time else 0
        return {
            'session_id': self.session_id,
            'layer_name': self.layer_name,
            'feature_count': self.feature_count,
            'strategy': self.strategy_used,
            'estimated_speedup': round(self.estimated_speedup, 2),
            'actual_speedup': round(self.actual_speedup, 2),
            'speedup_accuracy': round(self.actual_speedup / max(0.1, self.estimated_speedup) * 100, 1),
            'total_time_ms': round(total_time, 1),
            'analysis_time_ms': round(self.analysis_time_ms, 1),
            'execution_time_ms': round(self.execution_time_ms, 1),
        }


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache with TTL support.
    
    Features:
    - Automatic eviction of least recently used entries
    - Time-to-live (TTL) expiration
    - Thread-safe operations
    - Hit/miss statistics
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: float = 300.0):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds (0 = no expiration)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = Lock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            # Check TTL
            if self.ttl_seconds > 0:
                age = time.time() - self._timestamps.get(key, 0)
                if age > self.ttl_seconds:
                    # Expired
                    del self._cache[key]
                    del self._timestamps[key]
                    self._misses += 1
                    return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Remove existing if present
            if key in self._cache:
                del self._cache[key]
            
            # Add new entry at end
            self._cache[key] = value
            self._timestamps[key] = time.time()
            
            # Evict if over capacity
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._timestamps.pop(oldest_key, None)
    
    def invalidate(self, key: str) -> bool:
        """
        Remove specific entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if entry was removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._timestamps.pop(key, None)
                return True
            return False
    
    def invalidate_pattern(self, pattern_fn: Callable[[str], bool]) -> int:
        """
        Remove entries matching a pattern.
        
        Args:
            pattern_fn: Function that returns True for keys to remove
            
        Returns:
            Number of entries removed
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache if pattern_fn(k)]
            for key in keys_to_remove:
                del self._cache[key]
                self._timestamps.pop(key, None)
            return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': round(hit_rate * 100, 1),
        }
    
    def reset_stats(self) -> None:
        """Reset hit/miss statistics."""
        self._hits = 0
        self._misses = 0


class QueryPatternDetector:
    """
    Detects recurring query patterns for pre-optimization.
    
    Tracks query patterns and suggests optimizations for frequently
    used filter combinations.
    """
    
    def __init__(self, pattern_threshold: int = 3):
        """
        Initialize pattern detector.
        
        Args:
            pattern_threshold: Minimum occurrences to consider a pattern
        """
        self.pattern_threshold = pattern_threshold
        self._patterns: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'avg_time_ms': 0.0,
            'best_strategy': None,
            'last_seen': 0.0,
            'attributes': [],
            'predicates': [],
        })
        self._lock = Lock()
    
    def record_query(
        self,
        layer_id: str,
        attribute_filter: Optional[str],
        spatial_predicates: Optional[List[str]],
        execution_time_ms: float,
        strategy_used: str,
        success: bool = True
    ) -> Optional[str]:
        """
        Record a query execution and return pattern key if detected.
        
        Args:
            layer_id: Layer identifier
            attribute_filter: Attribute filter expression (normalized)
            spatial_predicates: List of spatial predicates used
            execution_time_ms: Query execution time
            strategy_used: Optimization strategy used
            success: Whether query was successful
            
        Returns:
            Pattern key if a recurring pattern is detected
        """
        # Generate pattern key
        pattern_key = self._generate_pattern_key(
            layer_id, attribute_filter, spatial_predicates
        )
        
        with self._lock:
            pattern = self._patterns[pattern_key]
            pattern['count'] += 1
            
            # Update rolling average
            old_avg = pattern['avg_time_ms']
            count = pattern['count']
            pattern['avg_time_ms'] = old_avg + (execution_time_ms - old_avg) / count
            
            # Track best performing strategy
            if pattern['best_strategy'] is None or execution_time_ms < pattern.get('best_time_ms', float('inf')):
                pattern['best_strategy'] = strategy_used
                pattern['best_time_ms'] = execution_time_ms
            
            pattern['last_seen'] = time.time()
            
            # Return pattern key if threshold reached
            if pattern['count'] >= self.pattern_threshold:
                return pattern_key
        
        return None
    
    def get_recommended_strategy(
        self,
        layer_id: str,
        attribute_filter: Optional[str],
        spatial_predicates: Optional[List[str]]
    ) -> Optional[Tuple[str, float]]:
        """
        Get recommended strategy based on historical patterns.
        
        Args:
            layer_id: Layer identifier
            attribute_filter: Attribute filter expression
            spatial_predicates: Spatial predicates
            
        Returns:
            Tuple of (strategy_name, confidence) or None
        """
        pattern_key = self._generate_pattern_key(
            layer_id, attribute_filter, spatial_predicates
        )
        
        with self._lock:
            if pattern_key in self._patterns:
                pattern = self._patterns[pattern_key]
                if pattern['count'] >= self.pattern_threshold:
                    # Confidence based on number of observations
                    confidence = min(1.0, pattern['count'] / 10.0)
                    return (pattern['best_strategy'], confidence)
        
        return None
    
    def _generate_pattern_key(
        self,
        layer_id: str,
        attribute_filter: Optional[str],
        spatial_predicates: Optional[List[str]]
    ) -> str:
        """Generate a pattern key for the query."""
        # Normalize attribute filter (extract field names only)
        attr_pattern = self._normalize_expression(attribute_filter) if attribute_filter else ""
        
        # Normalize spatial predicates
        pred_pattern = "|".join(sorted(spatial_predicates or []))
        
        return f"{layer_id}:{attr_pattern}:{pred_pattern}"
    
    def _normalize_expression(self, expression: str) -> str:
        """
        Normalize expression to pattern (extract structure, not values).
        
        Example: "status = 'active' AND type = 'A'" -> "status=?:type=?"
        """
        import re
        
        # Extract field names and operators
        field_pattern = r'(\w+)\s*(=|!=|<>|<|>|<=|>=|LIKE|IN|IS)\s*'
        matches = re.findall(field_pattern, expression, re.IGNORECASE)
        
        if matches:
            return ":".join(f"{m[0]}={m[1]}" for m in matches)
        
        return expression[:50]  # Fallback: truncated expression
    
    def get_patterns_summary(self) -> List[Dict[str, Any]]:
        """Get summary of detected patterns."""
        with self._lock:
            return [
                {
                    'pattern': key,
                    **{k: v for k, v in data.items() if k != 'best_time_ms'}
                }
                for key, data in self._patterns.items()
                if data['count'] >= self.pattern_threshold
            ]
    
    def clear_old_patterns(self, max_age_hours: float = 24.0) -> int:
        """
        Clear patterns not seen recently.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of patterns cleared
        """
        cutoff = time.time() - (max_age_hours * 3600)
        removed = 0
        
        with self._lock:
            keys_to_remove = [
                k for k, v in self._patterns.items()
                if v['last_seen'] < cutoff
            ]
            for key in keys_to_remove:
                del self._patterns[key]
                removed += 1
        
        return removed


class AdaptiveThresholdManager:
    """
    Dynamically adjusts optimization thresholds based on observed performance.
    
    Uses exponential moving averages to smooth threshold adjustments
    and prevent oscillation.
    """
    
    # Default thresholds
    DEFAULT_THRESHOLDS = {
        'centroid_threshold_distant': 5000,
        'centroid_threshold_local': 50000,
        'attribute_first_selectivity': 0.3,
        'bbox_prefilter_selectivity': 0.5,
        'chunk_size_base': 10000,
        'small_dataset': 1000,
        'medium_dataset': 50000,
        'large_dataset': 200000,
    }
    
    def __init__(self, smoothing_factor: float = 0.3):
        """
        Initialize adaptive threshold manager.
        
        Args:
            smoothing_factor: EMA smoothing factor (0-1, higher = more reactive)
        """
        self.smoothing_factor = smoothing_factor
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)
        self._observations: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        self._lock = Lock()
    
    def get_threshold(self, name: str) -> float:
        """Get current threshold value."""
        with self._lock:
            return self._thresholds.get(name, self.DEFAULT_THRESHOLDS.get(name, 0))
    
    def record_observation(
        self,
        threshold_name: str,
        threshold_value: float,
        was_beneficial: bool,
        speedup_achieved: float = 1.0
    ) -> None:
        """
        Record an observation about threshold effectiveness.
        
        Args:
            threshold_name: Name of the threshold
            threshold_value: Value that was used
            was_beneficial: Whether using this threshold was beneficial
            speedup_achieved: Speedup ratio achieved (1.0 = no change)
        """
        with self._lock:
            # Store observation with benefit score
            benefit_score = speedup_achieved if was_beneficial else 1.0 / max(0.1, speedup_achieved)
            self._observations[threshold_name].append((threshold_value, benefit_score))
            
            # Keep only recent observations
            if len(self._observations[threshold_name]) > 100:
                self._observations[threshold_name] = self._observations[threshold_name][-100:]
            
            # Adjust threshold if enough observations
            if len(self._observations[threshold_name]) >= 10:
                self._adjust_threshold(threshold_name)
    
    def _adjust_threshold(self, threshold_name: str) -> None:
        """Adjust threshold based on observations using EMA."""
        observations = self._observations[threshold_name]
        
        if not observations:
            return
        
        # Find observations with best benefit scores
        sorted_obs = sorted(observations, key=lambda x: x[1], reverse=True)
        
        # Take top 30% as "optimal" observations
        top_count = max(3, len(sorted_obs) // 3)
        optimal_values = [obs[0] for obs in sorted_obs[:top_count]]
        
        if optimal_values:
            # Calculate suggested threshold as median of optimal values
            suggested = statistics.median(optimal_values)
            current = self._thresholds[threshold_name]
            
            # Apply EMA smoothing
            new_value = current + self.smoothing_factor * (suggested - current)
            
            # Bound to reasonable range (50% - 200% of default)
            default = self.DEFAULT_THRESHOLDS.get(threshold_name, current)
            new_value = max(default * 0.5, min(default * 2.0, new_value))
            
            self._thresholds[threshold_name] = new_value
    
    def get_all_thresholds(self) -> Dict[str, float]:
        """Get all current thresholds."""
        with self._lock:
            return dict(self._thresholds)
    
    def reset_to_defaults(self) -> None:
        """Reset all thresholds to defaults."""
        with self._lock:
            self._thresholds = dict(self.DEFAULT_THRESHOLDS)
            self._observations.clear()


class SelectivityHistogram:
    """
    Simple histogram for estimating selectivity of attribute values.
    
    Uses sampling to build approximate histograms for common fields,
    enabling better selectivity estimation for non-PostgreSQL backends.
    """
    
    def __init__(self, num_buckets: int = 20):
        """
        Initialize histogram.
        
        Args:
            num_buckets: Number of histogram buckets
        """
        self.num_buckets = num_buckets
        self._histograms: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def build_histogram(
        self,
        layer_id: str,
        field_name: str,
        values: List[Any]
    ) -> None:
        """
        Build histogram for a field from sampled values.
        
        Args:
            layer_id: Layer identifier
            field_name: Field name
            values: Sampled values
        """
        if not values:
            return
        
        key = f"{layer_id}:{field_name}"
        
        # Determine value type and build appropriate histogram
        sample = values[0]
        
        with self._lock:
            if isinstance(sample, (int, float)):
                self._histograms[key] = self._build_numeric_histogram(values)
            else:
                self._histograms[key] = self._build_categorical_histogram(values)
            
            self._histograms[key]['total_sampled'] = len(values)
            self._histograms[key]['timestamp'] = time.time()
    
    def _build_numeric_histogram(self, values: List[float]) -> Dict[str, Any]:
        """Build histogram for numeric values."""
        numeric_vals = [v for v in values if isinstance(v, (int, float)) and v is not None]
        
        if not numeric_vals:
            return {'type': 'empty'}
        
        min_val = min(numeric_vals)
        max_val = max(numeric_vals)
        
        if min_val == max_val:
            return {
                'type': 'numeric',
                'min': min_val,
                'max': max_val,
                'buckets': [len(numeric_vals)],
                'bucket_width': 0,
            }
        
        bucket_width = (max_val - min_val) / self.num_buckets
        buckets = [0] * self.num_buckets
        
        for val in numeric_vals:
            bucket_idx = min(int((val - min_val) / bucket_width), self.num_buckets - 1)
            buckets[bucket_idx] += 1
        
        return {
            'type': 'numeric',
            'min': min_val,
            'max': max_val,
            'buckets': buckets,
            'bucket_width': bucket_width,
        }
    
    def _build_categorical_histogram(self, values: List[Any]) -> Dict[str, Any]:
        """Build histogram for categorical values."""
        from collections import Counter
        
        value_counts = Counter(str(v) for v in values if v is not None)
        
        # Keep top categories
        top_categories = dict(value_counts.most_common(self.num_buckets))
        other_count = sum(v for k, v in value_counts.items() if k not in top_categories)
        
        return {
            'type': 'categorical',
            'categories': top_categories,
            'other_count': other_count,
            'distinct_count': len(value_counts),
        }
    
    def estimate_selectivity(
        self,
        layer_id: str,
        field_name: str,
        operator: str,
        value: Any
    ) -> float:
        """
        Estimate selectivity for a condition.
        
        Args:
            layer_id: Layer identifier
            field_name: Field name
            operator: Comparison operator (=, <, >, etc.)
            value: Comparison value
            
        Returns:
            Estimated selectivity (0.0 to 1.0)
        """
        key = f"{layer_id}:{field_name}"
        
        with self._lock:
            if key not in self._histograms:
                return 0.5  # No histogram - assume 50%
            
            hist = self._histograms[key]
            total = hist.get('total_sampled', 1)
            
            if hist['type'] == 'categorical':
                return self._estimate_categorical_selectivity(hist, operator, value, total)
            elif hist['type'] == 'numeric':
                return self._estimate_numeric_selectivity(hist, operator, value, total)
            
            return 0.5
    
    def _estimate_categorical_selectivity(
        self,
        hist: Dict,
        operator: str,
        value: Any,
        total: int
    ) -> float:
        """Estimate selectivity for categorical field."""
        str_value = str(value)
        categories = hist.get('categories', {})
        
        if operator in ('=', '=='):
            count = categories.get(str_value, 0)
            return count / max(1, total)
        elif operator in ('!=', '<>'):
            count = categories.get(str_value, 0)
            return 1.0 - (count / max(1, total))
        elif operator.upper() == 'IN':
            # Assume value is a list
            if isinstance(value, (list, tuple)):
                count = sum(categories.get(str(v), 0) for v in value)
                return count / max(1, total)
        
        return 0.5
    
    def _estimate_numeric_selectivity(
        self,
        hist: Dict,
        operator: str,
        value: float,
        total: int
    ) -> float:
        """Estimate selectivity for numeric field."""
        min_val = hist.get('min', 0)
        max_val = hist.get('max', 0)
        buckets = hist.get('buckets', [])
        bucket_width = hist.get('bucket_width', 0)
        
        if not buckets or bucket_width == 0:
            return 0.5
        
        try:
            value = float(value)
        except (ValueError, TypeError):
            return 0.5
        
        if operator in ('=', '=='):
            # Point estimate - small fraction
            return 1.0 / max(1, hist.get('distinct_count', total))
        
        elif operator in ('<', '<='):
            if value <= min_val:
                return 0.0
            if value >= max_val:
                return 1.0
            
            # Sum buckets up to value
            bucket_idx = min(int((value - min_val) / bucket_width), len(buckets) - 1)
            count = sum(buckets[:bucket_idx + 1])
            return count / max(1, total)
        
        elif operator in ('>', '>='):
            if value >= max_val:
                return 0.0
            if value <= min_val:
                return 1.0
            
            bucket_idx = min(int((value - min_val) / bucket_width), len(buckets) - 1)
            count = sum(buckets[bucket_idx:])
            return count / max(1, total)
        
        elif operator == 'BETWEEN':
            # Assume value is a tuple (low, high)
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                low, high = float(value[0]), float(value[1])
                low_idx = max(0, int((low - min_val) / bucket_width))
                high_idx = min(len(buckets) - 1, int((high - min_val) / bucket_width))
                count = sum(buckets[low_idx:high_idx + 1])
                return count / max(1, total)
        
        return 0.5


class OptimizationMetricsCollector:
    """
    Central collector for optimization metrics and statistics.
    
    Provides a unified interface for:
    - Recording optimization sessions
    - Tracking performance metrics
    - Generating reports
    - Adaptive threshold updates
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern for global metrics collection."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize metrics collector."""
        if self._initialized:
            return
        
        self._sessions: Dict[str, OptimizationSession] = {}
        self._completed_sessions: List[OptimizationSession] = []
        self._max_completed = 1000  # Keep last N completed sessions
        
        # Sub-components
        self.cache = LRUCache(max_size=200, ttl_seconds=600.0)
        self.pattern_detector = QueryPatternDetector()
        self.threshold_manager = AdaptiveThresholdManager()
        self.histograms = SelectivityHistogram()
        
        # Global statistics
        self._total_queries = 0
        self._total_optimized = 0
        self._total_speedup = 0.0
        
        self._initialized = True
    
    def start_session(
        self,
        layer_id: str,
        layer_name: str,
        feature_count: int
    ) -> str:
        """
        Start a new optimization session.
        
        Args:
            layer_id: Layer identifier
            layer_name: Layer display name
            feature_count: Number of features
            
        Returns:
            Session ID
        """
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        session = OptimizationSession(
            session_id=session_id,
            layer_id=layer_id,
            layer_name=layer_name,
            feature_count=feature_count,
            start_time=time.time()
        )
        
        self._sessions[session_id] = session
        return session_id
    
    def record_analysis_time(self, session_id: str, time_ms: float) -> None:
        """Record time spent on layer analysis."""
        if session_id in self._sessions:
            self._sessions[session_id].analysis_time_ms = time_ms
    
    def record_planning_time(self, session_id: str, time_ms: float) -> None:
        """Record time spent on optimization planning."""
        if session_id in self._sessions:
            self._sessions[session_id].planning_time_ms = time_ms
    
    def record_strategy(
        self,
        session_id: str,
        strategy: str,
        estimated_speedup: float
    ) -> None:
        """Record optimization strategy selected."""
        if session_id in self._sessions:
            self._sessions[session_id].strategy_used = strategy
            self._sessions[session_id].estimated_speedup = estimated_speedup
    
    def end_session(
        self,
        session_id: str,
        execution_time_ms: float,
        baseline_estimate_ms: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        End an optimization session.
        
        Args:
            session_id: Session identifier
            execution_time_ms: Actual execution time
            baseline_estimate_ms: Estimated time without optimization
            
        Returns:
            Session summary dictionary
        """
        if session_id not in self._sessions:
            return None
        
        session = self._sessions.pop(session_id)
        session.end_time = time.time()
        session.execution_time_ms = execution_time_ms
        
        if baseline_estimate_ms:
            session.baseline_estimate_ms = baseline_estimate_ms
            session.calculate_actual_speedup(baseline_estimate_ms)
        
        # Update global stats
        self._total_queries += 1
        if session.strategy_used and session.strategy_used != 'direct':
            self._total_optimized += 1
            self._total_speedup += session.actual_speedup
        
        # Store completed session
        self._completed_sessions.append(session)
        if len(self._completed_sessions) > self._max_completed:
            self._completed_sessions = self._completed_sessions[-self._max_completed:]
        
        # Update adaptive thresholds
        if session.strategy_used:
            was_beneficial = session.actual_speedup > 1.0
            self.threshold_manager.record_observation(
                f"strategy_{session.strategy_used}",
                session.feature_count,
                was_beneficial,
                session.actual_speedup
            )
        
        return session.to_summary_dict()
    
    def get_layer_cache_key(
        self,
        layer_id: str,
        attribute_filter: Optional[str] = None,
        predicates: Optional[List[str]] = None
    ) -> str:
        """Generate cache key for layer analysis."""
        parts = [layer_id]
        if attribute_filter:
            parts.append(f"attr:{hash(attribute_filter)}")
        if predicates:
            parts.append(f"pred:{','.join(sorted(predicates))}")
        return ":".join(parts)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get global optimization statistics."""
        avg_speedup = (
            self._total_speedup / max(1, self._total_optimized)
        ) if self._total_optimized > 0 else 1.0
        
        return {
            'total_queries': self._total_queries,
            'total_optimized': self._total_optimized,
            'optimization_rate': round(
                self._total_optimized / max(1, self._total_queries) * 100, 1
            ),
            'average_speedup': round(avg_speedup, 2),
            'cache_stats': self.cache.stats,
            'active_sessions': len(self._sessions),
            'thresholds': self.threshold_manager.get_all_thresholds(),
            'patterns_detected': len(self.pattern_detector.get_patterns_summary()),
        }
    
    def get_recent_sessions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get summaries of recent optimization sessions."""
        recent = self._completed_sessions[-count:]
        return [s.to_summary_dict() for s in reversed(recent)]
    
    def clear_all(self) -> None:
        """Clear all metrics and reset state."""
        self._sessions.clear()
        self._completed_sessions.clear()
        self.cache.clear()
        self.threshold_manager.reset_to_defaults()
        self._total_queries = 0
        self._total_optimized = 0
        self._total_speedup = 0.0


# Global instance accessor
def get_metrics_collector() -> OptimizationMetricsCollector:
    """Get the global metrics collector instance."""
    return OptimizationMetricsCollector()
