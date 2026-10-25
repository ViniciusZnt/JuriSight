# Provimento com o Jev e filtro de provimento antes da busca — design

Data: 2026-10-21 · Branch de origem: `feat/harness-avaliacao` · Autor: Vinicius Zanatta

Documento de passagem: quem pegar isto vai escrever o plano de implementação
(`superpowers:writing-plans`). Tudo o que foi decisão minha, e não do Vinicius, está
marcado como **(decisão minha)**.

## Por quê

O `provimento` de cada acórdão (APROVADO, PARCIAL, NEGADO, NAO_APLICAVEL) hoje sai de uma
regex sobre o dispositivo (`scraper/provimento.py`). Numa conferência de 50 acórdãos, ela
acertou 62%; o Jev (TypeSafe System One) acertou 96%
(`docs/superpowers/specs/2026-10-20-provimento-jev-conferencia.md`, na branch
`feat/provimento-jev`). O advogado já pode filtrar a busca por provimento
(`POST /query`, campo `provimento`), então hoje esse filtro erra em mais de um terço dos
casos.

Além disso, o filtro roda **depois** da busca. `query/search/pipeline.py::buscar` pede
80 documentos ao híbrido (cada canal busca 400 candidatos na base inteira), traz os
documentos do Postgres e só então descarta os de outro provimento
(`aplicar_filtros`). Se o provimento pedido é raro entre os candidatos, sobra pouco
resultado, e um acórdão relevante que estava em 401º em todos os canais nunca entra. O
reranker também pontua todos os candidatos que sobram, o que pesa na latência.

O objetivo final é: **quando o advogado escolhe um provimento, os três canais buscam só
entre acórdãos daquele provimento, e esse provimento é o do Jev.**

## Estado atual (não é começar do zero)

A classificação com o Jev já está quase toda construída e foi mesclada em
`feat/harness-avaliacao` em 2026-10-21 (fast-forward de `feat/provimento-jev`):

- design e plano: `docs/superpowers/specs/2026-10-20-provimento-jev-design.md` e
  `docs/superpowers/plans/2026-10-20-provimento-jev.md`. **Leia o design
  primeiro**: as perguntas, o mapa para o enum, a tabela `provimento_jev` e as regras de
  "já classificado" estão definidos ali e continuam valendo;
- código: `scraper/provimento_jev.py` (perguntas e mapeamento),
  `scraper/provimento_jev_db.py` (tabela `public.provimento_jev`),
  `scraper/provimento_jev_cli.py` (subcomandos `classificar`,
  `aplicar` e `sincronizar`), com testes;
- conferência de 2026-10-20: 96% no provimento, 74% nas três perguntas juntas. Ela apontou
  dois buracos no texto das perguntas (abaixo).

O que falta é fechar a parte A e construir a parte B.

## Parte A — Fechar e adotar o provimento do Jev

1. ~~Merge de `feat/provimento-jev` em `feat/harness-avaliacao`~~ (feito em 2026-10-21).
2. **Ajustar o texto das perguntas** nos dois buracos que a conferência achou. Isso muda o
   `perguntas_sha`, e os 90 documentos já classificados voltam a ficar pendentes (custa
   centavos):
   - *Embargos de declaração acolhidos só para esclarecer, sem efeito modificativo.* Hoje
     não há critério. Proposta **(decisão minha, a confirmar com o Vinicius)**: contam como
     `nao_provido`, porque o resultado do julgamento não muda para ninguém. Acrescentar isso
     ao critério de `nao_provido` e às instruções de `resultado`.
   - *Mais de um recurso, nenhum provido* (um negado, outro não conhecido). A instrução
     atual ("resultados diferentes → parcialmente_provido") marca parcial sem ninguém ter
     ganho. Proposta **(decisão minha)**: `parcialmente_provido` só quando pelo menos um
     recurso foi provido, no todo ou em parte; se nenhum foi, `nao_provido`. Ajustar a
     instrução de `resultado` e o critério de `parcialmente_provido`.
3. **Refazer a conferência** em 50 acórdãos novos, com o mesmo método da anterior
   (leitores cegos, mesmo trecho que o Jev recebe) e registrar num arquivo
   `docs/superpowers/specs/AAAA-MM-DD-provimento-jev-conferencia-2.md`. Critério para
   seguir **(decisão minha)**: provimento nas 4 classes do enum ≥ 90% e nenhum erro nos
   dois casos acima. Se não passar, parar e voltar ao Vinicius.
4. **`classificar` no acervo inteiro** (69.349 acórdãos, ~110 M tokens). Antes, um lote
   cronometrado (`--limite 500`) para confirmar o tempo; o CLI já mostra a estimativa e
   pede confirmação.
5. Validação do provimento: feita pelas conferências cegas (`2026-10-20-provimento-jev-conferencia.md` e `2026-10-22-provimento-jev-conferencia-2.md`); os subcomandos `comparar` e `conferir` foram removidos.
6. **`aplicar --confianca-min 0.8 --confirmar`**. Abaixo de 0,8 o documento fica com o
   valor da regex. Só o Vinicius decide rodar com `--confirmar`.

Os passos 4 a 6 são operação, não código. O plano deve tratá-los como checklist para o
Vinicius, não como tarefas de implementação.

## Parte B — Filtrar por provimento antes da busca

### O que muda

