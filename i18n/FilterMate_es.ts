<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="es_ES" sourcelanguage="en_US">
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
        <translation>Abrir panel FilterMate</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Restablecer configuración y base de datos</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>Restablecer la configuración predeterminada y eliminar la base de datos SQLite</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>Restablecer Configuración</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>¿Está seguro de que desea restablecer la configuración predeterminada?

Esto hará:
- Restablecer todas las configuraciones de FilterMate
- Eliminar todas las bases de datos del historial de filtros</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>Configuración restablecida correctamente.</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>Archivo de configuración predeterminado no encontrado.</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>Base de datos eliminada: {filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>No se puede eliminar {filename}: {error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>Se requiere reinicio</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>La configuración ha sido restablecida.

Por favor, reinicie QGIS para aplicar todos los cambios.</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>Error durante el restablecimiento: {error}</translation>
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
        <translation>SELECCIÓN SIMPLE</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>SELECCIÓN MÚLTIPLE</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>SELECCIÓN PERSONALIZADA</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>FILTRADO</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>EXPORTACIÓN</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>CONFIGURACIÓN</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>Activar filtrado multicapa - Aplicar filtro a varias capas simultáneamente</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>Activar filtrado aditivo - Combinar múltiples filtros en la capa actual</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>Activar filtrado espacial - Filtrar entidades usando relaciones geométricas</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>Activar búfer - Añadir una zona de búfer alrededor de las entidades seleccionadas</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>Operador lógico para combinar filtros en la capa de origen</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>Seleccionar predicado(s) geométrico(s) para filtrado espacial</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>Distancia del búfer en metros</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>Seleccionar capas para exportar</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>Configurar proyección de salida</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>Exportar estilos de capa (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>Seleccionar formato de salida</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>Configurar ubicación de salida y nombre de archivo</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>Seleccionar SRC para exportación</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>Formato del archivo de salida</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>Modo por lotes</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>Aplicar Filtro - Ejecutar el filtro actual en las capas seleccionadas</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>Deshacer Filtro - Restaurar el estado de filtro anterior</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>Rehacer Filtro - Reaplicar el filtro anteriormente deshecho</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>Borrar Todos los Filtros - Eliminar todos los filtros de todas las capas</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>Exportar - Guardar capas filtradas en la ubicación especificada</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>Y</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>Y NO</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>O</translation>
    </message>
    <message>
        <source>QML</source>
        <translation>QML</translation>
    </message>
    <message>
        <source>SLD</source>
        <translation>SLD</translation>
    </message>
</context>
<context>
    <name>FilterMateDockWidget</name>
    <message>
        <source>Reload the plugin to apply layout changes (action bar position)</source>
        <translation>Recargar el plugin para aplicar cambios de diseño (posición de la barra de acciones)</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>Recargar Plugin</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>¿Desea recargar FilterMate para aplicar todos los cambios de configuración?</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>Capa actual: {name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>Ninguna capa seleccionada</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>Capas seleccionadas:</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>Varias capas seleccionadas</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>Ninguna capa seleccionada</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>Expresión:</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>Ninguna expresión definida</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>Expresión de visualización: {expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>ID de la entidad: {id}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>Iniciando filtrado en {count} capa(s)</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>Eliminando filtros de {count} capa(s)</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>Restableciendo {count} capa(s)</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>Exportando {count} capa(s)</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>{count} capa(s) filtrada(s) correctamente</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>Filtros eliminados de {count} capa(s) correctamente</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>{count} capa(s) restablecida(s) correctamente</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>{count} capa(s) exportada(s) correctamente</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>Conjunto de datos grande ({count} entidades) sin PostgreSQL. El rendimiento puede reducirse.</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>PostgreSQL recomendado para mejor rendimiento.</translation>
    </message>
</context>
</TS>
