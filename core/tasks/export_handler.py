"""
Export Handler for FilterEngineTask

Handles all export operations including standard, batch, streaming, and ZIP modes.
Extracted from FilterEngineTask as part of the C1 God Object decomposition (Phase 3).

This handler manages:
- Export parameter validation
- Standard single/multi-layer export (GPKG, SHP, GeoJSON, etc.)
- Batch export to folder or ZIP
- Streaming export for large datasets
- Style export (QML, SLD, LYRX)

Location: core/tasks/export_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    All methods are designed to be called from worker threads. They do not
    access QGIS UI elements directly. Progress and description updates are
    communicated via callback functions.
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from ...infrastructure.logging import setup_logger
from ...infrastructure.streaming import StreamingExporter, StreamingConfig
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.Export',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)


class ExportHandler:
    """Handles all export operations for FilterEngineTask.

    Encapsulates export logic previously embedded in FilterEngineTask,
    receiving all dependencies explicitly via method parameters.

    Example:
        >>> handler = ExportHandler()
        >>> result = handler.execute_exporting(
        ...     task_parameters=params,
        ...     project=QgsProject.instance(),
        ...     set_progress=task.setProgress,
        ...     set_description=task.setDescription,
        ...     is_canceled=task.isCanceled,
        ... )
    """

    def validate_export_parameters(
        self,
        task_parameters: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Validate and extract export parameters from task configuration.

        Args:
            task_parameters: Task configuration dict

        Returns:
            dict: Export configuration or None if validation fails
        """
        from ..export import validate_export_parameters

        result = validate_export_parameters(task_parameters, ENV_VARS)
        if result.valid:
            return {
                'layers': result.layers,
                'projection': result.projection,
                'styles': result.styles,
                'datatype': result.datatype,
                'output_folder': result.output_folder,
                'zip_path': result.zip_path,
                'batch_output_folder': result.batch_output_folder,
                'batch_zip': result.batch_zip,
            }
        else:
            logger.error(result.error_message)
            return None

    def get_layer_by_name(self, project: Any, layer_name: str) -> Optional[Any]:
        """Get layer object from project by name.

        Args:
            project: QgsProject instance
            layer_name: Name of the layer to find

        Returns:
            QgsVectorLayer or None if not found
        """
        layers_found = project.mapLayersByName(layer_name)
        if layers_found:
            return layers_found[0]
        logger.warning(f"Layer '{layer_name}' not found in project")
        return None

    def save_layer_style(
        self,
        layer: Any,
        output_path: str,
        style_format: str,
        datatype: str,
    ) -> None:
        """Save layer style in specified format.

        Args:
            layer: QgsVectorLayer
            output_path: Output file path
            style_format: Style format (QML, SLD, etc.)
            datatype: Export format
        """
        from ..export import save_layer_style
        save_layer_style(layer, output_path, style_format, datatype)

    def save_layer_style_lyrx(self, layer: Any, output_path: str) -> None:
        """Save layer style in LYRX format.

        Args:
            layer: QgsVectorLayer
            output_path: Output file path
        """
        from ..export.style_exporter import StyleExporter, StyleFormat
        exporter = StyleExporter()
        exporter.save_style(layer, output_path, StyleFormat.LYRX)

    def calculate_total_features(self, layers: List, project: Any) -> int:
        """Calculate total feature count across all layers.

        Args:
            layers: List of layer info dicts or layer names
            project: QgsProject instance

        Returns:
            int: Total feature count
        """
        total = 0
        for layer_info in layers:
            layer_name = layer_info['layer_name'] if isinstance(layer_info, dict) else layer_info
            layer = self.get_layer_by_name(project, layer_name)
            if layer:
                total += layer.featureCount()
        return total

    def execute_exporting(
        self,
        task_parameters: Dict[str, Any],
        project: Any,
        set_progress: Callable[[float], None],
        set_description: Callable[[str], None],
        is_canceled: Callable[[], bool],
    ) -> tuple:
        """Export selected layers to various formats.

        Supports multiple export modes:
        - Standard: Single file with all layers (GPKG, GeoJSON)
        - Batch folder: One file per layer in output folder
        - Batch ZIP: One ZIP archive per layer
        - Streaming: Memory-efficient export for large datasets

        Args:
            task_parameters: Task configuration dict
            project: QgsProject instance
            set_progress: Callback to update progress (0-100)
            set_description: Callback to update task description
            is_canceled: Callback to check if task was canceled

        Returns:
            tuple: (success: bool, message: str, error_details: Optional[str])
        """
        # Validate parameters
        export_config = self.validate_export_parameters(task_parameters)
        if not export_config:
            return False, 'Export configuration validation failed', None

        layers = export_config['layers']
        projection = export_config['projection']
        datatype = export_config['datatype']
        output_folder = export_config['output_folder']
        style_format = export_config['styles']
        zip_path = export_config['zip_path']
        batch_output_folder = export_config.get('batch_output_folder', False)
        batch_zip = export_config.get('batch_zip', False)
        save_styles = task_parameters["task"]['EXPORTING'].get("HAS_STYLES_TO_EXPORT", False)

        # Initialize exporters
        from ..export import BatchExporter, LayerExporter, sanitize_filename
        batch_exporter = BatchExporter(project=project)
        layer_exporter = LayerExporter(project=project)

        # Inject cancel check
        batch_exporter.is_canceled = is_canceled

        def progress_callback(percent):
            set_progress(percent)

        def description_callback(desc):
            set_description(desc)

        # BATCH MODE: One file per layer in folder
        if batch_output_folder:
            logger.info("Batch output folder mode enabled - delegating to BatchExporter")
            result = batch_exporter.export_to_folder(
                layers, output_folder, datatype,
                projection=projection,
                style_format=style_format,
                save_styles=save_styles,
                progress_callback=progress_callback,
                description_callback=description_callback
            )
            if result.success:
                message = f'Batch export: {result.exported_count} layer(s) exported to <a href="file:///{output_folder}">{output_folder}</a>'
            else:
                message = f'Batch export completed with errors:\n{result.get_summary()}'
            return result.success, message, getattr(result, 'error_details', None)

        # BATCH MODE: One ZIP per layer
        if batch_zip:
            logger.info("Batch ZIP mode enabled - delegating to BatchExporter")
            result = batch_exporter.export_to_zip(
                layers, output_folder, datatype,
                projection=projection,
                style_format=style_format,
                save_styles=save_styles,
                progress_callback=progress_callback,
                description_callback=description_callback
            )
            if result.success:
                message = f'Batch ZIP export: {result.exported_count} ZIP file(s) created in <a href="file:///{output_folder}">{output_folder}</a>'
            else:
                message = f'Batch ZIP export completed with errors:\n{result.get_summary()}'
            return result.success, message, getattr(result, 'error_details', None)

        # GPKG STANDARD MODE
        if datatype == 'GPKG':
            return self._export_gpkg(
                layers, output_folder, save_styles, zip_path,
                project, layer_exporter, batch_exporter, sanitize_filename
            )

        # STREAMING MODE: For large datasets (non-GPKG)
        streaming_config = task_parameters.get('config', {}).get('APP', {}).get('OPTIONS', {}).get('STREAMING_EXPORT', {})
        streaming_enabled = streaming_config.get('enabled', {}).get('value', True)
        feature_threshold = streaming_config.get('feature_threshold', {}).get('value', 10000)
        chunk_size = streaming_config.get('chunk_size', {}).get('value', 5000)

        if streaming_enabled:
            total_features = self.calculate_total_features(layers, project)
            if total_features >= feature_threshold:
                logger.info(f"Using STREAMING export mode ({total_features} features >= {feature_threshold} threshold)")
                success, message = self._export_with_streaming(
                    layers, output_folder, projection, datatype,
                    style_format, save_styles, chunk_size,
                    project, set_progress, set_description, is_canceled
                )
                if success and zip_path:
                    if BatchExporter.create_zip_archive(zip_path, output_folder):
                        message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'
                return success, message, None

        # STANDARD MODE: Single or multiple layers
        if not os.path.exists(output_folder):
            return False, f'Output path does not exist: {output_folder}', None

        export_success = False
        message = ''

        if len(layers) == 1:
            layer_name = layers[0]['layer_name'] if isinstance(layers[0], dict) else layers[0]
            logger.info(f"Single layer export - delegating to LayerExporter: {layer_name}")
            result = layer_exporter.export_single_layer(
                layer_name, output_folder, projection, datatype, style_format, save_styles
            )
            export_success = result.success
            if not result.success:
                message = result.error_message or 'Export failed'

        elif os.path.isdir(output_folder):
            logger.info(f"Multiple layers export - delegating to LayerExporter: {len(layers)} layers")
            from ..export import ExportConfig
            result = layer_exporter.export_multiple_to_directory(
                ExportConfig(
                    layers=layers,
                    output_path=output_folder,
                    datatype=datatype,
                    projection=projection,
                    style_format=style_format,
                    save_styles=save_styles
                )
            )
            export_success = result.success
            if not result.success:
                message = result.error_message or 'Export failed'
        else:
            return False, f'Invalid export configuration: {len(layers)} layers but output is not a directory', None

        if not export_success:
            return False, message, None

        if is_canceled():
            return False, 'Export cancelled by user', None

        # Create zip archive if requested
        zip_created = False
        if zip_path:
            zip_created = BatchExporter.create_zip_archive(zip_path, output_folder)
            if not zip_created:
                return False, 'Failed to create ZIP archive', None

        message = f'Layer(s) has been exported to <a href="file:///{output_folder}">{output_folder}</a>'
        if zip_created:
            message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'

        logger.info("Export completed successfully")
        return True, message, None

    def _export_gpkg(
        self,
        layers: List,
        output_folder: str,
        save_styles: bool,
        zip_path: Optional[str],
        project: Any,
        layer_exporter: Any,
        batch_exporter_class: Any,
        sanitize_filename_fn: Callable,
    ) -> tuple:
        """Handle GPKG export mode.

        Args:
            layers: List of layer info dicts or layer names
            output_folder: Output directory or .gpkg file path
            save_styles: Whether to save styles
            zip_path: Optional ZIP archive path
            project: QgsProject instance
            layer_exporter: LayerExporter instance
            batch_exporter_class: BatchExporter class (for create_zip_archive)
            sanitize_filename_fn: Function to sanitize filenames

        Returns:
            tuple: (success: bool, message: str, error_details: Optional[str])
        """
        if output_folder.lower().endswith('.gpkg'):
            gpkg_output_path = output_folder
            gpkg_dir = os.path.dirname(gpkg_output_path)
            if gpkg_dir and not os.path.exists(gpkg_dir):
                try:
                    os.makedirs(gpkg_dir)
                    logger.info(f"Created output directory: {gpkg_dir}")
                except OSError as e:
                    logger.error(f"Failed to create output directory: {e}")
                    return False, f'Failed to create output directory: {gpkg_dir}', None
        else:
            if not os.path.exists(output_folder):
                try:
                    os.makedirs(output_folder)
                except OSError as e:
                    logger.debug(f"Ignored in makedirs for export output: {e}")
                    return False, f'Failed to create output directory: {output_folder}', None

            project_title = project.title() if project.title() else None
            project_basename = project.baseName() if project.baseName() else None
            default_name = project_title or project_basename or 'export'
            default_name = sanitize_filename_fn(default_name)
            gpkg_output_path = os.path.join(output_folder, f"{default_name}.gpkg")

        logger.info(f"GPKG export - delegating to LayerExporter: {gpkg_output_path}")
        result = layer_exporter.export_to_gpkg(layers, gpkg_output_path, save_styles)

        if not result.success:
            return False, result.error_message or 'GPKG export failed', None

        message = f'Layer(s) exported to <a href="file:///{gpkg_output_path}">{gpkg_output_path}</a>'

        if zip_path:
            gpkg_dir = os.path.dirname(gpkg_output_path)
            if batch_exporter_class.create_zip_archive(zip_path, gpkg_dir):
                message += f' and Zip file has been exported to <a href="file:///{zip_path}">{zip_path}</a>'

        return True, message, None

    def _export_with_streaming(
        self,
        layers: List,
        output_folder: str,
        projection: Any,
        datatype: str,
        style_format: Optional[str],
        save_styles: bool,
        chunk_size: int,
        project: Any,
        set_progress: Callable,
        set_description: Callable,
        is_canceled: Callable,
    ) -> tuple:
        """Export layers using streaming for large datasets.

        Args:
            layers: List of layer info dicts or layer names
            output_folder: Output directory path
            projection: Target CRS
            datatype: Output format (GPKG, SHP, etc.)
            style_format: Style format (QML, SLD, etc.)
            save_styles: Whether to save styles
            chunk_size: Number of features per batch
            project: QgsProject instance
            set_progress: Progress callback
            set_description: Description callback
            is_canceled: Cancel check callback

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            config = StreamingConfig(batch_size=chunk_size)
            exporter = StreamingExporter(config)

            format_map = {
                'GPKG': 'gpkg', 'SHP': 'shp', 'GEOJSON': 'geojson',
                'GML': 'gml', 'KML': 'kml', 'CSV': 'csv'
            }
            export_format = format_map.get(datatype.upper(), datatype.lower())

            if not os.path.exists(output_folder):
                try:
                    os.makedirs(output_folder)
                    logger.info(f"Created output folder: {output_folder}")
                except OSError as e:
                    error_msg = f"Cannot create output folder '{output_folder}': {e}"
                    logger.error(error_msg)
                    return False, error_msg

            def progress_callback(progress):
                set_progress(int(progress.percent_complete))
                set_description(
                    f"Streaming export: {progress.features_processed}/{progress.total_features} features"
                )

            exported_count = 0
            failed_layers = []

            for layer_info in layers:
                layer_name = layer_info['layer_name'] if isinstance(layer_info, dict) else layer_info
                layer = self.get_layer_by_name(project, layer_name)

                if not layer:
                    logger.warning(f"Layer not found: {layer_name}")
                    failed_layers.append(f"{layer_name} (not found)")
                    continue

                # Determine output path
                ext_map = {'GPKG': 'gpkg', 'SHP': 'shp', 'GEOJSON': 'geojson'}
                ext = ext_map.get(datatype, datatype.lower())
                output_path = os.path.join(output_folder, f"{layer_name}.{ext}")

                logger.info(f"Streaming export: {layer_name} -> {output_path}")

                result = exporter.export_layer_streaming(
                    source_layer=layer,
                    output_path=output_path,
                    format=export_format,
                    progress_callback=progress_callback,
                    cancel_check=is_canceled
                )

                if not result.get('success', False):
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"Streaming export failed for {layer_name}: {error_msg}")
                    failed_layers.append(f"{layer_name} ({error_msg})")
                    continue

                exported_count += 1

                if save_styles and style_format:
                    self.save_layer_style(layer, output_path, style_format, datatype)

                if is_canceled():
                    logger.info("Export cancelled by user")
                    return False, "Export cancelled by user"

            if failed_layers:
                if exported_count > 0:
                    message = (
                        f"Partial export: {exported_count}/{len(layers)} layers exported. "
                        f"Failed: {', '.join(failed_layers[:3])}"
                    )
                    if len(failed_layers) > 3:
                        message += f" and {len(failed_layers) - 3} more"
                    logger.warning(message)
                    return True, message
                else:
                    message = (
                        f"Export failed for all {len(layers)} layers. "
                        f"Errors: {', '.join(failed_layers[:3])}"
                    )
                    if len(failed_layers) > 3:
                        message += f" and {len(failed_layers) - 3} more"
                    logger.error(message)
                    return False, message

            message = (
                f'Streaming export: {len(layers)} layer(s) exported to '
                f'<a href="file:///{output_folder}">{output_folder}</a>'
            )
            return True, message

        except Exception as e:  # catch-all safety net: streaming export must return error tuple
            error_msg = f"Streaming export error: {e}"
            logger.error(error_msg)
            return False, error_msg
