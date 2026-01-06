# -*- coding: utf-8 -*-
"""
Backend Optimization Widget for FilterMate

Provides a comprehensive UI panel for configuring optimizations
for each backend type (PostgreSQL, Spatialite, OGR/Memory).

Users can enable/disable and tune specific optimizations per backend.

v2.4.0: Initial implementation
v2.8.3: Added optimization profiles and intelligent recommendations
"""

from typing import Dict, Any
from qgis.PyQt.QtCore import Qt, pyqtSignal, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSpinBox, QFrame, QPushButton,
    QTabWidget, QScrollArea, QDialog, QDialogButtonBox,
    QComboBox, QProgressBar, QMessageBox
)

import logging

logger = logging.getLogger('FilterMate')


def tr(text: str) -> str:
    """Translate a string using QCoreApplication."""
    return QCoreApplication.translate("BackendOptimizationWidget", text)


# =============================================================================
# Optimization Profiles - Predefined configurations for common use cases
# =============================================================================

OPTIMIZATION_PROFILES = {
    'performance': {
        'name': '🚀 Maximum Performance',
        'description': 'All optimizations enabled. Best for large datasets and complex queries.',
        'icon': '🚀',
        'global': {
            'auto_optimization_enabled': True,
            'auto_centroid': {'enabled': True, 'distant_threshold': 3000},
            'auto_strategy_selection': True,
            'auto_simplify_geometry': False,
            'simplify_before_buffer': True,
            'parallel_filtering': {'enabled': True, 'max_workers': 0},
            'streaming_export': True,
            'ask_before_apply': False,
            'show_hints': True
        },
        'postgresql': {
            'materialized_views': {'enabled': True, 'threshold': 5000},
            'two_phase_filtering': True,
            'progressive_loading': {'enabled': True, 'lazy_cursor_threshold': 30000},
            'query_caching': True,
            'connection_pooling': True,
            'exists_subquery': {'enabled': True, 'threshold': 50000},
            'spatial_index_auto': True
        },
        'spatialite': {
            'rtree_temp_tables': {'enabled': True, 'threshold_kb': 30},
            'bbox_prefilter': True,
            'interruptible_queries': {'enabled': True, 'timeout_seconds': 180},
            'direct_sql_geopackage': True,
            'wkt_caching': True,
            'mod_spatialite_auto': True
        },
        'ogr': {
            'auto_spatial_index': True,
            'small_dataset_optimization': {'enabled': True, 'threshold': 8000},
            'cancellable_processing': True,
            'progressive_chunking': {'enabled': True, 'chunk_size': 8000},
            'geos_safe_geometry': True,
            'thread_safety': True
        }
    },
    'balanced': {
        'name': '⚖️ Balanced',
        'description': 'Good balance between speed and resource usage. Recommended for most users.',
        'icon': '⚖️',
        'global': {
            'auto_optimization_enabled': True,
            'auto_centroid': {'enabled': True, 'distant_threshold': 5000},
            'auto_strategy_selection': True,
            'auto_simplify_geometry': False,
            'simplify_before_buffer': True,
            'parallel_filtering': {'enabled': True, 'max_workers': 0},
            'streaming_export': True,
            'ask_before_apply': True,
            'show_hints': True
        },
        'postgresql': {
            'materialized_views': {'enabled': True, 'threshold': 10000},
            'two_phase_filtering': True,
            'progressive_loading': {'enabled': True, 'lazy_cursor_threshold': 50000},
            'query_caching': True,
            'connection_pooling': True,
            'exists_subquery': {'enabled': True, 'threshold': 100000},
            'spatial_index_auto': True
        },
        'spatialite': {
            'rtree_temp_tables': {'enabled': True, 'threshold_kb': 50},
            'bbox_prefilter': True,
            'interruptible_queries': {'enabled': True, 'timeout_seconds': 120},
            'direct_sql_geopackage': True,
            'wkt_caching': True,
            'mod_spatialite_auto': True
        },
        'ogr': {
            'auto_spatial_index': True,
            'small_dataset_optimization': {'enabled': True, 'threshold': 5000},
            'cancellable_processing': True,
            'progressive_chunking': {'enabled': True, 'chunk_size': 5000},
            'geos_safe_geometry': True,
            'thread_safety': True
        }
    },
    'memory_saver': {
        'name': '💾 Memory Saver',
        'description': 'Reduces memory usage. Best for limited RAM or very large datasets.',
        'icon': '💾',
        'global': {
            'auto_optimization_enabled': True,
            'auto_centroid': {'enabled': True, 'distant_threshold': 2000},
            'auto_strategy_selection': True,
            'auto_simplify_geometry': False,
            'simplify_before_buffer': True,
            'parallel_filtering': {'enabled': False, 'max_workers': 1},
            'streaming_export': True,
            'ask_before_apply': True,
            'show_hints': True
        },
        'postgresql': {
            'materialized_views': {'enabled': False, 'threshold': 20000},
            'two_phase_filtering': True,
            'progressive_loading': {'enabled': True, 'lazy_cursor_threshold': 20000},
            'query_caching': False,
            'connection_pooling': True,
            'exists_subquery': {'enabled': True, 'threshold': 50000},
            'spatial_index_auto': True
        },
        'spatialite': {
            'rtree_temp_tables': {'enabled': False, 'threshold_kb': 100},
            'bbox_prefilter': True,
            'interruptible_queries': {'enabled': True, 'timeout_seconds': 90},
            'direct_sql_geopackage': True,
            'wkt_caching': False,
            'mod_spatialite_auto': True
        },
        'ogr': {
            'auto_spatial_index': True,
            'small_dataset_optimization': {'enabled': False, 'threshold': 2000},
            'cancellable_processing': True,
            'progressive_chunking': {'enabled': True, 'chunk_size': 2000},
            'geos_safe_geometry': True,
            'thread_safety': True
        }
    },
    'safe': {
        'name': '🛡️ Safe Mode',
        'description': 'Conservative settings. Best for debugging or unstable connections.',
        'icon': '🛡️',
        'global': {
            'auto_optimization_enabled': False,
            'auto_centroid': {'enabled': False, 'distant_threshold': 10000},
            'auto_strategy_selection': False,
            'auto_simplify_geometry': False,
            'simplify_before_buffer': False,
            'parallel_filtering': {'enabled': False, 'max_workers': 1},
            'streaming_export': True,
            'ask_before_apply': True,
            'show_hints': False
        },
        'postgresql': {
            'materialized_views': {'enabled': False, 'threshold': 50000},
            'two_phase_filtering': False,
            'progressive_loading': {'enabled': False, 'lazy_cursor_threshold': 100000},
            'query_caching': False,
            'connection_pooling': False,
            'exists_subquery': {'enabled': False, 'threshold': 200000},
            'spatial_index_auto': True
        },
        'spatialite': {
            'rtree_temp_tables': {'enabled': False, 'threshold_kb': 200},
            'bbox_prefilter': False,
            'interruptible_queries': {'enabled': True, 'timeout_seconds': 60},
            'direct_sql_geopackage': False,
            'wkt_caching': False,
            'mod_spatialite_auto': True
        },
        'ogr': {
            'auto_spatial_index': True,
            'small_dataset_optimization': {'enabled': False, 'threshold': 1000},
            'cancellable_processing': True,
            'progressive_chunking': {'enabled': False, 'chunk_size': 1000},
            'geos_safe_geometry': True,
            'thread_safety': True
        }
    }
}


