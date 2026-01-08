# -*- coding: utf-8 -*-
"""
FilterMate Export Task - ARCH-047

Async task for exporting filtered data.
Supports multiple export formats.

Part of Phase 4 Task Refactoring.

Features:
- Multi-format export (GPKG, Shapefile, GeoJSON)
- Filtered feature export
- Progress reporting

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Tuple, Callable
from pathlib import Path

from .base_task import BaseFilterMateTask, TaskResult

logger = logging.getLogger('FilterMate.Tasks.Export')


class ExportTask(BaseFilterMateTask):
    """
    Async task for data export.

    Exports filtered layer data to various formats
    (GeoPackage, Shapefile, GeoJSON, etc.)

    Example:
        task = ExportTask(
            layer_id="layer_123",
            output_path="/path/to/output.gpkg",
            feature_ids=(1, 2, 3, 4, 5)
        )
        QgsApplication.taskManager().addTask(task)
    """

    # Supported export formats
    FORMATS = {
        '.gpkg': 'GPKG',
        '.shp': 'ESRI Shapefile',
        '.geojson': 'GeoJSON',
        '.json': 'GeoJSON',
        '.kml': 'KML',
        '.csv': 'CSV',
        '.gml': 'GML',
    }

    def __init__(
        self,
        layer_id: str,
        output_path: str,
        output_format: Optional[str] = None,
        feature_ids: Optional[Tuple[int, ...]] = None,
        include_styles: bool = False,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize export task.

        Args:
            layer_id: Layer ID to export
            output_path: Output file path
            output_format: Output format (auto-detected from extension if None)
            feature_ids: Optional feature IDs to export (None = all)
            include_styles: Include layer styles in export
            on_complete: Success callback
            on_error: Error callback
            on_progress: Progress callback
        """
        super().__init__(
            description=f"Exporting to {Path(output_path).name}",
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress
        )

        self._layer_id = layer_id
        self._output_path = Path(output_path)
        self._feature_ids = feature_ids
        self._include_styles = include_styles

        # Detect format from extension if not specified
        if output_format:
            self._output_format = output_format
        else:
            ext = self._output_path.suffix.lower()
            self._output_format = self.FORMATS.get(ext, 'GPKG')

        self._features_exported = 0

    def _execute(self) -> TaskResult:
        """Execute export operation."""
        try:
            from qgis.core import (
                QgsProject, QgsVectorLayer, QgsVectorFileWriter,
                QgsCoordinateTransformContext, QgsFeatureRequest
            )

            self.report_progress(0, 100, "Loading layer...")

            layer = QgsProject.instance().mapLayer(self._layer_id)
            if not layer or not isinstance(layer, QgsVectorLayer):
                return TaskResult.error_result("Layer not found or not a vector layer")

            self.report_progress(10, 100, "Preparing export...")

            # Create output directory if needed
            self._output_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare options
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = self._output_format
            options.fileEncoding = "UTF-8"

            # Filter features if IDs provided
            if self._feature_ids:
                options.filterExtent = None  # Clear any extent filter

                # For filtered export, we need to use subset or request
                self.report_progress(20, 100, f"Preparing {len(self._feature_ids)} features...")

                # Create a feature request to filter
                request = QgsFeatureRequest()
                request.setFilterFids(list(self._feature_ids))

                # Count features for progress
                feature_count = len(self._feature_ids)
            else:
                feature_count = layer.featureCount()

            self.report_progress(30, 100, f"Exporting {feature_count} features...")

            # Get transform context
            transform_context = QgsCoordinateTransformContext()

            # Write file
            if self._feature_ids:
                # Export with feature filter - need to use different approach
                error, error_msg = self._export_filtered(
                    layer, self._output_path, options, self._feature_ids
                )
            else:
                # Export all features
                error, error_msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    str(self._output_path),
                    transform_context,
                    options
                )

            self.report_progress(90, 100, "Finalizing...")

            if error != QgsVectorFileWriter.NoError:
                return TaskResult.error_result(f"Export failed: {error_msg}")

            self.report_progress(100, 100, "Export complete")

            return TaskResult.success_result(
                data={
                    'output_path': str(self._output_path),
                    'format': self._output_format,
                    'features_exported': feature_count
                },
                metrics={
                    'features_exported': feature_count,
                    'file_size_bytes': self._output_path.stat().st_size if self._output_path.exists() else 0
                }
            )

        except Exception as e:
            logger.exception(f"Export failed: {e}")
            return TaskResult.error_result(str(e))

    def _export_filtered(
        self,
        layer,
        output_path: Path,
        options,
        feature_ids: Tuple[int, ...]
    ) -> Tuple[int, str]:
        """
        Export only filtered features.

        Creates a temporary subset and exports.
        """
        from qgis.core import (
            QgsVectorFileWriter, QgsCoordinateTransformContext
        )

        # Save original subset string
        original_subset = layer.subsetString()

        try:
            # Build feature ID filter
            if len(feature_ids) > 0:
                pk_field = self._get_pk_field(layer)
                ids_str = ','.join(str(fid) for fid in feature_ids)
                layer.setSubsetString(f'"{pk_field}" IN ({ids_str})')

            # Export
            transform_context = QgsCoordinateTransformContext()
            error, error_msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                str(output_path),
                transform_context,
                options
            )

            self._features_exported = len(feature_ids)
            return error, error_msg

        finally:
            # Restore original subset
            layer.setSubsetString(original_subset)

    def _get_pk_field(self, layer) -> str:
        """Get primary key field name."""
        try:
            pk_attrs = layer.primaryKeyAttributes()
            if pk_attrs:
                return layer.fields()[pk_attrs[0]].name()
        except Exception:
            pass
        return "fid"

    @property
    def features_exported(self) -> int:
        """Get number of features exported."""
        return self._features_exported


