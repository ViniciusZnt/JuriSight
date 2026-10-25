"""
Qdrant Vector Store — substitui indexing/vector_store/chroma_store.py (README §Escalabilidade).

Por quê: o HNSW do Chroma exige o índice inteiro em RAM. Com ~69k acórdãos (~400k
chunks) isso já é pesado demais numa máquina com RAM limitada — ver
docs/Backup_Indices.md e a medição real: só abrir a coleção via PersistentClient
levou minutos, puro I/O de disco carregando o grafo. O Qdrant permite vetores E
grafo HNSW em disco (mmap, `on_disk=True`), que é o requisito real aqui.

Mesmo modelo Poly-Vector do Chroma, duas coleções:
  - COLLECTION_COMPLETO -> um ponto por CHUNK  (id = uuid5 determinístico do chunk_id);
  - COLLECTION_EMENTA   -> um ponto por DOCUMENTO (id = documento_id, já é UUID).

Interface pública idêntica a ChromaStore (add_chunks/query/documento_ids_indexados/
reset) de propósito — é a "troca localizada" que o README já previa: só quem
constrói o client muda (indexing/run.py e query/api/app.py); HybridSearch e o
resto do pipeline não sabem qual vector store está por trás.
"""
from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient, models

from processing.chunking.sac_chunker import Chunk

logger = logging.getLogger(__name__)

COLLECTION_COMPLETO = "chunks_completo"
COLLECTION_EMENTA = "chunks_ementa"

# Timeout DO SERVIDOR pra uma operação de busca, em segundos — repassado por
# request via query_points(timeout=...), não é o mesmo timeout de conexão do
# client (esse já é configurado por quem injeta o QdrantClient). Sem isto, o
# Qdrant aplica um timeout interno próprio (~60s) e devolve 500 se a busca no
# disco (mmap, on_disk=True) demorar mais — o que acontece nesta infra sob
# concorrência de CPU com o Ollama.
_SEARCH_TIMEOUT_S = 180

# text-embedding-3-small (processing/embeddings/poly_vector.py) — os dois canais
# Poly-Vector usam o mesmo modelo, logo a mesma dimensão.
EMBED_DIM = 1536

# HNSW/quantização tunados para favorecer disco sobre RAM (o objetivo desta troca).
_HNSW_CONFIG = models.HnswConfigDiff(on_disk=True)

# Namespace fixo (UUID aleatório gerado uma única vez) para o uuid5 determinístico
# do chunk_id — NUNCA mude este valor: mudar quebra a idempotência do upsert (o
# mesmo chunk_id passaria a gerar um point id diferente, duplicando o ponto em vez
# de atualizá-lo). chunk_id tem o formato "documento_id:posicao", que não é um
# UUID nem um inteiro sem sinal válidos — os dois formatos de id que o Qdrant aceita.
_CHUNK_ID_NAMESPACE = uuid.UUID("7f3b6a1a-6e0a-4b8b-9b9e-2a6b6f1a9c3e")


def chunk_point_id(chunk_id: str) -> str:
    """Converte um chunk_id ('documento_id:posicao') num UUID determinístico.

    Input:  chunk_id.
    Returns: string UUID — sempre a mesma para o mesmo chunk_id (reindexar não duplica).
    """
    return str(uuid.uuid5(_CHUNK_ID_NAMESPACE, chunk_id))


def _to_payload(chunk: Chunk) -> dict:
    """Monta o payload por-CHUNK para COLLECTION_COMPLETO (mesmos campos do
    ChromaStore._to_metadata, + chunk_id para introspecção/debug)."""
    return {
        "chunk_id":             chunk.chunk_id,
        "documento_id":         chunk.documento_id,
        "tipo_documento":       chunk.tipo_documento,
        "provimento":           chunk.provimento,
        "data_julgamento":      chunk.data_julgamento or "",
        "numero_processo":      chunk.numero_processo,
        "hierarquia_categoria": chunk.hierarquia_categoria,
        "posicao":              chunk.posicao,
    }


def _to_payload_documento(chunk: Chunk) -> dict:
    """Payload por-DOCUMENTO para COLLECTION_EMENTA, sem a chave 'posicao'."""
    payload = _to_payload(chunk)
    payload.pop("posicao", None)
    return payload


def _build_filter(where: dict | None) -> models.Filter | None:
    """Traduz o filtro de igualdade simples do HybridSearch (ex.: {"provimento":
    "APROVADO"}) para um Filter do Qdrant. Só suporta igualdade — é tudo que o
    chamador (query/search/hybrid_search.py) usa hoje."""
    if not where:
        return None
    return models.Filter(
        must=[models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in where.items()]
    )


