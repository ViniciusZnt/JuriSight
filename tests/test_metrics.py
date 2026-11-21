"""GET /metrics (Prometheus): exposto pela API, fora do OpenAPI, rótulo = template da rota."""
import pytest
from fastapi.testclient import TestClient

from query.api.app import app, get_current_user, get_doc_retriever
from tests.fakes import FakeDocRetriever, usuario_fake

_UUID = "3f6c1a52-9d0e-4b7a-8c11-aa77bb88cc99"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: usuario_fake("t@example.com", "T")
    app.dependency_overrides[get_doc_retriever] = lambda: FakeDocRetriever({})
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_metrics_expoe_texto_prometheus(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


def test_metrics_rotulo_e_template_da_rota(client):
    client.get(f"/document/{_UUID}")
    corpo = client.get("/metrics").text
    assert 'handler="/document/{documento_id}"' in corpo
    assert _UUID not in corpo


def test_metrics_fora_do_openapi(client):
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


def test_metrics_nao_conta_metrics_nem_health(client):
    client.get("/health")
    client.get("/metrics")
    corpo = client.get("/metrics").text
    assert 'handler="/metrics"' not in corpo
    assert 'handler="/health"' not in corpo
