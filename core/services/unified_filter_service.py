# -*- coding: utf-8 -*-
"""
Unified Filter Service and Factory.

Provides unified interface for filtering both vector and raster layers.
Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

This module contains:
- FilterStrategyFactory: Creates appropriate strategy for layer type
- UnifiedFilterService: Facade for all filter operations

Author: FilterMate Team (BMAD - Amelia)
Date: February 2026
Version: 5.0.0-alpha
"""

import logging
from typing import Optional, Dict, Type, Any, Callable

from ..domain.filter_criteria import (
    LayerType,
    VectorFilterCriteria,
    RasterFilterCriteria,
    UnifiedFilterCriteria,
    validate_criteria
)
from ..strategies.base_filter_strategy import (
    AbstractFilterStrategy,
    FilterContext,
    UnifiedFilterResult,
    FilterStatus
)

logger = logging.getLogger('FilterMate.Services.UnifiedFilter')


class FilterStrategyFactory:
    """Factory for creating filter strategies based on layer type.
    
    Implements the Factory Pattern to decouple strategy creation
    from the client code. Supports registration of custom strategies
    for extensibility.
    
    Usage:
        # Create strategy for known type
        strategy = FilterStrategyFactory.create(LayerType.VECTOR, context)
        
        # Auto-detect from layer ID
        strategy = FilterStrategyFactory.create_for_layer("layer_123", context)
        
        # Register custom strategy
        FilterStrategyFactory.register_strategy(LayerType.MESH, MeshStrategy)
    """
    
    # Registry of strategy classes by layer type
    _strategies: Dict[LayerType, Type[AbstractFilterStrategy]] = {}
    _initialized = False
    
    @classmethod
    def _ensure_initialized(cls):
        """Lazy initialization of default strategies."""
        if cls._initialized:
            return
        
        # Import and register default strategies
        try:
            from ..strategies.vector_filter_strategy import VectorFilterStrategy
            cls._strategies[LayerType.VECTOR] = VectorFilterStrategy
        except ImportError as e:
            logger.warning(f"Could not import VectorFilterStrategy: {e}")
        
        # Raster strategy
        try:
            from ..strategies.raster_filter_strategy import RasterFilterStrategy
            cls._strategies[LayerType.RASTER] = RasterFilterStrategy
        except ImportError as e:
            logger.warning(f"Could not import RasterFilterStrategy: {e}")
        
        cls._initialized = True
    
    @classmethod
    def register_strategy(
        cls,
        layer_type: LayerType,
        strategy_class: Type[AbstractFilterStrategy]
    ) -> None:
        """Register a strategy class for a layer type.
        
        Allows extension with custom strategies for new layer types
        or replacement of default strategies.
        
        Args:
            layer_type: The LayerType to register for
            strategy_class: The strategy class (must inherit AbstractFilterStrategy)
            
        Raises:
            TypeError: If strategy_class doesn't inherit AbstractFilterStrategy
            
        Example:
            FilterStrategyFactory.register_strategy(
                LayerType.MESH,
                MeshFilterStrategy
            )
        """
        if not issubclass(strategy_class, AbstractFilterStrategy):
            raise TypeError(
                f"Strategy class must inherit from AbstractFilterStrategy, "
                f"got {strategy_class.__name__}"
            )
        
        cls._strategies[layer_type] = strategy_class
        logger.info(f"Registered strategy {strategy_class.__name__} for {layer_type}")
    
    @classmethod
    def unregister_strategy(cls, layer_type: LayerType) -> bool:
        """Unregister a strategy for a layer type.
        
        Args:
            layer_type: The LayerType to unregister
            
        Returns:
            True if strategy was unregistered, False if not found
        """
        if layer_type in cls._strategies:
            del cls._strategies[layer_type]
            return True
        return False
    
    @classmethod
    def create(
        cls,
        layer_type: LayerType,
        context: FilterContext
    ) -> AbstractFilterStrategy:
        """Create a strategy instance for the given layer type.
        
        Args:
            layer_type: Type of layer to create strategy for
            context: FilterContext with project and callbacks
            
        Returns:
            Concrete strategy instance
            
        Raises:
            ValueError: If no strategy is registered for the layer type
            
        Example:
            strategy = FilterStrategyFactory.create(LayerType.VECTOR, context)
            result = strategy.apply_filter(criteria)
        """
        cls._ensure_initialized()
        
        strategy_class = cls._strategies.get(layer_type)
        if strategy_class is None:
            available = [lt.value for lt in cls._strategies.keys()]
            raise ValueError(
                f"No strategy registered for layer type: {layer_type.value}. "
                f"Available types: {available}"
            )
        
        return strategy_class(context)
    
    @classmethod
    def create_for_layer(
        cls,
        layer_id: str,
        context: FilterContext
    ) -> AbstractFilterStrategy:
        """Create a strategy by auto-detecting the layer type.
        
        Args:
            layer_id: QGIS layer ID
            context: FilterContext with project
            
        Returns:
            Appropriate strategy instance
            
        Raises:
            ValueError: If layer not found or unsupported type
            
        Example:
            strategy = FilterStrategyFactory.create_for_layer("my_layer_id", context)
        """
        layer_type = cls._detect_layer_type(layer_id, context)
        return cls.create(layer_type, context)
    
    @classmethod
    def get_supported_types(cls) -> list:
        """Get list of supported layer types.
        
        Returns:
            List of LayerType values that have registered strategies
        """
        cls._ensure_initialized()
        return list(cls._strategies.keys())
    
    @classmethod
    def is_supported(cls, layer_type: LayerType) -> bool:
        """Check if a layer type is supported.
        
        Args:
            layer_type: LayerType to check
            
        Returns:
            True if a strategy is registered for this type
        """
        cls._ensure_initialized()
        return layer_type in cls._strategies
    
    @staticmethod
    def _detect_layer_type(layer_id: str, context: FilterContext) -> LayerType:
        """Detect layer type from QGIS layer.
        
        Args:
            layer_id: QGIS layer ID
            context: FilterContext with project
            
        Returns:
            Detected LayerType
            
        Raises:
            ValueError: If layer not found or unsupported
        """
        try:
            from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer
            
            project = context.project or QgsProject.instance()
            layer = project.mapLayer(layer_id)
            
            if layer is None:
                raise ValueError(f"Layer not found: {layer_id}")
            
            if isinstance(layer, QgsVectorLayer):
                return LayerType.VECTOR
            elif isinstance(layer, QgsRasterLayer):
                return LayerType.RASTER
            else:
                raise ValueError(
                    f"Unsupported layer type: {type(layer).__name__}. "
                    f"Expected QgsVectorLayer or QgsRasterLayer."
                )
                
        except ImportError:
            # QGIS not available, try to infer from criteria
            raise ValueError(
                "Cannot detect layer type without QGIS. "
                "Please specify layer type explicitly."
            )


