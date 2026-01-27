# -*- coding: utf-8 -*-
"""
FilterMate Raster Exploring Controller.

Controller for the Raster Exploring GroupBox, managing:
- Raster layer selection and validation
- Statistics computation and display
- Histogram visualization
- Pixel identification on map
- Transparency controls

EPIC-2: Raster Integration
US-09: Controller Integration

Author: FilterMate Team
Date: January 2026
"""
import logging
from typing import TYPE_CHECKING, Optional, Tuple

try:
    from qgis.core import (
        QgsMapLayer,
        QgsProject,
        QgsRasterLayer,
    )
    from qgis.gui import QgsMapTool
    from qgis.PyQt.QtCore import pyqtSignal, QTimer
    from qgis.utils import iface
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    pyqtSignal = None
    QgsMapLayer = None
    QgsRasterLayer = None

from .base_controller import BaseController
from ...core.ports.raster_port import RasterPort
from ...core.services.raster_stats_service import (
    RasterStatsService,
    StatsRequest,
)

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...adapters.qgis.signals.signal_manager import SignalManager
    from ...ui.widgets.raster_groupbox import RasterExploringGroupBox
    from ...ui.widgets.pixel_identify_widget import RasterIdentifyMapTool

logger = logging.getLogger('FilterMate.Controllers.RasterExploring')


