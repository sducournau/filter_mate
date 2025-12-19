---
sidebar_position: 5
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Análise Imobiliária: Filtragem de Mercado

Filtrar propriedades residenciais por preço, tamanho e proximidade a escolas para identificar oportunidades ótimas de investimento.

## Visão Geral do Cenário

**Objetivo**: Encontrar casas unifamiliares entre $200k-$400k, >150m², dentro de 1km de escolas bem avaliadas.

**Aplicação do Mundo Real**:
- Investidores imobiliários encontrando propriedades que correspondem aos critérios
- Compradores de casa procurando bairros adequados para famílias
- Agentes imobiliários fornecendo recomendações baseadas em dados
- Analistas de mercado avaliando valores de propriedades vs. comodidades

**Tempo Estimado**: 8 minutos

**Dificuldade**: ⭐ Iniciante

---

## Pré-requisitos

### Dados Necessários

1. **Camada de Propriedades Residenciais** (pontos ou polígonos)
   - Listagens de propriedades ou dados de parcelas
   - Atributos necessários:
     - `preco` (numérico)
     - `area_m2` ou `area_habitavel` (numérico)
     - `tipo_propriedade` (texto: 'casa_unifamiliar', 'apartamento', etc.)
   - Opcional: `quartos`, `banheiros`, `ano_construcao`

2. **Camada de Escolas** (pontos)
   - Localizações de escolas
   - Opcional mas útil: `avaliacao`, `nivel_escolar`, `nome`
   - Cobre sua área de estudo

### Fontes de Dados de Exemplo

**Dados Imobiliários**:
- Exportações MLS (Multiple Listing Service)
- Feeds de dados Zillow/Trulia (se disponíveis)
- Bancos de dados de avaliação de propriedades municipais
- Edifícios OpenStreetMap com tags

**Dados de Escolas**:
```python
# Plugin QuickOSM do QGIS
Chave: "amenity", Valor: "school"
Chave: "school", Valor: "*"

# Ou dados governamentais:
- National Center for Education Statistics (EUA)
- Ministério da Educação
- Bancos de dados de autoridades educacionais locais
```

### Recomendação de Backend

**Comparação Multi-Backend** - Este fluxo de trabalho demonstra os três:
- **PostgreSQL**: Mais rápido se você tem >10k propriedades
- **Spatialite**: Bom meio-termo para dados em escala de cidade
- **OGR**: Funciona em todos os lugares, desempenho aceitável para <5k propriedades

---

## Instruções Passo a Passo

### Passo 1: Carregar e Inspecionar Dados de Propriedades

1. **Carregar camada de propriedades**: `propriedades_residenciais.gpkg`
2. **Abrir Tabela de Atributos** (F6)
3. **Verificar se campos necessários existem**:
   ```
   ✓ preco (numérico)
   ✓ area_m2 (numérico)
   ✓ tipo_propriedade (texto)
   ```

4. **Verificar qualidade dos dados**:
   ```
   Ordenar por preço: Procurar valores irrealistas (0, NULL, >$10M)
   Ordenar por área: Verificar valores 0 ou NULL
   Filtrar tipo_propriedade: Identificar categorias válidas
   ```

:::tip Limpeza de Dados
Se você tem valores faltando:
```sql
-- Filtrar PRIMEIRO registros incompletos
"preco" IS NOT NULL 
AND "area_m2" > 0 
AND "tipo_propriedade" IS NOT NULL
```
:::

### Passo 2: Aplicar Filtros Básicos de Atributos

**Usando FilterMate**:

1. Abrir painel FilterMate
2. Selecionar camada **propriedades_residenciais**
3. Escolher **qualquer backend** (filtragem de atributos funciona igualmente em todos)
4. Inserir expressão:

<Tabs>
  <TabItem value="basic" label="Filtro Básico" default>
    ```sql
    -- Preço entre $200k e $400k
    -- Área maior que 150m²
    -- Casas unifamiliares apenas
    
    "preco" >= 200000 
    AND "preco" <= 400000
    AND "area_m2" >= 150
    AND "tipo_propriedade" = 'casa_unifamiliar'
    ```
  </TabItem>
  
  <TabItem value="advanced" label="Avançado (Tipos Múltiplos)">
    ```sql
    -- Aceitar múltiplos tipos de propriedades
    "preco" BETWEEN 200000 AND 400000
    AND "area_m2" >= 150
    AND "tipo_propriedade" IN ('casa_unifamiliar', 'sobrado')
    AND "quartos" >= 3
    ```
  </TabItem>
  
  <TabItem value="deals" label="Focado em Investimento">
    ```sql
    -- Encontrar propriedades subvalorizadas (preço por m²)
    "preco" BETWEEN 200000 AND 400000
    AND "area_m2" >= 150
    AND "tipo_propriedade" = 'casa_unifamiliar'
    AND ("preco" / "area_m2") < 2000  -- Menos de $2000/m²
    ```
  </TabItem>
</Tabs>

5. Clicar em **Aplicar Filtro**
6. Revisar contagem: "Mostrando X de Y feições"

**Resultado Esperado**: Propriedades filtradas por preço, tamanho e tipo

### Passo 3: Adicionar Filtro Espacial para Proximidade de Escolas

Agora adicionar o critério **baseado em localização**:

1. **Garantir que camada de escolas está carregada**: `escolas.gpkg`
2. **Modificar expressão FilterMate** para adicionar componente espacial:

<Tabs>
  <TabItem value="ogr" label="OGR / Spatialite" default>
    ```sql
    -- Combinar filtros de atributos + proximidade espacial
    "preco" >= 200000 
    AND "preco" <= 400000
    AND "area_m2" >= 150
    AND "tipo_propriedade" = 'casa_unifamiliar'
    AND distance(
      $geometry,
      aggregate(
        layer:='escolas',
        aggregate:='collect',
        expression:=$geometry
      )
    ) <= 1000
    ```
    
    **Alternativa usando funções overlay**:
    ```sql
    -- Mesmos critérios + verificar se existe alguma escola dentro de 1km
    "preco" BETWEEN 200000 AND 400000
    AND "area_m2" >= 150
    AND "tipo_propriedade" = 'casa_unifamiliar'
    AND array_length(
      overlay_within(
        'escolas',
        buffer($geometry, 1000)
      )
    ) > 0
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL">
    ```sql
    -- Usando funções espaciais PostGIS
    preco >= 200000 
    AND preco <= 400000
    AND area_m2 >= 150
    AND tipo_propriedade = 'casa_unifamiliar'
    AND EXISTS (
      SELECT 1 
      FROM escolas e
      WHERE ST_DWithin(
        propriedades.geom,
        e.geom,
        1000  -- 1km em metros
      )
    )
    ```
    
    **Ou com cálculo de distância**:
    ```sql
    -- Incluir distância à escola mais próxima como saída
    SELECT 
      p.*,
      MIN(ST_Distance(p.geom, e.geom)) AS distancia_escola
    FROM propriedades p
    JOIN escolas e ON ST_DWithin(p.geom, e.geom, 1000)
    WHERE preco BETWEEN 200000 AND 400000
      AND area_m2 >= 150
      AND tipo_propriedade = 'casa_unifamiliar'
    GROUP BY p.id_propriedade
    ```
  </TabItem>
</Tabs>

3. Clicar em **Aplicar Filtro**
4. Revisar resultados no mapa (devem estar concentrados perto de escolas)

### Passo 4: Refinar por Qualidade da Escola (Opcional)

Se sua camada de escolas tem dados de avaliação:

```sql
-- Apenas propriedades perto de escolas bem avaliadas (avaliação ≥ 8/10)
"preco" BETWEEN 200000 AND 400000
AND "area_m2" >= 150
AND "tipo_propriedade" = 'casa_unifamiliar'
AND array_max(
  array_foreach(
    overlay_within('escolas', buffer($geometry, 1000)),
    attribute(@element, 'avaliacao')
  )
) >= 8
```

**O que isso faz**:
1. Encontra todas as escolas dentro de buffer de 1km
2. Obtém seus valores de avaliação
3. Mantém propriedades onde pelo menos uma escola próxima tem avaliação ≥8

### Passo 5: Calcular Distância à Escola Mais Próxima

Adicionar campo mostrando distância exata:

1. **Abrir Calculadora de Campo** (Ctrl+I) na camada filtrada
2. Criar novo campo:
   ```
   Nome do campo: escola_proxima_m
   Tipo de campo: Decimal (double)
   Precisão: 1
   
   Expressão:
   round(
     array_min(
       array_foreach(
         overlay_nearest('escolas', $geometry, limit:=1),
         distance(geometry(@element), $geometry)
       )
     ),
     0
   )
   ```

3. **Adicionar nome da escola** (opcional):
   ```
   Nome do campo: nome_escola_proxima
   Tipo de campo: Texto (string)
   
   Expressão:
   attribute(
     overlay_nearest('escolas', $geometry, limit:=1)[0],
     'nome'
   )
   ```

### Passo 6: Classificar Propriedades por Valor

Criar uma **pontuação de valor** combinando múltiplos fatores:

1. **Abrir Calculadora de Campo**
2. Criar campo calculado:
   ```
   Nome do campo: pontuacao_valor
   Tipo de campo: Decimal (double)
   
   Expressão:
   -- Pontuação maior = melhor valor
   -- Fatores ponderados:
   (400000 - "preco") / 1000 * 0.4 +          -- Preço menor = melhor (40% peso)
   ("area_m2" - 150) * 0.3 +                  -- Área maior = melhor (30% peso)
   (1000 - "escola_proxima_m") * 0.3          -- Escola mais próxima = melhor (30% peso)
   ```

3. **Ordenar por pontuacao_valor** decrescente para ver melhores negócios primeiro

### Passo 7: Visualizar Resultados

**Colorir por Distância à Escola**:

1. Clique direito na camada → **Simbologia**
2. Escolher **Graduado**
3. Valor: `escola_proxima_m`
4. Método: Quebras Naturais
5. Cores: Verde (perto) → Amarelo → Vermelho (longe)

**Adicionar Rótulos**:
```
Rotular com: concat('$', "preco"/1000, 'k - ', round("escola_proxima_m",0), 'm escola')
Tamanho: 10pt
Buffer: Branco, 1mm
```

### Passo 8: Exportar Correspondências para Análise

1. **No FilterMate**: Clicar em **Exportar Feições Filtradas**
   ```
   Formato: GeoPackage
   Nome do arquivo: propriedades_alvos_investimento.gpkg
   SRC: WGS84 (para portabilidade)
   Incluir todos os atributos: ✓
   ```

2. **Exportar tabela de atributos como planilha**:
   ```
   Clique direito na camada → Exportar → Salvar Feições Como
   Formato: CSV ou XLSX
   Campos: Selecionar apenas colunas relevantes
   ```

3. **Criar relatório simples** (opcional):
   ```python
   # Console Python
   layer = iface.activeLayer()
   features = list(layer.getFeatures())
   
   print("=== Relatório de Investimento Imobiliário ===")
   print(f"Propriedades correspondentes: {len(features)}")
   print(f"Preço médio: ${sum(f['preco'] for f in features)/len(features):,.0f}")
   print(f"Área média: {sum(f['area_m2'] for f in features)/len(features):.0f} m²")
   print(f"Distância média à escola: {sum(f['escola_proxima_m'] for f in features)/len(features):.0f} m")
   print(f"Faixa de preço: ${min(f['preco'] for f in features):,} - ${max(f['preco'] for f in features):,}")
   ```

---

## Entendendo os Resultados

### O Que o Filtro Mostra

✅ **Propriedades selecionadas**: Correspondem a TODOS os critérios:
- Preço: $200.000 - $400.000
- Tamanho: ≥150m²
- Tipo: Casa unifamiliar
- Localização: ≤1km de escola

❌ **Propriedades excluídas**: Falham em QUALQUER critério acima

### Interpretando Correspondências de Propriedades

**Alta Pontuação de Valor** (>500):
- Preço abaixo do mercado para a área
- Bom tamanho para faixa de preço
- Muito próximo de escola (apelo familiar)
- **Ação**: Visita/oferta prioritária

**Pontuação Média** (250-500):
- Valor justo de mercado
- Localização aceitável
- Considerar outros fatores (condição, bairro)
- **Ação**: Comparar com propriedades similares

**Pontuação Baixa** (<250):
- Pode estar supervalorizada
- Extremidade distante de proximidade de escola
- Tamanho menor para preço
- **Ação**: Negociar ou esperar melhores opções

### Verificações de Qualidade

1. **Verificação de sanidade**: Ver 5-10 resultados aleatórios
   - Verificar se preços são realistas
   - Medir distância de escola manualmente
   - Verificar se tipo_propriedade corresponde às expectativas

2. **Detecção de outliers**:
   ```sql
   -- Encontrar propriedades anormalmente baratas (podem ser erros ou ótimos negócios)
   "preco" / "area_m2" < 1500  -- Menos de $1500/m²
   ```

3. **Padrões no mapa**: Resultados devem se agrupar perto de escolas (se não, verificar SRC)

---

## Melhores Práticas

### Refinamento de Estratégia de Busca

**Começar Amplo, Estreitar Gradualmente**:

1. **Primeira passagem**: Aplicar apenas filtros de preço + tamanho
2. **Revisar contagem**: Se >100 resultados, adicionar filtro tipo_propriedade
3. **Adicionar espacial**: Aplicar proximidade de escola
4. **Ajuste fino**: Adicionar avaliação de escola, quartos, etc.

**Salvar Histórico de Filtro**:
- FilterMate salva automaticamente suas expressões
- Usar painel **Histórico de Filtro** para comparar diferentes conjuntos de critérios
- Salvar melhores filtros como **Favoritos**

### Considerações de Performance

**Guia de Seleção de Backend**:

```
Propriedades | Escolas | Backend Recomendado
-------------|---------|--------------------
< 1.000      | Qualquer| OGR (mais simples)
1k - 10k     | < 100   | Spatialite
> 10k        | Qualquer| PostgreSQL
Qualquer     | > 500   | PostgreSQL + índice espacial
```

**Dicas de Otimização**:

1. **Aplicar filtros de atributos primeiro** (mais barato):
   ```sql
   -- Bom: Atributos primeiro, espacial por último
   "preco" BETWEEN 200000 AND 400000 AND distance(...) <= 1000
   
   -- Ruim: Espacial primeiro (mais lento)
   distance(...) <= 1000 AND "preco" BETWEEN 200000 AND 400000
   ```

2. **Usar índice espacial** (automático no PostgreSQL, criar manualmente para Spatialite):
   ```
   Propriedades da Camada → Criar Índice Espacial
   ```

3. **Simplificar geometria de escolas** se complexa:
   ```
   Vetor → Geometria → Centroides (escolas → pontos)
   ```

### Melhores Práticas Imobiliárias

**Análise de Mercado**:
- Executar este filtro semanalmente para rastrear novas listagens
- Comparar tendências de pontuacao_valor ao longo do tempo
- Exportar resultados com timestamps para análise histórica

**Ajuste de Preço**:
```sql
-- Ajustar para inflação ou mudanças de mercado
"preco" * 1.05 BETWEEN 200000 AND 400000  -- +5% crescimento de mercado
```

**Padrões Sazonais**:
```sql
-- Proximidade de escola mais valiosa na primavera (temporada de mudança familiar)
-- Ajustar peso no cálculo de pontuacao_valor
```

---

## Problemas Comuns

### Problema 1: Nenhum resultado ou muito poucos resultados

**Causa**: Critérios muito rígidos ou problemas de qualidade de dados

**Soluções**:
```
1. Relaxar faixa de preço: 150k-500k em vez de 200k-400k
2. Reduzir área mínima: 120m² em vez de 150m²
3. Aumentar distância de escola: 2000m em vez de 1000m
4. Verificar valores NULL em atributos
5. Verificar se camada de escolas cobre mesma área que propriedades
```

### Problema 2: Cálculo de distância retorna erros

**Causa**: Incompatibilidade de SRC ou camada não encontrada

**Solução**:
```
1. Verificar se nome da camada de escolas corresponde exatamente (sensível a maiúsculas)
2. Verificar se ambas as camadas usam mesmo SRC (reprojetar se necessário)
3. Garantir que camada de escolas está no projeto atual
4. Tentar abordagem aggregate mais simples:
   
   distance(
     $geometry,
     aggregate('escolas', 'collect', $geometry)
   ) <= 1000
