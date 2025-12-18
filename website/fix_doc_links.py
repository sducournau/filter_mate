#!/usr/bin/env python3
"""
Fix broken links in i18n documentation by removing ./ prefix
When intro.md has slug: /, links like ./installation should be just 'installation'
"""

import re
from pathlib import Path

def fix_relative_links(content):
    """Remove ./ prefix from relative links"""
    # Pattern: [text](./path) or [text](./path#anchor)
    # Replace with: [text](path) or [text](path#anchor)
    pattern = r'\[([^\]]+)\]\(\.\/([^\)]+)\)'
    return re.sub(pattern, r'[\1](\2)', content)

def process_file(file_path):
    """Process a single markdown file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    content = fix_relative_links(content)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all broken links in fr and pt translations"""
    website_dir = Path(__file__).parent
    i18n_dir = website_dir / 'i18n'
    
    print("🔧 Fixing broken links in i18n documentation...\n")
    
    files_fixed = []
    
    for locale in ['fr', 'pt']:
        docs_dir = i18n_dir / locale / 'docusaurus-plugin-content-docs' / 'current'
        
        if not docs_dir.exists():
            print(f"⚠️  {locale}: docs directory not found")
            continue
        
        print(f"📁 Processing {locale} locale...")
        
        # Process all .md files
        for md_file in docs_dir.rglob('*.md'):
            if process_file(md_file):
                rel_path = md_file.relative_to(docs_dir)
                files_fixed.append(f"{locale}/{rel_path}")
                print(f"  ✓ {rel_path}")
    
    print(f"\n✅ Complete! Fixed {len(files_fixed)} files\n")
    
    if files_fixed:
        print("Fixed files:")
        for f in files_fixed[:10]:  # Show first 10
            print(f"  - {f}")
        if len(files_fixed) > 10:
            print(f"  ... and {len(files_fixed) - 10} more")
        
        print("\n📝 Next: Run 'npm run build' to verify fixes")
    else:
        print("ℹ️  No files needed fixing")

if __name__ == '__main__':
    main()
