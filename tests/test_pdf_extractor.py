"""
Testes do PDF Extractor (query/enrichment/pdf_extractor.py).

pdfplumber é substituído por um `opener` fake (páginas fake com .extract_text()),
e resumir_bloco/condensar por callables fake que só contam chamadas — nenhum PDF
real nem LLM real é necessário.
"""
import pytest

from query.enrichment.pdf_extractor import (
    LIMITE_CHARS_SEM_SUMARIZACAO,
    PDFSemTextoError,
    extract_text,
    resumir_hierarquico,
)


class _FakePagina:
    def __init__(self, texto: str | None):
        self._texto = texto

    def extract_text(self) -> str | None:
        return self._texto


class _FakePDF:
    def __init__(self, paginas: list[_FakePagina]):
        self.pages = paginas

    def __enter__(self) -> "_FakePDF":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _opener(paginas: list[str | None]):
    return lambda _buffer: _FakePDF([_FakePagina(t) for t in paginas])


# --------------------------------------------------------------------------- #
# extract_text                                                                 #
# --------------------------------------------------------------------------- #

def test_extract_text_concatena_paginas():
    texto = extract_text(b"fake", opener=_opener(["primeira página", "segunda página"]))
    assert "primeira página" in texto
    assert "segunda página" in texto


def test_extract_text_ignora_paginas_vazias_no_meio():
    texto = extract_text(b"fake", opener=_opener(["conteúdo", "", None, "mais conteúdo"]))
    assert "conteúdo" in texto and "mais conteúdo" in texto


def test_extract_text_todas_vazias_levanta_pdf_sem_texto():
    with pytest.raises(PDFSemTextoError):
        extract_text(b"fake", opener=_opener(["", None, "   "]))


# --------------------------------------------------------------------------- #
# resumir_hierarquico                                                          #
# --------------------------------------------------------------------------- #

class _ResumidorFake:
    def __init__(self):
        self.chamadas_bloco = 0
        self.chamadas_condensar = 0

    def resumir_bloco(self, texto: str) -> str:
        self.chamadas_bloco += 1
        return f"resumo({len(texto)})"

    def condensar(self, resumos: list[str]) -> str:
        self.chamadas_condensar += 1
        return "TESE_CONDENSADA: " + " ".join(resumos)


def test_resumir_hierarquico_texto_curto_nao_chama_llm():
    fake = _ResumidorFake()
    texto = "texto curto"
    resultado = resumir_hierarquico(texto, resumir_bloco=fake.resumir_bloco, condensar=fake.condensar)
    assert resultado == texto
    assert fake.chamadas_bloco == 0
    assert fake.chamadas_condensar == 0


def test_resumir_hierarquico_texto_longo_divide_resume_e_condensa():
    fake = _ResumidorFake()
    paragrafo = "frase relevante do processo. " * 50  # ~1500 chars
    texto = "\n\n".join([paragrafo] * 10)  # bem acima do limite default
    assert len(texto) > LIMITE_CHARS_SEM_SUMARIZACAO

    resultado = resumir_hierarquico(texto, resumir_bloco=fake.resumir_bloco, condensar=fake.condensar)

    assert resultado.startswith("TESE_CONDENSADA:")
    assert fake.chamadas_bloco > 0
    assert fake.chamadas_condensar == 1


def test_resumir_hierarquico_respeita_max_blocos():
    fake = _ResumidorFake()
    paragrafo = "frase relevante do processo. " * 50
    texto = "\n\n".join([paragrafo] * 20)

    resumir_hierarquico(
        texto,
        resumir_bloco=fake.resumir_bloco,
        condensar=fake.condensar,
        tamanho_bloco=1000,
        max_blocos=3,
    )
    assert fake.chamadas_bloco == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
