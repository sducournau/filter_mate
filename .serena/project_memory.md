# FilterMate Project Memory

**Version:** 4.1.0 | **Updated:** January 18, 2026

## Quick Reference

See **[CONSOLIDATED_PROJECT_CONTEXT.md](memories/CONSOLIDATED_PROJECT_CONTEXT.md)** for complete project documentation.

## Key Stats
- **Codebase:** 271,837 lines / 546 files
- **Architecture:** Hexagonal (complete)
- **Test Coverage:** 85% (106 tests)
- **Backends:** PostgreSQL, Spatialite, OGR, Memory

## Essential Imports

```python
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE
from core.tasks import FilterEngineTask
from core.services import FilterService, LayerService
from adapters.backends import BackendFactory
from infrastructure.utils.layer_utils import is_layer_valid
```

## Memory Files

| File | Purpose |
|------|---------|
| **CONSOLIDATED_PROJECT_CONTEXT.md** | Main reference (architecture, backends, issues) |
| project_overview.md | High-level overview |
| testing_documentation.md | Test guidelines |
| code_style_conventions.md | Coding standards |
| Other specialized memories | Feature-specific docs |

---
*Consolidated on January 18, 2026*
