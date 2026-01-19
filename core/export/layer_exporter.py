"""
Layer Exporter

v4.0 EPIC-1 Phase E1: Extracted from filter_task.py export methods

Handles layer export operations to various formats.

IMPORTANT: Export is INDEPENDENT from "exploring" and QGIS selection.
====================================================================

Export behavior:
- Uses QgsVectorFileWriter which respects the layer's subsetString (filter)
- WITH subset: exports only features matching the filter
- WITHOUT subset: exports all features in the layer
- Does NOT use QGIS selectedFeatures() - selection is ignored
- Does NOT reference current_layer from exploring tab

Original source: modules/tasks/filter_task.py lines 9551-10400 (~850 lines)
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsVectorFileWriter,
        QgsCoordinateReferenceSystem,
        QgsProject,
    )
    from qgis import processing
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = Any
    QgsVectorFileWriter = Any
    QgsCoordinateReferenceSystem = Any
    QgsProject = Any

logger = logging.getLogger('FilterMate.Export')


class ExportFormat(Enum):
    """Supported export formats."""
    GPKG = "GPKG"
    SHAPEFILE = "ESRI Shapefile"
    GEOJSON = "GeoJSON"
    GML = "GML"
    KML = "KML"
    CSV = "CSV"
    XLSX = "XLSX"
    TAB = "MapInfo File"
    DXF = "DXF"
    SPATIALITE = "SpatiaLite"


@dataclass
class ExportConfig:
    """Configuration for layer export."""
    
    layers: List[str]
    """Layer names to export."""
    
    output_path: str
    """Output path (file or directory)."""
    
    datatype: str
    """Export format (GPKG, SHP, etc.)."""
    
    projection: Optional[QgsCoordinateReferenceSystem] = None
    """Target CRS or None to use layer's CRS."""
    
    style_format: Optional[str] = None
    """Style format (qml, sld, lyrx) or None."""
    
    save_styles: bool = False
    """Whether to save layer styles."""
    
    batch_mode: bool = False
    """Whether to export each layer to separate file."""
    
    batch_zip: bool = False
    """Whether to create zip archive."""


