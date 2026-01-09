# 📋 FilterMate v3.0 Migration - Kanban Board

**Epic:** Migration Architecture Hexagonale  
**Sprint Actuel:** Sprint 2 - Intégration Controllers  
**Dernière MAJ:** 2026-01-09 (MIG-024 Phase 3 terminée - DatabaseManager)

---

## 🎯 Tableau Kanban

### 📥 BACKLOG

| ID       | Story                   | Priorité | Phase | Dépend de    |
| -------- | ----------------------- | -------- | ----- | ------------ |
| MIG-004  | CI/CD Configuration     | 🟡 P2    | 1     | -            |
| MIG-041  | Tests Performance       | 🟠 P1    | 5     | MIG-040      |
| MIG-042  | Documentation Migration | 🟡 P2    | 5     | MIG-040      |
| MIG-043  | Dépréciation Legacy     | 🟡 P2    | 5     | MIG-040      |
| MIG-050  | Release v3.0.0          | 🟠 P1    | 5     | MIG-041..043 |
| MIG-024b | Réduction Finale App    | 🟡 P2    | 5     | MIG-024      |

#### Phase 6: God Class DockWidget (30 stories)

##### Sprint 6 - Layout & Styling (9 stories)

| ID      | Story                   | Priorité | Statut         | Notes                    |
| ------- | ----------------------- | -------- | -------------- | ------------------------ |
| MIG-060 | Layout Module Structure | 🔴 P0    | ✅ DONE        | `ui/layout/` créé        |
| MIG-061 | SplitterManager         | 🟠 P1    | ✅ DONE        | 370 lignes, 18 tests     |
| MIG-062 | DimensionsManager       | 🟠 P1    | 🔄 IN_PROGRESS | Squelette créé (123L)    |
| MIG-063 | SpacingManager          | 🟠 P1    | 🔄 IN_PROGRESS | Squelette créé           |
| MIG-064 | ActionBarManager        | 🟠 P1    | 🔄 IN_PROGRESS | Squelette créé           |
| MIG-065 | Styling Module          | 🔴 P0    | 📝 TODO        | `ui/styles/` à compléter |
| MIG-066 | ThemeManager            | 🟠 P1    | 📝 TODO        | Migrer de ui_styles.py   |
| MIG-067 | IconManager             | 🟠 P1    | 📝 TODO        | Migrer IconThemeManager  |
| MIG-068 | ButtonStyler            | 🟡 P2    | 📝 TODO        | Styling unifié boutons   |

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

| ID      | Story                  | Priorité | Statut         | Notes               |
| ------- | ---------------------- | -------- | -------------- | ------------------- |
| MIG-080 | Dialogs Module         | 🟢 P3    | ✅ DONE        | `ui/dialogs/` créé  |
| MIG-081 | FavoritesManagerDialog | 🟡 P2    | 🔄 IN_PROGRESS | Fichier créé        |
| MIG-082 | OptimizationDialog     | 🟡 P2    | 📝 TODO        | 8 méthodes à migrer |
| MIG-083 | PostgresInfoDialog     | 🟢 P3    | 📝 TODO        | Info session PG     |
| MIG-084 | SignalManager Complet  | 🔴 P0    | 📝 TODO        | 🔴 HIGH RISK        |
| MIG-085 | LayerSignalHandler     | 🟠 P1    | 📝 TODO        | Handler spécialisé  |
| MIG-086 | Migrate All Signals    | 🟠 P1    | 📝 TODO        | Migration complète  |

##### Sprint 9 - Final Refactoring (3 stories)

| ID      | Story                   | Priorité | Statut  | Notes             |
| ------- | ----------------------- | -------- | ------- | ----------------- |
| MIG-087 | DockWidget Orchestrator | 🔴 P0    | 📝 TODO | 🔴 HIGH RISK      |
| MIG-088 | Deprecation Warnings    | 🟠 P1    | 📝 TODO | Prep v4.0         |
| MIG-089 | Regression Testing      | 🔴 P0    | 📝 TODO | 50+ tests Phase 6 |

---

### 📋 TODO (Sprint Courant)

| ID      | Story                 | Priorité | Assigné | Notes                      |
| ------- | --------------------- | -------- | ------- | -------------------------- |
| MIG-040 | Tests Intégration E2E | 🟠 P1    | Dev     | Valider la chaîne complète |

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
| MIG-060 | Layout Module Structure  | 🔴 P0    | 2026-01-09 | `ui/layout/` module créé (Phase 6)            |
| MIG-061 | SplitterManager          | 🟠 P1    | 2026-01-09 | 370 lignes, 18 tests, intégré dockwidget      |
| MIG-062 | DimensionsManager        | 🟠 P1    | 2026-01-09 | 650 lignes, 15 tests, intégré dockwidget      |
| MIG-063 | SpacingManager           | 🟠 P1    | 2026-01-09 | 320 lignes, 12 tests, standalone spacing      |
| MIG-064 | ActionBarManager         | 🟠 P1    | 2026-01-09 | 520 lignes, 18 tests, action bar positioning  |
| MIG-080 | Dialogs Module Structure | 🟢 P3    | 2026-01-09 | `ui/dialogs/` module créé (Phase 6)           |

