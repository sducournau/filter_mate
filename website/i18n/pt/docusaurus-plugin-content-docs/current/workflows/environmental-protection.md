---
sidebar_position: 3
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Análise Ambiental: Impacto de Zona Protegida

Encontrar instalações industriais dentro de zonas de buffer de água protegidas para avaliar conformidade e riscos ambientais.

## Visão Geral do Cenário

**Objetivo**: Identificar instalações industriais que se enquadram em zonas de buffer de 1km ao redor de corpos d'água protegidos para avaliar impacto ambiental.

**Aplicação do Mundo Real**:
- Agências ambientais monitorando conformidade
- ONGs avaliando riscos de poluição industrial
- Formuladores de políticas criando regulamentações de zona de buffer
- Planejadores urbanos gerenciando zoneamento industrial

**Tempo Estimado**: 15 minutos

**Dificuldade**: ⭐⭐⭐ Avançado

---

## Pré-requisitos

### Dados Necessários

1. **Camada de Locais Industriais** (pontos ou polígonos)
   - Localizações de instalações industriais
   - Deve incluir tipo/classificação da instalação
   - Mínimo 50+ locais para análise significativa

2. **Camada de Corpos d'Água** (polígonos)
   - Rios, lagos, pântanos, reservatórios
   - Atributo de status protegido (opcional mas útil)
   - Cobre sua área de estudo

3. **Zonas Protegidas** (opcional)
   - Zonas de proteção ambiental existentes
   - Limites de buffer regulatórios

### Fontes de Dados de Exemplo

**Opção 1: OpenStreetMap**
```python
# Usar plugin QuickOSM do QGIS
# Para corpos d'água:
Chave: "natural", Valor: "water"
Chave: "waterway", Valor: "river"

# Para locais industriais:
Chave: "landuse", Valor: "industrial"
Chave: "industrial", Valor: "*"
```

**Opção 2: Dados Governamentais**
- Bancos de dados da Agência de Proteção Ambiental (EPA)
- Bancos de dados nacionais de qualidade da água
- Registros de instalações industriais
- Limites de áreas protegidas (WDPA)

### Recomendação de Backend

**Spatialite** - Melhor escolha para este fluxo de trabalho:
- Bom desempenho para conjuntos de dados regionais (tipicamente <100k feições)
- Operações de buffer robustas
- Boas capacidades de reparo de geometria
- Nenhuma configuração de servidor necessária

---

## Instruções Passo a Passo

### Passo 1: Carregar e Inspecionar Dados

1. **Carregar ambas as camadas** no QGIS:
   - `corpos_agua.gpkg` ou `rios_lagos.shp`
   - `locais_industriais.gpkg` ou `fabricas.shp`

2. **Verificar compatibilidade de SRC**:
   ```
   Clique direito na camada → Propriedades → Informação
   Verificar se ambas usam o mesmo SRC projetado (ex: UTM, SIRGAS)
   ```

3. **Verificar validade da geometria**:
   ```
   Vetor → Ferramentas de Geometria → Verificar Validade
   Executar em ambas as camadas
   ```

:::warning Requisitos de SRC
Operações de buffer requerem um **sistema de coordenadas projetado** (metros/pés), não geográfico (lat/lon). Se seus dados estão em EPSG:4326, reprojete primeiro:

```
Vetor → Ferramentas de Gerenciamento de Dados → Reprojetar Camada
SRC Alvo: Escolher zona UTM apropriada ou projeção local
```
:::

### Passo 2: Criar Buffer de 1km ao Redor dos Corpos d'Água

**Opção A: Usar FilterMate (Recomendado)**

1. Abrir painel FilterMate
2. Selecionar camada **corpos_agua**
3. Inserir expressão de filtro:
   ```sql
   -- Manter todos os corpos d'água, preparar para buffer
   1 = 1
   ```
