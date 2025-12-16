# -*- coding: utf-8 -*-
"""
FilterMate - Filters Module

This module provides specialized filter classes for raster, network,
and telecom analysis operations.

Classes:
    - RasterFilter: Filters combining vector and raster data
    - NetworkFilter: Filters based on network analysis
    - TelecomFilter: Business filters for FTTH/telecom networks
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .raster_filters import RasterFilter
    from .network_filters import NetworkFilter
    from .telecom_filters import TelecomFilter

__all__ = [
    'RasterFilter',
    'NetworkFilter',
    'TelecomFilter',
]
