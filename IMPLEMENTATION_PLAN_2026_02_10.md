# PLAN D'IMPLEMENTATION -- FILTERMATE QGIS PLUGIN

**Date** : 10 fevrier 2026
**Auteur** : Marco, GIS Lead Developer
**Base** : Audit complet AUDIT_2026_02_10.md
**Version cible** : 5.0.0 (stabilisation) puis 6.0.0 (refactoring majeur)

---

## RESUME EXECUTIF

L'audit du 10 fevrier 2026 a revele un plugin architecturalement solide (hexagonal, 4 backends, 5 caches, connection pooling) mais souffrant de trois problemes structurels majeurs :

1. **Aucun test versionne** dans le depot Git -- 396 tests existent quelque part mais ne sont pas dans le repo. Tout refactoring sans filet de tests est du suicide technique.
2. **Deux God Objects** -- `filter_mate_dockwidget.py` (7 079 lignes, 279 methodes) et `filter_task.py` (5 884 lignes, 159 methodes) concentrent une complexite excessive.
3. **Gestion d'erreurs trop permissive** -- 1 232 clauses `except Exception` dans 165 fichiers masquent les bugs de programmation.

Le travail recent (audit signaux du 9 fevrier : 15 corrections, 8 bugs critiques corriges le 10 fevrier) a stabilise la couche signaux. Ce plan capitalise sur cette base pour consolider la qualite avant d'entreprendre le refactoring des monolithes.

**Principe directeur** : Stabiliser d'abord, tester ensuite, refactorer enfin. Jamais de refactoring sans couverture de tests prealable.

---

## CORRECTION DE L'AUDIT

**P6-1 / P8-2 (sql_utils.py lignes 240-256)** : L'audit signale que `sanitize_sql_identifier()` n'est pas execute dans les triple-quotes. Apres verification du code source, les lignes 240 et 251 utilisent bien des **f-strings** (`f"""`). Les fonctions sont donc correctement appelees. Ce finding est **invalide** et ne necessite aucune action corrective.

---

## VUE D'ENSEMBLE DES PHASES

```
Phase 0 : Quick Wins                         [Semaine 1 - Jours 1-2]
    |
Phase 1 : Filet de securite (Tests + CI)     [Semaines 1-3]
    |
Phase 2 : Assainissement erreurs             [Semaines 3-5]
    |
Phase 3 : Decomposition God Objects          [Semaines 5-11]
    |
Phase 4 : Architecture et qualite            [Semaines 11-14]
    |
Phase 5 : Consolidation finale               [Semaines 14-16]
```

### Dependances critiques

```
Phase 0 ──> Aucune dependance (executable immediatement)
Phase 1 ──> Prerequis pour Phase 3 (pas de refactoring sans tests)
Phase 2 ──> Prerequis partiel pour Phase 3 (les exceptions specifiques facilitent le refactoring)
Phase 3 ──> Depend de Phase 1 (tests) + Phase 2 (erreurs)
Phase 4 ──> Depend de Phase 3 (architecture propre apres decomposition)
Phase 5 ──> Depend de toutes les phases precedentes
```

---

## PHASE 0 : QUICK WINS (< 2h chacun)

Actions executables immediatement, sans risque de regression.

### QW-1 : Deplacer les imports `iface` au niveau local dans les fichiers de taches

**Priorite** : Haute
**Effort** : 1h
**Risque** : Nul (changement purement defensif)

**Description** : Remplacer les imports module-level de `from qgis.utils import iface` par des imports locaux dans les methodes qui utilisent `iface`, exclusivement dans les fichiers de taches (worker threads).

**Fichiers concernes** :
- `core/tasks/filter_task.py` (ligne 47) -- utilise dans `finished()` et methodes appelees depuis `finished()`
- `core/tasks/layer_management_task.py` (ligne 27) -- utilise dans `finished()` et methodes appelees depuis `finished()`
- `core/tasks/task_completion_handler.py` (ligne 12) -- appele uniquement depuis `finished()`

**Criteres d'acceptation** :
- Les trois imports module-level de `iface` sont supprimes dans ces fichiers
- Chaque methode utilisant `iface` contient un `from qgis.utils import iface` local
- Le plugin demarre et execute un filtre sans erreur
- `py_compile` passe sur les trois fichiers

**Risques** : Aucun. L'import local est strictement equivalent au runtime.

---

### QW-2 : Mettre a jour `qgisMinimumVersion` dans metadata.txt

**Priorite** : Basse
**Effort** : 15min
**Risque** : Nul

