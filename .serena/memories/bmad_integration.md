# BMAD Integration - FilterMate

**Last Updated:** February 1, 2026  
**BMAD Version:** 6.0.0-Beta.4  
**Project:** FilterMate v5.4.0

---

## Overview

FilterMate uses **BMAD (Business Model Agile Development)** for comprehensive project management, including requirements, user stories, workflows, and documentation.

---

## Configuration

### Core Config (_bmad/core/config.yaml)

```yaml
user_name: Simon
communication_language: French
document_output_language: English
output_folder: "{project-root}/_bmad-output"
```

### Agent Configuration

Location: `_bmad/_config/agent-manifest.csv`

**Available Agents:**
- **@bmad-master**: Orchestrator, knowledge custodian, workflow executor
- **@dev** (Amelia): Developer - strict implementation from user stories
- **@architect** (Winston): System architect - design decisions, patterns
- **@analyst** (Mary): Business analyst - research, specifications
- **@pm** (John): Product manager - PRDs, user needs
- **@sm** (Bob): Scrum master - story preparation, sprint planning
- **@tea** (Murat): Test architect - automated tests, CI/CD
- **@tech-writer** (Paige): Technical writer - documentation, guides
- **@ux-designer** (Sally): UX designer - user experience, UI
- **@quick-flow-solo-dev** (Barry): Full-stack rapid dev - quick implementations

---

## Directory Structure

```
_bmad/
├── core/                       # BMAD Core Platform
│   ├── agents/                 # Agent definitions (bmad-master.md, etc.)
│   ├── config.yaml             # Project configuration
│   ├── resources/              # Shared resources (Excalidraw, templates)
│   ├── tasks/                  # Core tasks
│   └── workflows/              # Core workflows (brainstorming, party-mode)
│
├── bmm/                        # BMM Module (Business Model Management)
│   ├── data/                   # PRDs, user stories, epics, specs
│   │   ├── documentation-standards.md
│   │   ├── epics/              # Epic definitions
│   │   ├── prds/               # Product requirement documents
│   │   └── user-stories/       # Detailed user stories
│   └── workflows/              # BMM-specific workflows
│       ├── 1-analysis/         # Analysis phase workflows
│       ├── 2-plan-workflows/   # Planning workflows
│       ├── 3-design/           # Design workflows
│       └── excalidraw-diagrams/ # Diagram creation workflows
│
├── _config/                    # Configuration files
│   ├── agent-manifest.csv      # Agent registry
│   ├── task-manifest.csv       # Task registry
│   └── workflow-manifest.csv   # Workflow registry
│
└── QUICKSTART.md               # BMAD getting started guide

_bmad-output/                   # Generated Artifacts
├── EPIC-3-*.md                 # EPIC-3 (Raster-Vector Integration) docs
├── EPIC-4-*.md                 # EPIC-4 (Raster Export) docs
├── STORY-*.md                  # User story specifications
├── PLAN-*.md                   # Planning documents
├── ARCHITECTURE-*.md           # Architecture documentation
├── TRANSLATION-AUDIT-*.md      # Translation audits
└── implementation-artifacts/   # Code generation artifacts
```

---

## Key Workflows

### Core Workflows (_bmad/core/workflows/)

#### 1. Brainstorming
- **Location:** `_bmad/core/workflows/brainstorming/workflow.md`
- **Purpose:** Generate ideas, explore solutions
- **Usage:** `@bmad-master charge le workflow brainstorming`

#### 2. Party Mode
- **Location:** `_bmad/core/workflows/party-mode/workflow.md`
- **Purpose:** Multi-agent collaborative discussion
- **Usage:** `@bmad-master PM` or `@bmad-master party mode`
- **Agents:** All agents participate in roundtable discussion

### BMM Workflows (_bmad/bmm/workflows/)

#### Analysis Phase (1-analysis/)
- **Research**: Market research, competitor analysis
- **Discovery**: User needs, pain points

#### Planning Phase (2-plan-workflows/)
- **Create PRD**: Product requirements document
- **Create User Stories**: Detailed user stories with acceptance criteria
- **Create UX Design**: Wireframes, mockups

#### Design Phase (3-design/)
- **Architecture**: System design, component diagrams
- **Database**: Schema design, migrations

#### Diagram Workflows (excalidraw-diagrams/)
- **Create Diagram**: General diagrams
- **Create Flowchart**: Process flowcharts
- **Create Wireframe**: UI wireframes
- **Create Dataflow**: Data flow diagrams

---

## Recent Artifacts (v5.4.0)

### EPIC-3: Raster-Vector Filter Integration

| Document | Purpose | Date |
|----------|---------|------|
| `EPIC-3-UI-SPECIFICATION.md` | Complete UI specification | Jan 2026 |
| `EPIC-3-USER-STORIES-DETAILED.md` | Detailed user stories | Jan 2026 |
| `EPIC-3-IMPLEMENTATION-PROGRESS.md` | Implementation tracking | Jan 2026 |
| `EPIC-3-RASTER-FILTER-UI-AUDIT.md` | UI audit and recommendations | Jan 2026 |
| `EPIC-3-UI-WIREFRAMES.md` | UI wireframes and mockups | Jan 2026 |
| `STORY-RASTER-EXPLORING-TOOLS-BUTTONS.md` | Raster tools button spec | Feb 1, 2026 |

### EPIC-4: Raster Export (Planned)

| Document | Purpose | Date |
|----------|---------|------|
| `EPIC-4-RASTER-EXPORT-USER-STORIES.md` | Raster export user stories | Jan 2026 |

