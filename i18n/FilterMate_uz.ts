<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="uz_UZ" sourcelanguage="en_US">
<context>
    <name>FilterMate</name>
    <message>
        <source>&amp;FilterMate</source>
        <translation>&amp;FilterMate</translation>
    </message>
    <message>
        <source>FilterMate</source>
        <translation>FilterMate</translation>
    </message>
    <message>
        <source>Open FilterMate panel</source>
        <translation>FilterMate panelini ochish</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Sozlamalar va ma&apos;lumotlar bazasini tiklash</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>Standart sozlamalarni tiklash va SQLite ma&apos;lumotlar bazasini o&apos;chirish</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>Sozlamalarni tiklash</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>Standart sozlamalarga qaytishni xohlaysizmi?

Bu quyidagilarni bajaradi:
- Barcha FilterMate sozlamalarini tiklaydi
- Barcha filtr tarixi ma&apos;lumotlar bazalarini o&apos;chiradi</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>Sozlamalar muvaffaqiyatli tiklandi.</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>Standart sozlamalar fayli topilmadi.</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>Ma&apos;lumotlar bazasi o&apos;chirildi: {filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>{filename} ni o&apos;chirib bo&apos;lmadi: {error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>Qayta ishga tushirish talab qilinadi</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>Sozlamalar tiklandi.

Barcha o&apos;zgarishlarni qo&apos;llash uchun QGIS ni qayta ishga tushiring.</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>Tiklash vaqtida xatolik: {error}</translation>
    </message>
    <message>
        <source>Obsolete configuration detected</source>
        <translation>Eskirgan sozlamalar aniqlandi</translation>
    </message>
    <message>
        <source>unknown version</source>
        <translation>noma&apos;lum versiya</translation>
    </message>
    <message>
        <source>An obsolete configuration ({}) has been detected.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created)
• No: Keep current configuration (may cause issues)</source>
        <translation>Eskirgan sozlamalar ({}) aniqlandi.

Standart sozlamalarga tiklamoqchimisiz?

• Ha: Tiklash (zaxira nusxa yaratiladi)
• Yo&apos;q: Joriy sozlamalarni saqlash (muammolar yuzaga kelishi mumkin)</translation>
    </message>
    <message>
        <source>Corrupted configuration detected</source>
        <translation>Buzilgan sozlamalar aniqlandi</translation>
    </message>
    <message>
        <source>The configuration file is corrupted and cannot be read.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created if possible)
• No: Cancel (the plugin may not work correctly)</source>
        <translation>Sozlamalar fayli buzilgan va o&apos;qib bo&apos;lmaydi.

Standart sozlamalarga tiklamoqchimisiz?

• Ha: Tiklash (iloji bo&apos;lsa zaxira nusxa yaratiladi)
• Yo&apos;q: Bekor qilish (plagin to&apos;g&apos;ri ishlamasligi mumkin)</translation>
    </message>
    <message>
        <source>Configuration reset</source>
        <translation>Sozlamalar tiklandi</translation>
    </message>
    <message>
        <source>The configuration needs to be reset.

Do you want to continue?</source>
        <translation>Sozlamalarni tiklash kerak.

Davom etmoqchimisiz?</translation>
    </message>
    <message>
        <source>Configuration not reset. Some features may not work correctly.</source>
        <translation>Sozlamalar tiklanmadi. Ba&apos;zi funksiyalar to&apos;g&apos;ri ishlamasligi mumkin.</translation>
    </message>
    <message>
        <source>Configuration created with default values</source>
        <translation>Standart qiymatlar bilan sozlamalar yaratildi</translation>
    </message>
    <message>
        <source>Corrupted configuration reset. Default settings have been restored.</source>
        <translation>Buzilgan sozlamalar tiklandi. Standart sozlamalar qayta tiklandi.</translation>
    </message>
    <message>
        <source>Obsolete configuration reset. Default settings have been restored.</source>
        <translation>Eskirgan sozlamalar tiklandi. Standart sozlamalar qayta tiklandi.</translation>
    </message>
    <message>
        <source>Configuration updated to latest version</source>
        <translation>Sozlamalar eng so&apos;nggi versiyaga yangilandi</translation>
    </message>
    <message>
        <source>Error during configuration migration: {}</source>
        <translation>Sozlamalarni ko&apos;chirish vaqtida xatolik: {}</translation>
    </message>
    <message>
        <source>Geometry validation setting</source>
        <translation>Geometriya tekshirish sozlamalari</translation>
    </message>
    <message>
        <source>The QGIS setting &apos;Invalid features filtering&apos; is currently set to &apos;{mode}&apos;.

