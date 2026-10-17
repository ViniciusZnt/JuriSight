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
from avaliacao.db import ensure_schema as ensure_avaliacao_schema
from avaliacao.store import AvaliacaoStore
from conversations.db import ensure_schema as ensure_conversas_schema
from conversations.store import ConversaStore
from indexing.lexical.bm25_builder import BM25Builder
from indexing.vector_store.qdrant_store import QdrantStore
from processing.embeddings.poly_vector import PolyVectorEmbedder
from query.api.auth_routes import get_current_user
from query.api.auth_routes import router as auth_router
from query.api.avaliacao_routes import router as avaliacao_router
from query.api.conversa_routes import router as conversa_router
from query.enrichment import pdf_extractor
from query.enrichment.query_enrichment import QueryEnricher
from query.enrichment.schema import EstruturaArgumentativa
from query.search.doc_retriever import DocRetriever
from query.search.hybrid_search import HybridSearch
from query.search.pipeline import (  # noqa: F401 — nomes reexportados (usados em tests/test_api.py)
    N_CANDIDATOS_COM_FILTRO,
    N_CANDIDATOS_PARA_RERANK,
    N_RESULTS_FINAL,
    buscar,
    normalizar_scores as _normalizar_scores,
)
from query.search.reranker import Reranker
from query.search.result_formatter import DocumentoDetalhe, ResultCard
from scraper.schema import Provimento

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DATABASE_URL = os.getenv("DATABASE_URL")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

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
    ensure_avaliacao_schema(DATABASE_URL)
    app.state.avaliacao_store = AvaliacaoStore(DATABASE_URL)
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
app.include_router(avaliacao_router)


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


@app.post("/query", response_model=list[ResultCard], dependencies=[Depends(get_current_user)])
async def query(
    body: QueryRequest,
    hybrid: HybridSearch = Depends(get_hybrid),
    retriever: DocRetriever = Depends(get_doc_retriever),
    reranker: Reranker = Depends(get_reranker),
) -> list[ResultCard]:
    try:
        return await run_in_threadpool(
            buscar,
            body.estrutura,
            hybrid=hybrid,
            retriever=retriever,
            reranker=reranker,
            provimento=body.provimento,
            data_inicio=body.data_inicio,
            data_fim=body.data_fim,
            ordenar_por=body.ordenar_por,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
