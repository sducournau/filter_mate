#!/usr/bin/env python3
"""
Update all FilterMate translation files with new configuration-related strings.
This script adds missing translations for the new config migration messages.
"""

import os
import re

# Base directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
I18N_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'i18n')

# New strings to add (source -> translations by language code)
NEW_STRINGS = {
    "Obsolete configuration detected": {
        "en": "Obsolete configuration detected",
        "fr": "Configuration obsolète détectée",
        "de": "Veraltete Konfiguration erkannt",
        "es": "Configuración obsoleta detectada",
        "it": "Configurazione obsoleta rilevata",
        "nl": "Verouderde configuratie gedetecteerd",
        "pt": "Configuração obsoleta detectada",
        "pl": "Wykryto przestarzałą konfigurację",
        "zh": "检测到过时配置",
        "ru": "Обнаружена устаревшая конфигурация",
        "id": "Konfigurasi usang terdeteksi",
        "vi": "Phát hiện cấu hình lỗi thời",
        "tr": "Eski yapılandırma algılandı",
        "hi": "पुरानी कॉन्फ़िगरेशन का पता चला",
        "fi": "Vanhentunut asetustiedosto havaittu",
        "da": "Forældet konfiguration fundet",
        "sv": "Föråldrad konfiguration upptäckt",
        "nb": "Utdatert konfigurasjon oppdaget",
        "sl": "Zastarela konfiguracija zaznana",
        "tl": "Lumang pagsasaayos ang nakita",
        "am": "ያረጀ ውቅረት ተገኝቷል",
    },
    "unknown version": {
        "en": "unknown version",
        "fr": "version inconnue",
        "de": "unbekannte Version",
        "es": "versión desconocida",
        "it": "versione sconosciuta",
        "nl": "onbekende versie",
        "pt": "versão desconhecida",
        "pl": "nieznana wersja",
        "zh": "未知版本",
        "ru": "неизвестная версия",
        "id": "versi tidak dikenal",
        "vi": "phiên bản không xác định",
        "tr": "bilinmeyen sürüm",
        "hi": "अज्ञात संस्करण",
        "fi": "tuntematon versio",
        "da": "ukendt version",
        "sv": "okänd version",
        "nb": "ukjent versjon",
        "sl": "neznana različica",
        "tl": "hindi kilalang bersyon",
        "am": "ያልታወቀ ስሪት",
    },
    "Corrupted configuration detected": {
        "en": "Corrupted configuration detected",
        "fr": "Configuration corrompue détectée",
        "de": "Beschädigte Konfiguration erkannt",
        "es": "Configuración dañada detectada",
        "it": "Configurazione corrotta rilevata",
        "nl": "Beschadigde configuratie gedetecteerd",
        "pt": "Configuração corrompida detectada",
        "pl": "Wykryto uszkodzoną konfigurację",
        "zh": "检测到损坏的配置",
        "ru": "Обнаружена повреждённая конфигурация",
        "id": "Konfigurasi rusak terdeteksi",
        "vi": "Phát hiện cấu hình bị hỏng",
        "tr": "Bozuk yapılandırma algılandı",
        "hi": "क्षतिग्रस्त कॉन्फ़िगरेशन का पता चला",
        "fi": "Vioittunut asetustiedosto havaittu",
        "da": "Beskadiget konfiguration fundet",
        "sv": "Skadad konfiguration upptäckt",
        "nb": "Skadet konfigurasjon oppdaget",
        "sl": "Poškodovana konfiguracija zaznana",
        "tl": "Sirang pagsasaayos ang nakita",
        "am": "የተበላሸ ውቅረት ተገኝቷል",
    },
    "Configuration reset": {
        "en": "Configuration reset",
        "fr": "Réinitialisation de la configuration",
        "de": "Konfiguration zurücksetzen",
        "es": "Restablecimiento de configuración",
        "it": "Ripristino configurazione",
        "nl": "Configuratie resetten",
        "pt": "Redefinição de configuração",
        "pl": "Resetowanie konfiguracji",
        "zh": "配置重置",
        "ru": "Сброс конфигурации",
        "id": "Reset konfigurasi",
        "vi": "Đặt lại cấu hình",
        "tr": "Yapılandırma sıfırlama",
        "hi": "कॉन्फ़िगरेशन रीसेट",
        "fi": "Asetusten nollaus",
        "da": "Nulstil konfiguration",
        "sv": "Återställ konfiguration",
        "nb": "Tilbakestilling av konfigurasjon",
        "sl": "Ponastavitev konfiguracije",
        "tl": "I-reset ang pagsasaayos",
        "am": "ውቅረት ዳግም አስጀምር",
    },
    "Configuration not reset. Some features may not work correctly.": {
        "en": "Configuration not reset. Some features may not work correctly.",
        "fr": "Configuration non réinitialisée. Certaines fonctionnalités peuvent ne pas fonctionner correctement.",
        "de": "Konfiguration nicht zurückgesetzt. Einige Funktionen funktionieren möglicherweise nicht korrekt.",
        "es": "Configuración no restablecida. Algunas funciones pueden no funcionar correctamente.",
        "it": "Configurazione non ripristinata. Alcune funzionalità potrebbero non funzionare correttamente.",
        "nl": "Configuratie niet gereset. Sommige functies werken mogelijk niet correct.",
        "pt": "Configuração não redefinida. Algumas funcionalidades podem não funcionar corretamente.",
        "pl": "Konfiguracja nie została zresetowana. Niektóre funkcje mogą nie działać poprawnie.",
        "zh": "配置未重置。某些功能可能无法正常工作。",
        "ru": "Конфигурация не сброшена. Некоторые функции могут работать некорректно.",
        "id": "Konfigurasi tidak direset. Beberapa fitur mungkin tidak berfungsi dengan benar.",
        "vi": "Cấu hình chưa được đặt lại. Một số tính năng có thể không hoạt động đúng.",
        "tr": "Yapılandırma sıfırlanmadı. Bazı özellikler düzgün çalışmayabilir.",
        "hi": "कॉन्फ़िगरेशन रीसेट नहीं हुई। कुछ सुविधाएं सही ढंग से काम नहीं कर सकती हैं।",
        "fi": "Asetuksia ei nollattu. Jotkin toiminnot eivät ehkä toimi oikein.",
        "da": "Konfiguration ikke nulstillet. Nogle funktioner fungerer muligvis ikke korrekt.",
        "sv": "Konfiguration inte återställd. Vissa funktioner kanske inte fungerar korrekt.",
        "nb": "Konfigurasjon ikke tilbakestilt. Noen funksjoner fungerer kanskje ikke riktig.",
        "sl": "Konfiguracija ni bila ponastavljena. Nekatere funkcije morda ne bodo delovale pravilno.",
        "tl": "Hindi na-reset ang pagsasaayos. Ang ilang mga tampok ay maaaring hindi gumana ng tama.",
        "am": "ውቅረት አልተዘዋወረም። አንዳንድ ባህሪያት በትክክል ላይሰሩ ይችላሉ።",
    },
    "Configuration created with default values": {
        "en": "Configuration created with default values",
        "fr": "Configuration créée avec les valeurs par défaut",
        "de": "Konfiguration mit Standardwerten erstellt",
        "es": "Configuración creada con valores predeterminados",
        "it": "Configurazione creata con valori predefiniti",
        "nl": "Configuratie aangemaakt met standaardwaarden",
        "pt": "Configuração criada com valores padrão",
        "pl": "Konfiguracja utworzona z wartościami domyślnymi",
        "zh": "已使用默认值创建配置",
        "ru": "Конфигурация создана со значениями по умолчанию",
        "id": "Konfigurasi dibuat dengan nilai default",
        "vi": "Cấu hình đã được tạo với giá trị mặc định",
        "tr": "Yapılandırma varsayılan değerlerle oluşturuldu",
        "hi": "डिफ़ॉल्ट मानों के साथ कॉन्फ़िगरेशन बनाई गई",
        "fi": "Asetukset luotu oletusarvoilla",
        "da": "Konfiguration oprettet med standardværdier",
        "sv": "Konfiguration skapad med standardvärden",
        "nb": "Konfigurasjon opprettet med standardverdier",
        "sl": "Konfiguracija ustvarjena s privzetimi vrednostmi",
        "tl": "Ang pagsasaayos ay nilikha gamit ang mga default na halaga",
        "am": "ውቅረት በነባሪ እሴቶች ተፈጥሯል",
    },
    "Corrupted configuration reset. Default settings have been restored.": {
        "en": "Corrupted configuration reset. Default settings have been restored.",
        "fr": "Configuration corrompue réinitialisée. Les paramètres par défaut ont été restaurés.",
        "de": "Beschädigte Konfiguration zurückgesetzt. Standardeinstellungen wurden wiederhergestellt.",
        "es": "Configuración dañada restablecida. Se han restaurado los ajustes predeterminados.",
        "it": "Configurazione corrotta ripristinata. Le impostazioni predefinite sono state ripristinate.",
        "nl": "Beschadigde configuratie gereset. Standaardinstellingen zijn hersteld.",
        "pt": "Configuração corrompida redefinida. As configurações padrão foram restauradas.",
        "pl": "Uszkodzona konfiguracja została zresetowana. Przywrócono ustawienia domyślne.",
        "zh": "损坏的配置已重置。默认设置已恢复。",
        "ru": "Повреждённая конфигурация сброшена. Настройки по умолчанию восстановлены.",
        "id": "Konfigurasi rusak telah direset. Pengaturan default telah dipulihkan.",
        "vi": "Cấu hình bị hỏng đã được đặt lại. Cài đặt mặc định đã được khôi phục.",
        "tr": "Bozuk yapılandırma sıfırlandı. Varsayılan ayarlar geri yüklendi.",
        "hi": "क्षतिग्रस्त कॉन्फ़िगरेशन रीसेट हो गई। डिफ़ॉल्ट सेटिंग्स पुनर्स्थापित हो गई हैं।",
        "fi": "Vioittunut asetustiedosto nollattu. Oletusasetukset on palautettu.",
        "da": "Beskadiget konfiguration nulstillet. Standardindstillinger er gendannet.",
        "sv": "Skadad konfiguration återställd. Standardinställningar har återställts.",
        "nb": "Skadet konfigurasjon tilbakestilt. Standardinnstillinger er gjenopprettet.",
        "sl": "Poškodovana konfiguracija ponastavljena. Privzete nastavitve so bile obnovljene.",
        "tl": "Na-reset ang sirang pagsasaayos. Naibalik na ang mga default na setting.",
        "am": "የተበላሸ ውቅረት ዳግም ተጀምሯል። ነባሪ ቅንብሮች ተመልሰዋል።",
    },
    "Obsolete configuration reset. Default settings have been restored.": {
        "en": "Obsolete configuration reset. Default settings have been restored.",
        "fr": "Configuration obsolète réinitialisée. Les paramètres par défaut ont été restaurés.",
        "de": "Veraltete Konfiguration zurückgesetzt. Standardeinstellungen wurden wiederhergestellt.",
        "es": "Configuración obsoleta restablecida. Se han restaurado los ajustes predeterminados.",
        "it": "Configurazione obsoleta ripristinata. Le impostazioni predefinite sono state ripristinate.",
        "nl": "Verouderde configuratie gereset. Standaardinstellingen zijn hersteld.",
        "pt": "Configuração obsoleta redefinida. As configurações padrão foram restauradas.",
        "pl": "Przestarzała konfiguracja została zresetowana. Przywrócono ustawienia domyślne.",
        "zh": "过时的配置已重置。默认设置已恢复。",
        "ru": "Устаревшая конфигурация сброшена. Настройки по умолчанию восстановлены.",
        "id": "Konfigurasi usang telah direset. Pengaturan default telah dipulihkan.",
        "vi": "Cấu hình lỗi thời đã được đặt lại. Cài đặt mặc định đã được khôi phục.",
        "tr": "Eski yapılandırma sıfırlandı. Varsayılan ayarlar geri yüklendi.",
        "hi": "पुरानी कॉन्फ़िगरेशन रीसेट हो गई। डिफ़ॉल्ट सेटिंग्स पुनर्स्थापित हो गई हैं।",
        "fi": "Vanhentunut asetustiedosto nollattu. Oletusasetukset on palautettu.",
        "da": "Forældet konfiguration nulstillet. Standardindstillinger er gendannet.",
        "sv": "Föråldrad konfiguration återställd. Standardinställningar har återställts.",
        "nb": "Utdatert konfigurasjon tilbakestilt. Standardinnstillinger er gjenopprettet.",
        "sl": "Zastarela konfiguracija ponastavljena. Privzete nastavitve so bile obnovljene.",
        "tl": "Na-reset ang lumang pagsasaayos. Naibalik na ang mga default na setting.",
        "am": "ያረጀ ውቅረት ዳግም ተጀምሯል። ነባሪ ቅንብሮች ተመልሰዋል።",
    },
    "Configuration updated to latest version": {
        "en": "Configuration updated to latest version",
        "fr": "Configuration mise à jour vers la dernière version",
        "de": "Konfiguration auf neueste Version aktualisiert",
        "es": "Configuración actualizada a la última versión",
        "it": "Configurazione aggiornata all'ultima versione",
        "nl": "Configuratie bijgewerkt naar nieuwste versie",
        "pt": "Configuração atualizada para a versão mais recente",
        "pl": "Konfiguracja zaktualizowana do najnowszej wersji",
        "zh": "配置已更新至最新版本",
        "ru": "Конфигурация обновлена до последней версии",
        "id": "Konfigurasi diperbarui ke versi terbaru",
        "vi": "Cấu hình đã được cập nhật lên phiên bản mới nhất",
        "tr": "Yapılandırma en son sürüme güncellendi",
        "hi": "कॉन्फ़िगरेशन नवीनतम संस्करण में अपडेट हो गई",
        "fi": "Asetukset päivitetty uusimpaan versioon",
        "da": "Konfiguration opdateret til seneste version",
        "sv": "Konfiguration uppdaterad till senaste version",
        "nb": "Konfigurasjon oppdatert til nyeste versjon",
        "sl": "Konfiguracija posodobljena na najnovejšo različico",
        "tl": "Na-update ang pagsasaayos sa pinakabagong bersyon",
        "am": "ውቅረት ወደ አዲሱ ስሪት ተዘምኗል",
    },
    "Geometry validation setting": {
        "en": "Geometry validation setting",
        "fr": "Paramètre de validation des géométries",
        "de": "Einstellung zur Geometrievalidierung",
        "es": "Configuración de validación de geometría",
        "it": "Impostazione di validazione della geometria",
        "nl": "Geometrie validatie instelling",
        "pt": "Configuração de validação de geometria",
        "pl": "Ustawienie walidacji geometrii",
        "zh": "几何验证设置",
        "ru": "Настройка проверки геометрии",
        "id": "Pengaturan validasi geometri",
        "vi": "Cài đặt xác thực hình học",
        "tr": "Geometri doğrulama ayarı",
        "hi": "ज्यामिति सत्यापन सेटिंग",
        "fi": "Geometrian tarkistusasetus",
        "da": "Geometri valideringsindstilling",
        "sv": "Geometrivalideringsinställning",
        "nb": "Geometrivalideringsinnstilling",
        "sl": "Nastavitev preverjanja geometrije",
        "tl": "Setting ng geometry validation",
        "am": "የጂኦሜትሪ ማረጋገጫ ቅንብር",
    },
    "Invalid geometry filtering disabled successfully.": {
        "en": "Invalid geometry filtering disabled successfully.",
        "fr": "Filtrage des géométries invalides désactivé avec succès.",
        "de": "Filterung ungültiger Geometrien erfolgreich deaktiviert.",
        "es": "Filtrado de geometrías inválidas desactivado correctamente.",
        "it": "Filtraggio delle geometrie non valide disabilitato con successo.",
        "nl": "Filteren van ongeldige geometrieën succesvol uitgeschakeld.",
        "pt": "Filtragem de geometrias inválidas desativada com sucesso.",
        "pl": "Filtrowanie nieprawidłowych geometrii zostało pomyślnie wyłączone.",
        "zh": "无效几何过滤已成功禁用。",
        "ru": "Фильтрация недопустимых геометрий успешно отключена.",
        "id": "Pemfilteran geometri tidak valid berhasil dinonaktifkan.",
        "vi": "Đã tắt thành công bộ lọc hình học không hợp lệ.",
        "tr": "Geçersiz geometri filtreleme başarıyla devre dışı bırakıldı.",
        "hi": "अमान्य ज्यामिति फ़िल्टरिंग सफलतापूर्वक अक्षम हो गई।",
        "fi": "Virheellisten geometrioiden suodatus poistettu käytöstä onnistuneesti.",
        "da": "Filtrering af ugyldige geometrier deaktiveret.",
        "sv": "Filtrering av ogiltiga geometrier har inaktiverats.",
        "nb": "Filtrering av ugyldige geometrier er deaktivert.",
        "sl": "Filtriranje neveljavnih geometrij je uspešno onemogočeno.",
        "tl": "Matagumpay na na-disable ang pag-filter ng invalid na geometry.",
        "am": "ልክ ያልሆነ ጂኦሜትሪ ማጣራት በተሳካ ሁኔታ ተሰናክሏል።",
    },
    "Invalid geometry filtering not modified. Some features may be excluded from exports.": {
        "en": "Invalid geometry filtering not modified. Some features may be excluded from exports.",
        "fr": "Filtrage des géométries invalides non modifié. Certaines entités peuvent être exclues des exports.",
        "de": "Filterung ungültiger Geometrien nicht geändert. Einige Features können vom Export ausgeschlossen werden.",
        "es": "Filtrado de geometrías inválidas no modificado. Algunas entidades pueden excluirse de las exportaciones.",
        "it": "Filtraggio delle geometrie non valide non modificato. Alcune feature potrebbero essere escluse dalle esportazioni.",
        "nl": "Filteren van ongeldige geometrieën niet gewijzigd. Sommige objecten kunnen worden uitgesloten van exports.",
        "pt": "Filtragem de geometrias inválidas não modificada. Algumas feições podem ser excluídas das exportações.",
        "pl": "Filtrowanie nieprawidłowych geometrii nie zostało zmienione. Niektóre obiekty mogą zostać wykluczone z eksportu.",
        "zh": "无效几何过滤未修改。某些要素可能会从导出中排除。",
        "ru": "Фильтрация недопустимых геометрий не изменена. Некоторые объекты могут быть исключены из экспорта.",
        "id": "Pemfilteran geometri tidak valid tidak diubah. Beberapa fitur mungkin dikecualikan dari ekspor.",
        "vi": "Bộ lọc hình học không hợp lệ không được thay đổi. Một số đối tượng có thể bị loại khỏi xuất.",
        "tr": "Geçersiz geometri filtreleme değiştirilmedi. Bazı özellikler dışa aktarmalardan hariç tutulabilir.",
        "hi": "अमान्य ज्यामिति फ़िल्टरिंग संशोधित नहीं की गई। कुछ सुविधाएं निर्यात से बाहर हो सकती हैं।",
        "fi": "Virheellisten geometrioiden suodatusta ei muutettu. Jotkin kohteet voivat jäädä pois viennistä.",
        "da": "Filtrering af ugyldige geometrier ikke ændret. Nogle objekter kan udelukkes fra eksport.",
        "sv": "Filtrering av ogiltiga geometrier ändrades inte. Vissa objekt kan exkluderas från export.",
        "nb": "Filtrering av ugyldige geometrier ikke endret. Noen objekter kan bli ekskludert fra eksport.",
        "sl": "Filtriranje neveljavnih geometrij ni bilo spremenjeno. Nekatere funkcije so lahko izključene iz izvoza.",
        "tl": "Hindi binago ang pag-filter ng invalid na geometry. Ang ilang mga tampok ay maaaring ihiwalay sa mga pag-export.",
        "am": "ልክ ያልሆነ ጂኦሜትሪ ማጣራት አልተሻሻለም። አንዳንድ ባህሪያት ከወጪዎች ሊገለሉ ይችላሉ።",
    },
}

