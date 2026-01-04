<?xml version='1.0' encoding='utf-8'?>
<TS version="2.1" language="sl_SI" sourcelanguage="sl_SI">
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
        <translation>Odpri ploščo FilterMate</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Ponastavi konfiguracijo in bazo podatkov</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>Ponastavi privzeto konfiguracijo in izbriši SQLite bazo podatkov</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>Ponastavi konfiguracijo</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>Ali ste prepričani, da želite ponastaviti privzeto konfiguracijo?

To bo:
- Ponastavilo vse nastavitve FilterMate
- Izbrisalo vse baze podatkov zgodovine filtrov</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>Konfiguracija uspešno ponastavljena.</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>Privzeta konfiguracijska datoteka ni bila najdena.</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>Baza podatkov izbrisana: {filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>Ni mogoče izbrisati {filename}: {error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>Potreben ponovni zagon</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>Konfiguracija je bila ponastavljena.

Prosimo, ponovno zaženite QGIS za uporabo vseh sprememb.</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>Napaka med ponastavitvijo: {error}</translation>
    </message>
    <message>
        <source>Obsolete configuration detected</source>
        <translation>Zastarela konfiguracija zaznana</translation>
    </message>
    <message>
        <source>unknown version</source>
        <translation>neznana različica</translation>
    </message>
    <message>
        <source>An obsolete configuration ({}) has been detected.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created)
• No: Keep current configuration (may cause issues)</source>
        <translation>An obsolete configuration ({}) has been detected.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created)
• No: Keep current configuration (may cause issues)</translation>
    </message>
    <message>
        <source>Corrupted configuration detected</source>
        <translation>Poškodovana konfiguracija zaznana</translation>
    </message>
    <message>
        <source>The configuration file is corrupted and cannot be read.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created if possible)
• No: Cancel (the plugin may not work correctly)</source>
        <translation>The configuration file is corrupted and cannot be read.

Do you want to reset to default settings?

• Yes: Reset (a backup will be created if possible)
• No: Cancel (the plugin may not work correctly)</translation>
    </message>
    <message>
        <source>Configuration reset</source>
        <translation>Ponastavitev konfiguracije</translation>
    </message>
    <message>
        <source>The configuration needs to be reset.

Do you want to continue?</source>
        <translation>The configuration needs to be reset.

Do you want to continue?</translation>
    </message>
    <message>
        <source>Configuration not reset. Some features may not work correctly.</source>
        <translation>Konfiguracija ni bila ponastavljena. Nekatere funkcije morda ne bodo delovale pravilno.</translation>
    </message>
    <message>
        <source>Configuration created with default values</source>
        <translation>Konfiguracija ustvarjena s privzetimi vrednostmi</translation>
    </message>
    <message>
        <source>Corrupted configuration reset. Default settings have been restored.</source>
        <translation>Poškodovana konfiguracija ponastavljena. Privzete nastavitve so bile obnovljene.</translation>
    </message>
    <message>
        <source>Obsolete configuration reset. Default settings have been restored.</source>
        <translation>Zastarela konfiguracija ponastavljena. Privzete nastavitve so bile obnovljene.</translation>
    </message>
    <message>
        <source>Configuration updated to latest version</source>
        <translation>Konfiguracija posodobljena na najnovejšo različico</translation>
    </message>
    <message>
        <source>Configuration updated: new settings available ({sections}). Access via Options menu.</source>
        <translation>Konfiguracija posodobljena: nove nastavitve na voljo ({sections}). Dostop prek menija Možnosti.</translation>
    </message>
    <message>
        <source>Geometry Simplification</source>
        <translation>Poenostavitev geometrije</translation>
    </message>
    <message>
        <source>Optimization Thresholds</source>
        <translation>Pragovi optimizacije</translation>
    </message>
    <message>
        <source>Error during configuration migration: {}</source>
        <translation>Error during configuration migration: {}</translation>
    </message>
    <message>
        <source>Geometry validation setting</source>
        <translation>Nastavitev preverjanja geometrije</translation>
    </message>
    <message>
        <source>The QGIS setting 'Invalid features filtering' is currently set to '{mode}'.

