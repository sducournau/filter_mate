"""
SourceFeatureResolver: Encapsulates feature retrieval logic for spatial filtering.

This adapter handles the complex logic of retrieving source features from various contexts:
- Task parameters (thread-safe)
- Layer selection
- Layer subset/filter
- Field-based mode
- Fallback mode

Extracted from filter_task.py prepare_*_source_geom methods to reduce duplication
and improve maintainability.

Architecture:
    - Port: core/ports/source_resolver.py (ISourceFeatureResolver)
    - Adapter: This file (QGIS implementation)
    - Pattern: Strangler Fig migration with legacy fallback

Version: v4.0 (MIG-204)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Dict
from enum import Enum
import logging

# QGIS imports with fallback for unit tests
try:
    from qgis.core import (
        QgsVectorLayer,
        QgsFeature,
        QgsFeatureRequest,
        QgsExpression,
        QgsGeometry,
        QgsMessageLog,
        Qgis,
    )
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsVectorLayer = Any
    QgsFeature = Any
    QgsFeatureRequest = Any
    QgsExpression = Any
    QgsGeometry = Any

logger = logging.getLogger("FilterMate")


class FeatureSourceMode(Enum):
    """Modes of feature source resolution."""
    TASK_PARAMS = "task_params"       # Features from task_parameters (thread-safe)
    SELECTION = "selection"            # Selected features on layer
    SUBSET = "subset"                  # Layer with subset/filter string
    FIELD_BASED = "field_based"        # Field-based Custom Selection mode
    EXPRESSION = "expression"          # Expression fallback
    FALLBACK = "fallback"              # All features (last resort)
    FID_RECOVERY = "fid_recovery"      # Recovered via feature FIDs


@dataclass
class FeatureResolutionResult:
    """Result of feature resolution with metadata."""
    
    features: List[Any] = field(default_factory=list)
    """Resolved features (QgsFeature list)."""
    
    mode_used: FeatureSourceMode = FeatureSourceMode.FALLBACK
    """Which resolution mode was used."""
    
    success: bool = False
    """Whether resolution succeeded."""
    
    feature_count: int = 0
    """Number of valid features resolved."""
    
    error_message: Optional[str] = None
    """Error message if resolution failed."""
    
    warnings: List[str] = field(default_factory=list)
    """Non-fatal warnings during resolution."""
    
    validation_errors: int = 0
    """Number of features that failed validation."""
    
    skipped_no_geometry: int = 0
    """Features skipped due to missing/empty geometry."""
    
    recovery_attempted: bool = False
    """Whether recovery was attempted after initial failure."""


@dataclass
class FeatureResolverConfig:
    """Configuration for feature resolution."""
    
    layer: Optional[Any] = None
    """Source layer (QgsVectorLayer)."""
    
    task_parameters: Optional[Dict] = None
    """Task parameters containing features/fids."""
    
    is_field_expression: Optional[Tuple] = None
    """Field-based mode indicator: (is_field: bool, field_name: str)."""
    
    expression: Optional[str] = None
    """Filter expression fallback."""
    
    param_source_new_subset: Optional[str] = None
    """New subset string fallback."""
    
    log_prefix: str = ""
    """Prefix for log messages."""


class SourceFeatureResolver:
    """
    Resolves source features for spatial filtering operations.
    
    Handles thread-safety issues and multiple fallback strategies.
    
    Priority order:
    1. task_features from task_parameters (most reliable, thread-safe)
    2. Feature FIDs recovery (if task_features validation failed)
    3. Layer selection (selectedFeatures)
    4. Layer subset (getFeatures with subsetString)
    5. Field-based mode (all filtered features)
    6. Expression fallback
    7. All features (last resort)
    
    Example:
        resolver = SourceFeatureResolver()
        config = FeatureResolverConfig(
            layer=my_layer,
            task_parameters=self.task_parameters,
            is_field_expression=self.is_field_expression
        )
        result = resolver.resolve_features(config)
        if result.success:
            features = result.features
          
    """
    
    def __init__(self):
        """Initialize the resolver."""
        self._last_result: Optional[FeatureResolutionResult] = None
    
    def resolve_features(self, config: FeatureResolverConfig) -> FeatureResolutionResult:
        """
        Resolve source features based on configuration.
        
        Args:
            config: Configuration with layer and task parameters
            
        Returns:
            FeatureResolutionResult with resolved features and metadata
        """
        result = FeatureResolutionResult()
        prefix = config.log_prefix or "SourceFeatureResolver"
        
        if not QGIS_AVAILABLE:
            result.error_message = "QGIS not available"
            return result
        
        layer = config.layer
        if not layer or not isinstance(layer, QgsVectorLayer):
            result.error_message = "Invalid or missing layer"
            return result
        
        # Analyze layer state
        has_subset = bool(layer.subsetString())
        has_selection = layer.selectedFeatureCount() > 0
        is_field_based_mode = self._check_field_based_mode(config.is_field_expression)
        
        # Get task features
        task_parameters = config.task_parameters or {}
        task_features = task_parameters.get("task", {}).get("features", [])
        feature_fids = task_parameters.get("task", {}).get("feature_fids", [])
        if not feature_fids:
            feature_fids = task_parameters.get("feature_fids", [])
        
        logger.info(f"=== {prefix} DEBUG ===")
        logger.info(f"  has_task_features: {bool(task_features)} ({len(task_features) if task_features else 0})")
        logger.info(f"  has_subset: {has_subset}")
        logger.info(f"  has_selection: {has_selection}")
        logger.info(f"  is_field_based_mode: {is_field_based_mode}")
        logger.info(f"  feature_fids: {len(feature_fids) if feature_fids else 0}")
        
        # Priority 1: Task features (most reliable, thread-safe)
        if task_features and not is_field_based_mode:
            result = self._resolve_from_task_features(
                task_features, feature_fids, layer, prefix
            )
            if result.success and result.feature_count > 0:
                self._last_result = result
                return result
        
        # Priority 2: Layer selection
        if has_selection and not is_field_based_mode:
            result = self._resolve_from_selection(layer, prefix)
            if result.success and result.feature_count > 0:
                self._last_result = result
                return result
        
        # Priority 3: Layer subset
        if has_subset:
            result = self._resolve_from_subset(layer, prefix)
            if result.success:
                self._last_result = result
                return result
        
        # Priority 4: Field-based mode
        if is_field_based_mode:
            result = self._resolve_field_based(layer, config.is_field_expression, prefix)
            if result.success:
                self._last_result = result
                return result
        
        # Priority 5: Expression fallback
        expression = config.expression or config.param_source_new_subset
        if expression and expression.strip():
            result = self._resolve_from_expression(layer, expression, prefix)
            if result.success and result.feature_count > 0:
                self._last_result = result
                return result
        
        # Priority 6: Fallback - all features
        result = self._resolve_fallback(layer, prefix)
        self._last_result = result
        return result
    
    def _check_field_based_mode(self, is_field_expression: Optional[Tuple]) -> bool:
        """Check if we're in field-based mode."""
        return (
            is_field_expression is not None and
            isinstance(is_field_expression, tuple) and
            len(is_field_expression) >= 2 and
            is_field_expression[0] is True
        )
    
    def _validate_features(
        self, 
        features: List[Any], 
        prefix: str
    ) -> Tuple[List[Any], int, int]:
        """
        Validate features and filter out invalid/empty ones.
        
        Returns:
            Tuple of (valid_features, validation_errors, skipped_no_geometry)
        """
        valid_features = []
        validation_errors = 0
        skipped_no_geometry = 0
        
        for i, f in enumerate(features):
            try:
                if f is None or f == "":
                    continue
                if hasattr(f, 'hasGeometry') and hasattr(f, 'geometry'):
                    if f.hasGeometry() and not f.geometry().isEmpty():
                        valid_features.append(f)
                        # Log first few for diagnostic
                        if i < 3 and logger.isEnabledFor(logging.DEBUG):
                            geom = f.geometry()
                            bbox = geom.boundingBox()
                            logger.debug(
                                f"  {prefix} Feature[{i}]: type={geom.wkbType()}, "
                                f"bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-"
                                f"({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})"
                            )
                    else:
                        skipped_no_geometry += 1
                        logger.debug(f"  {prefix} Skipping feature[{i}] without valid geometry")
                elif f:
                    valid_features.append(f)
            except (RuntimeError, AttributeError) as e:
                validation_errors += 1
                logger.warning(f"  {prefix} Feature[{i}] validation error (thread-safety): {e}")
        
        return valid_features, validation_errors, skipped_no_geometry
    
    def _resolve_from_task_features(
        self, 
        task_features: List[Any],
        feature_fids: List[int],
        layer: QgsVectorLayer,
        prefix: str
    ) -> FeatureResolutionResult:
        """Resolve features from task_parameters (thread-safe source)."""
        result = FeatureResolutionResult()
        result.mode_used = FeatureSourceMode.TASK_PARAMS
        
        logger.info(f"=== {prefix} (TASK PARAMS PRIORITY MODE) ===")
        logger.info(f"  Using {len(task_features)} features from task_parameters (thread-safe)")
        
        # Validate features
        valid_features, validation_errors, skipped_no_geometry = self._validate_features(
            task_features, prefix
        )
        
        result.validation_errors = validation_errors
        result.skipped_no_geometry = skipped_no_geometry
        total_failures = validation_errors + skipped_no_geometry
        
        logger.info(f"  Valid features after filtering: {len(valid_features)}")
        if skipped_no_geometry > 0:
            result.warnings.append(
                f"Skipped {skipped_no_geometry} features with no/empty geometry (thread-safety issue?)"
            )
            logger.warning(result.warnings[-1])
        
        # Handle total failure - try recovery
        if len(valid_features) == 0 and len(task_features) > 0 and total_failures > 0:
            result.recovery_attempted = True
            logger.error(f"  ❌ ALL {len(task_features)} task_features failed validation")
            logger.error(f"     ({validation_errors} errors, {skipped_no_geometry} no geometry)")
            
            # Try FID recovery
            if feature_fids and len(feature_fids) > 0:
                logger.info(f"  → Attempting recovery using {len(feature_fids)} feature_fids")
                try:
                    request = QgsFeatureRequest().setFilterFids(feature_fids)
                    recovered = list(layer.getFeatures(request))
                    if recovered:
                        valid_features = recovered
                        result.mode_used = FeatureSourceMode.FID_RECOVERY
                        logger.debug(f"  ✓ Recovered {len(recovered)} features using FIDs")
                except Exception as e:
                    logger.error(f"  ❌ FID recovery failed: {e}")
            
            # Try selection recovery
            if len(valid_features) == 0 and layer.selectedFeatureCount() > 0:
                logger.info(f"  → Attempting recovery from layer selection")
                try:
                    selected_fids = list(layer.selectedFeatureIds())
                    if selected_fids:
                        request = QgsFeatureRequest().setFilterFids(selected_fids)
                        recovered = list(layer.getFeatures(request))
                        if recovered:
                            valid_features = recovered
                            result.mode_used = FeatureSourceMode.SELECTION
                            logger.debug(f"  ✓ Recovered {len(recovered)} features from selection")
                except Exception as e:
                    logger.error(f"  ❌ Selection recovery failed: {e}")
            
            # If still no features, DON'T fall back to all features
            if len(valid_features) == 0:
                result.error_message = (
                    f"Could not recover any features from {len(task_features)} task_features. "
                    f"This prevents incorrect filtering with all {layer.featureCount()} features."
                )
                logger.error(f"  ❌ {result.error_message}")
                try:
                    QgsMessageLog.logMessage(
                        f"v4.0: BLOCKING fallback - would cause incorrect filter!",
                        "FilterMate", Qgis.Warning
                    )
                except (RuntimeError, AttributeError):
                    pass  # Logging may fail during shutdown
                return result
        
        result.features = valid_features
        result.feature_count = len(valid_features)
        result.success = result.feature_count > 0
        return result
    
    def _resolve_from_selection(
        self, 
        layer: QgsVectorLayer, 
        prefix: str
    ) -> FeatureResolutionResult:
        """Resolve features from layer selection."""
        result = FeatureResolutionResult()
        result.mode_used = FeatureSourceMode.SELECTION
        
        logger.info(f"=== {prefix} (SELECTION MODE) ===")
        logger.info(f"  Using {layer.selectedFeatureCount()} selected features")
        
        try:
            # Thread-safe: use selectedFeatureIds + getFeatures
            selected_fids = list(layer.selectedFeatureIds())
            if selected_fids:
                request = QgsFeatureRequest().setFilterFids(selected_fids)
                result.features = list(layer.getFeatures(request))
                result.feature_count = len(result.features)
                result.success = result.feature_count > 0
            else:
                result.error_message = "No selected feature IDs"
        except Exception as e:
            result.error_message = f"Failed to get selected features: {e}"
            logger.error(result.error_message)
        
        return result
    
    def _resolve_from_subset(
        self, 
        layer: QgsVectorLayer, 
        prefix: str
    ) -> FeatureResolutionResult:
        """Resolve features from layer with subset string."""
        result = FeatureResolutionResult()
        result.mode_used = FeatureSourceMode.SUBSET
        
        subset = layer.subsetString()
        logger.info(f"=== {prefix} (FILTERED MODE) ===")
        logger.info(f"  Source layer has active filter: {subset[:100]}")
        logger.info(f"  Using {layer.featureCount()} filtered features")
        
        try:
            result.features = list(layer.getFeatures())
            result.feature_count = len(result.features)
            result.success = True
            logger.debug(f"  Retrieved {result.feature_count} features from getFeatures()")
        except Exception as e:
            result.error_message = f"Failed to get features: {e}"
            logger.error(result.error_message)
        
        return result
    
    def _resolve_field_based(
        self, 
        layer: QgsVectorLayer,
        is_field_expression: Tuple,
        prefix: str
    ) -> FeatureResolutionResult:
        """Resolve features in field-based Custom Selection mode."""
        result = FeatureResolutionResult()
        result.mode_used = FeatureSourceMode.FIELD_BASED
        
        field_name = is_field_expression[1] if len(is_field_expression) > 1 else "unknown"
        subset = layer.subsetString() or "(none)"
        
        logger.info(f"=== {prefix} (FIELD-BASED MODE) ===")
        logger.info(f"  Field name: '{field_name}'")
        logger.info(f"  Source subset: '{subset[:80]}...'")
        logger.info(f"  Using ALL {layer.featureCount()} filtered features for geometric intersection")
        
        try:
            result.features = list(layer.getFeatures())
            result.feature_count = len(result.features)
            result.success = True
        except Exception as e:
            result.error_message = f"Failed to get features: {e}"
            logger.error(result.error_message)
        
        return result
    
    def _resolve_from_expression(
        self, 
        layer: QgsVectorLayer,
        expression: str,
        prefix: str
    ) -> FeatureResolutionResult:
        """Resolve features using expression filter."""
        result = FeatureResolutionResult()
        result.mode_used = FeatureSourceMode.EXPRESSION
        
        logger.info(f"=== {prefix} (EXPRESSION FALLBACK MODE) ===")
        logger.info(f"  Expression: '{expression[:80]}...'")
        
        try:
            expr = QgsExpression(expression)
            if not expr.hasParserError():
                request = QgsFeatureRequest(expr)
                result.features = list(layer.getFeatures(request))
                result.feature_count = len(result.features)
                result.success = result.feature_count > 0
                logger.info(f"  → Expression fallback: {result.feature_count} features")
            else:
                result.error_message = f"Expression parse error: {expr.parserErrorString()}"
                result.warnings.append(result.error_message)
                logger.warning(f"  → {result.error_message}")
        except Exception as e:
            result.error_message = f"Expression evaluation failed: {e}"
            logger.error(result.error_message)
        
        return result
    
    def _resolve_fallback(
        self, 
        layer: QgsVectorLayer, 
        prefix: str
    ) -> FeatureResolutionResult:
        """Fallback: use all features from layer."""
        result = FeatureResolutionResult()
        result.mode_used = FeatureSourceMode.FALLBACK
        
        logger.info(f"=== {prefix} (FALLBACK MODE) ===")
        logger.info(f"  No specific mode matched - using all source features")
        
        # Log warning for potential bug
        try:
            QgsMessageLog.logMessage(
                f"⚠️ FALLBACK MODE: Using ALL {layer.featureCount()} features from source layer",
                "FilterMate", Qgis.Warning
            )
            QgsMessageLog.logMessage(
                f"   This may cause incorrect filtering! Expected: single feature selected.",
                "FilterMate", Qgis.Warning
            )
        except (RuntimeError, AttributeError):
            pass  # Logging may fail during shutdown
        
        result.warnings.append(
            f"FALLBACK MODE: Using all {layer.featureCount()} features - may be a bug!"
        )
        
        try:
            result.features = list(layer.getFeatures())
            result.feature_count = len(result.features)
            result.success = True
            
            # Warn if many features in fallback mode
            if result.feature_count > 10:
                result.warnings.append(
                    f"POTENTIAL BUG: FALLBACK MODE with {result.feature_count} features! "
                    "Source geometry may be too large."
                )
                logger.warning(f"  ⚠️ {result.warnings[-1]}")
        except Exception as e:
            result.error_message = f"Failed to get features: {e}"
            logger.error(result.error_message)
        
        return result
    
    @property
    def last_result(self) -> Optional[FeatureResolutionResult]:
        """Get the last resolution result."""
        return self._last_result


def create_source_feature_resolver() -> SourceFeatureResolver:
    """Factory function to create a SourceFeatureResolver."""
    return SourceFeatureResolver()
