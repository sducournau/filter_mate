# FilterMate - Plan Documentation Docusaurus (Adapté Interface Réelle)

**Date**: 9 décembre 2025  
**Version**: 1.0.0  
**Site**: https://sducournau.github.io/filter_mate/  
**Approche**: Organisation par Onglets - FILTERING / EXPLORING / EXPORTING

---

## 🎯 Organisation Documentaire

**Principe**: Documenter selon l'organisation réelle du plugin en 3 onglets principaux + Configuration:

### 1. FILTERING Tab
**Objectif**: Gérer la sélection de couches et configurer tous les types de filtres

**Composants principaux**:
- **Layer Selection**:
  - Multi-sélection de couches sources
  - Bouton toggle "Auto Current Layer" (auto_layer_white.png)
  - Indicateur "Has Layers to Filter" (layers.png)
  - Informations couche (provider, features count, CRS)

- **Attribute Filtering**:
  - Expression builder QGIS (saisie libre)
  - Liste des champs disponibles avec types
  - Validation expression (✓ vert / ✗ rouge + message)

- **Geometric Filtering**:
  - Multi-sélection prédicats spatiaux (Intersects, Contains, Within, Overlaps, Touches, Disjoint, Crosses)
  - Sélecteur couche de référence distante
  - Combine operator (AND/OR) pour combiner prédicats
  - Indicateur "Has Geometric Predicates" (geo_predicates.png)
  - Indicateur "Has Combine Operator" (add_multi.png)

- **Buffer Configuration**:
  - Distance buffer + unité (mètres, km, etc.)
  - Type de buffer: Standard / Fast / Segment
  - Indicateurs "Has Buffer Value" (buffer_value.png) et "Has Buffer Type" (buffer_type.png)

- **Status Indicators**: Badges visuels pour chaque configuration active

### 2. EXPLORING Tab  
**Objectif**: Visualiser, sélectionner et interagir avec les features de la couche QGIS courante

**Composants principaux**:
- **Action Push Buttons** (6 boutons):
  - **Identify** (identify_alt.png): Identifier/surbriller features sur la carte
  - **Zoom** (zoom.png): Zoomer sur features sélectionnées
  - **Select** (select_black.png): Mode sélection interactive (checkable)
  - **Track** (track.png): Suivi automatique des sélections (checkable)
  - **Link** (link.png): Lier les widgets de configuration (checkable)
  - **Reset Properties** (save_properties.png): Réinitialiser propriétés de couche

- **Selection Widgets**:
  - **Single Selection**: QgsFeaturePickerWidget (dropdown single feature)
  - **Multiple Selection**: Widget liste avec multi-sélection
  - **Custom Selection**: Expression personnalisée pour filtrage
  - **Field Expression Widget**: QgsFieldExpressionWidget pour filtres attributaires
  - **Feature Table**: Tableau des attributs des features sélectionnées

**Note importante**: Opère toujours sur la **couche active courante** de QGIS

### 3. EXPORTING Tab
**Objectif**: Exporter les couches du projet (filtrées ou non) en différents formats

**Composants principaux**:
- **Layer Selection**:
  - Multi-sélection des couches à exporter
  - Indicateur "Has Layers to Export" (layers.png)

- **Format Configuration**:
  - Sélecteur format: GPKG, Shapefile, GeoJSON, KML/KMZ, CSV, PostGIS, Spatialite
  - Indicateur "Has Datatype to Export" (datatype.png)

- **CRS Transformation**:
  - Widget transformation CRS (re-projection)
  - Indicateur "Has Projection to Export" (projection_black.png)

- **Style Export**:
  - Export styles: QML (QGIS) / SLD (Standard) / ArcGIS
  - Indicateur "Has Styles to Export" (styles_black.png)

- **Output Options**:
  - Sélecteur dossier de destination
  - Indicateur "Has Output Folder to Export" (folder_black.png)
  - Mode batch (export séparé par couche)
  - Compression ZIP
  - Indicateur "Has ZIP to Export" (zip.png)

