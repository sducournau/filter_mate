---
sidebar_position: 8
---

# Favoritos de Filtros

Salve, organize e aplique rapidamente configurações de filtros usadas frequentemente com o sistema de favoritos integrado do FilterMate.

:::info Versão 2.0+
O sistema de favoritos está disponível no FilterMate v2.0 e posterior, com persistência SQLite e capacidades de exportação/importação.
:::

## Visão Geral

Os **Favoritos de Filtros** permitem salvar configurações complexas de filtros—incluindo expressões, predicados espaciais, configurações de buffer e seleções multi-camadas—para reutilização rápida entre sessões.

### Recursos Principais

- ⭐ **Salvar filtros complexos** com nomes e notas descritivos
- 📊 **Rastrear estatísticas de uso** (contagem de aplicações, último uso)
- 💾 **Persistência SQLite** - favoritos salvos em banco de dados
- 📤 **Exportar/Importar** - compartilhar favoritos via arquivos JSON
- 🔍 **Pesquisar & organizar** - encontrar favoritos por nome ou tags
- 🎯 **Suporte multi-camadas** - salvar configurações afetando várias camadas

## Indicador de Favoritos

O **indicador ★ Favoritos** está localizado na barra de cabeçalho no topo do painel FilterMate, ao lado do indicador de backend.

### Estados do Indicador

| Exibição | Significado | Dica |
|----------|-------------|------|
| **★** (cinza) | Nenhum favorito salvo | Clique para adicionar filtro atual |
| **★ 5** (dourado) | 5 favoritos salvos | Clique para aplicar ou gerenciar |

**Clicar no indicador** abre o menu contextual de favoritos.

---

## Adicionar Favoritos

### Método 1: Do Filtro Atual

1. **Configure seu filtro** na aba FILTRAGEM:
   - Definir expressão
   - Escolher predicados espaciais
   - Configurar distância do buffer
   - Selecionar camadas para filtrar

2. **Clique no indicador ★** no cabeçalho

3. **Selecione "⭐ Adicionar Filtro Atual aos Favoritos"**

4. **Insira detalhes** no diálogo:
   - **Nome**: Nome curto e descritivo (ex: "Grandes lotes residenciais")
   - **Descrição** (opcional): Notas detalhadas sobre o filtro
   - **Tags** (opcional): Palavras-chave para busca (separadas por vírgula)

5. **Clique em OK** para salvar

:::tip Convenção de Nomenclatura
Use nomes claros e orientados à ação:
- ✅ "Edifícios a 200m do metrô"
- ✅ "Propriedades de alto valor > 500k"
- ❌ "filtro1", "teste", "consulta"
:::

### O Que é Salvo

Um favorito captura:

- **Expressão de filtro**: O texto da expressão QGIS
- **Camada fonte**: Nome e ID da camada de referência
- **Camadas remotas**: Lista de camadas filtradas (se multi-camadas)
- **Predicados espaciais**: Relações geométricas selecionadas
- **Configurações de buffer**: Distância, unidade, tipo
- **Operador de combinação**: AND/OR/AND NOT
- **Metadados**: Data de criação, contagem de uso, último uso

---

## Aplicar Favoritos

### Do Menu ★

1. **Clique no indicador ★**

2. **Favoritos recentes** são mostrados (até 10 mais recentes)

3. **Clique em um favorito** para aplicá-lo:
   - Expressão restaurada
   - Camadas selecionadas
   - Configurações espaciais configuradas
   - Pronto para aplicar com botão **Filtrar**

4. **Clique em "Filtrar"** para executar a configuração salva

:::warning Disponibilidade de Camadas
Se uma camada salva não existir mais no projeto, o FilterMate irá:
- Ignorar a camada ausente com mensagem de aviso
- Aplicar o filtro apenas às camadas disponíveis
:::

### Formato de Exibição de Favoritos

```
★ Proximidade de edifícios (3 camadas)
  Usado 12 vezes • Último: 18 dez
```

**Mostra**:
- Nome
- Número de camadas envolvidas
- Contagem de uso
- Data do último uso

---

## Gerenciar Favoritos

### Diálogo Gerenciador de Favoritos

**Acesso**: Clique no indicador ★ → **"⚙️ Gerenciar Favoritos..."**

O gerenciador fornece:

#### Painel Esquerdo: Lista de Favoritos
- Todos os favoritos salvos
- Mostra nome, contagem de camadas, estatísticas de uso
- Clique para ver detalhes

#### Painel Direito: Detalhes & Edição

**Aba 1: Geral**
- **Nome**: Editar nome do favorito
- **Expressão**: Ver/editar expressão de filtro
- **Descrição**: Adicionar notas

**Aba 2: Camadas**
- **Camada Fonte**: Informações da camada de referência
- **Camadas Remotas**: Lista de camadas filtradas

