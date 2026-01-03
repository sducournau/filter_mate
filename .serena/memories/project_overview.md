# FilterMate Project Overview

**Last Updated:** January 3, 2026  
**Version:** 2.8.0 (Enhanced Auto-Optimization)  
**Status:** Production - Active Development

## Recent Changes (v2.8.0)

### Enhanced Auto-Optimization System
- New `optimizer_metrics.py`: Metrics collection, LRU cache, pattern detection
- New `parallel_processor.py`: Multi-threaded spatial filtering
- Enhanced `auto_optimizer.py`: `EnhancedAutoOptimizer` class

### Critical Fixes (v2.7.x)
- **v2.7.2**: PostgreSQL + OGR source now uses WKT mode correctly
- **v2.7.3**: WKT decision uses SELECTED feature count (not total)
- **v2.7.4**: Enhanced diagnostic logging for distant layer filtering
- **v2.7.5**: CASE WHEN wrapper parsing for negative buffers

### Configuration Changes
- Config reload on plugin initialization
- Small dataset optimization DISABLED by default
- Progressive chunking now DEFAULT (not optional)

### UI Synchronization Fixes
- Geometric predicates button state sync
- Layers to filter combobox sync
- Use centroids checkboxes sync

## Architecture
- Multi-backend: PostgreSQL, Spatialite, OGR, Memory
- Factory pattern with automatic backend selection
- QgsTask for async operations

## Key Files
- `filter_mate_app.py`: Application orchestrator
- `modules/backends/`: Backend implementations
- `modules/tasks/filter_task.py`: Core filtering task

## See Also
- Memory: `enhanced_optimizer_v2.8.0` - Detailed v2.8.0 documentation
- Memory: `backend_architecture` - Multi-backend system
- Docs: `docs/ENHANCED_OPTIMIZATION_v2.8.0.md` - Full documentation