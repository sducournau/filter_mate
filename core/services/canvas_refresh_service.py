# -*- coding: utf-8 -*-
"""
CanvasRefreshService

EPIC-1 Phase 14.8: Extracted from FilterTask canvas refresh methods

This service handles canvas refresh operations after filtering:
- Single canvas refresh (post-filter)
- Delayed canvas refresh (QTimer-based)
- Final canvas refresh (2s delay)

Handles different provider types (PostgreSQL, Spatialite, OGR) with
provider-specific optimizations and freeze prevention.

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase 14.8)
"""

import logging
from qgis.utils import iface
from ..ports.qgis_port import get_qgis_factory

logger = logging.getLogger('FilterMate.Core.Services.CanvasRefreshService')


# =============================================================================
# Constants
# =============================================================================

MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000  # Skip updateExtents for large layers


# =============================================================================
# Helper Functions
# =============================================================================

def is_complex_filter(subset: str, provider_type: str) -> bool:
    """
    Check if a filter expression is complex (requires longer refresh delay).

    CONSOLIDATED v4.1: Delegates to core.optimization.query_analyzer for DRY compliance.

    Args:
        subset: Filter expression
        provider_type: Provider type (postgres, spatialite, ogr)

    Returns:
        bool: True if filter is complex
    """
    # Delegate to the canonical, more detailed implementation
    from ..optimization.query_analyzer import is_complex_filter as core_is_complex
    return core_is_complex(subset, provider_type)


# =============================================================================
# CanvasRefreshService
# =============================================================================

