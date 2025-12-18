---
sidebar_position: 2
---

# Aperçu de l'interface

Guide rapide des principaux composants de l'interface FilterMate et des flux de travail.

## Ouvrir FilterMate

1. **Menu :** Vecteur → FilterMate
2. **Barre d'outils :** Cliquez sur l'icône FilterMate 

    <img src="/filter_mate/icons/logo.png" alt="Icône du plugin FilterMate" width="32"/>

3. **Clavier :** Configurer dans les paramètres QGIS

## Onglets principaux

FilterMate organise les fonctionnalités en 3 onglets principaux :

### 🎯 Onglet FILTRAGE

**Objectif :** Créer des sous-ensembles filtrés de vos données

**Composants clés :**

  - **Couche de référence :**

    <img src="/filter_mate/icons/auto_layer_white.png" alt="Bouton de synchronisation automatique de la couche" width="32"/>

    Choisir une couche source pour le filtrage spatial / Synchroniser la couche active avec le plugin

  - **Sélecteur de couches :**

    <img src="/filter_mate/icons/layers.png" alt="Icône du sélecteur de couches" width="32"/>

    Choisir les couches à filtrer (sélection multiple prise en charge)

  - **Paramètres de combinaison :**

    <img src="/filter_mate/icons/add_multi.png" alt="Icône de l'opérateur de combinaison" width="32"/>

    Combiner plusieurs filtres avec les opérateurs ET/OU

  - **Prédicats spatiaux :**

    <img src="/filter_mate/icons/geo_predicates.png" alt="Icône des prédicats spatiaux" width="32"/>

    Sélectionner les relations géométriques (Intersecte, Contient, À l'intérieur, etc.)

  - **Paramètres de tampon :**

    <img src="/filter_mate/icons/geo_tampon.png" alt="Icône de distance de tampon" width="32"/>

    Ajouter des zones de proximité (distance, unité, type)

  - **Paramètres de type de tampon :**

    <img src="/filter_mate/icons/buffer_type.png" alt="Icône de type de tampon" width="32"/>

    Choisir le type de géométrie de tampon (planaire, géodésique, ellipsoïdal)

**Cas d'usage :**
- Trouver des entités correspondant à des critères (par ex., population > 100 000)
- Sélectionner des géométries à l'intérieur/près d'autres entités
- Créer des sous-ensembles temporaires pour l'analyse

**Voir :** [Bases du filtrage](./filtering-basics), [Filtrage géométrique](./geometric-filtering), [Opérations de tampon](./buffer-operations)

---

### 🔍 Onglet EXPLORATION

**Objectif :** Visualiser et interagir avec les entités de la couche active QGIS actuelle

**Composants clés :**
- **Boutons d'action :** 6 boutons interactifs
  - **Identifier :** 
  
    <img src="/filter_mate/icons/identify.png" alt="Bouton identifier" width="32"/> 

    Mettre en évidence les entités sur la carte


  - **Zoom :** 
  
    <img src="/filter_mate/icons/zoom.png" alt="Bouton zoom" width="32"/> 
  
    Centrer la carte sur les entités
  - **Sélectionner :** 
    
    <img src="/filter_mate/icons/select_black.png" alt="Bouton sélectionner" width="32"/> 
  
    Activer le mode de sélection interactive
  
  - **Suivre :** 
  
    <img src="/filter_mate/icons/track.png" alt="Bouton suivre" width="32"/> 
    
    Synchroniser les sélections entre les widgets et la carte

  - **Lier :** 
  
    <img src="/filter_mate/icons/link.png" alt="Bouton lier" width="32"/> 
  
    Partager la configuration entre les widgets
  
  - **Réinitialiser les paramètres :** 
  
    <img src="/filter_mate/icons/auto_save.png" alt="Bouton réinitialiser les paramètres" width="32"/> 
  
    Restaurer les paramètres par défaut de la couche

- **Widgets de sélection :**
  - **Sélection unique :** Choisir une entité (menu déroulant)
  - **Sélection multiple :** Sélectionner plusieurs entités (cases à cocher)
  - **Sélection personnalisée :** Utiliser des expressions pour filtrer le widget

**Important :** EXPLORATION fonctionne toujours uniquement sur la **couche active actuelle** de QGIS. Pour changer de couche, mettez-la à jour dans le panneau des couches QGIS.

**Cas d'usage :**
- Parcourir les entités de manière interactive
- Identifier et zoomer sur des entités spécifiques
- Afficher les détails des attributs
- Sélection manuelle d'entités

:::tip EXPLORATION vs FILTRAGE
- **EXPLORATION :** Visualisation temporaire de la couche actuelle (aucune modification des données)
- **FILTRAGE :** Sous-ensembles filtrés permanents sur les couches sélectionnées (peuvent être multiples)
:::

---

### 📤 Onglet EXPORT

**Objectif :** Exporter des couches (filtrées ou non filtrées) vers divers formats

**Composants clés :**
- **Sélecteur de couches :**

  <img src="/filter_mate/icons/layers.png" alt="couches" width="32"/>

  Choisir les couches à exporter

- **Transformation SCR :**

  <img src="/filter_mate/icons/projection_black.png" alt="projection_black" width="32"/>

  Reprojeter vers un système de coordonnées différent

- **Export de style :**

  <img src="/filter_mate/icons/styles_white.png" alt="styles" width="32"/>
 
  Enregistrer les styles QGIS (QML, SLD, ArcGIS)

- **Format :** 

  <img src="/filter_mate/icons/datatype.png" alt="type de données" width="32"/>

  GPKG, Shapefile, GeoJSON, KML, CSV, PostGIS, Spatialite

- **Mode batch :** Exporter chaque couche dans un fichier séparé
- **Dossier de sortie :**

  <img src="/filter_mate/icons/folder.png" alt="dossier" width="32"/>

  Sélectionner le répertoire de destination
- **Compression ZIP :**

  <img src="/filter_mate/icons/zip.png" alt="zip" width="32"/>

  Empaqueter les sorties pour la livraison

**Cas d'usage :**
- Partager des données filtrées avec des collègues
- Archiver des instantanés d'analyse
- Convertir entre formats
- Préparer des données pour la cartographie web

**Voir :** [Exporter des entités](./export-features)

---

### ⚙️ Onglet CONFIGURATION

**Objectif :** Personnaliser le comportement et l'apparence de FilterMate

**Composants clés :**
- **Vue arborescente JSON :** Éditer la configuration complète
- **Sélecteur de thème :** Choisir le thème de l'interface (par défaut/sombre/clair/auto)
- **Options avancées :** Paramètres du plugin

**Voir :** [Configuration](../advanced/configuration)

---

## Boutons d'action (Barre supérieure)

Toujours visibles quel que soit l'onglet actif :

| Bouton | Icône | Action | Raccourci |
|--------|------|--------|----------|
| **FILTRER** | <img src="/filter_mate/icons/filter.png" alt="Filtrer" width="32"/> | Appliquer les filtres configurés | F5 |
| **ANNULER** | <img src="/filter_mate/icons/undo.png" alt="Annuler" width="32"/> | Annuler le dernier filtre | Ctrl+Z |
| **REFAIRE** | <img src="/filter_mate/icons/redo.png" alt="Refaire" width="32"/> | Réappliquer le filtre annulé | Ctrl+Y |
| **RÉINITIALISER** | <img src="/filter_mate/icons/reset.png" alt="Réinitialiser" width="32"/> | Effacer tous les filtres | Ctrl+Shift+C |
| **EXPORTER** | <img src="/filter_mate/icons/export.png" alt="Exporter" width="32"/> | Export rapide | Ctrl+E |
| **À PROPOS** | <img src="/filter_mate/icons/icon.png" alt="Icône" width="32"/> | Informations sur le plugin | - |

---

## Indicateurs de backend

Des badges visuels indiquent le type de source de données :

- **PostgreSQL ⚡ :** Meilleures performances (plus de 50k entités)
- **Spatialite 📦 :** Bonnes performances (moins de 50k entités)
- **OGR/Shapefile 📄 :** Compatibilité de base

Backend détecté automatiquement en fonction du type de couche.

---

## Raccourcis clavier rapides

- **Ctrl+F :** Focus sur le constructeur d'expression
- **F5 :** Exécuter le filtre
- **Ctrl+Z / Ctrl+Y :** Annuler / Refaire
- **Tab :** Naviguer entre les champs
- **Ctrl+Tab :** Basculer entre les onglets

---

## En savoir plus

- **Premiers pas :** [Guide de démarrage rapide](../getting-started/quick-start)
- **Utilisation détaillée :** [Bases du filtrage](./filtering-basics), [Filtrage géométrique](./geometric-filtering)
- **Options d'export :** [Exporter des entités](./export-features)
- **Avancé :** [Configuration](../advanced/configuration), [Optimisation des performances](../advanced/performance-tuning)

## Disposition de l'interface

```mermaid
graph TB
    subgraph "Panneau FilterMate"
        LS[Sélecteur de couches - Sélection multiple]
        AB["Boutons d'action : Filtrer / Annuler / Refaire / Réinitialiser / Exporter / À propos"]
        TB[Barre d'onglets]
        
        subgraph "Onglet FILTRAGE"
            LSF[Sélection de couche + Courant automatique]
            EXP[Constructeur d'expression - Filtrage par attributs]
            PRED[Prédicats spatiaux - Sélection multiple]
            REF[Couche de référence + Opérateur de combinaison]
            BUF[Paramètres de tampon : Distance + Unité + Type]
            IND[Indicateurs d'état]
        end
        
        subgraph "Onglet EXPLORATION"
            BTN[Boutons poussoirs : Identifier | Zoom | Sélectionner | Suivre | Lier | Réinitialiser]
            SS[Sélection unique - Sélecteur d'entité]
            MS[Sélection multiple - Widget de liste]
            CS[Sélection personnalisée - Expression]
            FE[Widget d'expression de champ]
            TBL[Table d'attributs d'entité]
        end
        
        subgraph "Onglet EXPORT"
            LYR[Couches à exporter - Sélection multiple]
            FMT[Sélecteur de format : GPKG | SHP | GeoJSON | etc.]
            CRS[Transformation SCR]
            STY[Export de style : QML | SLD | ArcGIS]
            OUT[Dossier de sortie + Mode batch]
            ZIP[Compression ZIP]
        end
        
        subgraph "Onglet CONFIGURATION"
            JSON[Vue arborescente JSON - Configuration complète]
            THEMES[Sélecteur de thème + Aperçu]
            OPTS[Options avancées]
        end
    end
    
    LS --> AB
    AB --> TB
    TB --> LSF
    TB --> BTN
    TB --> LYR
    TB --> JSON
```

## Sélecteur de couches

### Fonctionnalités

- 📋 **Sélection multiple :** Filtrer plusieurs couches à la fois
- 🔍 **Recherche :** Filtrage rapide de couches
- 🎨 **Icônes :** Indicateurs de type de géométrie
  - 🔵 Couches de points
  - 🟢 Couches de lignes
  - 🟪 Couches de polygones

### Utilisation

```
☑ Couche 1 (Polygone) — PostgreSQL ⚡
☑ Couche 2 (Point) — Spatialite
☐ Couche 3 (Ligne) — Shapefile
```

**Indicateurs de backend :**
- ⚡ PostgreSQL (haute performance)
- 📦 Spatialite (performance moyenne)
- 📄 OGR (compatibilité universelle)

## Lectures complémentaires

Pour des guides détaillés sur chaque fonctionnalité :

- **[Bases du filtrage](./filtering-basics)** - Guide complet du filtrage par attributs et des expressions QGIS
- **[Filtrage géométrique](./geometric-filtering)** - Prédicats spatiaux, opérations de tampon et flux de travail géométriques
- **[Opérations de tampon](./buffer-operations)** - Configuration des tampons, types et paramètres de distance
- **[Exporter des entités](./export-features)** - Formats d'export, transformation SCR et opérations par lots
- **[Historique des filtres](./filter-history)** - Gestion de l'historique, annuler/refaire et favoris

Pour débuter :

- **[Guide de démarrage rapide](../getting-started/quick-start)** - Introduction de 5 minutes
- **[Votre premier filtre](../getting-started/first-filter)** - Tutoriel pas à pas

---

## Directives d'utilisation des icônes

### Accessibilité
- Toutes les icônes ont été conçues avec des rapports de contraste élevés
- Les icônes sensibles au thème s'adaptent automatiquement aux modes clair/sombre
- Les icônes sont dimensionnées de manière appropriée pour les affichages 16px, 24px et 32px

### Cohérence
- Chaque icône représente une action spécifique et cohérente dans toute l'interface
- Les icônes de flux de travail (selection_1-7, zoom_1-5, etc.) montrent la progression du processus
- Les variantes claires/sombres maintiennent la cohérence visuelle dans tous les thèmes

### Contexte
- Les icônes apparaissent dans les boutons, les indicateurs d'état et la documentation
- Les info-bulles au survol fournissent un contexte supplémentaire pour toutes les icônes interactives
- Les icônes séquentielles guident les utilisateurs à travers les opérations en plusieurs étapes

---

## Personnalisation de l'interface

Vous pouvez personnaliser l'apparence des icônes et des thèmes FilterMate dans l'onglet **CONFIGURATION**. Consultez le [Guide de configuration](../advanced/configuration) pour plus de détails sur :

- Basculer entre les thèmes clair/sombre/auto
- Ajuster les tailles d'icônes (si pris en charge par le thème)
- Créer des configurations de thème personnalisées

---
