# FilterMate Documentation - Internationalization Setup

## ✅ Implemented

The FilterMate documentation now supports **3 languages**:
- 🇬🇧 **English** (default) - `en`
- 🇫🇷 **French** - `fr`
- 🇵🇹 **Portuguese** (Brazilian) - `pt`

### What's Been Completed

1. **Configuration** ✅
   - Updated `docusaurus.config.ts` with `fr` and `pt` locales
   - Added language selector dropdown in navbar
   - Configured locale-specific metadata (labels, directions, HTML lang)

2. **Translation Infrastructure** ✅
   - Generated translation JSON files using Docusaurus CLI
   - Created `i18n/fr/` and `i18n/pt/` directory structure
   - Set up `docusaurus-plugin-content-docs` JSON files

3. **UI Translations** ✅
   - **Navbar**: Translated navigation items and logo alt text
   - **Footer**: Translated all footer links and copyright
   - **Theme elements**: Generated code.json with 82 UI string translations

4. **Core Documentation** ✅
   - Translated `intro.md` (homepage) to French and Portuguese
   - Both translations are complete and ready for use

## 📋 Next Steps for Full Translation

### Directory Structure for Translations

All translated markdown files should be placed in:
- **French**: `i18n/fr/docusaurus-plugin-content-docs/current/`
- **Portuguese**: `i18n/pt/docusaurus-plugin-content-docs/current/`

The directory structure should mirror the English `docs/` folder:

```
i18n/
├── fr/
│   ├── code.json                        # UI strings (auto-generated) ✅
│   ├── docusaurus-theme-classic/
│   │   ├── navbar.json                  # ✅ Translated
│   │   └── footer.json                  # ✅ Translated
│   └── docusaurus-plugin-content-docs/
│       ├── current.json                 # Sidebar labels (auto-generated)
│       └── current/
│           ├── intro.md                 # ✅ Translated
│           ├── installation.md          # ⚠️ TODO
│           ├── changelog.md             # ⚠️ TODO
│           ├── accessibility.md         # ⚠️ TODO
│           ├── getting-started/
│           │   ├── index.md             # ⚠️ TODO
│           │   ├── quick-start.md       # ⚠️ TODO
│           │   ├── first-filter.md      # ⚠️ TODO
│           │   └── why-filtermate.md    # ⚠️ TODO
│           ├── user-guide/              # ⚠️ TODO (8 files)
│           ├── workflows/               # ⚠️ TODO (6 files)
│           ├── backends/                # ⚠️ TODO (6 files)
│           ├── advanced/                # ⚠️ TODO (3 files)
│           ├── reference/               # ⚠️ TODO (2+ files)
│           └── developer-guide/         # ⚠️ TODO (6 files)
└── pt/                                  # Same structure as fr/
```

### Priority Translation Order

Translate documents in this order for maximum user impact:

#### Phase 1: Essential User Docs (High Priority)
1. `installation.md` - Installation guide
2. `getting-started/quick-start.md` - Quick start tutorial
3. `getting-started/first-filter.md` - First filter example
4. `user-guide/introduction.md` - User guide intro
5. `user-guide/interface-overview.md` - UI overview
6. `user-guide/filtering-basics.md` - Basic filtering

#### Phase 2: Core Features (Medium Priority)
7. `user-guide/geometric-filtering.md` - Geometric operations
8. `user-guide/buffer-operations.md` - Buffer operations
9. `user-guide/export-features.md` - Export functionality
10. `user-guide/filter-history.md` - History management
11. `backends/overview.md` - Backend overview
12. `backends/choosing-backend.md` - Backend selection

#### Phase 3: Advanced & Reference (Lower Priority)
13. All `workflows/*.md` - Real-world examples
14. `backends/postgresql.md`, `spatialite.md`, `ogr.md` - Backend details
15. `advanced/configuration.md` - Configuration options
16. `reference/glossary.md` - Terminology
17. `developer-guide/*` - Developer documentation

### Translation Commands

#### Generate Translation Template Files
```bash
# French
npm run write-translations -- --locale fr

# Portuguese
npm run write-translations -- --locale pt
```

#### Build with All Locales
```bash
# Build all languages
npm run build

# Build and serve locally to test
npm run build && npm run serve
```

#### Start Development Server (Specific Locale)
```bash
# French
npm run start -- --locale fr

# Portuguese
npm run start -- --locale pt

# All locales
npm run start
```

### Translation Guidelines

1. **Preserve Markdown Structure**: Keep all frontmatter, headings, links, and code blocks intact
2. **Technical Terms**: Some terms like "FilterMate", "QGIS", "PostgreSQL" remain in English
3. **Code Examples**: Do NOT translate code, SQL queries, or command-line examples
4. **Links**: Keep relative links as-is (e.g., `./installation.md`)
5. **Emojis**: Keep all emojis - they're universal! 🎉
6. **Version Numbers**: Keep version numbers in English format (e.g., "v2.2.5")

