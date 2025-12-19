---
sidebar_position: 2
---

# Por que FilterMate?

Entenda quando usar FilterMate vs ferramentas nativas do QGIS para seus fluxos de trabalho de filtragem.

## Resposta Rápida

**Use FilterMate quando**:
- Você precisa de fluxos de trabalho de filtragem **rápidos e repetíveis**
- Trabalhando com **grandes conjuntos de dados** (&gt;50k feições)
- Combinando regularmente filtros de **atributo + espacial**
- Você quer **desfazer/refazer** operações de filtro
- **Exportando dados filtrados** com frequência
- Precisa de **otimização de desempenho** via backends

**Use QGIS Nativo quando**:
- Seleções simples pontuais
- Aprendendo conceitos básicos de GIS
- Instalação de plugins não permitida
- Ferramentas de processamento muito específicas necessárias

---

## Comparação de Recursos

### Operações de Filtragem

| Tarefa | QGIS Nativo | FilterMate | Vencedor |
|--------|-------------|------------|----------|
| **Filtro de atributo simples** | Propriedades da Camada → Fonte → Construtor de Consulta | Construtor de expressão no painel | 🤝 Empate |
| **Seleção rápida no mapa** | Ferramenta Selecionar por Expressão | Aba EXPLORAÇÃO | 🤝 Empate |
| **Consulta espacial complexa** | Caixa de Ferramentas de Processamento (3-5 etapas) | Operação única na aba FILTRAGEM | ⭐ **FilterMate** |
| **Filtragem multi-camadas** | Repetir processo para cada camada | Multi-seleção de camadas, aplicar uma vez | ⭐ **FilterMate** |
| **Combinado atributo + espacial** | Ferramentas separadas, combinação manual | Interface integrada | ⭐ **FilterMate** |
| **Buffer + filtro** | Ferramenta Buffer → Selecionar por Localização → Manual | Configuração de buffer + aplicar filtro | ⭐ **FilterMate** |

**Vantagem FilterMate**: Fluxo de trabalho integrado reduz 5-10 etapas manuais para 1 operação.

---

### Desempenho

| Cenário | QGIS Nativo | FilterMate | Melhoria |
|---------|-------------|------------|----------|
| **Conjunto pequeno** (&lt;10k feições) | 2-5 segundos | 1-3 segundos | 1,5× |
| **Conjunto médio** (10-50k feições) | 15-45 segundos | 2-8 segundos (Spatialite) | **5-10× mais rápido** |
| **Grande conjunto** (&gt;50k feições) | 60-300 segundos | 1-5 segundos (PostgreSQL) | **20-50× mais rápido** |
| **Conjunto muito grande** (&gt;500k feições) | 5-30+ minutos ⚠️ | 3-10 segundos (PostgreSQL) | **100-500× mais rápido** |

**Diferença Chave**: FilterMate aproveita backends de banco de dados (PostgreSQL, Spatialite) para processamento no lado do servidor, enquanto ferramentas nativas do QGIS frequentemente usam processamento em memória.

---

### Eficiência do Fluxo de Trabalho

| Tarefa | Etapas QGIS Nativo | Etapas FilterMate | Tempo Economizado |
|--------|-------------------|-------------------|-------------------|
| **Filtro de atributo** | 3 cliques (Camada → Propriedades → Consulta) | 2 cliques (Selecionar camada → Aplicar) | ~10 segundos |
| **Filtro espacial** | 5 etapas (Buffer → Selecionar por Localização → Extrair → Estilo) | 1 etapa (Definir buffer → Aplicar) | **2-5 minutos** |
| **Exportar filtrado** | 4 cliques (Botão direito → Exportar → Configurar → Salvar) | 2 cliques (Aba EXPORTAÇÃO → Exportar) | **30-60 segundos** |
| **Desfazer filtro** | Manual (recarregar camada ou limpar seleção) | 1 clique (Botão Desfazer) | **1-2 minutos** |
| **Repetir filtro** | Reinserir todas as configurações manualmente | 1 clique (Carregar de Favoritos) | **3-10 minutos** |

**Impacto no Mundo Real**: 
- **Usuários diários**: Economize 20-60 minutos por dia
- **Usuários semanais**: Economize 1-3 horas por semana
- **Usuários mensais**: Economias moderadas, mas melhorias na qualidade de vida

