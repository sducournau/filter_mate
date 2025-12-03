# FilterMate - Roadmap

## 🎯 Vue d'ensemble

Ce document décrit la feuille de route de développement de FilterMate, organisée par priorité et phase d'implémentation.

**Version actuelle**: 1.9.0 (3 décembre 2025)  
**Objectif à court terme**: Version 2.0.0 avec améliorations critiques et documentation complète

---

## 🔴 URGENCE 1 - Corrections Critiques (Sprint 1-2 semaines)

### ✅ COMPLÉTÉ
- [x] Correction des icônes de géométrie dans les combobox
- [x] Optimisation du tri des couches dans `manage_project_layers()`
- [x] Refactorisation de la détection du type de provider

### 🔥 EN COURS
- [ ] **Gestion d'erreurs silencieuses** (2-3h)
  - Remplacer `except: pass` par du logging approprié
  - Fichiers: `config/config.py`, `modules/appTasks.py`
  - Impact: Meilleure traçabilité des erreurs

- [ ] **Amélioration du logging** (3-4h)
  - Rotation des logs (10 MB max, 5 backups)
  - Niveaux de log appropriés (debug, info, warning, error)
  - Format standardisé avec timestamps
  - Impact: Débogage facilité

- [ ] **Messages de feedback utilisateur** (4-6h)
  - Indicateurs de backend actif
  - Messages de progression pour opérations longues
  - Avertissements de performance pour grands datasets
  - Impact: UX améliorée

### 🧪 Tests Unitaires de Base (1 semaine)
- [ ] Infrastructure de tests
  - Configuration pytest
  - Mocks pour QGIS
  - Fixtures pour données de test
  
- [ ] Tests prioritaires
  - `geometry_type_to_string()`
  - `detect_layer_provider_type()`
  - `qgis_expression_to_postgis()`
  - `qgis_expression_to_spatialite()`

**Livrables Sprint 1**: Version 1.9.1 avec corrections critiques

---

## ⚠️ URGENCE 2 - Refactoring et Performance (Sprint 2-4 semaines)

### Refactoring Majeur
- [ ] **Décomposition de `execute_geometric_filtering`** (1 semaine)
  - Actuellement: 395 lignes, complexité >40
  - Objectif: <50 lignes par méthode, complexité <10
  - Créer méthodes spécialisées:
    - `_execute_postgresql_geometric_filter()`
    - `_execute_spatialite_geometric_filter()`
    - `_execute_ogr_geometric_filter()`
    - `_build_sql_expression()`
  - Impact: Maintenabilité ++, testabilité ++

- [ ] **Externalisation des styles UI** (2-3 jours)
  - Créer `resources/styles.qss`
  - Remplacer les 527 lignes de styles inline dans `manage_ui_style()`
  - Support mode sombre/clair
  - Impact: Lisibilité du code, personnalisation

### Optimisations Performance
- [ ] **Cache d'icônes statique** (2h)
  - Mémoïzation dans `icon_per_geometry_type()`
  - Gain: Évite recalculs répétés
  
- [ ] **Prepared Statements pour SQL** (1 semaine)
  - Réutilisation de requêtes paramétrées
  - Particulièrement pour PostgreSQL
  - Gain: 20-30% sur requêtes répétées

- [ ] **Lazy Loading des propriétés de couches** (3-4 jours)
  - Charger uniquement les propriétés nécessaires
  - Pagination pour grandes listes
  - Gain: Temps de démarrage réduit

### Architecture
- [ ] **Pattern Strategy pour backends** (1 semaine)
  - Classes `PostgreSQLStrategy`, `SpatialiteStrategy`, `OGRStrategy`
  - Interface commune `BackendStrategy`
  - Simplification de la logique conditionnelle
  - Impact: Extensibilité, ajout de nouveaux backends facilité

**Livrables Sprint 2**: Version 1.10.0 avec refactoring majeur

---

## 🚀 URGENCE 3 - Nouvelles Fonctionnalités (Sprint 3-6 semaines)

### Historique et Undo/Redo (1 semaine)
- [ ] Classe `FilterHistory`
- [ ] Boutons UI Undo/Redo
- [ ] Raccourcis Ctrl+Z / Ctrl+Y
- [ ] Persistance entre sessions
- **Impact**: UX majeur, récupération d'erreurs

### Favoris de Filtres (1 semaine)
- [ ] Base de données de favoris (Spatialite)
- [ ] UI de gestion des favoris
- [ ] Import/Export JSON
- [ ] Partage entre projets
- **Impact**: Productivité ++

### Mode Batch (1 semaine)
- [ ] Sélection multiple de couches
- [ ] Application de filtre identique
- [ ] Filtrage par regex sur noms de champs
- [ ] Barre de progression globale
- **Impact**: Gain de temps pour traitements répétitifs

### Statistiques Post-Filtrage (3-4 jours)
- [ ] Compteur avant/après filtrage
- [ ] Statistiques sur champs numériques (min, max, avg, sum)
- [ ] Export statistiques (CSV/JSON)
- [ ] Graphiques simples (matplotlib)
- **Impact**: Analyse de données facilitée

### Prévisualisation Spatiale (1 semaine)
- [ ] Mode "Preview" avec couche temporaire
- [ ] Affichage différencié (style semi-transparent)
- [ ] Bouton "Appliquer définitivement"
- [ ] Annulation facile
- **Impact**: Validation avant application

