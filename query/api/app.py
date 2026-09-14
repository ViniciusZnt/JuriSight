"""
API Controller (RFC Tabela 6/Figura 10) — a aplicação FastAPI.

Orquestra o pipeline completo: PDF Extractor -> Query Enrichment -> Query Builder
-> Hybrid Search (RRF) -> Doc Retriever -> Hierarchical Ranker -> Result Formatter.

Endpoints (Tabela 6 / Tabela 13):
  - POST /enrich          — extrai a EstruturaArgumentativa do PDF e/ou da intenção.
  - POST /query           — busca híbrida sobre a EstruturaArgumentativa revisada.
  - GET  /document/{id}   — detalhe completo de um documento.
  - GET  /health          — liveness.

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

from indexing.lexical.bm25_builder import BM25Builder
from indexing.vector_store.qdrant_store import QdrantStore
from processing.embeddings.poly_vector import PolyVectorEmbedder
from query.enrichment import pdf_extractor, query_builder
from query.enrichment.query_enrichment import QueryEnricher
from query.enrichment.schema import EstruturaArgumentativa
from query.search import categorical_sort
from query.search.doc_retriever import DocRetriever
from query.search.hybrid_search import HybridSearch
from query.search.result_formatter import DocumentoDetalhe, ResultCard, format_results
from scraper.schema import Provimento

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DATABASE_URL = os.getenv("DATABASE_URL")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# Top-N final devolvido por /query (RFC: RRF Fusion "retorna os top-20").
N_RESULTS_FINAL = 20
# Pool de candidatos maior quando algum filtro (provimento/período) está ativo —
# o filtro é aplicado em Python DEPOIS da busca (ver _aplicar_filtros), então um
# pool maior evita perder recall.
N_CANDIDATOS_COM_FILTRO = 80


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Constrói os singletons com estado uma única vez, na subida da aplicação."""
    client = QdrantClient(url=QDRANT_URL, timeout=180)
    store = QdrantStore(client)
    bm25 = BM25Builder.load()
    embedder = PolyVectorEmbedder()
    app.state.hybrid = HybridSearch(embedder, store, bm25)
    app.state.doc_retriever = DocRetriever(DATABASE_URL)
    app.state.enricher = QueryEnricher()
    yield


app = FastAPI(title="JuriSight API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


def get_hybrid(request: Request) -> HybridSearch:
    return request.app.state.hybrid


def get_doc_retriever(request: Request) -> DocRetriever:
    return request.app.state.doc_retriever


def get_enricher(request: Request) -> QueryEnricher:
    return request.app.state.enricher


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


@app.post("/enrich", response_model=EnrichResponse)
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


@app.post("/query", response_model=list[ResultCard])
async def query(
    body: QueryRequest,
    hybrid: HybridSearch = Depends(get_hybrid),
    retriever: DocRetriever = Depends(get_doc_retriever),
) -> list[ResultCard]:
    try:
        bm25_query = query_builder.build_bm25_query(body.estrutura)
        frase_tese = query_builder.build_frase_tese(body.estrutura)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    tem_filtro = body.provimento is not None or body.data_inicio is not None or body.data_fim is not None
    n_candidatos = N_CANDIDATOS_COM_FILTRO if tem_filtro else N_RESULTS_FINAL

    rankings = await run_in_threadpool(hybrid.search, frase_tese, n_candidatos, bm25_query=bm25_query)
    docs = await run_in_threadpool(retriever.fetch, [doc_id for doc_id, _ in rankings])

    triplos = [(doc_id, docs[doc_id], score) for doc_id, score in rankings if doc_id in docs]
    if tem_filtro:
        triplos = _aplicar_filtros(triplos, body.provimento, body.data_inicio, body.data_fim)
    triplos = triplos[:N_RESULTS_FINAL]

    ordenados = categorical_sort.ordenar(triplos, body.ordenar_por)
    return format_results(ordenados)


# --------------------------------------------------------------------------- #
# GET /document/{id}                                                           #
# --------------------------------------------------------------------------- #

@app.get("/document/{documento_id}", response_model=DocumentoDetalhe)
async def get_document(
    documento_id: str,
    retriever: DocRetriever = Depends(get_doc_retriever),
) -> DocumentoDetalhe:
    docs = await run_in_threadpool(retriever.fetch, [documento_id])
    doc = docs.get(documento_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return DocumentoDetalhe(id=documento_id, **doc.model_dump())