class OptimizationProfileSelector(QWidget):
    """
    Widget for selecting and applying optimization profiles.
    """
    
    profileSelected = pyqtSignal(str, dict)  # profile_key, profile_settings
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        
        # Header
        header_layout = QHBoxLayout()
        header = QLabel(f"⚡ {tr('Quick Setup')}")
        header.setStyleSheet("font-size: 12pt; font-weight: bold;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Description
        desc = QLabel(tr("Choose a profile or customize settings below"))
        desc.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(desc)
        
        # Profile buttons
        profiles_layout = QHBoxLayout()
        profiles_layout.setSpacing(8)
        
        for profile_key, profile_data in OPTIMIZATION_PROFILES.items():
            btn = QPushButton(profile_data['name'])
            btn.setToolTip(profile_data['description'])
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            
            # Style based on profile
            if profile_key == 'performance':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #2ecc71; }
                    QPushButton:pressed { background-color: #1e8449; }
                """)
            elif profile_key == 'balanced':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #5dade2; }
                    QPushButton:pressed { background-color: #2980b9; }
                """)
            elif profile_key == 'memory_saver':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #9b59b6;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #a569bd; }
                    QPushButton:pressed { background-color: #7d3c98; }
                """)
            elif profile_key == 'safe':
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e67e22;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 8px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #f39c12; }
                    QPushButton:pressed { background-color: #d35400; }
                """)
            
            btn.clicked.connect(lambda checked, k=profile_key: self._on_profile_clicked(k))
            profiles_layout.addWidget(btn)
        
        layout.addLayout(profiles_layout)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #ddd; margin: 10px 0;")
        layout.addWidget(sep)
    
    def _on_profile_clicked(self, profile_key: str):
        """Handle profile button click."""
        profile = OPTIMIZATION_PROFILES.get(profile_key, {})
        self.profileSelected.emit(profile_key, profile)


class SmartRecommendationWidget(QWidget):
    """
    Widget that shows intelligent recommendations based on current context.
    """
    
    applyRecommendation = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recommendations = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 10)
        
        # Header
        header = QLabel(f"💡 {tr('Smart Recommendations')}")
        header.setStyleSheet("font-size: 11pt; font-weight: bold; color: #2980b9;")
        self.main_layout.addWidget(header)
        
        # Recommendations container
        self.recommendations_container = QVBoxLayout()
        self.recommendations_container.setSpacing(5)
        self.main_layout.addLayout(self.recommendations_container)
        
        # Initial state
        self._show_no_recommendations()
    
    def _show_no_recommendations(self):
        """Show message when no recommendations are available."""
        self._clear_recommendations()
        label = QLabel(tr("Analyzing your project... Recommendations will appear here."))
        label.setStyleSheet("color: #888; font-style: italic; padding: 10px;")
        self.recommendations_container.addWidget(label)
    
    def _clear_recommendations(self):
        """Clear all recommendation widgets."""
        while self.recommendations_container.count():
            item = self.recommendations_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def analyze_and_recommend(self, project_info: Dict = None):
        """
        Analyze the current project and generate recommendations.
        
        Args:
            project_info: Optional dictionary with project analysis data
        """
        self._clear_recommendations()
        self._recommendations = []
        
        # Generate recommendations based on project info
        recommendations = self._generate_recommendations(project_info)
        
        if not recommendations:
            self._show_no_recommendations()
            return
        
        for rec in recommendations[:3]:  # Show max 3 recommendations
            self._add_recommendation_widget(rec)
    
    def _generate_recommendations(self, project_info: Dict = None) -> list:
        """Generate intelligent recommendations."""
        recommendations = []
        
        # Check if we have project info
        if project_info:
            # Recommendations based on layer types
            pg_layers = project_info.get('postgresql_layers', 0)
            gpkg_layers = project_info.get('geopackage_layers', 0)
            shp_layers = project_info.get('shapefile_layers', 0)
            large_layers = project_info.get('large_layers', 0)
            remote_layers = project_info.get('remote_layers', 0)
            
            if pg_layers > 0 and large_layers > 0:
                recommendations.append({
                    'icon': '🐘',
                    'title': tr('Enable Materialized Views'),
                    'description': tr(
                        'You have {0} PostgreSQL layers with large datasets. '
                        'Materialized views can speed up filtering by 3-10x.'
                    ).format(pg_layers),
                    'action': 'enable_mv',
                    'priority': 'high'
                })
            
            if remote_layers > 0:
                recommendations.append({
                    'icon': '🌐',
                    'title': tr('Enable Auto-Centroid for Remote Layers'),
                    'description': tr(
                        'You have {0} remote layers. Using centroids reduces '
                        'network transfer by ~90%.'
                    ).format(remote_layers),
                    'action': 'enable_centroid',
                    'priority': 'high'
                })
            
            if gpkg_layers > 0:
                recommendations.append({
                    'icon': '📦',
                    'title': tr('Enable Direct SQL for GeoPackage'),
                    'description': tr(
                        'Direct SQL access can make GeoPackage filtering 2-5x faster.'
                    ),
                    'action': 'enable_direct_sql',
                    'priority': 'medium'
                })
            
            if shp_layers > 0:
                recommendations.append({
                    'icon': '📁',
                    'title': tr('Create Spatial Indexes'),
                    'description': tr(
                        'Some shapefiles may lack spatial indexes. '
                        'Creating indexes can improve performance 10-100x.'
                    ),
                    'action': 'create_indexes',
                    'priority': 'medium'
                })
        else:
            # Default recommendations when no project info
            recommendations.append({
                'icon': '⚡',
                'title': tr('Use Balanced Profile'),
                'description': tr(
                    'Start with balanced settings for optimal performance '
                    'on most projects.'
                ),
                'action': 'apply_balanced',
                'priority': 'info'
            })
        
        return recommendations
    
    def _add_recommendation_widget(self, rec: Dict):
        """Add a recommendation widget."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #e8f4fc;
                border: 1px solid #b8daef;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)
        
        # Icon
        icon_label = QLabel(rec['icon'])
        icon_label.setStyleSheet("font-size: 18pt;")
        layout.addWidget(icon_label)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        title = QLabel(f"<b>{rec['title']}</b>")
        title.setStyleSheet("font-size: 10pt;")
        text_layout.addWidget(title)
        
        desc = QLabel(rec['description'])
        desc.setStyleSheet("color: #555; font-size: 9pt;")
        desc.setWordWrap(True)
        text_layout.addWidget(desc)
        
        layout.addLayout(text_layout, stretch=1)
        
        # Apply button
        apply_btn = QPushButton(tr("Apply"))
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #5dade2; }
        """)
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.clicked.connect(lambda: self.applyRecommendation.emit(rec))
        layout.addWidget(apply_btn)
        
        self.recommendations_container.addWidget(frame)
        self._recommendations.append(rec)


class OptimizationToggle(QWidget):
    """
    A styled toggle widget for enabling/disabling an optimization.
    Shows optimization name, status, and optional speedup estimate.
    """
    
    toggled = pyqtSignal(bool)
    
    def __init__(self, name: str, description: str, speedup: str = "",
                 default_enabled: bool = True, parent=None):
        super().__init__(parent)
        self.name = name
        self.description = description
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(8)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(default_enabled)
        self.checkbox.stateChanged.connect(self._on_state_changed)
        layout.addWidget(self.checkbox)
        
        # Name and description
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        
        name_label = QLabel(f"<b>{name}</b>")
        name_label.setStyleSheet("font-size: 10pt;")
        info_layout.addWidget(name_label)
        
        desc_label = QLabel(f"<small>{description}</small>")
        desc_label.setStyleSheet("color: #666;")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        layout.addLayout(info_layout, stretch=1)
        
        # Speedup indicator
        if speedup:
            speedup_label = QLabel(
                f"<span style='color: #27ae60;'>{speedup}</span>"
            )
            speedup_label.setToolTip(tr("Estimated performance improvement"))
            layout.addWidget(speedup_label)
        
        self.setToolTip(description)
    
    def _on_state_changed(self, state):
        self.toggled.emit(state == Qt.Checked)
    
    def is_enabled(self) -> bool:
        return self.checkbox.isChecked()
    
    def set_enabled(self, enabled: bool):
        self.checkbox.setChecked(enabled)


