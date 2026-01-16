"""
FilterMate Exporting Controller.

Manages exporting tab logic including layer selection,
format configuration, output path, CRS selection,
and export execution (single and batch).
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


class ExportFormat(Enum):
    """Supported export formats."""
    GEOPACKAGE = "GPKG"
    SHAPEFILE = "ESRI Shapefile"
    GEOJSON = "GeoJSON"
    CSV = "CSV"
    KML = "KML"
    DXF = "DXF"
    
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
        
        # State
        self._layer_ids: List[str] = []
        self._output_format: ExportFormat = ExportFormat.GEOPACKAGE
        self._output_path: str = ""
        self._output_crs: Optional[str] = None
        self._export_mode: ExportMode = ExportMode.SINGLE
        self._include_styles: bool = False
        self._zip_output: bool = False
        
        # Execution state
        self._is_exporting: bool = False
        self._last_result: Optional[ExportResult] = None
        self._export_progress: float = 0.0
        
        # Callbacks
        self._on_export_started_callbacks: List[Callable[[], None]] = []
        self._on_export_completed_callbacks: List[Callable[[ExportResult], None]] = []
        self._on_progress_callbacks: List[Callable[[float], None]] = []
        self._on_config_changed_callbacks: List[Callable[[ExportConfiguration], None]] = []

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
            
            # Check preconditions
            if not dockwidget.widgets_initialized or not dockwidget.has_loaded_layers:
                return False
            
            # v4.0.4: Early return if PROJECT_LAYERS not populated yet
            # This prevents race condition during initialization
            if not dockwidget.PROJECT_LAYERS:
                logger.info("populate_export_combobox: PROJECT_LAYERS empty, deferring until projectLayersReady signal")
                return False
            
            # Get saved preferences
            layers_to_export = []
            datatype_to_export = ''
            
            if dockwidget.project_props.get('EXPORTING', {}).get('HAS_LAYERS_TO_EXPORT'):
                layers_to_export = dockwidget.project_props['EXPORTING']['LAYERS_TO_EXPORT']
            
            if dockwidget.project_props.get('EXPORTING', {}).get('HAS_DATATYPE_TO_EXPORT'):
                datatype_to_export = dockwidget.project_props['EXPORTING']['DATATYPE_TO_EXPORT']
            
            # Import required modules
            from qgis.core import QgsVectorLayer, QgsProject
            from qgis.PyQt.QtCore import Qt
            from ...infrastructure.constants import REMOTE_PROVIDERS
            from ...infrastructure.utils import geometry_type_to_string
            from ...infrastructure.utils.validation_utils import is_layer_source_available
            
            try:
                from osgeo import ogr
                ogr_available = True
            except ImportError:
                ogr_available = False
            
            project = QgsProject.instance()
            
            # Collect diagnostic info
            qgis_layers = [l for l in project.mapLayers().values() if isinstance(l, QgsVectorLayer)]
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
                
                # Validate layer is usable
                layer_obj = project.mapLayer(layer_id)
                if layer_obj and isinstance(layer_obj, QgsVectorLayer) and is_layer_source_available(layer_obj, require_psycopg2=False):
                    display_name = f"{layer_name} [{layer_crs_authid}]"
                    item_data = {"layer_id": key, "layer_geometry_type": layer_info["layer_geometry_type"]}
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
                
                if datatype_to_export:
                    idx = datatype_widget.findText(datatype_to_export)
                    datatype_widget.setCurrentIndex(idx if idx >= 0 else datatype_widget.findText('GPKG'))
                else:
                    datatype_widget.setCurrentIndex(datatype_widget.findText('GPKG'))
            
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
    
    def on_layer_selection_changed(self, layer_ids: List[str]) -> None:
        """
        Handle layer selection change from UI.
        
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
        
        config = self.build_configuration()
        
        try:
            if config.mode == ExportMode.BATCH or len(config.layer_ids) > 1:
                result = self._execute_batch_export(config)
            else:
                result = self._execute_single_export(config)
            
            self._on_export_success(result)
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
        """Initialize the controller."""
        # Connect signals would happen here
    
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
