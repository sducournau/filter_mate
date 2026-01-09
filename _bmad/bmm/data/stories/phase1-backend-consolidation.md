# 📋 Phase 1: Backend Consolidation - User Stories

> **Epic**: Legacy Removal Phase 1  
> **Version**: v3.1 → v3.2  
> **Status**: 📋 PLANNED

---

## 🎯 Sprint 10: Backend Base & Factory

### DEP-001: Migrate Base Backend to Adapters

**Priority**: 🔴 P0  
**Estimated**: 4h  
**Dependencies**: None

#### Description

Migrer `modules/backends/base_backend.py` vers `adapters/backends/base.py` en conservant la compatibilité.

#### Acceptance Criteria

- [ ] `adapters/backends/base.py` créé avec toutes les méthodes
- [ ] Interface `BackendPort` respectée
- [ ] `user_warnings` pattern (v3.0.21) inclus
- [ ] Tests unitaires migrés
- [ ] Façade legacy créée dans `modules/backends/base_backend.py`
- [ ] Warning de dépréciation émis sur import legacy

#### Technical Notes

```python
# modules/backends/base_backend.py (façade)
import warnings
warnings.warn(
    "modules.backends.base_backend is deprecated. "
    "Use adapters.backends.base instead.",
    DeprecationWarning, stacklevel=2
)
from adapters.backends.base import GeometricFilterBackend
__all__ = ['GeometricFilterBackend']
```

---

### DEP-002: Migrate PostgreSQL Backend

**Priority**: 🔴 P0  
**Estimated**: 8h  
**Dependencies**: DEP-001

#### Description

Migrer et refactorer `modules/backends/postgresql_backend.py` (3500+ lignes) vers `adapters/backends/postgresql/`.

#### Acceptance Criteria

- [ ] Structure créée: `adapters/backends/postgresql/`
  - [ ] `__init__.py`
  - [ ] `backend.py` (< 800 lignes)
  - [ ] `expression_builder.py`
  - [ ] `mv_manager.py` (materialized views)
  - [ ] `buffer_optimizer.py`
  - [ ] `utils.py`
- [ ] Tests existants passent
- [ ] Façade legacy fonctionne
- [ ] Performance identique (benchmark)

#### Technical Notes

Split proposé:

- `backend.py`: Classe principale, apply_filter
- `expression_builder.py`: Construction SQL/PostGIS
- `mv_manager.py`: Gestion vues matérialisées
- `buffer_optimizer.py`: Optimisation buffers
- `utils.py`: Fonctions utilitaires PostgreSQL

---

### DEP-003: Migrate Spatialite Backend

**Priority**: 🔴 P0  
**Estimated**: 6h  
**Dependencies**: DEP-001

#### Description

Migrer `modules/backends/spatialite_backend.py` (2500+ lignes) vers `adapters/backends/spatialite/`.

#### Acceptance Criteria

- [ ] Structure créée: `adapters/backends/spatialite/`
  - [ ] `__init__.py`
  - [ ] `backend.py` (< 800 lignes)
  - [ ] `expression_builder.py`
  - [ ] `geometry_utils.py`
  - [ ] `cache.py`
- [ ] Tests existants passent
- [ ] Fallback OGR fonctionne
- [ ] Façade legacy fonctionne

---

### DEP-004: Migrate OGR Backend

**Priority**: 🔴 P0  
**Estimated**: 8h  
**Dependencies**: DEP-001

#### Description

Migrer `modules/backends/ogr_backend.py` (3500 lignes) vers `adapters/backends/ogr/`.

#### Acceptance Criteria

- [ ] Structure créée: `adapters/backends/ogr/`
  - [ ] `__init__.py`
  - [ ] `backend.py` (< 800 lignes)
  - [ ] `multi_step_optimizer.py`
  - [ ] `spatial_index.py`
  - [ ] `expression_builder.py`
- [ ] `add_user_warning()` pattern (v3.0.21) conservé
- [ ] Tests existants passent
- [ ] Façade legacy fonctionne

---

### DEP-005: Migrate Memory Backend

**Priority**: 🟡 P2  
**Estimated**: 2h  
**Dependencies**: DEP-001

#### Description

Migrer `modules/backends/memory_backend.py` vers `adapters/backends/memory/`.

#### Acceptance Criteria

- [ ] `adapters/backends/memory/backend.py` créé
- [ ] Tests migrés
- [ ] Façade legacy

---

## 🎯 Sprint 11: Backend Helpers & Cache

### DEP-010: Migrate Cache Helpers

**Priority**: 🟠 P1  
**Estimated**: 4h  
**Dependencies**: DEP-001

#### Description

Migrer les utilitaires de cache backend vers `infrastructure/cache/`.

#### Acceptance Criteria

