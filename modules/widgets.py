from qgis.PyQt import QtGui, QtWidgets, QtCore, uic, sip
from qgis.PyQt.QtCore import (
    QEvent,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QPalette,
    QPixmap,
    QStandardItem
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QStylePainter,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget
)
from qgis.core import (
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsFeatureRequest,
    QgsMessageLog,
    QgsTask,
    Qgis
)
from qgis.gui import (
    QgsCheckableComboBox
)
from qgis.utils import iface
from functools import partial
import json
import logging

# Get FilterMate logger
logger = logging.getLogger('FilterMate')

# Utilities
from .appUtils import safe_set_subset_string, is_layer_source_available
from .feedback_utils import show_warning, show_error
from .object_safety import (
    is_valid_layer, is_gpkg_file_accessible, refresh_ogr_layer,
    GdalErrorHandler  # v2.3.11: Suppress transient GDAL warnings
)


def safe_iterate_features(layer_or_source, request=None, max_retries=5, retry_delay=0.3):
    """
    Safely iterate over features from a layer or feature source.
    
    Handles OGR/GeoPackage errors like "unable to open database file" with retry logic.
    Suppresses transient GDAL/OGR warnings that are handled internally.
    
    IMPORTANT: For multi-layer filtering with Spatialite/GeoPackage, concurrent database
    access can cause transient "unable to open database file" errors. This function uses
    exponential backoff to wait for database locks to clear.
    
    Args:
        layer_or_source: QgsVectorLayer, QgsVectorDataProvider, or QgsAbstractFeatureSource
        request: Optional QgsFeatureRequest
        max_retries: Number of retry attempts (default 5, increased for concurrent access)
        retry_delay: Initial delay between retries in seconds (default 0.3)
        
    Yields:
        Features from the layer/source
    """
    import time
    
    # Use GDAL error handler to suppress transient SQLite warnings during iteration
    with GdalErrorHandler():
        for attempt in range(max_retries):
            try:
                if request:
                    iterator = layer_or_source.getFeatures(request)
                else:
                    iterator = layer_or_source.getFeatures()
                
                for feature in iterator:
                    yield feature
                return  # Successfully completed iteration
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for known recoverable OGR/SQLite errors
                is_recoverable = any(x in error_str for x in [
                    'unable to open database file',
                    'database is locked',
                    'disk i/o error',
                    'sqlite3_step',
                    'busy',
                ])
                
                if is_recoverable and attempt < max_retries - 1:
                    layer_name = getattr(layer_or_source, 'name', lambda: 'unknown')()
                    logger.debug(
                        f"OGR access retry on '{layer_name}' (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Waiting {retry_delay:.2f}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 5.0)  # Exponential backoff, max 5 seconds
                else:
                    layer_name = getattr(layer_or_source, 'name', lambda: 'unknown')()
                    logger.error(f"Failed to iterate features from '{layer_name}' after {max_retries} attempts: {e}")
                    return  # Stop iteration on unrecoverable error


def get_feature_attribute(feature, field_name):
    """
    Safely get an attribute value from a feature.
    
    Handles special cases like 'fid' which may be a pseudo-field
    representing the feature ID rather than an actual attribute.
    
    Args:
        feature: QgsFeature object
        field_name: Name of the field to retrieve
        
    Returns:
        The attribute value, or None if not found
    """
    if field_name is None:
        return None
    
    # Handle special case for 'fid' (feature ID)
    # In QGIS, 'fid' is often a pseudo-column representing feature.id()
    if field_name.lower() == 'fid':
        try:
            # First try to get it as a regular attribute
            return feature[field_name]
        except (KeyError, IndexError):
            # Fall back to feature.id() if 'fid' is not a real field
            return feature.id()
    
    # For regular fields, try to access by name
    try:
        return feature[field_name]
    except (KeyError, IndexError):
        # If field access fails, try to get by index
        try:
            fields = feature.fields()
            idx = fields.lookupField(field_name)
            if idx >= 0:
                return feature.attributes()[idx]
        except (KeyError, IndexError, AttributeError) as e:
            logger.debug(f"Could not get feature attribute '{field_name}': {e}")
        return None


class PopulateListEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, parent, action, silent_flag):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.sub_action = self.description()
        self.action = action

        self.parent = parent

        self.silent_flag = silent_flag
        
        # CRITICAL: Store layer reference at task creation time
        # This ensures consistency between layer and its properties
        self.layer = self.parent.layer
        
        # Store the layer_id at creation time to detect if layer changed
        self._created_layer_id = self.layer.id() if self.layer else None
        
        # Vérifier que le layer existe toujours dans list_widgets
        if self.layer is None or self.layer.id() not in self.parent.list_widgets:
            self.identifier_field_name = None
            self.display_expression = None
            self.is_field_flag = None
        else:
            self.identifier_field_name = self.parent.list_widgets[self.layer.id()].getIdentifierFieldName()
            self.display_expression = self.parent.list_widgets[self.layer.id()].getDisplayExpression()
            self.is_field_flag = self.parent.list_widgets[self.layer.id()].getExpressionFieldFlag()
        
        # THREAD SAFETY FIX (v2.3.19): Pre-create expression context in main thread
        # Calling layer.createExpressionContext() from a background thread while the main thread
        # modifies layer variables (via setLayerVariable) causes "Windows fatal exception: access violation".
        # The expression context is NOT thread-safe, so we must create it here in the main thread.
        self._cached_expression_context = None
        if self.layer is not None:
            try:
                self._cached_expression_context = self.layer.createExpressionContext()
            except (RuntimeError, OSError, SystemError) as e:
                logger.debug(f"Could not pre-create expression context for layer '{self.layer.name()}': {e}")
                self._cached_expression_context = None


    def run(self):
        """Main function that run the right method from init parameters.
        
        Includes enhanced error handling for OGR/SQLite database access errors
        that can occur during concurrent Spatialite/GeoPackage operations.
        """
        import time
        
        try:
            # Vérifier que le layer et les widgets existent toujours
            if self.layer is None or self.layer.id() not in self.parent.list_widgets:
                logger.debug(f'Layer no longer exists in list_widgets, skipping task: {self.action}')
                # Return True for graceful skip (not an error, layer was just removed)
                return True
            
            # CRITICAL: Check if the parent's current layer has changed since task creation
            # This prevents race conditions where task was created for layer A but parent now has layer B
            if self._created_layer_id and self.parent.layer is not None:
                if self.parent.layer.id() != self._created_layer_id:
                    # Get layer names for more informative message
                    old_layer_name = self.layer.name() if self.layer else "Unknown"
                    new_layer_name = self.parent.layer.name() if self.parent.layer else "Unknown"
                    logger.debug(f'Layer changed since task creation (was {old_layer_name}_{self._created_layer_id[:8]}, now {new_layer_name}_{self.parent.layer.id()[:8]}), skipping task: {self.action}')
                    # Return True for graceful skip (not an error, user just switched layers)
                    return True
            
            # For Spatialite/OGR layers, add a brief stabilization delay to reduce
            # database lock contention with recently completed filter operations
            provider_type = self.layer.providerType() if self.layer else None
            if provider_type in ('spatialite', 'ogr') and self.action in ('loadFeaturesList', 'buildFeaturesList'):
                time.sleep(0.1)  # Brief delay to let filter connections fully close
                
            if self.action == 'buildFeaturesList':
                self.buildFeaturesList()
            elif self.action == 'loadFeaturesList':
                self.loadFeaturesList()
            elif self.action == 'selectAllFeatures':
                self.selectAllFeatures()
            elif self.action == 'deselectAllFeatures':
                self.deselectAllFeatures()
            elif self.action == 'filterFeatures':
                self.filterFeatures()   
            elif self.action == 'updateFeatures':
                self.updateFeatures()

            # FIX v2.5.19: Return True even when canceled to prevent QGIS "Task failed" messages
            # Cancellation is a normal, expected operation (e.g., user switches layers, new filter starts)
            # and should not be treated as an error. When tasks with ParentDependsOnSubTask
            # are canceled, returning True ensures the parent task also completes gracefully.
            if self.isCanceled():
                logger.debug(f'Task "{self.action}" was canceled for layer "{self.layer.name() if self.layer else "Unknown"}" - completing gracefully')
            
            return True
        
        except Exception as e:
            self.exception = e
            error_str = str(e).lower()
            
            # Check for known OGR/SQLite transient errors
            is_sqlite_error = any(x in error_str for x in [
                'unable to open database file',
                'database is locked',
                'sqlite3_step',
                'disk i/o error',
            ])
            
            # Check for layer invalidation errors (C++ object deleted)
            is_layer_deleted = any(x in error_str for x in [
                'deleted',
                'underlying c/c++',
                'c++ object',
                'null pointer',
            ])
            
            # Check for PostgreSQL connection errors (v2.5.11)
            # These occur when connection is lost during task execution
            is_postgres_error = any(x in error_str for x in [
                'connection is closed',
                'connection already closed',
                'server closed the connection',
                'connection terminated',
                'connection reset',
                'could not connect',
                'no connection',
                'connection refused',
                'operationalerror',  # psycopg2.OperationalError
                'interfaceerror',    # psycopg2.InterfaceError
                'databaseerror',     # psycopg2.DatabaseError
            ])
            
            # ENHANCED LOGGING: Differentiate between transient and permanent errors
            import traceback
            if is_sqlite_error:
                # SQLite concurrent access error - log at DEBUG level (expected during high concurrency)
                logger.debug(
                    f'PopulateListEngineTask: SQLite access error during "{self.action}" for '
                    f'layer "{self.layer.name() if self.layer else "None"}". '
                    f'This is typically transient during multi-layer filtering. Error: {e}'
                )
                # Return True for transient errors to avoid "Task failed" message in QGIS
                # The task will be retried on next user interaction anyway
                return True
            elif is_layer_deleted:
                # Layer was deleted during task execution - this is normal during project changes
                logger.debug(
                    f'PopulateListEngineTask: Layer deleted during "{self.action}". '
                    f'This is expected when switching projects or removing layers.'
                )
                return True
            elif is_postgres_error:
                # PostgreSQL connection error - log at DEBUG level (transient during cleanup)
                logger.debug(
                    f'PopulateListEngineTask: PostgreSQL connection error during "{self.action}" for '
                    f'layer "{self.layer.name() if self.layer else "None"}". '
                    f'This is typically transient when connection is lost. Error: {e}'
                )
                # Return True for transient errors to avoid "Task failed" message in QGIS
                return True
            else:
                # Other unexpected errors - log fully
                logger.error(f'PopulateListEngineTask failed for action "{self.action}": {e}')
                logger.error(f'  Layer: {self.layer.name() if self.layer else "None"}')
                logger.error(f'  Traceback:\n{traceback.format_exc()}')
            
            return False

    def get_task_action_and_layer(self):
        return self.action, self.layer
    
    def _update_progress_batched(self, index: int, total_count: int, batch_size: int = 100):
        """
        Update progress in batches to reduce UI overhead.
        
        For large datasets, updating progress on every feature causes significant
        slowdown. This method only updates every batch_size features.
        
        Args:
            index: Current feature index
            total_count: Total number of features
            batch_size: Update progress every N features (default: 100)
        """
        if total_count == 0:
            return
        if index % batch_size == 0 or index == total_count - 1:
            self.setProgress((index / total_count) * 100)
    
    def buildFeaturesList(self, has_limit=True, filter_txt_splitted=None):
        """
        Build the features list for the widget.
        
        PERFORMANCE OPTIMIZATIONS:
        - Uses batched progress updates to reduce UI overhead
        - Pre-compiles expressions for complex display expressions
        - Respects cancellation for quick abort
        """
        features_list = []

        limit = 0
        layer_features_source = None
        total_features_list_count = 0
        filter_expression_request = QgsFeatureRequest()
        
        # DEBUG: Log entry point
        logger.debug(f"buildFeaturesList: Starting for layer '{self.layer.name() if self.layer else 'None'}'")
        logger.debug(f"  → identifier_field_name: {self.identifier_field_name}")
        logger.debug(f"  → display_expression: {self.display_expression}")
        logger.debug(f"  → is_field_flag: {self.is_field_flag}")

        # THREAD SAFETY FIX (v2.3.12): Get featureSource from dataProvider BEFORE any filtering.
        # featureSource() returns a thread-safe snapshot that can be iterated from background threads.
        # CRITICAL: Do NOT call layer.setSubsetString() from background thread - causes access violation!
        # The featureSource already contains ALL features regardless of any subset filter.
        data_provider_layer = self.layer.dataProvider()
        if data_provider_layer:
            total_features_list_count = data_provider_layer.featureCount()
            layer_features_source = data_provider_layer.featureSource()

        if self.parent.list_widgets[self.layer.id()].getTotalFeaturesListCount() == 0 and total_features_list_count > 0:
            self.parent.list_widgets[self.layer.id()].setTotalFeaturesListCount(total_features_list_count)

        if layer_features_source is not None and has_limit is True:
            limit = self.parent.list_widgets[self.layer.id()].getLimit()
            
        
        if layer_features_source is not None:
            # Validate that required fields exist in the layer
            field_names = [field.name() for field in self.layer.fields()]
            
            # Check identifier field
            if self.identifier_field_name and self.identifier_field_name not in field_names:
                logger.warning(f"Identifier field '{self.identifier_field_name}' not found in layer '{self.layer.name()}'. Available fields: {field_names}")
                return
            
            # Check display expression field (only when is_field_flag is True)
            # If field not found, use a fallback field instead of returning silently
            if self.is_field_flag is True and self.display_expression and self.display_expression not in field_names:
                # Try to find a fallback field
                fallback_field = None
                
                # First choice: use identifier_field_name if it exists
                if self.identifier_field_name and self.identifier_field_name in field_names:
                    fallback_field = self.identifier_field_name
                # Second choice: use the first available field
                elif field_names:
                    fallback_field = field_names[0]
                
                if fallback_field:
                    logger.info(
                        f"Display field '{self.display_expression}' not found in layer '{self.layer.name()}'. "
                        f"Using fallback field '{fallback_field}'."
                    )
                    # Update the display expression to use the fallback
                    self.display_expression = fallback_field
                    # Also update the widget's stored expression for consistency
                    if self.layer.id() in self.parent.list_widgets:
                        self.parent.list_widgets[self.layer.id()].setDisplayExpression(fallback_field)
                else:
                    logger.error(
                        f"Display field '{self.display_expression}' not found in layer '{self.layer.name()}' "
                        f"and no fallback field available. Cannot build features list."
                    )
                    return
            
            if self.parent.list_widgets[self.layer.id()].getFilterExpression() != '':
                filter_expression = self.parent.list_widgets[self.layer.id()].getFilterExpression()
                if QgsExpression(filter_expression).isValid():

                    if filter_txt_splitted is not None:
                        filter_txt_splitted_final = []
                        for filter_txt in filter_txt_splitted:
                            filter_txt_splitted_final.append("""{display_expression} *~ '{filter_txt}'""".format(display_expression=self.display_expression,
                                                                                                                filter_txt=filter_txt.replace('é','?').replace('è','?').replace('â','?').replace('ô','?')))
                                              
                        filter_txt_string_final = ' OR '.join(filter_txt_splitted_final)
                        filter_expression = filter_expression + ' AND ( {filter_txt_string_final} )'.format(filter_txt_string_final=filter_txt_string_final)
                        filter_expression_request = QgsFeatureRequest(QgsExpression(filter_expression))
                    else: 
                        filter_expression_request = QgsFeatureRequest(QgsExpression(filter_expression))

                    if limit > 0:
                        filter_expression_request.setLimit(limit)

                    # PERFORMANCE FIX (v2.5.9): Avoid double iteration for PostgreSQL layers
                    # Previously: sum(1 for _ in getFeatures()) then getFeatures() again = 2x SQL queries
                    # Now: Single-pass collection with incremental progress updates
                    # For complex expressions on pre-filtered PostgreSQL layers, this prevents freezes
                    
                    # Use estimated count for progress (avoid costly pre-count query)
                    estimated_count = total_features_list_count if total_features_list_count > 0 else 1000
                    if limit > 0:
                        estimated_count = min(estimated_count, limit)
                    
                    if self.is_field_flag is True:
                        # Single-pass: collect features and update progress incrementally
                        for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                            # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
                            # when main thread modifies layer variables during setLayerVariable()
                            if self.isCanceled():
                                logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                                return
                            arr = [get_feature_attribute(feature, self.display_expression), get_feature_attribute(feature, self.identifier_field_name)]
                            features_list.append(arr)
                            # PERFORMANCE: Use batched progress updates with estimated count
                            self._update_progress_batched(index, estimated_count)
                        
                        # Check if we got any features, handle empty result
                        if len(features_list) == 0:
                            logger.debug(f"buildFeaturesList: No features match filter expression for layer '{self.layer.name()}'")
                            self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
                            return
                    else:
                        display_expression = QgsExpression(self.display_expression)

                        if display_expression.isValid():
                            # THREAD SAFETY FIX (v2.3.19): Use pre-cached expression context
                            # instead of calling layer.createExpressionContext() from background thread.
                            # This prevents access violations when main thread modifies layer variables.
                            context = self._cached_expression_context
                            if context is None:
                                # Fallback: create minimal context without layer (less feature-rich but thread-safe)
                                context = QgsExpressionContext()
                                logger.debug(f"Using minimal expression context for layer '{self.layer.name()}'")

                            # Single-pass iteration with incremental progress
                            for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                                # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
                                if self.isCanceled():
                                    logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                                    return
                                context.setFeature(feature)
                                result = display_expression.evaluate(context)
                                # Check for evaluation errors (e.g., missing referenced layers)
                                if display_expression.hasEvalError():
                                    # Fallback: try to get identifier field value instead
                                    logger.debug(f"Expression eval error: {display_expression.evalErrorString()}")
                                    result = get_feature_attribute(feature, self.identifier_field_name)
                                # FIX v2.5.11: Use 'is not None' instead of 'if result:' to allow
                                # falsy values like 0, empty string, False from CASE expressions
                                if result is not None:
                                    # Convert to string for display, preserving the value
                                    display_value = str(result) if result != '' else '(empty)'
                                    arr = [display_value, get_feature_attribute(feature, self.identifier_field_name)]
                                    features_list.append(arr)
                                    # PERFORMANCE: Use batched progress updates with estimated count
                                    self._update_progress_batched(index, estimated_count)
                            
                            # Check if we got any features, handle empty result
                            if len(features_list) == 0:
                                logger.debug(f"buildFeaturesList: No features match filter expression for layer '{self.layer.name()}'")
                                self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
                                return
                        else:
                            # Invalid expression - log and fallback to identifier field
                            expr_display = repr(self.display_expression) if self.display_expression else '<empty>'
                            logger.debug(f"Invalid/empty display expression {expr_display} for layer '{self.layer.name()}', using identifier field")
                            for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                                # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
                                if self.isCanceled():
                                    logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                                    return
                                id_value = get_feature_attribute(feature, self.identifier_field_name)
                                arr = [id_value, id_value]
                                features_list.append(arr)
                                # PERFORMANCE: Use batched progress updates with estimated count
                                self._update_progress_batched(index, estimated_count)


            
            else:

                if filter_txt_splitted is not None:
                    filter_txt_splitted_final = []
                    for filter_txt in filter_txt_splitted:
                        filter_txt_splitted_final.append("""{display_expression} *~ '{filter_txt}'""".format(display_expression=self.display_expression,
                                                                                                            filter_txt=filter_txt.replace('é','?').replace('è','?').replace('â','?').replace('ô','?')))
                                            
                    filter_txt_string_final = ' OR '.join(filter_txt_splitted_final)
                    filter_expression_request = QgsFeatureRequest(QgsExpression(filter_txt_string_final))

                if limit > 0:
                    filter_expression_request.setLimit(limit)

                # PERFORMANCE FIX (v2.5.9): Avoid double iteration - use estimated count
                # Previously: sum(1 for _ in getFeatures()) caused full query execution twice
                estimated_count_else = total_features_list_count if total_features_list_count > 0 else 1000
                if limit > 0:
                    estimated_count_else = min(estimated_count_else, limit)

                if self.is_field_flag is True:
                    for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                        # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
                        if self.isCanceled():
                            logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                            return
                        arr = [get_feature_attribute(feature, self.display_expression), get_feature_attribute(feature, self.identifier_field_name)]
                        features_list.append(arr)
                        # PERFORMANCE: Use batched progress updates with estimated count
                        self._update_progress_batched(index, estimated_count_else)
                    
                    # Handle empty result
                    if len(features_list) == 0:
                        logger.debug(f"buildFeaturesList: No features available for layer '{self.layer.name()}'")
                        self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
                        return
                else:
                    display_expression = QgsExpression(self.display_expression)

                    if display_expression.isValid():
                        # THREAD SAFETY FIX (v2.3.19): Use pre-cached expression context
                        # instead of calling layer.createExpressionContext() from background thread.
                        # This prevents access violations when main thread modifies layer variables.
                        context = self._cached_expression_context
                        if context is None:
                            # Fallback: create minimal context without layer (less feature-rich but thread-safe)
                            context = QgsExpressionContext()
                            logger.debug(f"Using minimal expression context for layer '{self.layer.name()}'")

                        for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                            # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
                            if self.isCanceled():
                                logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                                return
                            context.setFeature(feature)
                            result = display_expression.evaluate(context)
                            # Check for evaluation errors (e.g., missing referenced layers)
                            if display_expression.hasEvalError():
                                # Fallback: try to get identifier field value instead
                                logger.debug(f"Expression eval error: {display_expression.evalErrorString()}")
                                result = get_feature_attribute(feature, self.identifier_field_name)
                            # FIX v2.5.11: Use 'is not None' instead of 'if result:' to allow
                            # falsy values like 0, empty string, False from CASE expressions
                            if result is not None:
                                # Convert to string for display, preserving the value
                                display_value = str(result) if result != '' else '(empty)'
                                arr = [display_value, get_feature_attribute(feature, self.identifier_field_name)]
                                features_list.append(arr)
                                # PERFORMANCE: Use batched progress updates with estimated count
                                self._update_progress_batched(index, estimated_count_else)
                        
                        # Handle empty result
                        if len(features_list) == 0:
                            logger.debug(f"buildFeaturesList: No features available for layer '{self.layer.name()}'")
                            self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
                            return
                    else:
                        # Invalid expression - log and fallback to identifier field
                        expr_display = repr(self.display_expression) if self.display_expression else '<empty>'
                        logger.debug(f"Invalid/empty display expression {expr_display} for layer '{self.layer.name()}', using identifier field")
                        for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                            # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
                            if self.isCanceled():
                                logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                                return
                            id_value = get_feature_attribute(feature, self.identifier_field_name)
                            arr = [id_value, id_value]
                            features_list.append(arr)
                            # PERFORMANCE: Use batched progress updates with estimated count
                            self._update_progress_batched(index, estimated_count_else)
                        
                        # Handle empty result
                        if len(features_list) == 0:
                            logger.debug(f"buildFeaturesList: No features available for layer '{self.layer.name()}'")
                            self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
                            return

            # CRASH FIX (v2.3.20): Final cancellation check before widget updates
            if self.isCanceled():
                logger.debug(f"buildFeaturesList: Task cancelled before final updates for layer '{self.layer.name()}'")
                return
            
            # THREAD SAFETY FIX (v2.3.12): Use thread-safe layer_features_source instead of iterating layer.
            # safe_iterate_features(self.layer) calls layer.getFeatures() which is NOT thread-safe
            # and causes "Windows fatal exception: access violation" when multiple threads access same layer.
            # The layer_features_source snapshot is thread-safe and contains all features.
            # CRASH FIX (v2.3.20): Build list with cancellation checks instead of list comprehension
            nonSubset_features_list = []
            for feature in safe_iterate_features(layer_features_source):
                if self.isCanceled():
                    logger.debug(f"buildFeaturesList: Task cancelled during nonSubset iteration for layer '{self.layer.name()}'")
                    return
                nonSubset_features_list.append(get_feature_attribute(feature, self.identifier_field_name))
            
            # CRASH FIX (v2.3.20): Final validity check before widget updates
            if self.isCanceled() or self.layer is None or self.layer.id() not in self.parent.list_widgets:
                logger.debug(f"buildFeaturesList: Task cancelled or layer removed before widget update")
                return
                
            self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
            
            # FIX v2.5.8: Apply sort order from parent widget settings
            sort_order, sort_field = self.parent.getSortOrder()
            reverse = (sort_order == 'DESC')
            self.parent.list_widgets[self.layer.id()].sortFeaturesListByDisplayExpression(nonSubset_features_list, reverse=reverse)


    def loadFeaturesList(self, new_list=True):
        current_selected_features_list = [feature[1] for feature in self.parent.list_widgets[self.layer.id()].getSelectedFeaturesList()]
        
        # THREAD SAFETY FIX (v2.3.12): Use thread-safe featureSource() instead of iterating layer.
        # layer.getFeatures() is NOT thread-safe and causes access violations in multi-threaded context.
        data_provider = self.layer.dataProvider()
        if data_provider:
            layer_features_source = data_provider.featureSource()
            # CRASH FIX (v2.3.20): Build list with cancellation checks
            nonSubset_features_list = []
            for feature in safe_iterate_features(layer_features_source):
                if self.isCanceled():
                    logger.debug(f"loadFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
                    return
                nonSubset_features_list.append(get_feature_attribute(feature, self.identifier_field_name))
        else:
            logger.warning(f"loadFeaturesList: No data provider for layer '{self.layer.name()}'")
            nonSubset_features_list = []
        
        # CRASH FIX (v2.3.20): Check cancellation before UI operations
        if self.isCanceled():
            logger.debug(f"loadFeaturesList: Task cancelled before UI operations for layer '{self.layer.name()}'")
            return
        
        if new_list is True:
            self.parent.list_widgets[self.layer.id()].clear()

        filter_text = self.parent.list_widgets[self.layer.id()].getFilterText()
        if filter_text != '':
            self.parent.filter_le.setText(filter_text)

        list_to_load = self.parent.list_widgets[self.layer.id()].getFeaturesList()

        total_count = len(list_to_load)
        
        # CRITICAL FIX: Prevent division by zero when list is empty
        if total_count == 0:
            logger.warning(f"loadFeaturesList: No features to load for layer '{self.layer.name()}'")
            self.updateFeatures()
            return
        
        for index, it in enumerate(list_to_load):
            # CRASH FIX (v2.3.20): Check for task cancellation during list iteration
            if self.isCanceled():
                logger.debug(f"loadFeaturesList: Task cancelled during list loading for layer '{self.layer.name()}'")
                return
            lwi = QListWidgetItem(str(it[0]))
            lwi.setData(0,str(it[0]))
            lwi.setData(3,it[1])
            lwi.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            if it[1] in current_selected_features_list:
                lwi.setCheckState(Qt.Checked)
                if it[1] in nonSubset_features_list:
                    lwi.setData(6,self.parent.font_by_state['checked'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['checked'][1]))
                    lwi.setData(4,"True")
                else:
                    lwi.setData(6,self.parent.font_by_state['checkedFiltered'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['checkedFiltered'][1]))
                    lwi.setData(4,"False")
            else:
                lwi.setCheckState(Qt.Unchecked)
                if it[1] in nonSubset_features_list:
                    lwi.setData(6,self.parent.font_by_state['unChecked'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['unChecked'][1]))
                    lwi.setData(4,"True")
                else:
                    lwi.setData(6,self.parent.font_by_state['unCheckedFiltered'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['unCheckedFiltered'][1]))
                    lwi.setData(4,"False")
            self.parent.list_widgets[self.layer.id()].addItem(lwi)
            # PERFORMANCE: Use batched progress updates
            self._update_progress_batched(index, total_count)


        self.updateFeatures()

            
    def filterFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        filter_txt_splitted = self.parent.filter_txt.lower().strip().split(" ")

        self.parent.list_widgets[self.layer.id()].setFilterText(self.parent.filter_txt)

        if self.parent.list_widgets[self.layer.id()].getTotalFeaturesListCount() > total_count:
            self.buildFeaturesList(False, filter_txt_splitted)
            self.loadFeaturesList(True)

        else:
            filter_txt_splitted = [item.replace('é','e').replace('è','e').replace('â','a').replace('ô','o') for item in filter_txt_splitted]
            list_widget = self.parent.list_widgets[self.layer.id()]
            widget_count = list_widget.count()
            for index in range(widget_count):
                item = list_widget.item(index)
                string_value = item.text().lower().replace('é','e').replace('è','e').replace('â','a').replace('ô','o')
                filter = all(x not in string_value for x in filter_txt_splitted)
                list_widget.setRowHidden(index, filter)
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)

        visible_features_list = []
        list_widget = self.parent.list_widgets[self.layer.id()]
        widget_count = list_widget.count()
        for index in range(widget_count):
            item = list_widget.item(index)
            if not item.isHidden():
                visible_features_list.append([item.data(0), item.data(3), bool(item.data(4))])

        self.parent.filteredCheckedItemListEvent(visible_features_list, True)


    def selectAllFeatures(self):
        # THREAD SAFETY FIX (v2.3.12): Use thread-safe featureSource() instead of layer
        data_provider = self.layer.dataProvider()
        layer_features_source = data_provider.featureSource() if data_provider else None

        if self.sub_action == 'Select All':

            list_widget = self.parent.list_widgets[self.layer.id()]
            total_count = list_widget.count()
            if layer_features_source:
                nonSubset_features_list = [get_feature_attribute(feature, self.identifier_field_name) for feature in safe_iterate_features(layer_features_source)]
            else:
                nonSubset_features_list = []

            for index in range(total_count):
                item = list_widget.item(index)
                if not item.isHidden():
                    item.setCheckState(Qt.Checked)
                    item.setData(6,self.parent.font_by_state['checked'][0])
                    item.setData(9,QBrush(self.parent.font_by_state['checked'][1]))
                    item.setData(4,"True")
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)

        
        elif self.sub_action == 'Select All (non subset)':

            list_widget = self.parent.list_widgets[self.layer.id()]
            widget_count = list_widget.count()
            if layer_features_source:
                nonSubset_features_list = [get_feature_attribute(feature, self.identifier_field_name) for feature in safe_iterate_features(layer_features_source)]
            else:
                nonSubset_features_list = []
            total_count = widget_count - len(nonSubset_features_list)

            for index in range(widget_count):
                item = list_widget.item(index)
                if not item.isHidden():
                    if item.data(3) not in nonSubset_features_list:
                        item.setCheckState(Qt.Checked)
                        item.setData(6,self.parent.font_by_state['checkedFiltered'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['checkedFiltered'][1]))
                        item.setData(4,"False")
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)
        

        elif self.sub_action == 'Select All (subset)':

            if layer_features_source:
                nonSubset_features_list = [get_feature_attribute(feature, self.identifier_field_name) for feature in safe_iterate_features(layer_features_source)]
            else:
                nonSubset_features_list = []
            total_count = len(nonSubset_features_list)
            list_widget = self.parent.list_widgets[self.layer.id()]
            widget_count = list_widget.count()

            for index in range(widget_count):
                item = list_widget.item(index)
                if not item.isHidden():
                    if item.data(3) in nonSubset_features_list:
                        item.setCheckState(Qt.Checked)
                        item.setData(6,self.parent.font_by_state['checked'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['checked'][1]))
                        item.setData(4,"True")
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)

        self.updateFeatures()


    def deselectAllFeatures(self):
        # THREAD SAFETY FIX (v2.3.12): Use thread-safe featureSource() instead of layer
        data_provider = self.layer.dataProvider()
        layer_features_source = data_provider.featureSource() if data_provider else None

        if self.sub_action == 'De-select All':

            list_widget = self.parent.list_widgets[self.layer.id()]
            total_count = list_widget.count()
            if layer_features_source:
                nonSubset_features_list = [get_feature_attribute(feature, self.identifier_field_name) for feature in safe_iterate_features(layer_features_source)]
            else:
                nonSubset_features_list = []

            for index in range(total_count):
                item = list_widget.item(index)
                if not item.isHidden():
                    item.setCheckState(Qt.Unchecked)
                    item.setData(6,self.parent.font_by_state['unChecked'][0])
                    item.setData(9,QBrush(self.parent.font_by_state['unChecked'][1]))
                    item.setData(4,"True")
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)

        elif self.sub_action == 'De-select All (non subset)':

            list_widget = self.parent.list_widgets[self.layer.id()]
            widget_count = list_widget.count()
            if layer_features_source:
                nonSubset_features_list = [get_feature_attribute(feature, self.identifier_field_name) for feature in safe_iterate_features(layer_features_source)]
            else:
                nonSubset_features_list = []
            total_count = widget_count - len(nonSubset_features_list)

            for index in range(widget_count):
                item = list_widget.item(index)
                if not item.isHidden():
                    if item.data(3) not in nonSubset_features_list:
                        item.setCheckState(Qt.Unchecked)
                        item.setData(6,self.parent.font_by_state['unCheckedFiltered'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['unCheckedFiltered'][1]))
                        item.setData(4,"False")
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)


        elif self.sub_action == 'De-select All (subset)':

            if layer_features_source:
                nonSubset_features_list = [get_feature_attribute(feature, self.identifier_field_name) for feature in safe_iterate_features(layer_features_source)]
            else:
                nonSubset_features_list = []
            total_count = len(nonSubset_features_list)
            list_widget = self.parent.list_widgets[self.layer.id()]
            widget_count = list_widget.count()

            for index in range(widget_count):
                item = list_widget.item(index)
                if not item.isHidden():
                    if item.data(3) in nonSubset_features_list:
                        item.setCheckState(Qt.Unchecked)
                        item.setData(6,self.parent.font_by_state['unCheckedFiltered'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['unCheckedFiltered'][1]))
                        item.setData(4,"False")
                # PERFORMANCE: Use batched progress updates
                self._update_progress_batched(index, total_count)

        self.updateFeatures()

    
    def updateFeatures(self):

        selection_data = []
        visible_data = []
        list_widget = self.parent.list_widgets[self.layer.id()]
        total_count = list_widget.count()
        for index in range(total_count):
            item = list_widget.item(index)
            if item.checkState() == Qt.Checked:
                selection_data.append([item.data(0), item.data(3), bool(item.data(4))])
            visible_data.append([item.data(0), item.data(3), bool(item.data(4))])
            # PERFORMANCE: Use batched progress updates
            self._update_progress_batched(index, total_count)
        selection_data.sort(key=lambda k: k[0])
        self.parent.items_le.setText(', '.join([data[0] for data in selection_data]))
        self.parent.list_widgets[self.layer.id()].setSelectedFeaturesList(selection_data)
        self.parent.list_widgets[self.layer.id()].setVisibleFeaturesList(visible_data)
        self.parent.updatedCheckedItemListEvent(selection_data, True)
        
    
    def cancel(self):
        # Task cancellation is normal user behavior (switching layers, changing selection, etc.)
        # Log at Info level to reduce noise in the log panel
        QgsMessageLog.logMessage(
            '"{name}" was canceled'.format(name=self.description()),
            'FilterMate', Qgis.Info)
        super().cancel()


    def finished(self, result):
        """This function is called automatically when the task is completed and is
        called from the main thread so it is safe to interact with the GUI etc here"""
        if result is False:
            if self.isCanceled():
                # Task was cancelled by user - no need to show message
                pass
            elif self.exception is None:
                # Task failed without exception - log details for debugging
                layer_name = self.layer.name() if self.layer else 'Unknown'
                QgsMessageLog.logMessage(
                    f'Task "{self.action}" failed for layer "{layer_name}" without exception',
                    'FilterMate', Qgis.Warning)
            else:
                # Log full exception details to QGIS Message Log
                import traceback
                layer_name = self.layer.name() if self.layer else 'Unknown'
                error_details = f'Task "{self.action}" failed for layer "{layer_name}": {str(self.exception)}'
                QgsMessageLog.logMessage(error_details, 'FilterMate', Qgis.Critical)
                QgsMessageLog.logMessage(f'Traceback: {traceback.format_exc()}', 'FilterMate', Qgis.Info)
                
                show_error('FilterMate', f'Error occurred: {str(self.exception)}')
                logger.error(f'Task failed with exception: {self.exception}', exc_info=True)


