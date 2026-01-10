# Analyse Réduction Dockwidget - FilterMate v4.0

**Date**: 10 janvier 2026  
**Version analysée**: v4.0 (commit d8fdb9e)  
**Fichier cible**: `filter_mate_dockwidget.py`

---

## 📈 État Actuel

| Métrique | Valeur | Objectif |
|----------|--------|----------|
| Lignes dockwidget | 12,248 | 800 |
| Méthodes | 230 | ~50 |
| Méthodes > 100 lignes | 29 | 0 |
| Réduction nécessaire | 11,448 lignes | 93% |

### Controllers existants

| Controller | Lignes | Rôle |
|------------|--------|------|
| integration.py | 1,889 | Orchestration |
| filtering_controller.py | 1,066 | Filtrage |
| exploring_controller.py | 791 | Exploration |
| property_controller.py | 785 | Propriétés |
| config_controller.py | 708 | Configuration |
| exporting_controller.py | 697 | Export |
| favorites_controller.py | 682 | Favoris |
| backend_controller.py | 581 | Backends |
| layer_sync_controller.py | 517 | Sync couches |
| **Total controllers** | **8,262** | - |

---

## ✅ Phase 1: Délégations Directes (1,020 lignes)

Méthodes avec correspondance exacte dans un controller existant.

### Priorité Haute (>100 lignes)

| Méthode Dockwidget | Lignes | Controller Cible | Méthode Cible |
|--------------------|--------|------------------|---------------|
| `current_layer_changed` | 245 | LayerSyncController | `on_current_layer_changed` |
| `_update_buffer_validation` | 106 | PropertyController | `update_buffer_validation` |
| `_update_other_property` | 102 | PropertyController | `_update_other_property` |

### Priorité Moyenne (50-100 lignes)

| Méthode Dockwidget | Lignes | Controller Cible | Méthode Cible |
|--------------------|--------|------------------|---------------|
| `auto_select_optimal_backends` | 84 | BackendController | `auto_select_optimal_backends` |
| `on_layer_selection_changed` | 73 | ExportingController | `on_layer_selection_changed` |
| `_apply_action_bar_position_change` | 69 | ConfigController | `_apply_action_bar_position_change` |
| `_reset_layer_expressions` | 68 | ExploringController | `set_layer` |
| `_apply_ui_profile_change` | 60 | ConfigController | `_apply_ui_profile_change` |
| `_ensure_valid_current_layer` | 60 | LayerSyncController | `_ensure_valid_current_layer` |
| `_apply_action_bar_position` | 52 | ConfigController | `_apply_action_bar_position_change` |
| `_combine_operator_to_index` | 51 | FilteringController | `combine_operator_to_index` |
| `cancel_pending_config_changes` | 50 | ConfigController | `cancel_pending_config_changes` |

**Sous-total Phase 1: ~1,020 lignes**

---

## 🔧 Phase 2: Enrichissement Controllers (2,500 lignes)

Méthodes qui nécessitent d'enrichir les controllers existants.

### ExploringController (+1,056 lignes)

| Méthode | Lignes | Action |
|---------|--------|--------|
| `get_exploring_features` | 249 | Migrer vers controller |
| `_reload_exploration_widgets` | 234 | Migrer vers controller |
| `exploring_source_params_changed` | 137 | Migrer vers controller |
| `exploring_link_widgets` | 136 | Migrer vers controller |
| `exploring_features_changed` | 120 | Migrer vers controller |
| `zooming_to_features` | 154 | Migrer (zoom features) |
| `_compute_zoom_extent_for_mode` | 118 | Migrer (zoom) |

### LayerSyncController (+978 lignes)

| Méthode | Lignes | Action |
|---------|--------|--------|
| `_synchronize_layer_widgets` | 175 | Migrer vers controller |
| `_initialize_layer_state` | 159 | Migrer vers controller |
| `get_project_layers_from_app` | 139 | Migrer vers controller |
| `_analyze_layer_optimizations` | 116 | Migrer vers controller |
| `_reconnect_layer_signals` | 111 | Migrer vers controller |

### PropertyController (+194 lignes)

| Méthode | Lignes | Action |
|---------|--------|--------|
| `properties_group_state_reset_to_default` | 111 | Migrer vers controller |
| `project_property_changed` | 83 | Migrer vers controller |

### ExportingController (+133 lignes)

