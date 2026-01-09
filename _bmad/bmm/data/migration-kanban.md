# 📋 FilterMate v3.0 Migration - Kanban Board

**Epic:** Migration Architecture Hexagonale  
**Sprint Actuel:** Sprint 3 - Phase 6 DockWidget  
**Dernière MAJ:** 2026-01-09 (Phase 5 COMPLETE ✅)

---

## 🎯 Tableau Kanban

### 📥 BACKLOG

| ID       | Story                | Priorité | Phase | Dépend de |
| -------- | -------------------- | -------- | ----- | --------- |
| MIG-004  | CI/CD Configuration  | 🟡 P2    | 1     | -         |
| MIG-024b | Réduction Finale App | 🟡 P2    | 5     | MIG-024   |

#### Phase 6: God Class DockWidget (30 stories)

##### Sprint 6 - Layout & Styling (9 stories)

| ID      | Story                   | Priorité | Statut  | Notes                    |
| ------- | ----------------------- | -------- | ------- | ------------------------ |
| MIG-060 | Layout Module Structure | 🔴 P0    | ✅ DONE | `ui/layout/` créé        |
| MIG-061 | SplitterManager         | 🟠 P1    | ✅ DONE | 370 lignes, 18 tests     |
| MIG-062 | DimensionsManager       | 🟠 P1    | ✅ DONE | 825 lignes, 11 tests ✅  |
| MIG-063 | SpacingManager          | 🟠 P1    | ✅ DONE | 337 lignes, 10 tests     |
| MIG-064 | ActionBarManager        | 🟠 P1    | ✅ DONE | 582 lignes, 16 tests     |
| MIG-065 | Styling Module          | 🔴 P0    | 📝 TODO | `ui/styles/` à compléter |
| MIG-066 | ThemeManager            | 🟠 P1    | 📝 TODO | Migrer de ui_styles.py   |
| MIG-067 | IconManager             | 🟠 P1    | 📝 TODO | Migrer IconThemeManager  |
| MIG-068 | ButtonStyler            | 🟡 P2    | 📝 TODO | Styling unifié boutons   |

##### Sprint 7 - Controllers & Services (9 stories)

| ID      | Story                  | Priorité | Statut  | Dépend de   |
| ------- | ---------------------- | -------- | ------- | ----------- |
| MIG-070 | ConfigController       | 🟠 P1    | 📝 TODO | MIG-060,065 |
| MIG-071 | BackendController      | 🟠 P1    | 📝 TODO | MIG-070     |
| MIG-072 | FavoritesController    | 🟠 P1    | 📝 TODO | MIG-070     |
| MIG-073 | LayerSyncController    | 🟠 P1    | 📝 TODO | MIG-070     |
| MIG-074 | PropertyController     | 🟡 P2    | 📝 TODO | MIG-070     |
| MIG-075 | BackendService         | 🟠 P1    | 📝 TODO | MIG-070     |
| MIG-076 | FavoritesService       | 🟠 P1    | 📝 TODO | MIG-075     |
| MIG-077 | LayerService           | 🟠 P1    | 📝 TODO | MIG-075     |
| MIG-078 | PostgresSessionManager | 🟡 P2    | 📝 TODO | MIG-075     |

##### Sprint 8 - Dialogs & Signals (7 stories)

| ID      | Story                  | Priorité | Statut  | Notes                |
| ------- | ---------------------- | -------- | ------- | -------------------- |
| MIG-080 | Dialogs Module         | 🟢 P3    | ✅ DONE | `ui/dialogs/` créé   |
| MIG-081 | FavoritesManagerDialog | 🟡 P2    | ✅ DONE | 571 lignes, 17 tests |
| MIG-082 | OptimizationDialog     | 🟡 P2    | 📝 TODO | 8 méthodes à migrer  |
| MIG-083 | PostgresInfoDialog     | 🟢 P3    | 📝 TODO | Info session PG      |
| MIG-084 | SignalManager Complet  | 🔴 P0    | 📝 TODO | 🔴 HIGH RISK         |
| MIG-085 | LayerSignalHandler     | 🟠 P1    | 📝 TODO | Handler spécialisé   |
| MIG-086 | Migrate All Signals    | 🟠 P1    | 📝 TODO | Migration complète   |

