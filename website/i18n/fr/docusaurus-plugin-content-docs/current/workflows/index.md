---
sidebar_position: 1
---

# Flux de travail réels

Tutoriels pratiques et scénarisés montrant comment utiliser FilterMate pour des tâches SIG courantes.

## À propos de ces flux de travail

Chaque tutoriel de flux de travail est conçu pour :
- ✅ **Résoudre un problème réel** rencontré par les professionnels SIG
- ✅ **Enseigner plusieurs fonctionnalités FilterMate** dans un contexte pratique
- ✅ **Être complété en 10-15 minutes** avec les données d'exemple fournies
- ✅ **Inclure les meilleures pratiques** pour la performance et la précision

## Flux de travail disponibles

### 🏙️ Urbanisme et développement

**[Trouver des propriétés près des transports](/docs/workflows/urban-planning-transit)**
- **Scénario** : Identifier toutes les parcelles résidentielles dans un rayon de 500m des stations de métro
- **Compétences** : Opérations de tampon, prédicats spatiaux, filtrage multi-couches
- **Backend** : PostgreSQL (recommandé pour les grands jeux de données cadastrales)
- **Durée** : ~10 minutes
- **Difficulté** : ⭐⭐ Intermédiaire

---

### 🌳 Analyse environnementale

**[Évaluation d'impact des zones protégées](/docs/workflows/environmental-protection)**
- **Scénario** : Trouver les sites industriels dans les zones tampons d'eau protégées
- **Compétences** : Filtrage géométrique, contraintes d'attributs, réparation de géométrie
- **Backend** : Spatialite (bon pour les jeux de données régionaux)
- **Durée** : ~15 minutes
- **Difficulté** : ⭐⭐⭐ Avancé

---

### 🚒 Services d'urgence

**[Analyse de couverture des services](/docs/workflows/emergency-services)**
- **Scénario** : Identifier les zones à plus de 5km de la caserne de pompiers la plus proche
- **Compétences** : Requêtes spatiales inverses, calculs de distance, export des résultats
- **Backend** : OGR (compatibilité universelle)
- **Durée** : ~12 minutes
- **Difficulté** : ⭐⭐ Intermédiaire

---

### 🏠 Analyse immobilière

**[Filtrage et export du marché](/docs/workflows/real-estate-analysis)**
- **Scénario** : Filtrer les propriétés par prix, surface et proximité des écoles
- **Compétences** : Filtrage combiné attributs + géométrie, gestion de l'historique
- **Backend** : Comparaison multi-backend
- **Durée** : ~8 minutes
- **Difficulté** : ⭐ Débutant

---

### 🚗 Planification des transports

**[Préparation des données du réseau routier](/docs/workflows/transportation-planning)**
- **Scénario** : Exporter les segments de route dans une municipalité avec des attributs spécifiques
- **Compétences** : Filtrage d'attributs, transformation SCR, export par lots
- **Backend** : Tous (se concentre sur les fonctionnalités d'export)
- **Durée** : ~10 minutes
- **Difficulté** : ⭐ Débutant

---

## Structure des flux de travail

Chaque tutoriel suit un format cohérent :

1. **Aperçu du scénario** - Le problème réel
2. **Prérequis** - Données et configuration requises
3. **Instructions étape par étape** - Guide détaillé avec captures d'écran
4. **Comprendre les résultats** - Interprétation des sorties
5. **Meilleures pratiques** - Conseils d'optimisation
6. **Problèmes courants** - Guide de dépannage
7. **Prochaines étapes** - Flux de travail connexes et techniques avancées

## Données d'exemple

La plupart des flux de travail peuvent être complétés avec des **données OpenStreetMap** :

- Télécharger depuis [Geofabrik](https://download.geofabrik.de/)
- Utiliser le plugin QGIS **QuickOSM** pour récupérer des zones spécifiques
- Ou utiliser vos propres données de projet

:::tip Obtenir des données d'exemple
Installez le plugin **QuickOSM** dans QGIS :
1. Extensions → Installer/Gérer les extensions
2. Rechercher "QuickOSM"
3. Installer et redémarrer QGIS
4. Vecteur → QuickOSM → Requête rapide
:::

## Choisissez votre parcours d'apprentissage

### Nouveau sur FilterMate ?
Commencez par les **flux de travail débutants** (⭐) :
1. [Analyse immobilière](/docs/workflows/real-estate-analysis) - Filtrage simple
2. [Planification des transports](/docs/workflows/transportation-planning) - Focus export

### À l'aise avec les bases ?
Essayez les **flux de travail intermédiaires** (⭐⭐) :
1. [Urbanisme](/docs/workflows/urban-planning-transit) - Opérations spatiales
2. [Services d'urgence](/docs/workflows/emergency-services) - Analyse de distance

### Prêt pour des tâches complexes ?
Attaquez les **flux de travail avancés** (⭐⭐⭐) :
1. [Analyse environnementale](/docs/workflows/environmental-protection) - Filtrage multi-critères

---

## Objectifs des flux de travail

En complétant ces flux de travail, vous apprendrez :

- 🎯 **Filtrage efficace** - Techniques d'attributs et géométriques
- 📐 **Analyse spatiale** - Tampons, prédicats, calculs de distance
- 🗺️ **Opérations multi-couches** - Travail avec des jeux de données liés
- 💾 **Stratégies d'export** - Sélection de format et transformation SCR
- ⚡ **Optimisation des performances** - Sélection et réglage du backend
- 🔧 **Dépannage** - Problèmes courants et solutions
- 📝 **Gestion de l'historique** - Système annuler/rétablir

---

## Contribuer des flux de travail

Vous avez un cas d'utilisation réel ? Nous serions ravis de l'ajouter !

**Soumettre votre flux de travail :**
1. Ouvrez un ticket sur [GitHub](https://github.com/sducournau/filter_mate/issues)
2. Décrivez votre scénario et les exigences en matière de données
3. Incluez des captures d'écran si possible
4. Nous vous aiderons à créer un tutoriel

---

## Besoin d'aide ?

- 📖 **Documentation de référence** : [Guide utilisateur](/docs/user-guide/introduction)
- 🐛 **Signaler des problèmes** : [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Poser des questions** : [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 🎥 **Regarder le tutoriel** : [Vidéo YouTube](https://www.youtube.com/watch?v=2gOEPrdl2Bo)
