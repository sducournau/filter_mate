<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="pl_PL" sourcelanguage="en_US">
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
        <translation>Otwórz panel FilterMate</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Zresetuj konfigurację i bazę danych</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>Przywróć domyślną konfigurację i usuń bazę danych SQLite</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>Zresetuj konfigurację</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>Czy na pewno chcesz przywrócić domyślną konfigurację?

Spowoduje to:
- Zresetowanie wszystkich ustawień FilterMate
- Usunięcie wszystkich baz danych historii filtrów</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>Konfiguracja została pomyślnie zresetowana.</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>Nie znaleziono domyślnego pliku konfiguracyjnego.</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>Baza danych usunięta: {filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>Nie można usunąć {filename}: {error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>Wymagane ponowne uruchomienie</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>Konfiguracja została zresetowana.

Uruchom ponownie QGIS, aby zastosować wszystkie zmiany.</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>Błąd podczas resetowania: {error}</translation>
    </message>
    <message>
        <source>Obsolete configuration detected</source>
        <translation>Wykryto przestarzałą konfigurację</translation>
    </message>
    <message>
        <source>unknown version</source>
        <translation>nieznana wersja</translation>
    </message>
    <message>
        <source>Corrupted configuration detected</source>
        <translation>Wykryto uszkodzoną konfigurację</translation>
    </message>
    <message>
        <source>Configuration not reset. Some features may not work correctly.</source>
        <translation>Konfiguracja nie została zresetowana. Niektóre funkcje mogą nie działać poprawnie.</translation>
    </message>
    <message>
        <source>Configuration created with default values</source>
        <translation>Konfiguracja utworzona z wartościami domyślnymi</translation>
    </message>
    <message>
        <source>Corrupted configuration reset. Default settings have been restored.</source>
        <translation>Uszkodzona konfiguracja została zresetowana. Przywrócono ustawienia domyślne.</translation>
    </message>
    <message>
        <source>Obsolete configuration reset. Default settings have been restored.</source>
        <translation>Przestarzała konfiguracja została zresetowana. Przywrócono ustawienia domyślne.</translation>
    </message>
    <message>
        <source>Configuration updated to latest version</source>
        <translation>Konfiguracja zaktualizowana do najnowszej wersji</translation>
    </message>
    <message>
        <source>Configuration updated: new settings available ({sections}). Access via Options menu.</source>
        <translation>Konfiguracja zaktualizowana: nowe ustawienia dostępne ({sections}). Dostęp przez menu Opcje.</translation>
    </message>
    <message>
        <source>Geometry Simplification</source>
        <translation>Uproszczenie geometrii</translation>
    </message>
    <message>
        <source>Optimization Thresholds</source>
        <translation>Progi optymalizacji</translation>
    </message>
    <message>
        <source>Geometry validation setting</source>
        <translation>Ustawienie walidacji geometrii</translation>
    </message>
    <message>
        <source>Invalid geometry filtering disabled successfully.</source>
        <translation>Filtrowanie nieprawidłowych geometrii zostało pomyślnie wyłączone.</translation>
    </message>
    <message>
        <source>Invalid geometry filtering not modified. Some features may be excluded from exports.</source>
        <translation>Filtrowanie nieprawidłowych geometrii nie zostało zmienione. Niektóre obiekty mogą zostać wykluczone z eksportu.</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive=expand, negative=shrink polygons)</source>
        <translation>Wartość bufora w metrach (dodatnia=rozszerz, ujemna=zmniejsz wielokąty)</translation>
    </message>
    <message>
        <source>Negative buffer (erosion): shrinks polygons inward</source>
        <translation>Bufor ujemny (erozja): zmniejsza wielokąty do wewnątrz</translation>
    </message>
    <message>
        <source>point</source>
        <translation>punkt</translation>
    </message>
    <message>
        <source>line</source>
        <translation>linia</translation>
    </message>
    <message>
        <source>non-polygon</source>
        <translation>nie-wielokąt</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive only when centroids are enabled. Negative buffers cannot be applied to points)</source>
        <translation>Wartość bufora w metrach (tylko dodatnia gdy centroidy są włączone. Ujemne bufory nie mogą być stosowane do punktów)</translation>
    </message>
    <message>
        <source>Mode batch</source>
        <translation>Tryb wsadowy</translation>
    </message>
    <message>
        <source>Number of segments for buffer precision</source>
        <translation>Liczba segmentów dla precyzji bufora</translation>
    </message>
    <message>
        <source>Centroids</source>
        <translation>Centroidy</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for distant layers (faster for complex polygons like buildings)</source>
        <translation>Użyj centroidów zamiast pełnych geometrii dla odległych warstw (szybsze dla złożonych poligonów jak budynki)</translation>
    </message>
    <message>
        <source>An obsolete configuration ({}) has been detected.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created)
• No: Keep current configuration (may cause issues)</source>
        <translation>Wykryto przestarzałą konfigurację ({}).

Czy chcesz przywrócić ustawienia domyślne?

• Tak: Przywróć (kopia zapasowa zostanie utworzona)
• Nie: Zachowaj bieżącą konfigurację (może powodować problemy)</translation>
    </message>
    <message>
        <source>The configuration file is corrupted and cannot be read.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created if possible)
• No: Cancel (the plugin may not work correctly)</source>
        <translation>Plik konfiguracji jest uszkodzony i nie można go odczytać.

Czy chcesz przywrócić ustawienia domyślne?

• Tak: Przywróć (kopia zapasowa zostanie utworzona, jeśli to możliwe)
• Nie: Anuluj (wtyczka może nie działać poprawnie)</translation>
    </message>
    <message>
        <source>Configuration reset</source>
        <translation>Resetowanie konfiguracji</translation>
    </message>
    <message>
        <source>The configuration needs to be reset.

Do you want to continue?</source>
        <translation>Konfiguracja wymaga zresetowania.

Czy chcesz kontynuować?</translation>
    </message>
    <message>
        <source>Error during configuration migration: {}</source>
        <translation>Błąd podczas migracji konfiguracji: {}</translation>
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
        <translation>The QGIS setting &apos;Invalid features filtering&apos; is currently set to &apos;{mode}&apos;.

FilterMate recommends disabling this setting (value &apos;Off&apos;) for the following reasons:

• Features with invalid geometries could be silently excluded from exports and filters
• FilterMate handles geometry validation internally with automatic repair options
• Some legitimate data may have geometries considered as &apos;invalid&apos; according to strict OGC rules

Do you want to disable this setting now?

