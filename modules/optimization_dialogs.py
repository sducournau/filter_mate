# -*- coding: utf-8 -*-
"""
Optimization Dialogs for FilterMate

Provides user-facing dialogs and UI components for:
- Displaying optimization recommendations
- Confirming automatic optimizations
- Configuring optimization settings

v2.7.0: Initial implementation
v2.4.0: Simplified UI - cleaner design, fewer options
"""

from typing import Dict, List, Optional, Any
from qgis.PyQt.QtCore import Qt, pyqtSignal, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QWidget, QFrame, QDialogButtonBox
)

import logging

logger = logging.getLogger('FilterMate')


def tr(text: str) -> str:
    """Translate a string using QCoreApplication."""
    return QCoreApplication.translate("OptimizationDialogs", text)


class OptimizationRecommendationDialog(QDialog):
    """
    Simplified dialog showing optimization recommendations.
    
    Allows user to:
    - See what optimizations are recommended
    - Accept/reject each optimization
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
        
        self.setWindowTitle(tr("FilterMate - Optimizations"))
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the simplified dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Simple header with layer info
        header_label = QLabel(
            f"<b>🔧 {tr('Optimizations for:')}</b> {self.layer_name}<br>"
            f"<small>{self.feature_count:,} {tr('features')}</small>"
        )
        header_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(header_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #ddd;")
        layout.addWidget(separator)
        
        # Calculate total speedup
        total_speedup = 1.0
        for rec in self.recommendations:
            if rec.get('auto_applicable', False):
                total_speedup *= rec.get('estimated_speedup', 1.0)
        
        # Simple message with total speedup
        if total_speedup > 1.1:
            speedup_text = tr("Estimated speedup:")
            faster_text = tr("faster")
            speedup_label = QLabel(
                f"🚀 {speedup_text} <b>~{total_speedup:.1f}x {faster_text}</b>"
            )
            speedup_label.setStyleSheet(
                "color: #27ae60; font-size: 10pt; margin: 5px 0;"
            )
            layout.addWidget(speedup_label)
        
        # Checkboxes for each optimization (simplified)
        self.checkboxes = {}
        
        for rec in self.recommendations:
            opt_type = rec.get('optimization_type', 'unknown')
            speedup = rec.get('estimated_speedup', 1.0)
            auto_applicable = rec.get('auto_applicable', False)
            requires_consent = rec.get('requires_user_consent', False)
            reason = rec.get('reason', '')
            
            # Create checkbox with simplified text
            checkbox_text = self._get_optimization_display_text(opt_type, speedup)
            checkbox = QCheckBox(checkbox_text)
            checkbox.setChecked(auto_applicable and not requires_consent)
            checkbox.setToolTip(reason)
            
            # Subtle styling for warnings
            if requires_consent:
                checkbox.setStyleSheet("QCheckBox { color: #e67e22; }")
            
            self.checkboxes[opt_type] = checkbox
            layout.addWidget(checkbox)
        
        layout.addStretch()
        
        # Remember choice checkbox
        self.remember_checkbox = QCheckBox(tr("Remember for this session"))
        self.remember_checkbox.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(self.remember_checkbox)
        
        # Buttons - simplified
        button_layout = QHBoxLayout()
        
        skip_btn = QPushButton(tr("Skip"))
        skip_btn.clicked.connect(self._on_skip)
        button_layout.addWidget(skip_btn)
        
        button_layout.addStretch()
        
        apply_btn = QPushButton(tr("Apply"))
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 6px 24px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
    
    def _get_optimization_display_text(self, opt_type: str, speedup: float) -> str:
        """Get human-readable text for optimization type."""
        faster = tr("faster")
        opt_names = {
            'use_centroid': f"{tr('Use centroids')} ({speedup:.0f}x {faster})",
            'simplify_geometry': f"{tr('Simplify geometries')} ({speedup:.0f}x {faster}) ⚠️",
            'bbox_prefilter': f"{tr('BBox pre-filtering')} ({speedup:.0f}x {faster})",
            'attribute_first': f"{tr('Attribute-first strategy')} ({speedup:.0f}x {faster})",
        }
        return opt_names.get(opt_type, f"{opt_type} ({speedup:.0f}x {faster})")
    
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
    Simplified widget for configuring auto-optimization settings.
    Can be embedded in the configuration tab or shown as a dialog.
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Set up the simplified settings UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title
        title = QLabel(f"🔧 {tr('Optimization Settings')}")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        layout.addWidget(title)
        
        # Master switch
        self.enabled_checkbox = QCheckBox(tr("Enable optimizations"))
        self.enabled_checkbox.setToolTip(
            tr("Suggest performance optimizations before filtering")
        )
        self.enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self.enabled_checkbox)
        
        # Settings group (disabled when master switch is off)
        self.settings_group = QWidget()
        settings_layout = QVBoxLayout(self.settings_group)
        settings_layout.setContentsMargins(20, 5, 0, 0)
        settings_layout.setSpacing(6)
        
        # Centroid optimization
        self.centroid_checkbox = QCheckBox(
            tr("Auto-use centroids for remote layers")
        )
        self.centroid_checkbox.setToolTip(
            tr("Use centroids to reduce network transfer (~90% faster)")
        )
        settings_layout.addWidget(self.centroid_checkbox)
        
        # Strategy selection
        self.strategy_checkbox = QCheckBox(tr("Auto-select best strategy"))
        self.strategy_checkbox.setToolTip(
            tr("Automatically choose optimal filtering strategy")
        )
        settings_layout.addWidget(self.strategy_checkbox)
        
        # Geometry simplification (with warning)
        self.simplify_checkbox = QCheckBox(
            f"{tr('Auto-simplify geometries')} ⚠️"
        )
        self.simplify_checkbox.setStyleSheet("color: #e67e22;")
        self.simplify_checkbox.setToolTip(
            tr("Warning: lossy operation, may change polygon shapes")
        )
        settings_layout.addWidget(self.simplify_checkbox)
        
        # Ask before applying
        self.ask_before_checkbox = QCheckBox(tr("Ask before applying"))
        self.ask_before_checkbox.setToolTip(
            tr("Show confirmation dialog before optimizations")
        )
        settings_layout.addWidget(self.ask_before_checkbox)
        
        layout.addWidget(self.settings_group)
        
        # Apply button (for dialog mode)
        self.apply_btn = QPushButton(tr("Apply"))
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
            self.strategy_checkbox.setChecked(config.get('auto_strategy_selection', True))
            self.simplify_checkbox.setChecked(config.get('auto_simplify_geometry', False))
            self.ask_before_checkbox.setChecked(config.get('ask_before_apply', True))
            
            self.settings_group.setEnabled(self.enabled_checkbox.isChecked())
            
        except Exception as e:
            logger.warning(f"Could not load optimization settings: {e}")
            # Set defaults
            self.enabled_checkbox.setChecked(True)
            self.centroid_checkbox.setChecked(True)
            self.strategy_checkbox.setChecked(True)
            self.simplify_checkbox.setChecked(False)
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
            'auto_strategy_selection': self.strategy_checkbox.isChecked(),
            'auto_simplify_geometry': self.simplify_checkbox.isChecked(),
            'ask_before_apply': self.ask_before_checkbox.isChecked(),
        }
    
    def set_dialog_mode(self, is_dialog: bool = True):
        """Set whether this widget is shown in a dialog (show apply button)."""
        self.apply_btn.setVisible(is_dialog)


class OptimizationSettingsDialog(QDialog):
    """Simplified dialog wrapper for OptimizationSettingsWidget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("FilterMate - Optimizations"))
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        self.settings_widget = OptimizationSettingsWidget(self)
        self.settings_widget.set_dialog_mode(False)
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
    
    faster = tr("faster")
    opt_descriptions = {
        'use_centroid': tr("Centroids enabled for '{0}' (~{1}x {2})").format(
            layer_name, int(speedup), faster
        ),
        'bbox_prefilter': tr("BBox pre-filter enabled for '{0}'").format(layer_name),
    }
    
    message = opt_descriptions.get(
        optimization_type,
        tr("Optimization applied: '{0}' (~{1}x {2})").format(
            layer_name, int(speedup), faster
        )
    )
    
    iface.messageBar().pushInfo("FilterMate", message)
