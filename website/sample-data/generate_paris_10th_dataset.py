#!/usr/bin/env python3
"""
FilterMate Sample Dataset Generator
====================================

Generates paris_10th.gpkg GeoPackage with 5 layers from OpenStreetMap data
using Overpass API.

Requirements:
    pip install requests geopandas shapely pyproj

Usage:
    python generate_paris_10th_dataset.py

Output:
    - paris_10th.gpkg (GeoPackage with 5 layers)
    - generation_report.txt (validation report)

Author: FilterMate Documentation Team
Date: December 2025
License: GPL v3
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import sys

try:
    import requests
    import geopandas as gpd
    from shapely.geometry import shape, Point, LineString, Polygon
    import warnings
    warnings.filterwarnings('ignore')
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("\nInstall required packages:")
    print("  pip install requests geopandas shapely pyproj")
    sys.exit(1)

# Configuration
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_GPKG = "paris_10th.gpkg"
TARGET_CRS = "EPSG:2154"  # Lambert 93 (France)
SOURCE_CRS = "EPSG:4326"  # WGS84 (OSM)

# Paris 10th Arrondissement bounding box
BBOX = {
    "south": 48.8698,
    "west": 2.3516,
    "north": 48.8830,
    "east": 2.3730
}


def create_overpass_query(layer_type: str) -> str:
    """Create Overpass QL query for specific layer type."""
    
    bbox_str = f"{BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']}"
    
    queries = {
        "buildings": f"""
[out:json][timeout:60];
(
  way["building"]({bbox_str});
  relation["building"]({bbox_str});
);
out body;
>;
out skel qt;
""",
        "roads": f"""
[out:json][timeout:60];
(
  way["highway"]["highway"!~"footway|cycleway|path|service|track|steps"]({bbox_str});
);
out body;
>;
out skel qt;
""",
        "metro_stations": f"""
[out:json][timeout:60];
(
  node["station"="subway"]({bbox_str});
  node["railway"="subway_entrance"]({bbox_str});
);
out body;
""",
        "schools": f"""
[out:json][timeout:60];
(
  node["amenity"="school"]({bbox_str});
  way["amenity"="school"]({bbox_str});
  relation["amenity"="school"]({bbox_str});
);
out body;
>;
out skel qt;
""",
        "green_spaces": f"""
