"""
Resposta gerada e ancorada (POST /resposta): poucas frases que respondem à tese,
cada uma citando as decisões (#1..#N, a numeração dos cards) que a sustentam, e a
posição de cada decisão em relação à tese (deferiu / negou / fato diferente / outro).

Ao modelo vão SÓ a EstruturaArgumentativa (que já vai à OpenAI no embedding) e as
ementas públicas dos resultados — nunca o PDF nem texto do caso. Frase sem citação ou com
número fora das decisões enviadas é descartada aqui (a base legal também: com o 4o-mini, sem
âncora ela inventava artigos).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from query.enrichment.schema import EstruturaArgumentativa
from scraper.schema import DocumentoJuridico

MODELO_PADRAO = "gpt-4o-mini"
TIMEOUT_S = 30
MAX_EMENTA = 2000  # caracteres por ementa no prompt (começo + fim, onde fica o desfecho)

_PROMPT = (
    "Você é um advogado trabalhista brasileiro. Responda à tese do usuário com base nas ementas "
    "numeradas (#1, #2…); o cabeçalho de cada uma traz classe, tribunal, turma e data. Escreva em "
    "português, curto e técnico. Preencha o schema na ordem:\n"
    "- `desfechos`: um por decisão. `motivo`: o fato decisivo e a razão, em até 12 palavras. "
    "`pedido_da_tese`: \"deferiu\" ou \"negou\" ao trabalhador o pedido da tese, lendo o desfecho no "
    "fim da ementa; \"outro\" se não decidiu esse pedido. `fatos_da_premissa`: false se os fatos que "
    "a decisão deu por provados contradizem a premissa da tese (ex.: a premissa diz proteção "
    "ineficaz e a decisão a deu por eficaz; a premissa diz acima do limite e a decisão achou abaixo; "
    "outro agente); true se são os mesmos fatos.\n"
    "- `resposta`: começa por \"Sim.\", \"Não.\" ou \"Depende.\" e segue com UMA frase completa, "
    "condicionada à premissa, que um advogado possa citar (\"Sim. Há horas extras a pagar quando a "
    "empresa não comprova o controle da jornada.\").\n"
    "- `fundamentos`: 1 a 3 frases, uma por entendimento: junte numa frase só todas as turmas que "
    "entendem a mesma coisa. Em cada uma: `quem_decidiu` = tribunal e turma de cada decisão "
    "citada, como no cabeçalho (ex.: \"TRT12 1ª Turma\"); `precedente_de_outro_ramo` = o precedente de tribunal superior que essas ementas "
    "invocam quando ele trata de outro ramo do direito ou de outro direito, com o nome e o direito "
    "de que trata, como a própria ementa diz (ex.: \"tese do STF sobre aposentadoria especial\", "
    "usada para um adicional trabalhista), ou vazio. O texto enuncia o entendimento direto, como "
    "regra (\"A falta de controle formal da jornada não dispensa o empregador de provar…\"), sem "
    "nomear tribunal nem turma: a tela mostra quem decidiu a partir das citações. Se `precedente_de_outro_ramo` não é "
    "vazio, cite só decisões que o invocam e escreva, com estas palavras, que se \"aplica por "
    "analogia <precedente_de_outro_ramo>\" ou que se \"recusa a analogia com <precedente_de_outro_ramo>\"; "
    "nunca diga que esse precedente decidiu o pedido da tese. É proibido "
    "escrever que o STF ou o TST decidiu, estabelece ou entende algo sobre o pedido, salvo se a "
    "decisão citada for desse tribunal.\n"
    "- `base_legal`: UMA frase só, com os dispositivos separados por \";\", só com artigos de lei, "
    "NR e anexo, súmulas e OJs que as ementas citadas CITAM e que regem o pedido da tese, na forma "
    "\"<norma como a ementa a cita>: <o que a ementa diz dela>\"; cite em `citacoes` as decisões que "
    "as citam. Nada de norma que não esteja nas ementas; texto vazio se nenhuma cita.\n"
    "- `prova`: UMA frase \"Para o pedido, é preciso provar: …\" com o que as decisões exigiram para "
    "deferir, os itens separados por \";\".\n"
    "- `negaram_por_outros_fatos`: UMA frase só com as que negaram tendo `fatos_da_premissa` false: "
    "\"As que negaram partiram de <o fato delas>, o que não contraria a premissa\", dizendo também se "
    "recusam o precedente ou a analogia que as favoráveis usam; texto vazio se não há. Nunca as chame "
    "de contrárias.\n"
    "- `negaram_pelo_direito`: UMA frase só com as que negaram tendo `fatos_da_premissa` true, com "
    "o motivo jurídico delas (\"As decisões contrárias negaram porque …\"); texto vazio se não há.\n"
    "Sem contagem; não julgue quem está certo.\n"
    "Cada frase cita em `citacoes` os números (no máximo 4, os mais claros) das "
    "decisões que a sustentam e só menciona lei, súmula, OJ ou NR que apareça nelas. Não escreva "
    "números de decisão no texto (nem \"#3\", nem \"casos 5 e 6\")."
)

TipoFrase = Literal["resposta", "fundamento", "base_legal", "prova", "divergencia"]
PosicaoTese = Literal["deferiu", "negou", "fato_diferente", "outro"]


class Frase(BaseModel):
    tipo: TipoFrase
    texto: str
    citacoes: list[int]


class PosicaoDecisao(BaseModel):
    """Posição da decisão #numero em relação à tese — o painel "Decisões que sustentam" usa esta."""
    numero: int
    posicao: PosicaoTese


