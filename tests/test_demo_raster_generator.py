# -*- coding: utf-8 -*-
"""
Tests for Demo Raster Generator.

US-15: Demo Layer Support - Sprint 4
"""

import unittest
import tempfile
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPatternGenerator(unittest.TestCase):
    """Test pattern generation functions."""

    def test_gradient_horizontal(self):
        """Test horizontal gradient generation."""
        from tests.demo_raster_generator import PatternGenerator
        
        data = PatternGenerator.gradient(100, 50, 0, 255, "horizontal")
        
        self.assertEqual(data.shape, (50, 100))
        self.assertAlmostEqual(data[0, 0], 0.0, places=1)
        self.assertAlmostEqual(data[0, 99], 255.0, places=1)
        # Each row should be identical
        self.assertTrue((data[0] == data[25]).all())

    def test_gradient_vertical(self):
        """Test vertical gradient generation."""
        from tests.demo_raster_generator import PatternGenerator
        
        data = PatternGenerator.gradient(50, 100, 0, 255, "vertical")
        
        self.assertEqual(data.shape, (100, 50))
        self.assertAlmostEqual(data[0, 0], 0.0, places=1)
        self.assertAlmostEqual(data[99, 0], 255.0, places=1)

    def test_noise_reproducible(self):
        """Test noise with seed is reproducible."""
        from tests.demo_raster_generator import PatternGenerator
        
        data1 = PatternGenerator.noise(100, 100, seed=42)
        data2 = PatternGenerator.noise(100, 100, seed=42)
        
        self.assertTrue((data1 == data2).all())

    def test_noise_range(self):
        """Test noise values are within range."""
        from tests.demo_raster_generator import PatternGenerator
        
        data = PatternGenerator.noise(100, 100, 10, 50, seed=123)
        
        self.assertGreaterEqual(data.min(), 10)
        self.assertLessEqual(data.max(), 50)

    def test_checkerboard_pattern(self):
        """Test checkerboard pattern generation."""
        from tests.demo_raster_generator import PatternGenerator
        
        data = PatternGenerator.checkerboard(
            64, 64, tile_size=16, val_a=0, val_b=100
        )
        
        self.assertEqual(data.shape, (64, 64))
        # First tile should be val_a
        self.assertEqual(data[0, 0], 0)
        # Adjacent tile should be val_b
        self.assertEqual(data[0, 16], 100)

    def test_dem_terrain_range(self):
        """Test DEM terrain is within elevation range."""
        from tests.demo_raster_generator import PatternGenerator
        
        data = PatternGenerator.dem_terrain(
            100, 100,
            min_elevation=100,
            max_elevation=500,
            seed=42
        )
        
        self.assertGreaterEqual(data.min(), 100)
        self.assertLessEqual(data.max(), 500)

    def test_rgb_image_bands(self):
        """Test RGB image generates 3 bands."""
        from tests.demo_raster_generator import PatternGenerator
        
        bands = PatternGenerator.rgb_image(100, 100, "gradient")
        
        self.assertEqual(len(bands), 3)
        for band in bands:
            self.assertEqual(band.shape, (100, 100))


