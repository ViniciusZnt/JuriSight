"""
Reranker — reordena os candidatos da busca híbrida por relevância real, via
cross-encoder, depois do RRF.

Por quê: RRF funde bem os RANKS de canais diferentes (Qdrant completo, Qdrant
ementa, BM25), mas não lê o CONTEÚDO — só a posição relativa em cada lista. Um
cross-encoder recebe a tese e a ementa JUNTAS (não embedadas separadamente,
como no canal vetorial) e pontua a relevância de verdade, resgatando casos que
o RRF deixou mal posicionados. Prática de 2026: busca híbrida funde um pool
maior de candidatos (~50) via RRF, depois um cross-encoder reordena esse pool
antes do corte final — não o corpus inteiro, só os poucos candidatos que já
sobreviveram à primeira fase.

Via FlashRank (ONNX puro — onnxruntime + tokenizers, sem PyTorch/Transformers).
Modelo `ms-marco-MultiBERT-L-12` (~150MB), multilíngue, cobre português. Essa
escolha é deliberada: a máquina já é limitada em RAM (ver README
§Escalabilidade — o BM25 sozinho chegou a consumir ~7GB antes da migração para
bm25s nesta mesma sessão). Um cross-encoder via sentence-transformers traria
PyTorch como dependência — centenas de MB a mais só de instalação, e GBs de
RAM com o modelo carregado — o oposto do que a troca do BM25 acabou de
resolver. FlashRank entrega o mesmo mecanismo (cross-encoder) por uma fração
do custo.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from flashrank import Ranker, RerankRequest

# Multilíngue (cobre português) — os modelos só-inglês do FlashRank (ex.:
# ms-marco-TinyBERT-L-2-v2, o default) não pontuariam ementa em português
# de forma confiável.
MODEL_NAME = "ms-marco-MultiBERT-L-12"

# Medido nesta infra: pedir ao FlashRank pra pontuar 50 passagens NUM SÓ
# RerankRequest leva ~49s (algum custo super-linear no batching interno da
# lib — provável padding de todo o lote pro tamanho da maior passagem). Pedir
# as mesmas 50, uma por chamada, leva ~8s; paralelizando em threads (o
# onnxruntime libera o GIL durante a inferência), ~5s com 8 workers — mais que
# isso não ajuda (16 workers não ficou mais rápido que 8 nesta CPU).
_MAX_WORKERS = 8

# Teto de caracteres por passagem antes de mandar pro cross-encoder. Ementas
# são majoritariamente curtas (~840 chars em média nesta base), mas existem
# outliers acima de 60 mil — a atenção do transformer escala ~O(n²) com o
# tamanho da sequência, então UMA passagem gigante numa chamada paralela
# segura o executor.map() inteiro esperando ela terminar (medido: uma query
# caiu de ~8s pra ~54s por causa de um único outlier no lote). O resumo/tese
# de um acórdão cabe de sobra nos primeiros ~1200 caracteres — truncar aqui
# não perde o sinal que importa pro re-ranking.
_MAX_PASSAGE_CHARS = 1200


class Reranker:
    """Wrapper fino sobre o FlashRank — isola o resto do código da lib
    específica usada (mesmo espírito de QdrantStore sobre o QdrantClient)."""

    def __init__(self, cache_dir: str = "./data/index/reranker_cache", ranker: Ranker | None = None) -> None:
        """Carrega o modelo (baixa na primeira vez, cacheia localmente depois).

        Input:  cache_dir — onde o FlashRank guarda os pesos baixados;
                ranker — um Ranker já pronto (injetável em teste, mesmo padrão
                de QueryEnricher(client=...) — evita baixar/carregar o modelo
                real a cada teste).
        Returns: None.
        """
        self._ranker = ranker or Ranker(model_name=MODEL_NAME, cache_dir=cache_dir)

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        """Pontua cada passagem contra a query via cross-encoder.

        Uma chamada ao FlashRank POR PASSAGEM (não um RerankRequest só com
        todas) — ver o comentário de _MAX_WORKERS acima para o porquê: é
        ~6x mais rápido nesta infra, de um jeito nada óbvio. As chamadas
        rodam em paralelo (ThreadPoolExecutor) porque são independentes entre
        si e a inferência do onnxruntime libera o GIL.

        Input:  query — texto da consulta (a frase-tese, mesma usada no canal
                vetorial); passagens — uma por candidato (a ementa), MESMA
                ordem dos candidatos de quem chama.
        Returns: um score por passagem, NA MESMA ORDEM de entrada (não
        reordenado aqui — reordenar é responsabilidade de quem chama, que
        também sabe o doc_id/DocumentoJuridico de cada posição). Lista vazia
        se `passagens` for vazia.
        """
        if not passagens:
            return []

        def pontuar_uma(passagem: str) -> float:
            texto = passagem[:_MAX_PASSAGE_CHARS]
            resultado = self._ranker.rerank(RerankRequest(query=query, passages=[{"id": 0, "text": texto}]))
            return float(resultado[0]["score"])

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            return list(executor.map(pontuar_uma, passagens))
