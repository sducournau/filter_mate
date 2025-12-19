---
sidebar_position: 2
---

# Visão Geral da Interface

Guia rápido dos principais componentes da interface FilterMate e fluxos de trabalho.

## Abrindo o FilterMate

1. **Menu:** Vetor → FilterMate
2. **Barra de ferramentas:** Clique no ícone FilterMate 

    <img src="/filter_mate/icons/logo.png" alt="Ícone do plugin FilterMate" width="32"/>

3. **Teclado:** Configure nas configurações do QGIS

## Abas Principais

O FilterMate organiza recursos em 3 abas principais:

### 🎯 Aba FILTRAGEM

**Objetivo:** Criar subconjuntos filtrados de seus dados

**Componentes principais:**

  - **Camada de referência:**

    <img src="/filter_mate/icons/auto_layer_white.png" alt="Botão de sincronização automática de camada" width="32"/>

    Escolher uma camada fonte para filtragem espacial / Sincronizar camada ativa com plugin

  - **Seletor de camadas:**

    <img src="/filter_mate/icons/layers.png" alt="Ícone do seletor de camadas" width="32"/>

    Escolher quais camadas filtrar (seleção múltipla suportada)

  - **Configurações de combinação:**

    <img src="/filter_mate/icons/add_multi.png" alt="Ícone do operador de combinação" width="32"/>

    Combinar múltiplos filtros com operadores E/OU

  - **Predicados espaciais:**

    <img src="/filter_mate/icons/geo_predicates.png" alt="Ícone de predicados espaciais" width="32"/>

    Selecionar relacionamentos geométricos (Intercepta, Contém, Dentro, etc.)

  - **Configurações de buffer:**

    <img src="/filter_mate/icons/geo_tampon.png" alt="Ícone de distância de buffer" width="32"/>

    Adicionar zonas de proximidade (distância, unidade, tipo)

  - **Configurações de tipo de buffer:**

    <img src="/filter_mate/icons/buffer_type.png" alt="Ícone de tipo de buffer" width="32"/>

    Escolher tipo de geometria de buffer (planar, geodésico, elipsoidal)

**Casos de uso:**
- Encontrar feições que atendem critérios (ex: população > 100.000)
- Selecionar geometrias dentro/perto de outras feições
- Criar subconjuntos temporários para análise

**Veja:** [Noções básicas de filtragem](./filtering-basics), [Filtragem geométrica](./geometric-filtering), [Operações de buffer](./buffer-operations)

---

### 🔍 Aba EXPLORAÇÃO

**Objetivo:** Visualizar e interagir com feições da camada ativa atual do QGIS

**Componentes principais:**
- **Botões de ação:** 6 botões interativos
  - **Identificar:** 
  
    <img src="/filter_mate/icons/identify.png" alt="Botão identificar" width="32"/> 

    Destacar feições no mapa


  - **Zoom:** 
  
    <img src="/filter_mate/icons/zoom.png" alt="Botão zoom" width="32"/> 
  
    Centralizar mapa nas feições
  - **Selecionar:** 
    
    <img src="/filter_mate/icons/select_black.png" alt="Botão selecionar" width="32"/> 
  
    Ativar modo de seleção interativa
  
  - **Rastrear:** 
  
    <img src="/filter_mate/icons/track.png" alt="Botão rastrear" width="32"/> 
    
    Sincronizar seleções entre widgets e mapa

  - **Vincular:** 
  
    <img src="/filter_mate/icons/link.png" alt="Botão vincular" width="32"/> 
  
    Compartilhar configuração entre widgets
  
  - **Redefinir parâmetros:** 
  
    <img src="/filter_mate/icons/auto_save.png" alt="Botão redefinir parâmetros" width="32"/> 
  
    Restaurar parâmetros padrão da camada

- **Widgets de seleção:**
  - **Seleção única:** Escolher uma feição (menu suspenso)
  - **Seleção múltipla:** Selecionar várias feições (caixas de seleção)
  - **Seleção personalizada:** Usar expressões para filtrar widget

**Importante:** EXPLORAÇÃO sempre trabalha apenas na **camada ativa atual** do QGIS. Para mudar de camada, atualize-a no Painel de Camadas do QGIS.

**Casos de uso:**
- Navegar pelas feições interativamente
- Identificar e aproximar feições específicas
- Visualizar detalhes de atributos
- Seleção manual de feições

:::tip EXPLORAÇÃO vs FILTRAGEM
- **EXPLORAÇÃO:** Visualização temporária da camada atual (sem modificação de dados)
- **FILTRAGEM:** Subconjuntos filtrados permanentes em camadas selecionadas (podem ser múltiplas)
:::