class Resposta(BaseModel):
    frases: list[Frase] = []
    posicoes: list[PosicaoDecisao] = []


# --- Schema pedido ao modelo: um campo por parte, para nenhuma faltar nem trocar de lugar ---------

class Desfecho(BaseModel):
    numero: int
    motivo: str  # antes da classificação: o modelo lê o fato decisivo e só então classifica
    pedido_da_tese: Literal["deferiu", "negou", "outro"]
    fatos_da_premissa: bool  # negou com fatos que contradizem a premissa = "fato_diferente"


class Citada(BaseModel):
    citacoes: list[int]
    texto: str


class Fundamento(BaseModel):
    quem_decidiu: str  # força o modelo a atribuir a tese ao tribunal citado, não ao STF/TST
    precedente_de_outro_ramo: str  # ex.: Tema 555 (aposentadoria especial) → o texto diz "por analogia"
    citacoes: list[int]
    texto: str


class RespostaGerada(BaseModel):
    desfechos: list[Desfecho]
    resposta: Citada
    fundamentos: list[Fundamento]
    base_legal: Citada
    prova: Citada
    negaram_por_outros_fatos: Citada  # só "fato_diferente"; o servidor confere com os desfechos
    negaram_pelo_direito: Citada  # só "negou"


def _trecho(ementa: str) -> str:
    """Ementa inteira até MAX_EMENTA; acima disso, começo e fim (o dispositivo costuma vir no fim)."""
    e = ementa.strip()
    return e if len(e) <= MAX_EMENTA else f"{e[:1300]} […] {e[-(MAX_EMENTA - 1300):]}"


def _cabecalho(n: int, doc: DocumentoJuridico) -> str:
    """'#3 (RORSum, TRT2, 11ª Turma, 2025-05-12)' — só metadados públicos da decisão."""
    meta = [doc.sigla_classe, doc.tribunal, doc.turma, doc.data_julgamento and doc.data_julgamento.isoformat()]
    return f"#{n} ({', '.join(m for m in meta if m)})"


# Fundamento que invoca precedente de outro ramo sem dizer "analogia" (ou que a recusa) atribuiria ao
# precedente uma tese que ele não fixou: sai — melhor uma frase a menos que um erro jurídico na peça.
_ANALOGIA = re.compile(r"analogia|n[ãa]o aplica|inaplic|afasta|recusa", re.IGNORECASE)