# Language names for file headers
LANGUAGE_NAMES = {
    "en": ("en_US", "English"),
    "fr": ("fr_FR", "French"),
    "de": ("de_DE", "German"),
    "es": ("es_ES", "Spanish"),
    "it": ("it_IT", "Italian"),
    "nl": ("nl_NL", "Dutch"),
    "pt": ("pt_PT", "Portuguese"),
    "pl": ("pl_PL", "Polish"),
    "zh": ("zh_CN", "Chinese Simplified"),
    "ru": ("ru_RU", "Russian"),
    "id": ("id_ID", "Indonesian"),
    "vi": ("vi_VN", "Vietnamese"),
    "tr": ("tr_TR", "Turkish"),
    "hi": ("hi_IN", "Hindi"),
    "fi": ("fi_FI", "Finnish"),
    "da": ("da_DK", "Danish"),
    "sv": ("sv_SE", "Swedish"),
    "nb": ("nb_NO", "Norwegian Bokmål"),
    "sl": ("sl_SI", "Slovenian"),
    "tl": ("tl_PH", "Filipino/Tagalog"),
    "am": ("am_ET", "Amharic"),
}


def escape_xml(text):
    """Escape special characters for XML."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("'", "&apos;")
    return text


def add_message_to_ts(content, source, translation, after_marker="</context>"):
    """Add a message entry to the TS file content."""
    message_block = f"""    <message>
        <source>{escape_xml(source)}</source>
        <translation>{escape_xml(translation)}</translation>
    </message>
