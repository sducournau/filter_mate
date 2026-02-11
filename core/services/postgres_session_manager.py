"""
PostgresSessionManager - PostgreSQL Session Management Service.

Manages PostgreSQL session lifecycle including:
- Session ID generation and tracking
- Schema management
- View tracking and cleanup
- Session info retrieval

Extracted from filter_mate_dockwidget.py as part of God Class migration.

Story: MIG-078
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction
"""

import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

try:
    from qgis.PyQt.QtCore import pyqtSignal, QObject
except ImportError:
    from PyQt5.QtCore import pyqtSignal, QObject

if TYPE_CHECKING:
    pass  # No QGIS type hints needed

from ...infrastructure.database.sql_utils import sanitize_sql_identifier

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """PostgreSQL session status."""
    INACTIVE = auto()
    ACTIVE = auto()
    CLEANING = auto()
    CLOSED = auto()
    ERROR = auto()


@dataclass
class SessionInfo:
    """Information about a PostgreSQL session."""
    session_id: str
    schema: str
    created_at: datetime
    status: SessionStatus = SessionStatus.INACTIVE
    view_count: int = 0
    total_schema_views: int = 0
    other_session_views: int = 0
    schema_exists: bool = False
    auto_cleanup_enabled: bool = True
    last_activity: Optional[datetime] = None


@dataclass
class ViewInfo:
    """Information about a materialized view."""
    name: str
    session_id: str
    schema: str
    layer_id: str
    created_at: datetime
    size_bytes: int = 0
    row_count: int = 0


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    success: bool
    views_dropped: int = 0
    views_failed: int = 0
    schema_dropped: bool = False
    error_message: str = ""


