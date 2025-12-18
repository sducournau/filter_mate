---
sidebar_position: 100
---

# Journal des modifications

Toutes les modifications notables de FilterMate sont documentées ici.

## [2.3.7] - 18 décembre 2025 - Amélioration de la Stabilité du Changement de Projet

### 🛡️ Améliorations de Stabilité
- **Gestion Améliorée du Changement de Projet** - Réécriture complète de la détection de changement de projet
  - Force le nettoyage de l'état du projet précédent avant réinitialisation
  - Vide le cache des couches, la file de tâches et tous les drapeaux d'état
  - Réinitialise les références de couches du dockwidget pour éviter les données périmées

- **Nouveau Gestionnaire de Signal `cleared`** - Nettoyage approprié à la fermeture/effacement du projet
  - Assure la réinitialisation de l'état du plugin quand le projet est fermé ou qu'un nouveau projet est créé
  - Désactive les widgets UI en attendant les nouvelles couches

- **Constantes de Timing Mises à Jour** - Délais améliorés pour une meilleure stabilité avec PostgreSQL

### ✨ Nouvelles Fonctionnalités
- **Forcer le Rechargement des Couches (Raccourci F5)** - Rechargement manuel quand le changement de projet échoue
  - Appuyez sur F5 dans le dockwidget pour forcer un rechargement complet
  - Affiche un indicateur de statut pendant le rechargement ("⟳")
  - Option de récupération utile quand la détection automatique échoue

### 🐛 Corrections de Bugs
- **Correction du Non-Rechargement des Couches au Changement de Projet** - Nettoyage plus agressif
- **Correction du Dockwidget Non Mis à Jour Après Changement de Projet** - Réinitialisation complète
- **Correction du Problème de Timing des Signaux** - QGIS émet `layersAdded` AVANT la fin de `projectRead`

---

## [2.3.6] - 18 décembre 2025 - Stabilité du Chargement de Projet et Couches

### 🛡️ Améliorations de Stabilité
- **Constantes de Timing Centralisées** - Toutes les valeurs dans le dict `STABILITY_CONSTANTS`
  - `MAX_ADD_LAYERS_QUEUE`: 50 (empêche le débordement mémoire)
  - `FLAG_TIMEOUT_MS`: 30000 (timeout de 30 secondes pour les drapeaux périmés)

- **Drapeaux avec Horodatage** - Détection et réinitialisation automatique des drapeaux périmés
  - Empêche le plugin de rester bloqué en état "chargement"
  - Réinitialise automatiquement les drapeaux après 30 secondes

- **Validation des Couches** - Meilleure validation des objets C++
  - Empêche les crashs lors de l'accès à des couches supprimées

- **Anti-Rebond des Signaux** - Gestion des signaux rapides
  - Limite de taille de file avec élagage automatique (FIFO)
  - Gestion gracieuse des changements rapides de projet/couches

### 🐛 Corrections de Bugs
- **Correction des Drapeaux Bloqués** - Réinitialisation automatique après 30 secondes
- **Correction du Débordement de File** - File add_layers limitée à 50 éléments
- **Correction de la Récupération d'Erreur** - Drapeaux réinitialisés correctement

---

## [2.3.5] - 17 décembre 2025 - Qualité du Code et Configuration v2.0

### 🛠️ Système de Feedback Centralisé
- **Notifications Unifiées** - Feedback utilisateur cohérent dans tous les modules
  - Nouvelles fonctions `show_info()`, `show_warning()`, `show_error()`, `show_success()`
  - Fallback gracieux quand iface n'est pas disponible

### ⚡ Optimisation Init PostgreSQL
- **Chargement 5-50× Plus Rapide** - Initialisation plus intelligente
  - Vérification de l'existence des index avant création
  - Cache des connexions par source de données
  - CLUSTER différé au moment du filtrage
  - ANALYZE conditionnel seulement si pas de statistiques

### ⚙️ Système de Configuration v2.0
- **Structure de Métadonnées Intégrée** - Métadonnées directement dans les paramètres
- **Migration Automatique de Configuration** - Système de migration v1.0 → v2.0
- **Respect du Backend Forcé** - Le choix utilisateur est strictement respecté (pas de fallback vers OGR)

### 🐛 Corrections de Bugs
- **Correction d'Erreurs de Syntaxe** - Parenthèses non fermées corrigées
- **Correction des Clauses Except Génériques** - Gestion d'exception spécifique

### 🧹 Qualité du Code
- **Amélioration du Score** : 8.5 → 8.9/10

---

## [2.3.4] - 16 décembre 2025 - Correction Référence Table PostgreSQL 2 Parties