class QgsCheckableComboBoxFeaturesListPickerWidget(QWidget):
    '''
    Copy and paste this class into your PyQGIS project/ plugin
    '''
    updatingCheckedItemList = pyqtSignal(list, bool)
    filteringCheckedItemList = pyqtSignal()
    
    def __init__(self, config_data, parent=None):
        self.parent = parent
        QDialog.__init__(self)


        self.config_data = config_data
        
        # Dynamic sizing based on UIConfig
        try:
            from .ui_config import UIConfig
            combobox_height = UIConfig.get_config('combobox', 'height') or 30
            list_min_height = UIConfig.get_config('list', 'min_height') or 150
            
            # Calculate total height: 2 QLineEdit + spacing + list
            lineedit_height = combobox_height * 2 + 2  # 2 lineEdit + spacing
            total_min_height = lineedit_height + list_min_height + 4  # +4 for layout spacing
        except (AttributeError, TypeError, ValueError):
            total_min_height = 210  # Fallback: 54px (lineEdits) + 150px (list) + 6px
        
        self.setMinimumWidth(30)
        self.setMaximumWidth(16777215)
        self.setMinimumHeight(total_min_height)
        # Remove setMaximumHeight to allow expansion
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont("Segoe UI", 8)
        self.setFont(font)


        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.filter_le = QLineEdit(self)
        self.filter_le.setPlaceholderText('Type to filter...')
        self.items_le = QLineEdit(self)
        self.items_le.setReadOnly(True)

        self.layout.addWidget(self.filter_le)
        self.layout.addWidget(self.items_le)




        self.context_menu = QMenu(self)
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(lambda state, x='Select All': self.select_all(x))
        self.action_check_all_non_subset = QAction('Select All (non subset)', self)
        self.action_check_all_non_subset.triggered.connect(lambda state, x='Select All (non subset)': self.select_all(x))
        self.action_check_all_subset = QAction('Select All (subset)', self)
        self.action_check_all_subset.triggered.connect(lambda state, x='Select All (subset)': self.select_all(x))
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(lambda state, x='De-select All': self.deselect_all(x))
        self.action_uncheck_all_non_subset = QAction('De-select All (non subset)', self)
        self.action_uncheck_all_non_subset.triggered.connect(lambda state, x='De-select All (non subset)': self.deselect_all(x))
        self.action_uncheck_all_subset = QAction('De-select All (subset)', self)
        self.action_uncheck_all_subset.triggered.connect(lambda state, x='De-select All (subset)': self.deselect_all(x))

        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_check_all_non_subset)
        self.context_menu.addAction(self.action_check_all_subset)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.action_uncheck_all)
        self.context_menu.addAction(self.action_uncheck_all_non_subset)
        self.context_menu.addAction(self.action_uncheck_all_subset)

        # Use config helpers for color access
        from .config_helpers import get_font_colors
        font_colors = get_font_colors(self.config_data)
        self.font_by_state = {'unChecked':(QFont("Segoe UI", 8, QFont.Medium),(QColor(font_colors[0]))),
                              'checked':(QFont("Segoe UI", 8, QFont.Bold),(QColor(font_colors[0]))),
                              'unCheckedFiltered':(QFont("Segoe UI", 8, QFont.Medium),(QColor(font_colors[2]))),
                              'checkedFiltered':(QFont("Segoe UI", 8, QFont.Bold),(QColor(font_colors[2])))}


        self.list_widgets = {}

        self.tasks = {}


        self.tasks['buildFeaturesList'] = {}
        self.tasks['updateFeaturesList'] = {}
        self.tasks['loadFeaturesList'] = {}
        self.tasks['selectAllFeatures'] = {}
        self.tasks['deselectAllFeatures'] = {}
        self.tasks['filterFeatures'] = {}
        self.tasks['updateFeatures'] = {}

        self.last_layer = None
        self.layer = None
        self.is_field_flag = None
        
        # Sort order settings (ASC/DESC)
        self._sort_order = 'ASC'
        self._sort_field = None
        
        # Debounce timer for filter text input to prevent launching many tasks
        # when user types quickly - waits 300ms after last keystroke before filtering
        self._filter_debounce_timer = QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.setInterval(300)  # 300ms debounce delay
        self._filter_debounce_timer.timeout.connect(self._execute_filter)

    def setSortOrder(self, order='ASC', field=None):
        """
        Set the sort order for the features list.
        
        Args:
            order: 'ASC' or 'DESC' for ascending/descending order
            field: Optional field name for sorting (if None, uses display expression)
        """
        self._sort_order = order
        self._sort_field = field
        logger.debug(f"QgsCheckableComboBoxFeaturesListPickerWidget.setSortOrder: order={order}, field={field}")
        
        # If we have a layer and list widget, re-sort and refresh
        if self.layer is not None and self.layer.id() in self.list_widgets:
            # Trigger a refresh to apply the new sort order
            expression = self.list_widgets[self.layer.id()].getDisplayExpression()
            if expression:
                self.setDisplayExpression(expression)
    
    def getSortOrder(self):
        """
        Get the current sort order settings.
        
        Returns:
            tuple: (order, field) where order is 'ASC' or 'DESC'
        """
        return (self._sort_order, self._sort_field)

    def checkedItems(self):
        selection = []
        # Vérifier que le layer existe toujours dans list_widgets
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return selection
            
        for i in range(self.list_widgets[self.layer.id()].count()):
            item = self.list_widgets[self.layer.id()].item(i)
            if item.checkState() == Qt.Checked:
                selection.append([item.data(0), item.data(3),  item.data(6), item.data(9)])
        selection.sort(key=lambda k: k[0])
        return selection

    def displayExpression(self):
        if self.layer is not None:
            return self.list_widgets[self.layer.id()].getDisplayExpression()
        else:
            return False
      
    def currentLayer(self):
        if self.layer is not None:
            return self.layer
        else:
            return False
    
    def currentSelectedFeatures(self):
        if self.layer is not None:
            # Vérifier que le layer existe toujours dans list_widgets
            if self.layer.id() not in self.list_widgets:
                return False
            current_selected_features = self.list_widgets[self.layer.id()].getSelectedFeaturesList()
            return current_selected_features if len(current_selected_features) > 0 else False
        else:
            return False
        
    def currentVisibleFeatures(self):
        if self.layer is not None:
            # Vérifier que le layer existe toujours dans list_widgets
            if self.layer.id() not in self.list_widgets:
                return False
            visible_features_list = self.list_widgets[self.layer.id()].getVisibleFeaturesList()
            return visible_features_list if len(visible_features_list) > 0 else False
        else:
            return False
        
    def setLayer(self, layer, layer_props):

        try:

            if layer is not None:
                # Cancel all tasks for the OLD layer BEFORE changing to new layer
                if self.layer is not None:
                    old_layer_id = self.layer.id()
                    # Stop any pending debounce filter to prevent filtering on wrong layer
                    self._filter_debounce_timer.stop()
                    # Cancel all pending tasks for the old layer
                    for task_type in self.tasks:
                        if old_layer_id in self.tasks[task_type]:
                            try:
                                if isinstance(self.tasks[task_type][old_layer_id], QgsTask):
                                    self.tasks[task_type][old_layer_id].cancel()
                                    logger.debug(f"Cancelled task {task_type} for old layer {old_layer_id}")
                            except (RuntimeError, KeyError):
                                # Task already finished or doesn't exist
                                pass
                    
                    self.filter_le.clear()
                    self.items_le.clear()
                    
                self.layer = layer

                # Ensure the widget exists for the new layer BEFORE accessing it
                if self.layer.id() not in self.list_widgets:
                    self.manage_list_widgets(layer_props)

                # Validate required keys exist before accessing - with fallback
                pk_name = layer_props.get("infos", {}).get("primary_key_name")
                if pk_name is not None and self.layer.id() in self.list_widgets:
                    # Update identifier field name if it changed (important when reusing widgets)
                    if self.list_widgets[self.layer.id()].getIdentifierFieldName() != pk_name:
                        logger.debug(f"Updating identifier field from '{self.list_widgets[self.layer.id()].getIdentifierFieldName()}' to '{pk_name}' for layer {self.layer.name()}")
                        self.list_widgets[self.layer.id()].setIdentifierFieldName(pk_name)
                    
                    # CRITICAL: Clear stale display expression when reusing a widget
                    # This prevents using expressions from a different layer with the same ID
                    current_expr = self.list_widgets[self.layer.id()].getDisplayExpression()
                    if current_expr and current_expr != pk_name:
                        # Widget has an expression that's not the primary key
                        # Reset it to ensure it will be updated with correct layer_props expression
                        logger.debug(f"Resetting stale display expression '{current_expr}' for reused widget of layer {self.layer.name()}")
                        self.list_widgets[self.layer.id()].setDisplayExpression("")
                elif self.layer.id() in self.list_widgets:
                    # FALLBACK: pk_name is None but widget was created with fallback identifier
                    # Just log for debugging, widget should still work
                    logger.debug(f"Using fallback identifier for layer {layer.name()} (pk_name was None)")

                # Refresh widgets (will show existing or just-created widget)
                self.manage_list_widgets(layer_props)

                # Additional safety check: ensure widget was successfully created
                if self.layer.id() in self.list_widgets:
                    self.filter_le.setText(self.list_widgets[self.layer.id()].getFilterText())

                    # ALWAYS update display expression when changing layer to ensure
                    # we use the correct expression from layer_props, not a stale value
                    # from a previous layer with the same widget
                    expected_expression = layer_props.get("exploring", {}).get("multiple_selection_expression", "")
                    current_expression = self.list_widgets[self.layer.id()].getDisplayExpression()
                    
                    # Force update if expression is different OR if widget was just created/reused
                    if current_expression != expected_expression or not current_expression:
                        logger.debug(f"Updating display expression from '{current_expression}' to '{expected_expression}' for layer {self.layer.name()}")
                        self.setDisplayExpression(expected_expression)
                    else:
                        description = 'Loading features'
                        action = 'loadFeaturesList'
                        self.build_task(description, action, True)
                        self.launch_task(action)
                else:
                    logger.error(f"Failed to create list widget for layer {self.layer.id()}")

        except (AttributeError, RuntimeError) as e:
            # Handle case where widgets don't exist or are being destroyed
            try:
                self.filter_le.clear()
                self.items_le.clear()
            except (AttributeError, RuntimeError):
                pass
    

    def setFilterExpression(self, filter_expression, layer_props):
        if self.layer is not None:
            if self.layer.id() not in self.list_widgets:
                self.manage_list_widgets(layer_props)
            if self.layer.id() in self.list_widgets:  
                if filter_expression != self.list_widgets[self.layer.id()].getFilterExpression():
                    if QgsExpression(filter_expression).isField() is False:
                        self.list_widgets[self.layer.id()].setFilterExpression(filter_expression)
                        expression = self.list_widgets[self.layer.id()].getDisplayExpression()
                        self.setDisplayExpression(expression)


    def setDisplayExpression(self, expression):
        
        logger.debug(f"QgsCheckableComboBoxFeaturesListPickerWidget.setDisplayExpression called with: {expression}")
        
        if self.layer is not None:
            logger.debug(f"layer.id()={self.layer.id()}, list_widgets keys={list(self.list_widgets.keys())}")
            # Check if widget exists for this layer
            if self.layer.id() not in self.list_widgets:
                logger.warning(f"No list widget found for layer {self.layer.id()} in setDisplayExpression")
                return
            
            self.filter_le.clear()
            self.items_le.clear()
            
            # Handle empty or invalid expression - fall back to identifier field
            working_expression = expression
            if not expression or expression.strip() == '':
                # Expression is empty, use identifier field as fallback
                identifier_field = self.list_widgets[self.layer.id()].getIdentifierFieldName()
                if identifier_field:
                    logger.debug(f"Empty expression provided, using identifier field '{identifier_field}' for layer '{self.layer.name()}'")
                    working_expression = identifier_field
                    self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
                else:
                    # No identifier field available, try first field
                    field_names = [field.name() for field in self.layer.fields()]
                    if field_names:
                        working_expression = field_names[0]
                        logger.debug(f"No identifier field, using first field '{working_expression}' for layer '{self.layer.name()}'")
                        self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
                    else:
                        logger.warning(f"No fields available for layer '{self.layer.name()}', cannot set display expression")
                        return
            elif QgsExpression(expression).isField():
                working_expression = expression.replace('"', '')
                self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
            else:
                # It's a complex expression, validate it
                expr = QgsExpression(expression)
                if not expr.isValid():
                    # Invalid expression, fall back to identifier field
                    identifier_field = self.list_widgets[self.layer.id()].getIdentifierFieldName()
                    if identifier_field:
                        logger.debug(f"Invalid expression '{expression}', using identifier field '{identifier_field}' for layer '{self.layer.name()}'")
                        working_expression = identifier_field
                        self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
                    else:
                        logger.warning(f"Invalid expression and no identifier field for layer '{self.layer.name()}'")
                        return
                else:
                    working_expression = expression
                    self.list_widgets[self.layer.id()].setExpressionFieldFlag(False)

            self.list_widgets[self.layer.id()].setDisplayExpression(working_expression)

            sub_description = 'Building features list'
            sub_action = 'buildFeaturesList'

            self.build_task(sub_description, sub_action)

            description = 'Loading features'
            action = 'loadFeaturesList'
            self.build_task(description, action)

            self.tasks['loadFeaturesList'][self.layer.id()].addSubTask(self.tasks[sub_action][self.layer.id()], [], QgsTask.ParentDependsOnSubTask)

            self.launch_task('loadFeaturesList')
                
        

    def eventFilter(self, obj, event):

        # Safety check: ensure layer and widget exist
        if self.layer is None or self.layer.id() not in self.list_widgets:
            return False
        
        if event.type() == QEvent.MouseButtonPress and obj == self.list_widgets[self.layer.id()].viewport():
            identifier_field_name = self.list_widgets[self.layer.id()].getIdentifierFieldName()
            nonSubset_features_list = [feature[identifier_field_name] for feature in safe_iterate_features(self.layer)]
            if event.button() == Qt.LeftButton:
                clicked_item = self.list_widgets[self.layer.id()].itemAt(event.pos())
                if clicked_item is not None:
                    id_item = clicked_item.data(3)
                    if clicked_item.checkState() == Qt.Checked:
                        clicked_item.setCheckState(Qt.Unchecked)
                        if id_item in nonSubset_features_list:
                            clicked_item.setData(6,self.font_by_state['unChecked'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['unChecked'][1]))
                            clicked_item.setData(4,"True")
                        else:
                            clicked_item.setData(6,self.font_by_state['unCheckedFiltered'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['unCheckedFiltered'][1]))
                            clicked_item.setData(4,"False")

                    else:
                        clicked_item.setCheckState(Qt.Checked)
                        if id_item in nonSubset_features_list:
                            clicked_item.setData(6,self.font_by_state['checked'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['checked'][1]))
                            clicked_item.setData(4,"True")
                        else:   
                            clicked_item.setData(6,self.font_by_state['checkedFiltered'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['checkedFiltered'][1]))
                            clicked_item.setData(4,"False")
                        
                description = 'Selecting feature'
                action = 'updateFeatures'
                self.build_task(description, action, True)
                self.launch_task(action)

            elif event.button() == Qt.RightButton:
                self.context_menu.exec(QCursor.pos())
            return True
        return False


    def connect_filter_lineEdit(self):

        if self.layer is not None:
            if self.layer.id() in self.list_widgets:
                if self.list_widgets[self.layer.id()].getTotalFeaturesListCount() == self.list_widgets[self.layer.id()].count():
                    try:
                        self.filter_le.editingFinished.disconnect()
                    except TypeError:
                        # Signal not connected
                        pass
                    # Use debounced filtering to prevent launching many tasks on each keystroke
                    self.filter_le.textChanged.connect(self._on_filter_text_changed)
                else:
                    try:
                        self.filter_le.textChanged.disconnect()
                    except TypeError:
                        # Signal not connected
                        pass
                    self.filter_le.editingFinished.connect(self.filter_items)
    
    def _on_filter_text_changed(self, text):
        """Handle filter text changes with debouncing.
        
        Restarts the debounce timer on each keystroke. The actual filtering
        will only execute 300ms after the user stops typing, preventing
        task accumulation and QGIS freezes.
        """
        # Store the current text for when the timer fires
        self._pending_filter_text = text
        # Restart the debounce timer
        self._filter_debounce_timer.start()
    
    def _execute_filter(self):
        """Execute the filter after debounce delay.
        
        Called by the debounce timer when user has stopped typing.
        """
        if hasattr(self, '_pending_filter_text'):
            self.filter_items(self._pending_filter_text)



    def manage_list_widgets(self, layer_props):
        for key in self.list_widgets.keys():
            self.list_widgets[key].setVisible(False)

        if self.layer.id() in self.list_widgets:
            self.list_widgets[self.layer.id()].setVisible(True)
        else:
            self.add_list_widget(layer_props)


    def remove_list_widget(self, layer_id):
        if layer_id in self.list_widgets:
            for task in self.tasks:
                try:
                    del self.tasks[task][layer_id]
                except KeyError:
                    # Task doesn't exist for this layer
                    pass
            try:
                del self.list_widgets[layer_id]
            except KeyError:
                # Widget already removed
                pass

    def reset(self):
        # Stop any pending debounce filter
        self._filter_debounce_timer.stop()
        self.layer = None
        self.tasks = {}
        self.tasks['buildFeaturesList'] = {}
        self.tasks['updateFeaturesList'] = {}
        self.tasks['loadFeaturesList'] = {}
        self.tasks['selectAllFeatures'] = {}
        self.tasks['deselectAllFeatures'] = {}
        self.tasks['filterFeatures'] = {}
        self.tasks['updateFeatures'] = {}
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            widget = item.widget()       
            if widget:
                try:
                    widget.close()
                except RuntimeError:
                    # Widget already deleted or being destroyed
                    pass

        self.list_widgets = {}


    def add_list_widget(self, layer_props):
        # Validate required keys exist
        if "infos" not in layer_props:
            logger.warning("layer_props missing 'infos' dictionary in add_list_widget")
            return
        
        infos = layer_props["infos"]
        
        # FALLBACK FIX: Use sensible defaults when primary key info is missing
        # This allows the widget to work even without proper primary key detection
        pk_name = infos.get("primary_key_name")
        pk_is_numeric = infos.get("primary_key_is_numeric", True)  # Default to numeric
        
        if pk_name is None:
            # FALLBACK: Try to find a suitable identifier field
            # Priority: fid (OGR), id, then first field
            logger.warning(f"primary_key_name is None, attempting fallback for layer widget")
            
            if self.layer is not None:
                fields = self.layer.fields()
                # Try common ID field names
                fallback_names = ['fid', 'id', 'ID', 'FID', 'ogc_fid', 'gid']
                for fallback_name in fallback_names:
                    if fields.indexFromName(fallback_name) >= 0:
                        pk_name = fallback_name
                        # Check if field is numeric
                        field = fields.field(fallback_name)
                        pk_is_numeric = field.isNumeric() if field else True
                        logger.info(f"Using fallback identifier field: {pk_name} (numeric={pk_is_numeric})")
                        break
                
                # If still no pk_name, use first field as last resort
                if pk_name is None and fields.count() > 0:
                    pk_name = fields.field(0).name()
                    pk_is_numeric = fields.field(0).isNumeric()
                    logger.info(f"Using first field as fallback identifier: {pk_name} (numeric={pk_is_numeric})")
        
        if pk_name is None:
            logger.error("Could not determine any identifier field for list widget")
            return
        
        self.list_widgets[self.layer.id()] = ListWidgetWrapper(pk_name, pk_is_numeric, self)
        self.list_widgets[self.layer.id()].viewport().installEventFilter(self)
        self.layout.addWidget(self.list_widgets[self.layer.id()])




    def select_all(self, x):
        action = 'selectAllFeatures'
        self.build_task(x, action)
        self.launch_task(action)

    def deselect_all(self, x):
        action = 'deselectAllFeatures'
        self.build_task(x, action)
        self.launch_task(action)
        
    def filter_items(self, filter_txt=None):
        if filter_txt is None:
            self.filter_txt_limit_changed = True
            self.filter_txt = self.filter_le.text()
        else:
            self.filter_txt_limit_changed = False    
            self.filter_txt = filter_txt
            
        description = 'Filtering features'
        action = 'filterFeatures'
        self.build_task(description, action)
        self.launch_task(action)
    
    def build_task(self, description, action, silent_flag=False):
        """Build a new task for populating features list.
        
        CRITICAL FIX: Cancel existing tasks before creating new ones to prevent
        task accumulation during project load which causes freezes.
        
        Args:
            description: Task description for progress display
            action: 'buildFeaturesList' or 'loadFeaturesList'
            silent_flag: If True, suppress progress notifications
        """
        # Cancel any existing task for this layer/action to prevent accumulation
        if self.layer.id() in self.tasks[action]:
            existing_task = self.tasks[action][self.layer.id()]
            # Check if the C++ object still exists before accessing its methods
            # to avoid RuntimeError: wrapped C/C++ object has been deleted
            if isinstance(existing_task, QgsTask) and not sip.isdeleted(existing_task):
                if existing_task.status() in [QgsTask.Running, QgsTask.Queued]:
                    logger.debug(f"Cancelling existing {action} task for layer {self.layer.id()}")
                    existing_task.cancel()
  
        self.tasks[action][self.layer.id()] = PopulateListEngineTask(description, self, action, silent_flag)
        self.tasks[action][self.layer.id()].setDependentLayers([self.layer])

        # Message bar notification removed - too verbose for user experience
        # Task progress is visible in QGIS task manager if needed


    def launch_task(self, action):

        self.tasks[action][self.layer.id()].taskCompleted.connect(self.connect_filter_lineEdit)
        QgsApplication.taskManager().addTask(self.tasks[action][self.layer.id()])


    def updatedCheckedItemListEvent(self, data, flag):
        self.list_widgets[self.layer.id()].setSelectedFeaturesList(data)
        self.updatingCheckedItemList.emit(data, flag)

    def filteredCheckedItemListEvent(self, data, flag):
        self.list_widgets[self.layer.id()].setVisibleFeaturesList(data)
        self.filteringCheckedItemList.emit()



