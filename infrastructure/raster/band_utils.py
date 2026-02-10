"""
Raster Band Utilities.

Functions for querying band information and applying band compositions
(multi-band color rendering, single-band gray, preset compositions).

Thread Safety:
    - get_band_info() is thread-safe: creates layers from URI.
    - apply_band_composition() and apply_single_band() operate on layer objects
      and MUST be called from the main thread only (they modify QgsMapLayer rendering).

Phase 2: Band information + composition presets.
"""
import logging
from typing import Dict, List, Optional

from qgis.core import (
    QgsMultiBandColorRenderer,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsSingleBandGrayRenderer,
)

logger = logging.getLogger(__name__)


# ================================================================
# Preset Band Compositions
# ================================================================

# Common band compositions for multi-spectral rasters.
# Keys are preset names, values are dicts with:
#   - label: Human-readable label (for i18n, use self.tr() in UI layer)
#   - red, green, blue: 1-based band numbers
#   - description: Short description
#
# Note: Band numbers assume standard satellite band ordering.
# Sentinel-2 L2A (10m): B2=Blue, B3=Green, B4=Red, B8=NIR
# Landsat 8/9: B2=Blue, B3=Green, B4=Red, B5=NIR, B6=SWIR1, B7=SWIR2
PRESET_COMPOSITIONS: Dict[str, Dict] = {
    "natural_color": {
        "label": "Natural Color (RGB)",
        "red": 1,
        "green": 2,
        "blue": 3,
        "description": "True color composite using bands 1-2-3 (R-G-B)",
    },
    "false_color_irc": {
        "label": "False Color (IRC)",
        "red": 4,
        "green": 1,
        "blue": 2,
        "description": "Infrared composite: NIR-Red-Green. Vegetation appears red.",
    },
    "ndvi_false_color": {
        "label": "NDVI False Color",
        "red": 4,
        "green": 3,
        "blue": 2,
        "description": "NIR-Green-Blue. Healthy vegetation appears bright.",
    },
    "swir_composite": {
        "label": "SWIR Composite",
        "red": 6,
        "green": 4,
        "blue": 2,
        "description": "SWIR1-NIR-Blue. Urban and bare soil contrast.",
    },
    "agriculture": {
        "label": "Agriculture",
        "red": 5,
        "green": 4,
        "blue": 2,
        "description": "SWIR-NIR-Blue. Crop health monitoring.",
    },
}


def get_band_info(raster_uri: str) -> Optional[List[Dict]]:
    """Extract per-band information from a raster layer.

    Thread-safe: creates the layer from URI.

    Args:
        raster_uri: URI/path of the raster layer.

    Returns:
        List of dicts, one per band, with keys:
            - number: int (1-based band number)
            - name: str (band description/name)
            - data_type: str (e.g. "Float32", "Byte")
            - min: float or None
            - max: float or None
            - nodata: float or None
        Returns None if layer is invalid.
    """
    raster = QgsRasterLayer(raster_uri, "temp_raster_band_info")
    if not raster.isValid():
        logger.error(f"Invalid raster layer for band info: {raster_uri}")
        return None

    provider = raster.dataProvider()
    if provider is None:
        logger.error(f"No data provider for raster: {raster_uri}")
        return None

    band_count = raster.bandCount()
    bands = []

    for b in range(1, band_count + 1):
        band_dict = {
            "number": b,
            "name": provider.generateBandName(b),
            "data_type": _data_type_to_string(provider.dataType(b)),
            "min": None,
            "max": None,
            "nodata": None,
        }

        # Compute min/max stats
        try:
            stats = provider.bandStatistics(
                b,
                QgsRasterBandStats.Min | QgsRasterBandStats.Max,
            )
            band_dict["min"] = stats.minimumValue
            band_dict["max"] = stats.maximumValue
        except Exception as e:
            logger.warning(f"Could not compute stats for band {b}: {e}")

        # NoData
        try:
            if provider.sourceHasNoDataValue(b):
                band_dict["nodata"] = provider.sourceNoDataValue(b)
        except Exception:
            pass

        bands.append(band_dict)

    logger.debug(f"Band info extracted: {band_count} bands from {raster_uri}")
    return bands


