<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="pt_BR" sourcelanguage="en_US">
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
        <translation>Abrir painel FilterMate</translation>
    </message>
    <message>
        <source>Reset configuration and database</source>
        <translation>Redefinir configuração e banco de dados</translation>
    </message>
    <message>
        <source>Reset the default configuration and delete the SQLite database</source>
        <translation>Redefinir a configuração padrão e excluir o banco de dados SQLite</translation>
    </message>
    <message>
        <source>Reset Configuration</source>
        <translation>Redefinir Configuração</translation>
    </message>
    <message>
        <source>Are you sure you want to reset to the default configuration?

This will:
- Reset all FilterMate settings
- Delete all filter history databases</source>
        <translation>Tem certeza de que deseja redefinir para a configuração padrão?

Isso irá:
- Redefinir todas as configurações do FilterMate
- Excluir todos os bancos de dados de histórico de filtros</translation>
    </message>
    <message>
        <source>Configuration reset successfully.</source>
        <translation>Configuração redefinida com sucesso.</translation>
    </message>
    <message>
        <source>Default configuration file not found.</source>
        <translation>Arquivo de configuração padrão não encontrado.</translation>
    </message>
    <message>
        <source>Database deleted: {filename}</source>
        <translation>Banco de dados excluído: {filename}</translation>
    </message>
    <message>
        <source>Unable to delete {filename}: {error}</source>
        <translation>Não foi possível excluir {filename}: {error}</translation>
    </message>
    <message>
        <source>Restart required</source>
        <translation>Reinicialização necessária</translation>
    </message>
    <message>
        <source>The configuration has been reset.

Please restart QGIS to apply all changes.</source>
        <translation>A configuração foi redefinida.

