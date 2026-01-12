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
        from ...infrastructure.utils import is_sip_deleted, is_layer_valid as is_valid_layer, is_layer_source_available
        
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
        from ...infrastructure.utils import is_sip_deleted, validate_and_cleanup_postgres_layers
        from ...infrastructure.feedback import show_warning
        
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
        from ...infrastructure.utils import is_sip_deleted
        
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
        
        from ...infrastructure.resilience import get_postgresql_breaker, CircuitOpenError
        from ...infrastructure.utils import get_datasource_connexion_from_layer
        
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
    
    def cleanup(
        self,
        session_id: str,
        temp_schema: str,
        project_layers: Dict[str, Any],
        dockwidget: Any,
        auto_cleanup_enabled: bool,
        postgresql_available: bool
    ) -> None:
        """
        Clean up plugin resources on unload or reload.
        
        Safely removes widgets, clears data structures, and prevents memory leaks.
        Called when plugin is disabled or QGIS is closing.
        
        Args:
            session_id: Session ID for PostgreSQL cleanup
            temp_schema: PostgreSQL temp schema
            project_layers: Dictionary of layers to cleanup
            dockwidget: Reference to dockwidget for UI cleanup
            auto_cleanup_enabled: Whether PostgreSQL auto-cleanup is enabled
            postgresql_available: Whether PostgreSQL is available
            
        Cleanup steps:
            1. Clean up PostgreSQL materialized views for this session
            2. Clear list_widgets from multiple selection widget
            3. Reset async tasks
            4. Clear PROJECT_LAYERS dictionary
            5. Clear datasource connections
        """
        # Clean up PostgreSQL materialized views for this session (if auto-cleanup is enabled)
        if auto_cleanup_enabled:
            self.cleanup_postgresql_session_views(
                session_id=session_id,
                temp_schema=temp_schema,
                project_layers=project_layers,
                postgresql_available=postgresql_available
            )
        else:
            logger.info("PostgreSQL auto-cleanup disabled - session views not cleaned")
        
        if dockwidget is not None:
            # Clean all list_widgets to avoid KeyError
            if hasattr(dockwidget, 'widgets'):
                try:
                    multiple_selection_widget = dockwidget.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                    if multiple_selection_widget and hasattr(multiple_selection_widget, 'list_widgets'):
                        # Clean all list_widgets
                        multiple_selection_widget.list_widgets.clear()
                        # Reset tasks
                        if hasattr(multiple_selection_widget, 'tasks'):
                            multiple_selection_widget.tasks.clear()
                except (KeyError, AttributeError, RuntimeError) as e:
                    # Widgets may already be deleted
                    pass
            
            # Clean PROJECT_LAYERS
            if hasattr(dockwidget, 'PROJECT_LAYERS'):
                dockwidget.PROJECT_LAYERS.clear()
        
        logger.info("Layer lifecycle cleanup completed")
    
    def force_reload_layers(
        self,
        cancel_tasks_callback: Callable,
        reset_flags_callback: Callable,
        init_db_callback: Callable,
        manage_task_callback: Callable,
        project_layers: Dict[str, Any],
        dockwidget: Any,
        stability_constants: Dict[str, int]
    ) -> None:
        """
        Force a complete reload of all layers in the current project.
        
        This method is useful when the dockwidget gets out of sync with the
        current project, or when switching projects doesn't properly reload layers.
        
        Args:
            cancel_tasks_callback: Callback to cancel all tasks
            reset_flags_callback: Callback to reset state flags
            init_db_callback: Callback to reinitialize database
            manage_task_callback: Callback to manage add_layers task (layer_list)
            project_layers: Dictionary to be cleared
            dockwidget: Reference to dockwidget for UI updates
            stability_constants: Timing constants dictionary
            
        Workflow:
            1. Cancel all pending tasks
            2. Reset all state flags
            3. Clear PROJECT_LAYERS
            4. Reinitialize the database
            5. Reload all vector layers from current project
        """
        logger.info("FilterMate: Force reload layers requested")
        
        # 1. Reset all protection flags immediately
        reset_flags_callback()
        
        # 2. Cancel all pending tasks
        cancel_tasks_callback()
        
        # 3. Clear PROJECT_LAYERS
        project_layers.clear()
        
        # 4. Reset dockwidget state
        if dockwidget:
            dockwidget.current_layer = None
            dockwidget.has_loaded_layers = False
            dockwidget.PROJECT_LAYERS = {}
            dockwidget._plugin_busy = False
            dockwidget._updating_layers = False
            
            # Reset combobox to no selection (do NOT call clear() - it breaks the proxy model sync)
            try:
                if hasattr(dockwidget, 'comboBox_filtering_current_layer'):
                    dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    # CRITICAL: Do NOT call clear() on QgsMapLayerComboBox!
                    # It uses QgsMapLayerProxyModel which auto-syncs with project layers.
                    # Calling clear() breaks this synchronization and the combobox stays empty.
            except Exception as e:
                logger.debug(f"Error resetting layer combobox during reload: {e}")
            
            # CRITICAL: Clear QgsFeaturePickerWidget to prevent access violation
            # The widget has an internal timer that triggers scheduledReload which
            # creates QgsVectorLayerFeatureSource - if the layer is invalid/destroyed,
            # this causes a Windows fatal exception (access violation).
            try:
                if hasattr(dockwidget, 'mFeaturePickerWidget_exploring_single_selection'):
                    dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
            except Exception as e:
                logger.debug(f"Error resetting FeaturePickerWidget during reload: {e}")
            
            # Update indicator to show reloading state
            if hasattr(dockwidget, 'backend_indicator_label') and dockwidget.backend_indicator_label:
                dockwidget.backend_indicator_label.setText("⟳")
                dockwidget.backend_indicator_label.setStyleSheet("""
                    QLabel#label_backend_indicator {
                        color: #3498db;
                        font-size: 9pt;
                        font-weight: 600;
                        padding: 3px 10px;
                        border-radius: 12px;
                        border: none;
                        background-color: #e8f4fc;
                    }
                """)
        
        # 5. Reinitialize database
        try:
            init_db_callback()
        except Exception as e:
            logger.error(f"Error reinitializing database during reload: {e}")
        
        # 6. Get all current vector layers and add them
        project = QgsProject.instance()
        current_layers = self.filter_usable_layers(
            list(project.mapLayers().values()),
            postgresql_available=True  # Assume PostgreSQL may be available
        )
        
        if current_layers:
            logger.info(f"FilterMate: Reloading {len(current_layers)} layers")
            
            # Check if any PostgreSQL layers - need longer delay
            has_postgres = any(
                layer.providerType() == 'postgres' 
                for layer in current_layers
            )
            delay = stability_constants.get('UI_REFRESH_DELAY_MS', 300)
            if has_postgres:
                delay += stability_constants.get('POSTGRESQL_EXTRA_DELAY_MS', 1500)
            
            # Use weakref to prevent access violations on plugin unload
            weak_callback = weakref.ref(manage_task_callback)
            def safe_add_layers():
                strong_callback = weak_callback()
                if strong_callback is not None and callable(strong_callback):
                    strong_callback(current_layers)
            
            QTimer.singleShot(delay, safe_add_layers)
        else:
            logger.info("FilterMate: No usable layers to reload")
    
    def handle_remove_all_layers(
        self,
        cancel_tasks_callback: Callable,
        dockwidget: Any
    ) -> None:
        """
        Handle remove all layers event.
        
        Safely cleans up all layer state when all layers are removed from project.
        STABILITY FIX: Properly resets current_layer and has_loaded_layers to prevent
        crashes when accessing invalid layer references.
        
        Args:
            cancel_tasks_callback: Callback to cancel tasks
            dockwidget: Reference to dockwidget for UI cleanup
        """
        cancel_tasks_callback()
        
        # CRITICAL: Check if dockwidget exists before accessing its methods
        if dockwidget is not None:
            # CRITICAL: Reset layer combo box to prevent access violations
            # NOTE: Do NOT call clear() - it breaks the proxy model synchronization
            try:
                if hasattr(dockwidget, 'comboBox_filtering_current_layer'):
                    dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    logger.debug("FilterMate: Layer combo reset during remove_all_layers")
            except Exception as e:
                logger.debug(f"FilterMate: Error resetting layer combo during remove_all_layers: {e}")
            
            # CRITICAL: Reset QgsFeaturePickerWidget to prevent access violation
            # The widget has an internal timer that triggers scheduledReload
            try:
                if hasattr(dockwidget, 'mFeaturePickerWidget_exploring_single_selection'):
                    dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                    logger.debug("FilterMate: FeaturePickerWidget reset during remove_all_layers")
            except Exception as e:
                logger.debug(f"FilterMate: Error resetting FeaturePickerWidget during remove_all_layers: {e}")
            
            # STABILITY FIX: Disconnect LAYER_TREE_VIEW signal to prevent callbacks to invalid layers
            try:
                if hasattr(iface, 'layerTreeView') and iface.layerTreeView():
                    iface.layerTreeView().currentLayerChanged.disconnect(dockwidget.on_layerTreeView_currentLayerChanged)
                    logger.debug("FilterMate: Disconnected layerTreeView signal during remove_all_layers")
            except Exception as e:
                logger.debug(f"FilterMate: Error disconnecting layerTreeView signal during remove_all_layers: {e}")
        
        logger.info("Handle remove all layers completed")
    
    def handle_project_initialization(
        self,
        task_name: str,
        is_initializing: bool,
        is_loading: bool,
        dockwidget: Any,
        check_reset_flags_callback: Callable,
        set_initializing_flag_callback: Callable,
        set_loading_flag_callback: Callable,
        cancel_tasks_callback: Callable,
        init_env_vars_callback: Callable,
        get_project_callback: Callable,
        init_db_callback: Callable,
        manage_task_callback: Callable,
        temp_schema: str,
        stability_constants: Dict[str, int]
    ) -> None:
        """
        Handle project read/new project initialization.
        
        Args:
            task_name: 'project_read' or 'new_project'
            is_initializing: Current initializing flag state
            is_loading: Current loading flag state
            dockwidget: Reference to dockwidget
            check_reset_flags_callback: Callback to check/reset stale flags
            set_initializing_flag_callback: Callback to set initializing flag
            set_loading_flag_callback: Callback to set loading flag
            cancel_tasks_callback: Callback to cancel tasks
            init_env_vars_callback: Callback to init environment variables
            get_project_callback: Callback to get current project
            init_db_callback: Callback to initialize database
            manage_task_callback: Callback to manage add_layers task
            temp_schema: PostgreSQL temp schema
            stability_constants: Timing constants dictionary
        """
        logger.debug(f"_handle_project_initialization called with task_name={task_name}")
        
        # STABILITY FIX: Check and reset stale flags that might block operations
        check_reset_flags_callback()
        
        # CRITICAL: Skip if already initializing to prevent recursive calls
        if is_initializing:
            logger.debug(f"Skipping {task_name} - already initializing project")
            return
        
        # CRITICAL: Skip if currently loading a new project (add_layers in progress)
        if is_loading:
            logger.debug(f"Skipping {task_name} - already loading new project")
            return
        
        # CRITICAL: Skip if dockwidget doesn't exist yet - run() handles initial setup
        if dockwidget is None:
            logger.debug(f"Skipping {task_name} - dockwidget not created yet (run() will handle)")
            return
        
        # Use timestamp-tracked flag setter
        set_initializing_flag_callback(True)
        
        # CRITICAL: Reset layer combo box before project change to prevent access violations
        # NOTE: Do NOT call clear() - it breaks the proxy model synchronization
        if dockwidget is not None:
            try:
                if hasattr(dockwidget, 'comboBox_filtering_current_layer'):
                    dockwidget.comboBox_filtering_current_layer.setLayer(None)
                    logger.debug(f"FilterMate: Layer combo reset before {task_name}")
            except Exception as e:
                logger.debug(f"FilterMate: Error resetting layer combo before {task_name}: {e}")
            
            # CRITICAL: Reset QgsFeaturePickerWidget to prevent access violation
            try:
                if hasattr(dockwidget, 'mFeaturePickerWidget_exploring_single_selection'):
                    dockwidget.mFeaturePickerWidget_exploring_single_selection.setLayer(None)
                    logger.debug(f"FilterMate: FeaturePickerWidget reset before {task_name}")
            except Exception as e:
                logger.debug(f"FilterMate: Error resetting FeaturePickerWidget before {task_name}: {e}")
        
        # STABILITY FIX: Set dockwidget busy flag to prevent concurrent layer changes
        if dockwidget is not None:
            dockwidget._plugin_busy = True
        
        try:
            # Verify project is valid
            project = QgsProject.instance()
            if not project:
                logger.warning(f"Project not available for {task_name}, skipping")
                return
            
            # Callback to reset temp schema flag and cancel tasks
            cancel_tasks_callback()
            
            # Callback to init environment variables
            init_env_vars_callback()
            
            # Get project from callback
            current_project = get_project_callback()
            
            # Verify project is still valid after init
            if not current_project:
                logger.warning(f"Project became invalid during {task_name}, skipping")
                set_loading_flag_callback(False)
                return
            
            # Initialize database
            try:
                init_db_callback()
            except Exception as e:
                logger.error(f"Error initializing database during {task_name}: {e}")
            
            # Use timestamp-tracked flag setter for loading
            set_loading_flag_callback(True)
            
            # Get all vector layers
            all_layers = list(current_project.mapLayers().values())
            usable_layers = self.filter_usable_layers(all_layers, postgresql_available=True)
            
            if usable_layers:
                logger.info(f"FilterMate: {task_name} - loading {len(usable_layers)} layers")
                
                # Schedule add_layers with delay for project load
                delay = stability_constants.get('PROJECT_LOAD_DELAY_MS', 2500)
                
                # Use weakref to prevent access violations
                weak_callback = weakref.ref(manage_task_callback)
                def safe_add_layers():
                    strong_callback = weak_callback()
                    if strong_callback is not None and callable(strong_callback):
                        strong_callback(usable_layers)
                
                QTimer.singleShot(delay, safe_add_layers)
            else:
                logger.info(f"FilterMate: {task_name} - no usable layers found")
                set_loading_flag_callback(False)
        finally:
            set_initializing_flag_callback(False)
            if dockwidget is not None:
                dockwidget._plugin_busy = False

    def schedule_postgres_layer_retry(
        self,
        pending_layers: List[QgsVectorLayer],
        project_layers: dict,
        manage_task_callback: Callable,
        stability_constants: dict,
        max_retries: int = 3
    ) -> None:
        """
        Schedule retry for PostgreSQL layers that may become valid after connection is established.
        
        Sprint 17: Extracted from FilterMateApp._on_layers_added() to reduce God Class.
        
        PostgreSQL layers may not be immediately valid due to connection timing.
        This method schedules retries with increasing delays to handle this case.
        
        Args:
            pending_layers: List of PostgreSQL layers that failed initial validation
            project_layers: PROJECT_LAYERS dict to check if layer was already added
            manage_task_callback: Callback to trigger add_layers task
            stability_constants: Dict with POSTGRESQL_EXTRA_DELAY_MS
            max_retries: Maximum number of retry attempts
        """
        from ...infrastructure.utils import is_sip_deleted
        
        if not pending_layers:
            return
        
        logger.info(f"FilterMate: {len(pending_layers)} PostgreSQL layers pending - scheduling retry")
        
        # Use weakref to prevent access violations
        weak_callback = weakref.ref(manage_task_callback) if hasattr(manage_task_callback, '__self__') else None
        captured_pending = list(pending_layers)
        captured_project_layers = project_layers
        delay_ms = stability_constants.get('POSTGRESQL_EXTRA_DELAY_MS', 1500)
        
        def retry_postgres(retry_attempt: int = 1):
            # Get strong reference to callback
            callback = weak_callback() if weak_callback else manage_task_callback
            if callback is None:
                return
            
            now_valid = []
            still_pending = []
            
            for layer in captured_pending:
                try:
                    if is_sip_deleted(layer):
                        continue
                    if layer.isValid() and layer.id() not in captured_project_layers:
                        now_valid.append(layer)
                        logger.info(f"PostgreSQL layer '{layer.name()}' is now valid (retry #{retry_attempt})")
                    elif not layer.isValid():
                        still_pending.append(layer)
                except (RuntimeError, AttributeError):
                    pass
            
            if now_valid:
                logger.info(f"FilterMate: Adding {len(now_valid)} PostgreSQL layers after retry #{retry_attempt}")
                callback(now_valid)
            
            # Schedule a second retry if layers are still pending
            if still_pending and retry_attempt < max_retries:
                logger.info(f"FilterMate: {len(still_pending)} PostgreSQL layers still not valid - scheduling retry #{retry_attempt + 1}")
                QTimer.singleShot(
                    delay_ms * retry_attempt,
                    lambda: retry_postgres(retry_attempt + 1)
                )
        
        # Retry after PostgreSQL connection establishment delay
        QTimer.singleShot(delay_ms, retry_postgres)

    def validate_and_cleanup_postgres_layers_on_add(
        self,
        layers: List[QgsVectorLayer]
    ) -> List[str]:
        """
        Validate PostgreSQL layers for orphaned MV references BEFORE adding them.
        
        Sprint 17: Extracted from FilterMateApp._on_layers_added() to reduce God Class.
        
        This fixes "relation does not exist" errors when layers with stale filters are added.
        
        Args:
            layers: List of layers being added
            
        Returns:
            List of layer names that were cleaned
        """
        try:
            from ...infrastructure.utils import validate_and_cleanup_postgres_layers
        except ImportError:
            logger.debug("validate_and_cleanup_postgres_layers not available")
            return []
        
        postgres_to_validate = [l for l in layers if l.providerType() == 'postgres']
        if not postgres_to_validate:
            return []
        
        try:
            cleaned = validate_and_cleanup_postgres_layers(postgres_to_validate)
            if cleaned:
                logger.info(f"Cleared orphaned MV references from {len(cleaned)} layer(s) during add")
            return cleaned or []
        except Exception as e:
            logger.debug(f"Error validating PostgreSQL layers during add: {e}")
            return []
