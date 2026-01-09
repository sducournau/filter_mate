# 🗺️ FilterMate Legacy Removal Roadmap

> **Version**: 1.0 | **Created**: 2026-01-09 | **Target**: v4.0.0

## 📋 Executive Summary

Ce document planifie le retrait progressif de l'ancienne architecture (`modules/`) au profit de la nouvelle architecture hexagonale (`core/`, `adapters/`, `ui/`, `infrastructure/`).

### Principes Directeurs

1. **Backward Compatibility**: Aucune rupture pour les utilisateurs jusqu'à v4.0
2. **Gradual Deprecation**: Warnings progressifs avant retrait
3. **Test Coverage**: Chaque migration doit maintenir 80%+ de couverture
4. **Documentation First**: Documenter avant de migrer

---

## 📊 État Actuel (v3.0.21)

### Nouvelle Architecture ✅ En Production

| Module                   | Fichiers | Lignes | Couverture | Status    |
| ------------------------ | -------- | ------ | ---------- | --------- |
| `core/domain/`           | 4        | ~800   | 95%        | ✅ Stable |
| `core/services/`         | 8        | ~4500  | 85%        | ✅ Stable |
| `core/ports/`            | 4        | ~600   | 90%        | ✅ Stable |
| `adapters/backends/`     | 8        | ~1200  | 80%        | ✅ Stable |
| `adapters/repositories/` | 3        | ~600   | 75%        | ✅ Stable |
| `adapters/qgis/`         | 5        | ~800   | 70%        | ✅ Stable |
| `ui/controllers/`        | 12       | ~5000  | 80%        | ✅ Stable |
| `ui/layout/`             | 5        | ~2500  | 85%        | ✅ Stable |
| `ui/styles/`             | 4        | ~1500  | 80%        | ✅ Stable |
| `ui/dialogs/`            | 4        | ~2000  | 85%        | ✅ Stable |
| `infrastructure/`        | 10       | ~2000  | 70%        | ✅ Stable |

### Ancienne Architecture ⚠️ Déprécié

| Module                  | Fichiers | Lignes | Dépendances | Priorité Retrait |
| ----------------------- | -------- | ------ | ----------- | ---------------- |
| `modules/appTasks.py`   | 1        | ~3000  | 15+         | 🔴 Phase 1       |
| `modules/backends/*.py` | 10       | ~12000 | Core        | 🔴 Phase 1       |
| `modules/tasks/*.py`    | 15       | ~15000 | Core        | 🟠 Phase 2       |
| `modules/appUtils.py`   | 1        | ~2500  | 20+         | 🟠 Phase 2       |
| `modules/*.py` (autres) | 25       | ~8000  | Various     | 🟡 Phase 3       |

---

## 🎯 Plan de Retrait en 4 Phases

### Phase 1: Backends Consolidation (v3.1 → v3.2)

**Durée estimée**: 2-3 semaines
**Objectif**: Consolider les backends dans `adapters/backends/`

#### 1.1 Migration des Backends Legacy

| Fichier Source                           | Destination                               | Tâches            | Status  |
| ---------------------------------------- | ----------------------------------------- | ----------------- | ------- |
| `modules/backends/base_backend.py`       | `adapters/backends/base.py`               | Adapter interface | ⏳ TODO |
| `modules/backends/postgresql_backend.py` | `adapters/backends/postgresql/backend.py` | Split + refactor  | ⏳ TODO |
| `modules/backends/spatialite_backend.py` | `adapters/backends/spatialite/backend.py` | Split + refactor  | ⏳ TODO |
| `modules/backends/ogr_backend.py`        | `adapters/backends/ogr/backend.py`        | Split + refactor  | ⏳ TODO |
| `modules/backends/memory_backend.py`     | `adapters/backends/memory/backend.py`     | Simple move       | ⏳ TODO |
| `modules/backends/factory.py`            | ✅ Déjà migré                             | -                 | ✅ DONE |

#### 1.2 Migration des Helpers Backends

| Fichier Source                              | Destination                                   | Notes            |
| ------------------------------------------- | --------------------------------------------- | ---------------- |
| `modules/backends/cache_helpers.py`         | `infrastructure/cache/helpers.py`             | Cache utilities  |
| `modules/backends/wkt_cache.py`             | `infrastructure/cache/wkt_cache.py`           | WKT caching      |
| `modules/backends/spatialite_cache.py`      | `infrastructure/cache/spatialite_cache.py`    | Spatialite cache |
| `modules/backends/mv_registry.py`           | `adapters/backends/postgresql/mv_registry.py` | MV management    |
| `modules/backends/optimizer_metrics.py`     | `core/domain/optimizer_metrics.py`            | Domain object    |
| `modules/backends/spatial_index_manager.py` | `adapters/backends/spatial_index.py`          | Shared utility   |

#### 1.3 Critères de Validation Phase 1