**Aba 3: Configurações**
- **Predicados Espaciais**: Relações geométricas
- **Buffer**: Distância e tipo
- **Operador de Combinação**: AND/OR/AND NOT

**Aba 4: Estatísticas de Uso**
- Vezes usado
- Data de criação
- Data do último uso

#### Ações

- **Salvar Alterações**: Atualizar o favorito selecionado
- **Excluir**: Remover o favorito (com confirmação)
- **Aplicar**: Fechar diálogo e aplicar favorito

---

## Exportar & Importar

### Exportar Favoritos

Compartilhe seus filtros favoritos com colegas ou faça backup em arquivo:

1. **Clique no indicador ★** → **"📤 Exportar Favoritos..."**

2. **Escolha localização** e nome do arquivo (ex: `filtermate_favorites.json`)

3. **Todos os favoritos exportados** para formato JSON

**Casos de Uso**:
- Compartilhar com membros da equipe
- Backup antes de atualizações do plugin
- Transferir entre projetos

---

### Importar Favoritos

Carregar favoritos de um arquivo JSON:

1. **Clique no indicador ★** → **"📥 Importar Favoritos..."**

2. **Selecione arquivo JSON**

3. **Escolha modo de importação**:
   - **Mesclar**: Adicionar aos favoritos existentes
   - **Substituir**: Excluir todos e importar novos

4. **Favoritos carregados** e prontos para usar

:::tip Fluxos de Trabalho em Equipe
Estabeleça uma biblioteca de favoritos da equipe:
1. Usuário especialista cria filtros otimizados
2. Exporta para drive/repositório compartilhado
3. Membros da equipe importam filtros padronizados
4. Garante consistência entre análises
:::

---

## Pesquisar & Filtrar

### Encontrar Favoritos

**No Gerenciador de Favoritos**:
- Digite na caixa de pesquisa para filtrar por:
  - Nome
  - Texto de expressão
  - Tags
  - Descrição

**Sem distinção de maiúsculas** e corresponde a texto parcial.

---

## Recursos Avançados

### Estatísticas de Uso

O FilterMate rastreia:
- **Contagem de aplicações**: Quantas vezes você usou este favorito
- **Último uso**: Timestamp do uso mais recente
- **Criado**: Quando o favorito foi salvo pela primeira vez

**Benefício**: Identificar seus filtros mais valiosos e otimizar fluxos de trabalho.

---

### Favoritos Multi-Camadas

Quando você salva um favorito com **camadas remotas** (Camadas para Filtrar habilitado):

**Salvo**:
- Configuração da camada fonte
- Todos os IDs de camadas remotas
- Predicados geométricos
- Configurações de buffer

**Na Aplicação**:
- Todas as camadas salvas re-selecionadas (se disponíveis)
- Relações espaciais restauradas
- Pronto para filtragem multi-camadas

**Exemplo**: "Lotes urbanos perto de transporte"
- Fonte: estacoes_metro
- Camadas remotas: lotes, edificios, ruas
- Predicado: intersecta
- Buffer: 500m

---

## Persistência de Favoritos

### Localização de Armazenamento

Os favoritos são salvos em:
```
<perfil QGIS>/python/plugins/filter_mate/config/filterMate_db.sqlite
```

**Tabela**: `fm_favorites`

**Por Projeto**: Os favoritos são organizados por UUID do projeto, então diferentes projetos QGIS podem ter coleções de favoritos separadas.

---

### Estratégia de Backup

Os favoritos são automaticamente salvos quando:
- A configuração do plugin é salva
- O projeto é fechado
- O FilterMate é descarregado

**Backup Manual**: Use **Exportar Favoritos** para criar backups JSON.

---

## Melhores Práticas

### Nomear Favoritos

✅ **Bons Nomes**:
- "Propriedades > 500k perto de escolas"
- "Zonas industriais a 1km da água"
- "Estradas de alto tráfego (AADT > 10k)"

❌ **Evite**:
- "Teste", "Query1", "Temp"
- Palavras únicas sem contexto
- Jargão excessivamente técnico

---

### Organizar com Tags

Use **tags** para categorizar:
- Por propósito: `analise`, `exportacao`, `relatorio`
- Por geografia: `centro`, `suburbios`, `regiao-norte`
- Por tipo de dado: `lotes`, `ruas`, `edificios`

**Exemplo**:
```
Nome: Grandes lotes residenciais
Tags: lotes, residencial, analise, planejamento-urbano
```

---

### Manutenção

**Regularmente**:
- ✅ Excluir favoritos não usados
- ✅ Atualizar descrições conforme fluxos de trabalho evoluem
- ✅ Exportar backups antes de mudanças importantes
- ✅ Revisar e consolidar favoritos similares

**Manter contagem de favoritos**: ~20-50 favoritos ativos é ideal (evitar desordem).

---