### 4. CONFIGURATION Tab
**Objectif**: Configurer le plugin et personnaliser l'interface

**Composants principaux**:
- Qt JSON Tree View (visualisation/édition config.json complète)
- Sélecteur de thème UI (default/dark/light + auto)
- Options avancées du plugin

---

**Total: ~45-50 captures** organisées par workflow réel

**Gain**: Documentation alignée avec l'expérience utilisateur réelle et la structure de config.json

---

## 📸 Captures d'écran Essentielles

### 1. Composants UI (45 captures) → `website/static/img/ui-components/`

#### Groupe A: Interface Principale (5)
- `ui-main-panel.png` - Panel complet docké dans QGIS
- `ui-tab-bar.png` - Barre d'onglets FILTERING/EXPLORING/EXPORTING/CONFIGURATION
- `ui-action-buttons.png` - Boutons principaux: Filter, Undo, Redo, Reset, Export, About
- `ui-backend-indicator.png` - Badges backend (PostgreSQL⚡/Spatialite/OGR)
- `ui-panel-docked.png` - Panel ancré à droite/gauche + version flottante

#### Groupe B: FILTERING Tab - Layer Selection (5)
- `ui-filtering-layer-selector.png` - Multi-sélection couches avec icônes géométrie (point/line/polygon)
- `ui-filtering-layer-info.png` - Informations couche (provider type, feature count, CRS)
- `ui-filtering-auto-current.png` - Bouton toggle "Auto Current Layer" (auto_layer_white.png)
- `ui-filtering-has-layers-indicator.png` - Indicateur "Has Layers to Filter" actif (layers.png)
- `ui-filtering-layer-types.png` - Distinction visuelle PostgreSQL⚡ / Spatialite / OGR

