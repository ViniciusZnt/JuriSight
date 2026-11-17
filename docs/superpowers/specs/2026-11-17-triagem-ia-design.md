# Triagem por IA no lugar do reranker — design

Data: 17/11/2026.

## Por quê

Testando o sistema, o advogado viu que a **resposta gerada** (o `/resposta`) costuma citar exatamente as decisões que ele queria. Muitas vezes são decisões que a ordem dos cards deixava lá embaixo. A IA lendo a ementa contra a tese julga relevância melhor do que o cross-encoder (FlashRank).

Hoje essa leitura é desperdiçada de duas formas:

- **O funil é estreito.** O `/query` funde 30 candidatos no RRF, o reranker reordena esses 30 e corta em 20. A resposta lê só esses 20. No filtro restrito do TRT-12, por exemplo (2.443 elegíveis), só 30 decisões chegam a ser lidas.
- **O julgamento da IA não ordena nada.** Ele aparece só como citação (`#9`) dentro da resposta.

A proposta: tirar o reranker, ampliar o lote da busca para ~50 e pôr a IA para **avaliar cada decisão (nota 0–3)**. A nota ordena a lista. A resposta é escrita só com as decisões que a IA considerou relacionadas.

## Objetivos

- A lista de resultados passa a ser ordenada pela nota da IA. As decisões pouco relacionadas ficam recolhidas no fim.
- A avaliação chega **em lotes** e a tela se reordena a cada lote. O advogado pode **parar** no meio para economizar tokens.
- A resposta é gerada uma vez, ao fim da avaliação ou quando o advogado para, só com as decisões de nota 2 ou 3.
- Se a OpenAI estiver fora, a tela funciona como busca pura (ordem do RRF), sem resposta.
- O reranker sai do projeto inteiro: código, dependência, testes, benchmark e deploy.

## Não-objetivos

- **Múltiplas buscas com a IA mudando campos ou filtros:** fica para depois, por causa do custo em tokens. Nada no desenho impede: a triagem já diz quantas decisões têm nota ≥ 2, que é o gatilho natural para uma segunda rodada.
- **Triagem na faixa livre** (`/query/livre`): continua sem IA, na ordem do RRF, com 20 resultados.
- **Mandar à IA o inteiro teor ou o PDF do caso:** só vão a tese e as ementas públicas, como hoje.

## Anti-objetivos (falha, mesmo que funcione)

- A busca ficar mais lenta para mostrar o primeiro resultado. Os cards têm que aparecer logo, na ordem do RRF, como hoje.
- Uma falha da OpenAI esconder resultados ou travar a tela.
- A resposta citar `#N` que não corresponde ao card com esse número.
- Reabrir uma conversa gastar tokens sem o advogado pedir.

## Restrições

- **LGPD / RN05:** à OpenAI vão só os campos da tese e as ementas públicas, como já é no `/resposta`.
- **Limite diário** (`query/api/uso_diario.py`): a avaliação tem que caber nele.
- **Modelo padrão:** `gpt-4o-mini`, configurável por variável de ambiente, como o `OPENAI_GEN_MODEL`.

## Abordagens consideradas

1. **Uma chamada só** (ampliar o `/resposta` para devolver nota de 50 decisões e a resposta juntas). Muda pouco. Mas tem de escrever 50 avaliações antes da resposta (40–60s no 4o-mini), perde atenção no meio da lista e é tudo ou nada.
2. **Triagem em lotes + resposta** — **escolhida.** Um `/triagem` novo avalia lotes de 10, depois o `/resposta` lê só as relacionadas. A tela continua rápida, sobrevive à falha da IA, guarda a nota em cache por par tese × decisão e permite parar no meio.
3. **Triagem dentro do `/query`.** Os cards já chegariam ordenados, mas a busca ficaria ~10s parada, e uma queda da OpenAI derrubaria a busca.

## Desenho

### 1. Busca (`query/search/pipeline.py`)

- Sai o bloco do reranker e o parâmetro `reranker` de `buscar`.
- `buscar` ganha `n_resultados: int`:
  - O `/query` usa `N_RESULTADOS_TRIAGEM = 50`.
  - O `/query/livre` usa `N_RESULTADOS_LIVRE = 20`.
  - O benchmark usa o que precisar.
