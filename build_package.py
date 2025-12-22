#!/usr/bin/env python3
"""
Script de création d'archive pour l'upload sur le dépôt de plugins QGIS.

Ce script crée une archive ZIP prête à être uploadée sur https://plugins.qgis.org/

Usage:
    python build_package.py
    python build_package.py --output /chemin/vers/dossier
    python build_package.py --clean  # Nettoie les anciens builds

Le fichier ZIP sera créé dans le dossier 'dist/' par défaut.
"""

import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path


# Configuration
PLUGIN_NAME = "filter_mate"

# Fichiers et dossiers à EXCLURE de l'archive
EXCLUDE_PATTERNS = [
    # Dossiers de développement
    ".git",
    ".github",
    ".vscode",
    ".bmad-core",
    ".serena",
    ".mypy_cache",
    "__pycache__",
    ".pytest_cache",
    
    # Dossiers de build/test
    "dist",
    "build",
    "tests",
    "tools",
    "website",
    "docs",
    
    # Fichiers de configuration dev
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "Thumbs.db",
    
    # Scripts de build/test
    "build_package.py",
    "compile_ui.bat",
    "setup_tests.bat",
    "setup_tests.sh",
    "compile_translations.py",
    "requirements-test.txt",
    
    # Fichiers temporaires
    "*.tmp",
    "*.bak",
    "*.swp",
    "*~",
    
    # Changelogs de version spécifiques (pattern exact)
    "CHANGELOG_v",  # Tout fichier commençant par CHANGELOG_v
    
    # Backups de config
    "config/backups",
]

# Fichiers obligatoires pour un plugin QGIS
REQUIRED_FILES = [
    "__init__.py",
    "metadata.txt",
    f"{PLUGIN_NAME}.py",
    "resources.py",
    "icon.png",
]


