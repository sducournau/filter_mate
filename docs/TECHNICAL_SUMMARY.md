# FilterMate - Documentation Technique et Résumé d'Architecture

**Version**: 4.3.10 | **Date**: Janvier 2026 | **Statut**: Production

---

## 📋 Résumé Exécutif

**FilterMate** est un plugin QGIS de filtrage spatial avancé permettant l'exploration, le filtrage et l'export de données vectorielles avec des performances optimales sur toutes les sources de données.

### Caractéristiques Clés

| Caractéristique | Description |
|-----------------|-------------|
| **Type** | Plugin QGIS (Python 3.7+) |
| **Architecture** | Hexagonale (Ports & Adapters) |
| **Backends** | PostgreSQL, Spatialite, OGR, Memory |
| **Langues** | 21 langues supportées |
| **Thèmes** | Dark Mode automatique |
| **Score Qualité** | 9.0/10 |

---

## 🏗️ Architecture Hexagonale

FilterMate utilise une **architecture hexagonale** (aussi appelée Ports & Adapters) qui sépare clairement:

```
                    ╔═══════════════════════════════╗
                    ║      MONDE EXTERNE            ║
                    ║  (QGIS, PostgreSQL, User)     ║
                    ╚═══════════════════════════════╝
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
          ┌───────▼──────┐ ┌──────▼──────┐ ┌────▼─────┐
          │   UI Layer   │ │   Adapters  │ │ Infrastr.│
          │ (Controllers)│ │  (QGIS,DB)  │ │ (Logging)│
          └──────┬───────┘ └──────┬──────┘ └────┬─────┘
                 │                │              │
                 └────────┬───────┴──────────────┘
                          │
                  ┌───────▼────────┐
                  │     PORTS      │
                  │  (Interfaces)  │
                  └───────┬────────┘
                          │
                  ┌───────▼────────┐
                  │   CORE DOMAIN  │
                  │  (Logique      │
                  │   Métier)      │
                  └────────────────┘
```

### Avantages

- ✅ **Testabilité** - Logique métier testable sans QGIS
- ✅ **Maintenabilité** - Séparation claire des responsabilités
- ✅ **Flexibilité** - Ajout facile de nouveaux backends
- ✅ **Focus Domaine** - Logique métier isolée des détails techniques

---

## 📁 Structure des Répertoires

```
filter_mate/
├── filter_mate.py              # 🚀 Point d'entrée du plugin
├── filter_mate_app.py          # 🎯 Orchestrateur principal (2,237 lignes)
├── filter_mate_dockwidget.py   # 🖥️ Widget UI principal
│
├── core/                       # ⚪ COUCHE DOMAINE (Logique Métier)
│   ├── domain/                 # Objets valeur, entités
│   │   ├── filter_expression.py
│   │   ├── filter_result.py
│   │   ├── layer_info.py
│   │   └── optimization_config.py
│   ├── services/               # 27 services domaine
│   │   ├── filter_service.py       # Orchestration filtrage
│   │   ├── layer_service.py        # Gestion des couches
│   │   ├── expression_service.py   # Validation expressions
│   │   ├── history_service.py      # Undo/Redo
│   │   ├── favorites_service.py    # Favoris de filtre
│   │   └── ... (22 autres services)
│   ├── tasks/                  # Opérations asynchrones (QgsTask)
│   │   ├── filter_task.py          # Tâche de filtrage principale (4,820 lignes)
│   │   └── layer_management_task.py
│   ├── filter/                 # Logique de filtre
│   ├── geometry/               # Opérations géométriques
│   ├── export/                 # Logique d'export
│   ├── optimization/           # Optimisation des requêtes
│   ├── strategies/             # Implémentations Strategy pattern
│   └── ports/                  # 🔌 INTERFACES (abstractions)
│       ├── backend_port.py         # Interface backends
│       ├── repository_port.py      # Interface accès données
│       └── qgis_port.py            # Abstractions QGIS
│
├── adapters/                   # 🔌 COUCHE ADAPTERS (Systèmes Externes)
│   ├── backends/               # Système multi-backend
│   │   ├── postgresql/             # PostgreSQL/PostGIS
│   │   │   ├── filter_executor.py
│   │   │   ├── schema_manager.py
│   │   │   └── query_builder.py
│   │   ├── spatialite/             # Spatialite
│   │   │   ├── filter_executor.py
│   │   │   ├── spatial_index.py
│   │   │   └── cache_db.py
│   │   ├── ogr/                    # OGR (fallback universel)
│   │   │   └── filter_executor.py
│   │   ├── memory/                 # Couches mémoire
│   │   │   └── filter_executor.py
│   │   ├── factory.py              # Sélection automatique
│   │   └── postgresql_availability.py
│   ├── qgis/                   # Adapteurs QGIS
│   ├── repositories/           # Pattern Repository
│   ├── task_bridge.py          # Coordination des tâches
│   └── legacy_adapter.py       # Compatibilité v2.x
│
├── infrastructure/             # ⚙️ COUCHE INFRASTRUCTURE (Technique)
│   ├── logging/                # Configuration logging
│   ├── cache/                  # Cache requêtes/géométries
│   ├── database/               # Connexions, pools
│   ├── di/                     # Injection de dépendances
│   ├── state/                  # Gestion d'état
│   ├── feedback/               # Feedback utilisateur
│   ├── parallel/               # Exécution parallèle
│   └── streaming/              # Export streaming
│
├── ui/                         # 🎨 COUCHE UI (Présentation)
│   ├── controllers/            # Contrôleurs MVC (13 contrôleurs)
│   │   ├── integration.py          # Orchestration principale
│   │   ├── exploring_controller.py # Explorateur de features
│   │   ├── filtering_controller.py # Opérations de filtrage
│   │   ├── layer_sync_controller.py
│   │   └── ... (9 autres)
│   ├── widgets/                # Widgets personnalisés
│   ├── dialogs/                # Fenêtres de dialogue
│   ├── styles/                 # Thèmes et styles
│   └── layout/                 # Gestionnaires de layout
│
├── config/                     # ⚙️ CONFIGURATION
│   ├── config.py               # Configuration v2.0
│   ├── config.default.json     # Valeurs par défaut
│   └── theme_helpers.py
│
└── i18n/                       # 🌍 TRADUCTIONS (21 langues)
```

