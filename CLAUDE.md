# FilterMate — Claude Code Project Instructions

## Agent Routing Rules

### Default Agent: Marco (tech-lead-gis)
For ANY development task on FilterMate — coding, refactoring, bug fixing, code review, architecture decisions — **always delegate to the `tech-lead-gis` agent (Marco)** via the Task tool. This includes:
- Writing or modifying Python/PyQt5 code
- Plugin architecture decisions
- PostGIS/SpatiaLite queries
- Raster processing implementation
- Code review and audits
- Performance optimization
- Thread safety analysis

### Jordan (jordan-po)
Use Jordan for:
- Product scoping and feasibility analysis
- MVP definition and scope cutting
- User story writing and backlog prioritization
- Roadmap planning and sprint planning
- Formalizing ideas into actionable plans
- Go/No-Go decisions on features
- Decomposing epics into stories

### Atlas (atlas-tech-watch)
Use Atlas for:
- Technology watch and research (veille technologique)
- Tool comparisons and evaluations
- GIS ecosystem exploration (LiDAR, 3D, point clouds, remote sensing)
- Open data guidance (IGN, OSM, Copernicus)
- Strategic tech recommendations

### The Elder Scrolls (the-elder-scrolls)
Use The Elder Scrolls for:
- Memory management (archiving, consulting, curating)
- Cross-referencing project knowledge
- Auditing memory freshness and coherence
- Session result archival
- Project timeline reconstruction

### Beta (beta-tester)
Use Beta for:
- Testing features, edge cases, and shadow zones
- Finding bugs in uncovered code paths
- Acceptance testing for Jordan's stories
- Regression testing after Marco's fixes
- Risk analysis and test coverage mapping
- Bug reproduction and structured bug reports

### Steph (steph-cm)
Use Steph for:
- Discord server community management and engagement
- Release announcements and changelogs (user-facing)
- Tutorials, tips & tricks, use cases
- User feedback collection and synthesis
- Support responses and FAQ maintenance
- Publication planning and event communication

### Inter-Agent Relationships
```
Jordan (jordan-po) — Product Owner
  |-- directs --> Marco for implementation (stories, priorities, acceptance criteria)
  |-- asks --> Beta for acceptance testing before delivery
  |-- briefs --> Steph for communication priorities and release messaging
  |-- consults --> Atlas for market/tech landscape and benchmarks
  |-- consults --> Elder Scrolls for past product decisions
  |-- produces --> User stories, roadmap, MVP scopes, prioritized backlogs
  |
Marco (tech-lead-gis) — Lead Developer [DEFAULT for dev tasks]
  |-- reports to --> Jordan for scope clarification and acceptance validation
  |-- sends to --> Beta for testing after implementation or fix
  |-- briefs --> Steph for technical accuracy on tutorials and announcements
  |-- consults --> Atlas for tech recommendations and tool choices
  |-- consults --> Elder Scrolls for project history and past decisions
  |-- produces --> Code changes, audits, architecture docs, complexity estimates
  |
Beta (beta-tester) — QA Tester
  |-- reports bugs to --> Marco with structured reproduction steps
  |-- validates for --> Jordan with acceptance test results (Go/No-Go)
  |-- provides --> Steph with bug status for user support responses
  |-- consults --> Elder Scrolls for past bug history
  |-- produces --> Bug reports, risk maps, test results, shadow zone audits
  |
Steph (steph-cm) — Community Manager
  |-- consults --> Marco for technical accuracy verification
  |-- consults --> Jordan for messaging priorities and feature highlights
  |-- consults --> Atlas for trending topics and ecosystem context
  |-- consults --> Beta for bug status before user responses
  |-- archives via --> Elder Scrolls for community feedback persistence
  |-- produces --> Announcements, tutorials, FAQ, support responses, feedback reports
  |
Atlas (atlas-tech-watch) — Tech Intelligence
  |-- feeds --> Jordan with competitive/tech landscape for product decisions
  |-- feeds --> Marco with technology evaluations for implementation
  |-- feeds --> Steph with trending topics for community content
  |-- archives via --> Elder Scrolls for knowledge persistence
  |-- produces --> Watch reports, tool comparisons, KB entries
  |
Elder Scrolls (the-elder-scrolls) — Knowledge Guardian
  |-- serves --> Jordan with past product decisions and roadmap history
  |-- serves --> Marco with project context and past technical decisions
  |-- serves --> Beta with past bug history and known issues
  |-- serves --> Steph with feature history for storytelling
  |-- serves --> Atlas with historical tech watch data
  |-- maintains --> All project memories (Serena + auto-memory)
```

