"""
Theme Manager for FilterMate.

Centralized theme management with QGIS theme synchronization.
Migrated from modules/ui_styles.py (StyleLoader class).

Story: MIG-066
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Callable, List
import logging
import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, QEvent, Qt
from qgis.PyQt.QtWidgets import QDialog, QWidget
from qgis.PyQt.QtGui import QFont

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class GlobalDialogStyleFilter(QObject):
    """
    Global application-level event filter to reset styles on QGIS dialogs.
    
    This filter is installed on QApplication to intercept ALL dialog show events,
    regardless of their parent. It ensures dialogs like QgsExpressionBuilderDialog
    inherit QGIS default styles instead of FilterMate's custom styles.
    
    FIX 2026-01-21: Expression Builder dialogs displayed with gray/empty areas
    due to style inheritance from FilterMate dockwidget.
    """
    
    _instance = None
    _installed = False
    
    # Dialog class names that need style reset
    QGIS_DIALOGS = {
        'QgsExpressionBuilderDialog',
        'QgsExpressionSelectionDialog',
        'QgsProcessingAlgorithmDialogBase',
        'QgsFieldCalculator',
        'QgsQueryBuilder',
    }
    
    def __init__(self):
        super().__init__()
        self._processed_dialogs = set()
    
    @classmethod
    def get_instance(cls) -> 'GlobalDialogStyleFilter':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = GlobalDialogStyleFilter()
        return cls._instance
    
    @classmethod
    def install(cls) -> bool:
        """
        DISABLED 2026-01-21: Dialog style filter disabled.
        
        The scanner and event filter were causing UI freezes.
        Root cause investigation needed - may be QGIS/system theme issue.
        """
        logger.info("GlobalDialogStyleFilter is DISABLED (prevents UI freeze)")
        return True  # Return True to avoid breaking callers
    
    def _start_dialog_scanner(self):
        """
        DISABLED 2026-01-21: Scanner disabled to prevent UI freeze.
        The QTimer polling was causing performance issues.
        """
        pass
    
    def _scan_for_expression_dialogs(self):
        """Scan all top-level widgets for expression dialogs."""
        try:
            app = QgsApplication.instance()
            if not app:
                return
            
            for widget in app.topLevelWidgets():
                if widget is None:
                    continue
                    
                class_name = widget.__class__.__name__
                widget_id = id(widget)
                
                # Log ALL visible dialogs for debugging
                if widget.isVisible() and widget_id not in self._processed_dialogs:
                    # Check window title for "expression" keyword (case insensitive)
                    title = widget.windowTitle().lower() if hasattr(widget, 'windowTitle') else ""
                    
                    is_expression_dialog = (
                        'Expression' in class_name or 
                        'Builder' in class_name or 
                        'expression' in title or
                        'constructeur' in title or  # French
                        class_name in self.QGIS_DIALOGS
                    )
                    
                    if is_expression_dialog:
                        self._processed_dialogs.add(widget_id)
                        self._fix_expression_dialog(widget, class_name)
                        
        except Exception as e:
            logger.debug(f"Dialog scanner error: {e}")
    
    def _fix_expression_dialog(self, widget, class_name: str):
        """Fix expression dialog style using QGIS defaults."""
        try:
            # NUCLEAR OPTION: Apply one comprehensive stylesheet to the entire dialog
            # This overrides ALL inherited styles from parent widgets
            comprehensive_stylesheet = """
                QDialog {
                    background-color: white;
                }
                QWidget {
                    background-color: white;
                }
                QFrame {
                    background-color: white;
                }
                QSplitter {
                    background-color: white;
                }
                QSplitter::handle {
                    background-color: #d0d0d0;
                    width: 1px;
                    height: 1px;
                }
                QSplitter::handle:hover {
                    background-color: #b0b0b0;
                }
                QTabWidget::pane {
                    background-color: white;
                    border: 1px solid #c0c0c0;
                }
                QTreeView, QListView, QTreeWidget, QListWidget {
                    background-color: white;
                    alternate-background-color: #f5f5f5;
                    color: black;
                    border: 1px solid #c0c0c0;
                }
                QTreeView::item, QListView::item {
                    padding: 2px;
                }
                QTreeView::item:selected, QListView::item:selected {
                    background-color: #308cc6;
                    color: white;
                }
                QTreeView::item:hover, QListView::item:hover {
                    background-color: #e8f4fc;
                }
                QTextBrowser, QTextEdit, QPlainTextEdit {
                    background-color: white;
                    color: black;
                    border: 1px solid #c0c0c0;
                }
                QLineEdit, QComboBox {
                    background-color: white;
                    color: black;
                }
                QScrollArea {
                    background-color: white;
                }
            """
            
            widget.setStyleSheet(comprehensive_stylesheet)
            
            # Force repaint
            widget.update()
            widget.repaint()
            
        except Exception as e:
            logger.debug(f"Error fixing expression dialog {class_name}: {e}")
    
    @classmethod
    def uninstall(cls) -> None:
        """Remove global filter from QApplication."""
        if not cls._installed or cls._instance is None:
            return
        try:
            # Stop scanner timer
            if hasattr(cls._instance, '_scanner_timer') and cls._instance._scanner_timer:
                cls._instance._scanner_timer.stop()
                cls._instance._scanner_timer = None
            
            app = QgsApplication.instance()
            if app:
                app.removeEventFilter(cls._instance)
                cls._installed = False
                logger.info("GlobalDialogStyleFilter removed from QApplication")
        except Exception as e:
            logger.warning(f"Could not uninstall GlobalDialogStyleFilter: {e}")
    
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        DISABLED 2026-01-21: Event filter disabled to prevent UI freeze.
        Always returns False to allow normal event processing.
        """
        return False
    
    def _fix_widget_style(self, widget: QWidget, class_name: str) -> None:
        """Fix style for any widget (dialog or not)."""
        try:
            if isinstance(widget, QDialog):
                self._fix_dialog_style(widget, class_name)
            else:
                # For non-QDialog widgets, still try to fix
                app = QgsApplication.instance()
                app_palette = app.palette()
                widget.setStyleSheet("")
                widget.setPalette(app_palette)
                widget.setAutoFillBackground(True)
                for child in widget.findChildren(QWidget):
                    try:
                        child.setStyleSheet("")
                        child.setPalette(app_palette)
                        child.setAutoFillBackground(True)
                    except (RuntimeError, AttributeError):
                        pass  # Child widget may have been deleted
                widget.update()
        except Exception as e:
            logger.debug(f"Error fixing widget {class_name}: {e}")
    
    def _fix_dialog_style(self, dialog: QDialog, class_name: str) -> None:
        """
        Reset dialog and all its children to QGIS default appearance.
        """
        try:
            # Get QGIS application default palette and font
            app = QgsApplication.instance()
            app_palette = app.palette()
            app_font = app.font()
            
            # Get main window for reparenting reference
            from qgis.utils import iface
            main_window = iface.mainWindow() if iface else None
            
            # Reset the dialog itself
            dialog.setStyleSheet("")
            dialog.setPalette(app_palette)
            dialog.setFont(app_font)
            dialog.setAutoFillBackground(True)
            
            # Force the dialog to NOT inherit from parent
            dialog.setAttribute(Qt.WA_StyledBackground, False)
            dialog.setAttribute(Qt.WA_NoSystemBackground, False)
            
            # Import view classes for special handling
            from qgis.PyQt.QtWidgets import QTreeView, QListView, QAbstractItemView, QTreeWidget, QListWidget
            
            # Reset all child widgets recursively with special handling for views
            for child in dialog.findChildren(QWidget):
                try:
                    child_class = child.__class__.__name__
                    
                    # Clear stylesheet
                    if child.styleSheet():
                        child.setStyleSheet("")
                    
                    # Reset palette  
                    child.setPalette(app_palette)
                    
                    # Reset font to application default
                    child.setFont(app_font)
                    
                    # Enable auto-fill background for proper rendering
                    child.setAutoFillBackground(True)
                    
                    # Reset style attributes
                    child.setAttribute(Qt.WA_StyledBackground, False)
                    
                    # Special handling for tree/list views - they need explicit background
                    if isinstance(child, (QTreeView, QListView, QTreeWidget, QListWidget, QAbstractItemView)):
                        # Force white background for views
                        view_palette = app_palette
                        child.setPalette(view_palette)
                        child.setAutoFillBackground(True)
                        # Also fix viewport
                        if hasattr(child, 'viewport') and child.viewport():
                            child.viewport().setPalette(view_palette)
                            child.viewport().setAutoFillBackground(True)
                            child.viewport().setStyleSheet("")
                        
                except RuntimeError:
                    pass  # Widget was deleted
                except Exception as e:
                    logger.debug(f"Error fixing child {child.__class__.__name__}: {e}")
            
            # Force immediate repaint
            dialog.style().unpolish(dialog)
            dialog.style().polish(dialog)
            dialog.update()
            dialog.repaint()
            
        except RuntimeError:
            pass  # Dialog was deleted
        except Exception as e:
            logger.debug(f"Error in _fix_dialog_style for {class_name}: {e}")



