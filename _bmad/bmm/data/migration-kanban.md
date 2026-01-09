# 📋 FilterMate v3.0 Migration - Kanban Board

**Epic:** Migration Architecture Hexagonale  
**Sprint Actuel:** ✅ Phase 6 COMPLETE - Migration Terminée!  
**Dernière MAJ:** 2026-01-09 (Phase 6 terminée, stories archivées)

---

## 🎉 MIGRATION V3 COMPLÈTE

Toutes les stories ont été complétées et archivées. Voir `_archive/` pour l'historique.

---

## 🎯 Tableau Kanban

### 📥 BACKLOG (Post-Migration)

| ID      | Story               | Priorité | Phase | Notes     |
| ------- | ------------------- | -------- | ----- | --------- |
| MIG-004 | CI/CD Configuration | 🟡 P2    | Post  | Optionnel |

#### Phase 6: God Class DockWidget (30 stories) ✅ COMPLETE

##### Sprint 6 - Layout & Styling (9 stories) ✅ COMPLETE

| ID      | Story                   | Priorité | Statut  | Notes                           |
| ------- | ----------------------- | -------- | ------- | ------------------------------- |
| MIG-060 | Layout Module Structure | 🔴 P0    | ✅ DONE | `ui/layout/` créé               |
| MIG-061 | SplitterManager         | 🟠 P1    | ✅ DONE | 370 lignes, 18 tests            |
| MIG-062 | DimensionsManager       | 🟠 P1    | ✅ DONE | 825 lignes, 11 tests ✅         |
| MIG-063 | SpacingManager          | 🟠 P1    | ✅ DONE | 337 lignes, 10 tests            |
| MIG-064 | ActionBarManager        | 🟠 P1    | ✅ DONE | 582 lignes, 16 tests            |
| MIG-065 | Styling Module          | 🔴 P0    | ✅ DONE | `ui/styles/` créé (1320 lignes) |
| MIG-066 | ThemeManager            | 🟠 P1    | ✅ DONE | ThemeManager migré              |
| MIG-067 | IconManager             | 🟠 P1    | ✅ DONE | IconThemeManager migré          |
| MIG-068 | ButtonStyler            | 🟡 P2    | ✅ DONE | ButtonStyler 400 lignes         |

##### Sprint 7 - Controllers & Services (9 stories) 🔄 EN COURS

| ID      | Story                  | Priorité | Statut  | Dépend de   | Notes                   |
| ------- | ---------------------- | -------- | ------- | ----------- | ----------------------- |
| MIG-070 | ConfigController       | 🟠 P1    | ✅ DONE | MIG-060,065 | 708 lignes, intégré     |
| MIG-071 | BackendController      | 🟠 P1    | ✅ DONE | MIG-070     | 500+ lignes, 30 tests   |
| MIG-072 | FavoritesController    | 🟠 P1    | ✅ DONE | MIG-070     | 600+ lignes, 25 tests   |
| MIG-073 | LayerSyncController    | 🟠 P1    | ✅ DONE | MIG-070     | 400 lignes, CRIT-005 ✅ |
| MIG-074 | PropertyController     | 🟡 P2    | ✅ DONE | MIG-070     | 550 lignes, 25 tests    |
| MIG-075 | BackendService         | 🟠 P1    | ✅ DONE | MIG-070     | 550 lignes, 30 tests    |
| MIG-076 | FavoritesService       | 🟠 P1    | ✅ DONE | MIG-075     | 600 lignes, 25 tests    |
| MIG-077 | LayerService           | 🟠 P1    | ✅ DONE | MIG-075     | 600 lignes, 35 tests    |
| MIG-078 | PostgresSessionManager | 🟡 P2    | ✅ DONE | MIG-075     | 600 lignes, 40 tests    |

##### Sprint 8 - Dialogs & Signals (7 stories) ✅ COMPLETE

