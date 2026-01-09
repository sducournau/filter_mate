# Story MIG-101: Extract LayerLifecycleService from FilterMateApp

**Status**: ✅ COMPLETED (Partial - 2/7 méthodes)  
**Date**: 9 janvier 2026  
**Assignee**: Simon + Bmad Master  
**Effort**: 8h estimé → 3h réalisé (partiel)  
**Priority**: 🔴 HIGH

---

## 📝 Description

Créer un service dédié pour la gestion du cycle de vie des couches (validation, ajout, nettoyage PostgreSQL), extrayant ces responsabilités de la god class FilterMateApp.

## 🎯 Objectifs

- Créer LayerLifecycleService dans `core/services/`
- Créer LayerLifecyclePort dans `core/ports/`
- Extraire méthodes de lifecycle de FilterMateApp
- Réduire complexité de FilterMateApp

## ✅ Critères d'acceptation

- [x] LayerLifecycleService créé (448 lignes)
- [x] LayerLifecyclePort créé (interface)
- [x] `filter_usable_layers()` délègue au service
- [x] `cleanup_postgresql_session_views()` délègue au service
- [ ] `handle_layers_added()` déléguée (méthode trop couplée)
- [ ] `force_reload_layers()` déléguée (méthode trop couplée)
- [ ] `_handle_project_initialization()` déléguée (méthode trop couplée)
- [ ] `_handle_remove_all_layers()` déléguée (méthode trop couplée)
- [x] Pas d'erreurs de compilation
- [ ] Tests E2E (Phase 4)

## 🔨 Implémentation

### Fichiers créés

1. **core/services/layer_lifecycle_service.py** (448 lignes)
   - `LayerLifecycleService` classe principale
   - `LayerLifecycleConfig` dataclass configuration
   - `filter_usable_layers()` - filtre couches valides
   - `handle_layers_added()` - gère ajout avec retry PostgreSQL
   - `cleanup_postgresql_session_views()` - nettoyage vues materialisées
   - `_schedule_postgresql_retry()` - retry logic PostgreSQL

2. **core/ports/layer_lifecycle_port.py** (50 lignes)
   - `LayerLifecyclePort` interface (Protocol)
   - Définit le contrat pour implémentations futures

### Fichiers modifiés

1. **filter_mate_app.py** (+35 lignes pour délégation)
   - Import LayerLifecycleService et Config
   - `_get_layer_lifecycle_service()` - lazy initialization
   - `_filter_usable_layers()` - délègue au service
   - `_cleanup_postgresql_session_views()` - délègue au service
   - Documentation `@deprecated` ajoutée

### Architecture

```
AVANT (v4.0):
FilterMateApp
├── _filter_usable_layers() [87 lignes]
├── _on_layers_added() [109 lignes]
├── cleanup() [61 lignes]
├── _cleanup_postgresql_session_views() [85 lignes]
├── force_reload_layers() [170 lignes]
├── _handle_remove_all_layers() [65 lignes]
└── _handle_project_initialization() [246 lignes]
    Total: ~843 lignes

APRÈS (v4.0.1 - partiel):
FilterMateApp
├── _get_layer_lifecycle_service() [nouveau, 12 lignes]
├── _filter_usable_layers() [délégation, 15 lignes]
├── _cleanup_postgresql_session_views() [délégation, 20 lignes]
├── _on_layers_added() [109 lignes] ← À extraire
├── force_reload_layers() [170 lignes] ← À extraire
├── _handle_remove_all_layers() [65 lignes] ← À extraire
└── _handle_project_initialization() [246 lignes] ← À extraire

LayerLifecycleService (core/services/)
├── filter_usable_layers() [120 lignes]
├── handle_layers_added() [80 lignes]
├── cleanup_postgresql_session_views() [95 lignes]
└── _schedule_postgresql_retry() [40 lignes]
    Total: 448 lignes nouvelles
```

## 📊 Métriques

### Après MIG-101 (Partiel)

| Métrique | Valeur | Variation |
|----------|--------|-----------|
| FilterMateApp lignes | ~6,180 | +50 lignes* |
| Méthodes extraites | 2/7 | 28% |
| LayerLifecycleService | 448 lignes | Nouveau |

*Note: L'augmentation temporaire vient des fallbacks. Les méthodes restantes seront extraites après refactoring.

### Cible finale MIG-101 (7/7 méthodes)

| Métrique | Valeur cible |
|----------|--------------|
| FilterMateApp | ~5,350 lignes (-830) |
| LayerLifecycleService | ~700 lignes |

## 🚧 Défis techniques

### Couplage fort avec FilterMateApp

Les méthodes restantes (5/7) sont **très couplées** à FilterMateApp :
- Accès direct à `self.dockwidget`
- Accès direct à `self.PROJECT_LAYERS`
- Appels à `self.manage_task()`
- Modification de flags internes (`self._initializing_project`)

**Solution proposée** :
- Refactorer ces méthodes pour accepter tous les paramètres
- Passer callbacks pour `manage_task` et autres actions
- Phase 2.3 : extraire vers des services plus granulaires

### Méthodes trop complexes

- `_handle_project_initialization()` : 246 lignes, logique très complexe
- `force_reload_layers()` : 170 lignes avec gestion UI

**Solution** :
- Décomposer en sous-méthodes plus petites
- MIG-105 : extraire gestion UI vers UIController

## 📚 Documentation

### Code ajouté

- Docstrings complètes pour toutes les méthodes
- Documentation `@deprecated` pour méthodes FilterMateApp
- Type hints pour meilleure maintenabilité

### Documentation technique

- [x] Story MIG-101 documentée
- [x] Architecture hexagonale respectée (Port/Service pattern)
- [ ] Architecture docs (après Phase 2 complète)

## ⚠️ Notes et limitations

### Extraction partielle

Seules 2 méthodes sur 7 ont été extraites car :
- Les 5 autres nécessitent refactoring préalable
- Trop de couplage avec FilterMateApp
- Nécessitent passage de nombreux callbacks

### Rétrocompatibilité

Maintenue à 100% :
- Méthodes FilterMateApp inchangées (signature)
- Délégation transparente au service
- Fallback legacy si service indisponible

### Performance

- Impact: **Neutre**
- Lazy initialization du service (1 seule instance)
- Même logique exécutée

## 📝 Changelog

```
[4.0.1] - 2026-01-09
### Added
- LayerLifecycleService for layer lifecycle management
- LayerLifecyclePort interface
- filter_usable_layers() method in service
- cleanup_postgresql_session_views() method in service

### Changed
- FilterMateApp._filter_usable_layers() now delegates to service
- FilterMateApp._cleanup_postgresql_session_views() now delegates to service

### Deprecated
- Direct use of FilterMateApp lifecycle methods (use service)

### TODO (Phase 2.3)
- Extract remaining 5 lifecycle methods
- Refactor to reduce FilterMateApp coupling
- Create UIController for UI-heavy methods
```

## 🚀 Prochaines étapes

1. **MIG-102** : TaskManagementService (peut démarrer immédiatement)
2. **MIG-103-105** : Controllers DockWidget  
3. **Phase 2.3** : Finaliser extraction lifecycle (5 méthodes restantes)

---

**Story complétée (partiel) le**: 9 janvier 2026, 00:15 UTC  
**Durée réelle**: 3h (extraction partielle 2/7 méthodes)  
**Prochaine itération**: Phase 2.3 après refactoring