class QdrantStore:
    """Wrapper do Qdrant com as duas coleções Poly-Vector."""

    def __init__(self, client: QdrantClient) -> None:
        """Recebe o cliente Qdrant (injetado) e garante as duas coleções.

        Input:  client — QdrantClient já apontando para o servidor.
        Returns: None.
        """
        self._client = client
        self._garantir_colecao(COLLECTION_COMPLETO)
        self._garantir_colecao(COLLECTION_EMENTA)

    def _garantir_colecao(self, nome: str) -> None:
        """Cria a coleção (vetores + HNSW em disco) se ainda não existir.

        Input:  nome — nome da coleção.
        Returns: None. Idempotente: não mexe numa coleção já existente (reindexação
        delta não deve recriar/perder o que já está lá).
        """
        if self._client.collection_exists(nome):
            return
        self._client.create_collection(
            collection_name=nome,
            vectors_config=models.VectorParams(
                size=EMBED_DIM,
                distance=models.Distance.COSINE,
                on_disk=True,  # vetores em disco (mmap) — não força o corpus inteiro em RAM
            ),
            hnsw_config=_HNSW_CONFIG,
            on_disk_payload=True,
        )
        logger.info("Coleção Qdrant '%s' criada (vetores e HNSW em disco).", nome)

    def add_chunks(
        self,
        chunks: list[Chunk],
        emb_completo: list[list[float]],
        emb_ementa: list[list[float]],
    ) -> None:
        """Indexa (upsert) um lote nas duas coleções — mesma assinatura do ChromaStore.

        Input:  chunks, (emb_completo, emb_ementa) — vetores na mesma ordem dos chunks.
        Returns: None.
        """
        if not chunks:
            return
        if not (len(chunks) == len(emb_completo) == len(emb_ementa)):
            raise ValueError(
                f"Tamanhos divergentes: {len(chunks)} chunks, "
                f"{len(emb_completo)} emb_completo, {len(emb_ementa)} emb_ementa."
            )

        self._client.upsert(
            collection_name=COLLECTION_COMPLETO,
            points=[
                models.PointStruct(id=chunk_point_id(c.chunk_id), vector=emb, payload=_to_payload(c))
                for c, emb in zip(chunks, emb_completo)
            ],
        )

        # EMENTA: um ponto por documento — só o 1º chunk de cada documento_id.
        vistos: set[str] = set()
        points: list[models.PointStruct] = []
        for c, emb in zip(chunks, emb_ementa):
            if c.documento_id in vistos:
                continue
            vistos.add(c.documento_id)
            points.append(models.PointStruct(id=c.documento_id, vector=emb, payload=_to_payload_documento(c)))
        if points:
            self._client.upsert(collection_name=COLLECTION_EMENTA, points=points)

    def query(
        self,
        embedding: list[float],
        n_results: int = 20,
        where: dict | None = None,
        collection: str = COLLECTION_COMPLETO,
    ) -> list[dict]:
        """Busca vetorial numa coleção, com filtro opcional de metadados.

        Input:  embedding — vetor da query; n_results; where — filtro de igualdade
                (ex.: {"provimento": "APROVADO"}); collection — qual coleção usar.
        Returns: lista de {id, documento_id, distance, metadata}, mais próximos
                 primeiro — mesmo formato do ChromaStore.query() (nenhum chamador
                 lê "distance" hoje, mas o campo é mantido por paridade).
        """
        res = self._client.query_points(
            collection_name=collection,
            query=embedding,
            limit=n_results,
            query_filter=_build_filter(where),
            with_payload=True,
            timeout=_SEARCH_TIMEOUT_S,
        )
        resultados = []
        for point in res.points:
            payload = point.payload or {}
            resultados.append(
                {
                    "id": str(point.id),
                    "documento_id": payload.get("documento_id"),
                    "distance": 1 - point.score,  # score do Qdrant = similaridade (maior é melhor)
                    "metadata": payload,
                }
            )
        return resultados

    def documento_ids_indexados(self) -> set[str]:
        """Retorna os documento_id já presentes na coleção da ementa.
        Usado pela indexação delta para pular o embedding de quem já foi indexado.

        Input:  None.
        Returns: set de documento_id (vazio após reset ou base nova).
        """
        ids: set[str] = set()
        offset = None
        while True:
            pontos, offset = self._client.scroll(
                collection_name=COLLECTION_EMENTA,
                limit=1000,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            ids.update(str(p.id) for p in pontos)
            if offset is None:
                break
        return ids

    def reset(self) -> None:
        """Apaga e recria as duas coleções (re-indexação do zero).

        Input:  None.
        Returns: None.
        """
        for nome in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
            if self._client.collection_exists(nome):
                self._client.delete_collection(nome)
            self._garantir_colecao(nome)
