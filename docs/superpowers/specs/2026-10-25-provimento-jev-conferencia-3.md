# Conferência 3 do provimento com o Jev — 2026-10-25

Terceira medição do classificador `scraper/provimento_jev.py` (modelo `jev-1.13.0`,
`perguntas_sha` `06284cca`), agora sobre o acervo inteiro já classificado e com 200 casos.

## Cobertura

- 69.349 acórdãos no banco; 69.340 com texto. Todos os 69.340 têm classificação com o sha
  atual; 0 pendentes. Os 9 restantes têm `acordao` vazio e não são enviados ao Jev.
- `documentos.provimento` ainda é o da regex (`aplicar --confirmar` não foi rodado).
- Confiança do `resultado` ≥ 0,8 em 62.747 (90,5%); média 0,947.

## Como foi feita

- Amostra aleatória simples de 200 entre os 69.340 (seed `20261025`).
- Mesmo método das conferências 1 e 2: leitores Claude (Opus) cegos, 10 lotes de 20, com o
  mesmo trecho que o Jev recebe (ementa até 1.500 caracteres e os últimos 4.000 do acórdão)
  e a régua copiada de `PERGUNTAS_PROVIMENTO`. Certeza do gabarito: 120 alta, 67 média,
  13 baixa.
- **Não é gabarito de especialista.**
- Arquivos (fora do git): `data/eval/conferencia_provimento_3/` (amostra, lotes, gabaritos,
  `comparar.py`, `resultado.txt`).

## Resultado

| Medida | Todos (n=200) | Gabarito certeza alta (n=120) | Jev conf. resultado ≥ 0,8 (n=180) |
|---|---|---|---|
| Provimento 4 classes — Jev | **96,0%** (IC95% 92–98) | 100% | **98,9%** (96–100) |
| Provimento 4 classes — regex | 64,5% (58–71) | 75,0% | 66,1% |
| Resultado do recurso (5 classes) | 96,0% | 100% | 98,9% |
| Quem recorreu | 91,0% (86–94) | 97,5% | 91,1% |
| A quem favorece | 74,0% (68–80) | 86,7% | 74,4% |
| As três certas | 68,0% | 85,0% | 70,0% |

- No balde em que regex e Jev mais divergem (regex `NEGADO`, Jev `parcialmente_provido`,
  ~22% do acervo; 46 na amostra) o Jev acerta 91% e a regex 7%.
- Quem recorreu com confiança ≥ 0,8: 96,7% (n=150); ≥ 0,9: 98,4% (n=127).
- A quem favorece com confiança ≥ 0,8: 90,8% (n=119); ≥ 0,9: 96,4% (n=84).

### Os 8 erros de provimento

Três são erros claros do Jev: embargos não acolhidos lidos como provimento parcial (C141,
conf. 0,24), ação rescisória lida como recurso (C162, 0,47) e embargos que afastaram a
deserção e depois negaram o mérito (C080, 1,00). Os outros cinco são fronteira entre
`provido` e `parcialmente_provido` (um recurso provido e o outro prejudicado; preliminar
acolhida e outra rejeitada; embargos com efeito modificativo) ou trechos sem dispositivo,
com gabarito de certeza média ou baixa. Seis dos oito têm confiança < 0,8 e o `aplicar` os
deixaria de fora.

### A quem favorece: 52 divergências

- **41 são de definição, não de leitura.** Recurso provido em parte (31) ou recursos das
  duas partes negados (10): o gabarito seguiu a régua ao pé da letra (`ambos_em_parte`) e o
  Jev escolheu o lado do recorrente que ganhou algo. A conferência 2 teve o desvio inverso
  em 2 casos. A régua precisa decidir o que `favorece` significa no provimento parcial.
- **10 são lado invertido** (5% da amostra), quase todos com confiança baixa (8 de 10 abaixo
  de 0,65): embargos de declaração da reclamada rejeitados, recurso deserto da reclamada,
  agravo de petição do exequente, ação rescisória da empresa.
- 1 envolve `indefinido`.

## Leitura

O provimento do Jev está pronto para substituir a regex: 96% contra 64,5% na amostra
inteira e 98,9% no conjunto que o `aplicar --confirmar` (corte 0,8) escreveria. Hoje,
com a regex, cerca de um terço dos acórdãos tem o provimento errado no filtro.
`favorece` ainda não serve como sinal sem antes fixar a regra do provimento parcial; com
confiança ≥ 0,9 ele chega a 96%, mas cobre só 42% da amostra.

`aplicar --confirmar` e depois `sincronizar` continuam sendo decisão do Vinicius.
