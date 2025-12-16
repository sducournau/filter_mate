# 🎨 Proposition UI: Raster & Network Analysis pour FilterMate

**Date de création:** 16 décembre 2025  
**Version cible:** 3.0.0  
**Auteur:** FilterMate Team  
**Statut:** 📋 Proposition

---

## 📋 Résumé

Ce document propose l'interface utilisateur pour les nouvelles fonctionnalités d'analyse raster et réseau de FilterMate v3.0.0. L'approche retenue privilégie l'intégration harmonieuse avec l'UI existante tout en offrant des capacités avancées accessibles.

---

## 🏗️ Architecture UI Proposée

### Option A: Onglets Intégrés (Recommandé)

**Concept:** Ajout de 2 nouveaux onglets dans le dock widget principal

```
┌─────────────────────────────────────────────────────────────┐
│ FilterMate                                               [×]│
├─────────────────────────────────────────────────────────────┤
│ [EXPLORER] [FILTER] [EXPORT] [RASTER] [NETWORK]            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    (Contenu de l'onglet actif)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Avantages:**
- ✅ Intégration cohérente avec l'existant
- ✅ Navigation familière pour les utilisateurs
- ✅ Pas de fenêtre supplémentaire
- ✅ Respect du design system actuel

**Inconvénients:**
- ⚠️ Espace vertical limité
- ⚠️ Nécessite adaptation responsive

---

### Option B: Panels Dépliables

**Concept:** Panels collapsibles sous les sections existantes

```
┌─────────────────────────────────────────────────────────────┐
│ ▼ EXPLORATION                                               │
│   [Contenu exploration...]                                  │
├─────────────────────────────────────────────────────────────┤
│ ▼ FILTRAGE                                                  │
│   [Contenu filtrage...]                                     │
├─────────────────────────────────────────────────────────────┤
│ ▶ ANALYSE RASTER (cliquer pour déplier)                     │
├─────────────────────────────────────────────────────────────┤
│ ▶ ANALYSE RÉSEAU (cliquer pour déplier)                     │
├─────────────────────────────────────────────────────────────┤
│ ▼ EXPORT                                                    │
│   [Contenu export...]                                       │
└─────────────────────────────────────────────────────────────┘
```

**Avantages:**
- ✅ Visibilité de toutes les options
- ✅ Espace économisé quand replié

**Inconvénients:**
- ⚠️ Interface plus chargée
- ⚠️ Scroll possible

---

### Option C: Dock Widgets Séparés

**Concept:** Nouveaux dock widgets indépendants

**Avantages:**
- ✅ Flexibilité de positionnement
- ✅ Indépendance fonctionnelle

**Inconvénients:**
- ❌ Gestion multi-fenêtres
- ❌ Incohérence visuelle potentielle

---

## 🎯 Recommandation: Option A avec Variante Hybride

Combinaison des onglets (Option A) avec des sections collapsibles à l'intérieur de chaque onglet.

---

## 📐 Spécifications Détaillées

### 1. Onglet RASTER

#### 1.1 Structure Générale

```
┌─────────────────────────────────────────────────────────────┐
│                     ANALYSE RASTER                          │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ SOURCE RASTER                                         │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ Couche Raster:    [🗺️ MNT_IGN.tif              ▼] │ │ │
│ │ │ Bande:            [1 - Altitude (m)            ▼] │ │ │
│ │ │ CRS:              EPSG:2154 (Lambert-93)           │ │ │
│ │ │ Résolution:       25m × 25m                        │ │ │
│ │ │ Étendue:          ✅ Compatible avec couche cible   │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ COUCHE CIBLE                                          │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ Couche Vectorielle: [📍 Clients_FTTH          ▼] │ │ │
│ │ │ Entités:          12,450 points                    │ │ │
│ │ │ Sélection:        ○ Toutes  ● Sélection (47)       │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ OPTIONS D'ÉCHANTILLONNAGE                             │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ Méthode:                                            │ │ │
│ │ │   ● Nearest (Plus proche)                           │ │ │
│ │ │   ○ Bilinear (Interpolation bilinéaire)             │ │ │
│ │ │   ○ Cubic (Interpolation cubique)                   │ │ │
│ │ │                                                     │ │ │
│ │ │ Champ de sortie: [altitude_m         ] [Auto ▼]    │ │ │
│ │ │                                                     │ │ │
│ │ │ ☑️ Ajouter statistiques de pente                    │ │ │
│ │ │ ☑️ Ajouter orientation (exposition)                 │ │ │
│ │ │ ☐ Ajouter statistiques zonales (polygones)          │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ FILTRE PAR VALEURS RASTER                             │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ ☑️ Activer le filtre raster                         │ │ │
│ │ │                                                     │ │ │
│ │ │ Altitude:  Min [0       ] m  Max [500     ] m      │ │ │
│ │ │            ├───────●━━━━━━━━━━━━━━●───────┤         │ │ │
│ │ │            0                              1500      │ │ │
│ │ │                                                     │ │ │
│ │ │ Pente:     Max [30      ] %                        │ │ │
│ │ │            ├━━━━━━━━━━━━━━━━━●───────────┤          │ │ │
│ │ │            0%                            60%        │ │ │
│ │ │                                                     │ │ │
│ │ │ Exposition: ☑️ N  ☑️ S  ☐ E  ☐ O                   │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ACTIONS                                                 │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │  [🔍 Prévisualiser]  [▶️ Échantillonner]  [🗑️]     │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ╔═════════════════════════════════════════════════════════╗ │
│ ║ 📊 RÉSULTATS                                            ║ │
│ ║ ─────────────────────────────────────────────────────── ║ │
│ ║ Entités dans plage: 8,234 / 12,450 (66.1%)              ║ │
│ ║ Altitude moyenne:   245.7 m                             ║ │
│ ║ Pente moyenne:      12.3%                               ║ │
│ ║                                                         ║ │
│ ║ [Appliquer comme filtre] [Exporter résultats CSV]       ║ │
│ ╚═════════════════════════════════════════════════════════╝ │
└─────────────────────────────────────────────────────────────┘
```

#### 1.2 Mode Compact (Écrans < 1920×1080)

```
┌─────────────────────────────────────────────────────────────┐
│                   ANALYSE RASTER                            │
├─────────────────────────────────────────────────────────────┤
│ Raster: [MNT_IGN.tif           ▼] Bande: [1     ▼]         │
│ Cible:  [Clients_FTTH          ▼] ○ Tous ● Sélection       │
├─────────────────────────────────────────────────────────────┤
│ Échantillonnage: ● Nearest ○ Bilinear ○ Cubic              │
│ Champ sortie:    [altitude_m         ]                     │
│ ☑️ Pente  ☑️ Exposition  ☐ Stats zonales                   │
├─────────────────────────────────────────────────────────────┤
│ ☑️ Filtrer | Alt: [0   ]-[500  ]m | Pente max: [30  ]%     │
├─────────────────────────────────────────────────────────────┤
│ [Prévisualiser] [▶️ Exécuter] | 8,234/12,450 (66%)         │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. Onglet NETWORK (RÉSEAU)

