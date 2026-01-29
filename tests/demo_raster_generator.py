# -*- coding: utf-8 -*-
"""
Demo Raster Layer Generator for Testing.

US-15: Demo Layer Support - Sprint 4

Provides utilities for generating demo raster layers
for testing and demonstration purposes.

Author: FilterMate Team
Date: January 2026
"""

import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path
import tempfile
import struct

# QGIS imports with fallback for testing
try:
    from qgis.core import (
        QgsRasterLayer,
        QgsProject,
        QgsCoordinateReferenceSystem,
        Qgis
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DemoRasterConfig:
    """Configuration for demo raster generation."""
    
    width: int = 256
    height: int = 256
    band_count: int = 1
    data_type: str = "byte"  # byte, int16, float32
    crs: str = "EPSG:4326"
    extent: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    no_data_value: Optional[float] = None
    pattern: str = "gradient"  # gradient, noise, checkerboard, dem


@dataclass
class DemoBandConfig:
    """Configuration for a single band."""
    
    min_value: float = 0.0
    max_value: float = 255.0
    pattern: str = "gradient"
    noise_factor: float = 0.1


# =============================================================================
# Pattern Generators
# =============================================================================

class PatternGenerator:
    """Generate various raster patterns for testing."""
    
    @staticmethod
    def gradient(
        width: int,
        height: int,
        min_val: float = 0.0,
        max_val: float = 255.0,
        direction: str = "horizontal"
    ) -> np.ndarray:
        """
        Generate gradient pattern.
        
        Args:
            width: Raster width in pixels
            height: Raster height in pixels
            min_val: Minimum value
            max_val: Maximum value
            direction: 'horizontal', 'vertical', or 'diagonal'
            
        Returns:
            2D numpy array with gradient values
        """
        if direction == "horizontal":
            gradient = np.linspace(min_val, max_val, width)
            data = np.tile(gradient, (height, 1))
        elif direction == "vertical":
            gradient = np.linspace(min_val, max_val, height)
            data = np.tile(gradient.reshape(-1, 1), (1, width))
        else:  # diagonal
            x = np.linspace(0, 1, width)
            y = np.linspace(0, 1, height)
            xx, yy = np.meshgrid(x, y)
            data = (xx + yy) / 2 * (max_val - min_val) + min_val
        
        return data.astype(np.float32)
    
    @staticmethod
    def noise(
        width: int,
        height: int,
        min_val: float = 0.0,
        max_val: float = 255.0,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate random noise pattern.
        
        Args:
            width: Raster width
            height: Raster height
            min_val: Minimum value
            max_val: Maximum value
            seed: Random seed for reproducibility
            
        Returns:
            2D numpy array with noise values
        """
        if seed is not None:
            np.random.seed(seed)
        
        data = np.random.uniform(min_val, max_val, (height, width))
        return data.astype(np.float32)
    
    @staticmethod
    def checkerboard(
        width: int,
        height: int,
        tile_size: int = 32,
        val_a: float = 0.0,
        val_b: float = 255.0
    ) -> np.ndarray:
        """
        Generate checkerboard pattern.
        
        Args:
            width: Raster width
            height: Raster height
            tile_size: Size of each tile
            val_a: Value for dark tiles
            val_b: Value for light tiles
            
        Returns:
            2D numpy array with checkerboard pattern
        """
        data = np.zeros((height, width), dtype=np.float32)
        
        for i in range(height):
            for j in range(width):
                tile_i = i // tile_size
                tile_j = j // tile_size
                if (tile_i + tile_j) % 2 == 0:
                    data[i, j] = val_a
                else:
                    data[i, j] = val_b
        
        return data
    
    @staticmethod
    def dem_terrain(
        width: int,
        height: int,
        min_elevation: float = 0.0,
        max_elevation: float = 1000.0,
        roughness: float = 0.5,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate realistic DEM-like terrain using diamond-square algorithm.
        
        Args:
            width: Raster width
            height: Raster height
            min_elevation: Minimum elevation
            max_elevation: Maximum elevation
            roughness: Terrain roughness (0-1)
            seed: Random seed
            
        Returns:
            2D numpy array with terrain values
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Use power of 2 size for algorithm
        size = max(width, height)
        n = 1
        while n < size:
            n *= 2
        n += 1
        
        # Initialize with corner values
        terrain = np.zeros((n, n), dtype=np.float32)
        terrain[0, 0] = np.random.uniform(0, 1)
        terrain[0, n-1] = np.random.uniform(0, 1)
        terrain[n-1, 0] = np.random.uniform(0, 1)
        terrain[n-1, n-1] = np.random.uniform(0, 1)
        
        # Diamond-square iterations
        step = n - 1
        scale = roughness
        
        while step > 1:
            half = step // 2
            
            # Diamond step
            for i in range(half, n - 1, step):
                for j in range(half, n - 1, step):
                    avg = (
                        terrain[i - half, j - half] +
                        terrain[i - half, j + half] +
                        terrain[i + half, j - half] +
                        terrain[i + half, j + half]
                    ) / 4
                    terrain[i, j] = avg + np.random.uniform(-scale, scale)
            
            # Square step
            for i in range(0, n, half):
                for j in range((i + half) % step, n, step):
                    neighbors = []
                    if i >= half:
                        neighbors.append(terrain[i - half, j])
                    if i + half < n:
                        neighbors.append(terrain[i + half, j])
                    if j >= half:
                        neighbors.append(terrain[i, j - half])
                    if j + half < n:
                        neighbors.append(terrain[i, j + half])
                    
                    if neighbors:
                        avg = sum(neighbors) / len(neighbors)
                        terrain[i, j] = avg + np.random.uniform(-scale, scale)
            
            step = half
            scale *= 0.5
        
        # Normalize and scale
        terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min())
        terrain = terrain * (max_elevation - min_elevation) + min_elevation
        
        # Crop to requested size
        return terrain[:height, :width]
    
    @staticmethod
    def rgb_image(
        width: int,
        height: int,
        pattern: str = "gradient"
    ) -> List[np.ndarray]:
        """
        Generate RGB image with 3 bands.
        
        Args:
            width: Image width
            height: Image height
            pattern: Base pattern type
            
        Returns:
            List of 3 numpy arrays (R, G, B)
        """
        if pattern == "gradient":
            r = PatternGenerator.gradient(width, height, 0, 255, "horizontal")
            g = PatternGenerator.gradient(width, height, 0, 255, "vertical")
            b = PatternGenerator.gradient(width, height, 0, 255, "diagonal")
        else:
            r = PatternGenerator.noise(width, height, 0, 255, seed=1)
            g = PatternGenerator.noise(width, height, 0, 255, seed=2)
            b = PatternGenerator.noise(width, height, 0, 255, seed=3)
        
        return [r, g, b]


# =============================================================================
# Demo Layer Generator
# =============================================================================

class DemoRasterGenerator:
    """Generate demo raster layers for testing."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize generator.
        
        Args:
            output_dir: Directory for generated files.
                       Uses temp directory if None.
        """
        if output_dir is None:
            self.output_dir = Path(tempfile.gettempdir()) / "filtermate_demo"
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_asc(
        self,
        config: DemoRasterConfig,
        filename: str = "demo_raster.asc"
    ) -> Path:
        """
        Generate ASCII Grid file.
        
        Args:
            config: Raster configuration
            filename: Output filename
            
        Returns:
            Path to generated file
        """
        # Generate data
        if config.pattern == "gradient":
            data = PatternGenerator.gradient(
                config.width, config.height, 0, 255
            )
        elif config.pattern == "noise":
            data = PatternGenerator.noise(
                config.width, config.height, 0, 255
            )
        elif config.pattern == "checkerboard":
            data = PatternGenerator.checkerboard(
                config.width, config.height
            )
        else:  # dem
            data = PatternGenerator.dem_terrain(
                config.width, config.height, 0, 1000
            )
        
        # Calculate cell size
        xmin, ymin, xmax, ymax = config.extent
        cellsize = (xmax - xmin) / config.width
        
        # Write ASC file
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(f"ncols {config.width}\n")
            f.write(f"nrows {config.height}\n")
            f.write(f"xllcorner {xmin}\n")
            f.write(f"yllcorner {ymin}\n")
            f.write(f"cellsize {cellsize}\n")
            if config.no_data_value is not None:
                f.write(f"NODATA_value {config.no_data_value}\n")
            else:
                f.write("NODATA_value -9999\n")
            
            for row in data:
                line = " ".join(f"{val:.2f}" for val in row)
                f.write(line + "\n")
        
        return filepath
    
    def generate_memory_layer(
        self,
        config: DemoRasterConfig,
        name: str = "Demo Raster"
    ):
        """
        Generate in-memory raster layer.
        
        Requires QGIS to be available.
        
        Args:
            config: Raster configuration
            name: Layer name
            
        Returns:
            QgsRasterLayer or None if QGIS not available
        """
        if not QGIS_AVAILABLE:
            return None
        
        # Generate ASC file first
        filepath = self.generate_asc(config, f"{name}.asc")
        
        # Load as QGIS layer
        layer = QgsRasterLayer(str(filepath), name, "gdal")
        
        if not layer.isValid():
            return None
        
        return layer
    
    def add_to_project(
        self,
        layer,
        group_name: str = "Demo Layers"
    ) -> bool:
        """
        Add layer to current QGIS project.
        
        Args:
            layer: QgsRasterLayer to add
            group_name: Layer group name
            
        Returns:
            True if successful
        """
        if not QGIS_AVAILABLE:
            return False
        
        if layer is None or not layer.isValid():
            return False
        
        project = QgsProject.instance()
        
        # Find or create group
        root = project.layerTreeRoot()
        group = root.findGroup(group_name)
        if group is None:
            group = root.addGroup(group_name)
        
        # Add layer to project and group
        project.addMapLayer(layer, False)
        group.addLayer(layer)
        
        return True


# =============================================================================
# Preset Configurations
# =============================================================================

class DemoPresets:
    """Predefined demo raster configurations."""
    
    @staticmethod
    def simple_dem() -> DemoRasterConfig:
        """Simple DEM for basic testing."""
        return DemoRasterConfig(
            width=256,
            height=256,
            band_count=1,
            data_type="float32",
            crs="EPSG:4326",
            extent=(0.0, 0.0, 1.0, 1.0),
            pattern="dem"
        )
    
    @staticmethod
    def large_dem() -> DemoRasterConfig:
        """Large DEM for performance testing."""
        return DemoRasterConfig(
            width=2048,
            height=2048,
            band_count=1,
            data_type="float32",
            crs="EPSG:32632",
            extent=(500000, 5000000, 510000, 5010000),
            pattern="dem"
        )
    
    @staticmethod
    def rgb_image() -> DemoRasterConfig:
        """RGB image for multi-band testing."""
        return DemoRasterConfig(
            width=512,
            height=512,
            band_count=3,
            data_type="byte",
            crs="EPSG:4326",
            extent=(-1.0, -1.0, 1.0, 1.0),
            pattern="gradient"
        )
    
    @staticmethod
    def checkerboard() -> DemoRasterConfig:
        """Checkerboard for visual testing."""
        return DemoRasterConfig(
            width=256,
            height=256,
            band_count=1,
            data_type="byte",
            crs="EPSG:4326",
            extent=(0.0, 0.0, 1.0, 1.0),
            pattern="checkerboard"
        )
    
    @staticmethod
    def with_nodata() -> DemoRasterConfig:
        """Raster with NoData values."""
        return DemoRasterConfig(
            width=256,
            height=256,
            band_count=1,
            data_type="float32",
            crs="EPSG:4326",
            extent=(0.0, 0.0, 1.0, 1.0),
            no_data_value=-9999.0,
            pattern="noise"
        )


# =============================================================================
# Utility Functions
# =============================================================================

def create_demo_layer(
    preset: str = "simple_dem",
    add_to_project: bool = True
):
    """
    Convenience function to create demo layer.
    
    Args:
        preset: Preset name ('simple_dem', 'large_dem', 'rgb_image',
                'checkerboard', 'with_nodata')
        add_to_project: Whether to add to current project
        
    Returns:
        QgsRasterLayer or None
    """
    presets = {
        "simple_dem": DemoPresets.simple_dem,
        "large_dem": DemoPresets.large_dem,
        "rgb_image": DemoPresets.rgb_image,
        "checkerboard": DemoPresets.checkerboard,
        "with_nodata": DemoPresets.with_nodata
    }
    
    if preset not in presets:
        return None
    
    config = presets[preset]()
    generator = DemoRasterGenerator()
    layer = generator.generate_memory_layer(config, f"Demo {preset}")
    
    if add_to_project and layer is not None:
        generator.add_to_project(layer)
    
    return layer


def generate_test_suite():
    """
    Generate complete test suite of demo rasters.
    
    Returns:
        List of generated file paths
    """
    generator = DemoRasterGenerator()
    files = []
    
    for preset_name in ["simple_dem", "checkerboard", "with_nodata"]:
        config = getattr(DemoPresets, preset_name)()
        filepath = generator.generate_asc(config, f"test_{preset_name}.asc")
        files.append(filepath)
    
    return files


# =============================================================================
# Module Entry Point
# =============================================================================

if __name__ == "__main__":
    # Generate test files when run directly
    print("Generating demo raster files...")
    
    files = generate_test_suite()
    
    for f in files:
        print(f"  Created: {f}")
    
    print("Done!")