## Solução de Problemas

### Favorito Não Aplica Corretamente

**Sintomas**: Filtro aplica mas resultados diferem do esperado.

**Causas & Soluções**:

1. **Camada renomeada ou movida**
   - Solução: Editar favorito, atualizar referências de camada

2. **SRC alterado**
   - Solução: Re-salvar favorito com SRC atual

3. **Estrutura de dados alterada** (novos campos, etc.)
   - Solução: Editar expressão para corresponder ao esquema atual

---

### Favoritos Não Persistem

**Sintoma**: Favoritos desaparecem após reiniciar.

**Soluções**:

1. **Verificar arquivo de banco de dados**:
   ```bash
   # Verificar existência:
   ls <perfil>/python/plugins/filter_mate/config/filterMate_db.sqlite
   ```

2. **Permissões de arquivo**: Garantir acesso de gravação ao diretório de configuração

3. **Exportar backup**: Usar exportação JSON como armazenamento de fallback

---

### Importação Falha

**Erro**: "Nenhum favorito importado"

**Causas**:
- Formato JSON inválido
- Arquivo corrompido
- Versão incompatível

**Solução**: 
- Verificar estrutura JSON
- Tentar re-exportar da fonte
- Verificar se versões do FilterMate correspondem (v2.0+)

---

## Exemplos de Fluxos de Trabalho

### Fluxo de Trabalho 1: Filtros Padronizados de Equipe

**Cenário**: Equipe GIS de 5 pessoas precisa de filtragem consistente

**Configuração**:
1. Líder da equipe cria 10 favoritos principais
2. Exporta para `filtros_equipe.json`
3. Compartilha via repositório/drive
4. Membros da equipe importam no primeiro uso

**Resultado**: Todos usam lógica de filtro idêntica

---

### Fluxo de Trabalho 2: Análise Progressiva

**Tarefa**: Análise urbana em múltiplas etapas

**Favoritos**:
1. "Etapa 1: Lotes residenciais"
2. "Etapa 2: Perto de transporte (500m)"
3. "Etapa 3: Alto valor (>300k)"
4. "Etapa 4: Seleção final"

**Processo**: Aplicar cada favorito em sequência, exportar resultados em cada estágio.

---

### Fluxo de Trabalho 3: Garantia de Qualidade

**Caso de Uso**: Validar importações de dados

**Favoritos**:
- "QA: Atributos ausentes"
- "QA: Geometrias inválidas"
- "QA: Registros duplicados"
- "QA: Fora dos limites"

**Processo**: Aplicar cada filtro QA, revisar feições sinalizadas, corrigir problemas.

---

## Referência da API

### Classe FilterFavorite

Localização: `modules/filter_favorites.py`

**Propriedades**:
- `id`: UUID único
- `name`: Nome de exibição
- `expression`: Expressão de filtro
- `description`: Notas opcionais
- `tags`: Lista de palavras-chave
- `source_layer_id`: Camada de referência
- `remote_layers`: Lista de camadas filtradas
- `created_at`: Timestamp
- `last_used`: Timestamp
- `use_count`: Contador de aplicações

**Métodos**:
- `mark_used()`: Incrementar contador de uso
- `to_dict()`: Serializar para JSON
- `from_dict()`: Desserializar de JSON

---

### Classe FavoritesManager

Localização: `modules/filter_favorites.py`

**Métodos**:
- `add_favorite(fav)`: Adicionar à coleção
- `remove_favorite(id)`: Excluir por ID
- `get_favorite(id)`: Recuperar por ID
- `get_all_favorites()`: Listar todos (ordenados por nome)
- `get_recent_favorites(limit)`: Mais recentemente usados
- `search_favorites(query)`: Pesquisar por palavra-chave
- `export_to_file(path)`: Salvar em JSON
- `import_from_file(path)`: Carregar de JSON

---

## Documentação Relacionada

- **[Histórico de Filtros](./filter-history)** - Sistema Desfazer/Refazer
- **[Noções Básicas de Filtragem](./filtering-basics)** - Criar filtros
- **[Visão Geral da Interface](./interface-overview)** - Componentes da UI
- **[Por que FilterMate?](../getting-started/why-filtermate)** - Comparação de recursos

---

## Resumo

Os Favoritos de Filtros no FilterMate fornecem:

✅ **Salvar configurações complexas** para reutilização  
✅ **Organizar fluxos de trabalho** com nomes, descrições, tags  
✅ **Rastrear uso** para identificar filtros valiosos  
✅ **Compartilhar com equipe** via exportação/importação JSON  
✅ **Persistir entre sessões** com armazenamento SQLite  

**Próximos Passos**:
1. Criar seu primeiro favorito a partir de um filtro útil
2. Adicionar nome e tags descritivos
3. Aplicá-lo em diferentes projetos
4. Exportar para compartilhamento em equipe
