#!/usr/bin/env python3
"""Fix the last missing translation."""
import xml.etree.ElementTree as ET
import os

MISSING_TRANS = {
    "Use centroids instead of full geometries for distant layers (faster for complex polygons)": {
        "am": "ለርቀት ንብርብሮች ሙሉ ጂኦሜትሪዎች ፈንታ ማእከላትን ይጠቀሙ (ለውስብስብ ፖሊጎኖች ፈጣን)",
        "da": "Brug centroider i stedet for fulde geometrier for fjerne lag (hurtigere for komplekse polygoner)",
        "de": "Zentroide anstelle von vollständigen Geometrien für entfernte Layer verwenden (schneller für komplexe Polygone)",
        "en": "Use centroids instead of full geometries for distant layers (faster for complex polygons)",
        "es": "Usar centroides en lugar de geometrías completas para capas distantes (más rápido para polígonos complejos)",
        "fi": "Käytä keskipisteitä täysien geometrioiden sijaan etäisille tasoille (nopeampi monimutkaisille monikulmioille)",
        "fr": "Utiliser les centroïdes au lieu des géométries complètes pour les couches distantes (plus rapide pour les polygones complexes)",
        "hi": "दूरस्थ परतों के लिए पूर्ण ज्यामिति के बजाय सेंट्रॉइड का उपयोग करें (जटिल बहुभुजों के लिए तेज़)",
        "id": "Gunakan sentroid alih-alih geometri penuh untuk lapisan jauh (lebih cepat untuk poligon kompleks)",
        "it": "Usa centroidi invece di geometrie complete per layer distanti (più veloce per poligoni complessi)",
        "nb": "Bruk sentroider i stedet for fulle geometrier for fjerne lag (raskere for komplekse polygoner)",
        "nl": "Gebruik zwaartepunten in plaats van volledige geometrieën voor verre lagen (sneller voor complexe polygonen)",
        "pl": "Użyj centroidów zamiast pełnych geometrii dla odległych warstw (szybsze dla złożonych wielokątów)",
        "pt": "Usar centróides em vez de geometrias completas para camadas distantes (mais rápido para polígonos complexos)",
        "ru": "Использовать центроиды вместо полных геометрий для удаленных слоев (быстрее для сложных полигонов)",
        "sl": "Uporabi centroide namesto polnih geometrij za oddaljene sloje (hitreje za kompleksne poligone)",
        "sv": "Använd centroider istället för fulla geometrier för avlägsna lager (snabbare för komplexa polygoner)",
        "tl": "Gumamit ng mga sentroid sa halip na buong geometries para sa malalayong layer (mas mabilis para sa mga kumplikadong polygon)",
        "tr": "Uzak katmanlar için tam geometriler yerine sentroidler kullan (karmaşık çokgenler için daha hızlı)",
        "uz": "Uzoq qatlamlar uchun to'liq geometriyalar o'rniga markazlardan foydalaning (murakkab ko'pburchaklar uchun tezroq)",
        "vi": "Sử dụng trọng tâm thay vì hình học đầy đủ cho các lớp xa (nhanh hơn cho đa giác phức tạp)",
        "zh": "对远距离图层使用质心而不是完整几何（复杂多边形更快）"
    },
    "Use centroids instead of full geometries for distant layers (faster for complex polygons like buildings)": {
        "am": "ለርቀት ንብርብሮች ሙሉ ጂኦሜትሪዎች ፈንታ ማእከላትን ይጠቀሙ (እንደ ሕንፃዎች ለውስብስብ ፖሊጎኖች ፈጣን)",
        "da": "Brug centroider i stedet for fulde geometrier for fjerne lag (hurtigere for komplekse polygoner som bygninger)",
        "de": "Zentroide anstelle von vollständigen Geometrien für entfernte Layer verwenden (schneller für komplexe Polygone wie Gebäude)",
        "en": "Use centroids instead of full geometries for distant layers (faster for complex polygons like buildings)",
        "es": "Usar centroides en lugar de geometrías completas para capas distantes (más rápido para polígonos complejos como edificios)",
        "fi": "Käytä keskipisteitä täysien geometrioiden sijaan etäisille tasoille (nopeampi monimutkaisille monikulmioille kuten rakennuksille)",
        "fr": "Utiliser les centroïdes au lieu des géométries complètes pour les couches distantes (plus rapide pour les polygones complexes comme les bâtiments)",
        "hi": "दूरस्थ परतों के लिए पूर्ण ज्यामिति के बजाय सेंट्रॉइड का उपयोग करें (भवनों जैसे जटिल बहुभुजों के लिए तेज़)",
        "id": "Gunakan sentroid alih-alih geometri penuh untuk lapisan jauh (lebih cepat untuk poligon kompleks seperti bangunan)",
        "it": "Usa centroidi invece di geometrie complete per layer distanti (più veloce per poligoni complessi come edifici)",
        "nb": "Bruk sentroider i stedet for fulle geometrier for fjerne lag (raskere for komplekse polygoner som bygninger)",
        "nl": "Gebruik zwaartepunten in plaats van volledige geometrieën voor verre lagen (sneller voor complexe polygonen zoals gebouwen)",
        "pl": "Użyj centroidów zamiast pełnych geometrii dla odległych warstw (szybsze dla złożonych wielokątów jak budynki)",
        "pt": "Usar centróides em vez de geometrias completas para camadas distantes (mais rápido para polígonos complexos como edifícios)",
        "ru": "Использовать центроиды вместо полных геометрий для удаленных слоев (быстрее для сложных полигонов типа зданий)",
        "sl": "Uporabi centroide namesto polnih geometrij za oddaljene sloje (hitreje za kompleksne poligone kot zgradbe)",
        "sv": "Använd centroider istället för fulla geometrier för avlägsna lager (snabbare för komplexa polygoner som byggnader)",
        "tl": "Gumamit ng mga sentroid sa halip na buong geometries para sa malalayong layer (mas mabilis para sa mga kumplikadong polygon tulad ng mga gusali)",
        "tr": "Uzak katmanlar için tam geometriler yerine sentroidler kullan (binalar gibi karmaşık çokgenler için daha hızlı)",
        "uz": "Uzoq qatlamlar uchun to'liq geometriyalar o'rniga markazlardan foydalaning (binolar kabi murakkab ko'pburchaklar uchun tezroq)",
        "vi": "Sử dụng trọng tâm thay vì hình học đầy đủ cho các lớp xa (nhanh hơn cho đa giác phức tạp như các tòa nhà)",
        "zh": "对远距离图层使用质心而不是完整几何（对建筑物等复杂多边形更快）"
    }
}

