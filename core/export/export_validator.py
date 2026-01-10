"""
Export Validator

v4.0 EPIC-1 Phase E1: Extracted from filter_task.py._validate_export_parameters()

Validates export configurations before execution.

Original source: modules/tasks/filter_task.py lines 9253-9351 (~100 lines)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging

try:
    from qgis.core import QgsCoordinateReferenceSystem
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsCoordinateReferenceSystem = Any

logger = logging.getLogger('FilterMate.Export')


@dataclass
class ExportValidationResult:
    """Result of export parameter validation."""
    
    valid: bool
    """Whether validation succeeded."""
    
    layers: Optional[List[str]] = None
    """List of layer names to export."""
    
    projection: Optional[Any] = None
    """Target CRS (QgsCoordinateReferenceSystem) or None."""
    
    styles: Optional[str] = None
    """Style format (qml, sld, lyrx) or None."""
    
    datatype: Optional[str] = None
    """Export format (GPKG, ESRI Shapefile, etc.)."""
    
    output_folder: Optional[str] = None
    """Output directory path."""
    
    zip_path: Optional[str] = None
    """Zip file path or None."""
    
    batch_output_folder: bool = False
    """Whether to export each layer to separate folder."""
    
    batch_zip: bool = False
    """Whether to export to zip archive."""
    
    error_message: Optional[str] = None
    """Error message if validation failed."""


def validate_export_parameters(
    task_parameters: Dict[str, Any],
    env_vars: Optional[Dict[str, Any]] = None
) -> ExportValidationResult:
    """
    Validate and extract export parameters from task configuration.
    
    Original source: filter_task.py._validate_export_parameters()
    
    Args:
        task_parameters: Task parameters dict with 'task']['EXPORTING'] config
        env_vars: Environment variables dict (for PATH_ABSOLUTE_PROJECT)
        
    Returns:
        ExportValidationResult with validated config or error message
        
    Example:
        result = validate_export_parameters(task_params, env_vars)
        if result.valid:
            exporter.export(result.layers, result.datatype, result.output_folder)
        else:
            logger.error(result.error_message)
    """
    if not QGIS_AVAILABLE:
        return ExportValidationResult(
            valid=False,
            error_message="QGIS not available"
        )
    
    # Extract export config
    try:
        config = task_parameters["task"]['EXPORTING']
    except (KeyError, TypeError) as e:
        return ExportValidationResult(
            valid=False,
            error_message=f"Missing EXPORTING config: {e}"
        )
    
    # Validate layers
    if not config.get("HAS_LAYERS_TO_EXPORT", False):
        return ExportValidationResult(
            valid=False,
            error_message="No layers selected for export"
        )
    
    layers = task_parameters["task"].get("layers")
    if not layers or len(layers) == 0:
        return ExportValidationResult(
            valid=False,
            error_message="Empty layers list for export"
        )
    
    # Validate datatype
    if not config.get("HAS_DATATYPE_TO_EXPORT", False):
        return ExportValidationResult(
            valid=False,
            error_message="No export datatype specified"
        )
    
    datatype = config.get("DATATYPE_TO_EXPORT")
    if not datatype:
        return ExportValidationResult(
            valid=False,
            error_message="Export datatype is empty"
        )
    
    # Extract optional parameters
    projection = None
    if config.get("HAS_PROJECTION_TO_EXPORT", False):
        proj_wkt = config.get("PROJECTION_TO_EXPORT")
        if proj_wkt:
            crs = QgsCoordinateReferenceSystem()
            crs.createFromWkt(proj_wkt)
            if crs.isValid():
                projection = crs
            else:
                logger.warning(f"Invalid CRS from WKT: {proj_wkt[:100]}...")
    
    styles = None
    if config.get("HAS_STYLES_TO_EXPORT", False):
        styles_raw = config.get("STYLES_TO_EXPORT")
        if styles_raw:
            styles = styles_raw.lower()
    
    # Default output folder from environment
    output_folder = None
    if env_vars and "PATH_ABSOLUTE_PROJECT" in env_vars:
        output_folder = env_vars["PATH_ABSOLUTE_PROJECT"]
    
    if config.get("HAS_OUTPUT_FOLDER_TO_EXPORT", False):
        folder = config.get("OUTPUT_FOLDER_TO_EXPORT")
        if folder:
            output_folder = folder
    
    if not output_folder:
        return ExportValidationResult(
            valid=False,
            error_message="No output folder specified"
        )
    
    zip_path = None
    if config.get("HAS_ZIP_TO_EXPORT", False):
        zip_path = config.get("ZIP_TO_EXPORT")
    
    # Batch export flags
    batch_output_folder = config.get("BATCH_OUTPUT_FOLDER", False)
    batch_zip = config.get("BATCH_ZIP", False)
    
    # Debug logging
    logger.debug(f"Export validation: {len(layers)} layers, {datatype}, {output_folder}")
    logger.debug(f"Batch modes - folder: {batch_output_folder}, zip: {batch_zip}")
    
    return ExportValidationResult(
        valid=True,
        layers=layers,
        projection=projection,
        styles=styles,
        datatype=datatype,
        output_folder=output_folder,
        zip_path=zip_path,
        batch_output_folder=batch_output_folder,
        batch_zip=batch_zip
    )
