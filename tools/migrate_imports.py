#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate - Script de Migration des Imports Legacy

Ce script migre automatiquement les imports `from modules.*` vers 
la nouvelle architecture hexagonale.

Usage:
    python tools/migrate_imports.py [--dry-run] [--verbose]

Options:
    --dry-run   Afficher les changements sans les appliquer
    --verbose   Afficher les détails de chaque modification

Author: BMad Master + Simon
Date: 2026-01-09
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ============================================
# MODULE REPLACEMENTS - Ordre strict (plus long d'abord)
# ============================================
# Note: Les replacements sont appliqués ligne par ligne
# Chaque tuple: (pattern_source, replacement)

MODULE_REPLACEMENTS = [
    # --------------------------------------------
    # PostgreSQL Availability (priorité haute)
    # --------------------------------------------
    ("modules.psycopg2_availability", "adapters.backends"),
    ("modules.appUtils import POSTGRESQL_AVAILABLE", "adapters.backends import POSTGRESQL_AVAILABLE"),
    
    # --------------------------------------------
    # Logging
    # --------------------------------------------
    ("modules.logging_config", "infrastructure.logging"),
    
    # --------------------------------------------
    # Feedback Utils
    # --------------------------------------------
    ("modules.feedback_utils", "infrastructure.feedback"),
    
    # --------------------------------------------
    # UI Config
    # --------------------------------------------
    ("modules.ui_config", "ui.config"),
    
    # --------------------------------------------
    # UI Elements
    # --------------------------------------------
    ("modules.ui_elements", "ui.elements"),
    
    # --------------------------------------------
    # UI Styles
    # --------------------------------------------
    ("modules.ui_styles", "ui.styles"),
    
    # --------------------------------------------
    # Favorites
    # --------------------------------------------
    ("modules.filter_favorites", "core.services.favorites_service"),
    
    # --------------------------------------------
    # History
    # --------------------------------------------
    ("modules.filter_history", "core.services.history_service"),
    
    # --------------------------------------------
    # Backends (ordre: plus spécifique d'abord)
    # --------------------------------------------
    ("modules.backends.auto_optimizer", "core.services.auto_optimizer"),
    ("modules.backends.postgresql_backend", "adapters.backends.postgresql"),
    ("modules.backends.spatialite_backend", "adapters.backends.spatialite"),
    ("modules.backends.spatialite_cache", "infrastructure.cache"),
    ("modules.backends.ogr_backend", "adapters.backends.ogr"),
    ("modules.backends.base_backend", "adapters.backends.base"),
    ("modules.backends.factory", "adapters.backends.factory"),
    
    # --------------------------------------------
    # Tasks
    # --------------------------------------------
    ("modules.tasks.filter_task", "adapters.qgis.tasks"),
    ("modules.tasks.result_streaming", "adapters.qgis.tasks"),
    ("modules.appTasks", "adapters.qgis.tasks"),
    
    # --------------------------------------------
    # Resilience
    # --------------------------------------------
    ("modules.circuit_breaker", "infrastructure.resilience"),
    
    # --------------------------------------------
    # Cache
    # --------------------------------------------
    ("modules.exploring_cache", "infrastructure.cache"),
    
    # --------------------------------------------
    # Layer Utils
    # --------------------------------------------
    ("modules.appUtils import is_layer_source_available", "core.services.layer_service import is_layer_source_available"),
]


def migrate_file(filepath: Path, dry_run: bool = False, verbose: bool = False) -> Tuple[int, List[str]]:
    """
    Migrate imports in a single file.
    
    Returns:
        Tuple of (number of changes, list of change descriptions)
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  ⚠️ Cannot read {filepath}: {e}")
        return 0, []
    
    lines = content.split('\n')
    new_lines = []
    changes = []
    
    for line in lines:
        original_line = line
        modified = False
        
        # Skip comments
        if line.strip().startswith('#'):
            new_lines.append(line)
            continue
        
        # Apply replacements (ordre important - plus spécifique d'abord)
        for old_module, new_module in MODULE_REPLACEMENTS:
            if old_module in line:
                line = line.replace(old_module, new_module)
                modified = True
                break  # Un seul remplacement par ligne
        
        new_lines.append(line)
        
        if modified and original_line != line:
            if verbose:
                print(f"    {original_line.strip()[:50]}")
                print(f"    → {line.strip()[:50]}")
            changes.append(f"{original_line.strip()[:40]}... → {line.strip()[:40]}...")
    
    if changes and not dry_run:
        try:
            filepath.write_text('\n'.join(new_lines), encoding='utf-8')
        except Exception as e:
            print(f"  ⚠️ Cannot write {filepath}: {e}")
            return 0, []
    
    return len(changes), changes


def find_remaining_legacy_imports(filepath: Path) -> List[str]:
    """Find any remaining legacy imports that weren't migrated."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return []
    
    remaining = []
    for line in content.split('\n'):
        if 'from modules.' in line and not line.strip().startswith('#'):
            remaining.append(line.strip())
    
    return remaining


def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv
    
    if dry_run:
        print("🔍 Mode DRY-RUN - Aucune modification ne sera effectuée\n")
    
    root = Path(__file__).parent.parent
    exclude_dirs = {'__pycache__', '.git', 'node_modules', 'modules', 'tests', '_bmad', '_bmad-output'}
    exclude_files = {'migrate_imports.py'}  # Exclude self
    
    total_changes = 0
    total_files = 0
    files_with_remaining = []
    
    print("📦 Migration des imports FilterMate")
    print("=" * 50)
    
    for py_file in sorted(root.rglob("*.py")):
        # Skip excluded directories
        if any(ex in py_file.parts for ex in exclude_dirs):
            continue
        # Skip excluded files
        if py_file.name in exclude_files:
            continue
        
        relative_path = py_file.relative_to(root)
        changes, change_list = migrate_file(py_file, dry_run, verbose)
        
        if changes > 0:
            status = "🔄" if dry_run else "✅"
            print(f"{status} {relative_path}: {changes} import(s) migré(s)")
            total_changes += changes
            total_files += 1
            
            if verbose:
                for change in change_list:
                    print(f"    → {change}")
        
        # Check for remaining legacy imports
        remaining = find_remaining_legacy_imports(py_file)
        if remaining:
            files_with_remaining.append((relative_path, remaining))
    
    print("\n" + "=" * 50)
    print(f"📊 Résumé:")
    print(f"   Fichiers modifiés: {total_files}")
    print(f"   Imports migrés: {total_changes}")
    
    if files_with_remaining:
        print(f"\n⚠️ Imports legacy restants ({len(files_with_remaining)} fichiers):")
        for filepath, imports in files_with_remaining[:10]:  # Show first 10
            print(f"   {filepath}:")
            for imp in imports[:3]:  # Show first 3 imports per file
                print(f"      {imp[:70]}...")
        if len(files_with_remaining) > 10:
            print(f"   ... et {len(files_with_remaining) - 10} autres fichiers")
    else:
        print("\n✅ Aucun import legacy restant!")
    
    if dry_run:
        print("\n💡 Exécutez sans --dry-run pour appliquer les changements")


if __name__ == "__main__":
    main()
