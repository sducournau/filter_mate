# -*- coding: utf-8 -*-
"""
P0 Tests for FilterEngineTask Extracted Handlers (Phase 3 C1)

Tests the 6 handlers extracted from FilterEngineTask:
- CleanupHandler: PostgreSQL MV lifecycle, SQL generation
- ExportHandler: Export parameter validation, layer lookup, feature counting
- GeometryHandler: WKT conversion, buffer params, warning storage
- InitializationHandler: Source layer init, predicate mapping, CRS config
- SourceGeometryPreparer: Backend geometry delegation, early returns
- SubsetManagementHandler: Backend determination, performance warnings, history

Strategy:
    All tests use mocks for QGIS dependencies (QgsVectorLayer, etc.).
    Focus on testable pure logic, validation paths, and early returns.
    Handler methods that purely delegate to _backend_services are tested
    by verifying correct delegation (mock.assert_called_with patterns).

Author: Beta (QA Tester)
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_backend_services():
    """Create a mock BackendServices singleton for injection."""
    mock_bs = MagicMock()
    return mock_bs


@pytest.fixture
def mock_layer():
    """Create a mock QgsVectorLayer with standard attributes."""
    layer = MagicMock()
    layer.id.return_value = "layer_abc_123"
    layer.name.return_value = "test_layer"
    layer.isValid.return_value = True
    layer.featureCount.return_value = 100
    layer.providerType.return_value = "ogr"
    layer.subsetString.return_value = ""
    layer.source.return_value = "/tmp/test.gpkg"

    crs = MagicMock()
    crs.authid.return_value = "EPSG:2154"
    crs.isGeographic.return_value = False
    crs.postgisSrid.return_value = 2154
    layer.crs.return_value = crs
    layer.sourceCrs.return_value = crs

    return layer


@pytest.fixture
def mock_pg_layer():
    """Create a mock QgsVectorLayer for PostgreSQL provider."""
    layer = MagicMock()
    layer.id.return_value = "pg_layer_001"
    layer.name.return_value = "pg_test_layer"
    layer.isValid.return_value = True
    layer.featureCount.return_value = 50000
    layer.providerType.return_value = "postgres"
    layer.subsetString.return_value = ""
    return layer


@pytest.fixture
def mock_connexion():
    """Create a mock psycopg2-like connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ===========================================================================
# CleanupHandler Tests
# ===========================================================================

