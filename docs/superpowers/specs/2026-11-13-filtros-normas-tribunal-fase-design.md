# Normas num campo só, NRs/Temas/Súmulas vinculantes filtráveis, tribunal e fase — design

Data: 13/11/2026. Prazo do TCC: 20/11/2026. Continua `docs/superpowers/specs/2026-11-10-filtro-restrito-design.md`.

## Por quê

Na Revisão de Contexto há dois campos de norma ("Dispositivos legais", que filtra, e "Outras normas", que só vai para o BM25), e o advogado não entende por que são dois. Além disso, normas muito usadas na Justiça do Trabalho não podem ser exigidas porque não estão nos dispositivos do acervo (`referencia_legislativa`):

| Tipo | Decisões que citam no texto (ementa + fundamentação) | Nos dispositivos do acervo |
|---|---|---|
| Temas (repercussão geral / repetitivos) | 10.583 | 0 |
| NRs | 4.745 (NR-15: 3.262; NR-16: 1.017) | 0 |
| Súmulas vinculantes | 1.208 | 0 |

E o advogado não consegue restringir a busca ao tribunal onde litiga nem à fase do processo: os filtros de tribunal e período da tela de resultados só agem sobre as 20 decisões já mostradas, não sobre o acervo. Hoje uma busca de horas extras mistura acórdãos de conhecimento (ROT 37,7 mil, RORSum 12,9 mil) com agravos de petição da execução (AP 15,6 mil, AIAP 953), que discutem cálculo e não o direito.

## O que muda para o advogado

### Revisão de Contexto — bloco "Filtro restrito"

1. **Um campo só: "Normas e dispositivos"** (substitui "Dispositivos legais" e "Outras normas").
   - Digitar abre o autocompletar como hoje, agora também com NRs ("nr 15" → "NR-15 · N decisões"), Temas ("tema 1046" → "Tema 1046 · N") e Súmulas vinculantes ("vinculante 4" → "Súmula Vinculante 4 · N").
   - Escolher da lista cria um **chip sólido azul = filtra**.
   - Apertar Enter com um texto que não está na lista cria um **chip contornado com a etiqueta "só busca livre"** — vai para o BM25 como texto, não filtra (é o que hoje faz "Outras normas").
   - Chips "sugestão da IA" e as sugestões clicáveis de dispositivos continuam iguais.
2. **Tribunal**: o advogado escolhe um ou mais tribunais (lista dos 25, cada um com o total de decisões no acervo). Entre os escolhidos vale "OU" (TRT-4 **ou** TRT-12); com os outros filtros vale "E".
3. **Fase do processo**: Todas · Conhecimento · Execução · Outras, escolha única.
   - Conhecimento = ROT, RORSum, RO, RemNecRO, AIRO.
   - Execução = AP, AIAP.
   - Outras = as demais classes (MSCiv, AR, AgRT, TutCautAnt…).
   - "Todas" = sem filtro de fase (padrão).
4. "Expressões obrigatórias" continua como está.
5. A contagem combinada ("Com todos os filtros: N decisões") passa a considerar tribunal e fase.

A IA não preenche tribunal nem fase nesta etapa.

### Resultados

- "Como esta busca foi feita" (coluna Filtro restrito) e o resumo das decisões mostram também o tribunal e a fase escolhidos (ex.: etiquetas "TRT-4", "Execução").
- Os filtros de tribunal/período da barra de resultados continuam agindo só sobre a lista mostrada (sem mudança).

## Objetivos

1. Um campo só de normas na Revisão, com a diferença filtra / só busca livre visível no próprio chip.
2. NR, Tema e Súmula vinculante podem ser exigidos como qualquer artigo; a faixa restrita só traz decisões cujo texto os cita.
3. Tribunal e fase restringem a busca no acervo inteiro (servidor), como os dispositivos.
4. Busca sem nenhum filtro restrito continua igual à de hoje.

## Fora desta etapa

- Filtro pelo desfecho classificado pelo Jev no acervo todo (risco de erro da classificação).
- Turma e relator.
- Período no servidor.
- A IA sugerir tribunal ou fase.
- Normas coletivas (CCT/ACT): são do caso, não do acervo; continuam como expressão obrigatória.

## Decisões

Decididas pelo Vinicius: campo único com dois tipos de chip (A); NRs, Temas e Súmulas vinculantes extraídos do texto e filtráveis (B); tribunal e fase como filtro restrito no servidor, escolhidos na Revisão.

Decididas por mim (podem ser revistas):

