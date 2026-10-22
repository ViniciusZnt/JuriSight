"""Índices de payload e atualização de provimento no Qdrant (modo :memory:)."""
import pytest
from qdrant_client import QdrantClient, models

from indexing.vector_store.qdrant_store import (
    COLLECTION_COMPLETO,
    COLLECTION_EMENTA,
    QdrantStore,
)

DOC_A = "aaaaaaaa-0000-0000-0000-000000000001"
DOC_B = "bbbbbbbb-0000-0000-0000-000000000002"
VEC = [1.0, 0.0, 0.0, 0.0]


@pytest.fixture
def store():
    client = QdrantClient(":memory:")
    for nome in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
        client.create_collection(
            nome, vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE)
        )
    pontos_chunks = [
        (1, DOC_A, 0), (2, DOC_A, 1), (3, DOC_B, 0),
    ]
    client.upsert(COLLECTION_COMPLETO, points=[
        models.PointStruct(id=i, vector=VEC, payload={"documento_id": d, "provimento": "NEGADO", "posicao": p})
        for i, d, p in pontos_chunks
    ])
    client.upsert(COLLECTION_EMENTA, points=[
        models.PointStruct(id=DOC_A, vector=VEC, payload={"documento_id": DOC_A, "provimento": "NEGADO"}),
        models.PointStruct(id=DOC_B, vector=VEC, payload={"documento_id": DOC_B, "provimento": "NEGADO"}),
    ])
    return QdrantStore(client)


def _provimentos(store, colecao):
    pontos, _ = store._client.scroll(colecao, limit=100, with_payload=True)
    return {(p.payload["documento_id"], p.payload.get("posicao")): p.payload["provimento"] for p in pontos}


def test_atualizar_provimento_nas_duas_colecoes(store):
    enviados = store.atualizar_provimento("APROVADO", [DOC_A])
    assert enviados == 1
    completo = _provimentos(store, COLLECTION_COMPLETO)
    assert completo[(DOC_A, 0)] == "APROVADO"
    assert completo[(DOC_A, 1)] == "APROVADO"
    assert completo[(DOC_B, 0)] == "NEGADO"
    ementa = _provimentos(store, COLLECTION_EMENTA)
    assert ementa[(DOC_A, None)] == "APROVADO"
    assert ementa[(DOC_B, None)] == "NEGADO"


def test_atualizar_em_lotes(store):
    ids = [DOC_A, DOC_B, "cccccccc-0000-0000-0000-000000000003"]
    assert store.atualizar_provimento("PARCIAL", ids, lote=1) == 3
    assert set(_provimentos(store, COLLECTION_COMPLETO).values()) == {"PARCIAL"}
    assert set(_provimentos(store, COLLECTION_EMENTA).values()) == {"PARCIAL"}


def test_atualizar_lista_vazia(store):
    assert store.atualizar_provimento("APROVADO", []) == 0


def test_garantir_indices_idempotente(store):
    store.garantir_indices_payload()
    store.garantir_indices_payload()
    for nome in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
        schema = store._client.get_collection(nome).payload_schema
        # No modo :memory: o cliente local pode não reportar o índice.
        if schema:
            assert "provimento" in schema and "documento_id" in schema


def test_query_filtra_por_provimento(store):
    store.atualizar_provimento("APROVADO", [DOC_A])
    for colecao in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
        res = store.query(VEC, n_results=10, where={"provimento": "APROVADO"}, collection=colecao)
        assert res and {r["documento_id"] for r in res} == {DOC_A}
