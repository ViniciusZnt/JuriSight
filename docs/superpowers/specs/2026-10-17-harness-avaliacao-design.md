# Harness de Avaliação JuriSight — Design (Passo 0 + Etapa 1)

Data: 2026-10-17 · Status: aprovado pelo usuário (proposta v2 revisada no artefato
https://claude.ai/artifact/LmkrehVkbBpGi6Vcj7m9Dr)

## 1. Objetivo

Construir uma régua para a busca de jurisprudência: um conjunto-ouro de pares
(tese, acórdão) rotulados com **relevância 0–3** e **stance** (fortalece /
enfraquece / neutro), e um comando `eval` que dá nota ao pipeline de busca atual.
Nenhuma mudança visível ao usuário final nesta etapa — ela só mede.

Fora deste spec (etapas futuras, cada uma com spec próprio): reordenador com
sinais do Jev em tempo de busca (etapa 2), stance na tela (etapa 3), agente de
busca, troca do classificador de provimento.

## 2. Decisões fixadas

| Decisão | Valor |
|---|---|
| Fonte da verdade | Alexia (especialista) rotula ~150 pares; Jev rotula o resto depois de calibrado contra ela |
| Rótulo | Relevância 0–3 (Score) + stance (Choice) |
| Juiz | Só Jev (TypeSafe System One), `TYPESAFE_MODEL=jev-1.13.0`, chave `TYPESAFE_API_KEY` |
| Gerador de teses sintéticas | LLM generativo da OpenAI (Jev não gera texto) |
| Ordem | Passo 0 (teste em português) antes da Etapa 1 |
| Amostra da Alexia | Mista: 75 sorteados estratificados (medem kappa) + 75 de menor confiança (definem o limite) |
| Critério de confiança no juiz | Kappa (ponderado para relevância) ≥ 0,6 nos 75 sorteados |

Padrões assumidos para as perguntas em aberto (ajustáveis sem mudar a arquitetura):
- Teses reais vêm só de `public.conversas` (nenhuma fonte externa por ora).
- Temas do split `teste` são sorteados com seed fixa, ~40% dos temas.
- Acesso à tela de rotulação: e-mails em `AVALIACAO_EMAILS` (lista separada por vírgula).
- Progresso da Alexia é salvo a cada clique; a etapa não depende de uma sessão única.

## 3. Arquitetura

Novo pacote Python `avaliacao/` (mesmo padrão de `auth/` e `conversations/`:
psycopg puro, sem FastAPI dentro do pacote), mais uma rota HTTP fina e uma página
no frontend.

```
avaliacao/
  db.py          ensure_schema(): schema `avaliacao`, tabelas teses / pares / julgamentos
  store.py       AvaliacaoStore: CRUD
  juiz.py        JuizJev: julgar(tese, documento) -> Julgamento; interface Juiz trocável
  temas.py       lista fixa de temas + atribuição via Jev (Choice)
  geracao.py     teses sintéticas (OpenAI) + filtro de consistência (Jev)
  pooling.py     3 corredores: BM25, vetorial, pipeline completo
  amostra.py     amostra mista da Alexia
  metricas.py    nDCG@k, Recall@k, kappa (simples e ponderado quadrático), stance@k
  eval.py        CLI: python -m avaliacao.eval --split teste
  passo_zero.py  CLI do passo 0 (planilha CSV para a Alexia + comparação)
query/search/pipeline.py   lógica do /query extraída do endpoint (reuso pelo eval)
query/api/avaliacao_routes.py  /avaliacao/* (fila de pares, gravar rótulo)
frontend: /avaliacao  tela de rotulação
```

### 3.1 Extração do pipeline

A lógica de `query/api/app.py::query` (hybrid search → fetch → filtros →
re-ranking → corte → normalização → categorical sort) vai para
`query/search/pipeline.py::buscar(...)`, que recebe as dependências e devolve
`list[ResultCard]`. O endpoint passa a só chamar essa função. Comportamento
idêntico; os testes atuais de `/query` continuam passando sem alteração.

### 3.2 Dados (schema `avaliacao` no Postgres)

- `teses(id uuid, estrutura jsonb, origem text ['sintetica'|'real'], tema text,
  split text ['dev'|'teste'], documento_origem_id text null, criado_em)`
- `pares(id uuid, tese_id, documento_id text, corredores text[], unique(tese_id, documento_id))`
  — um par por (tese, acórdão) do pool, guardando de quais buscas veio.
- `julgamentos(id uuid, par_id, juiz text ['humano:<email>'|'jev:<versao>'],
  relevancia smallint 0–3, stance text, relevancia_probs jsonb null,
  stance_probs jsonb null, confianca_rel real null, confianca_stance real null,
  rodada int, criado_em)`
  — vários julgamentos por par (humano, Jev rodada 1, Jev rodada 2...).
- `amostra(par_id, metade text ['sorteada'|'incerta'])` — quais pares a Alexia rotula.

Rótulo final de um par: o humano, se existir; senão o Jev rodada 1.

### 3.3 Juiz (Jev)

Uma chamada `system_one` por par, com estado JSON
`{tese: {...EstruturaArgumentativa}, acordao: {ementa, fundamentacao_inicio}}`
(fundamentação truncada em 3.000 caracteres) e duas perguntas paralelas:

- `relevancia` — Score, 4 níveis:
  0 trata de outro problema jurídico; 1 mesmo ramo, outro pedido ou fato central;
  2 mesmo pedido, fato decisivo diferente; 3 mesmo problema jurídico e mesmo fato decisivo.
  Rótulo discreto = nível de maior probabilidade.
- `stance` — Choice: fortalece / enfraquece / neutro.

Concorrência limitada (8 threads), retry exponencial do SDK, versão do modelo e
texto das perguntas gravados em cada rodada. Interface `Juiz` (protocolo com
`julgar`) permite trocar por Laya ou LLM generativo sem tocar o resto.

### 3.4 Teses

- **Sintéticas** (`geracao.py`): sorteia acórdãos com `possui_ementa`, balanceando
  provimento; OpenAI (`OPENAI_GEN_MODEL`, padrão `gpt-4o-mini`) escreve uma
  `EstruturaArgumentativa` — metade a favor do lado que o acórdão favorece, metade
  contra. Filtro: Jev julga (tese, acórdão de origem); descarta se P(relevância ≥ 2) < 0,5.
- **Reais**: versões de `public.conversas` (estrutura de cada versão), deduplicadas.
- **Tema**: Jev Choice sobre a lista fixa de `temas.py` (+ "outro").
- **Split**: por tema, sorteio com seed fixa.
- Meta: ~100 teses (~60 dev / ~40 teste).

### 3.5 Pooling

Para cada tese: top-20 só BM25 (`LoadedBM25.search`, colapsado por documento),
top-20 só vetorial (Qdrant, duas coleções fundidas por RRF), top-20 do pipeline
completo (`buscar`). União → pares. Esperado ~40 por tese.

### 3.6 Amostra e calibração

- 75 sorteados: estratificados por tema × relevância do Jev × stance do Jev × origem.
  Incluem os pares do passo 0.
- 75 incertos: menor `min(confianca_rel, confianca_stance)` entre os não sorteados.
- Kappa calculado **só** nos 75 sorteados: Cohen simples para stance, ponderado
  quadrático para relevância. Aprovado se ambos ≥ 0,6.
- Limite de confiança: com os 75 incertos, menor limite tal que a acurácia do Jev
  acima dele ≥ 80%; relatado, não aplicado automaticamente.

### 3.7 Tela de rotulação

Rotas (exigem sessão e e-mail em `AVALIACAO_EMAILS`):
`GET /avaliacao/fila` (próximo par sem rótulo humano do usuário, com tese, ementa,
trecho da fundamentação, link, progresso) e `POST /avaliacao/pares/{id}/rotulo`
(`{relevancia, stance}`). Frontend `/avaliacao`: tese no topo, um acórdão por vez,
botões 0–3 e F/E/N com atalhos de teclado, sem mostrar a nota do Jev, progresso.

### 3.8 Comando eval

`python -m avaliacao.eval --split {dev,teste} [--saida data/eval/runs/]`
roda `buscar` para cada tese e reporta, por split e por origem:
nDCG@10 (ganho = relevância), Recall@20 (relevante = ≥2), fração "fortalece"
entre relevantes no top-10, fração de não julgados no top-10, e variação
teste-reteste do Jev (concordância rodada 1 × rodada 2). Salva JSON com data,
commit git e versão do Jev.

## 4. Passo 0

`python -m avaliacao.passo_zero preparar` escolhe ~5 teses sintéticas (geradas
como em 3.4) e 4 acórdãos por tese (top do pipeline + de outros temas), julga
com o Jev duas vezes e grava `data/eval/passo_zero.csv` com colunas para a Alexia
preencher (sem as notas do Jev). `python -m avaliacao.passo_zero comparar`
lê o CSV preenchido e imprime concordância, variação e a matriz de confusão de
stance. Os pares e rótulos entram no banco e na metade sorteada da etapa 1.
Decisão humana a partir do relatório: seguir, Jev só para relevância, ou trocar juiz.

## 5. Testes

Unitários sem infraestrutura (padrão do projeto): métricas com valores à mão,
amostragem estratificada determinística, juiz com cliente fake, pooling com fakes,
store contra fake/integração Postgres (pulada sem `DATABASE_URL`), rotas com
`dependency_overrides`, extração do pipeline coberta pelos testes atuais de `/query`.
Integração real (opcional, marcada): uma chamada ao Jev com `TYPESAFE_API_KEY`.

## 6. Riscos

Jev em português (passo 0); variação entre chamadas (métrica dedicada); custo
(estimar e imprimir antes de rodar lote); versão flutuante (fixada); Jev
corrigindo a própria prova na etapa 2 (aprovação pelos rótulos humanos).
