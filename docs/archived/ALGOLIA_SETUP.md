# Algolia DocSearch Setup Guide

Algolia DocSearch provides free search for open-source documentation. Here's how to set it up for FilterMate.

## Step 1: Apply for DocSearch

1. Visit: https://docsearch.algolia.com/apply/
2. Fill out the application form:

**Required Information:**
- **Website URL**: `https://sducournau.github.io/filter_mate/`
- **Repository URL**: `https://github.com/sducournau/filter_mate`
- **Email**: Your maintainer email
- **Description**: "FilterMate is an open-source QGIS plugin providing advanced filtering and export capabilities for vector data. We need search for our documentation site."

**Eligibility Requirements** (FilterMate meets all):
- ✅ Open source project (GPL-3.0 license)
- ✅ Publicly available documentation
- ✅ Owner/maintainer of the website
- ✅ Content is technical documentation (not a blog or marketing site)

## Step 2: Wait for Approval

**Timeline**: Usually 1-2 weeks

You'll receive an email from Algolia with:
- Application ID
- API Key
- Index Name

## Step 3: Configure Docusaurus

Once approved, update `docusaurus.config.ts`:

```typescript
themeConfig: {
  // ... existing config
  algolia: {
    // The application ID provided by Algolia
    appId: 'YOUR_APP_ID',

    // Public API key: it is safe to commit it
    apiKey: 'YOUR_SEARCH_API_KEY',

    // The index name provided by Algolia
    indexName: 'filter_mate',

    // Optional: See doc section below
    contextualSearch: true,

    // Optional: Specify domains where the navigation should occur through window.location instead on history.push
    externalUrlRegex: 'external\\.com|domain\\.com',

    // Optional: Replace parts of the item URLs from Algolia
    replaceSearchResultPathname: {
      from: '/docs/', // or as RegExp: /\/docs\//
      to: '/',
    },

    // Optional: Algolia search parameters
    searchParameters: {},

    // Optional: path for search page that enabled by default (`false` to disable it)
    searchPagePath: 'search',
  },
}
```

## Step 4: Verify Search

After deployment:

1. Visit your docs site
2. Press `Ctrl+K` or `/` to open search
3. Try searching for "filter", "export", "backend"
4. Verify results are accurate

## Alternative: DocSearch Scraper (Advanced)

If you want to self-host the crawler:

### Prerequisites
- Docker installed
- Algolia account (free tier)

### Steps

1. **Create Algolia Account**: https://www.algolia.com/users/sign_up

2. **Get API Keys**:
   - Application ID
   - Admin API Key
   - Search API Key

3. **Create `.env` file**:
```env
APPLICATION_ID=YOUR_APP_ID
API_KEY=YOUR_ADMIN_API_KEY
```

4. **Create `config.json`**:
```json
{
  "index_name": "filter_mate",
  "start_urls": ["https://sducournau.github.io/filter_mate/"],
  "sitemap_urls": ["https://sducournau.github.io/filter_mate/sitemap.xml"],
  "selectors": {
    "lvl0": {
      "selector": ".menu__link--sublist.menu__link--active",
      "global": true,
      "default_value": "Documentation"
    },
    "lvl1": "article h1",
    "lvl2": "article h2",
    "lvl3": "article h3",
    "lvl4": "article h4",
    "lvl5": "article h5",
    "text": "article p, article li"
  }
}
```

5. **Run Scraper**:
```bash
docker run -it --env-file=.env \
  -e "CONFIG=$(cat config.json | jq -r tostring)" \
  algolia/docsearch-scraper
```

6. **Schedule Regular Crawls** (Optional):
   - Set up GitHub Action
   - Run weekly or after deployments

## GitHub Action for Auto-Crawling (Optional)

Create `.github/workflows/algolia-scraper.yml`:

```yaml
name: Algolia DocSearch Scraper

on:
  # Run after successful deployment
  workflow_run:
    workflows: ["Deploy to GitHub Pages"]
    types:
      - completed
  # Or run on schedule
  schedule:
    - cron: '0 0 * * 0' # Weekly on Sunday

jobs:
  algolia-scraper:
    runs-on: ubuntu-latest
    steps:
      - name: Algolia DocSearch Scraper
        uses: algolia/docsearch-scraper-action@v1
        with:
          algolia_application_id: ${{ secrets.ALGOLIA_APP_ID }}
          algolia_api_key: ${{ secrets.ALGOLIA_API_KEY }}
          file: website/algolia-config.json
```

**Secrets to add** in GitHub repository settings:
- `ALGOLIA_APP_ID`
- `ALGOLIA_API_KEY` (Admin API Key, not Search Key)

## Testing Search

### Manual Testing
1. Build docs: `npm run build`
2. Serve locally: `npm run serve`
3. Press `Ctrl+K` or click search icon
4. Try various search terms
5. Verify results are relevant

### Search Quality Checklist
- [ ] All doc pages indexed
- [ ] Search results are relevant
- [ ] Headings appear in results
- [ ] Code snippets searchable
- [ ] Recent updates reflected (may take 24h)

## Troubleshooting

### Search Not Appearing
- Verify `algolia` config in `docusaurus.config.ts`
- Check browser console for errors
- Ensure API keys are correct

### Poor Search Results
- Wait 24 hours after initial indexing
- Adjust `searchParameters` in config
- Improve page titles and headings
- Add more descriptive content

### Index Not Updating
- Verify sitemap.xml is accessible
- Check Algolia dashboard for crawl status
- Re-run scraper manually
- Contact Algolia support

## Resources

- [Algolia DocSearch Docs](https://docsearch.algolia.com/docs/what-is-docsearch)
- [Docusaurus Search Guide](https://docusaurus.io/docs/search)
- [Algolia Dashboard](https://www.algolia.com/dashboard)
- [DocSearch GitHub](https://github.com/algolia/docsearch)

## Status

**Current**: Application not yet submitted  
**Next Step**: Apply at https://docsearch.algolia.com/apply/  
**ETA**: 1-2 weeks for approval

---

**Note**: This is a one-time setup. Once configured, search will update automatically with each deployment.
