#!/usr/bin/env python3
"""Complete remaining language translations for FilterMate"""

import xml.etree.ElementTree as ET
import subprocess
import os

# Final batch of translations
FINAL_TRANSLATIONS = {
    'fi': {  # Finnish
        "All layers using auto-selection": "Kaikki tasot käyttävät automaattista valintaa",
        "Applied to '{0}':\n{1}": "Sovellettu kohteeseen '{0}':\n{1}",
        "Auto-centroid {0}": "Automaattinen keskipiste {0}",
        "Auto-optimization {0}": "Automaattinen optimointi {0}",
        "Auto-optimizer module not available": "Automaattisen optimoinnin moduuli ei saatavilla",
        "Auto-optimizer not available: {0}": "Automaattinen optimoija ei saatavilla: {0}",
        "Auto-selected backends for {0} layer(s)": "Automaattisesti valitut taustaohjelmat {0} tasolle/tasoille",
        "Backend controller not available": "Taustaohjelman ohjain ei saatavilla",
        "Backend forced to {0} for '{1}'": "Taustaohjelma pakotettu tilaan {0} kohteelle '{1}'",
        "Backend optimization unavailable": "Taustaohjelman optimointi ei saatavilla",
        "Backend set to Auto for '{0}'": "Taustaohjelma asetettu tilaan Auto kohteelle '{0}'",
        "Clear ALL FilterMate temporary tables from all databases": "Tyhjennä KAIKKI FilterMaten väliaikaiset taulut kaikista tietokannoista",
        "Clear temporary tables for the current project only": "Tyhjennä väliaikaiset taulut vain nykyisestä projektista",
        "Cleared {0} temporary table(s) for current project": "Tyhjennetty {0} väliaikaista taulua nykyisestä projektista",
        "Cleared {0} temporary table(s) globally": "Tyhjennetty {0} väliaikaista taulua globaalisti",
        "Confirmation {0}": "Vahvistus {0}",
        "Could not analyze layer '{0}'": "Tasoa '{0}' ei voitu analysoida",
        "Could not reload plugin automatically.": "Laajennusta ei voitu ladata automaattisesti uudelleen.",
        "Dark mode": "Tumma tila",
        "Description (auto-generated, you can modify it)": "Kuvaus (automaattisesti luotu, voit muokata sitä)",
        "Dialog not available: {0}": "Valintaikkuna ei saatavilla: {0}",
        "Enter a name for this filter": "Anna tälle suodattimelle nimi",
        "Error analyzing layer: {0}": "Virhe analysoitaessa tasoa: {0}",
        "Error cancelling changes: {0}": "Virhe peruutettaessa muutoksia: {0}",
        "Error reloading plugin: {0}": "Virhe ladattaessa laajennusta uudelleen: {0}",
        "Error: {0}": "Virhe: {0}",
        "Favorites manager not available": "Suosikkien hallinta ei saatavilla",
        "Filter history position": "Sijainti suodatinhistoriassa",
        "FilterMate - Add to Favorites": "FilterMate - Lisää suosikkeihin",
        "Forced {0} backend for {1} layer(s)": "Pakotettu {0} taustaohjelma {1} tasolle/tasoille",
        "Initialization error: {}": "Alustusvirhe: {}",
        "Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}": "Taso '{0}' on jo optimaalisesti määritetty.\nTyyppi: {1}\nKohteet: {2:,}",
        "Light mode": "Vaalea tila",
        "No PostgreSQL connection available": "PostgreSQL-yhteyttä ei saatavilla",
        "No alternative backends available for this layer": "Tälle tasolle ei ole vaihtoehtoisia taustaohjelmia",
        "No layer selected. Please select a layer first.": "Tasoa ei valittu. Valitse ensin taso.",
        "No optimizations selected to apply.": "Sovellettavia optimointeja ei valittu.",
        "No temporary tables found": "Väliaikaisia tauluja ei löytynyt",
        "No temporary tables found for current project": "Nykyisestä projektista ei löytynyt väliaikaisia tauluja",
        "No views to clean or cleanup failed": "Ei puhdistettavia näkymiä tai puhdistus epäonnistui",
        "Optimized {0} layer(s)": "Optimoitu {0} taso/tasoa",
        "Other Sessions Active": "Muut istunnot aktiivisia",
        "Plugin activated with {0} vector layer(s)": "Laajennus aktivoitu {0} vektoritasolla/tasoilla",
        "PostgreSQL auto-cleanup disabled": "PostgreSQL automaattinen puhdistus poistettu käytöstä",
        "PostgreSQL auto-cleanup enabled": "PostgreSQL automaattinen puhdistus käytössä",
        "PostgreSQL session views cleaned up": "PostgreSQL-istunnon näkymät puhdistettu",
        "Redo filter (Ctrl+Y)": "Tee suodatin uudelleen (Ctrl+Y)",
        "Schema '{0}' dropped successfully": "Rakenne '{0}' poistettu onnistuneesti",
        "Schema cleanup cancelled": "Rakenteen puhdistus peruutettu",
        "Schema cleanup failed": "Rakenteen puhdistus epäonnistui",
        "Schema has {0} view(s) from other sessions.\nDrop anyway?": "Rakenteella on {0} näkymää muista istunnoista.\nPoista silti?",
        "The selected layer is invalid or its source cannot be found.": "Valittu taso on virheellinen tai sen lähdettä ei löydy.",
        "Theme adapted: {0}": "Teema mukautettu: {0}",
        "UI configuration incomplete - check logs": "Käyttöliittymän määritys puutteellinen - tarkista lokit",
        "UI dimension error: {}": "Käyttöliittymän mitta-virhe: {}",
        "Undo last filter (Ctrl+Z)": "Kumoa viimeisin suodatin (Ctrl+Z)",
        "disabled": "poistettu käytöstä",
        "enabled": "käytössä",
        "★ No favorites saved\nClick to add current filter": "★ Ei tallennettuja suosikkeja\nNapsauta lisätäksesi nykyisen suodattimen",
        "★ {0} Favorites saved\nClick to apply or manage": "★ {0} suosikkia tallennettu\nNapsauta soveltaaksesi tai hallitaksesi",
        "⚙️ Manage favorites...": "⚙️ Hallitse suosikkeja...",
        "⭐ Add Current Filter (no filter active)": "⭐ Lisää nykyinen suodatin (ei aktiivista suodatinta)",
        "⭐ Add Current Filter to Favorites": "⭐ Lisää nykyinen suodatin suosikkeihin",
        "⭐ Add current filter to favorites": "⭐ Lisää nykyinen suodatin suosikkeihin",
        "⭐ Add filter (no active filter)": "⭐ Lisää suodatin (ei aktiivista suodatinta)",
        "🌐 All Projects (Global)": "🌐 Kaikki projektit (Globaali)",
        "📁 Current Project": "📁 Nykyinen projekti",
        "📤 Export...": "📤 Vie...",
        "📥 Import...": "📥 Tuo...",
    },
    'nb': {  # Norwegian
        "All layers using auto-selection": "Alle lag bruker automatisk valg",
        "Applied to '{0}':\n{1}": "Anvendt på '{0}':\n{1}",
        "Auto-centroid {0}": "Auto-sentroid {0}",
        "Auto-optimization {0}": "Auto-optimalisering {0}",
        "Auto-optimizer module not available": "Auto-optimaliseringsmodul ikke tilgjengelig",
        "Auto-optimizer not available: {0}": "Auto-optimalisering ikke tilgjengelig: {0}",
        "Auto-selected backends for {0} layer(s)": "Automatisk valgte backends for {0} lag",
        "Backend controller not available": "Backend-kontroller ikke tilgjengelig",
        "Backend forced to {0} for '{1}'": "Backend tvunget til {0} for '{1}'",
        "Backend optimization unavailable": "Backend-optimalisering ikke tilgjengelig",
        "Backend set to Auto for '{0}'": "Backend satt til Auto for '{0}'",
        "Clear ALL FilterMate temporary tables from all databases": "Fjern ALLE FilterMate midlertidige tabeller fra alle databaser",
        "Clear temporary tables for the current project only": "Fjern midlertidige tabeller kun for gjeldende prosjekt",
        "Cleared {0} temporary table(s) for current project": "Fjernet {0} midlertidig(e) tabell(er) for gjeldende prosjekt",
        "Cleared {0} temporary table(s) globally": "Fjernet {0} midlertidig(e) tabell(er) globalt",
        "Confirmation {0}": "Bekreftelse {0}",
        "Could not analyze layer '{0}'": "Kunne ikke analysere lag '{0}'",
        "Could not reload plugin automatically.": "Kunne ikke laste inn plugin automatisk.",
        "Dark mode": "Mørk modus",
        "Description (auto-generated, you can modify it)": "Beskrivelse (auto-generert, du kan endre den)",
        "Dialog not available: {0}": "Dialog ikke tilgjengelig: {0}",
        "Enter a name for this filter": "Skriv inn et navn for dette filteret",
        "Error analyzing layer: {0}": "Feil ved analyse av lag: {0}",
        "Error cancelling changes: {0}": "Feil ved avbrytelse av endringer: {0}",
        "Error reloading plugin: {0}": "Feil ved innlasting av plugin: {0}",
        "Error: {0}": "Feil: {0}",
        "Favorites manager not available": "Favorittbehandler ikke tilgjengelig",
        "Filter history position": "Posisjon i filterhistorikk",
        "FilterMate - Add to Favorites": "FilterMate - Legg til i favoritter",
        "Forced {0} backend for {1} layer(s)": "Tvunget {0} backend for {1} lag",
        "Initialization error: {}": "Initialiseringsfeil: {}",
        "Layer '{0}' is already optimally configured.\nType: {1}\nFeatures: {2:,}": "Lag '{0}' er allerede optimalt konfigurert.\nType: {1}\nFunksjoner: {2:,}",
        "Light mode": "Lys modus",
        "No PostgreSQL connection available": "Ingen PostgreSQL-tilkobling tilgjengelig",
        "No alternative backends available for this layer": "Ingen alternative backends tilgjengelige for dette laget",
        "No layer selected. Please select a layer first.": "Ingen lag valgt. Vennligst velg et lag først.",
        "No optimizations selected to apply.": "Ingen optimaliseringer valgt å anvende.",
        "No temporary tables found": "Ingen midlertidige tabeller funnet",
        "No temporary tables found for current project": "Ingen midlertidige tabeller funnet for gjeldende prosjekt",
        "No views to clean or cleanup failed": "Ingen visninger å rydde eller opprydding mislyktes",
        "Optimized {0} layer(s)": "Optimaliserte {0} lag",
        "Other Sessions Active": "Andre økter aktive",
        "Plugin activated with {0} vector layer(s)": "Plugin aktivert med {0} vektorlag",
        "PostgreSQL auto-cleanup disabled": "PostgreSQL auto-opprydding deaktivert",
        "PostgreSQL auto-cleanup enabled": "PostgreSQL auto-opprydding aktivert",
        "PostgreSQL session views cleaned up": "PostgreSQL-øktsvisninger ryddet opp",
        "Redo filter (Ctrl+Y)": "Gjør om filter (Ctrl+Y)",
        "Schema '{0}' dropped successfully": "Skjema '{0}' fjernet vellykket",
        "Schema cleanup cancelled": "Skjema-opprydding avbrutt",
        "Schema cleanup failed": "Skjema-opprydding mislyktes",
        "Schema has {0} view(s) from other sessions.\nDrop anyway?": "Skjema har {0} visning(er) fra andre økter.\nFjern likevel?",
        "The selected layer is invalid or its source cannot be found.": "Det valgte laget er ugyldig eller kilden kan ikke finnes.",
        "Theme adapted: {0}": "Tema tilpasset: {0}",
        "UI configuration incomplete - check logs": "UI-konfigurasjon ufullstendig - sjekk logger",
        "UI dimension error: {}": "UI-dimensjonsfeil: {}",
        "Undo last filter (Ctrl+Z)": "Angre siste filter (Ctrl+Z)",
        "disabled": "deaktivert",
        "enabled": "aktivert",
        "★ No favorites saved\nClick to add current filter": "★ Ingen favoritter lagret\nKlikk for å legge til gjeldende filter",
        "★ {0} Favorites saved\nClick to apply or manage": "★ {0} favoritter lagret\nKlikk for å anvende eller administrere",
        "⚙️ Manage favorites...": "⚙️ Administrer favoritter...",
        "⭐ Add Current Filter (no filter active)": "⭐ Legg til gjeldende filter (ingen filter aktiv)",
        "⭐ Add Current Filter to Favorites": "⭐ Legg til gjeldende filter i favoritter",
        "⭐ Add current filter to favorites": "⭐ Legg til gjeldende filter i favoritter",
        "⭐ Add filter (no active filter)": "⭐ Legg til filter (ingen aktiv filter)",
        "🌐 All Projects (Global)": "🌐 Alle prosjekter (Globalt)",
        "📁 Current Project": "📁 Gjeldende prosjekt",
        "📤 Export...": "📤 Eksporter...",
        "📥 Import...": "📥 Importer...",
    },
}

