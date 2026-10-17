"""
Construção do conjunto-ouro do harness, em quatro etapas idempotentes (cada uma
pula o que já existe, então pode ser interrompida e retomada):

  1. teses:    completa até --teses (reais das conversas + sintéticas filtradas)
  2. pool:     une o top-k de bm25, vetorial e pipeline para cada tese
  3. julgamento: o Jev julga os pares ainda sem julgamento, nas rodadas 1..N
  4. amostra:  escolhe os pares que a especialista vai rotular

    python -m avaliacao.construir [--teses 100] [--rodadas 2] [--sim]

As etapas 1 e 3 fazem chamadas pagas (OpenAI e Jev): mostram a estimativa e pedem
confirmação, a menos que --sim. Recusar uma etapa só pula essa etapa.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from typing import Callable

from avaliacao.amostra import ItemAmostra, escolher_amostra
from avaliacao.passo_zero import TOKENS_POR_JULGAMENTO, confirmar, uuids_origem
from avaliacao.pooling import CORREDORES
from avaliacao.store import Julgamento, Par, Tese

TOKENS_POR_TESE_OPENAI = 1500
LOTE_FETCH = 500


def _aviso(msg: str) -> None:
    print(msg, file=sys.stderr)


# --- funções puras ----------------------------------------------------------


def reais_novas(reais: list[dict], existentes: list[dict], limite: int) -> list[dict]:
    """Teses reais ainda não gravadas (compara o JSON canônico), até `limite`."""
    vistas = {json.dumps(e, sort_keys=True) for e in existentes}
    novas: list[dict] = []
    for estrutura in reais:
        if len(novas) >= limite:
            break
        chave = json.dumps(estrutura, sort_keys=True)
        if chave not in vistas:
            vistas.add(chave)
            novas.append(estrutura)
    return novas


def precisa_de_pool(pares: list[Par]) -> bool:
    """True se a tese ainda não tem nenhum par vindo de um corredor do pooling.

    Teses do passo 0 têm pares, mas só com o corredor "passo_zero": também
    precisam do pool. `adicionar_pares` une os corredores, então remontar é seguro."""
    return not any(c in CORREDORES for p in pares for c in p.corredores)


def itens_da_amostra(
    teses: list[Tese], pares: list[Par], julgamentos: list[Julgamento], juiz: str
) -> list[ItemAmostra]:
    """Um item por par que tem julgamento do `juiz` na rodada 1.

    confianca = min(confianca_rel, confianca_stance); None conta como 0.0, o que
    leva o par para a metade "incerta"."""
    teses_por_id = {t.id: t for t in teses}
    pares_por_id = {p.id: p for p in pares}
    itens: list[ItemAmostra] = []
    for j in julgamentos:
        if j.juiz != juiz or j.rodada != 1 or j.par_id not in pares_por_id:
            continue
        tese = teses_por_id[pares_por_id[j.par_id].tese_id]
        confianca = min(j.confianca_rel or 0.0, j.confianca_stance or 0.0)
        itens.append(ItemAmostra(j.par_id, tese.tema, tese.origem, j.relevancia, j.stance, confianca))
    return itens


def candidatos_sinteticos(acordaos, uuids: dict[str, str], usados: set[str]):
    """(acórdão, uuid, lado) ainda sem tese, alternando favorável e contrário.

    O lado vem do provimento: NEGADO -> "contrario"; APROVADO/PARCIAL -> "favoravel"."""
    por_lado: dict[str, list] = {"favoravel": [], "contrario": []}
    for a in acordaos:
        uid = uuids.get(a.id_documento)
        if uid is None or uid in usados:
            continue
        lado = "contrario" if getattr(a.provimento, "value", a.provimento) == "NEGADO" else "favoravel"
        por_lado[lado].append((a, uid, lado))
    alternados = itertools.zip_longest(por_lado["favoravel"], por_lado["contrario"])
    return [c for par in alternados for c in par if c is not None]


# --- carregamento de documentos ---------------------------------------------


class CarregadorDocs:
    """`carregar_doc(documento_id)` com cache; `pre_carregar` busca em lote."""

    def __init__(self, retriever):
        self._retriever = retriever
        self._cache: dict = {}

    def pre_carregar(self, ids) -> None:
        faltam = sorted({i for i in ids if i not in self._cache})
        for i in range(0, len(faltam), LOTE_FETCH):
            self._cache.update(self._retriever.fetch(faltam[i : i + LOTE_FETCH]))

    def __call__(self, documento_id: str):
        if documento_id not in self._cache:
            self.pre_carregar([documento_id])
        return self._cache[documento_id]  # KeyError se o documento não existe mais


# --- etapas -----------------------------------------------------------------


def etapa_julgamento(store, juiz, carregar_doc: Callable, rodadas: int) -> int:
    """Julga os pares sem julgamento de `juiz`, rodada a rodada, gravando a cada sucesso.

    Devolve quantos itens falharam (0 = tudo certo); as demais rodadas seguem
    mesmo com falhas, e um novo `etapa_julgamento` tenta só o que faltou."""
    from avaliacao.juiz import julgar_lote

    estruturas = {t.id: t.estrutura for t in store.listar_teses()}
    falhas = 0
    for rodada in range(1, rodadas + 1):
        pares = store.pares_sem_julgamento(juiz.nome, rodada)
        if not pares:
            print(f"Rodada {rodada}: nada a julgar.")
            continue
        pre_carregar = getattr(carregar_doc, "pre_carregar", None)
        if pre_carregar:
            pre_carregar([p.documento_id for p in pares])
        itens, sem_doc = [], 0
        for p in pares:
            try:
                itens.append((p.id, estruturas[p.tese_id], carregar_doc(p.documento_id)))
            except KeyError:
                _aviso(f"Par {p.id}: documento {p.documento_id} não encontrado; pulado")
                sem_doc += 1
        ok = julgar_lote(juiz, itens, rodada, store.gravar_julgamento)
        print(f"Jev rodada {rodada}: {ok}/{len(pares)} julgamentos")
        if ok < len(itens):
            _aviso(f"Atenção: {len(itens) - ok} julgamento(s) da rodada {rodada} falharam; rode de novo para retomar.")
        falhas += (len(itens) - ok) + sem_doc
    return falhas


def etapa_teses(store, deps, juiz, cliente, alvo: int, seed: int, sim: bool) -> int:
    """Completa as teses até `alvo` (todas as já gravadas contam). Devolve 1 se faltou tese."""
    from avaliacao.geracao import sortear_split, teses_reais
    from avaliacao.temas import TEMAS, atribuir_tema

    existentes = store.listar_teses()
    faltam = alvo - len(existentes)
    if faltam <= 0:
        print(f"Teses: já há {len(existentes)} (alvo {alvo}).")
        return 0

    novas = reais_novas(
        teses_reais(deps.database_url), [t.estrutura for t in existentes if t.origem == "real"], faltam
    )
    faltam_sinteticas = faltam - len(novas)
    jev_chamadas = len(novas) + 2 * faltam_sinteticas  # tema das reais + (filtro + tema) das sintéticas
    print(
        f"Teses: {len(existentes)} gravadas, alvo {alvo}. A criar: {len(novas)} reais + "
        f"{faltam_sinteticas} sintéticas.\n"
        f"Estimativa (mínima; tese rejeitada pelo filtro gasta chamadas a mais): "
        f"Jev {jev_chamadas} chamadas x ~{TOKENS_POR_JULGAMENTO} = ~{jev_chamadas * TOKENS_POR_JULGAMENTO} tokens; "
        f"OpenAI {faltam_sinteticas} teses x ~{TOKENS_POR_TESE_OPENAI} = ~{faltam_sinteticas * TOKENS_POR_TESE_OPENAI} tokens"
    )
    if not sim and not confirmar("Continuar com as teses? [s/N] "):
        print("Etapa de teses pulada.")
        return 0

    splits = sortear_split(TEMAS, seed)  # sempre a lista completa, não só os temas presentes

    for estrutura in novas:
        try:
            tema = atribuir_tema(estrutura, client=cliente)
        except Exception as e:  # noqa: BLE001 — uma tese ruim não derruba o lote
            _aviso(f"Tese real descartada: {e}")
            continue
        store.criar_tese(estrutura, "real", tema, splits[tema])
        print(f"Tese real criada (tema: {tema})")

    if faltam_sinteticas > 0:
        _completar_sinteticas(store, deps, juiz, cliente, alvo, seed, splits)

    total = len(store.listar_teses())
    if total < alvo:
        _aviso(f"Atenção: só há {total} teses (alvo {alvo}); rode de novo para tentar completar.")
        return 1
    return 0


def _completar_sinteticas(store, deps, juiz, cliente, alvo, seed, splits) -> None:
    from avaliacao.geracao import gerar_tese, passa_filtro, sortear_acordaos
    from avaliacao.temas import atribuir_tema

    teses = store.listar_teses()
    faltam = alvo - len(teses)
    usados = {t.documento_origem_id for t in teses if t.documento_origem_id}
    # Sorteia a mais: o filtro rejeita algumas. Aumentar n estende cada metade,
    # então os primeiros candidatos são sempre os mesmos entre execuções.
    acordaos = sortear_acordaos(deps.database_url, len(usados) + 2 * faltam, seed)
    uuids = uuids_origem(deps.database_url, acordaos)

    for acordao, uid, lado in candidatos_sinteticos(acordaos, uuids, usados):
        if faltam <= 0:
            break
        try:
            dados = gerar_tese(acordao, lado).model_dump()
            if not passa_filtro(juiz, dados, acordao):
                print(f"Tese de {acordao.id_documento} reprovada no filtro; descartada")
                continue
            tema = atribuir_tema(dados, client=cliente)
        except Exception as e:  # noqa: BLE001
            _aviso(f"Acórdão {acordao.id_documento} descartado: {e}")
            continue
        store.criar_tese(dados, "sintetica", tema, splits[tema], documento_origem_id=uid)
        faltam -= 1
        print(f"Tese sintética criada ({lado}, tema: {tema}); faltam {faltam}")
    if faltam > 0:
        _aviso(f"Acabaram os candidatos sorteados; faltam {faltam} tese(s) sintética(s).")


def etapa_pool(store, deps) -> int:
    """Monta o pool das teses que ainda não têm pares de corredor. Devolve quantas falharam."""
    from avaliacao.pooling import montar_pool
    from query.enrichment.schema import EstruturaArgumentativa

    pendentes = [t for t in store.listar_teses() if precisa_de_pool(store.pares_da_tese(t.id))]
    if not pendentes:
        print("Pool: todas as teses já têm pares.")
        return 0
    falhas = 0
    for i, tese in enumerate(pendentes, start=1):
        try:
            pool = montar_pool(
                EstruturaArgumentativa.model_validate(tese.estrutura),
                hybrid=deps.hybrid, retriever=deps.retriever, reranker=deps.reranker,
            )
        except Exception as e:  # noqa: BLE001
            _aviso(f"Pool da tese {tese.id} falhou: {e}")
            falhas += 1
            continue
        store.adicionar_pares(tese.id, pool)
        print(f"Pool {i}/{len(pendentes)}: {len(pool)} documentos")
    return falhas


def etapa_amostra(store, juiz, seed: int) -> None:
    if store.amostra():
        print("Amostra: já definida; nada a fazer.")
        return
    if store.pares_sem_julgamento(juiz.nome, 1):
        _aviso("Amostra adiada: ainda há pares sem julgamento na rodada 1. Rode de novo quando terminar.")
        return
    teses = store.listar_teses()
    pares = [p for t in teses for p in store.pares_da_tese(t.id)]
    itens = itens_da_amostra(teses, pares, store.julgamentos("jev:"), juiz.nome)
    if not itens:
        _aviso("Amostra: nenhum par julgado pelo Jev na rodada 1.")
        return
    ids = {i.par_id for i in itens}
    obrigatorios = {j.par_id for j in store.julgamentos("humano:")} & ids
    amostra = escolher_amostra(itens, seed=seed, obrigatorios=obrigatorios)
    store.definir_amostra(amostra)
    n_sorteada = sum(1 for m in amostra.values() if m == "sorteada")
    print(f"Amostra definida: {n_sorteada} sorteada + {len(amostra) - n_sorteada} incerta")


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m avaliacao.construir", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teses", type=int, default=100, help="total de teses (inclui as já gravadas)")
    parser.add_argument("--rodadas", type=int, default=2, help="rodadas de julgamento do Jev")
    parser.add_argument("--sim", action="store_true", help="pula as confirmações de custo")
    args = parser.parse_args(argv)

    from typesafe_sdk import TypeSafeClient

    from avaliacao.contexto import carregar_dependencias
    from avaliacao.juiz import JuizJev, perguntas_sha

    seed = int(os.getenv("AVALIACAO_SEED", "42"))
    deps = carregar_dependencias()
    cliente = TypeSafeClient()
    juiz = JuizJev(client=cliente)
    store = deps.store
    print(f"perguntas_sha={perguntas_sha()} jev={juiz.model} seed={seed}")

    falhas = etapa_teses(store, deps, juiz, cliente, args.teses, seed, args.sim)
    falhas += etapa_pool(store, deps)

    pendentes = sum(len(store.pares_sem_julgamento(juiz.nome, r)) for r in range(1, args.rodadas + 1))
    print(
        f"Julgamento: {pendentes} chamadas ao Jev x ~{TOKENS_POR_JULGAMENTO} = "
        f"~{pendentes * TOKENS_POR_JULGAMENTO} tokens"
    )
    if pendentes and not args.sim and not confirmar("Continuar com o julgamento? [s/N] "):
        print("Etapa de julgamento pulada.")
    elif pendentes:
        falhas += etapa_julgamento(store, juiz, CarregadorDocs(deps.retriever), args.rodadas)

    etapa_amostra(store, juiz, seed)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
