import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scraper.spiders.utils.html_parser import html_to_text, extract_sections
from scraper.spiders.utils.juristkn import token_manager


def test_api_connection():
    """Testa se consegue se conectar à API e receber documentos."""
    import requests
    from urllib.parse import urlencode

    print("\n=== TESTE 1: Conexão com a API ===")

    tokens = token_manager.get_tokens()
    print(f"Token obtido: {tokens['juristkn'][:8]}...")
    print(f"Session:      {tokens['sessionId']}")
    print(f"Expira em:    {tokens.get('ttl_seconds', '?')}s")

    params = {
        "sessionId":                 tokens["sessionId"],
        "latitude":                  0,
        "longitude":                 0,
        "juristkn":                  tokens["juristkn"],
        "texto":                     "",
        "verTodosPrecedentes":       "false",
        "tribunais":                 "",
        "pesquisaSomenteNasEmentas": "false",
        "filtroRapidoData":          "IntervaloSelecionado",
        "dataInicio":                "2024-01-01",
        "dataFim":                   "2024-01-31",
        "colecao":                   "acordaos",
        "page":                      0,
        "size":                      10,
    }

    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer":         "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa",
        "Origin":          "https://jurisprudencia.jt.jus.br",
        "Connection":      "keep-alive",
    }

    session = requests.Session()
    session.headers.update(headers)

    response = session.get(
        "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional-backend/api/no-auth/pesquisa",
        params=params,
        timeout=15,
    )

    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"Erro: {response.text[:300]}")
        return None

    data = response.json()
    docs = data.get("documentos", [])
    print(f"Documentos recebidos: {len(docs)}")

    if not docs:
        print("AVISO: nenhum documento retornado para o período testado.")
        return None

    print(f"Primeiro documento: {docs[0].get('numeroProcesso')} | {docs[0].get('tribunal')}")
    return docs[0]


def test_html_to_text(doc: dict):
    """Testa a limpeza de HTML na ementa."""
    print("\n=== TESTE 2: Limpeza de HTML (ementa) ===")

    ementa_html = doc.get("ementa", "")
    ementa_texto = html_to_text(ementa_html)

    print(f"HTML original:  {len(ementa_html)} caracteres")
    print(f"Texto extraído: {len(ementa_texto)} caracteres")
    print(f"\nEmenta:\n{ementa_texto[:500]}")


def test_extract_sections(doc: dict):
    """Testa a extração de seções do textoAcordao."""
    print("\n=== TESTE 3: Extração de seções do textoAcordao ===")

    texto_html = doc.get("textoAcordao", "")
    print(f"HTML original: {len(texto_html)} caracteres")

    sections = extract_sections(texto_html)

    for field, content in sections.items():
        status = "✓" if content else "✗ vazio"
        preview = content[:120].replace("\n", " ") if content else ""
        print(f"\n[{status}] {field.upper()}")
        if preview:
            print(f"  {preview}...")


def test_full_item(doc: dict):
    """Simula a montagem completa do DocumentItem."""
    print("\n=== TESTE 4: Montagem do DocumentItem completo ===")

    sections = extract_sections(doc.get("textoAcordao", ""))

    item = {
        "tipo_documento":         "ACORDAO",
        "hierarquia_categoria":   4,
        "ano":                    2024,
        "mes":                    1,
        "id_documento":           doc.get("idDocumentoAcordao", ""),
        "numero_processo":        doc.get("numeroProcesso", ""),
        "tribunal":               doc.get("tribunal", ""),
        "classe_processo":        doc.get("classeProcesso", ""),
        "sigla_classe":           doc.get("siglaClasseProcesso", ""),
        "relator":                doc.get("relator", ""),
        "turma":                  doc.get("turma", ""),
        "gabinete":               doc.get("gabinete", ""),
        "id_gabinete":            doc.get("idGabinete"),
        "id_turma":               doc.get("idTurma"),
        "data_julgamento":        doc.get("dataJulgamento", ""),
        "data_juntada":           doc.get("dataJuntada", ""),
        "possui_ementa":          doc.get("possuiEmenta", "N") == "S",
        "referencia_legislativa": doc.get("referenciaLegislativa", []),
        "ementa":                 html_to_text(doc.get("ementa", "")),
        "cabecalho":              sections.get("cabecalho", ""),
        "dispositivo":            sections.get("dispositivo", ""),
        "relatorio":              sections.get("relatorio", ""),
        "fundamentacao":          sections.get("fundamentacao", ""),
        "votos":                  sections.get("votos", ""),
    }

    print("\nCampos preenchidos:")
    for key, value in item.items():
        if isinstance(value, str):
            status = "✓" if value else "✗"
            print(f"  {status} {key}: {value[:60]}..." if len(value) > 60 else f"  {status} {key}: {value}")
        else:
            print(f"  ✓ {key}: {value}")

    return item


if __name__ == "__main__":
    try:
        doc = test_api_connection()
        if doc:
            test_html_to_text(doc)
            test_extract_sections(doc)
            test_full_item(doc)
            print("\n\n✅ Todos os testes concluídos.")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()