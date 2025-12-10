# -*- coding: utf-8 -*-
"""
Spatialite Backend for FilterMate

Backend for Spatialite databases.
Uses Spatialite spatial functions which are largely compatible with PostGIS.
"""

from typing import Dict, Optional, Tuple
import sqlite3
import time
import re
from qgis.core import QgsVectorLayer, QgsDataSourceUri
from .base_backend import GeometricFilterBackend
from ..logging_config import get_tasks_logger
from ..constants import PROVIDER_SPATIALITE
from ..appUtils import safe_set_subset_string

logger = get_tasks_logger()


class SpatialiteGeometricFilter(GeometricFilterBackend):
    """
    Spatialite backend for geometric filtering.
    
    This backend provides filtering for Spatialite layers using:
    - Spatialite spatial functions (similar to PostGIS)
    - SQL-based filtering
    - Good performance for small to medium datasets
    """
    
    def __init__(self, task_params: Dict):
        """
        Initialize Spatialite backend.
        
        Args:
            task_params: Task parameters dictionary
        """
        super().__init__(task_params)
        self.logger = logger
        self._temp_table_name = None
        self._temp_table_conn = None
        # CRITICAL FIX: Temp tables don't work with setSubsetString!
        # QGIS uses its own connection to evaluate subset strings,
        # and SQLite TEMP tables are connection-specific.
        # When we create a TEMP table in our connection, QGIS cannot see it.
        # Solution: Always use inline WKT in GeomFromText() for subset strings.
        self._use_temp_table = False  # DISABLED: doesn't work with setSubsetString
    
    def supports_layer(self, layer: QgsVectorLayer) -> bool:
        """
        Check if this backend supports the given layer.
        
        Supports:
        - Native Spatialite layers (providerType == 'spatialite')
        - Valid GeoPackage layers (.gpkg files via OGR provider)
        - SQLite databases (.sqlite files via OGR provider)
        
        According to GDAL/OGR GeoPackage specification:
        - GeoPackage uses SQLite database file as container
        - Must have metadata tables (gpkg_contents, gpkg_spatial_ref_sys, gpkg_geometry_columns)
        - Supports standard WKB geometry encoding
        - Supports non-linear geometries (CIRCULARSTRING, COMPOUNDCURVE, etc.)
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if layer is from Spatialite provider or is a valid GeoPackage/SQLite file
        """
        from ..appUtils import is_valid_geopackage
        
        provider_type = layer.providerType()
        
        # Native Spatialite
        if provider_type == PROVIDER_SPATIALITE:
            self.log_debug(f"✓ Native Spatialite layer: {layer.name()}")
            return True
        
        # OGR provider - check if it's actually GeoPackage or SQLite
        if provider_type == 'ogr':
            source = layer.source()
            source_path = source.split('|')[0] if '|' in source else source
            
            # For .gpkg files, validate it's a real GeoPackage
            if source_path.lower().endswith('.gpkg'):
                if is_valid_geopackage(source_path):
                    self.log_info(f"✓ Valid GeoPackage detected via OGR: {layer.name()}")
                    self.log_debug(f"  File: {source_path}")
                    return True
                else:
                    self.log_warning(
                        f"File has .gpkg extension but is not a valid GeoPackage: {source_path}. "
                        f"Using OGR fallback backend instead."
                    )
                    return False
            
            # For .sqlite files, assume Spatialite/SQLite
            if source_path.lower().endswith('.sqlite'):
                self.log_debug(f"✓ SQLite file detected via OGR: {source_path}")
                return True
        
        return False
    
    def _get_spatialite_db_path(self, layer: QgsVectorLayer) -> Optional[str]:
        """
        Extract database file path from Spatialite/GeoPackage layer.
        
        Supports:
        - Native Spatialite databases (.sqlite)
        - GeoPackage files (.gpkg) - which use SQLite internally
        
        Note: GDAL GeoPackage driver requires read/write access to the file.
        
        Args:
            layer: Spatialite/GeoPackage vector layer
        
        Returns:
            Database file path or None if not found or not accessible
        """
        import os
        
        try:
            source = layer.source()
            self.log_debug(f"Layer source: {source}")
            
            # Try using QgsDataSourceUri (most reliable)
            uri = QgsDataSourceUri(source)
            db_path = uri.database()
            
            if db_path and db_path.strip():
                self.log_debug(f"Database path from URI: {db_path}")
                
                # Verify file exists
                if not os.path.isfile(db_path):
                    self.log_error(f"Database file not found: {db_path}")
                    return None
                
                # Check file permissions (GDAL GeoPackage driver requires read/write)
                if not os.access(db_path, os.R_OK):
                    self.log_error(
                        f"GeoPackage/Spatialite file not readable: {db_path}. "
                        f"GDAL driver requires read access."
                    )
                    return None
                
                if not os.access(db_path, os.W_OK):
                    self.log_warning(
                        f"GeoPackage/Spatialite file not writable: {db_path}. "
                        f"GDAL driver typically requires write access even for read operations. "
                        f"This may cause issues with spatial indexes and temporary tables."
                    )
                    # Don't return None - allow read-only operation but warn
                
                return db_path
            
            # Fallback: Parse source string manually
            # Format: dbname='/path/to/file.sqlite' table="table_name"
            match = re.search(r"dbname='([^']+)'", source)
            if match:
                db_path = match.group(1)
                self.log_debug(f"Database path from regex: {db_path}")
                return db_path
            
            # Another format: /path/to/file.gpkg|layername=table_name (GeoPackage)
            # or /path/to/file.sqlite|layername=table_name
            if '|' in source:
                db_path = source.split('|')[0]
                self.log_debug(f"Database path from pipe split: {db_path}")
                return db_path
            
            self.log_warning(f"Could not extract database path from source: {source}")
            return None
            
        except Exception as e:
            self.log_error(f"Error extracting database path: {str(e)}")
            return None
    
    def _create_temp_geometry_table(
        self,
        db_path: str,
        wkt_geom: str,
        srid: int = 4326
    ) -> Tuple[Optional[str], Optional[sqlite3.Connection]]:
        """
        Create temporary table with source geometry and spatial index.
        
        ⚠️ WARNING: This optimization is DISABLED for setSubsetString!
        
        WHY DISABLED:
        - SQLite TEMP tables are connection-specific
        - QGIS uses its own connection for evaluating subset strings
        - When we create a TEMP table, QGIS cannot see it
        - Result: "no such table: _fm_temp_geom_xxx" error
        
        SOLUTION:
        - Use inline WKT with GeomFromText() for subset strings
        - This function kept for potential future use with direct SQL queries
        - Could be re-enabled for export operations (not filtering)
        
        Performance Note:
        - Inline WKT: O(n × m) where m = WKT parsing time
        - With temp table: O(1) insertion + O(log n) indexed queries
        - Trade-off: Compatibility vs Performance
        
        Args:
            db_path: Path to Spatialite database
            wkt_geom: WKT geometry string
            srid: SRID for geometry (default 4326)
        
        Returns:
            Tuple (temp_table_name, connection) or (None, None) if failed
        """
        try:
            # Generate unique temp table name based on timestamp
            timestamp = int(time.time() * 1000000)  # Microseconds
            temp_table = f"_fm_temp_geom_{timestamp}"
            
            self.log_info(f"Creating temp geometry table '{temp_table}' in {db_path}")
            
            # Connect to database
            conn = sqlite3.connect(db_path)
            conn.enable_load_extension(True)
            
            # Load spatialite extension
            try:
                conn.load_extension('mod_spatialite')
            except (AttributeError, OSError):
                try:
                    conn.load_extension('mod_spatialite.dll')  # Windows
                except Exception as ext_error:
                    self.log_error(f"Could not load spatialite extension: {ext_error}")
                    conn.close()
                    return None, None
            
            cursor = conn.cursor()
            
            # Create temp table
            cursor.execute(f"""
                CREATE TEMP TABLE {temp_table} (
                    id INTEGER PRIMARY KEY,
                    geometry GEOMETRY
                )
            """)
            self.log_debug(f"Temp table {temp_table} created")
            
            # Insert geometry
            cursor.execute(f"""
                INSERT INTO {temp_table} (id, geometry)
                VALUES (1, GeomFromText(?, ?))
            """, (wkt_geom, srid))
            
            self.log_debug(f"Geometry inserted into {temp_table}")
            
            # Create spatial index on temp table
            # Spatialite uses virtual table for spatial index
            try:
                cursor.execute(f"""
                    SELECT CreateSpatialIndex('{temp_table}', 'geometry')
                """)
                self.log_info(f"✓ Spatial index created on {temp_table}")
            except Exception as idx_error:
                self.log_warning(f"Could not create spatial index: {idx_error}. Continuing without index.")
            
            conn.commit()
            
            self.log_info(
                f"✓ Temp table '{temp_table}' created successfully with spatial index. "
                f"WKT size: {len(wkt_geom)} chars"
            )
            
            return temp_table, conn
            
        except Exception as e:
            self.log_error(f"Error creating temp geometry table: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            if conn:
                try:
                    conn.close()
                except (AttributeError, OSError):
                    pass
            return None, None
    
    def cleanup(self):
        """
        Clean up temporary table and close connection.
        
        Should be called after filtering is complete.
        """
        if self._temp_table_name and self._temp_table_conn:
            try:
                self.log_debug(f"Cleaning up temp table {self._temp_table_name}")
                cursor = self._temp_table_conn.cursor()
                cursor.execute(f"DROP TABLE IF EXISTS {self._temp_table_name}")
                self._temp_table_conn.commit()
                self._temp_table_conn.close()
                self.log_info(f"✓ Temp table {self._temp_table_name} cleaned up")
            except Exception as e:
                self.log_warning(f"Error cleaning up temp table: {str(e)}")
            finally:
                self._temp_table_name = None
                self._temp_table_conn = None
    
    def build_expression(
        self,
        layer_props: Dict,
        predicates: Dict,
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build Spatialite filter expression.
        
        OPTIMIZATION: Uses temporary table with spatial index instead of inline WKT
        for massive performance improvement on medium-large datasets.
        
        Performance:
        - Without temp table: O(n × m) where m = WKT parsing overhead
        - With temp table: O(n log n) with spatial index
        - Gain: 10× on 5k features, 50× on 20k features
        
        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source geometry (WKT string)
            buffer_value: Buffer distance
            buffer_expression: Expression for dynamic buffer
        
        Returns:
            Spatialite SQL expression string
        """
        self.log_debug(f"Building Spatialite expression for {layer_props.get('layer_name', 'unknown')}")
        
        # Extract layer properties
        # Use layer_table_name (actual source table) if available, fallback to layer_name (display name)
        table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
        geom_field = layer_props.get("layer_geometry_field", "geom")
        primary_key = layer_props.get("primary_key_name")
        layer = layer_props.get("layer")  # QgsVectorLayer instance
        
        # CRITICAL FIX: Get actual geometry column name from layer's data source
        # Use QGIS API which is more reliable than parsing URIs or querying databases
        if layer:
            try:
                # METHOD 1: Try QGIS API first - most reliable
                provider = layer.dataProvider()
                
                # Get the URI object which contains all connection details
                from qgis.core import QgsDataSourceUri
                uri_string = provider.dataSourceUri()
                
                # Parse the URI to get geometry column
                uri_obj = QgsDataSourceUri(uri_string)
                
                # For OGR/Spatialite layers, get the geometry column name
                geom_col_from_uri = uri_obj.geometryColumn()
                if geom_col_from_uri:
                    geom_field = geom_col_from_uri
                else:
                    # METHOD 2: Try to extract from URI string manually
                    if '|' in uri_string:
                        parts = uri_string.split('|')
                        for part in parts:
                            if part.startswith('geometryname='):
                                geom_field = part.split('=')[1]
                                break
                    
                    # METHOD 3: Query the actual database as fallback
                    if geom_field == layer_props.get("layer_geometry_field", "geom"):
                        db_path = self._get_spatialite_db_path(layer)
                        
                        if db_path:
                            import sqlite3
                            try:
                                conn = sqlite3.connect(db_path)
                                cursor = conn.cursor()
                                
                                # Extract actual table name from URI (without layer name prefix)
                                actual_table = uri_obj.table()
                                if not actual_table:
                                    # Fallback: extract from URI string
                                    for part in uri_string.split('|'):
                                        if part.startswith('layername='):
                                            actual_table = part.split('=')[1]
                                            break
                                
                                # Query GeoPackage geometry_columns table
                                cursor.execute(
                                    "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
                                    (actual_table,)
                                )
                                result = cursor.fetchone()
                                if result:
                                    geom_field = result[0]
                                
                                conn.close()
                            except Exception as e:
                                self.log_warning(f"Database query error: {e}")
                
            except Exception as e:
                self.log_warning(f"Error detecting geometry column name: {e}")
        
        # Source geometry should be WKT string from prepare_spatialite_source_geom
        if not source_geom:
            self.log_error("No source geometry provided for Spatialite filter")
            return ""
        
        if not isinstance(source_geom, str):
            self.log_error(f"Invalid source geometry type for Spatialite: {type(source_geom)}")
            return ""
        
        wkt_length = len(source_geom)
        self.log_debug(f"Source WKT length: {wkt_length} chars")
        
        # Build geometry expression for target layer
        geom_expr = f'"{geom_field}"'
        
        # Check if we need table prefix (usually not needed for subset strings)
        if table and '.' in str(table):
            geom_expr = f'"{table}"."{geom_field}"'
        
        self.log_debug(f"Geometry expression: {geom_expr}")
        
        # CRITICAL: Temp tables DON'T WORK with setSubsetString!
        # QGIS uses its own connection and cannot see TEMP tables from our connection.
        # Always use inline WKT for subset string filtering.
        # Note: This may be slow for very large WKT, but it's the only way that works.
        use_temp_table = False  # FORCED: temp tables incompatible with setSubsetString
        
        if use_temp_table and layer:
            self.log_info(f"WKT size {wkt_length} chars - using OPTIMIZED temp table method")
            
            # Get database path
            db_path = self._get_spatialite_db_path(layer)
            
            if db_path:
                # Get SRID from layer
                srid = 4326  # Default
                if hasattr(layer, 'crs'):
                    crs = layer.crs()
                    if crs and crs.isValid():
                        # Extract numeric SRID from authid (e.g., 'EPSG:3857' -> 3857)
                        authid = crs.authid()
                        if ':' in authid:
                            try:
                                srid = int(authid.split(':')[1])
                            except (ValueError, IndexError):
                                self.log_warning(f"Could not parse SRID from {authid}, using 4326")
                
                # Create temp table
                temp_table, conn = self._create_temp_geometry_table(db_path, source_geom, srid)
                
                if temp_table and conn:
                    # Store for cleanup later
                    self._temp_table_name = temp_table
                    self._temp_table_conn = conn
                    
                    # Build optimized expression using temp table JOIN
                    # This uses spatial index for O(log n) performance
                    source_geom_expr = f"{temp_table}.geometry"
                    
                    self.log_info("✓ Using temp table with spatial index for filtering")
                else:
                    # Fallback to inline WKT
                    self.log_warning("Temp table creation failed, falling back to inline WKT")
                    use_temp_table = False
            else:
                self.log_warning("Could not get database path, falling back to inline WKT")
                use_temp_table = False
        else:
            use_temp_table = False
        
        # Use inline WKT (required for setSubsetString compatibility)
        if not use_temp_table:
            if wkt_length > 500000:
                self.log_warning(
                    f"Very large WKT ({wkt_length} chars) in subset string. "
                    "This may cause slow performance. Consider using smaller source selection or PostgreSQL."
                )
            elif wkt_length > 100000:
                self.log_info(
                    f"Large WKT ({wkt_length} chars) in subset string. "
                    "Performance may be reduced for datasets >10k features."
                )
            
            # IMPORTANT: Single quotes in WKT must be escaped for SQL
            # This was already done in prepare_spatialite_source_geom()
            source_geom_expr = f"GeomFromText('{source_geom}')"
            self.log_info(f"Using inline WKT method (required for QGIS subset strings)")
        
        # NOTE: Buffer is already applied in prepare_spatialite_source_geom()
        if buffer_expression:
            self.log_warning("Dynamic buffer expressions not yet fully supported for Spatialite")
            self.log_info("Note: Static buffer values are already applied in geometry preparation")
        
        # Build predicate expressions with OPTIMIZED order
        # Order by selectivity (most selective first = fastest short-circuit)
        # intersects > within > contains > overlaps > touches
        predicate_order = ['intersects', 'within', 'contains', 'overlaps', 'touches', 'crosses', 'disjoint']
        
        # Sort predicates by optimal order
        ordered_predicates = sorted(
            predicates.items(),
            key=lambda x: predicate_order.index(x[0]) if x[0] in predicate_order else 999
        )
        
        predicate_expressions = []
        for predicate_name, predicate_func in ordered_predicates:
            # Apply spatial predicate
            # Format: ST_Intersects("geometry", source_geom_expr)
            expr = f"{predicate_func}({geom_expr}, {source_geom_expr})"
            predicate_expressions.append(expr)
            self.log_debug(f"Added predicate: {predicate_func} (optimal order)")
        
        # Combine predicates with OR
        # Note: SQL engines typically evaluate OR left-to-right
        # Most selective predicates first = fewer expensive operations
        if predicate_expressions:
            combined = " OR ".join(predicate_expressions)
            method = "temp table" if use_temp_table else "inline WKT"
            self.log_info(
                f"Built Spatialite expression with {len(predicate_expressions)} predicate(s) "
                f"using {method} method"
            )
            self.log_debug(f"Expression preview: {combined[:150]}...")
            return combined
        
        self.log_warning("No predicates to apply")
        return ""
    
    def apply_filter(
        self,
        layer: QgsVectorLayer,
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to Spatialite layer using setSubsetString.
        
        Args:
            layer: Spatialite layer to filter
            expression: Spatialite SQL expression
            old_subset: Existing subset string
            combine_operator: Operator to combine filters (AND/OR)
        
        Returns:
            True if filter applied successfully
        """
        import time
        start_time = time.time()
        
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                return False
            
            # Log layer information
            self.log_debug(f"Layer provider: {layer.providerType()}")
            self.log_debug(f"Layer source: {layer.source()[:100]}...")
            self.log_debug(f"Current feature count: {layer.featureCount()}")
            
            # Combine with existing filter if specified
            if old_subset and combine_operator:
                final_expression = f"({old_subset}) {combine_operator} ({expression})"
                self.log_debug(f"Combining with existing subset using {combine_operator}")
            else:
                final_expression = expression
            
            self.log_info(f"Applying Spatialite filter to {layer.name()}")
            self.log_info(f"Expression length: {len(final_expression)} chars")
            
            # Log full expression for debugging (first 500 chars)
            if len(final_expression) <= 500:
                self.log_debug(f"Full expression: {final_expression}")
            else:
                self.log_debug(f"Expression start: {final_expression[:250]}...")
                self.log_debug(f"Expression end: ...{final_expression[-250:]}")
            
            # Apply the filter (thread-safe)
            self.log_debug("Calling safe_set_subset_string()...")
            result = safe_set_subset_string(layer, final_expression)
            
            elapsed = time.time() - start_time
            
            if result:
                feature_count = layer.featureCount()
                self.log_info(f"✓ Filter applied successfully in {elapsed:.2f}s. {feature_count} features match.")
                
                if feature_count == 0:
                    self.log_warning("Filter resulted in 0 features - check if expression is correct")
                    self.log_debug("Possible causes:")
                    self.log_debug("  - No features actually match the spatial criteria")
                    self.log_debug("  - Wrong CRS (source and target geometries in different projections)")
                    self.log_debug("  - Invalid WKT geometry")
                
                if elapsed > 5.0:
                    self.log_warning(f"Slow filter operation ({elapsed:.2f}s) - consider using PostgreSQL for better performance")
                
                # Warn if dataset is large
                if feature_count > 50000:
                    self.log_warning(
                        f"Large dataset ({feature_count} features) with Spatialite. "
                        "Consider using PostgreSQL for better performance."
                    )
            else:
                self.log_error(f"✗ setSubsetString() returned False - filter expression may be invalid")
                self.log_error("Common issues:")
                self.log_error("  1. Spatial functions not available (mod_spatialite not loaded by QGIS)")
                self.log_error("  2. Invalid WKT geometry syntax")
                self.log_error("  3. Wrong geometry column name")
                self.log_error("  4. SQL syntax error")
                self.log_error("  5. Referencing non-existent table (e.g., temp tables)")
                
                # Check if expression references a temp table (common mistake)
                if '_fm_temp_geom_' in final_expression:
                    self.log_error("⚠️ CRITICAL ERROR: Expression references temp table!")
                    self.log_error("   Temp tables DON'T WORK with QGIS setSubsetString()!")
                    self.log_error("   QGIS uses its own connection and cannot see our temp tables.")
                    self.log_error("   This should have been fixed - please report this bug.")
                
                # Try a simple test to see if spatial functions work
                try:
                    test_expr = f'"{layer.geometryColumn()}" IS NOT NULL'
                    self.log_debug(f"Testing simple expression: {test_expr}")
                    test_result = layer.setSubsetString(test_expr)
                    if test_result:
                        self.log_info("Simple geometry test passed - issue is with spatial expression")
                        # Restore no filter
                        layer.setSubsetString("")
                    else:
                        self.log_error("Even simple geometry expression failed - layer may not support subset strings")
                except Exception as test_error:
                    self.log_debug(f"Test expression error: {test_error}")
            
            return result
            
        except Exception as e:
            self.log_error(f"Exception while applying filter: {str(e)}")
            import traceback
            self.log_debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return "Spatialite"
