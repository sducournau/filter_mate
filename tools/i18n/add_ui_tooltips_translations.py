#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to add missing tooltip translations to FilterMate_*.ts files
"""

import os
import xml.etree.ElementTree as ET
from collections import OrderedDict

# New tooltips to translate
new_tooltips = {
    'en': {
        'Multi-layer filtering': 'Multi-layer filtering',
        'Additive filtering for the selected layer': 'Additive filtering for the selected layer',
        'Geospatial filtering': 'Geospatial filtering',
        'Buffer': 'Buffer',
        'Expression layer': 'Expression layer',
        'Geometric predicate': 'Geometric predicate',
        'Value in meters': 'Value in meters',
        'Select CRS for export': 'Select CRS for export',
        'Output format': 'Output format',
        'Filter': 'Filter',
        'Reset': 'Reset',
        'Layers to export': 'Layers to export',
        'Layers projection': 'Layers projection',
        'Save styles': 'Save styles',
        'Datatype export': 'Datatype export',
        'Name of file/directory': 'Name of file/directory'
    },
    'fr': {
        'Multi-layer filtering': 'Filtrage multicouche',
        'Additive filtering for the selected layer': 'Filtrage additif pour la couche sélectionnée',
        'Geospatial filtering': 'Filtrage géospatial',
        'Buffer': 'Tampon',
        'Expression layer': 'Couche de l\'expression',
        'Geometric predicate': 'Prédicat géométrique',
        'Value in meters': 'Valeur en mètres',
        'Select CRS for export': 'Sélectionnez le CRS pour l\'export',
        'Output format': 'Format de sortie',
        'Filter': 'Filtrer',
        'Reset': 'Réinitialiser',
        'Layers to export': 'Couches à exporter',
        'Layers projection': 'Projection des couches',
        'Save styles': 'Enregistrer les styles',
        'Datatype export': 'Export du type de données',
        'Name of file/directory': 'Nom du fichier/répertoire'
    },
    'de': {
        'Multi-layer filtering': 'Mehrebenen-Filterung',
        'Additive filtering for the selected layer': 'Additive Filterung für die ausgewählte Ebene',
        'Geospatial filtering': 'Räumliche Filterung',
        'Buffer': 'Puffer',
        'Expression layer': 'Ausdrucksebene',
        'Geometric predicate': 'Geometrisches Prädikat',
        'Value in meters': 'Wert in Metern',
        'Select CRS for export': 'KBS für Export auswählen',
        'Output format': 'Ausgabeformat',
        'Filter': 'Filtern',
        'Reset': 'Zurücksetzen',
        'Layers to export': 'Zu exportierende Ebenen',
        'Layers projection': 'Ebenenprojektion',
        'Save styles': 'Stile speichern',
        'Datatype export': 'Datentyp-Export',
        'Name of file/directory': 'Datei-/Verzeichnisname'
    },
    'es': {
        'Multi-layer filtering': 'Filtrado multicapa',
        'Additive filtering for the selected layer': 'Filtrado aditivo para la capa seleccionada',
        'Geospatial filtering': 'Filtrado geoespacial',
        'Buffer': 'Búfer',
        'Expression layer': 'Capa de expresión',
        'Geometric predicate': 'Predicado geométrico',
        'Value in meters': 'Valor en metros',
        'Select CRS for export': 'Seleccionar SRC para exportar',
        'Output format': 'Formato de salida',
        'Filter': 'Filtrar',
        'Reset': 'Restablecer',
        'Layers to export': 'Capas a exportar',
        'Layers projection': 'Proyección de capas',
        'Save styles': 'Guardar estilos',
        'Datatype export': 'Exportar tipo de datos',
        'Name of file/directory': 'Nombre de archivo/directorio'
    },
    'it': {
        'Multi-layer filtering': 'Filtraggio multistrato',
        'Additive filtering for the selected layer': 'Filtraggio additivo per il layer selezionato',
        'Geospatial filtering': 'Filtraggio geospaziale',
        'Buffer': 'Buffer',
        'Expression layer': 'Layer di espressione',
        'Geometric predicate': 'Predicato geometrico',
        'Value in meters': 'Valore in metri',
        'Select CRS for export': 'Seleziona SR per esportazione',
        'Output format': 'Formato di output',
        'Filter': 'Filtra',
        'Reset': 'Reimposta',
        'Layers to export': 'Layer da esportare',
        'Layers projection': 'Proiezione dei layer',
        'Save styles': 'Salva stili',
        'Datatype export': 'Esporta tipo di dati',
        'Name of file/directory': 'Nome del file/directory'
    },
    'nl': {
        'Multi-layer filtering': 'Meerlagige filtering',
        'Additive filtering for the selected layer': 'Additieve filtering voor de geselecteerde laag',
        'Geospatial filtering': 'Geo-ruimtelijke filtering',
        'Buffer': 'Buffer',
        'Expression layer': 'Expressielaag',
        'Geometric predicate': 'Geometrisch predikaat',
        'Value in meters': 'Waarde in meters',
        'Select CRS for export': 'Selecteer CRS voor export',
        'Output format': 'Uitvoerformaat',
        'Filter': 'Filteren',
        'Reset': 'Resetten',
        'Layers to export': 'Te exporteren lagen',
        'Layers projection': 'Lagenprojectie',
        'Save styles': 'Stijlen opslaan',
        'Datatype export': 'Gegevenstype exporteren',
        'Name of file/directory': 'Naam van bestand/map'
    },
    'pt': {
        'Multi-layer filtering': 'Filtragem multicamada',
        'Additive filtering for the selected layer': 'Filtragem aditiva para a camada selecionada',
        'Geospatial filtering': 'Filtragem geoespacial',
        'Buffer': 'Buffer',
        'Expression layer': 'Camada de expressão',
        'Geometric predicate': 'Predicado geométrico',
        'Value in meters': 'Valor em metros',
        'Select CRS for export': 'Selecionar SRC para exportação',
        'Output format': 'Formato de saída',
        'Filter': 'Filtrar',
        'Reset': 'Redefinir',
        'Layers to export': 'Camadas para exportar',
        'Layers projection': 'Projeção das camadas',
        'Save styles': 'Salvar estilos',
        'Datatype export': 'Exportar tipo de dados',
        'Name of file/directory': 'Nome do arquivo/diretório'
    }
}

def add_translations_to_ts_file(filepath, lang_code):
    """Add new translation entries to a .ts file using simple text manipulation."""
    print(f"\nProcessing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the FilterMateDockWidgetBase context
    context_start = content.find('<context>\n    <name>FilterMateDockWidgetBase</name>')
    if context_start == -1:
        print(f"  ⚠ FilterMateDockWidgetBase context not found")
        return False
    
    # Find the end of this context
    context_end = content.find('</context>', context_start)
    if context_end == -1:
        print(f"  ⚠ Context end not found")
        return False
    
    # Get the context content
    context_content = content[context_start:context_end]
    
    # Check which translations are missing
    translations = new_tooltips.get(lang_code, new_tooltips['en'])
    missing_translations = []
    
    for source_text, translation_text in translations.items():
        if f'<source>{source_text}</source>' not in context_content:
            missing_translations.append((source_text, translation_text))
    
    if not missing_translations:
        print(f"  ✓ All translations already present")
        return False
    
    # Build the new translation entries
    new_entries = []
    for source_text, translation_text in missing_translations:
        # Escape XML special characters
        source_escaped = source_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
        translation_escaped = translation_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
        
        entry = f'''    <message>
        <source>{source_escaped}</source>
        <translation>{translation_escaped}</translation>
    </message>'''
        new_entries.append(entry)
        print(f"  + Adding: '{source_text}' → '{translation_text}'")
    
    # Insert before the </context> tag
    new_entries_text = '\n'.join(new_entries) + '\n'
    new_content = content[:context_end] + new_entries_text + content[context_end:]
    
    # Write the updated content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  ✓ Added {len(missing_translations)} translation(s)")
    return True

def main():
    """Main function to update all translation files."""
    i18n_dir = 'i18n'
    
    if not os.path.exists(i18n_dir):
        print(f"Error: {i18n_dir} directory not found")
        return
    
    updated_count = 0
    for lang_code in new_tooltips.keys():
        ts_file = os.path.join(i18n_dir, f'FilterMate_{lang_code}.ts')
        if os.path.exists(ts_file):
            if add_translations_to_ts_file(ts_file, lang_code):
                updated_count += 1
        else:
            print(f"⚠ File not found: {ts_file}")
    
    print(f"\n{'='*60}")
    print(f"✓ Updated {updated_count} translation file(s)")
    print(f"{'='*60}")
    
    if updated_count > 0:
        print("\nNext steps:")
        print("1. Review the changes in the .ts files")
        print("2. Compile translations:")
        print("   - Windows: Use compile_translations.bat")
        print("   - Or manually: lrelease i18n/FilterMate_*.ts")
        print("3. Restart QGIS to test the translations")

if __name__ == '__main__':
    main()
