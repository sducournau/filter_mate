"""
Batch Exporter - Advanced batch export functionality

v4.0 EPIC-1 Phase E11: Migrated from filter_task.py batch export methods

Handles:
- Batch export to folder (one file per layer)
- Batch export to ZIP (one ZIP per layer)
- ZIP archive creation
- Progress tracking
- Error reporting with detailed summaries

Migrated from modules.tasks.filter_task.py (~400 lines)
Pattern: Strangler Fig migration from filter_task.py to dedicated service
"""

import os
import logging
import tempfile
import shutil
import zipfile
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsCoordinateReferenceSystem,
        QgsProject,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = None
    QgsCoordinateReferenceSystem = None
    QgsProject = None

from .layer_exporter import LayerExporter, ExportResult

logger = logging.getLogger('FilterMate.Export.Batch')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to handle special characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    import re
    # Replace em-dash and other special characters
    safe = filename.replace('—', '-').replace('–', '-')
    # Remove or replace other problematic characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', safe)
    return safe


@dataclass
class BatchExportResult:
    """Result of batch export operation."""
    
    success: bool
    """Overall success status (True only if all exports succeeded)."""
    
    exported_count: int = 0
    """Number of layers/files successfully exported."""
    
    failed_count: int = 0
    """Number of layers that failed to export."""
    
    skipped_count: int = 0
    """Number of layers skipped (not found)."""
    
    output_paths: List[str] = field(default_factory=list)
    """Paths to successfully exported files."""
    
    failed_layers: List[str] = field(default_factory=list)
    """Names of layers that failed with error messages."""
    
    skipped_layers: List[str] = field(default_factory=list)
    """Names of layers that were skipped."""
    
    error_details: Optional[str] = None
    """Detailed error message summary."""
    
    def get_summary(self) -> str:
        """
        Get human-readable summary of batch export results.
        
        Returns:
            Summary string suitable for user display
        """
        details = []
        
        if self.exported_count > 0:
            details.append(f"✓ {self.exported_count} file(s) exported successfully")
        
        if self.failed_count > 0:
            details.append(f"✗ {self.failed_count} layer(s) failed:")
            for failed in self.failed_layers[:5]:  # Limit to first 5
                details.append(f"  - {failed}")
            if len(self.failed_layers) > 5:
                details.append(f"  ... and {len(self.failed_layers) - 5} more (see logs)")
        
        if self.skipped_count > 0:
            skipped_names = ', '.join(self.skipped_layers[:3])
            details.append(f"⚠ {self.skipped_count} layer(s) not found: {skipped_names}")
            if len(self.skipped_layers) > 3:
                details.append(f"  ... and {len(self.skipped_layers) - 3} more")
        
        return "\n".join(details) if details else "No layers processed"


