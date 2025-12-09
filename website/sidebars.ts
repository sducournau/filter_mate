import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    'intro',
    'installation',
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      items: [
        'getting-started/index',
        'getting-started/quick-start',
        'getting-started/first-filter',
      ],
    },
    {
      type: 'category',
      label: 'User Guide',
      items: [
        'user-guide/introduction',
        'user-guide/interface-overview',
        'user-guide/filtering-basics',
        'user-guide/geometric-filtering',
        'user-guide/buffer-operations',
        'user-guide/export-features',
        'user-guide/filter-history',
      ],
    },
    {
      type: 'category',
      label: 'Backends',
      items: [
        'backends/overview',
        'backends/backend-selection',
        'backends/postgresql',
        'backends/spatialite',
        'backends/ogr',
        'backends/performance-comparison',
      ],
    },
    {
      type: 'category',
      label: 'Advanced',
      items: [
        'advanced/configuration',
        'advanced/performance-tuning',
        'advanced/troubleshooting',
      ],
    },
    {
      type: 'category',
      label: 'Developer Guide',
      items: [
        'developer-guide/architecture',
        'developer-guide/development-setup',
        'developer-guide/contributing',
        'developer-guide/code-style',
        'developer-guide/testing',
        'developer-guide/backend-development',
      ],
    },
    'changelog',
    'accessibility',
  ],
};

export default sidebars;