def get_version_from_metadata(plugin_dir: Path) -> str:
    """Extrait la version depuis metadata.txt"""
    metadata_file = plugin_dir / "metadata.txt"
    if not metadata_file.exists():
        raise FileNotFoundError(f"metadata.txt non trouvé dans {plugin_dir}")
    
    content = metadata_file.read_text(encoding='utf-8')
    match = re.search(r'^version\s*=\s*(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    raise ValueError("Version non trouvée dans metadata.txt")


def should_exclude(path: Path, base_dir: Path) -> bool:
    """Vérifie si un chemin doit être exclu de l'archive"""
    rel_path = path.relative_to(base_dir)
    path_str = str(rel_path)
    name = path.name
    
    for pattern in EXCLUDE_PATTERNS:
        # Pattern exact
        if name == pattern:
            return True
        # Pattern avec wildcard simple (*.pyc, etc.)
        if pattern.startswith("*") and name.endswith(pattern[1:]):
            return True
        if pattern.endswith("*") and name.startswith(pattern[:-1]):
            return True
        # Pattern de préfixe (CHANGELOG_v -> exclut CHANGELOG_v2.3.9.md)
        if not pattern.startswith("*") and not pattern.endswith("*"):
            if "/" not in pattern and name.startswith(pattern) and name != pattern:
                return True
        # Dossier dans le chemin
        if pattern in path_str.split(os.sep):
            return True
        # Sous-chemin (comme config/backups)
        if "/" in pattern and path_str.startswith(pattern.replace("/", os.sep)):
            return True
    
    return False


def validate_plugin(plugin_dir: Path) -> list:
    """Valide que tous les fichiers obligatoires sont présents"""
    missing = []
    for required in REQUIRED_FILES:
        if not (plugin_dir / required).exists():
            missing.append(required)
    return missing


def get_files_to_include(plugin_dir: Path) -> list:
    """Retourne la liste des fichiers à inclure dans l'archive"""
    files = []
    
    for root, dirs, filenames in os.walk(plugin_dir):
        root_path = Path(root)
        
        # Filtrer les dossiers à ne pas parcourir
        dirs[:] = [d for d in dirs if not should_exclude(root_path / d, plugin_dir)]
        
        for filename in filenames:
            file_path = root_path / filename
            if not should_exclude(file_path, plugin_dir):
                files.append(file_path)
    
    return files


def create_archive(plugin_dir: Path, output_dir: Path) -> Path:
    """Crée l'archive ZIP du plugin"""
    version = get_version_from_metadata(plugin_dir)
    
    # Validation
    missing = validate_plugin(plugin_dir)
    if missing:
        print(f"❌ Fichiers obligatoires manquants: {', '.join(missing)}")
        sys.exit(1)
    
    # Créer le dossier de sortie
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Nom du fichier ZIP (format standard QGIS: plugin_name.version.zip)
    zip_filename = f"{PLUGIN_NAME}.{version}.zip"
    zip_path = output_dir / zip_filename
    
    # Supprimer l'ancien fichier si existant
    if zip_path.exists():
        zip_path.unlink()
    
    # Obtenir les fichiers à inclure
    files = get_files_to_include(plugin_dir)
    
    print(f"📦 Création de l'archive: {zip_filename}")
    print(f"   Version: {version}")
    print(f"   Fichiers: {len(files)}")
    
    # Créer l'archive
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in sorted(files):
            # Le chemin dans l'archive doit commencer par le nom du plugin
            rel_path = file_path.relative_to(plugin_dir)
            arcname = f"{PLUGIN_NAME}/{rel_path}"
            zipf.write(file_path, arcname)
    
    # Afficher la taille
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✅ Archive créée: {zip_path}")
    print(f"   Taille: {size_mb:.2f} MB")
    
    return zip_path


def list_archive_contents(zip_path: Path):
    """Affiche le contenu de l'archive"""
    print(f"\n📋 Contenu de l'archive:")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        for info in sorted(zipf.infolist(), key=lambda x: x.filename):
            if not info.filename.endswith('/'):
                size_kb = info.file_size / 1024
                print(f"   {info.filename} ({size_kb:.1f} KB)")


def clean_dist(output_dir: Path):
    """Supprime le dossier dist"""
    if output_dir.exists():
        shutil.rmtree(output_dir)
        print(f"🧹 Dossier {output_dir} supprimé")
    else:
        print(f"ℹ️ Dossier {output_dir} n'existe pas")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Crée une archive ZIP pour l'upload sur plugins.qgis.org"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="dist",
        help="Dossier de sortie pour l'archive (défaut: dist)"
    )
    parser.add_argument(
        "--clean", "-c",
        action="store_true",
        help="Nettoie le dossier de sortie avant de créer l'archive"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Affiche le contenu de l'archive après création"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Affiche les fichiers qui seraient inclus sans créer l'archive"
    )
    
    args = parser.parse_args()
    
    # Chemins
    plugin_dir = Path(__file__).parent.resolve()
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = plugin_dir / output_dir
    
    print(f"🔧 FilterMate - Création d'archive pour plugins.qgis.org")
    print(f"   Dossier plugin: {plugin_dir}")
    print(f"   Dossier sortie: {output_dir}")
    print()
    
    # Nettoyage
    if args.clean:
        clean_dist(output_dir)
        print()
    
    # Mode dry-run
    if args.dry_run:
        files = get_files_to_include(plugin_dir)
        print(f"📋 Fichiers qui seraient inclus ({len(files)}):")
        for f in sorted(files):
            print(f"   {f.relative_to(plugin_dir)}")
        return
    
    # Création de l'archive
    zip_path = create_archive(plugin_dir, output_dir)
    
    # Afficher le contenu
    if args.list:
        list_archive_contents(zip_path)
    
    print()
    print("🚀 Prochaines étapes:")
    print("   1. Testez le plugin en installant l'archive localement")
    print("   2. Uploadez sur https://plugins.qgis.org/plugins/")
    print(f"   3. Fichier à uploader: {zip_path}")


if __name__ == "__main__":
    main()