#### 2.1 Structure Générale

```
┌─────────────────────────────────────────────────────────────┐
│                    ANALYSE RÉSEAU                           │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ CONFIGURATION RÉSEAU                                  │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ Couche Réseau:     [🔗 Cables_FO             ▼]    │ │ │
│ │ │ Champ de coût:     [longueur_m               ▼]    │ │ │
│ │ │ Direction:         [○ Bidirectionnel ● Orienté  ]   │ │ │
│ │ │ Champ direction:   [sens                     ▼]    │ │ │
│ │ │                                                     │ │ │
│ │ │ Backend: ● NetworkX (Python)                        │ │ │
│ │ │          ○ pgRouting (PostgreSQL) ⚠️ Non disponible │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ POINTS D'INTÉRÊT (TÉLÉCOM)                            │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ Couche BRO:       [📍 Points_BRO            ▼]     │ │ │
│ │ │ Champ ID BRO:     [bro_id                   ▼]     │ │ │
│ │ │ Champ capacité:   [capacite_max             ▼]     │ │ │
│ │ │                                                     │ │ │
│ │ │ Couche Clients:   [📍 Clients_FTTH          ▼]     │ │ │
│ │ │ Champ ID Client:  [client_id                ▼]     │ │ │
│ │ │ Champ priorité:   [priorite                 ▼]     │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ TYPE D'ANALYSE                                        │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ ● Plus court chemin (A → B)                         │ │ │
│ │ │ ○ Zone de desserte (Isochrone)                      │ │ │
│ │ │ ○ Équipement le plus proche                         │ │ │
│ │ │ ○ Assignation optimale BRO → Clients                │ │ │
│ │ │ ○ Analyse de faisabilité                            │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ▼ CONTRAINTES                                           │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ ☑️ Distance max réseau:  [2000    ] m               │ │ │
│ │ │ ☑️ Capacité BRO:         [128     ] clients         │ │ │
│ │ │                                                     │ │ │
│ │ │ ── Contraintes Terrain (optionnel) ──               │ │ │
│ │ │ ☐ Pente max:             [30      ] % [📁 MNT...]   │ │ │
│ │ │ ☐ NDVI max:              [0.6     ]   [📁 NDVI...]  │ │ │
│ │ │                                                     │ │ │
│ │ │ ── Obstacles à éviter ──                            │ │ │
│ │ │ ☐ Forêts       [📁 Sélectionner...]                 │ │ │
│ │ │ ☐ Cours d'eau  [📁 Sélectionner...]                 │ │ │
│ │ │ ☐ Bâtiments    [📁 Sélectionner...]                 │ │ │
│ │ │ ☐ Zones protégées [📁 Sélectionner...]              │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ACTIONS                                                 │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ [🔨 Construire Graphe] [▶️ Analyser] [📊 Rapport]   │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ╔═════════════════════════════════════════════════════════╗ │
│ ║ 📊 RÉSULTATS                                            ║ │
│ ║ ─────────────────────────────────────────────────────── ║ │
│ ║ Graphe: 23,456 nœuds | 45,678 arêtes                    ║ │
│ ║ Clients analysés: 1,234                                 ║ │
│ ║ Clients raccordables: 1,187 (96.2%)                     ║ │
│ ║ Longueur totale câble: 45,234 m                         ║ │
│ ║ Coût estimé moyen/client: 234 €                         ║ │
│ ║                                                         ║ │
│ ║ ┌─────────────────────────────────────────────────────┐ ║ │
│ ║ │ BRO         │ Clients │ Capacité │ Distance moy.  │ ║ │
│ ║ │─────────────┼─────────┼──────────┼────────────────│ ║ │
│ ║ │ BRO_001     │ 98/128  │ 76.6%    │ 456 m          │ ║ │
│ ║ │ BRO_002     │ 127/128 │ 99.2%    │ 523 m          │ ║ │
│ ║ │ BRO_003     │ 45/128  │ 35.2%    │ 789 m          │ ║ │
│ ║ └─────────────────────────────────────────────────────┘ ║ │
│ ║                                                         ║ │
│ ║ [📍 Zoom entités] [Appliquer filtre] [💾 Export CSV]    ║ │
│ ╚═════════════════════════════════════════════════════════╝ │
└─────────────────────────────────────────────────────────────┘
```

