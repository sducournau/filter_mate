# 📋 Plan d'Action FilterMate v2.3.0
**Date de création :** 14 décembre 2025  
**Basé sur :** Audit de Qualité, Stabilité et Performance  
**Objectif :** Améliorer la qualité du code et la maintenabilité

---

## 📊 État Actuel

| Métrique | Valeur | Objectif |
|----------|--------|----------|
| Score Global | 76/100 (4/5 ⭐) | 85/100 |
| Couverture Tests | ~5% | 30% |
| Lignes de Code | ~25,574 | - |
| Plus Gros Fichier | `filter_mate_dockwidget.py` (6,160 lignes) | < 2,000 |
| Type Hints | ~30% | 60% |
| `except:` bare | 0 ✅ | 0 |
| Wildcard Imports | 2/33 (légitimes) ✅ | Maintenir |

---

## 🎯 Priorités

### 🔴 Priorité Haute (P0)
- [ ] Convertir les tests en format pytest standard
- [ ] Augmenter la couverture de tests à 15%

### 🟠 Priorité Moyenne (P1)
- [ ] Refactoriser `filter_mate_dockwidget.py`
- [ ] Créer un `SignalManager` centralisé
- [ ] Supprimer les `global ENV_VARS` dans les tasks

### 🟡 Priorité Basse (P2)
- [ ] Ajouter type hints aux méthodes publiques
- [ ] Documenter les méthodes complexes
- [ ] Supprimer le shim `appTasks.py` (prévu v3.0.0)

---

## 📅 Sprint 1 : Fondations Tests (3-5 jours)

### Objectifs
- Convertir les tests existants en format pytest
- Créer des fixtures réutilisables
- Atteindre 15% de couverture

### Tâches

#### 1.1 Convertir `test_undo_redo.py` en pytest ✏️
**Fichier :** `tests/test_undo_redo.py`  
**Effort :** 2h  
**Priorité :** P0

```python
# ❌ Format actuel (fonctions standalone avec print)
def test_filter_state():
    print("\n=== Testing FilterState ===")
    state = FilterState("population > 10000", 150)
    assert state.expression == "population > 10000"
    print("✓ FilterState creation works")

# ✅ Format pytest
import pytest
from modules.filter_history import FilterState, FilterHistory, HistoryManager

class TestFilterState:
    """Tests for FilterState class."""
    
    def test_basic_creation(self):
        """Test FilterState with all parameters."""
        state = FilterState("population > 10000", 150, "Large cities")
        assert state.expression == "population > 10000"
        assert state.feature_count == 150
        assert state.description == "Large cities"
    
    def test_auto_description_empty_filter(self):
        """Test automatic description for empty filter."""
        state = FilterState("", 1000)
        assert "No filter" in state.description
    
    def test_long_expression_truncation(self):
        """Test that long expressions are truncated in description."""
        long_expr = "a" * 100
        state = FilterState(long_expr, 50)
        assert len(state.description) <= 63
        assert "..." in state.description


class TestFilterHistory:
    """Tests for FilterHistory class."""
    
    @pytest.fixture
    def history(self):
        """Create a fresh FilterHistory for each test."""
        return FilterHistory("layer_1", max_size=5)
    
    def test_initial_state(self, history):
        """Test that new history has no undo/redo."""
        assert not history.can_undo()
        assert not history.can_redo()
    
    def test_push_and_undo(self, history):
        """Test pushing states and undoing."""
        history.push_state("filter1", 100)
        history.push_state("filter2", 50)
        
        assert history.can_undo()
        prev_state = history.undo()
        assert prev_state.expression == "filter1"
```

#### 1.2 Convertir `test_filter_preservation.py` ✏️
**Fichier :** `tests/test_filter_preservation.py`  
**Effort :** 1h  
**Priorité :** P0

#### 1.3 Ajouter tests pour `config_manager.py` 🆕
**Fichier :** `tests/test_config_manager.py`  
**Effort :** 3h  
**Priorité :** P0

```python
import pytest
from config.config_manager import ConfigManager

class TestConfigManager:
    """Tests for ConfigManager v2."""
    
    @pytest.fixture
    def config_manager(self, tmp_path):
        """Create ConfigManager with temp directory."""
        return ConfigManager(str(tmp_path), auto_load=False)
    
    def test_get_with_default(self, config_manager):
        """Test get() returns default for missing keys."""
        result = config_manager.get('NONEXISTENT', 'KEY', default='fallback')
        assert result == 'fallback'
    
    def test_set_and_get(self, config_manager):
        """Test setting and retrieving values."""
        config_manager.set('TEST', 'KEY', 'value')
        assert config_manager.get('TEST', 'KEY') == 'value'
    
    def test_is_feature_enabled_defaults_true(self, config_manager):
        """Test that unknown features default to enabled."""
        assert config_manager.is_feature_enabled('UNKNOWN_FEATURE') is True
```

#### 1.4 Créer fixtures QGIS complètes 🆕
**Fichier :** `tests/conftest.py`  
**Effort :** 2h  
**Priorité :** P0

