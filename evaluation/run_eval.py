"""
Runner de avaliação dos KPIs de recuperação (RFC §1.6, Tabela 3).

Roda a busca híbrida real sobre o índice + DB para cada query do golden.toml,
mede latência e calcula os KPIs de IR/operacionais, comparando com as metas.

Requer o ambiente de produção (OpenAI para o embedding, ChromaDB indexado,
PostgreSQL). NÃO cobre Faithfulness/Answer Relevance (RAGAS): o sistema é
retrieval-only, sem etapa de geração — essas ficam para quando ela existir.

Uso:
    uv run python evaluation/run_eval.py            # relatório dos KPIs
    uv run python evaluation/run_eval.py --show     # + candidatos p/ rotular
    uv run python evaluation/run_eval.py --n-results 10
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import chromadb
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from evaluation import metrics
from evaluation.dataset import GoldenQuery, carregar
from indexing.lexical.bm25_builder import BM25Builder
from indexing.vector_store.chroma_store import ChromaStore
from processing.embeddings.poly_vector import PolyVectorEmbedder
from query.search.doc_retriever import DocRetriever
from query.search.hybrid_search import HybridSearch
from scraper.schema import TipoDocumento

DATABASE_URL = os.getenv("DATABASE_URL")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR")

# Metas da Tabela 3 (RFC §1.6). Latência: meta dura <30s, meta desejada <15s.
TARGETS = {
    "precision@5":          0.70,
    "precision@10":         0.60,
    "provimento_favoravel": 0.90,
    "citacao_fonte_real":   1.00,
    "cobertura_tipos":      1.00,
    "latencia_max_s":       30.0,
}


def _construir_pipeline() -> tuple[HybridSearch, DocRetriever]:
    """Monta a busca híbrida e o doc retriever a partir do ambiente.

    Input:  nenhum (lê env).
    Returns: (HybridSearch, DocRetriever).
    """
    client = chromadb.PersistentClient(path=os.path.expanduser(CHROMA_PERSIST_DIR))
    chroma = ChromaStore(client)
    bm25 = BM25Builder.load()
    embedder = PolyVectorEmbedder()
    return HybridSearch(embedder, chroma, bm25), DocRetriever(DATABASE_URL)


def _tipos_presentes() -> set[str]:
    """Tipos de documento distintos presentes no PostgreSQL (KPI de cobertura).

    Input:  nenhum.
    Returns: set de tipo_documento (strings).
    """
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT tipo_documento FROM documentos")
        return {row[0] for row in cur.fetchall()}


def _ordenar_por_busca(
    docs: dict, retrieved_ids: list[str]
) -> list:
    """Reordena os DocumentoJuridico na ordem em que a busca os devolveu.

    Input:  docs — {id: DocumentoJuridico}; retrieved_ids — ordem da busca.
    Returns: lista de DocumentoJuridico na ordem da busca (ignora ids não achados).
    """
    return [docs[i] for i in retrieved_ids if i in docs]


def _avaliar_query(
    gq: GoldenQuery, search: HybridSearch, retriever: DocRetriever, n_results: int
) -> dict:
    """Roda uma query e coleta tudo que os KPIs precisam.

    Input:  gq — query golden; search; retriever; n_results — corte.
    Returns: dict com retrieved_ids, docs ordenados, provimentos e latência (s).
    """
    inicio = time.perf_counter()
    hits = search.search(gq.query, n_results=n_results, where=gq.filtro)
    retrieved_ids = [doc_id for doc_id, _ in hits]
    docs_map = retriever.fetch(retrieved_ids)
    latencia = time.perf_counter() - inicio

    docs = _ordenar_por_busca(docs_map, retrieved_ids)
    return {
        "retrieved_ids": retrieved_ids,
        "docs": docs,
        "latencia": latencia,
    }


def _mostrar_candidatos(gq: GoldenQuery, docs: list) -> None:
    """Imprime os top-K de uma query para facilitar a rotulagem manual.

    Input:  gq — query; docs — DocumentoJuridico na ordem da busca.
    Returns: None.
    """
    print(f"\n[{gq.id}] {gq.query}")
    if gq.filtro:
        print(f"      filtro: {gq.filtro}")
    for i, d in enumerate(docs, 1):
        ementa = (d.ementa or "").replace("\n", " ")[:90]
        print(f"  {i:>2}. {d.numero_processo or '(sem nº)':<28} "
              f"{d.tipo_documento.value:<10} {d.provimento.value:<14} {ementa}")


def _linha(nome: str, valor: float | None, meta: float, menor_melhor: bool = False) -> str:
    """Formata uma linha do relatório com PASS/FAIL vs meta.

    Input:  nome; valor (None = não avaliável); meta; menor_melhor — True p/ latência.
    Returns: string formatada.
    """
    if valor is None:
        return f"  {nome:<26} {'—':>8}   (meta {meta:>5})   SEM RÓTULOS"
    ok = valor <= meta if menor_melhor else valor >= meta
    status = "PASS" if ok else "FAIL"
    return f"  {nome:<26} {valor:>8.3f}   (meta {meta:>5})   {status}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia os KPIs de recuperação do JuriSight.")
    parser.add_argument("--n-results", type=int, default=10, help="Top-N por query (default 10).")
    parser.add_argument("--show", action="store_true", help="Imprime os candidatos de cada query p/ rotulagem.")
    args = parser.parse_args()

    queries = carregar()
    search, retriever = _construir_pipeline()

    casos_p5: list[tuple[list[str], set[str]]] = []
    casos_p10: list[tuple[list[str], set[str]]] = []
    provimentos_filtrados: list[str] = []
    citacoes: list[dict] = []
    latencias: list[float] = []
    sem_rotulo: list[str] = []

    for gq in queries:
        res = _avaliar_query(gq, search, retriever, args.n_results)
        latencias.append(res["latencia"])
        docs = res["docs"]

        if args.show:
            _mostrar_candidatos(gq, docs)

        # Citação (todos os docs retornados) e provimento (só queries com filtro favorável).
        for d in docs:
            citacoes.append({
                "numero_processo": d.numero_processo,
                "tipo_documento": d.tipo_documento.value,
                "link_original": d.link_original,
            })
        if gq.filtro and gq.filtro.get("provimento") == "APROVADO":
            provimentos_filtrados.extend(d.provimento.value for d in docs)

        # Precision@K só entra para queries já rotuladas.
        if gq.rotulada:
            relev = set(gq.relevantes)
            casos_p5.append((res["retrieved_ids"], relev))
            casos_p10.append((res["retrieved_ids"], relev))
        else:
            sem_rotulo.append(gq.id)

    # --- Métricas -----------------------------------------------------------
    p5 = metrics.mean_precision_at_k(casos_p5, 5) if casos_p5 else None
    p10 = metrics.mean_precision_at_k(casos_p10, 10) if casos_p10 else None
    prov = metrics.provimento_rate(provimentos_filtrados) if provimentos_filtrados else None
    cit = metrics.citation_completeness(citacoes)
    cobertura = metrics.type_coverage(_tipos_presentes(), {t.value for t in TipoDocumento})
    lat = metrics.latency_summary(latencias)

    # --- Relatório ----------------------------------------------------------
    print("\n" + "=" * 64)
    print("KPIs de recuperação — JuriSight (RFC §1.6, Tabela 3)")
    print("=" * 64)
    print(f"  Queries: {len(queries)} total, {len(casos_p5)} rotuladas, "
          f"{len(sem_rotulo)} sem rótulos")
    print("-" * 64)
    print(_linha("Precision@5", p5, TARGETS["precision@5"]))
    print(_linha("Precision@10", p10, TARGETS["precision@10"]))
    print(_linha("Filtro por provimento", prov, TARGETS["provimento_favoravel"]))
    print(_linha("Citação com fonte real", cit, TARGETS["citacao_fonte_real"]))
    print(_linha("Cobertura de tipos", cobertura, TARGETS["cobertura_tipos"]))
    print(_linha("Latência máx (s)", lat["max"], TARGETS["latencia_max_s"], menor_melhor=True))
    print(f"  {'Latência p50/p95 (s)':<26} {lat['p50']:>8.3f} / {lat['p95']:.3f}")
    print("=" * 64)

    if sem_rotulo:
        print(f"\nSem rótulos (não entram no P@K): {', '.join(sem_rotulo)}")
        print("Rode com --show, preencha `relevantes` no golden.toml e rode de novo.")
    print("Nota: Faithfulness/Answer Relevance (RAGAS) não avaliadas — "
          "sistema retrieval-only, sem etapa de geração.\n")


if __name__ == "__main__":
    main()
