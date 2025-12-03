# FilterMate - Plan d'Implémentation Détaillé

## 📋 Vue d'ensemble

Ce document détaille les tâches d'implémentation concrètes, avec estimation de temps, dépendances et critères d'acceptation.

**Date de création**: 3 décembre 2025  
**Version cible**: 2.0.0  
**Durée estimée totale**: 10-12 semaines

---

## 🔥 Sprint 1: Corrections Critiques (Semaine 1-2)

### Tâche 1.1: Amélioration de la Gestion des Erreurs
**Priorité**: 🔴 Critique  
**Estimation**: 3 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire

**Description**:
Remplacer tous les `except: pass` par du logging approprié pour améliorer la traçabilité.

**Fichiers à modifier**:
- `config/config.py` (ligne 67)
- `modules/appTasks.py` (lignes 2076, 2081)

**Implémentation**:
```python
# Avant:
try:
    os.makedirs(PLUGIN_CONFIG_DIRECTORY, exist_ok=True)
except OSError as error:
    pass

# Après:
try:
    os.makedirs(PLUGIN_CONFIG_DIRECTORY, exist_ok=True)
except OSError as error:
    logger.warning(f"Could not create config directory {PLUGIN_CONFIG_DIRECTORY}: {error}")
```

**Critères d'acceptation**:
- [ ] Aucun `except: pass` restant dans le code
- [ ] Tous les messages d'erreur sont loggés
- [ ] Tests de régression passent

**Tests**:
```python
def test_config_directory_creation_error(tmp_path, caplog):
    """Test that directory creation errors are logged"""
    with mock.patch('os.makedirs', side_effect=OSError("Permission denied")):
        # Execute code
        assert "Could not create config directory" in caplog.text
```

---

### Tâche 1.2: Système de Logging Amélioré
**Priorité**: 🔴 Critique  
**Estimation**: 4 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire  
**Dépend de**: Tâche 1.1

**Description**:
Implémenter un système de logging robuste avec rotation et niveaux appropriés.

**Fichiers à créer/modifier**:
- Nouveau: `modules/logging_config.py`
- Modifier: `modules/appUtils.py`, `modules/appTasks.py`, `filter_mate_app.py`

**Implémentation**:
```python
# modules/logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name, log_file, level=logging.INFO):
    """Setup logger with rotation"""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger

# Usage dans appUtils.py
from modules.logging_config import setup_logger

logger = setup_logger(
    'FilterMate.Utils',
    os.path.join(ENV_VARS["PATH_ABSOLUTE_PROJECT"], 'logs', 'filtermate.log')
)
```

**Critères d'acceptation**:
- [ ] Logs avec rotation (max 10 MB, 5 backups)
- [ ] Format standardisé avec timestamps
- [ ] Niveaux appropriés (DEBUG, INFO, WARNING, ERROR)
- [ ] Configuration centralisée

---

### Tâche 1.3: Messages de Feedback Utilisateur
**Priorité**: 🟠 Haute  
**Estimation**: 5 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire

**Description**:
Ajouter indicateurs visuels et messages de progression pour améliorer l'UX.

**Fichiers à modifier**:
- `filter_mate_dockwidget.py`
- `filter_mate_app.py`
- `modules/appTasks.py`

**Implémentation**:

**1. Indicateur de backend (2h)**:
```python
# Dans filter_mate_dockwidget.py, ajouter un QLabel
def _update_backend_indicator(self, provider_type):
    """Update backend indicator in UI"""
    backend_icons = {
        'postgresql': '⚡',
        'spatialite': '💾',
        'ogr': '📁',
        'memory': '🧠'
    }
    backend_names = {
        'postgresql': 'PostgreSQL (Optimized)',
        'spatialite': 'Spatialite',
        'ogr': 'OGR Provider',
        'memory': 'Memory'
    }
    
    icon = backend_icons.get(provider_type, '❓')
    name = backend_names.get(provider_type, 'Unknown')
    
    self.label_backend.setText(f"Backend: {icon} {name}")
    
    # Color coding
    if provider_type == 'postgresql':
        self.label_backend.setStyleSheet("color: green; font-weight: bold;")
    elif provider_type == 'spatialite':
        self.label_backend.setStyleSheet("color: blue;")
    else:
        self.label_backend.setStyleSheet("color: orange;")
```

