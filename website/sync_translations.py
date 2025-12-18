#!/usr/bin/env python3
"""
Sync missing files from English docs to translation folders.
"""

import os
import shutil
from pathlib import Path

def sync_translation_files(docs_root, i18n_root, locale):
    """
    Copy missing files from English docs to translation folder.
    
    Args:
        docs_root: Path to English docs
        i18n_root: Path to i18n folder
        locale: Language code (e.g., 'fr', 'pt')
    """
    locale_path = i18n_root / locale / 'docusaurus-plugin-content-docs' / 'current'
    
    if not locale_path.exists():
        print(f"Translation path does not exist: {locale_path}")
        return
    
    # Get all .md files in English docs
    en_files = set(p.relative_to(docs_root) for p in docs_root.rglob('*.md'))
    
    # Get all .md files in translation
    locale_files = set(p.relative_to(locale_path) for p in locale_path.rglob('*.md'))
    
    # Find missing files
    missing_files = en_files - locale_files
    
    if not missing_files:
        print(f"✓ [{locale.upper()}] All files are translated")
        return
    
    print(f"\n[{locale.upper()}] Found {len(missing_files)} missing files:")
    
    for rel_path in sorted(missing_files):
        src_file = docs_root / rel_path
        dst_file = locale_path / rel_path
        
        # Create parent directory if needed
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        shutil.copy2(src_file, dst_file)
        print(f"  ✓ Copied: {rel_path}")
    
    print(f"✓ [{locale.upper()}] Synced {len(missing_files)} files")

if __name__ == '__main__':
    website_root = Path(__file__).parent
    docs_root = website_root / 'docs'
    i18n_root = website_root / 'i18n'
    
    print("=== Syncing translation files ===\n")
    
    # Sync French
    if (i18n_root / 'fr').exists():
        sync_translation_files(docs_root, i18n_root, 'fr')
    
    # Sync Portuguese
    if (i18n_root / 'pt').exists():
        sync_translation_files(docs_root, i18n_root, 'pt')
    
    print("\n✓ All translations synced!")