class ListWidgetWrapper(QListWidget):
  
    def __init__(self, identifier_field_name, primary_key_is_numeric, parent=None):

        super(ListWidgetWrapper, self).__init__(parent)

        # Dynamic sizing based on UIConfig - minimum height for displaying multiple items
        try:
            from .ui_config import UIConfig
            list_min_height = UIConfig.get_config('list', 'min_height') or 120
        except (ImportError, AttributeError, KeyError):
            list_min_height = 120  # Reduced height for compact display (3-4 items)
        
        self.setMinimumHeight(list_min_height)
        self.identifier_field_name = identifier_field_name
        self.identifier_field_type_numeric = primary_key_is_numeric
        self.filter_expression = ''
        self.filter_text = ''
        self.display_expression = ''
        self.field_flag = False
        self.subset_string = ''
        self.features_list = []
        self.filter_expression_features_id_list = []
        self.visible_features_list = []
        self.selected_features_list = []
        self.limit = 1000
        self.total_features_list_count = 0

    def setFilterExpression(self, filter_expression):
        self.filter_expression = filter_expression

    def setIdentifierFieldName(self, identifier_field_name):
        self.identifier_field_name = identifier_field_name

    def setFilterText(self, filter_text):
        self.filter_text = filter_text

    def setDisplayExpression(self, display_expression):
        self.display_expression = display_expression

    def setExpressionFieldFlag(self, field_flag):
        self.field_flag = field_flag    
    
    def setSubsetString(self, subset_string):
        self.subset_string = subset_string

    def setTotalFeaturesListCount(self, total_features_list_count):
        self.total_features_list_count = total_features_list_count

    def setFeaturesList(self, features_list):
        self.features_list = features_list

    def setFilterExpressionFeaturesIdList(self, filter_expression_features_id_list):
        self.filter_expression_features_id_list = filter_expression_features_id_list

    def setVisibleFeaturesList(self, visible_features_list):
        self.visible_features_list = visible_features_list

    def setSelectedFeaturesList(self, selected_features_list):
        self.selected_features_list = selected_features_list
    
    def setLimit(self, limit):
        self.limit = limit

    def getFilterExpression(self):
        return self.filter_expression

    def getIdentifierFieldName(self):
        return self.identifier_field_name
    
    def getFilterText(self):
        return self.filter_text

    def getDisplayExpression(self):
        return self.display_expression
    
    def getExpressionFieldFlag(self):
        return self.field_flag
    
    def getSubsetString(self):
        return self.subset_string
    
    def getTotalFeaturesListCount(self):
        return self.total_features_list_count
      
    def getFilterExpressionFeaturesIdList(self):
        return self.filter_expression_features_id_list

    def getFeaturesList(self):
        return self.features_list
    
    def getVisibleFeaturesList(self):
        return self.visible_features_list
    
    def getSelectedFeaturesList(self):
        return self.selected_features_list

    def getLimit(self):
        return self.limit
    
    def sortFeaturesListByDisplayExpression(self, nonSubset_features_list=[], reverse=False):
        """
        Sort features list by display expression.
        
        FIX v2.5.7: Handle None values in sort key to prevent TypeError
        when comparing str with NoneType.
        
        FIX v2.5.8: Added reverse parameter to support DESC order.
        
        Args:
            nonSubset_features_list: List of feature IDs that are not in the current subset
            reverse: If True, sort in descending order (DESC)
        """
        def safe_sort_key(k):
            # k[0] is the display expression value, k[1] is the feature id
            # Handle None values by converting to empty string for comparison
            display_value = k[0] if k[0] is not None else ""
            is_in_subset = k[1] not in nonSubset_features_list
            return (is_in_subset, display_value)
        
        self.features_list.sort(key=safe_sort_key, reverse=reverse)


