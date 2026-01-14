# Plan d'Action - Régressions FilterMate v4.0

> **Date**: 14 Janvier 2026  
> **Version**: 4.0-alpha  
> **Criticité Globale**: ⚠️ MOYENNE (1 méthode critique, 1 gap non bloquant)

---

## 📋 Résumé Exécutif

### Régressions Identifiées

| # | Fichier | Problème | Criticité | Effort |
|---|---------|----------|-----------|--------|
| **1** | `infrastructure/database/prepared_statements.py` | Méthode `delete_subset_history()` manquante | 🔴 CRITIQUE | 30 min |
| **2** | `infrastructure/cache/` | WKTCache non migré (402 lignes) | 🟡 FAIBLE | 2h |
| **3** | `prepared_statements.py` | 3 méthodes secondaires manquantes | ⚪ TRÈS FAIBLE | 1h |

### Impact

1. **Critique**: `delete_subset_history()` est appelé dans `filter_task.py` lignes 3966 et 4004. Sans cette méthode, le code va lever une `AttributeError` lors du reset des filtres.

2. **Faible**: WKTCache n'est plus utilisé dans la nouvelle architecture. Les constantes existent (`infrastructure/constants.py`) mais pas la classe. Si le cache WKT était utilisé dans Spatialite backend, il faut le migrer.

3. **Très Faible**: `insert_layer_properties()`, `delete_layer_properties()`, `update_layer_property()` ne sont pas utilisés dans le code actuel.

---

## 🔧 TÂCHE 1: Ajouter `delete_subset_history()` (CRITIQUE)

### Contexte

```python
# core/tasks/filter_task.py:3966
delete_history_fn = self._ps_manager.delete_subset_history  # AttributeError!

# core/tasks/filter_task.py:4004
self._ps_manager.delete_subset_history(self.project_uuid, layer.id())  # AttributeError!
```

### Implémentation

**Fichier**: `infrastructure/database/prepared_statements.py`

```python
# Ajouter dans la classe abstraite PreparedStatementManager (ligne ~50)
@abstractmethod
def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
    """Delete subset history records for a layer."""
    pass

# Ajouter dans PostgreSQLPreparedStatements (après insert_subset_history)
def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
    """Delete subset history using prepared statement."""
    try:
        cursor = self.connection.cursor()
        cursor.execute(
            "DELETE FROM fm_subset_history WHERE fk_project = %s AND layer_id = %s",
            (project_uuid, layer_id)
        )
        self.connection.commit()
        return True
    except Exception as e:
        logger.warning(f"PostgreSQL delete_subset_history failed: {e}")
        return False

# Ajouter dans SpatialitePreparedStatements (après insert_subset_history)
def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
    """Delete subset history using parameterized query."""
    try:
        cursor = self.connection.cursor()
        cursor.execute(
            "DELETE FROM fm_subset_history WHERE fk_project = ? AND layer_id = ?",
            (project_uuid, layer_id)
        )
        self.connection.commit()
        return True
    except Exception as e:
        logger.warning(f"Spatialite delete_subset_history failed: {e}")
        return False

# Ajouter dans NullPreparedStatements
def delete_subset_history(self, project_uuid: str, layer_id: str) -> bool:
    """Return False to indicate fallback to direct SQL."""
    return False
```

### Validation

```bash
# Après modification, vérifier les erreurs
cd /path/to/filter_mate
python -c "from infrastructure.database.prepared_statements import *; print('OK')"

# Test fonctionnel
# 1. Charger QGIS
# 2. Appliquer un filtre sur une couche PostgreSQL/Spatialite
# 3. Reset le filtre
# 4. Vérifier qu'aucune erreur n'apparaît
```

---

## 🔧 TÂCHE 2: Évaluer WKTCache (FAIBLE PRIORITÉ)

### Analyse

| Aspect | before_migration | v4.0 |
|--------|-----------------|------|
| **Fichier** | `modules/backends/wkt_cache.py` | ❌ Absent |
| **Utilisation** | `spatialite_backend.py` | Non utilisé |
| **Constantes** | ✅ Présentes | ✅ Migrées vers `infrastructure/constants.py` |

