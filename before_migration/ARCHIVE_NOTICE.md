# ⚠️ ARCHIVE NOTICE

> **Ce dossier est une ARCHIVE - NE PAS MODIFIER**

## 📦 Objectif

Ce dossier `before_migration/` contient le code source de FilterMate **avant la migration EPIC-1** vers l'architecture hexagonale (v4.0).

## 🎯 Usage

- ✅ **Référence historique** : Comparer l'ancienne et la nouvelle architecture
- ✅ **Documentation** : Comprendre les décisions de refactoring  
- ⛔ **NE PAS importer** depuis ce dossier dans le code actif
- ⛔ **NE PAS modifier** les fichiers

## 📅 Version Archivée

| Champ | Valeur |
|-------|--------|
| **Version** | v2.3.8 (pre-migration) |
| **Date d'archivage** | Janvier 2026 |
| **Architecture** | Monolithique (`modules/`) |

## 🔄 Mapping Migration

| Ancien (ici) | Nouveau (v4.0) |
|--------------|----------------|
| `modules/appUtils.py` | `infrastructure/utils/layer_utils.py` |
| `modules/tasks/filter_task.py` | `core/tasks/filter_task.py` |
| `modules/backends/` | `adapters/backends/` |
| `modules/widgets.py` | `ui/widgets/custom_widgets.py` |
| `modules/constants.py` | `infrastructure/constants.py` |

---

*Archivé pour référence - BMAD Master Agent - Janvier 2026*