FilterMate recommends disabling this setting (value &apos;Off&apos;) for the following reasons:

• Features with invalid geometries could be silently excluded from exports and filters
• FilterMate handles geometry validation internally with automatic repair options
• Some legitimate data may have geometries considered as &apos;invalid&apos; according to strict OGC rules

Do you want to disable this setting now?

• Yes: Disable filtering (recommended for FilterMate)
• No: Keep current setting</source>
        <translation>QGIS sozlamasi &apos;Noto&apos;g&apos;ri obyektlarni filtrlash&apos; hozirda &apos;{mode}&apos; ga o&apos;rnatilgan.

FilterMate quyidagi sabablarga ko&apos;ra ushbu sozlamani o&apos;chirishni tavsiya qiladi (qiymat &apos;O&apos;chirilgan&apos;):

• Noto&apos;g&apos;ri geometriyali obyektlar eksport va filtrlardan jimgina chiqarib tashlanishi mumkin
• FilterMate geometriya tekshiruvini avtomatik tuzatish imkoniyatlari bilan ichki boshqaradi
• Ba&apos;zi qonuniy ma&apos;lumotlar qat&apos;iy OGC qoidalariga ko&apos;ra &apos;noto&apos;g&apos;ri&apos; deb hisoblanishi mumkin

Hozir bu sozlamani o&apos;chirmoqchimisiz?

• Ha: Filtrlashni o&apos;chirish (FilterMate uchun tavsiya etiladi)
• Yo&apos;q: Joriy sozlamani saqlash</translation>
    </message>
    <message>
        <source>Invalid geometry filtering disabled successfully.</source>
        <translation>Noto&apos;g&apos;ri geometriya filtrlash muvaffaqiyatli o&apos;chirildi.</translation>
    </message>
    <message>
        <source>Invalid geometry filtering not modified. Some features may be excluded from exports.</source>
        <translation>Noto&apos;g&apos;ri geometriya filtrlash o&apos;zgartirilmadi. Ba&apos;zi obyektlar eksportdan chiqarib tashlanishi mumkin.</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Restore default settings
- Delete the layer database

QGIS must be restarted to apply the changes.</source>
        <translation>Standart sozlamalarga tiklamoqchimisiz?

Bu quyidagilarni bajaradi:
- Standart sozlamalarni tiklaydi
- Qatlam ma&apos;lumotlar bazasini o&apos;chiradi

O&apos;zgarishlarni qo&apos;llash uchun QGIS qayta ishga tushirilishi kerak.</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply the changes.</source>
        <translation>Sozlamalar tiklandi.

