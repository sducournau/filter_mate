# FilterMate Documentation - Quick Reference

## 🚀 Quick Start

### Test Locally
```bash
cd website
npm start
```
Visit: http://localhost:3000

### Build for Production
```bash
cd website
npm run build
npm run serve
```

### Deploy
```bash
git add .
git commit -m "docs: Update documentation"
git push origin main
```
GitHub Actions deploys automatically to: https://sducournau.github.io/filter_mate/

---

## ✅ What's New (December 9, 2025)

### Accessibility Features
- ✅ Skip navigation (Tab on page load)
- ✅ Enhanced focus indicators (3px outline)
- ✅ WCAG AA color contrast (4.5:1+)
- ✅ Descriptive alt text for all images
- ✅ Table of contents on all pages
- ✅ Breadcrumb navigation
- ✅ "Edit this page" links
- ✅ Comprehensive accessibility statement

### Navigation Improvements
- ✅ Collapsible sidebar
- ✅ Last updated timestamps
- ✅ Announcement bar
- ✅ Better heading hierarchy

---

## 📂 Key Files

### Configuration
- `docusaurus.config.ts` - Main config (metadata, theme, navbar)
- `sidebars.ts` - Navigation structure
- `src/css/custom.css` - Styles (300+ lines, accessibility)

### Components
- `src/theme/Root.tsx` - Skip navigation wrapper
- `src/pages/index.tsx` - Homepage

### Documentation
- `docs/` - All content pages
- `docs/accessibility.md` - Accessibility statement
- `static/` - Images, icons, assets

### Guides
- `IMPLEMENTATION_SUMMARY.md` - Complete overview
- `ACCESSIBILITY_IMPLEMENTATION.md` - Technical details
- `ALGOLIA_SETUP.md` - Search configuration
- `STATUS.md` - Current status

---

## 🎨 Customization

### Change Colors
Edit `src/css/custom.css`:
```css
:root {
  --ifm-color-primary: #1a7f5a;  /* Your brand color */
  --ifm-link-color: #0066cc;
}
```

### Update Logo
Replace:
- `static/img/logo.png` - Navbar logo
- `static/img/favicon.ico` - Browser icon

### Add Pages
1. Create `docs/your-page.md`
2. Add to `sidebars.ts`
3. Build and test

---

## 🧪 Testing

### Accessibility
```bash
# Install tools
npm install -D @axe-core/cli pa11y-ci

# Run tests
npm run build
npm run serve &
npx axe http://localhost:3000
npx pa11y-ci http://localhost:3000
```

### Manual Checks
- [ ] Tab through page (keyboard only)
- [ ] Press Tab → Skip link appears
- [ ] Test dark mode toggle
- [ ] Zoom to 200% (Ctrl/Cmd + +)
- [ ] Read with screen reader

---

## 🔍 Search Setup

### Option 1: Algolia DocSearch (Recommended)
1. Apply: https://docsearch.algolia.com/apply/
2. Wait 1-2 weeks for approval
3. Add config to `docusaurus.config.ts`
4. See `ALGOLIA_SETUP.md` for details

### Option 2: Local Search
```bash
npm install @easyops-cn/docusaurus-search-local
```
Add to `docusaurus.config.ts` themes.

---

## 📊 Metrics to Monitor

### Lighthouse Scores (Target)
- Accessibility: ≥95
- Performance: ≥85
- Best Practices: ≥90
- SEO: ≥90

### Run Lighthouse
1. Build: `npm run build && npm run serve`
2. Open Chrome DevTools (F12)
3. Lighthouse tab → Generate report

---

## 🐛 Troubleshooting

### Build Fails
```bash
# Clear cache
npm run clear
npm run build
```

### CSS Not Updating
```bash
# Hard reload
Ctrl+Shift+R (Windows/Linux)
Cmd+Shift+R (macOS)
```

### Search Not Working
- Wait 24h after first deploy
- Check Algolia dashboard
- Verify sitemap.xml accessible

---

## 📚 Common Tasks

### Add New Doc Page
```markdown
---
sidebar_position: 5
title: My Page
description: Page description for SEO
keywords: [qgis, filter, keyword]
---

# My Page

Content here...

:::tip Pro Tip
Use admonitions for important info!
:::
```

### Update Homepage
Edit `src/pages/index.tsx`

### Change Footer
Edit `docusaurus.config.ts` → `themeConfig.footer`

---

## 🎯 Best Practices

### Writing Docs
- ✅ Use headings (h2-h4) for TOC
- ✅ Add descriptive alt text to images
- ✅ Use admonitions (tip, warning, note)
- ✅ Include code examples
- ✅ Link to related pages

### Accessibility
- ✅ Descriptive link text (not "click here")
- ✅ Alt text describes content, not "image of"
- ✅ Proper heading hierarchy (don't skip levels)
- ✅ High contrast colors (4.5:1+)
- ✅ Keyboard navigable

### Performance
- ✅ Optimize images (TinyPNG)
- ✅ Use lazy loading for videos
- ✅ Keep pages under 500KB
- ✅ Minimize dependencies

---

## 🔗 Useful Links

- **Live Site**: https://sducournau.github.io/filter_mate/
- **GitHub**: https://github.com/sducournau/filter_mate
- **Issues**: https://github.com/sducournau/filter_mate/issues
- **Docusaurus Docs**: https://docusaurus.io/docs
- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/

---

## 💬 Get Help

**Questions?**
- Check existing docs
- Search GitHub Issues
- Open new issue with `documentation` label

**Contributing?**
- Fork the repo
- Create feature branch
- Submit pull request
- Follow existing patterns

---

## ✨ Quick Tips

1. **Test locally first**: `npm start` before committing
2. **Check builds**: Verify `npm run build` succeeds
3. **Use admonitions**: Make important info stand out
4. **Link internally**: Help users discover content
5. **Update STATUS.md**: Keep roadmap current

---

**Last Updated**: December 9, 2025  
**Docusaurus Version**: 3.6.0  
**Node Version**: ≥20.0 required
