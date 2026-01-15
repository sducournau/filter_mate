# -*- coding: utf-8 -*-
"""
QGIS Port - Hexagonal Architecture Abstraction Layer

This module defines abstract interfaces (ports) for QGIS dependencies,
allowing the core domain layer to remain independent of QGIS implementation details.

Following Hexagonal Architecture (Ports & Adapters pattern):
- core/ should NOT import from qgis.* directly
- Instead, core/ imports from this port module
- adapters/ provides concrete implementations

Author: FilterMate Team
Version: 4.1.0 (January 2026 - EPIC-1 Hexagonal Migration)
License: GNU GPL v2+
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum


# ==============================================================================
# VALUE OBJECTS (Domain Types)
# ==============================================================================

class GeometryType(Enum):
    """Geometry type enumeration (domain abstraction)."""
    UNKNOWN = 0
    POINT = 1
    LINE = 2
    POLYGON = 3
    MULTI_POINT = 4
    MULTI_LINE = 5
    MULTI_POLYGON = 6
    GEOMETRY_COLLECTION = 7
    NO_GEOMETRY = 100


class FieldType(Enum):
    """Field data type enumeration (domain abstraction)."""
    INVALID = 0
    INT = 1
    UINT = 2
    LONGLONG = 3
    ULONGLONG = 4
    DOUBLE = 5
    STRING = 10
    DATE = 14
    TIME = 15
    DATETIME = 16
    BOOL = 1  # Usually represented as INT
    BLOB = 12


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box value object."""
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    
    def is_null(self) -> bool:
        """Check if bounding box is null/empty."""
        return self.xmin >= self.xmax or self.ymin >= self.ymax


@dataclass(frozen=True)
class CoordinateReferenceSystem:
    """CRS value object."""
    auth_id: str  # e.g., "EPSG:4326"
    description: str
    is_geographic: bool
    
    @property
    def epsg_code(self) -> Optional[int]:
        """Extract EPSG code if available."""
        if self.auth_id.startswith("EPSG:"):
            try:
                return int(self.auth_id.split(":")[1])
            except (ValueError, IndexError):
                return None
        return None


# ==============================================================================
# GEOMETRY PORT
# ==============================================================================

class IGeometry(ABC):
    """
    Abstract interface for geometry operations.
    
    Isolates core logic from QgsGeometry implementation.
    """
    
    @abstractmethod
    def is_valid(self) -> bool:
        """Check if geometry is valid according to OGC standards."""
        pass
    
    @abstractmethod
    def is_empty(self) -> bool:
        """Check if geometry is empty."""
        pass
    
    @abstractmethod
    def geometry_type(self) -> GeometryType:
        """Get geometry type."""
        pass
    
    @abstractmethod
    def as_wkt(self) -> str:
        """Export as Well-Known Text."""
        pass
    
    @abstractmethod
    def as_wkb(self) -> bytes:
        """Export as Well-Known Binary."""
        pass
    
    @abstractmethod
    def buffer(self, distance: float, segments: int = 5) -> 'IGeometry':
        """Create buffer around geometry."""
        pass
    
    @abstractmethod
    def intersects(self, other: 'IGeometry') -> bool:
        """Check if this geometry intersects another."""
        pass
    
    @abstractmethod
    def contains(self, other: 'IGeometry') -> bool:
        """Check if this geometry contains another."""
        pass
    
    @abstractmethod
    def bounding_box(self) -> BoundingBox:
        """Get bounding box."""
        pass
    
    @abstractmethod
    def transform(self, target_crs: CoordinateReferenceSystem) -> 'IGeometry':
        """Transform geometry to target CRS."""
        pass


# ==============================================================================
# LAYER PORT
# ==============================================================================