def update_translations_for_language(lang_code, translations):
    """Update translations for a specific language"""
    
    ts_file = f'i18n/FilterMate_{lang_code}.ts'
    
    try:
        # Parse files
        en_tree = ET.parse('i18n/FilterMate_en.ts')
        lang_tree = ET.parse(ts_file)
        
        en_root = en_tree.getroot()
        lang_root = lang_tree.getroot()
        
        # Get existing sources
        lang_sources = {msg.find('source').text for msg in lang_root.findall('.//message')}
        
        # Get the context element
        lang_context = lang_root.find('context')
        
        # Find and add missing messages
        added = 0
        for en_msg in en_root.findall('.//message'):
            source_text = en_msg.find('source').text
            
            if source_text not in lang_sources and source_text in translations:
                # Create new message element
                new_msg = ET.Element('message')
                
                # Add source
                source = ET.SubElement(new_msg, 'source')
                source.text = source_text
                
                # Add translation
                translation = ET.SubElement(new_msg, 'translation')
                translation.text = translations[source_text]
                
                # Add to context
                lang_context.append(new_msg)
                added += 1
        
        if added > 0:
            # Write back to file with proper formatting
            ET.indent(lang_tree, space='    ')
            lang_tree.write(ts_file, encoding='utf-8', xml_declaration=True)
            
            # Compile the .qm file
            qm_file = ts_file.replace('.ts', '.qm')
            result = subprocess.run(
                ['/home/simon/anaconda3/bin/lrelease', ts_file, '-qm', qm_file],
                capture_output=True,
                text=True
            )
            
            print(f"✅ {lang_code.upper()}: Added {added} translations")
            if result.stdout:
                print(f"   {result.stdout.strip()}")
        else:
            print(f"✅ {lang_code.upper()}: Already complete!")
            
    except Exception as e:
        print(f"❌ {lang_code.upper()}: Error - {e}")

def main():
    """Update final translation files"""
    
    print("=== FilterMate Final Translation Update ===\n")
    
    # Change to plugin directory
    os.chdir('/mnt/c/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate')
    
    # Update remaining languages
    for lang_code, translations in FINAL_TRANSLATIONS.items():
        update_translations_for_language(lang_code, translations)
    
    print("\n=== Final translation update complete! ===")
    print("\n🎉 All major languages now have complete or near-complete translations!")

if __name__ == '__main__':
    main()
