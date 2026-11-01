# Conferência do provimento com o Jev — 2026-10-20

Primeira medição de acerto do classificador `scraper/provimento_jev.py`
(modelo `jev-1.13.0`, `perguntas_sha` `73991da3…05cc`) em 50 acórdãos novos.

## Como foi feita

- `classificar --limite 50 --sim`: 50 acórdãos, 0 falhas, 34 s no total (inclui as contagens do acervo no início).
- Gabarito **cego**: leitores Claude (modelo Opus) leram o mesmo trecho que o Jev recebe
  (ementa até 1.500 caracteres e os últimos 4.000 do acórdão), sem ver as respostas do Jev
  nem da regex, e responderam às mesmas três perguntas com nível de certeza.
  Certeza: 27 alta, 15 média, 8 baixa.
- **Não é gabarito de especialista.** É uma referência para decidir o próximo passo, não a validação final.

## Resultado

| Medida (n=50) | Jev | Regex |
|---|---|---|
| Provimento nas 4 classes do enum | **96%** (IC95% 87–99%) | **62%** (IC95% 48–74%) |
| Resultado do recurso | 96% | — |
| Quem recorreu | 92% | — |
| A quem favorece | 76% | — |
| As três certas | 74% | — |

Só nos 27 casos com gabarito de certeza alta: provimento 100% (Jev) contra 74% (regex);
"a quem favorece" 93%.

"A quem favorece" por confiança mínima do Jev: sem mínimo 76% (50 casos); ≥ 0,8 88% (32);
≥ 0,9 96% (23).

## O que os erros mostram

- Quase todos os erros de "a quem favorece" atribuem a vitória **a quem recorreu** quando o
  recurso foi só parcialmente provido ou eram embargos de declaração. É leitura de papéis e
  negação (fraqueza declarada do Jev), e a maioria desses erros vem com confiança baixa.
- A régua tem dois buracos que confundem também o gabarito:
  1. embargos de declaração "acolhidos só para esclarecer" (sem efeito modificativo) não têm critério;
  2. "resultados diferentes → parcialmente provido" marca parcial quando um recurso é negado
     e o outro não conhecido, sem ninguém ter ganho.

## Próximos passos sugeridos

1. Ajustar o texto das perguntas para os dois buracos acima (muda o `perguntas_sha`;
   reclassificar os 90 já feitos custa centavos) e refazer esta conferência.
2. Rodar `classificar` no acervo inteiro (~110 M tokens; ~1 h pelo limite de 1.200 req/min
   divulgado, a confirmar com um lote cronometrado).
3. `aplicar --confirmar` só para o provimento, com `--confianca-min 0.8`.
4. Usar "a quem favorece" como sinal apenas com confiança ≥ 0,9, ou depois do ajuste da régua.

Os lotes, o gabarito e o script de pontuação ficaram fora do repositório (pasta temporária da sessão).
