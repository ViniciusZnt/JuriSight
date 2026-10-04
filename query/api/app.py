"""
API Controller (RFC Tabela 6/Figura 10) — a aplicação FastAPI.

Orquestra o pipeline completo: PDF Extractor -> Query Enrichment -> Query Builder
-> Hybrid Search (RRF) -> Doc Retriever -> Hierarchical Ranker -> Result Formatter.

Endpoints (Tabela 6 / Tabela 13) — todos exigem sessão (cookie httpOnly, ver
query/api/auth_routes.py::get_current_user), exceto /health:
  - POST /enrich          — extrai a EstruturaArgumentativa do PDF e/ou da intenção.
  - POST /query           — busca híbrida sobre a EstruturaArgumentativa revisada.
  - GET  /document/{id}   — detalhe completo de um documento.
  - GET  /health          — liveness (público).

Autenticação (/auth/*: registro, login, logout, me) é montada via auth_router,
definida em query/api/auth_routes.py.

Os singletons com estado (conexões/índices) são construídos uma vez no lifespan e
lidos via Depends(...) a partir de request.app.state — em teste, cada Depends é
substituído via app.dependency_overrides, sem precisar de Postgres/Qdrant/Ollama
reais.

LGPD (RFC §6.1): nada do que o usuário envia (PDF, EstruturaArgumentativa) é
persistido — só leitura via DocRetriever sobre os documentos já coletados do TST.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from starlette.concurrency import run_in_threadpool

from auth.db import ensure_schema
from auth.store import UsuarioStore
from conversations.db import ensure_schema as ensure_conversas_schema
from conversations.store import ConversaStore
from indexing.lexical.bm25_builder import BM25Builder
from indexing.vector_store.qdrant_store import QdrantStore
from processing.embeddings.poly_vector import PolyVectorEmbedder
from query.api.auth_routes import get_current_user
from query.api.auth_routes import router as auth_router
from query.api.conversa_routes import router as conversa_router
from query.enrichment import pdf_extractor, query_builder
from query.enrichment.query_enrichment import QueryEnricher
from query.enrichment.schema import EstruturaArgumentativa
from query.search import categorical_sort
from query.search.doc_retriever import DocRetriever
from query.search.hybrid_search import HybridSearch
from query.search.reranker import Reranker
from query.search.result_formatter import DocumentoDetalhe, ResultCard, format_results
from scraper.schema import Provimento

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DATABASE_URL = os.getenv("DATABASE_URL")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# Top-N final devolvido por /query (RFC: RRF Fusion "retorna os top-20").
N_RESULTS_FINAL = 20
# Pool fundido pelo RRF antes do re-ranking (query/search/reranker.py) — maior
# que N_RESULTS_FINAL de propósito: a prática de 2026 é "funde um pool maior
# via RRF, depois um cross-encoder reordena esse pool", não só reordenar os
# mesmos 20 que já seriam devolvidos. 50 (o número usual na literatura) media
# ~14s nesta infra — o hybrid_search pede 5x isso por canal (ver
# CANDIDATOS_POR_CANAL em hybrid_search.py), então o pool maior também pesa na
# BUSCA, não só no re-ranking. 30 é o equilíbrio medido: ~50% de folga sobre
# os 20 finais, latência total ficando ~2x o baseline sem re-ranking.
N_CANDIDATOS_PARA_RERANK = 30
# Pool de candidatos maior quando algum filtro (provimento/período) está ativo —
# o filtro é aplicado em Python DEPOIS da busca (ver _aplicar_filtros), então um
# pool maior evita perder recall. Já cobre a folga do re-ranking acima.
N_CANDIDATOS_COM_FILTRO = 80


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Constrói os singletons com estado uma única vez, na subida da aplicação."""
    client = QdrantClient(url=QDRANT_URL, timeout=210)  # > _SEARCH_TIMEOUT_S (qdrant_store.py)
    store = QdrantStore(client)
    bm25 = BM25Builder.load()
    embedder = PolyVectorEmbedder()
    app.state.hybrid = HybridSearch(embedder, store, bm25)
    app.state.doc_retriever = DocRetriever(DATABASE_URL)
    app.state.enricher = QueryEnricher()
    app.state.reranker = Reranker()  # ~150MB, carregado uma vez (ver query/search/reranker.py)
    ensure_schema(DATABASE_URL)  # idempotente — cria auth.usuarios se ainda não existir
    app.state.usuario_store = UsuarioStore(DATABASE_URL)
    ensure_conversas_schema(DATABASE_URL)  # depende de auth.usuarios (FK) — roda depois
    app.state.conversa_store = ConversaStore(DATABASE_URL)
    yield


