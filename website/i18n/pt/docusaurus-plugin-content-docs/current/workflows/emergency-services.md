---
sidebar_position: 4
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Serviços de Emergência: Análise de Cobertura

Identificar áreas que carecem de cobertura adequada de serviços de emergência para otimizar o posicionamento de instalações e planejamento de resposta.

## Visão Geral do Cenário

**Objetivo**: Encontrar áreas residenciais a mais de 5km da estação de bombeiros mais próxima para identificar lacunas de cobertura.

**Aplicação do Mundo Real**:
- Departamentos de bombeiros otimizando posicionamento de estações
- Gestão de emergências planejando tempos de resposta
- Planejadores urbanos avaliando equidade de serviços
- Companhias de seguros avaliando zonas de risco

**Tempo Estimado**: 12 minutos

**Dificuldade**: ⭐⭐ Intermediário

---

## Pré-requisitos

### Dados Necessários

1. **Camada de Estações de Bombeiros** (pontos)
   - Localizações de instalações de serviços de emergência
   - Deve incluir nomes/IDs das estações
   - Cobre sua área de estudo

2. **Camada de Áreas Populacionais** (polígonos)
   - Setores censitários, bairros ou zonas postais
   - Atributo de contagem populacional (opcional mas valioso)
   - Áreas de uso residencial

3. **Opcional: Rede Viária**
   - Para análise de tempo de viagem (avançado)
   - Topologia de rede para roteamento

### Fontes de Dados de Exemplo

**Opção 1: OpenStreetMap**
```python
# Usar plugin QuickOSM do QGIS

# Para estações de bombeiros:
Chave: "amenity", Valor: "fire_station"

# Para áreas residenciais:
Chave: "landuse", Valor: "residential"
Chave: "place", Valor: "neighbourhood"
```

**Opção 2: Dados Abertos Governamentais**
- Bancos de dados municipais de serviços de emergência
- Arquivos de limites censitários com população
- HIFLD (Homeland Infrastructure Foundation-Level Data)
- Portais locais de dados SIG

### Recomendação de Backend

**OGR** - Melhor escolha para este fluxo de trabalho:
- Compatibilidade universal de formatos (Shapefiles, GeoJSON, GeoPackage)
- Nenhuma configuração complexa necessária
- Bom para conjuntos de dados <10.000 feições
- Funciona com qualquer instalação do QGIS

---

## Instruções Passo a Passo

### Passo 1: Carregar e Preparar Dados

1. **Carregar camadas** no QGIS:
   - `estacoes_bombeiros.gpkg` (ou .shp, .geojson)
   - `areas_residenciais.gpkg`

2. **Verificar SRC**:
   ```
   Ambas as camadas devem usar o mesmo sistema de coordenadas projetado
   Clique direito → Propriedades → Informação → SRC
   
   Recomendado: Zona UTM local ou grade estadual/nacional
   Exemplo: EPSG:32633 (Zona UTM 33N)
   ```

3. **Inspecionar dados**:
   - Contar estações de bombeiros: Deve ter pelo menos 3-5 para análise significativa
   - Verificar áreas residenciais: Procurar atributos de população ou número de domicílios
   - Verificar cobertura: Estações devem estar distribuídas pela área de estudo

