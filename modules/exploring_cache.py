"""
Exploring Features Cache Module

Cache pour les features d'exploration sélectionnées.
Ce module met en cache les features et leurs bounding boxes
pour éviter de recalculer lors des opérations de clignotement (flash),
zoom vers bounding box, et identification.

Architecture:
    - Cache par layer_id avec sous-clés par groupbox type
    - Stocke les features, l'expression, et la bounding box pré-calculée
    - Invalidation automatique sur changement de sélection ou de groupbox
    
Performance:
    - Évite les appels répétés à get_current_features() 
    - Pré-calcule la bounding box pour zoom instantané
    - Cache les feature IDs pour flash sans re-fetch

Usage:
    cache = ExploringFeaturesCache()
    
    # Mise en cache après sélection
    cache.put(layer_id, groupbox_type, features, expression)
    
    # Récupération
    cached = cache.get(layer_id, groupbox_type)
    if cached:
        features = cached['features']
        bbox = cached['bbox']
        expression = cached['expression']
    
    # Invalidation sur changement
    cache.invalidate(layer_id, groupbox_type)  # Invalide un groupbox spécifique
    cache.invalidate_layer(layer_id)  # Invalide tout le layer

Author: FilterMate Team
Version: 2.5.7 (December 2025)
"""

import logging
import os
import time
from typing import Dict, List, Optional, Any

from qgis.core import QgsFeature, QgsRectangle

from .logging_config import setup_logger
from ..config.config import ENV_VARS

# Setup logger
log_path = os.path.join(
    ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."),
    'logs',
    'filtermate_exploring.log'
)
logger = setup_logger('FilterMate.ExploringCache', log_path, level=logging.DEBUG)


class CacheEntry:
    """
    Représente une entrée de cache pour une sélection d'exploration.
    
    Attributes:
        features: Liste des QgsFeature sélectionnées
        feature_ids: Liste des IDs pour un accès rapide (flash)
        expression: Expression QGIS utilisée pour la sélection
        bbox: Bounding box pré-calculée pour zoom
        timestamp: Horodatage de création pour expiration
        hit_count: Nombre d'accès au cache (statistiques)
    """
    
    __slots__ = ['features', 'feature_ids', 'expression', 'bbox', 'timestamp', 'hit_count']
    
    def __init__(self, features: List[QgsFeature], expression: Optional[str] = None):
        """
        Initialise une entrée de cache.
        
        Args:
            features: Liste des features à mettre en cache
            expression: Expression QGIS utilisée pour la sélection
        """
        self.features = features
        self.feature_ids = [f.id() for f in features if f and hasattr(f, 'id')]
        self.expression = expression
        self.bbox = self._compute_bbox(features)
        self.timestamp = time.time()
        self.hit_count = 0
    
    def _compute_bbox(self, features: List[QgsFeature]) -> Optional[QgsRectangle]:
        """
        Calcule la bounding box combinée de toutes les features.
        
        Args:
            features: Liste des features
            
        Returns:
            QgsRectangle: Bounding box combinée, ou None si pas de géométrie
        """
        if not features:
            return None
            
        bbox = QgsRectangle()
        
        for feature in features:
            if feature and hasattr(feature, 'hasGeometry') and feature.hasGeometry():
                geom = feature.geometry()
                if not geom.isEmpty():
                    if bbox.isEmpty():
                        bbox = geom.boundingBox()
                    else:
                        bbox.combineExtentWith(geom.boundingBox())
        
        return bbox if not bbox.isEmpty() else None
    
    def is_valid(self) -> bool:
        """Vérifie si l'entrée de cache contient des données valides."""
        return len(self.features) > 0
    
    def is_expired(self, max_age_seconds: float = 300.0) -> bool:
        """
        Vérifie si l'entrée de cache est expirée.
        
        Args:
            max_age_seconds: Durée maximale de validité en secondes (défaut: 5 minutes)
            
        Returns:
            bool: True si expirée
        """
        return (time.time() - self.timestamp) > max_age_seconds
    
    def touch(self):
        """Met à jour le timestamp et incrémente le compteur d'accès."""
        self.timestamp = time.time()
        self.hit_count += 1


