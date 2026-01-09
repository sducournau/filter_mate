---
storyId: MIG-067
title: IconManager Extraction
epic: 6.2 - Styling Managers Extraction
phase: 6
sprint: 6
priority: P1
status: DONE
effort: 0.5 day
assignee: null
dependsOn: [MIG-065]
blocks: [MIG-070]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-067: IconManager Extraction

## 📋 Story

**En tant que** développeur,  
**Je veux** centraliser la gestion des icônes dans un manager dédié,  
**Afin que** les icônes s'adaptent au thème automatiquement et réduire le God Class.

---

## 🎯 Objectif

Extraire les méthodes de gestion des icônes de `filter_mate_dockwidget.py` (lignes 5785-5863, 6444-6500) vers `ui/styling/icon_manager.py`:

| Méthode                      | Lignes    | Responsabilité               |
| ---------------------------- | --------- | ---------------------------- |
| `set_widget_icon()`          | 5785-5820 | Définir icône sur widget     |
| `switch_widget_icon()`       | 5822-5850 | Changer icône selon état     |
| `icon_per_geometry_type()`   | 5852-5863 | Icône selon type géométrie   |
| `_refresh_icons_for_theme()` | 6444-6500 | Rafraîchir icônes pour thème |

**Réduction estimée:** ~135 lignes

---

## ✅ Critères d'Acceptation

### Extraction

- [ ] `IconManager` implémente les 4 méthodes
- [ ] Hérite de `StylerBase`
- [ ] Fichier < 200 lignes

### Icônes Adaptatives

- [ ] Icônes dark pour thème clair
- [ ] Icônes light pour thème sombre
- [ ] Changement automatique avec le thème

### Types de Géométrie

- [ ] Icône Point
- [ ] Icône Line
- [ ] Icône Polygon
- [ ] Icône NoGeometry / Table
- [ ] Icône Unknown

### Intégration

- [ ] Intégration avec `IconThemeManager` existant
- [ ] Écoute les changements de thème
- [ ] Cache des icônes pour performance

### Tests

- [ ] Tests unitaires pour `IconManager`
- [ ] Tests par type de géométrie
- [ ] Tests de switch thème

---

## 🏗️ Fichier Cible

### `ui/styling/icon_manager.py`

