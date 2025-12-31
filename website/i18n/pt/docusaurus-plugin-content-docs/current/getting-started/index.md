---
sidebar_position: 1
---

# Começar

Bem-vindo ao FilterMate! Estes tutoriais ajudarão você a se tornar produtivo rapidamente.

## Tutoriais nesta seção

### [Início rápido](/docs/getting-started/quick-start)

**Tempo: 5 minutos**

Aprenda o fluxo de trabalho essencial:

- Abrir o FilterMate e selecionar camadas
- Criar seu primeiro filtro de atributos
- Entender a seleção de backend
- Exportar resultados filtrados

### [Seu primeiro filtro](/docs/getting-started/first-filter)

**Tempo: 10-15 minutos**

Tutorial completo passo a passo:

- Configurar um filtro geométrico
- Usar operações de buffer
- Trabalhar com predicados espaciais
- Revisar e exportar resultados

## Antes de começar

Certifique-se de ter:

- ✅ **QGIS 3.x** instalado
- ✅ **Plugin FilterMate** instalado ([Guia de instalação](/docs/installation))
- ✅ **Camada vetorial** carregada em seu projeto

## Dicas de desempenho

Para melhores resultados com grandes conjuntos de dados:

- 📦 **Conjuntos de dados médios** (&lt;50k feições): Spatialite/OGR funcionam bem
- ⚡ **Grandes conjuntos de dados** (&gt;50k feições): Instale `psycopg2` para suporte PostgreSQL
- 🗄️ **Conjuntos de dados muito grandes** (&gt;1M feições): Use camadas PostGIS

## Tutorial em vídeo

Prefere aprender com vídeo? Assista ao nosso passo a passo completo:

<div style={{position: 'relative', width: '100%', maxWidth: '800px', margin: '1.5rem auto', paddingBottom: '56.25%', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)'}}>
  <iframe
    style={{position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', border: 'none'}}
    src="https://www.youtube-nocookie.com/embed/2gOEPrdl2Bo?rel=0&modestbranding=1"
    title="Demonstração FilterMate - Tutorial completo"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    allowFullScreen
    loading="lazy"
  />
</div>

## Próximos passos

Depois de completar estes tutoriais:

1. **[Visão geral da interface](/docs/user-guide/interface-overview)** - Explore todos os componentes da UI
2. **[Noções básicas de filtragem](/docs/user-guide/filtering-basics)** - Domine a filtragem de atributos
3. **[Filtragem geométrica](/docs/user-guide/geometric-filtering)** - Operações espaciais avançadas
4. **[Visão geral dos backends](/docs/backends/overview)** - Entenda a otimização de desempenho

:::tip Precisa de ajuda?
Consulte o [Guia de solução de problemas](/docs/advanced/troubleshooting) ou visite [GitHub Issues](https://github.com/sducournau/filter_mate/issues).
:::
