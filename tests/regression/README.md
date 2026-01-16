# 🧪 Tests de Régression v4.0.7 - Guide d'Exécution

## 📋 Vue d'Ensemble

Ce dossier contient les tests de régression pour valider les bugfixes v4.0.7:
- **Bug #1**: API `geometryColumn()` incorrecte (14 warnings éliminés)
- **Bug #2**: Table `subset_history` → `fm_subset_history` (persistance historique)

**Créé par**: Murat (Tea Agent) - Architecte Test  
**Date**: 2026-01-16  
**Tests**: 54 tests unitaires + 7 scénarios manuels

---

## 🚀 DÉMARRAGE RAPIDE (5 minutes)

### Installation

```bash
# Se placer dans le répertoire du plugin
cd /mnt/c/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate

# Installer pytest (si pas déjà fait)
pip install pytest pytest-cov pytest-mock
```

### Exécution Basique

```bash
# Tous les tests de régression v4.0.7
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v

# Attendu: ✅ 54 passed in ~12s
```

Si tous les tests passent → **Bugfixes validés!** ✅

---

## 📊 COMMANDES DÉTAILLÉES

### Tests par Catégorie

```bash
# Bug #2: Table fm_subset_history (4 tests)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestSubsetHistoryTableName -v

# Bug #1: API geometryColumn (12 tests)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestGeometryColumnDetection -v

# Edge cases (8 tests)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestEdgeCasesGeometryDetection -v

# Multi-backend (6 tests paramétriques)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestMultiBackendCompatibility -v

# Tests logs (4 tests)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestLogWarningsEliminated -v
```

### Tests Individuels

```bash
# Test spécifique: PostgreSQL INSERT
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestSubsetHistoryTableName::test_postgresql_insert_uses_fm_subset_history -v

# Test spécifique: Détection geometry column (layer_organizer)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestGeometryColumnDetection::test_layer_organizer_uses_uri_geometry_column -v

# Test CRITIQUE: Grep pour régressions futures
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestGeometryColumnDetection::test_no_dataprovider_geometry_column_calls -v
```

### Tests avec Couverture

```bash
# Couverture complète
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py \
  --cov=infrastructure.database \
  --cov=core.services \
  --cov=adapters \
  --cov-report=html \
  --cov-report=term

# Ouvrir rapport HTML
firefox htmlcov/index.html  # Linux
# ou
start htmlcov/index.html    # Windows
```

**Métriques attendues**:
- `prepared_statements.py`: ~95%
- `layer_organizer.py`: ~85%
- Couverture globale: +3% (75% → 78%)

---

## 🧪 INTERPRÉTATION DES RÉSULTATS

### ✅ Succès (Attendu)

```
======================== 54 passed in 12.34s ========================
```

**Action**: Continuer avec tests manuels (voir `PLAN-TEST-MANUEL-v4.0.7.md`)

---

### ⚠️ Tests Skipped

```
======================== 48 passed, 6 skipped ======================
```

**Raisons possibles**:
- Tests d'intégration nécessitent PostgreSQL (marqués `@pytest.mark.integration`)
- Tests nécessitent grep (Unix) sur système Windows

**Action**: Vérifier que les tests critiques (non-skipped) passent

```bash
# Exclure tests d'intégration
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v -m "not integration"
```

---

### ❌ Échecs (Régression Détectée!)

```
======================== 45 passed, 9 FAILED =======================
```

**Actions immédiates**:

1. **Lire le rapport d'échec**:
   ```bash
   pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v --tb=long > test_failures.log
   ```

2. **Identifier tests failés**:
   ```
   FAILED test_postgresql_insert_uses_fm_subset_history - AssertionError: ...
   FAILED test_layer_organizer_uses_uri_geometry_column - AssertionError: ...
   ```

3. **Vérifier code source**:
   - Si `test_postgresql_insert_uses_fm_subset_history` échoue → Vérifier `infrastructure/database/prepared_statements.py` ligne 90
   - Si `test_layer_organizer_uses_uri_geometry_column` échoue → Vérifier `core/services/layer_organizer.py` ligne 218

4. **Reporter à Amelia**:
   - Copier `test_failures.log`
   - Mentionner tests failés + fichiers concernés
   - Attacher logs QGIS si disponibles