class QgsCheckableComboBoxLayer(QComboBox):
    

    checkedItemsChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super(QgsCheckableComboBoxLayer, self).__init__(parent)

        self.parent = parent
        
        # Dynamic sizing based on UIConfig
        try:
            from .ui_config import UIConfig
            combobox_height = UIConfig.get_config('combobox', 'height') or 30
        except (ImportError, AttributeError, KeyError):
            combobox_height = 30
        
        self.setBaseSize(combobox_height, 0)
        self.setMinimumHeight(combobox_height)
        self.setMinimumWidth(30)
        self.setMaximumHeight(combobox_height)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)
        self.setFont(font)

        self.setModel(QtGui.QStandardItemModel(self))
        self.setItemDelegate(ItemDelegate(self))
        self.createMenuContext()

        self.view().setModel(self.model())
        
        self.installEventFilter(self)
        self.view().viewport().installEventFilter(self)


    def createMenuContext(self):
        self.context_menu = QMenu(self)
        
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(self.select_all)
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(self.deselect_all)
        self.action_check_all_geometry_line = QAction('Select all layers by geometry type (Lines)', self)
        self.action_check_all_geometry_line.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Line', Qt.Checked))
        self.action_uncheck_all_geometry_line = QAction('De-Select all layers by geometry type (Lines)', self)
        self.action_uncheck_all_geometry_line.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Line', Qt.Unchecked))
        self.action_check_all_geometry_point = QAction('Select all layers by geometry type (Points)', self)
        self.action_check_all_geometry_point.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Point', Qt.Checked))
        self.action_uncheck_all_geometry_point = QAction('De-Select all layers by geometry type (Lines)', self)
        self.action_uncheck_all_geometry_point.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Point', Qt.Unchecked))
        self.action_check_all_geometry_polygon = QAction('Select all layers by geometry type (Polygons)', self)
        self.action_check_all_geometry_polygon.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Polygon', Qt.Checked))
        self.action_uncheck_all_geometry_polygon = QAction('De-Select all layers by geometry type (Polygon)', self)
        self.action_uncheck_all_geometry_polygon.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Polygon', Qt.Unchecked))

        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_uncheck_all)
        self.context_menu.addSeparator()    
        self.context_menu.addAction(self.action_check_all_geometry_line)
        self.context_menu.addAction(self.action_uncheck_all_geometry_line)
        self.context_menu.addSeparator()    
        self.context_menu.addAction(self.action_check_all_geometry_point)
        self.context_menu.addAction(self.action_uncheck_all_geometry_point)
        self.context_menu.addSeparator()        
        self.context_menu.addAction(self.action_check_all_geometry_polygon)
        self.context_menu.addAction(self.action_uncheck_all_geometry_polygon)

            
    def addItem(self, icon, text, data=None):

        item = QStandardItem()
        item.setCheckable(True)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setData(Qt.Unchecked, Qt.CheckStateRole)
        item.setText(text)
        item.setData(text, role=Qt.DisplayRole)
        item.setData(icon, role=Qt.DecorationRole)


        if data is not None:
            item.setData(data, role=Qt.UserRole)

        
        
    
        self.model().appendRow(item)



    def setItemCheckState(self, i, state=None):
        item = self.model().item(i)
        if state is not None:
            item.setCheckState(state)
        else:
            state = item.data(Qt.CheckStateRole)
            if state == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            elif state == Qt.Unchecked:
                item.setCheckState(Qt.Checked)

    def setItemsCheckState(self, input_list, state):
        assert isinstance(input_list, list)
        for i in input_list:
            item = self.model().item(i)
            item.setCheckState(state)
        self.checkedItemsChangedEvent()

            
    def setCheckedItems(self, input_list):
        assert isinstance(input_list, list)
        for text in input_list:
            items = self.model().findItems(text)
            for item in items:
                item.setCheckState(Qt.Checked)
    

    def select_all(self):
        for i in range(self.count()):
            item = self.model().item(i)
            item.setCheckState(Qt.Checked)
        self.checkedItemsChangedEvent()

    def deselect_all(self):
        for i in range(self.count()):
            item = self.model().item(i)
            item.setCheckState(Qt.Unchecked)       
        self.checkedItemsChangedEvent()

    def select_by_geometry(self, geometry_type, state):
        items_to_be_checked = []
        for i in range(self.count()):
            item = self.model().item(i)
            data = item.data(Qt.UserRole)
            if data and isinstance(data, dict) and "layer_geometry_type" in data:
                if data["layer_geometry_type"] == geometry_type:
                    items_to_be_checked.append(i)
        self.setItemsCheckState(items_to_be_checked, state)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonRelease and obj == self.view().viewport() and event.button() == Qt.LeftButton:
            index = self.view().currentIndex()
            item = self.model().itemFromIndex(index)
            state = index.data(Qt.CheckStateRole)
            if state == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            elif state == Qt.Unchecked:
                item.setCheckState(Qt.Checked)
            return True
        elif event.type() == QEvent.MouseButtonRelease and obj in [self.view().viewport(), self] and event.button() == Qt.RightButton:
            action = self.context_menu.exec_(QCursor.pos())
            if action:
                return True
            else:
                return False
        return False



    def itemCheckState(self, i):
        item = self.model().item(i)
        if item:
            return item.checkState()
    

    def checkedItems(self):
        checked_items = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                checked_items.append(item.text())
        checked_items.sort()
        return checked_items



        
    def checkedItemsChangedEvent(self):
        event = self.checkedItems()
        self.checkedItemsChanged.emit(event)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = ",".join(self.checkedItems())
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)


class ItemDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent=None, *args):
        QtWidgets.QStyledItemDelegate.__init__(self, parent, *args)
        self.parent = parent


    # overrides
    def sizeHint(self, option, index):
        ish = option.decorationSize.height()
        isw = option.decorationSize.width()
        return QtCore.QSize(isw, ish)


    def getCheckboxRect(self, option):
        return QtCore.QRect(4, 4, 18, 18).translated(option.rect.topLeft())
    
    def getItemRect(self, item):
        size_hint = item.sizeHint()
        return QtCore.QRect(0, 0, size_hint.width(), size_hint.height())

    def paint(self, painter, option, index):
        painter.save()


        # Draw
        ish = option.decorationSize.height()
        isw = option.decorationSize.width()
        x, y, dx, dy = option.rect.x(), option.rect.y(), option.rect.width(), option.rect.height()


        text = index.data(QtCore.Qt.DisplayRole)
        if text:
           painter.drawText(int(x + isw*2 + 4), int(y + 4 + ish/2), text)

        # Decoration
        pic = index.data(QtCore.Qt.DecorationRole)
        if pic:
            if isinstance(pic, QtGui.QIcon):
                painter.drawPixmap(x + isw, y, pic.pixmap(int(isw), int(ish)))
            elif isinstance(pic, QtGui.QPixmap):
                painter.drawPixmap(x + isw, y, pic.scaled(int(isw), int(ish), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

        # Indicate Selected
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.setBrush(QtGui.QBrush(QtGui.QColor(0,70,240,128)))
        else:
            painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
        painter.drawRect(QtCore.QRect(x, y, dx, dy))

        # Checkstate
        value = index.data(QtCore.Qt.CheckStateRole)
        if value is not None:
            opt = QtWidgets.QStyleOptionViewItem()
            opt.rect = self.getCheckboxRect(option)
            opt.state = opt.state & ~QtWidgets.QStyle.State_HasFocus
            if value == QtCore.Qt.Unchecked:
                opt.state |= QtWidgets.QStyle.State_Off
            elif value == QtCore.Qt.PartiallyChecked:
                opt.state |= QtWidgets.QStyle.State_NoChange
            elif value == QtCore.Qt.Checked:
                opt.state = QtWidgets.QStyle.State_On
            style = QtWidgets.QApplication.style()
            style.drawPrimitive(
                QtWidgets.QStyle.PE_IndicatorViewItemCheck, opt, painter, None
            )


        painter.restore()
