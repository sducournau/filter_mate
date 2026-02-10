"""
Task Collectors Package

Collectors extracted and consolidated for Phase E13.

Contains:
- FeatureCollector: Collect and cache feature IDs from various sources
"""

from .feature_collector import FeatureCollector, CollectionResult  # noqa: F401

__all__ = [
    'FeatureCollector',
    'CollectionResult'
]
