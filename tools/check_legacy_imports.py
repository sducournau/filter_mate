#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy Import Detector for FilterMate

This tool scans the codebase for imports from deprecated modules
and generates a migration report.

Usage:
    python check_legacy_imports.py [--fix] [--verbose]

Options:
    --fix       Attempt to auto-migrate imports where possible
    --verbose   Show detailed file-by-file analysis
    --json      Output results as JSON

v3.0.21: Initial implementation for legacy removal planning
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict


# Root directory of the plugin
PLUGIN_ROOT = Path(__file__).parent.parent

# Directories to scan
SCAN_DIRS = ['core', 'adapters', 'ui', 'infrastructure', 'config']

# Directories to skip
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', '_legacy', '_backups', 'tests'}

# Legacy import patterns to detect
LEGACY_PATTERNS = [
    # Direct imports from modules/
    (r'from\s+modules\.', 'modules.'),
    (r'import\s+modules\.', 'modules.'),
    # Relative imports within modules/ that reference backends
    (r'from\s+\.\.backends\.', '..backends.'),
    (r'from\s+\.backends\.', '.backends.'),
    # Relative imports within modules/ that reference tasks
    (r'from\s+\.\.tasks\.', '..tasks.'),
    (r'from\s+\.tasks\.', '.tasks.'),
]

# Migration mapping: old import -> new import
MIGRATION_MAP = {
    # Backends
    'adapters.backends.factory': 'adapters.backends.factory',
    'adapters.backends.base': 'adapters.backends.base',
    'adapters.backends.postgresql': 'adapters.backends.postgresql.backend',
    'adapters.backends.spatialite': 'adapters.backends.spatialite.backend',
    'adapters.backends.ogr': 'adapters.backends.ogr.backend',
    'modules.backends.memory_backend': 'adapters.backends.memory.backend',
    
    # Utils
    'modules.appUtils': 'adapters.database_manager',
    'modules.crs_utils': 'infrastructure.utils.crs',
    'modules.geometry_safety': 'infrastructure.utils.geometry',
    'modules.type_utils': 'infrastructure.utils.types',
    'modules.object_safety': 'infrastructure.utils.safety',
    'infrastructure.logging': 'infrastructure.logging.config',
    
    # Constants
    'modules.constants': 'core.domain.constants',
    'modules.customExceptions': 'core.domain.exceptions',
}


@dataclass
class LegacyImport:
    """Represents a detected legacy import."""
    file_path: str
    line_number: int
    line_content: str
    pattern_matched: str
    suggested_fix: str = ""


@dataclass
class ScanResult:
    """Results of the legacy import scan."""
    total_files_scanned: int = 0
    files_with_issues: int = 0
    total_legacy_imports: int = 0
    imports_by_pattern: Dict[str, int] = field(default_factory=dict)
    imports_by_file: Dict[str, List[LegacyImport]] = field(default_factory=dict)
    auto_fixable: int = 0
    
    def add_import(self, legacy_import: LegacyImport):
        file_path = legacy_import.file_path
        if file_path not in self.imports_by_file:
            self.imports_by_file[file_path] = []
            self.files_with_issues += 1
        
        self.imports_by_file[file_path].append(legacy_import)
        self.total_legacy_imports += 1
        
        pattern = legacy_import.pattern_matched
        self.imports_by_pattern[pattern] = self.imports_by_pattern.get(pattern, 0) + 1
        
        if legacy_import.suggested_fix:
            self.auto_fixable += 1


def get_suggested_fix(import_line: str) -> str:
    """Get the suggested fix for a legacy import line."""
    for old, new in MIGRATION_MAP.items():
        if old in import_line:
            return import_line.replace(old, new)
    return ""


