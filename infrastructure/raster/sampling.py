"""
Raster Sampling Infrastructure.

Low-level functions for sampling raster values at vector feature locations.
All functions are thread-safe: they create layers from URIs, never accept
QgsLayer objects directly.

Thread Safety Contract:
    - ALL layer objects are created from URI strings within each function
    - NO QgsMapLayer references are passed in or stored
    - Vector geometries are reprojected to raster CRS before sampling
    - Functions support cancellation via QgsFeedback

CRS Contract:
    - Vector features are always reprojected to raster CRS
    - Uses QgsCoordinateTransform for on-the-fly transformation

Phase 1: Point-based sampling (centroid, pointOnSurface).
Phase 3+: Mean-under-polygon via QgsZonalStatistics on temp memory layer.
"""
import logging
from typing import Dict, Optional, Tuple

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)

logger = logging.getLogger(__name__)


def sample_raster_at_point(
    raster_uri: str,
    point: QgsPointXY,
    band: int = 1,
) -> Optional[float]:
    """Sample a single raster value at a given point.

    This is the atomic sampling operation. Higher-level functions
    delegate to this for each feature.

    Args:
        raster_uri: URI/path of the raster layer.
        point: Point coordinates in raster CRS (caller must ensure correct CRS).
        band: 1-based band number to sample.

    Returns:
        The raster value at the point, or None if NoData or outside extent.
    """
    raster = QgsRasterLayer(raster_uri, "temp_raster_sample")
    if not raster.isValid():
        logger.error(f"Invalid raster layer from URI: {raster_uri}")
        return None

    provider = raster.dataProvider()
    if provider is None:
        logger.error(f"No data provider for raster: {raster_uri}")
        return None

    result = provider.sample(point, band)
    # provider.sample() returns (value, is_valid) tuple
    if len(result) >= 2 and result[1]:
        return float(result[0])
    return None


def sample_raster_for_features(
    raster_uri: str,
    vector_uri: str,
    band: int = 1,
    method: str = "point_on_surface",
    feedback=None,
) -> Dict[int, Optional[float]]:
    """Sample raster values at all features in a vector layer.

    Thread-safe: creates both layers from URIs internally.
    CRS-safe: reprojects vector geometries to raster CRS.

    Args:
        raster_uri: URI/path of the raster layer.
        vector_uri: URI/path of the vector layer.
        band: 1-based band number to sample.
        method: Sampling method string matching SamplingMethod enum values:
            - "centroid": Use geometry centroid (fast but may fall outside concave polygons).
            - "point_on_surface": Guaranteed inside polygon (default, recommended).
            - "mean_under_polygon": NOT YET IMPLEMENTED (Phase 3).
        feedback: Optional QgsFeedback for cancellation support.

    Returns:
        Dict mapping feature ID -> sampled raster value (None for NoData/errors).

    Raises:
        ValueError: If raster or vector layers are invalid.
        NotImplementedError: If method is "mean_under_polygon" (Phase 3).
    """
    if method == "mean_under_polygon":
        raise NotImplementedError(
            "mean_under_polygon sampling requires QgsZonalStatistics (Phase 3). "
            "Use 'point_on_surface' or 'centroid' instead."
        )

    # -- 1. Create layers from URI (thread-safe) --
    raster = QgsRasterLayer(raster_uri, "temp_raster_sampling")
    if not raster.isValid():
        raise ValueError(f"Invalid raster layer: {raster_uri}")

    vector = QgsVectorLayer(vector_uri, "temp_vector_sampling", "ogr")
    if not vector.isValid():
        # Try other providers (memory, postgres, etc.)
        vector = QgsVectorLayer(vector_uri, "temp_vector_sampling")
        if not vector.isValid():
            raise ValueError(f"Invalid vector layer: {vector_uri}")

    raster_provider = raster.dataProvider()
    if raster_provider is None:
        raise ValueError(f"No data provider for raster: {raster_uri}")

    # -- 2. Setup CRS transform (vector -> raster) --
    vector_crs = vector.crs()
    raster_crs = raster.crs()
    needs_transform = vector_crs != raster_crs

    transform = None
    if needs_transform:
        transform = QgsCoordinateTransform(
            vector_crs, raster_crs, QgsProject.instance()
        )
        logger.debug(
            f"CRS transform: {vector_crs.authid()} -> {raster_crs.authid()}"
        )

    # -- 3. Iterate features and sample --
    results: Dict[int, Optional[float]] = {}
    total_features = vector.featureCount()
    processed = 0

    request = QgsFeatureRequest()
    # We only need geometry, not attributes, for sampling
    request.setNoAttributes()

    for feature in vector.getFeatures(request):
        # Check cancellation
        if feedback is not None and feedback.isCanceled():
            logger.info("Raster sampling cancelled by user")
            break

        fid = feature.id()
        geom = feature.geometry()

        if geom is None or geom.isEmpty():
            results[fid] = None
            processed += 1
            continue

        # Extract sample point based on method
        sample_point = _extract_sample_point(geom, method)
        if sample_point is None:
            results[fid] = None
            processed += 1
            continue

        # Reproject to raster CRS if needed
        if needs_transform and transform is not None:
            try:
                sample_geom = QgsGeometry.fromPointXY(sample_point)
                sample_geom.transform(transform)
                sample_point = sample_geom.asPoint()
            except Exception as e:
                logger.warning(f"CRS transform failed for feature {fid}: {e}")
                results[fid] = None
                processed += 1
                continue

        # Sample the raster
        try:
            result = raster_provider.sample(sample_point, band)
            if len(result) >= 2 and result[1]:
                results[fid] = float(result[0])
            else:
                results[fid] = None
        except Exception as e:
            logger.warning(f"Sampling failed for feature {fid}: {e}")
            results[fid] = None

        processed += 1

        # Report progress periodically
        if feedback is not None and total_features > 0 and processed % 100 == 0:
            progress_pct = (processed / total_features) * 100
            feedback.setProgress(progress_pct)

    logger.info(
        f"Raster sampling complete: {processed}/{total_features} features, "
        f"band={band}, method={method}"
    )
    return results


