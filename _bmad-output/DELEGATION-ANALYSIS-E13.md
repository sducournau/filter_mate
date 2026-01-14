# Phase E13 - Rapport d'Analyse de Délégation

**Date:** 14 janvier 2026  
**Analyse:** Méthodes restantes à déléguer dans FilterEngineTask  
**Objectif:** Réduire 4,718 lignes → ~600 lignes (-87%)

---

## 📋 RÉSUMÉ EXÉCUTIF

| Catégorie | Méthodes | Lignes | Complexité | Priorité |
|-----------|----------|--------|------------|----------|
| **AttributeFilterExecutor** | 9 | ~450 | Moyenne | HAUTE |
| **SpatialFilterExecutor** | 6 | ~350 | Élevée | HAUTE |
| **Cache Migration** | 8 usages | ~50 | Faible | MOYENNE |
| **Cleanup Legacy** | 15 | ~800 | Faible | BASSE |

**Total estimé à supprimer:** ~1,650 lignes  
**Réduction attendue:** 4,718 → 3,068 lignes (première passe)

---

## 🎯 CATÉGORIE 1: AttributeFilterExecutor (9 méthodes)

### ✅ Déjà Extraites (dans AttributeFilterExecutor)

Ces méthodes existent DÉJÀ dans AttributeFilterExecutor - il faut juste les DÉLÉGUER:

