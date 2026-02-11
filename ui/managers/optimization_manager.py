# -*- coding: utf-8 -*-
"""
OptimizationManager - Extracted from filter_mate_dockwidget.py

v5.0 Phase 2 P2-2 E1: Extract optimization/centroid/backend settings management
from God Class (7,130 lines).

Manages:
    - Auto-optimization toggles (enabled, centroid, ask-before)
    - Layer optimization analysis and recommendation dialogs
    - Backend optimization settings and dialogs
    - Centroid detection and override state
    - Optimization state serialization/deserialization

Author: FilterMate Team
Created: February 2026
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class OptimizationManager:
    """
    Manages optimization settings and dialogs for FilterMate dockwidget.

    Extracted from FilterMateDockWidget to reduce God Class complexity.
    This manager handles auto-optimization, centroid settings, backend
    optimization dialogs, and optimization state persistence.

    Args:
        dockwidget: Reference to FilterMateDockWidget instance.
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget'):
        self.dockwidget = dockwidget
        logger.debug("OptimizationManager initialized")

    # ========================================
    # OPTIMIZATION TOGGLES
    # ========================================

    def toggle_optimization_enabled(self):
        """Toggle auto-optimization enabled state. Delegates to BackendController."""
        from ...infrastructure.feedback import show_success, show_info
        dw = self.dockwidget
        if dw._backend_ctrl:
            enabled = dw._backend_ctrl.toggle_optimization_enabled()
            (show_success if enabled else show_info)(
                "FilterMate",
                dw.tr("Auto-optimization {0}").format(
                    dw.tr("enabled") if enabled else dw.tr("disabled")
                )
            )

    def toggle_centroid_auto(self):
        """Toggle auto-centroid enabled state. Delegates to BackendController."""
        from ...infrastructure.feedback import show_success, show_info
        dw = self.dockwidget
        if dw._backend_ctrl:
            enabled = dw._backend_ctrl.toggle_centroid_auto()
            (show_success if enabled else show_info)(
                "FilterMate",
                dw.tr("Auto-centroid {0}").format(
                    dw.tr("enabled") if enabled else dw.tr("disabled")
                )
            )

    def toggle_optimization_ask_before(self):
        """Toggle optimization confirmation dialog."""
        from ...infrastructure.feedback import show_success, show_info
        dw = self.dockwidget
        dw._optimization_ask_before = not getattr(dw, '_optimization_ask_before', True)
        (show_success if dw._optimization_ask_before else show_info)(
            "FilterMate",
            dw.tr("Confirmation {0}").format(
                dw.tr("enabled") if dw._optimization_ask_before else dw.tr("disabled")
            )
        )

    # ========================================
    # LAYER ANALYSIS & RECOMMENDATIONS
    # ========================================

    def analyze_layer_optimizations(self):
        """Analyze current layer and show optimization recommendations."""
        from ...infrastructure.feedback import show_warning, show_info, show_success
        from ...config.config import ENV_VARS, get_optimization_thresholds
        dw = self.dockwidget
        if not dw.current_layer:
            show_warning("FilterMate", dw.tr("No layer selected. Please select a layer first."))
            return
        try:
            from ...core.services.auto_optimizer import (
                LayerAnalyzer, AutoOptimizer, AUTO_OPTIMIZER_AVAILABLE
            )
            if not AUTO_OPTIMIZER_AVAILABLE:
                show_warning("FilterMate", dw.tr("Auto-optimizer module not available"))
                return
            layer_analysis = LayerAnalyzer().analyze_layer(dw.current_layer)
            if not layer_analysis:
                show_info(
                    "FilterMate",
                    dw.tr("Could not analyze layer '{0}'").format(dw.current_layer.name())
                )
                return
            has_buf = (
                getattr(dw, 'mQgsDoubleSpinBox_filtering_buffer_value', None)
                and dw.mQgsDoubleSpinBox_filtering_buffer_value.value() != 0.0
            )
            has_buf_type = (
                getattr(dw, 'checkBox_filtering_buffer_type', None)
                and dw.checkBox_filtering_buffer_type.isChecked()
            )
            recommendations = AutoOptimizer().get_recommendations(
                layer_analysis,
                user_centroid_enabled=self.is_centroid_already_enabled(dw.current_layer),
                has_buffer=has_buf,
                has_buffer_type=has_buf_type,
                is_source_layer=True
            )
            if not recommendations:
                show_success(
                    "FilterMate",
                    dw.tr(
                        "Layer '{0}' is already optimally configured.\n"
                        "Type: {1}\nFeatures: {2:,}"
                    ).format(
                        dw.current_layer.name(),
                        layer_analysis.location_type.value,
                        layer_analysis.feature_count
                    )
                )
                return
            from ...ui.dialogs.optimization_dialog import (
                RecommendationDialog as OptimizationRecommendationDialog
            )
            dialog = OptimizationRecommendationDialog(
                layer_name=dw.current_layer.name(),
                recommendations=[r.to_dict() for r in recommendations],
                feature_count=layer_analysis.feature_count,
                location_type=layer_analysis.location_type.value,
                parent=dw
            )
            if dialog.exec_():
                self.apply_optimization_selections(
                    dialog.get_selected_optimizations(), dw.current_layer
                )
        except ImportError as e:
            show_warning(
                "FilterMate",
                dw.tr("Auto-optimizer not available: {0}").format(str(e))
            )
        except Exception as e:
            show_warning(
                "FilterMate",
                dw.tr("Error analyzing layer: {0}").format(str(e)[:50])
            )

    def apply_optimization_selections(self, selected, layer):
        """Apply selected optimization overrides to a layer."""
        from ...infrastructure.feedback import show_success, show_info
        dw = self.dockwidget
        applied = []
        overrides = [
            ('use_centroid_distant', '_layer_centroid_overrides', "Use Centroids"),
            ('simplify_before_buffer', '_layer_simplify_buffer_overrides',
             "Simplify before buffer"),
            ('reduce_buffer_segments', '_layer_reduced_segments_overrides',
             "Reduce buffer segments (3)"),
        ]
        for key, attr, label in overrides:
            if selected.get(key, False):
                if not hasattr(dw, attr):
                    setattr(dw, attr, {})
                getattr(dw, attr)[layer.id()] = True
                if key == 'reduce_buffer_segments':
                    dw.mQgsSpinBox_filtering_buffer_segments.setValue(3)
                applied.append(label)
        if applied:
            show_success(
                "FilterMate",
                dw.tr("Applied to '{0}':\n{1}").format(
                    layer.name(), "\n".join(f"• {a}" for a in applied)
                )
            )
        else:
            show_info("FilterMate", dw.tr("No optimizations selected to apply."))

    # ========================================
    # OPTIMIZATION SETTINGS DIALOGS
    # ========================================

    def show_optimization_settings_dialog(self):
        """Show optimization settings dialog."""
        from ...infrastructure.feedback import show_warning, show_success
        from ...config.config import ENV_VARS, get_optimization_thresholds
        dw = self.dockwidget
        try:
            from ...ui.dialogs.optimization_dialog import (
                OptimizationDialog as BackendOptimizationDialog
            )
            dialog = BackendOptimizationDialog(dw)
            if dialog.exec_():
                self.apply_optimization_dialog_settings(dialog.get_settings())
        except ImportError:
            try:
                from ...ui.dialogs.optimization_dialog import (
                    OptimizationDialog as OptimizationSettingsDialog
                )
                dialog = OptimizationSettingsDialog(dw)
                if dialog.exec_():
                    s = dialog.get_settings()
                    dw._optimization_enabled = s.get('enabled', True)
                    dw._centroid_auto_enabled = s.get('auto_centroid_for_distant', True)
                    dw._optimization_ask_before = s.get('ask_before_apply', True)
                    if not hasattr(dw, '_optimization_thresholds'):
                        dw._optimization_thresholds = {}
                    dw._optimization_thresholds['centroid_distant'] = s.get(
                        'centroid_threshold_distant',
                        get_optimization_thresholds(ENV_VARS)['centroid_optimization_threshold']
                    )
                    show_success("FilterMate", dw.tr("Optimization settings saved"))
            except ImportError as e:
                show_warning(
                    "FilterMate",
                    dw.tr("Dialog not available: {0}").format(str(e))
                )
        except Exception as e:
            show_warning(
                "FilterMate",
                dw.tr("Error: {0}").format(str(e)[:50])
            )

    def apply_optimization_dialog_settings(self, all_settings):
        """Apply settings from optimization dialog."""
        from ...infrastructure.feedback import show_success
        dw = self.dockwidget
        global_s = all_settings.get('global', {})
        dw._optimization_enabled = global_s.get('auto_optimization_enabled', True)
        dw._centroid_auto_enabled = global_s.get('auto_centroid', {}).get('enabled', True)
        dw._optimization_ask_before = global_s.get('ask_before_apply', True)
        if not hasattr(dw, '_optimization_thresholds'):
            dw._optimization_thresholds = {}
        dw._optimization_thresholds['centroid_distant'] = (
            global_s.get('auto_centroid', {}).get('distant_threshold', 5000)
        )
        dw._backend_optimization_settings = all_settings
        show_success("FilterMate", dw.tr("Backend optimization settings saved"))

    def show_backend_optimization_dialog(self):
        """Show backend optimization dialog with full settings."""
        from ...infrastructure.feedback import show_warning, show_success
        dw = self.dockwidget
        try:
            from ...ui.dialogs.optimization_dialog import (
                OptimizationDialog as BackendOptimizationDialog
            )
            dialog = BackendOptimizationDialog(dw)
            if not dialog.exec_():
                return
            all_settings = dialog.get_settings()
            global_s = all_settings.get('global', {})
            dw._backend_optimization_settings = all_settings
            dw._optimization_enabled = global_s.get('auto_optimization_enabled', True)
            dw._centroid_auto_enabled = global_s.get('auto_centroid', {}).get('enabled', True)
            dw._optimization_ask_before = global_s.get('ask_before_apply', True)
            pg_mv = all_settings.get('postgresql', {}).get('materialized_views', {})
            dw._pg_auto_cleanup_enabled = pg_mv.get('auto_cleanup', True)
            if not hasattr(dw, '_optimization_thresholds'):
                dw._optimization_thresholds = {}
            dw._optimization_thresholds.update({
                'centroid_distant': global_s.get('auto_centroid', {}).get(
                    'distant_threshold', 5000
                ),
                'mv_threshold': pg_mv.get('threshold', 10000),
            })
            show_success("FilterMate", dw.tr("Backend optimizations configured"))
        except ImportError as e:
            show_warning(
                "FilterMate",
                dw.tr("Dialog not available: {0}").format(str(e))
            )
        except Exception as e:
            show_warning(
                "FilterMate",
                dw.tr("Error: {0}").format(str(e)[:50])
            )

    # ========================================
    # OPTIMIZATION STATE QUERIES
    # ========================================

    def get_backend_optimization_setting(
        self, backend: str, setting_path: str, default=None
    ):
        """Get backend optimization setting by dotted path."""
        dw = self.dockwidget
        current = getattr(dw, '_backend_optimization_settings', {}).get(backend, {})
        for part in setting_path.split('.'):
            current = current.get(part, default) if isinstance(current, dict) else default
        return current

    def is_centroid_already_enabled(self, layer) -> bool:
        """Check if centroid optimization is already enabled for the given layer."""
        dw = self.dockwidget
        lid = layer.id() if layer else None
        if (
            hasattr(dw, '_layer_centroid_overrides')
            and lid
            and dw._layer_centroid_overrides.get(lid, False)
        ):
            return True
        return (
            (
                hasattr(dw, 'checkBox_filtering_use_centroids_distant_layers')
                and dw.checkBox_filtering_use_centroids_distant_layers.isChecked()
            )
            or (
                hasattr(dw, 'checkBox_filtering_use_centroids_source_layer')
                and dw.checkBox_filtering_use_centroids_source_layer.isChecked()
            )
        )

    def should_use_centroid_for_layer(self, layer) -> bool:
        """Check if centroid optimization should be used for a layer."""
        from ...config.config import ENV_VARS, get_optimization_thresholds
        dw = self.dockwidget
        if hasattr(dw, '_layer_centroid_overrides'):
            override = dw._layer_centroid_overrides.get(
                layer.id() if layer else None
            )
            if override is not None:
                return override
        if (
            not getattr(dw, '_optimization_enabled', True)
            or not getattr(dw, '_centroid_auto_enabled', True)
        ):
            return False
        try:
            from ...core.services.auto_optimizer import (
                LayerAnalyzer, LayerLocationType, AUTO_OPTIMIZER_AVAILABLE
            )
            if not AUTO_OPTIMIZER_AVAILABLE:
                return False
            analysis = LayerAnalyzer().analyze_layer(layer)
            if not analysis:
                return False
            threshold = getattr(dw, '_optimization_thresholds', {}).get(
                'centroid_distant',
                get_optimization_thresholds(ENV_VARS).get(
                    'centroid_optimization_threshold', 1000
                )
            )
            return (
                analysis.location_type in (
                    LayerLocationType.REMOTE_SERVICE,
                    LayerLocationType.REMOTE_DATABASE,
                )
                and analysis.feature_count >= threshold
            )
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug(f"should_use_centroid_for_layer: {e}")
            return False

    # ========================================
    # STATE SERIALIZATION
    # ========================================

    def get_optimization_state(self) -> dict:
        """Get current optimization state for storage/restore."""
        dw = self.dockwidget
        return {
            'enabled': getattr(dw, '_optimization_enabled', True),
            'centroid_auto': getattr(dw, '_centroid_auto_enabled', True),
            'ask_before': getattr(dw, '_optimization_ask_before', True),
            'thresholds': getattr(dw, '_optimization_thresholds', {}),
            'layer_overrides': getattr(dw, '_layer_centroid_overrides', {}),
        }

    def restore_optimization_state(self, state: dict):
        """Restore optimization state from saved settings."""
        dw = self.dockwidget
        dw._optimization_enabled = state.get('enabled', True)
        dw._centroid_auto_enabled = state.get('centroid_auto', True)
        dw._optimization_ask_before = state.get('ask_before', True)
        dw._optimization_thresholds = state.get('thresholds', {})
        dw._layer_centroid_overrides = state.get('layer_overrides', {})

    def auto_select_optimal_backends(self):
        """Delegate backend auto-selection to BackendController."""
        from ...infrastructure.feedback import show_success, show_info, show_warning
        dw = self.dockwidget
        if dw._controller_integration and dw._controller_integration.backend_controller:
            try:
                count = dw._controller_integration.backend_controller.auto_select_optimal_backends()
                if count > 0:
                    show_success(
                        "FilterMate",
                        dw.tr("Optimized {0} layer(s)").format(count)
                    )
                else:
                    show_info(
                        "FilterMate",
                        dw.tr("All layers using auto-selection")
                    )
                if dw.current_layer:
                    _, _, layer_props = dw._validate_and_prepare_layer(dw.current_layer)
                    dw._synchronize_layer_widgets(dw.current_layer, layer_props)
            except Exception as e:
                logger.warning(f"auto_select_optimal_backends failed: {e}")
                show_warning(
                    "FilterMate",
                    dw.tr("Backend optimization unavailable")
                )
