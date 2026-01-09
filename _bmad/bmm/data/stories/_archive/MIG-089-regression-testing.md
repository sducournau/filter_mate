---
storyId: MIG-089
title: Complete Regression Testing
epic: 6.7 - Final Refactoring
phase: 6
sprint: 9
priority: P0
status: READY_FOR_DEV
effort: 1.5 days
assignee: null
dependsOn: [MIG-087, MIG-088, MIG-040]
blocks: [MIG-050]
createdAt: 2026-01-09
updatedAt: 2026-01-09
risk: HIGH
---

# MIG-089: Complete Regression Testing

## 📋 Story

**En tant que** développeur,  
**Je veux** valider que le refactoring n'a causé aucune régression,  
**Afin de** livrer une version stable v3.1.

---

## 🎯 Objectif

Exécuter une suite complète de tests de régression couvrant tous les scénarios utilisateurs après le refactoring Phase 6.

⚠️ **STORY CRITIQUE**: Cette story est le gate final avant la release v3.1. Aucun bug ne doit passer.

---

## ✅ Critères d'Acceptation

### Tests Automatisés

- [ ] Tous les tests unitaires existants passent (100%)
- [ ] Nouveaux tests d'intégration couvrent les cas extraits
- [ ] Coverage globale > 80%
- [ ] Aucun test skip ou xfail injustifié

### Tests Manuels

- [ ] Checklist de test manuel complétée
- [ ] Tous les backends testés (PostgreSQL, Spatialite, OGR)
- [ ] Tous les formats d'export testés
- [ ] Theme switching testé
- [ ] Favoris CRUD testé

### Non-Régression CRIT-005

- [ ] Bug CRIT-005 testé spécifiquement
- [ ] Test avec OGR (1er filtre)
- [ ] Test avec Spatialite (multi-step)
- [ ] Test avec PostgreSQL (2ème filtre)
- [ ] comboBox maintient sa valeur

### Performance

- [ ] Pas de dégradation > 10%
- [ ] Profiling avant/après documenté
- [ ] Memory leaks vérifiés

---

## 📝 Plan de Test

### 1. Tests Unitaires Automatisés

#### 1.1 Tests des Managers

```python
# tests/unit/ui/layout/
test_splitter_manager.py
test_dimensions_manager.py
test_spacing_manager.py
test_action_bar_manager.py

# tests/unit/ui/styling/
test_theme_manager.py
test_icon_manager.py
test_button_styler.py
```

#### 1.2 Tests des Controllers

```python
# tests/unit/ui/controllers/
test_filtering_controller.py
test_exploring_controller.py
test_exporting_controller.py
test_config_controller.py
test_backend_controller.py
test_favorites_controller.py
test_layer_sync_controller.py
test_property_controller.py
```

#### 1.3 Tests des Services

```python
# tests/unit/core/services/
test_filter_service.py
test_backend_service.py
test_favorites_service.py
test_layer_service.py
```

#### 1.4 Tests des Signals

```python
# tests/unit/adapters/qgis/signals/
test_signal_manager.py
test_layer_signal_handler.py
```

### 2. Tests d'Intégration

#### 2.1 Scénarios de Filtrage

```python
def test_filter_ogr_layer():
    """Filtrer une couche OGR (Shapefile)."""
    layer = load_test_shapefile()
    dockwidget.apply_filter("id > 10")

    assert layer.subsetString() == "id > 10"
    assert dockwidget.current_layer == layer  # CRIT-005

def test_filter_spatialite_multistep():
    """Filtrer une couche Spatialite en multi-step."""
    layer = load_test_spatialite()

    # Step 1
    dockwidget.apply_filter("population > 1000")
    assert dockwidget.current_layer == layer  # CRIT-005

    # Step 2
    dockwidget.apply_filter("population > 1000 AND area > 100")
    assert dockwidget.current_layer == layer  # CRIT-005

def test_filter_postgresql_second():
    """Filtrer une couche PostgreSQL deux fois."""
    layer = load_test_postgresql()

    # First filter
    dockwidget.apply_filter("id = 1")
    assert dockwidget.current_layer == layer

    # Second filter - CRIT-005 trigger point
    dockwidget.apply_filter("id = 2")
    assert dockwidget.current_layer == layer  # CRIT-005
```

#### 2.2 Scénarios d'Export

```python
def test_export_shapefile():
    """Export vers Shapefile."""
    output = dockwidget.export_data(format='shp')
    assert Path(output).exists()

def test_export_geopackage():
    """Export vers GeoPackage."""
    output = dockwidget.export_data(format='gpkg')
    assert Path(output).exists()

def test_export_geojson():
    """Export vers GeoJSON."""
    output = dockwidget.export_data(format='geojson')
    assert Path(output).exists()
```

#### 2.3 Scénarios de Favoris

```python
def test_favorites_crud():
    """Test complet CRUD favoris."""
    # Create
    fav = dockwidget.add_favorite("Test", "id = 1")
    assert fav.name == "Test"

    # Read
    favorites = dockwidget.get_favorites()
    assert len(favorites) > 0

    # Update
    dockwidget.update_favorite(fav.id, name="Updated")

    # Delete
    dockwidget.remove_favorite(fav.id)
```

### 3. Tests Manuels

#### 3.1 Checklist Backend OGR

