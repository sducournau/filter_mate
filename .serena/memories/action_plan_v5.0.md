# 🎯 FilterMate v5.0 - Plan d'Action

**Date de création:** 22 janvier 2026  
**Version actuelle:** 4.3.10  
**Objectif:** v5.0 Production Release  
**Timeline estimée:** Février-Mars 2026

---

## 📊 État Actuel

| Métrique | Valeur | Objectif v5.0 |
|----------|--------|---------------|
| Score qualité | 8.5/10 | 9.0/10 |
| Test coverage | ~75% | 80% |
| God classes (>2000 lignes) | 4 | 1 max |
| TODOs P1 | 5 | 0 |
| Lignes de code (prod) | 126,539 | < 120,000 |

---

## 🚀 PHASE 1: Stabilisation (Semaine 1-2)

### Sprint 1.1: TODOs Critiques (P1)

| # | TODO | Fichier | Effort | Impact |
|---|------|---------|--------|--------|
| 1.1 | Zip archive creation | `core/export/layer_exporter.py:418` | 2h | Export complet |
| 1.2 | Internal DB storage | `core/services/favorites_service.py:179` | 3h | Favoris autonomes |
| 1.3 | Widget updates | `ui/controllers/integration.py:2072` | 2h | UI cohérente |
| 1.4 | Buffer widget value | `ui/controllers/favorites_controller.py:625,948` | 1h | Favoris + buffer |

**Effort total:** ~8h  
**Livrable:** v4.4.0 - Tous les TODOs P1 résolus

### Sprint 1.2: Tests Critiques

| # | Action | Fichiers | Effort |
|---|--------|----------|--------|
| 1.5 | Tests export workflow | `tests/integration/test_export.py` | 4h |
| 1.6 | Tests filter chaining | `tests/integration/test_filter_chain.py` | 4h |
| 1.7 | Tests favorites | `tests/unit/test_favorites.py` | 3h |

**Effort total:** ~11h  
**Livrable:** Coverage +3% (~78%)

---

## 🏗️ PHASE 2: Refactoring God Classes (Semaine 3-6)

### Sprint 2.1: filter_mate_dockwidget.py (PRIORITÉ HAUTE)

**Fichier:** `filter_mate_dockwidget.py` (6,925 lignes → < 2,500)

| # | Extraction | Lignes | Destination |
|---|------------|--------|-------------|
| 2.1.1 | Signal handlers | ~800 | `ui/managers/dockwidget_signal_manager.py` |
| 2.1.2 | Widget initialization | ~600 | `ui/managers/widget_initializer.py` |
| 2.1.3 | Context menu handlers | ~400 | `ui/managers/context_menu_manager.py` |
| 2.1.4 | Export UI logic | ~500 | `ui/controllers/export_ui_controller.py` |
| 2.1.5 | Layer sync logic | ~600 | `ui/managers/layer_sync_manager.py` |

**Effort total:** ~16h  
**Objectif:** 6,925 → 2,500 lignes (-64%)

### Sprint 2.2: exploring_controller.py

**Fichier:** `ui/controllers/exploring_controller.py` (3,208 lignes → < 1,500)

| # | Extraction | Lignes | Destination |
|---|------------|--------|-------------|
| 2.2.1 | Field handling | ~500 | `ui/controllers/field_controller.py` |
| 2.2.2 | Value loading | ~400 | `ui/controllers/value_loader_controller.py` |
| 2.2.3 | Selection sync | ~300 | `ui/managers/selection_sync_manager.py` |

**Effort total:** ~8h  
**Objectif:** 3,208 → 1,500 lignes (-53%)

### Sprint 2.3: filter_task.py (OPTIONNEL v5.0)

**Fichier:** `core/tasks/filter_task.py` (5,851 lignes)

Ce fichier est complexe mais stable. Prévu pour v5.1 ou v6.0.

---

## 🧪 PHASE 3: Couverture de Tests (Semaine 7-8)

### Sprint 3.1: Tests Unitaires

