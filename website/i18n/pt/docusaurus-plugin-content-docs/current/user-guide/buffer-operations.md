---
sidebar_position: 5
---

# Operações de Buffer

Crie buffers ao redor de geometrias e use-os para análise de proximidade na aba **FILTERING**.

## Visão Geral

Um **buffer** é um polígono que representa todos os pontos dentro de uma distância especificada de uma geometria. No FilterMate, os buffers são configurados na **aba FILTERING** junto com os predicados geométricos para filtragem espacial baseada em proximidade.

### Usos Principais

Os buffers são essenciais para:
- **Análise de proximidade** - Encontrar feições próximas de algo (ex: edifícios dentro de 200m de estradas)
- **Zonas de impacto** - Definir áreas de influência (ex: buffer de ruído ao redor de aeroporto)
- **Áreas de serviço** - Análise de cobertura (ex: 500m de distância a pé até transporte)
- **Zonas de segurança** - Limites de exclusão (ex: buffer de 100m ao redor de perigos)

:::tip Localização na Interface
A configuração de buffer está na **aba FILTERING**, abaixo do seletor de predicados geométricos. Os buffers são aplicados à geometria da **camada de referência** antes da comparação espacial.
:::

### Conceitos-Chave

- **Distância**: Até onde o buffer se estende (nas unidades especificadas)
- **Unidade**: Medida de distância (metros, quilômetros, pés, milhas, graus)
- **Tipo de Buffer**: Algoritmo usado (Padrão, Rápido ou Segmento)
- **Integração**: Buffers funcionam com predicados espaciais (Intersects, Contains, etc.)

## Tipos de Buffer

O FilterMate suporta três algoritmos de buffer na aba FILTERING, cada um com diferentes características de desempenho e precisão.

### 1. Buffer Padrão (Default)

O **algoritmo padrão** cria buffers precisos adequados para a maioria dos casos de uso.

**Características:**
- ✅ Resultados precisos
- ✅ Lida bem com geometrias complexas
- ✅ Bom para a maioria dos casos de uso
- ⚠️ Desempenho moderado em grandes conjuntos de dados

**Quando Usar:**
- Análise geral de proximidade
- Aplicações de planejamento
- Conformidade regulatória (precisão necessária)
- Conjuntos de dados médios (<10k feições)

**Exemplo de Configuração:**
```
Aba FILTERING:
- Distância do Buffer: 500
- Unidade do Buffer: metros
- Tipo de Buffer: Padrão
- Segmentos: 16 (curvas suaves)
```

### 2. Buffer Rápido

O **algoritmo rápido** prioriza o **desempenho** sobre a precisão.

**Características:**
- ⚡ 2-5x mais rápido que o padrão
- ⚠️ Menor precisão geométrica
- ✅ Bom para grandes conjuntos de dados
- ✅ Adequado para visualização e exploração

**Quando Usar:**
- Grandes conjuntos de dados (>50k feições)
- Exploração interativa no QGIS
- Análise aproximada onde a precisão não é crítica
- Visualização rápida de zonas de proximidade

**Comparação de Desempenho:**
```
Tamanho Dataset | Padrão | Rápido | Ganho de Velocidade
----------------|--------|--------|--------------------
1.000 feições   | 0.5s   | 0.2s   | 2.5x
10.000          | 4.2s   | 1.1s   | 3.8x
50.000          | 21.3s  | 5.8s   | 3.7x
100.000         | 45.1s  | 11.2s  | 4.0x
```

### 3. Buffer de Segmento

O **buffer de segmento** cria buffers com segmentação personalizável para controle fino sobre suavidade vs desempenho.

**Características:**
- ✅ Controle fino sobre contagem de segmentos
- ✅ Equilíbrio entre precisão e velocidade
- ✅ Bom para saídas de qualidade de publicação
- ⚠️ Requer compreensão dos trade-offs

**Quando Usar:**
- Mapas de qualidade de publicação
- Quando você precisa de suavidade específica
- Ajuste de desempenho personalizado
- Usuários avançados querendo controle

**Diretrizes de Contagem de Segmentos:**
- **4-8 segmentos**: Rápido, aparência angular
- **16 segmentos**: Equilibrado (padrão)
- **32-64 segmentos**: Curvas suaves, mais lento
- **64+ segmentos**: Qualidade de publicação, mais lento

## Configuração de Buffer na Aba FILTERING

### Seleção de Distância e Unidade

**Unidades Suportadas**:
- **Metros** (m) - Mais comum para CRS projetado
- **Quilômetros** (km)
- **Pés** (ft) - US State Plane
- **Milhas** (mi)
- **Graus** - CRS Geográfico (use com cautela)

:::tip CRS Importa
Certifique-se de que sua camada usa um CRS apropriado:
- **Projetado** (metros, pés): UTM, State Plane, projeções locais → Use metros/pés
- **Geográfico** (graus): WGS84, NAD83 → Converta para CRS projetado primeiro para buffers precisos
:::

**Exemplos de Distância**:
```
Planejamento urbano:    50-500m
Acesso a transporte:    400-800m (distância a pé)
Zonas de ruído:         1-5km
Ambiental:              100m-10km
Análise regional:       10-100km
```

### Seleção de Tipo de Buffer

