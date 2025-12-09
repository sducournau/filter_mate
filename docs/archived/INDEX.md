# FilterMate Documentation Index

**Version 2.2.5** | December 9, 2025

## 📚 Active Documentation

### Core Documentation
- **[architecture.md](architecture.md)** - Complete system architecture and component diagrams
- **[DEVELOPER_ONBOARDING.md](DEVELOPER_ONBOARDING.md)** - Developer onboarding guide and setup instructions
- **[BACKEND_API.md](BACKEND_API.md)** - Backend API reference and usage

### Feature Implementation
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Current implementation status and performance optimizations
- **[FILTER_HISTORY_INTEGRATION.md](FILTER_HISTORY_INTEGRATION.md)** - Filter history system documentation
- **[AUTO_CONFIGURATION.md](AUTO_CONFIGURATION.md)** - Auto-configuration system
- **[INTEGRATION.md](INTEGRATION.md)** - Integration guidelines
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Filter history & favorites implementation

### UI & Themes
- **[UI_SYSTEM_OVERVIEW.md](UI_SYSTEM_OVERVIEW.md)** - Complete UI system guide
- **[THEMES.md](THEMES.md)** - Theme system documentation
- **[COLOR_HARMONIZATION.md](COLOR_HARMONIZATION.md)** - Color harmonization & accessibility (v2.2.2+)
- **[UI_DYNAMIC_CONFIG.md](UI_DYNAMIC_CONFIG.md)** - Dynamic UI configuration
- **[UI_TESTING_GUIDE.md](UI_TESTING_GUIDE.md)** - UI testing procedures
- **[UI_STYLES_TESTING_CHECKLIST.md](UI_STYLES_TESTING_CHECKLIST.md)** - Styles testing checklist

### Configuration & JSON
- **[CONFIG_JSON_IMPROVEMENTS.md](CONFIG_JSON_IMPROVEMENTS.md)** - JSON configuration improvements
- **[CONFIG_JSON_REACTIVITY.md](CONFIG_JSON_REACTIVITY.md)** - Real-time configuration reactivity

### User Documentation
- **[USER_DOCUMENTATION_PLAN.md](USER_DOCUMENTATION_PLAN.md)** - User documentation plan and workflows

---

## 📦 Archived Documentation

Located in: `archived/`

### Completed Fixes (`archived/fixes/`)
- FIELD_SELECTION_FIX.md - QgsFieldExpressionWidget configuration fix
- SOURCE_TABLE_NAME_FIX.md - Source table name detection fix
- SQLITE_LOCK_FIX.md - SQLite database locking fix
- SQLITE_LOCK_FIX_VISUAL.md - Visual documentation of SQLite fix
- FIX_EXPLORING_MULTIPLE_SPACING.md - Multiple selection spacing fix
- FIX_EXPLORING_SPACING_HEIGHTS.md - Spacing heights fix
- FIX_EXPLORING_WIDGET_OVERLAP.md - Widget overlap fix

### Completed UI Improvements (`archived/ui-improvements/`)
- COMPACT_MODE_HARMONIZATION.md - Compact mode harmonization
- COMPACT_MODE_TEST_GUIDE.md - Compact mode testing guide
- UI_IMPROVEMENTS_README.md - UI improvements overview
- UI_IMPROVEMENTS_REPORT.md - UI improvements report
- UI_IMPROVEMENT_PLAN_2025.md - 2025 UI improvement plan
- UI_STYLES_REFACTORING.md - Styles refactoring documentation
- THEME_PREVIEW.md - Theme preview system

### Historical Planning (`archived/planning/`)
- UI_HARMONIZATION_PLAN.md - UI harmonization planning
- UI_HARDCODED_PARAMETERS_ANALYSIS.md - Hardcoded parameters analysis
- UI_DYNAMIC_PARAMETERS_ANALYSIS.md - Dynamic parameters analysis
- IMPLEMENTATION_DYNAMIC_DIMENSIONS.md - Dynamic dimensions implementation
- DEPLOYMENT_GUIDE_DYNAMIC_DIMENSIONS.md - Dynamic dimensions deployment
- next_teps.md - Historical Docusaurus planning (French)

