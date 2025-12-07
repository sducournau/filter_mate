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

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          // Please change this to your repo.
          editUrl:
            'https://github.com/sducournau/filter_mate/tree/main/website/',
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
    navbar: {
      title: 'FilterMate',
      logo: {
        alt: 'FilterMate Logo',
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
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} FilterMate. Built with Docusaurus.`,
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
