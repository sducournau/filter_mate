#!/usr/bin/env python3
"""
Create new translation files for FilterMate.
This script creates translation files for Slovenian, Filipino, and Amharic.
"""

import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
I18N_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'i18n')

# Complete translations for new languages
# Maps source text to translations for each new language
TRANSLATIONS = {
    "sl": {  # Slovenian
        "_language_code": "sl_SI",
        "&FilterMate": "&FilterMate",
        "FilterMate": "FilterMate",
        "Open FilterMate panel": "Odpri ploščo FilterMate",
        "Reset configuration and database": "Ponastavi konfiguracijo in bazo podatkov",
        "Reset the default configuration and delete the SQLite database": "Ponastavi privzeto konfiguracijo in izbriši SQLite bazo podatkov",
        "Reset Configuration": "Ponastavi konfiguracijo",
        "Are you sure you want to reset to the default configuration?\n\nThis will:\n- Reset all FilterMate settings\n- Delete all filter history databases": "Ali ste prepričani, da želite ponastaviti privzeto konfiguracijo?\n\nTo bo:\n- Ponastavilo vse nastavitve FilterMate\n- Izbrisalo vse baze podatkov zgodovine filtrov",
        "Configuration reset successfully.": "Konfiguracija uspešno ponastavljena.",
        "Default configuration file not found.": "Privzeta konfiguracijska datoteka ni bila najdena.",
        "Database deleted: {filename}": "Baza podatkov izbrisana: {filename}",
        "Unable to delete {filename}: {error}": "Ni mogoče izbrisati {filename}: {error}",
        "Restart required": "Potreben ponovni zagon",
        "The configuration has been reset.\n\nPlease restart QGIS to apply all changes.": "Konfiguracija je bila ponastavljena.\n\nProsimo, ponovno zaženite QGIS za uporabo vseh sprememb.",
        "Error during reset: {error}": "Napaka med ponastavitvijo: {error}",
        "Obsolete configuration detected": "Zastarela konfiguracija zaznana",
        "unknown version": "neznana različica",
        "Corrupted configuration detected": "Poškodovana konfiguracija zaznana",
        "Configuration reset": "Ponastavitev konfiguracije",
        "Configuration not reset. Some features may not work correctly.": "Konfiguracija ni bila ponastavljena. Nekatere funkcije morda ne bodo delovale pravilno.",
        "Configuration created with default values": "Konfiguracija ustvarjena s privzetimi vrednostmi",
        "Corrupted configuration reset. Default settings have been restored.": "Poškodovana konfiguracija ponastavljena. Privzete nastavitve so bile obnovljene.",
        "Obsolete configuration reset. Default settings have been restored.": "Zastarela konfiguracija ponastavljena. Privzete nastavitve so bile obnovljene.",
        "Configuration updated to latest version": "Konfiguracija posodobljena na najnovejšo različico",
        "Geometry validation setting": "Nastavitev preverjanja geometrije",
        "Invalid geometry filtering disabled successfully.": "Filtriranje neveljavnih geometrij je uspešno onemogočeno.",
        "Invalid geometry filtering not modified. Some features may be excluded from exports.": "Filtriranje neveljavnih geometrij ni bilo spremenjeno. Nekatere funkcije so lahko izključene iz izvoza.",
        "SINGLE SELECTION": "ENOJNI IZBOR",
        "MULTIPLE SELECTION": "MNOŽIČNI IZBOR",
        "CUSTOM SELECTION": "PRILAGOJENI IZBOR",
        "FILTERING": "FILTRIRANJE",
        "EXPORTING": "IZVAŽANJE",
        "CONFIGURATION": "KONFIGURACIJA",
        "Identify feature - Display feature attributes": "Identificiraj element - Prikaži atribute elementa",
        "Zoom to feature - Center the map on the selected feature": "Povečaj na element - Centriraj zemljevid na izbrani element",
        "Enable selection - Select features on map": "Omogoči izbor - Izberi elemente na zemljevidu",
        "Enable tracking - Follow the selected feature on the map": "Omogoči sledenje - Sledi izbranemu elementu na zemljevidu",
        "Link widgets - Synchronize selection between widgets": "Poveži gradnike - Sinhroniziraj izbor med gradniki",
        "Reset layer properties - Restore default layer settings": "Ponastavi lastnosti sloja - Obnovi privzete nastavitve sloja",
        "Auto-sync with current layer - Automatically update when layer changes": "Samodejna sinhronizacija s trenutnim slojem - Samodejno posodobi ob spremembi sloja",
        "Enable multi-layer filtering - Apply filter to multiple layers simultaneously": "Omogoči večslojno filtriranje - Uporabi filter na več slojih hkrati",
        "Enable additive filtering - Combine multiple filters on the current layer": "Omogoči aditivno filtriranje - Združi več filtrov na trenutnem sloju",
        "Enable spatial filtering - Filter features using geometric relationships": "Omogoči prostorsko filtriranje - Filtriraj elemente z uporabo geometrijskih razmerij",
        "Enable buffer - Add a buffer zone around selected features": "Omogoči medpomnilnik - Dodaj območje medpomnilnika okoli izbranih elementov",
        "Buffer type - Select the buffer calculation method": "Vrsta medpomnilnika - Izberi metodo izračuna medpomnilnika",
        "Current layer - Select the layer to filter": "Trenutni sloj - Izberi sloj za filtriranje",
        "Apply Filter": "Uporabi filter",
        "Undo Filter": "Razveljavi filter",
        "Redo Filter": "Uveljavi filter",
        "Clear All Filters": "Počisti vse filtre",
        "Export": "Izvozi",
        "AND": "IN",
        "AND NOT": "IN NE",
        "OR": "ALI",
        "QML": "QML",
        "SLD": "SLD",
        " m": " m",
        ", ": ", ",
        "Multi-layer filtering": "Večslojno filtriranje",
        "Additive filtering for the selected layer": "Aditivno filtriranje za izbrani sloj",
        "Geospatial filtering": "Geoprostorsko filtriranje",
        "Buffer": "Medpomnilnik",
        "Expression layer": "Sloj izraza",
        "Geometric predicate": "Geometrični predikat",
        "Value in meters": "Vrednost v metrih",
        "Output format": "Izhodni format",
        "Filter": "Filter",
        "Reset": "Ponastavi",
        "Layers to export": "Sloji za izvoz",
        "Layers projection": "Projekcija slojev",
        "Save styles": "Shrani sloge",
        "Datatype export": "Izvoz podatkovnega tipa",
        "Name of file/directory": "Ime datoteke/mape",
        "Reload Plugin": "Ponovno naloži vtičnik",
        "No layer selected": "Noben sloj ni izbran",
        "Multiple layers selected": "Več slojev izbranih",
        "No layers selected": "Nobeni sloji niso izbrani",
        "No expression defined": "Noben izraz ni definiran",
        "Batch mode": "Paketni način",
    },
    "tl": {  # Filipino/Tagalog
        "_language_code": "tl_PH",
        "&FilterMate": "&FilterMate",
        "FilterMate": "FilterMate",
        "Open FilterMate panel": "Buksan ang FilterMate panel",
        "Reset configuration and database": "I-reset ang pagsasaayos at database",
        "Reset the default configuration and delete the SQLite database": "I-reset ang default na pagsasaayos at burahin ang SQLite database",
        "Reset Configuration": "I-reset ang Pagsasaayos",
        "Are you sure you want to reset to the default configuration?\n\nThis will:\n- Reset all FilterMate settings\n- Delete all filter history databases": "Sigurado ka bang gusto mong i-reset sa default na pagsasaayos?\n\nIto ay:\n- I-reset lahat ng mga setting ng FilterMate\n- Burahin lahat ng mga database ng kasaysayan ng filter",
        "Configuration reset successfully.": "Matagumpay na na-reset ang pagsasaayos.",
        "Default configuration file not found.": "Hindi nahanap ang default na file ng pagsasaayos.",
        "Database deleted: {filename}": "Nabura ang database: {filename}",
        "Unable to delete {filename}: {error}": "Hindi mabura ang {filename}: {error}",
        "Restart required": "Kailangang i-restart",
        "The configuration has been reset.\n\nPlease restart QGIS to apply all changes.": "Na-reset na ang pagsasaayos.\n\nPaki-restart ang QGIS upang mailapat ang lahat ng mga pagbabago.",
        "Error during reset: {error}": "Error sa panahon ng pag-reset: {error}",
        "Obsolete configuration detected": "Lumang pagsasaayos ang nakita",
        "unknown version": "hindi kilalang bersyon",
        "Corrupted configuration detected": "Sirang pagsasaayos ang nakita",
        "Configuration reset": "I-reset ang Pagsasaayos",
        "Configuration not reset. Some features may not work correctly.": "Hindi na-reset ang pagsasaayos. Ang ilang mga tampok ay maaaring hindi gumana ng tama.",
        "Configuration created with default values": "Ang pagsasaayos ay nilikha gamit ang mga default na halaga",
        "Corrupted configuration reset. Default settings have been restored.": "Na-reset ang sirang pagsasaayos. Naibalik na ang mga default na setting.",
        "Obsolete configuration reset. Default settings have been restored.": "Na-reset ang lumang pagsasaayos. Naibalik na ang mga default na setting.",
        "Configuration updated to latest version": "Na-update ang pagsasaayos sa pinakabagong bersyon",
        "Geometry validation setting": "Setting ng geometry validation",
        "Invalid geometry filtering disabled successfully.": "Matagumpay na na-disable ang pag-filter ng invalid na geometry.",
        "Invalid geometry filtering not modified. Some features may be excluded from exports.": "Hindi binago ang pag-filter ng invalid na geometry. Ang ilang mga tampok ay maaaring ihiwalay sa mga pag-export.",
        "SINGLE SELECTION": "SINGLE SELECTION",
        "MULTIPLE SELECTION": "MULTIPLE SELECTION",
        "CUSTOM SELECTION": "CUSTOM SELECTION",
        "FILTERING": "FILTERING",
        "EXPORTING": "EXPORTING",
        "CONFIGURATION": "CONFIGURATION",
        "Identify feature - Display feature attributes": "Tukuyin ang feature - Ipakita ang mga attribute ng feature",
        "Zoom to feature - Center the map on the selected feature": "Zoom sa feature - I-center ang mapa sa napiling feature",
        "Enable selection - Select features on map": "Paganahin ang pagpili - Pumili ng mga feature sa mapa",
        "Enable tracking - Follow the selected feature on the map": "Paganahin ang pagsubaybay - Sundan ang napiling feature sa mapa",
        "Link widgets - Synchronize selection between widgets": "I-link ang mga widget - I-synchronize ang pagpili sa pagitan ng mga widget",
        "Reset layer properties - Restore default layer settings": "I-reset ang mga property ng layer - Ibalik ang mga default na setting ng layer",
        "Auto-sync with current layer - Automatically update when layer changes": "Auto-sync sa kasalukuyang layer - Awtomatikong i-update kapag nagbago ang layer",
        "Enable multi-layer filtering - Apply filter to multiple layers simultaneously": "Paganahin ang multi-layer filtering - Ilapat ang filter sa maraming layer nang sabay-sabay",
        "Enable additive filtering - Combine multiple filters on the current layer": "Paganahin ang additive filtering - Pagsamahin ang maraming filter sa kasalukuyang layer",
        "Enable spatial filtering - Filter features using geometric relationships": "Paganahin ang spatial filtering - I-filter ang mga feature gamit ang geometric relationships",
        "Enable buffer - Add a buffer zone around selected features": "Paganahin ang buffer - Magdagdag ng buffer zone sa paligid ng mga napiling feature",
        "Buffer type - Select the buffer calculation method": "Uri ng buffer - Pumili ng paraan ng pagkalkula ng buffer",
        "Current layer - Select the layer to filter": "Kasalukuyang layer - Piliin ang layer na i-filter",
        "Apply Filter": "Ilapat ang Filter",
        "Undo Filter": "I-undo ang Filter",
        "Redo Filter": "I-redo ang Filter",
        "Clear All Filters": "Burahin Lahat ng Filter",
        "Export": "I-export",
        "AND": "AT",
        "AND NOT": "AT HINDI",
        "OR": "O",
        "QML": "QML",
        "SLD": "SLD",
        " m": " m",
        ", ": ", ",
        "Multi-layer filtering": "Multi-layer filtering",
        "Additive filtering for the selected layer": "Additive filtering para sa napiling layer",
        "Geospatial filtering": "Geospatial filtering",
        "Buffer": "Buffer",
        "Expression layer": "Expression layer",
        "Geometric predicate": "Geometric predicate",
        "Value in meters": "Halaga sa metro",
        "Output format": "Output format",
        "Filter": "Filter",
        "Reset": "I-reset",
        "Layers to export": "Mga layer na i-export",
        "Layers projection": "Projection ng mga layer",
        "Save styles": "I-save ang mga style",
        "Datatype export": "Datatype export",
        "Name of file/directory": "Pangalan ng file/directory",
        "Reload Plugin": "I-reload ang Plugin",
        "No layer selected": "Walang napiling layer",
        "Multiple layers selected": "Maraming layer ang napili",
        "No layers selected": "Walang napiling mga layer",
        "No expression defined": "Walang tinukoy na expression",
        "Batch mode": "Batch mode",
    },
    "am": {  # Amharic
        "_language_code": "am_ET",
        "&FilterMate": "&FilterMate",
        "FilterMate": "FilterMate",
        "Open FilterMate panel": "FilterMate ፓነልን ክፈት",
        "Reset configuration and database": "ውቅረትና ዳታቤዝ ዳግም አስጀምር",
        "Reset the default configuration and delete the SQLite database": "ነባሪ ውቅረትን ዳግም አስጀምርና SQLite ዳታቤዝን ሰርዝ",
        "Reset Configuration": "ውቅረት ዳግም አስጀምር",
        "Are you sure you want to reset to the default configuration?\n\nThis will:\n- Reset all FilterMate settings\n- Delete all filter history databases": "ነባሪ ውቅረት ላይ ዳግም ማስጀመር ትፈልጋለህ?\n\nይህ:\n- ሁሉንም FilterMate ቅንብሮች ዳግም ያስጀምራል\n- ሁሉንም የማጣሪያ ታሪክ ዳታቤዞች ይሰርዛል",
        "Configuration reset successfully.": "ውቅረት በተሳካ ሁኔታ ዳግም ተጀምሯል።",
        "Default configuration file not found.": "ነባሪ ውቅረት ፋይል አልተገኘም።",
        "Database deleted: {filename}": "ዳታቤዝ ተሰርዟል: {filename}",
        "Unable to delete {filename}: {error}": "{filename} መሰረዝ አልተቻለም: {error}",
        "Restart required": "ዳግም ማስጀመር ያስፈልጋል",
        "The configuration has been reset.\n\nPlease restart QGIS to apply all changes.": "ውቅረቱ ዳግም ተጀምሯል።\n\nሁሉንም ለውጦች ለማስፈጸም እባክዎ QGIS ን ዳግም ያስጀምሩ።",
        "Error during reset: {error}": "በዳግም ማስጀመር ወቅት ስህተት: {error}",
        "Obsolete configuration detected": "ያረጀ ውቅረት ተገኝቷል",
        "unknown version": "ያልታወቀ ስሪት",
        "Corrupted configuration detected": "የተበላሸ ውቅረት ተገኝቷል",
        "Configuration reset": "ውቅረት ዳግም አስጀምር",
        "Configuration not reset. Some features may not work correctly.": "ውቅረት አልተዘዋወረም። አንዳንድ ባህሪያት በትክክል ላይሰሩ ይችላሉ።",
        "Configuration created with default values": "ውቅረት በነባሪ እሴቶች ተፈጥሯል",
        "Corrupted configuration reset. Default settings have been restored.": "የተበላሸ ውቅረት ዳግም ተጀምሯል። ነባሪ ቅንብሮች ተመልሰዋል።",
        "Obsolete configuration reset. Default settings have been restored.": "ያረጀ ውቅረት ዳግም ተጀምሯል። ነባሪ ቅንብሮች ተመልሰዋል።",
        "Configuration updated to latest version": "ውቅረት ወደ አዲሱ ስሪት ተዘምኗል",
        "Geometry validation setting": "የጂኦሜትሪ ማረጋገጫ ቅንብር",
        "Invalid geometry filtering disabled successfully.": "ልክ ያልሆነ ጂኦሜትሪ ማጣራት በተሳካ ሁኔታ ተሰናክሏል።",
        "Invalid geometry filtering not modified. Some features may be excluded from exports.": "ልክ ያልሆነ ጂኦሜትሪ ማጣራት አልተሻሻለም። አንዳንድ ባህሪያት ከወጪዎች ሊገለሉ ይችላሉ።",
        "SINGLE SELECTION": "ነጠላ ምርጫ",
        "MULTIPLE SELECTION": "ብዙ ምርጫ",
        "CUSTOM SELECTION": "ብጁ ምርጫ",
        "FILTERING": "ማጣራት",
        "EXPORTING": "መላክ",
        "CONFIGURATION": "ውቅረት",
        "Identify feature - Display feature attributes": "ባህሪ ለይ - የባህሪ ባህሪያትን አሳይ",
        "Zoom to feature - Center the map on the selected feature": "ወደ ባህሪ አጉላ - ካርታውን በተመረጠው ባህሪ ላይ አስቀምጥ",
        "Enable selection - Select features on map": "ምርጫን አንቃ - በካርታ ላይ ባህሪያትን ምረጥ",
        "Enable tracking - Follow the selected feature on the map": "መከታተልን አንቃ - የተመረጠውን ባህሪ በካርታ ላይ ተከተል",
        "Link widgets - Synchronize selection between widgets": "ዊጀቶችን አገናኝ - በዊጀቶች መካከል ምርጫን አስተባብር",
        "Reset layer properties - Restore default layer settings": "የንብርብር ባህሪያትን ዳግም አስጀምር - ነባሪ የንብርብር ቅንብሮችን መልስ",
        "Auto-sync with current layer - Automatically update when layer changes": "ከአሁኑ ንብርብር ጋር በራስ-ሰር አስተባብር - ንብርብር ሲቀየር በራስ-ሰር አዘምን",
        "Enable multi-layer filtering - Apply filter to multiple layers simultaneously": "ብዙ-ንብርብር ማጣራትን አንቃ - ማጣሪያውን በአንድ ጊዜ በብዙ ንብርብሮች ላይ ተግብር",
        "Enable additive filtering - Combine multiple filters on the current layer": "ተጨማሪ ማጣራትን አንቃ - በአሁኑ ንብርብር ላይ ብዙ ማጣሪያዎችን አዋህድ",
        "Enable spatial filtering - Filter features using geometric relationships": "የቦታ ማጣራትን አንቃ - ጂኦሜትሪያዊ ግንኙነቶችን በመጠቀም ባህሪያትን አጣራ",
        "Enable buffer - Add a buffer zone around selected features": "ቋት አንቃ - በተመረጡ ባህሪያት ዙሪያ የቋት ዞን ጨምር",
        "Buffer type - Select the buffer calculation method": "የቋት አይነት - የቋት ስሌት ዘዴን ምረጥ",
        "Current layer - Select the layer to filter": "አሁኑ ንብርብር - ለማጣራት ንብርብር ምረጥ",
        "Apply Filter": "ማጣሪያ ተግብር",
        "Undo Filter": "ማጣሪያ ሻር",
        "Redo Filter": "ማጣሪያ መልስ",
        "Clear All Filters": "ሁሉንም ማጣሪያዎች አጽዳ",
        "Export": "ላክ",
        "AND": "እና",
        "AND NOT": "እና አይደለም",
        "OR": "ወይም",
        "QML": "QML",
        "SLD": "SLD",
        " m": " ሜ",
        ", ": "፣ ",
        "Multi-layer filtering": "ብዙ-ንብርብር ማጣራት",
        "Additive filtering for the selected layer": "ለተመረጠው ንብርብር ተጨማሪ ማጣራት",
        "Geospatial filtering": "ጂኦስፓሻል ማጣራት",
        "Buffer": "ቋት",
        "Expression layer": "የአገላለጽ ንብርብር",
        "Geometric predicate": "ጂኦሜትሪያዊ ቅድመ-ሁኔታ",
        "Value in meters": "እሴት በሜትር",
        "Output format": "የውጤት ቅርጸት",
        "Filter": "ማጣሪያ",
        "Reset": "ዳግም አስጀምር",
        "Layers to export": "ለመላክ ንብርብሮች",
        "Layers projection": "የንብርብሮች ትንበያ",
        "Save styles": "ቅጦችን አስቀምጥ",
        "Datatype export": "የዳታ አይነት ወጪ",
        "Name of file/directory": "የፋይል/ማውጫ ስም",
        "Reload Plugin": "ፕላጊንን ዳግም ጫን",
        "No layer selected": "ምንም ንብርብር አልተመረጠም",
        "Multiple layers selected": "ብዙ ንብርብሮች ተመርጠዋል",
        "No layers selected": "ምንም ንብርብሮች አልተመረጡም",
        "No expression defined": "ምንም አገላለጽ አልተገለጸም",
        "Batch mode": "ቡድን ሁነታ",
    },
}


