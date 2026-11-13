# Remover Setor, Função e "A empresa sabia?" — design curto

Data: 13/11/2026.

## Por quê

Os campos `setor`, `cargo` e `empresa_ciente` são extraídos pela IA e aparecem na Revisão
de Contexto, mas não entram na busca (nem semântica, nem BM25, nem filtro). Na resposta da
IA só apareciam como parte do JSON da tese enviado ao modelo (`gerar_resposta`), sem papel
próprio — correção feita na revisão final; a primeira versão deste texto dizia que não
chegavam à resposta. Confundem o advogado e vão contra o guia de uso que está sendo escrito ("cada campo
faz algo"). Decisão do Vinicius: **tirar de vez**.

## Abordagens

- **A) Tirar de vez (escolhida pelo Vinicius)** — saem da tela, da extração e do esquema.
  Revisão mais enxuta, llama gera menos texto. Custo: divergência registrada em relação ao
  RF02 do RFC assinado.
- **B) Fazer funcionar como o RFC** — setor/cargo de volta ao BM25 e ciência da empresa na
  resposta. Descartada: reintroduz ruído (foi tirado do BM25 por baixo valor
  discriminativo) e mexe no prompt da resposta perto da entrega.

## O que muda

- `EstruturaArgumentativa` perde `setor`, `cargo`, `empresa_ciente`. Conversas antigas
  continuam abrindo (pydantic ignora chaves extras; o front completa os campos que faltam).
- Prompt de extração: sai a descrição dos três campos e eles saem do exemplo few-shot.
- Front: os três somem do tipo, dos valores padrão e da Revisão de Contexto.
- Testes que citam os campos são ajustados.
- README e docstrings citam a decisão: "removidos — não ajudam a achar jurisprudência; a
  ciência da empresa é questão de mérito, que o advogado avalia na decisão". Para o TCC:
  "não entravam na busca; na resposta só apareciam como parte do JSON da tese" (mesma linha
  vai para o documento final do TCC, pelo Vinicius).

## Efeitos aceitos

- Respostas em cache cuja estrutura tinha esses campos preenchidos são geradas de novo uma
  vez (a chave do cache muda).
- O layout da Revisão: o espaço dos três campos fica para os que restam (cabe ao builder,
  seguindo a identidade atual).

## Fora

- O guia de uso (próximo trabalho, descreve a tela já sem os campos).
- Mudar o RFC assinado (o Vinicius registra a decisão no documento final).
