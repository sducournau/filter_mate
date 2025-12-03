"""
Tests for FilterMate Constants Module

Unit tests for modules/constants.py to ensure all constants and helper
functions work correctly.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.constants import (
    # Provider types
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY,
    PROVIDER_TYPE_MAPPING,
    # Geometry types
    GEOMETRY_TYPE_POINT, GEOMETRY_TYPE_LINE, GEOMETRY_TYPE_POLYGON,
    GEOMETRY_TYPE_UNKNOWN, GEOMETRY_TYPE_NULL,
    GEOMETRY_TYPE_STRINGS, GEOMETRY_TYPE_LEGACY_STRINGS,
    # Predicates
    PREDICATE_INTERSECTS, PREDICATE_WITHIN, PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS, PREDICATE_CROSSES, PREDICATE_TOUCHES,
    PREDICATE_DISJOINT, PREDICATE_EQUALS,
    ALL_PREDICATES, PREDICATE_SQL_MAPPING,
    # Tasks
    TASK_FILTER, TASK_UNFILTER, TASK_EXPORT,
    # Performance thresholds
    PERFORMANCE_THRESHOLD_SMALL, PERFORMANCE_THRESHOLD_MEDIUM,
    PERFORMANCE_THRESHOLD_LARGE, PERFORMANCE_THRESHOLD_XLARGE,
    # Helper functions
    get_provider_name, get_geometry_type_string,
    get_sql_predicate, should_warn_performance,
)


class TestProviderConstants:
    """Test provider type constants and mappings"""
    
    def test_provider_constants_are_strings(self):
        """Ensure all provider constants are strings"""
        assert isinstance(PROVIDER_POSTGRES, str)
        assert isinstance(PROVIDER_SPATIALITE, str)
        assert isinstance(PROVIDER_OGR, str)
        assert isinstance(PROVIDER_MEMORY, str)
    
    def test_provider_type_mapping_complete(self):
        """Ensure mapping covers all QGIS provider types"""
        assert 'postgres' in PROVIDER_TYPE_MAPPING
        assert 'spatialite' in PROVIDER_TYPE_MAPPING
        assert 'ogr' in PROVIDER_TYPE_MAPPING
        assert 'memory' in PROVIDER_TYPE_MAPPING
    
    def test_provider_mapping_values_correct(self):
        """Ensure mappings return correct values"""
        assert PROVIDER_TYPE_MAPPING['postgres'] == PROVIDER_POSTGRES
        assert PROVIDER_TYPE_MAPPING['spatialite'] == PROVIDER_SPATIALITE
        assert PROVIDER_TYPE_MAPPING['ogr'] == PROVIDER_OGR
    
    def test_get_provider_name_known_types(self):
        """Test get_provider_name with known provider types"""
        assert get_provider_name('postgres') == 'postgresql'
        assert get_provider_name('spatialite') == 'spatialite'
        assert get_provider_name('ogr') == 'ogr'
    
    def test_get_provider_name_unknown_type(self):
        """Test get_provider_name with unknown provider type"""
        result = get_provider_name('unknown_provider')
        assert result == 'unknown_provider'  # Should return input unchanged


class TestGeometryConstants:
    """Test geometry type constants and functions"""
    
    def test_geometry_type_constants_are_integers(self):
        """Ensure geometry type constants are integers"""
        assert isinstance(GEOMETRY_TYPE_POINT, int)
        assert isinstance(GEOMETRY_TYPE_LINE, int)
        assert isinstance(GEOMETRY_TYPE_POLYGON, int)
    
    def test_geometry_type_values_match_qgis(self):
        """Ensure geometry type values match QGIS enum"""
        assert GEOMETRY_TYPE_POINT == 0
        assert GEOMETRY_TYPE_LINE == 1
        assert GEOMETRY_TYPE_POLYGON == 2
    
    def test_geometry_type_strings_complete(self):
        """Ensure all geometry types have string representations"""
        for geom_type in [GEOMETRY_TYPE_POINT, GEOMETRY_TYPE_LINE, 
                          GEOMETRY_TYPE_POLYGON, GEOMETRY_TYPE_UNKNOWN]:
            assert geom_type in GEOMETRY_TYPE_STRINGS
            assert geom_type in GEOMETRY_TYPE_LEGACY_STRINGS
    
    def test_get_geometry_type_string_standard_format(self):
        """Test standard format geometry type strings"""
        assert get_geometry_type_string(GEOMETRY_TYPE_POINT) == 'Point'
        assert get_geometry_type_string(GEOMETRY_TYPE_LINE) == 'Line'
        assert get_geometry_type_string(GEOMETRY_TYPE_POLYGON) == 'Polygon'
    
    def test_get_geometry_type_string_legacy_format(self):
        """Test legacy format geometry type strings"""
        assert get_geometry_type_string(GEOMETRY_TYPE_POINT, legacy_format=True) == 'GeometryType.Point'
        assert get_geometry_type_string(GEOMETRY_TYPE_LINE, legacy_format=True) == 'GeometryType.Line'
        assert get_geometry_type_string(GEOMETRY_TYPE_POLYGON, legacy_format=True) == 'GeometryType.Polygon'
    
    def test_get_geometry_type_string_unknown(self):
        """Test unknown geometry type"""
        assert get_geometry_type_string(999) == 'Unknown'
        assert get_geometry_type_string(999, legacy_format=True) == 'GeometryType.Unknown'


class TestPredicateConstants:
    """Test spatial predicate constants"""
    
    def test_all_predicates_list_complete(self):
        """Ensure ALL_PREDICATES contains all predicates"""
        assert PREDICATE_INTERSECTS in ALL_PREDICATES
        assert PREDICATE_WITHIN in ALL_PREDICATES
        assert PREDICATE_CONTAINS in ALL_PREDICATES
        assert PREDICATE_OVERLAPS in ALL_PREDICATES
        assert len(ALL_PREDICATES) == 8  # Should have 8 predicates
    
    def test_predicate_sql_mapping_has_all_predicates(self):
        """Ensure SQL mapping covers all predicates"""
        for predicate in ALL_PREDICATES:
            assert predicate in PREDICATE_SQL_MAPPING
    
    def test_predicate_sql_mapping_case_insensitive(self):
        """Ensure SQL mapping works with lowercase"""
        assert 'intersects' in PREDICATE_SQL_MAPPING
        assert 'within' in PREDICATE_SQL_MAPPING
        assert PREDICATE_SQL_MAPPING['intersects'] == PREDICATE_SQL_MAPPING[PREDICATE_INTERSECTS]
    
    def test_get_sql_predicate(self):
        """Test get_sql_predicate function"""
        assert get_sql_predicate('Intersects') == 'ST_Intersects'
        assert get_sql_predicate('intersects') == 'ST_Intersects'
        assert get_sql_predicate('Within') == 'ST_Within'
    
    def test_get_sql_predicate_unknown(self):
        """Test get_sql_predicate with unknown predicate"""
        result = get_sql_predicate('CustomPredicate')
        assert result == 'ST_CustomPredicate'  # Should add ST_ prefix


class TestPerformanceThresholds:
    """Test performance threshold constants and warning function"""
    
    def test_thresholds_are_ascending(self):
        """Ensure performance thresholds are in ascending order"""
        assert PERFORMANCE_THRESHOLD_SMALL < PERFORMANCE_THRESHOLD_MEDIUM
        assert PERFORMANCE_THRESHOLD_MEDIUM < PERFORMANCE_THRESHOLD_LARGE
        assert PERFORMANCE_THRESHOLD_LARGE < PERFORMANCE_THRESHOLD_XLARGE
    
    def test_should_warn_performance_small_dataset(self):
        """Test no warning for small datasets"""
        should_warn, severity, message = should_warn_performance(5000, has_postgresql=False)
        assert should_warn is False
    
    def test_should_warn_performance_medium_dataset_no_postgres(self):
        """Test info warning for medium dataset without PostgreSQL"""
        should_warn, severity, message = should_warn_performance(30000, has_postgresql=False)
        assert should_warn is True
        assert severity == 'info'
        assert 'PostgreSQL' in message
    
    def test_should_warn_performance_medium_dataset_with_postgres(self):
        """Test no warning for medium dataset with PostgreSQL"""
        should_warn, severity, message = should_warn_performance(30000, has_postgresql=True)
        assert should_warn is False
    
    def test_should_warn_performance_large_dataset_no_postgres(self):
        """Test warning for large dataset without PostgreSQL"""
        should_warn, severity, message = should_warn_performance(75000, has_postgresql=False)
        assert should_warn is True
        assert severity == 'warning'
        assert 'Large dataset' in message
    
    def test_should_warn_performance_xlarge_dataset_no_postgres(self):
        """Test critical warning for very large dataset without PostgreSQL"""
        should_warn, severity, message = should_warn_performance(600000, has_postgresql=False)
        assert should_warn is True
        assert severity == 'critical'
        assert 'Extremely large' in message
    
    def test_should_warn_performance_xlarge_dataset_with_postgres(self):
        """Test warning for very large dataset even with PostgreSQL"""
        should_warn, severity, message = should_warn_performance(600000, has_postgresql=True)
        assert should_warn is True
        assert severity == 'warning'
        assert 'significant time' in message


class TestTaskConstants:
    """Test task type constants"""
    
    def test_task_constants_are_strings(self):
        """Ensure task constants are strings"""
        assert isinstance(TASK_FILTER, str)
        assert isinstance(TASK_UNFILTER, str)
        assert isinstance(TASK_EXPORT, str)
    
    def test_task_constants_unique(self):
        """Ensure task constants are unique"""
        tasks = [TASK_FILTER, TASK_UNFILTER, TASK_EXPORT]
        assert len(tasks) == len(set(tasks))


class TestBufferConstants:
    """Test buffer type constants"""
    
    def test_buffer_types_defined(self):
        """Ensure buffer type constants exist"""
        from modules.constants import BUFFER_TYPE_FIXED, BUFFER_TYPE_EXPRESSION, BUFFER_TYPE_NONE
        assert BUFFER_TYPE_FIXED is not None
        assert BUFFER_TYPE_EXPRESSION is not None
        assert BUFFER_TYPE_NONE is None


class TestCombineOperatorConstants:
    """Test combine operator constants"""
    
    def test_combine_operators_defined(self):
        """Ensure combine operators are defined"""
        from modules.constants import COMBINE_AND, COMBINE_OR
        assert COMBINE_AND == 'AND'
        assert COMBINE_OR == 'OR'


class TestUIConstants:
    """Test UI-related constants"""
    
    def test_tab_indices_defined(self):
        """Ensure tab indices are defined"""
        from modules.constants import (
            TAB_EXPLORING, TAB_FILTERING, TAB_EXPORTING, TAB_CONFIGURATION
        )
        assert TAB_EXPLORING == 0
        assert TAB_FILTERING == 1
        assert TAB_EXPORTING == 2
        assert TAB_CONFIGURATION == 3
    
    def test_message_durations_defined(self):
        """Ensure message bar durations are defined"""
        from modules.constants import (
            MESSAGE_DURATION_SHORT, MESSAGE_DURATION_MEDIUM, MESSAGE_DURATION_LONG
        )
        assert MESSAGE_DURATION_SHORT == 3
        assert MESSAGE_DURATION_MEDIUM == 5
        assert MESSAGE_DURATION_LONG == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