[out:json][timeout:60];
(
  way["leisure"="park"]({bbox_str});
  way["landuse"="grass"]({bbox_str});
  relation["leisure"="park"]({bbox_str});
);
out body;
>;
out skel qt;
"""
    }
    
    return queries[layer_type]


def query_overpass(query: str, layer_name: str) -> Dict:
    """Execute Overpass API query with retry logic."""
    
    print(f"🌍 Querying Overpass API for {layer_name}...", end=" ", flush=True)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=120
            )
            response.raise_for_status()
            
            data = response.json()
            print(f"✅ {len(data.get('elements', []))} elements")
            return data
            
        except requests.exceptions.Timeout:
            print(f"⏱️  Timeout (attempt {attempt + 1}/{max_retries})")
            time.sleep(5)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise
    
    raise Exception(f"Failed to query {layer_name} after {max_retries} attempts")


def osm_to_geojson(osm_data: Dict, geometry_type: str) -> List[Dict]:
    """Convert OSM data to GeoJSON features."""
    
    features = []
    nodes = {n['id']: (n['lon'], n['lat']) for n in osm_data.get('elements', []) if n['type'] == 'node'}
    
    for element in osm_data.get('elements', []):
        if element['type'] not in ['way', 'node', 'relation']:
            continue
            
        # Extract tags
        tags = element.get('tags', {})
        
        # Create geometry
        geom = None
        
        if element['type'] == 'node' and element['id'] in nodes:
            coords = nodes[element['id']]
            geom = Point(coords)
            
        elif element['type'] == 'way' and 'nodes' in element:
            coords = [nodes[nid] for nid in element['nodes'] if nid in nodes]
            if len(coords) >= 2:
                if geometry_type == 'polygon' and coords[0] == coords[-1] and len(coords) >= 4:
                    geom = Polygon(coords)
                elif geometry_type == 'linestring':
                    geom = LineString(coords)
                elif geometry_type == 'polygon' and len(coords) >= 4:
                    # Try to close polygon
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    if len(coords) >= 4:
                        geom = Polygon(coords)
        
        if geom and tags:
            features.append({
                'type': 'Feature',
                'geometry': geom.__geo_interface__,
                'properties': {
                    'osm_id': element['id'],
                    'osm_type': element['type'],
                    **{k: str(v) for k, v in tags.items()}
                }
            })
    
    return features


def create_layer(layer_name: str, geometry_type: str) -> gpd.GeoDataFrame:
    """Create a GeoDataFrame for a specific layer."""
    
    # Query Overpass API
    query = create_overpass_query(layer_name)
    osm_data = query_overpass(query, layer_name)
    
    # Convert to GeoJSON
    features = osm_to_geojson(osm_data, geometry_type)
    
    if not features:
        print(f"⚠️  No features found for {layer_name}")
        return None
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(features, crs=SOURCE_CRS)
    
    # Reproject to Lambert 93
    gdf = gdf.to_crs(TARGET_CRS)
    
    # Add layer-specific attributes
    if layer_name == "buildings":
        gdf['area_m2'] = gdf.geometry.area
        gdf['building_type'] = gdf.get('building', 'yes')
        
    elif layer_name == "roads":
        gdf['length_m'] = gdf.geometry.length
        gdf['road_type'] = gdf.get('highway', 'unknown')
        gdf['road_name'] = gdf.get('name', 'Unnamed')
        
    elif layer_name == "metro_stations":
        gdf['station_name'] = gdf.get('name', 'Unknown')
        gdf['lines'] = gdf.get('line', 'Unknown')
        
    elif layer_name == "schools":
        gdf['school_name'] = gdf.get('name', 'Unknown')
        gdf['school_type'] = gdf.get('school:type', 'Unknown')
        
    elif layer_name == "green_spaces":
        gdf['area_m2'] = gdf.geometry.area
        gdf['park_name'] = gdf.get('name', 'Unnamed')
        gdf['leisure_type'] = gdf.get('leisure', gdf.get('landuse', 'unknown'))
    
    print(f"✅ Created {layer_name}: {len(gdf)} features")
    return gdf


def validate_dataset(gpkg_path: Path) -> Dict[str, any]:
    """Validate generated dataset against tutorial scenarios."""
    
    print("\n🔍 Validating dataset...")
    
    validation_results = {
        "total_features": 0,
        "layers": {},
        "scenarios": {}
    }
    
    try:
        # Read all layers
        layers = {}
        for layer_name in ["buildings", "roads", "metro_stations", "schools", "green_spaces"]:
            try:
                gdf = gpd.read_file(gpkg_path, layer=layer_name)
                layers[layer_name] = gdf
                validation_results["layers"][layer_name] = {
                    "count": len(gdf),
                    "crs": str(gdf.crs),
                    "bounds": gdf.total_bounds.tolist()
                }
                validation_results["total_features"] += len(gdf)
            except Exception as e:
                validation_results["layers"][layer_name] = {"error": str(e)}
        
        # Scenario 1: Schools within 300m of metro stations
        if "schools" in layers and "metro_stations" in layers:
            schools = layers["schools"]
            metro = layers["metro_stations"]
            
            schools_buffered = metro.buffer(300).unary_union
            schools_near_metro = schools[schools.intersects(schools_buffered)]
            
            validation_results["scenarios"]["schools_near_metro"] = {
                "count": len(schools_near_metro),
                "expected": "8-12",
                "status": "✅" if 8 <= len(schools_near_metro) <= 12 else "⚠️"
            }
        
        # Scenario 2: Buildings by area
        if "buildings" in layers:
            buildings = layers["buildings"]
            large_buildings = buildings[buildings['area_m2'] > 500]
            
            validation_results["scenarios"]["large_buildings"] = {
                "count": len(large_buildings),
                "total": len(buildings),
                "percentage": f"{len(large_buildings) / len(buildings) * 100:.1f}%",
                "status": "✅"
            }
        
        # Scenario 3: Main roads
        if "roads" in layers:
            roads = layers["roads"]
            main_roads = roads[roads['road_type'].isin(['primary', 'secondary', 'tertiary'])]
            
            validation_results["scenarios"]["main_roads"] = {
                "count": len(main_roads),
                "total": len(roads),
                "status": "✅"
            }
        
        # Scenario 4: Green spaces
        if "green_spaces" in layers:
            green = layers["green_spaces"]
            large_parks = green[green['area_m2'] > 5000]
            
            validation_results["scenarios"]["large_parks"] = {
                "count": len(large_parks),
                "total": len(green),
                "status": "✅" if len(large_parks) > 0 else "⚠️"
            }
        
    except Exception as e:
        validation_results["error"] = str(e)
    
    return validation_results


def print_validation_report(results: Dict):
    """Print formatted validation report."""
    
    print("\n" + "="*60)
    print("📊 DATASET VALIDATION REPORT")
    print("="*60)
    
    print(f"\n✅ Total Features: {results['total_features']}")
    
    print("\n📋 Layers:")
    for layer, info in results['layers'].items():
        if 'error' in info:
            print(f"  ❌ {layer}: {info['error']}")
        else:
            print(f"  ✅ {layer}: {info['count']} features")
            print(f"     CRS: {info['crs']}")
    
    if results['scenarios']:
        print("\n🎯 Tutorial Scenarios:")
        for scenario, info in results['scenarios'].items():
            status = info.get('status', '❓')
            print(f"\n  {status} {scenario.replace('_', ' ').title()}")
            for key, value in info.items():
                if key != 'status':
                    print(f"     {key}: {value}")
    
    print("\n" + "="*60)


def save_validation_report(results: Dict, output_file: Path):
    """Save validation report to text file."""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("FilterMate Sample Dataset - Validation Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Features: {results['total_features']}\n\n")
        
        f.write("Layers:\n")
        for layer, info in results['layers'].items():
            if 'error' in info:
                f.write(f"  ❌ {layer}: {info['error']}\n")
            else:
                f.write(f"  ✅ {layer}: {info['count']} features\n")
        
        f.write("\nTutorial Scenarios:\n")
        for scenario, info in results['scenarios'].items():
            f.write(f"\n  {scenario}:\n")
            for key, value in info.items():
                f.write(f"    {key}: {value}\n")
        
        f.write("\n" + "=" * 60 + "\n")


def main():
    """Main execution function."""
    
    print("="*60)
    print("🏗️  FilterMate Sample Dataset Generator")
    print("="*60)
    print(f"\nTarget: {OUTPUT_GPKG}")
    print(f"CRS: {TARGET_CRS} (Lambert 93)")
    print(f"Bounding Box: Paris 10th Arrondissement\n")
    
    output_path = Path(OUTPUT_GPKG)
    
    # Check if file exists
    if output_path.exists():
        response = input(f"⚠️  {OUTPUT_GPKG} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            return
        output_path.unlink()
    
    # Layer definitions
    layers = {
        "buildings": "polygon",
        "roads": "linestring",
        "metro_stations": "point",
        "schools": "polygon",
        "green_spaces": "polygon"
    }
    
    # Generate each layer
    start_time = time.time()
    
    print("\n📥 Downloading data from OpenStreetMap...")
    print("-" * 60)
    
    for layer_name, geom_type in layers.items():
        try:
            gdf = create_layer(layer_name, geom_type)
            
            if gdf is not None and len(gdf) > 0:
                # Write to GeoPackage
                gdf.to_file(output_path, layer=layer_name, driver="GPKG")
                print(f"💾 Saved {layer_name} to {OUTPUT_GPKG}")
            else:
                print(f"⚠️  Skipped {layer_name} (no features)")
            
            # Be nice to Overpass API
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error creating {layer_name}: {e}")
            continue
    
    elapsed = time.time() - start_time
    
    # Validate dataset
    if output_path.exists():
        validation_results = validate_dataset(output_path)
        print_validation_report(validation_results)
        
        # Save report
        report_path = Path("generation_report.txt")
        save_validation_report(validation_results, report_path)
        print(f"\n💾 Validation report saved to {report_path}")
    
    # Final summary
    print("\n" + "="*60)
    print("✅ GENERATION COMPLETE")
    print("="*60)
    print(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
    print(f"📦 Output: {output_path.absolute()}")
    
    if output_path.exists():
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"💾 File size: {size_mb:.2f} MB")
    
    print("\n🎯 Next Steps:")
    print("  1. Open QGIS")
    print("  2. Drag & drop paris_10th.gpkg into map canvas")
    print("  3. Follow tutorials in FilterMate documentation")
    print("  4. Try the 4 tutorial scenarios!")
    print("\n" + "="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
