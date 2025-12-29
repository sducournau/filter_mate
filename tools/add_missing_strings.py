#!/usr/bin/env python3
"""
Add missing translatable strings to all FilterMate translation files.
"""

import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Base directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
I18N_DIR = os.path.join(PLUGIN_DIR, 'i18n')

# Missing strings with translations
MISSING_STRINGS = {
    "Buffer value in meters (positive=expand, negative=shrink polygons)": {
        "en": "Buffer value in meters (positive=expand, negative=shrink polygons)",
        "fr": "Valeur du tampon en mètres (positif=agrandir, négatif=réduire les polygones)",
        "de": "Pufferwert in Metern (positiv=erweitern, negativ=verkleinern von Polygonen)",
        "es": "Valor del búfer en metros (positivo=expandir, negativo=reducir polígonos)",
        "it": "Valore buffer in metri (positivo=espandi, negativo=riduci poligoni)",
        "nl": "Bufferwaarde in meters (positief=uitbreiden, negatief=verkleinen polygonen)",
        "pt": "Valor do buffer em metros (positivo=expandir, negativo=encolher polígonos)",
        "pl": "Wartość bufora w metrach (dodatnia=rozszerz, ujemna=zmniejsz wielokąty)",
        "zh": "缓冲区值（米）（正值=扩展，负值=收缩多边形）",
        "ru": "Значение буфера в метрах (положительное=расширить, отрицательное=сжать полигоны)",
        "id": "Nilai buffer dalam meter (positif=perluas, negatif=perkecil poligon)",
        "vi": "Giá trị đệm tính bằng mét (dương=mở rộng, âm=thu nhỏ đa giác)",
        "tr": "Metre cinsinden tampon değeri (pozitif=genişlet, negatif=daralt poligonlar)",
        "hi": "मीटर में बफर मान (सकारात्मक=विस्तार, नकारात्मक=बहुभुज सिकुड़ें)",
        "fi": "Puskurin arvo metreinä (positiivinen=laajenna, negatiivinen=kutista polygoneja)",
        "da": "Bufferværdi i meter (positiv=udvid, negativ=formindsk polygoner)",
        "sv": "Buffervärde i meter (positivt=expandera, negativt=krympa polygoner)",
        "nb": "Bufferverdi i meter (positiv=utvid, negativ=krymp polygoner)",
        "sl": "Vrednost medpomnilnika v metrih (pozitivno=razširi, negativno=skrči poligone)",
        "tl": "Halaga ng buffer sa metro (positibo=palawakin, negatibo=paliitin ang mga polygon)",
        "am": "በሜትር ውስጥ የቋት ዋጋ (አዎንታዊ=ማስፋፋት, አሉታዊ=ፖሊጎኖችን መቀነስ)",
        "uz": "Bufer qiymati metrda (musbat=kengaytirish, manfiy=poligonlarni qisqartirish)",
    },
    "Negative buffer (erosion): shrinks polygons inward": {
        "en": "Negative buffer (erosion): shrinks polygons inward",
        "fr": "Tampon négatif (érosion) : réduit les polygones vers l'intérieur",
        "de": "Negativer Puffer (Erosion): verkleinert Polygone nach innen",
        "es": "Búfer negativo (erosión): reduce los polígonos hacia el interior",
        "it": "Buffer negativo (erosione): riduce i poligoni verso l'interno",
        "nl": "Negatieve buffer (erosie): verkleint polygonen naar binnen",
        "pt": "Buffer negativo (erosão): encolhe polígonos para dentro",
        "pl": "Bufor ujemny (erozja): zmniejsza wielokąty do wewnątrz",
        "zh": "负缓冲区（侵蚀）：向内收缩多边形",
        "ru": "Отрицательный буфер (эрозия): сжимает полигоны внутрь",
        "id": "Buffer negatif (erosi): memperkecil poligon ke dalam",
        "vi": "Đệm âm (xói mòn): thu nhỏ đa giác vào trong",
        "tr": "Negatif tampon (erozyon): poligonları içe doğru daraltır",
        "hi": "नकारात्मक बफर (क्षरण): बहुभुज को अंदर की ओर सिकोड़ता है",
        "fi": "Negatiivinen puskuri (eroosio): kutistaa polygoneja sisäänpäin",
        "da": "Negativ buffer (erosion): formindsker polygoner indad",
        "sv": "Negativ buffert (erosion): krymper polygoner inåt",
        "nb": "Negativ buffer (erosjon): krymper polygoner innover",
        "sl": "Negativni medpomnilnik (erozija): skrči poligone navznoter",
        "tl": "Negatibong buffer (erosyon): pinaliit ang mga polygon papasok",
        "am": "አሉታዊ ቋት (መሸርሸር)፡ ፖሊጎኖችን ወደ ውስጥ ያሳንሳል",
        "uz": "Manfiy bufer (eroziya): poligonlarni ichkariga qisqartiradi",
    },
    "point": {
        "en": "point",
        "fr": "point",
        "de": "Punkt",
        "es": "punto",
        "it": "punto",
        "nl": "punt",
        "pt": "ponto",
        "pl": "punkt",
        "zh": "点",
        "ru": "точка",
        "id": "titik",
        "vi": "điểm",
        "tr": "nokta",
        "hi": "बिंदु",
        "fi": "piste",
        "da": "punkt",
        "sv": "punkt",
        "nb": "punkt",
        "sl": "točka",
        "tl": "punto",
        "am": "ነጥብ",
        "uz": "nuqta",
    },
    "line": {
        "en": "line",
        "fr": "ligne",
        "de": "Linie",
        "es": "línea",
        "it": "linea",
        "nl": "lijn",
        "pt": "linha",
        "pl": "linia",
        "zh": "线",
        "ru": "линия",
        "id": "garis",
        "vi": "đường",
        "tr": "çizgi",
        "hi": "रेखा",
        "fi": "viiva",
        "da": "linje",
        "sv": "linje",
        "nb": "linje",
        "sl": "črta",
        "tl": "linya",
        "am": "መስመር",
        "uz": "chiziq",
    },
    "non-polygon": {
        "en": "non-polygon",
        "fr": "non-polygone",
        "de": "Nicht-Polygon",
        "es": "no-polígono",
        "it": "non-poligono",
        "nl": "geen-polygoon",
        "pt": "não-polígono",
        "pl": "nie-wielokąt",
        "zh": "非多边形",
        "ru": "не-полигон",
        "id": "bukan-poligon",
        "vi": "không phải đa giác",
        "tr": "çokgen-olmayan",
        "hi": "गैर-बहुभुज",
        "fi": "ei-polygoni",
        "da": "ikke-polygon",
        "sv": "icke-polygon",
        "nb": "ikke-polygon",
        "sl": "ne-poligon",
        "tl": "hindi-polygon",
        "am": "ባልሆነ-ፖሊጎን",
        "uz": "ko'pburchak-emas",
    },
    "Mode batch": {
        "en": "Batch mode",
        "fr": "Mode batch",
        "de": "Batch-Modus",
        "es": "Modo por lotes",
        "it": "Modalità batch",
        "nl": "Batchmodus",
        "pt": "Modo batch",
        "pl": "Tryb wsadowy",
        "zh": "批处理模式",
        "ru": "Пакетный режим",
        "id": "Mode batch",
        "vi": "Chế độ batch",
        "tr": "Toplu işlem modu",
        "hi": "बैच मोड",
        "fi": "Eräkäsittely-tila",
        "da": "Batch-tilstand",
        "sv": "Batchläge",
        "nb": "Batch-modus",
        "sl": "Paketni način",
        "tl": "Batch mode",
        "am": "የባች ሁነታ",
        "uz": "Ommaviy rejim",
    },
}