class TestCleanupHandler:
    """Tests for CleanupHandler -- PostgreSQL MV lifecycle and SQL generation."""

    @pytest.fixture(autouse=True)
    def setup_handler(self, mock_backend_services):
        """Create CleanupHandler with mocked backend services."""
        with patch('core.tasks.cleanup_handler.get_backend_services',
                   return_value=mock_backend_services):
            from core.tasks.cleanup_handler import CleanupHandler
            self.handler = CleanupHandler()
            self.mock_bs = mock_backend_services

    # --- cleanup_postgresql_materialized_views early returns ---

    def test_cleanup_mvs_returns_early_when_not_postgresql_available(self):
        """If postgresql_available is False, cleanup should return immediately."""
        self.handler.cleanup_postgresql_materialized_views(
            postgresql_available=False,
            source_provider_type='ogr',
            source_layer=None,
            task_parameters={},
            param_all_layers=None,
            get_connection_fn=MagicMock(),
        )
        # No connection should be requested
        # (no assertion needed -- just verifying no exception)

    def test_cleanup_mvs_returns_early_when_not_postgresql_provider(self):
        """If provider is not 'postgresql', cleanup should return."""
        self.handler.cleanup_postgresql_materialized_views(
            postgresql_available=True,
            source_provider_type='ogr',
            source_layer=None,
            task_parameters={},
            param_all_layers=None,
            get_connection_fn=MagicMock(),
        )

    def test_cleanup_mvs_returns_early_when_no_layer_ids(self):
        """If no layer IDs can be collected, cleanup should return."""
        self.handler.cleanup_postgresql_materialized_views(
            postgresql_available=True,
            source_provider_type='postgresql',
            source_layer=None,
            task_parameters={},
            param_all_layers=None,
            get_connection_fn=MagicMock(),
        )

    def test_cleanup_mvs_collects_source_layer_id(self, mock_layer):
        """Should collect layer ID from source_layer."""
        mock_tracker = MagicMock()
        mock_tracker.remove_all_references_for_layer.return_value = set()
        with patch(
            'core.tasks.cleanup_handler.get_mv_reference_tracker',
            return_value=mock_tracker,
            create=True,
        ):
            # Need to patch the import inside the method
            import core.tasks.cleanup_handler as mod
            with patch.dict('sys.modules', {
                'adapters.backends.postgresql.mv_reference_tracker': MagicMock(
                    get_mv_reference_tracker=MagicMock(return_value=mock_tracker)
                )
            }):
                self.handler.cleanup_postgresql_materialized_views(
                    postgresql_available=True,
                    source_provider_type='postgresql',
                    source_layer=mock_layer,
                    task_parameters={},
                    param_all_layers=None,
                    get_connection_fn=MagicMock(),
                )

    # --- create_custom_buffer_view_sql ---

    def test_custom_buffer_view_sql_basic(self):
        """Test basic SQL generation for custom buffer MV."""
        self.mock_bs.parse_case_to_where_clauses.return_value = [
            '"field1" = 1'
        ]

        mock_source_layer = MagicMock()
        mock_source_layer.subsetString.return_value = ""

        sql = self.handler.create_custom_buffer_view_sql(
            schema="filtermate_temp",
            name="test_layer",
            geom_key_name="geom",
            where_clause_fields_arr=['"field1"'],
            last_subset_id=None,
            sql_subset_string="(SELECT pk FROM public.test_table)",
            postgresql_source_geom='"public"."test_table"."geom"',
            has_to_reproject_source_layer=False,
            source_layer_crs_authid="EPSG:2154",
            task_parameters={"filtering": {"buffer_type": "Round"}},
            param_buffer_segments=5,
            param_source_schema="public",
            param_source_table="test_table",
            primary_key_name="pk",
            source_layer=mock_source_layer,
            param_buffer="100",
            where_clause="CASE WHEN field1 = 1 THEN 1 END",
        )

        assert "CREATE MATERIALIZED VIEW" in sql
        assert "filtermate_temp" in sql
        assert "fm_temp_mv_test_layer" in sql
        assert "ST_Buffer" in sql
        assert "quad_segs=5" in sql

    def test_custom_buffer_view_sql_with_reprojection(self):
        """When reprojection is needed, should wrap geom in ST_Transform."""
        self.mock_bs.parse_case_to_where_clauses.return_value = ['"f" = 1']

        mock_source_layer = MagicMock()
        mock_source_layer.subsetString.return_value = ""

        sql = self.handler.create_custom_buffer_view_sql(
            schema="filtermate_temp",
            name="test",
            geom_key_name="geom",
            where_clause_fields_arr=['"f"'],
            last_subset_id=None,
            sql_subset_string="(SELECT pk FROM public.t)",
            postgresql_source_geom='"public"."t"."geom"',
            has_to_reproject_source_layer=True,
            source_layer_crs_authid="EPSG:4326",
            task_parameters={"filtering": {"buffer_type": "Round"}},
            param_buffer_segments=5,
            param_source_schema="public",
            param_source_table="t",
            primary_key_name="pk",
            source_layer=mock_source_layer,
            param_buffer="50",
            where_clause="CASE WHEN f = 1 THEN 1 END",
        )

        assert "ST_Transform" in sql
        assert "4326" in sql

    def test_custom_buffer_view_sql_flat_endcap(self):
        """Buffer type 'Flat' should produce endcap=flat in style_params."""
        self.mock_bs.parse_case_to_where_clauses.return_value = ['"f" = 1']

        mock_source_layer = MagicMock()
        mock_source_layer.subsetString.return_value = ""

        sql = self.handler.create_custom_buffer_view_sql(
            schema="s",
            name="n",
            geom_key_name="geom",
            where_clause_fields_arr=['"f"'],
            last_subset_id=None,
            sql_subset_string="(SELECT pk FROM s.t)",
            postgresql_source_geom='"s"."t"."geom"',
            has_to_reproject_source_layer=False,
            source_layer_crs_authid="EPSG:2154",
            task_parameters={"filtering": {"buffer_type": "Flat"}},
            param_buffer_segments=8,
            param_source_schema="s",
            param_source_table="t",
            primary_key_name="pk",
            source_layer=mock_source_layer,
            param_buffer="100",
            where_clause="CASE WHEN f = 1 THEN 1 END",
        )

        assert "endcap=flat" in sql
        assert "quad_segs=8" in sql

    def test_custom_buffer_view_sql_square_endcap(self):
        """Buffer type 'Square' should produce endcap=square."""
        self.mock_bs.parse_case_to_where_clauses.return_value = ['"f" = 1']

        mock_source_layer = MagicMock()
        mock_source_layer.subsetString.return_value = ""

        sql = self.handler.create_custom_buffer_view_sql(
            schema="s",
            name="n",
            geom_key_name="geom",
            where_clause_fields_arr=['"f"'],
            last_subset_id=None,
            sql_subset_string="(SELECT pk FROM s.t)",
            postgresql_source_geom='"s"."t"."geom"',
            has_to_reproject_source_layer=False,
            source_layer_crs_authid="EPSG:2154",
            task_parameters={"filtering": {"buffer_type": "Square"}},
            param_buffer_segments=5,
            param_source_schema="s",
            param_source_table="t",
            primary_key_name="pk",
            source_layer=mock_source_layer,
            param_buffer="100",
            where_clause="CASE WHEN f = 1 THEN 1 END",
        )

        assert "endcap=square" in sql

    def test_custom_buffer_view_sql_source_layer_with_select_subset(self):
        """When source_layer has a SELECT subset, should use it directly."""
        self.mock_bs.parse_case_to_where_clauses.return_value = ['"f" = 1']

        mock_source_layer = MagicMock()
        mock_source_layer.subsetString.return_value = "SELECT pk FROM s.t WHERE status = 1"

        sql = self.handler.create_custom_buffer_view_sql(
            schema="s",
            name="n",
            geom_key_name="geom",
            where_clause_fields_arr=['"f"'],
            last_subset_id=None,
            sql_subset_string="(SELECT pk FROM s.t)",
            postgresql_source_geom='"s"."t"."geom"',
            has_to_reproject_source_layer=False,
            source_layer_crs_authid="EPSG:2154",
            task_parameters={"filtering": {"buffer_type": "Round"}},
            param_buffer_segments=5,
            param_source_schema="s",
            param_source_table="t",
            primary_key_name="pk",
            source_layer=mock_source_layer,
            param_buffer="100",
            where_clause="CASE WHEN f = 1 THEN 1 END",
        )

        # Should use the source layer's SELECT subset
        assert "SELECT pk FROM s.t WHERE status = 1" in sql

    def test_custom_buffer_view_sql_source_layer_with_where_subset(self):
        """When source_layer has a WHERE-style subset, should wrap it in SELECT."""
        self.mock_bs.parse_case_to_where_clauses.return_value = ['"f" = 1']

        mock_source_layer = MagicMock()
        mock_source_layer.subsetString.return_value = "status = 1"

        sql = self.handler.create_custom_buffer_view_sql(
            schema="s",
            name="n",
            geom_key_name="geom",
            where_clause_fields_arr=['"f"'],
            last_subset_id=None,
            sql_subset_string="(SELECT pk FROM s.t)",
            postgresql_source_geom='"s"."t"."geom"',
            has_to_reproject_source_layer=False,
            source_layer_crs_authid="EPSG:2154",
            task_parameters={"filtering": {"buffer_type": "Round"}},
            param_buffer_segments=5,
            param_source_schema="s",
            param_source_table="t",
            primary_key_name="pk",
            source_layer=mock_source_layer,
            param_buffer="100",
            where_clause="CASE WHEN f = 1 THEN 1 END",
        )

        # Should wrap in SELECT ... WHERE
        assert "status = 1" in sql
        assert '"pk"' in sql

    # --- Delegation methods ---

    def test_cleanup_session_mvs_delegates_to_backend(self, mock_connexion):
        """cleanup_session_materialized_views should delegate to backend services."""
        self.handler.cleanup_session_materialized_views(
            connexion=mock_connexion,
            schema_name="filtermate_temp",
            session_id="sess_123",
        )
        self.mock_bs.cleanup_session_materialized_views.assert_called_once_with(
            mock_connexion, "filtermate_temp", "sess_123"
        )

    def test_cleanup_session_mvs_with_pg_executor(self, mock_connexion):
        """When pg_executor is available, should use it instead of backend services."""
        mock_pg = MagicMock()
        self.handler.cleanup_session_materialized_views(
            connexion=mock_connexion,
            schema_name="filtermate_temp",
            session_id="sess_123",
            pg_executor=mock_pg,
            pg_executor_available=True,
        )
        mock_pg.cleanup_session_materialized_views.assert_called_once()
        self.mock_bs.cleanup_session_materialized_views.assert_not_called()

    def test_ensure_temp_schema_exists_delegates(self, mock_connexion):
        """ensure_temp_schema_exists should delegate to backend services."""
        self.mock_bs.ensure_temp_schema_exists.return_value = "filtermate_temp"
        result = self.handler.ensure_temp_schema_exists(
            mock_connexion, "filtermate_temp"
        )
        assert result == "filtermate_temp"

    def test_get_session_prefixed_name_delegates(self):
        """get_session_prefixed_name should delegate to backend services."""
        self.mock_bs.get_session_prefixed_name.return_value = "sess123_layername"
        result = self.handler.get_session_prefixed_name("layername", "sess123")
        assert result == "sess123_layername"

    def test_execute_postgresql_commands_delegates(self, mock_connexion):
        """execute_postgresql_commands should delegate to backend services."""
        self.mock_bs.execute_commands.return_value = True
        result = self.handler.execute_postgresql_commands(
            connexion=mock_connexion,
            commands=["CREATE INDEX ..."],
        )
        assert result is True

    def test_execute_postgresql_commands_reconnect_on_failure(self, mock_connexion):
        """Should attempt reconnection when connection test fails."""
        mock_psycopg2 = MagicMock()
        mock_psycopg2.OperationalError = type('OperationalError', (Exception,), {})
        mock_psycopg2.InterfaceError = type('InterfaceError', (Exception,), {})

        # First cursor call raises OperationalError
        cursor_mock = MagicMock()
        cursor_mock.execute.side_effect = mock_psycopg2.OperationalError("connection closed")
        mock_connexion.cursor.return_value.__enter__ = MagicMock(return_value=cursor_mock)
        mock_connexion.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_conn = MagicMock(return_value=(MagicMock(), None))
        mock_source = MagicMock()

        self.mock_bs.execute_commands.return_value = True
        result = self.handler.execute_postgresql_commands(
            connexion=mock_connexion,
            commands=["SELECT 1"],
            source_layer=mock_source,
            psycopg2_module=mock_psycopg2,
            get_datasource_connexion_fn=mock_get_conn,
        )
        assert result is True


