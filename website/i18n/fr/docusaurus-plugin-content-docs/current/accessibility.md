---
sidebar_position: 100
title: Accessibility Statement
description: FilterMate documentation accessibility commitment and compliance information
keywords: [accessibility, WCAG, screen reader, keyboard navigation, a11y]
---

# Accessibility Statement

**Last Updated**: December 9, 2025

FilterMate documentation is committed to ensuring digital accessibility for all users, including those using assistive technologies. We strive to meet or exceed the Web Content Accessibility Guidelines (WCAG) 2.1 Level AA standards.

## Our Commitment

We believe that everyone should have equal access to information about FilterMate, regardless of ability or the technology they use. Accessibility is an ongoing effort, and we continuously work to improve the user experience for all visitors.

## Conformance Status

**WCAG 2.1 Level AA**: Partially Conformant

This means that some parts of the content do not fully conform to the WCAG 2.1 Level AA standard, but we are actively working to achieve full conformance.

## Accessibility Features

### ✅ Keyboard Navigation
- All interactive elements are accessible via keyboard
- Tab order follows a logical sequence
- Focus indicators are clearly visible
- Skip navigation link provided for quick access to main content

### ✅ Screen Reader Compatibility
- Semantic HTML5 structure with proper landmarks
- ARIA labels where appropriate
- Descriptive alt text for all informational images
- Heading hierarchy follows logical structure (h1 → h2 → h3)

### ✅ Visual Accessibility
- **Color Contrast**: Minimum 4.5:1 ratio for normal text (WCAG AA)
- **Text Resize**: Content readable at 200% zoom without loss of functionality
- **Focus Indicators**: 3px outline with 2px offset on all interactive elements
- **Font Size**: Base font size of 16px for improved readability
- **Line Height**: 1.65 line-height for comfortable reading

### ✅ Responsive Design
- Mobile-friendly layouts
- Touch targets minimum 44x44 pixels
- Adapts to different screen sizes and orientations

### ✅ Content Structure
- Clear headings and landmarks
- Table of contents for long pages
- Breadcrumb navigation
- Consistent navigation patterns

### ✅ Media
- Code blocks with syntax highlighting
- Diagrams include text alternatives
- Videos include captions (when available)

### ✅ Motion & Animation
- Respects `prefers-reduced-motion` setting
- No flashing content above 3Hz
- Animations can be disabled via browser settings

## Known Limitations

We are aware of the following accessibility limitations and are working to address them:

### 🔨 In Progress
- **Video Captions**: Some embedded videos may lack captions
- **PDF Accessibility**: Exported PDFs need accessibility tagging
- **Code Example Alternatives**: Text descriptions for complex code samples

### 📋 Planned Improvements
- Enhanced screen reader announcements for dynamic content
- Additional keyboard shortcuts documentation
- Improved color palette for colorblind users
- Live region announcements for AJAX updates

## Testing Methodology

Our accessibility testing includes:

- **Automated Testing**: 
  - axe-core DevTools
  - pa11y-ci
  - Lighthouse Accessibility Audit
  
- **Manual Testing**:
  - Keyboard-only navigation
  - Screen reader testing (NVDA, JAWS, VoiceOver)
  - Color contrast analysis
  - Browser zoom testing (up to 200%)
  
- **Real User Testing**:
  - Feedback from users with disabilities
  - Assistive technology user groups

## Browser & Assistive Technology Support

This documentation has been tested with:

### Browsers
- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

### Screen Readers
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS/iOS)
- TalkBack (Android)

### Keyboard Navigation
All features accessible via keyboard in supported browsers

## Feedback & Complaints

We welcome feedback on the accessibility of FilterMate documentation. If you encounter accessibility barriers, please let us know:

### Report an Issue
- **GitHub Issues**: [github.com/sducournau/filter_mate/issues](https://github.com/sducournau/filter_mate/issues)
- **Label**: Use the `accessibility` label
- **Information to Include**:
  - URL of the page
  - Description of the problem
  - Browser and assistive technology used
  - Steps to reproduce

### Response Timeline
We aim to respond to accessibility feedback within:
- Critical issues: 2 business days
- Important issues: 1 week
- Minor issues: 2 weeks

## Technical Specifications

FilterMate documentation accessibility relies on the following technologies:

- **HTML5**: Semantic markup
- **CSS3**: Responsive and accessible styling
- **JavaScript**: Progressive enhancement (site works without JS)
- **React**: Component-based architecture
- **Docusaurus**: Documentation framework

## Accessibility Standards

We reference the following standards and guidelines:

- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/) (Web Content Accessibility Guidelines)
- [Section 508](https://www.section508.gov/) (U.S. Rehabilitation Act)
- [ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/) (Accessible Rich Internet Applications)
- [ATAG 2.0](https://www.w3.org/WAI/standards-guidelines/atag/) (Authoring Tool Accessibility Guidelines)

## Third-Party Content

Some content on this site may come from third-party sources (e.g., embedded videos, external links). We strive to ensure third-party content is accessible but cannot guarantee full control over external resources.

## Continuous Improvement

Accessibility is an ongoing commitment. Our roadmap includes:

### Short Term (Next 3 Months)
- Complete alt text audit for all images
- Add captions to all tutorial videos
- Implement feedback widget on all pages
- Conduct comprehensive screen reader testing

### Medium Term (3-6 Months)
- Achieve full WCAG 2.1 AA compliance
- Add keyboard shortcuts documentation
- Implement live region announcements
- Enhance color contrast for all UI elements

### Long Term (6-12 Months)
- Target WCAG 2.1 AAA compliance where feasible
- Multilingual accessibility features
- Advanced assistive technology support
- Regular accessibility audits (quarterly)

## Resources

### For Users
- [WebAIM: Introduction to Web Accessibility](https://webaim.org/intro/)
- [NVDA Screen Reader](https://www.nvaccess.org/download/)
- [Color Contrast Checker](https://webaim.org/resources/contrastchecker/)

### For Developers
- [ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
- [Accessible Components Library](https://www.a11yproject.com/)
- [WebAIM Quick Reference](https://webaim.org/resources/quickref/)

## Legal Information

This accessibility statement applies to the FilterMate documentation website hosted at [https://sducournau.github.io/filter_mate/](https://sducournau.github.io/filter_mate/).

For questions about the plugin itself, please refer to the main [QGIS Plugin Repository](https://plugins.qgis.org/plugins/filter_mate/).

---

**Note**: This statement was created on December 9, 2025, and will be reviewed and updated quarterly to reflect our ongoing accessibility improvements.

:::tip Help Us Improve
Your feedback helps us make FilterMate documentation more accessible. If you use assistive technology and have suggestions, please [open an issue](https://github.com/sducournau/filter_mate/issues/new?labels=accessibility).
:::
