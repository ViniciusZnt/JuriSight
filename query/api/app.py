"""
API Controller (RFC Tabela 6/Figura 10) — a aplicação FastAPI.

Orquestra o pipeline completo: PDF Extractor -> Query Enrichment -> Query Builder
-> Hybrid Search (RRF) -> Doc Retriever -> Hierarchical Ranker -> Result Formatter.

Endpoints (Tabela 6 / Tabela 13) — todos exigem sessão (cookie httpOnly, ver
query/api/auth_routes.py::get_current_user), exceto /health:
  - POST /enrich          — extrai a EstruturaArgumentativa do PDF e/ou da intenção.
  - POST /query           — busca híbrida sobre a EstruturaArgumentativa revisada.
  - POST /resposta        — resposta curta gerada (OpenAI) e ancorada nas ementas dos resultados.
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

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date

import openai
import psycopg

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from starlette.concurrency import run_in_threadpool

from auth.db import ensure_schema
from auth.store import Usuario, UsuarioStore
from conversations.db import ensure_schema as ensure_conversas_schema
from conversations.store import ConversaStore
from indexing.lexical.bm25_builder import BM25Builder
from indexing.vector_store.qdrant_store import QdrantStore
from processing.embeddings.poly_vector import PolyVectorEmbedder
from query.api.auth_routes import get_current_user
from query.api.auth_routes import router as auth_router
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
from query.search.resposta import Resposta, chave_da_resposta, gerar_resposta
from query.search.resposta_cache import RespostaCache, ensure_schema as ensure_resposta_cache_schema
from query.api.provimento_routes import get_provimento_store
from query.api.uso_diario import LimiteDiarioExcedido, UsoDiario, ensure_schema as ensure_uso_diario_schema
from query.api.provimento_routes import router as provimento_router
from query.search.result_formatter import ClassificacaoProvimentoView, DocumentoDetalhe, ResultCard
from scraper.provimento_jev_db import ProvimentoJevStore, ensure_schema_correcoes
from scraper.schema import Provimento

logger = logging.getLogger(__name__)

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
    ensure_schema_correcoes(DATABASE_URL)  # depende de auth.usuarios (FK)
    app.state.provimento_store = ProvimentoJevStore(DATABASE_URL)
    ensure_uso_diario_schema(DATABASE_URL)  # depende de auth.usuarios (FK)
    app.state.uso_diario = UsoDiario(DATABASE_URL)
    ensure_resposta_cache_schema(DATABASE_URL)
    app.state.resposta_cache = RespostaCache(DATABASE_URL)
    app.state.openai = openai.OpenAI(max_retries=0)  # timeout curto por chamada (query/search/resposta.py)
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
app.include_router(provimento_router)


def com_classificacao(cards: list, store: ProvimentoJevStore | None) -> list:
    """Anexa a classificação do Jev aos cards. Falha no banco não derruba a busca."""
    if store is None or not cards:
        return cards
    try:
        detalhes = store.detalhes([c.id for c in cards])
    except psycopg.Error as exc:
        logger.warning("Sem classificação do provimento nos resultados: %s", exc)
        return cards
    return [
        c.model_copy(update={"classificacao_provimento": ClassificacaoProvimentoView(**detalhes[c.id])})
        if c.id in detalhes else c
        for c in cards
    ]


def get_hybrid(request: Request) -> HybridSearch:
    return request.app.state.hybrid


def get_doc_retriever(request: Request) -> DocRetriever:
    return request.app.state.doc_retriever


def get_enricher(request: Request) -> QueryEnricher:
    return request.app.state.enricher


def get_reranker(request: Request) -> Reranker:
    return request.app.state.reranker


def get_openai(request: Request) -> openai.OpenAI:
    return request.app.state.openai


def get_resposta_cache(request: Request) -> RespostaCache | None:
    return getattr(request.app.state, "resposta_cache", None)


def get_uso_diario(request: Request) -> UsoDiario | None:
    return getattr(request.app.state, "uso_diario", None)


async def consumir_limite(uso: UsoDiario | None, usuario: Usuario, acao: str) -> None:
    """429 quando a conta ou o sistema passou do limite do dia (query/api/uso_diario.py)."""
    if uso is None:
        return
    try:
        await run_in_threadpool(uso.consumir, usuario.id, acao)
    except LimiteDiarioExcedido as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def limite_diario(acao: str):
    """Dependency: conta um uso de `acao` para o usuário logado antes de a rota rodar."""
    async def _dep(usuario: Usuario = Depends(get_current_user), uso: UsoDiario | None = Depends(get_uso_diario)) -> None:
        await consumir_limite(uso, usuario, acao)
    return _dep


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


@app.post("/enrich", response_model=EnrichResponse, dependencies=[Depends(limite_diario("enrich"))])
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


@app.post("/query", response_model=list[ResultCard], dependencies=[Depends(limite_diario("query"))])
async def query(
    body: QueryRequest,
    hybrid: HybridSearch = Depends(get_hybrid),
    retriever: DocRetriever = Depends(get_doc_retriever),
    reranker: Reranker = Depends(get_reranker),
    provimento_store: ProvimentoJevStore | None = Depends(get_provimento_store),
) -> list[ResultCard]:
    try:
        cards = await run_in_threadpool(
            buscar,
            body.estrutura,
            hybrid=hybrid,
            retriever=retriever,
            reranker=reranker,
            provimento=body.provimento,
            data_inicio=body.data_inicio,
            data_fim=body.data_fim,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await run_in_threadpool(com_classificacao, cards, provimento_store)


# --------------------------------------------------------------------------- #
# POST /resposta                                                               #
# --------------------------------------------------------------------------- #

class RespostaRequest(BaseModel):
    estrutura: EstruturaArgumentativa
    ids: list[uuid.UUID] = Field(max_length=20)  # na ordem dos cards: ids[0] é o #1


@app.post("/resposta", response_model=Resposta)
async def resposta(
    body: RespostaRequest,
    usuario: Usuario = Depends(get_current_user),
    uso: UsoDiario | None = Depends(get_uso_diario),
    retriever: DocRetriever = Depends(get_doc_retriever),
    client: openai.OpenAI = Depends(get_openai),
    cache: RespostaCache | None = Depends(get_resposta_cache),
) -> Resposta:
    """As ementas vêm do banco (nunca do cliente); o número de cada uma é a posição em `ids`.
    Resposta já gerada para a mesma tese, lista, modelo e prompt vem do cache, sem chamar a OpenAI;
    falha no cache não derruba a resposta. Só a geração conta no limite diário."""
    ids = [str(i) for i in body.ids]
    chave = chave_da_resposta(body.estrutura, ids)
    if cache is not None:
        try:
            salva = await run_in_threadpool(cache.ler, chave)
            if salva is not None:
                return Resposta.model_validate(salva)
        except psycopg.Error as exc:
            logger.warning("Cache da resposta indisponível: %s", exc)
    await consumir_limite(uso, usuario, "resposta")  # só conta quando vai gerar (cache não gasta)
    docs = await run_in_threadpool(retriever.fetch, ids)
    decisoes = {n: docs[i] for n, i in enumerate(ids, start=1) if i in docs}
    try:
        gerada = await run_in_threadpool(gerar_resposta, body.estrutura, decisoes, client)
    except openai.OpenAIError as exc:
        logger.warning("Resposta gerada indisponível: %s", exc)
        raise HTTPException(status_code=503, detail="A resposta gerada está indisponível agora. Os resultados continuam abaixo.") from exc
    if cache is not None and gerada.frases:
        try:
            await run_in_threadpool(cache.gravar, chave, gerada.model_dump(mode="json"))
        except psycopg.Error as exc:
            logger.warning("Resposta não foi guardada no cache: %s", exc)
    return gerada


# --------------------------------------------------------------------------- #
# GET /document/{id}                                                           #
# --------------------------------------------------------------------------- #

@app.get("/document/{documento_id}", response_model=DocumentoDetalhe, dependencies=[Depends(get_current_user)])
async def get_document(
    documento_id: str,
    retriever: DocRetriever = Depends(get_doc_retriever),
    provimento_store: ProvimentoJevStore | None = Depends(get_provimento_store),
) -> DocumentoDetalhe:
    docs = await run_in_threadpool(retriever.fetch, [documento_id])
    doc = docs.get(documento_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    detalhe = DocumentoDetalhe(id=documento_id, **doc.model_dump())
    return (await run_in_threadpool(com_classificacao, [detalhe], provimento_store))[0]