def _sem_erro_de_precedente(f: Citada | Fundamento) -> bool:
    return not getattr(f, "precedente_de_outro_ramo", "").strip() or bool(_ANALOGIA.search(f.texto))


def _posicao(d: Desfecho) -> PosicaoTese:
    return "fato_diferente" if d.pedido_da_tese == "negou" and not d.fatos_da_premissa else d.pedido_da_tese


def chave_da_resposta(estrutura: EstruturaArgumentativa, ids: list[str]) -> str:
    """Chave do cache (query/search/resposta_cache.py): muda com o modelo, a temperatura, o prompt,
    a tese ou a lista de decisões — qualquer uma dessas muda a resposta."""
    partes = {
        "modelo": os.getenv("OPENAI_GEN_MODEL", MODELO_PADRAO),
        "temperatura": os.getenv("OPENAI_GEN_TEMPERATURE", "0"),
        "prompt": _PROMPT,
        "tese": estrutura.model_dump(mode="json", exclude_defaults=True),
        "ids": ids,
    }
    return hashlib.sha256(json.dumps(partes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def gerar_resposta(
    estrutura: EstruturaArgumentativa,
    decisoes: dict[int, DocumentoJuridico],
    client: OpenAI,
) -> Resposta:
    """Pede a resposta ao modelo e devolve só o que foi validado aqui.

    Input:  estrutura — a tese revisada; decisoes — número do card (#n) -> documento.
    Returns: frases na ordem resposta, fundamentos, base legal, prova, divergência, cada uma com
             citações que são todas números de `decisoes` (sem repetição), e a posição de cada
             decisão em relação à tese.
    Raises: openai.OpenAIError (rede, timeout, status) — o endpoint vira 503.
    """
    if not decisoes:
        return Resposta()
    ementas = "\n\n".join(
        f"{_cabecalho(n, d)}\n{_trecho(d.ementa)}" for n, d in sorted(decisoes.items())
    )
    tese = estrutura.model_dump_json(exclude_defaults=True)
    resposta = client.chat.completions.parse(
        model=os.getenv("OPENAI_GEN_MODEL", MODELO_PADRAO),
        temperature=float(os.getenv("OPENAI_GEN_TEMPERATURE", "0")),
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": f"Tese:\n{tese}\n\nEmentas:\n{ementas}"},
        ],
        response_format=RespostaGerada,
        timeout=TIMEOUT_S,
    )
    g = resposta.choices[0].message.parsed
    if g is None:  # recusa do modelo
        return Resposta()
    posicoes = {d.numero: _posicao(d) for d in reversed(g.desfechos) if d.numero in decisoes}
    # A divergência só cita quem negou pelo direito; a frase de "outros fatos", só quem negou por fato
    # diferente — citação que não bate com o desfecho sai, para a resposta não chamar de contrária
    # uma decisão que só tinha outros fatos.
    partes: list[tuple[TipoFrase, Citada | Fundamento, str | None]] = [
        ("resposta", g.resposta, None), *(("fundamento", f, None) for f in g.fundamentos),
        ("base_legal", g.base_legal, None), ("prova", g.prova, None), ("divergencia", g.negaram_pelo_direito, "negou"),
        ("divergencia", g.negaram_por_outros_fatos, "fato_diferente"),  # de direito antes, se houver
    ]
    frases: list[Frase] = []
    for tipo, f, exigida in partes:
        citacoes = [c for c in dict.fromkeys(f.citacoes) if exigida is None or posicoes.get(c) == exigida]
        if f.texto.strip() and citacoes and all(c in decisoes for c in citacoes) and _sem_erro_de_precedente(f):
            frases.append(Frase(tipo=tipo, texto=f.texto.strip(), citacoes=citacoes))
    return Resposta(
        frases=frases,
        posicoes=[PosicaoDecisao(numero=n, posicao=p) for n, p in sorted(posicoes.items())],
    )