FilterMate recommends disabling this setting (value 'Off') for the following reasons:

• Features with invalid geometries could be silently excluded from exports and filters
• FilterMate handles geometry validation internally with automatic repair options
• Some legitimate data may have geometries considered as 'invalid' according to strict OGC rules

Do you want to disable this setting now?

• Yes: Disable filtering (recommended for FilterMate)
• No: Keep current setting</source>
        <translation>The QGIS setting 'Invalid features filtering' is currently set to '{mode}'.

FilterMate recommends disabling this setting (value 'Off') for the following reasons:

• Features with invalid geometries could be silently excluded from exports and filters
• FilterMate handles geometry validation internally with automatic repair options
• Some legitimate data may have geometries considered as 'invalid' according to strict OGC rules

Do you want to disable this setting now?

• Yes: Disable filtering (recommended for FilterMate)
• No: Keep current setting</translation>
    </message>
    <message>
        <source>Invalid geometry filtering disabled successfully.</source>
        <translation>Filtriranje neveljavnih geometrij je uspešno onemogočeno.</translation>
    </message>
    <message>
        <source>Invalid geometry filtering not modified. Some features may be excluded from exports.</source>
        <translation>Filtriranje neveljavnih geometrij ni bilo spremenjeno. Nekatere funkcije so lahko izključene iz izvoza.</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Restore default settings
- Delete the layer database

QGIS must be restarted to apply the changes.</source>
        <translation>Are you sure you want to reset to the default configuration?

This will:
- Restore default settings
- Delete the layer database

QGIS must be restarted to apply the changes.</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply the changes.</source>
        <translation>The configuration has been reset.

