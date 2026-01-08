# FilterMate - Development Guide

> **Version**: 3.0.0 | **Updated**: January 2026

Guide complet pour développeurs souhaitant contribuer à FilterMate ou comprendre son fonctionnement interne.

## 🆕 What's New in v3.0

FilterMate v3.0 introduces a **complete architectural refactoring**:

- **Hexagonal Architecture**: Clean separation between core domain and adapters
- **Dependency Injection**: All services receive their dependencies
- **High Testability**: 90%+ code coverage enabled
- **Smaller Files**: Maximum 800 lines per file (down from 12,944)

See [Architecture v3.0](architecture-v3.md) for details.

## 🎯 Prérequis

### Système

| Composant  | Version Minimale        | Recommandé                 |
| ---------- | ----------------------- | -------------------------- |
| **Python** | 3.7                     | 3.9+                       |
| **QGIS**   | 3.0                     | 3.22+                      |
| **OS**     | Windows 7, Linux, macOS | Windows 10+, Ubuntu 20.04+ |

### Dépendances Python

#### Obligatoires (via QGIS)

```python
# Inclus avec QGIS
qgis.core
qgis.gui
qgis.utils
PyQt5
osgeo (GDAL/OGR)
```

#### Optionnelles

```bash
# PostgreSQL support (recommandé)
pip install psycopg2-binary

# Tests
pip install pytest pytest-cov pytest-mock

# Développement
pip install black flake8 mypy
```

### Outils Recommandés

- **IDE :** VS Code, PyCharm, Qt Creator
- **Extensions VS Code :**
  - Python
  - Qt for Python
  - GitLens
- **Qt Designer** : Pour éditer les fichiers `.ui`

---

## 🚀 Installation en Mode Développement

### 1. Cloner le Repository

```bash
# HTTPS
git clone https://github.com/sducournau/filter_mate.git

# SSH
git clone git@github.com:sducournau/filter_mate.git

cd filter_mate
```

### 2. Lien Symbolique vers QGIS Plugins

#### Linux / macOS

```bash
# Créer lien symbolique
ln -s $(pwd) ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate

# Ou copier (moins pratique pour dev)
cp -r . ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate
```

#### Windows

```powershell
# PowerShell (Administrateur)
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\filter_mate" `
  -Target "C:\path\to\filter_mate"

# Ou CMD (Administrateur)
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\filter_mate" "C:\path\to\filter_mate"
```

### 3. Installer Dépendances Optionnelles

```bash
# PostgreSQL support
pip install psycopg2-binary

# Tests
pip install -r requirements-test.txt
```

### 4. Compiler les Ressources UI

```bash
# Linux / macOS
./compile_ui.sh

# Windows
compile_ui.bat
```

**Détails de compilation :**

```bash
# compile_ui.sh fait :
pyrcc5 -o resources.py resources.qrc
pyuic5 -o filter_mate_dockwidget_base.py filter_mate_dockwidget_base.ui
```

### 5. Activer dans QGIS

1. Lancer QGIS
2. **Extensions → Gérer et installer les extensions**
3. Onglet **Installées**
4. Cocher **FilterMate**
5. Vérifier dans **Extensions → FilterMate** que le menu apparaît

---

## 🏗️ Structure de Développement

### Workflow Git

```bash
# Créer une branche feature
git checkout -b feature/my-new-feature

# Développer, tester
# ...

# Commit avec message conventionnel
git add .
git commit -m "feat: add spatial predicate 'covers'"