#### 2.2 Mode Compact (Écrans < 1920×1080)

```
┌─────────────────────────────────────────────────────────────┐
│                   ANALYSE RÉSEAU                            │
├─────────────────────────────────────────────────────────────┤
│ Réseau: [Cables_FO       ▼] Coût: [longueur_m ▼] ○Bi ●Dir  │
│ BRO:    [Points_BRO      ▼] Clients: [Clients_FTTH    ▼]   │
├─────────────────────────────────────────────────────────────┤
│ Analyse: ● Chemin ○ Zone ○ Proche ○ Assignation ○ Faisab.  │
├─────────────────────────────────────────────────────────────┤
│ ☑️ Dist. max: [2000]m  ☑️ Capacité: [128] clients          │
│ ☐ Pente: [30]%  ☐ NDVI: [0.6]  [▶ Contraintes avancées]   │
├─────────────────────────────────────────────────────────────┤
│ [🔨 Graphe] [▶️ Analyser] | 1,187/1,234 (96%) raccordables │
└─────────────────────────────────────────────────────────────┘
```

---

### 3. Vue Plus Court Chemin (Sous-panel)

```
┌─────────────────────────────────────────────────────────────┐
│ PLUS COURT CHEMIN                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Point départ:   [📍 Sélectionner sur carte...]             │
│                 ou [BRO_001              ▼]                 │
│                                                             │
│ Point arrivée:  [📍 Sélectionner sur carte...]             │
│                 ou [CLIENT_1234          ▼]                 │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ [▶️ Calculer chemin]                                        │
│                                                             │
│ ╔═════════════════════════════════════════════════════════╗ │
│ ║ RÉSULTAT                                                ║ │
│ ║ Distance réseau: 1,234 m                                ║ │
│ ║ Nombre de tronçons: 12                                  ║ │
│ ║ Coût estimé: 123.40 €                                   ║ │
│ ║                                                         ║ │
│ ║ [📍 Afficher chemin] [💾 Exporter GeoJSON]              ║ │
│ ╚═════════════════════════════════════════════════════════╝ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 4. Vue Zone de Desserte (Isochrone)

```
┌─────────────────────────────────────────────────────────────┐
│ ZONE DE DESSERTE (ISOCHRONE)                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Point central:  [📍 Sélectionner sur carte...]             │
│                 ou [BRO_001              ▼]                 │
│                                                             │
│ Distance max:   [2000        ] m                           │
│                 ├━━━━━━━━━━━━━━●─────────────────┤          │
│                 0                           5000 m          │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ Style de rendu:                                             │
│ ● Polygone (enveloppe)                                      │
│ ○ Arêtes accessibles                                        │
│ ○ Gradients (bandes de distance)                            │
│                                                             │
│ [▶️ Calculer zone]                                          │
│                                                             │
│ ╔═════════════════════════════════════════════════════════╗ │
│ ║ RÉSULTAT                                                ║ │
│ ║ Surface couverte: 3.45 km²                              ║ │
│ ║ Clients dans zone: 234                                  ║ │
│ ║ Tronçons accessibles: 567                               ║ │
│ ║                                                         ║ │
│ ║ [📍 Afficher zone] [Sélectionner clients] [💾 Export]   ║ │
│ ╚═════════════════════════════════════════════════════════╝ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Design System