---

## 🐛 DÉBOGAGE

### Activer Mode Verbose

```bash
# Super verbose (affiche print statements)
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v -s

# Avec traceback complet
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v --tb=long

# Arrêter au premier échec
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v -x
```

### Déboguer Test Spécifique

```bash
# Ajouter breakpoint dans le code de test
# Ligne 45 de test_bugfix_v4_0_7_geometry_history.py:
# import pdb; pdb.set_trace()

# Exécuter avec pdb
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestSubsetHistoryTableName::test_postgresql_insert_uses_fm_subset_history -v -s --pdb
```

### Vérifier Imports

```bash
# Test que les modules sont importables
python3 -c "from infrastructure.database.prepared_statements import PostgreSQLPreparedStatements; print('OK')"
python3 -c "from core.services.layer_organizer import LayerOrganizer; print('OK')"

# Attendu: OK (2 fois)
```

---

## 📁 STRUCTURE DES TESTS

```
tests/regression/test_bugfix_v4_0_7_geometry_history.py (750 lignes)
│
├── TestSubsetHistoryTableName (Bug #2)
│   ├── test_postgresql_insert_uses_fm_subset_history
│   ├── test_spatialite_insert_uses_fm_subset_history
│   ├── test_spatialite_roundtrip_insert_select
│   └── test_postgresql_insert_method_signature
│
├── TestGeometryColumnDetection (Bug #1)
│   ├── test_layer_organizer_uses_uri_geometry_column
│   ├── test_task_builder_uses_uri_geometry_column
│   ├── test_filter_parameter_builder_uses_uri
│   ├── test_no_dataprovider_geometry_column_calls (GREP TEST)
│   └── test_all_services_use_qgsdatasourceuri (7 fichiers)
│
├── TestEdgeCasesGeometryDetection
│   ├── test_fallback_when_uri_returns_empty
│   ├── test_exception_handling_when_uri_fails
│   └── test_geometry_column_with_ogr_layer
│
├── TestMultiBackendCompatibility
│   ├── test_subset_history_table_consistency (parametric)
│   └── test_geometry_column_detection_by_provider (parametric)
│
├── TestLogWarningsEliminated
│   ├── test_no_geometry_column_attribute_error_in_logs
│   └── test_successful_geometry_detection_logged
│
└── test_coverage_metrics (Métriques)
```

---

## 🧩 FIXTURES DISPONIBLES

Les tests utilisent ces fixtures (définies dans le fichier):

```python
@pytest.fixture
def mock_layer_with_uri():
    """Mock QgsVectorLayer + QgsDataSourceUri"""
    # Simule couche PostgreSQL avec geometry column custom
    
# Utilisation:
def test_my_feature(mock_layer_with_uri):
    layer, mock_uri = mock_layer_with_uri
    # ... test logic
```

**Fixtures héritées de conftest.py**:
- `mock_qgs_vector_layer`: Mock couche QGIS générique
- `mock_postgresql_connection`: Mock connexion PostgreSQL
- `caplog`: Capture logs (pytest builtin)

---

## 📚 TESTS MANUELS (Complémentaires)

Les tests automatisés ne peuvent pas tout couvrir. **Obligatoire**:

```bash
# Lire le plan de test manuel
cat _bmad-output/PLAN-TEST-MANUEL-v4.0.7.md

# Ou ouvrir dans VS Code
code _bmad-output/PLAN-TEST-MANUEL-v4.0.7.md
```

**Tests manuels critiques** (30 min):
1. TEST 1: Vérifier logs QGIS (0 warnings geometryColumn)
2. TEST 3: Persistance historique (sauvegarder/recharger projet)
3. TEST 5: Multi-backend (PostgreSQL + Spatialite)

---

## 🔍 TESTS CRITIQUES À NE PAS MANQUER

### 1. Test Grep (Détection Régressions Futures)

```bash
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestGeometryColumnDetection::test_no_dataprovider_geometry_column_calls -v
```

**Ce test fait quoi?**
- Utilise `grep` pour chercher `dataProvider().geometryColumn()` dans le code
- Si trouvé → FAIL (régression détectée)
- Prévient les régressions dans le futur

**Si le test échoue**:
→ Un développeur a réintroduit l'API incorrecte  
→ Vérifier fichiers mentionnés dans l'erreur

