# -*- coding: utf-8 -*-
"""
EPIC-3: Unit tests for RasterValueSelectionGroupBox pixel count calculation.

Tests the histogram-based pixel counting algorithm with various predicates.

Author: FilterMate Team
Date: January 2026
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add plugin root to path for imports
plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

# Mock QGIS modules before any imports
sys.modules['qgis'] = Mock()
sys.modules['qgis.core'] = Mock()
sys.modules['qgis.gui'] = Mock()
sys.modules['qgis.utils'] = Mock()
sys.modules['qgis.PyQt'] = Mock()
sys.modules['qgis.PyQt.QtCore'] = Mock()
sys.modules['qgis.PyQt.QtWidgets'] = Mock()
sys.modules['qgis.PyQt.QtGui'] = Mock()


class MockHistogramData:
    """Mock HistogramData for testing."""
    
    def __init__(self, bin_edges, counts):
        self.bin_edges = bin_edges
        self.counts = counts
        self.total_count = sum(counts)
        self.bin_count = len(counts)
        
    @property
    def bin_width(self):
        if len(self.bin_edges) < 2:
            return 0.0
        return self.bin_edges[-1] - self.bin_edges[0] / self.bin_count


class TestPixelCountCalculation(unittest.TestCase):
    """Test pixel count calculation logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create histogram with known data
        # 10 bins from 0 to 100, each with 100 pixels = 1000 total
        self.bin_edges = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        self.counts = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        self.histogram_data = MockHistogramData(self.bin_edges, self.counts)
    
    def _calculate_within_range(self, histogram_data, range_min, range_max):
        """Calculate pixels within range (mirroring widget logic)."""
        counts = histogram_data.counts
        bin_edges = histogram_data.bin_edges
        
        within_range_count = 0
        for i, count in enumerate(counts):
            if i + 1 >= len(bin_edges):
                break
            
            bin_start = bin_edges[i]
            bin_end = bin_edges[i + 1]
            
            if bin_end <= range_min or bin_start >= range_max:
                continue
            
            if bin_start >= range_min and bin_end <= range_max:
                within_range_count += count
            else:
                overlap_start = max(bin_start, range_min)
                overlap_end = min(bin_end, range_max)
                bin_width = bin_end - bin_start
                
                if bin_width > 0:
                    fraction = (overlap_end - overlap_start) / bin_width
                    within_range_count += int(count * fraction)
        
        return within_range_count
    
    def test_full_range_selection(self):
        """Test that selecting full range returns all pixels."""
        count = self._calculate_within_range(self.histogram_data, 0, 100)
        self.assertEqual(count, 1000)
    
    def test_half_range_selection(self):
        """Test that selecting half range returns ~half pixels."""
        count = self._calculate_within_range(self.histogram_data, 0, 50)
        self.assertEqual(count, 500)
    
    def test_single_bin_selection(self):
        """Test selecting exactly one bin."""
        count = self._calculate_within_range(self.histogram_data, 0, 10)
        self.assertEqual(count, 100)
    
    def test_partial_bin_selection(self):
        """Test partial bin selection with interpolation."""
        # Select first half of first bin (0-5)
        count = self._calculate_within_range(self.histogram_data, 0, 5)
        self.assertEqual(count, 50)  # 50% of 100 pixels
    
    def test_cross_bin_selection(self):
        """Test selection that crosses bin boundaries."""
        # Select from 5 to 15 (half of bin 0 + half of bin 1)
        count = self._calculate_within_range(self.histogram_data, 5, 15)
        self.assertEqual(count, 100)  # 50 + 50
    
    def test_empty_selection(self):
        """Test selecting outside data range."""
        count = self._calculate_within_range(self.histogram_data, 150, 200)
        self.assertEqual(count, 0)
    
    def test_negative_range(self):
        """Test selection with negative values (outside histogram)."""
        count = self._calculate_within_range(self.histogram_data, -50, -10)
        self.assertEqual(count, 0)
    
    def test_inverted_range(self):
        """Test that inverted range (min > max) returns 0."""
        count = self._calculate_within_range(self.histogram_data, 50, 30)
        self.assertEqual(count, 0)


