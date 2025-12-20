# FilterMate BMAD Documentation

## 📋 Overview

This directory contains the BMAD (Business/Method for Agile Development) documentation for the FilterMate QGIS plugin.

## 📁 Document Structure

| Document | Purpose |
|----------|---------|
| [project.bmad.md](project.bmad.md) | Project overview, vision, goals, tech stack |
| [prd.md](prd.md) | Product Requirements Document - all functional/non-functional requirements |
| [architecture.md](architecture.md) | Technical architecture, data flows, component details |
| [epics.md](epics.md) | Epic definitions with user stories (6 completed epics) |
| [roadmap.md](roadmap.md) | Development roadmap with completed/planned phases |
| [quality.md](quality.md) | Quality standards, testing, code guidelines |

## 🎯 Quick Links

### For New Contributors
1. Start with [project.bmad.md](project.bmad.md) for overview
2. Read [architecture.md](architecture.md) for technical details
3. Check [quality.md](quality.md) for coding standards

### For Product Managers
1. [prd.md](prd.md) - Complete requirements
2. [epics.md](epics.md) - Feature breakdown
3. [roadmap.md](roadmap.md) - Timeline and phases

### For Developers
1. [architecture.md](architecture.md) - System design
2. [quality.md](quality.md) - Standards and testing
3. [epics.md](epics.md) - User stories for context

## 📊 Current Status

| Metric | Value |
|--------|-------|
| **Version** | 2.3.8 |
| **Status** | Production - Stable |
| **Quality Score** | 9.0/10 |
| **Test Coverage** | ~70% |
| **Completed Epics** | 6/6 |
| **Active Phase** | Testing & Documentation |

## 🔗 Related Documentation

- [Main README](../README.md) - User-facing documentation
- [CHANGELOG](../CHANGELOG.md) - Version history
- [GitHub Copilot Instructions](../.github/copilot-instructions.md) - AI coding guidelines
- [Serena Memories](../.serena/) - Development context and memory

## 📝 Updating Documents

When updating BMAD documents:

1. **Version Control**: Update "Last Updated" date
2. **Consistency**: Keep cross-references accurate
3. **Completeness**: Update status of epics/stories
4. **Metrics**: Refresh quality metrics regularly

## 🏗️ Document Templates

### Epic Template
```markdown
# Epic: [Title]

## Epic Overview
| Field | Value |
|-------|-------|
| Epic ID | EPIC-XXX |
| Status | 📋 Planned / 🔄 In Progress / ✅ Complete |

## Goal
[One paragraph describing the goal]

## User Stories
### STORY-XXX: [Title]
**As a** [user type]
**I want** [action]
**So that** [benefit]

**Acceptance Criteria**:
- [ ] Criterion 1
- [ ] Criterion 2
```

### Story Template
```markdown
### STORY-XXX: [Title]
**As a** [user type]
**I want** [action]
**So that** [benefit]

**Acceptance Criteria**:
- [ ] AC1
- [ ] AC2

**Technical Notes**:
- Implementation detail
- Affected files
```