class RasterExploringController(BaseController):
    """
    Controller for the Raster Exploring GroupBox.

    Orchestrates between:
    - RasterExploringGroupBox (UI)
    - RasterStatsService (business logic)
    - QGISRasterBackend (data access)

    Responsibilities:
    - Detect and validate raster layers
    - Trigger statistics computation
    - Update UI with results
    - Manage pixel identify map tool
    - Apply transparency settings to layers

    Signals:
        stats_computed: Emitted when statistics are computed
        layer_changed: Emitted when raster layer changes
        error_occurred: Emitted on error
    """

    # === Signals ===
    if QGIS_AVAILABLE and pyqtSignal:
        stats_computed = pyqtSignal(str)  # layer_id
        layer_changed = pyqtSignal(object)  # QgsRasterLayer or None
        error_occurred = pyqtSignal(str)  # error message

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        raster_backend: Optional[RasterPort] = None,
        signal_manager: Optional['SignalManager'] = None
    ):
        """
        Initialize the Raster Exploring Controller.

        Args:
            dockwidget: Parent dockwidget for UI access
            raster_backend: RasterPort implementation (auto-created if None)
            signal_manager: Centralized signal manager
        """
        super().__init__(dockwidget, None, signal_manager)

        # Services
        self._raster_backend = raster_backend
        self._stats_service: Optional[RasterStatsService] = None

        # State
        self._current_layer: Optional[QgsRasterLayer] = None
        self._groupbox: Optional['RasterExploringGroupBox'] = None
        self._active_map_tool: Optional['RasterIdentifyMapTool'] = None
        self._previous_map_tool: Optional[QgsMapTool] = None
        self._current_band: int = 1

        # Debounce timer for stats computation
        self._stats_timer = QTimer()
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(300)
        self._stats_timer.timeout.connect(self._do_compute_stats)

    # =========================================================================
    # BaseController Implementation
    # =========================================================================

    def setup(self) -> None:
        """Initialize controller and connect signals."""
        logger.debug("[RasterExploringController] Setting up...")

        # Initialize backend if not provided
        if self._raster_backend is None:
            self._raster_backend = self._create_raster_backend()

        # Initialize stats service
        if self._raster_backend:
            self._stats_service = RasterStatsService(self._raster_backend)

        # Get groupbox from dockwidget
        self._groupbox = self._get_raster_groupbox()

        # Connect signals
        self._connect_signals()

        # Connect to project layer signals
        self._connect_project_signals()

        logger.debug("[RasterExploringController] Setup complete")

    def teardown(self) -> None:
        """Clean up controller resources."""
        logger.debug("[RasterExploringController] Tearing down...")

        # Restore previous map tool if we changed it
        self._restore_map_tool()

        # Disconnect signals
        self._disconnect_all_signals()

        # Clear state
        self._current_layer = None
        self._groupbox = None
        self._stats_service = None

        logger.debug("[RasterExploringController] Teardown complete")

    def on_tab_activated(self) -> None:
        """Called when the exploring tab is activated."""
        super().on_tab_activated()
        # Refresh if layer is set
        if self._current_layer and self._groupbox:
            self._request_stats_update()

    def on_tab_deactivated(self) -> None:
        """Called when switching away from the exploring tab."""
        super().on_tab_deactivated()
        # Restore map tool when leaving tab
        self._restore_map_tool()

    # =========================================================================
    # Public API
    # =========================================================================

    def set_layer(self, layer: Optional[QgsRasterLayer]) -> None:
        """
        Set the current raster layer.

        Args:
            layer: Raster layer to analyze, or None to clear
        """
        # Validate layer type
        if layer is not None and not self._is_raster_layer(layer):
            logger.warning(
                f"[RasterExploringController] Layer '{layer.name()}' "
                "is not a raster layer"
            )
            layer = None

        # Update state
        old_layer = self._current_layer
        self._current_layer = layer

        # Update groupbox
        if self._groupbox:
            if layer:
                self._groupbox.setVisible(True)
                self._groupbox.set_layer(layer)
                self._groupbox.set_stats_service(self._stats_service)
                self._request_stats_update()
            else:
                self._groupbox.clear()
                self._groupbox.setVisible(False)

        # Emit signal
        if QGIS_AVAILABLE and old_layer != layer:
            self.layer_changed.emit(layer)

        logger.debug(
            f"[RasterExploringController] Layer set to: "
            f"{layer.name() if layer else 'None'}"
        )

    def get_current_layer(self) -> Optional[QgsRasterLayer]:
        """Get the current raster layer."""
        return self._current_layer

    def refresh_statistics(self) -> None:
        """Force refresh of statistics for current layer."""
        if self._current_layer and self._stats_service:
            # Clear cache for this layer
            self._stats_service.invalidate_cache(self._current_layer.id())
            self._request_stats_update()

    def set_current_band(self, band_index: int) -> None:
        """
        Set the current band for analysis.

        Args:
            band_index: 1-based band index
        """
        if band_index < 1:
            band_index = 1

        self._current_band = band_index

        # Update histogram
        if self._groupbox:
            self._groupbox.update_histogram(band_index)

        logger.debug(
            f"[RasterExploringController] Current band set to {band_index}"
        )

    def activate_identify_tool(self) -> None:
        """Activate the pixel identify map tool."""
        if not QGIS_AVAILABLE:
            return

        canvas = iface.mapCanvas()
        if not canvas:
            return

        # Save current tool
        if self._active_map_tool is None:
            self._previous_map_tool = canvas.mapTool()

        # Get identify widget and its map tool
        if self._groupbox:
            identify_widget = self._groupbox.pixel_identify_widget
            if identify_widget and hasattr(identify_widget, 'map_tool'):
                self._active_map_tool = identify_widget.map_tool
                canvas.setMapTool(self._active_map_tool)
                logger.debug(
                    "[RasterExploringController] Identify tool activated"
                )

    def deactivate_identify_tool(self) -> None:
        """Deactivate the pixel identify tool and restore previous."""
        self._restore_map_tool()

    def apply_transparency(
        self,
        opacity: float,
        value_range: Optional[Tuple[float, float]] = None
    ) -> None:
        """
        Apply transparency settings to current layer.

        Args:
            opacity: Layer opacity (0.0 to 1.0)
            value_range: Optional (min, max) for value-based transparency
        """
        if not self._current_layer:
            logger.warning(
                "[RasterExploringController] No layer to apply transparency"
            )
            return

        # Apply opacity
        self._current_layer.setOpacity(opacity)

        # Apply value-based transparency if provided
        if value_range and self._raster_backend:
            from ...core.ports.raster_port import TransparencySettings
            settings = TransparencySettings(
                global_opacity=opacity,
                no_data_transparent=True,
                transparent_pixel_list=[],
                transparent_value_ranges=[value_range]
            )
            try:
                self._raster_backend.apply_transparency(
                    self._current_layer.id(),
                    settings
                )
            except Exception as e:
                logger.error(
                    f"[RasterExploringController] "
                    f"Failed to apply value transparency: {e}"
                )

        # Refresh layer
        self._current_layer.triggerRepaint()

        logger.info(
            f"[RasterExploringController] Applied transparency to "
            f"'{self._current_layer.name()}': opacity={opacity:.0%}"
        )

    # =========================================================================
    # Signal Connections
    # =========================================================================

    def _connect_signals(self) -> None:
        """Connect widget signals to controller slots."""
        if not self._groupbox:
            return

        # Stats panel signals
        stats_panel = self._groupbox.stats_panel
        if stats_panel:
            stats_panel.band_changed.connect(self._on_band_changed)
            stats_panel.refresh_requested.connect(self.refresh_statistics)

        # Histogram signals
        histogram = self._groupbox.histogram_widget
        if histogram:
            histogram.range_changed.connect(self._on_histogram_range_changed)
            histogram.refresh_requested.connect(self._on_histogram_refresh)

        # Pixel identify signals
        identify = self._groupbox.pixel_identify_widget
        if identify:
            identify.identify_requested.connect(self.activate_identify_tool)
            identify.clear_requested.connect(self._on_identify_clear)

        # Transparency signals
        transparency = self._groupbox.transparency_widget
        if transparency:
            transparency.opacity_changed.connect(self._on_opacity_changed)
            transparency.range_changed.connect(self._on_range_transparency)
            transparency.apply_requested.connect(self._on_apply_transparency)

        # Groupbox signals
        self._groupbox.stats_refresh_requested.connect(self.refresh_statistics)

        logger.debug(
            "[RasterExploringController] Widget signals connected"
        )

    def _connect_project_signals(self) -> None:
        """Connect to QGIS project signals for layer changes."""
        if not QGIS_AVAILABLE:
            return

        project = QgsProject.instance()

        # Layer removed
        project.layerRemoved.connect(self._on_layer_removed)

        # Layer added (to auto-detect raster layers)
        project.layerWasAdded.connect(self._on_layer_added)

        logger.debug(
            "[RasterExploringController] Project signals connected"
        )

    # =========================================================================
    # Signal Handlers
    # =========================================================================

    def _on_band_changed(self, band_index: int) -> None:
        """Handle band selection change."""
        self.set_current_band(band_index)

    def _on_histogram_range_changed(
        self,
        min_val: float,
        max_val: float
    ) -> None:
        """Handle histogram range selection."""
        logger.debug(
            f"[RasterExploringController] Histogram range: "
            f"[{min_val:.2f}, {max_val:.2f}]"
        )

        # Sync with transparency widget
        if self._groupbox:
            transparency = self._groupbox.transparency_widget
            if transparency:
                transparency.set_selection_range(min_val, max_val)

    def _on_histogram_refresh(self) -> None:
        """Handle histogram refresh request."""
        if self._groupbox:
            self._groupbox.update_histogram(self._current_band)

    def _on_identify_clear(self) -> None:
        """Handle identify clear request."""
        self._restore_map_tool()

    def _on_opacity_changed(self, opacity: float) -> None:
        """Handle opacity slider change."""
        if self._current_layer:
            self._current_layer.setOpacity(opacity)
            self._current_layer.triggerRepaint()

    def _on_range_transparency(
        self,
        min_val: float,
        max_val: float
    ) -> None:
        """Handle range transparency change."""
        logger.debug(
            f"[RasterExploringController] Range transparency: "
            f"[{min_val:.2f}, {max_val:.2f}]"
        )

    def _on_apply_transparency(self) -> None:
        """Handle apply transparency request."""
        if not self._groupbox:
            return

        transparency = self._groupbox.transparency_widget
        if not transparency:
            return

        opacity = transparency.opacity
        value_range = transparency.transparency_range

        self.apply_transparency(opacity, value_range)

    def _on_layer_removed(self, layer_id: str) -> None:
        """Handle layer removed from project."""
        if self._current_layer and self._current_layer.id() == layer_id:
            self.set_layer(None)

    def _on_layer_added(self, layer: QgsMapLayer) -> None:
        """Handle layer added to project."""
        # Auto-select first raster layer if none selected
        if self._current_layer is None and self._is_raster_layer(layer):
            logger.debug(
                f"[RasterExploringController] Auto-selecting raster layer: "
                f"'{layer.name()}'"
            )
            # Don't auto-select, let user choose
            pass

    # =========================================================================
    # Statistics Computation
    # =========================================================================

    def _request_stats_update(self) -> None:
        """Request a debounced statistics update."""
        self._stats_timer.start()

    def _do_compute_stats(self) -> None:
        """Compute statistics for current layer."""
        if not self._current_layer or not self._stats_service:
            return

        layer_id = self._current_layer.id()

        try:
            # Create request
            request = StatsRequest(
                layer_id=layer_id,
                include_histogram=True,
                histogram_bins=256,
                sample_size=0,  # Full statistics
                callback=self._on_stats_computed
            )

            # Compute (synchronous for now)
            self._stats_service.compute_statistics(request)

        except Exception as e:
            error_msg = f"Failed to compute statistics: {e}"
            logger.error(f"[RasterExploringController] {error_msg}")
            if QGIS_AVAILABLE:
                self.error_occurred.emit(error_msg)

    def _on_stats_computed(self, response) -> None:
        """Handle statistics computation result."""
        if not response.is_success:
            logger.error(
                f"[RasterExploringController] Stats computation failed: "
                f"{response.error_message}"
            )
            return

        # Update UI via groupbox
        if self._groupbox:
            # Stats panel is updated via set_layer
            # Update histogram for current band
            self._groupbox.update_histogram(self._current_band)

        # Emit signal
        if QGIS_AVAILABLE:
            self.stats_computed.emit(response.request.layer_id)

        logger.debug(
            f"[RasterExploringController] Stats computed in "
            f"{response.computation_time_ms:.1f}ms"
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_raster_groupbox(self) -> Optional['RasterExploringGroupBox']:
        """Get the raster groupbox from dockwidget."""
        if not self.dockwidget:
            return None

        # Try different attribute names
        for attr in [
            'raster_exploring_groupbox',
            'rasterExploringGroupBox',
            '_raster_groupbox'
        ]:
            if hasattr(self.dockwidget, attr):
                return getattr(self.dockwidget, attr)

        return None

    def _create_raster_backend(self) -> Optional[RasterPort]:
        """Create the QGIS raster backend."""
        try:
            from ...adapters.backends.qgis_raster_backend import (
                QGISRasterBackend
            )
            return QGISRasterBackend()
        except ImportError as e:
            logger.error(
                f"[RasterExploringController] "
                f"Failed to create raster backend: {e}"
            )
            return None

    def _is_raster_layer(self, layer) -> bool:
        """Check if layer is a raster layer."""
        if not QGIS_AVAILABLE:
            return False

        if layer is None:
            return False

        # Check layer type
        if hasattr(layer, 'type'):
            return layer.type() == QgsMapLayer.RasterLayer

        # Fallback: check class name
        return 'RasterLayer' in type(layer).__name__

    def _restore_map_tool(self) -> None:
        """Restore the previous map tool."""
        if not QGIS_AVAILABLE:
            return

        canvas = iface.mapCanvas()
        if canvas and self._previous_map_tool:
            canvas.setMapTool(self._previous_map_tool)
            self._active_map_tool = None
            self._previous_map_tool = None
            logger.debug(
                "[RasterExploringController] Previous map tool restored"
            )
