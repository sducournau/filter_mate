---
sidebar_position: 4
---

# Backend OGR

O backend OGR fornece **compatibilidade universal** com todos os formatos vetoriais suportados pelo QGIS através da biblioteca GDAL/OGR. Ele serve como um fallback confiável quando os backends PostgreSQL ou Spatialite não estão disponíveis.

:::tip Compatibilidade universal
O backend OGR funciona com **todos os formatos vetoriais**: Shapefiles, GeoPackage, GeoJSON, KML, DXF, CSV e mais de 80 outros formatos.
:::

## Visão geral

O backend OGR do FilterMate usa o framework de processamento do QGIS e camadas em memória para realizar filtragem geométrica. Embora não seja tão rápido quanto os backends de banco de dados para grandes conjuntos de dados, ele fornece excelente compatibilidade e não requer configuração adicional.

### Principais benefícios

- ✅ **Suporte universal de formatos** — funciona com qualquer formato legível pelo OGR
- 🔧 **Nenhuma configuração necessária** — integrado ao QGIS
- 📦 **Portátil** — funciona com arquivos locais e remotos
- 🌐 **Formatos web** — GeoJSON, KML, etc.
- 💾 **Camadas em memória** — processamento temporário em memória
- 🚀 **Automático** — fallback quando outros backends não estão disponíveis

## Quando o backend OGR é usado

O FilterMate seleciona automaticamente o backend OGR quando:

1. ✅ A fonte da camada **não** é PostgreSQL ou Spatialite
2. ✅ O provedor da camada é `ogr` (Shapefile, GeoPackage, etc.)
3. ✅ Fallback quando psycopg2 não está disponível para camadas PostgreSQL

**Formatos comuns usando o backend OGR:**
- Shapefile (`.shp`)
- GeoPackage (`.gpkg`)
- GeoJSON (`.geojson`, `.json`)
- KML/KMZ (`.kml`, `.kmz`)
- DXF/DWG (formatos CAD)
- CSV com geometria (`.csv`)
- GPS Exchange (`.gpx`)
- E mais de 80 outros formatos

## Instalação

### Pré-requisitos

- **QGIS 3.x** (inclui GDAL/OGR)
- **Nenhum pacote adicional necessário**

### Verificação

OGR está sempre disponível no QGIS. Verifique os formatos suportados:

```python
# No Console Python QGIS
from osgeo import ogr

driver_count = ogr.GetDriverCount()
print(f"✓ {driver_count} drivers OGR disponíveis")

# Listar alguns drivers comuns
for driver_name in ['ESRI Shapefile', 'GPKG', 'GeoJSON', 'KML']:
    driver = ogr.GetDriverByName(driver_name)
    if driver:
        print(f"  ✓ {driver_name}")
```

## Recursos

### 1. Camadas em memória

O FilterMate cria **camadas em memória** para resultados filtrados:

```python
# Exemplo de camada em memória criada pelo FilterMate
from qgis.core import QgsVectorLayer

memory_layer = QgsVectorLayer(
    f"Point?crs=epsg:4326&field=id:integer&field=name:string",
    "camada_filtrada",
    "memory"
)

# Copiar feições filtradas
for feature in source_layer.getFeatures(expression):
    memory_layer.dataProvider().addFeature(feature)
```

**Benefícios:**
- Criação rápida
- Sem E/S de disco
- Limpeza automática
- Funciona com todos os formatos

**Limitações:**
- Armazenado em RAM — não adequado para conjuntos muito grandes
- Perdido ao fechar o QGIS (a menos que salvo)

### 2. Matriz de compatibilidade de formatos

| Formato | Leitura | Escrita | Índice espacial | Desempenho |
|---------|---------|---------|-----------------|------------|
| Shapefile | ✅ | ✅ | ⚠️ Arquivos .qix | Bom |
| GeoPackage | ✅ | ✅ | ✅ R-tree | Excelente |
| GeoJSON | ✅ | ✅ | ❌ | Bom |
| KML/KMZ | ✅ | ✅ | ❌ | Bom |
| CSV | ✅ | ✅ | ❌ | Razoável |
| DXF/DWG | ✅ | ⚠️ Limitado | ❌ | Razoável |
| GPX | ✅ | ✅ | ❌ | Bom |
| FlatGeobuf | ✅ | ✅ | ✅ Integrado | Excelente |

