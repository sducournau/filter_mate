#!/usr/bin/env python3
"""
Fix Markdown links in Docusaurus documentation.
Adds ./ prefix to same-level links to ensure proper resolution during build.
"""

import re
import os
from pathlib import Path

def fix_markdown_links(content, file_path):
    """
    Fix Markdown links by adding ./ prefix to same-level links.
    
    Args:
        content: File content as string
        file_path: Path to the file being processed
        
    Returns:
        Fixed content with updated links
    """
    changes = []
    
    # Pattern to match markdown links: [text](url)
    # Captures same-level links like: [text](file.md) or [text](file.md#anchor)
    # Should NOT match:
    # - Links starting with ./ or ../
    # - Links starting with http:// or https://
    # - Links starting with /
    # - Links starting with #
    
    def replace_link(match):
        full_match = match.group(0)
        link_text = match.group(1)
        link_url = match.group(2)
        
        # Skip if already has ./ or ../
        if link_url.startswith('./') or link_url.startswith('../'):
            return full_match
        
        # Skip if is http/https URL
        if link_url.startswith('http://') or link_url.startswith('https://'):
            return full_match
        
        # Skip if is absolute path
        if link_url.startswith('/'):
            return full_match
        
        # Skip if is anchor only
        if link_url.startswith('#'):
            return full_match
        
        # Check if it's a same-level .md file (no / in path before any #)
        url_base = link_url.split('#')[0]
        if '/' not in url_base and url_base.endswith('.md'):
            # This is a same-level link that needs ./ prefix
            new_link = f'[{link_text}](./{link_url})'
            changes.append(f"  {link_url} -> ./{link_url}")
            return new_link
        
        return full_match
    
    # Regex pattern for markdown links
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    fixed_content = re.sub(link_pattern, replace_link, content)
    
    if changes:
        print(f"\n{file_path}:")
        for change in changes:
            print(change)
    
    return fixed_content

def process_directory(directory):
    """
    Process all Markdown files in a directory recursively.
    
    Args:
        directory: Path to directory to process
    """
    docs_path = Path(directory)
    markdown_files = list(docs_path.rglob('*.md'))
    
    print(f"Found {len(markdown_files)} Markdown files to process")
    
    total_files_changed = 0
    
    for file_path in markdown_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        fixed_content = fix_markdown_links(original_content, file_path)
        
        if fixed_content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            total_files_changed += 1
    
    print(f"\n✓ Fixed links in {total_files_changed} files")

if __name__ == '__main__':
    # Process English docs
    docs_en = Path(__file__).parent / 'docs'
    print("=== Processing English documentation ===")
    process_directory(docs_en)
    
    # Process French translations
    docs_fr = Path(__file__).parent / 'i18n' / 'fr' / 'docusaurus-plugin-content-docs' / 'current'
    if docs_fr.exists():
        print("\n=== Processing French documentation ===")
        process_directory(docs_fr)
    
    # Process Portuguese translations
    docs_pt = Path(__file__).parent / 'i18n' / 'pt' / 'docusaurus-plugin-content-docs' / 'current'
    if docs_pt.exists():
        print("\n=== Processing Portuguese documentation ===")
        process_directory(docs_pt)
    
    print("\n✓ All links fixed!")