**Critérios de Seleção**:

| Cenário | Tipo Recomendado | Por quê |
|---------|------------------|---------|
| Exploração rápida | Rápido | Velocidade sobre precisão |
| Relatórios oficiais | Padrão | Boa precisão |
| Grandes datasets (>50k) | Rápido | Desempenho |
| Mapas de publicação | Segmento (32+) | Qualidade visual |
| Conformidade regulatória | Padrão | Precisão confiável |

### Integração de Buffer com Filtragem Geométrica

Os buffers funcionam perfeitamente com **predicados espaciais** na aba FILTERING:

**Fluxo de Trabalho**:
1. Selecione a camada fonte (ex: "edifícios")
2. Selecione o predicado espacial (ex: "Intersects")
3. Selecione a camada de referência (ex: "estradas")
4. Configure o buffer: 200m, tipo Padrão
5. Clique FILTRAR

**O que Acontece**:
- A geometria da camada de referência é bufferizada em 200m
- O predicado espacial (Intersects) é aplicado entre a camada fonte e a referência bufferizada
- Resultado: Edifícios que intersectam estradas dentro de 200m

**Exemplos de Casos de Uso**:

| Camada Fonte | Predicado | Camada Referência | Buffer | Resultado |
|--------------|-----------|-------------------|--------|-----------|
| Edifícios | Intersects | Estradas | 200m | Edifícios dentro de 200m de estradas |
| Parcelas | Within | Zona Protegida | 50m | Parcelas dentro de 50m dentro da zona |
| Instalações | Disjoint | Perigos | 500m | Instalações a >500m de perigos |
| POIs | Contains | Distrito + Buffer | 100m | POIs no distrito + margem de 100m |

## Tratamento Automático de CRS

:::tip Novo na v2.2.5
O FilterMate agora converte automaticamente coordenadas geográficas (lat/lon) para um CRS métrico apropriado ao aplicar buffers, garantindo cálculos de distância precisos.
:::

### Como Funciona

Quando você aplica um buffer com unidades métricas (metros, quilômetros) em uma camada com CRS geográfico:

1. **Detecção**: FilterMate detecta que a camada usa graus
2. **Conversão**: Temporariamente reprojeta para um CRS métrico apropriado
3. **Cálculo**: Aplica o buffer na unidade métrica correta
4. **Resultado**: Retorna resultados precisos de proximidade

### Benefícios

- Sem configuração manual de CRS necessária
- Funciona com qualquer camada fonte
- Mantém a precisão para análise de proximidade
- Totalmente automático e transparente

## Exemplos Práticos

### Planejamento Urbano

#### Análise de Cobertura de Transporte
```python
# 400m a pé até estações de transporte
tipo_buffer = "padrão"
distância = 400
segmentos = 16

# Encontrar áreas residenciais NÃO cobertas
```

**Cenário**: Identificar lacunas de cobertura de transporte público

**Configuração**:
- Camada fonte: Parcelas residenciais
- Camada referência: Estações de transporte
- Predicado: Disjoint
- Buffer: 400m (distância de caminhada padrão)

**Resultado**: Parcelas além da distância de caminhada do transporte

### Análise Ambiental

#### Zonas de Proteção Ribeirinha
```python
# Buffer de 100m ao longo de cursos d'água
tipo_buffer = "padrão"
distância = 100
```

**Cenário**: Identificar atividades de desenvolvimento dentro de zonas de proteção

**Configuração**:
- Camada fonte: Licenças de construção
- Camada referência: Rios e córregos
- Predicado: Intersects
- Buffer: 100m (zona de proteção ribeirinha)

**Resultado**: Licenças de construção que requerem revisão ambiental

### Serviços de Emergência

#### Cobertura de Tempo de Resposta
```python
# Estações de bombeiros com raio de 5km
tipo_buffer = "rápido"  # Grande dataset
distância = 5000
```

**Cenário**: Analisar lacunas de cobertura de resposta a emergências

**Configuração**:
- Camada fonte: Todas as propriedades
- Camada referência: Estações de bombeiros
- Predicado: Disjoint
- Buffer: 5000m (meta de tempo de resposta)

**Resultado**: Propriedades fora do raio de resposta ideal

## Dicas de Desempenho

### Otimizando Operações de Buffer

1. **Use o tipo de buffer apropriado**
   - Exploração: Rápido
   - Análise final: Padrão
   - Publicação: Segmento

2. **Considere o tamanho do dataset**
   - <10k feições: Qualquer tipo funciona
   - 10k-50k: Prefira Rápido para exploração
   - >50k: Use Rápido, otimize depois

3. **Ajuste a contagem de segmentos**
   - Menos segmentos = mais rápido, menos suave
   - Mais segmentos = mais lento, mais suave

### Resolução de Problemas

#### Buffers parecem irregulares
**Causa**: Contagem de segmentos muito baixa
**Solução**: Aumente os segmentos para 32 ou 64

#### Operação de buffer muito lenta
**Causa**: Dataset grande com buffer padrão
**Solução**: Mude para tipo Rápido ou reduza segmentos

#### Resultados de buffer imprecisos
**Causa**: CRS geográfico com unidades métricas
**Solução**: O FilterMate v2.2.5+ lida com isso automaticamente