- O pool do RRF passa a ser o próprio `n_resultados`, porque não há mais reranker para alimentar. Com filtro de período, aplicado depois da busca, o pool é `N_CANDIDATOS_COM_FILTRO = 120`, e depois do filtro o resultado é cortado em `n_resultados`.
- `normalizar_scores` sai: existia por causa dos scores comprimidos do cross-encoder. O `score_rrf` vai cru. O front já usa o score só para obter a posição (`relevanceRanks`).
- `N_CANDIDATOS_PARA_RERANK` sai.

### 2. Triagem (`query/search/triagem.py`, novo) e `POST /triagem`

**Requisição:** `{ estrutura, ids: uuid[] (1..10), apenas_cache?: bool }`.

**Resposta:** `{ avaliacoes: [{ id, nota: 0|1|2|3, posicao: "deferiu"|"negou"|"fato_diferente"|"outro", motivo }] }`.

- Os ids que a IA não avaliar não voltam. O front os trata como "não avaliados".
- Com `apenas_cache=true`, devolve só o que está no cache e nunca chama a OpenAI nem conta no limite. É o que se usa ao reabrir uma conversa.

**O que vai ao modelo:**

- Só os **campos da tese**: `pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `tese_central`. Os filtros (`dispositivos`, `expressoes`, `tribunais`, `fase`) já garantiram a elegibilidade e mudá-los não muda a relevância.
- As ementas vêm do banco (`retriever.fetch(ids, completo=False)`), nunca do cliente, cortadas em 1.200 caracteres: começo + fim, a mesma ideia do `_trecho` atual, onde o fim traz o desfecho.
- Cada ementa vai com cabeçalho `#k` (k = 1..10, posição no lote) e metadados públicos (classe, tribunal, turma, data). O servidor converte `#k` de volta para o id.

**Schema pedido ao modelo** (structured output, `temperature=0`), um item por decisão, nesta ordem de campos:

- `numero` (k)
- `motivo`: o fato decisivo, em até 12 palavras. Vem antes da nota para o modelo ler o caso antes de classificar.
- `nota` (0–3), na escala do conjunto-ouro:
  - 0: outro problema jurídico;
  - 1: mesmo ramo, mas outro pedido ou outro fato central;
  - 2: mesmo pedido, com fato decisivo diferente ou só em parte;
  - 3: mesmo problema e mesmo fato decisivo ("eu citaria na peça").
- `pedido_da_tese`: "deferiu", "negou" ou "outro".
- `fatos_da_premissa`: bool.

A posição sai como hoje (`_posicao`): "negou" com `fatos_da_premissa=false` vira "fato_diferente". As regras de `pedido_da_tese` e `fatos_da_premissa` migram do prompt do `/resposta` para o da triagem.

**Validação no servidor:**

- Número fora de 1..k é descartado.
- Número repetido fica com a primeira ocorrência.
- Nota fora de 0..3 é descartada.

**Cache:**

- Tabela `public.triagem_cache`, com `chave TEXT PK, avaliacao JSONB, criada_em`.
- Uma linha **por par**. A chave é o sha256 de (modelo, temperatura, prompt, campos da tese, documento_id).
- Antes de chamar a IA, o servidor lê do cache os pares já avaliados e manda à OpenAI só os que faltam. Se todos estão no cache, não chama a OpenAI.
- Falha do banco no cache só gera log e não derruba a triagem, igual ao `resposta_cache`.

**Erros:**

- OpenAI fora ou timeout (`TIMEOUT_S = 20`) → 503, com a mensagem "Avaliação por IA indisponível agora."
- Recusa do modelo → avaliações vazias.
- Estrutura sem nenhum campo de tese → 422.

**Limite diário:**

- Nova ação `"triagem"`. Conta **um uso por lote que de fato chama a OpenAI**; acerto total no cache não conta.
- O limite por conta é `LIMITE_DIARIO_TRIAGEM_POR_CONTA`, padrão 5 × `LIMITE_DIARIO_POR_CONTA`, ou seja 150. Para o advogado, isso equivale a "uma busca". O total do sistema segue a mesma proporção.
- `UsoDiario.consumir` passa a aceitar um limite por ação.
- *(Ajuste em relação ao combinado na conversa: o servidor não tem como saber qual lote é o "primeiro" sem confiar no cliente. Contar por lote, com um teto 5×, dá o mesmo efeito sem essa brecha.)*

