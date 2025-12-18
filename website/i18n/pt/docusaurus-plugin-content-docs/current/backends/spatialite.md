---
sidebar_position: 3
---

# Backend Spatialite

O backend Spatialite fornece **excelente desempenho** para conjuntos de dados pequenos a médios sem exigir servidores de banco de dados externos. Ele aproveita as capacidades espaciais integradas do SQLite com índices R-tree para filtragem eficiente.

:::tip Ponto ideal
Spatialite é ideal para conjuntos de dados com **menos de 50.000 feições** e não requer **nenhuma instalação adicional** — funciona diretamente com Python.
:::

## Visão geral

O backend Spatialite do FilterMate conecta-se a bancos de dados SQLite locais com a extensão espacial Spatialite. Ele cria tabelas temporárias com índices espaciais para realizar filtragem geométrica eficientemente.

### Principais benefícios

- ⚡ **Desempenho rápido** em conjuntos de dados < 50k feições
- 🔧 **Nenhuma configuração necessária** — SQLite integrado ao Python
- 📦 **Portátil** — banco de dados em arquivo único
- 🗺️ **Índices espaciais R-tree** para buscas otimizadas
- 💾 **Processamento local** — sem sobrecarga de rede
- 🚀 **Automático** — funciona imediatamente com arquivos .sqlite

## Quando o backend Spatialite é usado

O FilterMate seleciona automaticamente o backend Spatialite quando:

1. ✅ A fonte da camada é Spatialite/SQLite com extensão espacial
2. ✅ O caminho do arquivo aponta para um arquivo `.sqlite`, `.db` ou `.spatialite`
3. ✅ A extensão Spatialite está disponível (automaticamente em Python 3.7+)

:::info Aviso de desempenho
Para conjuntos de dados com **mais de 50.000 feições**, o FilterMate exibirá um aviso de desempenho sugerindo PostgreSQL para melhor desempenho.
:::

## Instalação

### Pré-requisitos

- **Python 3.7+** (incluído com QGIS 3.x)
- **Extensão Spatialite** (geralmente pré-instalada)

### Verificação

Spatialite geralmente está disponível por padrão. Verifique no Console Python QGIS:

```python
import sqlite3

conn = sqlite3.connect(':memory:')
conn.enable_load_extension(True)

try:
    conn.load_extension('mod_spatialite')
    print("✓ Extensão Spatialite disponível")
except Exception as e:
    # Fallback Windows
    try:
        conn.load_extension('mod_spatialite.dll')
        print("✓ Extensão Spatialite disponível (Windows)")
    except:
        print(f"✗ Extensão Spatialite não encontrada: {e}")

conn.close()
```

## Recursos

### 1. Tabelas temporárias

O FilterMate cria **tabelas temporárias** para armazenar resultados filtrados:

```sql
-- Exemplo de tabela temporária criada pelo FilterMate
CREATE TEMP TABLE filtermate_filtered_123 AS
SELECT *
FROM minha_camada
WHERE ST_Intersects(
    geometry,
    (SELECT geometry FROM camada_filtro WHERE id = 1)
);

-- Índice espacial criado automaticamente
SELECT CreateSpatialIndex('filtermate_filtered_123', 'geometry');
```

**Benefícios:**
- Criação e consultas rápidas
- Limpeza automática ao final da sessão
- Sem modificações permanentes no banco de dados
- Eficiente em memória para < 50k feições

### 2. Índices espaciais R-tree

Spatialite usa **índices R-tree** para consultas espaciais:

```sql
-- Verificar índices espaciais
SELECT * FROM geometry_columns
WHERE f_table_name = 'minha_camada';

-- FilterMate cria índices R-tree automaticamente
SELECT CreateSpatialIndex('minha_camada', 'geometry');

-- O índice é usado automaticamente para consultas espaciais
SELECT * FROM minha_camada
WHERE ST_Intersects(geometry, MakePoint(100, 50, 4326));
```

:::tip Impacto no desempenho
Índices R-tree fornecem aceleração de 10-100x em consultas espaciais, dependendo da distribuição dos dados.
:::

### 3. Operações espaciais

Spatialite suporta ~90% das funções PostGIS:

| Função | Spatialite | Equivalente |
|--------|-----------|-------------|
| `ST_Intersects()` | ✅ Suporte completo | Igual ao PostGIS |
| `ST_Contains()` | ✅ Suporte completo | Igual ao PostGIS |
| `ST_Within()` | ✅ Suporte completo | Igual ao PostGIS |
| `ST_Buffer()` | ✅ Suporte completo | Igual ao PostGIS |
| `ST_Distance()` | ✅ Suporte completo | Igual ao PostGIS |
| `ST_Area()` | ✅ Suporte completo | Igual ao PostGIS |
| `ST_Length()` | ✅ Suporte completo | Igual ao PostGIS |

