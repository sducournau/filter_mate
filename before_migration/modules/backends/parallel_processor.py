# -*- coding: utf-8 -*-
"""
Parallel Chunk Processing for FilterMate

Provides parallel processing capabilities for large datasets using
Python's concurrent.futures for thread-based parallelism.

IMPORTANT: QGIS objects are NOT thread-safe. This module uses a 
producer-consumer pattern where:
- Main thread: Creates features requests and collects results
- Worker threads: Process geometry operations only (no QGIS API calls)

v2.8.0: Initial implementation
"""

import time
from typing import Dict, List, Optional, Tuple, Set, Any, Callable, Iterator
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from threading import Lock
import queue

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsRectangle,
)

from ..logging_config import get_tasks_logger

logger = get_tasks_logger()

# Check if parallel processing is available and beneficial
PARALLEL_AVAILABLE = True
try:
    import os
    CPU_COUNT = os.cpu_count() or 2
    # Use at most 4 workers to avoid overhead
    DEFAULT_WORKERS = min(4, max(2, CPU_COUNT - 1))
except Exception:
    PARALLEL_AVAILABLE = False
    CPU_COUNT = 1
    DEFAULT_WORKERS = 1


@dataclass
class ChunkResult:
    """Result from processing a single chunk."""
    chunk_id: int
    matching_fids: Set[int]
    processed_count: int
    execution_time_ms: float
    error: Optional[str] = None


@dataclass
class ParallelProcessingStats:
    """Statistics from parallel processing operation."""
    total_features: int
    total_chunks: int
    total_matching: int
    total_time_ms: float
    workers_used: int
    chunk_times_ms: List[float] = field(default_factory=list)
    
    @property
    def avg_chunk_time_ms(self) -> float:
        return sum(self.chunk_times_ms) / len(self.chunk_times_ms) if self.chunk_times_ms else 0.0
    
    @property
    def speedup_vs_sequential(self) -> float:
        """Estimate speedup compared to sequential processing."""
        if not self.chunk_times_ms or self.total_time_ms == 0:
            return 1.0
        sequential_estimate = sum(self.chunk_times_ms)
        return sequential_estimate / self.total_time_ms
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_features': self.total_features,
            'total_chunks': self.total_chunks,
            'total_matching': self.total_matching,
            'total_time_ms': round(self.total_time_ms, 1),
            'workers_used': self.workers_used,
            'avg_chunk_time_ms': round(self.avg_chunk_time_ms, 1),
            'speedup': round(self.speedup_vs_sequential, 2),
        }


class GeometryBatch:
    """
    Thread-safe batch of geometries for parallel processing.
    
    Geometries are pre-extracted from features in the main thread,
    then processed in parallel worker threads.
    """
    
    def __init__(self, chunk_id: int, feature_data: List[Tuple[int, bytes]]):
        """
        Initialize geometry batch.
        
        Args:
            chunk_id: Unique chunk identifier
            feature_data: List of (fid, wkb_bytes) tuples
        """
        self.chunk_id = chunk_id
        self.feature_data = feature_data
        self._processed = False
    
    def process_spatial_predicate(
        self,
        test_geometry_wkb: bytes,
        predicate: str
    ) -> Set[int]:
        """
        Process spatial predicate on all geometries in batch.
        
        This is the worker thread method - uses only QgsGeometry
        which is thread-safe for geometry operations.
        
        Args:
            test_geometry_wkb: WKB bytes of test geometry
            predicate: Spatial predicate name
            
        Returns:
            Set of matching feature IDs
        """
        matching = set()
        
        try:
            # Parse test geometry (thread-safe)
            test_geom = QgsGeometry()
            test_geom.fromWkb(test_geometry_wkb)
            
            if test_geom.isEmpty():
                return matching
            
            for fid, wkb in self.feature_data:
                try:
                    # Parse feature geometry
                    geom = QgsGeometry()
                    geom.fromWkb(wkb)
                    
                    if geom.isEmpty():
                        continue
                    
                    # Apply predicate
                    result = self._apply_predicate(geom, test_geom, predicate)
                    if result:
                        matching.add(fid)
                        
                except Exception as e:
                    logger.debug(f"Geometry error for FID {fid}: {e}")
            
            self._processed = True
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
        
        return matching
    
    def _apply_predicate(
        self,
        geom: QgsGeometry,
        test_geom: QgsGeometry,
        predicate: str
    ) -> bool:
        """Apply spatial predicate."""
        pred_lower = predicate.lower()
        
        if pred_lower == 'intersects':
            return geom.intersects(test_geom)
        elif pred_lower == 'within':
            return geom.within(test_geom)
        elif pred_lower == 'contains':
            return geom.contains(test_geom)
        elif pred_lower == 'overlaps':
            return geom.overlaps(test_geom)
        elif pred_lower == 'touches':
            return geom.touches(test_geom)
        elif pred_lower == 'crosses':
            return geom.crosses(test_geom)
        elif pred_lower == 'disjoint':
            return geom.disjoint(test_geom)
        else:
            # Default to intersects
            return geom.intersects(test_geom)


