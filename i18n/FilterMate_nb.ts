<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="nb_NO" sourcelanguage="en_US">
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
        <translation>Åpne FilterMate-panelet</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Tilbakestill konfigurasjon og database</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>Tilbakestill standardkonfigurasjonen og slett SQLite-databasen</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>Tilbakestill konfigurasjon</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>Er du sikker på at du vil tilbakestille til standardkonfigurasjonen?

Dette vil:
- Tilbakestille alle FilterMate-innstillinger
- Slette alle filterhistorikk-databaser</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>Konfigurasjonen ble tilbakestilt.</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>Standard konfigurasjonsfil ikke funnet.</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>Database slettet: {filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>Kan ikke slette {filename}: {error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>Omstart nødvendig</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>Konfigurasjonen har blitt tilbakestilt.

Start QGIS på nytt for å bruke alle endringene.</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>Feil under tilbakestilling: {error}</translation>
    </message>
    <message>
        <source>Obsolete configuration detected</source>
        <translation>Utdatert konfigurasjon oppdaget</translation>
    </message>
    <message>
        <source>unknown version</source>
        <translation>ukjent versjon</translation>
    </message>
    <message>
        <source>Corrupted configuration detected</source>
        <translation>Skadet konfigurasjon oppdaget</translation>
    </message>
    <message>
        <source>Configuration not reset. Some features may not work correctly.</source>
        <translation>Konfigurasjon ikke tilbakestilt. Noen funksjoner fungerer kanskje ikke riktig.</translation>
    </message>
    <message>
        <source>Configuration created with default values</source>
        <translation>Konfigurasjon opprettet med standardverdier</translation>
    </message>
    <message>
        <source>Corrupted configuration reset. Default settings have been restored.</source>
        <translation>Skadet konfigurasjon tilbakestilt. Standardinnstillinger er gjenopprettet.</translation>
    </message>
    <message>
        <source>Obsolete configuration reset. Default settings have been restored.</source>
        <translation>Utdatert konfigurasjon tilbakestilt. Standardinnstillinger er gjenopprettet.</translation>
    </message>
    <message>
        <source>Configuration updated to latest version</source>
        <translation>Konfigurasjon oppdatert til nyeste versjon</translation>
    </message>
    <message>
        <source>Geometry validation setting</source>
        <translation>Geometrivalideringsinnstilling</translation>
    </message>
    <message>
        <source>Invalid geometry filtering disabled successfully.</source>
        <translation>Filtrering av ugyldige geometrier er deaktivert.</translation>
    </message>
    <message>
        <source>Invalid geometry filtering not modified. Some features may be excluded from exports.</source>
        <translation>Filtrering av ugyldige geometrier ikke endret. Noen objekter kan bli ekskludert fra eksport.</translation>
    </message>
    <message>
        <source>Buffer value in meters (positive=expand, negative=shrink polygons)</source>
        <translation>Bufferverdi i meter (positiv=utvid, negativ=krymp polygoner)</translation>
    </message>
    <message>
        <source>Negative buffer (erosion): shrinks polygons inward</source>
        <translation>Negativ buffer (erosjon): krymper polygoner innover</translation>
    </message>
    <message>
        <source>point</source>
        <translation>punkt</translation>
    </message>
    <message>
        <source>line</source>
        <translation>linje</translation>
    </message>
    <message>
        <source>non-polygon</source>
        <translation>ikke-polygon</translation>
    </message>
    <message>
        <source>Mode batch</source>
        <translation>Batch-modus</translation>
    </message>
    <message>
        <source>Number of segments for buffer precision</source>
        <translation>Antall segmenter for bufferpresisjon</translation>
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
        <translation>ENKELTVALG</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>FLERVALG</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>TILPASSET VALG</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>FILTRERING</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>EKSPORT</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>KONFIGURASJON</translation>
    </message>
    <message>
        <source>Identify feature - Display feature attributes</source>
        <translation>Identifiser objekt - Vis objektattributter</translation>
    </message>
    <message>
        <source>Zoom to feature - Center the map on the selected feature</source>
        <translation>Zoom til objekt - Sentrer kartet på det valgte objektet</translation>
    </message>
    <message>
        <source>Enable selection - Select features on map</source>
        <translation>Aktiver valg - Velg objekter på kartet</translation>
    </message>
    <message>
        <source>Enable tracking - Follow the selected feature on the map</source>
        <translation>Aktiver sporing - Følg det valgte objektet på kartet</translation>
    </message>
    <message>
        <source>Link widgets - Synchronize selection between widgets</source>
        <translation>Lenk widgets - Synkroniser valg mellom widgets</translation>
    </message>
    <message>
        <source>Reset layer properties - Restore default layer settings</source>
        <translation>Tilbakestill lagegenskaper - Gjenopprett standard laginnstillinger</translation>
    </message>
    <message>
        <source>Auto-sync with current layer - Automatically update when layer changes</source>
        <translation>Auto-synkroniser med gjeldende lag - Oppdater automatisk når laget endres</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>Aktiver flerlagsfiltrering - Bruk filter på flere lag samtidig</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>Aktiver additiv filtrering - Kombiner flere filtre på det gjeldende laget</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>Aktiver romlig filtrering - Filtrer objekter ved hjelp av geometriske relasjoner</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>Aktiver buffer - Legg til en buffersone rundt valgte objekter</translation>
    </message>
    <message>
        <source>Buffer type - Select the buffer calculation method</source>
        <translation>Buffertype - Velg bufferberegningsmetode</translation>
    </message>
    <message>
        <source>Current layer - Select the layer to filter</source>
        <translation>Gjeldende lag - Velg lag å filtrere</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>Logisk operator for å kombinere filtre på kildelaget</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on other layers</source>
        <translation>Logisk operator for å kombinere filtre på andre lag</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>Velg geometriske predikater for romlig filtrering</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>Bufferavstand i meter</translation>
    </message>
    <message>
        <source>Buffer type - Define how the buffer is calculated</source>
        <translation>Buffertype - Definer hvordan bufferen beregnes</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>Velg lag å eksportere</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>Konfigurer output-projeksjon</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>Eksporter lagstiler (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>Velg outputformat</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>Konfigurer output-plassering og filnavn</translation>
    </message>
    <message>
        <source>Enable ZIP compression - Create a compressed archive of exported files</source>
        <translation>Aktiver ZIP-komprimering - Opprett et komprimert arkiv av eksporterte filer</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>Velg koordinatsystem for eksport</translation>
    </message>
    <message>
        <source>Style format - Select QML or SLD format</source>
        <translation>Stilformat - Velg QML eller SLD format</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>Output-filformat</translation>
    </message>
    <message>
        <source>Output folder name - Enter the name of the export folder</source>
        <translation>Output-mappenavn - Skriv inn navnet på eksportmappen</translation>
    </message>
    <message>
        <source>Enter folder name...</source>
        <translation>Skriv inn mappenavn...</translation>
    </message>
    <message>
        <source>Batch mode - Export each layer to a separate folder</source>
        <translation>Batchmodus - Eksporter hvert lag til en separat mappe</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>Batchmodus</translation>
    </message>
    <message>
        <source>ZIP filename - Enter the name for the compressed archive</source>
        <translation>ZIP-filnavn - Skriv inn navnet på det komprimerte arkivet</translation>
    </message>
    <message>
        <source>Enter ZIP filename...</source>
        <translation>Skriv inn ZIP-filnavn...</translation>
    </message>
    <message>
        <source>Batch mode - Create a separate ZIP for each layer</source>
        <translation>Batchmodus - Opprett en separat ZIP for hvert lag</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>Bruk filter - Utfør det gjeldende filteret på valgte lag</translation>
    </message>
    <message>
        <source>Apply Filter</source>
        <translation>Bruk filter</translation>
    </message>
    <message>
        <source>Apply the current filter expression to filter features on the selected layer(s)</source>
        <translation>Bruk det gjeldende filteruttrykket for å filtrere objekter på de valgte lagene</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>Angre filter - Gjenopprett den forrige filtertilstanden</translation>
    </message>
    <message>
        <source>Undo Filter</source>
        <translation>Angre filter</translation>
    </message>
    <message>
        <source>Undo the last filter operation and restore the previous state</source>
        <translation>Angre den siste filteroperasjonen og gjenopprett den forrige tilstanden</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>Gjør om filter - Bruk det tidligere angrede filteret på nytt</translation>
    </message>
    <message>
        <source>Redo Filter</source>
        <translation>Gjør om filter</translation>
    </message>
    <message>
        <source>Redo the previously undone filter operation</source>
        <translation>Gjør om den tidligere angrede filteroperasjonen</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>Fjern alle filtre - Fjern alle filtre fra alle lag</translation>
    </message>
    <message>
        <source>Clear All Filters</source>
        <translation>Fjern alle filtre</translation>
    </message>
    <message>
        <source>Remove all active filters from all layers in the project</source>
        <translation>Fjern alle aktive filtre fra alle lag i prosjektet</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>Eksporter - Lagre filtrerte lag til angitt plassering</translation>
    </message>
    <message>
        <source>Export</source>
        <translation>Eksporter</translation>
    </message>
    <message>
        <source>Export the filtered layers to the configured output location and format</source>
        <translation>Eksporter de filtrerte lagene til den konfigurerte output-plasseringen og formatet</translation>
    </message>
    <message>
        <source>About FilterMate - Display plugin information and help</source>
        <translation>Om FilterMate - Vis plugin-informasjon og hjelp</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>OG</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>OG IKKE</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>ELLER</translation>
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
        <translation>Flerlagsfiltrering</translation>
    </message>
    <message>
        <source>Additive filtering for the selected layer</source>
        <translation>Additiv filtrering for det valgte laget</translation>
    </message>
    <message>
        <source>Geospatial filtering</source>
        <translation>Geospatial filtrering</translation>
    </message>
    <message>
        <source>Buffer</source>
        <translation>Buffer</translation>
    </message>
    <message>
        <source>Expression layer</source>
        <translation>Uttrykkslag</translation>
    </message>
    <message>
        <source>Geometric predicate</source>
        <translation>Geometrisk predikat</translation>
    </message>
    <message>
        <source>Value in meters</source>
        <translation>Verdi i meter</translation>
    </message>
    <message>
        <source>Output format</source>
        <translation>Outputformat</translation>
    </message>
    <message>
        <source>Filter</source>
        <translation>Filter</translation>
    </message>
    <message>
        <source>Reset</source>
        <translation>Tilbakestill</translation>
    </message>
    <message>
        <source>Layers to export</source>
        <translation>Lag å eksportere</translation>
    </message>
    <message>
        <source>Layers projection</source>
        <translation>Lagprojeksjon</translation>
    </message>
    <message>
        <source>Save styles</source>
        <translation>Lagre stiler</translation>
    </message>
    <message>
        <source>Datatype export</source>
        <translation>Datatype-eksport</translation>
    </message>
    <message>
        <source>Name of file/directory</source>
        <translation>Navn på fil/mappe</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidget</name>
    <message>
        <source>Reload the plugin to apply layout changes (action bar position)</source>
        <translation>Last inn pluginet på nytt for å bruke layoutendringer (handlingsfeltposisjon)</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>Last inn plugin på nytt</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>Vil du laste inn FilterMate på nytt for å bruke alle konfigurasjonsendringene?</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>Gjeldende lag: {name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>Ingen lag valgt</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>Valgte lag:</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>Flere lag valgt</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>Ingen lag valgt</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>Uttrykk:</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>Ingen uttrykk definert</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>Vis uttrykk: {expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>Objekt-ID: {id}</translation>
    </message>
    <message>
        <source>Current layer: {0}</source>
        <translation>Gjeldende lag: {0}</translation>
    </message>
    <message>
        <source>Selected layers:
{0}</source>
        <translation>Valgte lag:
{0}</translation>
    </message>
    <message>
        <source>Expression:
{0}</source>
        <translation>Uttrykk:
{0}</translation>
    </message>
    <message>
        <source>Expression: {0}</source>
        <translation>Uttrykk: {0}</translation>
    </message>
    <message>
        <source>Display expression: {0}</source>
        <translation>Vis uttrykk: {0}</translation>
    </message>
    <message>
        <source>Feature ID: {0}
First attribute: {1}</source>
        <translation>Objekt-ID: {0}
Første attributt: {1}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>Starter filtrering på {count} lag</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>Fjerner filtre fra {count} lag</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>Tilbakestiller {count} lag</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>Eksporterer {count} lag</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>{count} lag ble filtrert</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>Filtre ble fjernet fra {count} lag</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>{count} lag ble tilbakestilt</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>{count} lag ble eksportert</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>Stort datasett ({count} objekter) uten PostgreSQL. Ytelsen kan være redusert.</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>PostgreSQL anbefales for bedre ytelse.</translation>
    </message>
</context>
</TS>