### Sidebar Translation

The sidebar labels are automatically translated via `i18n/[locale]/docusaurus-plugin-content-docs/current.json`. 

To customize sidebar labels:
```bash
npm run write-translations -- --locale fr
# Edit i18n/fr/docusaurus-plugin-content-docs/current.json
```

## 🔧 Configuration Reference

### Current i18n Configuration

```typescript
// docusaurus.config.ts
i18n: {
  defaultLocale: 'en',
  locales: ['en', 'fr', 'pt'],
  localeConfigs: {
    en: {
      label: 'English',
      direction: 'ltr',
      htmlLang: 'en-US',
    },
    fr: {
      label: 'Français',
      direction: 'ltr',
      htmlLang: 'fr-FR',
    },
    pt: {
      label: 'Português',
      direction: 'ltr',
      htmlLang: 'pt-BR',
    },
  },
}
```

### Locale Dropdown

The language selector is automatically added to the navbar:
```typescript
// docusaurus.config.ts - navbar items
{
  type: 'localeDropdown',
  position: 'right',
}
```

## 🌐 Deployment

### GitHub Pages Deployment

When deploying to GitHub Pages, all locales will be built:
```bash
npm run build
# Results in:
# - build/index.html (English - default)
# - build/fr/ (French)
# - build/pt/ (Portuguese)
```

Then deploy:
```bash
npm run deploy
```

### URL Structure

- English (default): `https://sducournau.github.io/filter_mate/docs/intro`
- French: `https://sducournau.github.io/filter_mate/fr/docs/intro`
- Portuguese: `https://sducournau.github.io/filter_mate/pt/docs/intro`

## 🤝 Contributing Translations

To contribute translations:

1. **Choose a document** from the priority list above
2. **Copy from English**: `docs/[path]/[file].md`
3. **Translate to target locale**: `i18n/[locale]/docusaurus-plugin-content-docs/current/[path]/[file].md`
4. **Preserve structure**: Keep all Markdown formatting, code, and links
5. **Test locally**: `npm run start -- --locale [locale]`
6. **Submit PR**: Commit and push your translation

### Translation Checklist

- [ ] Frontmatter preserved (sidebar_position, slug, etc.)
- [ ] All headings translated
- [ ] Body text translated (excluding code)
- [ ] Links kept as relative paths
- [ ] Code blocks unchanged
- [ ] Technical terms appropriately handled
- [ ] Emojis preserved
- [ ] Tested locally

## 📊 Translation Progress

### Current Status

| Language | Code | Progress | Files Translated |
|----------|------|----------|------------------|
| English  | `en` | 100% ✅  | 80+ (source)     |
| French   | `fr` | ~2% 🔄   | 1/80+ (intro.md) |
| Portuguese | `pt` | ~2% 🔄 | 1/80+ (intro.md) |

### Quick Stats

- **Total Documentation Files**: ~80 markdown files
- **Fully Translated**: 1 file per locale (intro.md)
- **UI Elements**: 100% translated (navbar, footer, theme)
- **Estimated Work**: 79 files remaining per locale

## 🚀 Quick Start for Translators

```bash
# 1. Install dependencies
npm install

# 2. Start dev server with French locale
npm run start -- --locale fr

# 3. Edit translation files in:
#    i18n/fr/docusaurus-plugin-content-docs/current/

# 4. Save and check browser (hot reload)

# 5. Build to verify no broken links
npm run build
```

## 📚 Resources

- [Docusaurus i18n Documentation](https://docusaurus.io/docs/i18n/introduction)
- [Docusaurus Translation Tutorial](https://docusaurus.io/docs/i18n/tutorial)
- [QGIS Translation Guidelines](https://docs.qgis.org/latest/en/docs/developers_guide/translating.html)

## ❓ FAQ

### Why are some links broken in French/Portuguese?

Links will show as broken until the target files are translated. This is expected. Docusaurus validates all internal links during build.

### Can I use machine translation?

While machine translation (DeepL, Google Translate) can provide a starting point, **human review is essential** for:
- Technical accuracy
- Natural language flow
- QGIS-specific terminology
- Cultural appropriateness

### How do I translate images/screenshots?

Currently, images are shared across all locales. If locale-specific images are needed:
1. Add to `i18n/[locale]/docusaurus-plugin-content-docs/current/[path]/`
2. Reference with relative path in translated markdown

### What about the blog?

FilterMate documentation doesn't use the blog feature (`blog: false` in config).

## 🎯 Goal

**Target**: Full translation of all user-facing documentation (Priority Phases 1-2) by Q1 2026.

---

**Last Updated**: December 9, 2024  
**Docusaurus Version**: 3.6.0  
**Maintained By**: FilterMate Documentation Team