def get_lang_code(filename):
    parts = filename.replace('.ts', '').split('_')
    return parts[-1] if len(parts) >= 2 else None

def main():
    i18n_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'i18n')
    updated_count = 0
    
    for ts_file in sorted(os.listdir(i18n_dir)):
        if not ts_file.endswith('.ts'):
            continue
        
        lang_code = get_lang_code(ts_file)
        if not lang_code:
            continue
        
        filepath = os.path.join(i18n_dir, ts_file)
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        updated = False
        for msg in root.iter('message'):
            src = msg.find('source')
            trans = msg.find('translation')
            
            if src is not None and src.text:
                source_text = src.text
                if source_text in MISSING_TRANS:
                    if trans is not None:
                        if (trans.get('type') == 'unfinished' or 
                            not trans.text or 
                            not trans.text.strip()):
                            if lang_code in MISSING_TRANS[source_text]:
                                trans.text = MISSING_TRANS[source_text][lang_code]
                                if trans.get('type'):
                                    del trans.attrib['type']
                                updated = True
        
        if updated:
            tree.write(filepath, encoding='utf-8', xml_declaration=True)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            if '<!DOCTYPE TS>' not in content:
                content = content.replace("<?xml version='1.0' encoding='utf-8'?>",
                                          '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            updated_count += 1
            print(f'Updated: {ts_file}')
    
    print(f'\nTotal files updated: {updated_count}')

if __name__ == '__main__':
    main()