:::tip Encontrando Sua Zona UTM
Use [epsg.io](https://epsg.io/) e clique no mapa para encontrar a zona UTM apropriada para sua região.
:::

### Passo 2: Criar Áreas de Serviço de 5km ao Redor das Estações

**Usando FilterMate**:

1. Abrir FilterMate, selecionar camada **estacoes_bombeiros**
2. Inserir expressão:
   ```sql
   -- Manter todas as estações
   1 = 1
   ```
3. Habilitar operação **Buffer**:
   - Distância: `5000` metros
   - Tipo: Positivo (expandir)
   - Segmentos: 16 (para círculos suaves)
4. **Aplicar Filtro**
5. **Exportar** como `cobertura_bombeiros_5km.gpkg`

**Resultado**: Buffers circulares de 5km ao redor de cada estação (zonas de cobertura de serviço)

### Passo 3: Identificar Áreas Residenciais Sub-atendidas (Consulta Inversa)

Este é o passo chave - encontrar áreas **NÃO** dentro de 5km de qualquer estação:

<Tabs>
  <TabItem value="ogr" label="OGR / Spatialite" default>
    **Método 1: Usando FilterMate (Recomendado)**
    
    1. Selecionar camada **areas_residenciais**
    2. Escolher backend **OGR**
    3. Inserir expressão:
    ```sql
    -- Áreas residenciais NÃO intersectando cobertura de bombeiros
    NOT intersects(
      $geometry,
      aggregate(
        layer:='cobertura_bombeiros_5km',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
    
    **Método 2: Usando predicado disjoint()**
    ```sql
    -- Áreas completamente fora de todas as zonas de cobertura
    disjoint(
      $geometry,
      aggregate('cobertura_bombeiros_5km', 'collect', $geometry)
    )
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL (Avançado)">
    ```sql
    -- Áreas residenciais sem estação próxima
    NOT EXISTS (
      SELECT 1
      FROM estacoes_bombeiros eb
      WHERE ST_DWithin(
        areas_residenciais.geom,
        eb.geom,
        5000  -- Limiar de 5km
      )
    )
    ```
    
    **Ou usando junção espacial**:
    ```sql
    SELECT ar.*
    FROM areas_residenciais ar
    LEFT JOIN estacoes_bombeiros eb
      ON ST_DWithin(ar.geom, eb.geom, 5000)
    WHERE eb.id_estacao IS NULL  -- Nenhuma estação correspondente encontrada
    ```
  </TabItem>
</Tabs>

4. Clicar em **Aplicar Filtro**
5. Revisar mapa - áreas vermelhas/destacadas mostram lacunas de cobertura

### Passo 4: Calcular Distância Exata à Estação Mais Próxima

Adicionar campo mostrando quão longe cada área sub-atendida está da estação mais próxima:

1. Abrir **Tabela de Atributos** (F6) da camada filtrada
2. **Abrir Calculadora de Campo**
3. Criar novo campo:
   ```
   Nome do campo: distancia_estacao_proxima
   Tipo de campo: Decimal (double)
   Precisão: 2
   
   Expressão:
   array_min(
     array_foreach(
       overlay_nearest('estacoes_bombeiros', $geometry, limit:=5),
       distance(geometry(@element), $geometry)
     )
   ) / 1000  -- Converter metros para quilômetros
   ```

**Resultado**: Cada área residencial agora mostra distância à estação mais próxima

### Passo 5: Priorizar por População em Risco

Se sua camada residencial tem dados de população:

1. **Calcular população total** em áreas sub-atendidas:
   ```sql
   -- No filtro de expressão ou calculadora de campo
   "populacao" > 0
   ```

2. **Ordenar por prioridade**:
   ```
   Tabela de Atributos → Clicar no cabeçalho da coluna "populacao"
   → Ordenar decrescente
   ```

3. **Criar categorias de prioridade**:
   ```sql
   CASE
     WHEN "distancia_estacao_proxima" > 10 THEN 'Crítico (>10km)'
     WHEN "distancia_estacao_proxima" > 7 THEN 'Alta Prioridade (7-10km)'
     WHEN "distancia_estacao_proxima" > 5 THEN 'Prioridade Média (5-7km)'
     ELSE 'Aceitável (<5km)'
   END
   ```

### Passo 6: Visualizar Lacunas de Cobertura

**Configuração de Simbologia**:

1. Clique direito em **areas_residenciais** → Simbologia
2. Escolher **Graduado**
3. Valor: `distancia_estacao_proxima`
4. Método: Quebras Naturais (Jenks)
5. Classes: 5
6. Rampa de cores: Vermelho (longe) → Amarelo → Verde (perto)
7. Aplicar

**Adicionar Rótulos** (opcional):
```
Rotular com: concat("nome", ' - ', round("distancia_estacao_proxima", 1), ' km')
Tamanho: Baseado em "populacao" (maior = mais pessoas afetadas)
```

### Passo 7: Exportar Resultados e Gerar Relatório

1. **Exportar áreas sub-atendidas**:
   ```
   FilterMate → Exportar Feições Filtradas
   Formato: GeoPackage
   Nome do arquivo: areas_residenciais_sub_atendidas.gpkg
   SRC: WGS84 (para compartilhar) ou manter SRC do projeto
   ```

2. **Gerar estatísticas resumidas**:
   ```
   Vetor → Ferramentas de Análise → Estatísticas Básicas
   Entrada: areas_residenciais_sub_atendidas
   Campo: populacao
   ```

3. **Criar relatório resumido** (Console Python - opcional):
   ```python
   layer = iface.activeLayer()
   features = list(layer.getFeatures())
   
   total_areas = len(features)
   total_populacao = sum(f['populacao'] for f in features if f['populacao'])
   distancia_media = sum(f['distancia_estacao_proxima'] for f in features) / total_areas
   distancia_max = max(f['distancia_estacao_proxima'] for f in features)
   
   print(f"=== Análise de Lacunas de Cobertura Serviços de Emergência ===")
   print(f"Áreas residenciais sub-atendidas: {total_areas}")
   print(f"População afetada: {total_populacao:,}")
   print(f"Distância média à estação mais próxima: {distancia_media:.1f} km")
   print(f"Distância máxima: {distancia_max:.1f} km")
   ```

---

## Entendendo os Resultados

### O Que o Filtro Mostra

✅ **Áreas selecionadas**: Zonas residenciais >5km de QUALQUER estação de bombeiros

❌ **Áreas excluídas**: Zonas residenciais dentro do raio de serviço de 5km

### Interpretando Lacunas de Cobertura

**Lacunas Críticas (>10km)**:
- Tempo de resposta provavelmente excede padrões nacionais (ex: NFPA 1710: 8 minutos)
- Alta prioridade para posicionamento de nova estação
- Considerar estações temporárias ou voluntárias
- Pode precisar de acordos de auxílio mútuo com jurisdições vizinhas

**Alta Prioridade (7-10km)**:
- Tempo de resposta limite aceitável
- Deve ser abordado no próximo ciclo de planejamento
- Considerar estações móveis/sazonais
- Avaliar qualidade da rede viária (pode ser tempo de viagem mais longo)

**Prioridade Média (5-7km)**:
- Tecnicamente sub-atendido por padrões estritos
- Baixa urgência se densidade populacional é baixa
- Monitorar para crescimento futuro
- Pode ser aceitável para áreas rurais

### Verificações de Validação

1. **Verificação visual pontual**: Usar ferramenta de Medição do QGIS para verificar distâncias
2. **Casos limite**: Áreas logo fora de 5km podem arredondar diferentemente
3. **Precisão populacional**: Verificar se soma corresponde aos totais censitários conhecidos
4. **Validade de geometria**: Procurar por fragmentos ou polígonos inválidos

---

## Melhores Práticas

### Padrões de Cobertura

**Recomendações NFPA 1710 (EUA)**:
- Áreas urbanas: 1.5 milha (2,4 km) distância de viagem
- Áreas rurais: Até 5 milhas (8 km) aceitável
- Meta de tempo de resposta: 8 minutos da chamada à chegada

**Ajustar limiar** baseado em sua região:
```
Áreas urbanas:    2-3 km
Áreas suburbanas: 5 km (como neste tutorial)
Áreas rurais:     8-10 km
```

### Otimização de Performance

**Para grandes conjuntos de dados**:

1. **Simplificar geometria das áreas residenciais**:
   ```
   Vetor → Geometria → Simplificar
   Tolerância: 50 metros (mantém precisão de cobertura)
   ```

2. **Pré-filtrar apenas para áreas povoadas**:
   ```sql
   "populacao" > 0 OR "uso_solo" = 'residential'
   ```

3. **Usar índice espacial** (OGR cria automaticamente para GeoPackage)

4. **Guia de seleção de backend**:
   ```
   < 1.000 áreas:    OGR (suficiente)
   1k - 50k:         Spatialite
   > 50k:            PostgreSQL
   ```

### Ajustes do Mundo Real

**Considerar realidade da rede viária**:
- 5km em linha reta pode ser 8km por estrada
- Montanhas/rios podem bloquear acesso direto
- Usar análise de rede para tempo de viagem (avançado)

**Alternativa de Análise de Rede** (integrado QGIS):
```
Processamento → Análise de Rede → Área de Serviço (de camada)
Entrada: estacoes_bombeiros
Custo de viagem: 5000 metros OU 10 minutos
Cria polígonos de tempo de viagem em vez de círculos
```

### Considerações de Qualidade de Dados

1. **Precisão das estações**:
   - Verificar se estações estão operacionais (não desativadas)
   - Verificar se estações voluntárias devem ter raio menor
   - Considerar estações especializadas (aeroporto, industrial)

2. **Qualidade das áreas residenciais**:
   - Remover parques, zonas industriais classificadas erroneamente como residenciais
   - Atualizar com dados censitários recentes
   - Contabilizar novos desenvolvimentos

3. **Importância do SRC**:
   - Cálculos de distância requerem SRC projetado
   - Geográfico (lat/lon) dará resultados incorretos
   - Sempre reprojetar se necessário antes da análise

---

## Problemas Comuns

### Problema 1: Todas as áreas residenciais selecionadas (ou nenhuma)

**Causa**: Incompatibilidade de SRC ou buffer não criado corretamente

**Solução**:
```
1. Verificar se camada cobertura_bombeiros_5km existe e tem feições
2. Verificar se ambas as camadas estão no mesmo SRC
3. Recriar buffers com unidade de distância correta (metros)
4. Verificar se nome da camada de buffer corresponde exatamente à expressão
```

### Problema 2: Cálculo de distância retorna NULL ou erros

**Causa**: overlay_nearest() não está encontrando camada estacoes_bombeiros

**Solução**:
```
1. Garantir que camada estacoes_bombeiros está carregada no projeto
2. Verificar se nome da camada corresponde exatamente (sensível a maiúsculas)
3. Alternativa: Usar aggregate() com distância mínima:

distance(
  $geometry,
  aggregate('estacoes_bombeiros', 'collect', $geometry)
)
```

### Problema 3: Resultados mostram padrões inesperados

**Causa**: Problemas de qualidade de dados ou projeção

**Solução de Problemas**:
```
1. Aproximar em resultado específico e medir distância manualmente
2. Verificar polígonos residenciais sobrepostos
3. Verificar se estacoes_bombeiros realmente cobrem a área
4. Procurar geometrias inválidas:
   Vetor → Ferramentas de Geometria → Verificar Validade
```

### Problema 4: Performance muito lenta

**Causa**: Geometrias grandes ou áreas residenciais complexas

**Soluções**:
```
1. Simplificar geometria residencial (tolerância 50-100m)
2. Criar índice espacial em ambas as camadas
3. Processar por distritos administrativos separadamente
4. Usar backend PostgreSQL para >10k feições
```

---

## Próximos Passos

### Fluxos de Trabalho Relacionados

- **[Planejamento Urbano Transporte](./urban-planning-transit)**: Padrão de análise de buffer similar
- **[Proteção Ambiental](./environmental-protection)**: Consultas espaciais inversas
- **[Análise Imobiliária](./real-estate-analysis)**: Filtragem multi-critérios

### Técnicas Avançadas

**1. Cobertura Multi-Estações** (áreas atendidas por ≥2 estações):
```sql
-- Contar zonas de cobertura sobrepostas
array_length(
  overlay_intersects('cobertura_bombeiros_5km', $geometry)
) >= 2
```

**2. Pontuação de Prioridade** (distância + população):
```sql
-- Pontuação maior = maior prioridade para nova estação
("distancia_estacao_proxima" - 5) * "populacao" / 1000
```

**3. Localização Ótima de Nova Estação**:
```
1. Exportar áreas sub-atendidas com população
2. Encontrar centroide ponderado por população:
   Processamento → Geometria de Vetor → Centroides
3. Análise manual: Posicionar nova estação no centroide de maior prioridade
```

**4. Modelagem de Tempo de Resposta** (avançado):
```python
# Requer rede viária e roteamento
# Usa ferramentas de Análise de Rede do QGIS
# Modela tempo de viagem real vs. distância em linha reta
# Considera limites de velocidade e restrições de curva
```

**5. Análise Temporal** (crescimento futuro):
```sql
-- Se você tem dados de projeção populacional
("populacao_2030" - "populacao_2024") / "populacao_2024" > 0.2
-- Áreas esperando >20% de crescimento
```

### Aprendizado Adicional

- 📖 [Referência de Predicados Espaciais](../reference/cheat-sheets/spatial-predicates)
- 📖 [Operações de Buffer](../user-guide/buffer-operations)
- 📖 [Análise de Rede no QGIS](https://docs.qgis.org/latest/pt_BR/docs/user_manual/processing_algs/qgis/networkanalysis.html)
- 📖 [Ajuste de Performance](../advanced/performance-tuning)

---

## Resumo

✅ **Você aprendeu**:
- Criar buffers de área de serviço ao redor de instalações
- Filtragem espacial inversa (NOT intersects)
- Cálculos de distância à feição mais próxima
- Análise de prioridade ponderada por população
- Exportação de resultados para relatórios de planejamento

✅ **Técnicas chave**:
- `NOT intersects()` para análise de lacunas de cobertura
- `overlay_nearest()` para cálculos de distância
- `aggregate()` com predicados espaciais
- Pontuação de prioridade com dados de atributo + espaciais

🎯 **Impacto real**: Este fluxo de trabalho ajuda agências de gestão de emergências a identificar lacunas de serviço, otimizar alocação de recursos, melhorar tempos de resposta e garantir cobertura equitativa de serviços de emergência nas comunidades.

💡 **Dica profissional**: Execute esta análise anualmente com dados censitários atualizados para rastrear mudanças de cobertura conforme as populações mudam e ajuste o posicionamento de estações de acordo.
