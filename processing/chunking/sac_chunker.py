"""
SAC Chunker.

Summary-Augmented Chunking: usa a ementa do documento como resumo global (SAC
summary) e a injeta como prefixo de cada chunk do `acordao`. Isso fixa cada
fragmento à decisão específica de onde veio, eliminando confusão entre acórdãos
estruturalmente similares (mesmo tema, mesmo vocabulário).

Entrada:  DocumentoJuridico (vem do Postgre — source of truth).
Saída:    list[Chunk] pronta para o Poly-Vector Embedder e os indexadores.
"""
from __future__ import annotations
from typing import Self
from pydantic import BaseModel, model_validator
from scraper.schema import DocumentoJuridico
# Lista de marcadores do classificador de provimento usada para o fallback do SAC.
from scraper.provimento import _DISPOSITIVO_MARKERS


# Alvo de tamanho da janela, em PALAVRAS. Nome está como 'TOKENS', MAS medimos palavras.
# Veja os testes de test_chunker
TARGET_TOKENS = 500
MIN_TOKENS = 400
MAX_TOKENS = 700
# Sobreposição entre chunks consecutivos para não cortar contexto no limite.
OVERLAP_TOKENS = 80
# Teto de palavras do resumo SAC, aplicado tanto à ementaquanto ao dispositivo:
# impede que um prefixo longo estoure o limite do nomic.
SUMMARY_MAX_WORDS = 150


class Chunk(BaseModel):
    """Fragmento de um documento jurídico.

    Os campos de metadado são duplicados aqui para serem
    gravados no ChromaDB e permitir filtragem sem consultar o PostgreSQL.
    """

    chunk_id:     str = ""       # Ver gerar_chunk_id()
    documento_id: str            # FK → documentos.id (UUID no PostgreSQL)
    texto:        str            # janela COM o prefixo SAC  — vai para o embedding
    texto_bruto:  str            # janela crua, SEM o prefixo SAC — vai para o índice BM25
    sac_summary:  str            # prefixo SAC (ementa)
    posicao:      int            # posição do chunk no documento

    # Metadados de filtragem
    tipo_documento:       str
    provimento:           str
    data_julgamento:      str | None = None   # ISO 8601, p/ filtro por período
    numero_processo:      str = ""
    hierarquia_categoria: int = 0

    @model_validator(mode="after")
    def gerar_chunk_id(self) -> Self:
        """Gera o chunk_id determinístico (documento_id:posicao) se ainda não foi criado.

        Input:  self, com documento_id e posicao já preenchidos.
        Returns: Self — checa o campo em memória, não consulta o Chroma.
        """
        if not self.chunk_id:
            self.chunk_id = f"{self.documento_id}:{self.posicao}"
        return self


def _count_tokens(text: str) -> int:
    """Mede o tamanho do texto em palavras (aproximação de tokens).

    Input:  text — texto a medir.
    Returns: número de palavras.
    """
    return len(text.split())


def _dispositivo_summary(acordao: str, max_words: int = SUMMARY_MAX_WORDS) -> str:
    """Resumo para acórdãos sem ementa (~33% do corpus): recorta o dispositivo.

    Input:  acordao — corpo do acórdão; max_words — teto de palavras do resumo.
    Returns: trecho a partir do último marcador de dispositivo (ou o início, se não houver).
    """
    low = acordao.lower()
    cut = max((low.rfind(m) for m in _DISPOSITIVO_MARKERS), default=-1)         # Default -1 para caso não ache use o inicio do corpo
    trecho = acordao[cut:] if cut >= 0 else acordao
    return " ".join(trecho.split()[:max_words])


def _split_into_windows(text: str) -> list[str]:
    """Fatia o texto em janelas deslizantes de ~TARGET_TOKENS com OVERLAP_TOKENS de overlap.

    Input:  text — corpo a fragmentar.
    Returns: lista de janelas; a cauda < MIN_TOKENS é fundida na anterior.
    """
    words = text.split()
    if not words:
        return []

    step = TARGET_TOKENS - OVERLAP_TOKENS      # avanço com overlap
    windows: list[str] = []
    start = 0
    while start < len(words):
        window = words[start:start + TARGET_TOKENS]
        windows.append(" ".join(window))
        if start + TARGET_TOKENS >= len(words):
            break 
        start += step

    # Evita uma última janela muito curta
    # funde o restante com a janela anterior.
    if len(windows) > 1 and len(windows[-1].split()) < MIN_TOKENS:
        tail = windows.pop()
        windows[-1] = f"{windows[-1]} {tail}"

    return windows


class SACChunker:
    """Divide o `acordao` em chunks e prefixa a ementa (SAC summary)."""

    def __init__(
        self,
        target_tokens: int = TARGET_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
    ) -> None:
        """Configura os tamanhos de janela e sobreposição (em palavras).

        Input:  target_tokens, overlap_tokens.
        Returns: None.
        """
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, doc: DocumentoJuridico, documento_id: str) -> list[Chunk]:
        """Gera os chunks SAC de um documento (acórdão em janelas; súmula/OJ em chunk único).

        Input:  doc — DocumentoJuridico; documento_id — UUID do Postgres (FK do Chroma,
                não confundir com doc.id_documento).
        Returns: list[Chunk], vazia se o documento não tem conteúdo indexável.
        """
        ementa = (doc.ementa or "").strip()
        corpo = (doc.acordao or "").strip()

        if corpo:
            sac_summary = ementa or _dispositivo_summary(corpo)
            # Teto no prefixo, sem ele poderia estourar a capacidade do nomic.
            sac_summary = " ".join(sac_summary.split()[:SUMMARY_MAX_WORDS])
            janelas = _split_into_windows(corpo)
        else:
            # Súmula/OJ e afins: sem seção de acórdão — a ementa é o conteúdo.
            # TODO: Estrutura pode ser diferente, rever quando implementar Súmula/OJ
            if not ementa:
                return []
            sac_summary = ""
            janelas = [ementa]

        if not janelas:
            return []

        data_iso = doc.data_julgamento.isoformat() if doc.data_julgamento else None

        chunks: list[Chunk] = []
        for posicao, janela in enumerate(janelas):
            texto = f"{sac_summary}\n\n{janela}" if sac_summary else janela
            chunks.append(
                Chunk(
                    documento_id=documento_id,
                    texto=texto,
                    texto_bruto=janela,
                    sac_summary=sac_summary,
                    posicao=posicao,
                    tipo_documento=doc.tipo_documento.value,
                    provimento=doc.provimento.value,
                    data_julgamento=data_iso,
                    numero_processo=doc.numero_processo,
                    hierarquia_categoria=doc.hierarquia_categoria,
                )
            )
        return chunks