# Pousser et créer PR
git push origin feature/my-new-feature
```

### Convention de Commits (Conventional Commits)

| Préfixe      | Usage                   | Exemple                             |
| ------------ | ----------------------- | ----------------------------------- |
| **feat**     | Nouvelle fonctionnalité | `feat: add favorites tagging`       |
| **fix**      | Correction bug          | `fix: correct UUID filtering`       |
| **docs**     | Documentation           | `docs: update README`               |
| **refactor** | Refactoring             | `refactor: extract backend factory` |
| **perf**     | Performance             | `perf: optimize WKT caching`        |
| **test**     | Tests                   | `test: add backend selection tests` |
| **chore**    | Maintenance             | `chore: update dependencies`        |

---

## 📝 Standards de Code

### PEP 8 et Style

```python
# ✅ Bon
def get_datasource_connexion_from_layer(layer):
    """
    Get PostgreSQL connection from layer.

    Args:
        layer (QgsVectorLayer): Source layer

    Returns:
        Tuple[connection, uri]: Connection and URI objects
    """
    if not POSTGRESQL_AVAILABLE:
        return None, None

    uri = QgsDataSourceUri(layer.source())
    # ...

# ❌ Mauvais
def GetConnection(Layer):  # PascalCase interdit pour fonctions
    conn=psycopg2.connect(...)  # Pas d'espace autour =
    return conn  # Pas de docstring
```

### Naming Conventions

| Type                   | Convention       | Exemple                                      |
| ---------------------- | ---------------- | -------------------------------------------- |
| **Classes**            | PascalCase       | `FilterMateApp`, `PostgreSQLGeometricFilter` |
| **Fonctions/Méthodes** | snake_case       | `apply_geometric_filter`, `get_backend`      |
| **Constantes**         | UPPER_SNAKE_CASE | `POSTGRESQL_AVAILABLE`, `PROVIDER_POSTGRES`  |
| **Variables**          | snake_case       | `layer_provider_type`, `feature_count`       |
| **Privées**            | \_prefixed       | `_internal_method`, `_cache`                 |

### Ordre des Imports

```python
# 1. Standard library
import os
import sys
import json
from typing import Dict, Optional, Tuple

# 2. Third-party (QGIS, PyQt)
from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QApplication

# 3. Local application
from .config.config import ENV_VARS
from .modules.backends import BackendFactory
from .modules.appUtils import (
    POSTGRESQL_AVAILABLE,
    get_datasource_connexion_from_layer
)
```

### Docstrings

```python
def apply_geometric_filter(
    self,
    predicate: str,
    source_geometry_wkt: str,
    buffer_distance: float = 0.0,
    buffer_unit: int = QgsUnitTypes.DistanceMeters,
    **kwargs
) -> Tuple[bool, str, int]:
    """
    Apply a geometric filter to the layer.

    This method filters features based on a spatial predicate (intersects,
    within, contains, etc.) applied to a source geometry with optional buffer.

    Args:
        predicate: Spatial predicate name (e.g., 'intersects', 'within')
        source_geometry_wkt: Source geometry as WKT string
        buffer_distance: Buffer distance (default: 0.0)
        buffer_unit: QgsUnitTypes distance unit (default: meters)
        **kwargs: Additional backend-specific parameters

    Returns:
        Tuple of:
        - success (bool): True if filter applied successfully
        - expression (str): Filter expression used
        - feature_count (int): Number of features after filtering

    Raises:
        FilterMateException: If layer is invalid or provider unsupported

    Example:
        >>> backend = PostgreSQLGeometricFilter(layer, {})
        >>> success, expr, count = backend.apply_geometric_filter(
        ...     'intersects',
        ...     'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
        ...     buffer_distance=10.0
        ... )
    """
    pass
```

---

## 🔧 Patterns de Développement Critiques

### 1. Vérification PostgreSQL

**❌ INCORRECT - Import direct**

```python
import psycopg2  # CRASH si psycopg2 non installé
```

**✅ CORRECT - Utiliser POSTGRESQL_AVAILABLE**

```python
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider_type == 'postgresql':
    # Code PostgreSQL sécurisé
    connexion = psycopg2.connect(...)
else:
    # Fallback Spatialite ou OGR
    pass
```

### 2. Détection Provider Type

**✅ Pattern Standard**

```python
from modules.appUtils import detect_layer_provider_type
from modules.constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE

provider_type = detect_layer_provider_type(layer)

