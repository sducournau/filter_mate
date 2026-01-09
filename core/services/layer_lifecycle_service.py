# -*- coding: utf-8 -*-
"""
Layer Lifecycle Service for FilterMate v4.0

Manages the complete lifecycle of layers within FilterMate:
- Layer validation and filtering
- Project initialization and cleanup
- Layer addition/removal handling
- PostgreSQL session cleanup

This service extracts layer management logic from the FilterMateApp god class,
providing a clean separation of concerns following hexagonal architecture principles.

Author: FilterMate Team
Date: January 2026
"""
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
import logging
import weakref
import time

try:
    from qgis.core import QgsVectorLayer, QgsProject
    from qgis.PyQt.QtCore import QTimer
    from qgis.utils import iface
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = Any
    QgsProject = Any

logger = logging.getLogger('FilterMate.LayerLifecycleService')


@dataclass
class LayerLifecycleConfig:
    """Configuration for layer lifecycle operations."""
    postgresql_temp_schema: str = "public"
    auto_cleanup_enabled: bool = True
    signal_debounce_ms: int = 100
    ui_refresh_delay_ms: int = 300
    postgresql_extra_delay_ms: int = 1500
    project_load_delay_ms: int = 2500
    max_postgresql_retries: int = 3


class LayerLifecycleService:
    """
    Service for managing layer lifecycle operations.
    
    Responsibilities:
    - Filter usable layers from project
    - Handle layer addition with PostgreSQL retry logic
    - Manage project initialization and cleanup
    - Clean up PostgreSQL session resources
    - Force layer reload
    
    This service is stateless - all state is passed through method parameters
    or maintained by the app orchestrator (FilterMateApp).
    """
    
    def __init__(self, config: Optional[LayerLifecycleConfig] = None):
        """
        Initialize the layer lifecycle service.
        
        Args:
            config: Optional configuration for lifecycle operations
        """
        self.config = config or LayerLifecycleConfig()
        self._last_layer_change_timestamp = 0
    
    def filter_usable_layers(
        self,
        layers: List[QgsVectorLayer],
        postgresql_available: bool = False
    ) -> List[QgsVectorLayer]:
        """
        Return only layers that are valid vector layers with available sources.
        
        Args:
            layers: List of layers to filter
            postgresql_available: Whether PostgreSQL backend is available
            
        Returns:
            List of usable layers
            
        Notes:
            - Uses is_valid_layer() from object_safety module
            - More permissive with PostgreSQL layers (connection may be initializing)
        """
        from modules.object_safety import is_sip_deleted, is_valid_layer
        from modules.appUtils import is_layer_source_available
        
        try:
            input_count = len(layers or [])
            usable = []
            filtered_reasons = []
            
            logger.info(f"filter_usable_layers: Processing {input_count} layers (POSTGRESQL_AVAILABLE={postgresql_available})")
            
            for l in (layers or []):
                # CRITICAL: Check if C++ object was deleted before any access
                if is_sip_deleted(l):
                    filtered_reasons.append("unknown: C++ object deleted")
                    continue
                    
                if not isinstance(l, QgsVectorLayer):
                    try:
                        name = l.name() if hasattr(l, 'name') else 'unknown'
                    except RuntimeError:
                        name = 'unknown'
                    filtered_reasons.append(f"{name}: not a vector layer")
                    continue
                
                is_postgres = l.providerType() == 'postgres'
                
                # Use object_safety module for comprehensive validation
                if not is_valid_layer(l):
                    try:
                        name = l.name()
                        is_valid_qgis = l.isValid()
                    except RuntimeError:
                        name = 'unknown'
                        is_valid_qgis = False
                    reason = f"{name}: invalid layer (isValid={is_valid_qgis}, C++ object may be deleted)"
                    if is_postgres:
                        reason += " [PostgreSQL]"
                        logger.warning(f"PostgreSQL layer '{name}' failed is_valid_layer check (isValid={is_valid_qgis})")
                    filtered_reasons.append(reason)
                    continue
                
                # For PostgreSQL: if layer is valid, include it even if source check fails
                # The connection may be initializing and will work shortly
                if is_postgres:
                    logger.info(f"PostgreSQL layer '{l.name()}': including despite any source availability issues (will retry connection later)")
                    usable.append(l)
                elif not is_layer_source_available(l, require_psycopg2=False):
                    reason = f"{l.name()}: source not available (provider={l.providerType()})"
                    filtered_reasons.append(reason)
                    continue
                else:
                    usable.append(l)
            
            if filtered_reasons and input_count != len(usable):
                logger.info(f"filter_usable_layers: {input_count} input layers -> {len(usable)} usable layers. Filtered: {len(filtered_reasons)}")
                # Group filtered reasons by type for cleaner logging
                reason_types = {}
                for reason in filtered_reasons:
                    reason_key = reason.split(':')[1].strip() if ':' in reason else reason
                    if reason_key not in reason_types:
                        reason_types[reason_key] = []
                    layer_name = reason.split(':')[0] if ':' in reason else 'unknown'
                    reason_types[reason_key].append(layer_name)
                
                for reason_type, layers_list in reason_types.items():
                    logger.info(f"  Filtered ({reason_type}): {len(layers_list)} layer(s) - {', '.join(layers_list[:5])}{'...' if len(layers_list) > 5 else ''}")
            else:
                logger.info(f"filter_usable_layers: All {input_count} layers are usable")
            
            return usable
        except Exception as e:
            logger.error(f"filter_usable_layers error: {e}", exc_info=True)
            return []
    
    def handle_layers_added(
        self,
        layers: List[QgsVectorLayer],
        postgresql_available: bool,
        add_layers_callback: Callable,
        stability_constants: Dict[str, int]
    ) -> None:
        """
        Handle layersAdded signal: ignore broken/invalid layers.
        
        Args:
            layers: Layers that were added
            postgresql_available: Whether PostgreSQL is available
            add_layers_callback: Callback to trigger add_layers task
            stability_constants: Timing constants for debouncing
            
        Notes:
            - Debounces rapid layer additions
            - Validates all layers before adding
            - Retries PostgreSQL layers that may not be immediately valid
        """
        from modules.object_safety import is_sip_deleted
        from modules.appUtils import validate_and_cleanup_postgres_layers
        from infrastructure.feedback import show_warning
        
        # STABILITY: Debounce rapid layer additions
        current_time = time.time() * 1000
        debounce_ms = stability_constants.get('SIGNAL_DEBOUNCE_MS', 100)
        if current_time - self._last_layer_change_timestamp < debounce_ms:
            logger.debug(f"Debouncing layersAdded signal (elapsed: {current_time - self._last_layer_change_timestamp:.0f}ms < {debounce_ms}ms)")
            # Queue for later processing
            QTimer.singleShot(debounce_ms, lambda: self.handle_layers_added(
                layers, postgresql_available, add_layers_callback, stability_constants
            ))
            return
        self._last_layer_change_timestamp = current_time
        
        # Identify PostgreSQL layers
        all_postgres = [l for l in layers if isinstance(l, QgsVectorLayer) and l.providerType() == 'postgres']
        
        # Warn if PostgreSQL layers without psycopg2
        if all_postgres and not postgresql_available:
            layer_names = ', '.join([l.name() for l in all_postgres[:3]])
            if len(all_postgres) > 3:
                layer_names += f" (+{len(all_postgres) - 3} autres)"
            
            show_warning(
                f"Couches PostgreSQL détectées ({layer_names}) mais psycopg2 n'est pas installé. "
                "Le plugin ne peut pas utiliser ces couches. "
                "Installez psycopg2 pour activer le support PostgreSQL."
            )
            logger.warning(f"FilterMate: Cannot use {len(all_postgres)} PostgreSQL layer(s) - psycopg2 not available")
        
        filtered = self.filter_usable_layers(layers, postgresql_available)
        
        # Identify PostgreSQL layers that failed validation (may be initializing)
        postgres_pending = [l for l in all_postgres 
                          if l.id() not in [f.id() for f in filtered] 
                          and not is_sip_deleted(l)]
        
        if not filtered and not postgres_pending:
            logger.info("FilterMate: Ignoring layersAdded (no usable layers)")
            return
        
        # Validate PostgreSQL layers for orphaned MV references BEFORE adding them
        postgres_to_validate = [l for l in filtered if l.providerType() == 'postgres']
        if postgres_to_validate:
            try:
                cleaned = validate_and_cleanup_postgres_layers(postgres_to_validate)
                if cleaned:
                    logger.info(f"Cleared orphaned MV references from {len(cleaned)} layer(s) during add")
            except Exception as e:
                logger.debug(f"Error validating PostgreSQL layers during add: {e}")
        
        if filtered:
            add_layers_callback(filtered)
        
        # Schedule retry for PostgreSQL layers that may become valid
        if postgres_pending:
            self._schedule_postgresql_retry(
                postgres_pending,
                add_layers_callback,
                stability_constants
            )
    
    def _schedule_postgresql_retry(
        self,
        pending_layers: List[QgsVectorLayer],
        add_layers_callback: Callable,
        stability_constants: Dict[str, int],
        retry_attempt: int = 1
    ) -> None:
        """Schedule retry for PostgreSQL layers that may become valid."""
        from modules.object_safety import is_sip_deleted
        
        logger.info(f"FilterMate: {len(pending_layers)} PostgreSQL layers pending - scheduling retry #{retry_attempt}")
        
        def retry_postgres():
            now_valid = []
            still_pending = []
            for layer in pending_layers:
                try:
                    if is_sip_deleted(layer):
                        continue
                    if layer.isValid():
                        now_valid.append(layer)
                        logger.info(f"PostgreSQL layer '{layer.name()}' is now valid (retry #{retry_attempt})")
                    else:
                        still_pending.append(layer)
                except (RuntimeError, AttributeError):
                    pass
            
            if now_valid:
                logger.info(f"FilterMate: Adding {len(now_valid)} PostgreSQL layers after retry #{retry_attempt}")
                add_layers_callback(now_valid)
            
            # Schedule another retry if layers still pending
            if still_pending and retry_attempt < self.config.max_postgresql_retries:
                self._schedule_postgresql_retry(
                    still_pending,
                    add_layers_callback,
                    stability_constants,
                    retry_attempt + 1
                )
        
        # Retry after PostgreSQL connection establishment delay
        delay = stability_constants.get('POSTGRESQL_EXTRA_DELAY_MS', 1500) * retry_attempt
        QTimer.singleShot(delay, retry_postgres)
    
    def cleanup_postgresql_session_views(
        self,
        session_id: str,
        temp_schema: str,
        project_layers: Dict[str, Any],
        postgresql_available: bool
    ) -> None:
        """
        Clean up all PostgreSQL materialized views created by this session.
        
        Args:
            session_id: Session ID for materialized view isolation
            temp_schema: PostgreSQL schema for temporary objects
            project_layers: Dictionary of project layers
            postgresql_available: Whether PostgreSQL backend is available
            
        Notes:
            - Drops all materialized views prefixed with session_id
            - Uses circuit breaker pattern for stability
            - Called during cleanup() when plugin is unloaded
        """
        if not postgresql_available:
            return
        
        if not session_id:
            return
        
        from infrastructure.resilience import get_postgresql_breaker, CircuitOpenError
        from modules.appUtils import get_datasource_connexion_from_layer
        
        # Check circuit breaker before attempting PostgreSQL operations
        pg_breaker = get_postgresql_breaker()
        if pg_breaker.is_open:
            logger.debug("Skipping PostgreSQL cleanup - circuit breaker is OPEN")
            return
        
        try:
            # Find a PostgreSQL layer to get connection
            connexion = None
            for layer_id, layer_info in project_layers.items():
                layer = layer_info.get('layer')
                if layer and layer.isValid() and layer.providerType() == 'postgres':
                    connexion, _ = get_datasource_connexion_from_layer(layer)
                    if connexion:
                        break
            
            if not connexion:
                logger.debug("No PostgreSQL connection available for session cleanup")
                return
            
            try:
                with connexion.cursor() as cursor:
                    # Find all materialized views for this session
                    cursor.execute("""
                        SELECT matviewname FROM pg_matviews 
                        WHERE schemaname = %s AND matviewname LIKE %s
                    """, (temp_schema, f"mv_{session_id}_%"))
                    views = cursor.fetchall()
                    
                    if views:
                        count = 0
                        for (view_name,) in views:
                            try:
                                # Drop associated index first
                                index_name = f"{temp_schema}_{view_name[3:]}_cluster"  # Remove 'mv_' prefix
                                cursor.execute(f'DROP INDEX IF EXISTS "{index_name}" CASCADE;')
                                # Drop the view
                                cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{temp_schema}"."{view_name}" CASCADE;')
                                count += 1
                            except Exception as e:
                                logger.debug(f"Error dropping view {view_name}: {e}")
                        
                        connexion.commit()
                        if count > 0:
                            logger.info(f"Cleaned up {count} materialized view(s) for session {session_id}")
                
                # Record success for circuit breaker
                pg_breaker.record_success()
            finally:
                try:
                    connexion.close()
                except Exception:
                    pass
                    
        except CircuitOpenError:
            logger.debug("PostgreSQL cleanup skipped - circuit breaker tripped")
        except Exception as e:
            # Record failure for circuit breaker
            pg_breaker.record_failure()
            logger.debug(f"Error during PostgreSQL session cleanup: {e}")
