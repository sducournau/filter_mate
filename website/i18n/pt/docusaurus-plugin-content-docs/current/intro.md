---
sidebar_position: 1
slug: /
---

# Bem-vindo ao FilterMate

**FilterMate** é um plugin QGIS pronto para produção que oferece capacidades avançadas de filtragem e exportação para dados vetoriais - funciona com QUALQUER fonte de dados!

## 🎉 Novidades na v2.2.5 - Manipulação automática de SRC geográfico

### Melhorias principais
- ✅ **Conversão automática para EPSG:3857** - SRC geográfico (EPSG:4326, etc.) convertido automaticamente para operações métricas
  - Recurso: Detecta sistemas de coordenadas geográficas automaticamente
  - Impacto: Buffer de 50m é sempre 50 metros, independentemente da latitude (sem mais erros de 30-50%!)
  - Implementação: Converte automaticamente para EPSG:3857 (Web Mercator) para cálculos de buffer
  - Desempenho: Sobrecarga mínima (~1ms por transformação de feição)
- ✅ **Correção de Zoom e Flash Geográfico** - Resolvido tremulação com `flashFeatureIds`
  - Corrigido: Geometria de feição não é mais modificada no local durante a transformação
  - Solução: Usa construtor de cópia `QgsGeometry()` para evitar modificação da geometria original
- ✅ **Operações métricas consistentes** - Todos os backends atualizados (Spatialite, OGR, Zoom)
  - Zero configuração necessária
  - Registro claro com indicador 🌍 quando ocorre mudança de SRC
- ✅ **Testes abrangentes** - Conjunto de testes adicionado em `tests/test_geographic_coordinates_zoom.py`

## Atualizações anteriores

### v2.2.4 - Harmonização de cores e acessibilidade (8 de dezembro de 2025)
- ✅ **Harmonização de cores** - Distinção visual aprimorada com +300% de contraste de quadro
- ✅ **Conformidade WCAG 2.1** - Padrões de acessibilidade AA/AAA para todo o texto
  - Texto principal: taxa de contraste 17.4:1 (AAA)
  - Texto secundário: taxa de contraste 8.86:1 (AAA)
  - Texto desabilitado: taxa de contraste 4.6:1 (AA)
