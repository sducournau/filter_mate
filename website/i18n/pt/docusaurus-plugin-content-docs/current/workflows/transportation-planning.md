---
sidebar_position: 6
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Planejamento de Transporte: Exportação de Dados Viários

Extrair e exportar segmentos viários dentro de limites municipais com atributos específicos para análise de planejamento de transporte.

## Visão Geral do Cenário

**Objetivo**: Exportar todas as vias principais (rodovia, primária, secundária) dentro dos limites da cidade com transformação apropriada de SRC para software CAD/engenharia.

**Aplicação do Mundo Real**:
- Departamentos de transporte preparando dados para empreiteiros
- Empresas de engenharia analisando redes viárias
- Analistas SIG criando subconjuntos de dados para modelagem
- Planejadores urbanos avaliando cobertura de infraestrutura

**Tempo Estimado**: 10 minutos

**Dificuldade**: ⭐ Iniciante

---

## Pré-requisitos

### Dados Necessários

1. **Camada de Rede Viária** (linhas)
   - Segmentos viários/eixos
   - Atributos necessários:
     - `tipo_via` ou classificação `highway`
     - `nome` (nome da rua)
   - Opcional: `superficie`, `faixas`, `velocidade_max`, `estado`

2. **Limite Municipal** (polígono)
   - Limite de cidade, município ou distrito
   - Feição única preferida (usar Dissolver se múltiplas)
   - Deve corresponder ou sobrepor extensão da rede viária

### Fontes de Dados de Exemplo

**Dados Viários**:
```python
# OpenStreetMap via QuickOSM
Chave: "highway", Valor: "*"

# Tipos de vias a incluir:
- motorway (rodovia)
- trunk (via expressa)  
- primary (via principal)
- secondary (via secundária)
- tertiary (via terciária)
```

**Limites**:
- Portais SIG municipais (limites oficiais)
- Arquivos Census TIGER/Line (EUA)
- Limites administrativos OpenStreetMap
- Agências cartográficas nacionais (IBGE, etc.)

### Recomendação de Backend

**Qualquer Backend** - Este fluxo de trabalho foca em recursos de exportação:
- **OGR**: Compatibilidade universal, funciona com todos os formatos
- **Spatialite**: Se você precisa de processamento temporário
- **PostgreSQL**: Se exportando redes muito grandes (>100k segmentos)

Todos os backends exportam identicamente - escolha baseado em sua configuração.

---

## Instruções Passo a Passo

### Passo 1: Carregar e Verificar Dados

1. **Carregar camadas** no QGIS:
   - `rede_viaria.gpkg` (ou OSM .shp, .geojson)
   - `limite_cidade.gpkg`

2. **Verificar SRC**:
   ```
   Ambas as camadas devem idealmente estar no mesmo SRC
   Clique direito → Propriedades → Informação → SRC
   
   Nota: Não é crítico para este fluxo (FilterMate lida com reprojeção)
   ```

3. **Inspecionar atributos**:
   ```
   Abrir tabela de atributos vias (F6)
   Encontrar campo de classificação viária: "highway", "tipo_via", "fclass", etc.
   Anotar nome do campo para próximo passo
   ```

4. **Verificar limite**:
   ```
   Selecionar camada limite_cidade
   Deve mostrar feição única cobrindo sua área de interesse
   Se múltiplos polígonos: Vetor → Geoprocessamento → Dissolver
   ```

:::tip Classificações Viárias OSM
Valores OpenStreetMap `highway`:
- `motorway`: Rodovia
- `trunk`: Vias expressas entre cidades
- `primary`: Vias principais dentro das cidades
- `secondary`: Vias de ligação  
- `tertiary`: Vias locais importantes
- `residential`: Ruas de bairro
:::

### Passo 2: Filtrar Vias por Tipo e Localização

**Usando FilterMate**:

1. Abrir painel FilterMate
2. Selecionar camada **rede_viaria**
3. Escolher **qualquer backend** (OGR serve)
4. Inserir expressão de filtro:

<Tabs>
  <TabItem value="osm" label="Dados OpenStreetMap" default>
    ```sql
    -- Vias principais apenas (excluir residencial, vias de serviço)
    "highway" IN ('motorway', 'trunk', 'primary', 'secondary')
    
    -- Dentro do limite da cidade
    AND intersects(
      $geometry,
      aggregate(
        layer:='limite_cidade',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
  </TabItem>
  
  <TabItem value="generic" label="Dados Viários Genéricos">
    ```sql
    -- Ajustar nome do campo conforme seus dados
    "tipo_via" IN ('rodovia', 'arterial', 'coletora')
    
    -- Dentro do município
    AND within(
      $geometry,
      aggregate('limite_cidade', 'collect', $geometry)
    )
    ```
  </TabItem>
  
  <TabItem value="advanced" label="Filtragem Avançada">
    ```sql
    -- Vias principais + critérios adicionais
    "highway" IN ('motorway', 'trunk', 'primary', 'secondary')
    AND intersects($geometry, aggregate('limite_cidade', 'collect', $geometry))
    
    -- Opcional: Adicionar filtros de condição
    AND ("superficie" = 'paved' OR "superficie" IS NULL)  -- Excluir não pavimentado
    AND "faixas" >= 2  -- Múltiplas faixas apenas
    AND "acesso" != 'private'  -- Vias públicas apenas
    ```
  </TabItem>
</Tabs>

5. Clicar em **Aplicar Filtro**
6. Revisar contagem: "Mostrando X de Y feições"
7. Inspecionar visualmente: Apenas vias principais dentro do limite devem estar destacadas

**Resultado Esperado**: Segmentos viários filtrados para tipos principais dentro dos limites da cidade

### Passo 3: Revisar e Refinar Seleção

**Verificar cobertura**:

1. Aproximar para extensão completa de limite_cidade
2. Verificar que vias filtradas cobrem todo o município
3. Procurar por lacunas ou segmentos faltando

**Ajustar se necessário**:

```sql
-- Se muitas vias incluídas, ser mais rigoroso:
"highway" IN ('motorway', 'trunk', 'primary')  -- Excluir secondary

-- Se faltam vias importantes, expandir:
"highway" IN ('motorway', 'trunk', 'primary', 'secondary', 'tertiary')