| # | Module | Tests à ajouter | Coverage cible |
|---|--------|-----------------|----------------|
| 3.1.1 | `core/services/` | 15 tests | 85% |
| 3.1.2 | `adapters/backends/` | 10 tests | 80% |
| 3.1.3 | `ui/controllers/` | 12 tests | 75% |

### Sprint 3.2: Tests d'Intégration

| # | Scénario | Effort |
|---|----------|--------|
| 3.2.1 | Multi-backend filtering | 4h |
| 3.2.2 | Export all formats | 3h |
| 3.2.3 | Undo/Redo complet | 2h |

**Effort total Phase 3:** ~20h  
**Objectif:** 75% → 80% coverage

---

## 📝 PHASE 4: Documentation & Release (Semaine 9-10)

### Sprint 4.1: Documentation

| # | Document | Action |
|---|----------|--------|
| 4.1.1 | CHANGELOG.md | Consolidation v4.x → v5.0 |
| 4.1.2 | README.md | Mise à jour features v5.0 |
| 4.1.3 | ARCHITECTURE.md | Refresh post-refactoring |
| 4.1.4 | User Guide (website) | Nouveaux screenshots |

### Sprint 4.2: Release v5.0

| # | Action | Effort |
|---|--------|--------|
| 4.2.1 | Final QA testing | 4h |
| 4.2.2 | QGIS plugin repository update | 1h |
| 4.2.3 | GitHub release notes | 1h |
| 4.2.4 | Website update | 2h |

---

## 📅 Timeline Résumé

```
Semaine 1-2  : PHASE 1 - Stabilisation (TODOs P1 + Tests critiques)
Semaine 3-6  : PHASE 2 - Refactoring God Classes
Semaine 7-8  : PHASE 3 - Couverture de Tests
Semaine 9-10 : PHASE 4 - Documentation & Release v5.0
```

**Date cible v5.0:** Mi-mars 2026

---

## 🎯 Critères de Succès v5.0

| Critère | Seuil | Méthode de validation |
|---------|-------|----------------------|
| Score qualité | ≥ 9.0/10 | Audit Serena |
| Test coverage | ≥ 80% | pytest-cov |
| God classes | ≤ 1 fichier > 3000 lignes | wc -l |
| TODOs P1 | 0 | grep "# TODO" |
| Bugs critiques | 0 | Issue tracker |
| Temps de démarrage | < 2s | Benchmark |

---

## 🔧 Actions Immédiates (Cette semaine)

### Aujourd'hui (22 janvier)
- [x] Analyse du codebase complète
- [x] Nettoyage __pycache__ et fichiers temporaires
- [x] Mise à jour des mémoires Serena
- [x] Création du plan d'action

### Sprint 1.1 - TODOs P1 (COMPLÉTÉ ✅)
- [x] TODO 1.1 - Zip archive creation (`core/export/layer_exporter.py`)
- [x] TODO 1.2 - Internal DB storage (`core/services/favorites_service.py`)
- [x] TODO 1.3 - Widget updates (`ui/controllers/integration.py`)
- [x] TODO 1.4 - Buffer widget value (`ui/controllers/favorites_controller.py`)

### Prochaines étapes
- [ ] Créer tests pour export workflow (Sprint 1.2)
- [ ] Tests filter chaining
- [ ] Tests favorites

---

## 📌 Notes Importantes

### Fichiers à NE PAS toucher (stable)
- `adapters/backends/postgresql/` - Stable, bien testé
- `core/geometry/` - Fonctionnel
- `infrastructure/cache/` - Performant

### Fichiers prioritaires pour refactoring
1. `filter_mate_dockwidget.py` - CRITIQUE
2. `exploring_controller.py` - HAUTE
3. `integration.py` - MOYENNE
4. `filter_task.py` - BASSE (v5.1)

### Risques identifiés
| Risque | Mitigation |
|--------|------------|
| Régression UI pendant refactoring | Tests E2E avant/après |
| Performance dégradée | Benchmarks comparatifs |
| Breaking changes | Backwards compat layer |

---

*Plan créé par BMAD Master - 22 janvier 2026*
