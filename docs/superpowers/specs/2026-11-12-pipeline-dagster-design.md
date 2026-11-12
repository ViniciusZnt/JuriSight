# Pipeline de dados no Dagster (VPS) + limpeza de código morto — design

Data: 12/11/2026. Prazo do TCC: 20/11/2026.

## Por quê

Hoje cada etapa do processamento de dados é um comando separado rodado à mão, na ordem
certa, na máquina local (coleta → indexação → preparar filtros; Jev à parte), e o acervo
de produção é uma **cópia** do local (pg_dump + volume do Qdrant + rsync). Decisão do
Vinicius: a VPS passa a ser a fonte da verdade do acervo; o ônus de ordem, retomada,
logs e histórico passa para o **Dagster**, rodando na VPS. A máquina local vira só
ambiente de desenvolvimento.

## O que muda

### Assets (cada parte do processamento, separada)

| Asset | O que faz | Config de run | Metadados no Dagster |
|---|---|---|---|
| `acervo` | coleta do TST (scraper) direto no Postgres | `data_inicio`/`data_fim` opcionais (vazio = continua do banco), `colecao` (padrão `acordaos`) | docs novos, período coletado, páginas, tempo |
| `indices` | a passada única do `indexing/run.py`: chunking → BM25 (reconstruído do zero) + embeddings OpenAI → Qdrant (delta: pula o que já está lá) | — | docs, chunks, embeddados × pulados, falhas, tempo |
| `filtros` | `preparar`: dispositivos + NR/Tema/SV + tsv | — | dispositivos, pares, totais nr/tema/sv, tempo |
| `jev_classificacoes` | Jev classifica acórdãos pendentes (equivale ao `classificar --sim`; materializar o asset **é** a confirmação de custo) | `limite`, `lote`, `max_workers` | classificados, estimativa de tokens, tempo |
| `jev_provimento` | aplica o Jev em `documentos.provimento` (equivale ao `aplicar --confirmar`) | `confianca_min` (padrão 0.8) | transições, abaixo do limite, tempo |
| `jev_sincronizado` | leva `documentos.provimento` ao Qdrant e ao provimentos.json | — | docs sincronizados, tempo |

Dependências: `indices` e `filtros` dependem de `acervo`;
a cadeia Jev é `jev_classificacoes → jev_provimento → jev_sincronizado`.

Nota (conferida no código): a indexação é **uma passada só** — o chunking alimenta o BM25
e os embeddings juntos — por isso um asset `indices`, e não dois; separar dobraria o
chunking dos ~69 mil docs sem ganho. E a reconstrução do BM25 lê `documentos.provimento`
do Postgres, que já carrega o resultado do Jev depois do `aplicar`: um `full` **não**
perde o trabalho do Jev (docs novos ficam com o provimento da regex até o Jev rodar).

### Jobs

- **`full`** = `acervo` → `indices` → `filtros`. **Sem Jev** (decisão
  do Vinicius: Jev custa tokens e fica de fora do full).
- Um job por parte: `coleta`, `indexacao`, `so_filtros`, `jev` (a cadeia).
- Disparo **manual pela UI**, sem agendamento. Fila com **1 run por vez** (a VPS tem 16 GB
  e o app em uso ocupa 8–10 GB; indexação e BM25 não podem empilhar).

### Logs como metadados

- Os números que hoje saem em print/log (contagens, totais, tempos) viram metadados
  estruturados da materialização, visíveis na UI com histórico por run.
- O stdout/stderr de cada run fica guardado pelo próprio Dagster (compute logs), então o
  log completo de cada etapa é consultável pela UI.

### Onde roda e como se acessa

- Serviço novo `dagster` no `docker-compose.prod.yml`, com acesso a postgres/qdrant/ollama
  e ao `.env`, montando o **mesmo bind `./data`** da api (o BM25 e o `provimentos.json`
  que ele escreve precisam aparecer para a api).
- A imagem é um **segundo estágio do Dockerfile** em cima da base da api: o scraper abre o
  portal com Playwright/Chromium (`session_minter.py`), então esse estágio roda
  `playwright install --with-deps chromium`. A imagem da api fica como está.
- UI só interna: porta publicada em `127.0.0.1` da VPS; acesso por **túnel SSH**
  (`ssh -L 3001:localhost:3000 deploy@...`), decisão do Vinicius. Nada no Caddy.
- Histórico do Dagster em SQLite num volume novo (`dagster_home`), com `dagster.yaml`
  fixando fila de 1 run (`QueuedRunCoordinator`, `max_concurrent_runs: 1`) — sem banco novo.
- Processo único `dagster dev` (webserver + daemon juntos): é o modo mais simples e basta
  para um usuário; se incomodar, separar depois.

## Decisões já tomadas

**Do Vinicius:** Dagster; roda na VPS; VPS vira fonte da verdade (fim da cópia
local→VPS); cada parte como asset + jobs individuais + um full; intervalo de datas do
scrape configurável por run; logs/números como metadados; Jev fora do full; UI por túnel SSH.

