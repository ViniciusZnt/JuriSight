# Filtro restrito por dispositivos e expressões — design

Data: 10/11/2026. Prazo do TCC: 20/11/2026.

## Por quê

Uma pessoa que usou o JuriSight buscou **danos morais coletivos** e recebeu decisões sobre **dano moral individual**. O advogado procura sempre o caso mais específico possível. Por isso, uma decisão "parecida" mas de outra esfera é pior do que nenhuma decisão.

Hoje a busca não tem como exigir nada. O BM25 e o embedding tratam "coletivo" como só mais uma palavra da frase, e as milhares de decisões de dano moral individual tomam o lugar das poucas que tratam do coletivo.

Medido no banco local (69.349 acórdãos de 2025):

- **Os dispositivos não separam coletivo de individual.** As ementas com "dano moral coletivo" citam principalmente CC art. 186 e 927 e CF art. 5º, V e X, que são os mesmos artigos do dano moral individual. A Lei 7.347/85 quase não aparece, e nenhuma decisão tem a classe Ação Civil Pública.
- **O que separa é a expressão.** São 53 ementas com "dano moral coletivo", ou 137 contando a fundamentação.
- **O filtro por dispositivo serve para os temas que a própria lei define.** Na gestante, `b_ii_art_10_adct` aparece em 163 decisões e `art_10_adct` em 156.
- **`referencia_legislativa` está preenchido em 69.248 decisões**, com média de 10 dispositivos cada e 15.621 valores distintos. Os valores vêm em níveis: `b_ii_art_10_adct` (ADCT art. 10, II, b), `prgf_2_art_791_clt` (CLT art. 791, § 2º), `sumula_85_tst`, `prgf_5_art_28_lei_8078_90`. Entre eles aparecem também valores que não são dispositivos, como `trt9` e `adct`.

## O que muda para o advogado

Ele passa a ter dois jeitos de buscar, e a tela deixa claro qual é qual:

- **Filtro restrito:** dispositivos legais e expressões obrigatórias. Só entram decisões que citam **todos** os dispositivos e contêm **todas** as expressões.
- **Busca livre (semântica):** a busca de hoje, por semelhança, sem garantia de citar ou conter nada.

### Revisão de Contexto

- **"Normas jurídicas" vira "Dispositivos legais · filtro restrito".**
  - Ao digitar, o campo sugere dispositivos que existem no acervo, com o nome legível e quantas decisões citam cada um. "art 15", "clt 15" ou "15 clt" sugerem "CLT art. 15 · N decisões" e "CPC art. 15 · N decisões".
  - O advogado escolhe da lista. O chip mostra o nome legível, e o filtro usa o código (`art_15_clt`).
  - Ele pode escolher qualquer nível: "ADCT art. 10" pega qualquer inciso e alínea do art. 10; "ADCT art. 10, II, b" pega só a alínea b.
- **As normas extraídas pela IA são convertidas para o código do acervo.**
  - As que existem no acervo viram chips marcados como **sugestão da IA**. Elas valem como filtro, a menos que o advogado as remova.
  - As que não convertem ou não existem no acervo aparecem com o aviso "não encontrado no acervo, não filtra". Elas continuam indo como texto para a busca livre, como hoje.
- **Campo novo: "Expressões obrigatórias · filtro restrito".**
  - É texto livre, com uma expressão por chip, e começa vazio. A IA não preenche esse campo nesta etapa.
  - Cada chip mostra quantas decisões contêm a expressão ("dano moral coletivo · 137 decisões").
- **Contagem combinada:** abaixo dos dois campos aparece "Com todos os filtros: N decisões", atualizada a cada mudança. Com N = 0, aparece o aviso de que a faixa restrita virá vazia.
- **Explicação na tela:** uma frase curta, junto dos dois campos, diz que eles restringem a busca, enquanto os outros campos só orientam a busca livre.
- **Edição dos chips:** todos os chips de todos os campos ganham um ícone de lápis visível, que abre a edição. O duplo clique pode continuar existindo.

### Tela de resultados

- **Sem dispositivo nem expressão:** a lista aparece como hoje, com uma linha dizendo que a busca é só semântica e que dá para restringir informando dispositivos ou expressões na Revisão de Contexto.
- **Com filtro, duas faixas:**
  1. **"Filtro restrito"**, aberta. Diz o que foi exigido e quantas decisões do acervo cumprem tudo: "5 decisões citam ADCT art. 10 e contêm 'dano moral coletivo'". Mostra até 20, na ordem da busca.
  2. **"Busca livre (semântica)"**, fechada, com um botão para abrir. Diz que são decisões parecidas sem garantia de cumprir o filtro e não repete as decisões da primeira faixa.
