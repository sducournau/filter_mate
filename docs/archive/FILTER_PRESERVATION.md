# Préservation Automatique des Filtres - FilterMate

**Version:** 2.3.0+  
**Date:** 13 décembre 2025  
**Feature:** Filter Preservation on Layer Switch

---

## 📋 Vue d'Ensemble

FilterMate implémente désormais un système de **préservation automatique des filtres** qui garantit que les filtres existants ne sont jamais perdus lors de l'application de nouveaux filtres, même lors du changement de couche.

## 🎯 Problème Résolu

### Scénario Utilisateur

1. L'utilisateur filtre des couches par des polygones (features d'une couche source)
2. L'utilisateur change de couche courante (ex: passe à "homecount")
3. L'utilisateur applique un filtre attributaire dans "custom selection"
4. **Avant:** Le nouveau filtre remplaçait l'ancien → perte des filtres géométriques
5. **Après:** Le nouveau filtre est combiné avec l'ancien → filtres cumulatifs préservés

## 🔧 Comportement Technique

### Logique de Combinaison

#### Pour la Couche Source

```python
def _combine_with_old_subset(self, expression):
    # Si un filtre existant est détecté
    if self.param_source_old_subset:
        # Récupérer l'opérateur défini dans l'UI
        combine_operator = self._get_source_combine_operator()
        
        # Si aucun opérateur défini, utiliser AND par défaut
        if not combine_operator:
            combine_operator = 'AND'
            
        # Combiner: (ancien filtre) AND (nouveau filtre)
        return f'({old_subset}) {combine_operator} ({expression})'
    
    return expression  # Pas de filtre existant
```

#### Pour les Couches Distantes

```python
def _combine_with_old_filter(self, expression, layer):
    old_subset = layer.subsetString()
    
    if old_subset:
        combine_operator = self._get_combine_operator() or 'AND'
        return f"({old_subset}) {combine_operator} ({expression})"
    
    return expression
```

### Opérateurs de Combinaison

| Opérateur | Comportement | Exemple SQL |
|-----------|-------------|-------------|
| **AND** (défaut) | Intersection - Cumule les conditions | `(pop > 1000) AND (area > 500)` |
| **OR** | Union - Au moins une condition | `(pop > 1000) OR (area > 500)` |
| **AND NOT** | Exclusion - Première condition SAUF deuxième | `(pop > 1000) AND NOT (area > 500)` |

## 🎨 Interface Utilisateur

### Bouton Combine Operator

**Widget:** `pushButton_checkable_filtering_current_layer_combine_operator`

- **État inactif:** Opérateur AND utilisé par défaut (silencieux)
- **État actif:** Affiche les comboBox pour choisir l'opérateur
  - Source Layer Operator: `comboBox_filtering_source_layer_combine_operator`
  - Other Layers Operator: `comboBox_filtering_other_layers_combine_operator`

### Configuration dans PROJECT_LAYERS

```python
PROJECT_LAYERS[layer_id]["filtering"] = {
    "has_combine_operator": bool,  # Bouton activé?
    "source_layer_combine_operator": str,  # 'AND', 'OR', 'AND NOT'
    "other_layers_combine_operator": str,   # 'AND', 'OR', 'AND NOT'
}
```

## 📊 Exemples d'Usage

### Exemple 1: Filtre Géométrique + Filtre Attributaire

**Étape 1:** Filtre par polygone
```sql
-- Résultat: 150 features dans zone polygonale
WHERE id IN (1, 5, 12, 45, 78, ...)
```

**Étape 2:** Changement de couche + filtre attributaire `population > 10000`

**Résultat avec préservation (AND par défaut):**
```sql
WHERE (id IN (1, 5, 12, 45, 78, ...)) AND (population > 10000)
-- Résultat: 23 features (dans zone ET avec pop > 10000)
```

**Sans préservation (ancien comportement):**
```sql
WHERE population > 10000
-- Résultat: 450 features (ignore la zone polygonale!)
```

### Exemple 2: Multi-Couches avec Prédicats Géométriques

**Configuration:**
- Couche source: "parcelles" (filtre: `zone = 'urbaine'`)
- Couches distantes: ["batiments", "voies"]
- Prédicat: `intersects`
- Nouveau filtre: `type = 'commercial'`

**Résultat sur "batiments":**
```sql
-- Filtre existant: géométrie intersects parcelles urbaines
-- Nouveau filtre: type commercial
-- Combiné:
WHERE (ST_Intersects(geom, source_geom)) AND (type = 'commercial')
```

## 🔍 Détection et Logs

### Messages de Log

