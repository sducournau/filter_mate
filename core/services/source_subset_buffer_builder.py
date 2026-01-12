# -*- coding: utf-8 -*-
"""
SourceSubsetBufferBuilder Service

EPIC-1 Phase 14.5: Extracted from FilterTask._initialize_source_subset_and_buffer()

This service initializes source subset expression and buffer parameters, handling:
- Field-based geometric filter mode detection
- Source subset preservation in field-based mode
- Centroids configuration extraction
- Buffer parameters (type, segments, value, expression)
- Optimization approvals from UI

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase 14.5)
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger('FilterMate.Core.Services.SourceSubsetBufferBuilder')


# =============================================================================
# Constants
# =============================================================================

BUFFER_TYPE_MAPPING = {
    "Round": 0,
    "Flat": 1,
    "Square": 2
}

DEFAULT_BUFFER_TYPE = 0  # Round
DEFAULT_BUFFER_SEGMENTS = 5


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SourceSubsetBufferConfig:
    """Result of source subset and buffer configuration."""
    # Subset configuration
    source_new_subset: str
    is_field_based_mode: bool = False
    field_name: Optional[str] = None
    
    # Centroids configuration
    use_centroids_source_layer: bool = False
    use_centroids_distant_layers: bool = False
    
    # Optimizations
    approved_optimizations: Dict[str, Any] = field(default_factory=dict)
    auto_apply_optimizations: bool = False
    
    # Buffer configuration
    has_buffer: bool = False
    buffer_value: float = 0.0
    buffer_expression: Optional[str] = None
    buffer_type: int = DEFAULT_BUFFER_TYPE
    buffer_segments: int = DEFAULT_BUFFER_SEGMENTS


@dataclass
class SubsetBufferBuilderContext:
    """Context for subset/buffer building."""
    task_parameters: Dict[str, Any]
    expression: str
    old_subset: str
    is_field_expression: Optional[Tuple[bool, str]] = None


# =============================================================================
# Helper Functions
# =============================================================================

def clean_buffer_value(value: float) -> float:
    """
    Clean buffer value from float precision errors.
    
    FIX v3.0.12: Convert 0.9999999 → 1.0, etc.
    
    Args:
        value: Raw buffer value
        
    Returns:
        Cleaned buffer value
    """
    if value is None:
        return 0.0
    
    # Round to 6 decimal places to avoid precision errors
    return round(float(value), 6)


# =============================================================================
# SourceSubsetBufferBuilder Service
# =============================================================================

class SourceSubsetBufferBuilder:
    """
    Service for building source subset and buffer configuration.
    
    This service extracts initialization logic from FilterTask,
    making it testable and reusable.
    
    Example:
        builder = SourceSubsetBufferBuilder()
        config = builder.build(context)
        print(f"Buffer: {config.buffer_value}m")
        print(f"Type: {config.buffer_type}")
    """
    
    def build(self, context: SubsetBufferBuilderContext) -> SourceSubsetBufferConfig:
        """
        Build source subset and buffer configuration.
        
        Args:
            context: Builder context with task parameters and expressions
            
        Returns:
            SourceSubsetBufferConfig with all initialized values
        """
        logger.info("🔧 SourceSubsetBufferBuilder.build() START")
        
        # Step 1: Detect field-based mode
        mode_info = self._detect_field_based_mode(context)
        
        # Step 2: Initialize source subset
        source_new_subset = self._initialize_source_subset(context, mode_info)
        
        # Step 3: Extract centroids configuration
        centroids_config = self._extract_centroids_config(context)
        
        # Step 4: Extract optimizations
        optimizations = self._extract_optimizations(context)
        
        # Step 5: Extract buffer configuration
        buffer_config = self._extract_buffer_config(context)
        
        logger.info("✓ SourceSubsetBufferBuilder.build() END")
        
        # Build result
        return SourceSubsetBufferConfig(
            source_new_subset=source_new_subset,
            is_field_based_mode=mode_info['is_field_based'],
            field_name=mode_info.get('field_name'),
            use_centroids_source_layer=centroids_config['source'],
            use_centroids_distant_layers=centroids_config['distant'],
            approved_optimizations=optimizations['approved'],
            auto_apply_optimizations=optimizations['auto_apply'],
            has_buffer=buffer_config['has_buffer'],
            buffer_value=buffer_config['value'],
            buffer_expression=buffer_config['expression'],
            buffer_type=buffer_config['type'],
            buffer_segments=buffer_config['segments']
        )
    
    def _detect_field_based_mode(
        self,
        context: SubsetBufferBuilderContext
    ) -> Dict[str, Any]:
        """
        Detect if we're in field-based geometric filter mode.
        
        In this mode:
        - is_field_expression = (True, field_name)
        - expression = old_subset
        - Source layer preserves its existing subset
        
        Returns:
            Dict with 'is_field_based' and optional 'field_name'
        """
        is_field_expr = context.is_field_expression
        
        is_field_based = (
            is_field_expr is not None and
            isinstance(is_field_expr, tuple) and
            len(is_field_expr) >= 2 and
            is_field_expr[0] is True
        )
        
        result = {'is_field_based': is_field_based}
        
        if is_field_based:
            field_name = is_field_expr[1]
            result['field_name'] = field_name
            logger.info(f"  🔄 FIELD-BASED MODE: Preserving source layer filter")
            logger.info(f"  → Field name: '{field_name}'")
            logger.info(f"  → Source layer keeps its current state")
        
        return result
    
    def _initialize_source_subset(
        self,
        context: SubsetBufferBuilderContext,
        mode_info: Dict[str, Any]
    ) -> str:
        """
        Initialize source subset based on mode.
        
        Args:
            context: Builder context
            mode_info: Field-based mode detection result
            
        Returns:
            Source new subset expression
        """
        if mode_info['is_field_based']:
            # CRITICAL: Always preserve existing subset in field-based mode
            subset = context.old_subset
            
            if subset:
                logger.info(f"  ✓ Existing subset preserved: '{subset[:80]}...'")
                logger.info(f"  ✓ Source geometries from filtered layer for intersection")
            else:
                logger.info(f"  ℹ No existing subset - all features will be used")
            
            return subset
        else:
            # Standard mode: Check if expression is a field
            try:
                from qgis.core import QgsExpression
                if QgsExpression(context.expression).isField() is False:
                    return context.expression
                else:
                    return context.old_subset
            except Exception as e:
                logger.warning(f"Could not evaluate expression type: {e}")
                return context.old_subset
    
    def _extract_centroids_config(
        self,
        context: SubsetBufferBuilderContext
    ) -> Dict[str, bool]:
        """Extract centroids configuration."""
        filtering_params = context.task_parameters.get("filtering", {})
        
        source = filtering_params.get("use_centroids_source_layer", False)
        distant = filtering_params.get("use_centroids_distant_layers", False)
        
        logger.info(f"  use_centroids_source_layer: {source}")
        logger.info(f"  use_centroids_distant_layers: {distant}")
        
        return {'source': source, 'distant': distant}
    
    def _extract_optimizations(
        self,
        context: SubsetBufferBuilderContext
    ) -> Dict[str, Any]:
        """Extract pre-approved optimizations from UI."""
        task_params = context.task_parameters.get("task", {})
        
        approved = task_params.get("approved_optimizations", {})
        auto_apply = task_params.get("auto_apply_optimizations", False)
        
        if approved:
            logger.info(f"  ✓ User-approved optimizations loaded: {len(approved)} layer(s)")
            for layer_id, opts in approved.items():
                logger.info(f"    - {layer_id[:8]}...: {opts}")
        elif auto_apply:
            logger.info(f"  ✓ Auto-apply optimizations enabled")
        
        return {'approved': approved, 'auto_apply': auto_apply}
    
    def _extract_buffer_config(
        self,
        context: SubsetBufferBuilderContext
    ) -> Dict[str, Any]:
        """Extract buffer configuration."""
        filtering_params = context.task_parameters.get("filtering", {})
        
        has_buffer = filtering_params.get("has_buffer_value", False)
        logger.info(f"  has_buffer_value: {has_buffer}")
        
        # Extract buffer type
        buffer_type_config = self._extract_buffer_type(filtering_params)
        
        if not has_buffer:
            logger.info(f"  ℹ️  NO BUFFER configured")
            return {
                'has_buffer': False,
                'value': 0.0,
                'expression': None,
                'type': buffer_type_config['type'],
                'segments': buffer_type_config['segments']
            }
        
        # Extract buffer value/expression
        buffer_property = filtering_params.get("buffer_value_property", False)
        buffer_expr = filtering_params.get("buffer_value_expression")
        buffer_val_raw = filtering_params.get("buffer_value", 0)
        
        # FIX v3.0.12: Clean buffer value from float precision errors
        buffer_val = clean_buffer_value(buffer_val_raw)
        
        logger.info(f"  buffer_value_property (override active): {buffer_property}")
        logger.info(f"  buffer_value_expression: '{buffer_expr}'")
        logger.info(f"  buffer_value (spinbox): {buffer_val}")
        
        # Determine final buffer value/expression
        final_value, final_expr = self._resolve_buffer_value(
            buffer_expr,
            buffer_val,
            buffer_property
        )
        
        return {
            'has_buffer': True,
            'value': final_value,
            'expression': final_expr,
            'type': buffer_type_config['type'],
            'segments': buffer_type_config['segments']
        }
    
    def _extract_buffer_type(
        self,
        filtering_params: Dict[str, Any]
    ) -> Dict[str, int]:
        """Extract buffer type and segments."""
        has_buffer_type = filtering_params.get("has_buffer_type", False)
        buffer_type_str = filtering_params.get("buffer_type", "Round")
        
        logger.info(f"  has_buffer_type: {has_buffer_type}")
        logger.info(f"  buffer_type: {buffer_type_str}")
        
        if has_buffer_type:
            buffer_type = BUFFER_TYPE_MAPPING.get(buffer_type_str, DEFAULT_BUFFER_TYPE)
            buffer_segments = filtering_params.get("buffer_segments", DEFAULT_BUFFER_SEGMENTS)
            
            logger.info(f"  ✓ Buffer type: {buffer_type_str} (END_CAP_STYLE={buffer_type})")
            logger.info(f"  ✓ Buffer segments: {buffer_segments}")
        else:
            buffer_type = DEFAULT_BUFFER_TYPE
            buffer_segments = DEFAULT_BUFFER_SEGMENTS
            logger.info(f"  ℹ️  Buffer type default: Round (0), segments=5")
        
        return {'type': buffer_type, 'segments': buffer_segments}
    
    def _resolve_buffer_value(
        self,
        buffer_expr: Optional[str],
        buffer_val: float,
        buffer_property: bool
    ) -> Tuple[float, Optional[str]]:
        """
        Resolve final buffer value and expression.
        
        Priority:
        1. buffer_value_expression (if valid)
        2. buffer_value (spinbox)
        
        Returns:
            Tuple of (value, expression)
        """
        # Check expression first (property override)
        if buffer_expr and buffer_expr.strip():
            try:
                # Try to convert to float - if successful, it's static
                numeric_value = clean_buffer_value(float(buffer_expr))
                logger.info(f"  ✓ Buffer from property override (numeric): {numeric_value}m")
                logger.info(f"  ℹ️  Expression '{buffer_expr}' converted to static value")
                return numeric_value, None
            except (ValueError, TypeError):
                # It's a dynamic expression (field reference or complex expression)
                logger.info(f"  ✓ Buffer from property override (DYNAMIC): {buffer_expr}")
                logger.info(f"  ℹ️  Will evaluate expression per feature")
                
                if buffer_property:
                    logger.info(f"  ✓ Property override button confirmed ACTIVE")
                else:
                    logger.warning(f"  ⚠️  Expression found but property=False")
                
                return 0.0, buffer_expr
        
        # Fallback to spinbox value
        if buffer_val is not None and buffer_val != 0:
            logger.info(f"  ✓ Buffer from spinbox: {buffer_val}m")
            return buffer_val, None
        
        # No valid buffer
        logger.warning(f"  ⚠️  No valid buffer value, defaulting to 0m")
        return 0.0, None


# =============================================================================
# Factory Function
# =============================================================================

def create_source_subset_buffer_builder() -> SourceSubsetBufferBuilder:
    """
    Factory function to create a SourceSubsetBufferBuilder.
    
    Returns:
        SourceSubsetBufferBuilder instance
    """
    return SourceSubsetBufferBuilder()


# =============================================================================
# Convenience Function for Direct Use
# =============================================================================

def build_source_subset_buffer_config(
    task_parameters: Dict[str, Any],
    expression: str,
    old_subset: str,
    is_field_expression: Optional[Tuple[bool, str]] = None
) -> SourceSubsetBufferConfig:
    """
    Build source subset and buffer configuration.
    
    Convenience function that creates a builder and builds configuration.
    
    Args:
        task_parameters: Task parameters dict
        expression: Current filter expression
        old_subset: Existing subset from source layer
        is_field_expression: Field expression tuple (is_field, field_name)
        
    Returns:
        SourceSubsetBufferConfig result
    """
    context = SubsetBufferBuilderContext(
        task_parameters=task_parameters,
        expression=expression,
        old_subset=old_subset,
        is_field_expression=is_field_expression
    )
    
    builder = create_source_subset_buffer_builder()
    return builder.build(context)
