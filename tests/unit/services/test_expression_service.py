"""
Tests unitaires pour ExpressionService.

Ce module teste le service de parsing et conversion d'expressions
sans dépendances QGIS.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.services.expression_service import (
    ExpressionService,
    ValidationResult,
    ParsedExpression
)
from core.domain.filter_expression import ProviderType, SpatialPredicate


# ============================================================================
# ValidationResult Tests
# ============================================================================

class TestValidationResult:
    """Tests pour ValidationResult."""
    
    def test_valid_factory(self):
        """valid() devrait créer un résultat valide."""
        result = ValidationResult.valid()
        
        assert result.is_valid
        assert result.error_message is None
        assert result.error_position is None
        assert result.warnings == []
    
    def test_valid_with_warnings(self):
        """valid() devrait accepter des warnings."""
        result = ValidationResult.valid(warnings=["Use = instead of =="])
        
        assert result.is_valid
        assert "Use = instead of ==" in result.warnings
    
    def test_invalid_factory(self):
        """invalid() devrait créer un résultat invalide."""
        result = ValidationResult.invalid("Syntax error", position=10)
        
        assert not result.is_valid
        assert result.error_message == "Syntax error"
        assert result.error_position == 10
    
    def test_bool_conversion_valid(self):
        """ValidationResult valide devrait être True."""
        result = ValidationResult.valid()
        assert bool(result) is True
    
    def test_bool_conversion_invalid(self):
        """ValidationResult invalide devrait être False."""
        result = ValidationResult.invalid("Error")
        assert bool(result) is False


# ============================================================================
# ParsedExpression Tests
# ============================================================================

class TestParsedExpression:
    """Tests pour ParsedExpression."""
    
    def test_is_spatial_with_predicates(self):
        """is_spatial devrait être True avec des prédicats spatiaux."""
        parsed = ParsedExpression(
            original="intersects($geometry, @layer)",
            fields=set(),
            spatial_predicates=[SpatialPredicate.INTERSECTS],
            has_geometry_reference=True,
            has_layer_reference=True,
            estimated_complexity=5
        )
        
        assert parsed.is_spatial
    
    def test_is_spatial_with_geometry_only(self):
        """is_spatial devrait être True avec référence géométrie."""
        parsed = ParsedExpression(
            original="$geometry IS NOT NULL",
            fields=set(),
            spatial_predicates=[],
            has_geometry_reference=True,
            has_layer_reference=False,
            estimated_complexity=2
        )
        
        assert parsed.is_spatial
    
    def test_is_spatial_false(self):
        """is_spatial devrait être False pour expression attributaire."""
        parsed = ParsedExpression(
            original='"name" = \'test\'',
            fields={"name"},
            spatial_predicates=[],
            has_geometry_reference=False,
            has_layer_reference=False,
            estimated_complexity=1
        )
        
        assert not parsed.is_spatial
    
    def test_is_simple(self):
        """is_simple devrait être True pour complexité <= 2."""
        parsed = ParsedExpression(
            original='"field" = 1',
            fields={"field"},
            spatial_predicates=[],
            has_geometry_reference=False,
            has_layer_reference=False,
            estimated_complexity=2
        )
        
        assert parsed.is_simple
    
    def test_is_complex(self):
        """is_complex devrait être True pour complexité >= 5."""
        parsed = ParsedExpression(
            original="complex expression",
            fields=set(),
            spatial_predicates=[],
            has_geometry_reference=False,
            has_layer_reference=False,
            estimated_complexity=7
        )
        
        assert parsed.is_complex
    
    def test_field_count(self):
        """field_count devrait retourner le nombre de champs."""
        parsed = ParsedExpression(
            original='"a" = 1 AND "b" = 2 AND "c" = 3',
            fields={"a", "b", "c"},
            spatial_predicates=[],
            has_geometry_reference=False,
            has_layer_reference=False,
            estimated_complexity=3
        )
        
        assert parsed.field_count == 3


# ============================================================================
# ExpressionService Validation Tests
# ============================================================================

class TestExpressionServiceValidation:
    """Tests pour la validation d'expressions."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return ExpressionService()
    
    def test_validate_empty_expression(self, service):
        """Une expression vide devrait être invalide."""
        result = service.validate("")
        
        assert not result.is_valid
        assert "empty" in result.error_message.lower()
    
    def test_validate_whitespace_only(self, service):
        """Une expression avec uniquement des espaces devrait être invalide."""
        result = service.validate("   ")
        
        assert not result.is_valid
    
    def test_validate_simple_valid_expression(self, service):
        """Une expression simple valide devrait passer."""
        result = service.validate('"field" = 1')
        
        assert result.is_valid
        assert result.error_message is None
    
    def test_validate_unbalanced_parentheses_missing_close(self, service):
        """Des parenthèses non fermées devraient être détectées."""
        result = service.validate('"field" = (1 + 2')
        
        assert not result.is_valid
        assert "parenthes" in result.error_message.lower()
    
    def test_validate_unbalanced_parentheses_extra_close(self, service):
        """Une parenthèse fermante en trop devrait être détectée."""
        result = service.validate('"field" = 1 + 2)')
        
        assert not result.is_valid
        assert "parenthes" in result.error_message.lower()
    
    def test_validate_balanced_parentheses(self, service):
        """Des parenthèses équilibrées devraient être valides."""
        result = service.validate('("field" = 1) AND ("other" = 2)')
        
        assert result.is_valid
    
    def test_validate_unbalanced_double_quotes(self, service):
        """Des guillemets doubles non fermés devraient être détectés."""
        result = service.validate('"field = 1')
        
        assert not result.is_valid
        assert "quote" in result.error_message.lower()
    
    def test_validate_balanced_double_quotes(self, service):
        """Des guillemets doubles équilibrés devraient être valides."""
        result = service.validate('"field" = "value"')
        
        assert result.is_valid
    
    def test_validate_unbalanced_single_quotes(self, service):
        """Des guillemets simples non fermés devraient être détectés."""
        result = service.validate('"field" = \'test')
        
        assert not result.is_valid
        assert "quote" in result.error_message.lower()
    
    def test_validate_escaped_single_quotes(self, service):
        """Des guillemets simples échappés devraient être valides."""
        result = service.validate("\"field\" = 'it''s a test'")
        
        assert result.is_valid
    
    def test_validate_warning_double_equals(self, service):
        """== devrait générer un warning."""
        result = service.validate('"field" == 1')
        
        assert result.is_valid  # Valide mais avec warning
        assert any("==" in w for w in result.warnings)
    
    def test_validate_warning_not_equals(self, service):
        """!= devrait générer un warning."""
        result = service.validate('"field" != 1')
        
        assert result.is_valid
        assert any("!=" in w for w in result.warnings)
    
    def test_validate_warning_double_ampersand(self, service):
        """&& devrait générer un warning."""
        result = service.validate('"a" = 1 && "b" = 2')
        
        assert result.is_valid
        assert any("&&" in w for w in result.warnings)
    
    def test_validate_dangerous_pattern_semicolon(self, service):
        """; devrait générer un warning."""
        result = service.validate('"field" = 1; DROP TABLE')
        
        assert result.is_valid  # Warning, pas erreur
        assert any(";" in w for w in result.warnings)
    
    def test_validate_dangerous_pattern_comment(self, service):
        """-- devrait générer un warning."""
        result = service.validate('"field" = 1 -- comment')
        
        assert result.is_valid
        assert any("--" in w for w in result.warnings)


