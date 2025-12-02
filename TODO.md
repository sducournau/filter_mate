# TODO - Migration FilterMate vers Support Multi-Backend

## 🎯 Vue d'ensemble
Rendre FilterMate fonctionnel sans dépendance PostgreSQL obligatoire, en utilisant Spatialite comme backend alternatif.

---

## 📋 Phase 1: Import Conditionnel PostgreSQL (PRIORITÉ CRITIQUE)
**Durée estimée**: 1 jour  
**Complexité**: 🟢 Faible

### ✅ Tâches
- [ ] **T1.1** Modifier `modules/appUtils.py`
  - [ ] Ligne 2: Rendre import `psycopg2` conditionnel
  - [ ] Ajouter flag `POSTGRESQL_AVAILABLE = True/False`
  - [ ] Ajouter `psycopg2 = None` si non disponible
  - [ ] Tests: importer module sans psycopg2 installé

- [ ] **T1.2** Modifier `modules/appTasks.py`
  - [ ] Ligne 9: Rendre import `psycopg2` conditionnel
  - [ ] Utiliser même pattern que appUtils.py
  - [ ] Tests: importer module sans psycopg2 installé

- [ ] **T1.3** Adapter fonction `get_datasource_connexion_from_layer()`
  - [ ] Ajouter vérification `if not POSTGRESQL_AVAILABLE: return None, None`
  - [ ] Ajouter vérification `if layer.providerType() != 'postgres': return None, None`
  - [ ] Tests: appeler fonction sans PostgreSQL

- [ ] **T1.4** Tests Phase 1
  - [ ] Test unitaire: import modules sans psycopg2
  - [ ] Test intégration: démarrage plugin QGIS
  - [ ] Test: charger couche Shapefile sans erreur
  - [ ] Commit: `feat: Make PostgreSQL optional dependency`

### 🎯 Critères de succès Phase 1
- Plugin démarre sans erreur si psycopg2 absent
- Aucune exception ImportError
- Fonctionnalités basiques accessibles

---

## 📋 Phase 2: Backend Spatialite (PRIORITÉ HAUTE)
**Durée estimée**: 3-5 jours  
**Complexité**: 🔴 Élevée

### ✅ Tâches

#### **T2.1** Créer fonction `create_temp_spatialite_table()`
**Fichier**: `modules/appTasks.py` (après ligne ~440)

- [ ] Implémenter fonction complète (voir MIGRATION_GUIDE.md)
- [ ] Paramètres: `db_path, table_name, sql_query, geom_field`
- [ ] Gestion connexion SQLite + extension Spatialite
- [ ] Support Windows: `mod_spatialite.dll`
- [ ] Support Linux/Mac: `mod_spatialite.so`
- [ ] Création table temporaire
- [ ] Création index spatial R-tree
- [ ] Création index clé primaire
- [ ] Gestion erreurs complète
- [ ] Tests: créer table temp avec géométries

#### **T2.2** Créer fonction `qgis_expression_to_spatialite()`
**Fichier**: `modules/appTasks.py` (après ligne ~390)

- [ ] Implémenter fonction (voir MIGRATION_GUIDE.md)
- [ ] Mapper expressions QGIS → SQL Spatialite
- [ ] Gérer fonctions spatiales (ST_Buffer, etc.)
- [ ] Tests: conversion expressions courantes

#### **T2.3** Adapter `prepare_postgresql_source_geom()`
**Fichier**: `modules/appTasks.py` (ligne ~389)

- [ ] Dupliquer logique pour `prepare_spatialite_source_geom()`
- [ ] Adapter construction expression géométrique
- [ ] Gérer transformations CRS (ST_Transform)
- [ ] Tests: préparation géométrie Spatialite

#### **T2.4** Modifier `execute_geometric_filtering()`
**Fichier**: `modules/appTasks.py` (ligne ~562)

- [ ] Ajouter branche conditionnelle Spatialite
- [ ] Pattern: `elif param_source_provider_type == 'spatialite':`
- [ ] Construction expressions prédicats spatiaux
- [ ] Intégration avec table temporaire
- [ ] Tests: filtrage intersection/buffer Spatialite

#### **T2.5** Remplacer vues matérialisées PostgreSQL
**Fichier**: `modules/appTasks.py`

Lignes à modifier:
- [ ] Ligne 1139: CREATE MATERIALIZED VIEW
- [ ] Ligne 1188: CREATE MATERIALIZED VIEW (avec buffer)
- [ ] Ligne 1202: CREATE MATERIALIZED VIEW (variante)
- [ ] Ligne 1341: CREATE MATERIALIZED VIEW

Pattern à appliquer partout:
```python
if provider == 'postgresql' and POSTGRESQL_AVAILABLE:
    # Code PostgreSQL existant
elif provider == 'spatialite':
    # Nouveau code Spatialite
else:
    # Fallback QGIS existant
```

