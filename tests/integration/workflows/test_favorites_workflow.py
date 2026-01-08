# -*- coding: utf-8 -*-
"""
End-to-End Tests for Favorites Workflow - ARCH-050

Tests the complete favorites workflow: save, load, apply.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import json
import tempfile
from pathlib import Path
import sys

# Add plugin directory to path
plugin_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def favorites_controller_mock():
    """Create a mock favorites controller."""
    controller = MagicMock()
    
    # Storage
    controller._favorites = {}
    
    def save_favorite(name, config):
        controller._favorites[name] = config
        return MagicMock(success=True, name=name)
    
    def load_favorite(name):
        if name in controller._favorites:
            return MagicMock(
                success=True,
                name=name,
                config=controller._favorites[name]
            )
        return MagicMock(success=False, error_message=f"Favorite '{name}' not found")
    
    def delete_favorite(name):
        if name in controller._favorites:
            del controller._favorites[name]
            return MagicMock(success=True)
        return MagicMock(success=False)
    
    def list_favorites():
        return list(controller._favorites.keys())
    
    controller.save_favorite.side_effect = save_favorite
    controller.load_favorite.side_effect = load_favorite
    controller.delete_favorite.side_effect = delete_favorite
    controller.list_favorites.side_effect = list_favorites
    
    return controller


@pytest.fixture
def sample_filter_config():
    """Return a sample filter configuration."""
    return {
        "name": "Population Filter",
        "expression": '"population" > 10000',
        "spatial_predicate": "intersects",
        "buffer_distance": 100.0,
        "target_layers": ["layer_1", "layer_2"],
        "created_at": "2026-01-08T12:00:00",
        "version": "3.0.0"
    }


@pytest.mark.e2e
@pytest.mark.integration
class TestFavoritesWorkflowE2E:
    """E2E tests for the favorites workflow."""
    
    def test_save_and_load_favorite(
        self,
        favorites_controller_mock,
        sample_filter_config
    ):
        """Test saving and loading a favorite."""
        controller = favorites_controller_mock
        
        # Save favorite
        save_result = controller.save_favorite(
            "My Filter",
            sample_filter_config
        )
        assert save_result.success is True
        
        # Load favorite
        load_result = controller.load_favorite("My Filter")
        assert load_result.success is True
        assert load_result.config["expression"] == sample_filter_config["expression"]
    
    def test_list_favorites(
        self,
        favorites_controller_mock,
        sample_filter_config
    ):
        """Test listing all favorites."""
        controller = favorites_controller_mock
        
        # Save multiple favorites
        controller.save_favorite("Filter 1", sample_filter_config)
        controller.save_favorite("Filter 2", sample_filter_config)
        controller.save_favorite("Filter 3", sample_filter_config)
        
        # List
        favorites = controller.list_favorites()
        assert len(favorites) == 3
        assert "Filter 1" in favorites
        assert "Filter 2" in favorites
        assert "Filter 3" in favorites
    
    def test_delete_favorite(
        self,
        favorites_controller_mock,
        sample_filter_config
    ):
        """Test deleting a favorite."""
        controller = favorites_controller_mock
        
        # Save
        controller.save_favorite("To Delete", sample_filter_config)
        assert "To Delete" in controller.list_favorites()
        
        # Delete
        result = controller.delete_favorite("To Delete")
        assert result.success is True
        assert "To Delete" not in controller.list_favorites()
    
    def test_update_favorite(
        self,
        favorites_controller_mock,
        sample_filter_config
    ):
        """Test updating an existing favorite."""
        controller = favorites_controller_mock
        
        # Save initial
        controller.save_favorite("Updatable", sample_filter_config)
        
        # Update with new config
        updated_config = sample_filter_config.copy()
        updated_config["expression"] = '"population" > 50000'
        
        controller.save_favorite("Updatable", updated_config)
        
        # Verify updated
        load_result = controller.load_favorite("Updatable")
        assert load_result.config["expression"] == '"population" > 50000'
    
    def test_load_nonexistent_favorite(
        self,
        favorites_controller_mock
    ):
        """Test loading a favorite that doesn't exist."""
        controller = favorites_controller_mock
        
        result = controller.load_favorite("NonExistent")
        assert result.success is False
        assert "not found" in result.error_message