app = FastAPI(title="JuriSight API", lifespan=lifespan)

# Falha alto na subida, não em produção sob ataque: /auth/* autentica via cookie
# httpOnly (query/api/auth_routes.py), e a única coisa que impede qualquer site
# de fazer fetch(..., {credentials:"include"}) contra ele é allow_credentials=True
# exigir uma allowlist explícita — o CORSMiddleware do Starlette aceita "*" +
# credentials=True SEM erro, e nesse caso ecoa de volta qualquer Origin recebida
# (autorizando todo mundo). Um "CORS_ORIGINS=*" digitado sob pressão de deploy
# nunca deve conseguir chegar rodando.
if "*" in CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS não pode incluir '*' com allow_credentials=True — isso "
        "autorizaria qualquer origem a enviar requisições autenticadas via "
        "cookie (/auth/*). Configure uma allowlist explícita de origens."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
app.include_router(conversa_router)


def get_hybrid(request: Request) -> HybridSearch:
    return request.app.state.hybrid


def get_doc_retriever(request: Request) -> DocRetriever:
    return request.app.state.doc_retriever


def get_enricher(request: Request) -> QueryEnricher:
    return request.app.state.enricher


def get_reranker(request: Request) -> Reranker:
    return request.app.state.reranker


# --------------------------------------------------------------------------- #
# GET /health                                                                  #
# --------------------------------------------------------------------------- #

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# POST /enrich                                                                 #
# --------------------------------------------------------------------------- #

class EnrichResponse(BaseModel):
    estrutura: EstruturaArgumentativa
    # None = nenhum PDF enviado (FA01) / True = extraído com sucesso / False = FA02.
    pdf_extraido: bool | None
    aviso: str | None = None