**2. Avertissements de performance (1h)**:
```python
# Dans FilterEngineTask.run()
def _check_performance_warnings(self):
    """Check and warn about performance issues"""
    layer_count = self.source_layer.featureCount()
    provider = self.param_source_provider_type
    
    if layer_count > 50000 and provider == 'spatialite':
        iface.messageBar().pushWarning(
            "FilterMate - Performance",
            f"Large dataset ({layer_count:,} features) on Spatialite. "
            "Consider using PostgreSQL for better performance.",
            duration=10
        )
    
    if layer_count > 100000 and provider == 'ogr':
        iface.messageBar().pushWarning(
            "FilterMate - Performance",
            f"Very large dataset ({layer_count:,} features) on OGR provider. "
            "This operation may take several minutes.",
            duration=15
        )
```

**3. Barre de progression (2h)**:
```python
# Dans FilterEngineTask
def run(self):
    total_steps = len(self.layers) + 3  # +3 for init, prepare, finalize
    current_step = 0
    
    def update_progress(message):
        nonlocal current_step
        current_step += 1
        progress = int((current_step / total_steps) * 100)
        self.setProgress(progress)
        logger.info(f"[{progress}%] {message}")
    
    update_progress("Initializing filter engine...")
    # ... rest of the code
    
    for layer in self.layers:
        update_progress(f"Filtering layer: {layer.name()}")
        # ... filtering logic
    
    update_progress("Finalizing...")
```

**Critères d'acceptation**:
- [ ] Indicateur de backend visible dans l'UI
- [ ] Avertissements pour datasets >50k features
- [ ] Barre de progression pour opérations longues
- [ ] Messages informatifs à chaque étape

---

### Tâche 1.4: Cache d'Icônes
**Priorité**: 🟠 Haute  
**Estimation**: 2 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire

**Description**:
Implémenter un cache statique pour éviter recalculs répétés des icônes.

**Fichiers à modifier**:
- `filter_mate_dockwidget.py` (méthode `icon_per_geometry_type`)

**Implémentation**:
```python
from functools import lru_cache

class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    # Cache statique de classe
    _icon_cache = {}
    
    @classmethod
    def get_geometry_icon(cls, geometry_type):
        """Get cached icon for geometry type"""
        if geometry_type not in cls._icon_cache:
            if geometry_type == 'GeometryType.Line':
                cls._icon_cache[geometry_type] = QgsLayerItem.iconLine()
            elif geometry_type == 'GeometryType.Point':
                cls._icon_cache[geometry_type] = QgsLayerItem.iconPoint()
            elif geometry_type == 'GeometryType.Polygon':
                cls._icon_cache[geometry_type] = QgsLayerItem.iconPolygon()
            elif geometry_type == 'GeometryType.Table':
                cls._icon_cache[geometry_type] = QgsLayerItem.iconTable()
            else:
                cls._icon_cache[geometry_type] = QgsLayerItem.iconDefault()
        
        return cls._icon_cache[geometry_type]
    
    def icon_per_geometry_type(self, geometry_type):
        """Wrapper for backward compatibility"""
        return self.get_geometry_icon(geometry_type)
```

**Benchmark attendu**:
- Avant: ~0.5ms par appel (recalcul à chaque fois)
- Après: ~0.01ms par appel (lookup dictionnaire)
- Gain: 50x sur affichage de 100 couches

**Critères d'acceptation**:
- [ ] Cache implémenté et fonctionnel
- [ ] Tests de performance montrent amélioration
- [ ] Aucune régression fonctionnelle

---

### Tâche 1.5: Infrastructure de Tests
**Priorité**: 🟠 Haute  
**Estimation**: 8 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire

**Description**:
Mettre en place l'infrastructure de tests unitaires avec pytest.

**Fichiers à créer**:
```
tests/
├── __init__.py
├── conftest.py           # Fixtures pytest
├── test_appUtils.py
├── test_geometry.py
├── test_providers.py
└── fixtures/
    ├── sample_layers.py
    └── mock_qgis.py
```

**Implémentation**:

**1. Configuration pytest (1h)**:
```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, MagicMock
from qgis.core import QgsVectorLayer, QgsProject

@pytest.fixture
def mock_qgis_iface():
    """Mock QGIS interface"""
    iface = Mock()
    iface.messageBar.return_value = Mock()
    return iface

@pytest.fixture
def sample_point_layer():
    """Create a sample point layer for testing"""
    layer = QgsVectorLayer("Point?crs=epsg:4326", "test_points", "memory")
    # Add features...
    return layer

@pytest.fixture
def mock_postgresql_connection():
    """Mock PostgreSQL connection"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor
```

