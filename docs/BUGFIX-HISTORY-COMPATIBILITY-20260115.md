# Bugfix: HistoryService Compatibility Layer

## Date
15 janvier 2026

## Problème
`AttributeError: 'HistoryService' object has no attribute 'get_or_create_history'`

### Contexte
Le plugin FilterMate a migré de l'ancienne architecture `HistoryManager` (qui gérait des instances `FilterHistory` par couche) vers une nouvelle architecture hexagonale avec `HistoryService` (qui gère toutes les couches de manière globale).

Cependant, `adapters/undo_redo_handler.py` utilisait toujours l'ancienne API qui attendait :
- `history_manager.get_or_create_history(layer_id)` → retourne un `FilterHistory`
- `FilterHistory.push_state(expression, feature_count, description, metadata)`

La nouvelle API `HistoryService` n'avait pas ces méthodes.

### Stack trace
```
File "filter_mate_app.py", line 1517, in _initialize_filter_history
    self._undo_redo_handler.initialize_filter_history(...)
File "adapters/undo_redo_handler.py", line 620, in initialize_filter_history
    history = self._history_manager.get_or_create_history(current_layer.id())
AttributeError: 'HistoryService' object has no attribute 'get_or_create_history'
```

## Solution

### Approche
Création d'une **couche de compatibilité** dans `HistoryService` pour supporter l'ancienne API sans casser la nouvelle architecture.

### Changements dans `core/services/history_service.py`

#### 1. Nouvelle classe `LayerHistory` (wrapper de compatibilité)
```python
class LayerHistory:
    """
    Per-layer history wrapper for backward compatibility with old HistoryManager API.
    
    This class provides the old FilterHistory-like interface while delegating
    to the global HistoryService.
    """
    
    def __init__(self, layer_id: str, parent_service: 'HistoryService'):
        self.layer_id = layer_id
        self._parent = parent_service
        self._states = []  # Simulated per-layer states for compatibility
    
    def push_state(self, expression: str, feature_count: int, 
                   description: str = "", metadata: Optional[Dict] = None):
        """Push a filter state (compatibility with old FilterHistory API)."""
        # ... implementation
```

#### 2. Ajout du cache de wrappers dans `HistoryService.__init__`
```python
def __init__(self, max_depth: int = 50, ...):
    # ... existing code
    # Per-layer history wrappers (for backward compatibility)
    self._layer_histories: Dict[str, LayerHistory] = {}
```

#### 3. Nouvelle méthode `get_or_create_history()`
```python
def get_or_create_history(self, layer_id: str) -> LayerHistory:
    """
    Get or create per-layer history wrapper (backward compatibility).
    
    Returns:
        LayerHistory wrapper for this layer
    """
    if layer_id not in self._layer_histories:
        self._layer_histories[layer_id] = LayerHistory(layer_id, self)
    return self._layer_histories[layer_id]
```

## Avantages de cette solution

✅ **Rétrocompatibilité** : L'ancienne API fonctionne sans changement  
✅ **Pas de régression** : La nouvelle API `HistoryService` reste intacte  
✅ **Migration progressive** : Permet de migrer `undo_redo_handler.py` plus tard  
✅ **Transparent** : Les appelants ne voient pas la différence  
✅ **Testable** : Pas de dépendances QGIS dans la couche de compatibilité

## Fichiers modifiés
- `core/services/history_service.py` (+70 lignes environ)

## Fichiers impactés (mais non modifiés)
- `adapters/undo_redo_handler.py` (utilise maintenant les nouvelles méthodes)
- `filter_mate_app.py` (instancie `HistoryService`)

## Tests de validation

```python
# Test que get_or_create_history existe et fonctionne
service = HistoryService()
layer_hist = service.get_or_create_history('layer_123')
assert isinstance(layer_hist, LayerHistory)

# Test que push_state fonctionne
layer_hist.push_state('test = 1', 100, 'Test')
assert len(layer_hist._states) == 1

# Test que le même layer_id retourne la même instance
layer_hist2 = service.get_or_create_history('layer_123')
assert layer_hist is layer_hist2
```

## Prochaines étapes

### Court terme (v4.0)
- ✅ Corriger l'erreur immédiate
- ⏳ Tester dans QGIS avec un workflow complet
- ⏳ Vérifier que undo/redo fonctionne correctement

### Moyen terme (v4.1 ou v5.0)
- Migrer `undo_redo_handler.py` pour utiliser directement la nouvelle API `HistoryService`
- Supprimer la couche de compatibilité `LayerHistory`
- Simplifier l'architecture

## Notes

### Pourquoi ne pas modifier `undo_redo_handler.py` directement ?
1. **Risque élevé** : `undo_redo_handler.py` est complexe (677 lignes) et critique
2. **Temps limité** : Fix rapide nécessaire pour débloquer l'utilisateur
3. **Migration progressive** : Permet de valider d'abord que la nouvelle API fonctionne
4. **Séparation des préoccupations** : Le fix est isolé dans `HistoryService`

### Architecture finale visée
```
HistoryService (global)
    ↓ push(HistoryEntry)
    ↓ undo() → HistoryEntry
    ↓ redo() → HistoryEntry
    ↓ get_history_for_layer(layer_id) → List[HistoryEntry]
    
UndoRedoHandler
    ↓ utilise HistoryService directement
    ↓ pas de LayerHistory
```

## Références
- Issue originale : AttributeError sur `get_or_create_history`
- Architecture v4.0 : `docs/ARCHITECTURE-v4.0.md`
- Migration status : `_bmad-output/REFACTORING-STATUS-20260112.md`
- Ancien code : `before_migration/modules/filter_history.py`
