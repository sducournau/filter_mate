---
sidebar_position: 100
---

# Registro de Alterações

Todas as alterações notáveis do FilterMate são documentadas aqui.

## [2.3.7] - 18 de dezembro de 2025 - Melhoria da Estabilidade na Troca de Projeto

### 🛡️ Melhorias de Estabilidade
- **Tratamento Aprimorado de Troca de Projeto** - Reescrita completa da detecção de troca de projeto
  - Força limpeza do estado do projeto anterior antes de reinicializar
  - Limpa cache de camadas, fila de tarefas e todos os flags de estado
  - Reseta referências de camadas do dockwidget para evitar dados obsoletos

- **Novo Handler de Sinal `cleared`** - Limpeza adequada no fechamento/limpeza de projeto
  - Garante reset do estado do plugin quando o projeto é fechado ou novo projeto criado
  - Desabilita widgets da UI enquanto aguarda novas camadas

- **Constantes de Timing Atualizadas** - Atrasos melhorados para melhor estabilidade com PostgreSQL

### ✨ Novas Funcionalidades
- **Forçar Recarga de Camadas (Atalho F5)** - Recarga manual quando a troca de projeto falha
  - Pressione F5 no dockwidget para forçar recarga completa
  - Mostra indicador de status durante a recarga ("⟳")
  - Opção de recuperação útil quando a detecção automática falha

### 🐛 Correções de Bugs
- **Corrigido Não-Recarga de Camadas na Troca de Projeto** - Limpeza mais agressiva
- **Corrigido Dockwidget Não Atualizando Após Troca de Projeto** - Reset completo
- **Corrigido Problema de Timing de Sinais** - QGIS emite `layersAdded` ANTES de `projectRead` completar

---

## [2.3.6] - 18 de dezembro de 2025 - Estabilidade de Carregamento de Projeto e Camadas

### 🛡️ Melhorias de Estabilidade
- **Constantes de Timing Centralizadas** - Todos os valores no dict `STABILITY_CONSTANTS`
  - `MAX_ADD_LAYERS_QUEUE`: 50 (previne overflow de memória)
  - `FLAG_TIMEOUT_MS`: 30000 (timeout de 30 segundos para flags obsoletos)

- **Flags com Timestamp** - Detecção e reset automático de flags obsoletos
  - Previne plugin de ficar preso em estado "carregando"
  - Reset automático de flags após 30 segundos

- **Validação de Camadas** - Melhor validação de objetos C++
  - Previne crashes ao acessar camadas deletadas

- **Debouncing de Sinais** - Tratamento de sinais rápidos
  - Limite de tamanho de fila com trimming automático (FIFO)
  - Tratamento gracioso de mudanças rápidas de projeto/camadas

### 🐛 Correções de Bugs
- **Corrigido Flags Travados** - Reset automático após 30 segundos
- **Corrigido Overflow de Fila** - Fila add_layers limitada a 50 itens
- **Corrigido Recuperação de Erro** - Flags resetados corretamente

---

## [2.3.5] - 17 de dezembro de 2025 - Qualidade de Código e Configuração v2.0

### 🛠️ Sistema de Feedback Centralizado
- **Notificações Unificadas** - Feedback de usuário consistente em todos os módulos
  - Novas funções `show_info()`, `show_warning()`, `show_error()`, `show_success()`
  - Fallback gracioso quando iface não disponível

### ⚡ Otimização Init PostgreSQL
- **Carregamento 5-50× Mais Rápido** - Inicialização mais inteligente
  - Verificação de existência de índice antes de criar
  - Cache de conexão por fonte de dados
  - CLUSTER adiado para o momento do filtro
  - ANALYZE condicional apenas se não houver estatísticas

### ⚙️ Sistema de Configuração v2.0
- **Estrutura de Metadados Integrada** - Metadados diretamente nos parâmetros
- **Migração Automática de Configuração** - Sistema de migração v1.0 → v2.0
- **Respeito ao Backend Forçado** - Escolha do usuário estritamente respeitada (sem fallback para OGR)

### 🐛 Correções de Bugs
- **Corrigido Erros de Sintaxe** - Parênteses não fechados corrigidos
- **Corrigido Cláusulas Except Genéricas** - Tratamento de exceção específico

### 🧹 Qualidade do Código
- **Melhoria de Pontuação**: 8.5 → 8.9/10

---

## [2.3.4] - 16 de dezembro de 2025 - Correção de Referência de Tabela PostgreSQL 2 Partes