@pytest.mark.e2e
@pytest.mark.integration
class TestFavoritesApplyE2E:
    """E2E tests for applying favorites."""
    
    def test_apply_favorite_to_current_layer(
        self,
        favorites_controller_mock,
        sample_filter_config,
        sample_vector_layer
    ):
        """Test applying a favorite to the current layer."""
        controller = favorites_controller_mock
        
        # Save favorite
        controller.save_favorite("Apply Test", sample_filter_config)
        
        # Apply favorite
        controller.apply_favorite = MagicMock()
        apply_result = MagicMock()
        apply_result.success = True
        apply_result.matched_count = 50
        controller.apply_favorite.return_value = apply_result
        
        result = controller.apply_favorite("Apply Test", sample_vector_layer)
        assert result.success is True
    
    def test_apply_favorite_with_layer_substitution(
        self,
        favorites_controller_mock,
        sample_filter_config,
        postgresql_layer,
        spatialite_layer
    ):
        """Test applying favorite with different layers."""
        controller = favorites_controller_mock
        
        # Original favorite with PostgreSQL layer
        config_postgres = sample_filter_config.copy()
        config_postgres["source_layer"] = postgresql_layer.id()
        
        controller.save_favorite("Substitute Test", config_postgres)
        
        # Apply to Spatialite layer
        controller.apply_favorite = MagicMock()
        apply_result = MagicMock()
        apply_result.success = True
        apply_result.layer_substituted = True
        controller.apply_favorite.return_value = apply_result
        
        result = controller.apply_favorite(
            "Substitute Test",
            spatialite_layer,
            substitute_layers=True
        )
        assert result.success is True


@pytest.mark.e2e
@pytest.mark.integration
class TestFavoritesImportExportE2E:
    """E2E tests for favorites import/export."""
    
    def test_export_favorites_to_file(
        self,
        favorites_controller_mock,
        sample_filter_config
    ):
        """Test exporting favorites to a JSON file."""
        controller = favorites_controller_mock
        
        # Save some favorites
        controller.save_favorite("Export 1", sample_filter_config)
        controller.save_favorite("Export 2", sample_filter_config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "favorites.json"
            
            # Export
            controller.export_favorites = MagicMock()
            export_result = MagicMock()
            export_result.success = True
            export_result.exported_count = 2
            export_result.path = str(export_path)
            controller.export_favorites.return_value = export_result
            
            result = controller.export_favorites(str(export_path))
            assert result.success is True
            assert result.exported_count == 2
    
    def test_import_favorites_from_file(
        self,
        favorites_controller_mock
    ):
        """Test importing favorites from a JSON file."""
        controller = favorites_controller_mock
        
        # Create test file
        favorites_data = {
            "Import 1": {"expression": '"test" = 1'},
            "Import 2": {"expression": '"test" = 2'}
        }
        
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(favorites_data, f)
            import_path = f.name
        
        # Import
        controller.import_favorites = MagicMock()
        import_result = MagicMock()
        import_result.success = True
        import_result.imported_count = 2
        import_result.duplicates_skipped = 0
        controller.import_favorites.return_value = import_result
        
        result = controller.import_favorites(import_path)
        assert result.success is True
        assert result.imported_count == 2
    
    def test_import_with_duplicate_handling(
        self,
        favorites_controller_mock,
        sample_filter_config
    ):
        """Test import handles duplicates correctly."""
        controller = favorites_controller_mock
        
        # Save existing favorite
        controller.save_favorite("Existing", sample_filter_config)
        
        # Import containing duplicate
        controller.import_favorites = MagicMock()
        import_result = MagicMock()
        import_result.success = True
        import_result.imported_count = 1
        import_result.duplicates_skipped = 1
        import_result.skipped_names = ["Existing"]
        controller.import_favorites.return_value = import_result
        
        result = controller.import_favorites("test.json", skip_duplicates=True)
        assert result.duplicates_skipped == 1
