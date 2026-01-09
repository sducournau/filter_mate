# Plan de Nettoyage Final - FilterMate v4.0

**Date**: 2026-01-09
**Auteur**: BMad Master + Simon
**Statut**: 🔄 Phase A Complète

---

## 📊 État de la Migration

### Résumé Exécutif

| Métrique                       | Avant | Après Phase A |
| ------------------------------ | ----- | ------------- |
| Imports legacy (hors modules/) | 162   | 0 ✅          |
| Fichiers migrés                | 0     | 35            |
| Shims de compatibilité         | 0     | 5             |

### Phase A - Migration des Imports ✅ COMPLÈTE

**Objectif**: Migrer tous les imports `from modules.*` vers la nouvelle architecture.

**Script utilisé**: `tools/migrate_imports.py`

**Résultats**:

- ✅ 143 imports migrés automatiquement
- ✅ 35 fichiers modifiés
- ✅ 0 imports legacy restants (hors shims)

**Shims de compatibilité créés**:

| Shim                                  | Source Legacy                 | Exports                                           |
| ------------------------------------- | ----------------------------- | ------------------------------------------------- |
| `infrastructure/logging/__init__.py`  | modules.logging_config        | get_logger, get_app_logger, setup_logger          |
| `infrastructure/feedback/__init__.py` | modules.feedback_utils        | show_info, show_success, show_warning, show_error |
| `adapters/backends/__init__.py`       | modules.psycopg2_availability | POSTGRESQL_AVAILABLE                              |
| `ui/config/__init__.py`               | modules.ui_config             | UIConfig, DisplayProfile                          |
| `ui/elements/__init__.py`             | modules.ui_elements           | get_spacer_size, LAYOUTS                          |
| `ui/widgets/tree_view.py`             | modules.tree_view_utils       | JsonModel                                         |

---

## Phase B - Suppression de modules/ (PROCHAINE)

**Objectif**: Supprimer le répertoire `modules/` (68,649 lignes, 74 fichiers)

**Prérequis**:

- [ ] Phase A complète ✅
- [ ] Tests unitaires passent
- [ ] Validation manuelle dans QGIS

**Actions**:

1. Copier les implémentations réelles des modules legacy vers les shims
2. Supprimer le répertoire `modules/`
3. Mettre à jour les tests

---

## Phase C - Réduction des God Classes

**Objectif**: Réduire les 3 God Classes de 31,783 lignes à < 5,000 lignes total

| Fichier                      | Lignes Actuelles | Cible                                    |
| ---------------------------- | ---------------- | ---------------------------------------- |
| filter_mate_dockwidget.py    | 13,049           | < 2,000                                  |
| modules/tasks/filter_task.py | 12,671           | À supprimer (remplacé par core/services) |
| filter_mate_app.py           | 6,063            | < 1,500                                  |

---

## Prochaines Étapes

1. **Valider Phase A**: Exécuter les tests pour confirmer que tout fonctionne
2. **Commencer Phase B**: Intégrer les implémentations réelles dans les shims
3. **Supprimer modules/**: Une fois les tests validés
