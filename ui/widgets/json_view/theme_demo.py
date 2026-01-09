"""
Simple theme demo widget for Qt JSON View.

A simple dialog to preview all available themes with sample JSON data.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QGroupBox
)
from qgis.PyQt.QtCore import Qt

from modules.qt_json_view import view, model


class ThemeDemoDialog(QDialog):
    """
    Dialog to demonstrate and preview all available themes.
    
    Usage in QGIS Python console:
        from modules.qt_json_view.theme_demo import ThemeDemoDialog
        demo = ThemeDemoDialog()
        demo.exec_()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Qt JSON View - Theme Demo")
        self.setMinimumSize(700, 500)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Theme selector group
        theme_group = QGroupBox("Theme Selection")
        theme_layout = QHBoxLayout(theme_group)
        
        theme_label = QLabel("Select Theme:")
        self.theme_combo = QComboBox()
        
        # Navigation buttons
        self.prev_button = QPushButton("← Previous")
        self.next_button = QPushButton("Next →")
        
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo, 1)
        theme_layout.addWidget(self.prev_button)
        theme_layout.addWidget(self.next_button)
        
        layout.addWidget(theme_group)
        
        # Current theme info
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)
        
        # Create JSON view with sample data
        sample_data = self._create_sample_data()
        self.json_model = model.JsonModel(sample_data, editable_keys=False, editable_values=True)
        self.json_view = view.JsonView(self.json_model)
        layout.addWidget(self.json_view, 1)
        
        # Populate theme combo
        self._populate_themes()
        
        # Connect signals
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.prev_button.clicked.connect(self._previous_theme)
        self.next_button.clicked.connect(self._next_theme)
        
        # Expand all items
        self.json_view.expandAll()
        
        # Set initial theme info
        self._update_info_label()
    
    def _create_sample_data(self):
        """Create comprehensive sample data showcasing all data types."""
        return {
            "plugin": {
                "name": "FilterMate",
                "version": "1.0.0",
                "author": "QGIS Team",
                "enabled": True,
                "priority": 100,
                "rating": 4.8
            },
            "features": [
                "Advanced filtering",
                "Multiple backends",
                "Export capabilities",
                "Filter history"
            ],
            "backends": {
                "postgresql": {
                    "available": True,
                    "port": 5432,
                    "max_connections": 100
                },
                "spatialite": {
                    "available": True,
                    "cache_size": 2000
                },
                "ogr": {
                    "available": True,
                    "drivers": 84
                }
            },
            "urls": {
                "homepage": "https://github.com/example/filtermate",
                "documentation": "https://docs.example.com/filtermate",
                "issues": "https://github.com/example/filtermate/issues"
            },
            "paths": {
                "config": "/path/to/config.json",
                "cache": "/tmp/filtermate_cache",
                "logs": "/var/log/qgis/filtermate.log"
            },
            "settings": {
                "max_results": 10000,
                "timeout_seconds": 30.5,
                "auto_save": True,
                "debug_mode": False,
                "null_value": None
            },
            "ranges": {
                "zoom_levels": {
                    "start": 1,
                    "end": 20,
                    "step": 1
                },
                "opacity": {
                    "start": 0.0,
                    "end": 1.0,
                    "step": 0.1
                }
            },
            "statistics": {
                "total_filters": 156,
                "active_tasks": 3,
                "cache_hit_rate": 0.847,
                "uptime_hours": 127.5
            }
        }
    
    def _populate_themes(self):
        """Populate the theme combo box."""
        themes = self.json_view.get_available_themes()
        
        # Sort themes alphabetically by display name
        sorted_themes = sorted(themes.items(), key=lambda x: x[1])
        
        for key, name in sorted_themes:
            self.theme_combo.addItem(name, key)
    
    def _on_theme_changed(self, index):
        """Handle theme change from combo box."""
        if index >= 0:
            theme_key = self.theme_combo.currentData()
            self.json_view.set_theme(theme_key)
            self._update_info_label()
    
    def _previous_theme(self):
        """Switch to previous theme."""
        current_index = self.theme_combo.currentIndex()
        if current_index > 0:
            self.theme_combo.setCurrentIndex(current_index - 1)
    
    def _next_theme(self):
        """Switch to next theme."""
        current_index = self.theme_combo.currentIndex()
        if current_index < self.theme_combo.count() - 1:
            self.theme_combo.setCurrentIndex(current_index + 1)
    
    def _update_info_label(self):
        """Update the info label with current theme information."""
        theme_name = self.json_view.get_current_theme_name()
        theme_count = self.theme_combo.count()
        current_index = self.theme_combo.currentIndex() + 1
        
        self.info_label.setText(
            f"<b>{theme_name}</b> theme | "
            f"Theme {current_index} of {theme_count}"
        )


def show_theme_demo():
    """
    Show the theme demo dialog.
    
    Usage in QGIS Python console:
        from modules.qt_json_view.theme_demo import show_theme_demo
        show_theme_demo()
    """
    from qgis.utils import iface
    
    dialog = ThemeDemoDialog(iface.mainWindow())
    dialog.exec_()


if __name__ == "__main__":
    print("This demo requires QGIS environment")
    print("Use: show_theme_demo() from within QGIS Python console")
