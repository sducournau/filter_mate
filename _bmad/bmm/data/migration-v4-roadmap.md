# 🗺️ Plan de Migration v4.0 - Prochaines Étapes

**Date**: 9 janvier 2026  
**Version actuelle**: v3.1 (après migration modules/)  
**Version cible**: v4.0  
**Responsable**: Simon + Bmad Master

---

## ✅ Phase 1 TERMINÉE : Nettoyage Initial (9 jan 2026)

### Accomplissements

- ✅ **StyleLoader migré** vers `ui/styles/style_loader.py` (500+ lignes)
- ✅ **QGISThemeWatcher migré** vers `ui/styles/theme_watcher.py` (150+ lignes)
- ✅ **21 imports automatiquement migrés** via `tools/migrate_imports.py`
- ✅ **modules/ supprimé** (80 fichiers, 2.9 MB)
- ✅ **9 shims de compatibilité créés** pour imports legacy
- ✅ **2 backups complets** dans `_backups/`

### Métriques

| Métrique          | Avant  | Après     | Gain       |
| ----------------- | ------ | --------- | ---------- |
| Fichiers modules/ | 80     | 9 (shims) | **-88%**   |
| Taille modules/   | 2.9 MB | ~10 KB    | **-99.7%** |
| Imports critiques | 21     | 0         | **100%**   |

---

## 🎯 Phase 2 : Réduction des God Classes (2-3 semaines)

### Objectif

Réduire FilterMateApp et FilterMateDockWidget de 50% en extrayant les méthodes vers services/adapters.

### Phase 2.1 : FilterMateApp (6,075 lignes → 3,000 lignes)

**Priorité**: 🔴 HAUTE

#### 2.1.1 Extraire TaskParameterBuilder (~467 lignes)

**Story**: MIG-100  
**Durée estimée**: 6h  
**Fichier cible**: `adapters/task_builder.py` (étendre existant)

**Méthodes à extraire**:

- `get_task_parameters()` (328 lignes)
- `_build_common_task_params()` (116 lignes)
- `_build_layer_management_params()` (23 lignes)

**Critères d'acceptation**:

- [ ] Méthodes extraites vers TaskParameterBuilder
- [ ] FilterMateApp délègue à TaskParameterBuilder
- [ ] Tests unitaires pour TaskParameterBuilder
- [ ] Pas de régression fonctionnelle

---

#### 2.1.2 Extraire LayerLifecycleService (~843 lignes)

**Story**: MIG-101  
**Durée estimée**: 8h  
**Fichier cible**: `core/services/layer_lifecycle_service.py` (nouveau)

**Méthodes à extraire**:

- `_handle_project_initialization()` (246 lignes)
- `_handle_remove_all_layers()` (65 lignes)
- `_on_layers_added()` (109 lignes)
- `_filter_usable_layers()` (87 lignes)
- `cleanup()` (61 lignes)
- `_cleanup_postgresql_session_views()` (85 lignes)
- `force_reload_layers()` (170 lignes)

**Critères d'acceptation**:

- [ ] Service créé dans `core/services/`
- [ ] Interface `LayerLifecyclePort` définie
- [ ] FilterMateApp injecte et utilise le service
- [ ] Tests E2E pour lifecycle complet

---

#### 2.1.3 Extraire TaskManagementService (~581 lignes)

**Story**: MIG-102  
**Durée estimée**: 6h  
**Fichier cible**: `core/services/task_management_service.py` (nouveau)

**Méthodes à extraire**:

- `_safe_cancel_all_tasks()` (23 lignes)
- `_cancel_layer_tasks()` (28 lignes)
- `_handle_layer_task_terminated()` (71 lignes)
- `_process_add_layers_queue()` (35 lignes)
- Gestion de `self._running_tasks`

**Critères d'acceptation**:

- [ ] Service avec gestion centralisée des tasks
- [ ] TaskBridge intègre TaskManagementService
- [ ] Logs structurés pour task lifecycle
- [ ] Pas de memory leaks (validation CRIT-006)

---

### Phase 2.2 : FilterMateDockWidget (13,456 lignes → 7,000 lignes)

**Priorité**: 🟠 MOYENNE

#### 2.2.1 Extraire Layout Managers (~2,100 lignes)

**Story**: MIG-103  
**Durée estimée**: 10h  
**Fichiers existants**: Étendre `ui/layout/`

**Méthodes à migrer** (42 méthodes au total):

- Gestion splitter → `SplitterManager` (compléter)
- Gestion dimensions → `DimensionsManager` (compléter)
- Gestion spacing → `SpacingManager` (compléter)
- Action bar → `ActionBarManager` (compléter)

**Critères d'acceptation**:

- [ ] 40/42 méthodes layout extraites
- [ ] DockWidget < 300 lignes de setup UI
- [ ] Tests visuels passent (screenshots)
- [ ] Performance identique

---

#### 2.2.2 Extraire FilteringController (~750 lignes)

**Story**: MIG-104  
**Durée estimée**: 8h  
**Fichier**: `ui/controllers/filtering_controller.py` (étendre)

**Responsabilités**:

- Gestion onglet "Filtering"
- Construction expression filter
- Validation expression
- Application filter via FilterService

**Critères d'acceptation**:

- [ ] Logique filtering 100% dans controller
- [ ] DockWidget délègue au controller
- [ ] Tests unitaires controller
- [ ] Signaux Qt bien connectés

---

#### 2.2.3 Extraire ExploringController (~3,200 lignes)

**Story**: MIG-105  
**Durée estimée**: 12h  
**Fichier**: `ui/controllers/exploring_controller.py` (étendre)

**Responsabilités**:

- Gestion onglet "Exploring"
- Table features (38 méthodes)
- Cache exploring
- Pagination

