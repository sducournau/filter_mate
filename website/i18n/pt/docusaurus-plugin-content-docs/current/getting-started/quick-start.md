---
sidebar_position: 2
---

# Início rápido

Comece com o FilterMate em 5 minutos! Este guia cobre o fluxo de trabalho essencial.

## Passo 1: Abrir o FilterMate

1. No QGIS, carregue uma camada vetorial (qualquer formato: Shapefile, GeoPackage, PostGIS, etc.)

<img src="/filter_mate/img/quickstart-1.png" alt="quickstart-1" width="500"/>

*QGIS com uma camada vetorial carregada e pronta para filtragem*

2. Clique no ícone **FilterMate** na barra de ferramentas, ou vá para **Complementos** → **FilterMate**

<img src="/filter_mate/img/install-4.png" alt="install-4" width="500"/>

*Abrindo o FilterMate da barra de ferramentas*

3. O painel acoplável do FilterMate aparecerá

<img src="/filter_mate/img/quickstart-3.png" alt="quickstart-3" width="500"/>

*Painel do FilterMate acoplado no lado direito do QGIS*

:::tip Primeira vez?
O FilterMate detectará automaticamente o tipo da sua camada e selecionará o backend ideal (PostgreSQL, Spatialite ou OGR).
:::

## Passo 2: Selecione sua camada

1. No menu suspenso **Seleção de camada** no topo do painel
2. Escolha a camada que deseja filtrar
3. O FilterMate carregará configurações específicas da camada e exibirá campos relevantes

*Camada selecionada com expressão de filtro pronta para aplicar*

## Passo 3: Criar um filtro

### Opção A: Filtro de atributos

Para filtrar por atributos (por ex., população > 10.000):

1. Vá para a aba **Filtro de atributos**
2. Digite uma expressão QGIS como:
   ```
   "population" > 10000
   ```
3. Clique em **Aplicar filtro**

### Opção B: Filtro geométrico

Para filtragem espacial (por ex., edifícios a 100m de uma estrada):

1. Vá para a aba **Filtro geométrico**
2. Selecione uma **camada de referência** (por ex., estradas)
3. Escolha um **predicado espacial** (por ex., "dentro da distância")
4. Defina uma **distância de buffer** (por ex., 100 metros)
5. Clique em **Aplicar filtro**

:::info Seleção de backend
O FilterMate usa automaticamente o melhor backend para seus dados:
- **PostgreSQL**: Para camadas PostGIS (mais rápido, requer psycopg2)
- **Spatialite**: Para bancos de dados Spatialite
- **OGR**: Para Shapefiles, GeoPackage, etc.
:::

## Passo 4: Revisar resultados

Após aplicar o filtro:

- Feições filtradas são **destacadas** no mapa
- A **contagem de feições** atualiza no painel
- Use a aba **Histórico** para desfazer/refazer filtros

## Passo 5: Exportar (Opcional)

Para exportar feições filtradas:

1. Vá para a aba **Exportar**
2. Escolha o **formato de exportação** (GeoPackage, Shapefile, PostGIS, etc.)
3. Configure o **SRC** e outras opções
4. Clique em **Exportar**

## Fluxos de trabalho comuns

### Filtrar por múltiplos critérios

Combine filtros de atributos e geométricos:

```python
# Filtro de atributos
"population" > 10000 AND "type" = 'residential'

# Depois aplicar filtro geométrico
# dentro de 500m do centro da cidade
```

### Desfazer/Refazer filtros

1. Vá para a aba **Histórico**
2. Clique em **Desfazer** para reverter o último filtro
3. Clique em **Refazer** para reaplicar

### Salvar configurações de filtro

O FilterMate salva automaticamente configurações por camada:
- Expressões de filtro
- Distâncias de buffer
- Preferências de exportação

## Dicas de desempenho

### Para grandes conjuntos de dados (>50.000 feições)

:::tip Use PostgreSQL
Instale psycopg2 e use camadas PostGIS para **filtragem 10-50× mais rápida**:
```bash
pip install psycopg2-binary
```
:::

### Para conjuntos de dados médios (10.000-50.000 feições)

- O backend Spatialite funciona bem
- Nenhuma instalação adicional necessária

### Para conjuntos de dados pequenos (Menos de 10.000 feições)

- Qualquer backend funcionará bem
- O backend OGR é suficiente

## Próximos passos

- **[Tutorial do primeiro filtro](./first-filter.md)** - Exemplo detalhado passo a passo
- **[Noções básicas de filtragem](../user-guide/filtering-basics.md)** - Aprenda sobre expressões e predicados
- **[Filtragem geométrica](../user-guide/geometric-filtering.md)** - Operações espaciais avançadas
- **[Comparação de backends](../backends/performance-benchmarks.md)** - Entenda o desempenho dos backends

## Solução de problemas

### Filtro não está aplicando?

Verifique:
- ✅ A sintaxe da expressão está correta (use o construtor de expressões do QGIS)
- ✅ Os nomes dos campos estão entre aspas corretamente: `"nome_campo"`
- ✅ A camada é editável (desbloqueie se necessário)
- ✅ Nenhum outro filtro já está aplicado

### Desempenho lento?

Soluções:
- ⚡ Mude para uma camada PostGIS com psycopg2 instalado
- 🔧 Simplifique expressões de filtro complexas
- 📊 Crie índices espaciais nas suas camadas
- 💾 Reduza o tamanho do conjunto de dados se possível

## Precisa de ajuda?

- 📖 [Guia completo do usuário](../user-guide/introduction.md)
- 🐛 [Relatar um bug](https://github.com/sducournau/filter_mate/issues)
- 💬 [Fazer uma pergunta](https://github.com/sducournau/filter_mate/discussions)
