# ✅ Phase 5 Checklist - Fallback Removal

**Date de création**: 11 janvier 2026  
**Phase**: 5 - Fallback Removal  
**Durée estimée**: 4-6 heures  
**Statut**: 📋 **PLANIFIÉ - EN ATTENTE**

---

## 🎯 Objectif de la Phase 5

Supprimer progressivement les fallbacks legacy vers modules/ après validation complète des services hexagonaux et UI controllers.

**Principe**: Strangler Fig Pattern - Retirer graduellement le code legacy validé.

---

## ⚠️ Prérequis (Validation Avant Démarrage)

### Prérequis Critiques

- [ ] **Phase 4 terminée** avec tests >70% coverage (✅ FAIT)
- [ ] **Production usage** >2 semaines sans issues critiques (⏳ EN ATTENTE)
- [ ] **Delegation success rate** >99% (⏳ À MESURER)
- [ ] **Backup complet** du projet créé (⚠️ CRITIQUE)

### Prérequis Recommandés

- [ ] **Monitoring actif** sur environnement production
- [ ] **Plan de rollback** documenté
- [ ] **Users informés** des changements à venir
- [ ] **Test environment** disponible pour validation

---

## 📦 Inventaire des Fallbacks

### Classification par Risque

| Fallback Method                         | File                | Risk  | Batch | Est. |
| --------------------------------------- | ------------------- | ----- | ----- | ---- |
| `filter_usable_layers()`                | filter_mate_app.py  | 🟢 LOW | 1     | 30m  |
| `cleanup_postgresql_session_views()`    | filter_mate_app.py  | 🟢 LOW | 1     | 30m  |
| `handle_layers_added()`                 | filter_mate_app.py  | 🟡 MED | 2     | 45m  |
| `force_reload_layers()`                 | filter_mate_app.py  | 🟡 MED | 2     | 30m  |
| `handle_remove_all_layers()`            | filter_mate_app.py  | 🟡 MED | 2     | 30m  |
| `cleanup()`                             | filter_mate_app.py  | 🔴 HIGH| 3     | 1h   |
| `safe_cancel_all_tasks()`               | filter_mate_app.py  | 🟡 MED | 2     | 45m  |
| `cancel_layer_tasks()`                  | filter_mate_app.py  | 🟡 MED | 2     | 30m  |

**Total Fallbacks**: 8  
**Total Temps Estimé**: 4h30m

---

## 🔄 Batch 1: Low-Risk Fallbacks (1h)

**Date prévue**: TBD (après validation prérequis)  
**Impact**: Minimal - Fonctions lecture seule ou non-critiques

### 1.1 - filter_usable_layers()

**Fichier**: `filter_mate_app.py`  
**Lignes**: ~XXX-XXX (à identifier)  
**Risk Level**: 🟢 LOW

**Checklist**:
- [ ] Localiser code fallback exact dans filter_mate_app.py
- [ ] Vérifier tests unitaires passent (LayerLifecycleService)
- [ ] Vérifier service delegation fonctionne
- [ ] Créer branch: `phase5/batch1/remove-filter-usable-layers-fallback`
- [ ] Supprimer code fallback
- [ ] Lancer tests complets
- [ ] Tester manuellement dans QGIS
- [ ] Commit avec message détaillé
- [ ] Monitor pendant 48h minimum
- [ ] Merge si stable

**Code Pattern à Rechercher**:
```python
# Fallback pattern to find:
try:
    result = self._layer_lifecycle_service.filter_usable_layers(...)
except Exception as e:
    # FALLBACK CODE TO REMOVE
    result = self._original_filter_usable_layers(...)
```

**Test de Validation**:
```bash
# Run specific tests
pytest tests/unit/services/test_layer_lifecycle_service.py::test_filter_usable_layers -v

# Run integration tests
pytest tests/integration/ -k "layer" -v
```

---

### 1.2 - cleanup_postgresql_session_views()

**Fichier**: `filter_mate_app.py`  
**Lignes**: ~XXX-XXX (à identifier)  
**Risk Level**: 🟢 LOW

**Checklist**:
- [ ] Localiser code fallback
- [ ] Vérifier tests passent
- [ ] Créer branch: `phase5/batch1/remove-cleanup-pg-views-fallback`
- [ ] Supprimer fallback
- [ ] Tests complets
- [ ] Test manuel avec PostgreSQL backend
- [ ] Test manuel avec Spatialite (fallback doit être gracieux)
- [ ] Commit
- [ ] Monitor 48h
- [ ] Merge si stable

**PostgreSQL Specific Test**:
```bash
# Requires PostgreSQL test environment
pytest tests/integration/backends/test_postgresql_backend.py -v
```

---

## 🔄 Batch 2: Medium-Risk Fallbacks (2h30m)

**Date prévue**: Après Batch 1 validé + 1 semaine monitoring  
**Impact**: Modéré - Fonctions utilisées fréquemment

### 2.1 - handle_layers_added()

**Fichier**: `filter_mate_app.py`  
**Risk Level**: 🟡 MEDIUM