def scan_file(file_path: Path) -> List[LegacyImport]:
    """Scan a single Python file for legacy imports."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (IOError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return issues
    
    for line_num, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        
        # Check each pattern
        for pattern, description in LEGACY_PATTERNS:
            if re.search(pattern, line):
                suggested_fix = get_suggested_fix(line)
                issues.append(LegacyImport(
                    file_path=str(file_path.relative_to(PLUGIN_ROOT)),
                    line_number=line_num,
                    line_content=line.rstrip(),
                    pattern_matched=description,
                    suggested_fix=suggested_fix.rstrip() if suggested_fix else ""
                ))
                break  # Only report once per line
    
    return issues


def scan_directory(directory: Path, skip_self: bool = True) -> ScanResult:
    """Scan a directory recursively for legacy imports."""
    result = ScanResult()
    
    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        
        root_path = Path(root)
        
        for file in files:
            if not file.endswith('.py'):
                continue
            
            file_path = root_path / file
            
            # Skip this script itself
            if skip_self and file_path.name == 'check_legacy_imports.py':
                continue
            
            result.total_files_scanned += 1
            issues = scan_file(file_path)
            
            for issue in issues:
                result.add_import(issue)
    
    return result


def generate_report(result: ScanResult, verbose: bool = False) -> str:
    """Generate a human-readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append("FilterMate Legacy Import Detection Report")
    lines.append("=" * 60)
    lines.append("")
    
    # Summary
    lines.append("📊 SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Files scanned:        {result.total_files_scanned}")
    lines.append(f"  Files with issues:    {result.files_with_issues}")
    lines.append(f"  Total legacy imports: {result.total_legacy_imports}")
    lines.append(f"  Auto-fixable:         {result.auto_fixable}")
    lines.append("")
    
    # Breakdown by pattern
    if result.imports_by_pattern:
        lines.append("📋 IMPORTS BY PATTERN")
        lines.append("-" * 40)
        for pattern, count in sorted(result.imports_by_pattern.items(), key=lambda x: -x[1]):
            lines.append(f"  {pattern:30s} {count:5d}")
        lines.append("")
    
    # Files with issues
    if result.files_with_issues > 0:
        lines.append("📁 FILES WITH LEGACY IMPORTS")
        lines.append("-" * 40)
        
        for file_path, imports in sorted(result.imports_by_file.items()):
            lines.append(f"\n  {file_path} ({len(imports)} imports)")
            
            if verbose:
                for imp in imports:
                    lines.append(f"    L{imp.line_number}: {imp.line_content.strip()}")
                    if imp.suggested_fix:
                        lines.append(f"         → {imp.suggested_fix.strip()}")
    
    # Recommendations
    lines.append("")
    lines.append("🎯 RECOMMENDATIONS")
    lines.append("-" * 40)
    
    if result.total_legacy_imports == 0:
        lines.append("  ✅ No legacy imports detected! Ready for v4.0.")
    else:
        lines.append(f"  ⚠️  {result.total_legacy_imports} legacy imports need migration.")
        lines.append(f"  📝 {result.auto_fixable} can be auto-fixed with --fix flag.")
        lines.append("  📚 See legacy-removal-roadmap.md for migration plan.")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def apply_fixes(result: ScanResult) -> int:
    """Apply automatic fixes where possible."""
    fixed_count = 0
    
    for file_path, imports in result.imports_by_file.items():
        fixable = [imp for imp in imports if imp.suggested_fix]
        if not fixable:
            continue
        
        full_path = PLUGIN_ROOT / file_path
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Apply fixes in reverse order to preserve line numbers
            for imp in sorted(fixable, key=lambda x: -x.line_number):
                lines[imp.line_number - 1] = imp.suggested_fix + '\n'
                fixed_count += 1
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print(f"✅ Fixed {len(fixable)} imports in {file_path}")
            
        except Exception as e:
            print(f"❌ Error fixing {file_path}: {e}", file=sys.stderr)
    
    return fixed_count


def main():
    parser = argparse.ArgumentParser(
        description='Detect legacy imports in FilterMate codebase'
    )
    parser.add_argument('--fix', action='store_true',
                        help='Attempt to auto-migrate imports')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed analysis')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('--scan-all', action='store_true',
                        help='Scan all directories including modules/')
    
    args = parser.parse_args()
    
    # Determine directories to scan
    if args.scan_all:
        scan_dirs = [PLUGIN_ROOT]
    else:
        scan_dirs = [PLUGIN_ROOT / d for d in SCAN_DIRS if (PLUGIN_ROOT / d).exists()]
    
    # Scan all directories
    combined_result = ScanResult()
    
    for scan_dir in scan_dirs:
        result = scan_directory(scan_dir)
        combined_result.total_files_scanned += result.total_files_scanned
        combined_result.files_with_issues += result.files_with_issues
        combined_result.total_legacy_imports += result.total_legacy_imports
        combined_result.auto_fixable += result.auto_fixable
        
        for pattern, count in result.imports_by_pattern.items():
            combined_result.imports_by_pattern[pattern] = \
                combined_result.imports_by_pattern.get(pattern, 0) + count
        
        combined_result.imports_by_file.update(result.imports_by_file)
    
    # Output
    if args.json:
        output = {
            'summary': {
                'total_files_scanned': combined_result.total_files_scanned,
                'files_with_issues': combined_result.files_with_issues,
                'total_legacy_imports': combined_result.total_legacy_imports,
                'auto_fixable': combined_result.auto_fixable,
            },
            'imports_by_pattern': combined_result.imports_by_pattern,
            'imports_by_file': {
                path: [asdict(imp) for imp in imports]
                for path, imports in combined_result.imports_by_file.items()
            }
        }
        print(json.dumps(output, indent=2))
    else:
        print(generate_report(combined_result, verbose=args.verbose))
    
    # Apply fixes if requested
    if args.fix and combined_result.auto_fixable > 0:
        print("\n🔧 Applying automatic fixes...")
        fixed = apply_fixes(combined_result)
        print(f"\n✅ Fixed {fixed} legacy imports")
    
    # Exit with error code if issues found
    return 1 if combined_result.total_legacy_imports > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