---

## Análise de Casos de Uso

### Caso 1: Seleção Simples Pontual

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

**Tarefa**: Selecionar cidades com população &gt; 100.000

<Tabs>
  <TabItem value="qgis" label="QGIS Nativo" default>
    ```
    1. Botão direito na camada → Filtrar
    2. Inserir: population > 100000
    3. Clicar OK
    
    Tempo: 15 segundos
    Complexidade: Baixa
    ```
    **Veredicto**: QGIS nativo está bem ✓
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Selecionar camada no FilterMate
    2. Inserir: population > 100000
    3. Clicar Aplicar Filtro
    
    Tempo: 12 segundos
    Complexidade: Baixa
    ```
    **Veredicto**: FilterMate ligeiramente mais rápido, mas não significativo
  </TabItem>
</Tabs>

**Vencedor**: 🤝 **Empate** - Ambas as ferramentas funcionam bem para filtros simples pontuais.

---

### Caso 2: Consulta Espacial Complexa

**Tarefa**: Encontrar parcelas residenciais dentro de 500m de estações de metrô

<Tabs>
  <TabItem value="qgis" label="QGIS Nativo" default>
    ```
    1. Processamento → Buffer
       - Entrada: estacoes_metro
       - Distância: 500
       - Saída: estacoes_buffer
    
    2. Processamento → Selecionar por Localização
       - Selecionar feições de: parcelas
       - Onde feições: intersectam
       - Referência: estacoes_buffer
    
    3. Processamento → Extrair Feições Selecionadas
       - Entrada: parcelas
       - Saída: parcelas_filtradas
    
    4. Botão direito em parcelas_filtradas → Filtrar
       - Inserir: land_use = 'residential'
    
    5. Estilizar camada resultado
    
    Tempo: 3-5 minutos
    Etapas: 5 operações separadas
    Complexidade: Alta
    ```
    **Veredicto**: Tedioso, propenso a erros, não reutilizável
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Selecionar camada parcelas
    2. Expressão: land_use = 'residential'
    3. Camada de referência: estacoes_metro
    4. Buffer: 500 metros
    5. Predicado: Intersecta
    6. Clicar Aplicar Filtro
    
    Tempo: 30-60 segundos
    Etapas: 1 operação integrada
    Complexidade: Baixa
    ```
    **Veredicto**: Rápido, simples, salvável como Favorito
  </TabItem>
</Tabs>

**Vencedor**: ⭐ **FilterMate** - 5× mais rápido, 80% menos etapas, fluxo de trabalho repetível.

---

### Caso 3: Análise Multi-Camadas

**Tarefa**: Filtrar edifícios, parcelas e estradas perto de rio (3 camadas)