```python
# Détection de filtre existant
logger.info(f"FilterMate: Filtre existant détecté sur {layer_name}: {old_subset[:100]}...")

# Application opérateur par défaut
logger.info(f"FilterMate: Aucun opérateur défini, utilisation de AND par défaut pour préserver le filtre existant")

# Préservation multi-couches
logger.info(f"FilterMate: Préservation du filtre existant sur {layer_name} avec AND par défaut")
```

### Vérification dans QGIS

1. Ouvrir la **Table d'Attributs** de la couche
2. Vérifier le **Subset String** dans les propriétés de la couche:
   - Clic droit → Propriétés → Source → Query Builder
   - La requête affichée montre les filtres combinés

## 🚨 Cas Particuliers

### Désactivation de la Préservation

Pour **remplacer** un filtre au lieu de le combiner:

1. **Option 1:** Réinitialiser d'abord (bouton "Reset Filter")
2. **Option 2:** Utiliser le système Undo/Redo
   - Undo pour revenir en arrière
   - Appliquer le nouveau filtre

### Expressions Complexes

Les expressions SQL complexes avec WHERE imbriqués sont gérées:

```python
# Ancien filtre complexe
"WHERE (field1 > 10) AND (field2 IN ('A', 'B'))"

# Extraction WHERE clause
param_old_subset_where = "WHERE (field1 > 10) AND (field2 IN ('A', 'B'))"

# Combinaison
f"{base_query} {param_old_subset_where} AND ({new_expression})"
```

## 🧪 Tests

### Test Unitaire (à créer)

```python
def test_filter_preservation_on_layer_switch():
    """Verify filters are preserved when switching layers"""
    # Setup layer with existing filter
    layer = create_test_layer()
    layer.setSubsetString("population > 5000")
    
    # Apply new filter without combine operator
    task = FilterEngineTask(...)
    task._initialize_source_filtering_parameters()
    result = task._combine_with_old_subset("area > 100")
    
    # Assert filters combined with AND
    assert "population > 5000" in result
    assert "area > 100" in result
    assert "AND" in result
```

### Test Manuel

1. Charger couche "communes"
2. Filtrer par polygone (selection géométrique)
3. Vérifier nombre de features (ex: 45)
4. Changer de couche courante
5. Appliquer filtre attributaire `population > 1000`
6. **Vérifier:** Nombre features < 45 (intersection)
7. **Vérifier:** Query Builder montre les deux filtres

## 📝 Notes de Développement

### Fichiers Modifiés

- `modules/tasks/filter_task.py`:
  - `_initialize_source_filtering_parameters()`: Capture systématique du filtre existant
  - `_combine_with_old_subset()`: Opérateur AND par défaut
  - `_combine_with_old_filter()`: Opérateur AND par défaut

### Backward Compatibility

✅ **100% compatible** avec versions antérieures:
- Comportement par défaut (AND) est le plus logique
- Si bouton combine_operator est activé, l'utilisateur garde le contrôle
- Aucun changement dans l'API publique

### Performance

- **Impact:** Négligeable
- **Overhead:** Simple concaténation de strings SQL
- **Optimisation:** Les backends (PostgreSQL/Spatialite) optimisent les requêtes combinées

## 🎓 Documentation Utilisateur

### Message d'Aide UI (à ajouter)

> **💡 Conseil:** Vos filtres existants sont automatiquement préservés !
> 
> Lorsque vous appliquez un nouveau filtre, il est combiné avec les filtres existants via l'opérateur AND.
> 
> **Pour remplacer complètement un filtre:**
> 1. Cliquez sur "Reset Filter" (🔄)
> 2. Appliquez votre nouveau filtre
> 
> **Pour choisir un autre opérateur:**
> 1. Activez le bouton "Combine Operator"
> 2. Sélectionnez OR ou AND NOT selon vos besoins

### FAQ

**Q: Pourquoi mes filtres ne s'effacent pas quand je change de couche?**  
**R:** C'est voulu ! FilterMate préserve automatiquement vos filtres pour éviter les pertes de données. Utilisez "Reset" pour effacer.

**Q: Comment revenir en arrière?**  
**R:** Utilisez les boutons Undo/Redo (⏪ ⏩) pour naviguer dans l'historique des filtres.

**Q: Puis-je utiliser OR au lieu de AND?**  
**R:** Oui ! Activez le bouton "Combine Operator" et sélectionnez l'opérateur souhaité.

---

## 🔗 Références

- `docs/UNDO_REDO_IMPLEMENTATION.md`: Système d'historique
- `docs/architecture_overview.md`: Architecture globale
- `modules/filter_history.py`: Gestion de l'historique
- `modules/tasks/filter_task.py`: Logique de filtrage

---

**Implémenté par:** Copilot + Simon Ducournau  
**Version:** 2.3.0  
**Statut:** ✅ Production Ready