class PostgresSessionManager(QObject):
    """
    Service for PostgreSQL session management.

    Provides:
    - Session ID generation and tracking
    - Schema creation and management
    - View tracking for current session
    - Session cleanup operations
    - Session info retrieval
    - Multi-session coordination

    Emits:
    - session_started: When a new session is started
    - session_closed: When session is closed
    - view_created: When a view is created
    - view_dropped: When a view is dropped
    - cleanup_completed: When cleanup finishes
    - error_occurred: When an error occurs
    """

    # Signals
    session_started = pyqtSignal(str)  # session_id
    session_closed = pyqtSignal(str)  # session_id
    view_created = pyqtSignal(str, str)  # session_id, view_name
    view_dropped = pyqtSignal(str, str)  # session_id, view_name
    cleanup_completed = pyqtSignal(str, int)  # session_id, count
    error_occurred = pyqtSignal(str, str)  # operation, error_message

    # Default schema name
    DEFAULT_SCHEMA = "filtermate_temp"

    # View prefix pattern (unified fm_temp_mv_ prefix v4.4.4)
    VIEW_PREFIX = "fm_temp_mv_"

    def __init__(
        self,
        schema: str = DEFAULT_SCHEMA,
        auto_cleanup: bool = True,
        parent: Optional[QObject] = None
    ):
        """
        Initialize PostgresSessionManager.

        Args:
            schema: PostgreSQL schema for temp objects
            auto_cleanup: Whether to auto-cleanup on close
            parent: Optional parent QObject
        """
        super().__init__(parent)

        self._session_id: Optional[str] = None
        self._schema = schema
        self._auto_cleanup = auto_cleanup
        self._status = SessionStatus.INACTIVE
        self._created_at: Optional[datetime] = None

        # Track views created in this session
        self._session_views: Dict[str, ViewInfo] = {}

        # Metrics
        self._metrics = {
            'views_created': 0,
            'views_dropped': 0,
            'cleanup_count': 0,
            'errors': 0,
            'last_cleanup': None
        }

    # ─────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._session_id

    @property
    def schema(self) -> str:
        """Get schema name."""
        return self._schema

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._status == SessionStatus.ACTIVE

    @property
    def auto_cleanup(self) -> bool:
        """Get auto-cleanup setting."""
        return self._auto_cleanup

    @auto_cleanup.setter
    def auto_cleanup(self, value: bool):
        """Set auto-cleanup setting."""
        self._auto_cleanup = value

    @property
    def status(self) -> SessionStatus:
        """Get current session status."""
        return self._status

    @property
    def metrics(self) -> dict:
        """Get session metrics."""
        return self._metrics.copy()

    @property
    def view_count(self) -> int:
        """Get number of views in this session."""
        return len(self._session_views)

    # ─────────────────────────────────────────────────────────────────
    # Session Lifecycle
    # ─────────────────────────────────────────────────────────────────

    def generate_session_id(self) -> str:
        """
        Generate a unique session ID.

        Format: 8 hex characters from UUID4

        Returns:
            str: Unique session ID
        """
        return uuid.uuid4().hex[:8]

    def start_session(self, session_id: Optional[str] = None) -> str:
        """
        Start a new PostgreSQL session.

        Args:
            session_id: Optional specific session ID, or auto-generate

        Returns:
            str: The session ID
        """
        if self._status == SessionStatus.ACTIVE:
            logger.warning(f"Session already active: {self._session_id}")
            return self._session_id

        self._session_id = session_id or self.generate_session_id()
        self._created_at = datetime.now()
        self._status = SessionStatus.ACTIVE
        self._session_views.clear()

        logger.info(f"PostgreSQL session started: {self._session_id}")
        self.session_started.emit(self._session_id)

        return self._session_id

    def close_session(
        self,
        connection: Any = None,
        force_cleanup: bool = False
    ) -> CleanupResult:
        """
        Close the current session.

        Args:
            connection: Optional database connection for cleanup
            force_cleanup: Force cleanup even if auto_cleanup disabled

        Returns:
            CleanupResult with cleanup details
        """
        if not self._session_id:
            return CleanupResult(
                success=True,
                error_message="No active session"
            )

        session_id = self._session_id
        result = CleanupResult(success=True)

        # Cleanup if needed
        if connection and (self._auto_cleanup or force_cleanup):
            self._status = SessionStatus.CLEANING
            result = self.cleanup_session_views(connection)

        # Reset state
        self._session_id = None
        self._status = SessionStatus.CLOSED
        self._session_views.clear()

        logger.info(f"PostgreSQL session closed: {session_id}")
        self.session_closed.emit(session_id)

        return result

    # ─────────────────────────────────────────────────────────────────
    # View Management
    # ─────────────────────────────────────────────────────────────────

    def get_view_name(self, layer_id: str, suffix: str = "") -> str:
        """
        Generate a view name for a layer.

        v4.4.4: Uses unified fm_temp_mv_ prefix.
        Format: fm_temp_mv_{session_id}_{layer_id_short}_{suffix}

        Args:
            layer_id: Layer ID
            suffix: Optional suffix

        Returns:
            str: View name
        """
        if not self._session_id:
            raise ValueError("No active session")

        # Sanitize layer_id (use first 8 chars of hash)
        layer_short = str(hash(layer_id) % 10**8).zfill(8)

        if suffix:
            return f"{self.VIEW_PREFIX}{self._session_id}_{layer_short}_{suffix}"
        return f"{self.VIEW_PREFIX}{self._session_id}_{layer_short}"

    def register_view(
        self,
        view_name: str,
        layer_id: str
    ) -> None:
        """
        Register a view created by this session.

        Args:
            view_name: Name of the materialized view
            layer_id: Associated layer ID
        """
        if not self._session_id:
            return

        view_info = ViewInfo(
            name=view_name,
            session_id=self._session_id,
            schema=self._schema,
            layer_id=layer_id,
            created_at=datetime.now()
        )

        self._session_views[view_name] = view_info
        self._metrics['views_created'] += 1

        logger.debug(f"Registered view: {view_name}")
        self.view_created.emit(self._session_id, view_name)

    def unregister_view(self, view_name: str) -> None:
        """
        Unregister a view (after dropping).

        Args:
            view_name: Name of the view
        """
        if view_name in self._session_views:
            del self._session_views[view_name]
            self._metrics['views_dropped'] += 1

            if self._session_id:
                self.view_dropped.emit(self._session_id, view_name)

    def get_session_views(self) -> List[str]:
        """
        Get list of views created by this session.

        Returns:
            List of view names
        """
        return list(self._session_views.keys())

    def is_session_view(self, view_name: str) -> bool:
        """
        Check if a view belongs to this session.

        Args:
            view_name: View name to check

        Returns:
            bool: True if view belongs to current session
        """
        if not self._session_id:
            return False

        # Check local registry
        if view_name in self._session_views:
            return True

        # Check naming pattern
        prefix = f"{self.VIEW_PREFIX}{self._session_id}_"
        return view_name.startswith(prefix)

    # ─────────────────────────────────────────────────────────────────
    # Cleanup Operations
    # ─────────────────────────────────────────────────────────────────

    def cleanup_session_views(
        self,
        connection: Any,
        session_id: Optional[str] = None
    ) -> CleanupResult:
        """
        Clean up all materialized views for a session.

        Args:
            connection: Database connection (psycopg2)
            session_id: Session to clean (defaults to current)

        Returns:
            CleanupResult with details
        """
        target_session = session_id or self._session_id

        if not target_session:
            return CleanupResult(
                success=False,
                error_message="No session ID specified"
            )

        try:
            cursor = connection.cursor()

            # Find all views for this session (unified fm_temp_* prefix v4.4.4)
            # Also check legacy mv_ prefix for backward compatibility
            cursor.execute("""
                SELECT matviewname FROM pg_matviews
                WHERE schemaname = %s
                AND (matviewname LIKE %s OR matviewname LIKE %s)
            """, (self._schema, f"fm_temp_mv_{target_session}_%", f"mv_{target_session}_%"))

            views = cursor.fetchall()

            if not views:
                return CleanupResult(
                    success=True,
                    views_dropped=0
                )

            dropped = 0
            failed = 0

            for (view_name,) in views:
                try:
                    cursor.execute(
                        f'DROP MATERIALIZED VIEW IF EXISTS "{self._schema}"."{view_name}" CASCADE;'
                    )
                    dropped += 1
                    self.unregister_view(view_name)
                except Exception as e:
                    logger.warning(f"Failed to drop view {view_name}: {e}")
                    failed += 1

            connection.commit()

            self._metrics['cleanup_count'] += 1
            self._metrics['last_cleanup'] = datetime.now().isoformat()

            logger.info(
                f"Cleaned up {dropped} views for session {target_session} "
                f"({failed} failed)"
            )

            self.cleanup_completed.emit(target_session, dropped)

            return CleanupResult(
                success=True,
                views_dropped=dropped,
                views_failed=failed
            )

        except Exception as e:
            self._metrics['errors'] += 1
            error_msg = str(e)
            logger.error(f"Cleanup failed: {error_msg}")
            self.error_occurred.emit("cleanup", error_msg)

            return CleanupResult(
                success=False,
                error_message=error_msg
            )

    def cleanup_schema_if_empty(
        self,
        connection: Any,
        force: bool = False
    ) -> CleanupResult:
        """
        Drop schema if no other sessions are using it.

        Args:
            connection: Database connection
            force: Force drop even if other sessions exist

        Returns:
            CleanupResult with details
        """
        try:
            cursor = connection.cursor()

            # Check if schema exists
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.schemata
                WHERE schema_name = %s
            """, (self._schema,))

            if cursor.fetchone()[0] == 0:
                return CleanupResult(
                    success=True,
                    error_message=f"Schema '{self._schema}' does not exist"
                )

            # Check for views from other sessions
            cursor.execute("""
                SELECT matviewname FROM pg_matviews
                WHERE schemaname = %s
            """, (self._schema,))

            views = cursor.fetchall()

            other_session_views = []
            for (view_name,) in views:
                if not self.is_session_view(view_name):
                    other_session_views.append(view_name)

            if other_session_views and not force:
                return CleanupResult(
                    success=False,
                    error_message=f"Schema has {len(other_session_views)} views from other sessions"
                )

            # Drop schema
            safe_schema = sanitize_sql_identifier(self._schema)
            cursor.execute(f'DROP SCHEMA IF EXISTS "{safe_schema}" CASCADE;')
            connection.commit()

            logger.info(f"Dropped schema: {self._schema}")

            return CleanupResult(
                success=True,
                schema_dropped=True
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Schema cleanup failed: {error_msg}")
            self.error_occurred.emit("schema_cleanup", error_msg)

            return CleanupResult(
                success=False,
                error_message=error_msg
            )

    def ensure_schema_exists(self, connection: Any) -> bool:
        """
        Ensure the temp schema exists, creating if needed.

        Args:
            connection: Database connection

        Returns:
            bool: True if schema exists/created
        """
        try:
            cursor = connection.cursor()
            safe_schema = sanitize_sql_identifier(self._schema)
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{safe_schema}";')
            connection.commit()

            logger.debug(f"Ensured schema exists: {self._schema}")
            return True

        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            self.error_occurred.emit("create_schema", str(e))
            return False

    # ─────────────────────────────────────────────────────────────────
    # Session Info
    # ─────────────────────────────────────────────────────────────────

    def get_session_info(
        self,
        connection: Optional[Any] = None
    ) -> SessionInfo:
        """
        Get information about the current session.

        Args:
            connection: Optional database connection for DB info

        Returns:
            SessionInfo object
        """
        info = SessionInfo(
            session_id=self._session_id or "",
            schema=self._schema,
            created_at=self._created_at or datetime.now(),
            status=self._status,
            view_count=len(self._session_views),
            auto_cleanup_enabled=self._auto_cleanup
        )

        if connection and self._session_id:
            try:
                cursor = connection.cursor()

                # Count our session views in DB
                cursor.execute("""
                    SELECT COUNT(*) FROM pg_matviews
                    WHERE schemaname = %s AND matviewname LIKE %s
                """, (self._schema, f"mv_{self._session_id}_%"))
                info.view_count = cursor.fetchone()[0]

                # Count all views in schema
                cursor.execute("""
                    SELECT COUNT(*) FROM pg_matviews
                    WHERE schemaname = %s
                """, (self._schema,))
                info.total_schema_views = cursor.fetchone()[0]

                info.other_session_views = info.total_schema_views - info.view_count

                # Check schema exists
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.schemata
                    WHERE schema_name = %s
                """, (self._schema,))
                info.schema_exists = cursor.fetchone()[0] > 0

            except Exception as e:
                logger.warning(f"Error getting session info from DB: {e}")

        return info

    def get_session_info_html(
        self,
        connection: Optional[Any] = None
    ) -> str:
        """
        Get session info as formatted HTML.

        Args:
            connection: Optional database connection

        Returns:
            HTML formatted string
        """
        info = self.get_session_info(connection)

        html = "<b>Session Information</b><br><br>"
        html += f"<b>Session ID:</b> {info.session_id or 'Not set'}<br>"
        html += f"<b>Status:</b> {info.status.name}<br>"
        html += f"<b>Schema:</b> {info.schema}<br>"
        html += f"<b>Auto-cleanup:</b> {'Enabled' if info.auto_cleanup_enabled else 'Disabled'}<br>"
        html += f"<b>Created:</b> {info.created_at.strftime('%H:%M:%S') if info.created_at else 'N/A'}<br><br>"

        if connection:
            html += f"<b>Schema exists:</b> {'Yes' if info.schema_exists else 'No'}<br>"
            html += f"<b>Your session views:</b> {info.view_count}<br>"
            html += f"<b>Total views in schema:</b> {info.total_schema_views}<br>"
            html += f"<b>Other sessions views:</b> {info.other_session_views}<br>"
        else:
            html += f"<b>Local view count:</b> {info.view_count}<br>"
            html += "<i>(Connect to DB for more info)</i><br>"

        return html

    # ─────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────

    def get_view_pattern(self, session_id: Optional[str] = None) -> str:
        """
        Get SQL LIKE pattern for matching session views.

        Args:
            session_id: Session ID (defaults to current)

        Returns:
            SQL LIKE pattern string
        """
        target = session_id or self._session_id
        if not target:
            return f"{self.VIEW_PREFIX}%"
        return f"{self.VIEW_PREFIX}{target}_%"

    def parse_view_name(self, view_name: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse a view name into components.

        Args:
            view_name: View name to parse

        Returns:
            Tuple of (session_id, layer_hash, suffix) or None
        """
        if not view_name.startswith(self.VIEW_PREFIX):
            return None

        parts = view_name[len(self.VIEW_PREFIX):].split("_")

        if len(parts) >= 2:
            session_id = parts[0]
            layer_hash = parts[1]
            suffix = "_".join(parts[2:]) if len(parts) > 2 else ""
            return (session_id, layer_hash, suffix)

        return None

    def reset(self) -> None:
        """Reset session manager to initial state."""
        self._session_id = None
        self._status = SessionStatus.INACTIVE
        self._created_at = None
        self._session_views.clear()

        self._metrics = {
            'views_created': 0,
            'views_dropped': 0,
            'cleanup_count': 0,
            'errors': 0,
            'last_cleanup': None
        }