**Modelo:** `OPENAI_TRIAGEM_MODEL`, com padrão `gpt-4o-mini`.

### 3. Resposta (`query/search/resposta.py`, `POST /resposta`)

**Requisição:** `{ estrutura, ids: uuid[] (1..25) }`, na ordem dos cards. `ids[0]` é o `#1`, como hoje.

O front manda só as decisões com nota 2 ou 3. Como elas são a primeira seção da lista, os números são `#1..#k`, contíguos.

**Mudanças:**

- **Sai** `desfechos` do schema e do prompt. A posição vem do `triagem_cache`, que o servidor lê para cada id. Isso evita confiar no cliente.
- Id sem avaliação no cache recebe a posição `"outro"`. Nesse caso a frase de divergência que o cita é descartada pela regra que já existe.
- Ao modelo vai a posição de cada decisão no cabeçalho: `#3 (RORSum, TRT2, 11ª Turma, 2025-05-12 · negou)`. Assim as frases "negaram pelo direito" e "negaram por outros fatos" usam a mesma classificação que a tela.
- `Resposta.posicoes` **sai** do modelo e do tipo `RespostaIA` no front, porque a tela passa a ler as posições da triagem. O campo hoje só está declarado em `frontend/src/lib/api.ts`.
- `chave_da_resposta` continua (modelo, temperatura, prompt, tese, ids). As posições são função dos ids e da tese via cache, então não entram na chave.
- `MAX_EMENTA` continua em 2.000: a resposta precisa de mais texto que a triagem.
- `TIMEOUT_S` sobe para 40, porque podem ir até 25 ementas.

### 4. Front — estado da triagem (`frontend/src/components/resultados/triagem.ts`, hook novo)

`useTriagem(estrutura, resultados, { automatica })` devolve `{ avaliacoes: Map<id, Avaliacao>, status, avaliadas, total, parar, continuar }`.

**`status`:** `"avaliando" | "parada" | "concluida" | "indisponivel" | "ociosa"`. O estado `"ociosa"` é quando a tela foi reaberta e ainda há decisões não avaliadas.

**Orquestração:**

1. Divide os resultados, na ordem do RRF, em lotes de 10.
2. Mantém **2 lotes em voo**. Quando um termina, dispara o próximo.
3. Cada lote é um `POST /triagem` com o seu `AbortController`.

**Parar e responder:**

- Aborta os lotes em voo e não dispara os próximos.
- O que já chegou fica. Um lote abortado no meio não traz nada.
- O status vira `"parada"`.

**Continuar depois de parar:** em `"parada"` também aparece o botão "Avaliar N restantes".

- Continuar descongela a ordem e descarta a resposta mostrada.
- Quando a avaliação conclui, a resposta é pedida de novo com as relacionadas atualizadas. É uma nova geração, a menos que a lista de ids seja a mesma e venha do cache.

**Falhas:**

- Lote com erro tenta de novo **uma vez**.
- Se falhar de novo, os ids dele ficam "não avaliados" e o resto segue.
- Se **o primeiro lote** falhar duas vezes com 503 ou erro de rede, o status vira `"indisponivel"` e nenhum outro lote é disparado.
- 429 (limite diário) para tudo, com a mensagem do servidor.

**Busca nova** (vinda da Revisão): `automatica = true`, a avaliação começa sozinha.

**Reabrir uma versão** (pela sidebar ou pelo seletor V1/V2):

- `automatica = false`. Primeiro chama `/triagem` com `apenas_cache=true` em todos os lotes, o que não custa nada.
- Se tudo veio do cache, o status é `"concluida"`. Se não, é `"ociosa"` e aparece o botão "Avaliar N restantes".
- Isso cobre também as conversas salvas antes desta mudança.

Cache em memória por `chave` (ids + estrutura), igual ao `useRespostaGerada`: voltar da página de decisão não refaz nada.

Fechar a tela ou trocar de consulta aborta tudo, como a `FaixaLivre` já faz.

### 5. Front — ordem e seções (`search-results-page.tsx`)

A lista vira três seções, nesta ordem:

1. **Relacionadas:** nota 3, depois nota 2. Desempate pela ordem do RRF. Em seguida, as marcadas pelo advogado como relevantes (ver 6), na ordem em que ele marcou.
2. **Ainda não avaliadas:** na ordem do RRF. Só existe enquanto avalia, se ele parou, ou se algum lote falhou.
3. **Pouco relacionadas:** nota 1, depois 0. Recolhidas por padrão, com o título "Pouco relacionadas (N)".

