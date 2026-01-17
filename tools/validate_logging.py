#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate Logging Validation Tool
===================================

Validates that all logging statements follow the standardization:
- Backend prefixes: [PostgreSQL], [Spatialite], [OGR]
- Consistent format with context (layer name, feature count)
- Proper log levels (DEBUG, INFO, WARNING, ERROR)

Usage:
    python tools/validate_logging.py
    python tools/validate_logging.py --verbose
    python tools/validate_logging.py --backend postgresql
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict


# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


BACKENDS = ['postgresql', 'spatialite', 'ogr']

REQUIRED_PREFIXES = {
    'postgresql': r'\[PostgreSQL\]',
    'spatialite': r'\[Spatialite\]',
    'ogr': r'\[OGR\]'
}

# Patterns for validation
LOG_PATTERN = r'logger\.(debug|info|warning|error|exception)\s*\('
PREFIX_PATTERNS = {backend: re.compile(REQUIRED_PREFIXES[backend]) for backend in BACKENDS}
CONTEXT_PATTERN = re.compile(r'(Layer:|features|Expression:|Database:|Schema:|Session:)')


def validate_log_line(line: str, backend: str, line_num: int, file_path: Path) -> Dict:
    """
    Validate a single log line.
    
    Returns dict with validation results.
    """
    result = {
        'has_prefix': False,
        'has_context': False,
        'log_level': None,
        'issues': []
    }
    
    # Extract log level
    level_match = re.search(r'logger\.(debug|info|warning|error|exception)', line)
    if level_match:
        result['log_level'] = level_match.group(1)
    
    # Check for backend prefix
    if PREFIX_PATTERNS[backend].search(line):
        result['has_prefix'] = True
    else:
        result['issues'].append(f"Missing [{backend.capitalize()}] prefix")
    
    # Check for context (layer name, features, etc.)
    if CONTEXT_PATTERN.search(line):
        result['has_context'] = True
    elif result['log_level'] in ['info', 'warning', 'error']:
        # INFO/WARNING/ERROR should have context
        result['issues'].append("Missing context (Layer:, features, etc.)")
    
    # Check for emoji/checkmarks (old style)
    if '✅' in line or '❌' in line:
        result['issues'].append("Contains emoji - use text only")
    
    return result