### Palette de Couleurs

#### Mode Clair (Blend of Gray)
```css
--bg-primary: #f5f5f5;
--bg-secondary: #ffffff;
--bg-section: #e8e8e8;
--text-primary: #333333;
--text-secondary: #666666;
--border: #cccccc;
--accent: #3498db;
--success: #27ae60;
--warning: #f39c12;
--error: #e74c3c;
```

#### Mode Sombre (Night Mapping)
```css
--bg-primary: #1e1e1e;
--bg-secondary: #2d2d2d;
--bg-section: #383838;
--text-primary: #e0e0e0;
--text-secondary: #a0a0a0;
--border: #555555;
--accent: #5dade2;
--success: #2ecc71;
--warning: #f1c40f;
--error: #e74c3c;
```

### Icônes Proposées

| Fonction | Icône | Description |
|----------|-------|-------------|
| Raster | 🗺️ | Carte topographique |
| Réseau | 🔗 | Chaîne de liens |
| Points | 📍 | Marqueur de position |
| Chemin | ➡️ | Flèche directionnelle |
| Zone | ⭕ | Cercle/zone |
| Graphe | 📊 | Graphique |
| Construire | 🔨 | Marteau |
| Exécuter | ▶️ | Play |
| Rapport | 📋 | Clipboard |
| Export | 💾 | Disquette |
| Avertissement | ⚠️ | Triangle attention |
| Succès | ✅ | Check vert |

### Dimensions Adaptatives

#### Profile COMPACT (< 1920×1080)
```python
RASTER_SECTION_HEIGHT = 140  # px
NETWORK_SECTION_HEIGHT = 150  # px
RESULTS_PANEL_HEIGHT = 100  # px
INPUT_HEIGHT = 24  # px
BUTTON_SIZE = 18  # px
SPACING = 3  # px
MARGINS = 2  # px
```

#### Profile NORMAL (≥ 1920×1080)
```python
RASTER_SECTION_HEIGHT = 180  # px
NETWORK_SECTION_HEIGHT = 200  # px
RESULTS_PANEL_HEIGHT = 140  # px
INPUT_HEIGHT = 30  # px
BUTTON_SIZE = 24  # px
SPACING = 6  # px
MARGINS = 4  # px
```

---

## 🔧 Composants UI à Créer

### 1. Nouveaux Widgets

#### RasterLayerComboBox
```python
class RasterLayerComboBox(QgsMapLayerComboBox):
    """ComboBox filtré pour couches raster uniquement."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.setAllowEmptyLayer(True)
        self.setShowCrs(True)
```

#### BandSelectorComboBox
```python
class BandSelectorComboBox(QComboBox):
    """Sélecteur de bandes avec info (nom, type, stats)."""
    
    bandChanged = pyqtSignal(int)
    
    def populate_from_raster(self, raster_layer: QgsRasterLayer):
        """Peuple avec les bandes du raster."""
        pass
```

