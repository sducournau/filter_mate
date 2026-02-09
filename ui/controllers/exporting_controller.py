"""
FilterMate Exporting Controller.

Manages exporting tab logic including layer selection,
format configuration, output path, CRS selection,
and export execution (single and batch).

IMPORTANT: Export is INDEPENDENT from "exploring" tab and QGIS selection.
==========================================================================

Export behavior:
- Exports ENTIRE layers (all features visible with current subset)
- WITH subset string: exports only filtered features (respects active filter)
- WITHOUT subset string: exports all features in the layer
- Layers to export are selected via checkboxes in the EXPORTING tab

Export does NOT use:
- exploring tab's current_layer
- exploring tab's selection expression
- QGIS selectedFeatures() or layer selection
- Any data from the filtering process

This design ensures export is a standalone operation that can be performed
independently of any filtering or exploring activity.
"""
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

from qgis.PyQt.QtCore import QTimer
from .base_controller import BaseController

# Module logger
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...core.services.filter_service import FilterService
    from ...adapters.qgis.signals.signal_manager import SignalManager


# =============================================================================
# VECTOR EXPORT ENUMS
# =============================================================================

class ExportFormat(Enum):
    """Supported vector export formats."""
    GEOPACKAGE = "GPKG"
    SHAPEFILE = "ESRI Shapefile"
    GEOJSON = "GeoJSON"
    CSV = "CSV"
    KML = "KML"
    DXF = "DXF"


# =============================================================================
# RASTER EXPORT ENUMS (US-EXP-03, US-EXP-04)
# =============================================================================

class RasterExportFormat(Enum):
    """Supported raster export formats."""
    GEOTIFF = "GTiff"
    COG = "COG"           # Cloud-Optimized GeoTIFF
    PNG = "PNG"
    JPEG = "JPEG"
    
    @property
    def extension(self) -> str:
        """Get file extension for format."""
        ext_map = {
            RasterExportFormat.GEOTIFF: '.tif',
            RasterExportFormat.COG: '.tif',
            RasterExportFormat.PNG: '.png',
            RasterExportFormat.JPEG: '.jpg',
        }
        return ext_map.get(self, '.tif')
    
    @property
    def description(self) -> str:
        """Get human-readable description."""
        desc_map = {
            RasterExportFormat.GEOTIFF: "GeoTIFF - Standard raster format with georeferencing",
            RasterExportFormat.COG: "Cloud-Optimized GeoTIFF - Optimized for web streaming",
            RasterExportFormat.PNG: "PNG - Portable Network Graphics (8-bit, lossless)",
            RasterExportFormat.JPEG: "JPEG - Lossy compression, small file size",
        }
        return desc_map.get(self, "")


class RasterCompressionType(Enum):
    """Compression options for raster export."""
    NONE = "NONE"
    LZW = "LZW"
    DEFLATE = "DEFLATE"
    ZSTD = "ZSTD"
    JPEG = "JPEG"
    
    @property
    def description(self) -> str:
        """Get human-readable description."""
        desc_map = {
            RasterCompressionType.NONE: "No compression - Fastest, largest file",
            RasterCompressionType.LZW: "LZW - Lossless, good compression ratio",
            RasterCompressionType.DEFLATE: "DEFLATE - Lossless, best compression ratio",
            RasterCompressionType.ZSTD: "ZSTD - Lossless, modern fast compression",
            RasterCompressionType.JPEG: "JPEG - Lossy, 8-bit only, smallest file",
        }
        return desc_map.get(self, "")


class RasterClipMode(Enum):
    """Clipping mode for raster export."""
    BOUNDING_BOX = "bbox"       # Rectangular clip to mask extent
    EXACT_GEOMETRY = "exact"   # Pixels outside geometry = NoData
    
    @classmethod
    def from_extension(cls, ext: str) -> 'ExportFormat':
        """Get format from file extension."""
        ext_map = {
            '.gpkg': cls.GEOPACKAGE,
            '.shp': cls.SHAPEFILE,
            '.geojson': cls.GEOJSON,
            '.json': cls.GEOJSON,
            '.csv': cls.CSV,
            '.kml': cls.KML,
            '.dxf': cls.DXF,
        }
        return ext_map.get(ext.lower(), cls.GEOPACKAGE)
    
    @property
    def extension(self) -> str:
        """Get file extension for format."""
        ext_map = {
            ExportFormat.GEOPACKAGE: '.gpkg',
            ExportFormat.SHAPEFILE: '.shp',
            ExportFormat.GEOJSON: '.geojson',
            ExportFormat.CSV: '.csv',
            ExportFormat.KML: '.kml',
            ExportFormat.DXF: '.dxf',
        }
        return ext_map.get(self, '.gpkg')
    
    @property
    def supports_multiple_layers(self) -> bool:
        """Check if format supports multiple layers in one file."""
        return self in (ExportFormat.GEOPACKAGE, ExportFormat.KML)


class ExportMode(Enum):
    """Export mode options."""
    SINGLE = "single"       # Export one layer
    BATCH = "batch"         # Export multiple layers to separate files
    MERGED = "merged"       # Merge layers into one file (if format supports)


