# Implémentation Undo/Redo Global pour FilterMate

## Vue d'ensemble

Cette implémentation ajoute une fonctionnalité complète d'undo/redo intelligent qui gère à la fois les filtres sur la couche source et sur les couches distantes associées.

## Fonctionnalités

### 1. Historique Global Multi-Couches

**Nouvelle classe `GlobalFilterState`** dans `modules/filter_history.py` :
- Capture l'état de la couche source + toutes les couches distantes simultanément
- Stocke les expressions de filtre et le nombre d'entités pour chaque couche
- Permet de restaurer l'état complet de toutes les couches en une seule opération

**Extension de `HistoryManager`** :
- Gestion de l'historique global séparé de l'historique par couche
- Stack d'historique global avec `_global_states` et `_global_current_index`
- Méthodes `push_global_state()`, `undo_global()`, `redo_global()`

### 2. Logique Undo/Redo Conditionnelle

#### Cas 1 : Couche source seule
**Quand ?** Aucune couche distante n'est sélectionnée dans la liste "Layers to filter"

**Comportement :**
- Undo : Retour à l'état précédent de la couche source uniquement
- Redo : Avance à l'état suivant de la couche source uniquement
- Utilise l'historique individuel de la couche (`FilterHistory`)

#### Cas 2 : Couches distantes filtrées
**Quand ?** Des couches distantes sont sélectionnées ET ont un filtre actif

**Comportement :**
- Undo : Retour à l'état précédent pour toutes les couches (source + distantes)
- Redo : Avance à l'état suivant pour toutes les couches
- Utilise l'historique global (`GlobalFilterState`)

### 3. Intégration UI

**Boutons pushButton :**
- `pushButton_action_undo_filter` : Bouton Undo
- `pushButton_action_redo_filter` : Bouton Redo

**Gestion de l'état des boutons :**
- Activés/désactivés automatiquement selon la disponibilité de l'historique
- Mis à jour après chaque filtre, undo, redo ou changement de couche
- Fonction `update_undo_redo_buttons()` dans `filter_mate_app.py`

**Signaux Qt :**
- `currentLayerChanged` : Émis quand la couche courante change
- Connecté à `update_undo_redo_buttons()` pour MAJ immédiate

## Architecture Technique

### Modules modifiés

#### `modules/filter_history.py`
```python
class GlobalFilterState:
    - source_layer_id: str
    - source_expression: str
    - source_feature_count: int
    - remote_layers: Dict[str, Tuple[str, int]]
    - timestamp: datetime
    - metadata: dict

class HistoryManager:
    + _global_states: List[GlobalFilterState]
    + _global_current_index: int
    + push_global_state(...)
    + undo_global() -> Optional[GlobalFilterState]
    + redo_global() -> Optional[GlobalFilterState]
    + can_undo_global() -> bool
    + can_redo_global() -> bool
```

#### `filter_mate_app.py`
```python
class FilterMateApp:
    + handle_undo()
    + handle_redo()
    + update_undo_redo_buttons()
    + _push_filter_to_history(...) # Extended with global state
```

#### `filter_mate_dockwidget.py`
```python
class FilterMateDockWidget:
    + currentLayerChanged = pyqtSignal()  # New signal
```

### Workflow

1. **Application d'un filtre** (`filter_engine_task_completed`)
   ```
   Filtre appliqué → _push_filter_to_history() 
                   → Historique individuel + global (si couches distantes)
                   → update_undo_redo_buttons()
   ```

2. **Undo** (`handle_undo`)
   ```
   Clic Undo → Détection contexte (source seule ou global)
             → Application état précédent
             → Refresh layers
             → update_undo_redo_buttons()
   ```

3. **Redo** (`handle_redo`)
   ```
   Clic Redo → Détection contexte (source seule ou global)
             → Application état suivant
             → Refresh layers
             → update_undo_redo_buttons()
   ```

4. **Changement de couche**
   ```
   Sélection nouvelle couche → currentLayerChanged.emit()
                              → update_undo_redo_buttons()
   ```

## Cas d'usage

### Scénario 1 : Filtrage simple (couche source uniquement)
```
1. Utilisateur sélectionne couche "Communes"
2. Applique filtre "population > 10000"
3. Bouton Undo activé, Redo désactivé
4. Clic Undo → Retour à état "sans filtre"
5. Bouton Undo désactivé, Redo activé
6. Clic Redo → Réapplique "population > 10000"
```

