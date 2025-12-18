#!/usr/bin/env python3
"""
Fix broken links in i18n markdown files by removing .md extensions.
Docusaurus expects links without .md extensions.
"""

import os
import re
from pathlib import Path

def fix_markdown_links(file_path):
    """
    Remove .md extensions from markdown links in a file.
    
    Transforms:
    - [text](./file.md) -> [text](./file)
    - [text](../path/file.md) -> [text](../path/file)
    - [text](../path/file.md#anchor) -> [text](../path/file#anchor)
    
    Does NOT change:
    - External links (http://, https://)
    - Absolute paths starting with /
    - Links without .md extension
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match markdown links with .md extension
    # Matches: [text](./path.md) or [text](../path.md) but NOT [text](/path.md) or [text](http://...)
    pattern = r'\[([^\]]+)\]\((\.\.?/[^\)]+?)\.md(\)|#[^\)]*\))'
    
    # Replace .md with empty string before closing ) or before #
    def replacer(match):
        text = match.group(1)
        path = match.group(2)
        closing = match.group(3)
        return f'[{text}]({path}{closing}'
    
    content = re.sub(pattern, replacer, content)
    
    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Process all markdown files in i18n directories."""
    website_dir = Path(__file__).parent
    i18n_dir = website_dir / 'i18n'
    
    if not i18n_dir.exists():
        print(f"❌ i18n directory not found: {i18n_dir}")
        return
    
    print("🔍 Scanning for markdown files in i18n directories...")
    
    # Find all markdown files in fr and pt translations
    locales = ['fr', 'pt']
    files_processed = 0
    files_modified = 0
    
    for locale in locales:
        locale_docs = i18n_dir / locale / 'docusaurus-plugin-content-docs'
        
        if not locale_docs.exists():
            print(f"⚠️  Skipping {locale}: directory not found")
            continue
        
        print(f"\n📁 Processing {locale} locale...")
        
        for md_file in locale_docs.rglob('*.md'):
            files_processed += 1
            if fix_markdown_links(md_file):
                files_modified += 1
                rel_path = md_file.relative_to(i18n_dir)
                print(f"  ✓ Fixed: {rel_path}")
    
    print(f"\n✅ Done!")
    print(f"   Processed: {files_processed} files")
    print(f"   Modified:  {files_modified} files")
    
    if files_modified == 0:
        print("   ℹ️  No files needed changes")

if __name__ == '__main__':
    main()
