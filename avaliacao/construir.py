"""
Construção do conjunto-ouro do harness, em duas etapas idempotentes (cada uma
pula o que já existe, então pode ser interrompida e retomada):

  1. teses: completa até --teses (reais das conversas + sintéticas)
  2. pool:  une os 30 candidatos do híbrido e o top-10 de BM25 e do denso por tese

    python -m avaliacao.construir [--teses 100] [--sim]

A etapa 1 faz chamadas pagas à OpenAI (tese sintética e tema): mostra a
estimativa e pede confirmação, a menos que --sim. Recusar só pula a etapa.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from avaliacao.geracao import candidatos_sinteticos, uuids_origem
from avaliacao.store import Par

TOKENS_POR_TESE_OPENAI = 1500
TOKENS_POR_TEMA_OPENAI = 600


def _aviso(msg: str) -> None:
    print(msg, file=sys.stderr)


def confirmar(pergunta: str) -> bool:
    """Pergunta s/N; sem terminal interativo (EOF) conta como não."""
    try:
        return input(pergunta).strip().lower() == "s"
    except EOFError:
        return False


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
    """True se a tese ainda não tem nenhum par do corredor "hibrido" (pool novo).

    Teses do passo 0 ("passo_zero") e as de pool antigo (bm25/vetorial/pipeline)
    também precisam do pool novo. `adicionar_pares` une os corredores, então
    remontar é seguro e não apaga os pares antigos."""
    return not any("hibrido" in p.corredores for p in pares)


# --- etapas -----------------------------------------------------------------


def etapa_teses(store, deps, cliente, alvo: int, seed: int, sim: bool) -> int:
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
    tokens = faltam_sinteticas * TOKENS_POR_TESE_OPENAI + faltam * TOKENS_POR_TEMA_OPENAI
    print(
        f"Teses: {len(existentes)} gravadas, alvo {alvo}. A criar: {len(novas)} reais + "
        f"{faltam_sinteticas} sintéticas.\n"
        f"Estimativa OpenAI: {faltam_sinteticas} teses + {faltam} temas = ~{tokens} tokens"
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
        _completar_sinteticas(store, deps, cliente, alvo, seed, splits)

    total = len(store.listar_teses())
    if total < alvo:
        _aviso(f"Atenção: só há {total} teses (alvo {alvo}); rode de novo para tentar completar.")
        return 1
    return 0


def _completar_sinteticas(store, deps, cliente, alvo, seed, splits) -> None:
    from avaliacao.geracao import gerar_tese, sortear_acordaos
    from avaliacao.temas import atribuir_tema

    teses = store.listar_teses()
    faltam = alvo - len(teses)
    usados = {t.documento_origem_id for t in teses if t.documento_origem_id}
    # Estilo dos advogados: sem nenhuma tese deles, None mantém o prompt de sempre.
    exemplos = [
        t.estrutura["_texto_original"]
        for t in teses
        if t.origem == "advogado" and t.estrutura.get("_texto_original")
    ] or None
    # Sorteia a mais: alguma geração pode falhar. Aumentar n estende cada metade,
    # então os primeiros candidatos são sempre os mesmos entre execuções.
    acordaos = sortear_acordaos(deps.database_url, len(usados) + 2 * faltam, seed)
    uuids = uuids_origem(deps.database_url, acordaos)

    for acordao, uid, lado in candidatos_sinteticos(acordaos, uuids, usados):
        if faltam <= 0:
            break
        try:
            dados = gerar_tese(acordao, lado, client=cliente, exemplos=exemplos).model_dump()
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
    """Monta o pool novo das teses que ainda não têm o corredor híbrido. Devolve quantas falharam."""
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
                hybrid=deps.hybrid, retriever=deps.retriever,
            )
        except Exception as e:  # noqa: BLE001
            _aviso(f"Pool da tese {tese.id} falhou: {e}")
            falhas += 1
            continue
        store.adicionar_pares(tese.id, pool)
        print(f"Pool {i}/{len(pendentes)}: {len(pool)} documentos")
    return falhas


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m avaliacao.construir", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teses", type=int, default=100, help="total de teses (inclui as já gravadas)")
    parser.add_argument("--sim", action="store_true", help="pula a confirmação de custo")
    args = parser.parse_args(argv)

    from openai import OpenAI

    from avaliacao.contexto import carregar_dependencias

    seed = int(os.getenv("AVALIACAO_SEED", "42"))
    deps = carregar_dependencias()
    cliente = OpenAI()
    store = deps.store
    print(f"seed={seed}")

    falhas = etapa_teses(store, deps, cliente, args.teses, seed, args.sim)
    falhas += etapa_pool(store, deps)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