4. Habilitar **Modificação de Geometria** → **Buffer**
5. Definir **Distância do Buffer**: `1000` (metros)
6. **Tipo de Buffer**: `Positivo (expandir)`
7. Clicar em **Aplicar Filtro**
8. **Exportar Resultado** como `buffers_agua_1km.gpkg`

**Opção B: Usar Ferramentas Nativas do QGIS**

```
Vetor → Ferramentas de Geoprocessamento → Buffer
Distância: 1000 metros
Segmentos: 16 (curvas suaves)
Salvar como: buffers_agua_1km.gpkg
```

### Passo 3: Filtrar Locais Industriais Dentro das Zonas de Buffer

Agora a operação principal do FilterMate:

1. **Selecionar camada locais_industriais** no FilterMate
2. **Escolher Backend**: Spatialite (ou PostgreSQL se disponível)
3. Inserir **expressão de filtro espacial**:

<Tabs>
  <TabItem value="spatialite" label="Spatialite / OGR" default>
    ```sql
    -- Locais industriais intersectando buffers de água 1km
    intersects(
      $geometry,
      geometry(get_feature('buffers_agua_1km', 'fid', fid))
    )
    ```
    
    **Alternativa usando referência de camada**:
    ```sql
    -- Mais eficiente se a camada de buffer já está carregada
    intersects(
      $geometry,
      aggregate(
        layer:='buffers_agua_1km',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL (Avançado)">
    ```sql
    -- Abordagem PostGIS mais eficiente com buffer direto
    ST_DWithin(
      locais.geom,
      agua.geom,
      1000  -- Buffer de 1km aplicado instantaneamente
    )
    WHERE agua.status_protegido = true
    ```
    
    **Abordagem completa com visão materializada**:
    ```sql
    -- Cria tabela temporária otimizada
    CREATE MATERIALIZED VIEW risco_industrial AS
    SELECT 
      l.*,
      a.nome AS corpo_agua_proximo,
      ST_Distance(l.geom, a.geom) AS distancia_metros
    FROM locais_industriais l
    JOIN corpos_agua a ON ST_DWithin(l.geom, a.geom, 1000)
    ORDER BY distancia_metros;
    ```
  </TabItem>
</Tabs>

4. Clicar em **Aplicar Filtro**
5. Revisar resultados na tela do mapa (feições devem estar destacadas)

### Passo 4: Adicionar Cálculos de Distância (Opcional)

Para ver **quão longe** cada local industrial está das zonas protegidas:

1. Abrir **Calculadora de Campo** (F6)
2. Criar novo campo:
   ```
   Nome do campo: distancia_agua
   Tipo de campo: Decimal (double)
   
   Expressão:
   distance(
     $geometry,
     aggregate(
       'buffers_agua_1km',
       'collect',
       $geometry
     )
   )
   ```
3. Feições dentro do buffer mostrarão `0` ou valores pequenos

### Passo 5: Categorizar por Nível de Risco

Criar categorias visuais baseadas em proximidade:

1. **Clique direito na camada filtrada** → Propriedades → Simbologia
2. Escolher **Categorizado**
3. Usar expressão:
   ```python
   CASE
     WHEN "distancia_agua" = 0 THEN 'Alto Risco (Dentro do Buffer)'
     WHEN "distancia_agua" <= 500 THEN 'Risco Médio (0-500m)'
     WHEN "distancia_agua" <= 1000 THEN 'Baixo Risco (500-1000m)'
     ELSE 'Sem Risco (Fora do Buffer)'
   END
   ```
4. Aplicar esquema de cores (vermelho → amarelo → verde)

### Passo 6: Exportar Resultados

1. No FilterMate, **Exportar Feições Filtradas**:
   ```
   Formato: GeoPackage
   Nome do arquivo: locais_industriais_risco_ambiental.gpkg
   Incluir atributos: ✓ Todos os campos
   SRC: Manter original ou escolher padrão (ex: WGS84 para compartilhar)
   ```

2. **Gerar relatório** (opcional):
   ```python
   # No Console Python (passo avançado opcional)
   layer = iface.activeLayer()
   total = layer.featureCount()
   alto_risco = sum(1 for f in layer.getFeatures() if f['distancia_agua'] == 0)
   
   print(f"Total locais industriais no buffer: {total}")
   print(f"Alto risco (diretamente no buffer de água): {alto_risco}")
   print(f"Porcentagem em risco: {(alto_risco/total)*100:.1f}%")
   ```

---

## Entendendo os Resultados

### O Que o Filtro Mostra

✅ **Feições selecionadas**: Locais industriais dentro de 1km de corpos d'água protegidos

❌ **Feições excluídas**: Locais industriais a mais de 1km de qualquer corpo d'água

### Interpretando a Análise

**Locais de Alto Risco** (distância = 0):
- Diretamente dentro de zonas de buffer regulamentadas
- Podem violar regulamentações ambientais
- Requerem revisão de conformidade imediata
- Potencial para contaminação da água

**Locais de Risco Médio** (0-500m):
- Próximos aos limites do buffer
- Devem ser monitorados
- Podem precisar de salvaguardas adicionais
- Expansões futuras do buffer poderiam afetá-los

**Locais de Baixo Risco** (500-1000m):
- Dentro do buffer analítico mas fora da regulamentação típica
- Útil para planejamento proativo
- Preocupação imediata menor

### Verificações de Qualidade

1. **Inspeção visual**: Aproximar em vários resultados e verificar que estão realmente perto da água
2. **Verificação de atributos**: Garantir que tipos de instalações correspondem às expectativas
3. **Validação de distância**: Medir distância no QGIS para confirmar precisão do buffer
4. **Problemas de geometria**: Procurar locais na borda do buffer (pode indicar problemas de geometria)

---

## Melhores Práticas

### Otimização de Performance

**Para Grandes Conjuntos de Dados (>10.000 locais industriais)**:

1. **Simplificar geometria dos corpos d'água** primeiro:
   ```
   Vetor → Ferramentas de Geometria → Simplificar
   Tolerância: 10 metros (mantém precisão)
   ```

2. **Usar índice espacial** (automático no PostgreSQL, manual no Spatialite):
   ```
   Camada → Propriedades → Criar Índice Espacial
   ```

3. **Pré-filtrar corpos d'água** apenas para áreas protegidas:
   ```sql
   "status_protegido" = 'sim' OR "designacao" IS NOT NULL
   ```

**Seleção de Backend**:
```
Feições     | Backend Recomendado
--------    | -------------------
< 1.000     | OGR (mais simples)
1k - 50k    | Spatialite (bom equilíbrio)
> 50k       | PostgreSQL (mais rápido)
```

### Considerações de Precisão

1. **Unidades de distância do buffer**: Sempre verificar que unidades correspondem ao seu SRC:
   ```
   Metros: UTM, SIRGAS, Web Mercator
   Pés: Algumas zonas State Plane
   Graus: NUNCA usar para buffers (reprojetar primeiro!)
   ```

2. **Reparo de geometria**: Corpos d'água frequentemente têm geometrias inválidas:
   ```
   Vetor → Ferramentas de Geometria → Corrigir Geometrias
   Executar antes da operação de buffer
   ```

3. **Topologia**: Corpos d'água sobrepostos podem criar formas de buffer inesperadas:
   ```
   Vetor → Geoprocessamento → Dissolver (unir todos os corpos d'água)
   Então criar buffer unificado único
   ```

### Conformidade Regulatória

- **Documentar metodologia**: Salvar histórico de expressões FilterMate
- **Controle de versão**: Manter dados originais + resultados filtrados + metadados
- **Validação**: Fazer referência cruzada com bancos de dados regulatórios oficiais
- **Atualizações**: Re-executar análise quando registro industrial for atualizado

---

## Problemas Comuns

### Problema 1: "Nenhuma feição selecionada"

**Causa**: Incompatibilidade de SRC ou distância de buffer muito pequena

**Solução**:
```
1. Verificar se ambas as camadas estão no mesmo SRC projetado
2. Verificar distância do buffer: 1000 em metros, não graus
3. Tentar buffer maior (ex: 2000m) para testar
4. Verificar se corpos d'água realmente existem em sua área de estudo
```

### Problema 2: "Erros de geometria" durante buffer

**Causa**: Geometrias de corpos d'água inválidas

**Solução**:
```
Vetor → Ferramentas de Geometria → Corrigir Geometrias
Então recriar buffers
```

### Problema 3: Performance muito lenta (>2 minutos)

**Causa**: Grandes conjuntos de dados sem otimização

**Soluções**:
```
1. Criar índices espaciais em ambas as camadas
2. Simplificar geometria dos corpos d'água (tolerância 10m)
3. Mudar para backend PostgreSQL
4. Pré-filtrar para área de interesse menor
```

### Problema 4: Buffer cria formas estranhas

**Causa**: SRC geográfico (lat/lon) em vez de projetado

**Solução**:
```
Reprojetar AMBAS as camadas para zona UTM apropriada:
Vetor → Gerenciamento de Dados → Reprojetar Camada
Encontrar zona correta: https://epsg.io/
```

---

## Próximos Passos

### Fluxos de Trabalho Relacionados

- **[Cobertura de Serviços de Emergência](./emergency-services)**: Técnicas similares de análise de buffer
- **[Planejamento Urbano Transporte](./urban-planning-transit)**: Filtragem espacial multi-camadas
- **[Análise Imobiliária](./real-estate-analysis)**: Combinação de filtros espaciais + atributos

### Técnicas Avançadas

**1. Buffers Multi-Anel** (zonas de risco graduadas):
```
Criar 3 buffers separados: 500m, 1000m, 1500m
Categorizar instalações por qual buffer elas se enquadram
```

**2. Proximidade à Água Mais Próxima** (não apenas qualquer água):
```sql
-- Encontrar distância apenas ao corpo d'água mais próximo
array_min(
  array_foreach(
    overlay_nearest('corpos_agua', $geometry),
    distance(@element, $geometry)
  )
)
```

**3. Análise Temporal** (se você tem dados de idade da instalação):
```sql
-- Instalações antigas em áreas sensíveis (risco mais alto)
"ano_construcao" < 1990 
AND distancia_agua < 500
```

**4. Impacto Acumulativo** (múltiplas instalações perto do mesmo corpo d'água):
```sql
-- Contar instalações afetando cada corpo d'água
WITH contagens_risco AS (
  SELECT id_agua, COUNT(*) as num_instalacoes
  FROM locais_filtrados
  GROUP BY id_agua
)
-- Mostrar corpos d'água com >5 instalações próximas
```

### Aprendizado Adicional

- �� [Referência de Predicados Espaciais](../reference/cheat-sheets/spatial-predicates)
- 📖 [Guia de Operações de Buffer](../user-guide/buffer-operations)
- 📖 [Ajuste de Performance](../advanced/performance-tuning)
- 📖 [Solução de Problemas](../advanced/troubleshooting)

---

## Resumo

✅ **Você aprendeu**:
- Criar zonas de buffer ao redor de corpos d'água
- Filtragem por interseção espacial com locais industriais
- Cálculo de distância e categorização de riscos
- Validação e reparo de geometria
- Técnicas de otimização específicas do backend

✅ **Principais conclusões**:
- Sempre usar SRC projetado para operações de buffer
- Corrigir erros de geometria antes de análise espacial
- Escolher backend baseado no tamanho do conjunto de dados
- Documentar metodologia para conformidade regulatória
- Validação visual é essencial

🎯 **Impacto real**: Este fluxo de trabalho ajuda agências ambientais a identificar riscos de conformidade, apoia formulação de políticas baseadas em evidências e protege qualidade da água ao destacar instalações que requerem monitoramento ou remediação.