-- Se usando classificação personalizada:
"classe_funcional" IN (1, 2, 3)  -- Códigos numéricos
```

**Casos limite** - Vias parcialmente fora do limite:

<Tabs>
  <TabItem value="include" label="Incluir Segmentos Parciais" default>
    ```sql
    -- Usar intersects (inclui sobreposições parciais)
    intersects($geometry, aggregate('limite_cidade', 'collect', $geometry))
    ```
  </TabItem>
  
  <TabItem value="exclude" label="Apenas Completamente Dentro">
    ```sql
    -- Usar within (apenas vias totalmente contidas)
    within($geometry, aggregate('limite_cidade', 'collect', $geometry))
    ```
  </TabItem>
  
  <TabItem value="clip" label="Recortar para Limite (Manual)">
    Após filtragem, usar ferramenta Recortar do QGIS:
    ```
    Vetor → Geoprocessamento → Recortar
    Entrada: vias filtradas
    Sobreposição: limite_cidade
    Resultado: Vias cortadas exatamente no limite
    ```
  </TabItem>
</Tabs>

### Passo 4: Selecionar Atributos para Exportar

**Identificar campos úteis**:

1. Abrir **Tabela de Atributos** da camada filtrada
2. Anotar colunas relevantes:
   ```
   Essenciais:
   - id_via, osm_id (identificador)
   - nome (nome da rua)
   - highway / tipo_via (classificação)
   
   Úteis:
   - superficie (pavimentado, não pavimentado, etc.)
   - faixas (número de faixas)
   - velocidade_max (limite de velocidade)
   - comprimento_m (calculado ou existente)
   ```

3. Opcional: **Remover colunas desnecessárias** antes da exportação:
   ```
   Camada → Propriedades → Campos
   Ativar modo de edição (ícone lápis)
   Excluir campos indesejados (metadados osm, etc.)
   Salvar edições
   ```

### Passo 5: Adicionar Campos Calculados (Opcional)

**Adicionar comprimento de via** em suas unidades preferidas:

1. Abrir **Calculadora de Campo** (Ctrl+I)
2. Criar novo campo:
   ```
   Nome do campo: comprimento_m
   Tipo: Decimal (double)
   Precisão: 2
   
   Expressão:
   $length
   ```

**Adicionar comprimento em diferentes unidades**:
   ```
   Nome do campo: comprimento_km
   Expressão: $length / 1000  -- metros para quilômetros
   ```

**Adicionar classificação funcional** (se convertendo dados OSM):
   ```
   Nome do campo: classe_funcional
   Tipo: Inteiro
   
   Expressão:
   CASE
     WHEN "highway" IN ('motorway', 'trunk') THEN 1
     WHEN "highway" = 'primary' THEN 2
     WHEN "highway" = 'secondary' THEN 3
     WHEN "highway" = 'tertiary' THEN 4
     ELSE 5
   END
   ```

### Passo 6: Escolher SRC Alvo para Exportação

**Escolhas comuns de SRC**:

<Tabs>
  <TabItem value="wgs84" label="WGS84 (Universal)" default>
    ```
    EPSG:4326 - WGS84 Geográfico
    
    Usar para:
    - Mapeamento web (Leaflet, Google Maps)
    - Aplicações GPS
    - Interoperabilidade máxima
    
    ⚠️ Não adequado para CAD (usa graus, não metros)
    ```
  </TabItem>
  
  <TabItem value="utm" label="UTM (Engenharia)">
    ```
    EPSG:326XX - Zonas UTM
    Exemplos:
    - EPSG:32633 - Zona UTM 33N (Europa Central)
    - EPSG:32723 - Zona UTM 23S (Brasil Sul)
    
    Usar para:
    - Software CAD (AutoCAD, MicroStation)
    - Desenhos de engenharia
    - Medições precisas de distância
    
    ✓ Baseado em metros, preserva precisão
    ```
  </TabItem>
  
  <TabItem value="local" label="Grade Local">
    ```
    Sistemas Nacionais/Regionais
    Exemplos:
    - EPSG:31984 - SIRGAS 2000 / UTM zone 24S (Brasil)
    - EPSG:2154 - Lambert 93 (França)
    - EPSG:3857 - Web Mercator (mapas web)
    
    Usar para:
    - Compatibilidade agência cartográfica nacional
    - Conformidade com padrões regionais
    ```
  </TabItem>
</Tabs>

**Encontrar seu SRC**:
- Buscar em [epsg.io](https://epsg.io/) por localização
- Verificar requisitos/especificações do projeto
- Perguntar à organização receptora o SRC preferido

### Passo 7: Exportar Vias Filtradas

**Usando Exportação FilterMate** (Recomendado):

1. No painel FilterMate, clicar em **Exportar Feições Filtradas**
2. Configurar ajustes de exportação:

   ```
   Formato: Escolher baseado nas necessidades do destinatário
   
   Para SIG:
   ├── GeoPackage (.gpkg) - Melhor para QGIS/SIG modernos
   ├── Shapefile (.shp) - Formato SIG universal
   └── GeoJSON (.geojson) - Mapeamento web, leve
   
   Para CAD:
   ├── DXF (.dxf) - AutoCAD, mais compatível
   └── DWG (.dwg) - AutoCAD (requer plugin)
   
   Para Bancos de Dados:
   ├── PostGIS - Exportação direta para banco
   └── Spatialite - Banco de dados embutido
   
   Para Outros:
   ├── CSV com geometria WKT - Baseado em texto
   ├── KML - Google Earth
   └── GPX - Dispositivos GPS
   ```

3. **Definir SRC** (Sistema de Referência de Coordenadas):
   ```
   Clicar no seletor de SRC
   Buscar SRC alvo (ex: "SIRGAS" ou "EPSG:31984")
   Selecionar e confirmar
   
   ℹ️ FilterMate reprojetará automaticamente
   ```

4. **Configurar opções**:
   ```
   ✓ Exportar apenas feições selecionadas (já filtradas)
   ✓ Ignorar campos de atributo: [escolher campos desnecessários]
   ✓ Adicionar coluna geometria (para exportações CSV)
   ✓ Forçar tipo multi-linha (se necessário)
   ```

5. **Nomear e salvar**:
   ```
   Nome do arquivo: cidade_vias_principais_sirgas_2024.gpkg
   
   Convenção de nomenclatura dica:
   [local]_[conteudo]_[src]_[data].[ext]
   ```

6. Clicar em **Exportar** → Aguardar confirmação

### Passo 8: Validar Exportação

**Verificações de qualidade**:

1. **Carregar arquivo exportado** de volta no QGIS:
   ```
   Camada → Adicionar Camada → Adicionar Camada Vetorial
   Navegar até arquivo exportado
   ```

2. **Verificar SRC**:
   ```
   Clique direito na camada → Propriedades → Informação
   Verificar se SRC corresponde ao seu alvo (ex: EPSG:31984)
   ```

3. **Verificar contagem de feições**:
   ```
   Deve corresponder à contagem filtrada do Passo 2
   Abrir tabela de atributos (F6) para verificar
   ```

4. **Inspecionar atributos**:
   ```
   Todos os campos selecionados presentes e preenchidos
   Sem valores NULL em campos críticos
   Codificação de texto correta (sem caracteres corrompidos)
   ```

5. **Comparação visual**:
   ```
   Sobrepor camada exportada com original
   Verificar se geometrias correspondem exatamente
   Verificar se nenhum segmento foi perdido ou duplicado
   ```

**Testar com software do destinatário** (se possível):
- Abrir no AutoCAD/MicroStation (para exportações DXF)
- Carregar no ArcGIS/MapInfo (para Shapefile)
- Importar para banco de dados (para exportações SQL)

---

## Entendendo os Resultados

### O Que Você Exportou

✅ **Incluído**:
- Vias principais (motorway, trunk, primary, secondary) apenas
- Vias intersectando/dentro do limite da cidade
- Atributos selecionados relevantes para análise
- Geometria reprojetada para SRC alvo

❌ **Excluído**:
- Vias menores (residencial, serviço, caminhos)
- Vias fora do município
- Metadados OSM e campos técnicos
- SRC original (se reprojetado)

### Expectativas de Tamanho de Arquivo

**Tamanhos típicos** para cidade média (área de 500km²):

```
Formato     | ~10k segmentos | Notas
------------|----------------|----------------------------
GeoPackage  | 2-5 MB         | Menor, mais rápido
Shapefile   | 3-8 MB         | Arquivos múltiplos (.shp/.dbf/.shx)
GeoJSON     | 5-15 MB        | Baseado em texto, maior mas legível
DXF         | 4-10 MB        | Formato CAD
CSV+WKT     | 10-30 MB       | Geometria texto, muito grande
```

---

## Melhores Práticas

### Preparação de Dados

**Lista de verificação antes da exportação**:

```
□ Filtro aplicado e verificado
□ Tabela de atributos revisada
□ Campos desnecessários removidos
□ Campos calculados adicionados (comprimento, etc.)
□ Geometrias validadas
□ SRC determinado
□ Formato de exportação confirmado com destinatário
```

### Convenções de Nomenclatura

**Boas práticas de nomenclatura de arquivo**:

```
Bom:
✓ saopaulo_vias_principais_sirgas_20240312.gpkg
✓ riodejaneiro_rodovias_utm23s_v2.shp
✓ brasilia_rede_transporte_wgs84_2024.geojson

