---
sidebar_position: 1
slug: /
---

# Bienvenue sur FilterMate

**FilterMate** est un plugin QGIS prêt pour la production qui offre des capacités avancées de filtrage et d'export pour les données vectorielles - fonctionne avec N'IMPORTE QUELLE source de données !

## 🎉 Nouveautés de la v2.5.4 - Correction critique : Backend OGR

Cette version corrige un bug critique dans le backend OGR qui causait l'échec de tous les filtres en raison d'un comptage incorrect des entités dans les couches mémoire.

### 🐛 Corrections critiques

| Problème                  | Solution                                                      |
| ------------------------- | ------------------------------------------------------------- |
| **Comptage Memory Layer** | Mécanisme de réessai intelligent pour le comptage des entités |
| **Faux "0 entités"**      | Diagnostics et validation améliorés                           |
| **Échecs filtres OGR**    | Empêche le rejet prématuré des couches valides                |

### Versions précédentes

## 🎉 v2.5.0 - Version majeure de stabilité

Cette version consolide toutes les corrections de stabilité de la série 2.4.x en une version stable, prête pour la production.

## 🎉 v2.2.5 - Gestion automatique des SCR géographiques

### Améliorations majeures

- ✅ **Conversion automatique en EPSG:3857** - Les SCR géographiques (EPSG:4326, etc.) sont automatiquement convertis pour les opérations métriques
  - Fonctionnalité : Détecte automatiquement les systèmes de coordonnées géographiques
  - Impact : Un tampon de 50m fait toujours 50 mètres, quelle que soit la latitude (plus d'erreurs de 30-50% !)
  - Implémentation : Conversion automatique en EPSG:3857 (Web Mercator) pour les calculs de tampon
  - Performance : Surcharge minimale (~1ms par transformation d'entité)
- ✅ **Correction du zoom et du flash géographiques** - Résolution du scintillement avec `flashFeatureIds`
  - Corrigé : La géométrie de l'entité n'est plus modifiée sur place pendant la transformation
  - Solution : Utilise le constructeur de copie `QgsGeometry()` pour éviter la modification de la géométrie originale
- ✅ **Opérations métriques cohérentes** - Tous les backends mis à jour (Spatialite, OGR, Zoom)
  - Zéro configuration requise
  - Journalisation claire avec indicateur 🌍 lors du changement de SCR
- ✅ **Tests complets** - Suite de tests ajoutée dans `tests/test_geographic_coordinates_zoom.py`

## Mises à jour précédentes

### v2.2.4 - Harmonisation des couleurs et accessibilité (8 décembre 2025)

- ✅ **Harmonisation des couleurs** - Distinction visuelle améliorée avec +300% de contraste des cadres
- ✅ **Conformité WCAG 2.1** - Normes d'accessibilité AA/AAA pour tout le texte
  - Texte principal : ratio de contraste 17.4:1 (AAA)
  - Texte secondaire : ratio de contraste 8.86:1 (AAA)
  - Texte désactivé : ratio de contraste 4.6:1 (AA)
- ✅ **Fatigue oculaire réduite** - Palette de couleurs optimisée pour les longues sessions de travail
- ✅ **Meilleure lisibilité** - Hiérarchie visuelle claire dans toute l'interface
- ✅ **Raffinements du thème** - Cadres plus sombres (#EFEFEF), bordures plus claires (#D0D0D0)
- ✅ **Tests automatisés** - Suite de validation de conformité WCAG

### v2.2.2 - Réactivité de la configuration (8 décembre 2025)

- ✅ **Mises à jour de configuration en temps réel** - Les modifications de l'arborescence JSON s'appliquent instantanément sans redémarrage
- ✅ **Changement dynamique de l'interface** - Basculez entre les modes compact/normal/auto à la volée
- ✅ **Mises à jour d'icônes en direct** - Les modifications de configuration se reflètent immédiatement
- ✅ **Intégration ChoicesType** - Sélecteurs déroulants pour les champs de configuration validés
- ✅ **Sécurité des types** - Valeurs invalides empêchées au niveau de l'interface
- ✅ **Sauvegarde automatique** - Toutes les modifications de configuration sont enregistrées automatiquement

### v2.2.1 - Maintenance (7 décembre 2025)

- ✅ **Stabilité améliorée** - Prévention améliorée des plantages de la vue JSON Qt
- ✅ **Meilleure récupération d'erreur** - Gestion robuste des widgets d'onglets et des thèmes
- ✅ **Améliorations de la construction** - Automatisation améliorée et gestion des versions

## Pourquoi FilterMate ?

- **🚀 Rapide** : Backends optimisés pour PostgreSQL, Spatialite et OGR
- **🎯 Précis** : Prédicats spatiaux avancés et opérations de tampon
- **💾 Prêt à l'export** : Formats multiples (GeoPackage, Shapefile, GeoJSON, PostGIS)
- **📜 Historique** : Annulation/rétablissement complet avec suivi de l'historique des filtres
- **🎨 Magnifique** : Interface conforme WCAG avec support des thèmes
- **🔧 Flexible** : Fonctionne avec n'importe quelle source de données vectorielles

## Démarrage rapide

1. **Installation** : Ouvrez QGIS → Extensions → Installer/Gérer les extensions → Rechercher "FilterMate"
2. **Ouvrir** : Cliquez sur l'icône FilterMate dans la barre d'outils
3. **Filtrer** : Sélectionnez une couche, écrivez une expression, cliquez sur Appliquer
4. **Exporter** : Choisissez le format et exportez vos données filtrées

👉 **[Guide d'installation complet](/docs/installation)**

## Fonctionnalités clés

### Filtrage avancé

- Filtrage d'attributs avec expressions QGIS
- Filtrage géométrique (intersecte, contient, dans, etc.)
- Opérations de tampon avec conversion automatique du SCR
- Support multi-couches

### Backends multiples

- **PostgreSQL** : Idéal pour les grands jeux de données (`>50k` entités) - 10 à 50× plus rapide
- **Spatialite** : Bon pour les jeux de données moyens (`<50k` entités)
- **OGR** : Compatibilité universelle (Shapefiles, GeoPackage, etc.)

**FilterMate choisit automatiquement le meilleur backend** pour votre source de données - aucune configuration nécessaire ! En savoir plus dans l'[Aperçu des backends](/docs/backends/overview).

### Capacités d'export

- Formats multiples : GPKG, SHP, GeoJSON, KML, CSV, PostGIS
- Transformation du SCR à l'export
- Export de style (QML, SLD, ArcGIS)
- Export par lots et compression ZIP

## Prérequis

Avant d'utiliser FilterMate :

- ✅ **QGIS 3.x** installé (n'importe quelle version)
- ✅ **Couche vectorielle** chargée dans votre projet
- ⚡ **Optionnel** : Installer `psycopg2` pour le support PostgreSQL (recommandé pour les grands jeux de données)

## Parcours d'apprentissage

Nouveau sur FilterMate ? Suivez ce parcours :

1. **[Installation](/docs/installation)** - Installez le plugin et les dépendances optionnelles
2. **[Démarrage rapide](/docs/getting-started/quick-start)** - Tutoriel de 5 minutes
3. **[Votre premier filtre](/docs/getting-started/first-filter)** - Exemple complet étape par étape
4. **[Aperçu de l'interface](/docs/user-guide/interface-overview)** - Comprendre l'interface
5. **[Bases du filtrage](/docs/user-guide/filtering-basics)** - Maîtriser les techniques de filtrage

:::note Traduction en cours
Certaines sections de la documentation ne sont pas encore disponibles en français. Consultez la [documentation anglaise](/docs) pour accéder à toutes les fonctionnalités.
:::

## Obtenir de l'aide

- 📖 **Documentation** : Parcourez le [Guide utilisateur](/docs/user-guide/introduction)
- 🐛 **Problèmes** : Signalez les bugs sur [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Discussions** : Rejoignez [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 🎥 **Vidéo** : Regardez notre [tutoriel YouTube](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Sections de la documentation

- **[Premiers pas](/docs/getting-started)** - Tutoriels et guides de démarrage rapide
- **[Guide utilisateur](/docs/user-guide/introduction)** - Documentation complète des fonctionnalités
- **[Backends](/docs/backends/overview)** - Comprendre les backends de sources de données

### v2.2.0 et antérieures

- ✅ **Multi-Backend complet** - Implémentations PostgreSQL, Spatialite et OGR
- ✅ **Interface dynamique** - Interface adaptative qui s'ajuste à la résolution de l'écran
- ✅ **Gestion d'erreur robuste** - Réparation automatique de géométrie et mécanismes de nouvelle tentative
- ✅ **Synchronisation des thèmes** - Correspond automatiquement au thème de l'interface QGIS
- ✅ **Performance optimisée** - 2,5× plus rapide avec ordre de requête intelligent

## Fonctionnalités clés

- 🔍 **Recherche intuitive** d'entités dans n'importe quelle couche
- 📐 **Filtrage géométrique** avec prédicats spatiaux et support de tampon
- 🎨 **Widgets spécifiques aux couches** - Configurer et enregistrer les paramètres par couche
- 📤 **Export intelligent** avec options personnalisables
- 🌍 **Reprojection SCR automatique** à la volée
- 📝 **Historique des filtres** - Annulation/rétablissement facile pour toutes les opérations
- 🚀 **Avertissements de performance** - Recommandations intelligentes pour les grands jeux de données
- 🎨 **Interface adaptative** - Dimensions dynamiques basées sur la résolution de l'écran
- 🌓 **Support des thèmes** - Synchronisation automatique avec le thème QGIS

## Liens rapides

- [Guide d'installation](/docs/installation)
- [Tutoriel de démarrage rapide](/docs/getting-started/quick-start)
- [Dépôt GitHub](https://github.com/sducournau/filter_mate)
- [Dépôt de plugins QGIS](https://plugins.qgis.org/plugins/filter_mate)

## Démo vidéo

Regardez FilterMate en action :

<div style={{position: 'relative', width: '100%', maxWidth: '800px', margin: '1.5rem auto', paddingBottom: '56.25%', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)'}}>
  <iframe
    style={{position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', border: 'none'}}
    src="https://www.youtube-nocookie.com/embed/2gOEPrdl2Bo?rel=0&modestbranding=1"
    title="Démo FilterMate"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    allowFullScreen
    loading="lazy"
  />
</div>

## Commencer

Prêt à commencer ? Rendez-vous sur le [Guide d'installation](/docs/installation) pour configurer FilterMate dans votre environnement QGIS.
