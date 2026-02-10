"""
Example of using color themes in Qt JSON View.

This example demonstrates how to create a JSON viewer with a theme selector.
"""

from qgis.PyQt.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel
)

from . import view, model


class JsonViewerWithThemes(QMainWindow):
    """Example JSON viewer with theme selection."""

    def __init__(self, json_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JSON Viewer with Color Themes")
        self.setGeometry(100, 100, 800, 600)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create theme selector
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()

        # Populate theme combo box
        self.json_model = model.JsonModel(json_data, editable_keys=True, editable_values=True)
        self.json_view = view.JsonView(self.json_model)

        themes_dict = self.json_view.get_available_themes()
        for key, name in sorted(themes_dict.items()):
            self.theme_combo.addItem(name, key)

        # Connect theme change
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)

        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        # Add current theme display
        self.current_theme_label = QLabel(f"Current: {self.json_view.get_current_theme_name()}")
        theme_layout.addWidget(self.current_theme_label)

        # Add widgets to main layout
        layout.addLayout(theme_layout)
        layout.addWidget(self.json_view)

        # Expand all by default
        self.json_view.expandAll()

    def on_theme_changed(self, index):
        """Handle theme selection change."""
        theme_key = self.theme_combo.currentData()
        if self.json_view.set_theme(theme_key):
            self.current_theme_label.setText(
                f"Current: {self.json_view.get_current_theme_name()}"
            )


def create_sample_data():
    """Create sample JSON data for demonstration."""
    return {
        "name": "FilterMate",
        "version": 1.0,
        "enabled": True,
        "features": ["filtering", "export", "history"],
        "config": {
            "max_results": 1000,
            "timeout": 30.5,
            "debug": False,
            "backend": "postgresql"
        },
        "urls": {
            "homepage": "https://github.com/example/filtermate",
            "documentation": "https://docs.example.com"
        },
        "paths": {
            "config": "/path/to/config.json",
            "logs": "/var/log/qgis/filtermate.log"
        },
        "ranges": {
            "zoom": {"start": 1, "end": 20, "step": 1},
            "scale": {"start": 0.0, "end": 1.0, "step": 0.1}
        },
        "nothing": None
    }


# Example usage in QGIS Plugin
def show_json_viewer_with_themes():
    """
    Example function to show JSON viewer with themes in a QGIS plugin.

    Usage:
        from ui.widgets.json_view.example_themes import show_json_viewer_with_themes
        show_json_viewer_with_themes()
    """
    from qgis.utils import iface

    # Create sample data
    data = create_sample_data()

    # Create and show viewer
    viewer = JsonViewerWithThemes(data, iface.mainWindow())
    viewer.show()

    return viewer


# Quick test themes function
def test_all_themes(json_view):
    """
    Test all available themes by cycling through them.

    Args:
        json_view: A JsonView instance
    """
    import time
    from qgis.PyQt.QtWidgets import QApplication

    themes = json_view.get_available_themes()

    for key, name in themes.items():
        json_view.set_theme(key)
        QApplication.processEvents()  # Update UI
        time.sleep(1)  # Wait 1 second


if __name__ == "__main__":
    pass  # block was empty
    # This won't work standalone, but shows the pattern
