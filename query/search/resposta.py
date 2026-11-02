"""
Resposta gerada e ancorada (POST /resposta): poucas frases que respondem à tese,
cada uma citando as decisões (#1..#N, a numeração dos cards) que a sustentam, e a
posição de cada decisão em relação à tese (deferiu / negou / fato diferente / outro).

Ao modelo vão SÓ a EstruturaArgumentativa (que já vai à OpenAI no embedding) e as
ementas públicas dos resultados — nunca o PDF nem texto do caso. Frase sem citação
(exceto a única de base legal) ou com número fora das decisões enviadas é descartada aqui.
"""
from __future__ import annotations

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
    "- `resposta`: frase completa que responde direto e condicionada à premissa (\"Sim, quando …\", "
    "\"Não, porque …\", \"Depende de …\").\n"
    "- `fundamentos`: 1 a 3 frases. Em cada uma: `quem_decidiu` = tribunal e turma de cada decisão "
    "citada, como no cabeçalho (ex.: \"TRT12 1ª Turma\"), e o texto nomeia a turma quando outras "
    "turmas do mesmo tribunal decidiram diferente; `precedente_de_outro_ramo` = o precedente de tribunal superior que essas ementas "
    "invocam quando ele trata de outro ramo do direito ou de outro direito, com o nome e o direito "
    "de que trata, como a própria ementa diz (ex.: \"tese do STF sobre aposentadoria especial\", "
    "usada para um adicional trabalhista), ou vazio. O texto atribui o entendimento a quem decidiu "
    "(\"a 1ª Turma do TRT12 entende…\", \"turmas do TRT2…\"). Se `precedente_de_outro_ramo` não é "
    "vazio, cite só decisões que o invocam e escreva, com estas palavras, que o tribunal \"aplica por "
    "analogia <precedente_de_outro_ramo>\" ou que \"recusa a analogia com <precedente_de_outro_ramo>\"; "
    "nunca diga que esse precedente decidiu o pedido da tese. É proibido "
    "escrever que o STF ou o TST decidiu, estabelece ou entende algo sobre o pedido, salvo se a "
    "decisão citada for desse tribunal.\n"
    "- `base_legal`: UMA frase só com artigos de lei, NR e anexo, súmulas e OJs do TST que regem "
    "exatamente o pedido da tese (não outros pedidos que as ementas também julgam; nada de STF, "
    "temas ou acórdãos), as que favorecem e as que limitam o "
    "pedido, com o que cada uma diz com exatidão, na forma \"<norma>: se <condição>, <efeito>\", mesmo que "
    "não estejam nas ementas, só as que você conhece com segurança (número e conteúdo certos).\n"
    "- `prova`: UMA frase \"Para o pedido, é preciso provar: …\" com o que as decisões exigiram para "
    "deferir.\n"
    "- `negaram_por_outros_fatos`: UMA frase só com as que negaram tendo `fatos_da_premissa` false: "
    "\"As que negaram partiram de <o fato delas>, o que não contraria a premissa\", dizendo também se "
    "recusam o precedente ou a analogia que as favoráveis usam; texto vazio se não há. Nunca as chame "
    "de contrárias.\n"
    "- `negaram_pelo_direito`: UMA frase só com as que negaram tendo `fatos_da_premissa` true, com "
    "o motivo jurídico delas (\"As decisões contrárias negaram porque …\"); texto vazio se não há.\n"
    "Sem contagem; não julgue quem está certo.\n"
    "Cada frase, exceto a base legal, cita em `citacoes` os números (no máximo 4, os mais claros) das "
    "decisões que a sustentam e só menciona lei, súmula, OJ ou NR que apareça nelas. Não escreva "
    "números de decisão no texto (nem \"#3\", nem \"casos 5 e 6\")."
)

TipoFrase = Literal["resposta", "fundamento", "base_legal", "prova", "divergencia"]
PosicaoTese = Literal["deferiu", "negou", "fato_diferente", "outro"]


class Frase(BaseModel):
    tipo: TipoFrase
    texto: str
    citacoes: list[int]  # vazio só na "base_legal"


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
    base_legal: str
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


def _do_tribunal_nomeado(f: Citada | Fundamento, decisoes: dict[int, DocumentoJuridico]) -> list[int]:
    """Num fundamento, só ficam as citações de decisões cujo tribunal o texto nomeia ("o TRT2 entende"
    não pode levar chip de decisão do TRT12)."""
    if not isinstance(f, Fundamento):
        return f.citacoes
    # número inexistente fica, para a frase inteira cair na validação de baixo
    return [c for c in f.citacoes if c not in decisoes or re.search(rf"\b{re.escape(decisoes[c].tribunal)}\b", f.texto)]


def _posicao(d: Desfecho) -> PosicaoTese:
    return "fato_diferente" if d.pedido_da_tese == "negou" and not d.fatos_da_premissa else d.pedido_da_tese


def gerar_resposta(
    estrutura: EstruturaArgumentativa,
    decisoes: dict[int, DocumentoJuridico],
    client: OpenAI,
) -> Resposta:
    """Pede a resposta ao modelo e devolve só o que foi validado aqui.

    Input:  estrutura — a tese revisada; decisoes — número do card (#n) -> documento.
    Returns: frases na ordem resposta, fundamentos, base legal, prova, divergência, cada uma com
             citações que são todas números de `decisoes` (sem repetição) — só a base legal vem
             sem citação (e sempre sem chips) — e a posição de cada decisão em relação à tese.
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
        ("prova", g.prova, None), ("divergencia", g.negaram_pelo_direito, "negou"),
        ("divergencia", g.negaram_por_outros_fatos, "fato_diferente"),  # de direito antes, se houver
    ]
    frases: list[Frase] = []
    for tipo, f, exigida in partes:
        citacoes = [c for c in dict.fromkeys(_do_tribunal_nomeado(f, decisoes)) if exigida is None or posicoes.get(c) == exigida]
        if f.texto.strip() and citacoes and all(c in decisoes for c in citacoes) and _sem_erro_de_precedente(f):
            frases.append(Frase(tipo=tipo, texto=f.texto.strip(), citacoes=citacoes))
    if g.base_legal.strip():  # sem chips: não vem das ementas; entra antes da prova
        i = next((k for k, f in enumerate(frases) if f.tipo in ("prova", "divergencia")), len(frases))
        frases.insert(i, Frase(tipo="base_legal", texto=g.base_legal.strip(), citacoes=[]))
    return Resposta(
        frases=frases,
        posicoes=[PosicaoDecisao(numero=n, posicao=p) for n, p in sorted(posicoes.items())],
    )
