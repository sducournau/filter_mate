---
title: "Phase 3 Dev Story Definition of Done"
validation-target: "Story markdown for Phase 3 - Core Domain Layer"
validation-criticality: "HIGHEST"
phase: 3
phase_name: "Core Domain & Services"
epic: "ARCH-EPIC-003"
required-inputs:
  - "Story markdown file (3-X-*.md)"
  - "Phase 3 tickets reference (phase3-tickets.md)"
  - "Architecture document (architecture-refactoring-v3.md)"
validation-rules:
  - "ZERO QGIS dependencies in core/ package"
  - "Frozen dataclasses for all Value Objects"
  - "95%+ test coverage required"
  - "Type hints on all function signatures"
---

# 🎯 Phase 3 Definition of Done Checklist

**Phase 3 Objectif:** Établir la couche domaine Python pure avec Value Objects, Entities et Services.

## 🏛️ Architecture Phase 3 - Validation Obligatoire

### Pure Python Requirement (CRITICAL)

- [ ] **ZERO QGIS imports** dans `core/domain/`, `core/services/`, `core/ports/`
- [ ] **ZERO PyQt5 imports** dans les packages core
- [ ] **Pas de dépendances** vers `modules/`, `adapters/` depuis core
- [ ] **Standard library only** + typing, dataclasses, enum, abc, datetime

### Domain-Driven Design Compliance

- [ ] **Value Objects**: Utilisent `@dataclass(frozen=True)`
- [ ] **Immutabilité**: `FrozenSet` au lieu de `set`, `tuple` au lieu de `list`
- [ ] **Factory Methods**: Méthode `create()` ou factories nommées
- [ ] **With Methods**: `with_x()` retourne une nouvelle instance
- [ ] **Validation**: Dans `__post_init__` ou factory

---

## 📋 Checklist par Type de Story

### Pour Value Objects (ex: FilterExpression, FilterResult)

- [ ] `@dataclass(frozen=True)` décorateur utilisé
- [ ] Attributs immutables (FrozenSet, tuple)
- [ ] Méthode `create()` factory avec validation
- [ ] Méthodes `with_*()` pour modifications immutables
- [ ] `__str__` et `__repr__` implémentés
- [ ] Enum(s) associé(s) si nécessaire
- [ ] Docstrings complets

### Pour Entities (ex: LayerInfo)

- [ ] Identifiant unique défini
- [ ] Égalité basée sur l'identité
- [ ] État mutable si nécessaire via with methods

### Pour Services (ex: ExpressionService, FilterService)

- [ ] Interface/Protocol défini dans `core/ports/`
- [ ] Injection de dépendances via constructeur
- [ ] Pas d'état mutable (stateless)
- [ ] Logique métier pure

### Pour Ports/Interfaces (ex: BackendPort)

- [ ] Classes abstraites (ABC) ou Protocols
- [ ] Toutes méthodes abstraites
- [ ] Documentation des contrats

---

## ✅ Implementation Completion

- [ ] **Tous les Tasks complétés:** Chaque task et subtask marqué [x]
- [ ] **Acceptance Criteria satisfaits:** TOUS les AC cochés
- [ ] **Pas d'implémentation ambiguë:** Code clair et auto-documenté
- [ ] **Edge Cases gérés:** Validation des entrées, cas limites

---

## 🧪 Testing Requirements (Phase 3 Specific)

### Coverage Minimum: 95%

- [ ] **Unit tests créés:** `tests/core/domain/test_{module}.py`
- [ ] **Test des factories:** `test_create_*`, `test_from_*`
- [ ] **Test de validation:** Cas d'erreur, entrées invalides
- [ ] **Test d'immutabilité:** Vérifier que frozen=True fonctionne
- [ ] **Test des with methods:** Vérifie nouvelle instance retournée
- [ ] **Test des computed properties:** Toutes les propriétés testées
- [ ] **Test des enums:** Toutes les valeurs testées

### Commands

```bash
# Run tests for specific module
pytest tests/core/domain/test_filter_expression.py -v

# Run with coverage
pytest tests/core/domain/ -v --cov=core/domain --cov-report=term-missing

# Type checking (optional but recommended)
python -m mypy core/domain/filter_expression.py --ignore-missing-imports
```

### Test Patterns Phase 3