```python
@pytest.fixture
def mock_vector_layer():
    """Create a mock QgsVectorLayer."""
    from unittest.mock import Mock, PropertyMock
    
    layer = Mock()
    layer.id.return_value = 'test_layer_123'
    layer.name.return_value = 'Test Layer'
    layer.providerType.return_value = 'ogr'
    layer.isValid.return_value = True
    layer.featureCount.return_value = 100
    layer.subsetString.return_value = ''
    layer.setSubsetString.return_value = True
    layer.fields.return_value = Mock()
    layer.sourceCrs.return_value = Mock(authid=lambda: 'EPSG:4326')
    
    return layer


@pytest.fixture
def sample_project_layers(mock_vector_layer):
    """Create sample PROJECT_LAYERS dictionary."""
    return {
        'test_layer_123': {
            'infos': {
                'layer_id': 'test_layer_123',
                'layer_name': 'Test Layer',
                'layer_provider_type': 'ogr',
                'layer_geometry_type': 'GeometryType.Point',
                'layer_crs_authid': 'EPSG:4326',
                'primary_key_name': 'id',
            },
            'exploring': {
                'is_tracking': False,
                'is_selecting': False,
            },
            'filtering': {
                'has_layers_to_filter': False,
                'layers_to_filter': [],
            }
        }
    }
```

---

## 📅 Sprint 2 : Refactorisation UI (1 semaine)

### Objectifs
- Réduire `filter_mate_dockwidget.py` de 6,160 à < 3,000 lignes
- Extraire les composants UI en modules séparés
- Créer un gestionnaire de signaux centralisé

### Tâches

#### 2.1 Créer la structure `modules/ui/` 🆕
**Effort :** 1h

```
modules/ui/
├── __init__.py
├── exploring_panel.py      # 800-1000 lignes
├── filtering_panel.py      # 600-800 lignes
├── exporting_panel.py      # 400-600 lignes
├── config_panel.py         # 300-400 lignes
├── layer_selector.py       # 200-300 lignes
└── signal_manager.py       # 150-200 lignes
```

#### 2.2 Extraire `ExploringPanel` 🆕
**Fichier :** `modules/ui/exploring_panel.py`  
**Effort :** 4h  
**Priorité :** P1

Méthodes à extraire de `filter_mate_dockwidget.py` :
- `setup_exploring_tab()`
- `_setup_single_selection_group()`
- `_setup_multiple_selection_group()`
- `_setup_custom_selection_group()`
- `manage_exploring_groupboxes()`
- `get_current_features()`
- ~20 méthodes liées à l'exploration

#### 2.3 Créer `SignalManager` 🆕
**Fichier :** `modules/ui/signal_manager.py`  
**Effort :** 3h  
**Priorité :** P1

```python
"""
Centralized Signal Manager for FilterMate UI.

Provides a clean interface for connecting/disconnecting Qt signals
with automatic cleanup and state tracking.
"""
from typing import Dict, List, Callable, Optional
from qgis.PyQt.QtCore import QObject
import logging

logger = logging.getLogger('FilterMate.UI.Signals')


class SignalManager:
    """
    Manages Qt signal connections with automatic tracking and cleanup.
    
    Usage:
        manager = SignalManager()
        manager.connect(widget.clicked, handler, group="filtering")
        manager.disconnect_group("filtering")
        manager.disconnect_all()
    """
    
    def __init__(self):
        self._connections: Dict[str, List[tuple]] = {}
        self._connection_count = 0
    
    def connect(self, signal, slot: Callable, group: str = "default") -> bool:
        """
        Connect a signal to a slot with group tracking.
        
        Args:
            signal: Qt signal to connect
            slot: Callable to receive the signal
            group: Group name for bulk disconnect operations
        
        Returns:
            True if connected successfully
        """
        try:
            signal.connect(slot)
            
            if group not in self._connections:
                self._connections[group] = []
            
            self._connections[group].append((signal, slot))
            self._connection_count += 1
            
            logger.debug(f"Connected signal to {slot.__name__} in group '{group}'")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to connect signal: {e}")
            return False
    
    def disconnect_group(self, group: str) -> int:
        """
        Disconnect all signals in a group.
        
        Args:
            group: Group name to disconnect
        
        Returns:
            Number of signals disconnected
        """
        if group not in self._connections:
            return 0
        
        count = 0
        for signal, slot in self._connections[group]:
            try:
                signal.disconnect(slot)
                count += 1
            except (TypeError, RuntimeError):
                pass  # Already disconnected
        
        del self._connections[group]
        self._connection_count -= count
        
        logger.debug(f"Disconnected {count} signals from group '{group}'")
        return count
    
    def disconnect_all(self) -> int:
        """Disconnect all managed signals."""
        total = 0
        for group in list(self._connections.keys()):
            total += self.disconnect_group(group)
        return total
    
    def get_stats(self) -> Dict:
        """Get connection statistics."""
        return {
            'total_connections': self._connection_count,
            'groups': list(self._connections.keys()),
            'connections_per_group': {
                g: len(c) for g, c in self._connections.items()
            }
        }
```