| ID      | Story                  | Priorité | Statut  | Notes                        |
| ------- | ---------------------- | -------- | ------- | ---------------------------- |
| MIG-080 | Dialogs Module         | 🟢 P3    | ✅ DONE | `ui/dialogs/` créé           |
| MIG-081 | FavoritesManagerDialog | 🟡 P2    | ✅ DONE | 571 lignes, 17 tests         |
| MIG-082 | OptimizationDialog     | 🟡 P2    | ✅ DONE | 610 lignes, 573 lignes test  |
| MIG-083 | PostgresInfoDialog     | 🟢 P3    | ✅ DONE | 290 lignes, 480 lignes test  |
| MIG-084 | SignalManager Complet  | 🔴 P0    | ✅ DONE | 500+ lignes, 500 lignes test |
| MIG-085 | LayerSignalHandler     | 🟠 P1    | ✅ DONE | 340 lignes, 450 lignes test  |
| MIG-086 | Migrate All Signals    | 🟠 P1    | ✅ DONE | 450 lignes, 380 lignes test  |

##### Sprint 9 - Final Refactoring (3 stories) ✅ COMPLETE

| ID      | Story                   | Priorité | Statut  | Notes                       |
| ------- | ----------------------- | -------- | ------- | --------------------------- |
| MIG-087 | DockWidget Orchestrator | 🔴 P0    | ✅ DONE | 550 lignes, 450 lignes test |
| MIG-088 | Deprecation Warnings    | 🟠 P1    | ✅ DONE | 380 lignes, 400 lignes test |
| MIG-089 | Regression Testing      | 🔴 P0    | ✅ DONE | 50+ tests, 4 fichiers       |

---

### 📋 TODO (Sprint Courant)

| ID      | Story                | Priorité | Assigné | Notes              |
| ------- | -------------------- | -------- | ------- | ------------------ |
| MIG-088 | Deprecation Warnings | 🟠 P1    | Dev     | Prochaine priorité |
| MIG-089 | Regression Testing   | 🔴 P0    | Dev     | Après MIG-088      |

---

### 🔄 IN PROGRESS

| ID  | Story | Priorité | Assigné | Progression | Notes |
| --- | ----- | -------- | ------- | ----------- | ----- |
| -   | -     | -        | -       | -           | -     |

---

### 👀 REVIEW

| ID  | Story | Priorité | Reviewer | PR/Branch |
| --- | ----- | -------- | -------- | --------- |
| -   | -     | -        | -        | -         |

---

### ✅ DONE

