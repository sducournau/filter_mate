# Fix: Spatialite Backend - Negative Buffer Support (2026-01)

## Issue

Avec le backend Spatialite, lors du filtrage géométrique avec un **buffer négatif** (ex: -1m), certaines couches distantes n'étaient pas filtrées correctement :

- Les couches avec `mode=OPTIMIZED SOURCE TABLE (R-tree)` retournaient 0 résultats
- Le diagnostic indiquait `source_geom valid=0, empty=0` (géométrie invalide)
- Le fallback OGR échouait également

### Contexte

Un **buffer négatif** (aussi appelé "érosion") réduit la géométrie source. Par exemple, un buffer de -1m sur un polygone réduit sa taille de 1m de tous côtés. Si le polygone a des parties fines (< 2m de largeur), ces parties disparaissent et la géométrie peut devenir **vide** ou **invalide**.

## Cause Racine

### 1. Détection incorrecte des buffers négatifs

**Ligne 1277** (ancienne) :
```python
has_buffer = buffer_value > 0
```

Cette condition ne détectait que les buffers **positifs** (`> 0`), ignorant les buffers **négatifs** (`< 0`). Résultat :
- La colonne `geom_buffered` n'était pas créée
- Le buffer négatif n'était jamais appliqué à la géométrie source
- La requête spatiale utilisait `geom` au lieu de `geom_buffered`

### 2. Géométries invalides après buffer négatif

`ST_Buffer()` avec une valeur négative peut produire des géométries **invalides** ou **vides** si :
- Le polygone a des parties fines qui disparaissent
- La géométrie résultante a des auto-intersections
- L'érosion élimine complètement certaines parties

Spatialite nécessite `MakeValid()` après `ST_Buffer()` pour gérer ces cas.

### 3. Diagnostic erroné

Le code diagnostiquait "géométrie invalide/vide = problème grave" sans différencier :
- **Géométrie invalide** → vraiment un problème technique
- **Géométrie vide après buffer négatif** → comportement normal et attendu

Cela déclenchait un fallback OGR inutile alors que le résultat (0 features) était correct.

## Solution

### 1. Détection des buffers négatifs

**Ligne 1277-1280** (nouvelle) :
```python
# v2.8.10: FIX - Include negative buffers (erosion) as well as positive buffers
# Negative buffers need MakeValid() to handle potential invalid/empty geometries
has_buffer = buffer_value != 0
is_negative_buffer = buffer_value < 0
```

Détecte maintenant tous les buffers non-nuls (positifs ET négatifs).

### 2. Application de MakeValid() pour buffers négatifs

**Insertions SQL** (multi-features et single-geometry) :

```python
if is_negative_buffer:
    # Utilise MakeValid pour gérer les géométries invalides après érosion
    buffer_expr = f"MakeValid(ST_Buffer(GeomFromText(...), {buffer_value}))"
else:
    # Buffer positif - pas besoin de MakeValid
    buffer_expr = f"ST_Buffer(GeomFromText(...), {buffer_value})"
```

`MakeValid()` garantit que la géométrie résultante est valide, même si certaines parties disparaissent.

### 3. Protection contre géométries vides dans les requêtes

**Ligne 3403-3426** :

```python
# Determine which geometry column to use (buffered or not)
source_geom_col = 'geom_buffered' if has_buffer else 'geom'

# v2.8.10: Check if this is a negative buffer (erosion) case
is_negative_buffer = buffer_value < 0

# Build source geometry expression with any needed transformations
if is_geographic and buffer_value != 0 and not has_buffer:
    # Geographic CRS with buffer but not pre-computed
    if buffer_value < 0:
        # Negative buffer needs MakeValid + NULL check for empty
        source_expr = f"""
            CASE WHEN ST_IsEmpty(MakeValid(ST_Buffer(...))) = 1 
            THEN NULL 
            ELSE ST_Transform(MakeValid(ST_Buffer(...)), {target_srid})
            END
        """
elif source_srid != target_srid:
    # v2.8.10: Handle empty geometries from negative buffer
    if is_negative_buffer and has_buffer:
        source_expr = f"CASE WHEN ST_IsEmpty(s.{source_geom_col}) = 1 OR s.{source_geom_col} IS NULL THEN NULL ELSE ST_Transform(s.{source_geom_col}, {target_srid}) END"
else:
    # v2.8.10: Handle empty geometries from negative buffer
    if is_negative_buffer and has_buffer:
        source_expr = f"CASE WHEN ST_IsEmpty(s.{source_geom_col}) = 1 OR s.{source_geom_col} IS NULL THEN NULL ELSE s.{source_geom_col} END"
```

Quand la géométrie est vide après buffer négatif, `source_expr` retourne `NULL`, ce qui fait que les prédicats spatiaux retournent `NULL` (pas 1), donc aucune feature n'est sélectionnée. **C'est le comportement correct.**

### 4. Diagnostic amélioré

**Ligne 3668-3703** :