### Routing Decision Tree
1. Is the task about product scoping, MVP, stories, prioritization, or feasibility? → **Jordan**
2. Is the task about writing/modifying/reviewing code? → **Marco**
3. Is the task about testing, bugs, edge cases, or quality validation? → **Beta**
4. Is the task about community, tutorials, announcements, Discord, or user-facing content? → **Steph**
5. Is the task about technology research or evaluation? → **Atlas**
6. Is the task about project knowledge or memory management? → **Elder Scrolls**
7. Ambiguous dev task? → **Marco** (default)
8. Ambiguous product/planning task? → **Jordan**

## BMAD Integration

The project uses **BMAD v6.0** for structured workflows (slash commands `/bmad-*`). BMAD agents are interactive personas; our custom agents are autonomous subagents. They complement each other.

### BMAD Agent → Custom Agent Mapping

| BMAD Agent | Name | Maps to Custom Agent | Role Overlap |
|---|---|---|---|
| `gis-lead-dev` | Marco | **Marco (tech-lead-gis)** | Identical — GIS Lead Dev |
| `pm` | John | **Jordan (jordan-po)** | Product management, PRD, priorities |
| `analyst` | Mary | **Jordan** + **Atlas** | Requirements → Jordan, Research → Atlas |
| `qa` / `quinn` | Quinn | **Beta (beta-tester)** | QA, testing, bug reports |
| `dev` | Amelia | **Marco (tech-lead-gis)** | Implementation, story execution |
| `sm` | Bob | **Jordan (jordan-po)** | Sprint management, story prep |
| `architect` | Winston | **Marco (tech-lead-gis)** | Architecture decisions |
| `tech-writer` | Paige | **Steph (steph-cm)** + **Elder Scrolls** | User docs → Steph, Internal docs → Elder Scrolls |
| `ux-designer` | Sally | No direct mapping | UI/UX design |
| `quick-flow` | Barry | **Marco** (fast mode) | Rapid dev + spec |

### BMAD Workflow → Agent Routing

Use BMAD `/bmad-bmm-*` workflows for **structured processes**. Use custom agents for **autonomous execution**.

| BMAD Workflow | Phase | Route to Agent | When to use |
|---|---|---|---|
| `create-product-brief` | Analysis | Jordan | Formalizing a new idea |
| `domain-research` | Analysis | Atlas | Exploring a GIS/tech domain |
| `market-research` | Analysis | Atlas + Jordan | Competitive landscape |
| `technical-research` | Analysis | Atlas | Tech stack evaluation |
| `create-prd` | Planning | Jordan | Full PRD creation |
| `validate-prd` | Planning | Jordan | PRD quality check |
| `create-ux-design` | Planning | (Sally, no mapping) | UI/UX design |
| `create-architecture` | Solutioning | Marco | Architecture decisions |
| `create-epics-and-stories` | Solutioning | Jordan | Story decomposition |
| `check-implementation-readiness` | Solutioning | Jordan + Marco | Pre-implementation gate |
| `create-story` | Implementation | Jordan | Next story from backlog |
| `dev-story` | Implementation | Marco | Story implementation |
| `code-review` | Implementation | Marco | Adversarial code review |
| `sprint-planning` | Implementation | Jordan | Sprint setup |
| `sprint-status` | Implementation | Jordan | Sprint tracking |
| `retrospective` | Implementation | Jordan | Post-sprint review |
| `correct-course` | Implementation | Jordan + Marco | Mid-sprint pivot |
| `quick-spec` | Quick Flow | Jordan + Marco | Rapid spec creation |
| `quick-dev` | Quick Flow | Marco | Rapid implementation |
| `qa-automate` | QA | Beta | Test automation |
| `document-project` | Docs | Elder Scrolls | Project documentation |
| `generate-project-context` | Docs | Elder Scrolls | Context file generation |

### When to use BMAD vs Custom Agents

- **Use BMAD** when you need a **structured, step-by-step process** with templates (PRD, architecture, sprint planning)
- **Use custom agents** when you need **autonomous task execution** (write code, find bugs, research tech, manage memory)
- **Combine both**: Use Jordan to scope → BMAD `/bmad-bmm-create-story` to formalize → Marco to implement → Beta to test

## Project Context
- QGIS plugin, Python/PyQt5, hexagonal architecture
- Thread safety: QGIS layers are NOT thread-safe
- Signal safety: always blockSignals around programmatic setValue calls
- Dockwidget is ~7000 lines — use `_get_current_exploring_layer()` for current layer
