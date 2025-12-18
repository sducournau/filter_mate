#!/usr/bin/env python3
"""
Fix broken links in i18n intro.md files that have slug: /
These files need absolute paths from /docs/ instead of relative paths.
"""

import os
import re
from pathlib import Path

def fix_intro_links(file_path, locale):
    """
    Fix links in intro.md that has slug: /
    
    Transforms:
    - [text](./installation.md) -> [text](/docs/installation)
    - [text](./getting-started/quick-start.md) -> [text](/docs/getting-started/quick-start)
    - [text](./backends/overview.md) -> [text](/docs/backends/overview)
    
    For non-English locales, it uses the locale prefix in the URL.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Check if this file has slug: /
    if 'slug: /' not in content:
        return False
    
    # Pattern to match relative links with optional .md extension
    # Matches: [text](./path) or [text](./path.md) or [text](./path/file.md)
    pattern = r'\[([^\]]+)\]\((\.\./?)([^\)]+?)(\.md)?(\)|#[^\)]*\))'
    
    def replacer(match):
        text = match.group(1)
        rel_prefix = match.group(2)  # ./ or ../
        path = match.group(3)
        md_ext = match.group(4)  # .md or None
        closing = match.group(5)  # ) or #anchor)
        
        # Only fix ./ links (same directory), not ../ links
        if rel_prefix == './':
            # Build absolute path based on locale
            if locale == 'en':
                abs_path = f'/docs/{path}'
            else:
                abs_path = f'/{locale}/docs/{path}'
            return f'[{text}]({abs_path}{closing}'
        else:
            # Keep ../ links as is
            return match.group(0)
    
    content = re.sub(pattern, replacer, content)
    
    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def fix_getting_started_index(file_path, locale):
    """
    Fix links in getting-started/index.md
    
    Transforms:
    - [text](./quick-start.md) -> [text](./quick-start)
    - [text](../installation.md) -> [text](../installation)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Simple pattern: remove .md from all relative links
    pattern = r'\((\.\./?)([^\)]+?)\.md(\)|#[^\)]*\))'
    
    def replacer(match):
        prefix = match.group(1)  # ./ or ../
        path = match.group(2)
        closing = match.group(3)  # ) or #anchor)
        return f'({prefix}{path}{closing}'
    
    content = re.sub(pattern, replacer, content)
    
    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def fix_workflows_index(file_path, locale):
    """
    Fix links in workflows/index.md - same as getting-started/index.md
    """
    return fix_getting_started_index(file_path, locale)

def main():
    """Process all problematic markdown files in i18n directories."""
    website_dir = Path(__file__).parent
    i18n_dir = website_dir / 'i18n'
    
    if not i18n_dir.exists():
        print(f"❌ i18n directory not found: {i18n_dir}")
        return
    
    print("🔍 Fixing broken links in i18n documentation...")
    
    locales = ['fr', 'pt']
    files_modified = 0
    
    for locale in locales:
        locale_docs = i18n_dir / locale / 'docusaurus-plugin-content-docs' / 'current'
        
        if not locale_docs.exists():
            print(f"⚠️  Skipping {locale}: directory not found")
            continue
        
        print(f"\n📁 Processing {locale} locale...")
        
        # Fix intro.md (has slug: /)
        intro_file = locale_docs / 'intro.md'
        if intro_file.exists():
            if fix_intro_links(intro_file, locale):
                files_modified += 1
                print(f"  ✓ Fixed: {locale}/intro.md")
        
        # Fix getting-started/index.md
        gs_index = locale_docs / 'getting-started' / 'index.md'
        if gs_index.exists():
            if fix_getting_started_index(gs_index, locale):
                files_modified += 1
                print(f"  ✓ Fixed: {locale}/getting-started/index.md")
        
        # Fix workflows/index.md
        wf_index = locale_docs / 'workflows' / 'index.md'
        if wf_index.exists():
            if fix_workflows_index(wf_index, locale):
                files_modified += 1
                print(f"  ✓ Fixed: {locale}/workflows/index.md")
        
        # Fix other files with .md extensions
        for md_file in locale_docs.rglob('*.md'):
            # Skip files we already processed
            if md_file.name in ['intro.md', 'index.md']:
                continue
            
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            
            # Remove .md from relative links
            pattern = r'\((\.\./?)([^\)]+?)\.md(\)|#[^\)]*\))'
            content = re.sub(pattern, r'(\1\2\3', content)
            
            if content != original:
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                files_modified += 1
                rel_path = md_file.relative_to(locale_docs)
                print(f"  ✓ Fixed: {locale}/{rel_path}")
    
    print(f"\n✅ Done! Modified {files_modified} files")
    
    if files_modified > 0:
        print("\n📝 Next steps:")
        print("   1. Review changes: git diff")
        print("   2. Test build: npm run build")
        print("   3. Commit: git commit -am 'fix: broken links in i18n documentation'")

if __name__ == '__main__':
    main()
