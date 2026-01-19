# Optimisation RTTOPO - Gestion des géométries complexes
**Date**: 2026-01-07  
**Version**: v2.9.28  
**Problème**: Erreurs RTTOPO "MakeValid error - Unknown Reason" avec géométries complexes

## 🐛 Problème Identifié

Les logs montraient des erreurs récurrentes lors du traitement de géométries complexes :

```
WARNING _apply_filter_direct_sql SQL ERROR for demand_points: 
MakeValid error - RTTOPO reports: Unknown Reason
```

**Contexte** :
- WKT de 35,835 caractères (GeometryCollection multi-polygones)
- Spatialite échoue avec `MakeValid(GeomFromText(...))`
- Le système bascule vers OGR fallback (succès mais plus lent)

## ✅ Solutions Implémentées

### 1. Réduction du seuil de simplification SQL (30KB → 30KB)

**Fichier** : `modules/backends/spatialite_backend.py`  
**Ligne** : ~2200

```python
# v2.9.28: Reduced threshold from 50KB to 30KB to match OGR fallback threshold
LARGE_WKT_SQL_SIMPLIFY_THRESHOLD = 30000  # Was 50000
```

**Impact** : Déclenche la simplification SQL plus tôt pour éviter les erreurs RTTOPO.

---

### 2. Détection des géométries valides avant MakeValid()

**Fichier** : `modules/backends/spatialite_backend.py`  
**Ligne** : ~2208-2250

**Nouveautés** :
- Vérifie si la géométrie est déjà valide avec `isGeosValid()`
- Si valide : utilise `GeomFromText()` directement (pas de MakeValid)
- Détecte les GeometryCollection (type problématique pour RTTOPO)
- Force la simplification pour GeometryCollection quelle que soit la taille

**Code** :
```python
# v2.9.28: Check if geometry is already valid to avoid unnecessary MakeValid()
needs_make_valid = True
is_geometry_collection = False

temp_geom = QgsGeometry.fromWkt(source_geom.replace("''", "'"))
if temp_geom and not temp_geom.isEmpty():
    # Check if already valid
    if temp_geom.isGeosValid():
        needs_make_valid = False
        self.log_debug("✓ Source geometry is already valid - skipping MakeValid()")
    
    # Check geometry type - GeometryCollection is problematic for RTTOPO
    geom_type = temp_geom.wkbType()
    if geom_type == QgsWkbTypes.GeometryCollection...:
        is_geometry_collection = True
        self.log_info("⚠️ GeometryCollection detected - forcing simplification")
```