<Tabs>
  <TabItem value="qgis" label="QGIS Nativo" default>
    ```
    1. Buffer na camada rio
    2. Selecionar por Localização para edifícios → Extrair
    3. Selecionar por Localização para parcelas → Extrair
    4. Selecionar por Localização para estradas → Extrair
    5. Estilizar 3 camadas resultado
    6. Gerenciar 6 camadas no total (originais + filtradas)
    
    Tempo: 8-12 minutos
    Etapas: 15+ operações
    Complexidade: Muito Alta
    ```
    **Veredicto**: Demorado, bagunça o painel de camadas
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Multi-seleção: edifícios, parcelas, estradas
    2. Camada de referência: rio
    3. Buffer: 100 metros
    4. Clicar Aplicar Filtro
    
    Todas as 3 camadas filtradas simultaneamente!
    
    Tempo: 1-2 minutos
    Etapas: 4 cliques
    Complexidade: Baixa
    ```
    **Veredicto**: Dramaticamente mais simples
  </TabItem>
</Tabs>

**Vencedor**: ⭐⭐ **FilterMate** - 5-10× mais rápido, mantém espaço de trabalho limpo.

---

### Caso 4: Desempenho em Grande Conjunto de Dados

**Tarefa**: Filtrar 150.000 parcelas por atributo e proximidade

<Tabs>
  <TabItem value="qgis" label="QGIS Nativo" default>
    ```
    Ferramentas de Processamento em 150k feições:
    - Buffer: 45-90 segundos
    - Selecionar por Localização: 120-180 segundos
    - Extrair: 30-60 segundos
    - Filtro de atributo: 15-30 segundos
    
    Tempo Total: 3,5-6 minutos
    Uso de Memória: Alto (processamento em memória)
    ```
    **Veredicto**: Lento, pode travar em grandes conjuntos de dados
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate (PostgreSQL)">
    ```
    Processamento no lado do servidor com índices espaciais:
    - Todas as operações combinadas: 0,5-2 segundos
    
    Tempo Total: 0,5-2 segundos
    Uso de Memória: Baixo (banco de dados gerencia)
    ```
    **Veredicto**: 100-500× mais rápido!
  </TabItem>
</Tabs>

**Vencedor**: ⭐⭐⭐ **FilterMate** - Transforma o impossível em instantâneo.

---

## Recursos Únicos do FilterMate

### 1. Histórico de Filtros & Desfazer/Refazer

**QGIS Nativo**: Sem histórico de filtros integrado
- Para "desfazer" um filtro: Remover manualmente o filtro ou recarregar a camada
- Nenhuma maneira de voltar através de mudanças de filtro
- Trabalho perdido se você cometer um erro

**FilterMate**: Gerenciamento completo de histórico
- Botão Desfazer (↩️) - Voltar ao filtro anterior
- Botão Refazer (↪️) - Avançar no histórico
- Histórico persiste durante a sessão
- Até 100 operações rastreadas

**Valor no Mundo Real**: 
- Filtragem experimental sem medo
- Comparar múltiplas variações de filtros
- Recuperação rápida de erros

---

### 2. Favoritos de Filtros

**QGIS Nativo**: Deve reinserir manualmente os filtros toda vez
- Nenhuma maneira de salvar filtros usados comumente
- Propenso a erros de digitação ao redigitar
- Difícil compartilhar filtros com colegas

**FilterMate**: Salvar e carregar filtros como Favoritos
- ⭐ Clicar para salvar o filtro atual
- Carregar do menu suspenso
- Salvo com arquivo de projeto
- Compartilhável entre equipe

**Valor no Mundo Real**:
- Filtragem padronizada para equipes
- Acesso instantâneo a filtros complexos
- Erros reduzidos de reinserção manual

---

### 3. Otimização de Backend

**QGIS Nativo**: Usa framework de Processamento
- Sempre em memória ou arquivos temporários
- Sem otimização de índice espacial
- Mesma velocidade independentemente da fonte de dados

**FilterMate**: Seleção inteligente de backend
- **PostgreSQL**: Processamento no servidor, visões materializadas
- **Spatialite**: Baseado em arquivo com índices espaciais
- **OGR**: Fallback para compatibilidade
- Seleção automática baseada no tipo de camada

**Valor no Mundo Real**:
- Melhoria de desempenho de 10-50× (PostgreSQL)
- Nenhuma mudança de fluxo de trabalho necessária
- Otimização transparente

**Ver**: [Comparação de Backends](../backends/choosing-backend)

---

### 4. Fluxo de Trabalho de Exportação Integrado

**QGIS Nativo**: Processo de exportação multi-etapas
```
1. Aplicar filtro
2. Botão direito na camada → Exportar → Salvar Feições Como
3. Configurar formato
4. Definir transformação de SRC
5. Escolher campos para exportar
6. Definir nome de arquivo
7. Clicar OK
```

**FilterMate**: Aba de exportação com um clique
```
1. Mudar para aba EXPORTAÇÃO
2. Selecionar formato (GPKG, SHP, GeoJSON, PostGIS, etc.)
3. Opcional: Transformar SRC
4. Clicar Exportar