class TestPredicateCalculations(unittest.TestCase):
    """Test different predicate type calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Histogram: 10 bins from 0-100, 100 pixels each
        self.bin_edges = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        self.counts = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        self.histogram_data = MockHistogramData(self.bin_edges, self.counts)
    
    def _count_above(self, histogram_data, threshold):
        """Count pixels above threshold."""
        count = 0
        for i, bin_count in enumerate(histogram_data.counts):
            if i + 1 >= len(histogram_data.bin_edges):
                break
            
            bin_start = histogram_data.bin_edges[i]
            bin_end = histogram_data.bin_edges[i + 1]
            
            if bin_start >= threshold:
                count += bin_count
            elif bin_end > threshold:
                fraction = (bin_end - threshold) / (bin_end - bin_start)
                count += int(bin_count * fraction)
        
        return count
    
    def _count_below(self, histogram_data, threshold):
        """Count pixels below threshold."""
        count = 0
        for i, bin_count in enumerate(histogram_data.counts):
            if i + 1 >= len(histogram_data.bin_edges):
                break
            
            bin_start = histogram_data.bin_edges[i]
            bin_end = histogram_data.bin_edges[i + 1]
            
            if bin_end <= threshold:
                count += bin_count
            elif bin_start < threshold:
                fraction = (threshold - bin_start) / (bin_end - bin_start)
                count += int(bin_count * fraction)
        
        return count
    
    def test_above_middle_value(self):
        """Test counting pixels above 50."""
        count = self._count_above(self.histogram_data, 50)
        self.assertEqual(count, 500)  # Bins 6-10
    
    def test_above_zero(self):
        """Test counting pixels above 0 returns all."""
        count = self._count_above(self.histogram_data, 0)
        self.assertEqual(count, 1000)
    
    def test_above_max(self):
        """Test counting pixels above max returns 0."""
        count = self._count_above(self.histogram_data, 100)
        self.assertEqual(count, 0)
    
    def test_below_middle_value(self):
        """Test counting pixels below 50."""
        count = self._count_below(self.histogram_data, 50)
        self.assertEqual(count, 500)  # Bins 1-5
    
    def test_below_zero(self):
        """Test counting pixels below 0 returns 0."""
        count = self._count_below(self.histogram_data, 0)
        self.assertEqual(count, 0)
    
    def test_below_max(self):
        """Test counting pixels below max returns all."""
        count = self._count_below(self.histogram_data, 100)
        self.assertEqual(count, 1000)
    
    def test_above_below_sum_equals_total(self):
        """Test that above + below at same threshold = total."""
        threshold = 50
        above = self._count_above(self.histogram_data, threshold)
        below = self._count_below(self.histogram_data, threshold)
        self.assertEqual(above + below, 1000)


class TestNonUniformHistogram(unittest.TestCase):
    """Test with non-uniform histogram data."""
    
    def setUp(self):
        """Set up non-uniform histogram."""
        # Histogram with varying counts
        self.bin_edges = [0, 10, 20, 30, 40, 50]
        self.counts = [10, 50, 200, 100, 40]  # Total: 400
        self.histogram_data = MockHistogramData(self.bin_edges, self.counts)
    
    def _calculate_within_range(self, histogram_data, range_min, range_max):
        """Calculate pixels within range."""
        counts = histogram_data.counts
        bin_edges = histogram_data.bin_edges
        
        within_range_count = 0
        for i, count in enumerate(counts):
            if i + 1 >= len(bin_edges):
                break
            
            bin_start = bin_edges[i]
            bin_end = bin_edges[i + 1]
            
            if bin_end <= range_min or bin_start >= range_max:
                continue
            
            if bin_start >= range_min and bin_end <= range_max:
                within_range_count += count
            else:
                overlap_start = max(bin_start, range_min)
                overlap_end = min(bin_end, range_max)
                bin_width = bin_end - bin_start
                
                if bin_width > 0:
                    fraction = (overlap_end - overlap_start) / bin_width
                    within_range_count += int(count * fraction)
        
        return within_range_count
    
    def test_peak_selection(self):
        """Test selecting the peak bin (20-30 with 200 pixels)."""
        count = self._calculate_within_range(self.histogram_data, 20, 30)
        self.assertEqual(count, 200)
    
    def test_low_count_selection(self):
        """Test selecting low count bin."""
        count = self._calculate_within_range(self.histogram_data, 0, 10)
        self.assertEqual(count, 10)
    
    def test_full_range(self):
        """Test full range returns total."""
        count = self._calculate_within_range(self.histogram_data, 0, 50)
        self.assertEqual(count, 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