**Checklist**:
- [ ] Localiser fallback
- [ ] Vérifier tests LayerLifecycleService
- [ ] Créer branch: `phase5/batch2/remove-handle-layers-added-fallback`
- [ ] Supprimer fallback
- [ ] Tests complets
- [ ] Test ajout layer manuel dans QGIS
- [ ] Test ajout multiple layers
- [ ] Commit
- [ ] Monitor 1 semaine
- [ ] Merge si stable

**Test Scenario**:
1. Ouvrir projet QGIS vide
2. Ajouter 1 layer PostgreSQL
3. Ajouter 1 layer Spatialite
4. Ajouter 3 layers Shapefile
5. Vérifier aucun crash, tous layers visibles

---

### 2.2 - force_reload_layers()

**Fichier**: `filter_mate_app.py`  
**Risk Level**: 🟡 MEDIUM

**Checklist**:
- [ ] Localiser fallback
- [ ] Vérifier tests
- [ ] Créer branch: `phase5/batch2/remove-force-reload-fallback`
- [ ] Supprimer fallback
- [ ] Tests
- [ ] Test manuel reload après filtre
- [ ] Commit
- [ ] Monitor 1 semaine
- [ ] Merge si stable

---

### 2.3 - handle_remove_all_layers()

**Fichier**: `filter_mate_app.py`  
**Risk Level**: 🟡 MEDIUM

**Checklist**:
- [ ] Localiser fallback
- [ ] Vérifier tests
- [ ] Créer branch: `phase5/batch2/remove-handle-remove-all-fallback`
- [ ] Supprimer fallback
- [ ] Tests
- [ ] Test suppression projet complet
- [ ] Commit
- [ ] Monitor 1 semaine
- [ ] Merge si stable

---

### 2.4 - safe_cancel_all_tasks()

**Fichier**: `filter_mate_app.py`  
**Risk Level**: 🟡 MEDIUM

**Checklist**:
- [ ] Localiser fallback
- [ ] Vérifier tests TaskManagementService
- [ ] Créer branch: `phase5/batch2/remove-cancel-tasks-fallback`
- [ ] Supprimer fallback
- [ ] Tests
- [ ] Test cancellation pendant filter en cours
- [ ] Commit
- [ ] Monitor 1 semaine
- [ ] Merge si stable

---

### 2.5 - cancel_layer_tasks()

**Fichier**: `filter_mate_app.py`  
**Risk Level**: 🟡 MEDIUM

**Checklist**:
- [ ] Localiser fallback
- [ ] Vérifier tests
- [ ] Créer branch: `phase5/batch2/remove-cancel-layer-tasks-fallback`
- [ ] Supprimer fallback
- [ ] Tests
- [ ] Test cancellation spécifique layer
- [ ] Commit
- [ ] Monitor 1 semaine
- [ ] Merge si stable

---

## 🔄 Batch 3: High-Risk Fallbacks (1h)

**Date prévue**: Après Batch 2 validé + 2 semaines monitoring  
**Impact**: Élevé - Fonctions critiques cleanup

### 3.1 - cleanup()

**Fichier**: `filter_mate_app.py`  
**Risk Level**: 🔴 HIGH

**Pourquoi HIGH**:
- Appelé au shutdown QGIS
- Gère cleanup PostgreSQL, resources
- Erreur = fuites mémoire ou corruption data

**Checklist**:
- [ ] Localiser fallback
- [ ] Vérifier tests LayerLifecycleService.cleanup()
- [ ] **Créer backup complet projet** ⚠️
- [ ] Créer branch: `phase5/batch3/remove-cleanup-fallback`
- [ ] Supprimer fallback avec EXTREME CAUTION
- [ ] Tests complets (unit + integration)
- [ ] Test manuel:
  - [ ] Ouvrir projet, filter, close QGIS proprement
  - [ ] Vérifier no PostgreSQL views left
  - [ ] Vérifier no memory leaks
  - [ ] Répéter 10+ fois
- [ ] Commit
- [ ] **Monitor 2 semaines minimum** ⚠️
- [ ] Peer review OBLIGATOIRE
- [ ] Merge uniquement si 100% stable

**Validation PostgreSQL**:
```sql
-- Check no temp views left after cleanup
SELECT schemaname, viewname 
FROM pg_views 
WHERE schemaname = 'filter_mate_temp';
-- Should return 0 rows
```

---

## 🛠️ Outils et Scripts

### Script de Localisation Fallbacks

Créer `tools/locate_fallbacks.py`:

```python
#!/usr/bin/env python3
"""Locate fallback patterns in filter_mate_app.py"""

import re
from pathlib import Path

def find_fallbacks(file_path):
    """Find try/except fallback patterns."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: service delegation with fallback
    pattern = r'try:\s+.*?self\._\w+_service\.(\w+)\(.*?\).*?except.*?:\s+.*?self\._original_(\w+)\('
    
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        method = match.group(1)
        print(f"Fallback found: {method}()")
        print(f"  Start: line {content[:match.start()].count(chr(10)) + 1}")
        print(f"  Content:\n{match.group(0)[:200]}...")
        print("-" * 80)

if __name__ == '__main__':
    app_file = Path(__file__).parent.parent / 'filter_mate_app.py'
    find_fallbacks(app_file)
```

