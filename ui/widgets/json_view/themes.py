"""
Color themes for Qt JSON View.

This module provides different color themes for displaying JSON data in the tree view.
Each theme defines colors for different data types.
"""

from qgis.PyQt import QtCore, QtGui


class Theme:
    """Base class for color themes."""

    def __init__(self, name):
        self.name = name
        self.colors = {
            'none': QtCore.Qt.black,
            'string': QtCore.Qt.black,
            'integer': QtCore.Qt.black,
            'float': QtCore.Qt.black,
            'boolean': QtCore.Qt.black,
            'list': QtCore.Qt.black,
            'dict': QtCore.Qt.black,
            'url': QtCore.Qt.black,
            'filepath': QtCore.Qt.black,
            'range': QtCore.Qt.black,
            'choices': QtCore.Qt.black,
        }

    def get_color(self, type_name):
        """Get color for a given data type."""
        return self.colors.get(type_name.lower(), QtCore.Qt.black)


class DefaultTheme(Theme):
    """Default theme with black text for all types."""

    def __init__(self):
        super().__init__("Default")


class MonokaiTheme(Theme):
    """Monokai-inspired dark theme with vibrant colors."""

    def __init__(self):
        super().__init__("Monokai")
        self.colors = {
            'none': QtGui.QColor("#75715E"),  # Gray
            'string': QtGui.QColor("#E6DB74"),  # Yellow
            'integer': QtGui.QColor("#AE81FF"),  # Purple
            'float': QtGui.QColor("#AE81FF"),  # Purple
            'boolean': QtGui.QColor("#FD971F"),  # Orange
            'list': QtGui.QColor("#F92672"),  # Pink
            'dict': QtGui.QColor("#66D9EF"),  # Cyan
            'url': QtGui.QColor("#A6E22E"),  # Green
            'filepath': QtGui.QColor("#A6E22E"),  # Green
            'range': QtGui.QColor("#AE81FF"),  # Purple
            'choices': QtGui.QColor("#E6DB74"),  # Yellow
        }


class SolarizedLightTheme(Theme):
    """Solarized Light theme with warm, readable colors."""

    def __init__(self):
        super().__init__("Solarized Light")
        self.colors = {
            'none': QtGui.QColor("#93A1A1"),  # Base1
            'string': QtGui.QColor("#2AA198"),  # Cyan
            'integer': QtGui.QColor("#D33682"),  # Magenta
            'float': QtGui.QColor("#D33682"),  # Magenta
            'boolean': QtGui.QColor("#CB4B16"),  # Orange
            'list': QtGui.QColor("#B58900"),  # Yellow
            'dict': QtGui.QColor("#268BD2"),  # Blue
            'url': QtGui.QColor("#859900"),  # Green
            'filepath': QtGui.QColor("#859900"),  # Green
            'range': QtGui.QColor("#6C71C4"),  # Violet
            'choices': QtGui.QColor("#2AA198"),  # Cyan
        }


class SolarizedDarkTheme(Theme):
    """Solarized Dark theme with warm, readable colors on dark background."""

    def __init__(self):
        super().__init__("Solarized Dark")
        self.colors = {
            'none': QtGui.QColor("#586E75"),  # Base01
            'string': QtGui.QColor("#2AA198"),  # Cyan
            'integer': QtGui.QColor("#D33682"),  # Magenta
            'float': QtGui.QColor("#D33682"),  # Magenta
            'boolean': QtGui.QColor("#CB4B16"),  # Orange
            'list': QtGui.QColor("#B58900"),  # Yellow
            'dict': QtGui.QColor("#268BD2"),  # Blue
            'url': QtGui.QColor("#859900"),  # Green
            'filepath': QtGui.QColor("#859900"),  # Green
            'range': QtGui.QColor("#6C71C4"),  # Violet
            'choices': QtGui.QColor("#2AA198"),  # Cyan
        }


class NordTheme(Theme):
    """Nord theme with cool, arctic colors."""

    def __init__(self):
        super().__init__("Nord")
        self.colors = {
            'none': QtGui.QColor("#4C566A"),  # Polar Night
            'string': QtGui.QColor("#A3BE8C"),  # Green
            'integer': QtGui.QColor("#B48EAD"),  # Purple
            'float': QtGui.QColor("#B48EAD"),  # Purple
            'boolean': QtGui.QColor("#D08770"),  # Orange
            'list': QtGui.QColor("#EBCB8B"),  # Yellow
            'dict': QtGui.QColor("#88C0D0"),  # Frost Cyan
            'url': QtGui.QColor("#8FBCBB"),  # Frost Teal
            'filepath': QtGui.QColor("#8FBCBB"),  # Frost Teal
            'range': QtGui.QColor("#B48EAD"),  # Purple
            'choices': QtGui.QColor("#A3BE8C"),  # Green
        }


