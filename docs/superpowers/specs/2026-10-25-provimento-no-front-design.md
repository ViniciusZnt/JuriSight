# Provimento do Jev no front e correção pelo usuário — design

Data: 2026-10-25 · Branch: `feat/benchmark-etapa2`

## Por quê

O card de resultado mostra hoje um selo Favorável/Desfavorável que vem de uma heurística
sobre o provimento de 4 classes (`frontend/src/lib/outcome.ts`: NEGADO = favorável) e um
percentual que é só o score do RRF relativo ao melhor resultado. A tabela
`public.provimento_jev` já tem, para 69.340 acórdãos, o resultado do recurso, quem recorreu,
a quem a decisão favorece, as probabilidades de cada opção e a confiança. Nada disso chega
à tela.

O usuário também quer poder dizer "isto está errado" e mandar a correção. Cada correção
fica registrada para medir onde o Jev erra e, mais tarde, servir de dado de treino.

## Objetivo

1. Mostrar, no card de resultado e no detalhe da decisão, as três respostas do Jev com a
   confiança e as probabilidades de cada opção.
2. Deixar o usuário confirmar ("Está correto") ou corrigir as três respostas, com um
   comentário opcional. A correção é gravada no Postgres, ligada ao documento e ao usuário.
3. Exportar as correções em CSV para análise.

## Não-objetivos

- Usar a correção do usuário na busca, no filtro ou no `documentos.provimento`.
- Fine-tuning, painel de revisão das correções ou moderação.
- Mostrar ao usuário as correções de outras pessoas.
- Mudar o filtro de provimento da tela de Revisão.

## Decisões

**Onde o dado entra na API.** `ResultCard` e `DocumentoDetalhe` ganham o campo opcional
`classificacao_provimento` (null quando o documento não tem linha em `provimento_jev`). O
`/query` e o `/document/{id}` preenchem o campo com uma consulta por lote depois da busca.
Se essa consulta falhar, a busca volta sem o campo; ela nunca derruba a busca.

**Selo Favorável/Desfavorável.** Passa a vir de `favorece` quando o Jev tem confiança ≥ 0,5:
`reclamante` → Favorável, `reclamada` → Desfavorável, o resto → Neutro. Sem classificação,
fica a heurística atual. O app já parte do lado do trabalhador (a heurística atual faz o
mesmo); a regra só troca um palpite por um dado. Os filtros Favoráveis/Desfavoráveis e as
contagens do topo usam a mesma regra.

**Percentual do card.** Continua, com um rótulo que diz o que é: "relevância relativa ao
melhor resultado desta busca".

**Correção.** Uma linha por (documento, usuário) em `public.provimento_correcao`; enviar de
novo substitui a anterior (upsert). A linha guarda as três respostas do usuário, o
comentário e uma cópia das respostas do Jev, do modelo e do `perguntas_sha` no momento do
envio, para a comparação valer mesmo se o Jev reclassificar depois. "Está correto" envia as
próprias respostas do Jev. Documento sem classificação não oferece correção.

**Valores aceitos.** Os mesmos de `scraper/provimento_jev.py` (`RESULTADOS`, `RECORRENTES`,
`FAVORECE`). Comentário até 1.000 caracteres.

**Rótulos na tela.**

| Pergunta | Valor → rótulo |
|---|---|
| Resultado do recurso | provido → Provido · parcialmente_provido → Provido em parte · nao_provido → Não provido · nao_conhecido → Não conhecido · sem_recurso → Sem recurso |
| Quem recorreu | reclamante → Reclamante (trabalhador) · reclamada → Reclamada (empresa) · ambos → Ambas as partes · outro → Outra parte · indefinido → Não identificado |
| A quem favorece | reclamante → Trabalhador · reclamada → Empresa · ambos_em_parte → Ambos em parte · indefinido → Não identificado |

Confiança: ≥ 0,8 alta, ≥ 0,5 média, abaixo disso baixa.

## Restrições

- Padrões do projeto: identificadores e docstrings em português no backend, psycopg puro,
  fakes injetados nos testes, nunca imprimir nem editar o `.env`.
- Frontend: mesmos tokens de cor inline (hex com variante `dark:`), `lucide-react`, sem
  dependência nova.
- Toda rota nova exige sessão (`Depends(get_current_user)`).