Por favor, reinicie o QGIS para aplicar todas as alterações.</translation>
    </message>
    <message>
        <source>Error during reset: {error}</source>
        <translation>Erro durante a redefinição: {error}</translation>
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
        <translation>SELEÇÃO SIMPLES</translation>
    </message>
    <message>
        <source>MULTIPLE SELECTION</source>
        <translation>SELEÇÃO MÚLTIPLA</translation>
    </message>
    <message>
        <source>CUSTOM SELECTION</source>
        <translation>SELEÇÃO PERSONALIZADA</translation>
    </message>
    <message>
        <source>FILTERING</source>
        <translation>FILTRAGEM</translation>
    </message>
    <message>
        <source>EXPORTING</source>
        <translation>EXPORTAÇÃO</translation>
    </message>
    <message>
        <source>CONFIGURATION</source>
        <translation>CONFIGURAÇÃO</translation>
    </message>
    <message>
        <source>Enable multi-layer filtering - Apply filter to multiple layers simultaneously</source>
        <translation>Ativar filtragem multicamada - Aplicar filtro a várias camadas simultaneamente</translation>
    </message>
    <message>
        <source>Enable additive filtering - Combine multiple filters on the current layer</source>
        <translation>Ativar filtragem aditiva - Combinar vários filtros na camada atual</translation>
    </message>
    <message>
        <source>Enable spatial filtering - Filter features using geometric relationships</source>
        <translation>Ativar filtragem espacial - Filtrar feições usando relações geométricas</translation>
    </message>
    <message>
        <source>Enable buffer - Add a buffer zone around selected features</source>
        <translation>Ativar buffer - Adicionar uma zona de buffer ao redor das feições selecionadas</translation>
    </message>
    <message>
        <source>Logical operator for combining filters on the source layer</source>
        <translation>Operador lógico para combinar filtros na camada de origem</translation>
    </message>
    <message>
        <source>Select geometric predicate(s) for spatial filtering</source>
        <translation>Selecionar predicado(s) geométrico(s) para filtragem espacial</translation>
    </message>
    <message>
        <source>Buffer distance in meters</source>
        <translation>Distância do buffer em metros</translation>
    </message>
    <message>
        <source>Select layers to export</source>
        <translation>Selecionar camadas para exportar</translation>
    </message>
    <message>
        <source>Configure output projection</source>
        <translation>Configurar projeção de saída</translation>
    </message>
    <message>
        <source>Export layer styles (QML/SLD)</source>
        <translation>Exportar estilos de camada (QML/SLD)</translation>
    </message>
    <message>
        <source>Select output format</source>
        <translation>Selecionar formato de saída</translation>
    </message>
    <message>
        <source>Configure output location and filename</source>
        <translation>Configurar local de saída e nome do arquivo</translation>
    </message>
    <message>
        <source>Select CRS for export</source>
        <translation>Selecionar SRC para exportação</translation>
    </message>
    <message>
        <source>Output file format</source>
        <translation>Formato do arquivo de saída</translation>
    </message>
    <message>
        <source>Batch mode</source>
        <translation>Modo em lote</translation>
    </message>
    <message>
        <source>Apply Filter - Execute the current filter on selected layers</source>
        <translation>Aplicar Filtro - Executar o filtro atual nas camadas selecionadas</translation>
    </message>
    <message>
        <source>Undo Filter - Restore the previous filter state</source>
        <translation>Desfazer Filtro - Restaurar o estado anterior do filtro</translation>
    </message>
    <message>
        <source>Redo Filter - Reapply the previously undone filter</source>
        <translation>Refazer Filtro - Reaplicar o filtro anteriormente desfeito</translation>
    </message>
    <message>
        <source>Clear All Filters - Remove all filters from all layers</source>
        <translation>Limpar Todos os Filtros - Remover todos os filtros de todas as camadas</translation>
    </message>
    <message>
        <source>Export - Save filtered layers to the specified location</source>
        <translation>Exportar - Salvar camadas filtradas no local especificado</translation>
    </message>
    <message>
        <source>AND</source>
        <translation>E</translation>
    </message>
    <message>
        <source>AND NOT</source>
        <translation>E NÃO</translation>
    </message>
    <message>
        <source>OR</source>
        <translation>OU</translation>
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
        <translation>Recarregar o plugin para aplicar alterações de layout (posição da barra de ações)</translation>
    </message>
    <message>
        <source>Reload Plugin</source>
        <translation>Recarregar Plugin</translation>
    </message>
    <message>
        <source>Do you want to reload FilterMate to apply all configuration changes?</source>
        <translation>Deseja recarregar o FilterMate para aplicar todas as alterações de configuração?</translation>
    </message>
    <message>
        <source>Current layer: {name}</source>
        <translation>Camada atual: {name}</translation>
    </message>
    <message>
        <source>No layer selected</source>
        <translation>Nenhuma camada selecionada</translation>
    </message>
    <message>
        <source>Selected layers:</source>
        <translation>Camadas selecionadas:</translation>
    </message>
    <message>
        <source>Multiple layers selected</source>
        <translation>Várias camadas selecionadas</translation>
    </message>
    <message>
        <source>No layers selected</source>
        <translation>Nenhuma camada selecionada</translation>
    </message>
    <message>
        <source>Expression:</source>
        <translation>Expressão:</translation>
    </message>
    <message>
        <source>No expression defined</source>
        <translation>Nenhuma expressão definida</translation>
    </message>
    <message>
        <source>Display expression: {expr}</source>
        <translation>Expressão de exibição: {expr}</translation>
    </message>
    <message>
        <source>Feature ID: {id}</source>
        <translation>ID da feição: {id}</translation>
    </message>
</context>
<context>
    <name>FeedbackUtils</name>
    <message>
        <source>Starting filter on {count} layer(s)</source>
        <translation>Iniciando filtragem em {count} camada(s)</translation>
    </message>
    <message>
        <source>Removing filters from {count} layer(s)</source>
        <translation>Removendo filtros de {count} camada(s)</translation>
    </message>
    <message>
        <source>Resetting {count} layer(s)</source>
        <translation>Redefinindo {count} camada(s)</translation>
    </message>
    <message>
        <source>Exporting {count} layer(s)</source>
        <translation>Exportando {count} camada(s)</translation>
    </message>
    <message>
        <source>Successfully filtered {count} layer(s)</source>
        <translation>{count} camada(s) filtrada(s) com sucesso</translation>
    </message>
    <message>
        <source>Successfully removed filters from {count} layer(s)</source>
        <translation>Filtros removidos de {count} camada(s) com sucesso</translation>
    </message>
    <message>
        <source>Successfully reset {count} layer(s)</source>
        <translation>{count} camada(s) redefinida(s) com sucesso</translation>
    </message>
    <message>
        <source>Successfully exported {count} layer(s)</source>
        <translation>{count} camada(s) exportada(s) com sucesso</translation>
    </message>
    <message>
        <source>Large dataset ({count} features) without PostgreSQL. Performance may be reduced.</source>
        <translation>Conjunto de dados grande ({count} feições) sem PostgreSQL. O desempenho pode ser reduzido.</translation>
    </message>
    <message>
        <source>PostgreSQL recommended for better performance.</source>
        <translation>PostgreSQL recomendado para melhor desempenho.</translation>
    </message>
</context>
</TS>