class UnifiedFilterService:
    """Unified service for filtering vector and raster layers.
    
    This is the main facade for all filter operations in FilterMate v5.0.
    It provides a single API regardless of layer type.
    
    Features:
    - Automatic strategy selection based on criteria type
    - Progress reporting via callbacks
    - Cancellation support
    - Backward compatible convenience methods
    
    Usage:
        service = UnifiedFilterService()
        
        # Filter vector layer
        result = service.apply_filter(VectorFilterCriteria(
            layer_id="communes",
            expression="population > 10000"
        ))
        
        # Filter raster layer  
        result = service.apply_filter(RasterFilterCriteria(
            layer_id="dem",
            min_value=500,
            max_value=1500
        ))
        
        # Export
        result = service.export(criteria, "/tmp/output.shp")
    """
    
    def __init__(
        self,
        project: Any = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None
    ):
        """Initialize the unified filter service.
        
        Args:
            project: QGIS project instance (or None for current project)
            progress_callback: Callback for progress updates (percent, message)
            cancel_callback: Callback to check for cancellation
        """
        self.context = FilterContext(
            project=project,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback
        )
        self._current_strategy: Optional[AbstractFilterStrategy] = None
    
    def apply_filter(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> UnifiedFilterResult:
        """Apply filter based on the criteria type.
        
        Automatically detects whether criteria is for vector or raster
        and uses the appropriate strategy.
        
        Args:
            criteria: VectorFilterCriteria or RasterFilterCriteria
            
        Returns:
            UnifiedFilterResult with operation results
            
        Example:
            result = service.apply_filter(VectorFilterCriteria(
                layer_id="my_layer",
                expression="field > 100"
            ))
            
            if result.is_success:
                print(f"Found {result.affected_count} features")
        """
        # Validate criteria first
        is_valid, error = validate_criteria(criteria)
        if not is_valid:
            return UnifiedFilterResult.error(
                layer_id=criteria.layer_id,
                layer_type=criteria.layer_type.value,
                error_message=error,
                expression_raw=criteria.to_display_string()
            )
        
        try:
            # Get appropriate strategy
            strategy = FilterStrategyFactory.create(
                criteria.layer_type,
                self.context
            )
            self._current_strategy = strategy
            
            # Additional strategy-specific validation
            is_valid, error = strategy.validate_criteria(criteria)
            if not is_valid:
                return UnifiedFilterResult.error(
                    layer_id=criteria.layer_id,
                    layer_type=criteria.layer_type.value,
                    error_message=error,
                    expression_raw=criteria.to_display_string()
                )
            
            # Execute filter
            return strategy.apply_filter(criteria)
            
        except ValueError as e:
            return UnifiedFilterResult.error(
                layer_id=criteria.layer_id,
                layer_type=criteria.layer_type.value,
                error_message=str(e),
                expression_raw=criteria.to_display_string()
            )
        except Exception as e:
            logger.exception(f"Unexpected error in apply_filter: {e}")
            return UnifiedFilterResult.error(
                layer_id=criteria.layer_id,
                layer_type=criteria.layer_type.value,
                error_message=f"Unexpected error: {str(e)}",
                expression_raw=criteria.to_display_string()
            )
    
    def get_preview(
        self, 
        criteria: UnifiedFilterCriteria
    ) -> Dict[str, Any]:
        """Get preview of filter without applying.
        
        Args:
            criteria: Filter criteria to preview
            
        Returns:
            Dict with preview data (content depends on layer type)
        """
        try:
            strategy = FilterStrategyFactory.create(
                criteria.layer_type,
                self.context
            )
            return strategy.get_preview(criteria)
            
        except Exception as e:
            return {
                "type": criteria.layer_type.value,
                "error": str(e)
            }
    
    def export(
        self,
        criteria: UnifiedFilterCriteria,
        output_path: str,
        **export_options
    ) -> UnifiedFilterResult:
        """Export filtered data to file.
        
        Args:
            criteria: Filter criteria
            output_path: Output file path
            **export_options: Format-specific options
            
        Returns:
            UnifiedFilterResult with export status
        """
        try:
            strategy = FilterStrategyFactory.create(
                criteria.layer_type,
                self.context
            )
            self._current_strategy = strategy
            
            return strategy.export(criteria, output_path, **export_options)
            
        except Exception as e:
            return UnifiedFilterResult.error(
                layer_id=criteria.layer_id,
                layer_type=criteria.layer_type.value,
                error_message=str(e),
                expression_raw=criteria.to_display_string()
            )
    
    def cancel(self) -> None:
        """Cancel the current operation."""
        if self._current_strategy:
            self._current_strategy.cancel()
    
    # =========================================================================
    # Backward compatibility methods
    # =========================================================================
    
    def filter_vector(
        self,
        layer_id: str,
        expression: str,
        source_layer_id: Optional[str] = None,
        spatial_predicate: Optional[str] = None,
        buffer_value: float = 0.0,
        use_selection: bool = False
    ) -> UnifiedFilterResult:
        """Convenience method for vector filtering.
        
        Backward compatible with previous API.
        
        Args:
            layer_id: Target layer ID
            expression: Filter expression
            source_layer_id: Source layer for spatial filter
            spatial_predicate: Spatial predicate
            buffer_value: Buffer distance
            use_selection: Filter selected features only
            
        Returns:
            UnifiedFilterResult
        """
        criteria = VectorFilterCriteria(
            layer_id=layer_id,
            expression=expression,
            source_layer_id=source_layer_id,
            spatial_predicate=spatial_predicate,
            buffer_value=buffer_value,
            use_selection=use_selection
        )
        return self.apply_filter(criteria)
    
    def filter_raster(
        self,
        layer_id: str,
        band_index: int = 1,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        mask_layer_id: Optional[str] = None
    ) -> UnifiedFilterResult:
        """Convenience method for raster filtering.
        
        Args:
            layer_id: Raster layer ID
            band_index: Band number (1-based)
            min_value: Minimum value
            max_value: Maximum value
            mask_layer_id: Vector layer for masking
            
        Returns:
            UnifiedFilterResult
        """
        criteria = RasterFilterCriteria(
            layer_id=layer_id,
            band_index=band_index,
            min_value=min_value,
            max_value=max_value,
            mask_layer_id=mask_layer_id
        )
        return self.apply_filter(criteria)
    
    def is_layer_supported(self, layer_id: str) -> bool:
        """Check if a layer can be filtered.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            True if layer type is supported
        """
        try:
            layer_type = FilterStrategyFactory._detect_layer_type(
                layer_id, 
                self.context
            )
            return FilterStrategyFactory.is_supported(layer_type)
        except Exception:
            return False
    
    def get_layer_type(self, layer_id: str) -> Optional[LayerType]:
        """Get the layer type for a layer ID.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            LayerType or None if detection fails
        """
        try:
            return FilterStrategyFactory._detect_layer_type(
                layer_id,
                self.context
            )
        except Exception:
            return None