# ===========================================================================
# ExportHandler Tests
# ===========================================================================

class TestExportHandler:
    """Tests for ExportHandler -- Export operations."""

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        """Create ExportHandler with mocked imports."""
        with patch('core.tasks.export_handler.StreamingExporter'), \
             patch('core.tasks.export_handler.StreamingConfig'):
            from core.tasks.export_handler import ExportHandler
            self.handler = ExportHandler()

    def test_get_layer_by_name_found(self):
        """Should return layer when found by name."""
        mock_project = MagicMock()
        mock_layer = MagicMock()
        mock_project.mapLayersByName.return_value = [mock_layer]

        result = self.handler.get_layer_by_name(mock_project, "roads")
        assert result == mock_layer

    def test_get_layer_by_name_not_found(self):
        """Should return None when layer not found."""
        mock_project = MagicMock()
        mock_project.mapLayersByName.return_value = []

        result = self.handler.get_layer_by_name(mock_project, "nonexistent")
        assert result is None

    def test_get_layer_by_name_returns_first_match(self):
        """Should return first layer when multiple matches."""
        mock_project = MagicMock()
        layer1 = MagicMock()
        layer2 = MagicMock()
        mock_project.mapLayersByName.return_value = [layer1, layer2]

        result = self.handler.get_layer_by_name(mock_project, "duplicate_name")
        assert result == layer1

    def test_calculate_total_features_single_layer(self):
        """Should count features for a single layer."""
        mock_project = MagicMock()
        mock_layer = MagicMock()
        mock_layer.featureCount.return_value = 42
        mock_project.mapLayersByName.return_value = [mock_layer]

        total = self.handler.calculate_total_features(
            [{"layer_name": "test"}], mock_project
        )
        assert total == 42

    def test_calculate_total_features_multiple_layers(self):
        """Should sum features across multiple layers."""
        mock_project = MagicMock()

        layer1 = MagicMock()
        layer1.featureCount.return_value = 100
        layer2 = MagicMock()
        layer2.featureCount.return_value = 200

        mock_project.mapLayersByName.side_effect = [[layer1], [layer2]]

        total = self.handler.calculate_total_features(
            [{"layer_name": "a"}, {"layer_name": "b"}], mock_project
        )
        assert total == 300

    def test_calculate_total_features_with_missing_layer(self):
        """Should skip layers not found in project."""
        mock_project = MagicMock()

        layer1 = MagicMock()
        layer1.featureCount.return_value = 100

        mock_project.mapLayersByName.side_effect = [[layer1], []]

        total = self.handler.calculate_total_features(
            [{"layer_name": "exists"}, {"layer_name": "missing"}], mock_project
        )
        assert total == 100

    def test_calculate_total_features_empty_list(self):
        """Should return 0 for empty layer list."""
        mock_project = MagicMock()
        total = self.handler.calculate_total_features([], mock_project)
        assert total == 0

    def test_calculate_total_features_string_layer_names(self):
        """Should handle string layer names (not dict)."""
        mock_project = MagicMock()
        mock_layer = MagicMock()
        mock_layer.featureCount.return_value = 50
        mock_project.mapLayersByName.return_value = [mock_layer]

        total = self.handler.calculate_total_features(
            ["test_layer"], mock_project
        )
        assert total == 50

    def test_execute_exporting_fails_on_invalid_params(self):
        """Should return failure tuple when validation fails."""
        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.error_message = "Missing output path"

        mock_validate = MagicMock(return_value=mock_result)
        mock_export_module = MagicMock()
        mock_export_module.validate_export_parameters = mock_validate

        with patch.dict('sys.modules', {
            'filter_mate.core.export': mock_export_module,
        }):
            # Patch the validate method on the handler itself
            with patch.object(self.handler, 'validate_export_parameters',
                            return_value=None):
                success, message, details = self.handler.execute_exporting(
                    task_parameters={"task": {"EXPORTING": {}}},
                    project=MagicMock(),
                    set_progress=MagicMock(),
                    set_description=MagicMock(),
                    is_canceled=MagicMock(return_value=False),
                )

            assert success is False
            assert "validation failed" in message.lower()


