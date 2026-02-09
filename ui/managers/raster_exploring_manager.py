# -*- coding: utf-8 -*-
"""
Raster Exploring Manager - Phase 3.1

Manages all raster exploration UI functionality:
- Raster tool buttons (pixel picker, rectangle picker, histogram sync)
- Band selection (single and multi-band)
- Statistics display and refresh (sync and async)
- Histogram widget
- Pixel picker map tool integration
- Raster export delegation

Extracted from FilterMateDockWidget (Phase 3.1 of Consolidation Plan v6.0).
"""
import os
import logging
import weakref

from qgis.PyQt.QtCore import QObject, QTimer
from qgis.PyQt import QtGui, QtCore
from qgis.core import QgsRasterLayer

logger = logging.getLogger('filter_mate')

# Safe imports for optional dependencies
try:
    from ..icons import get_themed_icon, ICON_THEME_AVAILABLE
except ImportError:
    ICON_THEME_AVAILABLE = False
    get_themed_icon = None

try:
    from ..widgets.checkable_combobox import QgsCheckableComboBoxBands
except ImportError:
    QgsCheckableComboBoxBands = None

try:
    from ...infrastructure.feedback import show_info, show_warning, show_success
except ImportError:
    def show_info(title, msg): logger.info(f"{title}: {msg}")
    def show_warning(title, msg): logger.warning(f"{title}: {msg}")
    def show_success(title, msg): logger.info(f"{title}: {msg}")


