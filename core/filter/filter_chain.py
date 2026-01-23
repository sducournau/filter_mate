"""
FilterChain System - Clear and Predictable Filter Combination

Phase 5.0-alpha: Explicit filter management to replace implicit priority logic.

Author: FilterMate Team
Date: 2026-01-21
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Tuple
import re
from qgis.core import QgsVectorLayer

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class FilterType(Enum):
    """
    Types de filtres distincts avec sémantique claire.
    
    Chaque type représente une catégorie de filtre avec un objectif spécifique.
    Les priorités par défaut sont définies dans DEFAULT_PRIORITIES.
    """
    
    # Filtres de base
    SPATIAL_SELECTION = "spatial_selection"     # Filtre spatial EXISTS (zone_pop)
    FIELD_CONDITION = "field_condition"         # Conditions sur champs (status='active')
    FID_LIST = "fid_list"                       # Liste explicite de PKs/FIDs
    
    # Filtres d'exploration utilisateur
    CUSTOM_EXPRESSION = "custom_expression"     # Expression custom pour exploration
    USER_SELECTION = "user_selection"           # Features sélectionnées manuellement
    
    # Filtres spatiaux avancés
    BUFFER_INTERSECT = "buffer_intersect"       # Intersection avec buffer d'une source
    SPATIAL_RELATION = "spatial_relation"       # Relations spatiales (contains, within, etc.)
    
    # Filtres de performance
    BBOX_FILTER = "bbox_filter"                 # Filtre par bounding box (optimisation)
    MATERIALIZED_VIEW = "materialized_view"     # Référence à une MV pré-calculée


# Priorités par défaut pour chaque type de filtre
# Plus la valeur est élevée, plus le filtre est prioritaire
DEFAULT_PRIORITIES = {
    FilterType.MATERIALIZED_VIEW: 100,      # Priorité MAX - optimisation
    FilterType.BBOX_FILTER: 90,             # Filtrage grossier d'abord
    FilterType.SPATIAL_SELECTION: 80,       # Filtre spatial de base (zone_pop)
    FilterType.FID_LIST: 70,                # Liste explicite de PKs
    FilterType.BUFFER_INTERSECT: 60,        # Relations spatiales avec buffer
    FilterType.SPATIAL_RELATION: 60,        # Autres relations spatiales
    FilterType.FIELD_CONDITION: 50,         # Conditions sur champs
    FilterType.USER_SELECTION: 40,          # Sélection utilisateur
    FilterType.CUSTOM_EXPRESSION: 30,       # Expression custom (exploration)
}


class CombinationStrategy(Enum):
    """Stratégies de combinaison des filtres."""
    
    PRIORITY_AND = "priority_and"       # Combine avec AND selon priorité
    PRIORITY_OR = "priority_or"         # Combine avec OR selon priorité
    CUSTOM = "custom"                   # Logique custom définie par règles
    REPLACE = "replace"                 # Le nouveau filtre remplace l'ancien


@dataclass
class Filter:
    """
    Représente un filtre unique avec métadonnées complètes.
    
    Attributes:
        filter_type: Type de filtre (FilterType enum)
        expression: Expression SQL/QGIS du filtre
        layer_name: Nom de la couche source (pour traçabilité)
        priority: Priorité d'application (1-100, plus élevé = priorité)
        combine_operator: Opérateur de combinaison (AND/OR)
        metadata: Métadonnées additionnelles (nom, description, etc.)
        is_temporary: Si True, filtre temporaire (ne persiste pas)
        created_at: Timestamp de création
    """
    filter_type: FilterType
    expression: str
    layer_name: str
    priority: int = None  # Auto-assigned from DEFAULT_PRIORITIES if None
    combine_operator: str = "AND"
    metadata: dict = field(default_factory=dict)
    is_temporary: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Auto-assign priority from defaults if not specified."""
        if self.priority is None:
            self.priority = DEFAULT_PRIORITIES.get(self.filter_type, 50)
    
    def to_sql(self, dialect: str = 'postgresql') -> str:
        """
        Convert filter to SQL for specific dialect.
        
        Args:
            dialect: Target SQL dialect ('postgresql', 'spatialite', 'qgis')
            
        Returns:
            SQL expression compatible with target dialect
        """
        # Currently returns expression as-is.
        # Future: Dialect-specific SQL conversion (Phase 5.0)
        # See: https://github.com/sducournau/filter_mate/issues for roadmap
        return self.expression
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate filter syntax and compatibility.
        
        Returns:
            Tuple (is_valid, error_message)
        """
        if not self.expression or not self.expression.strip():
            return False, "Expression is empty"
        
        if not self.layer_name:
            return False, "Layer name is required"
        
        if self.priority < 1 or self.priority > 100:
            return False, f"Priority must be between 1-100, got {self.priority}"
        
        if self.combine_operator.upper() not in ('AND', 'OR'):
            return False, f"Invalid combine_operator: {self.combine_operator}"
        
        return True, None
    
    def __hash__(self):
        """Make Filter hashable for caching."""
        return hash((self.filter_type, self.expression, self.priority))
    
    def __repr__(self):
        """Readable representation for debugging."""
        expr_preview = self.expression[:50] + "..." if len(self.expression) > 50 else self.expression
        return f"Filter({self.filter_type.value}, priority={self.priority}, expr='{expr_preview}')"


class FilterChain:
    """
    Chaîne de filtres avec règles de combinaison explicites.
    
    Gère l'ordre d'application, la combinaison logique, et la génération
    de l'expression SQL finale.
    
    Example:
        >>> chain = FilterChain(layer)
        >>> chain.add_filter(Filter(FilterType.SPATIAL_SELECTION, "pk IN (...)", "zone_pop"))
        >>> chain.add_filter(Filter(FilterType.CUSTOM_EXPRESSION, "status='active'", "layer"))
        >>> expr = chain.build_expression()
        >>> print(expr)  # "pk IN (...) AND status='active'"
    """
    
    def __init__(
        self, 
        target_layer: QgsVectorLayer,
        combination_strategy: CombinationStrategy = CombinationStrategy.PRIORITY_AND
    ):
        """
        Initialize FilterChain for target layer.
        
        Args:
            target_layer: QGIS layer to apply filters to
            combination_strategy: How to combine filters (default: PRIORITY_AND)
        """
        self.target_layer = target_layer
        self.filters: List[Filter] = []
        self.combination_strategy = combination_strategy
        self._cache: Dict[str, str] = {}
        self._creation_time = datetime.now()
        
    def add_filter(self, filter: Filter, replace_existing: bool = False) -> bool:
        """
        Ajoute un filtre à la chaîne avec validation.
        
        Args:
            filter: Filter object to add
            replace_existing: If True, remove existing filters of same type first
            
        Returns:
            True if filter was added successfully, False otherwise
        """
        # Validation
        is_valid, error_msg = filter.validate()
        if not is_valid:
            logger.warning(f"⚠️ Invalid filter rejected: {error_msg}")
            return False
        
        # Check compatibility with existing filters
        if not self._validate_compatibility(filter):
            logger.warning(f"⚠️ Filter incompatible with existing chain: {filter}")
            return False
        
        # Replace existing filters of same type if requested
        if replace_existing:
            self.remove_filter(filter.filter_type)
        
        # Add filter
        self.filters.append(filter)
        self._invalidate_cache()
        
        logger.info(f"✅ Filter added: {filter.filter_type.value} (priority={filter.priority})")
        return True
    
    def remove_filter(self, filter_type: FilterType) -> int:
        """
        Retire tous les filtres d'un type donné.
        
        Args:
            filter_type: Type of filters to remove
            
        Returns:
            Number of filters removed
        """
        original_count = len(self.filters)
        self.filters = [f for f in self.filters if f.filter_type != filter_type]
        removed_count = original_count - len(self.filters)
        
        if removed_count > 0:
            self._invalidate_cache()
            logger.info(f"🗑️ Removed {removed_count} filter(s) of type {filter_type.value}")
        
        return removed_count
    
    def get_filters_by_type(self, filter_type: FilterType) -> List[Filter]:
        """
        Récupère tous les filtres d'un type donné.
        
        Args:
            filter_type: Type of filters to retrieve
            
        Returns:
            List of matching filters
        """
        return [f for f in self.filters if f.filter_type == filter_type]
    
    def has_filter_type(self, filter_type: FilterType) -> bool:
        """Check if chain contains any filter of given type."""
        return any(f.filter_type == filter_type for f in self.filters)
    
    def clear(self) -> None:
        """Remove all filters from chain."""
        count = len(self.filters)
        self.filters.clear()
        self._invalidate_cache()
        logger.info(f"🗑️ Cleared all {count} filters from chain")
    
    def build_expression(self, dialect: str = 'postgresql') -> str:
        """
        Construit l'expression finale en combinant tous les filtres.
        
        Algorithme:
        1. Trie les filtres par priorité (décroissant)
        2. Convertit chaque filtre en SQL selon le dialecte
        3. Combine avec opérateurs logiques (AND/OR)
        4. Optimise l'expression finale
        
        Args:
            dialect: Target SQL dialect ('postgresql', 'spatialite', 'qgis')
            
        Returns:
            Expression SQL complète prête à l'emploi (vide si aucun filtre)
        """
        if not self.filters:
            return ""
            
        # Cache check
        cache_key = f"{dialect}_{hash(tuple(self.filters))}"
        if cache_key in self._cache:
            logger.debug(f"📦 Using cached expression for {self.target_layer.name()}")
            return self._cache[cache_key]
        
        # Tri par priorité (décroissant)
        sorted_filters = sorted(self.filters, key=lambda f: f.priority, reverse=True)
        
        # Construction de l'expression
        expression_parts = []
        for filter in sorted_filters:
            sql_expr = filter.to_sql(dialect)
            if sql_expr and sql_expr.strip():
                expression_parts.append((filter.combine_operator, sql_expr))
        
        if not expression_parts:
            return ""
        
        # Combinaison avec opérateurs logiques
        final_expression = self._combine_parts(expression_parts)
        
        # Optimisation
        final_expression = self._optimize_expression(final_expression)
        
        # Cache
        self._cache[cache_key] = final_expression
        
        logger.info(f"🔧 Built expression for {self.target_layer.name()}: {len(final_expression)} chars, {len(expression_parts)} filters")
        
        return final_expression
    
    def _combine_parts(self, parts: List[Tuple[str, str]]) -> str:
        """
        Combine filter parts with logical operators.
        
        Args:
            parts: List of (operator, expression) tuples
            
        Returns:
            Combined SQL expression
        """
        if not parts:
            return ""
        
        if len(parts) == 1:
            return parts[0][1]  # Return expression directly
        
        # Strategy: PRIORITY_AND (default)
        if self.combination_strategy == CombinationStrategy.PRIORITY_AND:
            # All filters combined with AND
            expressions = [expr for _, expr in parts]
            return " AND ".join(f"({expr})" for expr in expressions)
        
        # Strategy: PRIORITY_OR
        elif self.combination_strategy == CombinationStrategy.PRIORITY_OR:
            # All filters combined with OR
            expressions = [expr for _, expr in parts]
            return " OR ".join(f"({expr})" for expr in expressions)
        
        # Strategy: CUSTOM (respect each filter's combine_operator)
        elif self.combination_strategy == CombinationStrategy.CUSTOM:
            result = parts[0][1]
            for operator, expr in parts[1:]:
                result = f"({result}) {operator.upper()} ({expr})"
            return result
        
        else:
            # Fallback: AND combination
            expressions = [expr for _, expr in parts]
            return " AND ".join(f"({expr})" for expr in expressions)
    
    def _optimize_expression(self, expression: str) -> str:
        """
        Optimize SQL expression (remove redundant parentheses, etc.).
        
        Args:
            expression: Raw combined expression
            
        Returns:
            Optimized expression
        """
        if not expression:
            return expression
        
        # Remove redundant outer parentheses
        while expression.startswith('(') and expression.endswith(')'):
            # Check if these are matching outer parens
            depth = 0
            is_outer = True
            for i, char in enumerate(expression):
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0 and i < len(expression) - 1:
                        is_outer = False
                        break
            
            if is_outer:
                expression = expression[1:-1].strip()
            else:
                break
        
        # Future optimizations (Phase 5.0):
        # - Merge duplicate conditions
        # - Simplify redundant AND/OR chains  
        # - Extract common subexpressions
        
        return expression
    
    def _validate_compatibility(self, new_filter: Filter) -> bool:
        """
        Validate that new filter is compatible with existing filters.
        
        Args:
            new_filter: Filter to validate
            
        Returns:
            True if compatible, False otherwise
        """
        # Check for conflicting filter types
        # Example: FID_LIST and MATERIALIZED_VIEW shouldn't coexist (one should replace the other)
        
        if new_filter.filter_type == FilterType.MATERIALIZED_VIEW:
            # MV should replace FID_LIST
            if self.has_filter_type(FilterType.FID_LIST):
                logger.info("ℹ️ MATERIALIZED_VIEW will replace existing FID_LIST (optimization)")
        
        # Add more compatibility rules as needed
        
        return True
    
    def _invalidate_cache(self) -> None:
        """Invalidate expression cache after modifications."""
        self._cache.clear()
    
    def to_dict(self) -> dict:
        """
        Sérialise la chaîne pour persistence/debugging.
        
        Returns:
            Dictionary representation of FilterChain
        """
        return {
            'target_layer': self.target_layer.name(),
            'strategy': self.combination_strategy.value,
            'filter_count': len(self.filters),
            'created_at': self._creation_time.isoformat(),
            'filters': [
                {
                    'type': f.filter_type.value,
                    'expression': f.expression,
                    'layer_name': f.layer_name,
                    'priority': f.priority,
                    'operator': f.combine_operator,
                    'metadata': f.metadata,
                    'is_temporary': f.is_temporary,
                    'created_at': f.created_at.isoformat()
                }
                for f in self.filters
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict, target_layer: QgsVectorLayer) -> 'FilterChain':
        """
        Reconstruit FilterChain depuis dictionnaire.
        
        Args:
            data: Dictionary from to_dict()
            target_layer: QGIS layer to apply to
            
        Returns:
            Reconstructed FilterChain
        """
        strategy = CombinationStrategy(data.get('strategy', 'priority_and'))
        chain = cls(target_layer, strategy)
        
        for filter_data in data.get('filters', []):
            filter = Filter(
                filter_type=FilterType(filter_data['type']),
                expression=filter_data['expression'],
                layer_name=filter_data['layer_name'],
                priority=filter_data['priority'],
                combine_operator=filter_data.get('operator', 'AND'),
                metadata=filter_data.get('metadata', {}),
                is_temporary=filter_data.get('is_temporary', False)
            )
            chain.add_filter(filter)
        
        return chain
    
    def __repr__(self) -> str:
        """Représentation lisible pour debugging."""
        if not self.filters:
            return f"FilterChain({self.target_layer.name()}): EMPTY"
        
        filters_repr = '\n  '.join([
            f"[{f.priority:3d}] {f.filter_type.value:20s} | {f.combine_operator:3s} | {f.expression[:60]}..."
            for f in sorted(self.filters, key=lambda x: x.priority, reverse=True)
        ])
        return f"FilterChain({self.target_layer.name()}, {len(self.filters)} filters):\n  {filters_repr}"
    
    def __len__(self) -> int:
        """Return number of filters in chain."""
        return len(self.filters)
    
    def __bool__(self) -> bool:
        """FilterChain is truthy if it contains filters."""
        return len(self.filters) > 0