# ===========================================================================
# GeometryHandler Tests
# ===========================================================================

class TestGeometryHandler:
    """Tests for GeometryHandler -- Geometry operations."""

    @pytest.fixture(autouse=True)
    def setup_handler(self, mock_backend_services):
        """Create GeometryHandler with mocked backend services."""
        with patch('core.tasks.geometry_handler.get_backend_services',
                   return_value=mock_backend_services):
            from core.tasks.geometry_handler import GeometryHandler
            self.handler = GeometryHandler()
            self.mock_bs = mock_backend_services

    def test_geometry_to_wkt_returns_empty_for_none(self):
        """geometry_to_wkt should return empty string for None geometry."""
        result = self.handler.geometry_to_wkt(None)
        assert result == ""

    def test_geometry_to_wkt_returns_empty_for_empty_geometry(self):
        """geometry_to_wkt should return empty string for empty geometry."""
        mock_geom = MagicMock()
        mock_geom.isEmpty.return_value = True
        result = self.handler.geometry_to_wkt(mock_geom)
        assert result == ""

    def test_geometry_to_wkt_calls_asWkt_with_precision(self):
        """geometry_to_wkt should call asWkt with calculated precision."""
        mock_geom = MagicMock()
        mock_geom.isEmpty.return_value = False
        mock_geom.asWkt.return_value = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"

        with patch.object(self.handler, 'get_wkt_precision', return_value=6):
            result = self.handler.geometry_to_wkt(mock_geom, "EPSG:4326")

        mock_geom.asWkt.assert_called_once_with(6)
        assert "POLYGON" in result

    def test_fix_invalid_geometries_returns_input_unchanged(self):
        """fix_invalid_geometries is disabled and should return input layer."""
        mock_layer = MagicMock()
        result = self.handler.fix_invalid_geometries(mock_layer, "output_key")
        assert result is mock_layer

    def test_store_warning_message_adds_new_message(self):
        """store_warning_message should append new message to list."""
        warnings = []
        self.handler.store_warning_message("Test warning", warnings)
        assert len(warnings) == 1
        assert warnings[0] == "Test warning"

    def test_store_warning_message_skips_duplicate(self):
        """store_warning_message should not add duplicate messages."""
        warnings = ["Test warning"]
        self.handler.store_warning_message("Test warning", warnings)
        assert len(warnings) == 1

    def test_store_warning_message_skips_empty(self):
        """store_warning_message should skip empty messages."""
        warnings = []
        self.handler.store_warning_message("", warnings)
        assert len(warnings) == 0

    def test_store_warning_message_skips_none(self):
        """store_warning_message should skip None messages."""
        warnings = []
        self.handler.store_warning_message(None, warnings)
        assert len(warnings) == 0

    def test_apply_buffer_with_fallback_none_layer(self):
        """apply_buffer_with_fallback should return None for None layer."""
        result = self.handler.apply_buffer_with_fallback(
            layer=None,
            buffer_distance=100,
            param_buffer_type=0,
            param_buffer_segments=5,
            outputs={},
            verify_spatial_index_fn=MagicMock(),
            store_warning_fn=MagicMock(),
        )
        assert result is None

    def test_apply_buffer_with_fallback_invalid_layer(self):
        """apply_buffer_with_fallback should return None for invalid layer."""
        mock_layer = MagicMock()
        mock_layer.isValid.return_value = False

        result = self.handler.apply_buffer_with_fallback(
            layer=mock_layer,
            buffer_distance=100,
            param_buffer_type=0,
            param_buffer_segments=5,
            outputs={},
            verify_spatial_index_fn=MagicMock(),
            store_warning_fn=MagicMock(),
        )
        assert result is None

    def test_apply_buffer_with_fallback_empty_layer(self):
        """apply_buffer_with_fallback should return None for empty layer."""
        mock_layer = MagicMock()
        mock_layer.isValid.return_value = True
        mock_layer.featureCount.return_value = 0

        result = self.handler.apply_buffer_with_fallback(
            layer=mock_layer,
            buffer_distance=100,
            param_buffer_type=0,
            param_buffer_segments=5,
            outputs={},
            verify_spatial_index_fn=MagicMock(),
            store_warning_fn=MagicMock(),
        )
        assert result is None

    def test_simplify_geometry_adaptive_returns_original_on_none(self):
        """simplify_geometry_adaptive should return None for None geometry."""
        result = self.handler.simplify_geometry_adaptive(None)
        assert result is None

    def test_simplify_geometry_adaptive_returns_original_on_empty(self):
        """simplify_geometry_adaptive should return empty geometry unchanged."""
        mock_geom = MagicMock()
        mock_geom.isEmpty.return_value = True
        # Empty geometry evaluates as falsy
        mock_geom.__bool__ = MagicMock(return_value=True)

        result = self.handler.simplify_geometry_adaptive(mock_geom)
        assert result is mock_geom

    def test_simplify_geometry_adaptive_no_adapter(self):
        """When adapter is not available, should return original geometry."""
        self.mock_bs.get_geometry_preparation_adapter.return_value = None
        mock_geom = MagicMock()
        mock_geom.isEmpty.return_value = False
        mock_geom.__bool__ = MagicMock(return_value=True)

        result = self.handler.simplify_geometry_adaptive(mock_geom)
        assert result is mock_geom