| Méthode | Lignes | Action |
|---------|--------|--------|
| `exporting_populate_combobox` | 133 | Migrer vers controller |

### FilteringController (+117 lignes)

| Méthode | Lignes | Action |
|---------|--------|--------|
| `filtering_populate_layers_chekableCombobox` | 117 | Migrer vers controller |

---

## 🏗️ Phase 3: Nouveaux Controllers (2,000 lignes)

### Nouveau: UILayoutController (~1,467 lignes)

Gestion de l'interface utilisateur et layouts.

| Méthode | Lignes | Description |
|---------|--------|-------------|
| `_sync_multiple_selection_from_qgis` | 155 | Sync sélection |
| `_align_key_layouts` | 143 | Alignement layouts |
| `_create_horizontal_wrapper_for_side_action_bar` | 117 | Action bar wrapper |
| `_harmonize_checkable_pushbuttons` | 112 | Harmonisation boutons |
| `_apply_layout_spacing` | 112 | Spacing layouts |
| `dockwidget_widgets_configuration` | 164 | Config widgets |
| Autres méthodes UI | ~664 | Divers UI |

### Nouveau: FeatureController (~544 lignes)

Gestion des features et zoom.

| Méthode | Lignes | Description |
|---------|--------|-------------|
| `get_current_features` | 272 | Récupération features |
| `zooming_to_features` | 154 | Zoom features |
| `_compute_zoom_extent_for_mode` | 118 | Calcul extent zoom |

---

## 📋 Ordre d'Exécution Recommandé

### Sprint 1: Quick Wins (1 session)
1. ✅ Déléguer `current_layer_changed` (245 lignes)
2. ✅ Déléguer `_update_buffer_validation` (106 lignes)
3. ✅ Déléguer `auto_select_optimal_backends` (84 lignes)
4. ✅ Déléguer méthodes Config (≈180 lignes)

**Résultat attendu**: 12,248 → 11,633 lignes (-615)

### Sprint 2: ExploringController (1-2 sessions)
1. Enrichir ExploringController avec les 7 méthodes
2. Ajouter zoom features

**Résultat attendu**: 11,633 → 10,305 lignes (-1,328)

### Sprint 3: LayerSync & Property (1-2 sessions)
1. Enrichir LayerSyncController
2. Enrichir PropertyController

**Résultat attendu**: 10,305 → 9,133 lignes (-1,172)

### Sprint 4: Nouveaux Controllers (2-3 sessions)
1. Créer UILayoutController
2. Créer FeatureController
3. Migrer méthodes correspondantes

**Résultat attendu**: 9,133 → 7,122 lignes (-2,011)

### Sprint 5: Nettoyage Final
1. Extraire remaining méthodes < 50 lignes
2. Supprimer code mort
3. Refactorer dockwidget en façade pure

**Objectif final**: < 2,000 lignes (façade légère)

---

## 📊 Projections

| Phase | Lignes Avant | Lignes Après | Réduction |
|-------|--------------|--------------|-----------|
| État initial | 13,108 | - | - |
| Session actuelle | 13,108 | 12,248 | -860 (-6.6%) |
| Sprint 1 | 12,248 | 11,633 | -615 (-5.0%) |
| Sprint 2 | 11,633 | 10,305 | -1,328 (-11.4%) |
| Sprint 3 | 10,305 | 9,133 | -1,172 (-11.4%) |
| Sprint 4 | 9,133 | 7,122 | -2,011 (-22.0%) |
| Sprint 5 | 7,122 | ~2,000 | -5,122 (-71.9%) |

---

## ⚠️ Points d'Attention

### Dépendances Circulaires
- Vérifier que les controllers n'importent pas le dockwidget directement
- Utiliser l'injection de dépendances via `ControllerIntegration`

### Tests
- Chaque migration doit être testée dans QGIS
- Vérifier les signaux Qt (connexions/déconnexions)

### Fallbacks
- Conserver des fallbacks légers pour la compatibilité
- Pattern: essayer controller, sinon log warning

### Compilation
- Valider `python3 -m py_compile` après chaque changement
- Tester import dans QGIS Python console

---

## 🔗 Références

- Architecture hexagonale: [docs/architecture-v3.md](../../docs/architecture-v3.md)
- Guide développeur: [docs/development-guide.md](../../docs/development-guide.md)
- Controllers: [ui/controllers/](../../ui/controllers/)

---

*Généré par BMAD Master - Session du 10 janvier 2026*
