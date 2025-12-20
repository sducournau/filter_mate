# BMAD Integration with Serena

## Overview

FilterMate uses BMAD (Business Method for Agile Development) alongside Serena for comprehensive project documentation.

## BMAD Documents Location

All BMAD documents are in `.bmad-core/`:

| Document | Purpose |
|----------|---------|
| `project.bmad.md` | Project vision, goals, tech stack |
| `prd.md` | Product Requirements (40+ requirements) |
| `architecture.md` | Technical architecture diagrams |
| `epics.md` | 6 epics with 23 user stories |
| `roadmap.md` | Development phases (8 complete) |
| `quality.md` | Coding standards, testing |
| `personas.md` | 5 user personas |
| `tech-stack.md` | Complete technology stack |

## Mapping: Serena Memories ↔ BMAD

| When you need... | Read Serena Memory | Read BMAD Doc |
|------------------|-------------------|---------------|
| Current status | `project_overview` | `project.bmad.md` |
| Architecture | `architecture_overview` | `architecture.md` |
| Backend details | `backend_architecture` | `architecture.md` |
| Requirements | - | `prd.md` |
| User stories | - | `epics.md` |
| Roadmap | - | `roadmap.md` |
| Code style | `code_style_conventions` | `quality.md` |
| Performance | `performance_optimizations` | `prd.md` (NFR-PERF) |

## Development Workflow

### New Feature
1. **Check BMAD**: Is there a story in `epics.md`?
2. **Read Serena**: Get technical context from memories
3. **Implement**: Use Serena tools for navigation/editing
4. **Document**: Update relevant Serena memory
5. **Complete**: Mark story as ✅ in `epics.md`

### Bug Fix
1. **Check Serena**: Read `known_issues_bugs` memory
2. **Navigate**: Use symbolic tools to find code
3. **Fix**: Use `replace_symbol_body()` 
4. **Update**: Add to memory if significant

## Key BMAD Content Summary

### Completed Epics (epics.md)
- EPIC-001: Multi-Backend Filtering ✅
- EPIC-002: Undo/Redo System ✅
- EPIC-003: Configuration v2.0 ✅
- EPIC-004: Dark Mode & Theming ✅
- EPIC-005: Filter Favorites ✅
- EPIC-006: Project Change Stability ✅

### Current Phase (roadmap.md)
- Phase 8: Testing & Documentation (In Progress)
- Target: 80% test coverage
- Focus: Documentation, stability

### Future Phases
- Phase 9: Performance optimization (Q1 2026)
- Phase 10: Extensibility (Q2 2026)
- Phase 11: Enterprise features (Q3 2026)

## Quick Commands

```python
# Read BMAD requirements
# Just open .bmad-core/prd.md

# Check epic status
# Just open .bmad-core/epics.md

# Get architecture from Serena (faster)
mcp_oraios_serena_read_memory("architecture_overview")

# Get backend details
mcp_oraios_serena_read_memory("backend_architecture")
```