@dataclass
class ExportResult:
    """Result of export operation."""
    
    success: bool
    """Whether export succeeded."""
    
    exported_count: int = 0
    """Number of layers successfully exported."""
    
    failed_count: int = 0
    """Number of layers that failed to export."""
    
    output_path: Optional[str] = None
    """Path to exported file/directory."""
    
    error_message: Optional[str] = None
    """Error message if export failed."""
    
    warnings: List[str] = None
    """Non-fatal warnings during export."""
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class LayerExporter:
    """
    Exports QGIS vector layers to various formats.
    
    Supports:
    - Single layer export
    - Batch export to directory
    - GeoPackage multi-layer export
    - Style export (via StyleExporter)
    - CRS reprojection
    
    Example:
        exporter = LayerExporter(project)
        config = ExportConfig(
            layers=["layer1", "layer2"],
            output_path="/path/to/output.gpkg",
            datatype="GPKG",
            save_styles=True
        )
        result = exporter.export(config)
        if result.success:
            # print(f"Exported {result.exported_count} layers")  # DEBUG REMOVED
    """
    
    # Format driver mapping
    DRIVER_MAP = {
        'GPKG': 'GPKG',
        'SHP': 'ESRI Shapefile',
        'SHAPEFILE': 'ESRI Shapefile',
        'ESRI SHAPEFILE': 'ESRI Shapefile',
        'GEOJSON': 'GeoJSON',
        'JSON': 'GeoJSON',
        'GML': 'GML',
        'KML': 'KML',
        'CSV': 'CSV',
        'XLSX': 'XLSX',
        'TAB': 'MapInfo File',
        'MAPINFO': 'MapInfo File',
        'DXF': 'DXF',
        'SQLITE': 'SQLite',
        'SPATIALITE': 'SpatiaLite'
    }
    
    def __init__(self, project: Optional[QgsProject] = None):
        """
        Initialize layer exporter.
        
        Args:
            project: QgsProject instance or None to use current project
        """
        self.project = project or (QgsProject.instance() if QGIS_AVAILABLE else None)
    
    def export(self, config: ExportConfig) -> ExportResult:
        """
        Export layers according to configuration.
        
        Args:
            config: Export configuration
            
        Returns:
            ExportResult with export status and statistics
        """
        if not QGIS_AVAILABLE:
            return ExportResult(
                success=False,
                error_message="QGIS not available"
            )
        
        if not self.project:
            return ExportResult(
                success=False,
                error_message="No QGIS project available"
            )
        
        # Special handling for GPKG multi-layer export
        if config.datatype.upper() == 'GPKG' and not config.batch_mode:
            return self.export_to_gpkg(config.layers, config.output_path, config.save_styles)
        
        # Batch export (one file per layer)
        if config.batch_mode:
            return self.export_batch(config)
        
        # Single layer export
        if len(config.layers) == 1:
            return self.export_single_layer(
                config.layers[0],
                config.output_path,
                config.projection,
                config.datatype,
                config.style_format,
                config.save_styles
            )
        
        # Multiple layers to directory
        return self.export_multiple_to_directory(config)
    
    def export_single_layer(
        self,
        layer_name: str,
        output_path: str,
        projection: Optional[QgsCoordinateReferenceSystem],
        datatype: str,
        style_format: Optional[str],
        save_styles: bool
    ) -> ExportResult:
        """
        Export a single layer to file.
        
        Args:
            layer_name: Layer name to export
            output_path: Output file path
            projection: Target CRS or None to use layer's CRS
            datatype: Export format (e.g., 'SHP', 'GPKG')
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            
        Returns:
            ExportResult with export status
        """
        # Get layer
        layer = self.get_layer_by_name(layer_name)
        if not layer:
            return ExportResult(
                success=False,
                error_message=f"Layer '{layer_name}' not found in project"
            )
        
        # Determine CRS
        current_projection = projection if projection else layer.sourceCrs()
        
        # Map datatype to QGIS driver
        driver_name = self.DRIVER_MAP.get(datatype.upper(), datatype)
        
        logger.debug(f"Exporting layer '{layer.name()}' to {output_path} (driver: {driver_name})")
        
        try:
            result = QgsVectorFileWriter.writeAsVectorFormat(
                layer,
                os.path.normcase(output_path),
                "UTF-8",
                current_projection,
                driver_name
            )
            
            if result[0] != QgsVectorFileWriter.NoError:
                error_msg = result[1] if len(result) > 1 else "Unknown error"
                logger.error(f"Export failed for layer '{layer.name()}': {error_msg}")
                return ExportResult(
                    success=False,
                    error_message=error_msg
                )
            
            # Save style if requested
            if save_styles and style_format:
                from .style_exporter import save_layer_style
                save_layer_style(layer, output_path, style_format, datatype)
            
            return ExportResult(
                success=True,
                exported_count=1,
                output_path=output_path
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Export exception for layer '{layer.name()}': {error_msg}")
            return ExportResult(
                success=False,
                error_message=error_msg
            )
    
    def export_to_gpkg(
        self,
        layer_names: List[str],
        output_path: str,
        save_styles: bool
    ) -> ExportResult:
        """
        Export layers to GeoPackage format using QGIS processing.
        
        Args:
            layer_names: List of layer names to export
            output_path: Output GPKG file path
            save_styles: Whether to include layer styles
            
        Returns:
            ExportResult with export status
        """
        logger.info(f"Exporting {len(layer_names)} layer(s) to GPKG: {output_path}")
        
        # Collect layer objects
        layer_objects = []
        for layer_item in layer_names:
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            layer = self.get_layer_by_name(layer_name)
            if layer:
                layer_objects.append(layer)
        
        if not layer_objects:
            return ExportResult(
                success=False,
                error_message="No valid layers found for GPKG export"
            )
        
        alg_parameters = {
            'LAYERS': layer_objects,
            'OVERWRITE': True,
            'SAVE_STYLES': save_styles,
            'OUTPUT': output_path
        }
        
        try:
            # processing.run() is thread-safe for file operations
            output = processing.run("qgis:package", alg_parameters)
            
            if not output or 'OUTPUT' not in output:
                return ExportResult(
                    success=False,
                    error_message="GPKG export failed: no output returned"
                )
            
            logger.info(f"GPKG export successful: {output['OUTPUT']}")
            return ExportResult(
                success=True,
                exported_count=len(layer_objects),
                output_path=output['OUTPUT']
            )
            
        except Exception as e:
            logger.error(f"GPKG export failed with exception: {e}")
            return ExportResult(
                success=False,
                error_message=str(e)
            )
    
    def export_multiple_to_directory(self, config: ExportConfig) -> ExportResult:
        """
        Export multiple layers to a directory (one file per layer).
        
        Args:
            config: Export configuration
            
        Returns:
            ExportResult with export statistics
        """
        result = ExportResult(success=True, output_path=config.output_path)
        
        for layer_name_item in config.layers:
            # Handle both dict and string formats
            layer_name = layer_name_item['layer_name'] if isinstance(layer_name_item, dict) else layer_name_item
            
            # Build output path for this layer
            layer_output = os.path.join(
                config.output_path,
                f"{layer_name}.{config.datatype.lower()}"
            )
            
            # Export layer
            layer_result = self.export_single_layer(
                layer_name,
                layer_output,
                config.projection,
                config.datatype,
                config.style_format,
                config.save_styles
            )
            
            if layer_result.success:
                result.exported_count += 1
            else:
                result.failed_count += 1
                if layer_result.error_message:
                    result.warnings.append(f"{layer_name}: {layer_result.error_message}")
        
        # Overall success if at least one layer exported
        result.success = result.exported_count > 0
        if result.failed_count > 0:
            result.error_message = f"{result.failed_count} layer(s) failed to export"
        
        return result
    
    def export_batch(self, config: ExportConfig) -> ExportResult:
        """
        Export layers in batch mode (directory or zip).
        
        Args:
            config: Export configuration with batch settings
            
        Returns:
            ExportResult with export statistics
        """
        # For now, delegate to directory export
        # TODO: Implement zip archive creation
        if config.batch_zip:
            logger.warning("Batch ZIP export not yet implemented, using directory export")
        
        return self.export_multiple_to_directory(config)
    
    def get_layer_by_name(self, layer_name: str) -> Optional[QgsVectorLayer]:
        """
        Get layer object from project by name.
        
        Args:
            layer_name: Layer name to search for
            
        Returns:
            QgsVectorLayer or None if not found
        """
        if not self.project:
            return None
        
        layers_found = self.project.mapLayersByName(layer_name)
        if layers_found:
            return layers_found[0]
        
        logger.warning(f"Layer '{layer_name}' not found in project")
        return None