- **Faixa restrita vazia:** "Nenhuma decisão do acervo (≈70 mil acórdãos de 2025) cita … e contém …". A faixa livre continua disponível para abrir.
- **Resposta gerada:**
  - com filtro ativo, usa só as decisões da faixa restrita;
  - com a faixa restrita vazia, não é gerada, e a tela explica por quê;
  - sem filtro, funciona como hoje.

## Objetivos

1. Na faixa restrita, toda decisão cumpre todos os filtros, sem exceção.
2. O advogado não precisa saber o formato dos códigos: ele escolhe da lista.
3. Antes de buscar, o advogado sabe quantas decisões o filtro vai trazer.
4. A busca de "danos morais coletivos" com a expressão "dano moral coletivo" traz na faixa restrita só decisões que contêm a expressão, no singular ou no plural.

## Fora desta etapa

- Autocompletar para expressões, montado a partir dos verbetes das ementas. Os verbetes em maiúsculas no início da ementa ("ADICIONAL DE INSALUBRIDADE. LAUDO PERICIAL.") existem em 38 mil decisões e cerca de 3 mil aparecem em 5 ou mais. É o próximo passo, se sobrar tempo, e reaproveita o componente de autocompletar dos dispositivos.
- Facetas de dispositivos na tela de resultados (clicar nos dispositivos mais citados entre as decisões encontradas).
- Mostrar o que entrou na busca semântica e no BM25, renomear os títulos dos campos ("Agentes nocivos"), o guia de uso e a IA sugerir palavras-chave. São projetos separados.
- Operador "OU" entre filtros. Entre filtros vale sempre "E".

## O que não pode acontecer

- Uma decisão na faixa restrita que não cumpre o filtro.
- Completar a faixa restrita com decisões que não cumprem o filtro, sem avisar.
- Uma norma extraída pela IA filtrar sem aparecer na Revisão de Contexto como filtro que o advogado pode remover.
- Conversas salvas antes da mudança deixarem de abrir.
- A busca ficar perceptivelmente mais lenta. Meta: a busca com filtro leva no máximo cerca de 2 s a mais que a busca de hoje, e cada contagem responde em menos de 1 s.

## Decisões

Decididas pelo Vinicius:

- O filtro é restrito: só entra quem cumpre. A lista nunca é completada com decisões parecidas.
- Há duas faixas: a restrita aberta e a livre fechada, que abre com um clique.
- As expressões ficam num campo próprio, "Expressões obrigatórias". Nesta etapa é texto livre com contagem, e o autocompletar por verbetes fica para depois.
- Os dispositivos têm autocompletar com o que está indexado.
- As normas extraídas pela IA também filtram, aparecendo como sugestão que o advogado pode remover.

Decididas por mim (podem ser revistas):

- **A lista de quem passa no filtro vem do Postgres, e o Qdrant filtra por `documento_id`.**
  - O Vinicius tinha imaginado os dispositivos como metadado dos pontos no Qdrant. Na prática, a expressão só pode ser conferida no texto, que está no Postgres. Com uma fonte só, os dois filtros, as contagens e o autocompletar usam a mesma tabela.
  - Assim não é preciso regravar o payload dos ~400 mil pontos do Qdrant. A busca semântica da faixa restrita continua no Qdrant, filtrada pelos ids (`documento_id` já tem índice de payload).
  - Se algum dispositivo muito citado deixar a lista de ids grande demais, por exemplo CLT art. 791, com 11 mil decisões, gravar `dispositivos` no payload passa a valer a pena.
- **Tabela `public.documento_dispositivo (documento_id, codigo)`.**
  - Cada valor de `referencia_legislativa` entra com todos os níveis acima dele: `b_ii_art_10_adct` gera também `ii_art_10_adct` e `art_10_adct`. Assim, escolher "ADCT art. 10" pega todas as variações.
  - Valores que não são dispositivo (`trt9`, `adct` sozinho) ficam fora.
  - A tabela é montada por um script idempotente, rodado no banco local e no da VPS.
- **Expressões com índice de texto no Postgres** (ementa + fundamentação). "dano moral coletivo" casa também "danos morais coletivos", sem diferenciar maiúsculas nem acentos.
  - Testado: o stemmer `portuguese` do Postgres não junta "moral" e "morais" ("moral" vira `moral`, "morais" vira `mor`), então ele sozinho não basta. A frase em plural achou 75 decisões, contra 137 da regex com as duas formas.
  - Uma saída é gerar as formas singular e plural da expressão e buscar qualquer uma.
  - Sem índice, a busca na fundamentação levou 34 s, então o índice é obrigatório.