| ID      | Story                    | Priorité | Complété   | Notes                                         |
| ------- | ------------------------ | -------- | ---------- | --------------------------------------------- |
| MIG-001 | Branche Migration        | 🔴 P0    | 2026-01-08 | Travail sur main directement                  |
| MIG-002 | Tests Régression CRIT    | 🔴 P0    | 2026-01-08 | 24 tests (CRIT-005 + CRIT-006)                |
| MIG-003 | Mapping Dépendances      | 🔴 P0    | 2026-01-08 | `architecture.md` documenté                   |
| MIG-010 | Interface BackendPort    | 🔴 P0    | 2026-01-08 | `core/ports/backend_port.py` (280 lines)      |
| MIG-011 | Adaptateur Compatibilité | 🔴 P0    | 2026-01-08 | `adapters/compat.py`, `legacy_adapter.py`     |
| MIG-012 | FilterService Complet    | 🟠 P1    | 2026-01-08 | `core/services/filter_service.py` (785L)      |
| MIG-013 | HistoryService           | 🟡 P2    | 2026-01-06 | `core/services/history_service.py`            |
| MIG-014 | ExpressionService        | 🟡 P2    | 2026-01-08 | `core/services/expression_service.py`         |
| MIG-015 | AutoOptimizer            | 🟡 P2    | 2026-01-08 | `core/services/auto_optimizer.py`             |
| MIG-020 | FilteringController      | 🟠 P1    | 2026-01-08 | `ui/controllers/filtering_controller.py`      |
| MIG-021 | ExploringController      | 🟠 P1    | 2026-01-08 | `ui/controllers/exploring_controller.py`      |
| MIG-022 | ExportingController      | 🟠 P1    | 2026-01-08 | `ui/controllers/exporting_controller.py`      |
| MIG-030 | Backend Factory          | 🟠 P1    | 2026-01-08 | `adapters/backends/factory.py` (393L)         |
| MIG-031 | DI Container             | 🟠 P1    | 2026-01-08 | `infrastructure/di/container.py`              |
| MIG-032 | App Bridge               | 🟠 P1    | 2026-01-08 | `adapters/app_bridge.py` (18KB)               |
| MIG-023 | Réduction appTasks.py    | 🔴 P0    | 2026-01-08 | `adapters/qgis/tasks/` (multi_step, progress) |
| MIG-024 | Réduction FilterMateApp  | 🟠 P1    | 2026-01-09 | 6 modules extraits (~3500L), délégation DI ✅ |
| MIG-025 | Intégration Controllers  | 🔴 P0    | 2026-01-08 | Délégation manage_task + FilterService DI     |
| MIG-040 | Tests E2E Complets       | 🟠 P1    | 2026-01-09 | 150+ tests, 6 classes workflow ✅             |
| MIG-041 | Tests Performance        | 🟠 P1    | 2026-01-09 | Benchmarks v2/v3, rapport markdown ✅         |
| MIG-042 | Documentation Migration  | 🟡 P2    | 2026-01-09 | migration-v3.md complet ✅                    |
| MIG-043 | Dépréciation Legacy      | 🟡 P2    | 2026-01-09 | modules/**init**.py warnings ✅               |
| MIG-050 | Release v3.1.0           | 🟠 P1    | 2026-01-09 | RELEASE_NOTES_v3.1.md créé ✅                 |
| MIG-060 | Layout Module Structure  | 🔴 P0    | 2026-01-09 | `ui/layout/` module créé (Phase 6)            |
| MIG-061 | SplitterManager          | 🟠 P1    | 2026-01-09 | 370 lignes, 18 tests, intégré dockwidget      |
| MIG-062 | DimensionsManager        | 🟠 P1    | 2026-01-09 | 650 lignes, 15 tests, intégré dockwidget      |
| MIG-063 | SpacingManager           | 🟠 P1    | 2026-01-09 | 320 lignes, 12 tests, standalone spacing      |
| MIG-064 | ActionBarManager         | 🟠 P1    | 2026-01-09 | 520 lignes, 18 tests, action bar positioning  |
| MIG-080 | Dialogs Module Structure | 🟢 P3    | 2026-01-09 | `ui/dialogs/` module créé (Phase 6)           |
| MIG-081 | FavoritesManagerDialog   | 🟡 P2    | 2026-01-09 | 571 lignes, 17 tests                          |
| MIG-065 | Styling Module           | 🔴 P0    | 2026-01-09 | `ui/styles/` 1320 lignes (Phase 6)            |
| MIG-066 | ThemeManager             | 🟠 P1    | 2026-01-09 | ThemeManager migré vers ui/styles/            |
| MIG-067 | IconManager              | 🟠 P1    | 2026-01-09 | IconThemeManager intégré                      |
| MIG-068 | ButtonStyler             | 🟡 P2    | 2026-01-09 | ButtonStyler 400 lignes, 1068 lignes tests    |
| MIG-071 | BackendController        | 🟠 P1    | 2026-01-10 | 500+ lignes, 30 tests, backend indicator      |
| MIG-072 | FavoritesController      | 🟠 P1    | 2026-01-10 | 600+ lignes, 25 tests, favorites UI           |
| MIG-073 | LayerSyncController      | 🟠 P1    | 2026-01-10 | 400 lignes, CRIT-005 protection (5s window)   |
| MIG-074 | PropertyController       | 🟡 P2    | 2026-01-10 | 550 lignes, property orchestration            |
| MIG-075 | BackendService           | 🟠 P1    | 2026-01-10 | 550 lignes, backend management service        |
| MIG-076 | FavoritesService         | 🟠 P1    | 2026-01-10 | 600 lignes, favorites business logic          |
| MIG-082 | OptimizationDialog       | 🟡 P2    | 2026-01-09 | 610 lignes, 573 lignes tests                  |
| MIG-083 | PostgresInfoDialog       | 🟢 P3    | 2026-01-09 | 290 lignes, 480 lignes tests                  |
| MIG-084 | SignalManager Complet    | 🔴 P0    | 2026-01-09 | 500+ lignes, context manager, force reconnect |
| MIG-085 | LayerSignalHandler       | 🟠 P1    | 2026-01-09 | 340 lignes, 450 lignes tests                  |

---

## 📊 Progression par Phase

### ✅ Migration v3 (Phases 1-6) - COMPLETE

```
Phase 1: Stabilisation     [██████████] 100%  (4/4 stories)
Phase 2: Core Domain       [██████████] 100%  (6/6 stories)
Phase 3: God Classes       [██████████] 100%  (5/5 stories)
Phase 4: Backends          [██████████] 100%  (4/4 stories)
Phase 5: Validation        [██████████] 100%  (5/5 stories) ✅
Phase 6: DockWidget        [██████████] 100%  (30/30 stories) ✅
─────────────────────────────────────────────
TOTAL MIGRATION v3         [██████████] 100%  (54/54 stories) 🎉
```

### 🗺️ Legacy Removal (Phases 7-10) - PLANNED

```
Phase 7: Backend Consolidation  [░░░░░░░░░░] 0%   (0/14 stories)  📋 v3.1→v3.2
Phase 8: Tasks Consolidation    [░░░░░░░░░░] 0%   (0/12 stories)  📋 v3.2→v3.3
Phase 9: Utilities Migration    [░░░░░░░░░░] 0%   (0/10 stories)  📋 v3.3→v3.4
Phase 10: Final Cleanup         [░░░░░░░░░░] 0%   (0/6 stories)   📋 v3.4→v4.0
─────────────────────────────────────────────
TOTAL LEGACY REMOVAL       [░░░░░░░░░░] 0%   (0/42 stories)
```

---

## 🎯 Prochaine Phase: Backend Consolidation (Phase 7)

Voir [phase1-backend-consolidation.md](stories/phase1-backend-consolidation.md) pour les stories détaillées.

| ID      | Story                      | Priorité | Sprint | Status  |
| ------- | -------------------------- | -------- | ------ | ------- |
| DEP-001 | Migrate Base Backend       | 🔴 P0    | 10     | 📋 TODO |
| DEP-002 | Migrate PostgreSQL Backend | 🔴 P0    | 10     | 📋 TODO |
| DEP-003 | Migrate Spatialite Backend | 🔴 P0    | 10     | 📋 TODO |
| DEP-004 | Migrate OGR Backend        | 🔴 P0    | 10     | 📋 TODO |
| DEP-005 | Migrate Memory Backend     | 🟡 P2    | 10     | 📋 TODO |

---

## 🎉 Migration v3 Complète!

Toutes les phases de migration v3 sont terminées. Les stories ont été archivées dans `stories/_archive/`.

Le projet entre maintenant dans la phase de **Legacy Removal** pour préparer v4.0.

---

## 📈 Vélocité

| Sprint                   | Stories Planifiées | Stories Complétées | Vélocité |
| ------------------------ | ------------------ | ------------------ | -------- |
| Sprint 0 (Pré-migration) | 2                  | 1                  | 50%      |
| Sprint 1 (Core Domain)   | 12                 | 15                 | 125% 🚀  |
| Sprint 2 (Phase 3-5)     | 10                 | 12                 | 120% 🚀  |
| Sprint 3 (Phase 6)       | 30                 | 30                 | 100% ✅  |
| Sprint 10 (Phase 7)      | 5                  | 0                  | -        |

---

## 📊 Métriques Clés

| Métrique              | Avant v3 | Actuel v3.0.21 | Cible v4 | Status |
| --------------------- | -------- | -------------- | -------- | ------ |
| Lignes dans modules/  | 40,000   | 40,000         | 0        | 📋     |
| Lignes dans core/     | 0        | 6,000          | 8,000    | ✅     |
| Lignes dans adapters/ | 0        | 3,500          | 15,000   | 🟡     |
| Fichiers > 800 lignes | 15       | 8              | 0        | 🟡     |
| Tests unitaires       | ~30      | 400+           | 500+     | ✅     |
| Coverage estimé       | ~40%     | ~75%           | 85%      | 🟡     |

### Structure Actuelle

```
filter_mate/
├── core/          ~6,000 lignes  ✅ Nouvelle architecture
├── adapters/      ~3,500 lignes  ✅ Nouvelle architecture
├── ui/            ~15,000 lignes ✅ Nouvelle architecture
├── infrastructure/ ~2,000 lignes ✅ Nouvelle architecture
├── modules/       ~40,000 lignes ⚠️ DEPRECATED - À migrer
└── config/        ~500 lignes    ✅ Configuration
```

---

## 🏷️ Labels

| Label      | Description             | Couleur   |
| ---------- | ----------------------- | --------- |
| `phase-1`  | Stabilisation           | 🔵 Bleu   |
| `phase-2`  | Core Domain             | 🟢 Vert   |
| `phase-3`  | God Classes             | 🟡 Jaune  |
| `phase-4`  | Backends                | 🟠 Orange |
| `phase-5`  | Validation              | 🔴 Rouge  |
| `phase-6`  | God Class DockWidget    | 🟣 Violet |
| `phase-7`  | Backend Consolidation   | 🔵 Bleu   |
| `phase-8`  | Tasks Consolidation     | 🟢 Vert   |
| `phase-9`  | Utilities Migration     | 🟡 Jaune  |
| `phase-10` | Final Cleanup           | 🟠 Orange |
| `blocking` | Bloque d'autres stories | ⚫ Noir   |
| `critical` | Bug critique à fixer    | 🔴 Rouge  |
| `dep-*`    | Deprecation story       | ⬛ Gris   |

---

## 📝 Notes de Sprint

### Sprint 10 - Objectifs (Phase 7: Backend Consolidation)

1. ⬜ DEP-001: Migrate Base Backend to adapters/
2. ⬜ DEP-002: Migrate PostgreSQL Backend (split 3500L → 5 fichiers)
3. ⬜ DEP-003: Migrate Spatialite Backend (split 2500L → 4 fichiers)
4. ⬜ DEP-004: Migrate OGR Backend (split 3500L → 4 fichiers)
5. ⬜ DEP-005: Migrate Memory Backend

### Accomplissements Sprint 3 (Phase 6 Complete!)

- ✅ 30 stories complétées pour DockWidget refactoring
- ✅ ui/layout/, ui/styles/, ui/dialogs/ créés
- ✅ Controllers intégrés (12 controllers)
- ✅ SignalManager et LayerSignalHandler

### Risques Identifiés (Legacy Removal)

- [ ] filter_task.py (12700 lignes) - Complexité élevée
- [ ] Dépendances circulaires modules/ ↔ adapters/
- [ ] Tests de régression critiques

---

## 🔗 Liens Rapides

| Ressource                  | Lien                                                                               |
| -------------------------- | ---------------------------------------------------------------------------------- |
| **Legacy Removal Roadmap** | [legacy-removal-roadmap.md](legacy-removal-roadmap.md)                             |
| **Phase 7 Stories**        | [stories/phase1-backend-consolidation.md](stories/phase1-backend-consolidation.md) |
| User Stories détaillées    | [migration-v3-user-stories.md](migration-v3-user-stories.md)                       |
| Architecture v3            | [../../docs/architecture-v3.md](../../docs/architecture-v3.md)                     |
| Guide Migration            | [../../docs/migration-v3.md](../../docs/migration-v3.md)                           |
| Release Notes v3.1         | [../../docs/RELEASE_NOTES_v3.1.md](../../docs/RELEASE_NOTES_v3.1.md)               |
| Backlog Bugs               | [../../BACKLOG.md](../../BACKLOG.md)                                               |
| Changelog                  | [../../CHANGELOG.md](../../CHANGELOG.md)                                           |

---

## 📊 Timeline Legacy Removal

```
v3.0.21 (Current) ────┬───────────────────────────────────────────────────
                      │
                      ├── v3.1.0 (2026-Q1)
                      │   └── Phase 7 Start: Backend consolidation
                      │
                      ├── v3.2.0 (2026-Q2)
                      │   ├── Phase 7 Complete
                      │   └── Phase 8 Start: Tasks consolidation
                      │
                      ├── v3.3.0 (2026-Q2)
                      │   ├── Phase 8 Complete
                      │   └── Phase 9 Start: Utilities migration
                      │
                      ├── v3.4.0 (2026-Q3)
                      │   ├── Phase 9 Complete
                      │   └── Phase 10 Start: Final cleanup
                      │
                      └── v4.0.0 (2026-Q3)
                          ├── Phase 10 Complete
                          ├── modules/ removed
                          └── 🎉 Legacy Removal Complete!
```

---

_Dernière mise à jour: 2026-01-09 - Phase 6 COMPLETE ✅ | Legacy Removal PLANNED 📋_
