# Prévia da busca na Revisão — design curto

Data: 17/11/2026. Mudança pequena.

## Por quê

Na Revisão de Contexto, o advogado vê seis campos que parecem a mesma coisa:

- Pedido, Fatos e Condutas;
- Normas, Dispositivos e Expressões;
- Tese.

Ele não consegue prever o que vira termo da busca, o que vai para a busca semântica e o que exclui decisões. O "Como esta busca foi feita" responde a isso, mas só aparece depois, na tela de resultados.

## O que muda

Um quadro **"O que esta busca vai usar"** na Revisão, logo acima do botão "Buscar jurisprudências", atualizado enquanto o advogado edita. Ele tem três linhas:

- **Pelos termos:** os termos exatos que vão ao BM25, na ordem de `query_builder.termos_bm25`.
- **Pelo sentido:** a frase que vira o embedding (`build_frase_tese`).
- **Exige:** os rótulos dos dispositivos, as expressões, os tribunais (`rotuloTribunal`) e a fase (`ROTULO_FASE`). Sem nenhum filtro: "Nada é exigido: todo o acervo entra".

Estados especiais:

- **Estrutura sem tese nem pedido** (o servidor responde 422): o quadro mostra "Preencha a tese central ou o pedido principal para buscar".
- **Erro de rede:** o quadro some. É só uma ajuda e nunca bloqueia a busca.

## Como

- `POST /query/explicacao` ganha o campo `dispositivos: list[str]`, com os rótulos legíveis (`rotulo(c)`) dos dispositivos exigidos. A rota continua sem IA e sem limite diário; o front já a usa nos resultados.
- O componente novo `PreviaBusca` recebe a estrutura e chama `explicarBusca` com espera de 400 ms depois da última edição. Uma resposta atrasada (de uma edição anterior) é ignorada.

## Abordagens consideradas

- **Prévia ao vivo** (escolhida): mostra o efeito exato de cada campo sem mudar o modelo de dados.
- **Lista única de termos com "exigir":** resolve a confusão entre "Normas" e "Dispositivos", mas mexe na tela e no modelo. Fica para depois, se a prévia não bastar.
- **Ementa gerada por IA para o terço do acervo sem ementa:** recusada pelo custo em tokens.

## Fora do escopo

- Mudar os campos da Revisão.
- A lacuna das decisões sem ementa na triagem e na resposta.
