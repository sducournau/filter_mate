---
sidebar_position: 2
---

# Pourquoi FilterMate ?

Comprenez quand utiliser FilterMate plutôt que les outils natifs de QGIS pour vos flux de travail de filtrage.

## Réponse Rapide

**Utilisez FilterMate quand** :
- Vous avez besoin de flux de travail de filtrage **rapides et reproductibles**
- Vous travaillez avec **de grands jeux de données** (&gt;50k entités)
- Vous combinez régulièrement des filtres **d'attributs + spatiaux**
- Vous voulez **annuler/rétablir** des opérations de filtrage
- Vous **exportez des données filtrées** fréquemment
- Vous avez besoin d'**optimisation des performances** via des backends

**Utilisez QGIS natif quand** :
- Sélections simples ponctuelles
- Apprentissage des concepts SIG de base
- Installation de plugins non autorisée
- Outils de traitement très spécifiques nécessaires

---

## Comparaison des Fonctionnalités

### Opérations de Filtrage

| Tâche | QGIS Natif | FilterMate | Gagnant |
|-------|------------|------------|---------|
| **Filtre d'attribut simple** | Propriétés de couche → Source → Constructeur de requêtes | Constructeur d'expression dans le panneau | 🤝 Égalité |
| **Sélection rapide sur la carte** | Outil Sélectionner par expression | Onglet EXPLORATION | 🤝 Égalité |
| **Requête spatiale complexe** | Boîte à outils de traitement (3-5 étapes) | Opération unique dans l'onglet FILTRAGE | ⭐ **FilterMate** |
| **Filtrage multi-couches** | Répéter le processus pour chaque couche | Multi-sélection de couches, appliquer une fois | ⭐ **FilterMate** |
| **Combiné attribut + spatial** | Outils séparés, combinaison manuelle | Interface intégrée | ⭐ **FilterMate** |
| **Tampon + filtre** | Outil Tampon → Sélection par emplacement → Manuel | Paramètre de tampon + appliquer le filtre | ⭐ **FilterMate** |

**Avantage FilterMate** : Le flux de travail intégré réduit 5 à 10 étapes manuelles à 1 opération.

---

### Performance

| Scénario | QGIS Natif | FilterMate | Amélioration |
|----------|------------|------------|--------------|
| **Petit jeu de données** (&lt;10k entités) | 2-5 secondes | 1-3 secondes | 1,5× |
| **Jeu de données moyen** (10-50k entités) | 15-45 secondes | 2-8 secondes (Spatialite) | **5-10× plus rapide** |
| **Grand jeu de données** (&gt;50k entités) | 60-300 secondes | 1-5 secondes (PostgreSQL) | **20-50× plus rapide** |
| **Très grand jeu de données** (&gt;500k entités) | 5-30+ minutes ⚠️ | 3-10 secondes (PostgreSQL) | **100-500× plus rapide** |

**Différence clé** : FilterMate exploite les backends de bases de données (PostgreSQL, Spatialite) pour un traitement côté serveur, tandis que les outils natifs de QGIS utilisent souvent un traitement en mémoire.

---

### Efficacité du Flux de Travail

| Tâche | Étapes QGIS Natif | Étapes FilterMate | Temps Gagné |
|-------|-------------------|-------------------|-------------|
| **Filtre d'attribut** | 3 clics (Couche → Propriétés → Requête) | 2 clics (Sélectionner couche → Appliquer) | ~10 secondes |
| **Filtre spatial** | 5 étapes (Tampon → Sélection par emplacement → Extraire → Style) | 1 étape (Définir tampon → Appliquer) | **2-5 minutes** |
| **Exporter filtré** | 4 clics (Clic droit → Exporter → Configurer → Enregistrer) | 2 clics (Onglet EXPORTATION → Exporter) | **30-60 secondes** |
| **Annuler filtre** | Manuel (recharger la couche ou effacer la sélection) | 1 clic (Bouton Annuler) | **1-2 minutes** |
| **Répéter filtre** | Ressaisir tous les paramètres manuellement | 1 clic (Charger depuis Favoris) | **3-10 minutes** |

**Impact en Situation Réelle** : 
- **Utilisateurs quotidiens** : Économie de 20-60 minutes par jour
- **Utilisateurs hebdomadaires** : Économie de 1-3 heures par semaine
- **Utilisateurs mensuels** : Économies modérées, mais améliorations de la qualité de vie

---

