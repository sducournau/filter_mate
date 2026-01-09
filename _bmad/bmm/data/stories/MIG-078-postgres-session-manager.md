---
storyId: MIG-078
title: Create PostgresSessionManager
epic: 6.4 - Additional Services
phase: 6
sprint: 7
priority: P2
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-030]
blocks: [MIG-087]
createdAt: 2026-01-09
updatedAt: 2026-01-09
---

# MIG-078: Create PostgresSessionManager

## 📋 Story

**En tant que** développeur,  
**Je veux** créer un manager pour les sessions PostgreSQL,  
**Afin que** le cleanup des vues et schémas soit isolé et gérable.

---

## 🎯 Objectif

Extraire les méthodes de gestion de session PostgreSQL de `filter_mate_dockwidget.py` (lignes 3248-3442) vers un manager dédié.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `adapters/backends/postgres_session_manager.py` créé (< 300 lignes)
- [ ] Type hints sur toutes les signatures
- [ ] Docstrings Google style

### Méthodes à Implémenter

- [ ] `toggle_auto_cleanup(enabled: bool) -> None`
- [ ] `cleanup_session_views() -> int`
- [ ] `cleanup_schema_if_empty(schema: str) -> bool`
- [ ] `register_temp_view(view_name: str) -> None`
- [ ] `unregister_temp_view(view_name: str) -> None`
- [ ] `get_session_views() -> List[str]`
- [ ] `cleanup_on_close() -> int`

### Intégration

- [ ] Utilise `PostgreSQLBackend` existant pour les opérations DB
- [ ] Vérifie `POSTGRESQL_AVAILABLE` avant toute opération
- [ ] S'intègre avec le cycle de vie du plugin

### Tests

- [ ] `tests/unit/adapters/backends/test_postgres_session_manager.py` créé
- [ ] Tests pour cleanup
- [ ] Tests sans PostgreSQL disponible
- [ ] Couverture > 80%

---

## 📝 Spécifications Techniques

### Structure du Manager

```python
"""
PostgreSQL Session Manager for FilterMate.

Manages temporary views and cleanup for PostgreSQL sessions.
Extracted from filter_mate_dockwidget.py (lines 3248-3442).
"""

from typing import List, Optional, Set
import logging

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

logger = logging.getLogger(__name__)


class PostgresSessionManager:
    """
    Manager for PostgreSQL session resources.

    Handles:
    - Tracking of temporary views created during filtering
    - Auto-cleanup toggle
    - Manual cleanup of views and schemas
    - Cleanup on plugin close

    Note: All operations check POSTGRESQL_AVAILABLE first.
    """

    FILTERMATE_SCHEMA = 'filtermate_temp'
    VIEW_PREFIX = 'fm_view_'

    def __init__(self, connection_provider=None) -> None:
        """
        Initialize the session manager.

        Args:
            connection_provider: Callable that returns a psycopg2 connection
        """
        self._connection_provider = connection_provider
        self._temp_views: Set[str] = set()
        self._auto_cleanup_enabled: bool = True
        self._initialized: bool = False

    @property
    def is_available(self) -> bool:
        """Check if PostgreSQL is available."""
        return POSTGRESQL_AVAILABLE and self._connection_provider is not None

    def toggle_auto_cleanup(self, enabled: bool) -> None:
        """
        Toggle automatic cleanup of temporary views.

        Args:
            enabled: True to enable auto-cleanup
        """
        self._auto_cleanup_enabled = enabled
        logger.info(f"Auto-cleanup {'enabled' if enabled else 'disabled'}")

    def register_temp_view(self, view_name: str) -> None:
        """
        Register a temporary view for tracking.

        Args:
            view_name: Name of the temporary view
        """
        full_name = f"{self.FILTERMATE_SCHEMA}.{view_name}"
        self._temp_views.add(full_name)
        logger.debug(f"Registered temp view: {full_name}")

    def unregister_temp_view(self, view_name: str) -> None:
        """
        Unregister a temporary view.

        Args:
            view_name: Name of the temporary view
        """
        full_name = f"{self.FILTERMATE_SCHEMA}.{view_name}"
        self._temp_views.discard(full_name)
        logger.debug(f"Unregistered temp view: {full_name}")

    def get_session_views(self) -> List[str]:
        """
        Get list of registered temporary views.

        Returns:
            List of view names
        """
        return list(self._temp_views)

    def cleanup_session_views(self) -> int:
        """
        Cleanup all registered temporary views.

        Returns:
            Number of views cleaned up
        """
        if not self.is_available:
            logger.debug("PostgreSQL not available, skipping cleanup")
            return 0

        if not self._temp_views:
            return 0

        cleaned = 0
        conn = None

        try:
            conn = self._connection_provider()
            cursor = conn.cursor()

            for view_name in list(self._temp_views):
                try:
                    # Use DROP VIEW IF EXISTS for safety
                    cursor.execute(
                        f"DROP VIEW IF EXISTS {view_name} CASCADE"
                    )
                    self._temp_views.discard(view_name)
                    cleaned += 1
                    logger.debug(f"Dropped view: {view_name}")
                except Exception as e:
                    logger.warning(f"Failed to drop {view_name}: {e}")

            conn.commit()

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

        logger.info(f"Cleaned up {cleaned} temporary views")
        return cleaned

    def cleanup_schema_if_empty(self, schema: str = None) -> bool:
        """
        Drop schema if it contains no objects.

        Args:
            schema: Schema name (default: FILTERMATE_SCHEMA)

        Returns:
            True if schema was dropped
        """
        if not self.is_available:
            return False

        schema = schema or self.FILTERMATE_SCHEMA
        conn = None

        try:
            conn = self._connection_provider()
            cursor = conn.cursor()

            # Check if schema has any objects
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = %s
            """, (schema,))

            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema}")
                conn.commit()
                logger.info(f"Dropped empty schema: {schema}")
                return True
            else:
                logger.debug(f"Schema {schema} not empty ({count} objects)")
                return False

        except Exception as e:
            logger.error(f"Failed to check/drop schema: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def cleanup_on_close(self) -> int:
        """
        Perform cleanup when plugin is closing.

        Called from FilterMate.unload().

        Returns:
            Number of resources cleaned up
        """
        if not self._auto_cleanup_enabled:
            logger.info("Auto-cleanup disabled, skipping close cleanup")
            return 0

        cleaned = self.cleanup_session_views()
        self.cleanup_schema_if_empty()

        return cleaned

    def ensure_schema_exists(self) -> bool:
        """
        Ensure the FilterMate temp schema exists.

        Returns:
            True if schema exists or was created
        """
        if not self.is_available:
            return False

        conn = None

        try:
            conn = self._connection_provider()
            cursor = conn.cursor()

            cursor.execute(
                f"CREATE SCHEMA IF NOT EXISTS {self.FILTERMATE_SCHEMA}"
            )
            conn.commit()

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
```

