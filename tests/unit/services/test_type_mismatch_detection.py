# -*- coding: utf-8 -*-
"""
Tests for Type Mismatch Detection.

FIX v4.8.2 (2026-01-25): Tests for detecting VARCHAR fields in numeric comparisons.

Author: FilterMate Team (Bmad Master)
Date: 2026-01-25
"""
import pytest
from core.services.expression_service import ExpressionService


class TestTypeMismatchDetection:
    """Tests for detect_type_mismatches method."""
    
    @pytest.fixture
    def service(self):
        """Create ExpressionService instance."""
        return ExpressionService()
    
    @pytest.fixture
    def sample_field_types(self):
        """Sample field type mapping (lowercase)."""
        return {
            'importance': 'character varying',
            'fid': 'integer',
            'nature': 'varchar',
            'longueur': 'numeric',
            'nom': 'text',
            'id_unique': 'bigint',
        }
    
    def test_detects_varchar_in_numeric_comparison(self, service, sample_field_types):
        """Should detect VARCHAR field in numeric comparison."""
        expression = '"importance" < 4'
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) > 0
        assert 'importance' in warnings[0]
        assert 'VARCHAR' in warnings[0]
        assert '::integer' in warnings[0]
    
    def test_detects_multiple_mismatches(self, service, sample_field_types):
        """Should detect multiple type mismatches in one expression."""
        expression = '"importance" < 4 AND "nature" = \'test\' AND "importance" >= 2'
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        # Should detect both "importance" < 4 and "importance" >= 2
        assert len(warnings) >= 2
        importance_warnings = [w for w in warnings if 'importance' in w]
        assert len(importance_warnings) == 2
    
    def test_no_warning_for_integer_fields(self, service, sample_field_types):
        """Should NOT warn for INTEGER fields in numeric comparisons."""
        expression = '"fid" < 100'
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) == 0
    
    def test_no_warning_for_already_casted_fields(self, service, sample_field_types):
        """Should NOT warn if field already has ::integer cast."""
        expression = '"importance"::integer < 4'
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) == 0
    
    def test_no_warning_for_numeric_fields(self, service, sample_field_types):
        """Should NOT warn for NUMERIC fields in numeric comparisons."""
        expression = '"longueur" > 1000.5'
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) == 0
    
    def test_detects_integer_in_like_comparison(self, service, sample_field_types):
        """Should detect INTEGER field in LIKE comparison."""
        expression = '"fid" LIKE \'123%\''
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) > 0
        assert 'fid' in warnings[0]
        assert 'INTEGER' in warnings[0].upper()
        assert '::text' in warnings[0]
    
    def test_no_warning_for_text_in_like(self, service, sample_field_types):
        """Should NOT warn for TEXT fields in LIKE comparison."""
        expression = '"nom" LIKE \'Route%\''
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) == 0
    
    def test_handles_complex_expression(self, service, sample_field_types):
        """Should handle complex expressions with multiple operators."""
        expression = (
            '("importance" < 4 OR "importance" = 5) '
            'AND "nature" = \'Route à 1 chaussée\' '
            'AND "fid" > 1000'
        )
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        # Should detect "importance" < 4 and "importance" = 5
        assert len(warnings) >= 2
        importance_warnings = [w for w in warnings if 'importance' in w]
        assert len(importance_warnings) == 2
    
    def test_empty_expression(self, service, sample_field_types):
        """Should handle empty expression."""
        warnings = service.detect_type_mismatches('', sample_field_types)
        assert warnings == []
    
    def test_no_field_types(self, service):
        """Should handle missing field types dict."""
        expression = '"importance" < 4'
        warnings = service.detect_type_mismatches(expression, None)
        assert warnings == []
    
    def test_real_world_qgis_expression(self, service, sample_field_types):
        """Test with real expression from the error logs."""
        expression = (
            '((((((("nature" = \'Bac ou liaison maritime\') OR ("nature" = \'Bretelle\')) '
            'OR (("nature" = \'Rond-point\') AND TRUE)) '
            'OR (("nature" = \'Route à 1 chaussée\') AND ("importance" < 4))) '
            'OR (("nature" = \'Route à 2 chaussées\') AND TRUE)) '
            'OR ("nature" = \'Type autoroutier\'))'
        )
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        # Should detect "importance" < 4
        assert len(warnings) >= 1
        assert any('importance' in w for w in warnings)
        assert any('< 4' in w or '<= 4' in w or '< ' in w for w in warnings)
    
    def test_suggestion_format(self, service, sample_field_types):
        """Warning should include specific suggestion."""
        expression = '"importance" >= 3'
        
        warnings = service.detect_type_mismatches(expression, sample_field_types)
        
        assert len(warnings) == 1
        # Should suggest the exact fix
        assert '"importance"::integer >= 3' in warnings[0]


class TestFieldTypeSuggestions:
    """Tests for type cast suggestions."""
    
    def test_varchar_to_integer_suggestion(self):
        """Should suggest ::integer for VARCHAR in numeric comparison."""
        from infrastructure.database.field_type_detector import suggest_type_cast
        
        suggestion = suggest_type_cast('importance', 'varchar', 'numeric')
        
        assert suggestion == '"importance"::integer'
    
    def test_integer_to_text_suggestion(self):
        """Should suggest ::text for INTEGER in string comparison."""
        from infrastructure.database.field_type_detector import suggest_type_cast
        
        suggestion = suggest_type_cast('fid', 'integer', 'string')
        
        assert suggestion == '"fid"::text'
    
    def test_no_suggestion_for_matching_types(self):
        """Should NOT suggest cast when types match."""
        from infrastructure.database.field_type_detector import suggest_type_cast
        
        # Integer field in numeric comparison - OK
        suggestion = suggest_type_cast('fid', 'integer', 'numeric')
        assert suggestion is None
        
        # Text field in string comparison - OK
        suggestion = suggest_type_cast('name', 'text', 'string')
        assert suggestion is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
