# Filter Chain System - Architecture Design

**Version:** 5.0-alpha  
**Date:** 2026-01-21  
**Status:** Conception initiale

## 🎯 Objectif

Créer un système de combinaison de filtres **explicite, prévisible et maintenable** pour remplacer la logique actuelle implicite qui cause des conflits entre différents types de filtres.

## 📋 Problèmes Actuels

### Symptômes
1. **Confusion des filtres** : Les filtres s'écrasent mutuellement au lieu de se combiner
2. **Logique implicite** : Difficile de prédire quel filtre sera appliqué dans un contexte donné
3. **Priorités floues** : `task_features` vs `source_subset` vs `buffer_expression` - quelle priorité ?
4. **Pas de traçabilité** : Impossible de savoir quels filtres sont actifs et dans quel ordre

### Exemples concrets
```python
# Scenario 1: Couche source (ducts) pré-filtrée par zone_pop
source_layer.subsetString() = "pk IN (SELECT pk FROM zone_pop WHERE ...)"  # Filtre spatial

# Scenario 2: L'utilisateur sélectionne des features spécifiques pour explorer
task_features = [feature1, feature2, feature3]  # Custom expression champs

# Scenario 3: Buffer expression pour filtrer les couches distantes
buffer_expression = "ST_Buffer(geom, 50)"  # Expression spatiale avec buffer

# PROBLEME: Comment combiner ces 3 filtres ? Lequel prime ?
# - Pour ducts : zone_pop + custom expression (PAS de 2nd filtre spatial)
# - Pour structures : zone_pop + buffer intersect avec ducts
```

## 🏗️ Architecture Proposée

### Types de Filtres (FilterType)

```python
class FilterType(Enum):
    """Types de filtres distincts avec sémantique claire."""
    
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
```

### Classe Filter

```python
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
    priority: int = 50
    combine_operator: str = "AND"
    metadata: dict = field(default_factory=dict)
    is_temporary: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_sql(self, dialect: str = 'postgresql') -> str:
        """Convert filter to SQL for specific dialect."""
        # Conversion selon le dialecte (PostgreSQL, Spatialite, QGIS)
        pass
    
    def validate(self) -> bool:
        """Validate filter syntax and compatibility."""
        pass
```

### Classe FilterChain

```python
class FilterChain:
    """
    Chaîne de filtres avec règles de combinaison explicites.
    
    Gère l'ordre d'application, la combinaison logique, et la génération
    de l'expression SQL finale.
    """
    
    def __init__(self, target_layer: QgsVectorLayer):
        self.target_layer = target_layer
        self.filters: List[Filter] = []
        self.combination_strategy = CombinationStrategy.PRIORITY_AND
        self._cache = {}
        
    def add_filter(self, filter: Filter) -> None:
        """Ajoute un filtre à la chaîne avec validation."""
        if self._validate_compatibility(filter):
            self.filters.append(filter)
            self._invalidate_cache()
            
    def remove_filter(self, filter_type: FilterType) -> None:
        """Retire tous les filtres d'un type donné."""
        self.filters = [f for f in self.filters if f.filter_type != filter_type]
        self._invalidate_cache()
        
    def get_filters_by_type(self, filter_type: FilterType) -> List[Filter]:
        """Récupère tous les filtres d'un type donné."""
        return [f for f in self.filters if f.filter_type == filter_type]
    
    def build_expression(self, dialect: str = 'postgresql') -> str:
        """
        Construit l'expression finale en combinant tous les filtres.
        
        Algorithme:
        1. Trie les filtres par priorité (décroissant)
        2. Groupe par combine_operator
        3. Génère sous-expressions par groupe
        4. Combine avec opérateurs logiques
        5. Optimise l'expression finale
        
        Returns:
            Expression SQL complète prête à l'emploi
        """
        if not self.filters:
            return ""
            
        # Cache check
        cache_key = f"{dialect}_{hash(tuple(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        # Tri par priorité
        sorted_filters = sorted(self.filters, key=lambda f: f.priority, reverse=True)
        
        # Construction de l'expression
        expression_parts = []
        for filter in sorted_filters:
            sql_expr = filter.to_sql(dialect)
            if sql_expr:
                expression_parts.append((filter.combine_operator, sql_expr))
        
        # Combinaison avec opérateurs logiques
        final_expression = self._combine_parts(expression_parts)
        
        # Optimisation
        final_expression = self._optimize_expression(final_expression)
        
        # Cache
        self._cache[cache_key] = final_expression
        
        return final_expression
    
    def to_dict(self) -> dict:
        """Sérialise la chaîne pour persistence/debugging."""
        return {
            'target_layer': self.target_layer.name(),
            'strategy': self.combination_strategy.name,
            'filters': [
                {
                    'type': f.filter_type.value,
                    'expression': f.expression,
                    'priority': f.priority,
                    'operator': f.combine_operator,
                    'metadata': f.metadata,
                    'created_at': f.created_at.isoformat()
                }
                for f in self.filters
            ]
        }
    
    def __repr__(self) -> str:
        """Représentation lisible pour debugging."""
        filters_repr = '\n  '.join([
            f"[{f.priority}] {f.filter_type.value}: {f.expression[:50]}..."
            for f in sorted(self.filters, key=lambda x: x.priority, reverse=True)
        ])
        return f"FilterChain({self.target_layer.name()}):\n  {filters_repr}"
```