```python
import pytest
from core.domain.filter_expression import FilterExpression, ProviderType

class TestFilterExpression:
    """Test FilterExpression value object."""

    def test_create_simple_expression(self):
        """Test creation with factory method."""
        expr = FilterExpression.create(raw="status = 'active'")
        assert expr.raw == "status = 'active'"

    def test_immutability(self):
        """Test frozen dataclass cannot be modified."""
        expr = FilterExpression.create(raw="test")
        with pytest.raises(FrozenInstanceError):
            expr.raw = "modified"

    def test_with_method_returns_new_instance(self):
        """Test with_sql returns new instance."""
        original = FilterExpression.create(raw="test")
        updated = original.with_sql("SELECT *")
        assert original is not updated
        assert original.sql is None
        assert updated.sql == "SELECT *"
```

---

## 📝 Documentation & Tracking

- [ ] **File List complet:** Tous les fichiers créés/modifiés listés
- [ ] **Dev Agent Record mis à jour:**
  - [ ] Implementation Plan documenté
  - [ ] Debug Log si problèmes rencontrés
  - [ ] Completion Notes avec résumé
- [ ] **Change Log mis à jour:** Résumé des changements
- [ ] **Exports mis à jour:** `core/domain/__init__.py` exporte les nouvelles classes

---

## 🔚 Final Status Verification

### Story File Updates

- [ ] **Status → "completed"**
- [ ] **Tous les checkboxes AC → [x]**
- [ ] **Tous les checkboxes Tasks → [x]**

### Sprint Status Updates

- [ ] **sprint-status.yaml:** `{{story_key}}: "completed"`
- [ ] **completed_story_points:** Mis à jour

---

## 🎯 Phase 3 Quality Gates Summary

| Gate            | Critère                     | Validation                                           |
| --------------- | --------------------------- | ---------------------------------------------------- |
| 🐍 Pure Python  | Aucun import QGIS/PyQt5     | `grep -r "from qgis\|import qgis\|from PyQt5" core/` |
| ❄️ Immutabilité | frozen=True, FrozenSet      | Inspection du code                                   |
| 🏭 Factories    | Méthode create()            | Présente dans la classe                              |
| 📊 Coverage     | ≥ 95%                       | pytest --cov                                         |
| 📝 Type Hints   | Tous les paramètres         | Inspection du code                                   |
| 📚 Docstrings   | Classe + méthodes publiques | Inspection du code                                   |

---

## 🎯 Final Validation Output

```
=================================================
Phase 3 Definition of Done: {{PASS/FAIL}}
=================================================

Story: {{story_key}}
Type: {{story_type}} (Value Object / Entity / Service / Port)

✅ Architecture Compliance
   - Pure Python: {{status}}
   - Immutability: {{status}}
   - Factory Pattern: {{status}}

✅ Implementation
   - Tasks Complete: {{completed}}/{{total}}
   - Acceptance Criteria: {{ac_complete}}/{{ac_total}}

✅ Testing
   - Coverage: {{coverage}}%
   - Tests Passing: {{passed}}/{{total_tests}}

✅ Documentation
   - File List: {{status}}
   - Dev Record: {{status}}
   - Exports Updated: {{status}}

=================================================
{{final_message}}
=================================================
```

**Si FAIL:** Corriger les éléments manquants avant de marquer "completed"

**Si PASS:** Story prête pour la prochaine étape. Mettre à jour sprint-status.yaml.

---

## 📌 Phase 3 Stories Reference

| Story Key                  | Ticket   | Type         | Status |
| -------------------------- | -------- | ------------ | ------ |
| 3-1-filter-expression-vo   | ARCH-023 | Value Object | ✅     |
| 3-2-filter-result-vo       | ARCH-024 | Value Object | 🔄     |
| 3-3-layer-info-entity      | ARCH-025 | Entity       | ⏳     |
| 3-4-optimization-config-vo | ARCH-026 | Value Object | ⏳     |
| 3-5-backend-port           | ARCH-027 | Port         | ⏳     |
| 3-6-repository-port        | ARCH-028 | Port         | ⏳     |
| 3-7-cache-port             | ARCH-029 | Port         | ⏳     |
| 3-8-expression-service     | ARCH-030 | Service      | ⏳     |
| 3-9-filter-service         | ARCH-031 | Service      | ⏳     |
| 3-10-history-service       | ARCH-032 | Service      | ⏳     |
| 3-11-service-integration   | ARCH-033 | Integration  | ⏳     |
| 3-12-phase3-tests          | ARCH-034 | Tests        | ⏳     |