```python
# v2.8.10: Empty geometry after negative buffer is NORMAL behavior
if is_empty:
    # Check if negative buffer was used
    buf_val = filtering_params.get('buffer_value', 0) or 0
    if buf_val < 0:
        QgsMessageLog.logMessage(
            f"ℹ️ {layer.name()}: Source geometry empty after negative buffer ({buf_val}m) - normal for thin features",
            "FilterMate", Qgis.Info
        )
    else:
        QgsMessageLog.logMessage(
            f"⚠️ {layer.name()}: Source geometry is EMPTY - this explains 0 results!",
            "FilterMate", Qgis.Warning
        )
elif not is_valid:
    QgsMessageLog.logMessage(
        f"⚠️ {layer.name()}: Source geometry is INVALID - this explains 0 results!",
        "FilterMate", Qgis.Warning
    )
```

Différencie maintenant :
- **Géométrie vide après buffer négatif** → message INFO (normal)
- **Géométrie vide sans buffer négatif** → message WARNING (suspect)
- **Géométrie invalide** → message WARNING (problème)

### 5. Pas de fallback OGR inutile

**Ligne 3744-3768** :

```python
# Check if this is due to negative buffer producing empty geometry
is_negative_buffer_empty = False
if buf_val < 0 and has_buffer:
    # Check if source geometry is empty
    cursor.execute(f'SELECT ST_IsEmpty({source_geom_col_check}) FROM "{source_table}" LIMIT 1')
    result = cursor.fetchone()
    if result and result[0] == 1:
        is_negative_buffer_empty = True

# Only trigger OGR fallback if it's NOT a negative buffer empty case
if feature_count >= SUSPICIOUS_ZERO_THRESHOLD and not is_negative_buffer_empty:
    # ... fallback OGR
```

Évite le fallback OGR quand 0 résultats est dû à un buffer négatif produisant une géométrie vide (comportement normal).

## Résultats Attendus

Avec le correctif, lors du filtrage avec buffer négatif (-1m) :

1. ✅ La table source a une colonne `geom_buffered` avec `MakeValid(ST_Buffer(geom, -1))`
2. ✅ Si la géométrie devient vide, le diagnostic indique "normal for thin features"
3. ✅ Les couches retournent correctement 0 features (ou N features si certaines intersectent)
4. ✅ Pas de fallback OGR inutile
5. ✅ Messages clairs dans les logs

### Exemple de logs corrects

```
2026-01-06T10:00:00     INFO    ducts: Using buffer=-1m for source table optimization
2026-01-06T10:00:01     INFO    ducts: Spatial query completed → 11 matching features
2026-01-06T10:00:01     INFO    ✓ Spatialite source table filter: ducts → 11 features (1.04s)

2026-01-06T10:00:02     INFO    structures: Using buffer=-1m for source table optimization
2026-01-06T10:00:03     INFO    structures: Spatial query completed → 0 matching features
2026-01-06T10:00:03     INFO    🔍 structures DIAG: source_geom valid=1, empty=1, type=MULTIPOLYGON, npoints=0
2026-01-06T10:00:03     INFO    ℹ️ structures: Source geometry empty after negative buffer (-1m) - normal for thin features
2026-01-06T10:00:03     INFO    ℹ️ 0 features matched for structures (negative buffer made geometry empty)
2026-01-06T10:00:03     INFO    ✓ Spatialite filter applied: structures → 0 features
```

## Fichiers Modifiés

- `modules/backends/spatialite_backend.py`

### Lignes modifiées

1. **1277-1280** : Détection buffers négatifs (`has_buffer = buffer_value != 0`)
2. **1328-1361** : MakeValid dans insertions multi-features
3. **1394-1425** : MakeValid dans insertions single-geometry
4. **3400-3429** : Protection CASE WHEN pour géométries vides dans source_expr
5. **3668-3703** : Diagnostic amélioré (différenciation géométrie vide vs invalide)
6. **3744-3768** : Éviter fallback OGR pour buffer négatif normal

## Tests Recommandés

### Test 1 : Buffer négatif sur polygone large
- Géométrie source : polygone > 10m de largeur
- Buffer : -1m
- Résultat attendu : Polygone réduit, N features filtrées

### Test 2 : Buffer négatif sur polygone fin
- Géométrie source : polygone < 2m de largeur
- Buffer : -1m
- Résultat attendu : Géométrie vide, 0 features, message INFO "normal for thin features"

### Test 3 : Buffer négatif avec multi-features
- Géométrie source : sélection multiple
- Buffer : -1m
- Résultat attendu : Certaines géométries vides, certaines réduites, filtrage correct

### Test 4 : Couches du même GeoPackage
- 8 couches issues du même fichier .gpkg
- Buffer : -1m
- Résultat attendu : Chaque couche filtrée correctement, pas de fallback OGR

## Version

- **Date** : 2026-01-06
- **Version FilterMate** : 2.8.10 (à venir)
- **Auteur** : GitHub Copilot (via Simon Ducorneau)

## Voir Aussi

- [FIX_SPATIALITE_FREEZE_2026-01.md](FIX_SPATIALITE_FREEZE_2026-01.md) - Correctif freeze avec géométries complexes
- [NEGATIVE_BUFFER_FIX_README.md](NEGATIVE_BUFFER_FIX_README.md) - Correctif buffer négatif PostgreSQL (v2.5.3)
- `.github/copilot-instructions.md` - Guidelines pour buffer négatif
