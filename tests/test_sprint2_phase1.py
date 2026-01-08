"""
Unit tests for Sprint 2 Phase 1 implementations.

Tests cover:
- ARCH-003: FavoritesWidget
- ARCH-004: FavoritesManagerDialog
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockFavorite:
    """Mock FilterFavorite for testing."""
    
    def __init__(self, id="fav_001", name="Test Favorite", expression="field = 'value'"):
        self.id = id
        self.name = name
        self.expression = expression
        self.layer_name = "test_layer"
        self.layer_provider = "ogr"
        self.description = "Test description"
        self.tags = ["test", "sample"]
        self.use_count = 5
        self.created_at = "2026-01-08 12:00:00"
        self.remote_layers = {}
    
    def get_layers_count(self):
        return 1 + len(self.remote_layers)
    
    def get_display_name(self, max_len=25):
        return self.name[:max_len]
    
    def get_preview(self, max_len=80):
        return self.expression[:max_len]


class MockFavoritesManager:
    """Mock FavoritesManager for testing."""
    
    def __init__(self):
        self._favorites = {
            "fav_001": MockFavorite("fav_001", "Urban Filter", "type = 'urban'"),
            "fav_002": MockFavorite("fav_002", "Population Filter", "population > 1000"),
        }
    
    @property
    def count(self):
        return len(self._favorites)
    
    def get_all_favorites(self):
        return list(self._favorites.values())
    
    def get_recent_favorites(self, limit=10):
        return list(self._favorites.values())[:limit]
    
    def get_favorite(self, favorite_id):
        return self._favorites.get(favorite_id)
    
    def search_favorites(self, query):
        return [f for f in self._favorites.values() if query.lower() in f.name.lower()]
    
    def add_favorite(self, fav):
        self._favorites[fav.id] = fav
    
    def remove_favorite(self, favorite_id):
        if favorite_id in self._favorites:
            del self._favorites[favorite_id]
    
    def update_favorite(self, favorite_id, **kwargs):
        if favorite_id in self._favorites:
            fav = self._favorites[favorite_id]
            for key, value in kwargs.items():
                setattr(fav, key, value)
    
    def mark_favorite_used(self, favorite_id):
        if favorite_id in self._favorites:
            self._favorites[favorite_id].use_count += 1
    
    def save_to_project(self):
        pass
    
    def export_to_file(self, filepath):
        return True
    
    def import_from_file(self, filepath, merge=True):
        return 1


class TestFavoritesWidget(unittest.TestCase):
    """Test cases for FavoritesWidget."""
    
    def test_import(self):
        """Test FavoritesWidget can be imported."""
        from ui.widgets.favorites_widget import FavoritesWidget
        self.assertIsNotNone(FavoritesWidget)
    
    def test_initialization(self):
        """Test widget initialization without QGIS."""
        from ui.widgets.favorites_widget import FavoritesWidget, HAS_QGIS
        
        manager = MockFavoritesManager()
        
        # Without QGIS, widget should still instantiate
        widget = FavoritesWidget(
            favorites_manager=manager,
            get_current_expression_func=lambda: "test = 'value'",
            get_current_layer_func=lambda: None
        )
        
        self.assertIsNotNone(widget)
        self.assertEqual(widget._favorites_manager, manager)
    
    def test_favorites_count_property(self):
        """Test favorites_count property."""
        from ui.widgets.favorites_widget import FavoritesWidget
        
        manager = MockFavoritesManager()
        widget = FavoritesWidget(favorites_manager=manager)
        
        self.assertEqual(widget.favorites_count, 2)
    
    def test_set_favorites_manager(self):
        """Test setting favorites manager."""
        from ui.widgets.favorites_widget import FavoritesWidget
        
        widget = FavoritesWidget(favorites_manager=None)
        self.assertEqual(widget.favorites_count, 0)
        
        manager = MockFavoritesManager()
        widget.set_favorites_manager(manager)
        
        self.assertEqual(widget.favorites_count, 2)
    
    def test_generate_description(self):
        """Test description generation."""
        from ui.widgets.favorites_widget import FavoritesWidget
        
        widget = FavoritesWidget(favorites_manager=MockFavoritesManager())
        
        description = widget._generate_description(
            source_layer_name="cities",
            expression="population > 10000",
            remote_layers={"roads": {"feature_count": 100}}
        )
        
        self.assertIn("cities", description)
        self.assertIn("population > 10000", description)
        self.assertIn("roads", description)
        self.assertIn("Remote layers (1)", description)


class TestFavoritesManagerDialog(unittest.TestCase):
    """Test cases for FavoritesManagerDialog."""
    
    def test_import(self):
        """Test FavoritesManagerDialog can be imported."""
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        self.assertIsNotNone(FavoritesManagerDialog)
    
    def test_initialization(self):
        """Test dialog initialization without QGIS."""
        from ui.dialogs.favorites_manager import FavoritesManagerDialog, HAS_QGIS
        
        manager = MockFavoritesManager()
        
        # Without QGIS, dialog should still instantiate
        dialog = FavoritesManagerDialog(favorites_manager=manager)
        
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog._favorites_manager, manager)
    
    def test_current_fav_id_initial(self):
        """Test initial state of current favorite ID."""
        from ui.dialogs.favorites_manager import FavoritesManagerDialog
        
        manager = MockFavoritesManager()
        dialog = FavoritesManagerDialog(favorites_manager=manager)
        
        self.assertIsNone(dialog._current_fav_id)


class TestPackageExports(unittest.TestCase):
    """Test that packages export correctly."""
    
    def test_ui_widgets_export(self):
        """Test ui.widgets exports FavoritesWidget."""
        from ui.widgets import FavoritesWidget
        self.assertIsNotNone(FavoritesWidget)
    
    def test_ui_dialogs_export(self):
        """Test ui.dialogs exports FavoritesManagerDialog."""
        from ui.dialogs import FavoritesManagerDialog
        self.assertIsNotNone(FavoritesManagerDialog)


class TestMockFavorite(unittest.TestCase):
    """Test MockFavorite works correctly for testing."""
    
    def test_mock_favorite_creation(self):
        """Test mock favorite creates properly."""
        fav = MockFavorite("test_id", "Test Name", "field = 1")
        
        self.assertEqual(fav.id, "test_id")
        self.assertEqual(fav.name, "Test Name")
        self.assertEqual(fav.expression, "field = 1")
        self.assertEqual(fav.get_layers_count(), 1)
    
    def test_mock_favorite_with_remote_layers(self):
        """Test mock favorite with remote layers."""
        fav = MockFavorite()
        fav.remote_layers = {"layer1": {}, "layer2": {}}
        
        self.assertEqual(fav.get_layers_count(), 3)


class TestMockFavoritesManager(unittest.TestCase):
    """Test MockFavoritesManager works correctly."""
    
    def test_manager_count(self):
        """Test manager count property."""
        manager = MockFavoritesManager()
        self.assertEqual(manager.count, 2)
    
    def test_manager_get_all(self):
        """Test getting all favorites."""
        manager = MockFavoritesManager()
        all_favs = manager.get_all_favorites()
        
        self.assertEqual(len(all_favs), 2)
    
    def test_manager_get_by_id(self):
        """Test getting favorite by ID."""
        manager = MockFavoritesManager()
        fav = manager.get_favorite("fav_001")
        
        self.assertIsNotNone(fav)
        self.assertEqual(fav.name, "Urban Filter")
    
    def test_manager_search(self):
        """Test searching favorites."""
        manager = MockFavoritesManager()
        results = manager.search_favorites("urban")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Urban Filter")
    
    def test_manager_add_favorite(self):
        """Test adding a favorite."""
        manager = MockFavoritesManager()
        new_fav = MockFavorite("fav_new", "New Filter", "new = 1")
        
        manager.add_favorite(new_fav)
        
        self.assertEqual(manager.count, 3)
        self.assertIsNotNone(manager.get_favorite("fav_new"))
    
    def test_manager_remove_favorite(self):
        """Test removing a favorite."""
        manager = MockFavoritesManager()
        
        manager.remove_favorite("fav_001")
        
        self.assertEqual(manager.count, 1)
        self.assertIsNone(manager.get_favorite("fav_001"))
    
    def test_manager_update_favorite(self):
        """Test updating a favorite."""
        manager = MockFavoritesManager()
        
        manager.update_favorite("fav_001", name="Updated Name")
        
        fav = manager.get_favorite("fav_001")
        self.assertEqual(fav.name, "Updated Name")


if __name__ == '__main__':
    unittest.main(verbosity=2)