- [ ] Tests: création table temp Spatialite vs vue PostgreSQL

#### **T2.6** Tests Phase 2
- [ ] Test unitaire: `create_temp_spatialite_table()`
- [ ] Test unitaire: `qgis_expression_to_spatialite()`
- [ ] Test intégration: filtrage expression Spatialite
- [ ] Test intégration: filtrage géométrique Spatialite
- [ ] Test intégration: buffer + intersection
- [ ] Benchmark performances (1k, 10k, 100k features)
- [ ] Commit: `feat: Add Spatialite backend for geometric filtering`

### 🎯 Critères de succès Phase 2
- Filtrage géométrique fonctionne avec Spatialite
- Tables temporaires créées correctement
- Index spatiaux actifs
- Performances acceptables (< 5s pour 10k features)
- Code bien structuré et documenté

---

## 📋 Phase 3: Intégration & Documentation (PRIORITÉ MOYENNE)
**Durée estimée**: 2-3 jours  
**Complexité**: 🟡 Moyenne

### ✅ Tâches

#### **T3.1** Adapter `filter_mate_app.py`
**Fichier**: `filter_mate_app.py`

- [ ] Ligne ~890: Vérifier `POSTGRESQL_AVAILABLE` avant accès `project_datasources['postgresql']`
- [ ] Ajouter message warning si couches PostgreSQL mais psycopg2 absent
- [ ] Ajouter message info backend utilisé (PostgreSQL/Spatialite)
- [ ] Tests: comportement avec/sans PostgreSQL

#### **T3.2** Configuration
**Fichier**: `config/config.json`

- [ ] Ajouter option `"POSTGRESQL_ENABLED": true`
- [ ] Ajouter option `"FALLBACK_TO_SPATIALITE": true`
- [ ] Ajouter option `"WARN_PERFORMANCE_DEGRADATION": true`
- [ ] Ajouter option `"MAX_FEATURES_MEMORY_FILTER": 50000`
- [ ] Tests: lecture configuration

#### **T3.3** Messages utilisateur
- [ ] Warning si dataset > 50k features sans PostgreSQL
- [ ] Info backend utilisé dans logs
- [ ] Message pédagogique installation PostgreSQL
- [ ] Tests: affichage messages

#### **T3.4** Documentation utilisateur
- [ ] Mettre à jour `README.md`
  - [ ] Section "Installation" simplifiée
  - [ ] Section "Sans PostgreSQL"
  - [ ] Section "Avec PostgreSQL" (performances)
  - [ ] Tableau comparatif backends
  - [ ] Recommandations par taille dataset

- [ ] Créer `docs/POSTGRESQL_SETUP.md` (optionnel)
  - [ ] Guide installation PostgreSQL/PostGIS
  - [ ] Configuration connexion QGIS
  - [ ] Bonnes pratiques

#### **T3.5** Tests complets
- [ ] Suite tests unitaires complète
  - [ ] Test import modules
  - [ ] Test fonctions Spatialite
  - [ ] Test expressions spatiales
  
- [ ] Suite tests intégration
  - [ ] Workflow complet Shapefile
  - [ ] Workflow complet GeoPackage
  - [ ] Workflow complet Spatialite
  - [ ] Workflow mixte (plusieurs sources)
  
- [ ] Tests régression PostgreSQL
  - [ ] Workflow complet PostgreSQL inchangé
  - [ ] Benchmark performances identiques
  - [ ] Fonctionnalités avancées OK

- [ ] Commit: `test: Add comprehensive multi-backend test suite`

### 🎯 Critères de succès Phase 3
- Documentation complète et claire
- Tous tests passent (unitaires + intégration)
- Messages utilisateur appropriés
- Pas de régression PostgreSQL

---

## 📋 Phase 4: Optimisation & Polissage (PRIORITÉ BASSE)
**Durée estimée**: 3-5 jours  
**Complexité**: 🟡 Moyenne

### ✅ Tâches

#### **T4.1** Auto-détection backend optimal
- [ ] Fonction `select_optimal_backend(layer, operation)`
- [ ] Critères: type source, taille dataset, opération
- [ ] Préférence: PostgreSQL > Spatialite > QGIS Memory
- [ ] Tests: sélection correcte selon contexte

#### **T4.2** Cache résultats intermédiaires
- [ ] Implémenter cache requêtes spatiales
- [ ] Invalidation cache si données modifiées
- [ ] Nettoyage périodique tables temporaires
- [ ] Tests: amélioration performances

#### **T4.3** Optimisation index Spatialite
- [ ] Index R-tree systématiques
- [ ] VACUUM après création tables temp
- [ ] ANALYZE pour statistiques
- [ ] Tests: gains performances

