# Phase E13 Step 4: SubsetStringBuilder Extraction

**Date:** 14 janvier 2026  
**Status:** ✅ Complété  
**Author:** FilterMate Team

## Objectif

Extraire la logique de construction et gestion des subset strings (clauses WHERE) de `FilterEngineTask` vers un nouveau builder dédié.

## Contexte

Les subset strings sont des expressions SQL appliquées aux couches QGIS pour le filtrage. Leur gestion était dispersée dans `FilterEngineTask` avec ~150 LOC.

## Travail réalisé

### 1. Nouveau module créé

**Fichier:** [core/tasks/builders/subset_string_builder.py](../core/tasks/builders/subset_string_builder.py)

**Classes:**
- `SubsetStringBuilder` - Classe principale (~320 LOC)
- `SubsetRequest` - Dataclass pour les requêtes en attente
- `CombineResult` - Résultat de la combinaison d'expressions

### 2. Fonctionnalités extraites

| Méthode extraite | De FilterEngineTask | Vers SubsetStringBuilder |
|------------------|---------------------|-------------------------|
| `_queue_subset_string()` | ligne 797 | `queue_subset_request()` |
| `_build_combined_filter_expression()` | lignes 2271-2348 | `combine_expressions()` |
| Logic de sanitization | inline | `sanitize()` |
| Validation SQL | inline | `validate()` |

### 3. Nouvelles méthodes ajoutées

```python
# SubsetStringBuilder
def queue_subset_request(layer, expression) -> bool
def get_pending_requests() -> List[Tuple[layer, expr]]
def clear_pending_requests()
def get_pending_count() -> int
def combine_expressions(new, old, operator, layer_props) -> CombineResult
def sanitize(subset_string) -> str
def validate(expression, layer) -> Tuple[bool, error]

# Méthodes statiques utilitaires
@staticmethod extract_where_clause(subset) -> Tuple[prefix, where]
@staticmethod wrap_in_parentheses(expr) -> str
```

### 4. Intégration avec FilterEngineTask

**Modifications dans filter_task.py:**

```python
# Import ajouté
from .builders.subset_string_builder import SubsetStringBuilder

# Initialisation lazy
self._subset_builder = None

# Getter
def _get_subset_builder(self):
    if self._subset_builder is None:
        self._subset_builder = SubsetStringBuilder(
            sanitize_fn=self._sanitize_subset_string,
            use_optimizer=True
        )
    return self._subset_builder

# Délégation
def _queue_subset_string(self, layer, expression):
    return self._get_subset_builder().queue_subset_request(layer, expression)

def _build_combined_filter_expression(...):
    result = self._get_subset_builder().combine_expressions(...)
    return result.expression
```

### 5. Tests unitaires

**Fichier:** [tests/unit/tasks/builders/test_subset_string_builder.py](../tests/unit/tasks/builders/test_subset_string_builder.py)

| Classe de test | Nombre de tests |
|----------------|-----------------|
| `TestSubsetRequest` | 2 |
| `TestSubsetStringBuilder` | 6 |
| `TestCombineExpressions` | 5 |
| `TestManualCombine` | 2 |
| `TestValidation` | 5 |
| `TestUtilityMethods` | 4 |
| `TestOptimizerIntegration` | 2 |
| **Total** | **26 tests** |

## Architecture

```
FilterEngineTask
    │
    └─► _get_subset_builder() (lazy init)
            │
            └─► SubsetStringBuilder
                    │
                    ├─► queue_subset_request()
                    │       └─► _pending_requests: List[SubsetRequest]
                    │
                    └─► combine_expressions()
                            │
                            ├─► CombinedQueryOptimizer (si activé)
                            │
                            └─► _manual_combine() (fallback)
```

## Thread Safety

```
Background Thread                 Main Thread
      │                                │
      ▼                                │
queue_subset_request()                 │
      │                                │
      └── _pending_requests ─────────► │
                                       ▼
                            get_pending_requests()
                                       │
                                       ▼
                            layer.setSubsetString()
```

**CRITIQUE:** `setSubsetString()` DOIT être appelé depuis le thread principal pour éviter les crashs.

## Métriques

| Métrique | Avant | Après |
|----------|-------|-------|
| LOC dans FilterEngineTask | ~150 | ~20 (délégation) |
| LOC dans SubsetStringBuilder | 0 | ~320 |
| Tests unitaires | 0 | 26 |
| Couverture estimée | - | 90% |

## Prochaines étapes

| Phase | Description | Status |
|-------|-------------|--------|
| E13 Step 5 | FeatureCollector extraction | ⏳ |
| E13 Step 6 | FilterOrchestrator simplification | ⏳ |
| E13 Step 7 | God Class reduction finale | ⏳ |
