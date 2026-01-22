"""
Export Validator

v4.0 EPIC-1 Phase E1: Extracted from filter_task.py._validate_export_parameters()

Validates export configurations before execution.

IMPORTANT: Export is INDEPENDENT from "exploring" and QGIS selection.
====================================================================

Export validation checks:
- LAYERS_TO_EXPORT: layers selected via checkboxes in EXPORTING tab
- DATATYPE_TO_EXPORT: export format (GPKG, SHP, etc.)
- OUTPUT_FOLDER_TO_EXPORT: destination path

Export does NOT validate or use:
- current_layer from exploring tab
- selection expression from exploring
- QGIS selectedFeatures()
- Any filtering/exploring state

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
    
    logger.debug(f"Layers validation passed ({len(layers)} layers)")
    
    # Validate datatype
    has_datatype = config.get("HAS_DATATYPE_TO_EXPORT", False)
    logger.debug(f"HAS_DATATYPE_TO_EXPORT: {has_datatype}")
    
    if not has_datatype:
        logger.debug("No datatype specified")
        return ExportValidationResult(
            valid=False,
            error_message="No export datatype specified"
        )
    
    datatype = config.get("DATATYPE_TO_EXPORT")
    logger.debug(f"DATATYPE_TO_EXPORT: {datatype}")
    
    if not datatype:
        logger.debug("Datatype is empty")
        return ExportValidationResult(
            valid=False,
            error_message="Export datatype is empty"
        )
    
    logger.debug(f"Datatype validation passed: {datatype}")
    
    # Extract optional parameters
    projection = None
    if config.get("HAS_PROJECTION_TO_EXPORT", False):
        proj_wkt = config.get("PROJECTION_TO_EXPORT")
        logger.debug(f"PROJECTION_TO_EXPORT: {proj_wkt[:50] if proj_wkt else 'None'}...")
        if proj_wkt:
            crs = QgsCoordinateReferenceSystem()
            crs.createFromWkt(proj_wkt)
            if crs.isValid():
                projection = crs
                logger.debug(f"Projection: {crs.authid()}")
            else:
                logger.warning(f"Invalid CRS from WKT: {proj_wkt[:100]}...")
    
    styles = None
    if config.get("HAS_STYLES_TO_EXPORT", False):
        styles_raw = config.get("STYLES_TO_EXPORT")
        if styles_raw:
            styles = styles_raw.lower()
            logger.debug(f"Styles: {styles}")
    
    # Default output folder from environment
    output_folder = None
    logger.debug(f"env_vars available: {env_vars is not None}")
    if env_vars and "PATH_ABSOLUTE_PROJECT" in env_vars:
        output_folder = env_vars["PATH_ABSOLUTE_PROJECT"]
        logger.debug(f"Default output_folder from env: {output_folder}")
    
    has_output_folder = config.get("HAS_OUTPUT_FOLDER_TO_EXPORT", False)
    logger.debug(f"HAS_OUTPUT_FOLDER_TO_EXPORT: {has_output_folder}")
    
    if has_output_folder:
        folder = config.get("OUTPUT_FOLDER_TO_EXPORT")
        logger.debug(f"OUTPUT_FOLDER_TO_EXPORT: {folder}")
        if folder:
            output_folder = folder
    
    logger.debug(f"Final output_folder: {output_folder}")
    
    if not output_folder:
        logger.debug("No output folder specified!")
        return ExportValidationResult(
            valid=False,
            error_message="No output folder specified"
        )
    
    logger.debug(f"Output folder validation passed: {output_folder}")
    
    zip_path = None
    if config.get("HAS_ZIP_TO_EXPORT", False):
        zip_path = config.get("ZIP_TO_EXPORT")
        logger.debug(f"ZIP_TO_EXPORT: {zip_path}")
    
    # Batch export flags
    batch_output_folder = config.get("BATCH_OUTPUT_FOLDER", False)
    batch_zip = config.get("BATCH_ZIP", False)
    logger.debug(f"Batch modes - folder: {batch_output_folder}, zip: {batch_zip}")
    
    logger.info(f"Export validation PASSED: {len(layers)} layers, format={datatype}, output={output_folder}")
    
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