**2. Tests pour appUtils (3h)**:
```python
# tests/test_appUtils.py
import pytest
from modules.appUtils import (
    geometry_type_to_string,
    detect_layer_provider_type,
    get_datasource_connexion_from_layer
)
from qgis.core import QgsWkbTypes

class TestGeometryTypeConversion:
    def test_point_geometry(self):
        result = geometry_type_to_string(QgsWkbTypes.PointGeometry)
        assert result == "GeometryType.Point"
    
    def test_line_geometry(self):
        result = geometry_type_to_string(QgsWkbTypes.LineGeometry)
        assert result == "GeometryType.Line"
    
    def test_polygon_geometry(self):
        result = geometry_type_to_string(QgsWkbTypes.PolygonGeometry)
        assert result == "GeometryType.Polygon"
    
    def test_unknown_geometry(self):
        result = geometry_type_to_string(QgsWkbTypes.UnknownGeometry)
        assert result == "GeometryType.UnknownGeometry"

class TestProviderDetection:
    def test_postgresql_provider(self, sample_pg_layer):
        result = detect_layer_provider_type(sample_pg_layer)
        assert result == "postgresql"
    
    def test_spatialite_provider(self, sample_spatialite_layer):
        result = detect_layer_provider_type(sample_spatialite_layer)
        assert result == "spatialite"
    
    def test_ogr_shapefile_provider(self, sample_shapefile_layer):
        result = detect_layer_provider_type(sample_shapefile_layer)
        assert result == "ogr"
```

**3. Tests pour expressions (2h)**:
```python
# tests/test_expressions.py
class TestQGISExpressionConversion:
    def test_simple_postgis_conversion(self):
        task = FilterEngineTask(...)
        expression = '"population" > 1000'
        result = task.qgis_expression_to_postgis(expression)
        assert '"population"' in result
        assert '> 1000' in result
    
    def test_spatial_predicate_conversion(self):
        task = FilterEngineTask(...)
        expression = 'ST_Intersects($geometry, geom_ref)'
        result = task.qgis_expression_to_postgis(expression)
        assert 'ST_Intersects' in result
```

**4. Configuration CI/CD (2h)**:
```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install QGIS
      run: |
        sudo apt-get update
        sudo apt-get install -y qgis python3-qgis
    
    - name: Install dependencies
      run: |
        pip install pytest pytest-cov pytest-mock
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tests/ --cov=modules --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

**Critères d'acceptation**:
- [ ] pytest configuré et fonctionnel
- [ ] Au moins 20 tests unitaires
- [ ] Coverage >30% sur modules/appUtils.py
- [ ] CI/CD GitHub Actions configuré
- [ ] Tests passent sur Python 3.8-3.11

**Durée Sprint 1**: 22 heures (~3 jours de travail)

---

## 🔧 Sprint 2: Refactoring (Semaine 3-6)

### Tâche 2.1: Décomposition de execute_geometric_filtering
**Priorité**: 🟠 Haute  
**Estimation**: 20 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire  
**Dépend de**: Sprint 1 terminé

**Description**:
Refactoriser la méthode monolithique de 395 lignes en méthodes spécialisées.

**Plan de refactoring**:

**Étape 1: Extraction méthodes PostgreSQL (6h)**
```python
# Extraire dans modules/backends/postgresql_backend.py
class PostgreSQLGeometricFilter:
    def __init__(self, task_params):
        self.params = task_params
    
    def build_postgis_expression(self, layer_props, predicates):
        """Build PostGIS spatial query expression"""
        # Code actuel lignes 1008-1300
        pass
    
    def apply_filter(self, layer, expression):
        """Apply filter to PostgreSQL layer"""
        # Code actuel lignes 1300-1380
        pass
```

**Étape 2: Extraction méthodes Spatialite (4h)**
```python
# modules/backends/spatialite_backend.py
class SpatialiteGeometricFilter:
    def build_spatialite_expression(self, layer_props, predicates):
        """Build Spatialite spatial query expression"""
        pass
    
    def apply_filter(self, layer, expression):
        """Apply filter to Spatialite layer"""
        pass
```

**Étape 3: Extraction méthodes OGR (4h)**
```python
# modules/backends/ogr_backend.py
class OGRGeometricFilter:
    def execute_qgis_processing(self, layer, source_geom, predicates):
        """Use QGIS processing for OGR layers"""
        # Code actuel lignes 1340-1400
        pass
```

**Étape 4: Interface commune (3h)**
```python
# modules/backends/base_backend.py
from abc import ABC, abstractmethod