def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ", encoding='utf-8').decode('utf-8')

def add_strings_to_ts_file(filepath, lang_code):
    """Add missing strings to a translation file."""
    print(f"Processing {os.path.basename(filepath)}...")
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Find the first context
        context = root.find('context')
        if context is None:
            print(f"  ERROR: No context found in {filepath}")
            return False
        
        # Get existing source strings
        existing_sources = set()
        for message in context.findall('message'):
            source = message.find('source')
            if source is not None and source.text:
                existing_sources.add(source.text)
        
        # Add missing strings
        added_count = 0
        for source_text, translations in MISSING_STRINGS.items():
            if source_text not in existing_sources:
                translation_text = translations.get(lang_code, translations.get("en", source_text))
                
                # Create new message element
                message = ET.SubElement(context, 'message')
                source_elem = ET.SubElement(message, 'source')
                source_elem.text = source_text
                translation_elem = ET.SubElement(message, 'translation')
                translation_elem.text = translation_text
                
                added_count += 1
        
        if added_count > 0:
            # Write back to file with proper formatting
            tree.write(filepath, encoding='utf-8', xml_declaration=True)
            print(f"  ✓ Added {added_count} string(s)")
            return True
        else:
            print(f"  ℹ No new strings needed")
            return False
            
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def main():
    """Main function."""
    print("Adding missing strings to FilterMate translation files")
    print("=" * 60)
    print()
    
    # Get all .ts files
    ts_files = [f for f in os.listdir(I18N_DIR) if f.endswith('.ts')]
    
    if not ts_files:
        print("ERROR: No .ts files found!")
        return
    
    print(f"Found {len(ts_files)} translation file(s)\n")
    
    updated_count = 0
    for ts_file in sorted(ts_files):
        # Extract language code (e.g., FilterMate_fr.ts -> fr)
        lang_code = ts_file.replace('FilterMate_', '').replace('.ts', '')
        filepath = os.path.join(I18N_DIR, ts_file)
        
        if add_strings_to_ts_file(filepath, lang_code):
            updated_count += 1
    
    print()
    print("=" * 60)
    print(f"Updated {updated_count} file(s)")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Verify translations: python3 tools/verify_all_translations.py")
    print("  2. Compile translations: python3 tools/i18n/compile_ts_to_qm.py")

if __name__ == "__main__":
    main()