class IVectorLayer(ABC):
    """
    Abstract interface for vector layer operations.
    
    Isolates core logic from QgsVectorLayer implementation.
    """
    
    @abstractmethod
    def id(self) -> str:
        """Get unique layer identifier."""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Get layer name."""
        pass
    
    @abstractmethod
    def is_valid(self) -> bool:
        """Check if layer is valid and accessible."""
        pass
    
    @abstractmethod
    def feature_count(self) -> int:
        """Get total number of features."""
        pass
    
    @abstractmethod
    def geometry_type(self) -> GeometryType:
        """Get layer geometry type."""
        pass
    
    @abstractmethod
    def crs(self) -> CoordinateReferenceSystem:
        """Get layer CRS."""
        pass
    
    @abstractmethod
    def extent(self) -> BoundingBox:
        """Get layer extent (bounding box)."""
        pass
    
    @abstractmethod
    def provider_type(self) -> str:
        """Get data provider type (postgres, spatialite, ogr, etc.)."""
        pass
    
    @abstractmethod
    def source(self) -> str:
        """Get data source URI/path."""
        pass
    
    @abstractmethod
    def field_names(self) -> List[str]:
        """Get list of field names."""
        pass
    
    @abstractmethod
    def field_type(self, field_name: str) -> FieldType:
        """Get field data type."""
        pass
    
    @abstractmethod
    def primary_key_field(self) -> Optional[str]:
        """Get primary key field name if exists."""
        pass
    
    @abstractmethod
    def subset_string(self) -> str:
        """Get current subset filter expression."""
        pass
    
    @abstractmethod
    def set_subset_string(self, expression: str) -> bool:
        """
        Set subset filter expression.
        
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """Reload layer data."""
        pass


# ==============================================================================
# EXPRESSION PORT
# ==============================================================================

class IExpression(ABC):
    """
    Abstract interface for expression evaluation.
    
    Isolates core logic from QgsExpression implementation.
    """
    
    @abstractmethod
    def is_valid(self) -> bool:
        """Check if expression is syntactically valid."""
        pass
    
    @abstractmethod
    def parse_error(self) -> Optional[str]:
        """Get parse error message if invalid."""
        pass
    
    @abstractmethod
    def expression_string(self) -> str:
        """Get expression as string."""
        pass
    
    @abstractmethod
    def evaluate(self, feature: Dict[str, Any]) -> Any:
        """
        Evaluate expression for a feature.
        
        Args:
            feature: Feature attribute dict
            
        Returns:
            Evaluation result
        """
        pass
    
    @abstractmethod
    def referenced_columns(self) -> List[str]:
        """Get list of columns referenced in expression."""
        pass
    
    @abstractmethod
    def has_parser_error(self) -> bool:
        """Check if expression has parser error."""
        pass
    
    @abstractmethod
    def is_field(self) -> bool:
        """Check if expression represents a single field reference."""
        pass


# ==============================================================================
# FEATURE PORT
# ==============================================================================

class IFeature(ABC):
    """
    Abstract interface for feature (vector data record).
    
    Isolates core logic from QgsFeature implementation.
    """
    
    @abstractmethod
    def id(self) -> int:
        """Get feature ID."""
        pass
    
    @abstractmethod
    def attributes(self) -> List[Any]:
        """Get all feature attributes as list."""
        pass
    
    @abstractmethod
    def attribute(self, field_name: str) -> Any:
        """Get attribute value by field name."""
        pass
    
    @abstractmethod
    def set_attribute(self, field_name: str, value: Any) -> bool:
        """Set attribute value."""
        pass
    
    @abstractmethod
    def geometry(self) -> Optional[IGeometry]:
        """Get feature geometry."""
        pass
    
    @abstractmethod
    def set_geometry(self, geometry: IGeometry) -> None:
        """Set feature geometry."""
        pass
    
    @abstractmethod
    def fields(self) -> List[str]:
        """Get field names."""
        pass
    
    @abstractmethod
    def is_valid(self) -> bool:
        """Check if feature is valid."""
        pass


class IFeatureRequest(ABC):
    """
    Abstract interface for feature request (filtering/querying).
    
    Isolates core logic from QgsFeatureRequest implementation.
    """
    
    @abstractmethod
    def set_filter_expression(self, expression: str) -> 'IFeatureRequest':
        """Set filter expression."""
        pass
    
    @abstractmethod
    def set_limit(self, limit: int) -> 'IFeatureRequest':
        """Set maximum number of features to return."""
        pass
    
    @abstractmethod
    def set_flags(self, flags: int) -> 'IFeatureRequest':
        """Set request flags (e.g., NoGeometry)."""
        pass
    
    @abstractmethod
    def filter_expression(self) -> str:
        """Get current filter expression."""
        pass


# ==============================================================================
# PROJECT PORT
# ==============================================================================