class CanvasRefreshService:
    """
    Service for managing canvas refresh operations.

    This service handles three types of refreshes:
    1. Single comprehensive refresh (after filter)
    2. Delayed refresh (QTimer-based, for slow queries)
    3. Final refresh (2s delay, ensures all data loaded)

    Provider-specific optimizations:
    - PostgreSQL: Uses reloadData() for complex filters
    - Spatialite: Uses reload() for proper feature display
    - OGR: Uses triggerRepaint() only (prevents freeze on large FID filters)

    Example:
        service = CanvasRefreshService()
        service.single_canvas_refresh()
    """

    def single_canvas_refresh(self):
        """
        Perform a single comprehensive canvas refresh after filter application.

        FIX v2.5.21: Replaces multi-refresh approach that caused overlapping
        refreshes to cancel each other, leaving canvas white.

        FIX v2.6.5: Only refresh layers involved in filtering, not ALL project layers.
        Skip updateExtents() for large layers.

        FIX v2.9.11: REMOVED stopRendering() for Spatialite/OGR layers.
        For large FID filters (100k+ FIDs), rendering can take 30+ seconds.
        Calling stopRendering() after 1500ms cancels in-progress rendering,
        causing "Building features list was canceled" and incomplete display.

        Steps:
        1. Check if only file-based layers are filtered (skip stopRendering)
        2. Force reload for layers with complex filters (PostgreSQL only)
        3. Trigger repaint for filtered layers (skip expensive updateExtents for large layers)
        4. Perform single final canvas refresh
        """
        try:
            canvas = iface.mapCanvas()

            # Step 1: Only stop rendering for PostgreSQL layers
            has_postgres_filtered = self._has_postgres_filtered_layers()

            if has_postgres_filtered:
                canvas.stopRendering()
                logger.debug("stopRendering() called for PostgreSQL layers")
            else:
                logger.debug("Skipping stopRendering() for file-based layers")

            # Step 2: Refresh filtered layers
            layers_reloaded, layers_repainted = self._refresh_filtered_layers()

            # Step 3: Single final canvas refresh
            canvas.refresh()

            logger.debug(f"Single canvas refresh: reloaded {layers_reloaded}, repainted {layers_repainted} layers")

        except Exception as e:
            logger.debug(f"Single canvas refresh failed: {e}")
            # Last resort fallback
            try:
                iface.mapCanvas().refresh()
            except Exception as e:
                logger.debug(f"Ignored in last resort canvas refresh: {e}")

    def delayed_canvas_refresh(self):
        """
        Perform a delayed canvas refresh for all filtered layers.

        FIX v2.5.15: Called via QTimer.singleShot after initial refresh
        to allow providers to complete data fetch. Using a timer avoids
        blocking the main thread while ensuring proper canvas update.

        FIX v2.5.11: Force updateExtents for visible layers to fix display
        issues with complex spatial queries (buffered EXISTS).

        FIX v2.5.19: Force aggressive reload for layers with complex filters
        to ensure data provider cache is cleared. Fixes display issues after
        multi-step filtering with spatial predicates.

        FIX v2.5.20: Extended support for Spatialite and OGR layers.
        """
        try:
            layers_refreshed = {
                'postgres': 0,
                'spatialite': 0,
                'ogr': 0,
                'other': 0
            }

            # Refresh filtered layers
            factory = get_qgis_factory()
            project = factory.get_project()
            for layer_id, layer in project.map_layers().items():
                try:
                    if layer.type() != 0:  # Not a vector layer
                        continue

                    provider_type = layer.providerType()
                    subset = layer.subsetString() or ''
                    if not subset:
                        continue  # Skip unfiltered layers

                    # PostgreSQL: Force reload for complex filters
                    if provider_type == 'postgres':
                        if is_complex_filter(subset, provider_type):
                            try:
                                layer.blockSignals(True)
                                layer.dataProvider().reloadData()
                                logger.debug(f"  → Forced reloadData() for {layer.name()} (postgres, complex filter)")
                            except Exception as reload_err:
                                logger.debug(f"  → reloadData() failed for {layer.name()}: {reload_err}")
                                try:
                                    layer.reload()
                                except Exception as e:
                                    logger.debug(f"Ignored in fallback reload for {layer.name()}: {e}")
                            finally:
                                layer.blockSignals(False)
                            layers_refreshed['postgres'] += 1
                        else:
                            try:
                                layer.blockSignals(True)
                                layer.reload()
                            except Exception as e:
                                logger.debug(f"Ignored in postgres layer reload: {e}")
                            finally:
                                layer.blockSignals(False)

                    # For OGR/Spatialite: just triggerRepaint - NO reloadData()
                    # Skip updateExtents for large layers
                    feature_count = layer.featureCount()
                    if feature_count is not None and 0 <= feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                        layer.updateExtents()
                    layer.triggerRepaint()

                except Exception as layer_err:
                    logger.debug(f"  → Layer refresh failed: {layer_err}")

            # Final canvas refresh
            iface.mapCanvas().refresh()

            # Log summary
            total_refreshed = sum(layers_refreshed.values())
            if total_refreshed > 0:
                refresh_summary = ", ".join(
                    f"{count} {ptype}" for ptype, count in layers_refreshed.items() if count > 0
                )
                logger.debug(f"Delayed canvas refresh: reloaded {refresh_summary} layer(s)")
            else:
                logger.debug("Delayed canvas refresh completed")

        except Exception as e:
            logger.debug(f"Delayed canvas refresh skipped: {e}")

    def final_canvas_refresh(self):
        """
        Perform a final canvas refresh after all filter queries completed.

        FIX v2.5.19: Last refresh pass, scheduled 2 seconds after filtering
        to ensure even slow queries with complex EXISTS, ST_Buffer, and large
        IN clauses have completed.

        FIX v2.5.20: Extended to all provider types (PostgreSQL, Spatialite, OGR).

        Steps:
        1. Trigger repaint for all filtered vector layers
        2. Force canvas full refresh
        """
        try:
            # Final refresh for all vector layers with filters
            layers_repainted = 0
            factory = get_qgis_factory()
            project = factory.get_project()
            for layer_id, layer in project.map_layers().items():
                try:
                    if layer.type() == 0:  # Vector layer
                        subset = layer.subsetString()
                        if subset:
                            layer.triggerRepaint()
                            layers_repainted += 1
                except Exception as e:
                    logger.debug(f"Ignored in final repaint loop: {e}")

            # Final canvas refresh
            iface.mapCanvas().refresh()

            if layers_repainted > 0:
                logger.debug(f"Final canvas refresh: repainted {layers_repainted} filtered layer(s)")
            else:
                logger.debug("Final canvas refresh completed (2s delay)")

        except Exception as e:
            logger.debug(f"Final canvas refresh skipped: {e}")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _has_postgres_filtered_layers(self) -> bool:
        """Check if any PostgreSQL layer has a filter applied."""
        factory = get_qgis_factory()
        project = factory.get_project()
        for layer_id, layer in project.map_layers().items():
            try:
                if layer.type() == 0 and layer.providerType() == 'postgres':
                    subset = layer.subsetString() or ''
                    if subset:
                        return True
            except Exception as e:
                logger.debug(f"Ignored in postgres filtered layers check: {e}")
        return False

    def _refresh_filtered_layers(self) -> tuple:
        """
        Refresh all filtered layers with provider-specific logic.

        Returns:
            Tuple of (layers_reloaded, layers_repainted)
        """
        layers_reloaded = 0
        layers_repainted = 0

        factory = get_qgis_factory()
        project = factory.get_project()
        for layer_id, layer in project.map_layers().items():
            try:
                if layer.type() != 0:  # Not a vector layer
                    continue

                subset = layer.subsetString() or ''
                if not subset:
                    continue  # Skip unfiltered layers

                provider_type = layer.providerType()

                # PostgreSQL: Force reload for complex filters
                if provider_type == 'postgres':
                    if is_complex_filter(subset, provider_type):
                        try:
                            layer.blockSignals(True)
                            layer.dataProvider().reloadData()
                            layers_reloaded += 1
                        except Exception as reload_err:
                            logger.debug(f"reloadData() failed for {layer.name()}: {reload_err}")
                            try:
                                layer.reload()
                            except Exception as e:
                                logger.debug(f"Ignored in fallback reload for {layer.name()}: {e}")
                        finally:
                            layer.blockSignals(False)
                    else:
                        try:
                            layer.blockSignals(True)
                            layer.reload()
                        except Exception as e:
                            logger.debug(f"Ignored in simple reload for {layer.name()}: {e}")
                        finally:
                            layer.blockSignals(False)

                # Spatialite: Use reload() for proper feature display
                elif provider_type == 'spatialite':
                    try:
                        layer.blockSignals(True)
                        layer.reload()
                        layers_reloaded += 1
                        logger.debug(f"Forced reload() for Spatialite layer {layer.name()}")
                    except Exception as reload_err:
                        logger.debug(f"reload() failed for {layer.name()}: {reload_err}")
                    finally:
                        layer.blockSignals(False)

                # For OGR: just triggerRepaint() - NO reloadData()
                # Skip updateExtents for large layers
                feature_count = layer.featureCount()
                if feature_count is not None and 0 <= feature_count < MAX_FEATURES_FOR_UPDATE_EXTENTS:
                    layer.updateExtents()

                layer.triggerRepaint()
                layers_repainted += 1

            except Exception as layer_err:
                logger.debug(f"Layer refresh failed: {layer_err}")

        return layers_reloaded, layers_repainted


# =============================================================================
# Factory Functions
# =============================================================================

def create_canvas_refresh_service() -> CanvasRefreshService:
    """
    Factory function to create a CanvasRefreshService.

    Returns:
        CanvasRefreshService instance
    """
    return CanvasRefreshService()


# =============================================================================
# Convenience Functions
# =============================================================================

def single_canvas_refresh():
    """Perform a single comprehensive canvas refresh."""
    service = create_canvas_refresh_service()
    service.single_canvas_refresh()


def delayed_canvas_refresh():
    """Perform a delayed canvas refresh (QTimer-based)."""
    service = create_canvas_refresh_service()
    service.delayed_canvas_refresh()


def final_canvas_refresh():
    """Perform a final canvas refresh (2s delay)."""
    service = create_canvas_refresh_service()
    service.final_canvas_refresh()
