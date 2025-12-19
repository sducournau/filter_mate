---
sidebar_position: 8
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Erros Comuns e Soluções

Evite armadilhas frequentes e resolva problemas rapidamente com este guia de solução de problemas.

## Visão Geral

Este guia documenta os erros mais comuns que os usuários encontram ao usar o FilterMate, com soluções claras e estratégias de prevenção.

**Navegação Rápida**:
- [Resultados de Filtro Vazios](#1-resultados-de-filtro-vazios)
- [Backend PostgreSQL Indisponível](#2-backend-postgresql-indisponível)
- [Desempenho Lento](#3-desempenho-lento-30-segundos)
- [Resultados Espaciais Incorretos](#4-resultados-espaciais-incorretos)
- [Erros de Expressão](#5-erros-de-sintaxe-de-expressão)
- [Falhas de Exportação](#6-falhas-de-exportação)
- [Histórico de Filtros Perdido](#7-histórico-de-filtros-perdido-após-reinício)
- [Problemas de CRS](#8-problemas-de-incompatibilidade-de-crs)

---

## 1. Resultados de Filtro Vazios {#1-resultados-de-filtro-vazios}

**Sintoma**: O filtro retorna 0 feições, mas você esperava correspondências.

### Causas Comuns

#### Causa A: Incompatibilidade de CRS
**Problema**: As camadas têm sistemas de coordenadas diferentes que não se sobrepõem geograficamente.

**Exemplo**:
```
Camada 1: EPSG:4326 (WGS84) - Coordenadas globais
Camada 2: EPSG:2154 (Lambert 93) - Apenas França
```

**Solução**:
✅ O FilterMate lida com a reprojeção de CRS automaticamente, mas verifique se as camadas se sobrepõem:
1. Clique com o botão direito em cada camada → **Zoom para Camada**
2. Verifique se ambas as camadas aparecem na mesma área geográfica
3. Procure o indicador 🔄 de reprojeção nos logs do FilterMate

**Prevenção**:
- Use camadas da mesma região geográfica
- Verifique a extensão da camada em Propriedades → Informação

---

#### Causa B: Geometrias Inválidas
**Problema**: Geometrias corrompidas ou auto-intersectantes impedem operações espaciais.

**Sintomas**:
- "Erro GEOS" nos logs
- Resultados inconsistentes
- Algumas feições ausentes inesperadamente

**Solução**:
✅ Execute reparo de geometria antes de filtrar:
```bash
# Na Caixa de Ferramentas de Processamento QGIS
1. Geometria vetorial → Corrigir geometrias
2. Entrada: Sua camada problemática
3. Saída: camada_corrigida
4. Use a camada corrigida no FilterMate
```

**Verificação Rápida**:
```bash
# Caixa de Ferramentas de Processamento
Geometria vetorial → Verificar validade
```

---

#### Causa C: Distância de Buffer Muito Pequena
**Problema**: A zona de buffer não alcança nenhuma feição.

**Exemplo**:
```
Buffer: 10 metros
Realidade: A feição mais próxima está a 50 metros
Resultado: 0 feições encontradas
```

**Solução**:
✅ Aumente progressivamente a distância do buffer:
```
Tente: 50m → 100m → 500m → 1000m
```

✅ Teste primeiro sem buffer:
- Use o predicado "Intersects" sem buffer
- Se isso retornar resultados, a distância do buffer é o problema

---

#### Causa D: Valores de Atributo Errados
**Problema**: Filtrando por valores que não existem nos dados.

**Exemplo**:
```sql
-- Sua expressão:
city = 'Paris'

-- Valores reais nos dados:
city = 'PARIS' (maiúsculas)
city = 'Paris, France' (inclui país)
```

**Solução**:
✅ Verifique os valores reais dos campos primeiro:
1. Clique com o botão direito na camada → **Tabela de Atributos**
2. Observe os valores reais no campo
3. Ajuste a expressão para corresponder exatamente

✅ Use correspondência insensível a maiúsculas:
```sql
-- Em vez de:
city = 'Paris'

-- Use:
upper(city) = 'PARIS'
-- ou
city ILIKE 'paris'
```

---

#### Causa E: As Camadas Não se Sobrepõem Geograficamente
**Problema**: A camada de referência e a camada alvo estão em locais diferentes.

**Exemplo**:
```
Alvo: Edifícios em Nova York
Referência: Estradas em Londres
Resultado: Sem sobreposição = 0 resultados
```

**Solução**:
✅ Verifique a sobreposição geográfica:
1. Selecione ambas as camadas no Painel de Camadas
2. Clique com o botão direito → **Zoom para Camadas**
3. Ambas devem aparecer na mesma visualização do mapa

---

### Fluxo de Trabalho de Depuração para Resultados Vazios

**Passo 1**: Teste com expressão simples
```sql
1 = 1  -- Deve retornar TODAS as feições
```
Se isso falhar → Problema de backend ou camada

**Passo 2**: Teste apenas o filtro de atributo
```sql
-- Remova o filtro espacial
-- Teste: population > 0
```
Se isso funcionar → Problema de configuração espacial

**Passo 3**: Teste apenas o filtro espacial
```sql
-- Remova o filtro de atributo
-- Use um "Intersects" básico sem buffer
```
Se isso funcionar → Problema de expressão de atributo

**Passo 4**: Verifique os logs
```
QGIS → Visualizar → Painéis → Mensagens de Log → FilterMate
Procure mensagens de erro em vermelho
```

---

## 2. Backend PostgreSQL Indisponível {#2-backend-postgresql-indisponível}

**Sintoma**: Mensagem de aviso: `Backend PostgreSQL indisponível - usando fallback`

### Causa Raiz

**Problema**: O pacote Python `psycopg2` não está instalado no ambiente Python do QGIS.

**Impacto**:
- Desempenho 10-50× mais lento em grandes conjuntos de dados
- Sem views materializadas ou processamento no servidor
- Fallback para backend Spatialite ou OGR

---

### Solução: Instalar psycopg2

<Tabs>
  <TabItem value="windows" label="Windows" default>
    ```bash
    # Método A: Shell OSGeo4W (Recomendado)
    # Abra o Shell OSGeo4W como Administrador
    # Execute estes comandos:
    py3_env
    pip install psycopg2-binary
    
    # Método B: Console Python QGIS
    # QGIS → Plugins → Console Python
    # Execute este código:
    import subprocess
    subprocess.check_call(['python', '-m', 'pip', 'install', 'psycopg2-binary'])
    ```
  </TabItem>
  
  <TabItem value="linux" label="Linux">
    ```bash
    # Ubuntu/Debian
    sudo apt-get install python3-psycopg2
    
    # Ou via pip
    pip3 install psycopg2-binary
    
    # Verificar instalação
    python3 -c "import psycopg2; print(psycopg2.__version__)"
    ```
  </TabItem>
  
  <TabItem value="macos" label="macOS">
    ```bash
    # Via pip (Python QGIS)
    /Applications/QGIS.app/Contents/MacOS/bin/pip3 install psycopg2-binary
    
    # Ou via Homebrew
    brew install postgresql
    pip3 install psycopg2-binary
    ```
  </TabItem>
</Tabs>

---

### Verificação

**Verifique se psycopg2 está instalado**:
```python
# Console Python QGIS
import psycopg2
print(psycopg2.__version__)
# Esperado: '2.9.x (dt dec pq3 ext lo64)'
```

**Verifique os logs do FilterMate**:
```
✅ Sucesso: "Backend PostgreSQL disponível"
❌ Aviso: "psycopg2 não encontrado, usando Spatialite"
```

---

### Quando NÃO se Preocupar

**Você pode pular a instalação do PostgreSQL se**:
- Conjunto de dados com `<10.000` feições (Spatialite é rápido o suficiente)
- Usando camadas OGR (Shapefile, GeoPackage) e não pode migrar
- Filtragem apenas ocasional (desempenho não crítico)
- Nenhum banco de dados PostgreSQL disponível

---

## 3. Desempenho Lento (>30 segundos) {#3-desempenho-lento-30-segundos}

**Sintoma**: A operação de filtro leva mais de 30 segundos.

### Diagnóstico

**Verifique o backend em uso**:
```
Painel FilterMate → Info da camada:
Provider: ogr (⚠️ Mais lento)
Provider: spatialite (⏱️ Médio)
Provider: postgresql (⚡ Mais rápido)
```

---

### Soluções por Backend

#### Backend OGR (Shapefile, GeoPackage)

**Problema**: Sem índices espaciais nativos, processamento em memória.

**Solução 1**: Migrar para PostgreSQL
```bash
# Melhor para conjuntos de dados >50k feições
1. Configure PostgreSQL+PostGIS
2. Gerenciador BD → Importar camada
3. Reconecte no QGIS
4. Aceleração de 10-50×
```

**Solução 2**: Migrar para Spatialite
```bash
# Bom para conjuntos de dados 10k-50k feições
1. Caixa de Ferramentas de Processamento → Vetor geral → Empacotar camadas
2. Escolha formato Spatialite
3. Aceleração de 3-5× vs Shapefile
```

**Solução 3**: Otimizar a consulta
```sql
-- Adicione filtro de atributo PRIMEIRO (reduz escopo da consulta espacial)
population > 10000 AND ...consulta espacial...

-- Em vez de:
...consulta espacial... AND population > 10000
```

---

#### Backend Spatialite

**Problema**: Grande conjunto de dados (>50k feições).

**Solução**: Migrar para PostgreSQL
- Melhoria esperada: 5-10× mais rápido
- Consultas em menos de um segundo em 100k+ feições

**Contorno**: Reduzir escopo da consulta
```sql
-- Pré-filtrar com bounding box
bbox($geometry, 
     $xmin, $ymin, 
     $xmax, $ymax)
AND ...seu filtro...
```

---

#### Backend PostgreSQL (Já Rápido)

**Problema**: Lento apesar de usar PostgreSQL (raro).

**Causas Possíveis**:
1. ❌ Índice espacial ausente
2. ❌ Geometrias inválidas
3. ❌ Latência de rede (banco de dados remoto)

**Soluções**:
```sql
-- 1. Verifique se o índice espacial existe
SELECT * FROM pg_indexes 
WHERE tablename = 'sua_tabela' 
  AND indexdef LIKE '%GIST%';

-- 2. Crie índice se ausente
CREATE INDEX idx_geom ON sua_tabela USING GIST(geom);

-- 3. Corrija geometrias
UPDATE sua_tabela SET geom = ST_MakeValid(geom);
```

---

### Benchmarks de Desempenho

| Backend | 10k feições | 50k feições | 100k feições |
|---------|-------------|-------------|--------------|
| PostgreSQL | 0.1s ⚡ | 0.3s ⚡ | 0.8s ⚡ |
| Spatialite | 0.4s ✓ | 4.5s ⏱️ | 18s ⏱️ |
| OGR (GPKG) | 2.1s | 25s ⚠️ | 95s 🐌 |
| OGR (SHP) | 3.8s | 45s 🐌 | 180s 🐌 |

**Recomendação**: Use PostgreSQL para >50k feições.

---

## 4. Resultados Espaciais Incorretos {#4-resultados-espaciais-incorretos}

**Sintoma**: Feições distantes da geometria de referência estão incluídas nos resultados.

### Causas Comuns

#### Causa A: Distância de Buffer em Unidades Erradas

**Problema**: Usando graus quando você precisa de metros (ou vice-versa).

**Exemplo**:
```
Buffer: 500 (assumido metros)
CRS da camada: EPSG:4326 (graus!)
Resultado: Buffer de 500 graus (~55.000 km!)
```

**Solução**:
✅ O FilterMate auto-converte CRS geográfico para EPSG:3857 para buffers métricos
- Procure o indicador 🌍 nos logs
- Verificação manual: Propriedades da Camada → Informação → Unidades CRS

✅ Use CRS apropriado:
```
Graus: EPSG:4326 (WGS84) - Auto-convertido ✓
Metros: EPSG:3857 (Web Mercator)
Metros: Zonas UTM locais (mais precisas)
```

---

#### Causa B: Predicado Espacial Errado

**Problema**: Usando "Contains" quando você precisa de "Intersects".

**Significado dos Predicados**:
```
Intersects: Toca ou sobrepõe (mais permissivo)
Contains: A envolve completamente B (estrito)
Within: A completamente dentro de B (oposto de Contains)
Crosses: Interseção linear apenas
```

**Exemplo**:
```
❌ Errado: Contains
   - Encontra parcelas que CONTÊM estradas (oposto!)
   
✅ Correto: Intersects
   - Encontra parcelas que TOCAM estradas
```

**Solução**:
Veja o [Guia de Predicados Espaciais](../reference/cheat-sheets/spatial-predicates) para um guia visual.

---

#### Causa C: Camada de Referência Errada

**Problema**: Camada errada selecionada como referência espacial.

**Exemplo**:
```
Objetivo: Edifícios perto de ESTRADAS
Real: Camada de referência = RIOS
Resultado: Feições erradas selecionadas
```

**Solução**:
✅ Verifique novamente o dropdown da camada de referência:
- O nome da camada deve corresponder à sua intenção
- O ícone mostra o tipo de geometria (ponto/linha/polígono)

---

### Passos de Verificação

**Verificação Manual**:
1. Use a **Ferramenta de Medição** do QGIS (Ctrl+Shift+M)
2. Meça a distância da feição filtrada até a feição de referência mais próxima
3. A distância deve ser ≤ sua configuração de buffer

**Verificação Visual**:
1. **Ferramenta de Identificação** → Clique na feição de referência
2. Clique direito → **Zoom para Feição**
3. Observe as feições filtradas ao redor
4. Elas devem formar um anel ao redor da feição de referência (se buffer usado)

---

## 5. Erros de Sintaxe de Expressão {#5-erros-de-sintaxe-de-expressão}

**Sintoma**: ✗ vermelho no construtor de expressão com mensagem de erro.

### Erros de Sintaxe Comuns

#### Aspas Faltando ao Redor do Texto

```sql
❌ Errado:
city = Paris

✅ Correto:
city = 'Paris'
```

---

#### Nomes de Campos Sensíveis a Maiúsculas (Spatialite)

```sql
❌ Errado (Spatialite):
name = 'test'  -- Campo é 'NAME', não 'name'

✅ Correto:
"NAME" = 'test'  -- Aspas duplas para campos sensíveis a maiúsculas
```

---

#### Usando = com NULL

```sql
❌ Errado:
population = NULL

✅ Correto:
population IS NULL
```

---

#### Concatenação de Strings

```sql
❌ Errado:
city + ', ' + country

✅ Correto:
city || ', ' || country
```

---

#### Comparações de Data

```sql
❌ Errado:
date_field > '2024-01-01'  -- Comparação de string

✅ Correto:
date_field > to_date('2024-01-01')
-- ou
year(date_field) = 2024
```

---

### Depuração de Expressão

**Passo 1**: Teste no Construtor de Expressão
```
Camada QGIS → Abrir Tabela de Atributos → 
Calculadora de Campo → Teste a expressão
```

**Passo 2**: Use Visualização de Expressão
```
Clique no botão "Visualizar" para ver resultado na primeira feição
```

**Passo 3**: Simplifique a Expressão
```sql
-- Comece simples:
1 = 1  -- Sempre verdadeiro

-- Adicione complexidade gradualmente:
city = 'Paris'
city = 'Paris' AND population > 100000
```

---

## 6. Falhas de Exportação {#6-falhas-de-exportação}

**Sintoma**: O botão de exportação não faz nada ou mostra erro.

### Causas Comuns

#### Causa A: Permissão Negada

**Problema**: Não é possível escrever na pasta de destino.

**Solução**:
```bash
# Windows: Escolha pasta do usuário
C:\Users\SeuNome\Documents\

# Linux/macOS: Verifique permissões
chmod 755 /caminho/para/pasta/saida
```

---

#### Causa B: Caracteres Inválidos no Nome do Arquivo

**Problema**: Caracteres especiais não permitidos pelo sistema de arquivos.

```bash
❌ Errado:
exports/data:2024.gpkg  -- Dois-pontos não permitido (Windows)

✅ Correto:
exports/data_2024.gpkg
```

---

#### Causa C: CRS Alvo Inválido

**Problema**: O CRS selecionado não existe ou não é reconhecido.

**Solução**:
✅ Use códigos CRS comuns:
```
EPSG:4326 - WGS84 (mundial)
EPSG:3857 - Web Mercator (mapas web)
EPSG:2154 - Lambert 93 (França)
```

---

#### Causa D: Nome da Camada Contém Espaços (exportação PostgreSQL)

**Problema**: Nomes de tabela PostgreSQL com espaços requerem aspas.

**Solução**:
```sql
❌ Errado: meu nome de camada

✅ Correto: meu_nome_de_camada
```

---

## 7. Histórico de Filtros Perdido Após Reinício {#7-histórico-de-filtros-perdido-após-reinício}

**Sintoma**: O histórico Desfazer/Refazer está vazio após fechar o QGIS.

### Comportamento Esperado

**O histórico de filtros é baseado em sessão** - não é salvo no arquivo de projeto QGIS.

**Por quê**:
- O histórico pode se tornar grande (100+ operações)
- Pode conter critérios de filtro sensíveis
- Otimização de desempenho

---

### Contorno: Use Variáveis de Projeto QGIS

**Salve expressões de filtro importantes**:
1. Vá para **Projeto → Propriedades → Variáveis**
2. Crie uma nova variável (ex: `minha_expressao_filtro`)
3. Cole sua expressão de filtro como valor
4. Use no FilterMate referenciando `@minha_expressao_filtro`

**Alternativa: Notas da Camada**:
1. Clique direito na camada → **Propriedades → Metadados**
2. Adicione suas expressões de filtro no campo **Resumo**
3. Copie/cole quando necessário

:::tip Recurso Planejado
**Filtros Favoritos** (salvar/recuperar filtros usados frequentemente) está planejado para uma versão futura.
:::

---

## 8. Problemas de Incompatibilidade de CRS {#8-problemas-de-incompatibilidade-de-crs}

**Sintoma**: Feições aparecem no local errado ou consultas espaciais falham.

### Tratamento Automático de CRS

**O FilterMate reprojeta automaticamente as camadas** durante operações espaciais.

**Você verá**:
```
🔄 Reprojetando camada de EPSG:4326 para EPSG:3857
```

**Isso é NORMAL e esperado** - nenhuma ação necessária.

---

### Quando CRS Causa Problemas

#### Problema: CRS Geográfico Usado para Buffers

**Problema**: Distância de buffer interpretada como graus em vez de metros.

**Solução FilterMate**:
✅ Converte automaticamente EPSG:4326 → EPSG:3857 para operações métricas
- O indicador 🌍 aparece nos logs
- Nenhuma intervenção manual necessária

**Substituição Manual** (se necessário):
1. Clique direito na camada → **Exportar** → **Salvar Feições Como**
2. Defina CRS para sistema projetado local (UTM, State Plane, etc.)
3. Use a camada exportada no FilterMate

---

#### Problema: Camada Mostra Local Errado

**Problema**: Camada tem CRS errado atribuído.

**Sintomas**:
- Camada aparece longe do local esperado
- Pode estar do lado oposto do mundo
- Pula para 0°,0° (Golfo da Guiné)

**Solução**:
```bash
# Corrija o CRS da camada
1. Clique direito na camada → Definir CRS da Camada
2. Selecione o CRS correto (verifique documentação dos dados)
3. Não use "Definir CRS do Projeto a partir da Camada" - corrige apenas a exibição
```

**Identificar CRS Correto**:
- Verifique arquivo de metadados (.xml, .prj, .qmd)
- Observe valores de coordenadas na tabela de atributos
  - Números grandes (ex: 500.000) → CRS Projetado
  - Números pequenos (-180 a 180) → CRS Geográfico
- Pesquise no Google a fonte dos dados para informações de CRS

---

## Lista de Verificação de Prevenção

Antes de filtrar, verifique:

### Qualidade dos Dados
- [ ] Camadas carregam e exibem corretamente
- [ ] Geometrias são válidas (execute Verificar Geometrias)
- [ ] Tabela de atributos tem valores esperados
- [ ] Camadas se sobrepõem geograficamente

### Configuração
- [ ] Camada alvo correta selecionada
- [ ] Camada de referência correta (para consultas espaciais)
- [ ] Expressão mostra marca de verificação verde ✓
- [ ] Distância e unidades de buffer apropriadas
- [ ] Predicado espacial corresponde à intenção

### Desempenho
- [ ] Tipo de backend é apropriado para tamanho do conjunto de dados
- [ ] psycopg2 instalado se usando PostgreSQL
- [ ] Índices espaciais existem (PostgreSQL)

---

## Obtendo Ajuda

### Recursos de Autoatendimento

1. **Verifique os Logs**: QGIS → Visualizar → Painéis → Mensagens de Log → FilterMate
2. **Leia a Mensagem de Erro**: Frequentemente diz exatamente o que está errado
3. **Pesquise a Documentação**: Use a barra de pesquisa (Ctrl+K)
4. **Tente uma Versão Simplificada**: Remova complexidade para isolar o problema

### Suporte da Comunidade

- 🐛 **Relatórios de Bugs**: [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Perguntas**: [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 📧 **Contato**: Inclua versão do QGIS, versão do FilterMate e logs de erro

---

## Resumo

**Erros Mais Comuns**:
1. Resultados vazios → Verifique valores de atributos e distância de buffer
2. PostgreSQL indisponível → Instale psycopg2
3. Desempenho lento → Use PostgreSQL para grandes conjuntos de dados
4. Resultados espaciais errados → Verifique unidades de buffer e predicado
5. Erros de expressão → Verifique sintaxe e nomes de campos

**Pontos-Chave**:
- O FilterMate lida com CRS automaticamente (procure indicadores)
- Sempre teste com expressões simplificadas primeiro
- Verifique os logs para mensagens de erro detalhadas
- PostgreSQL oferece melhor desempenho para >50k feições
- O histórico de filtros é baseado em sessão (use Favoritos para persistência)

---

**Ainda travado?** Consulte o [Guia de Solução de Problemas](../advanced/troubleshooting) ou pergunte no [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions).