### 🐛 Correções de Bugs
- **CRÍTICO: Corrigido referências de tabela PostgreSQL 2 partes** - Filtragem espacial agora funciona corretamente com tabelas usando formato `"table"."geom"`
- **Corrigido resultados GeometryCollection de buffers** - Extração e conversão corretas para MultiPolygon
- **Corrigido erro virtual_id PostgreSQL** - Erro informativo para camadas sem chave primária

### ✨ Novas Funcionalidades
- **Seleção inteligente de campo de exibição** - Novas camadas auto-selecionam o melhor campo descritivo (name, label, titulo, etc.)
- **ANALYZE automático nas tabelas fonte** - Planejador de consultas PostgreSQL agora tem estatísticas corretas

### ⚡ Melhorias de Performance
- **Carregamento ~30% Mais Rápido de Camadas PostgreSQL**
  - Contagem rápida com `pg_stat_user_tables` (500× mais rápido que COUNT(*))
  - Views materializadas UNLOGGED (30-50% mais rápido)

---

## [2.3.3] - 15 de dezembro de 2025 - Correção Auto-Ativação no Carregamento de Projeto

### 🐛 Correções de Bugs
- **CRÍTICO: Corrigido auto-ativação no carregamento de projeto** - Plugin agora ativa corretamente ao carregar projeto QGIS contendo camadas vetoriais

---

## [2.3.2] - 15 de dezembro de 2025 - Seletor de Backend Interativo

### ✨ Novas Funcionalidades
- **Seletor de Backend Interativo** - O indicador de backend agora é clicável para forçar manualmente um backend
  - Clique no badge para abrir menu de contexto
  - Backends forçados marcados com símbolo ⚡
  - Preferências de backend por camada

- **🎯 Auto-seleção de Backends Ótimos** - Otimização automática de todas as camadas
  - Analisa características de cada camada (tipo de provider, contagem de feições)
  - Seleciona inteligentemente o melhor backend

### 🎨 Melhorias de Interface
- **Indicador de Backend Aprimorado**
  - Efeito hover com mudança de cursor
  - Feedback visual com símbolo ⚡ para backends forçados

---

## [2.3.1] - 14 de dezembro de 2025 - Estabilidade e Melhorias de Backend

### 🐛 Correções de Bugs
- **CRÍTICO: Corrigido erro GeometryCollection em operações de buffer backend OGR**
  - Conversão automática de GeometryCollection para MultiPolygon
- **CRÍTICO: Corrigido potenciais crashes KeyError no acesso PROJECT_LAYERS**
  - Cláusulas de guarda para verificar existência de camadas
- **Corrigido filtragem geométrica GeoPackage** - Camadas GeoPackage agora usam backend Spatialite rápido (10× mais performante)

### 🛠️ Melhorias
- **Tratamento de exceção melhorado** - Substituição de handlers genéricos por tipos específicos

---

## [2.3.0] - 13 de dezembro de 2025 - Desfazer/Refazer Global e Preservação Automática de Filtros

### 🚀 Funcionalidades Principais

#### Desfazer/Refazer Global
Sistema inteligente de desfazer/refazer com comportamento contextual:
- **Modo Apenas Camada Fonte**: Desfazer/refazer aplica-se apenas à camada fonte quando nenhuma camada remota está selecionada
- **Modo Global**: Quando camadas remotas estão selecionadas e filtradas, desfazer/refazer restaura o estado completo de todas as camadas simultaneamente
- **Estados de Botão Inteligentes**: Botões ativam/desativam automaticamente com base no histórico disponível
- **Captura Multi-Camadas**: Nova classe `GlobalFilterState` captura o estado atômico das camadas
- **Detecção Automática de Contexto**: Alterna perfeitamente entre os modos

#### Preservação Automática de Filtros ⭐ NOVO
Funcionalidade crítica que previne perda de filtros durante troca de camadas:
- **Problema Resolvido**: Anteriormente, aplicar um novo filtro substituía filtros existentes
- **Solução**: Filtros agora são combinados automaticamente (AND por padrão)
- **Operadores Disponíveis**: AND (padrão), OR, AND NOT
- **Exemplo de Uso**:
  1. Filtrar por geometria de polígono → 150 feições
  2. Mudar para outra camada
  3. Aplicar filtro de atributo `population > 10000`
  4. Resultado: 23 feições (interseção de ambos os filtros preservada!)

#### Redução da Fadiga de Notificações ⭐ NOVO
Sistema de feedback configurável com controle de verbosidade:
- **Três Níveis**: Mínimo (-92% mensagens), Normal (padrão, -42%), Verboso
- **Configurável via**: `config.json` → `APP.DOCKWIDGET.FEEDBACK_LEVEL`

