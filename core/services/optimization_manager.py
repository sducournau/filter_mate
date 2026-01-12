"""
Optimization Manager Service

v4.2: Extracted from FilterMateApp as part of God Class decomposition.

This service manages optimization recommendations and confirmations for
filtering operations. It analyzes layers to determine if optimizations
like centroid usage would benefit performance, and presents options to users.

Key responsibilities:
- Layer analysis for optimization opportunities
- Recommendation generation based on layer characteristics
- User confirmation dialog handling
- UI widget updates when optimizations are applied
"""

from typing import Dict, Tuple, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger('FilterMate')


class OptimizationStatus(Enum):
    """Status of optimization check."""
    DISABLED = "disabled"
    NO_RECOMMENDATIONS = "no_recommendations"
    AUTO_APPLY = "auto_apply"
    USER_APPROVED = "user_approved"
    USER_SKIPPED = "user_skipped"
    ERROR = "error"


@dataclass
class OptimizationResult:
    """Result of optimization check and confirmation."""
    approved_optimizations: Dict[str, Dict[str, bool]]
    auto_apply: bool
    status: OptimizationStatus
    message: str = ""


class OptimizationManager:
    """
    Manages optimization recommendations for filtering operations.
    
    Analyzes layers to identify optimization opportunities and handles
    user confirmation workflow. Extracted from FilterMateApp to reduce
    God Class complexity.
    """
    
    def __init__(
        self,
        get_dockwidget: Callable,
        get_project: Callable,
        get_project_layers: Callable[[], Dict],
    ):
        """
        Initialize OptimizationManager with dependency injection.
        
        Args:
            get_dockwidget: Callback to get current dockwidget instance
            get_project: Callback to get QgsProject instance
            get_project_layers: Callback to get PROJECT_LAYERS dict
        """
        self._get_dockwidget = get_dockwidget
        self._get_project = get_project
        self._get_project_layers = get_project_layers
        
        logger.info("OptimizationManager initialized (v4.2)")
    
    @property
    def dockwidget(self):
        """Get current dockwidget instance."""
        return self._get_dockwidget()
    
    @property
    def project(self):
        """Get current QgsProject instance."""
        return self._get_project()
    
    @property
    def project_layers(self) -> Dict:
        """Get PROJECT_LAYERS dictionary."""
        return self._get_project_layers()
    
    def check_and_confirm_optimizations(
        self, 
        current_layer, 
        task_parameters: Dict
    ) -> Tuple[Dict, bool]:
        """
        Check for optimization opportunities and ask user for confirmation.
        
        Analyzes the layers being filtered and determines if any optimizations
        (like centroid usage) would benefit the operation. If optimizations
        are available and the "ask before apply" setting is enabled, it shows
        a confirmation dialog to the user.
        
        Args:
            current_layer: The source layer for filtering
            task_parameters: The task parameters dictionary
            
        Returns:
            tuple: (approved_optimizations dict, auto_apply_optimizations bool)
        """
        result = self._analyze_and_recommend(current_layer, task_parameters)
        return result.approved_optimizations, result.auto_apply
    
    def _analyze_and_recommend(
        self, 
        current_layer, 
        task_parameters: Dict
    ) -> OptimizationResult:
        """
        Internal method to analyze layers and generate recommendations.
        
        Args:
            current_layer: Source layer for filtering
            task_parameters: Task parameters dictionary
            
        Returns:
            OptimizationResult with recommendations and status
        """
        approved_optimizations = {}
        auto_apply = False
        
        # Check if optimization system is enabled
        if not self._is_optimization_enabled():
            return OptimizationResult(
                approved_optimizations={},
                auto_apply=False,
                status=OptimizationStatus.DISABLED,
                message="Auto-optimization disabled by user setting"
            )
        
        # Check if we should auto-apply without asking
        if self._should_auto_apply():
            return OptimizationResult(
                approved_optimizations={},
                auto_apply=True,
                status=OptimizationStatus.AUTO_APPLY,
                message="Auto-apply optimizations enabled"
            )
        
        # Analyze layers for optimization opportunities
        try:
            from ..core.services.auto_optimizer import (
                LayerAnalyzer, AutoOptimizer, AUTO_OPTIMIZER_AVAILABLE, OptimizationType
            )
            
            if not AUTO_OPTIMIZER_AVAILABLE:
                return OptimizationResult(
                    approved_optimizations={},
                    auto_apply=False,
                    status=OptimizationStatus.DISABLED,
                    message="Auto-optimizer not available"
                )
            
            analyzer = LayerAnalyzer()
            optimizer = AutoOptimizer()
            
            # Collect recommendations
            layers_needing_optimization, distant_layers_recommendations, distant_layers_analyses = \
                self._collect_recommendations(
                    current_layer, task_parameters, analyzer, optimizer, OptimizationType
                )
            
            has_any_recommendations = bool(layers_needing_optimization) or bool(distant_layers_recommendations)
            
            if not has_any_recommendations:
                return OptimizationResult(
                    approved_optimizations={},
                    auto_apply=False,
                    status=OptimizationStatus.NO_RECOMMENDATIONS,
                    message="No optimization recommendations"
                )
            
            # Show confirmation dialog
            result = self._show_confirmation_dialog(
                current_layer, 
                layers_needing_optimization,
                distant_layers_recommendations,
                distant_layers_analyses,
                task_parameters
            )
            
            return result
            
        except ImportError as e:
            logger.debug(f"Auto-optimizer not available: {e}")
            return OptimizationResult(
                approved_optimizations={},
                auto_apply=False,
                status=OptimizationStatus.ERROR,
                message=f"Import error: {e}"
            )
        except Exception as e:
            logger.warning(f"Error in optimization check: {e}")
            return OptimizationResult(
                approved_optimizations={},
                auto_apply=False,
                status=OptimizationStatus.ERROR,
                message=f"Error: {e}"
            )
    
    def _is_optimization_enabled(self) -> bool:
        """Check if optimization system is enabled."""
        dockwidget = self.dockwidget
        if not dockwidget:
            return True
        
        optimization_enabled = getattr(dockwidget, '_optimization_enabled', True)
        centroid_auto = getattr(dockwidget, '_centroid_auto_enabled', True)
        
        if not optimization_enabled:
            logger.debug("Auto-optimization disabled by user setting")
            return False
        
        if not centroid_auto:
            logger.debug("Auto-centroid disabled by user setting")
            return False
        
        return True
    
    def _should_auto_apply(self) -> bool:
        """Check if optimizations should be auto-applied without asking."""
        dockwidget = self.dockwidget
        if not dockwidget:
            return False
        
        ask_before = getattr(dockwidget, '_optimization_ask_before', True)
        if not ask_before:
            logger.info("Auto-apply optimizations enabled (no confirmation dialog)")
            return True
        
        return False
    
    def _collect_recommendations(
        self,
        current_layer,
        task_parameters: Dict,
        analyzer,
        optimizer,
        OptimizationType
    ) -> Tuple[List[Dict], List, List]:
        """
        Collect optimization recommendations for all layers.
        
        Returns:
            Tuple of (layers_needing_optimization, distant_recommendations, distant_analyses)
        """
        layers_needing_optimization = []
        distant_layers_recommendations = []
        distant_layers_analyses = []
        
        # Get task layers and filtering params
        task_layers = task_parameters.get("task", {}).get("layers", [])
        filtering_params = task_parameters.get("filtering", {})
        has_buffer = filtering_params.get("has_buffer_value", False)
        has_buffer_type = filtering_params.get("has_buffer_type", False)
        has_layers_to_filter = filtering_params.get("has_layers_to_filter", False)
        layers_to_filter_ids = filtering_params.get("layers_to_filter", [])
        
        # Check if distant layers centroid is already enabled
        distant_centroid_enabled = self._is_distant_centroid_enabled()
        
        # Analyze distant layers for centroid optimization
        if has_layers_to_filter and layers_to_filter_ids and not distant_centroid_enabled:
            for distant_layer_id in layers_to_filter_ids:
                distant_layer = self.project.mapLayer(distant_layer_id)
                if distant_layer and distant_layer.isValid():
                    distant_analysis = analyzer.analyze_layer(distant_layer)
                    if distant_analysis:
                        distant_layers_analyses.append(distant_analysis)
            
            if distant_layers_analyses:
                distant_centroid_rec = optimizer.evaluate_distant_layers_centroid(
                    distant_layers_analyses,
                    user_already_enabled=distant_centroid_enabled
                )
                if distant_centroid_rec:
                    distant_layers_recommendations.append(distant_centroid_rec)
                    logger.debug(f"Distant layers centroid recommended: {distant_centroid_rec.reason}")
        
        # Analyze target layers
        for layer_props in task_layers:
            layer_id = layer_props.get("layer_id")
            if not layer_id:
                continue
            
            layer = self.project.mapLayer(layer_id)
            if not layer or not layer.isValid():
                continue
            
            analysis = analyzer.analyze_layer(layer)
            if not analysis:
                continue
            
            # Check if centroid already enabled
            user_centroid_enabled = self._is_layer_centroid_enabled(layer)
            
            # Get recommendations
            recommendations = optimizer.get_recommendations(
                analysis,
                user_centroid_enabled=user_centroid_enabled,
                has_buffer=has_buffer,
                has_buffer_type=has_buffer_type,
                is_source_layer=False
            )
            
            # Check for significant recommendations
            has_significant = any(
                rec.auto_applicable and rec.optimization_type in (
                    OptimizationType.USE_CENTROID_DISTANT,
                    OptimizationType.ENABLE_BUFFER_TYPE
                )
                for rec in recommendations
            )
            
            if has_significant:
                layers_needing_optimization.append({
                    'layer': layer,
                    'layer_id': layer_id,
                    'analysis': analysis,
                    'recommendations': recommendations
                })
        
        return layers_needing_optimization, distant_layers_recommendations, distant_layers_analyses
    
    def _is_distant_centroid_enabled(self) -> bool:
        """Check if distant layers centroid is already enabled."""
        dockwidget = self.dockwidget
        if not dockwidget:
            return False
        
        if hasattr(dockwidget, 'checkBox_filtering_use_centroids_distant_layers'):
            return dockwidget.checkBox_filtering_use_centroids_distant_layers.isChecked()
        elif hasattr(dockwidget, 'checkBox_filtering_use_centroids_source_layer'):
            return dockwidget.checkBox_filtering_use_centroids_source_layer.isChecked()
        
        return False
    
    def _is_layer_centroid_enabled(self, layer) -> bool:
        """Check if centroid is already enabled for a specific layer."""
        dockwidget = self.dockwidget
        if not dockwidget:
            return False
        
        if hasattr(dockwidget, '_is_centroid_already_enabled'):
            return dockwidget._is_centroid_already_enabled(layer)
        
        return False
    
    def _show_confirmation_dialog(
        self,
        current_layer,
        layers_needing_optimization: List[Dict],
        distant_layers_recommendations: List,
        distant_layers_analyses: List,
        task_parameters: Dict
    ) -> OptimizationResult:
        """
        Show confirmation dialog and process user response.
        
        Returns:
            OptimizationResult with user's choices
        """
        from ...ui.dialogs.optimization_dialog import RecommendationDialog as OptimizationRecommendationDialog
        
        # Build dialog parameters
        recommendations = []
        dialog_layer_name = current_layer.name()
        dialog_feature_count = 0
        dialog_location_type = "local_file"
        
        if layers_needing_optimization:
            first_layer_info = layers_needing_optimization[0]
            analysis = first_layer_info['analysis']
            recommendations = list(first_layer_info['recommendations'])
            dialog_feature_count = analysis.feature_count
            dialog_location_type = analysis.location_type.value
        
        # Add distant layer recommendations
        if distant_layers_recommendations:
            recommendations.extend(distant_layers_recommendations)
            
            if not layers_needing_optimization:
                layers_to_filter_ids = task_parameters.get("filtering", {}).get("layers_to_filter", [])
                total_features = sum(
                    self.project.mapLayer(lid).featureCount()
                    for lid in layers_to_filter_ids
                    if self.project.mapLayer(lid) and self.project.mapLayer(lid).isValid()
                )
                dialog_feature_count = total_features
                if distant_layers_analyses:
                    dialog_location_type = distant_layers_analyses[0].location_type.value
        
        # Deduplicate recommendations
        recommendations = self._deduplicate_recommendations(recommendations)
        
        total_count = len(layers_needing_optimization) + (1 if distant_layers_recommendations else 0)
        logger.info(f"Found {total_count} optimization recommendation(s)")
        
        # Show dialog
        dialog = OptimizationRecommendationDialog(
            layer_name=dialog_layer_name,
            recommendations=[r.to_dict() for r in recommendations],
            feature_count=dialog_feature_count,
            location_type=dialog_location_type,
            parent=self.dockwidget
        )
        
        result = dialog.exec_()
        
        if result:
            selected = dialog.get_selected_optimizations()
            approved_optimizations = {}
            
            for layer_info in layers_needing_optimization:
                approved_optimizations[layer_info['layer_id']] = selected
            
            # Apply to UI widgets
            self.apply_optimization_to_ui_widgets(selected)
            
            # Handle remember preference
            if dialog.should_remember():
                self._store_optimization_choices(layers_needing_optimization, selected)
            
            logger.info(f"User approved optimizations: {approved_optimizations}")
            
            return OptimizationResult(
                approved_optimizations=approved_optimizations,
                auto_apply=False,
                status=OptimizationStatus.USER_APPROVED,
                message="User approved optimizations"
            )
        else:
            logger.info("User skipped optimizations")
            return OptimizationResult(
                approved_optimizations={},
                auto_apply=False,
                status=OptimizationStatus.USER_SKIPPED,
                message="User skipped optimizations"
            )
    
    def _deduplicate_recommendations(self, recommendations: List) -> List:
        """Deduplicate recommendations, keeping highest speedup for each type."""
        deduped = {}
        for rec in recommendations:
            opt_type = rec.optimization_type.value if hasattr(rec.optimization_type, 'value') else str(rec.optimization_type)
            if opt_type not in deduped or rec.estimated_speedup > deduped[opt_type].estimated_speedup:
                deduped[opt_type] = rec
        return list(deduped.values())
    
    def _store_optimization_choices(self, layers_needing_optimization: List[Dict], selected: Dict):
        """Store optimization choices in dockwidget for session persistence."""
        dockwidget = self.dockwidget
        if not dockwidget:
            return
        
        if not hasattr(dockwidget, '_session_optimization_choices'):
            dockwidget._session_optimization_choices = {}
        
        for layer_info in layers_needing_optimization:
            dockwidget._session_optimization_choices[layer_info['layer_id']] = selected
    
    def apply_optimization_to_ui_widgets(self, selected_optimizations: Dict):
        """
        Apply accepted optimization choices to UI widgets.
        
        When user accepts optimizations in the confirmation dialog, this method
        updates the corresponding checkboxes and other UI controls.
        
        Args:
            selected_optimizations: Dict of {optimization_type: bool} choices
        """
        dockwidget = self.dockwidget
        if not dockwidget or not selected_optimizations:
            return
        
        try:
            # Handle centroid optimization for distant layers
            if selected_optimizations.get('use_centroid_distant', False):
                self._apply_centroid_optimization(dockwidget)
            
            # Handle buffer type optimization
            if selected_optimizations.get('enable_buffer_type', False):
                self._apply_buffer_optimization(dockwidget)
            
            logger.debug(f"Applied optimization choices to UI: {selected_optimizations}")
            
        except Exception as e:
            logger.warning(f"Error applying optimizations to UI widgets: {e}")
    
    def _apply_centroid_optimization(self, dockwidget):
        """Apply centroid optimization to UI widgets."""
        # Update distant layers centroid checkbox
        if hasattr(dockwidget, 'checkBox_filtering_use_centroids_distant_layers'):
            if not dockwidget.checkBox_filtering_use_centroids_distant_layers.isChecked():
                dockwidget.checkBox_filtering_use_centroids_distant_layers.setChecked(True)
                logger.info("AUTO-OPTIMIZATION: Enabled 'use_centroids_distant_layers' checkbox")
        
        # Update PROJECT_LAYERS
        if hasattr(dockwidget, 'current_layer') and dockwidget.current_layer:
            layer_id = dockwidget.current_layer.id()
            project_layers = self.project_layers
            if layer_id in project_layers:
                if "filtering" not in project_layers[layer_id]:
                    project_layers[layer_id]["filtering"] = {}
                project_layers[layer_id]["filtering"]["use_centroids_distant_layers"] = True
                logger.debug(f"AUTO-OPTIMIZATION: Updated PROJECT_LAYERS for {layer_id}")
    
    def _apply_buffer_optimization(self, dockwidget):
        """Apply buffer type optimization to UI widgets."""
        # Enable buffer type toggle
        if hasattr(dockwidget, 'pushButton_checkable_filtering_buffer_type'):
            if not dockwidget.pushButton_checkable_filtering_buffer_type.isChecked():
                dockwidget.pushButton_checkable_filtering_buffer_type.setChecked(True)
                logger.info("AUTO-OPTIMIZATION: Enabled 'buffer_type' toggle button")
        
        # Set buffer type to "Flat"
        if hasattr(dockwidget, 'comboBox_filtering_buffer_type'):
            flat_index = dockwidget.comboBox_filtering_buffer_type.findText("Flat")
            if flat_index >= 0:
                dockwidget.comboBox_filtering_buffer_type.setCurrentIndex(flat_index)
                logger.info("AUTO-OPTIMIZATION: Set buffer type to 'Flat'")
        
        # Set buffer segments to 1
        if hasattr(dockwidget, 'mQgsSpinBox_filtering_buffer_segments'):
            dockwidget.mQgsSpinBox_filtering_buffer_segments.setValue(1)
            logger.info("AUTO-OPTIMIZATION: Set buffer segments to 1")
        
        # Update PROJECT_LAYERS
        if hasattr(dockwidget, 'current_layer') and dockwidget.current_layer:
            layer_id = dockwidget.current_layer.id()
            project_layers = self.project_layers
            if layer_id in project_layers:
                if "filtering" not in project_layers[layer_id]:
                    project_layers[layer_id]["filtering"] = {}
                project_layers[layer_id]["filtering"]["has_buffer_type"] = True
                project_layers[layer_id]["filtering"]["buffer_type"] = "Flat"
                project_layers[layer_id]["filtering"]["buffer_segments"] = 1
                logger.debug(f"AUTO-OPTIMIZATION: Updated buffer params for {layer_id}")