### Translation & Quality

| Document | Purpose | Date |
|----------|---------|------|
| `TRANSLATION-AUDIT-20260201-COMPLETE.md` | Complete translation audit | Feb 1, 2026 |
| `PLAN-v5.0-MAJOR-UPDATE.md` | v5.0+ roadmap | Jan 2026 |

### Architecture

| Document | Purpose | Date |
|----------|---------|------|
| `ARCHITECTURE-UNIFIED-FILTER-SYSTEM.md` | Unified filter architecture | Jan 2026 |

---

## Agent Usage Patterns

### For Feature Development

```
# 1. Start with PM for PRD
@pm créer un PRD pour [feature name]

# 2. Convert to user stories with SM
@sm créer les user stories depuis le PRD

# 3. Architecture review
@architect réviser l'architecture pour [feature]

# 4. Implementation
@dev implémenter la story [reference]

# 5. Testing
@tea créer les tests pour [feature]

# 6. Documentation
@tech-writer documenter [feature]
```

### For Quick Changes

```
# Rapid development without ceremony
@quick-flow-solo-dev implémenter [quick feature]
```

### For Design Work

```
# UX design
@ux-designer créer les wireframes pour [feature]

# Technical diagrams
@analyst créer le diagramme de flux pour [process]
```

### For Analysis

```
# Research and analysis
@analyst analyser [topic]

# Brainstorming
@bmad-master charge le workflow brainstorming
```

---

## Documentation Standards

Location: `_bmad/bmm/data/documentation-standards.md`

### Document Types

1. **PRDs** (Product Requirements)
   - Problem statement
   - Target users
   - Success metrics
   - Requirements
   - Constraints

2. **User Stories**
   - As a [user]...
   - I want [feature]...
   - So that [benefit]...
   - Acceptance criteria
   - Story points

3. **Epics**
   - Epic overview
   - Related stories
   - Timeline
   - Dependencies

4. **Architecture Docs**
   - System overview
   - Component diagrams
   - Design patterns
   - Technology choices

5. **Implementation Artifacts**
   - Code specifications
   - API contracts
   - Database schemas
   - Deployment guides

---

## Current Status (Feb 1, 2026)

### Active Epics

| Epic | Status | Progress |
|------|--------|----------|
| EPIC-3: Raster-Vector Integration | ✅ Complete | v5.4.0 released |
| EPIC-4: Raster Export | 📋 Planning | User stories defined |

### Recent Workflow Executions

| Workflow | Date | Output |
|----------|------|--------|
| Create User Story | Feb 1, 2026 | STORY-RASTER-EXPLORING-TOOLS-BUTTONS.md |
| Translation Audit | Feb 1, 2026 | TRANSLATION-AUDIT-20260201-COMPLETE.md |
| Architecture Review | Jan 2026 | ARCHITECTURE-UNIFIED-FILTER-SYSTEM.md |

---

## Integration with Development

### Workflow

1. **Planning** (BMAD) → User stories, PRDs, specs
2. **Design** (BMAD + Excalidraw) → Wireframes, diagrams
3. **Implementation** (Code) → Following specs from BMAD
4. **Testing** (pytest) → Based on acceptance criteria
5. **Documentation** (BMAD) → User guides, technical docs
6. **Release** → CHANGELOG.md updated from BMAD artifacts

### Traceability

```
PRD (BMAD) 
  → Epic (BMAD) 
    → User Stories (BMAD) 
      → Implementation (Code) 
        → Tests (pytest) 
          → Documentation (BMAD)
            → Release Notes (CHANGELOG.md)
```

---

## Best Practices

### When to Use BMAD

✅ **DO use BMAD for:**
- Feature planning and requirements
- User story creation
- Architecture decisions
- Documentation generation
- Design artifacts (wireframes, diagrams)
- Translation planning
- Release planning

❌ **DON'T use BMAD for:**
- Direct code implementation (use @dev agent instead)
- Debugging (use standard debugging tools)
- Performance profiling (use profilers)
- Database queries (use QGIS/SQL tools)

### Communication Language

- **Agent communication**: French (as per config)
- **Documentation output**: English (as per config)
- **Code comments**: English
- **Commit messages**: English

---

## Quick Reference

### Load BMAD Master

```
# Auto-loaded when in bmad-master mode
# Manual activation if needed:
@bmad-master
```

### Common Commands

```
# List available tasks
@bmad-master LT

# List available workflows
@bmad-master LW

# Start party mode
@bmad-master PM

# Chat with agent
@bmad-master CH
```

### File Locations

| Item | Location |
|------|----------|
| Config | `_bmad/core/config.yaml` |
| Agents | `_bmad/core/agents/*.md` |
| Workflows | `_bmad/core/workflows/` + `_bmad/bmm/workflows/` |
| Output | `_bmad-output/` |
| User Stories | `_bmad/bmm/data/user-stories/` |
| PRDs | `_bmad/bmm/data/prds/` |

---

## Future Improvements

### Planned for v5.5
- [ ] Automated user story → test case generation
- [ ] CI/CD integration with BMAD artifacts
- [ ] Automated release notes from BMAD docs

### Planned for v6.0
- [ ] BMAD plugin for QGIS (in-app access)
- [ ] Automated PRD → code generation pipeline
- [ ] Integration with GitHub Projects

---

**Last Review:** February 1, 2026  
**Next Review:** March 1, 2026  
**BMAD Coordinator:** Simon (@sducournau)