**Minhas (podem ser revistas):**

- Os assets **chamam as funções que os CLIs já usam** (orchestrator do scraper, funções do
  `indexing/run.py`, `preparar`, funções do `provimento_jev_cli`), extraindo-as para serem
  importáveis onde preciso. Os CLIs continuam funcionando — localmente nada muda.
- Intervalo de datas por **run config**, não por partições do Dagster (partições/backfills
  são complexidade que esse acervo não pede).
- Código novo num pacote `pipeline/` na raiz (definitions + assets num arquivo ou dois).
- `dagster` e `dagster-webserver` entram como dependência normal no `pyproject.toml`
  (a imagem cresce um pouco; aceitável).
- Depois de um `full`, a **api precisa de restart** para recarregar o BM25 (ela carrega o
  índice na memória ao subir; Postgres e Qdrant são lidos ao vivo e não precisam). O
  pipeline **não** mexe em outros containers (precisaria do socket do Docker — risco sem
  ganho); o restart é manual e documentado, e o asset `indices` termina com essa
  instrução nos metadados.
- Sem schedule, sem sensor, sem retry automático, sem auth própria na UI.
- `jev_classificacoes` nasce com `limite` padrão **500** (um lote); `0` = sem limite. Na UI
  não há o s/N do terminal, então o padrão baixo evita que um clique classifique o acervo
  inteiro; a estimativa de tokens entra nos metadados do run.
- Coleta interrompida pelo portal (hoje `sys.exit(2)`) **falha o run** com o progresso nos
  metadados — o estado fica salvo no banco e rodar de novo retoma; o `full` não segue com
  coleta pela metade.
- O `--reset` do scraper e o `--reset` da indexação **não existem** na UI — nenhum asset
  apaga acervo ou índice em produção.
- O `full` é só `acordaos`; as outras coleções (`sumulas`, `ojs`, `precedentes`) podem ser
  coletadas pelo job `coleta`, mas indexá-las fica fora desta etapa (o acervo pesquisável
  hoje é 100% acórdãos).
- O cron de backup (`pg_dump` diário) fica como está, fora do Dagster.
- README ganha a seção do pipeline (como abrir o túnel, rodar jobs, o restart da api) e a
  seção de cópia local→VPS vira nota histórica.

## Riscos aceitos

- **Scrape saindo do IP da VPS:** o portal do TST pode tratar o IP de datacenter
  diferente do residencial. O scraper já tem delay adaptativo e retomada; se o portal
  bloquear, o fallback é coletar localmente e subir o dump (o caminho antigo continua
  documentado como nota histórica).
- **RAM durante indexação/BM25 com o app no ar:** mitigado pela fila de 1 run e por rodar
  fora do horário de uso; não há guard-rail automático.

## Fora desta etapa

- Agendamento automático e sensores.
- Partições/backfills do Dagster.
- Auth na UI do Dagster (o túnel é a proteção).
- Mover o backup para o Dagster.
- Qualquer mudança na busca, na API do app ou no frontend.

## Parte 2 — código morto

Varredura feita em 12/11; quase tudo que parecia morto está vivo (rerankers extras são do
benchmark S0–S6 e têm testes; `main.py` é usado pelo `run.sh`; `requirements.txt` é
fallback documentado para pip; `utils/reclassify.py` é o caminho de volta para a regex).
Remoções:

| Item | Por quê | Como |
|---|---|---|
| `indexing/vector_store/migrate_chroma_to_qdrant.py` | migração Chroma→Qdrant concluída há meses; Chroma não existe mais no projeto | remover + tirar a menção do README §Escalabilidade (vira uma linha histórica com o hash do commit) |
| `evaluation/` (só `__pycache__`), `jurisight.egg-info/`, `indexing.log`, `Legal AI Research Platform.zip` | lixo local não rastreado | apagar do disco; conferir cobertura no `.gitignore` |
| `data/index/bm25.pkl` (1,1 GB, local) | índice do formato antigo, já documentado como "não vai" | apagar do disco local |

Critério para qualquer remoção extra que o builder encontrar: só remove com `grep` limpo
(nenhuma referência fora do próprio arquivo e do README) **e** suíte verde depois.

## Como saber que funcionou

- Na VPS, `ssh -L 3001:localhost:3000` abre a UI do Dagster com os assets e jobs listados.
- Rodar `coleta` com `data_inicio`/`data_fim` de um período curto coleta só aquele período
  e mostra as contagens como metadados do run.
- Rodar `full` deixa documentos novos pesquisáveis (depois do restart da api): aparecem na
  busca e nos filtros (autocompletar com totais novos).
- A cadeia `jev` roda sem prompt interativo e `jev_provimento` respeita `confianca_min`.
- Dois runs disparados juntos entram em fila (1 por vez).
- Suíte verde depois da limpeza; `migrate_chroma_to_qdrant.py` fora do repo.