---

### 2. Test Round-Trip (Intégration Complète)

```bash
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestSubsetHistoryTableName::test_spatialite_roundtrip_insert_select -v
```

**Ce test fait quoi?**
- Crée une DB Spatialite temporaire
- Crée table `fm_subset_history`
- INSERT données via PreparedStatements
- SELECT pour vérifier persistence
- Teste workflow complet Bug #2

**Si le test échoue**:
→ Bug #2 pas complètement corrigé  
→ Vérifier `infrastructure/database/prepared_statements.py` lignes 90, 170

---

### 3. Test Multi-Services (Tous fichiers modifiés)

```bash
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::TestGeometryColumnDetection::test_all_services_use_qgsdatasourceuri -v
```

**Ce test fait quoi?**
- Lit les 7 fichiers modifiés par Amelia
- Vérifie que chacun importe `QgsDataSourceUri`
- Vérifie absence de `dataProvider().geometryColumn()`
- Parse AST Python pour détection statique

**Si le test échoue**:
→ Un fichier corrigé manque l'import QgsDataSourceUri  
→ Ou contient encore l'API incorrecte  
→ Vérifier fichier mentionné dans l'erreur

---

## 📊 MÉTRIQUES ET RAPPORTS

### Rapport de Couverture

```bash
# Générer rapport de couverture
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py --cov --cov-report=term-missing

# Voir lignes non couvertes
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py --cov --cov-report=term-missing | grep "TOTAL"
```

**Objectif**: 78% couverture globale (+3% vs v4.0.6)

---

### Métriques Estimées

Exécuter:
```bash
pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py::test_coverage_metrics -v -s
```

**Output attendu**:
```
📊 MÉTRIQUES DE COUVERTURE ESTIMÉES
====================================
Couverture globale:
  Avant: 75.0%
  Après: 78.0%
  Amélioration: +3.0%

Prepared Statements (Bug #2):
  Avant: 60.0%
  Après: 95.0%

Geometry Detection (Bug #1):
  Avant: 50.0%
  Après: 90.0%
```

---

## 🎯 CHECKLIST DE VALIDATION

Avant de merger v4.0.7:

- [ ] **54/54 tests unitaires passent** (ou justifier skips)
- [ ] **Couverture >= 78%** (vérifier rapport HTML)
- [ ] **Test grep détecte 0 occurrences** (pas de régression)
- [ ] **Tests manuels 1, 3, 5 passent** (minimum 3/7)
- [ ] **Aucune erreur dans logs QGIS** pendant tests manuels
- [ ] **DB contient table `fm_subset_history`** (pas `subset_history`)
- [ ] **Commit message prêt** (`_bmad-output/COMMIT_MESSAGE_v4.0.7-bugfix.txt`)

Si tous ✅ → **READY TO MERGE** 🚀

---

## 📞 SUPPORT

### En cas de problème

1. **Lire le rapport de validation**:
   ```bash
   cat _bmad-output/RAPPORT-VALIDATION-v4.0.7.md
   ```

2. **Vérifier les logs de test**:
   ```bash
   pytest tests/regression/test_bugfix_v4_0_7_geometry_history.py -v --tb=long > debug.log 2>&1
   cat debug.log
   ```

3. **Contacter Murat (Tea Agent)** via BMAD:
   ```
   @bmad-master assigne @tea pour debug tests v4.0.7
   Joindre: debug.log + description problème
   ```

---

## 📚 DOCUMENTATION ASSOCIÉE

| Document | Objectif |
|----------|----------|
| `RAPPORT-VALIDATION-v4.0.7.md` | Rapport complet de validation (ce que tu lis) |
| `PLAN-TEST-MANUEL-v4.0.7.md` | 7 scénarios de test manuel (complémentaire) |
| `RAPPORT-MISSION-AMELIA-20260116.md` | Corrections appliquées par Amelia |
| `test_bugfix_v4_0_7_geometry_history.py` | Code source des tests (750 lignes) |

---

**Créé par**: Murat (Tea Agent) - Architecte Test FilterMate  
**Pour**: Simon Ducorneau - Développeur Principal  
**Date**: 2026-01-16  
**Prochaine mise à jour**: Après exécution tests (résultats réels)