if provider_type == PROVIDER_POSTGRES:
    # PostgreSQL-specific
    pass
elif provider_type == PROVIDER_SPATIALITE:
    # Spatialite-specific
    pass
else:
    # OGR fallback
    pass
```

### 3. Connexions Spatialite

**✅ Pattern Spatialite**

```python
import sqlite3

def spatialite_connect(db_path: str) -> sqlite3.Connection:
    """Connect to Spatialite database with mod_spatialite loaded."""
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)

    try:
        conn.load_extension('mod_spatialite')
    except:
        # Windows fallback
        conn.load_extension('mod_spatialite.dll')

    return conn

# Usage
conn = spatialite_connect('/path/to/db.gpkg')
cursor = conn.cursor()
try:
    cursor.execute("SELECT ST_AsText(geom) FROM layer WHERE ...")
    results = cursor.fetchall()
finally:
    conn.close()
```

### 4. QgsTask Pattern (Tâches Asynchrones)

**✅ Template QgsTask**

```python
from qgis.core import QgsTask

class MyTask(QgsTask):
    """Custom asynchronous task."""

    def __init__(self, description: str, task_parameters: Dict):
        super().__init__(description, QgsTask.CanCancel)
        self.task_parameters = task_parameters
        self.result_data = None
        self.exception = None

    def run(self) -> bool:
        """
        Executed in separate thread.

        DO NOT:
        - Access Qt widgets directly
        - Call iface methods
        - Use QgsMessageBar

        Returns:
            bool: True if success, False if failure
        """
        try:
            # Check for cancellation
            if self.isCanceled():
                return False

            # Heavy computation here
            result = self._do_work()

            # Store result
            self.result_data = result
            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result: bool):
        """
        Executed in main thread after run().

        Safe to:
        - Update UI
        - Show messages
        - Access iface
        """
        if result:
            # Success handling
            iface.messageBar().pushSuccess(
                "FilterMate",
                f"Task completed: {self.result_data}"
            )
        else:
            # Error handling
            if self.exception:
                iface.messageBar().pushCritical(
                    "FilterMate",
                    f"Task failed: {str(self.exception)}"
                )

    def _do_work(self):
        """Internal work method."""
        # Implementation
        pass

# Usage
task = MyTask("My custom task", {"param": "value"})
QgsApplication.taskManager().addTask(task)
```

### 5. Backend Selection

**✅ Utiliser BackendFactory**

```python
from modules.backends import BackendFactory
from modules.appUtils import detect_layer_provider_type

# Détecte provider
provider_type = detect_layer_provider_type(layer)

# Obtient backend optimal
backend = BackendFactory.get_backend(
    layer=layer,
    layer_provider_type=provider_type,
    task_params={
        'use_cache': True,
        'enable_optimization': True
    }
)

# Applique filtre
success, expression, feature_count = backend.apply_geometric_filter(
    predicate='intersects',
    source_geometry_wkt='POLYGON(...)',
    buffer_distance=10.0,
    buffer_unit=QgsUnitTypes.DistanceMeters
)
```

### 6. Gestion Sécurisée des Objets Qt/QGIS

**✅ Utiliser object_safety**

```python
from modules.object_safety import (
    is_valid_layer,
    is_sip_deleted,
    require_valid_layer,
    safe_disconnect
)

# Validation manuelle
if not is_valid_layer(layer):
    logger.error("Invalid layer")
    return

# Validation automatique (decorator)
@require_valid_layer
def process_layer(layer: QgsVectorLayer):
    """Layer is guaranteed valid here."""
    pass

# Déconnexion sécurisée signaux
safe_disconnect(layer.dataChanged, self.on_data_changed)
```

### 7. Messages Utilisateur

**✅ CORRECT - 2 arguments seulement**

```python
from qgis.utils import iface

# ✅ Success
iface.messageBar().pushSuccess("FilterMate", "Filter applied successfully")