def create_ts_file(lang_code, translations):
    """Create a new .ts file for the given language."""
    lang_locale = translations.pop("_language_code", f"{lang_code}_{lang_code.upper()}")
    
    # Read English template
    en_file = os.path.join(I18N_DIR, "FilterMate_en.ts")
    with open(en_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace language code in header
    content = content.replace('language="en_US"', f'language="{lang_locale}"')
    
    # Replace translations
    for source, translation in translations.items():
        # Escape for XML
        src_escaped = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")
        trans_escaped = translation.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")
        
        # Find and replace translation
        # Handle both single-line and multi-line messages
        pattern = rf'(<source>{re.escape(src_escaped)}</source>\s*<translation>)[^<]*(</translation>)'
        replacement = rf'\g<1>{trans_escaped}\g<2>'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write new file
    output_file = os.path.join(I18N_DIR, f"FilterMate_{lang_code}.ts")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Created {output_file}")


def main():
    """Create new translation files."""
    print("Creating new FilterMate translation files...")
    print(f"i18n directory: {I18N_DIR}")
    
    for lang_code, translations in TRANSLATIONS.items():
        # Make a copy to avoid modifying the original
        trans_copy = translations.copy()
        create_ts_file(lang_code, trans_copy)
    
    print("\nDone creating new translation files!")
    print("\nRemember to:")
    print("1. Update config/config.default.json with new language codes")
    print("2. Compile translations with: python compile_translations.py")


if __name__ == "__main__":
    main()