Ruim:
✗ vias.shp (muito genérico)
✗ export_final_FINAL_v3.gpkg (versionamento confuso)
✗ dados.gpkg (nome pouco descritivo)
```

### Documentação de Metadados

**Sempre incluir arquivo de metadados**:

```
metadata.txt ou README.txt conteúdo:

=== Exportação Rede Viária ===
Data: 2024-03-12
Analista: João Silva
Projeto: Plano Diretor Transporte Cidade

Dados Fonte:
- Vias: OpenStreetMap (baixado 2024-03-01)
- Limite: Portal SIG Cidade (limite oficial 2024)

Processamento:
- Filtro: Vias principais apenas (motorway, trunk, primary, secondary)
- Área: Dentro limites da cidade
- Ferramenta: Plugin QGIS FilterMate v2.8.0

Especificações Exportação:
- Formato: GeoPackage
- SRC: EPSG:31984 (SIRGAS 2000 / UTM zone 24S)
- Contagem de Feições: 8.432 segmentos
- Comprimento Total: 1.247,3 km

Atributos:
- osm_id: Identificador OpenStreetMap
- nome: Nome da rua
- highway: Classificação viária
- superficie: Tipo de pavimento
- faixas: Número de faixas
- comprimento_m: Comprimento do segmento em metros

