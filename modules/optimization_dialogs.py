# -*- coding: utf-8 -*-
"""
Optimization Dialogs for FilterMate

Provides user-facing dialogs and UI components for:
- Displaying optimization recommendations
- Confirming automatic optimizations
- Configuring optimization settings

v2.7.0: Initial implementation
"""

from typing import Dict, List, Optional, Any
from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QScrollArea, QWidget, QFrame,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QComboBox
)
from qgis.PyQt.QtGui import QFont, QColor, QIcon

import logging

logger = logging.getLogger('FilterMate')


class OptimizationRecommendationDialog(QDialog):
    """
    Dialog showing optimization recommendations before applying filters.
    
    Allows user to:
    - See what optimizations are recommended
    - Accept/reject each optimization
    - Apply all or selected optimizations
    - Remember choices for future operations
    """
    
    # Signal emitted when user confirms with selected optimizations
    optimizationsAccepted = pyqtSignal(dict)  # {optimization_type: bool}
    
    def __init__(
        self,
        layer_name: str,
        recommendations: List[Dict],
        feature_count: int,
        location_type: str,
        parent=None
    ):
        """
        Initialize the optimization dialog.
        
        Args:
            layer_name: Name of the layer being filtered
            recommendations: List of optimization recommendation dicts
            feature_count: Number of features in layer
            location_type: Type of layer (remote_service, local_file, etc.)
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.layer_name = layer_name
        self.recommendations = recommendations
        self.feature_count = feature_count
        self.location_type = location_type
        self.selected_optimizations = {}
        
        self.setWindowTitle("FilterMate - Optimization Recommendations")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #3498db;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        
        title_label = QLabel("🔧 Optimization Recommendations")
        title_label.setStyleSheet("color: white; font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # Layer info
        location_emoji = {
            'remote_service': '☁️ Remote Service',
            'remote_database': '🌐 Remote Database',
            'local_database': '🗄️ Local Database',
            'local_file': '📁 Local File'
        }
        location_text = location_emoji.get(self.location_type, self.location_type)
        
        info_label = QLabel(
            f"Layer: <b>{self.layer_name}</b><br>"
            f"Features: <b>{self.feature_count:,}</b> | Type: <b>{location_text}</b>"
        )
        info_label.setStyleSheet("color: white; font-size: 10pt;")
        header_layout.addWidget(info_label)
        
        layout.addWidget(header_frame)
        
        # Recommendations section
        recs_group = QGroupBox("Recommended Optimizations")
        recs_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        recs_layout = QVBoxLayout(recs_group)
        
        self.checkboxes = {}
        
        for rec in self.recommendations:
            opt_type = rec.get('optimization_type', 'unknown')
            reason = rec.get('reason', '')
            speedup = rec.get('estimated_speedup', 1.0)
            auto_applicable = rec.get('auto_applicable', False)
            requires_consent = rec.get('requires_user_consent', False)
            
            # Create checkbox for each recommendation
            checkbox_text = self._get_optimization_display_text(opt_type, speedup)
            checkbox = QCheckBox(checkbox_text)
            checkbox.setChecked(auto_applicable and not requires_consent)
            checkbox.setToolTip(reason)
            
            # Style based on type
            if opt_type == 'use_centroid':
                checkbox.setStyleSheet("QCheckBox { color: #27ae60; font-weight: bold; }")
            elif requires_consent:
                checkbox.setStyleSheet("QCheckBox { color: #e67e22; }")
            
            self.checkboxes[opt_type] = checkbox
            recs_layout.addWidget(checkbox)
            
            # Add explanation label
            explanation = QLabel(f"   ℹ️ {reason}")
            explanation.setStyleSheet("color: #666666; font-size: 9pt; margin-left: 20px;")
            explanation.setWordWrap(True)
            recs_layout.addWidget(explanation)
        
        layout.addWidget(recs_group)
        
        # Estimated improvement
        total_speedup = 1.0
        for rec in self.recommendations:
            if rec.get('auto_applicable', False):
                total_speedup *= rec.get('estimated_speedup', 1.0)
        
        if total_speedup > 1.1:
            speedup_label = QLabel(f"🚀 Estimated total speedup: <b>~{total_speedup:.1f}x faster</b>")
            speedup_label.setStyleSheet("color: #27ae60; font-size: 11pt;")
            speedup_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(speedup_label)
        
        # Remember choice checkbox
        self.remember_checkbox = QCheckBox("Remember my choices for this session")
        self.remember_checkbox.setToolTip(
            "If checked, these optimization choices will be applied automatically\n"
            "to similar layers without asking again during this session."
        )
        layout.addWidget(self.remember_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        skip_btn = QPushButton("Skip Optimizations")
        skip_btn.setToolTip("Continue without applying any optimizations")
        skip_btn.clicked.connect(self._on_skip)
        button_layout.addWidget(skip_btn)
        
        button_layout.addStretch()
        
        apply_btn = QPushButton("Apply Selected")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        apply_btn.setToolTip("Apply selected optimizations and continue")
        apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
    
    def _get_optimization_display_text(self, opt_type: str, speedup: float) -> str:
        """Get human-readable text for optimization type."""
        opt_names = {
            'use_centroid': f"🎯 Use Centroids (~{speedup:.1f}x faster)",
            'simplify_geometry': f"📐 Simplify Geometries (~{speedup:.1f}x faster) ⚠️",
            'bbox_prefilter': f"📦 BBox Pre-filtering (~{speedup:.1f}x faster)",
            'attribute_first': f"🔤 Attribute-First Strategy (~{speedup:.1f}x faster)",
            'progressive_chunks': f"📊 Progressive Chunking (~{speedup:.1f}x faster)",
        }
        return opt_names.get(opt_type, f"⚙️ {opt_type} (~{speedup:.1f}x faster)")
    
    def _on_skip(self):
        """Handle skip button - reject all optimizations."""
        self.selected_optimizations = {opt: False for opt in self.checkboxes}
        self.reject()
    
    def _on_apply(self):
        """Handle apply button - collect selected optimizations."""
        self.selected_optimizations = {
            opt_type: checkbox.isChecked()
            for opt_type, checkbox in self.checkboxes.items()
        }
        self.optimizationsAccepted.emit(self.selected_optimizations)
        self.accept()
    
    def get_selected_optimizations(self) -> Dict[str, bool]:
        """Get the user's optimization selections."""
        return self.selected_optimizations
    
    def should_remember(self) -> bool:
        """Check if user wants to remember choices."""
        return self.remember_checkbox.isChecked()


