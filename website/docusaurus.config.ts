import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'FilterMate',
  tagline: 'Advanced QGIS filtering and export plugin',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://sducournau.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  baseUrl: '/filter_mate/',

  // GitHub pages deployment config.
  organizationName: 'sducournau',
  projectName: 'filter_mate',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'fr', 'pt'],
    localeConfigs: {
      en: {
        label: 'English',
        direction: 'ltr',
        htmlLang: 'en-US',
        calendar: 'gregory',
        path: 'en',
      },
      fr: {
        label: 'Français',
        direction: 'ltr',
        htmlLang: 'fr-FR',
        calendar: 'gregory',
        path: 'fr',
      },
      pt: {
        label: 'Português',
        direction: 'ltr',
        htmlLang: 'pt-BR',
        calendar: 'gregory',
        path: 'pt',
      },
    },
  },

  // Accessibility and SEO metadata
  headTags: [
    {
      tagName: 'meta',
      attributes: {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1.0',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'description',
        content: 'Accessible QGIS plugin documentation for FilterMate - Advanced filtering and export capabilities',
      },
    },
    {
      tagName: 'meta',
      attributes: {
        name: 'keywords',
        content: 'QGIS, plugin, filtering, GIS, spatial, accessibility, FilterMate',
      },
    },
  ],

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/sducournau/filter_mate/edit/main/website/',
          showLastUpdateAuthor: true,
          showLastUpdateTime: true,
          breadcrumbs: true,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    announcementBar: {
      id: 'accessibility',
      content: '♿ FilterMate documentation strives for WCAG 2.1 AA compliance. <a href="/filter_mate/docs/accessibility">Learn more</a>',
      backgroundColor: '#20232a',
      textColor: '#fff',
      isCloseable: true,
    },
    navbar: {
      title: 'FilterMate',
      logo: {
        alt: 'FilterMate plugin logo - funnel icon with map layers representing advanced QGIS filtering capabilities',
        src: 'img/logo.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
        {
          href: 'https://github.com/sducournau/filter_mate',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Getting Started',
              to: '/docs/installation',
            },
            {
              label: 'User Guide',
              to: '/docs/user-guide/introduction',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/sducournau/filter_mate',
            },
            {
              label: 'Issues',
              href: 'https://github.com/sducournau/filter_mate/issues',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'QGIS Plugin Repository',
              href: 'https://plugins.qgis.org/plugins/filter_mate',
            },
            {
              label: 'Accessibility',
              to: '/docs/accessibility',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} FilterMate. Built with Docusaurus.`,
    },
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 4,
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash'],
    },
    colorMode: {
      defaultMode: 'light',
      respectPrefersColorScheme: true,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