class IProject(ABC):
    """
    Abstract interface for QGIS project operations.
    
    Isolates core logic from QgsProject implementation.
    """
    
    @abstractmethod
    def map_layers(self) -> Dict[str, IVectorLayer]:
        """Get all map layers indexed by ID."""
        pass
    
    @abstractmethod
    def layer_by_id(self, layer_id: str) -> Optional[IVectorLayer]:
        """Get layer by ID."""
        pass
    
    @abstractmethod
    def layer_by_name(self, name: str) -> Optional[IVectorLayer]:
        """Get layer by name (first match)."""
        pass
    
    @abstractmethod
    def add_map_layer(self, layer: IVectorLayer, add_to_legend: bool = True) -> None:
        """Add layer to project."""
        pass
    
    @abstractmethod
    def remove_map_layer(self, layer_id: str) -> None:
        """Remove layer from project."""
        pass
    
    @abstractmethod
    def crs(self) -> CoordinateReferenceSystem:
        """Get project CRS."""
        pass
    
    @abstractmethod
    def file_name(self) -> str:
        """Get project file path."""
        pass


# ==============================================================================
# TASK PORT
# ==============================================================================

class TaskStatus(Enum):
    """Task execution status."""
    PENDING = 0
    RUNNING = 1
    COMPLETE = 2
    CANCELED = 3
    ERROR = 4


