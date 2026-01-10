# Backups from EPIC-1 Migration

This directory contains backup files from the EPIC-1 migration (Option A2).

## Files

- **task_utils.py.backup** (564 lines) - Original implementation before migration to infrastructure/utils/task_utils.py
  - Migration date: 2026-01-10
  - Commit: 8f8e131
  - New location: infrastructure/utils/task_utils.py (370 lines cleaned)

- **query_cache.py.backup** (627 lines) - Original implementation before migration to infrastructure/cache/query_cache.py
  - Migration date: 2026-01-10  
  - Commit: 8f8e131
  - New location: infrastructure/cache/query_cache.py (626 lines)

## Migration Path

```python
# OLD (deprecated)
from modules.tasks.task_utils import spatialite_connect
from modules.tasks.query_cache import QueryExpressionCache

# NEW
from infrastructure.utils import spatialite_connect
from infrastructure.cache import QueryExpressionCache
```

Shims remain in modules/tasks/ for backward compatibility.
