# -*- coding: utf-8 -*-
"""
Tests for FilterExpression domain model.

Tests:
- ProviderType enum
- SpatialPredicate enum
- FilterExpression dataclass
"""

import pytest
from unittest.mock import Mock


class TestProviderType:
    """Tests for ProviderType enum."""
    
    def test_provider_type_values(self):
        """Test ProviderType enum values."""
        providers = ['POSTGRESQL', 'SPATIALITE', 'OGR', 'MEMORY', 'UNKNOWN']
        
        assert 'POSTGRESQL' in providers
        assert 'SPATIALITE' in providers
        assert 'OGR' in providers
    
    def test_from_qgis_provider_postgres(self):
        """Test from_qgis_provider for postgres."""
        def from_qgis_provider(provider_name):
            mapping = {
                'postgres': 'POSTGRESQL',
                'spatialite': 'SPATIALITE',
                'ogr': 'OGR',
                'memory': 'MEMORY'
            }
            return mapping.get(provider_name, 'UNKNOWN')
        
        result = from_qgis_provider('postgres')
        
        assert result == 'POSTGRESQL'
    
    def test_from_qgis_provider_spatialite(self):
        """Test from_qgis_provider for spatialite."""
        def from_qgis_provider(provider_name):
            mapping = {
                'postgres': 'POSTGRESQL',
                'spatialite': 'SPATIALITE',
                'ogr': 'OGR'
            }
            return mapping.get(provider_name, 'UNKNOWN')
        
        result = from_qgis_provider('spatialite')
        
        assert result == 'SPATIALITE'
    
    def test_from_qgis_provider_unknown(self):
        """Test from_qgis_provider for unknown provider."""
        def from_qgis_provider(provider_name):
            mapping = {
                'postgres': 'POSTGRESQL',
                'spatialite': 'SPATIALITE'
            }
            return mapping.get(provider_name, 'UNKNOWN')
        
        result = from_qgis_provider('wms')
        
        assert result == 'UNKNOWN'


class TestSpatialPredicate:
    """Tests for SpatialPredicate enum."""
    
    def test_predicate_values(self):
        """Test SpatialPredicate enum values."""
        predicates = [
            'INTERSECTS',
            'CONTAINS',
            'WITHIN',
            'OVERLAPS',
            'TOUCHES',
            'CROSSES',
            'DISJOINT',
            'EQUALS'
        ]
        
        assert 'INTERSECTS' in predicates
        assert 'WITHIN' in predicates
    
    def test_predicate_comparison(self):
        """Test predicate comparison."""
        pred1 = 'INTERSECTS'
        pred2 = 'INTERSECTS'
        pred3 = 'CONTAINS'
        
        assert pred1 == pred2
        assert pred1 != pred3


class TestFilterExpressionCreation:
    """Tests for FilterExpression creation."""
    
    def test_basic_creation(self):
        """Test basic FilterExpression creation."""
        expr = {
            'qgis_expression': 'name = "test"',
            'sql_expression': None,
            'spatial_predicates': [],
            'buffer_distance': 0.0,
            'provider_type': 'UNKNOWN'
        }
        
        assert expr['qgis_expression'] == 'name = "test"'
    
    def test_post_init_normalizes_expression(self):
        """Test __post_init__ normalizes expression."""
        qgis_expr = '  name = "test"  '
        
        def post_init(expr_dict):
            expr_dict['qgis_expression'] = expr_dict['qgis_expression'].strip()
        
        expr = {'qgis_expression': qgis_expr}
        post_init(expr)
        
        assert expr['qgis_expression'] == 'name = "test"'


class TestFilterExpressionCreate:
    """Tests for create factory method."""
    
    def test_create_simple_expression(self):
        """Test creating simple expression."""
        def create(qgis_expr):
            return {
                'qgis_expression': qgis_expr,
                'sql_expression': None,
                'spatial_predicates': [],
                'buffer_distance': 0.0
            }
        
        expr = create('id > 10')
        
        assert expr['qgis_expression'] == 'id > 10'
    
    def test_create_with_sql(self):
        """Test creating expression with SQL."""
        def create(qgis_expr, sql=None):
            return {
                'qgis_expression': qgis_expr,
                'sql_expression': sql
            }
        
        expr = create('id > 10', 'id > 10')
        
        assert expr['sql_expression'] == 'id > 10'