---

## 🔧 Système Multi-Backend

FilterMate supporte **4 systèmes backend** pour des performances optimales:

### 1. PostgreSQL Backend

| Aspect | Détail |
|--------|--------|
| **Idéal pour** | Grands datasets (>100k features) |
| **Fonctionnalités** | Vues matérialisées, index GiST, traitement serveur |
| **Dépendance** | `psycopg2` (optionnel) |
| **Performance** | <2s pour 100k features |

### 2. Spatialite Backend

| Aspect | Détail |
|--------|--------|
| **Idéal pour** | Datasets moyens (<100k features), travail hors-ligne |
| **Fonctionnalités** | Index R-tree, tables temporaires |
| **Dépendance** | Intégré (mod_spatialite) |
| **Performance** | ~10s pour 100k features |

### 3. OGR Backend

| Aspect | Détail |
|--------|--------|
| **Idéal pour** | Shapefiles, GeoPackage, formats fichier |
| **Fonctionnalités** | Fallback universel, tous formats OGR |
| **Dépendance** | Aucune |
| **Performance** | ~30s pour 100k features |

### 4. Memory Backend

| Aspect | Détail |
|--------|--------|
| **Idéal pour** | Petits datasets (<10k features), couches temporaires |
| **Fonctionnalités** | Filtrage en mémoire, rapidité |
| **Dépendance** | Aucune |
| **Performance** | <1s pour 10k features |

### Tableau de Performance Comparatif

| Backend | 10k Features | 100k Features | 1M Features |
|---------|:------------:|:-------------:|:-----------:|
| **PostgreSQL** | <1s | <2s | ~10s |
| **Spatialite** | <2s | ~10s | ~60s |
| **OGR** | ~5s | ~30s | >120s |
| **Memory** | <0.5s | ⚠️ | ❌ |

### Algorithme de Sélection

```python
def select_backend(layer):
    provider = layer.provider_type()
    feature_count = layer.feature_count()
    
    if provider == 'postgres' and POSTGRESQL_AVAILABLE:
        return BackendType.POSTGRESQL
    elif provider == 'spatialite':
        return BackendType.SPATIALITE
    elif provider == 'ogr':
        return BackendType.OGR
    elif feature_count < 10000:
        return BackendType.MEMORY
    else:
        return BackendType.SPATIALITE if feature_count < 100000 else BackendType.MEMORY
```

---

## 🎯 Fonctionnalités Principales

### 1. Recherche Intelligente
- Recherche d'entités sur tous les types de couches
- Auto-complétion et suggestions
- Filtrage par attributs

### 2. Filtrage Géométrique
- Prédicats spatiaux (intersection, containment, buffer...)
- Support des buffers négatifs
- Optimisation automatique des géométries

### 3. Favoris de Filtres
- Sauvegarde des configurations de filtres
- Organisation par catégories
- Partage entre projets

### 4. Historique Undo/Redo
- Annulation/rétablissement complet
- Restauration contextuelle
- Historique persistant par session