class DraculaTheme(Theme):
    """Dracula theme with vivid colors on dark background."""

    def __init__(self):
        super().__init__("Dracula")
        self.colors = {
            'none': QtGui.QColor("#6272A4"),  # Comment Gray
            'string': QtGui.QColor("#F1FA8C"),  # Yellow
            'integer': QtGui.QColor("#BD93F9"),  # Purple
            'float': QtGui.QColor("#BD93F9"),  # Purple
            'boolean': QtGui.QColor("#FFB86C"),  # Orange
            'list': QtGui.QColor("#FF79C6"),  # Pink
            'dict': QtGui.QColor("#8BE9FD"),  # Cyan
            'url': QtGui.QColor("#50FA7B"),  # Green
            'filepath': QtGui.QColor("#50FA7B"),  # Green
            'range': QtGui.QColor("#BD93F9"),  # Purple
            'choices': QtGui.QColor("#F1FA8C"),  # Yellow
        }


class OneDarkTheme(Theme):
    """One Dark theme (Atom/VS Code style)."""

    def __init__(self):
        super().__init__("One Dark")
        self.colors = {
            'none': QtGui.QColor("#5C6370"),  # Gray
            'string': QtGui.QColor("#98C379"),  # Green
            'integer': QtGui.QColor("#D19A66"),  # Orange
            'float': QtGui.QColor("#D19A66"),  # Orange
            'boolean': QtGui.QColor("#E06C75"),  # Red
            'list': QtGui.QColor("#E5C07B"),  # Yellow
            'dict': QtGui.QColor("#61AFEF"),  # Blue
            'url': QtGui.QColor("#56B6C2"),  # Cyan
            'filepath': QtGui.QColor("#56B6C2"),  # Cyan
            'range': QtGui.QColor("#C678DD"),  # Purple
            'choices': QtGui.QColor("#98C379"),  # Green
        }


class GruvboxTheme(Theme):
    """Gruvbox theme with warm, retro colors."""

    def __init__(self):
        super().__init__("Gruvbox")
        self.colors = {
            'none': QtGui.QColor("#928374"),  # Gray
            'string': QtGui.QColor("#B8BB26"),  # Green
            'integer': QtGui.QColor("#D3869B"),  # Purple
            'float': QtGui.QColor("#D3869B"),  # Purple
            'boolean': QtGui.QColor("#FE8019"),  # Orange
            'list': QtGui.QColor("#FABD2F"),  # Yellow
            'dict': QtGui.QColor("#83A598"),  # Blue
            'url': QtGui.QColor("#8EC07C"),  # Aqua
            'filepath': QtGui.QColor("#8EC07C"),  # Aqua
            'range': QtGui.QColor("#D3869B"),  # Purple
            'choices': QtGui.QColor("#B8BB26"),  # Green
        }


# Available themes registry
THEMES = {
    'default': DefaultTheme(),
    'monokai': MonokaiTheme(),
    'solarized_light': SolarizedLightTheme(),
    'solarized_dark': SolarizedDarkTheme(),
    'nord': NordTheme(),
    'dracula': DraculaTheme(),
    'one_dark': OneDarkTheme(),
    'gruvbox': GruvboxTheme(),
}

# Current active theme (can be changed at runtime)
_current_theme = THEMES['default']


def get_current_theme():
    """Get the currently active theme."""
    return _current_theme


def set_theme(theme_name):
    """
    Set the active theme.

    Args:
        theme_name (str): Name of the theme to activate (e.g., 'monokai', 'nord')

    Returns:
        bool: True if theme was set successfully, False if theme not found
    """
    global _current_theme
    theme_name = theme_name.lower()
    if theme_name in THEMES:
        _current_theme = THEMES[theme_name]
        return True
    return False


def get_available_themes():
    """
    Get list of all available theme names.

    Returns:
        list: List of theme names
    """
    return list(THEMES.keys())


def get_theme_display_names():
    """
    Get dictionary of theme keys to display names.

    Returns:
        dict: Dictionary mapping theme keys to display names
    """
    return {key: theme.name for key, theme in THEMES.items()}
