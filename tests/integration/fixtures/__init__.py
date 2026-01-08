# -*- coding: utf-8 -*-
"""
Integration Test Fixtures - Layer Factories - ARCH-049

Provides factory functions and fixtures for creating
test layers with various configurations.

Part of Phase 5 Integration & Release.

Author: FilterMate Team
Date: January 2026
"""
import pytest
from unittest.mock import MagicMock
from typing import Optional, List, Dict
import uuid


class LayerFactory:
    """
    Factory for creating mock QGIS vector layers.
    
    Provides consistent layer mocks for integration testing
    with configurable properties.
    """
    
    # Default field definitions
    DEFAULT_FIELDS = {
        "id": {"type": "Integer", "length": 10},
        "name": {"type": "String", "length": 100},
        "population": {"type": "Integer", "length": 15},
        "area": {"type": "Double", "precision": 2},
        "category": {"type": "String", "length": 50}
    }
    
    @classmethod
    def create(
        cls,
        layer_id: Optional[str] = None,
        name: str = "Test Layer",
        provider_type: str = "ogr",
        feature_count: int = 1000,
        geometry_type: str = "Polygon",
        crs: str = "EPSG:4326",
        subset_string: str = "",
        fields: Optional[Dict[str, Dict]] = None,
        has_spatial_index: bool = True,
        **kwargs
    ) -> MagicMock:
        """
        Create a mock QgsVectorLayer.
        
        Args:
            layer_id: Unique layer ID
            name: Layer display name
            provider_type: Provider (ogr, postgres, spatialite, memory)
            feature_count: Number of features
            geometry_type: Geometry type (Point, LineString, Polygon)
            crs: Coordinate reference system
            subset_string: Initial filter expression
            fields: Field definitions
            has_spatial_index: Whether layer has spatial index
            
        Returns:
            Mock QgsVectorLayer
        """
        layer = MagicMock()
        
        # Basic properties
        layer.id.return_value = layer_id or f"layer_{uuid.uuid4().hex[:8]}"
        layer.name.return_value = name
        layer.isValid.return_value = True
        layer.providerType.return_value = provider_type
        layer.featureCount.return_value = feature_count
        
        # Geometry type mapping
        wkb_types = {"Point": 1, "LineString": 2, "Polygon": 3}
        layer.wkbType.return_value = wkb_types.get(geometry_type, 3)
        layer.geometryType.return_value = wkb_types.get(geometry_type, 3) - 1
        
        # CRS
        crs_mock = MagicMock()
        crs_mock.authid.return_value = crs
        crs_mock.isValid.return_value = True
        crs_mock.isGeographic.return_value = crs.startswith("EPSG:43")
        layer.crs.return_value = crs_mock
        
        # Subset string handling
        layer._subset_string = subset_string
        layer.subsetString.return_value = subset_string
        
        def set_subset(expr):
            layer._subset_string = expr
            layer.subsetString.return_value = expr
            return True
        layer.setSubsetString.side_effect = set_subset
        
        # Fields
        cls._setup_fields(layer, fields or cls.DEFAULT_FIELDS)
        
        # Provider
        cls._setup_provider(layer, provider_type, has_spatial_index, **kwargs)
        
        # Features iterator mock
        layer.getFeatures.return_value = iter([])
        
        return layer
    
    @classmethod
    def _setup_fields(cls, layer: MagicMock, fields: Dict[str, Dict]):
        """Setup field mocks for the layer."""
        fields_mock = MagicMock()
        fields_mock.names.return_value = list(fields.keys())
        fields_mock.count.return_value = len(fields)
        
        # Mock individual field access
        field_mocks = []
        for fname, fdef in fields.items():
            field = MagicMock()
            field.name.return_value = fname
            field.typeName.return_value = fdef.get("type", "String")
            field.length.return_value = fdef.get("length", 50)
            field_mocks.append(field)
        
        fields_mock.__iter__ = lambda s: iter(field_mocks)
        fields_mock.__getitem__ = lambda s, i: field_mocks[i] if isinstance(i, int) else next(
            (f for f in field_mocks if f.name() == i), None
        )
        
        layer.fields.return_value = fields_mock
    
    @classmethod
    def _setup_provider(
        cls,
        layer: MagicMock,
        provider_type: str,
        has_spatial_index: bool,
        **kwargs
    ):
        """Setup data provider mock for the layer."""
        provider = MagicMock()
        provider.name.return_value = provider_type
        provider.hasSpatialIndex.return_value = has_spatial_index
        
        if provider_type == "postgres":
            cls._setup_postgres_provider(provider, **kwargs)
        elif provider_type == "spatialite":
            cls._setup_spatialite_provider(provider, **kwargs)
        elif provider_type == "ogr":
            cls._setup_ogr_provider(provider, **kwargs)
        
        layer.dataProvider.return_value = provider
    
    @classmethod
    def _setup_postgres_provider(cls, provider: MagicMock, **kwargs):
        """Setup PostgreSQL-specific provider properties."""
        uri = MagicMock()
        uri.database.return_value = kwargs.get("database", "test_db")
        uri.host.return_value = kwargs.get("host", "localhost")
        uri.port.return_value = kwargs.get("port", "5432")
        uri.schema.return_value = kwargs.get("schema", "public")
        uri.table.return_value = kwargs.get("table", "test_table")
        uri.geometryColumn.return_value = kwargs.get("geom_column", "geom")
        uri.keyColumn.return_value = kwargs.get("key_column", "gid")
        uri.username.return_value = kwargs.get("username", "postgres")
        provider.uri.return_value = uri
    
    @classmethod
    def _setup_spatialite_provider(cls, provider: MagicMock, **kwargs):
        """Setup Spatialite-specific provider properties."""
        uri = MagicMock()
        uri.database.return_value = kwargs.get("db_path", "/tmp/test.sqlite")
        uri.table.return_value = kwargs.get("table", "test_table")
        uri.geometryColumn.return_value = kwargs.get("geom_column", "geometry")
        provider.uri.return_value = uri
    
    @classmethod
    def _setup_ogr_provider(cls, provider: MagicMock, **kwargs):
        """Setup OGR-specific provider properties."""
        provider.dataSourceUri.return_value = kwargs.get(
            "source_path", "/tmp/test.shp"
        )


