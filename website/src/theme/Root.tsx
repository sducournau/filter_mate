import React from 'react';

// Custom Root wrapper to add skip navigation link
export default function Root({children}: {children: React.ReactNode}) {
  return (
    <>
      <a href="#__docusaurus" className="skip-to-content">
        Skip to main content
      </a>
      {children}
    </>
  );
}
