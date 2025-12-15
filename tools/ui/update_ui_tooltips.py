#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to update tooltips in the .ui file from French to English
"""

import re

# Define replacements
replacements = {
    'Filtrage multicouche': 'Multi-layer filtering',
    'Filtrage additif pour la couche sélectionnée': 'Additive filtering for the selected layer',
    'Filtrage géospatial': 'Geospatial filtering',
    'Tampon': 'Buffer',
    "Couche de l'expression": 'Expression layer',
    'Prédicat géométrique': 'Geometric predicate',
    'Valeur en mètres': 'Value in meters',
    "Sélectionnez le CRS pour l'export": 'Select CRS for export',
    'Format de sortie': 'Output format',
    'Filtrer': 'Filter',
    'Réinitialiser': 'Reset'
}

def update_ui_file(filepath):
    """Update tooltips in .ui file."""
    print(f"Reading {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = 0
    
    # Replace each tooltip - no need for regex
    for french, english in replacements.items():
        search_str = f'<string>{french}</string>'
        replacement_str = f'<string>{english}</string>'
        if search_str in content:
            content = content.replace(search_str, replacement_str)
            changes_made += 1
            print(f"  Replacing: '{french}' → '{english}'")
        
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Updated {filepath}")
        
        # Show what was replaced
        for french, english in replacements.items():
            count = original_content.count(f'<string>{french}</string>')
            if count > 0:
                print(f"  - '{french}' → '{english}' ({count} occurrence(s))")
        
        return True
    else:
        print(f"⚠ No changes needed")
        return False

def main():
    ui_file = 'filter_mate_dockwidget_base.ui'
    
    if update_ui_file(ui_file):
        print("\n✓ UI file updated successfully!")
        print("\nNext steps:")
        print("1. Recompile the .ui file: compile_ui.bat")
        print("2. Update translation files with pylupdate5")
        print("3. Translate the new strings in each .ts file")
        print("4. Recompile translations: lrelease i18n/*.ts")
    else:
        print("\n⚠ No updates were made")

if __name__ == '__main__':
    main()