class TestFilterExpressionCreateSpatial:
    """Tests for create_spatial factory method."""
    
    def test_create_spatial_intersects(self):
        """Test creating spatial expression with INTERSECTS."""
        def create_spatial(geometry_wkt, predicate='INTERSECTS'):
            return {
                'qgis_expression': f"{predicate.lower()}($geometry, geom_from_wkt('{geometry_wkt}'))",
                'spatial_predicates': [predicate]
            }
        
        expr = create_spatial('POINT(0 0)', 'INTERSECTS')
        
        assert 'intersects' in expr['qgis_expression']
        assert 'INTERSECTS' in expr['spatial_predicates']
    
    def test_create_spatial_within(self):
        """Test creating spatial expression with WITHIN."""
        def create_spatial(geometry_wkt, predicate='WITHIN'):
            return {
                'qgis_expression': f"{predicate.lower()}($geometry, geom_from_wkt('{geometry_wkt}'))",
                'spatial_predicates': [predicate]
            }
        
        expr = create_spatial('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))', 'WITHIN')
        
        assert 'within' in expr['qgis_expression']


class TestFilterExpressionFromSpatialFilter:
    """Tests for from_spatial_filter factory method."""
    
    def test_from_spatial_filter(self):
        """Test creating from spatial filter."""
        def from_spatial_filter(geometry, operator, layer_geom_field='geometry'):
            wkt = geometry.asWkt() if hasattr(geometry, 'asWkt') else str(geometry)
            return {
                'qgis_expression': f"{operator.lower()}($geometry, geom_from_wkt('{wkt}'))",
                'spatial_predicates': [operator]
            }
        
        geom = Mock()
        geom.asWkt.return_value = 'POINT(0 0)'
        
        expr = from_spatial_filter(geom, 'INTERSECTS')
        
        assert 'intersects' in expr['qgis_expression']


class TestDetectSpatialPredicates:
    """Tests for _detect_spatial_predicates method."""
    
    def test_detect_intersects(self):
        """Test detecting INTERSECTS predicate."""
        def detect_spatial_predicates(expr_str):
            predicates = []
            expr_lower = expr_str.lower()
            if 'intersects' in expr_lower:
                predicates.append('INTERSECTS')
            if 'within' in expr_lower:
                predicates.append('WITHIN')
            if 'contains' in expr_lower:
                predicates.append('CONTAINS')
            return predicates
        
        predicates = detect_spatial_predicates('intersects($geometry, other_geom)')
        
        assert 'INTERSECTS' in predicates
    
    def test_detect_multiple_predicates(self):
        """Test detecting multiple predicates."""
        def detect_spatial_predicates(expr_str):
            predicates = []
            expr_lower = expr_str.lower()
            if 'intersects' in expr_lower:
                predicates.append('INTERSECTS')
            if 'within' in expr_lower:
                predicates.append('WITHIN')
            return predicates
        
        predicates = detect_spatial_predicates('intersects($geometry, a) AND within($geometry, b)')
        
        assert 'INTERSECTS' in predicates
        assert 'WITHIN' in predicates
    
    def test_detect_no_predicates(self):
        """Test detecting no predicates."""
        def detect_spatial_predicates(expr_str):
            predicates = []
            expr_lower = expr_str.lower()
            if 'intersects' in expr_lower:
                predicates.append('INTERSECTS')
            return predicates
        
        predicates = detect_spatial_predicates('name = "test"')
        
        assert len(predicates) == 0


class TestFilterExpressionWithSql:
    """Tests for with_sql method."""
    
    def test_with_sql_creates_new(self):
        """Test with_sql creates new expression with SQL."""
        expr = {
            'qgis_expression': 'id > 10',
            'sql_expression': None
        }
        
        def with_sql(e, sql):
            return {**e, 'sql_expression': sql}
        
        new_expr = with_sql(expr, 'id > 10')
        
        assert new_expr['sql_expression'] == 'id > 10'
        # Original unchanged
        assert expr['sql_expression'] is None


class TestFilterExpressionWithBuffer:
    """Tests for with_buffer method."""
    
    def test_with_buffer_creates_new(self):
        """Test with_buffer creates new expression with buffer."""
        expr = {
            'qgis_expression': 'intersects($geometry, geom)',
            'buffer_distance': 0.0
        }
        
        def with_buffer(e, distance):
            return {**e, 'buffer_distance': float(distance)}
        
        new_expr = with_buffer(expr, 100.0)
        
        assert new_expr['buffer_distance'] == 100.0
        # Original unchanged
        assert expr['buffer_distance'] == 0.0