#### **T4.4** GeoPackage comme format intermédiaire (optionnel)
- [ ] Alternative à Spatialite pour grandes données
- [ ] Format standard OGC
- [ ] Support natif QGIS
- [ ] Tests: performances vs Spatialite

#### **T4.5** Benchmarks détaillés
- [ ] Script benchmark automatisé
- [ ] Datasets test: 1k, 10k, 100k, 1M features
- [ ] Opérations: expression, buffer, intersection, union
- [ ] Rapport Markdown généré
- [ ] Commit: `perf: Optimize Spatialite backend with caching`

### 🎯 Critères de succès Phase 4
- Performances optimales Spatialite
- Sélection backend intelligente
- Benchmarks documentés
- Code propre et maintenable

---

## 📋 Phase 5: Déploiement & Feedback (PRIORITÉ BASSE)
**Durée estimée**: 1-2 semaines  
**Complexité**: 🟢 Faible

### ✅ Tâches

#### **T5.1** Version Beta
- [ ] Créer branche `feature/spatialite-backend`
- [ ] Merge toutes modifications
- [ ] Tests complets
- [ ] Tag `v1.9.0-beta1`
- [ ] Release notes

#### **T5.2** Tests utilisateurs
- [ ] Sélectionner 5-10 beta testeurs
- [ ] Guide test détaillé
- [ ] Collecte feedback (GitHub Issues)
- [ ] Corrections bugs identifiés

#### **T5.3** Version Stable
- [ ] Corrections finales
- [ ] Validation complète
- [ ] Merge dans `main`
- [ ] Update `metadata.txt` version 1.9
- [ ] Tag `v1.9.0`
- [ ] Release GitHub

#### **T5.4** Communication
- [ ] Changelog détaillé
- [ ] Post blog/forum QGIS
- [ ] Update page GitHub
- [ ] Notification utilisateurs existants

### 🎯 Critères de succès Phase 5
- Beta testée par >5 utilisateurs
- 0 bugs critiques
- Feedback positif majoritaire
- Version stable publiée

---

## 🐛 Bugs Connus / À Suivre

### À investiguer
- [ ] Performance Spatialite sur datasets > 100k features
- [ ] Compatibilité Windows vs Linux/Mac (extensions Spatialite)
- [ ] Gestion mémoire tables temporaires nombreuses
- [ ] Interaction avec autres plugins QGIS

### À documenter
- [ ] Limitations connues Spatialite vs PostgreSQL
- [ ] Workarounds problèmes courants
- [ ] FAQ utilisateurs

---

## 📊 Métriques de Suivi

### Code
- Lignes modifiées: ~150-200
- Fonctions créées: ~5-10
- Tests ajoutés: ~20-30
- Couverture tests: Objectif >80%

### Performances (objectifs)
- Démarrage plugin: < 2s
- Filtrage 1k features: < 1s
- Filtrage 10k features: < 5s
- Filtrage 100k features: < 30s

### Qualité
- 0 erreur critique
- 0 régression PostgreSQL
- Documentation complète
- Code reviewé

---

## 🔗 Ressources

### Documentation créée
- ✅ `AUDIT_FILTERMATE.md` - Analyse complète
- ✅ `SERENA_PROJECT_CONFIG.md` - Configuration projet
- ✅ `MIGRATION_GUIDE.md` - Guide détaillé migration
- ✅ `TODO.md` - Ce fichier

### Documentation à créer
- [ ] `docs/TESTING.md` - Guide tests
- [ ] `docs/BENCHMARKS.md` - Résultats benchmarks
- [ ] `docs/POSTGRESQL_SETUP.md` - Setup PostgreSQL (optionnel)

### Liens externes
- [Spatialite SQL Reference](https://www.gaia-gis.it/gaia-sins/spatialite-sql-latest.html)
- [QGIS PyQGIS Cookbook](https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/)
- [PostGIS Documentation](https://postgis.net/docs/)

---

## 🎉 Célébrations

### Jalons
- [ ] 🎯 Phase 1 complète: Plugin fonctionne sans psycopg2
- [ ] 🚀 Phase 2 complète: Backend Spatialite fonctionnel
- [ ] 📝 Phase 3 complète: Documentation et tests complets
- [ ] ⚡ Phase 4 complète: Optimisations implémentées
- [ ] 🏆 Phase 5 complète: Version stable publiée

### Remerciements
- Équipe développement FilterMate
- Beta testeurs
- Communauté QGIS
- Mainteneurs Spatialite

---

**Document créé**: 2 décembre 2025  
**Dernière mise à jour**: 2 décembre 2025  
**Prochaine révision**: Après Phase 1  
**Responsable**: Équipe FilterMate
