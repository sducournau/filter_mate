"""
Expression Service.

Core service for expression parsing, validation, and conversion.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from typing import Optional, List, Set
from dataclasses import dataclass, field
import re

from ..domain.filter_expression import ProviderType, SpatialPredicate


@dataclass
class ValidationResult:
    """
    Result of expression validation.
    
    Attributes:
        is_valid: Whether expression is syntactically valid
        error_message: Error description if invalid
        error_position: Character position of error (if known)
        warnings: List of non-fatal warnings
    """
    is_valid: bool
    error_message: Optional[str] = None
    error_position: Optional[int] = None
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def valid(cls, warnings: Optional[List[str]] = None) -> 'ValidationResult':
        """Create a valid result."""
        return cls(is_valid=True, warnings=warnings or [])

    @classmethod
    def invalid(
        cls, 
        message: str, 
        position: Optional[int] = None
    ) -> 'ValidationResult':
        """Create an invalid result."""
        return cls(
            is_valid=False,
            error_message=message,
            error_position=position
        )

    def __bool__(self) -> bool:
        """Allow using ValidationResult in boolean context."""
        return self.is_valid


@dataclass
class ParsedExpression:
    """
    Parsed expression with extracted components.
    
    Attributes:
        original: Original expression string
        fields: Set of field names referenced
        spatial_predicates: List of spatial predicates used
        has_geometry_reference: Whether $geometry is referenced
        has_layer_reference: Whether layer functions are used
        estimated_complexity: Complexity score (1-10)
        operators: List of operators used (AND, OR, etc.)
    """
    original: str
    fields: Set[str]
    spatial_predicates: List[SpatialPredicate]
    has_geometry_reference: bool
    has_layer_reference: bool
    estimated_complexity: int
    operators: List[str] = field(default_factory=list)

    @property
    def is_spatial(self) -> bool:
        """Check if expression is spatial."""
        return len(self.spatial_predicates) > 0 or self.has_geometry_reference

    @property
    def is_simple(self) -> bool:
        """Check if expression is simple (low complexity)."""
        return self.estimated_complexity <= 2

    @property
    def is_complex(self) -> bool:
        """Check if expression is complex (high complexity)."""
        return self.estimated_complexity >= 5

    @property
    def field_count(self) -> int:
        """Number of fields referenced."""
        return len(self.fields)


class ExpressionService:
    """
    Service for expression parsing and conversion.

    Handles:
    - QGIS expression validation
    - Conversion to PostgreSQL/PostGIS SQL
    - Conversion to Spatialite SQL
    - Spatial predicate detection
    - Field extraction
    - Expression complexity estimation

    Example:
        service = ExpressionService()
        
        # Validate expression
        result = service.validate("\"name\" = 'test'")
        if result.is_valid:
            # Parse for analysis
            parsed = service.parse("\"name\" = 'test'")
            print(f"Fields: {parsed.fields}")
            
            # Convert to SQL
            sql = service.to_sql("intersects($geometry, @g)", ProviderType.POSTGRESQL)
            print(f"SQL: {sql}")
    """

    # Patterns for expression parsing
    FIELD_PATTERN = re.compile(r'"([^"]+)"')
    GEOMETRY_PATTERN = re.compile(r'\$geometry|\$geom|geometry\(\)', re.IGNORECASE)
    LAYER_PATTERN = re.compile(r"@layer|layer_property|get_feature", re.IGNORECASE)
    OPERATOR_PATTERN = re.compile(r'\b(AND|OR|NOT|IN|LIKE|ILIKE|BETWEEN|IS NULL|IS NOT NULL)\b', re.IGNORECASE)

    # Spatial predicates mapping
    SPATIAL_PREDICATES = {
        'intersects': SpatialPredicate.INTERSECTS,
        'contains': SpatialPredicate.CONTAINS,
        'within': SpatialPredicate.WITHIN,
        'crosses': SpatialPredicate.CROSSES,
        'touches': SpatialPredicate.TOUCHES,
        'overlaps': SpatialPredicate.OVERLAPS,
        'disjoint': SpatialPredicate.DISJOINT,
        'equals': SpatialPredicate.EQUALS,
        'dwithin': SpatialPredicate.DWITHIN,
    }

    # QGIS to PostgreSQL/PostGIS function mapping
    POSTGIS_FUNCTIONS = {
        'intersects': 'ST_Intersects',
        'contains': 'ST_Contains',
        'within': 'ST_Within',
        'crosses': 'ST_Crosses',
        'touches': 'ST_Touches',
        'overlaps': 'ST_Overlaps',
        'disjoint': 'ST_Disjoint',
        'equals': 'ST_Equals',
        'buffer': 'ST_Buffer',
        'area': 'ST_Area',
        'length': 'ST_Length',
        'distance': 'ST_Distance',
        'centroid': 'ST_Centroid',
        'convexhull': 'ST_ConvexHull',
        'envelope': 'ST_Envelope',
        'simplify': 'ST_Simplify',
        'union': 'ST_Union',
        'intersection': 'ST_Intersection',
        'difference': 'ST_Difference',
        'symdifference': 'ST_SymDifference',
        'transform': 'ST_Transform',
        'makevalid': 'ST_MakeValid',
        'isvalid': 'ST_IsValid',
        'numpoints': 'ST_NPoints',
        'numgeometries': 'ST_NumGeometries',
        'geometryn': 'ST_GeometryN',
        'startpoint': 'ST_StartPoint',
        'endpoint': 'ST_EndPoint',
        'pointn': 'ST_PointN',
        'exteriorring': 'ST_ExteriorRing',
        'x': 'ST_X',
        'y': 'ST_Y',
    }

    # QGIS to Spatialite function mapping
    SPATIALITE_FUNCTIONS = {
        'intersects': 'Intersects',
        'contains': 'Contains',
        'within': 'Within',
        'crosses': 'Crosses',
        'touches': 'Touches',
        'overlaps': 'Overlaps',
        'disjoint': 'Disjoint',
        'equals': 'Equals',
        'buffer': 'Buffer',
        'area': 'Area',
        'length': 'GLength',  # Note: Different name in Spatialite
        'distance': 'Distance',
        'centroid': 'Centroid',
        'convexhull': 'ConvexHull',
        'envelope': 'Envelope',
        'simplify': 'Simplify',
        'union': 'GUnion',  # Note: Different name in Spatialite
        'intersection': 'Intersection',
        'difference': 'Difference',
        'symdifference': 'SymDifference',
        'transform': 'Transform',
        'makevalid': 'MakeValid',
        'isvalid': 'IsValid',
        'numpoints': 'NumPoints',
        'numgeometries': 'NumGeometries',
        'geometryn': 'GeometryN',
        'startpoint': 'StartPoint',
        'endpoint': 'EndPoint',
        'pointn': 'PointN',
        'exteriorring': 'ExteriorRing',
        'x': 'X',
        'y': 'Y',
    }

    def validate(self, expression: str) -> ValidationResult:
        """
        Validate expression syntax.

        Checks for:
        - Empty expression
        - Balanced parentheses
        - Balanced quotes
        - Common syntax issues

        Args:
            expression: QGIS expression string

        Returns:
            ValidationResult with validity and any errors/warnings
        """
        if not expression or not expression.strip():
            return ValidationResult.invalid("Expression cannot be empty")

        warnings: List[str] = []

        # Check for balanced parentheses
        paren_count = 0
        for i, char in enumerate(expression):
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                if paren_count < 0:
                    return ValidationResult.invalid(
                        "Unbalanced parentheses: unexpected ')'",
                        position=i
                    )
        if paren_count != 0:
            return ValidationResult.invalid("Unbalanced parentheses: missing ')'")

        # Check for balanced double quotes
        in_double_quote = False
        for i, char in enumerate(expression):
            if char == '"':
                in_double_quote = not in_double_quote
        if in_double_quote:
            return ValidationResult.invalid("Unbalanced double quotes")

        # Check for balanced single quotes (more complex due to escaping)
        single_quote_count = 0
        i = 0
        while i < len(expression):
            if expression[i] == "'":
                # Check for escaped quote
                if i + 1 < len(expression) and expression[i + 1] == "'":
                    i += 2  # Skip escaped quote
                    continue
                single_quote_count += 1
            i += 1
        if single_quote_count % 2 != 0:
            return ValidationResult.invalid("Unbalanced single quotes")

        # Check for common issues (warnings, not errors)
        if '==' in expression:
            warnings.append("Use '=' instead of '==' for equality")

        if '!=' in expression:
            warnings.append("Use '<>' instead of '!=' for inequality")

        if '&&' in expression:
            warnings.append("Use 'AND' instead of '&&'")

        if '||' in expression and 'concat' not in expression.lower():
            warnings.append("Use 'OR' instead of '||' (unless string concatenation)")

        # Check for potential SQL injection (basic check)
        dangerous_patterns = [';', '--', '/*', '*/']
        for pattern in dangerous_patterns:
            if pattern in expression:
                warnings.append(f"Potentially dangerous pattern '{pattern}' detected")

        return ValidationResult.valid(warnings)

    def parse(self, expression: str) -> ParsedExpression:
        """
        Parse expression and extract components.

        Extracts:
        - Field references
        - Spatial predicates
        - Geometry references
        - Layer references
        - Operators
        - Complexity estimate

        Args:
            expression: QGIS expression string

        Returns:
            ParsedExpression with extracted components
        """
        # Extract fields (quoted identifiers)
        fields = set(self.FIELD_PATTERN.findall(expression))

        # Detect spatial predicates
        spatial_predicates: List[SpatialPredicate] = []
        expr_lower = expression.lower()
        for name, predicate in self.SPATIAL_PREDICATES.items():
            if name in expr_lower:
                spatial_predicates.append(predicate)

        # Check for geometry and layer references
        has_geometry = bool(self.GEOMETRY_PATTERN.search(expression))
        has_layer = bool(self.LAYER_PATTERN.search(expression))

        # Extract operators
        operators = self.OPERATOR_PATTERN.findall(expression.upper())

        # Estimate complexity based on various factors
        complexity = self._estimate_complexity(
            expression=expression,
            fields=fields,
            spatial_predicates=spatial_predicates,
            has_geometry=has_geometry,
            operators=operators
        )

        return ParsedExpression(
            original=expression,
            fields=fields,
            spatial_predicates=spatial_predicates,
            has_geometry_reference=has_geometry,
            has_layer_reference=has_layer,
            estimated_complexity=complexity,
            operators=operators
        )

    def _estimate_complexity(
        self,
        expression: str,
        fields: Set[str],
        spatial_predicates: List[SpatialPredicate],
        has_geometry: bool,
        operators: List[str]
    ) -> int:
        """
        Estimate expression complexity on a scale of 1-10.
        
        Higher complexity suggests:
        - Longer execution time
        - May benefit from materialized views
        - May need more memory for caching
        """
        complexity = 1

        # Factor in operators
        and_or_count = sum(1 for op in operators if op in ('AND', 'OR'))
        complexity += min(and_or_count, 3)  # Cap at +3

        # Factor in spatial predicates (expensive)
        complexity += len(spatial_predicates) * 2

        # Factor in geometry reference
        if has_geometry:
            complexity += 1

        # Factor in field count
        if len(fields) > 3:
            complexity += 1

        # Factor in expression length
        if len(expression) > 200:
            complexity += 1

        # Cap at 10
        return min(complexity, 10)

    def to_sql(
        self,
        expression: str,
        provider: ProviderType,
        geometry_column: str = "geometry"
    ) -> str:
        """
        Convert QGIS expression to provider-specific SQL.

        Args:
            expression: QGIS expression
            provider: Target provider type
            geometry_column: Name of geometry column in table

        Returns:
            SQL expression string for the target provider
        """
        if provider == ProviderType.POSTGRESQL:
            return self._to_postgis(expression, geometry_column)
        elif provider == ProviderType.SPATIALITE:
            return self._to_spatialite(expression, geometry_column)
        else:
            # OGR and Memory use QGIS expressions directly
            return expression

    def _to_postgis(self, expression: str, geometry_column: str) -> str:
        """
        Convert to PostGIS SQL.
        
        Handles:
        - $geometry -> column reference
        - QGIS functions -> PostGIS equivalents
        - IF -> CASE WHEN conversion
        - Type casting for numeric/text operations
        - SQL keyword normalization
        
        Consolidated from legacy filter_task.py qgis_expression_to_postgis()
        """
        sql = expression
        
        if not sql:
            return sql

        # 1. Replace $geometry with column reference (including $area, $length, etc.)
        spatial_conversions = {
            r'\$area': f'ST_Area("{geometry_column}")',
            r'\$length': f'ST_Length("{geometry_column}")',
            r'\$perimeter': f'ST_Perimeter("{geometry_column}")',
            r'\$x': f'ST_X("{geometry_column}")',
            r'\$y': f'ST_Y("{geometry_column}")',
            r'\$geometry|\$geom': f'"{geometry_column}"',
        }
        for pattern, replacement in spatial_conversions.items():
            sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)

        # 2. Replace QGIS functions with PostGIS equivalents
        for qgis_func, pg_func in self.POSTGIS_FUNCTIONS.items():
            pattern = rf'\b{qgis_func}\s*\('
            sql = re.sub(pattern, f'{pg_func}(', sql, flags=re.IGNORECASE)

        # 3. Convert QGIS IF statements to SQL CASE WHEN
        # Pattern: if(condition, value_true, value_false) -> CASE WHEN condition THEN value_true ELSE value_false END
        sql = re.sub(
            r'\bif\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)',
            r'CASE WHEN \1 THEN \2 ELSE \3 END',
            sql,
            flags=re.IGNORECASE
        )

        # 4. Normalize SQL keywords
        sql = re.sub(r'\bcase\b', ' CASE ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bwhen\b', ' WHEN ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bthen\b', ' THEN ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\belse\b', ' ELSE ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bend\b', ' END ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bilike\b', ' ILIKE ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\blike\b', ' LIKE ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bnot\b', ' NOT ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bis\b', ' IS ', sql, flags=re.IGNORECASE)

        # 5. Add type casting for numeric operations (comparison operators)
        # "field" > value -> "field"::numeric > value
        sql = re.sub(r'"(\w+)"\s*>', r'"\1"::numeric >', sql)
        sql = re.sub(r'"(\w+)"\s*<', r'"\1"::numeric <', sql)
        sql = re.sub(r'"(\w+)"\s*\+', r'"\1"::numeric +', sql)
        sql = re.sub(r'"(\w+)"\s*-', r'"\1"::numeric -', sql)

        # 6. Add type casting for text operations (LIKE/ILIKE)
        sql = re.sub(r'"(\w+)"\s+(NOT\s+)?ILIKE', r'"\1"::text \2ILIKE', sql)
        sql = re.sub(r'"(\w+)"\s+(NOT\s+)?LIKE', r'"\1"::text \2LIKE', sql)

        # 7. Handle NULL comparisons
        sql = re.sub(r'\bIS\s+NULL\b', 'IS NULL', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bIS\s+NOT\s+NULL\b', 'IS NOT NULL', sql, flags=re.IGNORECASE)

        # 8. Handle boolean literals
        sql = re.sub(r'\bTRUE\b', 'TRUE', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bFALSE\b', 'FALSE', sql, flags=re.IGNORECASE)
        
        # 9. Clean up extra spaces
        sql = re.sub(r'\s+', ' ', sql).strip()

        return sql

    def _to_spatialite(self, expression: str, geometry_column: str) -> str:
        """
        Convert to Spatialite SQL.
        
        Handles:
        - $geometry -> column reference
        - QGIS functions -> Spatialite equivalents
        - PostgreSQL :: type casting -> CAST() function
        - ILIKE -> LOWER(field) LIKE LOWER(pattern)
        - SQL keyword normalization
        
        Consolidated from legacy filter_task.py qgis_expression_to_spatialite()
        
        Note:
            Spatialite spatial functions are ~90% compatible with PostGIS.
            Main differences: type casting syntax, no ILIKE, some function names.
        """
        sql = expression
        
        if not sql:
            return sql

        # 1. Replace $geometry with column reference
        sql = re.sub(
            r'\$geometry|\$geom',
            f'"{geometry_column}"',
            sql,
            flags=re.IGNORECASE
        )

        # 2. Replace QGIS functions with Spatialite equivalents
        for qgis_func, sl_func in self.SPATIALITE_FUNCTIONS.items():
            pattern = rf'\b{qgis_func}\s*\('
            sql = re.sub(pattern, f'{sl_func}(', sql, flags=re.IGNORECASE)

        # 3. Normalize CASE expressions
        sql = re.sub(r'\bcase\b', ' CASE ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bwhen\b', ' WHEN ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bthen\b', ' THEN ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\belse\b', ' ELSE ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bend\b', ' END ', sql, flags=re.IGNORECASE)
        
        # 4. Handle ILIKE - Spatialite doesn't have ILIKE, use LOWER() with LIKE
        # IMPORTANT: Process ILIKE before LIKE to avoid double-replacement
        # "field" ILIKE 'pattern' -> LOWER("field") LIKE LOWER('pattern')
        sql = re.sub(
            r'"(\w+)"\s+ILIKE\s+\'([^\']+)\'',
            r'LOWER("\1") LIKE LOWER(\'\2\')',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'"(\w+)"\s+NOT\s+ILIKE\s+\'([^\']+)\'',
            r'LOWER("\1") NOT LIKE LOWER(\'\2\')',
            sql,
            flags=re.IGNORECASE
        )
        
        # 5. Normalize LIKE and NOT
        sql = re.sub(r'\bnot\b', ' NOT ', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\blike\b', ' LIKE ', sql, flags=re.IGNORECASE)

        # 6. Convert PostgreSQL :: type casting to Spatialite CAST() function
        # "field"::numeric -> CAST("field" AS REAL)
        # "field"::integer -> CAST("field" AS INTEGER)
        # "field"::text -> CAST("field" AS TEXT)
        sql = re.sub(r'"(\w+)"::numeric', r'CAST("\1" AS REAL)', sql)
        sql = re.sub(r'"(\w+)"::integer', r'CAST("\1" AS INTEGER)', sql)
        sql = re.sub(r'"(\w+)"::text', r'CAST("\1" AS TEXT)', sql)
        sql = re.sub(r'"(\w+)"::double', r'CAST("\1" AS REAL)', sql)
        sql = re.sub(r'"(\w+)"::float', r'CAST("\1" AS REAL)', sql)

        # 7. Handle NULL comparisons
        sql = re.sub(r'\bIS\s+NULL\b', 'IS NULL', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bIS\s+NOT\s+NULL\b', 'IS NOT NULL', sql, flags=re.IGNORECASE)

        # 8. Spatialite boolean handling (uses 0/1 instead of TRUE/FALSE)
        sql = re.sub(r'\bTRUE\b', '1', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bFALSE\b', '0', sql, flags=re.IGNORECASE)
        
        # 9. Clean up extra spaces
        sql = re.sub(r'\s+', ' ', sql).strip()

        return sql

    def extract_fields(self, expression: str) -> Set[str]:
        """
        Extract field names from expression.
        
        Args:
            expression: QGIS expression string
            
        Returns:
            Set of field names
        """
        return set(self.FIELD_PATTERN.findall(expression))

    def is_spatial(self, expression: str) -> bool:
        """
        Check if expression contains spatial predicates or geometry references.
        
        Args:
            expression: QGIS expression string
            
        Returns:
            True if expression is spatial
        """
        expr_lower = expression.lower()
        has_predicate = any(pred in expr_lower for pred in self.SPATIAL_PREDICATES.keys())
        has_geometry = bool(self.GEOMETRY_PATTERN.search(expression))
        return has_predicate or has_geometry

    def get_spatial_predicates(self, expression: str) -> List[SpatialPredicate]:
        """
        Get list of spatial predicates in expression.
        
        Args:
            expression: QGIS expression string
            
        Returns:
            List of SpatialPredicate enums found
        """
        predicates: List[SpatialPredicate] = []
        expr_lower = expression.lower()
        for name, predicate in self.SPATIAL_PREDICATES.items():
            if name in expr_lower:
                predicates.append(predicate)
        return predicates

    def add_buffer(
        self,
        expression: str,
        buffer_value: float,
        provider: ProviderType,
        buffer_segments: int = 8
    ) -> str:
        """
        Wrap geometry references in buffer function.

        Args:
            expression: Original expression
            buffer_value: Buffer distance in layer units
            provider: Target provider type
            buffer_segments: Number of segments for buffer curves

        Returns:
            Expression with buffered geometry references
        """
        if provider == ProviderType.POSTGRESQL:
            buffer_fn = "ST_Buffer"
        elif provider == ProviderType.SPATIALITE:
            buffer_fn = "Buffer"
        else:
            buffer_fn = "buffer"

        # Wrap $geometry references in buffer
        pattern = r'(\$geometry|\$geom)'
        
        if provider == ProviderType.POSTGRESQL:
            # PostGIS uses ST_Buffer(geom, distance, segments)
            replacement = f'{buffer_fn}(\\1, {buffer_value})'
        elif provider == ProviderType.SPATIALITE:
            # Spatialite uses Buffer(geom, distance)
            replacement = f'{buffer_fn}(\\1, {buffer_value})'
        else:
            # QGIS expression: buffer($geometry, distance, segments)
            replacement = f'{buffer_fn}(\\1, {buffer_value}, {buffer_segments})'

        return re.sub(pattern, replacement, expression, flags=re.IGNORECASE)

    def normalize(self, expression: str) -> str:
        """
        Normalize expression for consistent comparison.
        
        - Strips whitespace
        - Normalizes operator case
        - Removes extra spaces
        
        Args:
            expression: QGIS expression string
            
        Returns:
            Normalized expression
        """
        result = expression.strip()
        
        # Normalize whitespace
        result = re.sub(r'\s+', ' ', result)
        
        # Normalize operators to uppercase
        for op in ['AND', 'OR', 'NOT', 'IN', 'LIKE', 'ILIKE', 'BETWEEN', 'IS', 'NULL']:
            result = re.sub(rf'\b{op}\b', op, result, flags=re.IGNORECASE)
        
        return result

    def combine_expressions(
        self,
        expressions: List[str],
        operator: str = 'AND'
    ) -> str:
        """
        Combine multiple expressions with an operator.
        
        Args:
            expressions: List of expression strings
            operator: Operator to use ('AND' or 'OR')
            
        Returns:
            Combined expression string
        """
        if not expressions:
            return ""
        if len(expressions) == 1:
            return expressions[0]
        
        # Wrap each expression in parentheses for safety
        wrapped = [f"({expr})" for expr in expressions if expr.strip()]
        return f" {operator.upper()} ".join(wrapped)

    def negate(self, expression: str) -> str:
        """
        Negate an expression.
        
        Args:
            expression: Expression to negate
            
        Returns:
            Negated expression
        """
        return f"NOT ({expression})"


def sanitize_subset_string(subset_string: str, logger=None) -> str:
    """
    Remove non-boolean display expressions and fix type casting issues in subset string.
    
    v4.7 E6-S2: Extracted from filter_task.py for reusability.
    
    Display expressions like 'coalesce("field",'<NULL>')' or CASE expressions that
    return true/false are valid QGIS expressions but cause issues in SQL WHERE clauses.
    This function removes such expressions and fixes common type casting issues.
    
    Args:
        subset_string: The original subset string
        logger: Optional logger for diagnostics (if None, prints to stdout)
        
    Returns:
        Sanitized subset string with non-boolean expressions removed
    """
    if not subset_string:
        return subset_string
    
    def log_info(msg):
        if logger:
            logger.info(msg)
    
    sanitized = subset_string
    
    # ========================================================================
    # PHASE 0: Normalize French SQL operators to English
    # ========================================================================
    french_operators = [
        (r'\)\s+ET\s+\(', ') AND ('),      # ) ET ( -> ) AND (
        (r'\)\s+OU\s+\(', ') OR ('),       # ) OU ( -> ) OR (
        (r'\s+ET\s+', ' AND '),            # ... ET ... -> ... AND ...
        (r'\s+OU\s+', ' OR '),             # ... OU ... -> ... OR ...
        (r'\s+ET\s+NON\s+', ' AND NOT '),  # ET NON -> AND NOT
        (r'\s+NON\s+', ' NOT '),           # NON ... -> NOT ...
    ]
    
    for pattern, replacement in french_operators:
        if re.search(pattern, sanitized, re.IGNORECASE):
            log_info(f"FilterMate: Normalizing French operator '{pattern}' to '{replacement}'")
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    # ========================================================================
    # PHASE 1: Remove non-boolean display expressions
    # ========================================================================
    
    coalesce_patterns = [
        r'(?:^|\s+)AND\s+\(coalesce\("[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
        r'(?:^|\s+)OR\s+\(coalesce\("[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
        r'(?:^|\s+)AND\s+\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)',
        r'(?:^|\s+)OR\s+\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)',
        r'(?:^|\s+)AND\s+\(coalesce\([^)]+\)\)',
        r'(?:^|\s+)OR\s+\(coalesce\([^)]+\)\)',
        r'(?:^|\s+)AND\s+\(coalesce\("[^"]+"\s*\.\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
        r'(?:^|\s+)OR\s+\(coalesce\("[^"]+"\s*\.\s*"[^"]+"\s*,\s*\'[^\']*\'\s*\)\)',
    ]
    
    for pattern in coalesce_patterns:
        match = re.search(pattern, sanitized, re.IGNORECASE)
        if match:
            log_info(f"FilterMate: Removing invalid coalesce expression: '{match.group()[:60]}...'")
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # SELECT CASE patterns
    select_case_pattern = r'\s*AND\s+\(\s*SELECT\s+CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+\s*(?:ELSE\s+.+?)?\s*end\s*\)'
    
    match = re.search(select_case_pattern, sanitized, re.IGNORECASE | re.DOTALL)
    if match:
        log_info(f"FilterMate: Removing SELECT CASE style expression: '{match.group()[:80]}...'")
        sanitized = re.sub(select_case_pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    case_patterns = [
        r'\s*AND\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+(?:ELSE\s+.+?)?\s*END\s*\)+',
        r'\s*OR\s+\(\s*CASE\s+(?:WHEN\s+.+?THEN\s+(?:true|false)\s*)+(?:ELSE\s+.+?)?\s*END\s*\)+',
        r'\s*AND\s+\(\s*SELECT\s+CASE\s+.+?\s+END\s*\)+',
        r'\s*OR\s+\(\s*SELECT\s+CASE\s+.+?\s+END\s*\)+',
    ]
    
    for pattern in case_patterns:
        match = re.search(pattern, sanitized, re.IGNORECASE | re.DOTALL)
        if match:
            matched_text = match.group()
            if re.search(r'\bTHEN\s+(true|false)\b', matched_text, re.IGNORECASE):
                log_info(f"FilterMate: Removing invalid CASE/style expression: '{matched_text[:60]}...'")
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove standalone coalesce expressions at start
    standalone_coalesce = r'^\s*\(coalesce\([^)]*(?:\([^)]*\)[^)]*)*\)\)\s*(?:AND|OR)?'
    if re.match(standalone_coalesce, sanitized, re.IGNORECASE):
        match = re.match(standalone_coalesce, sanitized, re.IGNORECASE)
        log_info(f"FilterMate: Removing standalone coalesce: '{match.group()[:60]}...'")
        sanitized = re.sub(standalone_coalesce, '', sanitized, flags=re.IGNORECASE)
    
    # ========================================================================
    # PHASE 2: Fix unbalanced parentheses
    # ========================================================================
    
    open_count = sanitized.count('(')
    close_count = sanitized.count(')')
    
    if close_count > open_count:
        excess = close_count - open_count
        trailing_parens = re.search(r'\)+\s*$', sanitized)
        if trailing_parens:
            parens_at_end = len(trailing_parens.group().strip())
            if parens_at_end >= excess:
                sanitized = re.sub(r'\){' + str(excess) + r'}\s*$', '', sanitized)
                log_info(f"FilterMate: Removed {excess} excess closing parentheses")
    
    # ========================================================================
    # PHASE 3: Clean up whitespace and orphaned operators
    # ========================================================================
    
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    sanitized = re.sub(r'\s+(AND|OR)\s*$', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'^\s*(AND|OR)\s+', '', sanitized, flags=re.IGNORECASE)
    
    # Remove duplicate AND/OR operators
    sanitized = re.sub(r'\s+AND\s+AND\s+', ' AND ', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\s+OR\s+OR\s+', ' OR ', sanitized, flags=re.IGNORECASE)
    
    if sanitized != subset_string:
        log_info(f"FilterMate: Subset sanitized from '{subset_string[:80]}...' to '{sanitized[:80]}...'")
    
    return sanitized