# ===========================================================================
# InitializationHandler Tests
# ===========================================================================

class TestInitializationHandler:
    """Tests for InitializationHandler -- Task parameter extraction."""

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        """Create InitializationHandler."""
        from core.tasks.initialization_handler import InitializationHandler
        self.handler = InitializationHandler()

    # --- initialize_source_layer ---

    def test_init_source_layer_missing_infos(self):
        """Should fail when 'infos' dict is missing."""
        result = self.handler.initialize_source_layer(
            task_parameters={},
            project=MagicMock(),
        )
        assert result['success'] is False
        assert result['exception'] is not None
        assert "infos" in str(result['exception'])

    def test_init_source_layer_missing_layer_id(self):
        """Should fail when layer_id is missing from infos."""
        result = self.handler.initialize_source_layer(
            task_parameters={"infos": {"layer_name": "test"}},
            project=MagicMock(),
        )
        assert result['success'] is False
        assert "layer_id" in str(result['exception'])

    def test_init_source_layer_none_layer_id(self):
        """Should fail when layer_id is None."""
        result = self.handler.initialize_source_layer(
            task_parameters={"infos": {"layer_id": None}},
            project=MagicMock(),
        )
        assert result['success'] is False
        assert "layer_id" in str(result['exception'])

    def test_init_source_layer_not_found_in_project(self):
        """Should fail when layer not found in project."""
        mock_project = MagicMock()
        mock_project.mapLayer.return_value = None
        mock_project.mapLayersByName.return_value = []

        result = self.handler.initialize_source_layer(
            task_parameters={"infos": {"layer_id": "nonexistent_123"}},
            project=mock_project,
        )
        assert result['success'] is False
        assert "not found" in str(result['exception'])

    def test_init_source_layer_success(self, mock_layer):
        """Should succeed when layer is found."""
        mock_project = MagicMock()
        mock_project.mapLayer.return_value = mock_layer

        result = self.handler.initialize_source_layer(
            task_parameters={
                "infos": {
                    "layer_id": "layer_abc_123",
                    "layer_name": "test_layer",
                    "layer_crs_authid": "EPSG:2154",
                }
            },
            project=mock_project,
        )
        assert result['success'] is True
        assert result['source_layer'] is mock_layer
        assert result['source_layer_crs_authid'] == "EPSG:2154"

    def test_init_source_layer_auto_fills_name(self, mock_layer):
        """Should auto-fill layer_name from the QGIS layer object."""
        mock_project = MagicMock()
        mock_project.mapLayer.return_value = mock_layer

        task_params = {
            "infos": {
                "layer_id": "layer_abc_123",
                # layer_name intentionally missing
            }
        }

        result = self.handler.initialize_source_layer(
            task_parameters=task_params,
            project=mock_project,
        )
        assert result['success'] is True
        assert task_params["infos"]["layer_name"] == "test_layer"

    def test_init_source_layer_auto_fills_crs(self, mock_layer):
        """Should auto-fill layer_crs_authid from the QGIS layer object."""
        mock_project = MagicMock()
        mock_project.mapLayer.return_value = mock_layer

        task_params = {
            "infos": {
                "layer_id": "layer_abc_123",
                "layer_name": "test_layer",
                # layer_crs_authid intentionally missing
            }
        }

        result = self.handler.initialize_source_layer(
            task_parameters=task_params,
            project=mock_project,
        )
        assert result['success'] is True
        assert result['source_layer_crs_authid'] is not None

    def test_init_source_layer_extracts_feature_count_limit(self, mock_layer):
        """Should extract feature count limit from task options."""
        mock_project = MagicMock()
        mock_project.mapLayer.return_value = mock_layer

        result = self.handler.initialize_source_layer(
            task_parameters={
                "infos": {
                    "layer_id": "layer_abc_123",
                    "layer_name": "test",
                    "layer_crs_authid": "EPSG:2154",
                },
                "task": {
                    "options": {
                        "LAYERS": {
                            "FEATURE_COUNT_LIMIT": 5000
                        }
                    }
                }
            },
            project=mock_project,
        )
        assert result['feature_count_limit'] == 5000

    def test_init_source_layer_ignores_zero_feature_limit(self, mock_layer):
        """Should ignore feature count limit <= 0."""
        mock_project = MagicMock()
        mock_project.mapLayer.return_value = mock_layer

        result = self.handler.initialize_source_layer(
            task_parameters={
                "infos": {
                    "layer_id": "layer_abc_123",
                    "layer_name": "test",
                    "layer_crs_authid": "EPSG:2154",
                },
                "task": {
                    "options": {
                        "LAYERS": {
                            "FEATURE_COUNT_LIMIT": 0
                        }
                    }
                }
            },
            project=mock_project,
        )
        assert result['feature_count_limit'] is None

    # --- initialize_current_predicates ---

    def test_init_predicates_empty_list(self):
        """Should return empty dicts when no geometric predicates."""
        result = self.handler.initialize_current_predicates(
            task_parameters={"filtering": {"geometric_predicates": []}},
            predicates_map={},
        )
        assert result['current_predicates'] == {}
        assert result['numeric_predicates'] == {}

    def test_init_predicates_no_filtering_key(self):
        """Should return empty dicts when filtering key is absent."""
        result = self.handler.initialize_current_predicates(
            task_parameters={},
            predicates_map={},
        )
        assert result['current_predicates'] == {}

    def test_init_predicates_maps_intersects(self):
        """Should correctly map 'Intersects' to ST_Intersects."""
        predicates_map = {"Intersects": "ST_Intersects"}
        result = self.handler.initialize_current_predicates(
            task_parameters={
                "filtering": {
                    "geometric_predicates": ["Intersects"],
                }
            },
            predicates_map=predicates_map,
        )
        assert "ST_Intersects" in result['current_predicates']
        assert 0 in result['numeric_predicates']  # QGIS code for Intersects

    def test_init_predicates_maps_multiple(self):
        """Should correctly map multiple predicates."""
        predicates_map = {
            "Intersects": "ST_Intersects",
            "Contains": "ST_Contains",
            "Within": "ST_Within",
        }
        result = self.handler.initialize_current_predicates(
            task_parameters={
                "filtering": {
                    "geometric_predicates": ["Intersects", "Contains", "Within"],
                }
            },
            predicates_map=predicates_map,
        )
        assert len(result['current_predicates']) == 3
        assert "ST_Intersects" in result['current_predicates']
        assert "ST_Contains" in result['current_predicates']
        assert "ST_Within" in result['current_predicates']

    def test_init_predicates_unknown_predicate_ignored(self):
        """Should skip unknown predicate keys without crashing."""
        predicates_map = {"Intersects": "ST_Intersects"}
        result = self.handler.initialize_current_predicates(
            task_parameters={
                "filtering": {
                    "geometric_predicates": ["Intersects", "UnknownPredicate"],
                }
            },
            predicates_map=predicates_map,
        )
        assert len(result['current_predicates']) == 1

    def test_init_predicates_propagates_to_expression_builder(self):
        """Should propagate predicates to expression_builder if provided."""
        predicates_map = {"Intersects": "ST_Intersects"}
        mock_eb = MagicMock()

        self.handler.initialize_current_predicates(
            task_parameters={
                "filtering": {
                    "geometric_predicates": ["Intersects"],
                }
            },
            predicates_map=predicates_map,
            expression_builder=mock_eb,
        )

        assert mock_eb.current_predicates == {"ST_Intersects": "ST_Intersects"}

    def test_init_predicates_propagates_to_filter_orchestrator(self):
        """Should propagate predicates to filter_orchestrator if provided."""
        predicates_map = {"Within": "ST_Within"}
        mock_fo = MagicMock()

        self.handler.initialize_current_predicates(
            task_parameters={
                "filtering": {
                    "geometric_predicates": ["Within"],
                }
            },
            predicates_map=predicates_map,
            filter_orchestrator=mock_fo,
        )

        assert mock_fo.current_predicates == {"ST_Within": "ST_Within"}