- **Códigos novos no mesmo formato do acervo**, gravados em `public.documento_dispositivo` pelo `preparar`, extraídos por regex do texto de ementa + fundamentação:
  - `nr_15` → rótulo "NR-15" (aceita "NR 15", "NR-15", "NR nº 15", "Norma Regulamentadora 15", com zero à esquerda);
  - `tema_1046` → "Tema 1046" (sem distinguir STF/TST: o texto nem sempre diz e a maioria dos Temas citados na JT é de repercussão geral do STF);
  - `sv_4` → "Súmula Vinculante 4".
  `niveis()` desses códigos é só o próprio código; `codigo_de_texto` e `tokens_da_busca` passam a reconhecer os três formatos. O `preparar` continua idempotente; a extração entra na carga dos dispositivos (o tempo dessa etapa cresce de ~8 s para o que a regex levar — medir).
- **Tribunal e fase moram na própria decisão** (`documentos.tribunal`, `documentos.sigla_classe`), sem tabela nova. A lista de classes de cada fase fica num só lugar do backend; "Outras" é tudo que não é conhecimento nem execução.
- **`EstruturaArgumentativa` ganha `tribunais: list[str] = []` e `fase: Literal["conhecimento","execucao","outras"] | None = None`**; padrões vazios, então conversas antigas e a chave do cache da resposta (`exclude_defaults`) não mudam. `temFiltroRestrito` passa a contar tribunal e fase. Limite de tamanho como nos outros campos.
- **Rótulo do tribunal** "TRT-4" (mesmo padrão do `orgaoDe`); o valor gravado é o do acervo ("TRT4").
- **A lista de tribunais com total** vem de um endpoint leve (`GET /filtros/tribunais`), consultado uma vez por tela.
- O BM25 da busca livre não recebe tribunal nem fase (não são termos).

### Respostas à revisão do documento (decididas por mim)

- **Rótulos dos códigos novos:** são derivados do código pela mesma regra do `rotulo()` (`nr_15` → "NR-15", `tema_1046` → "Tema 1046", `sv_4` → "Súmula Vinculante 4"). O `preparar` grava só o código. O autocompletar sugere só o que existe na tabela `public.dispositivo`, ou seja, o que aparece no acervo, com o total.
- **Súmula vinculante:** só conta quando o texto diz "vinculante" (ou "SV") colado ao número: "Súmula Vinculante 4", "Súmula Vinculante nº 4", "SV 4". "Súmula 4 do STF" e "Súmula 4 do TST" não viram `sv_4`. A contagem de 1.208 usou o mesmo critério ("súmula vinculante").
- **Tribunal e fase sozinhos valem:** "TRT-4 + Conhecimento", sem dispositivo nem expressão, já é busca restrita. O `FiltroStore` monta a condição só com tribunal e fase, e `temFiltroRestrito` conta os dois.
- **Campo único e dados salvos:**
  - O modelo de dados não muda: `estrutura.dispositivos` (códigos, filtram) e `estrutura.normas` (texto, só BM25). O campo único só desenha os dois juntos, e `normas` aparece como chip "só busca livre".
  - Conversas antigas abrem como estão: o texto em `normas` não vira filtro sozinho.
  - Numa extração nova, se o advogado escrever "NR-15" no texto do caso, o `/enrich` converte para `nr_15` ativo, porque `codigo_de_texto` passa a reconhecer NR, Tema e SV. É a mesma regra dos artigos citados no texto.
- **Fase "Outras":** é tudo que não está em conhecimento nem em execução, inclusive `sigla_classe` vazia ou nula.
- **Ordem de entrega, por causa do prazo de 20/11:**
  1. Tribunal e fase, que não exigem preparo.
  2. Campo único de normas.
  3. Extração de NR, Tema e SV.

  O `preparar` roda na VPS depois do merge, fora do horário de uso. Se a extração atrasar, as duas primeiras partes já entregam valor sozinhas.

## Fica com quem construir

- A forma exata da regex de extração, desde que cubra as variações acima e não confunda "NR" dentro de palavras nem "tema" usado em sentido comum ("tema central") — exigir número logo depois.
- Como juntar tribunal/fase às consultas do `FiltroStore` (EXISTS em `documentos` ou colunas copiadas para `documento_tsv`), desde que contagem e elegíveis continuem < 1 s.
- O componente visual de tribunal (chips com busca, menu multiseleção) e de fase (controle segmentado), seguindo a identidade da tela (azul #1A3A5C, chips como os de dispositivos).

## Como saber que funcionou

- "nr 15" no autocompletar mostra "NR-15" com um total próximo de 3.262; exigir NR-15 + "adicional de insalubridade" traz só decisões cujo texto cita a NR-15.
- "tema 1046" aparece no autocompletar e filtra.
- Tribunal TRT-4 + fase Conhecimento: todas as decisões da faixa restrita são do TRT4 e de classe ROT/RORSum/RO/RemNecRO/AIRO.
- Texto livre em "Normas e dispositivos" vira chip "só busca livre" e aparece nos termos do BM25 em "Como esta busca foi feita", sem entrar no filtro.
- Busca sem filtro igual à da `main`; conversa antiga abre normalmente.
- Deploy: rodar o `preparar` de novo na VPS (fora do horário de uso).
