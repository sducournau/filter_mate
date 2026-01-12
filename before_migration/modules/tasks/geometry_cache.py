"""
Source Geometry Cache Module

Cache pour géométries sources pré-calculées.
Extracted from appTasks.py during Phase 3 refactoring (Dec 2025).

This cache avoids recalculating source geometries when filtering multiple layers
with the same source selection, providing significant performance improvements.

Performance: 5× speedup when filtering 5+ layers with the same source.

Example:
    User selects 2000 features and filters 5 layers:
    - Without cache: 5 × 2s calculation = 10s wasted
    - With cache: 1 × 2s + 4 × 0.01s = 2.04s total
"""

import logging
import os

from ..logging_config import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.Cache',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)


class SourceGeometryCache:
    """
    Cache pour géométries sources pré-calculées.
    
    Évite de recalculer les géométries sources quand on filtre plusieurs layers
    avec la même sélection source.
    
    Performance: Gain de 5× quand on filtre 5+ layers avec la même source.
    
    Example:
        User sélectionne 2000 features et filtre 5 layers:
        - Sans cache: 5 × 2s calcul = 10s gaspillés
        - Avec cache: 1 × 2s + 4 × 0.01s = 2.04s total
    """
    
    def __init__(self):
        self._cache = {}
        self._max_cache_size = 10  # Limite mémoire: max 10 entrées
        self._access_order = []  # FIFO: First In, First Out
        logger.info("✓ SourceGeometryCache initialized (max size: 10)")
    
    def get_cache_key(self, features, buffer_value, target_crs_authid, layer_id=None, subset_string=None):
        """
        Génère une clé unique pour identifier une géométrie cachée.
        
        Args:
            features: Liste de features ou IDs
            buffer_value: Distance de buffer (ou None)
            target_crs_authid: CRS authid (ex: 'EPSG:3857')
            layer_id: ID de la couche source (optionnel, pour éviter les collisions)
            subset_string: Subset string actif sur la couche (optionnel, pour invalider le cache quand le filtre change)
        
        Returns:
            tuple: Clé unique pour ce cache
        """
        # Convertir features en tuple d'IDs triés (ordre indépendant)
        if isinstance(features, (list, tuple)) and features:
            if hasattr(features[0], 'id'):
                feature_ids = tuple(sorted([f.id() for f in features]))
            else:
                feature_ids = tuple(sorted(features))
        else:
            feature_ids = ()
        
        # Inclure layer_id et subset_string dans la clé pour éviter les collisions
        # Le subset_string est critique: si le filtre change, la géométrie doit être recalculée
        return (feature_ids, buffer_value, target_crs_authid, layer_id, subset_string)
    
    def get(self, features, buffer_value, target_crs_authid, layer_id=None, subset_string=None):
        """
        Récupère une géométrie du cache si elle existe.
        
        Args:
            features: Liste de features ou IDs
            buffer_value: Distance de buffer
            target_crs_authid: CRS authid
            layer_id: ID de la couche source (optionnel)
            subset_string: Subset string actif (optionnel)
        
        Returns:
            dict ou None: Données de géométrie cachées (wkt, bbox, etc.)
        """
        key = self.get_cache_key(features, buffer_value, target_crs_authid, layer_id, subset_string)
        
        if key in self._cache:
            # Update access order (move to end)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            logger.info("✓ Cache HIT: Geometry retrieved from cache")
            return self._cache[key]
        
        logger.debug("Cache MISS: Geometry not in cache")
        return None
    
    def put(self, features, buffer_value, target_crs_authid, geometry_data, layer_id=None, subset_string=None):
        """
        Stocke une géométrie dans le cache.
        
        Args:
            features: Liste de features ou IDs
            buffer_value: Distance de buffer
            target_crs_authid: CRS authid
            geometry_data: Données à cacher (dict avec wkt, bbox, etc.)
            layer_id: ID de la couche source (optionnel)
            subset_string: Subset string actif (optionnel)
        """
        key = self.get_cache_key(features, buffer_value, target_crs_authid, layer_id, subset_string)
        
        # Vérifier limite de cache
        if len(self._cache) >= self._max_cache_size:
            # Supprimer l'entrée la plus ancienne (FIFO)
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
                    logger.debug(f"Cache full: Removed oldest entry (size: {self._max_cache_size})")
        
        # Stocker dans le cache
        self._cache[key] = geometry_data
        self._access_order.append(key)
        
        logger.info(f"✓ Cached geometry (cache size: {len(self._cache)}/{self._max_cache_size})")
    
    def clear(self):
        """Vide le cache"""
        self._cache.clear()
        self._access_order.clear()
        logger.info("Cache cleared")