## Analyse de Cas d'Usage

### Cas 1 : Sélection Simple Ponctuelle

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

**Tâche** : Sélectionner les villes avec une population &gt; 100 000

<Tabs>
  <TabItem value="qgis" label="QGIS Natif" default>
    ```
    1. Clic droit sur la couche → Filtrer
    2. Entrer : population > 100000
    3. Cliquer sur OK
    
    Temps : 15 secondes
    Complexité : Faible
    ```
    **Verdict** : QGIS natif convient ✓
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Sélectionner la couche dans FilterMate
    2. Entrer : population > 100000
    3. Cliquer sur Appliquer le filtre
    
    Temps : 12 secondes
    Complexité : Faible
    ```
    **Verdict** : FilterMate légèrement plus rapide, mais pas significatif
  </TabItem>
</Tabs>

**Gagnant** : 🤝 **Égalité** - Les deux outils fonctionnent bien pour les filtres simples ponctuels.

---

### Cas 2 : Requête Spatiale Complexe

**Tâche** : Trouver les parcelles résidentielles à moins de 500m des stations de métro

<Tabs>
  <TabItem value="qgis" label="QGIS Natif" default>
    ```
    1. Traitement → Tampon
       - Entrée : stations_metro
       - Distance : 500
       - Sortie : stations_tampon
    
    2. Traitement → Sélectionner par emplacement
       - Sélectionner entités depuis : parcelles
       - Où les entités : intersectent
       - Référence : stations_tampon
    
    3. Traitement → Extraire les entités sélectionnées
       - Entrée : parcelles
       - Sortie : parcelles_filtrees
    
    4. Clic droit sur parcelles_filtrees → Filtrer
       - Entrer : land_use = 'residential'
    
    5. Styliser la couche résultat
    
    Temps : 3-5 minutes
    Étapes : 5 opérations séparées
    Complexité : Élevée
    ```
    **Verdict** : Fastidieux, sujet aux erreurs, non réutilisable
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Sélectionner la couche parcelles
    2. Expression : land_use = 'residential'
    3. Couche de référence : stations_metro
    4. Tampon : 500 mètres
    5. Prédicat : Intersecte
    6. Cliquer sur Appliquer le filtre
    
    Temps : 30-60 secondes
    Étapes : 1 opération intégrée
    Complexité : Faible
    ```
    **Verdict** : Rapide, simple, enregistrable en Favori
  </TabItem>
</Tabs>

**Gagnant** : ⭐ **FilterMate** - 5× plus rapide, 80% moins d'étapes, flux de travail reproductible.

---

### Cas 3 : Analyse Multi-Couches

**Tâche** : Filtrer bâtiments, parcelles et routes près d'une rivière (3 couches)