#### RangeSliderWidget
```python
class RangeSliderWidget(QWidget):
    """Double slider pour sélection de plage min/max."""
    
    rangeChanged = pyqtSignal(float, float)
    
    def __init__(self, min_val=0, max_val=100, parent=None):
        pass
    
    def setRange(self, min_val: float, max_val: float):
        pass
    
    def getRange(self) -> Tuple[float, float]:
        pass
```

#### NetworkConfigWidget
```python
class NetworkConfigWidget(QWidget):
    """Widget de configuration réseau réutilisable."""
    
    configChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        pass
    
    def getConfiguration(self) -> dict:
        """Retourne la configuration réseau actuelle."""
        pass
```

#### ResultsTableWidget
```python
class ResultsTableWidget(QTableWidget):
    """Table de résultats avec export et tri."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
    
    def export_to_csv(self, file_path: str):
        pass
    
    def highlight_row(self, row: int):
        pass
```

#### ProgressResultsPanel
```python
class ProgressResultsPanel(QFrame):
    """Panel de résultats avec barre de progression intégrée."""
    
    def __init__(self, parent=None):
        pass
    
    def set_progress(self, value: int, message: str = ""):
        pass
    
    def show_results(self, results: dict):
        pass
    
    def show_error(self, message: str):
        pass
```

### 2. Modification Widgets Existants

#### QgsCheckableComboBoxLayer (Extension)
```python
# Ajouter support filtrage par type (raster/vecteur)
def set_layer_type_filter(self, layer_type: str):
    """Filtre par type: 'vector', 'raster', 'all'."""
    pass
```

---

## 📱 Responsive Design

### Points de Rupture

| Largeur | Mode | Adaptations |
|---------|------|-------------|
| < 400px | Minimal | Icônes seules, sections collapsées par défaut |
| 400-600px | Compact | Labels courts, inputs réduits |
| 600-800px | Normal | Affichage standard |
| > 800px | Étendu | Affichage en colonnes, plus d'infos |

### Comportement Scroll

```python
# Activation scroll si contenu dépasse hauteur disponible
if content_height > available_height:
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
else:
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
```

---

## 🔄 Interactions & Workflows

### Workflow 1: Filtrage Raster Simple

```
1. Utilisateur sélectionne couche raster (MNT)
   → Auto-détection des bandes et métadonnées
   
2. Utilisateur sélectionne couche cible (Clients)
   → Affichage nombre d'entités
   
3. Utilisateur définit plage d'altitude [0-500m]
   → Prévisualisation temps réel
   
4. Clic sur "Échantillonner"
   → Tâche async avec barre de progression
   → Mise à jour attributs couche cible
   
5. Clic sur "Appliquer comme filtre"
   → Expression appliquée à la couche
```

### Workflow 2: Analyse Réseau FTTH

```
1. Utilisateur configure les couches
   - Réseau: Cables_FO
   - BRO: Points_BRO
   - Clients: Clients_FTTH
   
2. Clic sur "Construire Graphe"
   → Progression: Construction du graphe NetworkX
   → Affichage stats (nœuds, arêtes)
   
3. Utilisateur définit contraintes
   - Distance max: 2000m
   - Capacité BRO: 128
   - (optionnel) Pente max via MNT
   
4. Sélection type d'analyse: "Assignation optimale"

5. Clic sur "Analyser"
   → Calcul des affectations optimales
   → Affichage résultats dans tableau
   
6. Clic sur "Appliquer filtre"
   → Clients non-raccordables filtrés
   
7. Clic sur "Export CSV"
   → Rapport de faisabilité généré
```

### Workflow 3: Plus Court Chemin Interactif

```
1. Construction du graphe (si pas déjà fait)

2. Mode sélection carte activé
   → Clic 1: Point départ (surlignage)
   → Clic 2: Point arrivée (surlignage)
   
3. Calcul automatique du chemin
   → Affichage sur carte (ligne temporaire)
   → Stats: distance, nb tronçons, coût
   
4. Option: Exporter comme nouvelle couche
```

---

## ♿ Accessibilité

### Navigation Clavier

