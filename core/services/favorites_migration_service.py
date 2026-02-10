# -*- coding: utf-8 -*-
"""
Favorites Migration Service for FilterMate.

Handles automatic migration of orphan favorites and database maintenance.

Author: FilterMate Team
Date: January 2026
"""

import os
import logging
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime

logger = logging.getLogger('FilterMate.FavoritesMigration')


class FavoritesMigrationService:
    """
    Service for managing favorites migrations and cleanup.

    Provides:
    - Automatic orphan favorites migration on project load
    - Database cleanup for unused projects
    - Statistics and reporting
    """

    # UUID for global favorites (available in all projects)
    GLOBAL_PROJECT_UUID = "00000000-0000-0000-0000-000000000000"

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize FavoritesMigrationService.

        Args:
            db_path: Path to FilterMate SQLite database
        """
        self._db_path = db_path

    def set_database(self, db_path: str) -> None:
        """Set the database path."""
        self._db_path = db_path

    # ─────────────────────────────────────────────────────────────────
    # Orphan Migration
    # ─────────────────────────────────────────────────────────────────

    def count_orphan_favorites(self) -> int:
        """
        Count favorites associated with orphan projects.

        Returns:
            Number of orphan favorites
        """
        if not self._db_path:
            return 0

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Find favorites in orphan projects (empty name/path)
            cursor.execute("""
                SELECT COUNT(*) FROM fm_favorites f
                JOIN fm_projects p ON f.project_uuid = p.project_id
                WHERE (p.project_name = '' OR p.project_name IS NULL)
                  AND (p.project_path = '' OR p.project_path IS NULL)
            """)

            count = cursor.fetchone()[0]
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error counting orphan favorites: {e}")
            return 0

    def get_orphan_favorites_details(self) -> List[Dict[str, Any]]:
        """
        Get details of orphan favorites.

        Returns:
            List of dicts with favorite details
        """
        if not self._db_path:
            return []

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT f.id, f.name, f.expression, f.created_at, p.project_id
                FROM fm_favorites f
                JOIN fm_projects p ON f.project_uuid = p.project_id
                WHERE (p.project_name = '' OR p.project_name IS NULL)
                  AND (p.project_path = '' OR p.project_path IS NULL)
                ORDER BY f.created_at DESC
            """)

            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'name': row['name'],
                    'expression': row['expression'][:50] + '...' if len(row['expression']) > 50 else row['expression'],
                    'created_at': row['created_at'],
                    'orphan_project_uuid': row['project_id']
                })

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Error getting orphan favorites details: {e}")
            return []

    def migrate_orphan_favorites(
        self,
        target_project_uuid: str,
        source_project_uuid: Optional[str] = None
    ) -> Tuple[int, List[str]]:
        """
        Migrate orphan favorites to a target project.

        Args:
            target_project_uuid: UUID of the target project
            source_project_uuid: Optional specific orphan project UUID to migrate
                                (if None, migrates all orphans)

        Returns:
            Tuple of (migrated_count, list of migrated favorite names)
        """
        if not self._db_path or not target_project_uuid:
            return 0, []

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Get orphan favorites
            if source_project_uuid:
                cursor.execute("""
                    SELECT f.id, f.name FROM fm_favorites f
                    WHERE f.project_uuid = ?
                """, (source_project_uuid,))
            else:
                cursor.execute("""
                    SELECT f.id, f.name FROM fm_favorites f
                    JOIN fm_projects p ON f.project_uuid = p.project_id
                    WHERE (p.project_name = '' OR p.project_name IS NULL)
                      AND (p.project_path = '' OR p.project_path IS NULL)
                """)

            favorites_to_migrate = cursor.fetchall()

            if not favorites_to_migrate:
                conn.close()
                logger.info("No orphan favorites to migrate")
                return 0, []

            favorite_ids = [f[0] for f in favorites_to_migrate]
            favorite_names = [f[1] for f in favorites_to_migrate]

            # Update favorites to target project
            ','.join('?' * len(favorite_ids))
            cursor.execute("""
                UPDATE fm_favorites
                SET project_uuid = ?, updated_at = ?
                WHERE id IN ({placeholders})
            """, [target_project_uuid, datetime.now().isoformat()] + favorite_ids)

            conn.commit()
            conn.close()

            logger.info(f"✓ Migrated {len(favorite_names)} orphan favorites to project {target_project_uuid[:8]}...")
            for name in favorite_names:
                logger.info(f"  → Migrated: {name}")

            return len(favorite_names), favorite_names

        except Exception as e:
            logger.error(f"Error migrating orphan favorites: {e}")
            return 0, []

    def auto_migrate_on_project_load(self, project_uuid: str) -> Tuple[int, List[str]]:
        """
        Automatically migrate orphan favorites when a project is loaded.

        This is the main entry point called during project initialization.

        Args:
            project_uuid: UUID of the current project

        Returns:
            Tuple of (migrated_count, migrated_names)
        """
        orphan_count = self.count_orphan_favorites()

        if orphan_count == 0:
            return 0, []

        logger.info(f"🔄 Found {orphan_count} orphan favorite(s) - auto-migrating to current project")

        return self.migrate_orphan_favorites(project_uuid)

    # ─────────────────────────────────────────────────────────────────
    # Global Favorites
    # ─────────────────────────────────────────────────────────────────

    def ensure_global_project_exists(self) -> bool:
        """
        Ensure the global project entry exists in database.

        Returns:
            True if global project exists or was created
        """
        if not self._db_path:
            return False

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Check if global project exists
            cursor.execute(
                "SELECT project_id FROM fm_projects WHERE project_id = ?",
                (self.GLOBAL_PROJECT_UUID,)
            )

            if not cursor.fetchone():
                # Create global project entry
                cursor.execute("""
                    INSERT INTO fm_projects VALUES(
                        ?, datetime(), datetime(),
                        '__GLOBAL__', '__GLOBAL_FAVORITES__', '{}'
                    )
                """, (self.GLOBAL_PROJECT_UUID,))
                conn.commit()
                logger.info("✓ Created global favorites project entry")

            conn.close()
            return True

        except Exception as e:
            logger.error(f"Error ensuring global project exists: {e}")
            return False

    def get_global_favorites_count(self) -> int:
        """Get count of global favorites."""
        if not self._db_path:
            return 0

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM fm_favorites WHERE project_uuid = ?",
                (self.GLOBAL_PROJECT_UUID,)
            )

            count = cursor.fetchone()[0]
            conn.close()
            return count

        except Exception as e:
            logger.error(f"Error counting global favorites: {e}")
            return 0

    def make_favorite_global(self, favorite_id: str) -> bool:
        """
        Make a favorite global (available in all projects).

        Args:
            favorite_id: ID of favorite to make global

        Returns:
            True if successful
        """
        if not self._db_path:
            return False

        self.ensure_global_project_exists()

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE fm_favorites
                SET project_uuid = ?, updated_at = ?
                WHERE id = ?
            """, (self.GLOBAL_PROJECT_UUID, datetime.now().isoformat(), favorite_id))

            conn.commit()
            success = cursor.rowcount > 0
            conn.close()

            if success:
                logger.info(f"✓ Made favorite {favorite_id} global")

            return success

        except Exception as e:
            logger.error(f"Error making favorite global: {e}")
            return False

    def copy_favorite_to_project(
        self,
        favorite_id: str,
        target_project_uuid: str
    ) -> Optional[str]:
        """
        Copy a favorite to another project.

        Args:
            favorite_id: ID of favorite to copy
            target_project_uuid: Target project UUID

        Returns:
            New favorite ID if successful, None otherwise
        """
        if not self._db_path:
            return None

        try:
            import sqlite3
            import uuid

            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get original favorite
            cursor.execute("SELECT * FROM fm_favorites WHERE id = ?", (favorite_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                return None

            # Create new favorite with new ID
            new_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO fm_favorites (
                    id, project_uuid, name, expression, layer_name, layer_id,
                    layer_provider, description, tags, created_at, updated_at,
                    use_count, last_used_at, remote_layers, spatial_config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_id,
                target_project_uuid,
                row['name'],
                row['expression'],
                row['layer_name'],
                row['layer_id'],
                row['layer_provider'],
                row['description'],
                row['tags'],
                now,
                now,
                0,  # Reset use count
                None,
                row['remote_layers'],
                row['spatial_config']
            ))

            conn.commit()
            conn.close()

            logger.info(f"✓ Copied favorite to project {target_project_uuid[:8]}...")
            return new_id

        except Exception as e:
            logger.error(f"Error copying favorite: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────

    def cleanup_orphan_projects(self, keep_with_favorites: bool = True) -> Tuple[int, List[str]]:
        """
        Clean up orphan project entries.

        Args:
            keep_with_favorites: If True, don't delete projects that have favorites

        Returns:
            Tuple of (deleted_count, deleted_project_uuids)
        """
        if not self._db_path:
            return 0, []

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Find orphan projects (empty name/path)
            if keep_with_favorites:
                cursor.execute("""
                    SELECT p.project_id FROM fm_projects p
                    LEFT JOIN fm_favorites f ON p.project_id = f.project_uuid
                    WHERE (p.project_name = '' OR p.project_name IS NULL)
                      AND (p.project_path = '' OR p.project_path IS NULL)
                      AND f.id IS NULL
                      AND p.project_id != ?
                """, (self.GLOBAL_PROJECT_UUID,))
            else:
                cursor.execute("""
                    SELECT project_id FROM fm_projects
                    WHERE (project_name = '' OR project_name IS NULL)
                      AND (project_path = '' OR project_path IS NULL)
                      AND project_id != ?
                """, (self.GLOBAL_PROJECT_UUID,))

            orphan_ids = [row[0] for row in cursor.fetchall()]

            if not orphan_ids:
                conn.close()
                return 0, []

            # Delete orphan projects
            placeholders = ','.join('?' * len(orphan_ids))
            cursor.execute(f"DELETE FROM fm_projects WHERE project_id IN ({placeholders})", orphan_ids)  # nosec B608 - placeholders are ? parameters, orphan_ids passed as bound params (safe)

            conn.commit()
            conn.close()

            logger.info(f"✓ Cleaned up {len(orphan_ids)} orphan project(s)")
            return len(orphan_ids), orphan_ids

        except Exception as e:
            logger.error(f"Error cleaning up orphan projects: {e}")
            return 0, []

    # ─────────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────────

    def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with database statistics
        """
        if not self._db_path:
            return {'error': 'No database configured'}

        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Total projects
            cursor.execute("SELECT COUNT(*) FROM fm_projects")
            total_projects = cursor.fetchone()[0]

            # Total favorites
            cursor.execute("SELECT COUNT(*) FROM fm_favorites")
            total_favorites = cursor.fetchone()[0]

            # Orphan projects (no name/path)
            cursor.execute("""
                SELECT COUNT(*) FROM fm_projects
                WHERE (project_name = '' OR project_name IS NULL)
                  AND (project_path = '' OR project_path IS NULL)
            """)
            orphan_projects = cursor.fetchone()[0]

            # Orphan favorites
            orphan_favorites = self.count_orphan_favorites()

            # Global favorites
            global_favorites = self.get_global_favorites_count()

            # Favorites per project (top 5)
            cursor.execute("""
                SELECT p.project_name, COUNT(f.id) as fav_count
                FROM fm_projects p
                LEFT JOIN fm_favorites f ON p.project_id = f.project_uuid
                WHERE p.project_name != '' AND p.project_name IS NOT NULL
                GROUP BY p.project_id
                ORDER BY fav_count DESC
                LIMIT 5
            """)
            top_projects = [{'name': row[0], 'favorites': row[1]} for row in cursor.fetchall()]

            conn.close()

            return {
                'total_projects': total_projects,
                'total_favorites': total_favorites,
                'orphan_projects': orphan_projects,
                'orphan_favorites': orphan_favorites,
                'global_favorites': global_favorites,
                'top_projects': top_projects,
                'database_path': self._db_path,
                'database_size_kb': os.path.getsize(self._db_path) / 1024 if os.path.exists(self._db_path) else 0
            }

        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {'error': str(e)}
