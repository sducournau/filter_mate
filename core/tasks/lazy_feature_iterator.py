# -*- coding: utf-8 -*-
"""
LazyFeatureIterator - Memory-efficient feature iteration with pagination.

v4.1.1 - January 2026

PURPOSE:
Provides lazy loading of features with:
1. Configurable page size for memory efficiency
2. On-demand loading (only loads when iterated)
3. Progress callbacks for UI updates
4. Cancellation support

PERFORMANCE IMPACT:
- For UI widgets: Load first page (e.g., 500 items) immediately
- Load more only when user scrolls or requests
- Reduces initial load time from seconds to milliseconds
- Memory usage stays constant regardless of dataset size
"""

import logging
from typing import List, Iterator, Optional, Callable, Any, TYPE_CHECKING

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsFeatureRequest,
        QgsFeature,
        QgsExpression,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer, QgsFeatureRequest, QgsFeature

logger = logging.getLogger('FilterMate.LazyFeatureIterator')


class LazyFeatureIterator:
    """
    Memory-efficient iterator that loads features in pages.
    
    Instead of loading all features at once (which can freeze the UI for large layers),
    this iterator loads features in configurable batches (pages).
    
    USE CASES:
    - Populating feature list widgets with virtual scrolling
    - Processing large result sets without memory explosion
    - Providing responsive UI while data loads in background
    
    Example:
        # Load features in pages of 500
        iterator = LazyFeatureIterator(
            layer=my_layer,
            page_size=500,
            expression='"status" = 1'
        )
        
        # Get first page for immediate UI display
        first_page = iterator.get_page(0)
        update_ui(first_page)
        
        # Load more as needed
        if iterator.has_more_pages():
            next_page = iterator.get_next_page()
            append_to_ui(next_page)
    """
    
    # Default page size optimized for UI responsiveness
    DEFAULT_PAGE_SIZE = 500
    
    def __init__(
        self,
        layer: 'QgsVectorLayer',
        page_size: int = DEFAULT_PAGE_SIZE,
        expression: str = None,
        fields: List[str] = None,
        include_geometry: bool = True,
        on_progress: Callable[[int, int], None] = None,
    ):
        """
        Initialize the lazy feature iterator.
        
        Args:
            layer: Source vector layer
            page_size: Number of features per page (default: 500)
            expression: Optional filter expression
            fields: Optional list of field names to load (None = all)
            include_geometry: Whether to load geometry
            on_progress: Optional callback(loaded_count, total_estimate)
        """
        self._layer = layer
        self._page_size = page_size
        self._expression = expression
        self._fields = fields
        self._include_geometry = include_geometry
        self._on_progress = on_progress
        
        # State
        self._current_page = 0
        self._total_loaded = 0
        self._is_exhausted = False
        self._cancelled = False
        
        # Cache for loaded pages
        self._cached_pages: dict = {}  # page_index -> List[QgsFeature]
        
        # Total count (lazy-evaluated)
        self._total_count: Optional[int] = None
    
    @property
    def total_count(self) -> int:
        """
        Get total feature count (lazy-evaluated).
        
        For filtered queries, this requires counting features.
        """
        if self._total_count is None:
            if self._expression:
                # Count with expression - this can be slow
                request = QgsFeatureRequest()
                request.setFilterExpression(self._expression)
                request.setFlags(QgsFeatureRequest.NoGeometry)
                request.setSubsetOfAttributes([])
                self._total_count = sum(1 for _ in self._layer.getFeatures(request))
            else:
                self._total_count = self._layer.featureCount()
        return self._total_count
    
    @property
    def page_count(self) -> int:
        """Get estimated number of pages."""
        if self._total_count is None:
            # Avoid expensive count by estimating from layer
            estimated = self._layer.featureCount()
            return max(1, (estimated + self._page_size - 1) // self._page_size)
        return max(1, (self._total_count + self._page_size - 1) // self._page_size)
    
    @property
    def loaded_count(self) -> int:
        """Get number of features already loaded."""
        return self._total_loaded
    
    def has_more_pages(self) -> bool:
        """Check if there are more pages to load."""
        return not self._is_exhausted
    
    def cancel(self) -> None:
        """Cancel any ongoing iteration."""
        self._cancelled = True
    
    def reset(self) -> None:
        """Reset iterator to beginning."""
        self._current_page = 0
        self._total_loaded = 0
        self._is_exhausted = False
        self._cancelled = False
        self._cached_pages.clear()
    
    def get_page(self, page_index: int) -> List['QgsFeature']:
        """
        Get a specific page of features.
        
        Args:
            page_index: Zero-based page index
            
        Returns:
            List of features for that page
        """
        # Check cache
        if page_index in self._cached_pages:
            return self._cached_pages[page_index]
        
        # Load page
        offset = page_index * self._page_size
        features = self._load_features(offset, self._page_size)
        
        # Cache
        self._cached_pages[page_index] = features
        
        # Update state
        self._current_page = page_index
        if len(features) < self._page_size:
            self._is_exhausted = True
        
        return features
    
    def get_next_page(self) -> List['QgsFeature']:
        """
        Get the next page of features.
        
        Returns:
            List of features for the next page
        """
        if self._is_exhausted:
            return []
        
        next_page = self._current_page + 1 if self._total_loaded > 0 else 0
        return self.get_page(next_page)
    
    def get_first_n(self, n: int) -> List['QgsFeature']:
        """
        Get the first N features efficiently.
        
        Useful for quick initial UI population.
        
        Args:
            n: Number of features to get
            
        Returns:
            List of up to N features
        """
        return self._load_features(0, n)
    
    def iter_all(self) -> Iterator['QgsFeature']:
        """
        Iterate through all features (generator).
        
        Yields features one at a time, loading pages as needed.
        Useful for processing all features without loading all in memory.
        """
        page_index = 0
        
        while not self._cancelled:
            page = self.get_page(page_index)
            
            if not page:
                break
            
            for feature in page:
                if self._cancelled:
                    return
                yield feature
            
            page_index += 1
            
            if len(page) < self._page_size:
                break
    
    def _load_features(self, offset: int, limit: int) -> List['QgsFeature']:
        """
        Load features from layer with offset and limit.
        
        Args:
            offset: Number of features to skip
            limit: Maximum features to load
            
        Returns:
            List of loaded features
        """
        if not self._layer or not self._layer.isValid():
            logger.warning("Layer is not valid")
            return []
        
        try:
            # Build request
            request = QgsFeatureRequest()
            
            # Add expression filter
            if self._expression:
                qgs_expr = QgsExpression(self._expression)
                if qgs_expr.hasParserError():
                    logger.error(f"Invalid expression: {qgs_expr.parserErrorString()}")
                    return []
                request.setFilterExpression(self._expression)
            
            # Set limit
            request.setLimit(limit)
            
            # Set field subset
            if self._fields:
                request.setSubsetOfAttributes(self._fields, self._layer.fields())
            
            # Set geometry flag
            if not self._include_geometry:
                request.setFlags(QgsFeatureRequest.NoGeometry)
            
            # Load features
            features = []
            skip_count = offset
            load_count = 0
            
            for feature in self._layer.getFeatures(request):
                if self._cancelled:
                    break
                
                # Skip offset
                if skip_count > 0:
                    skip_count -= 1
                    continue
                
                features.append(feature)
                load_count += 1
                
                # Check limit
                if load_count >= limit:
                    break
                
                # Progress callback
                if self._on_progress and load_count % 100 == 0:
                    self._on_progress(self._total_loaded + load_count, self.total_count)
            
            self._total_loaded += len(features)
            
            # Final progress
            if self._on_progress:
                self._on_progress(self._total_loaded, self.total_count)
            
            return features
            
        except Exception as e:
            logger.error(f"Error loading features: {e}")
            return []


class LazyUniqueValuesIterator:
    """
    Memory-efficient iterator for unique field values with pagination.
    
    Similar to LazyFeatureIterator but optimized for unique values:
    - Uses uniqueValues() for small layers (fast, but loads all)
    - Uses feature iteration for large layers (slower, but memory-efficient)
    
    Example:
        iterator = LazyUniqueValuesIterator(
            layer=my_layer,
            field_name="category",
            page_size=100
        )
        
        # Get first 100 values for autocomplete
        first_values = iterator.get_first_n(100)
    """
    
    # Threshold for using uniqueValues() vs iteration
    FAST_THRESHOLD = 5000
    
    DEFAULT_PAGE_SIZE = 100
    
    def __init__(
        self,
        layer: 'QgsVectorLayer',
        field_name: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_values: bool = True,
    ):
        """
        Initialize the lazy unique values iterator.
        
        Args:
            layer: Source vector layer
            field_name: Name of field to get unique values from
            page_size: Number of values per page
            sort_values: Whether to sort values alphabetically
        """
        self._layer = layer
        self._field_name = field_name
        self._page_size = page_size
        self._sort_values = sort_values
        
        # State
        self._all_values: Optional[List[str]] = None
        self._is_loaded = False
        self._current_page = 0
    
    def _ensure_loaded(self) -> None:
        """Load all unique values if not already loaded."""
        if self._is_loaded:
            return
        
        field_index = self._layer.fields().indexFromName(self._field_name)
        if field_index < 0:
            logger.warning(f"Field '{self._field_name}' not found")
            self._all_values = []
            self._is_loaded = True
            return
        
        try:
            # Use fast method for small layers
            if self._layer.featureCount() < self.FAST_THRESHOLD:
                raw_values = self._layer.uniqueValues(field_index)
                self._all_values = [str(v) for v in raw_values if v is not None]
            else:
                # Use iteration for large layers
                unique_set = set()
                request = QgsFeatureRequest()
                request.setSubsetOfAttributes([field_index])
                request.setFlags(QgsFeatureRequest.NoGeometry)
                
                for feature in self._layer.getFeatures(request):
                    value = feature.attributes()[field_index]
                    if value is not None:
                        unique_set.add(str(value))
                
                self._all_values = list(unique_set)
            
            # Sort if requested
            if self._sort_values:
                self._all_values.sort()
            
            self._is_loaded = True
            
        except Exception as e:
            logger.error(f"Error loading unique values: {e}")
            self._all_values = []
            self._is_loaded = True
    
    @property
    def total_count(self) -> int:
        """Get total number of unique values."""
        self._ensure_loaded()
        return len(self._all_values)
    
    def get_first_n(self, n: int) -> List[str]:
        """Get first N unique values."""
        self._ensure_loaded()
        return self._all_values[:n]
    
    def get_page(self, page_index: int) -> List[str]:
        """Get a page of unique values."""
        self._ensure_loaded()
        start = page_index * self._page_size
        end = start + self._page_size
        return self._all_values[start:end]
    
    def get_all(self) -> List[str]:
        """Get all unique values."""
        self._ensure_loaded()
        return self._all_values.copy()
    
    def search(self, prefix: str, limit: int = 50) -> List[str]:
        """
        Search values by prefix for autocomplete.
        
        Args:
            prefix: Search prefix (case-insensitive)
            limit: Maximum results to return
            
        Returns:
            List of matching values
        """
        self._ensure_loaded()
        prefix_lower = prefix.lower()
        
        matches = [
            v for v in self._all_values 
            if v.lower().startswith(prefix_lower)
        ]
        
        return matches[:limit]
