"""
Filter Application Service for FilterMate.

Sprint 17: Extracted from FilterMateApp.apply_subset_filter() to reduce God Class.

This service handles the application and removal of subset filters on layers,
including history management and Spatialite database operations.
"""
import logging
from typing import Optional, Callable, Any

try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = None

try:
    from infrastructure.utils import is_layer_source_available, safe_set_subset_string
except ImportError:
    def is_layer_source_available(layer, require_psycopg2=False):
        return layer is not None and hasattr(layer, 'isValid') and layer.isValid()
    def safe_set_subset_string(layer, expr):
        if layer:
            layer.setSubsetString(expr)

try:
    from infrastructure.logging import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class FilterApplicationService:
    """
    Service for applying and removing subset filters on layers.
    
    Features:
    - Apply filter from Spatialite database history
    - Unfilter using history manager undo
    - Reset (clear) filters completely
    - Manages PROJECT_LAYERS is_already_subset flag
    
    Extracted from FilterMateApp.apply_subset_filter() in Sprint 17.
    """
    
    def __init__(
        self,
        history_manager,
        get_spatialite_connection: Callable[[], Any],
        get_project_uuid: Callable[[], str],
        get_project_layers: Callable[[], dict],
        show_warning: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize FilterApplicationService.
        
        Args:
            history_manager: HistoryManager instance for undo/redo
            get_spatialite_connection: Callback to get Spatialite connection
            get_project_uuid: Callback to get current project UUID
            get_project_layers: Callback to get PROJECT_LAYERS dict
            show_warning: Optional callback to show warning messages
        """
        self._history_manager = history_manager
        self._get_spatialite_connection = get_spatialite_connection
        self._get_project_uuid = get_project_uuid
        self._get_project_layers = get_project_layers
        self._show_warning = show_warning or self._default_warning
    
    def _default_warning(self, title: str, message: str):
        """Default warning handler using logger."""
        logger.warning(f"{title}: {message}")
    
    def apply_subset_filter(
        self,
        task_name: str,
        layer: 'QgsVectorLayer'
    ) -> bool:
        """
        Apply or remove subset filter expression on a layer.
        
        Uses FilterHistory module for proper undo/redo functionality.
        
        Args:
            task_name: Type of operation ('filter', 'unfilter', 'reset')
            layer: Layer to apply filter to
            
        Returns:
            True if operation succeeded, False otherwise
            
        Notes:
            - For 'unfilter': Uses history.undo() to return to previous state
            - For 'reset': Clears subset string and history
            - For 'filter': Applies expression from Spatialite database
        """
        # Guard: ensure layer is usable
        if not is_layer_source_available(layer):
            logger.warning("apply_subset_filter called on invalid/missing-source layer; skipping.")
            self._show_warning(
                "FilterMate",
                "La couche est invalide ou sa source est introuvable. Opération annulée."
            )
            return False
        
        project_layers = self._get_project_layers()
        layer_id = layer.id()
        
        if task_name == 'unfilter':
            return self._handle_unfilter(layer, project_layers)
        elif task_name in ('filter', 'reset'):
            return self._handle_filter_or_reset(task_name, layer, project_layers)
        else:
            logger.warning(f"Unknown task_name for apply_subset_filter: {task_name}")
            return False
    
    def _handle_unfilter(
        self,
        layer: 'QgsVectorLayer',
        project_layers: dict
    ) -> bool:
        """Handle unfilter operation using history undo."""
        layer_id = layer.id()
        
        # Clear Spatialite cache for this layer when unfiltering
        try:
            from infrastructure.cache import get_cache
            cache = get_cache()
            cache.clear_layer_cache(layer_id)
            logger.debug(f"FilterMate: Cleared Spatialite cache for {layer.name()}")
        except Exception as e:
            logger.debug(f"Could not clear Spatialite cache: {e}")
        
        # Use history manager for proper undo
        history = self._history_manager.get_history(layer_id)
        
        if history and history.can_undo():
            previous_state = history.undo()
            if previous_state:
                safe_set_subset_string(layer, previous_state.expression)
                logger.info(f"FilterMate: Undo applied - restored filter: {previous_state.description}")
                
                self._update_subset_flag(project_layers, layer_id, layer.subsetString() != '')
                return True
        
        # No history available - clear filter
        logger.info("FilterMate: No undo history available, clearing filter")
        safe_set_subset_string(layer, '')
        self._update_subset_flag(project_layers, layer_id, False)
        return True
    
    def _handle_filter_or_reset(
        self,
        task_name: str,
        layer: 'QgsVectorLayer',
        project_layers: dict
    ) -> bool:
        """Handle filter or reset operation using database history."""
        conn = self._get_spatialite_connection()
        if conn is None:
            logger.warning("Cannot apply filter: Spatialite connection unavailable")
            return False
        
        layer_id = layer.id()
        project_uuid = self._get_project_uuid()
        
        with conn:
            cur = conn.cursor()
            last_subset_string = ''
            
            # Use parameterized query to prevent SQL injection
            cur.execute(
                """SELECT * FROM fm_subset_history 
                   WHERE fk_project = ? AND layer_id = ? 
                   ORDER BY seq_order DESC LIMIT 1""",
                (str(project_uuid), layer_id)
            )
            
            results = cur.fetchall()
            
            if len(results) == 1:
                result = results[0]
                last_subset_string = result[6].replace("\'\'", "\'")
            
            if task_name == 'filter':
                safe_set_subset_string(layer, last_subset_string)
                self._update_subset_flag(project_layers, layer_id, layer.subsetString() != '')
            elif task_name == 'reset':
                safe_set_subset_string(layer, '')
                self._update_subset_flag(project_layers, layer_id, False)
        
        return True
    
    def _update_subset_flag(
        self,
        project_layers: dict,
        layer_id: str,
        is_subset: bool
    ) -> None:
        """Update is_already_subset flag in PROJECT_LAYERS."""
        if layer_id in project_layers and "infos" in project_layers[layer_id]:
            project_layers[layer_id]["infos"]["is_already_subset"] = is_subset
