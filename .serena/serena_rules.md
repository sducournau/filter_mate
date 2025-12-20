# Serena Integration Rules for GitHub Copilot Chat

## Project Status

**FilterMate v2.3.8** - Production QGIS Plugin
- ✅ All core phases complete (1-7)
- 🔄 Current: Test coverage improvement (70% → 80%)
- 📚 BMAD docs: `.bmad-core/`
- 🔧 Serena memories: `.serena/memories/` (19 files)

## Documentation System

### BMAD Documents (Project Methodology)
| Document | Purpose |
|----------|---------|
| `.bmad-core/prd.md` | Product requirements |
| `.bmad-core/epics.md` | User stories (23 stories) |
| `.bmad-core/architecture.md` | Technical architecture |
| `.bmad-core/roadmap.md` | Development phases |
| `.bmad-core/quality.md` | Quality standards |

### Serena Memories (Technical Context)
| Memory | Purpose |
|--------|---------|
| `project_overview` | Current status |
| `architecture_overview` | System architecture |
| `backend_architecture` | Multi-backend details |
| `bmad_integration` | BMAD-Serena mapping |

## Auto-Activation Rules

When GitHub Copilot Chat is invoked in this workspace, Serena symbolic tools should be preferred for code analysis tasks.

## Context Priority

1. **Primary Context** (always loaded):
   - `.github/copilot-instructions.md` - Coding guidelines and patterns
   - `.serena/project_memory.md` - Complete project architecture
   - `.serena/optimization_rules.md` - Serena efficiency rules
   - `.bmad-core/README.md` - BMAD documentation index

2. **Secondary Context** (loaded on demand):
   - `README.md` - Project overview
   - `.bmad-core/prd.md` - Requirements
   - `.bmad-core/epics.md` - User stories
   - Serena memories as needed

## Trigger Patterns

Copilot should use Serena tools when user asks about:

### Code Navigation
- "où est défini..." / "where is defined..."
- "trouve la fonction..." / "find the function..."
- "montre-moi la classe..." / "show me the class..."
- "quelles méthodes a..." / "what methods does..."

**Action**: Use `get_symbols_overview()` and `find_symbol()`

### Code Understanding
- "comment fonctionne..." / "how does... work..."
- "que fait cette fonction..." / "what does this function do..."
- "explique la logique de..." / "explain the logic of..."

**Action**: Use `find_symbol(include_body=True)`

### Impact Analysis
- "où est utilisé..." / "where is... used..."
- "qui appelle..." / "who calls..."
- "find references to..."

**Action**: Use `find_referencing_symbols()`

### Search & Discovery
- "trouve tous les..." / "find all..."
- "cherche les occurrences de..." / "search for occurrences of..."
- "liste les fonctions qui..." / "list functions that..."

**Action**: Use `search_for_pattern()` with appropriate filters

### Code Modification
- "modifie la fonction..." / "modify the function..."
- "ajoute une méthode..." / "add a method..."
- "change l'implémentation..." / "change the implementation..."

**Action**: 
1. First: `find_symbol()` to read current code
2. Then: `find_referencing_symbols()` to check impact
3. Finally: `replace_symbol_body()` or `insert_after_symbol()`

## Efficiency Rules (CRITICAL)

### ✅ DO THIS

```python
# Step 1: Overview first
get_symbols_overview("modules/appTasks.py")

# Step 2: Find symbol structure
find_symbol(
    "FilterTask",
    relative_path="modules/appTasks.py",
    depth=1,
    include_body=False
)

# Step 3: Read only needed method
find_symbol(
    "FilterTask/execute_geometric_filtering",
    relative_path="modules/appTasks.py",
    include_body=True
)
```

**Token usage**: ~1,000 tokens

### ❌ NEVER DO THIS

```python
# Reading entire 2080-line file
read_file("modules/appTasks.py", 1, 2080)
```

**Token usage**: ~50,000 tokens (50x worse!)

## Project-Specific Patterns

### Pattern 1: Check PostgreSQL Availability

Before suggesting any PostgreSQL code:

```python
# Always check this first
search_for_pattern(
    "POSTGRESQL_AVAILABLE",
    relative_path="modules/appUtils.py"
)
```

### Pattern 2: Find Provider-Specific Code

```python
# Search for backend-specific implementations
search_for_pattern(
    "provider.*==.*'(postgresql|spatialite|ogr)'",
    relative_path="modules/",
    restrict_search_to_code_files=True
)
```

### Pattern 3: Locate Materialized Views (Phase 2 Target)

```python
# Find all PostgreSQL-specific optimizations
search_for_pattern(
    "CREATE MATERIALIZED VIEW",
    context_lines_before=3,
    context_lines_after=3
)
```

### Pattern 4: Analyze Task Structure

```python
# Understand FilterTask architecture
find_symbol(
    "FilterTask",
    relative_path="modules/appTasks.py",
    depth=2,  # Get class + methods + nested
    include_body=False
)
```