class TestDemoRasterConfig(unittest.TestCase):
    """Test demo raster configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        from tests.demo_raster_generator import DemoRasterConfig
        
        config = DemoRasterConfig()
        
        self.assertEqual(config.width, 256)
        self.assertEqual(config.height, 256)
        self.assertEqual(config.band_count, 1)
        self.assertEqual(config.data_type, "byte")
        self.assertEqual(config.crs, "EPSG:4326")
        self.assertEqual(config.pattern, "gradient")

    def test_custom_config(self):
        """Test custom configuration."""
        from tests.demo_raster_generator import DemoRasterConfig
        
        config = DemoRasterConfig(
            width=512,
            height=512,
            band_count=3,
            data_type="float32",
            pattern="dem"
        )
        
        self.assertEqual(config.width, 512)
        self.assertEqual(config.band_count, 3)
        self.assertEqual(config.pattern, "dem")


class TestDemoRasterGenerator(unittest.TestCase):
    """Test demo raster generator."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def test_generate_asc_gradient(self):
        """Test ASC file generation with gradient."""
        from tests.demo_raster_generator import (
            DemoRasterGenerator,
            DemoRasterConfig
        )
        
        generator = DemoRasterGenerator(Path(self.temp_dir))
        config = DemoRasterConfig(
            width=10,
            height=10,
            pattern="gradient"
        )
        
        filepath = generator.generate_asc(config, "test.asc")
        
        self.assertTrue(filepath.exists())
        
        # Read and verify header
        with open(filepath) as f:
            lines = f.readlines()
        
        self.assertIn("ncols 10", lines[0])
        self.assertIn("nrows 10", lines[1])

    def test_generate_asc_dem(self):
        """Test ASC file generation with DEM."""
        from tests.demo_raster_generator import (
            DemoRasterGenerator,
            DemoRasterConfig
        )
        
        generator = DemoRasterGenerator(Path(self.temp_dir))
        config = DemoRasterConfig(
            width=20,
            height=20,
            pattern="dem"
        )
        
        filepath = generator.generate_asc(config, "dem.asc")
        
        self.assertTrue(filepath.exists())

    def test_generate_asc_with_nodata(self):
        """Test ASC file with NoData value."""
        from tests.demo_raster_generator import (
            DemoRasterGenerator,
            DemoRasterConfig
        )
        
        generator = DemoRasterGenerator(Path(self.temp_dir))
        config = DemoRasterConfig(
            width=10,
            height=10,
            no_data_value=-9999.0
        )
        
        filepath = generator.generate_asc(config, "nodata.asc")
        
        with open(filepath) as f:
            content = f.read()
        
        self.assertIn("NODATA_value -9999.0", content)


class TestDemoPresets(unittest.TestCase):
    """Test preset configurations."""

    def test_simple_dem_preset(self):
        """Test simple DEM preset."""
        from tests.demo_raster_generator import DemoPresets
        
        config = DemoPresets.simple_dem()
        
        self.assertEqual(config.width, 256)
        self.assertEqual(config.height, 256)
        self.assertEqual(config.pattern, "dem")
        self.assertEqual(config.data_type, "float32")

    def test_large_dem_preset(self):
        """Test large DEM preset."""
        from tests.demo_raster_generator import DemoPresets
        
        config = DemoPresets.large_dem()
        
        self.assertEqual(config.width, 2048)
        self.assertEqual(config.height, 2048)
        self.assertEqual(config.crs, "EPSG:32632")

    def test_rgb_image_preset(self):
        """Test RGB image preset."""
        from tests.demo_raster_generator import DemoPresets
        
        config = DemoPresets.rgb_image()
        
        self.assertEqual(config.band_count, 3)
        self.assertEqual(config.data_type, "byte")

    def test_checkerboard_preset(self):
        """Test checkerboard preset."""
        from tests.demo_raster_generator import DemoPresets
        
        config = DemoPresets.checkerboard()
        
        self.assertEqual(config.pattern, "checkerboard")

    def test_with_nodata_preset(self):
        """Test with_nodata preset."""
        from tests.demo_raster_generator import DemoPresets
        
        config = DemoPresets.with_nodata()
        
        self.assertEqual(config.no_data_value, -9999.0)
        self.assertEqual(config.pattern, "noise")


class TestGenerateTestSuite(unittest.TestCase):
    """Test test suite generation."""

    def test_generate_test_suite(self):
        """Test complete test suite generation."""
        from tests.demo_raster_generator import generate_test_suite
        
        files = generate_test_suite()
        
        self.assertEqual(len(files), 3)
        for filepath in files:
            self.assertTrue(filepath.exists())
            self.assertTrue(filepath.suffix == ".asc")


if __name__ == '__main__':
    unittest.main()