## Limitações

### Comparado ao PostgreSQL

| Recurso | Spatialite | PostgreSQL |
|---------|-----------|-----------|
| Tamanho máx prático | ~500k feições | 10M+ feições |
| Acesso concorrente | Limitado | Excelente |
| Operações no servidor | ❌ Não | ✅ Sim |
| Consultas paralelas | ❌ Não | ✅ Sim |
| Acesso de rede | ❌ Não (baseado em arquivo) | ✅ Sim |

### Limitações conhecidas

1. **Usuário único** — O bloqueio de arquivo impede acesso concorrente real
2. **Sem processamento paralelo** — Consultas executam em thread única
3. **Restrições de memória** — Grandes operações podem consumir muita RAM

:::tip Quando mudar
Se você trabalha regularmente com **mais de 50k feições**, considere migrar para PostgreSQL para melhoria de desempenho de 5-10x.
:::

## Solução de problemas

### Problema: "Extensão Spatialite não encontrada"

**Sintoma:** Erro ao abrir banco de dados Spatialite

**Solução:**

1. **Verificar ambiente Python:**
   ```python
   import sqlite3
   print(sqlite3.sqlite_version)  # Deve ser 3.7+
   ```

2. **Tentar nomes de extensão alternativos:**
   ```python
   conn.load_extension('mod_spatialite')      # Linux/macOS
   conn.load_extension('mod_spatialite.dll')  # Windows
   conn.load_extension('libspatialite')       # Alternativa
   ```

### Problema: "Consultas lentas apesar do índice espacial"

**Sintoma:** A filtragem demora mais do que o esperado

**Solução:**

1. **Verificar se o índice espacial existe:**
   ```sql
   SELECT * FROM geometry_columns WHERE f_table_name = 'minha_camada';
   ```

2. **Reconstruir índice espacial:**
   ```sql
   SELECT DisableSpatialIndex('minha_camada', 'geometry');
   SELECT CreateSpatialIndex('minha_camada', 'geometry');
   ```

3. **Executar ANALYZE:**
   ```sql
   ANALYZE minha_camada;
   ```

## Benchmarks de desempenho

Desempenho real em hardware típico (Core i7, 16GB RAM, SSD):

| Tamanho do conjunto | Feições | Spatialite | PostgreSQL | Proporção |
|---------------------|---------|-----------|-----------|-----------|
| Pequeno | 5.000 | 0.4s | 0.3s | 1.3x mais lento |
| Médio | 50.000 | 8.5s | 1.2s | 7x mais lento |
| Grande | 500.000 | 65s | 8.4s | 8x mais lento |
| Muito grande | 5.000.000 | Timeout | 45s | Não viável |

## Boas práticas

### ✅ Fazer

- **Usar Spatialite para < 50k feições** — excelente desempenho
- **Criar índices espaciais** — enorme aumento de desempenho
- **Usar modo de journal WAL** — melhor concorrência
- **Executar VACUUM periodicamente** — mantém o desempenho

### ❌ Evitar

- **Não usar para > 500k feições** — muito lento
- **Não esquecer índices espaciais** — penalidade de desempenho de 10-100x
- **Não abrir o mesmo arquivo em múltiplos processos** — bloqueio de banco de dados

## Migrar para PostgreSQL

Se seu banco de dados Spatialite crescer demais:

### Opção 1: QGIS DB Manager

1. **Abrir DB Manager** (Banco de dados → DB Manager)
2. **Selecionar banco de dados Spatialite**
3. **Clique direito na camada → Exportar para PostgreSQL**
4. **Configurar conexão e importar**

### Opção 2: Linha de comando (ogr2ogr)

```bash
ogr2ogr -f PostgreSQL \
  PG:"host=localhost dbname=meubanco user=meuusuario password=minhasenha" \
  meus_dados.sqlite \
  -lco GEOMETRY_NAME=geometry \
  -lco SPATIAL_INDEX=GIST
```

## Veja também

- [Visão geral dos backends](./overview) — Arquitetura multi-backend
- [Seleção de backend](./choosing-backend) — Lógica de seleção automática
- [Backend PostgreSQL](./postgresql) — Para maiores conjuntos de dados
- [Comparação de desempenho](./performance-benchmarks) — Benchmarks detalhados

---

**Última atualização:** 14 de dezembro de 2025  
**Versão do plugin:** 2.3.0  
**Suporte Spatialite:** SQLite 3.7+ com Spatialite 4.3+