```

### Problema 3: Performance lenta (>30 segundos)

**Causa**: Grande conjunto de dados ou consulta espacial complexa

**Soluções**:
```
1. Mudar para backend PostgreSQL (aceleração importante)
2. Criar índice espacial em ambas as camadas
3. Pré-filtrar propriedades para região menor:
   "cidade" = 'São Paulo' AND [resto da expressão]
4. Reduzir complexidade da consulta de escola:
   - Usar buffer uma vez: overlay_within('escolas', buffer($geometry, 1000))
   - Cache em campo temporário
```

### Problema 4: Resultados não estão perto de escolas visualmente

**Causa**: SRC usando graus em vez de metros

**Solução**:
```
1. Verificar SRC da camada: Propriedades → Informação
2. Se EPSG:4326 (lat/lon), reprojetar para UTM local:
   Vetor → Gerenciamento de Dados → Reprojetar Camada
3. Atualizar distância de 1000 para 0.01 se usando graus (não recomendado)
```

---

## Próximos Passos

### Fluxos de Trabalho Relacionados

- **[Planejamento Urbano Transporte](./urban-planning-transit)**: Análise de proximidade similar
- **[Serviços de Emergência](./emergency-services)**: Consultas de distância inversa
- **[Planejamento de Transporte](./transportation-planning)**: Tratamento de exportação e SRC

### Técnicas Avançadas

**1. Pontuação Multi-Comodidades** (escolas + parques + comércio):
```sql
-- Propriedades perto de múltiplas comodidades
array_length(overlay_within('escolas', buffer($geometry, 1000))) > 0
AND array_length(overlay_within('parques', buffer($geometry, 500))) > 0
AND array_length(overlay_within('comercios', buffer($geometry, 800))) > 0
```

**2. Potencial de Valorização** (combinar demografia):
```sql
-- Áreas com demografia melhorando
"renda_mediana_2023" > "renda_mediana_2020" * 1.1  -- 10% crescimento de renda
AND distance(centroide, aggregate('novos_desenvolvimentos', 'collect', $geometry)) < 2000
```

**3. Análise de Tempo de Deslocamento** (requer rede viária):
```
Processamento → Análise de Rede → Área de Serviço
Origem: Propriedades
Destino: Centros de emprego
Limite de tempo: 30 minutos
```

**4. Comparação de Mercado** (preço por m² por bairro):
```sql
-- Encontrar propriedades abaixo da média do bairro
"preco" / "area_m2" < 
  aggregate(
    layer:='todas_propriedades',
    aggregate:='avg',
    expression:="preco"/"area_m2",
    filter:="bairro" = attribute(@parent, 'bairro')
  ) * 0.9  -- 10% abaixo da média