### Website Deployment (`archived/website-deployment/`)
- DOCUSAURUS_IMPLEMENTATION.md - Docusaurus setup documentation
- QUICK_START_DEPLOY.md - Quick deployment guide

---

## 🌐 Website Documentation

Location: `website/docs/`

The user-facing documentation is built with Docusaurus and deployed to GitHub Pages:
- **URL**: https://sducournau.github.io/filter_mate/
- **Status**: website/DEVELOPMENT_STATUS.md
- **Deployment**: Automatic via GitHub Actions

### Main Sections
- **Getting Started**: Quick start, first filter tutorial
- **User Guide**: Interface, filtering, export, history
- **Backends**: PostgreSQL, Spatialite, OGR comparison
- **Advanced**: Configuration, performance tuning, troubleshooting
- **Developer Guide**: Architecture, contributing, code style

---

## 📝 How to Use This Index

### For Users
→ Start with **website documentation**: https://sducournau.github.io/filter_mate/

### For Developers
→ Read **[DEVELOPER_ONBOARDING.md](DEVELOPER_ONBOARDING.md)** first  
→ Then **[architecture.md](architecture.md)** for system understanding  
→ Refer to **[BACKEND_API.md](BACKEND_API.md)** for implementation details

### For Contributors
→ Check **[../CONTRIBUTING.md](../CONTRIBUTING.md)** for guidelines  
→ Review **[UI_SYSTEM_OVERVIEW.md](UI_SYSTEM_OVERVIEW.md)** for UI changes  
→ Follow **[../README.md](../README.md)** for setup instructions

---

## 🔄 Documentation Updates

**Last Major Update**: December 9, 2025
- Translated French documentation to English
- Consolidated duplicate content
- Updated website development status
- Moved outdated planning docs to archived/

**Maintenance**:
- Keep INDEX.md updated when adding new docs
- Move completed feature docs to archived/ when appropriate
- Update website/docs/ for user-facing changes
- Keep technical docs in /docs/ for developers
- **THEME_SYNC.md** - Theme synchronization (completed)

### Planning & Analysis Documents
Located in: `archived/planning/`

- **UI_HARMONIZATION_PLAN.md** - UI harmonization planning (completed)
- **UI_DYNAMIC_PARAMETERS_ANALYSIS.md** - Dynamic parameters analysis (completed)
- **UI_HARDCODED_PARAMETERS_ANALYSIS.md** - Hardcoded parameters analysis (completed)
- **DEPLOYMENT_GUIDE_DYNAMIC_DIMENSIONS.md** - Deployment guide for dynamic dimensions (completed)
- **IMPLEMENTATION_DYNAMIC_DIMENSIONS.md** - Dynamic dimensions implementation (completed)

---

## 📖 Documentation Guidelines

### When to Archive
Documents should be moved to `archived/` when:
- The feature/fix is fully implemented and stable
- The document is primarily historical or planning-focused
- The information is superseded by active documentation

### Active Document Standards
Active documents should:
- Be kept up-to-date with current implementation
- Include version information and last update date
- Reference archived documents when relevant
- Focus on current functionality and usage

### Archive Organization
- **fixes/** - Completed bug fixes and corrections
- **ui-improvements/** - Completed UI enhancements and refactorings
- **planning/** - Historical planning and analysis documents

---

## 🔍 Quick Reference

### For Developers
Start here:
1. [DEVELOPER_ONBOARDING.md](DEVELOPER_ONBOARDING.md)
2. [architecture.md](architecture.md)
3. [BACKEND_API.md](BACKEND_API.md)

### For Contributors
Start here:
1. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
2. [UI_TESTING_GUIDE.md](UI_TESTING_GUIDE.md)
3. GitHub Copilot Instructions: `../.github/copilot-instructions.md`

### For Theme Developers
Start here:
1. [UI System Overview](UI_SYSTEM_OVERVIEW.md)
2. [Themes](THEMES.md)
3. [UI Dynamic Config](UI_DYNAMIC_CONFIG.md)

---

**Last Updated:** December 7, 2025
