# Smart Field Selection - FilterMate v4.0

**Feature:** Automatic field selection with per-layer persistence

## 🎯 Objectif

Les combobox de champs dans les modes single et multiple selection de l'onglet Exploring sélectionnent maintenant automatiquement le "meilleur champ" et mémorisent le choix de l'utilisateur par couche.

## 📋 Fonctionnalités

### 1. Sélection Automatique Intelligente

Quand vous changez de couche, FilterMate sélectionne automatiquement le meilleur champ dans cet ordre de priorité :

1. **Champ sauvegardé** (si vous avez déjà utilisé cette couche)
2. **Expression d'affichage QGIS** (configurée dans les propriétés de la couche)
3. **Champs ValueRelation** avec `represent_value()` pour affichage lisible
4. **Champs descriptifs** (patterns: name, nom, label, titre, description, etc.)
5. **Champs texte** (en excluant les IDs)
6. **Clé primaire** (dernier recours)

### 2. Mémorisation du Choix Utilisateur

Quand vous sélectionnez un champ différent :
- ✅ **Sauvegardé automatiquement** dans la base SQLite du projet
- ✅ **Restauré automatiquement** quand vous revenez sur la couche
- ✅ **Par projet** : Chaque projet garde ses propres préférences
- ✅ **Par couche** : Chaque couche a son propre champ préféré

### 3. Synchronisation Entre Modes

Les champs sont gérés indépendamment pour :
- Single Selection
- Multiple Selection  
- Custom Expression

## 📊 Exemples Pratiques

### Exemple 1 : Couche "Villes"

**Champs:** `[id, nom, population, geom]`

**Comportement:**
```
1. Première ouverture → Auto-sélection de "nom" (champ descriptif)
2. User change → "population"
3. Sauvegarde dans SQLite
4. Retour sur la couche → Restaure "population"
```

### Exemple 2 : Couche avec ValueRelation

**Champs:** `[fid, type_route_id (ValueRelation), longueur, geom]`

**Comportement:**
```
Auto-sélection → represent_value("type_route_id")
Affiche: "Autoroute" au lieu de "5"
```

### Exemple 3 : Multi-Projets

```
Projet A: Couche "villes" → Utilisateur sélectionne "nom"
Projet B: Couche "villes" → Utilisateur sélectionne "population"

Chaque projet garde sa propre préférence indépendamment.
```

## 🔧 Stockage SQLite

### Table: layer_variables

```sql
CREATE TABLE layer_variables (
    project_path TEXT,
    layer_id TEXT,
    category TEXT,
    property TEXT,
    value TEXT,
    PRIMARY KEY (project_path, layer_id, category, property)
);
```

### Exemple de données

```sql
-- Projet: mon_projet.qgs
-- Couche: villes (layer123)
INSERT INTO layer_variables VALUES (
    '/path/to/mon_projet.qgs',
    'layer123',
    'exploring',
    'single_selection_expression',
    'nom'
);
```

## 🎮 Utilisation

### Pas d'Action Requise !

Le système fonctionne automatiquement :

1. **Changez de couche** → Champ intelligent sélectionné automatiquement
2. **Changez le champ** → Votre choix est sauvegardé
3. **Revenez sur la couche** → Votre champ est restauré

### Vérification dans les Logs

Activez les logs pour voir le fonctionnement :

```python
# Logs QGIS (Ctrl+Alt+M)
FilterMate.Controllers.Exploring: Best field detected for layer 'villes': nom
FilterMate.Controllers.Exploring: Persisting single_selection field 'population' to SQLite for layer villes
FilterMate.Controllers.Exploring: Using existing expressions for layer 'villes': single=population, multiple=nom
```

## 🐛 Gestion des Cas Limites

| Situation | Comportement |
|-----------|--------------|
| **Champ supprimé de la couche** | Fallback vers le meilleur champ disponible |
| **Couche sans champs** | Utilise la clé primaire ou premier champ |
| **Expression sauvegardée invalide** | Reset vers le meilleur champ |
| **Couche devient invalide** | Skip la sauvegarde (évite les erreurs) |
| **Première utilisation** | Auto-sélection intelligente |

## 📝 Détails Techniques

### Fichiers Modifiés

- [ui/controllers/exploring_controller.py](../ui/controllers/exploring_controller.py)
  - `_reload_exploration_widgets()`: Logique de sélection intelligente
  - `exploring_source_params_changed()`: Sauvegarde des préférences

### Dépendances

- [infrastructure/utils/layer_utils.py](../infrastructure/utils/layer_utils.py): `get_best_display_field()`
- [filter_mate_app.py](../filter_mate_app.py): `save_variables_from_layer()`
- [config/config.py](../config/config.py): Configuration SQLite

### Flux de Signaux

```
Utilisateur change le champ
  ↓
QgsFieldExpressionWidget.fieldChanged
  ↓
exploring_source_params_changed(change_source="field_changed")
  ↓
settingLayerVariable.emit(layer, [("exploring", "single_selection_expression")])
  ↓
FilterMateApp.save_variables_from_layer()
  ↓
SQLite: UPDATE layer_variables SET value='nouveau_champ'
```

## ✅ Avantages

- **🧠 Intelligence** : Sélectionne automatiquement les champs les plus pertinents
- **💾 Mémoire** : Se souvient de vos choix par couche et par projet
- **🔄 Persistance** : Survit aux redémarrages de QGIS
- **👤 Respect** : Garde vos préférences personnelles
- **🚀 Transparence** : Fonctionne sans action utilisateur

## 🔗 Références

- Commit: SMART_FIELD_SELECTION v4.0
- Lié à: UUID FIX v4.0 (support des clés primaires non-numériques)
- Documentation: [.serena/memories/primary_key_detection_system.md](../.serena/memories/primary_key_detection_system.md)

## 🎓 Pour les Développeurs

### Ajouter un Nouveau Pattern de Champ

Modifiez `get_best_display_field()` dans `infrastructure/utils/layer_utils.py` :

```python
# Patterns de noms communs pour champs descriptifs
name_patterns = [
    'name', 'nom', 'label', 'titre', 'title',
    'description', 'libelle', 'libellé',
    'mon_nouveau_pattern'  # ← Ajoutez ici
]
```

### Déboguer la Sélection

```python
# Dans exploring_controller.py
logger.setLevel(logging.DEBUG)

# Logs à observer:
# - "Best field detected..."
# - "Auto-selected best field..."
# - "Persisting ... field to SQLite..."
# - "Restored saved field..."
```

---

**Version:** v4.0-alpha  
**Date:** 15 janvier 2026  
**Auteur:** FilterMate Team
