"""
Unit Tests for FilterChain System

Test coverage for Filter, FilterType, and FilterChain classes.

Author: FilterMate Team
Date: 2026-01-21
"""

import unittest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from core.filter.filter_chain import (
    Filter,
    FilterType,
    FilterChain,
    CombinationStrategy,
    DEFAULT_PRIORITIES
)


class TestFilterType(unittest.TestCase):
    """Test FilterType enum."""
    
    def test_all_types_exist(self):
        """Verify all expected filter types are defined."""
        expected_types = [
            'SPATIAL_SELECTION',
            'FIELD_CONDITION',
            'FID_LIST',
            'CUSTOM_EXPRESSION',
            'USER_SELECTION',
            'BUFFER_INTERSECT',
            'SPATIAL_RELATION',
            'BBOX_FILTER',
            'MATERIALIZED_VIEW'
        ]
        
        for type_name in expected_types:
            self.assertTrue(hasattr(FilterType, type_name))
    
    def test_default_priorities_complete(self):
        """Verify all filter types have default priorities."""
        for filter_type in FilterType:
            self.assertIn(filter_type, DEFAULT_PRIORITIES)
            self.assertIsInstance(DEFAULT_PRIORITIES[filter_type], int)
            self.assertGreaterEqual(DEFAULT_PRIORITIES[filter_type], 1)
            self.assertLessEqual(DEFAULT_PRIORITIES[filter_type], 100)


class TestFilter(unittest.TestCase):
    """Test Filter dataclass."""
    
    def test_filter_creation(self):
        """Test basic filter creation."""
        filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (1, 2, 3)",
            layer_name="test_layer"
        )
        
        self.assertEqual(filter.filter_type, FilterType.SPATIAL_SELECTION)
        self.assertEqual(filter.expression, "pk IN (1, 2, 3)")
        self.assertEqual(filter.layer_name, "test_layer")
        self.assertEqual(filter.combine_operator, "AND")
        self.assertFalse(filter.is_temporary)
        self.assertIsInstance(filter.created_at, datetime)
    
    def test_auto_priority_assignment(self):
        """Test that priority is auto-assigned from defaults."""
        filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="test",
            layer_name="layer"
        )
        
        expected_priority = DEFAULT_PRIORITIES[FilterType.SPATIAL_SELECTION]
        self.assertEqual(filter.priority, expected_priority)
    
    def test_custom_priority(self):
        """Test custom priority overrides default."""
        custom_priority = 99
        filter = Filter(
            filter_type=FilterType.FIELD_CONDITION,
            expression="test",
            layer_name="layer",
            priority=custom_priority
        )
        
        self.assertEqual(filter.priority, custom_priority)
    
    def test_validation_valid_filter(self):
        """Test validation passes for valid filter."""
        filter = Filter(
            filter_type=FilterType.CUSTOM_EXPRESSION,
            expression="status = 'active'",
            layer_name="layer",
            priority=50
        )
        
        is_valid, error_msg = filter.validate()
        self.assertTrue(is_valid)
        self.assertIsNone(error_msg)
    
    def test_validation_empty_expression(self):
        """Test validation fails for empty expression."""
        filter = Filter(
            filter_type=FilterType.CUSTOM_EXPRESSION,
            expression="",
            layer_name="layer"
        )
        
        is_valid, error_msg = filter.validate()
        self.assertFalse(is_valid)
        self.assertIn("empty", error_msg.lower())
    
    def test_validation_no_layer_name(self):
        """Test validation fails without layer name."""
        filter = Filter(
            filter_type=FilterType.CUSTOM_EXPRESSION,
            expression="test",
            layer_name=""
        )
        
        is_valid, error_msg = filter.validate()
        self.assertFalse(is_valid)
        self.assertIn("layer name", error_msg.lower())
    
    def test_validation_invalid_priority(self):
        """Test validation fails for invalid priority."""
        filter = Filter(
            filter_type=FilterType.CUSTOM_EXPRESSION,
            expression="test",
            layer_name="layer",
            priority=150  # Out of range
        )
        
        is_valid, error_msg = filter.validate()
        self.assertFalse(is_valid)
        self.assertIn("priority", error_msg.lower())
    
    def test_validation_invalid_operator(self):
        """Test validation fails for invalid combine operator."""
        filter = Filter(
            filter_type=FilterType.CUSTOM_EXPRESSION,
            expression="test",
            layer_name="layer",
            combine_operator="XOR"  # Invalid
        )
        
        is_valid, error_msg = filter.validate()
        self.assertFalse(is_valid)
        self.assertIn("operator", error_msg.lower())
    
    def test_to_sql(self):
        """Test SQL conversion."""
        filter = Filter(
            filter_type=FilterType.FIELD_CONDITION,
            expression="status = 'active'",
            layer_name="layer"
        )
        
        sql = filter.to_sql('postgresql')
        self.assertEqual(sql, "status = 'active'")
    
    def test_filter_hashable(self):
        """Test that filters are hashable for caching."""
        filter1 = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (1, 2, 3)",
            layer_name="layer"
        )
        
        filter2 = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (1, 2, 3)",
            layer_name="layer"
        )
        
        # Same content should produce same hash
        self.assertEqual(hash(filter1), hash(filter2))
        
        # Should work in sets
        filter_set = {filter1, filter2}
        self.assertEqual(len(filter_set), 1)


