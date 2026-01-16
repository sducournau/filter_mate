#!/usr/bin/env python3
"""
Automatically fix deprecated module imports.

This script corrects imports from the old modules/ structure
to the new hexagonal architecture paths.

Usage:
    python3 tools/fix_imports.py [--dry-run] [--verbose]
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Import replacement patterns
# Key: regex pattern, Value: replacement string
REPLACEMENTS: Dict[str, str] = {
    # Backends - adapters/backends/ files
    r'from modules\.backends\.ogr_backend': 'from ..ogr.backend',
    r'from modules\.backends\.spatialite_backend': 'from ..spatialite.backend',
    r'from modules\.backends\.postgresql_backend': 'from ..postgresql.backend',
    r'from modules\.backends\.memory_backend': 'from ..memory.backend',
    r'from modules\.backends\.base_backend': 'from ..base_backend',
    
    # Infrastructure - for root-level or test files
    r'from modules\.appUtils import': 'from infrastructure.utils import',
    
    # Tasks - for test files
    r'from modules\.tasks\.filter_task import': 'from core.tasks import',
    r'from modules\.tasks\.layer_management_task import': 'from core.tasks import',
}

# Files to process
TARGET_FILES: List[str] = [
    'adapters/backends/factory.py',
    'adapters/backends/legacy_adapter.py',
    'tests/test_postgresql_layer_handling.py',
    'tests/test_postgresql_mv_cleanup.py',
]


def fix_imports_in_file(filepath: Path, dry_run: bool = False, verbose: bool = False) -> Tuple[int, List[str]]:
    """
    Fix imports in a single file.
    
    Args:
        filepath: Path to file to fix
        dry_run: If True, don't write changes (just report)
        verbose: If True, show detailed replacement info
    
    Returns:
        Tuple of (number of replacements, list of changes)
    """
    if not filepath.exists():
        return 0, [f"File not found: {filepath}"]
    
    content = filepath.read_text(encoding='utf-8')
    original = content
    changes = []
    
    for pattern, replacement in REPLACEMENTS.items():
        matches = list(re.finditer(pattern, content))
        if matches:
            content = re.sub(pattern, replacement, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                old_import = match.group(0)
                changes.append(f"  Line {line_num}: {old_import} → {replacement}")
    
    replacement_count = len(changes)
    
    if content != original and not dry_run:
        filepath.write_text(content, encoding='utf-8')
    
    return replacement_count, changes


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix deprecated module imports')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be changed without modifying files')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed replacement information')
    args = parser.parse_args()
    
    # Print header
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}FilterMate Import Fixer{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")
    
    if args.dry_run:
        print(f"{Colors.WARNING}DRY RUN MODE - No files will be modified{Colors.ENDC}\n")
    
    # Process files
    total_replacements = 0
    files_modified = 0
    
    for file_path in TARGET_FILES:
        path = Path(file_path)
        
        print(f"\n{Colors.BOLD}Processing: {file_path}{Colors.ENDC}")
        
        count, changes = fix_imports_in_file(path, dry_run=args.dry_run, verbose=args.verbose)
        
        if count > 0:
            files_modified += 1
            total_replacements += count
            print(f"{Colors.OKGREEN}✅ {count} replacement(s) made{Colors.ENDC}")
            
            if args.verbose:
                for change in changes:
                    print(f"{Colors.OKCYAN}{change}{Colors.ENDC}")
        elif not path.exists():
            print(f"{Colors.FAIL}❌ File not found{Colors.ENDC}")
        else:
            print(f"{Colors.OKBLUE}⏭️  No changes needed{Colors.ENDC}")
    
    # Print summary
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}Summary:{Colors.ENDC}")
    print(f"  Files processed: {len(TARGET_FILES)}")
    print(f"  Files modified: {files_modified}")
    print(f"  Total replacements: {total_replacements}")
    
    if total_replacements > 0:
        print(f"\n{Colors.OKGREEN}🎯 {total_replacements} deprecated imports fixed!{Colors.ENDC}")
        
        if args.dry_run:
            print(f"\n{Colors.WARNING}Run without --dry-run to apply changes{Colors.ENDC}")
        else:
            print(f"\n{Colors.OKGREEN}✅ Changes written to disk{Colors.ENDC}")
            print(f"\nNext steps:")
            print(f"  1. Test imports: python3 -c 'from adapters.backends.factory import BackendFactory'")
            print(f"  2. Run tests: pytest tests/test_postgresql_*.py -v")
    else:
        print(f"\n{Colors.OKGREEN}✅ All imports are up to date!{Colors.ENDC}")
    
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")
    
    # Exit code: 0 if successful, 1 if no changes made (for CI/CD)
    return 0 if total_replacements > 0 or args.dry_run else 0


if __name__ == '__main__':
    sys.exit(main())
