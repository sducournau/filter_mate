# FilterMate Documentation Website

This directory contains the Docusaurus-based documentation website for FilterMate.

## 🌐 Live Site

Visit the documentation at: **https://sducournau.github.io/filter_mate/**

*Last updated: December 7, 2025*

## 🚀 Quick Start

### Prerequisites

- Node.js ≥ 20.0
- npm or yarn

### Installation

```bash
cd website
npm install
```

### Local Development

```bash
npm start
```

This command starts a local development server and opens a browser window. Most changes are reflected live without restarting the server.

### Build

```bash
npm run build
```

This command generates static content into the `build` directory and can be served using any static contents hosting service.

### Deployment

The documentation is automatically deployed to GitHub Pages when changes are pushed to the `main` branch (via GitHub Actions).

To deploy manually:

```bash
GIT_USER=sducournau npm run deploy
```

## 📁 Structure

```
website/
├── docs/                  # Documentation pages (Markdown)
│   ├── intro.md
│   ├── installation.md
│   ├── getting-started/
│   ├── user-guide/
│   ├── backends/
│   ├── advanced/
│   ├── developer-guide/
│   ├── api/
│   └── themes/
├── src/
│   ├── components/        # React components
│   ├── css/              # Custom CSS
│   └── pages/            # Custom pages
├── static/
│   └── img/              # Images and assets
├── docusaurus.config.ts  # Site configuration
├── sidebars.ts           # Sidebar configuration
└── package.json
```

## 📝 Writing Documentation

### Adding a New Page

1. Create a Markdown file in the appropriate `docs/` subdirectory
2. Add frontmatter:
   ```markdown
   ---
   sidebar_position: 1
   ---
   
   # Page Title
   
   Content here...
   ```
3. The page will automatically appear in the sidebar

### Using Docusaurus Components

#### Tabs

```mdx
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
  <TabItem value="option1" label="Option 1" default>
    Content for option 1
  </TabItem>
  <TabItem value="option2" label="Option 2">
    Content for option 2
  </TabItem>
</Tabs>
```

#### Admonitions

```markdown
:::tip
This is a tip
:::

:::info
This is informational
:::

:::warning
This is a warning
:::

:::danger
This is dangerous!
:::
```

#### Code Blocks

````markdown
```python title="example.py"
def hello():
    print("Hello, world!")
```
````

## 🎨 Customization

### Styling

Edit `src/css/custom.css` to customize colors and styles.

### Configuration

Edit `docusaurus.config.ts` to change:
- Site title and tagline
- Navigation items
- Footer links
- Theme settings

### Sidebar

Edit `sidebars.ts` to change documentation structure.

## 🔧 Troubleshooting

### Build fails

```bash
# Clear cache and rebuild
npm run clear
npm run build
```

### Node version too old

Docusaurus 3 requires Node.js ≥ 20.0. Check your version:

```bash
node --version
```

If needed, upgrade Node.js or use [nvm](https://github.com/nvm-sh/nvm):

```bash
nvm install 20
nvm use 20
```

### Port already in use

```bash
# Start on a different port
npm start -- --port 3001
```

## 📚 Resources

- [Docusaurus Documentation](https://docusaurus.io/docs)
- [Markdown Features](https://docusaurus.io/docs/markdown-features)
- [Docusaurus GitHub](https://github.com/facebook/docusaurus)

## 🤝 Contributing

When contributing to the documentation:

1. Follow the existing structure
2. Use clear, concise language
3. Add code examples where appropriate
4. Test locally before committing
5. Ensure all links work

## 📄 License

Same as FilterMate project (see root LICENSE file).