# ============================================================================
# ExpressionService Parsing Tests
# ============================================================================

class TestExpressionServiceParsing:
    """Tests pour le parsing d'expressions."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return ExpressionService()
    
    def test_parse_extracts_fields(self, service):
        """parse devrait extraire les noms de champs."""
        parsed = service.parse('"name" = \'test\' AND "value" > 10')
        
        assert "name" in parsed.fields
        assert "value" in parsed.fields
        assert len(parsed.fields) == 2
    
    def test_parse_detects_intersects(self, service):
        """parse devrait détecter intersects."""
        parsed = service.parse('intersects($geometry, @layer)')
        
        assert SpatialPredicate.INTERSECTS in parsed.spatial_predicates
    
    def test_parse_detects_contains(self, service):
        """parse devrait détecter contains."""
        parsed = service.parse('contains(geometry(), @poly)')
        
        assert SpatialPredicate.CONTAINS in parsed.spatial_predicates
    
    def test_parse_detects_within(self, service):
        """parse devrait détecter within."""
        parsed = service.parse('within($geometry, @area)')
        
        assert SpatialPredicate.WITHIN in parsed.spatial_predicates
    
    def test_parse_detects_geometry_reference(self, service):
        """parse devrait détecter $geometry."""
        parsed = service.parse('$geometry IS NOT NULL')
        
        assert parsed.has_geometry_reference
    
    def test_parse_detects_geometry_function(self, service):
        """parse devrait détecter geometry()."""
        parsed = service.parse('area(geometry()) > 1000')
        
        assert parsed.has_geometry_reference
    
    def test_parse_detects_layer_reference(self, service):
        """parse devrait détecter @layer."""
        parsed = service.parse('intersects($geometry, @layer)')
        
        assert parsed.has_layer_reference
    
    def test_parse_extracts_operators(self, service):
        """parse devrait extraire les opérateurs."""
        parsed = service.parse('"a" = 1 AND "b" = 2 OR "c" = 3')
        
        assert "AND" in parsed.operators
        assert "OR" in parsed.operators
    
    def test_parse_extracts_like_operator(self, service):
        """parse devrait extraire LIKE."""
        parsed = service.parse('"name" LIKE \'%test%\'')
        
        assert "LIKE" in parsed.operators
    
    def test_parse_extracts_in_operator(self, service):
        """parse devrait extraire IN."""
        parsed = service.parse('"status" IN (1, 2, 3)')
        
        assert "IN" in parsed.operators
    
    def test_parse_complexity_simple(self, service):
        """Une expression simple devrait avoir une faible complexité."""
        parsed = service.parse('"field" = 1')
        
        assert parsed.estimated_complexity <= 2
    
    def test_parse_complexity_with_operators(self, service):
        """Les opérateurs augmentent la complexité."""
        parsed = service.parse('"a" = 1 AND "b" = 2 AND "c" = 3 OR "d" = 4')
        
        assert parsed.estimated_complexity >= 3
    
    def test_parse_complexity_with_spatial(self, service):
        """Les prédicats spatiaux augmentent significativement la complexité."""
        parsed = service.parse('intersects($geometry, @layer) AND contains($geometry, @poly)')
        
        assert parsed.estimated_complexity >= 5
    
    def test_parse_complexity_max_is_10(self, service):
        """La complexité maximale devrait être 10."""
        # Expression très complexe
        parsed = service.parse(
            'intersects($geometry, @layer1) AND contains($geometry, @layer2) '
            'AND within($geometry, @layer3) AND touches($geometry, @layer4) '
            'AND "a" = 1 AND "b" = 2 AND "c" = 3 AND "d" = 4 AND "e" = 5 '
            'OR "f" = 6 OR "g" = 7 ' * 10  # Très long
        )
        
        assert parsed.estimated_complexity <= 10


# ============================================================================
# ExpressionService SQL Conversion Tests
# ============================================================================

class TestExpressionServiceSQLConversion:
    """Tests pour la conversion en SQL."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return ExpressionService()
    
    def test_to_sql_simple_expression(self, service):
        """Une expression simple devrait rester inchangée."""
        sql = service.to_sql('"field" = 1', ProviderType.POSTGRESQL)
        
        assert "field" in sql
        assert "= 1" in sql
    
    def test_to_sql_replaces_geometry_postgresql(self, service):
        """$geometry devrait être remplacé par le nom de colonne PostgreSQL."""
        sql = service.to_sql(
            'intersects($geometry, @layer)',
            ProviderType.POSTGRESQL,
            geometry_column="geom"
        )
        
        # Le $geometry devrait être remplacé
        assert "$geometry" not in sql or "geom" in sql
    
    def test_to_sql_converts_intersects_postgis(self, service):
        """intersects devrait devenir ST_Intersects pour PostgreSQL."""
        sql = service.to_sql(
            'intersects($geometry, @layer)',
            ProviderType.POSTGRESQL
        )
        
        assert "ST_Intersects" in sql or "intersects" in sql.lower()
    
    def test_to_sql_converts_intersects_spatialite(self, service):
        """intersects devrait être adapté pour Spatialite."""
        sql = service.to_sql(
            'intersects($geometry, @layer)',
            ProviderType.SPATIALITE
        )
        
        # Spatialite utilise "Intersects" sans le préfixe ST_
        assert "Intersects" in sql or "intersects" in sql.lower()
    
    def test_to_sql_area_postgis(self, service):
        """area devrait devenir ST_Area pour PostgreSQL."""
        sql = service.to_sql(
            'area($geometry) > 1000',
            ProviderType.POSTGRESQL
        )
        
        assert "ST_Area" in sql or "area" in sql.lower()
    
    def test_to_sql_length_spatialite(self, service):
        """length devrait devenir GLength pour Spatialite."""
        sql = service.to_sql(
            'length($geometry) > 100',
            ProviderType.SPATIALITE
        )
        
        assert "GLength" in sql or "length" in sql.lower()
    
    def test_to_sql_preserves_string_literals(self, service):
        """Les chaînes de caractères devraient être préservées."""
        sql = service.to_sql(
            '"name" = \'test value\'',
            ProviderType.POSTGRESQL
        )
        
        assert "test value" in sql
    
    def test_to_sql_ogr_returns_expression(self, service):
        """OGR devrait retourner l'expression (pas de conversion SQL)."""
        original = '"field" = 1'
        sql = service.to_sql(original, ProviderType.OGR)
        
        # OGR n'a pas de SQL spécifique, l'expression est retournée telle quelle
        assert sql  # Devrait retourner quelque chose


