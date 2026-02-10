"""
Spacing Manager for FilterMate.

Handles layout spacing, margins, and spacer harmonization.
Extracted from filter_mate_dockwidget.py (lines 1153-1334, 1546-1612).

Story: MIG-063
Phase: 6 - God Class DockWidget Migration

Note: This manager provides standalone spacing functionality.
DimensionsManager also includes spacing methods as part of its
orchestration. For full UI setup, use DimensionsManager.apply().
For spacing-only operations, use SpacingManager directly.
"""

from typing import TYPE_CHECKING, Dict, Any
import logging

from qgis.PyQt.QtWidgets import QSpacerItem

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class SpacingManager(LayoutManagerBase):
    """
    Manages layout spacing and margins.

    Handles:
    - Layout spacing configuration
    - Spacer harmonization
    - Row spacing adjustments
    - Margin management

    Extracted methods from dockwidget:
    - _apply_layout_spacing()
    - _harmonize_spacers()
    - _adjust_row_spacing()

    Attributes:
        _config: Current spacing configuration from UIConfig

    Example:
        manager = SpacingManager(dockwidget)
        manager.setup()

        # Or for specific operations:
        manager.apply_layout_spacing()
        manager.harmonize_spacers()
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the SpacingManager.

        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        self._config: Dict[str, Any] = {}
        self._ui_config = None  # Lazy-loaded UIConfig

    def _get_ui_config(self):
        """Lazy load UIConfig to avoid circular imports."""
        if self._ui_config is None:
            UIConfig = None
            try:
                from ...ui.config import UIConfig
            except ImportError:
                try:
                    from ui.config import UIConfig
                except ImportError:
                    logger.warning("UIConfig not available, using defaults")
            self._ui_config = UIConfig
        return self._ui_config

    def setup(self) -> None:
        """
        Setup initial spacing based on active UI profile.
        """
        self.apply()
        self._initialized = True
        logger.debug("SpacingManager setup complete")

    def apply(self) -> bool:
        """
        Apply all spacing operations.

        Orchestrates the application of spacing by calling specialized methods.

        Returns:
            bool: True if all operations succeeded, False otherwise
        """
        try:
            self.apply_layout_spacing()
            self.harmonize_spacers()
            self.adjust_row_spacing()
            logger.info("SpacingManager: Applied all spacing configurations")
            return True
        except Exception as e:
            logger.error(f"SpacingManager: Error applying spacing: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return False

    def apply_layout_spacing(self) -> None:
        """
        Apply consistent spacing to layouts across all tabs.

        Uses harmonized spacing values from UIConfig to ensure
        uniform visual appearance across the entire UI.
        """
        try:
            UIConfig = self._get_ui_config()

            # Get harmonized layout spacing from config
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 8
            UIConfig.get_config('layout', 'spacing_content') or 6
            UIConfig.get_config('layout', 'spacing_section') or 8
            main_spacing = UIConfig.get_config('layout', 'spacing_main') or 8

            # Get key button spacing for harmonized key layouts
            key_button_config = UIConfig.get_config('key_button')
            button_spacing = key_button_config.get('spacing', 2) if key_button_config else 2

            # CRITICAL: Keys and values layouts MUST use the SAME spacing for alignment
            # Use button_spacing (2) for both columns to ensure proper horizontal alignment
            keys_values_spacing = button_spacing

            # Apply main container spacing for better responsiveness
            if hasattr(self.dockwidget, 'verticalLayout_main_content'):
                self.dockwidget.verticalLayout_main_content.setSpacing(main_spacing)

            # Apply spacing to exploring layouts
            exploring_layouts = [
                'verticalLayout_exploring_single_selection',
                'verticalLayout_exploring_multiple_selection',
                'verticalLayout_exploring_custom_selection'
            ]
            for layout_name in exploring_layouts:
                if hasattr(self.dockwidget, layout_name):
                    getattr(self.dockwidget, layout_name).setSpacing(layout_spacing)

            # Apply spacing to filtering layouts - SAME spacing for alignment
            if hasattr(self.dockwidget, 'verticalLayout_filtering_keys'):
                self.dockwidget.verticalLayout_filtering_keys.setSpacing(keys_values_spacing)
            if hasattr(self.dockwidget, 'verticalLayout_filtering_values'):
                self.dockwidget.verticalLayout_filtering_values.setSpacing(keys_values_spacing)

            # Apply spacing to exporting layouts - SAME spacing for alignment
            if hasattr(self.dockwidget, 'verticalLayout_exporting_keys'):
                self.dockwidget.verticalLayout_exporting_keys.setSpacing(keys_values_spacing)
            if hasattr(self.dockwidget, 'verticalLayout_exporting_values'):
                self.dockwidget.verticalLayout_exporting_values.setSpacing(keys_values_spacing)

            # Apply spacing to exploring key layout
            if hasattr(self.dockwidget, 'verticalLayout_exploring_content'):
                self.dockwidget.verticalLayout_exploring_content.setSpacing(button_spacing)

            section_spacing_adjusted = UIConfig.get_config('layout', 'spacing_section') or 4
            horizontal_layouts = [
                'horizontalLayout_filtering_content',
                'horizontalLayout_exporting_content'
            ]
            for layout_name in horizontal_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setSpacing(section_spacing_adjusted)

            # Apply harmonized margins to groupbox layouts
            margins_frame = UIConfig.get_config('layout', 'margins_frame')
            if margins_frame and isinstance(margins_frame, dict):
                left = margins_frame.get('left', 8)
                top = margins_frame.get('top', 8)
                right = margins_frame.get('right', 8)
                bottom = margins_frame.get('bottom', 10)

                # Exploring groupbox layouts
                groupbox_layouts = [
                    'gridLayout_exploring_single_content',
                    'gridLayout_exploring_multiple_content',
                    'verticalLayout_exploring_custom_container'
                ]

                for layout_name in groupbox_layouts:
                    if hasattr(self.dockwidget, layout_name):
                        layout = getattr(self.dockwidget, layout_name)
                        layout.setContentsMargins(left, top, right, bottom)

                # Apply to filtering/exporting value layouts
                value_layouts = [
                    'verticalLayout_filtering_values',
                    'verticalLayout_exporting_values'
                ]
                for layout_name in value_layouts:
                    if hasattr(self.dockwidget, layout_name):
                        layout = getattr(self.dockwidget, layout_name)
                        layout.setContentsMargins(left, top, right, bottom)

                logger.debug(f"Applied harmonized margins: {left}-{top}-{right}-{bottom}")

            # Apply action bar margins if available
            margins_actions = UIConfig.get_config('layout', 'margins_actions')
            if margins_actions and hasattr(self.dockwidget, 'frame_actions'):
                layout = self.dockwidget.frame_actions.layout()
                if layout:
                    layout.setContentsMargins(
                        margins_actions.get('left', 8),
                        margins_actions.get('top', 6),
                        margins_actions.get('right', 8),
                        margins_actions.get('bottom', 12)
                    )

            logger.debug(f"Applied harmonized layout spacing: {layout_spacing}px")

        except Exception as e:
            logger.debug(f"Could not apply layout spacing: {e}")

    def harmonize_spacers(self) -> None:
        """
        Harmonize vertical spacers across all key widget sections.

        Applies consistent spacer dimensions to exploring/filtering/exporting key widgets
        based on section-specific sizes from UI config.
        """
        try:
            UIConfig = self._get_ui_config()
            if UIConfig is None:
                logger.warning("UIConfig not available, skipping spacer harmonization")
                return
            try:
                from ...ui.config import DisplayProfile
                from ...ui.elements import get_spacer_size
            except ImportError:
                from ui.config import DisplayProfile
                from ui.elements import get_spacer_size

            # Get compact mode status from UIConfig
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT

            # Get dynamic spacer sizes based on active profile
            spacer_sizes = {
                'exploring': get_spacer_size('verticalSpacer_exploring_tab_top', is_compact),
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }

            spacer_width = 20  # Standard width for vertical spacers

            # Harmonize spacers in all three key widgets
            sections = {
                'exploring': 'widget_exploring_keys',
                'filtering': 'widget_filtering_keys',
                'exporting': 'widget_exporting_keys'
            }

            for section_name, widget_name in sections.items():
                # Get section-specific spacer height
                target_spacer_height = spacer_sizes.get(section_name, 4)

                if hasattr(self.dockwidget, widget_name):
                    widget = getattr(self.dockwidget, widget_name)
                    layout = widget.layout()
                    if layout:
                        spacer_count = 0
                        # Find the nested verticalLayout
                        for i in range(layout.count()):
                            item = layout.itemAt(i)
                            if item and hasattr(item, 'layout') and item.layout():
                                nested_layout = item.layout()
                                # Iterate through nested layout items to find spacers
                                for j in range(nested_layout.count()):
                                    nested_item = nested_layout.itemAt(j)
                                    if nested_item and isinstance(nested_item, QSpacerItem):
                                        # Set section-specific spacer dimensions
                                        nested_item.changeSize(
                                            spacer_width,
                                            target_spacer_height,
                                            nested_item.sizePolicy().horizontalPolicy(),
                                            nested_item.sizePolicy().verticalPolicy()
                                        )
                                        spacer_count += 1

                        if spacer_count > 0:
                            logger.debug(f"Harmonized {spacer_count} spacers in {section_name} to {target_spacer_height}px")

            mode_name = 'COMPACT' if is_compact else 'NORMAL'
            logger.debug(f"Applied spacer dimensions ({mode_name} mode): {spacer_sizes}")

        except Exception as e:
            logger.warning(f"Could not harmonize spacers: {e}")
            import traceback
            traceback.print_exc()

    def adjust_row_spacing(self) -> None:
        """
        Adjust row spacing in filtering and exporting value layouts.

        Synchronizes spacer heights between key and value layouts for proper
        horizontal alignment of widgets across columns.
        """
        try:
            UIConfig = self._get_ui_config()
            if UIConfig is None:
                logger.warning("UIConfig not available, skipping row spacing adjustment")
                return
            try:
                from ...ui.config import DisplayProfile
                from ...ui.elements import get_spacer_size
            except ImportError:
                from ui.config import DisplayProfile
                from ui.elements import get_spacer_size

            # Get compact mode status and spacer sizes
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT

            # CRITICAL: Use same spacing as keys layout for alignment
            key_button_config = UIConfig.get_config('key_button')
            keys_values_spacing = key_button_config.get('spacing', 2) if key_button_config else 2

            spacer_sizes = {
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }

            # Adjust spacers in filtering values layout to match keys layout
            if hasattr(self.dockwidget, 'verticalLayout_filtering_values'):
                values_layout = self.dockwidget.verticalLayout_filtering_values
                spacer_target_height = spacer_sizes.get('filtering', 4)

                for i in range(values_layout.count()):
                    item = values_layout.itemAt(i)
                    if item and isinstance(item, QSpacerItem):
                        item.changeSize(
                            item.sizeHint().width(),
                            spacer_target_height,
                            item.sizePolicy().horizontalPolicy(),
                            item.sizePolicy().verticalPolicy()
                        )

                # Use keys_values_spacing for alignment (not layout_spacing)
                self.dockwidget.verticalLayout_filtering_values.setSpacing(keys_values_spacing)

            # Adjust spacers in exporting values layout to match keys layout
            if hasattr(self.dockwidget, 'verticalLayout_exporting_values'):
                values_layout = self.dockwidget.verticalLayout_exporting_values
                spacer_target_height = spacer_sizes.get('exporting', 4)

                for i in range(values_layout.count()):
                    item = values_layout.itemAt(i)
                    if item and isinstance(item, QSpacerItem):
                        item.changeSize(
                            item.sizeHint().width(),
                            spacer_target_height,
                            item.sizePolicy().horizontalPolicy(),
                            item.sizePolicy().verticalPolicy()
                        )

                # Use keys_values_spacing for alignment (not layout_spacing)
                self.dockwidget.verticalLayout_exporting_values.setSpacing(keys_values_spacing)

            logger.debug(f"Adjusted row spacing: filtering/exporting aligned with {keys_values_spacing}px spacing")

        except Exception as e:
            logger.warning(f"Could not adjust row spacing: {e}")
            import traceback
            traceback.print_exc()