def get_raster_info(raster_uri: str) -> Optional[dict]:
    """Extract metadata from a raster layer.

    Thread-safe: creates the layer from URI.

    Args:
        raster_uri: URI/path of the raster layer.

    Returns:
        Dict with raster metadata, or None if layer is invalid.
        Keys: name, width, height, band_count, crs_authid, crs_description,
              extent, pixel_size_x, pixel_size_y, nodata_values, data_types,
              is_cog, format_name.
    """
    raster = QgsRasterLayer(raster_uri, "temp_raster_info")
    if not raster.isValid():
        logger.error(f"Invalid raster layer for info: {raster_uri}")
        return None

    provider = raster.dataProvider()
    if provider is None:
        return None

    extent = raster.extent()
    crs = raster.crs()
    band_count = raster.bandCount()

    # Collect per-band info
    nodata_values = []
    data_types = []
    band_names = []
    for b in range(1, band_count + 1):
        # NoData
        if provider.sourceHasNoDataValue(b):
            nodata_values.append(provider.sourceNoDataValue(b))
        else:
            nodata_values.append(None)
        # Data type name
        try:
            from qgis.core import Qgis
            dtype = provider.dataType(b)
            dtype_name = _data_type_to_string(dtype)
        except Exception:
            dtype_name = "Unknown"
        data_types.append(dtype_name)
        # Band name (description)
        band_names.append(provider.generateBandName(b))

    # Pixel size
    pixel_x = raster.rasterUnitsPerPixelX()
    pixel_y = raster.rasterUnitsPerPixelY()

    # Detect COG (Cloud-Optimized GeoTIFF) from metadata
    is_cog = _detect_cog(provider)

    # Format name from provider
    format_name = ""
    try:
        # Provider description (e.g. "GeoTIFF", "JPEG2000")
        desc = provider.description()
        if desc:
            format_name = desc
    except Exception:
        pass

    return {
        "name": raster.name(),
        "width": raster.width(),
        "height": raster.height(),
        "band_count": band_count,
        "band_names": band_names,
        "crs_authid": crs.authid() if crs.isValid() else "Unknown",
        "crs_description": crs.description() if crs.isValid() else "Unknown",
        "extent": {
            "xmin": extent.xMinimum(),
            "ymin": extent.yMinimum(),
            "xmax": extent.xMaximum(),
            "ymax": extent.yMaximum(),
        },
        "pixel_size_x": pixel_x,
        "pixel_size_y": pixel_y,
        "nodata_values": nodata_values,
        "data_types": data_types,
        "is_cog": is_cog,
        "format_name": format_name,
    }


def _extract_sample_point(geom: QgsGeometry, method: str) -> Optional[QgsPointXY]:
    """Extract a sample point from a geometry using the specified method.

    Args:
        geom: Source geometry (any type).
        method: "centroid" or "point_on_surface".

    Returns:
        QgsPointXY for sampling, or None if extraction fails.
    """
    try:
        if method == "centroid":
            pt_geom = geom.centroid()
        else:
            # Default: point_on_surface (guaranteed inside polygon)
            pt_geom = geom.pointOnSurface()

        if pt_geom is None or pt_geom.isEmpty():
            # Fallback: try centroid if pointOnSurface fails
            pt_geom = geom.centroid()

        if pt_geom is not None and not pt_geom.isEmpty():
            return pt_geom.asPoint()
    except Exception as e:
        logger.warning(f"Failed to extract sample point ({method}): {e}")

    return None


def _detect_cog(provider) -> bool:
    """Detect if a raster is a Cloud-Optimized GeoTIFF.

    Heuristic: checks GDAL metadata for COG-specific indicators.

    Args:
        provider: QgsRasterDataProvider instance.

    Returns:
        True if COG is detected, False otherwise.
    """
    try:
        # Check for LAYOUT=COG in creation options or metadata
        metadata = provider.htmlMetadata()
        if metadata:
            metadata_lower = metadata.lower()
            if "cog" in metadata_lower or "cloud-optimized" in metadata_lower:
                return True
            # Check for overview presence + tiled structure (COG indicators)
            if "overview" in metadata_lower and "tiled" in metadata_lower:
                return True
    except Exception:
        pass
    return False


def _data_type_to_string(data_type: int) -> str:
    """Convert QGIS raster data type enum to human-readable string.

    Args:
        data_type: Qgis.DataType enum value.

    Returns:
        String representation like "Float32", "Int16", etc.
    """
    # Qgis.DataType values (QGIS 3.x)
    type_map = {
        0: "Unknown",
        1: "Byte",
        2: "UInt16",
        3: "Int16",
        4: "UInt32",
        5: "Int32",
        6: "Float32",
        7: "Float64",
        8: "CInt16",
        9: "CInt32",
        10: "CFloat32",
        11: "CFloat64",
        12: "ARGB32",
        13: "ARGB32_Premultiplied",
    }
    return type_map.get(data_type, f"Type({data_type})")
