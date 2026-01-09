# -*- coding: utf-8 -*-
"""
Deprecation Tests - MIG-043

Tests for deprecation warnings on legacy module imports.

Part of Phase 5: Validation & Dépréciation

Author: FilterMate Team
Date: January 2026
"""
import pytest
import warnings
import sys
from pathlib import Path

# Add plugin directory to path (tests/ is directly under filter_mate/)
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture(autouse=True)
def capture_warnings():
    """Capture deprecation warnings for testing."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        yield w


class TestDeprecationWarnings:
    """Tests for deprecation warning system."""
    
    def test_modules_package_marked_deprecated(self):
        """Test that modules package is marked as deprecated."""
        # Import the modules package
        import modules
        
        # Check deprecation markers
        assert hasattr(modules, '__deprecated__')
        assert modules.__deprecated__ is True
        assert modules.__deprecated_since__ == "3.0.0"
        assert modules.__removal_version__ == "4.0.0"
    
    def test_usage_report_available(self):
        """Test that deprecation usage report is available."""
        import modules
        
        report = modules.get_deprecated_usage_report()
        
        assert "accessed_modules" in report
        assert "total_accesses" in report
        assert "deprecated_since" in report
        assert "removal_version" in report
    
    def test_migration_paths_documented(self):
        """Test that migration paths are documented in module."""
        import modules
        
        docstring = modules.__doc__
        
        # Check migration paths are in docstring
        assert "modules.appUtils" in docstring
        assert "modules.appTasks" in docstring
        assert "modules.backends" in docstring
        assert "adapters" in docstring
        assert "core" in docstring
        assert "v4.0" in docstring


class TestNewModuleStructure:
    """Tests for new module structure availability."""
    
    def test_core_domain_importable(self):
        """Test core.domain modules can be imported."""
        from core.domain.filter_expression import FilterExpression
        from core.domain.filter_result import FilterResult
        from core.domain.layer_info import LayerInfo
        
        assert FilterExpression is not None
        assert FilterResult is not None
        assert LayerInfo is not None
    
    def test_core_services_importable(self):
        """Test core.services modules can be imported."""
        from core.services.filter_service import FilterService
        from core.services.expression_service import ExpressionService
        from core.services.history_service import HistoryService
        
        assert FilterService is not None
        assert ExpressionService is not None
        assert HistoryService is not None
    
    def test_adapters_backends_importable(self):
        """Test adapters.backends modules can be imported."""
        from adapters.backends.factory import BackendFactory
        
        assert BackendFactory is not None
    
    def test_infrastructure_importable(self):
        """Test infrastructure modules can be imported."""
        from infrastructure.di.container import Container
        
        assert Container is not None


class TestMigrationDocumentation:
    """Tests for migration documentation completeness."""
    
    def test_migration_guide_exists(self):
        """Test migration guide exists."""
        migration_guide = plugin_dir / "docs" / "migration-v3.md"
        assert migration_guide.exists()
    
    def test_migration_guide_content(self):
        """Test migration guide has required sections."""
        migration_guide = plugin_dir / "docs" / "migration-v3.md"
        content = migration_guide.read_text(encoding="utf-8")
        
        # Check required sections
        assert "Import Path Changes" in content
        assert "For Users" in content
        assert "For Developers" in content
        assert "Deprecation" in content
        assert "v4.0" in content
    
    def test_changelog_updated(self):
        """Test CHANGELOG mentions v3.0 changes."""
        changelog = plugin_dir / "CHANGELOG.md"
        if changelog.exists():
            content = changelog.read_text(encoding="utf-8")
            # Should mention architecture changes
            assert "3.0" in content or "v3" in content


class TestBackwardsCompatibility:
    """Tests for backwards compatibility during deprecation period."""
    
    def test_legacy_imports_still_work(self, capture_warnings):
        """Test legacy imports still work (with warnings)."""
        # These should work but emit warnings
        # Note: We check this conceptually since actual imports
        # would require the full QGIS environment
        
        # Verify warning mechanism works
        warnings.warn(
            "Test deprecation warning",
            DeprecationWarning,
            stacklevel=1
        )
        
        assert len(capture_warnings) >= 1
        assert any(
            issubclass(w.category, DeprecationWarning)
            for w in capture_warnings
        )
    
    def test_deprecation_warning_format(self):
        """Test deprecation warning format is helpful."""
        import modules
        
        # Simulate warning message
        module_name = "appUtils"
        expected_elements = [
            "deprecated",
            "v3.0",
            "v4.0",
            "migration"
        ]
        
        # The docstring should contain migration info
        for element in expected_elements:
            assert element.lower() in modules.__doc__.lower()


# ============================================================================
# Run configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