class BatchExportTask(BaseFilterMateTask):
    """
    Export multiple layers in batch.

    Exports each layer to a separate file.
    """

    def __init__(
        self,
        exports: list,  # List of (layer_id, output_path, feature_ids) tuples
        output_format: str = "GPKG",
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[TaskResult], None]] = None
    ):
        """
        Initialize batch export task.

        Args:
            exports: List of (layer_id, output_path, feature_ids) tuples
            output_format: Output format for all exports
            on_complete: Success callback
            on_error: Error callback
        """
        super().__init__(
            description=f"Batch export of {len(exports)} layers",
            on_complete=on_complete,
            on_error=on_error
        )

        self._exports = exports
        self._output_format = output_format
        self._successful = 0
        self._failed = 0

    def _execute(self) -> TaskResult:
        """Execute batch export."""
        from qgis.core import (
            QgsProject, QgsVectorLayer, QgsVectorFileWriter,
            QgsCoordinateTransformContext
        )

        total = len(self._exports)
        results = []

        for i, (layer_id, output_path, feature_ids) in enumerate(self._exports):
            if self.check_cancelled():
                return TaskResult.cancelled_result()

            self.report_progress(i, total, f"Exporting layer {i+1}/{total}")

            try:
                layer = QgsProject.instance().mapLayer(layer_id)
                if not isinstance(layer, QgsVectorLayer):
                    self._failed += 1
                    results.append((layer_id, False, "Layer not found"))
                    continue

                # Create output directory
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                # Export
                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = self._output_format
                options.fileEncoding = "UTF-8"

                transform_context = QgsCoordinateTransformContext()
                error, error_msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    str(output_path),
                    transform_context,
                    options
                )

                if error == QgsVectorFileWriter.NoError:
                    self._successful += 1
                    results.append((layer_id, True, output_path))
                else:
                    self._failed += 1
                    results.append((layer_id, False, error_msg))

            except Exception as e:
                self._failed += 1
                results.append((layer_id, False, str(e)))

        self.report_progress(total, total, "Complete")

        return TaskResult(
            success=self._failed == 0,
            status=TaskStatus.COMPLETED if self._failed == 0 else TaskStatus.FAILED,
            data={
                'results': results,
                'successful': self._successful,
                'failed': self._failed
            }
        )


# Import TaskStatus here to avoid circular import
from .base_task import TaskStatus