#### Groupe C: FILTERING Tab - Attribute Filtering (4)
- `ui-filtering-expression-builder.png` - Zone saisie expression QGIS (texte libre)
- `ui-filtering-field-list.png` - Liste champs disponibles avec types (Integer, String, Date, etc.)
- `ui-filtering-validation-ok.png` - Validation expression OK (✓ verte)
- `ui-filtering-validation-error.png` - Erreur validation (✗ rouge + message d'erreur détaillé)

#### Groupe D: FILTERING Tab - Geometric Filtering (7)
- `ui-filtering-spatial-predicates.png` - Multi-sélection prédicats (Intersects, Contains, Within, Overlaps, Touches, Disjoint, Crosses)
- `ui-filtering-reference-layer.png` - Sélecteur couche de référence distante (dropdown)
- `ui-filtering-combine-operator.png` - Opérateur combinaison AND/OR pour prédicats multiples
- `ui-filtering-has-predicates-indicator.png` - Indicateur "Has Geometric Predicates" (geo_predicates.png)
- `ui-filtering-has-combine-indicator.png` - Indicateur "Has Combine Operator" (add_multi.png)
- `ui-filtering-buffer-distance.png` - Champ distance buffer + sélecteur unité (m, km, ft, mi)
- `ui-filtering-buffer-type.png` - Type buffer: Standard / Fast / Segment (dropdown)

#### Groupe E: FILTERING Tab - Buffer Indicators (2)
- `ui-filtering-buffer-value-indicator.png` - Indicateur "Has Buffer Value" actif (buffer_value.png)
- `ui-filtering-buffer-type-indicator.png` - Indicateur "Has Buffer Type" actif (buffer_type.png)

#### Groupe F: EXPLORING Tab - Action Buttons (7)
- `ui-exploring-action-buttons-row.png` - Vue complète des 6 push buttons alignés
- `ui-exploring-identify-btn.png` - Bouton Identify (identify_alt.png) + tooltip
- `ui-exploring-zoom-btn.png` - Bouton Zoom (zoom.png) + tooltip
- `ui-exploring-select-btn.png` - Bouton Select checkable non-pressé/pressé (select_black.png)
- `ui-exploring-track-btn.png` - Bouton Track checkable non-pressé/pressé (track.png)
- `ui-exploring-link-btn.png` - Bouton Link checkable non-pressé/pressé (link.png)
- `ui-exploring-reset-props-btn.png` - Bouton Reset Properties (save_properties.png) + tooltip

#### Groupe G: EXPLORING Tab - Selection Widgets (5)
- `ui-exploring-single-selection.png` - QgsFeaturePickerWidget (dropdown single feature avec preview)
- `ui-exploring-multiple-selection.png` - Widget liste multi-sélection avec checkboxes
- `ui-exploring-custom-selection.png` - Sélection personnalisée avec expression builder
- `ui-exploring-field-expression.png` - QgsFieldExpressionWidget pour filtrage attributaire
- `ui-exploring-feature-table.png` - Tableau attributs des features sélectionnées (colonnes + valeurs)

#### Groupe H: EXPORTING Tab - Layer & Format Selection (4)
- `ui-exporting-layer-selector.png` - Multi-sélection couches à exporter avec checkboxes
- `ui-exporting-has-layers-indicator.png` - Indicateur "Has Layers to Export" (layers.png)
- `ui-exporting-format-selector.png` - Dropdown formats: GPKG, Shapefile, GeoJSON, KML/KMZ, CSV, PostGIS, Spatialite
- `ui-exporting-format-indicator.png` - Indicateur "Has Datatype to Export" (datatype.png)

#### Groupe I: EXPORTING Tab - CRS & Styles (4)
- `ui-exporting-crs-widget.png` - Widget transformation CRS (QgsProjectionSelectionWidget)
- `ui-exporting-crs-indicator.png` - Indicateur "Has Projection to Export" (projection_black.png)
- `ui-exporting-style-selector.png` - Dropdown styles: QML / SLD / ArcGIS
- `ui-exporting-style-indicator.png` - Indicateur "Has Styles to Export" (styles_black.png)

#### Groupe J: EXPORTING Tab - Output Options (4)
- `ui-exporting-output-folder.png` - Widget sélecteur dossier (QgsFileWidget)
- `ui-exporting-folder-indicator.png` - Indicateur "Has Output Folder to Export" (folder_black.png)
- `ui-exporting-batch-mode.png` - Checkboxes: Batch mode + ZIP compression
- `ui-exporting-zip-indicator.png` - Indicateur "Has ZIP to Export" (zip.png)

#### Groupe K: CONFIGURATION Tab (3)
- `ui-config-json-tree.png` - Qt JSON Tree View (structure hiérarchique complète)
- `ui-config-theme-selector.png` - Dropdown thème: auto / default / dark / light
- `ui-config-advanced-options.png` - Options avancées du plugin

#### Groupe L: Progress & Feedback (3)
- `ui-progress-bar.png` - Barre progression tâches asynchrones (Filter/Export en cours)
- `ui-message-success.png` - Message succès (barre verte QGIS)
- `ui-message-warning.png` - Message avertissement (barre orange QGIS)
- `ui-message-error.png` - Message erreur (barre rouge QGIS)

---

### 2. Workflows Complets → `website/static/img/workflows/`

#### Workflow A: Filtrage Géométrique Complet + Export (14 captures)
**Scénario**: "Trouver bâtiments à moins de 200m des routes avec buffer + exporter en GeoPackage"

**Phase 1 - FILTERING Tab (10 captures)**:
- `workflow-filtering-01.png` - Interface initiale, onglet FILTERING ouvert
- `workflow-filtering-02.png` - Sélection couche source "buildings" dans layer selector
- `workflow-filtering-03.png` - Informations couche affichées (Spatialite, 15234 features, EPSG:4326)
- `workflow-filtering-04.png` - Activation prédicats spatiaux: Intersects sélectionné
- `workflow-filtering-05.png` - Sélection couche de référence "roads" (distante)
- `workflow-filtering-06.png` - Configuration buffer: 200, unité = mètres
- `workflow-filtering-07.png` - Sélection buffer type: Standard
- `workflow-filtering-08.png` - Vue des indicateurs actifs (has_geometric_predicates, has_buffer_value, has_buffer_type)
- `workflow-filtering-09.png` - Clic bouton FILTER (icône filter.png)
- `workflow-filtering-10.png` - Progress bar + backend utilisé (PostgreSQL⚡/Spatialite)

**Phase 2 - Résultats & Export (4 captures)**:
- `workflow-filtering-11.png` - Résultats carte filtrée + feature count (3847 features)
- `workflow-exporting-01.png` - Switch vers onglet EXPORTING
- `workflow-exporting-02.png` - Configuration: format GPKG, CRS EPSG:3857, styles QML
- `workflow-exporting-03.png` - Sélection dossier destination + clic EXPORT
- `workflow-exporting-04.png` - Notification succès (vert) + chemin fichier créé

#### Workflow B: Exploration Interactive des Features (10 captures)
**Scénario**: "Explorer features, sélectionner, identifier, zoomer et suivre les sélections"

- `workflow-exploring-01.png` - Onglet EXPLORING ouvert (couche active: cities)
- `workflow-exploring-02.png` - Widget Single Selection: choix d'une ville dans dropdown
- `workflow-exploring-03.png` - Clic bouton IDENTIFY: feature surbrillée sur carte (flash animation)
- `workflow-exploring-04.png` - Clic bouton ZOOM: zoom automatique sur feature
- `workflow-exploring-05.png` - Activation bouton SELECT (checkable pressé, border noir 2px)
- `workflow-exploring-06.png` - Sélection interactive sur carte (3 features cliquées)
- `workflow-exploring-07.png` - Widget Multiple Selection: affichage des 3 features sélectionnées
- `workflow-exploring-08.png` - Activation bouton TRACK (checkable pressé)
- `workflow-exploring-09.png` - Synchronisation: sélection carte ↔ widgets en temps réel
- `workflow-exploring-10.png` - Tableau des attributs: détails des 3 features (nom, pop, superficie)

#### Workflow C: Filtrage Attributaire Simple (8 captures)
**Scénario**: "Filtrer villes de plus de 100k habitants + export Shapefile"

- `workflow-attribute-01.png` - Onglet FILTERING, focus sur expression builder
- `workflow-attribute-02.png` - Saisie expression: `population > 100000`
- `workflow-attribute-03.png` - Liste champs visible: population (Integer64), name (String), area (Double)
- `workflow-attribute-04.png` - Validation OK (✓ verte) + preview feature count
- `workflow-attribute-05.png` - Clic FILTER + progress bar
- `workflow-attribute-06.png` - Résultats carte: 247 villes affichées
- `workflow-attribute-07.png` - Onglet EXPORTING: format Shapefile + CRS original
- `workflow-attribute-08.png` - Export succès + message historique mis à jour

#### Workflow D: Combinaison Prédicats Multiples (6 captures)
**Scénario**: "Parcelles qui intersectent OU touchent une zone protégée"

- `workflow-combine-01.png` - FILTERING Tab: sélection multi-prédicats (Intersects + Touches)
- `workflow-combine-02.png` - Combine operator: OR sélectionné dans dropdown
- `workflow-combine-03.png` - Indicateur "Has Combine Operator" actif (add_multi.png)
- `workflow-combine-04.png` - Couche référence: protected_zones sélectionnée
- `workflow-combine-05.png` - Application filtre: 1834 parcelles trouvées
- `workflow-combine-06.png` - Visualisation sur carte: parcelles en surbrillance

**Utilisation**: Chaque workflow référencé dans pages pertinentes selon contexte
- `workflow-attribute-03.png` - Validation OK (icône ✓ verte)
- `workflow-attribute-04.png` - Application filtre
- `workflow-attribute-05.png` - Résultats + historique mis à jour
- `workflow-attribute-06.png` - Utilisation Undo/Redo pour navigation historique

**Utilisation**: Chaque workflow référencé dans plusieurs pages selon contexte

---

### 3. Visuels Techniques (5 captures max)

#### Backends → `website/static/img/backends/`
- `backend-perf-graph.png` - Graphique performances (généré Matplotlib)

#### Themes → `website/static/img/themes/`
- `themes-overview.png` - Mosaïque 2x4 des 8 thèmes

#### Troubleshooting → `website/static/img/troubleshooting/`
- `error-postgresql-unavailable.png` - Message erreur type
- `error-expression-invalid.png` - Message erreur validation
- `error-layer-unsupported.png` - Message format non supporté

---

## 📄 Réutilisation dans les Pages

### User Guide - Interface Overview
- `interface-overview.md` → Galerie complète organisation par onglets
  - **Section "Main Interface"**: Groupe A (panel, tabs, action buttons, backend indicator)
  - **Section "FILTERING Tab"**: Groupes B, C, D, E (layer selection, attribute, geometric, buffer, indicators)
  - **Section "EXPLORING Tab"**: Groupes F, G (action buttons détaillés, selection widgets)
  - **Section "EXPORTING Tab"**: Groupes H, I, J (layers, formats, CRS, styles, output options)
  - **Section "CONFIGURATION Tab"**: Groupe K (JSON tree, theme selector)

### User Guide - FILTERING
- `filtering-basics.md` → 
  - Groupe B (layer selector, auto current layer)
  - Groupe C (expression builder, field list, validation)
  - Workflow C (filtrage attributaire complet, 8 étapes)
  - Focus sur expressions QGIS et validation

- `geometric-filtering.md` → 
  - Groupe D (spatial predicates, reference layer, combine operator, indicators)
  - Workflow A étapes 1-11 (filtrage géométrique)
  - Workflow D complet (combinaison prédicats, 6 étapes)
  - Explication détaillée de chaque prédicat spatial

- `buffer-operations.md` → 
  - Groupe D (buffer distance, unité, type)
  - Groupe E (buffer indicators)
  - Workflow A étapes 6-7-8 (configuration buffer)
  - Exemples visuels buffer sur carte
  - Comparaison types: Standard vs Fast vs Segment

### User Guide - EXPLORING  
- `exploring-features.md` → 
  - Groupe F complet (6 push buttons avec détails)
  - Groupe G complet (selection widgets)
  - Workflow B complet (exploration interactive, 10 étapes)
  - **Sections détaillées par bouton**:
    - **Identify**: Surbrillance temporaire, flash animation, use cases
    - **Zoom**: Zoom automatique adaptatif, marges, échelles
    - **Select**: Mode sélection interactive, toggle behavior, shortcuts
    - **Track**: Synchronisation bidirectionnelle carte ↔ widgets
    - **Link**: Liaison configuration widgets, cascade updates
    - **Reset Properties**: Réinitialisation complète propriétés couche

### User Guide - EXPORTING
- `export-features.md` → 
  - Groupe H complet (layer selector, format selector, indicators)
  - Groupe I complet (CRS transformation, style export)
  - Groupe J complet (output folder, batch mode, ZIP)
  - Workflow A étapes 12-14 (export après filtrage)
  - Workflow C étapes 7-8 (export Shapefile)
  - Tableaux comparatifs formats (GPKG vs SHP vs GeoJSON vs KML)
  - Meilleures pratiques export par format

### User Guide - Configuration & Advanced
- `configuration.md` → 
  - Groupe K (JSON tree view, theme selector, advanced options)
  - Guide édition config.json via interface
  - Personnalisation thèmes UI

- `advanced-features.md` → 
  - Historique filtres (si implémenté)
  - Favoris filtres (si implémenté)
  - Configuration avancée backends

### Workflows & Getting Started
- `quick-start.md` → Workflow C (simple, 8 étapes, débutants)
- `first-filter.md` → Workflow A (complet, 14 étapes, feature complete)
- `workflows.md` → 
  - Les 4 workflows complets
  - Diagrammes Mermaid pour chaque workflow
  - Liens croisés vers pages détaillées

### Technical Documentation
- `backends.md` → 
  - Groupe A (backend indicators)
  - Comparaison performances PostgreSQL⚡ / Spatialite / OGR
  
- `troubleshooting.md` → 
  - Groupe L (messages erreur/warning/success)
  - Cas d'erreur fréquents avec screenshots

### Syntaxe Markdown pour Images
```markdown
<!-- Image simple avec alt text -->
![Layer Selector](/img/ui-components/ui-filtering-layer-selector.png)
*Multi-sélection de couches avec indicateurs de géométrie*

<!-- Image avec lien vers workflow -->
Pour le workflow complet, consultez [Filtrage Géométrique](./geometric-filtering.md).

<!-- Étape de workflow -->
**Étape 4 - Configuration Buffer**:
![Configure Buffer](/img/workflows/workflow-filtering-06.png)
*Distance: 200m, Type: Standard, Unité: Mètres*

<!-- Galerie d'images -->
| Identify | Zoom | Select |
|----------|------|--------|
| ![Identify](/img/ui-components/ui-exploring-identify-btn.png) | ![Zoom](/img/ui-components/ui-exploring-zoom-btn.png) | ![Select](/img/ui-components/ui-exploring-select-btn.png) |
| Surbrillance features | Zoom automatique | Mode sélection |
```
    - Zoom: Zoomer sur sélection
    - Select: Mode sélection interactif
    - Track: Suivi des sélections dans widgets
    - Link: Liaison widgets configuration
    - Reset Properties: Réinitialiser propriétés couche

### User Guide - EXPORTING
- `export-features.md` → 
  - Groupe G (tous les composants export)
  - Workflow A étapes 9-12 (export après filtrage)
  - Tableaux comparatifs formats

### History & Configuration
- `filter-history.md` → 
  - Groupe H (dropdown, widget compact)
  - Workflow A étape 8 & Workflow C étape 5-6
- `advanced-features.md` → 
  - Configuration avancée
  - Favoris (à documenter si implémenté)

### Workflows
- `quick-start.md` → Workflow C (simple, 6 étapes)
- `first-filter.md` → Workflow A (complet, 12 étapes)
- `workflows.md` → Les 3 workflows + diagrammes Mermaid

### Configuration & Technical
- `configuration.md` → Groupe H (JSON tree, thème selector)
- `themes/*.md` → Mosaïque thèmes + exemples
- `backends/*.md` → Graphique performances
- `troubleshooting.md` → Groupe I (messages erreur)

### Syntaxe Markdown
```markdown
![Layer Selector](/img/ui-components/ui-layer-selector.png)
*Sélecteur de couche avec indicateurs de type géométrie*

Pour voir le workflow complet, consultez le [Guide du Premier Filtre](./first-filter.md).
Étape 4 du workflow:
![Configure Buffer](/img/workflow/workflow-04.png)
```

---

## 📅 Planning (10-14 jours)

### ✅ Sprint 1: COMPLÉTÉ
- Configuration Docusaurus
- 35+ pages créées
- 9 captures initiales (install + quickstart)
- Déploiement GitHub Pages actif

### Sprint 2: UI Components (3-4 jours) ⭐ PRIORITÉ
**Jour 1-2**: Groupes A-D (15 captures)
- Projet QGIS test standardisé
- Layer Selection, Filtering, Geometric, History

**Jour 3-4**: Groupes E-G (10 captures)
- Export, Configuration, Progress
- Annotations + optimisation

**Livrable**: 25 composants UI documentés

### Sprint 3: Workflow (2 jours)
- Scénario test (bâtiments + routes)
- 10 étapes capturées et annotées
- Optimisation web (<150KB/image)

**Livrable**: 1 workflow réutilisable

### Sprint 4: Contenu Textuel (3-4 jours)
- Rédaction 7 pages User Guide (texte + réf images)
- `filtering-basics.md`, `geometric-filtering.md`, `buffer-operations.md`
- `export-features.md`, `filter-history.md`, `advanced-features.md`
- `configuration.md`

**Livrable**: User Guide complet

### Sprint 5: Visuels Techniques (1-2 jours)
- Graphique perf backends (Python/Matplotlib)
- Mosaïque thèmes (montage 2x4)
- Messages erreur types (3 captures)

**Livrable**: Sections techniques illustrées

### Sprint 6: Polish (1-2 jours)
- Vérification liens
- Optimisation images WebP
- Textes alt (accessibilité)
- Tests navigation
- Mise à jour STATUS.md

**Livrable**: Documentation déployable

---

## 📊 Standards de Qualité

### Captures d'écran
- **Résolution**: 1920x1080 min
- **Format**: PNG → WebP (optimisation)
- **Poids**: <150KB/image
- **Nommage**: `ui-component-name.png`, `workflow-NN.png`

### Annotations
- Flèches rouges (#FF0000) pour pointer
- Rectangles arrondis (3px) pour délimiter
- Numéros en cercles pour séquences
- Police sans-serif 14-16pt, contraste élevé

### Environnement standard
- QGIS 3.28+ LTS
- Interface: Français
- Thème QGIS: Blend of Gray
- Panel FilterMate: Ancré droite, 400px
- Zoom adapté (tout visible)

### Organisation
```
website/static/img/
├── ui-components/      # 25 composants
├── workflow/           # 10 étapes
├── backends/           # 1 graphique
├── themes/             # 1 mosaïque
└── troubleshooting/    # 3 erreurs
```

---

## ✅ Checklist Sprint 2 (Démarrage)

### Préparation (30 min)
- [ ] Projet QGIS test (3 couches: points/lignes/polygones)
- [ ] FilterMate configuré avec données pertinentes
- [ ] Créer `website/static/img/ui-components/`
- [ ] Outil capture prêt (Flameshot/ShareX)

### Jour 1 (3-4h)
- [ ] Groupe A: ui-layer-selector, ui-layer-info, ui-backend-indicator
- [ ] Groupe B (1/2): ui-expression-builder, ui-field-selector, ui-validation-success

### Jour 2 (3-4h)
- [ ] Groupe B (2/2): ui-validation-error, ui-apply-button
- [ ] Groupe C: ui-spatial-predicate, ui-reference-layer, ui-buffer-controls, ui-buffer-preview

### Jour 3 (3h)
- [ ] Groupe D: ui-history-list, ui-history-entry, ui-favorites-panel, ui-context-menu
- [ ] Groupe E: ui-export-format, ui-field-selector-export, ui-crs-transform

### Jour 4 (2-3h)
- [ ] Groupe F: ui-json-tree, ui-theme-selector, ui-config-tabs
- [ ] Groupe G: ui-progress-bar, ui-message-bar, ui-task-notification
- [ ] Annotations + optimisation toutes images

---

## 📈 Métriques de Succès

### Quantitatifs
- [ ] 35-40 captures essentielles (vs 150+)
- [ ] 100% pages placeholders complétées (texte)
- [ ] Total images: <5MB (vs >20MB)
- [ ] <2s temps chargement
- [ ] Score Lighthouse >90

### Qualitatifs
- [ ] 1 composant UI = 1 seule capture (réutilisée partout)
- [ ] Navigation intuitive (testée 3+ users)
- [ ] Zéro redondance
- [ ] Maintenance facile (1 update → toutes pages)
- [ ] Accessibilité WCAG 2.1 AA

---

**Statut**: 🟢 Plan optimisé prêt  
**Prochaine étape**: Sprint 2 - UI Components (Démarrage immédiat possible)  
**Contact**: Simon Ducorneau | [GitHub](https://github.com/sducournau/filter_mate)
