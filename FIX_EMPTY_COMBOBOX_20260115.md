# Fix: Empty Combobox Fields in Exploring Tab

**Date:** 15 janvier 2026  
**Version:** v4.0-alpha  
**Issue:** Les combobox de sélection de champs restent vides au changement de layer

## 🐛 Problème

Lors du changement de couche (layer) dans l'onglet Exploring, les combobox de sélection de champs (single_selection, multiple_selection, custom_selection) restaient vides au lieu de sélectionner automatiquement un champ par défaut.

**Comportement attendu:**
- Changement de layer → auto-sélection du "meilleur" champ (nom, label, etc.)
- Si aucun champ approprié → sélection du premier champ disponible
- Les combobox ne peuvent JAMAIS être vides

**Comportement observé:**
- Combobox vides après changement de layer
- Aucun champ sélectionné par défaut

## 🔍 Cause Racine

Le problème avait **deux causes**:

### 1. Expressions initialisées avec la clé primaire (PAS vides!)

Contrairement à ce qui était supposé initialement, les expressions ne sont JAMAIS vides. Dans `core/tasks/layer_management_task.py` (ligne ~487):

```python
# Ensure all expression properties exist with primary key as default
expression_properties = [
    "single_selection_expression",
    "multiple_selection_expression",
    "custom_selection_expression"
]
for prop_name in expression_properties:
    if prop_name not in exploring:
        exploring[prop_name] = str(primary_key)  # ← Défaut: clé primaire!
```

Donc au premier chargement d'une couche:
- `single_selection_expression = "fid"` (ou "id", "ogc_fid", etc.)
- `multiple_selection_expression = "fid"`
- `custom_selection_expression = "fid"`

**Le problème**: Ces expressions ne sont PAS vides - elles contiennent la clé primaire, qui n'est généralement PAS un champ descriptif (nom, label, etc.).

### 2. Logique de fallback testait si expression vide

Le code original testait:

```python
# ❌ ANCIEN CODE - Ne se déclenche JAMAIS!
if not single_expr:  # False car single_expr = "fid" (truthy)
    best_field = get_best_display_field(layer)
    single_expr = best_field
```

**Résultat**: Les combobox affichaient toujours la clé primaire (`fid`, `id`) au lieu de champs descriptifs (`name`, `nom`, `label`).

## ✅ Solution

Ajout d'un **fallback en cascade** garantissant TOUJOURS une valeur:

```python
# ✅ NOUVEAU CODE
best_field = get_best_display_field(layer)
logger.debug(f"Best field detected for layer '{layer.name()}': {best_field}")

# FIX v4.0: If get_best_display_field returns empty, force to first field
# Comboboxes CANNOT be empty - must always have a value
if not best_field:
    fields = layer.fields()
    if fields.count() > 0:
        best_field = fields[0].name()
        logger.warning(f"get_best_display_field returned empty, using first field '{best_field}' for layer '{layer.name()}'")
    else:
        # No fields at all - fallback to $id
        best_field = "$id"
        logger.warning(f"Layer has no fields, using $id for layer '{layer.name()}'")
```

### Hiérarchie de Sélection (Fallback en Cascade)

1. **Préférence utilisateur sauvegardée** (SQLite) → priorité absolue
2. **Meilleur champ détecté** (`get_best_display_field()`) → champs descriptifs
3. **Premier champ disponible** (`fields[0].name()`) → fallback si aucun champ descriptif
4. **Expression `$id`** → fallback absolu si layer sans champs

**Garantie:** `best_field` ne sera JAMAIS vide après cette logique.

## 📊 Logs Ajoutés

Pour faciliter le debug, ajout de logs détaillés:

```python
logger.info(f"FINAL expressions for layer '{layer.name()}': single={single_expr}, multiple={multiple_expr}, custom={custom_expr}")

logger.info(f"Setting SINGLE_SELECTION_EXPRESSION widget: layer={layer.name()}, expression='{single_expr}'")
# ... setExpression() ...
logger.info(f"Widget expression after setExpression: '{widget.expression()}'")
```

**Vérification utilisateur:**
1. Ouvrir QGIS avec FilterMate
2. Changer de couche dans Exploring
3. Vérifier logs QGIS (Python console ou fichier log)
4. Chercher lignes `FINAL expressions for layer` et `Setting SINGLE_SELECTION_EXPRESSION widget`

## 🧪 Test Manuel

### Scénario 1: Layer avec champs descriptifs

**Layer:** `cities` avec `[id, name, population, geometry]`

**Résultat attendu:**
- `best_field = "name"` (détecté par patterns)
- Combobox affiche "name"
- LOG: `Auto-selected field 'name' for single_selection`

### Scénario 2: Layer sans champs descriptifs

**Layer:** `polygons` avec `[fid, area, perimeter, geometry]`

**Résultat attendu:**
- `get_best_display_field()` retourne `""` (aucun pattern trouvé)
- Fallback vers premier champ: `best_field = "fid"`
- Combobox affiche "fid"
- LOG: `get_best_display_field returned empty, using first field 'fid'`

### Scénario 3: Layer avec seulement géométrie

**Layer:** `shapes` avec `[geometry]` (pas de champs attributs)

**Résultat attendu:**
- `fields.count() = 0`
- Fallback vers `$id`: `best_field = "$id"`
- Combobox affiche "$id"
- LOG: `Layer has no fields, using $id`

### Scénario 4: Layer avec préférence utilisateur sauvegardée

**Setup:**
1. Layer `cities` avec `[id, name, population]`
2. Utilisateur a précédemment choisi `population` dans la combobox
3. Préférence sauvegardée dans SQLite

**Résultat attendu:**
- Ignore `get_best_display_field()`
- Combobox affiche `population` (préférence sauvegardée)
- LOG: `Using existing expressions for layer 'cities': single=population`

## 📝 Fichiers Modifiés

- **ui/controllers/exploring_controller.py**
  - Méthode `_reload_exploration_widgets()` (lignes ~2287-2350)
  - Ajout fallback en cascade pour `best_field`
  - Ajout logs détaillés

## 🔗 Références

- Issue: Combobox vides au changement de layer
- Related: Smart Field Selection (v4.0)
- Related: UUID Fix (v4.0) - même commit group

## ✅ Validation

- [x] Fallback en cascade implémenté
- [x] Logs détaillés ajoutés
- [ ] Test manuel avec layer sans champs descriptifs
- [ ] Test manuel avec layer sans champs attributs
- [ ] Vérification logs dans QGIS

## 🚀 Impact

**Avant:** Combobox vides → utilisateur doit sélectionner manuellement à chaque changement de layer

**Après:** Combobox auto-remplie intelligemment → workflow fluide, même avec layers "difficiles"