Estado filtrado aplicado automaticamente!
```

**Valor no Mundo Real**:
- 70% menos cliques
- Menos propenso a erros
- Exportação em lote de múltiplas camadas
- Exportação de estilo (QML/SLD) incluída

---

### 5. Operações Multi-Camadas

**QGIS Nativo**: Processar uma camada por vez
- Repetir todo o fluxo de trabalho para cada camada
- Gerenciar múltiplas camadas resultado
- Fácil perder uma camada ou aplicar filtros inconsistentes

**FilterMate**: Interface de checkbox multi-seleção
- Marcar todas as camadas para filtrar
- Aplicar filtro uma vez → afeta todas
- Parâmetros consistentes entre camadas
- Espaço de trabalho limpo (camadas originais filtradas, não duplicadas)

**Valor no Mundo Real**:
- 3-10× mais rápido para fluxos de trabalho multi-camadas
- Consistência garantida
- Painel de camadas mais limpo

---

### 6. Feedback Visual & Avisos

**QGIS Nativo**: Feedback mínimo
- Processamento pode executar sem indicador de progresso
- Sem avisos de desempenho
- Erros frequentemente crípticos

**FilterMate**: Sistema de feedback abrangente
- ✅ Mensagens de sucesso com contagem de feições
- ⚠️ Avisos de desempenho para grandes conjuntos de dados
- 🔄 Indicadores de reprojeção de SRC
- 🌍 Avisos de manipulação de coordenadas geográficas
- ⚡ Indicadores de desempenho de backend
- Mensagens de erro detalhadas com contexto

**Valor no Mundo Real**:
- Entender o que está acontecendo
- Prevenir problemas de desempenho
- Solucionar problemas mais rapidamente

---

## Quando QGIS Nativo É Melhor

### Vantagens da Caixa de Ferramentas de Processamento

**QGIS Nativo vence quando você precisa**:

1. **Algoritmos Especializados**
   - Operações topológicas complexas
   - Transformações geométricas avançadas
   - Ferramentas de análise estatística
   - Integração raster-vetor

2. **Processamento em Lote**
   - Múltiplas operações não relacionadas em sequência
   - Processamento em muitos arquivos desconectados
   - Fluxos de trabalho automatizados via Model Builder

3. **Algoritmos de Grafo**
   - Análise de rede (caminho mais curto, áreas de serviço)
   - Requer pgRouting (PostgreSQL) ou ferramentas QGIS

4. **Operações Raster**
   - FilterMate funciona apenas com dados vetoriais
   - Use Processamento para análise raster

---

### Aprendizado & Educação

**QGIS Nativo melhor para**:
- Entender conceitos GIS passo a passo
- Aprender funções individuais de ferramentas
- Ambientes acadêmicos/ensino
- Preparação para exames de certificação

**FilterMate melhor para**:
- Fluxos de trabalho de produção
- Projetos críticos de tempo
- Tarefas repetitivas
- Trabalho GIS do mundo real

---

## Caminho de Migração

### Começando com QGIS Nativo?

**Experimente FilterMate quando**:
1. ✅ Você fez o mesmo filtro 3+ vezes
2. ✅ Filtragem leva &gt;2 minutos manualmente
3. ✅ Trabalhando com &gt;50k feições
4. ✅ Combinando filtros de atributo + espaciais
5. ✅ Precisa de capacidade desfazer/refazer

**Estratégia de Transição**:
```
Semana 1: Aprenda básicos do FilterMate (filtros de atributo simples)
Semana 2: Experimente filtragem geométrica (predicados espaciais)
Semana 3: Use aba EXPORTAÇÃO para exportações filtradas
Semana 4: Salve Favoritos para filtros comuns
Semana 5+: Ferramenta principal, QGIS nativo para tarefas especializadas
```

---

### Já Usando FilterMate?

**Quando usar QGIS Nativo**:
- Processamento especializado não no FilterMate
- Automação Model Builder
- Aprendizado/ensino de conceitos específicos
- Solução de problemas (comparar resultados)

**Melhor Prática**: 
Use **FilterMate para 80% das tarefas de filtragem**, QGIS nativo para 20% especializados.

---

## Comparação de Desempenho: Números Reais

### Conjunto de Dados de Teste: Análise de Parcelas Urbanas

**Dados**:
- 125.000 polígonos de parcelas
- 5.000 linhas de estradas
- Tarefa: Encontrar parcelas residenciais dentro de 200m de estradas principais

**Hardware**: Laptop padrão (16GB RAM, SSD)

| Método | Tempo | Memória | Etapas | Camadas Resultado |
|--------|-------|---------|--------|-------------------|
| **Processamento QGIS (OGR)** | 287 segundos | 4,2 GB | 5 | 3 camadas |
| **Processamento QGIS (PostGIS)** | 12 segundos | 0,5 GB | 4 | 2 camadas |
| **FilterMate (OGR)** | 45 segundos | 1,8 GB | 1 | 1 camada (filtrada) |
| **FilterMate (Spatialite)** | 8,3 segundos | 0,6 GB | 1 | 1 camada (filtrada) |
| **FilterMate (PostgreSQL)** | 1,2 segundos | 0,3 GB | 1 | 1 camada (filtrada) |

**Insights Chave**:
- FilterMate (PostgreSQL): **240× mais rápido** que Processamento QGIS (OGR)
- FilterMate (Spatialite): **35× mais rápido** que Processamento QGIS (OGR)
- Até FilterMate (OGR): **6× mais rápido** devido ao fluxo de trabalho otimizado

---

## Análise Custo-Benefício

### Investimento de Tempo

**Curva de Aprendizado**:
- **Processamento QGIS**: 2-4 semanas para dominar ferramentas
- **FilterMate**: 2-4 horas para se tornar proficiente
- **FilterMate Avançado**: 1-2 dias para otimização

**Tempo de Configuração**:
- **Processamento QGIS**: Integrado (0 minutos)
- **FilterMate**: Instalação de plugin (2 minutos)
- **FilterMate + PostgreSQL**: Configuração completa (30-60 minutos)

---

### Economia de Tempo

**Usuário Diário** (10 filtros/dia):
- Tempo manual: ~60 minutos
- Tempo FilterMate: ~15 minutos
- **Economia: 45 minutos/dia = 180 horas/ano**

**Usuário Semanal** (20 filtros/semana):
- Tempo manual: ~120 minutos/semana
- Tempo FilterMate: ~30 minutos/semana
- **Economia: 90 minutos/semana = 75 horas/ano**

**Usuário Mensal** (10 filtros/mês):
- Tempo manual: ~60 minutos/mês
- Tempo FilterMate: ~15 minutos/mês
- **Economia: 45 minutos/mês = 9 horas/ano**

---

### Análise de Break-Even

**Instalação FilterMate** (2 minutos):
- Break-even após: **1-2 filtros**

**Configuração PostgreSQL** (60 minutos):
- Break-even após: **15-30 filtros** (grandes conjuntos de dados)
- Ou: **2-3 horas** de trabalho de filtragem

**Retorno sobre Investimento**: 
- FilterMate: **Imediato** (primeiro uso)
- PostgreSQL: **Na primeira semana** para usuários avançados

---

## Recomendações Resumidas

### Use FilterMate Quando...

✅ **Desempenho importa**
- Grandes conjuntos de dados (&gt;50k feições)
- Consultas espaciais complexas
- Fluxos de trabalho repetitivos

✅ **Eficiência importa**
- Operações multi-camadas
- Filtros combinados de atributo + espaciais
- Exportações filtradas frequentes

✅ **Conveniência importa**
- Precisa de capacidade desfazer/refazer
- Histórico de filtros com rastreamento de sessão
- Prefere interface integrada

---

### Use QGIS Nativo Quando...

✅ **Ferramentas especializadas necessárias**
- Operações raster
- Ferramentas topológicas avançadas
- Análise de rede
- Processamento estatístico

✅ **Aprendizado/Ensino**
- Entender etapas individuais
- Ambientes acadêmicos
- Demonstrar conceitos

✅ **Tarefas simples pontuais**
- Seleções rápidas no mapa
- Filtros de atributo de camada única
- Explorar dados desconhecidos

---

## Conclusão

**FilterMate complementa ferramentas nativas do QGIS**, não as substitui.

**Pense nisso como**:
- **Furadeira elétrica** (FilterMate) vs **Chave de fenda manual** (QGIS nativo)
- Ambos têm seu lugar
- Furadeira elétrica economiza tempo na maioria das tarefas
- Chave de fenda manual melhor para trabalho delicado

**Fluxo de Trabalho Recomendado**:
```
80% de filtragem → FilterMate (velocidade & eficiência)
20% de tarefas especializadas → Processamento QGIS (flexibilidade)
```

**Resumindo**: 
Instale FilterMate. Use-o para filtragem diária. Volte para QGIS nativo para tarefas especializadas. **O melhor dos dois mundos.**

---

## Próximos Passos

1. **Instalar FilterMate**: [Guia de Instalação](../installation)
2. **Início Rápido**: [Tutorial de 5 minutos](../getting-started/quick-start)
3. **Aprender Fluxos de Trabalho**: [Exemplos do mundo real](../workflows/)
4. **Otimizar Desempenho**: [Configuração de backends](../backends/choosing-backend)

---

**Perguntas?** Pergunte em [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