class ExploringFeaturesCache:
    """
    Cache pour les features d'exploration par layer et groupbox.
    
    Structure du cache:
        {
            layer_id: {
                'single_selection': CacheEntry,
                'multiple_selection': CacheEntry,
                'custom_selection': CacheEntry
            }
        }
    
    Features:
        - Cache LRU avec expiration automatique
        - Pré-calcul des bounding boxes
        - Statistiques d'utilisation
        - Invalidation ciblée ou globale
    """
    
    # Types de groupbox supportés
    GROUPBOX_TYPES = ('single_selection', 'multiple_selection', 'custom_selection')
    
    def __init__(self, max_layers: int = 50, max_age_seconds: float = 300.0):
        """
        Initialise le cache d'exploration.
        
        Args:
            max_layers: Nombre maximum de layers à cacher (défaut: 50)
            max_age_seconds: Durée de vie des entrées en secondes (défaut: 5 min)
        """
        self._cache: Dict[str, Dict[str, CacheEntry]] = {}
        self._access_order: List[str] = []  # Pour LRU
        self._max_layers = max_layers
        self._max_age = max_age_seconds
        
        # Statistiques
        self._stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0,
            'expirations': 0
        }
        
        logger.info(f"✓ ExploringFeaturesCache initialized (max_layers={max_layers}, max_age={max_age_seconds}s)")
    
    def _get_cache_key(self, layer_id: str) -> str:
        """Génère une clé de cache à partir de l'ID de layer."""
        return str(layer_id)
    
    def _evict_if_needed(self):
        """Évince les entrées les plus anciennes si le cache est plein."""
        while len(self._cache) >= self._max_layers and self._access_order:
            oldest_layer = self._access_order.pop(0)
            if oldest_layer in self._cache:
                del self._cache[oldest_layer]
                logger.debug(f"Cache eviction: layer {oldest_layer[:8]}...")
    
    def _update_access_order(self, layer_id: str):
        """Met à jour l'ordre d'accès LRU."""
        key = self._get_cache_key(layer_id)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def get(self, layer_id: str, groupbox_type: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les features en cache pour un layer et groupbox.
        
        Args:
            layer_id: ID du layer
            groupbox_type: Type de groupbox ('single_selection', 'multiple_selection', 'custom_selection')
            
        Returns:
            dict ou None: Dictionnaire avec 'features', 'feature_ids', 'expression', 'bbox'
                         ou None si non trouvé/expiré
        """
        key = self._get_cache_key(layer_id)
        
        if key not in self._cache:
            self._stats['misses'] += 1
            return None
        
        layer_cache = self._cache[key]
        
        if groupbox_type not in layer_cache:
            self._stats['misses'] += 1
            return None
        
        entry = layer_cache[groupbox_type]
        
        # Vérifier l'expiration
        if entry.is_expired(self._max_age):
            self._stats['expirations'] += 1
            del layer_cache[groupbox_type]
            logger.debug(f"Cache expired: {layer_id[:8]}.../{groupbox_type}")
            return None
        
        # Cache hit!
        self._stats['hits'] += 1
        entry.touch()
        self._update_access_order(layer_id)
        
        logger.debug(f"Cache HIT: {layer_id[:8]}.../{groupbox_type} ({len(entry.features)} features)")
        
        return {
            'features': entry.features,
            'feature_ids': entry.feature_ids,
            'expression': entry.expression,
            'bbox': entry.bbox
        }
    
    def put(self, layer_id: str, groupbox_type: str, features: List[QgsFeature], 
            expression: Optional[str] = None) -> bool:
        """
        Met en cache les features pour un layer et groupbox.
        
        Args:
            layer_id: ID du layer
            groupbox_type: Type de groupbox
            features: Liste des features à cacher
            expression: Expression QGIS associée
            
        Returns:
            bool: True si mise en cache réussie
        """
        if groupbox_type not in self.GROUPBOX_TYPES:
            logger.warning(f"Invalid groupbox type: {groupbox_type}")
            return False
        
        if not features:
            logger.debug(f"Empty features list, not caching: {layer_id[:8]}.../{groupbox_type}")
            return False
        
        key = self._get_cache_key(layer_id)
        
        # Éviction LRU si nécessaire
        if key not in self._cache:
            self._evict_if_needed()
            self._cache[key] = {}
        
        # Créer l'entrée de cache
        entry = CacheEntry(features, expression)
        self._cache[key][groupbox_type] = entry
        self._update_access_order(layer_id)
        
        bbox_info = f"bbox={entry.bbox.toString()}" if entry.bbox else "no bbox"
        logger.debug(f"Cache PUT: {layer_id[:8]}.../{groupbox_type} ({len(features)} features, {bbox_info})")
        
        return True
    
    def invalidate(self, layer_id: str, groupbox_type: Optional[str] = None):
        """
        Invalide le cache pour un layer et optionnellement un groupbox spécifique.
        
        Args:
            layer_id: ID du layer
            groupbox_type: Type de groupbox (None = tous les groupboxes du layer)
        """
        key = self._get_cache_key(layer_id)
        
        if key not in self._cache:
            return
        
        if groupbox_type:
            if groupbox_type in self._cache[key]:
                del self._cache[key][groupbox_type]
                self._stats['invalidations'] += 1
                logger.debug(f"Cache invalidated: {layer_id[:8]}.../{groupbox_type}")
        else:
            # Invalider tous les groupboxes du layer
            count = len(self._cache[key])
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            self._stats['invalidations'] += count
            logger.debug(f"Cache invalidated: {layer_id[:8]}... (all {count} groupboxes)")
    
    def invalidate_layer(self, layer_id: str):
        """Alias pour invalidate avec tous les groupboxes."""
        self.invalidate(layer_id, None)
    
    def invalidate_all(self):
        """Invalide tout le cache."""
        count = sum(len(v) for v in self._cache.values())
        self._cache.clear()
        self._access_order.clear()
        self._stats['invalidations'] += count
        logger.info(f"Cache cleared: {count} entries invalidated")
    
    def has_cached_data(self, layer_id: str, groupbox_type: str) -> bool:
        """
        Vérifie si des données sont en cache (sans les récupérer).
        
        Args:
            layer_id: ID du layer
            groupbox_type: Type de groupbox
            
        Returns:
            bool: True si des données valides sont en cache
        """
        key = self._get_cache_key(layer_id)
        
        if key not in self._cache or groupbox_type not in self._cache[key]:
            return False
        
        entry = self._cache[key][groupbox_type]
        return entry.is_valid() and not entry.is_expired(self._max_age)
    
    def get_bbox(self, layer_id: str, groupbox_type: str) -> Optional[QgsRectangle]:
        """
        Récupère uniquement la bounding box en cache (accès rapide pour zoom).
        
        Args:
            layer_id: ID du layer
            groupbox_type: Type de groupbox
            
        Returns:
            QgsRectangle ou None: Bounding box pré-calculée
        """
        cached = self.get(layer_id, groupbox_type)
        return cached['bbox'] if cached else None
    
    def get_feature_ids(self, layer_id: str, groupbox_type: str) -> List[int]:
        """
        Récupère uniquement les IDs de features (accès rapide pour flash).
        
        Args:
            layer_id: ID du layer
            groupbox_type: Type de groupbox
            
        Returns:
            list: Liste des feature IDs, ou liste vide
        """
        cached = self.get(layer_id, groupbox_type)
        return cached['feature_ids'] if cached else []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques d'utilisation du cache.
        
        Returns:
            dict: Statistiques (hits, misses, invalidations, etc.)
        """
        total = self._stats['hits'] + self._stats['misses']
        hit_ratio = (self._stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total,
            'hit_ratio': f"{hit_ratio:.1f}%",
            'cached_layers': len(self._cache),
            'total_entries': sum(len(v) for v in self._cache.values())
        }
    
    def cleanup_expired(self):
        """Nettoie les entrées expirées du cache."""
        expired_count = 0
        layers_to_remove = []
        
        for layer_id, layer_cache in self._cache.items():
            expired_groupboxes = [
                gb for gb, entry in layer_cache.items() 
                if entry.is_expired(self._max_age)
            ]
            
            for gb in expired_groupboxes:
                del layer_cache[gb]
                expired_count += 1
            
            if not layer_cache:
                layers_to_remove.append(layer_id)
        
        for layer_id in layers_to_remove:
            del self._cache[layer_id]
            if layer_id in self._access_order:
                self._access_order.remove(layer_id)
        
        if expired_count > 0:
            self._stats['expirations'] += expired_count
            logger.debug(f"Cleanup: {expired_count} expired entries removed")
    
    def __str__(self) -> str:
        """Représentation textuelle du cache."""
        stats = self.get_stats()
        return f"ExploringFeaturesCache({stats['cached_layers']} layers, {stats['total_entries']} entries, {stats['hit_ratio']} hit rate)"
    
    def __repr__(self) -> str:
        return self.__str__()


# Singleton instance pour usage global (optionnel)
_global_cache: Optional[ExploringFeaturesCache] = None


def get_exploring_cache() -> ExploringFeaturesCache:
    """
    Retourne l'instance globale du cache d'exploration.
    
    Returns:
        ExploringFeaturesCache: Instance singleton du cache
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = ExploringFeaturesCache()
    return _global_cache


def reset_exploring_cache():
    """Réinitialise l'instance globale du cache."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.invalidate_all()
    _global_cache = ExploringFeaturesCache()
