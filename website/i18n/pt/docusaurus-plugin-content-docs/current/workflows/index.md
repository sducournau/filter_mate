---
sidebar_position: 1
---

# Fluxos de Trabalho do Mundo Real

Tutoriais práticos baseados em cenários mostrando como usar o FilterMate para tarefas SIG comuns.

## Sobre Estes Fluxos de Trabalho

Cada tutorial de fluxo de trabalho foi projetado para:
- ✅ **Resolver um problema do mundo real** enfrentado por profissionais SIG
- ✅ **Ensinar múltiplos recursos do FilterMate** em contexto prático
- ✅ **Ser concluído em 10-15 minutos** com dados de exemplo fornecidos
- ✅ **Incluir melhores práticas** para desempenho e precisão

## Fluxos de Trabalho Disponíveis

### 🏙️ Planejamento Urbano e Desenvolvimento

**[Encontrar Propriedades Próximas ao Transporte](/docs/workflows/urban-planning-transit)**
- **Cenário**: Identificar todos os lotes residenciais dentro de 500m de estações de metrô
- **Habilidades**: Operações de buffer, predicados espaciais, filtragem multi-camadas
- **Backend**: PostgreSQL (recomendado para grandes conjuntos de dados de lotes)
- **Tempo**: ~10 minutos
- **Dificuldade**: ⭐⭐ Intermediário

---

### 🌳 Análise Ambiental

**[Avaliação de Impacto em Zona Protegida](/docs/workflows/environmental-protection)**
- **Cenário**: Encontrar instalações industriais dentro de zonas de buffer de água protegidas
- **Habilidades**: Filtragem geométrica, restrições de atributos, reparação de geometria
- **Backend**: Spatialite (bom para conjuntos de dados regionais)
- **Tempo**: ~15 minutos
- **Dificuldade**: ⭐⭐⭐ Avançado

---

### 🚒 Serviços de Emergência

**[Análise de Cobertura de Serviço](/docs/workflows/emergency-services)**
- **Cenário**: Identificar áreas a mais de 5km da estação de bombeiros mais próxima
- **Habilidades**: Consultas espaciais inversas, cálculos de distância, exportar resultados
- **Backend**: OGR (compatibilidade universal)
- **Tempo**: ~12 minutos
- **Dificuldade**: ⭐⭐ Intermediário

---

### �� Análise Imobiliária

**[Filtragem e Exportação de Mercado](/docs/workflows/real-estate-analysis)**
- **Cenário**: Filtrar propriedades por preço, área e proximidade de escolas
- **Habilidades**: Filtragem combinada de atributos + geométrica, gerenciamento de histórico
- **Backend**: Comparação multi-backend
- **Tempo**: ~8 minutos
- **Dificuldade**: ⭐ Iniciante

---

### 🚗 Planejamento de Transporte

**[Preparação de Dados de Rede Viária](/docs/workflows/transportation-planning)**
- **Cenário**: Exportar segmentos de rodovias dentro do município com atributos específicos
- **Habilidades**: Filtragem de atributos, transformação de SRC, exportação em lote
- **Backend**: Qualquer (foco em recursos de exportação)
- **Tempo**: ~10 minutos
- **Dificuldade**: ⭐ Iniciante

---

## Estrutura do Fluxo de Trabalho

Cada tutorial segue um formato consistente:

1. **Visão Geral do Cenário** - O problema do mundo real
2. **Pré-requisitos** - Dados e configuração necessários
3. **Instruções Passo a Passo** - Passo a passo detalhado com capturas de tela
4. **Compreendendo os Resultados** - Interpretando a saída
5. **Melhores Práticas** - Dicas para otimização
6. **Problemas Comuns** - Guia de solução de problemas
7. **Próximos Passos** - Fluxos de trabalho relacionados e técnicas avançadas

## Dados de Exemplo

A maioria dos fluxos de trabalho pode ser concluída com **dados do OpenStreetMap**:

- Baixe de [Geofabrik](https://download.geofabrik.de/)
- Use o plugin **QuickOSM** do QGIS para buscar áreas específicas
- Ou use seus próprios dados de projeto

:::tip Obtendo Dados de Exemplo
Instale o plugin **QuickOSM** no QGIS:
1. Plugins → Gerenciar e Instalar Plugins
2. Pesquisar "QuickOSM"
3. Instalar e reiniciar o QGIS
4. Vetor → QuickOSM → Consulta Rápida
:::

## Escolha Seu Caminho de Aprendizado

### Novo no FilterMate?
Comece com **fluxos de trabalho para iniciantes** (⭐):
1. [Análise Imobiliária](/docs/workflows/real-estate-analysis) - Filtragem simples
2. [Planejamento de Transporte](/docs/workflows/transportation-planning) - Foco em exportação

### Confortável com o Básico?
Experimente **fluxos de trabalho intermediários** (⭐⭐):
1. [Planejamento Urbano](/docs/workflows/urban-planning-transit) - Operações espaciais
2. [Serviços de Emergência](/docs/workflows/emergency-services) - Análise de distância

### Pronto para Tarefas Complexas?
Enfrente **fluxos de trabalho avançados** (⭐⭐⭐):
1. [Análise Ambiental](/docs/workflows/environmental-protection) - Filtragem multi-critérios

---

## Objetivos do Fluxo de Trabalho

Ao concluir estes fluxos de trabalho, você aprenderá:

- 🎯 **Filtragem eficiente** - Técnicas de atributos e geométricas
- 📐 **Análise espacial** - Buffers, predicados, cálculos de distância
- 🗺️ **Operações multi-camadas** - Trabalhando com conjuntos de dados relacionados
- 💾 **Estratégias de exportação** - Seleção de formato e transformação de SRC
- ⚡ **Otimização de desempenho** - Seleção e ajuste de backend
- 🔧 **Solução de problemas** - Problemas comuns e soluções
- 📝 **Gerenciamento de histórico** - Sistema desfazer/refazer

---

## Contribuindo com Fluxos de Trabalho

Tem um caso de uso do mundo real? Adoraríamos adicioná-lo!

**Envie seu fluxo de trabalho:**
1. Abra uma issue no [GitHub](https://github.com/sducournau/filter_mate/issues)
2. Descreva seu cenário e requisitos de dados
3. Inclua capturas de tela se possível
4. Ajudaremos você a criar um tutorial

---

## Precisa de Ajuda?

- 📖 **Documentos de Referência**: [Guia do Usuário](/docs/user-guide/introduction)
- 🐛 **Reportar Problemas**: [Issues do GitHub](https://github.com/sducournau/filter_mate/issues)
- 💬 **Fazer Perguntas**: [Discussões do GitHub](https://github.com/sducournau/filter_mate/discussions)
