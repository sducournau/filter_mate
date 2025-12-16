# 🎨 Visualisation UI - Onglets RASTER & NETWORK

**Date:** 16 décembre 2025  
**Version:** 3.0.0-alpha  
**Fichier UI:** `filter_mate_dockwidget_base.ui`

---

## 📐 Structure Générale du QToolBox

```
┌─────────────────────────────────────────────────────────────┐
│ FilterMate                                               [×]│
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 📂 EXPLORING (frame_exploring)                          │ │
│ │    [Contenu exploration - couches, sélection, etc.]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🔧 TOOLBOX (toolBox_tabTools)                           │ │
│ │ ┌───────────────────────────────────────────────────┐   │ │
│ │ │ [🔍 FILTERING] [🗺️ RASTER] [🔗 NETWORK] [💾 EXPORT]│   │ │
│ │ └───────────────────────────────────────────────────┘   │ │
│ │                                                         │ │
│ │    (Contenu de l'onglet actif)                          │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ⚡ ACTIONS (frame_actions)                              │ │
│ │    [Boutons d'action: Filtrer, Exporter, etc.]          │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Onglet RASTER - Visualisation Détaillée

```
┌─────────────────────────────────────────────────────────────┐
│ 🗺️ RASTER                                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ICÔNES          │  WIDGETS DE VALEURS                      │
│  (38-48px)       │  (Expanding)                             │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 🗺️   │ ←──────┼─→│ [▼ Sélectionner couche raster... ] │ │
│  │      │        │  │    mMapLayerComboBox_raster_layer   │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  raster_layer    │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 📊   │ ←──────┼─→│ [▼ Band 1                         ] │ │
│  │      │        │  │    comboBox_raster_band             │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  raster_band     │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 📍   │ ←──────┼─→│ [▼ Sélectionner couche cible...  ] │ │
│  │      │        │  │    mMapLayerComboBox_raster_target  │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  raster_target   │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 🎯   │ ←──────┼─→│ [▼ Nearest                        ] │ │
│  │      │        │  │    comboBox_raster_sampling_method  │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  raster_sampling │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌────────────────┬────────────────────┐ │
│  │ 📏   │ ←──────┼─→│ Min: [0     ] │ Max: [1000      ] │ │
│  │      │        │  │ doubleSpinBox  │ doubleSpinBox      │ │
│  └──────┘        │  │ _raster_min    │ _raster_max        │ │
│  pushButton_     │  └────────────────┴────────────────────┘ │
│  checkable_      │                                          │
│  raster_filter   │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 📝   │ ←──────┼─→│ [altitude                        ] │ │
│  │      │        │  │    lineEdit_raster_output_field     │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  raster_output   │                                          │
│                  │                                          │
│                  │  ┌─────────────────────────────────────┐ │
│                  │  │ ☑ Slope  ☑ Aspect  ☐ Zonal Stats  │ │
│                  │  │ checkBox_raster_add_slope           │ │
│                  │  │ checkBox_raster_add_aspect          │ │
│                  │  │ checkBox_raster_zonal_stats         │ │
│                  │  └─────────────────────────────────────┘ │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

---

## 🔗 Onglet NETWORK - Visualisation Détaillée

