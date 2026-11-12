"""
Testes do Query Enrichment (query/enrichment/query_enrichment.py).

O cliente Ollama é mockado — os testes validam a LÓGICA do enriquecimento
(montagem do conteúdo, parsing/validação da resposta, RN05) sem chamar um LLM
real. Um teste de integração real (com Ollama rodando) fica fora daqui.
"""
import pytest

from query.enrichment.query_enrichment import QueryEnricher, _montar_conteudo
from query.enrichment.schema import EstruturaArgumentativa


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeResponse:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeOllamaClient:
    """Cliente Ollama falso: expõe .chat() e registra as chamadas."""

    def __init__(self, respostas: list[str]):
        self._respostas = list(respostas)
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._respostas.pop(0))


def _enricher(respostas: list[str]) -> tuple[QueryEnricher, _FakeOllamaClient]:
    fake = _FakeOllamaClient(respostas)
    return QueryEnricher(client=fake), fake


_JSON_COMPLETO = (
    '{"pedido_principal": "adicional de insalubridade grau máximo", '
    '"agente_nocivo": ["benzeno"], "violacoes": ["ausência de EPI eficaz"], '
    '"normas": ["NR-15"], "empresa_ciente": true, "setor": "metalurgia", '
    '"cargo": "operador de prensa", '
    '"tese_central": "A empresa tinha ciência do risco."}'
)


# --------------------------------------------------------------------------- #
# _montar_conteudo                                                             #
# --------------------------------------------------------------------------- #

def test_montar_conteudo_combina_texto_e_intencao():
    conteudo = _montar_conteudo("texto do PDF", "intenção do advogado")
    assert "texto do PDF" in conteudo
    assert "intenção do advogado" in conteudo


def test_montar_conteudo_so_intencao_fa01():
    conteudo = _montar_conteudo(None, "intenção do advogado")
    assert "intenção do advogado" in conteudo


def test_montar_conteudo_levanta_erro_quando_tudo_vazio():
    with pytest.raises(ValueError):
        _montar_conteudo(None, None)
    with pytest.raises(ValueError):
        _montar_conteudo("", "   ")


# --------------------------------------------------------------------------- #
# extract_estrutura                                                            #
# --------------------------------------------------------------------------- #

def test_extract_estrutura_retorna_estrutura_validada():
    enricher, fake = _enricher([_JSON_COMPLETO])
    estrutura = enricher.extract_estrutura("texto do PDF", "intenção")

    assert isinstance(estrutura, EstruturaArgumentativa)
    assert estrutura.pedido_principal == "adicional de insalubridade grau máximo"
    assert estrutura.agente_nocivo == ["benzeno"]
    assert estrutura.empresa_ciente is True


def test_extract_estrutura_pede_schema_sem_campos_de_filtro_restrito():
    """O LLM não preenche dispositivos/expressões: viram filtro restrito sem o advogado ver."""
    enricher, fake = _enricher([_JSON_COMPLETO])
    enricher.extract_estrutura("texto", None)
    propriedades = fake.calls[0]["format"]["properties"]
    assert "dispositivos" not in propriedades and "expressoes" not in propriedades
    assert "expressoes_chave" in propriedades and "normas" in propriedades
    assert "dispositivos_relacionados" in propriedades


def test_extrair_separa_expressoes_sugeridas_da_estrutura():
    json_llm = (
        '{"pedido_principal": "indenização", "tese_central": "Houve dano coletivo.", '
        '"expressoes_chave": ["dano moral coletivo", " ", "dano moral coletivo", "ação civil pública"], '
        '"expressoes": ["não deve entrar"], "dispositivos": ["art_1_clt"]}'
    )
    enricher, _ = _enricher([json_llm])
    extracao = enricher.extrair("texto", None)
    assert extracao.expressoes_sugeridas == ["dano moral coletivo", "ação civil pública"]
    assert extracao.estrutura.expressoes == [] and extracao.estrutura.dispositivos == []
    assert extracao.estrutura.tese_central == "Houve dano coletivo."


def test_extract_estrutura_campos_ausentes_caem_no_default_rn05():
    json_parcial = '{"pedido_principal": "algo"}'
    enricher, fake = _enricher([json_parcial])
    estrutura = enricher.extract_estrutura("texto", None)

    assert estrutura.pedido_principal == "algo"
    assert estrutura.agente_nocivo == []
    assert estrutura.empresa_ciente is None
    assert estrutura.setor is None


def test_extract_estrutura_propaga_erro_sem_chamar_llm_quando_nada_a_enriquecer():
    enricher, fake = _enricher([])
    with pytest.raises(ValueError):
        enricher.extract_estrutura(None, None)
    assert fake.calls == []


# --------------------------------------------------------------------------- #
# resumir_bloco / condensar                                                    #
# --------------------------------------------------------------------------- #

def test_resumir_bloco_devolve_conteudo_da_resposta():
    enricher, fake = _enricher(["  resumo do bloco  "])
    resultado = enricher.resumir_bloco("texto original longo")
    assert resultado == "resumo do bloco"


def test_condensar_junta_resumos_num_unico_prompt():
    enricher, fake = _enricher(["tese condensada"])
    resultado = enricher.condensar(["resumo 1", "resumo 2"])
    assert resultado == "tese condensada"
    mensagens = fake.calls[0]["messages"]
    assert "resumo 1" in mensagens[-1]["content"]
    assert "resumo 2" in mensagens[-1]["content"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


def test_extrair_separa_dispositivos_sugeridos():
    json_llm = (
        '{"pedido_principal": "horas extras", "normas": [], '
        '"dispositivos_relacionados": ["CLT art. 62, I", " ", "CLT art. 62, I", "CLT art. 74"]}'
    )
    enricher, _ = _enricher([json_llm])
    extracao = enricher.extrair("texto", None)
    assert extracao.dispositivos_sugeridos == ["CLT art. 62, I", "CLT art. 74"]
    assert extracao.estrutura.dispositivos == [] and extracao.estrutura.normas == []


def test_ia_nao_preenche_tribunal_nem_fase():
    """tribunais/fase só vêm do advogado: fora do schema do LLM e descartados se ele os devolver."""
    enricher, fake = _enricher([
        '{"pedido_principal": "indenização", "tese_central": "Houve dano.", '
        '"tribunais": ["TRT2"], "fase": "conhecimento"}'
    ])
    extracao = enricher.extrair("texto", None)
    propriedades = fake.calls[0]["format"]["properties"]
    assert "tribunais" not in propriedades and "fase" not in propriedades
    assert extracao.estrutura.tribunais == [] and extracao.estrutura.fase is None
