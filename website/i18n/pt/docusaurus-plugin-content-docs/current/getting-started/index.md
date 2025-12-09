---
sidebar_position: 1
---

# Começar

Bem-vindo ao FilterMate! Estes tutoriais ajudarão você a se tornar produtivo rapidamente.

## Tutoriais nesta seção

### [Início rápido](./quick-start.md)
**Tempo: 5 minutos**

Aprenda o fluxo de trabalho essencial:
- Abrir o FilterMate e selecionar camadas
- Criar seu primeiro filtro de atributos
- Entender a seleção de backend
- Exportar resultados filtrados

### [Seu primeiro filtro](./first-filter.md)
**Tempo: 10-15 minutos**

Tutorial completo passo a passo:
- Configurar um filtro geométrico
- Usar operações de buffer
- Trabalhar com predicados espaciais
- Revisar e exportar resultados

## Antes de começar

Certifique-se de ter:

- ✅ **QGIS 3.x** instalado
- ✅ **Plugin FilterMate** instalado ([Guia de instalação](../installation.md))
- ✅ **Camada vetorial** carregada em seu projeto

## Dicas de desempenho

Para melhores resultados com grandes conjuntos de dados:

- 📦 **Conjuntos de dados médios** (&lt;50k feições): Spatialite/OGR funcionam bem
- ⚡ **Grandes conjuntos de dados** (&gt;50k feições): Instale `psycopg2` para suporte PostgreSQL
- 🗄️ **Conjuntos de dados muito grandes** (&gt;1M feições): Use camadas PostGIS

## Tutorial em vídeo

Prefere aprender com vídeo? Assista ao nosso passo a passo completo:

[![Demonstração FilterMate](https://img.youtube.com/vi/2gOEPrdl2Bo/0.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Próximos passos

Depois de completar estes tutoriais:

1. **[Visão geral da interface](../user-guide/interface-overview.md)** - Explore todos os componentes da UI
2. **[Noções básicas de filtragem](../user-guide/filtering-basics.md)** - Domine a filtragem de atributos
3. **[Filtragem geométrica](../user-guide/geometric-filtering.md)** - Operações espaciais avançadas
4. **[Visão geral dos backends](../backends/overview.md)** - Entenda a otimização de desempenho

:::tip Precisa de ajuda?
Consulte o [Guia de solução de problemas](../advanced/troubleshooting.md) ou visite [GitHub Issues](https://github.com/sducournau/filter_mate/issues).
:::