```python
"""
Icon Manager for FilterMate.

Manages icons for widgets, adapting to theme and geometry type.
Extracted from filter_mate_dockwidget.py (lines 5785-5863, 6444-6500).

Story: MIG-067
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict
from enum import Enum
import logging

from qgis.PyQt.QtWidgets import QWidget, QPushButton, QToolButton
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsWkbTypes

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from config.config import UIConfig

logger = logging.getLogger(__name__)


class GeometryIconType(Enum):
    """Geometry type for icon selection."""
    POINT = "point"
    LINE = "line"
    POLYGON = "polygon"
    NO_GEOMETRY = "no_geometry"
    UNKNOWN = "unknown"


class IconManager(StylerBase):
    """
    Manages icons for FilterMate widgets.

    Handles:
    - Theme-adaptive icons (dark/light variants)
    - Geometry-type icons
    - Icon caching for performance
    - Dynamic icon switching

    Attributes:
        dockwidget: Reference to the parent dockwidget
        config: UI configuration
        _icon_cache: Cache of loaded icons
        _icon_theme_manager: Reference to IconThemeManager
    """

    def __init__(
        self,
        dockwidget: "FilterMateDockWidget",
        config: Optional["UIConfig"] = None
    ) -> None:
        """
        Initialize IconManager.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            config: Optional UI configuration
        """
        super().__init__(dockwidget, config)
        self._icon_cache: Dict[str, QIcon] = {}
        self._icon_theme_manager = None
        self._setup_icon_theme_manager()

    def _setup_icon_theme_manager(self) -> None:
        """Setup IconThemeManager integration."""
        try:
            from modules.appIcons import IconThemeManager
            self._icon_theme_manager = IconThemeManager.instance()
        except ImportError:
            logger.warning("IconThemeManager not available")

    def apply(self) -> None:
        """
        Apply icons to all widgets.

        Refreshes all icons based on current theme.
        """
        self._refresh_icons_for_theme()

    def set_widget_icon(
        self,
        widget: QWidget,
        icon_name: str,
        size: Optional[tuple] = None
    ) -> None:
        """
        Set icon on a widget.

        Args:
            widget: Target widget (QPushButton, QToolButton, etc.)
            icon_name: Base name of icon (without theme suffix)
            size: Optional icon size as (width, height)
        """
        # TODO: Extract from lines 5785-5820
        raise NotImplementedError("Pending extraction from dockwidget")

    def switch_widget_icon(
        self,
        widget: QWidget,
        icon_name: str,
        state: bool
    ) -> None:
        """
        Switch widget icon based on state.

        Args:
            widget: Target widget
            icon_name: Base name of icon
            state: True for active/on, False for inactive/off
        """
        # TODO: Extract from lines 5822-5850
        raise NotImplementedError("Pending extraction from dockwidget")

    def icon_per_geometry_type(
        self,
        geometry_type: int
    ) -> QIcon:
        """
        Get icon for geometry type.

        Args:
            geometry_type: QgsWkbTypes geometry type

        Returns:
            QIcon for the geometry type
        """
        # TODO: Extract from lines 5852-5863
        icon_type = self._geometry_to_icon_type(geometry_type)
        return self._get_geometry_icon(icon_type)

    def _geometry_to_icon_type(self, geometry_type: int) -> GeometryIconType:
        """
        Convert QgsWkbTypes to GeometryIconType.

        Args:
            geometry_type: QgsWkbTypes value

        Returns:
            Corresponding GeometryIconType
        """
        geom_type = QgsWkbTypes.geometryType(geometry_type)

        if geom_type == QgsWkbTypes.PointGeometry:
            return GeometryIconType.POINT
        elif geom_type == QgsWkbTypes.LineGeometry:
            return GeometryIconType.LINE
        elif geom_type == QgsWkbTypes.PolygonGeometry:
            return GeometryIconType.POLYGON
        elif geom_type == QgsWkbTypes.NullGeometry:
            return GeometryIconType.NO_GEOMETRY
        else:
            return GeometryIconType.UNKNOWN

    def _get_geometry_icon(self, icon_type: GeometryIconType) -> QIcon:
        """
        Get cached icon for geometry type.

        Args:
            icon_type: GeometryIconType enum value

        Returns:
            QIcon for the type
        """
        cache_key = f"geometry_{icon_type.value}"

        if cache_key not in self._icon_cache:
            icon_name = f"mIconGeometry{icon_type.value.title()}"
            self._icon_cache[cache_key] = self._load_icon(icon_name)

        return self._icon_cache[cache_key]

    def _load_icon(self, icon_name: str) -> QIcon:
        """
        Load icon by name, respecting current theme.

        Args:
            icon_name: Icon name

        Returns:
            QIcon instance
        """
        if self._icon_theme_manager:
            return self._icon_theme_manager.get_icon(icon_name)

        # Fallback: load from resources
        from qgis.PyQt.QtGui import QIcon
        return QIcon(f":/plugins/filter_mate/icons/{icon_name}.svg")

    def _refresh_icons_for_theme(self) -> None:
        """
        Refresh all icons for current theme.

        Called when theme changes to update all widget icons.
        """
        # TODO: Extract from lines 6444-6500
        logger.debug("Refreshing icons for theme")

        # Clear cache to force reload
        self._icon_cache.clear()

        # Refresh all registered widgets
        # Implementation pending extraction
        raise NotImplementedError("Pending extraction from dockwidget")

    def clear_cache(self) -> None:
        """Clear icon cache."""
        self._icon_cache.clear()
        logger.debug("Icon cache cleared")

    def on_theme_changed(self, theme_name: str) -> None:
        """
        Handle theme change event.

        Args:
            theme_name: New theme name
        """
        logger.info(f"Theme changed to {theme_name}, refreshing icons")
        self._refresh_icons_for_theme()
```

---

## 🧪 Tests Requis

### `tests/unit/ui/styling/test_icon_manager.py`