### ✨ Melhorias
- **Auto-Ativação**: Plugin agora auto-ativa quando camadas vetoriais são adicionadas
- **Limpeza de Debug**: Todas as instruções print de debug convertidas para logging apropriado

### 🐛 Correções de Bugs
- **Congelamento QSplitter**: Corrigido congelamento quando ACTION_BAR_POSITION definido como 'left' ou 'right'
- **Condição de Corrida no Carregamento**: Corrigido congelamento ao carregar projetos com camadas
- **Desfazer Global Camadas Remotas**: Corrigido desfazer não restaurando todas as camadas remotas

### 🛠️ Qualidade do Código
- Auditoria abrangente do código com pontuação geral **4.2/5**
- Todas as comparações `!= None` e `== True/False` corrigidas para estilo PEP 8

---

## [2.2.5] - 8 de dezembro de 2025 - Tratamento Automático de CRS Geográfico

### 🚀 Melhorias Principais
- **Conversão Automática EPSG:3857**: FilterMate agora detecta automaticamente sistemas de coordenadas geográficas (EPSG:4326, etc.) e muda para EPSG:3857 para operações métricas
  - **Por quê**: Garante distâncias de buffer precisas em metros ao invés de graus imprecisos
  - **Benefício**: Buffer de 50m é sempre 50 metros, independente da latitude!
  - **Impacto no usuário**: Sem configuração - funciona automaticamente

### 🐛 Correções de Bugs
- **Zoom e Flash de Coordenadas Geográficas**: Corrigidos problemas críticos com EPSG:4326
  - Geometria da feição era modificada no local durante a transformação
  - Distâncias de buffer em graus variavam com a latitude
  - Solução: Usar cópia de geometria, auto-mudança para EPSG:3857 para buffers

---

## [2.2.4] - 8 de dezembro de 2025 - Correção de Expressões Spatialite

### 🐛 Correções de Bugs
- **CRÍTICO: Aspas em Expressões Spatialite**: Corrigido bug onde aspas duplas ao redor de nomes de campos eram removidas
  - Problema: `"HOMECOUNT" > 100` era incorretamente convertido para `HOMECOUNT > 100`
  - Impacto: Filtros falhavam em camadas Spatialite com nomes de campos sensíveis a maiúsculas
  - Solução: Preservadas aspas de nomes de campos na conversão de expressão

### 🧪 Testes
- Adicionada suite de testes abrangente para conversão de expressões Spatialite
- Validada preservação de aspas de nomes de campos

---

## [2.2.3] - 8 de dezembro de 2025 - Harmonização de Cores e Acessibilidade

### 🎨 Melhorias de Interface
- **Distinção Visual Aprimorada**: Melhoria significativa no contraste entre elementos da UI
- **Conformidade WCAG 2.1**: Padrões de acessibilidade AA/AAA atendidos para todo texto
  - Contraste de texto principal: 17.4:1 (conformidade AAA)
  - Contraste de texto secundário: 8.86:1 (conformidade AAA)
  - Texto desabilitado: 4.6:1 (conformidade AA)
