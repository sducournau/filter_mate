# Résumé du correctif - 15 janvier 2026

## ❌ Erreur corrigée
```
AttributeError: 'HistoryService' object has no attribute 'get_or_create_history'
```

## 🔧 Solution appliquée

### Fichier modifié
`core/services/history_service.py`

### Changements
1. **Nouvelle classe `LayerHistory`** : Wrapper de compatibilité qui simule l'ancienne API `FilterHistory`
2. **Cache de wrappers** : `self._layer_histories: Dict[str, LayerHistory] = {}` dans `HistoryService`
3. **Nouvelle méthode** : `get_or_create_history(layer_id: str) → LayerHistory`

### Code ajouté (~70 lignes)
```python
class LayerHistory:
    """Per-layer history wrapper for backward compatibility."""
    def __init__(self, layer_id: str, parent_service: 'HistoryService')
    def push_state(self, expression, feature_count, description, metadata)

# Dans HistoryService:
def get_or_create_history(self, layer_id: str) -> LayerHistory:
    if layer_id not in self._layer_histories:
        self._layer_histories[layer_id] = LayerHistory(layer_id, self)
    return self._layer_histories[layer_id]
```

## ✅ Tests de validation
- ✅ Syntaxe Python valide (`py_compile`)
- ✅ Méthode `get_or_create_history()` fonctionne
- ✅ `LayerHistory.push_state()` fonctionne
- ✅ Cache retourne la même instance pour le même layer_id

## 📝 Documentation
- `docs/BUGFIX-HISTORY-COMPATIBILITY-20260115.md` : Documentation complète
- Explication de l'architecture avant/après
- Plan de migration future

## 🚀 Prochaine étape
Tester dans QGIS pour valider que l'erreur est résolue et que le plugin se charge correctement.

## 📊 Impact
- **Lignes ajoutées** : ~70
- **Fichiers modifiés** : 1 (`core/services/history_service.py`)
- **Risque** : Faible (ajout de code, pas de modification de l'existant)
- **Rétrocompatibilité** : Maintenue à 100%
