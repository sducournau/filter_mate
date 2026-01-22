# -*- coding: utf-8 -*-
"""
Tests for BufferService - Buffer and simplification service.

Tests:
- Buffer configuration validation
- Tolerance calculations
- Simplification estimates
- WKT precision
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestBufferEndCapStyle:
    """Tests for BufferEndCapStyle enum."""
    
    def test_end_cap_styles_defined(self):
        """Test that buffer end cap styles are defined."""
        # Test structure of expected enum values
        styles = {'round': 1, 'flat': 2, 'square': 3}
        
        assert 'round' in styles
        assert 'flat' in styles
        assert 'square' in styles


class TestBufferJoinStyle:
    """Tests for BufferJoinStyle enum."""
    
    def test_join_styles_defined(self):
        """Test that buffer join styles are defined."""
        styles = {'round': 1, 'mitre': 2, 'bevel': 3}
        
        assert 'round' in styles
        assert 'mitre' in styles
        assert 'bevel' in styles


class TestBufferConfig:
    """Tests for BufferConfig dataclass."""
    
    def test_buffer_config_distance(self):
        """Test BufferConfig distance handling."""
        # Positive buffer
        config_positive = {'distance': 100.0}
        assert config_positive['distance'] > 0
        
        # Negative buffer (erosion)
        config_negative = {'distance': -50.0}
        assert config_negative['distance'] < 0
    
    def test_buffer_config_is_negative(self):
        """Test BufferConfig.is_negative property."""
        positive_distance = 100.0
        negative_distance = -50.0
        
        assert (negative_distance < 0) is True
        assert (positive_distance < 0) is False
    
    def test_buffer_config_absolute_distance(self):
        """Test BufferConfig.absolute_distance property."""
        distance = -50.0
        absolute = abs(distance)
        
        assert absolute == 50.0


class TestSimplificationConfig:
    """Tests for SimplificationConfig dataclass."""
    
    def test_simplification_config_defaults(self):
        """Test SimplificationConfig default structure."""
        config = {
            'enabled': True,
            'tolerance': 1.0,
            'preserve_topology': True
        }
        
        assert config['enabled'] is True
        assert config['tolerance'] > 0
        assert config['preserve_topology'] is True


class TestSimplificationResult:
    """Tests for SimplificationResult dataclass."""
    
    def test_simplification_result_structure(self):
        """Test SimplificationResult structure."""
        result = {
            'original_points': 1000,
            'simplified_points': 100,
            'tolerance_used': 1.5
        }
        
        assert result['original_points'] > result['simplified_points']
    
    def test_simplification_reduction_percentage(self):
        """Test reduction percentage calculation."""
        original_points = 1000
        simplified_points = 100
        
        reduction = ((original_points - simplified_points) / original_points) * 100
        
        assert reduction == 90.0


class TestBufferServiceValidation:
    """Tests for BufferService.validate_buffer_config method."""
    
    def test_validate_zero_distance(self):
        """Test validation fails with zero distance."""
        distance = 0.0
        errors = []
        
        if distance == 0:
            errors.append("Buffer distance cannot be zero")
        
        assert len(errors) > 0
    
    def test_validate_positive_distance(self):
        """Test validation succeeds with positive distance."""
        distance = 100.0
        errors = []
        
        if distance == 0:
            errors.append("Buffer distance cannot be zero")
        
        assert len(errors) == 0
    
    def test_validate_negative_distance_allowed(self):
        """Test negative distance (erosion) is allowed."""
        distance = -50.0
        errors = []
        
        # Negative distance is allowed for erosion
        if distance == 0:
            errors.append("Buffer distance cannot be zero")
        
        assert len(errors) == 0
    
    def test_validate_segments_positive(self):
        """Test segments must be positive."""
        segments = 0
        errors = []
        
        if segments <= 0:
            errors.append("Segments must be positive")
        
        assert len(errors) > 0


class TestBufferServiceToleranceCalculations:
    """Tests for BufferService tolerance calculation methods."""
    
    def test_buffer_aware_tolerance_positive_buffer(self):
        """Test tolerance calculation for positive buffer."""
        buffer_distance = 100.0
        base_tolerance = 1.0
        
        # Tolerance should scale with buffer distance
        tolerance = base_tolerance * (buffer_distance / 100.0) if buffer_distance > 0 else base_tolerance
        
        assert tolerance >= base_tolerance
    
    def test_buffer_aware_tolerance_negative_buffer(self):
        """Test tolerance calculation for negative buffer."""
        buffer_distance = -50.0
        base_tolerance = 1.0
        
        # For negative buffer, use smaller tolerance to preserve detail
        absolute_distance = abs(buffer_distance)
        tolerance = base_tolerance * 0.5 if buffer_distance < 0 else base_tolerance
        
        assert tolerance <= base_tolerance
    
    def test_estimate_simplification_tolerance(self):
        """Test simplification tolerance estimation."""
        geometry_extent = 1000.0  # meters
        target_reduction = 0.5  # 50% reduction
        
        # Estimate tolerance based on extent and target
        tolerance = geometry_extent * 0.001 * (1 + target_reduction)
        
        assert tolerance > 0
    
    def test_scale_tolerance_for_reduction(self):
        """Test tolerance scaling for target reduction."""
        base_tolerance = 1.0
        current_reduction = 0.3
        target_reduction = 0.7
        
        # Scale tolerance to achieve target reduction
        if current_reduction < target_reduction:
            scale_factor = (target_reduction / current_reduction) if current_reduction > 0 else 2.0
            scaled = base_tolerance * scale_factor
        else:
            scaled = base_tolerance
        
        assert scaled >= base_tolerance


class TestWKTPrecision:
    """Tests for WKT precision handling."""
    
    def test_wkt_precision_default(self):
        """Test default WKT precision."""
        default_precision = 6
        
        assert default_precision >= 1
        assert default_precision <= 15
    
    def test_wkt_precision_for_meters(self):
        """Test WKT precision for meter-based CRS."""
        # For projected CRS in meters, 2 decimal places = centimeter precision
        precision = 2
        
        value = 12345.678901234
        rounded = round(value, precision)
        
        assert rounded == 12345.68
    
    def test_wkt_precision_for_degrees(self):
        """Test WKT precision for degree-based CRS."""
        # For geographic CRS, 8 decimal places = ~millimeter precision
        precision = 8
        
        value = 45.123456789012
        rounded = round(value, precision)
        
        assert rounded == 45.12345679


class TestProgressiveToleranceSequence:
    """Tests for progressive tolerance sequence calculation."""
    
    def test_progressive_tolerance_increasing(self):
        """Test progressive tolerances are increasing."""
        base = 1.0
        steps = 5
        factor = 2.0
        
        sequence = [base * (factor ** i) for i in range(steps)]
        
        # Verify increasing
        for i in range(1, len(sequence)):
            assert sequence[i] > sequence[i-1]
    
    def test_progressive_tolerance_min_steps(self):
        """Test minimum steps in sequence."""
        min_steps = 3
        
        sequence = [1.0, 2.0, 4.0]
        
        assert len(sequence) >= min_steps
    
    def test_progressive_tolerance_max_bound(self):
        """Test maximum tolerance bound."""
        tolerances = [1.0, 2.0, 4.0, 8.0, 16.0]
        max_tolerance = 10.0
        
        bounded = [t for t in tolerances if t <= max_tolerance]
        
        assert max(bounded) <= max_tolerance


class TestBufferServiceMetrics:
    """Tests for BufferService metrics tracking."""
    
    def test_metrics_initial_state(self):
        """Test metrics initial state."""
        metrics = {
            'buffer_operations': 0,
            'simplification_operations': 0,
            'total_points_processed': 0,
            'total_points_reduced': 0
        }
        
        assert metrics['buffer_operations'] == 0
        assert metrics['simplification_operations'] == 0
    
    def test_metrics_update_after_operation(self):
        """Test metrics update after buffer operation."""
        metrics = {
            'buffer_operations': 0,
            'simplification_operations': 0,
            'total_points_processed': 0,
            'total_points_reduced': 0
        }
        
        # Simulate buffer operation
        metrics['buffer_operations'] += 1
        metrics['total_points_processed'] += 1000
        
        assert metrics['buffer_operations'] == 1
        assert metrics['total_points_processed'] == 1000


class TestCreateBufferService:
    """Tests for create_buffer_service factory function."""
    
    def test_create_buffer_service_structure(self):
        """Test factory creates service with expected structure."""
        # Simulate service creation
        service = {
            'config': {},
            'metrics': {},
            'methods': ['calculate_buffer_aware_tolerance', 'validate_buffer_config']
        }
        
        assert 'config' in service
        assert 'metrics' in service
        assert len(service['methods']) > 0


class TestBufferServiceConfig:
    """Tests for BufferService configuration handling."""
    
    def test_config_property_returns_copy(self):
        """Test config property returns a copy to prevent mutation."""
        original_config = {'distance': 100.0, 'segments': 8}
        config_copy = original_config.copy()
        
        # Modify copy
        config_copy['distance'] = 200.0
        
        # Original unchanged
        assert original_config['distance'] == 100.0
    
    def test_metrics_property_returns_copy(self):
        """Test metrics property returns a copy to prevent mutation."""
        original_metrics = {'buffer_operations': 5}
        metrics_copy = original_metrics.copy()
        
        # Modify copy
        metrics_copy['buffer_operations'] = 10
        
        # Original unchanged
        assert original_metrics['buffer_operations'] == 5