### Scénario 2 : Filtrage global (source + distantes)
```
1. Utilisateur sélectionne couche source "Départements"
2. Sélectionne couches distantes ["Communes", "Routes"]
3. Applique filtre "région = 'Bretagne'"
4. Les 3 couches sont filtrées simultanément
5. Historique global enregistre l'état des 3 couches
6. Clic Undo → Les 3 couches retournent à l'état précédent
7. Clic Redo → Les 3 couches réappliquent le filtre
```

### Scénario 3 : Changement de mode
```
1. Filtre avec couches distantes (mode global)
2. Désélection des couches distantes
3. update_undo_redo_buttons() passe en mode "source seule"
4. Undo/Redo n'affectent plus que la couche source
```

## Avantages de cette implémentation

### 1. Intelligence contextuelle
- Détection automatique du mode approprié (source vs global)
- Aucune confusion pour l'utilisateur
- Comportement intuitif

### 2. Performance
- Historique séparé pour éviter les conflits
- Stack dédié pour l'historique global
- Pas de duplication inutile

### 3. Robustesse
- Gestion des cas limites (couches supprimées, etc.)
- Logs détaillés pour debugging
- Messages utilisateur clairs

### 4. Extensibilité
- Architecture modulaire
- Facile d'ajouter de nouveaux types d'états
- Compatible avec futures améliorations

## Messages utilisateur

### Succès
- **Undo source** : `"Undo: <description du filtre>"`
- **Undo global** : `"Global undo successful (X layers)"`
- **Redo source** : `"Redo: <description du filtre>"`
- **Redo global** : `"Global redo successful (X layers)"`

### Avertissements
- **Pas d'historique** : `"No more undo history"`
- **Pas de redo** : `"No more redo history"`

## Logs de débogage

Les logs incluent :
- `FilterMate: Pushed global state (X layers)` - Historique global ajouté
- `FilterMate: Performing global undo` - Undo global en cours
- `FilterMate: Performing source layer undo only` - Undo source seul
- `FilterMate: Updated undo/redo buttons - undo: X, redo: Y` - État des boutons

## Configuration

### Taille maximale de l'historique
Par défaut : 100 états

Modifiable dans `filter_mate_app.py` :
```python
self.history_manager = HistoryManager(max_size=100)
```

### Persistance
- L'historique est en mémoire (session QGIS)
- Effacé au changement de projet
- Effacé lors d'un reset complet

## Tests recommandés

### Test 1 : Historique source seul
1. Charger une couche
2. Appliquer plusieurs filtres successifs
3. Vérifier undo/redo sur la couche source
4. Vérifier que les boutons sont activés/désactivés correctement

### Test 2 : Historique global
1. Charger couche source + 2 couches distantes
2. Sélectionner les couches distantes
3. Appliquer filtre
4. Vérifier que les 3 couches sont filtrées
5. Undo → Vérifier que les 3 couches retournent à l'état précédent
6. Redo → Vérifier que les 3 couches sont à nouveau filtrées

### Test 3 : Changement de mode
1. Commencer avec couches distantes (mode global)
2. Appliquer filtre
3. Désélectionner couches distantes
4. Vérifier que undo n'affecte que la source
5. Resélectionner couches distantes
6. Vérifier retour au mode global

### Test 4 : Limites de l'historique
1. Appliquer 105 filtres successifs (max_size=100)
2. Vérifier que les 5 premiers états sont supprimés
3. Vérifier que undo fonctionne sur les 100 derniers

## Migration depuis l'ancienne version

L'implémentation est rétrocompatible :
- L'historique individuel par couche est conservé
- Le comportement existant (unfilter) reste fonctionnel
- Ajout transparent de l'historique global

## Auteur et Date

- **Implémentation** : Décembre 2025
- **Version FilterMate** : Compatible avec la version actuelle
- **Testé avec** : QGIS 3.x

## Références

- `modules/filter_history.py` : Classes `FilterState`, `FilterHistory`, `GlobalFilterState`, `HistoryManager`
- `filter_mate_app.py` : Méthodes `handle_undo()`, `handle_redo()`, `update_undo_redo_buttons()`
- `filter_mate_dockwidget.py` : Signal `currentLayerChanged`