Please restart QGIS to apply the changes.</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive=expand, negative=shrink polygons)</source>
        <translation>Vrednost medpomnilnika v metrih (pozitivno=razširi, negativno=skrči poligone)</translation>
    </message>
    <message>
        <source>Negative buffer (erosion): shrinks polygons inward</source>
        <translation>Negativni medpomnilnik (erozija): skrči poligone navznoter</translation>
    </message>
    <message>
        <source>point</source>
        <translation>točka</translation>
    </message>
    <message>
        <source>line</source>
        <translation>črta</translation>
    </message>
    <message>
        <source>non-polygon</source>
        <translation>ne-poligon</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive only when centroids are enabled. Negative buffers cannot be applied to points)</source>
        <translation>Vrednost medpomnilnika v metrih (samo pozitivna, ko so centroidi omogočeni. Negativnih medpomnilnikov ni mogoče uporabiti za točke)</translation>
    </message>
    <message>
        <source>Mode batch</source>
        <translation>Paketni način</translation>
    </message>
    <message>
        <source>Number of segments for buffer precision</source>
        <translation>Število segmentov za natančnost medpomnilnika</translation>
    </message>
    <message>
        <source>Centroids</source>
        <translation>Centroidi</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for distant layers (faster for complex polygons like buildings)</source>
        <translation>Uporabi centroide namesto polnih geometrij za oddaljene sloje (hitrejše za kompleksne poligone, kot so zgradbe)</translation>
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
        <translation>ENOJNI IZBOR</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>MNOŽIČNI IZBOR</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>PRILAGOJENI IZBOR</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>FILTRIRANJE</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>IZVAŽANJE</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>KONFIGURACIJA</translation>
    </message>
    <message>
        <source>Identify feature - Display feature attributes</source>
        <translation>Identificiraj element - Prikaži atribute elementa</translation>
    </message>
    <message>
        <source>Zoom to feature - Center the map on the selected feature</source>
        <translation>Povečaj na element - Centriraj zemljevid na izbrani element</translation>
    </message>
    <message>
        <source>Enable selection - Select features on map</source>
        <translation>Omogoči izbor - Izberi elemente na zemljevidu</translation>
    </message>
    <message>
        <source>Enable tracking - Follow the selected feature on the map</source>
        <translation>Omogoči sledenje - Sledi izbranemu elementu na zemljevidu</translation>
    </message>
    <message>
        <source>Link widgets - Synchronize selection between widgets</source>
        <translation>Poveži gradnike - Sinhroniziraj izbor med gradniki</translation>
    </message>
    <message>
        <source>Reset layer properties - Restore default layer settings</source>
        <translation>Ponastavi lastnosti sloja - Obnovi privzete nastavitve sloja</translation>
    </message>
    <message>
        <source>Auto-sync with current layer - Automatically update when layer changes</source>
        <translation>Samodejna sinhronizacija s trenutnim slojem - Samodejno posodobi ob spremembi sloja</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>Omogoči večslojno filtriranje - Uporabi filter na več slojih hkrati</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>Omogoči aditivno filtriranje - Združi več filtrov na trenutnem sloju</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>Omogoči prostorsko filtriranje - Filtriraj elemente z uporabo geometrijskih razmerij</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>Omogoči medpomnilnik - Dodaj območje medpomnilnika okoli izbranih elementov</translation>
    </message>
    <message>
        <source>Buffer type - Select the buffer calculation method</source>
        <translation>Vrsta medpomnilnika - Izberi metodo izračuna medpomnilnika</translation>
    </message>
    <message>
        <source>Current layer - Select the layer to filter</source>
        <translation>Trenutni sloj - Izberi sloj za filtriranje</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>Logical operator for combining filters on the source layer</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on other layers</source>
        <translation>Logical operator for combining filters on other layers</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>Select geometric predicate(s) for spatial filtering</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>Buffer distance in meters</translation>
    </message>
    <message>
        <source>Buffer type - Define how the buffer is calculated</source>
        <translation>Buffer type - Define how the buffer is calculated</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>Select layers to export</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>Configure output projection</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>Export layer styles (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>Select output format</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>Configure output location and filename</translation>
    </message>
    <message>
        <source>Enable ZIP compression - Create a compressed archive of exported files</source>
        <translation>Enable ZIP compression - Create a compressed archive of exported files</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>Select CRS for export</translation>
    </message>
    <message>
        <source>Style format - Select QML or SLD format</source>
        <translation>Style format - Select QML or SLD format</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>Output file format</translation>
    </message>
    <message>
        <source>Output folder name - Enter the name of the export folder</source>
        <translation>Output folder name - Enter the name of the export folder</translation>
    </message>
    <message>
        <source>Enter folder name...</source>
        <translation>Enter folder name...</translation>
    </message>
    <message>
        <source>Batch mode - Export each layer to a separate folder</source>
        <translation>Batch mode - Export each layer to a separate folder</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>Paketni način</translation>
    </message>
    <message>
        <source>ZIP filename - Enter the name for the compressed archive</source>
        <translation>ZIP filename - Enter the name for the compressed archive</translation>
    </message>
    <message>
        <source>Enter ZIP filename...</source>
        <translation>Enter ZIP filename...</translation>
    </message>
    <message>
        <source>Batch mode - Create a separate ZIP for each layer</source>
        <translation>Batch mode - Create a separate ZIP for each layer</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>Apply Filter - Execute the current filter on selected layers</translation>
    </message>
    <message>
        <source>Apply Filter</source>
        <translation>Uporabi filter</translation>
    </message>
    <message>
        <source>Apply the current filter expression to filter features on the selected layer(s)</source>
        <translation>Apply the current filter expression to filter features on the selected layer(s)</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>Undo Filter - Restore the previous filter state</translation>
    </message>
    <message>
        <source>Undo Filter</source>
        <translation>Razveljavi filter</translation>
    </message>
    <message>
        <source>Undo the last filter operation and restore the previous state</source>
        <translation>Undo the last filter operation and restore the previous state</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>Redo Filter - Reapply the previously undone filter</translation>
    </message>
    <message>
        <source>Redo Filter</source>
        <translation>Uveljavi filter</translation>
    </message>
    <message>
        <source>Redo the previously undone filter operation</source>
        <translation>Redo the previously undone filter operation</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>Clear All Filters - Remove all filters from all layers</translation>
    </message>
    <message>
        <source>Clear All Filters</source>
        <translation>Počisti vse filtre</translation>
    </message>
    <message>
        <source>Remove all active filters from all layers in the project</source>
        <translation>Remove all active filters from all layers in the project</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>Export - Save filtered layers to the specified location</translation>
    </message>
    <message>
        <source>Export</source>
        <translation>Izvozi</translation>
    </message>
    <message>
        <source>Export the filtered layers to the configured output location and format</source>
        <translation>Export the filtered layers to the configured output location and format</translation>
    </message>
    <message>
        <source>About FilterMate - Display plugin information and help</source>
        <translation>About FilterMate - Display plugin information and help</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>IN</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>IN NE</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>ALI</translation>
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
        <translation>Večslojno filtriranje</translation>
    </message>
    <message>
        <source>Additive filtering for the selected layer</source>
        <translation>Aditivno filtriranje za izbrani sloj</translation>
    </message>
    <message>
        <source>Geospatial filtering</source>
        <translation>Geoprostorsko filtriranje</translation>
    </message>
    <message>
        <source>Buffer</source>
        <translation>Medpomnilnik</translation>
    </message>
    <message>
        <source>Expression layer</source>
        <translation>Sloj izraza</translation>
    </message>
    <message>
        <source>Geometric predicate</source>
        <translation>Geometrični predikat</translation>
    </message>
    <message>
        <source>Value in meters</source>
        <translation>Vrednost v metrih</translation>
    </message>
    <message>
        <source>Output format</source>
        <translation>Izhodni format</translation>
    </message>
    <message>
        <source>Filter</source>
        <translation>Filter</translation>
    </message>
    <message>
        <source>Reset</source>
        <translation>Ponastavi</translation>
    </message>
    <message>
        <source>Layers to export</source>
        <translation>Sloji za izvoz</translation>
    </message>
    <message>
        <source>Layers projection</source>
        <translation>Projekcija slojev</translation>
    </message>
    <message>
        <source>Save styles</source>
        <translation>Shrani sloge</translation>
    </message>
    <message>
        <source>Datatype export</source>
        <translation>Izvoz podatkovnega tipa</translation>
    </message>
    <message>
        <source>Name of file/directory</source>
        <translation>Ime datoteke/mape</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidget</name>
    <message>
        <source>Reload the plugin to apply layout changes (action bar position)</source>
        <translation>Reload the plugin to apply layout changes (action bar position)</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>Ponovno naloži vtičnik</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>Do you want to reload FilterMate to apply all configuration changes?</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>Current layer: {name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>Noben sloj ni izbran</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>Selected layers:</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>Več slojev izbranih</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>Nobeni sloji niso izbrani</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>Expression:</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>Noben izraz ni definiran</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>Display expression: {expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>Feature ID: {id}</translation>
    </message>
    <message>
        <source>Current layer: {0}</source>
        <translation>Current layer: {0}</translation>
    </message>
    <message>
        <source>Selected layers:
{0}</source>
        <translation>Selected layers:
{0}</translation>
    </message>
    <message>
        <source>Expression:
{0}</source>
        <translation>Expression:
{0}</translation>
    </message>
    <message>
        <source>Expression: {0}</source>
        <translation>Expression: {0}</translation>
    </message>
    <message>
        <source>Display expression: {0}</source>
        <translation>Display expression: {0}</translation>
    </message>
    <message>
        <source>Feature ID: {0}
First attribute: {1}</source>
        <translation>Feature ID: {0}
First attribute: {1}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>Starting filter on {count} layer(s)</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>Removing filters from {count} layer(s)</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>Resetting {count} layer(s)</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>Exporting {count} layer(s)</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>Successfully filtered {count} layer(s)</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>Successfully removed filters from {count} layer(s)</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>Successfully reset {count} layer(s)</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>Successfully exported {count} layer(s)</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>PostgreSQL priporočen za boljšo zmogljivost.</translation>
    </message>
</context>
<context>
    <name>OptimizationDialogs</name>
    <message>
        <source>FilterMate - Optimizations</source>
        <translation>FilterMate - Optimizacije</translation>
    </message>
    <message>
        <source>Optimizations for:</source>
        <translation>Optimizacije za:</translation>
    </message>
    <message>
        <source>features</source>
        <translation>objektov</translation>
    </message>
    <message>
        <source>Estimated speedup:</source>
        <translation>Ocenjena pospešitev:</translation>
    </message>
    <message>
        <source>faster</source>
        <translation>hitreje</translation>
    </message>
    <message>
        <source>Use centroids instead of full geometries for large datasets</source>
        <translation>Uporabi centroide namesto polnih geometrij za velike nabore podatkov</translation>
    </message>
    <message>
        <source>Use centroids</source>
        <translation>Uporabi centroide</translation>
    </message>
    <message>
        <source>Use centroids for distant layers</source>
        <translation>Uporabi centroide za oddaljene sloje</translation>
    </message>
    <message>
        <source>Enable buffer type</source>
        <translation>Omogoči tip medpomnilnika</translation>
    </message>
    <message>
        <source>Simplify complex geometries to reduce processing time</source>
        <translation>Poenostavi kompleksne geometrije za zmanjšanje časa obdelave</translation>
    </message>
    <message>
        <source>Simplify geometries</source>
        <translation>Poenostavi geometrije</translation>
    </message>
    <message>
        <source>Filter by bounding box first to eliminate distant features quickly</source>
        <translation>Najprej filtriraj po omejevalnem okvirju za hitro odstranitev oddaljenih objektov</translation>
    </message>
    <message>
        <source>BBox pre-filtering</source>
        <translation>Predhodno filtriranje BBox</translation>
    </message>
    <message>
        <source>Evaluate attribute conditions before expensive spatial operations</source>
        <translation>Oceni atributne pogoje pred dragimi prostorskimi operacijami</translation>
    </message>
    <message>
        <source>Attribute-first strategy</source>
        <translation>Strategija atribut-najprej</translation>
    </message>
    <message>
        <source>Apply for current session only</source>
        <translation>Uporabi samo za trenutno sejo</translation>
    </message>
    <message>
        <source>Remember for this session</source>
        <translation>Zapomni za to sejo</translation>
    </message>
    <message>
        <source>Skip without applying</source>
        <translation>Preskoči brez uporabe</translation>
    </message>
    <message>
        <source>Skip</source>
        <translation>Preskoči</translation>
    </message>
    <message>
        <source>Apply selected optimizations</source>
        <translation>Uporabi izbrane optimizacije</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>Uporabi</translation>
    </message>
    <message>
        <source>Optimization Settings</source>
        <translation>Nastavitve optimizacije</translation>
    </message>
    <message>
        <source>Enable automatic optimizations</source>
        <translation>Omogoči samodejne optimizacije</translation>
    </message>
    <message>
        <source>Enable optimizations</source>
        <translation>Omogoči optimizacije</translation>
    </message>
    <message>
        <source>Auto-apply recommendations</source>
        <translation>Samodejno uporabi priporočila</translation>
    </message>
    <message>
        <source>Ask before applying</source>
        <translation>Vprašaj pred uporabo</translation>
    </message>
    <message>
        <source>Show optimization dialog</source>
        <translation>Prikaži pogovorno okno optimizacije</translation>
    </message>
    <message>
        <source>Never apply</source>
        <translation>Nikoli ne uporabi</translation>
    </message>
    <message>
        <source>No optimizations</source>
        <translation>Brez optimizacij</translation>
    </message>
    <message>
        <source>Simplify before buffer</source>
        <translation>Poenostavi pred medpomnilnikom</translation>
    </message>
    <message>
        <source>Reduce buffer segments</source>
        <translation>Zmanjšaj segmente medpomnilnika</translation>
    </message>
</context>
<context>
    <name>BackendOptimizationWidget</name>
    <message>
        <source>Quick Setup</source>
        <translation>Hitra nastavitev</translation>
    </message>
    <message>
        <source>Choose a profile or customize settings below</source>
        <translation>Izberite profil ali prilagodite nastavitve spodaj</translation>
    </message>
    <message>
        <source>Smart Recommendations</source>
        <translation>Pametna priporočila</translation>
    </message>
    <message>
        <source>Balanced Profile</source>
        <translation>Uravnotežen profil</translation>
    </message>
    <message>
        <source>Maximum Performance</source>
        <translation>Maksimalna zmogljivost</translation>
    </message>
    <message>
        <source>Minimal Resources</source>
        <translation>Minimalni viri</translation>
    </message>
    <message>
        <source>PostgreSQL/PostGIS Optimizations</source>
        <translation>Optimizacije PostgreSQL/PostGIS</translation>
    </message>
    <message>
        <source>Materialized Views</source>
        <translation>Materializirani pogledi</translation>
    </message>
    <message>
        <source>Create temporary materialized views for complex filters</source>
        <translation>Ustvari začasne materializirane poglede za kompleksne filtre</translation>
    </message>
    <message>
        <source>Two-Phase Filtering</source>
        <translation>Dvofazno filtriranje</translation>
    </message>
    <message>
        <source>Use bounding box pre-filtering before precise geometry tests</source>
        <translation>Uporabi predfiltriranje z omejitvenim okvirjem pred natančnimi geometrijskimi testi</translation>
    </message>
    <message>
        <source>Progressive Loading</source>
        <translation>Progresivno nalaganje</translation>
    </message>
    <message>
        <source>Load data in chunks for very large datasets</source>
        <translation>Naloži podatke v kosih za zelo velike nabore podatkov</translation>
    </message>
    <message>
        <source>Chunk Size</source>
        <translation>Velikost kosa</translation>
    </message>
    <message>
        <source>Server-Side Simplification</source>
        <translation>Poenostavitev na strežniku</translation>
    </message>
    <message>
        <source>Simplify geometries on server for display purposes</source>
        <translation>Poenostavi geometrije na strežniku za namene prikaza</translation>
    </message>
    <message>
        <source>Simplification Tolerance</source>
        <translation>Toleranca poenostavitve</translation>
    </message>
    <message>
        <source>Parallel Query Execution</source>
        <translation>Vzporedno izvajanje poizvedb</translation>
    </message>
    <message>
        <source>Execute independent queries in parallel</source>
        <translation>Izvedi neodvisne poizvedbe vzporedno</translation>
    </message>
    <message>
        <source>Expression Caching</source>
        <translation>Predpomnjenje izrazov</translation>
    </message>
    <message>
        <source>Cache compiled expressions for reuse</source>
        <translation>Predpomni prevedene izraze za ponovno uporabo</translation>
    </message>
    <message>
        <source>Spatialite/GeoPackage Optimizations</source>
        <translation>Optimizacije Spatialite/GeoPackage</translation>
    </message>
    <message>
        <source>R-tree Temp Tables</source>
        <translation>Začasne tabele R-tree</translation>
    </message>
    <message>
        <source>Create temporary tables with R-tree indexes</source>
        <translation>Ustvari začasne tabele z indeksi R-tree</translation>
    </message>
    <message>
        <source>BBox Pre-filtering</source>
        <translation>Predfiltriranje BBox</translation>
    </message>
    <message>
        <source>Use bounding box filtering before precise tests</source>
        <translation>Uporabi filtriranje z omejitvenim okvirjem pred natančnimi testi</translation>
    </message>
    <message>
        <source>Memory-Mapped I/O</source>
        <translation>Pomnilniško preslikani V/I</translation>
    </message>
    <message>
        <source>Use memory-mapped I/O for file access</source>
        <translation>Uporabi pomnilniško preslikan V/I za dostop do datotek</translation>
    </message>
    <message>
        <source>Batch Processing</source>
        <translation>Serijska obdelava</translation>
    </message>
    <message>
        <source>Process multiple operations in batches</source>
        <translation>Obdelaj več operacij v serijah</translation>
    </message>
    <message>
        <source>Batch Size</source>
        <translation>Velikost serije</translation>
    </message>
    <message>
        <source>OGR/Memory Optimizations</source>
        <translation>Optimizacije OGR/Pomnilnik</translation>
    </message>
    <message>
        <source>Automatic Spatial Index</source>
        <translation>Samodejni prostorski indeks</translation>
    </message>
    <message>
        <source>Create temporary spatial indexes automatically</source>
        <translation>Samodejno ustvari začasne prostorske indekse</translation>
    </message>
    <message>
        <source>Progressive Chunking</source>
        <translation>Progresivno razdeljevanje</translation>
    </message>
    <message>
        <source>Process large files in progressive chunks</source>
        <translation>Obdelaj velike datoteke v progresivnih kosih</translation>
    </message>
    <message>
        <source>Memory Feature Caching</source>
        <translation>Predpomnjenje značilnosti v pomnilniku</translation>
    </message>
    <message>
        <source>Cache features in memory for faster access</source>
        <translation>Predpomni značilnosti v pomnilniku za hitrejši dostop</translation>
    </message>
    <message>
        <source>Cache Size (features)</source>
        <translation>Velikost predpomnilnika (značilnosti)</translation>
    </message>
    <message>
        <source>Geometry Simplification</source>
        <translation>Poenostavitev geometrije</translation>
    </message>
    <message>
        <source>Simplify complex geometries during processing</source>
        <translation>Poenostavi kompleksne geometrije med obdelavo</translation>
    </message>
    <message>
        <source>Global Optimizations</source>
        <translation>Globalne optimizacije</translation>
    </message>
    <message>
        <source>Auto-Optimization</source>
        <translation>Samodejna optimizacija</translation>
    </message>
    <message>
        <source>Automatically optimize based on data analysis</source>
        <translation>Samodejno optimiziraj na podlagi analize podatkov</translation>
    </message>
    <message>
        <source>Auto-Centroid</source>
        <translation>Samodejni centroid</translation>
    </message>
    <message>
        <source>Automatically center view on filter results</source>
        <translation>Samodejno centriraj pogled na rezultate filtra</translation>
    </message>
    <message>
        <source>Parallel Layer Filtering</source>
        <translation>Vzporedno filtriranje slojev</translation>
    </message>
    <message>
        <source>Filter multiple layers simultaneously</source>
        <translation>Filtriraj več slojev hkrati</translation>
    </message>
    <message>
        <source>Smart Expression Parsing</source>
        <translation>Pametno razčlenjevanje izrazov</translation>
    </message>
    <message>
        <source>Optimize expression parsing for complex queries</source>
        <translation>Optimiziraj razčlenjevanje izrazov za kompleksne poizvedbe</translation>
    </message>
    <message>
        <source>Deferred Refresh</source>
        <translation>Odložena osvežitev</translation>
    </message>
    <message>
        <source>Delay map refresh until all filters are applied</source>
        <translation>Odloži osvežitev zemljevida, dokler niso uporabljeni vsi filtri</translation>
    </message>
    <message>
        <source>Verbose Logging</source>
        <translation>Podrobno beleženje</translation>
    </message>
    <message>
        <source>Enable detailed logging for debugging</source>
        <translation>Omogoči podrobno beleženje za odpravljanje napak</translation>
    </message>
    <message>
        <source>Apply</source>
        <translation>Uporabi</translation>
    </message>
    <message>
        <source>Reset to Defaults</source>
        <translation>Ponastavi na privzeto</translation>
    </message>
    <message>
        <source>Settings applied successfully</source>
        <translation>Nastavitve uspešno uporabljene</translation>
    </message>
    <message>
        <source>Settings reset to defaults</source>
        <translation>Nastavitve ponastavljene na privzeto</translation>
    </message>
    <message>
        <source>Profile applied: {}</source>
        <translation>Profil uporabljen: {}</translation>
    </message>
    <message>
        <source>Error applying settings</source>
        <translation>Napaka pri uporabi nastavitev</translation>
    </message>
<message><source>MV Status: Checking...</source><translation type="unfinished">MV Status: Checking...</translation></message><message><source>MV Status: Error</source><translation type="unfinished">MV Status: Error</translation></message><message><source>MV Status: Clean</source><translation type="unfinished">MV Status: Clean</translation></message><message><source>MV Status:</source><translation type="unfinished">MV Status:</translation></message><message><source>active</source><translation type="unfinished">active</translation></message><message><source>No active materialized views</source><translation type="unfinished">No active materialized views</translation></message><message><source>Session:</source><translation type="unfinished">Session:</translation></message><message><source>Other sessions:</source><translation type="unfinished">Other sessions:</translation></message><message><source>🧹 Session</source><translation type="unfinished">🧹 Session</translation></message><message><source>Cleanup MVs from this session</source><translation type="unfinished">Cleanup MVs from this session</translation></message><message><source>🗑️ Orphaned</source><translation type="unfinished">🗑️ Orphaned</translation></message><message><source>Cleanup orphaned MVs (&gt;24h old)</source><translation type="unfinished">Cleanup orphaned MVs (&gt;24h old)</translation></message><message><source>⚠️ All</source><translation type="unfinished">⚠️ All</translation></message><message><source>Cleanup ALL MVs (affects other sessions)</source><translation type="unfinished">Cleanup ALL MVs (affects other sessions)</translation></message><message><source>Confirm Cleanup</source><translation type="unfinished">Confirm Cleanup</translation></message><message><source>Drop ALL materialized views?
This affects other FilterMate sessions!</source><translation type="unfinished">Drop ALL materialized views?
This affects other FilterMate sessions!</translation></message><message><source>Refresh MV status</source><translation type="unfinished">Refresh MV status</translation></message><message><source>Threshold:</source><translation type="unfinished">Threshold:</translation></message><message><source>features</source><translation type="unfinished">features</translation></message><message><source>Auto-cleanup on exit</source><translation type="unfinished">Auto-cleanup on exit</translation></message><message><source>Automatically drop session MVs when plugin unloads</source><translation type="unfinished">Automatically drop session MVs when plugin unloads</translation></message><message><source>Create MVs for datasets larger than this</source><translation type="unfinished">Create MVs for datasets larger than this</translation></message><message><source>faster possible</source><translation type="unfinished">faster possible</translation></message><message><source>Optimizations available</source><translation type="unfinished">Optimizations available</translation></message><message><source>FilterMate - Apply Optimizations?</source><translation type="unfinished">FilterMate - Apply Optimizations?</translation></message><message><source>Skip</source><translation type="unfinished">Skip</translation></message><message><source>✓ Apply</source><translation type="unfinished">✓ Apply</translation></message><message><source>Don't ask for this session</source><translation type="unfinished">Don't ask for this session</translation></message><message><source>Centroids</source><translation type="unfinished">Centroids</translation></message><message><source>Simplify</source><translation type="unfinished">Simplify</translation></message><message><source>Pre-simplify</source><translation type="unfinished">Pre-simplify</translation></message><message><source>Fewer segments</source><translation type="unfinished">Fewer segments</translation></message><message><source>Flat buffer</source><translation type="unfinished">Flat buffer</translation></message><message><source>BBox filter</source><translation type="unfinished">BBox filter</translation></message><message><source>Attr-first</source><translation type="unfinished">Attr-first</translation></message><message><source>PostgreSQL not available</source><translation type="unfinished">PostgreSQL not available</translation></message><message><source>No connection</source><translation type="unfinished">No connection</translation></message><message><source>Auto-zoom when feature changes</source><translation type="unfinished">Auto-zoom when feature changes</translation></message><message><source>Backend optimization settings saved</source><translation type="unfinished">Backend optimization settings saved</translation></message><message><source>Backend optimizations configured</source><translation type="unfinished">Backend optimizations configured</translation></message><message><source>Expression Evaluation</source><translation type="unfinished">Expression Evaluation</translation></message><message><source>Identify selected feature</source><translation type="unfinished">Identify selected feature</translation></message><message><source>Layer properties reset to defaults</source><translation type="unfinished">Layer properties reset to defaults</translation></message><message><source>Link exploring widgets together</source><translation type="unfinished">Link exploring widgets together</translation></message><message><source>Optimization settings saved</source><translation type="unfinished">Optimization settings saved</translation></message><message><source>Reset all layer exploring properties</source><translation type="unfinished">Reset all layer exploring properties</translation></message><message><source>Toggle feature selection on map</source><translation type="unfinished">Toggle feature selection on map</translation></message><message><source>Use centroids instead of full geometries for distant layers (faster for complex polygons)</source><translation type="unfinished">Use centroids instead of full geometries for distant layers (faster for complex polygons)</translation></message><message><source>Use centroids instead of full geometries for source layer (faster for complex polygons)</source><translation type="unfinished">Use centroids instead of full geometries for source layer (faster for complex polygons)</translation></message><message><source>Zoom to selected feature</source><translation type="unfinished">Zoom to selected feature</translation></message></context>
</TS>