<Tabs>
  <TabItem value="qgis" label="QGIS Natif" default>
    ```
    1. Tampon sur la couche rivière
    2. Sélection par emplacement pour bâtiments → Extraire
    3. Sélection par emplacement pour parcelles → Extraire
    4. Sélection par emplacement pour routes → Extraire
    5. Styliser 3 couches résultats
    6. Gérer 6 couches au total (originales + filtrées)
    
    Temps : 8-12 minutes
    Étapes : 15+ opérations
    Complexité : Très élevée
    ```
    **Verdict** : Chronophage, encombre le panneau des couches
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Multi-sélection : bâtiments, parcelles, routes
    2. Couche de référence : rivière
    3. Tampon : 100 mètres
    4. Cliquer sur Appliquer le filtre
    
    Les 3 couches filtrées simultanément !
    
    Temps : 1-2 minutes
    Étapes : 4 clics
    Complexité : Faible
    ```
    **Verdict** : Nettement plus simple
  </TabItem>
</Tabs>

**Gagnant** : ⭐⭐ **FilterMate** - 5-10× plus rapide, maintient un espace de travail propre.

---

### Cas 4 : Performance sur Grand Jeu de Données

**Tâche** : Filtrer 150 000 parcelles par attribut et proximité

<Tabs>
  <TabItem value="qgis" label="QGIS Natif" default>
    ```
    Outils de traitement sur 150k entités :
    - Tampon : 45-90 secondes
    - Sélection par emplacement : 120-180 secondes
    - Extraire : 30-60 secondes
    - Filtre d'attribut : 15-30 secondes
    
    Temps total : 3,5-6 minutes
    Utilisation mémoire : Élevée (traitement en mémoire)
    ```
    **Verdict** : Lent, peut planter sur de grands jeux de données
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate (PostgreSQL)">
    ```
    Traitement côté serveur avec index spatiaux :
    - Toutes les opérations combinées : 0,5-2 secondes
    
    Temps total : 0,5-2 secondes
    Utilisation mémoire : Faible (la base de données gère)
    ```
    **Verdict** : 100-500× plus rapide !
  </TabItem>
</Tabs>

**Gagnant** : ⭐⭐⭐ **FilterMate** - Transforme l'impossible en instantané.

---

## Fonctionnalités Uniques de FilterMate

### 1. Historique des Filtres & Annuler/Rétablir

**QGIS Natif** : Pas d'historique de filtres intégré
- Pour "annuler" un filtre : Supprimer manuellement le filtre ou recharger la couche
- Pas de moyen de revenir en arrière dans les changements de filtre
- Travail perdu si vous faites une erreur

**FilterMate** : Gestion complète de l'historique
- Bouton Annuler (↩️) - Revenir au filtre précédent
- Bouton Rétablir (↪️) - Avancer dans l'historique
- L'historique persiste pendant la session
- Jusqu'à 100 opérations suivies

**Valeur en Situation Réelle** : 
- Filtrage expérimental sans crainte
- Comparer plusieurs variations de filtres
- Récupération rapide des erreurs

---

### 2. Favoris de Filtres

**QGIS Natif** : Doit ressaisir manuellement les filtres à chaque fois
- Pas de moyen de sauvegarder les filtres couramment utilisés
- Sujet aux fautes de frappe lors de la ressaisie
- Difficile de partager des filtres avec des collègues

**FilterMate** : Sauvegarder et charger des filtres en Favoris
- ⭐ Cliquer pour sauvegarder le filtre actuel
- Charger depuis le menu déroulant
- Sauvegardé avec le fichier projet
- Partageable au sein de l'équipe

**Valeur en Situation Réelle** :
- Filtrage standardisé pour les équipes
- Accès instantané aux filtres complexes
- Erreurs réduites de la ressaisie manuelle

---

### 3. Optimisation Backend

**QGIS Natif** : Utilise le framework de traitement
- Toujours en mémoire ou fichiers temporaires
- Pas d'optimisation d'index spatial
- Même vitesse quelle que soit la source de données

**FilterMate** : Sélection intelligente de backend
- **PostgreSQL** : Traitement côté serveur, vues matérialisées
- **Spatialite** : Basé sur fichier avec index spatiaux
- **OGR** : Solution de secours pour compatibilité
- Sélection automatique selon le type de couche

**Valeur en Situation Réelle** :
- Amélioration de performance de 10-50× (PostgreSQL)
- Pas de changement de flux de travail nécessaire
- Optimisation transparente

**Voir** : [Comparaison des Backends](../backends/choosing-backend)

---

### 4. Flux de Travail d'Exportation Intégré

**QGIS Natif** : Processus d'exportation multi-étapes
```
1. Appliquer le filtre
2. Clic droit sur la couche → Exporter → Enregistrer les entités sous
3. Configurer le format
4. Définir la transformation de SCR
5. Choisir les champs à exporter
6. Définir le nom de fichier
7. Cliquer sur OK
```

**FilterMate** : Onglet d'exportation en un clic
```
1. Basculer vers l'onglet EXPORTATION
2. Sélectionner le format (GPKG, SHP, GeoJSON, PostGIS, etc.)
3. Optionnel : Transformer le SCR
4. Cliquer sur Exporter

