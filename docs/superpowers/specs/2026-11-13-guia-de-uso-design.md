# Guia de uso + cores das buscas — design

Data: 13/11/2026. Prazo do TCC: 20/11/2026.

## Por quê

Quem abre o JuriSight pela primeira vez não sabe o que cada campo da Revisão de Contexto faz,
nem que a busca combina três mecanismos (filtro restrito, busca semântica, busca por termos),
nem que o acervo é limitado (~69 mil acórdãos, quase todos de 2025). Resultado: buscas mal
ajustadas. Pedido do Vinicius: um guia **didático e informativo**, visual, para qualquer
pessoa que nunca usou, que deixe evidente o que cada parte da Revisão faz e os limites do MVP.

## Abordagens

- **A) Página própria com a Revisão redesenhada em HTML (escolhida)** — rota `/guia`, conteúdo
  estático, independe da API, funciona no celular e no modo escuro. Custo: atualizar à mão
  se a Revisão mudar.
- B) Reusar os componentes reais da Revisão em modo demonstração — descartada: dependem da API
  (contagens, sugestões) e prendem o guia aos detalhes internos.
- C) Prints anotados — descartada: ruins no celular/escuro e desatualizam.

## O que o Vinicius decidiu

- Público: qualquer pessoa que nunca usou; objetivo: buscar com mais eficiência.
- Acesso: **uma opção na tela inicial** (não na Revisão).
- Formato: **sequência vertical**, cada etapa com informações importantes, ícones e acabamento
  detalhado — o mockup aprovado é `.superpowers/brainstorm/39874-1794590503/content/guia-vertical-v5.html`
  (estrutura e conteúdo), com a **paleta A**.
- **Paleta A**, cada busca numa família de cor própria:
  - Filtro restrito = marinho `#1A3A5C` (a cor do JuriSight);
  - Busca semântica = violeta `#6D4FC2`;
  - Busca por termos = verde-água `#0E8A80`.
  "Faça/Evite" fica neutro (não disputa com as três).

## Conteúdo (do mockup v5, em ordem)

1. Topo: selo "Guia de uso", título "Como tirar o melhor do JuriSight", subtítulo, índice
   rápido (1 Conte o caso → 2–3 Revise os campos → 4 Filtre se precisar → 5–6 Leia os resultados).
2. Faixa do acervo: **69.349 acórdãos trabalhistas**; selos: 96% julgados em 2025;
   abr/2024 → mai/2026; 25 tribunais; sem súmulas, OJs ou sentenças.
3. Trilha vertical numerada com nós de ícone:
   1. Conte o caso — PDF ou texto; nota "Seu documento fica aqui" (o PDF é lido pela IA do
      JuriSight; para fora vão só os campos revisados e ementas públicas).
   2. A IA monta a Revisão de Contexto — pode errar ou deixar vazio.
   3. Revise os campos (selo "O passo que mais muda o resultado") — cartões de Pedido
      principal, Fatos do caso, Condutas da empresa (termos) e Tese central (semântica + ordem
      final), cada um com exemplo do caso da gestante e Faça/Evite; destaque de que a Tese é o
      campo mais importante.
   4. Use o filtro restrito (Opcional · só se precisar) — Normas e dispositivos (sólido filtra,
      tracejado "só busca livre"), Expressões obrigatórias, Tribunal ("ou"), Fase; nota do
      contador "Com todos os filtros: N decisões".
   5. O que acontece quando você busca — funil 69.349 → filtro (ex.: TRT-4 + Conhecimento,
      3.796) → semântica + termos → reordenação → 20.
   6. Leia os resultados — réplica do painel "Como esta busca foi feita", Resposta da IA
      ("abra a decisão antes de citar"), Busca livre, nota do lápis para ajustar.
   7. Limites desta versão (MVP) — acervo pequeno; só acórdãos; a IA pode errar; não
      substitui a leitura.
4. Chamada final "Pronto para a primeira busca?" com botão para a tela inicial.

Os números são os do acervo atual (fixos no texto; 69.349 já é a constante `TOTAL_ACERVO`
usada no painel dos resultados — reusar).

## Decisões minhas (podem ser revistas)

- **A paleta vale para o app inteiro, não só para o guia**, senão o guia ensina uma cor e a
  tela mostra outra:
  - painel "Como esta busca foi feita" e a marquinha de canal nos cartões de resultado:
    semântica `#6E8FB5` → violeta, termos `#C47A2D` → verde-água (tons claros sobre o
    marinho do painel);
  - **Revisão de Contexto**: os chips de Fatos (âmbar) e Condutas (verde, perto demais do
    verde-água) passam para o verde-água dos termos, e cada rótulo de campo ganha uma
    etiqueta pequena com o mecanismo que alimenta ("Busca por termos" / "Busca semântica").
    É o que deixa visível, na própria tela, o que cada parte faz.
- O guia é uma página do app (`/guia`, dentro do layout com a barra lateral), feita com os
  componentes de sempre (Tailwind + lucide-react), com modo escuro como o resto do app.
- Na tela inicial: botão "Como usar" no canto direito do topo (hoje vazio) e uma linha discreta
  sob o subtítulo ("Primeira vez? Veja como tirar o melhor da busca →").
- Conteúdo estático; sem chamada à API.

## Fora

- Tour interativo dentro da Revisão; vídeo; versão em PDF.
- Mudar o comportamento da busca.

## Como saber que funcionou

- A tela inicial mostra "Como usar"; o clique abre `/guia`.
- O guia segue o mockup v5 com a paleta A, no claro e no escuro, sem rolagem horizontal no
  celular.
- Painel dos resultados, marquinhas dos cartões e Revisão usam violeta (semântica) e
  verde-água (termos); nenhum `#6E8FB5`/`#C47A2D` sobra.
- Suítes do front verdes; tsc e eslint limpos.