@app.post("/enrich", response_model=EnrichResponse, dependencies=[Depends(get_current_user)])
async def enrich(
    pdf: UploadFile | None = File(None),
    intencao: str | None = Form(None),
    enricher: QueryEnricher = Depends(get_enricher),
) -> EnrichResponse:
    texto_pdf: str | None = None
    pdf_extraido: bool | None = None
    aviso: str | None = None

    if pdf is not None and pdf.filename:
        pdf_bytes = await pdf.read()
        try:
            texto_pdf = await run_in_threadpool(pdf_extractor.extract_text, pdf_bytes)
            texto_pdf = await run_in_threadpool(
                pdf_extractor.resumir_hierarquico,
                texto_pdf,
                resumir_bloco=enricher.resumir_bloco,
                condensar=enricher.condensar,
            )
            pdf_extraido = True
        except pdf_extractor.PDFSemTextoError:
            # FA02: notifica e prossegue como FA01 (só com a intenção, se houver).
            pdf_extraido = False
            aviso = (
                "Não foi possível extrair texto do PDF (possível documento escaneado). "
                "Prosseguindo com a intenção argumentativa informada."
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail="PDF inválido ou corrompido.") from exc

    try:
        estrutura = await run_in_threadpool(enricher.extract_estrutura, texto_pdf, intencao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return EnrichResponse(estrutura=estrutura, pdf_extraido=pdf_extraido, aviso=aviso)


# --------------------------------------------------------------------------- #
# POST /query                                                                  #
# --------------------------------------------------------------------------- #

class QueryRequest(BaseModel):
    estrutura: EstruturaArgumentativa
    provimento: Provimento | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    ordenar_por: Literal["relevancia", "data"] = "relevancia"


def _aplicar_filtros(
    triplos: list[tuple[str, object, float]],
    provimento: Provimento | None,
    data_inicio: date | None,
    data_fim: date | None,
) -> list[tuple[str, object, float]]:
    """Filtra os triplos (documento_id, doc, score) por provimento/período.

    Feito em Python pós-recuperação (não via `where` do Qdrant): hybrid_search.py
    já documenta que o BM25 não filtra por metadados e que um filtro rígido deve
    ser aplicado depois, sobre o DocumentoJuridico recuperado.
    """
    def ok(doc) -> bool:
        if provimento is not None and doc.provimento != provimento:
            return False
        if data_inicio is not None and (doc.data_julgamento is None or doc.data_julgamento < data_inicio):
            return False
        if data_fim is not None and (doc.data_julgamento is None or doc.data_julgamento > data_fim):
            return False
        return True

    return [t for t in triplos if ok(t[1])]


def _normalizar_scores(scores: list[float]) -> list[float]:
    """Min-max normaliza os scores do re-ranking pro intervalo [0, 1].

    Por quê: o cross-encoder (query/search/reranker.py) devolve scores muito
    comprimidos pra esse domínio (ex.: 0.97–0.999 — ver o módulo) — ótimo pra
    REORDENAR (é só a ordem relativa que importa), péssimo pro "% de
    relevância" exibido no frontend, que já divide pelo score máximo do lote
    (relevancePercent): sem normalizar, todo resultado apareceria como
    "~99% relevante". Esticar pro intervalo [0, 1] aqui resolve os dois usos
    com a MESMA métrica, sem precisar de um campo novo no ResultCard.

    Input:  scores — um por candidato, em qualquer ordem.
    Returns: mesma lista, normalizada; todos 1.0 se não houver variação
    (evita divisão por zero quando só 1 candidato, ou scores empatados).
    """
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


@app.post("/query", response_model=list[ResultCard], dependencies=[Depends(get_current_user)])
async def query(
    body: QueryRequest,
    hybrid: HybridSearch = Depends(get_hybrid),
    retriever: DocRetriever = Depends(get_doc_retriever),
    reranker: Reranker = Depends(get_reranker),
) -> list[ResultCard]:
    try:
        bm25_query = query_builder.build_bm25_query(body.estrutura)
        frase_tese = query_builder.build_frase_tese(body.estrutura)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    tem_filtro = body.provimento is not None or body.data_inicio is not None or body.data_fim is not None
    n_candidatos = N_CANDIDATOS_COM_FILTRO if tem_filtro else N_CANDIDATOS_PARA_RERANK

    rankings = await run_in_threadpool(hybrid.search, frase_tese, n_candidatos, bm25_query=bm25_query)
    docs = await run_in_threadpool(retriever.fetch, [doc_id for doc_id, _ in rankings])

    triplos = [(doc_id, docs[doc_id], score) for doc_id, score in rankings if doc_id in docs]
    if tem_filtro:
        triplos = _aplicar_filtros(triplos, body.provimento, body.data_inicio, body.data_fim)

    # Re-ranking: o RRF funde bem os RANKS de cada canal, mas não lê o
    # conteúdo — um cross-encoder pontua tese+ementa juntas e reordena por
    # relevância de verdade (ver query/search/reranker.py). Ordena pelo score
    # BRUTO do cross-encoder (reordenar por score bruto ou normalizado dá a
    # MESMA ordem — min-max é uma transformação monótona — então normalizar
    # antes não muda quem entra no corte, só a escala).
    if triplos:
        scores_rerank = await run_in_threadpool(
            reranker.rerank_scores, frase_tese, [doc.ementa for _, doc, _ in triplos]
        )
        triplos = [
            (doc_id, doc, score_bruto)
            for (doc_id, doc, _), score_bruto in zip(triplos, scores_rerank)
        ]
        triplos.sort(key=lambda t: t[2], reverse=True)

    triplos = triplos[:N_RESULTS_FINAL]

    # Normaliza DEPOIS do corte — só sobre os 20 exibidos, não o pool de 30.
    # Por quê: o cross-encoder devolve scores comprimidos nesse domínio (ex.:
    # 0.997-0.999); normalizar ANTES do corte usava os candidatos descartados
    # (os piores do pool) para ancorar o "0%", deixando os top-20 — que são os
    # melhores, logo os mais parecidos entre si — todos espremidos perto de
    # 100% (o bug visto em produção: toda carta mostrando "100% relevante").
    # Normalizar só os 20 exibidos espalha o score pelo intervalo completo
    # 0-100% de novo, sem mudar a ordem (a mesma transformação monótona).
    if triplos:
        scores_normalizados = _normalizar_scores([t[2] for t in triplos])
        triplos = [
            (doc_id, doc, score_norm)
            for (doc_id, doc, _), score_norm in zip(triplos, scores_normalizados)
        ]

    ordenados = categorical_sort.ordenar(triplos, body.ordenar_por)
    return format_results(ordenados)


# --------------------------------------------------------------------------- #
# GET /document/{id}                                                           #
# --------------------------------------------------------------------------- #

@app.get("/document/{documento_id}", response_model=DocumentoDetalhe, dependencies=[Depends(get_current_user)])
async def get_document(
    documento_id: str,
    retriever: DocRetriever = Depends(get_doc_retriever),
) -> DocumentoDetalhe:
    docs = await run_in_threadpool(retriever.fetch, [documento_id])
    doc = docs.get(documento_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return DocumentoDetalhe(id=documento_id, **doc.model_dump())