"""
    # Find the first </context> and insert before it
    first_context_end = content.find("</context>")
    if first_context_end != -1:
        return content[:first_context_end] + message_block + content[first_context_end:]
    return content


def update_translation_file(lang_code, filepath):
    """Update a translation file with new strings."""
    print(f"Updating {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check which strings are missing
    strings_to_add = []
    for source, translations in NEW_STRINGS.items():
        if source not in content:
            translation = translations.get(lang_code, translations.get("en", source))
            strings_to_add.append((source, translation))
    
    if not strings_to_add:
        print(f"  No new strings needed for {lang_code}")
        return
    
    # Add missing strings
    for source, translation in strings_to_add:
        content = add_message_to_ts(content, source, translation)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Added {len(strings_to_add)} new strings to {lang_code}")


def main():
    """Main function to update all translation files."""
    print("Updating FilterMate translation files...")
    print(f"i18n directory: {I18N_DIR}")
    
    # Get all existing .ts files
    ts_files = [f for f in os.listdir(I18N_DIR) if f.endswith('.ts')]
    print(f"Found {len(ts_files)} translation files")
    
    for ts_file in ts_files:
        # Extract language code from filename (e.g., FilterMate_de.ts -> de)
        match = re.match(r'FilterMate_(\w+)\.ts', ts_file)
        if match:
            lang_code = match.group(1)
            filepath = os.path.join(I18N_DIR, ts_file)
            update_translation_file(lang_code, filepath)
    
    print("\nDone updating translation files!")
    print("\nRemember to compile translations with: python compile_translations.py")


if __name__ == "__main__":
    main()
