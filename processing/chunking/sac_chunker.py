"""
SAC Chunker.

Summary-Augmented Chunking: usa a ementa do documento como resumo global (SAC
summary) e a injeta como prefixo de cada chunk do `acordao`. Isso fixa cada
fragmento à decisão específica de onde veio, eliminando confusão entre acórdãos
estruturalmente similares (mesmo tema, mesmo vocabulário).

Entrada:  DocumentoJuridico (lido do PostgreSQL — source of truth).
Saída:    list[Chunk] pronta para o Poly-Vector Embedder e os indexadores.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from scraper.schema import DocumentoJuridico
# Lista de marcadores do classificador de provimento:
# é a âncora do dispositivo, usada aqui para o fallback de SAC summary.
from scraper.provimento import _DISPOSITIVO_MARKERS


# Alvo de tamanho da janela, em PALAVRAS. Nome está como 'TOKENS', MAS medimos palavras.
# Veja os testes de test_chunker
TARGET_TOKENS = 500
MIN_TOKENS = 400
MAX_TOKENS = 700
# Sobreposição entre chunks consecutivos para não cortar contexto no limite.
OVERLAP_TOKENS = 80
# Teto (em palavras) do resumo global (prefixo SAC), aplicado tanto à ementa
# quanto ao dispositivo: impede que um prefixo longo estoure o limite do nomic.
SUMMARY_MAX_WORDS = 150


class Chunk(BaseModel):
    """Fragmento de um documento jurídico.

    Os campos de metadado (tipo_documento, provimento, data_julgamento,
    numero_processo, hierarquia_categoria) são duplicados aqui para serem
    gravados no ChromaDB e permitir filtragem sem consultar o PostgreSQL.
    Os embeddings são preenchidos depois, pelo Poly-Vector Embedder.
    """

    chunk_id:     str = Field(default_factory=lambda: str(uuid.uuid4()))
    documento_id: str            # FK → documentos.id (UUID no PostgreSQL)
    texto:        str            # janela COM o prefixo SAC (ementa) — vai para o embedding
    texto_bruto:  str            # a janela crua, SEM o prefixo SAC — vai para o índice BM25
    sac_summary:  str            # ementa usada como contexto global (prefixo SAC)
    posicao:      int            # posição do chunk no documento

    # Metadados de filtragem (duplicados no ChromaDB)
    tipo_documento:       str
    provimento:           str
    data_julgamento:      str | None = None   # ISO 8601, p/ filtro por período
    numero_processo:      str = ""
    hierarquia_categoria: int = 0


def _count_tokens(text: str) -> int:
    """Conta tokens do texto (aproximação por palavras).

    Sem dependência e com janela (700) com folga grande
    sobre o limite de contexto do nomic (2048).
    """
    return len(text.split())


def _dispositivo_summary(acordao: str, max_words: int = SUMMARY_MAX_WORDS) -> str:
    """Fallback para acórdãos SEM ementa, usado como SAC summary de fallback.

    Motivo: Até a coleta atual ~33% dos acórdãos do TST são publicados sem ementa (marcados como
    'possui_ementa=False' no portal).
    Sem um resumo global, esses chunks perderiam o ancoramento que é o propósito
    do SAC.

    O dispositivo (trecho após "ante o exposto…", onde a decisão é enunciada) é o
    melhor substituto da ementa. Recortamos a partir do último marcador e limitamos 
    a `max_words` como maximo de palavras para o fallback.
    Sem marcador, cai para o início do corpo (melhor que nada).
    """
    low = acordao.lower()
    cut = max((low.rfind(m) for m in _DISPOSITIVO_MARKERS), default=-1)         # Default -1 para caso não ache use o inicio do corpo
    trecho = acordao[cut:] if cut >= 0 else acordao
    return " ".join(trecho.split()[:max_words])


def _split_into_windows(text: str) -> list[str]:
    """Divide um texto longo em janelas de ~TARGET_TOKENS com OVERLAP_TOKENS.

    Janela deslizante sobre as palavras: avança um passo menor que a janela,
    então o fim de cada janela reaparece no início da seguinte. A última janela
    curta demais (< MIN_TOKENS) é fundida na anterior para não gerar um chunk raso.
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
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, doc: DocumentoJuridico, documento_id: str) -> list[Chunk]:
        """Gera os chunks de um documento.

        `documento_id` é o UUID `id` da linha no PostgreSQL (FK usada no ChromaDB)
        — NÃO confundir com `doc.id_documento` (chave natural do portal).

        Regras:
          - com acórdão: fragmenta `doc.acordao` em janelas; o resumo global (SAC)
            é a `doc.ementa` ou, quando ela não existe, o dispositivo como proxy
            (ver _dispositivo_summary);
          - sem acórdão (súmula/OJ): a ementa é o próprio conteúdo — vira um chunk
            único e sem prefixo (prefixar a ementa com ela mesma não faz sentido);
          - por chunk: `texto` = resumo + janela (vai para o embedding) e
            `texto_bruto` = janela crua sem o prefixo (vai para o BM25).
        """
        ementa = (doc.ementa or "").strip()
        corpo = (doc.acordao or "").strip()

        if corpo:
            # Acórdão: janela o corpo e usa a ementa como SAC.
            # ~33% dos acórdãos não têm ementa;
            # nesses, cai para o dispositivo como resumo.
            sac_summary = ementa or _dispositivo_summary(corpo)
            # Teto no prefixo, sem ele poderia estourar a capacidade do nomic.
            sac_summary = " ".join(sac_summary.split()[:SUMMARY_MAX_WORDS])
            janelas = _split_into_windows(corpo)
        else:
            # Súmula/OJ e afins: sem seção de acórdão — a ementa é o conteúdo.
            # TODO: Estrutura pode ser diferente, rever quando implementar
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