### Stratégies de Combinaison

```python
class CombinationStrategy(Enum):
    """Stratégies de combinaison des filtres."""
    
    PRIORITY_AND = "priority_and"       # Combine avec AND selon priorité
    PRIORITY_OR = "priority_or"         # Combine avec OR selon priorité
    CUSTOM = "custom"                   # Logique custom définie par règles
    REPLACE = "replace"                 # Le nouveau filtre remplace l'ancien
```

### Règles de Priorité par Défaut

```python
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
```

## 🔧 Cas d'Usage

### Cas 1: Couche Source avec Zone Pop + Custom Expression

```python
# Couche ducts pré-filtrée par zone_pop
chain = FilterChain(ducts_layer)

# Filtre spatial existant (zone_pop)
spatial_filter = Filter(
    filter_type=FilterType.SPATIAL_SELECTION,
    expression="pk IN (SELECT pk FROM zone_pop WHERE uuid IN (...))",
    layer_name="zone_pop",
    priority=80,  # Priorité élevée
    combine_operator="AND",
    metadata={'source': 'zone_pop', 'count': 5}
)
chain.add_filter(spatial_filter)

# Custom expression pour exploration (champs simples)
custom_filter = Filter(
    filter_type=FilterType.CUSTOM_EXPRESSION,
    expression="status = 'active'",
    layer_name="ducts",
    priority=30,  # Priorité basse - exploration
    combine_operator="AND",
    metadata={'user_defined': True}
)
chain.add_filter(custom_filter)

# Expression finale combinée
final_expr = chain.build_expression()
# Résultat: "pk IN (SELECT pk FROM zone_pop WHERE ...) AND status = 'active'"
```

### Cas 2: Couche Distante avec Buffer Intersect

```python
# Couche structures filtrée par ducts (avec buffer)
chain = FilterChain(structures_layer)

# Filtre spatial hérité (zone_pop)
spatial_filter = Filter(
    filter_type=FilterType.SPATIAL_SELECTION,
    expression="pk IN (SELECT pk FROM zone_pop WHERE uuid IN (...))",
    layer_name="zone_pop",
    priority=80,
    combine_operator="AND"
)
chain.add_filter(spatial_filter)

# Buffer intersect avec ducts
buffer_filter = Filter(
    filter_type=FilterType.BUFFER_INTERSECT,
    expression="""EXISTS (
        SELECT 1 FROM ducts AS __source
        WHERE ST_Intersects(structures.geom, ST_Buffer(__source.geom, 50))
        AND __source.pk IN (SELECT pk FROM zone_pop WHERE ...)
    )""",
    layer_name="ducts",
    priority=60,
    combine_operator="AND",
    metadata={'buffer_distance': 50, 'source_layer': 'ducts'}
)
chain.add_filter(buffer_filter)

# Expression finale
final_expr = chain.build_expression()
# Résultat: Combine zone_pop + buffer intersect avec ducts pré-filtré
```

### Cas 3: Optimisation avec Materialized View

