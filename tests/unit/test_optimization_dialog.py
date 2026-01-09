"""
Unit tests for OptimizationDialog.

Tests dialog initialization, settings management, and recommendations.
Story: MIG-082
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────
# Mock PyQt5/QGIS before importing
# ─────────────────────────────────────────────────────────────────

class MockSignal:
    """Mock pyqtSignal for testing."""
    def __init__(self, *args):
        self.args = args
        self.callbacks = []
        self.emissions = []
    
    def emit(self, *args):
        self.emissions.append(args)
        for cb in self.callbacks:
            cb(*args)
    
    def connect(self, callback):
        self.callbacks.append(callback)


class MockWidget:
    """Mock QWidget base."""
    def __init__(self, parent=None):
        self.parent = parent
        self._visible = False
    
    def setVisible(self, visible):
        self._visible = visible
    
    def isVisible(self):
        return self._visible


class MockCheckBox(MockWidget):
    """Mock QCheckBox."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self._checked = False
        self._style = ""
    
    def setChecked(self, checked):
        self._checked = checked
    
    def isChecked(self):
        return self._checked
    
    def setStyleSheet(self, style):
        self._style = style


class MockSpinBox(MockWidget):
    """Mock QSpinBox."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._min = 0
        self._max = 100
    
    def setValue(self, value):
        self._value = max(self._min, min(self._max, value))
    
    def value(self):
        return self._value
    
    def setRange(self, min_val, max_val):
        self._min = min_val
        self._max = max_val
    
    def setSingleStep(self, step):
        pass
    
    def setSuffix(self, suffix):
        pass


class MockLayout:
    """Mock layout class."""
    def __init__(self, parent=None):
        self.widgets = []
        self.layouts = []
    
    def addWidget(self, widget, *args):
        self.widgets.append(widget)
    
    def addLayout(self, layout, *args):
        self.layouts.append(layout)
    
    def addStretch(self, *args):
        pass
    
    def setSpacing(self, spacing):
        pass
    
    def setContentsMargins(self, *args):
        pass


class MockDialog(MockWidget):
    """Mock QDialog."""
    Accepted = 1
    Rejected = 0
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
    
    def setWindowTitle(self, title):
        self._title = title
    
    def setMinimumWidth(self, width):
        pass
    
    def setMinimumHeight(self, height):
        pass
    
    def setModal(self, modal):
        pass
    
    def accept(self):
        self._result = self.Accepted
    
    def reject(self):
        self._result = self.Rejected
    
    def exec_(self):
        return self._result or self.Rejected
    
    def tr(self, text):
        return text


# Apply mocks
import sys

mock_qt = MagicMock()
mock_qt.Qt = Mock()
mock_qt.Qt.Horizontal = 1
mock_qt.pyqtSignal = MockSignal

mock_widgets = MagicMock()
mock_widgets.QDialog = MockDialog
mock_widgets.QWidget = MockWidget
mock_widgets.QVBoxLayout = MockLayout
mock_widgets.QHBoxLayout = MockLayout
mock_widgets.QGridLayout = MockLayout
mock_widgets.QCheckBox = MockCheckBox
mock_widgets.QSpinBox = MockSpinBox
mock_widgets.QDoubleSpinBox = MockSpinBox
mock_widgets.QLabel = Mock
mock_widgets.QPushButton = Mock
mock_widgets.QFrame = Mock
mock_widgets.QGroupBox = Mock
mock_widgets.QTabWidget = Mock
mock_widgets.QDialogButtonBox = Mock
mock_widgets.QMessageBox = Mock
mock_widgets.QComboBox = Mock
mock_widgets.QScrollArea = Mock

sys.modules['qgis'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = mock_qt
sys.modules['qgis.PyQt.QtWidgets'] = mock_widgets
sys.modules['PyQt5'] = Mock()
sys.modules['PyQt5.QtCore'] = mock_qt
sys.modules['PyQt5.QtWidgets'] = mock_widgets


# Now import the module
from ui.dialogs.optimization_dialog import (
    OptimizationType,
    OptimizationSettings,
    OptimizationRecommendation,
    OptimizationDialog,
    RecommendationDialog
)


# ─────────────────────────────────────────────────────────────────
# Test OptimizationType Enum
# ─────────────────────────────────────────────────────────────────

class TestOptimizationType:
    """Tests for OptimizationType enum."""
    
    def test_all_types_exist(self):
        """Verify all expected optimization types exist."""
        assert OptimizationType.AUTO_CENTROID is not None
        assert OptimizationType.SIMPLIFY_BEFORE_BUFFER is not None
        assert OptimizationType.REDUCE_BUFFER_SEGMENTS is not None
        assert OptimizationType.USE_SPATIAL_INDEX is not None
        assert OptimizationType.CACHE_GEOMETRIES is not None
        assert OptimizationType.BATCH_PROCESSING is not None


# ─────────────────────────────────────────────────────────────────
# Test OptimizationSettings
# ─────────────────────────────────────────────────────────────────

class TestOptimizationSettings:
    """Tests for OptimizationSettings dataclass."""
    
    def test_default_values(self):
        """Test default settings values."""
        settings = OptimizationSettings()
        
        assert settings.enabled is True
        assert settings.ask_before_apply is True
        assert settings.auto_centroid_enabled is True
        assert settings.centroid_threshold_distant == 5000
        assert settings.postgresql_use_mv is True
        assert settings.spatialite_use_rtree is True
        assert settings.ogr_use_bbox is True
    
    def test_custom_values(self):
        """Test custom settings values."""
        settings = OptimizationSettings(
            enabled=False,
            auto_centroid_enabled=False,
            centroid_threshold_distant=10000,
            batch_size=5000
        )
        
        assert settings.enabled is False
        assert settings.auto_centroid_enabled is False
        assert settings.centroid_threshold_distant == 10000
        assert settings.batch_size == 5000
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        settings = OptimizationSettings()
        result = settings.to_dict()
        
        assert isinstance(result, dict)
        assert 'enabled' in result
        assert 'auto_centroid' in result
        assert 'backends' in result
        assert 'advanced' in result
        
        assert result['enabled'] is True
        assert result['auto_centroid']['enabled'] is True
        assert result['backends']['postgresql']['use_materialized_views'] is True
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'enabled': False,
            'ask_before_apply': False,
            'auto_centroid': {
                'enabled': False,
                'distant_threshold': 8000
            },
            'backends': {
                'postgresql': {'use_materialized_views': False}
            }
        }
        
        settings = OptimizationSettings.from_dict(data)
        
        assert settings.enabled is False
        assert settings.ask_before_apply is False
        assert settings.auto_centroid_enabled is False
        assert settings.centroid_threshold_distant == 8000
        assert settings.postgresql_use_mv is False
    
    def test_from_dict_defaults(self):
        """Test from_dict with missing keys uses defaults."""
        settings = OptimizationSettings.from_dict({})
        
        assert settings.enabled is True
        assert settings.auto_centroid_enabled is True
    
    def test_round_trip(self):
        """Test to_dict and from_dict round trip."""
        original = OptimizationSettings(
            enabled=False,
            centroid_threshold_distant=12000,
            postgresql_use_mv=False,
            batch_size=2500
        )
        
        data = original.to_dict()
        restored = OptimizationSettings.from_dict(data)
        
        assert restored.enabled == original.enabled
        assert restored.centroid_threshold_distant == original.centroid_threshold_distant
        assert restored.postgresql_use_mv == original.postgresql_use_mv
        assert restored.batch_size == original.batch_size


# ─────────────────────────────────────────────────────────────────
# Test OptimizationRecommendation
# ─────────────────────────────────────────────────────────────────

class TestOptimizationRecommendation:
    """Tests for OptimizationRecommendation dataclass."""
    
    def test_creation(self):
        """Test recommendation creation."""
        rec = OptimizationRecommendation(
            type=OptimizationType.AUTO_CENTROID,
            title="Use Centroids",
            description="Use point centroids for distant layers",
            impact="high"
        )
        
        assert rec.type == OptimizationType.AUTO_CENTROID
        assert rec.title == "Use Centroids"
        assert rec.impact == "high"
        assert rec.enabled is True
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        rec = OptimizationRecommendation(
            type=OptimizationType.SIMPLIFY_BEFORE_BUFFER,
            title="Simplify Geometry",
            description="Simplify before buffering",
            impact="medium",
            enabled=False
        )
        
        result = rec.to_dict()
        
        assert result['type'] == 'SIMPLIFY_BEFORE_BUFFER'
        assert result['title'] == "Simplify Geometry"
        assert result['impact'] == "medium"
        assert result['enabled'] is False


# ─────────────────────────────────────────────────────────────────
# Test OptimizationDialog
# ─────────────────────────────────────────────────────────────────

class TestOptimizationDialog:
    """Tests for OptimizationDialog."""
    
    @pytest.fixture
    def dialog(self):
        """Create dialog with mocked widgets."""
        with patch.object(OptimizationDialog, '_setup_ui'):
            d = OptimizationDialog()
            # Create mock widgets
            d._widgets = {
                'enabled': MockCheckBox(),
                'ask_before': MockCheckBox(),
                'auto_centroid': MockCheckBox(),
                'centroid_threshold': MockSpinBox(),
                'feature_threshold': MockSpinBox(),
                'simplify_buffer': MockCheckBox(),
                'reduce_segments': MockCheckBox(),
                'segments_value': MockSpinBox(),
                'pg_mv': MockCheckBox(),
                'pg_indices': MockCheckBox(),
                'sl_rtree': MockCheckBox(),
                'ogr_bbox': MockCheckBox(),
                'cache_enabled': MockCheckBox(),
                'batch_size': MockSpinBox()
            }
            d._widgets['centroid_threshold'].setRange(1, 50000)
            d._widgets['feature_threshold'].setRange(1000, 1000000)
            d._widgets['segments_value'].setRange(1, 16)
            d._widgets['batch_size'].setRange(100, 100000)
            return d
    
    def test_initialization_default_settings(self, dialog):
        """Test dialog initializes with default settings."""
        assert dialog._settings is not None
        assert dialog._settings.enabled is True
    
    def test_initialization_custom_settings(self):
        """Test dialog with custom settings."""
        settings = OptimizationSettings(enabled=False, batch_size=5000)
        
        with patch.object(OptimizationDialog, '_setup_ui'):
            dialog = OptimizationDialog(settings=settings)
        
        assert dialog._settings.enabled is False
        assert dialog._settings.batch_size == 5000
    
    def test_load_settings(self, dialog):
        """Test loading settings into widgets."""
        dialog._settings.enabled = True
        dialog._settings.auto_centroid_enabled = False
        dialog._settings.centroid_threshold_distant = 10000
        
        dialog._load_settings()
        
        assert dialog._widgets['enabled'].isChecked() is True
        assert dialog._widgets['auto_centroid'].isChecked() is False
        assert dialog._widgets['centroid_threshold'].value() == 10  # /1000
    
    def test_save_settings(self, dialog):
        """Test saving widget values to settings."""
        dialog._widgets['enabled'].setChecked(False)
        dialog._widgets['auto_centroid'].setChecked(True)
        dialog._widgets['centroid_threshold'].setValue(8)
        dialog._widgets['batch_size'].setValue(3000)
        
        dialog._save_settings()
        
        assert dialog._settings.enabled is False
        assert dialog._settings.auto_centroid_enabled is True
        assert dialog._settings.centroid_threshold_distant == 8000
        assert dialog._settings.batch_size == 3000
    
    def test_restore_defaults(self, dialog):
        """Test restoring default settings."""
        dialog._settings.enabled = False
        dialog._settings.batch_size = 9999
        
        dialog._restore_defaults()
        
        assert dialog._settings.enabled is True
        assert dialog._settings.batch_size == 1000  # Default
    
    def test_get_settings(self, dialog):
        """Test getting current settings."""
        dialog._widgets['enabled'].setChecked(True)
        
        settings = dialog.get_settings()
        
        assert isinstance(settings, OptimizationSettings)
    
    def test_get_settings_dict(self, dialog):
        """Test getting settings as dictionary."""
        result = dialog.get_settings_dict()
        
        assert isinstance(result, dict)
        assert 'enabled' in result


# ─────────────────────────────────────────────────────────────────
# Test RecommendationDialog
# ─────────────────────────────────────────────────────────────────

class TestRecommendationDialog:
    """Tests for RecommendationDialog."""
    
    @pytest.fixture
    def recommendations(self):
        """Create sample recommendations."""
        return [
            OptimizationRecommendation(
                type=OptimizationType.AUTO_CENTROID,
                title="Use Centroids",
                description="Use centroids for distant layers",
                impact="high"
            ),
            OptimizationRecommendation(
                type=OptimizationType.SIMPLIFY_BEFORE_BUFFER,
                title="Simplify Before Buffer",
                description="Simplify geometry before buffering",
                impact="medium"
            )
        ]
    
    def test_initialization(self, recommendations):
        """Test dialog initialization."""
        with patch.object(RecommendationDialog, '_setup_ui'):
            dialog = RecommendationDialog(
                layer_name="test_layer",
                recommendations=recommendations,
                feature_count=10000
            )
        
        assert dialog._layer_name == "test_layer"
        assert dialog._feature_count == 10000
        assert len(dialog._recommendations) == 2
    
    def test_get_selected_empty(self, recommendations):
        """Test getting selected with no checkboxes."""
        with patch.object(RecommendationDialog, '_setup_ui'):
            dialog = RecommendationDialog(
                layer_name="test",
                recommendations=recommendations
            )
            dialog._checkboxes = {}
        
        result = dialog.get_selected()
        
        assert isinstance(result, dict)
        assert len(result) == 0
    
    def test_get_selected_with_checkboxes(self, recommendations):
        """Test getting selected optimizations."""
        with patch.object(RecommendationDialog, '_setup_ui'):
            dialog = RecommendationDialog(
                layer_name="test",
                recommendations=recommendations
            )
            
            # Mock checkboxes
            cb1 = MockCheckBox()
            cb1.setChecked(True)
            cb2 = MockCheckBox()
            cb2.setChecked(False)
            
            dialog._checkboxes = {
                OptimizationType.AUTO_CENTROID: cb1,
                OptimizationType.SIMPLIFY_BEFORE_BUFFER: cb2
            }
        
        result = dialog.get_selected()
        
        assert result['AUTO_CENTROID'] is True
        assert result['SIMPLIFY_BEFORE_BUFFER'] is False


# ─────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for optimization dialogs."""
    
    def test_settings_workflow(self):
        """Test complete settings workflow."""
        # Create settings
        settings = OptimizationSettings(
            enabled=False,
            auto_centroid_enabled=True,
            postgresql_use_mv=False
        )
        
        # Convert to dict (for saving)
        data = settings.to_dict()
        
        # Restore from dict (loading)
        restored = OptimizationSettings.from_dict(data)
        
        # Verify
        assert restored.enabled == settings.enabled
        assert restored.auto_centroid_enabled == settings.auto_centroid_enabled
        assert restored.postgresql_use_mv == settings.postgresql_use_mv
    
    def test_recommendation_flow(self):
        """Test recommendation creation and serialization."""
        recommendations = [
            OptimizationRecommendation(
                type=OptimizationType.USE_SPATIAL_INDEX,
                title="Create Index",
                description="Add spatial index",
                impact="high"
            ),
            OptimizationRecommendation(
                type=OptimizationType.CACHE_GEOMETRIES,
                title="Cache Geometries",
                description="Cache for repeat access",
                impact="low",
                enabled=False
            )
        ]
        
        # Serialize
        data = [r.to_dict() for r in recommendations]
        
        # Verify
        assert len(data) == 2
        assert data[0]['type'] == 'USE_SPATIAL_INDEX'
        assert data[1]['enabled'] is False