### 5. Export GeoPackage
- Export avec styles
- Streaming pour grands datasets
- Compression automatique

---

## 📊 Design Patterns Utilisés

### 1. Ports & Adapters (Hexagonal)
Séparation domaine/infrastructure via interfaces abstraites.

### 2. Repository Pattern
Centralisation de l'accès aux données.

### 3. Strategy Pattern
Algorithmes de filtrage interchangeables par backend.

### 4. Factory Pattern
Création automatique du backend approprié.

### 5. Dependency Injection
Injection des dépendances pour testabilité.

### 6. Strangler Fig Pattern
Migration progressive du code legacy.

### 7. Circuit Breaker Pattern
Fallback automatique en cas d'échec PostgreSQL.

---

## 📝 Guide d'Utilisation Rapide

### Installation

#### Depuis le dépôt QGIS
```
QGIS → Plugins → Manage and Install Plugins → Rechercher "FilterMate" → Installer
```

#### Installation manuelle
1. Télécharger depuis [GitHub Releases](https://github.com/sducournau/filter_mate/releases)
2. Extraire dans le répertoire plugins QGIS:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

#### Support PostgreSQL (optionnel)
```bash
pip install psycopg2-binary
```

### Utilisation de Base

1. **Activer FilterMate**: `Plugins` → `FilterMate` → `Show Panel`
2. **Sélectionner une couche source**: Dans le panneau FilterMate
3. **Choisir les couches cibles**: Cocher les couches à filtrer
4. **Définir le filtre**: Attribut, géométrie, ou combinaison
5. **Appliquer**: Cliquer sur le bouton "Filter"

### Workflow Typique

```
┌─────────────────────────────────────────────────────┐
│  1. Sélection Couche Source                         │
│     ↓                                               │
│  2. Sélection Entités (par clic, rectangle, outil) │
│     ↓                                               │
│  3. Configuration Filtre Géométrique (optionnel)    │
│     - Prédicat: Intersects, Contains, Within...     │
│     - Buffer: 0, 100m, 500m, -100m...              │
│     ↓                                               │
│  4. Sélection Couches Cibles                        │
│     ↓                                               │
│  5. Application du Filtre                           │
│     ↓                                               │
│  6. Résultat: Couches filtrées sur le canevas      │
│     ↓                                               │
│  7. Export (optionnel): GeoPackage avec styles      │
└─────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### Fichier de Configuration

Emplacement: `{QGIS_SETTINGS}/FilterMate/config.json`

### Options Principales

```json
{
  "_CONFIG_VERSION": "2.0",
  "app": {
    "auto_activate": false,
    "ui": {
      "language": "auto",
      "theme": "auto",
      "feedback_level": "normal"
    }
  },
  "postgresql": {
    "filter": {
      "materialized_view": true,
      "use_gist_index": true
    }
  },
  "optimization": {
    "auto_simplify_after_buffer": true,
    "buffer_simplify_tolerance": 0.5,
    "cache_max_age": 300
  }
}
```

### Variables d'Environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `FILTERMATE_DEBUG` | Active le mode debug | `false` |
| `FILTERMATE_LOG_LEVEL` | Niveau de log | `INFO` |
| `FILTERMATE_CACHE_DIR` | Répertoire de cache | Auto |

---

## 🔍 Indicateurs Backend

| Indicateur | Signification |
|:----------:|---------------|
| 🟢 **PostgreSQL** | Backend optimal actif |
| 🔵 **Spatialite** | Backend intermédiaire actif |
| 🟠 **OGR** | Fallback universel actif |
| 🔴 **Unavailable** | Aucun backend disponible |

---

## 📈 Métriques Clés (v4.0.3)

| Métrique | Valeur |
|----------|--------|
| **Total Code** | ~120,000 lignes |
| **Core (Domaine)** | 39,708 lignes (33%) |
| **Adapters** | 23,272 lignes (19%) |
| **Infrastructure** | 11,694 lignes (10%) |
| **UI** | 27,727 lignes (23%) |
| **Services** | 27 |
| **Contrôleurs UI** | 13 |
| **Couverture Tests** | ~68% |

---

## 🔗 Ressources

| Ressource | Lien |
|-----------|------|
| **Documentation Web** | https://sducournau.github.io/filter_mate |
| **GitHub** | https://github.com/sducournau/filter_mate |
| **Plugin QGIS** | https://plugins.qgis.org/plugins/filter_mate |
| **Issues** | https://github.com/sducournau/filter_mate/issues |

---

## 📜 Licence

GNU General Public License v3.0

---

**Développé par**: imagodata  
**Contact**: simon.ducournau+filter_mate@gmail.com