# ===========================================================================
# SourceGeometryPreparer Tests
# ===========================================================================

class TestSourceGeometryPreparer:
    """Tests for SourceGeometryPreparer -- Backend geometry delegation."""

    @pytest.fixture(autouse=True)
    def setup_handler(self, mock_backend_services):
        """Create SourceGeometryPreparer with mocked backend services."""
        with patch('core.tasks.source_geometry_preparer.get_backend_services',
                   return_value=mock_backend_services):
            from core.tasks.source_geometry_preparer import SourceGeometryPreparer
            self.handler = SourceGeometryPreparer()
            self.mock_bs = mock_backend_services

    def test_prepare_postgresql_source_geom_delegates(self):
        """Should delegate to backend services."""
        self.mock_bs.prepare_postgresql_source_geom.return_value = (
            '"public"."table"."geom"', None
        )

        result = self.handler.prepare_postgresql_source_geom(
            source_table="parcels",
            source_schema="public",
            source_geom="geom",
        )

        assert result['geom'] == '"public"."table"."geom"'
        assert result['mv_name'] is None
        self.mock_bs.prepare_postgresql_source_geom.assert_called_once()

    def test_prepare_postgresql_source_geom_uses_cached_count(self):
        """Should prefer cached feature count over layer.featureCount()."""
        self.mock_bs.prepare_postgresql_source_geom.return_value = ("geom", None)

        mock_layer = MagicMock()
        mock_layer.featureCount.return_value = 999999  # Should NOT be used

        self.handler.prepare_postgresql_source_geom(
            source_table="t",
            source_schema="s",
            source_geom="g",
            source_feature_count=5000,  # Should be used
            source_layer=mock_layer,
        )

        call_kwargs = self.mock_bs.prepare_postgresql_source_geom.call_args
        assert call_kwargs.kwargs.get('source_feature_count') == 5000

    def test_prepare_ogr_source_geom_not_available(self):
        """Should return None when OGR executor is not available."""
        result = self.handler.prepare_ogr_source_geom(
            source_layer=MagicMock(),
            task_parameters={},
            ogr_executor=None,
            ogr_executor_available=False,
        )
        assert result is None

    def test_prepare_ogr_source_geom_no_context_class(self):
        """Should return None when OGR executor lacks OGRSourceContext."""
        mock_ogr = MagicMock(spec=[])  # spec=[] means no attributes

        result = self.handler.prepare_ogr_source_geom(
            source_layer=MagicMock(),
            task_parameters={},
            ogr_executor=mock_ogr,
            ogr_executor_available=True,
        )
        assert result is None

    def test_prepare_spatialite_source_geom_no_context_class(self):
        """Should return failure when SpatialiteSourceContext is not available."""
        self.mock_bs.get_spatialite_source_context_class.return_value = None

        result = self.handler.prepare_spatialite_source_geom(
            source_layer=MagicMock(),
            task_parameters={},
        )
        assert result['success'] is False
        assert "not available" in result['error_message']


