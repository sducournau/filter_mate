"""
FilterMate Raster Exploring Controller.

Phase 1: Layer Info display + Raster Value Sampling.
Phase 2: Histogram computation + Band Viewer compositions.

Responsibilities:
    - Update layer info labels when a raster layer is selected
    - Populate band combo dynamically from raster layer
    - Launch RasterSamplingTask on "Sample" button click
    - Display sampling results and enable "Apply Filter"
    - Apply filter to vector layer via selectByIds()
    - Compute and display band histogram (Phase 2)
    - Apply band compositions and presets (Phase 2)

Thread Safety:
    - Sampling runs as QgsTask (background thread)
    - Results arrive via QObject signals (thread-safe delivery to main thread)
    - NO layer objects are passed to the task; only URIs
    - Histogram computation runs in main thread (fast via QGIS cache)
"""
import logging
from typing import TYPE_CHECKING, List, Optional

from qgis.PyQt.QtCore import QTimer, pyqtSignal

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class RasterExploringController(BaseController):
    """Controller for the Raster Exploring panel.

    Phase 1: Manages Layer Info + Value Sampling groupboxes.
    Wired to dockwidget widgets created in _setup_dual_mode_exploring().

    Attributes:
        raster_layer_changed: Signal emitted when the active raster layer changes.
    """

    raster_layer_changed = pyqtSignal(object)  # QgsRasterLayer or None

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        filter_service=None,
        signal_manager=None,
    ):
        super().__init__(
            dockwidget=dockwidget,
            filter_service=filter_service,
            signal_manager=signal_manager,
        )
        self._current_raster_layer = None
        self._current_sampling_task = None
        self._last_sampling_result = None

        # Phase 2: Histogram state
        self._histogram_range_debounce = QTimer()
        self._histogram_range_debounce.setSingleShot(True)
        self._histogram_range_debounce.setInterval(300)
        self._histogram_range_debounce.timeout.connect(
            self._on_histogram_range_debounced
        )
        self._pending_range: Optional[tuple] = None
        self._last_histogram_stats: Optional[dict] = None

    def setup(self) -> None:
        """Initialize the raster exploring controller.

        Connects UI widgets to controller methods.
        Called once during dockwidget initialization.
        """
        dw = self.dockwidget

        # Connect "Sample" button
        try:
            if hasattr(dw, '_btn_raster_sample'):
                dw._btn_raster_sample.clicked.connect(self._on_sample_clicked)
                logger.debug("RasterExploringController: connected _btn_raster_sample")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: sample button not ready: {e}")

        # Connect "Apply Filter" button
        try:
            if hasattr(dw, '_btn_raster_apply_filter'):
                dw._btn_raster_apply_filter.clicked.connect(
                    self._on_apply_filter_clicked
                )
                logger.debug("RasterExploringController: connected _btn_raster_apply_filter")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: apply button not ready: {e}")

        # Connect raster layer combo change (for syncing band combo)
        try:
            if hasattr(dw, '_combo_raster_layer'):
                dw._combo_raster_layer.layerChanged.connect(
                    self._on_raster_combo_changed
                )
                logger.debug("RasterExploringController: connected _combo_raster_layer")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: raster combo not ready: {e}")

        # Phase 2: Histogram connections
        self._setup_histogram_connections()

        # Phase 2: Band Viewer connections
        self._setup_band_viewer_connections()

        logger.debug("RasterExploringController.setup() complete (Phase 2)")

    def teardown(self) -> None:
        """Clean up the raster exploring controller."""
        # Cancel any running task
        if self._current_sampling_task is not None:
            try:
                self._current_sampling_task.cancel()
            except (RuntimeError, AttributeError):
                pass
            self._current_sampling_task = None

        # Phase 2: Stop debounce timer
        try:
            self._histogram_range_debounce.stop()
        except (RuntimeError, AttributeError):
            pass

        self._current_raster_layer = None
        self._last_sampling_result = None
        self._last_histogram_stats = None
        self._pending_range = None
        self._disconnect_all_signals()
        logger.debug("RasterExploringController.teardown()")

    @property
    def current_raster_layer(self):
        """Return the current raster layer, if any."""
        return self._current_raster_layer

    def set_raster_layer(self, layer) -> None:
        """Update the current raster layer reference and refresh UI.

        Called by _on_dual_mode_layer_changed() when a raster layer is selected
        in the QGIS layer tree.

        Args:
            layer: QgsRasterLayer or None
        """
        if layer is self._current_raster_layer:
            return
        self._current_raster_layer = layer
        self.raster_layer_changed.emit(layer)

        # Update UI (Phase 1)
        self._update_layer_info(layer)
        self._update_band_combo(layer)

        # Sync the raster combo to the selected layer
        self._sync_raster_combo(layer)

        # Reset sampling state
        self._reset_sampling_state()

        # Phase 2: Update histogram band combo + band table
        self._update_histogram_band_combo(layer)
        self._populate_band_table()
        self._update_band_rgb_combos(layer)
        self._clear_histogram()

        layer_name = layer.name() if layer else "None"
        logger.debug(f"RasterExploringController: raster layer set to {layer_name}")

    # ================================================================
    # Layer Info
    # ================================================================

    def _update_layer_info(self, layer) -> None:
        """Populate the Layer Info groupbox labels from raster layer metadata.

        Args:
            layer: QgsRasterLayer or None.
        """
        dw = self.dockwidget

        if layer is None or not layer.isValid():
            self._clear_layer_info()
            return

        try:
            provider = layer.dataProvider()
            if provider is None:
                self._clear_layer_info()
                return

            # Name
            if hasattr(dw, '_lbl_raster_name'):
                dw._lbl_raster_name.setText(layer.name())

            # Format + COG detection
            if hasattr(dw, '_lbl_raster_format'):
                format_str = provider.description() if provider.description() else "Unknown"
                # Detect COG
                is_cog = self._detect_cog(provider)
                if is_cog:
                    format_str += " (COG: " + dw.tr("Yes") + ")"
                dw._lbl_raster_format.setText(format_str)

            # Size + pixel size
            if hasattr(dw, '_lbl_raster_size'):
                pixel_x = layer.rasterUnitsPerPixelX()
                pixel_y = layer.rasterUnitsPerPixelY()
                size_str = (
                    f"{layer.width()} x {layer.height()} px  |  "
                    f"{pixel_x:.2f} x {pixel_y:.2f}"
                )
                # Add unit from CRS
                crs = layer.crs()
                if crs.isValid():
                    try:
                        unit = crs.mapUnits()
                        from qgis.core import Qgis
                        # Map unit enum to string
                        unit_str = self._map_unit_string(unit)
                        size_str += f" {unit_str}"
                    except Exception:
                        pass
                dw._lbl_raster_size.setText(size_str)

            # Bands info
            if hasattr(dw, '_lbl_raster_bands'):
                band_count = layer.bandCount()
                bands_info = str(band_count)
                # Add data type of first band
                if band_count > 0 and provider is not None:
                    try:
                        dtype = provider.dataType(1)
                        dtype_name = self._data_type_string(dtype)
                        bands_info += f" ({dtype_name})"
                    except Exception:
                        pass
                # Add NoData of first band
                if band_count > 0 and provider is not None:
                    try:
                        if provider.sourceHasNoDataValue(1):
                            nodata = provider.sourceNoDataValue(1)
                            bands_info += f"  |  NoData: {nodata}"
                    except Exception:
                        pass
                dw._lbl_raster_bands.setText(bands_info)

            # CRS
            if hasattr(dw, '_lbl_raster_crs'):
                crs = layer.crs()
                if crs.isValid():
                    dw._lbl_raster_crs.setText(
                        f"{crs.authid()} ({crs.description()})"
                    )
                else:
                    dw._lbl_raster_crs.setText(dw.tr("Unknown"))

            # Extent
            if hasattr(dw, '_lbl_raster_extent'):
                extent = layer.extent()
                dw._lbl_raster_extent.setText(
                    f"[{extent.xMinimum():.2f}, {extent.yMinimum():.2f}, "
                    f"{extent.xMaximum():.2f}, {extent.yMaximum():.2f}]"
                )

        except Exception as e:
            logger.warning(f"Failed to update raster layer info: {e}")
            self._clear_layer_info()

    def _clear_layer_info(self) -> None:
        """Reset all layer info labels to empty state."""
        dw = self.dockwidget
        for attr in (
            '_lbl_raster_name', '_lbl_raster_format', '_lbl_raster_size',
            '_lbl_raster_bands', '_lbl_raster_crs', '_lbl_raster_extent',
        ):
            try:
                lbl = getattr(dw, attr, None)
                if lbl is not None:
                    lbl.setText("-")
            except (AttributeError, RuntimeError):
                pass

    # ================================================================
    # Band Combo
    # ================================================================

    def _update_band_combo(self, layer) -> None:
        """Populate the band combo from the raster layer's band count.

        Uses blockSignals to prevent spurious signal emission during population.

        Args:
            layer: QgsRasterLayer or None.
        """
        dw = self.dockwidget
        combo = getattr(dw, '_combo_raster_band', None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        if layer is not None and layer.isValid():
            band_count = layer.bandCount()
            for i in range(1, band_count + 1):
                try:
                    provider = layer.dataProvider()
                    band_name = provider.generateBandName(i) if provider else f"Band {i}"
                except Exception:
                    band_name = f"Band {i}"
                combo.addItem(band_name, i)

        combo.blockSignals(False)

    def _sync_raster_combo(self, layer) -> None:
        """Sync the raster layer combo to match the currently active layer.

        Args:
            layer: QgsRasterLayer to select in combo.
        """
        dw = self.dockwidget
        combo = getattr(dw, '_combo_raster_layer', None)
        if combo is None or layer is None:
            return

        try:
            # QgsMapLayerComboBox has setLayer()
            if hasattr(combo, 'setLayer'):
                combo.blockSignals(True)
                combo.setLayer(layer)
                combo.blockSignals(False)
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"Could not sync raster combo: {e}")

    def _on_raster_combo_changed(self, layer) -> None:
        """Handle raster layer combo change (user picks a different raster).

        Args:
            layer: QgsRasterLayer selected in combo.
        """
        if layer is None:
            return
        try:
            from qgis.core import QgsRasterLayer
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                self._current_raster_layer = layer
                self._update_layer_info(layer)
                self._update_band_combo(layer)
                self._reset_sampling_state()
                # Phase 2
                self._update_histogram_band_combo(layer)
                self._populate_band_table()
                self._update_band_rgb_combos(layer)
                self._clear_histogram()
        except Exception as e:
            logger.debug(f"_on_raster_combo_changed: {e}")

    # ================================================================
    # Value Sampling
    # ================================================================

    def _on_sample_clicked(self) -> None:
        """Handle "Sample" button click. Launch RasterSamplingTask."""
        dw = self.dockwidget

        try:
            from qgis.core import QgsApplication, QgsRasterLayer

            # Get raster layer (from combo or current)
            raster_layer = self._get_raster_layer_from_combo()
            if raster_layer is None or not raster_layer.isValid():
                self._show_result(dw.tr("No valid raster layer selected"))
                return

            # Get vector layer from combo
            vector_layer = self._get_vector_layer_from_combo()
            if vector_layer is None or not vector_layer.isValid():
                self._show_result(dw.tr("No valid vector layer selected"))
                return

            if vector_layer.featureCount() == 0:
                self._show_result(dw.tr("Vector layer has no features"))
                return

            # Get parameters
            band = self._get_selected_band()
            method = self._get_selected_method()
            operator = self._get_selected_operator()
            threshold = self._get_threshold()
            threshold_max = self._get_threshold_max()

            # Build URIs (thread-safe)
            raster_uri = raster_layer.source()
            vector_uri = vector_layer.source()

            # Import task
            from ...core.tasks.raster_sampling_task import RasterSamplingTask
            from ...core.domain.raster_filter_criteria import ComparisonOperator

            # Cancel any existing task
            if self._current_sampling_task is not None:
                try:
                    self._current_sampling_task.cancel()
                except (RuntimeError, AttributeError):
                    pass

            # Create and configure task
            task = RasterSamplingTask(
                raster_uri=raster_uri,
                vector_uri=vector_uri,
                band=band,
                method=method,
                operator=operator,
                threshold=threshold,
                threshold_max=threshold_max,
                description=dw.tr("Raster Sampling"),
            )

            # Connect signals
            task.signals.completed.connect(self._on_sampling_complete)
            task.signals.error.connect(self._on_sampling_error)
            task.signals.progress_updated.connect(self._on_sampling_progress)

            # Store reference
            self._current_sampling_task = task

            # Update UI state
            self._set_sampling_in_progress(True)
            self._show_result(dw.tr("Sampling in progress..."))

            # Add to QGIS task manager
            QgsApplication.taskManager().addTask(task)
            logger.info(
                f"RasterSamplingTask launched: raster={raster_layer.name()}, "
                f"vector={vector_layer.name()}, band={band}, method={method}"
            )

        except Exception as e:
            logger.error(f"Failed to launch raster sampling: {e}", exc_info=True)
            self._show_result(f"Error: {e}")
            self._set_sampling_in_progress(False)

    def _on_sampling_complete(self, result, task_id: str) -> None:
        """Handle successful sampling completion (main thread).

        Args:
            result: RasterSamplingResult instance.
            task_id: Task identifier string.
        """
        self._current_sampling_task = None
        self._last_sampling_result = result
        self._set_sampling_in_progress(False)

        dw = self.dockwidget

        # Show result summary
        self._show_result(result.summary())

        # Enable "Apply Filter" button
        if hasattr(dw, '_btn_raster_apply_filter'):
            dw._btn_raster_apply_filter.setEnabled(
                result.matching_count > 0
            )

        logger.info(f"Raster sampling complete: {result.summary()}")

    def _on_sampling_error(self, error_msg: str, task_id: str) -> None:
        """Handle sampling error (main thread).

        Args:
            error_msg: Error description.
            task_id: Task identifier string.
        """
        self._current_sampling_task = None
        self._set_sampling_in_progress(False)
        self._show_result(f"Error: {error_msg}")
        logger.error(f"Raster sampling failed: {error_msg}")

    def _on_sampling_progress(self, processed: int, total: int) -> None:
        """Update progress bar during sampling.

        Args:
            processed: Number of features processed so far.
            total: Total number of features.
        """
        dw = self.dockwidget
        progress = getattr(dw, '_progress_raster_sampling', None)
        if progress is not None:
            progress.setMaximum(total)
            progress.setValue(processed)

    # ================================================================
    # Apply Filter
    # ================================================================

    def _on_apply_filter_clicked(self) -> None:
        """Apply the sampling result as a selection on the vector layer."""
        dw = self.dockwidget

        if self._last_sampling_result is None:
            self._show_result(dw.tr("No sampling result available"))
            return

        result = self._last_sampling_result
        if result.matching_count == 0:
            self._show_result(dw.tr("No features match the criteria"))
            return

        try:
            # Get the vector layer
            vector_layer = self._get_vector_layer_from_combo()
            if vector_layer is None or not vector_layer.isValid():
                self._show_result(dw.tr("No valid vector layer"))
                return

            # Apply selection using selectByIds
            vector_layer.selectByIds(result.matching_ids)

            self._show_result(
                dw.tr("{count}/{total} features selected").format(
                    count=result.matching_count,
                    total=result.total_features,
                )
            )
            logger.info(
                f"Raster filter applied: {result.matching_count}/{result.total_features} "
                f"features selected on {vector_layer.name()}"
            )

            # Refresh canvas
            try:
                from qgis.utils import iface as qgis_iface
                if qgis_iface:
                    qgis_iface.mapCanvas().refresh()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to apply raster filter: {e}", exc_info=True)
            self._show_result(f"Error: {e}")

    # ================================================================
    # UI Helpers
    # ================================================================

    def _show_result(self, text: str) -> None:
        """Update the result label text."""
        dw = self.dockwidget
        lbl = getattr(dw, '_lbl_raster_result', None)
        if lbl is not None:
            lbl.setText(text)

    def _set_sampling_in_progress(self, in_progress: bool) -> None:
        """Toggle UI state between sampling/idle.

        Args:
            in_progress: True when sampling is running.
        """
        dw = self.dockwidget

        # Progress bar visibility
        progress = getattr(dw, '_progress_raster_sampling', None)
        if progress is not None:
            progress.setVisible(in_progress)
            if in_progress:
                progress.setValue(0)

        # Button states
        btn_sample = getattr(dw, '_btn_raster_sample', None)
        if btn_sample is not None:
            btn_sample.setEnabled(not in_progress)

        btn_apply = getattr(dw, '_btn_raster_apply_filter', None)
        if btn_apply is not None:
            btn_apply.setEnabled(False)  # Re-enabled on completion

    def _reset_sampling_state(self) -> None:
        """Reset sampling UI and state when layer changes."""
        self._last_sampling_result = None
        dw = self.dockwidget

        lbl = getattr(dw, '_lbl_raster_result', None)
        if lbl is not None:
            lbl.setText("")

        progress = getattr(dw, '_progress_raster_sampling', None)
        if progress is not None:
            progress.setVisible(False)

        btn_apply = getattr(dw, '_btn_raster_apply_filter', None)
        if btn_apply is not None:
            btn_apply.setEnabled(False)

    def _get_raster_layer_from_combo(self):
        """Get the raster layer from the combo, falling back to current layer."""
        dw = self.dockwidget
        combo = getattr(dw, '_combo_raster_layer', None)
        if combo is not None and hasattr(combo, 'currentLayer'):
            layer = combo.currentLayer()
            if layer is not None:
                return layer
        return self._current_raster_layer

    def _get_vector_layer_from_combo(self):
        """Get the vector layer from the sampling vector combo."""
        dw = self.dockwidget
        combo = getattr(dw, '_combo_sampling_vector', None)
        if combo is not None and hasattr(combo, 'currentLayer'):
            return combo.currentLayer()
        return None

    def _get_selected_band(self) -> int:
        """Get the selected band number (1-based)."""
        dw = self.dockwidget
        combo = getattr(dw, '_combo_raster_band', None)
        if combo is not None and combo.count() > 0:
            data = combo.currentData()
            if data is not None:
                return int(data)
        return 1

    def _get_selected_method(self) -> str:
        """Get the selected sampling method string."""
        dw = self.dockwidget
        combo = getattr(dw, '_combo_sampling_method', None)
        if combo is not None:
            data = combo.currentData()
            if data is not None:
                return str(data)
        return "point_on_surface"

    def _get_selected_operator(self):
        """Get the selected ComparisonOperator."""
        from ...core.domain.raster_filter_criteria import ComparisonOperator

        dw = self.dockwidget
        combo = getattr(dw, '_combo_raster_operator', None)
        if combo is not None:
            symbol = combo.currentData()
            if symbol is not None:
                for op in ComparisonOperator:
                    if op.value == symbol:
                        return op
        return ComparisonOperator.GREATER_EQUAL

    def _get_threshold(self) -> float:
        """Get the primary threshold value."""
        dw = self.dockwidget
        spin = getattr(dw, '_spin_raster_threshold', None)
        if spin is not None:
            return spin.value()
        return 0.0

    def _get_threshold_max(self) -> Optional[float]:
        """Get the max threshold value (for BETWEEN), or None."""
        dw = self.dockwidget
        combo = getattr(dw, '_combo_raster_operator', None)
        if combo is not None and combo.currentData() == "BETWEEN":
            spin = getattr(dw, '_spin_raster_threshold_max', None)
            if spin is not None:
                return spin.value()
        return None

    # ================================================================
    # Static Helpers
    # ================================================================

    @staticmethod
    def _detect_cog(provider) -> bool:
        """Detect if raster is a Cloud-Optimized GeoTIFF."""
        try:
            metadata = provider.htmlMetadata()
            if metadata:
                metadata_lower = metadata.lower()
                if "cog" in metadata_lower or "cloud-optimized" in metadata_lower:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _data_type_string(data_type: int) -> str:
        """Convert QGIS data type enum to string."""
        type_map = {
            0: "Unknown", 1: "Byte", 2: "UInt16", 3: "Int16",
            4: "UInt32", 5: "Int32", 6: "Float32", 7: "Float64",
            8: "CInt16", 9: "CInt32", 10: "CFloat32", 11: "CFloat64",
        }
        return type_map.get(data_type, f"Type({data_type})")

    @staticmethod
    def _map_unit_string(unit) -> str:
        """Convert QgsUnitTypes.DistanceUnit to human string."""
        # Common unit enum values
        unit_map = {
            0: "m",       # DistanceMeters
            1: "km",      # DistanceKilometers
            2: "ft",      # DistanceFeet
            3: "nm",      # DistanceNauticalMiles
            4: "yd",      # DistanceYards
            5: "mi",      # DistanceMiles
            6: "deg",     # DistanceDegrees
            7: "cm",      # DistanceCentimeters
            8: "mm",      # DistanceMillimeters
        }
        try:
            return unit_map.get(int(unit), "")
        except (TypeError, ValueError):
            return ""

    # ================================================================
    # Phase 2: Histogram
    # ================================================================

    def _setup_histogram_connections(self) -> None:
        """Connect histogram widgets to controller methods."""
        dw = self.dockwidget

        # "Compute" button
        try:
            btn = getattr(dw, '_btn_compute_histogram', None)
            if btn is not None:
                btn.clicked.connect(self._on_compute_histogram)
                logger.debug("RasterExploringController: connected _btn_compute_histogram")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: histogram compute btn not ready: {e}")

        # Histogram widget range changed signal
        try:
            hist_widget = getattr(dw, '_histogram_widget', None)
            if hist_widget is not None and hasattr(hist_widget, 'rangeChanged'):
                hist_widget.rangeChanged.connect(self._on_histogram_range_changed)
                logger.debug("RasterExploringController: connected histogram rangeChanged")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: histogram widget not ready: {e}")

        # Min/Max spinboxes for manual range entry
        try:
            spin_min = getattr(dw, '_spin_histogram_min', None)
            if spin_min is not None:
                spin_min.valueChanged.connect(self._on_histogram_spin_changed)
            spin_max = getattr(dw, '_spin_histogram_max', None)
            if spin_max is not None:
                spin_max.valueChanged.connect(self._on_histogram_spin_changed)
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: histogram spins not ready: {e}")

        # "Apply range as vector filter" button
        try:
            btn_filter = getattr(dw, '_btn_histogram_apply_filter', None)
            if btn_filter is not None:
                btn_filter.clicked.connect(self._on_apply_histogram_filter)
                logger.debug("RasterExploringController: connected _btn_histogram_apply_filter")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: histogram filter btn not ready: {e}")

    def _update_histogram_band_combo(self, layer) -> None:
        """Populate the histogram band combo from the raster layer.

        Args:
            layer: QgsRasterLayer or None.
        """
        dw = self.dockwidget
        combo = getattr(dw, '_combo_histogram_band', None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        if layer is not None and layer.isValid():
            band_count = layer.bandCount()
            for i in range(1, band_count + 1):
                try:
                    provider = layer.dataProvider()
                    band_name = provider.generateBandName(i) if provider else f"Band {i}"
                except Exception:
                    band_name = f"Band {i}"
                combo.addItem(band_name, i)

        combo.blockSignals(False)

    def _on_compute_histogram(self) -> None:
        """Handle "Compute" button click for histogram."""
        dw = self.dockwidget

        try:
            # Get raster layer
            raster_layer = self._get_raster_layer_from_combo()
            if raster_layer is None or not raster_layer.isValid():
                return

            # Get parameters
            combo_band = getattr(dw, '_combo_histogram_band', None)
            band = 1
            if combo_band is not None and combo_band.count() > 0:
                data = combo_band.currentData()
                if data is not None:
                    band = int(data)

            combo_bins = getattr(dw, '_combo_histogram_bins', None)
            n_bins = 256
            if combo_bins is not None and combo_bins.count() > 0:
                data = combo_bins.currentData()
                if data is not None:
                    n_bins = int(data)

            raster_uri = raster_layer.source()

            # Import infrastructure
            from ...infrastructure.raster.histogram import (
                compute_band_histogram,
                compute_band_statistics,
            )

            # Compute stats first
            stats = compute_band_statistics(raster_uri, band)
            self._last_histogram_stats = stats

            # Display stats
            if stats is not None:
                self._display_histogram_stats(stats)

            # Compute histogram
            result = compute_band_histogram(
                raster_uri, band, n_bins
            )
            if result is None:
                logger.warning("Histogram computation returned None")
                return

            counts, bin_edges = result

            # Feed data to histogram widget
            hist_widget = getattr(dw, '_histogram_widget', None)
            if hist_widget is not None and hasattr(hist_widget, 'set_data'):
                hist_widget.set_data(counts, bin_edges)

            # Update min/max spinboxes from stats
            if stats is not None:
                spin_min = getattr(dw, '_spin_histogram_min', None)
                spin_max = getattr(dw, '_spin_histogram_max', None)
                if spin_min is not None:
                    spin_min.blockSignals(True)
                    spin_min.setValue(stats["min"])
                    spin_min.blockSignals(False)
                if spin_max is not None:
                    spin_max.blockSignals(True)
                    spin_max.setValue(stats["max"])
                    spin_max.blockSignals(False)

            logger.info(
                f"Histogram computed: band={band}, bins={n_bins}, "
                f"layer={raster_layer.name()}"
            )

        except Exception as e:
            logger.error(f"Failed to compute histogram: {e}", exc_info=True)

    def _display_histogram_stats(self, stats: dict) -> None:
        """Display band statistics under the histogram.

        Args:
            stats: Dict from compute_band_statistics().
        """
        dw = self.dockwidget
        lbl = getattr(dw, '_lbl_histogram_stats', None)
        if lbl is None:
            return

        try:
            text = (
                f"Min: {stats['min']:.4f}  |  "
                f"Max: {stats['max']:.4f}  |  "
                f"Mean: {stats['mean']:.4f}  |  "
                f"Std: {stats['std_dev']:.4f}"
            )
            lbl.setText(text)
        except (KeyError, TypeError) as e:
            logger.debug(f"Could not format histogram stats: {e}")
            lbl.setText("")

    def _on_histogram_range_changed(self, range_min: float, range_max: float) -> None:
        """Handle range change from histogram widget (drag selection).

        Debounces with 300ms timer to avoid flooding the UI.

        Args:
            range_min: Minimum value of selection.
            range_max: Maximum value of selection.
        """
        dw = self.dockwidget

        # Update spinboxes to reflect the widget selection
        spin_min = getattr(dw, '_spin_histogram_min', None)
        spin_max = getattr(dw, '_spin_histogram_max', None)
        if spin_min is not None:
            spin_min.blockSignals(True)
            spin_min.setValue(range_min)
            spin_min.blockSignals(False)
        if spin_max is not None:
            spin_max.blockSignals(True)
            spin_max.setValue(range_max)
            spin_max.blockSignals(False)

        # Store pending range and start debounce
        self._pending_range = (range_min, range_max)
        self._histogram_range_debounce.start()

        # Enable apply button if valid range
        btn_filter = getattr(dw, '_btn_histogram_apply_filter', None)
        if btn_filter is not None:
            btn_filter.setEnabled(range_min < range_max)

    def _on_histogram_spin_changed(self) -> None:
        """Handle manual change in min/max spinboxes."""
        dw = self.dockwidget

        spin_min = getattr(dw, '_spin_histogram_min', None)
        spin_max = getattr(dw, '_spin_histogram_max', None)
        if spin_min is None or spin_max is None:
            return

        range_min = spin_min.value()
        range_max = spin_max.value()

        # Update histogram widget selection
        hist_widget = getattr(dw, '_histogram_widget', None)
        if hist_widget is not None and hasattr(hist_widget, 'set_range'):
            hist_widget.set_range(range_min, range_max)

        # Store pending range and debounce
        self._pending_range = (range_min, range_max)
        self._histogram_range_debounce.start()

        # Enable apply button
        btn_filter = getattr(dw, '_btn_histogram_apply_filter', None)
        if btn_filter is not None:
            btn_filter.setEnabled(range_min < range_max)

    def _on_histogram_range_debounced(self) -> None:
        """Called after debounce timer expires. Logs the final range."""
        if self._pending_range is not None:
            range_min, range_max = self._pending_range
            logger.debug(
                f"Histogram range debounced: [{range_min:.4f}, {range_max:.4f}]"
            )

    def _on_apply_histogram_filter(self) -> None:
        """Apply the histogram range selection as a vector filter.

        Uses sampling to find features whose raster value falls within
        the selected range, then selects them on the vector layer.
        """
        dw = self.dockwidget

        if self._pending_range is None:
            return

        range_min, range_max = self._pending_range
        if range_min >= range_max:
            return

        try:
            # Get layers
            raster_layer = self._get_raster_layer_from_combo()
            vector_layer = self._get_vector_layer_from_combo()
            if raster_layer is None or vector_layer is None:
                logger.warning("Cannot apply histogram filter: missing layer")
                return
            if not raster_layer.isValid() or not vector_layer.isValid():
                return

            # Get band
            combo_band = getattr(dw, '_combo_histogram_band', None)
            band = 1
            if combo_band is not None and combo_band.count() > 0:
                data = combo_band.currentData()
                if data is not None:
                    band = int(data)

            # Sample raster values at vector features
            from ...infrastructure.raster.sampling import sample_raster_for_features

            raster_uri = raster_layer.source()
            vector_uri = vector_layer.source()

            results = sample_raster_for_features(
                raster_uri=raster_uri,
                vector_uri=vector_uri,
                band=band,
                method="point_on_surface",
            )

            # Filter features within range
            matching_ids = []
            for fid, value in results.items():
                if value is not None and range_min <= value <= range_max:
                    matching_ids.append(fid)

            # Select matching features
            vector_layer.selectByIds(matching_ids)

            # Update result label
            lbl = getattr(dw, '_lbl_raster_result', None)
            if lbl is not None:
                lbl.setText(
                    dw.tr("{count}/{total} features in range [{min:.2f}, {max:.2f}]").format(
                        count=len(matching_ids),
                        total=vector_layer.featureCount(),
                        min=range_min,
                        max=range_max,
                    )
                )

            # Refresh canvas
            try:
                from qgis.utils import iface as qgis_iface
                if qgis_iface:
                    qgis_iface.mapCanvas().refresh()
            except Exception:
                pass

            logger.info(
                f"Histogram filter applied: {len(matching_ids)}/{vector_layer.featureCount()} "
                f"features in range [{range_min:.4f}, {range_max:.4f}]"
            )

        except Exception as e:
            logger.error(f"Failed to apply histogram filter: {e}", exc_info=True)

    def _clear_histogram(self) -> None:
        """Clear histogram widget and stats when layer changes."""
        dw = self.dockwidget

        hist_widget = getattr(dw, '_histogram_widget', None)
        if hist_widget is not None and hasattr(hist_widget, 'clear'):
            hist_widget.clear()

        lbl = getattr(dw, '_lbl_histogram_stats', None)
        if lbl is not None:
            lbl.setText("")

        btn_filter = getattr(dw, '_btn_histogram_apply_filter', None)
        if btn_filter is not None:
            btn_filter.setEnabled(False)

        self._last_histogram_stats = None
        self._pending_range = None

    # ================================================================
    # Phase 2: Band Viewer
    # ================================================================

    def _setup_band_viewer_connections(self) -> None:
        """Connect Band Viewer widgets to controller methods."""
        dw = self.dockwidget

        # Preset buttons
        for btn_attr in ('_btn_preset_natural', '_btn_preset_irc', '_btn_preset_ndvi'):
            try:
                btn = getattr(dw, btn_attr, None)
                if btn is not None:
                    # Use lambda with default arg to capture preset_name
                    preset_name = btn.property("preset_name")
                    if preset_name:
                        btn.clicked.connect(
                            lambda checked, pn=preset_name: self._on_band_composition_preset(pn)
                        )
                        logger.debug(
                            f"RasterExploringController: connected {btn_attr} "
                            f"-> preset {preset_name}"
                        )
            except (AttributeError, RuntimeError) as e:
                logger.debug(f"RasterExploringController: preset btn not ready: {e}")

        # Apply custom composition button
        try:
            btn = getattr(dw, '_btn_apply_band_composition', None)
            if btn is not None:
                btn.clicked.connect(self._on_apply_band_composition)
                logger.debug("RasterExploringController: connected _btn_apply_band_composition")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"RasterExploringController: apply composition btn not ready: {e}")

    def _populate_band_table(self) -> None:
        """Populate the band info QTableWidget from the current raster layer."""
        dw = self.dockwidget
        table = getattr(dw, '_table_band_info', None)
        if table is None:
            return

        layer = self._get_raster_layer_from_combo()
        if layer is None or not layer.isValid():
            table.setRowCount(0)
            return

        try:
            from ...infrastructure.raster.band_utils import get_band_info

            raster_uri = layer.source()
            bands = get_band_info(raster_uri)
            if bands is None:
                table.setRowCount(0)
                return

            from qgis.PyQt.QtWidgets import QTableWidgetItem

            table.setRowCount(len(bands))
            for row, band in enumerate(bands):
                table.setItem(row, 0, QTableWidgetItem(str(band["number"])))
                table.setItem(row, 1, QTableWidgetItem(band["name"]))
                table.setItem(row, 2, QTableWidgetItem(band["data_type"]))

                min_str = f"{band['min']:.4f}" if band["min"] is not None else "-"
                table.setItem(row, 3, QTableWidgetItem(min_str))

                max_str = f"{band['max']:.4f}" if band["max"] is not None else "-"
                table.setItem(row, 4, QTableWidgetItem(max_str))

            table.resizeColumnsToContents()
            logger.debug(f"Band table populated: {len(bands)} bands")

        except Exception as e:
            logger.warning(f"Failed to populate band table: {e}")
            table.setRowCount(0)

    def _update_band_rgb_combos(self, layer) -> None:
        """Populate R/G/B band combos from the raster layer.

        Args:
            layer: QgsRasterLayer or None.
        """
        dw = self.dockwidget

        for attr in ('_combo_band_red', '_combo_band_green', '_combo_band_blue'):
            combo = getattr(dw, attr, None)
            if combo is None:
                continue

            combo.blockSignals(True)
            combo.clear()

            if layer is not None and layer.isValid():
                band_count = layer.bandCount()
                for i in range(1, band_count + 1):
                    try:
                        provider = layer.dataProvider()
                        name = provider.generateBandName(i) if provider else f"Band {i}"
                    except Exception:
                        name = f"Band {i}"
                    combo.addItem(name, i)

            combo.blockSignals(False)

        # Set sensible defaults: R=1, G=2, B=3 (if enough bands)
        if layer is not None and layer.isValid():
            band_count = layer.bandCount()
            combos = [
                getattr(dw, '_combo_band_red', None),
                getattr(dw, '_combo_band_green', None),
                getattr(dw, '_combo_band_blue', None),
            ]
            for idx, combo in enumerate(combos):
                if combo is not None and idx < band_count:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)

    def _on_band_composition_preset(self, preset_name: str) -> None:
        """Apply a preset band composition to the current raster layer.

        Args:
            preset_name: Key from PRESET_COMPOSITIONS dict.
        """
        layer = self._get_raster_layer_from_combo()
        if layer is None or not layer.isValid():
            logger.warning("No valid raster layer for preset composition")
            return

        try:
            from ...infrastructure.raster.band_utils import (
                apply_preset_composition,
                PRESET_COMPOSITIONS,
            )

            preset = PRESET_COMPOSITIONS.get(preset_name)
            if preset is None:
                logger.warning(f"Unknown preset: {preset_name}")
                return

            # Check band count compatibility
            max_band = max(preset["red"], preset["green"], preset["blue"])
            if layer.bandCount() < max_band:
                dw = self.dockwidget
                lbl = getattr(dw, '_lbl_raster_result', None)
                if lbl is not None:
                    lbl.setText(
                        dw.tr(
                            "Preset '{name}' requires {n} bands, "
                            "layer has {count}"
                        ).format(
                            name=preset.get("label", preset_name),
                            n=max_band,
                            count=layer.bandCount(),
                        )
                    )
                logger.warning(
                    f"Preset {preset_name} requires band {max_band}, "
                    f"but layer has only {layer.bandCount()} bands"
                )
                return

            success = apply_preset_composition(layer, preset_name)
            if success:
                # Update RGB combos to match preset
                dw = self.dockwidget
                for attr, key in [
                    ('_combo_band_red', 'red'),
                    ('_combo_band_green', 'green'),
                    ('_combo_band_blue', 'blue'),
                ]:
                    combo = getattr(dw, attr, None)
                    if combo is not None:
                        band_idx = preset[key] - 1  # 0-based index for combo
                        if 0 <= band_idx < combo.count():
                            combo.blockSignals(True)
                            combo.setCurrentIndex(band_idx)
                            combo.blockSignals(False)

                logger.info(f"Applied preset: {preset_name}")

                # Refresh canvas
                try:
                    from qgis.utils import iface as qgis_iface
                    if qgis_iface:
                        qgis_iface.mapCanvas().refresh()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to apply preset {preset_name}: {e}", exc_info=True)

    def _on_apply_band_composition(self) -> None:
        """Apply custom R/G/B band composition from combo selections."""
        dw = self.dockwidget

        layer = self._get_raster_layer_from_combo()
        if layer is None or not layer.isValid():
            logger.warning("No valid raster layer for custom composition")
            return

        try:
            from ...infrastructure.raster.band_utils import apply_band_composition

            # Read band numbers from combos
            red = self._get_combo_band_data(dw, '_combo_band_red', 1)
            green = self._get_combo_band_data(dw, '_combo_band_green', 2)
            blue = self._get_combo_band_data(dw, '_combo_band_blue', 3)

            success = apply_band_composition(layer, red, green, blue)
            if success:
                logger.info(
                    f"Applied custom composition: R={red}, G={green}, B={blue}"
                )
                # Refresh canvas
                try:
                    from qgis.utils import iface as qgis_iface
                    if qgis_iface:
                        qgis_iface.mapCanvas().refresh()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to apply custom composition: {e}", exc_info=True)

    @staticmethod
    def _get_combo_band_data(dw, attr: str, default: int) -> int:
        """Get band number from a combo widget.

        Args:
            dw: Dockwidget instance.
            attr: Attribute name of the combo on dw.
            default: Default band number if combo is empty.

        Returns:
            1-based band number.
        """
        combo = getattr(dw, attr, None)
        if combo is not None and combo.count() > 0:
            data = combo.currentData()
            if data is not None:
                return int(data)
        return default