---

### 📤 Aba EXPORTAÇÃO

**Objetivo:** Exportar camadas (filtradas ou não filtradas) para vários formatos

**Componentes principais:**
- **Seletor de camadas:**

  <img src="/filter_mate/icons/layers.png" alt="camadas" width="32"/>

  Escolher camadas para exportar

- **Transformação SRC:**

  <img src="/filter_mate/icons/projection_black.png" alt="projection_black" width="32"/>

  Reprojetar para sistema de coordenadas diferente

- **Exportação de estilo:**

  <img src="/filter_mate/icons/styles_white.png" alt="estilos" width="32"/>
 
  Salvar estilos QGIS (QML, SLD, ArcGIS)

- **Formato:** 

  <img src="/filter_mate/icons/datatype.png" alt="tipo de dados" width="32"/>

  GPKG, Shapefile, GeoJSON, KML, CSV, PostGIS, Spatialite

- **Modo em lote:** Exportar cada camada para arquivo separado
- **Pasta de saída:**

  <img src="/filter_mate/icons/folder.png" alt="pasta" width="32"/>

  Selecionar diretório de destino
- **Compressão ZIP:**

  <img src="/filter_mate/icons/zip.png" alt="zip" width="32"/>

  Empacotar saídas para entrega

**Casos de uso:**
- Compartilhar dados filtrados com colegas
- Arquivar snapshots de análise
- Converter entre formatos
- Preparar dados para mapeamento web

**Veja:** [Exportar feições](./export-features)

---

### ⚙️ Aba CONFIGURAÇÃO

**Objetivo:** Personalizar comportamento e aparência do FilterMate

**Componentes principais:**
- **Visualização em árvore JSON:** Editar configuração completa
- **Seletor de tema:** Escolher tema da UI (padrão/escuro/claro/auto)
- **Opções avançadas:** Configurações do plugin

**Veja:** [Configuração](../advanced/configuration)

---

## Botões de Ação (Barra Superior)

Sempre visíveis independente da aba ativa:

| Botão | Ícone | Ação | Atalho |
|--------|------|--------|----------|
| **FILTRAR** | <img src="/filter_mate/icons/filter.png" alt="Filtrar" width="32"/> | Aplicar filtros configurados | F5 |
| **DESFAZER** | <img src="/filter_mate/icons/undo.png" alt="Desfazer" width="32"/> | Reverter último filtro | Ctrl+Z |
| **REFAZER** | <img src="/filter_mate/icons/redo.png" alt="Refazer" width="32"/> | Reaplicar filtro desfeito | Ctrl+Y |
| **REDEFINIR** | <img src="/filter_mate/icons/reset.png" alt="Redefinir" width="32"/> | Limpar todos os filtros | Ctrl+Shift+C |
| **EXPORTAR** | <img src="/filter_mate/icons/export.png" alt="Exportar" width="32"/> | Exportação rápida | Ctrl+E |
| **SOBRE** | <img src="/filter_mate/icons/icon.png" alt="Ícone" width="32"/> | Informações do plugin | - |

---

## Indicadores de Backend

Emblemas visuais mostram o tipo de fonte de dados:

- **PostgreSQL ⚡:** Melhor desempenho (mais de 50k feições)
- **Spatialite 📦:** Bom desempenho (menos de 50k feições)
- **OGR/Shapefile 📄:** Compatibilidade básica

Backend detectado automaticamente com base no tipo de camada.

---

## Atalhos de Teclado Rápidos

- **Ctrl+F:** Focar no construtor de expressões
- **F5:** Executar filtro
- **Ctrl+Z / Ctrl+Y:** Desfazer / Refazer
- **Tab:** Navegar entre campos
- **Ctrl+Tab:** Alternar entre abas

---

## Saiba Mais

- **Primeiros Passos:** [Guia de Início Rápido](../getting-started/quick-start)
- **Uso Detalhado:** [Noções básicas de filtragem](./filtering-basics), [Filtragem geométrica](./geometric-filtering)
- **Opções de Exportação:** [Exportar feições](./export-features)
- **Avançado:** [Configuração](../advanced/configuration), [Ajuste de Desempenho](../advanced/performance-tuning)

## Layout da Interface