def apply_band_composition(
    layer: QgsRasterLayer,
    red_band: int,
    green_band: int,
    blue_band: int,
) -> bool:
    """Apply a multi-band color composition to a raster layer.

    MAIN THREAD ONLY: modifies the layer's renderer.

    Args:
        layer: QgsRasterLayer to modify.
        red_band: 1-based band number for the red channel.
        green_band: 1-based band number for the green channel.
        blue_band: 1-based band number for the blue channel.

    Returns:
        True if successful, False otherwise.
    """
    if layer is None or not layer.isValid():
        logger.error("Cannot apply composition: invalid layer")
        return False

    band_count = layer.bandCount()
    for name, num in [("red", red_band), ("green", green_band), ("blue", blue_band)]:
        if num < 1 or num > band_count:
            logger.error(
                f"Band {name}={num} out of range [1, {band_count}]"
            )
            return False

    try:
        renderer = QgsMultiBandColorRenderer(
            layer.dataProvider(),
            red_band,
            green_band,
            blue_band,
        )
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        logger.info(
            f"Applied multi-band composition: R={red_band}, G={green_band}, "
            f"B={blue_band} on {layer.name()}"
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to apply band composition: {e}", exc_info=True
        )
        return False


def apply_single_band(
    layer: QgsRasterLayer,
    band: int,
) -> bool:
    """Apply a single-band gray renderer to a raster layer.

    MAIN THREAD ONLY: modifies the layer's renderer.

    Args:
        layer: QgsRasterLayer to modify.
        band: 1-based band number to display.

    Returns:
        True if successful, False otherwise.
    """
    if layer is None or not layer.isValid():
        logger.error("Cannot apply single band: invalid layer")
        return False

    band_count = layer.bandCount()
    if band < 1 or band > band_count:
        logger.error(
            f"Band {band} out of range [1, {band_count}]"
        )
        return False

    try:
        renderer = QgsSingleBandGrayRenderer(
            layer.dataProvider(),
            band,
        )
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        logger.info(
            f"Applied single-band gray: band={band} on {layer.name()}"
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to apply single band renderer: {e}", exc_info=True
        )
        return False


def apply_preset_composition(
    layer: QgsRasterLayer,
    preset_name: str,
) -> bool:
    """Apply a preset band composition to a raster layer.

    MAIN THREAD ONLY.

    Args:
        layer: QgsRasterLayer to modify.
        preset_name: Key from PRESET_COMPOSITIONS dict.

    Returns:
        True if successful, False otherwise.
    """
    preset = PRESET_COMPOSITIONS.get(preset_name)
    if preset is None:
        logger.error(
            f"Unknown preset: {preset_name}. "
            f"Available: {list(PRESET_COMPOSITIONS.keys())}"
        )
        return False

    return apply_band_composition(
        layer,
        red_band=preset["red"],
        green_band=preset["green"],
        blue_band=preset["blue"],
    )


def get_preset_names() -> List[str]:
    """Return list of available preset composition names."""
    return list(PRESET_COMPOSITIONS.keys())


def get_preset_label(preset_name: str) -> str:
    """Return the human-readable label for a preset composition."""
    preset = PRESET_COMPOSITIONS.get(preset_name)
    if preset is None:
        return preset_name
    return preset.get("label", preset_name)


# ================================================================
# Internal Helpers
# ================================================================

def _data_type_to_string(data_type: int) -> str:
    """Convert QGIS raster data type enum to human-readable string.

    Args:
        data_type: Qgis.DataType enum value.

    Returns:
        String representation like "Float32", "Int16", etc.
    """
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