:::tip Melhores formatos para o backend OGR
Para desempenho ideal: **GeoPackage** ou **FlatGeobuf** (ambos têm índices espaciais)
:::

## Configuração

### Opções específicas de formato

Configure o comportamento do backend OGR em `config/config.json`:

```json
{
  "OGR": {
    "use_memory_layers": true,
    "enable_spatial_index": true,
    "max_features_in_memory": 100000,
    "prefer_geopackage": true
  }
}
```

### Índices espaciais Shapefile

Para Shapefiles, crie o índice espacial `.qix`:

```python
# No Console Python QGIS
layer = iface.activeLayer()
layer.dataProvider().createSpatialIndex()

# Ou via processamento
processing.run("native:createspatialindex", {
    'INPUT': layer
})
```

Isso cria `meuarquivo.qix` ao lado de `meuarquivo.shp`.

## Utilização

### Filtragem básica

1. **Carregar qualquer camada vetorial** no QGIS
2. **Abrir o plugin FilterMate**
3. **Configurar as opções** de filtro
4. **Clicar em "Aplicar filtro"**

O FilterMate automaticamente:
- Detecta o backend OGR
- Cria uma camada em memória
- Copia as feições filtradas
- Adiciona a camada ao QGIS
- Exibe o indicador de backend: **[OGR]**

### Recomendações de formato

**Melhor desempenho:**
- GeoPackage (`.gpkg`) — tem índices espaciais
- FlatGeobuf (`.fgb`) — otimizado para streaming

**Bom desempenho:**
- Shapefile (`.shp`) — com índice `.qix`
- GeoJSON (`.geojson`) — para pequenos conjuntos de dados

**Desempenho aceitável:**
- KML (`.kml`) — para web/Google Earth
- CSV (`.csv`) — para dados pontuais simples

**Desempenho mais lento:**
- DXF/DWG — formatos CAD complexos
- Serviços remotos (WFS) — latência de rede

## Otimização de desempenho

### Para pequenos conjuntos de dados (< 10k feições)

- **Nenhuma configuração especial necessária**
- Todos os formatos funcionam bem
- Camadas em memória são rápidas

### Para conjuntos de dados médios (10k - 50k feições)

- **Use GeoPackage ou Shapefile com índice .qix**
- **Ative camadas em memória** (padrão)
- **Considere o backend Spatialite** em vez disso (5x mais rápido)

### Para grandes conjuntos de dados (50k - 500k feições)

:::warning Recomendação de desempenho
**Mude para PostgreSQL ou Spatialite** para desempenho 5-10x melhor. O backend OGR não é ideal para grandes conjuntos de dados.
:::

## Limitações

### Comparado aos backends de banco de dados

| Recurso | OGR | Spatialite | PostgreSQL |
|---------|-----|-----------|-----------|
| Tamanho máx prático | ~50k feições | ~500k feições | 10M+ feições |
| Índices espaciais | ⚠️ Depende do formato | ✅ R-tree | ✅ GIST |
| Uso de memória | ⚠️ Alto | ✅ Baixo | ✅ Muito baixo |
| Operações no servidor | ❌ Não | ❌ Não | ✅ Sim |
| Acesso concorrente | ⚠️ Limitado | ⚠️ Limitado | ✅ Excelente |

### Limitações específicas de formato

**Shapefile:**
- Limite de tamanho de arquivo 2GB
- Limite de 254 caracteres para nomes de campos
- Sem tipos de geometria mistos

**GeoJSON:**
- Sem suporte a índice espacial
- Pode ser muito grande (formato verboso)
- Análise mais lenta em arquivos grandes

**CSV:**
- Geometria armazenada em WKT (análise lenta)
- Sem índice espacial
- Não recomendado para grandes conjuntos de dados

## Solução de problemas

### Problema: "A camada não tem índice espacial"

**Sintoma:** Consultas lentas apesar de pequeno conjunto de dados

**Solução:**

