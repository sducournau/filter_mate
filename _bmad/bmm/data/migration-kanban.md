# 📋 FilterMate v3.1 Migration - Kanban Board

**Epic:** Migration Architecture Hexagonale  
**Sprint Actuel:** Sprint 1 - Stabilisation  
**Dernière MAJ:** 2026-01-08

---

## 🎯 Tableau Kanban

### 📥 BACKLOG

| ID      | Story                   | Priorité | Phase | Dépend de                 |
| ------- | ----------------------- | -------- | ----- | ------------------------- |
| MIG-004 | CI/CD Configuration     | 🟠 P1    | 1     | -                         |
| MIG-013 | HistoryService          | 🟡 P2    | 2     | -                         |
| MIG-021 | ExploringController     | 🟠 P1    | 3     | MIG-020                   |
| MIG-022 | ExportingController     | 🟠 P1    | 3     | MIG-020                   |
| MIG-024 | Réduction FilterMateApp | 🟠 P1    | 3     | MIG-020, MIG-023          |
| MIG-030 | Backend PostgreSQL v3   | 🟠 P1    | 4     | MIG-010                   |
| MIG-031 | Backend Spatialite v3   | 🟠 P1    | 4     | MIG-010                   |
| MIG-032 | Backend OGR v3          | 🟠 P1    | 4     | MIG-010                   |
| MIG-033 | Factory Unifiée         | 🟠 P1    | 4     | MIG-030, MIG-031, MIG-032 |
| MIG-041 | Tests Performance       | 🟠 P1    | 5     | MIG-040                   |
| MIG-042 | Documentation Migration | 🟡 P2    | 5     | MIG-040                   |
| MIG-043 | Dépréciation Legacy     | 🟡 P2    | 5     | MIG-040                   |
| MIG-050 | Release v3.1.0          | 🟠 P1    | 5     | MIG-041, MIG-042, MIG-043 |

---

### 📋 TODO (Sprint Courant)

| ID      | Story                         | Priorité | Assigné   | Notes           |
| ------- | ----------------------------- | -------- | --------- | --------------- |
| MIG-001 | Création Branche Migration    | 🔴 P0    | Dev       | Première action |
| MIG-002 | Tests Régression CRIT-005/006 | 🔴 P0    | Dev       | Bloque Phase 2  |
| MIG-003 | Mapping Dépendances           | 🔴 P0    | Architect | Bloque Phase 2  |

---

### 🔄 IN PROGRESS

| ID      | Story                    | Priorité | Assigné   | Progression    | Notes                               |
| ------- | ------------------------ | -------- | --------- | -------------- | ----------------------------------- |
| MIG-010 | Interface BackendPort    | 🔴 P0    | Architect | ██████░░░░ 60% | `core/ports/backend_port.py` existe |
| MIG-011 | Adaptateur Compatibilité | 🔴 P0    | Dev       | ████░░░░░░ 40% | `adapters/compat.py` créé           |
| MIG-012 | FilterService Complet    | 🟠 P1    | Dev       | ████████░░ 80% | Manque multi-step                   |

---

### 👀 REVIEW

| ID  | Story | Priorité | Reviewer | PR/Branch |
| --- | ----- | -------- | -------- | --------- |
| -   | -     | -        | -        | -         |

---

### ✅ DONE

| ID      | Story          | Priorité | Complété   | Notes                              |
| ------- | -------------- | -------- | ---------- | ---------------------------------- |
| MIG-013 | HistoryService | 🟡 P2    | 2026-01-06 | `core/services/history_service.py` |

---

## 📊 Progression par Phase

```
Phase 1: Stabilisation     [░░░░░░░░░░] 0%    (0/4 stories)
Phase 2: Core Domain       [██████░░░░] 60%   (1/4 stories DONE, 2 IN_PROGRESS)
Phase 3: God Classes       [░░░░░░░░░░] 0%    (0/5 stories)
Phase 4: Backends          [░░░░░░░░░░] 0%    (0/4 stories)
Phase 5: Validation        [░░░░░░░░░░] 0%    (0/5 stories)
─────────────────────────────────────────────
TOTAL                      [█░░░░░░░░░] 5%    (1/22 stories)
```

---

## 🔥 Priorités Immédiates (Cette Semaine)

### Sprint 1 - Semaine 1 (8-12 Jan 2026)

```
┌─────────────────────────────────────────────────────────────────┐
│  LUNDI 8      │  MARDI 9      │  MERCREDI 10  │  JEUDI 11      │
├───────────────┼───────────────┼───────────────┼────────────────┤
│  MIG-001      │  MIG-002      │  MIG-002      │  MIG-003       │
│  Branche      │  Tests CRIT   │  Tests CRIT   │  Mapping Deps  │
│  migration    │  -005         │  -006         │                │
├───────────────┼───────────────┼───────────────┼────────────────┤
│  MIG-010      │  MIG-010      │  MIG-011      │  MIG-011       │
│  BackendPort  │  BackendPort  │  Compat       │  Compat        │
│  (continuer)  │  (finaliser)  │  Adapter      │  Adapter       │
└───────────────┴───────────────┴───────────────┴────────────────┘
```

---

## 🚧 Blocages Actuels

| Bloqueur                   | Impact   | Stories Bloquées          | Action Requise                   |
| -------------------------- | -------- | ------------------------- | -------------------------------- |
| Branche non créée          | Phase 1  | MIG-002, MIG-003, MIG-004 | Créer `refactoring/v3-migration` |
| Tests régression manquants | Phase 2+ | Toutes Phase 2+           | Compléter MIG-002                |

---

## 📈 Vélocité

| Sprint                   | Stories Planifiées | Stories Complétées | Vélocité |
| ------------------------ | ------------------ | ------------------ | -------- |
| Sprint 0 (Pré-migration) | 2                  | 1                  | 50%      |
| Sprint 1 (Courant)       | 6                  | 0                  | -        |

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

### Sprint 1 - Objectifs

1. ✅ Créer branche de migration isolée
2. ⬜ Compléter tests de régression critiques
3. ⬜ Documenter le mapping des dépendances
4. ⬜ Finaliser l'interface `BackendPort`
5. ⬜ Créer l'adaptateur de compatibilité

### Risques Identifiés

- [ ] Tests QGIS difficiles à mocker → Mitigation: Utiliser pytest-qgis
- [ ] Dépendances circulaires possibles → Mitigation: Analyser avec MIG-003

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
