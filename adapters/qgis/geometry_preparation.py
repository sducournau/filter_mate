# -*- coding: utf-8 -*-
"""
Geometry Preparation Adapter for FilterMate.

Extracted from filter_task.py (MIG-202) as part of god class refactoring.
Provides QGIS-specific geometry preparation for spatial filtering operations.

This adapter handles:
- Copying filtered/selected layers to memory
- Geometry validation and repair
- CRS transformation
- Centroid conversion
- WKT generation with optimization

The pure calculation logic (tolerances, precision) is delegated to
core/services/buffer_service.py to maintain hexagonal separation.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, Tuple, Dict, Any, Union
from dataclasses import dataclass

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
)

logger = logging.getLogger('FilterMate.Adapters.GeometryPreparation')


@dataclass
class GeometryPreparationConfig:
    """
    Configuration for geometry preparation operations.
    
    Attributes:
        use_centroids: Convert geometries to centroids
        validate_geometries: Validate geometries before use
        repair_geometries: Attempt to repair invalid geometries
        max_wkt_length: Maximum WKT string length before simplification
        wkt_precision: Decimal precision for WKT output
    """
    use_centroids: bool = False
    validate_geometries: bool = True
    repair_geometries: bool = True
    max_wkt_length: int = 100000
    wkt_precision: int = 6


@dataclass
class GeometryPreparationResult:
    """
    Result of geometry preparation.
    
    Attributes:
        success: Whether preparation succeeded
        geometry: Prepared geometry (for single geometry results)
        layer: Prepared layer (for layer results)
        wkt: WKT string (for WKT results)
        feature_count: Number of features processed
        valid_count: Number of valid geometries
        repaired_count: Number of geometries that were repaired
        error_message: Error message if failed
    """
    success: bool
    geometry: Optional[QgsGeometry] = None
    layer: Optional[QgsVectorLayer] = None
    wkt: Optional[str] = None
    feature_count: int = 0
    valid_count: int = 0
    repaired_count: int = 0
    error_message: Optional[str] = None


class GeometryPreparationAdapter:
    """
    Adapter for QGIS geometry preparation operations.
    
    This adapter encapsulates the geometry preparation logic that was
    previously scattered across filter_task.py. It provides a clean
    interface for:
    
    - Creating memory layers from filtered/selected features
    - Validating and repairing geometries
    - Converting to centroids
    - Generating optimized WKT
    
    Example:
        adapter = GeometryPreparationAdapter()
        
        # Copy filtered layer to memory
        result = adapter.copy_filtered_to_memory(layer)
        if result.success:
            memory_layer = result.layer
        
        # Get WKT for spatial query
        result = adapter.features_to_wkt(features, crs)
        if result.success:
            wkt = result.wkt
    """
    
    def __init__(
        self,
        project: Optional[QgsProject] = None,
        config: Optional[GeometryPreparationConfig] = None
    ):
        """
        Initialize adapter.
        
        Args:
            project: QGIS project instance (uses current if None)
            config: Preparation configuration
        """
        self._project = project or QgsProject.instance()
        self._config = config or GeometryPreparationConfig()
        self._metrics = {
            'layers_copied': 0,
            'geometries_validated': 0,
            'geometries_repaired': 0,
            'wkt_generated': 0,
        }
    
    @property
    def config(self) -> GeometryPreparationConfig:
        """Get current configuration."""
        return self._config
    
    @config.setter
    def config(self, value: GeometryPreparationConfig) -> None:
        """Set configuration."""
        self._config = value
    
    @property
    def metrics(self) -> Dict[str, int]:
        """Get operation metrics."""
        return self._metrics.copy()
    
    # =========================================================================
    # Memory Layer Creation
    # =========================================================================
    
    def copy_filtered_to_memory(
        self,
        layer: QgsVectorLayer,
        layer_name: str = "filtered_copy"
    ) -> GeometryPreparationResult:
        """
        Copy filtered layer (with subset string) to memory layer.
        
        Creates a memory copy of only the visible features from a layer
        that has an active subset string filter. This is essential for
        algorithms that don't respect subset strings.
        
        STABILITY: Validates and optionally repairs geometries during copy
        to prevent access violations from corrupted geometries.
        
        Args:
            layer: Source layer (may have subset string)
            layer_name: Name for memory layer
            
        Returns:
            GeometryPreparationResult with memory layer
        """
        if not layer or not layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message="Invalid or None layer provided"
            )
        
        subset_string = layer.subsetString()
        feature_count = layer.featureCount()
        is_virtual = layer.providerType() == 'virtual'
        
        logger.debug(
            f"copy_filtered_to_memory: {layer.name()}, "
            f"features={feature_count}, "
            f"subset='{subset_string[:50] if subset_string else 'None'}'"
        )
        
        # If no filter and reasonable count, return original (except virtual layers)
        if not subset_string and feature_count < 10000 and not is_virtual:
            logger.debug("No filter and small layer - returning original")
            return GeometryPreparationResult(
                success=True,
                layer=layer,
                feature_count=feature_count
            )
        
        if is_virtual:
            logger.info(f"Virtual layer detected - copying to memory for stability")
        
        # Create memory layer with same structure
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        memory_layer = QgsVectorLayer(
            f"{geom_type}?crs={crs}",
            layer_name,
            "memory"
        )
        
        if not memory_layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message=f"Failed to create memory layer: {geom_type}?crs={crs}"
            )
        
        # Copy fields
        memory_layer.dataProvider().addAttributes(layer.fields())
        memory_layer.updateFields()
        
        # Copy features with optional validation
        features_to_copy = []
        skipped = 0
        repaired = 0
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            
            if self._config.validate_geometries and geom and not geom.isEmpty():
                if not geom.isGeosValid():
                    if self._config.repair_geometries:
                        repaired_geom = self._repair_geometry(geom)
                        if repaired_geom and repaired_geom.isGeosValid():
                            feature.setGeometry(repaired_geom)
                            repaired += 1
                        else:
                            skipped += 1
                            continue
                    else:
                        skipped += 1
                        continue
            
            features_to_copy.append(feature)
        
        if repaired > 0:
            logger.info(f"Repaired {repaired} invalid geometries during copy")
        if skipped > 0:
            logger.warning(f"Skipped {skipped} invalid geometries")
        
        if not features_to_copy:
            return GeometryPreparationResult(
                success=False,
                error_message="No valid features to copy"
            )
        
        memory_layer.dataProvider().addFeatures(features_to_copy)
        memory_layer.updateExtents()
        
        self._metrics['layers_copied'] += 1
        self._metrics['geometries_validated'] += len(features_to_copy) + skipped
        self._metrics['geometries_repaired'] += repaired
        
        logger.debug(
            f"Copied {len(features_to_copy)} features to memory "
            f"(skipped {skipped}, repaired {repaired})"
        )
        
        return GeometryPreparationResult(
            success=True,
            layer=memory_layer,
            feature_count=len(features_to_copy),
            valid_count=len(features_to_copy),
            repaired_count=repaired
        )
    
    def copy_selected_to_memory(
        self,
        layer: QgsVectorLayer,
        layer_name: str = "selected_copy"
    ) -> GeometryPreparationResult:
        """
        Copy only selected features from layer to memory layer.
        
        Essential for multi-selection mode where only selected features
        should be used for spatial operations.
        
        Args:
            layer: Source layer with selected features
            layer_name: Name for memory layer
            
        Returns:
            GeometryPreparationResult with memory layer
        """
        if not layer or not layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message="Invalid or None layer provided"
            )
        
        selected_count = layer.selectedFeatureCount()
        logger.debug(
            f"copy_selected_to_memory: {layer.name()}, selected={selected_count}"
        )
        
        if selected_count == 0:
            return GeometryPreparationResult(
                success=False,
                error_message="No features selected"
            )
        
        # Create memory layer
        geom_type = QgsWkbTypes.displayString(layer.wkbType())
        crs = layer.crs().authid()
        memory_layer = QgsVectorLayer(
            f"{geom_type}?crs={crs}",
            layer_name,
            "memory"
        )
        
        if not memory_layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message="Failed to create memory layer"
            )
        
        # Copy fields
        memory_layer.dataProvider().addAttributes(layer.fields())
        memory_layer.updateFields()
        
        # Get selected features thread-safely
        selected_fids = list(layer.selectedFeatureIds())
        request = QgsFeatureRequest().setFilterFids(selected_fids)
        
        features_to_copy = []
        skipped = 0
        repaired = 0
        
        for feature in layer.getFeatures(request):
            geom = feature.geometry()
            
            if self._config.validate_geometries and geom and not geom.isEmpty():
                if not geom.isGeosValid():
                    if self._config.repair_geometries:
                        repaired_geom = self._repair_geometry(geom)
                        if repaired_geom and repaired_geom.isGeosValid():
                            feature.setGeometry(repaired_geom)
                            repaired += 1
                        else:
                            skipped += 1
                            continue
                    else:
                        skipped += 1
                        continue
            
            features_to_copy.append(feature)
        
        if not features_to_copy:
            return GeometryPreparationResult(
                success=False,
                error_message="No valid selected features"
            )
        
        memory_layer.dataProvider().addFeatures(features_to_copy)
        memory_layer.updateExtents()
        
        self._metrics['layers_copied'] += 1
        
        return GeometryPreparationResult(
            success=True,
            layer=memory_layer,
            feature_count=len(features_to_copy),
            valid_count=len(features_to_copy),
            repaired_count=repaired
        )
    
    def create_memory_from_features(
        self,
        features: List[QgsFeature],
        crs: Union[QgsCoordinateReferenceSystem, str],
        layer_name: str = "from_features"
    ) -> GeometryPreparationResult:
        """
        Create memory layer from a list of QgsFeature objects.
        
        Used when task_parameters contains features but source layer
        has no visible features.
        
        Args:
            features: List of QgsFeature objects
            crs: CRS for memory layer
            layer_name: Name for memory layer
            
        Returns:
            GeometryPreparationResult with memory layer
        """
        if not features:
            return GeometryPreparationResult(
                success=False,
                error_message="No features provided"
            )
        
        # Find geometry type from first valid geometry
        geom_type = None
        for feat in features:
            if feat.hasGeometry() and not feat.geometry().isEmpty():
                geom_type = QgsWkbTypes.displayString(feat.geometry().wkbType())
                break
        
        if not geom_type:
            return GeometryPreparationResult(
                success=False,
                error_message="No valid geometries in features"
            )
        
        # Get CRS auth ID
        if isinstance(crs, QgsCoordinateReferenceSystem):
            crs_authid = crs.authid()
        else:
            crs_authid = str(crs)
        
        logger.info(
            f"create_memory_from_features: Creating {geom_type} layer "
            f"with {len(features)} features"
        )
        
        # Create memory layer
        memory_layer = QgsVectorLayer(
            f"{geom_type}?crs={crs_authid}",
            layer_name,
            "memory"
        )
        
        if not memory_layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message="Failed to create memory layer"
            )
        
        # Copy fields from first feature
        first_feat = features[0]
        if first_feat.fields().count() > 0:
            memory_layer.dataProvider().addAttributes(first_feat.fields())
            memory_layer.updateFields()
        
        # Add features with validation
        features_to_add = []
        skipped = 0
        
        for feat in features:
            if not feat.hasGeometry():
                skipped += 1
                continue
            
            geom = feat.geometry()
            if geom.isEmpty():
                skipped += 1
                continue
            
            if self._config.validate_geometries and not geom.isGeosValid():
                if self._config.repair_geometries:
                    repaired = self._repair_geometry(geom)
                    if repaired and repaired.isGeosValid():
                        feat.setGeometry(repaired)
                    else:
                        skipped += 1
                        continue
                else:
                    skipped += 1
                    continue
            
            features_to_add.append(feat)
        
        if not features_to_add:
            return GeometryPreparationResult(
                success=False,
                error_message="No valid features to add"
            )
        
        memory_layer.dataProvider().addFeatures(features_to_add)
        memory_layer.updateExtents()
        
        self._metrics['layers_copied'] += 1
        
        if skipped > 0:
            logger.warning(f"Skipped {skipped} features without valid geometry")
        
        return GeometryPreparationResult(
            success=True,
            layer=memory_layer,
            feature_count=len(features_to_add),
            valid_count=len(features_to_add)
        )
    
    # =========================================================================
    # Geometry Transformation
    # =========================================================================
    
    def convert_to_centroids(
        self,
        layer: QgsVectorLayer
    ) -> GeometryPreparationResult:
        """
        Convert layer geometries to their centroids.
        
        Optimization for complex polygons - uses simple point geometries
        instead of full polygons for spatial queries.
        
        Args:
            layer: Layer with polygon/line geometries
            
        Returns:
            GeometryPreparationResult with point layer
        """
        if not layer or not layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message="Invalid layer"
            )
        
        crs_authid = layer.crs().authid()
        centroid_layer = QgsVectorLayer(
            f"Point?crs={crs_authid}",
            "centroids",
            "memory"
        )
        
        if not centroid_layer.isValid():
            return GeometryPreparationResult(
                success=False,
                error_message="Failed to create centroid layer"
            )
        
        # Copy fields
        if layer.fields().count() > 0:
            centroid_layer.dataProvider().addAttributes(layer.fields())
            centroid_layer.updateFields()
        
        features_to_add = []
        skipped = 0
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if not geom or geom.isEmpty():
                skipped += 1
                continue
            
            centroid = geom.centroid()
            if not centroid or centroid.isEmpty():
                skipped += 1
                continue
            
            new_feature = QgsFeature(feature)
            new_feature.setGeometry(centroid)
            features_to_add.append(new_feature)
        
        if not features_to_add:
            return GeometryPreparationResult(
                success=False,
                error_message="Could not convert any features to centroids"
            )
        
        centroid_layer.dataProvider().addFeatures(features_to_add)
        centroid_layer.updateExtents()
        
        logger.debug(
            f"convert_to_centroids: Created {len(features_to_add)} "
            f"centroid features (skipped {skipped})"
        )
        
        return GeometryPreparationResult(
            success=True,
            layer=centroid_layer,
            feature_count=len(features_to_add)
        )
    
    # =========================================================================
    # WKT Generation
    # =========================================================================
    
    def features_to_wkt(
        self,
        features: List[QgsFeature],
        target_crs: Optional[QgsCoordinateReferenceSystem] = None,
        source_crs: Optional[QgsCoordinateReferenceSystem] = None,
        dissolve: bool = True,
        use_centroids: bool = False,
        wkt_precision: Optional[int] = None
    ) -> GeometryPreparationResult:
        """
        Convert features to WKT string for spatial queries.
        
        Collects geometries from features, optionally transforms CRS,
        dissolves into single geometry, and outputs as WKT.
        
        Args:
            features: List of features with geometries
            target_crs: Target CRS (if reprojection needed)
            source_crs: Source CRS (required if reprojecting)
            dissolve: Whether to dissolve geometries
            use_centroids: Convert to centroids before processing
            wkt_precision: Decimal precision (None = auto-detect from CRS)
            
        Returns:
            GeometryPreparationResult with WKT string
        """
        if not features:
            return GeometryPreparationResult(
                success=False,
                error_message="No features provided"
            )
        
        # Setup transform if needed
        transform = None
        if target_crs and source_crs:
            transform = QgsCoordinateTransform(
                source_crs, target_crs, self._project
            )
        
        # Collect geometries
        geometries = []
        for feature in features:
            if not feature.hasGeometry():
                continue
            
            geom = QgsGeometry(feature.geometry())  # Copy
            if geom.isEmpty():
                continue
            
            # Apply centroid if requested
            if use_centroids:
                centroid = geom.centroid()
                if centroid and not centroid.isEmpty():
                    geom = centroid
            
            # Transform if needed
            if transform:
                geom.transform(transform)
            
            # Validate
            if self._config.validate_geometries and not geom.isGeosValid():
                if self._config.repair_geometries:
                    geom = self._repair_geometry(geom)
                    if not geom or not geom.isGeosValid():
                        continue
                else:
                    continue
            
            geometries.append(geom)
        
        if not geometries:
            return GeometryPreparationResult(
                success=False,
                error_message="No valid geometries found"
            )
        
        # Dissolve geometries
        if dissolve and len(geometries) > 1:
            try:
                collected = QgsGeometry.collectGeometry(geometries)
                if collected and not collected.isEmpty():
                    dissolved = collected.unaryUnion()
                    if dissolved and not dissolved.isEmpty():
                        final_geom = dissolved
                    else:
                        final_geom = collected
                else:
                    final_geom = geometries[0]
            except Exception as e:
                logger.warning(f"Dissolve failed: {e}, using first geometry")
                final_geom = geometries[0]
        else:
            final_geom = geometries[0] if len(geometries) == 1 else QgsGeometry.collectGeometry(geometries)
        
        # Determine WKT precision
        if wkt_precision is None:
            wkt_precision = self._get_wkt_precision(target_crs or source_crs)
        
        # Generate WKT
        wkt = final_geom.asWkt(wkt_precision)
        
        # Escape for SQL
        wkt_escaped = wkt.replace("'", "''")
        
        self._metrics['wkt_generated'] += 1
        
        logger.debug(
            f"features_to_wkt: {len(features)} features → "
            f"{len(geometries)} geometries → {len(wkt)} chars WKT"
        )
        
        return GeometryPreparationResult(
            success=True,
            wkt=wkt_escaped,
            feature_count=len(features),
            valid_count=len(geometries)
        )
    
    def features_to_wkt_with_simplification(
        self,
        features: List[QgsFeature],
        target_crs: Optional[QgsCoordinateReferenceSystem] = None,
        source_crs: Optional[QgsCoordinateReferenceSystem] = None,
        dissolve: bool = True,
        use_centroids: bool = False,
        max_wkt_length: Optional[int] = None,
        buffer_value: Optional[float] = None,
        buffer_segments: int = 5,
        buffer_type: int = 0
    ) -> GeometryPreparationResult:
        """
        Convert features to WKT with automatic simplification for large geometries.
        
        Combines features_to_wkt and simplify_geometry_adaptive for optimal
        WKT generation. Automatically applies simplification if result exceeds
        max_wkt_length.
        
        Args:
            features: List of features with geometries
            target_crs: Target CRS (if reprojection needed)
            source_crs: Source CRS (required if reprojecting)
            dissolve: Whether to dissolve geometries
            use_centroids: Convert to centroids before processing
            max_wkt_length: Maximum WKT length before simplification
            buffer_value: Buffer value for tolerance calculation
            buffer_segments: Buffer segments
            buffer_type: Buffer end cap type
            
        Returns:
            GeometryPreparationResult with WKT string (possibly simplified)
        """
        if not features:
            return GeometryPreparationResult(
                success=False,
                error_message="No features provided"
            )
        
        # First, collect and dissolve geometries
        transform = None
        if target_crs and source_crs:
            transform = QgsCoordinateTransform(
                source_crs, target_crs, self._project
            )
        
        geometries = []
        for feature in features:
            if not feature.hasGeometry():
                continue
            
            geom = QgsGeometry(feature.geometry())
            if geom.isEmpty():
                continue
            
            if use_centroids:
                centroid = geom.centroid()
                if centroid and not centroid.isEmpty():
                    geom = centroid
            
            if transform:
                geom.transform(transform)
            
            if self._config.validate_geometries and not geom.isGeosValid():
                if self._config.repair_geometries:
                    geom = self._repair_geometry(geom)
                    if not geom or not geom.isGeosValid():
                        continue
                else:
                    continue
            
            geometries.append(geom)
        
        if not geometries:
            return GeometryPreparationResult(
                success=False,
                error_message="No valid geometries found"
            )
        
        # Dissolve geometries
        if dissolve and len(geometries) > 1:
            try:
                collected = QgsGeometry.collectGeometry(geometries)
                if collected and not collected.isEmpty():
                    dissolved = collected.unaryUnion()
                    final_geom = dissolved if dissolved and not dissolved.isEmpty() else collected
                else:
                    final_geom = geometries[0]
            except Exception as e:
                logger.warning(f"Dissolve failed: {e}")
                final_geom = geometries[0]
        else:
            final_geom = geometries[0] if len(geometries) == 1 else QgsGeometry.collectGeometry(geometries)
        
        # Determine CRS for precision
        crs = target_crs or source_crs
        crs_authid = crs.authid() if crs else None
        wkt_precision = self._get_wkt_precision(crs)
        
        # Generate initial WKT
        wkt = final_geom.asWkt(wkt_precision)
        
        # Check if simplification needed
        if max_wkt_length is None:
            max_wkt_length = self._config.max_wkt_length
        
        if len(wkt) > max_wkt_length:
            logger.info(
                f"WKT too large ({len(wkt)} chars), applying adaptive simplification"
            )
            
            simplify_result = self.simplify_geometry_adaptive(
                geometry=final_geom,
                max_wkt_length=max_wkt_length,
                crs_authid=crs_authid,
                buffer_value=buffer_value,
                buffer_segments=buffer_segments,
                buffer_type=buffer_type
            )
            
            if simplify_result.success and simplify_result.wkt:
                return GeometryPreparationResult(
                    success=True,
                    geometry=simplify_result.geometry,
                    wkt=simplify_result.wkt,
                    feature_count=len(features),
                    valid_count=len(geometries)
                )
        
        # Return original WKT (escaped)
        wkt_escaped = wkt.replace("'", "''")
        self._metrics['wkt_generated'] += 1
        
        return GeometryPreparationResult(
            success=True,
            geometry=final_geom,
            wkt=wkt_escaped,
            feature_count=len(features),
            valid_count=len(geometries)
        )
    
    # =========================================================================
    # Geometry Simplification
    # =========================================================================
    
    def simplify_geometry_adaptive(
        self,
        geometry: QgsGeometry,
        max_wkt_length: Optional[int] = None,
        crs_authid: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_segments: int = 5,
        buffer_type: int = 0
    ) -> GeometryPreparationResult:
        """
        Simplify geometry adaptively to fit within WKT size limit.
        
        Progressive simplification algorithm that:
        1. Estimates optimal tolerance based on geometry extent and target size
        2. Uses topology-preserving simplification
        3. Progressively increases tolerance until target size is reached
        4. Falls back to convexHull/boundingBox for extreme cases
        
        Args:
            geometry: QgsGeometry to simplify
            max_wkt_length: Maximum WKT string length (default from config)
            crs_authid: CRS authority ID for unit-aware simplification
            buffer_value: Buffer value for tolerance calculation
            buffer_segments: Buffer segments (affects precision)
            buffer_type: Buffer end cap type (0=round, 1=flat, 2=square)
            
        Returns:
            GeometryPreparationResult with simplified geometry
        """
        if not geometry or geometry.isEmpty():
            return GeometryPreparationResult(
                success=False,
                error_message="Empty or None geometry"
            )
        
        # Use configured max if not specified
        if max_wkt_length is None:
            max_wkt_length = self._config.max_wkt_length
        
        # Determine WKT precision
        wkt_precision = self._get_wkt_precision_from_authid(crs_authid)
        
        # Check if simplification needed
        original_wkt = geometry.asWkt(wkt_precision)
        original_length = len(original_wkt)
        
        if original_length <= max_wkt_length:
            return GeometryPreparationResult(
                success=True,
                geometry=geometry,
                wkt=original_wkt.replace("'", "''")
            )
        
        logger.info(
            f"Simplifying geometry: {original_length} chars → target {max_wkt_length}"
        )
        
        # Calculate reduction ratio needed
        reduction_ratio = max_wkt_length / original_length
        
        # Get geometry extent for tolerance calculation
        extent = geometry.boundingBox()
        extent_size = max(extent.width(), extent.height())
        
        # Determine if geographic CRS
        is_geographic = self._is_geographic_crs(crs_authid)
        
        # Calculate initial tolerance
        initial_tolerance = self._calculate_simplification_tolerance(
            extent_size=extent_size,
            reduction_ratio=reduction_ratio,
            is_geographic=is_geographic,
            buffer_value=buffer_value,
            buffer_segments=buffer_segments,
            buffer_type=buffer_type
        )
        
        # Progressive simplification
        tolerance = initial_tolerance
        best_simplified = geometry
        best_wkt_length = original_length
        max_attempts = 15
        tolerance_multiplier = 2.0
        
        # Get tolerance limits
        min_tolerance = 0.1 / 111000.0 if is_geographic else 0.1
        max_tolerance = 100.0 / 111000.0 if is_geographic else 100.0
        
        # Increase max tolerance for extreme reductions
        if reduction_ratio < 0.01:
            max_tolerance *= min(1.0 / reduction_ratio, 100)
        
        for attempt in range(max_attempts):
            if tolerance > max_tolerance:
                break
            
            simplified = geometry.simplify(tolerance)
            
            if simplified is None or simplified.isEmpty():
                tolerance *= 1.5
                continue
            
            # Check geometry type preserved
            if QgsWkbTypes.geometryType(simplified.wkbType()) != QgsWkbTypes.geometryType(geometry.wkbType()):
                tolerance *= tolerance_multiplier
                continue
            
            simplified_wkt = simplified.asWkt(wkt_precision)
            wkt_length = len(simplified_wkt)
            
            if wkt_length < best_wkt_length:
                best_simplified = simplified
                best_wkt_length = wkt_length
            
            if wkt_length <= max_wkt_length:
                reduction_pct = (1 - wkt_length / original_length) * 100
                logger.info(
                    f"Simplified: {original_length} → {wkt_length} chars "
                    f"({reduction_pct:.1f}% reduction)"
                )
                return GeometryPreparationResult(
                    success=True,
                    geometry=simplified,
                    wkt=simplified_wkt.replace("'", "''")
                )
            
            tolerance *= tolerance_multiplier
        
        # Try fallbacks for extreme cases
        fallback_result = self._try_simplification_fallbacks(
            geometry, max_wkt_length, wkt_precision
        )
        if fallback_result and fallback_result.success:
            return fallback_result
        
        # Return best result even if not under limit
        final_wkt = best_simplified.asWkt(wkt_precision)
        reduction_pct = (1 - len(final_wkt) / original_length) * 100
        logger.warning(
            f"Could not reach target, using best: {original_length} → "
            f"{len(final_wkt)} chars ({reduction_pct:.1f}% reduction)"
        )
        
        return GeometryPreparationResult(
            success=True,  # Partial success
            geometry=best_simplified,
            wkt=final_wkt.replace("'", "''")
        )
    
    def _calculate_simplification_tolerance(
        self,
        extent_size: float,
        reduction_ratio: float,
        is_geographic: bool,
        buffer_value: Optional[float] = None,
        buffer_segments: int = 5,
        buffer_type: int = 0
    ) -> float:
        """Calculate initial tolerance for simplification."""
        import math
        
        # If buffer is applied, use buffer-aware tolerance
        if buffer_value and buffer_value != 0:
            abs_buffer = abs(buffer_value)
            angle_per_segment = math.pi / (2 * buffer_segments)
            max_arc_error = abs_buffer * (1 - math.cos(angle_per_segment / 2))
            tolerance_factor = 2.0 if buffer_type in [1, 2] else 1.0
            base_tolerance = max_arc_error * tolerance_factor
        else:
            if is_geographic:
                base_tolerance = extent_size * 0.0001
            else:
                base_tolerance = extent_size * 0.001
        
        # Scale based on reduction needed
        if reduction_ratio < 0.01:
            scale = 50
        elif reduction_ratio < 0.05:
            scale = 20
        elif reduction_ratio < 0.1:
            scale = 10
        elif reduction_ratio < 0.5:
            scale = 5
        else:
            scale = 2
        
        return base_tolerance * scale
    
    def _try_simplification_fallbacks(
        self,
        geometry: QgsGeometry,
        max_wkt_length: int,
        wkt_precision: int
    ) -> Optional[GeometryPreparationResult]:
        """Try aggressive fallbacks for extreme simplification needs."""
        
        # Fallback 1: Convex Hull
        try:
            hull = geometry.convexHull()
            if hull and not hull.isEmpty():
                hull_wkt = hull.asWkt(wkt_precision)
                if len(hull_wkt) <= max_wkt_length:
                    logger.warning("Using Convex Hull fallback - precision lost")
                    return GeometryPreparationResult(
                        success=True,
                        geometry=hull,
                        wkt=hull_wkt.replace("'", "''")
                    )
        except Exception:
            pass
        
        # Fallback 2: Oriented Bounding Box
        try:
            oriented_bbox = geometry.orientedMinimumBoundingBox()[0]
            if oriented_bbox and not oriented_bbox.isEmpty():
                bbox_wkt = oriented_bbox.asWkt(wkt_precision)
                if len(bbox_wkt) <= max_wkt_length:
                    logger.warning("Using Oriented BBox fallback - precision lost")
                    return GeometryPreparationResult(
                        success=True,
                        geometry=oriented_bbox,
                        wkt=bbox_wkt.replace("'", "''")
                    )
        except Exception:
            pass
        
        # Fallback 3: Simple Bounding Box
        try:
            bbox = geometry.boundingBox()
            if not bbox.isEmpty():
                bbox_geom = QgsGeometry.fromRect(bbox)
                if bbox_geom and not bbox_geom.isEmpty():
                    bbox_wkt = bbox_geom.asWkt(wkt_precision)
                    logger.warning("Using Bounding Box fallback - maximum precision lost")
                    return GeometryPreparationResult(
                        success=True,
                        geometry=bbox_geom,
                        wkt=bbox_wkt.replace("'", "''")
                    )
        except Exception:
            pass
        
        return None
    
    def _is_geographic_crs(self, crs_authid: Optional[str]) -> bool:
        """Check if CRS is geographic based on auth ID."""
        if not crs_authid:
            return False
        try:
            if ':' in crs_authid:
                srid = int(crs_authid.split(':')[1])
            else:
                srid = int(crs_authid)
            return srid == 4326 or (4000 < srid < 5000)
        except (ValueError, IndexError):
            return False
    
    def _get_wkt_precision_from_authid(self, crs_authid: Optional[str]) -> int:
        """Get WKT precision from CRS auth ID string."""
        if self._is_geographic_crs(crs_authid):
            return 8
        return 3
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _repair_geometry(self, geom: QgsGeometry) -> Optional[QgsGeometry]:
        """
        Attempt to repair invalid geometry.
        
        Tries multiple repair strategies:
        1. makeValid()
        2. buffer(0)
        3. simplify then makeValid
        4. convexHull as last resort
        
        Args:
            geom: Geometry to repair
            
        Returns:
            Repaired geometry or None if all strategies fail
        """
        if geom is None or geom.isEmpty():
            return None
        
        # Strategy 1: makeValid
        try:
            repaired = geom.makeValid()
            if repaired and repaired.isGeosValid():
                return repaired
        except Exception:
            pass
        
        # Strategy 2: buffer(0)
        try:
            buffered = geom.buffer(0, 5)
            if buffered and buffered.isGeosValid():
                return buffered
        except Exception:
            pass
        
        # Strategy 3: simplify then makeValid
        try:
            simplified = geom.simplify(0.0001)
            if simplified and not simplified.isEmpty():
                repaired = simplified.makeValid()
                if repaired and repaired.isGeosValid():
                    return repaired
        except Exception:
            pass
        
        # Strategy 4: convexHull
        try:
            hull = geom.convexHull()
            if hull and hull.isGeosValid():
                logger.warning("Using convexHull fallback - some precision lost")
                return hull
        except Exception:
            pass
        
        return None
    
    def _get_wkt_precision(
        self,
        crs: Optional[QgsCoordinateReferenceSystem]
    ) -> int:
        """
        Get optimal WKT precision for CRS.
        
        Args:
            crs: Coordinate reference system
            
        Returns:
            Decimal precision for WKT
        """
        if not crs:
            return self._config.wkt_precision
        
        # Geographic CRS needs more precision
        if crs.isGeographic():
            return 8  # ~1mm at equator
        else:
            return 3  # mm precision for projected


# Factory function for easy instantiation
def create_geometry_preparation_adapter(
    project: Optional[QgsProject] = None,
    config: Optional[GeometryPreparationConfig] = None
) -> GeometryPreparationAdapter:
    """
    Factory function to create GeometryPreparationAdapter.
    
    Args:
        project: QGIS project (uses current if None)
        config: Configuration options
        
    Returns:
        Configured GeometryPreparationAdapter instance
    """
    return GeometryPreparationAdapter(project, config)
