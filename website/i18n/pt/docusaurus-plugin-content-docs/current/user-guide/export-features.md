---
sidebar_position: 6
---

# Exportar Feições

Exporte camadas (filtradas ou não) para vários formatos usando a aba **EXPORTING**.

## Visão Geral

A aba **EXPORTING** permite exportar camadas do seu projeto QGIS para conjuntos de dados autônomos para:
- **Compartilhar** com colegas ou clientes
- **Analisar** em outros softwares
- **Arquivar** snapshots de dados
- **Publicar** mapas web
- **Relatar** dados tabulares

**Recursos principais**:
- Multi-seleção de camadas para exportar
- Múltiplos formatos de saída (GPKG, Shapefile, GeoJSON, etc.)
- Transformação de SRC (reprojeção)
- Exportação de estilo (QML, SLD, ArcGIS)
- Modo batch (arquivos separados por camada)
- Compressão ZIP para entrega

:::tip Exportando Dados Filtrados
As camadas podem ser exportadas **com ou sem** filtros aplicados. Se você usou a aba FILTERING para criar subconjuntos filtrados, esses filtros são preservados durante a exportação. Para exportar dados não filtrados, remova os filtros primeiro na aba FILTERING.
:::

## Componentes da Aba EXPORTING

### Seleção de Camadas

Selecione quais camadas exportar do seu projeto QGIS:

<img src="/filter_mate/img/ui-exporting-layer-selector.png" alt="ui-exporting-layer-selector" width="300"/>

*Marque uma ou mais camadas para exportar*

**Recursos**:
- **Multi-seleção**: Exporte múltiplas camadas de uma vez
- **Indicadores de geometria**: Ícones visuais para camadas de ponto/linha/polígono
- **Contagem de feições**: Mostra a contagem atual de feições (respeita filtros ativos)
- **Info do backend**: Exibe a fonte de dados (PostgreSQL⚡, Spatialite, OGR)

### Seleção de Formato

Escolha o formato de saída para os dados exportados:

<img src="/filter_mate/img/ui-exporting-format-selector.png" alt="ui-exporting-format-selector" width="300"/>

*Menu suspenso com formatos de exportação disponíveis*


### Formatos Suportados

| Formato | Tipo | Melhor Para | Tamanho Máx | Extensão |
|---------|------|-------------|-------------|----------|
| **GeoPackage** | Vetor | Uso geral, grandes conjuntos de dados | Ilimitado | `.gpkg` |
| **Shapefile** | Vetor | Compatibilidade legada | 2 GB | `.shp` |
| **GeoJSON** | Vetor | Mapeamento web, APIs | ~500 MB | `.geojson` |
| **KML/KMZ** | Vetor | Google Earth, mobile | ~100 MB | `.kml`, `.kmz` |
| **CSV** | Tabular | Planilhas, apenas coordenadas | Ilimitado | `.csv` |
| **PostGIS** | Banco de dados | Grandes conjuntos de dados, empresarial | Ilimitado | `(database)` |
| **Spatialite** | Banco de dados | Conjuntos de dados médios, portátil | ~140 TB | `.sqlite` |

### Transformação de SRC

Reprojete camadas durante a exportação para um sistema de coordenadas diferente:

<img src="/filter_mate/img/ui-exporting-crs-selector.png" alt="ui-exporting-crs-selector" width="300"/>

*QgsProjectionSelectionWidget para seleção de SRC*


**Recursos**:
- Escolha qualquer código EPSG ou SRC personalizado
- Predefinições de SRC comuns (WGS84, Web Mercator, projeções locais)
- Reprojeção on-the-fly durante a exportação
- Preserva a camada original (sem modificação)

**Transformações de SRC Comuns**:
```
Original → SRC Export | Caso de Uso
----------------------|-------------------------------------
EPSG:4326 → EPSG:3857| Mapeamento web (Leaflet, OpenLayers)
Local → EPSG:4326     | Compatibilidade GPS
EPSG:4326 → zona UTM | Medições de distância precisas
Vários → SRC único   | Harmonizar dados de múltiplas fontes
```