## Response Templates

### When User Asks About Code Location

```
Looking for `{symbol_name}`...

[Use get_symbols_overview() or find_symbol()]

Found in `{file_path}`:
- Class/Function: `{symbol_name}`
- Line range: {start}-{end}
- Purpose: {brief_description}

[Show relevant code snippet]
```

### When User Asks to Modify Code

```
Analyzing `{symbol_name}` for modification...

[Use find_symbol() to read current code]

Current implementation: [summary]

[Use find_referencing_symbols()]

Used in {N} places:
- {reference_1}
- {reference_2}

Proposed change: [description]

[Use replace_symbol_body() or insert_after_symbol()]

Modified successfully. Impacts:
- {impact_1}
- {impact_2}
```

### When User Asks About Architecture

```
Analyzing project structure...

[Use get_symbols_overview() on key files]

Key components:
1. **{component_1}**: {purpose}
2. **{component_2}**: {purpose}

Dependencies:
- {dependency_map}

[Reference project_memory.md for details]
```

## Multi-Language Support

### French Triggers
- "où se trouve" → use `find_symbol()`
- "cherche" / "trouve" → use `search_for_pattern()`
- "modifie" / "change" → read then `replace_symbol_body()`
- "ajoute" → use `insert_after_symbol()`
- "qui utilise" → use `find_referencing_symbols()`

### English Triggers
- "where is" / "find" → use `find_symbol()`
- "search for" → use `search_for_pattern()`
- "modify" / "change" → read then `replace_symbol_body()`
- "add" → use `insert_after_symbol()`
- "who uses" / "references" → use `find_referencing_symbols()`

## Phase-Aware Responses

### Phase 1 (Complete)
If user asks about PostgreSQL optional support:
- ✅ Confirm implementation complete
- Show POSTGRESQL_AVAILABLE flag usage
- Reference test_phase1_optional_postgresql.py

### Phase 2 (In Progress)
If user asks about Spatialite backend:
- 🔄 Confirm in progress
- Show what needs to be implemented:
  - `create_temp_spatialite_table()`
  - `qgis_expression_to_spatialite()`
  - Conditional branches in `execute_geometric_filtering()`
- Reference .serena/optimization_rules.md Phase 2 roadmap

### Phase 3-5 (Planned)
If user asks about future phases:
- 📋 Refer to TODO.md
- Explain dependencies on Phase 2 completion

## Memory Management

### When to Create New Memory

Create specialized memory when:
- Implementing complex new feature (e.g., Spatialite backend)
- Documenting performance benchmarks
- Recording architectural decisions

```python
write_memory(
    memory_file_name="spatialite_implementation.md",
    content="..."
)
```

### When to Update Existing Memory

Update `project_memory.md` when:
- Phase transitions (e.g., Phase 2 → Phase 3)
- Major architectural changes
- New critical symbols added

## Error Handling

### If Serena Tool Fails

Fallback strategy:
1. Try with more specific parameters (e.g., add `relative_path`)
2. If still fails, use traditional tools (`read_file`, `grep_search`)
3. Document why Serena approach didn't work

### If Symbol Not Found

```python
# First try: Exact match
find_symbol("function_name")

# Second try: Substring matching
find_symbol("function", substring_matching=True)

# Third try: Pattern search
search_for_pattern("def.*function.*:")
```

## Performance Monitoring

Track token efficiency:
- **Optimal**: <2,000 tokens per query
- **Acceptable**: 2,000-5,000 tokens
- **Review needed**: >5,000 tokens

If consistently using >5,000 tokens:
1. Check if using `read_file()` instead of `find_symbol()`
2. Verify `relative_path` parameter usage
3. Consider splitting query into smaller steps

## Integration Checklist

When Copilot Chat starts:
- ✅ Load `.github/copilot-instructions.md`
- ✅ Load `.serena/project_memory.md`
- ✅ Load `.serena/optimization_rules.md`
- ✅ Display welcome message with phase status
- ✅ Enable Serena tools for code analysis
- ✅ Set efficiency mode (prefer symbolic tools)

## Quick Command Reference

```python
# Overview
get_symbols_overview("path/to/file.py")

# Find
find_symbol("SymbolName", relative_path="path/", include_body=True)

# Search
search_for_pattern("pattern", relative_path="path/", restrict_search_to_code_files=True)

# References
find_referencing_symbols("symbol_name", relative_path="path/to/file.py")

# Edit
replace_symbol_body("SymbolName", relative_path="path/", body="new code")
insert_after_symbol("SymbolName", relative_path="path/", body="new code")

# Memory
write_memory("memory_name.md", "content")
read_memory("memory_name.md")
```

---

**Auto-loaded by**: GitHub Copilot Chat  
**Project**: FilterMate QGIS Plugin  
**Serena Version**: Compatible with Oraios Serena MCP  
**Last Updated**: 2 December 2025