### Templates de Filtres (3-4 jours)
- [ ] Format JSON pour templates
- [ ] Bibliothèque de templates pré-configurés
- [ ] UI de gestion
- [ ] Marketplace communautaire (optionnel)
- **Impact**: Réutilisabilité, partage

**Livrables Sprint 3**: Version 2.0.0 avec fonctionnalités majeures

---

## 📚 URGENCE 3 - Documentation (Parallèle Sprint 1-3)

### Documentation Utilisateur (2 semaines)
- [ ] **Setup Docusaurus** (2 jours)
  - Installation et configuration
  - Thème personnalisé
  - CI/CD GitHub Pages

- [ ] **Contenu de base** (1 semaine)
  - Introduction et Quick Start
  - Guide d'installation
  - Guide utilisateur complet
  - Tutoriels pas-à-pas
  - Screenshots et vidéos

- [ ] **Référence technique** (3-4 jours)
  - Raccourcis clavier
  - Expressions QGIS
  - Prédicats spatiaux
  - Options de configuration
  - FAQ

### Documentation Développeur (1 semaine)
- [ ] Architecture détaillée
- [ ] Documentation API (Sphinx)
- [ ] Guide de contribution
- [ ] Guide de développement
- [ ] Standards de code
- [ ] Guide de test

**Livrables**: Site documentation complet sur GitHub Pages

---

## 🔒 URGENCE 3 - Sécurité (Sprint 2-3)

### Corrections Sécurité (3-4 jours)
- [ ] **Prévention injection SQL**
  - Utiliser paramètres plutôt que concaténation
  - Validation des entrées utilisateur
  - Échappement approprié

- [ ] **Validation chemins de fichiers**
  - Vérifier permissions d'écriture
  - Sanitization des noms de fichiers
  - Prévention path traversal

- [ ] **Audit dépendances**
  - Vérifier versions psycopg2, PyQt5
  - Scan vulnérabilités (safety, bandit)

**Impact**: Protection contre attaques

---

## 📊 URGENCE 4 - Qualité et Tests (Continu)

### Suite de Tests Complète (Intégration continue)
- [ ] Tests unitaires (80% coverage)
- [ ] Tests d'intégration
- [ ] Tests de performance
- [ ] Tests UI (pytest-qt)

### Benchmarks Performance (1 semaine)
- [ ] Infrastructure de benchmarking
- [ ] Tests sur différents datasets
  - Petit (<1k features)
  - Moyen (1k-100k features)
  - Grand (>100k features)
- [ ] Comparaison backends
- [ ] Documentation des résultats

### CI/CD (3-4 jours)
- [ ] GitHub Actions
  - Tests automatiques sur PR
  - Linting (flake8, black)
  - Tests multi-versions QGIS
  - Build et publication plugin

---

## 🎨 URGENCE 4 - UX Avancée (Sprint 4+)

### Améliorations UI (2 semaines)
- [ ] Mode sombre/clair
- [ ] Thèmes personnalisables
- [ ] Tooltips contextuels
- [ ] Raccourcis clavier complets
- [ ] Groupes repliables dans combobox
- [ ] Drag & drop pour réorganiser

### Accessibilité (1 semaine)
- [ ] Support lecteur d'écran
- [ ] Navigation clavier complète
- [ ] Contrastes suffisants
- [ ] Textes redimensionnables

---

## 🔮 FUTURE - Vision Long Terme (Post v2.0)

### Phase 4 - Intelligence (Q2 2026)
- [ ] Suggestions de filtres basées sur les données
- [ ] Détection automatique de corrélations spatiales
- [ ] Machine learning pour optimisation de requêtes
- [ ] Assistant de requête en langage naturel

### Phase 5 - Collaboration (Q3 2026)
- [ ] Partage de filtres en temps réel
- [ ] Commentaires et annotations
- [ ] Versioning des configurations
- [ ] Intégration avec services cloud

### Phase 6 - Extensibilité (Q4 2026)
- [ ] Système de plugins pour FilterMate
- [ ] API REST pour intégrations externes
- [ ] Support de nouveaux backends (MongoDB, Elasticsearch)
- [ ] Export vers formats big data (Parquet, Arrow)

---

## 📈 Métriques de Succès

### Qualité Code
- Complexité cyclomatique moyenne: <10 (actuellement >30)
- Coverage tests: >80% (actuellement 0%)
- Duplication code: <3% (actuellement ~15%)

### Performance
- Filtrage <1k features: <100ms (tous backends)
- Filtrage 10k-100k features: <2s (PostgreSQL), <5s (Spatialite)
- Temps démarrage plugin: <500ms

### Documentation
- 100% des fonctionnalités documentées
- Minimum 10 tutoriels complets
- Vidéos démo pour cas d'usage principaux

### Adoption
- 500+ téléchargements sur QGIS Plugin Repository (6 mois)
- 10+ contributeurs GitHub
- 4.5+ étoiles sur QGIS plugins

---

## 🤝 Contribution

Ce roadmap est évolutif. Les contributions et suggestions sont bienvenues !

- **Issues**: Pour signaler bugs ou proposer fonctionnalités
- **Pull Requests**: Voir [CONTRIBUTING.md](CONTRIBUTING.md)
- **Discussions**: Pour questions et suggestions

---

**Dernière mise à jour**: 3 décembre 2025  
**Prochaine révision**: 1er janvier 2026