```
┌─────────────────────────────────────────────────────────────┐
│ 🔗 NETWORK                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ICÔNES          │  WIDGETS DE VALEURS                      │
│  (38-48px)       │  (Expanding)                             │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 🔗   │ ←──────┼─→│ [▼ Sélectionner réseau (lignes)  ] │ │
│  │      │        │  │    mMapLayerComboBox_network_layer  │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  network_layer   │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ ⚖️   │ ←──────┼─→│ [▼ longueur_m                     ] │ │
│  │      │        │  │    mFieldComboBox_network_cost      │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  network_cost    │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 🏢   │ ←──────┼─→│ [▼ Points_BRO                     ] │ │
│  │      │        │  │    mMapLayerComboBox_network_bro    │ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  network_bro     │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 👥   │ ←──────┼─→│ [▼ Clients_FTTH                   ] │ │
│  │      │        │  │    mMapLayerComboBox_network_clients│ │
│  └──────┘        │  └─────────────────────────────────────┘ │
│  pushButton_     │                                          │
│  checkable_      │                                          │
│  network_client  │                                          │
│                  │                                          │
│  ┌──────┐        │  ┌─────────────────────────────────────┐ │
│  │ 🧭   │ ←──────┼─→│ [▼ Shortest Path                  ] │ │
│  │      │        │  │    comboBox_network_analysis_type   │ │
│  └──────┘        │  │    - Shortest Path                  │ │
│  pushButton_     │  │    - Service Area                   │ │
│  checkable_      │  │    - Nearest Facility               │ │
│  network_        │  │    - Optimal Assignment             │ │
│  analysis_type   │  │    - Feasibility Analysis           │ │
│                  │  └─────────────────────────────────────┘ │
│                  │                                          │
│  ┌──────┐        │  ┌────────────────┬────────────────────┐ │
│  │ ⚙️   │ ←──────┼─→│ Max dist:      │ Capacity:         │ │
│  │      │        │  │ [2000    ] m   │ [128        ]     │ │
│  └──────┘        │  │ spinBox_       │ spinBox_           │ │
│  pushButton_     │  │ network_       │ network_           │ │
│  checkable_      │  │ max_distance   │ capacity           │ │
│  network_        │  └────────────────┴────────────────────┘ │
│  constraints     │                                          │
│                  │  ┌─────────────────────────────────────┐ │
│                  │  │ ☐ Use MNT  ☑ Bidirectional         │ │
│                  │  │ checkBox_network_use_mnt            │ │
│                  │  │ checkBox_network_bidirectional      │ │
│                  │  └─────────────────────────────────────┘ │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

---

## 🎨 Liste des Icônes à Créer

### Icônes Existantes (à réutiliser)

| Fichier | Utilisation Actuelle | Réutilisation Proposée |
|---------|---------------------|------------------------|
| `raster.png` | Onglet RASTER | ✅ Déjà utilisé |
| `network.png` | Onglet NETWORK | ✅ Déjà utilisé |
| `layer.png` | Sélection couche | `pushButton_checkable_raster_layer` |
| `layers.png` | Multi-couches | - |
| `projection.png` | Projection | - |
| `geo.png` | Géométrie | `pushButton_checkable_network_layer` |
| `link.png` | Lien/réseau | Alternatif pour network |
| `filter.png` | Filtrage | `pushButton_checkable_raster_filter_range` |
| `zoom.png` | Zoom | - |

### 🆕 Icônes à Créer (16x16 PNG)

#### Pour l'onglet RASTER

| Nom Fichier | Bouton Associé | Description | Emoji Ref |
|-------------|----------------|-------------|-----------|
| `raster_band.png` | `pushButton_checkable_raster_band` | Bandes spectrales (couches superposées) | 📊 |
| `raster_target.png` | `pushButton_checkable_raster_target_layer` | Couche cible (point avec cible) | 🎯 |
| `raster_sampling.png` | `pushButton_checkable_raster_sampling_method` | Échantillonnage (grille avec points) | 📐 |
| `raster_range.png` | `pushButton_checkable_raster_filter_range` | Plage de valeurs (slider min-max) | 📏 |
| `raster_output.png` | `pushButton_checkable_raster_output_field` | Champ de sortie (texte/colonne) | 📝 |

#### Pour l'onglet NETWORK

| Nom Fichier | Bouton Associé | Description | Emoji Ref |
|-------------|----------------|-------------|-----------|
| `network_cost.png` | `pushButton_checkable_network_cost_field` | Coût/poids (balance ou €) | ⚖️ |
| `network_bro.png` | `pushButton_checkable_network_bro_layer` | Point BRO (bâtiment/antenne) | 🏢 |
| `network_client.png` | `pushButton_checkable_network_client_layer` | Clients (groupe de personnes) | 👥 |
| `network_analysis.png` | `pushButton_checkable_network_analysis_type` | Type d'analyse (boussole/graphe) | 🧭 |
| `network_constraints.png` | `pushButton_checkable_network_constraints` | Contraintes (engrenage/règle) | ⚙️ |

---

## 📋 Spécifications des Icônes

### Format et Dimensions

```
Format:        PNG avec transparence
Dimensions:    16x16 pixels (affichage dans boutons)
               32x32 pixels (haute résolution optionnel)
Couleurs:      
  - Mode clair: #333333 (gris foncé)
  - Mode sombre: #E0E0E0 (gris clair)
