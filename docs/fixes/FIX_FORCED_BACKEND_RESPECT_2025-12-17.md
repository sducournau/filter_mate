# Fix: Respect du backend forcé par l'utilisateur

**Date**: 2025-12-17  
**Issue**: Lorsqu'un backend est forcé pour un layer, le système peut retomber sur OGR au lieu d'utiliser le backend choisi  
**Solution**: Modification de `BackendFactory.get_backend()` pour respecter strictement le choix de l'utilisateur

## Problème identifié

Dans la version précédente, lorsqu'un utilisateur forçait un backend spécifique pour un layer via l'interface :

1. Le backend forcé était bien transmis via `forced_backends` dans les paramètres de tâche
2. Dans `BackendFactory.get_backend()`, le backend était créé
3. **PROBLÈME** : Si `backend.supports_layer(layer)` retournait `False`, le système retombait automatiquement sur OGR
4. Le choix explicite de l'utilisateur n'était pas respecté

### Exemple de comportement problématique

```python
# Ancien code dans BackendFactory.get_backend()
if forced_backend == 'postgresql' and POSTGRESQL_AVAILABLE:
    backend = PostgreSQLGeometricFilter(task_params)
    if backend.supports_layer(layer):
        return backend
    else:
        logger.warning(f"Forced PostgreSQL backend not available for {layer.name()}, falling back to OGR")
        backend = OGRGeometricFilter(task_params)  # ❌ Fallback automatique
        return backend
```

## Solution implémentée

Le nouveau code respecte **strictement** le backend forcé par l'utilisateur :

```python
# Nouveau code dans BackendFactory.get_backend()
if forced_backend == 'postgresql':
    if not POSTGRESQL_AVAILABLE:
        logger.warning(
            f"⚠️ PostgreSQL backend forced for '{layer.name()}' but psycopg2 not available. "
            f"Install psycopg2 to use PostgreSQL backend."
        )
    backend = PostgreSQLGeometricFilter(task_params)
    if not backend.supports_layer(layer):
        logger.warning(
            f"⚠️ PostgreSQL backend forced for '{layer.name()}' but layer type may not be fully supported. "
            f"Proceeding with forced backend as requested."
        )
    return backend  # ✅ Retourne le backend forcé dans tous les cas
```

## Changements apportés

### 1. `modules/backends/factory.py` - Méthode `BackendFactory.get_backend()`

**Modification de la logique PRIORITY 1 (backend forcé) :**

- ✅ Suppression du fallback automatique vers OGR
- ✅ Le backend forcé est **toujours** retourné, même si `supports_layer()` retourne `False`
- ✅ Ajout d'avertissements clairs pour informer l'utilisateur des problèmes potentiels
- ✅ Gestion spéciale pour PostgreSQL quand `psycopg2` n'est pas disponible

**Comportement par backend :**

#### PostgreSQL forcé
- Si `psycopg2` non disponible → avertissement mais création du backend quand même
- Si layer non supporté → avertissement mais utilisation du backend forcé
- Le backend gère l'erreur de manière gracieuse si nécessaire

#### Spatialite forcé
- Si layer non supporté → avertissement mais utilisation du backend forcé
- Le backend gère l'erreur de manière gracieuse si nécessaire

#### OGR forcé
- Toujours utilisé (OGR supporte tous les types de layers via QGIS processing)
- Message de confirmation

## Tests manuels à effectuer

1. **Test avec PostgreSQL forcé sur layer PostgreSQL valide**
   ```
   Résultat attendu: Backend PostgreSQL utilisé ✅
   ```

2. **Test avec PostgreSQL forcé sur layer Shapefile**
   ```
   Résultat attendu: 
   - Avertissement dans les logs
   - Backend PostgreSQL créé quand même
   - Erreur gracieuse lors de l'exécution
   ```

3. **Test avec PostgreSQL forcé sans psycopg2**
   ```
   Résultat attendu:
   - Avertissement "psycopg2 not available"
   - Backend créé quand même
   - Erreur gracieuse lors de l'exécution
   ```

4. **Test avec Spatialite forcé sur GeoPackage**
   ```
   Résultat attendu: Backend Spatialite utilisé ✅
   ```

5. **Test avec Spatialite forcé sur PostgreSQL**
   ```
   Résultat attendu:
   - Avertissement dans les logs
   - Backend Spatialite créé quand même
   - Erreur ou comportement dégradé
   ```

6. **Test avec OGR forcé sur tous types de layers**
   ```
   Résultat attendu: Backend OGR toujours utilisé ✅
   ```

## Logs attendus

### Cas nominal (backend forcé et supporté)
```
🔒 Using forced backend 'POSTGRESQL' for layer 'my_layer'
✓ Using backend: postgresql
```

### Cas avec avertissement (backend forcé mais partiellement supporté)
```
🔒 Using forced backend 'SPATIALITE' for layer 'postgis_layer'
⚠️ Spatialite backend forced for 'postgis_layer' but layer type may not be fully supported. 
   Proceeding with forced backend as requested.
```

### Cas avec erreur (psycopg2 manquant)
```
🔒 Using forced backend 'POSTGRESQL' for layer 'my_layer'
⚠️ PostgreSQL backend forced for 'my_layer' but psycopg2 not available. 
   Install psycopg2 to use PostgreSQL backend.
```

## Impact sur l'interface utilisateur

Le sélecteur de backend dans l'interface continue de fonctionner comme avant :
- L'utilisateur peut forcer un backend via le dropdown
- Le backend choisi sera **toujours** utilisé
- Des messages d'avertissement/erreur appropriés apparaîtront si le backend n'est pas optimal

## Recommandations futures

1. **Tests unitaires à ajouter** :
   - Test pour backend forcé avec layer supporté
   - Test pour backend forcé avec layer non supporté
   - Test pour PostgreSQL forcé sans psycopg2

2. **Amélioration UI possible** :
   - Désactiver les options de backend non disponibles dans le dropdown
   - Afficher un tooltip expliquant pourquoi un backend n'est pas disponible
   - Colorer les backends forcés mais non optimaux dans l'interface

3. **Documentation utilisateur** :
   - Ajouter une section dans le README expliquant les backends
   - Documenter quand forcer un backend est utile
   - Expliquer les messages d'avertissement possibles

## Conformité avec les guidelines

✅ Suit les conventions PEP 8  
✅ Messages de log clairs et informatifs  
✅ Gestion d'erreur gracieuse  
✅ Respect du choix utilisateur  
✅ Backward compatible  
✅ Pas de régression sur le comportement automatique (quand aucun backend n'est forcé)

## Fichiers modifiés

- `modules/backends/factory.py` : Méthode `BackendFactory.get_backend()` (lignes 248-282)

## Commit suggéré

```
fix: Respect strict backend choice when forced by user

When user explicitly forces a backend for a layer via the UI,
the system now strictly uses that backend instead of falling
back to OGR when supports_layer() returns False.

Adds appropriate warnings to inform user if forced backend
may not be optimal for the layer type.

Fixes issue where forced backend selection was ignored in
certain scenarios.

- Modified: modules/backends/factory.py
- Added: docs/fixes/FIX_FORCED_BACKEND_RESPECT_2025-12-17.md
```
