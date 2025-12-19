---
sidebar_position: 1.5
---

# Início Rápido de 3 Minutos

Faça seu primeiro filtro funcionar em apenas 3 minutos!

:::info O Que Você Aprenderá
- Como abrir o FilterMate
- Como aplicar um filtro de atributo
- Como ver os resultados no mapa
:::

**Tempo**: ⏱️ 3 minutos  
**Dificuldade**: ⭐ Iniciante Absoluto  
**Pré-requisitos**: QGIS instalado + qualquer camada vetorial carregada

---

## O Objetivo

**Filtrar uma camada de cidades para mostrar apenas grandes cidades** (população > 100.000)

---

## Passo 1: Abrir o FilterMate (30 segundos)

1. Procure pelo ícone do FilterMate na sua barra de ferramentas do QGIS:

   <img src="/filter_mate/icons/logo.png" alt="Ícone FilterMate" width="32"/>

2. Clique nele, ou vá em **Vetor** → **FilterMate**
3. O painel FilterMate aparece (geralmente do lado direito)

:::tip Posição do Painel
Você pode arrastar o painel para qualquer borda da janela do QGIS, ou torná-lo flutuante.
:::

---

## Passo 2: Selecione Sua Camada (30 segundos)

No dropdown **Seleção de Camada** no topo do painel FilterMate:

1. Clique no dropdown
2. Escolha sua camada de cidades/municípios
3. O FilterMate analisa a camada e mostra:
   - Tipo de backend (PostgreSQL⚡ / Spatialite / OGR)
   - Contagem de feições (ex: "450 feições")
   - Campos disponíveis

**Não tem uma camada de cidades?**
- Use qualquer camada com um campo numérico
- Ou baixe nosso [conjunto de dados de exemplo](https://github.com/sducournau/filter_mate/releases) (5 MB)

---

## Passo 3: Escrever uma Expressão de Filtro (1 minuto)

Agora vamos filtrar para mostrar apenas feições onde a população é maior que 100.000.

### Encontre a Caixa de Expressão

No painel FilterMate, procure pelo **construtor de expressões** - é a área de entrada de texto na aba FILTRAGEM ou EXPLORAÇÃO.

### Digite Sua Expressão

```sql
"populacao" > 100000
```

:::caution Nomes de Campos
- Nomes de campos são **sensíveis a maiúsculas/minúsculas**
- Use **aspas duplas** em torno dos nomes de campos: `"populacao"`
- Use **aspas simples** para valores de texto: `'São Paulo'`
:::

**Expressões Alternativas** (adapte aos seus dados):

<details>
<summary>Para uma camada com nomes de campos diferentes</summary>

```sql
-- Se seu campo é chamado "POPULACAO" (maiúsculas)
"POPULACAO" > 100000

-- Se seu campo é chamado "pop" ou "habitantes"
"pop" > 100000
"habitantes" > 100000

-- Múltiplas condições
"populacao" > 100000 AND "pais" = 'Brasil'
```

</details>

---

## Passo 4: Aplicar o Filtro (30 segundos)

1. Procure pelo botão **Aplicar Filtro** (geralmente tem um ícone de funil 🔽)
2. Clique nele
3. **Veja a mágica acontecer!** ✨

**O que você deve ver:**
- O mapa atualiza para mostrar apenas feições filtradas
- A contagem de feições atualiza (ex: "Mostrando 42 de 450 feições")
- Feições filtradas são destacadas no mapa

---

## ✅ Sucesso! O Que Acabou de Acontecer?

O FilterMate aplicou sua expressão a cada feição na camada:
- Feições com `populacao > 100000`: ✅ **Mostradas**
- Feições com `populacao ≤ 100000`: ❌ **Ocultadas**

Os dados originais estão **inalterados** - o FilterMate cria uma visualização filtrada temporária.

---

## �� Próximos Passos

### Aprenda Mais Técnicas de Filtragem

**Filtragem Geométrica** (10 min)  
Encontre feições baseadas em localização e relações espaciais  
[▶️ Seu Primeiro Filtro Geométrico](./first-filter)

**Exporte Seus Resultados** (5 min)  
Salve feições filtradas para GeoPackage, Shapefile ou PostGIS  
[▶️ Guia de Exportação](../user-guide/export-features)

**Desfazer/Refazer** (3 min)  
Navegue pelo seu histórico de filtros com desfazer/refazer inteligente  
[▶️ Histórico de Filtros](../user-guide/filter-history)

### Explore Fluxos de Trabalho do Mundo Real

**Planejamento Urbano** (10 min)  
Encontre propriedades perto de estações de transporte  
[▶️ Desenvolvimento Orientado ao Transporte](../workflows/urban-planning-transit)

**Imóveis** (8 min)  
Filtragem de propriedades com múltiplos critérios  
[▶️ Análise de Mercado](../workflows/real-estate-analysis)

---

## 🆘 Solução de Problemas

### "Nenhuma feição corresponde"

**Possíveis causas:**
1. **Erro de sintaxe na expressão** - Verifique erros de digitação
2. **Nome do campo incorreto** - Clique com botão direito na camada → Abrir Tabela de Atributos para verificar os nomes dos campos
3. **Limite muito alto** - Tente um valor menor: `"populacao" > 10000`

**Correção rápida:**
```sql
-- Tente esta expressão mais simples primeiro
"populacao" IS NOT NULL
```

Isso deve mostrar todas as feições com um valor de população.

---

### Erro "Campo não encontrado"

**Causa**: Nome do campo não corresponde exatamente

**Solução:**
1. Clique com botão direito na sua camada → **Abrir Tabela de Atributos**
2. Encontre a coluna com dados de população
3. Anote o nome **exato** do campo (incluindo capitalização)
4. Use esse nome exato entre aspas: `"SeuNomeDeCampo"`

---

### Não consigo encontrar o botão Aplicar

**A localização do botão Aplicar Filtro depende da sua configuração:**
- **Parte inferior do painel** (padrão)
- **Topo perto do seletor de camada**
- **Lado esquerdo ou direito** (se configurado)

Procure por um botão com ícone de funil (🔽) ou o texto "Aplicar Filtro".

---

## 💡 Dicas Profissionais

### 1. Use a Lista de Campos
A maioria das interfaces do FilterMate mostra uma lista de campos disponíveis. Clique em um nome de campo para inseri-lo automaticamente na sua expressão.

### 2. Verifique a Validade da Expressão
O FilterMate valida sua expressão em tempo real:
- ✅ Marca de seleção verde = Válido
- ❌ X vermelho = Erro de sintaxe (passe o mouse para detalhes)

### 3. Combine com Seleção no Mapa
Você pode combinar filtros do FilterMate com a ferramenta de seleção manual do QGIS:
1. Aplique o filtro do FilterMate
2. Use a ferramenta de Seleção para refinar ainda mais
3. Apenas feições filtradas são selecionáveis

---

## 🎉 Parabéns!

Você aplicou com sucesso seu primeiro filtro! Agora você está pronto para explorar os recursos mais avançados do FilterMate.

**Continue Aprendendo:**
- [Noções Básicas de Filtragem](../user-guide/filtering-basics) - Domine expressões QGIS
- [Filtragem Geométrica](../user-guide/geometric-filtering) - Relações espaciais
- [Todos os Fluxos de Trabalho](../workflows/) - Cenários do mundo real

**Precisa de Ajuda?**
- 📖 [Guia do Usuário](../user-guide/introduction)
- 🐛 [Reportar Problemas](https://github.com/sducournau/filter_mate/issues)
- 💬 [Fazer Perguntas](https://github.com/sducournau/filter_mate/discussions)
