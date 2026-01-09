"""
Tests for FavoritesService.

Story: MIG-076
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import json
import tempfile
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestFavoritesService:
    """Tests for FavoritesService class."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.add_favorite = Mock(return_value="fav_123")
        manager.remove_favorite = Mock(return_value=True)
        manager.update_favorite = Mock(return_value=True)
        manager.get_favorite = Mock(return_value=None)
        manager.get_all_favorites = Mock(return_value=[])
        manager.get_recent_favorites = Mock(return_value=[])
        manager.get_most_used_favorites = Mock(return_value=[])
        manager.search_favorites = Mock(return_value=[])
        manager.mark_favorite_used = Mock(return_value=True)
        manager.save_to_project = Mock()
        manager.load_from_database = Mock()
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        service = FavoritesService(favorites_manager=mock_manager)
        return service

    def test_creation(self, mock_manager):
        """Should create service without errors."""
        from core.services.favorites_service import FavoritesService
        service = FavoritesService(favorites_manager=mock_manager)
        
        assert service is not None
        assert service.favorites_manager is mock_manager

    def test_creation_without_manager(self):
        """Should create service without manager."""
        from core.services.favorites_service import FavoritesService
        service = FavoritesService()
        
        assert service is not None
        assert service.favorites_manager is None


class TestFavoriteCRUD:
    """Tests for favorite CRUD operations."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.add_favorite = Mock(return_value="fav_123")
        manager.remove_favorite = Mock(return_value=True)
        manager.update_favorite = Mock(return_value=True)
        manager.get_favorite = Mock(return_value=None)
        manager.get_favorite_by_name = Mock(return_value=None)
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        return FavoritesService(favorites_manager=mock_manager)

    def test_add_favorite(self, service, mock_manager):
        """Should add a favorite."""
        signals_received = []
        service.favorite_added.connect(
            lambda fid, name: signals_received.append((fid, name))
        )
        
        with patch('core.services.favorites_service.FilterFavorite') as mock_fav:
            mock_fav.return_value = Mock()
            result = service.add_favorite(
                name="Test Favorite",
                expression="field > 100"
            )
        
        assert result == "fav_123"
        assert len(signals_received) == 1
        assert signals_received[0] == ("fav_123", "Test Favorite")

    def test_add_favorite_without_manager(self):
        """Should return None when manager not initialized."""
        from core.services.favorites_service import FavoritesService
        service = FavoritesService()
        
        result = service.add_favorite(name="Test", expression="test")
        
        assert result is None

    def test_remove_favorite(self, service, mock_manager):
        """Should remove a favorite."""
        signals_received = []
        service.favorite_removed.connect(lambda fid: signals_received.append(fid))
        
        result = service.remove_favorite("fav_123")
        
        assert result is True
        mock_manager.remove_favorite.assert_called_once_with("fav_123")
        assert len(signals_received) == 1

    def test_update_favorite(self, service, mock_manager):
        """Should update a favorite."""
        signals_received = []
        service.favorite_updated.connect(
            lambda fid, name: signals_received.append((fid, name))
        )
        
        result = service.update_favorite("fav_123", name="Updated Name")
        
        assert result is True
        mock_manager.update_favorite.assert_called_once_with(
            "fav_123", name="Updated Name"
        )
        assert len(signals_received) == 1

    def test_get_favorite(self, service, mock_manager):
        """Should get a favorite by ID."""
        mock_fav = Mock()
        mock_fav.name = "Test"
        mock_manager.get_favorite.return_value = mock_fav
        
        result = service.get_favorite("fav_123")
        
        assert result is mock_fav
        mock_manager.get_favorite.assert_called_once_with("fav_123")


class TestFavoritesList:
    """Tests for favorites list operations."""

    @pytest.fixture
    def mock_favorites(self):
        """Create list of mock favorites."""
        fav1 = Mock()
        fav1.id = "fav_1"
        fav1.name = "Favorite 1"
        fav1.use_count = 5
        
        fav2 = Mock()
        fav2.id = "fav_2"
        fav2.name = "Favorite 2"
        fav2.use_count = 10
        
        return [fav1, fav2]

    @pytest.fixture
    def mock_manager(self, mock_favorites):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.get_all_favorites = Mock(return_value=mock_favorites)
        manager.get_recent_favorites = Mock(return_value=mock_favorites[:1])
        manager.get_most_used_favorites = Mock(return_value=[mock_favorites[1]])
        manager.search_favorites = Mock(return_value=mock_favorites)
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        return FavoritesService(favorites_manager=mock_manager)

    def test_get_all_favorites(self, service, mock_favorites):
        """Should get all favorites."""
        result = service.get_all_favorites()
        
        assert len(result) == 2
        assert result == mock_favorites

    def test_get_recent_favorites(self, service, mock_favorites):
        """Should get recent favorites."""
        result = service.get_recent_favorites(limit=1)
        
        assert len(result) == 1
        assert result[0] == mock_favorites[0]

    def test_get_most_used_favorites(self, service, mock_favorites):
        """Should get most used favorites."""
        result = service.get_most_used_favorites(limit=1)
        
        assert len(result) == 1
        assert result[0] == mock_favorites[1]

    def test_search_favorites(self, service, mock_favorites):
        """Should search favorites."""
        result = service.search_favorites("test")
        
        assert len(result) == 2

    def test_get_favorites_count(self, service, mock_favorites):
        """Should return count of favorites."""
        count = service.get_favorites_count()
        
        assert count == 2


class TestFavoriteApply:
    """Tests for applying favorites."""

    @pytest.fixture
    def mock_favorite(self):
        """Create mock FilterFavorite."""
        fav = Mock()
        fav.id = "fav_123"
        fav.name = "Test Favorite"
        fav.expression = "field > 100"
        fav.remote_layers = None
        return fav

    @pytest.fixture
    def mock_manager(self, mock_favorite):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.get_favorite = Mock(return_value=mock_favorite)
        manager.mark_favorite_used = Mock(return_value=True)
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        return FavoritesService(favorites_manager=mock_manager)

    def test_apply_favorite_success(self, service, mock_favorite):
        """Should apply favorite successfully."""
        callback_called = []
        service.set_callbacks(
            apply_expression=lambda expr, layer: callback_called.append(expr) or True
        )
        
        signals_received = []
        service.favorite_applied.connect(
            lambda fid, count: signals_received.append((fid, count))
        )
        
        result = service.apply_favorite("fav_123")
        
        assert result.success is True
        assert result.favorite_id == "fav_123"
        assert result.favorite_name == "Test Favorite"
        assert len(callback_called) == 1
        assert callback_called[0] == "field > 100"
        assert len(signals_received) == 1

    def test_apply_favorite_not_found(self, service, mock_manager):
        """Should fail when favorite not found."""
        mock_manager.get_favorite.return_value = None
        
        result = service.apply_favorite("nonexistent")
        
        assert result.success is False
        assert "not found" in result.error_message

    def test_mark_favorite_used(self, service, mock_manager):
        """Should mark favorite as used."""
        result = service.mark_favorite_used("fav_123")
        
        assert result is True
        mock_manager.mark_favorite_used.assert_called_once_with("fav_123")


class TestImportExport:
    """Tests for import/export operations."""

    @pytest.fixture
    def mock_favorites(self):
        """Create mock favorites."""
        fav = Mock()
        fav.id = "fav_123"
        fav.name = "Test"
        fav.to_dict = Mock(return_value={
            "id": "fav_123",
            "name": "Test",
            "expression": "field > 100"
        })
        return [fav]

    @pytest.fixture
    def mock_manager(self, mock_favorites):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.get_all_favorites = Mock(return_value=mock_favorites)
        manager.get_favorite = Mock(return_value=mock_favorites[0])
        manager.get_favorite_by_name = Mock(return_value=None)
        manager.add_favorite = Mock(return_value="fav_new")
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        return FavoritesService(favorites_manager=mock_manager)

    def test_export_favorites(self, service, mock_favorites):
        """Should export favorites to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            file_path = f.name
        
        try:
            signals_received = []
            service.favorites_exported.connect(
                lambda count, path: signals_received.append((count, path))
            )
            
            result = service.export_favorites(file_path)
            
            assert result.success is True
            assert result.favorites_count == 1
            assert len(signals_received) == 1
            
            # Verify file content
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            assert "favorites" in data
            assert len(data["favorites"]) == 1
            
        finally:
            Path(file_path).unlink(missing_ok=True)

    def test_import_favorites(self, service, mock_manager):
        """Should import favorites from file."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "version": "1.0",
                "favorites": [
                    {"name": "Imported", "expression": "test > 1"}
                ]
            }, f)
            file_path = f.name
        
        try:
            with patch('core.services.favorites_service.FilterFavorite') as mock_fav_class:
                mock_fav = Mock()
                mock_fav.id = None
                mock_fav_class.from_dict.return_value = mock_fav
                
                signals_received = []
                service.favorites_imported.connect(
                    lambda imp, skip: signals_received.append((imp, skip))
                )
                
                result = service.import_favorites(file_path)
                
                assert result.success is True
                assert result.imported_count == 1
                assert len(signals_received) == 1
                
        finally:
            Path(file_path).unlink(missing_ok=True)

    def test_import_skip_duplicates(self, service, mock_manager):
        """Should skip duplicate favorites on import."""
        # Make manager return existing favorite
        existing = Mock()
        existing.name = "Existing"
        mock_manager.get_favorite_by_name.return_value = existing
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "favorites": [
                    {"name": "Existing", "expression": "test > 1"}
                ]
            }, f)
            file_path = f.name
        
        try:
            result = service.import_favorites(file_path, skip_duplicates=True)
            
            assert result.success is True
            assert result.imported_count == 0
            assert result.skipped_count == 1
            
        finally:
            Path(file_path).unlink(missing_ok=True)


class TestStatistics:
    """Tests for favorites statistics."""

    @pytest.fixture
    def mock_favorites(self):
        """Create mock favorites with usage data."""
        fav1 = Mock()
        fav1.name = "Low Usage"
        fav1.use_count = 2
        
        fav2 = Mock()
        fav2.name = "High Usage"
        fav2.use_count = 15
        
        return [fav1, fav2]

    @pytest.fixture
    def mock_manager(self, mock_favorites):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.get_all_favorites = Mock(return_value=mock_favorites)
        manager.get_recent_favorites = Mock(return_value=[mock_favorites[1]])
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        return FavoritesService(favorites_manager=mock_manager)

    def test_get_statistics(self, service):
        """Should return statistics."""
        stats = service.get_statistics()
        
        assert stats["total_count"] == 2
        assert stats["total_uses"] == 17
        assert stats["most_used"] == "High Usage"
        assert stats["most_used_count"] == 15

    def test_get_statistics_empty(self, service, mock_manager):
        """Should handle empty favorites."""
        mock_manager.get_all_favorites.return_value = []
        
        stats = service.get_statistics()
        
        assert stats["total_count"] == 0
        assert stats["total_uses"] == 0
        assert stats["most_used"] is None


class TestSaveReload:
    """Tests for save/reload operations."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock FavoritesManager."""
        manager = Mock()
        manager.save_to_project = Mock()
        manager.load_from_database = Mock()
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        """Create FavoritesService instance."""
        from core.services.favorites_service import FavoritesService
        return FavoritesService(favorites_manager=mock_manager)

    def test_save(self, service, mock_manager):
        """Should save favorites."""
        result = service.save()
        
        assert result is True
        mock_manager.save_to_project.assert_called_once()

    def test_reload(self, service, mock_manager):
        """Should reload favorites."""
        signals_received = []
        service.favorites_changed.connect(lambda: signals_received.append(True))
        
        result = service.reload()
        
        assert result is True
        mock_manager.load_from_database.assert_called_once()
        assert len(signals_received) == 1