class RasterExploringManager(QObject):
    """Manager for raster exploring page UI and interactions.

    Follows the existing manager pattern (ConfigurationManager, DockwidgetSignalManager):
    - Takes dockwidget reference in __init__
    - Accesses widgets via self.dockwidget.widget_name
    - Provides setup() method called after UI initialization
    """

    def __init__(self, dockwidget):
        """Initialize the raster exploring manager.

        Args:
            dockwidget: Reference to FilterMateDockWidget instance
        """
        super().__init__()
        self.dockwidget = dockwidget
        self._histogram = None
        self._pixel_picker_tool = None
        self._tool_button_group = None
        self._tool_bindings = {}
        self._exclusive_groupboxes = []
        self._updating_groupboxes = False
        self._current_stats = None
        self._stats_task = None
        logger.debug("RasterExploringManager initialized")

    def setup(self):
        """Initialize raster exploring UI. Call after setupUi()."""
        self._setup_scrollarea()
        self._setup_checkable_band_combobox()
        self._setup_histogram_widget()
        self._setup_tool_buttons()  # includes _load_tool_icons() and signal connections
        logger.info("RasterExploringManager setup complete")

    def teardown(self):
        """Disconnect all signals connected during setup(). Call on plugin close/reload."""
        d = self.dockwidget
        try:
            # QButtonGroup signal
            if self._tool_button_group:
                try:
                    self._tool_button_group.buttonToggled.disconnect(self._on_button_group_toggled)
                except (TypeError, RuntimeError):
                    pass

            # Groupbox toggled/collapsed lambdas (blanket disconnect needed for lambdas)
            for button, groupbox in self._tool_bindings.items():
                try:
                    groupbox.toggled.disconnect()  # Blanket: connexion via lambda, pas de ref au slot précédent
                except (TypeError, RuntimeError):
                    pass
            for gb in self._exclusive_groupboxes:
                try:
                    gb.collapsedStateChanged.disconnect()  # Blanket: connexion via lambda, pas de ref au slot précédent
                except (TypeError, RuntimeError):
                    pass

            # Action buttons
            button_slot_pairs = [
                ('pushButton_raster_sync_histogram', 'clicked', self._on_sync_histogram_action),
                ('pushButton_raster_reset_range', 'clicked', self._on_reset_range_clicked),
                ('pushButton_raster_pixel_picker', 'clicked', self._on_pixel_picker_button_clicked),
                ('pushButton_raster_rect_picker', 'clicked', self._on_rect_picker_clicked),
                ('pushButton_raster_all_bands', 'toggled', self._on_all_bands_toggled),
                ('pushButton_add_pixel_to_selection', 'clicked', self._on_add_pixel_to_selection_clicked),
            ]
            for widget_name, signal_name, slot in button_slot_pairs:
                if hasattr(d, widget_name):
                    try:
                        getattr(getattr(d, widget_name), signal_name).disconnect(slot)
                    except (TypeError, RuntimeError):
                        pass

            # Combobox triggers
            combobox_slot_pairs = [
                ('comboBox_predicate', 'currentIndexChanged', self._on_combobox_predicate_trigger),
                ('doubleSpinBox_min', 'valueChanged', self._on_spinbox_range_trigger),
                ('doubleSpinBox_max', 'valueChanged', self._on_spinbox_range_trigger),
                ('doubleSpinBox_rect_min', 'valueChanged', self._on_rect_spinbox_trigger),
                ('doubleSpinBox_rect_max', 'valueChanged', self._on_rect_spinbox_trigger),
            ]
            for widget_name, signal_name, slot in combobox_slot_pairs:
                if hasattr(d, widget_name):
                    try:
                        getattr(getattr(d, widget_name), signal_name).disconnect(slot)
                    except (TypeError, RuntimeError):
                        pass

            # Histogram signals
            if self._histogram:
                try:
                    self._histogram.rangeChanged.disconnect(self._on_histogram_range_changed)
                except (TypeError, RuntimeError):
                    pass
                try:
                    self._histogram.rangeSelectionFinished.disconnect(self._on_histogram_range_finished)
                except (TypeError, RuntimeError):
                    pass

            # Cancel pending async task
            if self._stats_task:
                try:
                    self._stats_task.cancel()
                except Exception:
                    pass

            self._pixel_picker_tool = None
            self._histogram = None
            self._stats_task = None
            self._tool_button_group = None
            self._tool_bindings = {}
            self._exclusive_groupboxes = []

            logger.info("RasterExploringManager teardown complete")

        except Exception as e:
            logger.error(f"RasterExploringManager teardown failed: {e}")

    # ================================================================
    # SETUP METHODS
    # ================================================================

    def _setup_scrollarea(self):
        """Wrap raster content in a ScrollArea for proper GroupBox display."""
        d = self.dockwidget
        try:
            if not hasattr(d, 'widget_raster_content') or not hasattr(d, 'horizontalLayout_raster_main'):
                logger.debug("Raster content widgets not found, skipping scrollarea setup")
                return

            from qgis.PyQt.QtWidgets import QScrollArea, QSizePolicy, QFrame
            from qgis.PyQt.QtCore import Qt

            parent_layout = d.horizontalLayout_raster_main

            widget_index = -1
            for i in range(parent_layout.count()):
                item = parent_layout.itemAt(i)
                if item and item.widget() == d.widget_raster_content:
                    widget_index = i
                    break

            if widget_index < 0:
                logger.warning("Could not find widget_raster_content in horizontalLayout_raster_main")
                return

            parent_layout.removeWidget(d.widget_raster_content)

            d.scrollArea_raster_content = QScrollArea(d.page_exploring_raster)
            d.scrollArea_raster_content.setObjectName("scrollArea_raster_content")
            d.scrollArea_raster_content.setWidgetResizable(True)
            d.scrollArea_raster_content.setFrameShape(QFrame.NoFrame)
            d.scrollArea_raster_content.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            d.scrollArea_raster_content.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            sizePolicy.setHorizontalStretch(1)
            sizePolicy.setVerticalStretch(1)
            d.scrollArea_raster_content.setSizePolicy(sizePolicy)

            d.scrollArea_raster_content.setWidget(d.widget_raster_content)
            d.widget_raster_content.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred))
            parent_layout.insertWidget(widget_index, d.scrollArea_raster_content)

            logger.info("Raster content wrapped in ScrollArea for proper GroupBox display")

        except Exception as e:
            logger.warning(f"Could not setup raster scrollarea: {e}", exc_info=True)

    def _setup_checkable_band_combobox(self):
        """Replace standard comboBox_band with QgsCheckableComboBoxBands."""
        d = self.dockwidget
        if QgsCheckableComboBoxBands is None:
            logger.debug("QgsCheckableComboBoxBands not available, skipping")
            return
        try:
            if not hasattr(d, 'comboBox_band') or not hasattr(d, 'horizontalLayout_band'):
                logger.warning("comboBox_band or horizontalLayout_band not found, skipping checkable setup")
                return

            old_combo = d.comboBox_band
            parent_layout = d.horizontalLayout_band

            widget_index = -1
            for i in range(parent_layout.count()):
                item = parent_layout.itemAt(i)
                if item and item.widget() == old_combo:
                    widget_index = i
                    break

            if widget_index < 0:
                logger.warning("Could not find comboBox_band in horizontalLayout_band")
                return

            new_combo = QgsCheckableComboBoxBands(d.page_exploring_raster)
            new_combo.setObjectName("comboBox_band")
            new_combo.setSizePolicy(old_combo.sizePolicy())
            new_combo.setToolTip(old_combo.toolTip())

            parent_layout.removeWidget(old_combo)
            old_combo.setParent(None)
            old_combo.deleteLater()

            parent_layout.insertWidget(widget_index, new_combo)
            d.comboBox_band = new_combo

            logger.info("comboBox_band replaced with QgsCheckableComboBoxBands")

        except Exception as e:
            logger.error(f"Failed to setup checkable band combobox: {e}", exc_info=True)

    def _setup_histogram_widget(self):
        """Create and embed the RasterHistogramWidget into the placeholder."""
        d = self.dockwidget
        try:
            from ..widgets.raster_histogram_interactive import RasterHistogramInteractiveWidget
            from qgis.PyQt.QtWidgets import QVBoxLayout, QSizePolicy

            if not hasattr(d, 'widget_histogram_placeholder'):
                logger.warning("widget_histogram_placeholder not found in UI")
                return

            d.widget_histogram_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            d.widget_histogram_placeholder.setMinimumHeight(100)

            existing_layout = d.widget_histogram_placeholder.layout()
            if existing_layout is not None:
                while existing_layout.count():
                    item = existing_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

            layout = d.widget_histogram_placeholder.layout()
            if layout is None:
                layout = QVBoxLayout(d.widget_histogram_placeholder)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self._histogram = RasterHistogramInteractiveWidget()
            self._histogram.setMinimumHeight(80)
            self._histogram.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(self._histogram)

            self._histogram.setVisible(True)
            d.widget_histogram_placeholder.setVisible(True)

            self._histogram.rangeChanged.connect(self._on_histogram_range_changed)
            self._histogram.rangeSelectionFinished.connect(self._on_histogram_range_finished)

            logger.info("Raster histogram widget initialized")

        except ImportError as e:
            logger.warning(f"Could not import histogram widget: {e}")
            self._histogram = None
        except Exception as e:
            logger.error(f"Failed to setup histogram widget: {e}", exc_info=True)
            self._histogram = None

    def _load_tool_icons(self):
        """Load icons and apply consistent styling for raster tool buttons."""
        d = self.dockwidget
        try:
            pb_cfg = d.CONFIG_DATA.get("APP", {}).get("DOCKWIDGET", {}).get("PushButton", {})
            icons = pb_cfg.get("ICONS", {})
            sizes = pb_cfg.get("ICONS_SIZES", {})

            sz_oth_raw = sizes.get("OTHERS", 20)
            sz = sz_oth_raw.get("value", 20) if isinstance(sz_oth_raw, dict) else sz_oth_raw

            raster_icons = icons.get("RASTER_EXPLORING", {})
            if not raster_icons:
                logger.debug("RASTER_EXPLORING icons not yet available in config, will retry later")
                return

            button_font = QtGui.QFont()
            button_font.setFamily("Segoe UI")
            button_font.setPointSize(10)
            button_font.setBold(True)
            button_font.setItalic(False)
            button_font.setUnderline(False)
            button_font.setWeight(75)
            button_font.setStrikeOut(False)
            button_font.setKerning(True)
            button_font.setStyleStrategy(QtGui.QFont.PreferAntialias)

            loaded_count = 0
            for name, ico_file in raster_icons.items():
                attr = d._get_widget_attr_name("RASTER_EXPLORING", name)
                if not attr:
                    continue
                if not hasattr(d, attr):
                    logger.warning(f"Widget {attr} not found")
                    continue

                widget = getattr(d, attr)
                icon_path = os.path.join(d.plugin_dir, "icons", ico_file)

                if not os.path.exists(icon_path):
                    logger.warning(f"Icon file not found: {icon_path}")
                    continue

                icon = get_themed_icon(icon_path) if ICON_THEME_AVAILABLE else QtGui.QIcon(icon_path)
                widget.setIcon(icon)
                widget.setIconSize(QtCore.QSize(sz, sz))
                widget.setFont(button_font)
                loaded_count += 1

            logger.info(f"Loaded {loaded_count} raster icons with styling")

        except Exception as e:
            logger.error(f"_load_tool_icons failed: {e}")

    def _setup_tool_buttons(self):
        """Connect raster tool buttons to handlers and groupboxes."""
        d = self.dockwidget
        try:
            from qgis.PyQt.QtWidgets import QButtonGroup

            # QButtonGroup for exclusive pushbuttons
            self._tool_button_group = QButtonGroup(d)
            self._tool_button_group.setExclusive(True)

            checkable_tool_buttons = []
            if hasattr(d, 'pushButton_raster_pixel_picker'):
                checkable_tool_buttons.append(d.pushButton_raster_pixel_picker)
            if hasattr(d, 'pushButton_raster_rect_picker'):
                checkable_tool_buttons.append(d.pushButton_raster_rect_picker)
            if hasattr(d, 'pushButton_raster_sync_histogram'):
                checkable_tool_buttons.append(d.pushButton_raster_sync_histogram)

            for i, btn in enumerate(checkable_tool_buttons):
                self._tool_button_group.addButton(btn, i)

            self._tool_button_group.buttonToggled.connect(self._on_button_group_toggled)

            # Button → groupbox bindings
            self._tool_bindings = {}
            if hasattr(d, 'pushButton_raster_pixel_picker') and hasattr(d, 'mGroupBox_raster_pixel_picker'):
                self._tool_bindings[d.pushButton_raster_pixel_picker] = d.mGroupBox_raster_pixel_picker
            if hasattr(d, 'pushButton_raster_rect_picker') and hasattr(d, 'mGroupBox_raster_rect_picker'):
                self._tool_bindings[d.pushButton_raster_rect_picker] = d.mGroupBox_raster_rect_picker
            if hasattr(d, 'pushButton_raster_sync_histogram') and hasattr(d, 'mGroupBox_raster_histogram'):
                self._tool_bindings[d.pushButton_raster_sync_histogram] = d.mGroupBox_raster_histogram

            self._exclusive_groupboxes = []
            if hasattr(d, 'mGroupBox_raster_pixel_picker'):
                self._exclusive_groupboxes.append(d.mGroupBox_raster_pixel_picker)
            if hasattr(d, 'mGroupBox_raster_rect_picker'):
                self._exclusive_groupboxes.append(d.mGroupBox_raster_rect_picker)
            if hasattr(d, 'mGroupBox_raster_histogram'):
                self._exclusive_groupboxes.append(d.mGroupBox_raster_histogram)

            # Groupbox toggled → sync button
            for button, groupbox in self._tool_bindings.items():
                groupbox.toggled.connect(
                    lambda checked, btn=button: self._sync_button_from_groupbox(btn, checked)
                )

            # Collapsed state for exclusive behavior
            for gb in self._exclusive_groupboxes:
                gb.collapsedStateChanged.connect(
                    lambda collapsed, groupbox=gb: self._on_groupbox_collapsed_changed(groupbox, collapsed)
                )

            # Action buttons
            if hasattr(d, 'pushButton_raster_sync_histogram'):
                d.pushButton_raster_sync_histogram.clicked.connect(self._on_sync_histogram_action)
            if hasattr(d, 'pushButton_raster_reset_range'):
                d.pushButton_raster_reset_range.clicked.connect(self._on_reset_range_clicked)
            if hasattr(d, 'pushButton_raster_pixel_picker'):
                d.pushButton_raster_pixel_picker.clicked.connect(self._on_pixel_picker_button_clicked)
            if hasattr(d, 'pushButton_raster_rect_picker'):
                d.pushButton_raster_rect_picker.clicked.connect(self._on_rect_picker_clicked)
            if hasattr(d, 'pushButton_raster_all_bands'):
                d.pushButton_raster_all_bands.toggled.connect(self._on_all_bands_toggled)
            if hasattr(d, 'pushButton_add_pixel_to_selection'):
                d.pushButton_add_pixel_to_selection.clicked.connect(self._on_add_pixel_to_selection_clicked)

            # Combobox triggers
            self._connect_combobox_triggers()

            # Load icons
            self._load_tool_icons()

            # Initialize exclusive state
            self._initialize_groupbox_exclusive_state()

            logger.debug("Raster tool buttons connected with QButtonGroup + groupbox bindings")

        except Exception as e:
            logger.error(f"Failed to connect raster tool buttons: {e}")

    def _connect_combobox_triggers(self):
        """Connect combobox triggers for active groupboxes."""
        d = self.dockwidget
        try:
            if hasattr(d, 'comboBox_predicate') and hasattr(d, 'mGroupBox_raster_histogram'):
                d.comboBox_predicate.currentIndexChanged.connect(self._on_combobox_predicate_trigger)

            if hasattr(d, 'doubleSpinBox_min') and hasattr(d, 'mGroupBox_raster_histogram'):
                d.doubleSpinBox_min.valueChanged.connect(self._on_spinbox_range_trigger)
            if hasattr(d, 'doubleSpinBox_max') and hasattr(d, 'mGroupBox_raster_histogram'):
                d.doubleSpinBox_max.valueChanged.connect(self._on_spinbox_range_trigger)

            if hasattr(d, 'doubleSpinBox_rect_min') and hasattr(d, 'mGroupBox_raster_rect_picker'):
                d.doubleSpinBox_rect_min.valueChanged.connect(self._on_rect_spinbox_trigger)
            if hasattr(d, 'doubleSpinBox_rect_max') and hasattr(d, 'mGroupBox_raster_rect_picker'):
                d.doubleSpinBox_rect_max.valueChanged.connect(self._on_rect_spinbox_trigger)

            logger.debug("Raster combobox triggers connected")
        except Exception as e:
            logger.warning(f"Error connecting raster combobox triggers: {e}")

    def _initialize_groupbox_exclusive_state(self):
        """Initialize raster groupboxes to exclusive state (pixel picker default)."""
        d = self.dockwidget
        try:
            default_groupbox = None
            if hasattr(d, 'mGroupBox_raster_pixel_picker'):
                default_groupbox = d.mGroupBox_raster_pixel_picker

            for gb in self._exclusive_groupboxes:
                gb.blockSignals(True)
                if gb == default_groupbox:
                    gb.setChecked(True)
                    gb.setCollapsed(False)
                else:
                    gb.setChecked(False)
                    gb.setCollapsed(True)
                gb.blockSignals(False)

            for button, groupbox in self._tool_bindings.items():
                button.blockSignals(True)
                button.setChecked(groupbox == default_groupbox)
                button.blockSignals(False)

            logger.debug("Raster groupboxes initialized to exclusive state")
        except Exception as e:
            logger.warning(f"Error initializing raster groupbox state: {e}")

    # ================================================================
    # EVENT HANDLERS
    # ================================================================

    def _on_bands_changed(self, band_indices: list):
        """Handle multi-band selection change."""
        try:
            logger.debug(f"Raster bands changed: {band_indices}")
            if self._pixel_picker_tool:
                self._pixel_picker_tool.set_bands(band_indices)
            if self._histogram:
                if len(band_indices) > 1:
                    self._histogram.setBands(band_indices)
                elif band_indices:
                    self._histogram.setBand(band_indices[0])
            if band_indices:
                self._refresh_stats_for_bands(band_indices)
        except Exception as e:
            logger.error(f"Error handling bands change: {e}")

    def _on_band_changed(self, index: int):
        """Handle band selection change for raster filtering."""
        d = self.dockwidget
        if hasattr(d, 'comboBox_band'):
            band_name = d.comboBox_band.currentText()
            logger.debug(f"Raster band changed to: {band_name}")
            layer = d._get_current_exploring_layer()
            if layer and isinstance(layer, QgsRasterLayer):
                self._refresh_statistics(layer=layer)
                self._update_histogram(layer)

    def _on_refresh_stats(self):
        """Refresh raster statistics for current layer/band."""
        d = self.dockwidget
        logger.debug("Refresh raster stats requested")
        layer = d._get_current_exploring_layer()
        if layer and isinstance(layer, QgsRasterLayer):
            self._refresh_statistics(layer=layer)
            if self._histogram:
                band_index = 1
                if hasattr(d, 'comboBox_band'):
                    band_index = d.comboBox_band.currentIndex() + 1
                    if band_index < 1:
                        band_index = 1
                self._histogram._layer = layer
                self._histogram._band_index = band_index
                self._histogram.force_compute()
        else:
            logger.warning("Cannot refresh stats - no raster layer selected")

    def _on_button_group_toggled(self, button, checked):
        """Handle QButtonGroup toggle - update associated groupbox."""
        try:
            groupbox = self._tool_bindings.get(button)
            if groupbox:
                self._ensure_exclusive_groupbox(groupbox, checked)
                if checked:
                    self._trigger_combobox_for_groupbox(groupbox)
        except Exception as e:
            logger.warning(f"Error in button group toggle: {e}")

    def _on_combobox_predicate_trigger(self, index):
        """Handle predicate combobox change when histogram groupbox is active."""
        d = self.dockwidget
        try:
            if not hasattr(d, 'mGroupBox_raster_histogram'):
                return
            if d.mGroupBox_raster_histogram.isChecked():
                logger.debug(f"Predicate changed to index {index} (histogram active)")
                self._update_filter_from_ui()
        except Exception as e:
            logger.warning(f"Error in predicate trigger: {e}")

    def _on_spinbox_range_trigger(self, value):
        """Handle histogram range spinbox change when histogram groupbox is active."""
        d = self.dockwidget
        try:
            if not hasattr(d, 'mGroupBox_raster_histogram'):
                return
            if d.mGroupBox_raster_histogram.isChecked():
                if self._histogram:
                    min_val = d.doubleSpinBox_min.value() if hasattr(d, 'doubleSpinBox_min') else 0
                    max_val = d.doubleSpinBox_max.value() if hasattr(d, 'doubleSpinBox_max') else 0
                    self._histogram.set_range(min_val, max_val)
        except Exception as e:
            logger.warning(f"Error in range trigger: {e}")

    def _on_rect_spinbox_trigger(self, value):
        """Handle rectangle picker spinbox change when rect groupbox is active."""
        d = self.dockwidget
        try:
            if not hasattr(d, 'mGroupBox_raster_rect_picker'):
                return
            if d.mGroupBox_raster_rect_picker.isChecked():
                logger.debug("Rect range changed (rect picker active)")
        except Exception as e:
            logger.warning(f"Error in rect trigger: {e}")

    def _on_tool_button_toggled(self, groupbox, checked):
        """Handle raster tool button toggle (legacy)."""
        try:
            self._ensure_exclusive_groupbox(groupbox, checked)
        except Exception as e:
            logger.warning(f"Error updating groupbox state: {e}")

    def _on_groupbox_collapsed_changed(self, groupbox, collapsed):
        """Handle raster groupbox expand/collapse for exclusive behavior."""
        if collapsed:
            return
        if self._updating_groupboxes:
            return
        try:
            self._updating_groupboxes = True
            self._ensure_exclusive_groupbox(groupbox, True)
        except Exception as e:
            logger.warning(f"Error handling raster groupbox collapse change: {e}")
        finally:
            self._updating_groupboxes = False

    def _on_pixel_picker_button_clicked(self):
        """Handle click on raster pixel picker button."""
        d = self.dockwidget
        try:
            if hasattr(d, 'pushButton_raster_pixel_picker'):
                if not d.pushButton_raster_pixel_picker.isChecked():
                    self._deactivate_pixel_picker_tool()
                    return
            self._on_pixel_picker_clicked()
        except Exception as e:
            logger.error(f"Error in raster pixel picker: {e}")

    def _on_pixel_picker_clicked(self):
        """Activate pixel picker map tool for raster value selection."""
        d = self.dockwidget
        try:
            from qgis.utils import iface
            from ..tools.pixel_picker_tool import RasterPixelPickerTool

            if not iface or not iface.mapCanvas():
                show_warning("FilterMate", "Map canvas not available")
                return

            layer = d._get_current_exploring_layer()
            if not layer or not isinstance(layer, QgsRasterLayer):
                show_warning("FilterMate", "Please select a raster layer first")
                return

            if self._pixel_picker_tool is None:
                self._pixel_picker_tool = RasterPixelPickerTool(iface.mapCanvas(), d)
                self._pixel_picker_tool.valuesPicked.connect(self._on_pixel_values_picked)
                self._pixel_picker_tool.valuePicked.connect(self._on_single_pixel_picked)
                self._pixel_picker_tool.pixelPicked.connect(self._on_pixel_picked_with_coords)
                self._pixel_picker_tool.allBandsPicked.connect(self._on_all_bands_picked)
                self._pixel_picker_tool.pickingFinished.connect(self._on_pixel_picking_finished)

            band_index = 1
            if hasattr(d, 'comboBox_band'):
                band_index = d.comboBox_band.currentIndex() + 1
                if band_index < 1:
                    band_index = 1

            self._pixel_picker_tool.set_layer(layer, band_index)

            if hasattr(d, 'doubleSpinBox_min') and hasattr(d, 'doubleSpinBox_max'):
                self._pixel_picker_tool.set_current_range(
                    d.doubleSpinBox_min.value(), d.doubleSpinBox_max.value()
                )

            iface.mapCanvas().setMapTool(self._pixel_picker_tool)

            if hasattr(d, 'pushButton_raster_pixel_picker'):
                d.pushButton_raster_pixel_picker.blockSignals(True)
                d.pushButton_raster_pixel_picker.setChecked(True)
                d.pushButton_raster_pixel_picker.blockSignals(False)

            show_info("FilterMate", "Click on raster to pick value. Drag for range. Press Escape to cancel.")
            logger.info("Pixel picker tool activated")

        except ImportError as e:
            logger.error(f"Could not import pixel picker tool: {e}")
            show_warning("FilterMate", "Pixel picker not available")
        except Exception as e:
            logger.error(f"Failed to activate pixel picker: {e}", exc_info=True)
            show_warning("FilterMate", f"Error activating pixel picker: {e}")

    def _on_rect_picker_clicked(self):
        """Handle click on rectangle range picker button."""
        d = self.dockwidget
        try:
            if hasattr(d, 'pushButton_raster_rect_picker'):
                if not d.pushButton_raster_rect_picker.isChecked():
                    self._deactivate_pixel_picker_tool()
                    return

            from qgis.utils import iface
            from ..tools.pixel_picker_tool import RasterPixelPickerTool

            if not iface or not iface.mapCanvas():
                show_warning("FilterMate", "Map canvas not available")
                return

            layer = d._get_current_exploring_layer()
            if not layer or not isinstance(layer, QgsRasterLayer):
                show_warning("FilterMate", "Please select a raster layer first")
                if hasattr(d, 'pushButton_raster_rect_picker'):
                    d.pushButton_raster_rect_picker.blockSignals(True)
                    d.pushButton_raster_rect_picker.setChecked(False)
                    d.pushButton_raster_rect_picker.blockSignals(False)
                return

            if self._pixel_picker_tool is None:
                self._pixel_picker_tool = RasterPixelPickerTool(iface.mapCanvas(), d)
                self._pixel_picker_tool.valuesPicked.connect(self._on_pixel_values_picked)
                self._pixel_picker_tool.valuePicked.connect(self._on_single_pixel_picked)
                self._pixel_picker_tool.pixelPicked.connect(self._on_pixel_picked_with_coords)
                self._pixel_picker_tool.allBandsPicked.connect(self._on_all_bands_picked)
                self._pixel_picker_tool.pickingFinished.connect(self._on_pixel_picking_finished)

            band_index = 1
            if hasattr(d, 'comboBox_band'):
                band_index = d.comboBox_band.currentIndex() + 1
                if band_index < 1:
                    band_index = 1

            self._pixel_picker_tool.set_layer(layer, band_index)

            if hasattr(d, 'doubleSpinBox_min') and hasattr(d, 'doubleSpinBox_max'):
                self._pixel_picker_tool.set_current_range(
                    d.doubleSpinBox_min.value(), d.doubleSpinBox_max.value()
                )

            iface.mapCanvas().setMapTool(self._pixel_picker_tool)
            show_info("FilterMate", "Drag rectangle to select value range from area")
            logger.info("Raster rectangle picker activated")

        except ImportError as e:
            logger.error(f"Could not import pixel picker tool: {e}")
            show_warning("FilterMate", "Pixel picker not available")
        except Exception as e:
            logger.error(f"Failed to activate rectangle picker: {e}", exc_info=True)
            show_warning("FilterMate", f"Error: {e}")

    def _on_sync_histogram_action(self):
        """Synchronize spinbox values with histogram selection."""
        d = self.dockwidget
        try:
            if not hasattr(d, 'pushButton_raster_sync_histogram'):
                return
            if not d.pushButton_raster_sync_histogram.isChecked():
                return
            if self._histogram:
                min_val = d.doubleSpinBox_min.value() if hasattr(d, 'doubleSpinBox_min') else 0
                max_val = d.doubleSpinBox_max.value() if hasattr(d, 'doubleSpinBox_max') else 0
                self._histogram.set_range(min_val, max_val)
                show_info("FilterMate", f"Histogram synchronized: [{min_val:.2f}, {max_val:.2f}]")
            else:
                show_warning("FilterMate", "Histogram widget not available")
        except Exception as e:
            logger.error(f"Error syncing histogram: {e}")

    def _on_sync_histogram_clicked(self):
        """DEPRECATED: Use _on_sync_histogram_action instead."""
        self._on_sync_histogram_action()

    def _on_all_bands_toggled(self, checked: bool):
        """Handle toggle of all bands button - enables/disables multi-band mode."""
        d = self.dockwidget
        try:
            if hasattr(d, 'comboBox_band') and QgsCheckableComboBoxBands and isinstance(d.comboBox_band, QgsCheckableComboBoxBands):
                d.comboBox_band.setMultiSelectEnabled(checked)
                if checked:
                    show_info("FilterMate", d.tr("Multi-band mode enabled. Select bands in dropdown."))
                else:
                    show_info("FilterMate", d.tr("Single-band mode. Tools work on selected band only."))

            if hasattr(d, 'pushButton_raster_all_bands'):
                if checked:
                    d.pushButton_raster_all_bands.setToolTip(
                        d.tr("Multi-Band Mode: ON\n\nClick to disable multi-band mode.\n"
                             "Tools will work on all selected bands in the dropdown.")
                    )
                else:
                    d.pushButton_raster_all_bands.setToolTip(
                        d.tr("Multi-Band Mode: OFF\n\nClick to enable multi-band mode.\n"
                             "Tools will work on multiple selected bands.")
                    )
        except Exception as e:
            logger.error(f"Error toggling all bands mode: {e}")

    def _on_all_bands_clicked(self):
        """DEPRECATED: All bands functionality moved to toggled signal."""
        pass

    def _on_reset_range_clicked(self):
        """Reset min/max spinboxes to full data range from statistics."""
        d = self.dockwidget
        try:
            data_min = None
            data_max = None
            if self._current_stats:
                data_min = self._current_stats.get('min')
                data_max = self._current_stats.get('max')

            if data_min is not None and data_max is not None:
                if hasattr(d, 'doubleSpinBox_min'):
                    d.doubleSpinBox_min.blockSignals(True)
                    d.doubleSpinBox_min.setValue(data_min)
                    d.doubleSpinBox_min.blockSignals(False)
                if hasattr(d, 'doubleSpinBox_max'):
                    d.doubleSpinBox_max.blockSignals(True)
                    d.doubleSpinBox_max.setValue(data_max)
                    d.doubleSpinBox_max.blockSignals(False)
                if self._histogram:
                    self._histogram.set_range(data_min, data_max)
                show_info("FilterMate", f"Range reset to data bounds: [{data_min:.2f}, {data_max:.2f}]")
            else:
                show_warning("FilterMate", "Statistics not available. Click Refresh first.")
        except Exception as e:
            logger.error(f"Error resetting range: {e}")

    def _on_pixel_values_picked(self, min_val: float, max_val: float):
        """Handle min/max values picked from raster."""
        d = self.dockwidget
        logger.debug(f"Pixel values picked: [{min_val:.2f}, {max_val:.2f}]")
        if hasattr(d, 'doubleSpinBox_min'):
            d.doubleSpinBox_min.blockSignals(True)
            d.doubleSpinBox_min.setValue(min_val)
            d.doubleSpinBox_min.blockSignals(False)
        if hasattr(d, 'doubleSpinBox_max'):
            d.doubleSpinBox_max.blockSignals(True)
            d.doubleSpinBox_max.setValue(max_val)
            d.doubleSpinBox_max.blockSignals(False)
        if hasattr(d, 'doubleSpinBox_rect_min'):
            d.doubleSpinBox_rect_min.blockSignals(True)
            d.doubleSpinBox_rect_min.setValue(min_val)
            d.doubleSpinBox_rect_min.blockSignals(False)
        if hasattr(d, 'doubleSpinBox_rect_max'):
            d.doubleSpinBox_rect_max.blockSignals(True)
            d.doubleSpinBox_rect_max.setValue(max_val)
            d.doubleSpinBox_rect_max.blockSignals(False)
        if self._histogram:
            self._histogram.set_range(min_val, max_val)

    def _on_single_pixel_picked(self, value: float):
        """Handle single pixel value picked."""
        d = self.dockwidget
        logger.info(f"Single pixel value picked: {value:.4f}")
        if hasattr(d, 'label_pixel_value'):
            d.label_pixel_value.setText(f"{value:.4f}")

    def _on_pixel_picked_with_coords(self, value: float, x: float, y: float):
        """Handle pixel value picked with coordinates."""
        d = self.dockwidget
        logger.debug(f"Pixel picked: value={value:.4f} at ({x:.2f}, {y:.2f})")
        if hasattr(d, 'label_pixel_value'):
            d.label_pixel_value.setText(f"{value:.4f}")
        if hasattr(d, 'label_pixel_coords'):
            d.label_pixel_coords.setText(f"{x:.2f}, {y:.2f}")

    def _on_all_bands_picked(self, values: list):
        """Handle all bands values picked (Shift+click)."""
        band_info = []
        for i, val in enumerate(values, 1):
            if val is not None:
                band_info.append(f"Band {i}: {val:.4f}")
            else:
                band_info.append(f"Band {i}: NoData")
        message = "\n".join(band_info)
        logger.info(f"All bands:\n{message}")
        show_info("FilterMate - Pixel Values", message)

    def _on_add_pixel_to_selection_clicked(self):
        """Add currently displayed pixel value to range selection."""
        d = self.dockwidget
        try:
            if not hasattr(d, 'label_pixel_value'):
                show_warning("FilterMate", "No pixel value available")
                return

            value_text = d.label_pixel_value.text()
            if value_text == "--" or not value_text:
                show_warning("FilterMate", "Pick a pixel first using the pixel picker tool")
                return

            try:
                pixel_value = float(value_text)
            except ValueError:
                show_warning("FilterMate", f"Invalid pixel value: {value_text}")
                return

            current_min = d.doubleSpinBox_rect_min.value() if hasattr(d, 'doubleSpinBox_rect_min') else None
            current_max = d.doubleSpinBox_rect_max.value() if hasattr(d, 'doubleSpinBox_rect_max') else None

            is_first_value = (current_min == 0.0 and current_max == 0.0)
            if is_first_value:
                new_min = pixel_value
                new_max = pixel_value
            else:
                new_min = min(current_min, pixel_value) if current_min is not None else pixel_value
                new_max = max(current_max, pixel_value) if current_max is not None else pixel_value

            if hasattr(d, 'doubleSpinBox_rect_min'):
                d.doubleSpinBox_rect_min.blockSignals(True)
                d.doubleSpinBox_rect_min.setValue(new_min)
                d.doubleSpinBox_rect_min.blockSignals(False)
            if hasattr(d, 'doubleSpinBox_rect_max'):
                d.doubleSpinBox_rect_max.blockSignals(True)
                d.doubleSpinBox_rect_max.setValue(new_max)
                d.doubleSpinBox_rect_max.blockSignals(False)
            if self._histogram:
                self._histogram.set_range(new_min, new_max)

            logger.info(f"Added pixel value {pixel_value:.4f} to selection. Range: [{new_min:.4f}, {new_max:.4f}]")
            show_success("FilterMate", f"Pixel value {pixel_value:.4f} added to selection")

        except Exception as e:
            logger.error(f"Error adding pixel to selection: {e}")
            show_warning("FilterMate", f"Error adding pixel to selection: {str(e)}")

    def _on_pixel_picking_finished(self):
        """Handle pixel picking tool deactivation."""
        d = self.dockwidget
        logger.debug("Pixel picker deactivated")
        if hasattr(d, 'pushButton_raster_pixel_picker'):
            d.pushButton_raster_pixel_picker.blockSignals(True)
            d.pushButton_raster_pixel_picker.setChecked(False)
            d.pushButton_raster_pixel_picker.blockSignals(False)
        self._uncheck_tool_buttons()

    def _on_histogram_range_changed(self, min_val: float, max_val: float):
        """Synchronize interactive histogram selection with spinboxes."""
        d = self.dockwidget
        if hasattr(d, 'doubleSpinBox_min'):
            d.doubleSpinBox_min.blockSignals(True)
            d.doubleSpinBox_min.setValue(min_val)
            d.doubleSpinBox_min.blockSignals(False)
        if hasattr(d, 'doubleSpinBox_max'):
            d.doubleSpinBox_max.blockSignals(True)
            d.doubleSpinBox_max.setValue(max_val)
            d.doubleSpinBox_max.blockSignals(False)

    def _on_histogram_range_finished(self, min_val: float, max_val: float):
        """Apply raster filter after interactive histogram selection (drag finished)."""
        logger.debug(f"Histogram range selected: [{min_val:.2f}, {max_val:.2f}]")
        self._on_histogram_range_changed(min_val, max_val)

    def _on_histogram_groupbox_toggled(self, checked: bool):
        """Handle histogram groupbox toggle to compute/update histogram."""
        d = self.dockwidget
        if not checked:
            return
        try:
            if self._histogram is None:
                self._setup_histogram_widget()

            layer = d._get_current_exploring_layer()
            if not layer or not isinstance(layer, QgsRasterLayer):
                return

            self._update_histogram(layer)
        except Exception as e:
            logger.error(f"Error in histogram groupbox toggle: {e}")

    # ================================================================
    # REFRESH METHODS
    # ================================================================

    def _refresh_stats_for_bands(self, band_indices: list):
        """Refresh statistics display for multiple bands."""
        if not band_indices:
            return
        self._on_band_changed(band_indices[0])

    def _refresh_statistics(self, force_full_scan: bool = False, layer=None):
        """Calculate and display statistics for current raster layer/band."""
        d = self.dockwidget
        try:
            from qgis.core import QgsRasterBandStats, Qgis, QgsApplication

            current_layer = layer if layer else d._get_current_exploring_layer()
            if not current_layer or not isinstance(current_layer, QgsRasterLayer):
                self.clear_statistics_display()
                return

            band_index = 1
            if hasattr(d, 'comboBox_band'):
                band_index = d.comboBox_band.currentIndex() + 1
                if band_index < 1:
                    band_index = 1

            provider = current_layer.dataProvider()
            if not provider:
                self.clear_statistics_display()
                return

            width = current_layer.width()
            height = current_layer.height()
            total_pixels = width * height
            LARGE_RASTER_THRESHOLD = 10_000_000

            if total_pixels > LARGE_RASTER_THRESHOLD and not force_full_scan:
                logger.info(f"Large raster detected ({total_pixels:,} pixels), using async QgsTask")
                self._refresh_statistics_async(current_layer, band_index, force_full_scan)
                return

            SAMPLE_SIZE = 250_000
            sample_size = SAMPLE_SIZE if total_pixels > LARGE_RASTER_THRESHOLD else 0

            stats = provider.bandStatistics(
                band_index, QgsRasterBandStats.All, current_layer.extent(), sample_size
            )

            nodata_value = None
            if provider.sourceHasNoDataValue(band_index):
                nodata_value = provider.sourceNoDataValue(band_index)

            self._update_statistics_display(
                min_val=stats.minimumValue, max_val=stats.maximumValue,
                mean_val=stats.mean, stddev_val=stats.stdDev,
                nodata_val=nodata_value, band_index=band_index, layer=current_layer
            )

            if hasattr(d, 'doubleSpinBox_min') and hasattr(d, 'doubleSpinBox_max'):
                d.doubleSpinBox_min.blockSignals(True)
                d.doubleSpinBox_max.blockSignals(True)
                d.doubleSpinBox_min.setMinimum(stats.minimumValue)
                d.doubleSpinBox_min.setMaximum(stats.maximumValue)
                d.doubleSpinBox_max.setMinimum(stats.minimumValue)
                d.doubleSpinBox_max.setMaximum(stats.maximumValue)
                d.doubleSpinBox_min.setValue(stats.minimumValue)
                d.doubleSpinBox_max.setValue(stats.maximumValue)
                d.doubleSpinBox_min.blockSignals(False)
                d.doubleSpinBox_max.blockSignals(False)

            self._update_histogram(current_layer)

        except Exception as e:
            logger.error(f"Failed to compute raster statistics: {e}", exc_info=True)
            self.clear_statistics_display()

    def _refresh_statistics_async(self, layer, band_index: int, force_full_scan: bool = False):
        """Compute raster statistics asynchronously using QgsTask."""
        try:
            from qgis.core import QgsApplication
            from ...core.tasks.raster_stats_task import RasterStatsTask

            if self._stats_task:
                try:
                    self._stats_task.cancel()
                except Exception:
                    pass

            self._show_statistics_loading(layer.name(), band_index)

            self._stats_task = RasterStatsTask(
                layer=layer, band_index=band_index, force_full_scan=force_full_scan
            )
            self._stats_task.statsComputed.connect(self._on_stats_computed)
            self._stats_task.statsFailed.connect(self._on_stats_failed)
            QgsApplication.taskManager().addTask(self._stats_task)

            logger.info(f"Started async raster stats task for {layer.name()} band {band_index}")

        except ImportError as e:
            logger.warning(f"RasterStatsTask not available, falling back to sync: {e}")
            self._refresh_statistics_sync(layer, band_index, force_full_scan)
        except Exception as e:
            logger.error(f"Failed to start async stats task: {e}", exc_info=True)
            self.clear_statistics_display()

    def _refresh_statistics_sync(self, layer, band_index: int, force_full_scan: bool = False):
        """Synchronous fallback for raster statistics computation."""
        d = self.dockwidget
        try:
            from qgis.core import QgsRasterBandStats

            provider = layer.dataProvider()
            if not provider:
                self.clear_statistics_display()
                return

            total_pixels = layer.width() * layer.height()
            LARGE_RASTER_THRESHOLD = 10_000_000
            SAMPLE_SIZE = 250_000
            sample_size = SAMPLE_SIZE if (total_pixels > LARGE_RASTER_THRESHOLD and not force_full_scan) else 0

            stats = provider.bandStatistics(band_index, QgsRasterBandStats.All, layer.extent(), sample_size)

            nodata_value = None
            if provider.sourceHasNoDataValue(band_index):
                nodata_value = provider.sourceNoDataValue(band_index)

            self._update_statistics_display(
                min_val=stats.minimumValue, max_val=stats.maximumValue,
                mean_val=stats.mean, stddev_val=stats.stdDev,
                nodata_val=nodata_value, band_index=band_index, layer=layer
            )

            if hasattr(d, 'doubleSpinBox_min') and hasattr(d, 'doubleSpinBox_max'):
                d.doubleSpinBox_min.blockSignals(True)
                d.doubleSpinBox_max.blockSignals(True)
                d.doubleSpinBox_min.setMinimum(stats.minimumValue)
                d.doubleSpinBox_min.setMaximum(stats.maximumValue)
                d.doubleSpinBox_max.setMinimum(stats.minimumValue)
                d.doubleSpinBox_max.setMaximum(stats.maximumValue)
                d.doubleSpinBox_min.setValue(stats.minimumValue)
                d.doubleSpinBox_max.setValue(stats.maximumValue)
                d.doubleSpinBox_min.blockSignals(False)
                d.doubleSpinBox_max.blockSignals(False)

            self._update_histogram(layer)

        except Exception as e:
            logger.error(f"Sync raster stats failed: {e}", exc_info=True)
            self.clear_statistics_display()

    def _on_stats_computed(self, stats: dict):
        """Handle async raster statistics completion."""
        d = self.dockwidget
        try:
            self._update_statistics_display(
                min_val=stats['min'], max_val=stats['max'],
                mean_val=stats['mean'], stddev_val=stats['stddev'],
                nodata_val=stats['nodata'], band_index=stats['band_index'], layer=None
            )

            if hasattr(d, 'doubleSpinBox_min') and hasattr(d, 'doubleSpinBox_max'):
                d.doubleSpinBox_min.blockSignals(True)
                d.doubleSpinBox_max.blockSignals(True)
                d.doubleSpinBox_min.setMinimum(stats['min'])
                d.doubleSpinBox_min.setMaximum(stats['max'])
                d.doubleSpinBox_max.setMinimum(stats['min'])
                d.doubleSpinBox_max.setMaximum(stats['max'])
                d.doubleSpinBox_min.setValue(stats['min'])
                d.doubleSpinBox_max.setValue(stats['max'])
                d.doubleSpinBox_min.blockSignals(False)
                d.doubleSpinBox_max.blockSignals(False)

            layer = d._get_current_exploring_layer()
            if layer:
                self._update_histogram(layer)

        except Exception as e:
            logger.error(f"Error handling computed stats: {e}", exc_info=True)

    def _on_stats_failed(self, error_message: str):
        """Handle async raster statistics failure."""
        logger.warning(f"Async raster stats failed: {error_message}")
        self.clear_statistics_display()

    # ================================================================
    # SYNC & POPULATE METHODS (PUBLIC)
    # ================================================================

    def sync_with_layer(self, layer):
        """Synchronize all raster widgets with the given raster layer."""
        d = self.dockwidget
        if not layer or not isinstance(layer, QgsRasterLayer):
            self.clear_statistics_display()
            return
        try:
            logger.info(f"Syncing native raster widgets with layer '{layer.name()}'")
            self.populate_band_combobox(layer)

            if hasattr(d, 'comboBox_predicate') and d.comboBox_predicate.count() == 0:
                self.populate_predicate_combobox()

            weak_self = weakref.ref(self)
            captured_layer_id = layer.id()

            def deferred_stats_update():
                self_ref = weak_self()
                if not self_ref:
                    return
                try:
                    from qgis.core import QgsProject
                    fresh_layer = QgsProject.instance().mapLayer(captured_layer_id)
                    if fresh_layer and isinstance(fresh_layer, QgsRasterLayer):
                        self_ref._refresh_statistics(layer=fresh_layer)
                        self_ref._update_histogram(fresh_layer)
                except Exception as e:
                    logger.warning(f"Deferred raster update failed: {e}")

            QTimer.singleShot(100, deferred_stats_update)
            logger.info("Native raster widgets sync started (stats deferred)")

        except Exception as e:
            logger.error(f"Failed to sync native raster widgets: {e}", exc_info=True)

    def populate_band_combobox(self, layer):
        """Populate band combobox with available bands from raster layer."""
        d = self.dockwidget
        if not hasattr(d, 'comboBox_band'):
            return

        if QgsCheckableComboBoxBands and isinstance(d.comboBox_band, QgsCheckableComboBoxBands):
            d.comboBox_band.blockSignals(True)
            d.comboBox_band.setLayer(layer)
            d.comboBox_band.blockSignals(False)
        else:
            d.comboBox_band.blockSignals(True)
            d.comboBox_band.clear()
            if layer and isinstance(layer, QgsRasterLayer):
                band_count = layer.bandCount()
                for i in range(1, band_count + 1):
                    band_name = layer.bandName(i) if layer.bandName(i) else f"Band {i}"
                    d.comboBox_band.addItem(f"{i} - {band_name}")
            d.comboBox_band.blockSignals(False)

    def populate_predicate_combobox(self):
        """Populate the predicate combobox with available filter predicates."""
        d = self.dockwidget
        if not hasattr(d, 'comboBox_predicate'):
            return

        d.comboBox_predicate.blockSignals(True)
        d.comboBox_predicate.clear()

        predicates = [
            ("within_range", "Within Range (min \u2264 val \u2264 max)"),
            ("outside_range", "Outside Range (val < min OR val > max)"),
            ("above_value", "Above Value (val > min)"),
            ("below_value", "Below Value (val < max)"),
            ("equals_value", "Equals Value (val = min)"),
            ("is_nodata", "Is NoData"),
            ("is_not_nodata", "Is Not NoData"),
        ]
        for key, label in predicates:
            d.comboBox_predicate.addItem(label, key)

        d.comboBox_predicate.blockSignals(False)

    # ================================================================
    # UPDATE METHODS
    # ================================================================

    def _update_filter_from_ui(self):
        """Update raster filter based on current UI state."""
        d = self.dockwidget
        try:
            min_val = d.doubleSpinBox_min.value() if hasattr(d, 'doubleSpinBox_min') else 0
            max_val = d.doubleSpinBox_max.value() if hasattr(d, 'doubleSpinBox_max') else 0
            predicate_idx = d.comboBox_predicate.currentIndex() if hasattr(d, 'comboBox_predicate') else 0
            logger.debug(f"Updating raster filter: range=[{min_val}, {max_val}], predicate={predicate_idx}")
        except Exception as e:
            logger.warning(f"Error updating raster filter: {e}")

    def _update_statistics_display(self, min_val, max_val, mean_val, stddev_val,
                                   nodata_val, band_index, layer):
        """Update statistics display labels in the UI."""
        d = self.dockwidget

        def fmt(val, decimals=2):
            if val is None:
                return "--"
            return f"{val:.{decimals}f}"

        self._current_stats = {
            'min': min_val, 'max': max_val, 'mean': mean_val,
            'stddev': stddev_val, 'nodata': nodata_val
        }

        nodata_str = fmt(nodata_val) if nodata_val is not None else "--"
        if hasattr(d, 'label_stats_simplified'):
            d.label_stats_simplified.setText(
                f"\U0001f4ca Min: {fmt(min_val)} | Max: {fmt(max_val)} | "
                f"Mean: {fmt(mean_val)} | \u03c3: {fmt(stddev_val)} | NoData: {nodata_str}"
            )

        if hasattr(d, 'label_raster_metadata') and layer and layer.dataProvider():
            data_type = layer.dataProvider().dataType(band_index)
            type_name = self._get_data_type_name(data_type) if data_type else "Unknown"
            width = layer.width()
            height = layer.height()
            res_x = layer.rasterUnitsPerPixelX()
            res_y = layer.rasterUnitsPerPixelY()
            d.label_raster_metadata.setText(
                f"Data: {type_name} | Res: {res_x:.1f}\u00d7{res_y:.1f} | Size: {width}\u00d7{height}"
            )

    def clear_statistics_display(self):
        """Clear statistics display when no raster is selected."""
        d = self.dockwidget
        self._current_stats = None
        if hasattr(d, 'label_stats_simplified'):
            d.label_stats_simplified.setText(d.tr("\U0001f4ca Min: -- | Max: -- | Mean: -- | \u03c3: -- | NoData: --"))
        if hasattr(d, 'label_raster_metadata'):
            d.label_raster_metadata.setText(d.tr("Data: -- | Res: -- | Size: --"))

    def _show_statistics_loading(self, layer_name: str, band_index: int):
        """Show loading indicator while computing raster statistics."""
        d = self.dockwidget
        if hasattr(d, 'label_stats_simplified'):
            d.label_stats_simplified.setText(d.tr("\U0001f4ca Computing statistics..."))

    def _show_large_raster_placeholder(self, layer):
        """Show placeholder for large rasters."""
        d = self.dockwidget
        try:
            self.clear_statistics_display()
            width = layer.width()
            height = layer.height()
            total_pixels = width * height
            if hasattr(d, 'label_stats_simplified'):
                d.label_stats_simplified.setText(
                    f"\U0001f4ca Large raster ({width:,}\u00d7{height:,}) - Click 'Refresh' to compute stats"
                )
                d.label_stats_simplified.setToolTip(
                    f"Total pixels: {total_pixels:,}\nClick 'Refresh' to compute statistics"
                )
        except Exception as e:
            logger.warning(f"Error showing large raster placeholder: {e}")

    def _update_histogram(self, layer):
        """Update the interactive histogram widget with the current raster layer."""
        d = self.dockwidget
        if self._histogram is None:
            return
        try:
            if not layer or not isinstance(layer, QgsRasterLayer):
                return
            band_index = 1
            if hasattr(d, 'comboBox_band'):
                band_index = d.comboBox_band.currentIndex() + 1
                if band_index < 1:
                    band_index = 1
            self._histogram.set_layer(layer, band_index)
            logger.debug(f"Histogram updated for band {band_index}")
        except Exception as e:
            logger.error(f"Failed to update histogram: {e}")

    def _update_tool_buttons_state(self):
        """Update enabled state of raster tool buttons based on current layer."""
        d = self.dockwidget
        layer = d._get_current_exploring_layer()
        is_raster = layer is not None and isinstance(layer, QgsRasterLayer)

        tool_buttons = [
            'pushButton_raster_pixel_picker', 'pushButton_raster_rect_picker',
            'pushButton_raster_sync_histogram', 'pushButton_raster_all_bands',
            'pushButton_raster_reset_range', 'pushButton_add_pixel_to_selection',
        ]
        for btn_name in tool_buttons:
            if hasattr(d, btn_name):
                getattr(d, btn_name).setEnabled(is_raster)

    # ================================================================
    # HELPER METHODS
    # ================================================================

    def _ensure_exclusive_groupbox(self, current_groupbox, checked):
        """Ensure only one raster groupbox is expanded/checked at a time."""
        d = self.dockwidget
        if self._updating_groupboxes:
            return

        if not checked:
            current_groupbox.blockSignals(True)
            current_groupbox.setCollapsed(True)
            current_groupbox.blockSignals(False)
            for button, groupbox in self._tool_bindings.items():
                if groupbox == current_groupbox:
                    button.blockSignals(True)
                    button.setChecked(False)
                    button.blockSignals(False)
                    break
            return

        try:
            self._updating_groupboxes = True
            for gb in self._exclusive_groupboxes:
                gb.blockSignals(True)
                if gb == current_groupbox:
                    gb.setChecked(True)
                    gb.setCollapsed(False)
                else:
                    gb.setChecked(False)
                    gb.setCollapsed(True)
                gb.blockSignals(False)

            for button, groupbox in self._tool_bindings.items():
                button.blockSignals(True)
                button.setChecked(groupbox == current_groupbox)
                button.blockSignals(False)

            if hasattr(d, 'mGroupBox_raster_histogram') and current_groupbox == d.mGroupBox_raster_histogram:
                for button in self._tool_bindings.keys():
                    button.blockSignals(True)
                    button.setChecked(False)
                    button.blockSignals(False)

        except Exception as e:
            logger.warning(f"Error ensuring exclusive groupbox: {e}")
        finally:
            self._updating_groupboxes = False

    def _uncheck_tool_buttons(self):
        """Uncheck all checkable raster tool buttons (exclusive group only)."""
        d = self.dockwidget
        checkable_buttons = [
            'pushButton_raster_pixel_picker',
            'pushButton_raster_rect_picker',
            'pushButton_raster_sync_histogram',
        ]
        for btn_name in checkable_buttons:
            if hasattr(d, btn_name):
                btn = getattr(d, btn_name)
                if btn.isChecked():
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)

    def _trigger_combobox_for_groupbox(self, groupbox):
        """Trigger appropriate combobox action when a groupbox becomes active."""
        d = self.dockwidget
        try:
            if hasattr(d, 'mGroupBox_raster_histogram') and groupbox == d.mGroupBox_raster_histogram:
                if hasattr(d, 'comboBox_predicate'):
                    self._on_combobox_predicate_trigger(d.comboBox_predicate.currentIndex())
                if self._histogram:
                    layer = d._get_current_exploring_layer()
                    if layer and isinstance(layer, QgsRasterLayer):
                        self._update_histogram(layer)
                        self._histogram.update()
                        if hasattr(self._histogram, '_canvas'):
                            self._histogram._canvas.update()
            elif hasattr(d, 'mGroupBox_raster_rect_picker') and groupbox == d.mGroupBox_raster_rect_picker:
                pass
        except Exception as e:
            logger.warning(f"Error triggering combobox for groupbox: {e}")

    def _sync_button_from_groupbox(self, button, checked):
        """Sync raster tool button state from groupbox change."""
        try:
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
        except Exception as e:
            logger.warning(f"Error syncing button state: {e}")

    def _deactivate_pixel_picker_tool(self):
        """Deactivate the pixel picker tool and restore default tool."""
        try:
            from qgis.utils import iface
            if iface and iface.mapCanvas():
                if self._pixel_picker_tool:
                    iface.mapCanvas().unsetMapTool(self._pixel_picker_tool)
                logger.debug("Pixel picker tool deactivated")
        except Exception as e:
            logger.warning(f"Error deactivating pixel picker: {e}")

    def _is_large_raster(self, layer) -> bool:
        """Check if a raster is large enough to require deferred processing."""
        try:
            if not layer or not isinstance(layer, QgsRasterLayer):
                return False
            width = layer.width()
            height = layer.height()
            total_pixels = width * height
            LARGE_RASTER_THRESHOLD = 10_000_000
            if total_pixels > LARGE_RASTER_THRESHOLD:
                return True
            source = layer.source()
            if source.lower().endswith('.vrt'):
                return True
            provider = layer.dataProvider()
            if provider:
                provider_name = provider.name().lower()
                if 'vrt' in provider_name or 'virtual' in provider_name:
                    return True
            return False
        except Exception:
            return True

    def _get_data_type_name(self, data_type):
        """Convert QGIS raster data type to human-readable name."""
        from qgis.core import Qgis
        type_names = {
            Qgis.Byte: "Byte", Qgis.UInt16: "UInt16", Qgis.Int16: "Int16",
            Qgis.UInt32: "UInt32", Qgis.Int32: "Int32",
            Qgis.Float32: "Float32", Qgis.Float64: "Float64",
        }
        return type_names.get(data_type, "Unknown")

    def dispatch_operations(self, source_layer, raster_targets: list, options: dict = None):
        """Dispatch vector-to-raster operations (Clip/Mask/Zonal)."""
        from qgis.core import QgsProject, QgsVectorLayer
        options = options or {}
        try:
            from ...core.services.raster_filter_service import (
                RasterFilterService, VectorFilterRequest, RasterOperation
            )
            service = RasterFilterService()
            op_map = {
                'Clip': RasterOperation.CLIP,
                'Mask Outside': RasterOperation.MASK_OUTSIDE,
                'Mask Inside': RasterOperation.MASK_INSIDE,
                'Zonal Stats': RasterOperation.ZONAL_STATS,
            }
            for raster_layer, operation in raster_targets:
                if operation == 'Skip':
                    continue
                raster_op = op_map.get(operation, RasterOperation.CLIP)
                has_selection = (hasattr(source_layer, 'selectedFeatureCount')
                                 and source_layer.selectedFeatureCount() > 0)
                request = VectorFilterRequest(
                    vector_layer=source_layer, raster_layer=raster_layer,
                    operation=raster_op, use_selected_only=has_selection,
                    nodata_value=options.get('nodata_value', -9999),
                )
                logger.info(f"EPIC-6: {operation} on {raster_layer.name()} with options {options}")
                result = service.apply_vector_to_raster(request)
                if result.success:
                    if result.output_layer and options.get('add_to_project', True):
                        QgsProject.instance().addMapLayer(result.output_layer)
                    from qgis.utils import iface
                    iface.messageBar().pushSuccess("FilterMate", f"{operation}: {raster_layer.name()} \u2713")
                else:
                    from qgis.utils import iface
                    iface.messageBar().pushWarning(
                        "FilterMate", f"{operation} failed on {raster_layer.name()}: {result.error_message}"
                    )
        except ImportError as e:
            logger.error(f"RasterFilterService not available: {e}")
        except Exception as e:
            logger.error(f"Raster operation failed: {e}", exc_info=True)

    def export_layer(self, layer, settings: dict):
        """Export a single raster layer."""
        d = self.dockwidget
        try:
            from ...core.export import (
                RasterExporter, RasterExportConfig, RasterExportFormat, CompressionType
            )
            from qgis.core import QgsVectorLayer

            format_str = settings.get('format', 'GeoTIFF (.tif)')
            output_dir = settings.get('output_dir', '')
            raster_opts = settings.get('raster', {})

            if 'COG' in format_str:
                export_format = RasterExportFormat.COG
            else:
                export_format = RasterExportFormat.GEOTIFF

            filename = f"{layer.name()}.tif"
            output_path = os.path.join(output_dir, filename)

            compression_str = raster_opts.get('compression', 'LZW').upper()
            try:
                compression = CompressionType[compression_str]
            except KeyError:
                compression = CompressionType.LZW

            config = RasterExportConfig(
                layer=layer, output_path=output_path, format=export_format,
                compression=compression,
                create_pyramids=raster_opts.get('create_pyramids', False),
                include_world_file=raster_opts.get('include_world', False)
            )

            if raster_opts.get('clip_extent', False):
                current_layer = d._get_current_exploring_layer()
                if isinstance(current_layer, QgsVectorLayer):
                    config.mask_layer = current_layer

            exporter = RasterExporter()
            exporter.progressChanged.connect(d._on_export_progress)
            result = exporter.export(config)

            from qgis.utils import iface
            if result.success:
                iface.messageBar().pushSuccess(
                    "FilterMate", f"Raster exported: {result.output_path} ({result.output_size_mb:.1f} MB)"
                )
            else:
                iface.messageBar().pushCritical("FilterMate", f"Export failed: {result.error_message}")

        except ImportError as e:
            logger.error(f"Failed to import raster exporter: {e}")
        except Exception as e:
            logger.exception(f"Raster export error: {e}")