# ✅ Info
iface.messageBar().pushInfo("FilterMate", "Using Spatialite backend")

# ✅ Warning
iface.messageBar().pushWarning(
    "FilterMate",
    "Large dataset detected. Consider PostgreSQL for better performance."
)

# ✅ Error
iface.messageBar().pushCritical("FilterMate", f"Error: {str(error)}")
```

**❌ INCORRECT - 3 arguments (deprecated)**

```python
# ❌ NE PAS FAIRE - duration parameter deprecated
iface.messageBar().pushSuccess("FilterMate", "Message", 5)  # CRASH
```

---

## 🧪 Tests

### Exécuter les Tests

```bash
# Tous les tests
pytest

# Avec coverage
pytest --cov=. --cov-report=html

# Tests spécifiques
pytest tests/test_backends.py
pytest tests/test_backends.py::test_postgresql_backend

# Verbose
pytest -v
```

### Écrire des Tests

```python
# tests/test_my_feature.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from qgis.core import QgsVectorLayer

from modules.backends import BackendFactory

class TestBackendFactory:
    """Tests for BackendFactory."""

    @pytest.fixture
    def mock_layer(self):
        """Create a mock QgsVectorLayer."""
        layer = MagicMock(spec=QgsVectorLayer)
        layer.isValid.return_value = True
        layer.providerType.return_value = 'postgres'
        layer.featureCount.return_value = 1000
        return layer

    def test_get_backend_postgresql(self, mock_layer):
        """Test PostgreSQL backend selection."""
        from modules.backends.postgresql_backend import PostgreSQLGeometricFilter

        backend = BackendFactory.get_backend(
            mock_layer,
            'postgresql',
            {}
        )

        assert isinstance(backend, PostgreSQLGeometricFilter)

    @patch('modules.backends.factory.POSTGRESQL_AVAILABLE', False)
    def test_fallback_when_psycopg2_unavailable(self, mock_layer):
        """Test fallback to OGR when psycopg2 unavailable."""
        from modules.backends.ogr_backend import OGRGeometricFilter

        backend = BackendFactory.get_backend(
            mock_layer,
            'postgresql',  # Demande PostgreSQL
            {}
        )

        # Doit fallback vers OGR
        assert isinstance(backend, OGRGeometricFilter)
```

### Coverage Actuel

- **Global :** ~70%
- **Backend Layer :** ~75%
- **Task Layer :** ~65%
- **Utilities :** ~80%

**Objectif :** 80% coverage global

---

## 🔍 Debugging

### Logging

```python
from modules.logging_config import get_logger

logger = get_logger(__name__)

# Niveaux disponibles
logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error")

# Avec contexte
logger.info(f"Processing layer: {layer.name()}, features: {layer.featureCount()}")
```

**Fichiers de log :**

```
logs/
├── filtermate.log           # Log général
├── filtermate_tasks.log     # Tâches asynchrones
└── filtermate_utils.log     # Utilitaires
```

### Console Python QGIS

```python
# Dans QGIS Python Console
from filter_mate.filter_mate_app import FilterMateApp
from filter_mate.modules.backends import BackendFactory

# Accès direct aux composants
app = iface.mainWindow().findChild(FilterMateApp)
print(f"Current layer: {app.current_layer}")
```

### VS Code Launch Configuration

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "QGIS Python",
      "type": "python",
      "request": "attach",
      "port": 5678,
      "host": "localhost",
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "."
        }
      ]
    }
  ]
}
```

```python
# Dans votre code
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()  # Pause ici
```

---

## 📦 Compilation et Release

### Compiler les Ressources

```bash
# UI files (.ui → .py)
pyuic5 -o filter_mate_dockwidget_base.py filter_mate_dockwidget_base.ui

# Qt resources (.qrc → .py)
pyrcc5 -o resources.py resources.qrc

# Ou script tout-en-un
./compile_ui.sh  # Linux/macOS
compile_ui.bat   # Windows
```

### Compiler les Traductions

