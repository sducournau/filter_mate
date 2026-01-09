"""
Phase 6 Regression Tests - Layout Managers.

Story: MIG-089
Tests for Sprint 6 (Layout & Styling) components.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path
plugin_path = Path(__file__).parents[3]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


# ─────────────────────────────────────────────────────────────────
# Mock Classes
# ─────────────────────────────────────────────────────────────────

class MockWidget:
    """Mock widget for testing."""
    
    def __init__(self, name: str = "widget"):
        self.name = name
        self.visible = True
        self.enabled = True
        self.width = 100
        self.height = 50
        self.stylesheet = ""
    
    def show(self):
        self.visible = True
    
    def hide(self):
        self.visible = False
    
    def setEnabled(self, enabled):
        self.enabled = enabled
    
    def setMinimumWidth(self, w):
        self.width = max(w, self.width)
    
    def setMinimumHeight(self, h):
        self.height = max(h, self.height)
    
    def setStyleSheet(self, ss):
        self.stylesheet = ss


class MockDockWidget:
    """Mock dockwidget with common widgets."""
    
    def __init__(self):
        self.splitter_main = MockWidget("splitter_main")
        self.splitter_filtering = MockWidget("splitter_filtering")
        self.groupBox_filtering = MockWidget("groupBox_filtering")
        self.groupBox_exploring = MockWidget("groupBox_exploring")
        self.pushButton_apply = MockWidget("pushButton_apply")


# ─────────────────────────────────────────────────────────────────
# Test SplitterManager
# ─────────────────────────────────────────────────────────────────

class TestSplitterManagerRegression:
    """Regression tests for SplitterManager."""
    
    def test_import(self):
        """Test SplitterManager can be imported."""
        from ui.layout import SplitterManager
        assert SplitterManager is not None
    
    def test_init(self):
        """Test SplitterManager initialization."""
        from ui.layout import SplitterManager
        dw = MockDockWidget()
        
        manager = SplitterManager(dw)
        
        assert manager is not None
    
    def test_setup_method_exists(self):
        """Test setup method exists."""
        from ui.layout import SplitterManager
        dw = MockDockWidget()
        manager = SplitterManager(dw)
        
        assert hasattr(manager, 'setup')
        assert callable(manager.setup)
    
    def test_teardown_method_exists(self):
        """Test teardown method exists."""
        from ui.layout import SplitterManager
        dw = MockDockWidget()
        manager = SplitterManager(dw)
        
        assert hasattr(manager, 'teardown')
        assert callable(manager.teardown)


# ─────────────────────────────────────────────────────────────────
# Test DimensionsManager
# ─────────────────────────────────────────────────────────────────

class TestDimensionsManagerRegression:
    """Regression tests for DimensionsManager."""
    
    def test_import(self):
        """Test DimensionsManager can be imported."""
        from ui.layout import DimensionsManager
        assert DimensionsManager is not None
    
    def test_init(self):
        """Test DimensionsManager initialization."""
        from ui.layout import DimensionsManager
        dw = MockDockWidget()
        
        manager = DimensionsManager(dw)
        
        assert manager is not None


# ─────────────────────────────────────────────────────────────────
# Test SpacingManager
# ─────────────────────────────────────────────────────────────────

class TestSpacingManagerRegression:
    """Regression tests for SpacingManager."""
    
    def test_import(self):
        """Test SpacingManager can be imported."""
        from ui.layout import SpacingManager
        assert SpacingManager is not None
    
    def test_init(self):
        """Test SpacingManager initialization."""
        from ui.layout import SpacingManager
        dw = MockDockWidget()
        
        manager = SpacingManager(dw)
        
        assert manager is not None


# ─────────────────────────────────────────────────────────────────
# Test ActionBarManager
# ─────────────────────────────────────────────────────────────────

class TestActionBarManagerRegression:
    """Regression tests for ActionBarManager."""
    
    def test_import(self):
        """Test ActionBarManager can be imported."""
        from ui.layout import ActionBarManager
        assert ActionBarManager is not None
    
    def test_init(self):
        """Test ActionBarManager initialization."""
        from ui.layout import ActionBarManager
        dw = MockDockWidget()
        
        manager = ActionBarManager(dw)
        
        assert manager is not None


# ─────────────────────────────────────────────────────────────────
# Test ThemeManager
# ─────────────────────────────────────────────────────────────────

class TestThemeManagerRegression:
    """Regression tests for ThemeManager."""
    
    def test_import(self):
        """Test ThemeManager can be imported."""
        from ui.styles import ThemeManager
        assert ThemeManager is not None
    
    def test_init(self):
        """Test ThemeManager initialization."""
        from ui.styles import ThemeManager
        dw = MockDockWidget()
        
        manager = ThemeManager(dw)
        
        assert manager is not None


# ─────────────────────────────────────────────────────────────────
# Test IconManager
# ─────────────────────────────────────────────────────────────────

class TestIconManagerRegression:
    """Regression tests for IconManager."""
    
    def test_import(self):
        """Test IconManager can be imported."""
        from ui.styles import IconManager
        assert IconManager is not None
    
    def test_init(self):
        """Test IconManager initialization."""
        from ui.styles import IconManager
        dw = MockDockWidget()
        
        manager = IconManager(dw)
        
        assert manager is not None


# ─────────────────────────────────────────────────────────────────
# Test ButtonStyler
# ─────────────────────────────────────────────────────────────────

class TestButtonStylerRegression:
    """Regression tests for ButtonStyler."""
    
    def test_import(self):
        """Test ButtonStyler can be imported."""
        from ui.styles import ButtonStyler
        assert ButtonStyler is not None
    
    def test_init(self):
        """Test ButtonStyler initialization."""
        from ui.styles import ButtonStyler
        dw = MockDockWidget()
        
        styler = ButtonStyler(dw)
        
        assert styler is not None