class OptimizationSettingsWidget(QWidget):
    """
    Widget for configuring auto-optimization settings.
    Can be embedded in the configuration tab or shown as a dialog.
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Set up the settings UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🔧 Auto-Optimization Settings")
        title.setStyleSheet("font-size: 12pt; font-weight: bold;")
        layout.addWidget(title)
        
        # Master switch
        self.enabled_checkbox = QCheckBox("Enable automatic optimization recommendations")
        self.enabled_checkbox.setToolTip(
            "When enabled, FilterMate will analyze layers and suggest\n"
            "performance optimizations before filtering."
        )
        self.enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self.enabled_checkbox)
        
        # Settings group (disabled when master switch is off)
        self.settings_group = QGroupBox("Optimization Options")
        settings_layout = QVBoxLayout(self.settings_group)
        
        # Centroid optimization
        centroid_layout = QHBoxLayout()
        self.centroid_checkbox = QCheckBox("Auto-enable centroids for distant layers")
        self.centroid_checkbox.setToolTip(
            "Automatically use ST_Centroid() for WFS, ArcGIS, and remote PostgreSQL layers.\n"
            "This dramatically reduces network data transfer (~90% reduction)."
        )
        centroid_layout.addWidget(self.centroid_checkbox)
        
        centroid_layout.addWidget(QLabel("Threshold:"))
        self.centroid_threshold = QSpinBox()
        self.centroid_threshold.setRange(100, 1000000)
        self.centroid_threshold.setSingleStep(1000)
        self.centroid_threshold.setSuffix(" features")
        self.centroid_threshold.setToolTip("Feature count above which centroid optimization is suggested")
        centroid_layout.addWidget(self.centroid_threshold)
        centroid_layout.addStretch()
        
        settings_layout.addLayout(centroid_layout)
        
        # Strategy selection
        self.strategy_checkbox = QCheckBox("Auto-select optimal filtering strategy")
        self.strategy_checkbox.setToolTip(
            "Automatically choose between attribute-first, bbox-prefilter,\n"
            "or progressive chunking based on dataset characteristics."
        )
        settings_layout.addWidget(self.strategy_checkbox)
        
        # Geometry simplification (with warning)
        simplify_layout = QHBoxLayout()
        self.simplify_checkbox = QCheckBox("Auto-simplify complex geometries")
        self.simplify_checkbox.setStyleSheet("color: #e67e22;")
        self.simplify_checkbox.setToolTip(
            "⚠️ WARNING: This is a LOSSY operation!\n"
            "Geometry simplification reduces vertex count but may change\n"
            "the shape of polygons. Only enable if precision is not critical."
        )
        simplify_layout.addWidget(self.simplify_checkbox)
        
        warning_label = QLabel("⚠️ Lossy")
        warning_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        simplify_layout.addWidget(warning_label)
        simplify_layout.addStretch()
        
        settings_layout.addWidget(QWidget())  # Spacer
        settings_layout.addLayout(simplify_layout)
        
        # Confirmation behavior
        settings_layout.addWidget(QLabel(""))  # Spacer
        self.ask_before_checkbox = QCheckBox("Always ask before applying optimizations")
        self.ask_before_checkbox.setToolTip(
            "When enabled, shows a confirmation dialog before applying\n"
            "any automatic optimization. Recommended for first-time users."
        )
        settings_layout.addWidget(self.ask_before_checkbox)
        
        self.show_hints_checkbox = QCheckBox("Show optimization hints in message bar")
        self.show_hints_checkbox.setToolTip(
            "Display helpful hints about available optimizations\n"
            "in the QGIS message bar."
        )
        settings_layout.addWidget(self.show_hints_checkbox)
        
        layout.addWidget(self.settings_group)
        
        # Apply button (for dialog mode)
        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setVisible(False)  # Hidden by default, shown in dialog mode
        layout.addWidget(self.apply_btn)
        
        layout.addStretch()
    
    def _on_enabled_changed(self, state):
        """Handle master switch state change."""
        self.settings_group.setEnabled(state == Qt.Checked)
    
    def _load_settings(self):
        """Load current settings from config."""
        try:
            from .backends.auto_optimizer import get_auto_optimization_config
            config = get_auto_optimization_config()
            
            self.enabled_checkbox.setChecked(config.get('enabled', True))
            self.centroid_checkbox.setChecked(config.get('auto_centroid_for_distant', True))
            self.centroid_threshold.setValue(config.get('centroid_threshold_distant', 5000))
            self.strategy_checkbox.setChecked(config.get('auto_strategy_selection', True))
            self.simplify_checkbox.setChecked(config.get('auto_simplify_geometry', False))
            self.show_hints_checkbox.setChecked(config.get('show_optimization_hints', True))
            
            # Ask before is not in config by default, default to True
            self.ask_before_checkbox.setChecked(True)
            
            self.settings_group.setEnabled(self.enabled_checkbox.isChecked())
            
        except Exception as e:
            logger.warning(f"Could not load optimization settings: {e}")
            # Set defaults
            self.enabled_checkbox.setChecked(True)
            self.centroid_checkbox.setChecked(True)
            self.centroid_threshold.setValue(5000)
            self.strategy_checkbox.setChecked(True)
            self.simplify_checkbox.setChecked(False)
            self.show_hints_checkbox.setChecked(True)
            self.ask_before_checkbox.setChecked(True)
    
    def _on_apply(self):
        """Apply settings and emit signal."""
        settings = self.get_settings()
        self.settingsChanged.emit(settings)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dictionary."""
        return {
            'enabled': self.enabled_checkbox.isChecked(),
            'auto_centroid_for_distant': self.centroid_checkbox.isChecked(),
            'centroid_threshold_distant': self.centroid_threshold.value(),
            'auto_strategy_selection': self.strategy_checkbox.isChecked(),
            'auto_simplify_geometry': self.simplify_checkbox.isChecked(),
            'show_optimization_hints': self.show_hints_checkbox.isChecked(),
            'ask_before_apply': self.ask_before_checkbox.isChecked(),
        }
    
    def set_dialog_mode(self, is_dialog: bool = True):
        """Set whether this widget is shown in a dialog (show apply button)."""
        self.apply_btn.setVisible(is_dialog)


