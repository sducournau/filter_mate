#!/usr/bin/env python3
"""
Fix .md extensions in Markdown links for Docusaurus i18n compatibility.
Docusaurus requires links without .md extension in i18n translated files.
"""

import re
import os
from pathlib import Path

def fix_md_extensions(content, file_path):
    """
    Remove .md extensions from Markdown links.
    
    Converts:
    - [text](../path/file.md) -> [text](../path/file)
    - [text](./file.md#anchor) -> [text](./file#anchor)
    
    Args:
        content: File content as string
        file_path: Path to the file being processed
        
    Returns:
        Fixed content with .md extensions removed
    """
    changes = []
    
    # Pattern to match markdown links with .md extension
    # [text](path.md) or [text](path.md#anchor)
    pattern = r'\[([^\]]+)\]\(([^)]+)\.md(#[^)]+)?\)'
    
    def replace_link(match):
        link_text = match.group(1)
        link_path = match.group(2)
        anchor = match.group(3) if match.group(3) else ''
        
        # Skip external links
        if link_path.startswith('http://') or link_path.startswith('https://'):
            return match.group(0)
        
        # Reconstruct link without .md
        new_link = f'[{link_text}]({link_path}{anchor})'
        
        changes.append({
            'old': match.group(0),
            'new': new_link
        })
        
        return new_link
    
    new_content = re.sub(pattern, replace_link, content)
    
    if changes:
        print(f"\n📝 {file_path}")
        print(f"   Fixed {len(changes)} link(s):")
        for change in changes[:5]:  # Show first 5 changes
            print(f"   - {change['old']} → {change['new']}")
        if len(changes) > 5:
            print(f"   ... and {len(changes) - 5} more")
    
    return new_content, len(changes) > 0


def process_directory(directory_path, dry_run=False):
    """
    Process all .md files in directory recursively.
    
    Args:
        directory_path: Path to directory to process
        dry_run: If True, only show what would be changed
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        'files_processed': 0,
        'files_modified': 0,
        'total_changes': 0
    }
    
    directory = Path(directory_path)
    
    # Find all .md files
    md_files = list(directory.rglob('*.md'))
    
    print(f"\n🔍 Found {len(md_files)} Markdown files")
    print(f"{'[DRY RUN] ' if dry_run else ''}Processing...\n")
    
    for md_file in md_files:
        stats['files_processed'] += 1
        
        try:
            # Read file
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix links
            new_content, has_changes = fix_md_extensions(content, md_file.relative_to(directory))
            
            if has_changes:
                stats['files_modified'] += 1
                stats['total_changes'] += content.count('.md') - new_content.count('.md')
                
                # Write back if not dry run
                if not dry_run:
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
        
        except Exception as e:
            print(f"❌ Error processing {md_file}: {e}")
    
    return stats


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix .md extensions in Docusaurus i18n Markdown links'
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='i18n',
        help='Directory to process (default: i18n)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    args = parser.parse_args()
    
    # Get script directory
    script_dir = Path(__file__).parent
    target_dir = script_dir / args.directory
    
    if not target_dir.exists():
        print(f"❌ Directory not found: {target_dir}")
        return 1
    
    print(f"🚀 Processing Markdown files in: {target_dir}")
    
    # Process files
    stats = process_directory(target_dir, dry_run=args.dry_run)
    
    # Print summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(f"Files processed:  {stats['files_processed']}")
    print(f"Files modified:   {stats['files_modified']}")
    print(f"Total changes:    {stats['total_changes']}")
    
    if args.dry_run:
        print("\n⚠️  DRY RUN - No files were modified")
        print("Run without --dry-run to apply changes")
    else:
        print("\n✅ All changes applied successfully!")
    
    return 0


if __name__ == '__main__':
    exit(main())