État filtré appliqué automatiquement !
```

**Valeur en Situation Réelle** :
- 70% moins de clics
- Moins sujet aux erreurs
- Exportation par lots de plusieurs couches
- Exportation de style (QML/SLD) incluse

---

### 5. Opérations Multi-Couches

**QGIS Natif** : Traiter une couche à la fois
- Répéter tout le flux de travail pour chaque couche
- Gérer plusieurs couches résultats
- Facile de manquer une couche ou d'appliquer des filtres incohérents

**FilterMate** : Interface de case à cocher multi-sélection
- Cocher toutes les couches à filtrer
- Appliquer le filtre une fois → affecte toutes
- Paramètres cohérents entre les couches
- Espace de travail propre (couches originales filtrées, non dupliquées)

**Valeur en Situation Réelle** :
- 3-10× plus rapide pour les flux de travail multi-couches
- Cohérence garantie
- Panneau de couches plus propre

---

### 6. Retour Visuel & Avertissements

**QGIS Natif** : Retour minimal
- Le traitement peut s'exécuter sans indicateur de progression
- Pas d'avertissements de performance
- Erreurs souvent cryptiques

**FilterMate** : Système de retour complet
- ✅ Messages de succès avec nombre d'entités
- ⚠️ Avertissements de performance pour les grands jeux de données
- 🔄 Indicateurs de reprojection de SCR
- 🌍 Notifications de gestion des coordonnées géographiques
- ⚡ Indicateurs de performance backend
- Messages d'erreur détaillés avec contexte

**Valeur en Situation Réelle** :
- Comprendre ce qui se passe
- Prévenir les problèmes de performance
- Résoudre les problèmes plus rapidement

---

## Quand QGIS Natif Est Meilleur

### Avantages de la Boîte à Outils de Traitement

**QGIS Natif gagne quand vous avez besoin** :

1. **Algorithmes Spécialisés**
   - Opérations topologiques complexes
   - Transformations géométriques avancées
   - Outils d'analyse statistique
   - Intégration raster-vecteur

2. **Traitement par Lots**
   - Plusieurs opérations non liées en séquence
   - Traitement sur de nombreux fichiers déconnectés
   - Flux de travail automatisés via Model Builder

3. **Algorithmes de Graphes**
   - Analyse de réseau (plus court chemin, zones de service)
   - Nécessite pgRouting (PostgreSQL) ou outils QGIS

4. **Opérations Raster**
   - FilterMate fonctionne uniquement avec des données vectorielles
   - Utilisez Traitement pour l'analyse raster

---

### Apprentissage & Éducation

**QGIS Natif meilleur pour** :
- Comprendre les concepts SIG étape par étape
- Apprendre les fonctions des outils individuels
- Environnements académiques/enseignement
- Préparation aux examens de certification

**FilterMate meilleur pour** :
- Flux de travail de production
- Projets critiques en termes de temps
- Tâches répétitives
- Travail SIG du monde réel

---

## Chemin de Migration

### Vous commencez avec QGIS Natif ?

**Essayez FilterMate quand** :
1. ✅ Vous avez fait le même filtre 3+ fois
2. ✅ Le filtrage prend &gt;2 minutes manuellement
3. ✅ Vous travaillez avec &gt;50k entités
4. ✅ Vous combinez des filtres d'attributs + spatiaux
5. ✅ Vous avez besoin d'une capacité annuler/rétablir

**Stratégie de Transition** :
```
Semaine 1 : Apprenez les bases de FilterMate (filtres d'attributs simples)
Semaine 2 : Essayez le filtrage géométrique (prédicats spatiaux)
Semaine 3 : Utilisez l'onglet EXPORTATION pour les exportations filtrées
Semaine 4 : Sauvegardez des Favoris pour les filtres courants
Semaine 5+ : Outil principal, QGIS natif pour tâches spécialisées
```

---

### Vous utilisez déjà FilterMate ?

**Quand utiliser QGIS Natif** :
- Traitement spécialisé absent de FilterMate
- Automatisation Model Builder
- Apprentissage/enseignement de concepts spécifiques
- Dépannage (comparer les résultats)

**Meilleure Pratique** : 
Utilisez **FilterMate pour 80% des tâches de filtrage**, QGIS natif pour les 20% spécialisés.

---

## Comparaison de Performance : Chiffres Réels

### Jeu de Données Test : Analyse de Parcelles Urbaines

**Données** :
- 125 000 polygones de parcelles
- 5 000 lignes de routes
- Tâche : Trouver les parcelles résidentielles à moins de 200m des routes principales

**Matériel** : Ordinateur portable standard (16GB RAM, SSD)

| Méthode | Temps | Mémoire | Étapes | Couches Résultat |
|---------|-------|---------|--------|------------------|
| **Traitement QGIS (OGR)** | 287 secondes | 4,2 GB | 5 | 3 couches |
| **Traitement QGIS (PostGIS)** | 12 secondes | 0,5 GB | 4 | 2 couches |
| **FilterMate (OGR)** | 45 secondes | 1,8 GB | 1 | 1 couche (filtrée) |
| **FilterMate (Spatialite)** | 8,3 secondes | 0,6 GB | 1 | 1 couche (filtrée) |
| **FilterMate (PostgreSQL)** | 1,2 secondes | 0,3 GB | 1 | 1 couche (filtrée) |

**Informations Clés** :
- FilterMate (PostgreSQL) : **240× plus rapide** que Traitement QGIS (OGR)
- FilterMate (Spatialite) : **35× plus rapide** que Traitement QGIS (OGR)
- Même FilterMate (OGR) : **6× plus rapide** grâce au flux de travail optimisé

---

## Analyse Coût-Bénéfice

### Investissement en Temps

**Courbe d'Apprentissage** :
- **Traitement QGIS** : 2-4 semaines pour maîtriser les outils
- **FilterMate** : 2-4 heures pour devenir compétent
- **FilterMate Avancé** : 1-2 jours pour l'optimisation

**Temps de Configuration** :
- **Traitement QGIS** : Intégré (0 minutes)
- **FilterMate** : Installation du plugin (2 minutes)
- **FilterMate + PostgreSQL** : Configuration complète (30-60 minutes)

---

### Économies de Temps

**Utilisateur Quotidien** (10 filtres/jour) :
- Temps manuel : ~60 minutes
- Temps FilterMate : ~15 minutes
- **Économie : 45 minutes/jour = 180 heures/an**

**Utilisateur Hebdomadaire** (20 filtres/semaine) :
- Temps manuel : ~120 minutes/semaine
- Temps FilterMate : ~30 minutes/semaine
- **Économie : 90 minutes/semaine = 75 heures/an**

**Utilisateur Mensuel** (10 filtres/mois) :
- Temps manuel : ~60 minutes/mois
- Temps FilterMate : ~15 minutes/mois
- **Économie : 45 minutes/mois = 9 heures/an**

---

### Analyse de Seuil de Rentabilité

**Installation de FilterMate** (2 minutes) :
- Seuil de rentabilité après : **1-2 filtres**

**Configuration PostgreSQL** (60 minutes) :
- Seuil de rentabilité après : **15-30 filtres** (grands jeux de données)
- Ou : **2-3 heures** de travail de filtrage

**Retour sur Investissement** : 
- FilterMate : **Immédiat** (première utilisation)
- PostgreSQL : **Dans la première semaine** pour les utilisateurs avancés

---

## Recommandations Résumées

### Utilisez FilterMate Quand...

✅ **La performance compte**
- Grands jeux de données (&gt;50k entités)
- Requêtes spatiales complexes
- Flux de travail répétitifs

✅ **L'efficacité compte**
- Opérations multi-couches
- Filtres combinés attributs + spatiaux
- Exportations filtrées fréquentes

✅ **La commodité compte**
- Besoin de capacité annuler/rétablir
- Volonté de sauvegarder des favoris de filtres
- Préférence pour une interface intégrée

---

### Utilisez QGIS Natif Quand...

✅ **Outils spécialisés nécessaires**
- Opérations raster
- Outils topologiques avancés
- Analyse de réseau
- Traitement statistique

✅ **Apprentissage/Enseignement**
- Comprendre les étapes individuelles
- Environnements académiques
- Démonstration de concepts

✅ **Tâches simples ponctuelles**
- Sélections rapides sur carte
- Filtres d'attributs sur une seule couche
- Exploration de données inconnues

---

## Conclusion

**FilterMate complète les outils natifs de QGIS**, ne les remplace pas.

**Pensez-y comme** :
- **Perceuse électrique** (FilterMate) vs **Tournevis manuel** (QGIS natif)
- Les deux ont leur place
- La perceuse électrique fait gagner du temps sur la plupart des tâches
- Le tournevis manuel est meilleur pour les travaux délicats

**Flux de Travail Recommandé** :
```
80% du filtrage → FilterMate (vitesse & efficacité)
20% de tâches spécialisées → Traitement QGIS (flexibilité)
```

**En Résumé** : 
Installez FilterMate. Utilisez-le pour le filtrage quotidien. Revenez à QGIS natif pour les tâches spécialisées. **Le meilleur des deux mondes.**

---

## Prochaines Étapes

1. **Installer FilterMate** : [Guide d'installation](../installation)
2. **Démarrage Rapide** : [Tutoriel de 5 minutes](../getting-started/quick-start)
3. **Apprendre les Flux de Travail** : [Exemples du monde réel](../workflows/index)
4. **Optimiser les Performances** : [Configuration des backends](../backends/choosing-backend)

---

**Questions ?** Posez-les sur [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
