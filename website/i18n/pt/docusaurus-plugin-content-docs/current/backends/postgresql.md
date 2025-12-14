---
sidebar_position: 2
---

# Backend PostgreSQL

O backend PostgreSQL fornece **desempenho ideal** para o FilterMate, especialmente com grandes conjuntos de dados. Ele aproveita operações espaciais no servidor, views materializadas e índices espaciais para filtragem ultra-rápida.

:::tip Campeão de desempenho
PostgreSQL é recomendado para conjuntos de dados com **mais de 50.000 feições** e obrigatório para conjuntos com **mais de 500.000 feições**.
:::

## Visão geral

O backend PostgreSQL do FilterMate conecta-se diretamente ao seu banco de dados PostGIS para realizar operações de filtragem geométrica no servidor. Esta abordagem reduz drasticamente a transferência de dados e o tempo de processamento em comparação com a filtragem do lado do cliente.

### Principais benefícios

- ⚡ **Consultas em menos de um segundo** em conjuntos de dados com milhões de feições
- 🔧 **Views materializadas** para resultados filtrados persistentes
- 🗺️ **Índices espaciais GIST** para buscas espaciais otimizadas
- 🚀 **Processamento no servidor** reduz sobrecarga de rede
- 💾 **Eficiente em memória** - processa dados no banco de dados
- ⚙️ **Operações concorrentes** - múltiplos filtros não desaceleram

## Quando o backend PostgreSQL é usado

O FilterMate seleciona automaticamente o backend PostgreSQL quando:

1. ✅ A fonte da camada é PostgreSQL/PostGIS
2. ✅ O pacote Python `psycopg2` está instalado
3. ✅ A conexão com o banco de dados está disponível

Se `psycopg2` **não** estiver instalado, o FilterMate faz fallback para os backends Spatialite ou OGR com um aviso de desempenho para grandes conjuntos de dados.

## Instalação

### Pré-requisitos

- **PostgreSQL 9.5+** com extensão **PostGIS 2.3+**
- **QGIS 3.x** com conexão PostgreSQL configurada
- **Python 3.7+** (incluído com QGIS)

### Instalando psycopg2

Escolha o método que funciona melhor para seu ambiente:

#### Método 1: pip (Recomendado)

```bash
pip install psycopg2-binary
```

#### Método 2: Console Python QGIS

Abra o Console Python QGIS (Ctrl+Alt+P) e execute:

```python
import pip
pip.main(['install', 'psycopg2-binary'])
```

#### Método 3: OSGeo4W Shell (Windows)

```bash
# Abrir OSGeo4W Shell como Administrador
py3_env
pip install psycopg2-binary
```

### Verificação

Verifique se psycopg2 está disponível:

```python
# No Console Python QGIS
try:
    import psycopg2
    print(f"✓ Versão psycopg2: {psycopg2.__version__}")
except ImportError:
    print("✗ psycopg2 não instalado")
```

## Recursos

### 1. Views materializadas

O FilterMate cria **views materializadas** no PostgreSQL para armazenar resultados filtrados de forma persistente:

```sql
-- Exemplo de view materializada criada pelo FilterMate
CREATE MATERIALIZED VIEW filtermate_filtered_view_123 AS
SELECT *
FROM minha_camada
WHERE ST_Intersects(
    geometry,
    (SELECT geometry FROM camada_filtro WHERE id = 1)
);

-- Índice espacial criado automaticamente
CREATE INDEX idx_filtermate_filtered_view_123_geom
ON filtermate_filtered_view_123
USING GIST (geometry);
```

**Benefícios:**
- Resultados em cache no banco de dados
- Atualização instantânea em filtros subsequentes
- Compartilhável entre sessões QGIS
- Limpeza automática ao fechar o plugin

### 2. Operações espaciais no servidor

Todas as operações geométricas são executadas **no banco de dados**:

- `ST_Intersects()` - Encontrar feições que intersectam
- `ST_Contains()` - Encontrar feições que contêm
- `ST_Within()` - Encontrar feições dentro dos limites
- `ST_Buffer()` - Criar buffers no servidor
- `ST_Distance()` - Calcular distâncias

**Impacto no desempenho:**

| Operação | Lado do cliente (Python) | Lado do servidor (PostGIS) |
|----------|-------------------------|---------------------------|
| 10k feições | ~5 segundos | ~0.5 segundos (10x mais rápido) |
| 100k feições | ~60 segundos | ~2 segundos (30x mais rápido) |
| 1M feições | Timeout/crash | ~10 segundos (100x+ mais rápido) |