**Status `"indisponivel"`:**

- Uma seção só, na ordem do RRF, como a busca pura.
- Aviso: "Avaliação por IA indisponível agora; a lista está na ordem da busca."
- Sem bloco de resposta.

**Numeração `#N`:** é a posição na lista concatenada (relacionadas, não avaliadas, pouco relacionadas).

- Enquanto avalia, os números mudam a cada lote. Tudo bem, porque ainda não há resposta citando.
- Quando a resposta é pedida, a ordem é **congelada** junto com ela: `ordemCongelada: id[]`.
- Votos depois disso não renumeram (ver 6).

**Filtros e ordenação existentes** (desfecho, período, tribunal, base citada, ordenar por data): valem **dentro de cada seção**, sem misturar as seções. O "ordenar por relevância" passa a ser a ordem das seções descrita acima.

**Card:** o selo "Nº mais relevante de N" vira o rótulo da nota, com o `motivo` no `title`:

- 3: "Mesmo problema e fato"
- 2: "Mesmo pedido"
- 1: "Mesmo ramo"
- 0: "Outro tema"

Card sem avaliação não mostra selo.

**Barra de progresso** no topo da lista, durante `"avaliando"`: "Avaliando decisões com a IA… X de N", com o botão **Parar e responder**. Em `"ociosa"`: "N decisões ainda não avaliadas" e o botão **Avaliar**.

### 6. Front — resposta e voto "É relevante"

**Quando a resposta é pedida:**

- Uma vez, ao status virar `"concluida"` ou `"parada"`.
- Com os ids das relacionadas de nota 3 e 2, até 25, em ordem.
- Se não houver nenhuma, não há chamada. O bloco de resposta mostra: "Nenhuma decisão avaliada como relacionada à tese."
- Enquanto avalia, o bloco mostra "A resposta sai quando a avaliação terminar ou você parar."
- `useRespostaGerada` passa a receber a lista já filtrada e congelada. Hoje ele faz `slice(0, 20)` da ordem inteira.

**"Decisões que sustentam"** e qualquer outro lugar que usava a posição de cada decisão passam a ler `avaliacoes[id].posicao`.

**Voto "É relevante":**

- Botão nos cards de "Pouco relacionadas".
- Move o card para o fim das relacionadas, com o selo "Marcada por você". O card mantém o seu `#N` e não refaz a resposta.
- Há "Desfazer" no próprio card.
- O voto fica salvo **na versão da conversa**:
  - Campo novo `relevantes_usuario: id[]` no JSON da versão.
  - Endpoint novo `PATCH /conversas/{id}/versoes/{numero}`, com corpo `{ relevantes_usuario }`. Ele substitui o campo naquela versão; os outros campos não podem ser alterados por ele.
  - `ConversaStore` ganha `set_relevantes(conversa_id, usuario_id, numero, ids)`, um UPDATE com `jsonb_set` no elemento `numero - 1`. Versão inexistente ou que não pertence ao usuário levanta `ConversaNaoEncontradaError`.
- `loadVersion` e `ConversationVersion` carregam o campo. Versões antigas não o têm, então vale `[]`.

### 7. Remoção do reranker

**Saem do projeto:**

- os módulos `query/search/reranker.py`, `reranker_onnx.py` e `reranker_monoptt5.py`;
- os testes `tests/test_reranker*.py`;
- `FakeReranker` em `tests/fakes.py`, e os testes de API e de pipeline que testam reordenação pelo reranker;
- em `query/api/app.py`: `app.state.reranker`, `get_reranker` e o parâmetro em `_buscar_cards`;
- em `pyproject.toml`: a dependência `flashrank` e o grupo opcional `benchmark` (torch + transformers). O `uv.lock` é atualizado;
- no doc de deploy, o modelo do reranker: o passo do `rsync` sai, e a linha de "busca lenta" deixa de citar o reranker.

**README:** o diagrama do pipeline, a seção "Ordem dos resultados", a tabela de tecnologias e a seção de re-ranking passam a descrever a triagem.

### 8. Benchmark (`avaliacao/`)

