---
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Planejamento Urbano: Propriedades Próximas ao Transporte

Encontrar todas as parcelas residenciais a distância de caminhada de estações de metrô para análise de desenvolvimento orientado ao transporte.

## Visão Geral do Cenário

**Objetivo**: Identificar propriedades dentro de 500 metros de estações de metrô para avaliar oportunidades de desenvolvimento orientado ao transporte.

**Aplicação do Mundo Real**:
- Departamentos de planejamento urbano avaliando zonas de desenvolvimento
- Incorporadores imobiliários encontrando propriedades acessíveis por transporte
- Formuladores de políticas avaliando equidade e cobertura de transporte
- Planejadores ambientais reduzindo dependência de carros

**Tempo Estimado**: 10 minutos

**Dificuldade**: ⭐⭐ Intermediário

---

## Pré-requisitos

### Dados Necessários

1. **Camada de Parcelas** (polígonos)
   - Limites de propriedades residenciais
   - Deve incluir atributos de uso do solo ou zoneamento
   - Recomendado: 1.000+ feições para análise realista

2. **Camada de Estações de Transporte** (pontos)
   - Localizações de estações de metrô/trem
   - Inclui nomes de estações
   - Cobre sua área de estudo

### Fontes de Dados de Exemplo

**Opção 1: OpenStreetMap (Gratuito)**
```bash
# Usar plugin QuickOSM do QGIS
1. Vetor → QuickOSM → Consulta Rápida
2. Chave: "railway", Valor: "station"
3. Selecionar sua cidade/região
4. Baixar pontos
```

**Opção 2: Dados Abertos Municipais**
- Verifique o portal de dados abertos da sua cidade
- Procure por conjuntos de dados "parcelas", "cadastro" ou "propriedade"
- Dados de transporte geralmente sob "transporte"

### Requisitos do Sistema

- **Backend Recomendado**: PostgreSQL (para 50k+ parcelas)
- **Alternativa**: Spatialite (para <50k parcelas)
- **SRC**: Qualquer (FilterMate lida com reprojeção automaticamente)

---

## Instruções Passo a Passo

### Passo 1: Carregar Seus Dados

1. Abrir QGIS e criar um novo projeto
2. Carregar a camada **parcelas** (arrastar e soltar ou Camada → Adicionar Camada)
3. Carregar a camada **estacoes_transporte**
4. Verificar se ambas as camadas são exibidas corretamente no mapa

:::tip Verificação de SRC
SRCs diferentes? Sem problema! FilterMate reprojeta automaticamente as camadas durante operações espaciais. Você verá um indicador 🔄 quando a reprojeção ocorrer.
:::

---

### Passo 2: Abrir o FilterMate

1. Clicar no ícone **FilterMate** na barra de ferramentas
2. Ou: **Vetor** → **FilterMate**
3. O painel ancorado no lado direito

**O que você deve ver**:
- Três abas: FILTRAGEM / EXPLORAÇÃO / EXPORTAÇÃO
- Seletor de camada no topo
- Construtor de expressões vazio

---

### Passo 3: Configurar o Filtro

#### 3.1 Selecionar Camada Alvo

1. No menu suspenso **Seleção de Camada** (topo do painel)
2. Marcar a camada **parcelas**
3. Observe o indicador de backend (PostgreSQL⚡ / Spatialite / OGR)

**Exibição de Informações da Camada**:
```
Provedor: postgresql (PostgreSQL)
Feições: 125.347
SRC: EPSG:31983 (SIRGAS 2000 / UTM zone 23S)
Chave Primária: gid
```

:::info Performance do Backend
Se você vir "OGR" para grandes conjuntos de dados de parcelas, considere migrar para PostgreSQL para desempenho 10-50× mais rápido. Veja [Guia de Backends](../backends/choosing-backend).
:::

---

#### 3.2 Adicionar Filtro de Atributo (Opcional)

Filtrar apenas parcelas residenciais:

1. Na seção **Construtor de Expressões**
2. Clicar no menu suspenso **Campos** para ver atributos disponíveis
3. Inserir esta expressão:

```sql
uso_solo = 'residencial'
-- OU se usando códigos de zoneamento:
zoneamento LIKE 'R-%'
-- OU múltiplos tipos residenciais:
uso_solo IN ('residencial', 'uso-misto', 'multi-familiar')
```

4. Aguardar a marca de seleção verde (✓) - indica sintaxe válida

**Explicação da Expressão**:
- `uso_solo = 'residencial'` - Correspondência exata no campo de uso do solo
- `LIKE 'R-%'` - Correspondência de padrão para códigos de zoneamento residencial (R-1, R-2, etc.)
- `IN (...)` - Valores múltiplos permitidos

:::tip Sem Campo Residencial?
Se seus dados não têm uso do solo, pule este passo. O filtro espacial funcionará em todas as parcelas.
:::

---

#### 3.3 Configurar Filtro Geométrico

Agora adicione o componente espacial - proximidade ao transporte:

1. **Rolar para baixo** até a seção **Filtro Geométrico**
2. Clicar para expandir se recolhido

**Camada de Referência**:
3. Selecionar **estacoes_transporte** no menu suspenso
4. O ícone da camada de referência aparece: 🚉

**Predicado Espacial**:
5. Selecionar **"Intersecta"** no menu suspenso de predicados
   - (Adicionaremos distância de buffer, então intersecta = "toca o buffer")

**Distância do Buffer**:
6. Inserir `500` no campo de distância
7. Selecionar **metros** como unidade
8. Deixar tipo de buffer como **Redondo (Planar)** para áreas urbanas

**Sua Configuração Deve Parecer**:
```
Camada de Referência: estacoes_transporte
Predicado Espacial: Intersecta
Distância do Buffer: 500 metros
Tipo de Buffer: Redondo (Planar)
```

:::tip Conversão Automática de SRC Geográfico
Se suas camadas usam coordenadas geográficas (EPSG:4326), FilterMate converte automaticamente para EPSG:3857 para buffers métricos precisos. Você verá: indicador 🌍 nos logs.
:::

---

### Passo 4: Aplicar o Filtro

1. Clicar no botão **Aplicar Filtro** (botão grande na parte inferior)
2. FilterMate executa a consulta espacial

**O Que Acontece**:

<Tabs>
  <TabItem value="postgresql" label="Backend PostgreSQL" default>
    ```sql
    -- Cria vista materializada otimizada
    CREATE MATERIALIZED VIEW temp_filter AS
    SELECT p.*
    FROM parcelas p
    WHERE p.uso_solo = 'residencial'
      AND EXISTS (
        SELECT 1 FROM estacoes_transporte s
        WHERE ST_DWithin(
          p.geom::geography,
          s.geom::geography,
          500
        )
      );
    
    CREATE INDEX idx_temp_geom 
      ON temp_filter USING GIST(geom);
    ```
    ⚡ **Performance**: 0,3-2 segundos para 100k+ parcelas
  </TabItem>
  
  <TabItem value="spatialite" label="Backend Spatialite">
    ```sql
    -- Cria tabela temporária com índice espacial
    CREATE TEMP TABLE temp_filter AS
    SELECT p.*
    FROM parcelas p
    WHERE p.uso_solo = 'residencial'
      AND EXISTS (
        SELECT 1 FROM estacoes_transporte s
        WHERE ST_Distance(p.geom, s.geom) <= 500
      );
    
    SELECT CreateSpatialIndex('temp_filter', 'geom');
    ```
    ⏱️ **Performance**: 5-15 segundos para 50k parcelas
  </TabItem>
  
  <TabItem value="ogr" label="Backend OGR">
    Usa framework QGIS Processing com camadas de memória.
    
    🐌 **Performance**: 30-120 segundos para grandes conjuntos de dados
    
    **Recomendação**: Migrar para PostgreSQL para este fluxo de trabalho.
  </TabItem>