### Conclusion

**WKTCache n'est PAS une régression bloquante** car:
1. Le nouveau backend Spatialite (`adapters/backends/spatialite/`) n'utilise pas WKTCache
2. `SourceGeometryCache` (`infrastructure/cache/geometry_cache.py`) remplace probablement cette fonctionnalité
3. Aucune référence à `wkt_cache` dans `core/` ou `adapters/`

### Recommandation

**Ne pas migrer WKTCache** sauf si des problèmes de performance sont constatés sur Spatialite.

Si migration nécessaire plus tard:
```
infrastructure/cache/wkt_cache.py  ← Créer ce fichier
```

---

## 🔧 TÂCHE 3: Méthodes secondaires (TRÈS FAIBLE PRIORITÉ)

### Méthodes concernées

| Méthode | Usage actuel | Recommandation |
|---------|--------------|----------------|
| `insert_layer_properties()` | Non utilisée | Ignorer |
| `delete_layer_properties()` | Non utilisée | Ignorer |
| `update_layer_property()` | Non utilisée (différent de state_manager) | Ignorer |

### Recommandation

**Ne pas implémenter** ces méthodes car elles ne sont pas utilisées dans le code actuel. Les ajouter plus tard si besoin.

---

## ✅ Ordre d'Exécution

```
┌─────────────────────────────────────────────────────────────┐
│ PRIORITÉ 1 (IMMÉDIAT) - 30 minutes                         │
│ ─────────────────────────────────────────────────────────── │
│ ✓ Ajouter delete_subset_history() à prepared_statements.py │
│   - PreparedStatementManager (abstract)                     │
│   - PostgreSQLPreparedStatements                            │
│   - SpatialitePreparedStatements                            │
│   - NullPreparedStatements                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ PRIORITÉ 2 (OPTIONNEL) - Post-déploiement                  │
│ ─────────────────────────────────────────────────────────── │
│ ○ Surveiller performances Spatialite                        │
│ ○ Migrer WKTCache SI problèmes constatés                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ PRIORITÉ 3 (BACKLOG) - Jamais si non utilisé               │
│ ─────────────────────────────────────────────────────────── │
│ ○ insert_layer_properties()                                 │
│ ○ delete_layer_properties()                                 │
│ ○ update_layer_property()                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Récapitulatif des Changements Requis

### Fichier à modifier

| Fichier | Action | Lignes à ajouter |
|---------|--------|------------------|
| `infrastructure/database/prepared_statements.py` | Modifier | ~35 lignes |

### Code complet à insérer

Voir section [TÂCHE 1](#-tâche-1-ajouter-delete_subset_history-critique) pour le code exact.

---

## 🧪 Tests de Régression

### Test 1: Import du module

```python
from infrastructure.database.prepared_statements import (
    PreparedStatementManager,
    PostgreSQLPreparedStatements,
    SpatialitePreparedStatements,
    NullPreparedStatements,
    create_prepared_statements
)

# Vérifier que delete_subset_history existe
assert hasattr(PreparedStatementManager, 'delete_subset_history')
assert hasattr(PostgreSQLPreparedStatements, 'delete_subset_history')
assert hasattr(SpatialitePreparedStatements, 'delete_subset_history')
assert hasattr(NullPreparedStatements, 'delete_subset_history')
```

### Test 2: Fonctionnel dans QGIS

1. Ouvrir QGIS avec projet contenant couches PostgreSQL
2. Appliquer un filtre spatial
3. Réinitialiser le filtre (bouton Reset)
4. Vérifier que le reset fonctionne sans erreur

---

## 📝 Conclusion

**La régression la plus critique est l'absence de `delete_subset_history()`**. 

Cette méthode doit être implémentée **immédiatement** car elle est activement appelée dans `filter_task.py` et provoquera une `AttributeError` lors de l'utilisation du reset filter.

**Effort total estimé: 30 minutes**

Les autres éléments identifiés (WKTCache, méthodes layer_properties) ne sont pas bloquants et peuvent être ignorés pour le moment.
