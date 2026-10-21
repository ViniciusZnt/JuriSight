# Reclassificação do provimento com o Jev — design

Data: 2026-10-20 · Branch de origem: `feat/harness-avaliacao`

## Por quê

Hoje o `provimento` de cada acórdão sai de uma regex (`scraper/provimento.py`) que
procura no dispositivo frases como "negar provimento" e devolve `APROVADO`, `PARCIAL`,
`NEGADO` ou `NAO_APLICAVEL`. Isso diz se o recurso foi aceito, mas não diz quem ganhou:
"recurso negado" é vitória do trabalhador quando quem recorreu foi a empresa. O acervo
não registra quem recorreu (o `cabecalho` não traz "recorrente" em nenhum dos 69.349
acórdãos). Sem isso, a busca não sabe de que lado cada acórdão ficou, que é o sinal que
falta para separar o acórdão que fortalece a tese do que a enfraquece.

O Jev (TypeSafe System One) responde perguntas de escolha fechada com probabilidades,
que é exatamente o formato desta tarefa. O usuário quer usá-lo aqui de qualquer forma.

## Objetivo

Para cada acórdão, guardar três respostas do Jev, com probabilidades e confiança:

1. **resultado** do recurso: `provido`, `parcialmente_provido`, `nao_provido`,
   `nao_conhecido`, `sem_recurso`;
2. **recorrente**: `reclamante`, `reclamada`, `ambos`, `outro`, `indefinido`;
3. **favorece**: `reclamante`, `reclamada`, `ambos_em_parte`, `indefinido`.

Depois de uma conferência manual feita pelo próprio usuário, passar a usar o resultado
do Jev na coluna `documentos.provimento`, onde a confiança for alta.

## Não-objetivos

- Usar `favorece`/`recorrente` na busca, na tela ou no harness. Fica para um plano
  seguinte (sinal de stance). Este plano só produz e guarda o dado.
- Chamar o Jev na coleta (`scraper/doc_builder.py` segue com a regex). Documentos novos
  entram com a regex e são classificados quando o backfill rodar de novo.
- Atualizar o payload `provimento` no Qdrant. O pipeline filtra provimento no Postgres
  (`query/search/pipeline.py::aplicar_filtros`), não no Qdrant.
- Mudar o enum `Provimento` ou o frontend.

## Anti-objetivos

- Perder a classificação da regex: ela fica gravada ao lado (`provimento_regex`) e
  continua recalculável a partir do texto (`utils/reclassify.py`).
- Escrever em `documentos.provimento` sem o usuário pedir explicitamente.
- Gastar duas vezes: o backfill é retomável e não reclassifica o que já foi feito com o
  mesmo modelo e as mesmas perguntas.

## Restrições

- Modelo do Jev: `TYPESAFE_MODEL` (padrão `jev-1.13.0`), nunca `jev-latest`.
- Custo estimado: ~1.600 tokens por acórdão × 69.349 ≈ 110 M tokens. O CLI mostra a
  estimativa e pede confirmação antes; `--sim` pula.
- Máquina sem GPU e com 11 GB de RAM: o trabalho é só chamadas à API, sem modelo local.
- Padrões do projeto: identificadores e docstrings em português, psycopg puro, fakes
  injetados nos testes, nunca imprimir nem editar o `.env`.

## Como (decisões)

**Entrada do Jev** — decisão minha. Estado `{"acordao": {"ementa": ementa[:1500],
"dispositivo": acordao[-4000:]}}`. O dispositivo fica no fim do texto do acórdão
(mediana de ~1.600 caracteres a partir do último marcador; o texto inteiro tem mediana
de 11.500 e p99 de 81.000), e os últimos 4.000 caracteres o cobrem na maioria dos casos
sem estourar custo. A ementa ajuda quando o dispositivo é só "nos termos do voto".
Acórdão com `acordao` vazio ou só espaços não é enviado ao Jev.

**Perguntas** — texto fixo, versionado por um `perguntas_sha` como no harness:

- `resultado` (Choice) — instruções: "Qual foi o resultado do recurso julgado neste
  acórdão (`acordao`)? Se houver mais de um recurso com resultados diferentes, escolha
  parcialmente_provido."
  - `provido`: "O recurso foi provido (aceito) integralmente."
  - `parcialmente_provido`: "O recurso foi provido em parte, ou há mais de um recurso com resultados diferentes."
  - `nao_provido`: "O recurso foi conhecido, mas o provimento foi negado."
  - `nao_conhecido`: "O recurso não foi conhecido (não foi admitido para julgamento do mérito)."
  - `sem_recurso`: "O texto não julga um recurso (por exemplo, incidente, ação originária ou homologação)."
- `recorrente` (Choice) — instruções: "Quem interpôs o recurso julgado neste acórdão (`acordao`)?"
  - `reclamante`: "O trabalhador (reclamante, autor)."
  - `reclamada`: "A empresa ou o empregador (reclamada, ré)."
  - `ambos`: "Reclamante e reclamada recorreram."
  - `outro`: "Outra parte (Ministério Público do Trabalho, União, terceiro)."
  - `indefinido`: "O texto não permite saber quem recorreu."
- `favorece` (Choice) — instruções: "Considerando o resultado final deste acórdão
  (`acordao`), a decisão favorece o trabalhador (reclamante) ou a empresa (reclamada)?"
  - `reclamante`: "O resultado favorece o trabalhador."
  - `reclamada`: "O resultado favorece a empresa."
  - `ambos_em_parte`: "Cada parte ganhou em algum ponto."
  - `indefinido`: "O texto não permite saber a quem o resultado favorece."

**Lado neutro** — decisão minha. `favorece` é registrado em termos de parte
(reclamante/reclamada), não de "a favor da tese". Assim funciona tanto para advogado
de trabalhador quanto de empresa; a pergunta de qual lado os usuários defendem ficou
sem resposta e não muda este dado.

**Checagem de coerência** — decisão minha. Uma regra deriva `favorece` de
(`resultado`, `recorrente`) quando é inequívoco:

| recorrente | provido | parcialmente_provido | nao_provido / nao_conhecido |
|---|---|---|---|
| reclamante | reclamante | ambos_em_parte | reclamada |
| reclamada | reclamada | ambos_em_parte | reclamante |

Nos outros casos (ambos, outro, indefinido, sem_recurso) a regra não opina. O relatório
mostra quanto o `favorece` do Jev concorda com a regra aplicada às respostas do próprio
Jev. Discordância indica leitura errada de negação, o ponto fraco declarado do Jev.

**Armazenamento** — tabela nova `public.provimento_jev`, uma linha por documento
(`documento_id` UUID PK, FK para `documentos(id)` com `ON DELETE CASCADE`), com as três
respostas, as probabilidades (JSONB), as três confianças, o `provimento_regex` no momento
da classificação, `modelo`, `perguntas_sha` e `criado_em`. Upsert por `documento_id`.
"Já feito" = linha com o mesmo `modelo` e `perguntas_sha`.

**Validação** — sem a especialista. O CLI gera um CSV com uma amostra (seed fixa) das
divergências entre regex e Jev, com o trecho do dispositivo e uma coluna `quem_acertou`
(`jev`, `regex`, `ambos`, `nenhum`) que o usuário preenche. Um subcomando lê o CSV e
resume quem acertou mais.

**Adoção** — `documentos.provimento` passa a vir do Jev pelo mapa
`provido→APROVADO`, `parcialmente_provido→PARCIAL`, `nao_provido→NEGADO`,
`nao_conhecido→NEGADO`, `sem_recurso→NAO_APLICAVEL`, só onde
`confianca_resultado >= --confianca-min` (padrão 0,8). Sem `--confirmar`, só mostra as
transições. `nao_conhecido→NEGADO` repete o que a regex já faz.

## O que fica para quem constrói

Nomes internos, tamanho do lote de gravação, formato das tabelas impressas, layout do CSV
além das colunas citadas.