class BatchExporter:
    """
    Handles batch export operations for multiple layers.
    
    Supports:
    - Batch export to folder (one file per layer)
    - Batch export to ZIP archives (one ZIP per layer)
    - Progress tracking via callbacks
    - Detailed error reporting
    - Cancel support
    
    Example:
        exporter = BatchExporter(project)
        result = exporter.export_to_folder(
            layer_names=['layer1', 'layer2'],
            output_folder='/path/to/output',
            datatype='SHP',
            progress_callback=lambda p: print(f"Progress: {p}%")
        )
        print(result.get_summary())
    """
    
    # File extension mapping
    EXTENSION_MAP = {
        'GPKG': '.gpkg',
        'SHP': '.shp',
        'SHAPEFILE': '.shp',
        'ESRI SHAPEFILE': '.shp',
        'GEOJSON': '.geojson',
        'JSON': '.geojson',
        'GML': '.gml',
        'KML': '.kml',
        'CSV': '.csv',
        'XLSX': '.xlsx',
        'TAB': '.tab',
        'MAPINFO': '.tab',
        'DXF': '.dxf',
        'SQLITE': '.sqlite',
        'SPATIALITE': '.sqlite'
    }
    
    def __init__(self, project: Optional[QgsProject] = None):
        """
        Initialize batch exporter.
        
        Args:
            project: QgsProject instance or None to use current project
        """
        self.project = project or (QgsProject.instance() if QGIS_AVAILABLE else None)
        self.layer_exporter = LayerExporter(project)
        self._cancel_requested = False
    
    def request_cancel(self):
        """Request cancellation of current export operation."""
        self._cancel_requested = True
        logger.info("Batch export cancellation requested")
    
    def is_canceled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested
    
    def export_to_folder(
        self,
        layer_names: List[str],
        output_folder: str,
        datatype: str,
        projection: Optional[QgsCoordinateReferenceSystem] = None,
        style_format: Optional[str] = None,
        save_styles: bool = False,
        progress_callback: Optional[callable] = None,
        description_callback: Optional[callable] = None
    ) -> BatchExportResult:
        """
        Export multiple layers to folder (one file per layer).
        
        Args:
            layer_names: List of layer names to export
            output_folder: Output directory path
            datatype: Export format (e.g., 'SHP', 'GPKG')
            projection: Target CRS or None to use each layer's CRS
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            progress_callback: Optional callback(progress_percent: int)
            description_callback: Optional callback(description: str)
            
        Returns:
            BatchExportResult with detailed statistics
        """
        logger.info(f"Batch folder export: {len(layer_names)} layer(s) to {datatype} in {output_folder}")
        
        # Reset cancel flag
        self._cancel_requested = False
        
        # Ensure output directory exists
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
                logger.info(f"Created output directory: {output_folder}")
            except Exception as e:
                logger.error(f"Failed to create output directory: {e}")
                return BatchExportResult(
                    success=False,
                    error_details=f"Failed to create output directory: {str(e)}"
                )
        
        total_layers = len(layer_names)
        exported_paths = []
        failed_layers = []
        skipped_layers = []
        
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
            # Update progress
            if description_callback:
                description_callback(f"Batch export: layer {idx}/{total_layers}: {layer_name}")
            if progress_callback:
                progress_callback(int((idx / total_layers) * 100))
            
            # Get layer
            layer = self.layer_exporter.get_layer_by_name(layer_name)
            if not layer:
                logger.warning(f"Skipping layer '{layer_name}' (not found)")
                skipped_layers.append(layer_name)
                continue
            
            # Sanitize filename
            safe_filename = sanitize_filename(layer_name)
            file_extension = self.EXTENSION_MAP.get(datatype.upper(), f'.{datatype.lower()}')
            output_path = os.path.join(output_folder, f"{safe_filename}{file_extension}")
            
            # Export layer
            logger.info(f"Exporting layer '{layer_name}' to {output_path}")
            result = self.layer_exporter.export_single_layer(
                layer_name, output_path, projection, datatype, style_format, save_styles
            )
            
            if result.success:
                exported_paths.append(output_path)
                logger.info(f"Successfully exported '{layer_name}'")
            else:
                error_detail = f"{layer_name}: {result.error_message}" if result.error_message else layer_name
                failed_layers.append(error_detail)
                logger.error(f"Failed to export '{layer_name}': {result.error_message}")
            
            # Check for cancellation
            if self.is_canceled():
                logger.info("Batch folder export cancelled by user")
                return BatchExportResult(
                    success=False,
                    exported_count=len(exported_paths),
                    failed_count=len(failed_layers),
                    skipped_count=len(skipped_layers),
                    output_paths=exported_paths,
                    failed_layers=failed_layers,
                    skipped_layers=skipped_layers,
                    error_details=f"Export cancelled by user. Exported {len(exported_paths)}/{total_layers} layer(s)."
                )
        
        # Build result
        result = BatchExportResult(
            success=(len(failed_layers) == 0 and len(skipped_layers) == 0),
            exported_count=len(exported_paths),
            failed_count=len(failed_layers),
            skipped_count=len(skipped_layers),
            output_paths=exported_paths,
            failed_layers=failed_layers,
            skipped_layers=skipped_layers
        )
        
        if not result.success:
            result.error_details = result.get_summary()
        
        logger.info(f"Batch folder export completed: {result.exported_count}/{total_layers} successful")
        return result
    
    def export_to_zip(
        self,
        layer_names: List[str],
        output_folder: str,
        datatype: str,
        projection: Optional[QgsCoordinateReferenceSystem] = None,
        style_format: Optional[str] = None,
        save_styles: bool = False,
        progress_callback: Optional[callable] = None,
        description_callback: Optional[callable] = None
    ) -> BatchExportResult:
        """
        Export multiple layers to ZIP archives (one ZIP per layer).
        
        Args:
            layer_names: List of layer names to export
            output_folder: Output directory for ZIP files
            datatype: Export format (e.g., 'SHP', 'GPKG')
            projection: Target CRS or None to use each layer's CRS
            style_format: Style file format or None
            save_styles: Whether to save layer styles
            progress_callback: Optional callback(progress_percent: int)
            description_callback: Optional callback(description: str)
            
        Returns:
            BatchExportResult with detailed statistics
        """
        logger.info(f"Batch ZIP export: {len(layer_names)} layer(s) to {datatype} ZIPs in {output_folder}")
        
        # Reset cancel flag
        self._cancel_requested = False
        
        # Ensure output directory exists
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
                logger.info(f"Created output directory: {output_folder}")
            except Exception as e:
                logger.error(f"Failed to create output directory: {e}")
                return BatchExportResult(
                    success=False,
                    error_details=f"Failed to create output directory: {str(e)}"
                )
        
        total_layers = len(layer_names)
        exported_zips = []
        failed_layers = []
        skipped_layers = []
        
        for idx, layer_item in enumerate(layer_names, 1):
            # Handle both dict (layer info) and string (layer name) formats
            layer_name = layer_item['layer_name'] if isinstance(layer_item, dict) else layer_item
            
            # Update progress
            if description_callback:
                description_callback(f"Batch ZIP export: layer {idx}/{total_layers}: {layer_name}")
            if progress_callback:
                progress_callback(int((idx / total_layers) * 100))
            
            # Get layer
            layer = self.layer_exporter.get_layer_by_name(layer_name)
            if not layer:
                logger.warning(f"Skipping layer '{layer_name}' (not found)")
                skipped_layers.append(layer_name)
                continue
            
            # Sanitize filename
            safe_filename = sanitize_filename(layer_name)
            file_extension = self.EXTENSION_MAP.get(datatype.upper(), f'.{datatype.lower()}')
            
            # Create temporary directory for this layer's export
            temp_dir = tempfile.mkdtemp(prefix=f"fm_batch_{safe_filename}_")
            
            try:
                # Export layer to temporary directory
                temp_output = os.path.join(temp_dir, f"{safe_filename}{file_extension}")
                logger.info(f"Exporting layer '{layer_name}' to temp: {temp_output}")
                
                result = self.layer_exporter.export_single_layer(
                    layer_name, temp_output, projection, datatype, style_format, save_styles
                )
                
                if not result.success:
                    error_detail = f"{layer_name}: {result.error_message}" if result.error_message else layer_name
                    failed_layers.append(error_detail)
                    logger.error(f"Failed to export layer '{layer_name}': {result.error_message}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    continue
                
                # Create ZIP for this layer
                zip_path = os.path.join(output_folder, f"{safe_filename}.zip")
                logger.info(f"Creating ZIP archive: {zip_path} from {temp_dir}")
                
                if self.create_zip_archive(zip_path, temp_dir):
                    exported_zips.append(zip_path)
                    logger.info(f"Successfully created ZIP: {zip_path}")
                else:
                    error_detail = f"{layer_name}: Failed to create ZIP archive"
                    failed_layers.append(error_detail)
                    logger.error(f"Failed to create ZIP for '{layer_name}' at {zip_path}")
                
                # Clean up temporary directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
            except Exception as e:
                error_detail = f"{layer_name}: {str(e)}"
                failed_layers.append(error_detail)
                logger.error(f"Error during batch ZIP export of '{layer_name}': {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Check for cancellation
            if self.is_canceled():
                logger.info("Batch ZIP export cancelled by user")
                return BatchExportResult(
                    success=False,
                    exported_count=len(exported_zips),
                    failed_count=len(failed_layers),
                    skipped_count=len(skipped_layers),
                    output_paths=exported_zips,
                    failed_layers=failed_layers,
                    skipped_layers=skipped_layers,
                    error_details=f"Export cancelled by user. Created {len(exported_zips)}/{total_layers} ZIP files."
                )
        
        # Build result
        result = BatchExportResult(
            success=(len(failed_layers) == 0 and len(skipped_layers) == 0),
            exported_count=len(exported_zips),
            failed_count=len(failed_layers),
            skipped_count=len(skipped_layers),
            output_paths=exported_zips,
            failed_layers=failed_layers,
            skipped_layers=skipped_layers
        )
        
        if not result.success:
            result.error_details = result.get_summary()
        
        logger.info(f"Batch ZIP export completed: {result.exported_count}/{total_layers} successful")
        return result
    
    @staticmethod
    def create_zip_archive(zip_path: str, folder_to_zip: str) -> bool:
        """
        Create a ZIP archive of a folder.
        
        Args:
            zip_path: Output ZIP file path
            folder_to_zip: Folder to compress
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(folder_to_zip):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, folder_to_zip)
                        zipf.write(file_path, arcname)
                        logger.debug(f"Added to ZIP: {arcname}")
            
            logger.info(f"Successfully created ZIP archive: {zip_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create ZIP archive '{zip_path}': {e}")
            return False