#### 1. `_process_qgis_expression` (lignes 1303-1368)
- **Taille:** 66 lignes
- **Fonction:** Valider et convertir expression QGIS → SQL
- **Dépendances:** QgsExpression, _qualify_field_names_in_expression
- **Action:** Déléguer à `AttributeFilterExecutor.process_qgis_expression()`
- **Déjà dans:** [core/tasks/executors/attribute_filter_executor.py](core/tasks/executors/attribute_filter_executor.py#L120-L185)

```python
# AVANT (FilterEngineTask):
def _process_qgis_expression(self, expression):
    # 66 lignes de validation/conversion...
    return expression, is_field_expression

# APRÈS (délégation):
def _process_qgis_expression(self, expression):
    executor = self._get_attribute_executor()
    return executor.process_qgis_expression(
        expression=expression,
        source_layer_fields=self.source_layer_fields_names,
        primary_key=self.primary_key_name,
        table_name=self.param_source_table,
        provider_type=self.param_source_provider_type
    )
```

---

#### 2. `_combine_with_old_subset` (lignes 1370-1392)
- **Taille:** 23 lignes
- **Fonction:** Combiner nouvelle expression avec filtre existant
- **Dépendances:** combine_with_old_subset (core.filter.expression_combiner)
- **Action:** Déléguer à `AttributeFilterExecutor.combine_with_old_subset()`
- **Déjà dans:** [core/tasks/executors/attribute_filter_executor.py](core/tasks/executors/attribute_filter_executor.py#L187-L209)

```python
# APRÈS:
def _combine_with_old_subset(self, expression):
    executor = self._get_attribute_executor()
    return executor.combine_with_old_subset(
        expression=expression,
        old_subset=self.param_source_old_subset,
        combine_operator=self._get_source_combine_operator(),
        provider_type=self.param_source_provider_type
    )
```

---

#### 3. `_build_feature_id_expression` (lignes 1393-1438)
- **Taille:** 46 lignes
- **Fonction:** Construire expression IN à partir de feature IDs
- **Dépendances:** build_feature_id_expression (core.filter.expression_builder)
- **Action:** Déléguer à `AttributeFilterExecutor.build_feature_id_expression()`
- **Déjà dans:** [core/tasks/executors/attribute_filter_executor.py](core/tasks/executors/attribute_filter_executor.py#L211-L256)

```python
# APRÈS:
def _build_feature_id_expression(self, features_list):
    executor = self._get_attribute_executor()
    return executor.build_feature_id_expression(
        features_list=features_list,
        primary_key_name=self.primary_key_name,
        table_name=self.param_source_table,
        provider_type=self.param_source_provider_type,
        is_numeric=self.task_parameters["infos"]["primary_key_is_numeric"],
        old_subset=self.param_source_old_subset,
        combine_operator=self._get_source_combine_operator()
    )
```

---

#### 4. `_try_v3_attribute_filter` (lignes 937-1022)
- **Taille:** 86 lignes
- **Fonction:** Essayer v3 TaskBridge pour filtre attributaire
- **Dépendances:** _task_bridge, BridgeStatus
- **Action:** Déléguer à `AttributeFilterExecutor.try_v3_attribute_filter()`
- **Déjà dans:** [core/tasks/executors/attribute_filter_executor.py](core/tasks/executors/attribute_filter_executor.py#L258-L343)

```python
# APRÈS:
def _try_v3_attribute_filter(self, task_expression, task_features):
    executor = self._get_attribute_executor()
    return executor.try_v3_attribute_filter(
        task_expression=task_expression,
        task_features=task_features,
        task_bridge=self._task_bridge,
        source_layer=self.source_layer,
        primary_key_name=self.primary_key_name,
        task_parameters=self.task_parameters
    )
```

---

#### 5. `_apply_filter_and_update_subset` (lignes 1455-1520)
- **Taille:** 66 lignes
- **Fonction:** Appliquer filtre et mettre à jour subset
- **Dépendances:** _apply_postgresql_type_casting, manage_layer_subset_strings
- **Action:** Déléguer à `AttributeFilterExecutor.apply_filter()`
- **Déjà dans:** [core/tasks/executors/attribute_filter_executor.py](core/tasks/executors/attribute_filter_executor.py#L345-L400)

```python
# APRÈS:
def _apply_filter_and_update_subset(self, expression):
    executor = self._get_attribute_executor()
    return executor.apply_filter(
        expression=expression,
        source_layer=self.source_layer,
        provider_type=self.param_source_provider_type,
        schema=self.param_source_schema,
        table=self.param_source_table,
        geom_field=self.param_source_geom,
        primary_key=self.primary_key_name,
        pending_requests=self._pending_subset_requests
    )
```

---

### 🔧 Méthodes Utilitaires Simples (4 méthodes)

#### 6. `_optimize_duplicate_in_clauses` (lignes 1449-1453)
- **Taille:** 5 lignes (simple delegation)
- **Action:** DÉJÀ déléguée à core.filter.expression_sanitizer
- **Status:** ✅ OK, pas de changement nécessaire

#### 7. `_format_pk_values_for_sql` (lignes 1440-1447)
- **Taille:** 8 lignes (delegation)
- **Action:** DÉJÀ déléguée à pg_executor
- **Status:** ✅ OK, garder fallback

#### 8. `_is_pk_numeric` (lignes 1433-1439)
- **Taille:** 7 lignes (delegation)
- **Action:** DÉJÀ déléguée à pg_executor
- **Status:** ✅ OK, garder fallback

#### 9. `execute_source_layer_filtering` (lignes 1522-1557)
- **Taille:** 36 lignes
- **Fonction:** Orchestrer filtrage source layer
- **Action:** DÉJÀ déléguée à SourceLayerFilterExecutor service
- **Status:** ✅ OK, pas de changement (orchestration level)

---

## 🌍 CATÉGORIE 2: SpatialFilterExecutor (6 méthodes)

### ✅ Déjà Extraites (dans SpatialFilterExecutor)

#### 1. `_organize_layers_to_filter` (lignes 770-807)
- **Taille:** 38 lignes
- **Fonction:** Organiser layers par provider type
- **Dépendances:** LayerOrganizer service
- **Action:** Déléguer à `SpatialFilterExecutor.organize_layers()`
- **Déjà dans:** [core/tasks/executors/spatial_filter_executor.py](core/tasks/executors/spatial_filter_executor.py#L90-L127)

```python
# APRÈS:
def _organize_layers_to_filter(self):
    executor = self._get_spatial_executor()
    result = executor.organize_layers(
        task_action=self.task_action,
        task_parameters=self.task_parameters,
        project=self.PROJECT
    )
    self.layers = result.layers_by_provider
    self.layers_count = result.layers_count
    self.provider_list = result.provider_list
```

---

#### 2. `_try_v3_spatial_filter` (lignes 1024-1080)
- **Taille:** 57 lignes
- **Fonction:** Essayer v3 TaskBridge pour filtre spatial
- **Dépendances:** _task_bridge, BridgeStatus
- **Action:** Déléguer à `SpatialFilterExecutor.try_v3_spatial_filter()`
- **Déjà dans:** [core/tasks/executors/spatial_filter_executor.py](core/tasks/executors/spatial_filter_executor.py#L129-L185)

```python
# APRÈS:
def _try_v3_spatial_filter(self, layer, layer_props, predicates):
    executor = self._get_spatial_executor()
    return executor.try_v3_spatial_filter(
        layer=layer,
        layer_props=layer_props,
        predicates=predicates,
        task_bridge=self._task_bridge,
        source_layer=self.source_layer
    )
```

---

#### 3. `_prepare_source_geometry_via_executor` (lignes 487-523)
- **Taille:** 37 lignes
- **Fonction:** Préparer géométrie source via executor
- **Dépendances:** BackendRegistry
- **Action:** Déléguer à `SpatialFilterExecutor.prepare_source_geometry()`
- **Déjà dans:** [core/tasks/executors/spatial_filter_executor.py](core/tasks/executors/spatial_filter_executor.py#L187-L223)

```python
# APRÈS:
def _prepare_source_geometry_via_executor(self, layer_info, feature_ids=None, buffer_value=None):
    executor = self._get_spatial_executor()
    return executor.prepare_source_geometry(
        layer_info=layer_info,
        backend_registry=self._backend_registry,
        feature_ids=feature_ids,
        buffer_value=buffer_value,
        source_layer=self.source_layer
    )
```

---

#### 4. `_prepare_geometries_by_provider` (lignes 1580-1645)
- **Taille:** 66 lignes
- **Fonction:** Préparer géométries pour chaque provider
- **Dépendances:** GeometryPreparerService
- **Action:** Déléguer à `SpatialFilterExecutor.prepare_geometries_by_provider()`
- **Déjà dans:** [core/tasks/executors/spatial_filter_executor.py](core/tasks/executors/spatial_filter_executor.py#L225-L290)

```python
# APRÈS:
def _prepare_geometries_by_provider(self, provider_list):
    executor = self._get_spatial_executor()
    result = executor.prepare_geometries_by_provider(
        provider_list=provider_list,
        source_layer=self.source_layer,
        task_parameters=self.task_parameters
    )
    # Apply results to task
    if 'postgresql' in provider_list and result.postgresql_geom:
        self.postgresql_source_geom = result.postgresql_geom
    if 'spatialite' in provider_list and result.spatialite_geom:
        self.spatialite_source_geom = result.spatialite_geom
    if 'ogr' in provider_list and result.ogr_geom:
        self.ogr_source_geom = result.ogr_geom
```

---

#### 5. `_prepare_source_geometry` (lignes 2792-2880)
- **Taille:** 89 lignes
- **Fonction:** Préparer géométrie source (orchestration legacy)
- **Dépendances:** prepare_spatialite_source_geom, prepare_postgresql_source_geom
- **Action:** Peut être simplifié en délégant aux méthodes spécifiques
- **Note:** Méthode d'orchestration - garder mais simplifier

```python
# APRÈS (simplifié):
def _prepare_source_geometry(self, layer_provider_type):
    executor = self._get_spatial_executor()
    if layer_provider_type == 'postgresql':
        return self.prepare_postgresql_source_geom()
    elif layer_provider_type == 'spatialite':
        return self.prepare_spatialite_source_geom()
    elif layer_provider_type == 'ogr':
        return self.prepare_ogr_source_geom()
    logger.warning(f"Unsupported provider: {layer_provider_type}")
```

---

#### 6. `prepare_spatialite_source_geom` (lignes 2004-2109)
- **Taille:** 106 lignes
- **Fonction:** Préparer géométrie source Spatialite
- **Dépendances:** SpatialiteSourceContext, spatialite backend
- **Action:** DÉJÀ déléguée à adapters.backends.spatialite
- **Status:** ✅ OK, garde delegation existante

---

## 💾 CATÉGORIE 3: Cache Migration (8 usages)

### Remplacer anciens caches par nouveaux wrappers

Les nouveaux wrappers GeometryCache et ExpressionCache sont déjà initialisés dans `__init__`:
```python
self.geom_cache = GeometryCache()
self.expr_cache = ExpressionCache()
```

**Actions:**
1. ✅ Aucun changement nécessaire - les wrappers délèguent automatiquement
2. ✅ `self.geom_cache.get()` → appelle `SourceGeometryCache.get()`
3. ✅ `self.expr_cache.get()` → appelle `QueryExpressionCache.get()`

**Status:** ✅ Migration automatique grâce au pattern delegation

---

## 🧹 CATÉGORIE 4: Cleanup Legacy (15 méthodes - PHASE 2)

Ces méthodes seront supprimées APRÈS avoir validé que la délégation fonctionne:

### Méthodes à Supprimer (Phase 7C - Cleanup)

1. `_qualify_field_names_in_expression` - ⚠️ Encore utilisée par _process_qgis_expression
2. `_apply_postgresql_type_casting` - ⚠️ Encore utilisée
3. `_get_source_combine_operator` - ⚠️ Encore utilisée
4. `qgis_expression_to_postgis` - ⚠️ Encore utilisée
5. `qgis_expression_to_spatialite` - ⚠️ Encore utilisée
6. `manage_layer_subset_strings` - ⚠️ Encore utilisée
7. ... (autres méthodes utilitaires)

**Note:** Ces méthodes doivent être MIGRÉES vers les executors avant suppression.

---

## 📊 PLAN D'EXÉCUTION RECOMMANDÉ

### Étape 7B (1-2h estimée): Délégation

**Ordre de priorité:**

1. **AttributeFilterExecutor (5 méthodes principales)** - 30 min
   - `_process_qgis_expression`
   - `_combine_with_old_subset`
   - `_build_feature_id_expression`
   - `_try_v3_attribute_filter`
   - `_apply_filter_and_update_subset`

2. **SpatialFilterExecutor (4 méthodes principales)** - 30 min
   - `_organize_layers_to_filter`
   - `_try_v3_spatial_filter`
   - `_prepare_source_geometry_via_executor`
   - `_prepare_geometries_by_provider`

3. **Test de Smoke** - 15 min
   - Vérifier imports
   - Vérifier pas de références circulaires
   - Commit intermédiaire

### Étape 7C (2-3h estimée): Cleanup & Réduction

1. **Migration utilitaires** (1h)
   - Migrer `_qualify_field_names_in_expression` → AttributeFilterExecutor
   - Migrer `_apply_postgresql_type_casting` → AttributeFilterExecutor
   - Migrer autres méthodes utilitaires

2. **Suppression code dupliqué** (30 min)
   - Supprimer méthodes déléguées
   - Nettoyer imports obsolètes

3. **Refactor méthode `run()`** (1h)
   - Simplifier orchestration principale
   - Utiliser executors systématiquement

4. **Validation finale** (30 min)
   - Tests
   - Vérifier réduction de lignes
   - Commit final

---

## 🎯 MÉTRIQUES CIBLES

| Métrique | Avant | Après 7B | Après 7C | Objectif |
|----------|-------|----------|----------|----------|
| **Lignes FilterEngineTask** | 4,718 | ~3,500 | ~600 | 600 |
| **Méthodes déléguées** | 4 | 13 | 25+ | 30+ |
| **Complexité cyclomatique** | Élevée | Moyenne | Faible | Faible |
| **Responsabilités** | 8+ | 4 | 2 | 1-2 |

---

## ⚠️ RISQUES & MITIGATION

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| **Références circulaires** | Haut | Faible | Imports locaux dans méthodes |
| **Perte de contexte task** | Haut | Moyen | Passer self en paramètre |
| **Régression fonctionnelle** | Haut | Faible | Tests smoke après chaque batch |
| **Performance** | Moyen | Faible | Lazy init déjà implémentée |

---

## 💡 RECOMMANDATIONS

### Pour Étape 7B (MAINTENANT):

✅ **Utiliser multi_replace_string_in_file** pour batch delegation
✅ **Déléguer 9 méthodes en parallèle** (gain de temps massif)
✅ **Commit intermédiaire** après chaque catégorie
✅ **Garder backward compatibility** (ne pas supprimer encore)

### Pour Étape 7C (APRÈS 7B):

⏳ **Migrer utilitaires** vers executors
⏳ **Supprimer code dupliqué** progressivement
⏳ **Tester chaque suppression** individuellement
⏳ **Garder fallbacks** pour compatibilité legacy

---

## 📌 ACTIONS IMMÉDIATES

**MAINTENANT (Option C - Hyper-Accéléré):**

1. ✅ Rapport d'analyse généré
2. 🚀 Exécuter batch delegation (9 méthodes)
3. 🧪 Test smoke
4. 📝 Commit 7B
5. 🎯 Continuer vers 7C

**Temps estimé total Phase E13:** 6h (vs 36h budgétées = **30h d'avance**)

---

**Prêt pour batch delegation ?** 🚀