- [ ] `infrastructure/cache/helpers.py` créé
- [ ] `infrastructure/cache/wkt_cache.py` créé
- [ ] `infrastructure/cache/spatialite_cache.py` créé
- [ ] Tests migrés
- [ ] Façades legacy

---

### DEP-011: Migrate MV Registry

**Priority**: 🟠 P1  
**Estimated**: 3h  
**Dependencies**: DEP-002

#### Description

Migrer `modules/backends/mv_registry.py` vers `adapters/backends/postgresql/mv_registry.py`.

#### Acceptance Criteria

- [ ] Fichier migré
- [ ] Intégration avec PostgreSQL backend
- [ ] Tests migrés

---

### DEP-012: Migrate Spatial Index Manager

**Priority**: 🟠 P1  
**Estimated**: 3h  
**Dependencies**: DEP-001

#### Description

Migrer `modules/backends/spatial_index_manager.py` vers `adapters/backends/spatial_index.py`.

#### Acceptance Criteria

- [ ] Utilitaire partagé entre backends
- [ ] Tests migrés

---

### DEP-013: Migrate Optimizer Metrics

**Priority**: 🟡 P2  
**Estimated**: 2h  
**Dependencies**: None

#### Description

Migrer `modules/backends/optimizer_metrics.py` vers `core/domain/optimizer_metrics.py`.

#### Acceptance Criteria

- [ ] Domain object créé
- [ ] Utilisé par services

---

### DEP-014: Migrate Multi-Step Optimizer

**Priority**: 🟠 P1  
**Estimated**: 4h  
**Dependencies**: DEP-004

#### Description

Migrer `modules/backends/multi_step_optimizer.py` vers `adapters/backends/ogr/multi_step_optimizer.py`.

#### Acceptance Criteria

- [ ] Intégré à OGR backend
- [ ] Tests migrés
- [ ] Performance identique

---

## 🎯 Sprint 12: Integration & Cleanup

### DEP-020: Update Backend Factory

**Priority**: 🔴 P0  
**Estimated**: 4h  
**Dependencies**: DEP-002, DEP-003, DEP-004, DEP-005

#### Description

Mettre à jour `adapters/backends/factory.py` pour utiliser les nouveaux backends.

#### Acceptance Criteria

- [ ] Factory utilise `adapters/backends/*/backend.py`
- [ ] Pas de référence à `modules/backends/`
- [ ] Tests d'intégration passent

---

### DEP-021: Create Legacy Facades

**Priority**: 🔴 P0  
**Estimated**: 3h  
**Dependencies**: DEP-020

#### Description

Créer façades dans `modules/backends/` qui redirigent vers `adapters/backends/`.

#### Acceptance Criteria

- [ ] Chaque fichier legacy émet warning et redirige
- [ ] Code existant continue de fonctionner
- [ ] Warnings visibles dans logs

---

### DEP-022: Regression Testing

**Priority**: 🔴 P0  
**Estimated**: 4h  
**Dependencies**: DEP-021

#### Description

Exécuter suite complète de tests de régression.

#### Acceptance Criteria

- [ ] CRIT-005 (ComboBox) passe
- [ ] CRIT-006 (Memory Leak) passe
- [ ] Tests E2E passent
- [ ] Benchmarks OK (pas de régression > 5%)

---

### DEP-023: Documentation Update

**Priority**: 🟠 P1  
**Estimated**: 2h  
**Dependencies**: DEP-022

#### Description

Mettre à jour documentation pour refléter nouvelle structure.

#### Acceptance Criteria

- [ ] `docs/architecture-v3.md` mis à jour
- [ ] `docs/migration-v3.md` mis à jour
- [ ] API reference mis à jour
- [ ] README mis à jour

---

## 📊 Résumé Phase 1

| Sprint    | Stories           | Effort Total | Status     |
| --------- | ----------------- | ------------ | ---------- |
| Sprint 10 | DEP-001 à DEP-005 | 28h          | 📋 Planned |
| Sprint 11 | DEP-010 à DEP-014 | 16h          | 📋 Planned |
| Sprint 12 | DEP-020 à DEP-023 | 13h          | 📋 Planned |
| **Total** | **14 stories**    | **57h**      | -          |

---

## 🔗 Dépendances

```
DEP-001 (Base Backend)
    ├── DEP-002 (PostgreSQL)
    │   └── DEP-011 (MV Registry)
    ├── DEP-003 (Spatialite)
    ├── DEP-004 (OGR)
    │   └── DEP-014 (Multi-Step)
    ├── DEP-005 (Memory)
    ├── DEP-010 (Cache Helpers)
    └── DEP-012 (Spatial Index)

DEP-013 (Optimizer Metrics) → Standalone

DEP-020 (Factory Update)
    └── DEP-002, DEP-003, DEP-004, DEP-005

DEP-021 (Legacy Facades)
    └── DEP-020

DEP-022 (Regression Testing)
    └── DEP-021

DEP-023 (Documentation)
    └── DEP-022
```