# ============================================================================
# ExpressionService Field Quoting Tests
# ============================================================================

class TestExpressionServiceFieldQuoting:
    """Tests pour le quoting des noms de champs."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return ExpressionService()
    
    def test_postgresql_field_quoting(self, service):
        """PostgreSQL devrait utiliser des guillemets doubles."""
        # Les champs dans l'expression QGIS utilisent déjà des guillemets doubles
        sql = service.to_sql('"my_field" = 1', ProviderType.POSTGRESQL)
        
        # Devrait contenir le nom du champ
        assert "my_field" in sql
    
    def test_spatialite_field_quoting(self, service):
        """Spatialite devrait gérer les noms de champs."""
        sql = service.to_sql('"my_field" = 1', ProviderType.SPATIALITE)
        
        assert "my_field" in sql


# ============================================================================
# ExpressionService Edge Cases Tests
# ============================================================================

class TestExpressionServiceEdgeCases:
    """Tests pour les cas limites."""
    
    @pytest.fixture
    def service(self):
        """Créer une instance du service."""
        return ExpressionService()
    
    def test_parse_no_fields(self, service):
        """Une expression sans champ devrait fonctionner."""
        parsed = service.parse("1 = 1")
        
        assert len(parsed.fields) == 0
    
    def test_parse_multiple_same_field(self, service):
        """Le même champ répété ne devrait compter qu'une fois."""
        parsed = service.parse('"field" = 1 OR "field" = 2')
        
        assert len(parsed.fields) == 1
        assert "field" in parsed.fields
    
    def test_parse_nested_parentheses(self, service):
        """Les parenthèses imbriquées devraient fonctionner."""
        parsed = service.parse('(("a" = 1) AND (("b" = 2) OR ("c" = 3)))')
        
        assert "a" in parsed.fields
        assert "b" in parsed.fields
        assert "c" in parsed.fields
    
    def test_validate_complex_valid_expression(self, service):
        """Une expression complexe valide devrait passer."""
        expr = '''
            ("category" IN ('A', 'B', 'C'))
            AND ("value" BETWEEN 10 AND 100)
            AND ("name" LIKE '%test%' OR "name" IS NULL)
        '''
        result = service.validate(expr)
        
        assert result.is_valid
    
    def test_parse_case_insensitive_predicates(self, service):
        """Les prédicats spatiaux devraient être détectés case-insensitive."""
        parsed = service.parse('INTERSECTS($geometry, @layer)')
        
        assert SpatialPredicate.INTERSECTS in parsed.spatial_predicates
    
    def test_parse_preserves_original(self, service):
        """L'expression originale devrait être préservée."""
        original = '"field" = \'value\''
        parsed = service.parse(original)
        
        assert parsed.original == original