### 3. Índices espaciais GIST

O FilterMate garante que suas geometrias tenham **índices GIST** para desempenho de consulta ideal:

```sql
-- Verificar índices existentes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'minha_camada';

-- FilterMate cria índices GIST automaticamente
CREATE INDEX IF NOT EXISTS idx_minha_camada_geom
ON minha_camada
USING GIST (geometry);
```

:::info Gerenciamento automático de índices
O FilterMate verifica os índices espaciais e os cria se estiverem faltando. Esta operação única pode levar alguns segundos em tabelas grandes.
:::

## Configuração

### Conexão com o banco de dados

O FilterMate usa a conexão PostgreSQL existente do QGIS. Certifique-se de que sua conexão está configurada:

1. **Camada → Gerenciador de fontes de dados → PostgreSQL**
2. **Nova** conexão com os detalhes:
   - Nome: `meu_banco_postgis`
   - Host: `localhost` (ou host remoto)
   - Porta: `5432`
   - Banco de dados: `meu_banco`
   - Autenticação: Básica ou credenciais armazenadas

### Configurações de desempenho

Otimize PostgreSQL para consultas espaciais:

```sql
-- Em postgresql.conf ou por sessão

-- Aumentar memória de trabalho para grandes ordenações
SET work_mem = '256MB';

-- Habilitar execução paralela de consultas
SET max_parallel_workers_per_gather = 4;

-- Otimizar para operações espaciais
SET random_page_cost = 1.1;  -- Para armazenamento SSD
```

## Solução de problemas

### Problema: "psycopg2 não encontrado"

**Sintoma:** FilterMate mostra backend OGR/Spatialite para camadas PostgreSQL

**Solução:**
1. Instalar psycopg2 (veja a seção de Instalação)
2. Reiniciar QGIS
3. Verificar instalação no Console Python

### Problema: "Consultas lentas apesar do PostgreSQL"

**Sintoma:** Consultas demoram mais que o esperado

**Solução:**
1. **Verificar índices espaciais:**
   ```sql
   SELECT * FROM pg_indexes WHERE tablename = 'sua_tabela';
   ```

2. **Executar ANALYZE:**
   ```sql
   ANALYZE sua_tabela;
   ```

3. **Verificar plano de consulta:**
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM sua_tabela
   WHERE ST_Intersects(geometry, ST_GeomFromText('POLYGON(...)'));
   ```

4. **Procure "Seq Scan"** - se presente, o índice não está sendo usado

## Benchmarks de desempenho

Desempenho real em hardware típico (Core i7, 16GB RAM, SSD):

| Tamanho do conjunto | Feições | PostgreSQL | Spatialite | Aceleração |
|---------------------|---------|-----------|-----------|------------|
| Pequeno | 5.000 | 0.3s | 0.4s | 1.3x |
| Médio | 50.000 | 1.2s | 8.5s | 7x |
| Grande | 500.000 | 8.4s | 65s | 8x |
| Muito grande | 5.000.000 | 45s | Timeout | 10x+ |

## Boas práticas

### ✅ Fazer

- **Usar PostgreSQL para conjuntos de dados > 50k feições**
- **Garantir que índices espaciais existam antes de filtrar**
- **Executar VACUUM ANALYZE após atualizações em massa**
- **Usar pool de conexões para múltiplos filtros**
- **Monitorar desempenho de consultas com EXPLAIN**

### ❌ Evitar

- **Não misturar sistemas de referência espacial** - reprojetar antes
- **Não criar muitas views materializadas** - FilterMate limpa automaticamente
- **Não desabilitar índices espaciais** - enorme penalidade de desempenho
- **Não executar expressões complexas sem testar** - use EXPLAIN primeiro

## Veja também

- [Visão geral dos backends](./overview.md) - Arquitetura multi-backend
- [Seleção de backend](./choosing-backend.md) - Lógica de seleção automática
- [Comparação de desempenho](./performance-benchmarks.md) - Benchmarks detalhados
- [Backend Spatialite](./spatialite.md) - Alternativa para conjuntos menores

---

**Última atualização:** 14 de dezembro de 2025  
**Versão do plugin:** 2.3.0  
**Suporte PostgreSQL:** 9.5+ com PostGIS 2.3+