#### 2.4 Supprimer `global ENV_VARS` dans les tasks ✏️
**Fichiers :** 
- `modules/tasks/filter_task.py:201`
- `modules/tasks/layer_management_task.py:147`

**Effort :** 2h  
**Priorité :** P1

```python
# ❌ Actuel
def run(self):
    global ENV_VARS
    self.PROJECT = ENV_VARS["PROJECT"]

# ✅ Corrigé - Passer via task_parameters
def run(self):
    self.PROJECT = self.task_parameters.get("project")
```

---

## 📅 Sprint 3 : Qualité & Documentation (2 semaines)

### Objectifs
- Atteindre 30% de couverture de tests
- Ajouter type hints aux interfaces publiques
- Améliorer la documentation inline

### Tâches

#### 3.1 Tests pour `filter_task.py` 🆕
**Fichier :** `tests/test_filter_task.py`  
**Effort :** 6h  
**Priorité :** P1

Tests à créer :
- `test_initialize_source_layer()`
- `test_configure_metric_crs()`
- `test_organize_layers_to_filter()`
- `test_qgis_expression_to_postgis()`
- `test_qgis_expression_to_spatialite()`
- `test_combine_with_old_subset()`

#### 3.2 Tests pour backends 🆕
**Effort :** 4h  
**Priorité :** P1

Compléter :
- `tests/test_backends/test_ogr_backend.py`
- `tests/test_backends/test_spatialite_backend.py`
- Créer `tests/test_backends/test_postgresql_backend.py` (mocked)

#### 3.3 Ajouter type hints 📝
**Fichiers prioritaires :**  
**Effort :** 4h  
**Priorité :** P2

```python
# filter_mate_app.py - Méthodes publiques
def manage_task(self, task_name: str, data: Optional[Any] = None) -> None:
    ...

def get_task_parameters(self, task_name: str, data: Optional[Any] = None) -> Dict[str, Any]:
    ...

def filter_engine_task_completed(
    self, 
    task_name: str, 
    source_layer: QgsVectorLayer, 
    task_parameters: Dict[str, Any]
) -> None:
    ...
```

#### 3.4 Documenter les méthodes complexes 📝
**Effort :** 3h  
**Priorité :** P2

Ajouter docstrings complètes avec exemples pour :
- `FilterEngineTask.execute_filtering()`
- `FilterEngineTask._process_qgis_expression()`
- `LayersManagementEngineTask.add_project_layer()`

---

## 📅 Sprint 4 : Optimisation & Nettoyage (1 semaine)

### Objectifs
- Préparer la dépréciation de `appTasks.py`
- Optimiser les caches
- Finaliser la documentation

### Tâches

#### 4.1 Préparer dépréciation `appTasks.py`
**Effort :** 2h  
**Priorité :** P2

- Ajouter avertissement de version dans le warning
- Documenter le chemin de migration dans CHANGELOG
- Prévoir suppression pour v3.0.0

#### 4.2 Ajouter thread-safety au cache de styles
**Fichier :** `modules/ui_styles.py`  
**Effort :** 1h  
**Priorité :** P2

```python
import threading

class StyleLoader:
    _styles_cache: Dict[str, str] = {}
    _cache_lock = threading.Lock()
    
    @classmethod
    def load_stylesheet(cls, theme: str = 'default') -> str:
        with cls._cache_lock:
            if theme in cls._styles_cache:
                return cls._styles_cache[theme]
            # ... load and cache
```

#### 4.3 Créer `MIGRATION_GUIDE.md` 🆕
**Effort :** 2h  
**Priorité :** P2

Guide pour les utilisateurs passant de v2.2.x à v2.3.0+

---

## 📈 Métriques de Succès

| Métrique | Actuel | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 |
|----------|--------|----------|----------|----------|----------|
| Couverture Tests | 5% | 15% | 20% | 30% | 35% |
| Lignes dockwidget | 6,160 | 6,160 | 4,000 | 3,500 | 3,000 |
| Type Hints | 30% | 30% | 35% | 50% | 60% |
| Score Global | 76/100 | 78/100 | 82/100 | 85/100 | 88/100 |

---

## 🛠️ Outils et Commandes

### Exécuter les tests
```bash
cd /path/to/filter_mate
pytest tests/ -v --cov=. --cov-report=html
```

### Vérifier la qualité du code
```bash
flake8 . --max-line-length=120 --statistics
black --check --line-length 120 modules/ *.py
```

### Générer le rapport de couverture
```bash
pytest tests/ --cov=modules --cov-report=html
# Ouvrir htmlcov/index.html
```

---

## 📝 Notes

### Risques Identifiés
1. **Régression UI** lors de l'extraction des panels → Tests manuels nécessaires
2. **Compatibilité QGIS** → Tester sur QGIS 3.28, 3.34, 3.36
3. **Migration configs** → Préserver la rétrocompatibilité v2.2.x

### Dépendances Externes
- pytest >= 7.0.0
- pytest-cov >= 4.0.0
- pytest-mock >= 3.10.0

### Contacts
- **Mainteneur :** @sducournau
- **Repository :** https://github.com/sducournau/filter_mate

---

**Dernière mise à jour :** 14 décembre 2025