```python
# Si selection > 100 features, créer une MV
if len(selected_fids) > 100:
    mv_name = f"mv_selection_{layer.name()}_{timestamp}"
    
    # Créer la MV
    create_materialized_view(mv_name, fid_list)
    
    # Remplacer le filtre FID par une référence MV
    mv_filter = Filter(
        filter_type=FilterType.MATERIALIZED_VIEW,
        expression=f"pk IN (SELECT pk FROM {mv_name})",
        layer_name=layer.name(),
        priority=100,  # Priorité MAX
        combine_operator="AND",
        metadata={'mv_name': mv_name, 'fid_count': len(selected_fids)},
        is_temporary=True  # MV sera nettoyée
    )
    
    chain.add_filter(mv_filter)
```

## 📊 Comparaison Avant/Après

### AVANT (Logique Implicite)

```python
# ❌ Code actuel - logique confuse
if has_buffer_expression and source_subset:
    source_filter = optimized_source_subset
elif use_task_features:
    source_filter = from_task_features
elif source_subset and not skip_source_subset:
    source_filter = source_subset
# Quelle priorité ? Quelle combinaison ? Pas clair !
```

### APRÈS (FilterChain Explicite)

```python
# ✅ Nouveau système - intentions claires
chain = FilterChain(target_layer)

# Ajout explicite de chaque filtre avec priorité
chain.add_filter(spatial_selection_filter)   # Priorité 80
chain.add_filter(buffer_intersect_filter)    # Priorité 60
chain.add_filter(custom_expression_filter)   # Priorité 30

# Expression finale prévisible et traçable
final_expr = chain.build_expression()

# Debugging facile
print(chain)  # Affiche tous les filtres avec priorités
print(chain.to_dict())  # JSON complet pour logs
```

## 🔄 Migration Path

### Phase 1: Création des classes de base
- [ ] Créer `FilterType` enum
- [ ] Créer `Filter` dataclass
- [ ] Créer `FilterChain` class
- [ ] Tests unitaires pour chaque classe

### Phase 2: Intégration dans ExpressionBuilder
- [ ] Adapter `_prepare_source_filter()` pour utiliser FilterChain
- [ ] Migrer les conditions if/elif vers filters explicites
- [ ] Conserver backward compatibility temporaire

### Phase 3: Migration FilterEngineTask
- [ ] Remplacer subset string logic par FilterChain
- [ ] Adapter buffer MV creation pour utiliser FilterChain
- [ ] Tests d'intégration complets

### Phase 4: UI et Persistence
- [ ] Afficher FilterChain actif dans UI
- [ ] Persistence des chaînes de filtres (favoris)
- [ ] Undo/Redo support pour modifications de chaîne

## 🎯 Avantages

### Clarté
- Chaque filtre a un type explicite
- Priorités définies et visibles
- Opérateurs de combinaison clairs (AND/OR)

### Maintenabilité
- Logique centralisée dans FilterChain
- Debugging facile avec `to_dict()` et `__repr__()`
- Tests unitaires simples (un filtre = un test)

### Extensibilité
- Ajout de nouveaux types de filtres trivial
- Stratégies de combinaison personnalisables
- Support multi-backend (PostgreSQL, Spatialite, OGR)

### Performance
- Cache des expressions construites
- Détection automatique des optimisations MV
- Réutilisation des sous-requêtes EXISTS

## 📝 Notes d'Implémentation

### Thread Safety
- FilterChain doit être immutable après construction
- Créer une nouvelle chaîne pour modifications (pattern builder)
- Signal Qt pour updates UI

### Validation
- Valider la syntaxe de chaque filtre à l'ajout
- Détecter les conflits de filtres (FID_LIST + USER_SELECTION)
- Avertir l'utilisateur en cas de combinaison suspecte

### Logging
- Logger chaque ajout/suppression de filtre
- Tracer la construction de l'expression finale
- Métriques de performance (temps de construction, taille expression)

## 🔗 Liens

- Architecture hexagonale: `docs/ARCHITECTURE.md`
- Expression Builder: `core/filter/expression_builder.py`
- Filter Task: `core/tasks/filter_task.py`
- Tests: `tests/core/filter/test_filter_chain.py` (à créer)
