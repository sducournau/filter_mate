# -*- coding: utf-8 -*-
"""
QGIS Theme Watcher for FilterMate.

Watches for QGIS theme changes and notifies subscribers.

Migrated from modules/ui_styles.py (v4.0 Architecture Cleanup)
Story: MIG-090 - Final modules/ removal

Author: FilterMate Team
Date: January 2026
"""

import logging
from qgis.core import QgsApplication

logger = logging.getLogger(__name__)


class QGISThemeWatcher:
    """
    Watches for QGIS theme changes and notifies subscribers.

    Connects to QApplication palette change signal to detect
    when user changes QGIS theme (e.g., Night Mapping).

    Usage:
        watcher = QGISThemeWatcher()
        watcher.theme_changed.connect(my_handler)
        watcher.start_watching()
    """

    _instance = None
    _callbacks = []
    _last_theme = None
    _is_watching = False

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'QGISThemeWatcher':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start_watching(self) -> bool:
        """
        Start watching for QGIS theme changes.

        Connects to QApplication paletteChanged signal.

        Returns:
            bool: True if successfully started
        """
        if self._is_watching:
            return True

        try:
            # Import StyleLoader here to avoid circular import
            from .style_loader import StyleLoader

            app = QgsApplication.instance()
            if app:
                app.paletteChanged.connect(self._on_palette_changed)
                self._last_theme = StyleLoader.detect_qgis_theme()
                self._is_watching = True
                logger.info(f"QGISThemeWatcher started (current theme: {self._last_theme})")
                return True
        except Exception as e:
            logger.error(f"Failed to start QGISThemeWatcher: {e}")

        return False

    def stop_watching(self) -> None:
        """Stop watching for theme changes."""
        if not self._is_watching:
            return

        try:
            app = QgsApplication.instance()
            if app:
                app.paletteChanged.disconnect(self._on_palette_changed)
        except Exception:
            pass

        self._is_watching = False
        logger.info("QGISThemeWatcher stopped")

    def add_callback(self, callback) -> None:
        """
        Add a callback to be called when theme changes.

        Args:
            callback: Function(new_theme: str) to call
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _on_palette_changed(self, palette) -> None:
        """Handle palette change from QGIS."""
        # Import here to avoid circular import
        from .style_loader import StyleLoader

        new_theme = StyleLoader.detect_qgis_theme()

        if new_theme != self._last_theme:
            logger.info(f"QGIS theme changed: {self._last_theme} -> {new_theme}")
            self._last_theme = new_theme

            # Update StyleLoader current theme
            StyleLoader._current_theme = new_theme
            StyleLoader.clear_cache()

            # Sync icon theme
            StyleLoader.sync_icon_theme()

            # Notify all callbacks
            for callback in self._callbacks:
                try:
                    callback(new_theme)
                except Exception as e:
                    logger.error(f"Error in theme change callback: {e}")

    @property
    def current_theme(self) -> str:
        """Get the current detected theme."""
        if self._last_theme:
            return self._last_theme

        # Import here to avoid circular import
        from .style_loader import StyleLoader
        return StyleLoader.detect_qgis_theme()

    @property
    def is_watching(self) -> bool:
        """Check if watcher is active."""
        return self._is_watching