---

## 🔗 Dépendances

### Entrée

- MIG-030: PostgreSQL Backend (connexion provider)
- `modules/appUtils.py` (POSTGRESQL_AVAILABLE)

### Sortie

- MIG-087: Final refactoring

---

## 📊 Métriques

| Métrique                | Avant       | Après        |
| ----------------------- | ----------- | ------------ |
| Logique dans dockwidget | ~195 lignes | 0            |
| Nouveau fichier         | -           | < 300 lignes |
| Testabilité             | Faible      | Élevée       |

---

## 🧪 Scénarios de Test

### Test 1: Register and Cleanup Views

```python
def test_register_and_cleanup_views():
    """Les vues enregistrées doivent être nettoyées."""
    mock_conn = Mock()
    manager = PostgresSessionManager(lambda: mock_conn)

    manager.register_temp_view("test_view")
    assert "filtermate_temp.test_view" in manager.get_session_views()

    cleaned = manager.cleanup_session_views()

    assert cleaned == 1
    assert len(manager.get_session_views()) == 0
```

### Test 2: Skip When PostgreSQL Unavailable

```python
def test_skip_when_unavailable():
    """Le cleanup doit être ignoré si PostgreSQL n'est pas disponible."""
    manager = PostgresSessionManager(None)  # No connection

    result = manager.cleanup_session_views()

    assert result == 0
```

### Test 3: Toggle Auto-Cleanup

```python
def test_toggle_auto_cleanup():
    """Le toggle doit changer l'état de cleanup auto."""
    manager = PostgresSessionManager(lambda: Mock())

    manager.toggle_auto_cleanup(False)
    assert manager._auto_cleanup_enabled is False

    manager.toggle_auto_cleanup(True)
    assert manager._auto_cleanup_enabled is True
```

---

## 📋 Checklist Développeur

- [ ] Créer le fichier `adapters/backends/postgres_session_manager.py`
- [ ] Implémenter `PostgresSessionManager`
- [ ] Ajouter export dans `adapters/backends/__init__.py`
- [ ] Intégrer avec `filter_mate.py` (unload)
- [ ] Créer fichier de test
- [ ] Tester avec et sans PostgreSQL disponible

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