class TestFilterChain(unittest.TestCase):
    """Test FilterChain class."""
    
    def setUp(self):
        """Setup mock layer for testing."""
        self.mock_layer = Mock()
        self.mock_layer.name.return_value = "test_layer"
    
    def test_chain_creation(self):
        """Test basic chain creation."""
        chain = FilterChain(self.mock_layer)
        
        self.assertEqual(chain.target_layer, self.mock_layer)
        self.assertEqual(len(chain.filters), 0)
        self.assertEqual(chain.combination_strategy, CombinationStrategy.PRIORITY_AND)
    
    def test_add_filter(self):
        """Test adding a filter to chain."""
        chain = FilterChain(self.mock_layer)
        
        filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (1, 2, 3)",
            layer_name="test"
        )
        
        result = chain.add_filter(filter)
        
        self.assertTrue(result)
        self.assertEqual(len(chain), 1)
        self.assertIn(filter, chain.filters)
    
    def test_add_invalid_filter(self):
        """Test that invalid filters are rejected."""
        chain = FilterChain(self.mock_layer)
        
        invalid_filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="",  # Empty - invalid
            layer_name="test"
        )
        
        result = chain.add_filter(invalid_filter)
        
        self.assertFalse(result)
        self.assertEqual(len(chain), 0)
    
    def test_remove_filter_by_type(self):
        """Test removing filters by type."""
        chain = FilterChain(self.mock_layer)
        
        # Add multiple filters of different types
        filter1 = Filter(FilterType.SPATIAL_SELECTION, "expr1", "layer")
        filter2 = Filter(FilterType.FIELD_CONDITION, "expr2", "layer")
        filter3 = Filter(FilterType.SPATIAL_SELECTION, "expr3", "layer")
        
        chain.add_filter(filter1)
        chain.add_filter(filter2)
        chain.add_filter(filter3)
        
        # Remove SPATIAL_SELECTION filters
        removed_count = chain.remove_filter(FilterType.SPATIAL_SELECTION)
        
        self.assertEqual(removed_count, 2)
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain.filters[0], filter2)
    
    def test_get_filters_by_type(self):
        """Test retrieving filters by type."""
        chain = FilterChain(self.mock_layer)
        
        filter1 = Filter(FilterType.SPATIAL_SELECTION, "expr1", "layer")
        filter2 = Filter(FilterType.FIELD_CONDITION, "expr2", "layer")
        filter3 = Filter(FilterType.SPATIAL_SELECTION, "expr3", "layer")
        
        chain.add_filter(filter1)
        chain.add_filter(filter2)
        chain.add_filter(filter3)
        
        spatial_filters = chain.get_filters_by_type(FilterType.SPATIAL_SELECTION)
        
        self.assertEqual(len(spatial_filters), 2)
        self.assertIn(filter1, spatial_filters)
        self.assertIn(filter3, spatial_filters)
    
    def test_has_filter_type(self):
        """Test checking for filter type existence."""
        chain = FilterChain(self.mock_layer)
        
        filter = Filter(FilterType.SPATIAL_SELECTION, "expr", "layer")
        chain.add_filter(filter)
        
        self.assertTrue(chain.has_filter_type(FilterType.SPATIAL_SELECTION))
        self.assertFalse(chain.has_filter_type(FilterType.FIELD_CONDITION))
    
    def test_clear(self):
        """Test clearing all filters."""
        chain = FilterChain(self.mock_layer)
        
        chain.add_filter(Filter(FilterType.SPATIAL_SELECTION, "expr1", "layer"))
        chain.add_filter(Filter(FilterType.FIELD_CONDITION, "expr2", "layer"))
        
        chain.clear()
        
        self.assertEqual(len(chain), 0)
        self.assertFalse(chain)
    
    def test_build_expression_empty(self):
        """Test building expression with no filters."""
        chain = FilterChain(self.mock_layer)
        
        expr = chain.build_expression()
        
        self.assertEqual(expr, "")
    
    def test_build_expression_single_filter(self):
        """Test building expression with single filter."""
        chain = FilterChain(self.mock_layer)
        
        filter = Filter(
            filter_type=FilterType.FIELD_CONDITION,
            expression="status = 'active'",
            layer_name="layer"
        )
        chain.add_filter(filter)
        
        expr = chain.build_expression()
        
        self.assertEqual(expr, "status = 'active'")
    
    def test_build_expression_multiple_filters_and(self):
        """Test building expression with multiple filters (AND combination)."""
        chain = FilterChain(self.mock_layer, CombinationStrategy.PRIORITY_AND)
        
        filter1 = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (1, 2, 3)",
            layer_name="layer",
            priority=80
        )
        filter2 = Filter(
            filter_type=FilterType.FIELD_CONDITION,
            expression="status = 'active'",
            layer_name="layer",
            priority=50
        )
        
        chain.add_filter(filter1)
        chain.add_filter(filter2)
        
        expr = chain.build_expression()
        
        # Should be combined with AND, higher priority first
        self.assertIn("pk IN (1, 2, 3)", expr)
        self.assertIn("status = 'active'", expr)
        self.assertIn("AND", expr)
    
    def test_build_expression_priority_order(self):
        """Test that filters are applied in priority order."""
        chain = FilterChain(self.mock_layer, CombinationStrategy.PRIORITY_AND)
        
        filter1 = Filter(
            filter_type=FilterType.FIELD_CONDITION,
            expression="filter_priority_50",
            layer_name="layer",
            priority=50
        )
        filter2 = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="filter_priority_80",
            layer_name="layer",
            priority=80
        )
        filter3 = Filter(
            filter_type=FilterType.MATERIALIZED_VIEW,
            expression="filter_priority_100",
            layer_name="layer",
            priority=100
        )
        
        # Add in random order
        chain.add_filter(filter1)
        chain.add_filter(filter3)
        chain.add_filter(filter2)
        
        expr = chain.build_expression()
        
        # Check order: priority 100, 80, 50
        pos_100 = expr.find("filter_priority_100")
        pos_80 = expr.find("filter_priority_80")
        pos_50 = expr.find("filter_priority_50")
        
        self.assertLess(pos_100, pos_80)
        self.assertLess(pos_80, pos_50)
    
    def test_build_expression_caching(self):
        """Test that expressions are cached."""
        chain = FilterChain(self.mock_layer)
        
        filter = Filter(FilterType.FIELD_CONDITION, "status = 'active'", "layer")
        chain.add_filter(filter)
        
        # First call - builds expression
        expr1 = chain.build_expression()
        
        # Second call - should use cache
        expr2 = chain.build_expression()
        
        self.assertEqual(expr1, expr2)
        self.assertGreater(len(chain._cache), 0)
    
    def test_cache_invalidation_on_add(self):
        """Test that cache is invalidated when adding filter."""
        chain = FilterChain(self.mock_layer)
        
        filter1 = Filter(FilterType.FIELD_CONDITION, "expr1", "layer")
        chain.add_filter(filter1)
        chain.build_expression()  # Populate cache
        
        self.assertGreater(len(chain._cache), 0)
        
        filter2 = Filter(FilterType.SPATIAL_SELECTION, "expr2", "layer")
        chain.add_filter(filter2)
        
        # Cache should be cleared
        self.assertEqual(len(chain._cache), 0)
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        chain = FilterChain(self.mock_layer)
        
        filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (1, 2, 3)",
            layer_name="source_layer",
            priority=80,
            metadata={'count': 3}
        )
        chain.add_filter(filter)
        
        data = chain.to_dict()
        
        self.assertEqual(data['target_layer'], "test_layer")
        self.assertEqual(data['strategy'], "priority_and")
        self.assertEqual(data['filter_count'], 1)
        self.assertEqual(len(data['filters']), 1)
        
        filter_data = data['filters'][0]
        self.assertEqual(filter_data['type'], "spatial_selection")
        self.assertEqual(filter_data['expression'], "pk IN (1, 2, 3)")
        self.assertEqual(filter_data['layer_name'], "source_layer")
        self.assertEqual(filter_data['priority'], 80)
        self.assertEqual(filter_data['metadata'], {'count': 3})
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            'target_layer': 'test_layer',
            'strategy': 'priority_and',
            'filter_count': 1,
            'filters': [
                {
                    'type': 'spatial_selection',
                    'expression': 'pk IN (1, 2, 3)',
                    'layer_name': 'source_layer',
                    'priority': 80,
                    'operator': 'AND',
                    'metadata': {'count': 3},
                    'is_temporary': False,
                    'created_at': '2026-01-21T10:00:00'
                }
            ]
        }
        
        chain = FilterChain.from_dict(data, self.mock_layer)
        
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain.combination_strategy, CombinationStrategy.PRIORITY_AND)
        
        filter = chain.filters[0]
        self.assertEqual(filter.filter_type, FilterType.SPATIAL_SELECTION)
        self.assertEqual(filter.expression, "pk IN (1, 2, 3)")
        self.assertEqual(filter.layer_name, "source_layer")
        self.assertEqual(filter.priority, 80)
    
    def test_replace_existing_filter(self):
        """Test replacing existing filters of same type."""
        chain = FilterChain(self.mock_layer)
        
        filter1 = Filter(FilterType.SPATIAL_SELECTION, "old_expr", "layer")
        chain.add_filter(filter1)
        
        filter2 = Filter(FilterType.SPATIAL_SELECTION, "new_expr", "layer")
        chain.add_filter(filter2, replace_existing=True)
        
        # Should have only one SPATIAL_SELECTION filter (the new one)
        spatial_filters = chain.get_filters_by_type(FilterType.SPATIAL_SELECTION)
        self.assertEqual(len(spatial_filters), 1)
        self.assertEqual(spatial_filters[0].expression, "new_expr")
    
    def test_bool_conversion(self):
        """Test truthiness of FilterChain."""
        chain = FilterChain(self.mock_layer)
        
        # Empty chain is falsy
        self.assertFalse(chain)
        
        # Chain with filters is truthy
        chain.add_filter(Filter(FilterType.FIELD_CONDITION, "expr", "layer"))
        self.assertTrue(chain)


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world usage scenarios."""
    
    def setUp(self):
        """Setup mock layers."""
        self.ducts_layer = Mock()
        self.ducts_layer.name.return_value = "ducts"
        
        self.structures_layer = Mock()
        self.structures_layer.name.return_value = "structures"
    
    def test_scenario_ducts_with_zone_pop_and_custom_expression(self):
        """
        Scenario: Couche ducts avec filtre zone_pop + custom expression.
        
        Expected: zone_pop (priority 80) ET custom expression (priority 30)
        """
        chain = FilterChain(self.ducts_layer)
        
        # Filtre spatial zone_pop
        zone_pop_filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (SELECT pk FROM zone_pop WHERE uuid IN ('a', 'b', 'c'))",
            layer_name="zone_pop",
            priority=80,
            metadata={'source': 'zone_pop', 'count': 3}
        )
        chain.add_filter(zone_pop_filter)
        
        # Custom expression pour exploration
        custom_filter = Filter(
            filter_type=FilterType.CUSTOM_EXPRESSION,
            expression="status = 'active'",
            layer_name="ducts",
            priority=30,
            metadata={'user_defined': True}
        )
        chain.add_filter(custom_filter)
        
        # Build expression
        expr = chain.build_expression()
        
        # Verify both filters are present and combined with AND
        self.assertIn("pk IN (SELECT pk FROM zone_pop", expr)
        self.assertIn("status = 'active'", expr)
        self.assertIn("AND", expr)
        
        # Verify order (zone_pop before custom_expression due to priority)
        pos_zone = expr.find("zone_pop")
        pos_custom = expr.find("status")
        self.assertLess(pos_zone, pos_custom)
    
    def test_scenario_structures_with_buffer_intersect(self):
        """
        Scenario: Couche structures avec zone_pop + buffer intersect ducts.
        
        Expected: zone_pop (80) ET buffer intersect (60)
        """
        chain = FilterChain(self.structures_layer)
        
        # Filtre spatial hérité (zone_pop)
        zone_pop_filter = Filter(
            filter_type=FilterType.SPATIAL_SELECTION,
            expression="pk IN (SELECT pk FROM zone_pop WHERE uuid IN ('a', 'b', 'c'))",
            layer_name="zone_pop",
            priority=80
        )
        chain.add_filter(zone_pop_filter)
        
        # Buffer intersect avec ducts
        buffer_filter = Filter(
            filter_type=FilterType.BUFFER_INTERSECT,
            expression="""EXISTS (
                SELECT 1 FROM ducts AS __source
                WHERE ST_Intersects(structures.geom, ST_Buffer(__source.geom, 50))
                AND __source.pk IN (SELECT pk FROM zone_pop WHERE uuid IN ('a', 'b', 'c'))
            )""",
            layer_name="ducts",
            priority=60,
            metadata={'buffer_distance': 50, 'source_layer': 'ducts'}
        )
        chain.add_filter(buffer_filter)
        
        # Build expression
        expr = chain.build_expression()
        
        # Verify both filters present
        self.assertIn("zone_pop", expr)
        self.assertIn("ST_Buffer", expr)
        self.assertIn("AND", expr)
        
        print("\n=== SCENARIO: Structures with buffer ===")
        print(chain)
        print(f"\nFinal expression ({len(expr)} chars):")
        print(expr)
    
    def test_scenario_optimization_with_materialized_view(self):
        """
        Scenario: Large FID selection optimized with MV.
        
        Expected: MATERIALIZED_VIEW (100) replaces FID_LIST
        """
        chain = FilterChain(self.ducts_layer)
        
        # Initial FID list (large)
        fid_filter = Filter(
            filter_type=FilterType.FID_LIST,
            expression=f"pk IN ({', '.join(str(i) for i in range(1000))})",
            layer_name="ducts",
            priority=70
        )
        chain.add_filter(fid_filter)
        
        # Build initial expression
        expr_before = chain.build_expression()
        self.assertGreater(len(expr_before), 3000)  # Large expression
        
        # Optimize with MV
        mv_filter = Filter(
            filter_type=FilterType.MATERIALIZED_VIEW,
            expression="pk IN (SELECT pk FROM mv_selection_ducts_20260121)",
            layer_name="ducts",
            priority=100,
            metadata={'mv_name': 'mv_selection_ducts_20260121', 'fid_count': 1000},
            is_temporary=True
        )
        
        # Replace FID_LIST with MV
        chain.add_filter(mv_filter, replace_existing=False)
        chain.remove_filter(FilterType.FID_LIST)
        
        # Build optimized expression
        expr_after = chain.build_expression()
        
        # Verify MV is used and expression is much shorter
        self.assertIn("mv_selection", expr_after)
        self.assertLess(len(expr_after), len(expr_before) / 10)
        
        print("\n=== SCENARIO: MV Optimization ===")
        print(f"Before: {len(expr_before)} chars")
        print(f"After: {len(expr_after)} chars")
        print(f"Reduction: {100 * (1 - len(expr_after) / len(expr_before)):.1f}%")


if __name__ == '__main__':
    unittest.main()