class ParallelChunkProcessor:
    """
    Parallel processor for large geometry datasets.
    
    Uses a producer-consumer pattern:
    1. Main thread reads features and extracts geometry WKB
    2. Worker threads process geometry predicates in parallel
    3. Results are collected and merged
    
    Thread Safety:
    - QgsVectorLayer access: Main thread only
    - QgsGeometry operations: Thread-safe
    - Result collection: Thread-safe via locks
    """
    
    def __init__(
        self,
        num_workers: int = None,
        chunk_size: int = 5000
    ):
        """
        Initialize parallel processor.
        
        Args:
            num_workers: Number of worker threads (default: auto)
            chunk_size: Features per chunk
        """
        self.num_workers = num_workers or DEFAULT_WORKERS
        self.chunk_size = chunk_size
        self._cancel_requested = False
        self._result_lock = Lock()
    
    def process_spatial_filter_parallel(
        self,
        layer: QgsVectorLayer,
        test_geometry: QgsGeometry,
        predicate: str = 'intersects',
        pre_filter_fids: Optional[Set[int]] = None,
        bbox_prefilter: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Tuple[Set[int], ParallelProcessingStats]:
        """
        Process spatial filter using parallel workers.
        
        Args:
            layer: Target layer
            test_geometry: Geometry to test against
            predicate: Spatial predicate name
            pre_filter_fids: Optional set of pre-filtered FIDs
            bbox_prefilter: Whether to apply bbox pre-filter
            progress_callback: (current, total, message) callback
            
        Returns:
            Tuple of (matching_fids, stats)
        """
        self._cancel_requested = False
        start_time = time.time()
        
        # Determine total features to process
        if pre_filter_fids is not None:
            total_features = len(pre_filter_fids)
        else:
            total_features = layer.featureCount()
        
        # For small datasets, use sequential processing
        if total_features < self.chunk_size * 2:
            logger.debug(f"Dataset too small for parallel ({total_features}), using sequential")
            return self._process_sequential(
                layer, test_geometry, predicate, pre_filter_fids, progress_callback
            )
        
        # Prepare test geometry WKB (for thread safety)
        test_wkb = test_geometry.asWkb()
        test_bbox = test_geometry.boundingBox()
        
        # Build feature request
        request = QgsFeatureRequest()
        
        if pre_filter_fids is not None:
            if len(pre_filter_fids) == 0:
                return set(), ParallelProcessingStats(0, 0, 0, 0, 0)
            request.setFilterFids(list(pre_filter_fids))
        
        if bbox_prefilter and test_bbox and not test_bbox.isNull():
            request.setFilterRect(test_bbox)
        
        # Extract geometries in main thread and create batches
        batches = []
        current_batch = []
        chunk_id = 0
        
        for feat in layer.getFeatures(request):
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                # Store as WKB for thread safety
                current_batch.append((feat.id(), geom.asWkb()))
                
                if len(current_batch) >= self.chunk_size:
                    batches.append(GeometryBatch(chunk_id, current_batch))
                    current_batch = []
                    chunk_id += 1
        
        # Final batch
        if current_batch:
            batches.append(GeometryBatch(chunk_id, current_batch))
        
        if not batches:
            return set(), ParallelProcessingStats(0, 0, 0, 0, 0)
        
        # Process batches in parallel
        all_matching = set()
        chunk_times = []
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            # Submit all batches
            future_to_batch: Dict[Future, GeometryBatch] = {}
            
            for batch in batches:
                if self._cancel_requested:
                    break
                    
                future = executor.submit(
                    batch.process_spatial_predicate,
                    test_wkb,
                    predicate
                )
                future_to_batch[future] = batch
            
            # Collect results as they complete
            for future in as_completed(future_to_batch):
                if self._cancel_requested:
                    break
                
                batch = future_to_batch[future]
                batch_start = time.time()
                
                try:
                    matching = future.result(timeout=60.0)
                    
                    with self._result_lock:
                        all_matching.update(matching)
                    
                    processed_count += len(batch.feature_data)
                    chunk_times.append((time.time() - batch_start) * 1000)
                    
                    if progress_callback:
                        progress_callback(
                            processed_count,
                            total_features,
                            f"Chunk {batch.chunk_id + 1}/{len(batches)}: {len(matching)} matches"
                        )
                
                except Exception as e:
                    logger.error(f"Chunk {batch.chunk_id} failed: {e}")
        
        total_time = (time.time() - start_time) * 1000
        
        stats = ParallelProcessingStats(
            total_features=processed_count,
            total_chunks=len(batches),
            total_matching=len(all_matching),
            total_time_ms=total_time,
            workers_used=self.num_workers,
            chunk_times_ms=chunk_times
        )
        
        logger.info(
            f"🚀 Parallel processing complete: {stats.total_matching} matches "
            f"from {stats.total_features} features in {stats.total_time_ms:.0f}ms "
            f"(speedup: {stats.speedup_vs_sequential:.1f}x)"
        )
        
        return all_matching, stats
    
    def _process_sequential(
        self,
        layer: QgsVectorLayer,
        test_geometry: QgsGeometry,
        predicate: str,
        pre_filter_fids: Optional[Set[int]],
        progress_callback: Optional[Callable[[int, int, str], None]]
    ) -> Tuple[Set[int], ParallelProcessingStats]:
        """Fallback sequential processing for small datasets."""
        start_time = time.time()
        matching = set()
        
        request = QgsFeatureRequest()
        if pre_filter_fids is not None:
            request.setFilterFids(list(pre_filter_fids))
        
        processed = 0
        total = len(pre_filter_fids) if pre_filter_fids else layer.featureCount()
        
        for feat in layer.getFeatures(request):
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            
            try:
                pred_lower = predicate.lower()
                result = False
                
                if pred_lower == 'intersects':
                    result = geom.intersects(test_geometry)
                elif pred_lower == 'within':
                    result = geom.within(test_geometry)
                elif pred_lower == 'contains':
                    result = geom.contains(test_geometry)
                elif pred_lower == 'overlaps':
                    result = geom.overlaps(test_geometry)
                else:
                    result = geom.intersects(test_geometry)
                
                if result:
                    matching.add(feat.id())
                    
            except Exception as e:
                logger.debug(f"Predicate error for FID {feat.id()}: {e}")
            
            processed += 1
            if progress_callback and processed % 1000 == 0:
                progress_callback(processed, total, f"{len(matching)} matches")
        
        total_time = (time.time() - start_time) * 1000
        
        stats = ParallelProcessingStats(
            total_features=processed,
            total_chunks=1,
            total_matching=len(matching),
            total_time_ms=total_time,
            workers_used=1,
            chunk_times_ms=[total_time]
        )
        
        return matching, stats
    
    def cancel(self) -> None:
        """Request cancellation of ongoing processing."""
        self._cancel_requested = True


class ParallelAttributeProcessor:
    """
    Parallel processor for attribute expression evaluation.
    
    Note: Expression evaluation uses QGIS context which is NOT thread-safe.
    This processor uses a different approach:
    1. Fetch all needed attribute values in main thread
    2. Evaluate simple expressions in parallel using pure Python
    3. Return matching FIDs
    
    Only works for simple expressions (field = value, field IN (...), etc.)
    Complex expressions fall back to sequential processing.
    """
    
    def __init__(self, num_workers: int = None, chunk_size: int = 10000):
        self.num_workers = num_workers or DEFAULT_WORKERS
        self.chunk_size = chunk_size
    
    def can_parallelize_expression(self, expression: str) -> bool:
        """
        Check if expression can be parallelized.
        
        Only simple field comparisons are supported:
        - field = value
        - field IN (...)
        - field > / < / >= / <= value
        - field IS NULL / IS NOT NULL
        """
        import re
        
        # Check for complex constructs that require QGIS context
        complex_patterns = [
            r'\$\w+',           # $ variables ($id, $geometry, etc.)
            r'\bgeometry\b',    # geometry functions
            r'\baggregate\b',   # aggregate functions
            r'\beval\b',        # eval function
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, expression, re.IGNORECASE):
                return False
        
        return True
    
    def process_attribute_filter_parallel(
        self,
        layer: QgsVectorLayer,
        field_name: str,
        operator: str,
        value: Any,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Set[int]:
        """
        Process simple attribute filter in parallel.
        
        Args:
            layer: Target layer
            field_name: Field to filter on
            operator: Comparison operator
            value: Comparison value
            progress_callback: (current, total) callback
            
        Returns:
            Set of matching feature IDs
        """
        matching = set()
        
        # Verify field exists
        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            logger.warning(f"Field '{field_name}' not found")
            return matching
        
        # Build request for attributes only
        request = QgsFeatureRequest()
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([field_idx])
        
        # Collect data in main thread
        data_chunks = []
        current_chunk = []
        
        for feat in layer.getFeatures(request):
            attr_value = feat.attribute(field_idx)
            current_chunk.append((feat.id(), attr_value))
            
            if len(current_chunk) >= self.chunk_size:
                data_chunks.append(current_chunk)
                current_chunk = []
        
        if current_chunk:
            data_chunks.append(current_chunk)
        
        if not data_chunks:
            return matching
        
        # Process in parallel
        op_lower = operator.lower()
        
        def process_chunk(chunk: List[Tuple[int, Any]]) -> Set[int]:
            result = set()
            for fid, attr_val in chunk:
                try:
                    if self._compare_value(attr_val, op_lower, value):
                        result.add(fid)
                except Exception:
                    pass
            return result
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = [executor.submit(process_chunk, chunk) for chunk in data_chunks]
            
            for future in as_completed(futures):
                try:
                    chunk_result = future.result(timeout=30.0)
                    matching.update(chunk_result)
                except Exception as e:
                    logger.debug(f"Chunk processing error: {e}")
        
        return matching
    
    def _compare_value(self, attr_val: Any, operator: str, test_value: Any) -> bool:
        """Compare attribute value with test value."""
        # Handle NULL
        if attr_val is None:
            if operator == 'is null':
                return True
            elif operator == 'is not null':
                return False
            return False
        
        if operator in ('=', '=='):
            return attr_val == test_value
        elif operator in ('!=', '<>'):
            return attr_val != test_value
        elif operator == '<':
            return attr_val < test_value
        elif operator == '>':
            return attr_val > test_value
        elif operator == '<=':
            return attr_val <= test_value
        elif operator == '>=':
            return attr_val >= test_value
        elif operator == 'in':
            return attr_val in test_value
        elif operator == 'not in':
            return attr_val not in test_value
        elif operator == 'like':
            import re
            pattern = test_value.replace('%', '.*').replace('_', '.')
            return bool(re.match(pattern, str(attr_val), re.IGNORECASE))
        elif operator == 'is null':
            return attr_val is None
        elif operator == 'is not null':
            return attr_val is not None
        
        return False


def get_parallel_processor(
    num_workers: int = None,
    chunk_size: int = 5000
) -> ParallelChunkProcessor:
    """
    Factory function for parallel chunk processor.
    
    Args:
        num_workers: Number of worker threads
        chunk_size: Features per chunk
        
    Returns:
        Configured ParallelChunkProcessor
    """
    return ParallelChunkProcessor(num_workers, chunk_size)


def should_use_parallel_processing(
    feature_count: int,
    has_spatial_filter: bool = True,
    geometry_complexity: float = 1.0
) -> bool:
    """
    Determine if parallel processing is beneficial.
    
    Args:
        feature_count: Number of features to process
        has_spatial_filter: Whether spatial filtering is needed
        geometry_complexity: Estimated complexity factor
        
    Returns:
        True if parallel processing is recommended
    """
    if not PARALLEL_AVAILABLE:
        return False
    
    # Minimum threshold for parallel overhead to be worthwhile
    min_features = 10000
    
    # Lower threshold for complex geometries or spatial operations
    if has_spatial_filter and geometry_complexity > 2.0:
        min_features = 5000
    
    return feature_count >= min_features