| Test                     | Attendu           | Résultat |
| ------------------------ | ----------------- | -------- |
| Charger Shapefile        | Couche visible    | ☐        |
| Appliquer filtre simple  | Features filtrées | ☐        |
| comboBox garde sa valeur | Layer sélectionné | ☐        |
| Clear filter             | Toutes features   | ☐        |
| Export vers GeoJSON      | Fichier créé      | ☐        |

#### 3.2 Checklist Backend Spatialite

| Test                     | Attendu            | Résultat |
| ------------------------ | ------------------ | -------- |
| Charger GeoPackage       | Couche visible     | ☐        |
| Appliquer filtre spatial | Features dans zone | ☐        |
| Multi-step filtering     | Filtres combinés   | ☐        |
| comboBox garde sa valeur | Layer sélectionné  | ☐        |
| Export vers Shapefile    | Fichier créé       | ☐        |

#### 3.3 Checklist Backend PostgreSQL

| Test                     | Attendu           | Résultat |
| ------------------------ | ----------------- | -------- |
| Connecter base           | Connexion OK      | ☐        |
| Charger couche PostGIS   | Couche visible    | ☐        |
| Appliquer filtre 1       | Features filtrées | ☐        |
| Appliquer filtre 2       | Features filtrées | ☐        |
| comboBox garde sa valeur | Layer sélectionné | ☐        |
| Cleanup session views    | Views supprimées  | ☐        |

#### 3.4 Checklist Theme

| Test                   | Attendu            | Résultat |
| ---------------------- | ------------------ | -------- |
| Switch vers Dark mode  | UI dark            | ☐        |
| Switch vers Light mode | UI light           | ☐        |
| Icons adaptées         | Couleurs correctes | ☐        |
| Buttons stylés         | Style cohérent     | ☐        |

### 4. Tests de Performance

```python
def test_filter_performance():
    """Le filtrage ne doit pas dégradér > 10%."""
    layer = load_large_layer(100000)  # 100k features

    start = time.time()
    dockwidget.apply_filter("id > 50000")
    elapsed = time.time() - start

    # Baseline: 0.5s pour 100k features
    assert elapsed < 0.55  # Max 10% degradation

def test_no_memory_leak():
    """Pas de fuite mémoire après 100 filtres."""
    import tracemalloc

    tracemalloc.start()
    initial = tracemalloc.get_traced_memory()[0]

    for i in range(100):
        dockwidget.apply_filter(f"id = {i}")
        dockwidget.clear_filter()

    final = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    growth = final - initial
    assert growth < 10 * 1024 * 1024  # Max 10MB growth
```

---

## 🔗 Dépendances

### Entrée

- MIG-087: Simplified DockWidget
- MIG-088: Deprecation Warnings
- MIG-040: Tests E2E (Phase 5)

### Sortie

- MIG-050: Release v3.1

---

## 📊 Métriques de Succès

| Métrique                | Cible        | Seuil Échec |
| ----------------------- | ------------ | ----------- |
| Tests unitaires         | 100% pass    | < 100%      |
| Coverage                | > 80%        | < 70%       |
| Tests manuels           | 100% pass    | < 100%      |
| Performance dégradation | < 10%        | > 20%       |
| Memory leak             | < 10MB       | > 50MB      |
| CRIT-005 régression     | 0 occurrence | > 0         |

---

## ⚠️ Critères d'Arrêt

La release v3.1 est **BLOQUÉE** si:

1. Un test unitaire échoue
2. Un test CRIT-005 échoue
3. Un test d'export échoue
4. La dégradation performance > 20%
5. Memory leak > 50MB détecté

---

## 📋 Checklist Développeur

### Préparation

- [ ] Environnement de test configuré
- [ ] Données de test disponibles (OGR, Spatialite, PostgreSQL)
- [ ] Profiler configuré

### Exécution

- [ ] Lancer tous les tests unitaires
- [ ] Lancer tous les tests d'intégration
- [ ] Compléter checklist manuelle OGR
- [ ] Compléter checklist manuelle Spatialite
- [ ] Compléter checklist manuelle PostgreSQL
- [ ] Compléter checklist manuelle Theme
- [ ] Lancer tests de performance
- [ ] Lancer test memory leak

### Validation

- [ ] Générer rapport de coverage
- [ ] Documenter résultats dans test-report.md
- [ ] Créer issues pour tout problème trouvé
- [ ] Sign-off pour release

---

## 📄 Template Rapport de Test

```markdown
# Phase 6 Regression Test Report

**Date:** 2026-01-XX
**Version:** 3.1.0-rc1
**Tester:** [Name]

## Summary

| Category          | Pass | Fail | Skip |
| ----------------- | ---- | ---- | ---- |
| Unit Tests        | X    | 0    | 0    |
| Integration Tests | X    | 0    | 0    |
| Manual Tests      | X    | 0    | 0    |

## Coverage

- Global: XX%
- Core: XX%
- Controllers: XX%
- Services: XX%

## Performance

- Baseline: Xs
- After: Xs
- Degradation: X%

## Memory

- Initial: X MB
- After 100 ops: X MB
- Growth: X MB

## CRIT-005 Validation

- OGR: ✅ PASS
- Spatialite: ✅ PASS
- PostgreSQL: ✅ PASS

## Issues Found

None / [List issues]

## Sign-off

☐ Ready for release
☐ Blocked - [reason]
```

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
