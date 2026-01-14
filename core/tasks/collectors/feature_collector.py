"""
Feature Collector

Centralized class for collecting and managing features and their IDs.
Consolidates feature extraction logic as part of Phase E13 Step 5 (January 2026).

Responsibilities:
- Extract feature IDs from various sources (selection, expression, list)
- Cache extracted IDs for repeated access
- Batch processing for large feature sets
- Support for different primary key types (numeric, UUID, text)

Location: core/tasks/collectors/feature_collector.py
"""

import logging
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field

from qgis.core import QgsVectorLayer, QgsFeature, QgsFeatureRequest

logger = logging.getLogger('FilterMate.Tasks.FeatureCollector')


@dataclass
class CollectionResult:
    """Result of feature collection."""
    feature_ids: List[Any]
    count: int
    source: str  # 'selection', 'expression', 'all', 'list'
    primary_key_field: Optional[str] = None
    is_numeric: bool = True
    cached: bool = False
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None and self.count >= 0


class FeatureCollector:
    """
    Collects and manages features from various sources.
    
    Responsibilities:
    - Extract feature IDs from layer selection
    - Extract IDs from QgsFeature list
    - Extract IDs from expression filter
    - Cache results for performance
    - Support batch processing for large datasets
    
    Consolidated from:
    - core/filter/source_filter_builder.py::extract_feature_ids()
    - FilterEngineTask feature extraction logic
    
    Example:
        collector = FeatureCollector(
            layer=source_layer,
            primary_key_field="id"
        )
        
        # From selection
        result = collector.collect_from_selection()
        
        # From feature list
        result = collector.collect_from_features(features)
        
        # From expression
        result = collector.collect_from_expression("field > 10")
        
        # Get cached IDs
        ids = collector.get_cached_ids()
    """
    
    def __init__(
        self,
        layer: Optional[QgsVectorLayer] = None,
        primary_key_field: Optional[str] = None,
        is_pk_numeric: bool = True,
        cache_enabled: bool = True
    ):
        """
        Initialize FeatureCollector.
        
        Args:
            layer: Source QGIS vector layer
            primary_key_field: Name of the primary key field
            is_pk_numeric: Whether the primary key is numeric
            cache_enabled: Whether to cache collection results
        """
        self.layer = layer
        self.primary_key_field = primary_key_field
        self.is_pk_numeric = is_pk_numeric
        self.cache_enabled = cache_enabled
        
        # Cache for collected IDs
        self._cached_ids: Optional[List[Any]] = None
        self._cache_source: Optional[str] = None
        
        logger.debug(
            f"FeatureCollector initialized: pk={primary_key_field}, "
            f"numeric={is_pk_numeric}, cache={cache_enabled}"
        )
    
    def collect_from_selection(self) -> CollectionResult:
        """
        Collect feature IDs from layer selection.
        
        Returns:
            CollectionResult with extracted IDs
        """
        if not self.layer:
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='selection',
                error="No layer provided"
            )
        
        try:
            selected_features = list(self.layer.selectedFeatures())
            
            if not selected_features:
                return CollectionResult(
                    feature_ids=[],
                    count=0,
                    source='selection',
                    primary_key_field=self.primary_key_field
                )
            
            # Extract IDs
            ids = self._extract_ids_from_features(selected_features)
            
            # Cache if enabled
            if self.cache_enabled:
                self._cached_ids = ids
                self._cache_source = 'selection'
            
            return CollectionResult(
                feature_ids=ids,
                count=len(ids),
                source='selection',
                primary_key_field=self.primary_key_field,
                is_numeric=self.is_pk_numeric
            )
            
        except Exception as e:
            logger.error(f"Error collecting from selection: {e}")
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='selection',
                error=str(e)
            )
    
    def collect_from_features(
        self,
        features: List[Union[QgsFeature, Dict]]
    ) -> CollectionResult:
        """
        Collect IDs from a list of features.
        
        Args:
            features: List of QgsFeature objects or dicts
            
        Returns:
            CollectionResult with extracted IDs
        """
        if not features:
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='list',
                primary_key_field=self.primary_key_field
            )
        
        try:
            ids = self._extract_ids_from_features(features)
            
            # Cache if enabled
            if self.cache_enabled:
                self._cached_ids = ids
                self._cache_source = 'list'
            
            return CollectionResult(
                feature_ids=ids,
                count=len(ids),
                source='list',
                primary_key_field=self.primary_key_field,
                is_numeric=self.is_pk_numeric
            )
            
        except Exception as e:
            logger.error(f"Error collecting from features: {e}")
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='list',
                error=str(e)
            )
    
    def collect_from_expression(
        self,
        expression: str,
        limit: Optional[int] = None
    ) -> CollectionResult:
        """
        Collect feature IDs matching an expression.
        
        Args:
            expression: QGIS filter expression
            limit: Optional maximum number of features
            
        Returns:
            CollectionResult with extracted IDs
        """
        if not self.layer:
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='expression',
                error="No layer provided"
            )
        
        if not expression:
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='expression',
                error="No expression provided"
            )
        
        try:
            # Build feature request
            request = QgsFeatureRequest()
            request.setFilterExpression(expression)
            
            if self.primary_key_field:
                request.setSubsetOfAttributes([self.primary_key_field], self.layer.fields())
            
            if limit:
                request.setLimit(limit)
            
            # Collect features
            features = list(self.layer.getFeatures(request))
            ids = self._extract_ids_from_features(features)
            
            # Cache if enabled
            if self.cache_enabled:
                self._cached_ids = ids
                self._cache_source = 'expression'
            
            return CollectionResult(
                feature_ids=ids,
                count=len(ids),
                source='expression',
                primary_key_field=self.primary_key_field,
                is_numeric=self.is_pk_numeric
            )
            
        except Exception as e:
            logger.error(f"Error collecting from expression: {e}")
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='expression',
                error=str(e)
            )
    
    def collect_all(
        self,
        limit: Optional[int] = None
    ) -> CollectionResult:
        """
        Collect all feature IDs from layer.
        
        Args:
            limit: Optional maximum number of features
            
        Returns:
            CollectionResult with all IDs
        """
        if not self.layer:
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='all',
                error="No layer provided"
            )
        
        try:
            request = QgsFeatureRequest()
            
            if self.primary_key_field:
                request.setSubsetOfAttributes([self.primary_key_field], self.layer.fields())
            
            if limit:
                request.setLimit(limit)
            
            features = list(self.layer.getFeatures(request))
            ids = self._extract_ids_from_features(features)
            
            # Cache if enabled
            if self.cache_enabled:
                self._cached_ids = ids
                self._cache_source = 'all'
            
            return CollectionResult(
                feature_ids=ids,
                count=len(ids),
                source='all',
                primary_key_field=self.primary_key_field,
                is_numeric=self.is_pk_numeric
            )
            
        except Exception as e:
            logger.error(f"Error collecting all features: {e}")
            return CollectionResult(
                feature_ids=[],
                count=0,
                source='all',
                error=str(e)
            )
    
    def _extract_ids_from_features(
        self,
        features: List[Union[QgsFeature, Dict]]
    ) -> List[Any]:
        """
        Extract IDs from feature list.
        
        Uses attribute(pk_field) for proper DB primary key extraction,
        NOT f.id() which returns QGIS internal FID.
        
        Args:
            features: List of features
            
        Returns:
            List of primary key values
        """
        ids = []
        pk_field = self.primary_key_field
        
        for f in features:
            try:
                if hasattr(f, 'attribute') and pk_field:
                    # Use attribute() for DB primary key
                    fid_val = f.attribute(pk_field)
                    if fid_val is not None:
                        ids.append(fid_val)
                    elif hasattr(f, 'id'):
                        # Fallback to QGIS FID if attribute is null
                        ids.append(f.id())
                elif hasattr(f, 'id'):
                    # Legacy fallback
                    ids.append(f.id())
                elif isinstance(f, dict) and pk_field and pk_field in f:
                    ids.append(f[pk_field])
            except Exception as e:
                logger.debug(f"Could not extract ID from feature: {e}")
        
        return ids
    
    def get_cached_ids(self) -> Optional[List[Any]]:
        """Get cached feature IDs if available."""
        return self._cached_ids
    
    def get_cache_source(self) -> Optional[str]:
        """Get source of cached IDs ('selection', 'list', 'expression', 'all')."""
        return self._cache_source
    
    def clear_cache(self):
        """Clear cached IDs."""
        self._cached_ids = None
        self._cache_source = None
        logger.debug("Feature ID cache cleared")
    
    def has_cache(self) -> bool:
        """Check if cache has IDs."""
        return self._cached_ids is not None and len(self._cached_ids) > 0
    
    def get_cached_count(self) -> int:
        """Get count of cached IDs."""
        return len(self._cached_ids) if self._cached_ids else 0
    
    def collect_in_batches(
        self,
        batch_size: int = 1000,
        source: str = 'all',
        expression: Optional[str] = None
    ) -> Tuple[List[List[Any]], int]:
        """
        Collect feature IDs in batches for large datasets.
        
        Args:
            batch_size: Number of IDs per batch
            source: Collection source ('all', 'selection', 'expression')
            expression: Optional filter expression
            
        Returns:
            Tuple of (list of ID batches, total count)
        """
        # Collect all IDs first
        if source == 'selection':
            result = self.collect_from_selection()
        elif source == 'expression' and expression:
            result = self.collect_from_expression(expression)
        else:
            result = self.collect_all()
        
        if not result.success or not result.feature_ids:
            return [], 0
        
        # Split into batches
        ids = result.feature_ids
        batches = [
            ids[i:i + batch_size]
            for i in range(0, len(ids), batch_size)
        ]
        
        return batches, result.count
    
    @staticmethod
    def format_ids_for_sql(
        ids: List[Any],
        is_numeric: bool = True
    ) -> str:
        """
        Format IDs for SQL IN clause.
        
        Args:
            ids: List of IDs
            is_numeric: Whether IDs are numeric
            
        Returns:
            Formatted string for SQL
        """
        if not ids:
            return ""
        
        if is_numeric:
            return ", ".join(str(id_val) for id_val in ids)
        else:
            # Quote non-numeric values
            return ", ".join(f"'{id_val}'" for id_val in ids)
    
    @staticmethod
    def restore_layer_selection(
        layer: QgsVectorLayer,
        feature_ids: List[int]
    ) -> bool:
        """
        Restore selection on layer from feature FIDs.
        
        Note: This uses QGIS internal FIDs, not DB primary keys.
        
        Args:
            layer: Target layer
            feature_ids: List of QGIS feature FIDs
            
        Returns:
            True if selection restored successfully
        """
        if not layer or not feature_ids:
            return False
        
        try:
            layer.selectByIds(feature_ids)
            logger.info(f"Restored selection: {len(feature_ids)} features")
            return True
        except Exception as e:
            logger.warning(f"Failed to restore selection: {e}")
            return False
