#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate - Script de Suppression du Dossier modules/

Ce script supprime le dossier legacy `modules/` après la migration v4.0.

IMPORTANT: Exécuter ce script UNIQUEMENT après avoir:
1. Vérifié que tous les tests passent
2. Confirmé que le plugin fonctionne sans modules/
3. Fait un backup du dossier modules/

Usage:
    python tools/delete_modules_folder.py [--dry-run] [--backup]

Options:
    --dry-run   Affiche ce qui serait supprimé sans rien supprimer
    --backup    Crée une archive ZIP avant suppression
    --force     Supprime sans confirmation

Author: FilterMate Team
Date: January 2026
Version: 4.0.0
"""

import os
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path


def get_plugin_root() -> Path:
    """Get the FilterMate plugin root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent


def count_files(directory: Path) -> dict:
    """Count files in a directory by type."""
    counts = {
        'python': 0,
        'markdown': 0,
        'other': 0,
        'total': 0,
        'total_size': 0
    }
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            file_path = Path(root) / file
            counts['total'] += 1
            counts['total_size'] += file_path.stat().st_size
            
            if file.endswith('.py'):
                counts['python'] += 1
            elif file.endswith('.md'):
                counts['markdown'] += 1
            else:
                counts['other'] += 1
    
    return counts


def create_backup(modules_dir: Path, backup_dir: Path) -> Path:
    """Create a ZIP backup of the modules directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"modules_backup_{timestamp}"
    backup_path = backup_dir / backup_name
    
    print(f"Creating backup: {backup_path}.zip")
    shutil.make_archive(str(backup_path), 'zip', modules_dir.parent, modules_dir.name)
    
    return Path(f"{backup_path}.zip")


def delete_modules(modules_dir: Path, dry_run: bool = False) -> bool:
    """Delete the modules directory."""
    if dry_run:
        print(f"\n[DRY-RUN] Would delete: {modules_dir}")
        return True
    
    try:
        shutil.rmtree(modules_dir)
        print(f"\n✅ Successfully deleted: {modules_dir}")
        return True
    except Exception as e:
        print(f"\n❌ Error deleting {modules_dir}: {e}")
        return False


def verify_new_architecture(plugin_root: Path) -> list:
    """Verify that new architecture folders exist."""
    required_folders = [
        'adapters',
        'core', 
        'infrastructure',
        'ui',
        'config',
    ]
    
    missing = []
    for folder in required_folders:
        if not (plugin_root / folder).exists():
            missing.append(folder)
    
    return missing


def check_remaining_imports(plugin_root: Path, modules_dir: Path) -> list:
    """Check for remaining imports from modules/ in new architecture."""
    import re
    
    issues = []
    new_dirs = ['adapters', 'core', 'infrastructure', 'ui', 'config', 'utils']
    
    for dir_name in new_dirs:
        dir_path = plugin_root / dir_name
        if not dir_path.exists():
            continue
        
        for py_file in dir_path.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8')
                # Skip json_view since it has internal demo files
                if 'json_view' in str(py_file):
                    continue
                
                # Check for actual imports (not comments)
                for i, line in enumerate(content.split('\n'), 1):
                    if line.strip().startswith('#'):
                        continue
                    if 'from modules.' in line or 'import modules.' in line:
                        issues.append({
                            'file': py_file.relative_to(plugin_root),
                            'line': i,
                            'content': line.strip()
                        })
            except Exception:
                pass
    
    return issues


def main():
    parser = argparse.ArgumentParser(
        description='Delete the legacy modules/ folder after migration'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--backup',
        action='store_true', 
        help='Create a ZIP backup before deletion'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete without confirmation prompt'
    )
    
    args = parser.parse_args()
    
    # Get paths
    plugin_root = get_plugin_root()
    modules_dir = plugin_root / 'modules'
    backup_dir = plugin_root / '_backups'
    
    print("=" * 60)
    print("FilterMate - Suppression du Dossier modules/")
    print("=" * 60)
    
    # Check if modules exists
    if not modules_dir.exists():
        print(f"\n✅ Le dossier modules/ n'existe pas: {modules_dir}")
        print("   Rien à supprimer.")
        return 0
    
    # Verify new architecture
    print("\n📂 Vérification de la nouvelle architecture...")
    missing = verify_new_architecture(plugin_root)
    if missing:
        print(f"   ❌ Dossiers manquants: {', '.join(missing)}")
        print("   Arrêt du script.")
        return 1
    print("   ✅ Nouvelle architecture présente")
    
    # Check for remaining imports
    print("\n🔍 Vérification des imports restants...")
    issues = check_remaining_imports(plugin_root, modules_dir)
    if issues:
        print(f"   ⚠️  {len(issues)} import(s) depuis modules/ trouvé(s):")
        for issue in issues[:5]:
            print(f"      - {issue['file']}:{issue['line']}: {issue['content'][:50]}")
        if len(issues) > 5:
            print(f"      ... et {len(issues) - 5} autre(s)")
        
        if not args.force:
            print("\n   Utilisez --force pour ignorer cet avertissement.")
            return 1
    else:
        print("   ✅ Aucun import critique trouvé")
    
    # Count files
    print("\n📊 Statistiques du dossier modules/:")
    counts = count_files(modules_dir)
    print(f"   - Fichiers Python: {counts['python']}")
    print(f"   - Fichiers Markdown: {counts['markdown']}")
    print(f"   - Autres fichiers: {counts['other']}")
    print(f"   - Total: {counts['total']} fichiers")
    print(f"   - Taille: {counts['total_size'] / 1024:.1f} KB")
    
    # Create backup if requested
    if args.backup:
        backup_dir.mkdir(exist_ok=True)
        backup_path = create_backup(modules_dir, backup_dir)
        print(f"   ✅ Backup créé: {backup_path}")
    
    # Confirm deletion
    if not args.dry_run and not args.force:
        print("\n⚠️  ATTENTION: Cette action est irréversible!")
        response = input("   Voulez-vous vraiment supprimer modules/? [y/N]: ")
        if response.lower() != 'y':
            print("   Annulé.")
            return 0
    
    # Delete
    if delete_modules(modules_dir, dry_run=args.dry_run):
        print("\n🎉 Migration v4.0 terminée!")
        print("   Le dossier modules/ a été supprimé.")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