Notas de Qualidade:
- Geometrias validadas e reparadas
- Vias parcialmente fora do limite incluídas (intersects)
- Limites de velocidade: 15% de dados faltando (padrão da cidade)

Contato: joao.silva@cidade.gov.br
```

---

## Problemas Comuns

### Problema 1: Vias ao longo do limite parcialmente cortadas

**Causa**: Uso de `within()` em vez de `intersects()`

**Solução**:
```sql
-- Mudar de:
within($geometry, aggregate('limite_cidade', 'collect', $geometry))

-- Para:
intersects($geometry, aggregate('limite_cidade', 'collect', $geometry))

-- Ou recortar geometricamente após exportação:
Vetor → Geoprocessamento → Recortar
```

### Problema 2: Exportação falha com "erro de escrita"

**Causa**: Permissões de arquivo, problemas de caminho, ou espaço em disco

**Soluções**:
```
1. Verificar espaço em disco (precisa 2-3x tamanho final do arquivo)
2. Exportar para local diferente (ex: Área de Trabalho em vez de unidade de rede)
3. Fechar arquivo se estiver aberto em outro programa
4. Usar caminho de arquivo mais curto (<100 caracteres)
5. Remover caracteres especiais do nome do arquivo
```

### Problema 3: Software CAD não abre DXF

**Causa**: Exportação DXF do QGIS pode não corresponder às expectativas da versão CAD

**Soluções**:
```
Opção A: Tentar configurações de exportação DXF diferentes
   Projeto → Importar/Exportar → Exportar Projeto para DXF
   - Versão formato DXF: AutoCAD 2010
   - Modo simbologia: Simbologia de feição

Opção B: Usar formato intermediário
   Exportar para Shapefile → Abrir no AutoCAD (suporte SHP integrado)

Opção C: Usar plugin especializado
   Instalar plugin "Another DXF Exporter"
   Melhor compatibilidade CAD que exportação nativa
```

---

## Próximos Passos

### Fluxos de Trabalho Relacionados

- **[Análise Imobiliária](./real-estate-analysis)**: Técnicas de filtragem por atributos
- **[Serviços de Emergência](./emergency-services)**: Seleção baseada em buffers
- **[Planejamento Urbano Transporte](./urban-planning-transit)**: Filtragem espacial multi-camadas

### Técnicas Avançadas

**1. Exportação de Topologia de Rede**:
```
Exportar vias com conectividade mantida para análise de roteamento
Processamento → Análise Vetorial → Análise de Rede → Áreas de Serviço
```

**2. Exportação em Lote Multi-SRC**:
```python
# Console Python - exportar para múltiplos SRC simultaneamente
lista_src_alvos = [31984, 4326, 32723]  # Códigos EPSG
layer = iface.activeLayer()

for epsg in lista_src_alvos:
    arquivo_saida = f'vias_epsg{epsg}.gpkg'
    # Usar QgsVectorFileWriter para exportação programática
```

**3. Automação de Exportação Programada**:
```python
# Criar modelo de processamento QGIS
# Agendar com cron (Linux) ou Agendador de Tarefas (Windows)
# Auto-exportar dados viários atualizados semanalmente
```

---

## Resumo

✅ **Você aprendeu**:
- Filtrar vias por classificação e limite
- Selecionar e preparar atributos para exportação
- Escolher SRC alvo apropriado
- Exportar para múltiplos formatos (GeoPackage, Shapefile, DXF, etc.)
- Validar qualidade de exportação
- Criar documentação de metadados

✅ **Técnicas chave**:
- Predicados espaciais: `intersects()` vs `within()`
- Transformação de SRC durante exportação
- Seleção de formato conforme caso de uso
- Calculadora de campo para atributos derivados
- Processamento em lote para grandes conjuntos de dados

🎯 **Impacto real**: Este fluxo de trabalho simplifica preparação de dados para projetos de transporte, garante interoperabilidade de dados entre sistemas SIG e CAD, e mantém qualidade dos dados ao longo do pipeline de análise.

💡 **Dica profissional**: Crie um **Modelo de Processamento QGIS** para este fluxo de trabalho para automatizar filtragem + exportação em um clique. Salve o modelo e reutilize para diferentes cidades ou períodos.