• Yes: Disable filtering (recommended for FilterMate)
• No: Keep current setting</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Restore default settings
- Delete the layer database

QGIS must be restarted to apply the changes.</source>
        <translation>Czy na pewno chcesz przywrócić domyślną konfigurację?

To:
- Przywróci ustawienia domyślne
- Usunie bazę danych warstw

QGIS musi zostać uruchomiony ponownie, aby zastosować zmiany.</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply the changes.</source>
        <translation>Konfiguracja została zresetowana.

Uruchom ponownie QGIS, aby zastosować zmiany.</translation>
    </message>
    <message>
        <source>All layers using auto-selection</source>
        <translation>Wszystkie warstwy używają automatycznego wyboru</translation>
    </message>
    <message>
        <source>Auto-optimizer module not available</source>
        <translation>Moduł auto-optymalizacji niedostępny</translation>
    </message>
    <message>
        <source>Backend controller not available</source>
        <translation>Kontroler backendu niedostępny</translation>
    </message>
    <message>
        <source>Backend optimization unavailable</source>
        <translation>Optymalizacja backendu niedostępna</translation>
    </message>
    <message>
        <source>Could not reload plugin automatically.</source>
        <translation>Nie można automatycznie przeładować wtyczki.</translation>
    </message>
    <message>
        <source>Favorites manager not available</source>
        <translation>Menedżer ulubionych niedostępny</translation>
    </message>
    <message>
        <source>No PostgreSQL connection available</source>
        <translation>Brak dostępnego połączenia PostgreSQL</translation>
    </message>
    <message>
        <source>No layer selected. Please select a layer first.</source>
        <translation>Nie wybrano warstwy. Najpierw wybierz warstwę.</translation>
    </message>
    <message>
        <source>No optimizations selected to apply.</source>
        <translation>Nie wybrano optymalizacji do zastosowania.</translation>
    </message>
    <message>
        <source>No views to clean or cleanup failed</source>
        <translation>Brak widoków do wyczyszczenia lub czyszczenie nie powiodło się</translation>
    </message>
    <message>
        <source>Other Sessions Active</source>
        <translation>Inne sesje aktywne</translation>
    </message>
    <message>
        <source>PostgreSQL auto-cleanup disabled</source>
        <translation>Automatyczne czyszczenie PostgreSQL wyłączone</translation>
    </message>
    <message>
        <source>PostgreSQL auto-cleanup enabled</source>
        <translation>Automatyczne czyszczenie PostgreSQL włączone</translation>
    </message>
    <message>
        <source>PostgreSQL session views cleaned up</source>
        <translation>Widoki sesji PostgreSQL wyczyszczone</translation>
    </message>
    <message>
        <source>Schema cleanup cancelled</source>
        <translation>Czyszczenie schematu anulowane</translation>
    </message>
    <message>
        <source>Schema cleanup failed</source>
        <translation>Czyszczenie schematu nie powiodło się</translation>
    </message>
    <message>
        <source>UI configuration incomplete - check logs</source>
        <translation>Konfiguracja interfejsu niekompletna - sprawdź logi</translation>
    </message>
    <message>
        <source>disabled</source>
        <translation>wyłączony</translation>
    </message>
    <message>
        <source>enabled</source>
        <translation>włączony</translation>
    </message>
    <message>
        <source>★ No favorites saved
Click to add current filter</source>
        <translation>★ Brak zapisanych ulubionych
Kliknij, aby dodać bieżący filtr</translation>
    </message>
    <message>
        <source>★ {0} Favorites saved
Click to apply or manage</source>
        <translation>★ {0} ulubionych zapisanych
Kliknij, aby zastosować lub zarządzać</translation>
    </message>
    <message>
        <source>Initialization error: {}</source>
        <translation>Błąd inicjalizacji: {}</translation>
    </message>
    <message>
        <source>UI dimension error: {}</source>
        <translation>Błąd wymiarów interfejsu: {}</translation>
    </message>
    <message>
        <source>Forced {0} backend for {1} layer(s)</source>
        <translation>Wymuszono backend {0} dla {1} warstw(y)</translation>
    </message>
    <message>
        <source>Schema has {0} view(s) from other sessions.
Drop anyway?</source>
        <translation>Schemat ma {0} widok(ów) z innych sesji.
Usunąć mimo to?</translation>
    </message>
    <message>
        <source>Schema &apos;{0}&apos; dropped successfully</source>
        <translation>Schemat &apos;{0}&apos; pomyślnie usunięty</translation>
    </message>
    <message>
        <source>Auto-optimization {0}</source>
        <translation>Auto-optymalizacja {0}</translation>
    </message>
    <message>
        <source>Auto-centroid {0}</source>
        <translation>Auto-centroid {0}</translation>
    </message>
    <message>
        <source>Confirmation {0}</source>
        <translation>Potwierdzenie {0}</translation>
    </message>
    <message>
        <source>Could not analyze layer &apos;{0}&apos;</source>
        <translation>Nie można przeanalizować warstwy &apos;{0}&apos;</translation>
    </message>
    <message>
        <source>Layer &apos;{0}&apos; is already optimally configured.
Type: {1}
Features: {2:,}</source>
        <translation>Warstwa &apos;{0}&apos; jest już optymalnie skonfigurowana.
