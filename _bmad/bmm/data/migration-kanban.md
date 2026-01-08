# 📋 FilterMate v3.0 Migration - Kanban Board

**Epic:** Migration Architecture Hexagonale  
**Sprint Actuel:** Sprint 2 - Intégration Controllers  
**Dernière MAJ:** 2026-01-08 (MIG-024 TaskParameterBuilder + MIG-025 Controllers connectés)

---

## 🎯 Tableau Kanban

### 📥 BACKLOG

| ID      | Story                   | Priorité | Phase | Dépend de    |
| ------- | ----------------------- | -------- | ----- | ------------ |
| MIG-004 | CI/CD Configuration     | 🟡 P2    | 1     | -            |
| MIG-041 | Tests Performance       | 🟠 P1    | 5     | MIG-040      |
| MIG-042 | Documentation Migration | 🟡 P2    | 5     | MIG-040      |
| MIG-043 | Dépréciation Legacy     | 🟡 P2    | 5     | MIG-040      |
| MIG-050 | Release v3.0.0          | 🟠 P1    | 5     | MIG-041..043 |

---

### 📋 TODO (Sprint Courant)

| ID      | Story                 | Priorité | Assigné | Notes                      |
| ------- | --------------------- | -------- | ------- | -------------------------- |
| MIG-040 | Tests Intégration E2E | 🟠 P1    | Dev     | Valider la chaîne complète |

---

### 🔄 IN PROGRESS

| ID      | Story                   | Priorité | Assigné | Progression | Notes                                                   |
| ------- | ----------------------- | -------- | ------- | ----------- | ------------------------------------------------------- |
| MIG-024 | Réduction FilterMateApp | 🟠 P1    | Dev     | 60%         | TaskParameterBuilder + VariablesPersistenceManager done |

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
| MIG-025 | Intégration Controllers  | 🔴 P0    | 2026-01-08 | Délégation manage_task + FilterService DI     |

---

## 📊 Progression par Phase

```
Phase 1: Stabilisation     [██████████] 100%  (4/4 stories)
Phase 2: Core Domain       [██████████] 100%  (6/6 stories)
Phase 3: God Classes       [████████░░] 80%   (4/5 stories - Controllers intégrés)
Phase 4: Backends          [██████████] 100%  (4/4 stories - Factory done)
Phase 5: Validation        [██░░░░░░░░] 20%   (1/5 stories)
─────────────────────────────────────────────
TOTAL                      [████████░░] 83%   (20/24 stories)
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

| Bloqueur                        | Impact  | Stories Bloquées | Action Requise                          |
| ------------------------------- | ------- | ---------------- | --------------------------------------- |
| Controllers non connectés au UI | Phase 3 | MIG-024          | Intégrer dans filter_mate_dockwidget.py |
| God Class 12,985 lignes         | Release | MIG-050          | Réduire via strangler fig pattern       |

---

## 📈 Vélocité

| Sprint                   | Stories Planifiées | Stories Complétées | Vélocité |
| ------------------------ | ------------------ | ------------------ | -------- |
| Sprint 0 (Pré-migration) | 2                  | 1                  | 50%      |
| Sprint 1 (Core Domain)   | 12                 | 15                 | 125% 🚀  |
| Sprint 2 (Courant)       | 6                  | 0                  | -        |

---

## 📊 Métriques Clés

| Métrique                  | Avant v3 | Actuel | Cible v3 | Status |
| ------------------------- | -------- | ------ | -------- | ------ |
| filter_mate_dockwidget.py | 12,940   | 12,985 | < 800    | 🔴     |
| filter_mate_app.py        | 5,913    | 5,984  | < 800    | 🔴     |
| Tests unitaires           | ~30      | 92     | 150+     | 🟡     |
| Core Domain (lignes)      | 0        | 1,234  | -        | ✅     |
| Controllers (lignes)      | 0        | 2,897  | -        | ✅     |
| Coverage estimé           | ~40%     | ~55%   | 85%      | 🟡     |

---

## 🏷️ Labels

| Label      | Description             | Couleur   |
| ---------- | ----------------------- | --------- |
| `phase-1`  | Stabilisation           | 🔵 Bleu   |
| `phase-2`  | Core Domain             | 🟢 Vert   |
| `phase-3`  | God Classes             | 🟡 Jaune  |
| `phase-4`  | Backends                | 🟠 Orange |
| `phase-5`  | Validation              | 🔴 Rouge  |
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
