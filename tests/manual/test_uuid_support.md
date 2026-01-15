# Test Manual: Support UUID pour Feature Pickers et Zoom/Flash

**Version:** 4.0-alpha  
**Date:** 15 janvier 2026  
**Correctif:** UUID FIX v4.0

## 🎯 Objectif

Valider que les feature pickers, zoom, flash et autres fonctionnalités fonctionnent correctement avec des champs UUID comme clés primaires.

## 📋 Zones Corrigées

### 1. Expression Building (exploring_controller.py)
- ✅ Conversion explicite en string pour les UUID avant création d'expressions SQL
- ✅ Échappement des quotes simples dans les valeurs UUID/texte

### 2. Feature Picker Widget (custom_widgets.py)
- ✅ Conversion des fid non-numériques en string lors du stockage
- ✅ Support des UUID stockés comme valeurs PK

### 3. Expression Builder (expression_builder.py)
- ✅ Détection améliorée du type de champ (isNumeric())
- ✅ Formatage adapté pour UUID, text et numeric

## 🧪 Scénarios de Test

### Scénario 1: Single Feature Selection avec UUID

**Pré-requis:**
- Layer PostgreSQL ou OGR avec champ UUID comme PK
- Exemple: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`

**Steps:**
1. Ouvrir FilterMate
2. Sélectionner un layer avec PK UUID
3. Aller dans l'onglet "Exploring"
4. Mode "Single Selection"
5. Sélectionner une feature dans le picker

**Résultat Attendu:**
- ✅ Feature sélectionnée correctement
- ✅ Expression générée: `"id" = '7b2e1a3e-b812-4d51-bf33-7f0cd0271ef3'`
- ✅ Zoom/Flash fonctionne

### Scénario 2: Multiple Feature Selection avec UUID

**Steps:**
1. Mode "Multiple Selection"
2. Cocher plusieurs features avec UUID PK
3. Cliquer "Zoom" ou "Flash"

**Résultat Attendu:**
- ✅ Expression IN correcte: `"id" IN ('uuid1', 'uuid2', 'uuid3')`
- ✅ Toutes les features sélectionnées sont affichées/zoomées

### Scénario 3: Custom Expression avec UUID

**Steps:**
1. Mode "Custom Expression"
2. Entrer: `"id" = 'some-uuid-value'`
3. Tester Zoom/Flash

**Résultat Attendu:**
- ✅ Expression validée
- ✅ Feature trouvée et affichée

### Scénario 4: Types de Champs Mixtes

Tester avec différents types de PK:

| Type PK | Exemple | Expression Attendue |
|---------|---------|---------------------|
| INTEGER | 123 | `"id" = 123` |
| UUID | 7b2e1a3e-... | `"id" = '7b2e1a3e-...'` |
| VARCHAR | 'ABC123' | `"id" = 'ABC123'` |
| TEXT | 'Feature-001' | `"id" = 'Feature-001'` |

## 🐛 Problèmes Connus Résolus

### Avant Correctif
```python
# ❌ ANCIEN CODE - Erreur avec UUID
pk_value = some_uuid_object  # Python UUID object
expression = f'"{pk_name}" = \'{pk_value}\''  # Crash!
# Résultat: "id" = 'UUID('7b2e1a3e-...')' ← Syntaxe invalide
```

### Après Correctif
```python
# ✅ NOUVEAU CODE - Support UUID
pk_value_str = str(pk_value).replace("'", "''")  # Conversion + escape
expression = f'"{pk_name}" = \'{pk_value_str}\''
# Résultat: "id" = '7b2e1a3e-...' ← Syntaxe valide
```

## 📊 Validation Technique

### Code Inspection

Vérifier dans les logs QGIS:
```
FilterMate.Controllers.Exploring: Generated expression for postgresql: "id" = '7b2e1a3e-...'
```

### Vérification SQL

Si PostgreSQL, vérifier dans pgAdmin que la requête générée est valide:
```sql
SELECT * FROM my_table WHERE "id" = '7b2e1a3e-b812-4d51-bf33-7f0cd0271ef3'
```

## ✅ Checklist de Validation

- [ ] Layer avec PK INTEGER: OK
- [ ] Layer avec PK UUID: OK
- [ ] Layer avec PK VARCHAR: OK
- [ ] Single selection: OK
- [ ] Multiple selection: OK
- [ ] Custom expression: OK
- [ ] Zoom fonctionne: OK
- [ ] Flash fonctionne: OK
- [ ] Identify fonctionne: OK
- [ ] Aucune erreur dans logs: OK

## 📝 Notes

- Les fonctions `zoomToFeatureIds()` et `flashFeatureIds()` utilisent les **QGIS internal FIDs** (toujours des entiers), donc pas d'impact UUID direct
- Le problème UUID se situe uniquement dans la **construction des expressions SQL** pour récupérer les features
- La correction s'applique à **tous les providers** (PostgreSQL, Spatialite, OGR)

## 🔗 Références

- Fichiers modifiés:
  - [ui/controllers/exploring_controller.py](../../ui/controllers/exploring_controller.py)
  - [ui/widgets/custom_widgets.py](../../ui/widgets/custom_widgets.py)
  - [core/filter/expression_builder.py](../../core/filter/expression_builder.py)

- Documentation:
  - [.serena/memories/primary_key_detection_system.md](../../.serena/memories/primary_key_detection_system.md)
  - [core/filter/pk_formatter.py](../../core/filter/pk_formatter.py)