class OptimizationSettingsDialog(QDialog):
    """Dialog wrapper for OptimizationSettingsWidget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FilterMate - Optimization Settings")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        self.settings_widget = OptimizationSettingsWidget(self)
        self.settings_widget.set_dialog_mode(False)  # We'll use dialog buttons
        layout.addWidget(self.settings_widget)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get settings from the widget."""
        return self.settings_widget.get_settings()


def show_optimization_recommendations(
    layer_name: str,
    recommendations: List[Dict],
    feature_count: int,
    location_type: str,
    parent=None
) -> Optional[Dict[str, bool]]:
    """
    Show optimization recommendations dialog and return user's choices.
    
    Args:
        layer_name: Name of the layer
        recommendations: List of recommendation dicts from AutoOptimizer
        feature_count: Number of features
        location_type: Layer location type
        parent: Parent widget
        
    Returns:
        Dictionary of {optimization_type: bool} or None if dialog was cancelled
    """
    if not recommendations:
        return {}
    
    dialog = OptimizationRecommendationDialog(
        layer_name=layer_name,
        recommendations=recommendations,
        feature_count=feature_count,
        location_type=location_type,
        parent=parent
    )
    
    result = dialog.exec_()
    
    if result == QDialog.Accepted:
        return dialog.get_selected_optimizations()
    return None


def show_optimization_hint(layer_name: str, optimization_type: str, speedup: float):
    """
    Show a quick optimization hint in the QGIS message bar.
    
    Args:
        layer_name: Name of the layer
        optimization_type: Type of optimization available
        speedup: Estimated speedup factor
    """
    from qgis.utils import iface
    
    opt_descriptions = {
        'use_centroid': f"Using centroids for '{layer_name}' could be ~{speedup:.1f}x faster",
        'progressive_chunks': f"Large dataset '{layer_name}' - using progressive chunking",
        'bbox_prefilter': f"BBox pre-filtering enabled for '{layer_name}'",
    }
    
    message = opt_descriptions.get(
        optimization_type,
        f"Optimization available for '{layer_name}' (~{speedup:.1f}x speedup)"
    )
    
    iface.messageBar().pushInfo("FilterMate Optimization", message)
