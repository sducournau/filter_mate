---
sidebar_position: 2
---

# Início rápido

Comece com o FilterMate em 5 minutos! Este guia cobre o fluxo de trabalho essencial.

:::info Versão 2.3.0
Este guia está atualizado para o FilterMate v2.3.0 com Desfazer/Refazer inteligente e preservação automática de filtros.
:::

## Passo 1: Abrir o FilterMate

1. No QGIS, carregue uma camada vetorial (qualquer formato: Shapefile, GeoPackage, PostGIS, etc.)

<img src="/filter_mate/img/quickstart-1.png" alt="quickstart-1" width="500"/>

*QGIS com uma camada vetorial carregada e pronta para filtragem*

2. Clique no ícone **FilterMate** na barra de ferramentas, ou vá para **Complementos** → **FilterMate**

<img src="/filter_mate/img/install-4.png" alt="install-4" width="500"/>

*Abrindo o FilterMate da barra de ferramentas*

3. O painel acoplável do FilterMate aparecerá (ativa automaticamente quando camadas são adicionadas!)

<img src="/filter_mate/img/quickstart-3.png" alt="quickstart-3" width="500"/>

*Painel do FilterMate acoplado no lado direito do QGIS*

:::tip Primeira vez?
O FilterMate detectará automaticamente o tipo da sua camada e selecionará o backend ideal (PostgreSQL, Spatialite ou OGR). Para SRC geográficos (EPSG:4326), operações métricas são automaticamente convertidas para EPSG:3857 para maior precisão.
:::

## Passo 2: Selecione sua camada

1. No menu suspenso **Seleção de camada** no topo do painel
2. Escolha a camada que deseja filtrar
3. O FilterMate carregará configurações específicas da camada e exibirá campos relevantes

*Camada selecionada com expressão de filtro pronta para aplicar*

## Passo 3: Explorar e selecionar feições

O FilterMate oferece vários métodos de seleção na seção **Exploração**:

### Seleção simples
Use o widget **Seletor de feições** para selecionar feições individuais clicando no mapa ou escolhendo de um menu suspenso.

### Seleção múltipla
Expanda o grupo **Seleção múltipla** para selecionar várias feições de uma vez usando caixas de seleção.

### Expressão personalizada
Expanda o grupo **Expressão personalizada** para criar expressões QGIS complexas para filtragem:

```sql
"population" > 10000 AND "type" = 'residential'
```

## Passo 4: Aplicar filtros

### Opções de filtragem

Na seção **Filtragem**, configure seu filtro:

1. **Camadas a filtrar**: Selecione quais camadas serão filtradas (origem + camadas remotas)
2. **Operador de combinação**: Escolha como novos filtros interagem com os existentes:
   - **AND** (padrão): Combina filtros (interseção)
   - **OR**: União de filtros
   - **AND NOT**: Filtro de exclusão
3. **Predicados geométricos**: Selecione relações espaciais (intersecta, dentro, contém, etc.)
4. **Buffer**: Adicione uma distância de buffer ao seu filtro geométrico

### Aplicar o filtro

Clique no botão **Filtrar** (ícone de funil) na barra de ações. O filtro é aplicado a todas as camadas selecionadas.

:::info Preservação automática de filtros ⭐ NOVO na v2.3.0
O FilterMate agora preserva automaticamente filtros existentes! Quando você aplica um novo filtro, ele é combinado com filtros anteriores usando o operador selecionado (AND por padrão). Não há mais filtros perdidos ao alternar entre filtragem por atributos e geométrica.
:::

:::info Seleção de backend
O FilterMate usa automaticamente o melhor backend para seus dados:
- **PostgreSQL**: Para camadas PostGIS (mais rápido, requer psycopg2)
- **Spatialite**: Para bancos de dados Spatialite
- **OGR**: Para Shapefiles, GeoPackage, etc.
:::

## Passo 5: Revisar resultados

Após aplicar o filtro:

- Feições filtradas são **exibidas** no mapa
- A **contagem de feições** atualiza na lista de camadas
- **Botões Desfazer/Refazer** ficam ativos na barra de ações

## Passo 6: Desfazer/Refazer filtros

:::tip Desfazer/Refazer inteligente ⭐ NOVO na v2.3.0
FilterMate v2.3.0 apresenta desfazer/refazer contextual:
- **Apenas camada de origem**: Sem camadas remotas selecionadas, desfazer/refazer afeta apenas a camada de origem
- **Modo global**: Com camadas remotas filtradas, desfazer/refazer restaura o estado completo de todas as camadas simultaneamente
:::

Use os botões **Desfazer** (↩️) e **Refazer** (↪️) na barra de ações para navegar pelo histórico de filtros. Os botões ativam/desativam automaticamente com base na disponibilidade do histórico.

## Passo 7: Exportar (Opcional)

Para exportar feições filtradas:

1. Vá para a seção **Exportar**
2. Escolha o **formato de exportação** (GeoPackage, Shapefile, PostGIS, etc.)
3. Configure o **SRC** e outras opções
4. Clique em **Exportar**

## Fluxos de trabalho comuns

### Filtragem progressiva (Preservação de filtros)

Construa filtros complexos passo a passo:

```python
# Passo 1: Filtro geométrico - seleção por polígono
# Resultado: 150 feições

# Passo 2: Adicionar filtro de atributos com operador AND
"population" > 10000
# Resultado: 23 feições (interseção preservada!)
```

### Filtragem multicamada

1. Selecione feições na sua camada de origem
2. Ative **Camadas a filtrar** e selecione camadas remotas
3. Aplique o filtro - todas as camadas selecionadas são filtradas simultaneamente
4. Use **Desfazer global** para restaurar todas as camadas de uma vez

### Redefinir filtros

Clique no botão **Redefinir** para limpar todos os filtros das camadas selecionadas.

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

## Feedback configurável

FilterMate v2.3.0 inclui um sistema de feedback configurável para reduzir a fadiga de notificações:
- **Minimal**: Apenas erros críticos (produção)
- **Normal** (padrão): Equilibrado, informações essenciais
- **Verbose**: Todas as mensagens (desenvolvimento)

Configure em `config.json` → `APP.DOCKWIDGET.FEEDBACK_LEVEL`

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
- ✅ A camada tem feições que correspondem aos critérios

### Desempenho lento?

- Para grandes conjuntos de dados, considere [instalar o backend PostgreSQL](../installation.md#optional-postgresql-backend-recommended-for-large-datasets)
- Consulte o guia de [Ajuste de desempenho](../advanced/performance-tuning.md)

### Backend não detectado?

O FilterMate mostrará qual backend está sendo usado. Se PostgreSQL não estiver disponível:
1. Verifique se psycopg2 está instalado: `import psycopg2`
2. Verifique se a fonte da camada é PostgreSQL/PostGIS
3. Veja [Solução de problemas de instalação](../installation.md#troubleshooting)

## Precisa de ajuda?

- 📖 [Guia completo do usuário](../user-guide/introduction.md)
- 🐛 [Relatar um bug](https://github.com/sducournau/filter_mate/issues)
- 💬 [Fazer uma pergunta](https://github.com/sducournau/filter_mate/discussions)