1. **Sincronizar o provimento com os índices.** O design anterior deixou o Qdrant de fora
   ("o pipeline filtra no Postgres"). Este design inverte isso: depois do `aplicar`, o
   valor de `documentos.provimento` precisa chegar a:
   - o payload `provimento` das duas coleções do Qdrant (`COLLECTION_COMPLETO`, por chunk,
     e `COLLECTION_EMENTA`, por documento; ver `indexing/vector_store/qdrant_store.py`).
     Usar `set_payload`, **sem reindexar e sem chamar a OpenAI de novo**. Hoje não existe
     índice de payload em nenhum campo. Criar um índice `keyword` em `provimento` (para o
     filtro ser rápido e o HNSW filtrado não perder recall) e um em `documento_id` (para
     o `set_payload` em lote por filtro `MatchAny`) nas duas coleções;
   - um array paralelo aos `chunk_ids.json` no diretório do índice BM25 (o provimento de
     cada chunk, na mesma ordem). Hoje o BM25 não sabe nada de metadados.

   Forma **(decisão minha)**: um subcomando novo, `sincronizar`, que lê
   `documentos.provimento` do Postgres e atualiza os dois destinos. Ele é idempotente e
   pode rodar depois de cada `aplicar` ou de uma reindexação. O `BM25Builder` também passa
   a gravar o array ao construir o índice (o `Chunk` já tem `provimento`), para um índice
   novo já nascer com ele.

2. **BM25 com máscara.** O `bm25s` 0.3.11 já instalado aceita
   `retrieve(..., weight_mask=np.ndarray)`, que multiplica os scores. `LoadedBM25` carrega
   o array e monta uma máscara por valor do enum (4 arrays de ~400k floats, poucos MB).
   `search()` ganha um parâmetro opcional de provimento. Atenção: com a máscara, o top-k
   pode trazer chunks de score 0 quando há menos acertos que `k`. Esses hits precisam ser
   descartados.

3. **`HybridSearch.search`** passa o provimento aos três canais: `where={"provimento": X}`
   às duas consultas do Qdrant (o parâmetro e o `_build_filter` já existem) e a máscara ao
   BM25.

4. **`pipeline.buscar`**:
   - com só o filtro de provimento, o pool volta a `N_CANDIDATOS_PARA_RERANK` (30), porque
     todos os candidatos já são do provimento certo. Com filtro de período, continua em
     `N_CANDIDATOS_COM_FILTRO` (80);
   - `aplicar_filtros` continua checando provimento no Postgres, como rede de segurança
     barata contra índice dessincronizado **(decisão minha)**.

5. **Sem filtro, o comportamento é idêntico ao de hoje.** Nenhum canal recebe filtro ou
   máscara, e o resultado tem que sair igual.

### Como saber se funcionou

O `eval` do harness roda sem filtro, então não mede esta mudança. Medir assim
**(decisão minha)**: para as teses do conjunto-ouro, rodar a busca com cada um dos três
provimentos (APROVADO, PARCIAL, NEGADO), antes e depois, e comparar:

- quantos resultados voltam (a meta é chegar a 10 sempre que a base tiver 10 acórdãos
  daquele provimento sobre o tema);
- latência de ponta a ponta;
- se todo resultado tem o provimento pedido (tem que ser 100%).

Um script em `avaliacao/` ou `utils/` que imprime essa tabela basta. Não precisa entrar no
CLI do harness.

## Não-objetivos

- Filtro de período antes da busca. O Qdrant suporta isso (`DatetimeRange` com índice
  `datetime`), mas fica para depois; o período continua pós-busca.
- Usar `favorece` e `recorrente` na busca, na ordenação ou na tela (sinal de stance).
  Plano seguinte.
- Chamar o Jev na coleta (`scraper/doc_builder.py` segue com a regex). Documentos novos
  entram com a regex até o `classificar` rodar de novo.
- Colapsar resultados do mesmo `numero_processo` no top-10. Foi discutido e é uma boa
  ideia, mas é outro trabalho.
- Qualquer tratamento de NLP no BM25 (stemming, lematização, stopwords do domínio). Ficou
  decidido que não entra (inventário de 21/10, tabela de decisões).
- Mudar o enum `Provimento` ou o frontend.

## Anti-objetivos

- Um resultado com filtro APROVADO trazer acórdão de outro provimento.
- A busca sem filtro mudar de resultado ou de latência.
- Reindexar embeddings ou chamar a OpenAI para atualizar provimento.
- Escrever em `documentos.provimento` sem `aplicar --confirmar` explícito do Vinicius.
- Perder o valor da regex: ele continua em `provimento_jev.provimento_regex` e
  recalculável por `utils/reclassify.py`.

## Restrições

- Máquina com 11 GB de RAM e sem GPU. O BM25 é carregado com `mmap=True` e o Qdrant guarda
  vetores e HNSW em disco. Nada pode carregar o corpus inteiro na RAM.
- Jev: `TYPESAFE_MODEL` (padrão `jev-1.13.0`), nunca `jev-latest`.
- Escala: 69.349 acórdãos e ~400k chunks; só há acórdãos no acervo
  (`hierarquia_categoria` é sempre 4).
- O harness de avaliação não usa mais o Jev como juiz (removido em 2026-10-21): o Jev
  só classifica provimento. O CLI do provimento não depende de nada em `avaliacao/`.
- Padrões do projeto: identificadores e docstrings em português, psycopg puro, fakes
  injetados nos testes, nunca imprimir nem editar o `.env`. Testes de integração com
  Postgres usam `skipif` sem `DATABASE_URL`.

## O que fica para quem constrói

Nomes internos, formato do array de provimento no disco (JSON ou `.npy`), tamanho do lote
do `set_payload`, se `sincronizar` mora no CLI do provimento ou em `indexing/`, e o layout
da tabela de medição.
