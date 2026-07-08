"""
Testes do SAC Chunker (processing/chunking/sac_chunker.py).

Unit tests puros — não dependem de PostgreSQL nem do Ollama. Cobrem os três
primitivos (_count_tokens, _split_into_windows, _dispositivo_summary) e a
orquestração em chunk_document, incluindo os casos-limite que motivaram os
ajustes de tamanho de janela e teto de prefixo (evitar estourar os 2048 tokens
do nomic).
"""
from datetime import date

import pytest

from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento
from processing.chunking.sac_chunker import (
    MIN_TOKENS,
    OVERLAP_TOKENS,
    SUMMARY_MAX_WORDS,
    TARGET_TOKENS,
    Chunk,
    SACChunker,
    _count_tokens,
    _dispositivo_summary,
    _split_into_windows,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _words(n: int, prefix: str = "p") -> str:
    """Texto com n 'palavras' distintas e rastreáveis (p0 p1 ... p{n-1})."""
    return " ".join(f"{prefix}{i}" for i in range(n))


def _doc(**kwargs) -> DocumentoJuridico:
    """DocumentoJuridico mínimo com defaults sensatos para os testes."""
    base = dict(
        id_documento="DOC-1",
        tipo_documento=TipoDocumento.ACORDAO,
        hierarquia_categoria=4,
        provimento=Provimento.APROVADO,
        numero_processo="RR-1-2.2024.5.03.0001",
    )
    base.update(kwargs)
    return DocumentoJuridico(**base)


# --------------------------------------------------------------------------- #
# _count_tokens                                                                #
# --------------------------------------------------------------------------- #

def test_count_tokens_vazio_e_espacos():
    assert _count_tokens("") == 0
    assert _count_tokens("   \n\t ") == 0


def test_count_tokens_conta_palavras():
    assert _count_tokens("um dois tres") == 3
    assert _count_tokens("  espacos   colapsam  ") == 2


# --------------------------------------------------------------------------- #
# _split_into_windows                                                          #
# --------------------------------------------------------------------------- #

def test_split_vazio():
    assert _split_into_windows("") == []
    assert _split_into_windows("   ") == []


def test_split_texto_curto_uma_janela():
    texto = _words(TARGET_TOKENS - 100)
    janelas = _split_into_windows(texto)
    assert len(janelas) == 1
    assert janelas[0] == texto


def test_split_janela_exata_nao_gera_segunda():
    janelas = _split_into_windows(_words(TARGET_TOKENS))
    assert len(janelas) == 1
    assert _count_tokens(janelas[0]) == TARGET_TOKENS


def test_split_overlap_correto():
    """O início da 2ª janela deve recuar exatamente OVERLAP_TOKENS do fim da 1ª."""
    # Tamanho que garante 2+ janelas cheias sem cair na fusão da cauda.
    janelas = _split_into_windows(_words(TARGET_TOKENS * 2))
    assert len(janelas) >= 2
    fim_j0 = janelas[0].split()[-1]          # p{TARGET-1}
    inicio_j1 = janelas[1].split()[0]        # p{TARGET-OVERLAP}
    assert fim_j0 == f"p{TARGET_TOKENS - 1}"
    assert inicio_j1 == f"p{TARGET_TOKENS - OVERLAP_TOKENS}"


def test_split_funde_cauda_curta():
    """Uma cauda < MIN_TOKENS não vira janela própria: funde na anterior."""
    # TARGET + um resto pequeno (< MIN) após o passo.
    total = TARGET_TOKENS + 50
    janelas = _split_into_windows(_words(total))
    assert len(janelas) == 1                 # cauda de 50 fundida → janela única
    assert _count_tokens(janelas[0]) >= TARGET_TOKENS


def test_split_ultima_janela_nunca_menor_que_min():
    """Com várias janelas, nenhuma cauda raquítica sobra no fim."""
    janelas = _split_into_windows(_words(TARGET_TOKENS * 3 + 30))
    assert _count_tokens(janelas[-1]) >= MIN_TOKENS


def test_split_cobre_todo_o_texto():
    """Nenhuma palavra do fim é perdida (a última palavra aparece na saída)."""
    total = TARGET_TOKENS * 2 + 200
    janelas = _split_into_windows(_words(total))
    assert janelas[-1].split()[-1] == f"p{total - 1}"


# --------------------------------------------------------------------------- #
# _dispositivo_summary                                                         #
# --------------------------------------------------------------------------- #

def test_dispositivo_recorta_do_ultimo_marcador():
    texto = "relatorio irrelevante aqui. Ante o exposto, nego provimento ao recurso."
    resumo = _dispositivo_summary(texto)
    assert resumo.lower().startswith("ante o exposto")
    assert "relatorio irrelevante" not in resumo


def test_dispositivo_sem_marcador_usa_inicio():
    texto = _words(300, prefix="w")
    resumo = _dispositivo_summary(texto)
    assert resumo.split()[0] == "w0"


def test_dispositivo_respeita_teto_de_palavras():
    texto = "Ante o exposto, " + _words(500)
    resumo = _dispositivo_summary(texto)
    assert _count_tokens(resumo) <= SUMMARY_MAX_WORDS


# --------------------------------------------------------------------------- #
# chunk_document — acórdão com ementa                                          #
# --------------------------------------------------------------------------- #

def test_chunk_acordao_com_ementa_prefixo_sac():
    doc = _doc(ementa="Ementa breve do caso.", acordao=_words(TARGET_TOKENS + 100))
    chunks = doc_chunks = SACChunker().chunk_document(doc, "uuid-1")
    assert len(chunks) >= 1
    c0 = chunks[0]
    assert c0.sac_summary == "Ementa breve do caso."
    assert c0.texto == f"{c0.sac_summary}\n\n{c0.texto_bruto}"   # prefixo SAC
    assert not c0.texto_bruto.startswith(c0.sac_summary)          # bruto sem prefixo
    assert c0.documento_id == "uuid-1"


def test_chunk_metadados_e_posicao():
    doc = _doc(
        ementa="resumo",
        acordao=_words(TARGET_TOKENS * 2),
        data_julgamento=date(2024, 11, 27),
    )
    chunks = SACChunker().chunk_document(doc, "uuid-2")
    assert [c.posicao for c in chunks] == list(range(len(chunks)))
    for c in chunks:
        assert c.tipo_documento == "ACORDAO"
        assert c.provimento == "APROVADO"
        assert c.data_julgamento == "2024-11-27"
        assert c.numero_processo == "RR-1-2.2024.5.03.0001"
        assert c.hierarquia_categoria == 4


def test_chunk_data_julgamento_none():
    doc = _doc(ementa="resumo", acordao=_words(TARGET_TOKENS))
    c0 = SACChunker().chunk_document(doc, "uuid-3")[0]
    assert c0.data_julgamento is None


# --------------------------------------------------------------------------- #
# chunk_document — acórdão SEM ementa (fallback do dispositivo)                #
# --------------------------------------------------------------------------- #

def test_chunk_acordao_sem_ementa_usa_dispositivo():
    corpo = "Relatorio. " + _words(TARGET_TOKENS) + " Ante o exposto, dou provimento."
    doc = _doc(ementa="", acordao=corpo)
    c0 = SACChunker().chunk_document(doc, "uuid-4")[0]
    assert c0.sac_summary != ""                       # teve fallback
    assert "ante o exposto" in c0.sac_summary.lower()  # veio do dispositivo


# --------------------------------------------------------------------------- #
# chunk_document — súmula/OJ (sem acórdão)                                     #
# --------------------------------------------------------------------------- #

def test_chunk_sumula_sem_acordao_chunk_unico_sem_prefixo():
    doc = _doc(tipo_documento=TipoDocumento.SUMULA, hierarquia_categoria=1,
               provimento=Provimento.NAO_APLICAVEL, ementa="Texto da súmula.", acordao="")
    chunks = SACChunker().chunk_document(doc, "uuid-5")
    assert len(chunks) == 1
    c0 = chunks[0]
    assert c0.sac_summary == ""              # sem prefixo (não prefixa a ementa com ela mesma)
    assert c0.texto == c0.texto_bruto == "Texto da súmula."


def test_chunk_documento_sem_conteudo_retorna_vazio():
    doc = _doc(ementa="", acordao="")
    assert SACChunker().chunk_document(doc, "uuid-6") == []


# --------------------------------------------------------------------------- #
# Orçamento de tokens (regressão do estouro do nomic)                          #
# --------------------------------------------------------------------------- #

def test_chunk_respeita_orcamento_de_tokens():
    """Nem o pior caso (ementa longa + janela fundida) passa do limite do nomic.

    Aproximação: TARGET (500) + fusão (< MIN) + prefixo capado (SUMMARY_MAX_WORDS)
    ⇒ folga confortável sob 2048 tokens mesmo com ~1,8 token/palavra.
    """
    ementa_longa = _words(1000, prefix="e")          # bem maior que o teto
    doc = _doc(ementa=ementa_longa, acordao=_words(TARGET_TOKENS * 3 + 40))
    for c in SACChunker().chunk_document(doc, "uuid-7"):
        palavras = _count_tokens(c.texto)
        assert palavras <= TARGET_TOKENS + MIN_TOKENS + SUMMARY_MAX_WORDS
        # prefixo nunca ultrapassa o teto
        assert _count_tokens(c.sac_summary) <= SUMMARY_MAX_WORDS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