Style:         Flat, minimaliste, cohérent avec QGIS
```

### Arborescence Proposée

```
icons/
├── raster/
│   ├── raster.png          (existant, à copier)
│   ├── raster_band.png     🆕
│   ├── raster_target.png   🆕
│   ├── raster_sampling.png 🆕
│   ├── raster_range.png    🆕
│   └── raster_output.png   🆕
│
├── network/
│   ├── network.png         (existant, à copier)
│   ├── network_cost.png    🆕
│   ├── network_bro.png     🆕
│   ├── network_client.png  🆕
│   ├── network_analysis.png🆕
│   └── network_constraints.png 🆕
│
└── (icônes existantes)
```

---

## 🔄 Mapping Boutons → Icônes

### Onglet RASTER

| Widget Name | Icône à Utiliser | Tooltip |
|-------------|------------------|---------|
| `pushButton_checkable_raster_layer` | `raster.png` ou `layer.png` | "Raster layer (MNT, NDVI)" |
| `pushButton_checkable_raster_band` | `raster_band.png` 🆕 | "Raster band selection" |
| `pushButton_checkable_raster_target_layer` | `raster_target.png` 🆕 | "Target vector layer" |
| `pushButton_checkable_raster_sampling_method` | `raster_sampling.png` 🆕 | "Sampling method" |
| `pushButton_checkable_raster_filter_range` | `raster_range.png` 🆕 ou `filter.png` | "Filter by value range" |
| `pushButton_checkable_raster_output_field` | `raster_output.png` 🆕 | "Output field name" |

### Onglet NETWORK

| Widget Name | Icône à Utiliser | Tooltip |
|-------------|------------------|---------|
| `pushButton_checkable_network_layer` | `network.png` ou `link.png` | "Network layer (lines)" |
| `pushButton_checkable_network_cost_field` | `network_cost.png` 🆕 | "Cost/weight field" |
| `pushButton_checkable_network_bro_layer` | `network_bro.png` 🆕 | "BRO/Facility points layer" |
| `pushButton_checkable_network_client_layer` | `network_client.png` 🆕 | "Client/destination points layer" |
| `pushButton_checkable_network_analysis_type` | `network_analysis.png` 🆕 | "Analysis type" |
| `pushButton_checkable_network_constraints` | `network_constraints.png` 🆕 | "Analysis constraints" |

---

## 🎯 Priorité de Création

### Haute Priorité (Bloquant pour l'UI)

1. ✅ `raster.png` - **Existe déjà**
2. ✅ `network.png` - **Existe déjà**
3. 🆕 `raster_band.png` - Essentiel pour sélection de bande
4. 🆕 `network_bro.png` - Essentiel pour télécom FTTH
5. 🆕 `network_client.png` - Essentiel pour télécom FTTH

### Moyenne Priorité

6. 🆕 `raster_target.png` - Peut utiliser `layer.png` temporairement
7. 🆕 `network_cost.png` - Peut utiliser icône générique
8. 🆕 `network_analysis.png` - Peut utiliser icône générique

### Basse Priorité (Peut réutiliser existantes)

9. 🆕 `raster_sampling.png` - Utiliser `geo.png` temporairement
10. 🆕 `raster_range.png` - Utiliser `filter.png` temporairement
11. 🆕 `raster_output.png` - Utiliser icône texte générique
12. 🆕 `network_constraints.png` - Utiliser `parameters.png` temporairement

---

## 📊 Résumé

| Catégorie | Existantes | À Créer | Total |
|-----------|------------|---------|-------|
| Onglet RASTER | 1 | 5 | 6 |
| Onglet NETWORK | 1 | 5 | 6 |
| **TOTAL** | **2** | **10** | **12** |

### Icônes Réutilisables en Attendant

```python
TEMPORARY_ICON_MAPPING = {
    # RASTER
    'pushButton_checkable_raster_layer': 'raster.png',
    'pushButton_checkable_raster_band': 'layers.png',  # temporaire
    'pushButton_checkable_raster_target_layer': 'layer.png',  # temporaire
    'pushButton_checkable_raster_sampling_method': 'geo.png',  # temporaire
    'pushButton_checkable_raster_filter_range': 'filter.png',  # temporaire
    'pushButton_checkable_raster_output_field': 'datatype.png',  # temporaire
    
    # NETWORK
    'pushButton_checkable_network_layer': 'network.png',
    'pushButton_checkable_network_cost_field': 'link.png',  # temporaire
    'pushButton_checkable_network_bro_layer': 'geo.png',  # temporaire
    'pushButton_checkable_network_client_layer': 'layer.png',  # temporaire
    'pushButton_checkable_network_analysis_type': 'parameters.png',  # temporaire
    'pushButton_checkable_network_constraints': 'buffer_value.png',  # temporaire
}
```

---

## 🔧 Prochaines Étapes

1. **Créer les 10 nouvelles icônes** (ou utiliser mapping temporaire)
2. **Ajouter le code d'initialisation** dans `filter_mate_dockwidget.py` pour :
   - Configurer les filtres des QgsMapLayerComboBox
   - Connecter les signaux des boutons checkable
   - Charger les icônes sur les boutons
3. **Implémenter les backends** (`raster_backend.py`, `network_backend.py`)
4. **Tester l'interface** dans QGIS

---

*Document généré automatiquement - FilterMate v3.0.0-alpha*