**Description** : Changer `qgisMinimumVersion=3.0` en `qgisMinimumVersion=3.16` pour refleter la version minimum reellement supportee. QGIS 3.16 est la derniere LTR raisonnable en 2026.

**Fichiers concernes** :
- `metadata.txt`

**Criteres d'acceptation** :
- `qgisMinimumVersion=3.16` dans metadata.txt
- Verification que le plugin utilise uniquement des API disponibles dans QGIS 3.16+

---

### QW-3 : Creer `requirements-optional.txt`

**Priorite** : Basse
**Effort** : 15min
**Risque** : Nul

**Description** : Documenter les dependances Python optionnelles dans un fichier standard.

**Fichier a creer** :
- `requirements-optional.txt` a la racine

**Contenu** :
```
# Optional dependencies for FilterMate
# PostgreSQL/PostGIS backend support
psycopg2-binary>=2.8.0
```

**Criteres d'acceptation** :
- Le fichier existe et est versionne
- Le README mentionne son existence

---

### QW-4 : Ajouter un decorator `@main_thread_only` (debug mode)

**Priorite** : Moyenne
**Effort** : 1h30
**Risque** : Nul (actif uniquement en mode debug)

**Description** : Creer un decorator qui valide en mode debug que la methode decoree est appelee depuis le thread principal. Utile pour documenter et proteger les methodes `finished()`, les callbacks UI, et les acces a `iface`.

**Fichier a creer** :
- `infrastructure/utils/thread_utils.py`

**Criteres d'acceptation** :
- Le decorator leve `RuntimeError` en mode debug si appele hors thread principal
- En mode production (pas de flag debug), le decorator est un no-op
- Application sur `FilterEngineTask.finished()`, `LayersManagementEngineTask.finished()`
- Tests unitaires du decorator

---

## PHASE 1 : FILET DE SECURITE -- Tests et CI

**Duree estimee** : 2-3 semaines
**Objectif** : Rendre les tests existants (396 tests, ~47 600 lignes) accessibles dans le depot et executables via CI.

### A1 : Versionner le repertoire `tests/` dans le depot Git

**Priorite** : CRITIQUE
**Effort** : 2-4h (si les tests existent deja) / 1-2 semaines (si recreer)
**Risque** : Moyen -- les tests peuvent avoir des chemins relatifs casses, des imports manquants, ou des mocks incompatibles avec l'etat actuel du code

**Description** :
Les tests existent (documentes dans la memoire Serena `testing_documentation` : 157 fichiers, ~47 600 lignes, structure `tests/unit/`, `tests/integration/`, `tests/regression/`, `tests/performance/`). Ils ne sont pas dans le depot Git car le repertoire `tests/` n'existe pas.

Actions :
1. Localiser les fichiers de test (repertoire non versionne, depot separe, sauvegarde)
2. Copier `tests/` dans le projet
3. Copier `conftest.py` et `conftest_qgis_mocks.py`
4. Verifier que `.gitignore` ne les exclut pas (lignes 56-57 les preservent -- OK)
5. Executer `pytest tests/ -v --tb=short` pour identifier les tests casses
6. Corriger les imports et chemins relatifs
7. Commiter et pousser

**Fichiers concernes** :
- `tests/` (a ajouter -- ~157 fichiers)
- `tests/conftest.py` (a ajouter)
- `tests/conftest_qgis_mocks.py` (a ajouter)
- `.gitignore` (verifier, probablement OK)

**Criteres d'acceptation** :
- Le repertoire `tests/` est versionne dans Git
- `pytest tests/unit/ -v` execute au moins 200 tests sans erreur
- Les markers `@pytest.mark.unit`, `@pytest.mark.integration` sont fonctionnels
- `conftest.py` fournit les fixtures pour `iface`, `QgsProject`, `QgsVectorLayer`

**Dependances** : Aucune -- a faire en premier
**Bloque** : A3, B3 (tout refactoring)

---

### A1-bis : Corriger et stabiliser la CI GitHub Actions

**Priorite** : Haute
**Effort** : 2-4h
**Risque** : Faible

**Description** :
Le fichier `.github/workflows/test.yml` existe mais est partiellement obsolete :
- Utilise `actions/checkout@v3` et `actions/setup-python@v4` (OK)
- Pointe `pytest tests/` mais `tests/` n'existe pas
- Le job `code-quality` pointe `modules/ *.py` pour Black -- `modules/` est un repertoire legacy qui n'existe plus
- Pas de matrice de versions Python/QGIS
- Pas de cache pip