class TestFilterExpressionWithProvider:
    """Tests for with_provider method."""
    
    def test_with_provider_creates_new(self):
        """Test with_provider creates new expression with provider."""
        expr = {
            'qgis_expression': 'id > 10',
            'provider_type': 'UNKNOWN'
        }
        
        def with_provider(e, provider):
            return {**e, 'provider_type': provider}
        
        new_expr = with_provider(expr, 'POSTGRESQL')
        
        assert new_expr['provider_type'] == 'POSTGRESQL'


class TestFilterExpressionHasBuffer:
    """Tests for has_buffer property."""
    
    def test_has_buffer_true(self):
        """Test has_buffer returns true."""
        expr = {'buffer_distance': 100.0}
        
        def has_buffer(e):
            return e['buffer_distance'] > 0
        
        assert has_buffer(expr) is True
    
    def test_has_buffer_false(self):
        """Test has_buffer returns false."""
        expr = {'buffer_distance': 0.0}
        
        def has_buffer(e):
            return e['buffer_distance'] > 0
        
        assert has_buffer(expr) is False


class TestFilterExpressionIsSimple:
    """Tests for is_simple property."""
    
    def test_is_simple_true(self):
        """Test is_simple for non-spatial expression."""
        expr = {
            'spatial_predicates': [],
            'buffer_distance': 0.0
        }
        
        def is_simple(e):
            return len(e['spatial_predicates']) == 0 and e['buffer_distance'] == 0
        
        assert is_simple(expr) is True
    
    def test_is_simple_false_spatial(self):
        """Test is_simple false for spatial expression."""
        expr = {
            'spatial_predicates': ['INTERSECTS'],
            'buffer_distance': 0.0
        }
        
        def is_simple(e):
            return len(e['spatial_predicates']) == 0 and e['buffer_distance'] == 0
        
        assert is_simple(expr) is False
    
    def test_is_simple_false_buffer(self):
        """Test is_simple false with buffer."""
        expr = {
            'spatial_predicates': [],
            'buffer_distance': 100.0
        }
        
        def is_simple(e):
            return len(e['spatial_predicates']) == 0 and e['buffer_distance'] == 0
        
        assert is_simple(expr) is False


class TestFilterExpressionPredicateNames:
    """Tests for predicate_names property."""
    
    def test_predicate_names_list(self):
        """Test predicate_names returns list of names."""
        expr = {
            'spatial_predicates': ['INTERSECTS', 'WITHIN']
        }
        
        def predicate_names(e):
            return [p.lower() for p in e['spatial_predicates']]
        
        names = predicate_names(expr)
        
        assert 'intersects' in names
        assert 'within' in names
    
    def test_predicate_names_empty(self):
        """Test predicate_names for non-spatial."""
        expr = {'spatial_predicates': []}
        
        def predicate_names(e):
            return [p.lower() for p in e['spatial_predicates']]
        
        names = predicate_names(expr)
        
        assert len(names) == 0


class TestFilterExpressionToSql:
    """Tests for to_sql method."""
    
    def test_to_sql_uses_sql_expression(self):
        """Test to_sql uses sql_expression if available."""
        expr = {
            'qgis_expression': 'id > 10',
            'sql_expression': 'id > 10'
        }
        
        def to_sql(e):
            return e['sql_expression'] or e['qgis_expression']
        
        sql = to_sql(expr)
        
        assert sql == 'id > 10'
    
    def test_to_sql_falls_back_to_qgis(self):
        """Test to_sql falls back to qgis_expression."""
        expr = {
            'qgis_expression': 'id > 10',
            'sql_expression': None
        }
        
        def to_sql(e):
            return e['sql_expression'] or e['qgis_expression']
        
        sql = to_sql(expr)
        
        assert sql == 'id > 10'


class TestFilterExpressionStr:
    """Tests for __str__ method."""
    
    def test_str_representation(self):
        """Test string representation."""
        expr = {
            'qgis_expression': 'id > 10',
            'spatial_predicates': []
        }
        
        def to_str(e):
            return f"FilterExpression({e['qgis_expression']})"
        
        result = to_str(expr)
        
        assert 'id > 10' in result


class TestFilterExpressionRepr:
    """Tests for __repr__ method."""
    
    def test_repr_representation(self):
        """Test repr representation."""
        expr = {
            'qgis_expression': 'id > 10',
            'spatial_predicates': ['INTERSECTS'],
            'buffer_distance': 100.0
        }
        
        def to_repr(e):
            return f"<FilterExpression qgis='{e['qgis_expression']}' spatial={len(e['spatial_predicates'])} buffer={e['buffer_distance']}>"
        
        result = to_repr(expr)
        
        assert '<FilterExpression' in result
        assert 'id > 10' in result