```python
"""Unit tests for IconManager."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ui.styling.icon_manager import IconManager, GeometryIconType


class TestGeometryIconType:
    """Test GeometryIconType enum."""

    def test_all_types_defined(self):
        """Verify all geometry types are defined."""
        assert GeometryIconType.POINT.value == "point"
        assert GeometryIconType.LINE.value == "line"
        assert GeometryIconType.POLYGON.value == "polygon"
        assert GeometryIconType.NO_GEOMETRY.value == "no_geometry"
        assert GeometryIconType.UNKNOWN.value == "unknown"


class TestIconManager:
    """Test suite for IconManager."""

    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        return Mock()

    @pytest.fixture
    def manager(self, mock_dockwidget):
        """Create IconManager instance."""
        with patch.object(IconManager, '_setup_icon_theme_manager'):
            return IconManager(mock_dockwidget, {})

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager._icon_cache == {}

    def test_clear_cache(self, manager):
        """Test clearing icon cache."""
        manager._icon_cache["test"] = Mock()
        manager.clear_cache()
        assert manager._icon_cache == {}

    def test_geometry_to_icon_type_point(self, manager):
        """Test geometry type conversion for Point."""
        with patch('ui.styling.icon_manager.QgsWkbTypes') as mock_wkb:
            mock_wkb.geometryType.return_value = mock_wkb.PointGeometry
            mock_wkb.PointGeometry = 0

            result = manager._geometry_to_icon_type(1)
            assert result == GeometryIconType.POINT

    def test_geometry_to_icon_type_line(self, manager):
        """Test geometry type conversion for Line."""
        with patch('ui.styling.icon_manager.QgsWkbTypes') as mock_wkb:
            mock_wkb.geometryType.return_value = mock_wkb.LineGeometry
            mock_wkb.LineGeometry = 1

            result = manager._geometry_to_icon_type(2)
            assert result == GeometryIconType.LINE

    def test_geometry_to_icon_type_polygon(self, manager):
        """Test geometry type conversion for Polygon."""
        with patch('ui.styling.icon_manager.QgsWkbTypes') as mock_wkb:
            mock_wkb.geometryType.return_value = mock_wkb.PolygonGeometry
            mock_wkb.PolygonGeometry = 2

            result = manager._geometry_to_icon_type(3)
            assert result == GeometryIconType.POLYGON

    def test_on_theme_changed_refreshes_icons(self, manager):
        """Test theme change triggers icon refresh."""
        manager._refresh_icons_for_theme = Mock()
        manager.on_theme_changed("dark")
        manager._refresh_icons_for_theme.assert_called_once()


class TestIconManagerCaching:
    """Test icon caching behavior."""

    @pytest.fixture
    def manager(self):
        """Create IconManager with mocked dependencies."""
        with patch.object(IconManager, '_setup_icon_theme_manager'):
            manager = IconManager(Mock(), {})
            manager._load_icon = Mock(return_value=Mock())
            return manager

    def test_geometry_icon_cached(self, manager):
        """Test that geometry icons are cached."""
        # First call loads icon
        manager._get_geometry_icon(GeometryIconType.POINT)

        # Second call uses cache
        manager._get_geometry_icon(GeometryIconType.POINT)

        # _load_icon called only once
        assert manager._load_icon.call_count == 1

    def test_different_geometry_types_cached_separately(self, manager):
        """Test different geometry types have separate cache entries."""
        manager._get_geometry_icon(GeometryIconType.POINT)
        manager._get_geometry_icon(GeometryIconType.LINE)

        assert "geometry_point" in manager._icon_cache
        assert "geometry_line" in manager._icon_cache
```

---

## 📋 Checklist de Complétion

### Avant Développement

- [ ] MIG-065 (Styling Module Structure) complété
- [ ] Revue du code source lignes 5785-5863, 6444-6500
- [ ] `IconThemeManager` analysé

### Développement

- [ ] Fichier `icon_manager.py` créé
- [ ] `GeometryIconType` enum défini
- [ ] 4 méthodes extraites et adaptées
- [ ] Cache d'icônes implémenté
- [ ] Type hints complets

### Post-Développement

- [ ] Tests unitaires passent
- [ ] Tests de régression passent
- [ ] Review de code approuvée

---

## 🔗 Références

- **Epic:** [epics.md](../epics.md#epic-62-styling-managers-extraction)
- **Code Source:** `filter_mate_dockwidget.py` lignes 5785-5863, 6444-6500
- **Existant:** `IconThemeManager`, `modules/appIcons.py`
- **Dépendance:** MIG-065 (Styling Module Structure)
- **Bloque:** MIG-070 (ConfigController)

---

_Story créée par 🧙 BMad Master - 9 janvier 2026_