**Résultats** :
- Évite les appels MakeValid() inutiles (réduction du risque d'erreur)
- Détection précoce des types géométriques problématiques
- Simplification forcée pour GeometryCollection

---

### 3. Gestion intelligente des expressions géométriques

**Fichier** : `modules/backends/spatialite_backend.py`  
**Ligne** : ~2240-2260

**Stratégies** :
1. **Géométrie valide + petite** → `GeomFromText()` seul
2. **Géométrie invalide + petite** → `MakeValid(GeomFromText())`
3. **GeometryCollection OU grande** → `SimplifyPreserveTopology()` + (MakeValid si invalide)

**Code** :
```python
if is_geometry_collection or wkt_length > LARGE_WKT_SQL_SIMPLIFY_THRESHOLD:
    # Force simplification
    if needs_make_valid:
        source_geom_expr = f"SimplifyPreserveTopology(MakeValid(GeomFromText(...)), {tolerance})"
    else:
        source_geom_expr = f"SimplifyPreserveTopology(GeomFromText(...), {tolerance})"
else:
    # Standard path
    if needs_make_valid:
        source_geom_expr = f"MakeValid(GeomFromText(...))"
    else:
        source_geom_expr = f"GeomFromText(...)"  # ✅ Nouveau : géométrie déjà valide
```

---

### 4. Détection améliorée des erreurs RTTOPO

**Fichier** : `modules/backends/spatialite_backend.py`  
**Ligne** : ~3290-3310 (erreurs SQL) + ~1625-1645 (insertion geometries)

**Avant** :
```python
if error:
    self.log_error(f"Direct SQL query failed: {error}")
    return False
```

**Après** :
```python
if error:
    error_msg = str(error)
    # v2.9.28: Detect RTTOPO MakeValid errors
    if "makevalid" in error_msg.lower() or "rttopo" in error_msg.lower():
        self.log_warning(f"Spatialite RTTOPO error - will use OGR fallback")
        self.log_info(f"  → Error: {error_msg}")
        return False  # Déclenche OGR fallback
    elif "timeout" in error_msg.lower():
        # ... gestion timeout
```

**Avantages** :
- Détection spécifique des erreurs RTTOPO vs autres erreurs SQL
- Logs informatifs (pas d'alarme inutile, OGR fallback prendra le relais)
- Meilleure traçabilité pour debugging

---

### 5. Protection dans _create_permanent_source_table

**Fichier** : `modules/backends/spatialite_backend.py`  
**Ligne** : ~1625 et ~1665

**Ajout** :
```python
if error:
    error_msg = str(error)
    # v2.9.28: Detect RTTOPO errors during geometry insertion
    if "makevalid" in error_msg.lower() or "rttopo" in error_msg.lower():
        self.log_warning(f"RTTOPO error - aborting source table, OGR fallback will be used")
        self.log_info(f"  → Error: {error_msg}")
        raise Exception(f"RTTOPO error: {error_msg}")
```

**Impact** : Évite de créer des tables sources corrompues, déclenche le fallback OGR immédiatement.

---

## 📊 Flux de Décision

```
Géométrie source
    │
    ├─→ Taille < 30KB ET valide ET pas GeometryCollection
    │   └─→ GeomFromText() direct (optimal, sans MakeValid)
    │
    ├─→ Taille < 30KB ET invalide
    │   └─→ MakeValid(GeomFromText())
    │
    ├─→ Taille ≥ 30KB OU GeometryCollection
    │   ├─→ Calcul tolérance simplification (0.01% de l'extent)
    │   ├─→ Si valide : SimplifyPreserveTopology(GeomFromText(), tol)
    │   └─→ Si invalide : SimplifyPreserveTopology(MakeValid(GeomFromText()), tol)
    │
    └─→ Si erreur RTTOPO lors de l'exécution SQL
        └─→ Fallback OGR automatique (processing.selectbylocation)
```

---

## 🎯 Résultats Attendus

### Avant (v2.9.27)
```
INFO    Spatialite apply_filter: demand_points → mode=DIRECT SQL
WARNING _apply_filter_direct_sql SQL ERROR: MakeValid error - RTTOPO reports: Unknown Reason
INFO    🔄 demand_points: Attempting OGR fallback...
INFO    ✓ OGR fallback SUCCEEDED → 9231 features
```
**Temps total** : ~5-10 secondes (tentative Spatialite échouée + OGR)

### Après (v2.9.28)

**Scénario 1 - Géométrie simple** :
```
DEBUG   ✓ Source geometry is already valid - skipping MakeValid()
INFO    Spatialite apply_filter: demand_points → mode=DIRECT SQL
INFO    → Direct SQL found 319 matching FIDs
```
**Temps** : ~1 seconde (pas de MakeValid inutile)

**Scénario 2 - GeometryCollection détecté** :
```
INFO    ⚠️ GeometryCollection detected - forcing simplification
INFO    🔧 GeometryCollection - using SQL SimplifyPreserveTopology (tolerance=0.45)
INFO    Spatialite apply_filter: demand_points → mode=DIRECT SQL
INFO    → Direct SQL found 319 matching FIDs
```
**Temps** : ~2 secondes (simplification préventive, pas d'erreur)

**Scénario 3 - Géométrie trop complexe** :
```
INFO    🔧 Large WKT (35,835 chars) - using SQL SimplifyPreserveTopology
INFO    Spatialite apply_filter: demand_points → mode=DIRECT SQL
INFO    → Direct SQL found 319 matching FIDs
```
**Temps** : ~2-3 secondes (simplification SQL, pas d'erreur RTTOPO)

**Scénario 4 - Erreur RTTOPO inévitable** :
```
WARNING Spatialite RTTOPO error - will use OGR fallback
INFO    → Error: MakeValid error - RTTOPO reports: Unknown Reason
INFO    🔄 demand_points: Attempting OGR fallback...
INFO    ✓ OGR fallback SUCCEEDED
```
**Temps** : ~5 secondes (fallback rapide, log explicite)

---

## 🔍 Points de Surveillance

### Métriques de Performance
- **Ratio Spatialite/OGR** : Devrait augmenter (plus de cas traités par Spatialite)
- **Taux d'erreurs RTTOPO** : Devrait diminuer (~80-90% de réduction estimée)
- **Temps moyen de filtrage** : Devrait diminuer (moins de fallbacks OGR)

### Logs à Surveiller
```bash
# Succès de la détection précoce
grep "already valid - skipping MakeValid" filtermate.log

# GeometryCollection gérés proactivement
grep "GeometryCollection detected" filtermate.log

# Simplifications préventives
grep "using SQL SimplifyPreserveTopology" filtermate.log

# Erreurs RTTOPO résiduelles (devrait être rare)
grep "RTTOPO error" filtermate.log
```

### Cas Limites
- **Très grandes géométries** (> 100KB WKT) : Simplification agressive, possible perte de précision
- **GeometryCollection vides** : Nécessite validation supplémentaire
- **Géométries auto-intersectantes** : MakeValid() peut échouer même après simplification

---

## 📝 Notes de Version

### Changelog Entry (v2.9.28)
```markdown
### Fixed
- **Spatialite RTTOPO Errors**: Improved handling of complex geometries to prevent
  "MakeValid error - RTTOPO reports: Unknown Reason"
  - Reduced SQL simplification threshold from 50KB to 30KB
  - Auto-detect already-valid geometries to skip unnecessary MakeValid()
  - Force simplification for GeometryCollection types
  - Better error detection and automatic OGR fallback
  - Improved logging for debugging RTTOPO issues

### Performance
- Faster filtering for simple geometries (skip MakeValid when not needed)
- Fewer OGR fallbacks due to proactive simplification
- Better handling of multi-polygon selections (zones_drop, zones_mro, etc.)
```

---

## 🔗 Références

- **Issue** : Logs du 2026-01-07 11:21-11:22
- **Fichiers modifiés** : `modules/backends/spatialite_backend.py`
- **Lignes** : ~2200-2260 (build_expression), ~3290-3310 (error handling), ~1625-1680 (source table)
- **Tests recommandés** : 
  - Filtrage avec multi-sélection de polygones complexes
  - GeometryCollection de zones administratives
  - WKT > 30KB (communes détaillées, etc.)

---

**Auteur** : GitHub Copilot  
**Validation** : Tests requis sur jeux de données réels (bdd_import.gpkg)