class ITask(ABC):
    """
    Abstract interface for asynchronous task execution.
    
    Isolates core logic from QgsTask implementation.
    """
    
    @abstractmethod
    def description(self) -> str:
        """Get task description."""
        pass
    
    @abstractmethod
    def status(self) -> TaskStatus:
        """Get current task status."""
        pass
    
    @abstractmethod
    def progress(self) -> float:
        """Get task progress (0.0 to 100.0)."""
        pass
    
    @abstractmethod
    def is_canceled(self) -> bool:
        """Check if task has been canceled."""
        pass
    
    @abstractmethod
    def cancel(self) -> None:
        """Cancel task execution."""
        pass
    
    @abstractmethod
    def run(self) -> bool:
        """
        Execute task logic.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def finished(self, result: bool) -> None:
        """
        Called when task finishes.
        
        Args:
            result: Task execution result (True = success)
        """
        pass


# ==============================================================================
# FEEDBACK PORT (User Interaction)
# ==============================================================================

class MessageLevel(Enum):
    """Message severity level."""
    INFO = 0
    WARNING = 1
    CRITICAL = 2
    SUCCESS = 3


class IFeedback(ABC):
    """
    Abstract interface for user feedback (messages, progress).
    
    Isolates core logic from iface.messageBar() and QgsFeedback.
    """
    
    @abstractmethod
    def push_message(
        self,
        title: str,
        message: str,
        level: MessageLevel = MessageLevel.INFO
    ) -> None:
        """
        Display message to user.
        
        Args:
            title: Message title
            message: Message content
            level: Severity level
        """
        pass
    
    @abstractmethod
    def set_progress(self, value: float) -> None:
        """
        Set progress value.
        
        Args:
            value: Progress percentage (0.0 to 100.0)
        """
        pass
    
    @abstractmethod
    def is_canceled(self) -> bool:
        """Check if operation has been canceled by user."""
        pass
    
    @abstractmethod
    def set_progress_text(self, text: str) -> None:
        """Set progress text description."""
        pass


# ==============================================================================
# REPOSITORY PORT (Data Access)
# ==============================================================================

class ILayerRepository(ABC):
    """
    Abstract interface for layer data access.
    
    Provides CRUD operations for layers following Repository pattern.
    """
    
    @abstractmethod
    def get_all_vector_layers(self) -> List[IVectorLayer]:
        """Get all vector layers in project."""
        pass
    
    @abstractmethod
    def get_layer_by_id(self, layer_id: str) -> Optional[IVectorLayer]:
        """Get layer by ID."""
        pass
    
    @abstractmethod
    def get_layer_by_name(self, name: str) -> Optional[IVectorLayer]:
        """Get layer by name."""
        pass
    
    @abstractmethod
    def get_selected_layer(self) -> Optional[IVectorLayer]:
        """Get currently selected layer in QGIS."""
        pass
    
    @abstractmethod
    def layer_exists(self, layer_id: str) -> bool:
        """Check if layer exists."""
        pass
    
    @abstractmethod
    def is_layer_spatial(self, layer: IVectorLayer) -> bool:
        """Check if layer has geometry."""
        pass


# ==============================================================================
# FACTORY PORT (Object Creation)
# ==============================================================================

class IQGISFactory(ABC):
    """
    Abstract factory for creating QGIS objects.
    
    Allows core to request object creation without direct QGIS imports.
    """
    
    @abstractmethod
    def create_geometry_from_wkt(self, wkt: str) -> IGeometry:
        """Create geometry from WKT string."""
        pass
    
    @abstractmethod
    def create_expression(self, expression_str: str) -> IExpression:
        """Create expression from string."""
        pass
    
    @abstractmethod
    def create_feature(self) -> IFeature:
        """Create new empty feature."""
        pass
    
    @abstractmethod
    def create_feature_request(self) -> IFeatureRequest:
        """Create new feature request."""
        pass
    
    @abstractmethod
    def create_vector_layer(
        self,
        source: str,
        name: str,
        provider: str
    ) -> IVectorLayer:
        """
        Create vector layer.
        
        Args:
            source: Data source URI
            name: Layer name
            provider: Provider type (postgres, spatialite, ogr, memory)
        """
        pass
    
    @abstractmethod
    def create_crs(self, auth_id: str) -> CoordinateReferenceSystem:
        """Create CRS from authority ID (e.g., 'EPSG:4326')."""
        pass


# ==============================================================================
# ADAPTER RETRIEVAL (Dependency Injection)
# ==============================================================================

# Global adapter instances (set by adapters module at runtime)
_qgis_factory: Optional[IQGISFactory] = None
_layer_repository: Optional[ILayerRepository] = None
_project_adapter: Optional[IProject] = None
_feedback_adapter: Optional[IFeedback] = None


def set_qgis_factory(factory: IQGISFactory) -> None:
    """
    Set QGIS factory adapter (called by adapters module).
    
    Args:
        factory: Concrete implementation of IQGISFactory
    """
    global _qgis_factory
    _qgis_factory = factory


def set_layer_repository(repository: ILayerRepository) -> None:
    """Set layer repository adapter."""
    global _layer_repository
    _layer_repository = repository


def set_project_adapter(project: IProject) -> None:
    """Set project adapter."""
    global _project_adapter
    _project_adapter = project


def set_feedback_adapter(feedback: IFeedback) -> None:
    """Set feedback adapter."""
    global _feedback_adapter
    _feedback_adapter = feedback


def get_qgis_factory() -> IQGISFactory:
    """
    Get QGIS factory instance.
    
    Raises:
        RuntimeError: If factory not initialized
    """
    if _qgis_factory is None:
        raise RuntimeError(
            "QGIS factory not initialized. "
            "Call set_qgis_factory() from adapters module first."
        )
    return _qgis_factory


def get_layer_repository() -> ILayerRepository:
    """Get layer repository instance."""
    if _layer_repository is None:
        raise RuntimeError("Layer repository not initialized.")
    return _layer_repository


def get_project_adapter() -> IProject:
    """Get project adapter instance."""
    if _project_adapter is None:
        raise RuntimeError("Project adapter not initialized.")
    return _project_adapter


def get_feedback_adapter() -> IFeedback:
    """Get feedback adapter instance."""
    if _feedback_adapter is None:
        raise RuntimeError("Feedback adapter not initialized.")
    return _feedback_adapter


# ==============================================================================
# USAGE EXAMPLE (Documentation)
# ==============================================================================

"""
Example Usage in Core Domain:

    from core.ports.qgis_port import (
        get_layer_repository,
        get_qgis_factory,
        get_feedback_adapter,
        MessageLevel
    )
    
    # Instead of:
    # from qgis.core import QgsVectorLayer, QgsProject
    # layer = QgsProject.instance().mapLayersByName("my_layer")[0]
    
    # Use ports:
    repository = get_layer_repository()
    layer = repository.get_layer_by_name("my_layer")
    
    if layer and layer.is_valid():
        # Work with abstract interface
        count = layer.feature_count()
        geom_type = layer.geometry_type()
        
        # Provide feedback
        feedback = get_feedback_adapter()
        feedback.push_message(
            "FilterMate",
            f"Processing {count} features",
            MessageLevel.INFO
        )

Adapter Implementation (in adapters/qgis/):

    from core.ports.qgis_port import IVectorLayer, GeometryType
    from qgis.core import QgsVectorLayer, QgsWkbTypes
    
    class QGISVectorLayerAdapter(IVectorLayer):
        def __init__(self, qgs_layer: QgsVectorLayer):
            self._layer = qgs_layer
        
        def name(self) -> str:
            return self._layer.name()
        
        def geometry_type(self) -> GeometryType:
            wkb_type = self._layer.wkbType()
            # Map QgsWkbTypes to GeometryType enum
            ...
"""