Typ: {1}
Obiekty: {2:,}</translation>
    </message>
    <message>
        <source>Auto-optimizer not available: {0}</source>
        <translation>Auto-optymalizator niedostępny: {0}</translation>
    </message>
    <message>
        <source>Error analyzing layer: {0}</source>
        <translation>Błąd podczas analizowania warstwy: {0}</translation>
    </message>
    <message>
        <source>Applied to &apos;{0}&apos;:
{1}</source>
        <translation>Zastosowano do &apos;{0}&apos;:
{1}</translation>
    </message>
    <message>
        <source>Dialog not available: {0}</source>
        <translation>Okno dialogowe niedostępne: {0}</translation>
    </message>
    <message>
        <source>Error: {0}</source>
        <translation>Błąd: {0}</translation>
    </message>
    <message>
        <source>Optimized {0} layer(s)</source>
        <translation>Zoptymalizowano {0} warstw(ę/y)</translation>
    </message>
    <message>
        <source>Error cancelling changes: {0}</source>
        <translation>Błąd podczas anulowania zmian: {0}</translation>
    </message>
    <message>
        <source>Error reloading plugin: {0}</source>
        <translation>Błąd podczas przeładowywania wtyczki: {0}</translation>
    </message>
    <message>
        <source>No alternative backends available for this layer</source>
        <translation>Brak alternatywnych backendów dla tej warstwy</translation>
    </message>
    <message>
        <source>📁 Current Project</source>
        <translation>📁 Bieżący projekt</translation>
    </message>
    <message>
        <source>Clear temporary tables for the current project only</source>
        <translation>Wyczyść tabele tymczasowe tylko dla bieżącego projektu</translation>
    </message>
    <message>
        <source>🌐 All Projects (Global)</source>
        <translation>🌐 Wszystkie projekty (Globalne)</translation>
    </message>
    <message>
        <source>Clear ALL FilterMate temporary tables from all databases</source>
        <translation>Wyczyść WSZYSTKIE tabele tymczasowe FilterMate ze wszystkich baz danych</translation>
    </message>
    <message>
        <source>Auto-selected backends for {0} layer(s)</source>
        <translation>Automatycznie wybrane backendy dla {0} warstw(y)</translation>
    </message>
    <message>
        <source>Cleared {0} temporary table(s) for current project</source>
        <translation>Wyczyszczono {0} tabel(ę/y) tymczasowych dla bieżącego projektu</translation>
    </message>
    <message>
        <source>No temporary tables found for current project</source>
        <translation>Nie znaleziono tabel tymczasowych dla bieżącego projektu</translation>
    </message>
    <message>
        <source>Cleared {0} temporary table(s) globally</source>
        <translation>Wyczyszczono {0} tabel(ę/y) tymczasowych globalnie</translation>
    </message>
    <message>
        <source>No temporary tables found</source>
        <translation>Nie znaleziono tabel tymczasowych</translation>
    </message>
    <message>
        <source>Backend forced to {0} for &apos;{1}&apos;</source>
        <translation>Backend wymuszony na {0} dla &apos;{1}&apos;</translation>
    </message>
    <message>
        <source>Backend set to Auto for &apos;{0}&apos;</source>
        <translation>Backend ustawiony na Auto dla &apos;{0}&apos;</translation>
    </message>
    <message>
        <source>Undo last filter (Ctrl+Z)</source>
        <translation>Cofnij ostatni filtr (Ctrl+Z)</translation>
    </message>
    <message>
        <source>Redo filter (Ctrl+Y)</source>
        <translation>Ponów filtr (Ctrl+Y)</translation>
    </message>
    <message>
        <source>Filter history position</source>
        <translation>Pozycja w historii filtrów</translation>
    </message>
    <message>
        <source>FilterMate - Add to Favorites</source>
        <translation>FilterMate - Dodaj do ulubionych</translation>
    </message>
    <message>
        <source>Enter a name for this filter</source>
        <translation>Wprowadź nazwę dla tego filtra</translation>
    </message>
    <message>
        <source>Description (auto-generated, you can modify it)</source>
        <translation>Opis (wygenerowany automatycznie, możesz go zmodyfikować)</translation>
    </message>
    <message>
        <source>⭐ Add Current Filter to Favorites</source>
        <translation>⭐ Dodaj bieżący filtr do ulubionych</translation>
    </message>
    <message>
        <source>⭐ Add Current Filter (no filter active)</source>
        <translation>⭐ Dodaj bieżący filtr (brak aktywnego filtra)</translation>
    </message>
    <message>
        <source>⭐ Add current filter to favorites</source>
        <translation>⭐ Dodaj bieżący filtr do ulubionych</translation>
    </message>
    <message>
        <source>⭐ Add filter (no active filter)</source>
        <translation>⭐ Dodaj filtr (brak aktywnego filtra)</translation>
    </message>
    <message>
        <source>⚙️ Manage favorites...</source>
        <translation>⚙️ Zarządzaj ulubionymi...</translation>
    </message>
    <message>
        <source>📤 Export...</source>
        <translation>📤 Eksportuj...</translation>
    </message>
    <message>
        <source>📥 Import...</source>
        <translation>📥 Importuj...</translation>
    </message>
    <message>
        <source>The selected layer is invalid or its source cannot be found.</source>
        <translation>Wybrana warstwa jest nieprawidłowa lub nie można znaleźć jej źródła.</translation>
    </message>
    <message>
        <source>Plugin activated with {0} vector layer(s)</source>
        <translation>Wtyczka aktywowana z {0} warstwami wektorowymi</translation>
    </message>
    <message>
        <source>Theme adapted: {0}</source>
        <translation>Motyw dostosowany: {0}</translation>
    </message>
    <message>
        <source>Dark mode</source>
        <translation>Tryb ciemny</translation>
    </message>
    <message>
        <source>Light mode</source>
        <translation>Tryb jasny</translation>
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
        <translation>POJEDYNCZY WYBÓR</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>WIELOKROTNY WYBÓR</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>NIESTANDARDOWY WYBÓR</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>FILTROWANIE</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>EKSPORTOWANIE</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>KONFIGURACJA</translation>
    </message>
    <message>
        <source>Identify feature - Display feature attributes</source>
        <translation>Identyfikuj obiekt - Wyświetl atrybuty obiektu</translation>
    </message>
    <message>
        <source>Zoom to feature - Center the map on the selected feature</source>
        <translation>Powiększ do obiektu - Wyśrodkuj mapę na wybranym obiekcie</translation>
    </message>
    <message>
        <source>Enable selection - Select features on map</source>
        <translation>Włącz wybór - Wybierz obiekty na mapie</translation>
    </message>
    <message>
        <source>Enable tracking - Follow the selected feature on the map</source>
        <translation>Włącz śledzenie - Śledź wybrany obiekt na mapie</translation>
    </message>
    <message>
        <source>Link widgets - Synchronize selection between widgets</source>
        <translation>Połącz widżety - Synchronizuj wybór między widżetami</translation>
    </message>
    <message>
        <source>Reset layer properties - Restore default layer settings</source>
        <translation>Zresetuj właściwości warstwy - Przywróć domyślne ustawienia warstwy</translation>
    </message>
    <message>
        <source>Auto-sync with current layer - Automatically update when layer changes</source>
        <translation>Automatyczna synchronizacja z bieżącą warstwą - Automatycznie aktualizuj przy zmianie warstwy</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>Włącz filtrowanie wielowarstwowe - Zastosuj filtr do wielu warstw jednocześnie</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>Włącz filtrowanie addytywne - Łącz wiele filtrów na bieżącej warstwie</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>Włącz filtrowanie przestrzenne - Filtruj obiekty używając relacji geometrycznych</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>Włącz bufor - Dodaj strefę buforową wokół wybranych obiektów</translation>
    </message>
    <message>
        <source>Buffer type - Select the buffer calculation method</source>
        <translation>Typ bufora - Wybierz metodę obliczania bufora</translation>
    </message>
    <message>
        <source>Current layer - Select the layer to filter</source>
        <translation>Bieżąca warstwa - Wybierz warstwę do filtrowania</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>Operator logiczny do łączenia filtrów na warstwie źródłowej</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on other layers</source>
        <translation>Operator logiczny do łączenia filtrów na innych warstwach</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>Wybierz predykat(y) geometryczny(e) do filtrowania przestrzennego</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>Odległość bufora w metrach</translation>
    </message>
    <message>
        <source>Buffer type - Define how the buffer is calculated</source>
        <translation>Typ bufora - Określ sposób obliczania bufora</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>Wybierz warstwy do eksportu</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>Skonfiguruj projekcję wyjściową</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>Eksportuj style warstw (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>Wybierz format wyjściowy</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>Skonfiguruj lokalizację i nazwę pliku wyjściowego</translation>
    </message>
    <message>
        <source>Enable ZIP compression - Create a compressed archive of exported files</source>
        <translation>Włącz kompresję ZIP - Utwórz skompresowane archiwum eksportowanych plików</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>Wybierz układ współrzędnych do eksportu</translation>
    </message>
    <message>
        <source>Style format - Select QML or SLD format</source>
        <translation>Format stylu - Wybierz format QML lub SLD</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>Format pliku wyjściowego</translation>
    </message>
    <message>
        <source>Output folder name - Enter the name of the export folder</source>
        <translation>Nazwa folderu wyjściowego - Wprowadź nazwę folderu eksportu</translation>
    </message>
    <message>
        <source>Enter folder name...</source>
        <translation>Wprowadź nazwę folderu...</translation>
    </message>
    <message>
        <source>Batch mode - Export each layer to a separate folder</source>
        <translation>Tryb wsadowy - Eksportuj każdą warstwę do oddzielnego folderu</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>Tryb wsadowy</translation>
    </message>
    <message>
        <source>ZIP filename - Enter the name for the compressed archive</source>
        <translation>Nazwa pliku ZIP - Wprowadź nazwę skompresowanego archiwum</translation>
    </message>
    <message>
        <source>Enter ZIP filename...</source>
        <translation>Wprowadź nazwę pliku ZIP...</translation>
    </message>
    <message>
        <source>Batch mode - Create a separate ZIP for each layer</source>
        <translation>Tryb wsadowy - Utwórz oddzielny ZIP dla każdej warstwy</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>Zastosuj filtr - Wykonaj bieżący filtr na wybranych warstwach</translation>
    </message>
    <message>
        <source>Apply Filter</source>
        <translation>Zastosuj filtr</translation>
    </message>
    <message>
        <source>Apply the current filter expression to filter features on the selected layer(s)</source>
        <translation>Zastosuj bieżące wyrażenie filtra do filtrowania obiektów na wybranej warstwie(warstwach)</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>Cofnij filtr - Przywróć poprzedni stan filtra</translation>
    </message>
    <message>
        <source>Undo Filter</source>
        <translation>Cofnij filtr</translation>
    </message>
    <message>
        <source>Undo the last filter operation and restore the previous state</source>
        <translation>Cofnij ostatnią operację filtrowania i przywróć poprzedni stan</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>Ponów filtr - Ponownie zastosuj wcześniej cofnięty filtr</translation>
    </message>
    <message>
        <source>Redo Filter</source>
        <translation>Ponów filtr</translation>
    </message>
    <message>
        <source>Redo the previously undone filter operation</source>
        <translation>Ponów wcześniej cofniętą operację filtrowania</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>Wyczyść wszystkie filtry - Usuń wszystkie filtry ze wszystkich warstw</translation>
    </message>
    <message>
        <source>Clear All Filters</source>
        <translation>Wyczyść wszystkie filtry</translation>
    </message>
    <message>
        <source>Remove all active filters from all layers in the project</source>
        <translation>Usuń wszystkie aktywne filtry ze wszystkich warstw w projekcie</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>Eksportuj - Zapisz przefiltrowane warstwy w określonej lokalizacji</translation>
    </message>
    <message>
        <source>Export</source>
        <translation>Eksportuj</translation>
    </message>
    <message>
        <source>Export the filtered layers to the configured output location and format</source>
        <translation>Eksportuj przefiltrowane warstwy do skonfigurowanej lokalizacji i formatu</translation>
    </message>
    <message>
        <source>About FilterMate - Display plugin information and help</source>
        <translation>O FilterMate - Wyświetl informacje o wtyczce i pomoc</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>I</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>I NIE</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>LUB</translation>
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
        <translation>Filtrowanie wielowarstwowe</translation>
    </message>
    <message>
        <source>Additive filtering for the selected layer</source>
        <translation>Filtrowanie addytywne dla wybranej warstwy</translation>
    </message>
    <message>
        <source>Geospatial filtering</source>
        <translation>Filtrowanie geoprzestrzenne</translation>
    </message>
    <message>
        <source>Buffer</source>
        <translation>Bufor</translation>
    </message>
    <message>
        <source>Expression layer</source>
        <translation>Warstwa wyrażenia</translation>
    </message>
    <message>
        <source>Geometric predicate</source>
        <translation>Predykat geometryczny</translation>
    </message>
    <message>
        <source>Value in meters</source>
        <translation>Wartość w metrach</translation>
    </message>
    <message>
        <source>Output format</source>
        <translation>Format wyjściowy</translation>
    </message>
    <message>
        <source>Filter</source>
        <translation>Filtr</translation>
    </message>
    <message>
        <source>Reset</source>
        <translation>Resetuj</translation>
    </message>
    <message>
        <source>Layers to export</source>
        <translation>Warstwy do eksportu</translation>
    </message>
    <message>
        <source>Layers projection</source>
        <translation>Projekcja warstw</translation>
    </message>
    <message>
        <source>Save styles</source>
        <translation>Zapisz style</translation>
    </message>
    <message>
        <source>Datatype export</source>
        <translation>Eksport typu danych</translation>
    </message>
    <message>
        <source>Name of file/directory</source>
        <translation>Nazwa pliku/katalogu</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidget</name>
    <message>
        <source>Reload the plugin to apply layout changes (action bar position)</source>
        <translation>Przeładuj wtyczkę, aby zastosować zmiany układu (pozycja paska akcji)</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>Przeładuj wtyczkę</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>Czy chcesz przeładować FilterMate, aby zastosować wszystkie zmiany konfiguracji?</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>Bieżąca warstwa: {name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>Nie wybrano warstwy</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>Wybrane warstwy:</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>Wybrano wiele warstw</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>Nie wybrano warstw</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>Wyrażenie:</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>Nie zdefiniowano wyrażenia</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>Wyrażenie wyświetlania: {expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>ID obiektu: {id}</translation>
    </message>
    <message>
        <source>Current layer: {0}</source>
        <translation>Bieżąca warstwa: {0}</translation>
    </message>
    <message>
        <source>Selected layers:
{0}</source>
        <translation>Wybrane warstwy:
{0}</translation>
    </message>
    <message>
        <source>Expression:
{0}</source>
        <translation>Wyrażenie:
{0}</translation>
    </message>
    <message>
        <source>Expression: {0}</source>
        <translation>Wyrażenie: {0}</translation>
    </message>
    <message>
        <source>Display expression: {0}</source>
        <translation>Wyrażenie wyświetlania: {0}</translation>
    </message>
    <message>
        <source>Feature ID: {0}
First attribute: {1}</source>
        <translation>ID obiektu: {0}
Pierwszy atrybut: {1}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>Rozpoczynanie filtrowania na {count} warstwie(warstwach)</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>Usuwanie filtrów z {count} warstwy(warstw)</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>Resetowanie {count} warstwy(warstw)</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>Eksportowanie {count} warstwy(warstw)</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>Pomyślnie przefiltrowano {count} warstwę(warstw)</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>Pomyślnie usunięto filtry z {count} warstwy(warstw)</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>Pomyślnie zresetowano {count} warstwę(warstw)</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>Pomyślnie wyeksportowano {count} warstwę(warstw)</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>Duży zbiór danych ({count} obiektów) bez PostgreSQL. Wydajność może być obniżona.</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>Zalecany PostgreSQL dla lepszej wydajności.</translation>
    </message>
</context>
<context>
    <name>OptimizationDialogs</name>
    <message>
        <source>FilterMate - Optimizations</source>
        <translation>FilterMate - Optymalizacje</translation>
    </message>
    <message>
        <source>Optimizations for:</source>
        <translation>Optymalizacje dla:</translation>
    </message>
    <message>
        <source>features</source>
        <translation>obiektów</translation>
    </message>
    <message>
        <source>Estimated speedup:</source>
        <translation>Szacowane przyspieszenie:</translation>
    </message>
    <message>
        <source>faster</source>
        <translation>szybciej</translation>
    </message>
    <message>
        <source>Use centroids</source>
        <translation>Użyj centroidów</translation>
    </message>
    <message>
        <source>Use centroids for distant layers</source>
        <translation>Użyj centroidów dla odległych warstw</translation>
    </message>
    <message>
        <source>Enable buffer type</source>
        <translation>Włącz typ bufora</translation>
    </message>
    <message>
        <source>Simplify geometries</source>
        <translation>Uprość geometrie</translation>
    </message>
    <message>
        <source>BBox pre-filtering</source>
        <translation>Wstępne filtrowanie BBox</translation>
    </message>
    <message>
        <source>Attribute-first strategy</source>
        <translation>Strategia atrybuty najpierw</translation>
    </message>
    <message>
        <source>Remember for this session</source>
        <translation>Zapamiętaj dla tej sesji</translation>
    </message>
    <message>
        <source>Skip</source>
        <translation>Pomiń</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>Zastosuj</translation>
    </message>
    <message>
        <source>Optimization Settings</source>
        <translation>Ustawienia optymalizacji</translation>
    </message>
    <message>
        <source>Enable optimizations</source>
        <translation>Włącz optymalizacje</translation>
    </message>
    <message>
        <source>Suggest performance optimizations before filtering</source>
        <translation>Sugeruj optymalizacje wydajności przed filtrowaniem</translation>
    </message>
    <message>
        <source>Auto-use centroids for remote layers</source>
        <translation>Auto. użyj centroidów dla zdalnych warstw</translation>
    </message>
    <message>
        <source>Use centroids to reduce network transfer (~90% faster)</source>
        <translation>Użyj centroidów aby zmniejszyć transfer sieciowy (~90% szybciej)</translation>
    </message>
    <message>
        <source>Auto-select best strategy</source>
        <translation>Auto. wybierz najlepszą strategię</translation>
    </message>
    <message>
        <source>Automatically choose optimal filtering strategy</source>
        <translation>Automatycznie wybierz optymalną strategię filtrowania</translation>
    </message>
    <message>
        <source>Auto-simplify geometries</source>
        <translation>Auto. uprość geometrie</translation>
    </message>
    <message>
        <source>Warning: lossy operation, may change polygon shapes</source>
        <translation>Uwaga: operacja stratna, może zmienić kształty wielokątów</translation>
    </message>
    <message>
        <source>Ask before applying</source>
        <translation>Pytaj przed zastosowaniem</translation>
    </message>
    <message>
        <source>Show confirmation dialog before optimizations</source>
        <translation>Pokaż dialog potwierdzenia przed optymalizacjami</translation>
    </message>
    <message>
        <source>Centroids enabled for &apos;{0}&apos; (~{1}x {2})</source>
        <translation>Centroidy włączone dla &apos;{0}&apos; (~{1}x {2})</translation>
    </message>
    <message>
        <source>BBox pre-filter enabled for &apos;{0}&apos;</source>
        <translation>Wstępny filtr BBox włączony dla &apos;{0}&apos;</translation>
    </message>
    <message>
        <source>Optimization applied: &apos;{0}&apos; (~{1}x {2})</source>
        <translation>Optymalizacja zastosowana: &apos;{0}&apos; (~{1}x {2})</translation>
    </message>
    <message>
        <source>Simplify before buffer</source>
        <translation>Uprość przed buforem</translation>
    </message>
    <message>
        <source>Reduce buffer segments</source>
        <translation>Zmniejsz segmenty bufora</translation>
    </message>
</context>
<context>
    <name>BackendOptimizationWidget</name>
    <message>
        <source>Quick Setup</source>
        <translation>Szybka konfiguracja</translation>
    </message>
    <message>
        <source>Choose a profile or customize settings below</source>
        <translation>Wybierz profil lub dostosuj ustawienia poniżej</translation>
    </message>
    <message>
        <source>Smart Recommendations</source>
        <translation>Inteligentne zalecenia</translation>
    </message>
    <message>
        <source>Balanced Profile</source>
        <translation>Profil zrównoważony</translation>
    </message>
    <message>
        <source>Maximum Performance</source>
        <translation>Maksymalna wydajność</translation>
    </message>
    <message>
        <source>Minimal Resources</source>
        <translation>Minimalne zasoby</translation>
    </message>
    <message>
        <source>PostgreSQL/PostGIS Optimizations</source>
        <translation>Optymalizacje PostgreSQL/PostGIS</translation>
    </message>
    <message>
        <source>Materialized Views</source>
        <translation>Widoki zmaterializowane</translation>
    </message>
    <message>
        <source>Create temporary materialized views for complex filters</source>
        <translation>Twórz tymczasowe widoki zmaterializowane dla złożonych filtrów</translation>
    </message>
    <message>
        <source>Two-Phase Filtering</source>
        <translation>Filtrowanie dwufazowe</translation>
    </message>
    <message>
        <source>Use bounding box pre-filtering before precise geometry tests</source>
        <translation>Użyj wstępnego filtrowania ramki granicznej przed precyzyjnymi testami geometrii</translation>
    </message>
    <message>
        <source>Progressive Loading</source>
        <translation>Ładowanie progresywne</translation>
    </message>
    <message>
        <source>Load data in chunks for very large datasets</source>
        <translation>Ładuj dane w częściach dla bardzo dużych zbiorów danych</translation>
    </message>
    <message>
        <source>Chunk Size</source>
        <translation>Rozmiar części</translation>
    </message>
    <message>
        <source>Server-Side Simplification</source>
        <translation>Uproszczenie po stronie serwera</translation>
    </message>
    <message>
        <source>Simplify geometries on server for display purposes</source>
        <translation>Upraszczaj geometrie na serwerze dla celów wyświetlania</translation>
    </message>
    <message>
        <source>Simplification Tolerance</source>
        <translation>Tolerancja uproszczenia</translation>
    </message>
    <message>
        <source>Parallel Query Execution</source>
        <translation>Równoległe wykonywanie zapytań</translation>
    </message>
    <message>
        <source>Execute independent queries in parallel</source>
        <translation>Wykonuj niezależne zapytania równolegle</translation>
    </message>
    <message>
        <source>Expression Caching</source>
        <translation>Buforowanie wyrażeń</translation>
    </message>
    <message>
        <source>Cache compiled expressions for reuse</source>
        <translation>Buforuj skompilowane wyrażenia do ponownego użycia</translation>
    </message>
    <message>
        <source>Spatialite/GeoPackage Optimizations</source>
        <translation>Optymalizacje Spatialite/GeoPackage</translation>
    </message>
    <message>
        <source>R-tree Temp Tables</source>
        <translation>Tabele tymczasowe R-tree</translation>
    </message>
    <message>
        <source>Create temporary tables with R-tree indexes</source>
        <translation>Twórz tabele tymczasowe z indeksami R-tree</translation>
    </message>
    <message>
        <source>BBox Pre-filtering</source>
        <translation>Wstępne filtrowanie BBox</translation>
    </message>
    <message>
        <source>Use bounding box filtering before precise tests</source>
        <translation>Użyj filtrowania ramki granicznej przed precyzyjnymi testami</translation>
    </message>
    <message>
        <source>Memory-Mapped I/O</source>
        <translation>Mapowanie pamięci I/O</translation>
    </message>
    <message>
        <source>Use memory-mapped I/O for file access</source>
        <translation>Użyj mapowania pamięci I/O do dostępu do plików</translation>
    </message>
    <message>
        <source>Batch Processing</source>
        <translation>Przetwarzanie wsadowe</translation>
    </message>
    <message>
        <source>Process multiple operations in batches</source>
        <translation>Przetwarzaj wiele operacji w partiach</translation>
    </message>
    <message>
        <source>Batch Size</source>
        <translation>Rozmiar partii</translation>
    </message>
    <message>
        <source>OGR/Memory Optimizations</source>
        <translation>Optymalizacje OGR/Pamięci</translation>
    </message>
    <message>
        <source>Automatic Spatial Index</source>
        <translation>Automatyczny indeks przestrzenny</translation>
    </message>
    <message>
        <source>Create temporary spatial indexes automatically</source>
        <translation>Twórz automatycznie tymczasowe indeksy przestrzenne</translation>
    </message>
    <message>
        <source>Progressive Chunking</source>
        <translation>Progresywne dzielenie</translation>
    </message>
    <message>
        <source>Process large files in progressive chunks</source>
        <translation>Przetwarzaj duże pliki w progresywnych częściach</translation>
    </message>
    <message>
        <source>Memory Feature Caching</source>
        <translation>Buforowanie obiektów w pamięci</translation>
    </message>
    <message>
        <source>Cache features in memory for faster access</source>
        <translation>Buforuj obiekty w pamięci dla szybszego dostępu</translation>
    </message>
    <message>
        <source>Cache Size (features)</source>
        <translation>Rozmiar bufora (obiekty)</translation>
    </message>
    <message>
        <source>Geometry Simplification</source>
        <translation>Uproszczenie geometrii</translation>
    </message>
    <message>
        <source>Simplify complex geometries during processing</source>
        <translation>Upraszczaj złożone geometrie podczas przetwarzania</translation>
    </message>
    <message>
        <source>Global Optimizations</source>
        <translation>Optymalizacje globalne</translation>
    </message>
    <message>
        <source>Auto-Optimization</source>
        <translation>Auto-optymalizacja</translation>
    </message>
    <message>
        <source>Automatically optimize based on data analysis</source>
        <translation>Automatycznie optymalizuj na podstawie analizy danych</translation>
    </message>
    <message>
        <source>Auto-Centroid</source>
        <translation>Auto-centroid</translation>
    </message>
    <message>
        <source>Automatically center view on filter results</source>
        <translation>Automatycznie centruj widok na wynikach filtrowania</translation>
    </message>
    <message>
        <source>Parallel Layer Filtering</source>
        <translation>Równoległe filtrowanie warstw</translation>
    </message>
    <message>
        <source>Filter multiple layers simultaneously</source>
        <translation>Filtruj wiele warstw jednocześnie</translation>
    </message>
    <message>
        <source>Smart Expression Parsing</source>
        <translation>Inteligentne parsowanie wyrażeń</translation>
    </message>
    <message>
        <source>Optimize expression parsing for complex queries</source>
        <translation>Optymalizuj parsowanie wyrażeń dla złożonych zapytań</translation>
    </message>
    <message>
        <source>Deferred Refresh</source>
        <translation>Odroczone odświeżanie</translation>
    </message>
    <message>
        <source>Delay map refresh until all filters are applied</source>
        <translation>Opóźnij odświeżanie mapy do momentu zastosowania wszystkich filtrów</translation>
    </message>
    <message>
        <source>Verbose Logging</source>
        <translation>Szczegółowe logowanie</translation>
    </message>
    <message>
        <source>Enable detailed logging for debugging</source>
        <translation>Włącz szczegółowe logowanie do debugowania</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>Zastosuj</translation>
    </message>
    <message>
        <source>Reset to Defaults</source>
        <translation>Przywróć domyślne</translation>
    </message>
    <message>
        <source>Settings applied successfully</source>
        <translation>Ustawienia zastosowane pomyślnie</translation>
    </message>
    <message>
        <source>Settings reset to defaults</source>
        <translation>Ustawienia przywrócone do domyślnych</translation>
    </message>
    <message>
        <source>Profile applied: {}</source>
        <translation>Profil zastosowany: {}</translation>
    </message>
    <message>
        <source>Error applying settings</source>
        <translation>Błąd podczas stosowania ustawień</translation>
    </message>
    <message>
        <source>MV Status: Checking...</source>
        <translation>Status MV: Sprawdzanie...</translation>
    </message>
    <message>
        <source>MV Status: Error</source>
        <translation>Status MV: Błąd</translation>
    </message>
    <message>
        <source>MV Status: Clean</source>
        <translation>Status MV: Czysty</translation>
    </message>
    <message>
        <source>MV Status:</source>
        <translation>Status MV:</translation>
    </message>
    <message>
        <source>active</source>
        <translation>aktywny</translation>
    </message>
    <message>
        <source>No active materialized views</source>
        <translation>Brak aktywnych widoków zmaterializowanych</translation>
    </message>
    <message>
        <source>Session:</source>
        <translation>Sesja:</translation>
    </message>
    <message>
        <source>Other sessions:</source>
        <translation>Inne sesje:</translation>
    </message>
    <message>
        <source>🧹 Session</source>
        <translation>🧹 Sesja</translation>
    </message>
    <message>
        <source>Cleanup MVs from this session</source>
        <translation>Oczyść MV z tej sesji</translation>
    </message>
    <message>
        <source>🗑️ Orphaned</source>
        <translation>🗑️ Osierocone</translation>
    </message>
    <message>
        <source>Cleanup orphaned MVs (&gt;24h old)</source>
        <translation>Oczyść osierocone MV (&gt;24h)</translation>
    </message>
    <message>
        <source>⚠️ All</source>
        <translation>⚠️ Wszystkie</translation>
    </message>
    <message>
        <source>Cleanup ALL MVs (affects other sessions)</source>
        <translation>Oczyść WSZYSTKIE MV (wpływa na inne sesje)</translation>
    </message>
    <message>
        <source>Confirm Cleanup</source>
        <translation>Potwierdź czyszczenie</translation>
    </message>
    <message>
        <source>Drop ALL materialized views?
This affects other FilterMate sessions!</source>
        <translation>Usunąć WSZYSTKIE widoki zmaterializowane?
To wpłynie na inne sesje FilterMate!</translation>
    </message>
    <message>
        <source>Refresh MV status</source>
        <translation>Odśwież status MV</translation>
    </message>
    <message>
        <source>Threshold:</source>
        <translation>Próg:</translation>
    </message>
    <message>
        <source>features</source>
        <translation>funkcje</translation>
    </message>
    <message>
        <source>Auto-cleanup on exit</source>
        <translation>Auto-czyszczenie przy zamykaniu</translation>
    </message>
    <message>
        <source>Automatically drop session MVs when plugin unloads</source>
        <translation>Automatycznie usuń MV sesji gdy wtyczka zostanie odładowana</translation>
    </message>
    <message>
        <source>Create MVs for datasets larger than this</source>
        <translation>Utwórz MV dla zbiorów danych większych niż to</translation>
    </message>
    <message>
        <source>faster possible</source>
        <translation>szybsze możliwe</translation>
    </message>
    <message>
        <source>Optimizations available</source>
        <translation>Optymalizacje dostępne</translation>
    </message>
    <message>
        <source>FilterMate - Apply Optimizations?</source>
        <translation>FilterMate - Zastosować optymalizacje?</translation>
    </message>
    <message>
        <source>Skip</source>
        <translation>Pomiń</translation>
    </message>
    <message>
        <source>✓ Apply</source>
        <translation>✓ Zastosuj</translation>
    </message>
    <message>
        <source>Don&apos;t ask for this session</source>
        <translation>Nie pytaj dla tej sesji</translation>
    </message>
    <message>
        <source>Centroids</source>
        <translation>Centroidy</translation>
    </message>
    <message>
        <source>Simplify</source>
        <translation>Uprość</translation>
    </message>
    <message>
        <source>Pre-simplify</source>
        <translation>Wstępnie uprość</translation>
    </message>
    <message>
        <source>Fewer segments</source>
        <translation>Mniej segmentów</translation>
    </message>
    <message>
        <source>Flat buffer</source>
        <translation>Płaski bufor</translation>
    </message>
    <message>
        <source>BBox filter</source>
        <translation>Filtr BBox</translation>
    </message>
    <message>
        <source>Attr-first</source>
        <translation>Attr-najpierw</translation>
    </message>
    <message>
        <source>PostgreSQL not available</source>
        <translation>PostgreSQL niedostępny</translation>
    </message>
    <message>
        <source>No connection</source>
        <translation>Brak połączenia</translation>
    </message>
    <message>
        <source>Auto-zoom when feature changes</source>
        <translation>Auto-zoom przy zmianie funkcji</translation>
    </message>
    <message>
        <source>Backend optimization settings saved</source>
        <translation>Ustawienia optymalizacji backendu zapisane</translation>
    </message>
    <message>
        <source>Backend optimizations configured</source>
        <translation>Optymalizacje backendu skonfigurowane</translation>
    </message>
    <message>
        <source>Expression Evaluation</source>
        <translation>Ewaluacja wyrażenia</translation>
    </message>
    <message>
        <source>Identify selected feature</source>
        <translation>Zidentyfikuj wybraną funkcję</translation>
    </message>
    <message>
        <source>Layer properties reset to defaults</source>
        <translation>Właściwości warstwy zresetowane do domyślnych</translation>
    </message>
    <message>
        <source>Link exploring widgets together</source>
        <translation>Połącz widgety eksploracji</translation>
    </message>
    <message>
        <source>Optimization settings saved</source>
        <translation>Ustawienia optymalizacji zapisane</translation>
    </message>
    <message>
        <source>Reset all layer exploring properties</source>
        <translation>Zresetuj wszystkie właściwości eksploracji warstwy</translation>
    </message>
    <message>
        <source>Toggle feature selection on map</source>
        <translation>Przełącz wybór funkcji na mapie</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for distant layers (faster for complex polygons)</source>
        <translation>Użyj centroidów zamiast pełnych geometrii dla odległych warstw (szybsze dla złożonych wielokątów)</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for source layer (faster for complex polygons)</source>
        <translation>Użyj centroidów zamiast pełnych geometrii dla warstwy źródłowej (szybsze dla złożonych wielokątów)</translation>
    </message>
    <message>
        <source>Zoom to selected feature</source>
        <translation>Powiększ do wybranej funkcji</translation>
    </message>
</context>
<context>
    <name>OptimizationDialog</name>
    <message>
        <source>Optimization Settings</source>
        <translation>Ustawienia optymalizacji</translation>
    </message>
    <message>
        <source>Configure Optimization Settings</source>
        <translation>Skonfiguruj ustawienia optymalizacji</translation>
    </message>
    <message>
        <source>Enable automatic optimizations</source>
        <translation>Włącz automatyczne optymalizacje</translation>
    </message>
    <message>
        <source>Ask before applying optimizations</source>
        <translation>Pytaj przed zastosowaniem optymalizacji</translation>
    </message>
    <message>
        <source>Auto-Centroid Settings</source>
        <translation>Ustawienia auto-centroidu</translation>
    </message>
    <message>
        <source>Enable auto-centroid for distant layers</source>
        <translation>Włącz auto-centroid dla odległych warstw</translation>
    </message>
    <message>
        <source>Distance threshold (km):</source>
        <translation>Próg odległości (km):</translation>
    </message>
    <message>
        <source>Feature threshold:</source>
        <translation>Próg obiektów:</translation>
    </message>
    <message>
        <source>Buffer Optimizations</source>
        <translation>Optymalizacje bufora</translation>
    </message>
    <message>
        <source>Simplify geometry before buffer</source>
        <translation>Uprość geometrię przed buforem</translation>
    </message>
    <message>
        <source>Reduce buffer segments to:</source>
        <translation>Ogranicz segmenty bufora do:</translation>
    </message>
    <message>
        <source>General</source>
        <translation>Ogólne</translation>
    </message>
    <message>
        <source>Use materialized views for filtering</source>
        <translation>Użyj zmaterializowanych widoków do filtrowania</translation>
    </message>
    <message>
        <source>Create spatial indices automatically</source>
        <translation>Twórz indeksy przestrzenne automatycznie</translation>
    </message>
    <message>
        <source>Use R-tree spatial index</source>
        <translation>Użyj indeksu przestrzennego R-tree</translation>
    </message>
    <message>
        <source>Use bounding box pre-filter</source>
        <translation>Użyj pre-filtra bounding box</translation>
    </message>
    <message>
        <source>Backends</source>
        <translation>Backendy</translation>
    </message>
    <message>
        <source>Caching</source>
        <translation>Buforowanie</translation>
    </message>
    <message>
        <source>Enable geometry cache</source>
        <translation>Włącz pamięć podręczną geometrii</translation>
    </message>
    <message>
        <source>Batch Processing</source>
        <translation>Przetwarzanie wsadowe</translation>
    </message>
    <message>
        <source>Batch size:</source>
        <translation>Rozmiar paczki:</translation>
    </message>
    <message>
        <source>Advanced settings affect performance and memory usage. Change only if you understand the implications.</source>
        <translation>Zaawansowane ustawienia wpływają na wydajność i użycie pamięci. Zmieniaj tylko jeśli rozumiesz konsekwencje.</translation>
    </message>
    <message>
        <source>Advanced</source>
        <translation>Zaawansowane</translation>
    </message>
</context>
<context>
    <name>RecommendationDialog</name>
    <message>
        <source>Apply Optimizations?</source>
        <translation>Zastosować optymalizacje?</translation>
    </message>
    <message>
        <source>Optimizations Available</source>
        <translation>Dostępne optymalizacje</translation>
    </message>
    <message>
        <source>Skip</source>
        <translation>Pomiń</translation>
    </message>
    <message>
        <source>Apply Selected</source>
        <translation>Zastosuj wybrane</translation>
    </message>
</context>
<context>
    <name>PostgresInfoDialog</name>
    <message>
        <source>PostgreSQL Session Info</source>
        <translation>Info sesji PostgreSQL</translation>
    </message>
    <message>
        <source>PostgreSQL Active</source>
        <translation>PostgreSQL aktywny</translation>
    </message>
    <message>
        <source>Connection Info</source>
        <translation>Info połączenia</translation>
    </message>
    <message>
        <source>Connection:</source>
        <translation>Połączenie:</translation>
    </message>
    <message>
        <source>Temp Schema:</source>
        <translation>Schemat tymczasowy:</translation>
    </message>
    <message>
        <source>Status:</source>
        <translation>Status:</translation>
    </message>
    <message>
        <source>Temporary Views</source>
        <translation>Widoki tymczasowe</translation>
    </message>
    <message>
        <source>Cleanup Options</source>
        <translation>Opcje czyszczenia</translation>
    </message>
    <message>
        <source>Auto-cleanup on close</source>
        <translation>Automatyczne czyszczenie przy zamknięciu</translation>
    </message>
    <message>
        <source>Automatically cleanup temporary views when FilterMate closes.</source>
        <translation>Automatycznie czyść widoki tymczasowe przy zamykaniu FilterMate.</translation>
    </message>
    <message>
        <source>🗑️ Cleanup Now</source>
        <translation>🗑️ Wyczyść teraz</translation>
    </message>
    <message>
        <source>Drop all temporary views created by FilterMate in this session.</source>
        <translation>Usuń wszystkie widoki tymczasowe utworzone przez FilterMate w tej sesji.</translation>
    </message>
    <message>
        <source>(No temporary views)</source>
        <translation>(Brak widoków tymczasowych)</translation>
    </message>
    <message>
        <source>No Views</source>
        <translation>Brak widoków</translation>
    </message>
    <message>
        <source>There are no temporary views to clean up.</source>
        <translation>Nie ma widoków tymczasowych do wyczyszczenia.</translation>
    </message>
    <message>
        <source>Confirm Cleanup</source>
        <translation>Potwierdź czyszczenie</translation>
    </message>
    <message>
        <source>Cleanup Complete</source>
        <translation>Czyszczenie zakończone</translation>
    </message>
    <message>
        <source>Cleanup Issue</source>
        <translation>Problem z czyszczeniem</translation>
    </message>
    <message>
        <source>Cleanup Failed</source>
        <translation>Czyszczenie nie powiodło się</translation>
    </message>
</context>
</TS>
