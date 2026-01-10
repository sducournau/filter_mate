"""
Style Exporter

v4.0 EPIC-1 Phase E1: Extracted from filter_task.py style export methods

Handles layer style export to various formats (QML, SLD, LYRX).

Original source: modules/tasks/filter_task.py lines 9353-9548 (~200 lines)
"""

import os
import json
import logging
from enum import Enum
from typing import Optional, Any
from datetime import datetime

try:
    from qgis.core import QgsVectorLayer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = Any

logger = logging.getLogger('FilterMate.Export')


class StyleFormat(Enum):
    """Supported style export formats."""
    QML = "qml"         # QGIS style
    SLD = "sld"         # OGC Styled Layer Descriptor
    LYRX = "lyrx"       # ArcGIS Pro layer file


class StyleExporter:
    """
    Exports layer styles to various formats.
    
    Supports:
    - QML (QGIS native)
    - SLD (OGC standard)
    - LYRX (ArcGIS Pro)
    
    Example:
        exporter = StyleExporter()
        exporter.save_style(layer, "/path/to/output", StyleFormat.LYRX)
    """
    
    def __init__(self):
        """Initialize style exporter."""
        pass
    
    def save_style(
        self,
        layer: QgsVectorLayer,
        output_path: str,
        style_format: StyleFormat,
        datatype: Optional[str] = None
    ) -> bool:
        """
        Save layer style to file.
        
        Args:
            layer: QgsVectorLayer to export style from
            output_path: Base path for export (without extension)
            style_format: Style format to export
            datatype: Export datatype (to check if styles are supported)
            
        Returns:
            True if export succeeded, False otherwise
        """
        if not QGIS_AVAILABLE:
            logger.warning("QGIS not available - cannot export styles")
            return False
        
        # Skip for unsupported formats
        if datatype == 'XLSX':
            logger.debug(f"Skipping style export for XLSX format")
            return False
        
        if style_format == StyleFormat.LYRX:
            return self._save_lyrx(layer, output_path)
        elif style_format in (StyleFormat.QML, StyleFormat.SLD):
            return self._save_qgis_style(layer, output_path, style_format.value)
        else:
            logger.warning(f"Unknown style format: {style_format}")
            return False
    
    def _save_qgis_style(
        self,
        layer: QgsVectorLayer,
        output_path: str,
        format_name: str
    ) -> bool:
        """
        Save layer style using QGIS native saveNamedStyle.
        
        Args:
            layer: QgsVectorLayer
            output_path: Base path without extension
            format_name: Format extension (qml or sld)
            
        Returns:
            True if saved successfully
        """
        style_path = os.path.normcase(f"{output_path}.{format_name}")
        try:
            layer.saveNamedStyle(style_path)
            logger.debug(f"Style saved: {style_path}")
            return True
        except Exception as e:
            logger.warning(f"Could not save {format_name.upper()} style for '{layer.name()}': {e}")
            return False
    
    def _save_lyrx(self, layer: QgsVectorLayer, output_path: str) -> bool:
        """
        Export layer style to ArcGIS-compatible LYRX format.
        
        Creates a JSON-based style file that can be imported into ArcGIS Pro.
        Note: This is a basic conversion that includes symbology metadata.
        Full ArcGIS style support requires ArcPy (not available in QGIS).
        
        Args:
            layer: QgsVectorLayer
            output_path: Base path for export (without extension)
            
        Returns:
            True if export succeeded
        """
        style_path = os.path.normcase(f"{output_path}.lyrx")
        
        try:
            # Build ArcGIS-compatible layer definition
            renderer = layer.renderer()
            geometry_type_map = {
                0: "esriGeometryPoint",
                1: "esriGeometryPolyline", 
                2: "esriGeometryPolygon",
                3: "esriGeometryMultipoint",
                4: "esriGeometryNull"
            }
            
            lyrx_content = {
                "type": "CIMLayerDocument",
                "version": "2.9.0",
                "build": 32739,
                "layers": [
                    f"CIMPATH=map/{layer.name().replace(' ', '_')}.json"
                ],
                "layerDefinitions": [
                    {
                        "type": "CIMFeatureLayer",
                        "name": layer.name(),
                        "uRI": f"CIMPATH=map/{layer.name().replace(' ', '_')}.json",
                        "sourceModifiedTime": {
                            "type": "TimeInstant",
                            "start": datetime.now().timestamp() * 1000
                        },
                        "description": f"Exported from QGIS FilterMate - {layer.name()}",
                        "layerType": "Operational",
                        "showLegends": True,
                        "visibility": True,
                        "displayCacheType": "Permanent",
                        "maxDisplayCacheAge": 5,
                        "showPopups": True,
                        "serviceLayerID": -1,
                        "refreshRate": -1,
                        "refreshRateUnit": "esriTimeUnitsSeconds",
                        "autoGenerateFeatureTemplates": True,
                        "featureTable": {
                            "type": "CIMFeatureTable",
                            "displayField": layer.displayField() or "",
                            "editable": True,
                            "dataConnection": {
                                "type": "CIMStandardDataConnection",
                                "workspaceFactory": "FileGDB" if ".gdb" in layer.source() else "Shapefile"
                            },
                            "studyAreaSpatialRel": "esriSpatialRelUndefined",
                            "searchOrder": "esriSearchOrderSpatial"
                        },
                        "htmlPopupEnabled": True,
                        "selectable": True,
                        "featureCacheType": "Session",
                        "geometryType": geometry_type_map.get(layer.geometryType(), "esriGeometryNull"),
                        "_qgis_renderer_type": renderer.type() if renderer else "unknown",
                        "_qgis_crs": layer.crs().authid(),
                        "_qgis_feature_count": layer.featureCount(),
                        "_filtermate_export": {
                            "version": "2.5.0",
                            "timestamp": datetime.now().isoformat(),
                            "note": "Basic LYRX export. For full symbology, use ArcGIS Pro import."
                        }
                    }
                ]
            }
            
            # Add symbology info if available
            if renderer:
                if renderer.type() == 'singleSymbol':
                    symbol = renderer.symbol()
                    if symbol:
                        lyrx_content["layerDefinitions"][0]["renderer"] = {
                            "type": "CIMSimpleRenderer",
                            "symbol": {
                                "type": "CIMSymbolReference",
                                "symbol": self._convert_symbol_to_arcgis(symbol)
                            }
                        }
            
            with open(style_path, 'w', encoding='utf-8') as f:
                json.dump(lyrx_content, f, indent=2, ensure_ascii=False)
            
            logger.info(f"ArcGIS LYRX style saved: {style_path}")
            return True
            
        except Exception as e:
            logger.warning(f"Could not save ArcGIS LYRX style for '{layer.name()}': {e}")
            return False
    
    def _convert_symbol_to_arcgis(self, symbol: Any) -> dict:
        """
        Convert QGIS symbol to basic ArcGIS CIM symbol format.
        
        Args:
            symbol: QGIS symbol object
            
        Returns:
            dict: ArcGIS CIM symbol definition
        """
        try:
            # Get basic color from first symbol layer
            if symbol.symbolLayerCount() > 0:
                symbol_layer = symbol.symbolLayer(0)
                color = symbol_layer.color()
                rgb = [color.red(), color.green(), color.blue(), color.alpha()]
            else:
                rgb = [128, 128, 128, 255]
            
            symbol_type = symbol.type()
            
            if symbol_type == 0:  # Marker (Point)
                return {
                    "type": "CIMPointSymbol",
                    "symbolLayers": [{
                        "type": "CIMVectorMarker",
                        "enable": True,
                        "size": symbol.size() if hasattr(symbol, 'size') else 6,
                        "colorLocked": True,
                        "markerGraphics": [{
                            "type": "CIMMarkerGraphic",
                            "geometry": {"rings": [[[-1, -1], [-1, 1], [1, 1], [1, -1], [-1, -1]]]},
                            "symbol": {
                                "type": "CIMPolygonSymbol",
                                "symbolLayers": [{
                                    "type": "CIMSolidFill",
                                    "enable": True,
                                    "color": {"type": "CIMRGBColor", "values": rgb}
                                }]
                            }
                        }]
                    }]
                }
            elif symbol_type == 1:  # Line
                return {
                    "type": "CIMLineSymbol",
                    "symbolLayers": [{
                        "type": "CIMSolidStroke",
                        "enable": True,
                        "width": symbol.width() if hasattr(symbol, 'width') else 1,
                        "color": {"type": "CIMRGBColor", "values": rgb}
                    }]
                }
            else:  # Polygon
                return {
                    "type": "CIMPolygonSymbol",
                    "symbolLayers": [{
                        "type": "CIMSolidFill",
                        "enable": True,
                        "color": {"type": "CIMRGBColor", "values": rgb}
                    }]
                }
        except Exception as e:
            logger.debug(f"Symbol conversion fallback: {e}")
            return {"type": "CIMSymbolReference", "note": "Fallback symbol"}


def save_layer_style(
    layer: QgsVectorLayer,
    output_path: str,
    style_format: str,
    datatype: Optional[str] = None
) -> bool:
    """
    Convenience function to save layer style.
    
    Args:
        layer: QgsVectorLayer to export style from
        output_path: Base path for export (without extension)
        style_format: Style format string ('qml', 'sld', 'lyrx', 'arcgis (lyrx)')
        datatype: Export datatype (to check if styles are supported)
        
    Returns:
        True if export succeeded
        
    Example:
        save_layer_style(layer, "/path/output", "lyrx")
    """
    if not style_format or datatype == 'XLSX':
        return False
    
    # Normalize format name
    format_lower = style_format.lower().replace('arcgis (lyrx)', 'lyrx').strip()
    
    # Map to enum
    format_map = {
        'qml': StyleFormat.QML,
        'sld': StyleFormat.SLD,
        'lyrx': StyleFormat.LYRX,
        'arcgis': StyleFormat.LYRX
    }
    
    style_enum = format_map.get(format_lower)
    if not style_enum:
        logger.warning(f"Unknown style format: {style_format}")
        return False
    
    exporter = StyleExporter()
    return exporter.save_style(layer, output_path, style_enum, datatype)