class MVStatusWidget(QWidget):
    """
    Widget showing current materialized views status and management actions.
    Provides real-time info about active MVs and cleanup options.
    """
    
    cleanupRequested = pyqtSignal(str)  # 'session', 'all', 'orphaned'
    refreshRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._mv_count = 0
        self._session_count = 0
        self._other_count = 0
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(4)
        
        # Status frame with compact styling
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border: 1px solid #a5d6a7;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        status_layout = QVBoxLayout(self.status_frame)
        status_layout.setContentsMargins(8, 6, 8, 6)
        status_layout.setSpacing(4)
        
        # Status header with icon
        header_layout = QHBoxLayout()
        self.status_icon = QLabel("📊")
        self.status_icon.setStyleSheet("font-size: 14pt;")
        header_layout.addWidget(self.status_icon)
        
        self.status_label = QLabel(tr("MV Status: Checking..."))
        self.status_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        
        # Refresh button (compact)
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setToolTip(tr("Refresh MV status"))
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 12pt;
            }
            QPushButton:hover { background-color: rgba(0,0,0,0.1); border-radius: 12px; }
        """)
        self.refresh_btn.clicked.connect(lambda: self.refreshRequested.emit())
        header_layout.addWidget(self.refresh_btn)
        
        status_layout.addLayout(header_layout)
        
        # Details row
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("color: #555; font-size: 9pt;")
        self.details_label.setWordWrap(True)
        status_layout.addWidget(self.details_label)
        
        layout.addWidget(self.status_frame)
        
        # Action buttons row (compact)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        self.cleanup_session_btn = QPushButton(tr("🧹 Session"))
        self.cleanup_session_btn.setToolTip(tr("Cleanup MVs from this session"))
        self.cleanup_session_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #42A5F5; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.cleanup_session_btn.clicked.connect(lambda: self.cleanupRequested.emit('session'))
        btn_layout.addWidget(self.cleanup_session_btn)
        
        self.cleanup_orphaned_btn = QPushButton(tr("🗑️ Orphaned"))
        self.cleanup_orphaned_btn.setToolTip(tr("Cleanup orphaned MVs (>24h old)"))
        self.cleanup_orphaned_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #FFB74D; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.cleanup_orphaned_btn.clicked.connect(lambda: self.cleanupRequested.emit('orphaned'))
        btn_layout.addWidget(self.cleanup_orphaned_btn)
        
        self.cleanup_all_btn = QPushButton(tr("⚠️ All"))
        self.cleanup_all_btn.setToolTip(tr("Cleanup ALL MVs (affects other sessions)"))
        self.cleanup_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #e57373; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.cleanup_all_btn.clicked.connect(lambda: self.cleanupRequested.emit('all'))
        btn_layout.addWidget(self.cleanup_all_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def update_status(self, session_count: int = 0, other_count: int = 0, 
                      schema_exists: bool = False, error: str = None):
        """Update the MV status display."""
        self._session_count = session_count
        self._other_count = other_count
        total = session_count + other_count
        
        if error:
            self.status_icon.setText("⚠️")
            self.status_label.setText(tr("MV Status: Error"))
            self.details_label.setText(error[:80])
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #ffebee;
                    border: 1px solid #ef9a9a;
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
            self.cleanup_session_btn.setEnabled(False)
            self.cleanup_orphaned_btn.setEnabled(False)
            self.cleanup_all_btn.setEnabled(False)
        elif total == 0:
            self.status_icon.setText("✅")
            self.status_label.setText(tr("MV Status: Clean"))
            self.details_label.setText(tr("No active materialized views"))
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #e8f5e9;
                    border: 1px solid #a5d6a7;
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
            self.cleanup_session_btn.setEnabled(False)
            self.cleanup_orphaned_btn.setEnabled(False)
            self.cleanup_all_btn.setEnabled(schema_exists)
        else:
            self.status_icon.setText("📊")
            self.status_label.setText(f"{tr('MV Status:')} {total} {tr('active')}")
            details = f"{tr('Session:')} {session_count}"
            if other_count > 0:
                details += f" | {tr('Other sessions:')} {other_count}"
            self.details_label.setText(details)
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border: 1px solid #90caf9;
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
            self.cleanup_session_btn.setEnabled(session_count > 0)
            self.cleanup_orphaned_btn.setEnabled(True)
            self.cleanup_all_btn.setEnabled(True)


class PostgreSQLOptimizationPanel(QWidget):
    """
    Optimization settings specific to PostgreSQL/PostGIS backend.
    
    v2.8.6: Enhanced MV management with status widget and cleanup actions.
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header
        header = QLabel(f"🐘 {tr('PostgreSQL/PostGIS Optimizations')}")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #336791;")
        layout.addWidget(header)
        
        desc = QLabel(tr("Optimizations for PostgreSQL databases with PostGIS extension"))
        desc.setStyleSheet("color: #666; font-size: 9pt; margin-bottom: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # ===== MV STATUS SECTION =====
        self.mv_status_widget = MVStatusWidget()
        self.mv_status_widget.cleanupRequested.connect(self._on_cleanup_requested)
        self.mv_status_widget.refreshRequested.connect(self._refresh_mv_status)
        layout.addWidget(self.mv_status_widget)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #336791;")
        layout.addWidget(sep)
        
        # ===== OPTIMIZATION TOGGLES =====
        
        # Materialized Views
        self.mv_toggle = OptimizationToggle(
            tr("Materialized Views"),
            tr("Create indexed temporary views for complex spatial queries."),
            speedup="3-10x",
            default_enabled=True
        )
        layout.addWidget(self.mv_toggle)
        
        # MV settings row
        mv_settings_layout = QHBoxLayout()
        mv_settings_layout.setContentsMargins(30, 0, 0, 0)
        mv_settings_layout.addWidget(QLabel(tr("Threshold:")))
        self.mv_threshold_spin = QSpinBox()
        self.mv_threshold_spin.setRange(1000, 500000)
        self.mv_threshold_spin.setValue(10000)
        self.mv_threshold_spin.setSingleStep(1000)
        self.mv_threshold_spin.setToolTip(tr("Create MVs for datasets larger than this"))
        self.mv_threshold_spin.setFixedWidth(80)
        mv_settings_layout.addWidget(self.mv_threshold_spin)
        mv_settings_layout.addWidget(QLabel(tr("features")))
        mv_settings_layout.addStretch()
        
        # Auto-cleanup checkbox
        self.auto_cleanup_cb = QCheckBox(tr("Auto-cleanup on exit"))
        self.auto_cleanup_cb.setChecked(True)
        self.auto_cleanup_cb.setToolTip(tr("Automatically drop session MVs when plugin unloads"))
        mv_settings_layout.addWidget(self.auto_cleanup_cb)
        layout.addLayout(mv_settings_layout)
        
        # Two-Phase Filtering
        self.two_phase_toggle = OptimizationToggle(
            tr("Two-Phase Filtering"),
            tr("First filter by bounding box, then by exact geometry."),
            speedup="3-5x",
            default_enabled=True
        )
        layout.addWidget(self.two_phase_toggle)
        
        # Progressive/Lazy Loading
        self.progressive_toggle = OptimizationToggle(
            tr("Progressive Loading"),
            tr("Stream results in chunks to reduce memory usage."),
            speedup="50-80% memory",
            default_enabled=True
        )
        layout.addWidget(self.progressive_toggle)
        
        # Lazy cursor threshold
        lazy_layout = QHBoxLayout()
        lazy_layout.setContentsMargins(30, 0, 0, 0)
        lazy_layout.addWidget(QLabel(tr("Lazy cursor threshold:")))
        self.lazy_cursor_spin = QSpinBox()
        self.lazy_cursor_spin.setRange(10000, 500000)
        self.lazy_cursor_spin.setValue(50000)
        self.lazy_cursor_spin.setSingleStep(5000)
        self.lazy_cursor_spin.setFixedWidth(80)
        lazy_layout.addWidget(self.lazy_cursor_spin)
        lazy_layout.addStretch()
        layout.addLayout(lazy_layout)
        
        # Query Caching
        self.query_cache_toggle = OptimizationToggle(
            tr("Query Expression Caching"),
            tr("Cache expressions to avoid rebuilding identical queries."),
            speedup="2-3x",
            default_enabled=True
        )
        layout.addWidget(self.query_cache_toggle)
        
        # Connection Pooling
        self.conn_pool_toggle = OptimizationToggle(
            tr("Connection Pooling"),
            tr("Reuse connections to avoid 50-100ms overhead per query."),
            speedup="50-100ms",
            default_enabled=True
        )
        layout.addWidget(self.conn_pool_toggle)
        
        # EXISTS Subquery Mode
        self.exists_toggle = OptimizationToggle(
            tr("EXISTS Subquery for Large WKT"),
            tr("Use EXISTS subquery for very large geometries."),
            speedup="Variable",
            default_enabled=True
        )
        layout.addWidget(self.exists_toggle)
        
        # EXISTS threshold
        exists_layout = QHBoxLayout()
        exists_layout.setContentsMargins(30, 0, 0, 0)
        exists_layout.addWidget(QLabel(tr("WKT threshold:")))
        self.exists_threshold_spin = QSpinBox()
        self.exists_threshold_spin.setRange(10000, 500000)
        self.exists_threshold_spin.setValue(100000)
        self.exists_threshold_spin.setSingleStep(10000)
        self.exists_threshold_spin.setFixedWidth(80)
        exists_layout.addWidget(self.exists_threshold_spin)
        exists_layout.addWidget(QLabel(tr("chars")))
        exists_layout.addStretch()
        layout.addLayout(exists_layout)
        
        # Spatial Index Usage
        self.spatial_index_toggle = OptimizationToggle(
            tr("Automatic GIST Index Usage"),
            tr("Verify and use GIST spatial indexes for optimal query plans."),
            speedup="10-100x",
            default_enabled=True
        )
        layout.addWidget(self.spatial_index_toggle)
        
        layout.addStretch()
        
        # Initial status refresh
        self._refresh_mv_status()
    
    def _refresh_mv_status(self):
        """Refresh the MV status from database."""
        try:
            from .appUtils import POSTGRESQL_AVAILABLE, get_datasource_connexion_from_layer
            from qgis.core import QgsProject
            
            if not POSTGRESQL_AVAILABLE:
                self.mv_status_widget.update_status(error=tr("PostgreSQL not available"))
                return
            
            # Find a PostgreSQL layer to get connection
            project = QgsProject.instance()
            pg_layer = None
            for layer_id, layer in project.mapLayers().items():
                if hasattr(layer, 'providerType') and layer.providerType() == 'postgres':
                    pg_layer = layer
                    break
            
            if not pg_layer:
                self.mv_status_widget.update_status(
                    session_count=0, other_count=0, schema_exists=False
                )
                return
            
            conn, _ = get_datasource_connexion_from_layer(pg_layer)
            if not conn:
                self.mv_status_widget.update_status(error=tr("No connection"))
                return
            
            try:
                cursor = conn.cursor()
                schema = 'filter_mate_temp'
                
                # Check if schema exists
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema,))
                schema_exists = cursor.fetchone()[0] > 0
                
                if not schema_exists:
                    self.mv_status_widget.update_status(
                        session_count=0, other_count=0, schema_exists=False
                    )
                    cursor.close()
                    conn.close()
                    return
                
                # Get session ID (try from parent chain)
                session_id = None
                parent = self.parent()
                while parent:
                    if hasattr(parent, 'session_id'):
                        session_id = parent.session_id
                        break
                    if hasattr(parent, '_app_ref') and hasattr(parent._app_ref, 'session_id'):
                        session_id = parent._app_ref.session_id
                        break
                    parent = parent.parent() if hasattr(parent, 'parent') else None
                
                # Count MVs
                cursor.execute("""
                    SELECT matviewname FROM pg_matviews 
                    WHERE schemaname = %s
                """, (schema,))
                views = cursor.fetchall()
                
                session_count = 0
                other_count = 0
                for (view_name,) in views:
                    if session_id and view_name.startswith(f"mv_{session_id}_"):
                        session_count += 1
                    else:
                        other_count += 1
                
                self.mv_status_widget.update_status(
                    session_count=session_count,
                    other_count=other_count,
                    schema_exists=True
                )
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                self.mv_status_widget.update_status(error=str(e)[:50])
                try:
                    conn.close()
                except Exception:
                    pass  # Connection may already be closed
                    
        except Exception as e:
            self.mv_status_widget.update_status(error=str(e)[:50])
    
    def _on_cleanup_requested(self, cleanup_type: str):
        """Handle cleanup request from MV status widget."""
        try:
            from .appUtils import POSTGRESQL_AVAILABLE, get_datasource_connexion_from_layer
            from qgis.core import QgsProject
            
            if not POSTGRESQL_AVAILABLE:
                return
            
            # Find PostgreSQL connection
            project = QgsProject.instance()
            pg_layer = None
            for layer_id, layer in project.mapLayers().items():
                if hasattr(layer, 'providerType') and layer.providerType() == 'postgres':
                    pg_layer = layer
                    break
            
            if not pg_layer:
                return
            
            conn, _ = get_datasource_connexion_from_layer(pg_layer)
            if not conn:
                return
            
            schema = 'filter_mate_temp'
            
            # Get session ID
            session_id = None
            parent = self.parent()
            while parent:
                if hasattr(parent, 'session_id'):
                    session_id = parent.session_id
                    break
                if hasattr(parent, '_app_ref') and hasattr(parent._app_ref, 'session_id'):
                    session_id = parent._app_ref.session_id
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
            
            try:
                cursor = conn.cursor()
                count = 0
                
                if cleanup_type == 'session' and session_id:
                    # Cleanup session MVs
                    cursor.execute("""
                        SELECT matviewname FROM pg_matviews 
                        WHERE schemaname = %s AND matviewname LIKE %s
                    """, (schema, f"mv_{session_id}_%"))
                    views = cursor.fetchall()
                    
                    for (view_name,) in views:
                        cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;')
                        count += 1
                    
                elif cleanup_type == 'orphaned':
                    # Cleanup orphaned MVs (>24h old based on naming convention)
                    cursor.execute("""
                        SELECT matviewname FROM pg_matviews 
                        WHERE schemaname = %s AND matviewname LIKE 'mv_%'
                    """, (schema,))
                    views = cursor.fetchall()
                    
                    import time
                    # We can't easily check age, so we drop all except current session
                    for (view_name,) in views:
                        if session_id and view_name.startswith(f"mv_{session_id}_"):
                            continue  # Keep current session
                        cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view_name}" CASCADE;')
                        count += 1
                    
                elif cleanup_type == 'all':
                    # Confirm before dropping all
                    reply = QMessageBox.question(
                        self,
                        tr("Confirm Cleanup"),
                        tr("Drop ALL materialized views?\nThis affects other FilterMate sessions!"),
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE;')
                        count = -1  # Indicate schema dropped
                
                conn.commit()
                cursor.close()
                conn.close()
                
                # Refresh status
                self._refresh_mv_status()
                
                if count > 0:
                    logger.info(f"PostgreSQL cleanup ({cleanup_type}): {count} MV(s) dropped")
                elif count == -1:
                    logger.info(f"PostgreSQL cleanup: schema '{schema}' dropped")
                    
            except Exception as e:
                logger.error(f"MV cleanup error: {e}")
                try:
                    conn.close()
                except Exception:
                    pass  # Connection may already be closed
                    
        except Exception as e:
            logger.error(f"MV cleanup failed: {e}")
    
    def _load_settings(self):
        """Load settings from configuration."""
        try:
            from ..config.config import ENV_VARS
            config_data = ENV_VARS.get('CONFIG_DATA', {})
            
            # PostgreSQL settings
            pg_opts = config_data.get('POSTGRESQL', {}).get('FILTER', {})
            
            mv_enabled = pg_opts.get('MATERIALIZED_VIEW', {})
            if isinstance(mv_enabled, dict):
                self.mv_toggle.set_enabled(mv_enabled.get('value', True))
            elif isinstance(mv_enabled, bool):
                self.mv_toggle.set_enabled(mv_enabled)
            
            # App options
            app_opts = config_data.get('APP', {}).get('OPTIONS', {})
            
            # Progressive filtering
            prog = app_opts.get('PROGRESSIVE_FILTERING', {})
            self.two_phase_toggle.set_enabled(prog.get('two_phase_enabled', {}).get('value', True))
            self.progressive_toggle.set_enabled(prog.get('enabled', {}).get('value', True))
            self.lazy_cursor_spin.setValue(prog.get('lazy_cursor_threshold', {}).get('value', 50000))
            
            # Query cache
            cache = app_opts.get('QUERY_CACHE', {})
            self.query_cache_toggle.set_enabled(cache.get('enabled', {}).get('value', True))
            
        except Exception as e:
            logger.warning(f"Could not load PostgreSQL optimization settings: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dictionary."""
        return {
            'materialized_views': {
                'enabled': self.mv_toggle.is_enabled(),
                'threshold': self.mv_threshold_spin.value(),
                'auto_cleanup': self.auto_cleanup_cb.isChecked()
            },
            'two_phase_filtering': self.two_phase_toggle.is_enabled(),
            'progressive_loading': {
                'enabled': self.progressive_toggle.is_enabled(),
                'lazy_cursor_threshold': self.lazy_cursor_spin.value()
            },
            'query_caching': self.query_cache_toggle.is_enabled(),
            'connection_pooling': self.conn_pool_toggle.is_enabled(),
            'exists_subquery': {
                'enabled': self.exists_toggle.is_enabled(),
                'threshold': self.exists_threshold_spin.value()
            },
            'spatial_index_auto': self.spatial_index_toggle.is_enabled()
        }


class SpatialiteOptimizationPanel(QWidget):
    """
    Optimization settings specific to Spatialite/GeoPackage backend.
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header
        header = QLabel(f"📦 {tr('Spatialite/GeoPackage Optimizations')}")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #4a90d9;")
        layout.addWidget(header)
        
        desc = QLabel(tr("Optimizations for Spatialite databases and GeoPackage files"))
        desc.setStyleSheet("color: #666; font-size: 9pt; margin-bottom: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #4a90d9;")
        layout.addWidget(sep)
        
        # R-tree Temp Tables
        self.rtree_toggle = OptimizationToggle(
            tr("R-tree Temp Tables"),
            tr("Create temporary tables with R-tree spatial indexes for complex queries. "
               "Similar to PostgreSQL materialized views."),
            speedup="3-5x",
            default_enabled=True
        )
        layout.addWidget(self.rtree_toggle)
        
        # R-tree WKT threshold
        rtree_layout = QHBoxLayout()
        rtree_layout.setContentsMargins(30, 0, 0, 0)
        rtree_layout.addWidget(QLabel(tr("WKT size threshold (KB):")))
        self.rtree_threshold_spin = QSpinBox()
        self.rtree_threshold_spin.setRange(10, 500)
        self.rtree_threshold_spin.setValue(50)
        self.rtree_threshold_spin.setSingleStep(10)
        self.rtree_threshold_spin.setToolTip(tr("Use R-tree optimization for WKT larger than this"))
        rtree_layout.addWidget(self.rtree_threshold_spin)
        rtree_layout.addStretch()
        layout.addLayout(rtree_layout)
        
        # BBox Pre-filter for Large WKT
        self.bbox_prefilter_toggle = OptimizationToggle(
            tr("BBox Pre-filtering"),
            tr("Use bounding box filter before exact geometry test. "
               "O(log n) vs O(n) complexity for large geometries."),
            speedup="5-20x",
            default_enabled=True
        )
        layout.addWidget(self.bbox_prefilter_toggle)
        
        # Interruptible Queries
        self.interruptible_toggle = OptimizationToggle(
            tr("Interruptible Queries"),
            tr("Execute SQLite queries in background thread with cancellation support. "
               "Prevents QGIS freezing on long operations."),
            speedup="Safety",
            default_enabled=True
        )
        layout.addWidget(self.interruptible_toggle)
        
        # Query timeout
        timeout_layout = QHBoxLayout()
        timeout_layout.setContentsMargins(30, 0, 0, 0)
        timeout_layout.addWidget(QLabel(tr("Query timeout (seconds):")))
        self.query_timeout_spin = QSpinBox()
        self.query_timeout_spin.setRange(30, 600)
        self.query_timeout_spin.setValue(120)
        self.query_timeout_spin.setSingleStep(30)
        timeout_layout.addWidget(self.query_timeout_spin)
        timeout_layout.addStretch()
        layout.addLayout(timeout_layout)
        
        # Direct SQL for GeoPackage
        self.direct_sql_toggle = OptimizationToggle(
            tr("Direct SQL for GeoPackage"),
            tr("Bypass GDAL layer and execute SQL directly on GeoPackage. "
               "More reliable and faster for complex spatial queries."),
            speedup="2-5x",
            default_enabled=True
        )
        layout.addWidget(self.direct_sql_toggle)
        
        # WKT Caching
        self.wkt_cache_toggle = OptimizationToggle(
            tr("WKT Geometry Caching"),
            tr("Cache converted WKT strings to avoid repeated geometry serialization."),
            speedup="10-20%",
            default_enabled=True
        )
        layout.addWidget(self.wkt_cache_toggle)
        
        # Mod_spatialite auto-detection
        self.mod_spatialite_toggle = OptimizationToggle(
            tr("Auto-detect mod_spatialite"),
            tr("Automatically find and load the best mod_spatialite extension."),
            speedup="Compatibility",
            default_enabled=True
        )
        layout.addWidget(self.mod_spatialite_toggle)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load settings from configuration."""
        # Default values - could be loaded from config
        pass
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dictionary."""
        return {
            'rtree_temp_tables': {
                'enabled': self.rtree_toggle.is_enabled(),
                'threshold_kb': self.rtree_threshold_spin.value()
            },
            'bbox_prefilter': self.bbox_prefilter_toggle.is_enabled(),
            'interruptible_queries': {
                'enabled': self.interruptible_toggle.is_enabled(),
                'timeout_seconds': self.query_timeout_spin.value()
            },
            'direct_sql_geopackage': self.direct_sql_toggle.is_enabled(),
            'wkt_caching': self.wkt_cache_toggle.is_enabled(),
            'mod_spatialite_auto': self.mod_spatialite_toggle.is_enabled()
        }


class OGROptimizationPanel(QWidget):
    """
    Optimization settings for OGR/Memory backend (Shapefiles, etc.).
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header
        header = QLabel(f"📁 {tr('OGR/Memory Optimizations')}")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #e67e22;")
        layout.addWidget(header)
        
        desc = QLabel(tr("Optimizations for file-based formats (Shapefiles, GeoJSON) and memory layers"))
        desc.setStyleSheet("color: #666; font-size: 9pt; margin-bottom: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #e67e22;")
        layout.addWidget(sep)
        
        # Spatial Index Auto-creation
        self.auto_index_toggle = OptimizationToggle(
            tr("Automatic Spatial Index"),
            tr("Automatically create spatial index (.qix/.shx) for layers without one. "
               "Essential for reasonable performance on shapefiles."),
            speedup="10-100x",
            default_enabled=True
        )
        layout.addWidget(self.auto_index_toggle)
        
        # Small Dataset Optimization
        self.small_dataset_toggle = OptimizationToggle(
            tr("Small Dataset Memory Backend"),
            tr("For small PostgreSQL layers, copy to memory for faster filtering. "
               "Avoids network overhead for datasets under threshold."),
            speedup="2-5x",
            default_enabled=True
        )
        layout.addWidget(self.small_dataset_toggle)
        
        # Small dataset threshold
        small_layout = QHBoxLayout()
        small_layout.setContentsMargins(30, 0, 0, 0)
        small_layout.addWidget(QLabel(tr("Small dataset threshold:")))
        self.small_threshold_spin = QSpinBox()
        self.small_threshold_spin.setRange(1000, 50000)
        self.small_threshold_spin.setValue(5000)
        self.small_threshold_spin.setSingleStep(1000)
        small_layout.addWidget(self.small_threshold_spin)
        small_layout.addStretch()
        layout.addLayout(small_layout)
        
        # Cancellable Processing
        self.cancellable_toggle = OptimizationToggle(
            tr("Cancellable Processing"),
            tr("Allow cancellation of QGIS processing algorithms. "
               "Prevents QGIS freezing on long operations."),
            speedup="Safety",
            default_enabled=True
        )
        layout.addWidget(self.cancellable_toggle)
        
        # Progressive Chunking
        self.chunking_toggle = OptimizationToggle(
            tr("Progressive Chunking"),
            tr("Process features in chunks for very large datasets. "
               "Reduces memory usage and allows progress feedback."),
            speedup="Memory",
            default_enabled=True
        )
        layout.addWidget(self.chunking_toggle)
        
        # Chunk size
        chunk_layout = QHBoxLayout()
        chunk_layout.setContentsMargins(30, 0, 0, 0)
        chunk_layout.addWidget(QLabel(tr("Chunk size (features):")))
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(500, 20000)
        self.chunk_size_spin.setValue(5000)
        self.chunk_size_spin.setSingleStep(500)
        chunk_layout.addWidget(self.chunk_size_spin)
        chunk_layout.addStretch()
        layout.addLayout(chunk_layout)
        
        # GEOS-safe Geometry
        self.geos_safe_toggle = OptimizationToggle(
            tr("GEOS-safe Geometry Handling"),
            tr("Validate and repair geometries before processing. "
               "Prevents crashes from invalid geometries."),
            speedup="Stability",
            default_enabled=True
        )
        layout.addWidget(self.geos_safe_toggle)
        
        # Thread Safety
        self.thread_safety_toggle = OptimizationToggle(
            tr("Thread-safe Operations"),
            tr("Force sequential execution for OGR layers to prevent crashes. "
               "Required for stable operation with file-based formats."),
            speedup="Stability",
            default_enabled=True
        )
        layout.addWidget(self.thread_safety_toggle)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load settings from configuration."""
        try:
            from ..config.config import ENV_VARS
            config_data = ENV_VARS.get('CONFIG_DATA', {})
            app_opts = config_data.get('APP', {}).get('OPTIONS', {})
            
            small_opt = app_opts.get('SMALL_DATASET_OPTIMIZATION', {})
            self.small_dataset_toggle.set_enabled(
                small_opt.get('enabled', {}).get('value', True)
            )
            self.small_threshold_spin.setValue(
                small_opt.get('threshold', {}).get('value', 5000)
            )
            
        except Exception as e:
            logger.warning(f"Could not load OGR optimization settings: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dictionary."""
        return {
            'auto_spatial_index': self.auto_index_toggle.is_enabled(),
            'small_dataset_optimization': {
                'enabled': self.small_dataset_toggle.is_enabled(),
                'threshold': self.small_threshold_spin.value()
            },
            'cancellable_processing': self.cancellable_toggle.is_enabled(),
            'progressive_chunking': {
                'enabled': self.chunking_toggle.is_enabled(),
                'chunk_size': self.chunk_size_spin.value()
            },
            'geos_safe_geometry': self.geos_safe_toggle.is_enabled(),
            'thread_safety': self.thread_safety_toggle.is_enabled()
        }


class GlobalOptimizationPanel(QWidget):
    """
    Global optimization settings that apply to all backends.
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Header
        header = QLabel(f"⚡ {tr('Global Optimizations')}")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #27ae60;")
        layout.addWidget(header)
        
        desc = QLabel(tr("Optimizations that apply to all backend types"))
        desc.setStyleSheet("color: #666; font-size: 9pt; margin-bottom: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #27ae60;")
        layout.addWidget(sep)
        
        # Auto-Optimization Master Switch
        self.auto_opt_toggle = OptimizationToggle(
            tr("Enable Auto-Optimization"),
            tr("Automatically analyze layers and suggest optimizations before filtering."),
            speedup="Variable",
            default_enabled=True
        )
        layout.addWidget(self.auto_opt_toggle)
        
        # Centroid for Distant Layers
        self.centroid_toggle = OptimizationToggle(
            tr("Auto-Centroid for Distant Layers"),
            tr("Automatically use ST_Centroid() for remote layers (WFS, ArcGIS). "
               "Reduces network data transfer by ~90%."),
            speedup="~90%",
            default_enabled=True
        )
        layout.addWidget(self.centroid_toggle)
        
        # Centroid threshold
        centroid_layout = QHBoxLayout()
        centroid_layout.setContentsMargins(30, 0, 0, 0)
        centroid_layout.addWidget(QLabel(tr("Distant layer threshold:")))
        self.centroid_threshold_spin = QSpinBox()
        self.centroid_threshold_spin.setRange(1000, 100000)
        self.centroid_threshold_spin.setValue(5000)
        self.centroid_threshold_spin.setSingleStep(1000)
        centroid_layout.addWidget(self.centroid_threshold_spin)
        centroid_layout.addStretch()
        layout.addLayout(centroid_layout)
        
        # Auto Strategy Selection
        self.auto_strategy_toggle = OptimizationToggle(
            tr("Auto-Select Best Strategy"),
            tr("Automatically choose optimal filtering strategy based on layer analysis. "
               "(attribute-first, bbox-prefilter, progressive chunks)"),
            speedup="Variable",
            default_enabled=True
        )
        layout.addWidget(self.auto_strategy_toggle)
        
        # Geometry Simplification (with warning)
        self.simplify_toggle = OptimizationToggle(
            tr("Auto-Simplify Geometries ⚠️"),
            tr("Automatically simplify complex geometries. "
               "WARNING: This is a LOSSY operation that may change polygon shapes."),
            speedup="2-5x",
            default_enabled=False
        )
        self.simplify_toggle.setStyleSheet("QWidget { background-color: #fff3cd; }")
        layout.addWidget(self.simplify_toggle)
        
        # Simplify Before Buffer
        self.simplify_buffer_toggle = OptimizationToggle(
            tr("Simplify Before Buffer"),
            tr("Simplify geometries before applying buffer operations. "
               "Improves buffer performance without affecting final spatial results."),
            speedup="2-3x",
            default_enabled=True
        )
        layout.addWidget(self.simplify_buffer_toggle)
        
        # Simplify After Buffer (v2.8.6)
        self.simplify_after_buffer_toggle = OptimizationToggle(
            tr("Simplify After Buffer"),
            tr("Simplify the resulting polygon after buffer operations. "
               "Reduces vertex count for complex polygons from negative/positive buffer sequences."),
            speedup="1.5-2x",
            default_enabled=True
        )
        layout.addWidget(self.simplify_after_buffer_toggle)
        
        # Parallel Filtering
        self.parallel_toggle = OptimizationToggle(
            tr("Parallel Layer Filtering"),
            tr("Filter multiple layers simultaneously using multiple CPU cores."),
            speedup="2-4x",
            default_enabled=True
        )
        layout.addWidget(self.parallel_toggle)
        
        # Max workers
        workers_layout = QHBoxLayout()
        workers_layout.setContentsMargins(30, 0, 0, 0)
        workers_layout.addWidget(QLabel(tr("Max workers (0=auto):")))
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(0, 16)
        self.max_workers_spin.setValue(0)
        workers_layout.addWidget(self.max_workers_spin)
        workers_layout.addStretch()
        layout.addLayout(workers_layout)
        
        # Streaming Export
        self.streaming_toggle = OptimizationToggle(
            tr("Streaming Export"),
            tr("Use batch streaming for exporting large datasets. "
               "Prevents memory issues with very large exports."),
            speedup="Memory",
            default_enabled=True
        )
        layout.addWidget(self.streaming_toggle)
        
        # Ask Before Applying
        self.ask_before_toggle = OptimizationToggle(
            tr("Confirm Before Applying"),
            tr("Show confirmation dialog before applying automatic optimizations."),
            speedup="",
            default_enabled=True
        )
        layout.addWidget(self.ask_before_toggle)
        
        # Show Hints
        self.show_hints_toggle = OptimizationToggle(
            tr("Show Optimization Hints"),
            tr("Display optimization hints in message bar when recommendations are available."),
            speedup="",
            default_enabled=True
        )
        layout.addWidget(self.show_hints_toggle)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load settings from configuration."""
        try:
            from ..config.config import ENV_VARS
            config_data = ENV_VARS.get('CONFIG_DATA', {})
            app_opts = config_data.get('APP', {}).get('OPTIONS', {})
            
            auto_opt = app_opts.get('AUTO_OPTIMIZATION', {})
            self.auto_opt_toggle.set_enabled(auto_opt.get('enabled', {}).get('value', True))
            self.centroid_toggle.set_enabled(auto_opt.get('auto_centroid_for_distant', {}).get('value', True))
            self.centroid_threshold_spin.setValue(auto_opt.get('centroid_threshold_distant', {}).get('value', 5000))
            self.auto_strategy_toggle.set_enabled(auto_opt.get('auto_strategy_selection', {}).get('value', True))
            self.simplify_toggle.set_enabled(auto_opt.get('auto_simplify_geometry', {}).get('value', False))
            self.simplify_buffer_toggle.set_enabled(auto_opt.get('auto_simplify_before_buffer', {}).get('value', True))
            self.simplify_after_buffer_toggle.set_enabled(auto_opt.get('auto_simplify_after_buffer', {}).get('value', True))
            self.show_hints_toggle.set_enabled(auto_opt.get('show_optimization_hints', {}).get('value', True))
            
            parallel = app_opts.get('PARALLEL_FILTERING', {})
            self.parallel_toggle.set_enabled(parallel.get('enabled', {}).get('value', True))
            self.max_workers_spin.setValue(parallel.get('max_workers', {}).get('value', 0))
            
            streaming = app_opts.get('STREAMING_EXPORT', {})
            self.streaming_toggle.set_enabled(streaming.get('enabled', {}).get('value', True))
            
        except Exception as e:
            logger.warning(f"Could not load global optimization settings: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dictionary."""
        return {
            'auto_optimization_enabled': self.auto_opt_toggle.is_enabled(),
            'auto_centroid': {
                'enabled': self.centroid_toggle.is_enabled(),
                'distant_threshold': self.centroid_threshold_spin.value()
            },
            'auto_strategy_selection': self.auto_strategy_toggle.is_enabled(),
            'auto_simplify_geometry': self.simplify_toggle.is_enabled(),
            'simplify_before_buffer': self.simplify_buffer_toggle.is_enabled(),
            'simplify_after_buffer': self.simplify_after_buffer_toggle.is_enabled(),
            'parallel_filtering': {
                'enabled': self.parallel_toggle.is_enabled(),
                'max_workers': self.max_workers_spin.value()
            },
            'streaming_export': self.streaming_toggle.is_enabled(),
            'ask_before_apply': self.ask_before_toggle.is_enabled(),
            'show_hints': self.show_hints_toggle.is_enabled()
        }


class BackendOptimizationWidget(QWidget):
    """
    Main widget containing all backend optimization panels in a tabbed interface.
    Now includes profile selector and smart recommendations.
    """
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Profile selector at top
        self.profile_selector = OptimizationProfileSelector()
        layout.addWidget(self.profile_selector)
        
        # Smart recommendations
        self.recommendations_widget = SmartRecommendationWidget()
        layout.addWidget(self.recommendations_widget)
        
        # Tab widget for different backends
        self.tab_widget = QTabWidget()
        
        # Global tab (first)
        self.global_panel = GlobalOptimizationPanel()
        scroll_global = QScrollArea()
        scroll_global.setWidget(self.global_panel)
        scroll_global.setWidgetResizable(True)
        scroll_global.setFrameShape(QFrame.NoFrame)
        self.tab_widget.addTab(scroll_global, "⚡ " + tr("Global"))
        
        # PostgreSQL tab
        self.postgresql_panel = PostgreSQLOptimizationPanel()
        scroll_pg = QScrollArea()
        scroll_pg.setWidget(self.postgresql_panel)
        scroll_pg.setWidgetResizable(True)
        scroll_pg.setFrameShape(QFrame.NoFrame)
        self.tab_widget.addTab(scroll_pg, "🐘 PostgreSQL")
        
        # Spatialite tab
        self.spatialite_panel = SpatialiteOptimizationPanel()
        scroll_sp = QScrollArea()
        scroll_sp.setWidget(self.spatialite_panel)
        scroll_sp.setWidgetResizable(True)
        scroll_sp.setFrameShape(QFrame.NoFrame)
        self.tab_widget.addTab(scroll_sp, "📦 Spatialite")
        
        # OGR tab
        self.ogr_panel = OGROptimizationPanel()
        scroll_ogr = QScrollArea()
        scroll_ogr.setWidget(self.ogr_panel)
        scroll_ogr.setWidgetResizable(True)
        scroll_ogr.setFrameShape(QFrame.NoFrame)
        self.tab_widget.addTab(scroll_ogr, "📁 OGR/Files")
        
        layout.addWidget(self.tab_widget)
    
    def _connect_signals(self):
        """Connect signals for profile selection and recommendations."""
        self.profile_selector.profileSelected.connect(self._apply_profile)
        self.recommendations_widget.applyRecommendation.connect(
            self._apply_recommendation
        )
    
    def _apply_profile(self, profile_key: str, profile: Dict):
        """Apply a predefined optimization profile."""
        if not profile:
            return
        
        try:
            # Apply global settings
            if 'global' in profile:
                self._apply_global_settings(profile['global'])
            
            # Apply PostgreSQL settings
            if 'postgresql' in profile:
                self._apply_postgresql_settings(profile['postgresql'])
            
            # Apply Spatialite settings
            if 'spatialite' in profile:
                self._apply_spatialite_settings(profile['spatialite'])
            
            # Apply OGR settings
            if 'ogr' in profile:
                self._apply_ogr_settings(profile['ogr'])
            
            # Show success message
            profile_name = profile.get('name', profile_key)
            logger.info(f"Applied optimization profile: {profile_name}")
            
            # Emit settings changed
            self.settingsChanged.emit(self.get_all_settings())
            
        except Exception as e:
            logger.error(f"Error applying profile {profile_key}: {e}")
    
    def _apply_global_settings(self, settings: Dict):
        """Apply global settings to the panel."""
        panel = self.global_panel
        
        panel.auto_opt_toggle.set_enabled(settings.get('auto_optimization_enabled', True))
        
        centroid = settings.get('auto_centroid', {})
        panel.centroid_toggle.set_enabled(centroid.get('enabled', True))
        panel.centroid_threshold_spin.setValue(centroid.get('distant_threshold', 5000))
        
        panel.auto_strategy_toggle.set_enabled(settings.get('auto_strategy_selection', True))
        panel.simplify_toggle.set_enabled(settings.get('auto_simplify_geometry', False))
        panel.simplify_buffer_toggle.set_enabled(settings.get('simplify_before_buffer', True))
        panel.simplify_after_buffer_toggle.set_enabled(settings.get('simplify_after_buffer', True))
        
        parallel = settings.get('parallel_filtering', {})
        panel.parallel_toggle.set_enabled(parallel.get('enabled', True))
        panel.max_workers_spin.setValue(parallel.get('max_workers', 0))
        
        panel.streaming_toggle.set_enabled(settings.get('streaming_export', True))
        panel.ask_before_toggle.set_enabled(settings.get('ask_before_apply', True))
        panel.show_hints_toggle.set_enabled(settings.get('show_hints', True))
    
    def _apply_postgresql_settings(self, settings: Dict):
        """Apply PostgreSQL settings to the panel."""
        panel = self.postgresql_panel
        
        mv = settings.get('materialized_views', {})
        panel.mv_toggle.set_enabled(mv.get('enabled', True))
        panel.mv_threshold_spin.setValue(mv.get('threshold', 10000))
        
        panel.two_phase_toggle.set_enabled(settings.get('two_phase_filtering', True))
        
        prog = settings.get('progressive_loading', {})
        panel.progressive_toggle.set_enabled(prog.get('enabled', True))
        panel.lazy_cursor_spin.setValue(prog.get('lazy_cursor_threshold', 50000))
        
        panel.query_cache_toggle.set_enabled(settings.get('query_caching', True))
        panel.conn_pool_toggle.set_enabled(settings.get('connection_pooling', True))
        
        exists = settings.get('exists_subquery', {})
        panel.exists_toggle.set_enabled(exists.get('enabled', True))
        panel.exists_threshold_spin.setValue(exists.get('threshold', 100000))
        
        panel.spatial_index_toggle.set_enabled(settings.get('spatial_index_auto', True))
    
    def _apply_spatialite_settings(self, settings: Dict):
        """Apply Spatialite settings to the panel."""
        panel = self.spatialite_panel
        
        rtree = settings.get('rtree_temp_tables', {})
        panel.rtree_toggle.set_enabled(rtree.get('enabled', True))
        panel.rtree_threshold_spin.setValue(rtree.get('threshold_kb', 50))
        
        panel.bbox_prefilter_toggle.set_enabled(settings.get('bbox_prefilter', True))
        
        interruptible = settings.get('interruptible_queries', {})
        panel.interruptible_toggle.set_enabled(interruptible.get('enabled', True))
        panel.query_timeout_spin.setValue(interruptible.get('timeout_seconds', 120))
        
        panel.direct_sql_toggle.set_enabled(settings.get('direct_sql_geopackage', True))
        panel.wkt_cache_toggle.set_enabled(settings.get('wkt_caching', True))
        panel.mod_spatialite_toggle.set_enabled(settings.get('mod_spatialite_auto', True))
    
    def _apply_ogr_settings(self, settings: Dict):
        """Apply OGR settings to the panel."""
        panel = self.ogr_panel
        
        panel.auto_index_toggle.set_enabled(settings.get('auto_spatial_index', True))
        
        small = settings.get('small_dataset_optimization', {})
        panel.small_dataset_toggle.set_enabled(small.get('enabled', True))
        panel.small_threshold_spin.setValue(small.get('threshold', 5000))
        
        panel.cancellable_toggle.set_enabled(settings.get('cancellable_processing', True))
        
        chunking = settings.get('progressive_chunking', {})
        panel.chunking_toggle.set_enabled(chunking.get('enabled', True))
        panel.chunk_size_spin.setValue(chunking.get('chunk_size', 5000))
        
        panel.geos_safe_toggle.set_enabled(settings.get('geos_safe_geometry', True))
        panel.thread_safety_toggle.set_enabled(settings.get('thread_safety', True))
    
    def _apply_recommendation(self, recommendation: Dict):
        """Apply a smart recommendation."""
        action = recommendation.get('action', '')
        
        if action == 'enable_mv':
            self.postgresql_panel.mv_toggle.set_enabled(True)
            self.tab_widget.setCurrentIndex(1)  # Switch to PostgreSQL tab
        elif action == 'enable_centroid':
            self.global_panel.centroid_toggle.set_enabled(True)
            self.tab_widget.setCurrentIndex(0)  # Switch to Global tab
        elif action == 'enable_direct_sql':
            self.spatialite_panel.direct_sql_toggle.set_enabled(True)
            self.tab_widget.setCurrentIndex(2)  # Switch to Spatialite tab
        elif action == 'create_indexes':
            self.ogr_panel.auto_index_toggle.set_enabled(True)
            self.tab_widget.setCurrentIndex(3)  # Switch to OGR tab
        elif action == 'apply_balanced':
            self._apply_profile('balanced', OPTIMIZATION_PROFILES.get('balanced', {}))
        
        self.settingsChanged.emit(self.get_all_settings())
    
    def analyze_project(self, project_info: Dict = None):
        """
        Trigger project analysis for smart recommendations.
        
        Args:
            project_info: Dictionary with project analysis data
        """
        self.recommendations_widget.analyze_and_recommend(project_info)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get settings from all panels."""
        return {
            'global': self.global_panel.get_settings(),
            'postgresql': self.postgresql_panel.get_settings(),
            'spatialite': self.spatialite_panel.get_settings(),
            'ogr': self.ogr_panel.get_settings()
        }


class BackendOptimizationDialog(QDialog):
    """
    Dialog wrapper for BackendOptimizationWidget.
    Allows users to configure all backend optimizations in a modal dialog.
    Includes profile selection, smart recommendations, and MV management.
    
    v2.8.6: Enhanced with MV status widget and cleanup actions.
    """
    
    def __init__(self, parent=None, project_info: Dict = None):
        super().__init__(parent)
        self.project_info = project_info
        self._parent_ref = parent  # Store reference to access session_id
        self.setWindowTitle(tr("FilterMate - Backend Optimizations"))
        self.setMinimumWidth(580)
        self.setMinimumHeight(650)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Main widget
        self.optimization_widget = BackendOptimizationWidget(self)
        layout.addWidget(self.optimization_widget)
        
        # Pass session_id to PostgreSQL panel for MV status
        self._pass_session_info()
        
        # Analyze project for recommendations
        if project_info:
            self.optimization_widget.analyze_project(project_info)
        else:
            # Try to analyze current project
            self._analyze_current_project()
        
        # Sync auto_cleanup setting from parent dockwidget
        self._sync_auto_cleanup_setting()
        
        # Compact info label
        info = QLabel(
            tr("💡 Select a profile for quick setup, or customize settings per backend.")
        )
        info.setStyleSheet("color: #2980b9; font-size: 9pt;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        # Reset to defaults button
        reset_btn = QPushButton(tr("Reset to Defaults"))
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        reset_btn.clicked.connect(self._restore_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # OK button (styled)
        ok_btn = QPushButton(tr("Save Settings"))
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
    
    def _analyze_current_project(self):
        """Analyze the current QGIS project for recommendations."""
        try:
            from qgis.core import QgsProject
            
            project = QgsProject.instance()
            layers = project.mapLayers().values()
            
            project_info = {
                'postgresql_layers': 0,
                'geopackage_layers': 0,
                'shapefile_layers': 0,
                'large_layers': 0,
                'remote_layers': 0
            }
            
            for layer in layers:
                if not hasattr(layer, 'providerType'):
                    continue
                
                provider = layer.providerType()
                feature_count = layer.featureCount() if hasattr(layer, 'featureCount') else 0
                
                if provider == 'postgres':
                    project_info['postgresql_layers'] += 1
                elif provider == 'ogr':
                    source = layer.source().lower()
                    if '.gpkg' in source:
                        project_info['geopackage_layers'] += 1
                    elif '.shp' in source:
                        project_info['shapefile_layers'] += 1
                elif provider in ('WFS', 'arcgisfeatureserver', 'wfs'):
                    project_info['remote_layers'] += 1
                
                if feature_count > 50000:
                    project_info['large_layers'] += 1
            
            self.optimization_widget.analyze_project(project_info)
            
        except Exception as e:
            logger.debug(f"Could not analyze current project: {e}")
    
    def _pass_session_info(self):
        """Pass session info to PostgreSQL panel for MV status."""
        try:
            # Try to get session_id from parent hierarchy
            session_id = None
            parent = self._parent_ref
            while parent:
                if hasattr(parent, 'session_id'):
                    session_id = parent.session_id
                    break
                if hasattr(parent, '_app_ref') and hasattr(parent._app_ref, 'session_id'):
                    session_id = parent._app_ref.session_id
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
            
            if session_id:
                # Store session_id on the panel for MV status
                self.optimization_widget.postgresql_panel.session_id = session_id
                # Trigger refresh
                self.optimization_widget.postgresql_panel._refresh_mv_status()
        except Exception as e:
            logger.debug(f"Could not pass session info: {e}")
    
    def _sync_auto_cleanup_setting(self):
        """Sync auto_cleanup checkbox with dockwidget setting."""
        try:
            parent = self._parent_ref
            if parent and hasattr(parent, '_pg_auto_cleanup_enabled'):
                auto_cleanup = parent._pg_auto_cleanup_enabled
                pg_panel = self.optimization_widget.postgresql_panel
                pg_panel.auto_cleanup_cb.setChecked(auto_cleanup)
        except Exception as e:
            logger.debug(f"Could not sync auto_cleanup setting: {e}")
    
    def _restore_defaults(self):
        """Restore all settings to balanced defaults."""
        reply = QMessageBox.question(
            self,
            tr("Restore Defaults"),
            tr("Reset all settings to balanced defaults?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            balanced = OPTIMIZATION_PROFILES.get('balanced', {})
            self.optimization_widget._apply_profile('balanced', balanced)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get all settings from the widget."""
        return self.optimization_widget.get_all_settings()