- **Sistemas:** S0 (BM25), S1 (denso), S2 (híbrido RRF) e **S7 (S2 + triagem)**. S3–S6 e `construir_rerankers` saem.
- **S7:**
  - Roda `buscar(n_resultados=50)` e avalia todos os 50 com a mesma função de `query/search/triagem.py`, usando o cache.
  - Ordena por nota decrescente, com desempate pela ordem do RRF, e devolve o top-20.
  - Precisa do cliente OpenAI no contexto (`avaliacao/contexto.py`).
- **Pool:** `pooling` passa a unir os **50** candidatos do híbrido (antes 30), o top-10 do BM25 e o top-10 do denso.
  - **Consequência:** os pares novos (posições 31–50) precisam de julgamento humano antes da medição final.
  - O `planilha_julgamento exportar` já exporta só os pares sem rótulo, então o fluxo não muda.
- `docs/avaliacao/README.md`: atualizar a seção 2 e a tabela de sistemas.
- **Escolher 40 vs 50 e o tamanho do lote:** rodar o S7 com `n_resultados` 40 e 50 no split dev. Isso fica **depois** desta entrega. O padrão de produção começa em 50.

### 9. Indicador do limite diário (pedido do advogado, 17/11)

O advogado quer ver na tela quanto já gastou do limite de hoje.

**Backend:** `GET /uso`, com sessão obrigatória e sem consumir nada. Devolve `{ acoes: [{ acao, usado, limite }] }` para a conta logada, nas ações `enrich`, `query`, `triagem` e `resposta`, na ordem.

- `usado` vem de `public.uso_diario` no dia de Brasília. A ação sem linha no dia vale 0.
- `limite` é o limite por conta da ação (`UsoDiario.limites(acao)[0]`).
- O limite total do sistema não aparece, porque é dado de operação.
- Se o banco estiver fora, a resposta é 503 e o front esconde o indicador.

**Front:**

- Um bloco "Uso de hoje" no rodapé da sidebar, acima do perfil, com uma linha por ação: rótulo, "usado / limite" e uma barra fina.
  - A barra fica âmbar a partir de 80% e vermelha em 100%.
  - Os rótulos são "Leitura do caso" (`enrich`), "Buscas" (`query`), "Avaliações da IA" (`triagem`, com `title` "Cada lote de até 10 decisões conta 1") e "Respostas da IA" (`resposta`).
- Um contexto `UsoDiarioProvider` busca o `/uso` ao montar e expõe `atualizar()`.
- `atualizar()` é chamado depois de cada `/enrich`, `/query`, lote de `/triagem` e `/resposta` que terminar, com sucesso ou com 429.
- Se `/uso` falhar, o bloco não aparece. O indicador nunca bloqueia nada.

## Decididos pelo advogado

- Caminho 2 (triagem em lotes + resposta).
- A IA lê só a ementa.
- Lote de ~50, a ajustar por medição.
- Entrega progressiva, com opção de parar para economizar tokens.
- Pouco relacionadas recolhidas no fim, com opção de discordar.
- Se a OpenAI estiver fora, mostrar só o resultado da busca.
- O reranker sai inteiro, inclusive do benchmark.
- Múltiplas buscas ficam para depois.
- Mostrar na tela quanto já foi gasto do limite diário.

## Decisões do autor deste documento (conferir)

1. Lotes de 10, com 2 em voo. É isso que permite que "Parar" economize.
2. Resposta gerada uma vez, no fim ou ao parar, com no máximo 25 decisões de nota ≥ 2.
3. Ementa cortada em 1.200 caracteres na triagem e mantida em 2.000 na resposta.
4. Cache por par tese × decisão. A tese do cache e do prompt exclui os filtros.
5. Limite diário por lote que chama a IA, com teto 5× (ver o ajuste na seção 2).
6. Reabrir uma conversa nunca gasta tokens sozinho: usa só o cache e oferece o botão "Avaliar N restantes".
7. O voto não renumera nem refaz a resposta.
8. A faixa livre continua sem triagem, com 20 resultados.
9. A posição de cada decisão no `/resposta` vem do cache da triagem, não do cliente.

## Fica para quem implementa

- O texto final dos prompts. A triagem segue a escala 0–3 acima e as regras de posição que já estão no prompt do `/resposta`.
- O visual da barra de progresso, das três seções e do selo de nota, seguindo os componentes que já existem (`CollapsibleSection`, `EtiquetaBusca`).
- Os nomes internos de funções e tipos.
