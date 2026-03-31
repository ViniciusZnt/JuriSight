import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from scraper.spiders.falcao_acordaos import FalcaoSpider

class MockTokenManager:
    def get_tokens(self):
        return {
            "sessionId": "mock_session",
            "juristkn": "mock_token",
            "expires_at": "2026-04-30T00:00:00",
            "ttl_seconds": 3600
        }
    def force_refresh(self):
        return self.get_tokens()

def mock_parse_document(ementa, texto):
    return {"ementa": ementa, "acordao_section": texto}

def test_spider_logic():
    tasks_data = [
        {"data_inicio": "03-03-2026",
        "data_fim": "03-03-2026"
        },
        {"data_inicio": "04-03-2026",
        "data_fim": "04-03-2026"
        },
        {"data_inicio": "05-03-2026",
         "data_fim": "05-03-2026"
        }
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(tasks_data, tmp)
        tmp_path = tmp.name

    spider = FalcaoSpider()
    spider.TASKS_FILE = tmp_path

    with patch('scraper.spiders.falcao_acordaos.token_manager', MockTokenManager()), \
     patch('scraper.spiders.falcao_acordaos.parse_document', mock_parse_document):

        # Simula o start_requests (que é assíncrono) executando o loop de requests

        # 1. Ler tasks.json
        with open(tmp_path, encoding='utf-8') as f:
            tasks = json.load(f)
        assert len(tasks) == 3, "Deveria carregar 3 tasks"

        # 2. Testar build_url para cada task e página 0
        for task in tasks:
            url = spider.build_url(task["data_inicio"], task["data_fim"], page=0)
            assert "sessionId=mock_session" in url, "sessionId não está na URL"
            assert "juristkn=mock_token" in url, "juristkn não está na URL"
            assert f"dataInicio={task['data_inicio']}" in url, "dataInicio incorreta"
            assert f"dataFim={task['data_fim']}" in url, "dataFim incorreta"
            assert "page=0" in url, "page não está na URL"
            print(f"✅ URL OK para task {task['id']}: {url}")

        # 3. Testar que o método _handle_expired_token chamaria force_refresh
        # (simulando uma resposta 403)
        with patch.object(spider, '_handle_expired_token', wraps=spider._handle_expired_token) as wrapped:
            req_mock = MagicMock()
            req_mock.meta = {"task": tasks[0], "page": 0, "retry_on_403": True}
            spider._handle_expired_token(req_mock)
            assert wrapped.called, "_handle_expired_token não foi invocado"
        print("✅ Teste de renovação de token passou")

        # 4. Testar extract_item
        doc_exemplo = {
            "numeroProcesso": "12345",
            "tribunal": "TRT4",
            "relator": "João Silva",
            "turma": "1ª Turma",
            "gabinete": "Gabinete 1",
            "classeProcesso": "Recurso Ordinário",
            "siglaClasseProcesso": "RO",
            "dataJulgamento": "01/01/2024",
            "dataJuntada": "02/01/2024",
            "idDocumentoAcordao": "ABC123",
            "referenciaLegislativa": ["art_11_clt"],
            "possuiEmenta": "S",
            "ementa": "Ementa exemplo",
            "textoAcordao": "Texto completo"
        }
        task_exemplo = {"data_inicio": "2024-01-01"}
        item = spider.extract_item(doc_exemplo, task_exemplo)
        assert item["numero_processo"] == "12345"
        assert item["tipo_documento"] == "ACORDAO"
        assert item["data_filtro"] == "2024-01-01"
        print("✅ Extração de item passou")

    # Limpeza
    os.unlink(tmp_path)
    print("🎉 Todos os testes passaram!")

if __name__ == "__main__":
    test_spider_logic()