O&apos;zgarishlarni qo&apos;llash uchun QGIS ni qayta ishga tushiring.</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive=expand, negative=shrink polygons)</source>
        <translation>Bufer qiymati metrda (musbat=kengaytirish, manfiy=poligonlarni qisqartirish)</translation>
    </message>
    <message>
        <source>Negative buffer (erosion): shrinks polygons inward</source>
        <translation>Manfiy bufer (eroziya): poligonlarni ichkariga qisqartiradi</translation>
    </message>
    <message>
        <source>point</source>
        <translation>nuqta</translation>
    </message>
    <message>
        <source>line</source>
        <translation>chiziq</translation>
    </message>
    <message>
        <source>non-polygon</source>
        <translation>ko&apos;pburchak-emas</translation>
    </message>
    <message>
        <source>Mode batch</source>
        <translation>Ommaviy rejim</translation>
    </message>
    <message>
        <source>Number of segments for buffer precision</source>
        <translation>Bufer aniqligi uchun segmentlar soni</translation>
    </message>
    <message>
        <source>Centroids</source>
        <translation>Markazlar</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for distant layers (faster for complex polygons like buildings)</source>
        <translation>Uzoq qatlamlar uchun to&apos;liq geometriyalar o&apos;rniga markazlardan foydalaning (binolar kabi murakkab ko&apos;pburchaklar uchun tezroq)</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidgetBase</name>
    <message>
        <source>FilterMate</source>
        <translation>FilterMate</translation>
    </message>
    <message>
        <source>SINGLE SELECTION</source>
        <translation>YAKKA TANLASH</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>KO&apos;P TANLASH</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>MAXSUS TANLASH</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>FILTRLASH</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>EKSPORT QILISH</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>SOZLAMALAR</translation>
    </message>
    <message>
        <source>Identify feature - Display feature attributes</source>
        <translation>Obyektni aniqlash - Obyekt atributlarini ko&apos;rsatish</translation>
    </message>
    <message>
        <source>Zoom to feature - Center the map on the selected feature</source>
        <translation>Obyektga yaqinlashtirish - Xaritani tanlangan obyektga markazlashtirish</translation>
    </message>
    <message>
        <source>Enable selection - Select features on map</source>
        <translation>Tanlashni yoqish - Xaritada obyektlarni tanlash</translation>
    </message>
    <message>
        <source>Enable tracking - Follow the selected feature on the map</source>
        <translation>Kuzatishni yoqish - Xaritada tanlangan obyektni kuzatish</translation>
    </message>
    <message>
        <source>Link widgets - Synchronize selection between widgets</source>
        <translation>Vidjetlarni bog&apos;lash - Vidjetlar o&apos;rtasida tanlashni sinxronlashtirish</translation>
    </message>
    <message>
        <source>Reset layer properties - Restore default layer settings</source>
        <translation>Qatlam xususiyatlarini tiklash - Standart qatlam sozlamalarini tiklash</translation>
    </message>
    <message>
        <source>Auto-sync with current layer - Automatically update when layer changes</source>
        <translation>Joriy qatlam bilan avtomatik sinxronlash - Qatlam o&apos;zgarganda avtomatik yangilash</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>Ko&apos;p qatlamli filtrlashni yoqish - Filtrni bir vaqtda bir nechta qatlamlarga qo&apos;llash</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>Qo&apos;shimcha filtrlashni yoqish - Joriy qatlamda bir nechta filtrlarni birlashtirish</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>Fazoviy filtrlashni yoqish - Geometrik munosabatlar yordamida obyektlarni filtrlash</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>Buferni yoqish - Tanlangan obyektlar atrofiga bufer zonasini qo&apos;shish</translation>
    </message>
    <message>
        <source>Buffer type - Select the buffer calculation method</source>
        <translation>Bufer turi - Bufer hisoblash usulini tanlash</translation>
    </message>
    <message>
        <source>Current layer - Select the layer to filter</source>
        <translation>Joriy qatlam - Filtrlash uchun qatlamni tanlash</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>Manba qatlamida filtrlarni birlashtirish uchun mantiqiy operator</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on other layers</source>
        <translation>Boshqa qatlamlarda filtrlarni birlashtirish uchun mantiqiy operator</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>Fazoviy filtrlash uchun geometrik predikat(lar)ni tanlash</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>Metrda bufer masofasi</translation>
    </message>
    <message>
        <source>Buffer type - Define how the buffer is calculated</source>
        <translation>Bufer turi - Bufer qanday hisoblanishini belgilash</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>Eksport qilish uchun qatlamlarni tanlash</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>Chiqish proyeksiyasini sozlash</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>Qatlam uslublarini eksport qilish (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>Chiqish formatini tanlash</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>Chiqish joylashuvi va fayl nomini sozlash</translation>
    </message>
    <message>
        <source>Enable ZIP compression - Create a compressed archive of exported files</source>
        <translation>ZIP siqishni yoqish - Eksport qilingan fayllarning siqilgan arxivini yaratish</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>Eksport uchun CRS ni tanlash</translation>
    </message>
    <message>
        <source>Style format - Select QML or SLD format</source>
        <translation>Uslub formati - QML yoki SLD formatini tanlash</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>Chiqish fayl formati</translation>
    </message>
    <message>
        <source>Output folder name - Enter the name of the export folder</source>
        <translation>Chiqish papka nomi - Eksport papkasining nomini kiriting</translation>
    </message>
    <message>
        <source>Enter folder name...</source>
        <translation>Papka nomini kiriting...</translation>
    </message>
    <message>
        <source>Batch mode - Export each layer to a separate folder</source>
        <translation>Ommaviy rejim - Har bir qatlamni alohida papkaga eksport qilish</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>Ommaviy rejim</translation>
    </message>
    <message>
        <source>ZIP filename - Enter the name for the compressed archive</source>
        <translation>ZIP fayl nomi - Siqilgan arxiv uchun nomni kiriting</translation>
    </message>
    <message>
        <source>Enter ZIP filename...</source>
        <translation>ZIP fayl nomini kiriting...</translation>
    </message>
    <message>
        <source>Batch mode - Create a separate ZIP for each layer</source>
        <translation>Ommaviy rejim - Har bir qatlam uchun alohida ZIP yaratish</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>Filtrni qo&apos;llash - Tanlangan qatlamlarda joriy filtrni bajarish</translation>
    </message>
    <message>
        <source>Apply Filter</source>
        <translation>Filtrni qo&apos;llash</translation>
    </message>
    <message>
        <source>Apply the current filter expression to filter features on the selected layer(s)</source>
        <translation>Tanlangan qatlam(lar)dagi obyektlarni filtrlash uchun joriy filtr ifodasini qo&apos;llash</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>Filtrni bekor qilish - Oldingi filtr holatini tiklash</translation>
    </message>
    <message>
        <source>Undo Filter</source>
        <translation>Filtrni bekor qilish</translation>
    </message>
    <message>
        <source>Undo the last filter operation and restore the previous state</source>
        <translation>Oxirgi filtr operatsiyasini bekor qilish va oldingi holatni tiklash</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>Filtrni qayta qo&apos;llash - Oldin bekor qilingan filtrni qayta qo&apos;llash</translation>
    </message>
    <message>
        <source>Redo Filter</source>
        <translation>Filtrni qayta qo&apos;llash</translation>
    </message>
    <message>
        <source>Redo the previously undone filter operation</source>
        <translation>Oldin bekor qilingan filtr operatsiyasini qayta bajarish</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>Barcha filtrlarni tozalash - Barcha qatlamlardan barcha filtrlarni olib tashlash</translation>
    </message>
    <message>
        <source>Clear All Filters</source>
        <translation>Barcha filtrlarni tozalash</translation>
    </message>
    <message>
        <source>Remove all active filters from all layers in the project</source>
        <translation>Loyihadagi barcha qatlamlardan barcha faol filtrlarni olib tashlash</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>Eksport - Filtrlangan qatlamlarni ko&apos;rsatilgan joyga saqlash</translation>
    </message>
    <message>
        <source>Export</source>
        <translation>Eksport</translation>
    </message>
    <message>
        <source>Export the filtered layers to the configured output location and format</source>
        <translation>Filtrlangan qatlamlarni sozlangan chiqish joylashuvi va formatiga eksport qilish</translation>
    </message>
    <message>
        <source>About FilterMate - Display plugin information and help</source>
        <translation>FilterMate haqida - Plagin ma&apos;lumotlari va yordamni ko&apos;rsatish</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>VA</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>VA EMAS</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>YOKI</translation>
    </message>
    <message>
        <source>QML</source>
        <translation>QML</translation>
    </message>
    <message>
        <source>SLD</source>
        <translation>SLD</translation>
    </message>
    <message>
        <source> m</source>
        <translation> m</translation>
    </message>
    <message>
        <source>, </source>
        <translation>, </translation>
    </message>
    <message>
        <source>Multi-layer filtering</source>
        <translation>Ko&apos;p qatlamli filtrlash</translation>
    </message>
    <message>
        <source>Additive filtering for the selected layer</source>
        <translation>Tanlangan qatlam uchun qo&apos;shimcha filtrlash</translation>
    </message>
    <message>
        <source>Geospatial filtering</source>
        <translation>Geofazoviy filtrlash</translation>
    </message>
    <message>
        <source>Buffer</source>
        <translation>Bufer</translation>
    </message>
    <message>
        <source>Expression layer</source>
        <translation>Ifoda qatlami</translation>
    </message>
    <message>
        <source>Geometric predicate</source>
        <translation>Geometrik predikat</translation>
    </message>
    <message>
        <source>Value in meters</source>
        <translation>Metrda qiymat</translation>
    </message>
    <message>
        <source>Output format</source>
        <translation>Chiqish formati</translation>
    </message>
    <message>
        <source>Filter</source>
        <translation>Filtr</translation>
    </message>
    <message>
        <source>Reset</source>
        <translation>Tiklash</translation>
    </message>
    <message>
        <source>Layers to export</source>
        <translation>Eksport qilinadigan qatlamlar</translation>
    </message>
    <message>
        <source>Layers projection</source>
        <translation>Qatlamlar proyeksiyasi</translation>
    </message>
    <message>
        <source>Save styles</source>
        <translation>Uslublarni saqlash</translation>
    </message>
    <message>
        <source>Datatype export</source>
        <translation>Ma&apos;lumot turi eksporti</translation>
    </message>
    <message>
        <source>Name of file/directory</source>
        <translation>Fayl/katalog nomi</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidget</name>
    <message>
        <source>Reload the plugin to apply layout changes (action bar position)</source>
        <translation>Tartib o&apos;zgarishlarini qo&apos;llash uchun plaginni qayta yuklash (amal paneli holati)</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>Plaginni qayta yuklash</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>Barcha sozlama o&apos;zgarishlarini qo&apos;llash uchun FilterMate ni qayta yuklamoqchimisiz?</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>Joriy qatlam: {name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>Hech qanday qatlam tanlanmagan</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>Tanlangan qatlamlar:</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>Bir nechta qatlam tanlangan</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>Hech qanday qatlam tanlanmagan</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>Ifoda:</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>Hech qanday ifoda belgilanmagan</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>Ko&apos;rsatish ifodasi: {expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>Obyekt IDsi: {id}</translation>
    </message>
    <message>
        <source>Current layer: {0}</source>
        <translation>Joriy qatlam: {0}</translation>
    </message>
    <message>
        <source>Selected layers:
{0}</source>
        <translation>Tanlangan qatlamlar:
{0}</translation>
    </message>
    <message>
        <source>Expression:
{0}</source>
        <translation>Ifoda:
{0}</translation>
    </message>
    <message>
        <source>Expression: {0}</source>
        <translation>Ifoda: {0}</translation>
    </message>
    <message>
        <source>Display expression: {0}</source>
        <translation>Ko&apos;rsatish ifodasi: {0}</translation>
    </message>
    <message>
        <source>Feature ID: {0}
First attribute: {1}</source>
        <translation>Obyekt IDsi: {0}
Birinchi atribut: {1}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>{count} ta qatlamda filtrlash boshlanmoqda</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>{count} ta qatlamdan filtrlar olib tashlanmoqda</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>{count} ta qatlam tiklanmoqda</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>{count} ta qatlam eksport qilinmoqda</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>{count} ta qatlam muvaffaqiyatli filtrlandi</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>{count} ta qatlamdan filtrlar muvaffaqiyatli olib tashlandi</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>{count} ta qatlam muvaffaqiyatli tiklandi</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>{count} ta qatlam muvaffaqiyatli eksport qilindi</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>PostgreSQL siz katta ma&apos;lumotlar to&apos;plami ({count} ta obyekt). Ishlash samaradorligi kamayishi mumkin.</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>Yaxshiroq ishlash uchun PostgreSQL tavsiya etiladi.</translation>
    </message>
</context>
<context>
    <name>OptimizationDialogs</name>
    <message>
        <source>FilterMate - Optimizations</source>
        <translation>FilterMate - Optimallashtirish</translation>
    </message>
    <message>
        <source>Optimizations for:</source>
        <translation>Optimallashtirish uchun:</translation>
    </message>
    <message>
        <source>features</source>
        <translation>obyekt</translation>
    </message>
    <message>
        <source>Estimated speedup:</source>
        <translation>Taxminiy tezlashtirish:</translation>
    </message>
    <message>
        <source>faster</source>
        <translation>tezroq</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for large datasets</source>
        <translation>Katta ma&apos;lumotlar to&apos;plami uchun to&apos;liq geometriyalar o&apos;rniga markazlardan foydalaning</translation>
    </message>
    <message>
        <source>Use centroids</source>
        <translation>Markazlardan foydalanish</translation>
    </message>
    <message>
        <source>Simplify complex geometries to reduce processing time</source>
        <translation>Ishlash vaqtini qisqartirish uchun murakkab geometriyalarni soddalashtiring</translation>
    </message>
    <message>
        <source>Simplify geometries</source>
        <translation>Geometriyalarni soddalashtirish</translation>
    </message>
    <message>
        <source>Filter by bounding box first to eliminate distant features quickly</source>
        <translation>Uzoqdagi obyektlarni tezda yo&apos;q qilish uchun avval chegaralovchi quti bo&apos;yicha filtrlang</translation>
    </message>
    <message>
        <source>BBox pre-filtering</source>
        <translation>BBox oldindan filtrlash</translation>
    </message>
    <message>
        <source>Evaluate attribute conditions before expensive spatial operations</source>
        <translation>Qimmat fazoviy operatsiyalardan oldin atribut shartlarini baholang</translation>
    </message>
    <message>
        <source>Attribute-first strategy</source>
        <translation>Avval atribut strategiyasi</translation>
    </message>
    <message>
        <source>Apply for current session only</source>
        <translation>Faqat joriy seans uchun qo&apos;llash</translation>
    </message>
    <message>
        <source>Remember for this session</source>
        <translation>Bu seans uchun eslab qolish</translation>
    </message>
    <message>
        <source>Skip without applying</source>
        <translation>Qo&apos;llamay o&apos;tkazib yuborish</translation>
    </message>
    <message>
        <source>Skip</source>
        <translation>O&apos;tkazib yuborish</translation>
    </message>
    <message>
        <source>Apply selected optimizations</source>
        <translation>Tanlangan optimallashtirish qo&apos;llash</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>Qo&apos;llash</translation>
    </message>
    <message>
        <source>Optimization Settings</source>
        <translation>Optimallashtirish sozlamalari</translation>
    </message>
    <message>
        <source>Enable automatic optimizations</source>
        <translation>Avtomatik optimallashtirish yoqish</translation>
    </message>
    <message>
        <source>Enable optimizations</source>
        <translation>Optimallashtirish yoqish</translation>
    </message>
    <message>
        <source>Auto-apply recommendations</source>
        <translation>Tavsiyalarni avtomatik qo&apos;llash</translation>
    </message>
    <message>
        <source>Ask before applying</source>
        <translation>Qo&apos;llashdan oldin so&apos;rash</translation>
    </message>
    <message>
        <source>Show optimization dialog</source>
        <translation>Optimallashtirish dialogini ko&apos;rsatish</translation>
    </message>
    <message>
        <source>Never apply</source>
        <translation>Hech qachon qo&apos;llamang</translation>
    </message>
    <message>
        <source>No optimizations</source>
        <translation>Optimallashtirish yo&apos;q</translation>
    </message>
</context>
</TS>