Actions :
1. Mettre a jour les references de repertoires (`modules/` -> `core/`, `adapters/`, etc.)
2. Ajouter un cache pip pour accelerer la CI
3. S'assurer que les tests unitaires (sans QGIS) passent dans le runner Ubuntu
4. Configurer les markers pour ne pas executer les tests `@pytest.mark.qgis` en CI (pas d'environnement QGIS)
5. Ajouter un seuil de couverture minimale (`--cov-fail-under=70`)

**Fichiers concernes** :
- `.github/workflows/test.yml`

**Criteres d'acceptation** :
- Les tests unitaires passent en CI sur chaque push/PR
- Le rapport de couverture est genere
- Le build echoue si la couverture descend sous 70%
- Le lint (flake8) passe sans erreurs de syntaxe

**Dependances** : A1 (tests versionnes)

---

### A2 : Ajouter les tests critiques manquants

**Priorite** : Haute
**Effort** : 1 semaine
**Risque** : Faible

**Description** :
Ecrire des tests unitaires pour les modules les plus risques, en priorite :

1. **`core/domain/`** -- Tests purs sans aucun mock QGIS. Valider les dataclasses, les exceptions, les objets valeur. (~1 jour)
2. **`infrastructure/database/sql_utils.py`** -- Valider `sanitize_sql_identifier()`, les creations de tables SpatiaLite, les conversions de types. (~0.5 jour)
3. **`core/filter/expression_builder.py`** et `expression_sanitizer.py` -- Valider la construction d'expressions QGIS, les cas limites (caracteres speciaux, NULL, expressions vides). (~1 jour)
4. **`core/domain/exceptions.py`** -- Valider la hierarchie d'exceptions. (~0.5 jour)
5. **`ui/managers/dockwidget_signal_manager.py`** -- Valider la gestion des connexions/deconnexions. (~1 jour)

**Fichiers a creer** :
- `tests/unit/core/domain/test_domain_models.py`
- `tests/unit/core/domain/test_exceptions.py`
- `tests/unit/infrastructure/database/test_sql_utils.py`
- `tests/unit/core/filter/test_expression_builder.py`
- `tests/unit/ui/managers/test_signal_manager.py`

**Criteres d'acceptation** :
- Couverture de `core/domain/` >= 90%
- Couverture de `infrastructure/database/sql_utils.py` >= 80%
- Couverture de `core/filter/expression_builder.py` >= 75%
- Tous les tests passent localement et en CI

**Dependances** : A1 (structure de tests en place)

---

## PHASE 2 : ASSAINISSEMENT DE LA GESTION D'ERREURS

**Duree estimee** : 2 semaines
**Objectif** : Reduire les 1 232 `except Exception` a < 300, eliminer les exceptions silencieuses, et deployer la hierarchie d'exceptions metier.

### B1 : Eliminer les exceptions silencieuses (`except Exception: pass` ou equivalent)

**Priorite** : Haute
**Effort** : 2 jours
**Risque** : Faible -- remplacement par `logger.debug()` minimum

**Description** :
Identifier et corriger les blocs `except Exception` qui avalent silencieusement les erreurs (pattern `pass`, `continue` sans log, ou corps vide). Remplacer par un minimum de `logger.debug(f"Ignored in {context}: {e}")`.

**Methode** :
1. Grep multiline pour trouver les patterns `except Exception.*\n.*pass`
2. Classifier chaque occurrence :
   - **Intentionnel** (ex: teardown, cleanup) -- ajouter un commentaire et `logger.debug()`
   - **Bug masque** (ex: logique metier) -- remplacer par l'exception specifique
   - **Defensif excessif** (ex: validation) -- supprimer le try/except
3. Traiter fichier par fichier, en commencant par les plus critiques

**Fichiers prioritaires** (Top 10 par nombre d'occurrences) :
1. `filter_mate_dockwidget.py` (132)
2. `ui/controllers/integration.py` (120)
3. `ui/controllers/exploring_controller.py` (49)
4. `core/tasks/filter_task.py` (39)
5. `filter_mate_app.py` (29)
6. `filter_mate.py` (25)
7. `core/tasks/layer_management_task.py` (21)
8. `infrastructure/utils/layer_utils.py` (19)
9. `adapters/backends/ogr/expression_builder.py` (18)
10. `infrastructure/database/connection_pool.py` (17)

**Criteres d'acceptation** :
- Zero `except Exception: pass` dans le codebase
- Chaque `except Exception` avec `pass`/`continue` remplace par un log minimum
- Aucune regression (le plugin demarre, filtre, exporte)

**Dependances** : Aucune
**Bloque** : B2

---

### B2 : Specialiser les exceptions dans les modules de base de donnees

**Priorite** : Haute
**Effort** : 1 semaine
**Risque** : Moyen -- changer le type d'exception capture peut reveler des bugs latents

**Description** :
Remplacer les `except Exception` par des exceptions specifiques dans les couches d'acces aux donnees :

| Module | Exceptions specifiques |
|--------|----------------------|
| `adapters/backends/postgresql/` | `psycopg2.OperationalError`, `psycopg2.ProgrammingError`, `psycopg2.InterfaceError` |
| `adapters/backends/spatialite/` | `sqlite3.OperationalError`, `sqlite3.IntegrityError`, `sqlite3.DatabaseError` |
| `infrastructure/database/connection_pool.py` | `psycopg2.pool.PoolError`, `psycopg2.OperationalError`, `TimeoutError` |
| `infrastructure/database/sql_utils.py` | `sqlite3.OperationalError`, `ValueError` |

**Fichiers concernes** :
- `adapters/backends/postgresql/backend.py` (12)
- `adapters/backends/postgresql/expression_builder.py` (12)
- `adapters/backends/postgresql/schema_manager.py` (15)
- `adapters/backends/postgresql/cleanup.py` (14)
- `adapters/backends/postgresql/mv_manager.py` (10)
- `adapters/backends/spatialite/filter_executor.py` (10)
- `adapters/backends/spatialite/temp_table_manager.py` (13)
- `adapters/backends/spatialite/index_manager.py` (10)
- `infrastructure/database/connection_pool.py` (17)
- `infrastructure/database/sql_utils.py` (9)
- `infrastructure/database/prepared_statements.py` (7)

**Criteres d'acceptation** :
- Moins de 20 `except Exception` dans les modules DB (vs ~130 actuellement)
- Chaque `except` specifique documente l'erreur attendue
- Les tests d'integration des backends passent
- Le connection pool fonctionne sous charge

**Dependances** : B1 (connaitre les exceptions silencieuses d'abord)

---

### B2-bis : Enrichir la hierarchie d'exceptions metier

**Priorite** : Moyenne
**Effort** : 3 jours
**Risque** : Faible

**Description** :
Etendre `core/domain/exceptions.py` (actuellement 5 exceptions) avec une hierarchie complete :

```
FilterMateError (base)
  +-- FilterError
  |     +-- FilterExpressionError
  |     +-- FilterTimeoutError
  |     +-- FilterCancelledError
  +-- BackendError
  |     +-- PostgreSQLError
  |     +-- SpatialiteError
  |     +-- OGRError
  |     +-- BackendNotAvailableError (existe deja)
  +-- LayerError
  |     +-- LayerInvalidError (existe deja)
  |     +-- LayerNotFoundError
  |     +-- CRSMismatchError
  +-- ExportError
  |     +-- ExportPathError
  |     +-- ExportFormatError
  +-- ConfigurationError (existe deja)
  +-- ExpressionValidationError (existe deja)
  +-- SignalStateChangeError (existe deja)
```

**Fichiers concernes** :
- `core/domain/exceptions.py` (enrichir)
- Propagation progressive dans les modules concernes

**Criteres d'acceptation** :
- La hierarchie est definie dans `core/domain/exceptions.py`
- Au moins les modules DB (`adapters/backends/`) utilisent `BackendError` et ses sous-classes
- Les exceptions preservent le message et la cause originale (`raise ... from e`)
- Tests unitaires pour chaque exception

**Dependances** : Aucune (peut etre fait en parallele de B2)

---

### B3 : Auditer le ratio connect/disconnect des signaux Qt

**Priorite** : Haute
**Effort** : 2-3 jours
**Risque** : Moyen -- decouverte potentielle de fuites de signaux

**Description** :
Le ratio connect/disconnect est de 2.6:1 (267/104). Auditer chaque `.connect()` sans `.disconnect()` correspondant et classifier :

- **OK sans disconnect** : Signaux entre objets de meme duree de vie (parent-enfant Qt)
- **Fuite potentielle** : Signaux entre objets de durees de vie differentes (couches temporaires, taches)
- **A corriger** : Signaux connectes dans des boucles ou des handlers repetitifs sans deconnexion

**Fichiers prioritaires** :
- `filter_mate_dockwidget.py` (le plus de connexions)
- `filter_mate_app.py` (connexions de taches)
- `ui/controllers/exploring_controller.py` (connexions de couches)
- `ui/controllers/integration.py` (orchestration)

**Criteres d'acceptation** :
- Chaque `.connect()` sans `.disconnect()` est documente (commentaire expliquant pourquoi c'est OK)
- Les fuites identifiees sont corrigees
- Le ratio connect/disconnect est documente dans le code

**Dependances** : Aucune

---

## PHASE 3 : DECOMPOSITION DES GOD OBJECTS

**Duree estimee** : 4-6 semaines
**Objectif** : Reduire les deux God Objects sous 2 000 lignes chacun.

**PREREQUIS ABSOLU** : Phase 1 completee (tests versionnes et CI fonctionnelle). Ne pas commencer cette phase sans un filet de tests solide.

### C1 : Decomposer `FilterEngineTask` (5 884 lignes -> ~2 000 lignes + modules)

**Priorite** : Critique
**Effort** : 2-3 semaines
**Risque** : Eleve -- c'est le coeur du moteur de filtrage

**Description** :
`FilterEngineTask` gere simultanement le filtrage attributaire, spatial, l'export, l'undo/redo, le nettoyage des vues materialisees, la preparation des geometries, l'historique, et la gestion des couches memoire. La decomposition partielle est deja commencee (`builders/`, `collectors/`, `connectors/`, `dispatchers/`, `executors/`) mais le fichier principal reste a 5 884 lignes.

**Strategie de decomposition** :

| Composant a extraire | Lignes estimees | Module cible | Risque |
|----------------------|-----------------|--------------|--------|
| Export (streaming + batch) | ~600 | `core/tasks/export_handler.py` | Moyen |
| Undo/Redo + Historique | ~500 | `core/tasks/history_handler.py` | Faible |
| Nettoyage MV PostgreSQL | ~200 | `core/tasks/cleanup_handler.py` | Faible |
| Preparation geometries | ~400 | `core/tasks/geometry_handler.py` | Moyen |
| Gestion couches memoire | ~300 | `core/tasks/memory_layer_handler.py` | Moyen |
| Conversion expressions SL/PG | ~200 | Deja dans `expression_builder` | Faible |

Chaque extraction suit le pattern :
1. Ecrire les tests pour le bloc a extraire (utiliser les tests existants comme base)
2. Extraire dans un module avec une interface claire
3. Remplacer le code inline par un appel au module
4. Verifier que tous les tests passent
5. Commiter

**Fichiers concernes** :
- `core/tasks/filter_task.py` (source, 5 884 lignes)
- `core/tasks/export_handler.py` (a creer)
- `core/tasks/history_handler.py` (a creer)
- `core/tasks/cleanup_handler.py` (a creer)
- `core/tasks/geometry_handler.py` (a creer)
- `core/tasks/memory_layer_handler.py` (a creer)
- `core/tasks/__init__.py` (mettre a jour les exports)

**Criteres d'acceptation** :
- `filter_task.py` < 2 500 lignes
- Chaque module extrait < 600 lignes
- Zero regression sur les tests existants
- Le filtrage attributaire, spatial, l'export, et l'undo/redo fonctionnent
- Les performances de filtrage ne degradent pas (benchmarker avant/apres)

**Dependances** : Phase 1 (A1, A2) completee
**Bloque** : Aucun (les autres decompositions sont independantes)

---

### C2 : Decomposer `FilterMateDockWidget` (7 079 lignes -> ~2 000 lignes + sous-widgets)

**Priorite** : Critique
**Effort** : 2-3 semaines
**Risque** : Eleve -- c'est le point d'entree UI de tout le plugin

**Description** :
`FilterMateDockWidget` contient 279 methodes et melange logique d'UI, gestion de backends, indicateurs, optimisation PostgreSQL, splitter, icones. Des extractions ont deja eu lieu (`DockwidgetSignalManager`, `RasterExploringManager`, 13 controllers), mais le fichier reste massivement trop gros.

**Strategie de decomposition** :

| Composant a extraire | Lignes estimees | Module cible | Risque |
|----------------------|-----------------|--------------|--------|
| Backend indicators + UI | ~200 | `ui/widgets/backend_indicator_widget.py` | Faible |
| PostgreSQL optimization UI | ~250 | `ui/widgets/postgres_config_widget.py` | Faible |
| Splitter + Dimensions | ~400 | Deja partiellement dans `ui/layout/` | Faible |
| Icon loading | ~100 | Deja dans `ui/styles/icon_manager.py` | Faible |
| Layer combobox management | ~300 | `ui/widgets/layer_combobox_manager.py` | Moyen |
| Export UI | ~400 | `ui/widgets/export_panel_widget.py` | Moyen |
| Filter protection flags | ~200 | `ui/managers/filter_state_manager.py` | Moyen |

**Criteres d'acceptation** :
- `filter_mate_dockwidget.py` < 3 000 lignes (objectif ambitieux : 2 000)
- Chaque sous-widget < 500 lignes
- L'interface Qt Designer (.ui) n'est pas modifiee (les sous-widgets wrappent les widgets existants)
- Le plugin fonctionne identiquement avant/apres
- Les signaux sont correctement routes (pas de deconnexions cassees)

**Dependances** : Phase 1 (A1, A2) completee
**Bloque** : Aucun

---

### C3 : Auditer et documenter les `nosec B608`

**Priorite** : Moyenne
**Effort** : 2 jours
**Risque** : Faible

**Description** :
124 annotations `nosec B608` (SQL injection) dans le codebase. Auditer chaque occurrence et :
1. Documenter la justification dans un commentaire adjacent
2. Verifier que `sanitize_sql_identifier()` est appele en amont
3. Identifier les cas ou `psycopg2.sql.Identifier()` pourrait remplacer la construction manuelle

**Fichiers prioritaires** :
- `adapters/backends/postgresql/backend.py`
- `adapters/backends/postgresql/cleanup.py`
- `adapters/backends/postgresql/schema_manager.py`
- `adapters/backends/spatialite/` (multiples fichiers)
- `infrastructure/database/sql_utils.py`

**Criteres d'acceptation** :
- Chaque `nosec B608` a un commentaire justifiant la suppression
- Au moins 10 occurrences remplacees par `psycopg2.sql.Identifier()` dans le backend PostgreSQL
- Aucune regression

---

## PHASE 4 : ARCHITECTURE ET QUALITE

**Duree estimee** : 3 semaines
**Objectif** : Renforcer la purete hexagonale et la maintenabilite.

### D1 : Reduire le couplage QGIS dans `core/services/`

**Priorite** : Moyenne
**Effort** : 1-2 semaines
**Risque** : Moyen -- necessite de definir des ports pour toutes les fonctionnalites QGIS

**Description** :
20+ fichiers dans `core/services/` importent directement `qgis.core`. Introduire des abstractions dans `core/ports/` :

1. `core/ports/qgis_layer_port.py` -- abstraction pour QgsVectorLayer/QgsRasterLayer
2. `core/ports/qgis_project_port.py` -- abstraction pour QgsProject
3. `core/ports/qgis_canvas_port.py` -- abstraction pour iface/mapCanvas

Les services ne doivent recevoir que des ports. Les implementations concretes restent dans `adapters/qgis/`.

**Fichiers concernes** :
- `core/ports/` (nouveaux fichiers)
- `core/services/app_initializer.py`
- `core/services/geometry_preparer.py`
- `core/services/canvas_refresh_service.py`
- `core/services/task_management_service.py`
- `core/services/task_orchestrator.py`
- `core/services/backend_expression_builder.py`
- `core/services/backend_service.py`
- `core/services/datasource_manager.py`
- `core/services/layer_lifecycle_service.py`
- `core/services/layer_service.py`
- Et ~10 autres fichiers

**Criteres d'acceptation** :
- `core/services/` n'importe plus `qgis.core` directement (sauf via `TYPE_CHECKING`)
- Les ports sont definis avec des classes abstraites (`abc.ABC`)
- Les implementations concretes sont dans `adapters/qgis/`
- Le conteneur DI fournit les implementations aux services
- Tests unitaires des services executables SANS environnement QGIS

**Dependances** : Phase 3 (decomposition terminee pour eviter de refactorer des monolithes)

---

### D2 : Activer le conteneur DI pour les services principaux

**Priorite** : Moyenne
**Effort** : 1 semaine
**Risque** : Moyen

**Description** :
Le conteneur DI dans `infrastructure/di/container.py` est bien concu mais sous-utilise. Activer l'injection de dependances pour les 10 services les plus importants au lieu des imports directs.

**Fichiers concernes** :
- `infrastructure/di/container.py`
- `infrastructure/di/providers.py`
- `adapters/app_bridge.py`
- Les 10 services principaux dans `core/services/`

**Criteres d'acceptation** :
- Au moins 10 services injectes via le conteneur
- Les tests unitaires peuvent remplacer les implementations par des mocks
- Pas de regression fonctionnelle

**Dependances** : D1 (ports definis)

---

### D3 : Nettoyer les commentaires de version inline

**Priorite** : Basse
**Effort** : 1 jour
**Risque** : Nul

**Description** :
Supprimer les commentaires de type `# FIX v2.3.21`, `# CRASH FIX (v2.8.6)`, `# CRITICAL FIX v2.3.13` qui polluent le code. Conserver uniquement les explications du "pourquoi" (ex: "Apply pending subset strings on main thread because QgsVectorLayer is not thread-safe").

**Fichiers prioritaires** :
- `core/tasks/filter_task.py` (multiples occurrences)
- `infrastructure/database/connection_pool.py`
- `infrastructure/database/sql_utils.py`

**Criteres d'acceptation** :
- Zero commentaire de type `FIX v*.*.*` ou `CRASH FIX (v*.*.*)`
- Les explications techniques (le "pourquoi") sont preservees
- L'historique des corrections reste dans le CHANGELOG

---

### D4 : Reduire `max-line-length` a 120

**Priorite** : Basse
**Effort** : 2 jours
**Risque** : Faible (reformatage automatique avec Black)

**Description** :
Changer `max-line-length = 200` en `max-line-length = 120` dans `setup.cfg` et reformater le code avec Black.

**Fichiers concernes** :
- `setup.cfg`
- Potentiellement tous les fichiers Python (reformatage)

**Criteres d'acceptation** :
- `setup.cfg` : `max-line-length = 120`
- `black --check --line-length 120` passe sans erreur
- Aucune regression fonctionnelle

**Dependances** : Phases 1-3 (eviter les conflits de merge massifs pendant le refactoring)

---

## PHASE 5 : CONSOLIDATION FINALE

**Duree estimee** : 2 semaines
**Objectif** : Validation finale, documentation, et preparation release.

### E1 : Validation complete de non-regression

**Effort** : 3 jours

**Description** :
Executer l'integralite de la suite de tests (unit + integration + regression) et corriger les echecs. Tester manuellement les workflows critiques :
1. Filtrage attributaire simple sur couche PostgreSQL
2. Filtrage spatial avec buffer dynamique
3. Filtrage raster (pixel picker, rectangle range)
4. Export multi-format (Shapefile, GeoJSON, GeoPackage)
5. Undo/Redo (10 etats)
6. Changement de backend (auto, force PostgreSQL, force SpatiaLite)
7. Ouverture/fermeture de projet QGIS avec couches filtrees

### E2 : Mise a jour de la documentation

**Effort** : 2 jours

**Description** :
- Mettre a jour les memoires Serena (`.serena/memories/`)
- Mettre a jour `CHANGELOG.md`
- Mettre a jour `metadata.txt` (version, description)
- Mettre a jour `CONSOLIDATED_PROJECT_CONTEXT`
- Documenter les nouvelles exceptions metier
- Documenter les ports QGIS

### E3 : Metriques finales et rapport

**Effort** : 1 jour

Produire un rapport comparatif avant/apres :

| Metrique | Avant (10/02) | Objectif | Apres |
|----------|---------------|----------|-------|
| Tests dans le repo | 0 | 400+ | |
| Couverture | N/A | >= 75% | |
| `except Exception` | 1 232 | < 300 | |
| Plus gros fichier (prod) | 7 079 | < 3 000 | |
| `nosec B608` documentes | 0/124 | 124/124 | |
| Imports QGIS dans core/services | 20+ | 0 | |
| Score qualite | 3.0/5 | 4.0/5 | |

---

## PLANNING INDICATIF

```
Semaine 1  : Phase 0 (Quick Wins) + A1 (versionner tests)
Semaine 2  : A1-bis (CI) + A2 (tests critiques)
Semaine 3  : A2 (fin) + B1 (exceptions silencieuses)
Semaine 4  : B2 (exceptions DB) + B2-bis (hierarchie exceptions)
Semaine 5  : B2 (fin) + B3 (audit signaux) + Debut C1
Semaine 6  : C1 (decomposition FilterEngineTask)
Semaine 7  : C1 (suite)
Semaine 8  : C1 (fin) + Debut C2
Semaine 9  : C2 (decomposition FilterMateDockWidget)
Semaine 10 : C2 (suite)
Semaine 11 : C2 (fin) + C3 (audit nosec)
Semaine 12 : D1 (ports QGIS)
Semaine 13 : D1 (fin) + D2 (DI container)
Semaine 14 : D3 (commentaires) + D4 (line-length)
Semaine 15 : E1 (validation non-regression)
Semaine 16 : E2 (documentation) + E3 (metriques finales)
```

**Duree totale estimee** : 16 semaines (~4 mois) en rythme normal.

**Facteurs d'acceleration** :
- Si les tests existent deja et sont fonctionnels : -1 semaine sur Phase 1
- Si plusieurs developpeurs : C1 et C2 peuvent etre parallelises (-2 semaines)
- Si les exceptions silencieuses sont peu nombreuses : -1 semaine sur Phase 2

**Facteurs de ralentissement** :
- Si les tests doivent etre recrees : +2-3 semaines sur Phase 1
- Si la decomposition des God Objects revele des couplages non documentes : +1-2 semaines sur Phase 3
- Si des bugs latents apparaissent apres la specialisation des exceptions : +1 semaine sur Phase 2

---

## MATRICE DE RISQUES

| Action | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| Tests non retrouvables | Faible | Critique | Recreer les tests prioritaires depuis les memoires Serena |
| Regression lors decomposition FilterEngineTask | Moyenne | Eleve | Tests avant chaque extraction, commits atomiques, branches dediees |
| Regression lors decomposition Dockwidget | Moyenne | Eleve | Tests UI, signaux verifies, commits atomiques |
| Exceptions specifiques revelent des bugs | Haute | Moyen | Deployer progressivement, un module a la fois |
| Conflits de merge avec le dev en cours | Moyenne | Moyen | Branches courtes, merges frequents |
| Ports QGIS trop abstraits / sur-ingenierie | Faible | Moyen | Commencer par les 3 services les plus utilises |

---

## RECAPITULATIF DES ACTIONS PAR PRIORITE

### Immediat (cette semaine)
- [x] QW-1 : Deplacer imports `iface` (1h)
- [x] QW-2 : Mettre a jour `qgisMinimumVersion` (15min)
- [x] QW-3 : Creer `requirements-optional.txt` (15min)
- [x] A1 : Versionner `tests/` (2-4h)

### Sprint 1 (Semaines 1-3) -- Filet de securite
- [ ] A1-bis : Corriger la CI (2-4h)
- [ ] A2 : Ecrire tests critiques (1 semaine)
- [ ] QW-4 : Decorator `@main_thread_only` (1h30)

### Sprint 2 (Semaines 3-5) -- Assainissement erreurs
- [ ] B1 : Eliminer exceptions silencieuses (2 jours)
- [ ] B2 : Specialiser exceptions DB (1 semaine)
- [ ] B2-bis : Hierarchie exceptions metier (3 jours)
- [ ] B3 : Audit connect/disconnect signaux (2-3 jours)

### Sprint 3-4 (Semaines 5-11) -- Decomposition
- [ ] C1 : Decomposer `FilterEngineTask` (2-3 semaines)
- [ ] C2 : Decomposer `FilterMateDockWidget` (2-3 semaines)
- [ ] C3 : Auditer `nosec B608` (2 jours)

### Sprint 5 (Semaines 11-14) -- Architecture
- [ ] D1 : Ports QGIS dans `core/services/` (1-2 semaines)
- [ ] D2 : Activer le DI container (1 semaine)
- [ ] D3 : Nettoyer commentaires version (1 jour)
- [ ] D4 : `max-line-length = 120` (2 jours)

### Sprint 6 (Semaines 14-16) -- Consolidation
- [ ] E1 : Validation non-regression (3 jours)
- [ ] E2 : Documentation (2 jours)
- [ ] E3 : Metriques finales (1 jour)

---

## NOTES POUR LE DEVELOPPEUR

### Conventions de commits
Chaque action doit produire des commits atomiques avec le format :
```
refactor(scope): description courte

Description longue si necessaire.
Ref: IMPL-PLAN Action X.Y
```

### Branches
- Chaque phase majeure dans sa propre branche : `refactor/phase-1-tests`, `refactor/phase-2-errors`, etc.
- Merge dans `main` apres validation complete de la phase
- Pas de branches longues (> 1 semaine sans merge)

### Points de controle
- **Fin Phase 1** : Le CI est vert, les tests passent. Decision go/no-go pour Phase 3.
- **Fin Phase 2** : Les exceptions sont specialisees. Mesurer le nombre de bugs reveles.
- **Mi-Phase 3** : Apres la decomposition de `FilterEngineTask`, valider les performances avant de continuer avec le Dockwidget.
- **Fin Phase 4** : Les ports QGIS sont en place. Verifier que les tests unitaires n'ont plus besoin d'un environnement QGIS.
- **Fin Phase 5** : Score qualite >= 4.0/5. Release v5.0.0 ou v6.0.0.

---

**Document genere le 10 fevrier 2026 par Marco, GIS Lead Developer.**
**Base : Audit AUDIT_2026_02_10.md + validation du code source + memoires Serena.**
