---
sidebar_position: 100
title: Declaração de Acessibilidade
description: Compromisso e informações de conformidade de acessibilidade da documentação FilterMate
keywords: [acessibilidade, WCAG, leitor de tela, navegação por teclado, a11y]
---

# Declaração de Acessibilidade

**Última Atualização**: 9 de dezembro de 2025

A documentação FilterMate está comprometida em garantir acessibilidade digital para todos os usuários, incluindo aqueles que usam tecnologias assistivas. Nós nos esforçamos para atender ou exceder os padrões Web Content Accessibility Guidelines (WCAG) 2.1 Nível AA.

## Nosso Compromisso

Acreditamos que todos devem ter acesso igual às informações sobre FilterMate, independentemente da capacidade ou da tecnologia que usam. A acessibilidade é um esforço contínuo, e trabalhamos continuamente para melhorar a experiência do usuário para todos os visitantes.

## Status de Conformidade

**WCAG 2.1 Nível AA**: Parcialmente Conforme

Isso significa que algumas partes do conteúdo não estão totalmente conformes com o padrão WCAG 2.1 Nível AA, mas estamos trabalhando ativamente para alcançar conformidade total.

## Recursos de Acessibilidade

### ✅ Navegação por Teclado
- Todos os elementos interativos são acessíveis via teclado
- A ordem de tabulação segue uma sequência lógica
- Indicadores de foco são claramente visíveis
- Link de pular navegação fornecido para acesso rápido ao conteúdo principal

### ✅ Compatibilidade com Leitores de Tela
- Estrutura HTML5 semântica com marcos apropriados
- Labels ARIA quando apropriado
- Texto alternativo descritivo para todas as imagens informativas
- Hierarquia de cabeçalhos segue estrutura lógica (h1 → h2 → h3)

### ✅ Acessibilidade Visual
- **Contraste de Cores**: Proporção mínima de 4,5:1 para texto normal (WCAG AA)
- **Redimensionamento de Texto**: Conteúdo legível com zoom de 200% sem perda de funcionalidade
- **Indicadores de Foco**: Contorno de 3px com deslocamento de 2px em todos os elementos interativos
- **Tamanho da Fonte**: Tamanho de fonte base de 16px para melhor legibilidade
- **Altura da Linha**: Altura de linha de 1,65 para leitura confortável

### ✅ Design Responsivo
- Layouts adaptados para dispositivos móveis
- Alvos de toque mínimo de 44x44 pixels
- Adapta-se a diferentes tamanhos e orientações de tela

### ✅ Estrutura do Conteúdo
- Cabeçalhos e marcos claros
- Índice para páginas longas
- Navegação breadcrumb
- Padrões de navegação consistentes

### ✅ Mídia
- Blocos de código com destaque de sintaxe
- Diagramas incluem alternativas textuais
- Vídeos incluem legendas (quando disponível)

### ✅ Movimento e Animação
- Respeita a configuração `prefers-reduced-motion`
- Nenhum conteúdo piscante acima de 3Hz
- Animações podem ser desativadas via configurações do navegador

## Limitações Conhecidas

Estamos cientes das seguintes limitações de acessibilidade e trabalhamos para resolvê-las:

### �� Em Andamento
- **Legendas de Vídeo**: Alguns vídeos incorporados podem não ter legendas
- **Acessibilidade de PDF**: PDFs exportados precisam de marcação de acessibilidade
- **Alternativas para Exemplos de Código**: Descrições textuais para amostras de código complexas

### 📋 Melhorias Planejadas
- Anúncios aprimorados de leitor de tela para conteúdo dinâmico
- Documentação adicional de atalhos de teclado
- Paleta de cores melhorada para usuários daltônicos
- Anúncios de região ao vivo para atualizações AJAX

## Metodologia de Teste

Nossos testes de acessibilidade incluem:

- **Testes Automatizados**:
  - axe-core DevTools
  - pa11y-ci
  - Auditoria de Acessibilidade do Lighthouse

- **Testes Manuais**:
  - Navegação apenas por teclado
  - Testes com leitores de tela (NVDA, JAWS, VoiceOver)
  - Análise de contraste de cores
  - Testes de zoom do navegador (até 200%)

- **Testes com Usuários Reais**:
  - Feedback de usuários com deficiências
  - Grupos de usuários de tecnologia assistiva

## Suporte a Navegadores e Tecnologias Assistivas

Esta documentação foi testada com:

### Navegadores
- Chrome (última versão)
- Firefox (última versão)
- Safari (última versão)
- Edge (última versão)

### Leitores de Tela
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS/iOS)
- TalkBack (Android)

### Navegação por Teclado
Todos os recursos acessíveis via teclado em navegadores suportados

## Feedback e Reclamações

Recebemos com satisfação feedback sobre a acessibilidade da documentação FilterMate. Se você encontrar barreiras de acessibilidade, por favor nos informe:

### Reportar um Problema
- **Issues do GitHub**: [github.com/sducournau/filter_mate/issues](https://github.com/sducournau/filter_mate/issues)
- **Label**: Use o label `accessibility`
- **Informações a Incluir**:
  - URL da página
  - Descrição do problema
  - Navegador e tecnologia assistiva usados
  - Passos para reproduzir

### Prazo de Resposta
Nosso objetivo é responder ao feedback de acessibilidade dentro de:
- Problemas críticos: 2 dias úteis
- Problemas importantes: 1 semana
- Problemas menores: 2 semanas

## Especificações Técnicas

A acessibilidade da documentação FilterMate depende das seguintes tecnologias:

- **HTML5**: Marcação semântica
- **CSS3**: Estilos responsivos e acessíveis
- **JavaScript**: Aprimoramento progressivo (site funciona sem JS)
- **React**: Arquitetura baseada em componentes
- **Docusaurus**: Framework de documentação

## Padrões de Acessibilidade

Referenciamos os seguintes padrões e diretrizes:

- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/) (Web Content Accessibility Guidelines)
- [Section 508](https://www.section508.gov/) (U.S. Rehabilitation Act)
- [ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/) (Accessible Rich Internet Applications)
- [ATAG 2.0](https://www.w3.org/WAI/standards-guidelines/atag/) (Authoring Tool Accessibility Guidelines)

## Conteúdo de Terceiros

Algum conteúdo neste site pode vir de fontes de terceiros (por exemplo, vídeos incorporados, links externos). Nos esforçamos para garantir que o conteúdo de terceiros seja acessível, mas não podemos garantir controle total sobre recursos externos.

## Melhoria Contínua

A acessibilidade é um compromisso contínuo. Nosso roteiro inclui:

### Curto Prazo (Próximos 3 Meses)
- Auditoria completa de texto alternativo para todas as imagens
- Adicionar legendas a todos os vídeos de tutorial
- Implementar widget de feedback em todas as páginas
- Realizar testes abrangentes com leitores de tela

### Médio Prazo (3-6 Meses)
- Alcançar conformidade WCAG 2.1 AA completa
- Adicionar documentação de atalhos de teclado
- Implementar anúncios de região ao vivo
- Aprimorar contraste de cores para todos os elementos UI

### Longo Prazo (6-12 Meses)
- Visar conformidade WCAG 2.1 AAA quando viável
- Recursos de acessibilidade multilíngues
- Suporte avançado a tecnologias assistivas
- Auditorias regulares de acessibilidade (trimestrais)

## Recursos

### Para Usuários
- [WebAIM: Introdução à Acessibilidade Web](https://webaim.org/intro/)
- [Leitor de Tela NVDA](https://www.nvaccess.org/download/)
- [Verificador de Contraste de Cores](https://webaim.org/resources/contrastchecker/)

### Para Desenvolvedores
- [Guia de Práticas de Autoria ARIA](https://www.w3.org/WAI/ARIA/apg/)
- [Biblioteca de Componentes Acessíveis](https://www.a11yproject.com/)
- [Referência Rápida WebAIM](https://webaim.org/resources/quickref/)

## Informações Legais

Esta declaração de acessibilidade se aplica ao site de documentação FilterMate hospedado em [https://sducournau.github.io/filter_mate/](https://sducournau.github.io/filter_mate/).

Para questões sobre o plugin em si, consulte o [Repositório Principal de Plugins QGIS](https://plugins.qgis.org/plugins/filter_mate/).

---

**Nota**: Esta declaração foi criada em 9 de dezembro de 2025 e será revisada e atualizada trimestralmente para refletir nossas melhorias contínuas de acessibilidade.

:::tip Ajude-nos a Melhorar
Seu feedback nos ajuda a tornar a documentação FilterMate mais acessível. Se você usa tecnologia assistiva e tem sugestões, por favor [abra uma issue](https://github.com/sducournau/filter_mate/issues/new?labels=accessibility).
:::