##### Sprint 9 - Final Refactoring (3 stories)

| ID      | Story                   | Priorité | Statut  | Notes             |
| ------- | ----------------------- | -------- | ------- | ----------------- |
| MIG-087 | DockWidget Orchestrator | 🔴 P0    | 📝 TODO | 🔴 HIGH RISK      |
| MIG-088 | Deprecation Warnings    | 🟠 P1    | 📝 TODO | Prep v4.0         |
| MIG-089 | Regression Testing      | 🔴 P0    | 📝 TODO | 50+ tests Phase 6 |

---

### 📋 TODO (Sprint Courant)

| ID      | Story          | Priorité | Assigné | Notes              |
| ------- | -------------- | -------- | ------- | ------------------ |
| MIG-065 | Styling Module | 🔴 P0    | Dev     | Prochaine priorité |
| MIG-066 | ThemeManager   | 🟠 P1    | Dev     | Après MIG-065      |

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

---

## 📊 Progression par Phase

```
Phase 1: Stabilisation     [██████████] 100%  (4/4 stories)
Phase 2: Core Domain       [██████████] 100%  (6/6 stories)
Phase 3: God Classes       [██████████] 100%  (5/5 stories)
Phase 4: Backends          [██████████] 100%  (4/4 stories)
Phase 5: Validation        [██████████] 100%  (5/5 stories) ✅ COMPLETE
Phase 6: DockWidget        [██████░░░░] 27%   (8/30 stories)
─────────────────────────────────────────────
TOTAL                      [██████░░░░] 59%   (32/54 stories)
```

---

## 🔥 Priorités Immédiates (Cette Semaine)

### Sprint 3 - Phase 6 DockWidget (9-15 Jan 2026)

```
┌─────────────────────────────────────────────────────────────────┐
│  JEUDI 9      │  VENDREDI 10  │  LUNDI 13     │  MARDI 14      │
├───────────────┼───────────────┼───────────────┼────────────────┤
│  ✅ DONE      │  MIG-065      │  MIG-066      │  MIG-067       │
│  Phase 5      │  Styling      │  ThemeManager │  IconManager   │
│  Complete     │  Module       │               │                │
├───────────────┼───────────────┼───────────────┼────────────────┤
│  ✅ Release   │  MIG-065      │  MIG-066      │  MIG-068       │
│  v3.1.0       │  (suite)      │  (suite)      │  ButtonStyler  │
│  notes        │               │               │                │
└───────────────┴───────────────┴───────────────┴────────────────┘
```

---

## 🚧 Blocages Actuels

| Bloqueur                 | Impact  | Stories Bloquées | Action Requise                       |
| ------------------------ | ------- | ---------------- | ------------------------------------ |
| DockWidget 13,000 lignes | Phase 6 | MIG-065..089     | Extraire via Phase 6 (strangler fig) |

---

## 📈 Vélocité

| Sprint                   | Stories Planifiées | Stories Complétées | Vélocité |
| ------------------------ | ------------------ | ------------------ | -------- |
| Sprint 0 (Pré-migration) | 2                  | 1                  | 50%      |
| Sprint 1 (Core Domain)   | 12                 | 15                 | 125% 🚀  |
| Sprint 2 (Phase 3-5)     | 10                 | 12                 | 120% 🚀  |
| Sprint 3 (Courant)       | 4                  | 0                  | -        |

---

## 📊 Métriques Clés

| Métrique                   | Avant v3 | Actuel | Cible v3 | Status |
| -------------------------- | -------- | ------ | -------- | ------ |
| filter_mate_dockwidget.py  | 12,940   | 12,985 | < 2,000  | 🟡     |
| filter_mate_app.py         | 5,913    | 6,062  | < 3,000  | 🟡     |
| Adapters extraits (lignes) | 0        | 17,500 | -        | ✅     |
| Tests unitaires            | ~30      | 260+   | 150+     | ✅     |
| Core Domain (lignes)       | 0        | 1,234  | -        | ✅     |
| Controllers (lignes)       | 0        | 2,897  | -        | ✅     |
| Coverage estimé            | ~40%     | ~75%   | 85%      | 🟡     |