- **Ordem dentro da faixa restrita:** é a mesma da busca de hoje (Qdrant nas duas coleções + BM25, fundidos por RRF, depois o reranker), aplicada só às decisões que passaram no filtro.
- **A faixa livre** é a busca de hoje sem filtro, menos as decisões que já estão na faixa restrita. Mostra até 20.
- **API:**
  - um endpoint de sugestões de dispositivos (texto digitado → até 10 opções com código, nome legível e total);
  - um endpoint de contagem (dispositivos + expressões → total combinado e total de cada item);
  - os dois exigem login e não contam no limite diário;
  - o `/query` passa a dizer a faixa de cada card e o total da faixa restrita.
- **`EstruturaArgumentativa`** ganha os campos de dispositivos (códigos) e de expressões. O BM25 da busca livre continua recebendo as normas como texto legível.

### Respostas à revisão do documento (decididas por mim)

- **Tamanho do conjunto filtrado:**
  - a faixa restrita passa a lista de ids para o Qdrant (`documento_id` em `MatchAny`) e pede o mesmo pool de hoje (`N_CANDIDATOS_COM_FILTRO`);
  - o BM25 é cruzado com a lista;
  - RRF e reranker funcionam como hoje;
  - se o conjunto tiver menos decisões que o pool, todas entram no ranking.

  Não há limite de ids nesta etapa. É preciso medir a latência com CLT art. 791 (11 mil ids): se passar da meta de +2 s, aí sim grava-se `dispositivos` no payload.
- **A faixa livre é carregada só quando o advogado abre a faixa.**
  - Com filtro, o `/query` roda só a busca restrita; a livre é uma segunda chamada, feita no clique de abrir. Assim a busca com filtro não paga dois reranqueamentos.
  - A segunda chamada não conta no limite diário, porque é a mesma pesquisa.
  - Sem filtro, nada muda: uma chamada só, com a busca livre.
  - As decisões que já estão na faixa restrita são tiradas da livre.
- **`/resposta` não muda:** a tela manda só os ids da faixa restrita quando há filtro, e não chama a resposta quando a faixa vem vazia. A chave do cache já inclui a estrutura, então os campos novos geram chave nova naturalmente.
- **Conversas antigas:**
  - os campos novos da `EstruturaArgumentativa` têm padrão vazio;
  - cards salvos sem faixa abrem como uma lista única, do jeito de hoje;
  - reabrir uma conversa mostra os resultados salvos, sem refazer a busca, como hoje.
- **Conversão das normas da IA é conservadora:** só vira chip quando a lei está explícita ("CLT art. 192", "art. 5º, V, da CF") e o código existe no acervo. "art. 186" sem lei não converte e não filtra; vai como texto para a busca livre.
- **Expressões:**
  - a frase precisa aparecer com as palavras em sequência (busca por frase, não palavras soltas no texto);
  - "de", "da", "por" e similares podem ficar no meio sem atrapalhar;
  - cada palavra aceita singular ou plural;
  - a expressão pode estar na ementa OU na fundamentação.
- **Índice de texto:**
  - é um índice GIN sobre expressão (ementa + fundamentação), sem coluna nova;
  - antes de criar na VPS, é preciso conferir o espaço em disco lá;
  - o script de deploy cria o índice.
- **Autocompletar de dispositivos:**
  - busca por todas as palavras digitadas, em qualquer ordem ("clt 15" e "15 clt" dão o mesmo resultado);
  - ordena pelo total de decisões;
  - códigos fora dos casos cobertos mostram o código como está.

## Fica com quem construir

- O formato exato da resposta do `/query`: lista com a faixa em cada card ou um objeto com as duas faixas, desde que as conversas antigas continuem abrindo.
- Como converter texto em código ("CLT art. 192" → `art_192_clt`) e código em nome legível. Precisa cobrir pelo menos artigo, parágrafo, inciso, alínea, caput, parágrafo único, súmula, OJ, leis numeradas (`lei_8078_90`), CF, ADCT, CLT, CPC, CC e CP. Os outros casos podem mostrar o código como está.
- Como restringir o BM25 às decisões que passaram no filtro: máscara por ids, como já é feito com o provimento, ou interseção depois da busca.
- O visual das faixas, do lápis e das contagens, seguindo o estilo atual das telas.

## Como saber que funcionou

- **Dano moral coletivo:** a busca com a expressão "dano moral coletivo" traz na faixa restrita só decisões que contêm "dano moral coletivo" ou "danos morais coletivos". A contagem bate com uma consulta direta no banco.
- **Gestante:** a busca com "ADCT art. 10, II, b" traz na faixa restrita só decisões com `b_ii_art_10_adct`; com "ADCT art. 10", também as que citam só `art_10_adct`.
- **Busca sem filtro:** dá o mesmo resultado de hoje.
- **Conversas:** uma conversa salva antes da mudança abre normalmente.
- **Deploy:** a tabela de dispositivos e o índice de texto são criados também no banco da VPS.
