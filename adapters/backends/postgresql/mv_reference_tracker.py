# -*- coding: utf-8 -*-
"""
FilterMate PostgreSQL Materialized View Reference Tracker

Tracks references to materialized views to prevent premature cleanup
when multiple layers reference the same MV.

Problem:
When filtering multiple layers with a source layer using buffer expression,
a shared MV is created (e.g., temp_buffered_demand_points_xxx). Multiple
distant layers reference this same MV in their filter expressions. However,
when one layer's filter task completes, it tries to clean up all MVs,
including the shared one that other layers still need, causing
"relation does not exist" errors.

Solution:
Reference counting. Each MV tracks how many layers reference it.
Only drop the MV when reference count reaches zero.

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Dict, Set, Optional
from threading import Lock

logger = logging.getLogger('FilterMate.PostgreSQL.MVRefTracker')


class MVReferenceTracker:
    """
    Thread-safe reference tracker for materialized views.
    
    Prevents premature cleanup of MVs that are still referenced
    by other layers' filter expressions.
    
    Usage:
        tracker = MVReferenceTracker()
        
        # When creating/using MV
        tracker.add_reference("temp_buffered_demand_points_abc123", "layer_id_1")
        tracker.add_reference("temp_buffered_demand_points_abc123", "layer_id_2")
        
        # When layer no longer needs MV
        can_drop = tracker.remove_reference("temp_buffered_demand_points_abc123", "layer_id_1")
        if can_drop:
            # Safe to drop MV - no more references
            drop_materialized_view(mv_name)
    """
    
    def __init__(self):
        """Initialize the reference tracker."""
        # mv_name -> set of layer_ids that reference it
        self._references: Dict[str, Set[str]] = {}
        
        # Thread safety lock
        self._lock = Lock()
        
        logger.debug("[MVRefTracker] Initialized")
    
    def add_reference(self, mv_name: str, layer_id: str) -> int:
        """
        Add a reference from a layer to an MV.
        
        Args:
            mv_name: Materialized view name
            layer_id: Layer ID that references the MV
            
        Returns:
            New reference count for this MV
        """
        with self._lock:
            if mv_name not in self._references:
                self._references[mv_name] = set()
            
            self._references[mv_name].add(layer_id)
            count = len(self._references[mv_name])
            
            logger.debug(
                f"[MVRefTracker] Added reference: MV={mv_name}, "
                f"layer={layer_id[:8]}, refs={count}"
            )
            
            return count
    
    def remove_reference(self, mv_name: str, layer_id: str) -> bool:
        """
        Remove a reference from a layer to an MV.
        
        Args:
            mv_name: Materialized view name
            layer_id: Layer ID that no longer references the MV
            
        Returns:
            True if MV can be safely dropped (no more references), False otherwise
        """
        with self._lock:
            if mv_name not in self._references:
                logger.debug(
                    f"[MVRefTracker] MV {mv_name} not tracked - safe to drop"
                )
                return True
            
            self._references[mv_name].discard(layer_id)
            count = len(self._references[mv_name])
            
            if count == 0:
                # No more references - safe to drop
                del self._references[mv_name]
                logger.debug(
                    f"[MVRefTracker] Last reference removed: MV={mv_name}, "
                    f"layer={layer_id[:8]} → Safe to drop"
                )
                return True
            else:
                logger.debug(
                    f"[MVRefTracker] Reference removed: MV={mv_name}, "
                    f"layer={layer_id[:8]}, remaining refs={count} → Keep MV"
                )
                return False
    
    def get_reference_count(self, mv_name: str) -> int:
        """
        Get current reference count for an MV.
        
        Args:
            mv_name: Materialized view name
            
        Returns:
            Number of layers referencing this MV
        """
        with self._lock:
            if mv_name not in self._references:
                return 0
            return len(self._references[mv_name])
    
    def is_referenced(self, mv_name: str) -> bool:
        """
        Check if MV is currently referenced by any layer.
        
        Args:
            mv_name: Materialized view name
            
        Returns:
            True if MV has active references, False if safe to drop
        """
        return self.get_reference_count(mv_name) > 0
    
    def get_referencing_layers(self, mv_name: str) -> Set[str]:
        """
        Get all layer IDs that reference an MV.
        
        Args:
            mv_name: Materialized view name
            
        Returns:
            Set of layer IDs, empty if no references
        """
        with self._lock:
            if mv_name not in self._references:
                return set()
            return self._references[mv_name].copy()
    
    def remove_all_references_for_layer(self, layer_id: str) -> Set[str]:
        """
        Remove all references from a specific layer.
        
        Useful when a layer is removed from the project.
        
        Args:
            layer_id: Layer ID to clean up
            
        Returns:
            Set of MV names that can now be safely dropped
        """
        with self._lock:
            can_drop = set()
            
            for mv_name in list(self._references.keys()):
                if layer_id in self._references[mv_name]:
                    self._references[mv_name].discard(layer_id)
                    
                    if len(self._references[mv_name]) == 0:
                        del self._references[mv_name]
                        can_drop.add(mv_name)
                        logger.debug(
                            f"[MVRefTracker] Layer {layer_id[:8]} cleanup: "
                            f"MV {mv_name} can be dropped"
                        )
            
            if can_drop:
                logger.debug(
                    f"[MVRefTracker] Removed all references for layer {layer_id[:8]}: "
                    f"{len(can_drop)} MV(s) can be dropped"
                )
            
            return can_drop
    
    def clear_all(self) -> Set[str]:
        """
        Clear all references (for cleanup/shutdown).
        
        Returns:
            Set of all tracked MV names
        """
        with self._lock:
            mv_names = set(self._references.keys())
            self._references.clear()
            
            logger.debug(
                f"[MVRefTracker] Cleared all references: "
                f"{len(mv_names)} MV(s) tracked"
            )
            
            return mv_names
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get tracker statistics.
        
        Returns:
            Dictionary with stats: tracked_mvs, total_references
        """
        with self._lock:
            total_refs = sum(len(refs) for refs in self._references.values())
            return {
                'tracked_mvs': len(self._references),
                'total_references': total_refs
            }


# Global singleton instance
_global_tracker: Optional[MVReferenceTracker] = None


def get_mv_reference_tracker() -> MVReferenceTracker:
    """
    Get the global MV reference tracker instance.
    
    Returns:
        Singleton MVReferenceTracker instance
    """
    global _global_tracker
    
    if _global_tracker is None:
        _global_tracker = MVReferenceTracker()
    
    return _global_tracker