```mermaid
graph TB
    subgraph "Painel FilterMate"
        LS[Seletor de Camadas - Seleção múltipla]
        AB["Botões de Ação: Filtrar / Desfazer / Refazer / Redefinir / Exportar / Sobre"]
        TB[Barra de Abas]
        
        subgraph "Aba FILTRAGEM"
            LSF[Seleção de Camada + Auto Atual]
            EXP[Construtor de Expressões - Filtragem de Atributos]
            PRED[Predicados Espaciais - Seleção múltipla]
            REF[Camada de Referência + Operador de Combinação]
            BUF[Configurações de Buffer: Distância + Unidade + Tipo]
            IND[Indicadores de Status]
        end
        
        subgraph "Aba EXPLORAÇÃO"
            BTN[Botões de Pressão: Identificar | Zoom | Selecionar | Rastrear | Vincular | Redefinir]
            SS[Seleção Única - Seletor de Feição]
            MS[Seleção Múltipla - Widget de Lista]
            CS[Seleção Personalizada - Expressão]
            FE[Widget de Expressão de Campo]
            TBL[Tabela de Atributos de Feição]
        end
        
        subgraph "Aba EXPORTAÇÃO"
            LYR[Camadas para Exportar - Seleção múltipla]
            FMT[Seletor de Formato: GPKG | SHP | GeoJSON | etc.]
            CRS[Transformação SRC]
            STY[Exportação de Estilo: QML | SLD | ArcGIS]
            OUT[Pasta de Saída + Modo em Lote]
            ZIP[Compressão ZIP]
        end
        
        subgraph "Aba CONFIGURAÇÃO"
            JSON[Visualização em Árvore JSON - Configuração Completa]
            THEMES[Seletor de Tema + Pré-visualização]
            OPTS[Opções Avançadas]
        end
    end
    
    LS --> AB
    AB --> TB
    TB --> LSF
    TB --> BTN
    TB --> LYR
    TB --> JSON
```

## Seletor de Camadas

### Recursos

- 📋 **Seleção múltipla:** Filtrar múltiplas camadas de uma vez
- 🔍 **Pesquisa:** Filtragem rápida de camadas
- 🎨 **Ícones:** Indicadores de tipo de geometria
  - 🔵 Camadas de pontos
  - 🟢 Camadas de linhas
  - 🟪 Camadas de polígonos

### Uso

```
☑ Camada 1 (Polígono) — PostgreSQL ⚡
☑ Camada 2 (Ponto) — Spatialite
☐ Camada 3 (Linha) — Shapefile
```

**Indicadores de backend:**
- ⚡ PostgreSQL (alto desempenho)
- 📦 Spatialite (desempenho médio)
- 📄 OGR (compatibilidade universal)

## Leituras Adicionais

Para guias detalhados sobre cada recurso:

- **[Noções básicas de filtragem](./filtering-basics)** - Guia completo para filtragem de atributos e expressões QGIS
- **[Filtragem geométrica](./geometric-filtering)** - Predicados espaciais, operações de buffer e fluxos de trabalho geométricos
- **[Operações de buffer](./buffer-operations)** - Configuração de buffer, tipos e configurações de distância
- **[Exportar feições](./export-features)** - Formatos de exportação, transformação SRC e operações em lote
- **[Histórico de filtros](./filter-history)** - Gerenciamento de histórico e sistema desfazer/refazer

Para começar:

- **[Guia de Início Rápido](../getting-started/quick-start)** - Introdução de 5 minutos
- **[Seu Primeiro Filtro](../getting-started/first-filter)** - Tutorial passo a passo

---

## Diretrizes de Uso de Ícones

### Acessibilidade
- Todos os ícones foram projetados com altas taxas de contraste
- Ícones sensíveis ao tema se adaptam automaticamente aos modos claro/escuro
- Ícones são dimensionados apropriadamente para telas de 16px, 24px e 32px

### Consistência
- Cada ícone representa uma ação específica e consistente em toda a interface
- Ícones de fluxo de trabalho (selection_1-7, zoom_1-5, etc.) mostram progressão de processo
- Variantes claro/escuro mantêm consistência visual em todos os temas

### Contexto
- Ícones aparecem em botões, indicadores de status e documentação
- Dicas de ferramentas ao passar o mouse fornecem contexto adicional para todos os ícones interativos
- Ícones sequenciais guiam usuários através de operações de múltiplas etapas

---

## Personalização da Interface

Você pode personalizar a aparência dos ícones e temas do FilterMate na aba **CONFIGURAÇÃO**. Consulte o [Guia de Configuração](../advanced/configuration) para detalhes sobre:

- Alternar entre temas claro/escuro/auto
- Ajustar tamanhos de ícones (se suportado pelo tema)
- Criar configurações de tema personalizadas

---
