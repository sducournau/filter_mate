#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Logging Standardization Tool
=======================================

Automatically standardizes logging statements in FilterMate backends.
Applies [Backend] prefixes and enriches context.

Usage:
    python tools/auto_standardize_logging.py --backend spatialite
    python tools/auto_standardize_logging.py --all
    python tools/auto_standardize_logging.py --dry-run
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Backend-specific prefixes
BACKEND_PREFIXES = {
    'postgresql': '[PostgreSQL]',
    'spatialite': '[Spatialite]',
    'ogr': '[OGR]'
}

# Patterns to detect and transform
PATTERNS = [
    # Simple info logs without prefix
    (
        r'logger\.info\(f?"([^"]*?)"\)',
        lambda backend, msg: f'logger.info(f"{BACKEND_PREFIXES[backend]} {msg}")'
    ),
    # Debug logs without prefix
    (
        r'logger\.debug\(f?"([^"]*?)"\)',
        lambda backend, msg: f'logger.debug(f"{BACKEND_PREFIXES[backend]} {msg}")'
    ),
    # Warning logs without prefix
    (
        r'logger\.warning\(f?"([^"]*?)"\)',
        lambda backend, msg: f'logger.warning(f"{BACKEND_PREFIXES[backend]} {msg}")'
    ),
    # Error logs without prefix
    (
        r'logger\.error\(f?"([^"]*?)"\)',
        lambda backend, msg: f'logger.error(f"{BACKEND_PREFIXES[backend]} {msg}")'
    ),
]


def should_skip_line(line: str, backend: str) -> bool:
    """Check if line already has backend prefix."""
    prefix = BACKEND_PREFIXES[backend]
    return prefix in line


def standardize_file(file_path: Path, backend: str, dry_run: bool = False) -> Dict:
    """
    Standardize logging in a single file.
    
    Returns dict with statistics.
    """
    stats = {
        'total_logs': 0,
        'standardized': 0,
        'skipped': 0,
        'changes': []
    }
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    modified = False
    
    for line_num, line in enumerate(lines, 1):
        new_line = line
        
        # Check if line has a logger statement
        if re.search(r'logger\.(debug|info|warning|error)', line):
            stats['total_logs'] += 1
            
            # Skip if already has prefix
            if should_skip_line(line, backend):
                stats['skipped'] += 1
            else:
                # Try to standardize
                for pattern, transform in PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        # Extract message
                        msg = match.group(1)
                        
                        # Skip very complex f-strings (manual review needed)
                        if msg.count('{') > 5:
                            break
                        
                        # Apply transformation
                        new_log = transform(backend, msg)
                        new_line = re.sub(pattern, new_log, line)
                        
                        if new_line != line:
                            stats['standardized'] += 1
                            stats['changes'].append({
                                'line': line_num,
                                'old': line.strip(),
                                'new': new_line.strip()
                            })
                            modified = True
                        break
        
        new_lines.append(new_line)
    
    # Write back if not dry run and modified
    if not dry_run and modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    
    return stats


def process_backend(backend_path: Path, backend: str, dry_run: bool = False):
    """Process all Python files in a backend directory."""
    print(f"\n{'='*70}")
    print(f"Processing {backend.upper()} backend")
    print(f"{'='*70}\n")
    
    py_files = list(backend_path.rglob('*.py'))
    total_stats = {
        'files_processed': 0,
        'total_logs': 0,
        'standardized': 0,
        'skipped': 0
    }
    
    for py_file in py_files:
        if py_file.name.startswith('__'):
            continue
        
        print(f"Processing: {py_file.name}...", end=' ')
        
        stats = standardize_file(py_file, backend, dry_run)
        
        total_stats['files_processed'] += 1
        total_stats['total_logs'] += stats['total_logs']
        total_stats['standardized'] += stats['standardized']
        total_stats['skipped'] += stats['skipped']
        
        if stats['standardized'] > 0:
            print(f"✓ {stats['standardized']} logs standardized")
            if dry_run:
                for change in stats['changes'][:3]:  # Show first 3
                    print(f"  Line {change['line']}:")
                    print(f"    - {change['old']}")
                    print(f"    + {change['new']}")
                if len(stats['changes']) > 3:
                    print(f"  ... and {len(stats['changes']) - 3} more")
        else:
            print("✓ Already standardized")
    
    # Summary
    print(f"\n{backend.upper()} Summary:")
    print(f"  Files processed: {total_stats['files_processed']}")
    print(f"  Total logs found: {total_stats['total_logs']}")
    print(f"  Standardized: {total_stats['standardized']}")
    print(f"  Already OK: {total_stats['skipped']}")
    
    return total_stats


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto-standardize FilterMate logging')
    parser.add_argument('--backend', '-b', choices=['postgresql', 'spatialite', 'ogr', 'all'], 
                       default='all', help='Backend to process')
    parser.add_argument('--dry-run', '-d', action='store_true', 
                       help='Show changes without applying')
    args = parser.parse_args()
    
    # Determine base path
    script_dir = Path(__file__).parent
    base_path = script_dir.parent / 'adapters' / 'backends'
    
    if not base_path.exists():
        print(f"Error: Backend directory not found: {base_path}")
        return 1
    
    print(f"FilterMate Logging Auto-Standardization")
    print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE (will modify files)'}")
    print(f"Base: {base_path}\n")
    
    # Select backends
    backends = ['postgresql', 'spatialite', 'ogr'] if args.backend == 'all' else [args.backend]
    
    all_stats = {}
    
    for backend in backends:
        backend_path = base_path / backend
        if not backend_path.exists():
            print(f"Warning: {backend} directory not found")
            continue
        
        stats = process_backend(backend_path, backend, args.dry_run)
        all_stats[backend] = stats
    
    # Overall summary
    if len(all_stats) > 1:
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print(f"{'='*70}\n")
        
        total_files = sum(s['files_processed'] for s in all_stats.values())
        total_logs = sum(s['total_logs'] for s in all_stats.values())
        total_standardized = sum(s['standardized'] for s in all_stats.values())
        total_skipped = sum(s['skipped'] for s in all_stats.values())
        
        print(f"Backends processed: {len(all_stats)}")
        print(f"Files processed: {total_files}")
        print(f"Total logs: {total_logs}")
        print(f"Standardized: {total_standardized}")
        print(f"Already OK: {total_skipped}")
        
        if args.dry_run:
            print(f"\n✓ DRY RUN complete - No files modified")
            print(f"  Run without --dry-run to apply changes")
        else:
            print(f"\n✓ Standardization complete")
            print(f"  Run tools/validate_logging.py to verify")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