class GeometricFilterBackend(ABC):
    @abstractmethod
    def build_expression(self, layer_props, predicates):
        """Build filter expression for this backend"""
        pass
    
    @abstractmethod
    def apply_filter(self, layer, expression):
        """Apply filter to layer"""
        pass
    
    @abstractmethod
    def supports_layer(self, layer):
        """Check if this backend supports the layer"""
        pass
```

**Étape 5: Intégration (3h)**
```python
# Nouvelle version de execute_geometric_filtering (< 50 lignes)
def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
    """Execute geometric filtering using appropriate backend"""
    # Factory pattern
    backend = self._get_backend(layer_provider_type)
    
    if not backend.supports_layer(layer):
        logger.warning(f"Backend {backend.__class__.__name__} doesn't support layer")
        backend = OGRGeometricFilter()  # Fallback
    
    # Verify spatial index
    self._verify_and_create_spatial_index(layer, layer_props.get('infos', {}).get('layer_name'))
    
    # Build expression
    expression = backend.build_expression(layer_props, self.current_predicates)
    
    # Apply filter
    result = backend.apply_filter(layer, expression)
    
    if result:
        self.manage_layer_subset_strings(layer, expression, ...)
    
    return result

def _get_backend(self, provider_type):
    """Factory method for backend selection"""
    backends = {
        'postgresql': PostgreSQLGeometricFilter,
        'spatialite': SpatialiteGeometricFilter,
        'ogr': OGRGeometricFilter
    }
    backend_class = backends.get(provider_type, OGRGeometricFilter)
    return backend_class(self.task_parameters)
```

**Tests**:
```python
# tests/test_backends.py
class TestPostgreSQLBackend:
    def test_expression_building(self):
        backend = PostgreSQLGeometricFilter(params)
        expr = backend.build_expression(layer_props, predicates)
        assert 'ST_Intersects' in expr
    
    def test_filter_application(self):
        backend = PostgreSQLGeometricFilter(params)
        result = backend.apply_filter(mock_layer, "test_expr")
        assert result is True

class TestBackendSelection:
    def test_postgresql_layer_uses_postgresql_backend(self):
        task = FilterEngineTask(...)
        backend = task._get_backend('postgresql')
        assert isinstance(backend, PostgreSQLGeometricFilter)
```

**Critères d'acceptation**:
- [ ] Code refactorisé en <50 lignes par méthode
- [ ] Complexité cyclomatique <10
- [ ] Tests unitaires pour chaque backend
- [ ] Aucune régression fonctionnelle
- [ ] Documentation des nouvelles classes

---

### Tâche 2.2: Externalisation Styles CSS
**Priorité**: 🟡 Moyenne  
**Estimation**: 6 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire

**Description**:
Extraire les 527 lignes de styles inline dans un fichier QSS externe.

**Fichiers à créer**:
```
resources/
├── styles/
│   ├── light.qss
│   ├── dark.qss
│   └── default.qss
```

**Implémentation**:

**1. Créer fichier de styles (3h)**:
```css
/* resources/styles/default.qss */
/* Exploring Tab */
QGroupBox#groupBoxExploring {
    border: 2px solid #3daee9;
    border-radius: 5px;
    margin-top: 1ex;
    font-weight: bold;
}

QGroupBox#groupBoxExploring::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #3daee9;
}

/* Filtering Tab */
QGroupBox#groupBoxFiltering {
    border: 2px solid #27ae60;
    border-radius: 5px;
    margin-top: 1ex;
}

/* ... reste des styles */
```

**2. Loader de styles (2h)**:
```python
# modules/ui_styles.py
import os
from PyQt5.QtCore import QFile, QTextStream

class StyleLoader:
    _current_theme = 'default'
    _styles_cache = {}
    
    @classmethod
    def load_stylesheet(cls, theme='default'):
        """Load QSS stylesheet from file"""
        if theme in cls._styles_cache:
            return cls._styles_cache[theme]
        
        style_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'resources',
            'styles',
            f'{theme}.qss'
        )
        
        if not os.path.exists(style_file):
            logger.warning(f"Style file not found: {style_file}")
            theme = 'default'
            style_file = style_file.replace(theme, 'default')
        
        file = QFile(style_file)
        if file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(file)
            stylesheet = stream.readAll()
            cls._styles_cache[theme] = stylesheet
            cls._current_theme = theme
            return stylesheet
        
        return ""
    
    @classmethod
    def set_theme(cls, widget, theme='default'):
        """Apply theme to widget"""
        stylesheet = cls.load_stylesheet(theme)
        widget.setStyleSheet(stylesheet)