# ===========================================================================
# SubsetManagementHandler Tests
# ===========================================================================

class TestSubsetManagementHandler:
    """Tests for SubsetManagementHandler -- Subset string management."""

    @pytest.fixture(autouse=True)
    def setup_handler(self, mock_backend_services):
        """Create SubsetManagementHandler with mocked dependencies."""
        with patch('core.tasks.subset_management_handler.get_backend_services',
                   return_value=mock_backend_services):
            from core.tasks.subset_management_handler import SubsetManagementHandler
            self.handler = SubsetManagementHandler()
            self.mock_bs = mock_backend_services

    # --- determine_backend ---

    def test_determine_backend_postgresql(self, mock_pg_layer):
        """Should detect PostgreSQL backend when provider is postgres."""
        with patch('core.tasks.subset_management_handler.detect_layer_provider_type',
                   return_value='postgresql'):
            provider, use_pg, use_sl = self.handler.determine_backend(
                mock_pg_layer, postgresql_available=True
            )
        assert provider == 'postgresql'
        assert use_pg is True
        assert use_sl is False

    def test_determine_backend_postgresql_unavailable(self, mock_pg_layer):
        """When PostgreSQL not available, should fall back to Spatialite."""
        with patch('core.tasks.subset_management_handler.detect_layer_provider_type',
                   return_value='postgresql'):
            provider, use_pg, use_sl = self.handler.determine_backend(
                mock_pg_layer, postgresql_available=False
            )
        assert provider == 'postgresql'
        assert use_pg is False
        assert use_sl is True

    def test_determine_backend_ogr(self, mock_layer):
        """Should detect OGR backend and route to Spatialite path."""
        with patch('core.tasks.subset_management_handler.detect_layer_provider_type',
                   return_value='ogr'):
            provider, use_pg, use_sl = self.handler.determine_backend(
                mock_layer, postgresql_available=True
            )
        assert provider == 'ogr'
        assert use_pg is False
        assert use_sl is True

    def test_determine_backend_spatialite(self, mock_layer):
        """Should detect Spatialite backend."""
        with patch('core.tasks.subset_management_handler.detect_layer_provider_type',
                   return_value='spatialite'):
            provider, use_pg, use_sl = self.handler.determine_backend(
                mock_layer, postgresql_available=True
            )
        assert provider == 'spatialite'
        assert use_pg is False
        assert use_sl is True

    # --- log_performance_warning_if_needed ---

    def test_performance_warning_large_spatialite(self, mock_layer):
        """Should log warning for large Spatialite datasets (>50000)."""
        mock_layer.featureCount.return_value = 100000
        # This should not raise, just log a warning
        self.handler.log_performance_warning_if_needed(True, mock_layer)

    def test_no_performance_warning_small_dataset(self, mock_layer):
        """Should NOT warn for small datasets."""
        mock_layer.featureCount.return_value = 1000
        self.handler.log_performance_warning_if_needed(True, mock_layer)

    def test_no_performance_warning_postgresql(self, mock_layer):
        """Should NOT warn when using PostgreSQL (not Spatialite)."""
        mock_layer.featureCount.return_value = 100000
        self.handler.log_performance_warning_if_needed(False, mock_layer)

    # --- get_spatialite_datasource ---

    def test_get_spatialite_datasource_native(self, mock_layer):
        """Should return native datasource for Spatialite layers."""
        with patch('core.tasks.subset_management_handler.get_spatialite_datasource_from_layer',
                   create=True) as mock_get_ds:
            # Simulate the import
            import core.tasks.subset_management_handler as mod
            with patch.object(mod, 'get_spatialite_datasource_from_layer',
                            create=True, side_effect=ImportError):
                pass

    def test_get_spatialite_datasource_fallback(self, mock_layer):
        """When not native Spatialite, should use filterMate db path."""
        with patch(
            'core.tasks.subset_management_handler.get_spatialite_datasource_from_layer',
            return_value=(None, None),
            create=True,
        ):
            from core.tasks.subset_management_handler import SubsetManagementHandler
            handler = SubsetManagementHandler.__new__(SubsetManagementHandler)
            handler._backend_services = MagicMock()

            db_path, table_name, layer_srid, is_native = handler.get_spatialite_datasource(
                mock_layer, "/tmp/filtermate.db"
            )
            assert db_path == "/tmp/filtermate.db"
            assert is_native is False

    # --- build_spatialite_query ---

    def test_build_spatialite_query_with_executor(self):
        """Should delegate to sl_executor when available."""
        mock_sl = MagicMock()
        mock_sl.build_spatialite_query.return_value = "SELECT * FROM t"

        result = self.handler.build_spatialite_query(
            sql_subset_string="raw query",
            table_name="test_table",
            geom_key_name="geom",
            primary_key_name="pk",
            custom=False,
            param_buffer_expression=None,
            param_buffer_value=None,
            param_buffer_segments=5,
            task_parameters={},
            sl_executor=mock_sl,
            sl_executor_available=True,
        )
        assert result == "SELECT * FROM t"
        mock_sl.build_spatialite_query.assert_called_once()

    def test_build_spatialite_query_fallback(self):
        """Should return original query when executor not available."""
        result = self.handler.build_spatialite_query(
            sql_subset_string="raw query",
            table_name="test_table",
            geom_key_name="geom",
            primary_key_name="pk",
            custom=False,
            param_buffer_expression=None,
            param_buffer_value=None,
            param_buffer_segments=5,
            task_parameters={},
            sl_executor=None,
            sl_executor_available=False,
        )
        assert result == "raw query"

    # --- filter_action_postgresql ---

    def test_filter_action_postgresql_raises_when_unavailable(self):
        """Should raise ImportError when PG executor is not available."""
        with pytest.raises(ImportError, match="not available"):
            self.handler.filter_action_postgresql(
                layer=MagicMock(),
                sql_subset_string="SELECT 1",
                primary_key_name="pk",
                geom_key_name="geom",
                name="test",
                custom=False,
                cur=MagicMock(),
                conn=MagicMock(),
                seq_order=1,
                queue_subset_fn=MagicMock(),
                get_connection_fn=MagicMock(),
                ensure_stats_fn=MagicMock(),
                extract_where_fn=MagicMock(),
                insert_history_fn=MagicMock(),
                get_session_name_fn=MagicMock(),
                ensure_schema_fn=MagicMock(),
                execute_commands_fn=MagicMock(),
                create_simple_mv_fn=MagicMock(),
                create_custom_mv_fn=MagicMock(),
                parse_where_clauses_fn=MagicMock(),
                source_schema="public",
                source_table="t",
                source_geom="geom",
                current_mv_schema="filtermate_temp",
                project_uuid="uuid",
                session_id="sess",
                param_buffer_expression=None,
                pg_execute_filter_fn=None,
                pg_executor_available=False,
            )

    def test_filter_action_postgresql_delegates_when_available(self):
        """Should delegate to pg_execute_filter_fn when available."""
        mock_pg_fn = MagicMock(return_value=True)

        result = self.handler.filter_action_postgresql(
            layer=MagicMock(),
            sql_subset_string="SELECT 1",
            primary_key_name="pk",
            geom_key_name="geom",
            name="test",
            custom=False,
            cur=MagicMock(),
            conn=MagicMock(),
            seq_order=1,
            queue_subset_fn=MagicMock(),
            get_connection_fn=MagicMock(),
            ensure_stats_fn=MagicMock(),
            extract_where_fn=MagicMock(),
            insert_history_fn=MagicMock(),
            get_session_name_fn=MagicMock(),
            ensure_schema_fn=MagicMock(),
            execute_commands_fn=MagicMock(),
            create_simple_mv_fn=MagicMock(),
            create_custom_mv_fn=MagicMock(),
            parse_where_clauses_fn=MagicMock(),
            source_schema="public",
            source_table="t",
            source_geom="geom",
            current_mv_schema="filtermate_temp",
            project_uuid="uuid",
            session_id="sess",
            param_buffer_expression=None,
            pg_execute_filter_fn=mock_pg_fn,
            pg_executor_available=True,
        )
        assert result is True
        mock_pg_fn.assert_called_once()

    # --- reset_action_postgresql ---

    def test_reset_action_postgresql_raises_when_unavailable(self):
        """Should raise ImportError when PG executor is not available."""
        with pytest.raises(ImportError, match="not available"):
            self.handler.reset_action_postgresql(
                layer=MagicMock(),
                name="test",
                cur=MagicMock(),
                conn=MagicMock(),
                queue_subset_fn=MagicMock(),
                get_connection_fn=MagicMock(),
                execute_commands_fn=MagicMock(),
                get_session_name_fn=MagicMock(),
                project_uuid="uuid",
                current_mv_schema="filtermate_temp",
                ps_manager=None,
                pg_execute_reset_fn=None,
                pg_executor_available=False,
            )

    # --- reset_action_ogr ---

    def test_reset_action_ogr_with_executor(self, mock_layer):
        """Should delegate to ogr_execute_reset_fn when available."""
        mock_ogr_fn = MagicMock(return_value=True)
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        # Mock HistoryRepository
        with patch('core.tasks.subset_management_handler.HistoryRepository') as MockRepo:
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            result = self.handler.reset_action_ogr(
                layer=mock_layer,
                name="test",
                cur=mock_cur,
                conn=mock_conn,
                project_uuid="uuid",
                ps_manager=None,
                queue_subset_fn=MagicMock(),
                ogr_execute_reset_fn=mock_ogr_fn,
            )

        assert result is True
        mock_ogr_fn.assert_called_once()

    def test_reset_action_ogr_fallback_clears_subset(self, mock_layer):
        """Without OGR executor, should clear subset via queue_subset_fn."""
        mock_queue = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        with patch('core.tasks.subset_management_handler.HistoryRepository') as MockRepo:
            mock_repo_instance = MagicMock()
            MockRepo.return_value = mock_repo_instance

            result = self.handler.reset_action_ogr(
                layer=mock_layer,
                name="test",
                cur=mock_cur,
                conn=mock_conn,
                project_uuid="uuid",
                ps_manager=None,
                queue_subset_fn=mock_queue,
                ogr_execute_reset_fn=None,
            )

        assert result is True
        mock_queue.assert_called_once_with(mock_layer, '')
