---
sidebar_position: 3
---

# Seu Primeiro Filtro

Este tutorial orienta você na criação de seu primeiro filtro com FilterMate, do início ao fim.

## Cenário

**Objetivo**: Encontrar todos os edifícios dentro de 200 metros de uma estrada principal.

**Dados Necessários**:
- Uma camada de **edifícios** (polígonos)
- Uma camada de **estradas** (linhas)

## Tutorial Passo a Passo

### 1. Carregue Seus Dados

Primeiro, carregue ambas as camadas no QGIS:

1. Abra o QGIS
2. Carregue a camada de **edifícios** (a camada que vamos filtrar)
3. Carregue a camada de **estradas** (a camada de referência)

:::info Dados de Exemplo
Se você não tem dados de exemplo, pode usar dados do OpenStreetMap:
- Baixe do [Geofabrik](https://download.geofabrik.de/)
- Ou use o plugin **QuickOSM** do QGIS para buscar dados
:::

### 2. Abra o FilterMate

1. Clique no ícone **FilterMate** na barra de ferramentas
2. Ou vá em **Complementos** → **FilterMate**
3. O painel encaixável aparece no lado direito

<!-- ![Configuração do Primeiro Filtro](/img/first-filter-1.png -->
*Painel FilterMate pronto para seu primeiro filtro geométrico*

### 3. Selecione a Camada Alvo

1. No menu suspenso **Seleção de Camada** no topo
2. Selecione **edifícios** (a camada que queremos filtrar)

O FilterMate analisará a camada e exibirá:
- Backend sendo usado (PostgreSQL, Spatialite ou OGR)
- Contagem de feições
- Campos disponíveis

### 4. Configure o Filtro Geométrico

Agora vamos criar um filtro espacial para encontrar edifícios perto de estradas:

1. **Vá para a aba Filtro Geométrico**
   - Clique na aba **Filtro Geométrico** no painel

2. **Selecione a Camada de Referência**
   - Escolha **estradas** no menu suspenso da camada de referência

3. **Escolha o Predicado Espacial**
   - Selecione **"dentro da distância"** ou **"intersecta"** (se usar buffer)

4. **Defina a Distância do Buffer**
   - Digite **200** no campo de distância do buffer
   - Unidades: **metros** (ou unidades do SRC da sua camada)

:::tip Reprojeção de SRC
O FilterMate reprojeta automaticamente as camadas se elas tiverem SRC diferentes. Não é necessária reprojeção manual!
:::

### 5. Aplique o Filtro

1. Clique no botão **Aplicar Filtro**
2. O FilterMate irá:
   - Criar uma visualização filtrada temporária
   - Destacar feições correspondentes no mapa
   - Atualizar a contagem de feições no painel

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

**O que acontece nos bastidores:**

<Tabs>
  <TabItem value="postgresql" label="Backend PostgreSQL" default>
    ```sql
    -- Cria uma visão materializada com índice espacial
    CREATE MATERIALIZED VIEW temp_filter AS
    SELECT b.*
    FROM buildings b
    JOIN roads r ON ST_DWithin(b.geom, r.geom, 200);
    
    CREATE INDEX idx_temp_geom ON temp_filter USING GIST(geom);
    ```
    ⚡ **Ultra-rápido** (menos de um segundo em 100k+ feições)
  </TabItem>
  <TabItem value="spatialite" label="Backend Spatialite">
    ```sql
    -- Cria tabela temporária com índice R-tree
    CREATE TEMP TABLE filtered_buildings AS
    SELECT b.*
    FROM buildings b
    JOIN roads r ON ST_Distance(b.geom, r.geom) <= 200;
    
    -- Usa índice espacial R-tree
    SELECT CreateSpatialIndex('filtered_buildings', 'geom');
    ```
    ✅ **Rápido** (~2-10s em 50k feições)
  </TabItem>
  <TabItem value="ogr" label="Backend OGR">
    ```python
    # Usa framework de processamento do QGIS
    processing.run("native:buffer", {
        'INPUT': roads,
        'DISTANCE': 200,
        'OUTPUT': 'memory:'
    })
    
    processing.run("native:selectbylocation", {
        'INPUT': buildings,
        'INTERSECT': buffered_roads,
        'METHOD': 0
    })
    ```
    ⚠️ **Mais lento** (~10-30s em 50k feições)
  </TabItem>
</Tabs>

### 6. Revise os Resultados

Após a filtragem:

- **Tela do Mapa**: Edifícios filtrados são destacados
- **Painel**: Mostra contagem de feições filtradas
- **Tabela de Atributos**: Abra para ver as feições filtradas

:::tip Zoom nos Resultados
Clique com botão direito na camada → **Zoom para Camada** para ver todas as feições filtradas
:::

### 7. Refine o Filtro (Opcional)

Quer adicionar critérios de atributo? Combine com um filtro de atributo:

1. Vá para a aba **Filtro de Atributo**
2. Adicione uma expressão como:
   ```
   "building_type" = 'residential'
   ```
3. Clique em **Aplicar Filtro**

Agora você tem edifícios que são:
- ✅ Dentro de 200m de estradas
- ✅ E são edifícios residenciais

### 8. Exporte os Resultados (Opcional)

Para salvar os edifícios filtrados:

1. Vá para a aba **Exportar**
2. Escolha o formato de saída:
   - **GeoPackage** (recomendado para fluxos modernos)
   - **Shapefile** (para compatibilidade)
   - **PostGIS** (para salvar no banco de dados)
3. Configure as opções:
   - SRC de saída (padrão: mesmo da fonte)
   - Local de saída
4. Clique em **Exportar**

## O Que Você Aprendeu

✅ Como abrir o FilterMate e selecionar uma camada  
✅ Como criar um filtro geométrico com buffer  
✅ Entender a seleção de backend (automática)  
✅ Como combinar filtros de atributo e geométricos  
✅ Como exportar resultados filtrados  

## Próximos Passos

Agora que você criou seu primeiro filtro, explore mais:

- **[Fundamentos de Filtragem](../user-guide/filtering-basics)** - Aprenda expressões QGIS
- **[Filtragem Geométrica](../user-guide/geometric-filtering)** - Predicados espaciais avançados
- **[Operações de Buffer](../user-guide/buffer-operations)** - Diferentes tipos de buffer
- **[Exportar Feições](../user-guide/export-features)** - Opções avançadas de exportação

## Problemas Comuns

### Nenhuma feição retornada?

Verifique:
- ✅ A distância do buffer é apropriada para seu SRC (metros vs. graus)
- ✅ As camadas têm extensões sobrepostas
- ✅ A camada de referência tem feições

### O filtro está lento?

Para grandes conjuntos de dados:
- Instale o backend PostgreSQL para aceleração de 10-50×
- Veja [Ajuste de Desempenho](../advanced/performance-tuning)

### SRC errado?

O FilterMate reprojeta automaticamente, mas você pode verificar:
1. Propriedades da camada → aba SRC
2. Certifique-se de que ambas as camadas têm SRC válido definido
3. O FilterMate cuida do resto!