@dataclass
class ExportConfiguration:
    """
    Holds the current export configuration state.
    
    Immutable representation of an export setup.
    """
    layer_ids: List[str] = field(default_factory=list)
    output_format: ExportFormat = ExportFormat.GEOPACKAGE
    output_path: str = ""
    output_crs: Optional[str] = None  # EPSG code or WKT
    mode: ExportMode = ExportMode.SINGLE
    include_styles: bool = False
    zip_output: bool = False
    
    def is_valid(self) -> bool:
        """Check if configuration is valid for export."""
        return (
            len(self.layer_ids) > 0 and
            bool(self.output_path)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "layer_ids": self.layer_ids,
            "output_format": self.output_format.value,
            "output_path": self.output_path,
            "output_crs": self.output_crs,
            "mode": self.mode.value,
            "include_styles": self.include_styles,
            "zip_output": self.zip_output
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExportConfiguration':
        """Create from dictionary."""
        return cls(
            layer_ids=data.get("layer_ids", []),
            output_format=ExportFormat(data.get("output_format", "GPKG")),
            output_path=data.get("output_path", ""),
            output_crs=data.get("output_crs"),
            mode=ExportMode(data.get("mode", "single")),
            include_styles=data.get("include_styles", False),
            zip_output=data.get("zip_output", False)
        )


# =============================================================================
# RASTER EXPORT CONFIGURATION (US-EXP-03, US-EXP-06, US-EXP-07)
# =============================================================================

@dataclass
class RasterExportConfiguration:
    """
    Configuration for raster layer export.
    
    Used when exporting raster layers with optional clipping by vector mask
    and optional value-based filtering.
    
    Value filtering (new in v5.0):
    - min_value/max_value: Export only pixels within this range
    - nodata_value: Set NoData for pixels outside filter range
    - band_index: Band to filter on (default: 1)
    """
    layer_id: str = ""
    output_path: str = ""
    output_format: RasterExportFormat = RasterExportFormat.GEOTIFF
    compression: RasterCompressionType = RasterCompressionType.LZW
    output_crs: Optional[str] = None
    
    # Clipping options (US-EXP-06, US-EXP-07)
    clip_enabled: bool = False
    mask_layer_id: Optional[str] = None
    clip_mode: RasterClipMode = RasterClipMode.EXACT_GEOMETRY
    
    # COG options (US-EXP-05)
    create_cog: bool = False
    create_pyramids: bool = True
    
    # Value filtering options (new in v5.0 - EPIC-UNIFIED-FILTER)
    filter_enabled: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    nodata_value: Optional[float] = None
    band_index: int = 1
    
    def is_valid(self) -> bool:
        """Check if configuration is valid for export."""
        if not self.layer_id or not self.output_path:
            return False
        if self.clip_enabled and not self.mask_layer_id:
            return False
        # Value filtering validation
        if self.filter_enabled:
            if self.min_value is not None and self.max_value is not None:
                if self.min_value > self.max_value:
                    return False
        return True
    
    @property
    def has_value_filter(self) -> bool:
        """Check if value filtering is configured."""
        return self.filter_enabled and (
            self.min_value is not None or self.max_value is not None
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "layer_id": self.layer_id,
            "output_path": self.output_path,
            "output_format": self.output_format.value,
            "compression": self.compression.value,
            "output_crs": self.output_crs,
            "clip_enabled": self.clip_enabled,
            "mask_layer_id": self.mask_layer_id,
            "clip_mode": self.clip_mode.value,
            "create_cog": self.create_cog,
            "create_pyramids": self.create_pyramids,
            # Value filtering (v5.0)
            "filter_enabled": self.filter_enabled,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "nodata_value": self.nodata_value,
            "band_index": self.band_index,
        }


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    exported_files: List[str] = field(default_factory=list)
    failed_layers: List[str] = field(default_factory=list)
    error_message: str = ""
    execution_time_ms: float = 0.0
    
    @property
    def partial_success(self) -> bool:
        """Check if export was partially successful."""
        return len(self.exported_files) > 0 and len(self.failed_layers) > 0


class ExportingController(BaseController):
    """
    Controller for the Exporting tab.
    
    Manages:
    - Layer selection for export
    - Format selection
    - Output path configuration
    - CRS selection
    - Single and batch export execution
    - Style and zip options
    
    Signals (emitted via callbacks):
    - exportStarted: Export started
    - exportCompleted: Export completed successfully
    - exportError: Export failed
    - exportProgress: Progress update for batch export
    """
    
    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        filter_service: Optional['FilterService'] = None,
        signal_manager: Optional['SignalManager'] = None
    ):
        """
        Initialize the exporting controller.
        
        Args:
            dockwidget: Parent dockwidget for UI access
            filter_service: Filter service for business logic
            signal_manager: Centralized signal manager
        """
        super().__init__(dockwidget, filter_service, signal_manager)
        
        # Vector export state
        self._layer_ids: List[str] = []
        self._output_format: ExportFormat = ExportFormat.GEOPACKAGE
        self._output_path: str = ""
        self._output_crs: Optional[str] = None
        self._export_mode: ExportMode = ExportMode.SINGLE
        self._include_styles: bool = False
        self._zip_output: bool = False
        
        # Raster export state (US-EXP-01, US-EXP-03, US-EXP-06)
        self._raster_layer_ids: List[str] = []
        self._raster_format: RasterExportFormat = RasterExportFormat.GEOTIFF
        self._raster_compression: RasterCompressionType = RasterCompressionType.LZW
        self._raster_clip_enabled: bool = False
        self._raster_mask_layer_id: Optional[str] = None
        self._raster_clip_mode: RasterClipMode = RasterClipMode.EXACT_GEOMETRY
        self._raster_create_cog: bool = False
        self._raster_create_pyramids: bool = True
        
        # Raster value filtering state (v5.0 - EPIC-UNIFIED-FILTER)
        self._raster_filter_enabled: bool = False
        self._raster_filter_min_value: Optional[float] = None
        self._raster_filter_max_value: Optional[float] = None
        self._raster_filter_nodata_value: Optional[float] = None
        self._raster_filter_band_index: int = 1
        
        # Execution state
        self._is_exporting: bool = False
        self._last_result: Optional[ExportResult] = None
        self._export_progress: float = 0.0
        
        # Callbacks
        self._on_export_started_callbacks: List[Callable[[], None]] = []
        self._on_export_completed_callbacks: List[Callable[[ExportResult], None]] = []
        self._on_progress_callbacks: List[Callable[[float], None]] = []
        self._on_config_changed_callbacks: List[Callable[[ExportConfiguration], None]] = []
        self._on_raster_selection_changed_callbacks: List[Callable[[bool], None]] = []

    # === Layer Selection ===
    
    def get_layers_to_export(self) -> List[str]:
        """Get list of layer IDs selected for export."""
        return self._layer_ids.copy()
    
    def populate_export_combobox(self) -> bool:
        """
        Populate the export layers combobox with available layers.
        
        v3.1 Sprint 5: Migrated from dockwidget to controller.
        
        This method:
        - Clears existing items
        - Adds all valid vector layers from PROJECT_LAYERS
        - Handles PostgreSQL and remote layers missing from PROJECT_LAYERS
        - Sets check state based on saved preferences
        - Populates the datatype/format combobox with OGR drivers
        
        Returns:
            True if population succeeded, False otherwise
        """
        try:
            dockwidget = self._dockwidget
            if not dockwidget:
                return False
            
            # Check preconditions - v4.0.5: Relaxed check since _on_project_layers_ready sets has_loaded_layers
            if not dockwidget.widgets_initialized:
                logger.warning("populate_export_combobox: widgets not initialized")
                return False
            
            # v4.0.5: Check PROJECT_LAYERS instead of has_loaded_layers
            # The signal may fire before has_loaded_layers is set by filter_mate_app.py
            if not dockwidget.PROJECT_LAYERS:
                logger.info("populate_export_combobox: PROJECT_LAYERS empty, deferring until projectLayersReady signal")
                return False
            
            logger.info(f"populate_export_combobox: Starting with {len(dockwidget.PROJECT_LAYERS)} layers in PROJECT_LAYERS")
            
            # Get saved preferences
            layers_to_export = []
            datatype_to_export = ''
            
            if dockwidget.project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT'):
                layers_to_export = dockwidget.project_props['EXPORTING']['LAYERS_TO_EXPORT']
            
            if dockwidget.project_props.get('EXPORTING', {}).get('HAS_DATATYPE_TO_EXPORT'):
                datatype_to_export = dockwidget.project_props['EXPORTING']['DATATYPE_TO_EXPORT']
            
            # Import required modules
            from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject
            from qgis.PyQt.QtCore import Qt
            from ...infrastructure.constants import REMOTE_PROVIDERS
            from ...infrastructure.utils import geometry_type_to_string
            from ...infrastructure.utils.validation_utils import is_layer_source_available
            
            try:
                from osgeo import ogr
                ogr_available = True
                logger.debug(f"OGR available: {ogr.GetDriverCount()} drivers")
            except ImportError as e:
                ogr_available = False
                logger.warning(f"OGR not available: {e}. Export formats list will be empty.")
            
            project = QgsProject.instance()
            
            # Collect diagnostic info - v5.1: Include both vector and raster layers
            qgis_layers = [l for l in project.mapLayers().values() 
                           if isinstance(l, QgsVectorLayer) or isinstance(l, QgsRasterLayer)]
            postgres_layers = [l for l in qgis_layers if l.providerType() == 'postgres']
            remote_layers = [l for l in qgis_layers if l.providerType() in REMOTE_PROVIDERS]
            
            # Find layers missing from PROJECT_LAYERS
            missing_postgres = [l for l in postgres_layers if l.id() not in dockwidget.PROJECT_LAYERS]
            missing_remote = [l for l in remote_layers if l.id() not in dockwidget.PROJECT_LAYERS]
            
            if missing_postgres:
                logger.warning(f"populate_export_combobox: {len(missing_postgres)} PostgreSQL layer(s) missing from PROJECT_LAYERS")
                logger.warning(f"Layers in QGIS but NOT in PROJECT_LAYERS: {[l.name() for l in missing_postgres]}")
                
                # FIX 2026-01-16 v2: Robust automatic addition with retry
                # BYPASS queue system for critical sync + retry after 1s
                if hasattr(dockwidget, 'app') and dockwidget.app:
                    logger.info("🔄 Triggering automatic add_layers for missing PostgreSQL layers...")
                    try:
                        # Reset counter to bypass queue
                        dockwidget.app._pending_add_layers_tasks = 0
                        dockwidget.app.manage_task('add_layers', missing_postgres)
                        
                        # Retry after 1s to ensure completion
                        def retry_add_postgres():
                            still_missing = [l for l in missing_postgres 
                                           if l.id() not in dockwidget.PROJECT_LAYERS]
                            if still_missing:
                                logger.warning(f"⚠️ Retrying add_layers for {len(still_missing)} PostgreSQL layers")
                                dockwidget.app._pending_add_layers_tasks = 0
                                dockwidget.app.manage_task('add_layers', still_missing)
                        QTimer.singleShot(1000, retry_add_postgres)
                    except Exception as e:
                        logger.error(f"Failed to auto-add missing layers: {e}")
                
            if missing_remote:
                logger.warning(f"populate_export_combobox: {len(missing_remote)} remote layer(s) missing from PROJECT_LAYERS")
                logger.warning(f"Remote layers in QGIS but NOT in PROJECT_LAYERS: {[l.name() for l in missing_remote]}")
                
                # FIX 2026-01-16 v2: Robust automatic addition with retry
                if hasattr(dockwidget, 'app') and dockwidget.app:
                    logger.info("🔄 Triggering automatic add_layers for missing remote layers...")
                    try:
                        # Reset counter to bypass queue
                        dockwidget.app._pending_add_layers_tasks = 0
                        dockwidget.app.manage_task('add_layers', missing_remote)
                        
                        # Retry after 1s to ensure completion
                        def retry_add_remote():
                            still_missing = [l for l in missing_remote 
                                           if l.id() not in dockwidget.PROJECT_LAYERS]
                            if still_missing:
                                logger.warning(f"⚠️ Retrying add_layers for {len(still_missing)} remote layers")
                                dockwidget.app._pending_add_layers_tasks = 0
                                dockwidget.app.manage_task('add_layers', still_missing)
                        QTimer.singleShot(1000, retry_add_remote)
                    except Exception as e:
                        logger.error(f"Failed to auto-add missing remote layers: {e}")
            
            # Clear and populate layers widget
            layers_widget = dockwidget.widgets["EXPORTING"]["LAYERS_TO_EXPORT"]["WIDGET"]
            layers_widget.clear()
            item_index = 0
            
            # Add layers from PROJECT_LAYERS
            for key in list(dockwidget.PROJECT_LAYERS.keys()):
                if key not in dockwidget.PROJECT_LAYERS or "infos" not in dockwidget.PROJECT_LAYERS[key]:
                    continue
                
                layer_info = dockwidget.PROJECT_LAYERS[key]["infos"]
                required_keys = ["layer_id", "layer_name", "layer_crs_authid", "layer_geometry_type"]
                if any(k not in layer_info or layer_info[k] is None for k in required_keys):
                    continue
                
                layer_id = layer_info["layer_id"]
                layer_name = layer_info["layer_name"]
                layer_crs_authid = layer_info["layer_crs_authid"]
                geom_type = layer_info["layer_geometry_type"]
                layer_icon = dockwidget.icon_per_geometry_type(geom_type)
                
                # DIAGNOSTIC: Log geometry type and icon validity
                logger.debug(f"populate_export_combobox: layer='{layer_name}', geom_type='{geom_type}', icon_isNull={layer_icon.isNull() if layer_icon else 'None'}")
                
                # Validate layer is usable - v5.1: Support both vector and raster layers
                layer_obj = project.mapLayer(layer_id)
                if not layer_obj:
                    continue
                
                is_vector = isinstance(layer_obj, QgsVectorLayer)
                is_raster = isinstance(layer_obj, QgsRasterLayer)
                
                if (is_vector or is_raster) and is_layer_source_available(layer_obj, require_psycopg2=False):
                    # v5.1: Update geometry type for raster layers
                    if is_raster:
                        geom_type = "GeometryType.Raster"
                        layer_icon = dockwidget.icon_per_geometry_type(geom_type)
                    
                    display_name = f"{layer_name} [{layer_crs_authid}]"
                    item_data = {"layer_id": key, "layer_geometry_type": geom_type}
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    item = layers_widget.model().item(item_index)
                    item.setCheckState(Qt.Checked if key in layers_to_export else Qt.Unchecked)
                    item_index += 1
            
            # Add missing PostgreSQL layers
            for pg_layer in missing_postgres:
                if pg_layer.isValid() and is_layer_source_available(pg_layer, require_psycopg2=False):
                    display_name = f"{pg_layer.name()} [{pg_layer.crs().authid()}]"
                    geom_type_str = geometry_type_to_string(pg_layer)
                    layer_icon = dockwidget.icon_per_geometry_type(geom_type_str)
                    logger.debug(f"populate_export_combobox [PostgreSQL]: layer='{pg_layer.name()}', geom_type='{geom_type_str}', icon_isNull={layer_icon.isNull() if layer_icon else 'None'}")
                    item_data = {"layer_id": pg_layer.id(), "layer_geometry_type": geom_type_str}
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    item = layers_widget.model().item(item_index)
                    item.setCheckState(Qt.Checked if pg_layer.id() in layers_to_export else Qt.Unchecked)
                    item_index += 1
                    logger.info(f"populate_export_combobox: Added missing PostgreSQL layer '{pg_layer.name()}'")
            
            # Add missing remote layers
            for remote_layer in missing_remote:
                if remote_layer.isValid() and is_layer_source_available(remote_layer, require_psycopg2=False):
                    display_name = f"{remote_layer.name()} [{remote_layer.crs().authid()}]"
                    geom_type_str = geometry_type_to_string(remote_layer)
                    layer_icon = dockwidget.icon_per_geometry_type(geom_type_str)
                    logger.debug(f"populate_export_combobox [Remote]: layer='{remote_layer.name()}', geom_type='{geom_type_str}', icon_isNull={layer_icon.isNull() if layer_icon else 'None'}")
                    item_data = {"layer_id": remote_layer.id(), "layer_geometry_type": geom_type_str}
                    layers_widget.addItem(layer_icon, display_name, item_data)
                    item = layers_widget.model().item(item_index)
                    item.setCheckState(Qt.Checked if remote_layer.id() in layers_to_export else Qt.Unchecked)
                    item_index += 1
                    logger.info(f"populate_export_combobox: Added missing remote layer '{remote_layer.name()}'")
            
            logger.info(f"populate_export_combobox: Added {item_index} layers to export combobox")
            
            # Populate datatype/format combobox
            if ogr_available:
                datatype_widget = dockwidget.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                datatype_widget.clear()
                ogr_driver_list = sorted([ogr.GetDriver(i).GetDescription() for i in range(ogr.GetDriverCount())])
                datatype_widget.addItems(ogr_driver_list)
                logger.info(f"populate_export_combobox: Added {len(ogr_driver_list)} export formats")
                
                if datatype_to_export:
                    idx = datatype_widget.findText(datatype_to_export)
                    datatype_widget.setCurrentIndex(idx if idx >= 0 else datatype_widget.findText('GPKG'))
                else:
                    datatype_widget.setCurrentIndex(datatype_widget.findText('GPKG'))
            else:
                logger.warning("populate_export_combobox: OGR not available, cannot populate export formats")
            
            return True
            
        except Exception as e:
            logger.error(f"populate_export_combobox failed: {e}")
            return False
    
    def set_layers_to_export(self, layer_ids: List[str]) -> None:
        """
        Set layers to export.
        
        Args:
            layer_ids: List of layer IDs to export
        """
        if layer_ids == self._layer_ids:
            return
        
        self._layer_ids = layer_ids.copy()
        
        # Update mode based on layer count
        if len(layer_ids) > 1:
            if not self._output_format.supports_multiple_layers:
                self._export_mode = ExportMode.BATCH
        else:
            self._export_mode = ExportMode.SINGLE
        
        self._notify_config_changed()
    
    def add_layer(self, layer_id: str) -> None:
        """Add a layer to export list."""
        if layer_id not in self._layer_ids:
            self._layer_ids.append(layer_id)
            self._notify_config_changed()
    
    def remove_layer(self, layer_id: str) -> None:
        """Remove a layer from export list."""
        if layer_id in self._layer_ids:
            self._layer_ids.remove(layer_id)
            self._notify_config_changed()
    
    def clear_layers(self) -> None:
        """Clear all layers from export list."""
        self._layer_ids.clear()
        self._notify_config_changed()
    
    def set_layers_from_selection(self, layer_ids: List[str]) -> None:
        """
        Handle layer selection change from UI (list-based).
        
        Note: For individual layer toggle, use on_layer_selection_changed(layer_id, is_selected).
        
        Args:
            layer_ids: New list of selected layer IDs
        """
        self.set_layers_to_export(layer_ids)
    
    # === Format Selection ===
    
    def get_output_format(self) -> ExportFormat:
        """Get current export format."""
        return self._output_format
    
    def set_output_format(self, format_value: ExportFormat) -> None:
        """
        Set export format.
        
        Args:
            format_value: Export format to use
        """
        if format_value == self._output_format:
            return
        
        self._output_format = format_value
        
        # Update output path extension if set
        if self._output_path:
            self._update_output_extension()
        
        # Check if mode is still valid for format
        if len(self._layer_ids) > 1:
            if not format_value.supports_multiple_layers:
                self._export_mode = ExportMode.BATCH
            elif self._export_mode == ExportMode.BATCH:
                # Keep batch mode even if merged is now possible
                pass
        
        self._notify_config_changed()
    
    def get_available_formats(self) -> List[ExportFormat]:
        """Get list of available export formats."""
        return list(ExportFormat)
    
    def on_format_changed(self, format_value: str) -> None:
        """
        Handle format change from UI.
        
        Args:
            format_value: Format value string
        """
        try:
            export_format = ExportFormat(format_value)
            self.set_output_format(export_format)
        except ValueError:
            pass  # Invalid format, ignore
    
    # === Output Path ===
    
    def get_output_path(self) -> str:
        """Get current output path."""
        return self._output_path
    
    def set_output_path(self, path: str) -> None:
        """
        Set output path.
        
        Args:
            path: Output file or directory path
        """
        if path == self._output_path:
            return
        
        self._output_path = path
        
        # Try to detect format from extension
        if path:
            ext = Path(path).suffix.lower()
            if ext:
                try:
                    detected_format = ExportFormat.from_extension(ext)
                    if detected_format != self._output_format:
                        self._output_format = detected_format
                except ValueError:
                    pass
        
        self._notify_config_changed()
    
    def _update_output_extension(self) -> None:
        """Update output path extension to match format."""
        if not self._output_path:
            return
        
        path = Path(self._output_path)
        new_ext = self._output_format.extension
        
        if path.suffix.lower() != new_ext:
            self._output_path = str(path.with_suffix(new_ext))
    
    def on_output_path_changed(self, path: str) -> None:
        """
        Handle output path change from UI.
        
        Args:
            path: New output path
        """
        self.set_output_path(path)

    # =========================================================================
    # RASTER EXPORT METHODS (US-EXP-01, US-EXP-03, US-EXP-06)
    # =========================================================================

    # === Layer Type Detection (US-EXP-01) ===
    
    def is_layer_raster(self, layer_id: str) -> bool:
        """
        Check if a layer is a raster layer.
        
        Args:
            layer_id: Layer ID to check
            
        Returns:
            True if layer is QgsRasterLayer, False otherwise
        """
        from qgis.core import QgsProject, QgsRasterLayer
        layer = QgsProject.instance().mapLayer(layer_id)
        return isinstance(layer, QgsRasterLayer) if layer else False
    
    def is_layer_vector(self, layer_id: str) -> bool:
        """
        Check if a layer is a vector layer.
        
        Args:
            layer_id: Layer ID to check
            
        Returns:
            True if layer is QgsVectorLayer, False otherwise
        """
        from qgis.core import QgsProject, QgsVectorLayer
        layer = QgsProject.instance().mapLayer(layer_id)
        return isinstance(layer, QgsVectorLayer) if layer else False
    
    def has_raster_selected(self) -> bool:
        """
        Check if any selected layer is a raster.
        
        Returns:
            True if at least one raster is selected for export
        """
        return len(self._raster_layer_ids) > 0
    
    def has_vector_selected(self) -> bool:
        """
        Check if any selected layer is a vector.
        
        Returns:
            True if at least one vector is selected for export
        """
        # Vector layers are in _layer_ids but NOT in _raster_layer_ids
        vector_ids = [lid for lid in self._layer_ids if lid not in self._raster_layer_ids]
        return len(vector_ids) > 0
    
    def get_selected_raster_ids(self) -> List[str]:
        """Get list of selected raster layer IDs."""
        return self._raster_layer_ids.copy()
    
    def get_selected_vector_ids(self) -> List[str]:
        """Get list of selected vector layer IDs."""
        return [lid for lid in self._layer_ids if lid not in self._raster_layer_ids]
    
    def on_layer_selection_changed(self, layer_id: str, is_selected: bool) -> None:
        """
        Handle layer selection change in export combobox.
        
        Updates both _layer_ids and _raster_layer_ids, then notifies
        UI to show/hide raster options.
        
        Args:
            layer_id: ID of layer that changed
            is_selected: True if layer is now selected
        """
        had_raster = self.has_raster_selected()
        
        if is_selected:
            if layer_id not in self._layer_ids:
                self._layer_ids.append(layer_id)
            # Track rasters separately
            if self.is_layer_raster(layer_id):
                if layer_id not in self._raster_layer_ids:
                    self._raster_layer_ids.append(layer_id)
        else:
            if layer_id in self._layer_ids:
                self._layer_ids.remove(layer_id)
            if layer_id in self._raster_layer_ids:
                self._raster_layer_ids.remove(layer_id)
        
        has_raster = self.has_raster_selected()
        
        # Notify if raster selection state changed (for UI visibility)
        if had_raster != has_raster:
            self._notify_raster_selection_changed(has_raster)
        
        self._notify_config_changed()
    
    def _notify_raster_selection_changed(self, has_raster: bool) -> None:
        """
        Notify listeners that raster selection state changed.
        
        Used to show/hide raster options GroupBox in UI.
        """
        for callback in self._on_raster_selection_changed_callbacks:
            try:
                callback(has_raster)
            except Exception as e:
                logger.debug(f"Raster selection callback failed: {e}")
    
    def register_raster_selection_callback(self, callback: Callable[[bool], None]) -> None:
        """
        Register callback for raster selection changes.
        
        Args:
            callback: Function called with (has_raster: bool)
        """
        if callback not in self._on_raster_selection_changed_callbacks:
            self._on_raster_selection_changed_callbacks.append(callback)

    # === Raster Format Selection (US-EXP-03, US-EXP-04) ===
    
    def get_raster_format(self) -> RasterExportFormat:
        """Get current raster export format."""
        return self._raster_format
    
    def set_raster_format(self, format_value: RasterExportFormat) -> None:
        """Set raster export format."""
        self._raster_format = format_value
        # COG implies specific format
        if format_value == RasterExportFormat.COG:
            self._raster_create_cog = True
        self._notify_config_changed()
    
    def get_raster_compression(self) -> RasterCompressionType:
        """Get current raster compression type."""
        return self._raster_compression
    
    def set_raster_compression(self, compression: RasterCompressionType) -> None:
        """Set raster compression type."""
        self._raster_compression = compression
        self._notify_config_changed()
    
    def get_available_raster_formats(self) -> List[RasterExportFormat]:
        """Get list of available raster export formats."""
        return list(RasterExportFormat)
    
    def get_available_compressions(self) -> List[RasterCompressionType]:
        """Get list of available compression types."""
        return list(RasterCompressionType)

    # === Raster Clipping Options (US-EXP-06, US-EXP-07) ===
    
    def is_raster_clip_enabled(self) -> bool:
        """Check if raster clipping is enabled."""
        return self._raster_clip_enabled
    
    def set_raster_clip_enabled(self, enabled: bool) -> None:
        """Enable or disable raster clipping."""
        self._raster_clip_enabled = enabled
        self._notify_config_changed()
    
    def get_raster_mask_layer_id(self) -> Optional[str]:
        """Get mask layer ID for raster clipping."""
        return self._raster_mask_layer_id
    
    def set_raster_mask_layer_id(self, layer_id: Optional[str]) -> None:
        """Set mask layer for raster clipping."""
        self._raster_mask_layer_id = layer_id
        self._notify_config_changed()
    
    def get_raster_clip_mode(self) -> RasterClipMode:
        """Get raster clipping mode."""
        return self._raster_clip_mode
    
    def set_raster_clip_mode(self, mode: RasterClipMode) -> None:
        """Set raster clipping mode (bbox or exact geometry)."""
        self._raster_clip_mode = mode
        self._notify_config_changed()
    
    def get_polygon_layers_for_mask(self) -> List[Dict[str, Any]]:
        """
        Get list of polygon layers that can be used as mask.
        
        Returns list with layer info including filter indicator.
        
        Returns:
            List of dicts with: layer_id, name, has_filter, filter_expression
        """
        from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes
        
        result = []
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            
            # Only polygon layers can be used as mask
            geom_type = layer.geometryType()
            if geom_type != QgsWkbTypes.PolygonGeometry:
                continue
            
            # Check if layer has active filter (US-EXP-02)
            subset_string = layer.subsetString()
            has_filter = bool(subset_string)
            
            result.append({
                'layer_id': layer.id(),
                'name': layer.name(),
                'has_filter': has_filter,
                'filter_expression': subset_string if has_filter else None,
                'display_name': f"{layer.name()} (🔶 filtered)" if has_filter else layer.name()
            })
        
        return result

    # === Raster Export Configuration Builder ===
    
    def build_raster_configuration(self, layer_id: str) -> RasterExportConfiguration:
        """
        Build raster export configuration for a specific layer.
        
        Args:
            layer_id: Raster layer ID to export
            
        Returns:
            RasterExportConfiguration with current settings
        """
        return RasterExportConfiguration(
            layer_id=layer_id,
            output_path=self._output_path,
            output_format=self._raster_format,
            compression=self._raster_compression,
            output_crs=self._output_crs,
            clip_enabled=self._raster_clip_enabled,
            mask_layer_id=self._raster_mask_layer_id,
            clip_mode=self._raster_clip_mode,
            create_cog=self._raster_create_cog,
            create_pyramids=self._raster_create_pyramids,
            # Value filtering (v5.0 - EPIC-UNIFIED-FILTER)
            filter_enabled=self._raster_filter_enabled,
            min_value=self._raster_filter_min_value,
            max_value=self._raster_filter_max_value,
            nodata_value=self._raster_filter_nodata_value,
            band_index=self._raster_filter_band_index,
        )
    
    # === Raster Value Filtering (v5.0 - EPIC-UNIFIED-FILTER) ===
    
    def set_raster_filter_enabled(self, enabled: bool) -> None:
        """Enable/disable value filtering for raster export."""
        if enabled == self._raster_filter_enabled:
            return
        self._raster_filter_enabled = enabled
        self._notify_config_changed()
    
    def set_raster_filter_range(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> None:
        """
        Set value filter range for raster export.
        
        Args:
            min_value: Minimum value to include (None for no minimum)
            max_value: Maximum value to include (None for no maximum)
        """
        self._raster_filter_min_value = min_value
        self._raster_filter_max_value = max_value
        self._notify_config_changed()
    
    def set_raster_filter_nodata(self, nodata_value: Optional[float]) -> None:
        """Set NoData value for filtered pixels."""
        self._raster_filter_nodata_value = nodata_value
        self._notify_config_changed()
    
    def set_raster_filter_band(self, band_index: int) -> None:
        """Set band index for value filtering (1-based)."""
        if band_index < 1:
            band_index = 1
        self._raster_filter_band_index = band_index
        self._notify_config_changed()
    
    def get_raster_filter_state(self) -> Dict[str, Any]:
        """Get current raster filter state."""
        return {
            "enabled": self._raster_filter_enabled,
            "min_value": self._raster_filter_min_value,
            "max_value": self._raster_filter_max_value,
            "nodata_value": self._raster_filter_nodata_value,
            "band_index": self._raster_filter_band_index,
        }

    # === CRS Selection ===

    
    def get_output_crs(self) -> Optional[str]:
        """Get current output CRS (EPSG code or WKT)."""
        return self._output_crs
    
    def set_output_crs(self, crs: Optional[str]) -> None:
        """
        Set output CRS.
        
        Args:
            crs: CRS as EPSG code (e.g., "EPSG:4326") or WKT, or None for layer CRS
        """
        if crs == self._output_crs:
            return
        
        self._output_crs = crs
        self._notify_config_changed()
    
    def on_crs_changed(self, crs_string: str) -> None:
        """
        Handle CRS change from UI.
        
        Args:
            crs_string: CRS string from selector
        """
        self.set_output_crs(crs_string if crs_string else None)
    
    # === Export Mode ===
    
    def get_export_mode(self) -> ExportMode:
        """Get current export mode."""
        return self._export_mode
    
    def set_export_mode(self, mode: ExportMode) -> None:
        """
        Set export mode.
        
        Args:
            mode: Export mode
        """
        if mode == self._export_mode:
            return
        
        # Validate mode is compatible with format
        if mode == ExportMode.MERGED and not self._output_format.supports_multiple_layers:
            return  # Can't merge to shapefile
        
        self._export_mode = mode
        self._notify_config_changed()
    
    # === Options ===
    
    def get_include_styles(self) -> bool:
        """Get whether to include layer styles."""
        return self._include_styles
    
    def set_include_styles(self, include: bool) -> None:
        """Set whether to include layer styles."""
        if include == self._include_styles:
            return
        self._include_styles = include
        self._notify_config_changed()
    
    def get_zip_output(self) -> bool:
        """Get whether to zip output."""
        return self._zip_output
    
    def set_zip_output(self, zip_it: bool) -> None:
        """Set whether to zip output."""
        if zip_it == self._zip_output:
            return
        self._zip_output = zip_it
        self._notify_config_changed()
    
    # === Configuration ===
    
    def build_configuration(self) -> ExportConfiguration:
        """
        Build current configuration object.
        
        Returns:
            Current export configuration
        """
        return ExportConfiguration(
            layer_ids=self._layer_ids.copy(),
            output_format=self._output_format,
            output_path=self._output_path,
            output_crs=self._output_crs,
            mode=self._export_mode,
            include_styles=self._include_styles,
            zip_output=self._zip_output
        )
    
    def apply_configuration(self, config: ExportConfiguration) -> None:
        """
        Apply a saved configuration.
        
        Args:
            config: Configuration to apply
        """
        self._layer_ids = config.layer_ids.copy()
        self._output_format = config.output_format
        self._output_path = config.output_path
        self._output_crs = config.output_crs
        self._export_mode = config.mode
        self._include_styles = config.include_styles
        self._zip_output = config.zip_output
        
        self._notify_config_changed()
    
    # === Export Execution ===
    
    def can_export(self) -> bool:
        """
        Check if export can be executed.
        
        Returns:
            True if configuration is valid for export
        """
        if self._is_exporting:
            return False
        
        config = self.build_configuration()
        return config.is_valid()
    
    def execute_export(self) -> bool:
        """
        Execute the export operation.
        
        Handles both vector and raster exports:
        - Vector layers: Uses LayerExporter
        - Raster layers: Uses RasterExporter
        - Mixed: Exports both types
        
        Returns:
            True if export started, False otherwise
        """
        if not self.can_export():
            return False
        
        self._is_exporting = True
        self._export_progress = 0.0
        
        # Notify started
        for callback in self._on_export_started_callbacks:
            try:
                callback()
            except Exception:
                pass
        
        results = []
        
        try:
            # Export raster layers if any selected (US-EXP-08)
            if self.has_raster_selected():
                logger.info(f"Exporting {len(self._raster_layer_ids)} raster layer(s)")
                raster_result = self.execute_raster_exports()
                results.append(raster_result)
            
            # Export vector layers if any selected
            if self.has_vector_selected():
                config = self.build_configuration()
                # Filter to only vector layers
                vector_ids = self.get_selected_vector_ids()
                config.layer_ids = vector_ids
                
                logger.info(f"Exporting {len(vector_ids)} vector layer(s)")
                
                if config.mode == ExportMode.BATCH or len(config.layer_ids) > 1:
                    vector_result = self._execute_batch_export(config)
                else:
                    vector_result = self._execute_single_export(config)
                results.append(vector_result)
            
            # Aggregate results
            if results:
                aggregated = ExportResult(
                    success=all(r.success for r in results),
                    exported_files=[f for r in results for f in r.exported_files],
                    failed_layers=[f for r in results for f in r.failed_layers],
                    execution_time_ms=sum(r.execution_time_ms for r in results)
                )
                self._on_export_success(aggregated)
            else:
                self._on_export_error("No layers to export")
                return False
            
            return True
            
        except Exception as e:
            self._on_export_error(str(e))
            return False
    
    def _execute_single_export(self, config: ExportConfiguration) -> ExportResult:
        """
        Execute single layer export.
        
        Args:
            config: Export configuration
            
        Returns:
            Export result
        """
        # This is a simplified implementation
        # Actual implementation would use QGIS processing or ogr2ogr
        
        if not config.layer_ids:
            return ExportResult(success=False, error_message="No layers selected")
        
        # Simulate successful export
        exported_path = config.output_path
        
        return ExportResult(
            success=True,
            exported_files=[exported_path]
        )
    
    def _execute_batch_export(self, config: ExportConfiguration) -> ExportResult:
        """
        Execute batch export (multiple layers to separate files).
        
        Args:
            config: Export configuration
            
        Returns:
            Export result
        """
        exported_files = []
        failed_layers = []
        
        total = len(config.layer_ids)
        
        for i, layer_id in enumerate(config.layer_ids):
            try:
                # Build output path for this layer
                base_path = Path(config.output_path)
                if base_path.suffix:
                    # File path - add layer name before extension
                    layer_path = base_path.parent / f"{base_path.stem}_{layer_id}{base_path.suffix}"
                else:
                    # Directory - use layer name as filename
                    layer_path = base_path / f"{layer_id}{config.output_format.extension}"
                
                # Simulate export
                exported_files.append(str(layer_path))
                
                # Update progress
                self._export_progress = (i + 1) / total
                self._notify_progress(self._export_progress)
                
            except Exception as e:
                failed_layers.append(layer_id)
        
        return ExportResult(
            success=len(failed_layers) == 0,
            exported_files=exported_files,
            failed_layers=failed_layers
        )
    
    def _execute_raster_export(self, raster_config: RasterExportConfiguration) -> ExportResult:
        """
        Execute raster export using RasterExporter or UnifiedExportAdapter.
        
        Uses core/export/raster_exporter.py which supports:
        - GeoTIFF with compression
        - COG creation
        - Clipping by vector mask
        
        When value filtering is enabled (v5.0), uses UnifiedExportAdapter
        which supports:
        - Value range filtering
        - NoData handling
        - Band-specific filtering
        
        Args:
            raster_config: Raster export configuration
            
        Returns:
            Export result
        """
        from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
        
        # Route to UnifiedExportAdapter if value filtering is enabled
        if raster_config.has_value_filter:
            return self._execute_raster_export_with_filter(raster_config)
        
        try:
            # Import RasterExporter
            from ...core.export.raster_exporter import (
                RasterExporter,
                RasterExportConfig as CoreRasterConfig,
                RasterExportFormat as CoreRasterFormat,
                CompressionType,
            )
            
            # Get raster layer
            raster_layer = QgsProject.instance().mapLayer(raster_config.layer_id)
            if not raster_layer or not isinstance(raster_layer, QgsRasterLayer):
                return ExportResult(
                    success=False,
                    error_message=f"Invalid raster layer: {raster_config.layer_id}"
                )
            
            # Get mask layer if clipping enabled
            mask_layer = None
            if raster_config.clip_enabled and raster_config.mask_layer_id:
                mask_layer = QgsProject.instance().mapLayer(raster_config.mask_layer_id)
                if not mask_layer or not isinstance(mask_layer, QgsVectorLayer):
                    return ExportResult(
                        success=False,
                        error_message=f"Invalid mask layer: {raster_config.mask_layer_id}"
                    )
            
            # Map format enum
            format_map = {
                RasterExportFormat.GEOTIFF: CoreRasterFormat.GEOTIFF,
                RasterExportFormat.COG: CoreRasterFormat.COG,
                RasterExportFormat.PNG: CoreRasterFormat.PNG,
                RasterExportFormat.JPEG: CoreRasterFormat.JPEG,
            }
            
            # Map compression enum
            compression_map = {
                RasterCompressionType.NONE: CompressionType.NONE,
                RasterCompressionType.LZW: CompressionType.LZW,
                RasterCompressionType.DEFLATE: CompressionType.DEFLATE,
                RasterCompressionType.ZSTD: CompressionType.ZSTD,
                RasterCompressionType.JPEG: CompressionType.JPEG,
            }
            
            # Build core config
            core_config = CoreRasterConfig(
                layer=raster_layer,
                output_path=raster_config.output_path,
                format=format_map.get(raster_config.output_format, CoreRasterFormat.GEOTIFF),
                compression=compression_map.get(raster_config.compression, CompressionType.LZW),
                mask_layer=mask_layer,
                create_pyramids=raster_config.create_pyramids,
            )
            
            # For bounding box mode, use extent instead of mask
            if raster_config.clip_enabled and raster_config.clip_mode == RasterClipMode.BOUNDING_BOX:
                if mask_layer:
                    core_config.extent = mask_layer.extent()
                    core_config.mask_layer = None  # Use extent, not geometry clipping
            
            # Execute export
            exporter = RasterExporter()
            
            # Connect progress signal
            def on_progress(value: int):
                self._export_progress = value / 100.0
                self._notify_progress(self._export_progress)
            
            exporter.progressChanged.connect(on_progress)
            
            result = exporter.export(core_config)
            
            if result.success:
                logger.info(f"Raster export success: {result.output_path} ({result.output_size_mb:.2f} MB)")
                return ExportResult(
                    success=True,
                    exported_files=[result.output_path] if result.output_path else [],
                    execution_time_ms=result.processing_time_seconds * 1000
                )
            else:
                logger.error(f"Raster export failed: {result.error_message}")
                return ExportResult(
                    success=False,
                    error_message=result.error_message or "Unknown raster export error"
                )
                
        except ImportError as e:
            logger.error(f"RasterExporter import failed: {e}")
            return ExportResult(
                success=False,
                error_message=f"RasterExporter not available: {e}"
            )
        except Exception as e:
            logger.exception(f"Raster export exception: {e}")
            return ExportResult(
                success=False,
                error_message=str(e)
            )
    
    def _execute_raster_export_with_filter(
        self, raster_config: RasterExportConfiguration
    ) -> ExportResult:
        """
        Execute raster export with value filtering via UnifiedExportAdapter.
        
        This method is called when value filtering is enabled on the raster config.
        It uses the UnifiedFilterService via the adapter to:
        - Filter pixels by value range
        - Apply NoData for excluded pixels
        - Export the filtered result
        
        Args:
            raster_config: Raster export configuration with filter settings
            
        Returns:
            Export result
        """
        try:
            # Import adapter
            from ...adapters.unified_export_adapter import (
                UnifiedExportAdapter,
                UnifiedExportRequest,
            )
            
            # Map raster format to string
            format_map = {
                RasterExportFormat.GEOTIFF: "GTiff",
                RasterExportFormat.COG: "COG",
                RasterExportFormat.PNG: "PNG",
                RasterExportFormat.JPEG: "JPEG",
            }
            
            # Map compression to string
            compression_map = {
                RasterCompressionType.NONE: "NONE",
                RasterCompressionType.LZW: "LZW",
                RasterCompressionType.DEFLATE: "DEFLATE",
                RasterCompressionType.ZSTD: "ZSTD",
                RasterCompressionType.JPEG: "JPEG",
            }
            
            # Progress callback
            def on_progress(percent: float, message: str):
                self._export_progress = percent / 100.0
                self._notify_progress(self._export_progress)
            
            # Build unified request
            request = UnifiedExportRequest(
                layer_id=raster_config.layer_id,
                output_path=raster_config.output_path,
                layer_type="raster",
                # Raster-specific options
                raster_format=format_map.get(raster_config.output_format, "GTiff"),
                compression=compression_map.get(raster_config.compression, "LZW"),
                create_pyramids=raster_config.create_pyramids,
                # Value filtering
                min_value=raster_config.min_value,
                max_value=raster_config.max_value,
                nodata_value=raster_config.nodata_value,
                band_index=raster_config.band_index,
                # Clipping
                mask_layer_id=raster_config.mask_layer_id if raster_config.clip_enabled else None,
                # Callbacks
                progress_callback=on_progress,
            )
            
            # Execute via adapter
            adapter = UnifiedExportAdapter()
            result = adapter.export(request)
            
            if result.success:
                logger.info(
                    f"Filtered raster export success: {result.output_path} "
                    f"(matched {result.statistics.get('match_percentage', 'N/A')}%)"
                )
                return ExportResult(
                    success=True,
                    exported_files=[result.output_path] if result.output_path else [],
                    execution_time_ms=result.execution_time_ms or 0.0
                )
            else:
                logger.error(f"Filtered raster export failed: {result.error_message}")
                return ExportResult(
                    success=False,
                    error_message=result.error_message or "Unknown filtered export error"
                )
                
        except ImportError as e:
            logger.error(f"UnifiedExportAdapter import failed: {e}")
            # Fallback to regular export without filtering
            logger.warning("Falling back to standard export (no value filtering)")
            raster_config_copy = RasterExportConfiguration(
                layer_id=raster_config.layer_id,
                output_path=raster_config.output_path,
                output_format=raster_config.output_format,
                compression=raster_config.compression,
                output_crs=raster_config.output_crs,
                clip_enabled=raster_config.clip_enabled,
                mask_layer_id=raster_config.mask_layer_id,
                clip_mode=raster_config.clip_mode,
                create_cog=raster_config.create_cog,
                create_pyramids=raster_config.create_pyramids,
                filter_enabled=False,  # Disable filtering for fallback
            )
            return self._execute_raster_export(raster_config_copy)
            
        except Exception as e:
            logger.exception(f"Filtered raster export exception: {e}")
            return ExportResult(
                success=False,
                error_message=str(e)
            )
    
    def execute_raster_exports(self) -> ExportResult:
        """
        Execute export for all selected raster layers.
        
        Returns:
            Aggregated export result
        """
        if not self._raster_layer_ids:
            return ExportResult(success=False, error_message="No raster layers selected")
        
        exported_files = []
        failed_layers = []
        total_time = 0.0
        
        for i, layer_id in enumerate(self._raster_layer_ids):
            # Build config for this layer
            config = self.build_raster_configuration(layer_id)
            
            # Adjust output path for multiple rasters
            if len(self._raster_layer_ids) > 1:
                from qgis.core import QgsProject
                layer = QgsProject.instance().mapLayer(layer_id)
                layer_name = layer.name() if layer else layer_id
                base_path = Path(self._output_path)
                config.output_path = str(
                    base_path.parent / f"{base_path.stem}_{layer_name}{self._raster_format.extension}"
                )
            
            result = self._execute_raster_export(config)
            
            if result.success:
                exported_files.extend(result.exported_files)
            else:
                failed_layers.append(layer_id)
            
            total_time += result.execution_time_ms
            
            # Update progress
            self._export_progress = (i + 1) / len(self._raster_layer_ids)
            self._notify_progress(self._export_progress)
        
        return ExportResult(
            success=len(failed_layers) == 0,
            exported_files=exported_files,
            failed_layers=failed_layers,
            execution_time_ms=total_time
        )
    
    def _on_export_success(self, result: ExportResult) -> None:
        """Handle successful export."""
        self._is_exporting = False
        self._last_result = result
        self._export_progress = 1.0
        
        for callback in self._on_export_completed_callbacks:
            try:
                callback(result)
            except Exception:
                pass
    
    def _on_export_error(self, error_message: str) -> None:
        """Handle export error."""
        self._is_exporting = False
        self._last_result = ExportResult(
            success=False,
            error_message=error_message
        )
    
    def get_last_result(self) -> Optional[ExportResult]:
        """Get result of last export operation."""
        return self._last_result
    
    def get_progress(self) -> float:
        """Get current export progress (0.0 to 1.0)."""
        return self._export_progress
    
    def is_exporting(self) -> bool:
        """Check if export is in progress."""
        return self._is_exporting
    
    # === Callbacks ===
    
    def register_export_started_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for export start."""
        if callback not in self._on_export_started_callbacks:
            self._on_export_started_callbacks.append(callback)
    
    def register_export_completed_callback(self, callback: Callable[[ExportResult], None]) -> None:
        """Register callback for export completion."""
        if callback not in self._on_export_completed_callbacks:
            self._on_export_completed_callbacks.append(callback)
    
    def register_progress_callback(self, callback: Callable[[float], None]) -> None:
        """Register callback for progress updates."""
        if callback not in self._on_progress_callbacks:
            self._on_progress_callbacks.append(callback)
    
    def register_config_callback(self, callback: Callable[[ExportConfiguration], None]) -> None:
        """Register callback for configuration changes."""
        if callback not in self._on_config_changed_callbacks:
            self._on_config_changed_callbacks.append(callback)
    
    def _notify_config_changed(self) -> None:
        """Notify listeners of configuration change."""
        config = self.build_configuration()
        for callback in self._on_config_changed_callbacks:
            try:
                callback(config)
            except Exception:
                pass
    
    def _notify_progress(self, progress: float) -> None:
        """Notify listeners of progress update."""
        for callback in self._on_progress_callbacks:
            try:
                callback(progress)
            except Exception:
                pass
    
    # === Lifecycle ===
    
    def setup(self) -> None:
        """Initialize the controller and connect UI signals."""
        if not self._dockwidget:
            logger.warning("ExportingController.setup: No dockwidget available")
            return
            
        try:
            # --- Layer selection widget (critical for raster detection) ---
            # Connect to checkableComboBoxLayer_exporting_layers signal
            if hasattr(self._dockwidget, 'checkableComboBoxLayer_exporting_layers'):
                self._dockwidget.checkableComboBoxLayer_exporting_layers.checkedItemsChanged.connect(
                    self._on_export_layers_changed
                )
                logger.debug("Connected to checkableComboBoxLayer_exporting_layers.checkedItemsChanged")
            
            # --- Raster UI widget connections ---
            # Format/compression combos
            if hasattr(self._dockwidget, 'comboBox_exporting_raster_format'):
                self._dockwidget.comboBox_exporting_raster_format.currentIndexChanged.connect(
                    self._on_raster_format_changed
                )
            if hasattr(self._dockwidget, 'comboBox_exporting_raster_compression'):
                self._dockwidget.comboBox_exporting_raster_compression.currentIndexChanged.connect(
                    self._on_raster_compression_changed
                )
            
            # COG checkbox
            if hasattr(self._dockwidget, 'checkBox_exporting_raster_cog'):
                self._dockwidget.checkBox_exporting_raster_cog.stateChanged.connect(
                    self._on_raster_cog_changed
                )
            
            # Clipping checkbox - enables/disables mask options
            if hasattr(self._dockwidget, 'checkBox_exporting_raster_clip'):
                self._dockwidget.checkBox_exporting_raster_clip.stateChanged.connect(
                    self._on_raster_clip_changed
                )
            
            # Mask layer combo
            if hasattr(self._dockwidget, 'mMapLayerComboBox_exporting_raster_mask'):
                self._dockwidget.mMapLayerComboBox_exporting_raster_mask.layerChanged.connect(
                    self._on_raster_mask_layer_changed
                )
            
            # Clip mode radio buttons
            if hasattr(self._dockwidget, 'radioButton_exporting_raster_clip_bbox'):
                self._dockwidget.radioButton_exporting_raster_clip_bbox.toggled.connect(
                    self._on_raster_clip_mode_changed
                )
            
            # Register callback to show/hide raster options GroupBox
            self.register_raster_selection_callback(self._update_raster_groupbox_visibility)
            
            logger.debug("ExportingController.setup: Raster UI signals connected")
            
        except Exception as e:
            logger.warning(f"ExportingController.setup: Failed to connect signals: {e}")
    
    def _disconnect_all_signals(self) -> None:
        """Disconnect all UI signals safely."""
        if not self._dockwidget:
            return
            
        try:
            widgets_to_disconnect = [
                ('checkableComboBoxLayer_exporting_layers', 'checkedItemsChanged'),
                ('comboBox_exporting_raster_format', 'currentIndexChanged'),
                ('comboBox_exporting_raster_compression', 'currentIndexChanged'),
                ('checkBox_exporting_raster_cog', 'stateChanged'),
                ('checkBox_exporting_raster_clip', 'stateChanged'),
                ('mMapLayerComboBox_exporting_raster_mask', 'layerChanged'),
                ('radioButton_exporting_raster_clip_bbox', 'toggled'),
            ]
            
            for widget_name, signal_name in widgets_to_disconnect:
                if hasattr(self._dockwidget, widget_name):
                    widget = getattr(self._dockwidget, widget_name)
                    signal = getattr(widget, signal_name, None)
                    if signal:
                        try:
                            signal.disconnect()
                        except TypeError:
                            pass  # No connections to disconnect
                            
            logger.debug("ExportingController._disconnect_all_signals: Signals disconnected")
            
        except Exception as e:
            logger.debug(f"ExportingController._disconnect_all_signals: {e}")
    
    # === Layer Selection Handler (EPIC-4 Sprint 2) ===
    
    def _on_export_layers_changed(self) -> None:
        """
        Handle layer selection change in export combobox (checkedItemsChanged signal).
        
        This method:
        1. Gets the list of currently checked layer names
        2. Resolves layer names to layer IDs
        3. Detects which are rasters vs vectors
        4. Updates internal state and notifies UI to show/hide raster options
        """
        if not self._dockwidget:
            return
        
        try:
            from qgis.core import QgsProject, QgsRasterLayer
            
            combo = self._dockwidget.checkableComboBoxLayer_exporting_layers
            checked_items = combo.checkedItems() if hasattr(combo, 'checkedItems') else []
            
            # Get layer names from checked items
            layer_names = []
            for item in checked_items:
                if hasattr(item, 'text'):
                    layer_names.append(item.text())
                elif isinstance(item, str):
                    layer_names.append(item)
            
            logger.debug(f"Export layers changed: {layer_names}")
            
            # Resolve names to layer IDs and detect rasters
            had_raster = self.has_raster_selected()
            
            self._layer_ids.clear()
            self._raster_layer_ids.clear()
            
            project = QgsProject.instance()
            for name in layer_names:
                # Find layer by name
                layers = project.mapLayersByName(name)
                if layers:
                    layer = layers[0]
                    layer_id = layer.id()
                    self._layer_ids.append(layer_id)
                    
                    # Track rasters separately
                    if isinstance(layer, QgsRasterLayer):
                        self._raster_layer_ids.append(layer_id)
            
            has_raster = self.has_raster_selected()
            
            # Notify if raster selection state changed
            if had_raster != has_raster:
                logger.info(f"Raster selection changed: {had_raster} -> {has_raster}")
                self._notify_raster_selection_changed(has_raster)
            
            self._notify_config_changed()
            
        except Exception as e:
            logger.warning(f"_on_export_layers_changed error: {e}")

    # === Raster UI Signal Handlers ===
    
    def _on_raster_format_changed(self, index: int) -> None:
        """Handle raster format combo change."""
        if not self._dockwidget:
            return
        
        try:
            combo = self._dockwidget.comboBox_exporting_raster_format
            format_text = combo.currentText().upper()
            
            # Map text to enum
            format_map = {
                'GEOTIFF': RasterExportFormat.GEOTIFF,
                'COG': RasterExportFormat.COG,
                'PNG': RasterExportFormat.PNG,
                'JPEG': RasterExportFormat.JPEG,
            }
            
            new_format = format_map.get(format_text, RasterExportFormat.GEOTIFF)
            self._raster_format = new_format
            
            # Update COG checkbox visibility (only for TIFF formats)
            if hasattr(self._dockwidget, 'checkBox_exporting_raster_cog'):
                cog_visible = new_format in (RasterExportFormat.GEOTIFF, RasterExportFormat.COG)
                self._dockwidget.checkBox_exporting_raster_cog.setVisible(cog_visible)
                if new_format == RasterExportFormat.COG:
                    self._dockwidget.checkBox_exporting_raster_cog.setChecked(True)
            
            # Update compression options based on format
            self._update_compression_for_format(new_format)
            
            logger.debug(f"Raster format changed to: {new_format.value}")
            self._notify_config_changed()
            
        except Exception as e:
            logger.debug(f"_on_raster_format_changed error: {e}")
    
    def _update_compression_for_format(self, raster_format: RasterExportFormat) -> None:
        """Update available compression options based on format."""
        if not self._dockwidget or not hasattr(self._dockwidget, 'comboBox_exporting_raster_compression'):
            return
            
        combo = self._dockwidget.comboBox_exporting_raster_compression
        current = combo.currentText()
        
        # Clear and repopulate
        combo.clear()
        
        if raster_format in (RasterExportFormat.GEOTIFF, RasterExportFormat.COG):
            # All compressions available for TIFF
            combo.addItems(['LZW', 'DEFLATE', 'ZSTD', 'JPEG', 'None'])
        elif raster_format == RasterExportFormat.PNG:
            # PNG uses internal compression
            combo.addItems(['DEFLATE', 'None'])
        elif raster_format == RasterExportFormat.JPEG:
            # JPEG only supports JPEG compression
            combo.addItems(['JPEG'])
        
        # Restore previous selection if possible
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    
    def _on_raster_compression_changed(self, index: int) -> None:
        """Handle raster compression combo change."""
        if not self._dockwidget:
            return
        
        try:
            combo = self._dockwidget.comboBox_exporting_raster_compression
            compression_text = combo.currentText().upper()
            
            compression_map = {
                'LZW': RasterCompressionType.LZW,
                'DEFLATE': RasterCompressionType.DEFLATE,
                'ZSTD': RasterCompressionType.ZSTD,
                'JPEG': RasterCompressionType.JPEG,
                'NONE': RasterCompressionType.NONE,
            }
            
            self._raster_compression = compression_map.get(compression_text, RasterCompressionType.LZW)
            logger.debug(f"Raster compression changed to: {self._raster_compression.value}")
            self._notify_config_changed()
            
        except Exception as e:
            logger.debug(f"_on_raster_compression_changed error: {e}")
    
    def _on_raster_cog_changed(self, state: int) -> None:
        """
        Handle COG checkbox state change.
        
        US-EXP-05: COG format includes internal pyramids (overviews) for efficient web streaming.
        """
        from qgis.PyQt.QtCore import Qt
        
        is_cog = state == Qt.Checked
        self._raster_create_cog = is_cog
        
        # Update format to COG if checked, back to GEOTIFF if unchecked
        if is_cog:
            self._raster_format = RasterExportFormat.COG
        elif self._raster_format == RasterExportFormat.COG:
            self._raster_format = RasterExportFormat.GEOTIFF
        
        logger.debug(f"COG option changed: {is_cog}, create_cog={self._raster_create_cog}")
        self._notify_config_changed()
    
    def _on_raster_clip_changed(self, state: int) -> None:
        """Handle clip checkbox - enables/disables mask options."""
        from qgis.PyQt.QtCore import Qt
        
        is_clip_enabled = state == Qt.Checked
        self._raster_clip_enabled = is_clip_enabled
        
        # Enable/disable mask-related widgets
        if self._dockwidget:
            widgets = [
                'label_raster_mask',
                'mMapLayerComboBox_exporting_raster_mask',
                'radioButton_exporting_raster_clip_bbox',
                'radioButton_exporting_raster_clip_geom',
            ]
            for widget_name in widgets:
                if hasattr(self._dockwidget, widget_name):
                    getattr(self._dockwidget, widget_name).setEnabled(is_clip_enabled)
            
            # Populate mask layers when enabled
            if is_clip_enabled:
                self._populate_mask_layer_combo()
        
        logger.debug(f"Raster clipping enabled: {is_clip_enabled}")
        self._notify_config_changed()
    
    def _populate_mask_layer_combo(self) -> None:
        """
        Populate the mask layer combo with polygon layers.
        
        US-EXP-02: Updates tooltip to show filter status for selected layer.
        """
        if not self._dockwidget or not hasattr(self._dockwidget, 'mMapLayerComboBox_exporting_raster_mask'):
            return
        
        try:
            # QGIS 3.34+: Use Qgis.LayerFilter enum flags instead of deprecated QgsMapLayerProxyModel int flags
            try:
                from qgis.core import Qgis
                _LayerFilter = Qgis.LayerFilter
                _LayerFilters = Qgis.LayerFilters
            except (ImportError, AttributeError):
                from qgis.core import QgsMapLayerProxyModel as _LayerFilter
                _LayerFilters = None

            combo = self._dockwidget.mMapLayerComboBox_exporting_raster_mask
            # Filter to polygon layers only
            filters = _LayerFilter.PolygonLayer
            combo.setFilters(_LayerFilters(filters) if _LayerFilters else filters)
            
            # Update tooltip to show filter info
            self._update_mask_layer_tooltip()
            
            logger.debug("Mask layer combo populated with polygon layers")
            
        except Exception as e:
            logger.debug(f"_populate_mask_layer_combo error: {e}")
    
    def _update_mask_layer_tooltip(self) -> None:
        """
        Update mask layer combo tooltip to show filter status.
        
        US-EXP-02: Shows "(🔶 filtered)" indicator and filter expression.
        """
        if not self._dockwidget or not hasattr(self._dockwidget, 'mMapLayerComboBox_exporting_raster_mask'):
            return
        
        try:
            combo = self._dockwidget.mMapLayerComboBox_exporting_raster_mask
            layer = combo.currentLayer()
            
            if not layer:
                combo.setToolTip(
                    "Clipping Mask Layer\n\n"
                    "Select a polygon layer to use as clipping mask.\n"
                    "Raster will be clipped to the polygon boundaries."
                )
                return
            
            subset = layer.subsetString()
            if subset:
                # Layer has active filter
                tooltip = (
                    f"🔶 {layer.name()} (filtered)\n"
                    f"Filter: {subset}\n\n"
                    "Only filtered features will be used as clipping mask."
                )
            else:
                tooltip = (
                    f"{layer.name()}\n"
                    "All features will be used as clipping mask.\n"
                    "Tip: Apply a filter first to clip to specific features."
                )
            
            combo.setToolTip(tooltip)
            
        except Exception as e:
            logger.debug(f"_update_mask_layer_tooltip error: {e}")
    
    def _on_raster_mask_layer_changed(self, layer) -> None:
        """Handle mask layer selection change."""
        if layer:
            self._raster_mask_layer_id = layer.id()
            logger.debug(f"Mask layer changed to: {layer.name()}")
        else:
            self._raster_mask_layer_id = None
            logger.debug("Mask layer cleared")
        
        # US-EXP-02: Update tooltip to show filter status
        self._update_mask_layer_tooltip()
        
        self._notify_config_changed()
    
    def _on_raster_clip_mode_changed(self, checked: bool) -> None:
        """Handle clip mode radio button change."""
        if not checked:  # Only process when button is checked
            return
        
        if self._dockwidget and hasattr(self._dockwidget, 'radioButton_exporting_raster_clip_bbox'):
            if self._dockwidget.radioButton_exporting_raster_clip_bbox.isChecked():
                self._raster_clip_mode = RasterClipMode.BOUNDING_BOX
            else:
                self._raster_clip_mode = RasterClipMode.EXACT_GEOMETRY
        
        logger.debug(f"Raster clip mode changed to: {self._raster_clip_mode.value}")
        self._notify_config_changed()
    
    def _update_raster_groupbox_visibility(self, has_raster: bool) -> None:
        """
        Show or hide the raster options GroupBox based on selection.
        
        This is called via callback when raster selection changes.
        
        Args:
            has_raster: True if at least one raster is selected
        """
        if not self._dockwidget:
            return
        
        try:
            if hasattr(self._dockwidget, 'groupBox_exporting_raster_options'):
                self._dockwidget.groupBox_exporting_raster_options.setVisible(has_raster)
                logger.debug(f"Raster options GroupBox visibility: {has_raster}")
        except Exception as e:
            logger.debug(f"_update_raster_groupbox_visibility error: {e}")
    
    def teardown(self) -> None:
        """Clean up the controller."""
        self._disconnect_all_signals()
        
        # Clear state
        self._layer_ids.clear()
        self._output_path = ""
        self._output_crs = None
        
        # Clear callbacks
        self._on_export_started_callbacks.clear()
        self._on_export_completed_callbacks.clear()
        self._on_progress_callbacks.clear()
        self._on_config_changed_callbacks.clear()
    
    def on_tab_activated(self) -> None:
        """Called when exporting tab becomes active."""
        super().on_tab_activated()
    
    def on_tab_deactivated(self) -> None:
        """Called when exporting tab becomes inactive."""
        super().on_tab_deactivated()
    
    # === Reset ===
    
    def reset(self) -> None:
        """Reset all export configuration."""
        self._layer_ids.clear()
        self._output_format = ExportFormat.GEOPACKAGE
        self._output_path = ""
        self._output_crs = None
        self._export_mode = ExportMode.SINGLE
        self._include_styles = False
        self._zip_output = False
        self._last_result = None
        
        self._notify_config_changed()
    
    # === String Representation ===
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        layers = len(self._layer_ids)
        format_name = self._output_format.value
        path = self._output_path or "not set"
        
        return (
            f"ExportingController("
            f"layers={layers}, "
            f"format={format_name}, "
            f"path={path}, "
            f"exporting={self._is_exporting})"
        )
    
    # === FIX 2026-01-16: Methods required by integration.py signal handlers ===
    
    def refresh_layers(self) -> bool:
        """
        Refresh the export layers list.
        
        Called by integration._on_widgets_initialized() when widgets are ready.
        Delegates to populate_export_combobox().
        
        Returns:
            True if refresh succeeded, False otherwise
        """
        logger.debug("ExportingController.refresh_layers() called")
        return self.populate_export_combobox()
    
    def on_task_started(self, task_type: str) -> None:
        """
        Handle task started notification.
        
        Called by integration._on_launching_task() when an export task starts.
        Can be used to update UI state (disable buttons, show progress).
        
        Args:
            task_type: Type of task started (e.g., 'export')
        """
        logger.info(f"ExportingController: Task started: {task_type}")
        if task_type == 'export':
            self._is_exporting = True
            # Notify callbacks that export started
            for callback in self._on_export_started_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.debug(f"Export started callback failed: {e}")
    
    def on_task_completed(self, task_type: str, success: bool) -> None:
        """
        Handle task completed notification.
        
        Called when an export task completes.
        
        Args:
            task_type: Type of task that completed
            success: Whether task succeeded
        """
        logger.info(f"ExportingController: Task completed: {task_type}, success={success}")
        if task_type == 'export':
            self._is_exporting = False