**Critères d'acceptation**:

- [ ] Logique exploring 100% dans controller
- [ ] Cache bien géré
- [ ] Performance identique ou meilleure
- [ ] Tests E2E exploring

---

### Phase 2.3 : Migration modules/tasks (~18,000 lignes)

**Priorité**: 🟡 BASSE (peut attendre v4.1)

Les fichiers dans `modules/tasks/` n'ont pas été supprimés car encore en backup.  
Stratégie : créer shims comme pour modules/ principal.

**Option A** : Garder tel quel avec warnings  
**Option B** : Créer shims minimaux maintenant  
**Option C** : Reporter à v4.1

**Recommandation** : **Option A** pour l'instant.

---

## 🧪 Phase 3 : Nettoyage et Consolidation (1 semaine)

### 3.1 Supprimer les Shims

**Story**: MIG-110  
**Durée estimée**: 4h

**Actions**:

- Migrer tous les imports restants vers nouvelle architecture
- Supprimer `modules/` complètement
- Vérifier aucune référence à modules/

**Critères d'acceptation**:

- [ ] 0 imports de modules/ dans le code actif
- [ ] Script `check_legacy_imports.py` retourne 0
- [ ] modules/ supprimé définitivement

---

### 3.2 Optimiser Imports

**Story**: MIG-111  
**Durée estimée**: 3h

**Actions**:

- Nettoyer imports circulaires
- Organiser imports par catégorie
- Utiliser imports absolus

---

### 3.3 Documentation Architecture

**Story**: MIG-112  
**Durée estimée**: 4h

**Livrables**:

- Mettre à jour `docs/architecture-v3.md`
- Créer diagrammes d'architecture
- Documenter les services

---

## ✅ Phase 4 : Tests et Validation (1 semaine)

### 4.1 Tests Unitaires

**Story**: MIG-120  
**Coverage cible**: 85%

**Focus**:

- Tous les nouveaux services
- Tous les controllers
- Adapters critiques

---

### 4.2 Tests E2E

**Story**: MIG-121

**Scénarios**:

- [ ] Cycle complet : ouvrir projet → filter → undo → export
- [ ] Multi-layers filtering
- [ ] PostgreSQL + Spatialite + OGR
- [ ] Performance benchmarks

---

### 4.3 Tests de Régression

**Story**: MIG-122

**Validation**:

- [ ] CRIT-005 (ComboBox) OK
- [ ] CRIT-006 (Memory leaks) OK
- [ ] Tous les bugs connus résolus
- [ ] Aucune nouvelle régression

---

## 📦 Phase 5 : Release v4.0 (2 jours)

### 5.1 Release Notes

**Story**: MIG-130

**Contenu**:

- Breaking changes (si aucun)
- Nouvelles features
- Architecture improvements
- Migration guide

---

### 5.2 Packaging

**Story**: MIG-131

**Actions**:

- Version bump à 4.0.0
- Update metadata.txt
- Créer tag Git
- Publier sur QGIS Plugin Repository

---

## 📊 Planning Proposé

```
Semaine 1 (13-17 jan)
├── MIG-100: TaskParameterBuilder (6h)
├── MIG-101: LayerLifecycleService (8h)
└── MIG-102: TaskManagementService (6h)
    Total: 20h

Semaine 2 (20-24 jan)
├── MIG-103: Layout Managers (10h)
├── MIG-104: FilteringController (8h)
└── Tests intermédiaires (2h)
    Total: 20h

Semaine 3 (27-31 jan)
├── MIG-105: ExploringController (12h)
└── MIG-110-112: Cleanup (8h)
    Total: 20h

Semaine 4 (3-7 fév)
├── MIG-120-122: Tests complets (16h)
└── MIG-130-131: Release (4h)
    Total: 20h
```

**Total effort estimé**: **80 heures** (4 semaines)

---

## 🎯 Succès Metrics v4.0

| Métrique                      | v3.1 (actuel) | v4.0 (cible) | Gain      |
| ----------------------------- | ------------- | ------------ | --------- |
| FilterMateApp (lignes)        | 6,075         | < 3,000      | **-50%**  |
| FilterMateDockWidget (lignes) | 13,456        | < 7,000      | **-48%**  |
| modules/ (fichiers)           | 9 (shims)     | 0            | **-100%** |
| Test coverage                 | 70%           | 85%          | **+15%**  |
| Méthodes > 100 lignes         | 25            | < 10         | **-60%**  |
| God classes                   | 2             | 0            | **-100%** |

---

## ⚠️ Risques et Mitigations

| Risque                   | Impact    | Probabilité | Mitigation                 |
| ------------------------ | --------- | ----------- | -------------------------- |
| Régression fonctionnelle | 🔴 Élevé  | Moyenne     | Tests E2E systématiques    |
| Performance dégradée     | 🟠 Moyen  | Basse       | Benchmarks automatisés     |
| Délais dépassés          | 🟡 Faible | Moyenne     | Priorisation stricte       |
| Complexité sous-estimée  | 🟠 Moyen  | Moyenne     | Buffer 20% sur estimations |

---

## 🚀 Démarrage Immédiat Recommandé

**Next Action**: Commencer **MIG-100** (TaskParameterBuilder)

**Raison**:

- Impact immédiat sur FilterMateApp
- Pas de dépendances externes
- Tests faciles (pure data transformation)
- Quick win pour momentum

**Commande**:

```bash
# Créer la story
cd _bmad/bmm/data/stories
cp template.md MIG-100-task-parameter-builder.md
# Éditer et commencer l'implémentation
```

---

**Simon, ce plan est prêt ! Veux-tu que je commence MIG-100 maintenant ? 🚀**