### 🐛 Corrections de Bugs
- **CRITIQUE : Correction des références de table PostgreSQL 2 parties** - Le filtrage spatial fonctionne maintenant correctement avec les tables utilisant le format `"table"."geom"`
- **Correction des résultats GeometryCollection des tampons** - Extraction et conversion correctes en MultiPolygon
- **Correction de l'erreur virtual_id PostgreSQL** - Erreur informative pour les couches sans clé primaire

### ✨ Nouvelles Fonctionnalités
- **Sélection intelligente du champ d'affichage** - Les nouvelles couches sélectionnent automatiquement le meilleur champ descriptif (name, label, titre, etc.)
- **ANALYZE automatique sur les tables sources** - Le planificateur de requêtes PostgreSQL a maintenant des statistiques correctes

### ⚡ Améliorations de Performance
- **Chargement ~30% Plus Rapide des Couches PostgreSQL**
  - Comptage rapide avec `pg_stat_user_tables` (500× plus rapide que COUNT(*))
  - Vues matérialisées UNLOGGED (30-50% plus rapide)

---

## [2.3.3] - 15 décembre 2025 - Correction Auto-Activation au Chargement de Projet

### 🐛 Corrections de Bugs
- **CRITIQUE : Correction de l'auto-activation au chargement de projet** - Le plugin s'active maintenant correctement au chargement d'un projet QGIS contenant des couches vecteur

---

## [2.3.2] - 15 décembre 2025 - Sélecteur de Backend Interactif

### ✨ Nouvelles Fonctionnalités
- **Sélecteur de Backend Interactif** - L'indicateur de backend est maintenant cliquable pour forcer manuellement un backend
  - Cliquez sur le badge pour ouvrir le menu contextuel
  - Backends forcés marqués avec le symbole ⚡
  - Préférences de backend par couche