</Tabs>

---

### Passo 5: Revisar Resultados

**Vista do Mapa**:
- Parcelas filtradas são destacadas no mapa
- Parcelas não correspondentes são ocultadas (ou acinzentadas)
- Contagem exibida no painel FilterMate: `Encontrado: 3.247 feições`

**Verificar Resultados**:
1. Aproximar em uma estação de transporte
2. Selecionar uma parcela filtrada
3. Usar **Ferramenta de Medida** para verificar que está dentro de 500m da estação

**Resultados Esperados**:
- Centros urbanos: Alta densidade de parcelas filtradas
- Áreas suburbanas: Parcelas esparsas perto de estações
- Áreas rurais: Muito poucas ou nenhum resultado

---

### Passo 6: Analisar e Exportar

#### Opção A: Estatísticas Rápidas

1. Clique direito na camada filtrada
2. **Propriedades** → **Informação**
3. Ver contagem de feições e extensão

#### Opção B: Exportar para Relatório

1. Mudar para aba **EXPORTAÇÃO** no FilterMate
2. Selecionar camada de parcelas filtradas
3. Escolher formato de saída:
   - **GeoPackage (.gpkg)** - Melhor para QGIS
   - **GeoJSON** - Para mapeamento web
   - **Shapefile** - Para sistemas legados
   - **PostGIS** - De volta para banco de dados

4. **Opcional**: Transformar SRC (ex: WGS84 para web)
5. Clicar em **Exportar**

**Exemplo de Configurações de Exportação**:
```
Camada: parcelas (filtrado)
Formato: GeoPackage
SRC de Saída: EPSG:4326 (WGS84)
Nome do arquivo: parcelas_acessiveis_transporte.gpkg
```

---

## Entendendo os Resultados

### Interpretar Contagens de Feições

**Resultados de Exemplo**:
```
Total de parcelas: 125.347
Parcelas residenciais: 87.420 (70%)
Residencial acessível por transporte: 3.247 (3,7% do residencial)
```

**O Que Isso Significa**:
- Apenas 3,7% das parcelas residenciais são acessíveis por transporte
- Oportunidade para desenvolvimento orientado ao transporte
- A maioria dos residentes depende de carros (preocupação de equidade)

### Padrões Espaciais

**Procurar**:
- **Clusters** em torno de grandes hubs de transporte → Zonas de alta densidade
- **Lacunas** entre estações → Desenvolvimento de preenchimento potencial
- **Parcelas isoladas** → Desertos de transporte necessitando expansão de serviço

---

## Melhores Práticas

### Otimização de Performance

✅ **Usar PostgreSQL** para conjuntos de dados de parcelas >50k feições
- 10-50× mais rápido que backend OGR
- Tempos de consulta sub-segundo mesmo em 500k+ parcelas

✅ **Filtrar por atributo primeiro** se possível
- `uso_solo = 'residencial'` reduz escopo da consulta espacial
- Melhoria de performance de 30-50%

✅ **Unidades de Distância do Buffer**
- Usar **metros** para análise urbana (consistente mundialmente)
- Evitar **graus** para consultas baseadas em distância (impreciso)

### Considerações de Precisão

⚠️ **Seleção do Tipo de Buffer**:
- **Redondo (Planar)**: Rápido, preciso para áreas pequenas (<10km)
- **Redondo (Geodésico)**: Mais preciso para grandes regiões
- **Quadrado**: Otimização computacional (raramente necessário)

⚠️ **Escolha do SRC**:
- SRC projetado local (ex: SIRGAS, UTM) - Melhor precisão
- Web Mercator (EPSG:3857) - Bom para análise mundial
- WGS84 (EPSG:4326) - Auto-convertido pelo FilterMate ✓

### Qualidade dos Dados

🔍 **Verificar**:
- **Parcelas sobrepostas** - Pode inflar contagens
- **Geometrias ausentes** - Usar ferramenta "Verificar Geometrias"
- **Dados de transporte desatualizados** - Verificar status operacional das estações