def validate_backend_files(backend_path: Path, backend_name: str, verbose: bool = False) -> Dict:
    """
    Validate all Python files in a backend directory.
    """
    results = {
        'total_logs': 0,
        'with_prefix': 0,
        'with_context': 0,
        'by_level': defaultdict(int),
        'issues': [],
        'files_processed': 0
    }
    
    py_files = list(backend_path.rglob('*.py'))
    
    for py_file in py_files:
        if py_file.name.startswith('__'):
            continue
            
        results['files_processed'] += 1
        
        with open(py_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if re.search(LOG_PATTERN, line):
                    results['total_logs'] += 1
                    
                    validation = validate_log_line(line, backend_name, line_num, py_file)
                    
                    if validation['has_prefix']:
                        results['with_prefix'] += 1
                    
                    if validation['has_context']:
                        results['with_context'] += 1
                    
                    if validation['log_level']:
                        results['by_level'][validation['log_level']] += 1
                    
                    # Collect issues
                    if validation['issues']:
                        issue_entry = {
                            'file': py_file.name,
                            'line': line_num,
                            'issues': validation['issues'],
                            'code': line.strip()[:100]
                        }
                        results['issues'].append(issue_entry)
    
    return results


def print_backend_results(backend: str, results: Dict, verbose: bool = False):
    """Print results for a single backend."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{backend.upper()} Backend{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    total = results['total_logs']
    
    # Summary stats
    print(f"Files processed: {results['files_processed']}")
    print(f"Total log statements: {total}")
    
    if total > 0:
        prefix_pct = (results['with_prefix'] / total) * 100
        context_pct = (results['with_context'] / total) * 100
        
        # Prefix compliance
        prefix_color = Colors.GREEN if prefix_pct == 100 else Colors.YELLOW if prefix_pct >= 80 else Colors.RED
        print(f"With [{backend.capitalize()}] prefix: {prefix_color}{results['with_prefix']}/{total} ({prefix_pct:.1f}%){Colors.RESET}")
        
        # Context compliance
        context_color = Colors.GREEN if context_pct >= 80 else Colors.YELLOW if context_pct >= 50 else Colors.RED
        print(f"With context: {context_color}{results['with_context']}/{total} ({context_pct:.1f}%){Colors.RESET}")
        
        # By level
        print(f"\nLog levels:")
        for level in ['debug', 'info', 'warning', 'error', 'exception']:
            if level in results['by_level']:
                print(f"  {level.upper()}: {results['by_level'][level]}")
    
    # Issues
    issue_count = len(results['issues'])
    if issue_count > 0:
        print(f"\n{Colors.YELLOW}⚠️  Issues found: {issue_count}{Colors.RESET}")
        
        if verbose or issue_count <= 10:
            for issue in results['issues']:
                print(f"\n  {Colors.RED}✗{Colors.RESET} {issue['file']}:{issue['line']}")
                for problem in issue['issues']:
                    print(f"    - {problem}")
                if verbose:
                    print(f"    Code: {issue['code']}")
        else:
            print(f"\n  Showing first 10 issues (use --verbose for all):")
            for issue in results['issues'][:10]:
                print(f"  {Colors.RED}✗{Colors.RESET} {issue['file']}:{issue['line']} - {', '.join(issue['issues'])}")
            print(f"  ... and {issue_count - 10} more")
    else:
        print(f"\n{Colors.GREEN}✓ All logs properly formatted!{Colors.RESET}")


def print_overall_summary(all_results: Dict[str, Dict]):
    """Print overall summary across all backends."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}OVERALL SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    total_logs = sum(r['total_logs'] for r in all_results.values())
    total_with_prefix = sum(r['with_prefix'] for r in all_results.values())
    total_with_context = sum(r['with_context'] for r in all_results.values())
    total_issues = sum(len(r['issues']) for r in all_results.values())
    
    print(f"Total backends analyzed: {len(all_results)}")
    print(f"Total log statements: {total_logs}")
    
    if total_logs > 0:
        prefix_pct = (total_with_prefix / total_logs) * 100
        context_pct = (total_with_context / total_logs) * 100
        
        prefix_color = Colors.GREEN if prefix_pct == 100 else Colors.YELLOW if prefix_pct >= 80 else Colors.RED
        context_color = Colors.GREEN if context_pct >= 80 else Colors.YELLOW if context_pct >= 50 else Colors.RED
        
        print(f"Properly prefixed: {prefix_color}{total_with_prefix}/{total_logs} ({prefix_pct:.1f}%){Colors.RESET}")
        print(f"With context: {context_color}{total_with_context}/{total_logs} ({context_pct:.1f}%){Colors.RESET}")
        print(f"Total issues: {Colors.RED if total_issues > 0 else Colors.GREEN}{total_issues}{Colors.RESET}")
        
        # Pass/Fail determination
        print(f"\n{Colors.BOLD}Status: ", end='')
        if prefix_pct == 100 and total_issues == 0:
            print(f"{Colors.GREEN}✓ PASSED - All logs standardized!{Colors.RESET}")
            return 0
        elif prefix_pct >= 80:
            print(f"{Colors.YELLOW}⚠ PARTIAL - {total_logs - total_with_prefix} logs need fixing{Colors.RESET}")
            return 1
        else:
            print(f"{Colors.RED}✗ FAILED - {total_logs - total_with_prefix} logs need fixing{Colors.RESET}")
            return 1
    
    return 0


def main():
    """Run validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate FilterMate logging standardization')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--backend', '-b', choices=BACKENDS, help='Validate specific backend only')
    args = parser.parse_args()
    
    # Determine base path
    script_dir = Path(__file__).parent
    base_path = script_dir.parent / 'adapters' / 'backends'
    
    if not base_path.exists():
        print(f"{Colors.RED}Error: Backend directory not found: {base_path}{Colors.RESET}")
        return 1
    
    print(f"{Colors.BOLD}FilterMate Logging Validation{Colors.RESET}")
    print(f"Scanning: {base_path}\n")
    
    # Select backends to validate
    backends_to_check = [args.backend] if args.backend else BACKENDS
    
    all_results = {}
    
    for backend in backends_to_check:
        backend_path = base_path / backend
        if not backend_path.exists():
            print(f"{Colors.YELLOW}Warning: Backend directory not found: {backend_path}{Colors.RESET}")
            continue
        
        results = validate_backend_files(backend_path, backend, args.verbose)
        all_results[backend] = results
        print_backend_results(backend, results, args.verbose)
    
    # Overall summary
    if len(all_results) > 1:
        exit_code = print_overall_summary(all_results)
    else:
        # Single backend - use its result
        backend_result = list(all_results.values())[0]
        total = backend_result['total_logs']
        if total > 0:
            exit_code = 0 if backend_result['with_prefix'] == total else 1
        else:
            exit_code = 0
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