```bash
# .ts → .qm (compilation)
lrelease i18n/FilterMate_fr.ts

# Mise à jour .ts depuis code source
pylupdate5 filter_mate.pro

# Tous les .ts
for file in i18n/*.ts; do lrelease "$file"; done
```

### Créer un Package

```bash
# Script de packaging (à créer)
./build_plugin.sh

# Contenu minimal du script
#!/bin/bash
VERSION=$(grep "version=" metadata.txt | cut -d= -f2)
PLUGIN_NAME="filter_mate"

# Créer archive
zip -r ${PLUGIN_NAME}_${VERSION}.zip \
    *.py \
    *.txt \
    *.md \
    config/ \
    modules/ \
    i18n/*.qm \
    icons/ \
    -x "*.pyc" -x "__pycache__/*"
```

---

## 🚀 Contribuer

### Process de Contribution

1. **Fork** le repository
2. **Clone** votre fork
3. **Créer branche** feature/fix
4. **Développer** avec tests
5. **Commit** avec messages conventionnels
6. **Push** vers votre fork
7. **Créer Pull Request** vers `main`

### Checklist PR

- [ ] Tests passent (`pytest`)
- [ ] Code formaté (`black`, `flake8`)
- [ ] Docstrings ajoutées
- [ ] Documentation mise à jour si nécessaire
- [ ] CHANGELOG.md mis à jour
- [ ] Pas de régression performance

### Review Process

1. **CI/CD** : Tests automatiques GitHub Actions
2. **Code Review** : Revue par mainteneur
3. **Merge** : Squash and merge vers main
4. **Release** : Tag sémantique (v2.9.13, etc.)

---

## 📚 Ressources Utiles

### Documentation QGIS

- **QGIS API Docs :** https://qgis.org/pyqgis/master/
- **PyQGIS Cookbook :** https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/
- **Plugin Development :** https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/plugins/index.html

### PyQt5

- **Qt for Python Docs :** https://doc.qt.io/qtforpython/
- **Qt Designer :** https://doc.qt.io/qt-5/qtdesigner-manual.html

### Spatial Databases

- **PostGIS Docs :** https://postgis.net/documentation/
- **Spatialite Docs :** https://www.gaia-gis.it/fossil/libspatialite/index

### Python

- **PEP 8 Style Guide :** https://peps.python.org/pep-0008/
- **pytest Docs :** https://docs.pytest.org/

---

## 🔑 Commandes Quick Reference

```bash
# Installation dev
ln -s $(pwd) ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate
./compile_ui.sh
pip install -r requirements-test.txt

# Tests
pytest
pytest --cov=. --cov-report=html
pytest tests/test_backends.py -v

# Code quality
black .
flake8 . --max-line-length=120
mypy modules/

# Build
./compile_ui.sh
for file in i18n/*.ts; do lrelease "$file"; done

# Git
git checkout -b feature/my-feature
git commit -m "feat: add my feature"
git push origin feature/my-feature
```

---

## 🆘 Problèmes Courants

### QGIS ne détecte pas le plugin

1. Vérifier le lien symbolique
2. Vérifier `metadata.txt` (syntaxe)
3. Recharger QGIS
4. Vérifier logs : `Help → Message Log`

### Import psycopg2 échoue

```python
# Solution : vérifier POSTGRESQL_AVAILABLE
from modules.appUtils import POSTGRESQL_AVAILABLE

if not POSTGRESQL_AVAILABLE:
    # Fallback OGR
    pass
```

### Tests échouent

```bash
# Installer dépendances test
pip install -r requirements-test.txt

# Vérifier PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Relancer
pytest -v
```

---

## 📞 Support

- **GitHub Issues :** https://github.com/sducournau/filter_mate/issues
- **Email :** simon.ducournau+filter_mate@gmail.com
- **Documentation :** https://sducournau.github.io/filter_mate

---

**Prochaine étape :** [Source Tree Analysis](source-tree-analysis.md)