### Exportação de Estilo

Exporte o estilo da camada junto com os dados:

<!-- <!-- ![Style Selector](/img/ui-components/ui-exporting-style-selector.png --> -->
*Escolha o formato de estilo: QML (QGIS), SLD (Padrão), ou ArcGIS*

**Formatos Disponíveis**:
- **QML** (Estilo QGIS) - Estilo QGIS completo, preserva todos os recursos
- **SLD** (Styled Layer Descriptor) - Padrão OGC, funciona no GeoServer, MapServer
- **ArcGIS** - Estilo compatível com ArcGIS para software Esri

**Comportamento da Exportação de Estilo**:
```
Formato    | Inclui                      | Compatível Com
-----------|-----------------------------|--------------------------
QML        | Árvore de estilo QGIS       | Apenas QGIS
SLD        | Simbologia + rótulos        | GeoServer, MapServer, QGIS
ArcGIS     | Simbologia Esri             | ArcGIS Desktop, ArcGIS Pro
```

### Opções de Saída

Configure o destino e modo de entrega:

<img src="/filter_mate/img/ui-exporting-output-folder.png" alt="ui-exporting-output-folder" width="300"/>

*QgsFileWidget para seleção de pasta*

<img src="/filter_mate/img/ui-exporting-output-zip.png" alt="ui-exporting-output-zip" width="300"/>

*Caixas de seleção para modo Batch e compressão ZIP*

**Opções**:
- **Pasta de Saída**: Escolha o diretório de destino
- **Modo Batch**: Exporte cada camada para um arquivo separado (vs arquivo único para todas)
- **Compressão ZIP**: Comprima automaticamente a saída para entrega

**Comparação do Modo Batch**:
```
Modo Normal:
pasta_saida/
  └── export.gpkg (contém todas as camadas)

Modo Batch:
pasta_saida/
  ├── camada1.gpkg
  ├── camada2.gpkg
  └── camada3.gpkg

Batch + ZIP:
pasta_saida/
  └── export_2024-12-09.zip
      ├── camada1.gpkg
      ├── camada2.gpkg
      └── camada3.gpkg
```

## Fluxo de Exportação

Processo completo de exportação da aba EXPORTING:

```mermaid
sequenceDiagram
    participant U as Usuário
    participant E as Aba EXPORTING
    participant FM as FilterMate
    participant Q as QGIS
    participant DB as Backend
    participant F as Sistema de Arquivos
    
    U->>E: 1. Alternar para aba EXPORTING
    U->>E: 2. Selecionar camadas para exportar (multi-seleção)
    E->>U: Mostrar indicador "Has Layers to Export"
    
    U->>E: 3. Escolher formato (GPKG/SHP/GeoJSON/etc.)
    E->>U: Mostrar indicador "Has Datatype"
    
    U->>E: 4. Opcional: Selecionar transformação de SRC
    E->>U: Mostrar indicador "Has Projection" (se selecionado)
    
    U->>E: 5. Opcional: Escolher exportação de estilo (QML/SLD/ArcGIS)
    E->>U: Mostrar indicador "Has Styles" (se selecionado)
    
    U->>E: 6. Selecionar pasta de saída
    E->>U: Mostrar indicador "Has Output Folder"
    
    U->>E: 7. Opcional: Ativar modo batch + ZIP
    E->>U: Mostrar indicador "Has ZIP" (se ativado)
    
    U->>FM: 8. Clicar no botão EXPORT
    FM->>Q: Preparar parâmetros de exportação
    
    loop Para Cada Camada Selecionada
        Q->>DB: Consultar feições (com filtros se aplicados)
        DB->>Q: Retornar dados de feições
        
        alt Transformação de SRC Necessária
            Q->>Q: Reprojetar geometrias
        end
        
        Q->>F: Escrever no formato de saída
        
        alt Exportação de Estilo Ativada
            Q->>F: Escrever arquivo de estilo (.qml/.sld/etc.)
        end
    end
    
    alt Compressão ZIP Ativada
        F->>F: Comprimir todas as saídas para ZIP
    end
    
    F->>FM: Exportação completa
    FM->>U: Mostrar mensagem de sucesso com caminho(s) do arquivo
```

### Exemplo Passo a Passo: Exportar Após Filtrar

**Cenário**: Exportar edifícios dentro de 200m de estradas (da aba FILTERING) para GeoPackage

<!-- <!-- ![Step 1 - Filter Applied](/img/workflows/workflow-filtering-11.png --> -->
*1. Aba FILTERING: Filtro aplicado, 3.847 edifícios encontrados*

<!-- <!-- ![Step 2 - Switch to EXPORTING](/img/workflows/workflow-exporting-01.png --> -->
*2. Alternar para aba EXPORTING*

<!-- <!-- ![Step 3 - Select Layers](/img/workflows/workflow-exporting-02.png --> -->
*3. Selecionar camada "buildings" para exportar (o subconjunto filtrado será exportado)*

<!-- <!-- ![Step 4 - Configure Export](/img/workflows/workflow-exporting-02.png --> -->
*4. Configurar: Formato=GPKG, SRC=EPSG:3857 (Web Mercator), Estilos=QML*

Todos os indicadores ativos:
- Has Layers to Export ✓
- Has Datatype (GPKG) ✓
- Has Projection (EPSG:3857) ✓
- Has Styles (QML) ✓

<!-- <!-- ![Step 5 - Output Folder](/img/workflows/workflow-exporting-03.png --> -->
*5. Selecionar pasta de saída + nome do arquivo*

<!-- <!-- ![Step 6 - Export](/img/workflows/workflow-exporting-03.png --> -->
*6. Clicar no botão EXPORT → Barra de progresso mostra processamento*

<!-- <!-- ![Step 7 - Success](/img/workflows/workflow-exporting-04.png --> -->
*7. Notificação de sucesso com caminho de saída: `C:/exports/buildings_filtered.gpkg` (3.847 feições, 2,3 MB)*

**Resultado**:
- Arquivo criado: `buildings_filtered.gpkg`
- Arquivo de estilo: `buildings_filtered.qml` (na mesma pasta)
- SRC: EPSG:3857 (reprojetado do original EPSG:4326)
- Feições: 3.847 (apenas subconjunto filtrado)

## Detalhes dos Formatos

### GeoPackage (.gpkg)

**Formato recomendado** para a maioria dos casos de uso.

**Vantagens:**
- ✅ Arquivo único (portátil)
- ✅ Tamanho ilimitado
- ✅ Múltiplas camadas por arquivo
- ✅ Índices espaciais embutidos
- ✅ Padrão aberto (OGC)
- ✅ Desempenho rápido
- ✅ Suporta todos os tipos de geometria

**Limitações:**
- ⚠️ Requer GDAL 2.0+ (padrão no QGIS moderno)

**Quando Usar:**
- Escolha padrão para a maioria das exportações
- Grandes conjuntos de dados (>100k feições)
- Exportações de múltiplas camadas
- Arquivamento de longo prazo

**Exemplo de Exportação:**
```python
arquivo_saida = "/caminho/para/export.gpkg"
nome_camada = "feicoes_filtradas"
# Arquivo único, múltiplas camadas possíveis
```

### Shapefile (.shp)

Formato legado para **retrocompatibilidade**.

**Vantagens:**
- ✅ Compatibilidade universal
- ✅ Amplamente suportado
- ✅ Estrutura simples

**Limitações:**
- ❌ Limite de tamanho de arquivo de 2 GB
- ❌ Limite de nome de campo de 10 caracteres
- ❌ Tipos de dados limitados
- ❌ Múltiplos arquivos (.shp, .dbf, .shx, .prj)
- ❌ Sem tipos de geometria mistos
- ⚠️ Problemas de codificação (caracteres não-ASCII)

**Quando Usar:**
- Exigido por software legado
- Compartilhamento com usuários do ArcGIS Desktop 9.x
- Conjuntos de dados simples e pequenos

**Recomendações:**
- Use GeoPackage em vez disso, se possível
- Mantenha a contagem de feições < 100k
- Evite nomes de campos longos
- Teste a codificação com caracteres não-ASCII

**Exemplo de Exportação:**
```python
arquivo_saida = "/caminho/para/export.shp"
# Cria arquivos .shp, .dbf, .shx, .prj
```

### GeoJSON (.geojson)

Formato baseado em texto para **aplicações web**.

**Vantagens:**
- ✅ Legível por humanos
- ✅ Amigável para web
- ✅ Nativo em JavaScript
- ✅ Integração com API
- ✅ Amigável para controle de versão

**Limitações:**
- ⚠️ Tamanhos de arquivo grandes (formato texto)
- ⚠️ Desempenho mais lento que formatos binários
- ⚠️ Sem índices espaciais
- ⚠️ WGS84 (EPSG:4326) recomendado

**Quando Usar:**
- Mapeamento web (Leaflet, Mapbox)
- APIs REST
- Pequenos a médios conjuntos de dados (`<10k` feições)
- Controle de versão Git

**Exemplo de Exportação:**
```python
arquivo_saida = "/caminho/para/export.geojson"
src = "EPSG:4326"  # WGS84 recomendado para web
```

### KML/KMZ (.kml, .kmz)

Formato para **Google Earth** e aplicativos móveis.

**Vantagens:**
- ✅ Compatibilidade com Google Earth
- ✅ KMZ inclui estilo e imagens
- ✅ Suporte a aplicativos móveis
- ✅ Legível por humanos (KML)

**Limitações:**
- ❌ Suporte limitado a atributos
- ❌ Complexidade de estilo
- ⚠️ Problemas de desempenho com grandes conjuntos de dados
- ⚠️ Apenas WGS84 (EPSG:4326)

**Quando Usar:**
- Visualização no Google Earth
- Aplicativos móveis de campo
- Apresentações para partes interessadas
- Engajamento público

**Exemplo de Exportação:**
```python
arquivo_saida = "/caminho/para/export.kmz"  # Comprimido
# ou
arquivo_saida = "/caminho/para/export.kml"  # Texto
```

### CSV (.csv)

Formato **tabular** para coordenadas e atributos.

**Vantagens:**
- ✅ Compatibilidade universal com planilhas
- ✅ Tamanho de arquivo pequeno
- ✅ Fácil de editar
- ✅ Amigável para importação em banco de dados

**Limitações:**
- ❌ Sem geometria (apenas coordenadas X,Y para pontos)
- ❌ Sem referência espacial
- ❌ Sem estilo
- ⚠️ Apenas pontos (sem linhas/polígonos)

**Quando Usar:**
- Apenas coordenadas de pontos
- Análise em Excel/planilha
- Relatórios apenas de atributos
- Importações de banco de dados

**Exemplo de Exportação:**
```python
arquivo_saida = "/caminho/para/export.csv"
# Inclui colunas X, Y para geometria de ponto
# GEOMETRY_AS: 'AS_XY' ou 'AS_WKT'
```

### PostGIS (PostgreSQL)

Exportar para **banco de dados PostgreSQL** com extensão PostGIS.

**Vantagens:**
- ✅ Melhor desempenho
- ✅ Tamanho ilimitado
- ✅ Acesso multi-usuário
- ✅ Índices espaciais
- ✅ Consultas avançadas
- ✅ Recursos empresariais

**Limitações:**
- ⚠️ Requer PostgreSQL + PostGIS
- ⚠️ Configuração de rede necessária
- ⚠️ Administração mais complexa

**Quando Usar:**
- Ambientes empresariais
- Grandes conjuntos de dados (>1M feições)
- Colaboração multi-usuário
- Atualizações contínuas
- Integração com sistemas backend

**Exemplo de Exportação:**
```python
conexao = "postgresql://user:password@host:5432/database"
schema = "public"
nome_tabela = "feicoes_filtradas"
```

### Spatialite (.sqlite)

**Arquivo de banco de dados** leve.

**Vantagens:**
- ✅ Arquivo único
- ✅ Índices espaciais
- ✅ Consultas SQL
- ✅ Bom desempenho
- ✅ Sem necessidade de servidor

**Limitações:**
- ⚠️ Mais lento que PostGIS
- ⚠️ Limitação de escrita única
- ⚠️ Máximo teórico de 140 TB

**Quando Usar:**
- Bancos de dados portáteis
- Conjuntos de dados médios (10k-1M feições)
- Trabalho offline
- Aplicações desktop

**Exemplo de Exportação:**
```python
arquivo_saida = "/caminho/para/export.sqlite"
nome_tabela = "feicoes_filtradas"
```

## Opções de Exportação

### Sistema de Referência de Coordenadas (SRC)

Escolha o SRC de destino para sua exportação:

```python
# Manter SRC original
src = layer.crs()

# Transformar para WGS84 (web/GPS)
src = "EPSG:4326"

# Transformar para projeção local
src = "EPSG:32633"  # UTM Zona 33N
```

**Escolhas Comuns de SRC:**
- **EPSG:4326** (WGS84) - Mapas web, GPS, global
- **EPSG:3857** (Web Mercator) - Tiles web
- **EPSG:32xxx** (UTM) - Projetado local, métrico
- **SRC Original** - Manter projeção de origem

### Seleção de Campos

Exporte campos específicos ou todos os atributos:

```python
# Todos os campos
campos_exportacao = None

# Apenas campos selecionados
campos_exportacao = ['nome', 'populacao', 'area', 'data']

# Excluir campos
campos_excluir = ['id_interno', 'campo_temp']
```

### Tipo de Geometria

Controle a exportação de geometria:

```python
# Manter geometria (padrão)
geometria = True

# Apenas atributos (sem geometria)
geometria = False

# Simplificar geometria (reduzir tamanho)
geometria = "simplified"
tolerancia_simplificacao = 10  # metros
```

### Codificação

Codificação de caracteres para campos de texto:

```python
# UTF-8 (recomendado, padrão)
codificacao = "UTF-8"

# Latin-1 (Europa Ocidental)
codificacao = "ISO-8859-1"

# Windows-1252 (padrão Windows)
codificacao = "CP1252"
```

## Estratégias de Exportação

### Exportação de Grandes Conjuntos de Dados

Para conjuntos de dados > 100k feições:

```mermaid
graph TD
    A[Grande Conjunto de Dados] --> B{Verificação de Tamanho}
    B -->|< 100k| C[Exportação Direta]
    B -->|100k - 1M| D[GeoPackage]
    B -->|> 1M| E[PostGIS]
    
    D --> F[Ativar Índice Espacial]
    E --> G[Processamento em Lote]
    
    F --> H[Exportação Completa]
    G --> H
    C --> H
    
    style D fill:#90EE90
    style E fill:#87CEEB
```

**Recomendações:**
1. **Use GeoPackage ou PostGIS** - Formatos binários
2. **Ative índices espaciais** - Acesso posterior mais rápido
3. **Processamento em lote** - Exporte em partes se necessário
4. **Simplifique a geometria** - Reduza a contagem de vértices se apropriado

### Exportação Multi-Formato

Exporte os mesmos dados para múltiplos formatos:

```python
# Fluxo de exportação
filtro_aplicado = True

# Versão web (GeoJSON)
export_geojson(src="EPSG:4326", simplificado=True)

# Versão desktop (GeoPackage)
export_geopackage(src=src_original, precisao_completa=True)

# Versão planilha (CSV)
export_csv(coordenadas="XY", apenas_atributos=False)
```

### Exportações Incrementais

Exporte mudanças desde a última atualização:

```python
# Filtrar por data
expressao_filtro = "last_modified >= '2024-01-01'"

# Exportar com timestamp
arquivo_saida = f"atualizacoes_{datetime.now().strftime('%Y%m%d')}.gpkg"
```

## Exemplos Práticos

### Exportação de Planejamento Urbano

```python
# Exportar lotes filtrados para revisão
expressao_filtro = """
zona = 'comercial'
AND area > 5000
AND status = 'proposto'
"""

# Múltiplos formatos para diferentes partes interessadas
export_geopackage("lotes_revisao.gpkg")  # Equipe SIG
export_kml("lotes_revisao.kmz")  # Apresentação pública
export_csv("lista_lotes.csv")  # Conselho de planejamento
```

### Monitoramento Ambiental

```python
# Exportar locais de monitoramento com dados recentes
expressao_filtro = """
tipo_local = 'qualidade_agua'
AND ultima_amostra >= now() - interval '30 days'
AND contagem_parametros > 5
"""

# GeoJSON para dashboard web
export_geojson(
    saida="locais_monitoramento.geojson",
    src="EPSG:4326",
    campos=['id_local', 'ultima_amostra', 'status']
)
```

### Resposta de Emergência

```python
# Exportar zonas de evacuação
expressao_filtro = """
intersects(
    $geometry,
    buffer(geometry(get_feature('perigo', 'status', 'ativo')), 2000)
)
AND ocupacao > 0
"""

# KML para equipes de campo
export_kml("zonas_evacuacao.kmz")

# GeoPackage para análise SIG
export_geopackage("analise_evacuacao.gpkg")
```

## Otimização de Desempenho

### Comparação de Backends

| Backend | Velocidade de Exportação | Recomendado |
|---------|--------------------------|-------------|
| PostgreSQL | ⚡⚡⚡⚡ Mais Rápido | GeoPackage, PostGIS |
| Spatialite | ⚡⚡⚡ Rápido | GeoPackage, Spatialite |
| OGR | ⚡⚡ Moderado | GeoPackage |

### Dicas de Otimização

1. **Simplificar Geometria**
   ```python
   # Reduzir contagem de vértices
   tolerancia_simplificacao = 10  # metros
   ```

2. **Selecionar Campos Necessários**
   ```python
   # Exportar apenas atributos necessários
   campos = ['id', 'nome', 'status']
   ```

3. **Usar Formato Apropriado**
   ```python
   # Formatos binários mais rápidos que texto
   GeoPackage > Shapefile > GeoJSON
   ```

4. **Ativar Índices Espaciais**
   ```python
   # Para GeoPackage/Spatialite
   criar_indice_espacial = True
   ```

## Solução de Problemas

### Exportação Falha

**Problemas Comuns:**

1. **Arquivo Bloqueado**
   - Feche aplicações usando o arquivo
   - Verifique permissões do arquivo

2. **Espaço em Disco**
   - Verifique espaço disponível
   - Use compressão (KMZ, GPKG)

3. **Geometrias Inválidas**
   ```sql
   -- Filtre geometrias inválidas antes da exportação
   is_valid($geometry)
   ```

4. **Problemas de Codificação**
   - Use codificação UTF-8
   - Teste com feições de amostra

### Tamanho de Arquivo Grande

**Soluções:**

1. **Simplificar geometria**
   ```python
   tolerancia_simplificacao = 10  # Reduzir precisão
   ```

2. **Reduzir atributos**
   ```python
   campos = ['campo_essencial_1', 'campo_essencial_2']
   ```

3. **Usar compressão**
   ```python
   # KMZ em vez de KML
   # GPKG tem compressão interna
   ```

4. **Dividir em tiles**
   ```python
   # Exportar por região ou grade
   expressao_filtro = "regiao = 'norte'"
   ```

### Problemas de Projeção

**Soluções:**

1. **Verificar SRC de origem**
   ```python
   src_origem = layer.crs()
   print(f"Origem: {src_origem.authid()}")
   ```

2. **Transformar explicitamente**
   ```python
   src_destino = "EPSG:4326"
   ```

3. **Verificar precisão da transformação**
   ```python
   # Use a transformação apropriada
   # Especialmente para datums históricos
   ```

## Exemplos de Exportação em Lote

### Múltiplas Camadas Filtradas

Exporte várias camadas com diferentes configurações:

**Cenário**: Exportar 3 camadas com diferentes filtros, formatos e SRC

**Passo 1 - Filtrar Camadas** (na aba FILTERING):
```
Camada 1 (lotes): zona = 'comercial'
Camada 2 (edificios): ano_construcao > 2020
Camada 3 (estradas): classe_estrada = 'rodovia'
```

**Passo 2 - Configurar Exportação em Lote** (na aba EXPORTING):
```
Configuração da Aba EXPORTING:
- Camadas selecionadas: lotes, edificios, estradas (todas as 3)
- Formato: GeoPackage
- SRC: EPSG:3857 (Web Mercator)
- Estilos: QML
- Pasta de saída: C:/exports/
- Modo batch: ATIVADO
- ZIP: ATIVADO
```

**Resultado**:
```
C:/exports/export_2024-12-09.zip
  ├── lotes.gpkg (zonas comerciais, filtradas)
  ├── lotes.qml
  ├── edificios.gpkg (edifícios recentes, filtrados)
  ├── edificios.qml
  ├── estradas.gpkg (rodovias, filtradas)
  └── estradas.qml
```

**Benefícios**:
- Operação única exporta todas as camadas
- Cada camada em arquivo separado (modo batch)
- Todas reprojetadas para Web Mercator
- Estilos preservados
- Comprimido para entrega

### Exportar Dados Não Filtrados

Para exportar camadas completas (sem filtros):

**Opção 1 - Remover Filtros Primeiro** (aba FILTERING):
1. Alternar para aba FILTERING
2. Clicar no botão RESET para limpar todos os filtros
3. Alternar para aba EXPORTING
4. Exportar normalmente

**Opção 2 - Exportar Camadas Diferentes**:
- Simplesmente selecione camadas que não têm filtros aplicados
- A aba EXPORTING exporta o estado atual da camada

:::info Exportação Filtrada vs Não Filtrada
- **Com filtros**: A aba EXPORTING exporta apenas feições que correspondem aos filtros atuais
- **Sem filtros**: Exporta a camada completa (todas as feições)
- Verifique a contagem de feições no seletor de camadas para confirmar o que será exportado
:::

## Tópicos Relacionados

- [Fundamentos de Filtragem](filtering-basics.md) - Criar filtros para exportar subconjuntos filtrados (aba FILTERING)
- [Filtragem Geométrica](geometric-filtering.md) - Aplicar filtros espaciais antes da exportação
- [Operações de Buffer](buffer-operations.md) - Filtragem baseada em proximidade antes da exportação
- [Visão Geral da Interface](interface-overview.md) - Guia completo dos componentes da aba EXPORTING

:::info Fluxo de Trabalho das Três Abas Principais
1. **Aba FILTERING**: Criar subconjuntos filtrados (opcional)
2. **Aba EXPLORING**: Visualizar e verificar feições (opcional)
3. **Aba EXPORTING**: Exportar para vários formatos (filtrado ou não filtrado)

Todas as três abas trabalham juntas para fornecer um fluxo de trabalho completo de processamento de dados.
:::

## Próximos Passos

- **[Histórico de Filtros](filter-history.md)** - Reutilizar configurações de filtros para exportações
- **[Visão Geral da Interface](interface-overview.md)** - Aprender sobre as três abas principais