- ✅ **Fadiga ocular reduzida** - Paleta de cores otimizada para longas sessões de trabalho
- ✅ **Melhor legibilidade** - Hierarquia visual clara em toda a interface
- ✅ **Refinamentos de tema** - Quadros mais escuros (#EFEFEF), bordas mais claras (#D0D0D0)
- ✅ **Testes automatizados** - Conjunto de validação de conformidade WCAG

### v2.2.2 - Reatividade de configuração (8 de dezembro de 2025)
- ✅ **Atualizações de configuração em tempo real** - Mudanças na visualização em árvore JSON aplicadas instantaneamente sem reiniciar
- ✅ **Alternância dinâmica de UI** - Alterne entre os modos compacto/normal/automático em tempo real
- ✅ **Atualizações de ícone ao vivo** - Mudanças de configuração refletidas imediatamente
- ✅ **Integração ChoicesType** - Seletores suspensos para campos de configuração validados
- ✅ **Segurança de tipo** - Valores inválidos impedidos no nível da interface
- ✅ **Salvamento automático** - Todas as alterações de configuração salvas automaticamente

### v2.2.1 - Manutenção (7 de dezembro de 2025)
- ✅ **Estabilidade aprimorada** - Prevenção aprimorada de falhas na visualização JSON Qt
- ✅ **Melhor recuperação de erro** - Manipulação robusta de widget de guia e tema
- ✅ **Melhorias de compilação** - Automação aprimorada e gerenciamento de versão

## Por que FilterMate?

- **🚀 Rápido**: Backends otimizados para PostgreSQL, Spatialite e OGR
- **🎯 Preciso**: Predicados espaciais avançados e operações de buffer
- **💾 Pronto para exportar**: Múltiplos formatos (GeoPackage, Shapefile, GeoJSON, PostGIS)
- **📜 Histórico**: Desfazer/refazer completo com rastreamento de histórico de filtros
- **🎨 Bonito**: Interface compatível com WCAG com suporte a temas
- **🔧 Flexível**: Funciona com qualquer fonte de dados vetoriais

## Início rápido

1. **Instalar**: Abra QGIS → Complementos → Gerenciar e instalar complementos → Pesquisar "FilterMate"
2. **Abrir**: Clique no ícone FilterMate na barra de ferramentas
3. **Filtrar**: Selecione uma camada, escreva uma expressão, clique em Aplicar
4. **Exportar**: Escolha o formato e exporte seus dados filtrados

👉 **[Guia completo de instalação](./installation)**

## Recursos principais

### Filtragem avançada
- Filtragem de atributos com expressões QGIS
- Filtragem geométrica (intersecta, contém, dentro, etc.)
- Operações de buffer com conversão automática de SRC
- Suporte a múltiplas camadas

### Múltiplos backends
- **PostgreSQL**: Melhor para grandes conjuntos de dados (`>50k` feições) - 10-50× mais rápido
- **Spatialite**: Bom para conjuntos de dados médios (`<50k` feições)
- **OGR**: Compatibilidade universal (Shapefiles, GeoPackage, etc.)

**FilterMate escolhe automaticamente o melhor backend** para sua fonte de dados - nenhuma configuração necessária! Saiba mais na [Visão geral dos backends](./backends/overview).

### Capacidades de exportação
- Múltiplos formatos: GPKG, SHP, GeoJSON, KML, CSV, PostGIS
- Transformação de SRC na exportação
- Exportação de estilo (QML, SLD, ArcGIS)
- Exportação em lote e compactação ZIP

## Pré-requisitos

Antes de usar o FilterMate:

- ✅ **QGIS 3.x** instalado (qualquer versão)
- ✅ **Camada vetorial** carregada em seu projeto
- ⚡ **Opcional**: Instale `psycopg2` para suporte PostgreSQL (recomendado para grandes conjuntos de dados)

## Caminho de aprendizado

Novo no FilterMate? Siga este caminho:

1. **[Instalação](./installation)** - Instale o plugin e dependências opcionais
2. **[Início rápido](./getting-started/quick-start)** - Tutorial de 5 minutos
3. **[Seu primeiro filtro](./getting-started/first-filter)** - Exemplo completo passo a passo
4. **[Visão geral da interface](./user-guide/interface-overview)** - Entenda a interface
5. **[Noções básicas de filtragem](./user-guide/filtering-basics)** - Domine as técnicas de filtragem

## Obtendo ajuda

- 📖 **Documentação**: Navegue pelo [Guia do usuário](./user-guide/introduction)
- 🐛 **Problemas**: Relate bugs em [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Discussões**: Participe das [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 🎥 **Vídeo**: Assista ao nosso [tutorial no YouTube](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Seções de documentação

- **[Começar](./getting-started/index)** - Tutoriais e guias de início rápido
- **[Guia do usuário](./user-guide/introduction)** - Documentação completa de recursos
- **[Backends](./backends/overview)** - Entendendo backends de fonte de dados

:::note Tradução em andamento
Algumas seções da documentação ainda não estão disponíveis em português. Consulte a [documentação em inglês](/docs) para acessar todos os recursos.
:::

### v2.2.0 e anteriores
- ✅ **Multi-Backend completo** - Implementações PostgreSQL, Spatialite e OGR
- ✅ **Interface dinâmica** - Interface adaptativa que se ajusta à resolução da tela
- ✅ **Manipulação robusta de erros** - Reparação automática de geometria e mecanismos de nova tentativa
- ✅ **Sincronização de tema** - Corresponde ao tema da interface QGIS automaticamente
- ✅ **Desempenho otimizado** - 2.5× mais rápido com ordenação inteligente de consultas

## Recursos principais

- 🔍 **Pesquisa intuitiva** de feições em qualquer camada
- 📐 **Filtragem geométrica** com predicados espaciais e suporte a buffer
- 🎨 **Widgets específicos da camada** - Configure e salve configurações por camada
- 📤 **Exportação inteligente** com opções personalizáveis
- 🌍 **Reprojeção automática de SRC** em tempo real
- 📝 **Histórico de filtros** - Desfazer/refazer fácil para todas as operações
- 🚀 **Avisos de desempenho** - Recomendações inteligentes para grandes conjuntos de dados
- 🎨 **Interface adaptativa** - Dimensões dinâmicas baseadas na resolução da tela
- 🌓 **Suporte a temas** - Sincronização automática com o tema QGIS

## Links rápidos

- [Guia de instalação](./installation)
- [Tutorial de início rápido](./getting-started/quick-start)
- [Repositório GitHub](https://github.com/sducournau/filter_mate)
- [Repositório de plugins QGIS](https://plugins.qgis.org/plugins/filter_mate)

## Demonstração em vídeo

Veja o FilterMate em ação:

[![Demonstração FilterMate](https://img.youtube.com/vi/2gOEPrdl2Bo/0.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Começar

Pronto para começar? Vá para o [Guia de instalação](./installation) para configurar o FilterMate em seu ambiente QGIS.