**Usage**:
```bash
python tools/locate_fallbacks.py
```

---

### Script de Validation Post-Removal

Créer `tools/validate_phase5_batch.py`:

```python
#!/usr/bin/env python3
"""Validate Phase 5 batch removal was successful."""

import subprocess
import sys

def run_tests():
    """Run comprehensive test suite."""
    print("🧪 Running unit tests...")
    result = subprocess.run(['pytest', 'tests/unit/', '-v'], capture_output=True)
    if result.returncode != 0:
        print("❌ Unit tests FAILED")
        return False
    
    print("✅ Unit tests PASSED")
    
    print("🧪 Running integration tests...")
    result = subprocess.run(['pytest', 'tests/integration/', '-v'], capture_output=True)
    if result.returncode != 0:
        print("❌ Integration tests FAILED")
        return False
    
    print("✅ Integration tests PASSED")
    return True

def check_fallback_removed(method_name):
    """Check fallback code is truly removed."""
    with open('filter_mate_app.py', 'r') as f:
        content = f.read()
    
    if f'self._original_{method_name}(' in content:
        print(f"❌ FALLBACK STILL EXISTS: _original_{method_name}()")
        return False
    
    print(f"✅ Fallback removed: {method_name}()")
    return True

if __name__ == '__main__':
    method = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not method:
        print("Usage: validate_phase5_batch.py <method_name>")
        sys.exit(1)
    
    if not check_fallback_removed(method):
        sys.exit(1)
    
    if not run_tests():
        sys.exit(1)
    
    print(f"\n🎉 Batch validation SUCCESSFUL for {method}()")
```

**Usage**:
```bash
python tools/validate_phase5_batch.py filter_usable_layers
```

---

## 📊 Métriques de Succès

### Pour Chaque Batch

- [ ] **Tests**: 100% pass rate
- [ ] **Code**: Fallback code removed (grep validation)
- [ ] **Manual Testing**: No crashes, expected behavior
- [ ] **Monitoring**: No error spikes in logs
- [ ] **Performance**: No degradation (compare before/after)

### Pour Phase 5 Complète

- [ ] **8/8 fallbacks removed**
- [ ] **Test coverage**: Maintained >70%
- [ ] **Production stability**: 4+ weeks no issues
- [ ] **Code reduction**: ~500-800 lines removed
- [ ] **Delegation rate**: 100% (no more fallbacks)

---

## 🚨 Plan de Rollback

### Si Batch Échoue

1. **Revert immediat**:
   ```bash
   git revert <commit-sha>
   git push origin main
   ```

2. **Notify team/users**: Issue created with details

3. **Investigate**:
   - Logs analysis
   - Reproduce error
   - Identify root cause

4. **Fix**:
   - Option A: Fix service implementation
   - Option B: Keep fallback longer

5. **Re-attempt**: After fix validated

---

## 🎓 Best Practices Phase 5

### DO ✅

- **Incremental**: 1 fallback at a time
- **Test thoroughly**: Unit + integration + manual
- **Monitor actively**: Check logs daily
- **Document**: Commit messages détaillés
- **Wait**: Don't rush between batches

### DON'T ❌

- **Rush**: Ne pas supprimer multiple fallbacks same day
- **Skip tests**: Toujours run full suite
- **Ignore warnings**: Investigate every anomaly
- **Skip monitoring**: Always monitor post-deployment
- **Work alone**: Peer review for HIGH risk items

---

## 📅 Timeline Proposée

| Batch   | Start Date | Duration | Monitoring | Total |
| ------- | ---------- | -------- | ---------- | ----- |
| Batch 1 | TBD        | 1h       | 2 days     | ~3d   |
| *Wait*  | -          | -        | 1 week     | 1w    |
| Batch 2 | TBD        | 2.5h     | 1 week     | ~1.5w |
| *Wait*  | -          | -        | 2 weeks    | 2w    |
| Batch 3 | TBD        | 1h       | 2 weeks    | ~2.5w |

**Total Phase 5**: ~6-7 semaines (avec monitoring conservateur)

---

## ✅ Phase 5 Complete - Definition of Done

Phase 5 sera considérée **COMPLETE** quand:

- [x] Tous 8 fallbacks supprimés
- [x] Tous tests passent (>70% coverage maintenu)
- [x] Production stable 4+ semaines
- [x] Aucun spike d'erreurs en monitoring
- [x] Documentation mise à jour (ce fichier + roadmap)
- [x] Code review approuvé par peer
- [x] Métriques de succès atteintes
- [x] Lessons learned documentées

---

## 📞 Contact et Support

**Questions**: Consulter [BMAD_DOCUMENTATION_INDEX.md](BMAD_DOCUMENTATION_INDEX.md)  
**Issues**: Créer GitHub issue avec tag `phase-5`  
**Urgent**: Rollback immediat si production impactée

---

*Checklist générée par BMAD Master - 11 janvier 2026*  
*Dernière mise à jour: 11 janvier 2026*