class BackendFactory:
    """
    Factory for creating mock backend instances.
    
    Provides consistent backend mocks for integration testing.
    """
    
    @classmethod
    def create_postgresql(
        cls,
        supports_mv: bool = True,
        execution_time_ms: float = 25.0,
        match_count: int = 100,
        **kwargs
    ) -> MagicMock:
        """Create a mock PostgreSQL backend."""
        backend = MagicMock()
        backend.name = "PostgreSQL"
        backend.get_priority.return_value = 100
        
        # Capabilities
        backend.supports_mv.return_value = supports_mv
        backend.supports_spatial.return_value = True
        backend.supports_connection_pool.return_value = True
        
        # Info
        backend.get_info.return_value = MagicMock(
            name="PostgreSQL",
            priority=100,
            provider_types=["postgres", "postgresql"],
            capabilities=["mv_optimization", "spatial", "connection_pool"]
        )
        
        # Execution result
        cls._setup_execution(backend, match_count, execution_time_ms, True)
        
        return backend
    
    @classmethod
    def create_spatialite(
        cls,
        supports_rtree: bool = True,
        execution_time_ms: float = 50.0,
        match_count: int = 100,
        **kwargs
    ) -> MagicMock:
        """Create a mock Spatialite backend."""
        backend = MagicMock()
        backend.name = "Spatialite"
        backend.get_priority.return_value = 50
        
        # Capabilities
        backend.supports_rtree.return_value = supports_rtree
        backend.supports_spatial.return_value = True
        backend.supports_cache.return_value = True
        
        # Info
        backend.get_info.return_value = MagicMock(
            name="Spatialite",
            priority=50,
            provider_types=["spatialite"],
            capabilities=["rtree", "spatial", "cache"]
        )
        
        # Execution result
        cls._setup_execution(backend, match_count, execution_time_ms, True)
        
        return backend
    
    @classmethod
    def create_ogr(
        cls,
        execution_time_ms: float = 150.0,
        match_count: int = 100,
        **kwargs
    ) -> MagicMock:
        """Create a mock OGR backend."""
        backend = MagicMock()
        backend.name = "OGR"
        backend.get_priority.return_value = 10
        
        # Capabilities
        backend.supports_spatial.return_value = True
        
        # Info
        backend.get_info.return_value = MagicMock(
            name="OGR",
            priority=10,
            provider_types=["ogr", "memory"],
            capabilities=["universal"]
        )
        
        # Execution result
        cls._setup_execution(backend, match_count, execution_time_ms, False)
        
        return backend
    
    @classmethod
    def create_memory(
        cls,
        execution_time_ms: float = 5.0,
        match_count: int = 50,
        **kwargs
    ) -> MagicMock:
        """Create a mock memory backend."""
        backend = MagicMock()
        backend.name = "Memory"
        backend.get_priority.return_value = 5
        
        # Capabilities
        backend.supports_spatial.return_value = True
        
        # Info
        backend.get_info.return_value = MagicMock(
            name="Memory",
            priority=5,
            provider_types=["memory"],
            capabilities=["fast"]
        )
        
        # Execution result
        cls._setup_execution(backend, match_count, execution_time_ms, False)
        
        return backend
    
    @classmethod
    def _setup_execution(
        cls,
        backend: MagicMock,
        match_count: int,
        execution_time_ms: float,
        used_optimization: bool
    ):
        """Setup execution result for backend."""
        result = MagicMock()
        result.success = True
        result.matched_count = match_count
        result.feature_ids = list(range(match_count))
        result.execution_time_ms = execution_time_ms
        result.used_optimization = used_optimization
        result.error_message = None
        backend.execute.return_value = result


# Fixtures

@pytest.fixture
def layer_factory():
    """Provide LayerFactory for tests."""
    return LayerFactory


@pytest.fixture
def backend_factory():
    """Provide BackendFactory for tests."""
    return BackendFactory


@pytest.fixture
def create_test_layer():
    """Factory fixture for creating test layers."""
    def _create(size: int = 1000, provider: str = "ogr", **kwargs):
        return LayerFactory.create(
            feature_count=size,
            provider_type=provider,
            **kwargs
        )
    return _create


@pytest.fixture
def generate_test_layers():
    """Generate multiple test layers."""
    def _generate(count: int = 5, **kwargs) -> List[MagicMock]:
        return [
            LayerFactory.create(
                layer_id=f"layer_{i}",
                name=f"Layer {i}",
                **kwargs
            )
            for i in range(count)
        ]
    return _generate