- [ ] Tous les backends migrent vers `adapters/backends/`
- [ ] Tests de régression passent (CRIT-005, CRIT-006)
- [ ] Aucune régression de performance (benchmark)
- [ ] Imports legacy émettent des warnings

---

### Phase 2: Tasks Consolidation (v3.2 → v3.3)

**Durée estimée**: 3-4 semaines
**Objectif**: Consolider les tâches dans `adapters/qgis/tasks/`

#### 2.1 Analyse des Dépendances filter_task.py

Le fichier `modules/tasks/filter_task.py` (12700+ lignes) est le plus complexe.
Stratégie: **Strangler Fig Pattern** - encapsuler puis remplacer progressivement.

```
filter_task.py (12700 lines)
├── FilterTask class (~2000 lines)
│   ├── __init__, run, finished → adapters/qgis/tasks/filter_task.py
│   ├── execute_filtering → core/services/filter_service.py
│   ├── execute_exporting → core/services/export_service.py
│   └── _apply_filter_* → Backend delegation
├── Expression building (~3000 lines)
│   └── → core/services/expression_service.py
├── Optimization logic (~2000 lines)
│   └── → core/services/optimization_service.py
├── Caching logic (~1500 lines)
│   └── → infrastructure/cache/filter_cache.py
├── PostgreSQL specific (~2000 lines)
│   └── → adapters/backends/postgresql/
└── Error handling, logging (~2200 lines)
    └── → infrastructure/logging/, core/domain/errors.py
```

#### 2.2 Tasks à Migrer

| Fichier Source                           | Destination                              | Complexité | Dépendances |
| ---------------------------------------- | ---------------------------------------- | ---------- | ----------- |
| `modules/tasks/filter_task.py`           | Split multi-fichiers                     | 🔴 Élevée  | 20+         |
| `modules/tasks/layer_management_task.py` | `adapters/qgis/tasks/`                   | 🟠 Moyenne | 10          |
| `modules/tasks/multi_step_filter.py`     | `core/services/multi_step_service.py`    | 🟠 Moyenne | 5           |
| `modules/tasks/progressive_filter.py`    | `core/services/progressive_service.py`   | 🟡 Basse   | 3           |
| `modules/tasks/task_utils.py`            | `adapters/qgis/tasks/utils.py`           | 🟡 Basse   | 5           |
| `modules/tasks/geometry_cache.py`        | `infrastructure/cache/geometry_cache.py` | 🟡 Basse   | 2           |
| `modules/tasks/query_cache.py`           | `infrastructure/cache/query_cache.py`    | 🟡 Basse   | 2           |

#### 2.3 Critères de Validation Phase 2

- [ ] FilterTask < 1000 lignes (délégation aux services)
- [ ] Tests unitaires pour chaque nouveau service
- [ ] Performance identique ou meilleure
- [ ] Documentation API mise à jour

---

### Phase 3: Utilities Migration (v3.3 → v3.4)

**Durée estimée**: 2 semaines
**Objectif**: Migrer les utilitaires vers `infrastructure/`

#### 3.1 Fichiers à Migrer

| Fichier Source               | Destination                        | Notes               |
| ---------------------------- | ---------------------------------- | ------------------- |
| `modules/appUtils.py`        | Split → voir ci-dessous            | God class           |
| `modules/crs_utils.py`       | `infrastructure/utils/crs.py`      | CRS handling        |
| `modules/geometry_safety.py` | `infrastructure/utils/geometry.py` | Geometry validation |
| `modules/type_utils.py`      | `infrastructure/utils/types.py`    | Type helpers        |
| `modules/object_safety.py`   | `infrastructure/utils/safety.py`   | Object safety       |
| `modules/signal_utils.py`    | `ui/signals/utils.py`              | Signal helpers      |
| `modules/feedback_utils.py`  | `infrastructure/feedback/utils.py` | User feedback       |
| `modules/icon_utils.py`      | `ui/styles/icons.py`               | Icon management     |
| `modules/logging_config.py`  | `infrastructure/logging/config.py` | Logging setup       |

#### 3.2 Split de appUtils.py

```
appUtils.py (~2500 lines)
├── Database connections → adapters/database_manager.py ✅ DONE
├── Layer utilities → adapters/layer_validator.py ✅ DONE
├── Provider detection → infrastructure/utils/provider.py
├── Expression helpers → core/services/expression_service.py
├── Geometry utilities → infrastructure/utils/geometry.py
├── PostgreSQL specific → adapters/backends/postgresql/utils.py
└── Constants → modules/constants.py → core/domain/constants.py
```

---

### Phase 4: Final Cleanup (v3.4 → v4.0)

**Durée estimée**: 1 semaine
**Objectif**: Supprimer `modules/` et finaliser

#### 4.1 Dernières Migrations