---

## Problemas Comuns e Soluções

### Problema 1: Nenhum Resultado Encontrado

**Sintomas**: Filtro retorna 0 feições, mas você espera correspondências.

**Causas Possíveis**:
1. ❌ Distância do buffer muito pequena (tentar 1000m)
2. ❌ Valor de atributo errado (verificar valores do campo `uso_solo`)
3. ❌ Camadas não se sobrepõem geograficamente
4. ❌ Incompatibilidade de SRC (embora FilterMate lide com isso)

**Passos de Depuração**:
```sql
-- Teste 1: Remover filtro de atributo
-- Apenas executar consulta espacial em todas as parcelas

-- Teste 2: Aumentar distância do buffer
-- Tentar 1000 ou 2000 metros

-- Teste 3: Inverter consulta
-- Filtrar estações dentro de parcelas (sempre deve retornar resultados)
```

---

### Problema 2: Performance Lenta (>30 segundos)

**Causa**: Grande conjunto de dados com backend OGR.

**Soluções**:
1. ✅ Instalar PostgreSQL + PostGIS
2. ✅ Carregar dados no banco PostgreSQL
3. ✅ Usar camada PostgreSQL no QGIS
4. ✅ Re-executar filtro (esperar aceleração de 10-50×)

**Configuração Rápida PostgreSQL**:
```bash
# Instalar psycopg2 para Python do QGIS
pip install psycopg2-binary

# Ou no OSGeo4W Shell (Windows):
py3_env
pip install psycopg2-binary
```

---

### Problema 3: Resultados Parecem Errados

**Sintomas**: Parcelas longe de estações são incluídas.

**Causas Possíveis**:
1. ❌ Distância do buffer em unidades erradas (graus em vez de metros)
2. ❌ Predicado "Contém" em vez de "Intersecta"
3. ❌ Camada de referência está errada (estradas em vez de estações)

**Verificação**:
1. Usar **Ferramenta de Medida** do QGIS
2. Medir distância da parcela filtrada à estação mais próxima
3. Deve ser ≤ 500 metros

---

## Próximos Passos

### Fluxos de Trabalho Relacionados

- **[Cobertura de Serviços de Emergência](./emergency-services)** - Análise de distância similar
- **[Zonas de Proteção Ambiental](./environmental-protection)** - Filtragem multi-critérios
- **[Análise Imobiliária](./real-estate-analysis)** - Filtragem de atributos combinados

### Técnicas Avançadas

**Buffers Graduados**:
Executar múltiplos filtros com diferentes distâncias (250m, 500m, 1000m) para criar zonas de caminhabilidade.

**Combinar com Demografia**:
Unir dados de censo para estimar população acessível por transporte.

**Análise Temporal**:
Usar dados históricos para rastrear desenvolvimento orientado ao transporte ao longo do tempo.

---

## Resumo

**Você Aprendeu**:
- ✅ Filtragem combinada de atributos e geométrica
- ✅ Operações de buffer com parâmetros de distância
- ✅ Seleção de predicado espacial (Intersecta)
- ✅ Otimização de performance do backend
- ✅ Exportação de resultados e transformação de SRC

**Principais Conclusões**:
- FilterMate lida com reprojeção de SRC automaticamente
- Backend PostgreSQL fornece melhor performance para grandes conjuntos de dados
- 500m é "distância de caminhada" típica para planejamento urbano
- Sempre verificar resultados com amostragem de medição manual

**Tempo Economizado**:
- Seleção manual: ~2 horas
- Caixa de Ferramentas de Processamento (multi-etapas): ~20 minutos
- Fluxo de trabalho FilterMate: ~10 minutos ⚡

---

Precisa de ajuda? Confira o [Guia de Solução de Problemas](../advanced/troubleshooting) ou pergunte em [Discussões do GitHub](https://github.com/sducournau/filter_mate/discussions).
