"""
OptimizationDialog - Unified Optimization Settings Dialog.

Provides a consolidated dialog for all optimization settings:
- General optimization toggles
- Backend-specific settings (PostgreSQL, Spatialite, OGR)
- Auto-centroid configuration
- Threshold settings

Extracted from filter_mate_dockwidget.py as part of God Class migration.

Story: MIG-082
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction
"""

import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum, auto

try:
    from qgis.PyQt.QtCore import pyqtSignal
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QCheckBox, QSpinBox, QWidget,
        QFrame, QDialogButtonBox, QGroupBox, QTabWidget
    )
except ImportError:
    from PyQt5.QtCore import pyqtSignal
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QCheckBox, QSpinBox, QWidget,
        QFrame, QDialogButtonBox, QGroupBox, QTabWidget
    )

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of optimizations available."""
    AUTO_CENTROID = auto()
    SIMPLIFY_BEFORE_BUFFER = auto()
    REDUCE_BUFFER_SEGMENTS = auto()
    USE_SPATIAL_INDEX = auto()
    CACHE_GEOMETRIES = auto()
    BATCH_PROCESSING = auto()


@dataclass
class OptimizationSettings:
    """Container for all optimization settings."""
    # General settings
    enabled: bool = True
    ask_before_apply: bool = True

    # Auto-centroid settings
    auto_centroid_enabled: bool = True
    centroid_threshold_distant: int = 5000  # meters
    centroid_threshold_features: int = 10000

    # Buffer settings
    simplify_before_buffer: bool = True
    reduce_buffer_segments: bool = False
    buffer_segments_value: int = 3

    # Backend settings
    postgresql_use_mv: bool = True
    postgresql_use_indices: bool = True
    spatialite_use_rtree: bool = True
    ogr_use_bbox: bool = True

    # Advanced settings
    cache_enabled: bool = True
    batch_size: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'enabled': self.enabled,
            'ask_before_apply': self.ask_before_apply,
            'auto_centroid': {
                'enabled': self.auto_centroid_enabled,
                'distant_threshold': self.centroid_threshold_distant,
                'feature_threshold': self.centroid_threshold_features
            },
            'buffer': {
                'simplify_before': self.simplify_before_buffer,
                'reduce_segments': self.reduce_buffer_segments,
                'segments_value': self.buffer_segments_value
            },
            'backends': {
                'postgresql': {
                    'use_materialized_views': self.postgresql_use_mv,
                    'use_indices': self.postgresql_use_indices
                },
                'spatialite': {
                    'use_rtree': self.spatialite_use_rtree
                },
                'ogr': {
                    'use_bbox': self.ogr_use_bbox
                }
            },
            'advanced': {
                'cache_enabled': self.cache_enabled,
                'batch_size': self.batch_size
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationSettings":
        """Create from dictionary."""
        settings = cls()

        settings.enabled = data.get('enabled', True)
        settings.ask_before_apply = data.get('ask_before_apply', True)

        auto_centroid = data.get('auto_centroid', {})
        settings.auto_centroid_enabled = auto_centroid.get('enabled', True)
        settings.centroid_threshold_distant = auto_centroid.get('distant_threshold', 5000)
        settings.centroid_threshold_features = auto_centroid.get('feature_threshold', 10000)

        buffer = data.get('buffer', {})
        settings.simplify_before_buffer = buffer.get('simplify_before', True)
        settings.reduce_buffer_segments = buffer.get('reduce_segments', False)
        settings.buffer_segments_value = buffer.get('segments_value', 3)

        backends = data.get('backends', {})
        pg = backends.get('postgresql', {})
        settings.postgresql_use_mv = pg.get('use_materialized_views', True)
        settings.postgresql_use_indices = pg.get('use_indices', True)

        sl = backends.get('spatialite', {})
        settings.spatialite_use_rtree = sl.get('use_rtree', True)

        ogr = backends.get('ogr', {})
        settings.ogr_use_bbox = ogr.get('use_bbox', True)

        advanced = data.get('advanced', {})
        settings.cache_enabled = advanced.get('cache_enabled', True)
        settings.batch_size = advanced.get('batch_size', 1000)

        return settings


@dataclass
class OptimizationRecommendation:
    """A single optimization recommendation."""
    type: OptimizationType
    title: str
    description: str
    impact: str  # "high", "medium", "low"
    enabled: bool = True
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'type': self.type.name,
            'title': self.title,
            'description': self.description,
            'impact': self.impact,
            'enabled': self.enabled,
            'details': self.details
        }


class OptimizationDialog(QDialog):
    """
    Unified dialog for optimization settings.

    Provides:
    - Tabbed interface (General, Backends, Advanced)
    - Per-backend configuration
    - Threshold settings
    - Preview of current settings

    Emits:
    - settings_changed: When settings are modified
    - settings_saved: When dialog is accepted
    """

    settings_changed = pyqtSignal(dict)
    settings_saved = pyqtSignal(dict)

    def __init__(
        self,
        settings: Optional[OptimizationSettings] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize OptimizationDialog.

        Args:
            settings: Initial settings (defaults if None)
            parent: Parent widget
        """
        super().__init__(parent)

        self._settings = settings or OptimizationSettings()
        self._widgets: Dict[str, QWidget] = {}

        self.setWindowTitle(self.tr("Optimization Settings"))
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self.setModal(True)

        self._setup_ui()
        self._load_settings()

    def tr(self, text: str) -> str:
        """Translate text."""
        try:
            from qgis.PyQt.QtCore import QCoreApplication
            return QCoreApplication.translate("OptimizationDialog", text)
        except ImportError:
            return text

    # ─────────────────────────────────────────────────────────────────
    # UI Setup
    # ─────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("⚡ " + self.tr("Configure Optimization Settings"))
        header.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Create tabs
        self._create_general_tab()
        self._create_backends_tab()
        self._create_advanced_tab()

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore_defaults)

        layout.addWidget(button_box)

    def _create_general_tab(self):
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Enable optimization
        self._widgets['enabled'] = QCheckBox(self.tr("Enable automatic optimizations"))
        layout.addWidget(self._widgets['enabled'])

        # Ask before apply
        self._widgets['ask_before'] = QCheckBox(self.tr("Ask before applying optimizations"))
        layout.addWidget(self._widgets['ask_before'])

        # Auto-centroid group
        centroid_group = QGroupBox(self.tr("Auto-Centroid Settings"))
        centroid_layout = QVBoxLayout(centroid_group)

        self._widgets['auto_centroid'] = QCheckBox(self.tr("Enable auto-centroid for distant layers"))
        centroid_layout.addWidget(self._widgets['auto_centroid'])

        threshold_layout = QGridLayout()

        threshold_layout.addWidget(QLabel(self.tr("Distance threshold (km):")), 0, 0)
        self._widgets['centroid_threshold'] = QSpinBox()
        self._widgets['centroid_threshold'].setRange(100, 50000)
        self._widgets['centroid_threshold'].setSingleStep(500)
        self._widgets['centroid_threshold'].setSuffix(" km")
        threshold_layout.addWidget(self._widgets['centroid_threshold'], 0, 1)

        threshold_layout.addWidget(QLabel(self.tr("Feature threshold:")), 1, 0)
        self._widgets['feature_threshold'] = QSpinBox()
        self._widgets['feature_threshold'].setRange(1000, 1000000)
        self._widgets['feature_threshold'].setSingleStep(1000)
        threshold_layout.addWidget(self._widgets['feature_threshold'], 1, 1)

        centroid_layout.addLayout(threshold_layout)
        layout.addWidget(centroid_group)

        # Buffer optimization group
        buffer_group = QGroupBox(self.tr("Buffer Optimizations"))
        buffer_layout = QVBoxLayout(buffer_group)

        self._widgets['simplify_buffer'] = QCheckBox(self.tr("Simplify geometry before buffer"))
        buffer_layout.addWidget(self._widgets['simplify_buffer'])

        segments_layout = QHBoxLayout()
        self._widgets['reduce_segments'] = QCheckBox(self.tr("Reduce buffer segments to:"))
        segments_layout.addWidget(self._widgets['reduce_segments'])

        self._widgets['segments_value'] = QSpinBox()
        self._widgets['segments_value'].setRange(1, 16)
        self._widgets['segments_value'].setValue(3)
        segments_layout.addWidget(self._widgets['segments_value'])
        segments_layout.addStretch()

        buffer_layout.addLayout(segments_layout)
        layout.addWidget(buffer_group)

        layout.addStretch()

        self._tabs.addTab(widget, "🔧 " + self.tr("General"))

    def _create_backends_tab(self):
        """Create the Backend settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # PostgreSQL group
        pg_group = QGroupBox("🐘 PostgreSQL")
        pg_layout = QVBoxLayout(pg_group)

        self._widgets['pg_mv'] = QCheckBox(self.tr("Use materialized views for filtering"))
        pg_layout.addWidget(self._widgets['pg_mv'])

        self._widgets['pg_indices'] = QCheckBox(self.tr("Create spatial indices automatically"))
        pg_layout.addWidget(self._widgets['pg_indices'])

        layout.addWidget(pg_group)

        # Spatialite group
        sl_group = QGroupBox("💾 Spatialite")
        sl_layout = QVBoxLayout(sl_group)

        self._widgets['sl_rtree'] = QCheckBox(self.tr("Use R-tree spatial index"))
        sl_layout.addWidget(self._widgets['sl_rtree'])

        layout.addWidget(sl_group)

        # OGR group
        ogr_group = QGroupBox("📁 OGR (Shapefiles, GeoPackage)")
        ogr_layout = QVBoxLayout(ogr_group)

        self._widgets['ogr_bbox'] = QCheckBox(self.tr("Use bounding box pre-filter"))
        ogr_layout.addWidget(self._widgets['ogr_bbox'])

        layout.addWidget(ogr_group)

        layout.addStretch()

        self._tabs.addTab(widget, "🗄️ " + self.tr("Backends"))

    def _create_advanced_tab(self):
        """Create the Advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Cache settings
        cache_group = QGroupBox(self.tr("Caching"))
        cache_layout = QVBoxLayout(cache_group)

        self._widgets['cache_enabled'] = QCheckBox(self.tr("Enable geometry cache"))
        cache_layout.addWidget(self._widgets['cache_enabled'])

        layout.addWidget(cache_group)

        # Batch processing
        batch_group = QGroupBox(self.tr("Batch Processing"))
        batch_layout = QHBoxLayout(batch_group)

        batch_layout.addWidget(QLabel(self.tr("Batch size:")))
        self._widgets['batch_size'] = QSpinBox()
        self._widgets['batch_size'].setRange(100, 100000)
        self._widgets['batch_size'].setSingleStep(500)
        batch_layout.addWidget(self._widgets['batch_size'])
        batch_layout.addStretch()

        layout.addWidget(batch_group)

        # Info label
        info_label = QLabel(
            "<i>" + self.tr(
                "Advanced settings affect performance and memory usage. "
                "Change only if you understand the implications."
            ) + "</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888;")
        layout.addWidget(info_label)

        layout.addStretch()

        self._tabs.addTab(widget, "⚙️ " + self.tr("Advanced"))

    # ─────────────────────────────────────────────────────────────────
    # Settings Management
    # ─────────────────────────────────────────────────────────────────

    def _load_settings(self):
        """Load current settings into widgets."""
        s = self._settings

        # General
        self._widgets['enabled'].setChecked(s.enabled)
        self._widgets['ask_before'].setChecked(s.ask_before_apply)
        self._widgets['auto_centroid'].setChecked(s.auto_centroid_enabled)
        self._widgets['centroid_threshold'].setValue(s.centroid_threshold_distant // 1000)
        self._widgets['feature_threshold'].setValue(s.centroid_threshold_features)
        self._widgets['simplify_buffer'].setChecked(s.simplify_before_buffer)
        self._widgets['reduce_segments'].setChecked(s.reduce_buffer_segments)
        self._widgets['segments_value'].setValue(s.buffer_segments_value)

        # Backends
        self._widgets['pg_mv'].setChecked(s.postgresql_use_mv)
        self._widgets['pg_indices'].setChecked(s.postgresql_use_indices)
        self._widgets['sl_rtree'].setChecked(s.spatialite_use_rtree)
        self._widgets['ogr_bbox'].setChecked(s.ogr_use_bbox)

        # Advanced
        self._widgets['cache_enabled'].setChecked(s.cache_enabled)
        self._widgets['batch_size'].setValue(s.batch_size)

    def _save_settings(self):
        """Save widget values to settings."""
        s = self._settings

        # General
        s.enabled = self._widgets['enabled'].isChecked()
        s.ask_before_apply = self._widgets['ask_before'].isChecked()
        s.auto_centroid_enabled = self._widgets['auto_centroid'].isChecked()
        s.centroid_threshold_distant = self._widgets['centroid_threshold'].value() * 1000
        s.centroid_threshold_features = self._widgets['feature_threshold'].value()
        s.simplify_before_buffer = self._widgets['simplify_buffer'].isChecked()
        s.reduce_buffer_segments = self._widgets['reduce_segments'].isChecked()
        s.buffer_segments_value = self._widgets['segments_value'].value()

        # Backends
        s.postgresql_use_mv = self._widgets['pg_mv'].isChecked()
        s.postgresql_use_indices = self._widgets['pg_indices'].isChecked()
        s.spatialite_use_rtree = self._widgets['sl_rtree'].isChecked()
        s.ogr_use_bbox = self._widgets['ogr_bbox'].isChecked()

        # Advanced
        s.cache_enabled = self._widgets['cache_enabled'].isChecked()
        s.batch_size = self._widgets['batch_size'].value()

    def _restore_defaults(self):
        """Restore default settings."""
        self._settings = OptimizationSettings()
        self._load_settings()

    def _on_accept(self):
        """Handle dialog acceptance."""
        self._save_settings()
        self.settings_saved.emit(self._settings.to_dict())
        self.accept()

    def get_settings(self) -> OptimizationSettings:
        """Get current settings."""
        self._save_settings()
        return self._settings

    def get_settings_dict(self) -> Dict[str, Any]:
        """Get settings as dictionary."""
        return self.get_settings().to_dict()


class RecommendationDialog(QDialog):
    """
    Dialog for showing and applying optimization recommendations.

    Provides:
    - List of recommended optimizations
    - Estimated impact for each
    - Select/deselect individual optimizations
    - Quick apply all or apply selected
    """

    optimizations_applied = pyqtSignal(dict)

    def __init__(
        self,
        layer_name: str,
        recommendations: List[OptimizationRecommendation],
        feature_count: int = 0,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize RecommendationDialog.

        Args:
            layer_name: Name of the layer
            recommendations: List of recommendations
            feature_count: Feature count for display
            parent: Parent widget
        """
        super().__init__(parent)

        self._layer_name = layer_name
        self._recommendations = recommendations
        self._feature_count = feature_count
        self._checkboxes: Dict[OptimizationType, QCheckBox] = {}

        self.setWindowTitle(self.tr("Apply Optimizations?"))
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()

    def tr(self, text: str) -> str:
        """Translate text."""
        try:
            from qgis.PyQt.QtCore import QCoreApplication
            return QCoreApplication.translate("RecommendationDialog", text)
        except ImportError:
            return text

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel("⚡ " + self.tr("Optimizations Available"))
        header.setStyleSheet("font-size: 13pt; font-weight: bold; color: #3498db;")
        layout.addWidget(header)

        # Layer info
        info = QLabel(f"{self._layer_name} • {self._feature_count:,} features")
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)

        # Recommendations list
        for rec in self._recommendations:
            frame = QFrame()
            frame.setStyleSheet(
                "QFrame { background: #f5f5f5; border-radius: 4px; padding: 8px; }"
            )
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(8, 8, 8, 8)

            # Checkbox with title
            cb = QCheckBox(rec.title)
            cb.setChecked(rec.enabled)
            cb.setStyleSheet("font-weight: bold;")
            frame_layout.addWidget(cb)

            self._checkboxes[rec.type] = cb

            # Description
            desc = QLabel(rec.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #666; margin-left: 20px;")
            frame_layout.addWidget(desc)

            # Impact badge
            impact_colors = {
                'high': '#27ae60',
                'medium': '#f39c12',
                'low': '#95a5a6'
            }
            impact_text = f"<span style='color: {impact_colors.get(rec.impact, '#888')}'>"
            impact_text += f"Impact: {rec.impact.upper()}</span>"
            impact_label = QLabel(impact_text)
            impact_label.setStyleSheet("margin-left: 20px;")
            frame_layout.addWidget(impact_label)

            layout.addWidget(frame)

        # Buttons
        button_layout = QHBoxLayout()

        skip_btn = QPushButton(self.tr("Skip"))
        skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(skip_btn)

        button_layout.addStretch()

        apply_btn = QPushButton(self.tr("Apply Selected"))
        apply_btn.setDefault(True)
        apply_btn.setStyleSheet(
            "QPushButton { background: #3498db; color: white; padding: 8px 16px; }"
        )
        apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_btn)

        layout.addLayout(button_layout)

    def _on_apply(self):
        """Handle apply button click."""
        selected = {}
        for opt_type, checkbox in self._checkboxes.items():
            selected[opt_type.name] = checkbox.isChecked()

        self.optimizations_applied.emit(selected)
        self.accept()

    def get_selected(self) -> Dict[str, bool]:
        """Get selected optimizations."""
        return {
            opt_type.name: cb.isChecked()
            for opt_type, cb in self._checkboxes.items()
        }