| Fichier Source                | Action                        | Notes              |
| ----------------------------- | ----------------------------- | ------------------ |
| `modules/__init__.py`         | Garder comme façade           | Émet warnings      |
| `modules/constants.py`        | → `core/domain/constants.py`  | Constants globales |
| `modules/customExceptions.py` | → `core/domain/exceptions.py` | Exceptions         |
| `modules/widgets.py`          | → `ui/widgets/legacy.py`      | Legacy widgets     |
| `modules/ui_*.py`             | → `ui/`                       | UI utilities       |
| `modules/config_*.py`         | → `config/`                   | Config modules     |

#### 4.2 Actions Finales v4.0

- [ ] Supprimer `modules/backends/` (remplacé par `adapters/backends/`)
- [ ] Supprimer `modules/tasks/` (remplacé par `adapters/qgis/tasks/`)
- [ ] Archiver `modules/` → `_legacy/modules/` (référence)
- [ ] Mettre à jour tous les imports
- [ ] Supprimer warnings de dépréciation
- [ ] Release Notes v4.0

---

## 📅 Timeline Proposée

```
v3.0.21 (Current)
    │
    ├── v3.1.0 (2026-Q1)
    │   └── Phase 1 Start: Backend consolidation
    │
    ├── v3.2.0 (2026-Q2)
    │   ├── Phase 1 Complete
    │   └── Phase 2 Start: Tasks consolidation
    │
    ├── v3.3.0 (2026-Q2)
    │   ├── Phase 2 Complete
    │   └── Phase 3 Start: Utilities migration
    │
    ├── v3.4.0 (2026-Q3)
    │   ├── Phase 3 Complete
    │   └── Phase 4 Start: Final cleanup
    │
    └── v4.0.0 (2026-Q3)
        ├── Phase 4 Complete
        ├── modules/ removed
        └── 🎉 Migration Complete!
```

---

## 🔧 Outils de Migration

### 1. Script de Détection des Imports Legacy

```python
# tools/check_legacy_imports.py
"""Détecte les imports depuis modules/ dans le code."""

import ast
import os

LEGACY_PATTERNS = [
    'from modules.',
    'import modules.',
    'from ..backends.',  # Relative imports in modules/
]

def check_file(filepath):
    with open(filepath) as f:
        content = f.read()

    issues = []
    for i, line in enumerate(content.split('\n'), 1):
        for pattern in LEGACY_PATTERNS:
            if pattern in line:
                issues.append((i, line.strip()))
    return issues
```

### 2. Script de Migration Automatique

```python
# tools/migrate_imports.py
"""Migre automatiquement les imports legacy vers la nouvelle architecture."""

MIGRATION_MAP = {
    'modules.backends.factory': 'adapters.backends.factory',
    'modules.backends.postgresql_backend': 'adapters.backends.postgresql.backend',
    'modules.appUtils': 'adapters.database_manager',
    # ... etc
}

def migrate_file(filepath):
    with open(filepath) as f:
        content = f.read()

    for old, new in MIGRATION_MAP.items():
        content = content.replace(f'from {old}', f'from {new}')
        content = content.replace(f'import {old}', f'import {new}')

    with open(filepath, 'w') as f:
        f.write(content)
```

---

## 📊 Métriques de Succès

### Par Phase

| Phase | Métrique                | Objectif | Mesure       |
| ----- | ----------------------- | -------- | ------------ |
| 1     | Backends dans adapters/ | 100%     | Count files  |
| 2     | filter_task.py lines    | < 1000   | wc -l        |
| 3     | modules/\*.py count     | < 10     | ls count     |
| 4     | Legacy imports          | 0        | Script check |

### Globales

| Métrique              | Avant  | Objectif | Status |
| --------------------- | ------ | -------- | ------ |
| Lignes dans modules/  | ~40000 | 0        | ⏳     |
| Lignes dans core/     | ~6000  | 8000     | ✅     |
| Lignes dans adapters/ | ~3500  | 6000     | ⏳     |
| Test coverage         | 70%    | 85%      | ⏳     |
| Fichiers > 800 lignes | 8      | 0        | ⏳     |

---

## ⚠️ Risques et Mitigations

| Risque                        | Impact    | Probabilité | Mitigation                   |
| ----------------------------- | --------- | ----------- | ---------------------------- |
| Régression fonctionnelle      | 🔴 Élevé  | Moyenne     | Tests E2E avant chaque phase |
| Dégradation performance       | 🟠 Moyen  | Basse       | Benchmarks automatisés       |
| Breaking changes API          | 🔴 Élevé  | Basse       | Semver strict, façades       |
| Incompatibilité plugins tiers | 🟡 Faible | Très basse  | Documentation, warnings      |

---

## 📚 Références

- [Architecture v3](../../../docs/architecture-v3.md)
- [Migration Guide](../../../docs/migration-v3.md)
- [Kanban Board](./migration-kanban.md)
- [God Class Analysis - FilterMateApp](../../../docs/GOD_CLASS_ANALYSIS_FilterMateApp.md)
- [God Class Analysis - DockWidget](../../../docs/DOCKWIDGET_GOD_CLASS_ANALYSIS.md)