---

## 📊 Progression par Phase

```
Phase 1: Stabilisation     [██████████] 100%  (4/4 stories)
Phase 2: Core Domain       [██████████] 100%  (6/6 stories)
Phase 3: God Classes       [██████████] 100%  (5/5 stories - MIG-024 DONE ✅)
Phase 4: Backends          [██████████] 100%  (4/4 stories - Factory done)
Phase 5: Validation        [██░░░░░░░░] 20%   (1/5 stories)
Phase 6: DockWidget        [██░░░░░░░░] 20%   (6/30 stories) ✅ MIG-060..064,080
─────────────────────────────────────────────
TOTAL                      [█████░░░░░] 50%   (27/54 stories)
```

---

## 🔥 Priorités Immédiates (Cette Semaine)

### Sprint 2 - Intégration (8-12 Jan 2026)

```
┌─────────────────────────────────────────────────────────────────┐
│  LUNDI 8      │  MARDI 9      │  MERCREDI 10  │  JEUDI 11      │
├───────────────┼───────────────┼───────────────┼────────────────┤
│  ✅ DONE      │  MIG-025      │  MIG-025      │  MIG-023       │
│  Commit &     │  Intégration  │  Intégration  │  Réduction     │
│  Push         │  Controllers  │  (suite)      │  appTasks      │
├───────────────┼───────────────┼───────────────┼────────────────┤
│  ✅ Tests     │  MIG-024      │  MIG-024      │  MIG-040       │
│  Régression   │  Réduction    │  Réduction    │  Tests E2E     │
│  créés        │  App          │  App          │                │
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
| Sprint 2 (Courant)       | 6                  | 0                  | -        |

---

## 📊 Métriques Clés

| Métrique                   | Avant v3 | Actuel | Cible v3 | Status |
| -------------------------- | -------- | ------ | -------- | ------ |
| filter_mate_dockwidget.py  | 12,940   | 12,985 | < 2,000  | 🟡     |
| filter_mate_app.py         | 5,913    | 6,062  | < 3,000  | 🟡     |
| Adapters extraits (lignes) | 0        | 17,500 | -        | ✅     |
| Tests unitaires            | ~30      | 110    | 150+     | 🟡     |
| Core Domain (lignes)       | 0        | 1,234  | -        | ✅     |
| Controllers (lignes)       | 0        | 2,897  | -        | ✅     |
| Coverage estimé            | ~40%     | ~60%   | 85%      | 🟡     |

### Modules Extraits de FilterMateApp (MIG-024)

- `adapters/task_builder.py` (365 lignes)
- `adapters/variables_manager.py` (474 lignes)
- `adapters/undo_redo_handler.py` (587 lignes)
- `adapters/layer_refresh_manager.py` (285 lignes)
- `adapters/layer_validator.py` (270 lignes)
- `adapters/task_bridge.py` (780 lignes)
- `adapters/database_manager.py` (557 lignes) ← NEW

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

### Sprint 2 - Objectifs

1. ⬜ Connecter FilteringController au dockwidget
2. ⬜ Connecter ExploringController au dockwidget
3. ⬜ Connecter ExportingController au dockwidget
4. ⬜ Réduire filter_mate_dockwidget.py de 50%
5. ⬜ Valider avec tests d'intégration

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
- [ ] Couplage fort dockwidget ↔ logique métier → En cours (controllers)

---

## 🔗 Liens Rapides

| Ressource               | Lien                                                           |
| ----------------------- | -------------------------------------------------------------- |
| User Stories détaillées | [migration-v3-user-stories.md](migration-v3-user-stories.md)   |
| **Phase 6 Stories**     | [stories/phase6-stories.md](stories/phase6-stories.md)         |
| Architecture v3         | [../../docs/architecture-v3.md](../../docs/architecture-v3.md) |
| Guide Migration         | [../../docs/migration-v3.md](../../docs/migration-v3.md)       |
| Backlog Bugs            | [../../BACKLOG.md](../../BACKLOG.md)                           |
| Changelog               | [../../CHANGELOG.md](../../CHANGELOG.md)                       |

---

## 📊 Burndown Chart (Sprint 1)

```
Stories │
   6    │ ●───────────────────────────
        │     ╲
   5    │       ╲   Idéal
        │         ╲
   4    │           ╲
        │             ╲
   3    │               ╲
        │                 ╲
   2    │                   ╲
        │                     ╲
   1    │                       ╲
        │                         ╲
   0    │───────────────────────────●
        └─────────────────────────────
          J1  J2  J3  J4  J5  J6  J7

● = Réel (à mettre à jour quotidiennement)
```

---

_Dernière mise à jour: 2026-01-08 18:00 UTC_