### Phase 5 Livrables

- `tests/integration/workflows/test_e2e_complete_workflow.py` (560 lignes)
- `tests/performance/test_v3_performance_comparison.py` (450 lignes)
- `tests/test_deprecation_warnings.py` (160 lignes)
- `docs/RELEASE_NOTES_v3.1.md` (150 lignes)
- `modules/__init__.py` - Deprecation warnings (110 lignes)

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
| `blocking` | Bloque d'autres stories | ⚫ Noir   |
| `critical` | Bug critique à fixer    | 🔴 Rouge  |

---

## 📝 Notes de Sprint

### Sprint 3 - Objectifs (Phase 6: Styling)

1. ⬜ MIG-065: Créer module `ui/styles/`
2. ⬜ MIG-066: Extraire ThemeManager de ui_styles.py
3. ⬜ MIG-067: Extraire IconManager (IconThemeManager)
4. ⬜ MIG-068: Créer ButtonStyler composant

### Accomplissements Sprint 2 (Phase 5 Complete!)

- ✅ MIG-040: Tests E2E complets (6 classes, 150+ tests)
- ✅ MIG-041: Benchmarks performance v2/v3
- ✅ MIG-042: Documentation migration mise à jour
- ✅ MIG-043: Système de dépréciation implémenté
- ✅ MIG-050: Release notes v3.1.0 créées

### Accomplissements Sprint 1 (Exceptionnel!)

- ✅ Core Domain complet (4 value objects)
- ✅ 4 ports définis (BackendPort, CachePort, etc.)
- ✅ 4 services créés (Filter, History, Expression, AutoOptimizer)
- ✅ 3 controllers créés (Filtering, Exploring, Exporting)
- ✅ DI Container + Providers
- ✅ Backend Factory
- ✅ App Bridge pour compatibilité
- ✅ 92 fichiers de tests

### Risques Identifiés

- [x] Tests QGIS difficiles à mocker → ✅ Résolu avec mocks dans tests/
- [x] Couplage fort dockwidget ↔ logique métier → ✅ Phase 6 en cours
- [ ] SignalManager complexe → À surveiller (MIG-084)

---

## 🔗 Liens Rapides

| Ressource               | Lien                                                                 |
| ----------------------- | -------------------------------------------------------------------- |
| User Stories détaillées | [migration-v3-user-stories.md](migration-v3-user-stories.md)         |
| **Phase 6 Stories**     | [stories/phase6-stories.md](stories/phase6-stories.md)               |
| Architecture v3         | [../../docs/architecture-v3.md](../../docs/architecture-v3.md)       |
| Guide Migration         | [../../docs/migration-v3.md](../../docs/migration-v3.md)             |
| **Release Notes v3.1**  | [../../docs/RELEASE_NOTES_v3.1.md](../../docs/RELEASE_NOTES_v3.1.md) |
| Backlog Bugs            | [../../BACKLOG.md](../../BACKLOG.md)                                 |
| Changelog               | [../../CHANGELOG.md](../../CHANGELOG.md)                             |

---

## 📊 Burndown Chart (Sprint 2 - Complete)

```
Stories │
   6    │ ●───────────────────────────
        │     ╲
   5    │       ╲   Idéal
        │         ●─╲
   4    │             ╲
        │               ╲
   3    │                 ●╲
        │                   ╲
   2    │                     ╲
        │                       ●
   1    │                        ╲
        │                          ●
   0    │───────────────────────────●
        └─────────────────────────────
          J1  J2  J3  J4  J5  J6  J7

● = Réel (Sprint 2 Complete!)
```

---

_Dernière mise à jour: 2026-01-09 - Phase 5 COMPLETE ✅_