Para **Shapefile**, criar índice .qix:
```python
layer.dataProvider().createSpatialIndex()
```

Para **GeoPackage**, reconstruir o R-tree:
```python
# Abrir no DB Manager e executar:
# DROP TABLE rtree_nome_camada_geometry;
# Depois recarregar a camada
```

### Problema: "Sem memória"

**Sintoma:** QGIS trava em grande conjunto de dados

**Solução:**

1. **Desativar camadas em memória:**
   ```json
   {
     "OGR": {
       "use_memory_layers": false
     }
   }
   ```

2. **Mudar para formato GeoPackage** (mais eficiente)

3. **Usar backend PostgreSQL ou Spatialite** em vez disso

### Problema: "Filtragem muito lenta"

**Sintoma:** Leva minutos para pequeno conjunto de dados

**Solução:**

1. **Verificar índice espacial:**
   ```python
   # Shapefile - verificar arquivo .qix
   # GeoPackage - verificar tabela rtree
   ```

2. **Simplificar geometria** se complexa:
   ```python
   processing.run("native:simplifygeometries", {
       'INPUT': layer,
       'METHOD': 0,  # Distância
       'TOLERANCE': 1,  # metros
       'OUTPUT': 'memory:'
   })
   ```

## Conversão de formato

### Para GeoPackage (Recomendado)

```bash
# Linha de comando (ogr2ogr)
ogr2ogr -f GPKG saida.gpkg entrada.shp

# Python
import processing
processing.run("native:package", {
    'LAYERS': [layer],
    'OUTPUT': '/caminho/para/saida.gpkg'
})
```

## Benchmarks de desempenho

Desempenho real em hardware típico (Core i7, 16GB RAM, SSD):

| Tamanho do conjunto | Feições | OGR (Shapefile) | OGR (GeoPackage) | Spatialite | PostgreSQL |
|---------------------|---------|----------------|-----------------|-----------|-----------|
| Pequeno | 5.000 | 0.8s | 0.6s | 0.4s | 0.3s |
| Médio | 50.000 | 25s | 15s | 8.5s | 1.2s |
| Grande | 500.000 | Timeout | 180s | 65s | 8.4s |

## Boas práticas

### ✅ Fazer

- **Usar GeoPackage para melhor desempenho OGR**
- **Criar índices espaciais** (.qix para Shapefile)
- **Manter conjuntos de dados < 50k feições** para backend OGR
- **Usar para compatibilidade universal de formatos**

### ❌ Evitar

- **Não usar OGR para > 100k feições** — muito lento
- **Não esquecer índices espaciais** — enorme impacto no desempenho
- **Não usar CSV/GeoJSON para grandes dados** — sem índice espacial
- **Não usar camadas em memória para enormes conjuntos de dados** — vai travar

## Migrar para melhores backends

### Quando mudar para Spatialite

**Indicadores:**
- Conjunto de dados > 10k feições
- Precisa de melhor desempenho de consulta
- Quer resultados persistentes

**Migração:**
```python
# Exportar para Spatialite
from qgis.core import QgsVectorFileWriter

options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "SQLite"
options.datasourceOptions = ["SPATIALITE=YES"]

QgsVectorFileWriter.writeAsVectorFormatV3(
    layer,
    "/caminho/para/saida.sqlite",
    QgsCoordinateTransformContext(),
    options
)
```

### Quando mudar para PostgreSQL

**Indicadores:**
- Conjunto de dados > 50k feições
- Precisa de acesso concorrente
- Quer operações no servidor
- Precisa do melhor desempenho

## Veja também

- [Visão geral dos backends](./overview.md) — Arquitetura multi-backend
- [Seleção de backend](./choosing-backend.md) — Lógica de seleção automática
- [Backend PostgreSQL](./postgresql.md) — Para melhor desempenho
- [Backend Spatialite](./spatialite.md) — Para conjuntos de dados médios
- [Comparação de desempenho](./performance-benchmarks.md) — Benchmarks detalhados

---

**Última atualização:** 14 de dezembro de 2025  
**Versão do plugin:** 2.3.0  
**Suporte OGR/GDAL:** Versão incluída com QGIS 3.x
