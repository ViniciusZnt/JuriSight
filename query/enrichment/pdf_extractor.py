"""
PDF Extractor (RFC Tabela 6/12).

Extrai o texto do PDF enviado pelo usuário (RF01). Quando o documento é longo
demais, aplica sumarização hierárquica antes de devolver o texto (RNF05/FA04):
divide em blocos, resume cada um, e condensa os resumos numa tese única.

O extrator em si (extract_text) não depende de LLM — só de pdfplumber, com o
`opener` injetável para teste. A sumarização (resumir_hierarquico) também não
importa Ollama diretamente: recebe resumir_bloco/condensar como funções
injetadas, para não acoplar este módulo a um provedor de LLM específico. As
implementações reais vivem em query_enrichment.py e são passadas pela camada de
API (query/api/app.py), que é quem sabe montar o QueryEnricher.
"""
from __future__ import annotations

from typing import Callable

import pdfplumber

# Acima disso, o texto é dividido em blocos e resumido antes de seguir (FA04).
LIMITE_CHARS_SEM_SUMARIZACAO = 8000
# Tamanho alvo de cada bloco enviado ao LLM para resumo individual.
TAMANHO_BLOCO = 4000
# Teto de blocos processados — protege o tempo de resposta (RNF02: < 30s).
# Blocos excedentes são descartados (o documento já é atípicamente longo).
MAX_BLOCOS = 8


class PDFSemTextoError(ValueError):
    """PDF sem texto extraível (documento escaneado/imagem) — sinaliza FA02."""


def extract_text(pdf_bytes: bytes, *, opener: Callable = pdfplumber.open) -> str:
    """Extrai e concatena o texto de todas as páginas do PDF.

    Input:  pdf_bytes — conteúdo bruto do PDF; opener — abre o PDF (injetável
            em teste; default é pdfplumber.open sobre um buffer em memória).
    Returns: texto concatenado das páginas, separado por linha em branco.
    Raises: PDFSemTextoError se nenhuma página tiver texto extraível (FA02).
    """
    import io

    with opener(io.BytesIO(pdf_bytes)) as pdf:
        paginas = [p.extract_text() or "" for p in pdf.pages]

    texto = "\n\n".join(p.strip() for p in paginas if p.strip())
    if not texto:
        raise PDFSemTextoError(
            "Não foi possível extrair texto do PDF (possível documento escaneado)."
        )
    return texto


def _dividir_em_blocos(texto: str, tamanho_bloco: int, max_blocos: int) -> list[str]:
    """Empacota parágrafos em blocos de até `tamanho_bloco` caracteres.

    Input:  texto — texto completo; tamanho_bloco; max_blocos — teto de blocos
            (o restante do texto é descartado se exceder).
    Returns: lista de blocos (parágrafos não são quebrados no meio quando possível).
    """
    paragrafos = [p for p in texto.split("\n\n") if p.strip()]
    blocos: list[str] = []
    atual = ""
    for p in paragrafos:
        candidato = f"{atual}\n\n{p}" if atual else p
        if len(candidato) > tamanho_bloco and atual:
            blocos.append(atual)
            if len(blocos) >= max_blocos:
                return blocos
            atual = p
        else:
            atual = candidato
    if atual and len(blocos) < max_blocos:
        blocos.append(atual)
    return blocos


def resumir_hierarquico(
    texto: str,
    *,
    resumir_bloco: Callable[[str], str],
    condensar: Callable[[list[str]], str],
    limite_chars: int = LIMITE_CHARS_SEM_SUMARIZACAO,
    tamanho_bloco: int = TAMANHO_BLOCO,
    max_blocos: int = MAX_BLOCOS,
) -> str:
    """Sumarização hierárquica para PDFs longos (RNF05/FA04).

    Texto dentro do limite passa direto, sem custo de LLM. Texto longo é dividido
    em blocos, cada um resumido individualmente, e os resumos são condensados
    numa tese única antes de seguir para o Query Enrichment.

    Input:  texto — texto extraído do PDF; resumir_bloco — resume um bloco;
            condensar — condensa a lista de resumos numa tese única; limite_chars,
            tamanho_bloco, max_blocos — ver módulo.
    Returns: o próprio texto (se curto) ou a tese condensada (se longo).
    """
    if len(texto) <= limite_chars:
        return texto

    blocos = _dividir_em_blocos(texto, tamanho_bloco, max_blocos)
    resumos = [resumir_bloco(b) for b in blocos]
    return condensar(resumos)
