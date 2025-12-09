---
sidebar_position: 2
---

# Instalação

O FilterMate está disponível através do Repositório de Plugins do QGIS e funciona imediatamente com qualquer instalação do QGIS.

## Instalação básica

1. Abra o QGIS
2. Vá para **Complementos** → **Gerenciar e instalar complementos**

 <img src="/filter_mate/img/install-1.png" alt="install-1" width="500"/>
 
*Gerenciador de plugins do QGIS - Pesquisa por FilterMate*

3. Pesquise por **"FilterMate"**

 <img src="/filter_mate/img/install-2.png" alt="install-2" width="500"/>

*Resultados da pesquisa mostrando o plugin FilterMate*

4. Clique em **Instalar plugin**

*FilterMate instalado com sucesso e pronto para usar*

Pronto! O FilterMate agora está pronto para uso com backends OGR e Spatialite.

## Opcional: Backend PostgreSQL (Recomendado para grandes conjuntos de dados)

Para desempenho ideal com camadas PostgreSQL/PostGIS, instale o pacote `psycopg2`.

:::tip Aumento de desempenho
O backend PostgreSQL fornece **filtragem 10-50× mais rápida** em grandes conjuntos de dados (>50.000 feições) em comparação com outros backends.
:::

### Método 1: pip (Recomendado)

```bash
pip install psycopg2-binary
```

### Método 2: Console Python do QGIS

1. Abra o Console Python do QGIS (**Complementos** → **Console Python**)
2. Execute:

```python
import pip
pip.main(['install', 'psycopg2-binary'])
```

### Método 3: Shell OSGeo4W (Windows)

1. Abra o **Shell OSGeo4W** como Administrador
2. Execute:

```bash
py3_env
pip install psycopg2-binary
```

### Verificar instalação

Verifique se o backend PostgreSQL está disponível:

```python
from modules.appUtils import POSTGRESQL_AVAILABLE
print(f"PostgreSQL disponível: {POSTGRESQL_AVAILABLE}")
```

Se `True`, está tudo pronto! O backend PostgreSQL será usado automaticamente para camadas PostGIS.

## Seleção de backend

O FilterMate seleciona automaticamente o backend ideal com base na sua fonte de dados:

| Fonte de dados | Backend usado | Instalação necessária |
|----------------|---------------|----------------------|
| PostgreSQL/PostGIS | PostgreSQL (se psycopg2 instalado) | Opcional: psycopg2 |
| Spatialite | Spatialite | Nenhuma (integrado) |
| Shapefile, GeoPackage, etc. | OGR | Nenhuma (integrado) |

Saiba mais sobre backends na [Visão geral dos backends](./backends/overview.md).

## Solução de problemas

### PostgreSQL não está sendo usado?

**Verifique se psycopg2 está instalado:**

```python
try:
    import psycopg2
    print("✅ psycopg2 instalado")
except ImportError:
    print("❌ psycopg2 não instalado")
```

**Problemas comuns:**
- A camada não é de fonte PostgreSQL → Use camadas PostGIS
- psycopg2 não está no ambiente Python do QGIS → Reinstale no ambiente correto
- Credenciais de conexão não salvas → Verifique configurações da fonte de dados da camada

## Próximos passos

- [Tutorial de início rápido](./getting-started/quick-start.md) - Aprenda o básico
- [Primeiro filtro](./getting-started/first-filter.md) - Crie seu primeiro filtro
- [Benchmarks de desempenho](./backends/performance-benchmarks.md) - Entenda o desempenho dos backends
