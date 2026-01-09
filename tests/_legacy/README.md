# Tests Legacy (modules/)

Ces tests ont été archivés car ils testaient du code du dossier `modules/` qui a été supprimé dans FilterMate v4.0.

## Date d'archivage

- **Date**: 9 janvier 2026
- **Version**: v4.0.0
- **Raison**: Suppression du dossier `modules/` après migration vers l'architecture hexagonale

## Fichiers archivés

| Fichier                                    | Module testé                           |
| ------------------------------------------ | -------------------------------------- |
| `test_auto_config_reset.py`                | `modules.config_migration`             |
| `test_config_helpers.py`                   | `modules.config_helpers`               |
| `test_config_improved_structure.py`        | `modules.config_metadata_handler`      |
| `test_config_migration.py`                 | `modules.config_migration`             |
| `test_enhanced_optimizer.py`               | `modules.backends.optimizer_metrics`   |
| `test_filter_preservation.py`              | `modules.tasks.filter_task`            |
| `test_forced_backend_respect.py`           | `modules.backends.factory`             |
| `test_negative_buffer.py`                  | `modules.geometry_safety`              |
| `test_plugin_loading.py`                   | `modules.appUtils`, `modules.backends` |
| `test_undo_redo.py`                        | `modules.filter_history`               |
| `test_backends/test_ogr_backend.py`        | `modules.backends.ogr_backend`         |
| `test_backends/test_spatialite_backend.py` | `modules.backends.spatialite_backend`  |
| `unit/test_buffer_state_multistep.py`      | `modules.backends.spatialite_backend`  |

## Nouvelle architecture

Les nouveaux tests doivent cibler:

- `adapters/` - Adaptateurs (backends, repositories, QGIS)
- `core/` - Logique métier (domain, services, ports)
- `infrastructure/` - Logging, feedback, utils
- `ui/` - Interface utilisateur
- `config/` - Configuration

## Restauration

Si nécessaire, ces tests peuvent être restaurés depuis:

- Ce dossier `_legacy/`
- Le backup ZIP: `_backups/modules_backup_*.zip`
