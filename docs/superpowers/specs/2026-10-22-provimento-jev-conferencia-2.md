# Conferência 2 do provimento com o Jev — 2026-10-22

Segunda medição do classificador `scraper/provimento_jev.py` (modelo `jev-1.13.0`), depois
de ajustar as perguntas nos dois casos que a conferência 1
(`2026-10-20-provimento-jev-conferencia.md`) apontou. `perguntas_sha` novo:
`06284cca…6b3e`.

## O que mudou nas perguntas

- `resultado`: com mais de um recurso, `parcialmente_provido` só quando pelo menos um foi
  provido; se nenhum foi, `nao_provido`. Embargos de declaração acolhidos só para
  esclarecer, sem efeito modificativo, contam como `nao_provido`.
- `favorece`: dica de negação ("negar provimento ao recurso da reclamada favorece o
  reclamante" e o inverso; provimento parcial = cada parte ganhou em algum ponto).

## Como foi feita

- `classificar --limite 140 --sim`: os 90 já classificados (voltaram a ficar pendentes com
  o sha novo) mais 50 acórdãos nunca vistos. 0 falhas, 20 s no total.
- A conferência usa só os **50 nunca vistos**, com o mesmo método da conferência 1:
  leitores Claude (Opus) cegos, com o mesmo trecho que o Jev recebe (ementa até 1.500
  caracteres e os últimos 4.000 do acórdão) e a régua revisada. Certeza do gabarito:
  39 alta, 8 média, 3 baixa.
- **Não é gabarito de especialista.**

## Resultado

| Medida (n=50) | Conferência 1 | Conferência 2 |
|---|---|---|
| Provimento nas 4 classes — Jev | 96% | **100%** (IC95% 93–100%) |
| Provimento nas 4 classes — regex | 62% | 74% (IC95% 60–84%) |
| Resultado do recurso | 96% | 100% |
| Quem recorreu | 92% | 92% |
| A quem favorece | 76% | **90%** |
| As três certas | 74% | 88% |

"A quem favorece" por confiança mínima do Jev: ≥ 0,5 → 93% (44 casos); ≥ 0,8 → 97% (35).

Os 8 casos-alvo da revisão (embargos acolhidos só para esclarecer, embargos rejeitados,
recursos de ambas as partes negados) saíram todos certos.

Erros restantes em "a quem favorece" (5): dois casos de provimento parcial ao recurso do
reclamante em que o Jev respondeu `ambos_em_parte` e o gabarito `reclamante` (efeito da
dica nova; os dois são defensáveis), um de recursos das duas partes negados, um agravo de
petição com papéis trocados e um embargo do devedor com gabarito de certeza baixa.

## Decisão

Critério do design de 21/10 atendido (provimento ≥ 90% e nenhum erro nos dois casos).
Segue para o lote cronometrado e o `classificar` no acervo inteiro. `aplicar --confirmar`
continua sendo decisão do Vinicius. A validação do provimento foi feita por esta e pela primeira conferência cega.