```

**5. Rastreamento de Série Temporal** (monitorar duração de listagem):
```sql
-- Propriedades no mercado >30 dias (vendedores motivados)
"dias_mercado" > 30
AND "preco_reduzido" = 1
```

### Aprendizado Adicional

- 📖 [Referência de Predicados Espaciais](../reference/cheat-sheets/spatial-predicates)
- 📖 [Fundamentos de Filtragem](../user-guide/filtering-basics)
- 📖 [Histórico de Filtro & Favoritos](../user-guide/filter-history)
- 📖 [Mergulho Profundo na Calculadora de Campo](https://docs.qgis.org/latest/pt_BR/docs/user_manual/working_with_vector/attribute_table.html#using-the-field-calculator)

---

## Resumo

✅ **Você aprendeu**:
- Combinar filtros de atributos e espaciais
- Cálculos de distância a feições mais próximas
- Criar pontuações de valor a partir de múltiplos critérios
- Exportar resultados filtrados para análise
- Gerenciar histórico de filtro para diferentes buscas

✅ **Técnicas chave**:
- Operador `BETWEEN` para filtragem por faixa
- Função `distance()` para proximidade
- `overlay_within()` para relações espaciais
- Calculadora de campo para atributos derivados
- Comparação multi-backend

🎯 **Impacto real**: Este fluxo de trabalho ajuda profissionais imobiliários a tomar decisões baseadas em dados, investidores a identificar oportunidades rapidamente, e compradores a encontrar propriedades correspondendo a critérios complexos que levariam dias para pesquisar manualmente.

💡 **Dica profissional**: Salve múltiplas variações de filtro como **Favoritos** com nomes descritivos como "Investimento: Casas Familiares Perto Escolas" ou "Orçamento: Casas Iniciantes Acesso Transporte" para recriar instantaneamente buscas.