```python
# Tab order logique
tab_order = [
    raster_combo,       # 1. Sélection raster
    band_combo,         # 2. Sélection bande
    target_combo,       # 3. Couche cible
    method_radio_group, # 4. Méthode échantillonnage
    output_field,       # 5. Champ sortie
    filter_checkbox,    # 6. Activer filtre
    min_spinbox,        # 7. Valeur min
    max_spinbox,        # 8. Valeur max
    preview_button,     # 9. Prévisualiser
    execute_button,     # 10. Exécuter
    apply_filter_button # 11. Appliquer filtre
]
```

### Attributs ARIA/Qt

```python
# Labels accessibles
raster_combo.setAccessibleName("Sélection de la couche raster")
raster_combo.setAccessibleDescription("Choisissez le fichier raster (MNT, NDVI) à utiliser")

execute_button.setAccessibleName("Exécuter l'échantillonnage")
execute_button.setAccessibleDescription("Lance l'analyse raster sur les entités sélectionnées")
```

### Contrastes

- Ratio minimum: 4.5:1 (WCAG AA)
- Validation automatique via `UIStyles.validate_contrast()`

---

## 🧪 Plan de Tests UI

### Tests Automatisés

```python
# tests/test_raster_ui.py

def test_raster_combo_filters_raster_only():
    """Vérifie que seules les couches raster apparaissent."""
    pass

def test_band_selector_updates_on_raster_change():
    """Vérifie la mise à jour des bandes."""
    pass

def test_range_slider_emits_correct_values():
    """Vérifie les valeurs du slider de plage."""
    pass

def test_results_panel_displays_correctly():
    """Vérifie l'affichage des résultats."""
    pass
```

### Tests Manuels

| # | Scénario | Attendu | Statut |
|---|----------|---------|--------|
| 1 | Ouvrir onglet RASTER | Affichage correct | ☐ |
| 2 | Sélectionner MNT | Bandes peuplées | ☐ |
| 3 | Changer thème QGIS | Couleurs adaptées | ☐ |
| 4 | Redimensionner fenêtre | Layout responsive | ☐ |
| 5 | Navigation clavier | Tab order correct | ☐ |
| 6 | Exécuter analyse | Progression visible | ☐ |
| 7 | Annuler analyse | Arrêt propre | ☐ |
| 8 | Afficher résultats | Tableau correct | ☐ |
| 9 | Exporter CSV | Fichier valide | ☐ |
| 10 | Mode compact | Adaptation OK | ☐ |

---

## 📅 Planning Implémentation UI

### Phase 1: Fondations (Semaine 1-2)

- [ ] Créer structure onglets dans dockwidget
- [ ] Implémenter `RasterLayerComboBox`
- [ ] Implémenter `BandSelectorComboBox`
- [ ] Créer layout de base onglet RASTER

### Phase 2: Widgets Avancés (Semaine 3-4)

- [ ] Implémenter `RangeSliderWidget`
- [ ] Implémenter `ProgressResultsPanel`
- [ ] Créer layout onglet NETWORK
- [ ] Implémenter `NetworkConfigWidget`

### Phase 3: Intégration (Semaine 5-6)

- [ ] Connexion signaux/slots avec backends
- [ ] Implémentation responsive design
- [ ] Tests accessibilité
- [ ] Documentation utilisateur

### Phase 4: Polissage (Semaine 7)

- [ ] Tests complets
- [ ] Ajustements visuels
- [ ] Optimisation performance UI
- [ ] Traductions i18n

---

## 📎 Annexes

### A. Fichiers à Créer

```
modules/
├── ui/
│   ├── __init__.py
│   ├── raster_tab.py          # UI onglet RASTER
│   ├── network_tab.py         # UI onglet NETWORK
│   ├── raster_widgets.py      # Widgets spécifiques raster
│   ├── network_widgets.py     # Widgets spécifiques réseau
│   └── results_widgets.py     # Widgets résultats communs
```

### B. Fichiers à Modifier

```
filter_mate_dockwidget.py      # Ajout onglets
filter_mate_dockwidget_base.ui # Layout de base
modules/ui_config.py           # Nouvelles dimensions
modules/ui_styles.py           # Styles nouveaux widgets
```

### C. Ressources Graphiques

```
icons/
├── raster/
│   ├── mnt.svg
│   ├── ndvi.svg
│   ├── sample.svg
│   └── elevation.svg
└── network/
    ├── graph.svg
    ├── path.svg
    ├── isochrone.svg
    └── cable.svg
```

---

*Document de proposition - Soumis pour validation*

**Prochaine étape:** Validation par l'équipe et début implémentation Phase 1