- **🎯 Auto-sélection des Backends Optimaux** - Optimisation automatique de toutes les couches
  - Analyse les caractéristiques de chaque couche (type de provider, nombre d'entités)
  - Sélectionne intelligemment le meilleur backend

### 🎨 Améliorations de l'Interface
- **Indicateur de Backend Amélioré**
  - Effet de survol avec changement de curseur
  - Feedback visuel avec symbole ⚡ pour les backends forcés

---

## [2.3.1] - 14 décembre 2025 - Stabilité et Améliorations Backend

### 🐛 Corrections de Bugs
- **CRITIQUE : Correction erreur GeometryCollection dans les tampons backend OGR**
  - Conversion automatique de GeometryCollection vers MultiPolygon
- **CRITIQUE : Correction crashs KeyError potentiels dans l'accès PROJECT_LAYERS**
  - Clauses de garde pour vérifier l'existence des couches
- **Correction filtrage géométrique GeoPackage** - Les couches GeoPackage utilisent maintenant le backend Spatialite rapide (10× plus performant)

### 🛠️ Améliorations
- **Gestion d'exception améliorée** - Remplacement des gestionnaires génériques par des types spécifiques

---

## [2.3.0] - 13 décembre 2025 - Annuler/Rétablir Global et Préservation Automatique des Filtres

### 🚀 Fonctionnalités majeures

#### Annuler/Rétablir Global
Système intelligent d'annulation/rétablissement avec comportement contextuel :
- **Mode Couche Source Seule** : Annuler/rétablir s'applique uniquement à la couche source quand aucune couche distante n'est sélectionnée
- **Mode Global** : Quand des couches distantes sont sélectionnées et filtrées, annuler/rétablir restaure l'état complet de toutes les couches simultanément
- **États des Boutons Intelligents** : Les boutons s'activent/désactivent automatiquement selon l'historique disponible
- **Capture Multi-Couches** : Nouvelle classe `GlobalFilterState` pour capturer l'état atomique des couches
- **Détection Automatique du Contexte** : Bascule transparente entre les modes

#### Préservation Automatique des Filtres ⭐ NOUVEAU
Fonctionnalité critique empêchant la perte de filtres lors du changement de couche :
- **Problème Résolu** : Auparavant, appliquer un nouveau filtre remplaçait les filtres existants
- **Solution** : Les filtres sont maintenant combinés automatiquement (AND par défaut)
- **Opérateurs Disponibles** : AND (défaut), OR, AND NOT
- **Exemple d'Utilisation** :
  1. Filtrer par géométrie polygone → 150 entités
  2. Changer de couche
  3. Appliquer un filtre attributaire `population > 10000`
  4. Résultat : 23 entités (intersection des deux filtres préservée !)

#### Réduction de la Fatigue des Notifications ⭐ NOUVEAU
Système de feedback configurable avec contrôle de verbosité :
- **Trois Niveaux** : Minimal (-92% messages), Normal (défaut, -42%), Verbeux
- **Configurable via** : `config.json` → `APP.DOCKWIDGET.FEEDBACK_LEVEL`

### ✨ Améliorations
- **Auto-Activation** : Le plugin s'active automatiquement à l'ajout de couches vecteur
- **Nettoyage Debug** : Tous les print de debug convertis en logging approprié

### 🐛 Corrections de bugs
- **Gel QSplitter** : Correction du gel quand ACTION_BAR_POSITION défini sur 'left' ou 'right'
- **Condition de Course au Chargement** : Correction du gel au chargement de projets avec couches
- **Annuler Global Couches Distantes** : Correction de l'annulation ne restaurant pas toutes les couches distantes

### 🛠️ Qualité du Code
- Audit complet du code avec score global **4.2/5**
- Toutes les comparaisons `!= None` et `== True/False` corrigées selon PEP 8

---

## [2.2.5] - 8 décembre 2025 - Gestion Automatique des CRS Géographiques

### 🚀 Améliorations Majeures
- **Conversion Automatique EPSG:3857** : FilterMate détecte maintenant automatiquement les systèmes de coordonnées géographiques (EPSG:4326, etc.) et bascule vers EPSG:3857 pour les opérations métriques
  - **Pourquoi** : Assure des distances de tampon précises en mètres au lieu de degrés imprécis
  - **Bénéfice** : Un tampon de 50m fait toujours 50 mètres, quelle que soit la latitude !
  - **Impact utilisateur** : Aucune configuration - fonctionne automatiquement

### 🐛 Corrections de bugs
- **Zoom et Flash Coordonnées Géographiques** : Correction de problèmes critiques avec EPSG:4326
  - La géométrie des entités était modifiée en place lors de la transformation
  - Les distances de tampon en degrés variaient avec la latitude
  - Solution : Utilisation d'une copie de géométrie, bascule auto vers EPSG:3857

---

## [2.2.4] - 8 décembre 2025 - Correction Expressions Spatialite

### 🐛 Corrections de bugs
- **CRITIQUE : Guillemets Expressions Spatialite** : Correction du bug où les guillemets doubles autour des noms de champs étaient supprimés
  - Problème : `"HOMECOUNT" > 100` était incorrectement converti en `HOMECOUNT > 100`
  - Impact : Les filtres échouaient sur les couches Spatialite avec noms de champs sensibles à la casse
  - Solution : Préservation des guillemets dans la conversion d'expression

### 🧪 Tests
- Ajout d'une suite de tests complète pour la conversion d'expressions Spatialite
- Validation de la préservation des guillemets des noms de champs

---

## [2.2.3] - 8 décembre 2025 - Harmonisation des Couleurs et Accessibilité

### 🎨 Améliorations de l'Interface
- **Distinction Visuelle Améliorée** : Amélioration significative du contraste entre les éléments de l'interface
- **Conformité WCAG 2.1** : Standards d'accessibilité AA/AAA respectés pour tout le texte
  - Contraste texte principal : 17.4:1 (conformité AAA)
  - Contraste texte secondaire : 8.86:1 (conformité AAA)
  - Texte désactivé : 4.6:1 (conformité AA)
- **Améliorations des Thèmes** : 
  - Thème `default` : Fonds de cadre plus sombres (#EFEFEF), bordures plus claires (#D0D0D0)
  - Thème `light` : Meilleur contraste des widgets (#F8F8F8), bordures visibles (#CCCCCC)
- **Couleurs d'Accent** : Bleu plus profond (#1565C0) pour un meilleur contraste
- **Séparation des Cadres** : +300% d'amélioration du contraste entre cadres et widgets
- **Visibilité des Bordures** : +40% de bordures plus sombres

### 📊 Accessibilité et Ergonomie
- ✅ Réduction de la fatigue oculaire avec des contrastes optimisés
- ✅ Hiérarchie visuelle claire dans toute l'interface
- ✅ Meilleure distinction pour les utilisateurs avec déficiences visuelles légères
- ✅ Confort amélioré pour les longues sessions de travail

### 🧪 Tests et Documentation
- **Nouvelle Suite de Tests** : `test_color_contrast.py` valide la conformité WCAG
- **Prévisualisation** : `generate_color_preview.py` crée une comparaison HTML interactive
- **Documentation** : Guide complet d'harmonisation des couleurs

## [2.2.2] - 8 décembre 2025 - Réactivité de la Configuration

### ✨ Nouvelles Fonctionnalités
- **Mises à Jour en Temps Réel** : Les changements dans la vue JSON s'appliquent sans redémarrage
- **Changement Dynamique de Profil UI** : Basculement instantané entre modes compact/normal/auto
- **Mise à Jour Live des Icônes** : Changements reflétés immédiatement
- **Sauvegarde Automatique** : Tous les changements sauvegardés automatiquement

### 🎯 Types de Configuration Améliorés
- **Intégration ChoicesType** : Sélecteurs déroulants pour les champs clés
  - Menus déroulants UI_PROFILE, ACTIVE_THEME, THEME_SOURCE
  - Sélecteurs de format STYLES_TO_EXPORT, DATATYPE_TO_EXPORT
- **Sécurité des Types** : Valeurs invalides empêchées au niveau de l'UI

### 🔧 Améliorations Techniques
- **Gestion des Signaux** : Signal itemChanged activé pour le gestionnaire de config
- **Détection Intelligente** : Auto-détection du type de changement
- **Nouveau Module** : config_helpers.py avec utilitaires get/set
- **Gestion des Erreurs** : Gestion complète avec feedback utilisateur

### 🎨 Travail Initial d'Harmonisation
- Contraste amélioré entre éléments UI en mode normal
- Conformité WCAG AAA (17.4:1 pour texte principal)
- Meilleure distinction cadre/widget

## [2.2.1] - 7 décembre 2025 - Version de Maintenance

### 🔧 Maintenance
- ✅ Gestion des Releases : Procédures de tagging et déploiement améliorées
- ✅ Scripts de Build : Automatisation et gestion des versions améliorées
- ✅ Documentation : Procédures de release mises à jour
- ✅ Nettoyage du Code : Améliorations mineures de formatage

## [2.2.0] - Décembre 2025

### Ajouté
- ✅ Prévention améliorée des crashs Qt JSON view
- ✅ Récupération d'erreur du tab widget améliorée
- ✅ Gestion robuste des thèmes et synchronisation
- ✅ Documentation complète de l'architecture multi-backend

### Amélioré
- ⚡ Performance 2.5× plus rapide avec ordonnancement intelligent des requêtes
- 🎨 Adaptation dynamique de l'UI selon la résolution d'écran
- 🔧 Meilleure récupération des verrous SQLite
- 📝 Logging et capacités de débogage améliorées

### Corrigé
- 🐛 Crash Qt JSON view lors du changement de thème
- 🐛 Problèmes d'initialisation du tab widget
- 🐛 Cas limites de réparation de géométrie
- 🐛 Avertissements de reprojection CRS

## [2.1.0] - Novembre 2025

### Ajouté
- 🎨 UI adaptative avec dimensions dynamiques
- 🌓 Synchronisation automatique du thème avec QGIS
- 📝 Historique des filtres avec annuler/rétablir
- 🚀 Avertissements de performance pour grands jeux de données

### Amélioré
- ⚡ Support multi-backend (PostgreSQL, Spatialite, OGR)
- 📊 Monitoring de performance amélioré
- 🔍 Meilleure gestion des prédicats spatiaux

## [1.9.0] - Octobre 2025

### Ajouté
- 🏗️ Pattern Factory pour la sélection du backend
- 📈 Optimisations de performance automatiques
- 🔧 Mécanismes de retry pour les verrous SQLite

### Performance
- ⚡ Filtrage Spatialite 44.6× plus rapide (index R-tree)
- ⚡ Opérations OGR 19.5× plus rapides (index spatiaux)
- ⚡ 2.3× plus rapide avec ordonnancement des prédicats

## [1.8.0] - Septembre 2025

### Ajouté
- 🎨 Configuration des widgets par couche
- 💾 Paramètres persistants par couche
- 🔄 Reprojection CRS automatique

## Versions Antérieures

Pour l'historique complet des versions, voir la page [GitHub Releases](https://github.com/sducournau/filter_mate/releases).

---

## Numérotation des Versions

FilterMate suit le [Versionnage Sémantique](https://semver.org/lang/fr/) :

- **Majeur.Mineur.Patch** (ex: 2.1.0)
- **Majeur** : Changements incompatibles
- **Mineur** : Nouvelles fonctionnalités (rétrocompatibles)
- **Patch** : Corrections de bugs

## Guide de Mise à Jour

### De 1.x vers 2.x

La version 2.0 a introduit l'architecture multi-backend. Pour mettre à jour :

1. Mettez à jour via le Gestionnaire d'Extensions QGIS
2. (Optionnel) Installez psycopg2 pour le support PostgreSQL
3. Les paramètres existants seront migrés automatiquement

### De 2.0 vers 2.1+

Pas de changements incompatibles. Mettez à jour directement via le Gestionnaire d'Extensions.

## Signalement de Problèmes

Vous avez trouvé un bug ou une suggestion de fonctionnalité ?

- [Issues GitHub](https://github.com/sducournau/filter_mate/issues)
- [Forum de Discussion](https://github.com/sducournau/filter_mate/discussions)
