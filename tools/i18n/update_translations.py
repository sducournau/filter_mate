#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to add new translation strings to all FilterMate_*.ts files
"""

import os
import re

# New translations to add in each language
translations = {
    'de': {
        'Current layer: {0}': 'Aktuelle Ebene: {0}',
        'Selected layers:\n{0}': 'Ausgewählte Ebenen:\n{0}',
        'Expression:\n{0}': 'Ausdruck:\n{0}',
        'Expression: {0}': 'Ausdruck: {0}',
        'Display expression: {0}': 'Anzeigeausdruck: {0}',
        'Feature ID: {0}\nFirst attribute: {1}': 'Feature-ID: {0}\nErstes Attribut: {1}'
    },
    'es': {
        'Current layer: {0}': 'Capa actual: {0}',
        'Selected layers:\n{0}': 'Capas seleccionadas:\n{0}',
        'Expression:\n{0}': 'Expresión:\n{0}',
        'Expression: {0}': 'Expresión: {0}',
        'Display expression: {0}': 'Expresión de visualización: {0}',
        'Feature ID: {0}\nFirst attribute: {1}': 'ID de entidad: {0}\nPrimer atributo: {1}'
    },
    'it': {
        'Current layer: {0}': 'Layer corrente: {0}',
        'Selected layers:\n{0}': 'Layer selezionati:\n{0}',
        'Expression:\n{0}': 'Espressione:\n{0}',
        'Expression: {0}': 'Espressione: {0}',
        'Display expression: {0}': 'Espressione di visualizzazione: {0}',
        'Feature ID: {0}\nFirst attribute: {1}': 'ID entità: {0}\nPrimo attributo: {1}'
    },
    'nl': {
        'Current layer: {0}': 'Huidige laag: {0}',
        'Selected layers:\n{0}': 'Geselecteerde lagen:\n{0}',
        'Expression:\n{0}': 'Expressie:\n{0}',
        'Expression: {0}': 'Expressie: {0}',
        'Display expression: {0}': 'Weergave-expressie: {0}',
        'Feature ID: {0}\nFirst attribute: {1}': 'Feature-ID: {0}\nEerste attribuut: {1}'
    },
    'pt': {
        'Current layer: {0}': 'Camada atual: {0}',
        'Selected layers:\n{0}': 'Camadas selecionadas:\n{0}',
        'Expression:\n{0}': 'Expressão:\n{0}',
        'Expression: {0}': 'Expressão: {0}',
        'Display expression: {0}': 'Expressão de exibição: {0}',
        'Feature ID: {0}\nFirst attribute: {1}': 'ID da feição: {0}\nPrimeiro atributo: {1}'
    }
}

def escape_xml(text):
    """Escape special XML characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

def add_translations_to_file(filepath, lang_code):
    """Add new translation entries to a .ts file."""
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the FilterMateDockWidget context and the insertion point
    pattern = r'(<message>\s*<source>Feature ID: \{id\}</source>.*?</message>)\s*(</context>\s*<context>\s*<name>FeedbackUtils</name>)'
    
    # Build the new entries
    new_entries = []
    for source, translation in translations[lang_code].items():
        # Escape XML and handle newlines
        source_escaped = escape_xml(source)
        translation_escaped = escape_xml(translation)
        
        entry = f"""    <message>
        <source>{source_escaped}</source>
        <translation>{translation_escaped}</translation>
    </message>"""
        new_entries.append(entry)
    
    new_entries_str = '\n'.join(new_entries)
    
    # Replace with the new content
    replacement = r'\1\n' + new_entries_str + r'\n\2'
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✓ Updated {filepath}")
        return True
    else:
        print(f"⚠ No changes needed for {filepath} (pattern not found)")
        return False

def main():
    """Main function to update all translation files."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    i18n_dir = os.path.join(script_dir, 'i18n')
    
    updated_count = 0
    for lang_code in translations.keys():
        ts_file = os.path.join(i18n_dir, f'FilterMate_{lang_code}.ts')
        if os.path.exists(ts_file):
            if add_translations_to_file(ts_file, lang_code):
                updated_count += 1
        else:
            print(f"⚠ File not found: {ts_file}")
    
    print(f"\n✓ Updated {updated_count} translation file(s)")
    print("\nNext steps:")
    print("1. Review the changes in the .ts files")
    print("2. Compile translations with: lrelease i18n/*.ts")
    print("   or use your compile_ui.bat/sh script")
    print("3. Restart QGIS to test the translations")

if __name__ == '__main__':
    main()
