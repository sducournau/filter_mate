"""
Performance Advisor Module

EPIC-1 Phase E7.5: Extracted from modules/tasks/filter_task.py

Provides contextual performance warnings and recommendations based on:
- Current backend (PostgreSQL, Spatialite, OGR)
- Query duration
- Dataset size

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase E7.5)
"""

import logging
from typing import Optional

logger = logging.getLogger('FilterMate.Core.Optimization.PerformanceAdvisor')


def get_contextual_performance_warning(
    elapsed_time: float,
    provider_type: str,
    postgresql_available: bool = True,
    severity: str = 'warning'
) -> Optional[str]:
    """
    Generate contextual performance warning based on current backend.

    Provides relevant advice based on current backend instead of always suggesting PostgreSQL.

    Args:
        elapsed_time: Query duration in seconds
        provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
        postgresql_available: Whether PostgreSQL/psycopg2 is available
        severity: 'warning' or 'critical'

    Returns:
        Contextual warning message string, or None if no warning needed
    """
    is_postgresql = postgresql_available and provider_type == 'postgresql'
    is_spatialite = provider_type == 'spatialite'
    is_ogr = provider_type == 'ogr'

    # Base message with timing
    base_msg = f"La requête de filtrage a pris {elapsed_time:.1f}s"

    if is_postgresql:
        # Already using PostgreSQL - suggest complexity reduction
        if severity == 'critical':
            return (
                f"{base_msg} (backend: PostgreSQL). "
                "Pour améliorer les performances, vous pouvez: "
                "réduire le rayon du buffer, limiter le nombre de couches, "
                "ou créer des index spatiaux sur les tables concernées."
            )
        else:
            return (
                f"{base_msg} (backend: PostgreSQL). "
                "Temps normal pour une requête complexe. "
                "Vérifiez vos index spatiaux si les performances restent lentes."
            )
    elif is_spatialite:
        # Using Spatialite - suggest PostgreSQL for large datasets
        if severity == 'critical':
            return (
                f"{base_msg} (backend: Spatialite). "
                "Pour de meilleures performances, considérez: "
                "PostgreSQL/PostGIS pour les grands jeux de données, "
                "ou réduisez la complexité du filtre."
            )
        else:
            return (
                f"{base_msg} (backend: Spatialite). "
                "Performances acceptables. PostgreSQL/PostGIS serait plus rapide "
                "pour les requêtes fréquentes sur ce jeu de données."
            )
    elif is_ogr:
        # Using OGR fallback - suggest optimized backend
        if severity == 'critical':
            return (
                f"{base_msg} (backend: OGR/mémoire). "
                "Pour de meilleures performances, utilisez PostgreSQL/PostGIS "
                "ou Spatialite. Le backend actuel n'est pas optimisé pour les grandes données."
            )
        else:
            return (
                f"{base_msg} (backend: OGR/mémoire). "
                "Considérez PostgreSQL ou GeoPackage (Spatialite) pour de meilleures performances."
            )
    else:
        # Unknown/default backend
        if severity == 'critical':
            return (
                f"{base_msg}. "
                "Pour de meilleures performances, utilisez PostgreSQL/PostGIS "
                "ou réduisez la complexité du filtre."
            )
        else:
            return (
                f"{base_msg}. "
                "Temps de traitement élevé. Vérifiez la taille des données et la complexité du filtre."
            )