class ChildDialogStyleFilter(QObject):
    """
    Event filter to prevent FilterMate styles from affecting child dialogs.
    
    When QGIS widgets like QgsFieldExpressionWidget open dialogs
    (e.g., QgsExpressionBuilderDialog), those dialogs inherit the parent's
    palette/styles. This filter intercepts child additions and resets
    the stylesheet on QDialog instances to restore default QGIS appearance.
    
    FIX 2026-01-21: Expression Builder and other QGIS dialogs displayed
    incorrectly due to style inheritance from FilterMate's themed dockwidget.
    """
    
    # Dialog class names that should be protected from style inheritance
    PROTECTED_DIALOGS = {
        'QgsExpressionBuilderDialog',
        'QgsProcessingAlgorithmDialogBase', 
        'QDialog',
        'QMessageBox',
        'QFileDialog',
        'QColorDialog',
        'QFontDialog',
        'QInputDialog',
    }
    
    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._processed_widgets = set()  # Track processed widgets by id
    
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Filter events to detect child dialog creation and show events.
        
        Args:
            watched: The object being watched
            event: The event being processed
            
        Returns:
            False to allow event to continue propagation
        """
        # Handle ChildAdded events on the parent
        if event.type() == QEvent.ChildAdded:
            child = event.child()
            if child is not None and isinstance(child, QDialog):
                widget_id = id(child)
                if widget_id not in self._processed_widgets:
                    self._processed_widgets.add(widget_id)
                    from qgis.PyQt.QtCore import QTimer
                    QTimer.singleShot(0, lambda w=child: self._reset_dialog_style(w))
        
        # Handle Show events - dialogs might be created later
        elif event.type() == QEvent.Show:
            if isinstance(watched, QDialog):
                widget_id = id(watched)
                if widget_id not in self._processed_widgets:
                    self._processed_widgets.add(widget_id)
                    self._reset_dialog_style(watched)
        
        # Always return False to allow normal event processing
        return False
    
    def _reset_dialog_style(self, dialog: QDialog) -> None:
        """
        Reset dialog stylesheet and palette to default.
        
        Args:
            dialog: The dialog to reset
        """
        try:
            # Check if dialog still exists and is valid
            if dialog is None:
                return
                
            class_name = dialog.__class__.__name__
            
            # Only reset protected dialog types
            if class_name in self.PROTECTED_DIALOGS or isinstance(dialog, QDialog):
                # Clear any inherited stylesheet
                current_style = dialog.styleSheet()
                if current_style:
                    dialog.setStyleSheet("")
                    logger.debug(f"Reset stylesheet for child dialog: {class_name}")
                
                # Reset palette to application default
                from qgis.core import QgsApplication
                app_palette = QgsApplication.instance().palette()
                dialog.setPalette(app_palette)
                
                # Ensure all children also use default palette
                for child in dialog.findChildren(QObject):
                    if hasattr(child, 'setPalette'):
                        try:
                            child.setPalette(app_palette)
                        except (RuntimeError, AttributeError):
                            pass  # Child widget may have been deleted
                            
                logger.debug(f"Reset palette for child dialog: {class_name}")
                    
        except RuntimeError:
            # Widget was deleted
            pass
        except Exception as e:
            logger.debug(f"Could not reset dialog style: {e}")


class ThemeManager(StylerBase):
    """
    Centralized theme management for FilterMate.
    
    Provides:
    - Theme detection from QGIS palette
    - Theme application to widgets
    - Theme change events via callbacks
    - Color scheme management
    
    Migrated methods from modules/ui_styles.py:
    - detect_qgis_theme() -> detect_system_theme()
    - set_theme() -> set_theme()
    - get_current_theme() -> current_theme property
    - load_stylesheet() -> _load_stylesheet()
    
    Theme Change Callbacks:
        Use add_theme_changed_callback() to register handlers
    
    Example:
        manager = ThemeManager(dockwidget)
        manager.setup()
        
        # React to theme changes via callback
        manager.add_theme_changed_callback(on_theme_changed)
        
        # Change theme
        manager.set_theme('dark')
    """
    
    # Default color schemes
    COLOR_SCHEMES = {
        'default': {
            'color_bg_0': '#EFEFEF',
            'color_1': '#FFFFFF',
            'color_bg_1': '#FFFFFF',      # Alias for color_1
            'color_2': '#D0D0D0',
            'color_bg_2': '#D0D0D0',      # Alias for color_2
            'color_bg_3': '#2196F3',
            'color_3': '#4A4A4A',
            'color_font_0': '#1A1A1A',
            'color_font_1': '#4A4A4A',
            'color_font_2': '#888888',
            'color_accent': '#1565C0',
            'color_accent_hover': '#1E88E5',
            'color_accent_pressed': '#0D47A1',
            'color_accent_light_bg': '#E3F2FD',
            'color_accent_dark': '#01579B',
            'icon_filter': 'none'
        },
        'dark': {
            'color_bg_0': '#1E1E1E',
            'color_1': '#252526',
            'color_bg_1': '#252526',      # Alias for color_1
            'color_2': '#37373D',
            'color_bg_2': '#37373D',      # Alias for color_2
            'color_bg_3': '#0E639C',
            'color_3': '#CCCCCC',
            'color_font_0': '#D4D4D4',
            'color_font_1': '#9D9D9D',
            'color_font_2': '#6A6A6A',
            'color_accent': '#007ACC',
            'color_accent_hover': '#1177BB',
            'color_accent_pressed': '#005A9E',
            'color_accent_light_bg': '#264F78',
            'color_accent_dark': '#FFFFFF',
            'icon_filter': 'invert(100%)'
        },
        'light': {
            'color_bg_0': '#FFFFFF',
            'color_1': '#F8F8F8',
            'color_bg_1': '#F8F8F8',      # Alias for color_1
            'color_2': '#CCCCCC',
            'color_bg_2': '#CCCCCC',      # Alias for color_2
            'color_bg_3': '#2196F3',
            'color_3': '#333333',
            'color_font_0': '#000000',
            'color_font_1': '#333333',
            'color_font_2': '#999999',
            'color_accent': '#1976D2',
            'color_accent_hover': '#2196F3',
            'color_accent_pressed': '#0D47A1',
            'color_accent_light_bg': '#E3F2FD',
            'color_accent_dark': '#0D47A1',
            'icon_filter': 'none'
        }
    }
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the ThemeManager.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        
        self._current_theme: str = 'default'
        self._auto_detect: bool = True
        self._styles_cache: Dict[str, str] = {}
        self._config_data: Optional[Dict] = None
        self._theme_changed_callbacks: List[Callable[[str], None]] = []
        self._child_dialog_filter: Optional['ChildDialogStyleFilter'] = None
    
    def add_theme_changed_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to be called when theme changes.
        
        Args:
            callback: Function that accepts theme name as parameter
        """
        if callback not in self._theme_changed_callbacks:
            self._theme_changed_callbacks.append(callback)
    
    def remove_theme_changed_callback(self, callback: Callable[[str], None]) -> None:
        """
        Remove a previously registered theme change callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._theme_changed_callbacks:
            self._theme_changed_callbacks.remove(callback)
    
    def _emit_theme_changed(self, theme: str) -> None:
        """Notify all registered callbacks of theme change."""
        for callback in self._theme_changed_callbacks:
            try:
                callback(theme)
            except Exception as e:
                logger.error(f"Error in theme change callback: {e}")
    
    @property
    def current_theme(self) -> str:
        """Get current active theme name."""
        return self._current_theme
    
    @property
    def is_dark_mode(self) -> bool:
        """Check if current theme is dark mode."""
        return self._current_theme == 'dark'
    
    def setup(self) -> None:
        """
        Initialize theme from QGIS settings or config.
        
        Auto-detects theme from QGIS if auto-detect is enabled.
        Installs event filter to protect child dialogs from style inheritance.
        """
        logger.debug(f"ThemeManager.setup(): STARTING, _auto_detect={self._auto_detect}")
        # Try to load config
        self._load_config()
        
        # Install event filter to protect child dialogs (Expression Builder, etc.)
        self._install_child_dialog_filter()
        
        # Detect and apply theme
        if self._auto_detect:
            detected = self.detect_system_theme()
            self._current_theme = detected
            logger.debug(f"ThemeManager.setup(): auto-detected theme = {detected}")
        
        logger.debug(f"ThemeManager.setup(): calling apply() with theme = {self._current_theme}")
        success = self.apply()
        if not success:
            logger.warning("ThemeManager: Initial theme application failed")
        self._initialized = True
        logger.info(f"ThemeManager initialized with theme: {self._current_theme} (success={success})")
    
    def _install_child_dialog_filter(self) -> None:
        """
        Install event filter to reset stylesheet on child dialogs.
        
        This prevents FilterMate's styles from affecting QGIS dialogs like
        QgsExpressionBuilderDialog that are created with dockwidget as parent.
        
        FIX 2026-01-21: Now uses GlobalDialogStyleFilter on QApplication
        to catch ALL dialogs, not just direct children of dockwidget.
        """
        try:
            # Install global filter on QApplication (catches all dialogs)
            GlobalDialogStyleFilter.install()
            logger.debug("Global dialog style filter installed via ThemeManager")
        except Exception as e:
            logger.warning(f"Could not install global dialog filter: {e}")
        except Exception as e:
            logger.warning(f"Could not install child dialog filter: {e}")
    
    def apply(self) -> bool:
        """
        Apply current theme to dockwidget.
        
        CRITICAL: The stylesheet uses #dockWidgetContents as prefix for scoping.
        We must apply it to the parent (QDockWidget) so that #dockWidgetContents
        selectors can match the child widget with that objectName.
        
        Qt CSS selector rules:
        - #id selectors match widgets by objectName
        - When stylesheet is set on widget X, selectors resolve from X's children
        - "#dockWidgetContents QComboBox" needs dockWidgetContents to be a CHILD
        
        Returns:
            bool: True if theme applied successfully, False otherwise
        """
        try:
            logger.info(f"ThemeManager.apply(): loading stylesheet for theme '{self._current_theme}'")
            stylesheet = self._load_stylesheet(self._current_theme)
            
            if not stylesheet:
                logger.error(f"ThemeManager.apply(): FAILED - No stylesheet loaded for theme '{self._current_theme}'")
                return False
            
            logger.info(f"ThemeManager.apply(): stylesheet loaded ({len(stylesheet)} chars)")
            
            # FIX 2026-02-02: Apply stylesheet to the QDockWidget (parent)
            # This allows #dockWidgetContents selectors to work correctly
            # because dockWidgetContents is a CHILD of the QDockWidget
            target_widget = self.dockwidget
            
            logger.info(f"ThemeManager.apply(): applying to '{target_widget.objectName()}' ({type(target_widget).__name__})")
            
            # Apply stylesheet to the QDockWidget
            target_widget.setStyleSheet(stylesheet)
            
            # Force update of dockWidgetContents and all its children
            contents = self.dockwidget.dockWidgetContents
            contents.update()
            contents.style().unpolish(contents)
            contents.style().polish(contents)
            
            # Also update all child widgets
            child_count = 0
            for child in contents.findChildren(QWidget):
                try:
                    child.style().unpolish(child)
                    child.style().polish(child)
                    child.update()
                    child_count += 1
                except (RuntimeError, AttributeError):
                    pass
            
            logger.info(f"ThemeManager.apply(): ✓ SUCCESS - Applied theme '{self._current_theme}' to {child_count} widgets")
            return True
        except Exception as e:
            logger.error(f"ThemeManager: Error applying theme '{self._current_theme}': {e}", exc_info=True)
            return False
    
    def set_theme(self, theme: str) -> None:
        """
        Set and apply a new theme.
        
        Args:
            theme: Theme name ('light', 'dark', 'default', 'auto')
        """
        if theme == 'auto':
            theme = self.detect_system_theme()
        
        if theme not in self.COLOR_SCHEMES:
            logger.warning(f"Unknown theme '{theme}', falling back to 'default'")
            theme = 'default'
        
        if theme != self._current_theme:
            old_theme = self._current_theme
            self._current_theme = theme
            success = self.apply()
            if success:
                self._emit_theme_changed(theme)
                logger.info(f"Theme changed from '{old_theme}' to '{theme}'")
            else:
                logger.error(f"Theme change from '{old_theme}' to '{theme}' FAILED - reverting")
                self._current_theme = old_theme  # Revert on failure
    
    def detect_system_theme(self) -> str:
        """
        Detect current QGIS theme.
        
        Analyzes QGIS palette luminance to determine dark/light mode.
        
        Returns:
            str: 'dark' if QGIS uses dark theme, 'default' for light theme
        """
        try:
            app = QgsApplication.instance()
            if app is None:
                return 'default'
            
            palette = app.palette()
            bg_color = palette.color(palette.Window)
            
            # Calculate luminance (perceived brightness)
            luminance = (0.299 * bg_color.red() + 
                        0.587 * bg_color.green() + 
                        0.114 * bg_color.blue())
            
            if luminance < 128:
                logger.debug(f"Detected QGIS dark theme (luminance: {luminance:.0f})")
                return 'dark'
            else:
                logger.debug(f"Detected QGIS light theme (luminance: {luminance:.0f})")
                return 'default'
                
        except Exception as e:
            logger.warning(f"Could not detect QGIS theme: {e}")
            return 'default'
    
    def on_theme_changed(self, theme: str) -> None:
        """
        Handle external theme change event.
        
        Args:
            theme: New theme name
        """
        self.set_theme(theme)
    
    def get_color(self, color_key: str) -> str:
        """
        Get a color value from current theme.
        
        Args:
            color_key: Color key name (e.g., 'color_accent')
        
        Returns:
            str: Color value (hex) or empty string if not found
        """
        colors = self.COLOR_SCHEMES.get(self._current_theme, {})
        return colors.get(color_key, '')
    
    def get_colors(self) -> Dict[str, str]:
        """
        Get all colors for current theme.
        
        Returns:
            Dict of color key -> color value
        """
        return self.COLOR_SCHEMES.get(self._current_theme, {}).copy()
    
    def get_available_themes(self) -> list:
        """
        Get list of available theme names.
        
        Returns:
            List of theme names
        """
        return list(self.COLOR_SCHEMES.keys())
    
    def clear_cache(self) -> None:
        """Clear stylesheet cache."""
        self._styles_cache.clear()
        logger.debug("Theme cache cleared")
    
    def _load_config(self) -> None:
        """Load configuration from dockwidget or config file."""
        try:
            # FIX 2026-02-02: Support both CONFIG_DATA (uppercase, actual attribute) 
            # and config_data (lowercase, for compatibility)
            config_data = None
            if hasattr(self.dockwidget, 'CONFIG_DATA'):
                config_data = self.dockwidget.CONFIG_DATA
            elif hasattr(self.dockwidget, 'config_data'):
                config_data = self.dockwidget.config_data
            
            if config_data:
                self._config_data = config_data
                
                # Check for auto-detect setting
                # Support both new structure (app.active_theme) and old (APP.DOCKWIDGET.COLORS.ACTIVE_THEME)
                # FIX 2026-02-02: Config values can be dict with 'value' key or plain string
                active_theme = config_data.get('app', {}).get('active_theme', None)
                if active_theme is None:
                    active_theme = config_data.get('APP', {}).get('DOCKWIDGET', {}).get('COLORS', {}).get('ACTIVE_THEME', 'auto')
                
                # Extract 'value' if active_theme is a dict (new config format)
                if isinstance(active_theme, dict):
                    active_theme = active_theme.get('value', 'auto')
                
                self._auto_detect = (active_theme == 'auto')
                if not self._auto_detect:
                    self._current_theme = active_theme
                logger.debug(f"ThemeManager: config loaded, active_theme={active_theme}, auto_detect={self._auto_detect}")
            else:
                logger.warning("ThemeManager: No config_data found on dockwidget")
        except Exception as e:
            logger.debug(f"Could not load theme config: {e}")
    
    def _load_stylesheet(self, theme: str) -> str:
        """
        Load QSS stylesheet for theme.
        
        Args:
            theme: Theme name
        
        Returns:
            Stylesheet content with colors applied
        """
        # Check cache first
        if theme in self._styles_cache:
            return self._styles_cache[theme]
        
        # Get raw stylesheet
        stylesheet = self._load_raw_stylesheet(theme)
        if not stylesheet:
            return ""
        
        # Apply colors
        colors = self.COLOR_SCHEMES.get(theme, self.COLOR_SCHEMES['default'])
        for key, value in colors.items():
            stylesheet = stylesheet.replace(f'{{{key}}}', value)
        
        # Check for unreplaced variables (debug)
        import re
        unreplaced = re.findall(r'\{[a-z_0-9]+\}', stylesheet)
        if unreplaced:
            logger.warning(f"Unreplaced variables in stylesheet: {set(unreplaced)}")
        
        # Cache result
        self._styles_cache[theme] = stylesheet
        
        return stylesheet
    
    def _load_raw_stylesheet(self, theme: str) -> str:
        """
        Load raw QSS file without color replacement.
        
        Args:
            theme: Theme name
        
        Returns:
            Raw stylesheet content
        """
        plugin_dir = self.get_plugin_dir()
        logger.info(f"_load_raw_stylesheet: plugin_dir = {plugin_dir}")
        
        if not plugin_dir:
            # Final fallback: use __file__ from this module
            try:
                current_file = os.path.abspath(__file__)
                # Go up from ui/styles/theme_manager.py to plugin root
                plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
                logger.info(f"_load_raw_stylesheet: fallback plugin_dir from __file__ = {plugin_dir}")
            except Exception as e:
                logger.error(f"_load_raw_stylesheet: CANNOT determine plugin_dir! {e}")
                return ""
        
        style_file = os.path.join(plugin_dir, 'resources', 'styles', f'{theme}.qss')
        logger.info(f"_load_raw_stylesheet: looking for {style_file}")
        
        # Fallback to default theme
        if not os.path.exists(style_file):
            style_file = os.path.join(plugin_dir, 'resources', 'styles', 'default.qss')
            logger.info(f"_load_raw_stylesheet: fallback to {style_file}")
        
        if not os.path.exists(style_file):
            logger.error(f"Stylesheet NOT FOUND: {style_file}")
            return ""
        
        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"_load_raw_stylesheet: ✓ Loaded {len(content)} chars from {os.path.basename(style_file)}")
                return content
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
            return ""
    
    def teardown(self) -> None:
        """Clean up resources."""
        # Remove event filter
        if self._child_dialog_filter is not None:
            try:
                self.dockwidget.removeEventFilter(self._child_dialog_filter)
                self._child_dialog_filter = None
                logger.debug("Child dialog style filter removed")
            except Exception as e:
                logger.debug(f"Could not remove event filter: {e}")
        
        self.clear_cache()
        self._theme_changed_callbacks.clear()
        super().teardown()