- **Refinamentos de Tema**: 
  - Tema `default`: Fundos de moldura mais escuros (#EFEFEF), bordas mais claras (#D0D0D0)
  - Tema `light`: Melhor contraste de widgets (#F8F8F8), bordas visíveis (#CCCCCC)
- **Cores de Destaque**: Azul mais profundo (#1565C0) para melhor contraste
- **Separação de Molduras**: +300% de melhoria no contraste entre molduras e widgets
- **Visibilidade de Bordas**: +40% de bordas mais escuras

### 📊 Acessibilidade e Ergonomia
- ✅ Redução da fadiga ocular com contrastes otimizados
- ✅ Hierarquia visual clara em toda a interface
- ✅ Melhor distinção para usuários com deficiências visuais leves
- ✅ Conforto melhorado para longas sessões de trabalho

### 🧪 Testes e Documentação
- **Nova Suite de Testes**: `test_color_contrast.py` valida conformidade WCAG
- **Prévia Visual**: `generate_color_preview.py` cria comparação HTML interativa
- **Documentação**: Guia completo de harmonização de cores

## [2.2.2] - 8 de dezembro de 2025 - Reatividade de Configuração

### ✨ Novas Funcionalidades
- **Atualizações em Tempo Real**: Alterações na visualização JSON aplicam-se sem reiniciar
- **Troca Dinâmica de Perfil UI**: Alternância instantânea entre modos compact/normal/auto
- **Atualização Ao Vivo de Ícones**: Alterações refletidas imediatamente
- **Salvamento Automático**: Todas as alterações salvas automaticamente

### 🎯 Tipos de Configuração Aprimorados
- **Integração ChoicesType**: Seletores dropdown para campos chave
  - Dropdowns UI_PROFILE, ACTIVE_THEME, THEME_SOURCE
  - Seletores de formato STYLES_TO_EXPORT, DATATYPE_TO_EXPORT
- **Segurança de Tipos**: Valores inválidos impedidos no nível da UI

### 🔧 Melhorias Técnicas
- **Gerenciamento de Sinais**: Sinal itemChanged ativado para handler de config
- **Detecção Inteligente**: Auto-detecção do tipo de alteração
- **Novo Módulo**: config_helpers.py com utilitários get/set
- **Tratamento de Erros**: Tratamento abrangente com feedback ao usuário

### 🎨 Trabalho Inicial de Harmonização
- Contraste aprimorado entre elementos UI em modo normal
- Conformidade WCAG AAA (17.4:1 para texto principal)
- Melhor distinção moldura/widget

## [2.2.1] - 7 de dezembro de 2025 - Versão de Manutenção

### 🔧 Manutenção
- ✅ Gerenciamento de Releases: Procedimentos de tagging e deploy aprimorados
- ✅ Scripts de Build: Automação e gerenciamento de versão aprimorados
- ✅ Documentação: Procedimentos de release atualizados
- ✅ Limpeza de Código: Melhorias menores de formatação

## [2.2.0] - Dezembro de 2025

### Adicionado
- ✅ Prevenção aprimorada de crashes do Qt JSON view
- ✅ Recuperação de erro do tab widget melhorada
- ✅ Tratamento robusto de temas e sincronização
- ✅ Documentação completa da arquitetura multi-backend

### Melhorado
- ⚡ Performance 2.5× mais rápida com ordenação inteligente de consultas
- 🎨 Adaptação dinâmica da UI baseada na resolução da tela
- 🔧 Melhor recuperação de locks SQLite
- 📝 Logging e capacidades de debug aprimorados

### Corrigido
- 🐛 Crash do Qt JSON view na troca de tema
- 🐛 Problemas de inicialização do tab widget
- 🐛 Casos extremos de reparo de geometria
- 🐛 Avisos de reprojeção de CRS

## [2.1.0] - Novembro de 2025

### Adicionado
- 🎨 UI adaptativa com dimensões dinâmicas
- 🌓 Sincronização automática de tema com QGIS
- 📝 Histórico de filtros com desfazer/refazer
- 🚀 Avisos de performance para grandes conjuntos de dados

### Melhorado
- ⚡ Suporte multi-backend (PostgreSQL, Spatialite, OGR)
- 📊 Monitoramento de performance aprimorado
- 🔍 Melhor tratamento de predicados espaciais

## [1.9.0] - Outubro de 2025

### Adicionado
- 🏗️ Padrão Factory para seleção de backend
- 📈 Otimizações automáticas de performance
- 🔧 Mecanismos de retry para locks SQLite

### Performance
- ⚡ Filtragem Spatialite 44.6× mais rápida (índices R-tree)
- ⚡ Operações OGR 19.5× mais rápidas (índices espaciais)
- ⚡ 2.3× mais rápido com ordenação de predicados

## [1.8.0] - Setembro de 2025

### Adicionado
- 🎨 Configuração de widgets por camada
- 💾 Configurações persistentes por camada
- 🔄 Reprojeção de CRS automática

## Versões Anteriores

Para o histórico completo de versões, veja a página [GitHub Releases](https://github.com/sducournau/filter_mate/releases).

---

## Numeração de Versões

FilterMate segue o [Versionamento Semântico](https://semver.org/lang/pt-BR/):

- **Maior.Menor.Patch** (ex: 2.1.0)
- **Maior**: Mudanças incompatíveis
- **Menor**: Novas funcionalidades (retrocompatíveis)
- **Patch**: Correções de bugs

## Guia de Atualização

### De 1.x para 2.x

A versão 2.0 introduziu a arquitetura multi-backend. Para atualizar:

1. Atualize via Gerenciador de Plugins do QGIS
2. (Opcional) Instale psycopg2 para suporte PostgreSQL
3. Configurações existentes serão migradas automaticamente

### De 2.0 para 2.1+

Sem mudanças incompatíveis. Atualize diretamente via Gerenciador de Plugins.

## Reportando Problemas

Encontrou um bug ou tem uma sugestão de funcionalidade?

- [Issues do GitHub](https://github.com/sducournau/filter_mate/issues)
- [Fórum de Discussão](https://github.com/sducournau/filter_mate/discussions)
