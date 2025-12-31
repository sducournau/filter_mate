import clsx from "clsx";
import Link from "@docusaurus/Link";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import Layout from "@theme/Layout";
import Heading from "@theme/Heading";

import styles from "./index.module.css";

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <header className={clsx("hero hero--primary", styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link
            className="button button--secondary button--lg"
            to="/docs/installation"
          >
            Get Started - 5min ⏱️
          </Link>
          <Link
            className="button button--outline button--lg"
            to="/docs/getting-started/quick-start"
            style={{ marginLeft: "10px" }}
          >
            Quick Start Tutorial
          </Link>
        </div>
      </div>
    </header>
  );
}

function Feature({ title, description, icon }) {
  return (
    <div className={clsx("col col--4")}>
      <div className="text--center" style={{ fontSize: "3rem" }}>
        {icon}
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

function HomepageFeatures() {
  const features = [
    {
      title: "🚀 Fast Performance",
      description:
        "Multi-backend architecture with PostgreSQL, Spatialite, and OGR support. Up to 50× faster on large datasets.",
      icon: "⚡",
    },
    {
      title: "🔍 Intuitive Filtering",
      description:
        "Combine attribute and geometric filters with spatial predicates and buffer operations. Easy-to-use interface.",
      icon: "🎯",
    },
    {
      title: "🌍 Universal Compatibility",
      description:
        "Works with ANY data source: PostgreSQL, Spatialite, Shapefile, GeoPackage, and more. Automatic CRS reprojection.",
      icon: "🗺️",
    },
    {
      title: "📝 Filter History",
      description:
        "Full undo/redo support. Never lose your work. Review and restore previous filters with one click.",
      icon: "⏮️",
    },
    {
      title: "🎨 Adaptive UI",
      description:
        "Dynamic interface that adjusts to screen resolution. Theme synchronization with QGIS. Layer-specific widgets.",
      icon: "💎",
    },
    {
      title: "📤 Smart Export",
      description:
        "Export filtered features to GeoPackage, Shapefile, PostGIS, and more. Customizable CRS and options.",
      icon: "💾",
    },
  ];

  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {features.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}

function VideoSection() {
  return (
    <section className={styles.videoSection}>
      <div className="container">
        <div className="text--center">
          <Heading as="h2">See FilterMate in Action</Heading>
          <p>Watch our 5-minute demo to see how easy filtering can be</p>
          <div className={styles.videoWrapper}>
            <iframe
              src="https://www.youtube-nocookie.com/embed/2gOEPrdl2Bo?rel=0&modestbranding=1"
              title="FilterMate Demo - Complete Walkthrough"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              loading="lazy"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function WhyFilterMate() {
  return (
    <section className={styles.whySection}>
      <div className="container">
        <div className="text--center margin-bottom--lg">
          <Heading as="h2">Why FilterMate?</Heading>
        </div>
        <div className="row">
          <div className="col col--6">
            <Heading as="h3">🎯 Production-Ready</Heading>
            <ul>
              <li>Robust error handling and recovery</li>
              <li>Automatic geometry repair</li>
              <li>SQLite lock retry mechanisms</li>
              <li>Comprehensive test coverage</li>
            </ul>
          </div>
          <div className="col col--6">
            <Heading as="h3">⚡ Performance-Optimized</Heading>
            <ul>
              <li>44.6× faster with R-tree indexes</li>
              <li>2.3× faster with predicate ordering</li>
              <li>5× faster geometry caching</li>
              <li>Intelligent backend selection</li>
            </ul>
          </div>
        </div>
        <div className="row margin-top--lg">
          <div className="col col--6">
            <Heading as="h3">🛠️ Developer-Friendly</Heading>
            <ul>
              <li>Clean architecture with factory pattern</li>
              <li>Comprehensive API documentation</li>
              <li>Easy to extend and customize</li>
              <li>Active development and support</li>
            </ul>
          </div>
          <div className="col col--6">
            <Heading as="h3">📚 Well-Documented</Heading>
            <ul>
              <li>Step-by-step tutorials</li>
              <li>Complete API reference</li>
              <li>Performance comparison guides</li>
              <li>Troubleshooting documentation</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title} - Advanced QGIS Filtering`}
      description="FilterMate is a production-ready QGIS plugin for advanced filtering and export. Multi-backend support with PostgreSQL, Spatialite, and OGR."
    >
      <HomepageHeader />
      <main>
        <HomepageFeatures />
        <VideoSection />
        <WhyFilterMate />
      </main>
    </Layout>
  );
}