```

**3. Intégration (1h)**:
```python
# filter_mate_dockwidget.py
from modules.ui_styles import StyleLoader

class FilterMateDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    def manage_ui_style(self):
        """Apply UI styles from external stylesheet"""
        # Remplacer les 527 lignes par:
        StyleLoader.set_theme(self, 'default')
        
        # Options de thème dans le menu
        theme_menu = self.menuBar().addMenu("Theme")
        theme_menu.addAction("Light", lambda: StyleLoader.set_theme(self, 'light'))
        theme_menu.addAction("Dark", lambda: StyleLoader.set_theme(self, 'dark'))
```

**Critères d'acceptation**:
- [ ] Styles externalisés dans fichiers QSS
- [ ] Méthode `manage_ui_style()` réduite à <20 lignes
- [ ] Support thèmes clair/sombre
- [ ] Aucune différence visuelle vs version précédente

---

### Tâche 2.3: Pattern Strategy pour Backends
**Priorité**: 🟡 Moyenne  
**Estimation**: 16 heures  
**Assigné**: TBD  
**Status**: 🟡 À faire  
**Dépend de**: Tâche 2.1

**Description**:
Implémenter le pattern Strategy pour une architecture extensible des backends.

**Structure proposée**:
```
modules/
└── backends/
    ├── __init__.py
    ├── base_backend.py        # Interface abstraite
    ├── postgresql_backend.py
    ├── spatialite_backend.py
    ├── ogr_backend.py
    └── factory.py             # Backend factory
```

**Implémentation détaillée dans ROADMAP.md**

**Durée Sprint 2**: 42 heures (~1 semaine)

---

## 🚀 Sprint 3: Fonctionnalités (Semaine 7-12)

### Tâche 3.1: Historique et Undo/Redo
**Estimation**: 20 heures

### Tâche 3.2: Favoris de Filtres
**Estimation**: 16 heures

### Tâche 3.3: Mode Batch
**Estimation**: 20 heures

### Tâche 3.4: Statistiques Post-Filtrage
**Estimation**: 12 heures

### Tâche 3.5: Prévisualisation Spatiale
**Estimation**: 16 heures

**Durée Sprint 3**: 84 heures (~2 semaines)

---

## 📚 Parallèle: Documentation

### Tâche DOC.1: Setup Docusaurus
**Estimation**: 8 heures

### Tâche DOC.2: Contenu Utilisateur
**Estimation**: 40 heures

### Tâche DOC.3: Documentation API
**Estimation**: 24 heures

**Durée Documentation**: 72 heures (~1.5 semaines, en parallèle)

---

## 📊 Récapitulatif Global

| Sprint | Durée | Tâches | Heures | Livrables |
|--------|-------|--------|--------|-----------|
| Sprint 1 | Sem 1-2 | 5 | 22h | v1.9.1 Corrections |
| Sprint 2 | Sem 3-6 | 3 | 42h | v1.10.0 Refactoring |
| Sprint 3 | Sem 7-12 | 5 | 84h | v2.0.0 Features |
| Docs | Parallèle | 3 | 72h | Documentation complète |
| **TOTAL** | **12 sem** | **16** | **220h** | **v2.0.0 + Docs** |

---

## 🎯 Définition de "Done"

Une tâche est considérée terminée quand:
- [ ] Code implémenté et testé
- [ ] Tests unitaires écrits et passants
- [ ] Coverage ≥ 80% sur le nouveau code
- [ ] Documentation API mise à jour
- [ ] Code review effectué
- [ ] Tests d'intégration passants
- [ ] Pas de régression détectée
- [ ] Changelog mis à jour

---

## 📝 Notes d'Implémentation

### Conventions de Code
- PEP 8 strictement respecté
- Type hints pour toutes les fonctions publiques
- Docstrings Google style
- Maximum 120 caractères par ligne

### Git Workflow
```bash
# Créer branche de feature
git checkout -b feature/logging-improvements

# Commits atomiques
git commit -m "feat: add rotating file handler for logs"
git commit -m "test: add tests for logging configuration"

# Squash si nécessaire avant merge
git rebase -i main
```

### Revue de Code
- Minimum 1 reviewer
- Tests automatiques passants requis
- Pas de merge si coverage baisse

---

**Document vivant - Mis à jour régulièrement**  
**Dernière mise à jour**: 3 décembre 2025
